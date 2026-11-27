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
    """Canonical enum for all 5 WeCom report templates in 维恩科仪."""

    MORNING_BRIEF = "morning_brief"
    DAILY_10MIN = "daily_10min"
    FIELD_SUPPORT = "field_support"
    FIELD_SUPPORT_BACKFILL = "field_support_backfill"
    RD_TEST_REPAIR = "rd_test_repair"


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
    """Canonical 6 workflow/functional categories."""

    SALES = "销售"
    MARKETING = "市场推广"
    MANUFACTURING = "生产制造"
    PROJECT_MGMT = "项目管理"
    TECH_SUPPORT = "技术支持与售后"
    RD_PCB = "产品与电路板研发"


class TemplateSpec(BaseModel):
    """Immutable metadata for a WeCom Journal template."""

    model_config = ConfigDict(frozen=True)

    template_id: str = Field(min_length=8, max_length=128)
    internal_id: str = Field(default="")
    template_name: str = Field(min_length=1, max_length=120)
    report_type: ReportType


# Official live-verified WeCom Journal templates for 维恩科仪 (CorpID: ww9238966755b26e48)
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
    ),
    TemplateSpec(
        template_id="3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8",
        internal_id="40001103",
        template_name="研发产品性能测试和客户返厂维护维修设备日报",
        report_type=ReportType.RD_TEST_REPAIR,
    ),
)

TEMPLATE_BY_ID: dict[str, TemplateSpec] = {t.template_id: t for t in DEFAULT_WECOM_TEMPLATES}


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
    StaffRoleProfile(name="薛蕾", role_group="财务", work_function=WorkFunction.PROJECT_MGMT),
    StaffRoleProfile(name="王晓", role_group="财务", work_function=WorkFunction.PROJECT_MGMT),
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
    submitted_at: str = Field(min_length=10, max_length=32)
    parsed_fields: dict[str, str] = Field(default_factory=dict)
    plain_text: str = Field(default="")
    attachment_media_ids: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


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
