"""Pydantic schemas and LangGraph WorkflowState for Boiler FBG/DTS R&D Workflow.

Design Pattern References:
- Chapter 7 (P113-131): Multi-Agent Collaboration - Role definitions
- Chapter 11 (P183-195): Goal Monitoring - Milestone tracking
- Chapter 13 (P204-212): HITL - Gate approval records
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator


class StageCode(str, Enum):
    """R&D workflow stage codes."""
    STAGE_0_REQUIREMENTS = "stage_0_requirements"
    STAGE_1_CONCEPT = "stage_1_concept"
    STAGE_2_DETAILED_DESIGN = "stage_2_detailed_design"
    STAGE_3_DEVELOPMENT = "stage_3_development"
    STAGE_4_TESTING = "stage_4_testing"
    STAGE_5_PRODUCTION = "stage_5_production"


class RoleCode(str, Enum):
    """Team role codes."""
    PM = "pm"
    MKT = "mkt"
    OPT = "opt"
    HW = "hw"
    SW = "sw"
    SCM = "scm"
    QA = "qa"
    MFG = "mfg"
    TRN = "trn"
    FIN = "fin"
    SLS = "sls"
    STR = "str"


class GateStatus(str, Enum):
    """Quality gate decision status."""
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"
    PENDING_HITL = "PENDING_HITL"


class EvidenceType(str, Enum):
    """Evidence classification types."""
    LITERATURE = "EV-LIT"
    DATASHEET = "EV-DS"
    CALCULATION = "EV-CALC"
    SYNTHETIC = "EV-SYNTH"
    TEST = "EV-TEST"
    REVIEW = "EV-REVIEW"
    HITL = "EV-HITL"
    UNKNOWN = "EV-UNKNOWN"


class IssueSeverity(str, Enum):
    """QA issue severity levels."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class FiberTechRoute(str, Enum):
    """Fiber optic temperature sensing technology routes."""
    FBG = "FBG"
    DTS_RAMAN = "DTS_Raman"
    DTS_BRILLOUIN = "DTS_Brillouin"
    HYBRID = "Hybrid"


class EvidenceRecord(BaseModel):
    """Auditable evidence record stored in evidence registry.
    
    Reference: Chapter 14 (P213-230) - Knowledge Retrieval traceability
    """
    ev_id: str = Field(..., pattern=r"^\[EV-[A-Z]+-\d{3,}\]$")
    ev_type: EvidenceType
    title: str
    source: str
    url: str = ""
    date: str = ""
    content_hash: str = ""
    status: Literal["VERIFIED", "PENDING_VERIFICATION", "REJECTED"] = "PENDING_VERIFICATION"
    referenced_by: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


class MarketSegment(BaseModel):
    """Market segment definition for sizing calculations."""
    segment_id: str
    name: str
    description: str
    estimated_boiler_count: int = Field(ge=0, description="Number of target boilers in segment")
    avg_water_wall_area_m2: float = Field(ge=0, description="Average water-wall area per boiler")
    evidence_ids: list[str] = Field(default_factory=list)


class MarketSizingResult(BaseModel):
    """Deterministic market sizing calculation result.
    
    All calculations performed in Python, NOT by LLM.
    Tag: [MKT-CALC]
    """
    calc_tag: str = "[MKT-CALC]"
    segment_id: str
    horizon: Literal["2026-2028", "2029-2032"]
    tam_units: int = Field(ge=0, description="Total Addressable Market - sensor systems")
    tam_cny_wan: float = Field(ge=0, description="TAM in CNY (万元)")
    sam_units: int = Field(ge=0, description="Serviceable Addressable Market")
    sam_cny_wan: float = Field(ge=0)
    som_units: int = Field(ge=0, description="Serviceable Obtainable Market")
    som_cny_wan: float = Field(ge=0)
    assumptions: str
    evidence_ids: list[str] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    """Competitor analysis profile."""
    vendor_name: str
    origin: Literal["domestic", "international"]
    tech_route: FiberTechRoute
    key_products: list[str]
    temperature_range_c: str
    accuracy_c: str
    strengths: str
    weaknesses: str
    china_presence: str
    evidence_ids: list[str] = Field(default_factory=list)


class TechnicalRequirement(BaseModel):
    """Technical requirement specification."""
    req_id: str
    category: Literal["temperature", "spatial", "temporal", "environmental", "interface", "safety"]
    description: str
    target_value: str
    unit: str = ""
    priority: Literal["must", "should", "could"]
    verification_method: str
    status: Literal["draft", "reviewed", "approved", "implemented", "verified"] = "draft"
    evidence_ids: list[str] = Field(default_factory=list)


class FBGSensorSpec(BaseModel):
    """FBG sensor specification - pending vendor verification.
    
    WARNING: All values marked as pending_verification require
    confirmation from original manufacturer datasheets.
    """
    spec_id: str
    vendor: str = "[PENDING]"
    model: str = "[PENDING]"
    wavelength_nm: float = Field(ge=800, le=1700, default=1550.0)
    max_temperature_c: float = Field(ge=0, le=1200, description="Max operating temperature")
    temperature_accuracy_c: float = Field(ge=0, le=10, default=1.0)
    response_time_ms: float = Field(ge=0, default=100.0)
    long_term_drift_c_year: float = Field(ge=0, description="Annual drift specification")
    strain_sensitivity_pm_ue: float = Field(ge=0, default=1.2, description="Strain sensitivity pm/με")
    packaging_type: str = "[PENDING]"
    pending_verification: list[str] = Field(
        default_factory=lambda: [
            "max_temperature_c",
            "long_term_drift_c_year",
            "packaging compatibility with water-wall welding"
        ]
    )
    evidence_ids: list[str] = Field(default_factory=list)


class BOMItem(BaseModel):
    """Bill of Materials item."""
    item_id: str
    category: Literal["sensor", "demodulator", "cable", "enclosure", "power", "software", "service", "other"]
    description: str
    vendor: str = "[PENDING]"
    part_number: str = "[PENDING]"
    quantity: int = Field(ge=1)
    unit_price_cny: float = Field(ge=0, default=0.0)
    lead_time_weeks: int = Field(ge=0, default=0)
    status: Literal["pending_quote", "quoted", "approved", "ordered", "received"] = "pending_quote"
    hold_reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    @property
    def total_price_cny(self) -> float:
        return self.quantity * self.unit_price_cny


class CostBreakdown(BaseModel):
    """Cost analysis breakdown.
    
    Tag: [COST-CALC] - Deterministic calculation
    """
    calc_tag: str = "[COST-CALC]"
    tier: Literal["mvp_prototype", "pilot_system"]
    hardware_cost_cny: float = Field(ge=0)
    software_cost_cny: float = Field(ge=0)
    integration_cost_cny: float = Field(ge=0)
    testing_cost_cny: float = Field(ge=0)
    contingency_pct: float = Field(ge=0, le=100, default=20.0)
    total_cost_cny: float = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def compute_total(self) -> "CostBreakdown":
        base = self.hardware_cost_cny + self.software_cost_cny + self.integration_cost_cny + self.testing_cost_cny
        self.total_cost_cny = base * (1 + self.contingency_pct / 100)
        return self


class QAIssue(BaseModel):
    """Quality review issue record.
    
    Reference: Chapter 4 (P65-78) - Reflection pattern critic output
    """
    issue_id: str
    stage: StageCode
    role_source: RoleCode
    severity: IssueSeverity
    title: str
    description: str
    required_action: str
    assigned_to: RoleCode
    status: Literal["open", "in_progress", "resolved", "wontfix"] = "open"
    resolution: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class QAReviewResult(BaseModel):
    """Quality review result for a stage.
    
    Reference: Chapter 4 (P65-78) - Reflection pattern
    Reference: Chapter 13 (P204-212) - HITL gate decision
    """
    review_id: str
    stage: StageCode
    reviewer_role: RoleCode = RoleCode.QA
    overall_assessment: str
    issues: list[QAIssue] = Field(default_factory=list)
    gate_status: GateStatus
    requires_hitl: bool = False
    hitl_reason: str = ""
    artifacts_reviewed: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.MAJOR)


class HITLDecision(BaseModel):
    """Human-in-the-Loop decision record.
    
    Reference: Chapter 13 (P204-212) - HITL pattern
    """
    decision_id: str
    stage: StageCode
    gate_type: Literal["requirement_approval", "design_approval", "procurement_approval", 
                       "test_approval", "launch_approval"]
    request_summary: str
    options_presented: list[str]
    decision: Literal["approve", "reject", "defer", "modify"]
    decision_rationale: str
    decided_by: str = "[HUMAN_OPERATOR]"
    decided_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    conditions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Milestone(BaseModel):
    """Project milestone for tracking.
    
    Reference: Chapter 11 (P183-195) - Goal Monitoring
    """
    milestone_id: str
    stage: StageCode
    name: str
    description: str
    target_date: str = ""
    actual_date: str = ""
    status: Literal["pending", "in_progress", "completed", "delayed", "blocked"] = "pending"
    deliverables: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """Risk register item."""
    risk_id: str
    title: str
    description: str
    category: Literal["technical", "schedule", "cost", "resource", "external", "safety"]
    probability: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation_strategy: str
    contingency_plan: str = ""
    owner: RoleCode
    status: Literal["identified", "mitigating", "mitigated", "occurred", "closed"] = "identified"
    evidence_ids: list[str] = Field(default_factory=list)


class StageOutput(BaseModel):
    """Generic stage output container."""
    stage: StageCode
    role: RoleCode
    output_type: str
    content: dict[str, Any]
    artifacts: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class TemperatureReading(BaseModel):
    """Single temperature reading from FBG/DTS system.
    
    Used in temperature monitoring application prototype.
    """
    channel_id: int
    position_m: float
    temperature_c: float
    wavelength_shift_pm: float = 0.0
    strain_ue: float = 0.0
    timestamp: str
    quality_flag: Literal["good", "suspect", "bad", "missing"] = "good"
    data_source: Literal["live", "synthetic"] = "synthetic"


class TemperatureAlert(BaseModel):
    """Temperature alert/warning record."""
    alert_id: str
    alert_type: Literal["over_temp", "temp_rise_fast", "gradient_high", "sensor_drift", 
                        "fiber_break", "signal_loss", "data_gap"]
    severity: Literal["info", "warning", "alarm", "critical"]
    channel_id: int | None = None
    position_m: float | None = None
    current_value: float
    threshold_value: float
    message: str
    recommended_action: str
    timestamp: str
    acknowledged: bool = False
    ack_by: str = ""


class WorkflowState(TypedDict, total=False):
    """LangGraph root State for multi-agent R&D workflow.
    
    Reference: Chapter 7 (P113-131) - Multi-Agent Collaboration state sharing
    """
    run_id: str
    mode: Literal["simulation", "offline-replay", "live"]
    current_stage: str
    hitl_enabled: bool
    output_dir: str
    
    # Stage 0: Requirements
    market_segments: list[dict[str, Any]]
    market_sizing: list[dict[str, Any]]
    competitors: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    recommended_scenario: dict[str, Any]
    
    # Stage 1: Concept Design
    tech_route_analysis: dict[str, Any]
    sensor_specs: list[dict[str, Any]]
    system_architecture: dict[str, Any]
    software_architecture: dict[str, Any]
    
    # Stage 2: Detailed Design
    detailed_optical_design: dict[str, Any]
    detailed_hw_design: dict[str, Any]
    bom_items: list[dict[str, Any]]
    cost_breakdown: dict[str, Any]
    supplier_analysis: list[dict[str, Any]]
    
    # Stage 3-5: Development, Testing, Production
    development_status: dict[str, Any]
    test_results: list[dict[str, Any]]
    production_readiness: dict[str, Any]
    
    # Cross-cutting
    qa_reviews: Annotated[list[dict[str, Any]], add]
    hitl_decisions: Annotated[list[dict[str, Any]], add]
    milestones: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    evidence_registry: dict[str, Any]
    
    # Training & Marketing outputs
    training_materials: dict[str, Any]
    sales_toolkit: dict[str, Any]
    marketing_strategy: dict[str, Any]
    
    # Telemetry
    stage_gate_results: dict[str, Any]
    cost_ledger: dict[str, Any]
    telemetry_events: Annotated[list[dict[str, Any]], add]
    written_files: list[str]
