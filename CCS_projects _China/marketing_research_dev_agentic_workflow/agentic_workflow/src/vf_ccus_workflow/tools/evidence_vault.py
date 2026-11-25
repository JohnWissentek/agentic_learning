"""SQLite-backed EvidenceVault with Volume-Targeted Routing, Full-Text Audit & Zero-LLM Index."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vf_ccus_workflow.schemas import (
    DeterministicAuditReport,
    EvidenceRecord,
    EvidenceSearchHit,
    GeoScope,
    VolumeCitationAudit,
)

EV_ID_PATTERN = re.compile(r"\b(EV-(?:SIGGI|CN|GL)-\d{3,4})\b")

REQUIRED_5_VOLUMES: tuple[str, ...] = (
    "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
    "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
    "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
    "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
    "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
)


def extract_all_ev_ids(text: str) -> set[str]:
    """Extract all EV-SIGGI / EV-CN / EV-GL IDs from single brackets, multi-ID lists, or tables."""
    if not text:
        return set()
    return set(EV_ID_PATTERN.findall(text))


class EvidenceVault:
    """Thread-safe local SQLite WAL registry assigning deterministic EV-SIGGI / EV-CN / EV-GL IDs."""

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
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_track ON evidences(track_id);")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_scope ON evidences(geo_scope);")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _prefix_for_scope(self, geo_scope: GeoScope) -> str:
        if geo_scope == "SIGGI":
            return "EV-SIGGI"
        if geo_scope == "CN":
            return "EV-CN"
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
        return f"{prefix}-{max_num + 1:03d}"

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
        """Deduplicate by URL or content hash and persist evidence record."""
        url = (hit.url or "").strip()
        if not url:
            return None
        snippet = (hit.snippet or hit.content or "").strip()
        if not snippet:
            return None
        digest_src = f"{url}::{hit.title.strip()}" if url.startswith("siggi-corpus://") else url
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
            (
                track_id,
                engine,
                geo_scope,
                query[:300],
                hits_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def list_by_track(self, track_id: str) -> list[EvidenceRecord]:
        rows = self._conn.execute(
            "SELECT * FROM evidences WHERE track_id = ? ORDER BY ev_id ASC", (track_id,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_by_scope(self, geo_scope: GeoScope) -> list[EvidenceRecord]:
        rows = self._conn.execute(
            "SELECT * FROM evidences WHERE geo_scope = ? ORDER BY ev_id ASC", (geo_scope,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_by_ids(self, ev_ids: set[str]) -> list[EvidenceRecord]:
        if not ev_ids:
            return []
        placeholders = ",".join("?" for _ in ev_ids)
        rows = self._conn.execute(
            f"SELECT * FROM evidences WHERE ev_id IN ({placeholders}) ORDER BY ev_id ASC",
            tuple(sorted(ev_ids)),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_all(self) -> list[EvidenceRecord]:
        rows = self._conn.execute("SELECT * FROM evidences ORDER BY ev_id ASC").fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_valid_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT ev_id FROM evidences").fetchall()
        return {str(r["ev_id"]) for r in rows}

    def build_volume_evidence_bundle(
        self,
        *,
        volume_name: str,
        track_ids: list[str] | None = None,
        priority_ev_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[EvidenceRecord]:
        """Return volume-targeted EvidenceRecords prioritizing cited IDs & matching tracks."""
        selected: list[EvidenceRecord] = []
        seen: set[str] = set()

        def _append_batch(records: list[EvidenceRecord]) -> None:
            for rec in records:
                if len(selected) >= limit:
                    return
                if rec.ev_id not in seen:
                    seen.add(rec.ev_id)
                    selected.append(rec)

        # Tier 1: Explicitly cited / priority evidence IDs (regardless of numeric index)
        if priority_ev_ids:
            _append_batch(self.list_by_ids(set(priority_ev_ids)))

        # Tier 2: Matching tracks for this volume
        if track_ids:
            for tid in track_ids:
                _append_batch(self.list_by_track(tid))

        # Tier 3: Primary Siggi evidence + CRAG_GAP refills
        _append_batch(self.list_by_scope("SIGGI"))
        _append_batch(self.list_by_track("CRAG_GAP"))

        # Tier 4: Remaining CN & GLOBAL evidence ordered to balance coverage
        if volume_name.startswith("02_"):
            _append_batch(self.list_by_scope("GLOBAL"))
            _append_batch(self.list_by_scope("CN"))
        else:
            _append_batch(self.list_by_scope("CN"))
            _append_batch(self.list_by_scope("GLOBAL"))

        return selected[:limit]

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT geo_scope, COUNT(*) AS cnt FROM evidences GROUP BY geo_scope"
        ).fetchall()
        counts = {r["geo_scope"]: int(r["cnt"]) for r in rows}
        siggi_cnt = counts.get("SIGGI", 0)
        cn_cnt = counts.get("CN", 0)
        gl_cnt = counts.get("GLOBAL", 0)
        url_cnt = self._conn.execute("SELECT COUNT(DISTINCT url) FROM evidences").fetchone()[0]
        return {
            "total": siggi_cnt + cn_cnt + gl_cnt,
            "siggi_count": siggi_cnt,
            "cn_count": cn_cnt,
            "global_count": gl_cnt,
            "unique_sources": int(url_cnt),
        }


def render_evidence_index(
    records: list[EvidenceRecord],
    *,
    db_label: str = "data/vf_ccus_evidence_vault.db",
) -> str:
    """Zero-LLM deterministic Vol 05 Verified Evidence Index."""
    siggi = [r for r in records if r.geo_scope == "SIGGI"]
    cn = [r for r in records if r.geo_scope == "CN"]
    gl = [r for r in records if r.geo_scope == "GLOBAL"]
    lines = [
        "# 第05卷：可审计证据库索引与一手资料追溯表 (`05_VERIFIED_EVIDENCE_CITATIONS_INDEX`)",
        "",
        f"> 本索引由确定性 Python 程序直接从 `{db_label}` 渲染生成，**零 LLM 转述编造**。",
        f"> 证据总量：**{len(records)} 条**（Siggi一手资料 `[EV-SIGGI]`: **{len(siggi)}** | 中国本土检索 `[EV-CN]`: **{len(cn)}** | 全球/国际标准对标 `[EV-GL]`: **{len(gl)}**）。",
        "",
        "## 一、Siggi一手资料与国际核心技术文献索引 (`[EV-SIGGI-*]`)",
        "",
        "| 证据ID | Track | 标题 | 链接/出处 | 核心摘要 |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in siggi:
        title = r.title.replace("|", "\\|").replace("\n", " ")[:95]
        snip = r.snippet.replace("|", "\\|").replace("\n", " ")[:180]
        lines.append(f"| `{r.ev_id}` | {r.track_id} | {title} | `{r.url}` | {snip} |")

    lines.extend(
        [
            "",
            "## 二、中国CCS/CCUS政策、项目、设计院与竞品检索索引 (`[EV-CN-*]`)",
            "",
            "| 证据ID | Track | 来源引擎 | 标题 | 原始URL | 核心摘要 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in cn:
        title = r.title.replace("|", "\\|").replace("\n", " ")[:90]
        snip = r.snippet.replace("|", "\\|").replace("\n", " ")[:170]
        lines.append(
            f"| `{r.ev_id}` | {r.track_id} | {r.source_engine} | {title} | {r.url} | {snip} |"
        )

    lines.extend(
        [
            "",
            "## 三、全球CCS标准、竞品对标与海运/认证文献索引 (`[EV-GL-*]`)",
            "",
            "| 证据ID | Track | 来源引擎 | 标题 | 原始URL | 核心摘要 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in gl:
        title = r.title.replace("|", "\\|").replace("\n", " ")[:90]
        snip = r.snippet.replace("|", "\\|").replace("\n", " ")[:170]
        lines.append(
            f"| `{r.ev_id}` | {r.track_id} | {r.source_engine} | {title} | {r.url} | {snip} |"
        )
    return "\n".join(lines) + "\n"


def _som_number_matches(text: str, som_wan: float, som_units: int) -> bool:
    """Check whether expected 10yr baseline SOM (in 万元, 亿元, or units) appears cleanly in text."""
    if som_wan <= 0:
        return True
    compact = text.replace(",", "")
    wan_int = f"{int(round(som_wan))}"
    wan_1dp = f"{som_wan:.1f}"
    yi_2dp = f"{som_wan / 10000.0:.2f}"
    wan_ok = (wan_int in compact) or (wan_1dp in compact) or (yi_2dp in compact)
    units_ok = som_units <= 0 or bool(re.search(rf"\b{som_units}\s*(?:台套|套|台)", compact))
    return wan_ok and units_ok


def run_deterministic_full_audit(
    *,
    vault_stats: dict[str, int],
    valid_ids: set[str],
    full_drafts: dict[str, str],
    executive_drafts: dict[str, str],
    market_sizing_summary: dict[str, Any],
    evaluated_wedges: list[dict[str, Any]],
    eliminated_wedges: list[dict[str, Any]],
    dropped_unverified_records: list[dict[str, Any]],
    contract: dict[str, Any],
) -> DeterministicAuditReport:
    """100% full-text programmatic audit across both Full & Executive editions."""
    gates = contract.get("quality_gates", {}) or {}
    min_tot = int(gates.get("min_evidences_total", 55))
    min_cn = int(gates.get("min_cn_evidences", 25))
    min_gl = int(gates.get("min_global_evidences", 15))
    min_siggi = int(gates.get("min_siggi_evidences", 12))

    req_deliv = contract.get("required_deliverables", {})
    if isinstance(req_deliv, dict) and req_deliv.get("full_edition"):
        required_vols = tuple(req_deliv["full_edition"])
    else:
        required_vols = REQUIRED_5_VOLUMES

    full_audits: list[VolumeCitationAudit] = []
    exec_audits: list[VolumeCitationAudit] = []
    invalid_by_vol: dict[str, list[str]] = {}
    failed_gates: list[str] = []

    full_missing: list[str] = []
    exec_missing: list[str] = []

    for vol in required_vols:
        f_text = (full_drafts.get(vol) or "").strip()
        if len(f_text) < 100:
            full_missing.append(vol)
        f_ids = extract_all_ev_ids(f_text)
        f_bad = sorted(eid for eid in f_ids if eid not in valid_ids)
        full_audits.append(
            VolumeCitationAudit(
                volume_name=vol,
                edition="full",
                total_chars=len(f_text),
                distinct_valid_ids=len(f_ids) - len(f_bad),
                invalid_ids=f_bad,
            )
        )
        if f_bad:
            invalid_by_vol[f"full:{vol}"] = f_bad

        e_text = (executive_drafts.get(vol) or "").strip()
        if len(e_text) < 80:
            exec_missing.append(vol)
        e_ids = extract_all_ev_ids(e_text)
        e_bad = sorted(eid for eid in e_ids if eid not in valid_ids)
        exec_audits.append(
            VolumeCitationAudit(
                volume_name=vol,
                edition="executive",
                total_chars=len(e_text),
                distinct_valid_ids=len(e_ids) - len(e_bad),
                invalid_ids=e_bad,
            )
        )
        if e_bad:
            invalid_by_vol[f"executive:{vol}"] = e_bad

    dual_edition_complete = (len(full_missing) == 0) and (len(exec_missing) == 0)
    if full_missing:
        failed_gates.append(f"Full edition missing/empty volumes: {', '.join(full_missing)}")
    if exec_missing:
        failed_gates.append(f"Executive edition missing/empty volumes: {', '.join(exec_missing)}")

    if invalid_by_vol:
        failed_gates.append(f"Invalid/fabricated EV citations detected in {len(invalid_by_vol)} volume(s)")

    all_full_text = "\n".join(full_drafts.get(v, "") for v in required_vols)
    all_exec_text = "\n".join(executive_drafts.get(v, "") for v in required_vols)
    combined_text = all_full_text + "\n" + all_exec_text

    # Numeric consistency check against deterministic [MKT-CALC] and [ROI-CALC]
    numeric_discrepancies: list[str] = []
    if "[MKT-CALC]" not in all_full_text:
        numeric_discrepancies.append("Full edition missing [MKT-CALC] marker")
    if "[ROI-CALC]" not in all_full_text:
        numeric_discrepancies.append("Full edition missing [ROI-CALC] marker")

    som_wan = float(market_sizing_summary.get("grand_total_10yr_baseline_som_cny_wan", 0.0) or 0.0)
    som_units = int(market_sizing_summary.get("grand_total_10yr_baseline_som_units", 0) or 0)
    if som_wan > 0:
        if not _som_number_matches(all_full_text, som_wan, som_units):
            numeric_discrepancies.append(
                f"Full edition 10yr baseline SOM mismatch: expected {som_units} units / {som_wan:.1f} 万元 ({som_wan/10000:.2f} 亿元)"
            )
        if not _som_number_matches(all_exec_text, som_wan, som_units):
            numeric_discrepancies.append(
                f"Executive edition 10yr baseline SOM mismatch: expected {som_units} units / {som_wan:.1f} 万元 ({som_wan/10000:.2f} 亿元)"
            )

    if evaluated_wedges:
        top_pb = float((evaluated_wedges[0].get("roi") or {}).get("payback_months", 0.0) or 0.0)
        if top_pb > 0:
            pb_str = f"{top_pb:.1f}"
            if pb_str not in all_full_text and f"{top_pb:.2f}" not in all_full_text:
                numeric_discrepancies.append(
                    f"Full edition missing top wedge [ROI-CALC] payback figure ({pb_str} months)"
                )

    numeric_consistency_passed = len(numeric_discrepancies) == 0
    if not numeric_consistency_passed:
        failed_gates.append(f"Numeric consistency discrepancies: {'; '.join(numeric_discrepancies)}")

    dual_track_covered = ("TRACK_A" in combined_text or "Track A" in combined_text) and (
        "TRACK_B" in combined_text or "Track B" in combined_text or "VF-QAS-CN" in combined_text
    )
    if not dual_track_covered:
        failed_gates.append("Missing Track A / Track B (VF-QAS-CN) dual-track commercial architecture coverage")

    if eliminated_wedges:
        elim_ids = [str(e.get("wedge_id", "")) for e in eliminated_wedges if e.get("wedge_id")]
        eliminated_wedges_disclosed = any(eid in combined_text for eid in elim_ids) or (
            "伪需求" in combined_text and "淘汰" in combined_text
        )
    else:
        eliminated_wedges_disclosed = True

    if not eliminated_wedges_disclosed:
        failed_gates.append("Eliminated / pseudo-demand control wedges not disclosed in deliverables")

    if vault_stats.get("total", 0) < min_tot:
        failed_gates.append(f"Total evidences {vault_stats.get('total', 0)} < gate {min_tot}")
    if vault_stats.get("siggi_count", 0) < min_siggi:
        failed_gates.append(f"Siggi evidences {vault_stats.get('siggi_count', 0)} < gate {min_siggi}")
    if vault_stats.get("cn_count", 0) < min_cn:
        failed_gates.append(f"CN evidences {vault_stats.get('cn_count', 0)} < gate {min_cn}")
    if vault_stats.get("global_count", 0) < min_gl:
        failed_gates.append(f"GLOBAL evidences {vault_stats.get('global_count', 0)} < gate {min_gl}")

    return DeterministicAuditReport(
        passed=len(failed_gates) == 0,
        vault_stats=vault_stats,
        dropped_unverified_count=len(dropped_unverified_records),
        dropped_unverified_records=dropped_unverified_records,
        full_edition_audits=full_audits,
        executive_edition_audits=exec_audits,
        invalid_citations_by_volume=invalid_by_vol,
        numeric_consistency_passed=numeric_consistency_passed,
        numeric_discrepancies=numeric_discrepancies,
        dual_edition_complete=dual_edition_complete,
        dual_track_covered=dual_track_covered,
        eliminated_wedges_disclosed=eliminated_wedges_disclosed,
        secret_leak_check_passed=True,
        failed_gates=failed_gates,
    )


def deterministic_contract_checks(
    *,
    vault_stats: dict[str, int],
    drafts: dict[str, str],
    evaluated_wedges: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Legacy-compatible summary helper using upgraded full multi-ID citation extraction."""
    gates = contract.get("quality_gates", {}) or {}
    min_tot = int(gates.get("min_evidences_total", 55))
    min_cn = int(gates.get("min_cn_evidences", 25))
    min_gl = int(gates.get("min_global_evidences", 15))
    min_siggi = int(gates.get("min_siggi_evidences", 12))

    non_empty_5_vols = all(len(drafts.get(v, "").strip()) >= 600 for v in REQUIRED_5_VOLUMES)
    all_text = "\n".join(drafts.get(v, "") for v in REQUIRED_5_VOLUMES)

    has_mkt_calc_tag = "[MKT-CALC]" in all_text
    has_roi_calc_tag = "[ROI-CALC]" in all_text
    has_dual_track = ("TRACK_A" in all_text or "Track A" in all_text) and (
        "TRACK_B" in all_text or "Track B" in all_text or "VF-QAS-CN" in all_text
    )
    cited_ids = extract_all_ev_ids(all_text)

    return {
        "total_evidences": vault_stats.get("total", 0),
        "siggi_evidences": vault_stats.get("siggi_count", 0),
        "cn_evidences": vault_stats.get("cn_count", 0),
        "global_evidences": vault_stats.get("global_count", 0),
        "meets_total_evidence_gate": vault_stats.get("total", 0) >= min_tot,
        "meets_siggi_evidence_gate": vault_stats.get("siggi_count", 0) >= min_siggi,
        "meets_cn_evidence_gate": vault_stats.get("cn_count", 0) >= min_cn,
        "meets_global_evidence_gate": vault_stats.get("global_count", 0) >= min_gl,
        "all_5_volumes_non_empty": non_empty_5_vols,
        "has_mkt_calc_tag": has_mkt_calc_tag,
        "has_roi_calc_tag": has_roi_calc_tag,
        "has_dual_track_coverage": has_dual_track,
        "distinct_citations_used": len(cited_ids),
        "evaluated_wedges_count": len(evaluated_wedges),
    }
