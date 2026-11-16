"""Offline end-to-end LangGraph trajectory test with mocked LLM & mocked search router."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel

from bfbg_workflow.config import CostLedger, WorkflowSettings
from bfbg_workflow.graph import build_boiler_fbg_graph
from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import VOLUME_SPECS
from bfbg_workflow.schemas import (
    ArchitectureEloMatch,
    CriticAuditReport,
    CriticIssue,
    EvidenceSearchHit,
    IPDReviewMemo,
    JudgeRubricScores,
    PowerPlantStormPanel,
    ProductDiscoveryPlan,
    TrackPlanItem,
    TrackResearchDossier,
)
from bfbg_workflow.tools.evidence_vault import EvidenceVault


class _MockSearchRouter:
    async def search_track(self, *, track_id: str, geo_scope: str, query: str, num_results: int = 8, use_time_filter: bool = True):
        return [
            EvidenceSearchHit(
                title=f"Mock hit {track_id} {geo_scope}",
                url=f"https://mock.local/{track_id}/{geo_scope}/{abs(hash(query))}",
                snippet=f"Verified mock evidence for {query[:40]}",
                source_engine="metaso" if geo_scope == "CN" else "serper",
                geo_scope=geo_scope,  # type: ignore[arg-type]
            )
        ]

    async def enrich_top_hits(self, hits, *, max_fetch: int = 1):
        return hits


class _MockLLM:
    def __init__(self) -> None:
        self.critic_calls = 0

    async def complete_json(
        self, *, tier: str, node: str, system_prompt: str, user_prompt: str, schema: Type[BaseModel], max_tokens: int = 4096, temperature: float = 0.15
    ) -> Any:
        if schema is ProductDiscoveryPlan:
            tracks = [
                TrackPlanItem(
                    track_id=tid,  # type: ignore[arg-type]
                    role_title=f"Role {tid}",
                    focus_mandate=f"Research {tid}",
                    cn_queries=[f"CN {tid}"],
                    global_queries=[f"GL {tid}"],
                    priority=idx + 1,
                )
                for idx, tid in enumerate(
                    [
                        "T1_MARKET_POLICY",
                        "T2_COMPETITIVE_INTEL",
                        "T3_OPTICS_HARDWARE",
                        "T4_FIBER_BOILER_PACKAGING",
                        "T5_SOFTWARE_BOILER_AI",
                        "T6_NPI_QAQC_FINANCE",
                    ]
                )
            ]
            return ProductDiscoveryPlan(
                contract_id="BFBG-IPD-CONTRACT-2026-V1",
                profile="fast",
                step_back_thesis="Dual-tier modular FBG + bypass AI",
                china_market_positioning="Competitive price & reliability",
                track_plans=tracks,
            )
        if schema is TrackResearchDossier:
            tid = node.replace("stage1_miner_", "")
            return TrackResearchDossier(
                track_id=tid,  # type: ignore[arg-type]
                role_title=f"Specialist {tid}",
                executive_findings=f"Summary for {tid}",
                key_technical_decisions=["Modular dual-tier architecture"],
                evidence_ids=["EV-CN-0001", "EV-PDF-0001"],
            )
        if schema is IPDReviewMemo:
            return IPDReviewMemo(
                overall_readiness_verdict="APPROVE_TO_PROTOTYPE",
                critical_interface_risks=["FC/APC dust contamination"],
                design_for_manufacturing_actions=["Use I-MON 512 USB OEM"],
                qa_calibration_mandates=["650C 3-zone calibration"],
                cost_down_levers=["Track B hybrid fiber"],
                evidence_ids=["EV-PDF-0001"],
            )
        if schema is PowerPlantStormPanel:
            return PowerPlantStormPanel(
                chief_engineer_concerns=["Tube leak warning lead time"],
                boiler_inspection_head_demands=["Loose-tube strain isolation"],
                ic_cybersecurity_hard_gates=["One-way optical/hardware gap"],
                cfo_procurement_thresholds=["< 12 month payback"],
                winning_value_propositions=["Dual-track pricing + Phase-1 read-only AI"],
                evidence_ids=["EV-CN-0001"],
            )
        if schema is ArchitectureEloMatch:
            return ArchitectureEloMatch(
                round_num=1,
                arch_a="ARCH_1_DUAL_TIER_MODULAR",
                arch_b="ARCH_2_PURE_RAYLEIGH_OFDR",
                winner="ARCH_1_DUAL_TIER_MODULAR",
                margin="decisive",
                rationale="Superior SNR & 2.5m fast time-to-market",
            )
        if schema is CriticAuditReport:
            self.critic_calls += 1
            if self.critic_calls == 1:
                return CriticAuditReport(
                    passed=False,
                    overall_assessment="Need extra CRAG verification on Vol 03",
                    volumes_to_rewrite=["03_COMPONENT_INTERFACES_AND_DETAILED_INTEGRATION_DESIGN.md"],
                    issues=[
                        CriticIssue(
                            volume="03_COMPONENT_INTERFACES_AND_DETAILED_INTEGRATION_DESIGN.md",
                            severity="major",
                            finding="Check Sercalo RS-232 baud rate",
                            fix_instruction="Specify 115200bps",
                            needs_crag_gap_search=True,
                            suggested_geo_scope="GLOBAL",
                            suggested_query="Sercalo SW1x16 RS232 protocol",
                        )
                    ],
                )
            return CriticAuditReport(
                passed=True,
                overall_assessment="All checks clean.",
                volumes_to_rewrite=[],
                issues=[],
            )
        if schema is JudgeRubricScores:
            return JudgeRubricScores(
                market_and_competitive_rigor=18.5,
                hardware_selection_and_interface_completeness=19.0,
                software_demod_and_boiler_ai_actionability=18.5,
                npi_qaqc_bringup_and_field_sop=18.5,
                financial_gtm_training_and_traceability=18.5,
                total_score=93.0,
                pass_status="PASS",
                executive_verdict="Production-ready IPD package.",
                key_strengths=["Verified PDFs", "Zero-LLM math"],
                remaining_gaps=[],
            )
        raise AssertionError(f"Unhandled schema: {schema}")

    async def complete_text(
        self, *, tier: str, node: str, system_prompt: str, user_prompt: str, max_tokens: int = 7500, temperature: float = 0.25
    ) -> str:
        return (
            f"# {node}\n\n"
            "Verified [EV-CN-0001] & [EV-PDF-0001] -> "
            "./datasheets_pdf/01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf\n"
        )


def test_offline_graph_trajectory_and_critic_loop(tmp_path: Path, monkeypatch) -> None:
    import bfbg_workflow.nodes.researcher as res_mod
    import bfbg_workflow.nodes.critic_and_judge as cj_mod

    monkeypatch.setattr(cj_mod, "run_diagram_generators", lambda root, out: ["mock_diagram.py"])

    orig_exec = res_mod.execute_all_tracks_and_pdfs

    async def _no_online_pdf(*args, **kwargs):
        kwargs["skip_online_pdf"] = True
        return await orig_exec(*args, **kwargs)

    monkeypatch.setattr(res_mod, "execute_all_tracks_and_pdfs", _no_online_pdf)

    settings = WorkflowSettings.load()
    vault = EvidenceVault(tmp_path / "graph_vault.db")
    out_dir = tmp_path / "output"
    try:
        deps = RuntimeDeps(
            settings=settings,
            ledger=CostLedger(),
            vault=vault,
            search_router=_MockSearchRouter(),  # type: ignore[arg-type]
            llm=_MockLLM(),
            semaphore=asyncio.Semaphore(4),
        )
        graph = build_boiler_fbg_graph(deps)
        final_state = asyncio.run(
            graph.ainvoke(
                {
                    "run_id": "test-run-1",
                    "profile": "fast",
                    "output_dir": str(out_dir),
                    "vault_db": str(tmp_path / "graph_vault.db"),
                },
                config={"configurable": {"thread_id": "test-run-1"}},
            )
        )
        assert final_state["critic_loop_count"] == 2
        assert final_state["final_manifest"]["stage_gate_total_score"] == 93.0
        for fname, *_ in VOLUME_SPECS:
            assert (out_dir / fname).exists()
        assert (out_dir / "07_VERIFIED_EVIDENCE_AND_DATASHEET_INDEX.md").exists()
        assert (out_dir / "08_EVALUATION_SCORECARD_AND_TELEMETRY.json").exists()
    finally:
        vault.close()
