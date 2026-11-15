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
    JudgeRubricScores,
    OpportunityStormMemo,
    PainPointItem,
    ResearchPlan,
    ROIInputs,
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
            f"# {node} 深度分析报告\n\n"
            f"## 中国市场优先分析（3-5年与5-10年）\n"
            f"基于证据 [EV-CN-001] 与中国产线良率提升需求，结合 [ROI-CALC] 计算结果显示投资回收期优于行业阈值。\n\n"
            f"## 全球市场跟进与出海策略\n"
            f"结合欧美半导体与电力合规标准 [EV-GL-001]，覆盖 3-5年(2027-2031) 与 5-10年(2031-2036) 技术演进。\n"
            + ("详细工程论证与四大价值支柱分析。" * 25)
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
            raw_t = next(t for t in self.settings.taxonomy["tracks"] if t["id"] == tid)
            s0 = raw_t["seed_opportunities"][0]
            return TrackDossier(
                track_id=tid,
                sector=raw_t["sector"],
                track_name=raw_t["name"],
                china_market_dynamics="中国市场本土扩产与良率爬坡驱动在线检测加速。",
                global_market_dynamics="全球先进制程与碳中和法规推动高端在线仪表普及。",
                horizon_3_5y_outlook="3-5年聚焦高ROI国产替代与产线在线闭环。",
                horizon_5_10y_outlook="5-10年向非接触原位量子/太赫兹/软电离质谱跃迁。",
                pain_points=[
                    PainPointItem(
                        process_stage=raw_t["manufacturing_stages"][0],
                        geo_scope="CN",
                        pain_description="离线抽检滞后导致批量不良风险。",
                        current_limitation="响应慢、耗材贵",
                        impact_pillars=["质量良率", "成本ROI"],
                        evidence_ids=[],
                    )
                ],
                opportunities=[
                    TechOpportunitySeed(
                        opp_id=s0["opp_id"],
                        track_id=tid,
                        sector=raw_t["sector"],
                        title=s0["title"],
                        horizon=s0["horizon"],
                        china_priority_score=s0["china_priority_score"],
                        global_priority_score=s0["global_priority_score"],
                        physics_principle=s0["physics_principle"],
                        target_process_point=raw_t["manufacturing_stages"][0],
                        product_form_factor="产线在线集成系统",
                        quality_yield_mechanism="实时阻断缺陷逃逸",
                        cost_tco_mechanism="消除耗材与停线损失",
                        green_ehs_mechanism="降低毒害气体与废液排放",
                        industrial_upgrade_mechanism="实现国产核心装备闭环",
                        china_positioning="中国示范线率先放量",
                        global_expansion_path="随产业链出海全球",
                        evidence_ids=[],
                        roi_inputs=ROIInputs(**s0["roi_baseline"]),
                    )
                ],
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
                            "track_id": "S3",
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

        # Verify all 8 tracks executed via parallel Send()
        dossiers = result["track_dossiers"]
        assert len(dossiers) == 8
        assert {d["track_id"] for d in dossiers} == {"P1", "P2", "P3", "P4", "S1", "S2", "S3", "S4"}

        # Verify Corrective RAG loop executed once then passed
        assert result["loop_count"] == 1
        assert llm.critic_calls == 2
        assert any(c[0] == "S3" and "KGD" in c[2] or "碳化硅" in c[2] for c in search_router.calls)

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
