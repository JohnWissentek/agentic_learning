"""Stage 0a & 0b: Baseline Corpus Ingestion, Macro Recon & Chief PM Step-Back Planner."""

from __future__ import annotations

import asyncio
from typing import Any

from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import CHIEF_PM_SYSTEM
from bfbg_workflow.schemas import EvidenceRecord, ProductDiscoveryPlan, WorkflowState
from bfbg_workflow.tools.evidence_vault import format_records_compact
from bfbg_workflow.tools.prior_corpus_loader import ingest_prior_research_corpus

RECON_QUERIES: list[tuple[str, str]] = [
    ("CN", "中国 燃煤电厂 锅炉 水冷壁 温度监测 光纤光栅 三改联动 深度调峰"),
    ("CN", "电站锅炉 水冷壁 防爆管 壁温监测 市场规模 招投标 价格"),
    ("GLOBAL", "power plant boiler waterwall tube temperature FBG fiber optic sensing"),
    ("GLOBAL", "femtosecond fiber bragg grating high temperature interrogator Ibsen Santec FBGS"),
]


async def run_macro_recon(deps: RuntimeDeps, *, profile: str) -> tuple[list[EvidenceRecord], list[dict[str, Any]]]:
    """Run initial CN + GLOBAL market and technology reconnaissance queries."""
    queries = RECON_QUERIES if profile == "flagship" else RECON_QUERIES[:2]

    async def _one(geo: str, q: str) -> tuple[dict[str, Any], list[EvidenceRecord]]:
        async with deps.semaphore:
            hits = await deps.search_router.search_track(
                track_id="RECON", geo_scope=geo, query=q, num_results=6  # type: ignore[arg-type]
            )
            deps.vault.log_query(
                track_id="RECON",
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,  # type: ignore[arg-type]
                query=q,
                hits_count=len(hits),
            )
            recs: list[EvidenceRecord] = []
            for h in hits:
                r = deps.vault.upsert_hit(track_id="RECON", hit=h)
                if r:
                    recs.append(r)
            return {"geo_scope": geo, "query": q, "hits": len(hits)}, recs

    batches = await asyncio.gather(*(_one(g, q) for g, q in queries))
    q_log: list[dict[str, Any]] = []
    all_recs: list[EvidenceRecord] = []
    for log_item, recs in batches:
        q_log.append(log_item)
        all_recs.extend(recs)
    return all_recs, q_log


async def node_ingest_and_planner(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 0a/0b LangGraph node: ingest prior docs, run recon, invoke Chief PM planner."""
    profile = state.get("profile", "flagship")
    prior_recs = ingest_prior_research_corpus(deps.settings.prior_research_dir, deps.vault)
    recon_recs, _ = await run_macro_recon(deps, profile=profile)

    prior_ctx = format_records_compact(prior_recs, limit=20)
    recon_ctx = format_records_compact(recon_recs, limit=20)

    user_prompt = (
        f"Profile={profile}\n"
        f"Contract={deps.settings.contract.get('contract_id')}\n"
        "Product Lines: BS-STD-600 (300-600 pts) & BS-PRO-2000 (1000-2000+ pts)\n"
        "Strategy: 100% imported/off-the-shelf core optical & DAQ hardware integration + self-developed software/demod + Phase-1 read-only bypass Boiler AI + dual-track sensor BOM (Track A full imported vs Track B hybrid high-value).\n\n"
        f"=== PRIOR BASELINE CORPUS [EV-BASE-*] ===\n{prior_ctx}\n\n"
        f"=== LIVE MACRO RECON ===\n{recon_ctx}\n\n"
        "Produce exactly 6 TrackPlanItem entries covering: "
        "T1_MARKET_POLICY, T2_COMPETITIVE_INTEL, T3_OPTICS_HARDWARE, T4_FIBER_BOILER_PACKAGING, T5_SOFTWARE_BOILER_AI, T6_NPI_QAQC_FINANCE."
    )
    plan = await deps.llm.complete_json(
        tier="producer",
        node="stage0_chief_pm_planner",
        system_prompt=CHIEF_PM_SYSTEM,
        user_prompt=user_prompt,
        schema=ProductDiscoveryPlan,
        max_tokens=4096,
    )
    return {
        "recon_summary": plan.step_back_thesis,
        "discovery_plan": plan.model_dump(),
    }
