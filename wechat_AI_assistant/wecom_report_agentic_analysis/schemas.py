"""Red-Zone Pydantic v2 contracts for WeCom Report Agentic Analysis (Slice 0 + Slice 1).

All cross-module enums, WeCom 5-template registry, 15-person company role roster,
G1-G5 strategic roadmap baseline, structured report records, inferred tasks,
high-cost R&D audit, AI transformation radar, alignment audit outputs, and
untrusted-data fencing helpers live here so business logic never passes untyped dicts.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportType(str, Enum):
    """Canonical enum for all 7 WeCom report templates (+ pre-2025 legacy archive) in 维恩科仪."""

    MORNING_BRIEF = "morning_brief"
    DAILY_10MIN = "daily_10min"
    FIELD_SUPPORT = "field_support"
    FIELD_SUPPORT_BACKFILL = "field_support_backfill"
    RD_TEST_REPAIR = "rd_test_repair"
    FINANCE_DAILY_10MIN = "finance_daily_10min"
    FIELD_DAILY_10MIN = "field_daily_10min"
    LEGACY_OTHER = "legacy_other"


class ProductLine(str, Enum):
    """Canonical 7 product lines + common/cross-product bucket."""

    SONIC_TEMP = "声波测温"
    IMPORT_VF_MS = "进口V&F质谱仪"
    DOMESTIC_MS = "国产质谱仪"
    IMPORT_FID = "进口FID"
    DOMESTIC_FID = "国产FID"
    CEMS = "CEMS"
    FTIR = "FTIR"
    COMMON = "跨产品/公司通用"


class WorkFunction(str, Enum):
    """Canonical 7 workflow/functional categories (V3.0 separates finance & admin)."""

    SALES = "销售"
    MARKETING = "市场推广"
    MANUFACTURING = "生产制造"
    PROJECT_MGMT = "项目管理"
    TECH_SUPPORT = "技术支持与售后"
    RD_PCB = "产品与电路板研发"
    FINANCE_ADMIN = "财务与综合行政"


class TemplateSpec(BaseModel):
    """Immutable metadata for a WeCom Journal template."""

    model_config = ConfigDict(frozen=True)

    template_id: str = Field(min_length=8, max_length=128)
    internal_id: str = Field(default="")
    template_name: str = Field(min_length=1, max_length=120)
    report_type: ReportType
    status: Literal["active", "disabled"] = "active"
    confidentiality_level: Literal["standard", "finance_restricted"] = "standard"


# Legacy 5-template tuple retained for Slice 0 backward compatibility
DEFAULT_WECOM_TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        template_id="3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP",
        internal_id="40001105",
        template_name="晨会简报",
        report_type=ReportType.MORNING_BRIEF,
    ),
    TemplateSpec(
        template_id="C4c9RoeekLMSRRcqyurjgee3x7c6MUgPqN96rLmFr",
        internal_id="40001104",
        template_name="每日10分钟工作日报",
        report_type=ReportType.DAILY_10MIN,
    ),
    TemplateSpec(
        template_id="C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B",
        internal_id="40001101",
        template_name="现场技术支持工作日报",
        report_type=ReportType.FIELD_SUPPORT,
    ),
    TemplateSpec(
        template_id="C4c5FCnCK487vAdZ1mpe6gNMeFabs6zPTSHWmV5Dr",
        internal_id="40001102",
        template_name="现场技术支持工作日报（后补）",
        report_type=ReportType.FIELD_SUPPORT_BACKFILL,
        status="disabled",
    ),
    TemplateSpec(
        template_id="3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8",
        internal_id="40001103",
        template_name="研发产品性能测试和客户返厂维护维修设备日报",
        report_type=ReportType.RD_TEST_REPAIR,
    ),
)

TEMPLATE_BY_ID: dict[str, TemplateSpec] = {t.template_id: t for t in DEFAULT_WECOM_TEMPLATES}

# Authoritative 2026-11-28 7-template registry (6 active + 1 disabled historical)
NEW_TEMPLATE_EFFECTIVE_DATE = "2026-11-28"

ALL_WECOM_TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        template_id="3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP",
        internal_id="40001105",
        template_name="晨会简报",
        report_type=ReportType.MORNING_BRIEF,
        status="active",
    ),
    TemplateSpec(
        template_id="C4c9RoeekLMSRRcqyurjgee3x7c6MUgPqN96rLmFr",
        internal_id="40001104",
        template_name="每日10分钟工作日报",
        report_type=ReportType.DAILY_10MIN,
        status="active",
    ),
    TemplateSpec(
        template_id="C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B",
        internal_id="40001101",
        template_name="现场技术支持工作报告",
        report_type=ReportType.FIELD_SUPPORT,
        status="active",
    ),
    TemplateSpec(
        template_id="C4c5FCnCK487vAdZ1mpe6gNMeFabs6zPTSHWmV5Dr",
        internal_id="40001102",
        template_name="现场技术支持工作报告（后补）",
        report_type=ReportType.FIELD_SUPPORT_BACKFILL,
        status="disabled",
    ),
    TemplateSpec(
        template_id="3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8",
        internal_id="40001103",
        template_name="研发产品性能测试和客户返厂维护维修设备日报",
        report_type=ReportType.RD_TEST_REPAIR,
        status="active",
    ),
    TemplateSpec(
        template_id="3WPHEvnos5s9srSXWAqcs5hUgib4WwJYkb8yxAsZ",
        internal_id="40001106",
        template_name="财务每日10分钟工作简报",
        report_type=ReportType.FINANCE_DAILY_10MIN,
        status="active",
        confidentiality_level="finance_restricted",
    ),
    TemplateSpec(
        template_id="3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3",
        internal_id="40001107",
        template_name="现场每日10分钟工作报告",
        report_type=ReportType.FIELD_DAILY_10MIN,
        status="active",
    ),
)

ACTIVE_WECOM_TEMPLATES: tuple[TemplateSpec, ...] = tuple(
    t for t in ALL_WECOM_TEMPLATES if t.status == "active"
)
ALL_TEMPLATES_BY_ID: dict[str, TemplateSpec] = {t.template_id: t for t in ALL_WECOM_TEMPLATES}


class StaffRoleProfile(BaseModel):
    """Chairman-confirmed functional role mapping for each company employee."""

    model_config = ConfigDict(frozen=True)

    name: str
    role_group: str
    work_function: WorkFunction
    is_high_cost_rd: bool = False
    notes: str = ""


# Chairman-confirmed 15-person company roster (2026-11-27)
DEFAULT_COMPANY_ROSTER: tuple[StaffRoleProfile, ...] = (
    StaffRoleProfile(
        name="李文颖",
        role_group="高成本专职电路板/核心研发",
        work_function=WorkFunction.RD_PCB,
        is_high_cost_rd=True,
        notes="G5 专项聚焦审计对象：须高度对齐公司战略核心硬件/国产化突破",
    ),
    StaffRoleProfile(name="杨丽丽", role_group="销售", work_function=WorkFunction.SALES),
    StaffRoleProfile(name="吕旭东", role_group="销售", work_function=WorkFunction.SALES),
    StaffRoleProfile(name="刘家明", role_group="销售", work_function=WorkFunction.SALES),
    StaffRoleProfile(
        name="徐梦嘉",
        role_group="销售助理（兼职采购与市场宣传发布）",
        work_function=WorkFunction.MARKETING,
        notes="跨销售支持/采购/市场宣传发布，重点评估AI工作流自动化提效空间",
    ),
    StaffRoleProfile(name="陈晞", role_group="采购", work_function=WorkFunction.MANUFACTURING),
    StaffRoleProfile(
        name="孔紫初",
        role_group="项目经理",
        work_function=WorkFunction.PROJECT_MGMT,
        notes="每日晨会简报提交人",
    ),
    StaffRoleProfile(name="杨震", role_group="生产制造", work_function=WorkFunction.MANUFACTURING),
    StaffRoleProfile(name="薛蕾", role_group="财务", work_function=WorkFunction.FINANCE_ADMIN),
    StaffRoleProfile(name="王晓", role_group="财务", work_function=WorkFunction.FINANCE_ADMIN),
    StaffRoleProfile(name="王楠", role_group="技术支持工程师", work_function=WorkFunction.TECH_SUPPORT),
    StaffRoleProfile(name="王旭", role_group="技术支持工程师", work_function=WorkFunction.TECH_SUPPORT),
    StaffRoleProfile(name="赵勇成", role_group="技术支持工程师", work_function=WorkFunction.TECH_SUPPORT),
    StaffRoleProfile(name="石志同", role_group="技术支持工程师", work_function=WorkFunction.TECH_SUPPORT),
    StaffRoleProfile(name="牛海庆", role_group="技术支持工程师", work_function=WorkFunction.TECH_SUPPORT),
)

ROSTER_BY_NAME: dict[str, StaffRoleProfile] = {p.name: p for p in DEFAULT_COMPANY_ROSTER}


class WeComUserRecord(BaseModel):
    """Normalized company employee directory record for userid -> name/dept mapping."""

    model_config = ConfigDict(extra="ignore")

    userid: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    department_names: list[str] = Field(default_factory=list)
    position: str = Field(default="", max_length=128)
    is_active: bool = True


class WeComReportRecord(BaseModel):
    """Normalized, idempotent WeCom Journal submission stored in `ops_wecom_reports`."""

    model_config = ConfigDict(extra="ignore")

    journal_uuid: str = Field(min_length=1, max_length=160)
    template_id: str = Field(min_length=1, max_length=128)
    template_name: str = Field(min_length=1, max_length=160)
    report_type: ReportType
    submitter_userid: str = Field(min_length=1, max_length=128)
    submitter_name: str = Field(default="", max_length=128)
    department: str = Field(default="", max_length=160)
    report_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    work_date: str = Field(default="", max_length=10)
    submitted_at: str = Field(min_length=10, max_length=32)
    schema_era: Literal["legacy_v1", "upgraded_v2"] = "legacy_v1"
    confidentiality_level: Literal["standard", "finance_restricted"] = "standard"
    parsed_fields: dict[str, str] = Field(default_factory=dict)
    structured_extras: dict[str, Any] = Field(default_factory=dict)
    plain_text: str = Field(default="")
    attachment_media_ids: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SyncWatermarkRecord(BaseModel):
    """Per-template full-backfill & incremental sync cursor persisted in `ops_sync_watermarks`."""

    model_config = ConfigDict(extra="ignore")

    template_id: str = Field(min_length=1, max_length=128)
    template_name: str = Field(default="", max_length=160)
    report_type: str = Field(default="", max_length=64)
    template_status: Literal["active", "disabled_frozen"] = "active"
    full_backfill_completed: bool = False
    backfill_cursor_date: str = Field(default="", max_length=10)
    earliest_report_date: str = Field(default="", max_length=10)
    last_synced_at: str = Field(default="", max_length=32)
    total_records_synced: int = Field(default=0, ge=0)


class SmartSyncResult(BaseModel):
    """Deterministic return summary of a watermark-driven full/incremental sync run."""

    model_config = ConfigDict(extra="ignore")

    mode: Literal["full_backfill", "incremental", "mixed"]
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    templates_processed: int = Field(ge=0)
    templates_skipped_frozen: int = Field(default=0, ge=0)
    records_fetched: int = Field(ge=0)
    records_inserted: int = Field(ge=0)
    records_skipped_duplicate: int = Field(ge=0)
    legacy_unregistered_inserted: int = Field(default=0, ge=0)
    users_synced: int = Field(ge=0)
    archive_path: str = Field(default="")
    errors: list[str] = Field(default_factory=list)


class RoadmapGoal(BaseModel):
    """Company strategic objective & roadmap item persisted in `ops_company_roadmap`."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    goal_code: str = Field(min_length=1, max_length=64)
    horizon: str = Field(min_length=1, max_length=32, description="e.g. 2026-Q4 / 2027-H1")
    category: Literal["核心产品研发", "重点客户交付", "市场拓展", "降本与供应链", "组织能力"]
    title: str = Field(min_length=1, max_length=160)
    target_outcomes: str = Field(default="", max_length=1000)
    key_milestones: list[str] = Field(default_factory=list)
    target_effort_share_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    owner_names: list[str] = Field(default_factory=list)
    priority: Literal["P0", "P1", "P2"] = "P1"
    status: Literal["active", "paused", "completed"] = "active"


# Chairman-confirmed G1-G5 strategic baseline (2026-11-27)
DEFAULT_ROADMAP_GOALS: tuple[RoadmapGoal, ...] = (
    RoadmapGoal(
        goal_code="G1-SONIC-BREAKTHROUGH",
        horizon="2026-Q4~2027",
        category="市场拓展",
        title="声波测温在燃煤火电（燃烧优化）与垃圾焚烧（高效SNCR控制）双场景突破",
        target_outcomes="围绕燃烧优化与高效SNCR控制建立系统级价值卖点，有效平衡技术优势与价格竞争，形成标杆复制。",
        key_milestones=[
            "燃煤电厂结合燃烧优化形成标杆方案与ROI价值话术",
            "垃圾焚烧结合高效SNCR优化控制突破核心客户",
            "建立技术优势对冲价格竞争的报价与应答体系",
        ],
        target_effort_share_pct=30.0,
        owner_names=["杨丽丽", "吕旭东", "刘家明"],
        priority="P0",
    ),
    RoadmapGoal(
        goal_code="G2-VF-MS-HIGHEND",
        horizon="2026-Q4~2027",
        category="市场拓展",
        title="进口V&F质谱仪突破半导体与CCS/CCUS等高端高毛利市场",
        target_outcomes="摆脱低端价格内卷，在半导体工艺监测与CCS/CCUS高端工业场景建立实质商机与示范项目。",
        key_milestones=[
            "锁定半导体与CCS/CCUS头部目标客户清单并推进技术交流",
            "沉淀V&F高端应用场景解决方案与标杆试用",
        ],
        target_effort_share_pct=20.0,
        owner_names=["杨丽丽", "吕旭东", "刘家明"],
        priority="P0",
    ),
    RoadmapGoal(
        goal_code="G3-CN-MS-NICHE",
        horizon="2026-Q4~2027",
        category="核心产品研发",
        title="国产质谱仪卡位氢燃料电池与实验室研究细分场景",
        target_outcomes="推进国产质谱仪核心性能验证与稳定性提升，精准切入氢燃料电池及高校/科研实验室。",
        key_milestones=[
            "国产质谱仪关键性能测试达标与样机定型",
            "氢燃料电池与实验室客户试点落地",
        ],
        target_effort_share_pct=15.0,
        owner_names=["李文颖", "杨震"],
        priority="P1",
    ),
    RoadmapGoal(
        goal_code="G4-FID-EVOLUTION",
        horizon="2026-Q4~2027",
        category="核心产品研发",
        title="FID产品线两步走：守稳汽车VOC基本盘，国产化后切入工业在线检测",
        target_outcomes="当前依托进口FID稳住汽车VOC相关业务；同步推进国产FID落地筹备，具备国产设备后拓展在线检测市场。",
        key_milestones=[
            "稳固汽车VOC存量客户交付与维保口碑",
            "明确国产FID技术路线与在线检测切入场景",
        ],
        target_effort_share_pct=15.0,
        owner_names=["杨丽丽", "吕旭东", "李文颖"],
        priority="P1",
    ),
    RoadmapGoal(
        goal_code="G5-RD-COST-ALIGNMENT",
        horizon="2026-Q4~2027",
        category="组织能力",
        title="高成本专职电路板/核心研发人员（李文颖）工作与公司战略高度对齐",
        target_outcomes="确保高成本专职研发人力优先聚焦战略核心硬件与国产化突破，严控低价值打杂与无休止售后救火稀释研发主航道。",
        key_milestones=[
            "建立李文颖周度研发任务与战略目标映射台账",
            "核心研发精力聚焦战略主航道占比>=75%，明确硬交付里程碑",
        ],
        target_effort_share_pct=20.0,
        owner_names=["李文颖", "孔紫初"],
        priority="P0",
    ),
)


class InferredTask(BaseModel):
    """Concrete work task reconstructed across fragmented staff reports."""

    model_config = ConfigDict(extra="ignore")

    task_name: str = Field(min_length=1, max_length=160)
    product_line: ProductLine
    work_function: WorkFunction
    aligned_goal_code: str = Field(default="UNALIGNED", max_length=64)
    first_seen_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    last_seen_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    span_days: int = Field(ge=1)
    participants: list[str] = Field(default_factory=list)
    report_mentions: int = Field(ge=1)
    status: Literal["推进中", "停滞卡顿", "反复救火", "已闭环"] = "推进中"
    summary: str = Field(min_length=1, max_length=400)
    evidence_uuids: list[str] = Field(min_length=1)


class ChairmanOverlapItem(BaseModel):
    """Overlap mapping between Chairman's `list_items` task and staff reports."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    task_title: str = Field(min_length=1, max_length=200)
    overlap_status: Literal["高度对齐推进中", "部分提及但进展偏慢", "方向存在偏差"]
    matched_staff: list[str] = Field(default_factory=list)
    latest_ground_progress: str = Field(min_length=1, max_length=400)
    evidence_uuids: list[str] = Field(min_length=1)


class HighCostRdAudit(BaseModel):
    """Dedicated G5 alignment & ROI audit for high-cost PCB/R&D engineer (李文颖)."""

    model_config = ConfigDict(extra="ignore")

    engineer_name: str = Field(default="李文颖", min_length=1, max_length=64)
    total_reports_in_period: int = Field(ge=0)
    strategic_rd_share_pct: float = Field(ge=0.0, le=100.0)
    support_or_non_rd_share_pct: float = Field(ge=0.0, le=100.0)
    main_product_lines: list[str] = Field(default_factory=list)
    observed_deliverables: list[str] = Field(default_factory=list)
    drift_or_dilution_risks: list[str] = Field(default_factory=list)
    alignment_verdict: Literal["高度对齐", "部分稀释需纠偏", "严重偏离主航道"]
    reallocation_advice: str = Field(min_length=1, max_length=600)
    evidence_uuids: list[str] = Field(default_factory=list)


class AiTransformationOpportunity(BaseModel):
    """Concrete AI workflow automation, quality/compliance harness, or role-replacement opportunity."""

    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "重复事务自动化与岗位替代",
        "质量与合规刚性管控",
        "一线经验RAG知识化",
        "战略销售价值包装",
    ]
    target_workflow: str = Field(min_length=1, max_length=160)
    affected_roles: list[str] = Field(default_factory=list)
    current_pain_point: str = Field(min_length=1, max_length=400)
    ai_solution_and_harness: str = Field(min_length=1, max_length=500)
    efficiency_or_replacement_impact: str = Field(min_length=1, max_length=300)
    priority: Literal["P0", "P1", "P2"] = "P1"
    evidence_uuids: list[str] = Field(min_length=1)


class MissedTaskSuggestion(BaseModel):
    """Matter reported by staff that is missing from the Chairman's `list_items`."""

    model_config = ConfigDict(extra="ignore")

    suggested_title: str = Field(min_length=1, max_length=160)
    work_domain: Literal["产品研发", "客户销售", "项目交付", "采购供应链", "公司治理与人事", "个人思考"]
    priority: Literal["P0", "P1", "P2"] = "P1"
    reason: str = Field(min_length=1, max_length=400)
    involved_staff: list[str] = Field(default_factory=list)
    evidence_uuids: list[str] = Field(min_length=1)


class StalledTaskAlert(BaseModel):
    """Chairman open task (`list_items`) with no matching staff report progress."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    task_title: str = Field(min_length=1, max_length=200)
    days_without_report_mention: int = Field(ge=0)
    diagnostic_note: str = Field(min_length=1, max_length=400)


class GoalEffortBreakdown(BaseModel):
    """Actual staff effort share vs target share for a company roadmap goal."""

    model_config = ConfigDict(extra="ignore")

    goal_code: str = Field(min_length=1, max_length=64)
    goal_title: str = Field(min_length=1, max_length=160)
    target_effort_share_pct: float = Field(ge=0.0, le=100.0)
    estimated_actual_share_pct: float = Field(ge=0.0, le=100.0)
    alignment_status: Literal["aligned", "under_invested", "over_invested", "drifting"]
    evidence_uuids: list[str] = Field(default_factory=list)
    commentary: str = Field(min_length=1, max_length=400)


class StaffingRecommendation(BaseModel):
    """Actionable staffing, workload rebalancing, or workflow adjustment suggestion."""

    model_config = ConfigDict(extra="ignore")

    scope: Literal["人员负荷", "跨项目调配", "出差与售后救火", "研发资源聚焦", "流程与协同"]
    target_people_or_team: str = Field(min_length=1, max_length=120)
    observation: str = Field(min_length=1, max_length=400)
    recommendation: str = Field(min_length=1, max_length=400)
    evidence_uuids: list[str] = Field(min_length=1)


class AlignmentAuditReport(BaseModel):
    """Structured flagship brain output stored in `ops_alignment_audits`."""

    model_config = ConfigDict(extra="ignore")

    audit_kind: Literal["daily", "weekly", "baseline_30d"] = "daily"
    period_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    alignment_score: float = Field(ge=0.0, le=100.0)
    inferred_tasks: list[InferredTask] = Field(default_factory=list)
    chairman_overlap_tasks: list[ChairmanOverlapItem] = Field(default_factory=list)
    missed_tasks: list[MissedTaskSuggestion] = Field(default_factory=list)
    stalled_chairman_tasks: list[StalledTaskAlert] = Field(default_factory=list)
    goal_effort_breakdown: list[GoalEffortBreakdown] = Field(default_factory=list)
    high_cost_rd_audit: HighCostRdAudit | None = None
    staffing_recommendations: list[StaffingRecommendation] = Field(default_factory=list)
    ai_transformation_opportunities: list[AiTransformationOpportunity] = Field(default_factory=list)
    executive_brief_md: str = Field(min_length=1, max_length=12000)


class SyncResult(BaseModel):
    """Deterministic return summary of a WeCom Journal sync run."""

    model_config = ConfigDict(extra="ignore")

    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    templates_queried: int = Field(ge=0)
    records_fetched: int = Field(ge=0)
    records_inserted: int = Field(ge=0)
    records_skipped_duplicate: int = Field(ge=0)
    users_synced: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


_START_FENCE_RE = re.compile(r"\[UNTRUSTED_EXTERNAL_DATA_START:[^\]]*\]", flags=re.IGNORECASE)
_END_FENCE_RE = re.compile(r"\[UNTRUSTED_EXTERNAL_DATA_END\]", flags=re.IGNORECASE)


def wrap_untrusted_report_text(text: str, *, label: str = "WECOM_REPORT") -> str:
    """Physically fence untrusted employee report content against prompt injection."""
    safe_label = re.sub(r"[\]\r\n]+", "_", str(label or "WECOM_REPORT")).strip() or "WECOM_REPORT"
    sanitized = _START_FENCE_RE.sub("(redacted-start-fence)", text or "")
    sanitized = _END_FENCE_RE.sub("(redacted-end-fence)", sanitized)
    return f"[UNTRUSTED_EXTERNAL_DATA_START: {safe_label}]\n{sanitized}\n[UNTRUSTED_EXTERNAL_DATA_END]"


def validate_audit_grounding(
    report: AlignmentAuditReport,
    *,
    valid_journal_uuids: set[str],
    valid_chairman_task_ids: set[int],
) -> list[str]:
    """Deterministic Harness check: reject any hallucinated `journal_uuid` or `task_id`."""
    failures: list[str] = []
    for task in report.inferred_tasks:
        bad = [u for u in task.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"还原任务「{task.task_name}」引用了不存在的汇报UUID: {bad}")
    for ov in report.chairman_overlap_tasks:
        if ov.task_id not in valid_chairman_task_ids:
            failures.append(f"重叠对照引用了不存在的董事长任务ID: #{ov.task_id}")
        bad = [u for u in ov.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"重叠对照任务 #{ov.task_id} 引用了不存在的汇报UUID: {bad}")
    for item in report.missed_tasks:
        bad = [u for u in item.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"遗漏建议「{item.suggested_title}」引用了不存在的汇报UUID: {bad}")
    for stalled in report.stalled_chairman_tasks:
        if stalled.task_id not in valid_chairman_task_ids:
            failures.append(f"停滞任务预警引用了不存在的董事长任务ID: #{stalled.task_id}")
    for g in report.goal_effort_breakdown:
        bad = [u for u in g.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"战略目标「{g.goal_code}」引用了不存在的汇报UUID: {bad}")
    if report.high_cost_rd_audit is not None:
        bad = [u for u in report.high_cost_rd_audit.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(
                f"高成本研发审计「{report.high_cost_rd_audit.engineer_name}」引用了不存在的汇报UUID: {bad}"
            )
    for rec in report.staffing_recommendations:
        bad = [u for u in rec.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"人员配置建议「{rec.target_people_or_team}」引用了不存在的汇报UUID: {bad}")
    for ai_opp in report.ai_transformation_opportunities:
        bad = [u for u in ai_opp.evidence_uuids if u not in valid_journal_uuids]
        if bad:
            failures.append(f"AI提效替代建议「{ai_opp.target_workflow}」引用了不存在的汇报UUID: {bad}")
    return failures


# ==============================================================================
# V3.0 Dual-Track Contracts (06_ANALYSIS_FRAMEWORK_AND_REPORT_TEMPLATE_SPEC.md)
# ==============================================================================


class TransformationTag(str, Enum):
    """Orthogonal strategic transformation tags (5 canonical values)."""

    LOCALIZATION = "本土化与国产替代"
    CHANNEL_ENABLEMENT = "渠道赋能与分销转型"
    LEAN_MFG_KNOWHOW = "轻资产制造与保Know-How"
    OVERSEAS = "海外市场拓展"
    FIREFIGHTING_WASTE = "终端救火与低效内耗"


class TrajectoryStatus(str, Enum):
    """5-tier dynamic trajectory verdict across 4 rolling horizons."""

    IMPROVING = "持续向好 ↗"
    STEADY = "稳步推进 →"
    OSCILLATING = "波动反复 ↔"
    DETERIORATING = "偏离恶化 ↘"
    BASELINE_ONLY = "基线初建 ○"


class AlertTrack(str, Enum):
    """Dual-track governance alert source track."""

    STRATEGIC = "战略轨"
    QUALITY = "质量轨"


class AlertSeverity(str, Enum):
    """Three-level graded alert severity."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    OPTIMIZATION = "OPTIMIZATION"


class StaffReportingQualityItem(BaseModel):
    """Track 1 per-employee reporting & project management quality rating."""

    model_config = ConfigDict(extra="ignore")

    staff_name: str = Field(min_length=1, max_length=64)
    role_group: str = Field(default="", max_length=120)
    sop_compliance: Literal["绿", "黄", "红", "基线免评"] = "绿"
    traceability_and_archiving: Literal["绿", "黄", "红", "基线免评"] = "绿"
    tangible_deliverables: Literal["绿", "黄", "红", "基线免评"] = "绿"
    value_closure: Literal["绿", "黄", "红", "基线免评"] = "绿"
    hollow_report_flag: bool = False
    benchmark_highlight: str = Field(default="", max_length=300)
    commentary: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list)


class GoalEffortLedgerItem(BaseModel):
    """Track 2 quantitative effort & hard deliverable ledger per active strategic goal."""

    model_config = ConfigDict(extra="ignore")

    goal_tier: Literal["long_term", "annual", "quarterly", "monthly"] = "long_term"
    goal_code: str = Field(min_length=1, max_length=64)
    goal_title: str = Field(min_length=1, max_length=240)
    contributor_count: int = Field(ge=0)
    contributors: list[str] = Field(default_factory=list)
    report_mentions: int = Field(ge=0)
    estimated_person_days: float = Field(ge=0.0)
    total_effort_share_pct: float = Field(ge=0.0, le=100.0)
    effective_strategic_share_pct: float = Field(ge=0.0, le=100.0)
    firefighting_or_maintenance_share_pct: float = Field(ge=0.0, le=100.0)
    observed_hard_deliverables: list[str] = Field(default_factory=list)
    trajectory_verdict: TrajectoryStatus = TrajectoryStatus.BASELINE_ONLY
    commentary: str = Field(min_length=1, max_length=600)
    evidence_refs: list[str] = Field(default_factory=list)


class GovernanceAlert(BaseModel):
    """Red/Yellow/Blue 6-element governance alert emitted by Red-Team critic."""

    model_config = ConfigDict(extra="ignore")

    alert_id: str = Field(default="", max_length=32)
    track: AlertTrack
    severity: AlertSeverity
    category: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    quant_data: str = Field(min_length=1, max_length=300)
    evidence_refs: list[str] = Field(min_length=1)
    recommended_action: str = Field(min_length=1, max_length=500)
    verification_status: Literal["verified", "degraded_unverified"] = "verified"


class DualTrackInferredTask(BaseModel):
    """V3.0 reconstructed concrete work task with 8x7x5 classification."""

    model_config = ConfigDict(extra="ignore")

    task_name: str = Field(min_length=1, max_length=160)
    product_line: ProductLine
    work_function: WorkFunction
    transformation_tags: list[TransformationTag] = Field(default_factory=list)
    aligned_goal_code: str = Field(default="UNALIGNED", max_length=64)
    first_seen_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    last_seen_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    span_days: int = Field(ge=1)
    participants: list[str] = Field(default_factory=list)
    report_mentions: int = Field(ge=1)
    status: Literal["推进中", "停滞卡顿", "反复救火", "已闭环"] = "推进中"
    summary: str = Field(min_length=1, max_length=400)
    evidence_refs: list[str] = Field(min_length=1)


class DualTrackAuditReport(BaseModel):
    """Authoritative V3.0 Dual-Track Audit & Graded Alert Report."""

    model_config = ConfigDict(extra="ignore")

    audit_kind: Literal["weekly", "monthly", "baseline_30d"] = "weekly"
    period_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    active_goal_tiers: list[str] = Field(default_factory=lambda: ["long_term"])
    skipped_empty_goal_tiers: list[str] = Field(default_factory=lambda: ["annual", "quarterly", "monthly"])
    overall_hard_deliverable_pass_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    alignment_score: float = Field(ge=0.0, le=100.0)
    alerts: list[GovernanceAlert] = Field(default_factory=list)
    staff_quality_matrix: list[StaffReportingQualityItem] = Field(default_factory=list)
    goal_effort_ledger: list[GoalEffortLedgerItem] = Field(default_factory=list)
    unaligned_overhead_pool_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    unaligned_overhead_person_days: float = Field(default=0.0, ge=0.0)
    inferred_tasks: list[DualTrackInferredTask] = Field(default_factory=list)
    long_term_transformation_summary: list[str] = Field(default_factory=list)
    high_cost_rd_audit: HighCostRdAudit | None = None
    chairman_overlap_tasks: list[ChairmanOverlapItem] = Field(default_factory=list)
    missed_tasks: list[MissedTaskSuggestion] = Field(default_factory=list)
    stalled_chairman_tasks: list[StalledTaskAlert] = Field(default_factory=list)
    staffing_recommendations: list[StaffingRecommendation] = Field(default_factory=list)
    ai_transformation_opportunities: list[AiTransformationOpportunity] = Field(default_factory=list)
    executive_brief_md: str = Field(min_length=1, max_length=16000)
    degraded_notes: list[str] = Field(default_factory=list)


class StrategicGoalItem(BaseModel):
    """Single goal entry loaded from `config/strategic_goals.json`."""

    model_config = ConfigDict(extra="ignore")

    goal_code: str = Field(min_length=1, max_length=64)
    parent_goal_code: str = Field(default="", max_length=64)
    priority: Literal["P0", "P1", "P2"] = "P1"
    title: str = Field(min_length=1, max_length=260)
    product_lines: list[str] = Field(default_factory=list)
    vision_and_end_state: str = Field(default="")
    target_outcomes: str = Field(default="")
    evaluation_redlines: list[str] = Field(default_factory=list)
    positive_trend_signals: list[str] = Field(default_factory=list)
    status: Literal["active", "paused", "completed", "draft"] = "active"


class StrategicGoalsConfig(BaseModel):
    """Typed loader for `config/strategic_goals.json` supporting sparse-tier auto-skip."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="2.3")
    company: dict[str, Any] = Field(default_factory=dict)
    sparse_tier_policy: dict[str, Any] = Field(default_factory=dict)
    reporting_attendance_rules: dict[str, Any] = Field(default_factory=dict)
    dual_track_evaluation_policy: dict[str, Any] = Field(default_factory=dict)
    sync_and_analysis_policy: dict[str, Any] = Field(default_factory=dict)
    goals: dict[str, list[StrategicGoalItem]] = Field(default_factory=dict)

    @property
    def new_template_effective_date(self) -> str:
        return str(
            self.dual_track_evaluation_policy.get("new_wecom_template_effective_date")
            or NEW_TEMPLATE_EFFECTIVE_DATE
        )

    @property
    def initial_backfill_start_date(self) -> str:
        ing = self.sync_and_analysis_policy.get("data_ingestion") or {}
        return str(ing.get("initial_backfill_start_date") or "2022-12-01")

    @property
    def max_investigation_steps(self) -> int:
        limits = self.sync_and_analysis_policy.get("agent_loop_limits") or {}
        return int(limits.get("max_investigation_steps") or 18)

    @property
    def max_verification_retries(self) -> int:
        limits = self.sync_and_analysis_policy.get("agent_loop_limits") or {}
        return int(limits.get("max_verification_retries") or 2)

    def active_goals_by_tier(self) -> dict[str, list[StrategicGoalItem]]:
        out: dict[str, list[StrategicGoalItem]] = {}
        for tier in ("long_term", "annual", "quarterly", "monthly"):
            items = [g for g in (self.goals.get(tier) or []) if g.status == "active"]
            if items:
                out[tier] = items
        return out

    def active_tiers(self) -> list[str]:
        return list(self.active_goals_by_tier().keys())

    def empty_tiers(self) -> list[str]:
        active = set(self.active_tiers())
        return [t for t in ("long_term", "annual", "quarterly", "monthly") if t not in active]


def load_strategic_goals_config(config_path: Any = None) -> StrategicGoalsConfig:
    """Load and validate `config/strategic_goals.json` (single source of truth)."""
    import json
    from pathlib import Path

    path = Path(config_path) if config_path else (Path(__file__).resolve().parent / "config" / "strategic_goals.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return StrategicGoalsConfig.model_validate(raw)


class GroundingCheckResult(BaseModel):
    """Deterministic verification outcome for `DualTrackAuditReport`."""

    model_config = ConfigDict(extra="ignore")

    passed: bool
    degraded: bool = False
    failures: list[str] = Field(default_factory=list)
    degraded_notes: list[str] = Field(default_factory=list)
    hydrated_report: DualTrackAuditReport | None = None


_FORBIDDEN_EXECUTIVE_JARGON: tuple[str, ...] = (
    "ops_wecom_reports",
    "ops_alignment_audits",
    "ops_sync_watermarks",
    "ops_company_roadmap",
    "ops_wecom_users",
    "ops_delivery_locks",
    "list_items",
    "journal_uuid",
    "apply_data",
    "DualTrackAuditReport",
)

_SEVERITY_ORDER: dict[AlertSeverity, int] = {
    AlertSeverity.CRITICAL: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.OPTIMIZATION: 2,
}


def validate_dual_track_grounding(
    report: DualTrackAuditReport,
    *,
    short_ref_to_uuid: dict[str, str],
    valid_chairman_task_ids: set[int],
    allow_degrade_minor: bool = False,
) -> GroundingCheckResult:
    """Verify R-xxx / UUID refs, task IDs, date math, jargon-free prose, & grade-sort alerts."""
    valid_uuids = set(short_ref_to_uuid.values())
    hydrated = report.model_copy(deep=True)
    hard_failures: list[str] = []
    degraded_notes: list[str] = list(hydrated.degraded_notes)
    degraded = False

    def _resolve_list(refs: list[str]) -> tuple[list[str], list[str]]:
        resolved: list[str] = []
        bad: list[str] = []
        for raw in refs:
            tok = str(raw or "").strip()
            if tok in short_ref_to_uuid:
                resolved.append(short_ref_to_uuid[tok])
            elif tok in valid_uuids:
                resolved.append(tok)
            else:
                bad.append(tok)
        return resolved, bad

    # 1. Hard invariant: zero code/DB jargon in executive_brief_md
    brief = hydrated.executive_brief_md or ""
    for jargon in _FORBIDDEN_EXECUTIVE_JARGON:
        if jargon in brief:
            hard_failures.append(f"高管执行摘要泄露内部技术黑话: `{jargon}`")

    # 2. Inferred tasks: date logic + evidence refs
    for task in hydrated.inferred_tasks:
        if task.last_seen_date < task.first_seen_date:
            hard_failures.append(
                f"还原任务「{task.task_name}」日期倒挂: first_seen_date={task.first_seen_date} > last_seen_date={task.last_seen_date}"
            )
        resolved, bad = _resolve_list(task.evidence_refs)
        if bad:
            hard_failures.append(f"还原任务「{task.task_name}」引用了不存在的汇报编号: {bad}")
        else:
            task.evidence_refs = resolved

    # 3. Staff quality matrix (Track 1)
    for item in hydrated.staff_quality_matrix:
        if item.evidence_refs:
            resolved, bad = _resolve_list(item.evidence_refs)
            if bad:
                hard_failures.append(f"员工质量评估「{item.staff_name}」引用了不存在的汇报编号: {bad}")
            else:
                item.evidence_refs = resolved

    # 4. Goal effort ledger (Track 2)
    for ledger in hydrated.goal_effort_ledger:
        if ledger.evidence_refs:
            resolved, bad = _resolve_list(ledger.evidence_refs)
            if bad:
                hard_failures.append(f"目标投入总账「{ledger.goal_code}」引用了不存在的汇报编号: {bad}")
            else:
                ledger.evidence_refs = resolved

    # 5. Chairman overlap & stalled tasks
    for ov in hydrated.chairman_overlap_tasks:
        if ov.task_id not in valid_chairman_task_ids:
            hard_failures.append(f"董事长任务对齐引用了不存在的任务ID: #{ov.task_id}")
        resolved, bad = _resolve_list(ov.evidence_uuids)
        if bad:
            hard_failures.append(f"董事长任务 #{ov.task_id} 引用了不存在的汇报编号: {bad}")
        else:
            ov.evidence_uuids = resolved

    for stalled in hydrated.stalled_chairman_tasks:
        if stalled.task_id not in valid_chairman_task_ids:
            hard_failures.append(f"挂单空转预警引用了不存在的董事长任务ID: #{stalled.task_id}")

    # 6. Missed tasks, high-cost R&D, staffing, AI opportunities
    for mt in hydrated.missed_tasks:
        resolved, bad = _resolve_list(mt.evidence_uuids)
        if bad:
            hard_failures.append(f"盲区遗漏建议「{mt.suggested_title}」引用了不存在的汇报编号: {bad}")
        else:
            mt.evidence_uuids = resolved

    if hydrated.high_cost_rd_audit is not None and hydrated.high_cost_rd_audit.evidence_uuids:
        resolved, bad = _resolve_list(hydrated.high_cost_rd_audit.evidence_uuids)
        if bad:
            hard_failures.append(
                f"高成本研发专项审计「{hydrated.high_cost_rd_audit.engineer_name}」引用了不存在的汇报编号: {bad}"
            )
        else:
            hydrated.high_cost_rd_audit.evidence_uuids = resolved

    for rec in hydrated.staffing_recommendations:
        resolved, bad = _resolve_list(rec.evidence_uuids)
        if bad:
            hard_failures.append(f"人员配置建议「{rec.target_people_or_team}」引用了不存在的汇报编号: {bad}")
        else:
            rec.evidence_uuids = resolved

    for ai_opp in hydrated.ai_transformation_opportunities:
        resolved, bad = _resolve_list(ai_opp.evidence_uuids)
        if bad:
            hard_failures.append(f"AI提效建议「{ai_opp.target_workflow}」引用了不存在的汇报编号: {bad}")
        else:
            ai_opp.evidence_uuids = resolved

    # 7. Alerts: strict check OR graceful minor degradation when allow_degrade_minor=True
    alert_failures: list[str] = []
    for alert in hydrated.alerts:
        resolved, bad = _resolve_list(alert.evidence_refs)
        if bad:
            if allow_degrade_minor:
                alert.verification_status = "degraded_unverified"
                if resolved:
                    alert.evidence_refs = resolved
                note = (
                    f"告警 {alert.alert_id or alert.title} 包含未核实汇报引用 {bad}，已自动标灰降级放行（不阻断已实证预警投递）。"
                )
                degraded_notes.append(note)
                degraded = True
            else:
                alert_failures.append(
                    f"预警「{alert.alert_id or alert.title}」引用了不存在的汇报编号: {bad}"
                )
        else:
            alert.evidence_refs = resolved
            alert.verification_status = "verified"

    # Sort alerts strictly: CRITICAL -> WARNING -> OPTIMIZATION
    hydrated.alerts.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 9), a.alert_id))
    hydrated.degraded_notes = degraded_notes

    all_failures = hard_failures + alert_failures
    passed = len(all_failures) == 0
    return GroundingCheckResult(
        passed=passed,
        degraded=degraded and passed,
        failures=all_failures,
        degraded_notes=degraded_notes,
        hydrated_report=hydrated if passed else None,
    )
