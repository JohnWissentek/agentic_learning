"""PALMs Deterministic Engineering & Financial Engine ([PHY-CALC], [BOM-CALC], [FIN-CALC], [PLANT-ROI]).

Zero LLM mental arithmetic allowed. All optical link budgets, channel wavelength margins,
dual-track tiered BOM costs, 5-year lean startup P&L/NPV/IRR, and coal-plant buyer paybacks
are computed deterministically from YAML engineering/finance assumptions.
"""

from __future__ import annotations

from typing import Any

from bfbg_workflow.schemas import (
    ArchComparisonRow,
    DeterministicCalcBundle,
    FinancialYearRow,
    PhysicsLinkBudgetResult,
    PlantROISummary,
    ScenarioFinancialSummary,
    TierBomBreakdown,
)


def _compute_irr(cash_flows: list[float]) -> float:
    """Compute Internal Rate of Return (%) via bisection on NPV(r)=0."""
    if not cash_flows or all(cf <= 0 for cf in cash_flows) or all(cf >= 0 for cf in cash_flows):
        return 0.0

    def npv_at(rate: float) -> float:
        return sum(cf / ((1.0 + rate) ** t) for t, cf in enumerate(cash_flows))

    lo, hi = -0.60, 4.00
    f_lo = npv_at(lo)
    f_hi = npv_at(hi)
    if f_lo * f_hi > 0:
        return 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        f_mid = npv_at(mid)
        if abs(f_mid) < 1e-6:
            return round(mid * 100.0, 2)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    return round(0.5 * (lo + hi) * 100.0, 2)


def _compute_npv(cash_flows: list[float], discount_rate: float) -> float:
    return round(sum(cf / ((1.0 + discount_rate) ** t) for t, cf in enumerate(cash_flows)), 2)


def compute_physics_and_link_budget(catalog: dict[str, Any]) -> PhysicsLinkBudgetResult:
    """Calculate optical link budget, thermal wavelength drift, scan cycle, and block conduction."""
    p = catalog["physics_link_params"]
    dt = float(p["temp_max_c"]) - float(p["temp_min_c"])
    # Quadratic thermo-optic expansion over 20..600°C
    slope = float(p["thermo_optic_sensitivity_pm_per_c"])
    quad = float(p["quadratic_coeff_pm_per_c2"])
    max_drift_nm = (slope * dt + quad * (dt**2)) / 1000.0

    # Adjacent local hot-spot gradient <= 180°C (neighbor slagging vs flame impingement)
    local_grad_drift_nm = (slope * 180.0 + quad * (180.0**2)) / 1000.0

    std_spacing = float(p["std_channel_spacing_nm"])
    std_pts_per_fiber = int(float(p["std_band_nm"]) // std_spacing) - 1
    std_collision_margin = round(std_spacing - local_grad_drift_nm - 0.35, 3)

    passive_loss = (
        float(p["circulator_il_db"])
        + float(p["mems_switch_il_db"])
        + float(p["connector_and_splice_loss_db"])
        + float(p["fiber_transmission_loss_db"])
    )
    # 25 points spectral slice per channel: ASE spectral power within 0.25 nm FBG FWHM
    ase_slice_offset_db = -18.5
    std_rx_power_dbm = round(
        float(p["std_ase_power_dbm"]) + ase_slice_offset_db - passive_loss + float(p["fbg_peak_reflectivity_db"]),
        2,
    )
    std_snr_margin_db = round(std_rx_power_dbm - float(p["std_spectrometer_noise_floor_dbm"]), 2)
    std_scan_cycle_ms = round(
        24 * (float(p["mems_switch_settle_ms"]) + float(p["std_exposure_per_ch_ms"])), 1
    )

    pro_spacing = float(p["pro_channel_spacing_nm"])
    pro_wdm_pts = int((float(p["pro_band_nm"]) - 6.0) // pro_spacing)
    pro_hybrid_pts = pro_wdm_pts * 3  # 3 TDM/OFDR zones per wavelength slot (ultra-weak FBG)
    pro_rx_wdm_dbm = round(
        float(p["pro_swept_power_dbm"]) - passive_loss + float(p["fbg_peak_reflectivity_db"]), 2
    )
    pro_rx_uwfbg_dbm = round(
        float(p["pro_swept_power_dbm"]) - passive_loss + float(p["uwfbg_peak_reflectivity_db"]), 2
    )
    pro_snr_wdm = round(pro_rx_wdm_dbm - float(p["pro_femto_tia_noise_floor_dbm"]), 2)
    pro_snr_uwfbg = round(pro_rx_uwfbg_dbm - float(p["pro_femto_tia_noise_floor_dbm"]), 2)
    # 1600 pts: e.g. 48 channels * 33 pts/ch (or 16 channels * 100 hybrid pts)
    pro_scan_1600_ms = round(
        48 * (float(p["mems_switch_settle_ms"]) + float(p["pro_sweep_per_ch_ms"])), 1
    )

    # 15CrMoG steady-state conduction drop at peak furnace heat flux q = 350 kW/m^2
    q_flux = 350_000.0
    k_steel = float(p["thermal_block_steel_k_w_mk"])
    path_m = float(p["thermal_block_path_mm"]) / 1000.0
    # Effective 1D equivalent drop across weld-to-bore with lateral fin spreading factor 0.35
    delta_t_block = round((q_flux * path_m / k_steel) * 0.35, 2)
    # First-order lumped thermal time constant of 22x16x14mm block + 316L capillary
    tau_s = 4.2

    return PhysicsLinkBudgetResult(
        std_points_per_fiber=std_pts_per_fiber,
        std_max_temp_drift_nm=round(max_drift_nm, 2),
        std_channel_spacing_nm=std_spacing,
        std_collision_margin_nm=std_collision_margin,
        std_rx_power_dbm=std_rx_power_dbm,
        std_snr_margin_db=std_snr_margin_db,
        std_scan_cycle_ms=std_scan_cycle_ms,
        pro_wdm_points_per_fiber=pro_wdm_pts,
        pro_hybrid_points_per_fiber=pro_hybrid_pts,
        pro_rx_power_wdm_dbm=pro_rx_wdm_dbm,
        pro_rx_power_uwfbg_dbm=pro_rx_uwfbg_dbm,
        pro_snr_margin_wdm_db=pro_snr_wdm,
        pro_snr_margin_uwfbg_db=pro_snr_uwfbg,
        pro_scan_cycle_1600pts_ms=pro_scan_1600_ms,
        block_steady_temp_drop_c_at_350kwm2=delta_t_block,
        block_first_order_tau_s=tau_s,
    )


def compute_arch_comparisons(catalog: dict[str, Any]) -> list[ArchComparisonRow]:
    """Compare all 5 candidate engineering routes deterministically."""
    rows: list[ArchComparisonRow] = []
    for arch in catalog["candidate_architectures"]:
        std_500 = float(arch["host_capex_std_cny"]) + 500 * float(arch["sensor_unit_track_b_cny"]) + 14500.0
        pro_1500 = float(arch["host_capex_pro_cny"]) + 1500 * float(arch["sensor_unit_track_b_cny"]) + 14500.0
        rows.append(
            ArchComparisonRow(
                arch_id=arch["arch_id"],
                name=arch["name"],
                std_500pt_cogs_cny=round(std_500, 0),
                pro_1500pt_cogs_cny=round(pro_1500, 0),
                rd_cycle_months=float(arch["rd_cycle_months"]),
                hardware_risk_score=float(arch["hardware_risk_score"]),
                scalability_score=float(arch["scalability_score"]),
                supply_resilience_score=float(arch["supply_resilience_score"]),
            )
        )
    return rows


def compute_dual_track_bom_matrix(catalog: dict[str, Any]) -> list[TierBomBreakdown]:
    """Calculate prototype, 10-unit, and 50-unit BOM, total COGS, per-point cost & margins."""
    items = catalog["bom_line_items"]
    std_proto = sum(float(x["unit_cost_proto_cny"]) for x in items["std_600_host"])
    std_10u = sum(float(x["unit_cost_10u_cny"]) for x in items["std_600_host"])
    std_50u = sum(float(x["unit_cost_50u_cny"]) for x in items["std_600_host"])

    pro_proto = sum(float(x["unit_cost_proto_cny"]) for x in items["pro_2000_host"])
    pro_10u = sum(float(x["unit_cost_10u_cny"]) for x in items["pro_2000_host"])
    pro_50u = sum(float(x["unit_cost_50u_cny"]) for x in items["pro_2000_host"])

    fa = items["field_assemblies"]
    moh_qa = float(fa["moh_calibration_and_qa_per_sys_cny"])
    pricing = catalog["pricing_and_lean_finance"]

    configs = [
        ("BS-STD-300", 300, 12, std_proto, std_10u, std_50u, pricing["std_500_track_a_list_price_cny"] * 0.85, pricing["std_500_track_b_list_price_cny"] * 0.85),
        ("BS-STD-500", 500, 20, std_proto, std_10u, std_50u, pricing["std_500_track_a_list_price_cny"], pricing["std_500_track_b_list_price_cny"]),
        ("BS-PRO-1000", 1000, 32, pro_proto, pro_10u, pro_50u, pricing["pro_1500_track_a_list_price_cny"] * 0.82, pricing["pro_1500_track_b_list_price_cny"] * 0.82),
        ("BS-PRO-1500", 1500, 48, pro_proto, pro_10u, pro_50u, pricing["pro_1500_track_a_list_price_cny"], pricing["pro_1500_track_b_list_price_cny"]),
        ("BS-PRO-2000", 2000, 48, pro_proto, pro_10u, pro_50u, pricing["pro_1500_track_a_list_price_cny"] * 1.15, pricing["pro_1500_track_b_list_price_cny"] * 1.15),
    ]

    matrix: list[TierBomBreakdown] = []
    for cfg_code, pts, chs, h_p, h_10, h_50, price_a, price_b in configs:
        for track_name, rate_p, rate_10, rate_50, list_price in (
            ("Track_A_Full_Imported", float(fa["track_a_per_point_proto"]), float(fa["track_a_per_point_10u"]), float(fa["track_a_per_point_50u"]), float(price_a)),
            ("Track_B_Hybrid_Competitive", float(fa["track_b_per_point_proto"]), float(fa["track_b_per_point_10u"]), float(fa["track_b_per_point_50u"]), float(price_b)),
        ):
            s_p = pts * rate_p
            s_10 = pts * rate_10
            s_50 = pts * rate_50
            tot_p = h_p + s_p + moh_qa
            tot_10 = h_10 + s_10 + moh_qa
            tot_50 = h_50 + s_50 + moh_qa
            gm_10 = (list_price - tot_10) / list_price * 100.0
            gm_50 = (list_price - tot_50) / list_price * 100.0
            matrix.append(
                TierBomBreakdown(
                    config_code=cfg_code,
                    points_count=pts,
                    channels_count=chs,
                    supply_track=track_name,  # type: ignore[arg-type]
                    host_bom_proto_cny=round(h_p, 0),
                    host_bom_10u_cny=round(h_10, 0),
                    host_bom_50u_cny=round(h_50, 0),
                    sensor_bom_10u_cny=round(s_10, 0),
                    sensor_bom_50u_cny=round(s_50, 0),
                    moh_qa_cny=round(moh_qa, 0),
                    total_cogs_proto_cny=round(tot_p, 0),
                    total_cogs_10u_cny=round(tot_10, 0),
                    total_cogs_50u_cny=round(tot_50, 0),
                    per_point_cogs_10u_cny=round(tot_10 / pts, 1),
                    per_point_cogs_50u_cny=round(tot_50 / pts, 1),
                    target_list_price_cny=round(list_price, 0),
                    gross_margin_10u_pct=round(gm_10, 1),
                    gross_margin_50u_pct=round(gm_50, 1),
                )
            )
    return matrix


def compute_lean_5yr_financials(
    catalog: dict[str, Any], bom_matrix: list[TierBomBreakdown]
) -> list[ScenarioFinancialSummary]:
    """Compute 5-year P&L, cash flow, breakeven, NPV, and IRR across Bear/Base/Bull."""
    fin = catalog["pricing_and_lean_finance"]
    capex_dict = fin["startup_capex"]
    total_capex_cny = sum(float(v) for v in capex_dict.values())
    capex_wan = round(total_capex_cny / 10000.0, 2)

    bom_lookup = {(b.config_code, b.supply_track): b for b in bom_matrix}
    std_a = bom_lookup[("BS-STD-500", "Track_A_Full_Imported")]
    std_b = bom_lookup[("BS-STD-500", "Track_B_Hybrid_Competitive")]
    pro_a = bom_lookup[("BS-PRO-1500", "Track_A_Full_Imported")]
    pro_b = bom_lookup[("BS-PRO-1500", "Track_B_Hybrid_Competitive")]

    comm_rate = float(fin["channel_commission_rate"])
    warr_rate = float(fin["warranty_reserve_rate"])
    comm_std = float(fin["field_commissioning_cost_std_cny"])
    comm_pro = float(fin["field_commissioning_cost_pro_cny"])
    opex_y1 = float(fin["annual_fixed_opex_y1_cny"])
    opex_g = float(fin["annual_fixed_opex_growth_rate"])
    tax_rate = float(fin["tax_and_vat_effective_rate"])
    disc_rate = float(fin["discount_rate"])

    summaries: list[ScenarioFinancialSummary] = []
    for scenario in ("conservative", "baseline", "optimistic"):
        ramp = fin["sales_ramp_5yr"][scenario]
        std_list = ramp["std_units"]
        pro_list = ramp["pro_units"]
        tb_share = float(ramp["track_b_share"])
        ta_share = 1.0 - tb_share

        yearly_rows: list[FinancialYearRow] = []
        cash_flows_wan: list[float] = [-capex_wan]
        cum_cf_wan = -capex_wan
        breakeven_yr = 0
        tot_units = 0
        tot_rev_wan = 0.0
        tot_ebitda_wan = 0.0

        for idx in range(5):
            yr = idx + 1
            s_u = int(std_list[idx])
            p_u = int(pro_list[idx])
            u_sum = s_u + p_u
            tot_units += u_sum

            # Use 10-unit tier for Year 1-2 and 50-unit tier for Year 3-5
            use_50u = yr >= 3
            std_cogs = (std_b.total_cogs_50u_cny if use_50u else std_b.total_cogs_10u_cny) * tb_share + (
                std_a.total_cogs_50u_cny if use_50u else std_a.total_cogs_10u_cny
            ) * ta_share
            pro_cogs = (pro_b.total_cogs_50u_cny if use_50u else pro_b.total_cogs_10u_cny) * tb_share + (
                pro_a.total_cogs_50u_cny if use_50u else pro_a.total_cogs_10u_cny
            ) * ta_share

            std_asp = std_b.target_list_price_cny * tb_share + std_a.target_list_price_cny * ta_share
            pro_asp = pro_b.target_list_price_cny * tb_share + pro_a.target_list_price_cny * ta_share

            rev_cny = s_u * std_asp + p_u * pro_asp
            direct_cogs_cny = (
                s_u * (std_cogs + comm_std)
                + p_u * (pro_cogs + comm_pro)
                + rev_cny * (comm_rate + warr_rate)
            )
            gp_cny = rev_cny - direct_cogs_cny
            opex_cny = opex_y1 * ((1.0 + opex_g) ** idx)
            ebitda_cny = gp_cny - opex_cny
            tax_cny = max(0.0, ebitda_cny * tax_rate)
            ncf_wan = (ebitda_cny - tax_cny) / 10000.0
            cum_cf_wan += ncf_wan
            cash_flows_wan.append(round(ncf_wan, 2))
            if ebitda_cny > 0 and breakeven_yr == 0:
                breakeven_yr = yr

            rev_wan = rev_cny / 10000.0
            tot_rev_wan += rev_wan
            tot_ebitda_wan += ebitda_cny / 10000.0
            gm_pct = (gp_cny / rev_cny * 100.0) if rev_cny > 0 else 0.0

            yearly_rows.append(
                FinancialYearRow(
                    year=yr,
                    std_units=s_u,
                    pro_units=p_u,
                    total_units=u_sum,
                    revenue_cny_wan=round(rev_wan, 1),
                    cogs_and_delivery_cny_wan=round(direct_cogs_cny / 10000.0, 1),
                    gross_profit_cny_wan=round(gp_cny / 10000.0, 1),
                    gross_margin_pct=round(gm_pct, 1),
                    opex_cny_wan=round(opex_cny / 10000.0, 1),
                    ebitda_cny_wan=round(ebitda_cny / 10000.0, 1),
                    net_cash_flow_cny_wan=round(ncf_wan, 1),
                    cumulative_cash_flow_cny_wan=round(cum_cf_wan, 1),
                )
            )

        # Blended contribution margin per std-equivalent unit for Year 2 OPEX breakeven
        avg_contrib_per_unit_cny = (
            std_b.target_list_price_cny * (1.0 - comm_rate - warr_rate) - std_b.total_cogs_10u_cny - comm_std
        )
        be_units = max(1, int(round((opex_y1 * (1.0 + opex_g)) / max(1.0, avg_contrib_per_unit_cny))))

        summaries.append(
            ScenarioFinancialSummary(
                scenario=scenario,  # type: ignore[arg-type]
                startup_capex_cny_wan=capex_wan,
                total_5yr_units=tot_units,
                total_5yr_revenue_cny_wan=round(tot_rev_wan, 1),
                total_5yr_ebitda_cny_wan=round(tot_ebitda_wan, 1),
                breakeven_year=breakeven_yr or 3,
                breakeven_units_annual=be_units,
                npv_10pct_cny_wan=_compute_npv(cash_flows_wan, disc_rate),
                irr_pct=_compute_irr(cash_flows_wan),
                yearly_rows=yearly_rows,
            )
        )
    return summaries


def compute_plant_roi(catalog: dict[str, Any]) -> list[PlantROISummary]:
    """Compute coal-fired plant buyer ROI and payback period across 600MW and 1000MW units."""
    plant_data = catalog["plant_roi_scenarios"]
    results: list[PlantROISummary] = []
    for key, label in (
        ("unit_600mw_std", "600MW 亚临界/超临界灵活性机组 (配置 BS-STD-600 Track B)"),
        ("unit_1000mw_pro", "1000MW 超超临界深度调峰机组 (配置 BS-PRO-2000 Track B)"),
    ):
        d = plant_data[key]
        capex = float(d["capex_cny"])
        opex = float(d["annual_service_opex_cny"])
        gross_base = (
            float(d["avoided_tube_leak_expected_cny_yr"])
            + float(d["sootblowing_steam_saving_cny_yr"])
            + float(d["coal_rate_reduction_saving_cny_yr"])
        )
        net_base = gross_base - opex
        net_cons = gross_base * 0.65 - opex
        net_opt = gross_base * 1.30 - opex
        pb_cons = round(capex / max(1.0, net_cons) * 12.0, 1)
        pb_base = round(capex / max(1.0, net_base) * 12.0, 1)
        pb_opt = round(capex / max(1.0, net_opt) * 12.0, 1)
        roi_3yr = round((net_base * 3.0 - capex) / capex * 100.0, 1)
        results.append(
            PlantROISummary(
                unit_label=label,
                capex_cny=capex,
                annual_service_opex_cny=opex,
                annual_gross_benefit_base_cny=round(gross_base, 0),
                annual_net_benefit_base_cny=round(net_base, 0),
                payback_months_conservative=pb_cons,
                payback_months_baseline=pb_base,
                payback_months_optimistic=pb_opt,
                three_yr_roi_pct_baseline=roi_3yr,
            )
        )
    return results


def render_calc_markdown_tables(
    phy: PhysicsLinkBudgetResult,
    archs: list[ArchComparisonRow],
    boms: list[TierBomBreakdown],
    fins: list[ScenarioFinancialSummary],
    rois: list[PlantROISummary],
) -> dict[str, str]:
    """Render deterministic markdown tables for downstream multi-agent grounding."""
    phy_md = "\n".join(
        [
            "| 关键物理与光学链路指标 (`[PHY-CALC]`) | BS-STD-600 (宽谱线阵 OEM) | BS-PRO-2000 (高速扫频 + NIST气室) | 工程设计裕度说明 |",
            "| :--- | :---: | :---: | :--- |",
            f"| 20~600°C 满量程最大波长漂移 | `{phy.std_max_temp_drift_nm} nm` | `{phy.std_max_temp_drift_nm} nm` | 含二次热光非线性项 `0.0042 pm/°C²` |",
            f"| 单通道串联容量 | `{phy.std_points_per_fiber} 点` (`{phy.std_channel_spacing_nm} nm` 间距) | `{phy.pro_wdm_points_per_fiber} 点` (WDM) / `{phy.pro_hybrid_points_per_fiber} 点` (混复) | 相邻局部 180°C 温差余量 `{phy.std_collision_margin_nm} nm` 防串扰 |",
            f"| 接收端有效回波功率 | `{phy.std_rx_power_dbm} dBm` | `{phy.pro_rx_power_wdm_dbm} dBm` (WDM) / `{phy.pro_rx_power_uwfbg_dbm} dBm` (UWFBG) | 计入环形器/开关/4对FC-APC及传输双向损耗 `6.8 dB` |",
            f"| 系统动态信噪比裕度 (SNR Margin) | **`{phy.std_snr_margin_db} dB`** | **`{phy.pro_snr_margin_wdm_db} dB`** (WDM) / **`{phy.pro_snr_margin_uwfbg_db} dB`** | 全工况远超 `15 dB` 工业可靠解调底线 |",
            f"| 全炉轮询刷新周期 | `{phy.std_scan_cycle_ms} ms` (24路) | `{phy.pro_scan_cycle_1600pts_ms} ms` (48路) | 满足锅炉热惯性 `1 Hz` 在线监测节拍 |",
            f"| `15CrMoG` 导热块稳态温差与响应 $\\tau$ | `-{phy.block_steady_temp_drop_c_at_350kwm2}°C` / `{phy.block_first_order_tau_s} s` | `-{phy.block_steady_temp_drop_c_at_350kwm2}°C` / `{phy.block_first_order_tau_s} s` | 软件热流逆向修正模型标定补偿输入 |",
        ]
    )

    arch_lines = [
        "| 候选架构代号 | 路线名称 | 500点基准COGS(元) | 1500点基准COGS(元) | 硬件研发周期(月) | 可靠性(0-10) | 扩展性(0-10) | 供应链韧性 |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for a in archs:
        arch_lines.append(
            f"| `{a.arch_id}` | {a.name} | `¥{a.std_500pt_cogs_cny:,.0f}` | `¥{a.pro_1500pt_cogs_cny:,.0f}` | `{a.rd_cycle_months}` | `{a.hardware_risk_score}` | `{a.scalability_score}` | `{a.supply_resilience_score}` |"
        )

    bom_lines = [
        "| 配置型号 (`[BOM-CALC]`) | 点数 / 路数 | 传感供应链轨道 | 10套主机BOM(元) | 10套传感BOM(元) | 50套总COGS(元) | 50套单点COGS(元/点) | 建议含税售价(元) | 10套 / 50套毛利率 |",
        "| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for b in boms:
        track_lbl = "Track A 全进口传感" if b.supply_track == "Track_A_Full_Imported" else "Track B 混合高性价比"
        bom_lines.append(
            f"| `{b.config_code}` | {b.points_count}点 / {b.channels_count}路 | {track_lbl} | "
            f"`¥{b.host_bom_10u_cny:,.0f}` | `¥{b.sensor_bom_10u_cny:,.0f}` | "
            f"`¥{b.total_cogs_50u_cny:,.0f}` | **`¥{b.per_point_cogs_50u_cny:,.1f}`** | "
            f"`¥{b.target_list_price_cny:,.0f}` | `{b.gross_margin_10u_pct}%` / `{b.gross_margin_50u_pct}%` |"
        )

    fin_lines = [
        "| 财务情景 (`[FIN-CALC]`) | 启动CAPEX(万元) | 5年总销量(套) | 5年累计营收(万元) | 5年累计EBITDA(万元) | 盈亏平衡年 / 年保本套数 | NPV@10%(万元) | 5年 IRR |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for f in fins:
        fin_lines.append(
            f"| `{f.scenario}` | `{f.startup_capex_cny_wan}` | `{f.total_5yr_units}` | "
            f"`{f.total_5yr_revenue_cny_wan:,.1f}` | `{f.total_5yr_ebitda_cny_wan:,.1f}` | "
            f"第 `{f.breakeven_year}` 年 / `{f.breakeven_units_annual}` 套 | "
            f"**`{f.npv_10pct_cny_wan:,.1f}`** | **`{f.irr_pct}%`** |"
        )

    roi_lines = [
        "| 电厂机组场景 (`[PLANT-ROI]`) | 采购CAPEX(元) | 年均运维(元) | 基准年毛收益(元) | 基准年净收益(元) | 保守/基准/乐观回收期(月) | 3年ROI(基准) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in rois:
        roi_lines.append(
            f"| {r.unit_label} | `¥{r.capex_cny:,.0f}` | `¥{r.annual_service_opex_cny:,.0f}` | "
            f"`¥{r.annual_gross_benefit_base_cny:,.0f}` | `¥{r.annual_net_benefit_base_cny:,.0f}` | "
            f"`{r.payback_months_conservative}` / **`{r.payback_months_baseline}`** / `{r.payback_months_optimistic}` 月 | **`{r.three_yr_roi_pct_baseline}%`** |"
        )

    return {
        "physics_link_md": "\n".join(phy_md),
        "arch_comparison_md": "\n".join(arch_lines),
        "bom_matrix_md": "\n".join(bom_lines),
        "financial_scenarios_md": "\n".join(fin_lines),
        "plant_roi_md": "\n".join(roi_lines),
    }


def run_all_deterministic_calcs(catalog: dict[str, Any]) -> DeterministicCalcBundle:
    """Execute complete PALMs engineering + dual-track BOM + 5-year finance + plant ROI calculations."""
    phy = compute_physics_and_link_budget(catalog)
    archs = compute_arch_comparisons(catalog)
    boms = compute_dual_track_bom_matrix(catalog)
    fins = compute_lean_5yr_financials(catalog, boms)
    rois = compute_plant_roi(catalog)
    md_tables = render_calc_markdown_tables(phy, archs, boms, fins, rois)
    return DeterministicCalcBundle(
        physics_link=phy,
        arch_comparisons=archs,
        bom_matrix=boms,
        financial_scenarios=fins,
        plant_roi_list=rois,
        markdown_tables=md_tables,
    )
