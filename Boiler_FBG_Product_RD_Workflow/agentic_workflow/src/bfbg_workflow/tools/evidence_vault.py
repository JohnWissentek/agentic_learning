"""SQLite-backed EvidenceVault with BASE / CN / GLOBAL / PDF scoping & Zero-LLM Index Rendering."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bfbg_workflow.schemas import DatasheetAsset, EvidenceRecord, EvidenceSearchHit, GeoScope


class EvidenceVault:
    """Thread-safe local SQLite WAL registry assigning deterministic EV-BASE / EV-CN / EV-GL / EV-PDF IDs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidences (
                ev_id TEXT PRIMARY KEY,
                track_id TEXT NOT NULL,
                geo_scope TEXT NOT NULL,
                source_engine TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                snippet TEXT NOT NULL,
                fulltext_excerpt TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL UNIQUE,
                retrieved_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS datasheets (
                ev_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                vendor TEXT NOT NULL,
                part_number TEXT NOT NULL,
                subsystem TEXT NOT NULL,
                source_url TEXT NOT NULL,
                origin_type TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                key_specs_summary TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                engine TEXT NOT NULL,
                geo_scope TEXT NOT NULL,
                query TEXT NOT NULL,
                hits_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _prefix_for_scope(self, geo_scope: GeoScope) -> str:
        if geo_scope == "BASE":
            return "EV-BASE"
        if geo_scope == "CN":
            return "EV-CN"
        if geo_scope == "PDF":
            return "EV-PDF"
        return "EV-GL"

    def _next_ev_id(self, geo_scope: GeoScope) -> str:
        prefix = self._prefix_for_scope(geo_scope)
        rows = self._conn.execute(
            "SELECT ev_id FROM evidences WHERE ev_id LIKE ?", (f"{prefix}-%",)
        ).fetchall()
        max_num = 0
        for row in rows:
            m = re.search(rf"{re.escape(prefix)}-(\d+)$", str(row["ev_id"]))
            if m:
                max_num = max(max_num, int(m.group(1)))
        return f"{prefix}-{max_num + 1:04d}"

    def _row_to_record(self, row: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord(
            ev_id=row["ev_id"],
            track_id=row["track_id"],
            geo_scope=row["geo_scope"],
            source_engine=row["source_engine"],
            title=row["title"],
            url=row["url"],
            snippet=row["snippet"],
            fulltext_excerpt=row["fulltext_excerpt"],
            published_at=row["published_at"],
            content_hash=row["content_hash"],
            retrieved_at=row["retrieved_at"],
        )

    def upsert_hit(self, *, track_id: str, hit: EvidenceSearchHit) -> EvidenceRecord | None:
        url = (hit.url or "").strip()
        if not url:
            return None
        snippet = (hit.snippet or hit.content or "").strip()
        if not snippet:
            return None
        digest_src = f"{url}::{hit.title.strip()}" if url.startswith(("prior-corpus://", "local-pdf://")) else url
        c_hash = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:24]

        existing = self._conn.execute(
            "SELECT * FROM evidences WHERE content_hash = ? OR url = ?", (c_hash, url)
        ).fetchone()
        if existing is not None:
            if hit.content and len(hit.content) > len(existing["fulltext_excerpt"]):
                self._conn.execute(
                    "UPDATE evidences SET fulltext_excerpt = ? WHERE ev_id = ?",
                    (hit.content[:2800], existing["ev_id"]),
                )
                self._conn.commit()
                refreshed = self._conn.execute(
                    "SELECT * FROM evidences WHERE ev_id = ?", (existing["ev_id"],)
                ).fetchone()
                return self._row_to_record(refreshed)
            return self._row_to_record(existing)

        ev_id = self._next_ev_id(hit.geo_scope)
        now_iso = datetime.now(timezone.utc).isoformat()
        fulltext = (hit.content or snippet)[:2800]
        self._conn.execute(
            """
            INSERT INTO evidences (
                ev_id, track_id, geo_scope, source_engine, title, url, snippet,
                fulltext_excerpt, published_at, content_hash, retrieved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev_id,
                track_id,
                hit.geo_scope,
                hit.source_engine,
                (hit.title or "Untitled")[:260],
                url,
                snippet[:750],
                fulltext,
                (hit.published_at or "")[:80],
                c_hash,
                now_iso,
            ),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM evidences WHERE ev_id = ?", (ev_id,)).fetchone()
        return self._row_to_record(row)

    def upsert_datasheet(self, asset: DatasheetAsset) -> None:
        self._conn.execute(
            """
            INSERT INTO datasheets (
                ev_id, filename, vendor, part_number, subsystem, source_url,
                origin_type, page_count, file_size_bytes, sha256, key_specs_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                ev_id=excluded.ev_id,
                vendor=excluded.vendor,
                part_number=excluded.part_number,
                subsystem=excluded.subsystem,
                source_url=excluded.source_url,
                origin_type=excluded.origin_type,
                page_count=excluded.page_count,
                file_size_bytes=excluded.file_size_bytes,
                sha256=excluded.sha256,
                key_specs_summary=excluded.key_specs_summary
            """,
            (
                asset.ev_id,
                asset.filename,
                asset.vendor,
                asset.part_number,
                asset.subsystem,
                asset.source_url,
                asset.origin_type,
                asset.page_count,
                asset.file_size_bytes,
                asset.sha256,
                asset.key_specs_summary[:800],
            ),
        )
        self._conn.commit()

    def list_datasheets(self) -> list[DatasheetAsset]:
        rows = self._conn.execute("SELECT * FROM datasheets ORDER BY ev_id").fetchall()
        return [
            DatasheetAsset(
                ev_id=r["ev_id"],
                filename=r["filename"],
                vendor=r["vendor"],
                part_number=r["part_number"],
                subsystem=r["subsystem"],
                source_url=r["source_url"],
                origin_type=r["origin_type"],
                page_count=int(r["page_count"]),
                file_size_bytes=int(r["file_size_bytes"]),
                sha256=r["sha256"],
                key_specs_summary=r["key_specs_summary"],
            )
            for r in rows
        ]

    def log_query(
        self,
        *,
        track_id: str,
        engine: str,
        geo_scope: GeoScope,
        query: str,
        hits_count: int,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO query_log (track_id, engine, geo_scope, query, hits_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (track_id, engine, geo_scope, query, hits_count, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def list_all(self, *, geo_scope: GeoScope | None = None, track_id: str | None = None) -> list[EvidenceRecord]:
        sql = "SELECT * FROM evidences WHERE 1=1"
        params: list[Any] = []
        if geo_scope:
            sql += " AND geo_scope = ?"
            params.append(geo_scope)
        if track_id:
            sql += " AND track_id = ?"
            params.append(track_id)
        sql += " ORDER BY ev_id"
        return [self._row_to_record(r) for r in self._conn.execute(sql, params).fetchall()]

    def all_ev_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT ev_id FROM evidences").fetchall()
        return {str(r["ev_id"]) for r in rows}

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT geo_scope, COUNT(*) AS cnt FROM evidences GROUP BY geo_scope"
        ).fetchall()
        counts = {"BASE": 0, "CN": 0, "GLOBAL": 0, "PDF": 0}
        for r in rows:
            counts[str(r["geo_scope"])] = int(r["cnt"])
        counts["TOTAL"] = sum(counts.values())
        ds_cnt = self._conn.execute("SELECT COUNT(*) AS cnt FROM datasheets").fetchone()
        counts["VERIFIED_DATASHEETS"] = int(ds_cnt["cnt"]) if ds_cnt else 0
        return counts


def format_records_compact(records: list[EvidenceRecord], *, limit: int = 30) -> str:
    """Format vault records concisely for LLM context injection without leaking URLs."""
    lines: list[str] = []
    for rec in records[:limit]:
        excerpt = (rec.fulltext_excerpt or rec.snippet).replace("\n", " ").strip()[:320]
        lines.append(f"[{rec.ev_id}] ({rec.geo_scope}/{rec.track_id}) {rec.title} | {excerpt}")
    return "\n".join(lines)


def deterministic_contract_checks(
    *,
    vault: EvidenceVault,
    volumes: dict[str, str],
    output_dir: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Ch 19 programmatic checks: valid EV IDs, zero broken PDF links, volume presence."""
    valid_ids = vault.all_ev_ids()
    cited_ids: set[str] = set()
    invalid_citations: dict[str, list[str]] = {}
    broken_pdf_links: dict[str, list[str]] = {}

    for fname, md in volumes.items():
        found = set(re.findall(r"\[(EV-(?:BASE|CN|GL|PDF)-\d{4})\]", md))
        cited_ids.update(found)
        bad = sorted(c for c in found if c not in valid_ids)
        if bad:
            invalid_citations[fname] = bad

        pdf_refs = set(re.findall(r"datasheets_pdf/([A-Za-z0-9._-]+\.pdf)", md))
        missing_pdfs = sorted(p for p in pdf_refs if not (output_dir / "datasheets_pdf" / p).exists())
        if missing_pdfs:
            broken_pdf_links[fname] = missing_pdfs

    required_vols = contract.get("required_output_volumes", [])
    missing_vols = [v for v in required_vols if not volumes.get(v, "").strip()]
    stats = vault.stats()
    gates = contract.get("evidence_and_pdf_gates", {})

    return {
        "vault_stats": stats,
        "cited_evidence_count": len(cited_ids),
        "invalid_citations": invalid_citations,
        "invalid_citations_count": sum(len(v) for v in invalid_citations.values()),
        "broken_pdf_links": broken_pdf_links,
        "broken_pdf_links_count": sum(len(v) for v in broken_pdf_links.values()),
        "missing_required_volumes": missing_vols,
        "meets_min_evidence_gate": stats["TOTAL"] >= int(gates.get("min_total_evidence_records", 60)),
        "meets_min_pdf_gate": stats["VERIFIED_DATASHEETS"] >= int(gates.get("min_verified_pdf_datasheets", 14)),
    }


def render_evidence_and_datasheet_index(vault: EvidenceVault) -> str:
    """Zero-LLM deterministic generator for 07_VERIFIED_EVIDENCE_AND_DATASHEET_INDEX.md."""
    datasheets = vault.list_datasheets()
    all_recs = vault.list_all()
    stats = vault.stats()

    parts: list[str] = [
        "# 07_VERIFIED_EVIDENCE_AND_DATASHEET_INDEX — 全量可追溯证据库与原厂 PDF 规格书台账",
        "",
        "> 本文档由 Python `EvidenceVault` (`Zero-LLM`) 确定性导出，任何正文引用的 `[EV-BASE-*]`、`[EV-CN-*]`、`[EV-GL-*]`、`[EV-PDF-*]` 编号及 `./datasheets_pdf/*.pdf` 链接均受程序化校验与 SHA-256 指纹审计。",
        "",
        "## 1. 证据库覆盖统计",
        "",
        f"- **总核验证据条数**: `{stats['TOTAL']}` 条",
        f"- **本地历史研究参考 (`EV-BASE`)**: `{stats['BASE']}` 条",
        f"- **中国市场与电力政策/竞品检索 (`EV-CN`)**: `{stats['CN']}` 条",
        f"- **全球光电硬件与国际竞品检索 (`EV-GL`)**: `{stats['GLOBAL']}` 条",
        f"- **原厂 PDF 规格书解析条目 (`EV-PDF`)**: `{stats['PDF']}` 条",
        f"- **已验真落盘的原厂 PDF 物理文件**: `{stats['VERIFIED_DATASHEETS']}` 份（位于 [`./datasheets_pdf/`](./datasheets_pdf/)）",
        "",
        "## 2. 已验真原厂 PDF 规格书物理台账 (`./datasheets_pdf/`)",
        "",
        "| 证据 ID | 所属子系统 | 原厂品牌 | 器件/设备型号 | 来源分类 | 页数 / 大小 | SHA-256 (前12位) | 物理文件链接 |",
        "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |",
    ]
    for ds in datasheets:
        size_kb = ds.file_size_bytes / 1024.0
        parts.append(
            f"| `{ds.ev_id}` | {ds.subsystem} | {ds.vendor} | `{ds.part_number}` | "
            f"{ds.origin_type} | {ds.page_count}p / {size_kb:.0f} KB | `{ds.sha256[:12]}` | "
            f"[{ds.filename}](./datasheets_pdf/{ds.filename}) |"
        )

    parts.extend(
        [
            "",
            "## 3. 全量可追溯证据索引 (`[EV-*]`)",
            "",
            "| 证据 ID | 范围 | 赛道 | 来源引擎 | 标题 | 链接 / URI |",
            "| :--- | :---: | :--- | :---: | :--- | :--- |",
        ]
    )
    for r in all_recs:
        safe_title = r.title.replace("|", "\\|").replace("\n", " ")[:95]
        safe_url = r.url.replace("|", "%7C")
        parts.append(
            f"| `{r.ev_id}` | `{r.geo_scope}` | `{r.track_id}` | `{r.source_engine}` | {safe_title} | {safe_url} |"
        )

    parts.append("")
    return "\n".join(parts)
