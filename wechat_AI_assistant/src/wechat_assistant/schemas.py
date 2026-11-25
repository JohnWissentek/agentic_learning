"""Core Pydantic v2 domain schemas for the Chief-of-Staff workflow (v2.0 flat task cards)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


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
    referenced_numbers: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    overload_warning: str | None = None


class CriticVerdict(BaseModel):
    """Heterogeneous critic-tier audit verdict (`deepseek-v4-pro`)."""

    passed: bool
    numeric_fidelity_ok: bool = True
    schedule_reasonable: bool = True
    issues: list[str] = Field(default_factory=list)
    fix_instructions: str = ""
