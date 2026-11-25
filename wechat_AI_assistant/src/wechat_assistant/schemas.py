"""Core Pydantic v2 domain schemas for the Chief-of-Staff workflow (v2.0 flat task cards)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkDomain(str, Enum):
    """Business energy allocation domains."""

    RD = "产品研发"
    SALES = "客户销售"
    DELIVERY = "项目交付"
    SUPPLY_CHAIN = "采购供应链"
    GOVERNANCE = "公司治理与人事"
    THINKING = "个人思考"


class ListType(str, Enum):
    """Four personal executive lists."""

    PROJECT_ACTION = "project_action"
    NEXT_ACTION = "next_action"
    IDEA = "idea"
    WAITING_FOR = "waiting_for"


class PriorityLevel(str, Enum):
    """Dynamic priority grades."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class IntentRoute(BaseModel):
    """Fast-tier context-aware triage classification result (`qwen3.8-flash`)."""

    model_config = ConfigDict(extra="ignore")

    intent: Literal[
        "work_triage",
        "quick_query",
        "conversational_chat",
        "confirm_pending",
        "ideas_only_pending",
        "discard_pending",
        "revise_pending",
        "mutate_existing_item",
        "update_item_fields",
        "checkin",
        "append_note",
        "view_timeline",
        "undo",
        "open_cockpit",
        "show_workload",
        "chitchat",
        "clarify_or_unsupported",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    target_item_id: int | None = None
    actual_hours: float | None = None
    note_kind: Literal["progress", "comment", "ceo_evaluation", ""] = ""
    note_content: str = ""
    resolved_intent_text: str = ""
    search_queries: list[str] = Field(default_factory=list)
    clarify_question: str = ""
    summary: str = Field(min_length=1, max_length=200)


class EvidenceCard(BaseModel):
    """Compressed retrieval evidence (Level 2 Context Engineering)."""

    source_id: str
    title: str
    snippet: str
    page_ref: str | None = None
    relevance: float = Field(default=0.8, ge=0.0, le=1.0)


class TimelineEntry(BaseModel):
    """Timestamped progress or communication log attached to an independent task card."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = ""
    channel: Literal["wechat", "mail_in", "mail_out", "web"] = "wechat"
    from_party: str = ""
    to_party: str = ""
    cc_parties: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=300)
    source_ref: str = ""
    mail_conversation_id: str = ""


class TimestampedNote(BaseModel):
    """Append-only dated note for `comments` (objective) or `ceo_evaluation` (Chairman subjective)."""

    model_config = ConfigDict(extra="ignore")

    date: str = ""
    content: str = Field(min_length=1, max_length=500)


class ActionMutation(BaseModel):
    """Flat independent task card mutation (v2.0: 1 matter = 1 task card, 100% backward compatible)."""

    model_config = ConfigDict(extra="ignore")

    list_type: ListType
    work_domain: WorkDomain
    project_name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    deliverable: str = Field(default="", max_length=300)
    acceptance_criteria: str = Field(default="", max_length=300)
    milestone_stage: str = Field(default="已启动", max_length=80)
    owner: str = "本人"
    assignee: str = ""
    external_partner: str = "无"
    chairman_role: Literal["owner", "assignee", "cc_observer", "approver"] = "owner"
    role_inference_reason: str = Field(default="", max_length=200)
    planned_start_at: str = Field(default="", description="ISO date YYYY-MM-DD")
    planned_end_at: str = Field(default="", description="ISO date YYYY-MM-DD or '' when TBD")
    estimated_hours: float = Field(default=0.0, ge=0.0, le=200.0)
    priority: PriorityLevel = PriorityLevel.P1
    blocker_note: str = Field(default="", max_length=300)
    source_channel: Literal["wechat", "outlook", "web"] = "wechat"
    linked_files: list[str] = Field(default_factory=list)
    mail_conversation_ids: list[str] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    comments: list[TimestampedNote] = Field(default_factory=list)
    ceo_evaluation: list[TimestampedNote] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    onedrive_target_dir: str = "01_项目归档"

    @field_validator("missing_required_fields", mode="before")
    @classmethod
    def _normalize_missing_fields(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        alias_map = {
            "归属项目": "project_name",
            "项目名": "project_name",
            "目标与交付成果": "deliverable",
            "交付成果": "deliverable",
            "交付物": "deliverable",
            "负责人": "owner",
            "实施人": "assignee",
            "执行人": "assignee",
            "目标截止时间": "planned_end_at",
            "目标截止日期": "planned_end_at",
            "截止时间": "planned_end_at",
            "截止日期": "planned_end_at",
            "截止日": "planned_end_at",
        }
        out: list[str] = []
        for item in v:
            s = str(item or "").strip()
            mapped = alias_map.get(s, s)
            if mapped and mapped not in out:
                out.append(mapped)
        return out


class TaskTimelineUpdate(BaseModel):
    """Append a communication/progress update onto an existing open task without creating duplicates."""

    model_config = ConfigDict(extra="ignore")

    target_task_id: int
    target_task_title: str = ""
    match_method: Literal["conversation_id", "semantic_match"] = "semantic_match"
    timeline_entry: TimelineEntry
    milestone_stage_update: str = ""
    blocker_note_update: str = ""
    comment_append: str = ""


class FyiNotice(BaseModel):
    """Pure CC / team-sync notice displayed in summary without creating a redundant task card."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = ""
    from_party: str = ""
    to_party: str = ""
    summary: str = Field(min_length=1, max_length=240)
    mail_conversation_id: str = ""


class MailDigestItem(BaseModel):
    """Per-email executive digest item paired deterministically with Graph headers (`MAIL-k`)."""

    model_config = ConfigDict(extra="ignore")

    mail_ref: str = Field(min_length=1, max_length=32, description="邮件短编号，如 MAIL-1")
    main_content: str = Field(min_length=1, max_length=220, description="1~2 句精炼主要内容")
    action_type: Literal[
        "需您回复",
        "需建卡跟进",
        "归入已有任务",
        "团队跟进(您仅抄送)",
        "纯知会免处理",
    ] = "需建卡跟进"
    suggested_action: str = Field(min_length=1, max_length=180, description="一句话具体处理建议")


class MailBatchDigest(BaseModel):
    """Read-only per-email digest batch (used when deferring new confirmation card creation)."""

    model_config = ConfigDict(extra="ignore")

    items: list[MailDigestItem] = Field(default_factory=list)


class TriageProposal(BaseModel):
    """Unified Path-4 structured Chief-of-Staff proposal shared by WeChat and hourly mail batches."""

    model_config = ConfigDict(extra="ignore")

    headline: str = Field(min_length=1, max_length=120)
    executive_summary: str = Field(default="", max_length=800)
    actions: list[ActionMutation] = Field(
        default_factory=list,
        validation_alias=AliasChoices("actions", "new_tasks"),
    )
    task_updates: list[TaskTimelineUpdate] = Field(default_factory=list)
    fyi_notices: list[FyiNotice] = Field(default_factory=list)
    mail_digests: list[MailDigestItem] = Field(default_factory=list)
    referenced_numbers: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    overload_warning: str | None = None


class CriticVerdict(BaseModel):
    """Legacy audit verdict schema kept for backward compatibility."""

    passed: bool
    numeric_fidelity_ok: bool = True
    schedule_reasonable: bool = True
    issues: list[str] = Field(default_factory=list)
    fix_instructions: str = ""


class TaskFieldUpdate(BaseModel):
    """Direct structured modification to an existing persisted task card."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    planned_end_at: str | None = None
    planned_start_at: str | None = None
    assignee: str | None = None
    owner: str | None = None
    external_partner: str | None = None
    deliverable: str | None = None
    milestone_stage: str | None = None
    blocker_note: str | None = None
    priority: PriorityLevel | None = None
    project_name: str | None = None


class TaskNoteAppend(BaseModel):
    """Append a CEO evaluation, objective comment, or progress timeline entry to an existing task."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    kind: Literal["ceo_evaluation", "comment", "progress"]
    content: str = Field(min_length=1, max_length=500)


class TaskStatusChange(BaseModel):
    """Mark an existing task started (`in_progress`) or completed (`done`)."""

    model_config = ConfigDict(extra="ignore")

    task_id: int
    action: Literal["start", "complete"]
    actual_hours: float | None = None


class AgentDecision(BaseModel):
    """v3.0 Single-Brain Flagship Agent unified output contract (Model-First, Plan A).

    A single flagship LLM turn (`qwen3.8-max`) natively handles:
    - creating/revising task proposals (with optional `confirm_and_commit=True` 1-step commit),
    - confirming/discarding pending proposals,
    - executing compound direct operations on existing tasks (field updates, notes, status check-ins, timeline, undo),
    - grounded Q&A or executive conversation, cockpit/workload lookups.
    """

    model_config = ConfigDict(extra="ignore")

    mode: Literal[
        "propose",
        "confirm_pending",
        "discard_pending",
        "direct_ops",
        "reply",
        "open_cockpit",
        "show_workload",
    ] = "reply"
    proposal: TriageProposal | None = None
    confirm_and_commit: bool = False
    ideas_only: bool = False
    field_updates: list[TaskFieldUpdate] = Field(default_factory=list)
    note_appends: list[TaskNoteAppend] = Field(default_factory=list)
    status_changes: list[TaskStatusChange] = Field(default_factory=list)
    view_timeline_ids: list[int] = Field(default_factory=list)
    undo_last: bool = False
    reply_text: str = Field(default="", max_length=2500)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_shapes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "mode" in data:
            return data
        # Backward compatibility: direct TriageProposal payload
        if "headline" in data and ("actions" in data or "new_tasks" in data or "task_updates" in data or "fyi_notices" in data):
            return {"mode": "propose", "proposal": data}
        # Backward compatibility: direct Q&A or conversational reply payload
        if "answer" in data:
            return {"mode": "reply", "reply_text": str(data.get("answer") or "")}
        if "reply" in data:
            return {"mode": "reply", "reply_text": str(data.get("reply") or "")}
        if "reply_text" in data:
            return {"mode": "reply", "reply_text": str(data.get("reply_text") or "")}
        if any(k in data for k in ("field_updates", "note_appends", "status_changes", "view_timeline_ids", "undo_last")):
            return {"mode": "direct_ops", **data}
        raise ValueError("AgentDecision JSON must specify 'mode' or recognized decision fields")
