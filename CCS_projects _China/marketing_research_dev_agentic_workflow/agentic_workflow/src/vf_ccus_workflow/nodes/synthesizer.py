"""Stage 3a & 3c: Volume-Targeted Full Edition Synthesis & High-Density Executive Distillation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.nodes.planner import format_records_compact
from vf_ccus_workflow.prompts import EXECUTIVE_DISTILLER_SYSTEM, VOLUME_SYNTH_SYSTEM
from vf_ccus_workflow.schemas import WorkflowState

VOLUME_SPECS: list[tuple[str, str, str]] = [
    (
        "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md",
        "总览决策备忘录与核心商业结论",
        "Must directly answer the 4 core executive questions with zero fluff: (1) Real China opportunity verdict vs pseudo-demand/eliminated food-CO2 trap; (2) [MKT-CALC] China 2026-2030 & 2031-2036 TAM/SAM/SOM summary including Track B & Track C; (3) Competitive positioning vs Thermo MAX-iR/MAX-Bev, ABB/Siemens/GC & domestic MS; (4) Dual-Track A/B/C commercial model & GO/NO-GO decision.",
    ),
    (
        "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md",
        "第01卷：中国CCS/CCUS市场规模测算、重点项目图谱与化学腐蚀防毒刚需分析",
        "Present Python [MKT-CALC] bottom-up tables verbatim (preserving sub-segment & Track B/C breakdown), full catalog of verified Chinese CCUS/EOR/e-Methanol/LCO2 ship projects, Shell/IFE 2024 H2SO4/HNO3 pitting kinetics & catalyst poisoning science proving WHY ~1s IMR-MS is needed, plus Stage 2 eliminated/pseudo-demand wedges.",
    ),
    (
        "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md",
        "第02卷：国内外竞争格局对比与一线技术销售Battlecards（防爆/FTIR/GC/国产替代）",
        "Rigorous technical & commercial battlecards against Overseas Process MS, Thermo Fisher MAX-iR / MAX-Bev (10-min batch, blind to H2/Ar/N2, optical cross-interference, DNV caveats), ABB/Siemens/Emerson/E+H/Servomex gas analyzers + GC combinations, and Chinese domestic MS/PAC vendors. Include ready-to-use sales objection scripts.",
    ),
    (
        "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md",
        "第03卷：双轨本土化GTM营销方案、定价利润结构、设计院Spec-in与PAC生态合作",
        "Detailed Track A (CO2Sense ¥140-220万) / Track B (VF-QAS-CN ¥320-550万 localized Ex shelter) / Track C (PremierGuard ¥580-950万) BOM & channel split, [ROI-CALC] customer payback tables across S1-S3, consolidated 4-persona buying-center resistance & mitigation matrix, PAC integrator selection criteria (GB/T 3836 Ex, CPA/P2O5/Hg integration), and Design Institute Spec-in playbook.",
    ),
    (
        "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md",
        "第04卷：商业落地行动路线图（30-60-90天、12-18个月灯塔验证与2027-2031放量预算）",
        "Actionable execution calendar with owners, Austrian HQ (Sigi) support split, PAC & Design Institute milestones, Brevik/Northern Lights Ph2/Stockholm Exergi proof-pack transfer plan, demo/trial unit strategy, KPI kill-gates, and lean BD budget.",
    ),
]

VOLUME_TRACK_ROUTING: dict[str, list[str]] = {
    "00_EXECUTIVE_DECISION_MEMO_AND_VERDICT.md": ["SIGGI_BASE", "RECON", "T1_EOR_PIPE", "T2_LCO2_SHIP", "T3_GREEN_MEOH", "T6_FOOD_CTRL"],
    "01_CHINA_CCUS_MARKET_SIZING_AND_PAIN_POINTS.md": ["T1_EOR_PIPE", "T2_LCO2_SHIP", "T3_GREEN_MEOH", "T4_AMINE_RD", "T6_FOOD_CTRL"],
    "02_COMPETITIVE_LANDSCAPE_AND_BATTLECARDS.md": ["T5_COMP_PAC", "SIGGI_BASE"],
    "03_COMMERCIAL_GTM_PRICING_AND_PARTNERSHIP_PLAN.md": ["T5_COMP_PAC", "T1_EOR_PIPE", "T3_GREEN_MEOH", "T4_AMINE_RD"],
    "04_ACTION_ROADMAP_30_60_90_AND_12_24M.md": ["T1_EOR_PIPE", "T2_LCO2_SHIP", "T3_GREEN_MEOH", "T5_COMP_PAC", "SIGGI_BASE"],
}


def collect_priority_ev_ids_for_volume(state: WorkflowState, volume_name: str) -> set[str]:
    """Gather all EV IDs cited by structured catalogs relevant to a given volume."""
    ids: set[str] = set()
    for w in state.get("evaluated_wedges", []):
        ids.update(w.get("seed", {}).get("evidence_ids", []))
    for el in state.get("eliminated_wedges", []):
        ids.update(el.get("evidence_ids", []))
    if volume_name.startswith(("00_", "01_", "04_")):
        for p in state.get("china_projects_catalog", []):
            ids.update(p.get("evidence_ids", []))
    if volume_name.startswith(("00_", "02_", "03_")):
        for c in state.get("competitors_catalog", []):
            ids.update(c.get("evidence_ids", []))
        for pac in state.get("pac_integrators_catalog", []):
            ids.update(pac.get("evidence_ids", []))
    return ids


async def node_parallel_volume_synthesizer(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 3a: Generate all 5 Full Detailed Volumes in parallel with volume-targeted evidence bundles."""
    profile = state.get("profile", "flagship")
    fact_sheet = state.get("executive_fact_sheet", "")

    async def _write_volume(filename: str, cn_title: str, mandate: str) -> tuple[str, str]:
        priority_ids = collect_priority_ev_ids_for_volume(state, filename)
        routed_tracks = VOLUME_TRACK_ROUTING.get(filename, [])
        ev_records = deps.vault.build_volume_evidence_bundle(
            volume_name=filename,
            track_ids=routed_tracks,
            priority_ev_ids=priority_ids,
            limit=80,
        )
        ev_ctx = format_records_compact(ev_records, limit=80)

        prompt = (
            f"Target File (Full Detailed Edition / 原始详版): {filename}\n"
            f"Chinese Document Title: {cn_title}\n"
            f"Specific Volume Mandate: {mandate}\n\n"
            f"=== LOCKED EXECUTIVE FACT SHEET ([MKT-CALC] & [ROI-CALC] SINGLE SOURCE OF TRUTH) ===\n"
            f"{fact_sheet}\n\n"
            f"=== VOLUME-ROUTED VERIFIED EVIDENCE BUNDLE ({len(ev_records)} records) ===\n{ev_ctx}\n\n"
            "Write a deep, technically rigorous, executive-ready Full Edition Markdown report in Simplified Chinese. "
            "Cite valid `[EV-SIGGI-*]`, `[EV-CN-*]`, `[EV-GL-*]` inline and quote `[MKT-CALC]` & `[ROI-CALC]` verbatim."
        )
        async with deps.semaphore:
            text = await deps.llm.complete_text(
                tier="producer",
                node=f"synth_full_{filename[:2]}",
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


async def distill_executive_edition(
    *,
    full_drafts: dict[str, str],
    fact_sheet: str,
    deps: RuntimeDeps,
) -> dict[str, str]:
    """Distill all 5 audited Full Volumes in parallel into High-Density Executive Editions (2500-5500 chars)."""
    spec_map = {f: (t, m) for f, t, m in VOLUME_SPECS}

    async def _distill_one(filename: str) -> tuple[str, str]:
        full_text = full_drafts.get(filename, "")
        cn_title, _ = spec_map.get(filename, (filename, ""))
        prompt = (
            f"Source Volume: {filename} ({cn_title})\n"
            f"Target Output: High-Density Executive Edition（高密度高管版，目标 2,500–5,500 字）\n\n"
            f"=== LOCKED FACT SHEET ([MKT-CALC] & [ROI-CALC] VERBATIM ANCHOR) ===\n{fact_sheet}\n\n"
            f"=== COMPLETE AUDITED FULL VOLUME (100% FULL TEXT) ===\n{full_text}\n\n"
            "Distill into a crisp, boardroom-ready High-Density Executive Edition preserving ALL exact "
            "`[MKT-CALC]` / `[ROI-CALC]` figures, Track A/B/C architecture, eliminated pseudo-demand controls, "
            "and ONLY valid `[EV-*]` citations from the source."
        )
        async with deps.semaphore:
            text = await deps.llm.complete_text(
                tier="producer",
                node=f"distill_exec_{filename[:2]}",
                system_prompt=EXECUTIVE_DISTILLER_SYSTEM,
                user_prompt=prompt,
                temperature=0.15,
                max_tokens=3600,
            )
        return filename, text.strip() + "\n"

    pairs = await asyncio.gather(*[_distill_one(f) for f, _, _ in VOLUME_SPECS if f in full_drafts])
    return dict(pairs)
