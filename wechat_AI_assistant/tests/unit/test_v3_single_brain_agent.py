"""Independent black-box contract tests for v3.0 Single-Brain Flagship Agent (Plan A, RED phase).

Strictly derived from Red-Zone contracts & debug specs:
- `src/wechat_assistant/schemas.py`: `AgentDecision`, `TaskFieldUpdate`, `TaskNoteAppend`,
  `TaskStatusChange`, `TriageProposal`, `ActionMutation`
- `debug_records/01-2026-11-25-五彩湾DCS任务修改截止日被清空与啰嗦故障复盘.md`
- `debug_records/03-v3.0大模型优先架构重构方案.md`

Covers all 7 core black-box acceptance scenarios:
1. Single-brain invariant: 0 calls to `fast_model` / `critic_model`, only `producer_model`,
   with deterministic calendar anchor table (yesterday / today + weekday / this Friday).
2. Wucaiwan 2-turn real conversation: yesterday preserved without false rejection, and
   2nd turn ("暂定本周五，之后可以确认落盘了") commits in 1 step without extra "1".
3. Objective guard precision: WeChat delegation never blocked by Outlook-only `cc_observer`,
   valid ISO dates in `referenced_numbers` never flagged as fabrication, while Outlook CC
   with `[SYSTEM_TRUSTED_MAIL_META]` still strictly blocks owner/assignee assigned to Chairman.
4. Compound direct_ops in a single natural-language turn (update #1 deadline + append #2
   CEO evaluation + complete #3) with 0 calls to `fast_model` / `critic_model`.
5. Concise single-task decision card hides redundant `executive_summary` and filters system
   citation noise, while preserving real document page citations.
6. Objective safety floor invariant: `confirm_and_commit=True` with invalid calendar date or
   inverted start/end dates MUST be blocked and NEVER persisted to DB.
7. Emergency offline buttons (`1`, `0`, `撤销`, `看板`) succeed with 0 LLM calls even when
   all flagship & fallback LLMs return 503.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine, format_decision_card
from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.schemas import (
    ActionMutation,
    AgentDecision,
    IntentRoute,
    ListType,
    PriorityLevel,
    TaskFieldUpdate,
    TaskNoteAppend,
    TaskStatusChange,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage.db import Database

SHANGHAI = ZoneInfo("Asia/Shanghai")
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


# ---------------------------------------------------------------------------
# Deterministic stubs & calendar helpers (zero network, zero real LLM calls)
# ---------------------------------------------------------------------------


class _DummyOneDrive:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}

    def upload_bytes(self, remote_path: str, data: bytes, *, content_type: str = "") -> dict[str, Any]:
        self.uploads[remote_path] = data
        return {
            "id": f"id_{len(self.uploads)}",
            "webUrl": f"https://wissentek.sharepoint.cn/mock/{remote_path}",
            "size": len(data),
        }

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        return {}

    def append_project_note(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


class _ScriptedCompletions:
    """Fake OpenAI chat completions recording every call (model + messages + kwargs)."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=60, completion_tokens=50, completion_tokens_details=None),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content, tool_calls=None, reasoning_content="")
                )
            ],
        )


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        dashscope_api_key="sk-fakeunit1234567890abcdef",
        web_access_secret="unit-test-hmac-secret-key-1234567890",
        data_dir=str(tmp_path / "data"),
        wecom_corp_id="wwtestcorp",
        wecom_app_agent_id="1000002",
        wecom_app_token="tokentest123456",
        wecom_app_aes_key="A" * 43,
    )


def _make_engine(
    tmp_path: Path,
    handler,
    *,
    db: Database | None = None,
    magic_link_factory=None,
) -> tuple[ChiefOfStaffEngine, Database, Settings, _ScriptedCompletions]:
    settings = _make_settings(tmp_path)
    database = db or Database(tmp_path / "app.db")
    completions = _ScriptedCompletions(handler)
    gateway = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=database,
        gateway=gateway,
        onedrive=_DummyOneDrive(),
        checkpoints_path=tmp_path / "ckpt.db",
        magic_link_factory=magic_link_factory,
    )
    return engine, database, settings, completions


def _shanghai_calendar_dates() -> tuple[date, date, date, str]:
    """Return (yesterday, today, this_friday, today_weekday_char) in Asia/Shanghai."""
    today = datetime.now(SHANGHAI).date()
    yesterday = today - timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    this_friday = monday + timedelta(days=4)
    return yesterday, today, this_friday, WEEKDAY_CN[today.weekday()]


def _notes_blob(notes: Any) -> str:
    if isinstance(notes, str):
        return notes
    return json.dumps(notes, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. Single-brain invariant: 0 fast/critic LLM calls + calendar anchor table
# ---------------------------------------------------------------------------


def test_v3_single_brain_never_calls_fast_router_or_critic_llm(tmp_path: Path) -> None:
    """[禁令+正常] 微信普通交办 0 次调用 fast_model/critic_model，仅调用 producer_model 且注入确定性日历锚点表。"""
    yesterday, today, this_friday, weekday_char = _shanghai_calendar_dates()
    yesterday_str = yesterday.isoformat()
    today_str = today.isoformat()
    this_friday_str = this_friday.isoformat()

    decision = AgentDecision(
        mode="propose",
        proposal=TriageProposal(
            headline="联系五彩湾电厂提供DCS文件",
            executive_summary="杨丽丽联系中电投五彩湾电厂提供DCS文件，截止日待定。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="五彩湾电厂项目",
                    title="联系中电投五彩湾电厂提供DCS文件",
                    deliverable="获取五彩湾电厂DCS点表与逻辑文件",
                    owner="徐宏玮",
                    assignee="杨丽丽",
                    external_partner="中电投五彩湾电厂",
                    chairman_role="owner",
                    planned_start_at=yesterday_str,
                    planned_end_at="",
                    missing_required_fields=["planned_end_at"],
                )
            ],
            referenced_numbers=[yesterday_str],
        ),
    )

    def scripted(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return IntentRoute(
                intent="work_triage",
                confidence=0.95,
                summary="五彩湾电厂DCS文件任务",
            ).model_dump_json()
        if model == "deepseek-v4-pro":
            return json.dumps(
                {
                    "passed": True,
                    "numeric_fidelity_ok": True,
                    "schedule_reasonable": True,
                    "issues": [],
                    "fix_instructions": "",
                }
            )
        return decision.model_dump_json()

    engine, _db, settings, completions = _make_engine(tmp_path, scripted)
    try:
        res = engine.handle_incoming_turn(
            "杨丽丽在联系中电投五彩湾电厂提供DCS文件，昨天开始联系的，还不知道什么时候回复",
            external_msg_id="v3_single_brain_1",
        )
        assert res["reply_text"]

        called_models = [c["model"] for c in completions.calls]
        producer_calls = [c for c in completions.calls if c["model"] == settings.producer_model]

        assert settings.fast_model not in called_models, (
            f"v3.0 MUST NOT call fast_model ({settings.fast_model}), called={called_models}"
        )
        assert settings.critic_model not in called_models, (
            f"v3.0 MUST NOT call critic_model ({settings.critic_model}), called={called_models}"
        )
        assert len(producer_calls) >= 1, f"Expected flagship producer_model ({settings.producer_model}) to be called"
        assert set(called_models) == {settings.producer_model}, (
            f"Only producer_model should be invoked, got {called_models}"
        )

        # Deterministic calendar anchor table MUST be injected into the flagship prompt
        prompt_blob = json.dumps(producer_calls[0]["messages"], ensure_ascii=False)
        assert yesterday_str in prompt_blob, f"Calendar anchor must include yesterday ({yesterday_str})"
        assert today_str in prompt_blob, f"Calendar anchor must include today ({today_str})"
        assert any(w in prompt_blob for w in (f"周{weekday_char}", f"星期{weekday_char}")), (
            f"Calendar anchor must include today's weekday (周{weekday_char}/星期{weekday_char})"
        )
        assert this_friday_str in prompt_blob, f"Calendar anchor must include this Friday ({this_friday_str})"
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 2. Wucaiwan 2-turn real conversation: yesterday preserved + 1-step commit
# ---------------------------------------------------------------------------


def test_v3_wucaiwan_two_turn_yesterday_and_one_step_revise_commit(tmp_path: Path) -> None:
    """[正常+边界] 复现五彩湾2轮真实对话：第1轮保留昨日开始日1轮直出待确认卡；第2轮补本周五并一步确认落盘。"""
    yesterday, _today, this_friday, _weekday_char = _shanghai_calendar_dates()
    yesterday_str = yesterday.isoformat()
    # Guard against weekend clock runs where this_friday < yesterday; on Mon-Sat target_end == this_friday
    target_end_str = (this_friday if this_friday >= yesterday else this_friday + timedelta(days=7)).isoformat()

    turn1_decision = AgentDecision(
        mode="propose",
        confirm_and_commit=False,
        proposal=TriageProposal(
            headline="获取五彩湾电厂DCS文件",
            executive_summary="杨丽丽跟进中电投五彩湾电厂提供DCS文件。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="五彩湾电厂项目",
                    title="联系中电投五彩湾电厂提供DCS文件",
                    deliverable="获取用于燃烧优化更新的DCS点表与逻辑文件",
                    owner="徐宏玮",
                    assignee="杨丽丽",
                    external_partner="中电投新疆能源化工集团五彩湾发电有限责任公司",
                    chairman_role="owner",
                    planned_start_at=yesterday_str,
                    planned_end_at="",
                    missing_required_fields=["planned_end_at"],
                )
            ],
            referenced_numbers=[yesterday_str],
        ),
    )

    turn2_decision = AgentDecision(
        mode="propose",
        confirm_and_commit=True,
        proposal=TriageProposal(
            headline="获取五彩湾电厂DCS文件",
            executive_summary="补齐目标截止时间并确认落盘。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="五彩湾电厂项目",
                    title="联系中电投五彩湾电厂提供DCS文件",
                    deliverable="获取用于燃烧优化更新的DCS点表与逻辑文件",
                    owner="徐宏玮",
                    assignee="杨丽丽",
                    external_partner="中电投新疆能源化工集团五彩湾发电有限责任公司",
                    chairman_role="owner",
                    planned_start_at=yesterday_str,
                    planned_end_at=target_end_str,
                    missing_required_fields=[],
                )
            ],
            referenced_numbers=[yesterday_str, target_end_str],
        ),
    )

    producer_turn = {"count": 0}

    def scripted(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return IntentRoute(
                intent="work_triage" if producer_turn["count"] == 0 else "revise_pending",
                confidence=0.95,
                summary="五彩湾任务",
            ).model_dump_json()
        if model == "deepseek-v4-pro":
            return json.dumps(
                {
                    "passed": True,
                    "numeric_fidelity_ok": True,
                    "schedule_reasonable": True,
                    "issues": [],
                    "fix_instructions": "",
                }
            )
        producer_turn["count"] += 1
        if producer_turn["count"] == 1:
            return turn1_decision.model_dump_json()
        return turn2_decision.model_dump_json()

    engine, db, settings, completions = _make_engine(tmp_path, scripted)
    try:
        # Turn 1: Create proposal with yesterday start date & TBD deadline
        r1 = engine.handle_incoming_turn(
            "杨丽丽在联系中电投新疆能源化工集团五彩湾发电有限责任公司提供DCS文件，昨天开始联系的，还不知道什么时候回复",
            external_msg_id="v3_wcw_turn_1",
        )
        t1_reply = r1["reply_text"]

        # Must complete in a single flagship call (zero retries, zero fast/critic calls)
        assert [c["model"] for c in completions.calls] == [settings.producer_model], (
            f"Turn 1 must make exactly 1 producer call with no retry/fast/critic, got {[c['model'] for c in completions.calls]}"
        )
        assert f"开始 {yesterday_str}" in t1_reply, f"Card must display '开始 {yesterday_str}':\n{t1_reply}"
        assert "负责人：徐宏玮" in t1_reply, f"Card must display '负责人：徐宏玮':\n{t1_reply}"
        assert "实施人：杨丽丽" in t1_reply, f"Card must display '实施人：杨丽丽':\n{t1_reply}"
        assert db.get_latest_pending_proposal("owner") is not None
        assert db.list_items(include_done=True) == []

        # Turn 2: Revise deadline to this Friday AND confirm_and_commit in one step
        r2 = engine.handle_incoming_turn(
            "目标截止时间可以暂定本周五，之后可以确认落盘了",
            external_msg_id="v3_wcw_turn_2",
        )
        assert r2["reply_text"]
        assert [c["model"] for c in completions.calls] == [settings.producer_model, settings.producer_model], (
            f"Two turns must invoke producer_model twice total (0 fast/critic), got {[c['model'] for c in completions.calls]}"
        )

        # Immediately persisted without requiring a separate "1" reply
        items = db.list_items(include_done=True)
        assert len(items) == 1, f"Expected 1 committed item after 1-step revise+commit, got {items}"
        saved = items[0]
        assert saved["planned_start_at"] == yesterday_str
        assert saved["planned_end_at"] == target_end_str
        assert saved["owner"] == "徐宏玮"
        assert saved["assignee"] == "杨丽丽"
        assert db.get_latest_pending_proposal("owner") is None, "Pending proposal must be cleared after 1-step commit"
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 3. Objective guard: WeChat delegation & ISO dates pass; Outlook CC blocked
# ---------------------------------------------------------------------------


def test_v3_wechat_delegation_never_blocked_by_cc_observer_while_outlook_cc_is_blocked() -> None:
    """[边界+禁令] 微信交办不被邮件专属 cc_observer 误杀、合法相对推算 ISO 日期不被判编造；Outlook 抄送依然硬拦截。"""
    # Part A: WeChat delegation (NO [SYSTEM_TRUSTED_MAIL_META]) even if model mistakenly sets cc_observer
    wechat_proposal = TriageProposal(
        headline="联系五彩湾电厂提供DCS文件",
        executive_summary="杨丽丽跟进五彩湾电厂DCS文件。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="五彩湾电厂项目",
                title="联系中电投五彩湾电厂提供DCS文件",
                deliverable="获取五彩湾电厂DCS点表与逻辑文件",
                owner="徐宏玮",
                assignee="杨丽丽",
                chairman_role="cc_observer",
                planned_start_at="2026-11-24",
                planned_end_at="2026-11-27",
            )
        ],
        referenced_numbers=["2026-11-24", "2026-11-27"],
    )
    wechat_issues = deterministic_critic_check(
        wechat_proposal,
        raw_input="杨丽丽在联系五彩湾电厂提供DCS文件，昨天开始联系的，目标截止时间暂定本周五",
        evidence_text="",
        tool_outputs_text="",
    )
    assert wechat_issues == [], (
        f"WeChat delegation & valid ISO dates in referenced_numbers must NOT be blocked, got: {wechat_issues}"
    )

    # Part B: Outlook CC mail WITH [SYSTEM_TRUSTED_MAIL_META] & chairman_role=cc_observer MUST still block
    outlook_cc_raw = (
        "[SYSTEM_TRUSTED_MAIL_META]\n"
        "chairman_role=cc_observer | suggested_owner=王楠 | suggested_assignee=王楠\n"
        "[/SYSTEM_TRUSTED_MAIL_META]\n"
        "[UNTRUSTED_EXTERNAL_DATA]\n"
        "From: Arnab@budi.de\n"
        "To: wangnan@wissentek.com\n"
        "Cc: john.xu@palmarytech.com\n"
        "Subject: Bozhou DCS table\n"
        "Please send the updated DCS table by 2026-11-27.\n"
        "[/UNTRUSTED_EXTERNAL_DATA]"
    )

    def _outlook_proposal(*, owner: str, assignee: str) -> TriageProposal:
        return TriageProposal(
            headline="亳州电厂 DCS 点表发送",
            executive_summary="Arnab 催王楠发送点表，董事长仅抄送。",
            actions=[
                ActionMutation(
                    list_type=ListType.WAITING_FOR,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="亳州电厂项目",
                    title="向 Arnab 发送更新版 DCS 点表",
                    deliverable="发送更新版 DCS 点表给 Arnab",
                    owner=owner,
                    assignee=assignee,
                    external_partner="Arnab",
                    chairman_role="cc_observer",
                    source_channel="outlook",
                    planned_start_at="2026-11-25",
                    planned_end_at="2026-11-27",
                )
            ],
        )

    issues_bad_owner = deterministic_critic_check(
        _outlook_proposal(owner="本人", assignee="王楠"),
        raw_input=outlook_cc_raw,
        evidence_text="",
        tool_outputs_text="",
    )
    assert len(issues_bad_owner) > 0, "Outlook CC mail with owner='本人' MUST be blocked"

    issues_bad_assignee = deterministic_critic_check(
        _outlook_proposal(owner="王楠", assignee="徐宏玮"),
        raw_input=outlook_cc_raw,
        evidence_text="",
        tool_outputs_text="",
    )
    assert len(issues_bad_assignee) > 0, "Outlook CC mail with assignee='徐宏玮' MUST be blocked"

    issues_valid_colleague = deterministic_critic_check(
        _outlook_proposal(owner="王楠", assignee="王楠"),
        raw_input=outlook_cc_raw,
        evidence_text="",
        tool_outputs_text="",
    )
    assert issues_valid_colleague == [], (
        f"Outlook CC mail assigned to colleague should pass, got: {issues_valid_colleague}"
    )


# ---------------------------------------------------------------------------
# 4. Compound direct_ops executed in a single natural-language turn
# ---------------------------------------------------------------------------


def test_v3_compound_direct_ops_in_single_natural_turn(tmp_path: Path) -> None:
    """[正常+边界] 单句复合自然语言同时执行改 #1 截止日 + 追加 #2 CEO评价 + #3 标完成，0 次 fast/critic 调用。"""
    db = Database(tmp_path / "app.db")
    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="五彩湾电厂项目",
                title="联系中电投五彩湾电厂提供DCS文件",
                deliverable="DCS点表与逻辑文件",
                owner="徐宏玮",
                assignee="杨丽丽",
                planned_start_at="2026-11-24",
                planned_end_at="",
                missing_required_fields=["planned_end_at"],
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="前置放大器国产替代 BOM 改版",
                deliverable="国产替代 BOM 清单",
                owner="徐宏玮",
                assignee="李文颖",
                planned_start_at="2026-11-20",
                planned_end_at="2026-12-10",
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="西柏坡项目",
                title="西柏坡替换麦克风合箱发运",
                deliverable="麦克风到货验收",
                owner="徐宏玮",
                assignee="王楠",
                planned_start_at="2026-11-18",
                planned_end_at="2026-11-30",
            ),
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert seed["inserted_item_ids"] == [1, 2, 3]
    db.update_item_fields(2, {"status": "in_progress"})
    db.update_item_fields(3, {"status": "in_progress"})

    compound_decision = AgentDecision(
        mode="direct_ops",
        field_updates=[TaskFieldUpdate(task_id=1, planned_end_at="2026-12-05")],
        note_appends=[TaskNoteAppend(task_id=2, kind="ceo_evaluation", content="进度太慢")],
        status_changes=[TaskStatusChange(task_id=3, action="complete")],
    )

    def scripted(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return IntentRoute(
                intent="update_item_fields",
                confidence=0.9,
                target_item_id=1,
                summary="复合修改",
            ).model_dump_json()
        return compound_decision.model_dump_json()

    engine, db, settings, completions = _make_engine(tmp_path, scripted, db=db)
    try:
        res = engine.handle_incoming_turn(
            "把五彩湾那个任务的截止日期改成 2026-12-05，顺便给 #2 加个评价说进度太慢，另外 #3 已经做完了",
            external_msg_id="v3_compound_ops_1",
        )
        reply = res["reply_text"]

        # Single-brain invariant: 0 fast_model / critic_model calls
        called_models = [c["model"] for c in completions.calls]
        assert settings.fast_model not in called_models, f"v3.0 MUST NOT call fast_model, got {called_models}"
        assert settings.critic_model not in called_models, f"v3.0 MUST NOT call critic_model, got {called_models}"
        assert settings.producer_model in called_models, f"Expected producer_model call, got {called_models}"

        # All 3 operations persisted atomically in a single turn
        items = {it["id"]: it for it in db.list_items(include_done=True)}
        assert items[1]["planned_end_at"] == "2026-12-05"
        assert "进度太慢" in _notes_blob(items[2]["ceo_evaluation"])
        assert "进度太慢" not in _notes_blob(items[2]["comments"])
        assert items[3]["status"] == "done"

        # Reply text summarizes all 3 mutations clearly
        assert "#1" in reply and "2026-12-05" in reply, f"Reply should mention #1 deadline update:\n{reply}"
        assert "#2" in reply and ("评价" in reply or "进度太慢" in reply), (
            f"Reply should mention #2 CEO evaluation:\n{reply}"
        )
        assert "#3" in reply and ("完成" in reply or "done" in reply.lower()), (
            f"Reply should mention #3 completion:\n{reply}"
        )
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 5. Concise single-task card hides redundant summary & filters citation noise
# ---------------------------------------------------------------------------


def test_v3_concise_single_task_card_hides_redundant_summary_and_system_citation_noise() -> None:
    """[正常+边界] 单任务确认卡隐藏冗余 executive_summary、过滤系统噪点出处，但保留真实文档页码出处。"""
    noisy_proposal = TriageProposal(
        headline="联系五彩湾电厂提供DCS文件",
        executive_summary="根据董事长微信交办及审计打回整改要求，新建独立任务卡，明确责任分工并追踪DCS文件交付。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="五彩湾电厂项目",
                title="联系中电投五彩湾电厂提供DCS文件",
                deliverable="获取用于燃烧优化更新的DCS点表与逻辑文件",
                owner="徐宏玮",
                assignee="杨丽丽",
                external_partner="中电投五彩湾电厂",
                planned_start_at="2026-11-24",
                planned_end_at="",
                missing_required_fields=["planned_end_at"],
            )
        ],
        citations=[
            "用户输入微信消息[11-25 12:05]",
            "审计打回整改要求",
            "check_workload_and_schedule工具输出（每日0项）",
        ],
    )

    card_noisy = format_decision_card(1, noisy_proposal)
    assert "根据董事长微信交办" not in card_noisy, (
        f"Single-task card must hide redundant executive_summary:\n{card_noisy}"
    )
    assert "用户输入微信消息" not in card_noisy
    assert "审计打回整改要求" not in card_noisy
    assert "check_workload_and_schedule" not in card_noisy
    assert "📎 证据出处" not in card_noisy, (
        f"When all citations are system noise, '📎 证据出处' section must be omitted:\n{card_noisy}"
    )

    # Real document page citation MUST be preserved
    doc_proposal = noisy_proposal.model_copy(
        update={
            "citations": [
                "用户输入微信消息[11-25 12:05]",
                "Calibration_Spec.pdf 第 4 页",
            ]
        }
    )
    card_doc = format_decision_card(2, doc_proposal)
    assert "📎 证据出处：Calibration_Spec.pdf 第 4 页" in card_doc, (
        f"Real document citation must be preserved cleanly:\n{card_doc}"
    )
    assert "用户输入微信消息" not in card_doc


# ---------------------------------------------------------------------------
# 6. Safety floor: confirm_and_commit blocked when objective guard fails
# ---------------------------------------------------------------------------


def test_v3_confirm_and_commit_blocked_when_objective_guard_fails(tmp_path: Path) -> None:
    """[禁令] 即使模型返回 confirm_and_commit=True，只要客观日期护栏失败（2月30日或结束早于开始），绝不允许带错落盘。"""
    bad_cases = [
        ("invalid_feb30", "2026-11-24", "2026-02-30"),
        ("inverted_range", "2026-12-10", "2026-11-25"),
    ]

    for case_name, start_date, end_date in bad_cases:
        case_dir = tmp_path / case_name
        case_dir.mkdir(parents=True, exist_ok=True)

        bad_decision = AgentDecision(
            mode="propose",
            confirm_and_commit=True,
            proposal=TriageProposal(
                headline="五彩湾非法日期任务",
                executive_summary="测试非法日期拦截。",
                actions=[
                    ActionMutation(
                        list_type=ListType.PROJECT_ACTION,
                        work_domain=WorkDomain.DELIVERY,
                        project_name="五彩湾电厂项目",
                        title="联系五彩湾电厂提供DCS文件",
                        deliverable="DCS文件",
                        owner="徐宏玮",
                        assignee="杨丽丽",
                        planned_start_at=start_date,
                        planned_end_at=end_date,
                    )
                ],
            ),
        )

        def scripted(kwargs: dict[str, Any], _idx: int, _dec=bad_decision) -> str:
            model = kwargs["model"]
            if model == "qwen3.8-flash":
                return IntentRoute(intent="work_triage", confidence=0.95, summary="测试").model_dump_json()
            return _dec.model_dump_json()

        engine, db, settings, completions = _make_engine(case_dir, scripted)
        try:
            res = engine.handle_incoming_turn(
                f"把五彩湾任务截止时间定在 {end_date}，直接确认落盘",
                external_msg_id=f"v3_guard_block_{case_name}",
            )
            called_models = [c["model"] for c in completions.calls]
            assert settings.fast_model not in called_models, (
                f"[{case_name}] v3.0 must not invoke fast_model, got {called_models}"
            )
            assert settings.critic_model not in called_models, (
                f"[{case_name}] v3.0 must not invoke critic_model, got {called_models}"
            )
            assert db.list_items(include_done=True) == [], (
                f"[{case_name}] Objective guard failure MUST prevent DB commit!"
            )
            reply = res["reply_text"]
            assert reply, f"[{case_name}] Expected non-empty rejection feedback"
            assert not any(kw in reply for kw in ("已确认落盘", "落盘成功", "已入库")), (
                f"[{case_name}] Rejected commit must not claim success:\n{reply}"
            )
        finally:
            engine.close()


# ---------------------------------------------------------------------------
# 7. Emergency offline buttons work with 0 LLM calls under total 503 outage
# ---------------------------------------------------------------------------


def test_v3_emergency_offline_buttons_work_when_flagship_llm_is_503(tmp_path: Path) -> None:
    """[禁令+边界] 旗舰与备用模型全部 503 宕机时，应急指令 1 / 撤销 / 0 / 看板 均 0 次 LLM 调用直接成功执行。"""

    def outage_llm(kwargs: dict[str, Any], _idx: int) -> str:
        raise RuntimeError("503 Service Unavailable")

    engine, db, _settings, completions = _make_engine(
        tmp_path,
        outage_llm,
        magic_link_factory=lambda: "https://assistant.fire-matrix.com/",
    )

    def _seed_pending(title: str) -> None:
        proposal = TriageProposal(
            headline=title,
            executive_summary=title,
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="五彩湾电厂项目",
                    title=title,
                    deliverable="DCS点表文件",
                    owner="徐宏玮",
                    assignee="杨丽丽",
                    planned_start_at="2026-11-24",
                    planned_end_at="2026-11-27",
                )
            ],
        )
        db.save_pending_proposal(
            thread_id="owner",
            proposal_dict=proposal.model_dump(mode="json"),
            source_ids=[],
        )

    try:
        # 1) "1" commits pending proposal #1 with 0 LLM calls
        _seed_pending("联系五彩湾电厂提供DCS文件")
        r_confirm = engine.handle_incoming_turn("1", external_msg_id="v3_offline_confirm")
        assert r_confirm["reply_text"]
        assert [c["model"] for c in completions.calls] == [], (
            f"'1' must use 0 LLM calls, got {[c['model'] for c in completions.calls]}"
        )
        assert len(db.list_items(include_done=True)) == 1
        assert db.get_latest_pending_proposal("owner") is None

        # 2) "撤销" rolls back the last commit with 0 LLM calls
        r_undo = engine.handle_incoming_turn("撤销", external_msg_id="v3_offline_undo")
        assert r_undo["reply_text"]
        assert [c["model"] for c in completions.calls] == [], (
            f"'撤销' must use 0 LLM calls, got {[c['model'] for c in completions.calls]}"
        )
        assert len(db.list_items(include_done=True)) == 0

        # 3) "0" discards pending proposal #2 with 0 LLM calls
        _seed_pending("待作废测试任务")
        assert db.get_latest_pending_proposal("owner") is not None
        r_discard = engine.handle_incoming_turn("0", external_msg_id="v3_offline_discard")
        assert r_discard["reply_text"]
        assert [c["model"] for c in completions.calls] == [], (
            f"'0' must use 0 LLM calls, got {[c['model'] for c in completions.calls]}"
        )
        assert db.get_latest_pending_proposal("owner") is None
        assert len(db.list_items(include_done=True)) == 0

        # 4) "看板" returns cockpit link with 0 LLM calls
        r_cockpit = engine.handle_incoming_turn("看板", external_msg_id="v3_offline_cockpit")
        assert "https://assistant.fire-matrix.com/" in r_cockpit["reply_text"], (
            f"'看板' should return cockpit link under 503 outage:\n{r_cockpit['reply_text']}"
        )
        assert [c["model"] for c in completions.calls] == [], (
            f"'看板' must use 0 LLM calls, got {[c['model'] for c in completions.calls]}"
        )
    finally:
        engine.close()
