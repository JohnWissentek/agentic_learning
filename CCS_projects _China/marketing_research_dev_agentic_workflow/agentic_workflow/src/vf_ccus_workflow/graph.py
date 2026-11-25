"""LangGraph v2.0 4-Stage Bounded Cyclic StateGraph Assembly for V&F China CCS/CCUS Workflow."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from vf_ccus_workflow.config import CostLedger, WorkflowSettings
from vf_ccus_workflow.nodes.critic_and_judge import (
    node_crag_gap_and_rewrite,
    node_distill_audit_and_finalize,
    node_full_text_critic,
    route_after_critic,
)
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import node_siggi_ingest_and_planner
from vf_ccus_workflow.nodes.researcher import node_parallel_track_researcher
from vf_ccus_workflow.nodes.storm_and_rank import node_size_screen_and_arbitrate
from vf_ccus_workflow.nodes.synthesizer import node_parallel_volume_synthesizer
from vf_ccus_workflow.schemas import WorkflowState
from vf_ccus_workflow.tools.evidence_vault import EvidenceVault
from vf_ccus_workflow.tools.search_router import DualEngineSearchRouter


def build_vf_ccus_graph(deps: RuntimeDeps, *, checkpointer: Any | None = None):
    """Assemble v2.0 4-Stage Graph:
    Stage 0 (Ingest & Plan) -> Stage 1 (Parallel Orthogonal Research) ->
    Stage 2 (Deterministic Sizing/ROI & Single Flagship Arbitration) ->
    Stage 3 (Parallel Synthesis -> Bounded Full-Text Critic/CRAG -> Dual-Edition Audit & Finalize).
    """
    builder = StateGraph(WorkflowState)

    builder.add_node("siggi_ingest_and_planner", partial(node_siggi_ingest_and_planner, deps=deps))
    builder.add_node("parallel_track_researcher", partial(node_parallel_track_researcher, deps=deps))
    builder.add_node("size_screen_and_arbitrate", partial(node_size_screen_and_arbitrate, deps=deps))
    builder.add_node("parallel_volume_synthesizer", partial(node_parallel_volume_synthesizer, deps=deps))
    builder.add_node("full_text_critic", partial(node_full_text_critic, deps=deps))
    builder.add_node("crag_gap_and_rewrite", partial(node_crag_gap_and_rewrite, deps=deps))
    builder.add_node("distill_audit_and_finalize", partial(node_distill_audit_and_finalize, deps=deps))

    builder.add_edge(START, "siggi_ingest_and_planner")
    builder.add_edge("siggi_ingest_and_planner", "parallel_track_researcher")
    builder.add_edge("parallel_track_researcher", "size_screen_and_arbitrate")
    builder.add_edge("size_screen_and_arbitrate", "parallel_volume_synthesizer")
    builder.add_edge("parallel_volume_synthesizer", "full_text_critic")

    builder.add_conditional_edges(
        "full_text_critic",
        partial(route_after_critic, deps=deps),
        {
            "rewrite": "crag_gap_and_rewrite",
            "finalize": "distill_audit_and_finalize",
        },
    )
    builder.add_edge("crag_gap_and_rewrite", "full_text_critic")
    builder.add_edge("distill_audit_and_finalize", END)

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
