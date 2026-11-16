"""Pydantic v2 contracts and LangGraph WorkflowState for BoilerSense-AI™ IPD Workflow."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

GeoScope = Literal["BASE", "CN", "GLOBAL", "PDF"]
TrackId = Literal[
    "T1_MARKET_POLICY",
    "T2_COMPETITIVE_INTEL",
    "T3_OPTICS_HARDWARE",
    "T4_FIBER_BOILER_PACKAGING",
    "T5_SOFTWARE_BOILER_AI",
    "T6_NPI_QAQC_FINANCE",
]
ProductTierCode = Literal["BS-STD-600", "BS-PRO-2000"]


class EvidenceSearchHit(BaseModel):
    """Normalized hit returned by DualEngineSearchRouter or PDF/Prior loader."""

    title: str
    url: str
    snippet: str
    content: str = ""
    source_engine: Literal["metaso", "serper", "jina", "prior_corpus", "pdf_datasheet"]
    geo_scope: GeoScope
    published_at: str = ""
    score: float = 0.0


class EvidenceRecord(BaseModel):
    """Persisted auditable evidence unit stored in SQLite EvidenceVault."""

    ev_id: str
    track_id: str
    geo_scope: GeoScope
    source_engine: Literal["metaso", "serper", "jina", "prior_corpus", "pdf_datasheet"]
    title: str
    url: str
    snippet: str
    fulltext_excerpt: str = ""
    published_at: str = ""
    content_hash: str
    retrieved_at: str


class DatasheetAsset(BaseModel):
    """Verified OEM PDF datasheet stored in output/datasheets_pdf/."""

    ev_id: str
    filename: str
    vendor: str
    part_number: str
    subsystem: str
    source_url: str
    origin_type: Literal["baseline_copied", "downloaded_online"]
    page_count: int
    file_size_bytes: int
    sha256: str
    key_specs_summary: str


class TrackPlanItem(BaseModel):
    """Single research/engineering track plan emitted by Chief Product Manager."""

    track_id: TrackId
    role_title: str
    focus_mandate: str
    cn_queries: list[str] = Field(min_length=1, max_length=5)
    global_queries: list[str] = Field(min_length=1, max_length=5)
    pdf_queries: list[str] = Field(default_factory=list, max_length=4)
    priority: int = Field(ge=1, le=6)


class ProductDiscoveryPlan(BaseModel):
    """Stage 0b Step-Back planning output from Chief PM."""

    contract_id: str
    profile: str
    step_back_thesis: str
    china_market_positioning: str
    track_plans: list[TrackPlanItem] = Field(min_length=4, max_length=8)


class CompetitorBenchmark(BaseModel):
    """Audited competitor entry grounded in EvidenceVault."""

    vendor_name: str
    segment: Literal["Domestic_FBG_Leader", "Global_FBG_Leader", "Acoustic_IR_Thermal_Competitor", "Traditional_TC"]
    representative_product: str
    optical_route: str
    claimed_capability_and_price_band: str
    key_weaknesses_or_gaps: str
    our_win_wedge: str
    evidence_ids: list[str] = Field(min_length=1)


class SelectedHardwareComponent(BaseModel):
    """Selected off-the-shelf international/dual-track hardware component."""

    subsystem: str
    product_tier: Literal["BS-STD-600", "BS-PRO-2000", "SHARED_BOTH"]
    primary_vendor: str
    part_number: str
    backup_vendor_and_model: str
    electrical_optical_interface: str
    mechanical_env_rating: str
    datasheet_filename: str
    evidence_ids: list[str] = Field(min_length=1)


class TrackResearchDossier(BaseModel):
    """Structured findings produced by each of the 6 specialist agents in Stage 1."""

    track_id: TrackId
    role_title: str
    executive_findings: str
    key_technical_decisions: list[str]
    competitors: list[CompetitorBenchmark] = Field(default_factory=list)
    selected_components: list[SelectedHardwareComponent] = Field(default_factory=list)
    qa_or_field_risks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)


class PhysicsLinkBudgetResult(BaseModel):
    """Deterministic [PHY-CALC] optical link budget, thermal drift, and block conduction metrics."""

    calc_tag: str = "[PHY-CALC]"
    std_points_per_fiber: int
    std_max_temp_drift_nm: float
    std_channel_spacing_nm: float
    std_collision_margin_nm: float
    std_rx_power_dbm: float
    std_snr_margin_db: float
    std_scan_cycle_ms: float
    pro_wdm_points_per_fiber: int
    pro_hybrid_points_per_fiber: int
    pro_rx_power_wdm_dbm: float
    pro_rx_power_uwfbg_dbm: float
    pro_snr_margin_wdm_db: float
    pro_snr_margin_uwfbg_db: float
    pro_scan_cycle_1600pts_ms: float
    block_steady_temp_drop_c_at_350kwm2: float
    block_first_order_tau_s: float


class TierBomBreakdown(BaseModel):
    """Deterministic [BOM-CALC] cost & margin breakdown for one product config & supply track."""

    config_code: str
    points_count: int
    channels_count: int
    supply_track: Literal["Track_A_Full_Imported", "Track_B_Hybrid_Competitive"]
    host_bom_proto_cny: float
    host_bom_10u_cny: float
    host_bom_50u_cny: float
    sensor_bom_10u_cny: float
    sensor_bom_50u_cny: float
    moh_qa_cny: float
    total_cogs_proto_cny: float
    total_cogs_10u_cny: float
    total_cogs_50u_cny: float
    per_point_cogs_10u_cny: float
    per_point_cogs_50u_cny: float
    target_list_price_cny: float
    gross_margin_10u_pct: float
    gross_margin_50u_pct: float


class ArchComparisonRow(BaseModel):
    """Deterministic comparison across 5 candidate technical architectures."""

    arch_id: str
    name: str
    std_500pt_cogs_cny: float
    pro_1500pt_cogs_cny: float
    rd_cycle_months: float
    hardware_risk_score: float
    scalability_score: float
    supply_resilience_score: float


class FinancialYearRow(BaseModel):
    """Single-year P&L and cash flow row in 5-year lean startup model."""

    year: int
    std_units: int
    pro_units: int
    total_units: int
    revenue_cny_wan: float
    cogs_and_delivery_cny_wan: float
    gross_profit_cny_wan: float
    gross_margin_pct: float
    opex_cny_wan: float
    ebitda_cny_wan: float
    net_cash_flow_cny_wan: float
    cumulative_cash_flow_cny_wan: float


class ScenarioFinancialSummary(BaseModel):
    """5-year financial summary for Bear/Base/Bull scenarios."""

    scenario: Literal["conservative", "baseline", "optimistic"]
    startup_capex_cny_wan: float
    total_5yr_units: int
    total_5yr_revenue_cny_wan: float
    total_5yr_ebitda_cny_wan: float
    breakeven_year: int
    breakeven_units_annual: int
    npv_10pct_cny_wan: float
    irr_pct: float
    yearly_rows: list[FinancialYearRow]


class PlantROISummary(BaseModel):
    """Coal-fired plant buyer ROI summary [PLANT-ROI]."""

    unit_label: str
    capex_cny: float
    annual_service_opex_cny: float
    annual_gross_benefit_base_cny: float
    annual_net_benefit_base_cny: float
    payback_months_conservative: float
    payback_months_baseline: float
    payback_months_optimistic: float
    three_yr_roi_pct_baseline: float


class DeterministicCalcBundle(BaseModel):
    """All zero-LLM deterministic calculations injected into IPD, STORM, Synthesizer, and Critic."""

    physics_link: PhysicsLinkBudgetResult
    arch_comparisons: list[ArchComparisonRow]
    bom_matrix: list[TierBomBreakdown]
    financial_scenarios: list[ScenarioFinancialSummary]
    plant_roi_list: list[PlantROISummary]
    markdown_tables: dict[str, str]


class IPDReviewMemo(BaseModel):
    """Stage 3a: 6-role internal IPD engineering review verdict."""

    overall_readiness_verdict: Literal["APPROVE_TO_PROTOTYPE", "CONDITIONAL_WITH_ACTION_ITEMS"]
    critical_interface_risks: list[str]
    design_for_manufacturing_actions: list[str]
    qa_calibration_mandates: list[str]
    cost_down_levers: list[str]
    evidence_ids: list[str] = Field(min_length=1)


class PowerPlantStormPanel(BaseModel):
    """Stage 3b: 4-persona power-plant buyer committee STORM interrogation."""

    chief_engineer_concerns: list[str]
    boiler_inspection_head_demands: list[str]
    ic_cybersecurity_hard_gates: list[str]
    cfo_procurement_thresholds: list[str]
    winning_value_propositions: list[str]
    evidence_ids: list[str] = Field(min_length=1)


class ArchitectureEloMatch(BaseModel):
    """Single Swiss-round pairwise comparison between two candidate architectures."""

    round_num: int
    arch_a: str
    arch_b: str
    winner: str
    margin: Literal["decisive", "narrow"]
    rationale: str


class CriticIssue(BaseModel):
    """Specific defect identified by Adversarial Critic."""

    volume: str
    severity: Literal["critical", "major", "minor"]
    finding: str
    fix_instruction: str
    needs_crag_gap_search: bool = False
    suggested_geo_scope: Literal["CN", "GLOBAL", "PDF"] = "CN"
    suggested_query: str = ""


class CriticAuditReport(BaseModel):
    """Stage 6 Heterogeneous Critic output."""

    passed: bool
    overall_assessment: str
    volumes_to_rewrite: list[str] = Field(default_factory=list)
    issues: list[CriticIssue] = Field(default_factory=list)


class JudgeRubricScores(BaseModel):
    """Stage 7 Ch 19 LLM-as-a-Judge 100-point Stage-Gate scorecard."""

    market_and_competitive_rigor: float = Field(ge=0, le=20)
    hardware_selection_and_interface_completeness: float = Field(ge=0, le=20)
    software_demod_and_boiler_ai_actionability: float = Field(ge=0, le=20)
    npi_qaqc_bringup_and_field_sop: float = Field(ge=0, le=20)
    financial_gtm_training_and_traceability: float = Field(ge=0, le=20)
    total_score: float = Field(ge=0, le=100)
    pass_status: Literal["PASS", "NEEDS_HUMAN_REVIEW"]
    executive_verdict: str
    key_strengths: list[str]
    remaining_gaps: list[str]


class WorkflowState(TypedDict, total=False):
    """Shared LangGraph State across all 8 stages."""

    run_id: str
    profile: str
    output_dir: str
    vault_db: str
    recon_summary: str
    discovery_plan: dict[str, Any]
    track_dossiers: Annotated[list[dict[str, Any]], add]
    datasheet_assets: list[dict[str, Any]]
    calc_bundle: dict[str, Any]
    ipd_memo: dict[str, Any]
    storm_panel: dict[str, Any]
    elo_matches: list[dict[str, Any]]
    elo_ranking: list[dict[str, Any]]
    volumes: dict[str, str]
    critic_loop_count: int
    critic_history: Annotated[list[dict[str, Any]], add]
    volumes_to_rewrite: list[str]
    crag_queries: list[dict[str, str]]
    crag_context: str
    judge_rubric: dict[str, Any]
    final_manifest: dict[str, Any]
