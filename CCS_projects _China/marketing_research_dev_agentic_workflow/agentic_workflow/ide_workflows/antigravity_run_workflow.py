"""Antigravity IDE Native Hybrid Workflow v2.0 (`run_workflow`) — Primary Entrypoint.

Model-First + Deterministic Chassis Architecture (4 Stages, All-Flagship Brain, Zero Truncation):
- Stage 0: Deterministic Siggi Corpus + Macro Recon -> 1 Flagship Discovery Architect
- Stage 1: Deterministic Multi-Engine Search -> Parallel Flagship Orthogonal Mining
           (Sector tracks -> SectorDossier; Competitive/PAC track -> CompetitiveEcosystemDossier)
- Stage 2: Deterministic Python [MKT-CALC] & [ROI-CALC] Funnel -> 1 Flagship Global Portfolio Arbitrator
           (replaces 10 flash STORM + 10 flash Elo) -> Locked Executive Fact Sheet & Volume Evidence Routing
- Stage 3: Parallel Flagship Full Edition (5 vols) -> 100% Full-Text Per-Volume Critic/CRAG Loop (<=2)
           -> Parallel Flagship High-Density Executive Edition (5 vols)
           -> 100% Deterministic Dual-Edition Audit Gate + Zero-LLM Vol 05 + Disk Persistence

Zero hand-copied JSON Schemas: all flat schemas are dynamically exported from `vf_ccus_workflow.schemas`.
Supports checkpoint resume via `args={"resume_from": "stage2_apply" | "stage3b"}`.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

_user_args = args if "args" in globals() and isinstance(args, dict) else {}
BASE_DIR = (
    Path(_user_args["base_dir"]).resolve()
    if _user_args.get("base_dir")
    else (Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().resolve())
)
VENV_CLI = BASE_DIR / ".venv/bin/vf-ccus-research"

profile = str(_user_args.get("profile", "flagship"))
output_dir = str(_user_args.get("output_dir", "../research_outputs"))
vault_db = str(_user_args.get("vault_db", "data/vf_ccus_evidence_vault.db"))
target_model = str(_user_args.get("model", "pro"))
resume_from = str(_user_args.get("resume_from", "")).strip().lower()
run_id = f"vf-v2-native-{uuid.uuid4().hex[:8]}"
max_loops = 2 if profile == "flagship" else 1

EV_ID_PATTERN = re.compile(r"\b(EV-(?:SIGGI|CN|GL)-\d{3,4})\b")

NO_TOOL_JSON_DIRECTIVE = (
    "\n\nCRITICAL DIRECTIVE: All verified EvidenceVault excerpts ([EV-SIGGI-*], [EV-CN-*], [EV-GL-*]) "
    "and deterministic Python [MKT-CALC] / [ROI-CALC] metrics are ALREADY injected into this prompt. "
    "Do NOT call any filesystem, shell, search, or browser tools. Complete your analysis in one single turn "
    "and return ONLY valid JSON via `finish` matching the schema."
)

NO_TOOL_MARKDOWN_DIRECTIVE = (
    "\n\nCRITICAL DIRECTIVE: All verified data and evidence are ALREADY injected into this prompt. "
    "Do NOT call any filesystem, shell, search, or browser tools. "
    "NEVER use range-compressed citations like `EV-SIGGI-007~016`; list explicit valid IDs like `[EV-SIGGI-007, EV-SIGGI-009]`. "
    "You MUST submit your complete Simplified Chinese Markdown string by calling the `finish` tool in one single turn."
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


async def _call_agent_with_retry(*, prompt: str, schema: dict, role: str, model: str, retries: int = 2):
    """Run a workflow agent with bounded retry against transient no-finish failures."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            suffix = "" if attempt == 1 else (
                "\n\nREMINDER: Your previous attempt ended without calling `finish`. "
                "Keep the Markdown crisp and well-structured, and ALWAYS call `finish` with the result."
            )
            return await agent(
                prompt=prompt + suffix,
                schema=schema,
                role=role if attempt == 1 else f"{role} (Retry {attempt})",
                model=model,
            )
        except Exception as exc:
            last_err = exc
            log(f"[WARN] Agent `{role}` attempt {attempt}/{retries} failed: {exc}")
    raise last_err


# ---------------------------------------------------------------------------
# Single-Source Flat JSON Schemas exported directly from `schemas.py`
# ---------------------------------------------------------------------------
schema_file = BASE_DIR / "data/v2_flat_schemas.json"
_run_cli(["export-schemas", "--output-file", str(schema_file)])
SCHEMAS = json.loads(schema_file.read_text(encoding="utf-8"))

DISCOVERY_PLAN_SCHEMA = SCHEMAS["DiscoveryPlan"]
SECTOR_DOSSIER_SCHEMA = SCHEMAS["SectorDossier"]
COMPETITIVE_DOSSIER_SCHEMA = SCHEMAS["CompetitiveEcosystemDossier"]
PORTFOLIO_ARBITRATION_SCHEMA = SCHEMAS["PortfolioArbitrationOutput"]
SINGLE_VOLUME_CRITIC_SCHEMA = SCHEMAS["SingleVolumeCriticOutput"]
FREE_MARKDOWN_SCHEMA = {"type": "string"}

recon_file = BASE_DIR / "data/stage0_recon_bundle.json"
plan_file = BASE_DIR / "data/stage0_discovery_plan.json"
track_ev_file = BASE_DIR / "data/stage1_track_evidence.json"
dossiers_file = BASE_DIR / "data/stage1_track_dossiers.json"
screened_file = BASE_DIR / "data/stage2_screened_pool.json"
arbitration_file = BASE_DIR / "data/stage2_arbitration.json"
locked_file = BASE_DIR / "data/stage2_locked_fact_bundle.json"
stage3a_file = BASE_DIR / "data/stage3a_full_drafts.json"

track_count = 6

# ---------------------------------------------------------------------------
# Stage 0 & Stage 1 & Stage 2 (skipped cleanly when resuming from stage2_apply / stage3b)
# ---------------------------------------------------------------------------
if resume_from not in ("stage2_apply", "stage3b"):
    phase("Stage 0: Deterministic Siggi Corpus + Macro Recon & Orthogonal Discovery Plan")
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
    log(f"Stage 0 vault_stats: {recon_bundle['vault_stats']}")

    plan_prompt = (
        "You are the Chief CCUS Market Intelligence Architect (Stage 0 Discovery Planner).\n"
        "Synthesize V&F Austria Siggi primary materials ([EV-SIGGI-*]) and live China/Global macro recon ([EV-CN-*], [EV-GL-*]) "
        "to design 6 strictly ORTHOGONAL research tracks:\n\n"
        "1. T1_EOR_PIPE (`track_kind='sector'`, `S1_pipeline_ship_eor`): 中国百万吨级超临界CO2管道/油田EOR强腐蚀链式反应监控\n"
        "2. T2_LCO2_SHIP (`track_kind='sector'`, `S1_pipeline_ship_eor`): 中国船厂LCO2运输船出口建造与沿海/离岸封存枢纽\n"
        "3. T3_GREEN_MEOH (`track_kind='sector'`, `S2_green_methanol_ccu_chem`): 绿氢+CO2合成绿色甲醇/e-SAF催化剂防硫氨中毒保护\n"
        "4. T4_AMINE_RD (`track_kind='sector'`, `S3_capture_rd_industry`): 燃煤/水泥/钢铁胺法捕集逃逸与设计院中试验证平台\n"
        "5. T5_COMP_PAC (`track_kind='competitive_ecosystem'`, `S1_pipeline_ship_eor`): 国内外竞品与本土GB/T 3836防爆分析小屋PAC集成商及设计院准入壁垒\n"
        "6. T6_FOOD_CTRL (`track_kind='sector'`, `S4_food_beverage_dryice`): 中国食品饮料级/干冰级CO2低支付意愿负向对照验证\n\n"
        "Generate sharp Simplified Chinese Metaso `cn_queries` (3-5 per track) and English Serper `global_queries` (1-3 per track).\n"
        f"Contract ID: VF-CCUS-CHINA-2026-V2 | Profile: {profile}\n\n"
        f"=== SIGGI PRIMARY CORPUS ([EV-SIGGI-*]) ===\n{recon_bundle['siggi_context_text']}\n\n"
        f"=== LIVE MACRO RECON ([EV-CN-*] / [EV-GL-*]) ===\n{recon_bundle['recon_context_text']}"
        + NO_TOOL_JSON_DIRECTIVE
    )

    plan_res = await _call_agent_with_retry(
        prompt=plan_prompt,
        schema=DISCOVERY_PLAN_SCHEMA,
        role="Stage 0 Discovery Architect",
        model=target_model,
    )
    plan_file.write_text(json.dumps(plan_res, ensure_ascii=False, indent=2), encoding="utf-8")

    phase("Stage 1: Parallel Multi-Engine Search & Flagship Orthogonal Track Mining")
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
    track_count = len(track_payload["tracks"])
    scope_yaml = recon_bundle["discovery_scope"]

    async def _mine_one_track(t_item: dict) -> dict:
        tp = t_item["track"]
        track_kind = t_item.get("track_kind") or tp.get("track_kind", "sector")

        if track_kind == "competitive_ecosystem":
            prompt = (
                f"You are a Principal Competitive & PAC Ecosystem Analyst mining `{tp['track_id']}` ({tp['name']}).\n"
                "RULES:\n"
                "1. STRICT ZERO FABRICATION: Every competitor model, technical blind spot, and Chinese PAC integrator MUST come strictly from the verified evidence below and cite ONLY valid EV IDs present below.\n"
                "2. Cover Overseas Process MS (70eV EI), Overseas FTIR/Optical/GC (Thermo MAX-iR/MAX-Bev, ABB/Siemens/Emerson/E+H), Domestic Chinese MS, and Chinese GB/T 3836 Ex-p/Ex-d PAC shelter integrators.\n"
                "3. Extract concrete Design Institute (SEI/HQC/CPECC/天辰) PID Spec-in & EPC budget barriers.\n\n"
                f"=== VERIFIED EVIDENCE EXCERPTS ===\n{t_item['evidence_context']}"
                + NO_TOOL_JSON_DIRECTIVE
            )
            res = await _call_agent_with_retry(
                prompt=prompt,
                schema=COMPETITIVE_DOSSIER_SCHEMA,
                role=f"Competitive Ecosystem Miner ({tp['track_id']})",
                model=target_model,
            )
            return {"kind": "competitive_ecosystem", "dossier": res}

        prompt = (
            f"You are a Principal CCUS & Analytical Instrumentation Analyst mining sector track `{tp['track_id']}` ({tp['name']}).\n"
            f"Sector: `{tp['sector']}`\n"
            f"Hypothesis: {tp['research_hypothesis']}\n\n"
            "RULES:\n"
            "1. STRICT ZERO FABRICATION: Every project, competitor, and standard MUST appear in the Evidence Excerpts below and cite ONLY valid EV IDs present below.\n"
            "2. STRICT 0–100 SCORE SCALE: `china_priority_score` and `vf_moat_score` MUST be on a 0–100 scale (e.g. 88.0, 94.0 — NEVER 0–10!).\n"
            "3. SUB-SEGMENT SIZING: Populate `SegmentSizingInput.sub_segment` clearly (e.g. `onshore_pipeline_eor` for T1, `lco2_export_vessel_hub` for T2, `green_methanol_esaf` for T3, `amine_capture_rd` for T4, `food_grade_control` for T6).\n"
            "4. HONEST 4-COMPONENT ROI BREAKDOWN: Assign the 4 `roi_baseline` benefit streams faithfully to the real failure physics.\n"
            "5. DUAL-TRACK PRICING MODEL (CNY): TRACK_A (¥140-220万, base 180万), TRACK_B VF-QAS-CN (¥320-550万, base 420万), TRACK_C PremierGuard (¥580-950万, base 720万).\n"
            f"6. SECTOR ROI GUARDRAILS ({tp['sector']}): {json.dumps(scope_yaml['wedge_roi_guardrails'].get(tp['sector'], {}), ensure_ascii=False)}\n"
            "7. HONEST PSEUDO-DEMAND FLAGGING: For S4 food-grade routine offline GC displacement, mark `DEPRIORITIZE_OR_PSEUDO_DEMAND`.\n\n"
            f"=== VERIFIED EVIDENCE EXCERPTS ===\n{t_item['evidence_context']}"
            + NO_TOOL_JSON_DIRECTIVE
        )
        res = await _call_agent_with_retry(
            prompt=prompt,
            schema=SECTOR_DOSSIER_SCHEMA,
            role=f"Sector Miner ({tp['track_id']})",
            model=target_model,
        )
        return {"kind": "sector", "dossier": res}

    mined_results = await parallel(track_payload["tracks"], _mine_one_track)
    sector_dossiers = [r["dossier"] for r in mined_results if r["kind"] == "sector"]
    competitive_dossiers = [r["dossier"] for r in mined_results if r["kind"] == "competitive_ecosystem"]

    dossiers_file.write_text(
        json.dumps(
            {"sector_dossiers": sector_dossiers, "competitive_dossiers": competitive_dossiers},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    phase("Stage 2: Deterministic [MKT-CALC]/[ROI-CALC] + Single Flagship Global Arbitrator")
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
    log(
        f"Stage 2 Deterministic Funnel: shortlist={len(screened['shortlist'])}, "
        f"eliminated={len(screened['eliminated'])}, dropped_unverified={len(screened['dropped_unverified_records'])}"
    )

    max_finalists = 8 if profile == "flagship" else 5
    candidate_cards = [
        {
            "wedge_id": item["seed"]["wedge_id"],
            "track_id": item["seed"]["track_id"],
            "sector": item["seed"]["sector"],
            "horizon": item["seed"]["horizon"],
            "delivery_track": item["seed"]["delivery_track"],
            "title": item["seed"]["title"],
            "china_priority_score": item["seed"]["china_priority_score"],
            "vf_moat_score": item["seed"]["vf_moat_score"],
            "weighted_pillar_score": item["weighted_pillar_score"],
            "pain_point": item["seed"]["chemical_pain_point_and_imr_advantage"],
            "sku": item["seed"]["recommended_vf_sku_and_localization"],
            "roi_baseline": {
                "capex_wan": round(item["roi"]["capex_cny"] / 10000, 1),
                "payback_months": item["roi"]["payback_months"],
                "irr_5yr_pct": item["roi"]["irr_5yr_pct"],
                "npv_5yr_wan": round(item["roi"]["npv_5yr_cny"] / 10000, 1),
                "conservative_payback_months": (
                    (item.get("roi_range") or {}).get("conservative") or item["roi"]
                )["payback_months"],
            },
            "evidence_ids": item["seed"]["evidence_ids"],
        }
        for item in screened["shortlist"]
    ]

    arbitrator_prompt = (
        "You are the Chief Commercialization Partner executing ONE globally consistent Portfolio Arbitration pass.\n\n"
        f"1. DEDUPLICATE & MERGE overlapping wedges across tracks into at most {max_finalists} distinct canonical wedges "
        "(use the strongest source `wedge_id` as `canonical_wedge_id` and record all merged source IDs in `merged_from_wedge_ids`).\n"
        "2. RANK globally on a unified 0–100 `global_priority_score` scale based on IMR-MS physical moat, [ROI-CALC] payback resilience, and 2026-2030 China signing probability.\n"
        "3. BUILD a concise, zero-truncation 4-Persona Buying-Center Resistance Matrix across delivery scenario groups "
        "(Track A 科研中试 / Track B 超临界管网与EOR / Track B 绿醇与e-SAF催化剂防毒 / Track C LCO2海运与离岸枢纽), "
        "including ALL 4 required persona roles per group:\n"
        "   - 三大油/央企CCUS工程公司工艺与压缩防腐总工\n"
        "   - 设计院(SEI/HQC/CPECC/天辰)分析仪表室主任与EPC包采经理\n"
        "   - 煤化工/水泥/绿醇项目业主EHS、碳核查与财务ROI决策人\n"
        "   - 大型CCUS分析小屋集成商与运维总包负责人\n\n"
        f"=== SURVIVING CANDIDATES (WITH DETERMINISTIC [ROI-CALC]) ===\n{json.dumps(candidate_cards, ensure_ascii=False, indent=2)}\n\n"
        f"=== COMPETITORS, PAC INTEGRATORS & DESIGN INSTITUTE BARRIERS ===\n"
        f"{json.dumps({'competitors': screened['competitors'][:14], 'pac_integrators': screened['pac_integrators'], 'barriers': screened['design_institute_barriers']}, ensure_ascii=False, indent=2)}"
        + NO_TOOL_JSON_DIRECTIVE
    )

    arbitration_res = await _call_agent_with_retry(
        prompt=arbitrator_prompt,
        schema=PORTFOLIO_ARBITRATION_SCHEMA,
        role="Stage 2 Global Portfolio Arbitrator",
        model=target_model,
    )
    arbitration_file.write_text(json.dumps(arbitration_res, ensure_ascii=False, indent=2), encoding="utf-8")

# Always run (or re-run on stage2_apply resume) deterministic apply-arbitration to lock Fact Sheet
phase("Stage 2b: Deterministic Arbitration Lock & Volume Evidence Routing")
_run_cli(
    [
        "apply-arbitration",
        "--screened-file",
        str(screened_file),
        "--arbitration-file",
        str(arbitration_file),
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-file",
        str(locked_file),
    ]
)
locked = json.loads(locked_file.read_text(encoding="utf-8"))
fact_sheet = locked["executive_fact_sheet"]
volume_bundles = locked["volume_evidence_bundles"]
all_valid_ev_ids = set(locked["all_valid_ev_ids"])
log(f"Locked finalists={len(locked['evaluated_wedges'])}, fact_sheet_chars={len(fact_sheet)}, valid_ev_ids={len(all_valid_ev_ids)}")


VOLUME_SPECS = [
    (
        "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
        "核心决策备忘录：V&F IMR-MS 中国 CCS/CCUS 市场机会裁决与双轨商业战略",
        "Directly answer all 4 core questions: (1) High-ROI genuine industrial needs (including #1 onshore supercritical pipeline/EOR) vs eliminated food-grade pseudo-demand; "
        "(2) Exact [MKT-CALC] China 2026-2030 & 2031-2036 TAM/SAM/SOM (explicitly covering Track A, Track B & Track C and exact 10yr baseline SOM); "
        "(3) Core competitive moat vs Thermo MAX-iR/MAX-Bev, optical/GC & domestic MS; (4) Dual-Track A/B/C GO decision.",
    ),
    (
        "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        "第01卷：中国 CCS/CCUS 市场规模测算、重点工程图谱与强腐蚀/防毒痛点剖析",
        "Present verbatim Python [MKT-CALC] sub-segment tables, verified Chinese CCUS/EOR/green-methanol/LCO2 ship project catalog, "
        "Shell/IFE 2024 acid-dew pitting kinetics & methanol catalyst sulfur/amine poisoning science, and Stage 2 Eliminated Pseudo-Demand Table.",
    ),
    (
        "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
        "第02卷：国内外竞争格局全面对比与一线技术销售 Battlecards",
        "Rigorous comparison & field sales objection-handling battlecards against Overseas Process MS, Thermo MAX-iR/MAX-Bev FTIR, "
        "ABB/Siemens/Emerson/Servomex/E+H NDIR/TDLAS/GC combinations, and verified domestic Chinese MS & PAC shelter integrators.",
    ),
    (
        "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
        "第03卷：双轨本土化 GTM 方案、定价与利润结构、PAC 生态合作及设计院 Spec-in 战术",
        "Track A/B/C pricing & BOM split, verbatim [ROI-CALC] payback/NPV/IRR tables, FULL 4-Persona Buying-Center Resistance Matrix, "
        "PAC integrator selection scorecard (GB/T 3836 Ex / CPA / AVL), and Design Institute (SEI/HQC/CPECC/天辰) Spec-in playbook.",
    ),
    (
        "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
        "第04卷：商业落地行动路线图（30-60-90 天、12-18 个月灯塔突破与 2027-2031 规模化预算）",
        "Concrete milestone roadmap with owners, Austria HQ (Dr. Siegfried Praun) proof-pack transfer split (Northern Lights Ph2 / Brevik / Stockholm Exergi), "
        "demo/trial strategy, target customer attack wave list, KPI kill-gates, and lean BD budget.",
    ),
]


# ---------------------------------------------------------------------------
# Stage 3a: Parallel Flagship Synthesis of 5 Full Detailed Volumes (原始详版)
# ---------------------------------------------------------------------------
if resume_from == "stage3b" and stage3a_file.exists():
    volumes_map = json.loads(stage3a_file.read_text(encoding="utf-8"))
    log(f"Resumed Stage 3a full drafts from checkpoint ({len(volumes_map)} volumes)")
else:
    phase("Stage 3a: Volume-Targeted Synthesis of 5 Full Detailed Volumes (原始详版)")

    async def _synth_full_volume(spec: tuple[str, str, str]) -> dict:
        fname, title_cn, mandate = spec
        prompt = (
            f"Author **Full Detailed Volume（原始详版）** `{fname}` ({title_cn}) in authoritative Simplified Chinese.\n"
            f"Target length: 9,000–14,000 Chinese characters (deep engineering & commercial rigor, zero bloat).\n"
            f"Mandate: {mandate}\n\n"
            "NON-NEGOTIABLE GROUNDING RULES:\n"
            "1. Every factual claim MUST cite explicit valid `[EV-SIGGI-*]`, `[EV-CN-*]`, or `[EV-GL-*]` IDs present in the evidence bundle below. NEVER use range compression like `EV-SIGGI-007~016`!\n"
            "2. Copy Python `[MKT-CALC]` market numbers (especially 2026-2030, 2031-2036, and 10yr baseline SOM units & 万元/亿元) and `[ROI-CALC]` payback/IRR/NPV figures EXACTLY without alteration.\n"
            "3. Explicitly cite Track A / Track B (`VF-QAS-CN`) / Track C and disclose the Stage 2 eliminated pseudo-demand controls.\n\n"
            f"=== LOCKED EXECUTIVE FACT SHEET (SINGLE SOURCE OF TRUTH) ===\n{fact_sheet}\n\n"
            f"=== VOLUME-ROUTED VERIFIED EVIDENCE BUNDLE ===\n{volume_bundles.get(fname, '')}"
            + NO_TOOL_MARKDOWN_DIRECTIVE
        )
        md = await _call_agent_with_retry(
            prompt=prompt,
            schema=FREE_MARKDOWN_SCHEMA,
            role=f"Full Synthesizer ({fname[:2]})",
            model=target_model,
        )
        text = md["markdown"] if isinstance(md, dict) else str(md)
        return {"filename": fname, "markdown": text.strip() + "\n"}

    full_vol_list = await parallel(VOLUME_SPECS, _synth_full_volume)
    volumes_map = {item["filename"]: item["markdown"] for item in full_vol_list}
    stage3a_file.write_text(json.dumps(volumes_map, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 3b: 100% Full-Text Per-Volume Critic + CRAG Rewrite Loop (Max 2 Loops)
# ---------------------------------------------------------------------------
phase("Stage 3b: 100% Full-Text Per-Volume Critic & Targeted CRAG Rewrite")
critique_history: list[dict] = []
critique_loops_executed = 0
critic_agent_calls = 0
rewrite_agent_calls = 0

for loop_idx in range(1, max_loops + 1):
    critique_loops_executed = loop_idx
    invalid_cites: dict[str, list[str]] = {}
    for v_name, v_text in volumes_map.items():
        cited = set(EV_ID_PATTERN.findall(v_text))
        bad = sorted(c for c in cited if c not in all_valid_ev_ids)
        if bad:
            invalid_cites[v_name] = bad

    async def _critic_one(v_name: str) -> dict:
        full_text = volumes_map[v_name]
        bad_ids = invalid_cites.get(v_name, [])
        c_prompt = (
            f"Audit Target Volume: `{v_name}` (Loop {loop_idx}/{max_loops}, {len(full_text)} chars — 100% UNTRUNCATED)\n"
            f"Programmatic Full-Text Invalid EV-ID Detection: {json.dumps(bad_ids, ensure_ascii=False)}\n\n"
            f"=== LOCKED EXECUTIVE FACT SHEET ===\n{fact_sheet}\n\n"
            f"=== COMPLETE VOLUME FULL TEXT (100% UNTRUNCATED) ===\n{full_text}\n\n"
            "Audit ONLY substantive defects: (1) invalid/range-compressed EV IDs or fabricated competitor models, "
            "(2) numeric contradictions against the locked `[MKT-CALC]` / `[ROI-CALC]` tables, "
            "(3) missing Track A/B/C or pseudo-demand disclosure. Do NOT request rewrites for minor stylistic preferences. "
            "If clean, set passed=true and needs_rewrite=false."
            + NO_TOOL_JSON_DIRECTIVE
        )
        res = await _call_agent_with_retry(
            prompt=c_prompt,
            schema=SINGLE_VOLUME_CRITIC_SCHEMA,
            role=f"Full-Text Critic L{loop_idx} ({v_name[:2]})",
            model=target_model,
        )
        res["volume_name"] = v_name
        if bad_ids:
            res["passed"] = False
            res["needs_rewrite"] = True
        return res

    vol_names_sorted = [f for f, _, _ in VOLUME_SPECS if f in volumes_map]
    critic_results = await parallel(vol_names_sorted, _critic_one)
    critic_agent_calls += len(critic_results)

    vols_to_fix = [r["volume_name"] for r in critic_results if (not r.get("passed", True)) or r.get("needs_rewrite")]
    all_issues = [iss for r in critic_results for iss in r.get("issues", [])]
    crag_queries = [
        {
            "track_id": "CRAG_GAP",
            "geo_scope": iss.get("suggested_geo_scope", "CN"),
            "query": iss.get("suggested_query", ""),
        }
        for iss in all_issues
        if iss.get("needs_crag_gap_search") and str(iss.get("suggested_query", "")).strip()
    ][:4]

    per_vol_fb = {r["volume_name"]: r for r in critic_results}
    loop_passed = len(vols_to_fix) == 0
    critique_history.append(
        {
            "loop": loop_idx,
            "passed": loop_passed,
            "volumes_to_rewrite": vols_to_fix,
            "issues_count": len(all_issues),
            "crag_queries": crag_queries,
        }
    )

    if loop_passed or loop_idx == max_loops or (not vols_to_fix and not crag_queries):
        break

    crag_ctx = ""
    if crag_queries:
        gap_q_file = BASE_DIR / f"data/stage3_gap_queries_l{loop_idx}.json"
        gap_out_file = BASE_DIR / f"data/stage3_gap_evidence_l{loop_idx}.json"
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
        fb = per_vol_fb.get(v_name, {})
        r_prompt = (
            f"Targeted Full-Text Revision of `{v_name}` (100% of prior draft provided below — ZERO truncation):\n"
            f"Critic Assessment: {fb.get('overall_assessment', '')}\n"
            f"Specific Issues to Fix: {json.dumps(fb.get('issues', []), ensure_ascii=False)}\n"
            f"Invalid IDs that MUST be removed: {invalid_cites.get(v_name, [])}\n\n"
            f"=== LOCKED EXECUTIVE FACT SHEET ===\n{fact_sheet}\n\n"
            f"=== NEW CRAG EVIDENCE (IF ANY) ===\n{crag_ctx or '(None)'}\n\n"
            f"=== COMPLETE PREVIOUS DRAFT (100% UNTRUNCATED) ===\n{volumes_map[v_name]}\n\n"
            "Fix every flagged issue cleanly, expand any compressed citation ranges into explicit valid EV IDs, "
            "preserve exact [MKT-CALC]/[ROI-CALC] numbers, keep the volume crisp (9,000–14,000 chars), "
            "and return the full revised Markdown via `finish`."
            + NO_TOOL_MARKDOWN_DIRECTIVE
        )
        md = await _call_agent_with_retry(
            prompt=r_prompt,
            schema=FREE_MARKDOWN_SCHEMA,
            role=f"Full-Text Rewriter ({v_name[:2]})",
            model=target_model,
        )
        text = md["markdown"] if isinstance(md, dict) else str(md)
        return {"filename": v_name, "markdown": text.strip() + "\n"}

    valid_targets = [v for v in vols_to_fix if v in volumes_map]
    if valid_targets:
        rewritten = await parallel(valid_targets, _rewrite_target)
        rewrite_agent_calls += len(rewritten)
        for item in rewritten:
            volumes_map[item["filename"]] = item["markdown"]
        stage3a_file.write_text(json.dumps(volumes_map, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 3c: Parallel Flagship High-Density Executive Edition Distillation (高密度高管版)
# ---------------------------------------------------------------------------
phase("Stage 3c: Distilling High-Density Executive Edition (高密度高管版 5 卷)")


async def _distill_exec_volume(spec: tuple[str, str, str]) -> dict:
    fname, title_cn, _ = spec
    full_text = volumes_map[fname]
    e_prompt = (
        f"Distill audited Full Volume `{fname}` ({title_cn}) into its paired **High-Density Executive Edition（高密度高管版）**.\n\n"
        "STRICT EXECUTIVE EDITION RULES:\n"
        "1. Target 2,500–5,500 Chinese characters per volume: decision-first takeaways, compact Markdown tables, bold executive verdicts — ZERO filler.\n"
        "2. Preserve 100% EXACT `[MKT-CALC]` 2026-2030 / 2031-2036 / 10-year baseline SOM numbers (units + 万元 + 亿元), EXACT `[ROI-CALC]` payback/IRR figures, "
        "Track A/B/C pricing architecture, eliminated pseudo-demand controls, and ONLY explicit valid `[EV-*]` citations from the audited source (NO range shorthands like `~`).\n\n"
        f"=== LOCKED EXECUTIVE FACT SHEET ===\n{fact_sheet}\n\n"
        f"=== COMPLETE AUDITED FULL VOLUME (100% FULL TEXT) ===\n{full_text}"
        + NO_TOOL_MARKDOWN_DIRECTIVE
    )
    md = await _call_agent_with_retry(
        prompt=e_prompt,
        schema=FREE_MARKDOWN_SCHEMA,
        role=f"Executive Distiller ({fname[:2]})",
        model=target_model,
    )
    text = md["markdown"] if isinstance(md, dict) else str(md)
    return {"filename": fname, "markdown": text.strip() + "\n"}


exec_vol_list = await parallel(VOLUME_SPECS, _distill_exec_volume)
executive_volumes_map = {item["filename"]: item["markdown"] for item in exec_vol_list}


# ---------------------------------------------------------------------------
# Stage 3d: 100% Deterministic Dual-Edition Audit Gate & Disk Finalize
# ---------------------------------------------------------------------------
phase("Stage 3d: Deterministic Dual-Edition Audit Gate, Zero-LLM Vol 05 & Finalize")

final_bundle = {
    "schema_version": "2.0",
    "run_id": run_id,
    "profile": profile,
    "llm_engine": f"antigravity_native:{target_model}",
    "evaluated_wedges": locked["evaluated_wedges"],
    "eliminated_wedges": locked["eliminated"],
    "dropped_unverified_records": locked["dropped_unverified_records"],
    "portfolio_arbitration": locked["portfolio_arbitration"],
    "market_sizing_summary": locked["market_sizing_summary"],
    "volumes": volumes_map,
    "executive_volumes": executive_volumes_map,
    "critique_loops_executed": critique_loops_executed,
    "critique_history": critique_history,
    "native_agent_invocations": {
        "discovery_planner": 1,
        "orthogonal_track_miners": track_count,
        "global_portfolio_arbitrator": 1,
        "full_volume_synthesizers": len(VOLUME_SPECS),
        "full_text_critic_calls": critic_agent_calls,
        "full_text_rewrite_calls": rewrite_agent_calls,
        "executive_distillers": len(VOLUME_SPECS),
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

sc_file = (BASE_DIR / output_dir).resolve() / "06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json"
scorecard_data = json.loads(sc_file.read_text(encoding="utf-8"))
print(
    json.dumps(
        {
            "run_id": run_id,
            "stage_gate_passed": scorecard_data.get("stage_gate_passed"),
            "failed_gates": scorecard_data.get("deterministic_audit_report", {}).get("failed_gates", []),
            "output_dir": str((BASE_DIR / output_dir).resolve()),
            "executive_dir": str(((BASE_DIR / output_dir).resolve() / "executive_edition")),
            "finalists_count": len(locked["evaluated_wedges"]),
            "eliminated_count": len(locked["eliminated"]),
        },
        ensure_ascii=False,
    )
)
