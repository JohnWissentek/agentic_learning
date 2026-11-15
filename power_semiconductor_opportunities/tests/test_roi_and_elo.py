"""Deterministic unit tests for PALMs Python ROI calculator and pillar scoring."""

from __future__ import annotations

import pytest

from pso_workflow.config import WorkflowSettings
from pso_workflow.schemas import ROIInputs, ROIRangeInputs, TechOpportunitySeed, _coerce_commercial_status
from pso_workflow.tools.roi_calculator import (
    clamp_roi_range_inputs,
    compute_range_roi_metrics,
    compute_roi_metrics,
    compute_weighted_pillar_score,
    screen_candidate_pool,
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


def test_clamp_and_compute_range_roi_metrics() -> None:
    guardrails = WorkflowSettings.load().discovery_scope["sector_roi_guardrails"]
    semi_g = guardrails["semiconductor"]

    out_of_bounds = ROIRangeInputs(
        capex_cny_low=10_000,  # below semiconductor min (300,000)
        capex_cny_base=2_000_000,
        capex_cny_high=4_000_000,
        yield_gain_pct_low=0.15,
        yield_gain_pct_base=0.45,
        yield_gain_pct_high=19.0,  # above semiconductor max (3.5)
        annual_output_value_cny=500_000_000,
        annual_opex_cny=1.0,  # below opex_ratio_min * capex_base
        annual_scrap_saving_cny=250_000,
        annual_downtime_saving_cny=150_000,
        annual_consumable_ehs_saving_cny=80_000,
        market_tam_china_cny_100m=20.0,
        market_tam_global_usd_m=500.0,
        parameter_basis="out-of-bounds test",
    )
    clamped = clamp_roi_range_inputs(out_of_bounds, "semiconductor", guardrails)
    assert clamped.capex_cny_low >= semi_g["capex_cny_min"]
    assert clamped.yield_gain_pct_high <= semi_g["yield_gain_pct_max"]
    assert clamped.annual_opex_cny >= clamped.capex_cny_base * semi_g["opex_ratio_min"] - 1e-6

    env = compute_range_roi_metrics(clamped)
    assert env.optimistic.payback_months <= env.baseline.payback_months <= env.conservative.payback_months
    assert env.optimistic.npv_5yr_cny >= env.baseline.npv_5yr_cny >= env.conservative.npv_5yr_cny


def _make_seed(
    *,
    opp_id: str,
    track_id: str,
    sector: str,
    capex_base: float,
    yield_base: float,
    evidence_ids: list[str],
    output_val: float = 300_000_000.0,
) -> TechOpportunitySeed:
    return TechOpportunitySeed(
        opp_id=opp_id,
        track_id=track_id,
        sector=sector,  # type: ignore[arg-type]
        title=f"{opp_id} Online Metrology System",
        horizon="3-5y",
        china_priority_score=90.0,
        global_priority_score=86.0,
        physics_principle="Inline non-destructive optical/electrical sensing",
        target_process_point="Key process step",
        product_form_factor="Inline sensor module",
        quality_yield_mechanism="Early defect capture",
        cost_tco_mechanism="Reduce scrap",
        green_ehs_mechanism="Reduce waste",
        industrial_upgrade_mechanism="Closed-loop control",
        china_positioning="China Tier-1 fab spec-in",
        global_expansion_path="Export via global standards",
        evidence_ids=evidence_ids,
        roi_range_inputs=ROIRangeInputs(
            capex_cny_low=capex_base * 0.85,
            capex_cny_base=capex_base,
            capex_cny_high=capex_base * 1.20,
            yield_gain_pct_low=yield_base * 0.80,
            yield_gain_pct_base=yield_base,
            yield_gain_pct_high=yield_base * 1.25,
            annual_output_value_cny=output_val,
            annual_opex_cny=capex_base * 0.08,
            annual_scrap_saving_cny=250_000.0,
            annual_downtime_saving_cny=150_000.0,
            annual_consumable_ehs_saving_cny=50_000.0,
            market_tam_china_cny_100m=18.0,
            market_tam_global_usd_m=420.0,
            parameter_basis="unit test synthetic range",
        ),
    )


def test_screen_candidate_pool_funnel_and_elimination() -> None:
    guardrails = WorkflowSettings.load().discovery_scope["sector_roi_guardrails"]
    cands: list[TechOpportunitySeed] = []

    # Invalid candidate 1: zero evidence IDs
    cands.append(
        _make_seed(
            opp_id="DP1-BAD-EV",
            track_id="DP1",
            sector="power_energy",
            capex_base=1_200_000.0,
            yield_base=0.60,
            evidence_ids=[],
        )
    )
    # Invalid candidate 2: slow conservative payback (> 42 months)
    cands.append(
        _make_seed(
            opp_id="DS1-BAD-PB",
            track_id="DS1",
            sector="semiconductor",
            capex_base=25_000_000.0,
            yield_base=0.05,
            evidence_ids=["EV-CN-001"],
            output_val=100_000_000.0,
        )
    )
    # 9 valid power + 9 valid semiconductor candidates
    for i in range(1, 10):
        cands.append(
            _make_seed(
                opp_id=f"DP{(i - 1) % 4 + 1}-O{i}",
                track_id=f"DP{(i - 1) % 4 + 1}",
                sector="power_energy",
                capex_base=900_000.0 + i * 180_000.0,
                yield_base=0.80 - i * 0.04,
                evidence_ids=["EV-CN-001", "EV-GL-001"],
            )
        )
        cands.append(
            _make_seed(
                opp_id=f"DS{(i - 1) % 4 + 1}-O{i}",
                track_id=f"DS{(i - 1) % 4 + 1}",
                sector="semiconductor",
                capex_base=1_400_000.0 + i * 200_000.0,
                yield_base=0.75 - i * 0.03,
                evidence_ids=["EV-CN-002", "EV-GL-002"],
                output_val=420_000_000.0,
            )
        )

    shortlist, eliminated = screen_candidate_pool(
        cands,
        sector_filter="all",
        guardrails=guardrails,
        target_total=16,
        max_conservative_payback_months=42.0,
    )
    assert len(shortlist) == 16
    assert sum(1 for e in shortlist if e.seed.sector == "power_energy") == 8
    assert sum(1 for e in shortlist if e.seed.sector == "semiconductor") == 8
    assert len(eliminated) == 4

    elim_by_id = {el.opp_id: el for el in eliminated}
    assert "DP1-BAD-EV" in elim_by_id
    assert "evidence_ids=0" in elim_by_id["DP1-BAD-EV"].elimination_reason
    assert "DS1-BAD-PB" in elim_by_id
    assert "保守情景回收期" in elim_by_id["DS1-BAD-PB"].elimination_reason
    for el in eliminated:
        assert el.elimination_reason.strip()


def test_v3_commercial_whitespace_and_ai_co_design_scoring() -> None:
    """V3 unit test: white-space coercion, score bonus/penalty calibration, and red-ocean deprioritization."""
    assert _coerce_commercial_status("overseas_only_cn_blank") == "overseas_only_cn_blank"
    assert _coerce_commercial_status("global_and_cn_true_blank") == "global_and_cn_true_blank"
    assert _coerce_commercial_status("global_and_cn_commercialized") == "global_and_cn_commercialized"
    assert _coerce_commercial_status("海内外均属产品空白(未产业化)") == "global_and_cn_true_blank"
    assert _coerce_commercial_status("海外巨头在售但国产空白") == "overseas_only_cn_blank"
    assert _coerce_commercial_status("海内外均已在售红海") == "global_and_cn_commercialized"

    settings = WorkflowSettings.load()
    guardrails = settings.discovery_scope.get("sector_roi_guardrails", {})

    # Verify compute_weighted_pillar_score rewards CN/Global blanks and AI co-design while penalizing red-ocean
    base_metrics = compute_roi_metrics(
        ROIInputs(
            capex_cny=1_200_000,
            annual_opex_cny=100_000,
            annual_output_value_cny=300_000_000,
            yield_gain_pct=0.50,
            annual_scrap_saving_cny=250_000,
            annual_downtime_saving_cny=150_000,
            annual_consumable_ehs_saving_cny=80_000,
            market_tam_china_cny_100m=24.0,
            market_tam_global_usd_m=620.0,
        )
    )
    score_cn_blank = compute_weighted_pillar_score(
        roi=base_metrics,
        china_priority=85.0,
        global_priority=82.0,
        horizon="3-5y",
        evidence_count=3,
        commercial_status="overseas_only_cn_blank",
        has_ai_co_design=True,
    )
    score_red_ocean = compute_weighted_pillar_score(
        roi=base_metrics,
        china_priority=85.0,
        global_priority=82.0,
        horizon="3-5y",
        evidence_count=3,
        commercial_status="global_and_cn_commercialized",
        has_ai_co_design=False,
    )
    score_true_blank_ai = compute_weighted_pillar_score(
        roi=base_metrics,
        china_priority=85.0,
        global_priority=82.0,
        horizon="5-10y",
        evidence_count=3,
        commercial_status="global_and_cn_true_blank",
        has_ai_co_design=True,
    )
    score_true_blank_no_ai = compute_weighted_pillar_score(
        roi=base_metrics,
        china_priority=85.0,
        global_priority=82.0,
        horizon="5-10y",
        evidence_count=3,
        commercial_status="global_and_cn_true_blank",
        has_ai_co_design=False,
    )
    assert score_cn_blank > score_red_ocean
    assert score_true_blank_ai > score_true_blank_no_ai > score_red_ocean

    # Identical ROI candidates: screen_candidate_pool must keep overseas_only_cn_blank and drop commercialized red-ocean
    c_blank = _make_seed(
        opp_id="DS1-BLANK",
        track_id="DS1",
        sector="semiconductor",
        capex_base=1_500_000.0,
        yield_base=0.60,
        evidence_ids=["EV-CN-001", "EV-GL-001"],
        output_val=400_000_000.0,
    ).model_copy(
        update={
            "commercial_status": "overseas_only_cn_blank",
            "ai_computational_sensing_and_co_design": "PINN反演补偿光学阵列降BOM",
            "ai_rd_acceleration_and_edge_deployment": "合成缺陷冷启动+FPGA边缘协同",
        }
    )
    c_red = _make_seed(
        opp_id="DS1-RED",
        track_id="DS1",
        sector="semiconductor",
        capex_base=1_500_000.0,
        yield_base=0.60,
        evidence_ids=["EV-CN-001", "EV-GL-001"],
        output_val=400_000_000.0,
    ).model_copy(update={"commercial_status": "global_and_cn_commercialized"})

    shortlist, eliminated = screen_candidate_pool(
        [c_red, c_blank],
        sector_filter="semiconductor",
        guardrails=guardrails,
        target_total=1,
        max_conservative_payback_months=42.0,
    )
    assert [s.seed.opp_id for s in shortlist] == ["DS1-BLANK"]
    assert len(eliminated) == 1
    assert eliminated[0].opp_id == "DS1-RED"
    assert eliminated[0].commercial_status == "global_and_cn_commercialized"
