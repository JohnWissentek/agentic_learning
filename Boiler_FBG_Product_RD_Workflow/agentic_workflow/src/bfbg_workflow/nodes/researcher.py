"""Stage 1: 6-Role Parallel Deep Research & OEM PDF Datasheet Acquisition."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import SPECIALIST_SYSTEM
from bfbg_workflow.schemas import (
    DatasheetAsset,
    EvidenceRecord,
    ProductDiscoveryPlan,
    TrackPlanItem,
    TrackResearchDossier,
    WorkflowState,
)
from bfbg_workflow.tools.datasheet_fetcher import sync_and_fetch_datasheets
from bfbg_workflow.tools.evidence_vault import format_records_compact


async def execute_track_queries(
    deps: RuntimeDeps,
    track: TrackPlanItem,
    *,
    profile: str,
) -> list[EvidenceRecord]:
    """Execute Metaso (CN) + Serper (GLOBAL/PDF) queries for one specialist track."""
    limit_per_scope = 3 if profile == "flagship" else 2
    tasks: list[tuple[str, str]] = []
    for q in track.cn_queries[:limit_per_scope]:
        tasks.append(("CN", q))
    for q in track.global_queries[:limit_per_scope]:
        tasks.append(("GLOBAL", q))

    async def _run_q(geo: str, query: str) -> list[EvidenceRecord]:
        async with deps.semaphore:
            hits = await deps.search_router.search_track(
                track_id=track.track_id,
                geo_scope=geo,  # type: ignore[arg-type]
                query=query,
                num_results=6 if profile == "flagship" else 4,
            )
            if hits and profile == "flagship":
                hits = await deps.search_router.enrich_top_hits(hits, max_fetch=1)
            deps.vault.log_query(
                track_id=track.track_id,
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,  # type: ignore[arg-type]
                query=query,
                hits_count=len(hits),
            )
            recs: list[EvidenceRecord] = []
            for h in hits:
                rec = deps.vault.upsert_hit(track_id=track.track_id, hit=h)
                if rec:
                    recs.append(rec)
            return recs

    batches = await asyncio.gather(*(_run_q(g, q) for g, q in tasks))
    out: list[EvidenceRecord] = []
    for b in batches:
        out.extend(b)
    return out


async def execute_all_tracks_and_pdfs(
    deps: RuntimeDeps,
    plan: ProductDiscoveryPlan,
    *,
    output_dir: Path,
    profile: str,
    skip_online_pdf: bool = False,
) -> tuple[dict[str, list[EvidenceRecord]], list[DatasheetAsset]]:
    """Run all 6 research tracks concurrently and acquire/verify OEM PDF datasheets."""
    prior_pdf_dir = deps.settings.prior_research_dir / "06_300Pts_System_Design_and_Datasheets" / "Datasheets_PDF"
    target_pdf_dir = output_dir / "datasheets_pdf"

    track_coros = [execute_track_queries(deps, tp, profile=profile) for tp in plan.track_plans]
    pdf_coro = sync_and_fetch_datasheets(
        prior_datasheets_dir=prior_pdf_dir,
        target_datasheets_dir=target_pdf_dir,
        vault=deps.vault,
        search_router=deps.search_router,
        max_size_mb=float(deps.settings.contract.get("evidence_and_pdf_gates", {}).get("max_pdf_size_mb", 9.5)),
        skip_online_download=skip_online_pdf,
    )
    results = await asyncio.gather(*track_coros, pdf_coro)
    track_map: dict[str, list[EvidenceRecord]] = {}
    for tp, recs in zip(plan.track_plans, results[:-1]):
        track_map[tp.track_id] = recs
    assets: list[DatasheetAsset] = results[-1]  # type: ignore[assignment]
    return track_map, assets


async def node_parallel_track_researcher(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 1 LangGraph node: search + PDF fetch + 6 parallel specialist mining agents."""
    profile = state.get("profile", "flagship")
    raw_out = state.get("output_dir", str(deps.settings.default_output_dir))
    out_dir = Path(raw_out) if Path(raw_out).is_absolute() else (deps.settings.root_dir / raw_out).resolve()
    plan = ProductDiscoveryPlan.model_validate(state["discovery_plan"])

    track_map, assets = await execute_all_tracks_and_pdfs(
        deps, plan, output_dir=out_dir, profile=profile
    )
    base_recs = deps.vault.list_all(geo_scope="BASE")
    pdf_recs = deps.vault.list_all(geo_scope="PDF")

    base_ctx = format_records_compact(base_recs, limit=18)
    pdf_ctx = format_records_compact(pdf_recs, limit=25)

    async def _mine_one(tp: TrackPlanItem) -> dict[str, Any]:
        t_recs = track_map.get(tp.track_id, [])
        t_ctx = format_records_compact(t_recs, limit=24)
        user_prompt = (
            f"Track ID: {tp.track_id} | Role: {tp.role_title}\n"
            f"Mandate: {tp.focus_mandate}\n\n"
            f"=== TRACK SPECIFIC WEB EVIDENCE ===\n{t_ctx}\n\n"
            f"=== VERIFIED OEM PDF DATASHEETS [EV-PDF-*] ===\n{pdf_ctx}\n\n"
            f"=== PRIOR CORPUS [EV-BASE-*] ===\n{base_ctx}\n\n"
            "Extract grounded TrackResearchDossier JSON using ONLY exact [EV-*] IDs visible above."
        )
        dossier = await deps.llm.complete_json(
            tier="fast",
            node=f"stage1_miner_{tp.track_id}",
            system_prompt=SPECIALIST_SYSTEM,
            user_prompt=user_prompt,
            schema=TrackResearchDossier,
            max_tokens=4096,
        )
        return dossier.model_dump()

    dossiers = await asyncio.gather(*(_mine_one(tp) for tp in plan.track_plans))
    return {
        "track_dossiers": dossiers,
        "datasheet_assets": [a.model_dump() for a in assets],
    }
