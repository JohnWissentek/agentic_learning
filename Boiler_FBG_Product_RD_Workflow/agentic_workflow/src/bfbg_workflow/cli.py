"""CLI entrypoint (`bfbg-workflow`) supporting Standalone DashScope & Antigravity Native Hybrid Run."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from rich.console import Console

from bfbg_workflow.config import (
    CostLedger,
    DashScopeLLMGateway,
    WorkflowSettings,
    assert_no_secrets_leaked,
)
from bfbg_workflow.graph import build_boiler_fbg_graph
from bfbg_workflow.nodes.critic_and_judge import export_all_deliverables
from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.nodes.ipd_and_storm import compute_elo_standings
from bfbg_workflow.nodes.planner import run_macro_recon
from bfbg_workflow.nodes.researcher import execute_all_tracks_and_pdfs
from bfbg_workflow.schemas import ProductDiscoveryPlan
from bfbg_workflow.tools.engineering_and_finance_calc import run_all_deterministic_calcs
from bfbg_workflow.tools.evidence_vault import (
    EvidenceVault,
    deterministic_contract_checks,
    format_records_compact,
)
from bfbg_workflow.tools.prior_corpus_loader import ingest_prior_research_corpus
from bfbg_workflow.tools.search_router import DualEngineSearchRouter

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
            track_id="VERIFY", geo_scope="CN", query="燃煤电厂 锅炉 水冷壁 光纤光栅 测温", num_results=2
        )
        gl_hits = await deps.search_router.search_track(
            track_id="VERIFY", geo_scope="GLOBAL", query="Ibsen I-MON 512 FBG interrogator", num_results=2
        )
        prior_files = (
            list(settings.prior_research_dir.rglob("*.md"))
            if settings.prior_research_dir.exists()
            else []
        )
        prior_pdfs = (
            list(settings.prior_research_dir.rglob("*.pdf"))
            if settings.prior_research_dir.exists()
            else []
        )
        drawio_ok = Path("/Applications/draw.io.app/Contents/MacOS/draw.io").exists()
        console.print(
            f"[bold green]BoilerSense-AI Environment Verification[/bold green]\n"
            f"- Prior research corpus: {len(prior_files)} markdown docs, {len(prior_pdfs)} baseline PDFs\n"
            f"- Metaso CN probe hits: {len(cn_hits)} | Serper GLOBAL probe hits: {len(gl_hits)}\n"
            f"- Draw.io CLI binary available: {drawio_ok}\n"
            f"- Secrets configured (masked check): metaso={bool(settings.metaso_api_key)}, serper={bool(settings.serper_api_key)}, dashscope={bool(settings.dashscope_api_key)}"
        )
        return 0 if (cn_hits and gl_hits and len(prior_files) >= 10) else 1
    finally:
        deps.vault.close()


async def _cmd_prepare_evidence(
    settings: WorkflowSettings, *, profile: str, vault_db: str, output_file: str
) -> int:
    deps = _make_deps(settings, vault_db)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prior_recs = ingest_prior_research_corpus(settings.prior_research_dir, deps.vault)
        recon_recs, q_log = await run_macro_recon(deps, profile=profile)
        stats = deps.vault.stats()
        payload = {
            "contract": settings.contract,
            "profile": profile,
            "vault_db": str(deps.vault.db_path),
            "vault_stats": stats,
            "query_log": q_log,
            "prior_count": len(prior_recs),
            "recon_count": len(recon_recs),
            "prior_context_text": format_records_compact(prior_recs, limit=22),
            "recon_context_text": format_records_compact(recon_recs, limit=24),
        }
        txt = json.dumps(payload, ensure_ascii=False, indent=2)
        assert_no_secrets_leaked(txt, settings)
        out_path.write_text(txt, encoding="utf-8")
        console.print(f"[green]Stage 0 recon saved:[/green] stats={stats}, file={out_path}")
        return 0
    finally:
        deps.vault.close()


async def _cmd_execute_tracks_and_pdfs(
    settings: WorkflowSettings,
    *,
    plan_file: str,
    profile: str,
    vault_db: str,
    output_dir: str,
    output_file: str,
) -> int:
    p_path = _resolve_path(settings, plan_file)
    out_dir = _resolve_path(settings, output_dir)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_plan = json.loads(p_path.read_text(encoding="utf-8"))
    if "track_plans" not in raw_plan and "tracks" in raw_plan:
        raw_plan["track_plans"] = raw_plan["tracks"]
    plan = ProductDiscoveryPlan.model_validate(raw_plan)

    deps = _make_deps(settings, vault_db)
    try:
        track_map, assets = await execute_all_tracks_and_pdfs(
            deps, plan, output_dir=out_dir, profile=profile
        )
        base_recs = deps.vault.list_all(geo_scope="BASE")
        cn_recs = deps.vault.list_all(geo_scope="CN")
        gl_recs = deps.vault.list_all(geo_scope="GLOBAL")
        pdf_recs = deps.vault.list_all(geo_scope="PDF")

        track_contexts = {
            tid: format_records_compact(recs, limit=24) for tid, recs in track_map.items()
        }
        payload = {
            "vault_stats": deps.vault.stats(),
            "all_valid_ev_ids": sorted(deps.vault.all_ev_ids()),
            "track_contexts": track_contexts,
            "datasheet_assets": [a.model_dump() for a in assets],
            "context_base": format_records_compact(base_recs, limit=20),
            "context_cn": format_records_compact(cn_recs, limit=35),
            "context_global": format_records_compact(gl_recs, limit=28),
            "context_pdf": format_records_compact(pdf_recs, limit=25),
            "search_telemetry": deps.ledger.summary(),
        }
        txt = json.dumps(payload, ensure_ascii=False, indent=2)
        assert_no_secrets_leaked(txt, settings)
        out_path.write_text(txt, encoding="utf-8")
        console.print(
            f"[green]Stage 1 tracks & PDFs saved:[/green] stats={deps.vault.stats()}, "
            f"verified_pdfs={len(assets)}, file={out_path}"
        )
        return 0
    finally:
        deps.vault.close()


def _cmd_run_calcs(settings: WorkflowSettings, *, output_file: str) -> int:
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = run_all_deterministic_calcs(settings.catalog)
    txt = json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2)
    assert_no_secrets_leaked(txt, settings)
    out_path.write_text(txt, encoding="utf-8")
    console.print(f"[green]Stage 2 deterministic calculations saved:[/green] {out_path}")
    return 0


async def _cmd_gap_search(
    settings: WorkflowSettings, *, queries_json: str, vault_db: str, output_file: str
) -> int:
    q_path = _resolve_path(settings, queries_json)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    queries = json.loads(q_path.read_text(encoding="utf-8"))
    deps = _make_deps(settings, vault_db)
    try:
        recs = []
        for item in queries:
            hits = await deps.search_router.search_track(
                track_id="CRAG_GAP",
                geo_scope=item.get("geo_scope", "CN"),
                query=item.get("query", ""),
                num_results=5,
            )
            for h in hits:
                r = deps.vault.upsert_hit(track_id="CRAG_GAP", hit=h)
                if r:
                    recs.append(r)
        payload = {
            "new_count": len(recs),
            "all_valid_ev_ids": sorted(deps.vault.all_ev_ids()),
            "formatted_context": format_records_compact(recs, limit=18),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]CRAG gap search complete:[/green] new={len(recs)}")
        return 0
    finally:
        deps.vault.close()


def _cmd_finalize(
    settings: WorkflowSettings, *, bundle_file: str, vault_db: str, output_dir: str
) -> int:
    b_path = _resolve_path(settings, bundle_file)
    out_dir = _resolve_path(settings, output_dir)
    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    deps = _make_deps(settings, vault_db)
    try:
        elo_ranking = compute_elo_standings(
            [a["arch_id"] for a in settings.catalog["candidate_architectures"]],
            bundle.get("elo_matches", []),
        )
        extra_tel = {
            "elo_ranking": elo_ranking,
            "elo_matches": bundle.get("elo_matches", []),
            "critique_loops_executed": bundle.get("critique_loops_executed", 0),
            "critique_history": bundle.get("critique_history", []),
            "native_agent_invocations": bundle.get("native_agent_invocations", {}),
        }
        scorecard = export_all_deliverables(
            deps=deps,
            output_dir=out_dir,
            volumes=bundle.get("volumes", {}),
            judge_rubric=bundle.get("judge_rubric", {}),
            run_id=bundle.get("run_id", f"bfbg-{uuid.uuid4().hex[:8]}"),
            profile=bundle.get("profile", "flagship"),
            llm_engine=bundle.get("llm_engine", "antigravity_native"),
            extra_telemetry=extra_tel,
        )
        console.print(
            f"[bold green]Final deliverables compiled:[/bold green] "
            f"score={scorecard['stage_gate_total_score']}, "
            f"invalid_cites={scorecard['programmatic_checks']['invalid_citations_count']}, "
            f"broken_pdfs={scorecard['programmatic_checks']['broken_pdf_links_count']}, "
            f"dir={out_dir}"
        )
        return 0
    finally:
        deps.vault.close()


def _cmd_check_deliverables(settings: WorkflowSettings, *, output_dir: str, vault_db: str) -> int:
    out_dir = _resolve_path(settings, output_dir)
    deps = _make_deps(settings, vault_db)
    try:
        vols: dict[str, str] = {}
        for fname in settings.contract.get("required_output_volumes", []):
            p = out_dir / fname
            if p.exists():
                vols[fname] = p.read_text(encoding="utf-8")
        checks = deterministic_contract_checks(
            vault=deps.vault, volumes=vols, output_dir=out_dir, contract=settings.contract
        )
        console.print(json.dumps(checks, ensure_ascii=False, indent=2))
        ok = (
            checks["invalid_citations_count"] == 0
            and checks["broken_pdf_links_count"] == 0
            and not checks["missing_required_volumes"]
        )
        return 0 if ok else 1
    finally:
        deps.vault.close()


async def _cmd_run_full(
    settings: WorkflowSettings, *, profile: str, output_dir: str, vault_db: str
) -> int:
    deps = _make_deps(settings, vault_db)
    try:
        graph = build_boiler_fbg_graph(deps)
        run_id = f"bfbg-{uuid.uuid4().hex[:8]}"
        final_state = await graph.ainvoke(
            {
                "run_id": run_id,
                "profile": profile,
                "output_dir": output_dir,
                "vault_db": vault_db,
            },
            config={"configurable": {"thread_id": run_id}},
        )
        manifest = final_state.get("final_manifest", {})
        console.print(
            f"[bold green]Standalone LangGraph run finished:[/bold green] "
            f"score={manifest.get('stage_gate_total_score')}"
        )
        return 0
    finally:
        deps.vault.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="bfbg-workflow")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verify-env")

    p_prep = sub.add_parser("prepare-evidence")
    p_prep.add_argument("--profile", default="flagship")
    p_prep.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")
    p_prep.add_argument("--output-file", default="data/stage0_recon_context.json")

    p_tr = sub.add_parser("execute-tracks-and-pdfs")
    p_tr.add_argument("--plan-file", required=True)
    p_tr.add_argument("--profile", default="flagship")
    p_tr.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")
    p_tr.add_argument("--output-dir", default="../output")
    p_tr.add_argument("--output-file", default="data/stage1_tracks_and_pdfs.json")

    p_calc = sub.add_parser("run-calcs")
    p_calc.add_argument("--output-file", default="data/stage2_deterministic_calcs.json")

    p_gap = sub.add_parser("gap-search")
    p_gap.add_argument("--queries-json", required=True)
    p_gap.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")
    p_gap.add_argument("--output-file", default="data/stage6_gap_evidence.json")

    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--bundle-file", required=True)
    p_fin.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")
    p_fin.add_argument("--output-dir", default="../output")

    p_chk = sub.add_parser("check-deliverables")
    p_chk.add_argument("--output-dir", default="../output")
    p_chk.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")

    p_run = sub.add_parser("run")
    p_run.add_argument("--profile", default="flagship")
    p_run.add_argument("--output-dir", default="../output")
    p_run.add_argument("--vault-db", default="data/bfbg_evidence_vault.db")

    args = parser.parse_args()
    settings = WorkflowSettings.load()

    if args.cmd == "verify-env":
        raise SystemExit(asyncio.run(_cmd_verify_env(settings)))
    if args.cmd == "prepare-evidence":
        raise SystemExit(
            asyncio.run(
                _cmd_prepare_evidence(
                    settings, profile=args.profile, vault_db=args.vault_db, output_file=args.output_file
                )
            )
        )
    if args.cmd == "execute-tracks-and-pdfs":
        raise SystemExit(
            asyncio.run(
                _cmd_execute_tracks_and_pdfs(
                    settings,
                    plan_file=args.plan_file,
                    profile=args.profile,
                    vault_db=args.vault_db,
                    output_dir=args.output_dir,
                    output_file=args.output_file,
                )
            )
        )
    if args.cmd == "run-calcs":
        raise SystemExit(_cmd_run_calcs(settings, output_file=args.output_file))
    if args.cmd == "gap-search":
        raise SystemExit(
            asyncio.run(
                _cmd_gap_search(
                    settings,
                    queries_json=args.queries_json,
                    vault_db=args.vault_db,
                    output_file=args.output_file,
                )
            )
        )
    if args.cmd == "finalize":
        raise SystemExit(
            _cmd_finalize(
                settings, bundle_file=args.bundle_file, vault_db=args.vault_db, output_dir=args.output_dir
            )
        )
    if args.cmd == "check-deliverables":
        raise SystemExit(
            _cmd_check_deliverables(settings, output_dir=args.output_dir, vault_db=args.vault_db)
        )
    if args.cmd == "run":
        raise SystemExit(
            asyncio.run(
                _cmd_run_full(
                    settings, profile=args.profile, output_dir=args.output_dir, vault_db=args.vault_db
                )
            )
        )


if __name__ == "__main__":
    main()
