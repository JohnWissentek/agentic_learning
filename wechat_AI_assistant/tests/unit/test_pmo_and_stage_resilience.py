"""PMO delegation visibility & Stage 1-5 resilience black-box contract tests (Red-Green TDD)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.context_assembler import ContextAssembler
from wechat_assistant.graph import ChiefOfStaffEngine, format_decision_card
from wechat_assistant.intake.mail_poller import poll_mailbox_once
from wechat_assistant.intake.wecom_gateway import WeComGateway
from wechat_assistant.schemas import (
    ActionMutation,
    CriticVerdict,
    ListType,
    PriorityLevel,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import extract_document_pages


class _ScriptedCompletions:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=40, completion_tokens=30, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None, reasoning_content=""))],
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


def test_decision_card_displays_owner_for_pmo_delegation(tmp_path: Path) -> None:
    """[正常] 当分拣动作包含外部委派责任人（如张工）时，生成的决策确认卡应显式展示责任人标识与姓名，且绝不隐去委派归属。"""
    proposal = TriageProposal(
        headline="传感器高温老化报告跟进",
        executive_summary="已拆解外部跟进事项，预计周五前收回报告并花 0.5h 验收。",
        actions=[
            ActionMutation(
                list_type=ListType.WAITING_FOR,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞交付",
                title="提交传感器高温老化测试报告",
                owner="张工",
                planned_start_at="2026-11-24",
                planned_end_at="2026-11-28",
                estimated_hours=0.5,
                priority=PriorityLevel.P1,
                onedrive_target_dir="01_项目归档/帕莫瑞交付",
            )
        ],
        referenced_numbers=["0.5"],
        citations=[],
    )

    card_text = format_decision_card(1, proposal)
    assert "张工" in card_text
    assert "负责人" in card_text

    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")

    def handler(kwargs, _idx):
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps(
                {
                    "intent": "work_triage",
                    "confidence": 0.96,
                    "needs_deep_research": False,
                    "summary": "委派老化报告跟进",
                },
                ensure_ascii=False,
            )
        if model == "qwen3.8-max":
            return proposal.model_dump_json()
        return CriticVerdict(passed=True, numeric_fidelity_ok=True, schedule_reasonable=True).model_dump_json()

    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))),
    )
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn(
        "让张工周五前提交传感器高温老化报告，验收只需我0.5小时",
        external_msg_id="pmo_owner_1",
    )
    assert "张工" in res["reply_text"]
    assert "负责人" in res["reply_text"]
    eng.close()


def test_critic_max_loops_unpassed_exposes_warning_on_card(tmp_path: Path) -> None:
    """[边界] 当异构审计模型连续达到最大反思轮数仍未通过并强制放行至确认门禁时，微信确认卡应显式包含未通过的审计问题警告，且绝不静默隐藏风险。"""
    settings = _make_settings(tmp_path)
    assert settings.max_reflection_loops == 2
    db = Database(tmp_path / "app.db")
    critic_calls = {"n": 0}

    def handler(kwargs, _idx):
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps(
                {
                    "intent": "work_triage",
                    "confidence": 0.95,
                    "needs_deep_research": False,
                    "summary": "核对传感器交期",
                },
                ensure_ascii=False,
            )
        if model == "qwen3.8-max":
            return TriageProposal(
                headline="帕莫瑞传感器交期核对",
                executive_summary="安排传感器交期核对，预计本人投入 1.0h。",
                actions=[
                    ActionMutation(
                        list_type=ListType.PROJECT_ACTION,
                        work_domain=WorkDomain.DELIVERY,
                        project_name="帕莫瑞交付",
                        title="核对帕莫瑞传感器交期",
                        owner="本人",
                        planned_start_at="2026-11-24",
                        planned_end_at="2026-11-26",
                        estimated_hours=1.0,
                        priority=PriorityLevel.P1,
                        onedrive_target_dir="01_项目归档/帕莫瑞交付",
                    )
                ],
                referenced_numbers=["1.0"],
                citations=[],
            ).model_dump_json()

        critic_calls["n"] += 1
        return CriticVerdict(
            passed=False,
            numeric_fidelity_ok=True,
            schedule_reasonable=False,
            issues=["关键交期与原文不符"],
            fix_instructions="核对交期",
        ).model_dump_json()

    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))),
    )
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn(
        "核对帕莫瑞传感器交期，预计本人投入 1.0 小时",
        external_msg_id="critic_warn_1",
    )
    assert critic_calls["n"] >= 2
    assert "node:hitl_preview_gate" in res["trajectory"]
    assert "关键交期与原文不符" in res["reply_text"]
    eng.close()


def test_attachment_ingested_even_when_routed_to_quick_qa(tmp_path: Path) -> None:
    """[边界] 当用户同时上传附件并提问且被路由为快速问答（quick_query）时，应先提取附件入库并带着附件证据完成作答，且绝不漏掉当轮附件。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")

    quote_file = tmp_path / "NewQuote.txt"
    quote_file.write_text("帕莫瑞最新传感器底价为 36.8 万元", encoding="utf-8")

    qa_prompts: list[str] = []

    def handler(kwargs, _idx):
        model = kwargs["model"]
        joined_messages = "\n".join(str(m.get("content", "")) for m in kwargs.get("messages", []))
        if model == "qwen3.8-flash":
            return json.dumps(
                {
                    "intent": "quick_query",
                    "confidence": 0.98,
                    "needs_deep_research": False,
                    "resolved_intent_text": "这份附件里帕莫瑞底价是多少？",
                    "search_queries": ["帕莫瑞", "底价", "NewQuote"],
                    "summary": "查询新附件底价",
                },
                ensure_ascii=False,
            )
        qa_prompts.append(joined_messages)
        return json.dumps(
            {
                "found": True,
                "answer": "根据附件 NewQuote.txt，帕莫瑞最新传感器底价为 36.8 万元。",
                "citations": ["NewQuote.txt 第 1 页"],
            },
            ensure_ascii=False,
        )

    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))),
    )
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn(
        "这份附件里帕莫瑞底价是多少？",
        external_msg_id="att_qa_1",
        attachments=[
            {
                "filename": "NewQuote.txt",
                "path": str(quote_file),
                "size": quote_file.stat().st_size,
            }
        ],
    )

    assert len(db.search_sources("36.8")) >= 1
    assert len(qa_prompts) == 1
    assert "36.8" in qa_prompts[0]
    assert "36.8" in res["reply_text"]
    assert "未查到" not in res["reply_text"]
    eng.close()


def test_corrupt_docx_and_xlsx_gracefully_fallback(tmp_path: Path) -> None:
    """[边界] 当收到损坏或加密的 .docx/.xlsx 非法 OOXML 字节文件时，extract_document_pages 应降级返回单页可读说明，且绝不抛出未捕获解析异常。"""
    broken_docx = tmp_path / "broken.docx"
    encrypted_xlsx = tmp_path / "encrypted.xlsx"
    broken_docx.write_bytes(b"CORRUPT_OOXML_BYTES")
    encrypted_xlsx.write_bytes(b"CORRUPT_OOXML_BYTES")

    docx_pages = extract_document_pages(broken_docx)
    xlsx_pages = extract_document_pages(encrypted_xlsx)

    assert len(docx_pages) == 1
    assert "broken.docx" in docx_pages[0]["text"]
    assert any(kw in docx_pages[0]["text"] for kw in ("无法解析", "未解析", "解析失败", "损坏"))
    assert "CORRUPT_OOXML_BYTES" not in docx_pages[0]["text"]

    assert len(xlsx_pages) == 1
    assert "encrypted.xlsx" in xlsx_pages[0]["text"]
    assert any(kw in xlsx_pages[0]["text"] for kw in ("无法解析", "未解析", "解析失败", "损坏"))
    assert "CORRUPT_OOXML_BYTES" not in xlsx_pages[0]["text"]


def test_wecom_arrival_ack_failure_does_not_drop_message(tmp_path: Path, monkeypatch) -> None:
    """[边界] 当企业微信发送首条「⚡ 已收到」回执偶发网络超时报错时，后续消息聚合与业务主流程仍应正常执行并推送正式回复，且绝不丢弃用户消息。"""
    monkeypatch.setenv("SEGMENT_QUIET_SECONDS", "0.03")
    settings = _make_settings(tmp_path)
    turns: list[tuple[str, str, list[dict], str]] = []
    push_attempts: list[str] = []
    delivered_pushes: list[str] = []

    async def proc(text: str, sender: str, atts: list[dict], msgid: str) -> str:
        turns.append((text, sender, atts, msgid))
        return "正式排期确认卡回复"

    wc = WeComGateway(settings, turn_processor=proc)

    async def flaky_push(content: str) -> dict:
        push_attempts.append(content)
        if len(push_attempts) == 1:
            raise RuntimeError("ack timeout")
        delivered_pushes.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(wc, "send_app_push", flaky_push)

    async def run() -> None:
        await wc.handle_callback_event(
            {
                "MsgType": "text",
                "Content": "跟进帕莫瑞合同签署",
                "FromUserName": "XuHongwei",
                "MsgId": "m_ack_timeout_1",
            }
        )
        await asyncio.sleep(0.18)

    asyncio.run(run())

    assert len(push_attempts) == 2
    assert "⚡ 已收到" in push_attempts[0]
    assert len(turns) == 1
    assert "跟进帕莫瑞合同签署" in turns[0][0]
    assert delivered_pushes == ["正式排期确认卡回复"]


def test_wecom_parse_crash_does_not_burn_msgid_dedup(tmp_path: Path, monkeypatch) -> None:
    """[边界] 当企业微信回调首次解析消息（如下载媒体抖动）抛错未进入聚合器时，同一 MsgId 重推应正常解析并进入业务处理，且绝不被去重表误杀。"""
    monkeypatch.setenv("SEGMENT_QUIET_SECONDS", "0.03")
    settings = _make_settings(tmp_path)
    turns: list[tuple[str, str, list[dict], str]] = []
    pushes: list[str] = []

    async def proc(text: str, sender: str, atts: list[dict], msgid: str) -> str:
        turns.append((text, sender, atts, msgid))
        return "重推后成功受理"

    wc = WeComGateway(settings, turn_processor=proc)
    orig_parse = wc._parse_app_xml_message
    parse_calls = {"n": 0}

    async def flaky_parse(ev: dict[str, str]):
        parse_calls["n"] += 1
        if parse_calls["n"] == 1:
            raise RuntimeError("download jitter")
        return await orig_parse(ev)

    async def fake_push(content: str) -> dict:
        pushes.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(wc, "_parse_app_xml_message", flaky_parse)
    monkeypatch.setattr(wc, "send_app_push", fake_push)

    event_payload = {
        "MsgType": "text",
        "Content": "帕莫瑞交付排期确认",
        "FromUserName": "XuHongwei",
        "MsgId": "m_same_retry_1",
    }

    async def run() -> None:
        try:
            await wc.handle_callback_event(event_payload)
        except RuntimeError:
            pass

        await wc.handle_callback_event(event_payload)
        await asyncio.sleep(0.18)

        # Third duplicate push after successful intake must still be deduplicated
        await wc.handle_callback_event(event_payload)
        await asyncio.sleep(0.10)

    asyncio.run(run())

    assert parse_calls["n"] == 2
    assert len(turns) == 1
    assert "帕莫瑞交付排期确认" in turns[0][0]
    assert "重推后成功受理" in pushes


def test_mail_poller_does_not_mark_seen_when_handler_fails(tmp_path: Path, monkeypatch) -> None:
    """[边界] 当邮件拉取后下游 on_email 处理首次抛临时异常时，不应锁死外部邮件去重记录，下轮重试恢复后同一邮件必须成功处理 1 次。"""
    settings = Settings(
        dashscope_api_key="sk-fakeunit1234567890abcdef",
        data_dir=str(tmp_path / "data"),
        mail_enabled=True,
        mail_allowlist=("V&F",),
    )
    db = Database(tmp_path / "app.db")
    sample = [
        {
            "id": "mail_1",
            "internetMessageId": "<vf-transient-mail-1>",
            "subject": "V&F urgent delivery update",
            "from": {"emailAddress": {"address": "sales@vf.at", "name": "V&F"}},
            "bodyPreview": "Updated sensor shipment schedule.",
        }
    ]

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"value": sample}

    class _Client:
        def __init__(self, *a, **kw) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a) -> bool:
            return False

        async def get(self, *a, **kw) -> _Resp:
            return _Resp()

    monkeypatch.setattr("wechat_assistant.intake.mail_poller.httpx.AsyncClient", _Client)
    od = SimpleNamespace(_get_token=lambda: "fake-mail-token")

    attempts = {"n": 0}
    processed: list[str] = []

    async def flaky_on_email(body: str, sender: str, ext_id: str) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient error")
        processed.append(ext_id)

    try:
        asyncio.run(poll_mailbox_once(settings, od, flaky_on_email, mark_seen=db.mark_external_seen))
    except RuntimeError:
        pass
    assert processed == []

    cnt_retry = asyncio.run(poll_mailbox_once(settings, od, flaky_on_email, mark_seen=db.mark_external_seen))
    assert cnt_retry == 1
    assert processed == ["<vf-transient-mail-1>"]

    cnt_dup = asyncio.run(poll_mailbox_once(settings, od, flaky_on_email, mark_seen=db.mark_external_seen))
    assert cnt_dup == 0
    assert processed == ["<vf-transient-mail-1>"]


def test_context_assembler_survives_malformed_json_columns(tmp_path: Path) -> None:
    """[边界] 当历史库中 projects.aliases_json 或 conversation_turns.topic_tags_json 含非法 JSON 字符串时，ContextAssembler.assemble 应容错降级并正常返回上下文，且绝不崩溃。"""
    db_path = tmp_path / "app.db"
    db = Database(db_path)

    db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞测温项目",
                title="核对高温探头线束长度",
                planned_start_at="2026-11-24",
                planned_end_at="2026-11-28",
                priority=PriorityLevel.P1,
            )
        ],
        source_ids=[],
        doc_paths=[],
        brief_summary="推进帕莫瑞探头定制",
    )
    db.append_conversation_turn(
        thread_id="owner",
        role="user",
        content="帕莫瑞探头线束长度改为 3 米",
        topic_tags=["帕莫瑞", "线束"],
    )

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE projects SET aliases_json = ?", ("帕莫瑞,维恩",))
    conn.execute("UPDATE conversation_turns SET topic_tags_json = ?", ("{bad_json",))
    conn.commit()
    conn.close()

    assembler = ContextAssembler(db)
    ctx = assembler.assemble("owner", "帕莫瑞")
    rendered = assembler.render_for_router(ctx, "帕莫瑞")

    assert ctx is not None
    assert "帕莫瑞测温项目" in rendered
    assert "核对高温探头线束长度" in rendered


def test_operational_override_supports_zero_and_cancel_even_on_router_outage(tmp_path: Path) -> None:
    """[边界] 当库中存在待确认卡片时，即使路由模型误判为 chitchat 或直接故障抛错，用户回复「0」或「取消」仍应确定性作废待确认卡片，且绝不误写正式待办。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")

    sample_proposal = TriageProposal(
        headline="帕莫瑞样品寄送",
        executive_summary="寄送测试样品。",
        actions=[
            ActionMutation(
                list_type=ListType.NEXT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞交付",
                title="安排寄送帕莫瑞测试样品",
                owner="本人",
                planned_start_at="2026-11-24",
                planned_end_at="2026-11-25",
                estimated_hours=0.5,
                priority=PriorityLevel.P1,
            )
        ],
    ).model_dump()

    # Case A: Router misclassifies "0" as chitchat
    db.save_pending_proposal(thread_id="owner", proposal_dict=sample_proposal, source_ids=[])
    assert db.get_latest_pending_proposal("owner") is not None

    misclassify_gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(
            chat=SimpleNamespace(
                completions=_ScriptedCompletions(
                    lambda *_: json.dumps({"intent": "chitchat", "confidence": 0.95, "summary": "数字0"})
                )
            )
        ),
    )
    eng_mis = ChiefOfStaffEngine(settings=settings, db=db, gateway=misclassify_gw)
    res_zero_mis = eng_mis.handle_incoming_turn("0", external_msg_id="override_zero_mis")
    assert db.get_latest_pending_proposal("owner") is None
    assert "已作废" in res_zero_mis["reply_text"]
    assert len(db.list_items(include_done=True)) == 0
    eng_mis.close()

    # Case B: Complete router LLM outage on both "0" and "取消"
    class _OutageGateway:
        def generate_structured(self, *a, **kw):
            raise RuntimeError("router 503 outage")

    eng_outage = ChiefOfStaffEngine(settings=settings, db=db, gateway=_OutageGateway())

    db.save_pending_proposal(thread_id="owner", proposal_dict=sample_proposal, source_ids=[])
    res_zero_outage = eng_outage.handle_incoming_turn("0", external_msg_id="override_zero_outage")
    assert db.get_latest_pending_proposal("owner") is None
    assert "已作废" in res_zero_outage["reply_text"]

    db.save_pending_proposal(thread_id="owner", proposal_dict=sample_proposal, source_ids=[])
    res_cancel_outage = eng_outage.handle_incoming_turn("取消", external_msg_id="override_cancel_outage")
    assert db.get_latest_pending_proposal("owner") is None
    assert "已作废" in res_cancel_outage["reply_text"]
    assert len(db.list_items(include_done=True)) == 0
    eng_outage.close()


def test_stage5_onedrive_outage_still_commits_sqlite_truthfully(tmp_path: Path) -> None:
    """[正常/边界] 当远端 OneDrive 全部接口抛 503 异常时，确认落盘「1」与打卡「完成 1」仍应成功提交本地 SQLite 并如实反馈已落盘，且绝不谎报「没有生成待办」。"""

    class _OutageOneDrive:
        def upload_bytes(self, *a, **kw):
            raise RuntimeError("onedrive 503")

        def upload_and_cleanup_local(self, *a, **kw):
            raise RuntimeError("onedrive 503")

        def list_onedrive_tree(self, *a, **kw):
            raise RuntimeError("onedrive 503")

        def sync_all_lists(self, *a, **kw):
            raise RuntimeError("onedrive 503")

        def append_project_note(self, *a, **kw):
            raise RuntimeError("onedrive 503")

    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _OutageOneDrive()

    def handler(kwargs, _idx):
        model = kwargs["model"]
        user_msg = kwargs["messages"][-2]["content"] if len(kwargs.get("messages", [])) >= 2 else ""
        if model == "qwen3.8-flash":
            latest = user_msg.split("【用户最新输入】")[-1].strip()
            if latest == "1":
                return json.dumps(
                    {
                        "intent": "confirm_pending",
                        "confidence": 0.99,
                        "needs_deep_research": False,
                        "summary": "确认落盘",
                    },
                    ensure_ascii=False,
                )
            if latest.startswith("完成"):
                return json.dumps(
                    {
                        "intent": "checkin",
                        "confidence": 0.99,
                        "needs_deep_research": False,
                        "target_item_id": 1,
                        "summary": "完成打卡",
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "intent": "work_triage",
                    "confidence": 0.96,
                    "needs_deep_research": False,
                    "summary": "审阅技术协议",
                },
                ensure_ascii=False,
            )
        if model == "qwen3.8-max":
            return TriageProposal(
                headline="审阅帕莫瑞技术协议",
                executive_summary="周五前完成帕莫瑞技术协议审阅，预计净工时 1.5h。",
                actions=[
                    ActionMutation(
                        list_type=ListType.PROJECT_ACTION,
                        work_domain=WorkDomain.SALES,
                        project_name="帕莫瑞交付",
                        title="审阅帕莫瑞技术协议",
                        owner="本人",
                        planned_start_at="2026-11-24",
                        planned_end_at="2026-11-27",
                        estimated_hours=1.5,
                        priority=PriorityLevel.P0,
                        onedrive_target_dir="01_项目归档/帕莫瑞交付",
                    )
                ],
                referenced_numbers=["1.5"],
                citations=[],
            ).model_dump_json()
        return CriticVerdict(passed=True, numeric_fidelity_ok=True, schedule_reasonable=True).model_dump_json()

    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))),
    )
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od)

    preview = eng.handle_incoming_turn("周五前审完帕莫瑞技术协议，预计1.5h", external_msg_id="od503_1")
    assert preview["proposal_id"] is not None

    commit_res = eng.handle_incoming_turn("1", external_msg_id="od503_2")
    items = db.list_items(include_done=True)
    assert len(items) == 1
    assert items[0]["title"] == "审阅帕莫瑞技术协议"
    assert "已确认落盘" in commit_res["reply_text"]
    assert "没有生成待办" not in commit_res["reply_text"]

    done_res = eng.handle_incoming_turn("完成 1", external_msg_id="od503_3")
    assert "没有生成待办" not in done_res["reply_text"]
    updated_items = db.list_items(include_done=True)
    assert updated_items[0]["status"] == "done"
    eng.close()
