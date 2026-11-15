"""CLI entrypoint (`vf-ccus-research`) supporting Standalone DashScope & Native Hybrid Orchestration."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from vf_ccus_workflow.config import (
    CostLedger,
    DashScopeLLMGateway,
    WorkflowSettings,
    assert_no_secrets_leaked,
    unwrap_json_container_strings,
)
from vf_ccus_workflow.graph import build_vf_ccus_graph
from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact, ingest_siggi_corpus, run_macro_recon
from vf_ccus_workflow.nodes.researcher import clean_track_dossier, collect_queries_for_track
from vf_ccus_workflow.nodes.storm_and_rank import aggregate_catalogs_and_screen, update_elo
from vf_ccus_workflow.schemas import (
    ChinaMarketSizingSummary,
    DiscoveryPlan,
    EvaluatedWedge,
    JudgeRubricScores,
    TrackDossier,
    WedgeStormMemo,
)
from vf_ccus_workflow.tools.evidence_vault import (
    EvidenceVault,
    deterministic_contract_checks,
    render_evidence_index,
)
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    format_eliminated_table,
    format_market_sizing_table,
    format_roi_table,
)
from vf_ccus_workflow.tools.search_router import DualEngineSearchRouter

console = Console()


def _resolve_path(settings: WorkflowSettings, target: str) -> Path:
    p = Path(target)
    return p if p.is_absolute() else (settings.root_dir / p).resolve()


def _make_deps(settings: WorkflowSettings, vault_db: str | None = None) -> RuntimeDeps:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    vault_path = settings.resolve_vault_path(vault_db)
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = CostLedger()
    vault = EvidenceVault(vault_path)
    router = DualEngineSearchRouter(settings, ledger)
    llm = DashScopeLLMGateway(settings, ledger)
    return RuntimeDeps(
        settings=settings,
        ledger=ledger,
        vault=vault,
        search_router=router,
        llm=llm,
        semaphore=asyncio.Semaphore(settings.concurrency),
    )


async def _cmd_verify_env(settings: WorkflowSettings) -> int:
    deps = _make_deps(settings)
    try:
        cn_hits = await deps.search_router.search_track(
            track_id="VERIFY", geo_scope="CN", query="中国 CCUS 二氧化碳 捕集 管道", num_results=2
        )
        gl_hits = await deps.search_router.search_track(
            track_id="VERIFY", geo_scope="GLOBAL", query="Northern Lights CO2 purity analyzer", num_results=2
        )
        model_checks: dict[str, str] = {}
        for tier in ("fast", "producer", "critic"):
            out = await deps.llm.complete_text(
                tier=tier,
                node=f"verify_{tier}",
                system_prompt="Reply strictly with OK.",
                user_prompt="Ping",
                max_tokens=16,
            )
            model_checks[tier] = "PASS" if out else "FAIL"

        siggi_files = (
            list(settings.siggi_corpus_dir.iterdir()) if settings.siggi_corpus_dir.exists() else []
        )
        console.print(
            f"[bold green]Environment Verification Complete[/bold green]\n"
            f"- Siggi corpus files: {len(siggi_files)}\n"
            f"- Metaso CN probe hits: {len(cn_hits)} | Serper GLOBAL probe hits: {len(gl_hits)}\n"
            f"- DashScope Models: {model_checks}"
        )
        return 0 if (cn_hits and gl_hits and len(siggi_files) >= 5) else 1
    finally:
        deps.vault.close()


def _cmd_ingest_siggi(settings: WorkflowSettings, *, vault_db: str) -> int:
    deps = _make_deps(settings, vault_db)
    try:
        recs = ingest_siggi_corpus(deps)
        stats = deps.vault.stats()
        console.print(
            f"[green]Siggi MCP corpus ingested:[/green] new_or_existing={len(recs)}, vault_stats={stats}"
        )
        return 0 if len(recs) > 0 else 1
    finally:
        deps.vault.close()


async def _cmd_recon_search(
    settings: WorkflowSettings, *, profile: str, vault_db: str, output_file: str
) -> int:
    deps = _make_deps(settings, vault_db)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        siggi_recs = ingest_siggi_corpus(deps)
        recon_recs, q_log = await run_macro_recon(deps, profile=profile)
        stats = deps.vault.stats()
        payload = {
            "contract": settings.contract,
            "discovery_scope": settings.discovery_scope,
            "profile": profile,
            "vault_db": str(deps.vault.db_path),
            "query_log": q_log,
            "vault_stats": stats,
            "siggi_count": len(siggi_recs),
            "recon_count": len(recon_recs),
            "siggi_context_text": format_records_compact(siggi_recs, limit=28),
            "recon_context_text": format_records_compact(recon_recs, limit=28),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Stage 0 recon saved:[/green] stats={stats}, file={out_path}")
        return 0
    finally:
        deps.vault.close()


async def _cmd_track_search(
    settings: WorkflowSettings, *, plan_file: str, profile: str, vault_db: str, output_file: str
) -> int:
    p_path = _resolve_path(settings, plan_file)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_plan = json.loads(p_path.read_text(encoding="utf-8"))
    if "track_plans" not in raw_plan and "tracks" in raw_plan:
        raw_plan["track_plans"] = raw_plan["tracks"]
    plan = DiscoveryPlan.model_validate(raw_plan)

    deps = _make_deps(settings, vault_db)
    try:
        siggi_all = deps.vault.list_by_scope("SIGGI")
        recon_all = deps.vault.list_by_track("RECON")
        num_res = 6 if profile == "flagship" else 3
        max_ft = 2 if profile == "flagship" else 1

        async def _one(tp):
            recs, qh = await collect_queries_for_track(
                deps=deps, track=tp, num_results=num_res, max_fulltext=max_ft
            )
            combined = recs + siggi_all[:10] + recon_all[:8]
            return {
                "track": tp.model_dump(),
                "query_hashes": qh,
                "valid_ev_ids": sorted({r.ev_id for r in combined}),
                "evidence_context": format_records_compact(combined, limit=28),
            }

        tracks_out = list(await asyncio.gather(*[_one(tp) for tp in plan.track_plans]))
        stats = deps.vault.stats()
        payload = {
            "discovery_plan": plan.model_dump(),
            "vault_db": str(deps.vault.db_path),
            "vault_stats": stats,
            "all_valid_ev_ids": sorted(deps.vault.list_valid_ids()),
            "tracks": tracks_out,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Stage 1 track search saved:[/green] stats={stats}, file={out_path}")
        return 0
    finally:
        deps.vault.close()


def _cmd_screen_and_size(
    settings: WorkflowSettings, *, dossiers_file: str, profile: str, vault_db: str, output_file: str
) -> int:
    d_path = _resolve_path(settings, dossiers_file)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_payload = unwrap_json_container_strings(json.loads(d_path.read_text(encoding="utf-8")))
    raw_dossiers = raw_payload.get("dossiers", raw_payload) if isinstance(raw_payload, dict) else raw_payload

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        valid_ids = vault.list_valid_ids()
        cleaned: list[dict[str, Any]] = []
        for item in raw_dossiers:
            td = TrackDossier.model_validate(item)
            t_recs = vault.list_by_track(td.track_id) or vault.list_all()
            c_td = clean_track_dossier(
                raw_dossier=td,
                track_id=td.track_id,
                sector=td.sector,
                track_records=t_recs,
                valid_global_ids=valid_ids,
            )
            cleaned.append(c_td.model_dump())

        agg = aggregate_catalogs_and_screen(
            cleaned,
            discovery_scope=settings.discovery_scope,
            contract=settings.contract,
            profile=profile,
        )
        mkt_summary = ChinaMarketSizingSummary.model_validate(agg["market_sizing_summary"])
        all_records = vault.list_all()
        payload = {
            "shortlist": agg["shortlist"],
            "eliminated": agg["eliminated"],
            "projects": agg["projects"],
            "competitors": agg["competitors"],
            "market_sizing_summary": agg["market_sizing_summary"],
            "market_sizing_md": format_market_sizing_table(mkt_summary),
            "roi_table_md": format_roi_table(agg["shortlist"]),
            "eliminated_table_md": format_eliminated_table(agg["eliminated"]),
            "evidence_context_siggi": format_records_compact([r for r in all_records if r.geo_scope == "SIGGI"], limit=22),
            "evidence_context_cn": format_records_compact([r for r in all_records if r.geo_scope == "CN"], limit=26),
            "evidence_context_global": format_records_compact([r for r in all_records if r.geo_scope == "GLOBAL"], limit=18),
            "vault_stats": vault.stats(),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 2 sizing & screening complete:[/green] shortlist={len(agg['shortlist'])}, "
            f"eliminated={len(agg['eliminated'])}, projects={len(agg['projects'])}, comps={len(agg['competitors'])}"
        )
        return 0
    finally:
        vault.close()


async def _cmd_gap_search(
    settings: WorkflowSettings, *, queries_arg: str, vault_db: str, output_file: str
) -> int:
    q_cand = _resolve_path(settings, queries_arg)
    raw_q = json.loads(q_cand.read_text(encoding="utf-8")) if q_cand.exists() else json.loads(queries_arg)
    if isinstance(raw_q, dict):
        raw_q = raw_q.get("gap_queries", [])
    gap_queries = list(raw_q)[:4]

    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    deps = _make_deps(settings, vault_db)
    added = []
    try:
        for item in gap_queries:
            q = str(item.get("query", "")).strip()
            if not q:
                continue
            geo = "GLOBAL" if str(item.get("geo_scope", "")).upper() == "GLOBAL" else "CN"
            tid = str(item.get("track_id") or "CRAG_GAP")
            hits = await deps.search_router.search_track(
                track_id=tid,
                geo_scope=geo,  # type: ignore[arg-type]
                query=q,
                mode="webpage" if geo == "CN" else "search",
                num_results=5,
            )
            deps.vault.log_query(
                track_id=tid,
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,  # type: ignore[arg-type]
                query=q,
                hits_count=len(hits),
            )
            for h in hits:
                rec = deps.vault.upsert_hit(track_id=tid, hit=h)
                if rec is not None:
                    added.append(rec)

        payload = {
            "added_count": len(added),
            "vault_stats": deps.vault.stats(),
            "all_valid_ev_ids": sorted(deps.vault.list_valid_ids()),
            "formatted_context": format_records_compact(added, limit=20) if added else "",
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Stage 6 CRAG refill complete:[/green] added={len(added)}")
        return 0
    finally:
        deps.vault.close()


def _cmd_finalize(
    settings: WorkflowSettings, *, bundle_file: str, vault_db: str, output_dir: str
) -> int:
    b_path = _resolve_path(settings, bundle_file)
    out_path = _resolve_path(settings, output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    vault_path = settings.resolve_vault_path(vault_db)
    vault = EvidenceVault(vault_path)
    try:
        all_records = vault.list_all()
        vault_stats = vault.stats()

        evaluated = [EvaluatedWedge.model_validate(e) for e in bundle.get("shortlist", [])]
        by_id = {e.seed.wedge_id: e for e in evaluated}
        storm_memos = bundle.get("storm_memos", {}) or {}
        for ev in evaluated:
            if ev.storm_memo is None and ev.seed.wedge_id in storm_memos:
                ev.storm_memo = WedgeStormMemo.model_validate(storm_memos[ev.seed.wedge_id])
            ev.elo_rating = round(1500.0 + (ev.weighted_pillar_score - 75.0) * 4.0, 2)

        elo_matches = list(bundle.get("elo_matches", []))
        for m in elo_matches:
            a_id, b_id, w_id = str(m.get("wedge_a_id", "")), str(m.get("wedge_b_id", "")), str(m.get("winner_id", ""))
            if a_id in by_id and b_id in by_id:
                oa, ob = by_id[a_id], by_id[b_id]
                a_won = w_id.strip() != b_id
                na, nb = update_elo(oa.elo_rating, ob.elo_rating, a_won)
                oa.elo_rating, ob.elo_rating = na, nb
                m["elo_a_after"], m["elo_b_after"] = na, nb

        if evaluated:
            elos = [e.elo_rating for e in evaluated]
            lo, hi = min(elos), max(elos)
            span = max(1.0, hi - lo)
            evaluated.sort(
                key=lambda e: 0.55 * e.weighted_pillar_score + 0.45 * (60.0 + ((e.elo_rating - lo) / span) * 38.0),
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
        drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
            all_records, db_label=f"data/{vault_path.name}"
        )

        eval_dicts = [e.model_dump() for e in evaluated]
        det_checks = deterministic_contract_checks(
            vault_stats=vault_stats,
            drafts=drafts,
            evaluated_wedges=eval_dicts,
            contract=settings.contract,
        )

        rubric = JudgeRubricScores.model_validate(bundle["judge_rubric"])
        exact_total = round(
            rubric.china_grounding_and_project_specificity
            + rubric.market_sizing_and_pain_point_rigor
            + rubric.competitive_battlecard_accuracy
            + rubric.dual_track_gtm_and_roi_actionability
            + rubric.evidence_traceability_and_prose,
            2,
        )
        threshold = float(settings.contract.get("quality_gates", {}).get("stage_gate_pass_score", 85.0))
        passed = bool(exact_total >= threshold and det_checks.get("all_5_volumes_non_empty"))
        rubric = rubric.model_copy(update={"total_score": exact_total, "pass_stage_gate": passed})

        written: list[str] = []
        for fname, content in sorted(drafts.items()):
            assert_no_secrets_leaked(content, settings)
            target = out_path / fname
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        search_queries_logged = int(vault._conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0])
        scorecard = {
            "run_id": bundle.get("run_id", f"native-{uuid.uuid4().hex[:8]}"),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "profile": bundle.get("profile", "flagship"),
            "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
            "stage_gate_passed": passed,
            "pass_threshold": threshold,
            "judge_rubric": rubric.model_dump(),
            "deterministic_contract_checks": det_checks,
            "evidence_vault_stats": vault_stats,
            "market_sizing_summary": bundle.get("market_sizing_summary", {}),
            "evaluated_wedges_top10": [
                {
                    "rank": e.composite_rank,
                    "wedge_id": e.seed.wedge_id,
                    "sector": e.seed.sector,
                    "delivery_track": e.seed.delivery_track,
                    "title": e.seed.title,
                    "payback_months": e.roi.payback_months,
                    "irr_5yr_pct": e.roi.irr_5yr_pct,
                    "npv_5yr_cny": e.roi.npv_5yr_cny,
                    "weighted_pillar_score": e.weighted_pillar_score,
                    "elo_rating": e.elo_rating,
                }
                for e in evaluated[:10]
            ],
            "eliminated_wedges": bundle.get("eliminated", []),
            "elo_tournament_matches": elo_matches,
            "critique_loops_executed": int(bundle.get("critique_loops_executed", 0)),
            "critique_history": bundle.get("critique_history", []),
            "cost_and_token_telemetry": {
                "billing_mode": "Antigravity IDE Native Reasoning + Verified Local/Web Search (.env.ai_search)",
                "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
                "native_agent_invocations": bundle.get("native_agent_invocations", {}),
                "search_queries_in_vault": search_queries_logged,
            },
        }
        sc_str = json.dumps(scorecard, ensure_ascii=False, indent=2)
        assert_no_secrets_leaked(sc_str, settings)
        sc_path = out_path / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
        sc_path.write_text(sc_str + "\n", encoding="utf-8")
        written.append(str(sc_path))

        console.print(
            f"[bold green]V&F CCUS Finalize Complete![/bold green]\n"
            f"- Stage-Gate Passed: {passed} ({exact_total}/100)\n"
            f"- Vault: {vault_stats}\n"
            f"- Deliverables ({len(written)} files) -> {out_path}"
        )
        return 0 if passed else 1
    finally:
        vault.close()


async def _cmd_run(settings: WorkflowSettings, *, profile: str, output_dir: str, vault_db: str) -> int:
    deps = _make_deps(settings, vault_db)
    try:
        graph = build_vf_ccus_graph(deps)
        run_id = f"vf-{uuid.uuid4().hex[:8]}"
        final_state = await graph.ainvoke(
            {
                "run_id": run_id,
                "profile": profile,
                "sector_filter": "all",
                "hitl_enabled": False,
                "output_dir": output_dir,
                "vault_db_path": str(deps.vault.db_path),
            },
            config={"configurable": {"thread_id": run_id}},
        )
        console.print(
            f"[bold green]Standalone LangGraph Complete![/bold green] "
            f"passed={final_state.get('stage_gate_passed')} | score={final_state.get('judge_rubric', {}).get('total_score')}/100"
        )
        return 0 if final_state.get("stage_gate_passed") else 1
    finally:
        deps.vault.close()


def _cmd_evaluate(settings: WorkflowSettings, *, scorecard_path: str) -> int:
    sc = _resolve_path(settings, scorecard_path)
    data = json.loads(sc.read_text(encoding="utf-8"))
    assert_no_secrets_leaked(sc.read_text(encoding="utf-8"), settings)
    console.print(json.dumps(data.get("judge_rubric", {}), ensure_ascii=False, indent=2))
    return 0 if data.get("stage_gate_passed") else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="vf-ccus-research")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verify-env")

    p_ing = sub.add_parser("ingest-siggi")
    p_ing.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")

    p_rec = sub.add_parser("recon-search")
    p_rec.add_argument("--profile", default="flagship")
    p_rec.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_rec.add_argument("--output-file", default="data/stage0_recon_bundle.json")

    p_trk = sub.add_parser("track-search")
    p_trk.add_argument("--plan-file", required=True)
    p_trk.add_argument("--profile", default="flagship")
    p_trk.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_trk.add_argument("--output-file", default="data/stage1_track_evidence.json")

    p_scr = sub.add_parser("screen-and-size")
    p_scr.add_argument("--dossiers-file", required=True)
    p_scr.add_argument("--profile", default="flagship")
    p_scr.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_scr.add_argument("--output-file", default="data/stage2_screened_pool.json")

    p_gap = sub.add_parser("gap-search")
    p_gap.add_argument("--queries-json", required=True)
    p_gap.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_gap.add_argument("--output-file", default="data/stage6_gap_evidence.json")

    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--bundle-file", required=True)
    p_fin.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_fin.add_argument("--output-dir", default="../research_outputs")

    p_run = sub.add_parser("run")
    p_run.add_argument("--profile", default="flagship", choices=["fast", "flagship"])
    p_run.add_argument("--sector", default="all")
    p_run.add_argument("--output-dir", default="../research_outputs")
    p_run.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument(
        "--scorecard",
        default="../research_outputs/06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json",
    )

    args = parser.parse_args()
    settings = WorkflowSettings.load()

    if args.cmd == "verify-env":
        return asyncio.run(_cmd_verify_env(settings))
    if args.cmd == "ingest-siggi":
        return _cmd_ingest_siggi(settings, vault_db=args.vault_db)
    if args.cmd == "recon-search":
        return asyncio.run(
            _cmd_recon_search(
                settings, profile=args.profile, vault_db=args.vault_db, output_file=args.output_file
            )
        )
    if args.cmd == "track-search":
        return asyncio.run(
            _cmd_track_search(
                settings,
                plan_file=args.plan_file,
                profile=args.profile,
                vault_db=args.vault_db,
                output_file=args.output_file,
            )
        )
    if args.cmd == "screen-and-size":
        return _cmd_screen_and_size(
            settings,
            dossiers_file=args.dossiers_file,
            profile=args.profile,
            vault_db=args.vault_db,
            output_file=args.output_file,
        )
    if args.cmd == "gap-search":
        return asyncio.run(
            _cmd_gap_search(
                settings, queries_arg=args.queries_json, vault_db=args.vault_db, output_file=args.output_file
            )
        )
    if args.cmd == "finalize":
        return _cmd_finalize(
            settings, bundle_file=args.bundle_file, vault_db=args.vault_db, output_dir=args.output_dir
        )
    if args.cmd == "run":
        return asyncio.run(
            _cmd_run(settings, profile=args.profile, output_dir=args.output_dir, vault_db=args.vault_db)
        )
    if args.cmd == "evaluate":
        return _cmd_evaluate(settings, scorecard_path=args.scorecard)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
