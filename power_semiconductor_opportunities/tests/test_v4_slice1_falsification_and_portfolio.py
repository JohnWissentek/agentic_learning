"""Black-box contract tests for V4.0 Slice 1: Flagship Falsification Loop & Sector Portfolio Review.

Locked RED-phase specification verifying:
1. Flagship brain upgrade in `node_track_researcher` (`tier="producer"`, never downgraded to `"fast"`).
2. Bounded falsification loop (`run_blank_falsification_check`) for claimed commercial blanks:
   - Executes bounded search queries (`1 <= calls <= max_queries_per_round`), persists hits to SQLite
     EvidenceVault, runs 1 flagship (`tier="producer"`) review round, preserves downgraded status &
     `falsification_audit_note`, and strips hallucinated evidence IDs without fabricating fallbacks.
   - Generates fallback falsification queries when seeds omit `falsification_queries`.
   - Zero search & zero LLM calls when all candidates are already `global_and_cn_commercialized`.
   - Strictly bounded when `max_rounds=0` (no infinite loop, 0 calls).
3. Unified sector buying-committee & portfolio prioritization (`node_sector_portfolio_reviewer`):
   - Dual-sector (4 power_energy + 4 semiconductor) uses `<= 3` total LLM calls, all `tier="producer"`.
   - Sector review prompt embeds all sector `opp_id`s, 3-scenario `[ROI-CALC]` paybacks,
     `commercial_status` + `falsification_audit_note`, and `[UNTRUSTED_EXTERNAL_DATA_START:` framed
     EvidenceVault snippets.
   - Writes 4-persona `storm_memos`, `portfolio_role`, and `composite_rank=1..8` back to
     `evaluated_opportunities`, matching `ordered_opp_ids` with zero candidate loss (even when LLM
     omits, duplicates, or hallucinates `opp_id`s).
4. Single-sector optimization: only 1 `SectorPortfolioReview` LLM call (no cross-sector ranking call)
   and empty-shortlist zero-call guard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Type, TypeVar

import pytest
from pydantic import BaseModel

from pso_workflow.config import CostLedger, WorkflowSettings
from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.nodes.portfolio_reviewer import node_sector_portfolio_reviewer
from pso_workflow.nodes.researcher import node_track_researcher, run_blank_falsification_check
from pso_workflow.schemas import (
    BuyerPersonaAssessment,
    EvaluatedOpportunity,
    EvidenceRecord,
    GlobalPortfolioRanking,
    PainPointItem,
    PortfolioCandidateReview,
    RangeROIMetrics,
    ROIInputs,
    ROIMetrics,
    ROIRangeInputs,
    SearchHit,
    SectorPortfolioReview,
    TechOpportunitySeed,
    TrackDossier,
    WorkflowState,
)
from pso_workflow.tools.evidence_vault import EvidenceVault

TModel = TypeVar("TModel", bound=BaseModel)

_BUYER_ROLES: tuple[
    Literal[
        "Fab/Plant Yield VP",
        "Metrology/Process Chief Engineer",
        "EHS & Green Compliance Director",
        "CFO / Procurement ROI Gatekeeper",
    ],
    ...,
] = (
    "Fab/Plant Yield VP",
    "Metrology/Process Chief Engineer",
    "EHS & Green Compliance Director",
    "CFO / Procurement ROI Gatekeeper",
)

_PORTFOLIO_ROLES: tuple[
    Literal[
        "near_term_cash_cow",
        "strategic_localization_wedge",
        "frontier_white_space_bet",
        "defensive_upgrade",
    ],
    ...,
] = (
    "near_term_cash_cow",
    "strategic_localization_wedge",
    "frontier_white_space_bet",
    "defensive_upgrade",
)


# ---------------------------------------------------------------------------
# Deterministic Recording Fakes & Test Builders
# ---------------------------------------------------------------------------


@dataclass
class RecordedLLMCall:
    kind: Literal["structured", "text"]
    tier: str
    node: str
    schema: type[BaseModel] | None
    system_prompt: str
    user_prompt: str


class RecordingSearchRouter:
    """Offline SearchRouter stub recording every query and returning deterministic SearchHits."""

    def __init__(self, *, prefix: str = "falsify") -> None:
        self.prefix = prefix
        self.calls: list[dict[str, Any]] = []
        self.fulltext_calls: list[str] = []

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: Literal["CN", "GLOBAL"],
        query: str,
        mode: str = "webpage",
        num_results: int = 8,
    ) -> list[SearchHit]:
        idx = len(self.calls) + 1
        self.calls.append(
            {
                "track_id": track_id,
                "geo_scope": geo_scope,
                "query": query,
                "mode": mode,
                "num_results": num_results,
            }
        )
        domain = "miit.gov.cn" if geo_scope == "CN" else "kla.com"
        engine: Literal["metaso", "serper"] = "metaso" if geo_scope == "CN" else "serper"
        return [
            SearchHit(
                engine=engine,
                geo_scope=geo_scope,
                query=query,
                title=f"[{self.prefix}-{idx}] {track_id} {geo_scope} Vendor & Commercial Evidence",
                url=f"https://{domain}/{self.prefix}/{track_id.lower()}/{geo_scope.lower()}/{idx}",
                snippet=(
                    f"FALSIFICATION_HIT_{idx}: Commercial vendor check for {track_id} ({geo_scope}) "
                    f"matching query '{query[:48]}'."
                ),
                published_date="2026-06-18",
            )
        ]

    async def read_fulltext(self, *, url: str, track_id: str) -> str:
        self.fulltext_calls.append(url)
        return f"# Fulltext for {track_id}\n\nVerified commercial status details from {url}."


class RecordingLLMClient:
    """Offline LLMClientProtocol stub recording tiers/prompts and dispatching deterministic outputs."""

    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self.calls: list[RecordedLLMCall] = []

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 6000,
    ) -> str:
        rec = RecordedLLMCall(
            kind="text",
            tier=tier,
            node=node,
            schema=None,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        self.calls.append(rec)
        return str(self._handler(rec))

    async def complete_structured(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        temperature: float = 0.15,
        max_tokens: int = 6000,
    ) -> TModel:
        rec = RecordedLLMCall(
            kind="structured",
            tier=tier,
            node=node,
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        self.calls.append(rec)
        result = self._handler(rec)
        assert isinstance(result, schema), f"Test stub returned {type(result)!r}, expected {schema!r}"
        return result


def _make_deps(
    tmp_path: Path,
    *,
    llm_handler: Any,
    search_router: RecordingSearchRouter | None = None,
    db_name: str = "test_vault.db",
) -> tuple[RuntimeDeps, RecordingSearchRouter, RecordingLLMClient]:
    settings = WorkflowSettings(
        root_dir=tmp_path,
        concurrency=4,
        data_dir=tmp_path,
        vault_db_name=db_name,
        discovery_scope={
            "sector_roi_guardrails": {
                "power_energy": {"capex_cny_min": 200_000, "capex_cny_max": 12_000_000},
                "semiconductor": {"capex_cny_min": 800_000, "capex_cny_max": 45_000_000},
            }
        },
        contract={"contract_id": "PSO-CONTRACT-2026-V4"},
    )
    vault = EvidenceVault(tmp_path / db_name)
    router = search_router or RecordingSearchRouter()
    llm = RecordingLLMClient(llm_handler)
    deps = RuntimeDeps(
        settings=settings,
        ledger=CostLedger(),
        vault=vault,
        search_router=router,
        llm=llm,
    )
    return deps, router, llm


def _seed_vault_record(
    vault: EvidenceVault,
    *,
    track_id: str,
    geo_scope: Literal["CN", "GLOBAL"],
    slug: str,
    snippet: str,
) -> EvidenceRecord:
    domain = "sgcc.com.cn" if geo_scope == "CN" else "semi.org"
    engine: Literal["metaso", "serper"] = "metaso" if geo_scope == "CN" else "serper"
    rec = vault.upsert_hit(
        track_id=track_id,
        hit=SearchHit(
            engine=engine,
            geo_scope=geo_scope,
            query=f"seed query {track_id} {geo_scope}",
            title=f"{track_id} {geo_scope} Authoritative Source {slug}",
            url=f"https://{domain}/{track_id.lower()}/{slug}",
            snippet=snippet,
            published_date="2026-04-10",
        ),
    )
    assert rec is not None
    return rec


def _make_seed(
    *,
    opp_id: str,
    track_id: str,
    sector: Literal["power_energy", "semiconductor"],
    commercial_status: Literal[
        "global_and_cn_commercialized",
        "overseas_only_cn_blank",
        "global_and_cn_true_blank",
    ] = "overseas_only_cn_blank",
    evidence_ids: list[str] | None = None,
    falsification_queries: list[dict[str, str]] | None = None,
    falsification_audit_note: str = "",
) -> TechOpportunitySeed:
    return TechOpportunitySeed(
        opp_id=opp_id,
        track_id=track_id,
        sector=sector,
        title=f"{opp_id} 在线传感与量测仪器机会",
        horizon="3-5y",
        china_priority_score=89.0,
        global_priority_score=84.0,
        physics_principle="拉曼光谱与高频电磁场耦合原位在线探测",
        target_process_point="关键量产工艺段 100% 在线全检闭环",
        product_form_factor="机台集成式原位传感模组 + 边缘计算箱",
        quality_yield_mechanism="微秒级捕捉工艺漂移并拦截批量报废",
        cost_tco_mechanism="替代离线破坏性抽检并压缩复判成本",
        green_ehs_mechanism="降低危化品泄漏风险与返工能耗",
        industrial_upgrade_mechanism="攻克国产高端在线量测装备卡脖子空白",
        china_positioning="优先切入国内头部产线验证并实现国产替代标配",
        global_expansion_path="依托 AI 算法与高性价比优势出海欧洲及东南亚",
        commercial_status=commercial_status,
        global_vendors_and_products="KLA / Bruker 存在高价离线或部分在线方案",
        china_vendors_and_products="国内尚无成熟量产在线全检商业整机",
        white_space_and_entry_wedge="AI 计算传感补偿中端国产核心传感器件",
        ai_computational_sensing_and_co_design="PINNs 逆问题实时反演与弱信号增强",
        ai_rd_acceleration_and_edge_deployment="数字孪生缺陷合成 + FPGA 边缘推理",
        estimated_rd_months_ai_vs_legacy="14个月 (AI原生协同) vs 30个月 (传统串行研发)",
        hardware_bom_localization_and_gtm_form="国产光学/射频核心件 + 独立整机交付",
        evidence_ids=list(evidence_ids) if evidence_ids is not None else ["EV-CN-001"],
        roi_range_inputs=ROIRangeInputs(
            capex_cny_low=1_200_000.0,
            capex_cny_base=1_500_000.0,
            capex_cny_high=1_900_000.0,
            yield_gain_pct_low=1.2,
            yield_gain_pct_base=1.8,
            yield_gain_pct_high=2.4,
            annual_output_value_cny=900_000_000.0,
            annual_opex_cny=140_000.0,
            annual_scrap_saving_cny=420_000.0,
            annual_downtime_saving_cny=210_000.0,
            annual_consumable_ehs_saving_cny=110_000.0,
            market_tam_china_cny_100m=24.0,
            market_tam_global_usd_m=680.0,
            parameter_basis="deterministic test fixture",
            wacc=0.10,
        ),
        falsification_queries=list(falsification_queries or []),
        falsification_audit_note=falsification_audit_note,
    )


def _make_dossier(
    *,
    track_id: str,
    sector: Literal["power_energy", "semiconductor"],
    opportunities: list[TechOpportunitySeed],
    evidence_ids: list[str],
) -> TrackDossier:
    return TrackDossier(
        track_id=track_id,
        sector=sector,
        track_name=f"{track_id} 关键在线量测赛道",
        commercial_landscape_summary="海外巨头主导高端产线，国产在线闭环方案存在结构性空白。",
        china_market_dynamics="国内头部产线扩产与良率压力驱动国产在线检测导入。",
        global_market_dynamics="全球先进制程与新型电力系统加速实时原位传感部署。",
        horizon_3_5y_outlook="3-5年聚焦国产替代与单点工艺闭环量测。",
        horizon_5_10y_outlook="5-10年演进为全厂级 AI 计算传感与预测控制网络。",
        pain_points=[
            PainPointItem(
                process_stage="核心工艺在线质控",
                geo_scope="CN",
                pain_description="离线抽检滞后导致整批报废风险。",
                current_limitation="进口设备昂贵且交付周期超过 12 个月。",
                impact_pillars=["质量良率", "成本TCO"],
                evidence_ids=list(evidence_ids),
            )
        ],
        opportunities=opportunities,
        evidence_count_cn=sum(1 for eid in evidence_ids if eid.startswith("EV-CN-")),
        evidence_count_global=sum(1 for eid in evidence_ids if eid.startswith("EV-GL-")),
        top_evidence_ids=list(evidence_ids),
    )


def _make_buyer_assessments(opp_id: str) -> list[BuyerPersonaAssessment]:
    return [
        BuyerPersonaAssessment(
            persona_role=role,
            core_question=f"[{opp_id}] {role} 关注在线精度、稳定性与投资回报。",
            adoption_barrier=f"[{opp_id}] {role} 担忧首台套产线导入验证周期。",
            spec_in_trigger=f"[{opp_id}] {role} 要求连续 72 小时量产线盲测达标。",
            recommended_product_tweak=f"[{opp_id}] {role} 建议提供标准 SECS/GEM 或 IEC61850 接口。",
        )
        for role in _BUYER_ROLES
    ]


def _make_evaluated_opp_dict(
    *,
    opp_id: str,
    track_id: str,
    sector: Literal["power_energy", "semiconductor"],
    commercial_status: Literal[
        "global_and_cn_commercialized",
        "overseas_only_cn_blank",
        "global_and_cn_true_blank",
    ],
    falsification_audit_note: str,
    evidence_ids: list[str],
    optimistic_payback: float,
    baseline_payback: float,
    conservative_payback: float,
    weighted_pillar_score: float,
) -> dict[str, Any]:
    seed = _make_seed(
        opp_id=opp_id,
        track_id=track_id,
        sector=sector,
        commercial_status=commercial_status,
        evidence_ids=evidence_ids,
        falsification_audit_note=falsification_audit_note,
    )
    base_roi = ROIMetrics(
        capex_cny=4_800_000.0,
        annual_opex_cny=360_000.0,
        yield_gain_saving_cny=1_900_000.0,
        annual_gross_benefit_cny=2_600_000.0,
        net_annual_cashflow_cny=2_240_000.0,
        payback_months=baseline_payback,
        roi_3yr_pct=96.0,
        npv_5yr_cny=1_850_000.0,
        irr_5yr_pct=24.5,
        payback_tier="Tier-B (12-24m Strong ROI)",
        china_sam_cny_100m=12.0,
        china_som_3_5y_cny_100m=2.1,
        global_sam_usd_m=310.0,
        global_som_5_10y_usd_m=38.0,
    )
    ev = EvaluatedOpportunity(
        seed=seed,
        roi=base_roi,
        roi_range=RangeROIMetrics(
            conservative=base_roi.model_copy(update={"payback_months": conservative_payback}),
            baseline=base_roi,
            optimistic=base_roi.model_copy(update={"payback_months": optimistic_payback}),
            parameter_basis=f"calibrated 3-scenario fixture for {opp_id}",
        ),
        storm_memo=None,
        weighted_pillar_score=weighted_pillar_score,
        elo_rating=1500.0,
        composite_rank=0,
    )
    return ev.model_dump()


def _build_eight_candidate_fixture(
    vault: EvidenceVault,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Create 4 power_energy + 4 semiconductor candidates backed by real SQLite EvidenceVault hits."""
    specs: list[dict[str, Any]] = [
        # Power & Energy (4)
        {
            "opp_id": "DP1-O1",
            "track_id": "DP1",
            "sector": "power_energy",
            "commercial_status": "overseas_only_cn_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DP1-VERIFIED-CN-BLANK: 海外Hitachi在售，国内尚无在线量产机",
            "snippet": "VAULT_SNIPPET_DP1_HVDC_C4F7N_DECOMPOSITION",
            "opt_pb": 11.2,
            "base_pb": 15.4,
            "cons_pb": 21.6,
            "score": 91.0,
        },
        {
            "opp_id": "DP2-O1",
            "track_id": "DP2",
            "sector": "power_energy",
            "commercial_status": "global_and_cn_true_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DP2-CONFIRMED-TRUE-BLANK: 海内外反证均未发现量产在线检测整机",
            "snippet": "VAULT_SNIPPET_DP2_SOLID_STATE_DRY_ELECTRODE",
            "opt_pb": 13.4,
            "base_pb": 18.6,
            "cons_pb": 26.8,
            "score": 88.5,
        },
        {
            "opp_id": "DP3-O1",
            "track_id": "DP3",
            "sector": "power_energy",
            "commercial_status": "overseas_only_cn_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DP3-DOWNGRADED-FROM-TRUE-BLANK: 西门子能源已有原型交付",
            "snippet": "VAULT_SNIPPET_DP3_SUBSEA_CABLE_PD_ONLINE",
            "opt_pb": 14.2,
            "base_pb": 19.8,
            "cons_pb": 27.4,
            "score": 86.0,
        },
        {
            "opp_id": "DP4-O1",
            "track_id": "DP4",
            "sector": "power_energy",
            "commercial_status": "global_and_cn_commercialized",
            "falsification_audit_note": "FALSIFY-NOTE-DP4-COMMERCIALIZED-CHECKED: 已有商用但AI边缘成本可降40%",
            "snippet": "VAULT_SNIPPET_DP4_PEM_ELECTROLYZER_MEMBRANE",
            "opt_pb": 16.4,
            "base_pb": 22.8,
            "cons_pb": 31.2,
            "score": 83.5,
        },
        # Semiconductor (4)
        {
            "opp_id": "DS1-O1",
            "track_id": "DS1",
            "sector": "semiconductor",
            "commercial_status": "overseas_only_cn_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DS1-VERIFIED-KLA-MONOPOLY: KLA在售，国内Fab全线空白",
            "snippet": "VAULT_SNIPPET_DS1_HYBRID_BONDING_VOID_METROLOGY",
            "opt_pb": 9.8,
            "base_pb": 13.6,
            "cons_pb": 19.4,
            "score": 93.0,
        },
        {
            "opp_id": "DS2-O1",
            "track_id": "DS2",
            "sector": "semiconductor",
            "commercial_status": "global_and_cn_true_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DS2-CONFIRMED-TRUE-BLANK: 玻璃基板TGV微裂纹在线全检尚无量产机",
            "snippet": "VAULT_SNIPPET_DS2_GLASS_SUBSTRATE_TGV_INSPECT",
            "opt_pb": 12.2,
            "base_pb": 16.8,
            "cons_pb": 23.6,
            "score": 90.0,
        },
        {
            "opp_id": "DS3-O1",
            "track_id": "DS3",
            "sector": "semiconductor",
            "commercial_status": "overseas_only_cn_blank",
            "falsification_audit_note": "FALSIFY-NOTE-DS3-VERIFIED-BRUKER-ONLY: 仅Bruker提供高价在线XRF",
            "snippet": "VAULT_SNIPPET_DS3_SIC_EPITAXY_INLINE_DEFECT",
            "opt_pb": 15.2,
            "base_pb": 20.6,
            "cons_pb": 28.4,
            "score": 85.0,
        },
        {
            "opp_id": "DS4-O1",
            "track_id": "DS4",
            "sector": "semiconductor",
            "commercial_status": "global_and_cn_commercialized",
            "falsification_audit_note": "FALSIFY-NOTE-DS4-COMMERCIALIZED-BENCHMARK: 已有商用但AI算力压缩体积",
            "snippet": "VAULT_SNIPPET_DS4_EUV_PELLICLE_CONTAMINATION",
            "opt_pb": 17.6,
            "base_pb": 24.4,
            "cons_pb": 33.8,
            "score": 81.5,
        },
    ]

    evaluated: list[dict[str, Any]] = []
    meta_by_id: dict[str, dict[str, Any]] = {}
    for spec in specs:
        cn_rec = _seed_vault_record(
            vault,
            track_id=spec["track_id"],
            geo_scope="CN",
            slug=f"{spec['opp_id'].lower()}-cn",
            snippet=f"{spec['snippet']}_CN",
        )
        gl_rec = _seed_vault_record(
            vault,
            track_id=spec["track_id"],
            geo_scope="GLOBAL",
            slug=f"{spec['opp_id'].lower()}-gl",
            snippet=f"{spec['snippet']}_GLOBAL",
        )
        ev_dict = _make_evaluated_opp_dict(
            opp_id=spec["opp_id"],
            track_id=spec["track_id"],
            sector=spec["sector"],
            commercial_status=spec["commercial_status"],
            falsification_audit_note=spec["falsification_audit_note"],
            evidence_ids=[cn_rec.ev_id, gl_rec.ev_id],
            optimistic_payback=spec["opt_pb"],
            baseline_payback=spec["base_pb"],
            conservative_payback=spec["cons_pb"],
            weighted_pillar_score=spec["score"],
        )
        evaluated.append(ev_dict)
        meta_by_id[spec["opp_id"]] = {
            **spec,
            "evidence_ids": [cn_rec.ev_id, gl_rec.ev_id],
        }
    return evaluated, meta_by_id


# ---------------------------------------------------------------------------
# Scenario 1: Flagship Brain Upgrade in Track Researcher (Never Downgrade to `fast`)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_researcher_flagship_uses_producer_tier_never_fast(tmp_path: Path) -> None:
    """In `profile='flagship'`, primary track discovery MUST invoke `tier='producer'`, never `tier='fast'`."""

    def _llm_handler(call: RecordedLLMCall) -> BaseModel:
        assert call.schema is TrackDossier
        found_ids = re.findall(r"\bEV-(?:CN|GL)-\d{3}\b", call.user_prompt)
        ev_ids = found_ids[:2] if found_ids else []
        return _make_dossier(
            track_id="DS1",
            sector="semiconductor",
            opportunities=[
                _make_seed(
                    opp_id="DS1-O1",
                    track_id="DS1",
                    sector="semiconductor",
                    commercial_status="global_and_cn_commercialized",
                    evidence_ids=ev_ids,
                )
            ],
            evidence_ids=ev_ids,
        )

    deps, _router, llm = _make_deps(tmp_path, llm_handler=_llm_handler, db_name="s1_flagship.db")
    try:
        state = {
            "profile": "flagship",
            "track_plan": {
                "track_id": "DS1",
                "sector": "semiconductor",
                "name": "混合键合界面空洞在线声学量测",
                "step_back_physics_principle": "高频超声表面波衰减反演微米级空洞",
                "cn_queries": [{"query": "中国 混合键合 在线检测 良率痛点 2025", "scope": "webpage"}],
                "global_queries": [{"query": "hybrid bonding inline void metrology yield 2025", "endpoint": "search"}],
                "cn_vendor_queries": [{"query": "混合键合 在线检测 国产厂商", "scope": "webpage"}],
                "global_vendor_queries": [{"query": "KLA Bruker hybrid bonding inline inspection", "endpoint": "search"}],
                "manufacturing_stages": ["晶圆键合", "封装终测"],
            },
        }
        result = await node_track_researcher(state, deps)

        structured_calls = [c for c in llm.calls if c.kind == "structured" and c.schema is TrackDossier]
        assert len(structured_calls) >= 1, "Expected at least one TrackDossier LLM call"
        assert all(c.tier == "producer" for c in structured_calls), (
            f"Flagship track researcher MUST use tier='producer', got tiers={[c.tier for c in structured_calls]}"
        )
        assert not any(c.tier == "fast" for c in llm.calls), (
            f"Flagship track researcher MUST NEVER downgrade any call to tier='fast', got {[c.tier for c in llm.calls]}"
        )
        assert len(result["track_dossiers"]) == 1
        assert result["track_dossiers"][0]["track_id"] == "DS1"
    finally:
        deps.vault.close()


# ---------------------------------------------------------------------------
# Scenario 2: Bounded Falsification Loop for Claimed Commercial Blanks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_falsification_loop_triggers_on_claimed_blank_and_updates_status_without_fabricating_ids(
    tmp_path: Path,
) -> None:
    """Claimed blanks must trigger bounded falsification search, Vault persistence, flagship review, and strict ID hygiene."""
    expected_audit_note = "反证核查发现海外巨头 KLA 已推出商用产线机台，故由全球空白降级为海外在售/国产空白"
    captured_new_ids: list[str] = []

    def _llm_handler(call: RecordedLLMCall) -> BaseModel:
        assert call.schema is TrackDossier
        # Verify physical untrusted-data framing in falsification prompt
        assert "[UNTRUSTED_EXTERNAL_DATA_START:" in call.user_prompt
        # Discover newly persisted evidence IDs present in Vault / prompt
        all_ids = sorted(set(re.findall(r"\bEV-(?:CN|GL)-\d{3}\b", call.user_prompt)))
        new_ids = [eid for eid in all_ids if eid not in {"EV-CN-001", "EV-GL-001"}]
        captured_new_ids.extend(new_ids)
        return _make_dossier(
            track_id="DS1",
            sector="semiconductor",
            opportunities=[
                _make_seed(
                    opp_id="DS1-O1",
                    track_id="DS1",
                    sector="semiconductor",
                    # Downgraded from global_and_cn_true_blank -> overseas_only_cn_blank
                    commercial_status="overseas_only_cn_blank",
                    # Mix real new Vault ID with one hallucinated ID that MUST be stripped
                    evidence_ids=(["EV-CN-001"] + new_ids[:1] + ["EV-CN-999"]),
                    falsification_audit_note=expected_audit_note,
                ),
                _make_seed(
                    opp_id="DS1-O2",
                    track_id="DS1",
                    sector="semiconductor",
                    commercial_status="overseas_only_cn_blank",
                    # Only hallucinated IDs -> MUST remain [] (zero fallback fabrication)
                    evidence_ids=["EV-GL-888"],
                    falsification_audit_note="反证复核维持国产空白，但缺失有效证据绑定",
                ),
            ],
            evidence_ids=["EV-CN-001", "EV-GL-001"] + new_ids[:1],
        )

    deps, router, llm = _make_deps(tmp_path, llm_handler=_llm_handler, db_name="s2_falsify_trigger.db")
    try:
        r_cn = _seed_vault_record(
            deps.vault,
            track_id="DS1",
            geo_scope="CN",
            slug="init-cn",
            snippet="Initial CN pain point snippet.",
        )
        r_gl = _seed_vault_record(
            deps.vault,
            track_id="DS1",
            geo_scope="GLOBAL",
            slug="init-gl",
            snippet="Initial GLOBAL pain point snippet.",
        )
        existing_records = deps.vault.list_by_track("DS1")
        assert len(existing_records) == 2

        # Provide 6 falsification queries across 2 blank candidates to verify `max_queries_per_round=4` cap
        initial_dossier = _make_dossier(
            track_id="DS1",
            sector="semiconductor",
            opportunities=[
                _make_seed(
                    opp_id="DS1-O1",
                    track_id="DS1",
                    sector="semiconductor",
                    commercial_status="global_and_cn_true_blank",
                    evidence_ids=[r_cn.ev_id, r_gl.ev_id],
                    falsification_queries=[
                        {"geo_scope": "GLOBAL", "query": "KLA commercial inline hybrid bonding void inspection 2025"},
                        {"geo_scope": "CN", "query": "国产 混合键合 在线空洞检测 商用机台 中科飞测 2025"},
                        {"geo_scope": "GLOBAL", "query": "Bruker Sonoscan inline wafer bonding commercial tool"},
                        {"geo_scope": "CN", "query": "混合键合 在线检测 招标 中标 2025 2026"},
                    ],
                ),
                _make_seed(
                    opp_id="DS1-O2",
                    track_id="DS1",
                    sector="semiconductor",
                    commercial_status="overseas_only_cn_blank",
                    evidence_ids=[r_cn.ev_id],
                    falsification_queries=[
                        {"geo_scope": "CN", "query": "国内 碳化硅外延 在线缺陷检测 量产厂商 精测电子"},
                        {"geo_scope": "GLOBAL", "query": "Lasertec SICA SiC inline inspection product launch"},
                    ],
                ),
            ],
            evidence_ids=[r_cn.ev_id, r_gl.ev_id],
        )

        updated_dossier, updated_records, new_hashes, rounds_executed = await run_blank_falsification_check(
            deps=deps,
            track_id="DS1",
            sector="semiconductor",
            initial_dossier=initial_dossier,
            existing_records=existing_records,
            max_rounds=1,
            max_queries_per_round=4,
        )

        # Bounded search execution & Vault persistence
        assert 1 <= len(router.calls) <= 4, f"Expected 1..4 falsification queries, got {len(router.calls)}"
        assert rounds_executed == 1
        assert len(new_hashes) >= 1
        vault_records_after = deps.vault.list_by_track("DS1")
        assert len(vault_records_after) > len(existing_records), "New falsification hits must be persisted in Vault"
        assert len(updated_records) == len(vault_records_after)

        # Flagship LLM review (tier="producer")
        assert len(llm.calls) == 1
        assert llm.calls[0].tier == "producer"
        assert llm.calls[0].schema is TrackDossier

        # Updated commercial_status, audit note, and strict non-fabrication of evidence IDs
        opps_by_id = {o.opp_id: o for o in updated_dossier.opportunities}
        assert opps_by_id["DS1-O1"].commercial_status == "overseas_only_cn_blank"
        assert expected_audit_note in opps_by_id["DS1-O1"].falsification_audit_note
        assert "EV-CN-999" not in opps_by_id["DS1-O1"].evidence_ids
        assert captured_new_ids, "Falsification prompt must expose newly persisted Vault evidence IDs"
        assert captured_new_ids[0] in opps_by_id["DS1-O1"].evidence_ids

        # DS1-O2 had only hallucinated ID -> must stay [] (no fabricated fallback_ids)
        assert opps_by_id["DS1-O2"].evidence_ids == []
    finally:
        deps.vault.close()


@pytest.mark.asyncio
async def test_falsification_loop_generates_fallback_queries_when_seed_omits_them(
    tmp_path: Path,
) -> None:
    """Even if a blank seed leaves `falsification_queries=[]`, bounded falsification queries MUST still run."""

    def _llm_handler(call: RecordedLLMCall) -> BaseModel:
        assert call.schema is TrackDossier
        return _make_dossier(
            track_id="DP2",
            sector="power_energy",
            opportunities=[
                _make_seed(
                    opp_id="DP2-O1",
                    track_id="DP2",
                    sector="power_energy",
                    commercial_status="overseas_only_cn_blank",
                    evidence_ids=["EV-CN-001"],
                    falsification_audit_note="自动构造反证检索词复核，确认国产尚无量产整机",
                )
            ],
            evidence_ids=["EV-CN-001"],
        )

    deps, router, llm = _make_deps(tmp_path, llm_handler=_llm_handler, db_name="s2_falsify_fallback_q.db")
    try:
        r_cn = _seed_vault_record(
            deps.vault,
            track_id="DP2",
            geo_scope="CN",
            slug="init-dp2",
            snippet="Initial DP2 evidence.",
        )
        existing_records = deps.vault.list_by_track("DP2")
        initial_dossier = _make_dossier(
            track_id="DP2",
            sector="power_energy",
            opportunities=[
                _make_seed(
                    opp_id="DP2-O1",
                    track_id="DP2",
                    sector="power_energy",
                    commercial_status="overseas_only_cn_blank",
                    evidence_ids=[r_cn.ev_id],
                    falsification_queries=[],
                )
            ],
            evidence_ids=[r_cn.ev_id],
        )

        updated_dossier, updated_records, new_hashes, rounds_executed = await run_blank_falsification_check(
            deps=deps,
            track_id="DP2",
            sector="power_energy",
            initial_dossier=initial_dossier,
            existing_records=existing_records,
            max_rounds=1,
            max_queries_per_round=4,
        )

        assert 1 <= len(router.calls) <= 4
        assert rounds_executed == 1
        assert len(new_hashes) >= 1
        assert len(updated_records) > len(existing_records)
        assert len(llm.calls) == 1
        assert llm.calls[0].tier == "producer"
        assert updated_dossier.opportunities[0].falsification_audit_note
    finally:
        deps.vault.close()


@pytest.mark.asyncio
async def test_falsification_loop_skips_when_all_candidates_already_commercialized(
    tmp_path: Path,
) -> None:
    """When all candidates are `global_and_cn_commercialized`, MUST run 0 searches and 0 LLM reviews."""

    def _forbidden_llm(_call: RecordedLLMCall) -> BaseModel:
        raise AssertionError("LLM must NOT be called when no candidate claims commercial blank")

    deps, router, llm = _make_deps(tmp_path, llm_handler=_forbidden_llm, db_name="s2_falsify_skip.db")
    try:
        r_cn = _seed_vault_record(
            deps.vault,
            track_id="DP1",
            geo_scope="CN",
            slug="init-comm",
            snippet="Commercialized vendor landscape.",
        )
        existing_records = deps.vault.list_by_track("DP1")
        initial_dossier = _make_dossier(
            track_id="DP1",
            sector="power_energy",
            opportunities=[
                _make_seed(
                    opp_id="DP1-O1",
                    track_id="DP1",
                    sector="power_energy",
                    commercial_status="global_and_cn_commercialized",
                    evidence_ids=[r_cn.ev_id],
                    falsification_queries=[{"geo_scope": "CN", "query": "不应被执行的冗余查询"}],
                ),
                _make_seed(
                    opp_id="DP1-O2",
                    track_id="DP1",
                    sector="power_energy",
                    commercial_status="global_and_cn_commercialized",
                    evidence_ids=[r_cn.ev_id],
                ),
            ],
            evidence_ids=[r_cn.ev_id],
        )

        updated_dossier, updated_records, new_hashes, rounds_executed = await run_blank_falsification_check(
            deps=deps,
            track_id="DP1",
            sector="power_energy",
            initial_dossier=initial_dossier,
            existing_records=existing_records,
            max_rounds=1,
            max_queries_per_round=4,
        )

        assert len(router.calls) == 0
        assert len(llm.calls) == 0
        assert rounds_executed == 0
        assert new_hashes == []
        assert len(updated_records) == len(existing_records)
        assert [o.opp_id for o in updated_dossier.opportunities] == ["DP1-O1", "DP1-O2"]
    finally:
        deps.vault.close()


@pytest.mark.asyncio
async def test_falsification_loop_respects_zero_max_rounds_bound(tmp_path: Path) -> None:
    """Setting `max_rounds=0` MUST terminate immediately with 0 searches, 0 LLM calls, and `rounds_executed == 0`."""

    def _forbidden_llm(_call: RecordedLLMCall) -> BaseModel:
        raise AssertionError("LLM must NOT be called when max_rounds=0")

    deps, router, llm = _make_deps(tmp_path, llm_handler=_forbidden_llm, db_name="s2_falsify_zero.db")
    try:
        r_cn = _seed_vault_record(
            deps.vault,
            track_id="DS2",
            geo_scope="CN",
            slug="init-zero",
            snippet="Initial blank claim.",
        )
        existing_records = deps.vault.list_by_track("DS2")
        initial_dossier = _make_dossier(
            track_id="DS2",
            sector="semiconductor",
            opportunities=[
                _make_seed(
                    opp_id="DS2-O1",
                    track_id="DS2",
                    sector="semiconductor",
                    commercial_status="global_and_cn_true_blank",
                    evidence_ids=[r_cn.ev_id],
                    falsification_queries=[{"geo_scope": "GLOBAL", "query": "should not run"}],
                )
            ],
            evidence_ids=[r_cn.ev_id],
        )

        updated_dossier, updated_records, new_hashes, rounds_executed = await run_blank_falsification_check(
            deps=deps,
            track_id="DS2",
            sector="semiconductor",
            initial_dossier=initial_dossier,
            existing_records=existing_records,
            max_rounds=0,
            max_queries_per_round=4,
        )

        assert rounds_executed == 0
        assert len(router.calls) == 0
        assert len(llm.calls) == 0
        assert new_hashes == []
        assert len(updated_records) == len(existing_records)
        assert updated_dossier.opportunities[0].opp_id == "DS2-O1"
    finally:
        deps.vault.close()


# ---------------------------------------------------------------------------
# Scenario 3: Unified Sector Buying-Committee & Portfolio Prioritization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portfolio_reviewer_dual_sector_calls_budget_prompt_grounding_and_writeback(
    tmp_path: Path,
) -> None:
    """Dual-sector review (4 power + 4 semi) MUST use <=3 flagship calls, ground prompts, and write back full ranking."""
    expected_global_order = [
        "DS1-O1",
        "DP1-O1",
        "DS2-O1",
        "DP2-O1",
        "DP3-O1",
        "DS3-O1",
        "DP4-O1",
        "DS4-O1",
    ]
    expected_roles_by_opp = {
        "DP1-O1": "near_term_cash_cow",
        "DP2-O1": "frontier_white_space_bet",
        "DP3-O1": "strategic_localization_wedge",
        "DP4-O1": "defensive_upgrade",
        "DS1-O1": "strategic_localization_wedge",
        "DS2-O1": "frontier_white_space_bet",
        "DS3-O1": "near_term_cash_cow",
        "DS4-O1": "defensive_upgrade",
    }

    def _llm_handler(call: RecordedLLMCall) -> BaseModel:
        if call.schema is SectorPortfolioReview:
            is_semi = "DS1-O1" in call.user_prompt
            sector: Literal["power_energy", "semiconductor"] = "semiconductor" if is_semi else "power_energy"
            opp_ids = (
                ["DS1-O1", "DS2-O1", "DS3-O1", "DS4-O1"]
                if is_semi
                else ["DP1-O1", "DP2-O1", "DP3-O1", "DP4-O1"]
            )
            return SectorPortfolioReview(
                sector=sector,
                portfolio_synthesis=f"{sector} 行业买方委员会综合评审结论。",
                ranked_reviews=[
                    PortfolioCandidateReview(
                        opp_id=oid,
                        sector_rank=idx,
                        portfolio_role=expected_roles_by_opp[oid],  # type: ignore[arg-type]
                        sharpest_pain_point_summary=f"{oid} 产线最尖锐痛点总结。",
                        key_localization_or_export_moat=f"{oid} 国产替代与出海壁垒。",
                        buyer_assessments=_make_buyer_assessments(oid),
                        ranking_rationale=f"{oid} 在行业内排第 {idx} 位。",
                    )
                    for idx, oid in enumerate(opp_ids, start=1)
                ],
            )
        if call.schema is GlobalPortfolioRanking:
            return GlobalPortfolioRanking(
                executive_ranking_thesis="结合现金流确定性、国产空白紧迫度与反证可信度进行跨行业组合排序。",
                ordered_opp_ids=list(expected_global_order),
                cross_sector_synergies=["AI计算传感与边缘FPGA硬件平台可跨电力与半导体复用"],
            )
        raise AssertionError(f"Unexpected schema requested: {call.schema!r}")

    deps, _router, llm = _make_deps(tmp_path, llm_handler=_llm_handler, db_name="s3_dual_sector.db")
    try:
        evaluated_input, meta_by_id = _build_eight_candidate_fixture(deps.vault)
        state: WorkflowState = {
            "run_id": "test-v4-s3-dual",
            "sector_filter": "all",
            "profile": "flagship",
            "evaluated_opportunities": evaluated_input,
        }

        result = await node_sector_portfolio_reviewer(state, deps)

        # 1. Strict call budget (<=3) and flagship tier="producer" on every single call
        assert len(llm.calls) <= 3, f"Expected <=3 LLM calls, got {len(llm.calls)}"
        assert all(c.tier == "producer" for c in llm.calls), (
            f"All portfolio reviewer calls MUST use tier='producer', got {[c.tier for c in llm.calls]}"
        )
        sector_calls = [c for c in llm.calls if c.schema is SectorPortfolioReview]
        global_calls = [c for c in llm.calls if c.schema is GlobalPortfolioRanking]
        assert len(sector_calls) == 2
        assert len(global_calls) == 1

        # 2. Prompt grounding checks for EACH sector review call
        seen_sectors: set[str] = set()
        for sc in sector_calls:
            prompt = sc.user_prompt
            sector_key = "semiconductor" if "DS1-O1" in prompt else "power_energy"
            seen_sectors.add(sector_key)
            sector_specs = [m for m in meta_by_id.values() if m["sector"] == sector_key]
            assert "[ROI-CALC]" in prompt, f"Sector prompt for {sector_key} must include [ROI-CALC] tag"
            assert "[UNTRUSTED_EXTERNAL_DATA_START:" in prompt, (
                f"Sector prompt for {sector_key} must frame external evidence with [UNTRUSTED_EXTERNAL_DATA_START:"
            )
            assert "[UNTRUSTED_EXTERNAL_DATA_END]" in prompt
            for spec in sector_specs:
                oid = spec["opp_id"]
                assert oid in prompt, f"Missing opp_id {oid} in {sector_key} prompt"
                for pb_val in (spec["opt_pb"], spec["base_pb"], spec["cons_pb"]):
                    assert f"{pb_val:.1f}" in prompt, (
                        f"Missing 3-scenario payback {pb_val:.1f} for {oid} in {sector_key} prompt"
                    )
                assert spec["commercial_status"] in prompt, (
                    f"Missing commercial_status {spec['commercial_status']} for {oid}"
                )
                assert spec["falsification_audit_note"] in prompt, (
                    f"Missing falsification_audit_note for {oid}"
                )
                assert spec["snippet"] in prompt, (
                    f"Missing real Vault evidence snippet {spec['snippet']} for {oid}"
                )
        assert seen_sectors == {"power_energy", "semiconductor"}

        # 3. Full writeback & ordering consistency (zero dropped candidates)
        out_evals = result["evaluated_opportunities"]
        assert len(out_evals) == 8
        out_ids = [ev["seed"]["opp_id"] for ev in out_evals]
        assert out_ids == expected_global_order
        assert [ev["composite_rank"] for ev in out_evals] == list(range(1, 9))

        storm_memos = result["storm_memos"]
        assert set(storm_memos.keys()) == set(expected_global_order)
        for ev in out_evals:
            oid = ev["seed"]["opp_id"]
            assert ev["seed"]["portfolio_role"] == expected_roles_by_opp[oid]
            assert ev["storm_memo"] is not None
            assert len(ev["storm_memo"]["buyer_assessments"]) == 4
            assert len(storm_memos[oid]["buyer_assessments"]) == 4

        global_ranking = result["global_portfolio_ranking"]
        assert global_ranking["ordered_opp_ids"] == out_ids
        assert set(result["portfolio_reviews"].keys()) == {"power_energy", "semiconductor"}
    finally:
        deps.vault.close()


@pytest.mark.asyncio
async def test_portfolio_reviewer_never_drops_candidates_when_llm_omits_or_hallucinates_ids(
    tmp_path: Path,
) -> None:
    """Even when LLM omits, duplicates, or hallucinates opp_ids, deterministic fallback keeps all 8 ranked 1..8."""

    def _buggy_llm_handler(call: RecordedLLMCall) -> BaseModel:
        if call.schema is SectorPortfolioReview:
            is_semi = "DS1-O1" in call.user_prompt
            if is_semi:
                opp_ids = ["DS1-O1", "DS2-O1", "DS3-O1", "DS4-O1"]
                return SectorPortfolioReview(
                    sector="semiconductor",
                    portfolio_synthesis="半导体行业评审。",
                    ranked_reviews=[
                        PortfolioCandidateReview(
                            opp_id=oid,
                            sector_rank=idx,
                            portfolio_role=_PORTFOLIO_ROLES[(idx - 1) % 4],
                            sharpest_pain_point_summary=f"{oid} 痛点。",
                            key_localization_or_export_moat=f"{oid} 壁垒。",
                            buyer_assessments=_make_buyer_assessments(oid),
                            ranking_rationale=f"{oid} 理由。",
                        )
                        for idx, oid in enumerate(opp_ids, start=1)
                    ],
                )
            # Power sector deliberately omits DP4-O1 and injects hallucinated FAKE-OPP-999
            return SectorPortfolioReview(
                sector="power_energy",
                portfolio_synthesis="电力能源评审（刻意漏掉 DP4-O1 并含幻觉 ID）。",
                ranked_reviews=[
                    PortfolioCandidateReview(
                        opp_id=oid,
                        sector_rank=idx,
                        portfolio_role=_PORTFOLIO_ROLES[(idx - 1) % 4],
                        sharpest_pain_point_summary=f"{oid} 痛点。",
                        key_localization_or_export_moat=f"{oid} 壁垒。",
                        buyer_assessments=_make_buyer_assessments(oid),
                        ranking_rationale=f"{oid} 理由。",
                    )
                    for idx, oid in enumerate(["DP1-O1", "DP2-O1", "FAKE-OPP-999", "DP3-O1"], start=1)
                ],
            )
        if call.schema is GlobalPortfolioRanking:
            # Deliberately omits DP3-O1, DP4-O1, DS3-O1, DS4-O1, duplicates DS1-O1, and adds hallucinated ID
            return GlobalPortfolioRanking(
                executive_ranking_thesis="不完整且含重复与幻觉的跨行业排序输出。",
                ordered_opp_ids=["DS1-O1", "DP1-O1", "DS1-O1", "NON-EXISTENT-O9", "DS2-O1", "DP2-O1"],
                cross_sector_synergies=[],
            )
        raise AssertionError(f"Unexpected schema requested: {call.schema!r}")

    deps, _router, _llm = _make_deps(tmp_path, llm_handler=_buggy_llm_handler, db_name="s3_fallback.db")
    try:
        evaluated_input, meta_by_id = _build_eight_candidate_fixture(deps.vault)
        expected_all_ids = set(meta_by_id.keys())
        state: WorkflowState = {
            "run_id": "test-v4-s3-fallback",
            "sector_filter": "all",
            "profile": "flagship",
            "evaluated_opportunities": evaluated_input,
        }

        result = await node_sector_portfolio_reviewer(state, deps)

        out_evals = result["evaluated_opportunities"]
        out_ids = [ev["seed"]["opp_id"] for ev in out_evals]

        # Zero candidate loss, zero duplicates, zero hallucinated IDs
        assert len(out_evals) == 8
        assert len(set(out_ids)) == 8
        assert set(out_ids) == expected_all_ids
        assert "FAKE-OPP-999" not in out_ids
        assert "NON-EXISTENT-O9" not in out_ids

        # Continuous ranking 1..8 and strict consistency with normalized ordered_opp_ids
        assert [ev["composite_rank"] for ev in out_evals] == list(range(1, 9))
        assert out_ids[:4] == ["DS1-O1", "DP1-O1", "DS2-O1", "DP2-O1"]
        assert result["global_portfolio_ranking"]["ordered_opp_ids"] == out_ids
    finally:
        deps.vault.close()


# ---------------------------------------------------------------------------
# Scenario 4: Single-Sector Optimization (<= 1 LLM Call) & Empty Guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portfolio_reviewer_single_sector_uses_at_most_one_llm_call(tmp_path: Path) -> None:
    """With only 4 semiconductor candidates, MUST invoke at most 1 SectorPortfolioReview (0 GlobalPortfolioRanking)."""
    expected_semi_order = ["DS2-O1", "DS1-O1", "DS4-O1", "DS3-O1"]

    def _semi_only_handler(call: RecordedLLMCall) -> BaseModel:
        assert call.schema is SectorPortfolioReview, (
            f"Single-sector run MUST NOT invoke {call.schema!r}; expected only SectorPortfolioReview"
        )
        return SectorPortfolioReview(
            sector="semiconductor",
            portfolio_synthesis="单半导体行业买方委员会评审。",
            ranked_reviews=[
                PortfolioCandidateReview(
                    opp_id=oid,
                    sector_rank=idx,
                    portfolio_role=_PORTFOLIO_ROLES[(idx - 1) % 4],
                    sharpest_pain_point_summary=f"{oid} 半导体产线痛点。",
                    key_localization_or_export_moat=f"{oid} 国产化护城河。",
                    buyer_assessments=_make_buyer_assessments(oid),
                    ranking_rationale=f"{oid} 单行业排第 {idx} 位。",
                )
                for idx, oid in enumerate(expected_semi_order, start=1)
            ],
        )

    deps, _router, llm = _make_deps(tmp_path, llm_handler=_semi_only_handler, db_name="s4_single_sector.db")
    try:
        all_evals, _meta = _build_eight_candidate_fixture(deps.vault)
        semi_only_evals = [e for e in all_evals if e["seed"]["sector"] == "semiconductor"]
        assert len(semi_only_evals) == 4

        state: WorkflowState = {
            "run_id": "test-v4-s4-semi",
            "sector_filter": "semiconductor",
            "profile": "flagship",
            "evaluated_opportunities": semi_only_evals,
        }

        result = await node_sector_portfolio_reviewer(state, deps)

        assert len(llm.calls) == 1, f"Single-sector run MUST use exactly 1 LLM call, got {len(llm.calls)}"
        assert llm.calls[0].tier == "producer"
        assert llm.calls[0].schema is SectorPortfolioReview

        out_evals = result["evaluated_opportunities"]
        out_ids = [ev["seed"]["opp_id"] for ev in out_evals]
        assert out_ids == expected_semi_order
        assert [ev["composite_rank"] for ev in out_evals] == [1, 2, 3, 4]
        assert result["global_portfolio_ranking"]["ordered_opp_ids"] == expected_semi_order

        for ev in out_evals:
            oid = ev["seed"]["opp_id"]
            assert ev["storm_memo"] is not None
            assert len(ev["storm_memo"]["buyer_assessments"]) == 4
            assert len(result["storm_memos"][oid]["buyer_assessments"]) == 4
            assert ev["seed"]["portfolio_role"] in _PORTFOLIO_ROLES
    finally:
        deps.vault.close()


@pytest.mark.asyncio
async def test_portfolio_reviewer_empty_shortlist_makes_zero_llm_calls(tmp_path: Path) -> None:
    """Empty shortlisted pool MUST return cleanly with 0 LLM calls."""

    def _forbidden_llm(_call: RecordedLLMCall) -> BaseModel:
        raise AssertionError("LLM must NOT be called for empty shortlist")

    deps, _router, llm = _make_deps(tmp_path, llm_handler=_forbidden_llm, db_name="s4_empty.db")
    try:
        state: WorkflowState = {
            "run_id": "test-v4-s4-empty",
            "sector_filter": "all",
            "profile": "flagship",
            "evaluated_opportunities": [],
        }
        result = await node_sector_portfolio_reviewer(state, deps)

        assert len(llm.calls) == 0
        assert result["evaluated_opportunities"] == []
        assert result["storm_memos"] == {}
    finally:
        deps.vault.close()
