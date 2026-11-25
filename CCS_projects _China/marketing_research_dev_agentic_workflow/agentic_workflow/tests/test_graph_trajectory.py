"""End-to-End v2.0 4-Stage Trajectory & Native CLI Spine Tests (Offline Deterministic Mocks)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Type

import pytest
from pydantic import BaseModel

from vf_ccus_workflow.cli import (
    _cmd_apply_arbitration,
    _cmd_export_schemas,
    _cmd_finalize,
    _cmd_screen_and_size,
)
from vf_ccus_workflow.config import CostLedger, WorkflowSettings
from vf_ccus_workflow.graph import build_vf_ccus_graph
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.schemas import (
    BuyerPersonaCritique,
    ChinaCCUSProjectItem,
    CommercialWedgeCandidate,
    CompetitiveEcosystemDossier,
    CompetitorProfile,
    CritiqueIssue,
    DiscoveryPlan,
    EvidenceSearchHit,
    PACIntegratorProfile,
    PortfolioArbitrationOutput,
    RankedWedgeDecision,
    ROIInputs,
    SectorDossier,
    SegmentSizingInput,
    SingleVolumeCriticOutput,
    TrackBuyerResistanceCard,
    TrackPlan,
)
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault


class MockSearchRouter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: str,
        query: str,
        mode: str = "webpage",
        num_results: int = 8,
    ):
        self.calls.append(f"{track_id}:{geo_scope}:{query[:25]}")
        hits = []
        # Return enough unique records to satisfy contract quality gates offline
        count = 6 if geo_scope == "CN" else 4
        for idx in range(count):
            seq = len(self.calls) * 10 + idx
            if geo_scope == "CN":
                hits.append(
                    EvidenceSearchHit(
                        title=f"中国CCUS示范与标准检索 ({track_id} #{seq})",
                        url=f"https://example.cn/{track_id}/{seq}",
                        snippet="齐鲁石化-胜利油田、大亚湾及绿色甲醇项目需要ppm级在线杂质监控。",
                        source_engine="metaso",
                        geo_scope="CN",
                    )
                )
            else:
                hits.append(
                    EvidenceSearchHit(
                        title=f"Global CCS Purity Spec ({track_id} #{seq})",
                        url=f"https://example.org/{track_id}/{seq}",
                        snippet="Northern Lights & Brevik CO2 stream monitoring with V&F IMR-MS.",
                        source_engine="serper",
                        geo_scope="GLOBAL",
                    )
                )
        return hits

    async def read_fulltext(self, *, url: str, track_id: str) -> str:
        return ""


class MockLLMClientV2:
    def __init__(self) -> None:
        self.critic_loops_by_vol: dict[str, int] = {}

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 6000,
    ) -> str:
        is_exec = node.startswith("distill_exec_")
        edition_label = "高密度高管版" if is_exec else "原始详版"
        # Quote exact deterministic [MKT-CALC] & [ROI-CALC] figures injected in Fact Sheet
        return (
            f"# {node} 战略卷宗（{edition_label}）\n\n"
            "基于 [EV-SIGGI-001, EV-CN-001; EV-GL-001] 的核验证据，本卷严格采用 "
            "Track A (`TRACK_A_IMPORTED_CORE`) + Track B (`TRACK_B_LOCALIZED_QAS` / VF-QAS-CN) + "
            "Track C (`TRACK_C_AUSTRIA_PREMIERGUARD`) 三轨架构。\n"
            "- `[MKT-CALC]` 十年(2026-2036) 基准情景累计 SOM：**12 台套 / ¥5,040 万元（约 ¥0.50 亿元）**。\n"
            "- `[ROI-CALC]` 核心管网防腐场景基准回收期 **16.4 个月**。\n"
            "- 反幸存者偏差：明确淘汰 S4 食品饮料级 CO2 离线抽检伪需求 (`W-T4_FOOD-01`)。\n"
            + ("技术细节、竞品对比、防爆分析小屋本土化路径与 30-60-90 天行动计划。" * (6 if is_exec else 20))
        )

    async def complete_structured(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.15,
        max_tokens: int = 6000,
    ):
        name = schema.__name__
        if name == "DiscoveryPlan":
            return DiscoveryPlan(
                contract_id="VF-CCUS-CHINA-2026-V2",
                profile="fast",
                macro_recon_summary="Macro recon complete",
                step_back_thesis="Focus on corrosive EOR pipelines, LCO2 shipping & green methanol.",
                track_plans=[
                    TrackPlan(
                        track_id="T1_EOR",
                        track_kind="sector",
                        sector="S1_pipeline_ship_eor",
                        name="EOR Pipe",
                        research_hypothesis="Corrosion guard",
                        cn_queries=["q1", "q2"],
                        global_queries=["gq1"],
                    ),
                    TrackPlan(
                        track_id="T2_MEOH",
                        track_kind="sector",
                        sector="S2_green_methanol_ccu_chem",
                        name="Green Methanol",
                        research_hypothesis="Catalyst protection",
                        cn_queries=["q3", "q4"],
                        global_queries=["gq2"],
                    ),
                    TrackPlan(
                        track_id="T3_COMP_PAC",
                        track_kind="competitive_ecosystem",
                        sector="S1_pipeline_ship_eor",
                        name="Competitors & PAC",
                        research_hypothesis="Verify FTIR/GC blind spots & Ex shelter OEMs",
                        cn_queries=["q5"],
                        global_queries=["gq3"],
                    ),
                    TrackPlan(
                        track_id="T4_FOOD",
                        track_kind="sector",
                        sector="S4_food_beverage_dryice",
                        name="Food CO2 Control",
                        research_hypothesis="Negative control",
                        cn_queries=["q6"],
                        global_queries=["gq4"],
                    ),
                ],
            )
        if name == "CompetitiveEcosystemDossier":
            return CompetitiveEcosystemDossier(
                track_id="T3_COMP_PAC",
                track_name="Competitors & PAC",
                key_findings_summary="Verified competitor & PAC ecosystem",
                competitors=[
                    CompetitorProfile(
                        vendor_name="Thermo Fisher MAX-iR/MAX-Bev",
                        origin_category="Overseas_FTIR_Optical_GC",
                        verified_models_and_tech="FTIR + O2/Sulfur (~10min)",
                        detectable_species_and_speed="FTIR batch",
                        blind_spots_vs_vf_imr_ms="No H2/Ar/N2",
                        china_ccus_presence_and_pricing_position="Imported",
                        win_strategy_for_vf="1s continuous IMR-MS",
                        evidence_ids=["EV-SIGGI-002"],
                    )
                ],
                pac_integrators=[
                    PACIntegratorProfile(
                        company_name="聚光科技(FPI)",
                        core_capabilities="GB/T 3836防爆分析小屋成套",
                        certifications_and_qualifications="Ex d/p + 石油化工准入",
                        cooperation_fit_with_vf="Track B OEM 核心伙伴",
                        evidence_ids=["EV-CN-001"],
                    )
                ],
                design_institute_spec_barriers=["SEI/HQC PID 标准入册门槛"],
                evidence_ids=["EV-SIGGI-002", "EV-CN-001"],
            )
        if name == "SectorDossier":
            tid = "T1_EOR" if "T1_EOR" in node else ("T2_MEOH" if "T2_MEOH" in node else "T4_FOOD")
            sec = (
                "S1_pipeline_ship_eor"
                if tid == "T1_EOR"
                else ("S2_green_methanol_ccu_chem" if tid == "T2_MEOH" else "S4_food_beverage_dryice")
            )
            sub_seg = (
                "onshore_pipeline_eor"
                if tid == "T1_EOR"
                else ("green_methanol_esaf" if tid == "T2_MEOH" else "food_grade_control")
            )
            verdict = "DEPRIORITIZE_OR_PSEUDO_DEMAND" if tid == "T4_FOOD" else "GO_HIGH_PRIORITY"
            gross_corr = 180_000 if tid == "T4_FOOD" else 2_100_000
            return SectorDossier(
                track_id=tid,
                sector=sec,  # type: ignore[arg-type]
                track_name=tid,
                key_findings_summary="Grounded mining result",
                named_projects=[
                    ChinaCCUSProjectItem(
                        project_name=f"项目-{tid}",
                        owner_and_epc="中石化/SEI",
                        province_or_region="山东",
                        sector=sec,  # type: ignore[arg-type]
                        capacity_mtpa_or_scale="1.0 Mtpa",
                        status_2026="运行",
                        co2_impurity_profile_and_risk="NOx/SOx/H2S/H2O",
                        recommended_delivery_track="TRACK_B_LOCALIZED_QAS",
                        evidence_ids=["EV-SIGGI-001"],
                    )
                ],
                competitors=[],
                sizing_inputs=(
                    [
                        SegmentSizingInput(
                            sector=sec,  # type: ignore[arg-type]
                            sub_segment=sub_seg,
                            horizon="2026-2030",
                            addressable_project_or_line_count=20,
                            stations_per_project=2.0,
                            primary_delivery_track="TRACK_B_LOCALIZED_QAS",
                            technical_fit_ratio=0.75,
                            realistic_som_win_rate=0.20,
                            evidence_ids=["EV-CN-001"],
                        )
                    ]
                    if tid != "T4_FOOD"
                    else []
                ),
                wedges=[
                    CommercialWedgeCandidate(
                        wedge_id=f"W-{tid}-01",
                        track_id=tid,
                        sector=sec,  # type: ignore[arg-type]
                        horizon="2026-2030",
                        delivery_track="TRACK_B_LOCALIZED_QAS",
                        title=f"切入场景-{tid}",
                        verdict=verdict,  # type: ignore[arg-type]
                        china_priority_score=90.0 if tid != "T4_FOOD" else 8.0,
                        vf_moat_score=92.0 if tid != "T4_FOOD" else 40.0,
                        target_process_point="管道总管",
                        chemical_pain_point_and_imr_advantage="酸露点腐蚀防中毒",
                        recommended_vf_sku_and_localization="VF-QAS-CN",
                        key_competing_alternatives="FTIR+GC",
                        roi_baseline=ROIInputs(
                            capex_cny=4_200_000,
                            avoided_corrosion_and_shutdown_loss_cny_yr=gross_corr,
                            avoided_catalyst_poison_or_flaring_cny_yr=700_000 if tid != "T4_FOOD" else 80_000,
                            avoided_manual_lab_and_multi_gc_opex_cny_yr=350_000 if tid != "T4_FOOD" else 50_000,
                            ccer_or_export_compliance_upside_cny_yr=180_000 if tid != "T4_FOOD" else 20_000,
                            annual_opex_cny_yr=260_000,
                        ),
                        evidence_ids=["EV-SIGGI-001"],
                    )
                ],
                evidence_ids=["EV-SIGGI-001"],
            )
        if name == "PortfolioArbitrationOutput":
            personas = [
                "三大油/央企CCUS工程公司工艺与压缩防腐总工",
                "设计院(SEI/HQC/CPECC/天辰)分析仪表室主任与EPC包采经理",
                "煤化工/水泥/绿醇项目业主EHS、碳核查与财务ROI决策人",
                "大型CCUS分析小屋集成商与运维总包负责人",
            ]
            return PortfolioArbitrationOutput(
                deduped_ranked_wedges=[
                    RankedWedgeDecision(
                        final_rank=1,
                        canonical_wedge_id="W-T1_EOR-01",
                        merged_from_wedge_ids=["W-T1_EOR-01"],
                        global_priority_score=93.5,
                        ranking_rationale="超临界管道酸露点点蚀秒级切断为绝对物理刚需且回收期仅16.4个月。",
                    ),
                    RankedWedgeDecision(
                        final_rank=2,
                        canonical_wedge_id="W-T2_MEOH-01",
                        merged_from_wedge_ids=["W-T2_MEOH-01"],
                        global_priority_score=90.0,
                        ranking_rationale="绿醇催化剂硫穿透亚秒级防护价值高、十五五项目密集落地。",
                    ),
                ],
                track_buyer_matrix=[
                    TrackBuyerResistanceCard(
                        scenario_group="Track B 超临界管道与绿醇工业成套",
                        delivery_track="TRACK_B_LOCALIZED_QAS",
                        persona_critiques=[
                            BuyerPersonaCritique(
                                persona_role=p,
                                verdict="CONDITIONAL_试点",
                                primary_concern="防爆资质与长期稳定性核验",
                                procurement_or_spec_barrier="设计院 PID 规范入册",
                                vf_winning_hook="Northern Lights / Brevik 实绩与本土 PAC 联手交付",
                            )
                            for p in personas
                        ],
                        consensus_gtm_implication="采用 Track B 双轨本土化防爆小屋突破 EPC 价格与资质壁垒。",
                    )
                ],
                executive_synthesis_thesis="聚焦超临界管网防腐与绿醇催化剂防毒，坚决剔除食品级离线抽检伪需求。",
            )
        if name == "SingleVolumeCriticOutput":
            vol_prefix = node.split("_")[-1]
            vol_map = {
                "00": "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
                "01": "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
                "02": "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
                "03": "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
                "04": "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
            }
            vol_name = vol_map.get(vol_prefix, "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md")
            seen_turns = self.critic_loops_by_vol.get(vol_name, 0) + 1
            self.critic_loops_by_vol[vol_name] = seen_turns
            if vol_prefix == "00" and seen_turns == 1:
                return SingleVolumeCriticOutput(
                    volume_name=vol_name,
                    passed=False,
                    overall_assessment="Trigger 1 targeted CRAG gap search on China supercritical CO2 standard.",
                    issues=[
                        CritiqueIssue(
                            volume_name=vol_name,
                            severity="major",
                            description="Need CN pipeline CO2 purity standard citation",
                            required_fix_action="Add CN standard reference cleanly",
                            needs_crag_gap_search=True,
                            suggested_query="中国 超临界 CO2 输送 杂质 团标 国标",
                            suggested_geo_scope="CN",
                        )
                    ],
                    needs_rewrite=True,
                )
            return SingleVolumeCriticOutput(
                volume_name=vol_name,
                passed=True,
                overall_assessment="Full-text audit passed with zero citation or numeric discrepancies.",
                issues=[],
                needs_rewrite=False,
            )
        raise ValueError(f"Unhandled schema in mock: {name}")


@pytest.mark.asyncio
async def test_v2_end_to_end_graph_trajectory_and_dual_editions(tmp_path: Path) -> None:
    """Verify 4-stage graph runs cleanly, executes 1 bounded CRAG rewrite, and writes BOTH Full & Executive editions."""
    settings = WorkflowSettings.load()
    ledger = CostLedger()
    vault = EvidenceVault(tmp_path / "traj_vault.db")
    out_dir = tmp_path / "outputs"
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=MockSearchRouter(),  # type: ignore[arg-type]
        llm=MockLLMClientV2(),
        semaphore=asyncio.Semaphore(4),
    )
    try:
        graph = build_vf_ccus_graph(deps)
        final_state = await graph.ainvoke(
            {
                "run_id": "test-v2-traj-01",
                "profile": "fast",
                "sector_filter": "all",
                "hitl_enabled": False,
                "output_dir": str(out_dir),
                "vault_db_path": str(vault.db_path),
            },
            config={"configurable": {"thread_id": "test-v2-traj-01"}},
        )
        assert final_state["stage_gate_passed"] is True, final_state.get("audit_report")
        assert final_state["critique_loop_count"] == 2
        assert len(final_state["eliminated_wedges"]) == 1  # T4_FOOD control eliminated cleanly
        assert len(final_state["pac_integrators_catalog"]) == 1  # Dedicated competitive track

        # Verify Full Edition (5 vols) + Executive Edition (5 vols) + Vol 05 + Vol 06
        for fname in (
            "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
            "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
            "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
            "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
            "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
        ):
            assert (out_dir / fname).exists()
            assert (out_dir / "executive_edition" / fname).exists()

        assert (out_dir / "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md").exists()
        sc_path = out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
        assert sc_path.exists()
        sc = json.loads(sc_path.read_text(encoding="utf-8"))
        assert sc["schema_version"] == "2.0"
        assert sc["deterministic_audit_report"]["dual_edition_complete"] is True
        assert sc["deterministic_audit_report"]["numeric_consistency_passed"] is True
    finally:
        vault.close()


def test_native_hybrid_cli_spine_end_to_end_offline(tmp_path: Path) -> None:
    """Verify the exact Python CLI spine invoked by Antigravity Native Hybrid (`export-schemas` -> `finalize`)."""
    settings = WorkflowSettings.load()
    vault_db = tmp_path / "native_spine.db"
    schemas_out = tmp_path / "v2_flat_schemas.json"

    assert _cmd_export_schemas(settings, output_file=str(schemas_out)) == 0
    exported = json.loads(schemas_out.read_text(encoding="utf-8"))
    for key in (
        "DiscoveryPlan",
        "SectorDossier",
        "CompetitiveEcosystemDossier",
        "PortfolioArbitrationOutput",
        "VolumeMarkdownOutput",
        "SingleVolumeCriticOutput",
    ):
        assert key in exported
        assert "$ref" not in json.dumps(exported[key])

    # Populate real SQLite vault meeting contract evidence gates
    vault = EvidenceVault(vault_db)
    try:
        for i in range(1, 15):
            vault.upsert_hit(
                track_id="SIGGI_BASE",
                hit=EvidenceSearchHit(
                    title=f"Siggi {i}",
                    url=f"siggi-corpus://s#{i}",
                    snippet=f"Siggi evidence {i}",
                    source_engine="siggi_mcp",
                    geo_scope="SIGGI",
                ),
            )
        for i in range(1, 28):
            vault.upsert_hit(
                track_id="T1_EOR_PIPE",
                hit=EvidenceSearchHit(
                    title=f"CN {i}",
                    url=f"https://example.cn/{i}",
                    snippet=f"CN evidence {i}",
                    source_engine="metaso",
                    geo_scope="CN",
                ),
            )
        for i in range(1, 17):
            vault.upsert_hit(
                track_id="T2_LCO2_SHIP",
                hit=EvidenceSearchHit(
                    title=f"GL {i}",
                    url=f"https://example.org/{i}",
                    snippet=f"GL evidence {i}",
                    source_engine="serper",
                    geo_scope="GLOBAL",
                ),
            )
    finally:
        vault.close()

    dossiers_file = tmp_path / "stage1_dossiers.json"
    dossiers_file.write_text(
        json.dumps(
            {
                "sector_dossiers": [
                    {
                        "track_id": "T1_EOR_PIPE",
                        "sector": "S1_pipeline_ship_eor",
                        "track_name": "EOR Pipe",
                        "key_findings_summary": "Summary",
                        "named_projects": [],
                        "competitors": [],
                        "sizing_inputs": [
                            {
                                "sector": "S1_pipeline_ship_eor",
                                "sub_segment": "onshore_pipeline_eor",
                                "horizon": "2026-2030",
                                "addressable_project_or_line_count": 28,
                                "stations_per_project": 2.5,
                                "primary_delivery_track": "TRACK_B_LOCALIZED_QAS",
                                "technical_fit_ratio": 0.80,
                                "realistic_som_win_rate": 0.25,
                                "evidence_ids": ["EV-CN-001"],
                            }
                        ],
                        "wedges": [
                            {
                                "wedge_id": "W-EOR-01",
                                "track_id": "T1_EOR_PIPE",
                                "sector": "S1_pipeline_ship_eor",
                                "horizon": "2026-2030",
                                "delivery_track": "TRACK_B_LOCALIZED_QAS",
                                "title": "超临界CO2管网酸雾点蚀联锁切断",
                                "verdict": "GO_HIGH_PRIORITY",
                                "china_priority_score": 92.0,
                                "vf_moat_score": 95.0,
                                "target_process_point": "干线首站",
                                "chemical_pain_point_and_imr_advantage": "1s监测H2S/NOx/SOx",
                                "recommended_vf_sku_and_localization": "VF-QAS-CN",
                                "key_competing_alternatives": "FTIR/GC",
                                "roi_baseline": {
                                    "capex_cny": 4200000,
                                    "avoided_corrosion_and_shutdown_loss_cny_yr": 2400000,
                                    "avoided_catalyst_poison_or_flaring_cny_yr": 400000,
                                    "avoided_manual_lab_and_multi_gc_opex_cny_yr": 300000,
                                    "ccer_or_export_compliance_upside_cny_yr": 200000,
                                    "annual_opex_cny_yr": 260000,
                                },
                                "evidence_ids": ["EV-SIGGI-001", "EV-CN-001"],
                            }
                        ],
                        "evidence_ids": ["EV-SIGGI-001", "EV-CN-001"],
                    },
                    {
                        "track_id": "T2_LCO2_SHIP",
                        "sector": "S1_pipeline_ship_eor",
                        "track_name": "LCO2 Ship",
                        "key_findings_summary": "Ship summary",
                        "named_projects": [],
                        "competitors": [],
                        "sizing_inputs": [
                            {
                                "sector": "S1_pipeline_ship_eor",
                                "sub_segment": "lco2_export_vessel_hub",
                                "horizon": "2026-2030",
                                "addressable_project_or_line_count": 15,
                                "stations_per_project": 2.0,
                                "primary_delivery_track": "TRACK_C_AUSTRIA_PREMIERGUARD",
                                "technical_fit_ratio": 0.80,
                                "realistic_som_win_rate": 0.25,
                                "evidence_ids": ["EV-GL-001"],
                            }
                        ],
                        "wedges": [
                            {
                                "wedge_id": "W-FOOD-CTRL",
                                "track_id": "T2_LCO2_SHIP",
                                "sector": "S4_food_beverage_dryice",
                                "horizon": "2026-2030",
                                "delivery_track": "TRACK_A_IMPORTED_CORE",
                                "title": "食品级离线抽检对照",
                                "verdict": "DEPRIORITIZE_OR_PSEUDO_DEMAND",
                                "china_priority_score": 5.0,
                                "vf_moat_score": 30.0,
                                "target_process_point": "槽车抽检",
                                "chemical_pain_point_and_imr_advantage": "无支付意愿",
                                "recommended_vf_sku_and_localization": "Track A",
                                "key_competing_alternatives": "离线GC",
                                "roi_baseline": {
                                    "capex_cny": 1800000,
                                    "avoided_corrosion_and_shutdown_loss_cny_yr": 100000,
                                    "avoided_catalyst_poison_or_flaring_cny_yr": 100000,
                                    "avoided_manual_lab_and_multi_gc_opex_cny_yr": 100000,
                                    "ccer_or_export_compliance_upside_cny_yr": 50000,
                                    "annual_opex_cny_yr": 180000,
                                },
                                "evidence_ids": ["EV-SIGGI-001"],
                            }
                        ],
                        "evidence_ids": ["EV-GL-001"],
                    },
                ],
                "competitive_dossiers": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    screened_file = tmp_path / "stage2_screened.json"
    assert (
        _cmd_screen_and_size(
            settings,
            dossiers_file=str(dossiers_file),
            profile="flagship",
            vault_db=str(vault_db),
            output_file=str(screened_file),
        )
        == 0
    )
    screened = json.loads(screened_file.read_text(encoding="utf-8"))
    # Both S1 sub-segments (Track B & Track C) preserved!
    assert len(screened["market_sizing_summary"]["segments"]) == 2
    som_units = screened["market_sizing_summary"]["grand_total_10yr_baseline_som_units"]
    som_wan = screened["market_sizing_summary"]["grand_total_10yr_baseline_som_cny_wan"]
    top_pb = screened["shortlist"][0]["roi"]["payback_months"]

    arb_file = tmp_path / "stage2_arb.json"
    arb_file.write_text(
        json.dumps(
            {
                "deduped_ranked_wedges": [
                    {
                        "final_rank": 1,
                        "canonical_wedge_id": "W-EOR-01",
                        "merged_from_wedge_ids": ["W-EOR-01"],
                        "global_priority_score": 94.0,
                        "ranking_rationale": "超临界管网酸雾点蚀秒级切断为首选刚需场景。",
                    }
                ],
                "track_buyer_matrix": [
                    {
                        "scenario_group": "Track B 管网",
                        "delivery_track": "TRACK_B_LOCALIZED_QAS",
                        "persona_critiques": [
                            {
                                "persona_role": f"Role {idx}",
                                "verdict": "STRONG_BUY",
                                "primary_concern": "防腐",
                                "procurement_or_spec_barrier": "防爆认证",
                                "vf_winning_hook": "1s 响应",
                            }
                            for idx in range(4)
                        ],
                        "consensus_gtm_implication": "双轨本土化交付。",
                    }
                ],
                "executive_synthesis_thesis": "主攻超临界管网与LCO2出口船运。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    locked_file = tmp_path / "stage2_locked.json"
    assert (
        _cmd_apply_arbitration(
            settings,
            screened_file=str(screened_file),
            arbitration_file=str(arb_file),
            profile="flagship",
            vault_db=str(vault_db),
            output_file=str(locked_file),
        )
        == 0
    )
    locked = json.loads(locked_file.read_text(encoding="utf-8"))
    assert len(locked["volume_evidence_bundles"]) == 5

    vol_names = [
        "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
        "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
        "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
        "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
    ]
    sample_md = (
        "# 报告正文\n\n"
        f"核验证据 [EV-SIGGI-001, EV-CN-001; EV-GL-001]。\n"
        f"`[MKT-CALC]` 十年基准 SOM：{som_units} 台套 / ¥{som_wan:.1f} 万元。\n"
        f"`[ROI-CALC]` 基准回收期：{top_pb:.1f} 个月。\n"
        "双轨架构：Track A + Track B (VF-QAS-CN) + Track C。\n"
        "伪需求淘汰：W-FOOD-CTRL。\n"
    )
    final_bundle_file = tmp_path / "final_bundle.json"
    final_bundle_file.write_text(
        json.dumps(
            {
                "run_id": "native-cli-test",
                "profile": "flagship",
                "evaluated_wedges": locked["evaluated_wedges"],
                "eliminated_wedges": locked["eliminated"],
                "dropped_unverified_records": locked["dropped_unverified_records"],
                "market_sizing_summary": locked["market_sizing_summary"],
                "volumes": {v: sample_md for v in vol_names},
                "executive_volumes": {v: sample_md for v in vol_names},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "native_out"
    assert (
        _cmd_finalize(
            settings,
            bundle_file=str(final_bundle_file),
            vault_db=str(vault_db),
            output_dir=str(out_dir),
        )
        == 0
    )
    for v in vol_names:
        assert (out_dir / v).exists()
        assert (out_dir / "executive_edition" / v).exists()
    assert (out_dir / "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md").exists()
    assert (out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").exists()


def test_apply_portfolio_arbitration_anchors_merged_alias_without_dropping_rank1() -> None:
    """When Arbitrator invents a new merged canonical_wedge_id, anchor to merged_from_wedge_ids[0]."""
    from vf_ccus_workflow.nodes.storm_and_rank import apply_portfolio_arbitration
    from vf_ccus_workflow.tools.market_and_roi_calculator import screen_wedge_pool

    c1 = CommercialWedgeCandidate(
        wedge_id="W_T1_01_PIPE_ACID_REDOX",
        track_id="T1_EOR_PIPE",
        sector="S1_pipeline_ship_eor",
        horizon="2026-2030",
        delivery_track="TRACK_B_LOCALIZED_QAS",
        title="超临界管道酸露点点蚀切断",
        verdict="GO_HIGH_PRIORITY",
        china_priority_score=90.0,
        vf_moat_score=94.0,
        target_process_point="首站总管",
        chemical_pain_point_and_imr_advantage="1s监测H2S/NOx/SOx",
        recommended_vf_sku_and_localization="VF-QAS-CN",
        key_competing_alternatives="FTIR/GC",
        roi_baseline=ROIInputs(
            capex_cny=4_200_000,
            avoided_corrosion_and_shutdown_loss_cny_yr=2_400_000,
            avoided_catalyst_poison_or_flaring_cny_yr=400_000,
            avoided_manual_lab_and_multi_gc_opex_cny_yr=300_000,
            ccer_or_export_compliance_upside_cny_yr=200_000,
            annual_opex_cny_yr=260_000,
        ),
        evidence_ids=["EV-SIGGI-001", "EV-CN-001"],
    )
    c2 = c1.model_copy(
        update={
            "wedge_id": "W_T1_03_EOR_RECYCLE_NETWORK",
            "title": "EOR循环伴生气监控",
            "evidence_ids": ["EV-CN-002"],
        }
    )
    shortlist, _ = screen_wedge_pool([c1, c2], target_total=5)
    arb = PortfolioArbitrationOutput(
        deduped_ranked_wedges=[
            RankedWedgeDecision(
                final_rank=1,
                canonical_wedge_id="W_T1_PIPE_EOR_QAS",  # New merged alias!
                merged_from_wedge_ids=["W_T1_01_PIPE_ACID_REDOX", "W_T1_03_EOR_RECYCLE_NETWORK"],
                global_priority_score=91.0,
                ranking_rationale="合并管网与EOR循环伴生气场景，确立第一优先级。",
            )
        ],
        track_buyer_matrix=[
            TrackBuyerResistanceCard(
                scenario_group="Track B 管网",
                delivery_track="TRACK_B_LOCALIZED_QAS",
                persona_critiques=[
                    BuyerPersonaCritique(
                        persona_role=f"Role {i}",
                        verdict="STRONG_BUY",
                        primary_concern="防腐",
                        procurement_or_spec_barrier="防爆",
                        vf_winning_hook="1s",
                    )
                    for i in range(4)
                ],
                consensus_gtm_implication="双轨推进。",
            )
        ],
        executive_synthesis_thesis="聚焦超临界管网防腐与EOR循环伴生气实时保护，确立首选切入组合。",
    )
    ranked = apply_portfolio_arbitration([e.model_dump() for e in shortlist], arb)
    assert len(ranked) == 1
    assert ranked[0]["composite_rank"] == 1
    assert ranked[0]["seed"]["wedge_id"] == "W_T1_01_PIPE_ACID_REDOX"
    assert set(ranked[0]["merged_from_wedge_ids"]) == {
        "W_T1_01_PIPE_ACID_REDOX",
        "W_T1_03_EOR_RECYCLE_NETWORK",
    }
    assert "EV-CN-002" in ranked[0]["seed"]["evidence_ids"]
