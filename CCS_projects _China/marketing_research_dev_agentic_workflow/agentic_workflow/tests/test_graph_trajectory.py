"""End-to-End Bounded Cyclic StateGraph Trajectory Test (Offline Deterministic Mocks)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Type

import pytest
from pydantic import BaseModel

from vf_ccus_workflow.config import CostLedger, WorkflowSettings
from vf_ccus_workflow.graph import build_vf_ccus_graph
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.schemas import (
    BuyerPersonaCritique,
    ChinaCCUSProjectItem,
    CommercialWedgeCandidate,
    CompetitorProfile,
    CriticAuditOutput,
    CritiqueIssue,
    DiscoveryPlan,
    EvidenceSearchHit,
    JudgeRubricScores,
    ROIInputs,
    SegmentSizingInput,
    TrackDossier,
    TrackPlan,
    WedgeStormMemo,
)
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault


class MockSearchRouter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def search_track(self, *, track_id: str, geo_scope: str, query: str, mode: str = "webpage", num_results: int = 8):
        self.calls.append(f"{track_id}:{geo_scope}:{query[:25]}")
        if geo_scope == "CN":
            return [
                EvidenceSearchHit(
                    title=f"中国CCUS示范与标准检索 ({track_id})",
                    url=f"https://example.cn/{track_id}/{len(self.calls)}",
                    snippet="齐鲁石化-胜利油田、大亚湾及绿色甲醇项目需要ppm级在线杂质监控。",
                    source_engine="metaso",
                    geo_scope="CN",
                )
            ]
        return [
            EvidenceSearchHit(
                title=f"Global CCS Purity Spec ({track_id})",
                url=f"https://example.org/{track_id}/{len(self.calls)}",
                snippet="Northern Lights & Brevik CO2 stream monitoring with V&F IMR-MS.",
                source_engine="serper",
                geo_scope="GLOBAL",
            )
        ]

    async def read_fulltext(self, *, url: str, track_id: str) -> str:
        return ""


class MockLLMClient:
    def __init__(self) -> None:
        self.critic_turns = 0

    async def complete_text(self, *, tier: str, node: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 6000) -> str:
        return (
            f"# {node} 战略卷宗\n\n"
            "基于 [EV-SIGGI-001]、[EV-CN-001]、[EV-GL-001] 的核验证据，本报告围绕 Track A / "
            "TRACK_B_LOCALIZED_QAS (VF-QAS-CN) / Track C 三轨架构完成分析，"
            "并严格引用 `[MKT-CALC]` 与 `[ROI-CALC]` 确定性测算数值。\n"
            + ("分析详情与竞品对比、防爆分析小屋本土化路径、30-60-90天行动计划。" * 45)
        )

    async def complete_structured(self, *, tier: str, node: str, system_prompt: str, user_prompt: str, schema: Type[BaseModel], temperature: float = 0.15, max_tokens: int = 6000):
        name = schema.__name__
        if name == "DiscoveryPlan":
            return DiscoveryPlan(
                contract_id="VF-CCUS-CHINA-2026-V1",
                profile="fast",
                macro_recon_summary="Macro recon complete",
                step_back_thesis="Focus on corrosive EOR pipelines & green methanol.",
                track_plans=[
                    TrackPlan(
                        track_id="T1_EOR",
                        sector="S1_pipeline_ship_eor",
                        name="EOR Pipe",
                        research_hypothesis="Corrosion guard",
                        cn_queries=["q1", "q2"],
                        global_queries=["gq1"],
                    ),
                    TrackPlan(
                        track_id="T2_MEOH",
                        sector="S2_green_methanol_ccu_chem",
                        name="Green Methanol",
                        research_hypothesis="Catalyst protection",
                        cn_queries=["q3", "q4"],
                        global_queries=["gq2"],
                    ),
                    TrackPlan(
                        track_id="T3_FOOD",
                        sector="S4_food_beverage_dryice",
                        name="Food CO2 Control",
                        research_hypothesis="Negative control",
                        cn_queries=["q5", "q6"],
                        global_queries=["gq3"],
                    ),
                ],
            )
        if name == "TrackDossier":
            tid = "T1_EOR" if "T1_EOR" in node else ("T2_MEOH" if "T2_MEOH" in node else "T3_FOOD")
            sec = "S1_pipeline_ship_eor" if tid == "T1_EOR" else ("S2_green_methanol_ccu_chem" if tid == "T2_MEOH" else "S4_food_beverage_dryice")
            verdict = "DEPRIORITIZE_OR_PSEUDO_DEMAND" if tid == "T3_FOOD" else "GO_HIGH_PRIORITY"
            gross = 180_000 if tid == "T3_FOOD" else 1_800_000
            return TrackDossier(
                track_id=tid,
                sector=sec,  # type: ignore[arg-type]
                track_name=tid,
                key_findings_summary="Grounded mining result",
                named_projects=[
                    ChinaCCUSProjectItem(
                        project_name=f"项目-{tid}",
                        owner_and_epc="中石化/设计院",
                        province_or_region="山东",
                        sector=sec,  # type: ignore[arg-type]
                        capacity_mtpa_or_scale="1.0 Mtpa",
                        status_2026="运行",
                        co2_impurity_profile_and_risk="NOx/SOx/H2S/H2O",
                        recommended_delivery_track="TRACK_B_LOCALIZED_QAS",
                        evidence_ids=["EV-SIGGI-001"],
                    )
                ],
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
                sizing_inputs=[
                    SegmentSizingInput(
                        sector=sec,  # type: ignore[arg-type]
                        horizon="2026-2030",
                        addressable_project_or_line_count=10,
                        stations_per_project=1.5,
                        primary_delivery_track="TRACK_B_LOCALIZED_QAS",
                        evidence_ids=["EV-CN-001"],
                    )
                ],
                wedges=[
                    CommercialWedgeCandidate(
                        wedge_id=f"W-{tid}-01",
                        track_id=tid,
                        sector=sec,  # type: ignore[arg-type]
                        horizon="2026-2030",
                        delivery_track="TRACK_B_LOCALIZED_QAS",
                        title=f"切入场景-{tid}",
                        verdict=verdict,  # type: ignore[arg-type]
                        china_priority_score=90.0 if tid != "T3_FOOD" else 35.0,
                        vf_moat_score=92.0,
                        target_process_point="管道总管",
                        chemical_pain_point_and_imr_advantage="酸露点腐蚀防中毒",
                        recommended_vf_sku_and_localization="VF-QAS-CN",
                        key_competing_alternatives="FTIR+GC",
                        roi_baseline=ROIInputs(
                            capex_cny=4_200_000,
                            avoided_corrosion_and_shutdown_loss_cny_yr=gross,
                            avoided_catalyst_poison_or_flaring_cny_yr=800_000 if tid != "T3_FOOD" else 80_000,
                            avoided_manual_lab_and_multi_gc_opex_cny_yr=400_000 if tid != "T3_FOOD" else 50_000,
                            ccer_or_export_compliance_upside_cny_yr=300_000 if tid != "T3_FOOD" else 20_000,
                            annual_opex_cny_yr=260_000,
                        ),
                        evidence_ids=["EV-SIGGI-001"],
                    )
                ],
                evidence_ids=["EV-SIGGI-001"],
            )
        if name == "WedgeStormMemo":
            personas = [
                "三大油/央企CCUS工程公司工艺与压缩防腐总工",
                "设计院(SEI/HQC/CPECC/天辰)分析仪表室主任与EPC包采经理",
                "煤化工/水泥/绿醇项目业主EHS、碳核查与财务ROI决策人",
                "大型CCUS分析小屋集成商与运维总包负责人",
            ]
            return WedgeStormMemo(
                wedge_id="W-MOCK",
                persona_critiques=[
                    BuyerPersonaCritique(
                        persona_role=p,
                        verdict="CONDITIONAL_试点",
                        primary_concern="核验防爆与长期稳定运行",
                        procurement_or_spec_barrier="需要设计院PID入册",
                        vf_winning_hook="Brevik/Northern Lights背书",
                    )
                    for p in personas
                ],
                consensus_gtm_implication="通过Track B双轨合作推进设计院Spec-in。",
            )
        if name == "EloPairDecision":
            return schema.model_validate({"winner_id": "W-T1_EOR-01", "rationale": "Strongest acid corrosion ROI and pipe trigger."})
        if name == "CriticAuditOutput":
            self.critic_turns += 1
            if self.critic_turns == 1:
                return CriticAuditOutput(
                    passed=False,
                    overall_assessment="Trigger 1 CRAG gap search on China LCO2 standards.",
                    issues=[
                        CritiqueIssue(
                            volume_name="00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
                            severity="major",
                            description="Need CN pipeline CO2 standard check",
                            required_fix_action="Refill and expand",
                            needs_crag_gap_search=True,
                            suggested_query="中国 超临界 CO2 输送 杂质 团标 国标",
                            suggested_geo_scope="CN",
                        )
                    ],
                    volumes_to_rewrite=["00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md"],
                )
            return CriticAuditOutput(passed=True, overall_assessment="All volumes passed after revision.", issues=[], volumes_to_rewrite=[])
        if name == "JudgeRubricScores":
            return JudgeRubricScores(
                china_grounding_and_project_specificity=18.5,
                market_sizing_and_pain_point_rigor=18.5,
                competitive_battlecard_accuracy=18.0,
                dual_track_gtm_and_roi_actionability=18.0,
                evidence_traceability_and_prose=18.0,
                total_score=91.0,
                pass_stage_gate=True,
                executive_commentary="Stage-Gate PASS",
            )
        raise ValueError(f"Unhandled schema in mock: {name}")


@pytest.mark.asyncio
async def test_end_to_end_graph_trajectory(tmp_path: Path) -> None:
    settings = WorkflowSettings.load()
    ledger = CostLedger()
    vault = EvidenceVault(tmp_path / "traj_vault.db")
    out_dir = tmp_path / "outputs"
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=MockSearchRouter(),  # type: ignore[arg-type]
        llm=MockLLMClient(),
        semaphore=asyncio.Semaphore(4),
    )
    try:
        graph = build_vf_ccus_graph(deps)
        final_state = await graph.ainvoke(
            {
                "run_id": "test-traj-01",
                "profile": "fast",
                "sector_filter": "all",
                "hitl_enabled": False,
                "output_dir": str(out_dir),
                "vault_db_path": str(vault.db_path),
            },
            config={"configurable": {"thread_id": "test-traj-01"}},
        )
        assert final_state["stage_gate_passed"] is True
        assert final_state["critique_loop_count"] == 2
        assert len(final_state["eliminated_wedges"]) == 1  # T3_FOOD control eliminated cleanly
        assert (out_dir / "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md").exists()
        assert (out_dir / "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md").exists()
        assert (out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").exists()
    finally:
        vault.close()
