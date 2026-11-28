"""Isolated SQLite storage (`ops_*` tables) for WeCom Report Agentic Analysis.

Shares `/opt/wechat-agent/data/app.db` safely alongside the Chairman's existing
`list_items` and `projects` tables without ever modifying or deleting them.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wecom_report_agentic_analysis.schemas import (
    ALL_TEMPLATES_BY_ID,
    NEW_TEMPLATE_EFFECTIVE_DATE,
    AlignmentAuditReport,
    ReportType,
    RoadmapGoal,
    SyncWatermarkRecord,
    TemplateSpec,
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
        """Create/migrate `ops_*` tables idempotently without touching any existing tables."""
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
                    work_date TEXT DEFAULT '',
                    submitted_at TEXT NOT NULL,
                    schema_era TEXT DEFAULT 'legacy_v1',
                    confidentiality_level TEXT DEFAULT 'standard',
                    parsed_fields_json TEXT DEFAULT '{}',
                    structured_extras_json TEXT DEFAULT '{}',
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

                CREATE TABLE IF NOT EXISTS ops_sync_watermarks (
                    template_id TEXT PRIMARY KEY,
                    template_name TEXT DEFAULT '',
                    report_type TEXT DEFAULT '',
                    template_status TEXT DEFAULT 'active',
                    full_backfill_completed INTEGER DEFAULT 0,
                    backfill_cursor_date TEXT DEFAULT '',
                    earliest_report_date TEXT DEFAULT '',
                    last_synced_at TEXT DEFAULT '',
                    total_records_synced INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_delivery_locks (
                    period_key TEXT PRIMARY KEY,
                    subject TEXT DEFAULT '',
                    recipient TEXT DEFAULT '',
                    pdf_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'sent',
                    created_at TEXT NOT NULL
                );
                """
            )
            report_cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(ops_wecom_reports)").fetchall()
            }
            for col_name, col_def in (
                ("work_date", "TEXT DEFAULT ''"),
                ("schema_era", "TEXT DEFAULT 'legacy_v1'"),
                ("confidentiality_level", "TEXT DEFAULT 'standard'"),
                ("structured_extras_json", "TEXT DEFAULT '{}'"),
            ):
                if col_name not in report_cols:
                    conn.execute(f"ALTER TABLE ops_wecom_reports ADD COLUMN {col_name} {col_def}")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ops_reports_work_date ON ops_wecom_reports(work_date)"
            )

            audit_cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(ops_alignment_audits)").fetchall()
            }
            if "full_report_json" not in audit_cols:
                conn.execute(
                    "ALTER TABLE ops_alignment_audits ADD COLUMN full_report_json TEXT DEFAULT '{}'"
                )

    def _row_to_report(self, row: sqlite3.Row) -> WeComReportRecord:
        keys = set(row.keys())
        raw_rt = str(row["report_type"])
        try:
            rt = ReportType(raw_rt)
        except ValueError:
            rt = ReportType.LEGACY_OTHER
        return WeComReportRecord(
            journal_uuid=str(row["journal_uuid"]),
            template_id=str(row["template_id"]),
            template_name=str(row["template_name"]),
            report_type=rt,
            submitter_userid=str(row["submitter_userid"]),
            submitter_name=str(row["submitter_name"] or ""),
            department=str(row["department"] or ""),
            report_date=str(row["report_date"]),
            work_date=str(row["work_date"] or "") if "work_date" in keys else "",
            submitted_at=str(row["submitted_at"]),
            schema_era=str(row["schema_era"] or "legacy_v1") if "schema_era" in keys else "legacy_v1",
            confidentiality_level=(
                str(row["confidentiality_level"] or "standard")
                if "confidentiality_level" in keys
                else "standard"
            ),
            parsed_fields=dict(_safe_json_loads(row["parsed_fields_json"], {})),
            structured_extras=(
                dict(_safe_json_loads(row["structured_extras_json"], {}))
                if "structured_extras_json" in keys
                else {}
            ),
            plain_text=str(row["plain_text"] or ""),
            attachment_media_ids=list(_safe_json_loads(row["attachment_media_ids_json"], [])),
            raw_payload=dict(_safe_json_loads(row["raw_payload_json"], {})),
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
                        report_date, work_date, submitted_at,
                        schema_era, confidentiality_level,
                        parsed_fields_json, structured_extras_json,
                        plain_text, attachment_media_ids_json, raw_payload_json, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        rep.work_date or rep.report_date,
                        rep.submitted_at,
                        rep.schema_era,
                        rep.confidentiality_level,
                        json.dumps(rep.parsed_fields, ensure_ascii=False),
                        json.dumps(rep.structured_extras, ensure_ascii=False),
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

        return [self._row_to_report(row) for row in rows]

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

    def save_alignment_audit(self, report: AlignmentAuditReport | Any, *, reports_analyzed_count: int) -> int:
        """Persist a verified `AlignmentAuditReport` or `DualTrackAuditReport` into `ops_alignment_audits`."""
        now = _now_iso()
        missed = getattr(report, "missed_tasks", []) or []
        stalled = getattr(report, "stalled_chairman_tasks", []) or []
        goals_bd = getattr(report, "goal_effort_breakdown", None)
        if goals_bd is None:
            goals_bd = getattr(report, "goal_effort_ledger", []) or []
        staffing = getattr(report, "staffing_recommendations", []) or []

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
                    json.dumps([m.model_dump(mode="json") for m in missed], ensure_ascii=False),
                    json.dumps([s.model_dump(mode="json") for s in stalled], ensure_ascii=False),
                    json.dumps([g.model_dump(mode="json") for g in goals_bd], ensure_ascii=False),
                    json.dumps([r.model_dump(mode="json") for r in staffing], ensure_ascii=False),
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
        """Strictly READ-ONLY query on existing `list_items` where `status != 'done'`."""
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

    def get_sync_watermark(self, template_id: str) -> SyncWatermarkRecord | None:
        """Return sync watermark record for `template_id`, or None if not yet initialized."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ops_sync_watermarks WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            return None
        return SyncWatermarkRecord(
            template_id=str(row["template_id"]),
            template_name=str(row["template_name"] or ""),
            report_type=str(row["report_type"] or ""),
            template_status=str(row["template_status"] or "active"),
            full_backfill_completed=bool(row["full_backfill_completed"]),
            backfill_cursor_date=str(row["backfill_cursor_date"] or ""),
            earliest_report_date=str(row["earliest_report_date"] or ""),
            last_synced_at=str(row["last_synced_at"] or ""),
            total_records_synced=int(row["total_records_synced"] or 0),
        )

    def list_sync_watermarks(self) -> list[SyncWatermarkRecord]:
        """Return all persisted template sync watermarks ordered by template_id."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ops_sync_watermarks ORDER BY template_id ASC"
            ).fetchall()
        return [
            SyncWatermarkRecord(
                template_id=str(row["template_id"]),
                template_name=str(row["template_name"] or ""),
                report_type=str(row["report_type"] or ""),
                template_status=str(row["template_status"] or "active"),
                full_backfill_completed=bool(row["full_backfill_completed"]),
                backfill_cursor_date=str(row["backfill_cursor_date"] or ""),
                earliest_report_date=str(row["earliest_report_date"] or ""),
                last_synced_at=str(row["last_synced_at"] or ""),
                total_records_synced=int(row["total_records_synced"] or 0),
            )
            for row in rows
        ]

    def upsert_sync_watermark(self, watermark: SyncWatermarkRecord) -> None:
        """Idempotently persist or update a template sync watermark."""
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ops_sync_watermarks (
                    template_id, template_name, report_type, template_status,
                    full_backfill_completed, backfill_cursor_date,
                    earliest_report_date, last_synced_at, total_records_synced, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(template_id) DO UPDATE SET
                    template_name = excluded.template_name,
                    report_type = excluded.report_type,
                    template_status = excluded.template_status,
                    full_backfill_completed = excluded.full_backfill_completed,
                    backfill_cursor_date = excluded.backfill_cursor_date,
                    earliest_report_date = excluded.earliest_report_date,
                    last_synced_at = excluded.last_synced_at,
                    total_records_synced = excluded.total_records_synced,
                    updated_at = excluded.updated_at
                """,
                (
                    watermark.template_id,
                    watermark.template_name,
                    watermark.report_type,
                    watermark.template_status,
                    1 if watermark.full_backfill_completed else 0,
                    watermark.backfill_cursor_date,
                    watermark.earliest_report_date,
                    watermark.last_synced_at,
                    int(watermark.total_records_synced),
                    now,
                ),
            )

    def export_reports_archive_jsonl_gz(
        self,
        output_path: str | Path,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Export persisted reports (including raw_payload) to a gzip-compressed JSONL cold backup."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        reports = self.list_reports(start_date=start_date, end_date=end_date)
        with gzip.open(out_p, "wt", encoding="utf-8") as fh:
            for rep in reports:
                fh.write(json.dumps(rep.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return {
            "archive_path": str(out_p),
            "record_count": len(reports),
            "size_bytes": out_p.stat().st_size,
            "exported_at": _now_iso(),
        }

    def backup_sqlite_snapshot(self, dest_path: str | Path) -> Path:
        """Create a consistent SQLite backup snapshot using sqlite3 online backup API."""
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            src_conn = sqlite3.connect(str(self.db_path), timeout=15.0)
            dst_conn = sqlite3.connect(str(dest), timeout=15.0)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()
        return dest

    def reparse_stored_reports(self, *, effective_date: str = NEW_TEMPLATE_EFFECTIVE_DATE) -> int:
        """Re-parse all stored `raw_payload_json` rows locally without calling WeCom API."""
        from wecom_report_agentic_analysis.wecom_journal_client import parse_journal_detail

        user_map = self.get_user_map()
        reparsed = 0
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM ops_wecom_reports").fetchall()
            for row in rows:
                raw_payload = _safe_json_loads(row["raw_payload_json"], {})
                if not isinstance(raw_payload, dict) or not raw_payload:
                    continue
                tid = str(row["template_id"])
                tpl = ALL_TEMPLATES_BY_ID.get(tid)
                if tpl is None:
                    raw_rt = str(row["report_type"] or ReportType.LEGACY_OTHER.value)
                    try:
                        rt_enum = ReportType(raw_rt)
                    except ValueError:
                        rt_enum = ReportType.LEGACY_OTHER
                    safe_tid = tid if len(tid) >= 8 else f"legacy_{tid or 'unknown'}"
                    tpl = TemplateSpec(
                        template_id=safe_tid,
                        template_name=str(row["template_name"] or "历史汇报"),
                        report_type=rt_enum,
                        status="disabled" if rt_enum in (ReportType.FIELD_SUPPORT_BACKFILL, ReportType.LEGACY_OTHER) else "active",
                        confidentiality_level=(
                            "finance_restricted" if rt_enum == ReportType.FINANCE_DAILY_10MIN else "standard"
                        ),
                    )
                rec = parse_journal_detail(
                    raw_payload,
                    template_spec=tpl,
                    user_map=user_map,
                    effective_date=effective_date,
                )
                conn.execute(
                    """
                    UPDATE ops_wecom_reports SET
                        template_name = ?,
                        submitter_name = COALESCE(NULLIF(?, ''), submitter_name),
                        department = COALESCE(NULLIF(?, ''), department),
                        work_date = ?,
                        schema_era = ?,
                        confidentiality_level = ?,
                        parsed_fields_json = ?,
                        structured_extras_json = ?,
                        plain_text = ?,
                        attachment_media_ids_json = ?
                    WHERE journal_uuid = ?
                    """,
                    (
                        rec.template_name,
                        rec.submitter_name,
                        rec.department,
                        rec.work_date or rec.report_date,
                        rec.schema_era,
                        rec.confidentiality_level,
                        json.dumps(rec.parsed_fields, ensure_ascii=False),
                        json.dumps(rec.structured_extras, ensure_ascii=False),
                        rec.plain_text,
                        json.dumps(rec.attachment_media_ids, ensure_ascii=False),
                        str(row["journal_uuid"]),
                    ),
                )
                reparsed += 1
        return reparsed

    def search_reports_readonly(
        self,
        *,
        staff_name: str | None = None,
        keyword: str | None = None,
        report_type: ReportType | str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
    ) -> list[WeComReportRecord]:
        """Strictly read-only search over `ops_wecom_reports` for ReAct drilldown tools."""
        clauses: list[str] = []
        params: list[Any] = []
        if staff_name:
            clauses.append("submitter_name = ?")
            params.append(staff_name.strip())
        if report_type is not None:
            rt_val = report_type.value if isinstance(report_type, ReportType) else str(report_type)
            clauses.append("report_type = ?")
            params.append(rt_val)
        if start_date:
            clauses.append("COALESCE(NULLIF(work_date, ''), report_date) >= ?")
            params.append(start_date[:10])
        if end_date:
            clauses.append("COALESCE(NULLIF(work_date, ''), report_date) <= ?")
            params.append(end_date[:10])
        if keyword:
            kw = f"%{keyword.strip()}%"
            clauses.append("(plain_text LIKE ? OR parsed_fields_json LIKE ? OR template_name LIKE ?)")
            params.extend([kw, kw, kw])

        sql = "SELECT * FROM ops_wecom_reports"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY COALESCE(NULLIF(work_date, ''), report_date) DESC, submitted_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_report(row) for row in rows]

    def has_delivery_lock(self, period_key: str) -> bool:
        """Return True if an email delivery for `period_key` has already been committed."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM ops_delivery_locks WHERE period_key = ?",
                (period_key,),
            ).fetchone()
        return row is not None

    def record_delivery_lock(
        self,
        period_key: str,
        *,
        subject: str,
        recipient: str,
        pdf_path: str,
        status: str = "sent",
    ) -> None:
        """Persist idempotent delivery receipt in `ops_delivery_locks`."""
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ops_delivery_locks (
                    period_key, subject, recipient, pdf_path, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(period_key) DO UPDATE SET
                    subject = excluded.subject,
                    recipient = excluded.recipient,
                    pdf_path = excluded.pdf_path,
                    status = excluded.status
                """,
                (period_key, subject, recipient, pdf_path, status, now),
            )
