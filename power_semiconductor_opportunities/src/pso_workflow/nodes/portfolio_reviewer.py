"""Stage 3 (V4.0): Unified Sector Buying-Committee Stress-Test & Portfolio Prioritization.

Replaces 16 isolated STORM calls + 16 noisy 2-round Elo pairwise calls (32 fragmented calls)
with 1 holistic flagship-brain review per active sector + 1 cross-sector executive ordering
(2-3 calls total), ensuring buyer objections, calibrated 3-scenario [ROI-CALC], falsification
notes, and verified Vault evidence directly inform the final portfolio ranking.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import GLOBAL_PORTFOLIO_RANK_SYSTEM, PORTFOLIO_COMMITTEE_SYSTEM
from pso_workflow.schemas import (
    EvaluatedOpportunity,
    EvidenceRecord,
    GlobalPortfolioRanking,
    OpportunityStormMemo,
    PortfolioCandidateReview,
    SectorPortfolioReview,
    WorkflowState,
)
from pso_workflow.tools.audit_guard import wrap_untrusted_evidence


def _collect_sector_evidence_snippets(
    sector_opps: list[EvaluatedOpportunity],
    all_records: list[EvidenceRecord],
    *,
    sector: str,
) -> str:
    """Gather authentic EvidenceVault snippets for every shortlisted candidate in a sector."""
    by_ev_id = {r.ev_id: r for r in all_records}
    chosen: list[EvidenceRecord] = []
    seen_ids: set[str] = set()

    for ev in sector_opps:
        for eid in ev.seed.evidence_ids:
            rec = by_ev_id.get(eid)
            if rec is not None and rec.ev_id not in seen_ids:
                seen_ids.add(rec.ev_id)
                chosen.append(rec)

    if len(chosen) < len(sector_opps) * 2:
        track_ids = {ev.seed.track_id for ev in sector_opps}
        for rec in all_records:
            if rec.track_id in track_ids and rec.ev_id not in seen_ids:
                seen_ids.add(rec.ev_id)
                chosen.append(rec)
                if len(chosen) >= 32:
                    break

    lines = [
        f"- [{r.ev_id}] ({r.track_id} | {r.geo_scope} | {r.authority_tier}) {r.title}: "
        f"{(r.full_markdown[:400] if r.full_markdown else r.snippet[:320]).replace(chr(10), ' ')}"
        for r in chosen
    ]
    raw = "\n".join(lines) if lines else "(No Vault snippets found for this sector.)"
    return wrap_untrusted_evidence(raw, label=f"PORTFOLIO_{sector.upper()}_EVIDENCE")


def _format_sector_candidate_cards(sector_opps: list[EvaluatedOpportunity]) -> str:
    """Format all candidates in a sector side-by-side with 3-scenario [ROI-CALC] & falsification notes."""
    cards: list[str] = []
    for ev in sector_opps:
        s = ev.seed
        r = ev.roi
        opt_pb = ev.roi_range.optimistic.payback_months if ev.roi_range else r.payback_months
        cons_pb = ev.roi_range.conservative.payback_months if ev.roi_range else r.payback_months
        cards.append(
            f"### Candidate `{s.opp_id}` ({s.track_id} | {s.horizon}): {s.title}\n"
            f"- Commercial Status: `{s.commercial_status}`\n"
            f"- Falsification Audit Note: {s.falsification_audit_note or '未执行/无特殊修正'}\n"
            f"- Vendors (Global vs CN): {s.global_vendors_and_products} || {s.china_vendors_and_products}\n"
            f"- White-Space Wedge: {s.white_space_and_entry_wedge}\n"
            f"- AI HW/SW Co-Design: {s.ai_computational_sensing_and_co_design} | R&D: {s.estimated_rd_months_ai_vs_legacy}\n"
            f"- Deterministic [ROI-CALC] 3-Scenario Payback (Opt/Base/Cons): "
            f"{opt_pb:.1f} / {r.payback_months:.1f} / {cons_pb:.1f} 个月 | "
            f"CAPEX=¥{r.capex_cny:,.0f} | NetCF=¥{r.net_annual_cashflow_cny:,.0f}/yr | "
            f"5Y IRR={r.irr_5yr_pct:.1f}% | Weighted Pillar Score={ev.weighted_pillar_score:.2f}\n"
            f"- Evidence IDs: {', '.join(s.evidence_ids)}"
        )
    return "\n\n".join(cards)


def build_sector_portfolio_prompt(
    sector: Literal["power_energy", "semiconductor"],
    sector_opps: list[EvaluatedOpportunity],
    all_records: list[EvidenceRecord],
) -> str:
    """Build deterministic holistic sector prompt shared by LangGraph & IDE thin shell."""
    cards = _format_sector_candidate_cards(sector_opps)
    ev_block = _collect_sector_evidence_snippets(sector_opps, all_records, sector=sector)
    opp_ids = [ev.seed.opp_id for ev in sector_opps]
    return (
        f"Sector: `{sector}` | Shortlisted Candidates ({len(sector_opps)}): {opp_ids}\n\n"
        f"## All Sector Candidates Side-by-Side (with Calibrated [ROI-CALC] & Falsification Notes)\n"
        f"{cards}\n\n"
        f"## Grounded EvidenceVault Excerpts\n"
        f"{ev_block}\n\n"
        f"Execute a holistic 4-persona buying-committee stress-test AND relative portfolio ranking across "
        f"ALL {len(sector_opps)} candidates (`{opp_ids}`). Every candidate MUST appear once in `ranked_reviews` "
        f"with all 4 `persona_role` entries (`Fab/Plant Yield VP`, `Metrology/Process Chief Engineer`, "
        f"`EHS & Green Compliance Director`, `CFO / Procurement ROI Gatekeeper`)."
    )


def build_global_ranking_prompt(
    sector_reviews: dict[str, SectorPortfolioReview],
    by_id: dict[str, EvaluatedOpportunity],
) -> str:
    """Build concise cross-sector executive ranking prompt combining both sector reviews."""
    lines: list[str] = []
    for sec, rev in sector_reviews.items():
        lines.append(f"### Sector `{sec}` Committee Synthesis\n{rev.portfolio_synthesis}")
        for r in sorted(rev.ranked_reviews, key=lambda x: x.sector_rank):
            ev = by_id.get(r.opp_id)
            if ev is None:
                continue
            cons_pb = ev.roi_range.conservative.payback_months if ev.roi_range else ev.roi.payback_months
            lines.append(
                f"- `{r.opp_id}` (sector_rank=#{r.sector_rank}, role=`{r.portfolio_role}`, "
                f"status=`{ev.seed.commercial_status}`, [ROI-CALC] Base/Cons={ev.roi.payback_months:.1f}/{cons_pb:.1f}m, "
                f"IRR={ev.roi.irr_5yr_pct:.1f}%, Pillar={ev.weighted_pillar_score:.1f}): "
                f"{ev.seed.title} | Objection: {r.sharpest_pain_point_summary} | Rationale: {r.ranking_rationale}"
            )
    all_valid_ids = list(by_id.keys())
    return (
        f"Finalist Opportunity IDs ({len(all_valid_ids)}): {all_valid_ids}\n\n"
        + "\n".join(lines)
        + f"\n\nReturn `GlobalPortfolioRanking` with `ordered_opp_ids` containing EVERY ID in {all_valid_ids} "
        f"exactly once in final executive investment priority order."
    )


def apply_portfolio_reviews_and_rank(
    pool: list[EvaluatedOpportunity],
    sector_reviews: dict[str, SectorPortfolioReview],
    global_ranking: GlobalPortfolioRanking | None = None,
) -> tuple[list[EvaluatedOpportunity], dict[str, dict[str, Any]], dict[str, Any]]:
    """Deterministically apply buyer memos, portfolio roles, and zero-loss global ranking."""
    by_id: dict[str, EvaluatedOpportunity] = {ev.seed.opp_id: ev for ev in pool}
    sector_rank_lookup: dict[str, int] = {}
    storm_memos: dict[str, dict[str, Any]] = {}

    for rev in sector_reviews.values():
        for item in rev.ranked_reviews:
            ev = by_id.get(item.opp_id)
            if ev is None:
                continue  # ignore hallucinated opp_ids cleanly
            memo = OpportunityStormMemo(
                opp_id=item.opp_id,
                buyer_assessments=item.buyer_assessments,
                sharpest_pain_point_summary=item.sharpest_pain_point_summary,
                key_localization_or_export_moat=item.key_localization_or_export_moat,
            )
            updated_seed = ev.seed.model_copy(update={"portfolio_role": item.portfolio_role})
            by_id[item.opp_id] = ev.model_copy(update={"seed": updated_seed, "storm_memo": memo})
            storm_memos[item.opp_id] = memo.model_dump()
            sector_rank_lookup[item.opp_id] = item.sector_rank

    # Determine canonical ordered_opp_ids with ZERO drops, ZERO duplicates, ZERO hallucinations
    ordered_ids: list[str] = []
    seen: set[str] = set()

    if global_ranking is not None:
        for oid in global_ranking.ordered_opp_ids:
            if oid in by_id and oid not in seen:
                seen.add(oid)
                ordered_ids.append(oid)
    elif len(sector_reviews) == 1:
        only_rev = next(iter(sector_reviews.values()))
        for item in sorted(only_rev.ranked_reviews, key=lambda x: x.sector_rank):
            if item.opp_id in by_id and item.opp_id not in seen:
                seen.add(item.opp_id)
                ordered_ids.append(item.opp_id)

    # Deterministic fallback for any valid candidate omitted by LLM
    leftovers = [
        ev for oid, ev in by_id.items() if oid not in seen
    ]
    leftovers.sort(
        key=lambda e: (
            sector_rank_lookup.get(e.seed.opp_id, 9999),
            -e.weighted_pillar_score,
            e.roi.payback_months,
        )
    )
    for ev in leftovers:
        seen.add(ev.seed.opp_id)
        ordered_ids.append(ev.seed.opp_id)

    ranked_pool: list[EvaluatedOpportunity] = []
    for idx, oid in enumerate(ordered_ids, start=1):
        ev = by_id[oid]
        ranked_pool.append(ev.model_copy(update={"composite_rank": idx}))

    thesis = (
        global_ranking.executive_ranking_thesis
        if global_ranking is not None
        else next(iter(sector_reviews.values())).portfolio_synthesis
        if sector_reviews
        else ""
    )
    synergies = list(global_ranking.cross_sector_synergies) if global_ranking is not None else []
    normalized_global = GlobalPortfolioRanking(
        executive_ranking_thesis=thesis,
        ordered_opp_ids=ordered_ids,
        cross_sector_synergies=synergies,
    ).model_dump()

    return ranked_pool, storm_memos, normalized_global


async def node_sector_portfolio_reviewer(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Run holistic sector-level buyer-committee stress-test & cross-sector portfolio ranking."""
    raw_pool = state.get("evaluated_opportunities", []) or []
    if not raw_pool:
        return {
            "evaluated_opportunities": [],
            "storm_memos": {},
            "portfolio_reviews": {},
            "global_portfolio_ranking": {
                "executive_ranking_thesis": "",
                "ordered_opp_ids": [],
                "cross_sector_synergies": [],
            },
            "telemetry_events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "node": "sector_portfolio_reviewer",
                    "sectors_reviewed": 0,
                    "opportunities_ranked": 0,
                }
            ],
        }

    pool = [EvaluatedOpportunity.model_validate(e) for e in raw_pool]
    all_records = deps.vault.list_all()

    grouped: dict[Literal["power_energy", "semiconductor"], list[EvaluatedOpportunity]] = {}
    for ev in pool:
        grouped.setdefault(ev.seed.sector, []).append(ev)

    async def _review_sector(
        sec: Literal["power_energy", "semiconductor"],
        sec_opps: list[EvaluatedOpportunity],
    ) -> tuple[str, SectorPortfolioReview]:
        prompt = build_sector_portfolio_prompt(sec, sec_opps, all_records)
        async with deps.semaphore:
            rev = await deps.llm.complete_structured(
                tier="producer",
                node=f"portfolio_review_{sec}",
                system_prompt=PORTFOLIO_COMMITTEE_SYSTEM,
                user_prompt=prompt,
                schema=SectorPortfolioReview,
                max_tokens=6400,
            )
        return sec, rev

    sector_pairs = await asyncio.gather(
        *[_review_sector(sec, opps) for sec, opps in grouped.items()]
    )
    sector_reviews: dict[str, SectorPortfolioReview] = dict(sector_pairs)

    by_id = {ev.seed.opp_id: ev for ev in pool}
    global_ranking: GlobalPortfolioRanking | None = None
    if len(sector_reviews) > 1:
        g_prompt = build_global_ranking_prompt(sector_reviews, by_id)
        async with deps.semaphore:
            global_ranking = await deps.llm.complete_structured(
                tier="producer",
                node="global_portfolio_ranker",
                system_prompt=GLOBAL_PORTFOLIO_RANK_SYSTEM,
                user_prompt=g_prompt,
                schema=GlobalPortfolioRanking,
                max_tokens=2400,
            )

    ranked_pool, storm_memos, normalized_global = apply_portfolio_reviews_and_rank(
        pool, sector_reviews, global_ranking
    )

    return {
        "evaluated_opportunities": [e.model_dump() for e in ranked_pool],
        "storm_memos": storm_memos,
        "portfolio_reviews": {k: v.model_dump() for k, v in sector_reviews.items()},
        "global_portfolio_ranking": normalized_global,
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "sector_portfolio_reviewer",
                "sectors_reviewed": len(sector_reviews),
                "opportunities_ranked": len(ranked_pool),
                "global_rank_called": global_ranking is not None,
            }
        ],
    }
