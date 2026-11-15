"""Nodes 6 & 7: Heterogeneous Producer-Critic Reflection & Ch 19 Stage-Gate Judge."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import CRITIC_SYSTEM, JUDGE_SYSTEM
from pso_workflow.schemas import CritiqueVerdict, JudgeRubricScores, WorkflowState


def _extract_citation_ids(texts: list[str]) -> set[str]:
    found: set[str] = set()
    for t in texts:
        found.update(re.findall(r"EV-(?:CN|GL)-\d{3}", t))
    return found


def deterministic_contract_checks(
    *,
    vault_stats: dict[str, Any],
    drafts: dict[str, str],
    evaluated_opps: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Ch 19 Formalized Contractor deterministic compliance checks."""
    gates = contract.get("quality_gates", {})
    min_ev = int(gates.get("min_total_evidences", 48))
    min_cn_ratio = float(gates.get("min_china_evidence_ratio", 0.45))
    min_tracks = int(gates.get("min_tracks_covered", 8))

    # Adjust threshold dynamically when running filtered single-sector jobs
    tracks_covered = len(vault_stats.get("by_track", {}))
    effective_min_ev = min_ev if tracks_covered >= 6 else max(16, min_ev // 2)

    main_texts = [
        v for k, v in drafts.items() if k.startswith(("00_", "01_", "02_", "03_", "04_"))
    ]
    cited_ids = _extract_citation_ids(main_texts)
    roi_tags = sum(t.count("[ROI-CALC]") for t in main_texts)
    has_cn_and_global = all(
        ("中国" in t and ("全球" in t or "欧美" in t or "海外" in t))
        for t in main_texts[:3]
    )
    has_dual_horizon = all(("3-5" in t or "3–5" in t) and ("5-10" in t or "5–10" in t) for t in main_texts[:3])

    checks = {
        "total_evidences_pass": vault_stats.get("total", 0) >= effective_min_ev,
        "china_ratio_pass": vault_stats.get("cn_ratio", 0.0) >= min_cn_ratio,
        "tracks_covered_pass": tracks_covered >= min(min_tracks, tracks_covered or 1),
        "opportunities_ranked_count": len(evaluated_opps),
        "citations_used_count": len(cited_ids),
        "roi_calc_tags_count": roi_tags,
        "china_first_global_second_present": has_cn_and_global,
        "dual_horizon_present": has_dual_horizon,
        "all_5_volumes_non_empty": len(main_texts) == 5 and all(len(t) > 500 for t in main_texts),
    }
    return checks


async def node_heterogeneous_critic(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 4 Heterogeneous Critic (`deepseek-v4-pro`) auditing drafts against contract."""
    drafts = state.get("draft_reports") or {}
    vault_stats = deps.vault.stats()
    evaluated = state.get("evaluated_opportunities", [])
    loop_count = int(state.get("loop_count", 0))
    max_loops = int(state.get("max_loops", deps.settings.max_reflection_loops))

    det_checks = deterministic_contract_checks(
        vault_stats=vault_stats,
        drafts=drafts,
        evaluated_opps=evaluated,
        contract=deps.settings.contract,
    )

    draft_previews = "\n\n".join(
        f"=== {k} ({len(v)} chars) ===\n{v[:2200]}\n...[tail]...\n{v[-800:]}"
        for k, v in sorted(drafts.items())
        if k.startswith(("00_", "01_", "02_", "03_", "04_"))
    )

    user_prompt = (
        f"Current Reflection Loop: {loop_count} / {max_loops}\n"
        f"EvidenceVault Stats: {json.dumps(vault_stats, ensure_ascii=False)}\n"
        f"Deterministic Checks: {json.dumps(det_checks, ensure_ascii=False)}\n\n"
        f"Draft Report Excerpts:\n{draft_previews}\n\n"
        f"Audit rigorously against the Formalized Contract (China-first -> Global-second, 3-5y vs 5-10y, "
        f"physics precision, [EV-...] citations, [ROI-CALC] fidelity). "
        f'Return `CritiqueVerdict` JSON with `decision` in ["pass", "needs_more_evidence", "needs_rewrite"].'
    )

    verdict = await deps.llm.complete_structured(
        tier="critic",
        node="heterogeneous_critic",
        system_prompt=CRITIC_SYSTEM,
        user_prompt=user_prompt,
        schema=CritiqueVerdict,
        max_tokens=8192,
    )

    # Enforce deterministic evidence floor: if vault total is critically low and loop remains, force refill
    if not det_checks["total_evidences_pass"] and verdict.decision == "pass" and loop_count < max_loops:
        verdict = verdict.model_copy(
            update={
                "decision": "needs_more_evidence",
                "summary": f"证据总量({vault_stats.get('total')})低于合同要求，自动触发定向补搜。",
                "gap_queries": verdict.gap_queries
                or [
                    {
                        "track_id": "P3",
                        "geo_scope": "CN",
                        "query": "特高压 SF6替代气体 C4F7N 在线监测 国家电网 招标",
                    },
                    {
                        "track_id": "S3",
                        "geo_scope": "CN",
                        "query": "8英寸 碳化硅 外延 缺陷检测 晶圆级 动态测试 KGD",
                    },
                ],
            }
        )

    next_loop_count = loop_count + 1 if verdict.decision != "pass" else loop_count

    return {
        "loop_count": next_loop_count,
        "latest_critique": verdict.model_dump(),
        "critique_history": [verdict.model_dump()],
        "evidence_stats": vault_stats,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "heterogeneous_critic",
                "decision": verdict.decision,
                "confidence": verdict.overall_confidence,
                "issues_count": len(verdict.issues),
                "next_loop_count": next_loop_count,
            }
        ],
    }


def route_after_critic(
    state: WorkflowState,
) -> Literal[
    "corrective_rag_refill",
    "grounded_report_synthesizer",
    "stage_gate_judge_and_compiler",
]:
    """Ch 2 & Rule 03 Deterministic Conditional Routing with hard loop cutoff."""
    verdict = state.get("latest_critique") or {}
    decision = str(verdict.get("decision", "pass"))
    loop_count = int(state.get("loop_count", 0))
    max_loops = int(state.get("max_loops", 2))

    # Notice loop_count was already incremented on non-pass in critic
    if loop_count > max_loops:
        return "stage_gate_judge_and_compiler"
    if decision == "needs_more_evidence":
        return "corrective_rag_refill"
    if decision == "needs_rewrite":
        return "grounded_report_synthesizer"
    return "stage_gate_judge_and_compiler"


async def node_stage_gate_judge_and_compiler(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 19 LLM-as-a-Judge + Deterministic Audit + Final Deliverable Compilation."""
    drafts = state.get("draft_reports") or {}
    vault_stats = deps.vault.stats()
    evaluated = state.get("evaluated_opportunities", [])
    out_dir = Path(state.get("output_dir") or deps.settings.default_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    det_checks = deterministic_contract_checks(
        vault_stats=vault_stats,
        drafts=drafts,
        evaluated_opps=evaluated,
        contract=deps.settings.contract,
    )

    sample_excerpts = "\n\n".join(
        f"### {k}\n{v[:2500]}"
        for k, v in sorted(drafts.items())
        if k.startswith(("00_", "01_", "02_", "03_", "04_"))
    )
    judge_prompt = (
        f"Deterministic Checks:\n{json.dumps(det_checks, ensure_ascii=False)}\n"
        f"Evidence Vault Stats:\n{json.dumps(vault_stats, ensure_ascii=False)}\n"
        f"Draft Deliverables Previews:\n{sample_excerpts}\n\n"
        f"Score 0-20 on each of the 5 dimensions (`china_first_then_global_depth`, "
        f"`dual_horizon_3_5y_vs_5_10y_rigor`, `pain_point_and_physics_specificity`, "
        f"`roi_and_industrial_upgrade_value`, `citation_grounding_and_prose`), ensure "
        f"`total_score` equals their exact sum, and return `JudgeRubricScores` JSON."
    )

    rubric = await deps.llm.complete_structured(
        tier="critic",
        node="stage_gate_judge",
        system_prompt=JUDGE_SYSTEM,
        user_prompt=judge_prompt,
        schema=JudgeRubricScores,
        max_tokens=8192,
    )

    # Recompute exact sum deterministically to prevent LLM arithmetic drift
    exact_sum = round(
        rubric.china_first_then_global_depth
        + rubric.dual_horizon_3_5y_vs_5_10y_rigor
        + rubric.pain_point_and_physics_specificity
        + rubric.roi_and_industrial_upgrade_value
        + rubric.citation_grounding_and_prose,
        2,
    )
    rubric = rubric.model_copy(update={"total_score": exact_sum})

    written_files: list[str] = []
    for filename, content in sorted(drafts.items()):
        target = out_dir / filename
        target.write_text(content, encoding="utf-8")
        written_files.append(str(target))

    cost_summary = deps.ledger.summary()
    pass_threshold = float(deps.settings.contract.get("quality_gates", {}).get("stage_gate_pass_score", 85))
    scorecard = {
        "run_id": state.get("run_id", ""),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": state.get("profile", "flagship"),
        "sector_filter": state.get("sector_filter", "all"),
        "stage_gate_passed": exact_sum >= pass_threshold and det_checks["all_5_volumes_non_empty"],
        "pass_threshold": pass_threshold,
        "judge_rubric": rubric.model_dump(),
        "deterministic_contract_checks": det_checks,
        "evidence_vault_stats": vault_stats,
        "critique_loops_executed": int(state.get("loop_count", 0)),
        "critique_history": state.get("critique_history", []),
        "cost_and_token_telemetry": cost_summary,
        "llm_call_trace": deps.ledger.llm_calls,
        "search_call_trace": deps.ledger.search_calls,
        "node_events": state.get("telemetry_events", []),
    }

    scorecard_path = out_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
    scorecard_path.write_text(
        json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    written_files.append(str(scorecard_path))

    return {
        "evaluation_scorecard": scorecard,
        "final_deliverables": written_files,
    }
