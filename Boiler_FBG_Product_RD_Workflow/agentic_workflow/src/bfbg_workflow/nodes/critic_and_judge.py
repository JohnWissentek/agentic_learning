"""Stage 6 & 7: Heterogeneous Critic, CRAG Gap Refill, 100-Point Stage-Gate Judge & Final Export."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bfbg_workflow.config import assert_no_secrets_leaked
from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import CRITIC_SYSTEM, JUDGE_SYSTEM
from bfbg_workflow.schemas import CriticAuditReport, JudgeRubricScores, WorkflowState
from bfbg_workflow.tools.evidence_vault import (
    deterministic_contract_checks,
    format_records_compact,
    render_evidence_and_datasheet_index,
)


def normalize_volume_markdown(md: str) -> str:
    """Normalize LLM-emitted file:/// links to relative ./ paths and flatten [[EV-*]] brackets."""
    text = re.sub(
        r"\(file:///[^)\s]*?datasheets_pdf/([A-Za-z0-9._-]+\.pdf)\)",
        r"(./datasheets_pdf/\1)",
        md,
    )
    text = re.sub(
        r"\(file:///[^)\s]*?/([0-9]{2}_[A-Za-z0-9_]+\.(?:md|json|pdf|svg|drawio))\)",
        r"(./\1)",
        text,
    )
    text = re.sub(r"\[\[(EV-(?:BASE|CN|GL|PDF)-\d{4})\]\]", r"[\1]", text)
    return text


def run_diagram_generators(root_dir: Path, output_dir: Path) -> list[str]:
    """Execute both Draw.io/SVG/PDF diagram generator scripts and return generated filenames."""
    generated: list[str] = []
    scripts = [
        root_dir / "scripts" / "generate_ipd_workflow_drawio.py",
        root_dir / "scripts" / "generate_system_interface_drawio.py",
    ]
    for sc in scripts:
        if sc.exists():
            subprocess.run(
                [sys.executable, str(sc), "--output-dir", str(output_dir)],
                cwd=str(root_dir),
                check=True,
                capture_output=True,
                text=True,
            )
            generated.append(sc.name)
    return generated


def export_all_deliverables(
    *,
    deps: RuntimeDeps,
    output_dir: Path,
    volumes: dict[str, str],
    judge_rubric: dict[str, Any],
    run_id: str,
    profile: str,
    llm_engine: str,
    extra_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically compile Vol 07, Vol 08 scorecard, diagrams, and verify zero secret/link errors."""
    output_dir.mkdir(parents=True, exist_ok=True)
    volumes = {k: normalize_volume_markdown(v) for k, v in volumes.items()}
    for fname, content in volumes.items():
        assert_no_secrets_leaked(content, deps.settings)
        (output_dir / fname).write_text(content.strip() + "\n", encoding="utf-8")

    vol07 = render_evidence_and_datasheet_index(deps.vault)
    assert_no_secrets_leaked(vol07, deps.settings)
    (output_dir / "07_VERIFIED_EVIDENCE_AND_DATASHEET_INDEX.md").write_text(vol07, encoding="utf-8")

    checks = deterministic_contract_checks(
        vault=deps.vault,
        volumes=volumes,
        output_dir=output_dir,
        contract=deps.settings.contract,
    )

    diagrams_ran = run_diagram_generators(deps.settings.root_dir, output_dir)

    scorecard = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_id": deps.settings.contract.get("contract_id"),
        "profile": profile,
        "llm_engine": llm_engine,
        "stage_gate_rubric": judge_rubric,
        "stage_gate_total_score": judge_rubric.get("total_score", 0),
        "programmatic_checks": checks,
        "diagrams_generated": diagrams_ran,
        "cost_and_search_telemetry": deps.ledger.summary(),
        "secret_leak_check": "PASS",
    }
    if extra_telemetry:
        scorecard["orchestration_telemetry"] = extra_telemetry

    scorecard_str = json.dumps(scorecard, ensure_ascii=False, indent=2)
    assert_no_secrets_leaked(scorecard_str, deps.settings)
    (output_dir / "08_EVALUATION_SCORECARD_AND_TELEMETRY.json").write_text(
        scorecard_str + "\n", encoding="utf-8"
    )
    return scorecard


async def node_adversarial_critic(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 6a: Run programmatic citation/PDF checks + Heterogeneous Critic review."""
    raw_out = state.get("output_dir", str(deps.settings.default_output_dir))
    out_dir = Path(raw_out) if Path(raw_out).is_absolute() else (deps.settings.root_dir / raw_out).resolve()
    volumes = state.get("volumes", {})
    checks = deterministic_contract_checks(
        vault=deps.vault, volumes=volumes, output_dir=out_dir, contract=deps.settings.contract
    )
    loop_idx = int(state.get("critic_loop_count", 0)) + 1
    md = state["calc_bundle"]["markdown_tables"]
    excerpts = "\n\n".join(f"=== {k} ===\n{v[:2200]}" for k, v in sorted(volumes.items()))

    prompt = (
        f"Critique Loop {loop_idx}/{deps.settings.max_reflection_loops}\n"
        f"Programmatic Checks: {json.dumps(checks, ensure_ascii=False)}\n\n"
        f"=== [PHY-CALC] & [BOM-CALC] ===\n{md['physics_link_md']}\n\n{md['bom_matrix_md']}\n\n"
        f"=== [FIN-CALC] & [PLANT-ROI] ===\n{md['financial_scenarios_md']}\n\n{md['plant_roi_md']}\n\n"
        f"=== DRAFT VOLUMES EXCERPTS ===\n{excerpts}"
    )
    audit = await deps.llm.complete_json(
        tier="critic",
        node=f"stage6_critic_l{loop_idx}",
        system_prompt=CRITIC_SYSTEM,
        user_prompt=prompt,
        schema=CriticAuditReport,
        max_tokens=3000,
    )

    vols_to_fix = list(dict.fromkeys(audit.volumes_to_rewrite))
    for bad_v in set(checks["invalid_citations"].keys()) | set(checks["broken_pdf_links"].keys()):
        if bad_v not in vols_to_fix:
            vols_to_fix.append(bad_v)
    passed = audit.passed and checks["invalid_citations_count"] == 0 and checks["broken_pdf_links_count"] == 0

    crag_qs = [
        {"geo_scope": iss.suggested_geo_scope, "query": iss.suggested_query}
        for iss in audit.issues
        if iss.needs_crag_gap_search and iss.suggested_query.strip()
    ][:4]

    return {
        "critic_loop_count": loop_idx,
        "volumes_to_rewrite": [] if passed else vols_to_fix,
        "crag_queries": crag_qs,
        "critic_history": [
            {
                "loop": loop_idx,
                "passed": passed,
                "volumes_to_rewrite": vols_to_fix,
                "assessment": audit.overall_assessment,
            }
        ],
    }


def route_after_critic(state: WorkflowState, *, deps: RuntimeDeps) -> str:
    """Ch 2/4 Bounded reflection router."""
    hist = state.get("critic_history", [])
    latest_passed = hist[-1]["passed"] if hist else True
    loop_count = int(state.get("critic_loop_count", 0))
    vols_to_fix = state.get("volumes_to_rewrite", [])
    if latest_passed or loop_count >= deps.settings.max_reflection_loops or not vols_to_fix:
        return "judge"
    return "rewrite"


async def node_crag_gap_and_rewrite(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 6b: Corrective RAG gap search + targeted volume rewrite."""
    crag_qs = state.get("crag_queries", [])
    new_recs = []
    for item in crag_qs:
        hits = await deps.search_router.search_track(
            track_id="CRAG_GAP",
            geo_scope=item.get("geo_scope", "CN"),  # type: ignore[arg-type]
            query=item.get("query", ""),
            num_results=5,
        )
        for h in hits:
            r = deps.vault.upsert_hit(track_id="CRAG_GAP", hit=h)
            if r:
                new_recs.append(r)

    crag_ctx = format_records_compact(new_recs, limit=15)
    volumes = dict(state.get("volumes", {}))
    targets = [v for v in state.get("volumes_to_rewrite", []) if v in volumes]
    md = state["calc_bundle"]["markdown_tables"]
    valid_ev_ctx = format_records_compact(deps.vault.list_all(), limit=35)
    latest_assess = state.get("critic_history", [{}])[-1].get("assessment", "")

    async def _rewrite(vname: str) -> tuple[str, str]:
        usr_p = (
            f"请精准修复并重写 `{vname}`：\n审查意见：{latest_assess}\n\n"
            f"=== 确定性数据 ===\n{md['physics_link_md']}\n\n{md['bom_matrix_md']}\n\n{md['financial_scenarios_md']}\n\n"
            f"=== CRAG 补检新证据 ===\n{crag_ctx}\n\n"
            f"=== 合法证据 ID 样本 ===\n{valid_ev_ctx}\n\n"
            f"=== 原文 ===\n{volumes[vname][:6000]}"
        )
        text = await deps.llm.complete_text(
            tier="producer",
            node=f"stage6_rewrite_{vname[:2]}",
            system_prompt="你是资深工程主编，请严格修复审查缺陷、清除无效引用并补齐定量细节。",
            user_prompt=usr_p,
            max_tokens=7800,
        )
        return vname, text + "\n"

    rewritten = await asyncio.gather(*(_rewrite(t) for t in targets))
    for k, v in rewritten:
        volumes[k] = v
    return {"volumes": volumes, "crag_context": crag_ctx}


async def node_stage_gate_judge_and_finalize(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 7: Ch 19 100-point Stage-Gate Judge & Finalize deliverables to output/."""
    volumes = state.get("volumes", {})
    raw_out = state.get("output_dir", str(deps.settings.default_output_dir))
    out_dir = Path(raw_out) if Path(raw_out).is_absolute() else (deps.settings.root_dir / raw_out).resolve()

    excerpts = "\n\n".join(f"=== {k} ===\n{v[:1800]}" for k, v in sorted(volumes.items()))
    stats = deps.vault.stats()
    judge_prompt = (
        f"EvidenceVault Stats: {json.dumps(stats, ensure_ascii=False)}\n\n"
        f"=== DELIVERABLES EXCERPTS ===\n{excerpts}"
    )
    rubric = await deps.llm.complete_json(
        tier="critic",
        node="stage7_judge",
        system_prompt=JUDGE_SYSTEM,
        user_prompt=judge_prompt,
        schema=JudgeRubricScores,
        max_tokens=2000,
    )
    scorecard = export_all_deliverables(
        deps=deps,
        output_dir=out_dir,
        volumes=volumes,
        judge_rubric=rubric.model_dump(),
        run_id=state.get("run_id", "bfbg-langgraph"),
        profile=state.get("profile", "flagship"),
        llm_engine=f"dashscope:{deps.settings.producer_model}+{deps.settings.critic_model}",
        extra_telemetry={"critic_history": state.get("critic_history", [])},
    )
    return {"judge_rubric": rubric.model_dump(), "final_manifest": scorecard}
