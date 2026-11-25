"""Stage 0: Siggi Primary Corpus Ingestion, Macro Recon & Flagship Discovery Planner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.prompts import DISCOVERY_PLANNER_SYSTEM
from vf_ccus_workflow.schemas import DiscoveryPlan, EvidenceRecord, WorkflowState
from vf_ccus_workflow.tools.siggi_corpus_loader import load_siggi_corpus_hits

RECON_QUERIES: list[tuple[str, str, str]] = [
    ("CN", "webpage", "中国 CCUS 二氧化碳捕集 利用 封存 年度报告 百万吨 管道 齐鲁石化 大亚湾 2025 2026"),
    ("CN", "webpage", "中国 绿色甲醇 绿氢 二氧化碳合成 示范项目 产能规划 十五五 2025 2026"),
    ("CN", "webpage", "中国 液化二氧化碳 LCO2 运输船 江南造船 厦船重工 大连造船 出口 标准 2025 2026"),
    ("CN", "webpage", "中国 CCUS 二氧化碳 纯度 标准 在线质谱仪 FTIR 分析小屋 竞争格局 中石化 中海油"),
    ("CN", "scholar", "超临界二氧化碳管道 杂质 腐蚀 NOx SOx H2S 在线监测 质谱 气相色谱"),
    ("GLOBAL", "search", "China CCUS CCS projects pipeline green methanol LCO2 ship 2025 2026 CO2 purity"),
    ("GLOBAL", "search", "Northern Lights CO2 impurity specification IMR-MS V&F Thermo MAX-iR FTIR CCS comparison"),
]


def ingest_siggi_corpus(deps: RuntimeDeps) -> list[EvidenceRecord]:
    """Deterministically ingest primary V&F/Thermo/Shell-IFE files into EvidenceVault."""
    hits = load_siggi_corpus_hits(deps.settings.siggi_corpus_dir)
    records: list[EvidenceRecord] = []
    for hit in hits:
        rec = deps.vault.upsert_hit(track_id="SIGGI_BASE", hit=hit)
        if rec is not None:
            records.append(rec)
    deps.vault.log_query(
        track_id="SIGGI_BASE",
        engine="siggi_mcp",
        geo_scope="SIGGI",
        query=f"local_corpus:{deps.settings.siggi_corpus_dir.name}",
        hits_count=len(records),
    )
    return records


async def run_macro_recon(
    deps: RuntimeDeps, profile: str = "flagship"
) -> tuple[list[EvidenceRecord], list[str]]:
    """Run Stage 0 live China + Global macro search without hardcoded outcomes."""
    queries = RECON_QUERIES if profile == "flagship" else RECON_QUERIES[:4]
    num_res = 6 if profile == "flagship" else 3
    records: list[EvidenceRecord] = []
    q_log: list[str] = []

    for geo, mode, q in queries:
        hits = await deps.search_router.search_track(
            track_id="RECON",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            mode=mode,  # type: ignore[arg-type]
            num_results=num_res,
        )
        deps.vault.log_query(
            track_id="RECON",
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            hits_count=len(hits),
        )
        q_log.append(f"{geo}:{q[:50]}")
        for h in hits:
            rec = deps.vault.upsert_hit(track_id="RECON", hit=h)
            if rec is not None:
                records.append(rec)
    return records, q_log


def format_records_compact(records: list[EvidenceRecord], *, limit: int = 48) -> str:
    lines: list[str] = []
    for r in records[:limit]:
        body = (r.fulltext_excerpt or r.snippet).replace("\n", " ")[:480]
        lines.append(f"[{r.ev_id}] ({r.geo_scope}/{r.track_id}) {r.title}\nURL: {r.url}\nExcerpt: {body}")
    return "\n\n".join(lines)


async def node_siggi_ingest_and_planner(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 0: Ingest Siggi primary corpus, run live macro recon, and emit orthogonal DiscoveryPlan."""
    profile = state.get("profile", "flagship")
    siggi_records = ingest_siggi_corpus(deps)
    recon_records, q_log = await run_macro_recon(deps, profile=profile)

    siggi_ctx = format_records_compact(siggi_records, limit=32)
    recon_ctx = format_records_compact(recon_records, limit=32)

    user_prompt = (
        f"Contract: {deps.settings.contract.get('title')}\n"
        f"Contract ID: {deps.settings.contract.get('contract_id', 'VF-CCUS-CHINA-2026-V2')}\n"
        f"Profile: {profile}\n\n"
        f"=== SIGGI PRIMARY CORPUS ([EV-SIGGI-*]) ===\n{siggi_ctx}\n\n"
        f"=== LIVE CHINA & GLOBAL MACRO RECON ([EV-CN-*] / [EV-GL-*]) ===\n{recon_ctx}\n\n"
        "Generate a DiscoveryPlan with orthogonal `sector` tracks (covering S1 pipeline/EOR, S1 LCO2 ship/offshore, "
        "S2 green methanol/e-SAF, S3 amine capture/R&D, S4 food-grade negative control) PLUS 1 dedicated "
        "`competitive_ecosystem` track for competitors & Chinese GB/T 3836 PAC shelter integrators."
    )

    # Model-First principle: always use flagship brain for strategic planning; NEVER silently swallow failures
    plan = await deps.llm.complete_structured(
        tier="producer",
        node="discovery_planner",
        system_prompt=DISCOVERY_PLANNER_SYSTEM,
        user_prompt=user_prompt,
        schema=DiscoveryPlan,
        max_tokens=4000,
    )

    return {
        "siggi_records": [r.model_dump() for r in siggi_records],
        "recon_records": [r.model_dump() for r in recon_records],
        "discovery_plan": plan.model_dump(),
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "siggi_ingest_and_planner",
                "siggi_records": len(siggi_records),
                "recon_records": len(recon_records),
                "recon_queries": q_log,
                "emergent_tracks": len(plan.track_plans),
            }
        ],
    }
