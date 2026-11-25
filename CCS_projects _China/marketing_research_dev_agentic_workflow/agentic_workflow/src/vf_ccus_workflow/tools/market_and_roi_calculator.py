"""Deterministic Python Calculators: [MKT-CALC] China TAM/SAM/SOM & [ROI-CALC] 3-Scenario PALMs."""

from __future__ import annotations

from typing import Any

from vf_ccus_workflow.schemas import (
    ChinaMarketSizingSummary,
    CommercialWedgeCandidate,
    EliminatedWedge,
    EvaluatedWedge,
    HorizonSizingBreakdown,
    ROIInputs,
    ROIMetrics,
    ROIRangeInputs,
    ROIRangeMetrics,
    SegmentSizingInput,
    SegmentSizingResult,
)

DISCOUNT_RATE = 0.08
HORIZON_YEARS = 5

DEFAULT_ASP_CNY_WAN: dict[str, float] = {
    "TRACK_A_IMPORTED_CORE": 180.0,
    "TRACK_B_LOCALIZED_QAS": 420.0,
    "TRACK_C_AUSTRIA_PREMIERGUARD": 720.0,
}

DEFAULT_SCENARIO_MULTIPLIERS: dict[str, float] = {
    "conservative": 0.70,
    "baseline": 1.00,
    "optimistic": 1.35,
}

DEFAULT_WIN_RATE_MULTIPLIERS: dict[str, float] = {
    "conservative": 0.75,
    "baseline": 1.00,
    "optimistic": 1.22,
}

SECTOR_LABELS_CN: dict[str, str] = {
    "S1_pipeline_ship_eor": "S1: 超临界管道/油田EOR/LCO2船运枢纽",
    "S2_green_methanol_ccu_chem": "S2: 绿氢+CO2绿色甲醇/e-SAF合成",
    "S3_capture_rd_industry": "S3: 煤电/水泥/钢铁捕集与中试平台",
    "S4_food_beverage_dryice": "S4: 食品饮料/干冰CCU(对照甄别)",
}


def _build_horizon_breakdown(
    *,
    name: str,
    base_tam_units: int,
    base_sam_units: int,
    win_rate: float,
    asp: float,
    v_mult: float,
    w_mult: float,
) -> HorizonSizingBreakdown:
    t_u = max(1, round(base_tam_units * v_mult))
    sa_u = max(1, round(base_sam_units * v_mult))
    so_u = max(0, min(sa_u, round(sa_u * win_rate * w_mult)))
    return HorizonSizingBreakdown(
        scenario=name,  # type: ignore[arg-type]
        tam_units=t_u,
        tam_cny_wan=round(t_u * asp, 1),
        sam_units=sa_u,
        sam_cny_wan=round(sa_u * asp, 1),
        som_units=so_u,
        som_cny_wan=round(so_u * asp, 1),
    )


def compute_china_tam_sam_som(
    inputs: list[SegmentSizingInput],
    *,
    asp_map: dict[str, float] | None = None,
    scenario_multipliers: dict[str, float] | None = None,
    win_rate_multipliers: dict[str, float] | None = None,
) -> ChinaMarketSizingSummary:
    """Deterministic bottom-up [MKT-CALC] engine across 2026-2030 & 2031-2036 (Low/Base/High).

    Aggregates orthogonally by (sector, sub_segment, primary_delivery_track, horizon) so
    e.g. onshore S1 pipelines (Track B) and offshore/ship LCO2 hubs (Track C) accumulate cleanly.
    """
    asp_table = dict(DEFAULT_ASP_CNY_WAN)
    if asp_map:
        asp_table.update({k: float(v) for k, v in asp_map.items()})

    vol_mults = dict(DEFAULT_SCENARIO_MULTIPLIERS)
    if scenario_multipliers:
        vol_mults.update({k: float(v) for k, v in scenario_multipliers.items()})

    win_mults = dict(DEFAULT_WIN_RATE_MULTIPLIERS)
    if win_rate_multipliers:
        win_mults.update({k: float(v) for k, v in win_rate_multipliers.items()})

    # Deduplicate only exact (sector, sub_segment, track, horizon) duplicates keeping strongest evidence
    deduped: dict[tuple[str, str, str, str], SegmentSizingInput] = {}
    for item in inputs:
        norm_sub = item.sub_segment.strip().lower() or "general"
        key = (item.sector, norm_sub, item.primary_delivery_track, item.horizon)
        cur = deduped.get(key)
        if cur is None or len(item.evidence_ids) > len(cur.evidence_ids):
            deduped[key] = item

    results: list[SegmentSizingResult] = []
    horizon_totals: dict[str, dict[str, dict[str, float]]] = {
        "2026-2030": {
            s: {"tam_units": 0, "tam_cny_wan": 0.0, "sam_units": 0, "sam_cny_wan": 0.0, "som_units": 0, "som_cny_wan": 0.0}
            for s in ("conservative", "baseline", "optimistic")
        },
        "2031-2036": {
            s: {"tam_units": 0, "tam_cny_wan": 0.0, "sam_units": 0, "sam_cny_wan": 0.0, "som_units": 0, "som_cny_wan": 0.0}
            for s in ("conservative", "baseline", "optimistic")
        },
    }

    for key in sorted(deduped.keys()):
        seg = deduped[key]
        horizon = seg.horizon
        asp = asp_table.get(seg.primary_delivery_track, 420.0)
        base_tam_units = max(1, round(seg.addressable_project_or_line_count * seg.stations_per_project))
        base_sam_units = max(1, round(base_tam_units * seg.technical_fit_ratio))

        cons = _build_horizon_breakdown(
            name="conservative",
            base_tam_units=base_tam_units,
            base_sam_units=base_sam_units,
            win_rate=seg.realistic_som_win_rate,
            asp=asp,
            v_mult=vol_mults["conservative"],
            w_mult=win_mults["conservative"],
        )
        base = _build_horizon_breakdown(
            name="baseline",
            base_tam_units=base_tam_units,
            base_sam_units=base_sam_units,
            win_rate=seg.realistic_som_win_rate,
            asp=asp,
            v_mult=vol_mults["baseline"],
            w_mult=win_mults["baseline"],
        )
        opt = _build_horizon_breakdown(
            name="optimistic",
            base_tam_units=base_tam_units,
            base_sam_units=base_sam_units,
            win_rate=seg.realistic_som_win_rate,
            asp=asp,
            v_mult=vol_mults["optimistic"],
            w_mult=win_mults["optimistic"],
        )

        for scen_name, bd in (("conservative", cons), ("baseline", base), ("optimistic", opt)):
            bucket = horizon_totals[horizon][scen_name]
            bucket["tam_units"] += bd.tam_units
            bucket["tam_cny_wan"] = round(bucket["tam_cny_wan"] + bd.tam_cny_wan, 1)
            bucket["sam_units"] += bd.sam_units
            bucket["sam_cny_wan"] = round(bucket["sam_cny_wan"] + bd.sam_cny_wan, 1)
            bucket["som_units"] += bd.som_units
            bucket["som_cny_wan"] = round(bucket["som_cny_wan"] + bd.som_cny_wan, 1)

        results.append(
            SegmentSizingResult(
                sector=seg.sector,
                sub_segment=seg.sub_segment,
                horizon=seg.horizon,
                primary_delivery_track=seg.primary_delivery_track,
                asp_cny_wan=asp,
                conservative=cons,
                baseline=base,
                optimistic=opt,
                evidence_ids=seg.evidence_ids,
            )
        )

    grand_som_wan = round(
        horizon_totals["2026-2030"]["baseline"]["som_cny_wan"]
        + horizon_totals["2031-2036"]["baseline"]["som_cny_wan"],
        1,
    )
    grand_som_units = int(
        horizon_totals["2026-2030"]["baseline"]["som_units"]
        + horizon_totals["2031-2036"]["baseline"]["som_units"]
    )
    return ChinaMarketSizingSummary(
        segments=results,
        horizon_totals=horizon_totals,
        grand_total_10yr_baseline_som_cny_wan=grand_som_wan,
        grand_total_10yr_baseline_som_units=grand_som_units,
    )


def _compute_irr(cashflows: list[float]) -> float:
    """Solve 5-year IRR (%) using bisection on NPV=0."""
    if sum(cashflows[1:]) <= abs(cashflows[0]):
        total_cf = sum(cashflows)
        return round((total_cf / abs(cashflows[0])) * 20.0, 2) if cashflows[0] != 0 else -100.0

    low, high = -0.95, 5.0
    for _ in range(80):
        mid = (low + high) / 2.0
        npv = sum(cf / ((1.0 + mid) ** t) for t, cf in enumerate(cashflows))
        if npv > 0:
            low = mid
        else:
            high = mid
    return round(((low + high) / 2.0) * 100.0, 2)


def _payback_tier(payback_months: float) -> str:
    if payback_months < 12.0:
        return "<12个月(极强刚需)"
    if payback_months <= 24.0:
        return "12-24个月(明确正向商业可行)"
    if payback_months <= 36.0:
        return "24-36个月(战略协同推进)"
    return ">36个月/负现金流(淘汰或伪需求)"


def compute_roi_metrics(inputs: ROIInputs) -> ROIMetrics:
    """Deterministic PALMs financial computation ([ROI-CALC])."""
    gross = inputs.total_gross_benefit_cny_yr
    net_cf = gross - inputs.annual_opex_cny_yr
    capex = inputs.capex_cny

    if net_cf <= 0:
        payback = 999.0
        roi_3yr = round(((net_cf * 3.0 - capex) / capex) * 100.0, 2)
    else:
        payback = round((capex / net_cf) * 12.0, 2)
        roi_3yr = round(((net_cf * 3.0 - capex) / capex) * 100.0, 2)

    cashflows = [-capex] + [net_cf] * HORIZON_YEARS
    npv_5yr = round(
        sum(cf / ((1.0 + DISCOUNT_RATE) ** t) for t, cf in enumerate(cashflows)), 2
    )
    irr_5yr = _compute_irr(cashflows)

    return ROIMetrics(
        capex_cny=round(capex, 2),
        gross_annual_benefit_cny=round(gross, 2),
        net_annual_cashflow_cny=round(net_cf, 2),
        payback_months=payback,
        roi_3yr_pct=roi_3yr,
        npv_5yr_cny=npv_5yr,
        irr_5yr_pct=irr_5yr,
        payback_tier=_payback_tier(payback),  # type: ignore[arg-type]
    )


def clamp_range_inputs_to_guardrails(
    wedge: CommercialWedgeCandidate,
    guardrails: dict[str, Any] | None = None,
) -> ROIRangeInputs:
    """Derive and clamp 3-scenario customer ROI ranges against YAML sector guardrails."""
    roi_in = wedge.roi_baseline
    raw_gross = roi_in.total_gross_benefit_cny_yr
    rng = wedge.roi_range or ROIRangeInputs(
        capex_cny_min=round(roi_in.capex_cny * 0.85, 2),
        capex_cny_base=round(roi_in.capex_cny, 2),
        capex_cny_max=round(roi_in.capex_cny * 1.22, 2),
        gross_benefit_cny_min=round(max(80_000.0, raw_gross * 0.65), 2),
        gross_benefit_cny_base=round(max(100_000.0, raw_gross), 2),
        gross_benefit_cny_max=round(max(120_000.0, raw_gross * 1.35), 2),
        annual_opex_cny_min=round(roi_in.annual_opex_cny_yr * 0.85, 2),
        annual_opex_cny_base=round(roi_in.annual_opex_cny_yr, 2),
        annual_opex_cny_max=round(roi_in.annual_opex_cny_yr * 1.20, 2),
    )

    sec_guard = (guardrails or {}).get(wedge.sector, {}) or {}
    if sec_guard:
        c_lo, c_hi = sec_guard.get("capex_cny_band", [rng.capex_cny_min, rng.capex_cny_max])
        b_lo, b_hi = sec_guard.get("gross_benefit_cny_band", [rng.gross_benefit_cny_min, rng.gross_benefit_cny_max])
        o_lo, o_hi = sec_guard.get("annual_opex_cny_band", [rng.annual_opex_cny_min, rng.annual_opex_cny_max])
        return ROIRangeInputs(
            capex_cny_min=min(max(rng.capex_cny_min, float(c_lo)), float(c_hi)),
            capex_cny_base=min(max(rng.capex_cny_base, float(c_lo)), float(c_hi)),
            capex_cny_max=min(max(rng.capex_cny_max, float(c_lo)), float(c_hi)),
            gross_benefit_cny_min=min(max(rng.gross_benefit_cny_min, float(b_lo)), float(b_hi)),
            gross_benefit_cny_base=min(max(rng.gross_benefit_cny_base, float(b_lo)), float(b_hi)),
            gross_benefit_cny_max=min(max(rng.gross_benefit_cny_max, float(b_lo)), float(b_hi)),
            annual_opex_cny_min=min(max(rng.annual_opex_cny_min, float(o_lo)), float(o_hi)),
            annual_opex_cny_base=min(max(rng.annual_opex_cny_base, float(o_lo)), float(o_hi)),
            annual_opex_cny_max=min(max(rng.annual_opex_cny_max, float(o_lo)), float(o_hi)),
        )
    return rng


def compute_range_roi_metrics(
    rng: ROIRangeInputs,
    template: ROIInputs | None = None,
) -> ROIRangeMetrics:
    def _build(capex: float, gross: float, opex: float) -> ROIMetrics:
        if template is not None:
            roi_in = template.scaled(
                capex_cny=capex,
                target_gross_benefit_cny=gross,
                annual_opex_cny=opex,
            )
        else:
            roi_in = ROIInputs(
                capex_cny=capex,
                avoided_corrosion_and_shutdown_loss_cny_yr=round(gross * 0.45, 2),
                avoided_catalyst_poison_or_flaring_cny_yr=round(gross * 0.30, 2),
                avoided_manual_lab_and_multi_gc_opex_cny_yr=round(gross * 0.15, 2),
                ccer_or_export_compliance_upside_cny_yr=round(gross * 0.10, 2),
                annual_opex_cny_yr=opex,
            )
        return compute_roi_metrics(roi_in)

    return ROIRangeMetrics(
        conservative=_build(rng.capex_cny_max, rng.gross_benefit_cny_min, rng.annual_opex_cny_max),
        baseline=_build(rng.capex_cny_base, rng.gross_benefit_cny_base, rng.annual_opex_cny_base),
        optimistic=_build(rng.capex_cny_min, rng.gross_benefit_cny_max, rng.annual_opex_cny_min),
    )


def compute_weighted_wedge_score(
    *,
    roi: ROIMetrics,
    china_priority: float,
    vf_moat: float,
    horizon: str,
    evidence_count: int,
    delivery_track: str,
) -> float:
    """Deterministic multi-pillar composite score (0-100) balancing customer ROI, China priority, and V&F moat."""
    if roi.payback_months <= 12.0:
        roi_score = 95.0
    elif roi.payback_months <= 20.0:
        roi_score = 86.0
    elif roi.payback_months <= 30.0:
        roi_score = 74.0
    elif roi.payback_months <= 42.0:
        roi_score = 58.0
    else:
        roi_score = 25.0

    horizon_bonus = 4.0 if horizon == "2026-2030" else 1.5
    track_bonus = 3.0 if delivery_track == "TRACK_B_LOCALIZED_QAS" else 2.0
    ev_bonus = min(5.0, evidence_count * 1.25)

    raw = 0.36 * roi_score + 0.32 * china_priority + 0.25 * vf_moat + horizon_bonus + track_bonus + ev_bonus - 5.0
    return round(max(0.0, min(100.0, raw)), 2)


def screen_wedge_pool(
    candidates: list[CommercialWedgeCandidate],
    *,
    guardrails: dict[str, Any] | None = None,
    target_total: int = 10,
    max_conservative_payback_months: float = 42.0,
) -> tuple[list[EvaluatedWedge], list[EliminatedWedge]]:
    """Stage 2 Funnel: Clamp ranges preserving 4-line ROI proportions -> Hard gates -> Preserve eliminated wedges."""
    deduped: dict[str, CommercialWedgeCandidate] = {}
    for c in candidates:
        cur = deduped.get(c.wedge_id)
        if cur is None or len(c.evidence_ids) > len(cur.evidence_ids):
            deduped[c.wedge_id] = c

    evaluated_all: list[EvaluatedWedge] = []
    for cand in deduped.values():
        clamped = clamp_range_inputs_to_guardrails(cand, guardrails=guardrails)
        scaled_baseline = clamped.to_baseline_inputs(template=cand.roi_baseline)
        clean_cand = cand.model_copy(
            update={"roi_range": clamped, "roi_baseline": scaled_baseline}
        )
        roi_rng = compute_range_roi_metrics(clamped, template=cand.roi_baseline)
        roi = roi_rng.baseline
        w_score = compute_weighted_wedge_score(
            roi=roi,
            china_priority=clean_cand.china_priority_score,
            vf_moat=clean_cand.vf_moat_score,
            horizon=clean_cand.horizon,
            evidence_count=len(clean_cand.evidence_ids),
            delivery_track=clean_cand.delivery_track,
        )
        evaluated_all.append(
            EvaluatedWedge(
                seed=clean_cand,
                roi=roi,
                roi_range=roi_rng,
                weighted_pillar_score=w_score,
            )
        )

    survivors: list[EvaluatedWedge] = []
    eliminated: list[EliminatedWedge] = []
    for ev in evaluated_all:
        cons_pb = ev.roi_range.conservative.payback_months if ev.roi_range else ev.roi.payback_months
        reasons: list[str] = []
        if len(ev.seed.evidence_ids) == 0:
            reasons.append("缺少证据库引用 ID")
        if ev.roi.net_annual_cashflow_cny <= 0:
            reasons.append(f"基准情景客户年净现金流为负 (¥{ev.roi.net_annual_cashflow_cny:,.0f})")
        if cons_pb > max_conservative_payback_months:
            reasons.append(
                f"保守情景回收期 {cons_pb:.1f} 个月超过准入门槛 {max_conservative_payback_months:.1f} 个月"
            )
        if ev.seed.verdict == "DEPRIORITIZE_OR_PSEUDO_DEMAND":
            reasons.append("被业务判定为低支付意愿或伪需求对照赛道")

        if reasons:
            eliminated.append(
                EliminatedWedge(
                    wedge_id=ev.seed.wedge_id,
                    sector=ev.seed.sector,
                    title=ev.seed.title,
                    baseline_payback_months=ev.roi.payback_months,
                    conservative_payback_months=cons_pb,
                    elimination_reason="；".join(reasons),
                    evidence_ids=ev.seed.evidence_ids,
                )
            )
        else:
            survivors.append(ev)

    survivors.sort(key=lambda x: (x.weighted_pillar_score, -x.roi.payback_months), reverse=True)
    if len(survivors) > target_total:
        for extra in survivors[target_total:]:
            cons_pb = extra.roi_range.conservative.payback_months if extra.roi_range else extra.roi.payback_months
            eliminated.append(
                EliminatedWedge(
                    wedge_id=extra.seed.wedge_id,
                    sector=extra.seed.sector,
                    title=extra.seed.title,
                    baseline_payback_months=extra.roi.payback_months,
                    conservative_payback_months=cons_pb,
                    elimination_reason=f"Stage 2 加权评分 {extra.weighted_pillar_score:.1f} 未进入前 {target_total} 优先切入组合",
                    evidence_ids=extra.seed.evidence_ids,
                )
            )
        survivors = survivors[:target_total]

    for idx, item in enumerate(survivors, start=1):
        item.composite_rank = idx
    return survivors, eliminated


def format_market_sizing_table(summary: ChinaMarketSizingSummary) -> str:
    """Format deterministic [MKT-CALC] China TAM/SAM/SOM Markdown table."""
    lines = [
        "### [MKT-CALC] 中国CCS/CCUS V&F IMR-MS 市场规模确定性测算总表（单位：台套数 / 人民币万元）",
        "",
        "| 细分赛道 / 子板块 | 周期 | 主推交付轨道 | 单价基准(万元) | 保守TAM/SAM/SOM(万元) | 基准TAM/SAM/SOM(万元) | 基准SOM台套 | 乐观SOM(万元) | 依据ID |",
        "| :--- | :--- | :--- | ---: | :--- | :--- | ---: | ---: | :--- |",
    ]
    for s in summary.segments:
        lbl = SECTOR_LABELS_CN.get(s.sector, s.sector)
        sub_lbl = f"{lbl} ({s.sub_segment})" if s.sub_segment and s.sub_segment != "general" else lbl
        cons_s = f"{s.conservative.tam_cny_wan:,.0f} / {s.conservative.sam_cny_wan:,.0f} / **{s.conservative.som_cny_wan:,.0f}**"
        base_s = f"{s.baseline.tam_cny_wan:,.0f} / {s.baseline.sam_cny_wan:,.0f} / **{s.baseline.som_cny_wan:,.0f}**"
        evs = ", ".join(s.evidence_ids[:4])
        lines.append(
            f"| {sub_lbl} | {s.horizon} | `{s.primary_delivery_track}` | {s.asp_cny_wan:,.0f} | "
            f"{cons_s} | {base_s} | **{s.baseline.som_units}** | {s.optimistic.som_cny_wan:,.0f} | {evs} |"
        )

    lines.extend(
        [
            "",
            "#### [MKT-CALC] 分阶段汇总 (中国区域)",
            "",
            "| 规划周期 | 情景 | TAM (台套 / 亿元) | SAM (台套 / 亿元) | V&F 可触达 SOM (台套 / 万元) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for horizon in ("2026-2030", "2031-2036"):
        for scen, label in (("conservative", "保守"), ("baseline", "基准"), ("optimistic", "乐观")):
            b = summary.horizon_totals[horizon][scen]
            lines.append(
                f"| {horizon} | {label} | {int(b['tam_units'])} 套 / ¥{b['tam_cny_wan']/10000:.2f}亿 | "
                f"{int(b['sam_units'])} 套 / ¥{b['sam_cny_wan']/10000:.2f}亿 | "
                f"**{int(b['som_units'])} 套 / ¥{b['som_cny_wan']:,.0f}万** |"
            )
    lines.append(
        f"\n> **[MKT-CALC] 10年(2026-2036) 基准情景 V&F 中国区累计可获取 SOM**：**{summary.grand_total_10yr_baseline_som_units} 台套 / ¥{summary.grand_total_10yr_baseline_som_cny_wan:,.0f} 万元（约 ¥{summary.grand_total_10yr_baseline_som_cny_wan/10000:.2f} 亿元）**。"
    )
    return "\n".join(lines) + "\n"


def format_roi_table(wedges: list[dict[str, Any]]) -> str:
    """Format deterministic [ROI-CALC] Markdown table across surviving wedges."""
    lines = [
        "### [ROI-CALC] 入选高价值商业切入点三情景客户投资回报明细",
        "",
        "| 排名 | Wedge ID | 切入场景 | 交付轨道 | 客户CAPEX(万) | 年净现金流(万) | 回收期[乐/基/保](月) | 5Y IRR | 5Y NPV(万) | 全局评分 |",
        "| :---: | :--- | :--- | :--- | ---: | ---: | :---: | ---: | ---: | ---: |",
    ]
    for w in wedges:
        seed = w["seed"]
        roi = w["roi"]
        rng = w.get("roi_range") or {}
        opt_pb = (rng.get("optimistic") or {}).get("payback_months", roi["payback_months"])
        cons_pb = (rng.get("conservative") or {}).get("payback_months", roi["payback_months"])
        score = w.get("global_priority_score") if w.get("global_priority_score") is not None else w.get("weighted_pillar_score", 0)
        lines.append(
            f"| #{w.get('composite_rank', 0)} | `{seed['wedge_id']}` | {seed['title']} | "
            f"`{seed['delivery_track']}` | ¥{roi['capex_cny']/10000:.1f} | "
            f"¥{roi['net_annual_cashflow_cny']/10000:.1f} | "
            f"{opt_pb:.1f} / **{roi['payback_months']:.1f}** / {cons_pb:.1f} | "
            f"{roi['irr_5yr_pct']:.1f}% | ¥{roi['npv_5yr_cny']/10000:.1f} | {float(score):.1f} |"
        )
    return "\n".join(lines) + "\n"


def format_eliminated_table(eliminated: list[dict[str, Any]]) -> str:
    """Format explicitly eliminated / pseudo-demand wedges to avoid survivorship bias."""
    if not eliminated:
        return "（本次漏斗未淘汰任何候选场景。）\n"
    lines = [
        "### Stage 2 漏斗淘汰与“伪需求/低支付意愿”对照清单",
        "",
        "| Wedge ID | 赛道 | 场景标题 | 基准/保守回收期(月) | 淘汰或降级原因 | 依据ID |",
        "| :--- | :--- | :--- | :---: | :--- | :--- |",
    ]
    for el in eliminated:
        evs = ", ".join(el.get("evidence_ids", [])[:3])
        lines.append(
            f"| `{el['wedge_id']}` | {el['sector']} | {el['title']} | "
            f"{el['baseline_payback_months']:.1f} / {el['conservative_payback_months']:.1f} | "
            f"{el['elimination_reason']} | {evs} |"
        )
    return "\n".join(lines) + "\n"
