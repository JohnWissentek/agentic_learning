"""Nodes 3 & 4: STORM Multi-Persona Interrogation, PALMs ROI Engine, and Elo Tournament."""

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
    compute_roi_metrics,
    compute_weighted_pillar_score,
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


async def node_storm_persona_interrogator(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 7 + Stanford STORM: stress-test every opportunity with 4 factory buyer personas."""
    dossiers = state.get("track_dossiers", [])
    profile = state.get("profile", "flagship")
    seeds = _collect_unique_seeds(dossiers)
    tier = "producer" if profile == "flagship" else "fast"

    async def _interrogate_one(seed: TechOpportunitySeed) -> tuple[str, dict[str, Any]]:
        roi_preview = compute_roi_metrics(seed.roi_inputs)
        user_prompt = (
            f"Opportunity ID: {seed.opp_id}\n"
            f"Sector: {seed.sector} | Track: {seed.track_id} | Horizon: {seed.horizon}\n"
            f"Title: {seed.title}\n"
            f"Physics Principle: {seed.physics_principle}\n"
            f"Target Process Point: {seed.target_process_point}\n"
            f"Form Factor: {seed.product_form_factor}\n"
            f"China Positioning: {seed.china_positioning}\n"
            f"Global Expansion: {seed.global_expansion_path}\n"
            f"Deterministic [ROI-CALC] Baseline: CAPEX=¥{roi_preview.capex_cny:,.0f}, "
            f"Annual Gross Benefit=¥{roi_preview.annual_gross_benefit_cny:,.0f}, "
            f"Payback={roi_preview.payback_months} months, 5Y IRR={roi_preview.irr_5yr_pct}%\n\n"
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
        return seed.opp_id, memo.model_dump()

    pairs = await asyncio.gather(*[_interrogate_one(s) for s in seeds])
    memos_map = dict(pairs)

    return {
        "storm_memos": memos_map,
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
    """Ch 17 PALMs deterministic ROI computation + Ch 20/21 Elo Tournament Ranking."""
    dossiers = state.get("track_dossiers", [])
    memos_map = state.get("storm_memos", {})
    profile = state.get("profile", "flagship")
    seeds = _collect_unique_seeds(dossiers)

    evaluated: list[EvaluatedOpportunity] = []
    for seed in seeds:
        roi = compute_roi_metrics(seed.roi_inputs)
        pillar_score = compute_weighted_pillar_score(
            roi=roi,
            china_priority=seed.china_priority_score,
            global_priority=seed.global_priority_score,
            horizon=seed.horizon,
            evidence_count=len(seed.evidence_ids),
        )
        raw_memo = memos_map.get(seed.opp_id)
        memo_obj = OpportunityStormMemo.model_validate(raw_memo) if raw_memo else None
        evaluated.append(
            EvaluatedOpportunity(
                seed=seed,
                roi=roi,
                storm_memo=memo_obj,
                weighted_pillar_score=pillar_score,
                elo_rating=1500.0 + (pillar_score - 75.0) * 4.0,
            )
        )

    # Swiss-system pairwise Elo tournament across adjacent sorted pairs
    rounds = 2 if profile == "flagship" else 1
    elo_records: list[EloMatchRecord] = []
    tier = "producer" if profile == "flagship" else "fast"

    for r_idx in range(1, rounds + 1):
        evaluated.sort(key=lambda x: x.elo_rating, reverse=True)
        matchups: list[tuple[EvaluatedOpportunity, EvaluatedOpportunity]] = []
        for i in range(0, len(evaluated) - 1, 2):
            matchups.append((evaluated[i], evaluated[i + 1]))

        async def _judge_pair(
            a: EvaluatedOpportunity, b: EvaluatedOpportunity
        ) -> tuple[EvaluatedOpportunity, EvaluatedOpportunity, EloPairDecision]:
            prompt = (
                f"Compare Option A vs Option B:\n\n"
                f"[Option A: {a.seed.opp_id}] {a.seed.title}\n"
                f"- Sector/Horizon: {a.seed.sector} / {a.seed.horizon} | China Priority={a.seed.china_priority_score}\n"
                f"- [ROI-CALC]: CAPEX=¥{a.roi.capex_cny:,.0f}, Net Annual CF=¥{a.roi.net_annual_cashflow_cny:,.0f}, "
                f"Payback={a.roi.payback_months}m, 5Y IRR={a.roi.irr_5yr_pct}%, China TAM=¥{a.seed.roi_inputs.market_tam_china_cny_100m}亿\n"
                f"- Quality/Yield: {a.seed.quality_yield_mechanism}\n"
                f"- Upgrade: {a.seed.industrial_upgrade_mechanism}\n\n"
                f"[Option B: {b.seed.opp_id}] {b.seed.title}\n"
                f"- Sector/Horizon: {b.seed.sector} / {b.seed.horizon} | China Priority={b.seed.china_priority_score}\n"
                f"- [ROI-CALC]: CAPEX=¥{b.roi.capex_cny:,.0f}, Net Annual CF=¥{b.roi.net_annual_cashflow_cny:,.0f}, "
                f"Payback={b.roi.payback_months}m, 5Y IRR={b.roi.irr_5yr_pct}%, China TAM=¥{b.seed.roi_inputs.market_tam_china_cny_100m}亿\n"
                f"- Quality/Yield: {b.seed.quality_yield_mechanism}\n"
                f"- Upgrade: {b.seed.industrial_upgrade_mechanism}\n\n"
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

    # Final composite rank: 55% weighted_pillar_score + 45% normalized Elo
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
