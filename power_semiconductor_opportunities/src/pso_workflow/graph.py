"""Main LangGraph StateGraph assembly (adapted from open_deep_research + STORM + Deer-Flow).

Features:
- Parallel Send() fan-out over 8 orthogonal Power & Semiconductor tracks
- Persistent SQLite checkpointer (`langgraph-checkpoint-sqlite`) for resume & time-travel
- Heterogeneous Producer-Critic reflection loop with Corrective RAG branch
- `build_studio_graph()` factory exported for `langgraph.json` (LangGraph Studio)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from pso_workflow.config import CostLedger, DashScopeLLMGateway, WorkflowSettings
from pso_workflow.nodes import (
    RuntimeDeps,
    node_corrective_rag_refill,
    node_deterministic_funnel_screener,
    node_grounded_report_synthesizer,
    node_heterogeneous_critic,
    node_hitl_approval_gate,
    node_input_guardrail_and_planner,
    node_sector_portfolio_reviewer,
    node_stage_gate_judge_and_compiler,
    node_track_researcher,
    route_after_critic,
)
from pso_workflow.schemas import WorkflowState
from pso_workflow.tools.evidence_vault import EvidenceVault
from pso_workflow.tools.search_router import DualEngineSearchRouter


def _fan_out_tracks(state: WorkflowState) -> list[Send]:
    """Ch 3 dynamic Send() fan-out across planned industry tracks."""
    plan = state.get("research_plan") or {}
    profile = state.get("profile", "flagship")
    track_plans = plan.get("track_plans", [])
    return [
        Send("track_researcher", {"track_plan": tp, "profile": profile})
        for tp in track_plans
    ]


def build_workflow_graph(
    deps: RuntimeDeps,
    *,
    checkpointer: Any = None,
):
    """Compile the complete LangGraph StateGraph with injected dependencies."""

    async def _planner(state: WorkflowState) -> dict[str, Any]:
        return await node_input_guardrail_and_planner(state, deps)

    async def _hitl(state: WorkflowState) -> dict[str, Any]:
        return await node_hitl_approval_gate(state, deps)

    async def _researcher(state: dict[str, Any]) -> dict[str, Any]:
        return await node_track_researcher(state, deps)

    async def _screener(state: WorkflowState) -> dict[str, Any]:
        return await node_deterministic_funnel_screener(state, deps)

    async def _portfolio(state: WorkflowState) -> dict[str, Any]:
        return await node_sector_portfolio_reviewer(state, deps)

    async def _synth(state: WorkflowState) -> dict[str, Any]:
        return await node_grounded_report_synthesizer(state, deps)

    async def _critic(state: WorkflowState) -> dict[str, Any]:
        return await node_heterogeneous_critic(state, deps)

    async def _refill(state: WorkflowState) -> dict[str, Any]:
        return await node_corrective_rag_refill(state, deps)

    async def _judge(state: WorkflowState) -> dict[str, Any]:
        return await node_stage_gate_judge_and_compiler(state, deps)

    builder = StateGraph(WorkflowState)
    builder.add_node("input_guardrail_and_planner", _planner)
    builder.add_node("hitl_approval_gate", _hitl)
    builder.add_node("track_researcher", _researcher)
    builder.add_node("deterministic_funnel_screener", _screener)
    builder.add_node("sector_portfolio_reviewer", _portfolio)
    builder.add_node("grounded_report_synthesizer", _synth)
    builder.add_node("heterogeneous_critic", _critic)
    builder.add_node("corrective_rag_refill", _refill)
    builder.add_node("stage_gate_judge_and_compiler", _judge)

    builder.add_edge(START, "input_guardrail_and_planner")
    builder.add_edge("input_guardrail_and_planner", "hitl_approval_gate")
    builder.add_conditional_edges("hitl_approval_gate", _fan_out_tracks, ["track_researcher"])
    builder.add_edge("track_researcher", "deterministic_funnel_screener")
    builder.add_edge("deterministic_funnel_screener", "sector_portfolio_reviewer")
    builder.add_edge("sector_portfolio_reviewer", "grounded_report_synthesizer")
    builder.add_edge("grounded_report_synthesizer", "heterogeneous_critic")
    builder.add_conditional_edges(
        "heterogeneous_critic",
        route_after_critic,
        {
            "corrective_rag_refill": "corrective_rag_refill",
            "grounded_report_synthesizer": "grounded_report_synthesizer",
            "stage_gate_judge_and_compiler": "stage_gate_judge_and_compiler",
        },
    )
    builder.add_edge("corrective_rag_refill", "grounded_report_synthesizer")
    builder.add_edge("stage_gate_judge_and_compiler", END)

    return builder.compile(checkpointer=checkpointer)


def create_default_deps(
    settings: WorkflowSettings | None = None,
) -> RuntimeDeps:
    """Instantiate live production RuntimeDeps from workspace `.env*` files."""
    cfg = settings or WorkflowSettings.load()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    ledger = CostLedger()
    vault = EvidenceVault(cfg.resolve_vault_path())
    search_router = DualEngineSearchRouter(cfg, ledger)
    llm = DashScopeLLMGateway(cfg, ledger)
    return RuntimeDeps(
        settings=cfg,
        ledger=ledger,
        vault=vault,
        search_router=search_router,
        llm=llm,
    )


def create_sync_checkpointer(db_path: Path) -> SqliteSaver:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def create_async_checkpointer_ctx(db_path: Path):
    """Return AsyncSqliteSaver context manager for async CLI execution."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return AsyncSqliteSaver.from_conn_string(str(db_path))


def build_studio_graph():
    """Zero-argument factory referenced by `langgraph.json` for LangGraph Studio."""
    deps = create_default_deps()
    return build_workflow_graph(deps)
