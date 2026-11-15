"""Stage 3 & Stage 4: STORM Multi-Persona Interrogation, 3-Scenario PALMs ROI, and Elo Tournament."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import ELO_PAIRWISE_SYSTEM, STORM_SYSTEM
from pso_workflow.schemas import (
    EloMatchRecord,
    EvaluatedOpportunity,
    OpportunityStormMemo,
    TechOpportunitySeed,
    WorkflowState,
)
from pso_workflow.tools.roi_calculator import (
    compute_range_roi_metrics,
    compute_weighted_pillar_score,
    derive_range_inputs_from_seed,
)


class EloPairDecision(BaseModel):
    """Structured winner selection for one Elo tournament matchup."""

    winner_id: str
    rationale: str = Field(min_length=10)


def _collect_unique_seeds(dossiers: list[dict[str, Any]]) -> list[TechOpportunitySeed]:
    seen: dict[str, TechOpportunitySeed] = {}
    for d in dossiers:
        for raw_opp in d.get("opportunities", []):
            seed = TechOpportunitySeed.model_validate(raw_opp)
            if seed.opp_id not in seen:
                seen[seed.opp_id] = seed
    return list(seen.values())


def _resolve_evaluated_pool(
    state: WorkflowState, deps: RuntimeDeps
) -> list[EvaluatedOpportunity]:
    """Use Stage 2 screened shortlist if present; otherwise derive 3-scenario ROI from dossiers."""
    existing = state.get("evaluated_opportunities", [])
    memos_map = state.get("storm_memos", {}) or {}
    if existing:
        out: list[EvaluatedOpportunity] = []
        for raw in existing:
            ev = EvaluatedOpportunity.model_validate(raw)
            if ev.storm_memo is None and ev.seed.opp_id in memos_map:
                ev = ev.model_copy(
                    update={"storm_memo": OpportunityStormMemo.model_validate(memos_map[ev.seed.opp_id])}
                )
            out.append(ev)
        return out

    guardrails = deps.settings.discovery_scope.get("sector_roi_guardrails", {}) or {}
    seeds = _collect_unique_seeds(state.get("track_dossiers", []))
    fallback_pool: list[EvaluatedOpportunity] = []
    for seed in seeds:
        clamped_rng = derive_range_inputs_from_seed(seed, guardrails=guardrails)
        clean_seed = seed.model_copy(
            update={
                "roi_range_inputs": clamped_rng,
                "roi_inputs": clamped_rng.to_baseline_inputs(),
            }
        )
        roi_range = compute_range_roi_metrics(clamped_rng)
        roi = roi_range.baseline
        w_score = compute_weighted_pillar_score(
            roi=roi,
            china_priority=clean_seed.china_priority_score,
            global_priority=clean_seed.global_priority_score,
            horizon=clean_seed.horizon,
            evidence_count=len(clean_seed.evidence_ids),
            commercial_status=clean_seed.commercial_status,
            has_ai_co_design=bool(clean_seed.ai_computational_sensing_and_co_design.strip()),
        )
        raw_memo = memos_map.get(clean_seed.opp_id)
        fallback_pool.append(
            EvaluatedOpportunity(
                seed=clean_seed,
                roi=roi,
                roi_range=roi_range,
                storm_memo=OpportunityStormMemo.model_validate(raw_memo) if raw_memo else None,
                weighted_pillar_score=w_score,
            )
        )
    return fallback_pool


async def node_storm_persona_interrogator(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 7 + Stanford STORM: stress-test shortlisted candidates with 4 factory buyer personas."""
    profile = state.get("profile", "flagship")
    pool = _resolve_evaluated_pool(state, deps)
    tier = "producer" if profile == "flagship" else "fast"

    async def _interrogate_one(ev: EvaluatedOpportunity) -> EvaluatedOpportunity:
        seed = ev.seed
        base_roi = ev.roi
        cons_roi = ev.roi_range.conservative if ev.roi_range else base_roi
        opt_roi = ev.roi_range.optimistic if ev.roi_range else base_roi
        user_prompt = (
            f"Opportunity ID: {seed.opp_id}\n"
            f"Sector: {seed.sector} | Track: {seed.track_id} | Horizon: {seed.horizon} | "
            f"Commercial White-Space Status: {seed.commercial_status}\n"
            f"Title: {seed.title}\n"
            f"Overseas Incumbents & Products: {seed.global_vendors_and_products}\n"
            f"China Vendors & Status: {seed.china_vendors_and_products}\n"
            f"White-Space & Entry Wedge: {seed.white_space_and_entry_wedge}\n"
            f"AI Computational Sensing & HW/SW Co-Design: {seed.ai_computational_sensing_and_co_design}\n"
            f"AI R&D Acceleration & Edge Deployment: {seed.ai_rd_acceleration_and_edge_deployment}\n"
            f"R&D Cycle Comparison: {seed.estimated_rd_months_ai_vs_legacy} | "
            f"BOM & GTM Form: {seed.hardware_bom_localization_and_gtm_form}\n"
            f"Physics Principle: {seed.physics_principle}\n"
            f"Target Process Point: {seed.target_process_point}\n"
            f"Form Factor: {seed.product_form_factor}\n"
            f"China Positioning: {seed.china_positioning}\n"
            f"Global Expansion: {seed.global_expansion_path}\n"
            f"Deterministic [ROI-CALC] Baseline: CAPEX=¥{base_roi.capex_cny:,.0f}, "
            f"Net Annual CF=¥{base_roi.net_annual_cashflow_cny:,.0f}, "
            f"Payback={base_roi.payback_months}m, 5Y IRR={base_roi.irr_5yr_pct}%\n"
            f"Deterministic [ROI-CALC] Conservative Stress vs Optimistic: "
            f"Conservative Payback={cons_roi.payback_months}m (CAPEX=¥{cons_roi.capex_cny:,.0f}, IRR={cons_roi.irr_5yr_pct}%), "
            f"Optimistic Payback={opt_roi.payback_months}m\n\n"
            f"Stress-test BOTH baseline AND conservative downside adoption barriers, including: "
            f"(1) incumbent vendor switching barrier vs true-blank few-shot cold-start, "
            f"(2) AI Edge-AI FPGA/NPU false-alarm & drift calibration risk in air-gapped lines, and "
            f"(3) hardware+software TCO payback! "
            f"Generate an `OpportunityStormMemo` with ALL 4 exact `persona_role` entries: "
            f'"Fab/Plant Yield VP", "Metrology/Process Chief Engineer", '
            f'"EHS & Green Compliance Director", "CFO / Procurement ROI Gatekeeper".'
        )
        async with deps.semaphore:
            memo = await deps.llm.complete_structured(
                tier=tier,
                node=f"storm_{seed.opp_id}",
                system_prompt=STORM_SYSTEM,
                user_prompt=user_prompt,
                schema=OpportunityStormMemo,
                max_tokens=3200,
            )
        memo = memo.model_copy(update={"opp_id": seed.opp_id})
        return ev.model_copy(update={"storm_memo": memo})

    updated_pool = list(await asyncio.gather(*[_interrogate_one(ev) for ev in pool]))
    memos_map = {
        ev.seed.opp_id: ev.storm_memo.model_dump()
        for ev in updated_pool
        if ev.storm_memo is not None
    }

    return {
        "storm_memos": memos_map,
        "evaluated_opportunities": [ev.model_dump() for ev in updated_pool],
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "storm_persona_interrogator",
                "opportunities_interrogated": len(memos_map),
            }
        ],
    }


def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _update_elo(elo_a: float, elo_b: float, a_won: bool, k: float = 32.0) -> tuple[float, float]:
    exp_a = _expected_score(elo_a, elo_b)
    exp_b = 1.0 - exp_a
    score_a = 1.0 if a_won else 0.0
    score_b = 1.0 - score_a
    return round(elo_a + k * (score_a - exp_a), 2), round(elo_b + k * (score_b - exp_b), 2)


async def node_palms_roi_and_elo_ranker(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 17 3-Scenario PALMs ROI Ranking + Ch 20/21 Swiss-System Elo Tournament."""
    profile = state.get("profile", "flagship")
    evaluated = _resolve_evaluated_pool(state, deps)

    for ev in evaluated:
        ev.elo_rating = round(1500.0 + (ev.weighted_pillar_score - 75.0) * 4.0, 2)

    rounds = 2 if profile == "flagship" else 1
    elo_records: list[EloMatchRecord] = []
    tier = "producer" if profile == "flagship" else "fast"

    def _format_pair_card(label: str, ev: EvaluatedOpportunity) -> str:
        cons_pb = ev.roi_range.conservative.payback_months if ev.roi_range else ev.roi.payback_months
        opt_pb = ev.roi_range.optimistic.payback_months if ev.roi_range else ev.roi.payback_months
        tam_cn = ev.seed.roi_inputs.market_tam_china_cny_100m if ev.seed.roi_inputs else 0.0
        return (
            f"[{label}: {ev.seed.opp_id}] {ev.seed.title}\n"
            f"- Sector/Track/Horizon: {ev.seed.sector} / {ev.seed.track_id} / {ev.seed.horizon} | "
            f"White-Space={ev.seed.commercial_status} | China Priority={ev.seed.china_priority_score}\n"
            f"- Vendors (Global vs CN): {ev.seed.global_vendors_and_products} || {ev.seed.china_vendors_and_products}\n"
            f"- AI HW/SW Co-Design: {ev.seed.ai_computational_sensing_and_co_design} | R&D: {ev.seed.estimated_rd_months_ai_vs_legacy}\n"
            f"- [ROI-CALC]: CAPEX=¥{ev.roi.capex_cny:,.0f}, Net Annual CF=¥{ev.roi.net_annual_cashflow_cny:,.0f}, "
            f"Payback(Opt/Base/Cons)={opt_pb}/{ev.roi.payback_months}/{cons_pb}m, "
            f"5Y IRR={ev.roi.irr_5yr_pct}%, China TAM=¥{tam_cn}亿\n"
            f"- Quality/Yield: {ev.seed.quality_yield_mechanism}\n"
            f"- Upgrade: {ev.seed.industrial_upgrade_mechanism}"
        )

    for r_idx in range(1, rounds + 1):
        evaluated.sort(key=lambda x: x.elo_rating, reverse=True)
        matchups: list[tuple[EvaluatedOpportunity, EvaluatedOpportunity]] = []
        for i in range(0, len(evaluated) - 1, 2):
            matchups.append((evaluated[i], evaluated[i + 1]))

        async def _judge_pair(
            a: EvaluatedOpportunity, b: EvaluatedOpportunity
        ) -> tuple[EvaluatedOpportunity, EvaluatedOpportunity, EloPairDecision]:
            prompt = (
                f"Compare Option A vs Option B (considering BOTH baseline ROI and conservative downside resilience):\n\n"
                f"{_format_pair_card('Option A', a)}\n\n"
                f"{_format_pair_card('Option B', b)}\n\n"
                f'Output JSON with `winner_id` equal to either "{a.seed.opp_id}" or "{b.seed.opp_id}" and concise `rationale`.'
            )
            async with deps.semaphore:
                dec = await deps.llm.complete_structured(
                    tier=tier,
                    node=f"elo_r{r_idx}",
                    system_prompt=ELO_PAIRWISE_SYSTEM,
                    user_prompt=prompt,
                    schema=EloPairDecision,
                    max_tokens=900,
                )
            return a, b, dec

        decisions = await asyncio.gather(*[_judge_pair(a, b) for a, b in matchups])
        for a, b, dec in decisions:
            a_won = dec.winner_id.strip() != b.seed.opp_id
            winner_id = a.seed.opp_id if a_won else b.seed.opp_id
            new_a, new_b = _update_elo(a.elo_rating, b.elo_rating, a_won)
            a.elo_rating = new_a
            b.elo_rating = new_b
            elo_records.append(
                EloMatchRecord(
                    round_idx=r_idx,
                    opp_a_id=a.seed.opp_id,
                    opp_b_id=b.seed.opp_id,
                    winner_id=winner_id,
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
        for rank_idx, item in enumerate(evaluated, start=1):
            item.composite_rank = rank_idx

    return {
        "evaluated_opportunities": [e.model_dump() for e in evaluated],
        "elo_matches": [m.model_dump() for m in elo_records],
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "palms_roi_and_elo_ranker",
                "opportunities_ranked": len(evaluated),
                "elo_matches": len(elo_records),
            }
        ],
    }
