"""Antigravity IDE Native Hybrid Workflow (`run_workflow`) for V&F IMR-MS China CCS/CCUS Strategy.

Executes the 8-Stage Agentic Design Patterns pipeline combining:
- Native Antigravity frontier subagent reasoning (`pro` for planning/STORM/synthesis, `flash` for fast mining, independent critic)
- Deterministic Python CLI spine (`vf-ccus-research`) for Siggi MCP ingestion, Metaso/Serper SQLite Vault,
  bottom-up [MKT-CALC] market sizing, 3-scenario [ROI-CALC] payback funnel, zero-LLM Vol 05, and Vol 06 scorecard.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/CCS_projects _China/marketing_research_dev_agentic_workflow/agentic_workflow")
VENV_CLI = BASE_DIR / ".venv/bin/vf-ccus-research"

_user_args = args if "args" in globals() and isinstance(args, dict) else {}
profile = str(_user_args.get("profile", "flagship"))
output_dir = str(_user_args.get("output_dir", "../research_outputs"))
vault_db = str(_user_args.get("vault_db", "data/vf_ccus_evidence_vault.db"))
target_model = str(_user_args.get("model", "pro"))
run_id = f"vf-native-{uuid.uuid4().hex[:8]}"
max_loops = 2 if profile == "flagship" else 1

NO_TOOL_DIRECTIVE = (
    "\n\nCRITICAL DIRECTIVE: All verified EvidenceVault excerpts ([EV-SIGGI-*], [EV-CN-*], [EV-GL-*]) "
    "and deterministic Python [MKT-CALC] / [ROI-CALC] metrics are ALREADY injected into this prompt. "
    "Do NOT call any filesystem, shell, search, or browser tools. Complete your analysis in one single turn "
    "and return ONLY valid JSON via `finish` matching the schema."
)


def _run_cli(cli_args: list[str]) -> str:
    proc = subprocess.run(
        [str(VENV_CLI), *cli_args],
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
# Strict Flat JSON Schemas (ZERO $ref / ZERO $defs for run_workflow `agent()`)
# ---------------------------------------------------------------------------

SECTORS_ENUM = [
    "S1_pipeline_ship_eor",
    "S2_green_methanol_ccu_chem",
    "S3_capture_rd_industry",
    "S4_food_beverage_dryice",
]
TRACKS_ENUM = [
    "TRACK_A_IMPORTED_CORE",
    "TRACK_B_LOCALIZED_QAS",
    "TRACK_C_AUSTRIA_PREMIERGUARD",
]
HORIZONS_ENUM = ["2026-2030", "2031-2036"]

DISCOVERY_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "contract_id": {"type": "string"},
        "profile": {"type": "string"},
        "macro_recon_summary": {"type": "string"},
        "step_back_thesis": {"type": "string"},
        "track_plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                    "sector": {"type": "string", "enum": SECTORS_ENUM},
                    "name": {"type": "string"},
                    "research_hypothesis": {"type": "string"},
                    "cn_queries": {"type": "array", "items": {"type": "string"}},
                    "global_queries": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "integer"},
                },
                "required": [
                    "track_id",
                    "sector",
                    "name",
                    "research_hypothesis",
                    "cn_queries",
                    "global_queries",
                    "priority",
                ],
            },
        },
    },
    "required": ["contract_id", "profile", "macro_recon_summary", "step_back_thesis", "track_plans"],
}

TRACK_DOSSIER_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "string"},
        "sector": {"type": "string", "enum": SECTORS_ENUM},
        "track_name": {"type": "string"},
        "key_findings_summary": {"type": "string"},
        "named_projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "owner_and_epc": {"type": "string"},
                    "province_or_region": {"type": "string"},
                    "sector": {"type": "string", "enum": SECTORS_ENUM},
                    "capacity_mtpa_or_scale": {"type": "string"},
                    "status_2026": {"type": "string"},
                    "co2_impurity_profile_and_risk": {"type": "string"},
                    "recommended_delivery_track": {"type": "string", "enum": TRACKS_ENUM},
                    "estimated_analyzer_stations": {"type": "integer"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "project_name",
                    "owner_and_epc",
                    "province_or_region",
                    "sector",
                    "capacity_mtpa_or_scale",
                    "status_2026",
                    "co2_impurity_profile_and_risk",
                    "recommended_delivery_track",
                    "estimated_analyzer_stations",
                    "evidence_ids",
                ],
            },
        },
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vendor_name": {"type": "string"},
                    "origin_category": {
                        "type": "string",
                        "enum": [
                            "Overseas_Process_MS",
                            "Overseas_FTIR_Optical_GC",
                            "Domestic_MS_Vendor",
                            "Domestic_PAC_System_Integrator",
                        ],
                    },
                    "verified_models_and_tech": {"type": "string"},
                    "detectable_species_and_speed": {"type": "string"},
                    "blind_spots_vs_vf_imr_ms": {"type": "string"},
                    "china_ccus_presence_and_pricing_position": {"type": "string"},
                    "win_strategy_for_vf": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "vendor_name",
                    "origin_category",
                    "verified_models_and_tech",
                    "detectable_species_and_speed",
                    "blind_spots_vs_vf_imr_ms",
                    "china_ccus_presence_and_pricing_position",
                    "win_strategy_for_vf",
                    "evidence_ids",
                ],
            },
        },
        "sizing_inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "enum": SECTORS_ENUM},
                    "horizon": {"type": "string", "enum": HORIZONS_ENUM},
                    "addressable_project_or_line_count": {"type": "integer"},
                    "stations_per_project": {"type": "number"},
                    "primary_delivery_track": {"type": "string", "enum": TRACKS_ENUM},
                    "technical_fit_ratio": {"type": "number"},
                    "realistic_som_win_rate": {"type": "number"},
                    "driver_notes": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "sector",
                    "horizon",
                    "addressable_project_or_line_count",
                    "stations_per_project",
                    "primary_delivery_track",
                    "technical_fit_ratio",
                    "realistic_som_win_rate",
                    "driver_notes",
                    "evidence_ids",
                ],
            },
        },
        "wedges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wedge_id": {"type": "string"},
                    "track_id": {"type": "string"},
                    "sector": {"type": "string", "enum": SECTORS_ENUM},
                    "horizon": {"type": "string", "enum": HORIZONS_ENUM},
                    "delivery_track": {"type": "string", "enum": TRACKS_ENUM},
                    "title": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "enum": ["GO_HIGH_PRIORITY", "GO_CONDITIONAL", "DEPRIORITIZE_OR_PSEUDO_DEMAND"],
                    },
                    "china_priority_score": {"type": "number"},
                    "vf_moat_score": {"type": "number"},
                    "target_process_point": {"type": "string"},
                    "chemical_pain_point_and_imr_advantage": {"type": "string"},
                    "recommended_vf_sku_and_localization": {"type": "string"},
                    "key_competing_alternatives": {"type": "string"},
                    "named_china_benchmark_customers": {"type": "array", "items": {"type": "string"}},
                    "siggi_reference_proof": {"type": "string"},
                    "roi_baseline": {
                        "type": "object",
                        "properties": {
                            "capex_cny": {"type": "number"},
                            "avoided_corrosion_and_shutdown_loss_cny_yr": {"type": "number"},
                            "avoided_catalyst_poison_or_flaring_cny_yr": {"type": "number"},
                            "avoided_manual_lab_and_multi_gc_opex_cny_yr": {"type": "number"},
                            "ccer_or_export_compliance_upside_cny_yr": {"type": "number"},
                            "annual_opex_cny_yr": {"type": "number"},
                        },
                        "required": [
                            "capex_cny",
                            "avoided_corrosion_and_shutdown_loss_cny_yr",
                            "avoided_catalyst_poison_or_flaring_cny_yr",
                            "avoided_manual_lab_and_multi_gc_opex_cny_yr",
                            "ccer_or_export_compliance_upside_cny_yr",
                            "annual_opex_cny_yr",
                        ],
                    },
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "wedge_id",
                    "track_id",
                    "sector",
                    "horizon",
                    "delivery_track",
                    "title",
                    "verdict",
                    "china_priority_score",
                    "vf_moat_score",
                    "target_process_point",
                    "chemical_pain_point_and_imr_advantage",
                    "recommended_vf_sku_and_localization",
                    "key_competing_alternatives",
                    "named_china_benchmark_customers",
                    "siggi_reference_proof",
                    "roi_baseline",
                    "evidence_ids",
                ],
            },
        },
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "track_id",
        "sector",
        "track_name",
        "key_findings_summary",
        "named_projects",
        "competitors",
        "sizing_inputs",
        "wedges",
        "evidence_ids",
    ],
}

STORM_MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "wedge_id": {"type": "string"},
        "persona_critiques": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "persona_role": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["STRONG_BUY", "CONDITIONAL_试点", "REJECT_OR_WAIT"]},
                    "primary_concern": {"type": "string"},
                    "procurement_or_spec_barrier": {"type": "string"},
                    "vf_winning_hook": {"type": "string"},
                },
                "required": ["persona_role", "verdict", "primary_concern", "procurement_or_spec_barrier", "vf_winning_hook"],
            },
        },
        "consensus_gtm_implication": {"type": "string"},
    },
    "required": ["wedge_id", "persona_critiques", "consensus_gtm_implication"],
}

ELO_PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "winner_id": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["winner_id", "rationale"],
}

VOLUME_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "markdown": {"type": "string"},
    },
    "required": ["markdown"],
}

CRITIC_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "overall_assessment": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "volume_name": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "description": {"type": "string"},
                    "required_fix_action": {"type": "string"},
                    "needs_crag_gap_search": {"type": "boolean"},
                    "suggested_query": {"type": "string"},
                    "suggested_geo_scope": {"type": "string", "enum": ["CN", "GLOBAL"]},
                },
                "required": [
                    "volume_name",
                    "severity",
                    "description",
                    "required_fix_action",
                    "needs_crag_gap_search",
                    "suggested_query",
                    "suggested_geo_scope",
                ],
            },
        },
        "volumes_to_rewrite": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["passed", "overall_assessment", "issues", "volumes_to_rewrite"],
}

JUDGE_RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {
        "china_grounding_and_project_specificity": {"type": "number"},
        "market_sizing_and_pain_point_rigor": {"type": "number"},
        "competitive_battlecard_accuracy": {"type": "number"},
        "dual_track_gtm_and_roi_actionability": {"type": "number"},
        "evidence_traceability_and_prose": {"type": "number"},
        "total_score": {"type": "number"},
        "pass_stage_gate": {"type": "boolean"},
        "executive_commentary": {"type": "string"},
    },
    "required": [
        "china_grounding_and_project_specificity",
        "market_sizing_and_pain_point_rigor",
        "competitive_battlecard_accuracy",
        "dual_track_gtm_and_roi_actionability",
        "evidence_traceability_and_prose",
        "total_score",
        "pass_stage_gate",
        "executive_commentary",
    ],
}


# ---------------------------------------------------------------------------
# Stage 0a & 0b: Siggi Primary Corpus + Live Macro Recon -> DiscoveryPlan
# ---------------------------------------------------------------------------
phase("Stage 0a/0b: Siggi Corpus Ingestion, Macro Recon & Discovery Planner")
recon_file = BASE_DIR / "data/stage0_recon_bundle.json"
_run_cli(
    [
        "recon-search",
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-file",
        str(recon_file),
    ]
)
recon_bundle = json.loads(recon_file.read_text(encoding="utf-8"))
log(f"Stage 0a vault_stats: {recon_bundle['vault_stats']}")

plan_prompt = (
    "You are the Chief CCUS Market Intelligence Architect (Phase 0b Step-Back Planner).\n"
    "Synthesize V&F Austria Siggi primary materials ([EV-SIGGI-*]) and live China/Global macro recon ([EV-CN-*], [EV-GL-*]) "
    "to design 6 emergent research tracks for V&F IMR-MS (CO2Sense / PremierGuard CCUS QAS) in China.\n\n"
    "MANDATORY TRACK STRUCTURE:\n"
    "1. T1_EOR_PIPE (S1_pipeline_ship_eor): 中国百万吨级超临界CO2管道/油田EOR强腐蚀链式反应监控与三桶油项目\n"
    "2. T2_LCO2_SHIP (S1_pipeline_ship_eor): 中国船厂LCO2运输船出口建造与沿海/海上CCUS接收外输枢纽(对标Northern Lights)\n"
    "3. T3_GREEN_MEOH (S2_green_methanol_ccu_chem): 绿氢+CO2合成绿色甲醇/e-SAF催化剂防硫氨中毒实时保护\n"
    "4. T4_AMINE_RD (S3_capture_rd_industry): 燃煤/水泥/钢铁/垃圾焚烧胺法捕集逃逸与科研院所/设计院中试平台\n"
    "5. T5_COMP_PAC (S1_pipeline_ship_eor): 中国过程质谱/Thermo FTIR/ABB-Siemens光学GC/国产质谱与GB/T 3836防爆分析小屋集成生态\n"
    "6. T6_FOOD_CTRL (S4_food_beverage_dryice): 中国食品饮料级/干冰级CO2市场低支付意愿负向对照验证\n\n"
    "Generate sharp Simplified Chinese Metaso `cn_queries` (3-5 per track) and English Serper `global_queries` (1-3 per track).\n"
    f"Contract ID: VF-CCUS-CHINA-2026-V1 | Profile: {profile}\n\n"
    f"=== SIGGI PRIMARY CORPUS ([EV-SIGGI-*]) ===\n{recon_bundle['siggi_context_text']}\n\n"
    f"=== LIVE MACRO RECON ([EV-CN-*] / [EV-GL-*]) ===\n{recon_bundle['recon_context_text']}"
    + NO_TOOL_DIRECTIVE
)

plan_res = await agent(
    prompt=plan_prompt,
    schema=DISCOVERY_PLAN_SCHEMA,
    role="Stage 0b Discovery Architect",
    model=target_model,
)
plan_file = BASE_DIR / "data/stage0_discovery_plan.json"
plan_file.write_text(json.dumps(plan_res, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 1: Parallel Search + Parallel Track Mining
# ---------------------------------------------------------------------------
phase("Stage 1: Multi-Engine Deep Track Search & Evidence Mining")
track_ev_file = BASE_DIR / "data/stage1_track_evidence.json"
_run_cli(
    [
        "track-search",
        "--plan-file",
        str(plan_file),
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-file",
        str(track_ev_file),
    ]
)
track_payload = json.loads(track_ev_file.read_text(encoding="utf-8"))
all_valid_ev_ids = set(track_payload.get("all_valid_ev_ids", []))
scope_yaml = recon_bundle["discovery_scope"]

async def _mine_one_track(t_item: dict) -> dict:
    tp = t_item["track"]
    prompt = (
        f"You are a Principal CCUS & Analytical Instrumentation Analyst mining track `{tp['track_id']}` ({tp['name']}).\n"
        f"Sector: `{tp['sector']}`\n"
        f"Hypothesis: {tp['research_hypothesis']}\n\n"
        "RULES:\n"
        "1. STRICT ZERO FABRICATION: Every project, competitor model, and standard MUST appear in the Evidence Excerpts below and cite ONLY valid `[EV-SIGGI-*]` / `[EV-CN-*]` / `[EV-GL-*]` IDs present below.\n"
        "2. DUAL-TRACK PRICING MODEL (CNY):\n"
        "   - `TRACK_A_IMPORTED_CORE`: 进口CO2Sense/AirSense主机 (¥140-220万, 基准180万, 科研/中试/专利商)\n"
        "   - `TRACK_B_LOCALIZED_QAS`: 双轨本土化防爆小屋VF-QAS-CN (¥320-550万, 基准420万, 三桶油/管道/绿醇/大型工厂)\n"
        "   - `TRACK_C_AUSTRIA_PREMIERGUARD`: 奥地利原装PremierGuard QAS (¥580-950万, 基准720万, 外资沿海枢纽/出口LCO2船)\n"
        f"3. SECTOR ROI GUARDRAILS ({tp['sector']}): {json.dumps(scope_yaml['wedge_roi_guardrails'].get(tp['sector'], {}), ensure_ascii=False)}\n"
        "4. HONEST SIZING & PSEUDO-DEMAND CHECK:\n"
        "   - Provide bottom-up `SegmentSizingInput` for BOTH `2026-2030` and `2031-2036` where applicable to this sector (for `T6_FOOD_CTRL`, reflect low realistic win rate and mark food routine offline GC displacement as `DEPRIORITIZE_OR_PSEUDO_DEMAND` with modest avoided benefits so Stage 2 funnel honestly evaluates/eliminates it).\n"
        "   - Extract 2 to 4 concrete `CommercialWedgeCandidate`s.\n\n"
        f"=== VERIFIED EVIDENCE EXCERPTS ===\n{t_item['evidence_context']}"
        + NO_TOOL_DIRECTIVE
    )
    return await agent(
        prompt=prompt,
        schema=TRACK_DOSSIER_SCHEMA,
        role=f"Track Miner ({tp['track_id']})",
        model=target_model,
    )

mined_dossiers = await parallel(track_payload["tracks"], _mine_one_track)
dossiers_file = BASE_DIR / "data/stage1_track_dossiers.json"
dossiers_file.write_text(json.dumps({"dossiers": mined_dossiers}, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 2: Deterministic Python [MKT-CALC] Sizing + [ROI-CALC] Funnel Screening
# ---------------------------------------------------------------------------
phase("Stage 2: Deterministic Python [MKT-CALC] & [ROI-CALC] Funnel")
screened_file = BASE_DIR / "data/stage2_screened_pool.json"
_run_cli(
    [
        "screen-and-size",
        "--dossiers-file",
        str(dossiers_file),
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-file",
        str(screened_file),
    ]
)
screened = json.loads(screened_file.read_text(encoding="utf-8"))
shortlist = screened["shortlist"]
log(f"Stage 2 Funnel: shortlist={len(shortlist)}, eliminated={len(screened['eliminated'])}, projects={len(screened['projects'])}, competitors={len(screened['competitors'])}")


# ---------------------------------------------------------------------------
# Stage 3: 4-Persona Chinese CCS Buyer STORM Interrogation
# ---------------------------------------------------------------------------
phase("Stage 3: 4-Persona China CCS Buyer Committee STORM Interrogation")
REQUIRED_PERSONAS = [
    "三大油/央企CCUS工程公司工艺与压缩防腐总工",
    "设计院(SEI/HQC/CPECC/天辰)分析仪表室主任与EPC包采经理",
    "煤化工/水泥/绿醇项目业主EHS、碳核查与财务ROI决策人",
    "大型CCUS分析小屋集成商与运维总包负责人",
]

async def _storm_one(ev_item: dict) -> dict:
    s = ev_item["seed"]
    r = ev_item["roi"]
    cons = (ev_item.get("roi_range") or {}).get("conservative") or r
    prompt = (
        f"Stress-test this shortlisted V&F IMR-MS wedge from ALL 4 Chinese buyer committee perspectives:\n"
        f"- Wedge ID: {s['wedge_id']} | Title: {s['title']}\n"
        f"- Sector: {s['sector']} | Horizon: {s['horizon']} | Delivery Track: {s['delivery_track']}\n"
        f"- Recommended Config: {s['recommended_vf_sku_and_localization']}\n"
        f"- Pain Point & Physics: {s['chemical_pain_point_and_imr_advantage']}\n"
        f"- Competing Alternatives: {s['key_competing_alternatives']}\n"
        f"- Named CN Customers: {', '.join(s.get('named_china_benchmark_customers', []))}\n"
        f"- [ROI-CALC] Baseline CAPEX=¥{r['capex_cny']/10000:.1f}万, NetCF=¥{r['net_annual_cashflow_cny']/10000:.1f}万/年, "
        f"Payback={r['payback_months']}月, IRR={r['irr_5yr_pct']}%, NPV=¥{r['npv_5yr_cny']/10000:.1f}万 | "
        f"Conservative Payback={cons['payback_months']}月\n\n"
        f"You MUST include all 4 exact `persona_role` values:\n"
        + "\n".join(f"- {p}" for p in REQUIRED_PERSONAS)
        + NO_TOOL_DIRECTIVE
    )
    memo = await agent(
        prompt=prompt,
        schema=STORM_MEMO_SCHEMA,
        role=f"STORM Panel ({s['wedge_id']})",
        model="flash",
    )
    memo["wedge_id"] = s["wedge_id"]
    return memo

storm_results = await parallel(shortlist, _storm_one)
storm_memos = {m["wedge_id"]: m for m in storm_results}


# ---------------------------------------------------------------------------
# Stage 4: 2-Round Swiss-System Pairwise Elo Tournament
# ---------------------------------------------------------------------------
phase("Stage 4: Swiss-System Pairwise Elo Tournament")

def _expected(a: float, b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((b - a) / 400.0))

for ev_item in shortlist:
    ev_item["elo_rating"] = round(1500.0 + (ev_item["weighted_pillar_score"] - 75.0) * 4.0, 2)

rounds = 2 if profile == "flagship" else 1
elo_matches: list[dict] = []

for r_idx in range(1, rounds + 1):
    shortlist.sort(key=lambda x: x["elo_rating"], reverse=True)
    pairs = [(shortlist[i], shortlist[i + 1]) for i in range(0, len(shortlist) - 1, 2)]

    async def _judge_pair(pair: tuple[dict, dict]) -> dict:
        a, b = pair
        sa, sb = a["seed"], b["seed"]
        ra, rb = a["roi"], b["roi"]
        prompt = (
            f"Round {r_idx} Pairwise Commercial Priority Duel:\n\n"
            f"[Option A: {sa['wedge_id']}] {sa['title']}\n"
            f"Track={sa['delivery_track']} | Priority={sa['china_priority_score']} | Moat={sa['vf_moat_score']} | Pillar={a['weighted_pillar_score']}\n"
            f"Pain Point: {sa['chemical_pain_point_and_imr_advantage']}\n"
            f"[ROI-CALC] CAPEX=¥{ra['capex_cny']/10000:.1f}万, Payback={ra['payback_months']}m, IRR={ra['irr_5yr_pct']}%\n\n"
            f"[Option B: {sb['wedge_id']}] {sb['title']}\n"
            f"Track={sb['delivery_track']} | Priority={sb['china_priority_score']} | Moat={sb['vf_moat_score']} | Pillar={b['weighted_pillar_score']}\n"
            f"Pain Point: {sb['chemical_pain_point_and_imr_advantage']}\n"
            f"[ROI-CALC] CAPEX=¥{rb['capex_cny']/10000:.1f}万, Payback={rb['payback_months']}m, IRR={rb['irr_5yr_pct']}%\n\n"
            f'Select `winner_id` as strictly "{sa["wedge_id"]}" or "{sb["wedge_id"]}" based on IMR-MS physical necessity, ROI resilience, and 2026-2030 China signing probability.'
            + NO_TOOL_DIRECTIVE
        )
        dec = await agent(
            prompt=prompt,
            schema=ELO_PAIR_SCHEMA,
            role=f"Elo Judge R{r_idx}",
            model="flash",
        )
        return {"a_id": sa["wedge_id"], "b_id": sb["wedge_id"], "dec": dec}

    outcomes = await parallel(pairs, _judge_pair)
    by_wid = {x["seed"]["wedge_id"]: x for x in shortlist}
    for o in outcomes:
        oa, ob = by_wid[o["a_id"]], by_wid[o["b_id"]]
        a_won = str(o["dec"]["winner_id"]).strip() != ob["seed"]["wedge_id"]
        exp_a = _expected(oa["elo_rating"], ob["elo_rating"])
        sa_pts, sb_pts = (1.0, 0.0) if a_won else (0.0, 1.0)
        oa["elo_rating"] = round(oa["elo_rating"] + 32.0 * (sa_pts - exp_a), 2)
        ob["elo_rating"] = round(ob["elo_rating"] + 32.0 * (sb_pts - (1.0 - exp_a)), 2)
        elo_matches.append(
            {
                "round_idx": r_idx,
                "wedge_a_id": o["a_id"],
                "wedge_b_id": o["b_id"],
                "winner_id": o["a_id"] if a_won else o["b_id"],
                "rationale": o["dec"]["rationale"],
                "elo_a_after": oa["elo_rating"],
                "elo_b_after": ob["elo_rating"],
            }
        )

elos = [x["elo_rating"] for x in shortlist] or [1500.0]
lo_e, hi_e = min(elos), max(elos)
span_e = max(1.0, hi_e - lo_e)
shortlist.sort(
    key=lambda e: 0.55 * e["weighted_pillar_score"] + 0.45 * (60.0 + ((e["elo_rating"] - lo_e) / span_e) * 38.0),
    reverse=True,
)
for r_idx, item in enumerate(shortlist, start=1):
    item["composite_rank"] = r_idx


# ---------------------------------------------------------------------------
# Stage 5: Parallel Grounded Synthesis of the 5 Core Volumes (00_..04_)
# ---------------------------------------------------------------------------
phase("Stage 5: Parallel Grounded Synthesis of 5 Executive Volumes")

VOLUME_SPECS = [
    (
        "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
        "核心决策备忘录：V&F IMR-MS 中国 CCS/CCUS 市场机会裁决与双轨商业战略",
        "Directly open with clear executive verdict answers to all 4 core questions: "
        "(1) Is there a real opportunity? Explicitly distinguish HIGH-ROI genuine needs (acid-gas pipeline pitting, export LCO2 shipping, green methanol catalyst protection, R&D amine monitoring) vs ELIMINATED/pseudo-demand wedges (domestic food-grade offline sampling); "
        "(2) Exact [MKT-CALC] China 2026-2030 & 2031-2036 TAM/SAM/SOM summary; "
        "(3) Core competitive moat vs Thermo MAX-iR/MAX-Bev, optical/GC analyzers, and domestic MS; "
        "(4) Dual-Track A/B/C commercial model & GO decision.",
    ),
    (
        "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        "第01卷：中国 CCS/CCUS 市场规模测算、重点工程图谱与强腐蚀/防毒痛点剖析",
        "Present the full verbatim Python [MKT-CALC] bottom-up tables (2026-2030 & 2031-2036 Low/Base/High), "
        "verified Chinese CCUS/EOR/green-methanol/LCO2 ship project catalog citing [EV-CN-*], "
        "Shell/IFE 2024 reaction kinetics (H2S+3NO2 -> SO2+H2O+3NO, H2SO4/HNO3 >25-1000mm/y pitting) & methanol catalyst sulfur/amine poisoning proving why ~1s IMR-MS is non-negotiable, "
        "and preserve the Stage 2 Eliminated/Pseudo-Demand Control Table verbatim.",
    ),
    (
        "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
        "第02卷：国内外竞争格局全面对比与一线技术销售 Battlecards",
        "Deep comparison & sales battlecards covering: "
        "(a) Overseas Process MS vs V&F soft-ionization IMR-MS (~10-14 eV avoiding %CO2 fragmentation masking); "
        "(b) Thermo Fisher MAX-iR FTIR & MAX-Bev (~10 min cycle, no direct H2/Ar/N2 measurement, 3 cal gas bottles, DNV charts caveats per [EV-SIGGI-*]); "
        "(c) ABB/Siemens/Emerson/Servomex/E+H NDIR/TDLAS/GC multi-box combinations; "
        "(d) Chinese domestic MS & PAC integration vendors verified in EvidenceVault (NEVER invent ungrounded model numbers). "
        "Include field objection-handling scripts for Chinese design institute engineers & plant VPs.",
    ),
    (
        "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
        "第03卷：双轨本土化 GTM 方案、定价与利润结构、PAC 生态合作及设计院 Spec-in 战术",
        "Full commercial blueprint: Track A (CO2Sense ¥140-220万), Track B (VF-QAS-CN ¥320-550万 localized GB/T 3836 Ex shelter with Chinese PAC OEMs + local GC/H2O/Hg/FID), Track C (PremierGuard ¥580-950万). "
        "Include verbatim [ROI-CALC] customer payback/NPV/IRR table, 4-Persona STORM friction resolution matrix, PAC integrator selection scorecard, and Design Institute (SEI/HQC/CPECC/天辰) PID Spec-in & bidding qualification playbook.",
    ),
    (
        "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
        "第04卷：商业落地行动路线图（30-60-90 天、12-18 个月灯塔突破与 2027-2031 规模化预算）",
        "Concrete milestone roadmap with owners, Austria HQ (Dr. Siegfried Praun) engineering transfer split (Brevik/Northern Lights Ph2/Stockholm Exergi proof packs & Grafana templates), demo/joint-validation unit strategy, Tier-1/Tier-2 target customer attack wave list, KPI kill-gates, and lean BD resource budget.",
    ),
]

shared_calc_block = (
    f"{screened['market_sizing_md']}\n\n"
    f"{screened['roi_table_md']}\n\n"
    f"{screened['eliminated_table_md']}\n\n"
    f"=== VERIFIED CHINA PROJECTS ===\n{json.dumps(screened['projects'][:18], ensure_ascii=False, indent=2)}\n\n"
    f"=== VERIFIED COMPETITORS ===\n{json.dumps(screened['competitors'][:14], ensure_ascii=False, indent=2)}\n\n"
    f"=== 4-PERSONA STORM INTERROGATION MEMOS ===\n{json.dumps(storm_memos, ensure_ascii=False)[:4800]}\n\n"
    f"=== ELO TOURNAMENT RESULTS ===\n{json.dumps(elo_matches, ensure_ascii=False)[:1800]}"
)

async def _synth_volume(spec: tuple[str, str, str]) -> dict:
    fname, title_cn, mandate = spec
    prompt = (
        f"Author Volume `{fname}` ({title_cn}) in authoritative, persuasive Simplified Chinese.\n"
        f"Mandate: {mandate}\n\n"
        "NON-NEGOTIABLE GROUNDING RULES:\n"
        "1. Every evidence claim MUST cite valid `[EV-SIGGI-*]`, `[EV-CN-*]`, or `[EV-GL-*]` present in the evidence excerpts below.\n"
        "2. Copy Python `[MKT-CALC]` market numbers and `[ROI-CALC]` payback/IRR/NPV figures EXACTLY without alteration.\n"
        "3. Cover the Track A / Track B (VF-QAS-CN) / Track C architecture cleanly without inventing unverified domestic models.\n\n"
        f"=== DETERMINISTIC DATA & CATALOGS ===\n{shared_calc_block}\n\n"
        f"=== SIGGI EVIDENCE ===\n{screened['evidence_context_siggi']}\n\n"
        f"=== CHINA EVIDENCE ===\n{screened['evidence_context_cn']}\n\n"
        f"=== GLOBAL EVIDENCE ===\n{screened['evidence_context_global']}"
        + NO_TOOL_DIRECTIVE
    )
    res = await agent(
        prompt=prompt,
        schema=VOLUME_REPORT_SCHEMA,
        role=f"Synthesizer ({fname[:2]})",
        model=target_model,
    )
    return {"filename": fname, "markdown": res["markdown"].strip() + "\n"}

vol_list = await parallel(VOLUME_SPECS, _synth_volume)
volumes_map = {item["filename"]: item["markdown"] for item in vol_list}


# ---------------------------------------------------------------------------
# Stage 6: Bounded Critic Reflection + CRAG Refill (Max 2 Loops)
# ---------------------------------------------------------------------------
phase("Stage 6: Adversarial Critic Audit & CRAG Gap-Refill")
critique_history: list[dict] = []
critique_loops_executed = 0

for loop_idx in range(1, max_loops + 1):
    critique_loops_executed = loop_idx
    invalid_cites: dict[str, list[str]] = {}
    for v_name, v_text in volumes_map.items():
        cited = set(re.findall(r"\[(EV-(?:SIGGI|CN|GL)-\d{3,4})\]", v_text))
        bad = sorted(c for c in cited if c not in all_valid_ev_ids)
        if bad:
            invalid_cites[v_name] = bad

    excerpts = "\n\n".join(
        f"=== {k} (len={len(v)}) ===\n{v[:2200]}" for k, v in sorted(volumes_map.items())
    )
    critic_prompt = (
        f"Critique Loop {loop_idx}/{max_loops} for V&F China CCS/CCUS Strategy Dossier:\n"
        f"Programmatic Invalid Citation Check: {json.dumps(invalid_cites, ensure_ascii=False)}\n\n"
        f"=== AUTHORITATIVE [MKT-CALC] & [ROI-CALC] ===\n{screened['market_sizing_md']}\n\n{screened['roi_table_md']}\n\n"
        f"=== DRAFT EXCERPTS ===\n{excerpts}\n\n"
        "Check cross-volume numeric consistency, competitor honesty (no fabricated models), valid `[EV-*]` IDs, "
        "presence of eliminated pseudo-demand controls, and Track A/B/C execution specificity. "
        "If clean, return passed=true and volumes_to_rewrite=[]."
        + NO_TOOL_DIRECTIVE
    )
    audit = await agent(
        prompt=critic_prompt,
        schema=CRITIC_AUDIT_SCHEMA,
        role=f"Adversarial Critic L{loop_idx}",
        model=target_model,
    )

    vols_to_fix = list(dict.fromkeys(audit.get("volumes_to_rewrite", [])))
    if invalid_cites:
        for bad_v in invalid_cites:
            if bad_v not in vols_to_fix:
                vols_to_fix.append(bad_v)
        audit["passed"] = False

    crag_queries = [
        {
            "track_id": "CRAG_GAP",
            "geo_scope": iss["suggested_geo_scope"],
            "query": iss["suggested_query"],
        }
        for iss in audit.get("issues", [])
        if iss.get("needs_crag_gap_search") and str(iss.get("suggested_query", "")).strip()
    ][:4]

    critique_history.append(
        {
            "loop": loop_idx,
            "passed": audit["passed"],
            "volumes_to_rewrite": vols_to_fix,
            "crag_queries": crag_queries,
            "assessment": audit["overall_assessment"],
        }
    )

    if audit["passed"] or loop_idx == max_loops or (not vols_to_fix and not crag_queries):
        break

    crag_ctx = ""
    if crag_queries:
        gap_q_file = BASE_DIR / f"data/stage6_gap_queries_l{loop_idx}.json"
        gap_out_file = BASE_DIR / f"data/stage6_gap_evidence_l{loop_idx}.json"
        gap_q_file.write_text(json.dumps(crag_queries, ensure_ascii=False, indent=2), encoding="utf-8")
        _run_cli(
            [
                "gap-search",
                "--queries-json",
                str(gap_q_file),
                "--vault-db",
                vault_db,
                "--output-file",
                str(gap_out_file),
            ]
        )
        gap_data = json.loads(gap_out_file.read_text(encoding="utf-8"))
        crag_ctx = gap_data.get("formatted_context", "")
        if gap_data.get("all_valid_ev_ids"):
            all_valid_ev_ids.update(gap_data["all_valid_ev_ids"])

    async def _rewrite_target(v_name: str) -> dict:
        r_prompt = (
            f"Rewrite `{v_name}` to fix Critic findings:\n"
            f"Assessment: {audit['overall_assessment']}\n"
            f"Invalid IDs to remove: {invalid_cites.get(v_name, [])}\n\n"
            f"=== AUTHORITATIVE DATA ===\n{shared_calc_block[:4800]}\n\n"
            f"=== CRAG NEW EVIDENCE ===\n{crag_ctx}\n\n"
            f"=== VALID EVIDENCE SAMPLES ===\n{screened['evidence_context_siggi'][:2500]}\n\n{screened['evidence_context_cn'][:2500]}\n\n"
            f"=== PREVIOUS TEXT ===\n{volumes_map[v_name][:5500]}"
            + NO_TOOL_DIRECTIVE
        )
        res = await agent(
            prompt=r_prompt,
            schema=VOLUME_REPORT_SCHEMA,
            role=f"CRAG Rewriter ({v_name[:2]})",
            model=target_model,
        )
        return {"filename": v_name, "markdown": res["markdown"].strip() + "\n"}

    valid_targets = [v for v in vols_to_fix if v in volumes_map]
    if valid_targets:
        rewritten = await parallel(valid_targets, _rewrite_target)
        for item in rewritten:
            volumes_map[item["filename"]] = item["markdown"]


# ---------------------------------------------------------------------------
# Stage 7: 100-Point Stage-Gate Judge & Deterministic Finalize
# ---------------------------------------------------------------------------
phase("Stage 7: Stage-Gate Judge & Finalize Deliverables")
judge_prompt = (
    "Score this V&F IMR-MS China CCS/CCUS Research Dossier strictly on the 5x20=100 Stage-Gate Rubric:\n"
    "1. `china_grounding_and_project_specificity` (20)\n"
    "2. `market_sizing_and_pain_point_rigor` (20)\n"
    "3. `competitive_battlecard_accuracy` (20)\n"
    "4. `dual_track_gtm_and_roi_actionability` (20)\n"
    "5. `evidence_traceability_and_prose` (20)\n\n"
    f"Stats: projects={len(screened['projects'])}, competitors={len(screened['competitors'])}, "
    f"shortlist={len(shortlist)}, eliminated={len(screened['eliminated'])}\n\n"
    f"Vol 00:\n{volumes_map['00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md'][:2600]}\n\n"
    f"Vol 02:\n{volumes_map['02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md'][:2200]}\n\n"
    f"Vol 03:\n{volumes_map['03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md'][:2200]}"
    + NO_TOOL_DIRECTIVE
)
rubric = await agent(
    prompt=judge_prompt,
    schema=JUDGE_RUBRIC_SCHEMA,
    role="Stage-Gate Judge",
    model=target_model,
)

final_bundle = {
    "run_id": run_id,
    "profile": profile,
    "llm_engine": f"antigravity_native:{target_model}",
    "shortlist": shortlist,
    "eliminated": screened["eliminated"],
    "storm_memos": storm_memos,
    "elo_matches": elo_matches,
    "market_sizing_summary": screened["market_sizing_summary"],
    "volumes": volumes_map,
    "judge_rubric": rubric,
    "critique_loops_executed": critique_loops_executed,
    "critique_history": critique_history,
    "native_agent_invocations": {
        "planner": 1,
        "track_miners": len(track_payload["tracks"]),
        "storm_panels": len(shortlist),
        "elo_matches": len(elo_matches),
        "volume_synthesizers": len(VOLUME_SPECS),
        "critic_loops": critique_loops_executed,
        "judge": 1,
    },
}
bundle_file = BASE_DIR / "data/final_native_bundle.json"
bundle_file.write_text(json.dumps(final_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

_run_cli(
    [
        "finalize",
        "--bundle-file",
        str(bundle_file),
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
            "stage_gate_score": rubric.get("total_score"),
            "output_dir": str((BASE_DIR / output_dir).resolve()),
            "shortlist_count": len(shortlist),
            "eliminated_count": len(screened["eliminated"]),
        },
        ensure_ascii=False,
    )
)
