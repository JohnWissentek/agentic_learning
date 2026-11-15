"""Stage 1 & Stage 2: Parallel Track Researcher, Deterministic Funnel Screener, and Corrective RAG Refill."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import RESEARCHER_V2_SYSTEM
from pso_workflow.schemas import (
    EvidenceRecord,
    ROIRangeInputs,
    TechOpportunitySeed,
    TrackDossier,
    WorkflowState,
)
from pso_workflow.tools.roi_calculator import screen_candidate_pool


async def _collect_queries_for_track(
    *,
    deps: RuntimeDeps,
    track_id: str,
    track_name: str,
    cn_queries: list[dict[str, str]],
    global_queries: list[dict[str, str]],
    cn_vendor_queries: list[dict[str, str]] | None = None,
    global_vendor_queries: list[dict[str, str]] | None = None,
    num_results: int,
    max_fulltext: int,
) -> tuple[list[EvidenceRecord], list[str]]:
    """Run CN & GLOBAL pain-point + commercial-vendor searches concurrently, enrich Markdown, store in Vault."""
    query_hashes: list[str] = []
    seen_q_keys: set[str] = set()

    async def _run_one(geo: Literal["CN", "GLOBAL"], item: dict[str, str]) -> list[EvidenceRecord]:
        q = str(item.get("query", "")).strip()
        q_key = f"{geo}:{q}"
        if not q or q_key in seen_q_keys:
            return []
        seen_q_keys.add(q_key)
        mode = str(item.get("scope") or item.get("endpoint") or ("webpage" if geo == "CN" else "search"))
        query_hashes.append(hashlib.sha1(q_key.encode("utf-8")).hexdigest()[:12])
        async with deps.semaphore:
            hits = await deps.search_router.search_track(
                track_id=track_id,
                geo_scope=geo,
                query=q,
                mode=mode,
                num_results=num_results,
            )
        deps.vault.log_query(
            track_id=track_id,
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,
            query=q,
            hits_count=len(hits),
        )
        stored: list[EvidenceRecord] = []
        for h in hits:
            rec = deps.vault.upsert_hit(track_id=track_id, hit=h)
            if rec is not None:
                stored.append(rec)
        return stored

    all_cn = list(cn_queries) + list(cn_vendor_queries or [])
    all_gl = list(global_queries) + list(global_vendor_queries or [])
    tasks = [_run_one("CN", q) for q in all_cn] + [
        _run_one("GLOBAL", q) for q in all_gl
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    all_records = deps.vault.list_by_track(track_id)
    if len(all_records) < 6 and track_name:
        broaden_tasks = [
            _run_one("CN", {"query": f"中国 {track_name} 在线检测 测试仪器 痛点 招标 2025 2026", "scope": "webpage"}),
            _run_one("GLOBAL", {"query": f"{track_name} inline metrology sensor inspection yield bottleneck 2025 2026", "endpoint": "search"}),
        ]
        await asyncio.gather(*broaden_tasks, return_exceptions=True)
        all_records = deps.vault.list_by_track(track_id)

    candidates_for_ft = [
        r for r in all_records if not r.full_markdown and r.authority_tier in ("T1", "T2", "T3")
    ][:max_fulltext]

    async def _fetch_ft(rec: EvidenceRecord) -> None:
        async with deps.semaphore:
            md = await deps.search_router.read_fulltext(url=rec.url, track_id=track_id)
        if md:
            from pso_workflow.schemas import SearchHit

            deps.vault.upsert_hit(
                track_id=track_id,
                hit=SearchHit(
                    engine="metaso" if rec.engine == "metaso" else "serper",
                    geo_scope=rec.geo_scope,
                    query=rec.query,
                    title=rec.title,
                    url=rec.url,
                    snippet=rec.snippet,
                    published_date=rec.published_date,
                    authority_tier=rec.authority_tier,
                ),
                full_markdown=md,
            )

    if candidates_for_ft:
        await asyncio.gather(*[_fetch_ft(r) for r in candidates_for_ft], return_exceptions=True)
        all_records = deps.vault.list_by_track(track_id)

    return all_records, query_hashes


def _format_evidence_context(records: list[EvidenceRecord], max_items: int = 22) -> str:
    cn_recs = [r for r in records if r.geo_scope == "CN"][: max_items // 2 + 2]
    gl_recs = [r for r in records if r.geo_scope == "GLOBAL"][: max_items // 2 + 2]
    lines: list[str] = []
    for r in cn_recs + gl_recs:
        body = (r.full_markdown[:900] if r.full_markdown else r.snippet[:450]).replace("\n", " ")
        lines.append(
            f"- [{r.ev_id}] ({r.geo_scope} | {r.authority_tier} | {r.engine} | {r.published_date or 'n/a'}) "
            f"{r.title}\n  URL: {r.url}\n  Content: {body}"
        )
    return "\n".join(lines) if lines else "(No external search hits recovered for this track.)"


def _format_roi_guardrail_hint(guardrails: dict[str, Any], sector: str) -> str:
    g = guardrails.get(sector, {}) or {}
    if not g:
        return "Provide realistic factory-line CAPEX, annual output value, yield gain intervals, OPEX, and TAM."
    return (
        f"Physical Scale Guardrails for `{sector}` (extract interval bounds `roi_range_inputs` anchored to evidence, NOT canned presets):\n"
        f"- CAPEX (CNY): {g.get('capex_cny_min', 150000):,.0f} ~ {g.get('capex_cny_max', 50000000):,.0f}\n"
        f"- Protected Line Annual Output Value (CNY): {g.get('annual_output_value_cny_min', 2e7):,.0f} ~ {g.get('annual_output_value_cny_max', 5e9):,.0f}\n"
        f"- Inline Yield Gain (% pt): {g.get('yield_gain_pct_min', 0.05)} ~ {g.get('yield_gain_pct_max', 5.0)}\n"
        f"- Annual OPEX ratio of CAPEX: {g.get('opex_ratio_min', 0.03)} ~ {g.get('opex_ratio_max', 0.20)}\n"
        f"- China TAM (100M CNY): {g.get('market_tam_china_cny_100m_min', 1.0)} ~ {g.get('market_tam_china_cny_100m_max', 200.0)} | "
        f"Global TAM (M USD): {g.get('market_tam_global_usd_m_min', 20.0)} ~ {g.get('market_tam_global_usd_m_max', 8000.0)}"
    )


def _clean_discovered_dossier(
    *,
    llm_dossier: TrackDossier,
    track_id: str,
    sector: Literal["power_energy", "semiconductor"],
    records: list[EvidenceRecord],
) -> TrackDossier:
    """Validate and clean zero-seed discovered pain points and candidate opportunities."""
    cn_ids = [r.ev_id for r in records if r.geo_scope == "CN"]
    gl_ids = [r.ev_id for r in records if r.geo_scope == "GLOBAL"]
    valid_ids = {r.ev_id for r in records}
    fallback_ids = (cn_ids[:2] + gl_ids[:2]) or [r.ev_id for r in records[:3]]

    cleaned_pps = []
    for pp in llm_dossier.pain_points:
        c_evs = [eid for eid in pp.evidence_ids if eid in valid_ids]
        cleaned_pps.append(pp.model_copy(update={"evidence_ids": c_evs or fallback_ids[:2]}))

    seen_opp_ids: set[str] = set()
    cleaned_opps: list[TechOpportunitySeed] = []
    for idx, opp in enumerate(llm_dossier.opportunities, start=1):
        oid = (opp.opp_id or "").strip()
        if not oid or oid in seen_opp_ids:
            oid = f"{track_id}-O{idx}"
        seen_opp_ids.add(oid)

        cleaned_evs = [eid for eid in opp.evidence_ids if eid in valid_ids]
        rng = opp.roi_range_inputs
        if rng is None and opp.roi_inputs is not None:
            b = opp.roi_inputs
            rng = ROIRangeInputs(
                capex_cny_low=round(b.capex_cny * 0.80, 2),
                capex_cny_base=b.capex_cny,
                capex_cny_high=round(b.capex_cny * 1.25, 2),
                yield_gain_pct_low=round(b.yield_gain_pct * 0.75, 4),
                yield_gain_pct_base=b.yield_gain_pct,
                yield_gain_pct_high=round(b.yield_gain_pct * 1.25, 4),
                annual_output_value_cny=b.annual_output_value_cny,
                annual_opex_cny=b.annual_opex_cny,
                annual_scrap_saving_cny=b.annual_scrap_saving_cny,
                annual_downtime_saving_cny=b.annual_downtime_saving_cny,
                annual_consumable_ehs_saving_cny=b.annual_consumable_ehs_saving_cny,
                market_tam_china_cny_100m=b.market_tam_china_cny_100m,
                market_tam_global_usd_m=b.market_tam_global_usd_m,
                parameter_basis="derived from single-point estimate",
                wacc=b.wacc,
            )

        cleaned_opps.append(
            opp.model_copy(
                update={
                    "opp_id": oid,
                    "track_id": track_id,
                    "sector": sector,
                    "global_vendors_and_products": (
                        opp.global_vendors_and_products
                        or "海内外检索未见公开成熟量产整机型号披露（需在报告中据实标明）"
                    ),
                    "china_vendors_and_products": (
                        opp.china_vendors_and_products
                        or "中国产线商用整机仍处验证或空白阶段（据实检索边界）"
                    ),
                    "white_space_and_entry_wedge": (
                        opp.white_space_and_entry_wedge
                        or "依托 AI 计算传感与旁路微侵入集成形成高性价比切入抓手"
                    ),
                    "ai_computational_sensing_and_co_design": (
                        opp.ai_computational_sensing_and_co_design
                        or "PINNs/AI 逆问题求解与弱信号去噪补偿中端国产传感件极限"
                    ),
                    "ai_rd_acceleration_and_edge_deployment": (
                        opp.ai_rd_acceleration_and_edge_deployment
                        or "物理数字孪生合成缺陷数据 + AI 辅助 FPGA/上位机开发 + 断网 Edge-AI 推理"
                    ),
                    "hardware_bom_localization_and_gtm_form": (
                        opp.hardware_bom_localization_and_gtm_form
                        or "核心传感国产化适配 + 外挂旁路模组/独立在线整机 + 工艺模型库订阅"
                    ),
                    "evidence_ids": cleaned_evs or fallback_ids,
                    "roi_range_inputs": rng,
                    "roi_inputs": rng.to_baseline_inputs() if rng is not None else opp.roi_inputs,
                    "discovery_origin": opp.discovery_origin or "dynamic_evidence_emergence",
                }
            )
        )

    return llm_dossier.model_copy(
        update={
            "track_id": track_id,
            "sector": sector,
            "commercial_landscape_summary": (
                llm_dossier.commercial_landscape_summary
                or f"{llm_dossier.track_name} 商业供给与产品空白摸底（基于 {len(cn_ids)} 条中国 + {len(gl_ids)} 条海外证据）。"
            ),
            "pain_points": cleaned_pps,
            "opportunities": cleaned_opps,
            "evidence_count_cn": len(cn_ids),
            "evidence_count_global": len(gl_ids),
            "top_evidence_ids": cn_ids[:4] + gl_ids[:4],
        }
    )


async def node_track_researcher(
    state: dict[str, Any], deps: RuntimeDeps
) -> dict[str, Any]:
    """Parallel Send() worker: zero-seed pain-point + vendor search, Markdown read, V3 TrackDossier."""
    tp = state["track_plan"]
    profile = state.get("profile", "flagship")
    track_id = tp["track_id"]
    sector: Literal["power_energy", "semiconductor"] = tp["sector"]

    num_results = 6 if profile == "flagship" else 3
    max_ft = 3 if profile == "flagship" else 1
    target_cands = "3-4" if profile == "flagship" else "2-3"

    records, q_hashes = await _collect_queries_for_track(
        deps=deps,
        track_id=track_id,
        track_name=tp.get("name", ""),
        cn_queries=tp.get("cn_queries", []),
        global_queries=tp.get("global_queries", []),
        cn_vendor_queries=tp.get("cn_vendor_queries", []),
        global_vendor_queries=tp.get("global_vendor_queries", []),
        num_results=num_results,
        max_fulltext=max_ft,
    )

    ev_context = _format_evidence_context(records, max_items=22)
    guardrails = deps.settings.discovery_scope.get("sector_roi_guardrails", {}) or {}
    guardrail_hint = _format_roi_guardrail_hint(guardrails, sector)

    user_prompt = (
        f"Track ID: {track_id}\n"
        f"Sector: {sector}\n"
        f"Track Name: {tp['name']}\n"
        f"Emerging/Cross-Cutting Flag: {tp.get('is_emerging_or_cross_cutting', False)} | "
        f"Emergence Rationale: {tp.get('emergence_rationale', '')}\n"
        f"Step-Back Physics Principle: {tp.get('step_back_physics_principle', '')}\n"
        f"Manufacturing Stages: {tp.get('manufacturing_stages', [])}\n\n"
        f"{guardrail_hint}\n\n"
        f"Retrieved EvidenceVault Records (covering BOTH process pain points AND commercial vendor supply):\n{ev_context}\n\n"
        f"Execute V3.0 ZERO-SEED bottom-up discovery:\n"
        f"1. Synthesize `commercial_landscape_summary` identifying overseas vs Chinese commercial equipment incumbents & gaps.\n"
        f"2. Extract concrete `pain_points` (both CN & GLOBAL) and discover {target_cands} high-conviction online instrumentation "
        f"`opportunities` (`opp_id` like `{track_id}-O1`, `{track_id}-O2`, ...) spanning `3-5y` and `5-10y`.\n"
        f"3. For EVERY opportunity, ground `commercial_status` (`global_and_cn_commercialized`, `overseas_only_cn_blank`, "
        f"`global_and_cn_true_blank`), real `global_vendors_and_products`, `china_vendors_and_products`, `white_space_and_entry_wedge`, "
        f"`ai_computational_sensing_and_co_design`, `ai_rd_acceleration_and_edge_deployment`, `estimated_rd_months_ai_vs_legacy`, "
        f"`hardware_bom_localization_and_gtm_form`, and `roi_range_inputs` in `[EV-...]` evidence."
    )

    async with deps.semaphore:
        llm_dossier = await deps.llm.complete_structured(
            tier="fast",
            node=f"researcher_{track_id}",
            system_prompt=RESEARCHER_V2_SYSTEM,
            user_prompt=user_prompt,
            schema=TrackDossier,
            max_tokens=6400,
        )

    final_dossier = _clean_discovered_dossier(
        llm_dossier=llm_dossier,
        track_id=track_id,
        sector=sector,
        records=records,
    )

    return {
        "track_dossiers": [final_dossier.model_dump()],
        "recent_query_hashes": q_hashes,
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": f"researcher_{track_id}",
                "ev_cn": final_dossier.evidence_count_cn,
                "ev_global": final_dossier.evidence_count_global,
                "opportunities_discovered": len(final_dossier.opportunities),
            }
        ],
    }


async def node_deterministic_funnel_screener(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 2 deterministic Python PALMs funnel: clamp ranges, 3-scenario ROI, eliminate & shortlist."""
    dossiers = [TrackDossier(**d) for d in state.get("track_dossiers", [])]
    raw_candidates: list[TechOpportunitySeed] = []
    for d in dossiers:
        raw_candidates.extend(d.opportunities)

    sector_filter = state.get("sector_filter", "all")
    profile = state.get("profile", "flagship")
    funnel_cfg = deps.settings.contract.get("discovery_funnel", {}) or {}
    guardrails = deps.settings.discovery_scope.get("sector_roi_guardrails", {}) or {}

    if sector_filter == "all":
        target_total = int(
            funnel_cfg.get("finalist_shortlist_flagship", 16)
            if profile == "flagship"
            else funnel_cfg.get("finalist_shortlist_fast", 8)
        )
    else:
        target_total = 8 if profile == "flagship" else 4

    max_cons_pb = float(funnel_cfg.get("max_conservative_payback_months", 42.0))

    shortlist, eliminated = screen_candidate_pool(
        raw_candidates,
        sector_filter=sector_filter,
        guardrails=guardrails,
        target_total=target_total,
        max_conservative_payback_months=max_cons_pb,
    )

    return {
        "evaluated_opportunities": [ev.model_dump() for ev in shortlist],
        "raw_candidates_count": len(raw_candidates),
        "eliminated_candidates": [el.model_dump() for el in eliminated],
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "deterministic_funnel_screener",
                "raw_candidates": len(raw_candidates),
                "shortlist_kept": len(shortlist),
                "eliminated_count": len(eliminated),
            }
        ],
    }


async def node_corrective_rag_refill(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Ch 14 Corrective RAG node executed when Critic flags missing evidence gaps."""
    critique = state.get("latest_critique") or {}
    gap_queries = critique.get("gap_queries", [])[:4]
    seen_hashes = set(state.get("recent_query_hashes", []))
    track_plans = state.get("research_plan", {}).get("track_plans", [])
    fallback_tid = str(track_plans[0].get("track_id", "DP1")) if track_plans else "DP1"

    new_hashes: list[str] = []
    added = 0

    for item in gap_queries:
        q = str(item.get("query", "")).strip()
        if not q:
            continue
        geo: Literal["CN", "GLOBAL"] = "GLOBAL" if str(item.get("geo_scope", "")).upper() == "GLOBAL" else "CN"
        track_id = str(item.get("track_id") or fallback_tid)
        qh = hashlib.sha1(f"{geo}:{q}".encode("utf-8")).hexdigest()[:12]
        if qh in seen_hashes:
            continue
        new_hashes.append(qh)
        hits = await deps.search_router.search_track(
            track_id=track_id,
            geo_scope=geo,
            query=q,
            mode="webpage" if geo == "CN" else "search",
            num_results=5,
        )
        deps.vault.log_query(
            track_id=track_id,
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,
            query=q,
            hits_count=len(hits),
        )
        for h in hits:
            if deps.vault.upsert_hit(track_id=track_id, hit=h) is not None:
                added += 1

    return {
        "recent_query_hashes": new_hashes,
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "corrective_rag_refill",
                "gap_queries_run": len(new_hashes),
                "vault_hits_upserted": added,
            }
        ],
    }
