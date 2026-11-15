"""End-to-end LangGraph trajectory evaluation with mocked Search & LLM (Ch 19 Layer 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Type, TypeVar

import pytest
from pydantic import BaseModel

from pso_workflow.config import CostLedger, WorkflowSettings
from pso_workflow.graph import build_workflow_graph
from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.nodes.storm_and_rank import EloPairDecision
from pso_workflow.schemas import (
    BuyerPersonaAssessment,
    CritiqueIssue,
    CritiqueVerdict,
    DiscoveredTrack,
    DiscoveryPlan,
    JudgeRubricScores,
    OpportunityStormMemo,
    PainPointItem,
    ResearchPlan,
    ROIRangeInputs,
    SearchHit,
    TechOpportunitySeed,
    TrackDossier,
    TrackQueryPlan,
)
from pso_workflow.tools.evidence_vault import EvidenceVault

TModel = TypeVar("TModel", bound=BaseModel)


class MockSearchRouter:
    """Deterministic mock search returning realistic CN and GLOBAL hits."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: Literal["CN", "GLOBAL"],
        query: str,
        mode: str = "webpage",
        num_results: int = 8,
    ) -> list[SearchHit]:
        self.calls.append((track_id, geo_scope, query))
        domain = "semi.org" if geo_scope == "GLOBAL" else "miit.gov.cn"
        engine = "serper" if geo_scope == "GLOBAL" else "metaso"
        return [
            SearchHit(
                engine=engine,
                geo_scope=geo_scope,
                query=query,
                title=f"{track_id} {geo_scope} Inline Testing Standard ({len(self.calls)}-{idx})",
                url=f"https://{domain}/{track_id.lower()}/{geo_scope.lower()}/{len(self.calls)}/{idx}",
                snippet=f"Verified evidence snippet for {track_id} in {geo_scope}: yield +0.5%, payback < 14 months.",
                published_date="2026-08-15",
            )
            for idx in range(4)
        ]

    async def read_fulltext(self, *, url: str, track_id: str) -> str:
        return f"# Fulltext for {track_id}\n\nDetailed metrology specifications from {url}.\n" * 6


class MockLLMClient:
    """Deterministic LLM stub tracking node invocations and exercising Critic loop transitions."""

    def __init__(self, settings: WorkflowSettings, *, force_infinite_rewrite: bool = False) -> None:
        self.settings = settings
        self.force_infinite_rewrite = force_infinite_rewrite
        self.critic_calls = 0
        self.node_calls: list[str] = []

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
        self.node_calls.append(node)
        return (
            f"# {node} 深度分析报告 (V3.0)\n\n"
            f"## 中国市场优先分析与海内外在售与国产空白对照（3-5年与5-10年）\n"
            f"基于证据 [EV-CN-001] 与海外在售与国产空白对照，结合 [ROI-CALC] 计算结果显示投资回收期优于行业阈值。\n\n"
            f"## 全球市场跟进与 AI计算传感与FPGA边缘协同 落地路径\n"
            f"结合欧美半导体与电力合规标准 [EV-GL-001]，通过 AI计算传感与FPGA边缘协同 将研发周期从36个月压缩至12个月，覆盖 3-5年(2027-2031) 与 5-10年(2031-2036) 演进。\n"
            + ("详细工程论证、在售竞品盘点、国产BOM替代与四大价值支柱分析。" * 25)
        )

    async def complete_structured(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        temperature: float = 0.15,
        max_tokens: int = 6000,
    ) -> TModel:
        self.node_calls.append(node)

        if schema is DiscoveryPlan:
            dynamic_specs = [
                ("DP1", "power_energy", "固态电池干法电极与产线在线监测", False, ""),
                ("DP2", "power_energy", "特高压环保气体(C4F7N)分解物在线检测", False, ""),
                ("DP3", "power_energy", "海缆绝缘老化与局放原位在线诊断", False, ""),
                (
                    "DP4",
                    "power_energy",
                    "AI算力中心800V HVDC与液冷绝缘在线监测",
                    True,
                    "AI算力中心机柜功率密度跃升催生800V直流微电弧与冷板微漏交叉检测需求",
                ),
                ("DS1", "semiconductor", "先进晶圆厂AMC微量分子污染与湿化特气监测", False, ""),
                ("DS2", "semiconductor", "前道纳米光学与X射线薄膜量测", False, ""),
                ("DS3", "semiconductor", "SiC/GaN宽禁带功率芯片晶圆级动态KGD测试", False, ""),
                (
                    "DS4",
                    "semiconductor",
                    "CPO硅光共封装与玻璃基板TGV三维互连无损检测",
                    True,
                    "Stage 0 信号显示AI光互连与TGV通孔良率成为2026-2031新兴瓶颈",
                ),
            ]
            return DiscoveryPlan(
                contract_id="PSO-CONTRACT-2026-V3",
                sector_filter="all",
                profile="flagship",
                macro_recon_summary="Stage 0 广谱扫描发现新型电力与AI封装交叉在线监测新机会及海内外商业化空白。",
                step_back_thesis="From physical degradation mechanisms & commercial white-space to AI-accelerated inline closed-loop metrology.",
                track_plans=[
                    DiscoveredTrack(
                        track_id=tid,
                        sector=sec,  # type: ignore[arg-type]
                        name=name,
                        step_back_physics_principle=f"First-principles physics sensing for {tid}",
                        is_emerging_or_cross_cutting=emg,
                        emergence_rationale=rat,
                        recon_evidence_ids=[],
                        manufacturing_stages=[f"{tid}核心制造工段A", f"{tid}封装/并网检测工段B"],
                        cn_queries=[{"query": f"中国 {name} 在线检测 痛点 招标", "scope": "webpage"}],
                        global_queries=[{"query": f"{name} inline metrology yield ROI", "endpoint": "search"}],
                        cn_vendor_queries=[{"query": f"中国 {name} 在线检测 设备厂商 中标型号 国产替代", "scope": "webpage"}],
                        global_vendor_queries=[{"query": f"{name} commercial inline metrology vendor instrument model", "endpoint": "search"}],
                    )
                    for tid, sec, name, emg, rat in dynamic_specs
                ],
            )  # type: ignore[return-value]

        if schema is ResearchPlan:
            tracks = self.settings.taxonomy.get("tracks", [])
            return ResearchPlan(
                contract_id="PSO-CONTRACT-2026-V1",
                sector_filter="all",
                profile="fast",
                step_back_thesis="From physical degradation mechanisms to inline closed-loop metrology.",
                track_plans=[
                    TrackQueryPlan(
                        track_id=t["id"],
                        sector=t["sector"],
                        name=t["name"],
                        step_back_physics_principle=f"Physics principle for {t['id']}",
                        cn_queries=t["cn_queries"][:1],
                        global_queries=t["global_queries"][:1],
                    )
                    for t in tracks
                ],
            )  # type: ignore[return-value]

        if schema is TrackDossier:
            tid = node.replace("researcher_", "")
            sec = "semiconductor" if tid.startswith(("DS", "S")) else "power_energy"
            capex_mult = 1.4 if sec == "semiconductor" else 1.0
            cands = []
            for c_idx in range(1, 4):
                horizon = "5-10y" if c_idx == 2 else "3-5y"
                comm_status = (
                    "overseas_only_cn_blank",
                    "global_and_cn_true_blank",
                    "global_and_cn_commercialized",
                )[c_idx - 1]
                # Make O3 slower payback (~34m) so deterministic Stage 2 capacity funnel prioritizes O1/O2 cleanly
                capex_base = (900_000.0 if c_idx < 3 else 4_800_000.0) * capex_mult
                yield_base = 0.55 if c_idx < 3 else 0.35
                cands.append(
                    TechOpportunitySeed(
                        opp_id=f"{tid}-O{c_idx}",
                        track_id=tid,
                        sector=sec,  # type: ignore[arg-type]
                        title=f"{tid} 候选在线测试装备方案 #{c_idx} ({horizon})",
                        horizon=horizon,  # type: ignore[arg-type]
                        china_priority_score=93.0 - c_idx * 4.0,
                        global_priority_score=89.0 - c_idx * 3.0,
                        physics_principle=f"{tid} 多物理场无损在线探测原理 #{c_idx}",
                        target_process_point=f"{tid} 关键工艺工段 #{c_idx}",
                        product_form_factor="产线在线/旁路闭环集成系统",
                        quality_yield_mechanism="毫秒级缺陷拦截并阻断批量逃逸",
                        cost_tco_mechanism="降低返工报废、耗材与非计划停机损失",
                        green_ehs_mechanism="削减有害排放、化学废液与单位能耗",
                        industrial_upgrade_mechanism="实现国产高端量检测核心装备自主闭环",
                        china_positioning="中国标杆产线优先 Spec-in 放量",
                        global_expansion_path="随中国产能及 IEC/SEMI 标准认证出海",
                        commercial_status=comm_status,  # type: ignore[arg-type]
                        global_vendors_and_products=(
                            "尚未检索到量产在售整机（疑似空白）"
                            if comm_status == "global_and_cn_true_blank"
                            else "海外龙头已有产线方案（以 [EV-GL-001] 实证记录为准）"
                        ),
                        china_vendors_and_products=(
                            "国内已有在售常规机型 [EV-CN-001]，缺乏AI原位实时闭环版本"
                            if comm_status == "global_and_cn_commercialized"
                            else "尚未检索到国产成熟量产在售整机（疑似空白）"
                        ),
                        white_space_and_entry_wedge="聚焦国产空白或全球原位空白工段切入产线闭环控制。",
                        ai_computational_sensing_and_co_design="PINN物理反演+AI超分辨计算传感以算代硬降低光学/射频BOM成本35%。",
                        ai_rd_acceleration_and_edge_deployment="合成缺陷样本冷启动 + AI辅助FPGA/EDA开发 + 断网产线NPU边缘推理与Golden-Tool自校准。",
                        estimated_rd_months_ai_vs_legacy="AI协同研发 12-16个月 vs 传统模式 36-42个月",
                        hardware_bom_localization_and_gtm_form="国产FPGA/ADC/激光模组替代；先OEM旁路模块切入后升级整机ATE。",
                        evidence_ids=[],
                        roi_range_inputs=ROIRangeInputs(
                            capex_cny_low=capex_base * 0.85,
                            capex_cny_base=capex_base,
                            capex_cny_high=capex_base * 1.20,
                            yield_gain_pct_low=yield_base * 0.80,
                            yield_gain_pct_base=yield_base,
                            yield_gain_pct_high=yield_base * 1.25,
                            annual_output_value_cny=360_000_000.0 if sec == "semiconductor" else 280_000_000.0,
                            annual_opex_cny=capex_base * 0.08,
                            annual_scrap_saving_cny=320_000.0,
                            annual_downtime_saving_cny=180_000.0,
                            annual_consumable_ehs_saving_cny=90_000.0,
                            market_tam_china_cny_100m=24.0,
                            market_tam_global_usd_m=620.0,
                            parameter_basis=f"Mock range anchored to {tid} inline metrology benchmark",
                        ),
                    )
                )
            return TrackDossier(
                track_id=tid,
                sector=sec,  # type: ignore[arg-type]
                track_name=f"{tid} 动态发现赛道",
                china_market_dynamics="中国市场扩产与良率爬坡驱动在线检测加速。",
                global_market_dynamics="全球先进制造与碳中和法规推动高端在线仪表普及。",
                commercial_landscape_summary="海外头部企业在部分标准节点已商业化，但原位AI计算传感与国产高端段仍存显著空白。",
                horizon_3_5y_outlook="3-5年聚焦高ROI国产空白替代与产线在线闭环。",
                horizon_5_10y_outlook="5-10年向非接触原位量子/太赫兹/软电离质谱跃迁。",
                pain_points=[
                    PainPointItem(
                        process_stage=f"{tid} 核心工段",
                        geo_scope="CN",
                        pain_description="离线抽检滞后导致批量不良风险。",
                        current_limitation="响应慢、耗材贵",
                        impact_pillars=["质量良率", "成本ROI"],
                        evidence_ids=[],
                    )
                ],
                opportunities=cands,
                evidence_count_cn=2,
                evidence_count_global=2,
                top_evidence_ids=[],
            )  # type: ignore[return-value]

        if schema is OpportunityStormMemo:
            oid = node.replace("storm_", "")
            roles = [
                "Fab/Plant Yield VP",
                "Metrology/Process Chief Engineer",
                "EHS & Green Compliance Director",
                "CFO / Procurement ROI Gatekeeper",
            ]
            return OpportunityStormMemo(
                opp_id=oid,
                buyer_assessments=[
                    BuyerPersonaAssessment(
                        persona_role=r,  # type: ignore[arg-type]
                        core_question=f"{r} 关注在线实时性与误报率",
                        adoption_barrier="需兼容现有产线节拍与协议",
                        spec_in_trigger="提供对比测试与良率验证",
                        recommended_product_tweak="增加自动校准旁路模块",
                    )
                    for r in roles
                ],
                sharpest_pain_point_summary="离线抽检无法拦截连续工艺漂移。",
                key_localization_or_export_moat="核心传感器自主可控叠加本地化维保。",
            )  # type: ignore[return-value]

        if schema is EloPairDecision:
            # Extract first quoted opp_id in prompt
            import re
            ids = re.findall(r"\[Option [AB]: ([^\]]+)\]", user_prompt)
            return EloPairDecision(
                winner_id=ids[0] if ids else "OPP-P1-3Y-01",
                rationale="在制造端投资回收期与良率杠杆上具备更强直接经济性 [ROI-CALC]。",
            )  # type: ignore[return-value]

        if schema is CritiqueVerdict:
            self.critic_calls += 1
            if self.force_infinite_rewrite:
                return CritiqueVerdict(
                    decision="needs_rewrite",
                    overall_confidence=70.0,
                    summary="Forced rewrite to verify hard loop termination.",
                    issues=[
                        CritiqueIssue(
                            severity="major",
                            section="00_",
                            issue_type="prose_quality",
                            description="Expand summary details.",
                        )
                    ],
                )  # type: ignore[return-value]
            if self.critic_calls == 1:
                return CritiqueVerdict(
                    decision="needs_more_evidence",
                    overall_confidence=78.0,
                    summary="Need additional evidence on SiC KGD before final approval.",
                    issues=[
                        CritiqueIssue(
                            severity="major",
                            section="02_",
                            issue_type="missing_evidence",
                            description="Add SiC wafer dynamic KGD evidence.",
                            suggested_query="SiC wafer level KGD dynamic test China",
                        )
                    ],
                    gap_queries=[
                        {
                            "track_id": "DS3",
                            "geo_scope": "CN",
                            "query": "碳化硅晶圆级动态KGD测试中国产线进展",
                        }
                    ],
                )  # type: ignore[return-value]
            return CritiqueVerdict(
                decision="pass",
                overall_confidence=94.0,
                summary="All contract requirements and citations satisfied.",
                issues=[],
            )  # type: ignore[return-value]

        if schema is JudgeRubricScores:
            return JudgeRubricScores(
                china_first_then_global_depth=18.5,
                dual_horizon_3_5y_vs_5_10y_rigor=18.0,
                pain_point_and_physics_specificity=18.5,
                roi_and_industrial_upgrade_value=19.0,
                citation_grounding_and_prose=18.0,
                total_score=92.0,
                executive_verdict="PASS: High-quality grounded output.",
                strengths=["China-first + Global structure", "Deterministic [ROI-CALC] metrics"],
                residual_risks=["Verify field calibration cycles during pilot deployment"],
            )  # type: ignore[return-value]

        raise AssertionError(f"Unexpected schema {schema}")


@pytest.mark.asyncio
async def test_full_graph_trajectory_with_corrective_rag_loop(tmp_path: Path) -> None:
    settings = WorkflowSettings.load()
    ledger = CostLedger()
    vault = EvidenceVault(tmp_path / "vault.db")
    search_router = MockSearchRouter()
    llm = MockLLMClient(settings)
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=search_router,
        llm=llm,
    )
    out_dir = tmp_path / "outputs"

    try:
        graph = build_workflow_graph(deps)
        result = await graph.ainvoke(
            {
                "run_id": "test-traj-01",
                "sector_filter": "all",
                "profile": "fast",
                "output_dir": str(out_dir),
                "hitl_enabled": False,
                "max_loops": 2,
                "loop_count": 0,
                "recent_query_hashes": [],
                "track_dossiers": [],
                "draft_reports": {},
                "critique_history": [],
                "telemetry_events": [],
            }
        )

        # Verify Stage 0 RECON + all 8 dynamic tracks executed via parallel Send()
        assert any(c[0] == "RECON" for c in search_router.calls)
        dossiers = result["track_dossiers"]
        assert len(dossiers) == 8
        assert {d["track_id"] for d in dossiers} == {"DP1", "DP2", "DP3", "DP4", "DS1", "DS2", "DS3", "DS4"}

        # Verify Stage 2 deterministic funnel screening (24 raw -> 8 fast shortlist, 16 eliminated)
        assert result["raw_candidates_count"] == 24
        assert len(result["evaluated_opportunities"]) == 8
        assert len(result["eliminated_candidates"]) == 16
        assert result["evaluated_opportunities"][0].get("roi_range") is not None

        # Verify Corrective RAG loop executed once on DS3 then passed
        assert result["loop_count"] == 1
        assert llm.critic_calls == 2
        assert any(c[0] == "DS3" and ("KGD" in c[2] or "碳化硅" in c[2]) for c in search_router.calls)

        # Verify all 7 deliverable files written
        expected_files = [
            "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
            "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
            "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
            "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
            "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
            "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md",
            "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json",
        ]
        for fname in expected_files:
            assert (out_dir / fname).exists(), f"Missing {fname}"

        scorecard = json.loads((out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").read_text())
        assert scorecard["workflow_version"] == "V3.0_COMMERCIAL_WHITESPACE_AND_AI_CO_DESIGN"
        assert scorecard["deterministic_contract_checks"]["commercial_whitespace_grounded"] is True
        assert scorecard["deterministic_contract_checks"]["ai_native_paradigm_present"] is True
        assert "commercial_whitespace_breakdown" in scorecard
        assert len(scorecard["discovered_tracks"]) == 8
        assert scorecard["discovery_funnel_summary"]["raw_candidates_count"] == 24
        assert scorecard["stage_gate_passed"] is True
        assert scorecard["judge_rubric"]["total_score"] == 92.0
    finally:
        vault.close()


@pytest.mark.asyncio
async def test_hard_loop_cutoff_prevents_infinite_reflection(tmp_path: Path) -> None:
    settings = WorkflowSettings.load()
    vault = EvidenceVault(tmp_path / "vault_cutoff.db")
    deps = RuntimeDeps(
        settings=settings,
        ledger=CostLedger(),
        vault=vault,
        search_router=MockSearchRouter(),
        llm=MockLLMClient(settings, force_infinite_rewrite=True),
    )
    out_dir = tmp_path / "outputs_cutoff"

    try:
        graph = build_workflow_graph(deps)
        result = await graph.ainvoke(
            {
                "run_id": "test-cutoff-01",
                "sector_filter": "power",
                "profile": "fast",
                "output_dir": str(out_dir),
                "hitl_enabled": False,
                "max_loops": 1,
                "loop_count": 0,
                "recent_query_hashes": [],
                "track_dossiers": [],
                "draft_reports": {},
                "critique_history": [],
                "telemetry_events": [],
            }
        )
        # With max_loops=1, critic runs twice (loop 0 -> rewrite -> loop 1 -> cutoff to judge)
        assert result["loop_count"] == 2
        assert len(result["track_dossiers"]) == 4
        assert (out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").exists()
    finally:
        vault.close()


@pytest.mark.asyncio
async def test_prepare_context_and_finalize_native_roundtrip(tmp_path: Path) -> None:
    from pso_workflow.cli import _cmd_finalize_native, _cmd_prepare_context

    settings = WorkflowSettings.load()
    settings.data_dir = tmp_path / "data"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    vault = EvidenceVault(settings.data_dir / "evidence_vault.db")
    try:
        # Seed >= 48 synthetic evidences across CN and GLOBAL so prepare-context avoids network calls
        idx = 0
        for tid in ("P1", "P2", "P3", "P4", "S1", "S2", "S3", "S4"):
            for geo in ("CN", "GLOBAL"):
                for j in range(4):
                    idx += 1
                    vault.upsert_hit(
                        track_id=tid,
                        hit=SearchHit(
                            engine="metaso" if geo == "CN" else "serper",
                            geo_scope=geo,  # type: ignore[arg-type]
                            query=f"{tid} {geo}",
                            title=f"{tid} {geo} Evidence {j}",
                            url=f"https://example.org/{tid}/{geo}/{idx}",
                            snippet="Verified inline testing evidence.",
                        ),
                    )
    finally:
        vault.close()

    ctx_file = tmp_path / "ctx.json"
    rc_prep = await _cmd_prepare_context(settings, "all", str(ctx_file))
    assert rc_prep == 0
    ctx = json.loads(ctx_file.read_text(encoding="utf-8"))
    assert ctx["vault_stats"]["total"] == 64
    assert len(ctx["tracks"]) == 8

    # Build a synthetic native bundle matching all 16 calibrated seeds + 5 volumes
    track_results = []
    elo_matches = []
    all_seeds = []
    for t in ctx["tracks"]:
        opps = []
        for s in t["seeds"]:
            all_seeds.append(s)
            opps.append(
                {
                    "opp_id": s["opp_id"],
                    "title": s["title"],
                    "evidence_ids": t["valid_ev_ids"][:2],
                    "storm": {
                        "sharpest_pain_point_summary": "误报率门限与回本周期控制",
                        "key_localization_or_export_moat": "原位快速响应",
                        "buyer_assessments": [
                            {
                                "persona_role": "CFO / Procurement ROI Gatekeeper",
                                "core_question": "多快回收投资？",
                                "adoption_barrier": "CAPEX审批周期",
                                "spec_in_trigger": "回收期<=18个月",
                                "recommended_product_tweak": "旁路免停线安装",
                            }
                        ],
                    },
                }
            )
        track_results.append({"track_id": t["id"], "sector": t["sector"], "opportunities": opps})

    if len(all_seeds) >= 2:
        elo_matches.append(
            {
                "round_idx": 1,
                "opp_a_id": all_seeds[0]["opp_id"],
                "opp_b_id": all_seeds[1]["opp_id"],
                "winner_id": all_seeds[0]["opp_id"],
                "rationale": "ROI回收期更短且良率贡献更大。",
            }
        )

    vol_body = (
        "## 中国市场（优先）\n3-5年与5-10年技术机会 [EV-CN-001]，[ROI-CALC] 回收期优于行业标准。\n"
        "## 全球市场（跟进）\n对标欧美标准 [EV-GL-001]，支撑产业升级与环保减排。\n"
        + ("工程量化分析。" * 60)
    )
    bundle = {
        "run_id": "test-native-01",
        "sector_filter": "all",
        "profile": "flagship",
        "llm_engine": "antigravity_native:pro",
        "track_results": track_results,
        "elo_matches": elo_matches,
        "volumes": {
            "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md": "# 00\n" + vol_body,
            "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md": "# 01\n" + vol_body,
            "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md": "# 02\n" + vol_body,
            "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md": "# 03\n" + vol_body,
            "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md": "# 04\n" + vol_body,
        },
        "critique_loops_executed": 0,
        "critique_history": [],
        "judge_rubric": {
            "china_first_then_global_depth": 19.0,
            "dual_horizon_3_5y_vs_5_10y_rigor": 18.5,
            "pain_point_and_physics_specificity": 18.5,
            "roi_and_industrial_upgrade_value": 19.0,
            "citation_grounding_and_prose": 18.0,
            "total_score": 93.0,
            "executive_verdict": "PASS",
            "strengths": ["Strong grounding"],
            "residual_risks": ["Pilot calibration"],
        },
        "native_agent_invocations": {"planner": 1, "track_analysts_and_storm": 8},
    }
    bundle_file = tmp_path / "bundle.json"
    bundle_file.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "native_out"

    rc_fin = _cmd_finalize_native(settings, str(bundle_file), str(out_dir))
    assert rc_fin == 0
    for fn in (
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
        "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
        "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
        "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
        "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md",
        "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json",
    ):
        assert (out_dir / fn).exists()
    sc = json.loads((out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").read_text(encoding="utf-8"))
    assert sc["stage_gate_passed"] is True
    assert sc["llm_engine"] == "antigravity_native:pro"
    assert len(sc["evaluated_opportunities_top10"]) == 10


@pytest.mark.asyncio
async def test_v2_cli_funnel_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pso_workflow.cli as cli_mod
    from pso_workflow.cli import (
        _cmd_finalize_v2,
        _cmd_gap_search,
        _cmd_recon_search,
        _cmd_screen_candidates,
        _cmd_track_search,
    )

    settings = WorkflowSettings.load()
    settings.root_dir = tmp_path
    settings.data_dir = tmp_path / "data"
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    mock_router = MockSearchRouter()
    monkeypatch.setattr(cli_mod, "DualEngineSearchRouter", lambda s, l: mock_router)

    vault_name = "evidence_vault_v2.db"
    recon_file = tmp_path / "data/v2_recon_context.json"
    rc_rec = await _cmd_recon_search(
        settings,
        sector="all",
        profile="fast",
        vault_db=vault_name,
        output_file=str(recon_file),
    )
    assert rc_rec == 0
    recon_ctx = json.loads(recon_file.read_text(encoding="utf-8"))
    assert len(recon_ctx["recon_evidences"]) > 0
    recon_ev_ids = [r["ev_id"] for r in recon_ctx["recon_evidences"][:2]]

    plan_file = tmp_path / "data/v3_discovery_plan.json"
    plan_payload = {
        "contract_id": "PSO-CONTRACT-2026-V3",
        "sector_filter": "all",
        "profile": "fast",
        "macro_recon_summary": "Stage 0 offline mock recon clustered 4 dynamic tracks.",
        "step_back_thesis": "Inline metrology converts passive inspection into yield feedback.",
        "track_plans": [
            {
                "track_id": "DP1",
                "sector": "power_energy",
                "name": "固态电池界面在线超声监测",
                "step_back_physics_principle": "Ultrasonic time-of-flight attenuation",
                "is_emerging_or_cross_cutting": False,
                "emergence_rationale": "Signal clustered from battery yields",
                "recon_evidence_ids": recon_ev_ids,
                "manufacturing_stages": ["叠片与等静压工段"],
                "cn_queries": [{"query": "中国 固态电池 超声 在线检测", "scope": "webpage"}],
                "global_queries": [{"query": "solid state battery ultrasonic inline inspection", "endpoint": "search"}],
                "cn_vendor_queries": [{"query": "中国 固态电池 超声 检测 设备厂商 中标", "scope": "webpage"}],
                "global_vendor_queries": [{"query": "solid state battery ultrasonic vendor instrument model", "endpoint": "search"}],
            },
            {
                "track_id": "DP2",
                "sector": "power_energy",
                "name": "AI算力中心800V HVDC液冷在线绝缘监测",
                "step_back_physics_principle": "High-frequency partial discharge & leakage current sensing",
                "is_emerging_or_cross_cutting": True,
                "emergence_rationale": "Cross-cutting AI IDC power inflection",
                "recon_evidence_ids": recon_ev_ids,
                "manufacturing_stages": ["母排测试工段"],
                "cn_queries": [{"query": "中国 800V HVDC 液冷 在线监测", "scope": "webpage"}],
                "global_queries": [{"query": "800V HVDC data center inline insulation monitoring", "endpoint": "search"}],
                "cn_vendor_queries": [{"query": "中国 800V 直流 局放 监测 厂商 型号", "scope": "webpage"}],
                "global_vendor_queries": [{"query": "800V HVDC inline partial discharge vendor model", "endpoint": "search"}],
            },
            {
                "track_id": "DS1",
                "sector": "semiconductor",
                "name": "前道湿法化学与AMC在线质谱监控",
                "step_back_physics_principle": "Soft ionization PTR-MS / ion mobility spectrometry",
                "is_emerging_or_cross_cutting": False,
                "emergence_rationale": "Cleanroom AMC traceability",
                "recon_evidence_ids": recon_ev_ids,
                "manufacturing_stages": ["EUV光刻与湿法清洗"],
                "cn_queries": [{"query": "中国 晶圆厂 AMC 在线质谱", "scope": "webpage"}],
                "global_queries": [{"query": "semiconductor fab AMC online PTR-MS", "endpoint": "search"}],
                "cn_vendor_queries": [{"query": "中国 晶圆厂 AMC 质谱 国产 厂商 型号", "scope": "webpage"}],
                "global_vendor_queries": [{"query": "semiconductor fab AMC monitor vendor IONICON Tofwerk", "endpoint": "search"}],
            },
            {
                "track_id": "DS2",
                "sector": "semiconductor",
                "name": "CPO硅光共封装与TGV激光超声在线测试",
                "step_back_physics_principle": "Laser ultrasound + optical interferometry",
                "is_emerging_or_cross_cutting": True,
                "emergence_rationale": "Emerging CPO/TGV metrology bottleneck",
                "recon_evidence_ids": recon_ev_ids,
                "manufacturing_stages": ["TGV深孔与键合"],
                "cn_queries": [{"query": "中国 CPO 硅光 TGV 在线检测", "scope": "webpage"}],
                "global_queries": [{"query": "CPO silicon photonics TGV inline metrology", "endpoint": "search"}],
                "cn_vendor_queries": [{"query": "中国 TGV 玻璃基板 在线 检测 设备厂商 型号", "scope": "webpage"}],
                "global_vendor_queries": [{"query": "TGV glass substrate inline metrology vendor Onto KLA", "endpoint": "search"}],
            },
        ],
    }
    plan_file.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tracks_ev_file = tmp_path / "data/v2_tracks_evidence.json"
    rc_trk = await _cmd_track_search(
        settings,
        plan_file=str(plan_file),
        profile="fast",
        vault_db=vault_name,
        output_file=str(tracks_ev_file),
    )
    assert rc_trk == 0
    tracks_ev = json.loads(tracks_ev_file.read_text(encoding="utf-8"))
    assert len(tracks_ev["tracks"]) == 4

    # Construct raw dossiers WITHOUT nested track_id/sector on opportunities to verify TrackDossier propagation
    raw_dossiers = []
    for entry in tracks_ev["tracks"]:
        tp = entry["track"]
        tid = tp["track_id"]
        sec = tp["sector"]
        evs = entry["valid_ev_ids"][:2]
        opps = []
        for idx in (1, 2, 3):
            capex = (950_000.0 if idx < 3 else 4_500_000.0) * (1.3 if sec == "semiconductor" else 1.0)
            ygain = 0.55 if idx < 3 else 0.30
            comm_st = (
                "overseas_only_cn_blank",
                "global_and_cn_true_blank",
                "global_and_cn_commercialized",
            )[idx - 1]
            opps.append(
                {
                    "opp_id": f"{tid}-O{idx}",
                    "title": f"{tp['name']} 在线方案 {idx}",
                    "horizon": "5-10y" if idx == 2 else "3-5y",
                    "china_priority_score": 92.0 - idx * 4.0,
                    "global_priority_score": 88.0 - idx * 3.0,
                    "physics_principle": tp["step_back_physics_principle"],
                    "target_process_point": tp["manufacturing_stages"][0],
                    "product_form_factor": "Inline bypass module",
                    "quality_yield_mechanism": "Early inline defect arrest",
                    "cost_tco_mechanism": "Eliminate scrap and downtime",
                    "green_ehs_mechanism": "Cut chemical waste",
                    "industrial_upgrade_mechanism": "Closed-loop native fab control",
                    "china_positioning": "China Tier-1 pilot first",
                    "global_expansion_path": "IEC/SEMI standard export",
                    "commercial_status": comm_st,
                    "global_vendors_and_products": "海外头部企业商用机型 [EV-GL-001]" if comm_st != "global_and_cn_true_blank" else "尚未检索到量产在售整机（疑似空白）",
                    "china_vendors_and_products": "国产现有成熟产品 [EV-CN-001]" if comm_st == "global_and_cn_commercialized" else "尚未检索到量产在售整机（疑似空白）",
                    "white_space_and_entry_wedge": "以AI计算传感降低光机BOM门槛并从国产空白切入产线闭环。",
                    "ai_computational_sensing_and_co_design": "PINN反演+压缩重构降低精密硬件成本40%。",
                    "ai_rd_acceleration_and_edge_deployment": "合成缺陷样本冷启动 + AI辅助FPGA开发 + 产线断网Edge-AI与Golden-Tool自校准。",
                    "estimated_rd_months_ai_vs_legacy": "AI协同研发 12-16个月 vs 传统模式 36-42个月",
                    "hardware_bom_localization_and_gtm_form": "国产FPGA/ADC替代；OEM模块切入。",
                    "evidence_ids": evs,
                    "roi_range_inputs": {
                        "capex_cny_low": capex * 0.85,
                        "capex_cny_base": capex,
                        "capex_cny_high": capex * 1.20,
                        "yield_gain_pct_low": ygain * 0.80,
                        "yield_gain_pct_base": ygain,
                        "yield_gain_pct_high": ygain * 1.25,
                        "annual_output_value_cny": 350_000_000.0,
                        "annual_opex_cny": capex * 0.08,
                        "annual_scrap_saving_cny": 260_000.0,
                        "annual_downtime_saving_cny": 140_000.0,
                        "annual_consumable_ehs_saving_cny": 70_000.0,
                        "market_tam_china_cny_100m": 20.0,
                        "market_tam_global_usd_m": 500.0,
                        "parameter_basis": "roundtrip test range",
                    },
                }
            )
        raw_dossiers.append(
            {
                "track_id": tid,
                "sector": sec,
                "track_name": tp["name"],
                "china_market_dynamics": "中国产线良率需求迫切。",
                "global_market_dynamics": "全球先进制造同步升级。",
                "commercial_landscape_summary": "海外局部在售而国产高端与原位AI协同工段空白明显。",
                "horizon_3_5y_outlook": "3-5年国产化放量。",
                "horizon_5_10y_outlook": "5-10年原位闭环跃迁。",
                "pain_points": [
                    {
                        "process_stage": tp["manufacturing_stages"][0],
                        "geo_scope": "CN",
                        "pain_description": "抽检滞后漏检风险。",
                        "current_limitation": "响应慢",
                        "impact_pillars": ["质量良率", "成本ROI"],
                        "evidence_ids": evs,
                    }
                ],
                "opportunities": opps,
            }
        )

    raw_dossiers_file = tmp_path / "data/v2_raw_dossiers.json"
    raw_dossiers_file.write_text(json.dumps({"dossiers": raw_dossiers}, ensure_ascii=False, indent=2), encoding="utf-8")

    screened_file = tmp_path / "data/v2_screened_shortlist.json"
    rc_scr = _cmd_screen_candidates(
        settings,
        dossiers_file=str(raw_dossiers_file),
        plan_file=str(plan_file),
        sector="all",
        profile="fast",
        vault_db=vault_name,
        output_file=str(screened_file),
    )
    assert rc_scr == 0
    screened = json.loads(screened_file.read_text(encoding="utf-8"))
    assert screened["raw_candidates_count"] == 12
    assert screened["shortlist_count"] == 8
    assert screened["eliminated_count"] == 4
    assert "commercial_tables" in screened

    gap_out = tmp_path / "data/v2_gap_refill.json"
    rc_gap = await _cmd_gap_search(
        settings,
        queries_arg=json.dumps([{"track_id": "DS2", "geo_scope": "CN", "query": "CPO硅光在线检测进展"}]),
        vault_db=vault_name,
        output_file=str(gap_out),
    )
    assert rc_gap == 0

    vol_body = (
        "## 中国市场（优先）\n3-5年与5-10年技术机会 [EV-CN-001]，[ROI-CALC] 乐观/基准/保守回收期均满足门禁。\n"
        "海外在售与国产空白对照及AI计算传感FPGA边缘软硬件协同。\n"
        "## 全球市场（跟进）\n对标欧美标准 [EV-GL-001]，支撑产业升级与环保减排。\n"
        + ("工程量化、商业在售空白盘点与AI软硬件协同漏斗审计分析。" * 55)
    )
    v2_bundle = {
        "run_id": "test-v2-cli-01",
        "sector_filter": "all",
        "profile": "fast",
        "llm_engine": "antigravity_native:pro",
        "discovery_plan": tracks_ev["discovery_plan"],
        "dossiers": screened["cleaned_dossiers"],
        "raw_candidates_count": screened["raw_candidates_count"],
        "shortlist": screened["shortlist"],
        "eliminated_candidates": screened["eliminated_candidates"],
        "elo_matches": [
            {
                "round_idx": 1,
                "opp_a_id": screened["shortlist"][0]["seed"]["opp_id"],
                "opp_b_id": screened["shortlist"][1]["seed"]["opp_id"],
                "winner_id": screened["shortlist"][0]["seed"]["opp_id"],
                "rationale": "保守情景下依然保持较短回收期。",
            }
        ],
        "volumes": {
            "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md": "# 00\n" + vol_body,
            "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md": "# 01\n" + vol_body,
            "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md": "# 02\n" + vol_body,
            "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md": "# 03\n" + vol_body,
            "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md": "# 04\n" + vol_body,
        },
        "critique_loops_executed": 1,
        "critique_history": [],
        "judge_rubric": {
            "china_first_then_global_depth": 19.0,
            "dual_horizon_3_5y_vs_5_10y_rigor": 18.5,
            "pain_point_and_physics_specificity": 18.5,
            "roi_and_industrial_upgrade_value": 19.0,
            "citation_grounding_and_prose": 18.5,
            "total_score": 93.5,
            "executive_verdict": "PASS",
            "strengths": ["Zero-preset commercial white-space & AI co-design funnel verified"],
            "residual_risks": ["Mock test only"],
        },
        "native_agent_invocations": {"stage0": 1, "stage1": 4},
    }
    v2_bundle_file = tmp_path / "data/v2_native_outputs_bundle.json"
    v2_bundle_file.write_text(json.dumps(v2_bundle, ensure_ascii=False), encoding="utf-8")

    v2_out = tmp_path / "v2_out"
    rc_fin = _cmd_finalize_v2(
        settings,
        bundle_file=str(v2_bundle_file),
        vault_db=vault_name,
        output_dir=str(v2_out),
    )
    assert rc_fin == 0
    for fn in (
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
        "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
        "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
        "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
        "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md",
        "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json",
    ):
        assert (v2_out / fn).exists(), f"Missing {fn}"
    sc_v2 = json.loads((v2_out / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json").read_text(encoding="utf-8"))
    assert sc_v2["workflow_version"] == "V3.0_COMMERCIAL_WHITESPACE_AND_AI_CO_DESIGN"
    assert sc_v2["stage_gate_passed"] is True
    assert "commercial_whitespace_breakdown" in sc_v2
    assert sc_v2["deterministic_contract_checks"]["commercial_whitespace_grounded"] is True
    assert sc_v2["deterministic_contract_checks"]["ai_native_paradigm_present"] is True
    assert sc_v2["discovery_funnel_summary"]["raw_candidates_count"] == 12
    assert sc_v2["discovery_funnel_summary"]["eliminated_count"] == 4
