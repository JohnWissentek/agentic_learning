"""Stage 0 & Node 1: Macro Recon Dynamic Track Discovery & Optional HITL Gate (V2.0 Zero-Preset)."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.types import interrupt

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import RECON_DISCOVERY_SYSTEM
from pso_workflow.schemas import (
    DiscoveredTrack,
    DiscoveryPlan,
    EvidenceRecord,
    WorkflowState,
)


def _active_sectors(sector_filter: str) -> list[str]:
    if sector_filter == "power":
        return ["power_energy"]
    if sector_filter == "semiconductor":
        return ["semiconductor"]
    return ["power_energy", "semiconductor"]


def _recon_query_items(
    deps: RuntimeDeps, sector_filter: str, profile: str
) -> list[tuple[Literal["CN", "GLOBAL"], dict[str, str]]]:
    """Collect broad Stage 0 reconnaissance queries from `discovery_scope.yaml`."""
    recon_cfg = deps.settings.discovery_scope.get("macro_recon_queries", {}) or {}
    per_geo_limit = 4 if profile == "flagship" else 2
    items: list[tuple[Literal["CN", "GLOBAL"], dict[str, str]]] = []
    for sec in _active_sectors(sector_filter):
        sec_cfg = recon_cfg.get(sec, {}) or {}
        for q in list(sec_cfg.get("cn_queries", []))[:per_geo_limit]:
            items.append(("CN", dict(q)))
        for q in list(sec_cfg.get("global_queries", []))[:per_geo_limit]:
            items.append(("GLOBAL", dict(q)))
    return items


async def run_macro_recon(
    deps: RuntimeDeps, sector_filter: str, profile: str
) -> tuple[list[EvidenceRecord], list[str]]:
    """Execute broad CN & Global Stage 0 scan and store hits under `track_id='RECON'`."""
    query_items = _recon_query_items(deps, sector_filter, profile)
    num_results = 5 if profile == "flagship" else 3
    query_hashes: list[str] = []

    async def _run_one(geo: Literal["CN", "GLOBAL"], item: dict[str, str]) -> None:
        q = str(item.get("query", "")).strip()
        if not q:
            return
        mode = str(item.get("scope") or item.get("endpoint") or ("webpage" if geo == "CN" else "search"))
        query_hashes.append(hashlib.sha1(f"{geo}:{q}".encode("utf-8")).hexdigest()[:12])
        async with deps.semaphore:
            hits = await deps.search_router.search_track(
                track_id="RECON",
                geo_scope=geo,
                query=q,
                mode=mode,
                num_results=num_results,
            )
        deps.vault.log_query(
            track_id="RECON",
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,
            query=q,
            hits_count=len(hits),
        )
        for hit in hits:
            deps.vault.upsert_hit(track_id="RECON", hit=hit)

    if query_items:
        await asyncio.gather(
            *[_run_one(geo, item) for geo, item in query_items],
            return_exceptions=True,
        )

    return deps.vault.list_by_track("RECON"), query_hashes


def _format_recon_context(records: list[EvidenceRecord], max_items: int = 24) -> str:
    cn_recs = [r for r in records if r.geo_scope == "CN"][: max_items // 2 + 2]
    gl_recs = [r for r in records if r.geo_scope == "GLOBAL"][: max_items // 2 + 2]
    lines: list[str] = []
    for r in cn_recs + gl_recs:
        snippet = r.snippet[:400].replace("\n", " ")
        lines.append(
            f"- [{r.ev_id}] ({r.geo_scope} | {r.authority_tier} | {r.published_date or 'n/a'}) "
            f"{r.title} | Query: {r.query}\n  URL: {r.url}\n  Snippet: {snippet}"
        )
    return "\n".join(lines) if lines else "(No Stage 0 recon snippets returned.)"


def _normalize_discovered_tracks(
    *,
    plan: DiscoveryPlan,
    contract_id: str,
    sector_filter: str,
    profile: str,
    recon_records: list[EvidenceRecord],
) -> DiscoveryPlan:
    """Clean dynamic track IDs, recon evidence IDs, and ensure usable search queries without preset YAML overwrite."""
    valid_recon_ids = {r.ev_id for r in recon_records}
    fallback_recon = (
        [r.ev_id for r in recon_records if r.geo_scope == "CN"][:2]
        + [r.ev_id for r in recon_records if r.geo_scope == "GLOBAL"][:2]
    ) or [r.ev_id for r in recon_records[:3]]

    active = set(_active_sectors(sector_filter))
    q_cap = 3 if profile == "flagship" else 1
    normalized: list[DiscoveredTrack] = []
    seen_ids: set[str] = set()
    p_idx = 1
    s_idx = 1

    for tp in plan.track_plans:
        sec = tp.sector
        if sec not in active:
            continue
        raw_id = (tp.track_id or "").strip()
        if not raw_id or raw_id in seen_ids:
            if sec == "power_energy":
                tid = f"DP{p_idx}"
                p_idx += 1
            else:
                tid = f"DS{s_idx}"
                s_idx += 1
        else:
            tid = raw_id
        seen_ids.add(tid)

        cleaned_evs = [eid for eid in tp.recon_evidence_ids if eid in valid_recon_ids]
        cn_q = [dict(q) for q in tp.cn_queries if str(q.get("query", "")).strip()][:q_cap]
        gl_q = [dict(q) for q in tp.global_queries if str(q.get("query", "")).strip()][:q_cap]
        if not cn_q:
            cn_q = [{"query": f"中国 {tp.name} 在线检测 仪器 产线痛点 ROI 2025 2026", "scope": "webpage"}]
        if not gl_q:
            gl_q = [{"query": f"{tp.name} inline metrology testing market trend 2025 2026", "endpoint": "search"}]

        vendor_cap = 2 if profile == "flagship" else 1
        cn_vq = [dict(q) for q in tp.cn_vendor_queries if str(q.get("query", "")).strip()][:vendor_cap]
        gl_vq = [dict(q) for q in tp.global_vendor_queries if str(q.get("query", "")).strip()][:vendor_cap]
        if not cn_vq:
            cn_vq = [{"query": f"中国 {tp.name} 在线检测 设备 厂商 型号 中标 国产替代 2025 2026", "scope": "webpage"}]
        if not gl_vq:
            gl_vq = [{"query": f"{tp.name} inline metrology testing equipment commercial vendor product model 2025 2026", "endpoint": "search"}]

        normalized.append(
            DiscoveredTrack(
                track_id=tid,
                sector=sec,
                name=tp.name,
                step_back_physics_principle=(
                    tp.step_back_physics_principle
                    or f"围绕 {tp.name} 关键失效物理机理与 AI 软硬协同在线闭环测控。"
                ),
                is_emerging_or_cross_cutting=tp.is_emerging_or_cross_cutting,
                emergence_rationale=tp.emergence_rationale or "由 Stage 0 广谱侦察证据聚类涌现。",
                recon_evidence_ids=cleaned_evs or fallback_recon,
                manufacturing_stages=tp.manufacturing_stages or ["核心制造与在线检测工段"],
                cn_queries=cn_q,
                global_queries=gl_q,
                cn_vendor_queries=cn_vq,
                global_vendor_queries=gl_vq,
            )
        )

    if not normalized:
        raise ValueError(f"Dynamic discovery failed to produce any valid track for sector_filter={sector_filter!r}")

    return DiscoveryPlan(
        contract_id=contract_id,
        sector_filter=sector_filter,
        profile="flagship" if profile == "flagship" else "fast",
        macro_recon_summary=plan.macro_recon_summary or "Stage 0 广谱扫描聚类完成动态赛道定义。",
        step_back_thesis=plan.step_back_thesis,
        track_plans=normalized,
    )


async def node_input_guardrail_and_planner(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Execute Stage 0 macro recon and dynamically emerge orthogonal tracks (`DiscoveryPlan`)."""
    sector_filter = state.get("sector_filter", "all")
    profile = state.get("profile", "flagship")
    contract_id = deps.settings.contract.get("contract_id", "PSO-CONTRACT-2026-V3")
    funnel_cfg = deps.settings.contract.get("discovery_funnel", {}) or {}
    mandate_cfg = deps.settings.discovery_scope.get("sector_mandates", {}) or {}

    recon_records, q_hashes = await run_macro_recon(deps, sector_filter, profile)
    recon_context = _format_recon_context(recon_records)

    active = _active_sectors(sector_filter)
    per_sector = (
        int(funnel_cfg.get("tracks_per_sector_flagship", 4))
        if profile == "flagship"
        else 2
    )
    target_tracks = per_sector * len(active)
    queries_per_geo = 2 if profile == "flagship" else 1
    vendor_q_per_geo = 2 if profile == "flagship" else 1

    mandate_lines = "\n".join(
        f"- {sec} ({mandate_cfg.get(sec, {}).get('display_name', sec)}): "
        f"{mandate_cfg.get(sec, {}).get('scope_description', '').strip()}"
        for sec in active
    )
    user_prompt = (
        f"Contract ID: {contract_id}\n"
        f"Sector Filter: {sector_filter} | Profile: {profile} | Target Dynamic Tracks: {target_tracks} "
        f"({per_sector} tracks per active sector)\n"
        f"Mandate Boundaries (No preset sub-tracks):\n{mandate_lines}\n\n"
        f"Stage 0 Macro Recon EvidenceVault Snippets (`[EV-...]`):\n{recon_context}\n\n"
        f"Cluster these real-time signals into {target_tracks} orthogonal tracks (`DP1..` for `power_energy`, "
        f"`DS1..` for `semiconductor`). Highlight genuinely emerging/cross-cutting inflections "
        f"(`is_emerging_or_cross_cutting=true`, citing `recon_evidence_ids`). "
        f"Generate {queries_per_geo} pain-point/tech `cn_queries` + `global_queries` AND "
        f"{vendor_q_per_geo} commercial-vendor/model/blank `cn_vendor_queries` + `global_vendor_queries` per track."
    )

    raw_plan = await deps.llm.complete_structured(
        tier="producer" if profile == "flagship" else "fast",
        node="planner",
        system_prompt=RECON_DISCOVERY_SYSTEM,
        user_prompt=user_prompt,
        schema=DiscoveryPlan,
        max_tokens=3600,
    )

    final_plan = _normalize_discovered_tracks(
        plan=raw_plan,
        contract_id=contract_id,
        sector_filter=sector_filter,
        profile=profile,
        recon_records=recon_records,
    )

    return {
        "recon_evidence_ids": [r.ev_id for r in recon_records],
        "research_plan": final_plan.model_dump(),
        "recent_query_hashes": q_hashes,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "planner",
                "recon_hits": len(recon_records),
                "tracks_discovered": len(final_plan.track_plans),
                "emerging_tracks": sum(
                    1 for t in final_plan.track_plans if t.is_emerging_or_cross_cutting
                ),
                "profile": profile,
            }
        ],
    }


async def node_hitl_approval_gate(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 13 HITL checkpoint to review Stage 0 dynamically discovered tracks before deep search."""
    if not state.get("hitl_enabled", False):
        return {"hitl_approved": True}

    plan = state.get("research_plan", {})
    approval = interrupt(
        {
            "message": "请审批 Stage 0 动态涌现的赛道清单，确认后进入 Stage 1 零种子并行深挖（Ch 13 HITL）",
            "macro_recon_summary": plan.get("macro_recon_summary", ""),
            "step_back_thesis": plan.get("step_back_thesis", ""),
            "discovered_tracks": [
                {
                    "track_id": t.get("track_id"),
                    "sector": t.get("sector"),
                    "name": t.get("name"),
                    "is_emerging_or_cross_cutting": t.get("is_emerging_or_cross_cutting", False),
                    "emergence_rationale": t.get("emergence_rationale", ""),
                }
                for t in plan.get("track_plans", [])
            ],
        }
    )
    approved = bool(approval.get("approved", True)) if isinstance(approval, dict) else bool(approval)
    return {"hitl_approved": approved}
