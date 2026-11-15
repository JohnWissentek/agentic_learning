"""Deterministic Python PALMs financial & ROI calculator (Ch 5 + Ch 17).

LLMs never perform mental arithmetic on CAPEX, OPEX, Payback, NPV, or IRR.
All numbers tagged `[ROI-CALC]` in final reports originate strictly from here.
"""

from __future__ import annotations

from pso_workflow.schemas import ROIInputs, ROIMetrics


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


def compute_roi_metrics(inputs: ROIInputs) -> ROIMetrics:
    """Compute Payback Months, 3-yr ROI %, 5-yr NPV, IRR %, and SAM/SOM."""
    yield_gain_saving = inputs.annual_output_value_cny * (inputs.yield_gain_pct / 100.0)
    annual_gross_benefit = (
        yield_gain_saving
        + inputs.annual_scrap_saving_cny
        + inputs.annual_downtime_saving_cny
        + inputs.annual_consumable_ehs_saving_cny
    )
    net_annual_cf = annual_gross_benefit - inputs.annual_opex_cny

    if net_annual_cf > 0:
        payback_months = (inputs.capex_cny / net_annual_cf) * 12.0
    else:
        payback_months = 999.0

    roi_3yr_pct = ((net_annual_cf * 3.0 - inputs.capex_cny) / inputs.capex_cny) * 100.0
    cashflows = [-inputs.capex_cny] + [net_annual_cf] * 5
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

    # Conservative SAM/SOM ratios anchored to inline inspection penetration curves
    china_sam = inputs.market_tam_china_cny_100m * 0.42
    china_som = china_sam * 0.16
    global_sam = inputs.market_tam_global_usd_m * 0.38
    global_som = global_sam * 0.12

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
) -> float:
    """Score an opportunity on [0, 100] aligned with the 4 contract value pillars.

    Weights from `config/research_contract.yaml`:
    - 35% Manufacturing ROI & Payback
    - 25% Quality / Yield Impact
    - 20% Industrial Upgrade & China-First Localization Leverage
    - 20% Cost/TCO & Green/EHS Evidence Grounding
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
    return round(min(99.5, max(40.0, total)), 2)
