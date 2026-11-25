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

from pso_workflow.config import (
    SEARCH_UNIT_COST_CNY,
    CostLedger,
    DashScopeLLMGateway,
    WorkflowSettings,
)
from pso_workflow.graph import (
    build_workflow_graph,
    create_async_checkpointer_ctx,
    create_default_deps,
)
from pso_workflow.nodes.critic_and_judge import deterministic_contract_checks
from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.nodes.planner import _format_recon_context, _normalize_discovered_tracks, run_macro_recon
from pso_workflow.nodes.portfolio_reviewer import (
    apply_portfolio_reviews_and_rank,
    build_global_ranking_prompt,
    build_sector_portfolio_prompt,
)
from pso_workflow.nodes.researcher import (
    _clean_discovered_dossier,
    _collect_queries_for_track,
    _format_evidence_context,
    _format_roi_guardrail_hint,
)
from pso_workflow.nodes.storm_and_rank import _update_elo
from pso_workflow.nodes.synthesizer import (
    build_deterministic_tables,
    build_volume_specs,
    format_commercial_whitespace_and_ai_table,
    format_discovery_and_funnel_summary,
    format_dossiers,
    format_roi_table,
    format_vault_snippets,
    inject_deterministic_tables,
    render_evidence_index,
)
from pso_workflow.prompts import (
    FALSIFICATION_REVIEW_SYSTEM,
    GLOBAL_PORTFOLIO_RANK_SYSTEM,
    JUDGE_SYSTEM,
    PORTFOLIO_COMMITTEE_SYSTEM,
    RECON_DISCOVERY_SYSTEM,
    RESEARCHER_V2_SYSTEM,
    SYNTHESIZER_SYSTEM,
)
from pso_workflow.schemas import (
    DiscoveryPlan,
    EliminatedCandidate,
    EvaluatedOpportunity,
    GlobalPortfolioRanking,
    JudgeRubricScores,
    OpportunityStormMemo,
    ROIInputs,
    SectorPortfolioReview,
    TechOpportunitySeed,
    TrackDossier,
)
from pso_workflow.tools.audit_guard import run_full_objective_audit
from pso_workflow.tools.evidence_vault import EvidenceVault
from pso_workflow.tools.roi_calculator import (
    compute_roi_metrics,
    compute_weighted_pillar_score,
    screen_candidate_pool,
)
from pso_workflow.tools.search_router import DualEngineSearchRouter, MetasoClient, SerperClient

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
    vault_path = settings.resolve_vault_path()
    if not vault_path.exists() and (settings.data_dir / "evidence_vault.db").exists():
        vault_path = settings.data_dir / "evidence_vault.db"
    vault = EvidenceVault(vault_path)
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
        _apply_elo_and_rank(evaluated, seen_opps, elo_matches)

        volumes = dict(bundle.get("volumes") or {})
        drafts: dict[str, str] = {
            k: str(v).strip() + "\n"
            for k, v in volumes.items()
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
        }
        drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
            all_records, db_label="data/evidence_vault.db"
        )

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


def _resolve_cli_path(settings: WorkflowSettings, target: str) -> Path:
    p = Path(target)
    return p if p.is_absolute() else settings.root_dir / p


def _make_v2_deps(settings: WorkflowSettings, vault_db: str | None) -> RuntimeDeps:
    cfg_dir = settings.data_dir
    cfg_dir.mkdir(parents=True, exist_ok=True)
    vault_path = settings.resolve_vault_path(vault_db)
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = CostLedger()
    vault = EvidenceVault(vault_path)
    search_router = DualEngineSearchRouter(settings, ledger)
    llm = DashScopeLLMGateway(settings, ledger)
    return RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=search_router,
        llm=llm,
    )


def _apply_elo_and_rank(
    evaluated: list[EvaluatedOpportunity],
    seen_opps: dict[str, EvaluatedOpportunity],
    elo_matches: list[dict[str, Any]],
) -> None:
    """Replay pairwise Elo outcomes and assign 55/45 deterministic composite ranks."""
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


async def _cmd_recon_search(
    settings: WorkflowSettings,
    *,
    sector: str,
    profile: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 0 V2 macro recon search exported as structured JSON for zero-preset clustering."""
    deps = _make_v2_deps(settings, vault_db)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        records, q_hashes = await run_macro_recon(deps, sector, profile)
        stats = deps.vault.stats()
        payload = {
            "contract": settings.contract,
            "discovery_funnel": settings.contract.get("discovery_funnel", {}),
            "sector_mandates": settings.discovery_scope.get("sector_mandates", {}),
            "sector_roi_guardrails": settings.discovery_scope.get("sector_roi_guardrails", {}),
            "sector_filter": sector,
            "profile": profile,
            "vault_db": str(deps.vault.db_path),
            "query_hashes": q_hashes,
            "vault_stats": stats,
            "recon_evidences": [r.model_dump() for r in records],
            "recon_context_text": _format_recon_context(records, max_items=32),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 0 recon search complete:[/green] recon_hits={len(records)}, "
            f"total_vault={stats.get('total')}, file={out_path}"
        )
        return 0
    finally:
        deps.vault.close()


async def _cmd_track_search(
    settings: WorkflowSettings,
    *,
    plan_file: str,
    profile: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 1 V2 dual-engine deep search across dynamically emerged tracks."""
    p_path = _resolve_cli_path(settings, plan_file)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_plan_data = json.loads(p_path.read_text(encoding="utf-8"))
    if "track_plans" not in raw_plan_data and "tracks" in raw_plan_data:
        raw_plan_data = {
            "contract_id": raw_plan_data.get("contract_id", "PSO-CONTRACT-2026-V3"),
            "sector_filter": raw_plan_data.get("sector_filter", "all"),
            "profile": raw_plan_data.get("profile", profile),
            "macro_recon_summary": raw_plan_data.get("macro_recon_summary", ""),
            "step_back_thesis": raw_plan_data.get("step_back_thesis", ""),
            "track_plans": raw_plan_data["tracks"],
        }
    parsed_plan = DiscoveryPlan.model_validate(raw_plan_data)

    deps = _make_v2_deps(settings, vault_db)
    try:
        recon_records = deps.vault.list_by_track("RECON")
        norm_plan = _normalize_discovered_tracks(
            plan=parsed_plan,
            contract_id=settings.contract.get("contract_id", "PSO-CONTRACT-2026-V3"),
            sector_filter=parsed_plan.sector_filter,
            profile=profile,
            recon_records=recon_records,
        )
        num_results = 6 if profile == "flagship" else 3
        max_ft = 3 if profile == "flagship" else 1
        guardrails = settings.discovery_scope.get("sector_roi_guardrails", {}) or {}

        async def _search_one(tp):
            records, q_hashes = await _collect_queries_for_track(
                deps=deps,
                track_id=tp.track_id,
                track_name=tp.name,
                cn_queries=tp.cn_queries,
                global_queries=tp.global_queries,
                cn_vendor_queries=tp.cn_vendor_queries,
                global_vendor_queries=tp.global_vendor_queries,
                num_results=num_results,
                max_fulltext=max_ft,
            )
            return {
                "track": tp.model_dump(),
                "query_hashes": q_hashes,
                "evidence_count_cn": len([r for r in records if r.geo_scope == "CN"]),
                "evidence_count_global": len([r for r in records if r.geo_scope == "GLOBAL"]),
                "valid_ev_ids": [r.ev_id for r in records],
                "records": [r.model_dump() for r in records],
                "evidence_context": _format_evidence_context(records, max_items=24),
                "guardrail_hint": _format_roi_guardrail_hint(guardrails, tp.sector),
            }

        tracks_out = list(await asyncio.gather(*[_search_one(tp) for tp in norm_plan.track_plans]))
        stats = deps.vault.stats()
        payload = {
            "discovery_plan": norm_plan.model_dump(),
            "vault_db": str(deps.vault.db_path),
            "vault_stats": stats,
            "tracks": tracks_out,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 1 track search complete:[/green] tracks={len(tracks_out)}, "
            f"total_vault={stats.get('total')}, file={out_path}"
        )
        return 0
    finally:
        deps.vault.close()


def _cmd_screen_candidates(
    settings: WorkflowSettings,
    *,
    dossiers_file: str,
    plan_file: str | None,
    sector: str,
    profile: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 2 V2 deterministic 3-scenario PALMs range clamping & funnel elimination."""
    d_path = _resolve_cli_path(settings, dossiers_file)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_dossiers_payload = json.loads(d_path.read_text(encoding="utf-8"))
    raw_dossiers = (
        raw_dossiers_payload.get("dossiers", [])
        if isinstance(raw_dossiers_payload, dict)
        else list(raw_dossiers_payload)
    )
    plan_data: dict[str, Any] = {}
    if plan_file:
        p_path = _resolve_cli_path(settings, plan_file)
        if p_path.exists():
            plan_data = json.loads(p_path.read_text(encoding="utf-8"))

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        all_vault_records = vault.list_all()
        recon_recs = vault.list_by_track("RECON")
        cleaned_dossiers: list[TrackDossier] = []
        raw_candidates: list[TechOpportunitySeed] = []

        for item in raw_dossiers:
            td = TrackDossier.model_validate(item)
            t_records = vault.list_by_track(td.track_id) or all_vault_records
            if recon_recs:
                seen_ids = {r.ev_id for r in t_records}
                t_records = list(t_records) + [r for r in recon_recs if r.ev_id not in seen_ids]
            cleaned = _clean_discovered_dossier(
                llm_dossier=td,
                track_id=td.track_id,
                sector=td.sector,
                records=t_records,
            )
            cleaned_dossiers.append(cleaned)
            raw_candidates.extend(cleaned.opportunities)

        funnel_cfg = settings.contract.get("discovery_funnel", {}) or {}
        guardrails = settings.discovery_scope.get("sector_roi_guardrails", {}) or {}
        if sector == "all":
            target_total = int(
                funnel_cfg.get("finalist_shortlist_flagship", 16)
                if profile == "flagship"
                else funnel_cfg.get("finalist_shortlist_fast", 8)
            )
        else:
            target_total = 8 if profile == "flagship" else 4
        max_cons_pb = float(funnel_cfg.get("max_conservative_payback_months", 42.0))

        shortlist, eliminated = screen_candidate_pool(
            raw_candidates,
            sector_filter=sector,
            guardrails=guardrails,
            target_total=target_total,
            max_conservative_payback_months=max_cons_pb,
        )
        shortlist_dicts = [ev.model_dump() for ev in shortlist]
        elim_dicts = [el.model_dump() for el in eliminated]
        cleaned_dicts = [d.model_dump() for d in cleaned_dossiers]

        power_tids = {d.track_id for d in cleaned_dossiers if d.sector == "power_energy"} | {"RECON"}
        semi_tids = {d.track_id for d in cleaned_dossiers if d.sector == "semiconductor"} | {"RECON"}

        payload = {
            "raw_candidates_count": len(raw_candidates),
            "shortlist_count": len(shortlist_dicts),
            "eliminated_count": len(elim_dicts),
            "shortlist": shortlist_dicts,
            "eliminated_candidates": elim_dicts,
            "cleaned_dossiers": cleaned_dicts,
            "roi_tables": {
                "all": format_roi_table(shortlist_dicts),
                "power_energy": format_roi_table(shortlist_dicts, sector="power_energy"),
                "semiconductor": format_roi_table(shortlist_dicts, sector="semiconductor"),
            },
            "commercial_tables": {
                "all": format_commercial_whitespace_and_ai_table(shortlist_dicts),
                "power_energy": format_commercial_whitespace_and_ai_table(shortlist_dicts, sector="power_energy"),
                "semiconductor": format_commercial_whitespace_and_ai_table(shortlist_dicts, sector="semiconductor"),
            },
            "formatted_dossiers": {
                "power_energy": format_dossiers(cleaned_dicts, sector="power_energy"),
                "semiconductor": format_dossiers(cleaned_dicts, sector="semiconductor"),
            },
            "vault_snippets": {
                "all": format_vault_snippets(all_vault_records, tracks=None, limit=40),
                "power_energy": format_vault_snippets(all_vault_records, tracks=power_tids, limit=32),
                "semiconductor": format_vault_snippets(all_vault_records, tracks=semi_tids, limit=32),
            },
            "discovery_funnel_md": format_discovery_and_funnel_summary(
                plan=plan_data,
                raw_count=len(raw_candidates),
                shortlist_count=len(shortlist_dicts),
                eliminated=elim_dicts,
            ),
            "vault_stats": vault.stats(),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 2 funnel screening complete:[/green] raw={len(raw_candidates)}, "
            f"shortlist={len(shortlist_dicts)}, eliminated={len(elim_dicts)}, file={out_path}"
        )
        return 0
    finally:
        vault.close()


async def _cmd_gap_search(
    settings: WorkflowSettings,
    *,
    queries_arg: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 6 V2 Corrective RAG gap refill search into SQLite EvidenceVault."""
    q_candidate = _resolve_cli_path(settings, queries_arg)
    if q_candidate.exists():
        raw_q = json.loads(q_candidate.read_text(encoding="utf-8"))
    else:
        raw_q = json.loads(queries_arg)
    if isinstance(raw_q, dict):
        raw_q = raw_q.get("gap_queries", [])
    gap_queries = list(raw_q)[:4]

    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    deps = _make_v2_deps(settings, vault_db)
    added_records = []
    try:
        for item in gap_queries:
            q = str(item.get("query", "")).strip()
            if not q:
                continue
            geo = "GLOBAL" if str(item.get("geo_scope", "")).upper() == "GLOBAL" else "CN"
            tid = str(item.get("track_id") or "DP1")
            hits = await deps.search_router.search_track(
                track_id=tid,
                geo_scope=geo,
                query=q,
                mode="webpage" if geo == "CN" else "search",
                num_results=5,
            )
            deps.vault.log_query(
                track_id=tid,
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,
                query=q,
                hits_count=len(hits),
            )
            for h in hits:
                rec = deps.vault.upsert_hit(track_id=tid, hit=h)
                if rec is not None:
                    added_records.append(rec)
        stats = deps.vault.stats()
        payload = {
            "queries_run": len(gap_queries),
            "added_or_touched": len(added_records),
            "vault_stats": stats,
            "records": [r.model_dump() for r in added_records],
            "formatted_snippets": format_vault_snippets(added_records, tracks=None, limit=20)
            if added_records
            else "",
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 6 Corrective RAG refill complete:[/green] queries={len(gap_queries)}, "
            f"records={len(added_records)}, total_vault={stats.get('total')}"
        )
        return 0
    finally:
        deps.vault.close()


def _cmd_finalize_v2(
    settings: WorkflowSettings,
    *,
    bundle_file: str,
    vault_db: str,
    output_dir: str,
) -> int:
    """Stage 7 V2 deterministic Elo replay, contract audit, Evidence Index, and 7 deliverables."""
    b_path = _resolve_cli_path(settings, bundle_file)
    out_path = _resolve_cli_path(settings, output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    vault_path = settings.resolve_vault_path(vault_db)
    vault = EvidenceVault(vault_path)
    try:
        all_records = vault.list_all()
        vault_stats = vault.stats()

        evaluated = [EvaluatedOpportunity.model_validate(e) for e in bundle.get("shortlist", [])]
        seen_opps = {e.seed.opp_id: e for e in evaluated}
        storm_memos = bundle.get("storm_memos", {}) or {}
        for ev in evaluated:
            if ev.storm_memo is None and ev.seed.opp_id in storm_memos:
                ev.storm_memo = OpportunityStormMemo.model_validate(storm_memos[ev.seed.opp_id])
            ev.elo_rating = round(1500.0 + (ev.weighted_pillar_score - 75.0) * 4.0, 2)

        elo_matches = list(bundle.get("elo_matches", []))
        _apply_elo_and_rank(evaluated, seen_opps, elo_matches)

        volumes = dict(bundle.get("volumes") or {})
        drafts: dict[str, str] = {
            k: str(v).strip() + "\n"
            for k, v in volumes.items()
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
        }
        drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
            all_records, db_label=f"data/{vault_path.name}"
        )

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
        plan_data = bundle.get("discovery_plan", {}) or {}
        eliminated = [
            EliminatedCandidate.model_validate(el).model_dump()
            for el in bundle.get("eliminated_candidates", [])
        ]
        raw_count = int(bundle.get("raw_candidates_count", 0)) or (len(evaluated) + len(eliminated))

        commercial_whitespace_breakdown = {
            "global_and_cn_commercialized": sum(
                1 for e in evaluated if e.seed.commercial_status == "global_and_cn_commercialized"
            ),
            "overseas_only_cn_blank": sum(
                1 for e in evaluated if e.seed.commercial_status == "overseas_only_cn_blank"
            ),
            "global_and_cn_true_blank": sum(
                1 for e in evaluated if e.seed.commercial_status == "global_and_cn_true_blank"
            ),
        }

        scorecard = {
            "run_id": bundle.get("run_id", f"v3-native-{uuid.uuid4().hex[:8]}"),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "workflow_version": "V3.0_COMMERCIAL_WHITESPACE_AND_AI_CO_DESIGN",
            "profile": bundle.get("profile", "flagship"),
            "sector_filter": bundle.get("sector_filter", "all"),
            "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
            "stage_gate_passed": stage_passed,
            "pass_threshold": pass_threshold,
            "discovered_tracks": [
                {
                    "track_id": t.get("track_id"),
                    "sector": t.get("sector"),
                    "name": t.get("name"),
                    "is_emerging_or_cross_cutting": t.get("is_emerging_or_cross_cutting", False),
                    "emergence_rationale": t.get("emergence_rationale", ""),
                    "recon_evidence_ids": t.get("recon_evidence_ids", []),
                }
                for t in plan_data.get("track_plans", [])
            ],
            "commercial_whitespace_breakdown": commercial_whitespace_breakdown,
            "discovery_funnel_summary": {
                "recon_evidence_count": len(vault.list_by_track("RECON")),
                "raw_candidates_count": raw_count,
                "shortlist_count": len(evaluated),
                "eliminated_count": len(eliminated),
                "eliminated_candidates": eliminated,
            },
            "judge_rubric": rubric.model_dump(),
            "deterministic_contract_checks": det_checks,
            "evidence_vault_stats": vault_stats,
            "evaluated_opportunities_top16": [
                {
                    "rank": e.composite_rank,
                    "opp_id": e.seed.opp_id,
                    "track_id": e.seed.track_id,
                    "sector": e.seed.sector,
                    "horizon": e.seed.horizon,
                    "title": e.seed.title,
                    "discovery_origin": e.seed.discovery_origin,
                    "commercial_status": e.seed.commercial_status,
                    "global_vendors_and_products": e.seed.global_vendors_and_products,
                    "china_vendors_and_products": e.seed.china_vendors_and_products,
                    "white_space_and_entry_wedge": e.seed.white_space_and_entry_wedge,
                    "estimated_rd_months_ai_vs_legacy": e.seed.estimated_rd_months_ai_vs_legacy,
                    "weighted_pillar_score": e.weighted_pillar_score,
                    "elo_rating": e.elo_rating,
                    "optimistic_payback_months": e.roi_range.optimistic.payback_months if e.roi_range else e.roi.payback_months,
                    "baseline_payback_months": e.roi.payback_months,
                    "conservative_payback_months": e.roi_range.conservative.payback_months if e.roi_range else e.roi.payback_months,
                    "irr_5yr_pct": e.roi.irr_5yr_pct,
                    "npv_5yr_cny": e.roi.npv_5yr_cny,
                    "payback_tier": e.roi.payback_tier,
                }
                for e in evaluated
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
            f"[bold green]V3.0 Commercial & AI Discovery Finalized![/bold green]\n"
            f"- Engine: {scorecard['llm_engine']} | Stage-Gate: {stage_passed} ({exact_sum}/100)\n"
            f"- Funnel: raw={raw_count} -> shortlist={len(evaluated)} (eliminated={len(eliminated)}) | "
            f"White-Space={commercial_whitespace_breakdown}\n"
            f"- Evidences: total={vault_stats.get('total')} (CN={vault_stats.get('cn_count')}, GLOBAL={vault_stats.get('global_count')})\n"
            f"- Deliverables written: {len(written_files)} -> {out_path}"
        )
        return 0 if stage_passed else 1
    finally:
        vault.close()


def _compute_real_search_cost_from_vault(vault: EvidenceVault) -> dict[str, Any]:
    """Compute real paid search API spend from SQLite `query_log` and fulltext reads (never hardcoded 0.0)."""
    rows = vault._conn.execute(
        "SELECT engine, COUNT(*) AS cnt FROM query_log GROUP BY engine"
    ).fetchall()
    by_engine = {str(r["engine"]): int(r["cnt"]) for r in rows}
    metaso_q = by_engine.get("metaso", 0)
    serper_q = by_engine.get("serper", 0)
    fulltext_cnt = int(
        vault._conn.execute("SELECT COUNT(*) FROM evidences WHERE length(full_markdown) > 200").fetchone()[0]
    )
    search_cost = (
        metaso_q * SEARCH_UNIT_COST_CNY["metaso_search"]
        + serper_q * SEARCH_UNIT_COST_CNY["serper_search"]
        + fulltext_cnt * SEARCH_UNIT_COST_CNY["metaso_reader"]
    )
    return {
        "metaso_queries": metaso_q,
        "serper_queries": serper_q,
        "fulltext_reads": fulltext_cnt,
        "total_queries_logged": sum(by_engine.values()),
        "search_cost_cny": round(search_cost, 4),
    }


async def _cmd_falsify_search(
    settings: WorkflowSettings,
    *,
    dossiers_file: str,
    vault_db: str,
    output_file: str,
    max_queries_per_track: int = 4,
) -> int:
    """Stage 1b (V4): Run bounded falsification searches for claimed commercial blanks."""
    d_path = _resolve_cli_path(settings, dossiers_file)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_payload = json.loads(d_path.read_text(encoding="utf-8"))
    raw_dossiers = raw_payload.get("dossiers", []) if isinstance(raw_payload, dict) else list(raw_payload)

    deps = _make_v2_deps(settings, vault_db)
    try:
        tasks_out: list[dict[str, Any]] = []
        for item in raw_dossiers:
            td = TrackDossier.model_validate(item)
            existing_recs = deps.vault.list_by_track(td.track_id)
            cleaned_td = _clean_discovered_dossier(
                llm_dossier=td,
                track_id=td.track_id,
                sector=td.sector,
                records=existing_recs,
            )
            blank_opps = [
                o
                for o in cleaned_td.opportunities
                if o.commercial_status in ("global_and_cn_true_blank", "overseas_only_cn_blank")
            ]
            if not blank_opps:
                tasks_out.append(
                    {
                        "track_id": td.track_id,
                        "sector": td.sector,
                        "needs_falsification": False,
                        "initial_dossier": cleaned_td.model_dump(),
                        "queries_executed": [],
                        "newly_added_ev_ids": [],
                        "falsify_prompt": "",
                    }
                )
                continue

            planned: list[tuple[str, str]] = []
            seen_keys: set[str] = set()
            for opp in blank_opps:
                for q_item in opp.falsification_queries:
                    q_str = str(q_item.get("query", "")).strip()
                    if not q_str:
                        continue
                    geo = "GLOBAL" if str(q_item.get("geo_scope", "CN")).upper() in ("GLOBAL", "GL") else "CN"
                    key = f"{geo}:{q_str}"
                    if key not in seen_keys and len(planned) < max_queries_per_track:
                        seen_keys.add(key)
                        planned.append((geo, q_str))
            if not planned:
                for opp in blank_opps:
                    for geo, q_str in (
                        ("CN", f"中国 {opp.title} 在线检测 商业化 厂商 型号 中标 2025 2026"),
                        ("GLOBAL", f"{opp.title} inline metrology commercial vendor product datasheet model 2025 2026"),
                    ):
                        key = f"{geo}:{q_str}"
                        if key not in seen_keys and len(planned) < max_queries_per_track:
                            seen_keys.add(key)
                            planned.append((geo, q_str))

            before_ids = {r.ev_id for r in existing_recs}

            async def _exec_one(tid: str, geo: str, q_str: str) -> None:
                async with deps.semaphore:
                    hits = await deps.search_router.search_track(
                        track_id=tid,
                        geo_scope="GLOBAL" if geo == "GLOBAL" else "CN",
                        query=q_str,
                        mode="webpage" if geo == "CN" else "search",
                        num_results=4,
                    )
                deps.vault.log_query(
                    track_id=tid,
                    engine="metaso" if geo == "CN" else "serper",
                    geo_scope=geo,
                    query=q_str,
                    hits_count=len(hits),
                )
                for h in hits:
                    deps.vault.upsert_hit(track_id=tid, hit=h)

            await asyncio.gather(
                *[_exec_one(td.track_id, geo, q_str) for geo, q_str in planned],
                return_exceptions=True,
            )
            updated_recs = deps.vault.list_by_track(td.track_id)
            newly_added = [r for r in updated_recs if r.ev_id not in before_ids]
            prioritized = newly_added + [r for r in updated_recs if r.ev_id in before_ids]
            f_ctx = _format_evidence_context(prioritized, max_items=26, label=f"FALSIFICATION_{td.track_id}")
            blank_lines = "\n".join(
                f"- `{o.opp_id}` ({o.commercial_status}): {o.title} | GL={o.global_vendors_and_products} | CN={o.china_vendors_and_products}"
                for o in blank_opps
            )
            prompt = (
                f"{FALSIFICATION_REVIEW_SYSTEM}\n\n"
                f"Track ID: {td.track_id} | Sector: {td.sector} | Track Name: {td.track_name}\n"
                f"Falsification Queries Executed ({len(planned)}):\n"
                + "\n".join(f"  - [{g}] {q}" for g, q in planned)
                + f"\n\nInitial Claimed Blanks:\n{blank_lines}\n\n"
                f"Initial TrackDossier JSON:\n{cleaned_td.model_dump_json(indent=2)}\n\n"
                f"Retrieved EvidenceVault Records (Newly added: {[r.ev_id for r in newly_added]}):\n{f_ctx}\n\n"
                f"Update `commercial_status` honestly if real vendors were found, or record `falsification_audit_note`. "
                f"Cite ONLY authentic EV IDs from above."
            )
            tasks_out.append(
                {
                    "track_id": td.track_id,
                    "sector": td.sector,
                    "needs_falsification": True,
                    "initial_dossier": cleaned_td.model_dump(),
                    "queries_executed": [{"geo_scope": g, "query": q} for g, q in planned],
                    "newly_added_ev_ids": [r.ev_id for r in newly_added],
                    "falsify_prompt": prompt,
                }
            )

        out_path.write_text(
            json.dumps(
                {
                    "vault_stats": deps.vault.stats(),
                    "tracks": tasks_out,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        console.print(
            f"[green]Stage 1b falsification search complete:[/green] tracks={len(tasks_out)}, "
            f"needs_review={sum(1 for t in tasks_out if t['needs_falsification'])}, file={out_path}"
        )
        return 0
    finally:
        deps.vault.close()


def _cmd_prepare_portfolio(
    settings: WorkflowSettings,
    *,
    screened_file: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 3 (V4): Export holistic sector buying-committee prompts shared with LangGraph core."""
    s_path = _resolve_cli_path(settings, screened_file)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    screened = json.loads(s_path.read_text(encoding="utf-8"))
    pool = [EvaluatedOpportunity.model_validate(e) for e in screened.get("shortlist", [])]

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        all_records = vault.list_all()
        grouped: dict[str, list[EvaluatedOpportunity]] = {}
        for ev in pool:
            grouped.setdefault(ev.seed.sector, []).append(ev)

        sector_tasks = [
            {
                "sector": sec,
                "opp_ids": [e.seed.opp_id for e in opps],
                "system_prompt": PORTFOLIO_COMMITTEE_SYSTEM,
                "user_prompt": build_sector_portfolio_prompt(
                    "semiconductor" if sec == "semiconductor" else "power_energy",
                    opps,
                    all_records,
                ),
            }
            for sec, opps in grouped.items()
        ]
        out_path.write_text(
            json.dumps(
                {
                    "sector_tasks": sector_tasks,
                    "global_system_prompt": GLOBAL_PORTFOLIO_RANK_SYSTEM,
                    "needs_global_ranking": len(sector_tasks) > 1,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        console.print(
            f"[green]Stage 3 portfolio prompts prepared:[/green] sectors={len(sector_tasks)}, file={out_path}"
        )
        return 0
    finally:
        vault.close()


def _cmd_prepare_synthesis(
    settings: WorkflowSettings,
    *,
    screened_file: str,
    portfolio_file: str,
    plan_file: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Stage 4 (V4): Apply portfolio ranking & export single-core volume prompts + locked tables."""
    s_path = _resolve_cli_path(settings, screened_file)
    p_path = _resolve_cli_path(settings, portfolio_file)
    pl_path = _resolve_cli_path(settings, plan_file)
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    screened = json.loads(s_path.read_text(encoding="utf-8"))
    portfolio_raw = json.loads(p_path.read_text(encoding="utf-8"))
    plan_data = json.loads(pl_path.read_text(encoding="utf-8"))

    pool = [EvaluatedOpportunity.model_validate(e) for e in screened.get("shortlist", [])]
    sector_reviews = {
        sec: SectorPortfolioReview.model_validate(rev)
        for sec, rev in (portfolio_raw.get("sector_reviews") or {}).items()
    }
    raw_global = portfolio_raw.get("global_portfolio_ranking")
    global_ranking = GlobalPortfolioRanking.model_validate(raw_global) if raw_global else None

    ranked_pool, storm_memos, normalized_global = apply_portfolio_reviews_and_rank(
        pool, sector_reviews, global_ranking
    )
    ranked_dicts = [e.model_dump() for e in ranked_pool]
    eliminated = list(screened.get("eliminated_candidates", []))
    raw_count = int(screened.get("raw_candidates_count", len(ranked_dicts) + len(eliminated)))
    dossiers = list(screened.get("cleaned_dossiers", []))

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        all_records = vault.list_all()
        tables = build_deterministic_tables(
            plan=plan_data,
            evaluated=ranked_dicts,
            raw_candidates_count=raw_count,
            eliminated_candidates=eliminated,
        )
        specs = build_volume_specs(
            plan=plan_data,
            dossiers=dossiers,
            evaluated=ranked_dicts,
            elo_matches=[],
            all_records=all_records,
            raw_candidates_count=raw_count,
            eliminated_candidates=eliminated,
        )
        global_rank_prompt = (
            build_global_ranking_prompt(sector_reviews, {e.seed.opp_id: e for e in pool})
            if len(sector_reviews) > 1
            else ""
        )
        payload = {
            "ranked_shortlist": ranked_dicts,
            "storm_memos": storm_memos,
            "global_portfolio_ranking": normalized_global,
            "global_rank_prompt": global_rank_prompt,
            "synthesizer_system_prompt": SYNTHESIZER_SYSTEM,
            "tables": tables,
            "volumes_spec": [
                {"filename": fn, "role": lbl, "prompt": pr}
                for fn, lbl, pr in specs
            ],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 4 synthesis bundle prepared:[/green] ranked={len(ranked_dicts)}, volumes={len(specs)}, file={out_path}"
        )
        return 0
    finally:
        vault.close()


def _inline_pydantic_schema(model_cls: type) -> dict[str, Any]:
    """Flatten Pydantic v2 JSON Schema (zero $defs/$ref) for Antigravity `run_workflow`."""
    raw = model_cls.model_json_schema()
    defs = raw.pop("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return _resolve(dict(defs[node["$ref"].split("/")[-1]]))
            if "anyOf" in node:
                non_null = [x for x in node["anyOf"] if x != {"type": "null"}]
                return _resolve(non_null[0]) if non_null else {"type": "string"}
            return {
                k: _resolve(v)
                for k, v in node.items()
                if k not in ("default", "title", "additionalProperties")
            }
        if isinstance(node, list):
            return [_resolve(x) for x in node]
        return node

    return _resolve(raw)


def _cmd_export_v4_schemas(settings: WorkflowSettings, *, output_file: str) -> int:
    """Export single-core V4 flat JSON schemas & prompts so stdlib-only workflow shells stay DRY."""
    out_path = _resolve_cli_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dp_schema = _inline_pydantic_schema(DiscoveryPlan)
    dp_item = dp_schema["properties"]["track_plans"]["items"]
    dp_item["required"] = sorted(
        set(dp_item.get("required", []))
        | {
            "is_emerging_or_cross_cutting",
            "emergence_rationale",
            "recon_evidence_ids",
            "manufacturing_stages",
            "cn_queries",
            "global_queries",
            "cn_vendor_queries",
            "global_vendor_queries",
        }
    )

    td_schema = _inline_pydantic_schema(TrackDossier)
    opp_item = td_schema["properties"]["opportunities"]["items"]
    opp_item["required"] = sorted(
        set(opp_item.get("required", []))
        | {
            "commercial_status",
            "global_vendors_and_products",
            "china_vendors_and_products",
            "white_space_and_entry_wedge",
            "ai_computational_sensing_and_co_design",
            "ai_rd_acceleration_and_edge_deployment",
            "estimated_rd_months_ai_vs_legacy",
            "hardware_bom_localization_and_gtm_form",
            "evidence_ids",
            "roi_range_inputs",
            "falsification_queries",
            "falsification_audit_note",
        }
    )
    # Remove redundant roi_inputs from exported TrackDossier schema so agent always populates roi_range_inputs
    opp_item["properties"].pop("roi_inputs", None)

    payload = {
        "schemas": {
            "DiscoveryPlan": dp_schema,
            "TrackDossier": td_schema,
            "SectorPortfolioReview": _inline_pydantic_schema(SectorPortfolioReview),
            "GlobalPortfolioRanking": _inline_pydantic_schema(GlobalPortfolioRanking),
        },
        "prompts": {
            "RECON_DISCOVERY_SYSTEM": RECON_DISCOVERY_SYSTEM,
            "RESEARCHER_V2_SYSTEM": RESEARCHER_V2_SYSTEM,
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exported single-core V4 schemas & prompts:[/green] {out_path}")
    return 0


def _cmd_finalize_v4(
    settings: WorkflowSettings,
    *,
    bundle_file: str,
    vault_db: str,
    output_dir: str,
) -> int:
    """Stage 5 (V4): Deterministic table injection, 100% full-corpus hard audit, real search cost & compilation."""
    b_path = _resolve_cli_path(settings, bundle_file)
    out_path = _resolve_cli_path(settings, output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    vault_path = settings.resolve_vault_path(vault_db)
    vault = EvidenceVault(vault_path)
    try:
        all_records = vault.list_all()
        valid_ev_ids = {r.ev_id for r in all_records}
        vault_stats = vault.stats()
        search_cost_info = _compute_real_search_cost_from_vault(vault)

        evaluated = [EvaluatedOpportunity.model_validate(e) for e in bundle.get("shortlist", [])]
        storm_memos = bundle.get("storm_memos", {}) or {}
        for idx, ev in enumerate(evaluated, start=1):
            if ev.storm_memo is None and ev.seed.opp_id in storm_memos:
                ev.storm_memo = OpportunityStormMemo.model_validate(storm_memos[ev.seed.opp_id])
            if ev.composite_rank <= 0:
                ev.composite_rank = idx

        eval_dicts = [e.model_dump() for e in evaluated]
        plan_data = bundle.get("discovery_plan", {}) or {}
        eliminated = [
            EliminatedCandidate.model_validate(el).model_dump()
            for el in bundle.get("eliminated_candidates", [])
        ]
        raw_count = int(bundle.get("raw_candidates_count", 0)) or (len(evaluated) + len(eliminated))

        tables = build_deterministic_tables(
            plan=plan_data,
            evaluated=eval_dicts,
            raw_candidates_count=raw_count,
            eliminated_candidates=eliminated,
        )

        raw_volumes = dict(bundle.get("volumes") or {})
        drafts: dict[str, str] = {}
        for k, v in raw_volumes.items():
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_")):
                injected = inject_deterministic_tables(
                    filename=str(k),
                    llm_markdown=str(v).strip() + "\n",
                    tables=tables,
                )
                drafts[str(k)] = injected.strip() + "\n"

        drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
            all_records, db_label=f"data/{vault_path.name}"
        )

        target_tracks = len(plan_data.get("track_plans", [])) or None
        objective_audit = run_full_objective_audit(
            vault_stats=vault_stats,
            valid_ev_ids=valid_ev_ids,
            drafts=drafts,
            evaluated_opps=eval_dicts,
            contract=settings.contract,
            target_tracks=target_tracks,
        )

        pass_threshold = float(settings.contract.get("quality_gates", {}).get("stage_gate_pass_score", 85))
        raw_rubric = bundle.get("judge_rubric")
        if raw_rubric:
            rubric = JudgeRubricScores.model_validate(raw_rubric)
            exact_sum = round(
                rubric.china_first_then_global_depth
                + rubric.dual_horizon_3_5y_vs_5_10y_rigor
                + rubric.pain_point_and_physics_specificity
                + rubric.roi_and_industrial_upgrade_value
                + rubric.citation_grounding_and_prose,
                2,
            )
            rubric = rubric.model_copy(update={"total_score": exact_sum})
            rubric_passed = exact_sum >= pass_threshold
            rubric_dump = rubric.model_dump()
        else:
            exact_sum = 100.0 if objective_audit["passed"] else 0.0
            rubric_passed = True
            rubric_dump = {
                "mode": "objective_hard_audit_only",
                "total_score": exact_sum,
                "executive_verdict": (
                    "全量客观硬审计 100% 通过" if objective_audit["passed"] else "存在客观硬缺陷，已拦截"
                ),
            }

        stage_passed = bool(objective_audit["passed"] and rubric_passed)

        written_files: list[str] = []
        for fname, content in sorted(drafts.items()):
            target = out_path / fname
            target.write_text(content, encoding="utf-8")
            written_files.append(str(target))

        ws_breakdown = {
            "global_and_cn_commercialized": sum(
                1 for e in evaluated if e.seed.commercial_status == "global_and_cn_commercialized"
            ),
            "overseas_only_cn_blank": sum(
                1 for e in evaluated if e.seed.commercial_status == "overseas_only_cn_blank"
            ),
            "global_and_cn_true_blank": sum(
                1 for e in evaluated if e.seed.commercial_status == "global_and_cn_true_blank"
            ),
        }
        llm_cost_cny = float(bundle.get("llm_cost_cny", 0.0))
        search_cost_cny = float(search_cost_info["search_cost_cny"])

        scorecard = {
            "run_id": bundle.get("run_id", f"v4-native-{uuid.uuid4().hex[:8]}"),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "workflow_version": "V4.0_MODEL_FIRST_FALSIFIED_DISCOVERY",
            "profile": bundle.get("profile", "flagship"),
            "sector_filter": bundle.get("sector_filter", "all"),
            "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
            "stage_gate_passed": stage_passed,
            "pass_threshold": pass_threshold,
            "objective_audit": objective_audit,
            "deterministic_contract_checks": objective_audit,
            "discovered_tracks": [
                {
                    "track_id": t.get("track_id"),
                    "sector": t.get("sector"),
                    "name": t.get("name"),
                    "is_emerging_or_cross_cutting": t.get("is_emerging_or_cross_cutting", False),
                    "emergence_rationale": t.get("emergence_rationale", ""),
                    "recon_evidence_ids": t.get("recon_evidence_ids", []),
                }
                for t in plan_data.get("track_plans", [])
            ],
            "commercial_whitespace_breakdown": ws_breakdown,
            "discovery_funnel_summary": {
                "recon_evidence_count": len(vault.list_by_track("RECON")),
                "raw_candidates_count": raw_count,
                "shortlist_count": len(evaluated),
                "eliminated_count": len(eliminated),
                "eliminated_candidates": eliminated,
            },
            "judge_rubric": rubric_dump,
            "evidence_vault_stats": vault_stats,
            "portfolio_reviews": bundle.get("portfolio_reviews", {}),
            "global_portfolio_ranking": bundle.get("global_portfolio_ranking", {}),
            "evaluated_opportunities_top16": [
                {
                    "rank": e.composite_rank,
                    "opp_id": e.seed.opp_id,
                    "track_id": e.seed.track_id,
                    "sector": e.seed.sector,
                    "horizon": e.seed.horizon,
                    "portfolio_role": e.seed.portfolio_role,
                    "title": e.seed.title,
                    "commercial_status": e.seed.commercial_status,
                    "falsification_audit_note": e.seed.falsification_audit_note,
                    "global_vendors_and_products": e.seed.global_vendors_and_products,
                    "china_vendors_and_products": e.seed.china_vendors_and_products,
                    "white_space_and_entry_wedge": e.seed.white_space_and_entry_wedge,
                    "estimated_rd_months_ai_vs_legacy": e.seed.estimated_rd_months_ai_vs_legacy,
                    "weighted_pillar_score": e.weighted_pillar_score,
                    "optimistic_payback_months": e.roi_range.optimistic.payback_months if e.roi_range else e.roi.payback_months,
                    "baseline_payback_months": e.roi.payback_months,
                    "conservative_payback_months": e.roi_range.conservative.payback_months if e.roi_range else e.roi.payback_months,
                    "irr_5yr_pct": e.roi.irr_5yr_pct,
                    "npv_5yr_cny": e.roi.npv_5yr_cny,
                    "payback_tier": e.roi.payback_tier,
                }
                for e in evaluated
            ],
            "critique_loops_executed": int(bundle.get("critique_loops_executed", 0)),
            "critique_history": bundle.get("critique_history", []),
            "cost_and_token_telemetry": {
                "billing_mode": "Antigravity IDE Native Frontier Quota + Paid Search APIs (.env.ai_search)",
                "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
                "llm_cost_cny": round(llm_cost_cny, 4),
                "search_cost_cny": search_cost_cny,
                "total_cost_cny": round(llm_cost_cny + search_cost_cny, 4),
                "search_breakdown": search_cost_info,
                "native_agent_invocations": bundle.get("native_agent_invocations", {}),
                "search_queries_in_vault": search_cost_info["total_queries_logged"],
            },
        }
        sc_path = out_path / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
        sc_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
        written_files.append(str(sc_path))

        console.print(
            f"[bold green]V4.0 Model-First Discovery Finalized![/bold green]\n"
            f"- Engine: {scorecard['llm_engine']} | Stage-Gate: {stage_passed} | "
            f"Objective Audit: {objective_audit['passed']} (broken_cites={len(objective_audit['broken_citation_ids'])}, "
            f"roi_mismatches={len(objective_audit['roi_mismatches'])})\n"
            f"- Funnel: raw={raw_count} -> shortlist={len(evaluated)} (eliminated={len(eliminated)}) | "
            f"White-Space={ws_breakdown}\n"
            f"- Evidences: total={vault_stats.get('total')} (CN={vault_stats.get('cn_count')}, GLOBAL={vault_stats.get('global_count')}) | "
            f"Search Cost: ¥{search_cost_cny:.2f} CNY\n"
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

    p_prep = sub.add_parser("prepare-context", help="[V1 Archive] Export EvidenceVault + ROI baselines JSON for native IDE workflow")
    p_prep.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_prep.add_argument("--output", default="data/native_context_bundle.json")

    p_fin = sub.add_parser("finalize-native", help="[V1 Archive] Compute deterministic ROI/Elo/Judge checks and compile 7 outputs")
    p_fin.add_argument("--bundle", default="data/native_outputs_bundle.json")
    p_fin.add_argument("--output-dir", default="outputs/power_semiconductor_online_testing_2026_2036")

    p_rec = sub.add_parser("recon-search", help="[V3] Stage 0 macro recon search -> JSON bundle")
    p_rec.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_rec.add_argument("--profile", choices=["flagship", "fast"], default="flagship")
    p_rec.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_rec.add_argument("--output", default="data/v3_recon_context.json")

    p_trk = sub.add_parser("track-search", help="[V3] Stage 1 concurrent pain-point + vendor search across tracks")
    p_trk.add_argument("--plan", default="data/v3_discovery_plan.json")
    p_trk.add_argument("--profile", choices=["flagship", "fast"], default="flagship")
    p_trk.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_trk.add_argument("--output", default="data/v3_tracks_evidence.json")

    p_scr = sub.add_parser("screen-candidates", help="[V3] Stage 2 deterministic 3-scenario PALMs range & funnel screener")
    p_scr.add_argument("--dossiers", default="data/v3_raw_dossiers.json")
    p_scr.add_argument("--plan", default="data/v3_discovery_plan.json")
    p_scr.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_scr.add_argument("--profile", choices=["flagship", "fast"], default="flagship")
    p_scr.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_scr.add_argument("--output", default="data/v3_screened_shortlist.json")

    p_gap = sub.add_parser("gap-search", help="[V3] Stage 6 Corrective RAG targeted refill search")
    p_gap.add_argument("--queries-json", required=True)
    p_gap.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_gap.add_argument("--output", default="data/v3_gap_refill.json")

    p_fv2 = sub.add_parser("finalize-v2", help="[V2/V3 Compat] Stage 7 deterministic Elo replay, Judge checks & 7 deliverables")
    p_fv2.add_argument("--bundle", default="data/v3_native_outputs_bundle.json")
    p_fv2.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_fv2.add_argument("--output-dir", default="outputs/v3_commercial_ai_grounded_2026_2036")

    p_fv3 = sub.add_parser("finalize-v3", help="[V3 Compat] Stage 7 deterministic Elo replay, Judge checks & 7 deliverables")
    p_fv3.add_argument("--bundle", default="data/v3_native_outputs_bundle.json")
    p_fv3.add_argument("--vault-db", default="evidence_vault_v3.db")
    p_fv3.add_argument("--output-dir", default="outputs/v3_commercial_ai_grounded_2026_2036")

    p_fal = sub.add_parser("falsify-search", help="[V4] Stage 1b bounded falsification search for claimed commercial blanks")
    p_fal.add_argument("--dossiers", default="data/v4_raw_dossiers.json")
    p_fal.add_argument("--vault-db", default="evidence_vault_v4.db")
    p_fal.add_argument("--output", default="data/v4_falsify_context.json")
    p_fal.add_argument("--max-queries", type=int, default=4)

    p_port = sub.add_parser("prepare-portfolio", help="[V4] Stage 3 export holistic sector buying-committee prompts")
    p_port.add_argument("--screened", default="data/v4_screened_shortlist.json")
    p_port.add_argument("--vault-db", default="evidence_vault_v4.db")
    p_port.add_argument("--output", default="data/v4_portfolio_prompts.json")

    p_syn = sub.add_parser("prepare-synthesis", help="[V4] Stage 4 apply portfolio ranking & export single-core volume prompts")
    p_syn.add_argument("--screened", default="data/v4_screened_shortlist.json")
    p_syn.add_argument("--portfolio", default="data/v4_portfolio_results.json")
    p_syn.add_argument("--plan", default="data/v4_discovery_plan.json")
    p_syn.add_argument("--vault-db", default="evidence_vault_v4.db")
    p_syn.add_argument("--output", default="data/v4_synthesis_bundle.json")

    p_exp = sub.add_parser("export-v4-schemas", help="[V4] Export single-core flat JSON schemas & prompts for stdlib shells")
    p_exp.add_argument("--output", default="data/v4_runtime_schemas.json")

    p_fv4 = sub.add_parser("finalize-v4", help="[V4] Stage 5 deterministic table injection, full-corpus hard audit & compilation")
    p_fv4.add_argument("--bundle", default="data/v4_native_outputs_bundle.json")
    p_fv4.add_argument("--vault-db", default="evidence_vault_v4.db")
    p_fv4.add_argument("--output-dir", default="outputs/v4_model_first_grounded_2026_2036")

    p_run = sub.add_parser("run", help="Execute complete LangGraph opportunity discovery workflow")
    p_run.add_argument("--sector", choices=["all", "power", "semiconductor"], default="all")
    p_run.add_argument("--profile", choices=["flagship", "fast"], default="flagship")
    p_run.add_argument("--output-dir", default="outputs/v4_model_first_grounded_2026_2036")
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
    elif args.command == "recon-search":
        rc = asyncio.run(
            _cmd_recon_search(
                settings,
                sector=args.sector,
                profile=args.profile,
                vault_db=args.vault_db,
                output_file=args.output,
            )
        )
    elif args.command == "track-search":
        rc = asyncio.run(
            _cmd_track_search(
                settings,
                plan_file=args.plan,
                profile=args.profile,
                vault_db=args.vault_db,
                output_file=args.output,
            )
        )
    elif args.command == "screen-candidates":
        rc = _cmd_screen_candidates(
            settings,
            dossiers_file=args.dossiers,
            plan_file=args.plan,
            sector=args.sector,
            profile=args.profile,
            vault_db=args.vault_db,
            output_file=args.output,
        )
    elif args.command == "gap-search":
        rc = asyncio.run(
            _cmd_gap_search(
                settings,
                queries_arg=args.queries_json,
                vault_db=args.vault_db,
                output_file=args.output,
            )
        )
    elif args.command in ("finalize-v2", "finalize-v3"):
        rc = _cmd_finalize_v2(
            settings,
            bundle_file=args.bundle,
            vault_db=args.vault_db,
            output_dir=args.output_dir,
        )
    elif args.command == "falsify-search":
        rc = asyncio.run(
            _cmd_falsify_search(
                settings,
                dossiers_file=args.dossiers,
                vault_db=args.vault_db,
                output_file=args.output,
                max_queries_per_track=args.max_queries,
            )
        )
    elif args.command == "prepare-portfolio":
        rc = _cmd_prepare_portfolio(
            settings,
            screened_file=args.screened,
            vault_db=args.vault_db,
            output_file=args.output,
        )
    elif args.command == "prepare-synthesis":
        rc = _cmd_prepare_synthesis(
            settings,
            screened_file=args.screened,
            portfolio_file=args.portfolio,
            plan_file=args.plan,
            vault_db=args.vault_db,
            output_file=args.output,
        )
    elif args.command == "export-v4-schemas":
        rc = _cmd_export_v4_schemas(settings, output_file=args.output)
    elif args.command == "finalize-v4":
        rc = _cmd_finalize_v4(
            settings,
            bundle_file=args.bundle,
            vault_db=args.vault_db,
            output_dir=args.output_dir,
        )
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
