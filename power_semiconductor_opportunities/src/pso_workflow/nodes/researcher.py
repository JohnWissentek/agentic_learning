"""Stage 1 & Stage 2: Parallel Track Researcher, Deterministic Funnel Screener, and Corrective RAG Refill."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import FALSIFICATION_REVIEW_SYSTEM, RESEARCHER_V2_SYSTEM
from pso_workflow.schemas import (
    EvidenceRecord,
    ROIRangeInputs,
    TechOpportunitySeed,
    TrackDossier,
    WorkflowState,
)
from pso_workflow.tools.audit_guard import wrap_untrusted_evidence
from pso_workflow.tools.roi_calculator import screen_candidate_pool

logger = logging.getLogger(__name__)


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
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, BaseException):
            logger.warning("Track %s search task failed: %s", track_id, res)

    all_records = deps.vault.list_by_track(track_id)
    if len(all_records) < 6 and track_name:
        broaden_tasks = [
            _run_one("CN", {"query": f"中国 {track_name} 在线检测 测试仪器 痛点 招标 2025 2026", "scope": "webpage"}),
            _run_one("GLOBAL", {"query": f"{track_name} inline metrology sensor inspection yield bottleneck 2025 2026", "endpoint": "search"}),
        ]
        b_results = await asyncio.gather(*broaden_tasks, return_exceptions=True)
        for res in b_results:
            if isinstance(res, BaseException):
                logger.warning("Track %s broaden search failed: %s", track_id, res)
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
        ft_results = await asyncio.gather(*[_fetch_ft(r) for r in candidates_for_ft], return_exceptions=True)
        for res in ft_results:
            if isinstance(res, BaseException):
                logger.warning("Track %s fulltext fetch failed: %s", track_id, res)
        all_records = deps.vault.list_by_track(track_id)

    return all_records, query_hashes


def _format_evidence_context(
    records: list[EvidenceRecord], max_items: int = 22, *, label: str = "TRACK_EVIDENCE"
) -> str:
    cn_recs = [r for r in records if r.geo_scope == "CN"][: max_items // 2 + 2]
    gl_recs = [r for r in records if r.geo_scope == "GLOBAL"][: max_items // 2 + 2]
    lines: list[str] = []
    for r in cn_recs + gl_recs:
        body = (r.full_markdown[:1200] if r.full_markdown else r.snippet[:500]).replace("\n", " ")
        lines.append(
            f"- [{r.ev_id}] ({r.geo_scope} | {r.authority_tier} | {r.engine} | {r.published_date or 'n/a'}) "
            f"{r.title}\n  URL: {r.url}\n  Content: {body}"
        )
    raw = "\n".join(lines) if lines else "(No external search hits recovered for this track.)"
    return wrap_untrusted_evidence(raw, label=label)


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
    """Strictly validate zero-seed discovered pain points & opportunities without fabricating citations."""
    cn_ids = [r.ev_id for r in records if r.geo_scope == "CN"]
    gl_ids = [r.ev_id for r in records if r.geo_scope == "GLOBAL"]
    valid_ids = {r.ev_id for r in records}

    cleaned_pps = []
    for pp in llm_dossier.pain_points:
        c_evs = [eid for eid in pp.evidence_ids if eid in valid_ids]
        cleaned_pps.append(pp.model_copy(update={"evidence_ids": c_evs}))

    seen_opp_ids: set[str] = set()
    cleaned_opps: list[TechOpportunitySeed] = []
    for idx, opp in enumerate(llm_dossier.opportunities, start=1):
        oid = (opp.opp_id or "").strip()
        if not oid or oid in seen_opp_ids:
            oid = f"{track_id}-O{idx}"
        seen_opp_ids.add(oid)

        # V4.0 Hard Rule: NEVER backfill fallback_ids when LLM provides missing or hallucinated IDs.
        # Ungrounded candidates keep evidence_ids=[] and are eliminated deterministically in Stage 2.
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
                unit_margin_or_scrap_ratio=b.unit_margin_or_scrap_ratio,
                instrument_attribution_share=b.instrument_attribution_share,
                first_year_ramp_factor=b.first_year_ramp_factor,
            )

        cleaned_opps.append(
            opp.model_copy(
                update={
                    "opp_id": oid,
                    "track_id": track_id,
                    "sector": sector,
                    "evidence_ids": cleaned_evs,
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
            "commercial_landscape_summary": llm_dossier.commercial_landscape_summary,
            "pain_points": cleaned_pps,
            "opportunities": cleaned_opps,
            "evidence_count_cn": len(cn_ids),
            "evidence_count_global": len(gl_ids),
            "top_evidence_ids": cn_ids[:4] + gl_ids[:4],
        }
    )


async def run_blank_falsification_check(
    *,
    deps: RuntimeDeps,
    track_id: str,
    sector: Literal["power_energy", "semiconductor"],
    initial_dossier: TrackDossier,
    existing_records: list[EvidenceRecord],
    max_rounds: int = 1,
    max_queries_per_round: int = 4,
) -> tuple[TrackDossier, list[EvidenceRecord], list[str], int]:
    """Bounded falsification search loop verifying claimed commercial blanks before locking dossier."""
    if max_rounds <= 0 or max_queries_per_round <= 0:
        return initial_dossier, existing_records, [], 0

    current_dossier = initial_dossier
    current_records = list(existing_records)
    all_new_hashes: list[str] = []
    rounds_executed = 0

    for _round_idx in range(max_rounds):
        blank_opps = [
            opp
            for opp in current_dossier.opportunities
            if opp.commercial_status in ("global_and_cn_true_blank", "overseas_only_cn_blank")
        ]
        if not blank_opps:
            break

        # Gather explicit LLM-proposed falsification queries first; synthesize bounded fallbacks if omitted
        planned_queries: list[tuple[Literal["CN", "GLOBAL"], str]] = []
        seen_q_keys: set[str] = set()
        for opp in blank_opps:
            for item in opp.falsification_queries:
                q_str = str(item.get("query", "")).strip()
                if not q_str:
                    continue
                geo_raw = str(item.get("geo_scope", "CN")).strip().upper()
                geo: Literal["CN", "GLOBAL"] = "GLOBAL" if geo_raw in ("GLOBAL", "GL") else "CN"
                key = f"{geo}:{q_str}"
                if key not in seen_q_keys:
                    seen_q_keys.add(key)
                    planned_queries.append((geo, q_str))
                    if len(planned_queries) >= max_queries_per_round:
                        break
            if len(planned_queries) >= max_queries_per_round:
                break

        if not planned_queries:
            for opp in blank_opps:
                cn_q = f"中国 {opp.title} 在线检测 商业化 厂商 型号 中标 2025 2026"
                gl_q = f"{opp.title} inline metrology commercial vendor product datasheet model 2025 2026"
                for geo, q_str in (("CN", cn_q), ("GLOBAL", gl_q)):
                    key = f"{geo}:{q_str}"
                    if key not in seen_q_keys and len(planned_queries) < max_queries_per_round:
                        seen_q_keys.add(key)
                        planned_queries.append((geo, q_str))
                if len(planned_queries) >= max_queries_per_round:
                    break

        planned_queries = planned_queries[:max_queries_per_round]
        if not planned_queries:
            break

        existing_ids_before = {r.ev_id for r in current_records}

        async def _run_falsify_query(geo: Literal["CN", "GLOBAL"], q_str: str) -> None:
            qh = hashlib.sha1(f"{geo}:{q_str}".encode("utf-8")).hexdigest()[:12]
            all_new_hashes.append(qh)
            async with deps.semaphore:
                hits = await deps.search_router.search_track(
                    track_id=track_id,
                    geo_scope=geo,
                    query=q_str,
                    mode="webpage" if geo == "CN" else "search",
                    num_results=4,
                )
            deps.vault.log_query(
                track_id=track_id,
                engine="metaso" if geo == "CN" else "serper",
                geo_scope=geo,
                query=q_str,
                hits_count=len(hits),
            )
            for h in hits:
                deps.vault.upsert_hit(track_id=track_id, hit=h)

        f_results = await asyncio.gather(
            *[_run_falsify_query(geo, q_str) for geo, q_str in planned_queries],
            return_exceptions=True,
        )
        for res in f_results:
            if isinstance(res, BaseException):
                logger.warning("Falsification search failed in track %s: %s", track_id, res)

        current_records = deps.vault.list_by_track(track_id)
        newly_added = [r for r in current_records if r.ev_id not in existing_ids_before]

        # Format both newly retrieved falsification evidence and existing track evidence inside untrusted fence
        prioritized_records = newly_added + [r for r in current_records if r.ev_id in existing_ids_before]
        falsify_context = _format_evidence_context(
            prioritized_records,
            max_items=26,
            label=f"FALSIFICATION_{track_id}",
        )
        blank_summary = "\n".join(
            f"- `{o.opp_id}` ({o.commercial_status}): {o.title} | "
            f"Global: {o.global_vendors_and_products} | China: {o.china_vendors_and_products}"
            for o in blank_opps
        )
        user_prompt = (
            f"Track ID: {track_id} | Sector: {sector} | Track Name: {current_dossier.track_name}\n"
            f"Falsification Queries Executed ({len(planned_queries)}):\n"
            + "\n".join(f"  - [{geo}] {q}" for geo, q in planned_queries)
            + f"\n\nInitial Claimed Blank Candidates to Audit:\n{blank_summary}\n\n"
            f"Initial TrackDossier JSON:\n{current_dossier.model_dump_json(indent=2)}\n\n"
            f"Falsification & Track EvidenceVault Records (Newly added IDs: {[r.ev_id for r in newly_added]}):\n"
            f"{falsify_context}\n\n"
            f"Re-evaluate every claimed blank candidate against the newly retrieved evidence. "
            f"Downgrade `commercial_status` honestly if real mass-produced vendors were found, or record "
            f"a concrete `falsification_audit_note` confirming the verified gap. Cite ONLY authentic EV IDs present above."
        )

        async with deps.semaphore:
            revised = await deps.llm.complete_structured(
                tier="producer",
                node=f"falsify_{track_id}",
                system_prompt=FALSIFICATION_REVIEW_SYSTEM,
                user_prompt=user_prompt,
                schema=TrackDossier,
                max_tokens=6400,
            )

        current_dossier = _clean_discovered_dossier(
            llm_dossier=revised,
            track_id=track_id,
            sector=sector,
            records=current_records,
        )
        rounds_executed += 1

    return current_dossier, current_records, all_new_hashes, rounds_executed


async def node_track_researcher(
    state: dict[str, Any], deps: RuntimeDeps
) -> dict[str, Any]:
    """Parallel Send() worker: zero-seed pain-point + vendor search, Markdown read, V4 flagship TrackDossier + bounded falsification."""
    tp = state["track_plan"]
    profile = state.get("profile", "flagship")
    track_id = tp["track_id"]
    sector: Literal["power_energy", "semiconductor"] = tp["sector"]

    num_results = 6 if profile == "flagship" else 3
    max_ft = 6 if profile == "flagship" else 2
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

    ev_context = _format_evidence_context(records, max_items=24, label=f"TRACK_{track_id}_EVIDENCE")
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
        f"Execute V4.0 ZERO-SEED bottom-up discovery:\n"
        f"1. Synthesize `commercial_landscape_summary` identifying overseas vs Chinese commercial equipment incumbents & gaps.\n"
        f"2. Extract concrete `pain_points` (both CN & GLOBAL) and discover {target_cands} high-conviction online instrumentation "
        f"`opportunities` (`opp_id` like `{track_id}-O1`, `{track_id}-O2`, ...) spanning `3-5y` and `5-10y`.\n"
        f"3. For EVERY opportunity, ground `commercial_status` (`global_and_cn_commercialized`, `overseas_only_cn_blank`, "
        f"`global_and_cn_true_blank`), real `global_vendors_and_products`, `china_vendors_and_products`, `white_space_and_entry_wedge`, "
        f"`ai_computational_sensing_and_co_design`, `ai_rd_acceleration_and_edge_deployment`, `estimated_rd_months_ai_vs_legacy`, "
        f"`hardware_bom_localization_and_gtm_form`, `falsification_queries` (for any blank claim), and calibrated `roi_range_inputs` in `[EV-...]` evidence."
    )

    # V4.0 Model-First Rule: flagship mining ALWAYS uses flagship `producer` tier (never downgraded to `fast`)
    miner_tier = "producer" if profile == "flagship" else "producer"
    async with deps.semaphore:
        llm_dossier = await deps.llm.complete_structured(
            tier=miner_tier,
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

    falsify_rounds = 1 if profile == "flagship" else 0
    falsify_executed = 0
    if falsify_rounds > 0:
        final_dossier, records, f_hashes, falsify_executed = await run_blank_falsification_check(
            deps=deps,
            track_id=track_id,
            sector=sector,
            initial_dossier=final_dossier,
            existing_records=records,
            max_rounds=falsify_rounds,
            max_queries_per_round=4,
        )
        q_hashes.extend(f_hashes)

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
                "falsification_rounds": falsify_executed,
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
