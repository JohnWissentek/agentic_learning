"""Black-box v2.0 contract & regression tests (Blind Test Author - RED Phase).

Covers all 7 acceptance scenarios against Red-Zone contracts (`schemas.py`,
`config/discovery_scope.yaml`, `config/research_contract.yaml`) and public
module entrypoints with real temporary SQLite vaults and zero network calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from vf_ccus_workflow.nodes.critic_and_judge import (
    build_single_volume_critic_prompt,
    build_single_volume_rewrite_prompt,
)
from vf_ccus_workflow.nodes.researcher import (
    clean_competitive_dossier,
    clean_sector_dossier,
)
from vf_ccus_workflow.schemas import (
    ChinaCCUSProjectItem,
    CommercialWedgeCandidate,
    CompetitiveEcosystemDossier,
    CompetitorProfile,
    DeterministicAuditReport,
    EvidenceSearchHit,
    PACIntegratorProfile,
    PortfolioArbitrationOutput,
    ROIInputs,
    ROIRangeInputs,
    SectorDossier,
    SegmentSizingInput,
    export_flat_json_schema,
)
from vf_ccus_workflow.tools.evidence_vault import (
    EvidenceVault,
    extract_all_ev_ids,
    run_deterministic_full_audit,
)
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    compute_china_tam_sam_som,
    screen_wedge_pool,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "config" / "research_contract.yaml"
SCOPE_PATH = PROJECT_ROOT / "config" / "discovery_scope.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _make_roi_inputs(
    *,
    capex_cny: float = 3_600_000.0,
    corrosion: float = 200_000.0,
    catalyst: float = 2_400_000.0,
    lab: float = 200_000.0,
    compliance: float = 200_000.0,
    opex: float = 220_000.0,
) -> ROIInputs:
    return ROIInputs(
        capex_cny=capex_cny,
        avoided_corrosion_and_shutdown_loss_cny_yr=corrosion,
        avoided_catalyst_poison_or_flaring_cny_yr=catalyst,
        avoided_manual_lab_and_multi_gc_opex_cny_yr=lab,
        ccer_or_export_compliance_upside_cny_yr=compliance,
        annual_opex_cny_yr=opex,
    )


def _make_wedge_candidate(
    *,
    wedge_id: str = "W-MEOH-CAT-01",
    sector: str = "S2_green_methanol_ccu_chem",
    verdict: str = "GO_HIGH_PRIORITY",
    china_priority_score: float = 88.0,
    vf_moat_score: float = 92.0,
    roi_baseline: ROIInputs | None = None,
    roi_range: ROIRangeInputs | None = None,
    evidence_ids: list[str] | None = None,
) -> CommercialWedgeCandidate:
    return CommercialWedgeCandidate(
        wedge_id=wedge_id,
        track_id="T2_MEOH",
        sector=sector,  # type: ignore[arg-type]
        horizon="2026-2030",
        delivery_track="TRACK_B_LOCALIZED_QAS",
        title="绿氢+CO2制绿色甲醇合成气Cu/ZnO催化剂防毒秒级守门",
        verdict=verdict,  # type: ignore[arg-type]
        china_priority_score=china_priority_score,
        vf_moat_score=vf_moat_score,
        target_process_point="CO2精脱硫出口至甲醇合成塔入口总管",
        chemical_pain_point_and_imr_advantage="1s在线拦截ppm级H2S/COS/NH3/Amines瞬态穿透防止催化剂失活",
        recommended_vf_sku_and_localization="Track B VF-QAS-CN双轨防爆分析小屋",
        key_competing_alternatives="离线GC(5-15分钟滞后)/多台光学单气体仪表",
        named_china_benchmark_customers=["金风绿能化工", "吉利碳循环甲醇示范"],
        siggi_reference_proof="V&F ProcessSense/CO2Sense 1s全谱监控",
        roi_baseline=roi_baseline or _make_roi_inputs(),
        roi_range=roi_range,
        evidence_ids=evidence_ids or ["EV-SIGGI-001", "EV-CN-001"],
    )


# =============================================================================
# 场景 1：单源扁平 JSON Schema 导出（零 $ref/$defs，保留数值上下界与枚举约束）
# =============================================================================


@pytest.mark.parametrize(
    "model_cls",
    [SectorDossier, CompetitiveEcosystemDossier, PortfolioArbitrationOutput],
)
def test_s1_export_flat_json_schema_has_no_refs_or_defs(model_cls: type) -> None:
    """导出后的 JSON Schema 必须完全内联扁平化，严禁残留 $ref 或 $defs。"""
    schema = export_flat_json_schema(model_cls)
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"

    serialized = json.dumps(schema, ensure_ascii=False)
    assert "$ref" not in serialized, f"{model_cls.__name__} schema still contains $ref"
    assert "$defs" not in serialized, f"{model_cls.__name__} schema still contains $defs"


def test_s1_export_flat_json_schema_preserves_numeric_bounds_and_enums() -> None:
    """扁平化导出必须完整保留 0–100 数值上下界与核心 Literal 枚举约束。"""
    sector_schema = export_flat_json_schema(SectorDossier)
    wedge_props = sector_schema["properties"]["wedges"]["items"]["properties"]

    for score_field in ("china_priority_score", "vf_moat_score"):
        field_schema = wedge_props[score_field]
        assert field_schema.get("minimum") == 0.0
        assert field_schema.get("maximum") == 100.0

    assert set(sector_schema["properties"]["sector"]["enum"]) == {
        "S1_pipeline_ship_eor",
        "S2_green_methanol_ccu_chem",
        "S3_capture_rd_industry",
        "S4_food_beverage_dryice",
    }
    assert set(wedge_props["delivery_track"]["enum"]) == {
        "TRACK_A_IMPORTED_CORE",
        "TRACK_B_LOCALIZED_QAS",
        "TRACK_C_AUSTRIA_PREMIERGUARD",
    }
    assert set(wedge_props["verdict"]["enum"]) == {
        "GO_HIGH_PRIORITY",
        "GO_CONDITIONAL",
        "DEPRIORITIZE_OR_PSEUDO_DEMAND",
    }

    comp_schema = export_flat_json_schema(CompetitiveEcosystemDossier)
    comp_origin_enum = comp_schema["properties"]["competitors"]["items"]["properties"]["origin_category"]["enum"]
    assert "Overseas_Process_MS" in comp_origin_enum
    assert "Domestic_PAC_System_Integrator" in comp_origin_enum

    arb_schema = export_flat_json_schema(PortfolioArbitrationOutput)
    ranked_props = arb_schema["properties"]["deduped_ranked_wedges"]["items"]["properties"]
    assert ranked_props["global_priority_score"].get("minimum") == 0.0
    assert ranked_props["global_priority_score"].get("maximum") == 100.0
    persona_verdict_enum = (
        arb_schema["properties"]["track_buyer_matrix"]["items"]["properties"]["persona_critiques"]["items"][
            "properties"
        ]["verdict"]["enum"]
    )
    assert set(persona_verdict_enum) == {"STRONG_BUY", "CONDITIONAL_试点", "REJECT_OR_WAIT"}


# =============================================================================
# 场景 2：防 0–10 vs 0–100 标尺分裂，且不误杀 S4 食品级伪需求低分场景
# =============================================================================


@pytest.mark.parametrize(
    ("china_priority_score", "vf_moat_score"),
    [
        (9.2, 92.0),
        (88.0, 9.5),
        (9.2, 9.5),
    ],
)
def test_s2_high_priority_wedge_rejects_ten_point_scale_scores(
    china_priority_score: float,
    vf_moat_score: float,
) -> None:
    """GO_HIGH_PRIORITY 场景若出现 0–10 分制错标（<=10），Pydantic 必须拦截抛出 ValidationError。"""
    with pytest.raises(ValidationError):
        _make_wedge_candidate(
            verdict="GO_HIGH_PRIORITY",
            china_priority_score=china_priority_score,
            vf_moat_score=vf_moat_score,
        )


def test_s2_deprioritize_s4_pseudo_demand_allows_low_score_without_false_positive() -> None:
    """S4 食品级伪需求（DEPRIORITIZE_OR_PSEUDO_DEMAND）低分如 5.0 必须合法放行，防误杀。"""
    s4_wedge = _make_wedge_candidate(
        wedge_id="W-S4-FOOD-CTRL",
        sector="S4_food_beverage_dryice",
        verdict="DEPRIORITIZE_OR_PSEUDO_DEMAND",
        china_priority_score=5.0,
        vf_moat_score=8.5,
    )
    assert s4_wedge.china_priority_score == 5.0
    assert s4_wedge.verdict == "DEPRIORITIZE_OR_PSEUDO_DEMAND"


# =============================================================================
# 场景 3：S1 跨子赛道细分累加不覆盖 + 读取 YAML 情景乘数（0.70 非硬编码 0.72）
# =============================================================================


def _make_s1_dual_subsegment_inputs() -> list[SegmentSizingInput]:
    return [
        SegmentSizingInput(
            sector="S1_pipeline_ship_eor",
            sub_segment="onshore_pipeline_eor",
            horizon="2026-2030",
            addressable_project_or_line_count=28,
            stations_per_project=2.5,
            primary_delivery_track="TRACK_B_LOCALIZED_QAS",
            technical_fit_ratio=0.80,
            realistic_som_win_rate=0.20,
            evidence_ids=["EV-CN-001"],
        ),
        SegmentSizingInput(
            sector="S1_pipeline_ship_eor",
            sub_segment="lco2_export_vessel_hub",
            horizon="2026-2030",
            addressable_project_or_line_count=15,
            stations_per_project=2.0,
            primary_delivery_track="TRACK_C_AUSTRIA_PREMIERGUARD",
            technical_fit_ratio=0.80,
            realistic_som_win_rate=0.25,
            evidence_ids=["EV-SIGGI-001", "EV-GL-001"],
        ),
    ]


def test_s3_tam_sam_som_accumulates_sub_segments_without_overwriting_track_c() -> None:
    """同属 S1 2026-2030 的陆上管网(Track B)与海运枢纽(Track C)必须并存累加，严禁键碰撞覆盖丢失。"""
    summary = compute_china_tam_sam_som(_make_s1_dual_subsegment_inputs())

    assert len(summary.segments) == 2
    assert {seg.sub_segment for seg in summary.segments} == {
        "onshore_pipeline_eor",
        "lco2_export_vessel_hub",
    }
    assert {seg.primary_delivery_track for seg in summary.segments} == {
        "TRACK_B_LOCALIZED_QAS",
        "TRACK_C_AUSTRIA_PREMIERGUARD",
    }

    h_2026_base = summary.horizon_totals["2026-2030"]["baseline"]
    assert h_2026_base["tam_units"] == 100
    assert h_2026_base["tam_cny_wan"] == pytest.approx(70 * 420.0 + 30 * 720.0)


def test_s3_tam_sam_som_uses_yaml_scenario_multipliers_instead_of_hardcoded_072() -> None:
    """传入 YAML 情景乘数 conservative=0.70 时，保守情景 tam_units 必须按 0.70（70套）而非硬编码 0.72（72套）计算。"""
    scope = _load_yaml(SCOPE_PATH)
    yaml_multipliers = scope["china_market_sizing_guardrails"]["scenario_multipliers"]
    assert yaml_multipliers == {"conservative": 0.70, "baseline": 1.00, "optimistic": 1.35}

    summary = compute_china_tam_sam_som(
        _make_s1_dual_subsegment_inputs(),
        scenario_multipliers={"conservative": 0.70, "baseline": 1.00, "optimistic": 1.35},
    )

    assert len(summary.segments) == 2
    # 70 * 0.70 = 49, 30 * 0.70 = 21 => 保守情景总计 70 套（若硬编码 0.72 会误算为 50 + 22 = 72 套）
    h_2026_cons = summary.horizon_totals["2026-2030"]["conservative"]
    assert h_2026_cons["tam_units"] == 70
    assert h_2026_cons["tam_cny_wan"] == pytest.approx(49 * 420.0 + 21 * 720.0)


# =============================================================================
# 场景 4：保留 ROI 四项原始收益比例，禁止 45/30/15/10 强洗
# =============================================================================


def test_s4_roi_inputs_scaled_preserves_domain_benefit_proportions() -> None:
    """ROIInputs.scaled 必须等比缩放 4 项收益，保持催化剂防毒 80% 占比不被强洗为 30%。"""
    base_roi = _make_roi_inputs(
        capex_cny=3_600_000.0,
        corrosion=200_000.0,
        catalyst=2_400_000.0,  # 80% of 3,000,000
        lab=200_000.0,
        compliance=200_000.0,
        opex=220_000.0,
    )
    assert base_roi.total_gross_benefit_cny_yr == pytest.approx(3_000_000.0)

    scaled = base_roi.scaled(
        capex_cny=3_800_000.0,
        target_gross_benefit_cny=4_200_000.0,
        annual_opex_cny=250_000.0,
    )
    assert scaled.capex_cny == pytest.approx(3_800_000.0)
    assert scaled.annual_opex_cny_yr == pytest.approx(250_000.0)
    assert scaled.total_gross_benefit_cny_yr == pytest.approx(4_200_000.0, rel=1e-4)

    catalyst_share = scaled.avoided_catalyst_poison_or_flaring_cny_yr / scaled.total_gross_benefit_cny_yr
    assert catalyst_share == pytest.approx(0.80, abs=0.01)


def test_s4_screen_wedge_pool_clamping_preserves_80pct_catalyst_ratio() -> None:
    """经 screen_wedge_pool 护栏钳制后，绿醇催化剂防毒收益占比仍须维持约 80%（误差 < 1%）。"""
    # 构造超出 S2 上限(420万)的 600 万总收益，强制触发护栏钳制，验证钳制后四项比例不被洗成 45/30/15/10
    over_band_roi = _make_roi_inputs(
        capex_cny=3_600_000.0,
        corrosion=400_000.0,
        catalyst=4_800_000.0,  # 80% of 6,000,000
        lab=400_000.0,
        compliance=400_000.0,
        opex=220_000.0,
    )
    in_band_roi = _make_roi_inputs(
        capex_cny=3_600_000.0,
        corrosion=200_000.0,
        catalyst=2_400_000.0,  # 80% of 3,000,000
        lab=200_000.0,
        compliance=200_000.0,
        opex=220_000.0,
    )
    cand_in_band = _make_wedge_candidate(
        wedge_id="W-MEOH-INBAND",
        roi_baseline=in_band_roi,
        roi_range=None,
    )
    cand_over_band = _make_wedge_candidate(
        wedge_id="W-MEOH-CLAMPED",
        roi_baseline=over_band_roi,
        roi_range=ROIRangeInputs(
            capex_cny_min=3_200_000.0,
            capex_cny_base=3_600_000.0,
            capex_cny_max=4_200_000.0,
            gross_benefit_cny_min=4_500_000.0,
            gross_benefit_cny_base=6_000_000.0,
            gross_benefit_cny_max=7_000_000.0,
            annual_opex_cny_min=180_000.0,
            annual_opex_cny_base=220_000.0,
            annual_opex_cny_max=280_000.0,
        ),
    )

    shortlist, eliminated = screen_wedge_pool(
        [cand_in_band, cand_over_band],
        target_total=5,
        max_conservative_payback_months=42.0,
    )
    assert len(eliminated) == 0
    assert len(shortlist) == 2

    for evaluated in shortlist:
        roi_b = evaluated.seed.roi_baseline
        assert roi_b.total_gross_benefit_cny_yr > 0
        catalyst_share = roi_b.avoided_catalyst_poison_or_flaring_cny_yr / roi_b.total_gross_benefit_cny_yr
        assert catalyst_share == pytest.approx(0.80, abs=0.01), (
            f"Wedge {evaluated.seed.wedge_id} catalyst share distorted to {catalyst_share:.2%}"
        )


# =============================================================================
# 场景 5：多 ID 括号引用全提取 & 拒绝静默假挂靠 fallback_ids
# =============================================================================


def test_s5_extract_all_ev_ids_handles_single_and_multi_id_brackets() -> None:
    """extract_all_ev_ids 必须从逗号/分号混合多 ID 括号与单 ID 括号中完整提取全部 4 个 ID。"""
    text = "见 [EV-SIGGI-001, EV-CN-003; EV-GL-009] 以及 [EV-CN-999]"
    extracted = extract_all_ev_ids(text)
    assert extracted == {"EV-SIGGI-001", "EV-CN-003", "EV-GL-009", "EV-CN-999"}

    table_text = "| 项目 | [EV-SIGGI-002、EV-CN-010 / EV-GL-004] |"
    assert extract_all_ev_ids(table_text) == {"EV-SIGGI-002", "EV-CN-010", "EV-GL-004"}


def test_s5_clean_sector_dossier_drops_unverified_records_without_silent_backfill() -> None:
    """clean_sector_dossier 遇到仅引用未入库假 ID 的项目/竞品必须剔除并审计记录，严禁假挂靠有效 ID。"""
    valid_global_ids = {"EV-SIGGI-001", "EV-CN-001"}
    raw = SectorDossier(
        track_id="T1_EOR",
        sector="S1_pipeline_ship_eor",
        track_name="超临界管道与EOR",
        key_findings_summary="核验发现",
        named_projects=[
            ChinaCCUSProjectItem(
                project_name="齐鲁石化-胜利油田CCUS",
                owner_and_epc="中石化/SEI",
                province_or_region="山东",
                sector="S1_pipeline_ship_eor",
                capacity_mtpa_or_scale="1.0 Mtpa",
                status_2026="投运",
                co2_impurity_profile_and_risk="H2S/NOx/SOx交叉腐蚀",
                recommended_delivery_track="TRACK_B_LOCALIZED_QAS",
                evidence_ids=["EV-CN-001"],
            ),
            ChinaCCUSProjectItem(
                project_name="虚构管道示范项目X",
                owner_and_epc="虚构EPC",
                province_or_region="某省",
                sector="S1_pipeline_ship_eor",
                capacity_mtpa_or_scale="5.0 Mtpa",
                status_2026="规划",
                co2_impurity_profile_and_risk="未知",
                recommended_delivery_track="TRACK_B_LOCALIZED_QAS",
                evidence_ids=["EV-CN-999"],
            ),
        ],
        competitors=[
            CompetitorProfile(
                vendor_name="Thermo Fisher MAX-iR",
                origin_category="Overseas_FTIR_Optical_GC",
                verified_models_and_tech="FTIR + O2/Sulfur",
                detectable_species_and_speed="多组分约10分钟",
                blind_spots_vs_vf_imr_ms="无法直测H2/N2/Ar且滞后",
                china_ccus_presence_and_pricing_position="海外进口",
                win_strategy_for_vf="1s秒级IMR-MS连续监控",
                evidence_ids=["EV-SIGGI-001", "EV-CN-999"],
            ),
            CompetitorProfile(
                vendor_name="虚构质谱厂商Y",
                origin_category="Domestic_MS_Vendor",
                verified_models_and_tech="虚构型号MS-9999",
                detectable_species_and_speed="虚构",
                blind_spots_vs_vf_imr_ms="虚构",
                china_ccus_presence_and_pricing_position="低价",
                win_strategy_for_vf="无",
                evidence_ids=["EV-CN-999"],
            ),
        ],
        sizing_inputs=[
            SegmentSizingInput(
                sector="S1_pipeline_ship_eor",
                sub_segment="onshore_pipeline_eor",
                horizon="2026-2030",
                addressable_project_or_line_count=10,
                stations_per_project=2.0,
                primary_delivery_track="TRACK_B_LOCALIZED_QAS",
                evidence_ids=["EV-CN-001"],
            )
        ],
        wedges=[_make_wedge_candidate(sector="S1_pipeline_ship_eor", evidence_ids=["EV-SIGGI-001"])],
        evidence_ids=["EV-SIGGI-001", "EV-CN-001", "EV-CN-999"],
    )

    cleaned, dropped = clean_sector_dossier(
        raw_dossier=raw,
        track_id="T1_EOR",
        sector="S1_pipeline_ship_eor",
        valid_global_ids=valid_global_ids,
    )

    assert [p.project_name for p in cleaned.named_projects] == ["齐鲁石化-胜利油田CCUS"]
    assert [c.vendor_name for c in cleaned.competitors] == ["Thermo Fisher MAX-iR"]
    assert cleaned.competitors[0].evidence_ids == ["EV-SIGGI-001"]
    assert "EV-CN-999" not in cleaned.evidence_ids

    assert len(dropped) >= 2
    dropped_blob = json.dumps(dropped, ensure_ascii=False)
    assert "虚构管道示范项目X" in dropped_blob
    assert "虚构质谱厂商Y" in dropped_blob


def test_s5_clean_competitive_dossier_drops_unverified_competitors_and_pac() -> None:
    """clean_competitive_dossier 必须剔除仅含伪造 ID 的竞品与 PAC 集成商并记入审计表。"""
    valid_global_ids = {"EV-SIGGI-001", "EV-CN-005"}
    raw_comp = CompetitiveEcosystemDossier(
        track_id="T5_COMP_PAC",
        track_name="竞品与本土PAC分析小屋生态",
        key_findings_summary="竞品生态核验",
        competitors=[
            CompetitorProfile(
                vendor_name="ABB Process Analytics",
                origin_category="Overseas_FTIR_Optical_GC",
                verified_models_and_tech="FTIR/GC多机组合",
                detectable_species_and_speed="多组分分钟级",
                blind_spots_vs_vf_imr_ms="非秒级单一主机",
                china_ccus_presence_and_pricing_position="高价外资",
                win_strategy_for_vf="单机IMR-MS+本土小屋",
                evidence_ids=["EV-CN-005"],
            ),
            CompetitorProfile(
                vendor_name="虚构海外竞品Z",
                origin_category="Overseas_Process_MS",
                verified_models_and_tech="FakeMS-X1",
                detectable_species_and_speed="虚构",
                blind_spots_vs_vf_imr_ms="虚构",
                china_ccus_presence_and_pricing_position="未知",
                win_strategy_for_vf="无",
                evidence_ids=["EV-CN-999"],
            ),
        ],
        pac_integrators=[
            PACIntegratorProfile(
                company_name="真实本土分析小屋集成商A",
                core_capabilities="国标GB/T 3836防爆正压小屋与预处理集成",
                certifications_and_qualifications="防爆合格证/石油化工准入",
                cooperation_fit_with_vf="高契合度Track B OEM伙伴",
                evidence_ids=["EV-CN-005"],
            ),
            PACIntegratorProfile(
                company_name="虚构PAC集成商W",
                core_capabilities="虚构能力",
                certifications_and_qualifications="无",
                cooperation_fit_with_vf="未知",
                evidence_ids=["EV-GL-888"],
            ),
        ],
        design_institute_spec_barriers=["SEI/HQC PID标准册准入"],
        evidence_ids=["EV-SIGGI-001", "EV-CN-005"],
    )

    cleaned, dropped = clean_competitive_dossier(
        raw_dossier=raw_comp,
        track_id="T5_COMP_PAC",
        valid_global_ids=valid_global_ids,
    )

    assert [c.vendor_name for c in cleaned.competitors] == ["ABB Process Analytics"]
    assert [p.company_name for p in cleaned.pac_integrators] == ["真实本土分析小屋集成商A"]
    assert len(dropped) >= 2
    dropped_blob = json.dumps(dropped, ensure_ascii=False)
    assert "虚构海外竞品Z" in dropped_blob
    assert "虚构PAC集成商W" in dropped_blob


# =============================================================================
# 场景 6：Critic 与 Rewrite 100% 全文无截断 + 卷宗精准证据路由
# =============================================================================


def test_s6_critic_and_rewrite_prompts_preserve_full_text_without_truncation() -> None:
    """超过 15,000 字符的报告在第 14,500 字符处的哨兵标记必须 100% 出现在 Critic 与 Rewrite 提示词中。"""
    sentinel = "END_SENTINEL_14500"
    long_report = ("甲" * 14_500) + sentinel + ("乙" * 600)
    assert len(long_report) > 15_000

    critic_prompt = build_single_volume_critic_prompt(
        volume_name="01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        full_text=long_report,
        fact_sheet="[MKT-CALC] 基准事实表",
        invalid_ids=[],
        loop_idx=1,
        max_loops=2,
    )
    assert sentinel in critic_prompt
    assert len(critic_prompt) >= len(long_report)

    rewrite_prompt = build_single_volume_rewrite_prompt(
        volume_name="01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        full_text=long_report,
        fact_sheet="[MKT-CALC] 基准事实表",
        critic_feedback="补强末端章节的管道腐蚀机理引用",
        invalid_ids=["EV-CN-999"],
        crag_context="补充CRAG检索到的中国超临界管道团标证据",
        volume_evidence_context="[EV-CN-001] 齐鲁-胜利油田CCUS工程",
    )
    assert sentinel in rewrite_prompt
    assert len(rewrite_prompt) >= len(long_report)


def test_s6_vault_volume_evidence_bundle_prioritizes_track_and_high_index_ev_id(tmp_path: Path) -> None:
    """写入 100+ 条跨赛道证据后，卷宗路由包必须优先召回高序号 EV-CN-095 及目标轨道证据，不得按序截断丢弃。"""
    vault = EvidenceVault(tmp_path / "routing_vault.db")
    try:
        # 写入 10 条 SIGGI + 10 条 GLOBAL + 100 条 CN（其中第 91-100 条归属 T5_COMP_PAC，确保总库 > 80 条）
        for i in range(1, 11):
            vault.upsert_hit(
                track_id="SIGGI_BASE",
                hit=EvidenceSearchHit(
                    title=f"Siggi Primary Evidence {i}",
                    url=f"siggi-corpus://doc#{i}",
                    snippet=f"V&F IMR-MS benchmark fact #{i}",
                    source_engine="siggi_mcp",
                    geo_scope="SIGGI",
                ),
            )
        for i in range(1, 11):
            vault.upsert_hit(
                track_id="T1_PIPELINE",
                hit=EvidenceSearchHit(
                    title=f"Global CCS Spec {i}",
                    url=f"https://global.example.org/spec/{i}",
                    snippet=f"Northern Lights / ISO CO2 impurity spec #{i}",
                    source_engine="serper",
                    geo_scope="GLOBAL",
                ),
            )
        ev_cn_095_record = None
        for i in range(1, 101):
            tid = "T5_COMP_PAC" if i >= 91 else "T1_PIPELINE"
            rec = vault.upsert_hit(
                track_id=tid,
                hit=EvidenceSearchHit(
                    title=f"中国CCUS证据条目 {i}",
                    url=f"https://example.cn/evidence/{i}",
                    snippet=f"赛道 {tid} 证据摘要 #{i}",
                    source_engine="metaso",
                    geo_scope="CN",
                ),
            )
            if i == 95:
                ev_cn_095_record = rec

        assert ev_cn_095_record is not None
        assert ev_cn_095_record.ev_id == "EV-CN-095"
        assert vault.stats()["total"] == 120

        bundle = vault.build_volume_evidence_bundle(
            volume_name="02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
            track_ids=["T5_COMP_PAC"],
            priority_ev_ids={"EV-CN-095"},
        )
        bundle_ids = {rec.ev_id for rec in bundle}
        assert "EV-CN-095" in bundle_ids
        assert any(rec.track_id == "T5_COMP_PAC" for rec in bundle)
        assert len(bundle) <= 80
    finally:
        vault.close()


# =============================================================================
# 场景 7：双版本全量确定性审计门禁 run_deterministic_full_audit
# =============================================================================


def _build_valid_audit_fixture() -> dict[str, Any]:
    contract = _load_yaml(CONTRACT_PATH)
    volume_names = list(contract["required_deliverables"]["full_edition"])
    valid_ids = {
        *(f"EV-SIGGI-{i:03d}" for i in range(1, 15)),
        *(f"EV-CN-{i:03d}" for i in range(1, 31)),
        *(f"EV-GL-{i:03d}" for i in range(1, 17)),
    }
    vault_stats = {"total": 60, "siggi_count": 14, "cn_count": 30, "global_count": 16}

    market_sizing_summary = {
        "calc_tag": "[MKT-CALC]",
        "segments": [],
        "horizon_totals": {
            "2026-2030": {
                "baseline": {
                    "tam_units": 100,
                    "tam_cny_wan": 51000.0,
                    "sam_units": 75,
                    "sam_cny_wan": 38250.0,
                    "som_units": 24,
                    "som_cny_wan": 11500.0,
                }
            },
            "2031-2036": {
                "baseline": {
                    "tam_units": 180,
                    "tam_cny_wan": 86400.0,
                    "sam_units": 135,
                    "sam_cny_wan": 64800.0,
                    "som_units": 44,
                    "som_cny_wan": 21000.0,
                }
            },
        },
        "grand_total_10yr_baseline_som_cny_wan": 32500.0,
        "grand_total_10yr_baseline_som_units": 68,
    }
    evaluated_wedges = [
        {
            "seed": _make_wedge_candidate(wedge_id="W-EOR-01", sector="S1_pipeline_ship_eor").model_dump(),
            "roi": {
                "calc_tag": "[ROI-CALC]",
                "capex_cny": 4_200_000.0,
                "gross_annual_benefit_cny": 3_000_000.0,
                "net_annual_cashflow_cny": 2_740_000.0,
                "payback_months": 18.4,
                "roi_3yr_pct": 95.7,
                "npv_5yr_cny": 6_200_000.0,
                "irr_5yr_pct": 58.2,
                "payback_tier": "12-24个月(明确正向商业可行)",
            },
        }
    ]
    eliminated_wedges = [
        {
            "wedge_id": "W-S4-FOOD-CTRL",
            "sector": "S4_food_beverage_dryice",
            "title": "中国常规食品饮料级CO2离线抽检替代",
            "baseline_payback_months": 68.5,
            "conservative_payback_months": 92.0,
            "elimination_reason": "客户价格极度敏感且无强制在线监管，回收期超过42个月阈值",
            "evidence_ids": ["EV-SIGGI-001"],
        }
    ]

    full_body = (
        "# 中国CCUS市场V&F IMR-MS战略报告（详版）\n\n"
        "本卷依据 [EV-SIGGI-001]、[EV-SIGGI-002, EV-CN-001; EV-GL-001] 形成确定性结论：\n"
        "- 市场规模 `[MKT-CALC]`：2026–2036 十年基准 SOM 合计 68 套，对应人民币 32500.0 万元（3.25 亿元）。\n"
        "- 财务模型 `[ROI-CALC]`：核心 EOR 管道场景基准回收期 18.4 个月。\n"
        "- 双轨交付：覆盖 Track A（奥地利原装核心主机 TRACK_A_IMPORTED_CORE）与 "
        "Track B（本土化防爆分析小屋 TRACK_B_LOCALIZED_QAS / VF-QAS-CN），并兼顾 Track C 离岸船运枢纽。\n"
        "- 伪需求淘汰披露：明确淘汰 S4 食品饮料级 CO2 离线抽检场景（W-S4-FOOD-CTRL），避免幸存者偏差。\n"
    )
    exec_body = (
        "# 中国CCUS市场V&F IMR-MS战略报告（高管精简版）\n\n"
        "核心摘要 [EV-SIGGI-001, EV-CN-002; EV-GL-002]：\n"
        "- `[MKT-CALC]` 十年基准 SOM 为 32500.0 万元（3.25 亿元，68 套）。\n"
        "- `[ROI-CALC]` 回收期 18.4 个月，执行 Track A + Track B（VF-QAS-CN）双轨切入。\n"
        "- 明确淘汰 S4 食品饮料级伪需求（W-S4-FOOD-CTRL）。\n"
    )

    return {
        "contract": contract,
        "vault_stats": vault_stats,
        "valid_ids": valid_ids,
        "full_drafts": {name: full_body for name in volume_names},
        "executive_drafts": {name: exec_body for name in volume_names},
        "market_sizing_summary": market_sizing_summary,
        "evaluated_wedges": evaluated_wedges,
        "eliminated_wedges": eliminated_wedges,
        "dropped_unverified_records": [],
    }


def test_s7_deterministic_full_audit_passes_when_dual_edition_and_math_are_valid() -> None:
    """5 卷详版 + 5 卷高管版齐全、引用全部合规、十年 SOM/ROI 与伪需求披露一致时，审计必须通过。"""
    fx = _build_valid_audit_fixture()
    report = run_deterministic_full_audit(**fx)

    assert isinstance(report, DeterministicAuditReport)
    assert report.passed is True
    assert report.dual_edition_complete is True
    assert report.numeric_consistency_passed is True
    assert report.dual_track_covered is True
    assert report.eliminated_wedges_disclosed is True
    assert report.invalid_citations_by_volume == {}
    assert report.numeric_discrepancies == []
    assert report.failed_gates == []


def test_s7_deterministic_full_audit_fails_when_executive_volume_is_missing() -> None:
    """高管精简版缺失任意一卷时，passed 与 dual_edition_complete 必须为 False 并在 failed_gates 报出。"""
    fx = _build_valid_audit_fixture()
    fx["executive_drafts"].pop("04_ACTION_ROADMAP_30_60_90_AND_12_24M.md")

    report = run_deterministic_full_audit(**fx)
    assert report.passed is False
    assert report.dual_edition_complete is False
    assert len(report.failed_gates) >= 1


def test_s7_deterministic_full_audit_catches_forged_id_inside_multi_id_bracket() -> None:
    """组合引用括号 [EV-SIGGI-001, EV-CN-999] 中混入 1 个伪造 ID 时，必须拦截并在 invalid_citations_by_volume 报出。"""
    fx = _build_valid_audit_fixture()
    target_vol = "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md"
    fx["full_drafts"][target_vol] += "\n补充竞品对比见 [EV-SIGGI-001, EV-CN-999]。\n"

    report = run_deterministic_full_audit(**fx)
    assert report.passed is False
    all_reported_invalid = {
        ev_id for ids in report.invalid_citations_by_volume.values() for ev_id in ids
    }
    assert "EV-CN-999" in all_reported_invalid
    assert len(report.failed_gates) >= 1


def test_s7_deterministic_full_audit_catches_10yr_som_numeric_discrepancy() -> None:
    """报告中 [MKT-CALC] 十年基准 SOM 金额与 market_sizing_summary 不一致时，必须拦截并报出 numeric_discrepancies。"""
    fx = _build_valid_audit_fixture()
    for edition_key in ("full_drafts", "executive_drafts"):
        for vol_name, text in list(fx[edition_key].items()):
            fx[edition_key][vol_name] = (
                text.replace("32500.0", "98765.0")
                .replace("3.25", "9.88")
                .replace("68 套", "999 套")
            )

    report = run_deterministic_full_audit(**fx)
    assert report.passed is False
    assert report.numeric_consistency_passed is False
    assert len(report.numeric_discrepancies) >= 1
    assert len(report.failed_gates) >= 1
