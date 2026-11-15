"""Stage 6 (Bounded Heterogeneous Critic + CRAG Gap-Refill) & Stage 7 (100-pt Judge + Finalize)."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vf_ccus_workflow.config import assert_no_secrets_leaked
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.nodes.synthesizer import _format_catalogs_context
from vf_ccus_workflow.prompts import CRITIC_SYSTEM, JUDGE_SYSTEM, VOLUME_SYNTH_SYSTEM
from vf_ccus_workflow.schemas import (
    CriticAuditOutput,
    CritiqueIssue,
    JudgeRubricScores,
    WorkflowState,
)
from vf_ccus_workflow.tools.evidence_vault import (
    deterministic_contract_checks,
    render_evidence_index,
)


def _find_invalid_citations(drafts: dict[str, str], valid_ids: set[str]) -> dict[str, list[str]]:
    invalid_by_vol: dict[str, list[str]] = {}
    for vol, text in drafts.items():
        if not vol.startswith(("00_", "01_", "02_", "03_", "04_")):
            continue
        cited = set(re.findall(r"\[(EV-(?:SIGGI|CN|GL)-\d{3,4})\]", text))
        bad = sorted(cid for cid in cited if cid not in valid_ids)
        if bad:
            invalid_by_vol[vol] = bad
    return invalid_by_vol


async def node_adversarial_critic(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 6a: Programmatic Citation Audit + Heterogeneous Critic Model."""
    profile = state.get("profile", "flagship")
    loop_count = int(state.get("critique_loop_count", 0))
    max_loops = deps.settings.max_reflection_loops
    drafts = dict(state.get("report_drafts", {}))
    valid_ids = deps.vault.list_valid_ids()
    invalid_map = _find_invalid_citations(drafts, valid_ids)

    tier = "critic" if profile == "flagship" else "fast"
    calc_ctx = _format_catalogs_context(state)
    vol_excerpts = "\n\n".join(
        f"=== {k} (len={len(v)}) ===\n{v[:2200]}"
        for k, v in sorted(drafts.items())
        if k.startswith(("00_", "01_", "02_", "03_", "04_"))
    )
    prompt = (
        f"Reflection Iteration: {loop_count + 1} / {max_loops}\n"
        f"Programmatic Invalid Citation Detection: {json.dumps(invalid_map, ensure_ascii=False)}\n"
        f"Valid IDs Sample Count: {len(valid_ids)}\n\n"
        f"=== DETERMINISTIC [MKT-CALC] & [ROI-CALC] GROUND TRUTH ===\n{calc_ctx[:4000]}\n\n"
        f"=== DRAFT VOLUMES EXCERPTS ===\n{vol_excerpts}\n\n"
        "Audit consistency, citation integrity, competitor honesty, and dual-track actionability."
    )
    audit = await deps.llm.complete_structured(
        tier=tier,
        node=f"critic_loop_{loop_count + 1}",
        system_prompt=CRITIC_SYSTEM,
        user_prompt=prompt,
        schema=CriticAuditOutput,
        max_tokens=2800,
    )

    # Enforce programmatic failure if fabricated citations exist
    issues = list(audit.issues)
    vols_to_rewrite = list(dict.fromkeys(audit.volumes_to_rewrite))
    if invalid_map:
        for vol, bad_ids in invalid_map.items():
            if vol not in vols_to_rewrite:
                vols_to_rewrite.append(vol)
            issues.append(
                CritiqueIssue(
                    volume_name=vol,
                    severity="critical",
                    description=f"存在未入库引用ID: {', '.join(bad_ids[:5])}",
                    required_fix_action="删除伪造ID并替换为核验证据库中的真实[EV-SIGGI/CN/GL-*]ID。",
                    needs_crag_gap_search=False,
                )
            )
        audit = audit.model_copy(
            update={"passed": False, "issues": issues, "volumes_to_rewrite": vols_to_rewrite}
        )

    pending_queries = [
        {
            "track_id": "CRAG_GAP",
            "geo_scope": iss.suggested_geo_scope,
            "query": iss.suggested_query,
        }
        for iss in audit.issues
        if iss.needs_crag_gap_search and iss.suggested_query.strip()
    ][:4]

    return {
        "critique_loop_count": loop_count + 1,
        "pending_crag_queries": pending_queries,
        "critique_history": [
            {
                "loop": loop_count + 1,
                "passed": audit.passed,
                "volumes_to_rewrite": audit.volumes_to_rewrite,
                "issues_count": len(audit.issues),
                "crag_queries": pending_queries,
                "assessment": audit.overall_assessment,
            }
        ],
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "adversarial_critic",
                "loop": loop_count + 1,
                "passed": audit.passed,
                "rewrite_vols": audit.volumes_to_rewrite,
            }
        ],
    }


def route_after_critic(state: WorkflowState, deps: RuntimeDeps) -> str:
    """Bounded conditional router (<= max_reflection_loops)."""
    history = state.get("critique_history", [])
    latest = history[-1] if history else {}
    loop_count = int(state.get("critique_loop_count", 0))
    max_loops = deps.settings.max_reflection_loops
    if latest.get("passed", True):
        return "judge"
    if loop_count >= max_loops:
        return "judge"
    if not latest.get("volumes_to_rewrite") and not state.get("pending_crag_queries"):
        return "judge"
    return "rewrite"


async def node_crag_gap_and_rewrite(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 6b: Corrective RAG gap search + targeted rewrite of flagged volumes only."""
    profile = state.get("profile", "flagship")
    tier = "producer" if profile == "flagship" else "fast"
    gap_queries = list(state.get("pending_crag_queries", []))[:4]
    added_records = []

    for q_item in gap_queries:
        q = str(q_item.get("query", "")).strip()
        if not q:
            continue
        geo = "GLOBAL" if q_item.get("geo_scope") == "GLOBAL" else "CN"
        hits = await deps.search_router.search_track(
            track_id="CRAG_GAP",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            mode="webpage" if geo == "CN" else "search",
            num_results=5,
        )
        deps.vault.log_query(
            track_id="CRAG_GAP",
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            hits_count=len(hits),
        )
        for h in hits:
            rec = deps.vault.upsert_hit(track_id="CRAG_GAP", hit=h)
            if rec is not None:
                added_records.append(rec)

    history = state.get("critique_history", [])
    latest = history[-1] if history else {}
    vols_to_rewrite = latest.get("volumes_to_rewrite", []) or []
    drafts = dict(state.get("report_drafts", {}))
    calc_ctx = _format_catalogs_context(state)
    new_ev_ctx = format_records_compact(added_records, limit=18) if added_records else ""
    valid_ctx = format_records_compact(deps.vault.list_all(), limit=32)

    async def _rewrite_one(vol_name: str) -> tuple[str, str]:
        old_text = drafts.get(vol_name, "")
        prompt = (
            f"Rewrite and upgrade `{vol_name}` to resolve Critic findings:\n"
            f"Critic Feedback: {latest.get('assessment', '')}\n\n"
            f"=== AUTHORITATIVE [MKT-CALC] & [ROI-CALC] ===\n{calc_ctx}\n\n"
            f"=== NEW CRAG EVIDENCE ===\n{new_ev_ctx}\n\n"
            f"=== VERIFIED EVIDENCE SAMPLE ===\n{valid_ctx[:4500]}\n\n"
            f"=== PREVIOUS DRAFT ===\n{old_text[:5500]}\n\n"
            "Fix every flagged discrepancy, eliminate any unverified EV ID, and return full polished Simplified Chinese Markdown."
        )
        async with deps.semaphore:
            revised = await deps.llm.complete_text(
                tier=tier,
                node=f"rewrite_{vol_name[:2]}",
                system_prompt=VOLUME_SYNTH_SYSTEM,
                user_prompt=prompt,
                temperature=0.18,
                max_tokens=7200 if profile == "flagship" else 4200,
            )
        return vol_name, revised.strip() + "\n"

    rewritten_pairs = await asyncio.gather(
        *[_rewrite_one(v) for v in vols_to_rewrite if v in drafts]
    )
    for k, v in rewritten_pairs:
        drafts[k] = v

    return {
        "report_drafts": drafts,
        "pending_crag_queries": [],
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "crag_gap_and_rewrite",
                "crag_added": len(added_records),
                "rewritten_volumes": [k for k, _ in rewritten_pairs],
            }
        ],
    }


async def node_stage_gate_judge_and_finalize(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 7: Deterministic Vol 05 Index, Contract Audit, 100-pt Judge & Disk Persistence."""
    drafts = dict(state.get("report_drafts", {}))
    all_records = deps.vault.list_all()
    vault_stats = deps.vault.stats()

    drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
        all_records, db_label=f"data/{deps.vault.db_path.name}"
    )

    evaluated = state.get("evaluated_wedges", [])
    det_checks = deterministic_contract_checks(
        vault_stats=vault_stats,
        drafts=drafts,
        evaluated_wedges=evaluated,
        contract=deps.settings.contract,
    )

    calc_ctx = _format_catalogs_context(state)
    exec_excerpt = drafts.get("00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md", "")[:3200]
    comp_excerpt = drafts.get("02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md", "")[:2400]
    gtm_excerpt = drafts.get("03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md", "")[:2400]

    tier = "critic" if state.get("profile", "flagship") == "flagship" else "fast"
    judge_prompt = (
        f"Deterministic Checks: {json.dumps(det_checks, ensure_ascii=False)}\n"
        f"Summary [MKT-CALC] & [ROI-CALC]:\n{calc_ctx[:2600]}\n\n"
        f"Vol 00 Excerpt:\n{exec_excerpt}\n\n"
        f"Vol 02 Excerpt:\n{comp_excerpt}\n\n"
        f"Vol 03 Excerpt:\n{gtm_excerpt}\n\n"
        "Score strictly on the 5x20=100 Stage-Gate Rubric."
    )
    rubric = await deps.llm.complete_structured(
        tier=tier,
        node="stage_gate_judge",
        system_prompt=JUDGE_SYSTEM,
        user_prompt=judge_prompt,
        schema=JudgeRubricScores,
        max_tokens=1600,
    )
    exact_total = round(
        rubric.china_grounding_and_project_specificity
        + rubric.market_sizing_and_pain_point_rigor
        + rubric.competitive_battlecard_accuracy
        + rubric.dual_track_gtm_and_roi_actionability
        + rubric.evidence_traceability_and_prose,
        2,
    )
    threshold = float(deps.settings.contract.get("quality_gates", {}).get("stage_gate_pass_score", 85.0))
    passed = bool(exact_total >= threshold and det_checks.get("all_5_volumes_non_empty"))
    rubric = rubric.model_copy(update={"total_score": exact_total, "pass_stage_gate": passed})

    out_dir_str = state.get("output_dir") or str(deps.settings.default_output_dir)
    out_path = Path(out_dir_str)
    if not out_path.is_absolute():
        out_path = (deps.settings.root_dir / out_path).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    for fname, content in sorted(drafts.items()):
        assert_no_secrets_leaked(content, deps.settings)
        target = out_path / fname
        target.write_text(content, encoding="utf-8")
        written_files.append(str(target))

    cost_sum = deps.ledger.summary()
    scorecard = {
        "run_id": state.get("run_id", f"vf-{uuid.uuid4().hex[:8]}"),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": state.get("profile", "flagship"),
        "stage_gate_passed": passed,
        "pass_threshold": threshold,
        "judge_rubric": rubric.model_dump(),
        "deterministic_contract_checks": det_checks,
        "evidence_vault_stats": vault_stats,
        "market_sizing_summary": state.get("market_sizing_summary", {}),
        "evaluated_wedges_top10": [
            {
                "rank": w.get("composite_rank"),
                "wedge_id": w["seed"]["wedge_id"],
                "sector": w["seed"]["sector"],
                "delivery_track": w["seed"]["delivery_track"],
                "title": w["seed"]["title"],
                "payback_months": w["roi"]["payback_months"],
                "irr_5yr_pct": w["roi"]["irr_5yr_pct"],
                "weighted_pillar_score": w["weighted_pillar_score"],
                "elo_rating": w["elo_rating"],
            }
            for w in evaluated[:10]
        ],
        "eliminated_wedges": state.get("eliminated_wedges", []),
        "critique_loops_executed": int(state.get("critique_loop_count", 0)),
        "critique_history": state.get("critique_history", []),
        "cost_and_token_telemetry": cost_sum,
    }
    sc_str = json.dumps(scorecard, ensure_ascii=False, indent=2)
    assert_no_secrets_leaked(sc_str, deps.settings)
    sc_path = out_path / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
    sc_path.write_text(sc_str + "\n", encoding="utf-8")
    written_files.append(str(sc_path))

    return {
        "report_drafts": drafts,
        "judge_rubric": rubric.model_dump(),
        "deterministic_checks": det_checks,
        "stage_gate_passed": passed,
        "cost_summary": cost_sum,
        "written_files": written_files,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "stage_gate_judge_and_finalize",
                "total_score": exact_total,
                "passed": passed,
                "written_count": len(written_files),
            }
        ],
    }
