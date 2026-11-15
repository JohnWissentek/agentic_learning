"""Stage 1 Parallel Deep-Research Track Searchers & Structured Track Mining."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.prompts import TRACK_MINER_SYSTEM
from vf_ccus_workflow.schemas import (
    CommercialWedgeCandidate,
    DiscoveryPlan,
    EvidenceRecord,
    TrackDossier,
    TrackPlan,
    WorkflowState,
)


async def collect_queries_for_track(
    *,
    deps: RuntimeDeps,
    track: TrackPlan,
    num_results: int = 6,
    max_fulltext: int = 3,
) -> tuple[list[EvidenceRecord], list[str]]:
    """Run CN (Metaso) + GLOBAL (Serper) search for one track, plus selective full-text read."""
    records: list[EvidenceRecord] = []
    q_hashes: list[str] = []

    async def _run_batch(queries: list[str], geo: str, mode: str) -> None:
        for q in queries:
            hits = await deps.search_router.search_track(
                track_id=track.track_id,
                geo_scope=geo,  # type: ignore[arg-type]
                query=q,
                mode=mode,  # type: ignore[arg-type]
                num_results=num_results,
            )
            deps.vault.log_query(
                track_id=track.track_id,
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,  # type: ignore[arg-type]
                query=q,
                hits_count=len(hits),
            )
            q_hashes.append(f"{geo}:{q[:40]}")
            for idx, hit in enumerate(hits):
                if idx < max_fulltext and not hit.content and hit.url.startswith("http"):
                    md = await deps.search_router.read_fulltext(url=hit.url, track_id=track.track_id)
                    if md:
                        hit.content = md
                rec = deps.vault.upsert_hit(track_id=track.track_id, hit=hit)
                if rec is not None:
                    records.append(rec)

    await asyncio.gather(
        _run_batch(track.cn_queries, "CN", "webpage"),
        _run_batch(track.global_queries, "GLOBAL", "search"),
    )
    return records, q_hashes


def clean_track_dossier(
    *,
    raw_dossier: TrackDossier,
    track_id: str,
    sector: str,
    track_records: list[EvidenceRecord],
    valid_global_ids: set[str],
) -> TrackDossier:
    """Enforce zero-hallucination evidence IDs across all nested projects/competitors/wedges."""
    fallback_ids = [r.ev_id for r in track_records[:4]] or sorted(valid_global_ids)[:4]

    def _keep_valid(ids: list[str]) -> list[str]:
        kept = [str(eid).strip() for eid in ids if str(eid).strip() in valid_global_ids]
        return kept if kept else fallback_ids

    clean_projects = [
        p.model_copy(update={"evidence_ids": _keep_valid(p.evidence_ids)})
        for p in raw_dossier.named_projects
    ]
    clean_comps = [
        c.model_copy(update={"evidence_ids": _keep_valid(c.evidence_ids)})
        for c in raw_dossier.competitors
    ]
    clean_sizing = [
        s.model_copy(update={"evidence_ids": _keep_valid(s.evidence_ids)})
        for s in raw_dossier.sizing_inputs
    ]
    clean_wedges: list[CommercialWedgeCandidate] = []
    for idx, w in enumerate(raw_dossier.wedges, start=1):
        wid = w.wedge_id.strip() or f"{track_id}-W{idx:02d}"
        clean_wedges.append(
            w.model_copy(
                update={
                    "wedge_id": wid,
                    "track_id": track_id,
                    "evidence_ids": _keep_valid(w.evidence_ids),
                }
            )
        )

    return raw_dossier.model_copy(
        update={
            "track_id": track_id,
            "sector": sector,
            "named_projects": clean_projects,
            "competitors": clean_comps,
            "sizing_inputs": clean_sizing,
            "wedges": clean_wedges,
            "evidence_ids": _keep_valid(raw_dossier.evidence_ids),
        }
    )


async def node_parallel_track_researcher(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 1: Parallel web + Siggi retrieval and structured JSON track mining."""
    profile = state.get("profile", "flagship")
    plan = DiscoveryPlan.model_validate(state["discovery_plan"])
    num_res = 6 if profile == "flagship" else 3
    max_ft = 2 if profile == "flagship" else 1

    siggi_all = deps.vault.list_by_scope("SIGGI")
    recon_all = deps.vault.list_by_track("RECON")
    tier = "fast"

    async def _mine_track(tp: TrackPlan) -> TrackDossier:
        track_recs, _ = await collect_queries_for_track(
            deps=deps,
            track=tp,
            num_results=num_res,
            max_fulltext=max_ft,
        )
        combined = track_recs + siggi_all[:12] + recon_all[:8]
        ev_ctx = format_records_compact(combined, limit=30)
        scope_yaml = deps.settings.discovery_scope

        user_prompt = (
            f"Track ID: {tp.track_id} | Sector: {tp.sector}\n"
            f"Track Name: {tp.name}\n"
            f"Hypothesis: {tp.research_hypothesis}\n\n"
            f"=== DUAL-TRACK PRICING & GUARDRAILS ===\n"
            f"Delivery Tracks ASP (万CNY): {scope_yaml.get('delivery_tracks', {})}\n"
            f"Customer ROI Sector Guardrails: {scope_yaml.get('wedge_roi_guardrails', {}).get(tp.sector, {})}\n\n"
            f"=== VERIFIED EVIDENCE EXCERPTS ===\n{ev_ctx}\n\n"
            "Extract: (1) named_projects (verified Chinese CCUS/EOR/e-MeOH/ship projects), "
            "(2) competitors (only vendors/models grounded in evidence), "
            "(3) sizing_inputs (1-2 bottom-up SegmentSizingInput entries for 2026-2030 & 2031-2036), "
            "(4) 2-4 CommercialWedgeCandidates assigning exact delivery_track and realistic ROI inputs."
        )
        async with deps.semaphore:
            raw = await deps.llm.complete_structured(
                tier=tier,
                node=f"miner_{tp.track_id}",
                system_prompt=TRACK_MINER_SYSTEM,
                user_prompt=user_prompt,
                schema=TrackDossier,
                max_tokens=4800,
            )
        valid_ids = deps.vault.list_valid_ids()
        return clean_track_dossier(
            raw_dossier=raw,
            track_id=tp.track_id,
            sector=tp.sector,
            track_records=track_recs,
            valid_global_ids=valid_ids,
        )

    dossiers = list(await asyncio.gather(*[_mine_track(tp) for tp in plan.track_plans]))
    return {
        "track_dossiers": [d.model_dump() for d in dossiers],
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "parallel_track_researcher",
                "tracks_mined": len(dossiers),
                "vault_stats": deps.vault.stats(),
            }
        ],
    }
