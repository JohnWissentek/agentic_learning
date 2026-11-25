"""Stage 1: Parallel Track Retrieval & Flagship Orthogonal Mining (Zero Silent Evidence Backfill)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.prompts import COMPETITIVE_ECOSYSTEM_SYSTEM, TRACK_MINER_SYSTEM
from vf_ccus_workflow.schemas import (
    CommercialWedgeCandidate,
    CompetitiveEcosystemDossier,
    DiscoveryPlan,
    EvidenceRecord,
    SectorDossier,
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


def _filter_valid_ids(ids: list[str], valid_global_ids: set[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for raw_id in ids:
        eid = str(raw_id).strip()
        if eid in valid_global_ids and eid not in seen:
            seen.add(eid)
            kept.append(eid)
    return kept


def clean_sector_dossier(
    *,
    raw_dossier: SectorDossier,
    track_id: str,
    sector: str,
    valid_global_ids: set[str],
) -> tuple[SectorDossier, list[dict[str, Any]]]:
    """Strictly drop unverified items instead of silently backfilling fallback_ids; return audit log."""
    dropped: list[dict[str, Any]] = []

    clean_projects = []
    for p in raw_dossier.named_projects:
        kept = _filter_valid_ids(p.evidence_ids, valid_global_ids)
        if kept:
            clean_projects.append(p.model_copy(update={"evidence_ids": kept}))
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "named_project",
                    "name": p.project_name,
                    "invalid_evidence_ids": list(p.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    clean_comps = []
    for c in raw_dossier.competitors:
        kept = _filter_valid_ids(c.evidence_ids, valid_global_ids)
        if kept:
            clean_comps.append(c.model_copy(update={"evidence_ids": kept}))
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "competitor",
                    "name": c.vendor_name,
                    "invalid_evidence_ids": list(c.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    clean_sizing = []
    for s in raw_dossier.sizing_inputs:
        kept = _filter_valid_ids(s.evidence_ids, valid_global_ids)
        if kept:
            clean_sizing.append(s.model_copy(update={"evidence_ids": kept}))
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "sizing_input",
                    "name": f"{s.sector}/{s.sub_segment}/{s.horizon}",
                    "invalid_evidence_ids": list(s.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    clean_wedges: list[CommercialWedgeCandidate] = []
    for idx, w in enumerate(raw_dossier.wedges, start=1):
        wid = w.wedge_id.strip() or f"{track_id}-W{idx:02d}"
        kept = _filter_valid_ids(w.evidence_ids, valid_global_ids)
        if kept:
            clean_wedges.append(
                w.model_copy(
                    update={
                        "wedge_id": wid,
                        "track_id": track_id,
                        "evidence_ids": kept,
                    }
                )
            )
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "commercial_wedge",
                    "name": f"{wid}: {w.title}",
                    "invalid_evidence_ids": list(w.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    dossier_ev_ids = _filter_valid_ids(raw_dossier.evidence_ids, valid_global_ids)
    if not dossier_ev_ids:
        # Collect verified IDs actually used by surviving children (never unrelated fallback records)
        derived: list[str] = []
        for item in (*clean_projects, *clean_comps, *clean_sizing, *clean_wedges):
            for eid in item.evidence_ids:
                if eid not in derived:
                    derived.append(eid)
        dossier_ev_ids = derived

    cleaned = raw_dossier.model_construct(
        track_id=track_id,
        sector=sector,  # type: ignore[arg-type]
        track_name=raw_dossier.track_name,
        key_findings_summary=raw_dossier.key_findings_summary,
        named_projects=clean_projects,
        competitors=clean_comps,
        sizing_inputs=clean_sizing,
        wedges=clean_wedges,
        evidence_ids=dossier_ev_ids,
    )
    return cleaned, dropped


def clean_competitive_dossier(
    *,
    raw_dossier: CompetitiveEcosystemDossier,
    track_id: str,
    valid_global_ids: set[str],
) -> tuple[CompetitiveEcosystemDossier, list[dict[str, Any]]]:
    """Strictly drop unverified competitors/PAC integrators instead of silently backfilling IDs."""
    dropped: list[dict[str, Any]] = []

    clean_comps = []
    for c in raw_dossier.competitors:
        kept = _filter_valid_ids(c.evidence_ids, valid_global_ids)
        if kept:
            clean_comps.append(c.model_copy(update={"evidence_ids": kept}))
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "competitor",
                    "name": c.vendor_name,
                    "invalid_evidence_ids": list(c.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    clean_pacs = []
    for p in raw_dossier.pac_integrators:
        kept = _filter_valid_ids(p.evidence_ids, valid_global_ids)
        if kept:
            clean_pacs.append(p.model_copy(update={"evidence_ids": kept}))
        else:
            dropped.append(
                {
                    "track_id": track_id,
                    "entity_type": "pac_integrator",
                    "name": p.company_name,
                    "invalid_evidence_ids": list(p.evidence_ids),
                    "reason": "Zero valid EvidenceVault IDs after verification",
                }
            )

    dossier_ev_ids = _filter_valid_ids(raw_dossier.evidence_ids, valid_global_ids)
    if not dossier_ev_ids:
        derived: list[str] = []
        for item in (*clean_comps, *clean_pacs):
            for eid in item.evidence_ids:
                if eid not in derived:
                    derived.append(eid)
        dossier_ev_ids = derived

    cleaned = raw_dossier.model_construct(
        track_id=track_id,
        track_name=raw_dossier.track_name,
        key_findings_summary=raw_dossier.key_findings_summary,
        competitors=clean_comps,
        pac_integrators=clean_pacs,
        design_institute_spec_barriers=list(raw_dossier.design_institute_spec_barriers),
        evidence_ids=dossier_ev_ids,
    )
    return cleaned, dropped


async def node_parallel_track_researcher(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 1: Parallel web retrieval + flagship orthogonal mining (Sector vs Competitive Ecosystem)."""
    profile = state.get("profile", "flagship")
    plan = DiscoveryPlan.model_validate(state["discovery_plan"])
    num_res = 6 if profile == "flagship" else 3
    max_ft = 2 if profile == "flagship" else 1

    siggi_all = deps.vault.list_by_scope("SIGGI")
    recon_all = deps.vault.list_by_track("RECON")
    scope_yaml = deps.settings.discovery_scope

    async def _mine_track(
        tp: TrackPlan,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        track_recs, _ = await collect_queries_for_track(
            deps=deps,
            track=tp,
            num_results=num_res,
            max_fulltext=max_ft,
        )
        combined = track_recs + siggi_all[:16] + recon_all[:10]
        ev_ctx = format_records_compact(combined, limit=48)
        valid_ids = deps.vault.list_valid_ids()

        if tp.track_kind == "competitive_ecosystem":
            user_prompt = (
                f"Track ID: {tp.track_id} | Dedicated Competitive & PAC Ecosystem Track\n"
                f"Track Name: {tp.name}\n"
                f"Hypothesis: {tp.research_hypothesis}\n\n"
                f"=== DUAL-TRACK ARCHITECTURE CONTEXT ===\n"
                f"{scope_yaml.get('delivery_tracks', {})}\n\n"
                f"=== VERIFIED EVIDENCE EXCERPTS ===\n{ev_ctx}\n\n"
                "Extract ONLY verified competitors (across overseas MS, FTIR/optical/GC, domestic MS), "
                "Chinese GB/T 3836 PAC analysis shelter integrators, and Design Institute Spec-in barriers."
            )
            async with deps.semaphore:
                raw_comp = await deps.llm.complete_structured(
                    tier="producer",
                    node=f"miner_comp_{tp.track_id}",
                    system_prompt=COMPETITIVE_ECOSYSTEM_SYSTEM,
                    user_prompt=user_prompt,
                    schema=CompetitiveEcosystemDossier,
                    max_tokens=5200,
                )
            cleaned_comp, dropped = clean_competitive_dossier(
                raw_dossier=raw_comp,
                track_id=tp.track_id,
                valid_global_ids=valid_ids,
            )
            return "competitive", cleaned_comp.model_dump(), dropped

        user_prompt = (
            f"Track ID: {tp.track_id} | Sector: {tp.sector}\n"
            f"Track Name: {tp.name}\n"
            f"Hypothesis: {tp.research_hypothesis}\n\n"
            f"=== DUAL-TRACK PRICING & GUARDRAILS ===\n"
            f"Delivery Tracks ASP (万CNY): {scope_yaml.get('delivery_tracks', {})}\n"
            f"Customer ROI Sector Guardrails: {scope_yaml.get('wedge_roi_guardrails', {}).get(tp.sector, {})}\n\n"
            f"=== VERIFIED EVIDENCE EXCERPTS ===\n{ev_ctx}\n\n"
            "Extract: (1) named_projects, (2) competitors grounded in evidence, "
            "(3) sizing_inputs with explicit `sub_segment` for 2026-2030 & 2031-2036, "
            "(4) 2-3 CommercialWedgeCandidates using STRICT 0-100 scores and domain-faithful 4-line ROI inputs."
        )
        async with deps.semaphore:
            raw_sec = await deps.llm.complete_structured(
                tier="producer",
                node=f"miner_sec_{tp.track_id}",
                system_prompt=TRACK_MINER_SYSTEM,
                user_prompt=user_prompt,
                schema=SectorDossier,
                max_tokens=5200,
            )
        cleaned_sec, dropped = clean_sector_dossier(
            raw_dossier=raw_sec,
            track_id=tp.track_id,
            sector=tp.sector,
            valid_global_ids=valid_ids,
        )
        return "sector", cleaned_sec.model_dump(), dropped

    mined_results = list(await asyncio.gather(*[_mine_track(tp) for tp in plan.track_plans]))
    sector_dossiers = [payload for kind, payload, _ in mined_results if kind == "sector"]
    comp_dossiers = [payload for kind, payload, _ in mined_results if kind == "competitive"]
    all_dropped = [item for _, _, d_list in mined_results for item in d_list]

    return {
        "track_dossiers": sector_dossiers,
        "competitive_dossiers": comp_dossiers,
        "dropped_unverified_records": all_dropped,
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "parallel_track_researcher",
                "sector_tracks_mined": len(sector_dossiers),
                "competitive_tracks_mined": len(comp_dossiers),
                "dropped_unverified_count": len(all_dropped),
                "vault_stats": deps.vault.stats(),
            }
        ],
    }
