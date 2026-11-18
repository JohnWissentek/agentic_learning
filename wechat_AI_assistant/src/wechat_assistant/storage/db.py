"""Lightweight SQLite 3-layer memory store, dynamic priority engine, workload model, and 24h undo snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    return date.today().isoformat()


def _parse_iso_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(val[:10])
    except ValueError:
        return None


def compute_priority_score(priority: str, planned_end_at: str | None, list_type: str) -> float:
    """Compute Ch.20 dynamic priority score for sorting actions and waiting items."""
    base = {"P0": 100.0, "P1": 60.0, "P2": 20.0}.get(priority, 40.0)
    due = _parse_iso_date(planned_end_at)
    if due is not None:
        days_left = (due - date.today()).days
        if days_left <= 0:
            base += 40.0
        elif days_left <= 2:
            base += 25.0
        elif days_left <= 5:
            base += 10.0
    if list_type == ListType.WAITING_FOR.value:
        base += 5.0
    return round(base, 2)


class Database:
    """Thread-safe SQLite store managing `app.db` (`3+1` core tables + undo & proposal state)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.fts_tokenizer = "unicode61"
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    external_msg_id TEXT UNIQUE,
                    sender TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    raw_text TEXT DEFAULT '',
                    content_hash TEXT DEFAULT '',
                    is_confidential INTEGER DEFAULT 0,
                    onedrive_raw_path TEXT DEFAULT '',
                    onedrive_archive_path TEXT DEFAULT '',
                    onedrive_web_url TEXT DEFAULT '',
                    extracted_pages_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    aliases_json TEXT DEFAULT '[]',
                    category TEXT DEFAULT 'project',
                    work_domain TEXT DEFAULT '项目交付',
                    status TEXT DEFAULT 'active',
                    planned_start_date TEXT DEFAULT '',
                    target_end_date TEXT DEFAULT '',
                    total_estimated_hours REAL DEFAULT 0.0,
                    total_actual_hours REAL DEFAULT 0.0,
                    onedrive_folder TEXT DEFAULT '',
                    onedrive_web_url TEXT DEFAULT '',
                    latest_brief TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_type TEXT NOT NULL,
                    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    project_name TEXT DEFAULT '通用待办',
                    work_domain TEXT DEFAULT '产品研发',
                    title TEXT NOT NULL,
                    owner TEXT DEFAULT '本人',
                    planned_start_at TEXT DEFAULT '',
                    planned_end_at TEXT DEFAULT '',
                    actual_start_at TEXT DEFAULT '',
                    actual_end_at TEXT DEFAULT '',
                    estimated_hours REAL DEFAULT 0.5,
                    actual_hours REAL,
                    priority TEXT DEFAULT 'P1',
                    priority_score REAL DEFAULT 60.0,
                    status TEXT DEFAULT 'todo',
                    stage TEXT DEFAULT '闪念收集',
                    relation_note TEXT DEFAULT '',
                    source_ids_json TEXT DEFAULT '[]',
                    onedrive_doc_paths_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_kind TEXT NOT NULL,
                    trigger_tags_json TEXT DEFAULT '[]',
                    rule_text TEXT NOT NULL,
                    baseline_hours REAL,
                    correction_count INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'confirmed',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    source_ids_json TEXT DEFAULT '[]',
                    pending_files_json TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS undo_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    restored INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS model_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tier TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    reasoning_tokens INTEGER DEFAULT 0,
                    latency_ms INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL DEFAULT 'owner',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    intent TEXT DEFAULT '',
                    topic_tags_json TEXT DEFAULT '[]',
                    proposal_id INTEGER,
                    is_confidential INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conv_turns_thread ON conversation_turns(thread_id, id DESC);

                CREATE TABLE IF NOT EXISTS episode_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL DEFAULT 'owner',
                    summary_text TEXT NOT NULL,
                    last_turn_id INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_episode_thread ON episode_summaries(thread_id, id DESC);
                """
            )
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts "
                    "USING fts5(source_id UNINDEXED, title, content, tokenize='trigram');"
                )
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS conversation_turns_fts "
                    "USING fts5(turn_id UNINDEXED, content, tags, tokenize='trigram');"
                )
                self.fts_tokenizer = "trigram"
            except sqlite3.OperationalError:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts "
                    "USING fts5(source_id UNINDEXED, title, content, tokenize='unicode61');"
                )
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS conversation_turns_fts "
                    "USING fts5(turn_id UNINDEXED, content, tags, tokenize='unicode61');"
                )
                self.fts_tokenizer = "unicode61"

            # Deduplicate FTS rows left by the legacy text-vs-integer backfill bug, then backfill missing rows.
            conn.execute(
                """
                DELETE FROM conversation_turns_fts
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM conversation_turns_fts GROUP BY CAST(turn_id AS INTEGER)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO conversation_turns_fts (turn_id, content, tags)
                SELECT CAST(id AS TEXT), content, topic_tags_json FROM conversation_turns
                WHERE is_confidential = 0
                  AND id NOT IN (SELECT CAST(turn_id AS INTEGER) FROM conversation_turns_fts)
                """
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS seen_external_ids (ext_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL)"
            )

    def mark_external_seen(self, ext_id: str) -> bool:
        """Atomically mark an external message id as processed. Returns True only the first time."""
        if not ext_id:
            return True
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO seen_external_ids (ext_id, seen_at) VALUES (?, ?)",
                (ext_id, _now_str()),
            )
            return cur.rowcount > 0

    # --- Raw sources & hybrid search ---

    def insert_raw_source(
        self,
        *,
        source_type: str,
        external_msg_id: str | None,
        sender: str,
        title: str,
        raw_text: str,
        is_confidential: bool = False,
        onedrive_raw_path: str = "",
        onedrive_archive_path: str = "",
        onedrive_web_url: str = "",
        extracted_pages: list[dict[str, Any]] | None = None,
    ) -> tuple[int, bool]:
        """Insert a raw source with `external_msg_id` deduplication. Returns `(id, is_new)`."""
        pages = extracted_pages or []
        content_hash = hashlib.sha256(f"{source_type}|{title}|{raw_text}".encode("utf-8")).hexdigest()
        now = _now_str()

        with self._lock, self._connect() as conn:
            if external_msg_id:
                existing = conn.execute(
                    "SELECT id FROM raw_sources WHERE external_msg_id = ?",
                    (external_msg_id,),
                ).fetchone()
                if existing:
                    return int(existing["id"]), False

            cur = conn.execute(
                """
                INSERT INTO raw_sources (
                    source_type, external_msg_id, sender, title, raw_text, content_hash,
                    is_confidential, onedrive_raw_path, onedrive_archive_path, onedrive_web_url,
                    extracted_pages_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_type,
                    external_msg_id,
                    sender,
                    title,
                    raw_text,
                    content_hash,
                    1 if is_confidential else 0,
                    onedrive_raw_path,
                    onedrive_archive_path,
                    onedrive_web_url,
                    json.dumps(pages, ensure_ascii=False),
                    now,
                ),
            )
            source_id = int(cur.lastrowid)
            combined_pages = "\n".join(
                f"[第{p.get('page', '?')}页] {p.get('text', '')}" for p in pages
            )
            full_index_text = "\n".join(part for part in (raw_text, combined_pages) if part)
            conn.execute(
                "INSERT INTO sources_fts (source_id, title, content) VALUES (?, ?, ?)",
                (str(source_id), title, full_index_text),
            )
            return source_id, True

    def update_source_onedrive_paths(
        self,
        source_id: int,
        *,
        raw_path: str = "",
        archive_path: str = "",
        web_url: str = "",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE raw_sources
                SET onedrive_raw_path = COALESCE(NULLIF(?, ''), onedrive_raw_path),
                    onedrive_archive_path = COALESCE(NULLIF(?, ''), onedrive_archive_path),
                    onedrive_web_url = COALESCE(NULLIF(?, ''), onedrive_web_url)
                WHERE id = ?
                """,
                (raw_path, archive_path, web_url, source_id),
            )

    def search_sources(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search raw_sources & extracted pages using FTS5 + keyword LIKE fallback."""
        tokens = [t.strip() for t in query.replace("?", " ").replace("？", " ").split() if len(t.strip()) >= 2]
        if not tokens and len(query.strip()) >= 2:
            tokens = [query.strip()]

        matched_ids: dict[int, float] = {}
        with self._lock, self._connect() as conn:
            for tok in tokens[:5]:
                safe_q = '"' + tok.replace('"', "") + '"'
                try:
                    rows = conn.execute(
                        "SELECT source_id FROM sources_fts WHERE sources_fts MATCH ? LIMIT ?",
                        (safe_q, top_k * 2),
                    ).fetchall()
                    for r in rows:
                        sid = int(r["source_id"])
                        matched_ids[sid] = matched_ids.get(sid, 0.0) + 2.0
                except sqlite3.OperationalError:
                    pass

                like_pat = f"%{tok}%"
                rows_like = conn.execute(
                    """
                    SELECT id FROM raw_sources
                    WHERE title LIKE ? OR raw_text LIKE ? OR extracted_pages_json LIKE ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (like_pat, like_pat, like_pat, top_k * 2),
                ).fetchall()
                for r in rows_like:
                    sid = int(r["id"])
                    matched_ids[sid] = matched_ids.get(sid, 0.0) + 1.0

            if not matched_ids and query.strip():
                like_pat = f"%{query.strip()}%"
                for r in conn.execute(
                    "SELECT id FROM raw_sources WHERE title LIKE ? OR raw_text LIKE ? OR extracted_pages_json LIKE ? LIMIT ?",
                    (like_pat, like_pat, like_pat, top_k),
                ).fetchall():
                    matched_ids[int(r["id"])] = 1.0

            if not matched_ids:
                return []

            ordered_ids = sorted(matched_ids.keys(), key=lambda x: (-matched_ids[x], -x))[:top_k]
            placeholders = ",".join("?" for _ in ordered_ids)
            rows = conn.execute(
                f"SELECT * FROM raw_sources WHERE id IN ({placeholders})",
                ordered_ids,
            ).fetchall()
            row_map = {int(r["id"]): dict(r) for r in rows}
            results = []
            for sid in ordered_ids:
                if sid in row_map:
                    item = row_map[sid]
                    item["score"] = matched_ids[sid]
                    item["pages"] = json.loads(item.get("extracted_pages_json") or "[]")
                    results.append(item)
            return results

    def get_source_pages(self, source_id: int, page_numbers: list[int] | None = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, onedrive_archive_path, onedrive_web_url, extracted_pages_json, raw_text "
                "FROM raw_sources WHERE id = ?",
                (source_id,),
            ).fetchone()
            if not row:
                return []
            pages = json.loads(row["extracted_pages_json"] or "[]")
            if not pages and row["raw_text"]:
                pages = [{"page": 1, "text": row["raw_text"]}]
            if page_numbers:
                target = set(page_numbers)
                pages = [p for p in pages if p.get("page") in target]
            return [
                {
                    "source_id": int(row["id"]),
                    "title": row["title"],
                    "page": p.get("page", 1),
                    "text": p.get("text", ""),
                    "web_url": row["onedrive_web_url"] or "",
                }
                for p in pages
            ]

    # --- Projects, list items, workload & analytics ---

    def _upsert_project(
        self,
        conn: sqlite3.Connection,
        *,
        name: str,
        work_domain: str,
        start_date: str,
        end_date: str,
        onedrive_folder: str,
        onedrive_web_url: str = "",
        brief: str = "",
    ) -> tuple[int, dict[str, Any] | None]:
        now = _now_str()
        existing = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        if existing:
            prev = dict(existing)
            new_end = end_date if (end_date and (not prev["target_end_date"] or end_date > prev["target_end_date"])) else prev["target_end_date"]
            new_start = start_date if (start_date and (not prev["planned_start_date"] or start_date < prev["planned_start_date"])) else prev["planned_start_date"]
            conn.execute(
                """
                UPDATE projects
                SET planned_start_date = ?, target_end_date = ?,
                    onedrive_folder = COALESCE(NULLIF(?, ''), onedrive_folder),
                    onedrive_web_url = COALESCE(NULLIF(?, ''), onedrive_web_url),
                    latest_brief = COALESCE(NULLIF(?, ''), latest_brief),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_start, new_end, onedrive_folder, onedrive_web_url, brief, now, prev["id"]),
            )
            return int(prev["id"]), prev

        cur = conn.execute(
            """
            INSERT INTO projects (
                name, work_domain, status, planned_start_date, target_end_date,
                onedrive_folder, onedrive_web_url, latest_brief, updated_at
            ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (name, work_domain, start_date, end_date, onedrive_folder, onedrive_web_url, brief, now),
        )
        return int(cur.lastrowid), None

    def _recalculate_project_hours(self, conn: sqlite3.Connection, project_id: int) -> None:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(estimated_hours), 0.0) AS est,
                   COALESCE(SUM(COALESCE(actual_hours, 0.0)), 0.0) AS act
            FROM list_items WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        conn.execute(
            "UPDATE projects SET total_estimated_hours = ?, total_actual_hours = ?, updated_at = ? WHERE id = ?",
            (round(float(row["est"]), 2), round(float(row["act"]), 2), _now_str(), project_id),
        )

    def apply_proposal_atomic(
        self,
        *,
        proposal_id: int | None,
        actions: list[ActionMutation],
        source_ids: list[int],
        doc_paths: list[str],
        brief_summary: str = "",
        project_web_urls: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Commit a confirmed TriageProposal atomically and record a 24h undo snapshot."""
        now = _now_str()
        inserted_item_ids: list[int] = []
        created_project_ids: list[int] = []
        previous_projects: list[dict[str, Any]] = []
        web_map = project_web_urls or {}

        with self._lock, self._connect() as conn:
            touched_project_ids: set[int] = set()
            for act in actions:
                proj_name = act.project_name.strip() or "日常事务"
                proj_id, prev_proj = self._upsert_project(
                    conn,
                    name=proj_name,
                    work_domain=act.work_domain.value,
                    start_date=act.planned_start_at,
                    end_date=act.planned_end_at,
                    onedrive_folder=act.onedrive_target_dir,
                    onedrive_web_url=web_map.get(proj_name, ""),
                    brief=brief_summary[:300],
                )
                touched_project_ids.add(proj_id)
                if prev_proj is None and proj_id not in created_project_ids:
                    created_project_ids.append(proj_id)
                elif prev_proj is not None and not any(p["id"] == prev_proj["id"] for p in previous_projects):
                    previous_projects.append(prev_proj)

                score = compute_priority_score(act.priority.value, act.planned_end_at, act.list_type.value)
                stage = "闪念收集" if act.list_type == ListType.IDEA else "待执行"
                cur = conn.execute(
                    """
                    INSERT INTO list_items (
                        list_type, project_id, project_name, work_domain, title, owner,
                        planned_start_at, planned_end_at, estimated_hours, priority, priority_score,
                        status, stage, source_ids_json, onedrive_doc_paths_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?)
                    """,
                    (
                        act.list_type.value,
                        proj_id,
                        proj_name,
                        act.work_domain.value,
                        act.title,
                        act.owner,
                        act.planned_start_at,
                        act.planned_end_at,
                        round(float(act.estimated_hours), 2),
                        act.priority.value,
                        score,
                        stage,
                        json.dumps(source_ids),
                        json.dumps(doc_paths, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                inserted_item_ids.append(int(cur.lastrowid))

            for pid in touched_project_ids:
                self._recalculate_project_hours(conn, pid)

            snapshot = {
                "inserted_item_ids": inserted_item_ids,
                "created_project_ids": created_project_ids,
                "previous_projects": previous_projects,
            }
            cur_undo = conn.execute(
                "INSERT INTO undo_snapshots (proposal_id, snapshot_json, created_at, restored) VALUES (?, ?, ?, 0)",
                (proposal_id, json.dumps(snapshot, ensure_ascii=False), now),
            )
            if proposal_id is not None:
                conn.execute("UPDATE pending_proposals SET status = 'confirmed' WHERE id = ?", (proposal_id,))

            return {
                "inserted_item_ids": inserted_item_ids,
                "undo_snapshot_id": int(cur_undo.lastrowid),
            }

    def undo_last_commit(self, max_age_hours: int = 24) -> tuple[bool, str]:
        """Roll back the most recent committed proposal within `max_age_hours`."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM undo_snapshots WHERE restored = 0 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return False, "当前没有可撤销的近期落盘记录。"

            created_dt = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - created_dt > timedelta(hours=max_age_hours):
                return False, f"最近一次操作已超过 {max_age_hours} 小时撤销窗口。"

            snap = json.loads(row["snapshot_json"])
            for iid in snap.get("inserted_item_ids", []):
                conn.execute("DELETE FROM list_items WHERE id = ?", (int(iid),))
            for pid in snap.get("created_project_ids", []):
                conn.execute("DELETE FROM projects WHERE id = ?", (int(pid),))
            for prev in snap.get("previous_projects", []):
                conn.execute(
                    """
                    UPDATE projects
                    SET planned_start_date = ?, target_end_date = ?,
                        total_estimated_hours = ?, total_actual_hours = ?,
                        latest_brief = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        prev["planned_start_date"],
                        prev["target_end_date"],
                        prev["total_estimated_hours"],
                        prev["total_actual_hours"],
                        prev["latest_brief"],
                        prev["updated_at"],
                        prev["id"],
                    ),
                )
            conn.execute("UPDATE undo_snapshots SET restored = 1 WHERE id = ?", (row["id"],))
            return True, f"已完整回滚 {len(snap.get('inserted_item_ids', []))} 条清单项及对应项目记录。"

    # --- Pending HITL proposals (F8 crash-recovery) ---

    def save_pending_proposal(
        self,
        *,
        thread_id: str,
        proposal_dict: dict[str, Any],
        source_ids: list[int],
        pending_files: list[dict[str, Any]] | None = None,
    ) -> int:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE pending_proposals SET status = 'superseded' WHERE thread_id = ? AND status = 'pending'",
                (thread_id,),
            )
            cur = conn.execute(
                """
                INSERT INTO pending_proposals (thread_id, proposal_json, source_ids_json, pending_files_json, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (
                    thread_id,
                    json.dumps(proposal_dict, ensure_ascii=False),
                    json.dumps(source_ids),
                    json.dumps(pending_files or [], ensure_ascii=False),
                    _now_str(),
                ),
            )
            return int(cur.lastrowid)

    def get_latest_pending_proposal(self, thread_id: str | None = None) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            if thread_id:
                row = conn.execute(
                    "SELECT * FROM pending_proposals WHERE thread_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
                    (thread_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM pending_proposals WHERE status = 'pending' ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if not row:
                return None
            out = dict(row)
            out["proposal"] = json.loads(out["proposal_json"])
            out["source_ids"] = json.loads(out["source_ids_json"])
            out["pending_files"] = json.loads(out["pending_files_json"])
            return out

    def cancel_pending_proposal(self, proposal_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE pending_proposals SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
                (proposal_id,),
            )
            return cur.rowcount > 0

    def append_conversation_turn(
        self,
        *,
        thread_id: str = "owner",
        role: str,
        content: str,
        intent: str = "",
        topic_tags: list[str] | None = None,
        proposal_id: int | None = None,
        is_confidential: bool = False,
        created_at: str | None = None,
    ) -> int:
        ts = created_at or _now_str()
        tags_json = json.dumps(topic_tags or [], ensure_ascii=False)
        tags_text = " ".join(topic_tags or [])
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO conversation_turns (
                    thread_id, role, content, intent, topic_tags_json, proposal_id, is_confidential, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, role, content, intent, tags_json, proposal_id, 1 if is_confidential else 0, ts),
            )
            turn_id = int(cur.lastrowid)
            if not is_confidential:
                conn.execute(
                    "INSERT INTO conversation_turns_fts (turn_id, content, tags) VALUES (?, ?, ?)",
                    (str(turn_id), content, tags_text),
                )
            return turn_id

    def get_latest_episode_summary(self, thread_id: str = "owner") -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM episode_summaries WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
            return dict(row) if row else None

    def upsert_episode_summary(self, thread_id: str, summary_text: str, last_turn_id: int) -> None:
        now = _now_str()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO episode_summaries (thread_id, summary_text, last_turn_id, updated_at) VALUES (?, ?, ?, ?)",
                (thread_id, summary_text.strip()[:1200], int(last_turn_id), now),
            )

    def get_turns_since(self, thread_id: str = "owner", after_id: int = 0, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE thread_id = ? AND is_confidential = 0 AND id > ?
                ORDER BY id ASC LIMIT ?
                """,
                (thread_id, after_id, limit),
            ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                item["topic_tags"] = json.loads(item.get("topic_tags_json") or "[]")
                out.append(item)
            return out

    def get_recent_conversation_turns(self, thread_id: str = "owner", limit: int = 10) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE thread_id = ? AND is_confidential = 0
                ORDER BY id DESC LIMIT ?
                """,
                (thread_id, limit),
            ).fetchall()
            out = []
            for r in reversed(rows):
                item = dict(r)
                item["topic_tags"] = json.loads(item.get("topic_tags_json") or "[]")
                out.append(item)
            return out

    def search_conversation_turns(
        self,
        keywords: list[str],
        *,
        thread_id: str = "owner",
        exclude_ids: set[int] | None = None,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        clean_kws = [k.strip() for k in keywords if len(k.strip()) >= 2]
        if not clean_kws:
            return []
        excl = exclude_ids or set()
        scored: dict[int, tuple[float, dict[str, Any]]] = {}
        with self._lock, self._connect() as conn:
            for kw in clean_kws[:8]:
                matched_rows: list[sqlite3.Row] = []
                # 1) Try FTS5 trigram/unicode61 first (fast & handles longer phrases cleanly)
                if len(kw) >= 3 or self.fts_tokenizer == "unicode61":
                    safe_kw = kw.replace('"', "")
                    try:
                        matched_rows = conn.execute(
                            """
                            SELECT c.* FROM conversation_turns_fts f
                            JOIN conversation_turns c ON c.id = CAST(f.turn_id AS INTEGER)
                            WHERE f.conversation_turns_fts MATCH ?
                              AND c.thread_id = ? AND c.is_confidential = 0
                            ORDER BY c.id DESC LIMIT ?
                            """,
                            (f'"{safe_kw}"', thread_id, limit * 2),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        matched_rows = []
                # 2) Fallback to LIKE for short 2-char Chinese tokens or zero FTS hits
                if not matched_rows:
                    pat = f"%{kw}%"
                    matched_rows = conn.execute(
                        """
                        SELECT * FROM conversation_turns
                        WHERE thread_id = ? AND is_confidential = 0
                          AND (content LIKE ? OR topic_tags_json LIKE ?)
                        ORDER BY id DESC LIMIT ?
                        """,
                        (thread_id, pat, pat, limit * 2),
                    ).fetchall()
                for r in matched_rows:
                    tid = int(r["id"])
                    if tid in excl:
                        continue
                    item = dict(r)
                    item["topic_tags"] = json.loads(item.get("topic_tags_json") or "[]")
                    prev_score = scored[tid][0] if tid in scored else 0.0
                    bonus = 2.0 if kw in item["topic_tags"] else 1.0
                    scored[tid] = (prev_score + bonus, item)
        ordered = sorted(scored.values(), key=lambda x: (-x[0], -int(x[1]["id"])))[:limit]
        return [pair[1] for pair in ordered]

    # --- Check-ins, Web editing, Workload & Analytics ---

    def start_item(self, item_id: int) -> dict[str, Any] | None:
        now = _now_str()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE list_items SET status = 'in_progress', actual_start_at = ?, updated_at = ? WHERE id = ?",
                (row["actual_start_at"] or now, now, item_id),
            )
            return dict(conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone())

    def complete_item(self, item_id: int, actual_hours: float | None = None) -> dict[str, Any] | None:
        now = _now_str()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            hours = round(float(actual_hours if actual_hours is not None else row["estimated_hours"]), 2)
            start_str = row["actual_start_at"] or now
            start_d = _parse_iso_date(row["actual_start_at"]) or _parse_iso_date(row["planned_start_at"]) or _parse_iso_date(row["created_at"]) or date.today()
            span_days = max(1, (date.today() - start_d).days + 1)
            conn.execute(
                """
                UPDATE list_items
                SET status = 'done',
                    actual_start_at = COALESCE(NULLIF(actual_start_at, ''), ?),
                    actual_end_at = ?,
                    actual_hours = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (start_str, now, hours, now, item_id),
            )
            if row["project_id"]:
                self._recalculate_project_hours(conn, int(row["project_id"]))

            # Record actual completion calendar span into memory rules
            conn.execute(
                """
                INSERT INTO memory_rules (memory_kind, trigger_tags_json, rule_text, baseline_hours, correction_count, status, updated_at)
                VALUES ('span_baseline', ?, ?, ?, 1, 'confirmed', ?)
                """,
                (
                    json.dumps([row["work_domain"], row["project_name"]], ensure_ascii=False),
                    f"同类事项「{row['title'][:40]}」实际完成跨度 {span_days} 天（{start_d.isoformat()} ~ {date.today().isoformat()}）",
                    float(span_days),
                    now,
                ),
            )
            out = dict(conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone())
            out["actual_span_days"] = span_days
            return out

    def update_item_fields(self, item_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
        allowed_cols = {
            "title",
            "list_type",
            "work_domain",
            "project_name",
            "owner",
            "planned_start_at",
            "planned_end_at",
            "estimated_hours",
            "actual_hours",
            "priority",
            "status",
            "stage",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_cols and v is not None}
        if not filtered:
            return None

        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            merged = dict(row) | filtered
            filtered["priority_score"] = compute_priority_score(
                merged["priority"], merged["planned_end_at"], merged["list_type"]
            )
            filtered["updated_at"] = _now_str()
            sets = ", ".join(f"{k} = ?" for k in filtered)
            conn.execute(f"UPDATE list_items SET {sets} WHERE id = ?", (*filtered.values(), item_id))
            if row["project_id"]:
                self._recalculate_project_hours(conn, int(row["project_id"]))
            return dict(conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone())

    def delete_item(self, item_id: int) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT project_id FROM list_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM list_items WHERE id = ?", (item_id,))
            if row["project_id"]:
                self._recalculate_project_hours(conn, int(row["project_id"]))
            return True

    def promote_idea_to_project(
        self,
        item_id: int,
        *,
        project_name: str,
        planned_start_at: str,
        planned_end_at: str,
        estimated_hours: float,
    ) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            proj_id, _ = self._upsert_project(
                conn,
                name=project_name,
                work_domain=row["work_domain"],
                start_date=planned_start_at,
                end_date=planned_end_at,
                onedrive_folder=f"01_项目归档/{project_name}",
            )
            score = compute_priority_score("P1", planned_end_at, ListType.PROJECT_ACTION.value)
            conn.execute(
                """
                UPDATE list_items
                SET list_type = 'project_action', project_id = ?, project_name = ?,
                    planned_start_at = ?, planned_end_at = ?, estimated_hours = ?,
                    priority = 'P1', priority_score = ?, stage = '准备立项', status = 'todo', updated_at = ?
                WHERE id = ?
                """,
                (proj_id, project_name, planned_start_at, planned_end_at, estimated_hours, score, _now_str(), item_id),
            )
            self._recalculate_project_hours(conn, proj_id)
            return dict(conn.execute("SELECT * FROM list_items WHERE id = ?", (item_id,)).fetchone())

    def list_items(self, *, list_type: str | None = None, include_done: bool = True) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            sql = "SELECT * FROM list_items WHERE 1=1"
            params: list[Any] = []
            if list_type:
                sql += " AND list_type = ?"
                params.append(list_type)
            if not include_done:
                sql += " AND status != 'done'"
            sql += " ORDER BY CASE WHEN status='done' THEN 1 ELSE 0 END ASC, priority_score DESC, id ASC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC, id ASC").fetchall()
            return [dict(r) for r in rows]

    def list_memory_rules(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM memory_rules ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_daily_workload(
        self,
        start_date: str | None = None,
        days: int = 14,
        daily_capacity: float = 6.0,
    ) -> dict[str, Any]:
        """Calculate daily net effort hours booked without counting external wait days."""
        base = _parse_iso_date(start_date) or date.today()
        buckets: dict[str, dict[str, Any]] = {}
        for offset in range(days):
            d_str = (base + timedelta(days=offset)).isoformat()
            buckets[d_str] = {"date": d_str, "booked_hours": 0.0, "capacity": daily_capacity, "overloaded": False, "items": []}

        open_items = self.list_items(include_done=False)
        for item in open_items:
            if item["list_type"] == ListType.IDEA.value:
                continue
            target_day = _parse_iso_date(item["planned_start_at"]) or _parse_iso_date(item["planned_end_at"]) or base
            if target_day < base:
                target_day = base
            d_str = target_day.isoformat()
            if d_str in buckets:
                hrs = float(item["estimated_hours"] or 0.0)
                buckets[d_str]["booked_hours"] = round(buckets[d_str]["booked_hours"] + hrs, 2)
                buckets[d_str]["items"].append({"id": item["id"], "title": item["title"], "hours": hrs, "priority": item["priority"]})

        for day_data in buckets.values():
            day_data["overloaded"] = day_data["booked_hours"] > daily_capacity
            day_data["remaining_hours"] = round(max(0.0, daily_capacity - day_data["booked_hours"]), 2)

        return {"capacity_hours": daily_capacity, "days": buckets}

    def get_domain_analytics(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT work_domain,
                       COUNT(*) AS item_count,
                       SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count,
                       ROUND(COALESCE(SUM(estimated_hours), 0.0), 2) AS estimated_hours,
                       ROUND(COALESCE(SUM(COALESCE(actual_hours, 0.0)), 0.0), 2) AS actual_hours
                FROM list_items
                GROUP BY work_domain
                ORDER BY estimated_hours DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_timeline_for_project(self, project_name: str) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            proj = conn.execute("SELECT * FROM projects WHERE name LIKE ?", (f"%{project_name}%",)).fetchone()
            items = conn.execute(
                "SELECT * FROM list_items WHERE project_name LIKE ? ORDER BY planned_start_at ASC, id ASC",
                (f"%{project_name}%",),
            ).fetchall()
            sources = conn.execute(
                "SELECT id, source_type, title, onedrive_web_url, created_at FROM raw_sources "
                "WHERE title LIKE ? OR raw_text LIKE ? ORDER BY id DESC LIMIT 10",
                (f"%{project_name}%", f"%{project_name}%"),
            ).fetchall()
            return {
                "project": dict(proj) if proj else None,
                "items": [dict(r) for r in items],
                "sources": [dict(r) for r in sources],
            }

    def record_model_call(
        self,
        *,
        tier: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int,
        latency_ms: int,
        success: bool = True,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_calls (tier, model, prompt_tokens, completion_tokens, reasoning_tokens, latency_ms, success, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tier, model, prompt_tokens, completion_tokens, reasoning_tokens, latency_ms, 1 if success else 0, _now_str()),
            )

    def count_model_calls(self) -> int:
        with self._lock, self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0])

    def dashboard_overview(self, daily_capacity: float = 6.0) -> dict[str, Any]:
        items = self.list_items(include_done=True)
        projects = self.list_projects()
        workload = self.get_daily_workload(days=14, daily_capacity=daily_capacity)
        domains = self.get_domain_analytics()
        waiting = [i for i in items if i["list_type"] == ListType.WAITING_FOR.value and i["status"] != "done"]
        today = date.today()
        done_spans: list[int] = []
        for it in items:
            ps = _parse_iso_date(it.get("planned_start_at"))
            pe = _parse_iso_date(it.get("planned_end_at")) or ps
            it["planned_span_days"] = max(1, (pe - ps).days + 1) if (ps and pe) else 1
            if it.get("status") == "done":
                a_s = _parse_iso_date(it.get("actual_start_at")) or ps or _parse_iso_date(it.get("created_at")) or today
                a_e = _parse_iso_date(it.get("actual_end_at")) or today
                sp = max(1, (a_e - a_s).days + 1)
                it["actual_span_days"] = sp
                done_spans.append(sp)
            else:
                it["actual_span_days"] = None
        for w in waiting:
            start_d = _parse_iso_date(w.get("planned_start_at")) or _parse_iso_date(w.get("created_at")) or today
            w["waiting_days"] = max(0, (today - start_d).days)
        avg_span = round(sum(done_spans) / len(done_spans), 1) if done_spans else 0.0
        return {
            "today": today.isoformat(),
            "daily_capacity_hours": daily_capacity,
            "avg_completion_span_days": avg_span,
            "workload": workload,
            "domains": domains,
            "projects": projects,
            "items": items,
            "waiting_items": waiting,
            "model_calls_count": self.count_model_calls(),
        }
