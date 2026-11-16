"""Read-only ingestion of prior Boiler_FBG_Thermometry_Research markdown corpus into EV-BASE-*."""

from __future__ import annotations

import re
from pathlib import Path

from bfbg_workflow.schemas import EvidenceRecord, EvidenceSearchHit
from bfbg_workflow.tools.evidence_vault import EvidenceVault


def ingest_prior_research_corpus(prior_dir: Path, vault: EvidenceVault) -> list[EvidenceRecord]:
    """Read Boiler_FBG_Thermometry_Research/*.md strictly read-only and extract section summaries."""
    records: list[EvidenceRecord] = []
    if not prior_dir.exists():
        return records

    md_files = sorted(prior_dir.rglob("*.md"))
    for md_path in md_files:
        rel = md_path.relative_to(prior_dir).as_posix()
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0].lstrip("#").strip() if lines[0].startswith("#") else md_path.stem
        headings = [re.sub(r"^#+\s*", "", ln) for ln in lines if ln.startswith("##")][:6]
        body_excerpt = " ".join(
            ln for ln in lines if not ln.startswith("#") and not ln.startswith("```")
        )[:700]
        snippet = (
            f"[历史基线参考，非最终设计约束] 章节覆盖: {', '.join(headings)} | 摘要: {body_excerpt[:350]}"
        )
        rec = vault.upsert_hit(
            track_id="PRIOR_CORPUS",
            hit=EvidenceSearchHit(
                title=f"PriorResearch: {title}",
                url=f"prior-corpus://{rel}",
                snippet=snippet,
                content=f"Source: {rel}\nHeadings: {'; '.join(headings)}\n\n{body_excerpt}",
                source_engine="prior_corpus",
                geo_scope="BASE",
                published_at="2026-11-09",
                score=0.85,
            ),
        )
        if rec:
            records.append(rec)
    return records
