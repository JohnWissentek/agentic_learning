"""Black-box contract tests for v2.0 flat independent task cards, From/To/Cc mail role
inference & conversation threading, Morning Digest v2.0, WeChat note/progress shortcuts,
and Web API v2.0 endpoints.

Strictly derived from:
- `src/wechat_assistant/schemas.py`
- `report_templates/早间工作报告.md`
- `report_templates/邮件汇总模板.md`
- `report_templates/task_card_schema.json`
- `config/mail_domains.json`
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine, format_decision_card
from wechat_assistant.intake import mail_poller
from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.schemas import (
    ActionMutation,
    FyiNotice,
    ListType,
    PriorityLevel,
    TaskTimelineUpdate,
    TimelineEntry,
    TimestampedNote,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage.db import Database
from wechat_assistant.web.app import build_daily_digest_message, create_app

SHANGHAI = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Deterministic external gateway stubs (LLM / OneDrive / Graph Mail)
# ---------------------------------------------------------------------------


class _DummyOneDrive:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.synced_boards: dict[str, str] = {}

    def _get_token(self) -> str:
        return "fake-mail-token"

    def upload_bytes(self, remote_path: str, data: bytes, *, content_type: str = "") -> dict[str, Any]:
        self.uploads[remote_path] = data
        return {
            "id": f"id_{len(self.uploads)}",
            "webUrl": f"https://wissentek.sharepoint.cn/mock/{remote_path}",
            "size": len(data),
        }

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        return {}


class _ScriptedCompletions:
    """Deterministic fake OpenAI completions recording every model & message payload."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=50, completion_tokens=40, completion_tokens_details=None),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content, tool_calls=None, reasoning_content="")
                )
            ],
        )


def _make_settings(tmp_path: Path, *, mail_user: str = "john.xu@palmarytech.com") -> Settings:
    return Settings(
        dashscope_api_key="sk-fakeunit1234567890abcdef",
        web_access_secret="unit-test-hmac-secret-key-1234567890",
        data_dir=str(tmp_path / "data"),
        wecom_corp_id="wwtestcorp",
        wecom_app_agent_id="1000002",
        wecom_app_token="tokentest123456",
        wecom_app_aes_key="A" * 43,
        mail_enabled=True,
        mail_user=mail_user,
    )


def _make_graph_msg(
    *,
    msg_id: str,
    internet_id: str,
    subject: str,
    sender: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    conversation_id: str = "",
    received_utc: str | None = None,
    sent_utc: str | None = None,
    body_preview: str = "",
    body_content: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "id": msg_id,
        "internetMessageId": internet_id,
        "conversationId": conversation_id,
        "subject": subject,
        "from": {"emailAddress": {"name": sender.split("@")[0], "address": sender}},
        "toRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in to_addrs],
        "ccRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in (cc_addrs or [])],
        "bodyPreview": body_preview,
        "body": {"contentType": "text", "content": body_content if body_content is not None else body_preview},
    }
    if received_utc is not None:
        msg["receivedDateTime"] = received_utc
    if sent_utc is not None:
        msg["sentDateTime"] = sent_utc
    return msg


def _field(obj: Any, name: str) -> Any:
    """Read an attribute or dict key cleanly from a structured return value."""
    if isinstance(obj, dict):
        assert name in obj, f"Expected key {name!r} in {obj!r}"
        return obj[name]
    assert hasattr(obj, name), f"Expected attribute {name!r} on {obj!r}"
    return getattr(obj, name)


def _notes_blob(notes: Any) -> str:
    """Serialize list-of-TimestampedNote or string notes for content verification."""
    if isinstance(notes, str):
        return notes
    return json.dumps(notes, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. DB v2.0 migration preserves legacy rows & persists full task card fields
# ---------------------------------------------------------------------------


def test_db_v2_migration_preserves_legacy_rows_and_persists_task_card_fields(tmp_path: Path) -> None:
    """[正常+边界] 旧版 list_items 升级到 v2.0 不丢行、补齐全部新列与 task_timeline 表，且新任务卡字段与追加留痕跨重启持久化。"""
    db_path = tmp_path / "app.db"

    # Seed a legacy pre-v2.0 SQLite database with ONLY old list_items columns
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_type TEXT NOT NULL,
                project_id INTEGER,
                project_name TEXT DEFAULT '通用待办',
                work_domain TEXT DEFAULT '产品研发',
                title TEXT NOT NULL,
                owner TEXT DEFAULT '本人',
                planned_start_at TEXT DEFAULT '',
                planned_end_at TEXT DEFAULT '',
                actual_start_at TEXT DEFAULT '',
                actual_end_at TEXT DEFAULT '',
                estimated_hours REAL DEFAULT 0.5,
                actual_hours REAL,
                priority TEXT DEFAULT 'P1',
                priority_score REAL DEFAULT 60.0,
                status TEXT DEFAULT 'todo',
                stage TEXT DEFAULT '闪念收集',
                relation_note TEXT DEFAULT '',
                source_ids_json TEXT DEFAULT '[]',
                onedrive_doc_paths_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO list_items (
                list_type, project_name, work_domain, title, owner,
                planned_start_at, planned_end_at, status, created_at, updated_at
            ) VALUES (
                'project_action', '历史项目', '项目交付', '旧线上任务', '本人',
                '2026-11-01', '2026-11-30', 'in_progress',
                '2026-11-01 09:00:00', '2026-11-01 09:00:00'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    # Open with Database -> triggers v2.0 schema migration
    db = Database(db_path)

    # Legacy row MUST be preserved intact
    existing_items = db.list_items(include_done=True)
    legacy_rows = [it for it in existing_items if it["title"] == "旧线上任务"]
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["owner"] == "本人"

    # Verify all required v2.0 columns on list_items and task_timeline table exist
    check_conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in check_conn.execute("PRAGMA table_info(list_items)").fetchall()}
        tables = {
            row[0] for row in check_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        check_conn.close()

    required_v2_cols = {
        "deliverable",
        "assignee",
        "external_partner",
        "milestone_stage",
        "blocker_note",
        "comments",
        "ceo_evaluation",
        "mail_conversation_ids",
    }
    missing_cols = required_v2_cols - cols
    assert not missing_cols, f"Missing v2.0 columns in list_items: {missing_cols}"
    assert "task_timeline" in tables, "Missing task_timeline table after v2.0 migration"

    # Persist a full v2.0 task card via apply_proposal_atomic
    created = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="声波测温前置放大器国产替代 BOM 改版",
                deliverable="产出可采购的国产替代 BOM 清单并完成样机测试通过",
                owner="徐宏玮",
                assignee="李文颖",
                external_partner="无",
                planned_start_at="2026-11-25",
                planned_end_at="",
                milestone_stage="BOM 选型中",
                blocker_note="需核对国产工业级 IC 温漂指标",
                mail_conversation_ids=["conv-001"],
                timeline=[
                    TimelineEntry(
                        timestamp="2026-11-25 09:00",
                        channel="wechat",
                        from_party="徐宏玮",
                        to_party="李文颖",
                        summary="启动国产替代 BOM 筛选",
                        mail_conversation_id="conv-001",
                    )
                ],
                comments=[
                    TimestampedNote(
                        date="2026-11-25",
                        content="排除金属屏蔽盖与外壳，只替换板级高价值进口 IC",
                    )
                ],
                ceo_evaluation=[
                    TimestampedNote(
                        date="2026-11-25",
                        content="核心降本任务，本周内完成首批国产 IC 筛选",
                    )
                ],
                missing_required_fields=["planned_end_at"],
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    new_item_id = created["inserted_item_ids"][0]

    # Conversation ID lookup & timeline readback
    found = db.find_task_by_mail_conversation_id("conv-001")
    assert found is not None
    assert found["id"] == new_item_id
    assert found["title"] == "声波测温前置放大器国产替代 BOM 改版"

    tl = db.get_task_timeline(new_item_id)
    assert len(tl) >= 1
    assert any("启动国产替代 BOM 筛选" in entry["summary"] for entry in tl)

    # Append dated comment & CEO evaluation without overwriting prior entries
    db.append_task_comment(new_item_id, "第二条客观技术约束：工业级耐温需达 -40~85℃")
    db.append_task_ceo_evaluation(new_item_id, "第二条批示：优先验证绿创商城现货供货周期")

    # Re-open Database from disk to prove full persistence across restarts
    db_reopened = Database(db_path)
    reopened_items = {it["id"]: it for it in db_reopened.list_items(include_done=True)}
    assert any(it["title"] == "旧线上任务" for it in reopened_items.values())

    card = reopened_items[new_item_id]
    assert card["deliverable"] == "产出可采购的国产替代 BOM 清单并完成样机测试通过"
    assert card["assignee"] == "李文颖"
    assert card["external_partner"] == "无"
    assert card["planned_end_at"] == ""
    assert card["milestone_stage"] == "BOM 选型中"
    assert card["blocker_note"] == "需核对国产工业级 IC 温漂指标"

    assert isinstance(card["comments"], list) and len(card["comments"]) == 2
    comments_text = _notes_blob(card["comments"])
    assert "排除金属屏蔽盖与外壳" in comments_text
    assert "工业级耐温需达 -40~85℃" in comments_text
    assert all(entry.get("date") for entry in card["comments"])

    assert isinstance(card["ceo_evaluation"], list) and len(card["ceo_evaluation"]) == 2
    eval_text = _notes_blob(card["ceo_evaluation"])
    assert "核心降本任务" in eval_text
    assert "优先验证绿创商城现货供货周期" in eval_text
    assert all(entry.get("date") for entry in card["ceo_evaluation"])

    assert db_reopened.find_task_by_mail_conversation_id("conv-001")["id"] == new_item_id
    reopened_tl = db_reopened.get_task_timeline(new_item_id)
    assert any("启动国产替代 BOM 筛选" in entry["summary"] for entry in reopened_tl)


# ---------------------------------------------------------------------------
# 2. DB apply_proposal_atomic supports task_updates (no duplicates) & undo
# ---------------------------------------------------------------------------


def test_db_apply_proposal_atomic_supports_task_updates_and_undo(tmp_path: Path) -> None:
    """[正常+边界] task_updates 向已有任务追加时间轴与阶段/卡点更新而不新建重复任务，且 undo_last_commit 可干净回滚。"""
    db = Database(tmp_path / "app.db")

    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="亳州电厂项目",
                title="亳州电厂 #2 锅炉号角资料与温度数据对接",
                deliverable="通过 Arnab 确认的 #2 锅炉号角安装参数",
                owner="王楠",
                assignee="王楠",
                external_partner="Arnab(Budi)",
                planned_start_at="2026-11-20",
                planned_end_at="2026-12-01",
                milestone_stage="资料整理中",
                blocker_note="",
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1]

    # Apply task_updates without creating any new task card
    db.apply_proposal_atomic(
        proposal_id=None,
        actions=[],
        task_updates=[
            TaskTimelineUpdate(
                target_task_id=1,
                match_method="conversation_id",
                timeline_entry=TimelineEntry(
                    timestamp="2026-11-25 08:10",
                    channel="mail_in",
                    from_party="王楠",
                    to_party="Arnab",
                    summary="已发送亳州#2号角资料",
                ),
                milestone_stage_update="待客户确认",
                blocker_note_update="等Arnab反馈",
            )
        ],
        source_ids=[],
        doc_paths=[],
    )

    items = db.list_items(include_done=True)
    assert len(items) == 1, "task_updates must NOT create a duplicate task card"
    task1 = items[0]
    assert task1["id"] == 1
    assert task1["milestone_stage"] == "待客户确认"
    assert task1["blocker_note"] == "等Arnab反馈"

    tl_after = db.get_task_timeline(1)
    assert any(
        entry["summary"] == "已发送亳州#2号角资料"
        and entry["channel"] == "mail_in"
        and entry["from_party"] == "王楠"
        and entry["to_party"] == "Arnab"
        for entry in tl_after
    )

    # Undo last commit -> appended timeline entry MUST be cleanly rolled back
    ok, _msg = db.undo_last_commit()
    assert ok is True
    assert len(db.list_items(include_done=True)) == 1
    tl_undone = db.get_task_timeline(1)
    assert not any("已发送亳州#2号角资料" in entry["summary"] for entry in tl_undone)


# ---------------------------------------------------------------------------
# 3. Deterministic critic allows explicit TBD deadline, blocks bad dates
# ---------------------------------------------------------------------------


def test_deterministic_critic_allows_explicit_tbd_deadline_but_blocks_bad_dates() -> None:
    """[正常+禁令] 显式待定截止日期（planned_end_at='' 且在 missing_required_fields）必须放行；非法日期或起止倒挂必须拦截。"""
    tbd_proposal = TriageProposal(
        headline="博州电厂 DCS 点表整理",
        executive_summary="交办王楠整理博州电厂 DCS 点表与逻辑描述，截止日待补齐。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="博州电厂项目",
                title="输出博州电厂 DCS 点表与逻辑描述",
                deliverable="经韩工确认的 DCS 点表与逻辑描述",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="韩工",
                planned_start_at="2026-11-25",
                planned_end_at="",
                missing_required_fields=["planned_end_at"],
            )
        ],
    )
    tbd_issues = deterministic_critic_check(
        tbd_proposal,
        raw_input="让王楠把博州电厂 DCS 点表与逻辑描述整理好，截止时间待定",
        evidence_text="",
        tool_outputs_text="",
    )
    assert tbd_issues == [], f"Explicit TBD deadline should pass critic, got issues: {tbd_issues}"

    invalid_calendar_proposal = TriageProposal(
        headline="非法日期测试",
        executive_summary="测试 2 月 30 日非法截止日期。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="非法日期任务",
                deliverable="测试报告",
                owner="徐宏玮",
                assignee="李文颖",
                planned_start_at="2026-11-25",
                planned_end_at="2026-02-30",
            )
        ],
    )
    invalid_cal_issues = deterministic_critic_check(
        invalid_calendar_proposal,
        raw_input="2026-02-30 交付测试报告",
        evidence_text="",
        tool_outputs_text="",
    )
    assert len(invalid_cal_issues) > 0, "Invalid calendar date 2026-02-30 must be blocked"

    inverted_range_proposal = TriageProposal(
        headline="起止日期倒挂测试",
        executive_summary="测试结束日期早于开始日期。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="日期倒挂任务",
                deliverable="测试报告",
                owner="徐宏玮",
                assignee="李文颖",
                planned_start_at="2026-11-28",
                planned_end_at="2026-11-25",
            )
        ],
    )
    inverted_issues = deterministic_critic_check(
        inverted_range_proposal,
        raw_input="2026-11-28 开始，2026-11-25 结束",
        evidence_text="",
        tool_outputs_text="",
    )
    assert len(inverted_issues) > 0, "End date earlier than start date must be blocked"


# ---------------------------------------------------------------------------
# 4. Mail domain groups loading & legacy compatibility
# ---------------------------------------------------------------------------


def test_mail_domains_loads_internal_and_partner_domains_compatibly(tmp_path: Path) -> None:
    """[正常+边界] load_mail_domain_groups 正确解析 internal_domains/partner_domains，并向后兼容旧版仅含 domains 字段的 JSON。"""
    v2_path = tmp_path / "mail_domains_v2.json"
    v2_path.write_text(
        json.dumps(
            {
                "domains": [
                    "palmarytech.com",
                    "wissentek.com",
                    "budi.de",
                    "vandf.com",
                    "tera-instruments.com",
                ],
                "internal_domains": ["palmarytech.com", "wissentek.com"],
                "partner_domains": ["budi.de", "vandf.com", "tera-instruments.com"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    groups_v2 = mail_poller.load_mail_domain_groups(v2_path)
    assert groups_v2 is not None
    assert tuple(_field(groups_v2, "internal_domains")) == ("palmarytech.com", "wissentek.com")
    assert tuple(_field(groups_v2, "partner_domains")) == ("budi.de", "vandf.com", "tera-instruments.com")
    assert set(_field(groups_v2, "domains")) == {
        "palmarytech.com",
        "wissentek.com",
        "budi.de",
        "vandf.com",
        "tera-instruments.com",
    }

    legacy_path = tmp_path / "mail_domains_legacy.json"
    legacy_path.write_text(json.dumps({"domains": ["vandf.com"]}, ensure_ascii=False), encoding="utf-8")

    groups_legacy = mail_poller.load_mail_domain_groups(legacy_path)
    assert groups_legacy is not None
    assert tuple(_field(groups_legacy, "domains")) == ("vandf.com",)
    assert tuple(_field(groups_legacy, "internal_domains")) == ()


# ---------------------------------------------------------------------------
# 5. From/To/Cc role inference invariants (CC Chairman is NEVER owner/assignee)
# ---------------------------------------------------------------------------


def test_email_role_inference_never_assigns_cc_chairman_as_owner_or_assignee() -> None:
    """[正常+禁令] 依据 From/To/Cc 精准推断董事长角色与责任分工；仅抄送董事长时绝不把董事长填为负责人或实施人。"""
    self_email = "john.xu@palmarytech.com"
    internal = ("palmarytech.com", "wissentek.com")

    # (1) External -> To colleague, Cc Chairman
    msg_ext_to_colleague_cc_ceo = _make_graph_msg(
        msg_id="r-1",
        internet_id="<r-1@budi.de>",
        subject="Bozhou horn drawing feedback",
        sender="Arnab@budi.de",
        to_addrs=["wangnan@wissentek.com"],
        cc_addrs=[self_email],
    )
    hint1 = mail_poller.infer_email_role_hint(
        msg_ext_to_colleague_cc_ceo,
        self_email=self_email,
        internal_domains=internal,
    )
    assert _field(hint1, "chairman_role") == "cc_observer"
    assignee1 = str(_field(hint1, "suggested_assignee"))
    owner1 = str(_field(hint1, "suggested_owner"))
    assert "wangnan" in assignee1.lower()
    for forbidden in ("本人", "徐宏玮"):
        assert forbidden not in owner1, f"CC chairman must not be owner, got {owner1!r}"
        assert forbidden not in assignee1, f"CC chairman must not be assignee, got {assignee1!r}"

    # (2) Colleague -> To External, Cc Chairman
    msg_colleague_to_ext_cc_ceo = _make_graph_msg(
        msg_id="r-2",
        internet_id="<r-2@wissentek.com>",
        subject="Re: Bozhou #2 horn data",
        sender="wangnan@wissentek.com",
        to_addrs=["Arnab@budi.de"],
        cc_addrs=[self_email],
    )
    hint2 = mail_poller.infer_email_role_hint(
        msg_colleague_to_ext_cc_ceo,
        self_email=self_email,
        internal_domains=internal,
    )
    assert _field(hint2, "chairman_role") == "cc_observer"
    assignee2 = str(_field(hint2, "suggested_assignee"))
    owner2 = str(_field(hint2, "suggested_owner"))
    partner2 = str(_field(hint2, "external_partner"))
    assert "wangnan" in assignee2.lower()
    assert "arnab" in partner2.lower()
    for forbidden in ("本人", "徐宏玮"):
        assert forbidden not in owner2, f"CC chairman must not be owner, got {owner2!r}"
        assert forbidden not in assignee2, f"CC chairman must not be assignee, got {assignee2!r}"

    # (3) External -> Direct To Chairman, Cc colleague
    msg_ext_to_ceo = _make_graph_msg(
        msg_id="r-3",
        internet_id="<r-3@budi.de>",
        subject="Xibaipo replacement microphone consolidation",
        sender="Arnab@budi.de",
        to_addrs=[self_email],
        cc_addrs=["wangnan@wissentek.com"],
    )
    hint3 = mail_poller.infer_email_role_hint(
        msg_ext_to_ceo,
        self_email=self_email,
        internal_domains=internal,
    )
    assert _field(hint3, "chairman_role") == "owner"
    assert _field(hint3, "suggested_owner") in ("徐宏玮", "本人")

    # (4) Colleague -> Direct To Chairman (approval / escalation)
    msg_colleague_to_ceo = _make_graph_msg(
        msg_id="r-4",
        internet_id="<r-4@wissentek.com>",
        subject="请示：博州项目报价方案审批",
        sender="wangnan@wissentek.com",
        to_addrs=[self_email],
        cc_addrs=[],
    )
    hint4 = mail_poller.infer_email_role_hint(
        msg_colleague_to_ceo,
        self_email=self_email,
        internal_domains=internal,
    )
    assert _field(hint4, "chairman_role") == "approver"
    assert "wangnan" in str(_field(hint4, "suggested_assignee")).lower()


# ---------------------------------------------------------------------------
# 6. Mail batch prompt carries From/To/Cc, conversationId, role hint & bound task #1
# ---------------------------------------------------------------------------


async def test_mail_batch_prompt_includes_from_to_cc_conversation_id_and_role_hint(tmp_path: Path) -> None:
    """[正常] 邮件批次送入分拣模型时，prompt 必须同时包含 To、Cc、conversationId、角色推断提示及已绑定任务 #1。"""
    settings = _make_settings(tmp_path, mail_user="john.xu@palmarytech.com")
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T00:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T00:00:00Z")

    # Seed existing task #1 bound to conversationId "conv-bozhou-01"
    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="亳州电厂项目",
                title="亳州电厂 #2 锅炉号角资料对接",
                deliverable="经 Budi 确认的 #2 号角技术参数",
                owner="王楠",
                assignee="王楠",
                external_partner="Arnab(Budi)",
                planned_start_at="2026-11-20",
                planned_end_at="2026-12-01",
                mail_conversation_ids=["conv-bozhou-01"],
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1]

    domains_path = tmp_path / "mail_domains.json"
    domains_path.write_text(
        json.dumps(
            {
                "domains": ["palmarytech.com", "wissentek.com", "budi.de"],
                "internal_domains": ["palmarytech.com", "wissentek.com"],
                "partner_domains": ["budi.de"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proposal_json = TriageProposal(
        headline="亳州号角资料同步",
        executive_summary="王楠已向 Arnab 发送亳州 #2 号角资料。",
        actions=[],
        task_updates=[
            TaskTimelineUpdate(
                target_task_id=1,
                target_task_title="亳州电厂 #2 锅炉号角资料对接",
                match_method="conversation_id",
                timeline_entry=TimelineEntry(
                    timestamp="2026-11-25 08:10",
                    channel="mail_in",
                    from_party="王楠",
                    to_party="Arnab",
                    summary="已发送亳州 #2 锅炉号角资料",
                    mail_conversation_id="conv-bozhou-01",
                ),
            )
        ],
    ).model_dump_json()

    def handler(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model in (settings.producer_model, settings.producer_fallback_model):
            return proposal_json
        return json.dumps(
            {"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": []},
            ensure_ascii=False,
        )

    completions = _ScriptedCompletions(handler)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    od = _DummyOneDrive()
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt.db",
    )

    inbox_msgs = [
        _make_graph_msg(
            msg_id="m-bozhou-1",
            internet_id="<bozhou-1@wissentek.com>",
            conversation_id="conv-bozhou-01",
            subject="Re: 亳州 #2 锅炉号角资料",
            sender="wangnan@wissentek.com",
            to_addrs=["Arnab@budi.de"],
            cc_addrs=["john.xu@palmarytech.com"],
            received_utc="2026-11-25T00:10:00Z",
            body_preview="已将亳州 #2 锅炉号角图纸与实测温度数据发出，请查收。",
        )
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 25, 9, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        producer_calls = [
            c for c in completions.calls if c["model"] in (settings.producer_model, settings.producer_fallback_model)
        ]
        assert len(producer_calls) >= 1, "Expected producer model to be called for inbox mail batch"

        prompt_blob = json.dumps(producer_calls[0]["messages"], ensure_ascii=False)
        prompt_lower = prompt_blob.lower()

        assert "arnab@budi.de" in prompt_lower, "Producer prompt must include To recipient address"
        assert "john.xu@palmarytech.com" in prompt_lower, "Producer prompt must include Cc recipient address"
        assert "conv-bozhou-01" in prompt_blob, "Producer prompt must include mail conversationId"
        assert ("抄送" in prompt_blob) or ("cc_observer" in prompt_blob), (
            "Producer prompt must include chairman role hint (抄送 / cc_observer)"
        )
        assert "#1" in prompt_blob, "Producer prompt must include matched existing task hint #1"
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 7. Sent mail auto-appends timeline when conversationId matches (0 LLM calls)
# ---------------------------------------------------------------------------


async def test_sent_mail_auto_appends_timeline_when_conversation_id_matches(tmp_path: Path) -> None:
    """[正常+禁令] 已发送邮件命中已有任务 conversationId 时：0 次大模型调用、不建确认卡、自动追加 mail_out 时间轴、原状态排期不动、微信提示已自动归入 #1。"""
    settings = _make_settings(tmp_path, mail_user="john.xu@palmarytech.com")
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T00:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T00:00:00Z")

    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="西柏坡项目",
                title="西柏坡替换麦克风合箱发运",
                deliverable="替换麦克风随 8 根石英管合箱到货验收",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="Arnab(Budi)",
                planned_start_at="2026-11-25",
                planned_end_at="2026-12-05",
                mail_conversation_ids=["conv-xbp-001"],
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1]
    db.update_item_fields(1, {"status": "in_progress"})

    domains_path = tmp_path / "mail_domains.json"
    domains_path.write_text(
        json.dumps(
            {
                "domains": ["palmarytech.com", "wissentek.com", "budi.de"],
                "internal_domains": ["palmarytech.com", "wissentek.com"],
                "partner_domains": ["budi.de"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fail_if_called(kwargs: dict[str, Any], _idx: int) -> str:
        raise AssertionError(f"LLM must NOT be called for sent mail auto-threading: {kwargs}")

    completions = _ScriptedCompletions(fail_if_called)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    od = _DummyOneDrive()
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt.db",
    )

    sent_msgs = [
        _make_graph_msg(
            msg_id="m-sent-xbp-1",
            internet_id="<sent-xbp-1@palmarytech.com>",
            conversation_id="conv-xbp-001",
            subject="Re: 西柏坡替换麦克风",
            sender="john.xu@palmarytech.com",
            to_addrs=["Arnab@budi.de"],
            sent_utc="2026-11-25T00:35:00Z",
            body_preview="同意随 8 根石英管合箱寄送，请安排发运。",
        )
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return sent_msgs if folder == "sent" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 25, 9, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # Invariant: ZERO LLM calls & ZERO pending confirmation cards
        assert len(completions.calls) == 0
        assert db.get_latest_pending_proposal("owner") is None

        # Timeline automatically appended with channel == "mail_out"
        tl = db.get_task_timeline(1)
        mail_out_entries = [e for e in tl if e.get("channel") == "mail_out"]
        assert len(mail_out_entries) == 1, f"Expected 1 mail_out timeline entry, got {tl}"
        assert "西柏坡替换麦克风" in mail_out_entries[0]["summary"] or (
            mail_out_entries[0].get("mail_conversation_id") == "conv-xbp-001"
        )

        # Task #1 status and planned_end_at MUST remain untouched
        task1 = next(it for it in db.list_items(include_done=True) if it["id"] == 1)
        assert task1["status"] == "in_progress"
        assert task1["planned_end_at"] == "2026-12-05"

        # WeCom push explicitly indicates auto-归入 #1
        assert len(pushes) == 1
        assert "已自动归入 #1" in pushes[0]
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 8. Decision card strips duplicate '确认 #N｜' prefix & renders v2.0 sections
# ---------------------------------------------------------------------------


def test_decision_card_strips_duplicate_confirm_prefix_and_renders_v2_sections() -> None:
    """[正常+边界] 决策确认卡自动去除重复的「确认 #9｜」前缀，并渲染 v2.0 交付成果/分工/已有任务追加/知会与缺失必填提示。"""
    proposal = TriageProposal(
        headline="确认 #9｜西柏坡替换麦克风合箱发运",
        executive_summary="Budi 确认免费补发替换麦克风并建议随 8 根石英管合箱发运。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="西柏坡项目",
                title="西柏坡替换麦克风免费补发与合箱发运",
                deliverable="替换麦克风随8根石英管到货",
                owner="徐宏玮",
                assignee="【待补齐】",
                external_partner="Arnab/Martin(Budi)",
                planned_start_at="2026-11-25",
                planned_end_at="",
                missing_required_fields=["assignee", "planned_end_at"],
                timeline=[
                    TimelineEntry(
                        timestamp="2026-11-24 22:15",
                        channel="mail_in",
                        from_party="Arnab",
                        to_party="徐宏玮",
                        summary="确认免费补发替换麦克风并询问合箱意见",
                    )
                ],
            )
        ],
        task_updates=[
            TaskTimelineUpdate(
                target_task_id=1,
                target_task_title="博州/亳州电厂声波测温对接",
                match_method="conversation_id",
                timeline_entry=TimelineEntry(
                    timestamp="2026-11-25 08:10",
                    channel="mail_in",
                    from_party="王楠",
                    to_party="Arnab",
                    summary="已发送亳州#2号角资料及实测温度数据",
                ),
            )
        ],
        fyi_notices=[
            FyiNotice(
                timestamp="2026-11-25 08:20",
                from_party="李文颖",
                to_party="供应链",
                summary="已同步前置放大器国产 IC 询价进展",
            )
        ],
    )

    card = format_decision_card(9, proposal)

    # Deduplicated confirm prefix invariant
    assert "确认 #9｜确认 #9" not in card
    assert "确认 #9｜西柏坡替换麦克风合箱发运" in card

    # v2.0 core sections & fields
    assert "目标与交付成果" in card
    assert "替换麦克风随8根石英管到货" in card
    assert "负责人" in card and "徐宏玮" in card
    assert "实施人" in card and "【待补齐】" in card
    assert "外部协作" in card and "Arnab/Martin(Budi)" in card

    # Existing task timeline append section (#1)
    assert ("归入" in card) or ("#1" in card)
    assert "#1" in card
    assert "已发送亳州#2号角资料" in card

    # Pure FYI notice section
    assert ("知会" in card) or ("同步" in card)
    assert "已同步前置放大器国产 IC 询价进展" in card

    # Missing required fields warning
    assert "缺失必填" in card


# ---------------------------------------------------------------------------
# 9. WeChat deterministic shortcuts (0 LLM calls even when router is down 503)
# ---------------------------------------------------------------------------


def test_wechat_shortcuts_append_ceo_evaluation_comment_progress_and_view_timeline(tmp_path: Path) -> None:
    """[正常+禁令] 路由模型 503 宕机时，微信快捷口令（评价/备注/进展/查沟通记录）仍 0 模型调用准确分流落库与查询。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")

    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="博州电厂项目",
                title="博州电厂声波测温 DCS 点表与逻辑对接",
                deliverable="经韩工确认的 DCS 点表与逻辑描述",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="韩工",
                planned_start_at="2026-11-18",
                planned_end_at="",
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1]

    # Simulate router & all LLM endpoints returning 503 outage
    def broken_llm(kwargs: dict[str, Any], _idx: int) -> str:
        raise RuntimeError("503")

    completions = _ScriptedCompletions(broken_llm)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        checkpoints_path=tmp_path / "ckpt.db",
    )

    try:
        # 1) CEO Evaluation -> writes ONLY to ceo_evaluation, NEVER comments
        res_eval = engine.handle_incoming_turn(
            "评价 #1：王楠推进偏慢，本周必须发出点表",
            external_msg_id="shortcut_eval_1",
        )
        assert res_eval["reply_text"]
        task1 = next(it for it in db.list_items(include_done=True) if it["id"] == 1)
        assert "王楠推进偏慢，本周必须发出点表" in _notes_blob(task1["ceo_evaluation"])
        assert "王楠推进偏慢，本周必须发出点表" not in _notes_blob(task1["comments"])

        # 2) Objective Comment -> writes ONLY to comments, NEVER ceo_evaluation
        res_cmt = engine.handle_incoming_turn(
            "备注 #1：现场同意简化为点表+逻辑描述",
            external_msg_id="shortcut_cmt_1",
        )
        assert res_cmt["reply_text"]
        task1 = next(it for it in db.list_items(include_done=True) if it["id"] == 1)
        assert "现场同意简化为点表+逻辑描述" in _notes_blob(task1["comments"])
        assert "现场同意简化为点表+逻辑描述" not in _notes_blob(task1["ceo_evaluation"])

        # 3) Progress -> appends to task_timeline with channel == "wechat"
        res_prog = engine.handle_incoming_turn(
            "#1 进展：已发点表给韩工等签字",
            external_msg_id="shortcut_prog_1",
        )
        assert res_prog["reply_text"]
        tl = db.get_task_timeline(1)
        assert any(
            entry["channel"] == "wechat" and "已发点表给韩工等签字" in entry["summary"]
            for entry in tl
        ), f"Expected wechat timeline entry for #1, got {tl}"

        # 4) View timeline -> returns the logged progress text
        res_view = engine.handle_incoming_turn(
            "查 #1 沟通记录",
            external_msg_id="shortcut_view_1",
        )
        assert "已发点表给韩工等签字" in res_view["reply_text"]

        # Invariant: ZERO LLM calls across all 4 shortcuts
        assert len(completions.calls) == 0
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 10. Morning Digest v2.0 renders flat 1~7 task cards without repetition
# ---------------------------------------------------------------------------


def test_morning_digest_v2_renders_flat_task_cards_without_repetition(tmp_path: Path) -> None:
    """[正常+边界] 早间工作报告 v2.0 输出扁平单层 1)~7) 标准任务卡、不出现复读段落，且无备注/无评价任务自动隐藏 6)/7)。"""
    db = Database(tmp_path / "app.db")

    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="博州电厂项目",
                title="博州电厂声波测温 DCS 点表与逻辑对接",
                deliverable="输出并通过韩工/电厂确认的 DCS 对接资料（点表 + 逻辑描述）",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="韩工",
                planned_start_at="2026-11-18",
                planned_end_at="",
                milestone_stage="范围已收口，待发图确认",
                blocker_note="需锁定最终提交电厂的截止日期",
                timeline=[
                    TimelineEntry(
                        timestamp="2026-11-18 14:00",
                        channel="wechat",
                        from_party="徐宏玮",
                        to_party="王楠",
                        summary="明确 DCS 交付物简化为点表+逻辑描述",
                    ),
                    TimelineEntry(
                        timestamp="2026-11-25 08:10",
                        channel="mail_in",
                        from_party="王楠",
                        to_party="韩工",
                        summary="已发送第一版点表草稿待确认",
                    ),
                ],
                comments=[
                    TimestampedNote(
                        date="2026-11-18",
                        content="现场沟通同意先不交完整组态包，以简化版点表+逻辑描述为准",
                    )
                ],
                ceo_evaluation=[
                    TimestampedNote(
                        date="2026-11-25",
                        content="博州项目是标杆交付，本周内把点表发给韩工锁接口",
                    )
                ],
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="声波测温前置放大器国产替代 BOM 改版",
                deliverable="产出可采购的国产替代 BOM 清单并完成样机测试通过",
                owner="徐宏玮",
                assignee="李文颖",
                external_partner="无",
                planned_start_at="2026-11-24",
                planned_end_at="2026-12-10",
                milestone_stage="BOM 选型中",
                blocker_note="",
                comments=[],
                ceo_evaluation=[],
            ),
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1, 2]

    msg = build_daily_digest_message(
        db.dashboard_overview(),
        "🌅 早间工作报告",
        "https://assistant.fire-matrix.com/",
    )

    # Task #1 full 1)~7) flat card elements
    assert "【任务 #1】" in msg
    assert "1）目标与交付成果" in msg
    assert "2）当前进度与往来沟通" in msg
    assert "3）责任分工" in msg
    assert "负责人" in msg and "实施人" in msg and "外部协作" in msg
    assert "王楠" in msg and "韩工" in msg
    assert "4）时间排期" in msg and "【待补齐】" in msg
    assert "5）卡点与关联档案" in msg
    assert "6）补充备注" in msg
    assert "7）CEO 评价" in msg

    # Zero-repetition invariant: must NOT contain redundant "今日/下一步动作" section
    assert "今日/下一步动作" not in msg

    # Task #2 has neither comments nor ceo_evaluation -> hide empty 6) & 7) in its block
    assert "【任务 #2】" in msg
    after_task2 = msg.split("【任务 #2】", 1)[1]
    # Stop before the footer hint line (e.g., "👉") if present
    task2_block = after_task2.split("👉", 1)[0]
    assert "6）补充备注" not in task2_block, f"Empty comments section leaked in Task #2 block:\n{task2_block}"
    assert "7）CEO 评价" not in task2_block, f"Empty CEO evaluation section leaked in Task #2 block:\n{task2_block}"


# ---------------------------------------------------------------------------
# 11. Web API v2.0: task card fields, notes (eval/comment/progress), timeline, overview
# ---------------------------------------------------------------------------


def test_web_api_supports_v2_task_card_fields_notes_and_timeline(tmp_path: Path) -> None:
    """[正常] Web API 支持 v2.0 建卡字段、POST /api/items/{id}/note（评价/备注/进展）、GET timeline 及 overview 透出全量字段。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _DummyOneDrive()
    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(lambda *_: "{}"))),
    )
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od, checkpoints_path=tmp_path / "ckpt.db")
    app = create_app(settings=settings, db=db, engine=eng, onedrive=od, start_background_tasks=False)

    try:
        with TestClient(app) as client:
            # Authenticate via single-use magic link
            tok = app.state.auth.mint_magic_token(300)
            login_resp = client.get(f"/auth/magic?token={tok}", follow_redirects=False)
            assert login_resp.status_code == 302

            # Create v2.0 task card via POST /api/items
            res_create = client.post(
                "/api/items",
                json={
                    "title": "声波测温前置放大器国产替代 BOM 改版",
                    "list_type": "project_action",
                    "work_domain": "产品研发",
                    "project_name": "声波测温研发",
                    "deliverable": "产出可采购的国产替代 BOM 清单并完成样机测试通过",
                    "owner": "徐宏玮",
                    "assignee": "李文颖",
                    "external_partner": "无",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "",
                    "priority": "P1",
                },
            )
            assert res_create.status_code == 200, res_create.text
            item_id = res_create.json()["created_ids"][0]

            # Append CEO evaluation, comment, and progress via POST /api/items/{id}/note
            res_eval = client.post(
                f"/api/items/{item_id}/note",
                json={"kind": "ceo_evaluation", "content": "研发重点，本周给出首批备选 IC"},
            )
            assert res_eval.status_code == 200, res_eval.text

            res_cmt = client.post(
                f"/api/items/{item_id}/note",
                json={"kind": "comment", "content": "排除金属屏蔽盖，只替换板级高价值进口 IC"},
            )
            assert res_cmt.status_code == 200, res_cmt.text

            res_prog = client.post(
                f"/api/items/{item_id}/note",
                json={"kind": "progress", "content": "已完成绿创商城第一批国产器件参数核对"},
            )
            assert res_prog.status_code == 200, res_prog.text

            # Query timeline via GET /api/items/{id}/timeline
            res_tl = client.get(f"/api/items/{item_id}/timeline")
            assert res_tl.status_code == 200, res_tl.text
            tl_payload = res_tl.json()
            tl_entries = tl_payload["timeline"] if isinstance(tl_payload, dict) else tl_payload
            assert isinstance(tl_entries, list)
            assert any("已完成绿创商城第一批国产器件参数核对" in json.dumps(e, ensure_ascii=False) for e in tl_entries)

            # Verify GET /api/dashboard/overview exposes all v2.0 fields
            res_ov = client.get("/api/dashboard/overview")
            assert res_ov.status_code == 200, res_ov.text
            items = res_ov.json()["items"]
            card = next(it for it in items if it["id"] == item_id)

            assert card["deliverable"] == "产出可采购的国产替代 BOM 清单并完成样机测试通过"
            assert card["assignee"] == "李文颖"
            assert card["external_partner"] == "无"
            assert card["planned_end_at"] == ""
            assert "排除金属屏蔽盖，只替换板级高价值进口 IC" in _notes_blob(card["comments"])
            assert "研发重点，本周给出首批备选 IC" in _notes_blob(card["ceo_evaluation"])
            assert "已完成绿创商城第一批国产器件参数核对" in json.dumps(card["timeline"], ensure_ascii=False)
    finally:
        eng.close()
