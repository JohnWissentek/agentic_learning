"""Stage 2: Deterministic [MKT-CALC]+[ROI-CALC] Funnel + Single Flagship Global Portfolio Arbitrator.

Replaces legacy 10x flash STORM panels + 10x flash Swiss Elo matches with ONE unified
flagship arbitration pass that deduplicates overlapping wedges, ranks globally on a single
0-100 scale, and produces a zero-truncation 4-persona x delivery-track buyer matrix.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.prompts import GLOBAL_PORTFOLIO_ARBITRATOR_SYSTEM
from vf_ccus_workflow.schemas import (
    ChinaCCUSProjectItem,
    ChinaMarketSizingSummary,
    CommercialWedgeCandidate,
    CompetitorProfile,
    EvaluatedWedge,
    PACIntegratorProfile,
    PortfolioArbitrationOutput,
    SegmentSizingInput,
    WorkflowState,
)
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    compute_china_tam_sam_som,
    format_eliminated_table,
    format_market_sizing_table,
    format_roi_table,
    screen_wedge_pool,
)


def aggregate_catalogs_and_screen(
    dossiers: list[dict[str, Any]],
    *,
    competitive_dossiers: list[dict[str, Any]] | None = None,
    discovery_scope: dict[str, Any],
    contract: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    """Deterministic Stage 2 aggregation of projects, competitors, PAC integrators, [MKT-CALC], and [ROI-CALC]."""
    proj_map: dict[str, ChinaCCUSProjectItem] = {}
    comp_map: dict[str, CompetitorProfile] = {}
    pac_map: dict[str, PACIntegratorProfile] = {}
    barriers: list[str] = []
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

    for cd in competitive_dossiers or []:
        for c in cd.get("competitors", []):
            comp = CompetitorProfile.model_validate(c)
            comp_map.setdefault(comp.vendor_name.strip(), comp)
        for pac in cd.get("pac_integrators", []):
            p_obj = PACIntegratorProfile.model_validate(pac)
            pac_map.setdefault(p_obj.company_name.strip(), p_obj)
        for b in cd.get("design_institute_spec_barriers", []):
            b_str = str(b).strip()
            if b_str and b_str not in barriers:
                barriers.append(b_str)

    sizing_cfg = discovery_scope.get("china_market_sizing_guardrails", {}) or {}
    market_summary = compute_china_tam_sam_som(
        sizing_list,
        asp_map=sizing_cfg.get("asp_by_track_cny_wan"),
        scenario_multipliers=sizing_cfg.get("scenario_multipliers"),
        win_rate_multipliers=sizing_cfg.get("win_rate_multipliers"),
    )

    funnel_cfg = contract.get("discovery_funnel", {}) or {}
    # Allow slightly wider pre-arbitration pool so GlobalPortfolioArbitrator can deduplicate cleanly
    target_total = int(
        funnel_cfg.get("finalist_shortlist_flagship", 8) + 4
        if profile == "flagship"
        else funnel_cfg.get("finalist_shortlist_fast", 5) + 3
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
        "pac_integrators": [p.model_dump() for p in pac_map.values()],
        "design_institute_barriers": barriers,
        "market_sizing_summary": market_summary.model_dump(),
        "shortlist": [e.model_dump() for e in shortlist],
        "eliminated": [el.model_dump() for el in eliminated],
    }


def apply_portfolio_arbitration(
    shortlist_dicts: list[dict[str, Any]],
    arbitration: PortfolioArbitrationOutput,
    *,
    max_finalists: int = 8,
) -> list[dict[str, Any]]:
    """Deterministically apply GlobalPortfolioArbitrator deduplication & unified ranking."""
    by_id: dict[str, EvaluatedWedge] = {}
    for item in shortlist_dicts:
        ev = EvaluatedWedge.model_validate(item)
        by_id[ev.seed.wedge_id] = ev

    ranked_output: list[EvaluatedWedge] = []
    consumed_ids: set[str] = set()

    for dec in sorted(arbitration.deduped_ranked_wedges, key=lambda x: x.final_rank):
        canon_id = dec.canonical_wedge_id.strip()
        valid_merged = [
            mid for mid in dec.merged_from_wedge_ids if mid in by_id and mid not in consumed_ids
        ]
        # If the arbitrator invented a new merged alias (e.g. W_T1_PIPE_EOR_QAS) while listing
        # valid source IDs in merged_from_wedge_ids, anchor to valid_merged[0] instead of dropping!
        if canon_id in by_id and canon_id not in consumed_ids:
            anchor_id = canon_id
        elif valid_merged:
            anchor_id = valid_merged[0]
        else:
            continue

        ev = by_id[anchor_id]
        merged_ids = list(dict.fromkeys([anchor_id, *valid_merged]))
        consumed_ids.update(merged_ids)

        # Merge verified evidence_ids from merged duplicate wedges
        merged_ev_ids = list(dict.fromkeys(eid for mid in merged_ids for eid in by_id[mid].seed.evidence_ids))
        updated_seed = ev.seed.model_copy(update={"evidence_ids": merged_ev_ids})
        ranked_output.append(
            ev.model_copy(
                update={
                    "seed": updated_seed,
                    "global_priority_score": round(dec.global_priority_score, 2),
                    "merged_from_wedge_ids": merged_ids,
                    "ranking_rationale": dec.ranking_rationale,
                }
            )
        )

    # Fallback: preserve any unconsumed survivors only if arbitration returned fewer items than expected
    if not ranked_output:
        ranked_output = list(by_id.values())

    ranked_output = ranked_output[:max_finalists]
    for idx, ev in enumerate(ranked_output, start=1):
        ev.composite_rank = idx
    return [e.model_dump() for e in ranked_output]


def build_executive_fact_sheet(
    *,
    market_sizing_summary: dict[str, Any],
    evaluated_wedges: list[dict[str, Any]],
    eliminated_wedges: list[dict[str, Any]],
    arbitration: dict[str, Any],
    projects: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    pac_integrators: list[dict[str, Any]],
    design_institute_barriers: list[str],
) -> str:
    """Build the single read-only Executive Fact Sheet shared verbatim by all 5 Full & Executive volumes."""
    mkt = ChinaMarketSizingSummary.model_validate(market_sizing_summary)
    mkt_md = format_market_sizing_table(mkt)
    roi_md = format_roi_table(evaluated_wedges)
    elim_md = format_eliminated_table(eliminated_wedges)

    buyer_matrix = arbitration.get("track_buyer_matrix", [])
    thesis = arbitration.get("executive_synthesis_thesis", "")
    matrix_lines = ["### 买方委员会四角色 × 交付轨道综合阻力与破局矩阵（全量零截断）", ""]
    for card in buyer_matrix:
        matrix_lines.append(
            f"#### {card.get('scenario_group', '')} (`{card.get('delivery_track', '')}`)"
        )
        for pc in card.get("persona_critiques", []):
            matrix_lines.append(
                f"- **{pc.get('persona_role')}** [{pc.get('verdict')}]: "
                f"核心关切={pc.get('primary_concern')} | 采购/规范壁垒={pc.get('procurement_or_spec_barrier')} | "
                f"V&F破局钩子={pc.get('vf_winning_hook')}"
            )
        matrix_lines.append(f"- **GTM共识启示**：{card.get('consensus_gtm_implication', '')}\n")

    proj_lines = [
        "### 已核验中国项目图谱 (Verified Projects)",
        "| 项目名称 | 业主/EPC | 区域 | 赛道 | 规模 | 2026状态 | 交付轨道 | 依据ID |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for p in projects:
        evs = ", ".join(p.get("evidence_ids", [])[:5])
        proj_lines.append(
            f"| {p.get('project_name')} | {p.get('owner_and_epc')} | {p.get('province_or_region')} | "
            f"{p.get('sector')} | {p.get('capacity_mtpa_or_scale')} | {p.get('status_2026')} | "
            f"`{p.get('recommended_delivery_track')}` | {evs} |"
        )

    comp_lines = [
        "### 已核验国内外竞品图谱 (Verified Competitors)",
        "| 厂商 | 类别 | 核验型号/技术 | 相对V&F核心盲区 | V&F制胜策略 | 依据ID |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for c in competitors:
        evs = ", ".join(c.get("evidence_ids", [])[:5])
        comp_lines.append(
            f"| {c.get('vendor_name')} | {c.get('origin_category')} | {c.get('verified_models_and_tech')} | "
            f"{c.get('blind_spots_vs_vf_imr_ms')} | {c.get('win_strategy_for_vf')} | {evs} |"
        )

    pac_block = json.dumps(
        {
            "pac_integrators": pac_integrators,
            "design_institute_barriers": design_institute_barriers,
        },
        ensure_ascii=False,
    )

    return (
        f"## 全局裁决核心论点\n{thesis}\n\n"
        f"{mkt_md}\n\n"
        f"{roi_md}\n\n"
        f"{elim_md}\n\n"
        + "\n".join(matrix_lines)
        + "\n"
        + "\n".join(proj_lines)
        + "\n\n"
        + "\n".join(comp_lines)
        + "\n\n### 本土防爆分析小屋 PAC 集成商与设计院 Spec-in 壁垒\n"
        + pac_block
    )


async def node_size_screen_and_arbitrate(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 2: Deterministic [MKT-CALC]+[ROI-CALC] Funnel -> Single Flagship Global Portfolio Arbitrator."""
    profile = state.get("profile", "flagship")
    agg = aggregate_catalogs_and_screen(
        state.get("track_dossiers", []),
        competitive_dossiers=state.get("competitive_dossiers", []),
        discovery_scope=deps.settings.discovery_scope,
        contract=deps.settings.contract,
        profile=profile,
    )
    shortlist = agg["shortlist"]

    funnel_cfg = deps.settings.contract.get("discovery_funnel", {}) or {}
    max_finalists = int(
        funnel_cfg.get("finalist_shortlist_flagship", 8)
        if profile == "flagship"
        else funnel_cfg.get("finalist_shortlist_fast", 5)
    )

    candidate_cards = []
    for item in shortlist:
        s = item["seed"]
        r = item["roi"]
        cons = (item.get("roi_range") or {}).get("conservative") or r
        candidate_cards.append(
            {
                "wedge_id": s["wedge_id"],
                "track_id": s["track_id"],
                "sector": s["sector"],
                "horizon": s["horizon"],
                "delivery_track": s["delivery_track"],
                "title": s["title"],
                "china_priority_score": s["china_priority_score"],
                "vf_moat_score": s["vf_moat_score"],
                "weighted_pillar_score": item["weighted_pillar_score"],
                "pain_point": s["chemical_pain_point_and_imr_advantage"],
                "sku": s["recommended_vf_sku_and_localization"],
                "roi_baseline": {
                    "capex_wan": round(r["capex_cny"] / 10000, 1),
                    "payback_months": r["payback_months"],
                    "irr_5yr_pct": r["irr_5yr_pct"],
                    "npv_5yr_wan": round(r["npv_5yr_cny"] / 10000, 1),
                    "conservative_payback_months": cons["payback_months"],
                },
                "evidence_ids": s["evidence_ids"],
            }
        )

    prompt = (
        f"Perform global deduplication, unified 0-100 ranking (top {max_finalists} non-overlapping canonical wedges), "
        f"and a consolidated 4-persona Chinese buyer resistance matrix across delivery tracks.\n\n"
        f"=== SURVIVING CANDIDATE WEDGES (WITH DETERMINISTIC [ROI-CALC]) ===\n"
        f"{json.dumps(candidate_cards, ensure_ascii=False, indent=2)}\n\n"
        f"=== COMPETITIVE & PAC CONTEXT ===\n"
        f"{json.dumps({'competitors': agg['competitors'][:12], 'pac_integrators': agg['pac_integrators'], 'barriers': agg['design_institute_barriers']}, ensure_ascii=False, indent=2)}"
    )

    arbitration = await deps.llm.complete_structured(
        tier="producer",
        node="global_portfolio_arbitrator",
        system_prompt=GLOBAL_PORTFOLIO_ARBITRATOR_SYSTEM,
        user_prompt=prompt,
        schema=PortfolioArbitrationOutput,
        max_tokens=5600,
    )

    final_wedges = apply_portfolio_arbitration(
        shortlist, arbitration, max_finalists=max_finalists
    )
    arb_dict = arbitration.model_dump()
    fact_sheet = build_executive_fact_sheet(
        market_sizing_summary=agg["market_sizing_summary"],
        evaluated_wedges=final_wedges,
        eliminated_wedges=agg["eliminated"],
        arbitration=arb_dict,
        projects=agg["projects"],
        competitors=agg["competitors"],
        pac_integrators=agg["pac_integrators"],
        design_institute_barriers=agg["design_institute_barriers"],
    )

    return {
        "china_projects_catalog": agg["projects"],
        "competitors_catalog": agg["competitors"],
        "pac_integrators_catalog": agg["pac_integrators"],
        "design_institute_barriers": agg["design_institute_barriers"],
        "market_sizing_summary": agg["market_sizing_summary"],
        "evaluated_wedges": final_wedges,
        "eliminated_wedges": agg["eliminated"],
        "portfolio_arbitration": arb_dict,
        "executive_fact_sheet": fact_sheet,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "size_screen_and_arbitrate",
                "pre_dedup_shortlist": len(shortlist),
                "post_dedup_finalists": len(final_wedges),
                "eliminated_count": len(agg["eliminated"]),
                "projects_cataloged": len(agg["projects"]),
                "competitors_cataloged": len(agg["competitors"]),
                "pac_integrators_cataloged": len(agg["pac_integrators"]),
            }
        ],
    }
