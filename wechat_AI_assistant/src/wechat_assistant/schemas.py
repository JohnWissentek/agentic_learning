"""Core Pydantic v2 domain schemas for the Chief-of-Staff workflow."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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

    intent: Literal[
        "work_triage",
        "quick_query",
        "conversational_chat",
        "confirm_pending",
        "ideas_only_pending",
        "discard_pending",
        "revise_pending",
        "mutate_existing_item",
        "checkin",
        "undo",
        "open_cockpit",
        "show_workload",
        "chitchat",
        "clarify_or_unsupported",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    needs_deep_research: bool = False
    target_item_id: int | None = None
    actual_hours: float | None = None
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


class ActionMutation(BaseModel):
    """Atomic list & schedule proposal item separating net effort hours from calendar duration."""

    list_type: ListType
    work_domain: WorkDomain
    project_name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    owner: str = "本人"
    planned_start_at: str = Field(description="ISO date YYYY-MM-DD")
    planned_end_at: str = Field(description="ISO date YYYY-MM-DD")
    estimated_hours: float = Field(default=0.0, ge=0.0, le=200.0)
    priority: PriorityLevel = PriorityLevel.P1
    onedrive_target_dir: str = "01_项目归档"


class TriageProposal(BaseModel):
    """Producer-tier structured Chief-of-Staff recommendation card (`qwen3.8-max`)."""

    headline: str = Field(min_length=1, max_length=120)
    executive_summary: str = Field(min_length=1, max_length=800)
    actions: list[ActionMutation] = Field(default_factory=list)
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
