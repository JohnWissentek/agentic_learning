"""Deterministic unit tests for PALMs Python ROI calculator and pillar scoring."""

from __future__ import annotations

import pytest

from pso_workflow.schemas import ROIInputs
from pso_workflow.tools.roi_calculator import (
    compute_roi_metrics,
    compute_weighted_pillar_score,
)


def test_compute_roi_metrics_exact_math() -> None:
    inputs = ROIInputs(
        capex_cny=1_200_000,
        annual_opex_cny=100_000,
        annual_output_value_cny=300_000_000,
        yield_gain_pct=0.40,  # 1,200,000 / yr
        annual_scrap_saving_cny=300_000,
        annual_downtime_saving_cny=200_000,
        annual_consumable_ehs_saving_cny=100_000,
        market_tam_china_cny_100m=30.0,
        market_tam_global_usd_m=900.0,
        wacc=0.10,
    )
    m = compute_roi_metrics(inputs)
    assert m.yield_gain_saving_cny == pytest.approx(1_200_000.0)
    assert m.annual_gross_benefit_cny == pytest.approx(1_800_000.0)
    assert m.net_annual_cashflow_cny == pytest.approx(1_700_000.0)
    # 1,200,000 / 1,700,000 * 12 = 8.47 -> 8.5 months
    assert m.payback_months == pytest.approx(8.5)
    assert m.payback_tier == "Tier-A (<=12m Ultra-High ROI)"
    assert m.roi_3yr_pct == pytest.approx(325.0)
    assert m.npv_5yr_cny > 5_000_000.0
    assert m.irr_5yr_pct > 100.0
    assert m.china_sam_cny_100m == pytest.approx(12.6)
    assert m.global_som_5_10y_usd_m == pytest.approx(41.04)


def test_compute_roi_negative_cashflow_edge_case() -> None:
    inputs = ROIInputs(
        capex_cny=2_000_000,
        annual_opex_cny=500_000,
        annual_output_value_cny=10_000_000,
        yield_gain_pct=0.1,  # 10,000
        annual_scrap_saving_cny=50_000,
        annual_downtime_saving_cny=0,
        annual_consumable_ehs_saving_cny=0,
        market_tam_china_cny_100m=5.0,
        market_tam_global_usd_m=100.0,
    )
    m = compute_roi_metrics(inputs)
    assert m.net_annual_cashflow_cny < 0
    assert m.payback_months == 999.0
    assert m.payback_tier == "Tier-D (>42m Long Horizon)"


def test_weighted_pillar_score_bounds() -> None:
    inputs = ROIInputs(
        capex_cny=1_000_000,
        annual_opex_cny=80_000,
        annual_output_value_cny=500_000_000,
        yield_gain_pct=0.5,
        annual_scrap_saving_cny=500_000,
        annual_downtime_saving_cny=200_000,
        annual_consumable_ehs_saving_cny=150_000,
        market_tam_china_cny_100m=25.0,
        market_tam_global_usd_m=800.0,
    )
    roi = compute_roi_metrics(inputs)
    score = compute_weighted_pillar_score(
        roi=roi,
        china_priority=96,
        global_priority=92,
        horizon="3-5y",
        evidence_count=6,
    )
    assert 85.0 <= score <= 99.5
