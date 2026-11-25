"""CLI entrypoint (`vf-ccus-research`) supporting v2.0 Antigravity Native Hybrid & Standalone LangGraph."""

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
from vf_ccus_workflow.nodes.researcher import (
    clean_competitive_dossier,
    clean_sector_dossier,
    collect_queries_for_track,
)
from vf_ccus_workflow.nodes.storm_and_rank import (
    aggregate_catalogs_and_screen,
    apply_portfolio_arbitration,
    build_executive_fact_sheet,
)
from vf_ccus_workflow.nodes.synthesizer import (
    VOLUME_SPECS,
    VOLUME_TRACK_ROUTING,
    collect_priority_ev_ids_for_volume,
)
from vf_ccus_workflow.schemas import (
    ChinaMarketSizingSummary,
    CompetitiveEcosystemDossier,
    DiscoveryPlan,
    PortfolioArbitrationOutput,
    SectorDossier,
    SingleVolumeCriticOutput,
    VolumeMarkdownOutput,
    export_flat_json_schema,
)
from vf_ccus_workflow.tools.evidence_vault import (
    EvidenceVault,
    render_evidence_index,
    run_deterministic_full_audit,
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


def _cmd_export_schemas(settings: WorkflowSettings, *, output_file: str) -> int:
    """Export all single-source flat JSON Schemas (zero $ref/$defs) from schemas.py."""
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema_version": "2.0",
        "DiscoveryPlan": export_flat_json_schema(DiscoveryPlan),
        "SectorDossier": export_flat_json_schema(SectorDossier),
        "CompetitiveEcosystemDossier": export_flat_json_schema(CompetitiveEcosystemDossier),
        "PortfolioArbitrationOutput": export_flat_json_schema(PortfolioArbitrationOutput),
        "VolumeMarkdownOutput": export_flat_json_schema(VolumeMarkdownOutput),
        "SingleVolumeCriticOutput": export_flat_json_schema(SingleVolumeCriticOutput),
    }
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exported {len(bundle) - 1} single-source flat JSON schemas -> {out_path}[/green]")
    return 0


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
        for tier in ("producer", "critic"):
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
            f"- DashScope Flagship/Critic Models: {model_checks}"
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
            f"[green]Siggi primary corpus ingested:[/green] new_or_existing={len(recs)}, vault_stats={stats}"
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
            "siggi_context_text": format_records_compact(siggi_recs, limit=32),
            "recon_context_text": format_records_compact(recon_recs, limit=32),
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
            combined = recs + siggi_all[:16] + recon_all[:10]
            return {
                "track": tp.model_dump(),
                "track_kind": tp.track_kind,
                "query_hashes": qh,
                "valid_ev_ids": sorted({r.ev_id for r in combined}),
                "evidence_context": format_records_compact(combined, limit=48),
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
    if isinstance(raw_payload, dict):
        raw_sector = raw_payload.get("sector_dossiers", raw_payload.get("dossiers", []))
        raw_comp = raw_payload.get("competitive_dossiers", [])
    else:
        raw_sector = raw_payload
        raw_comp = []

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        valid_ids = vault.list_valid_ids()
        cleaned_sectors: list[dict[str, Any]] = []
        cleaned_comps: list[dict[str, Any]] = []
        all_dropped: list[dict[str, Any]] = []

        for item in raw_sector:
            sd = SectorDossier.model_validate(item)
            c_sd, dropped = clean_sector_dossier(
                raw_dossier=sd,
                track_id=sd.track_id,
                sector=sd.sector,
                valid_global_ids=valid_ids,
            )
            cleaned_sectors.append(c_sd.model_dump())
            all_dropped.extend(dropped)

        for item in raw_comp:
            cd = CompetitiveEcosystemDossier.model_validate(item)
            c_cd, dropped = clean_competitive_dossier(
                raw_dossier=cd,
                track_id=cd.track_id,
                valid_global_ids=valid_ids,
            )
            cleaned_comps.append(c_cd.model_dump())
            all_dropped.extend(dropped)

        agg = aggregate_catalogs_and_screen(
            cleaned_sectors,
            competitive_dossiers=cleaned_comps,
            discovery_scope=settings.discovery_scope,
            contract=settings.contract,
            profile=profile,
        )
        mkt_summary = ChinaMarketSizingSummary.model_validate(agg["market_sizing_summary"])
        payload = {
            "shortlist": agg["shortlist"],
            "eliminated": agg["eliminated"],
            "projects": agg["projects"],
            "competitors": agg["competitors"],
            "pac_integrators": agg["pac_integrators"],
            "design_institute_barriers": agg["design_institute_barriers"],
            "dropped_unverified_records": all_dropped,
            "market_sizing_summary": agg["market_sizing_summary"],
            "market_sizing_md": format_market_sizing_table(mkt_summary),
            "roi_table_md": format_roi_table(agg["shortlist"]),
            "eliminated_table_md": format_eliminated_table(agg["eliminated"]),
            "vault_stats": vault.stats(),
            "all_valid_ev_ids": sorted(valid_ids),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 2 sizing & screening complete:[/green] shortlist={len(agg['shortlist'])}, "
            f"eliminated={len(agg['eliminated'])}, dropped_unverified={len(all_dropped)}, "
            f"projects={len(agg['projects'])}, comps={len(agg['competitors'])}, pacs={len(agg['pac_integrators'])}"
        )
        return 0
    finally:
        vault.close()


def _cmd_apply_arbitration(
    settings: WorkflowSettings,
    *,
    screened_file: str,
    arbitration_file: str,
    profile: str,
    vault_db: str,
    output_file: str,
) -> int:
    """Apply GlobalPortfolioArbitrator output, lock ExecutiveFactSheet, and route per-volume evidence bundles."""
    s_path = _resolve_path(settings, screened_file)
    a_path = _resolve_path(settings, arbitration_file)
    out_path = _resolve_path(settings, output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    screened = json.loads(s_path.read_text(encoding="utf-8"))
    arb_raw = unwrap_json_container_strings(json.loads(a_path.read_text(encoding="utf-8")))
    arb = PortfolioArbitrationOutput.model_validate(arb_raw)

    funnel_cfg = settings.contract.get("discovery_funnel", {}) or {}
    max_finalists = int(
        funnel_cfg.get("finalist_shortlist_flagship", 8)
        if profile == "flagship"
        else funnel_cfg.get("finalist_shortlist_fast", 5)
    )
    final_wedges = apply_portfolio_arbitration(
        screened.get("shortlist", []), arb, max_finalists=max_finalists
    )
    arb_dict = arb.model_dump()
    fact_sheet = build_executive_fact_sheet(
        market_sizing_summary=screened["market_sizing_summary"],
        evaluated_wedges=final_wedges,
        eliminated_wedges=screened.get("eliminated", []),
        arbitration=arb_dict,
        projects=screened.get("projects", []),
        competitors=screened.get("competitors", []),
        pac_integrators=screened.get("pac_integrators", []),
        design_institute_barriers=screened.get("design_institute_barriers", []),
    )

    state_like = {
        "evaluated_wedges": final_wedges,
        "eliminated_wedges": screened.get("eliminated", []),
        "china_projects_catalog": screened.get("projects", []),
        "competitors_catalog": screened.get("competitors", []),
        "pac_integrators_catalog": screened.get("pac_integrators", []),
    }

    vault = EvidenceVault(settings.resolve_vault_path(vault_db))
    try:
        volume_bundles: dict[str, str] = {}
        for fname, _, _ in VOLUME_SPECS:
            p_ids = collect_priority_ev_ids_for_volume(state_like, fname)  # type: ignore[arg-type]
            recs = vault.build_volume_evidence_bundle(
                volume_name=fname,
                track_ids=VOLUME_TRACK_ROUTING.get(fname, []),
                priority_ev_ids=p_ids,
                limit=80,
            )
            volume_bundles[fname] = format_records_compact(recs, limit=80)

        payload = {
            **screened,
            "evaluated_wedges": final_wedges,
            "portfolio_arbitration": arb_dict,
            "executive_fact_sheet": fact_sheet,
            "volume_evidence_bundles": volume_bundles,
            "all_valid_ev_ids": sorted(vault.list_valid_ids()),
            "vault_stats": vault.stats(),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]Stage 2 arbitration & volume routing locked:[/green] finalists={len(final_wedges)}, "
            f"fact_sheet_chars={len(fact_sheet)}, file={out_path}"
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
            "formatted_context": format_records_compact(added, limit=24) if added else "",
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Stage 3b CRAG refill complete:[/green] added={len(added)}")
        return 0
    finally:
        deps.vault.close()


def _cmd_finalize(
    settings: WorkflowSettings, *, bundle_file: str, vault_db: str, output_dir: str
) -> int:
    """Run 100% deterministic dual-edition full audit, render Zero-LLM Vol 05, and persist deliverables."""
    b_path = _resolve_path(settings, bundle_file)
    out_path = _resolve_path(settings, output_dir)
    exec_path = out_path / "executive_edition"
    out_path.mkdir(parents=True, exist_ok=True)
    exec_path.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(b_path.read_text(encoding="utf-8"))

    vault_path = settings.resolve_vault_path(vault_db)
    vault = EvidenceVault(vault_path)
    try:
        all_records = vault.list_all()
        vault_stats = vault.stats()
        valid_ids = vault.list_valid_ids()

        raw_full = dict(bundle.get("volumes") or {})
        raw_exec = dict(bundle.get("executive_volumes") or {})
        full_drafts: dict[str, str] = {
            k: str(v).strip() + "\n"
            for k, v in raw_full.items()
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
        }
        exec_drafts: dict[str, str] = {
            k: str(v).strip() + "\n"
            for k, v in raw_exec.items()
            if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
        }

        evaluated = list(bundle.get("evaluated_wedges") or bundle.get("shortlist") or [])
        eliminated = list(bundle.get("eliminated_wedges") or bundle.get("eliminated") or [])
        dropped = list(bundle.get("dropped_unverified_records") or [])

        audit_report = run_deterministic_full_audit(
            vault_stats=vault_stats,
            valid_ids=valid_ids,
            full_drafts=full_drafts,
            executive_drafts=exec_drafts,
            market_sizing_summary=bundle.get("market_sizing_summary", {}),
            evaluated_wedges=evaluated,
            eliminated_wedges=eliminated,
            dropped_unverified_records=dropped,
            contract=settings.contract,
        )

        vol05_md = render_evidence_index(all_records, db_label=f"data/{vault_path.name}")

        written: list[str] = []
        for fname, content in sorted(full_drafts.items()):
            assert_no_secrets_leaked(content, settings)
            target = out_path / fname
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        for fname, content in sorted(exec_drafts.items()):
            assert_no_secrets_leaked(content, settings)
            target = exec_path / fname
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        assert_no_secrets_leaked(vol05_md, settings)
        v05_target = out_path / "05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"
        v05_target.write_text(vol05_md, encoding="utf-8")
        written.append(str(v05_target))

        search_queries_logged = int(vault._conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0])
        scorecard = {
            "schema_version": "2.0",
            "run_id": bundle.get("run_id", f"native-{uuid.uuid4().hex[:8]}"),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "profile": bundle.get("profile", "flagship"),
            "llm_engine": bundle.get("llm_engine", "antigravity_native:pro"),
            "stage_gate_passed": audit_report.passed,
            "deterministic_audit_report": audit_report.model_dump(),
            "evidence_vault_stats": vault_stats,
            "market_sizing_summary": bundle.get("market_sizing_summary", {}),
            "evaluated_wedges_ranked": [
                {
                    "rank": e.get("composite_rank"),
                    "wedge_id": e["seed"]["wedge_id"],
                    "sector": e["seed"]["sector"],
                    "delivery_track": e["seed"]["delivery_track"],
                    "title": e["seed"]["title"],
                    "payback_months": e["roi"]["payback_months"],
                    "irr_5yr_pct": e["roi"]["irr_5yr_pct"],
                    "npv_5yr_cny": e["roi"]["npv_5yr_cny"],
                    "global_priority_score": e.get("global_priority_score"),
                    "weighted_pillar_score": e.get("weighted_pillar_score"),
                    "merged_from_wedge_ids": e.get("merged_from_wedge_ids", []),
                }
                for e in evaluated
            ],
            "eliminated_wedges": eliminated,
            "critique_loops_executed": int(bundle.get("critique_loops_executed", 0)),
            "critique_history": bundle.get("critique_history", []),
            "cost_and_token_telemetry": {
                "billing_mode": "Antigravity IDE Native Flagship Reasoning + Verified Local/Web Search",
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
            f"[bold green]V&F CCUS v2.0 Finalize Complete![/bold green]\n"
            f"- Deterministic Stage-Gate Passed: {audit_report.passed}\n"
            f"- Dual Edition Complete (Full 5 + Executive 5): {audit_report.dual_edition_complete}\n"
            f"- Numeric Consistency: {audit_report.numeric_consistency_passed}\n"
            f"- Failed Gates: {audit_report.failed_gates}\n"
            f"- Vault: {vault_stats}\n"
            f"- Deliverables ({len(written)} files) -> {out_path}"
        )
        return 0 if audit_report.passed else 1
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
        audit = final_state.get("audit_report", {})
        console.print(
            f"[bold green]Standalone LangGraph v2.0 Complete![/bold green] "
            f"passed={final_state.get('stage_gate_passed')} | failed_gates={audit.get('failed_gates', [])}"
        )
        return 0 if final_state.get("stage_gate_passed") else 1
    finally:
        deps.vault.close()


def _cmd_evaluate(settings: WorkflowSettings, *, scorecard_path: str) -> int:
    sc = _resolve_path(settings, scorecard_path)
    raw = sc.read_text(encoding="utf-8")
    assert_no_secrets_leaked(raw, settings)
    data = json.loads(raw)
    report = data.get("deterministic_audit_report") or data.get("judge_rubric") or {}
    console.print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if data.get("stage_gate_passed") else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="vf-ccus-research")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verify-env")

    p_exp = sub.add_parser("export-schemas")
    p_exp.add_argument("--output-file", default="data/v2_flat_schemas.json")

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

    p_arb = sub.add_parser("apply-arbitration")
    p_arb.add_argument("--screened-file", required=True)
    p_arb.add_argument("--arbitration-file", required=True)
    p_arb.add_argument("--profile", default="flagship")
    p_arb.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_arb.add_argument("--output-file", default="data/stage2_locked_fact_bundle.json")

    p_gap = sub.add_parser("gap-search")
    p_gap.add_argument("--queries-json", required=True)
    p_gap.add_argument("--vault-db", default="data/vf_ccus_evidence_vault.db")
    p_gap.add_argument("--output-file", default="data/stage3_gap_evidence.json")

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
    if args.cmd == "export-schemas":
        return _cmd_export_schemas(settings, output_file=args.output_file)
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
    if args.cmd == "apply-arbitration":
        return _cmd_apply_arbitration(
            settings,
            screened_file=args.screened_file,
            arbitration_file=args.arbitration_file,
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
