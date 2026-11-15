"""LangGraph Bounded Cyclic StateGraph Assembly for V&F China CCS/CCUS Workflow."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from vf_ccus_workflow.config import CostLedger, WorkflowSettings
from vf_ccus_workflow.nodes.critic_and_judge import (
    node_adversarial_critic,
    node_crag_gap_and_rewrite,
    node_stage_gate_judge_and_finalize,
    route_after_critic,
)
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import node_siggi_ingest_and_planner
from vf_ccus_workflow.nodes.researcher import node_parallel_track_researcher
from vf_ccus_workflow.nodes.storm_and_rank import (
    node_size_screen_and_storm,
    node_swiss_elo_ranker,
)
from vf_ccus_workflow.nodes.synthesizer import node_parallel_volume_synthesizer
from vf_ccus_workflow.schemas import WorkflowState
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault
from vf_ccus_workflow.tools.search_router import DualEngineSearchRouter


def build_vf_ccus_graph(deps: RuntimeDeps, *, checkpointer: Any | None = None):
    """Assemble Stage 0a/0b -> Stage 1 -> Stage 2/3 -> Stage 4 -> Stage 5 -> Bounded Stage 6 -> Stage 7."""
    builder = StateGraph(WorkflowState)

    builder.add_node("siggi_ingest_and_planner", partial(node_siggi_ingest_and_planner, deps=deps))
    builder.add_node("parallel_track_researcher", partial(node_parallel_track_researcher, deps=deps))
    builder.add_node("size_screen_and_storm", partial(node_size_screen_and_storm, deps=deps))
    builder.add_node("swiss_elo_ranker", partial(node_swiss_elo_ranker, deps=deps))
    builder.add_node("parallel_volume_synthesizer", partial(node_parallel_volume_synthesizer, deps=deps))
    builder.add_node("adversarial_critic", partial(node_adversarial_critic, deps=deps))
    builder.add_node("crag_gap_and_rewrite", partial(node_crag_gap_and_rewrite, deps=deps))
    builder.add_node(
        "stage_gate_judge_and_finalize",
        partial(node_stage_gate_judge_and_finalize, deps=deps),
    )

    builder.add_edge(START, "siggi_ingest_and_planner")
    builder.add_edge("siggi_ingest_and_planner", "parallel_track_researcher")
    builder.add_edge("parallel_track_researcher", "size_screen_and_storm")
    builder.add_edge("size_screen_and_storm", "swiss_elo_ranker")
    builder.add_edge("swiss_elo_ranker", "parallel_volume_synthesizer")
    builder.add_edge("parallel_volume_synthesizer", "adversarial_critic")

    builder.add_conditional_edges(
        "adversarial_critic",
        partial(route_after_critic, deps=deps),
        {
            "rewrite": "crag_gap_and_rewrite",
            "judge": "stage_gate_judge_and_finalize",
        },
    )
    builder.add_edge("crag_gap_and_rewrite", "adversarial_critic")
    builder.add_edge("stage_gate_judge_and_finalize", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


def build_langgraph_app():
    """Factory entrypoint referenced by langgraph.json."""
    from vf_ccus_workflow.config import DashScopeLLMGateway

    settings = WorkflowSettings.load()
    ledger = CostLedger()
    vault = EvidenceVault(settings.default_vault_path)
    router = DualEngineSearchRouter(settings, ledger)
    llm = DashScopeLLMGateway(settings, ledger)
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=router,
        llm=llm,
        semaphore=asyncio.Semaphore(settings.concurrency),
    )
    return build_vf_ccus_graph(deps)
