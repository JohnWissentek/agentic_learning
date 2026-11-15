"""Node 2: Parallel Dual-Engine Track Researcher & Corrective RAG Refill (Ch 3, Ch 14)."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import RESEARCHER_SYSTEM
from pso_workflow.schemas import (
    EvidenceRecord,
    ROIInputs,
    TechOpportunitySeed,
    TrackDossier,
    WorkflowState,
)


def _track_config(deps: RuntimeDeps, track_id: str) -> dict[str, Any]:
    for t in deps.settings.taxonomy.get("tracks", []):
        if t.get("id") == track_id:
            return t
    return {}


async def _collect_queries_for_track(
    *,
    deps: RuntimeDeps,
    track_id: str,
    cn_queries: list[dict[str, str]],
    global_queries: list[dict[str, str]],
    num_results: int,
    max_fulltext: int,
) -> tuple[list[EvidenceRecord], list[str]]:
    """Run CN & GLOBAL searches concurrently, enrich top hits with Markdown, store in Vault."""
    query_hashes: list[str] = []

    async def _run_one(geo: Literal["CN", "GLOBAL"], item: dict[str, str]) -> list[EvidenceRecord]:
        q = item.get("query", "").strip()
        if not q:
            return []
        mode = item.get("scope") or item.get("endpoint") or ("webpage" if geo == "CN" else "search")
        query_hashes.append(hashlib.sha1(f"{geo}:{q}".encode("utf-8")).hexdigest()[:12])
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

    tasks = [_run_one("CN", q) for q in cn_queries] + [
        _run_one("GLOBAL", q) for q in global_queries
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Pull full Markdown on highest-authority hits that don't yet have fulltext
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

    # Ignore unused exception objects safely
    _ = results
    return all_records, query_hashes


def _format_evidence_context(records: list[EvidenceRecord], max_items: int = 18) -> str:
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


def _merge_baseline_opportunities(
    *,
    llm_dossier: TrackDossier,
    raw_cfg: dict[str, Any],
    records: list[EvidenceRecord],
) -> TrackDossier:
    """Ensure every baseline domain opportunity is preserved with verified citations and valid ROI."""
    cn_ids = [r.ev_id for r in records if r.geo_scope == "CN"]
    gl_ids = [r.ev_id for r in records if r.geo_scope == "GLOBAL"]
    valid_ids = {r.ev_id for r in records}
    fallback_ids = (cn_ids[:2] + gl_ids[:2]) or [r.ev_id for r in records[:3]]

    by_id = {opp.opp_id: opp for opp in llm_dossier.opportunities}
    merged: list[TechOpportunitySeed] = []

    for base in raw_cfg.get("seed_opportunities", []):
        oid = base["opp_id"]
        llm_opp = by_id.pop(oid, None)
        base_roi = ROIInputs(**base["roi_baseline"])
        if llm_opp is not None:
            cleaned_evs = [eid for eid in llm_opp.evidence_ids if eid in valid_ids]
            merged.append(
                llm_opp.model_copy(
                    update={
                        "track_id": llm_dossier.track_id,
                        "sector": llm_dossier.sector,
                        "evidence_ids": cleaned_evs or fallback_ids,
                        "roi_inputs": base_roi,  # Anchor financial inputs to calibrated industry baselines
                    }
                )
            )
        else:
            merged.append(
                TechOpportunitySeed(
                    opp_id=oid,
                    track_id=llm_dossier.track_id,
                    sector=llm_dossier.sector,
                    title=base["title"],
                    horizon=base["horizon"],
                    china_priority_score=float(base.get("china_priority_score", 90)),
                    global_priority_score=float(base.get("global_priority_score", 88)),
                    physics_principle=base["physics_principle"],
                    target_process_point=raw_cfg.get("manufacturing_stages", ["产线关键工段"])[0],
                    product_form_factor="在线/旁路工业集成分析仪",
                    quality_yield_mechanism="实时阻断批量不良与缺陷逃逸，直接提升一次良率",
                    cost_tco_mechanism="减少离线抽检滞后报废、高价耗材与非计划停线损失",
                    green_ehs_mechanism="精准控耗减排与痕量有害介质实时泄漏防护",
                    industrial_upgrade_mechanism="支撑高端产线闭环自控与国产核心量检测装备自主可控",
                    china_positioning="中国头部产线痛点切入与国产替代示范",
                    global_expansion_path="随中国产业链出海及对标国际一线晶圆/电力标准",
                    evidence_ids=fallback_ids,
                    roi_inputs=base_roi,
                )
            )

    # Keep any genuinely new LLM-discovered opportunities (up to 1 extra per track)
    for extra in list(by_id.values())[:1]:
        cleaned_evs = [eid for eid in extra.evidence_ids if eid in valid_ids]
        merged.append(
            extra.model_copy(
                update={
                    "track_id": llm_dossier.track_id,
                    "sector": llm_dossier.sector,
                    "evidence_ids": cleaned_evs or fallback_ids,
                }
            )
        )

    # Clean evidence IDs on pain points too
    cleaned_pps = []
    for pp in llm_dossier.pain_points:
        c_evs = [eid for eid in pp.evidence_ids if eid in valid_ids]
        cleaned_pps.append(pp.model_copy(update={"evidence_ids": c_evs or fallback_ids[:2]}))

    return llm_dossier.model_copy(
        update={
            "pain_points": cleaned_pps,
            "opportunities": merged,
            "evidence_count_cn": len(cn_ids),
            "evidence_count_global": len(gl_ids),
            "top_evidence_ids": (cn_ids[:4] + gl_ids[:4]),
        }
    )


async def node_track_researcher(
    state: dict[str, Any], deps: RuntimeDeps
) -> dict[str, Any]:
    """Parallel Send() worker: search, read fulltext, store in Vault, compress TrackDossier."""
    tp = state["track_plan"]
    profile = state.get("profile", "flagship")
    track_id = tp["track_id"]
    raw_cfg = _track_config(deps, track_id)

    num_results = 6 if profile == "flagship" else 3
    max_ft = 3 if profile == "flagship" else 1

    records, q_hashes = await _collect_queries_for_track(
        deps=deps,
        track_id=track_id,
        cn_queries=tp.get("cn_queries", []),
        global_queries=tp.get("global_queries", []),
        num_results=num_results,
        max_fulltext=max_ft,
    )

    ev_context = _format_evidence_context(records)
    seeds_text = "\n".join(
        f"- {s['opp_id']} [{s['horizon']}]: {s['title']} | physics={s['physics_principle']} | roi={s['roi_baseline']}"
        for s in raw_cfg.get("seed_opportunities", [])
    )

    user_prompt = (
        f"Track ID: {track_id}\n"
        f"Sector: {tp['sector']}\n"
        f"Track Name: {tp['name']}\n"
        f"Step-Back Physics Principle: {tp.get('step_back_physics_principle', '')}\n"
        f"Manufacturing Stages: {raw_cfg.get('manufacturing_stages', [])}\n\n"
        f"Calibrated Seed Opportunities (refine and enrich with verified evidence IDs; you may add at most 1 newly discovered opportunity if strongly backed by retrieved evidence):\n{seeds_text}\n\n"
        f"Retrieved EvidenceVault Records:\n{ev_context}\n\n"
        f"Produce a strictly grounded `TrackDossier` in Simplified Chinese with `pain_points` covering both CN and GLOBAL, and `opportunities` preserving the calibrated `opp_id`s."
    )

    async with deps.semaphore:
        llm_dossier = await deps.llm.complete_structured(
            tier="fast",
            node=f"researcher_{track_id}",
            system_prompt=RESEARCHER_SYSTEM,
            user_prompt=user_prompt,
            schema=TrackDossier,
            max_tokens=5000,
        )

    final_dossier = _merge_baseline_opportunities(
        llm_dossier=llm_dossier, raw_cfg=raw_cfg, records=records
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
                "opportunities": len(final_dossier.opportunities),
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
    new_hashes: list[str] = []
    added = 0

    for item in gap_queries:
        q = str(item.get("query", "")).strip()
        if not q:
            continue
        geo: Literal["CN", "GLOBAL"] = "GLOBAL" if str(item.get("geo_scope", "")).upper() == "GLOBAL" else "CN"
        track_id = str(item.get("track_id") or "P1")
        qh = hashlib.sha1(f"{geo}:{q}".encode("utf-8")).hexdigest()[:12]
        if qh in seen_hashes:
            continue  # Loop safety guard against duplicate query thrashing
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
