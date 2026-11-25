"""Stage 3b & 3c: 100% Full-Text Per-Volume Critic + CRAG Rewrite + Dual-Edition Deterministic Finalize."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vf_ccus_workflow.config import assert_no_secrets_leaked
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.nodes.synthesizer import (
    VOLUME_SPECS,
    VOLUME_TRACK_ROUTING,
    collect_priority_ev_ids_for_volume,
    distill_executive_edition,
)
from vf_ccus_workflow.prompts import SINGLE_VOLUME_CRITIC_SYSTEM, VOLUME_SYNTH_SYSTEM
from vf_ccus_workflow.schemas import (
    CritiqueIssue,
    SingleVolumeCriticOutput,
    WorkflowState,
)
from vf_ccus_workflow.tools.evidence_vault import (
    extract_all_ev_ids,
    render_evidence_index,
    run_deterministic_full_audit,
)


def build_single_volume_critic_prompt(
    *,
    volume_name: str,
    full_text: str,
    fact_sheet: str,
    invalid_ids: list[str],
    loop_idx: int,
    max_loops: int,
) -> str:
    """Build per-volume Critic prompt containing 100% of full_text (ZERO truncation)."""
    return (
        f"Audit Target Volume: `{volume_name}` (Reflection Iteration {loop_idx} / {max_loops})\n"
        f"Programmatic Invalid EV-ID Detection (Full-Text Scan): {json.dumps(invalid_ids, ensure_ascii=False)}\n"
        f"Volume Character Count: {len(full_text)}\n\n"
        f"=== LOCKED EXECUTIVE FACT SHEET ([MKT-CALC] & [ROI-CALC] GROUND TRUTH) ===\n{fact_sheet}\n\n"
        f"=== COMPLETE VOLUME FULL TEXT (100% UNTRUNCATED) ===\n{full_text}\n\n"
        "Audit the ENTIRE text above for citation integrity, exact numeric consistency against [MKT-CALC]/[ROI-CALC], "
        "competitor honesty (zero fabricated models), pseudo-demand disclosure, and Track A/B/C coherence."
    )


def build_single_volume_rewrite_prompt(
    *,
    volume_name: str,
    full_text: str,
    fact_sheet: str,
    critic_feedback: str,
    invalid_ids: list[str],
    crag_context: str,
    volume_evidence_context: str,
) -> str:
    """Build per-volume rewrite prompt containing 100% of full_text (ZERO truncation)."""
    return (
        f"Targeted Revision of `{volume_name}` (Preserve full analytical depth; fix every flagged issue):\n"
        f"Critic Findings & Required Fixes:\n{critic_feedback}\n"
        f"Invalid EV-IDs that MUST be removed or replaced with verified IDs: {json.dumps(invalid_ids, ensure_ascii=False)}\n\n"
        f"=== LOCKED EXECUTIVE FACT SHEET ([MKT-CALC] & [ROI-CALC]) ===\n{fact_sheet}\n\n"
        f"=== NEW CRAG GAP EVIDENCE ===\n{crag_context}\n\n"
        f"=== VOLUME-ROUTED VERIFIED EVIDENCE ===\n{volume_evidence_context}\n\n"
        f"=== COMPLETE PREVIOUS DRAFT (100% UNTRUNCATED) ===\n{full_text}\n\n"
        "Return the complete revised Simplified Chinese Markdown volume with all flagged issues resolved."
    )


def find_invalid_citations_full_text(
    drafts: dict[str, str], valid_ids: set[str]
) -> dict[str, list[str]]:
    """Scan 100% of every volume (including multi-ID brackets) for unverified EV IDs."""
    invalid_by_vol: dict[str, list[str]] = {}
    for vol, text in drafts.items():
        if not vol.startswith(("00_", "01_", "02_", "03_", "04_")):
            continue
        cited = extract_all_ev_ids(text)
        bad = sorted(cid for cid in cited if cid not in valid_ids)
        if bad:
            invalid_by_vol[vol] = bad
    return invalid_by_vol


async def node_full_text_critic(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 3b-1: Programmatic Full-Text Citation Audit + Per-Volume 100% Full-Text Critic."""
    profile = state.get("profile", "flagship")
    loop_count = int(state.get("critique_loop_count", 0))
    max_loops = deps.settings.max_reflection_loops
    drafts = dict(state.get("report_drafts", {}))
    fact_sheet = state.get("executive_fact_sheet", "")
    valid_ids = deps.vault.list_valid_ids()
    invalid_map = find_invalid_citations_full_text(drafts, valid_ids)

    tier = "critic" if profile == "flagship" else "producer"
    target_vols = [f for f, _, _ in VOLUME_SPECS if f in drafts]

    async def _audit_one(vol_name: str) -> SingleVolumeCriticOutput:
        full_text = drafts[vol_name]
        bad_ids = invalid_map.get(vol_name, [])
        prompt = build_single_volume_critic_prompt(
            volume_name=vol_name,
            full_text=full_text,
            fact_sheet=fact_sheet,
            invalid_ids=bad_ids,
            loop_idx=loop_count + 1,
            max_loops=max_loops,
        )
        async with deps.semaphore:
            res = await deps.llm.complete_structured(
                tier=tier,
                node=f"critic_l{loop_count + 1}_{vol_name[:2]}",
                system_prompt=SINGLE_VOLUME_CRITIC_SYSTEM,
                user_prompt=prompt,
                schema=SingleVolumeCriticOutput,
                max_tokens=2200,
            )
        issues = list(res.issues)
        passed = res.passed
        needs_rewrite = res.needs_rewrite
        if bad_ids:
            passed = False
            needs_rewrite = True
            issues.append(
                CritiqueIssue(
                    volume_name=vol_name,
                    severity="critical",
                    description=f"全文扫描发现未入库引用ID: {', '.join(bad_ids[:8])}",
                    required_fix_action="删除伪造ID并替换为核验证据库中的真实[EV-SIGGI/CN/GL-*]ID。",
                    needs_crag_gap_search=False,
                )
            )
        return res.model_copy(
            update={
                "volume_name": vol_name,
                "passed": passed,
                "needs_rewrite": needs_rewrite,
                "issues": issues,
            }
        )

    vol_audits = list(await asyncio.gather(*[_audit_one(v) for v in target_vols]))
    vols_to_rewrite = [a.volume_name for a in vol_audits if not a.passed or a.needs_rewrite]
    all_issues = [iss for a in vol_audits for iss in a.issues]
    overall_passed = len(vols_to_rewrite) == 0

    pending_queries = [
        {
            "track_id": "CRAG_GAP",
            "geo_scope": iss.suggested_geo_scope,
            "query": iss.suggested_query,
        }
        for iss in all_issues
        if iss.needs_crag_gap_search and iss.suggested_query.strip()
    ][:4]

    per_vol_feedback = {
        a.volume_name: (
            a.overall_assessment
            + ("\n" + "\n".join(f"- [{i.severity}] {i.description} -> {i.required_fix_action}" for i in a.issues) if a.issues else "")
        )
        for a in vol_audits
    }

    return {
        "critique_loop_count": loop_count + 1,
        "pending_crag_queries": pending_queries,
        "volumes_to_rewrite": vols_to_rewrite,
        "critique_history": [
            {
                "loop": loop_count + 1,
                "passed": overall_passed,
                "volumes_to_rewrite": vols_to_rewrite,
                "issues_count": len(all_issues),
                "crag_queries": pending_queries,
                "per_volume_feedback": per_vol_feedback,
            }
        ],
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "full_text_critic",
                "loop": loop_count + 1,
                "passed": overall_passed,
                "rewrite_vols": vols_to_rewrite,
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
        return "finalize"
    if loop_count >= max_loops:
        return "finalize"
    if not latest.get("volumes_to_rewrite") and not state.get("pending_crag_queries"):
        return "finalize"
    return "rewrite"


async def node_crag_gap_and_rewrite(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 3b-2: Corrective RAG gap search + 100% full-text targeted rewrite of flagged volumes."""
    profile = state.get("profile", "flagship")
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
    per_vol_fb = latest.get("per_volume_feedback", {}) or {}
    drafts = dict(state.get("report_drafts", {}))
    fact_sheet = state.get("executive_fact_sheet", "")
    valid_ids = deps.vault.list_valid_ids()
    invalid_map = find_invalid_citations_full_text(drafts, valid_ids)
    new_ev_ctx = format_records_compact(added_records, limit=24) if added_records else "(No new CRAG records)"

    async def _rewrite_one(vol_name: str) -> tuple[str, str]:
        full_text = drafts.get(vol_name, "")
        ev_bundle = deps.vault.build_volume_evidence_bundle(
            volume_name=vol_name,
            track_ids=VOLUME_TRACK_ROUTING.get(vol_name, []),
            priority_ev_ids=collect_priority_ev_ids_for_volume(state, vol_name),
            limit=70,
        )
        vol_ev_ctx = format_records_compact(ev_bundle, limit=70)
        prompt = build_single_volume_rewrite_prompt(
            volume_name=vol_name,
            full_text=full_text,
            fact_sheet=fact_sheet,
            critic_feedback=str(per_vol_fb.get(vol_name, "")),
            invalid_ids=invalid_map.get(vol_name, []),
            crag_context=new_ev_ctx,
            volume_evidence_context=vol_ev_ctx,
        )
        async with deps.semaphore:
            revised = await deps.llm.complete_text(
                tier="producer",
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
        "volumes_to_rewrite": [],
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


async def node_distill_audit_and_finalize(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 3c: Distill Executive Edition + 100% Deterministic Audit Gate + Zero-LLM Index + Disk Write."""
    full_drafts = dict(state.get("report_drafts", {}))
    fact_sheet = state.get("executive_fact_sheet", "")
    all_records = deps.vault.list_all()
    vault_stats = deps.vault.stats()
    valid_ids = deps.vault.list_valid_ids()

    # Distill paired High-Density Executive Edition (5 volumes)
    exec_drafts = dict(state.get("executive_drafts", {}))
    if not exec_drafts:
        exec_drafts = await distill_executive_edition(
            full_drafts=full_drafts,
            fact_sheet=fact_sheet,
            deps=deps,
        )

    vol05_md = render_evidence_index(all_records, db_label=f"data/{deps.vault.db_path.name}")

    audit_report = run_deterministic_full_audit(
        vault_stats=vault_stats,
        valid_ids=valid_ids,
        full_drafts=full_drafts,
        executive_drafts=exec_drafts,
        market_sizing_summary=state.get("market_sizing_summary", {}),
        evaluated_wedges=state.get("evaluated_wedges", []),
        eliminated_wedges=state.get("eliminated_wedges", []),
        dropped_unverified_records=state.get("dropped_unverified_records", []),
        contract=deps.settings.contract,
    )

    out_dir_str = state.get("output_dir") or str(deps.settings.default_output_dir)
    out_path = Path(out_dir_str)
    if not out_path.is_absolute():
        out_path = (deps.settings.root_dir / out_path).resolve()
    exec_dir = out_path / "executive_edition"
    out_path.mkdir(parents=True, exist_ok=True)
    exec_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    for fname, content in sorted(full_drafts.items()):
        assert_no_secrets_leaked(content, deps.settings)
        target = out_path / fname
        target.write_text(content, encoding="utf-8")
        written_files.append(str(target))

    for fname, content in sorted(exec_drafts.items()):
        assert_no_secrets_leaked(content, deps.settings)
        target = exec_dir / fname
        target.write_text(content, encoding="utf-8")
        written_files.append(str(target))

    assert_no_secrets_leaked(vol05_md, deps.settings)
    v05_path = out_path / "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"
    v05_path.write_text(vol05_md, encoding="utf-8")
    written_files.append(str(v05_path))

    evaluated = state.get("evaluated_wedges", [])
    cost_sum = deps.ledger.summary()
    scorecard = {
        "schema_version": "2.0",
        "run_id": state.get("run_id", f"vf-{uuid.uuid4().hex[:8]}"),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": state.get("profile", "flagship"),
        "stage_gate_passed": audit_report.passed,
        "deterministic_audit_report": audit_report.model_dump(),
        "evidence_vault_stats": vault_stats,
        "market_sizing_summary": state.get("market_sizing_summary", {}),
        "evaluated_wedges_ranked": [
            {
                "rank": w.get("composite_rank"),
                "wedge_id": w["seed"]["wedge_id"],
                "sector": w["seed"]["sector"],
                "delivery_track": w["seed"]["delivery_track"],
                "title": w["seed"]["title"],
                "payback_months": w["roi"]["payback_months"],
                "irr_5yr_pct": w["roi"]["irr_5yr_pct"],
                "npv_5yr_cny": w["roi"]["npv_5yr_cny"],
                "global_priority_score": w.get("global_priority_score"),
                "weighted_pillar_score": w.get("weighted_pillar_score"),
                "merged_from_wedge_ids": w.get("merged_from_wedge_ids", []),
            }
            for w in evaluated
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

    full_drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = vol05_md

    return {
        "report_drafts": full_drafts,
        "executive_drafts": exec_drafts,
        "audit_report": audit_report.model_dump(),
        "stage_gate_passed": audit_report.passed,
        "cost_summary": cost_sum,
        "written_files": written_files,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "distill_audit_and_finalize",
                "passed": audit_report.passed,
                "failed_gates": audit_report.failed_gates,
                "written_count": len(written_files),
            }
        ],
    }
