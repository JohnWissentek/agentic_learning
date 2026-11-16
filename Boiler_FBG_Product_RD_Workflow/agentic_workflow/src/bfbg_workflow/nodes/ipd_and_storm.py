"""Stage 2-4: Deterministic Calcs + IPD Engineering Review Board + Buyer STORM + Elo Tournament."""

from __future__ import annotations

import asyncio
from typing import Any

from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import ELO_MATCH_SYSTEM, IPD_BOARD_SYSTEM, STORM_BUYER_SYSTEM
from bfbg_workflow.schemas import (
    ArchitectureEloMatch,
    IPDReviewMemo,
    PowerPlantStormPanel,
    WorkflowState,
)
from bfbg_workflow.tools.engineering_and_finance_calc import run_all_deterministic_calcs
from bfbg_workflow.tools.evidence_vault import format_records_compact


def compute_elo_standings(
    arch_ids: list[str], matches: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compute standard Elo ratings (K=32, base=1500) from pairwise tournament outcomes."""
    ratings: dict[str, float] = {aid: 1500.0 for aid in arch_ids}
    wins: dict[str, int] = {aid: 0 for aid in arch_ids}
    for m in matches:
        a = m["arch_a"]
        b = m["arch_b"]
        w = m["winner"]
        if a not in ratings or b not in ratings:
            continue
        k = 40.0 if m.get("margin") == "decisive" else 24.0
        ea = 1.0 / (1.0 + 10.0 ** ((ratings[b] - ratings[a]) / 400.0))
        eb = 1.0 - ea
        sa = 1.0 if w == a else 0.0
        sb = 1.0 - sa
        ratings[a] += k * (sa - ea)
        ratings[b] += k * (sb - eb)
        if w in wins:
            wins[w] += 1

    ranked = sorted(
        (
            {"arch_id": aid, "elo": round(ratings[aid], 1), "wins": wins[aid]}
            for aid in arch_ids
        ),
        key=lambda x: (-x["elo"], -x["wins"]),
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


async def node_calc_ipd_storm_and_elo(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Run PALMs calculations, then launch IPD Review Board, Buyer STORM & Architecture Elo."""
    calc_bundle = run_all_deterministic_calcs(deps.settings.catalog)
    md = calc_bundle.markdown_tables

    all_recs = deps.vault.list_all()
    ev_ctx = format_records_compact(all_recs, limit=36)
    dossiers_summary = "\n".join(
        f"- {d['track_id']} ({d['role_title']}): {d['executive_findings'][:400]}"
        for d in state.get("track_dossiers", [])
    )

    ipd_prompt = (
        "Conduct the 6-role IPD Engineering & Manufacturability Review.\n"
        f"=== [PHY-CALC] ===\n{md['physics_link_md']}\n\n"
        f"=== [BOM-CALC] ===\n{md['bom_matrix_md']}\n\n"
        f"=== SPECIALIST TRACK FINDINGS ===\n{dossiers_summary}\n\n"
        f"=== VERIFIED EVIDENCE ===\n{ev_ctx}"
    )
    storm_prompt = (
        "Conduct the 4-persona Coal Power Plant Buyer STORM Interrogation.\n"
        f"=== [PLANT-ROI] ===\n{md['plant_roi_md']}\n\n"
        f"=== [BOM-CALC] ===\n{md['bom_matrix_md']}\n\n"
        f"=== SPECIALIST TRACK FINDINGS ===\n{dossiers_summary}\n\n"
        f"=== VERIFIED EVIDENCE ===\n{ev_ctx}"
    )

    arch_ids = [a.arch_id for a in calc_bundle.arch_comparisons]
    pairs = [
        (1, arch_ids[0], arch_ids[1]),
        (1, arch_ids[2], arch_ids[3]),
        (2, arch_ids[0], arch_ids[2]),
        (2, arch_ids[0], arch_ids[3]),
        (3, arch_ids[0], arch_ids[4]),
    ]

    async def _run_elo(r_num: int, a_id: str, b_id: str) -> dict[str, Any]:
        e_prompt = (
            f"Swiss Round {r_num}: Compare `{a_id}` vs `{b_id}` for China Coal Boiler FBG Productization.\n"
            f"=== [ARCH COMPARISON] ===\n{md['arch_comparison_md']}\n\n"
            f"=== [PHY-CALC] ===\n{md['physics_link_md']}\n\n"
            "Select winner (`arch_a` or `arch_b` exact arch_id) with concrete engineering rationale."
        )
        res = await deps.llm.complete_json(
            tier="fast",
            node=f"stage4_elo_{a_id}_{b_id}",
            system_prompt=ELO_MATCH_SYSTEM,
            user_prompt=e_prompt,
            schema=ArchitectureEloMatch,
            max_tokens=1500,
        )
        return res.model_dump()

    ipd_task = deps.llm.complete_json(
        tier="producer",
        node="stage3a_ipd_board",
        system_prompt=IPD_BOARD_SYSTEM,
        user_prompt=ipd_prompt,
        schema=IPDReviewMemo,
        max_tokens=3000,
    )
    storm_task = deps.llm.complete_json(
        tier="producer",
        node="stage3b_storm_panel",
        system_prompt=STORM_BUYER_SYSTEM,
        user_prompt=storm_prompt,
        schema=PowerPlantStormPanel,
        max_tokens=3000,
    )
    elo_tasks = [_run_elo(rn, a, b) for rn, a, b in pairs]

    gathered = await asyncio.gather(ipd_task, storm_task, *elo_tasks)
    ipd_memo: IPDReviewMemo = gathered[0]  # type: ignore[assignment]
    storm_panel: PowerPlantStormPanel = gathered[1]  # type: ignore[assignment]
    elo_matches: list[dict[str, Any]] = list(gathered[2:])  # type: ignore[arg-type]
    elo_ranking = compute_elo_standings(arch_ids, elo_matches)

    return {
        "calc_bundle": calc_bundle.model_dump(),
        "ipd_memo": ipd_memo.model_dump(),
        "storm_panel": storm_panel.model_dump(),
        "elo_matches": elo_matches,
        "elo_ranking": elo_ranking,
    }
