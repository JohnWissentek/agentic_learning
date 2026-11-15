"""Native Antigravity IDE `run_workflow` Orchestration on Built-in Frontier LLMs.

Combines:
- Antigravity built-in frontier LLMs (`model="pro"` by default) for ALL cognitive work:
  Step-Back Planning, 8-Track Grounded Research, 4-Persona STORM Interrogation,
  AI Co-Scientist Elo Tournament, 5-Volume Grounded Report Synthesis, Producer-Critic
  Reflection, and Independent Stage-Gate Judging.
- Local deterministic Python CLI (`pso-research prepare-context` & `finalize-native`):
  Paid Dual-Engine AI Search (Metaso CN + Serper Global -> SQLite EvidenceVault)
  and PALMs deterministic Payback / 3Y ROI / 5Y NPV / 5Y IRR / SAM-SOM calculation.

Usage inside Antigravity IDE:
  run_workflow(
      ScriptPath="/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/ide_workflows/antigravity_run_workflow.py",
      Args={"sector": "all", "output_dir": "outputs/power_semiconductor_online_testing_2026_2036", "model": "pro"},
      Cwd="/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities",
      Description="Execute Power & Semiconductor Online Testing Flagship Workflow on Antigravity Pro LLM",
  )
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
output_dir = str(_user_args.get("output_dir", "outputs/power_semiconductor_online_testing_2026_2036"))
target_model = str(_user_args.get("model", "pro"))
run_id = f"native-{uuid.uuid4().hex[:8]}"

NO_TOOL_DIRECTIVE = (
    "\n\nIMPORTANT: All required evidence excerpts, market seeds, and deterministic [ROI-CALC] metrics "
    "are ALREADY provided in this prompt. Do NOT call any filesystem, shell, search, or browser tools "
    "(do not call run_command, read_file, write_file, edit_file, or search_web). Complete your reasoning "
    "in a single turn and return your final output by calling the `finish` tool matching the schema."
)

# ---------------------------------------------------------------------------
# Flat JSON Schemas (no $ref / $defs) for run_workflow `agent(..., schema=...)`
# ---------------------------------------------------------------------------

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "step_back_thesis": {"type": "string"},
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                    "step_back_physics_principle": {"type": "string"},
                },
                "required": ["track_id", "step_back_physics_principle"],
            },
        },
    },
    "required": ["step_back_thesis", "tracks"],
}

TRACK_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "string"},
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
                    "storm": {
                        "type": "object",
                        "properties": {
                            "sharpest_pain_point_summary": {"type": "string"},
                            "key_localization_or_export_moat": {"type": "string"},
                            "buyer_assessments": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "persona_role": {"type": "string"},
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
                    },
                },
                "required": [
                    "opp_id",
                    "title",
                    "horizon",
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
                    "storm",
                ],
            },
        },
    },
    "required": [
        "track_id",
        "china_market_dynamics",
        "global_market_dynamics",
        "horizon_3_5y_outlook",
        "horizon_5_10y_outlook",
        "pain_points",
        "opportunities",
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
        "decision": {"type": "string", "enum": ["pass", "needs_rewrite"]},
        "overall_confidence": {"type": "number"},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "section": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["severity", "section", "issue_type", "description"],
            },
        },
    },
    "required": ["decision", "overall_confidence", "summary", "issues"],
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
# Phase 1: Prepare Grounded EvidenceVault + Deterministic PALMs ROI Context
# ---------------------------------------------------------------------------

phase(f"1. Prepare Grounded EvidenceVault & PALMs ROI Context (sector={sector})")
ctx_path = BASE_DIR / "data/native_context_bundle.json"
prep_proc = subprocess.run(
    [
        str(VENV_PSO),
        "prepare-context",
        "--sector",
        sector,
        "--output",
        str(ctx_path),
    ],
    cwd=str(BASE_DIR),
    check=True,
    capture_output=True,
    text=True,
)
log(prep_proc.stdout.strip())
ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
vstats = ctx["vault_stats"]
log(
    f"EvidenceVault ready: total={vstats.get('total')} "
    f"(CN={vstats.get('cn_count')}, GLOBAL={vstats.get('global_count')}, "
    f"fulltext={vstats.get('with_fulltext_count')}) | tracks={len(ctx['tracks'])} | llm_model={target_model}"
)


# ---------------------------------------------------------------------------
# Phase 2: Step-Back Metrology & Industrial Upgrade Architecture
# ---------------------------------------------------------------------------

phase(f"2. Step-Back Metrology Planning (Antigravity {target_model})")
track_briefs = "\n".join(
    f"- {t['id']} ({t['sector']}): {t['name']} | stages={', '.join(t.get('manufacturing_stages', []))}"
    for t in ctx["tracks"]
)
plan_res = await agent(
    role="Chief Metrology Architect",
    model=target_model,
    schema=PLAN_SCHEMA,
    prompt=(
        "You are a Chief Industrial Metrology Architect planning an executive research study on online/inline "
        "testing & analytical instrumentation opportunities in Power & Energy and Semiconductor Chip Manufacturing.\n"
        "Mandate:\n"
        "- Geographic order: CHINA FIRST (2027-2031 localization & scale-up + 2031-2036 industrial upgrade), then GLOBAL SECOND.\n"
        "- Time horizons: 3-5 years (2027-2031) vs 5-10 years (2031-2036).\n"
        "- Core value pillars: Quality/Yield improvement, Manufacturing Cost/TCO reduction, Environmental/EHS decarbonization, High Manufacturing ROI & Industrial Upgrading.\n\n"
        f"Selected Tracks:\n{track_briefs}\n\n"
        "Using Step-Back reasoning from first-principles physics & yield failure limits, output a Simplified Chinese "
        "`step_back_thesis` plus a concise Simplified Chinese `step_back_physics_principle` for EVERY track ID above."
        + NO_TOOL_DIRECTIVE
    ),
)
phys_by_track = {
    item["track_id"]: item["step_back_physics_principle"]
    for item in plan_res.get("tracks", [])
    if isinstance(item, dict) and item.get("track_id")
}
log(f"Step-Back thesis prepared: {plan_res.get('step_back_thesis', '')[:140]}...")


# ---------------------------------------------------------------------------
# Phase 3: Parallel Track Grounded Research & 4-Persona STORM Interrogation
# ---------------------------------------------------------------------------

phase(f"3. Parallel {len(ctx['tracks'])}-Track Research & STORM Buying-Committee Audit (Antigravity {target_model})")


def _build_track_prompt(track: dict) -> str:
    ev_lines = []
    for r in track["evidence_pack"]:
        ev_lines.append(
            f"- [{r['ev_id']}] ({r['geo_scope']} | {r['authority_tier']} | {r['engine']} | {r['published_date'] or 'n/a'}) "
            f"{r['title']}\n  Excerpt: {r['excerpt']}"
        )
    seed_lines = []
    for s in track["seeds"]:
        m = s["roi_metrics"]
        seed_lines.append(
            f"- {s['opp_id']} [{s['horizon']}]: {s['title']} | physics={s['physics_principle']} | "
            f"[ROI-CALC]: CAPEX=¥{m['capex_cny']/10000:.1f}万, NetCF=¥{m['net_annual_cashflow_cny']/10000:.1f}万/yr, "
            f"Payback={m['payback_months']}m, 5Y IRR={m['irr_5yr_pct']}%, 5Y NPV=¥{m['npv_5yr_cny']/10000:.1f}万, "
            f"ChinaTAM=¥{s['roi_baseline']['market_tam_china_cny_100m']}亿, GlobalTAM=${s['roi_baseline']['market_tam_global_usd_m']}M"
        )
    phys_note = phys_by_track.get(track["id"], "")
    return (
        f"You are analyzing Track {track['id']} ({track['sector']}): {track['name']}.\n"
        f"Step-Back Physics Guidance: {phys_note}\n"
        f"Manufacturing Stages: {track.get('manufacturing_stages', [])}\n\n"
        f"Calibrated Seed Opportunities (YOU MUST preserve ALL seed `opp_id` values below in your output `opportunities` list):\n"
        + "\n".join(seed_lines)
        + "\n\nVerified EvidenceVault Records (CITE ONLY exact `[EV-CN-...]` / `[EV-GL-...]` IDs present below):\n"
        + "\n".join(ev_lines)
        + "\n\nRequirements (authoritative Simplified Chinese with English technical terms on first mention):\n"
        "1. Strictly contrast CHINA FIRST (`china_market_dynamics`, localization bottlenecks, policy/grid/fab pain points) "
        "followed by GLOBAL SECOND (`global_market_dynamics`).\n"
        "2. Distinguish `horizon_3_5y_outlook` (2027-2031 scale-up & high-ROI) from `horizon_5_10y_outlook` (2031-2036 generational shift).\n"
        "3. Provide >= 4 factory-floor `pain_points` covering BOTH `CN` and `GLOBAL` with exact `evidence_ids`.\n"
        "4. For EACH opportunity seed above, articulate concrete sensing physics, inline form factor, all 4 value mechanisms, "
        "China-first positioning, Global expansion path, verified `evidence_ids`, AND a realistic 4-persona `storm` critique covering: "
        '"Fab/Plant Yield VP", "Metrology/Process Chief Engineer", "EHS & Green Compliance Director", "CFO / Procurement ROI Gatekeeper".'
        + NO_TOOL_DIRECTIVE
    )


raw_track_results = await parallel(
    ctx["tracks"],
    lambda t: agent(
        role=f"Track {t['id']} Research + STORM",
        model=target_model,
        schema=TRACK_SCHEMA,
        prompt=_build_track_prompt(t),
    ),
)

# Deterministically align track results with authoritative seed ROI baselines & Elo starting scores
merged_track_results = []
flat_opps = []
for orig_t, res_t in zip(ctx["tracks"], raw_track_results):
    valid_ids = set(orig_t["valid_ev_ids"])
    fallback_ids = orig_t["valid_ev_ids"][:4]
    by_oid = {
        str(o.get("opp_id")): o
        for o in res_t.get("opportunities", [])
        if isinstance(o, dict) and o.get("opp_id")
    }
    aligned_opps = []
    for seed in orig_t["seeds"]:
        oid = seed["opp_id"]
        o_llm = by_oid.get(oid, {})
        evs = [e for e in o_llm.get("evidence_ids", []) if e in valid_ids] or fallback_ids
        pillar = float(seed["weighted_pillar_score"])
        elo_init = round(1500.0 + (pillar - 75.0) * 4.0, 2)
        opp_rec = {
            "opp_id": oid,
            "track_id": orig_t["id"],
            "sector": orig_t["sector"],
            "title": o_llm.get("title") or seed["title"],
            "horizon": seed["horizon"],
            "china_priority_score": seed["china_priority_score"],
            "global_priority_score": seed["global_priority_score"],
            "physics_principle": o_llm.get("physics_principle") or seed["physics_principle"],
            "target_process_point": o_llm.get("target_process_point") or (orig_t["manufacturing_stages"][0] if orig_t["manufacturing_stages"] else "核心产线在线工位"),
            "product_form_factor": o_llm.get("product_form_factor") or "在线/原位工业集成分析仪",
            "quality_yield_mechanism": o_llm.get("quality_yield_mechanism") or "在线实时拦截批量缺陷并闭环良率优化",
            "cost_tco_mechanism": o_llm.get("cost_tco_mechanism") or "降低报废损失、耗材消耗与非计划停线",
            "green_ehs_mechanism": o_llm.get("green_ehs_mechanism") or "精准控制高危介质泄漏与双碳减排",
            "industrial_upgrade_mechanism": o_llm.get("industrial_upgrade_mechanism") or "推动国产高端在线量检测装备自主可控",
            "china_positioning": o_llm.get("china_positioning") or "中国头部产线痛点优先Spec-in切入",
            "global_expansion_path": o_llm.get("global_expansion_path") or "随中国产业链及国际认证体系出海",
            "evidence_ids": evs,
            "roi_metrics": seed["roi_metrics"],
            "roi_baseline": seed["roi_baseline"],
            "weighted_pillar_score": pillar,
            "elo_rating": elo_init,
            "storm": o_llm.get("storm") or {
                "sharpest_pain_point_summary": "产线停机风险与误报率容忍门槛",
                "key_localization_or_export_moat": "原位快速响应、国产备件成本优势与国际标准合规",
                "buyer_assessments": [],
            },
        }
        aligned_opps.append(opp_rec)
        flat_opps.append(opp_rec)

    merged_track_results.append(
        {
            "track_id": orig_t["id"],
            "sector": orig_t["sector"],
            "track_name": orig_t["name"],
            "china_market_dynamics": res_t.get("china_market_dynamics", ""),
            "global_market_dynamics": res_t.get("global_market_dynamics", ""),
            "horizon_3_5y_outlook": res_t.get("horizon_3_5y_outlook", ""),
            "horizon_5_10y_outlook": res_t.get("horizon_5_10y_outlook", ""),
            "pain_points": res_t.get("pain_points", []),
            "opportunities": aligned_opps,
        }
    )
log(f"Aligned {len(merged_track_results)} track dossiers and {len(flat_opps)} opportunities.")


# ---------------------------------------------------------------------------
# Phase 4: AI Co-Scientist Pairwise Elo Tournament & Deterministic ROI Tables
# ---------------------------------------------------------------------------

phase(f"4. AI Co-Scientist Pairwise Elo Tournament (Antigravity {target_model})")
elo_matches = []


def _update_elo_local(ra: float, rb: float, a_won: bool, k: float = 32.0) -> tuple[float, float]:
    ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
    eb = 1.0 - ea
    sa = 1.0 if a_won else 0.0
    return round(ra + k * (sa - ea), 2), round(rb + k * ((1.0 - sa) - eb), 2)


for r_idx in (1, 2):
    flat_opps.sort(key=lambda x: x["elo_rating"], reverse=True)
    matchups = [(flat_opps[i], flat_opps[i + 1]) for i in range(0, len(flat_opps) - 1, 2)]
    decisions = await parallel(
        matchups,
        lambda pair: agent(
            role=f"Elo Judge R{r_idx}: {pair[0]['opp_id']} vs {pair[1]['opp_id']}",
            model=target_model,
            schema=ELO_SCHEMA,
            prompt=(
                f"Compare Option A vs Option B head-to-head on: Manufacturing ROI & Payback (35%), "
                f"Quality/Yield impact (25%), Industrial Upgrade & China-First leverage (20%), Cost/TCO & Green EHS (20%).\n\n"
                f"[Option A: {pair[0]['opp_id']}] ({pair[0]['sector']} | {pair[0]['horizon']}) {pair[0]['title']}\n"
                f"- [ROI-CALC]: CAPEX=¥{pair[0]['roi_metrics']['capex_cny']:,.0f}, NetCF=¥{pair[0]['roi_metrics']['net_annual_cashflow_cny']:,.0f}, "
                f"Payback={pair[0]['roi_metrics']['payback_months']}m, 5Y IRR={pair[0]['roi_metrics']['irr_5yr_pct']}%, ChinaTAM=¥{pair[0]['roi_baseline']['market_tam_china_cny_100m']}亿\n"
                f"- Yield: {pair[0]['quality_yield_mechanism']}\n"
                f"- Upgrade: {pair[0]['industrial_upgrade_mechanism']}\n\n"
                f"[Option B: {pair[1]['opp_id']}] ({pair[1]['sector']} | {pair[1]['horizon']}) {pair[1]['title']}\n"
                f"- [ROI-CALC]: CAPEX=¥{pair[1]['roi_metrics']['capex_cny']:,.0f}, NetCF=¥{pair[1]['roi_metrics']['net_annual_cashflow_cny']:,.0f}, "
                f"Payback={pair[1]['roi_metrics']['payback_months']}m, 5Y IRR={pair[1]['roi_metrics']['irr_5yr_pct']}%, ChinaTAM=¥{pair[1]['roi_baseline']['market_tam_china_cny_100m']}亿\n"
                f"- Yield: {pair[1]['quality_yield_mechanism']}\n"
                f"- Upgrade: {pair[1]['industrial_upgrade_mechanism']}\n\n"
                f'Return JSON with `winner_id` strictly equal to "{pair[0]["opp_id"]}" or "{pair[1]["opp_id"]}", and a concise Chinese `rationale`.'
                + NO_TOOL_DIRECTIVE
            ),
        ),
    )
    for (a, b), dec in zip(matchups, decisions):
        a_won = str(dec.get("winner_id", "")).strip() != b["opp_id"]
        wid = a["opp_id"] if a_won else b["opp_id"]
        new_a, new_b = _update_elo_local(a["elo_rating"], b["elo_rating"], a_won, k=32.0)
        a["elo_rating"], b["elo_rating"] = new_a, new_b
        elo_matches.append(
            {
                "round_idx": r_idx,
                "opp_a_id": a["opp_id"],
                "opp_b_id": b["opp_id"],
                "winner_id": wid,
                "rationale": dec.get("rationale", ""),
                "elo_a_after": new_a,
                "elo_b_after": new_b,
            }
        )

if flat_opps:
    elos = [o["elo_rating"] for o in flat_opps]
    lo, hi = min(elos), max(elos)
    span = max(1.0, hi - lo)
    flat_opps.sort(
        key=lambda o: 0.55 * o["weighted_pillar_score"] + 0.45 * (60.0 + ((o["elo_rating"] - lo) / span) * 38.0),
        reverse=True,
    )
    for idx, o in enumerate(flat_opps, start=1):
        o["composite_rank"] = idx


def _fmt_roi_table(sec_filter: str | None = None) -> str:
    rows = []
    for o in flat_opps:
        if sec_filter and o["sector"] != sec_filter:
            continue
        m = o["roi_metrics"]
        evs = ", ".join(f"[{e}]" for e in o["evidence_ids"][:4])
        rows.append(
            f"| #{o['composite_rank']} | `{o['opp_id']}` | {o['track_id']} | {o['horizon']} | {o['title']} | "
            f"¥{m['capex_cny']/10000:.1f}万 | ¥{m['net_annual_cashflow_cny']/10000:.1f}万/年 | "
            f"**{m['payback_months']}月** | {m['irr_5yr_pct']}% | ¥{m['npv_5yr_cny']/10000:.1f}万 | "
            f"{m['payback_tier']} | {o['weighted_pillar_score']} / Elo {o['elo_rating']} | {evs} |"
        )
    hdr = (
        "| 综合排名 | ID | 赛道 | 周期 | 机会名称 | 单套CAPEX | 年净现金流 | "
        "回收期[ROI-CALC] | 5年IRR[ROI-CALC] | 5年NPV[ROI-CALC] | ROI分级 | 综合分/Elo | 证据溯源 |\n"
        "| :---: | :---: | :---: | :---: | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :---: | :--- |"
    )
    return hdr + "\n" + "\n".join(rows)


def _fmt_dossiers(sec_filter: str | None = None) -> str:
    blocks = []
    for t in merged_track_results:
        if sec_filter and t["sector"] != sec_filter:
            continue
        pps = "\n".join(
            f"  - [{p['geo_scope']}] {p['process_stage']}: {p['pain_description']} "
            f"(现有局限: {p['current_limitation']}) 证据: {p.get('evidence_ids', [])}"
            for p in t["pain_points"]
        )
        opps = "\n".join(
            f"  - `{o['opp_id']}` ({o['horizon']}): {o['title']} | 机理: {o['physics_principle']} | "
            f"形态: {o['product_form_factor']} | 工位: {o['target_process_point']} | "
            f"中国切入: {o['china_positioning']} | 全球拓展: {o['global_expansion_path']} | "
            f"四大支柱: 良率[{o['quality_yield_mechanism']}], 降本[{o['cost_tco_mechanism']}], "
            f"环保[{o['green_ehs_mechanism']}], 升级[{o['industrial_upgrade_mechanism']}] | 证据: {o['evidence_ids']}"
            for o in t["opportunities"]
        )
        blocks.append(
            f"### 赛道 {t['track_id']}: {t['track_name']}\n"
            f"- 中国市场动态: {t['china_market_dynamics']}\n"
            f"- 全球市场动态: {t['global_market_dynamics']}\n"
            f"- 3-5年展望: {t['horizon_3_5y_outlook']}\n"
            f"- 5-10年展望: {t['horizon_5_10y_outlook']}\n"
            f"- 产线痛点:\n{pps}\n"
            f"- 机会详情:\n{opps}"
        )
    return "\n\n".join(blocks)


def _fmt_storm(sec_filter: str | None = None) -> str:
    lines = []
    for o in flat_opps:
        if sec_filter and o["sector"] != sec_filter:
            continue
        st = o["storm"]
        ba = " ; ".join(
            f"{a['persona_role']}->{a['adoption_barrier']} (Spec-in: {a['spec_in_trigger']}; 工程改型: {a['recommended_product_tweak']})"
            for a in st.get("buyer_assessments", [])
        )
        lines.append(
            f"- `{o['opp_id']}` 最尖锐痛点: {st.get('sharpest_pain_point_summary', '')} | "
            f"本土/出海护城河: {st.get('key_localization_or_export_moat', '')} | 四方拷问: {ba}"
        )
    return "\n".join(lines)


def _fmt_vault(prefixes: tuple[str, ...], limit_per_track: int = 8) -> str:
    out = []
    for t in ctx["tracks"]:
        if not t["id"].startswith(prefixes):
            continue
        for r in t["evidence_pack"][:limit_per_track]:
            out.append(
                f"- [{r['ev_id']}] ({t['id']}/{r['geo_scope']}/{r['authority_tier']}) {r['title']} -> {r['excerpt'][:340]}"
            )
    return "\n".join(out)


roi_all_table = _fmt_roi_table()
roi_power_table = _fmt_roi_table("power_energy")
roi_semi_table = _fmt_roi_table("semiconductor")
power_dossiers = _fmt_dossiers("power_energy")
semi_dossiers = _fmt_dossiers("semiconductor")
storm_all = _fmt_storm()
storm_power = _fmt_storm("power_energy")
storm_semi = _fmt_storm("semiconductor")
elo_digest = "\n".join(
    f"- Round {m['round_idx']}: `{m['opp_a_id']}` vs `{m['opp_b_id']}` -> Winner `{m['winner_id']}` | {m['rationale']}"
    for m in elo_matches
)
ev_power = _fmt_vault(("P",), 8)
ev_semi = _fmt_vault(("S",), 8)
ev_all = _fmt_vault(("P", "S"), 5)


# ---------------------------------------------------------------------------
# Phase 5: Parallel 5-Volume Grounded Flagship Synthesis (Antigravity Pro)
# ---------------------------------------------------------------------------

phase(f"5. Parallel 5-Volume Flagship Synthesis (Antigravity {target_model})")

SYNTH_RULES = (
    "\n\nMANDATORY WRITING & GROUNDING RULES (McKinsey / SEMI / CICC Flagship Research Standard):\n"
    "1. Language: Rigorous, quantitative, crisp Simplified Chinese with standard English technical terms in parentheses on first mention.\n"
    "2. Order: ALWAYS analyze **中国市场（优先）** first, followed by **全球市场（欧美日韩台及出海）**; ALWAYS separate **3-5年（2027-2031）** and **5-10年（2031-2036）**.\n"
    "3. Grounding: Cite exact evidence IDs `[EV-CN-...]` and `[EV-GL-...]` across factual/market/standard claims. NEVER alter or invent financial figures — preserve Python `[ROI-CALC]` figures verbatim with `[ROI-CALC]` marker.\n"
    "4. Four Value Pillars: Explicitly prove how instruments deliver (a) 提高产品质量/良率, (b) 降低制造/全生命周期成本, (c) 促进环保与双碳EHS, (d) 生产制造高ROI与产业升级.\n"
    "5. Depth: Aim for ~2,800-4,500 Chinese characters with clear Markdown headings, executive comparison tables, and a clean Mermaid diagram where insightful."
)

volumes_spec = [
    (
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
        "Volume 00: 执行摘要、交叉协同主线与 Top 16 机会全景榜单",
        f"""Write **Volume 00: 电力能源与半导体芯片制造在线测试仪器仪表 3-5年及5-10年战略机会总报告**.
Step-Back Thesis: {plan_res.get('step_back_thesis', '')}

Deterministic [ROI-CALC] Master Ranking Table (preserve exact numbers verbatim):
{roi_all_table}

STORM Buying-Committee Highlights:
{storm_all}

AI Co-Scientist Elo Tournament Log:
{elo_digest}

Selected Grounded Evidence:
{ev_all}

Mandatory Structure:
1. 执行摘要与核心判断（中国优先→全球跟进的双轨结构性拐点）
2. 电力能源 × 半导体交叉协同主线（重点剖析 SiC/GaN 宽禁带器件、电网高频高压装备、新能源与算力芯片的共性在线测试底层能力复用，附 Mermaid 平台复用图）
3. 3-5年（2027-2031 产线痛点高ROI放量） vs 5-10年（2031-2036 代际工艺跃迁新物种）双时间窗全景对比表
4. Top 16 机会综合排位总表（完整复现上面 Python 计算的 `[ROI-CALC]` 数据）
5. 对工业仪器研发企业与系统集成商的三大决策建议（先切哪个产线、如何用 ROI 算账打动 CFO/总工、如何借国产替代出海）。"""
        + SYNTH_RULES
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
        "Volume 01: 电力能源行业（P1-P4）在线测试仪器深度研报",
        f"""Write **Volume 01: 电力能源行业（储能/固态电池、新型光伏/绿氢、特高压/环保气体/海缆、灵活调峰与CCUS）3-5年及5-10年在线测试仪器仪表深度研报**.
Power Deterministic [ROI-CALC] Table:
{roi_power_table}

Power Track Dossiers:
{power_dossiers}

STORM Buyer Interrogation:
{storm_power}

Power Grounded Evidence:
{ev_power}

Mandatory Structure (for EACH of P1, P2, P3, P4):
- 第一节：中国市场产业痛点、十五五/双碳/国网南网驱动与本土在线检测刚需（引用 `[EV-CN-...]`）
- 第二节：全球市场（欧美F-gas法规、绿氢补贴、海外储能与CCUS）对标与出海窗口（引用 `[EV-GL-...]`）
- 第三节：3-5年高ROI机会 vs 5-10年下一代技术新机会（含测量物理机理、产品形态、取样/光学/高压接口、产线良率/降本/环保/ROI[ROI-CALC]量化支撑）
- 第四节：产线买方四角色阻力与 Spec-in 破局点。"""
        + SYNTH_RULES
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
        "Volume 02: 半导体芯片制造行业（S1-S4）在线测试仪器深度研报",
        f"""Write **Volume 02: 半导体芯片制造行业（Fab AMC与湿化/特气、前道纳米光学/X射线量测、SiC/GaN宽禁带功率半导体、2.5D/3D Chiplet/HBM混合键合）3-5年及5-10年在线量检测与测试深度研报**.
Semiconductor Deterministic [ROI-CALC] Table:
{roi_semi_table}

Semiconductor Track Dossiers:
{semi_dossiers}

STORM Buyer Interrogation:
{storm_semi}

Semiconductor Grounded Evidence:
{ev_semi}

Mandatory Structure (for EACH of S1, S2, S3, S4):
- 第一节：中国晶圆厂/功率产线/封测厂痛点、良率爬坡瓶颈与国产化率缺口（引用 `[EV-CN-...]`）
- 第二节：全球先进节点（GAA/CFET、HBM4、Cu-Cu混合键合、8英寸SiC）技术代际演进与国际标杆（引用 `[EV-GL-...]`）
- 第三节：3-5年确定性国产替代与良率放量机会 vs 5-10年原子级/非接触无损原位新物种（含物理测量限界突破、EFEM/原位腔体集成、良率/成本/EHS/ROI[ROI-CALC]定量指标）
- 第四节：晶圆厂工艺与CFO门禁壁垒破解方案。"""
        + SYNTH_RULES
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
        "Volume 03: PALMs 制造端 ROI 财务建模与 Elo 锦标赛排位",
        f"""Write **Volume 03: 制造环节投资回报率 (ROI) 量化模型、TCO 算账与 AI Co-Scientist Elo 锦标赛排位报告**.
Master Deterministic [ROI-CALC] Table:
{roi_all_table}

Pairwise Elo Tournament Match Log:
{elo_digest}

STORM CFO & Procurement Gatekeeper Findings:
{storm_all}

Mandatory Structure:
1. 生产制造端 ROI 建模方法论（为什么产线买单靠的是 `良率增益 + 避免整批报废/非计划停线 + 耗材/环保减负 - OPEX`，附计算公式与 10% WACC 基准）
2. 完整 16 项机会的 `[ROI-CALC]` 财务指标汇总与敏感性分析（区分 Tier-A <=12个月、Tier-B 12-24个月、Tier-C 24-42个月）
3. AI Co-Scientist 两两对抗 Elo 锦标赛排序解析（为什么某些兼顾产业升级的项目在 Elo 评分中胜出）
4. 给客户 CFO 与总工的“一页纸算账模板”（分别以动力电池/特高压换流站、先进晶圆厂/8英寸SiC产线为例）。"""
        + SYNTH_RULES
        + NO_TOOL_DIRECTIVE,
    ),
    (
        "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
        "Volume 04: 仪器技术平台、工程化与产业升级 BD 执行手册",
        f"""Write **Volume 04: 在线测试仪器技术研发、产品形态演进与助力产业升级执行手册 (Playbook)**.
Master Ranking Table:
{roi_all_table}

Dossiers Digest:
{power_dossiers[:3800]}
{semi_dossiers[:3800]}

STORM Engineering Tweaks:
{storm_all}

Selected Grounded Evidence:
{ev_all}

Mandatory Structure:
1. 共性核心技术平台复用矩阵（如何用“软电离质谱(IMR-MS)/激光光谱(TDLAS/CRDS)/太赫兹与超声无损成像/高压动态电学测试”四大底层平台横跨电力能源与半导体双赛道，附 Mermaid 架构图）
2. 从“离线实验室仪器”升级为“产线在线/机台原位仪器”的五大工程化坎（采样预处理防堵塞/防腐蚀、SECS/GEM 与 PLC 工业总线闭环、防爆/洁净室兼容、自动标定免漂移、AI实时缺陷重构）
3. 分阶段市场进入策略（先中国本土标杆示范线 Spec-in -> 再随大客户与认证标准出海欧美/东南亚/中东）
4. 未来 3-5 年与 5-10 年研发立项与并购/生态合作里程碑清单。"""
        + SYNTH_RULES
        + NO_TOOL_DIRECTIVE,
    ),
]

volume_texts = await parallel(
    volumes_spec,
    lambda spec: agent(
        role=f"Synthesizer {spec[0][:2]}",
        model=target_model,
        schema={"type": "string"},
        prompt=spec[2],
    ),
)
volumes = {spec[0]: str(txt).strip() for spec, txt in zip(volumes_spec, volume_texts)}
log(f"Synthesized 5 volumes (chars: {', '.join(f'{k[:2]}={len(v)}' for k, v in volumes.items())}).")


# ---------------------------------------------------------------------------
# Phase 6: Producer-Critic Reflection & Independent Stage-Gate Judge
# ---------------------------------------------------------------------------

phase(f"6. Producer-Critic Audit & Stage-Gate Judge (Antigravity {target_model})")


def _previews_and_checks() -> tuple[str, dict]:
    ev_cited = set()
    roi_cnt = 0
    for content in volumes.values():
        ev_cited.update(re.findall(r"EV-(?:CN|GL)-\d{3}", content))
        roi_cnt += content.count("[ROI-CALC]")
    det_summary = {
        "vault_total": vstats.get("total", 0),
        "vault_cn": vstats.get("cn_count", 0),
        "vault_global": vstats.get("global_count", 0),
        "distinct_ev_ids_cited": len(ev_cited),
        "roi_calc_tags": roi_cnt,
        "volume_lengths": {k: len(v) for k, v in volumes.items()},
    }
    previews = "\n\n".join(
        f"=== {k} ({len(v)} chars) ===\n{v[:2200]}\n...[tail]...\n{v[-800:]}"
        for k, v in sorted(volumes.items())
    )
    return previews, det_summary


previews, det_summary = _previews_and_checks()
critic = await agent(
    role="Heterogeneous Chief Reviewer",
    model=target_model,
    schema=CRITIC_SCHEMA,
    prompt=(
        "You are an unforgiving Heterogeneous Chief Reviewer (Metrology Fellow & Industrial PE Partner) auditing "
        "all 5 synthesized volumes against the Formalized Contract:\n"
        "- China FIRST -> Global SECOND in every section\n"
        "- Clear separation of 3-5y (2027-2031) vs 5-10y (2031-2036)\n"
        "- Exact physics sensing mechanisms & inline form factors without technological confusion\n"
        "- Genuine `[EV-CN-...]` / `[EV-GL-...]` grounding and exact Python `[ROI-CALC]` consistency\n"
        "- Zero empty/truncated sections.\n\n"
        f"Deterministic Stats:\n{json.dumps(det_summary, ensure_ascii=False)}\n\n"
        f"Draft Excerpts:\n{previews}\n\n"
        'Return `decision` ("pass" or "needs_rewrite"), `overall_confidence` (0-100), concise Chinese `summary`, '
        "and specific `issues`."
        + NO_TOOL_DIRECTIVE
    ),
)

critique_history = [critic]
revisions_run = 0
if critic.get("decision") == "needs_rewrite" and critic.get("issues"):
    flagged_prefixes = {str(i.get("section", ""))[:2] for i in critic.get("issues", [])}
    to_revise = [s for s in volumes_spec if s[0][:2] in flagged_prefixes] or volumes_spec[:2]
    issues_txt = "\n".join(
        f"- [{i['severity']}] ({i['section']}): {i['description']}"
        for i in critic.get("issues", [])
    )
    revised_texts = await parallel(
        to_revise,
        lambda spec: agent(
            role=f"Reviser {spec[0][:2]}",
            model=target_model,
            schema={"type": "string"},
            prompt=(
                f"Revise `{spec[0]}` to fix EVERY Reviewer critique below while keeping all verified `[EV-...]` IDs "
                f"and Python `[ROI-CALC]` figures exact.\n\nCritic Issues:\n{issues_txt}\n\n"
                f"Current Draft:\n{volumes[spec[0]]}"
                + NO_TOOL_DIRECTIVE
            ),
        ),
    )
    for spec, rev_txt in zip(to_revise, revised_texts):
        volumes[spec[0]] = str(rev_txt).strip()
        revisions_run += 1
    previews, det_summary = _previews_and_checks()

judge = await agent(
    role="Stage-Gate Quality Judge",
    model=target_model,
    schema=JUDGE_SCHEMA,
    prompt=(
        "You are an independent Stage-Gate Quality Auditor (Ch 19 LLM-as-a-Judge). Score the deliverables objectively "
        "from 0 to 20 on each of the 5 criteria (total 100):\n"
        "1. `china_first_then_global_depth` (0-20)\n"
        "2. `dual_horizon_3_5y_vs_5_10y_rigor` (0-20)\n"
        "3. `pain_point_and_physics_specificity` (0-20)\n"
        "4. `roi_and_industrial_upgrade_value` (0-20)\n"
        "5. `citation_grounding_and_prose` (0-20)\n\n"
        f"Deterministic Summary:\n{json.dumps(det_summary, ensure_ascii=False)}\n\n"
        f"Critic Summary: {critic.get('summary', '')}\n\n"
        f"Deliverable Excerpts:\n{previews}\n\n"
        "Return exact scores, `total_score`, concise Chinese `executive_verdict`, `strengths`, and `residual_risks`."
        + NO_TOOL_DIRECTIVE
    ),
)


# ---------------------------------------------------------------------------
# Phase 7: Deterministic Finalization & 7-Deliverable Compilation
# ---------------------------------------------------------------------------

phase("7. Deterministic Finalization & 7-Deliverable Compilation")
out_bundle = BASE_DIR / "data/native_outputs_bundle.json"
bundle_payload = {
    "run_id": run_id,
    "sector_filter": sector,
    "profile": "flagship",
    "llm_engine": f"antigravity_native:{target_model}",
    "step_back_thesis": plan_res.get("step_back_thesis", ""),
    "track_results": merged_track_results,
    "elo_matches": elo_matches,
    "volumes": volumes,
    "critique_loops_executed": 1 if revisions_run else 0,
    "critique_history": critique_history,
    "judge_rubric": judge,
    "native_agent_invocations": {
        "planner": 1,
        "track_analysts_and_storm": len(ctx["tracks"]),
        "elo_pairwise_matches": len(elo_matches),
        "volume_synthesizers": len(volumes_spec),
        "heterogeneous_critic": 1,
        "targeted_revisions": revisions_run,
        "stage_gate_judge": 1,
    },
}
out_bundle.write_text(json.dumps(bundle_payload, ensure_ascii=False, indent=2), encoding="utf-8")

fin_proc = subprocess.run(
    [
        str(VENV_PSO),
        "finalize-native",
        "--bundle",
        str(out_bundle),
        "--output-dir",
        output_dir,
    ],
    cwd=str(BASE_DIR),
    check=True,
    capture_output=True,
    text=True,
)
log(fin_proc.stdout.strip())
print(
    json.dumps(
        {
            "run_id": run_id,
            "llm_engine": f"antigravity_native:{target_model}",
            "output_dir": str(BASE_DIR / output_dir),
            "evidences": vstats.get("total"),
            "judge_score": judge.get("total_score"),
            "revisions": revisions_run,
        },
        ensure_ascii=False,
    )
)
