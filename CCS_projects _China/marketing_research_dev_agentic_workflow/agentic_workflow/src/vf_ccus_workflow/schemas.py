"""Pydantic v2.0 Red-Zone Contracts & Single-Source Flat JSON Schema Exporter."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator

GeoScope = Literal["SIGGI", "CN", "GLOBAL"]
TrackKind = Literal["sector", "competitive_ecosystem"]
SectorCode = Literal[
    "S1_pipeline_ship_eor",
    "S2_green_methanol_ccu_chem",
    "S3_capture_rd_industry",
    "S4_food_beverage_dryice",
]
DeliveryTrack = Literal[
    "TRACK_A_IMPORTED_CORE",
    "TRACK_B_LOCALIZED_QAS",
    "TRACK_C_AUSTRIA_PREMIERGUARD",
]
HorizonCode = Literal["2026-2030", "2031-2036"]
OpportunityVerdict = Literal["GO_HIGH_PRIORITY", "GO_CONDITIONAL", "DEPRIORITIZE_OR_PSEUDO_DEMAND"]
ReportEdition = Literal["full", "executive"]


def export_flat_json_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Export a $ref/$defs-free JSON Schema preserving all numeric/enum constraints."""
    raw = model_cls.model_json_schema()
    defs = dict(raw.get("$defs") or {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            ref_name = str(node["$ref"]).split("/")[-1]
            target = dict(defs.get(ref_name, {}))
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return _resolve(merged)

        if "anyOf" in node and isinstance(node["anyOf"], list):
            non_null = [
                opt
                for opt in node["anyOf"]
                if not (isinstance(opt, dict) and opt.get("type") == "null")
            ]
            if len(non_null) == 1:
                chosen = _resolve(non_null[0])
                if isinstance(chosen, dict):
                    for meta_k in ("description", "default"):
                        if meta_k in node and meta_k not in chosen:
                            chosen[meta_k] = node[meta_k]
                return chosen

        out: dict[str, Any] = {}
        for k, v in node.items():
            if k in ("$defs", "title"):
                continue
            out[k] = _resolve(v)
        return out

    flat = _resolve(raw)
    if isinstance(flat, dict) and "type" not in flat:
        flat["type"] = "object"
    return flat


class EvidenceSearchHit(BaseModel):
    """Normalized hit returned by DualEngineSearchRouter before vault persistence."""

    title: str
    url: str
    snippet: str
    content: str = ""
    source_engine: Literal["metaso", "serper", "jina", "siggi_mcp"]
    geo_scope: GeoScope
    published_at: str = ""
    score: float = 0.0


class EvidenceRecord(BaseModel):
    """Persisted auditable evidence unit stored in SQLite EvidenceVault."""

    ev_id: str
    track_id: str
    geo_scope: GeoScope
    source_engine: Literal["metaso", "serper", "jina", "siggi_mcp"]
    title: str
    url: str
    snippet: str
    fulltext_excerpt: str = ""
    published_at: str = ""
    content_hash: str
    retrieved_at: str


class ChinaCCUSProjectItem(BaseModel):
    """Named Chinese CCS/CCUS, CO2 shipping/pipeline, or e-methanol project from evidence."""

    project_name: str
    owner_and_epc: str
    province_or_region: str
    sector: SectorCode
    capacity_mtpa_or_scale: str
    status_2026: str
    co2_impurity_profile_and_risk: str
    recommended_delivery_track: DeliveryTrack
    estimated_analyzer_stations: int = Field(ge=0, le=500, default=1)
    evidence_ids: list[str] = Field(min_length=1)


class CompetitorProfile(BaseModel):
    """Audited competitor profile strictly grounded in EvidenceVault (no invented models)."""

    vendor_name: str
    origin_category: Literal[
        "Overseas_Process_MS",
        "Overseas_FTIR_Optical_GC",
        "Domestic_MS_Vendor",
        "Domestic_PAC_System_Integrator",
    ]
    verified_models_and_tech: str
    detectable_species_and_speed: str
    blind_spots_vs_vf_imr_ms: str
    china_ccus_presence_and_pricing_position: str
    win_strategy_for_vf: str
    evidence_ids: list[str] = Field(min_length=1)


class SegmentSizingInput(BaseModel):
    """Bottom-up inputs for Python deterministic [MKT-CALC] China TAM/SAM/SOM sizing."""

    sector: SectorCode
    sub_segment: str = Field(
        default="general",
        min_length=1,
        description="Distinct sub-segment within a sector, e.g. onshore_pipeline_eor vs lco2_export_vessel_hub",
    )
    horizon: HorizonCode
    addressable_project_or_line_count: int = Field(ge=0, le=5000)
    stations_per_project: float = Field(ge=0.1, le=50.0, default=1.5)
    primary_delivery_track: DeliveryTrack
    technical_fit_ratio: float = Field(ge=0.0, le=1.0, default=0.75)
    realistic_som_win_rate: float = Field(ge=0.0, le=1.0, default=0.18)
    driver_notes: str = ""
    evidence_ids: list[str] = Field(min_length=1)


class HorizonSizingBreakdown(BaseModel):
    """Deterministic [MKT-CALC] scenario output for a single horizon & scenario."""

    scenario: Literal["conservative", "baseline", "optimistic"]
    tam_units: int
    tam_cny_wan: float
    sam_units: int
    sam_cny_wan: float
    som_units: int
    som_cny_wan: float


class SegmentSizingResult(BaseModel):
    """Deterministic [MKT-CALC] breakdown per (sector, sub_segment, track, horizon)."""

    sector: SectorCode
    sub_segment: str = "general"
    horizon: HorizonCode
    primary_delivery_track: DeliveryTrack
    asp_cny_wan: float
    conservative: HorizonSizingBreakdown
    baseline: HorizonSizingBreakdown
    optimistic: HorizonSizingBreakdown
    evidence_ids: list[str] = Field(default_factory=list)


class ChinaMarketSizingSummary(BaseModel):
    """Consolidated [MKT-CALC] China market size across 2026-2030 and 2031-2036."""

    calc_tag: str = "[MKT-CALC]"
    segments: list[SegmentSizingResult]
    horizon_totals: dict[str, dict[str, dict[str, float]]]
    grand_total_10yr_baseline_som_cny_wan: float
    grand_total_10yr_baseline_som_units: int


class ROIInputs(BaseModel):
    """Validated customer unit-economics parameters fed into deterministic Python [ROI-CALC]."""

    capex_cny: float = Field(gt=0, description="Turnkey customer CAPEX including sampling/shelter (CNY)")
    avoided_corrosion_and_shutdown_loss_cny_yr: float = Field(
        ge=0, description="Annual avoided H2SO4/HNO3 pitting/compressor failure loss (CNY/yr)"
    )
    avoided_catalyst_poison_or_flaring_cny_yr: float = Field(
        ge=0, description="Annual avoided catalyst poisoning, off-spec CO2 venting or re-liquefaction cost (CNY/yr)"
    )
    avoided_manual_lab_and_multi_gc_opex_cny_yr: float = Field(
        ge=0, description="Annual avoided lab sampling shifts & redundant single-gas analyzer maintenance (CNY/yr)"
    )
    ccer_or_export_compliance_upside_cny_yr: float = Field(
        ge=0, description="Annual carbon credit / LCO2 shipping acceptance / green-methanol premium unlocked (CNY/yr)"
    )
    annual_opex_cny_yr: float = Field(gt=0, description="Annual V&F service, cal gas & auxiliary upkeep (CNY/yr)")

    @property
    def total_gross_benefit_cny_yr(self) -> float:
        return (
            self.avoided_corrosion_and_shutdown_loss_cny_yr
            + self.avoided_catalyst_poison_or_flaring_cny_yr
            + self.avoided_manual_lab_and_multi_gc_opex_cny_yr
            + self.ccer_or_export_compliance_upside_cny_yr
        )

    def scaled(
        self,
        *,
        capex_cny: float,
        target_gross_benefit_cny: float,
        annual_opex_cny: float,
    ) -> "ROIInputs":
        """Scale all 4 benefit lines proportionally so domain economics are never overwritten."""
        orig_total = self.total_gross_benefit_cny_yr
        if orig_total > 0:
            ratio = target_gross_benefit_cny / orig_total
            corr = round(self.avoided_corrosion_and_shutdown_loss_cny_yr * ratio, 2)
            cat = round(self.avoided_catalyst_poison_or_flaring_cny_yr * ratio, 2)
            lab = round(self.avoided_manual_lab_and_multi_gc_opex_cny_yr * ratio, 2)
            comp = round(max(0.0, target_gross_benefit_cny - corr - cat - lab), 2)
        else:
            corr = round(target_gross_benefit_cny * 0.45, 2)
            cat = round(target_gross_benefit_cny * 0.30, 2)
            lab = round(target_gross_benefit_cny * 0.15, 2)
            comp = round(max(0.0, target_gross_benefit_cny - corr - cat - lab), 2)
        return ROIInputs(
            capex_cny=round(capex_cny, 2),
            avoided_corrosion_and_shutdown_loss_cny_yr=corr,
            avoided_catalyst_poison_or_flaring_cny_yr=cat,
            avoided_manual_lab_and_multi_gc_opex_cny_yr=lab,
            ccer_or_export_compliance_upside_cny_yr=comp,
            annual_opex_cny_yr=round(annual_opex_cny, 2),
        )


class ROIRangeInputs(BaseModel):
    """3-scenario parameter spread (Conservative / Baseline / Optimistic) clamped by YAML guardrails."""

    capex_cny_min: float = Field(gt=0)
    capex_cny_base: float = Field(gt=0)
    capex_cny_max: float = Field(gt=0)
    gross_benefit_cny_min: float = Field(ge=0)
    gross_benefit_cny_base: float = Field(gt=0)
    gross_benefit_cny_max: float = Field(gt=0)
    annual_opex_cny_min: float = Field(gt=0)
    annual_opex_cny_base: float = Field(gt=0)
    annual_opex_cny_max: float = Field(gt=0)

    @model_validator(mode="after")
    def _ensure_order(self) -> "ROIRangeInputs":
        lo_c, mid_c, hi_c = sorted([self.capex_cny_min, self.capex_cny_base, self.capex_cny_max])
        lo_b, mid_b, hi_b = sorted([self.gross_benefit_cny_min, self.gross_benefit_cny_base, self.gross_benefit_cny_max])
        lo_o, mid_o, hi_o = sorted([self.annual_opex_cny_min, self.annual_opex_cny_base, self.annual_opex_cny_max])
        self.capex_cny_min, self.capex_cny_base, self.capex_cny_max = lo_c, mid_c, hi_c
        self.gross_benefit_cny_min, self.gross_benefit_cny_base, self.gross_benefit_cny_max = lo_b, mid_b, hi_b
        self.annual_opex_cny_min, self.annual_opex_cny_base, self.annual_opex_cny_max = lo_o, mid_o, hi_o
        return self

    def to_baseline_inputs(self, template: ROIInputs | None = None) -> ROIInputs:
        if template is not None:
            return template.scaled(
                capex_cny=self.capex_cny_base,
                target_gross_benefit_cny=self.gross_benefit_cny_base,
                annual_opex_cny=self.annual_opex_cny_base,
            )
        b = self.gross_benefit_cny_base
        return ROIInputs(
            capex_cny=self.capex_cny_base,
            avoided_corrosion_and_shutdown_loss_cny_yr=round(b * 0.45, 2),
            avoided_catalyst_poison_or_flaring_cny_yr=round(b * 0.30, 2),
            avoided_manual_lab_and_multi_gc_opex_cny_yr=round(b * 0.15, 2),
            ccer_or_export_compliance_upside_cny_yr=round(b * 0.10, 2),
            annual_opex_cny_yr=self.annual_opex_cny_base,
        )


class ROIMetrics(BaseModel):
    """Deterministic financial outputs calculated strictly in Python ([ROI-CALC])."""

    calc_tag: str = "[ROI-CALC]"
    capex_cny: float
    gross_annual_benefit_cny: float
    net_annual_cashflow_cny: float
    payback_months: float
    roi_3yr_pct: float
    npv_5yr_cny: float
    irr_5yr_pct: float
    payback_tier: Literal[
        "<12个月(极强刚需)",
        "12-24个月(明确正向商业可行)",
        "24-36个月(战略协同推进)",
        ">36个月/负现金流(淘汰或伪需求)",
    ]


class ROIRangeMetrics(BaseModel):
    """Conservative / Baseline / Optimistic 3-scenario customer ROI band."""

    calc_tag: str = "[ROI-CALC]"
    conservative: ROIMetrics
    baseline: ROIMetrics
    optimistic: ROIMetrics


class BuyerPersonaCritique(BaseModel):
    """One Chinese CCS/CCUS stakeholder perspective in the consolidated buyer resistance matrix."""

    persona_role: str
    verdict: Literal["STRONG_BUY", "CONDITIONAL_试点", "REJECT_OR_WAIT"]
    primary_concern: str = Field(min_length=2)
    procurement_or_spec_barrier: str = Field(min_length=2)
    vf_winning_hook: str = Field(min_length=2)


class TrackBuyerResistanceCard(BaseModel):
    """Consolidated 4-persona buying-center resistance & winning playbook for a delivery scenario."""

    scenario_group: str = Field(
        description="e.g. Track A 科研中试 / Track B 管网与EOR / Track B 绿醇催化剂防毒 / Track C 海运与离岸枢纽"
    )
    delivery_track: DeliveryTrack
    persona_critiques: list[BuyerPersonaCritique] = Field(min_length=4, max_length=6)
    consensus_gtm_implication: str = Field(min_length=4)


class RankedWedgeDecision(BaseModel):
    """One deduplicated, globally ranked commercial wedge from Stage 2 GlobalPortfolioArbitrator."""

    final_rank: int = Field(ge=1, le=20)
    canonical_wedge_id: str = Field(min_length=2)
    merged_from_wedge_ids: list[str] = Field(min_length=1)
    global_priority_score: float = Field(ge=0.0, le=100.0, description="Unified 0-100 score across all tracks")
    ranking_rationale: str = Field(min_length=10)


class PortfolioArbitrationOutput(BaseModel):
    """Single flagship call replacing 10 flash STORM panels + 10 flash Elo matches."""

    deduped_ranked_wedges: list[RankedWedgeDecision] = Field(min_length=1, max_length=12)
    track_buyer_matrix: list[TrackBuyerResistanceCard] = Field(min_length=1, max_length=6)
    executive_synthesis_thesis: str = Field(min_length=10)


class CommercialWedgeCandidate(BaseModel):
    """One V&F China commercial application wedge discovered from evidence."""

    wedge_id: str
    track_id: str
    sector: SectorCode
    horizon: HorizonCode
    delivery_track: DeliveryTrack
    title: str
    verdict: OpportunityVerdict = "GO_CONDITIONAL"
    china_priority_score: float = Field(
        ge=0.0, le=100.0, description="Strictly 0-100 scale (e.g. 85.0, NEVER 0-10)"
    )
    vf_moat_score: float = Field(
        ge=0.0, le=100.0, description="Strictly 0-100 scale (e.g. 92.0, NEVER 0-10)"
    )
    target_process_point: str
    chemical_pain_point_and_imr_advantage: str
    recommended_vf_sku_and_localization: str
    key_competing_alternatives: str
    named_china_benchmark_customers: list[str] = Field(default_factory=list)
    siggi_reference_proof: str = ""
    roi_baseline: ROIInputs
    roi_range: ROIRangeInputs | None = None
    evidence_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _guard_against_ten_point_scale_mixup(self) -> "CommercialWedgeCandidate":
        """Reject obvious 0-10 scale inputs on high-priority wedges without false-positiving S4."""
        if self.verdict == "GO_HIGH_PRIORITY" and (
            self.china_priority_score <= 10.0 or self.vf_moat_score <= 10.0
        ):
            raise ValueError(
                f"Detected suspected 0-10 scale score on GO_HIGH_PRIORITY wedge '{self.wedge_id}': "
                f"china_priority_score={self.china_priority_score}, vf_moat_score={self.vf_moat_score}. "
                "Scores MUST use a 0-100 scale (e.g. 85.0, not 8.5)."
            )
        return self


class EvaluatedWedge(BaseModel):
    """Wedge after deterministic [ROI-CALC] scoring and global arbitration."""

    seed: CommercialWedgeCandidate
    roi: ROIMetrics
    roi_range: ROIRangeMetrics | None = None
    weighted_pillar_score: float = 0.0
    global_priority_score: float | None = None
    merged_from_wedge_ids: list[str] = Field(default_factory=list)
    ranking_rationale: str = ""
    composite_rank: int = 0


class EliminatedWedge(BaseModel):
    """Explicitly rejected / pseudo-demand wedge preserved in report to prevent survivorship bias."""

    wedge_id: str
    sector: SectorCode
    title: str
    baseline_payback_months: float
    conservative_payback_months: float
    elimination_reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class TrackPlan(BaseModel):
    """Dynamic emergent research track discovered at Stage 0."""

    track_id: str
    track_kind: TrackKind = "sector"
    sector: SectorCode
    name: str
    research_hypothesis: str
    cn_queries: list[str] = Field(min_length=1, max_length=12)
    global_queries: list[str] = Field(min_length=1, max_length=10)
    priority: int = Field(ge=1, le=10, default=1)


class DiscoveryPlan(BaseModel):
    """Stage 0 planner output synthesized from Siggi corpus + live China macro recon."""

    contract_id: str
    profile: str
    macro_recon_summary: str
    step_back_thesis: str
    track_plans: list[TrackPlan] = Field(min_length=3, max_length=8)


class SectorDossier(BaseModel):
    """Structured Stage 1 output mined for one business sector track (NO competitive-only clutter)."""

    track_id: str
    sector: SectorCode
    track_name: str
    key_findings_summary: str
    named_projects: list[ChinaCCUSProjectItem] = Field(default_factory=list)
    competitors: list[CompetitorProfile] = Field(default_factory=list)
    sizing_inputs: list[SegmentSizingInput] = Field(default_factory=list)
    wedges: list[CommercialWedgeCandidate] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


# Backwards-compatible alias for any external caller
TrackDossier = SectorDossier


class PACIntegratorProfile(BaseModel):
    """Chinese domestic explosion-proof shelter / PAC integrator candidate for Track B."""

    company_name: str
    core_capabilities: str
    certifications_and_qualifications: str
    cooperation_fit_with_vf: str
    evidence_ids: list[str] = Field(min_length=1)


class CompetitiveEcosystemDossier(BaseModel):
    """Dedicated Stage 1 output for competitor battlecards, domestic PAC integrators, and Spec-in barriers."""

    track_id: str
    track_name: str
    key_findings_summary: str
    competitors: list[CompetitorProfile] = Field(min_length=1)
    pac_integrators: list[PACIntegratorProfile] = Field(default_factory=list)
    design_institute_spec_barriers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)


class CritiqueIssue(BaseModel):
    volume_name: str
    severity: Literal["critical", "major", "minor"]
    description: str
    required_fix_action: str
    needs_crag_gap_search: bool = False
    suggested_query: str = ""
    suggested_geo_scope: Literal["CN", "GLOBAL"] = "CN"


class SingleVolumeCriticOutput(BaseModel):
    """Per-volume full-text Critic audit result (zero truncation)."""

    volume_name: str
    passed: bool
    overall_assessment: str
    issues: list[CritiqueIssue] = Field(default_factory=list)
    needs_rewrite: bool = False


class VolumeMarkdownOutput(BaseModel):
    """Structured wrapper for full or executive volume markdown."""

    markdown: str = Field(min_length=50)


class VolumeCitationAudit(BaseModel):
    """Deterministic full-text citation verification metrics for a single volume."""

    volume_name: str
    edition: ReportEdition
    total_chars: int
    distinct_valid_ids: int
    invalid_ids: list[str] = Field(default_factory=list)


class DeterministicAuditReport(BaseModel):
    """Objective programmatic Stage-Gate report replacing the 100-pt LLM judge."""

    passed: bool
    vault_stats: dict[str, int]
    dropped_unverified_count: int = 0
    dropped_unverified_records: list[dict[str, Any]] = Field(default_factory=list)
    full_edition_audits: list[VolumeCitationAudit] = Field(default_factory=list)
    executive_edition_audits: list[VolumeCitationAudit] = Field(default_factory=list)
    invalid_citations_by_volume: dict[str, list[str]] = Field(default_factory=dict)
    numeric_consistency_passed: bool = False
    numeric_discrepancies: list[str] = Field(default_factory=list)
    dual_edition_complete: bool = False
    dual_track_covered: bool = False
    eliminated_wedges_disclosed: bool = False
    secret_leak_check_passed: bool = True
    failed_gates: list[str] = Field(default_factory=list)


class WorkflowState(TypedDict, total=False):
    """LangGraph root State shared across Stage 0 -> Stage 3 (v2.0 4-Stage Architecture)."""

    run_id: str
    profile: Literal["fast", "flagship"]
    sector_filter: str
    hitl_enabled: bool
    output_dir: str
    vault_db_path: str

    siggi_records: list[dict[str, Any]]
    recon_records: list[dict[str, Any]]
    discovery_plan: dict[str, Any]
    track_dossiers: list[dict[str, Any]]
    competitive_dossiers: list[dict[str, Any]]
    dropped_unverified_records: list[dict[str, Any]]

    market_sizing_summary: dict[str, Any]
    evaluated_wedges: list[dict[str, Any]]
    eliminated_wedges: list[dict[str, Any]]
    china_projects_catalog: list[dict[str, Any]]
    competitors_catalog: list[dict[str, Any]]
    pac_integrators_catalog: list[dict[str, Any]]
    design_institute_barriers: list[str]

    portfolio_arbitration: dict[str, Any]
    executive_fact_sheet: str

    report_drafts: dict[str, str]
    executive_drafts: dict[str, str]
    critique_loop_count: int
    critique_history: Annotated[list[dict[str, Any]], add]
    pending_crag_queries: list[dict[str, Any]]
    volumes_to_rewrite: list[str]

    audit_report: dict[str, Any]
    stage_gate_passed: bool
    evidence_stats: dict[str, Any]
    cost_summary: dict[str, Any]
    written_files: list[str]
    telemetry_events: Annotated[list[dict[str, Any]], add]
