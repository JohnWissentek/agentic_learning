"""Stage 5: Parallel Grounded Synthesis of the 5 Core Executive Volumes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.prompts import VOLUME_SYNTH_SYSTEM
from vf_ccus_workflow.schemas import ChinaMarketSizingSummary, WorkflowState
from vf_ccus_workflow.tools.market_and_roi_calculator import (
    format_eliminated_table,
    format_market_sizing_table,
    format_roi_table,
)

VOLUME_SPECS: list[tuple[str, str, str]] = [
    (
        "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
        "总览决策备忘录与核心商业结论",
        "Must directly answer the 4 core executive questions with zero fluff: (1) Real China opportunity verdict vs pseudo-demand/eliminated food-CO2 trap; (2) [MKT-CALC] China 2026-2030 & 2031-2036 TAM/SAM/SOM summary; (3) Competitive positioning vs Thermo MAX-iR/MAX-Bev, ABB/Siemens/GC & domestic MS; (4) Dual-Track A/B/C commercial model & GO/NO-GO decision.",
    ),
    (
        "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        "第01卷：中国CCS/CCUS市场规模测算、重点项目图谱与化学腐蚀防毒刚需分析",
        "Present Python [MKT-CALC] bottom-up tables verbatim, full catalog of verified Chinese CCUS/EOR/e-Methanol/LCO2 ship projects, Shell/IFE 2024 H2SO4/HNO3 pitting kinetics & catalyst poisoning science proving WHY ~1s IMR-MS is needed, plus Stage 2 eliminated/pseudo-demand wedges.",
    ),
    (
        "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
        "第02卷：国内外竞争格局对比与一线技术销售Battlecards（防爆/FTIR/GC/国产替代）",
        "Rigorous technical & commercial battlecards against Overseas Process MS, Thermo Fisher MAX-iR / MAX-Bev (10-min batch, blind to H2/Ar/N2, optical cross-interference, DNV caveats), ABB/Siemens/Emerson/E+H/Servomex gas analyzers + GC combinations, and Chinese domestic MS/PAC vendors. Include ready-to-use sales objection scripts.",
    ),
    (
        "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
        "第03卷：双轨本土化GTM营销方案、定价利润结构、设计院Spec-in与PAC生态合作",
        "Detailed Track A (CO2Sense ¥140-220万) / Track B (VF-QAS-CN ¥320-550万 localized Ex shelter) / Track C (PremierGuard ¥580-950万) BOM & channel split, [ROI-CALC] customer payback tables across S1-S3, STORM 4-persona buying center friction & mitigation, PAC integrator selection criteria (GB/T 3836 Ex, CPA/P2O5/Hg integration), and Design Institute Spec-in playbook.",
    ),
    (
        "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
        "第04卷：商业落地行动路线图（30-60-90天、12-18个月灯塔验证与2027-2031放量预算）",
        "Actionable execution calendar with owners, Austrian HQ (Sigi) support split, PAC & Design Institute milestones, Brevik/Northern Lights Ph2/Stockholm Exergi proof-pack transfer plan, demo/trial unit strategy, KPI kill-gates, and lean BD budget.",
    ),
]


def _format_catalogs_context(state: WorkflowState) -> str:
    mkt = ChinaMarketSizingSummary.model_validate(state["market_sizing_summary"])
    mkt_md = format_market_sizing_table(mkt)
    evaluated = state.get("evaluated_wedges", [])
    eliminated = state.get("eliminated_wedges", [])
    roi_md = format_roi_table(evaluated)
    elim_md = format_eliminated_table(eliminated)

    projects_json = json.dumps(state.get("china_projects_catalog", [])[:16], ensure_ascii=False, indent=2)
    comps_json = json.dumps(state.get("competitors_catalog", [])[:14], ensure_ascii=False, indent=2)
    storm_json = json.dumps(state.get("storm_memos", {}), ensure_ascii=False)[:4200]
    elo_json = json.dumps(state.get("elo_matches", [])[:12], ensure_ascii=False)

    return (
        f"{mkt_md}\n\n{roi_md}\n\n{elim_md}\n\n"
        f"=== VERIFIED CHINA CCUS PROJECTS ===\n{projects_json}\n\n"
        f"=== VERIFIED COMPETITORS ===\n{comps_json}\n\n"
        f"=== 4-PERSONA STORM BUYER FRICTION ===\n{storm_json}\n\n"
        f"=== ELO TOURNAMENT RESULTS ===\n{elo_json}"
    )


async def node_parallel_volume_synthesizer(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 5: Generate all 5 strategic markdown deliverables in parallel."""
    profile = state.get("profile", "flagship")
    tier = "producer" if profile == "flagship" else "fast"
    calc_context = _format_catalogs_context(state)

    siggi_ctx = format_records_compact(deps.vault.list_by_scope("SIGGI"), limit=20)
    cn_ctx = format_records_compact(deps.vault.list_by_scope("CN"), limit=22)
    gl_ctx = format_records_compact(deps.vault.list_by_scope("GLOBAL"), limit=16)

    async def _write_volume(filename: str, cn_title: str, mandate: str) -> tuple[str, str]:
        prompt = (
            f"Target File: {filename}\n"
            f"Chinese Document Title: {cn_title}\n"
            f"Specific Volume Mandate: {mandate}\n\n"
            f"=== DETERMINISTIC PYTHON TABLES ([MKT-CALC] & [ROI-CALC]) ===\n{calc_context}\n\n"
            f"=== SIGGI EVIDENCE ([EV-SIGGI-*]) ===\n{siggi_ctx}\n\n"
            f"=== CHINA EVIDENCE ([EV-CN-*]) ===\n{cn_ctx}\n\n"
            f"=== GLOBAL EVIDENCE ([EV-GL-*]) ===\n{gl_ctx}\n\n"
            "Write a deep, comprehensive, executive-ready Markdown report in Simplified Chinese. "
            "Include inline citations like `[EV-SIGGI-001]`, `[EV-CN-003]`, `[EV-GL-002]` and quote "
            "`[MKT-CALC]` & `[ROI-CALC]` figures accurately without inventing numbers."
        )
        async with deps.semaphore:
            text = await deps.llm.complete_text(
                tier=tier,
                node=f"synth_{filename[:2]}",
                system_prompt=VOLUME_SYNTH_SYSTEM,
                user_prompt=prompt,
                temperature=0.22,
                max_tokens=7200 if profile == "flagship" else 4200,
            )
        return filename, text.strip() + "\n"

    results = await asyncio.gather(*[_write_volume(f, t, m) for f, t, m in VOLUME_SPECS])
    drafts = dict(results)
    return {
        "report_drafts": drafts,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "parallel_volume_synthesizer",
                "volumes_generated": sorted(drafts.keys()),
            }
        ],
    }
