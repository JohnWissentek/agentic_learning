"""Rich CLI entrypoint (`pso-research`) for verifying keys, collecting evidence, running, and auditing."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from pso_workflow.config import CostLedger, DashScopeLLMGateway, WorkflowSettings
from pso_workflow.graph import (
    build_workflow_graph,
    create_async_checkpointer_ctx,
    create_default_deps,
)
from pso_workflow.nodes.critic_and_judge import deterministic_contract_checks
from pso_workflow.nodes.storm_and_rank import _update_elo
from pso_workflow.nodes.synthesizer import render_evidence_index
from pso_workflow.prompts import JUDGE_SYSTEM
from pso_workflow.schemas import (
    EvaluatedOpportunity,
    JudgeRubricScores,
    OpportunityStormMemo,
    ROIInputs,
    TechOpportunitySeed,
)
from pso_workflow.tools.evidence_vault import EvidenceVault
from pso_workflow.tools.roi_calculator import (
    compute_roi_metrics,
    compute_weighted_pillar_score,
)
from pso_workflow.tools.search_router import MetasoClient, SerperClient

console = Console()


def _mask(secret: str) -> str:
    if not secret:
        return "[red]<missing>[/red]"
    if len(secret) <= 10:
        return "<set>"
    return f"{secret[:5]}...{secret[-4:]}"


async def _cmd_verify_env(settings: WorkflowSettings) -> int:
    table = Table(title="PSO Workflow Environment Verification (.env.ai_search & .env.llm)")
    table.add_column("Service", style="bold cyan")
    table.add_column("Credential", style="dim")
    table.add_column("Status")
    table.add_column("Detail")

    all_ok = True

    # 1. Metaso
    if not settings.metaso_api_key:
        table.add_row("Metaso AI Search", _mask(""), "[red]FAIL[/red]", "METASO_API_KEY missing")
        all_ok = False
    else:
        try:
            mc = MetasoClient(settings.metaso_api_key, settings.metaso_api_base)
            hits, credits = await mc.search(query="特高压 环保气体 在线监测", scope="webpage", size=2)
            table.add_row(
                "Metaso AI Search",
                _mask(settings.metaso_api_key),
                "[green]PASS[/green]",
                f"hits={len(hits)}, credits={credits}",
            )
        except Exception as exc:
            table.add_row("Metaso AI Search", _mask(settings.metaso_api_key), "[red]FAIL[/red]", str(exc))
            all_ok = False

    # 2. Serper
    if not settings.serper_api_key:
        table.add_row("Serper Google API", _mask(""), "[red]FAIL[/red]", "SERPER_API_KEY missing")
        all_ok = False
    else:
        try:
            sc = SerperClient(settings.serper_api_key, settings.serper_time_range)
            hits = await sc.search(query="semiconductor inline metrology yield ROI", num=2)
            table.add_row(
                "Serper Google API",
                _mask(settings.serper_api_key),
                "[green]PASS[/green]",
                f"organic_hits={len(hits)}",
            )
        except Exception as exc:
            table.add_row("Serper Google API", _mask(settings.serper_api_key), "[red]FAIL[/red]", str(exc))
            all_ok = False

    # 3. DashScope Tiered Models
    if not settings.dashscope_api_key:
        table.add_row("DashScope LLM", _mask(""), "[red]FAIL[/red]", "DASHSCOPE_API_KEY missing")
        all_ok = False
    else:
        ledger = CostLedger()
        gw = DashScopeLLMGateway(settings, ledger)
        for label, tier, model in [
            (f"LLM FAST ({settings.fast_model})", "fast", settings.fast_model),
            (f"LLM PRODUCER ({settings.producer_model})", "producer", settings.producer_model),
            (f"LLM CRITIC ({settings.critic_model})", "critic", settings.critic_model),
        ]:
            try:
                out = await gw.complete_text(
                    tier=tier,
                    node="verify_env",
                    system_prompt="Reply strictly with OK.",
                    user_prompt="Reply OK",
                    max_tokens=16,
                )
                table.add_row(label, _mask(settings.dashscope_api_key), "[green]PASS[/green]", f"reply={out!r}")
            except Exception as exc:
                table.add_row(label, _mask(settings.dashscope_api_key), "[red]FAIL[/red]", str(exc))
                all_ok = False

    console.print(table)
    return 0 if all_ok else 1


async def _cmd_collect(settings: WorkflowSettings, sector: str, num_results: int) -> int:
    deps = create_default_deps(settings)
    tracks = settings.taxonomy.get("tracks", [])
    if sector == "power":
        tracks = [t for t in tracks if t["sector"] == "power_energy"]
    elif sector == "semiconductor":
        tracks = [t for t in tracks if t["sector"] == "semiconductor"]

    console.print(f"[bold cyan]Collecting dual-engine evidence for {len(tracks)} track(s)...[/bold cyan]")
    for t in tracks:
        tid = t["id"]
        for q in t.get("cn_queries", []):
            hits = await deps.search_router.search_track(
                track_id=tid,
                geo_scope="CN",
                query=q["query"],
                mode=q.get("scope", "webpage"),
                num_results=num_results,
            )
            for h in hits:
                deps.vault.upsert_hit(track_id=tid, hit=h)
        for q in t.get("global_queries", []):
            hits = await deps.search_router.search_track(
                track_id=tid,
                geo_scope="GLOBAL",
                query=q["query"],
                mode=q.get("endpoint", "search"),
                num_results=num_results,
            )
            for h in hits:
                deps.vault.upsert_hit(track_id=tid, hit=h)

    stats = deps.vault.stats()
    deps.vault.close()
    console.print("[green]EvidenceVault collection complete:[/green]", stats)
    return 0


async def _cmd_run(
    settings: WorkflowSettings,
    *,
    sector: str,
    profile: str,
    output_dir: str,
    thread_id: str,
    hitl: bool,
) -> int:
    deps = create_default_deps(settings)
    ckpt_db = settings.data_dir / "langgraph_checkpoints.db"
    out_path = Path(output_dir)
    if not out_path.is_absolute():
        out_path = settings.root_dir / out_path

    initial_state: dict[str, Any] = {
        "run_id": thread_id,
        "sector_filter": sector,
        "profile": profile,
        "output_dir": str(out_path),
        "hitl_enabled": hitl,
        "max_loops": settings.max_reflection_loops if profile == "flagship" else 1,
        "loop_count": 0,
        "recent_query_hashes": [],
        "track_dossiers": [],
        "draft_reports": {},
        "critique_history": [],
        "telemetry_events": [],
    }

    console.print(
        f"[bold cyan]Starting PSO Agentic Workflow[/bold cyan] | profile={profile} | "
        f"sector={sector} | thread_id={thread_id} | out={out_path}"
    )

    try:
        async with create_async_checkpointer_ctx(ckpt_db) as checkpointer:
            graph = build_workflow_graph(deps, checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            result = await graph.ainvoke(initial_state, config=config)
    finally:
        deps.vault.close()

    scorecard = result.get("evaluation_scorecard", {})
    rubric = scorecard.get("judge_rubric", {})
    cost = scorecard.get("cost_and_token_telemetry", {})
    ev = scorecard.get("evidence_vault_stats", {})

    console.print(
        f"\n[bold green]Workflow Complete![/bold green]\n"
        f"- Stage-Gate Passed: {scorecard.get('stage_gate_passed')} "
        f"(Score: {rubric.get('total_score')}/100)\n"
        f"- EvidenceVault: total={ev.get('total')} (CN={ev.get('cn_count')}, GLOBAL={ev.get('global_count')}, "
        f"fulltext={ev.get('with_fulltext_count')})\n"
        f"- Total Cost: ¥{cost.get('total_cost_cny')} CNY "
        f"(LLM calls={cost.get('total_llm_calls')}, Search calls={cost.get('total_search_calls')})\n"
        f"- Output Dir: {out_path}"
    )
    return 0


async def _cmd_evaluate(settings: WorkflowSettings, target_dir: str) -> int:
    out_path = Path(target_dir)
    if not out_path.is_absolute():
        out_path = settings.root_dir / out_path
    if not out_path.exists():
        console.print(f"[red]Output directory not found: {out_path}[/red]")
        return 1

    drafts = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(out_path.glob("0[0-5]_*.md"))
    }
    vault = EvidenceVault(settings.data_dir / "evidence_vault.db")
    stats = vault.stats()
    vault.close()

    det = deterministic_contract_checks(
        vault_stats=stats,
        drafts=drafts,
        evaluated_opps=[{}],
        contract=settings.contract,
    )
    ledger = CostLedger()
    gw = DashScopeLLMGateway(settings, ledger)
    excerpts = "\n\n".join(f"### {k}\n{v[:2500]}" for k, v in sorted(drafts.items()) if k != "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md")
    rubric = await gw.complete_structured(
        tier="critic",
        node="standalone_judge",
        system_prompt=JUDGE_SYSTEM,
        user_prompt=f"Deterministic Checks:\n{json.dumps(det, ensure_ascii=False)}\n\nExcerpts:\n{excerpts}",
        schema=JudgeRubricScores,
        max_tokens=8192,
    )
    total = round(
        rubric.china_first_then_global_depth
        + rubric.dual_horizon_3_5y_vs_5_10y_rigor
        + rubric.pain_point_and_physics_specificity
        + rubric.roi_and_industrial_upgrade_value
        + rubric.citation_grounding_and_prose,
        2,
    )
    rubric = rubric.model_copy(update={"total_score": total})
    console.print_json(data={"deterministic_checks": det, "judge_rubric": rubric.model_dump()})
    return 0


async def _cmd_prepare_context(settings: WorkflowSettings, sector: str, output_file: str) -> int:
    """Export grounded EvidenceVault context + deterministic PALMs ROI baselines for native workflow."""
    out_path = Path(output_file)
    if not out_path.is_absolute():
        out_path = settings.root_dir / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vault = EvidenceVault(settings.data_dir / "evidence_vault.db")
    try:
        stats = vault.stats()
    finally:
        vault.close()

    if stats.get("total", 0) < 48:
        await _cmd_collect(settings, sector, 6)

    vault = EvidenceVault(settings.data_dir / "evidence_vault.db")
    try:
        stats = vault.stats()
        tracks = list(settings.taxonomy.get("tracks", []))
        if sector == "power":
            tracks = [t for t in tracks if t.get("sector") == "power_energy"]
        elif sector == "semiconductor":
            tracks = [t for t in tracks if t.get("sector") == "semiconductor"]

        exported_tracks: list[dict[str, Any]] = []
        for t in tracks:
            tid = t["id"]
            records = vault.list_by_track(tid)
            cn_recs = [r for r in records if r.geo_scope == "CN"][:12]
            gl_recs = [r for r in records if r.geo_scope == "GLOBAL"][:10]
            pack = [
                {
                    "ev_id": r.ev_id,
                    "geo_scope": r.geo_scope,
                    "authority_tier": r.authority_tier,
                    "engine": r.engine,
                    "published_date": r.published_date,
                    "title": r.title,
                    "url": r.url,
                    "excerpt": (
                        r.full_markdown[:600] if r.full_markdown else r.snippet[:380]
                    ).replace("\n", " "),
                }
                for r in cn_recs + gl_recs
            ]

            seeds_out: list[dict[str, Any]] = []
            for s in t.get("seed_opportunities", []):
                roi_in = ROIInputs(**s["roi_baseline"])
                roi_m = compute_roi_metrics(roi_in)
                pillar = compute_weighted_pillar_score(
                    roi=roi_m,
                    china_priority=float(s.get("china_priority_score", 90.0)),
                    global_priority=float(s.get("global_priority_score", 88.0)),
                    horizon=s.get("horizon", "3-5y"),
                    evidence_count=min(4, len(pack)) or 2,
                )
                seeds_out.append(
                    {
                        "opp_id": s["opp_id"],
                        "track_id": tid,
                        "sector": t["sector"],
                        "title": s["title"],
                        "horizon": s["horizon"],
                        "china_priority_score": float(s.get("china_priority_score", 90.0)),
                        "global_priority_score": float(s.get("global_priority_score", 88.0)),
                        "physics_principle": s["physics_principle"],
                        "roi_baseline": s["roi_baseline"],
                        "roi_metrics": roi_m.model_dump(),
                        "weighted_pillar_score": pillar,
                    }
                )

            exported_tracks.append(
                {
                    "id": tid,
                    "sector": t["sector"],
                    "name": t["name"],
                    "manufacturing_stages": t.get("manufacturing_stages", []),
                    "evidence_count_cn": len([r for r in records if r.geo_scope == "CN"]),
                    "evidence_count_global": len([r for r in records if r.geo_scope == "GLOBAL"]),
                    "valid_ev_ids": [r.ev_id for r in records],
                    "evidence_pack": pack,
                    "seeds": seeds_out,
                }
            )

        payload = {
            "contract": settings.contract,
            "vault_stats": stats,
            "sector_filter": sector,
            "tracks": exported_tracks,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Prepared native context:[/green] tracks={len(exported_tracks)}, "
            f"evidences={stats.get('total')}, file={out_path}"
        )
        return 0
    finally:
        vault.close()


def _cmd_finalize_native(settings: WorkflowSettings, bundle_file: str, output_dir: str) -> int:
    """Apply deterministic PALMs ROI, Elo updates, EvIndex, Stage-Gate checks, and write 7 files."""
    b_path = Path(bundle_file)
    if not b_path.is_absolute():
        b_path = settings.root_dir / b_path
    out_path = Path(output_dir)
    if not out_path.is_absolute():
        out_path = settings.root_dir / out_path
    out_path.mkdir(parents=True, exist_ok=True)

    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    # Lookup calibrated taxonomy baselines to keep financial math 100% deterministic
    seed_by_opp: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for raw_track in settings.taxonomy.get("tracks", []):
        for s in raw_track.get("seed_opportunities", []):
            seed_by_opp[s["opp_id"]] = (raw_track, s)

    vault = EvidenceVault(settings.data_dir / "evidence_vault.db")
    try:
        all_records = vault.list_all()
        vault_stats = vault.stats()
        ev_by_track: dict[str, list[str]] = {}
        valid_ev_all: set[str] = set()
        for r in all_records:
            valid_ev_all.add(r.ev_id)
            ev_by_track.setdefault(r.track_id, []).append(r.ev_id)

        evaluated: list[EvaluatedOpportunity] = []
        seen_opps: dict[str, EvaluatedOpportunity] = {}
        for tr in bundle.get("track_results", []):
            tid = str(tr.get("track_id", ""))
            sector_val = str(tr.get("sector", "power_energy"))
            fallback_evs = ev_by_track.get(tid, [])[:4] or list(valid_ev_all)[:4]
            for raw_opp in tr.get("opportunities", []):
                oid = str(raw_opp.get("opp_id", ""))
                if not oid or oid in seen_opps:
                    continue
                if oid in seed_by_opp:
                    raw_track, base_seed = seed_by_opp[oid]
                    roi_in = ROIInputs(**base_seed["roi_baseline"])
                    horizon = base_seed["horizon"]
                    cn_prio = float(base_seed.get("china_priority_score", 90.0))
                    gl_prio = float(base_seed.get("global_priority_score", 88.0))
                    track_id = raw_track["id"]
                    sector_val = raw_track["sector"]
                else:
                    roi_in = ROIInputs(**(raw_opp.get("roi_inputs") or raw_opp.get("roi_baseline")))
                    horizon = str(raw_opp.get("horizon", "3-5y"))
                    cn_prio = float(raw_opp.get("china_priority_score", 86.0))
                    gl_prio = float(raw_opp.get("global_priority_score", 84.0))
                    track_id = tid

                cleaned_evs = [
                    str(eid) for eid in raw_opp.get("evidence_ids", []) if str(eid) in valid_ev_all
                ] or fallback_evs

                seed = TechOpportunitySeed(
                    opp_id=oid,
                    track_id=track_id,
                    sector=sector_val,  # type: ignore[arg-type]
                    title=str(raw_opp.get("title") or (seed_by_opp[oid][1]["title"] if oid in seed_by_opp else oid)),
                    horizon=horizon,  # type: ignore[arg-type]
                    china_priority_score=cn_prio,
                    global_priority_score=gl_prio,
                    physics_principle=str(
                        raw_opp.get("physics_principle")
                        or (seed_by_opp[oid][1]["physics_principle"] if oid in seed_by_opp else "")
                    ),
                    target_process_point=str(raw_opp.get("target_process_point") or "关键制造工段在线测控点"),
                    product_form_factor=str(raw_opp.get("product_form_factor") or "在线/旁路工业集成分析仪"),
                    quality_yield_mechanism=str(raw_opp.get("quality_yield_mechanism") or "实时缺陷拦截与闭环良率提升"),
                    cost_tco_mechanism=str(raw_opp.get("cost_tco_mechanism") or "降低报废、非计划停机及耗材成本"),
                    green_ehs_mechanism=str(raw_opp.get("green_ehs_mechanism") or "削减有毒泄漏、F-gas排放与单位能耗"),
                    industrial_upgrade_mechanism=str(
                        raw_opp.get("industrial_upgrade_mechanism") or "推动国产高端量检测装备自主可控与工艺升级"
                    ),
                    china_positioning=str(raw_opp.get("china_positioning") or "中国头部产线优先Spec-in切入"),
                    global_expansion_path=str(raw_opp.get("global_expansion_path") or "随中国产业链及国际标准认证出海"),
                    evidence_ids=cleaned_evs,
                    roi_inputs=roi_in,
                )
                roi = compute_roi_metrics(roi_in)
                pillar = compute_weighted_pillar_score(
                    roi=roi,
                    china_priority=seed.china_priority_score,
                    global_priority=seed.global_priority_score,
                    horizon=seed.horizon,
                    evidence_count=len(cleaned_evs),
                )
                storm_raw = raw_opp.get("storm") or raw_opp.get("storm_memo")
                storm_obj = None
                if isinstance(storm_raw, dict):
                    storm_payload = dict(storm_raw)
                    storm_payload.setdefault("opp_id", oid)
                    storm_obj = OpportunityStormMemo.model_validate(storm_payload)

                ev_opp = EvaluatedOpportunity(
                    seed=seed,
                    roi=roi,
                    storm_memo=storm_obj,
                    weighted_pillar_score=pillar,
                    elo_rating=1500.0 + (pillar - 75.0) * 4.0,
                )
                evaluated.append(ev_opp)
                seen_opps[oid] = ev_opp

        # Replay pairwise Elo tournament matches deterministically
        elo_matches = list(bundle.get("elo_matches", []))
        if elo_matches:
            for m in elo_matches:
                a_id = str(m.get("opp_a_id", ""))
                b_id = str(m.get("opp_b_id", ""))
                w_id = str(m.get("winner_id", ""))
                if a_id in seen_opps and b_id in seen_opps:
                    opp_a, opp_b = seen_opps[a_id], seen_opps[b_id]
                    a_won = w_id.strip() != b_id
                    new_a, new_b = _update_elo(opp_a.elo_rating, opp_b.elo_rating, a_won, k=32.0)
                    opp_a.elo_rating = new_a
                    opp_b.elo_rating = new_b
                    m["elo_a_after"] = new_a
                    m["elo_b_after"] = new_b

        if evaluated:
            elos = [e.elo_rating for e in evaluated]
            lo, hi = min(elos), max(elos)
            span = max(1.0, hi - lo)
            evaluated.sort(
                key=lambda e: 0.55 * e.weighted_pillar_score
                + 0.45 * (60.0 + ((e.elo_rating - lo) / span) * 38.0),
                reverse=True,
            )
            for idx, item in enumerate(evaluated, start=1):
                item.composite_rank = idx

        volumes = dict(bundle.get("volumes") or {})
        drafts: dict[str, str] = {
            k: str(v).strip() + "\n"
            for k, v in volumes.items()
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
        }
        drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(all_records)

        eval_dicts = [e.model_dump() for e in evaluated]
        det_checks = deterministic_contract_checks(
            vault_stats=vault_stats,
            drafts=drafts,
            evaluated_opps=eval_dicts,
            contract=settings.contract,
        )

        rubric = JudgeRubricScores.model_validate(bundle["judge_rubric"])
        exact_sum = round(
            rubric.china_first_then_global_depth
            + rubric.dual_horizon_3_5y_vs_5_10y_rigor
            + rubric.pain_point_and_physics_specificity
            + rubric.roi_and_industrial_upgrade_value
            + rubric.citation_grounding_and_prose,
            2,
        )
        rubric = rubric.model_copy(update={"total_score": exact_sum})

        pass_threshold = float(settings.contract.get("quality_gates", {}).get("stage_gate_pass_score", 85))
        stage_passed = bool(exact_sum >= pass_threshold and det_checks["all_5_volumes_non_empty"])

        written_files: list[str] = []
        for fname, content in sorted(drafts.items()):
            target = out_path / fname
            target.write_text(content, encoding="utf-8")
            written_files.append(str(target))

        search_queries_logged = int(
            vault._conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        )
        scorecard = {
            "run_id": bundle.get("run_id", f"native-{uuid.uuid4().hex[:8]}"),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "profile": bundle.get("profile", "flagship"),
            "sector_filter": bundle.get("sector_filter", "all"),
            "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
            "stage_gate_passed": stage_passed,
            "pass_threshold": pass_threshold,
            "judge_rubric": rubric.model_dump(),
            "deterministic_contract_checks": det_checks,
            "evidence_vault_stats": vault_stats,
            "evaluated_opportunities_top10": [
                {
                    "rank": e.composite_rank,
                    "opp_id": e.seed.opp_id,
                    "track_id": e.seed.track_id,
                    "sector": e.seed.sector,
                    "horizon": e.seed.horizon,
                    "title": e.seed.title,
                    "weighted_pillar_score": e.weighted_pillar_score,
                    "elo_rating": e.elo_rating,
                    "payback_months": e.roi.payback_months,
                    "irr_5yr_pct": e.roi.irr_5yr_pct,
                    "npv_5yr_cny": e.roi.npv_5yr_cny,
                    "payback_tier": e.roi.payback_tier,
                }
                for e in evaluated[:10]
            ],
            "elo_tournament_matches": elo_matches,
            "critique_loops_executed": int(bundle.get("critique_loops_executed", 0)),
            "critique_history": bundle.get("critique_history", []),
            "cost_and_token_telemetry": {
                "billing_mode": "Antigravity IDE Native Frontier Quota + Paid Search APIs (.env.ai_search)",
                "total_cost_cny": 0.0,
                "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
                "native_agent_invocations": bundle.get("native_agent_invocations", {}),
                "search_queries_in_vault": search_queries_logged,
            },
        }
        sc_path = out_path / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
        sc_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
        written_files.append(str(sc_path))

        console.print(
            f"[bold green]Native Antigravity Flagship Workflow Finalized![/bold green]\n"
            f"- Engine: {scorecard['llm_engine']} | Stage-Gate: {stage_passed} ({exact_sum}/100)\n"
            f"- Evidences: total={vault_stats.get('total')} (CN={vault_stats.get('cn_count')}, GLOBAL={vault_stats.get('global_count')})\n"
            f"- Deliverables written: {len(written_files)} -> {out_path}"
        )
        return 0 if stage_passed else 1
    finally:
        vault.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pso-research",
        description="Power & Semiconductor Online Testing Instrumentation Agentic Workflow",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify-env", help="Verify paid Metaso, Serper, and DashScope credentials")

    p_col = sub.add_parser("collect", help="Run dual-engine evidence collection into SQLite EvidenceVault")
    p_col.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_col.add_argument("--num-results", type=int, default=6)

    p_prep = sub.add_parser("prepare-context", help="Export grounded EvidenceVault + ROI baselines JSON for native IDE workflow")
    p_prep.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_prep.add_argument("--output", default="data/native_context_bundle.json")

    p_fin = sub.add_parser("finalize-native", help="Compute deterministic ROI/Elo/Judge checks and compile 7 outputs from native IDE bundle")
    p_fin.add_argument("--bundle", default="data/native_outputs_bundle.json")
    p_fin.add_argument("--output-dir", default="outputs/power_semiconductor_online_testing_2026_2036")

    p_run = sub.add_parser("run", help="Execute complete LangGraph opportunity discovery workflow")
    p_run.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_run.add_argument("--profile", choices=["flagship", "fast"], default="flagship")
    p_run.add_argument("--output-dir", default="outputs/power_semiconductor_online_testing_2026_2036")
    p_run.add_argument("--thread-id", default=f"pso-{uuid.uuid4().hex[:8]}")
    p_run.add_argument("--hitl", action="store_true", help="Enable Ch 13 HITL interrupt before search fan-out")

    p_eval = sub.add_parser("evaluate", help="Run Ch 19 Contract + LLM-as-a-Judge audit on an output folder")
    p_eval.add_argument("target_dir")

    args = parser.parse_args()
    settings = WorkflowSettings.load()

    if args.command == "verify-env":
        rc = asyncio.run(_cmd_verify_env(settings))
    elif args.command == "collect":
        rc = asyncio.run(_cmd_collect(settings, args.sector, args.num_results))
    elif args.command == "prepare-context":
        rc = asyncio.run(_cmd_prepare_context(settings, args.sector, args.output))
    elif args.command == "finalize-native":
        rc = _cmd_finalize_native(settings, args.bundle, args.output_dir)
    elif args.command == "run":
        rc = asyncio.run(
            _cmd_run(
                settings,
                sector=args.sector,
                profile=args.profile,
                output_dir=args.output_dir,
                thread_id=args.thread_id,
                hitl=args.hitl,
            )
        )
    elif args.command == "evaluate":
        rc = asyncio.run(_cmd_evaluate(settings, args.target_dir))
    else:
        rc = 2
    sys.exit(rc)


if __name__ == "__main__":
    main()
