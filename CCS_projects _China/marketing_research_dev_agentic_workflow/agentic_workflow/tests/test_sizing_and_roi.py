"""Tests for deterministic Python [MKT-CALC] and [ROI-CALC] PALMs engines."""

from __future__ import annotations

from vf_ccus_workflow.schemas import CommercialWedgeCandidate, ROIInputs, SegmentSizingInput
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    compute_china_tam_sam_som,
    compute_roi_metrics,
    screen_wedge_pool,
)


def test_china_tam_sam_som_deterministic_math() -> None:
    inputs = [
        SegmentSizingInput(
            sector="S1_pipeline_ship_eor",
            horizon="2026-2030",
            addressable_project_or_line_count=12,
            stations_per_project=2.0,
            primary_delivery_track="TRACK_B_LOCALIZED_QAS",
            technical_fit_ratio=0.75,
            realistic_som_win_rate=0.25,
            evidence_ids=["EV-CN-001", "EV-SIGGI-005"],
        ),
        SegmentSizingInput(
            sector="S2_green_methanol_ccu_chem",
            horizon="2031-2036",
            addressable_project_or_line_count=30,
            stations_per_project=1.5,
            primary_delivery_track="TRACK_B_LOCALIZED_QAS",
            technical_fit_ratio=0.80,
            realistic_som_win_rate=0.20,
            evidence_ids=["EV-CN-002"],
        ),
    ]
    summary = compute_china_tam_sam_som(inputs)
    assert len(summary.segments) == 2
    seg0 = summary.segments[0]
    assert seg0.baseline.tam_units == 24
    assert seg0.baseline.tam_cny_wan == 24 * 420.0
    assert seg0.baseline.sam_units == 18
    assert seg0.baseline.som_units == 4  # round(18 * 0.25) -> 4 in Python banker's rounding
    assert seg0.conservative.som_cny_wan <= seg0.baseline.som_cny_wan <= seg0.optimistic.som_cny_wan
    assert summary.grand_total_10yr_baseline_som_cny_wan > 0


def test_roi_metrics_and_funnel_eliminates_pseudo_demand() -> None:
    strong_roi = compute_roi_metrics(
        ROIInputs(
            capex_cny=4_200_000,
            avoided_corrosion_and_shutdown_loss_cny_yr=1_800_000,
            avoided_catalyst_poison_or_flaring_cny_yr=600_000,
            avoided_manual_lab_and_multi_gc_opex_cny_yr=350_000,
            ccer_or_export_compliance_upside_cny_yr=250_000,
            annual_opex_cny_yr=260_000,
        )
    )
    assert strong_roi.net_annual_cashflow_cny == 2_740_000.0
    assert 18.0 < strong_roi.payback_months < 19.0
    assert strong_roi.npv_5yr_cny > 0
    assert strong_roi.irr_5yr_pct > 40.0

    # Candidate pool with one strong EOR pipeline wedge and one pseudo-demand food CO2 wedge
    cands = [
        CommercialWedgeCandidate(
            wedge_id="W-EOR-PIPE",
            track_id="T1",
            sector="S1_pipeline_ship_eor",
            horizon="2026-2030",
            delivery_track="TRACK_B_LOCALIZED_QAS",
            title="百万吨级EOR酸性超临界管道VF-QAS-CN腐蚀门禁",
            verdict="GO_HIGH_PRIORITY",
            china_priority_score=94.0,
            vf_moat_score=95.0,
            target_process_point="增压站出口超临界CO2干线总管",
            chemical_pain_point_and_imr_advantage="1s监测H2S+NOx+SOx+O2自由基链式点蚀",
            recommended_vf_sku_and_localization="VF-QAS-CN双轨本土化小屋",
            key_competing_alternatives="Thermo MAX-iR / 离线GC",
            roi_baseline=ROIInputs(
                capex_cny=4_200_000,
                avoided_corrosion_and_shutdown_loss_cny_yr=1_800_000,
                avoided_catalyst_poison_or_flaring_cny_yr=700_000,
                avoided_manual_lab_and_multi_gc_opex_cny_yr=350_000,
                ccer_or_export_compliance_upside_cny_yr=250_000,
                annual_opex_cny_yr=250_000,
            ),
            evidence_ids=["EV-SIGGI-002", "EV-CN-001"],
        ),
        CommercialWedgeCandidate(
            wedge_id="W-FOOD-CTRL",
            track_id="T6",
            sector="S4_food_beverage_dryice",
            horizon="2026-2030",
            delivery_track="TRACK_A_IMPORTED_CORE",
            title="传统饮料级CO2离线抽检替代（低支付意愿对照）",
            verdict="DEPRIORITIZE_OR_PSEUDO_DEMAND",
            china_priority_score=40.0,
            vf_moat_score=70.0,
            target_process_point="食品CO2槽车充装抽检",
            chemical_pain_point_and_imr_advantage="ISBT痕量硫/苯，但国内无强监管在线买单意愿",
            recommended_vf_sku_and_localization="Track A CO2Sense",
            key_competing_alternatives="离线人工气相色谱",
            roi_baseline=ROIInputs(
                capex_cny=1_800_000,
                avoided_corrosion_and_shutdown_loss_cny_yr=100_000,
                avoided_catalyst_poison_or_flaring_cny_yr=150_000,
                avoided_manual_lab_and_multi_gc_opex_cny_yr=120_000,
                ccer_or_export_compliance_upside_cny_yr=50_000,
                annual_opex_cny_yr=180_000,
            ),
            evidence_ids=["EV-SIGGI-003"],
        ),
    ]
    shortlist, eliminated = screen_wedge_pool(cands, target_total=5, max_conservative_payback_months=42.0)
    assert len(shortlist) == 1
    assert shortlist[0].seed.wedge_id == "W-EOR-PIPE"
    assert len(eliminated) == 1
    assert eliminated[0].wedge_id == "W-FOOD-CTRL"
