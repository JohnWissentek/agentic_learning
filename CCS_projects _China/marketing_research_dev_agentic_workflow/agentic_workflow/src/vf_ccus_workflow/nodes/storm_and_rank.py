"""Stage 2 ([MKT-CALC]+[ROI-CALC] Funnel), Stage 3 (4-Persona STORM) & Stage 4 (Swiss Elo)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.prompts import ELO_PAIRWISE_SYSTEM, STORM_SYSTEM
from vf_ccus_workflow.schemas import (
    ChinaCCUSProjectItem,
    CommercialWedgeCandidate,
    CompetitorProfile,
    EloMatchRecord,
    EvaluatedWedge,
    SegmentSizingInput,
    WedgeStormMemo,
    WorkflowState,
)
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    compute_china_tam_sam_som,
    screen_wedge_pool,
)


class EloPairDecision(BaseModel):
    winner_id: str
    rationale: str = Field(min_length=10)


def aggregate_catalogs_and_screen(
    dossiers: list[dict[str, Any]],
    *,
    discovery_scope: dict[str, Any],
    contract: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    """Deterministic Stage 2 aggregation of projects, competitors, [MKT-CALC], and [ROI-CALC] funnel."""
    proj_map: dict[str, ChinaCCUSProjectItem] = {}
    comp_map: dict[str, CompetitorProfile] = {}
    sizing_list: list[SegmentSizingInput] = []
    wedges: list[CommercialWedgeCandidate] = []

    for d in dossiers:
        for p in d.get("named_projects", []):
            item = ChinaCCUSProjectItem.model_validate(p)
            proj_map.setdefault(item.project_name.strip(), item)
        for c in d.get("competitors", []):
            comp = CompetitorProfile.model_validate(c)
            comp_map.setdefault(comp.vendor_name.strip(), comp)
        for s in d.get("sizing_inputs", []):
            sizing_list.append(SegmentSizingInput.model_validate(s))
        for w in d.get("wedges", []):
            wedges.append(CommercialWedgeCandidate.model_validate(w))

    asp_map = (discovery_scope.get("china_market_sizing_guardrails", {}) or {}).get(
        "asp_by_track_cny_wan", {}
    )
    market_summary = compute_china_tam_sam_som(sizing_list, asp_map=asp_map)

    funnel_cfg = contract.get("discovery_funnel", {}) or {}
    target_total = int(
        funnel_cfg.get("finalist_shortlist_flagship", 10)
        if profile == "flagship"
        else funnel_cfg.get("finalist_shortlist_fast", 6)
    )
    max_cons_pb = float(funnel_cfg.get("max_conservative_payback_months", 42.0))
    guardrails = discovery_scope.get("wedge_roi_guardrails", {}) or {}

    shortlist, eliminated = screen_wedge_pool(
        wedges,
        guardrails=guardrails,
        target_total=target_total,
        max_conservative_payback_months=max_cons_pb,
    )

    return {
        "projects": [p.model_dump() for p in proj_map.values()],
        "competitors": [c.model_dump() for c in comp_map.values()],
        "market_sizing_summary": market_summary.model_dump(),
        "shortlist": [e.model_dump() for e in shortlist],
        "eliminated": [el.model_dump() for el in eliminated],
    }


def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def update_elo(elo_a: float, elo_b: float, a_won: bool, k: float = 32.0) -> tuple[float, float]:
    exp_a = _expected_score(elo_a, elo_b)
    score_a = 1.0 if a_won else 0.0
    score_b = 1.0 - score_a
    return round(elo_a + k * (score_a - exp_a), 2), round(elo_b + k * (score_b - (1.0 - exp_a)), 2)


async def node_size_screen_and_storm(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 2 Deterministic [MKT-CALC]+[ROI-CALC] Funnel -> Stage 3 4-Persona Chinese Buyer STORM."""
    profile = state.get("profile", "flagship")
    agg = aggregate_catalogs_and_screen(
        state.get("track_dossiers", []),
        discovery_scope=deps.settings.discovery_scope,
        contract=deps.settings.contract,
        profile=profile,
    )
    shortlist = [EvaluatedWedge.model_validate(x) for x in agg["shortlist"]]
    tier = "producer" if profile == "flagship" else "fast"

    async def _interrogate(ev: EvaluatedWedge) -> EvaluatedWedge:
        w = ev.seed
        base_r = ev.roi
        cons_r = ev.roi_range.conservative if ev.roi_range else base_r
        prompt = (
            f"Wedge ID: {w.wedge_id} | Track: {w.track_id} | Sector: {w.sector} | Horizon: {w.horizon}\n"
            f"Title: {w.title}\n"
            f"Delivery Track: {w.delivery_track} | SKU & Localization: {w.recommended_vf_sku_and_localization}\n"
            f"Chemical Pain Point & IMR Advantage: {w.chemical_pain_point_and_imr_advantage}\n"
            f"Competing Alternatives: {w.key_competing_alternatives}\n"
            f"Named CN Customers: {', '.join(w.named_china_benchmark_customers)}\n"
            f"[ROI-CALC] Baseline: CAPEX=¥{base_r.capex_cny:,.0f}, NetCF=¥{base_r.net_annual_cashflow_cny:,.0f}/yr, "
            f"Payback={base_r.payback_months}m, 5Y IRR={base_r.irr_5yr_pct}%, 5Y NPV=¥{base_r.npv_5yr_cny:,.0f}\n"
            f"[ROI-CALC] Conservative: CAPEX=¥{cons_r.capex_cny:,.0f}, Payback={cons_r.payback_months}m\n\n"
            "Evaluate rigorously across ALL 4 Chinese buyer personas."
        )
        async with deps.semaphore:
            memo = await deps.llm.complete_structured(
                tier=tier,
                node=f"storm_{w.wedge_id}",
                system_prompt=STORM_SYSTEM,
                user_prompt=prompt,
                schema=WedgeStormMemo,
                max_tokens=2800,
            )
        memo = memo.model_copy(update={"wedge_id": w.wedge_id})
        return ev.model_copy(update={"storm_memo": memo})

    interrogated = list(await asyncio.gather(*[_interrogate(e) for e in shortlist]))
    memos_map = {
        e.seed.wedge_id: e.storm_memo.model_dump()
        for e in interrogated
        if e.storm_memo is not None
    }

    return {
        "china_projects_catalog": agg["projects"],
        "competitors_catalog": agg["competitors"],
        "market_sizing_summary": agg["market_sizing_summary"],
        "evaluated_wedges": [e.model_dump() for e in interrogated],
        "eliminated_wedges": agg["eliminated"],
        "storm_memos": memos_map,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "size_screen_and_storm",
                "shortlist_count": len(interrogated),
                "eliminated_count": len(agg["eliminated"]),
                "projects_cataloged": len(agg["projects"]),
                "competitors_cataloged": len(agg["competitors"]),
            }
        ],
    }


async def node_swiss_elo_ranker(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 4: Swiss-System Pairwise Elo Tournament across shortlisted wedges."""
    profile = state.get("profile", "flagship")
    evaluated = [EvaluatedWedge.model_validate(x) for x in state.get("evaluated_wedges", [])]
    for ev in evaluated:
        ev.elo_rating = round(1500.0 + (ev.weighted_pillar_score - 75.0) * 4.0, 2)

    rounds = 2 if profile == "flagship" else 1
    tier = "producer" if profile == "flagship" else "fast"
    elo_records: list[EloMatchRecord] = []

    def _card(label: str, ev: EvaluatedWedge) -> str:
        s = ev.seed
        return (
            f"[{label}: {s.wedge_id}] {s.title}\n"
            f"- Sector/Track/Horizon: {s.sector} / {s.delivery_track} / {s.horizon}\n"
            f"- Priority={s.china_priority_score} | V&F Moat={s.vf_moat_score} | Pillar={ev.weighted_pillar_score}\n"
            f"- Physics Moat: {s.chemical_pain_point_and_imr_advantage}\n"
            f"- [ROI-CALC] Baseline CAPEX=¥{ev.roi.capex_cny/10000:.1f}万, "
            f"Payback={ev.roi.payback_months}m, IRR={ev.roi.irr_5yr_pct}%"
        )

    for r_idx in range(1, rounds + 1):
        evaluated.sort(key=lambda x: x.elo_rating, reverse=True)
        pairs = [(evaluated[i], evaluated[i + 1]) for i in range(0, len(evaluated) - 1, 2)]

        async def _judge(a: EvaluatedWedge, b: EvaluatedWedge):
            prompt = (
                f"{_card('Option A', a)}\n\n{_card('Option B', b)}\n\n"
                f'Pick `winner_id` equal to "{a.seed.wedge_id}" or "{b.seed.wedge_id}".'
            )
            async with deps.semaphore:
                dec = await deps.llm.complete_structured(
                    tier=tier,
                    node=f"elo_r{r_idx}",
                    system_prompt=ELO_PAIRWISE_SYSTEM,
                    user_prompt=prompt,
                    schema=EloPairDecision,
                    max_tokens=700,
                )
            return a, b, dec

        outcomes = await asyncio.gather(*[_judge(a, b) for a, b in pairs])
        for a, b, dec in outcomes:
            a_won = dec.winner_id.strip() != b.seed.wedge_id
            w_id = a.seed.wedge_id if a_won else b.seed.wedge_id
            new_a, new_b = update_elo(a.elo_rating, b.elo_rating, a_won)
            a.elo_rating, b.elo_rating = new_a, new_b
            elo_records.append(
                EloMatchRecord(
                    round_idx=r_idx,
                    wedge_a_id=a.seed.wedge_id,
                    wedge_b_id=b.seed.wedge_id,
                    winner_id=w_id,
                    rationale=dec.rationale,
                    elo_a_after=new_a,
                    elo_b_after=new_b,
                )
            )

    if evaluated:
        elos = [e.elo_rating for e in evaluated]
        lo, hi = min(elos), max(elos)
        span = max(1.0, hi - lo)
        evaluated.sort(
            key=lambda e: 0.55 * e.weighted_pillar_score
            + 0.45 * (60.0 + ((e.elo_rating - lo) / span) * 38.0),
            reverse=True,
        )
        for idx, item in enumerate(evaluated, start=1):
            item.composite_rank = idx

    return {
        "evaluated_wedges": [e.model_dump() for e in evaluated],
        "elo_matches": [m.model_dump() for m in elo_records],
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "swiss_elo_ranker",
                "matches_played": len(elo_records),
            }
        ],
    }
