"""Stage 3 & 4 core unit tests covering confidential isolation, schedule/effort separation, Excel diff, guards, HITL restart recovery, Web Auth, and WeCom whitelist."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake.wecom_gateway import WeComGateway
from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel, TriageProposal, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import parse_excel_quote_rows
from wechat_assistant.tools.calc_tools import analyze_excel_quote
from wechat_assistant.tools.guard import ApprovalToken, before_tool_callback
from wechat_assistant.tools.onedrive_tools import render_lists_markdown
from wechat_assistant.tools.search_tools import sanitize_external_query
from wechat_assistant.web.app import create_app


class _DummyOneDrive:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.notes: list[tuple[str, str]] = []
        self.synced_boards: dict[str, str] = {}

    def upload_bytes(self, remote_path: str, data: bytes, *, content_type: str = "") -> dict:
        self.uploads[remote_path] = data
        return {"id": f"id_{len(self.uploads)}", "webUrl": f"https://wissentek.sharepoint.cn/mock/{remote_path}", "size": len(data)}

    def upload_and_cleanup_local(self, remote_path: str, local_path: str | Path) -> dict:
        p = Path(local_path)
        data = p.read_bytes()
        if p.exists():
            p.unlink()
        return self.upload_bytes(remote_path, data)

    def append_project_note(self, project_name: str, entry_md: str) -> dict:
        self.notes.append((project_name, entry_md))
        return {"id": "note_1"}

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        self.synced_boards = render_lists_markdown(db)
        return {k: f"https://wissentek.sharepoint.cn/mock/00_我的四大清单/{k}" for k in self.synced_boards}


class _ScriptedCompletions:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=50, completion_tokens=40, completion_tokens_details=None),
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


def test_confidential_zero_llm_calls(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    completions = _ScriptedCompletions(lambda *_: "{}")
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    od = _DummyOneDrive()
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od)

    secret_file = tmp_path / "secret_param.txt"
    secret_file.write_text("Optical offset = 0.0042", encoding="utf-8")

    res = eng.handle_incoming_turn(
        "密：核心光学算法补偿参数备忘",
        attachments=[{"filename": "secret_param.txt", "path": str(secret_file)}],
    )
    assert res["confidential"] is True
    assert db.count_model_calls() == 0
    assert len(completions.calls) == 0
    assert any(p.startswith("04_想法与行业参考/") for p in od.uploads)
    assert not secret_file.exists()  # cleaned up after mock OneDrive upload
    eng.close()


def test_critic_rejects_conflated_waiting_hours_and_fabricated_numbers(tmp_path):
    bad_proposal = TriageProposal(
        headline="等待供应商打样",
        executive_summary="预计报价 999999 元，等待10天打样",
        actions=[
            ActionMutation(
                list_type=ListType.WAITING_FOR,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="锅炉测温",
                title="等待供应商高温探头打样",
                owner="某供应商",
                planned_start_at="2026-11-18",
                planned_end_at="2026-11-28",
                estimated_hours=80.0,  # Error: multiplied 10 calendar days by 8h
                priority=PriorityLevel.P1,
            )
        ],
        referenced_numbers=["999999"],
    )
    issues = deterministic_critic_check(
        bad_proposal,
        raw_input="供应商说高温探头打样需要10天，验收大概花我半小时",
        evidence_text="",
        tool_outputs_text="",
    )
    assert any("净工时误填为 80.0h" in i for i in issues)
    assert any("999999" in i for i in issues)


def test_bounded_reflection_loop_revises_rejected_proposal(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    producer_attempts = {"n": 0}

    def handler(kwargs, _idx):
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps({"intent": "work_triage", "confidence": 0.95, "needs_deep_research": False, "summary": "打样"})
        if model == "qwen3.8-max":
            producer_attempts["n"] += 1
            hrs = 80.0 if producer_attempts["n"] == 1 else 0.5
            return json.dumps({
                "headline": "高温探头打样跟进",
                "executive_summary": f"供应商打样 10 天，本人验收投入 {hrs}h。",
                "actions": [{
                    "list_type": "waiting_for",
                    "work_domain": "采购供应链",
                    "project_name": "锅炉测温",
                    "title": "等高温探头打样并验收",
                    "owner": "某供应商",
                    "planned_start_at": "2026-11-18",
                    "planned_end_at": "2026-11-28",
                    "estimated_hours": hrs,
                    "priority": "P1",
                    "onedrive_target_dir": "01_项目归档/锅炉测温",
                }],
                "referenced_numbers": [str(hrs)],
                "citations": [],
            })
        return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn("供应商打样10天，验收只需我0.5小时", external_msg_id="loop_1")
    assert producer_attempts["n"] == 2
    assert "critic:deterministic_reject" in res["trajectory"]
    assert "0.5h" in res["reply_text"]
    eng.close()


def test_excel_quote_diff_precision(tmp_path):
    p1 = tmp_path / "q1.xlsx"
    p2 = tmp_path / "q2.xlsx"
    for path, rows in [
        (p1, [["物料", "单价", "数量", "小计"], ["光纤探头", 1200, 10, 12000], ["主机箱", 5000, 1, 5000]]),
        (p2, [["物料", "单价", "数量", "小计"], ["光纤探头", 1350, 10, 13500], ["主机箱", 5000, 1, 5000]]),
    ]:
        wb = Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        wb.save(path)

    diff = analyze_excel_quote(parse_excel_quote_rows(p1), parse_excel_quote_rows(p2))
    assert diff["old_total"] == 17000.0
    assert diff["new_total"] == 18500.0
    assert diff["total_delta"] == 1500.0
    assert diff["changed"][0]["key"] == "光纤探头"


def test_external_query_sanitization():
    safe, redacted = sanitize_external_query("帕莫瑞科技有限公司 锅炉测温 2U机箱 ¥128000 EMI标准")
    assert "帕莫瑞" not in safe
    assert "128000" not in safe
    assert "2U机箱" in safe
    assert len(redacted) >= 2


def test_before_tool_callback_blocks_without_token():
    with pytest.raises(PermissionError):
        before_tool_callback("propose_list_mutations", {}, approval_token=None, signing_secret="abc")
    with pytest.raises(PermissionError):
        before_tool_callback("organize_onedrive_files", {}, approval_token=ApprovalToken.mint(1, "wrong"), signing_secret="abc")

    valid = ApprovalToken.mint(7, "abc-secret")
    before_tool_callback("compose_markdown_brief", {}, approval_token=valid, signing_secret="abc-secret")


def test_hitl_restart_recovery_checkin_and_undo(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _DummyOneDrive()

    def handler(kwargs, call_idx):
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps({"intent": "work_triage", "confidence": 0.95, "needs_deep_research": False, "summary": "合同审阅"})
        if model == "qwen3.8-max":
            return json.dumps({
                "headline": "审阅帕莫瑞合同",
                "executive_summary": "审阅合同预计净投入 1.5h，周五前完成。",
                "actions": [{
                    "list_type": "project_action",
                    "work_domain": "客户销售",
                    "project_name": "帕莫瑞交付",
                    "title": "审阅帕莫瑞技术合同",
                    "owner": "本人",
                    "planned_start_at": "2026-11-18",
                    "planned_end_at": "2026-11-20",
                    "estimated_hours": 1.5,
                    "priority": "P0",
                    "onedrive_target_dir": "01_项目归档/帕莫瑞交付",
                }],
                "referenced_numbers": ["1.5"],
                "citations": [],
            })
        return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))))
    eng1 = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od, checkpoints_path=tmp_path / "ckpt.db")
    preview = eng1.handle_incoming_turn("周五前要审完帕莫瑞技术合同，预计1.5h", external_msg_id="m_f8_1")
    assert preview["proposal_id"] is not None
    eng1.close()

    # F8: Simulate full process restart before user replies `1`
    db2 = Database(tmp_path / "app.db")
    calls_before = db2.count_model_calls()
    eng2 = ChiefOfStaffEngine(settings=settings, db=db2, gateway=gw, onedrive=od, checkpoints_path=tmp_path / "ckpt.db")
    commit_res = eng2.handle_incoming_turn("1")
    assert "已确认落盘" in commit_res["reply_text"]
    assert db2.count_model_calls() == calls_before  # zero extra LLM calls on restart confirm!
    assert "审阅帕莫瑞技术合同" in od.synced_boards["01_今日与行动待办.md"]

    # Check-in start & complete
    s_res = eng2.handle_incoming_turn("开始 1")
    assert "已记录" in s_res["reply_text"]
    c_res = eng2.handle_incoming_turn("完成 1 2.0h")
    assert "2.0h" in c_res["reply_text"]
    assert "实2.0h" in od.synced_boards["01_今日与行动待办.md"]

    # Undo rollback
    u_res = eng2.handle_incoming_turn("撤销")
    assert "已完整回滚" in u_res["reply_text"]
    assert len(db2.list_items()) == 0
    eng2.close()


def test_grounded_qa_with_page_citation_and_honest_refusal(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.insert_raw_source(
        source_type="pdf",
        external_msg_id="pdf_spec_1",
        sender="owner",
        title="Calibration_Spec_2026.pdf",
        raw_text="校准规范",
        extracted_pages=[
            {"page": 1, "text": "目录与概述"},
            {"page": 4, "text": "高温漂移补偿系数调整为 0.0095（旧版为 0.012）。"},
        ],
    )

    def handler(kwargs, _idx):
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps({"intent": "quick_query", "confidence": 0.99, "needs_deep_research": False, "summary": "查参数"})
        return json.dumps({
            "found": True,
            "answer": "根据 Calibration_Spec_2026.pdf 第 4 页，补偿系数已调整为 0.0095。",
            "citations": ["Calibration_Spec_2026.pdf 第 4 页"],
        })

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)

    hit = eng.handle_incoming_turn("Calibration_Spec_2026 补偿系数是多少")
    assert "0.0095" in hit["reply_text"]
    assert "第 4 页" in hit["reply_text"]

    miss = eng.handle_incoming_turn("火星基地合同总额是多少")
    assert "未查到" in miss["reply_text"]
    eng.close()


def test_web_app_single_use_magic_link_and_crud(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _DummyOneDrive()
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(lambda *_: "{}"))))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od)
    app = create_app(settings=settings, db=db, engine=eng, onedrive=od, start_background_tasks=False)

    # Seed one idea
    db.apply_proposal_atomic(
        proposal_id=None,
        actions=[ActionMutation(
            list_type=ListType.IDEA,
            work_domain=WorkDomain.RD,
            project_name="2U通用机箱",
            title="评估 2U 机箱通用化",
            planned_start_at="2026-11-18",
            planned_end_at="2026-11-25",
            estimated_hours=2.0,
        )],
        source_ids=[],
        doc_paths=[],
    )

    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Executive Work OS" in page.text

        assert client.get("/healthz").json()["status"] == "ok"
        assert client.get("/api/dashboard/overview").status_code == 401

        tok = app.state.auth.mint_magic_token(300)
        r1 = client.get(f"/auth/magic?token={tok}", follow_redirects=False)
        assert r1.status_code == 302
        # 2nd replay MUST fail cleanly
        r2 = client.get(f"/auth/magic?token={tok}", follow_redirects=False)
        assert r2.status_code == 403

        ov = client.get("/api/dashboard/overview")
        assert ov.status_code == 200
        assert len(ov.json()["items"]) == 1

        res_create = client.post(
            "/api/items",
            json={
                "title": "Review supplier NDA",
                "list_type": "next_action",
                "work_domain": "采购供应链",
                "project_name": "2U通用机箱",
                "owner": "Chairman",
                "estimated_hours": 1.0,
                "priority": "P0",
            },
        )
        assert res_create.status_code == 200
        new_id = res_create.json()["created_ids"][0]
        assert len(client.get("/api/dashboard/overview").json()["items"]) == 2

        res_del = client.delete(f"/api/items/{new_id}")
        assert res_del.status_code == 200
        assert res_del.json()["deleted"] is True
        assert len(client.get("/api/dashboard/overview").json()["items"]) == 1

        res_prom = client.post(
            "/api/items/1/promote",
            json={"project_name": "2U标准化项目", "planned_start_at": "2026-11-19", "planned_end_at": "2026-11-30", "estimated_hours": 3.5},
        )
        assert res_prom.status_code == 200
        assert res_prom.json()["item"]["list_type"] == "project_action"


def test_wecom_whitelist_and_merged_msg_parsing(tmp_path):
    settings = _make_settings(tmp_path)
    received = []

    async def proc(text, sender, atts, msgid):
        received.append((text, sender, msgid))
        return "ok"

    wc = WeComGateway(settings, turn_processor=proc)

    async def run():
        parsed_text, parsed_atts = await wc._parse_kf_message({
            "msgtype": "merged_msg",
            "merged_msg": {
                "title": "客户沟通记录",
                "item": [
                    {"sender_name": "客户A", "send_time": 1700000000, "msgtype": "text", "msg_content": '{"text":{"content":"周五前发最终报价"}}'},
                ],
            },
        })
        assert "客户沟通记录" in parsed_text
        assert "客户A" in parsed_text
        assert "周五前发最终报价" in parsed_text

        # Whitelist binding check
        wc.set_owner_external_userid("wm_owner_only_123")
        assert wc.get_owner_external_userid() == "wm_owner_only_123"

    asyncio.run(run())


def test_wecom_self_built_app_multimodal_and_batching(tmp_path, monkeypatch):
    monkeypatch.setenv("SEGMENT_QUIET_SECONDS", "0.05")
    settings = _make_settings(tmp_path)
    turns = []
    pushes = []

    async def proc(text, sender, atts, msgid):
        await asyncio.sleep(0.01)
        turns.append((text, sender, atts, msgid))
        return "已受理整合"

    wc = WeComGateway(settings, turn_processor=proc)

    async def fake_download(media_id: str, fallback_ext: str = ".bin", explicit_filename: str = ""):
        await asyncio.sleep(0.01)
        return {"filename": explicit_filename or f"f{fallback_ext}", "path": str(tmp_path / "f.xlsx"), "size": 2048}

    async def fake_push(content: str):
        await asyncio.sleep(0.01)
        pushes.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(wc, "_download_media", fake_download)
    monkeypatch.setattr(wc, "send_app_push", fake_push)

    async def run():
        await wc.handle_callback_event({"MsgType": "event", "Event": "enter_agent", "FromUserName": "XuHongwei"})
        assert len(turns) == 0

        await wc.handle_callback_event({
            "MsgType": "text",
            "Content": "帕莫瑞项目今天要跟进报价",
            "FromUserName": "XuHongwei",
            "MsgId": "m_1",
        })
        await wc.handle_callback_event({
            "MsgType": "file",
            "FileName": "报价v2.xlsx",
            "MediaId": "m123",
            "FromUserName": "XuHongwei",
            "MsgId": "m_2",
        })
        await asyncio.sleep(0.2)

        assert len(turns) == 1
        assert "帕莫瑞项目今天要跟进报价" in turns[0][0]
        assert turns[0][2][0]["filename"] == "报价v2.xlsx"
        assert len(pushes) == 2
        assert "⚡ 已收到" in pushes[0]
        assert pushes[1] == "已受理整合"

    asyncio.run(run())


def test_utf8_byte_chunking_voice_asr_and_binary_extractor(tmp_path, monkeypatch):
    from wechat_assistant.storage.extractors import extract_document_pages

    chunks = WeComGateway._split_chunks("中" * 950, limit=1800)
    assert len(chunks) >= 2
    assert all(len(c.encode("utf-8")) <= 1800 for c in chunks)

    amr_path = tmp_path / "sample.amr"
    amr_path.write_bytes(b"#!AMR\n\x04" + b"\x00" * 12)
    pages = extract_document_pages(amr_path)
    assert pages[0]["text"] == "[Media attachment: sample.amr]"

    monkeypatch.setenv("SEGMENT_QUIET_SECONDS", "0.02")
    settings = _make_settings(tmp_path)
    seen_texts = []
    pushes = []

    async def proc(text, sender, atts, msgid):
        await asyncio.sleep(0.01)
        seen_texts.append(text)
        return "已完成分析排期"

    wc = WeComGateway(settings, turn_processor=proc)

    async def fake_download(media_id: str, fallback_ext: str = ".bin", explicit_filename: str = ""):
        await asyncio.sleep(0.01)
        return {"filename": "voice.amr", "path": str(amr_path), "size": 19}

    async def fake_asr(local_path):
        await asyncio.sleep(0.01)
        return "明天下午两点评审2U机箱报价"

    async def fake_push(content: str):
        await asyncio.sleep(0.01)
        pushes.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(wc, "_download_media", fake_download)
    monkeypatch.setattr(wc, "_transcribe_audio_dashscope", fake_asr)
    monkeypatch.setattr(wc, "send_app_push", fake_push)

    async def run():
        await wc.handle_callback_event({
            "MsgType": "voice",
            "MediaId": "vm_1",
            "Format": "amr",
            "FromUserName": "XuHongwei",
            "MsgId": "m_voice_1",
        })
        await asyncio.sleep(0.15)

        assert seen_texts == ["[语音转写] 明天下午两点评审2U机箱报价"]
        assert len(pushes) == 2
        assert "🎙️ 已收到语音" in pushes[0]
        assert "🗣️ **语音识别**：「明天下午两点评审2U机箱报价」" in pushes[1]
        assert "已完成分析排期" in pushes[1]

    asyncio.run(run())


def test_continuous_multi_turn_qa_revision_and_natural_confirm(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _DummyOneDrive()
    router_prompts: list[str] = []

    def handler(kwargs, _idx):
        model = kwargs["model"]
        user_msg = kwargs["messages"][-2]["content"]
        if model == "qwen3.8-flash":
            router_prompts.append(user_msg)
            latest_msg = user_msg.split("【用户最新输入】")[-1]
            if "为什么排明天" in latest_msg:
                return json.dumps({
                    "intent": "quick_query",
                    "confidence": 0.96,
                    "needs_deep_research": False,
                    "resolved_intent_text": "为什么待确认卡片排在明天而不是今天",
                    "search_queries": ["帕莫瑞评审"],
                    "summary": "追问排期依据",
                })
            if "0.5小时就行" in latest_msg:
                return json.dumps({
                    "intent": "revise_pending",
                    "confidence": 0.96,
                    "needs_deep_research": False,
                    "resolved_intent_text": "将待确认卡片改期为下周五 2026-11-27，预计净工时 0.5h",
                    "search_queries": [],
                    "summary": "自然语言修改待确认卡",
                })
            if "按这个落盘" in latest_msg:
                return json.dumps({
                    "intent": "confirm_pending",
                    "confidence": 0.98,
                    "needs_deep_research": False,
                    "resolved_intent_text": "确认提交当前待确认卡片 #2 落盘",
                    "search_queries": [],
                    "summary": "自然语言确认落盘",
                })
            return json.dumps({
                "intent": "work_triage",
                "confidence": 0.95,
                "needs_deep_research": False,
                "resolved_intent_text": "安排帕莫瑞客户方案评审，预计1.5h",
                "search_queries": ["帕莫瑞"],
                "summary": "新建分拣提案",
            })

        if model == "qwen3.8-max":
            if "问题：" in user_msg:
                assert "待确认卡片 #1" in user_msg
                return json.dumps({
                    "found": True,
                    "answer": "待确认卡片 #1 当前排在明天 2026-11-18，净工时 1.5h。",
                    "citations": ["待确认卡片 #1"],
                })
            is_revised = "0.5h" in user_msg or "2026-11-27" in user_msg
            hrs = 0.5 if is_revised else 1.5
            end_d = "2026-11-27" if is_revised else "2026-11-18"
            return json.dumps({
                "headline": "帕莫瑞评审（调整版）" if is_revised else "帕莫瑞方案评审",
                "executive_summary": f"已按净工时 {hrs}h 排期至 {end_d}。",
                "actions": [{
                    "list_type": "project_action",
                    "work_domain": "项目交付",
                    "project_name": "帕莫瑞交付",
                    "title": "帕莫瑞方案评审",
                    "owner": "本人",
                    "planned_start_at": end_d,
                    "planned_end_at": end_d,
                    "estimated_hours": hrs,
                    "priority": "P1",
                    "onedrive_target_dir": "01_项目归档/帕莫瑞交付",
                }],
                "referenced_numbers": [str(hrs)],
                "citations": [],
            })

        return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=od)

    r1 = eng.handle_incoming_turn("明天安排帕莫瑞方案评审，预计1.5h", external_msg_id="mt_1")
    assert r1["proposal_id"] == 1

    # Follow-up question must inspect active card WITHOUT overwriting Proposal #1!
    r2 = eng.handle_incoming_turn("为什么排明天？", external_msg_id="mt_2")
    assert "待确认卡片 #1" in r2["reply_text"]
    assert db.get_latest_pending_proposal("owner")["id"] == 1
    assert "明天安排帕莫瑞方案评审" in router_prompts[-1]

    # Natural revision without literal "改：" prefix
    r3 = eng.handle_incoming_turn("改成下周五，0.5小时就行", external_msg_id="mt_3")
    assert r3["proposal_id"] == 2
    assert "0.5h" in r3["reply_text"]

    # Natural confirmation without literal "1"
    r4 = eng.handle_incoming_turn("好的，按这个落盘", external_msg_id="mt_4")
    assert "已确认落盘" in r4["reply_text"]
    items = db.list_items()
    assert len(items) == 1
    assert items[0]["estimated_hours"] == 0.5
    assert items[0]["planned_end_at"] == "2026-11-27"
    eng.close()


def test_discontinuous_long_horizon_context_recall(tmp_path):
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")

    # Seed an older episodic turn from 3 days earlier + 12 unrelated recent turns + 5h gap
    db.append_conversation_turn(
        thread_id="owner",
        role="user",
        content="帕莫瑞液冷板打样对接人是苏州精工陈总",
        intent="work_triage",
        topic_tags=["帕莫瑞", "液冷板", "苏州精工", "陈总"],
        created_at="2026-11-14 09:30:00",
    )
    for idx in range(12):
        db.append_conversation_turn(
            thread_id="owner",
            role="user",
            content=f"日常行政审批测试条目 {idx}",
            intent="chitchat",
            topic_tags=["行政审批"],
            created_at=f"2026-11-17 10:{idx:02d}:00",
        )

    qa_prompts: list[str] = []

    def handler(kwargs, _idx):
        model = kwargs["model"]
        user_msg = kwargs["messages"][-2]["content"]
        if model == "qwen3.8-flash":
            return json.dumps({
                "intent": "quick_query",
                "confidence": 0.97,
                "needs_deep_research": False,
                "resolved_intent_text": "前两天聊的帕莫瑞液冷板打样对接人是谁",
                "search_queries": ["帕莫瑞", "液冷板", "陈总"],
                "summary": "跨时段检索历史对话",
            })
        qa_prompts.append(user_msg)
        return json.dumps({
            "found": True,
            "answer": "根据 2026-11-14 的对话记录，帕莫瑞液冷板打样对接人是苏州精工陈总。",
            "citations": ["2026-11-14 历史对话记录"],
        })

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(handler))))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn("前两天聊的帕莫瑞液冷板对接人是谁？", external_msg_id="lh_1")
    assert "陈总" in res["reply_text"]
    assert len(qa_prompts) == 1
    assert "苏州精工陈总" in qa_prompts[0]
    eng.close()
