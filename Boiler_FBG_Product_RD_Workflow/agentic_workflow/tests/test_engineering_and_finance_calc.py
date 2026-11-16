"""Unit tests for deterministic PALMs physics link budget, dual-track BOM, 5-yr finance & plant ROI."""

from __future__ import annotations

from pathlib import Path

import yaml

from bfbg_workflow.tools.engineering_and_finance_calc import run_all_deterministic_calcs


def _load_catalog() -> dict:
    p = Path(__file__).resolve().parents[1] / "config" / "hardware_and_market_catalog.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_physics_link_budget_and_margins() -> None:
    catalog = _load_catalog()
    bundle = run_all_deterministic_calcs(catalog)
    phy = bundle.physics_link

    assert phy.std_points_per_fiber == 25
    assert phy.pro_wdm_points_per_fiber >= 30
    assert phy.std_snr_margin_db > 15.0
    assert phy.pro_snr_margin_wdm_db > 25.0
    assert phy.pro_snr_margin_uwfbg_db > 15.0
    assert phy.std_collision_margin_nm > 0.0
    assert phy.block_steady_temp_drop_c_at_350kwm2 > 0.0


def test_dual_track_bom_and_financial_scenarios() -> None:
    catalog = _load_catalog()
    bundle = run_all_deterministic_calcs(catalog)

    assert len(bundle.bom_matrix) == 10
    lookup = {(b.config_code, b.supply_track): b for b in bundle.bom_matrix}
    std_a = lookup[("BS-STD-500", "Track_A_Full_Imported")]
    std_b = lookup[("BS-STD-500", "Track_B_Hybrid_Competitive")]
    assert std_b.total_cogs_50u_cny < std_a.total_cogs_50u_cny
    assert std_b.per_point_cogs_50u_cny < 260.0
    assert std_b.gross_margin_50u_pct > 50.0

    fin_map = {f.scenario: f for f in bundle.financial_scenarios}
    assert fin_map["conservative"].total_5yr_units < fin_map["baseline"].total_5yr_units
    assert fin_map["baseline"].total_5yr_units < fin_map["optimistic"].total_5yr_units
    assert fin_map["baseline"].npv_10pct_cny_wan > 0.0
    assert fin_map["baseline"].irr_pct > 25.0

    for roi in bundle.plant_roi_list:
        assert 2.0 < roi.payback_months_baseline < 12.0
        assert roi.payback_months_optimistic <= roi.payback_months_baseline <= roi.payback_months_conservative
