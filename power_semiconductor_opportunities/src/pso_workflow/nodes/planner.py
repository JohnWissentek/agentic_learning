"""Node 1: Input Guardrail, Step-Back Domain Planner, and Optional HITL Gate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.types import interrupt

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import PLANNER_SYSTEM
from pso_workflow.schemas import ResearchPlan, TrackQueryPlan, WorkflowState


def _select_tracks(deps: RuntimeDeps, sector_filter: str) -> list[dict[str, Any]]:
    all_tracks: list[dict[str, Any]] = deps.settings.taxonomy.get("tracks", [])
    if sector_filter == "power":
        return [t for t in all_tracks if t.get("sector") == "power_energy"]
    if sector_filter == "semiconductor":
        return [t for t in all_tracks if t.get("sector") == "semiconductor"]
    return list(all_tracks)


async def node_input_guardrail_and_planner(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Validate execution scope against Formalized Contract and create 8-track plan."""
    sector_filter = state.get("sector_filter", "all")
    profile = state.get("profile", "flagship")
    contract_id = deps.settings.contract.get("contract_id", "PSO-CONTRACT-2026-V1")
    selected_tracks = _select_tracks(deps, sector_filter)

    if not selected_tracks:
        raise ValueError(f"No domain tracks matched sector_filter={sector_filter!r}")

    track_briefs = "\n".join(
        f"- {t['id']} ({t['sector']}): {t['name']} | stages: {', '.join(t.get('manufacturing_stages', []))}"
        for t in selected_tracks
    )
    user_prompt = (
        f"Contract ID: {contract_id}\n"
        f"Sector Filter: {sector_filter} | Profile: {profile}\n"
        f"Mandate: China FIRST (2027-2031 3-5y scale-up + 2031-2036 5-10y upgrade), "
        f"then Global SECOND. Focus on Quality/Yield, Cost/TCO, Green/EHS, and High Manufacturing ROI.\n\n"
        f"Selected Tracks:\n{track_briefs}\n\n"
        f"Using Step-Back reasoning, output a `ResearchPlan` preserving exact `track_id`, `sector`, "
        f"`name`, and concise `step_back_physics_principle` for each track. "
        f"Set `cn_queries` and `global_queries` to empty arrays `[]` (authoritative queries from taxonomy are attached automatically)."
    )

    plan = await deps.llm.complete_structured(
        tier="producer" if profile == "flagship" else "fast",
        node="planner",
        system_prompt=PLANNER_SYSTEM,
        user_prompt=user_prompt,
        schema=ResearchPlan,
        max_tokens=2400,
    )

    # Ensure deterministic preservation of authoritative track configs & baseline queries
    plan_by_id = {tp.track_id: tp for tp in plan.track_plans}
    normalized_plans: list[TrackQueryPlan] = []
    for raw in selected_tracks:
        tid = raw["id"]
        llm_tp = plan_by_id.get(tid)
        cn_q = list(raw.get("cn_queries", []))
        gl_q = list(raw.get("global_queries", []))
        if profile == "fast":
            cn_q = cn_q[:1]
            gl_q = gl_q[:1]
        normalized_plans.append(
            TrackQueryPlan(
                track_id=tid,
                sector=raw["sector"],
                name=raw["name"],
                step_back_physics_principle=(
                    llm_tp.step_back_physics_principle
                    if llm_tp and llm_tp.step_back_physics_principle
                    else f"在线传感围绕 {raw['name']} 关键失效物理量与工艺闭环控制。"
                ),
                cn_queries=cn_q,
                global_queries=gl_q,
            )
        )

    final_plan = ResearchPlan(
        contract_id=contract_id,
        sector_filter=sector_filter,
        profile=profile,
        step_back_thesis=plan.step_back_thesis,
        track_plans=normalized_plans,
    )

    return {
        "research_plan": final_plan.model_dump(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "planner",
                "tracks_scheduled": len(normalized_plans),
                "profile": profile,
            }
        ],
    }


async def node_hitl_approval_gate(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 13 HITL checkpoint before parallel high-concurrency deep search."""
    if not state.get("hitl_enabled", False):
        return {"hitl_approved": True}

    plan = state.get("research_plan", {})
    approval = interrupt(
        {
            "message": "请审批在线测试仪器仪表 8 赛道研究计划（Ch 13 HITL 检查点）",
            "step_back_thesis": plan.get("step_back_thesis", ""),
            "track_ids": [t.get("track_id") for t in plan.get("track_plans", [])],
        }
    )
    approved = bool(approval.get("approved", True)) if isinstance(approval, dict) else bool(approval)
    return {"hitl_approved": approved}
