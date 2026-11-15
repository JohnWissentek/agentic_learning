"""Strongly-typed Pydantic v2 contracts and LangGraph state schemas.

Implements Appendix A ("Parse, don't validate") and Ch 19 Formalized Contracts
so every stage boundary exchanges machine-verified structured data.
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator


def _coerce_sector(v: Any) -> str:
    s = str(v or "").lower()
    return "semiconductor" if any(k in s for k in ("semi", "半导体", "芯片")) else "power_energy"


def _clamp(v: Any, lo: float, hi: float) -> float:
    return max(lo, min(float(v), hi))


def _coerce_commercial_status(v: Any) -> str:
    low = str(v or "").strip().lower()
    if any(
        k in low
        for k in (
            "true_blank",
            "global_and_cn_true_blank",
            "全球空白",
            "海内外均属产品空白",
            "海内外空白",
            "全球均无",
            "均无量产",
            "均未商业",
            "均无",
            "尚无成熟",
            "global blank",
            "true blank",
        )
    ):
        return "global_and_cn_true_blank"
    if any(k in low for k in ("global_and_cn_commercialized", "commercialized", "均有", "红海", "均已在售", "海内外在售")):
        return "global_and_cn_commercialized"
    return "overseas_only_cn_blank"


def _coerce_query_list(v: Any) -> list[dict[str, str]]:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return [{"query": v}] if v.strip() else []
    if not isinstance(v, list):
        return []
    out: list[dict[str, str]] = []
    for item in v:
        if isinstance(item, str) and item.strip():
            out.append({"query": item.strip()})
        elif isinstance(item, dict):
            d = {str(k): str(val) for k, val in item.items()}
            if "query" not in d and "关键词" in d:
                d["query"] = d["关键词"]
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Search & Evidence Schemas (Ch 5, Ch 8, Ch 14)
# ---------------------------------------------------------------------------


class SearchHit(BaseModel):
    """Normalized raw result returned by Metaso, Serper, or fallback search."""

    engine: Literal["metaso", "serper", "mock"]
    geo_scope: Literal["CN", "GLOBAL"]
    query: str
    title: str
    url: str
    snippet: str = ""
    summary: str = ""
    published_date: str = ""
    authority_tier: Literal["T1", "T2", "T3", "T4"] = "T3"
    score: float = 0.5


class EvidenceRecord(BaseModel):
    """Deduplicated, authority-scored evidence persisted in SQLite EvidenceVault."""

    ev_id: str
    track_id: str
    geo_scope: Literal["CN", "GLOBAL"]
    engine: str
    authority_tier: Literal["T1", "T2", "T3", "T4"]
    title: str
    url: str
    published_date: str = ""
    snippet: str = ""
    full_markdown: str = ""
    query: str = ""


# ---------------------------------------------------------------------------
# Planning & Track Research Schemas (Ch 3, Ch 6, Ch 14)
# ---------------------------------------------------------------------------


class TrackQueryPlan(BaseModel):
    """Query plan for a single orthogonal industry track."""

    track_id: str
    sector: Literal["power_energy", "semiconductor"]
    name: str
    step_back_physics_principle: str
    cn_queries: list[dict[str, str]] = Field(default_factory=list)
    global_queries: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("sector", mode="before")
    @classmethod
    def _val_sector(cls, v: Any) -> str:
        return _coerce_sector(v)

    @field_validator("cn_queries", "global_queries", mode="before")
    @classmethod
    def _val_queries(cls, v: Any) -> list[dict[str, str]]:
        return _coerce_query_list(v)


class ResearchPlan(BaseModel):
    """Global research plan produced by Node 1 (Planner + Guardrail)."""

    contract_id: str
    sector_filter: str
    profile: Literal["flagship", "fast"]
    step_back_thesis: str
    track_plans: list[TrackQueryPlan]


class DiscoveredTrack(TrackQueryPlan):
    """V2.0/V3.0 dynamically discovered orthogonal or cross-cutting track from Stage 0 Recon."""

    is_emerging_or_cross_cutting: bool = False
    emergence_rationale: str = ""
    recon_evidence_ids: list[str] = Field(default_factory=list)
    manufacturing_stages: list[str] = Field(default_factory=list)
    cn_vendor_queries: list[dict[str, str]] = Field(default_factory=list)
    global_vendor_queries: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("cn_vendor_queries", "global_vendor_queries", mode="before")
    @classmethod
    def _val_vendor_queries(cls, v: Any) -> list[dict[str, str]]:
        return _coerce_query_list(v)


class DiscoveryPlan(BaseModel):
    """V3.0 dynamic track discovery output clustered from Stage 0 macro recon evidence."""

    contract_id: str = "PSO-CONTRACT-2026-V3"
    sector_filter: str = "all"
    profile: Literal["flagship", "fast"] = "flagship"
    macro_recon_summary: str = ""
    step_back_thesis: str
    track_plans: list[DiscoveredTrack]


class PainPointItem(BaseModel):
    """Structured production-line pain point backed by evidence IDs."""

    process_stage: str
    geo_scope: Literal["CN", "GLOBAL"]
    pain_description: str
    current_limitation: str
    impact_pillars: list[str]
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("geo_scope", mode="before")
    @classmethod
    def _val_geo(cls, v: Any) -> str:
        s = str(v or "").strip().lower()
        return "CN" if (s in {"cn", "china", "中国", "domestic"} or "中国" in s) else "GLOBAL"


class ROIInputs(BaseModel):
    """Deterministic financial inputs fed into PALMs ROI calculator."""

    capex_cny: float = Field(gt=0)
    annual_opex_cny: float = Field(ge=0)
    annual_output_value_cny: float = Field(gt=0)
    yield_gain_pct: float = Field(ge=0, le=20.0)
    annual_scrap_saving_cny: float = Field(ge=0)
    annual_downtime_saving_cny: float = Field(ge=0)
    annual_consumable_ehs_saving_cny: float = Field(ge=0)
    market_tam_china_cny_100m: float = Field(gt=0)
    market_tam_global_usd_m: float = Field(gt=0)
    wacc: float = Field(default=0.10, gt=0, lt=0.5)

    @field_validator("wacc", mode="before")
    @classmethod
    def _val_wacc(cls, v: Any) -> float:
        val = float(v)
        if val >= 1.0:
            val = val / 100.0
        return _clamp(val, 0.03, 0.35)

    @field_validator("yield_gain_pct", mode="before")
    @classmethod
    def _val_yield(cls, v: Any) -> float:
        return _clamp(v, 0.0, 20.0)

    @field_validator(
        "capex_cny",
        "annual_output_value_cny",
        "market_tam_china_cny_100m",
        "market_tam_global_usd_m",
        mode="before",
    )
    @classmethod
    def _val_pos(cls, v: Any) -> float:
        return max(1.0, float(v))

    @field_validator(
        "annual_opex_cny",
        "annual_scrap_saving_cny",
        "annual_downtime_saving_cny",
        "annual_consumable_ehs_saving_cny",
        mode="before",
    )
    @classmethod
    def _val_nonneg(cls, v: Any) -> float:
        return max(0.0, float(v))


class ROIMetrics(BaseModel):
    """Deterministic output produced exclusively by Python PALMs code (Ch 17)."""

    capex_cny: float
    annual_opex_cny: float
    yield_gain_saving_cny: float
    annual_gross_benefit_cny: float
    net_annual_cashflow_cny: float
    payback_months: float
    roi_3yr_pct: float
    npv_5yr_cny: float
    irr_5yr_pct: float
    payback_tier: Literal[
        "Tier-A (<=12m Ultra-High ROI)",
        "Tier-B (12-24m Strong ROI)",
        "Tier-C (24-42m Strategic Upgrade)",
        "Tier-D (>42m Long Horizon)",
    ]
    china_sam_cny_100m: float
    china_som_3_5y_cny_100m: float
    global_sam_usd_m: float
    global_som_5_10y_usd_m: float


class ROIRangeInputs(BaseModel):
    """Evidence-anchored low/base/high economic parameter bounds extracted for V2.0 dynamic candidates."""

    capex_cny_low: float = Field(gt=0)
    capex_cny_base: float = Field(gt=0)
    capex_cny_high: float = Field(gt=0)
    yield_gain_pct_low: float = Field(ge=0, le=20.0)
    yield_gain_pct_base: float = Field(ge=0, le=20.0)
    yield_gain_pct_high: float = Field(ge=0, le=20.0)
    annual_output_value_cny: float = Field(gt=0)
    annual_opex_cny: float = Field(ge=0)
    annual_scrap_saving_cny: float = Field(ge=0)
    annual_downtime_saving_cny: float = Field(ge=0)
    annual_consumable_ehs_saving_cny: float = Field(ge=0)
    market_tam_china_cny_100m: float = Field(gt=0)
    market_tam_global_usd_m: float = Field(gt=0)
    parameter_basis: str = ""
    wacc: float = Field(default=0.10, gt=0, lt=0.5)

    @field_validator("wacc", mode="before")
    @classmethod
    def _val_range_wacc(cls, v: Any) -> float:
        val = float(v)
        if val >= 1.0:
            val = val / 100.0
        return _clamp(val, 0.03, 0.35)

    @model_validator(mode="after")
    def _normalize_triads(self) -> "ROIRangeInputs":
        c_lo, c_mid, c_hi = sorted(
            (max(1.0, self.capex_cny_low), max(1.0, self.capex_cny_base), max(1.0, self.capex_cny_high))
        )
        y_lo, y_mid, y_hi = sorted(
            (
                _clamp(self.yield_gain_pct_low, 0.0, 20.0),
                _clamp(self.yield_gain_pct_base, 0.0, 20.0),
                _clamp(self.yield_gain_pct_high, 0.0, 20.0),
            )
        )
        self.capex_cny_low, self.capex_cny_base, self.capex_cny_high = c_lo, c_mid, c_hi
        self.yield_gain_pct_low, self.yield_gain_pct_base, self.yield_gain_pct_high = y_lo, y_mid, y_hi
        return self

    def to_baseline_inputs(self) -> ROIInputs:
        return ROIInputs(
            capex_cny=self.capex_cny_base,
            annual_opex_cny=self.annual_opex_cny,
            annual_output_value_cny=self.annual_output_value_cny,
            yield_gain_pct=self.yield_gain_pct_base,
            annual_scrap_saving_cny=self.annual_scrap_saving_cny,
            annual_downtime_saving_cny=self.annual_downtime_saving_cny,
            annual_consumable_ehs_saving_cny=self.annual_consumable_ehs_saving_cny,
            market_tam_china_cny_100m=self.market_tam_china_cny_100m,
            market_tam_global_usd_m=self.market_tam_global_usd_m,
            wacc=self.wacc,
        )


class RangeROIMetrics(BaseModel):
    """Three-scenario deterministic PALMs sensitivity envelope."""

    conservative: ROIMetrics
    baseline: ROIMetrics
    optimistic: ROIMetrics
    parameter_basis: str = ""


class EliminatedCandidate(BaseModel):
    """Candidate filtered out during Stage 2 deterministic PALMs funnel screening."""

    opp_id: str
    track_id: str
    sector: Literal["power_energy", "semiconductor"]
    title: str
    horizon: Literal["3-5y", "5-10y"]
    commercial_status: str = "overseas_only_cn_blank"
    baseline_payback_months: float
    conservative_payback_months: float
    weighted_pillar_score: float
    evidence_count: int
    elimination_reason: str


class TechOpportunitySeed(BaseModel):
    """Candidate online instrumentation technology, product, or application."""

    opp_id: str
    track_id: str
    sector: Literal["power_energy", "semiconductor"]
    title: str
    horizon: Literal["3-5y", "5-10y"]
    china_priority_score: float = Field(ge=0, le=100)
    global_priority_score: float = Field(ge=0, le=100)
    physics_principle: str
    target_process_point: str
    product_form_factor: str
    quality_yield_mechanism: str
    cost_tco_mechanism: str
    green_ehs_mechanism: str
    industrial_upgrade_mechanism: str
    china_positioning: str
    global_expansion_path: str
    commercial_status: Literal[
        "global_and_cn_commercialized",
        "overseas_only_cn_blank",
        "global_and_cn_true_blank",
    ] = "overseas_only_cn_blank"
    global_vendors_and_products: str = ""
    china_vendors_and_products: str = ""
    white_space_and_entry_wedge: str = ""
    ai_computational_sensing_and_co_design: str = ""
    ai_rd_acceleration_and_edge_deployment: str = ""
    estimated_rd_months_ai_vs_legacy: str = "14个月 (AI原生协同) vs 30个月 (传统串行研发)"
    hardware_bom_localization_and_gtm_form: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    roi_inputs: ROIInputs | None = None
    roi_range_inputs: ROIRangeInputs | None = None
    discovery_origin: str = "dynamic_evidence_emergence"

    @field_validator("commercial_status", mode="before")
    @classmethod
    def _val_commercial_status(cls, v: Any) -> str:
        return _coerce_commercial_status(v)

    @model_validator(mode="after")
    def _ensure_roi_inputs(self) -> "TechOpportunitySeed":
        if self.roi_inputs is None and self.roi_range_inputs is not None:
            self.roi_inputs = self.roi_range_inputs.to_baseline_inputs()
        elif self.roi_inputs is None:
            raise ValueError("Either `roi_inputs` or `roi_range_inputs` must be provided")
        return self

    @field_validator("sector", mode="before")
    @classmethod
    def _val_sector(cls, v: Any) -> str:
        return _coerce_sector(v)

    @field_validator("horizon", mode="before")
    @classmethod
    def _val_horizon(cls, v: Any) -> str:
        s = str(v or "")
        return "5-10y" if any(k in s for k in ("5-10", "5–10", "2031")) else "3-5y"

    @field_validator("china_priority_score", "global_priority_score", mode="before")
    @classmethod
    def _val_scores(cls, v: Any) -> float:
        return _clamp(v, 0.0, 100.0)


class TrackDossier(BaseModel):
    """Compressed, citation-grounded findings from one parallel track worker."""

    track_id: str
    sector: Literal["power_energy", "semiconductor"]
    track_name: str
    commercial_landscape_summary: str = ""
    china_market_dynamics: str
    global_market_dynamics: str
    horizon_3_5y_outlook: str
    horizon_5_10y_outlook: str
    pain_points: list[PainPointItem]
    opportunities: list[TechOpportunitySeed]
    evidence_count_cn: int = 0
    evidence_count_global: int = 0
    top_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _propagate_track_meta(cls, data: Any) -> Any:
        """Stamp parent track_id and sector onto nested opportunities when omitted by LLM schemas."""
        if isinstance(data, dict) and isinstance(data.get("opportunities"), list):
            tid = data.get("track_id")
            sec = data.get("sector")
            patched_opps = []
            for opp in data["opportunities"]:
                if isinstance(opp, dict):
                    opp_copy = dict(opp)
                    if tid and not opp_copy.get("track_id"):
                        opp_copy["track_id"] = tid
                    if sec and not opp_copy.get("sector"):
                        opp_copy["sector"] = sec
                    patched_opps.append(opp_copy)
                else:
                    patched_opps.append(opp)
            return {**data, "opportunities": patched_opps}
        return data

    @field_validator("sector", mode="before")
    @classmethod
    def _val_sector(cls, v: Any) -> str:
        return _coerce_sector(v)


# ---------------------------------------------------------------------------
# STORM Multi-Persona Interrogation & Ranking Schemas (Ch 7, Ch 20, Ch 21)
# ---------------------------------------------------------------------------


class BuyerPersonaAssessment(BaseModel):
    """One buyer persona's realistic manufacturing interrogation."""

    persona_role: Literal[
        "Fab/Plant Yield VP",
        "Metrology/Process Chief Engineer",
        "EHS & Green Compliance Director",
        "CFO / Procurement ROI Gatekeeper",
    ]
    core_question: str
    adoption_barrier: str
    spec_in_trigger: str
    recommended_product_tweak: str

    @field_validator("persona_role", mode="before")
    @classmethod
    def _val_persona_role(cls, v: Any) -> str:
        s = str(v or "").strip()
        canonical = (
            "Fab/Plant Yield VP",
            "Metrology/Process Chief Engineer",
            "EHS & Green Compliance Director",
            "CFO / Procurement ROI Gatekeeper",
        )
        if s in canonical:
            return s
        low = s.lower()
        if any(k in low for k in ("yield", "良率")):
            return "Fab/Plant Yield VP"
        if any(k in low for k in ("metrology", "process", "工艺", "总工")):
            return "Metrology/Process Chief Engineer"
        if any(k in low for k in ("ehs", "green", "环保", "双碳", "安全")):
            return "EHS & Green Compliance Director"
        if any(k in low for k in ("cfo", "procurement", "roi", "财务", "采购")):
            return "CFO / Procurement ROI Gatekeeper"
        return "Fab/Plant Yield VP"


class OpportunityStormMemo(BaseModel):
    """Aggregated 4-persona STORM critique for one opportunity."""

    opp_id: str
    buyer_assessments: list[BuyerPersonaAssessment]
    sharpest_pain_point_summary: str
    key_localization_or_export_moat: str


class EvaluatedOpportunity(BaseModel):
    """Opportunity enriched with deterministic ROI, STORM memo, and Elo score."""

    seed: TechOpportunitySeed
    roi: ROIMetrics
    roi_range: RangeROIMetrics | None = None
    storm_memo: OpportunityStormMemo | None = None
    weighted_pillar_score: float = 0.0
    elo_rating: float = 1500.0
    composite_rank: int = 0


class EloMatchRecord(BaseModel):
    """Single pairwise Elo debate record (Ch 21 AI Co-Scientist)."""

    round_idx: int
    opp_a_id: str
    opp_b_id: str
    winner_id: str
    rationale: str
    elo_a_after: float
    elo_b_after: float


# ---------------------------------------------------------------------------
# Reflection, Corrective RAG & Stage-Gate Judge Schemas (Ch 4, Ch 11, Ch 19)
# ---------------------------------------------------------------------------


class CritiqueIssue(BaseModel):
    """Single concrete defect flagged by the heterogeneous Critic."""

    severity: Literal["critical", "major", "minor"]
    section: str
    issue_type: Literal[
        "missing_evidence",
        "physics_precision",
        "commercial_landscape_gap",
        "ai_co_design_depth",
        "china_global_balance",
        "horizon_clarity",
        "roi_consistency",
        "prose_quality",
    ]
    description: str
    suggested_query: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _val_severity(cls, v: Any) -> str:
        low = str(v or "").strip().lower()
        if "critical" in low:
            return "critical"
        if "major" in low or "high" in low:
            return "major"
        return "minor"

    @field_validator("issue_type", mode="before")
    @classmethod
    def _val_issue_type(cls, v: Any) -> str:
        s = str(v or "").strip().lower()
        valid = {
            "missing_evidence",
            "physics_precision",
            "commercial_landscape_gap",
            "ai_co_design_depth",
            "china_global_balance",
            "horizon_clarity",
            "roi_consistency",
            "prose_quality",
        }
        if s in valid:
            return s
        if "commercial" in s or "vendor" in s or "blank" in s:
            return "commercial_landscape_gap"
        if "ai" in s or "co_design" in s:
            return "ai_co_design_depth"
        return "missing_evidence" if "evidence" in s else "prose_quality"


class CritiqueVerdict(BaseModel):
    """Structured decision from Node 6 (heterogeneous_critic)."""

    decision: Literal["pass", "needs_more_evidence", "needs_rewrite"]
    overall_confidence: float = Field(ge=0, le=100)
    summary: str
    issues: list[CritiqueIssue] = Field(default_factory=list)
    gap_queries: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("decision", mode="before")
    @classmethod
    def _normalize_decision(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if s in {"pass", "needs_more_evidence", "needs_rewrite"}:
            return s
        if "evidence" in s:
            return "needs_more_evidence"
        if "rewrite" in s or "revise" in s:
            return "needs_rewrite"
        return "pass"

    @field_validator("gap_queries", mode="before")
    @classmethod
    def _normalize_gap_queries(cls, v: Any) -> list[dict[str, str]]:
        if v is None:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                return [{"track_id": "S3", "geo_scope": "CN", "query": v}] if v.strip() else []
        if not isinstance(v, list):
            return []
        out: list[dict[str, str]] = []
        for item in v:
            if isinstance(item, str) and item.strip():
                out.append({"track_id": "S3", "geo_scope": "CN", "query": item.strip()})
            elif isinstance(item, dict):
                out.append({str(k): str(val) for k, val in item.items()})
        return out


class JudgeRubricScores(BaseModel):
    """Ch 19 LLM-as-a-Judge 100-point rubric output."""

    china_first_then_global_depth: float = Field(ge=0, le=20)
    dual_horizon_3_5y_vs_5_10y_rigor: float = Field(ge=0, le=20)
    pain_point_and_physics_specificity: float = Field(ge=0, le=20)
    roi_and_industrial_upgrade_value: float = Field(ge=0, le=20)
    citation_grounding_and_prose: float = Field(ge=0, le=20)
    total_score: float = Field(default=0.0, ge=0, le=100)
    executive_verdict: str
    strengths: list[str]
    residual_risks: list[str]

    @field_validator(
        "china_first_then_global_depth",
        "dual_horizon_3_5y_vs_5_10y_rigor",
        "pain_point_and_physics_specificity",
        "roi_and_industrial_upgrade_value",
        "citation_grounding_and_prose",
        mode="before",
    )
    @classmethod
    def _val_dim_score(cls, v: Any) -> float:
        return _clamp(v, 0.0, 20.0)


# ---------------------------------------------------------------------------
# LangGraph Global State (Ch 3 Reducers + Ch 8 State Hygiene)
# ---------------------------------------------------------------------------


def _merge_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class WorkflowState(TypedDict, total=False):
    """Typed LangGraph State shared across all workflow stages."""

    run_id: str
    sector_filter: Literal["all", "power", "semiconductor"]
    profile: Literal["flagship", "fast"]
    output_dir: str
    hitl_enabled: bool
    max_loops: int
    loop_count: int
    recent_query_hashes: Annotated[list[str], operator.add]

    # Stage 0 & 1: Dynamic Recon Plan
    recon_evidence_ids: list[str]
    research_plan: dict[str, Any]
    hitl_approved: bool

    # Stage 1 & 2: Parallel Fan-out Track Dossiers & Funnel Screening
    track_dossiers: Annotated[list[dict[str, Any]], operator.add]
    evidence_stats: dict[str, Any]
    raw_candidates_count: int
    eliminated_candidates: list[dict[str, Any]]

    # Stage 3: STORM & PALMs / Elo Ranking
    storm_memos: dict[str, Any]
    evaluated_opportunities: list[dict[str, Any]]
    elo_matches: list[dict[str, Any]]

    # Stage 4: Grounded Synthesis & Heterogeneous Reflection
    draft_reports: Annotated[dict[str, str], _merge_dict]
    critique_history: Annotated[list[dict[str, Any]], operator.add]
    latest_critique: dict[str, Any]

    # Stage 5: Judge & Telemetry
    evaluation_scorecard: dict[str, Any]
    telemetry_events: Annotated[list[dict[str, Any]], operator.add]
    final_deliverables: list[str]
