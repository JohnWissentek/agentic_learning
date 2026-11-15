"""V3.0 Commercial White-Space & AI-Native HW/SW Co-Design Discovery Workflow for Antigravity IDE (`run_workflow`).

Architecture (Zero-Preset Discovery + Commercial Vendor Grounding + AI-Native HW/SW Co-Design):
- Stage 0: `pso-research recon-search` (Paid CN Metaso + Global Serper scanning bottlenecks, commercial vendors, & AI shifts)
           -> Discovery Architect LLM clusters live evidence into orthogonal `DiscoveredTrack`s with BOTH tech & vendor queries.
- Stage 1: `pso-research track-search` (concurrent pain-point + commercial-vendor search + <6-hit broaden + fulltext)
           -> Parallel Track Miners extract `commercial_landscape_summary`, CN/GLOBAL pain points, and 3-4 candidates
              grounded with `commercial_status` (`global_and_cn_commercialized` / `overseas_only_cn_blank` /
              `global_and_cn_true_blank`), real vendor/model maps, AI HW/SW co-design specs, and `ROIRangeInputs`.
- Stage 2: `pso-research screen-candidates` (Deterministic Python PALMs range clamping, 3-scenario ROI,
           commercial white-space & AI-moat weighted scoring, hard gates -> Top 16 + Elimination Log).
- Stage 3: Parallel 4-Persona STORM Buying & Productization Committee stress-testing ONLY Top 16 shortlist
           (incumbent displacement, true-blank cold-start, air-gapped FPGA/NPU reliability, TCO payback).
- Stage 4: 2-Round Swiss-System AI Co-Scientist Elo Tournament on Top 16 + 55/45 composite ranking.
- Stage 5: Parallel 5-Volume Practical Grounded Synthesis (`00_`..`04_`) citing `[EV-...]`, vendor matrices,
           AI HW/SW co-design playbooks, and 3-scenario `[ROI-CALC]`.
- Stage 6: Bounded Heterogeneous Critic Reflection Loop (`max_loops=2`) with Corrective RAG `gap-search`.
- Stage 7: Independent Stage-Gate Judge -> `pso-research finalize-v3` compiles 7 deliverables (`00_`..`06_`).
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
VENV_PSO = BASE_DIR / ".venv/bin/pso-research"

_user_args = args if "args" in globals() and isinstance(args, dict) else {}
sector = str(_user_args.get("sector", "all"))
profile = str(_user_args.get("profile", "flagship"))
output_dir = str(_user_args.get("output_dir", "outputs/v3_commercial_ai_grounded_2026_2036"))
vault_db = str(_user_args.get("vault_db", "data/evidence_vault_v3.db"))
target_model = str(_user_args.get("model", "pro"))
hitl_enabled = bool(_user_args.get("hitl", False))
run_id = f"v3-native-{uuid.uuid4().hex[:8]}"
max_loops = 2 if profile == "flagship" else 1

NO_TOOL_DIRECTIVE = (
    "\n\nIMPORTANT: All required EvidenceVault excerpts, physical scale guardrails, and deterministic "
    "[ROI-CALC] numbers are ALREADY provided in this prompt. Do NOT call any filesystem, shell, search, "
    "or browser tools. Complete your reasoning in one turn and return your result via `finish` matching the JSON schema."
)


def _run_cli(cli_args: list[str]) -> str:
    proc = subprocess.run(
        [str(VENV_PSO), *cli_args],
        cwd=str(BASE_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    if out:
        log(out)
    return out


# ---------------------------------------------------------------------------
# Flat JSON Schemas (zero $ref / $defs) for run_workflow `agent(..., schema=...)`
# ---------------------------------------------------------------------------

DISCOVERY_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "macro_recon_summary": {"type": "string"},
        "step_back_thesis": {"type": "string"},
        "track_plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                    "sector": {"type": "string", "enum": ["power_energy", "semiconductor"]},
                    "name": {"type": "string"},
                    "step_back_physics_principle": {"type": "string"},
                    "is_emerging_or_cross_cutting": {"type": "boolean"},
                    "emergence_rationale": {"type": "string"},
                    "recon_evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "manufacturing_stages": {"type": "array", "items": {"type": "string"}},
                    "cn_queries": {"type": "array", "items": {"type": "string"}},
                    "global_queries": {"type": "array", "items": {"type": "string"}},
                    "cn_vendor_queries": {"type": "array", "items": {"type": "string"}},
                    "global_vendor_queries": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "track_id",
                    "sector",
                    "name",
                    "step_back_physics_principle",
                    "is_emerging_or_cross_cutting",
                    "emergence_rationale",
                    "recon_evidence_ids",
                    "manufacturing_stages",
                    "cn_queries",
                    "global_queries",
                    "cn_vendor_queries",
                    "global_vendor_queries",
                ],
            },
        },
    },
    "required": ["macro_recon_summary", "step_back_thesis", "track_plans"],
}

TRACK_MINER_SCHEMA = {
    "type": "object",
    "properties": {
        "commercial_landscape_summary": {"type": "string"},
        "china_market_dynamics": {"type": "string"},
        "global_market_dynamics": {"type": "string"},
        "horizon_3_5y_outlook": {"type": "string"},
        "horizon_5_10y_outlook": {"type": "string"},
        "pain_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "process_stage": {"type": "string"},
                    "geo_scope": {"type": "string", "enum": ["CN", "GLOBAL"]},
                    "pain_description": {"type": "string"},
                    "current_limitation": {"type": "string"},
                    "impact_pillars": {"type": "array", "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "process_stage",
                    "geo_scope",
                    "pain_description",
                    "current_limitation",
                    "impact_pillars",
                    "evidence_ids",
                ],
            },
        },
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opp_id": {"type": "string"},
                    "title": {"type": "string"},
                    "horizon": {"type": "string", "enum": ["3-5y", "5-10y"]},
                    "commercial_status": {
                        "type": "string",
                        "enum": [
                            "global_and_cn_commercialized",
                            "overseas_only_cn_blank",
                            "global_and_cn_true_blank",
                        ],
                    },
                    "global_vendors_and_products": {"type": "string"},
                    "china_vendors_and_products": {"type": "string"},
                    "white_space_and_entry_wedge": {"type": "string"},
                    "ai_computational_sensing_and_co_design": {"type": "string"},
                    "ai_rd_acceleration_and_edge_deployment": {"type": "string"},
                    "estimated_rd_months_ai_vs_legacy": {"type": "string"},
                    "hardware_bom_localization_and_gtm_form": {"type": "string"},
                    "china_priority_score": {"type": "number"},
                    "global_priority_score": {"type": "number"},
                    "physics_principle": {"type": "string"},
                    "target_process_point": {"type": "string"},
                    "product_form_factor": {"type": "string"},
                    "quality_yield_mechanism": {"type": "string"},
                    "cost_tco_mechanism": {"type": "string"},
                    "green_ehs_mechanism": {"type": "string"},
                    "industrial_upgrade_mechanism": {"type": "string"},
                    "china_positioning": {"type": "string"},
                    "global_expansion_path": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "roi_range_inputs": {
                        "type": "object",
                        "properties": {
                            "capex_cny_low": {"type": "number"},
                            "capex_cny_base": {"type": "number"},
                            "capex_cny_high": {"type": "number"},
                            "yield_gain_pct_low": {"type": "number"},
                            "yield_gain_pct_base": {"type": "number"},
                            "yield_gain_pct_high": {"type": "number"},
                            "annual_output_value_cny": {"type": "number"},
                            "annual_opex_cny": {"type": "number"},
                            "annual_scrap_saving_cny": {"type": "number"},
                            "annual_downtime_saving_cny": {"type": "number"},
                            "annual_consumable_ehs_saving_cny": {"type": "number"},
                            "market_tam_china_cny_100m": {"type": "number"},
                            "market_tam_global_usd_m": {"type": "number"},
                            "parameter_basis": {"type": "string"},
                        },
                        "required": [
                            "capex_cny_low",
                            "capex_cny_base",
                            "capex_cny_high",
                            "yield_gain_pct_low",
                            "yield_gain_pct_base",
                            "yield_gain_pct_high",
                            "annual_output_value_cny",
                            "annual_opex_cny",
                            "annual_scrap_saving_cny",
                            "annual_downtime_saving_cny",
                            "annual_consumable_ehs_saving_cny",
                            "market_tam_china_cny_100m",
                            "market_tam_global_usd_m",
                            "parameter_basis",
                        ],
                    },
                },
                "required": [
                    "opp_id",
                    "title",
                    "horizon",
                    "commercial_status",
                    "global_vendors_and_products",
                    "china_vendors_and_products",
                    "white_space_and_entry_wedge",
                    "ai_computational_sensing_and_co_design",
                    "ai_rd_acceleration_and_edge_deployment",
                    "estimated_rd_months_ai_vs_legacy",
                    "hardware_bom_localization_and_gtm_form",
                    "china_priority_score",
                    "global_priority_score",
                    "physics_principle",
                    "target_process_point",
                    "product_form_factor",
                    "quality_yield_mechanism",
                    "cost_tco_mechanism",
                    "green_ehs_mechanism",
                    "industrial_upgrade_mechanism",
                    "china_positioning",
                    "global_expansion_path",
                    "evidence_ids",
                    "roi_range_inputs",
                ],
            },
        },
    },
    "required": [
        "commercial_landscape_summary",
        "china_market_dynamics",
        "global_market_dynamics",
        "horizon_3_5y_outlook",
        "horizon_5_10y_outlook",
        "pain_points",
        "opportunities",
    ],
}

STORM_SCHEMA = {
    "type": "object",
    "properties": {
        "sharpest_pain_point_summary": {"type": "string"},
        "key_localization_or_export_moat": {"type": "string"},
        "buyer_assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "persona_role": {
                        "type": "string",
                        "enum": [
                            "Fab/Plant Yield VP",
                            "Metrology/Process Chief Engineer",
                            "EHS & Green Compliance Director",
                            "CFO / Procurement ROI Gatekeeper",
                        ],
                    },
                    "core_question": {"type": "string"},
                    "adoption_barrier": {"type": "string"},
                    "spec_in_trigger": {"type": "string"},
                    "recommended_product_tweak": {"type": "string"},
                },
                "required": [
                    "persona_role",
                    "core_question",
                    "adoption_barrier",
                    "spec_in_trigger",
                    "recommended_product_tweak",
                ],
            },
        },
    },
    "required": [
        "sharpest_pain_point_summary",
        "key_localization_or_export_moat",
        "buyer_assessments",
    ],
}

ELO_SCHEMA = {
    "type": "object",
    "properties": {
        "winner_id": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["winner_id", "rationale"],
}

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["pass", "needs_more_evidence", "needs_rewrite"]},
        "overall_confidence": {"type": "number"},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "section": {"type": "string"},
                    "issue_type": {
                        "type": "string",
                        "enum": [
                            "missing_evidence",
                            "physics_precision",
                            "commercial_landscape_gap",
                            "ai_co_design_depth",
                            "china_global_balance",
                            "horizon_clarity",
                            "roi_consistency",
                            "prose_quality",
                        ],
                    },
                    "description": {"type": "string"},
                },
                "required": ["severity", "section", "issue_type", "description"],
            },
        },
        "gap_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                    "geo_scope": {"type": "string", "enum": ["CN", "GLOBAL"]},
                    "query": {"type": "string"},
                },
                "required": ["track_id", "geo_scope", "query"],
            },
        },
    },
    "required": ["decision", "overall_confidence", "summary", "issues", "gap_queries"],
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "china_first_then_global_depth": {"type": "number"},
        "dual_horizon_3_5y_vs_5_10y_rigor": {"type": "number"},
        "pain_point_and_physics_specificity": {"type": "number"},
        "roi_and_industrial_upgrade_value": {"type": "number"},
        "citation_grounding_and_prose": {"type": "number"},
        "total_score": {"type": "number"},
        "executive_verdict": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "residual_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "china_first_then_global_depth",
        "dual_horizon_3_5y_vs_5_10y_rigor",
        "pain_point_and_physics_specificity",
        "roi_and_industrial_upgrade_value",
        "citation_grounding_and_prose",
        "total_score",
        "executive_verdict",
        "strengths",
        "residual_risks",
    ],
}


# ---------------------------------------------------------------------------
# Stage 0: Macro Recon Search -> Dynamic Zero-Preset Track Clustering
# ---------------------------------------------------------------------------

phase(f"0. Stage 0 Macro Recon & Commercial/AI Track Discovery (sector={sector}, profile={profile})")
recon_path = BASE_DIR / "data/v3_recon_context.json"
_run_cli(
    [
        "recon-search",
        "--sector",
        sector,
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output",
        str(recon_path),
    ]
)
recon_ctx = json.loads(recon_path.read_text(encoding="utf-8"))

active_sectors = (
    ["power_energy"]
    if sector == "power"
    else (["semiconductor"] if sector == "semiconductor" else ["power_energy", "semiconductor"])
)
per_sector_tracks = 4 if profile == "flagship" else 2
target_track_total = per_sector_tracks * len(active_sectors)
queries_per_geo = 2 if profile == "flagship" else 1
vendor_queries_per_geo = 2 if profile == "flagship" else 1

mandate_text = "\n".join(
    f"- {s} ({recon_ctx['sector_mandates'].get(s, {}).get('display_name', s)}): "
    f"{recon_ctx['sector_mandates'].get(s, {}).get('scope_description', '').strip()}"
    for s in active_sectors
)

raw_discovery = await agent(
    role="Stage 0 Dynamic Track Architect (V3.0)",
    model=target_model,
    schema=DISCOVERY_PLAN_SCHEMA,
    prompt=(
        "You are a Chief Industrial Metrology Discovery Architect executing Stage 0 MACRO RECONNAISSANCE "
        "(V3.0 Commercial White-Space & AI Co-Design Grounding). Start with NO preset sub-track table and NO preset seeds.\n\n"
        f"Sector Filter: {sector} | Profile: {profile} | Target Orthogonal Tracks: {target_track_total} "
        f"({per_sector_tracks} for each active sector).\n"
        f"Mandate Scope Boundaries:\n{mandate_text}\n\n"
        f"Live Stage 0 Macro Recon EvidenceVault Snippets (`[EV-...]`):\n{recon_ctx['recon_context_text']}\n\n"
        "Instructions:\n"
        "1. Cluster the live Stage 0 signals into orthogonal, high-impact manufacturing tracks "
        "(`DP1`..`DP4` for `power_energy`, `DS1`..`DS4` for `semiconductor` when both sectors active).\n"
        "2. Actively spotlight genuinely emerging or cross-cutting inflections (`is_emerging_or_cross_cutting=true`, "
        "e.g. AI data-center HVDC/liquid-cooling testing, CPO silicon photonics, glass substrate, solid-state interface, etc., "
        "ONLY where evidenced) and explain why in `emergence_rationale` citing `recon_evidence_ids`.\n"
        "3. Apply Step-Back first-principles physics (`step_back_physics_principle`) AND generate FOUR query sets per track:\n"
        f"   - `{queries_per_geo}` Chinese pain-point/policy queries (`cn_queries`) + `{queries_per_geo}` English pain-point/standard queries (`global_queries`)\n"
        f"   - `{vendor_queries_per_geo}` Chinese commercial-vendor/tender queries (`cn_vendor_queries`: 国产厂商、中标、设备型号、替代) "
        f"+ `{vendor_queries_per_geo}` English incumbent vendor/model queries (`global_vendor_queries`: commercial vendor, inline metrology tool, equipment model)\n"
        "4. Write all Chinese prose cleanly in Simplified Chinese with bilingual terms on first mention."
        + NO_TOOL_DIRECTIVE
    ),
)

discovery_plan_payload = {
    "contract_id": recon_ctx["contract"].get("contract_id", "PSO-CONTRACT-2026-V3"),
    "sector_filter": sector,
    "profile": "flagship" if profile == "flagship" else "fast",
    "macro_recon_summary": raw_discovery.get("macro_recon_summary", ""),
    "step_back_thesis": raw_discovery.get("step_back_thesis", ""),
    "track_plans": raw_discovery.get("track_plans", []),
}
plan_path = BASE_DIR / "data/v3_discovery_plan.json"
plan_path.write_text(json.dumps(discovery_plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

if hitl_enabled:
    log("[HITL Info] Stage 0 dynamic tracks logged cleanly before Stage 1 vendor+pain-point search.")


# ---------------------------------------------------------------------------
# Stage 1: Dual Track Search (Pain-Points + Commercial Vendors) + Mining
# ---------------------------------------------------------------------------

phase(f"1. Stage 1 Dual Pain-Point & Vendor Search + Mining ({len(discovery_plan_payload['track_plans'])} tracks)")
tracks_ev_path = BASE_DIR / "data/v3_tracks_evidence.json"
_run_cli(
    [
        "track-search",
        "--plan",
        str(plan_path),
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output",
        str(tracks_ev_path),
    ]
)
tracks_ctx = json.loads(tracks_ev_path.read_text(encoding="utf-8"))
norm_plan = tracks_ctx["discovery_plan"]
plan_path.write_text(json.dumps(norm_plan, ensure_ascii=False, indent=2), encoding="utf-8")

cands_per_track = "3-4" if profile == "flagship" else "2-3"


async def _mine_track(t_entry: dict) -> dict:
    tp = t_entry["track"]
    tid = tp["track_id"]
    res = await agent(
        role=f"V3 Commercial+AI Miner {tid}: {tp['name'][:18]}",
        model=target_model,
        schema=TRACK_MINER_SCHEMA,
        prompt=(
            f"You are an isolated Senior Metrology Product Architect & Market Intelligence Lead mining Track `{tid}` "
            f"(`{tp['sector']}`): **{tp['name']}**.\n"
            f"Emerging/Cross-Cutting: {tp.get('is_emerging_or_cross_cutting')} | Rationale: {tp.get('emergence_rationale', '')}\n"
            f"Step-Back Physics Principle: {tp.get('step_back_physics_principle', '')}\n"
            f"Manufacturing Stages: {', '.join(tp.get('manufacturing_stages', []))}\n\n"
            f"{t_entry['guardrail_hint']}\n\n"
            f"Verified Retrieved EvidenceVault Records (`valid_ev_ids`: {t_entry['valid_ev_ids']}):\n"
            f"{t_entry['evidence_context']}\n\n"
            "CRITICAL V3.0 INSTRUCTIONS (ANTI-THEORETICAL GROUNDING):\n"
            "1. Synthesize China-FIRST -> Global-SECOND dynamics (`china_market_dynamics`, `global_market_dynamics`), "
            "dual time horizons (`horizon_3_5y_outlook`, `horizon_5_10y_outlook`), AND `commercial_landscape_summary` "
            "summarizing which overseas and Chinese vendors already sell tools vs where true product white-space sits.\n"
            "2. Extract concrete factory-floor `pain_points` covering BOTH `CN` and `GLOBAL` with exact verified `evidence_ids`.\n"
            f"3. Bottom-up discover {cands_per_track} candidate online instrumentation `opportunities` (`opp_id` = `{tid}-O1`, `{tid}-O2`, ...) "
            "spanning both `3-5y` and `5-10y`, each specifying:\n"
            "   (a) STRICT VENDOR LANDSCAPE & WHITE-SPACE: set `commercial_status` cleanly to one of "
            "`global_and_cn_commercialized`, `overseas_only_cn_blank`, or `global_and_cn_true_blank`. "
            "List ONLY vendors & product models explicitly observed in `evidence_context` with inline `[EV-GL-...]`/`[EV-CN-...]` citations "
            "in `global_vendors_and_products` and `china_vendors_and_products`. If NO mass-produced inline China or global product is found, "
            "state `'尚未检索到量产在售整机（疑似空白）'` instead of inventing models! Detail the unmet wedge in `white_space_and_entry_wedge`.\n"
            "   (b) AI-ERA HARDWARE/SOFTWARE CO-DESIGN PARADIGM:\n"
            "       - `ai_computational_sensing_and_co_design`: how PINNs / inverse scattering / compressive reconstruction / AI super-resolution "
            "trades edge compute for expensive hardware (reducing BOM cost or bypassing export-controlled ultra-high-spec components).\n"
            "       - `ai_rd_acceleration_and_edge_deployment`: how multiphysics surrogates, synthetic defect cold-start (Zero/Few-shot), "
            "AI-assisted FPGA/EDA/host-SW generation (compressing legacy 30-48m cycles to 10-18m), and air-gapped factory FPGA+NPU Edge-AI + Golden-Tool self-calibration work.\n"
            "       - `estimated_rd_months_ai_vs_legacy`: concrete contrast string, e.g. `'AI协同研发 12-16个月 vs 传统模式 36-42个月'`.\n"
            "       - `hardware_bom_localization_and_gtm_form`: domestic component substitutions + GTM form factor (OEM module / inline retrofit / full ATE).\n"
            "   (c) `roi_range_inputs`: concrete `capex_cny_low/base/high`, `yield_gain_pct_low/base/high`, `annual_output_value_cny`, "
            "`annual_opex_cny`, savings, TAM, and explicit `parameter_basis`."
            + NO_TOOL_DIRECTIVE
        ),
    )
    opps = []
    for idx, opp in enumerate(res.get("opportunities", []), start=1):
        opp_d = dict(opp)
        opp_d.setdefault("opp_id", f"{tid}-O{idx}")
        opp_d["track_id"] = tid
        opp_d["sector"] = tp["sector"]
        opps.append(opp_d)
    return {
        "track_id": tid,
        "sector": tp["sector"],
        "track_name": tp["name"],
        **res,
        "opportunities": opps,
    }


raw_dossiers = list(await parallel(tracks_ctx["tracks"], _mine_track))
dossiers_path = BASE_DIR / "data/v3_raw_dossiers.json"
dossiers_path.write_text(json.dumps({"dossiers": raw_dossiers}, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 2: Deterministic Python Range PALMs, White-Space Scoring & Funnel
# ---------------------------------------------------------------------------

phase("2. Stage 2 Deterministic Range PALMs, Commercial White-Space & Funnel Screening")
screened_path = BASE_DIR / "data/v3_screened_shortlist.json"
_run_cli(
    [
        "screen-candidates",
        "--dossiers",
        str(dossiers_path),
        "--plan",
        str(plan_path),
        "--sector",
        sector,
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output",
        str(screened_path),
    ]
)
screened = json.loads(screened_path.read_text(encoding="utf-8"))
shortlist = list(screened["shortlist"])
eliminated = list(screened["eliminated_candidates"])
cleaned_dossiers = list(screened["cleaned_dossiers"])
vstats = dict(screened["vault_stats"])
log(
    f"Stage 2 Funnel: raw={screened['raw_candidates_count']} -> shortlist={len(shortlist)} "
    f"(eliminated={len(eliminated)}) | vault_total={vstats.get('total')}"
)


# ---------------------------------------------------------------------------
# Stage 3: Parallel 4-Persona STORM Interrogation (ONLY Top Shortlist)
# ---------------------------------------------------------------------------

phase(f"3. Stage 3 4-Persona STORM Buying Committee ({len(shortlist)} shortlisted candidates)")


async def _storm_one(ev: dict) -> dict:
    s = ev["seed"]
    base_roi = ev["roi"]
    cons_roi = (ev.get("roi_range") or {}).get("conservative", base_roi)
    opt_roi = (ev.get("roi_range") or {}).get("optimistic", base_roi)
    cs_code = s.get("commercial_status", "overseas_only_cn_blank")
    memo = await agent(
        role=f"STORM Buyer Panel (V3): {s['opp_id']}",
        model=target_model,
        schema=STORM_SCHEMA,
        prompt=(
            f"Stress-test `{s['opp_id']}` ({s['sector']} | {s['track_id']} | {s['horizon']}): **{s['title']}**\n"
            f"- Physics Principle: {s['physics_principle']} | Process Point: {s['target_process_point']} | Form Factor: {s['product_form_factor']}\n"
            f"- Commercial Landscape (`{cs_code}`): Overseas={s.get('global_vendors_and_products', '')} | "
            f"China={s.get('china_vendors_and_products', '')} | Wedge={s.get('white_space_and_entry_wedge', '')}\n"
            f"- AI HW/SW Co-Design: {s.get('ai_computational_sensing_and_co_design', '')}\n"
            f"- AI R&D & Edge-AI: {s.get('ai_rd_acceleration_and_edge_deployment', '')} ({s.get('estimated_rd_months_ai_vs_legacy', '')})\n"
            f"- BOM & GTM Form: {s.get('hardware_bom_localization_and_gtm_form', '')}\n"
            f"- China Positioning: {s['china_positioning']} | Global Expansion: {s['global_expansion_path']}\n"
            f"- Deterministic [ROI-CALC] 3-Scenario Payback: Optimistic={opt_roi['payback_months']}m, "
            f"Baseline={base_roi['payback_months']}m (CAPEX ¥{base_roi['capex_cny']:,.0f}, IRR {base_roi['irr_5yr_pct']}%), "
            f"Conservative Stress={cons_roi['payback_months']}m (CAPEX ¥{cons_roi['capex_cny']:,.0f}, IRR {cons_roi['irr_5yr_pct']}%)\n\n"
            "Evaluate rigorously across ALL 4 factory personas (`Fab/Plant Yield VP`, `Metrology/Process Chief Engineer`, "
            "`EHS & Green Compliance Director`, `CFO / Procurement ROI Gatekeeper`) explicitly probing: "
            "(1) incumbent displacement vs blank-market Golden-Tool cold-start validation burden, "
            "(2) air-gapped factory Edge-AI NPU+FPGA compliance & physics interpretability, "
            "(3) BOM localization resilience & conservative downside ROI. "
            "Output concise Simplified Chinese `sharpest_pain_point_summary`, `key_localization_or_export_moat`, and 4 `buyer_assessments`."
            + NO_TOOL_DIRECTIVE
        ),
    )
    memo["opp_id"] = s["opp_id"]
    return memo


storm_results = list(await parallel(shortlist, _storm_one))
storm_memos = {m["opp_id"]: m for m in storm_results}
for ev in shortlist:
    ev["storm_memo"] = storm_memos.get(ev["seed"]["opp_id"])
    ev["elo_rating"] = round(1500.0 + (ev["weighted_pillar_score"] - 75.0) * 4.0, 2)


# ---------------------------------------------------------------------------
# Stage 4: Swiss-System AI Co-Scientist Elo Tournament & Post-Elo Tables
# ---------------------------------------------------------------------------

phase("4. Stage 4 AI Co-Scientist Pairwise Elo Tournament (ROI + White-Space + AI Co-Design)")
elo_matches: list[dict] = []

COMMERCIAL_STATUS_LABELS = {
    "global_and_cn_commercialized": "海内外均已在售(红海/升级)",
    "overseas_only_cn_blank": "海外在售·国产空白",
    "global_and_cn_true_blank": "海内外均属产品空白",
}


def _update_elo_local(ra: float, rb: float, a_won: bool, k: float = 32.0) -> tuple[float, float]:
    ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
    eb = 1.0 - ea
    sa = 1.0 if a_won else 0.0
    return round(ra + k * (sa - ea), 2), round(rb + k * ((1.0 - sa) - eb), 2)


def _pair_summary(label: str, ev: dict) -> str:
    s = ev["seed"]
    r = ev["roi"]
    rr = ev.get("roi_range") or {}
    opt_pb = rr.get("optimistic", {}).get("payback_months", r["payback_months"])
    cons_pb = rr.get("conservative", {}).get("payback_months", r["payback_months"])
    tam_cn = (s.get("roi_inputs") or {}).get("market_tam_china_cny_100m", 0)
    cs_lbl = COMMERCIAL_STATUS_LABELS.get(s.get("commercial_status", ""), s.get("commercial_status", ""))
    return (
        f"[{label}: {s['opp_id']}] ({s['sector']} | {s['track_id']} | {s['horizon']} | 商业状态={cs_lbl}) {s['title']}\n"
        f"- [ROI-CALC] Payback(Opt/Base/Cons)={opt_pb}/{r['payback_months']}/{cons_pb}m, "
        f"CAPEX=¥{r['capex_cny']:,.0f}, NetCF=¥{r['net_annual_cashflow_cny']:,.0f}, IRR={r['irr_5yr_pct']}%, ChinaTAM=¥{tam_cn}亿\n"
        f"- Vendors/Wedge: CN={str(s.get('china_vendors_and_products', ''))[:110]} | GL={str(s.get('global_vendors_and_products', ''))[:110]}\n"
        f"- AI Co-Design ({s.get('estimated_rd_months_ai_vs_legacy', '')}): {str(s.get('ai_computational_sensing_and_co_design', ''))[:140]}\n"
        f"- Yield: {s['quality_yield_mechanism']} | Upgrade: {s['industrial_upgrade_mechanism']}"
    )


elo_rounds = (1, 2) if profile == "flagship" else (1,)
for r_idx in elo_rounds:
    shortlist.sort(key=lambda x: x["elo_rating"], reverse=True)
    matchups = [(shortlist[i], shortlist[i + 1]) for i in range(0, len(shortlist) - 1, 2)]
    decisions = await parallel(
        matchups,
        lambda pair: agent(
            role=f"Elo Judge R{r_idx}: {pair[0]['seed']['opp_id']} vs {pair[1]['seed']['opp_id']}",
            model=target_model,
            schema=ELO_SCHEMA,
            prompt=(
                "Compare Option A vs Option B on: Manufacturing ROI & Conservative Resilience (30%), "
                "Quality/Yield Impact (25%), Commercial White-Space Attractiveness (China-Blank / Global-Blank vs Red-Ocean) & Upgrade Leverage (25%), "
                "and AI-Era HW/SW Co-Design Feasibility, R&D Compression & Green EHS (20%).\n\n"
                f"{_pair_summary('Option A', pair[0])}\n\n{_pair_summary('Option B', pair[1])}\n\n"
                f'Return JSON with `winner_id` strictly equal to "{pair[0]["seed"]["opp_id"]}" or '
                f'"{pair[1]["seed"]["opp_id"]}", and a concise Chinese `rationale`.'
                + NO_TOOL_DIRECTIVE
            ),
        ),
    )
    for (a, b), dec in zip(matchups, decisions):
        a_id, b_id = a["seed"]["opp_id"], b["seed"]["opp_id"]
        a_won = str(dec.get("winner_id", "")).strip() != b_id
        wid = a_id if a_won else b_id
        new_a, new_b = _update_elo_local(a["elo_rating"], b["elo_rating"], a_won, k=32.0)
        a["elo_rating"], b["elo_rating"] = new_a, new_b
        elo_matches.append(
            {
                "round_idx": r_idx,
                "opp_a_id": a_id,
                "opp_b_id": b_id,
                "winner_id": wid,
                "rationale": dec.get("rationale", ""),
                "elo_a_after": new_a,
                "elo_b_after": new_b,
            }
        )

if shortlist:
    elos = [e["elo_rating"] for e in shortlist]
    lo, hi = min(elos), max(elos)
    span = max(1.0, hi - lo)
    shortlist.sort(
        key=lambda e: 0.55 * e["weighted_pillar_score"] + 0.45 * (60.0 + ((e["elo_rating"] - lo) / span) * 38.0),
        reverse=True,
    )
    for idx, item in enumerate(shortlist, start=1):
        item["composite_rank"] = idx


def _format_post_elo_roi_table(items: list[dict], sec: str | None = None) -> str:
    header = (
        "| 综合排名 | ID | 赛道 | 周期 | 机会名称 | 商业空白级 | 基准CAPEX | 基准年净现金流 | "
        "乐观/基准/保守回收期[ROI-CALC] | 基准5年IRR[ROI-CALC] | 基准5年NPV[ROI-CALC] | ROI分级 | 综合分/Elo | 证据溯源 |\n"
        "| :---: | :---: | :---: | :---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :---: | :--- |"
    )
    rows = []
    for item in items:
        s = item["seed"]
        if sec and s["sector"] != sec:
            continue
        r = item["roi"]
        rr = item.get("roi_range") or {}
        opt_pb = rr.get("optimistic", {}).get("payback_months", r["payback_months"])
        cons_pb = rr.get("conservative", {}).get("payback_months", r["payback_months"])
        cs_lbl = COMMERCIAL_STATUS_LABELS.get(s.get("commercial_status", ""), s.get("commercial_status", ""))
        rows.append(
            f"| #{item['composite_rank']} | `{s['opp_id']}` | {s['track_id']} | {s['horizon']} | "
            f"{s['title']} | {cs_lbl} | ¥{r['capex_cny']/10000:.1f}万 | ¥{r['net_annual_cashflow_cny']/10000:.1f}万/年 | "
            f"**{opt_pb} / {r['payback_months']} / {cons_pb}月** | {r['irr_5yr_pct']}% | ¥{r['npv_5yr_cny']/10000:.1f}万 | "
            f"{r['payback_tier']} | {item['weighted_pillar_score']} / Elo {item['elo_rating']} | "
            f"{', '.join(f'[{e}]' for e in s.get('evidence_ids', [])[:4])} |"
        )
    return header + "\n" + "\n".join(rows)


def _format_post_elo_commercial_table(items: list[dict], sec: str | None = None) -> str:
    header = (
        "| 综合排名 | ID | 赛道 | 机会名称 | 商业化状态 | 海外在售厂商与型号 | 中国本土厂商与空白 | "
        "AI算力换硬件与软硬件协同方案 | AI研发周期 vs 传统 | BOM国产化与切入形态 |\n"
        "| :---: | :---: | :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    )
    rows = []
    for item in items:
        s = item["seed"]
        if sec and s["sector"] != sec:
            continue
        cs_lbl = COMMERCIAL_STATUS_LABELS.get(s.get("commercial_status", ""), s.get("commercial_status", ""))
        gl_v = (s.get("global_vendors_and_products") or "未见披露").replace("\n", " ")
        cn_v = (s.get("china_vendors_and_products") or "尚未检索到量产在售整机").replace("\n", " ")
        ai_cs = (s.get("ai_computational_sensing_and_co_design") or "").replace("\n", " ")
        rd_cmp = (s.get("estimated_rd_months_ai_vs_legacy") or "").replace("\n", " ")
        bom = (s.get("hardware_bom_localization_and_gtm_form") or "").replace("\n", " ")
        rows.append(
            f"| #{item['composite_rank']} | `{s['opp_id']}` | {s['track_id']} | {s['title']} | {cs_lbl} | "
            f"{gl_v} | {cn_v} | {ai_cs} | {rd_cmp} | {bom} |"
        )
    return header + "\n" + "\n".join(rows)


def _format_storm_digest_local(items: list[dict], sec: str | None = None) -> str:
    lines = []
    for item in items:
        s = item["seed"]
        if sec and s["sector"] != sec:
            continue
        memo = item.get("storm_memo") or {}
        p_txt = " ; ".join(
            f"{a['persona_role']}->{a['adoption_barrier']} (Spec-in: {a['spec_in_trigger']})"
            for a in memo.get("buyer_assessments", [])
        )
        lines.append(
            f"- `{s['opp_id']}` 最尖锐痛点: {memo.get('sharpest_pain_point_summary', '')} | "
            f"本土/出海护城河: {memo.get('key_localization_or_export_moat', '')} | 四方拷问: {p_txt}"
        )
    return "\n".join(lines)


roi_all_tbl = _format_post_elo_roi_table(shortlist)
roi_power_tbl = _format_post_elo_roi_table(shortlist, "power_energy")
roi_semi_tbl = _format_post_elo_roi_table(shortlist, "semiconductor")
comm_all_tbl = _format_post_elo_commercial_table(shortlist)
comm_power_tbl = _format_post_elo_commercial_table(shortlist, "power_energy")
comm_semi_tbl = _format_post_elo_commercial_table(shortlist, "semiconductor")
storm_all_txt = _format_storm_digest_local(shortlist)
storm_power_txt = _format_storm_digest_local(shortlist, "power_energy")
storm_semi_txt = _format_storm_digest_local(shortlist, "semiconductor")

elo_summary = "\n".join(
    f"- Round {m['round_idx']}: `{m['opp_a_id']}` vs `{m['opp_b_id']}` -> Winner `{m['winner_id']}` | {m['rationale']}"
    for m in elo_matches
)
power_track_labels = ", ".join(
    f"{d['track_id']}({d['track_name']})" for d in cleaned_dossiers if d.get("sector") == "power_energy"
) or "电力能源动态赛道"
semi_track_labels = ", ".join(
    f"{d['track_id']}({d['track_name']})" for d in cleaned_dossiers if d.get("sector") == "semiconductor"
) or "半导体制造动态赛道"
discovery_funnel_md = screened["discovery_funnel_md"]
dossiers_power_md = screened["formatted_dossiers"]["power_energy"]
dossiers_semi_md = screened["formatted_dossiers"]["semiconductor"]
vault_all_txt = screened["vault_snippets"]["all"]
vault_power_txt = screened["vault_snippets"]["power_energy"]
vault_semi_txt = screened["vault_snippets"]["semiconductor"]


# ---------------------------------------------------------------------------
# Stage 5: Parallel 5-Volume Grounded Report Synthesis (V3.0 Commercial + AI)
# ---------------------------------------------------------------------------

phase(f"5. Stage 5 5-Volume Grounded Report Synthesis (V3.0, Antigravity {target_model})")

SYSTEM_SYNTH_RULES = (
    "You are the Lead Industry Research Partner & Senior Metrology Instrument Architect authoring an authoritative V3.0 deliverable "
    "(McKinsey / SEMI / CICC engineering-practicality standard) in fluent, authoritative Simplified Chinese with English technical terms on first mention.\n"
    "NON-NEGOTIABLE GROUNDING RULES:\n"
    "1. Every market claim, vendor product/model, tender, policy, or standard MUST cite exact evidence IDs `[EV-CN-...]` / `[EV-GL-...]` from context.\n"
    "2. NEVER fabricate overseas or Chinese vendor company names or instrument model numbers; if none exist in EvidenceVault, state '尚未检索到量产在售整机（疑似空白）'.\n"
    "3. Every CAPEX, NetCF, 3-Scenario Payback (Optimistic/Baseline/Conservative), NPV, IRR MUST match the Python `[ROI-CALC]` tables verbatim.\n"
    "4. Every shortlisted opportunity MUST address (a) Overseas vs China commercial vendor white-space (`global_and_cn_commercialized`, `overseas_only_cn_blank`, `global_and_cn_true_blank`) "
    "and (b) AI-era HW/SW co-design (PINNs/computational sensing replacing hardware limits, synthetic defect cold-start, AI-assisted FPGA/EDA/host-SW compressing ~30-48m to ~10-18m, air-gapped Edge-AI + Golden-Tool calibration, BOM localization & GTM form).\n"
    "5. Mandatory order: CHINA FIRST -> GLOBAL SECOND; distinguish 3-5y (2027-2031) vs 5-10y (2031-2036).\n"
    "6. Return ONLY the complete Markdown volume text as a string."
)

volumes_spec = [
    (
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
        "Volume 00: Strategic Executive Summary, Vendor White-Space & AI Co-Design Panorama",
        f"""{SYSTEM_SYNTH_RULES}

Write **00. 电力能源与半导体芯片制造在线测试仪器仪表 V3.0 战略总报告：海内外在售产品空白图谱与 AI 时代软硬件协同新范式 (2026-2036)**.
Step-Back Thesis: {norm_plan.get('step_back_thesis', '')}

{discovery_funnel_md}

Post-Elo Deterministic [ROI-CALC] Master Table:
{roi_all_tbl}

Commercial Vendor Landscape & AI-Era Co-Design Master Matrix:
{comm_all_tbl}

STORM Buyer Committee Digest:
{storm_all_txt}

Evidence Snippets:
{vault_all_txt}

Required Sections:
1. 执行摘要与核心战略判断（从理论构想到商业在售图谱 + AI软硬件协同落脚点）
2. 动态发现赛道全景与【海内外在售 vs 国产空白 vs 全球空白】商业版图统计（拆解哪些赛道已成红海、哪些属于海外独占而国产空白、哪些是全球原创新空白）
3. AI 时代工业检测仪器研发与软硬件协同新范式总论（AI算力换硬件低成本BOM、合成缺陷样本冷启动、AI辅助FPGA/上位机将30-48月研发压缩至10-18月、离线产线边缘协同与闭环自校准）
4. 3-5年（2027-2031 国产替代与高ROI工程放量）vs 5-10年（2031-2036 全球前沿空白新物种）双时间窗对比表
5. Top 决选机会综合排位总表（完整保留三档 `[ROI-CALC]` 数据 + 商业空白级 + 海外/中国在售对照）与淘汰低ROI候选简评
6. 面向工业仪器创始人、研发VP与系统集成商的落地切入策略（OEM模块 vs 产线外挂改造 vs 整机ATE）。"""
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
        "Volume 01: Power & Energy Commercial Landscape & AI Co-Design Deep Analysis",
        f"""{SYSTEM_SYNTH_RULES}

Write **01. 电力能源行业动态发现赛道（{power_track_labels}）商业化空白研判与 AI 协同在线测试深度研报 (V3.0)**.
Power Deterministic [ROI-CALC] Table:
{roi_power_tbl}

Power Commercial Vendor & AI Co-Design Matrix:
{comm_power_tbl}

Power Track Dossiers:
{dossiers_power_md}

STORM Buyer Interrogation:
{storm_power_txt}

Power Evidence Snippets:
{vault_power_txt}

Cover EVERY Power track above in full depth:
- 第一节：中国市场产业痛点、十五五/双碳/新型电力系统与AIDC供配电刚需（`[EV-CN-...]`）
- 第二节：海内外商业化在售产品盘点与空白诊断（明确点名已检索到的国内/国际在售厂商与产品型号，严格区分红海升级 vs 国产空白 vs 全球空白）
- 第三节：3-5年 vs 5-10年技术与产品新机会（物理机理 + 三档 `[ROI-CALC]` + AI计算传感降本方案 + BOM国产化与切入形态）
- 第四节：产线与变电现场 AI 边缘协同、离线断网部署、四方买方阻力与 Spec-in 破局点。"""
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
        "Volume 02: Semiconductor Commercial Landscape & AI Co-Design Deep Analysis",
        f"""{SYSTEM_SYNTH_RULES}

Write **02. 半导体芯片制造行业动态发现赛道（{semi_track_labels}）海内外设备竞品对比与 AI 原位量检测深度研报 (V3.0)**.
Semiconductor Deterministic [ROI-CALC] Table:
{roi_semi_tbl}

Semiconductor Commercial Vendor & AI Co-Design Matrix:
{comm_semi_tbl}

Semiconductor Track Dossiers:
{dossiers_semi_md}

STORM Buyer Interrogation:
{storm_semi_txt}

Semiconductor Evidence Snippets:
{vault_semi_txt}

Cover EVERY Semiconductor track above in full depth:
- 第一节：中国晶圆厂/碳化硅功率产线/先进封装痛点与良率瓶颈（`[EV-CN-...]`）
- 第二节：海内外已售商用量检测设备全面盘点与真实产品空白定级（严禁编造型号，仅援引检索证据对比海外龙头与国产已商业化/空白环节）
- 第三节：AI 时代物理反演/虚拟量测/超分辨以算代硬破局（绕开卡脖子超高精度光机硬件，叠加合成缺陷冷启动与三档 `[ROI-CALC]`）
- 第四节：EFEM/机台原位集成、断网 NPU+FPGA 部署、BOM 替代与晶圆厂 Spec-in 破局方案。"""
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
        "Volume 03: PALMs ROI Model, White-Space Scoring Calibration & Elo Ranking",
        f"""{SYSTEM_SYNTH_RULES}

Write **03. 制造环节三情景 PALMs ROI 量化模型、商业空白加权校准、漏斗审计与 Elo 排位报告 (V3.0)**.
{discovery_funnel_md}

Master [ROI-CALC] Table:
{roi_all_tbl}

Commercial White-Space & AI Co-Design Summary:
{comm_all_tbl}

Pairwise Elo Match Log:
{elo_summary}

STORM CFO & Procurement Findings:
{storm_all_txt}

Required Sections:
1. 三情景区间 ROI + 商业空白度与 AI 软硬件协同评分校准模型（说明为何 `海外在售·国产空白` 与 `海内外空白+AI以算代硬` 获得结构性溢价，而纯红海在售方向被扣分警示）
2. 入围机会三档 `[ROI-CALC]` 财务全景与商业化/AI研发周期压缩对IRR与现金流的敏感性影响
3. Stage 2 漏斗淘汰审计（含淘汰候选商业空白级对照）
4. AI Co-Scientist Elo 锦标赛排位解析与两套客户 CFO/总工一页纸算账模板。"""
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
        "Volume 04: AI-Era Hardware/Software Co-Design & Commercial GTM Playbook",
        f"""{SYSTEM_SYNTH_RULES}

Write **04. AI 时代智能检测仪器软硬件协同研发、供应链国产化与商业化落地执行手册 (V3.0 Playbook)**.
Master Ranking:
{roi_all_tbl}

Commercial White-Space & AI Co-Design Matrix:
{comm_all_tbl}

Dossiers Summary:
{dossiers_power_md[:4200]}

{dossiers_semi_md[:4200]}

STORM Engineering Tweaks:
{storm_all_txt}

Required Sections:
1. **传统仪器研发范式 (30-48个月) vs AI 时代软硬件协同新范式 (10-18个月) 全流程对照表**（涵盖：物理PINN/多物理场代理建模 -> 合成缺陷Zero/Few-shot冷启动 -> AI辅助FPGA/EDA/上位机代码生成 -> 产线断网FPGA+NPU边缘推理与Golden-Tool在线自校准）
2. **以算代硬（AI 计算传感 / 反演 / 超分辨）绕开核心硬件卡脖子与降 BOM 清单实战指南**
3. **三类商业战场差异化 GTM 打法**（①海内外在售红海的 AI 升级差异化策略；②海外在售·国产空白的标杆产线 Golden-Tool 对标平替策略；③海内外空白原创新物种的联合体首台套协同落地策略）
4. **核心传感元器件 BOM 国产化替代路线图与未来 3-5 年/5-10 年研发立项里程碑**。"""
        + NO_TOOL_DIRECTIVE,
    ),
]

synth_texts = await parallel(
    volumes_spec,
    lambda spec: agent(
        role=spec[1],
        model=target_model,
        schema={"type": "string"},
        prompt=spec[2],
    ),
)
volumes = {spec[0]: str(txt).strip() for spec, txt in zip(volumes_spec, synth_texts)}


# ---------------------------------------------------------------------------
# Stage 6: Bounded Heterogeneous Critic Reflection Loop with Corrective RAG
# ---------------------------------------------------------------------------

phase(f"6. Stage 6 Bounded Heterogeneous Critic Loop (V3.0, max_loops={max_loops})")


def _previews_and_checks() -> tuple[str, dict]:
    ev_cited = set()
    roi_cnt = 0
    combined = "\n".join(volumes.values())
    for content in volumes.values():
        ev_cited.update(re.findall(r"EV-(?:CN|GL)-\d{3,4}", content))
        roi_cnt += content.count("[ROI-CALC]")
    ws_counts: dict[str, int] = {}
    for ev_item in shortlist:
        k = ev_item.get("seed", {}).get("commercial_status", "overseas_only_cn_blank")
        ws_counts[k] = ws_counts.get(k, 0) + 1
    det_summary = {
        "vault_total": vstats.get("total", 0),
        "vault_cn": vstats.get("cn_count", 0),
        "vault_global": vstats.get("global_count", 0),
        "tracks_discovered": [tp["track_id"] for tp in norm_plan.get("track_plans", [])],
        "funnel_raw": screened["raw_candidates_count"],
        "funnel_shortlist": len(shortlist),
        "funnel_eliminated": len(eliminated),
        "commercial_whitespace_breakdown": ws_counts,
        "distinct_ev_ids_cited": len(ev_cited),
        "roi_calc_tags": roi_cnt,
        "has_commercial_whitespace_terms": any(w in combined for w in ("在售", "空白", "海外在售")),
        "has_ai_codesign_terms": any(w in combined for w in ("计算传感", "软硬件协同", "FPGA", "PINN", "合成缺陷")),
        "volume_lengths": {k: len(v) for k, v in volumes.items()},
    }
    previews = "\n\n".join(
        f"=== {k} ({len(v)} chars) ===\n{v[:2200]}\n...[tail]...\n{v[-800:]}"
        for k, v in sorted(volumes.items())
    )
    return previews, det_summary


critique_history: list[dict] = []
revisions_run = 0
extra_gap_snippets = ""

for loop_idx in range(max_loops):
    previews, det_summary = _previews_and_checks()
    critic = await agent(
        role=f"Heterogeneous Chief Reviewer (V3 Loop {loop_idx + 1})",
        model=target_model,
        schema=CRITIC_SCHEMA,
        prompt=(
            "You are an unforgiving Heterogeneous Chief Reviewer auditing all 5 synthesized V3.0 volumes:\n"
            "- China FIRST -> Global SECOND; strict 3-5y vs 5-10y separation\n"
            "- Grounded COMMERCIAL LANDSCAPE: explicit overseas vs Chinese in-market vendors/models citing `[EV-...]` (no fabricated models, honest blank identification)\n"
            "- AI-ERA HW/SW CO-DESIGN DEPTH: PINN/computational sensing replacing hardware limits, synthetic defect cold-start, AI FPGA/EDA compression (10-18m vs 30-48m), air-gapped Edge-AI + BOM localization\n"
            "- All Stage 0 dynamically discovered tracks, Stage 2 funnel elimination audit, and exact 3-scenario `[ROI-CALC]` tables faithfully reflected.\n\n"
            f"Deterministic Telemetry:\n{json.dumps(det_summary, ensure_ascii=False)}\n\n"
            f"Draft Excerpts:\n{previews}\n\n"
            'Return `decision` in ["pass", "needs_more_evidence", "needs_rewrite"], `overall_confidence` (0-100), '
            "`summary`, `issues`, and `gap_queries` (non-empty only when `needs_more_evidence`)."
            + NO_TOOL_DIRECTIVE
        ),
    )
    critique_history.append(critic)
    decision = str(critic.get("decision", "pass"))
    if decision == "pass":
        break

    if decision == "needs_more_evidence" and critic.get("gap_queries"):
        gap_q_path = BASE_DIR / "data/v3_gap_queries.json"
        gap_out_path = BASE_DIR / "data/v3_gap_refill.json"
        gap_q_path.write_text(json.dumps(critic["gap_queries"][:4], ensure_ascii=False, indent=2), encoding="utf-8")
        _run_cli(
            [
                "gap-search",
                "--queries-json",
                str(gap_q_path),
                "--vault-db",
                vault_db,
                "--output",
                str(gap_out_path),
            ]
        )
        gap_res = json.loads(gap_out_path.read_text(encoding="utf-8"))
        vstats = dict(gap_res.get("vault_stats", vstats))
        if gap_res.get("formatted_snippets"):
            extra_gap_snippets += "\n" + gap_res["formatted_snippets"]

    flagged_prefixes = {str(i.get("section", ""))[:2] for i in critic.get("issues", [])}
    to_revise = [s for s in volumes_spec if s[0][:2] in flagged_prefixes] or volumes_spec[:2]
    issues_txt = "\n".join(
        f"- [{i['severity']}] ({i['section']}): {i['description']}"
        for i in critic.get("issues", [])
    )
    revised_texts = await parallel(
        to_revise,
        lambda spec: agent(
            role=f"Reviser L{loop_idx + 1} {spec[0][:2]}",
            model=target_model,
            schema={"type": "string"},
            prompt=(
                f"Revise `{spec[0]}` to fix EVERY Reviewer critique below while keeping all `[EV-...]` citations, "
                f"commercial vendor white-space tables, AI HW/SW co-design specs, and Python 3-scenario `[ROI-CALC]` numbers exact.\n\n"
                f"Critic Issues:\n{issues_txt}\n\n"
                + (f"Newly Added Refill Evidence:\n{extra_gap_snippets}\n\n" if extra_gap_snippets else "")
                + f"Current Draft:\n{volumes[spec[0]]}"
                + NO_TOOL_DIRECTIVE
            ),
        ),
    )
    for spec, rev_txt in zip(to_revise, revised_texts):
        volumes[spec[0]] = str(rev_txt).strip()
        revisions_run += 1


# ---------------------------------------------------------------------------
# Stage 7: Independent Stage-Gate Judge & Deterministic Finalization
# ---------------------------------------------------------------------------

phase("7. Stage 7 Independent Stage-Gate Judge & Deterministic Finalization (V3.0)")
previews, det_summary = _previews_and_checks()
judge = await agent(
    role="Stage-Gate Quality Judge (V3.0)",
    model=target_model,
    schema=JUDGE_SCHEMA,
    prompt=(
        "You are an independent Stage-Gate Quality Auditor (Ch 19 LLM-as-a-Judge). Score the V3.0 deliverables "
        "rigorously from 0 to 20 on each of the 5 criteria (total 100):\n"
        "1. `china_first_then_global_depth` (0-20) — China-first priority + overseas/China commercial vendor & blank accuracy\n"
        "2. `dual_horizon_3_5y_vs_5_10y_rigor` (0-20) — 3-5y commercialization vs 5-10y white-space paradigm differentiation\n"
        "3. `pain_point_and_physics_specificity` (0-20) — Physics precision + AI-era HW/SW co-design (PINN, synthetic defect, FPGA/NPU Edge-AI, BOM)\n"
        "4. `roi_and_industrial_upgrade_value` (0-20) — Deterministic 3-scenario `[ROI-CALC]` fidelity + R&D cycle compression + GTM viability\n"
        "5. `citation_grounding_and_prose` (0-20) — Authentic `[EV-CN-...]`/`[EV-GL-...]` grounding with zero fabricated models\n\n"
        f"Deterministic Summary:\n{json.dumps(det_summary, ensure_ascii=False)}\n\n"
        f"Last Critic Summary: {critique_history[-1].get('summary', '') if critique_history else ''}\n\n"
        f"Deliverable Excerpts:\n{previews}\n\n"
        "Return exact scores, `total_score`, concise Chinese `executive_verdict`, `strengths`, and `residual_risks`."
        + NO_TOOL_DIRECTIVE
    ),
)

out_bundle = BASE_DIR / "data/v3_native_outputs_bundle.json"
bundle_payload = {
    "run_id": run_id,
    "sector_filter": sector,
    "profile": profile,
    "llm_engine": f"antigravity_native:{target_model}",
    "discovery_plan": norm_plan,
    "dossiers": cleaned_dossiers,
    "raw_candidates_count": screened["raw_candidates_count"],
    "shortlist": shortlist,
    "eliminated_candidates": eliminated,
    "storm_memos": storm_memos,
    "elo_matches": elo_matches,
    "volumes": volumes,
    "critique_loops_executed": len(critique_history) - (1 if critique_history and critique_history[-1].get("decision") == "pass" else 0),
    "critique_history": critique_history,
    "judge_rubric": judge,
    "native_agent_invocations": {
        "stage0_discovery_architect": 1,
        "stage1_zero_seed_track_miners": len(tracks_ctx["tracks"]),
        "stage3_storm_panels": len(shortlist),
        "stage4_elo_pairwise_matches": len(elo_matches),
        "stage5_volume_synthesizers": len(volumes_spec),
        "stage6_heterogeneous_critic": len(critique_history),
        "stage6_targeted_revisions": revisions_run,
        "stage7_stage_gate_judge": 1,
    },
}
out_bundle.write_text(json.dumps(bundle_payload, ensure_ascii=False, indent=2), encoding="utf-8")

_run_cli(
    [
        "finalize-v3",
        "--bundle",
        str(out_bundle),
        "--vault-db",
        vault_db,
        "--output-dir",
        output_dir,
    ]
)

print(
    json.dumps(
        {
            "run_id": run_id,
            "llm_engine": f"antigravity_native:{target_model}",
            "output_dir": str(BASE_DIR / output_dir),
            "tracks_discovered": len(norm_plan.get("track_plans", [])),
            "raw_candidates": screened["raw_candidates_count"],
            "shortlist_kept": len(shortlist),
            "eliminated": len(eliminated),
            "commercial_whitespace_breakdown": det_summary.get("commercial_whitespace_breakdown", {}),
            "evidences": vstats.get("total"),
            "judge_score": judge.get("total_score"),
            "revisions": revisions_run,
        },
        ensure_ascii=False,
    )
)
