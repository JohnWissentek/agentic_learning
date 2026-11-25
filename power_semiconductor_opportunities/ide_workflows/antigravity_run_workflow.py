"""V4.0 Single-Core Thin Orchestration Shell for Antigravity IDE (`run_workflow`).

100% stdlib-only so it runs cleanly on system Python 3 without third-party imports.
All prompts, Pydantic schemas, calibrated PALMs ROI math, deterministic Markdown tables,
untrusted evidence fencing, and full-corpus objective audit live in `src/pso_workflow/`.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
VENV_PSO = BASE_DIR / ".venv/bin/pso-research"

_user_args = args if "args" in globals() and isinstance(args, dict) else {}
sector = str(_user_args.get("sector", "all"))
profile = str(_user_args.get("profile", "flagship"))
output_dir = str(_user_args.get("output_dir", "outputs/v4_model_first_grounded_2026_2036"))
vault_db = str(_user_args.get("vault_db", "data/evidence_vault_v4.db"))
target_model = str(_user_args.get("model", "pro"))
hitl_enabled = bool(_user_args.get("hitl", False))
resume_plan = str(_user_args.get("resume_plan", "")).strip()
resume_from_stage2 = bool(_user_args.get("resume_from_stage2", False))
run_id = f"v4-native-{uuid.uuid4().hex[:8]}"

NO_TOOL = (
    "\n\nIMPORTANT: All EvidenceVault records and calibrated `[ROI-CALC]` tables are already provided. "
    "Do NOT call shell/web/filesystem tools; complete reasoning in one turn and return via `finish`."
)


def _cli(cli_args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run([str(VENV_PSO), *cli_args], cwd=str(BASE_DIR), check=check, capture_output=True, text=True)
    if proc.stdout.strip():
        log(proc.stdout.strip())
    if proc.returncode != 0 and proc.stderr.strip():
        log(f"[CLI stderr] {proc.stderr.strip()}")
    return proc


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Load single-core schemas & prompts from `src/pso_workflow/` via `.venv/bin/pso-research`
schemas_path = BASE_DIR / "data/v4_runtime_schemas.json"
_cli(["export-v4-schemas", "--output", str(schemas_path)])
core_bundle = _read_json(schemas_path)
SCHEMAS = core_bundle["schemas"]
PROMPTS = core_bundle["prompts"]

# Stage 0 & Stage 1 (skip cleanly if resuming directly from verified Stage 1b dossiers)
plan_path = BASE_DIR / "data/v4_discovery_plan.json"
tracks_ev_path = BASE_DIR / "data/v4_tracks_evidence.json"
dossiers_path = BASE_DIR / "data/v4_raw_dossiers.json"
falsify_ctx_path = BASE_DIR / "data/v4_falsify_context.json"

if resume_from_stage2 and plan_path.exists() and dossiers_path.exists():
    phase("0-1. Resuming from verified Stage 0-1b plan, vault & falsified dossiers")
    norm_plan = _read_json(plan_path)
    tracks_ctx = _read_json(tracks_ev_path) if tracks_ev_path.exists() else {"tracks": norm_plan.get("track_plans", [])}
    falsify_ctx = _read_json(falsify_ctx_path) if falsify_ctx_path.exists() else {"tracks": []}
    falsify_review_count = sum(1 for t in falsify_ctx.get("tracks", []) if t.get("needs_falsification"))
else:
    if resume_plan and Path(resume_plan).exists():
        phase(f"0. Resuming from HITL-approved track plan ({resume_plan})")
        plan_path.write_text(Path(resume_plan).read_text(encoding="utf-8"), encoding="utf-8")
    else:
        phase(f"0. Stage 0 Macro Recon & Dynamic Track Discovery (sector={sector}, profile={profile})")
        recon_path = BASE_DIR / "data/v4_recon_context.json"
        _cli(["recon-search", "--sector", sector, "--profile", profile, "--vault-db", vault_db, "--output", str(recon_path)])
        recon_ctx = _read_json(recon_path)
        active_sectors = ["power_energy"] if sector == "power" else (["semiconductor"] if sector == "semiconductor" else ["power_energy", "semiconductor"])
        per_sec = 4 if profile == "flagship" else 2
        mandate_text = "\n".join(
            f"- {s} ({recon_ctx['sector_mandates'].get(s, {}).get('display_name', s)}): "
            f"{recon_ctx['sector_mandates'].get(s, {}).get('scope_description', '').strip()}"
            for s in active_sectors
        )
        plan_obj = await agent(
            role="Stage 0 Dynamic Track Architect (V4.0)",
            model=target_model,
            schema=SCHEMAS["DiscoveryPlan"],
            prompt=(
                f"{PROMPTS['RECON_DISCOVERY_SYSTEM']}\n\n"
                f"Contract ID: PSO-CONTRACT-2026-V4 | Sector: {sector} | Profile: {profile} | "
                f"Target Tracks: {per_sec * len(active_sectors)} ({per_sec} per active sector).\n"
                f"Mandates:\n{mandate_text}\n\nStage 0 EvidenceVault:\n{recon_ctx['recon_context_text']}\n\n"
                "Generate orthogonal tracks with pain-point (`cn_queries`/`global_queries`) AND vendor "
                "(`cn_vendor_queries`/`global_vendor_queries`) queries (`{\"query\": \"...\"}` items)." + NO_TOOL
            ),
        )
        plan_obj.update({"contract_id": "PSO-CONTRACT-2026-V4", "sector_filter": sector, "profile": "flagship" if profile == "flagship" else "fast"})
        _write_json(plan_path, plan_obj)

        if hitl_enabled:
            pending_path = BASE_DIR / "data/v4_hitl_pending_tracks.json"
            _write_json(pending_path, plan_obj)
            print(json.dumps({"status": "HITL_PAUSED_FOR_TRACK_APPROVAL", "pending_plan_file": str(pending_path), "tracks": [{"track_id": t.get("track_id"), "sector": t.get("sector"), "name": t.get("name")} for t in plan_obj.get("track_plans", [])]}, ensure_ascii=False))
            raise SystemExit(0)

    phase("1. Stage 1 Dual Search, Flagship Mining & Bounded Blank-Claim Falsification")
    _cli(["track-search", "--plan", str(plan_path), "--profile", profile, "--vault-db", vault_db, "--output", str(tracks_ev_path)])
    tracks_ctx = _read_json(tracks_ev_path)
    norm_plan = tracks_ctx["discovery_plan"]
    _write_json(plan_path, norm_plan)
    cands_per_track = "3-4" if profile == "flagship" else "2-3"

    async def _mine_track(t_entry: dict) -> dict:
        tp = t_entry["track"]
        tid = tp["track_id"]
        res = await agent(
            role=f"V4 Flagship Miner {tid}: {tp['name'][:18]}",
            model=target_model,
            schema=SCHEMAS["TrackDossier"],
            prompt=(
                f"{PROMPTS['RESEARCHER_V2_SYSTEM']}\n\nTrack `{tid}` (`{tp['sector']}`): **{tp['name']}**\n"
                f"Step-Back Physics: {tp.get('step_back_physics_principle', '')}\n{t_entry['guardrail_hint']}\n\n"
                f"EvidenceVault (`valid_ev_ids`: {t_entry['valid_ev_ids']}):\n{t_entry['evidence_context']}\n\n"
                f"Discover {cands_per_track} grounded opportunities (`{tid}-O1`, ...) with calibrated `roi_range_inputs` "
                "(`unit_margin_or_scrap_ratio`, `instrument_attribution_share`, `first_year_ramp_factor`) AND explicit "
                "`falsification_queries` (2 targeted vendor-check queries) for every claimed blank. "
                "Cite ONLY exact IDs from `valid_ev_ids`." + NO_TOOL
            ),
        )
        res.update({"track_id": tid, "sector": tp["sector"], "track_name": tp["name"]})
        return res

    _write_json(dossiers_path, {"dossiers": list(await parallel(tracks_ctx["tracks"], _mine_track))})
    _cli(["falsify-search", "--dossiers", str(dossiers_path), "--vault-db", vault_db, "--output", str(falsify_ctx_path), "--max-queries", "4" if profile == "flagship" else "2"])
    falsify_ctx = _read_json(falsify_ctx_path)

    async def _falsify_one(entry: dict) -> dict:
        if not entry.get("needs_falsification"):
            return entry["initial_dossier"]
        res = await agent(role=f"V4 Falsification Auditor {entry['track_id']}", model=target_model, schema=SCHEMAS["TrackDossier"], prompt=entry["falsify_prompt"] + NO_TOOL)
        res.update({"track_id": entry["track_id"], "sector": entry["sector"]})
        return res

    verified_dossiers = list(await parallel(falsify_ctx["tracks"], _falsify_one))
    falsify_review_count = sum(1 for t in falsify_ctx["tracks"] if t.get("needs_falsification"))
    _write_json(dossiers_path, {"dossiers": verified_dossiers})

# Stage 2: Calibrated PALMs 3-Scenario CFO Funnel
phase("2. Stage 2 Calibrated PALMs CFO Funnel & Commercial White-Space Screening")
screened_path = BASE_DIR / "data/v4_screened_shortlist.json"
_cli(["screen-candidates", "--dossiers", str(dossiers_path), "--plan", str(plan_path), "--sector", sector, "--profile", profile, "--vault-db", vault_db, "--output", str(screened_path)])
screened = _read_json(screened_path)

# Stage 3: Unified Sector Buying-Committee & Portfolio Prioritization (<=3 calls replacing 32)
phase("3. Stage 3 Holistic Sector Buying-Committee & Cross-Sector Portfolio Ranking")
portfolio_prompts_path = BASE_DIR / "data/v4_portfolio_prompts.json"
_cli(["prepare-portfolio", "--screened", str(screened_path), "--vault-db", vault_db, "--output", str(portfolio_prompts_path)])
p_ctx = _read_json(portfolio_prompts_path)
sector_review_list = list(
    await parallel(
        p_ctx["sector_tasks"],
        lambda task: agent(role=f"V4 Buying Committee ({task['sector']})", model=target_model, schema=SCHEMAS["SectorPortfolioReview"], prompt=f"{task['system_prompt']}\n\n{task['user_prompt']}" + NO_TOOL),
    )
)
sector_reviews_map = {task["sector"]: rev for task, rev in zip(p_ctx["sector_tasks"], sector_review_list)}

portfolio_results_path = BASE_DIR / "data/v4_portfolio_results.json"
synth_bundle_path = BASE_DIR / "data/v4_synthesis_bundle.json"
_write_json(portfolio_results_path, {"sector_reviews": sector_reviews_map, "global_portfolio_ranking": None})
_cli(["prepare-synthesis", "--screened", str(screened_path), "--portfolio", str(portfolio_results_path), "--plan", str(plan_path), "--vault-db", vault_db, "--output", str(synth_bundle_path)])
synth_ctx = _read_json(synth_bundle_path)

global_ranking_obj = None
if p_ctx.get("needs_global_ranking") and synth_ctx.get("global_rank_prompt"):
    global_ranking_obj = await agent(
        role="V4 Global Cross-Sector Portfolio Chair",
        model=target_model,
        schema=SCHEMAS["GlobalPortfolioRanking"],
        prompt=f"{p_ctx['global_system_prompt']}\n\n{synth_ctx['global_rank_prompt']}" + NO_TOOL,
    )
    _write_json(portfolio_results_path, {"sector_reviews": sector_reviews_map, "global_portfolio_ranking": global_ranking_obj})
    _cli(["prepare-synthesis", "--screened", str(screened_path), "--portfolio", str(portfolio_results_path), "--plan", str(plan_path), "--vault-db", vault_db, "--output", str(synth_bundle_path)])
    synth_ctx = _read_json(synth_bundle_path)

# Stage 4: Parallel 5-Volume High-Density Synthesis (Single-Core Prompts + Table Placeholders)
phase("4. Stage 4 Parallel 5-Volume High-Density Executive Synthesis (V4.0)")
vol_specs = synth_ctx["volumes_spec"]
synth_sys = synth_ctx["synthesizer_system_prompt"]
draft_texts = list(
    await parallel(
        vol_specs,
        lambda spec: agent(role=spec["role"], model=target_model, schema={"type": "string"}, prompt=f"{synth_sys}\n\n{spec['prompt']}" + NO_TOOL),
    )
)
volumes = {spec["filename"]: str(txt).strip() for spec, txt in zip(vol_specs, draft_texts)}

# Stage 5: Deterministic Table Injection, 100% Full-Corpus Hard Audit & Bounded Autonomous Repair
phase("5. Stage 5 Deterministic Table Injection, Full-Corpus Objective Audit & Finalization")
out_bundle_path = BASE_DIR / "data/v4_native_outputs_bundle.json"
revisions_run = 0


def _finalize() -> tuple[int, dict]:
    _write_json(
        out_bundle_path,
        {
            "run_id": run_id,
            "sector_filter": sector,
            "profile": profile,
            "llm_engine": f"antigravity_native:{target_model}",
            "discovery_plan": norm_plan,
            "shortlist": synth_ctx["ranked_shortlist"],
            "eliminated_candidates": screened["eliminated_candidates"],
            "raw_candidates_count": screened["raw_candidates_count"],
            "storm_memos": synth_ctx["storm_memos"],
            "portfolio_reviews": sector_reviews_map,
            "global_portfolio_ranking": synth_ctx["global_portfolio_ranking"],
            "volumes": volumes,
            "critique_loops_executed": revisions_run,
            "critique_history": [],
            "native_agent_invocations": {
                "stage0_discovery_architect": 1,
                "stage1_flagship_track_miners": len(tracks_ctx["tracks"]),
                "stage1b_falsification_auditors": falsify_review_count,
                "stage3_sector_portfolio_committees": len(sector_review_list),
                "stage3_global_portfolio_ranker": 1 if global_ranking_obj else 0,
                "stage4_volume_synthesizers": len(vol_specs),
                "stage5_targeted_hard_audit_repairs": revisions_run,
            },
        },
    )
    proc = _cli(["finalize-v4", "--bundle", str(out_bundle_path), "--vault-db", vault_db, "--output-dir", output_dir], check=False)
    sc_path = BASE_DIR / output_dir / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
    return proc.returncode, (_read_json(sc_path) if sc_path.exists() else {})


rc, scorecard = _finalize()
obj_audit = scorecard.get("objective_audit", {})
if rc != 0 and not obj_audit.get("passed", False):
    hard_failures = obj_audit.get("hard_failures", [])
    broken_ids = set(obj_audit.get("broken_citation_ids", []))
    roi_bad_vols = {m.get("volume", "") for m in obj_audit.get("roi_mismatches", [])}
    affected = [fn for fn, txt in volumes.items() if fn in roi_bad_vols or any(bid in txt for bid in broken_ids)] or list(volumes.keys())[:2]
    phase(f"5b. Autonomous Bounded Hard-Audit Repair ({len(affected)} volume(s))")
    repaired = list(
        await parallel(
            affected,
            lambda fn: agent(
                role=f"V4 Hard-Audit Repair {fn[:2]}",
                model=target_model,
                schema={"type": "string"},
                prompt=(
                    f"Fix EVERY objective hard-audit failure in `{fn}`:\n"
                    + "\n".join(f"- {f}" for f in hard_failures)
                    + "\nRemove any non-existent `[EV-...]` IDs, preserve `<!-- TABLE:... -->` placeholders "
                    "verbatim (do NOT alter `[ROI-CALC]` figures), and return ONLY the repaired Markdown.\n\n"
                    f"Current Draft:\n{volumes[fn]}" + NO_TOOL
                ),
            ),
        )
    )
    for fn, fixed_txt in zip(affected, repaired):
        volumes[fn] = str(fixed_txt).strip()
        revisions_run += 1
    rc, scorecard = _finalize()

print(
    json.dumps(
        {
            "run_id": run_id,
            "workflow_version": scorecard.get("workflow_version", "V4.0"),
            "stage_gate_passed": scorecard.get("stage_gate_passed", False),
            "objective_audit_passed": scorecard.get("objective_audit", {}).get("passed", False),
            "hard_failures": scorecard.get("objective_audit", {}).get("hard_failures", []),
            "output_dir": str(BASE_DIR / output_dir),
            "evidences": scorecard.get("evidence_vault_stats", {}).get("total"),
            "search_cost_cny": scorecard.get("cost_and_token_telemetry", {}).get("search_cost_cny"),
            "agent_invocations": scorecard.get("cost_and_token_telemetry", {}).get("native_agent_invocations", {}),
            "revisions_run": revisions_run,
        },
        ensure_ascii=False,
    )
)
