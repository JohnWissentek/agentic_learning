"""Deterministic Python PALMs financial & ROI calculator (Ch 5 + Ch 17).

LLMs never perform mental arithmetic on CAPEX, OPEX, Payback, NPV, or IRR.
All numbers tagged `[ROI-CALC]` in final reports originate strictly from here.
"""

from __future__ import annotations

from typing import Any

from pso_workflow.schemas import (
    EliminatedCandidate,
    EvaluatedOpportunity,
    RangeROIMetrics,
    ROIInputs,
    ROIMetrics,
    ROIRangeInputs,
    TechOpportunitySeed,
)


def _clamp_val(value: float, lo: float | None, hi: float | None) -> float:
    out = float(value)
    if lo is not None:
        out = max(float(lo), out)
    if hi is not None:
        out = min(float(hi), out)
    return out


def _npv(rate: float, cashflows: list[float]) -> float:
    return sum(cf / ((1.0 + rate) ** t) for t, cf in enumerate(cashflows))


def _irr_bisection(cashflows: list[float]) -> float:
    """Solve 5-year IRR robustly via bisection over [-0.90, 5.00]."""
    if cashflows[0] >= 0:
        return 0.0
    if sum(cashflows[1:]) <= abs(cashflows[0]):
        # Negative net return overall -> return bounded negative rate estimate
        total_in = sum(cashflows[1:])
        return max(-90.0, ((total_in / abs(cashflows[0])) - 1.0) * 100.0)

    low, high = -0.90, 5.00
    for _ in range(80):
        mid = (low + high) / 2.0
        val = _npv(mid, cashflows)
        if val > 0:
            low = mid
        else:
            high = mid
    return ((low + high) / 2.0) * 100.0


def compute_roi_metrics(
    inputs: ROIInputs,
    *,
    commercial_status: str | None = None,
) -> ROIMetrics:
    """Compute calibrated industrial Payback Months, 3-yr ROI %, 5-yr NPV, IRR %, and SAM/SOM.

    Industrial CFO calibration (V4.0):
    - `yield_gain_saving` applies `unit_margin_or_scrap_ratio` and `instrument_attribution_share`
      instead of treating 100% of gross line revenue uplift as pure net profit.
    - Year-1 cashflow accounts for `first_year_ramp_factor` (6-12m factory qualification ramp).
    """
    yield_gain_saving = (
        inputs.annual_output_value_cny
        * (inputs.yield_gain_pct / 100.0)
        * inputs.unit_margin_or_scrap_ratio
        * inputs.instrument_attribution_share
    )
    annual_gross_benefit = (
        yield_gain_saving
        + inputs.annual_scrap_saving_cny
        + inputs.annual_downtime_saving_cny
        + inputs.annual_consumable_ehs_saving_cny
    )
    net_annual_cf = annual_gross_benefit - inputs.annual_opex_cny
    year1_net_cf = annual_gross_benefit * inputs.first_year_ramp_factor - inputs.annual_opex_cny

    if net_annual_cf <= 0:
        payback_months = 999.0
    elif year1_net_cf >= inputs.capex_cny:
        payback_months = (inputs.capex_cny / year1_net_cf) * 12.0
    else:
        remaining_after_y1 = inputs.capex_cny - year1_net_cf
        payback_months = 12.0 + (remaining_after_y1 / net_annual_cf) * 12.0

    cum_3yr_cf = year1_net_cf + net_annual_cf * 2.0
    roi_3yr_pct = ((cum_3yr_cf - inputs.capex_cny) / inputs.capex_cny) * 100.0
    cashflows = [-inputs.capex_cny, year1_net_cf] + [net_annual_cf] * 4
    npv_5yr = _npv(inputs.wacc, cashflows)
    irr_5yr_pct = _irr_bisection(cashflows)

    if payback_months <= 12.0:
        tier = "Tier-A (<=12m Ultra-High ROI)"
    elif payback_months <= 24.0:
        tier = "Tier-B (12-24m Strong ROI)"
    elif payback_months <= 42.0:
        tier = "Tier-C (24-42m Strategic Upgrade)"
    else:
        tier = "Tier-D (>42m Long Horizon)"

    # Explicit commercial-status penetration assumptions (transparent & auditable)
    penetration_map = {
        "overseas_only_cn_blank": (0.45, 0.18, 0.36, 0.10),
        "global_and_cn_true_blank": (0.35, 0.20, 0.35, 0.15),
        "global_and_cn_commercialized": (0.48, 0.10, 0.42, 0.08),
    }
    cn_sam_r, cn_som_r, gl_sam_r, gl_som_r = penetration_map.get(
        commercial_status or "", (0.42, 0.16, 0.38, 0.12)
    )
    china_sam = inputs.market_tam_china_cny_100m * cn_sam_r
    china_som = china_sam * cn_som_r
    global_sam = inputs.market_tam_global_usd_m * gl_sam_r
    global_som = global_sam * gl_som_r

    return ROIMetrics(
        capex_cny=round(inputs.capex_cny, 2),
        annual_opex_cny=round(inputs.annual_opex_cny, 2),
        yield_gain_saving_cny=round(yield_gain_saving, 2),
        annual_gross_benefit_cny=round(annual_gross_benefit, 2),
        net_annual_cashflow_cny=round(net_annual_cf, 2),
        payback_months=round(payback_months, 1),
        roi_3yr_pct=round(roi_3yr_pct, 1),
        npv_5yr_cny=round(npv_5yr, 2),
        irr_5yr_pct=round(irr_5yr_pct, 1),
        payback_tier=tier,
        china_sam_cny_100m=round(china_sam, 2),
        china_som_3_5y_cny_100m=round(china_som, 2),
        global_sam_usd_m=round(global_sam, 2),
        global_som_5_10y_usd_m=round(global_som, 2),
    )


def compute_weighted_pillar_score(
    *,
    roi: ROIMetrics,
    china_priority: float,
    global_priority: float,
    horizon: str,
    evidence_count: int,
    commercial_status: str | None = None,
    has_ai_co_design: bool = False,
) -> float:
    """Score an opportunity on [0, 100] aligned with the 4 contract value pillars.

    Weights from `config/research_contract.yaml`:
    - 35% Manufacturing ROI & Payback
    - 25% Quality / Yield Impact
    - 20% Industrial Upgrade & China-First Localization Leverage
    - 20% Cost/TCO & Green/EHS Evidence Grounding

    In V3.0, optional `commercial_status` & `has_ai_co_design` apply bounded white-space
    and AI-moat prioritization adjustments without perturbing unit callers that omit them.
    """
    # Payback component (<=6m -> 100, 12m -> 90, 24m -> 72, 36m -> 55, >=48m -> 35)
    pb = roi.payback_months
    if pb <= 6.0:
        roi_score = 98.0
    elif pb <= 12.0:
        roi_score = 98.0 - (pb - 6.0) * 1.3
    elif pb <= 24.0:
        roi_score = 90.0 - (pb - 12.0) * 1.5
    elif pb <= 42.0:
        roi_score = 72.0 - (pb - 24.0) * 1.1
    else:
        roi_score = 45.0

    # Yield component scaled by annual yield saving relative to CAPEX
    yield_ratio = min(2.5, roi.yield_gain_saving_cny / max(1.0, roi.capex_cny))
    yield_score = min(100.0, 58.0 + yield_ratio * 18.0)

    # Industrial upgrade & China-first + Global expansion score
    upgrade_score = china_priority * 0.65 + global_priority * 0.35
    if horizon == "5-10y":
        upgrade_score = min(100.0, upgrade_score + 2.5)

    # Evidence grounding + TCO/EHS composite
    ev_bonus = min(100.0, 68.0 + min(evidence_count, 8) * 4.0)

    total = (
        0.35 * roi_score
        + 0.25 * yield_score
        + 0.20 * upgrade_score
        + 0.20 * ev_bonus
    )

    if commercial_status == "overseas_only_cn_blank":
        total += 2.0
    elif commercial_status == "global_and_cn_true_blank":
        total += 2.4 if has_ai_co_design else 1.6
    elif commercial_status == "global_and_cn_commercialized":
        total -= 0.3 if has_ai_co_design else 1.2

    return round(min(99.5, max(40.0, total)), 2)


def clamp_roi_range_inputs(
    rng: ROIRangeInputs,
    sector: str,
    guardrails: dict[str, Any] | None = None,
) -> ROIRangeInputs:
    """Clamp LLM-extracted economic intervals against physical sector guardrails."""
    guard = (guardrails or {}).get(sector, {}) or {}
    if not guard:
        return rng

    cap_lo_b, cap_hi_b = guard.get("capex_cny_min"), guard.get("capex_cny_max")
    out_lo_b, out_hi_b = guard.get("annual_output_value_cny_min"), guard.get("annual_output_value_cny_max")
    yld_lo_b, yld_hi_b = guard.get("yield_gain_pct_min"), guard.get("yield_gain_pct_max")
    opex_r_lo, opex_r_hi = guard.get("opex_ratio_min"), guard.get("opex_ratio_max")
    cn_lo_b, cn_hi_b = guard.get("market_tam_china_cny_100m_min"), guard.get("market_tam_china_cny_100m_max")
    gl_lo_b, gl_hi_b = guard.get("market_tam_global_usd_m_min"), guard.get("market_tam_global_usd_m_max")

    c_lo = _clamp_val(rng.capex_cny_low, cap_lo_b, cap_hi_b)
    c_mid = _clamp_val(rng.capex_cny_base, cap_lo_b, cap_hi_b)
    c_hi = _clamp_val(rng.capex_cny_high, cap_lo_b, cap_hi_b)
    c_lo, c_mid, c_hi = sorted((c_lo, c_mid, c_hi))

    y_lo = _clamp_val(rng.yield_gain_pct_low, yld_lo_b, yld_hi_b)
    y_mid = _clamp_val(rng.yield_gain_pct_base, yld_lo_b, yld_hi_b)
    y_hi = _clamp_val(rng.yield_gain_pct_high, yld_lo_b, yld_hi_b)
    y_lo, y_mid, y_hi = sorted((y_lo, y_mid, y_hi))

    opex_min = c_mid * float(opex_r_lo) if opex_r_lo is not None else 0.0
    opex_max = c_mid * float(opex_r_hi) if opex_r_hi is not None else rng.annual_opex_cny

    return ROIRangeInputs(
        capex_cny_low=c_lo,
        capex_cny_base=c_mid,
        capex_cny_high=c_hi,
        yield_gain_pct_low=y_lo,
        yield_gain_pct_base=y_mid,
        yield_gain_pct_high=y_hi,
        annual_output_value_cny=_clamp_val(rng.annual_output_value_cny, out_lo_b, out_hi_b),
        annual_opex_cny=_clamp_val(rng.annual_opex_cny, opex_min, opex_max),
        annual_scrap_saving_cny=max(0.0, rng.annual_scrap_saving_cny),
        annual_downtime_saving_cny=max(0.0, rng.annual_downtime_saving_cny),
        annual_consumable_ehs_saving_cny=max(0.0, rng.annual_consumable_ehs_saving_cny),
        market_tam_china_cny_100m=_clamp_val(rng.market_tam_china_cny_100m, cn_lo_b, cn_hi_b),
        market_tam_global_usd_m=_clamp_val(rng.market_tam_global_usd_m, gl_lo_b, gl_hi_b),
        parameter_basis=rng.parameter_basis,
        wacc=rng.wacc,
        unit_margin_or_scrap_ratio=_clamp_val(
            rng.unit_margin_or_scrap_ratio,
            guard.get("unit_margin_or_scrap_ratio_min", 0.05),
            guard.get("unit_margin_or_scrap_ratio_max", 0.80),
        ),
        instrument_attribution_share=_clamp_val(
            rng.instrument_attribution_share,
            guard.get("instrument_attribution_share_min", 0.05),
            guard.get("instrument_attribution_share_max", 1.0),
        ),
        first_year_ramp_factor=_clamp_val(
            rng.first_year_ramp_factor,
            guard.get("first_year_ramp_factor_min", 0.20),
            guard.get("first_year_ramp_factor_max", 1.0),
        ),
    )


def derive_range_inputs_from_seed(
    seed: TechOpportunitySeed,
    guardrails: dict[str, Any] | None = None,
) -> ROIRangeInputs:
    """Resolve and clamp ROIRangeInputs whether candidate supplied range or baseline only."""
    if seed.roi_range_inputs is not None:
        rng = seed.roi_range_inputs
    else:
        assert seed.roi_inputs is not None
        base = seed.roi_inputs
        rng = ROIRangeInputs(
            capex_cny_low=round(base.capex_cny * 0.80, 2),
            capex_cny_base=base.capex_cny,
            capex_cny_high=round(base.capex_cny * 1.25, 2),
            yield_gain_pct_low=round(base.yield_gain_pct * 0.75, 4),
            yield_gain_pct_base=base.yield_gain_pct,
            yield_gain_pct_high=round(base.yield_gain_pct * 1.25, 4),
            annual_output_value_cny=base.annual_output_value_cny,
            annual_opex_cny=base.annual_opex_cny,
            annual_scrap_saving_cny=base.annual_scrap_saving_cny,
            annual_downtime_saving_cny=base.annual_downtime_saving_cny,
            annual_consumable_ehs_saving_cny=base.annual_consumable_ehs_saving_cny,
            market_tam_china_cny_100m=base.market_tam_china_cny_100m,
            market_tam_global_usd_m=base.market_tam_global_usd_m,
            parameter_basis="derived ±25% from baseline parameters",
            wacc=base.wacc,
            unit_margin_or_scrap_ratio=base.unit_margin_or_scrap_ratio,
            instrument_attribution_share=base.instrument_attribution_share,
            first_year_ramp_factor=base.first_year_ramp_factor,
        )
    return clamp_roi_range_inputs(rng, seed.sector, guardrails)


def compute_range_roi_metrics(
    rng: ROIRangeInputs,
    *,
    commercial_status: str | None = None,
) -> RangeROIMetrics:
    """Compute conservative / baseline / optimistic ROI envelopes deterministically."""
    conservative_inputs = ROIInputs(
        capex_cny=rng.capex_cny_high,
        annual_opex_cny=round(rng.annual_opex_cny * 1.10, 2),
        annual_output_value_cny=rng.annual_output_value_cny,
        yield_gain_pct=rng.yield_gain_pct_low,
        annual_scrap_saving_cny=round(rng.annual_scrap_saving_cny * 0.80, 2),
        annual_downtime_saving_cny=round(rng.annual_downtime_saving_cny * 0.80, 2),
        annual_consumable_ehs_saving_cny=round(rng.annual_consumable_ehs_saving_cny * 0.80, 2),
        market_tam_china_cny_100m=rng.market_tam_china_cny_100m,
        market_tam_global_usd_m=rng.market_tam_global_usd_m,
        wacc=rng.wacc,
        unit_margin_or_scrap_ratio=rng.unit_margin_or_scrap_ratio,
        instrument_attribution_share=rng.instrument_attribution_share,
        first_year_ramp_factor=max(0.20, round(rng.first_year_ramp_factor * 0.85, 3)),
    )
    optimistic_inputs = ROIInputs(
        capex_cny=rng.capex_cny_low,
        annual_opex_cny=round(rng.annual_opex_cny * 0.95, 2),
        annual_output_value_cny=rng.annual_output_value_cny,
        yield_gain_pct=rng.yield_gain_pct_high,
        annual_scrap_saving_cny=round(rng.annual_scrap_saving_cny * 1.15, 2),
        annual_downtime_saving_cny=round(rng.annual_downtime_saving_cny * 1.15, 2),
        annual_consumable_ehs_saving_cny=round(rng.annual_consumable_ehs_saving_cny * 1.15, 2),
        market_tam_china_cny_100m=rng.market_tam_china_cny_100m,
        market_tam_global_usd_m=rng.market_tam_global_usd_m,
        wacc=rng.wacc,
        unit_margin_or_scrap_ratio=rng.unit_margin_or_scrap_ratio,
        instrument_attribution_share=rng.instrument_attribution_share,
        first_year_ramp_factor=min(1.0, round(rng.first_year_ramp_factor * 1.15, 3)),
    )
    return RangeROIMetrics(
        conservative=compute_roi_metrics(conservative_inputs, commercial_status=commercial_status),
        baseline=compute_roi_metrics(rng.to_baseline_inputs(), commercial_status=commercial_status),
        optimistic=compute_roi_metrics(optimistic_inputs, commercial_status=commercial_status),
        parameter_basis=rng.parameter_basis,
    )


def _to_eliminated(ev: EvaluatedOpportunity, reason: str) -> EliminatedCandidate:
    return EliminatedCandidate(
        opp_id=ev.seed.opp_id,
        track_id=ev.seed.track_id,
        sector=ev.seed.sector,
        title=ev.seed.title,
        horizon=ev.seed.horizon,
        commercial_status=ev.seed.commercial_status,
        baseline_payback_months=ev.roi.payback_months,
        conservative_payback_months=(
            ev.roi_range.conservative.payback_months if ev.roi_range else ev.roi.payback_months
        ),
        weighted_pillar_score=ev.weighted_pillar_score,
        evidence_count=len(ev.seed.evidence_ids),
        elimination_reason=reason,
    )


def screen_candidate_pool(
    candidates: list[TechOpportunitySeed],
    *,
    sector_filter: str = "all",
    guardrails: dict[str, Any] | None = None,
    target_total: int = 16,
    max_conservative_payback_months: float = 42.0,
) -> tuple[list[EvaluatedOpportunity], list[EliminatedCandidate]]:
    """Deterministic Stage 2 PALMs funnel: clamp -> compute 3 scenarios -> hard gates -> balanced shortlist."""
    deduped: dict[str, TechOpportunitySeed] = {}
    for cand in candidates:
        existing = deduped.get(cand.opp_id)
        if existing is None or len(cand.evidence_ids) > len(existing.evidence_ids):
            deduped[cand.opp_id] = cand

    evaluated_all: list[EvaluatedOpportunity] = []
    for cand in deduped.values():
        clamped_rng = derive_range_inputs_from_seed(cand, guardrails=guardrails)
        clean_seed = cand.model_copy(
            update={
                "roi_range_inputs": clamped_rng,
                "roi_inputs": clamped_rng.to_baseline_inputs(),
            }
        )
        roi_range = compute_range_roi_metrics(
            clamped_rng, commercial_status=clean_seed.commercial_status
        )
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
        evaluated_all.append(
            EvaluatedOpportunity(
                seed=clean_seed,
                roi=roi,
                roi_range=roi_range,
                weighted_pillar_score=w_score,
            )
        )

    survivors: list[EvaluatedOpportunity] = []
    eliminated: list[EliminatedCandidate] = []
    for ev in evaluated_all:
        cons_pb = ev.roi_range.conservative.payback_months if ev.roi_range else ev.roi.payback_months
        reasons: list[str] = []
        if len(ev.seed.evidence_ids) == 0:
            reasons.append("缺少经证据库核验的原始引用 ID (evidence_ids=0)")
        if ev.roi.net_annual_cashflow_cny <= 0:
            reasons.append(f"基准情景年净现金流为负 ({ev.roi.net_annual_cashflow_cny:,.0f} CNY)")
        if cons_pb > max_conservative_payback_months:
            reasons.append(
                f"保守情景回收期 {cons_pb:.1f} 个月超过漏斗上限 {max_conservative_payback_months:.1f} 个月"
            )
        if reasons:
            eliminated.append(_to_eliminated(ev, "；".join(reasons)))
        else:
            survivors.append(ev)

    if not survivors and evaluated_all:
        # Safety net: only if every single candidate failed hard gates, promote top cited ones
        fallback_sorted = sorted(
            evaluated_all,
            key=lambda e: (len(e.seed.evidence_ids) > 0, e.weighted_pillar_score),
            reverse=True,
        )
        kept = fallback_sorted[: min(target_total, len(fallback_sorted))]
        kept_ids = {k.seed.opp_id for k in kept}
        survivors = kept
        eliminated = [el for el in eliminated if el.opp_id not in kept_ids]

    def _rank_key(ev: EvaluatedOpportunity) -> tuple[float, float, int]:
        return (ev.weighted_pillar_score, -ev.roi.payback_months, len(ev.seed.evidence_ids))

    survivors.sort(key=_rank_key, reverse=True)

    if sector_filter == "all" and len(survivors) > target_total:
        half = target_total // 2
        power_pool = [e for e in survivors if e.seed.sector == "power_energy"]
        semi_pool = [e for e in survivors if e.seed.sector == "semiconductor"]
        selected = power_pool[:half] + semi_pool[: (target_total - half)]
        selected_ids = {e.seed.opp_id for e in selected}
        if len(selected) < target_total:
            leftovers = [e for e in survivors if e.seed.opp_id not in selected_ids]
            for extra in leftovers[: target_total - len(selected)]:
                selected.append(extra)
                selected_ids.add(extra.seed.opp_id)
        for ev in survivors:
            if ev.seed.opp_id not in selected_ids:
                sector_cn = "电力能源" if ev.seed.sector == "power_energy" else "半导体制造"
                eliminated.append(
                    _to_eliminated(
                        ev,
                        f"Stage 2 赛道平衡名额竞争淘汰：{sector_cn}组加权得分 {ev.weighted_pillar_score:.1f} 未进入前 {half} 名决选池",
                    )
                )
    elif len(survivors) > target_total:
        selected = survivors[:target_total]
        for ev in survivors[target_total:]:
            eliminated.append(
                _to_eliminated(
                    ev,
                    f"Stage 2 综合得分竞争淘汰：加权得分 {ev.weighted_pillar_score:.1f} 未进入前 {target_total} 名决选池",
                )
            )
    else:
        selected = list(survivors)

    selected.sort(key=_rank_key, reverse=True)
    for idx, ev in enumerate(selected, start=1):
        ev.composite_rank = idx

    return selected, eliminated
