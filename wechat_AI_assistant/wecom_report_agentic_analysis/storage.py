"""Isolated SQLite storage (`ops_*` tables) for WeCom Report Agentic Analysis.

Shares `/opt/wechat-agent/data/app.db` safely alongside the Chairman's existing
`list_items` and `projects` tables without ever modifying or deleting them.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wecom_report_agentic_analysis.schemas import (
    AlignmentAuditReport,
    ReportType,
    RoadmapGoal,
    WeComReportRecord,
    WeComUserRecord,
)

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_TZ_SHANGHAI).isoformat(timespec="seconds")


def _safe_json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


class CompanyOpsStorage:
    """Thread-safe SQLite store for `ops_*` company reporting & strategic alignment tables."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            with conn:
                yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create the four `ops_*` tables idempotently without touching any existing tables."""
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ops_wecom_reports (
                    journal_uuid TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    submitter_userid TEXT NOT NULL,
                    submitter_name TEXT DEFAULT '',
                    department TEXT DEFAULT '',
                    report_date TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    parsed_fields_json TEXT DEFAULT '{}',
                    plain_text TEXT DEFAULT '',
                    attachment_media_ids_json TEXT DEFAULT '[]',
                    raw_payload_json TEXT DEFAULT '{}',
                    synced_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ops_reports_date_type
                    ON ops_wecom_reports(report_date, report_type);
                CREATE INDEX IF NOT EXISTS idx_ops_reports_submitter_date
                    ON ops_wecom_reports(submitter_name, report_date);

                CREATE TABLE IF NOT EXISTS ops_wecom_users (
                    userid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department_names_json TEXT DEFAULT '[]',
                    position TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_company_roadmap (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_code TEXT NOT NULL UNIQUE,
                    horizon TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    target_outcomes TEXT DEFAULT '',
                    key_milestones_json TEXT DEFAULT '[]',
                    target_effort_share_pct REAL DEFAULT 20.0,
                    owner_names_json TEXT DEFAULT '[]',
                    priority TEXT DEFAULT 'P1',
                    status TEXT DEFAULT 'active',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_alignment_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_kind TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    reports_analyzed_count INTEGER DEFAULT 0,
                    alignment_score REAL NOT NULL,
                    missed_tasks_json TEXT DEFAULT '[]',
                    stalled_chairman_tasks_json TEXT DEFAULT '[]',
                    goal_effort_breakdown_json TEXT DEFAULT '[]',
                    staffing_recommendations_json TEXT DEFAULT '[]',
                    full_report_json TEXT DEFAULT '{}',
                    executive_brief_md TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            audit_cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(ops_alignment_audits)").fetchall()
            }
            if "full_report_json" not in audit_cols:
                conn.execute(
                    "ALTER TABLE ops_alignment_audits ADD COLUMN full_report_json TEXT DEFAULT '{}'"
                )

    def upsert_users(self, users: list[WeComUserRecord]) -> int:
        """Idempotently upsert WeCom employee directory records by `userid`."""
        if not users:
            return 0
        now = _now_iso()
        with self._lock, self._connect() as conn:
            for user in users:
                conn.execute(
                    """
                    INSERT INTO ops_wecom_users (
                        userid, name, department_names_json, position, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(userid) DO UPDATE SET
                        name = excluded.name,
                        department_names_json = excluded.department_names_json,
                        position = excluded.position,
                        is_active = excluded.is_active,
                        updated_at = excluded.updated_at
                    """,
                    (
                        user.userid,
                        user.name,
                        json.dumps(user.department_names, ensure_ascii=False),
                        user.position,
                        1 if user.is_active else 0,
                        now,
                    ),
                )
        return len(users)

    def get_user_map(self) -> dict[str, WeComUserRecord]:
        """Return `{userid: WeComUserRecord}` from `ops_wecom_users`."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM ops_wecom_users").fetchall()
        result: dict[str, WeComUserRecord] = {}
        for row in rows:
            result[str(row["userid"])] = WeComUserRecord(
                userid=str(row["userid"]),
                name=str(row["name"]),
                department_names=list(_safe_json_loads(row["department_names_json"], [])),
                position=str(row["position"] or ""),
                is_active=bool(row["is_active"]),
            )
        return result

    def get_existing_report_uuids(self) -> set[str]:
        """Return all already-persisted `journal_uuid` keys for fast incremental sync."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT journal_uuid FROM ops_wecom_reports").fetchall()
        return {str(row["journal_uuid"]) for row in rows}

    def insert_reports(self, reports: list[WeComReportRecord]) -> tuple[int, int]:
        """Idempotently insert reports by `journal_uuid`; return `(inserted, skipped_duplicate)`."""
        if not reports:
            return (0, 0)
        now = _now_iso()
        inserted = 0
        skipped = 0
        with self._lock, self._connect() as conn:
            for rep in reports:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ops_wecom_reports (
                        journal_uuid, template_id, template_name, report_type,
                        submitter_userid, submitter_name, department,
                        report_date, submitted_at, parsed_fields_json,
                        plain_text, attachment_media_ids_json, raw_payload_json, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rep.journal_uuid,
                        rep.template_id,
                        rep.template_name,
                        rep.report_type.value if isinstance(rep.report_type, ReportType) else str(rep.report_type),
                        rep.submitter_userid,
                        rep.submitter_name,
                        rep.department,
                        rep.report_date,
                        rep.submitted_at,
                        json.dumps(rep.parsed_fields, ensure_ascii=False),
                        rep.plain_text,
                        json.dumps(rep.attachment_media_ids, ensure_ascii=False),
                        json.dumps(rep.raw_payload, ensure_ascii=False),
                        now,
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        return (inserted, skipped)

    def list_reports(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        report_type: ReportType | str | None = None,
        submitter_name: str | None = None,
    ) -> list[WeComReportRecord]:
        """Query `ops_wecom_reports` with optional date range, template type, and submitter filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if start_date:
            clauses.append("report_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("report_date <= ?")
            params.append(end_date)
        if report_type is not None:
            rt_val = report_type.value if isinstance(report_type, ReportType) else str(report_type)
            clauses.append("report_type = ?")
            params.append(rt_val)
        if submitter_name:
            clauses.append("submitter_name = ?")
            params.append(submitter_name)

        sql = "SELECT * FROM ops_wecom_reports"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY report_date DESC, submitted_at DESC, journal_uuid ASC"

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            WeComReportRecord(
                journal_uuid=str(row["journal_uuid"]),
                template_id=str(row["template_id"]),
                template_name=str(row["template_name"]),
                report_type=ReportType(str(row["report_type"])),
                submitter_userid=str(row["submitter_userid"]),
                submitter_name=str(row["submitter_name"] or ""),
                department=str(row["department"] or ""),
                report_date=str(row["report_date"]),
                submitted_at=str(row["submitted_at"]),
                parsed_fields=dict(_safe_json_loads(row["parsed_fields_json"], {})),
                plain_text=str(row["plain_text"] or ""),
                attachment_media_ids=list(_safe_json_loads(row["attachment_media_ids_json"], [])),
                raw_payload=dict(_safe_json_loads(row["raw_payload_json"], {})),
            )
            for row in rows
        ]

    def upsert_roadmap_goal(self, goal: RoadmapGoal) -> int:
        """Insert or update a company strategic roadmap goal by `goal_code`; return row id."""
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ops_company_roadmap (
                    goal_code, horizon, category, title, target_outcomes,
                    key_milestones_json, target_effort_share_pct, owner_names_json,
                    priority, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(goal_code) DO UPDATE SET
                    horizon = excluded.horizon,
                    category = excluded.category,
                    title = excluded.title,
                    target_outcomes = excluded.target_outcomes,
                    key_milestones_json = excluded.key_milestones_json,
                    target_effort_share_pct = excluded.target_effort_share_pct,
                    owner_names_json = excluded.owner_names_json,
                    priority = excluded.priority,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    goal.goal_code,
                    goal.horizon,
                    goal.category,
                    goal.title,
                    goal.target_outcomes,
                    json.dumps(goal.key_milestones, ensure_ascii=False),
                    float(goal.target_effort_share_pct),
                    json.dumps(goal.owner_names, ensure_ascii=False),
                    goal.priority,
                    goal.status,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT id FROM ops_company_roadmap WHERE goal_code = ?",
                (goal.goal_code,),
            ).fetchone()
            return int(row["id"])

    def list_roadmap_goals(self, active_only: bool = True) -> list[RoadmapGoal]:
        """Return strategic roadmap goals ordered by priority and id."""
        sql = "SELECT * FROM ops_company_roadmap"
        params: list[Any] = []
        if active_only:
            sql += " WHERE status = 'active'"
        sql += " ORDER BY priority ASC, id ASC"
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            RoadmapGoal(
                id=int(row["id"]),
                goal_code=str(row["goal_code"]),
                horizon=str(row["horizon"]),
                category=row["category"],
                title=str(row["title"]),
                target_outcomes=str(row["target_outcomes"] or ""),
                key_milestones=list(_safe_json_loads(row["key_milestones_json"], [])),
                target_effort_share_pct=float(row["target_effort_share_pct"]),
                owner_names=list(_safe_json_loads(row["owner_names_json"], [])),
                priority=row["priority"],
                status=row["status"],
            )
            for row in rows
        ]

    def save_alignment_audit(self, report: AlignmentAuditReport, *, reports_analyzed_count: int) -> int:
        """Persist a verified `AlignmentAuditReport` into `ops_alignment_audits`; return row id."""
        now = _now_iso()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO ops_alignment_audits (
                    audit_kind, period_start, period_end, reports_analyzed_count,
                    alignment_score, missed_tasks_json, stalled_chairman_tasks_json,
                    goal_effort_breakdown_json, staffing_recommendations_json,
                    full_report_json, executive_brief_md, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.audit_kind,
                    report.period_start,
                    report.period_end,
                    int(reports_analyzed_count),
                    float(report.alignment_score),
                    json.dumps([m.model_dump() for m in report.missed_tasks], ensure_ascii=False),
                    json.dumps([s.model_dump() for s in report.stalled_chairman_tasks], ensure_ascii=False),
                    json.dumps([g.model_dump() for g in report.goal_effort_breakdown], ensure_ascii=False),
                    json.dumps([r.model_dump() for r in report.staffing_recommendations], ensure_ascii=False),
                    json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
                    report.executive_brief_md,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_alignment_audits(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return latest alignment audits ordered newest first."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ops_alignment_audits ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row["id"]),
                    "audit_kind": str(row["audit_kind"]),
                    "period_start": str(row["period_start"]),
                    "period_end": str(row["period_end"]),
                    "reports_analyzed_count": int(row["reports_analyzed_count"]),
                    "alignment_score": float(row["alignment_score"]),
                    "missed_tasks": _safe_json_loads(row["missed_tasks_json"], []),
                    "stalled_chairman_tasks": _safe_json_loads(row["stalled_chairman_tasks_json"], []),
                    "goal_effort_breakdown": _safe_json_loads(row["goal_effort_breakdown_json"], []),
                    "staffing_recommendations": _safe_json_loads(row["staffing_recommendations_json"], []),
                    "full_report": _safe_json_loads(row["full_report_json"], {}),
                    "executive_brief_md": str(row["executive_brief_md"]),
                    "created_at": str(row["created_at"]),
                }
            )
        return out

    def read_chairman_open_tasks(self) -> list[dict[str, Any]]:
        """Strictly READ-ONLY query on existing `list_items` where `status != 'done'`.

        Returns `[]` cleanly when `list_items` does not exist in the SQLite file.
        """
        with self._lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='list_items'"
            ).fetchone()
            if not exists:
                return []
            rows = conn.execute(
                "SELECT * FROM list_items WHERE LOWER(COALESCE(status, '')) != 'done' ORDER BY id ASC"
            ).fetchall()
        return [dict(row) for row in rows]
