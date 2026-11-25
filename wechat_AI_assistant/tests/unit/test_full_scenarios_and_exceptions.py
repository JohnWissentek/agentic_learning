"""全仓企业微信对话 + 阶段 1-6 全应用场景与全异常韧性 + Web 驾驶舱鉴权与 CRUD + OneDrive 客户端黑盒测试套件。

严格遵循读写隔离 TDD 原则：以生产级业务规格与防御基线为唯一真理标准，
使用真实临时 SQLite、真实 ChiefOfStaffEngine、真实 FastAPI TestClient、
真实 WeComGateway、真实 extract_document_pages、deterministic_critic_check、
calc_business_date，仅对外部 HTTP / LLM API 做确定性 Stub。
"""

from __future__ import annotations

import asyncio
import base64
import copy
import gc
import json
import os
import re
import sqlite3
import warnings
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi.testclient import TestClient

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake.wecom_gateway import (
    QuietAggregator,
    WeComGateway,
    compute_signature,
)
from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.schemas import (
    ActionMutation,
    ListType,
    PriorityLevel,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage import extractors
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import extract_document_pages
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient, render_lists_markdown
from wechat_assistant.tools.schedule_tools import calc_business_date
from wechat_assistant.web.app import COOKIE_NAME, create_app


# ---------------------------------------------------------------------------
# 通用黑盒测试基础设施（可控 Fake / Stub）
# ---------------------------------------------------------------------------


class _DummyOneDrive:
    """可控内存 OneDrive Stub，精确记录上传与清理调用次数。"""

    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.cleanup_upload_calls: int = 0
        self.notes: list[tuple[str, str]] = []
        self.synced_boards: dict[str, str] = {}

    def upload_bytes(self, remote_path: str, data: bytes, *, content_type: str = "") -> dict[str, Any]:
        self.uploads[remote_path] = data
        return {
            "id": f"id_{len(self.uploads)}",
            "webUrl": f"https://wissentek.sharepoint.cn/mock/{remote_path}",
            "size": len(data),
        }

    def upload_and_cleanup_local(self, remote_path: str, local_path: str | Path) -> dict[str, Any]:
        self.cleanup_upload_calls += 1
        p = Path(local_path)
        data = p.read_bytes()
        if p.exists():
            p.unlink()
        return self.upload_bytes(remote_path, data)

    def append_project_note(self, project_name: str, entry_md: str) -> dict[str, Any]:
        self.notes.append((project_name, entry_md))
        return {"id": f"note_{len(self.notes)}"}

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        self.synced_boards = render_lists_markdown(db)
        return {
            k: f"https://wissentek.sharepoint.cn/mock/00_我的四大清单/{k}"
            for k in self.synced_boards
        }


class _ScriptedCompletions:
    """确定性 LLM Stub：按调用记录完整参数并返回预设 JSON。"""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=60, completion_tokens=45, completion_tokens_details=None),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content, tool_calls=None, reasoning_content="")
                )
            ],
        )


def _make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "dashscope_api_key": "sk-fakeunit1234567890abcdef",
        "web_access_secret": "unit-test-hmac-secret-key-1234567890",
        "data_dir": str(tmp_path / "data"),
        "wecom_corp_id": "wwtestcorp",
        "wecom_app_agent_id": "1000002",
        "wecom_app_secret": "fake_wecom_app_secret_123456",
        "wecom_app_token": "tokentest123456",
        "wecom_app_aes_key": "A" * 43,
        "ms_tenant_id": "tenant-test-001",
        "ms_client_id": "client-test-001",
        "ms_client_secret": "ms-client-secret-test-12345",
        "ms_site_id": "site-test-001",
    }
    base.update(overrides)
    return Settings(**base)


def _make_engine(
    tmp_path: Path,
    handler,
    *,
    db: Database | None = None,
    onedrive: _DummyOneDrive | None = None,
    settings: Settings | None = None,
) -> tuple[ChiefOfStaffEngine, Database, _ScriptedCompletions, _DummyOneDrive]:
    st = settings or _make_settings(tmp_path)
    database = db or Database(tmp_path / "app.db")
    od = onedrive or _DummyOneDrive()
    completions = _ScriptedCompletions(handler)
    gw = DashScopeLLMGateway(st, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(
        settings=st,
        db=database,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "checkpoints.db",
        magic_link_factory=lambda: "https://assistant.fire-matrix.com/",
    )
    return eng, database, completions, od


def _encrypt_wecom_payload(aes_key_43: str, plaintext: str, receive_id: str) -> str:
    """按企业微信标准 AES-256-CBC + PKCS7(32字节块) 加密回调明文。"""
    key = base64.b64decode(aes_key_43 + "=")
    msg_bytes = plaintext.encode("utf-8")
    raw = os.urandom(16) + len(msg_bytes).to_bytes(4, "big") + msg_bytes + receive_id.encode("utf-8")
    pad_len = 32 - (len(raw) % 32)
    padded = raw + bytes([pad_len]) * pad_len
    cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
    enc = cipher.encryptor()
    encrypted = enc.update(padded) + enc.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def _proposal_dict_with_actions(actions: list[dict[str, Any]], headline: str = "测试待确认卡") -> dict[str, Any]:
    return {
        "headline": headline,
        "executive_summary": "用于验证待确认卡流转与落盘语义的测试提案。",
        "actions": actions,
        "referenced_numbers": [],
        "citations": [],
    }


def _action_dict(
    *,
    title: str,
    list_type: str = "project_action",
    project_name: str = "帕莫瑞项目",
    work_domain: str = "项目交付",
    start: str = "2026-11-25",
    end: str = "2026-11-28",
    hours: float = 1.0,
) -> dict[str, Any]:
    return {
        "list_type": list_type,
        "work_domain": work_domain,
        "project_name": project_name,
        "title": title,
        "owner": "本人",
        "planned_start_at": start,
        "planned_end_at": end,
        "estimated_hours": hours,
        "priority": "P1",
        "onedrive_target_dir": f"01_项目归档/{project_name}",
    }


# ---------------------------------------------------------------------------
# 1. 跨轮状态零串台（AUD-P0-1）
# ---------------------------------------------------------------------------


def test_same_day_turns_without_external_msg_id_never_leak_state(tmp_path: Path) -> None:
    """同一天不传 external_msg_id 连续多轮对话，绝不可发生跨轮状态泄漏。

    (a) 先发「改：延迟到下周」走修正流程，紧接着发普通查询，必须正常调用 fast_model 路由，
        绝不可被上一轮残留的 user_correction 劫持去跑 work_triage；
    (b) 先对含 project_action+idea 的卡片回「2」(仅存想法)，再对新卡片回「1」(全量落盘)，
        第 2 张卡的 project_action 必须完整落盘，绝不可继承上一轮 pending_ideas_only=True。
    """

    # --- 子场景 (a): user_correction 不泄漏到下一轮普通查询 ---
    def handler_a(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        sys_msgs = "\n".join(str(m.get("content", "")) for m in kwargs.get("messages", []))
        if model == "qwen3.8-flash":
            if "ConversationalReply" in sys_msgs or "reply_text" in sys_msgs:
                return json.dumps({"reply_text": "您当前有 1 项待确认事项，其余待办已整理完毕。"})
            return json.dumps({
                "intent": "conversational_chat",
                "confidence": 0.95,
                "summary": "普通待办查询",
            })
        if model == "qwen3.8-max":
            return json.dumps(
                _proposal_dict_with_actions(
                    [_action_dict(title="延迟到下周的交付评审", start="2026-12-01", end="2026-12-04")],
                    headline="已按要求顺延至下周",
                )
            )
        return json.dumps({
            "passed": True,
            "numeric_fidelity_ok": True,
            "schedule_reasonable": True,
            "issues": [],
            "fix_instructions": "",
        })

    eng_a, db_a, comp_a, _ = _make_engine(tmp_path / "case_a", handler_a)
    try:
        db_a.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([_action_dict(title="本周交付评审")]),
            source_ids=[],
        )

        # 第 1 轮：不传 external_msg_id，触发修正流程
        rev_res = eng_a.handle_incoming_turn("改：延迟到下周")
        assert rev_res["proposal_id"] is not None

        calls_before_query = len(comp_a.calls)
        # 第 2 轮：同一天、同一 thread_id、不传 external_msg_id，发普通查询
        query_res = eng_a.handle_incoming_turn("你好，帮我看看最近有什么待办？")
        turn2_calls = comp_a.calls[calls_before_query:]
        turn2_models = [c["model"] for c in turn2_calls]

        assert "qwen3.8-flash" in turn2_models, "普通查询必须正常调用 fast_model 进行路由，不得被上一轮修正状态劫持"
        assert query_res["proposal_id"] is None
        assert "node:producer_drafter" not in query_res["trajectory"]
    finally:
        eng_a.close()

    # --- 子场景 (b): pending_ideas_only 不泄漏到下一张卡片的「1」全量确认 ---
    eng_b, db_b, _, _ = _make_engine(
        tmp_path / "case_b",
        lambda *_: json.dumps({"intent": "chitchat", "confidence": 0.9, "summary": "noop"}),
    )
    try:
        db_b.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([
                _action_dict(title="卡1正式任务", list_type="project_action"),
                _action_dict(title="卡1闪念想法", list_type="idea"),
            ]),
            source_ids=[],
        )
        res_ideas_only = eng_b.handle_incoming_turn("2")
        assert res_ideas_only["reply_text"]
        titles_after_card1 = {it["title"] for it in db_b.list_items()}
        assert "卡1闪念想法" in titles_after_card1
        assert "卡1正式任务" not in titles_after_card1

        # 第 2 张卡同样包含 project_action + idea，回复「1」全量落盘（均不传 external_msg_id）
        db_b.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([
                _action_dict(title="卡2正式任务", list_type="project_action"),
                _action_dict(title="卡2闪念想法", list_type="idea"),
            ]),
            source_ids=[],
        )
        res_full_commit = eng_b.handle_incoming_turn("1")
        assert res_full_commit["reply_text"]
        titles_after_card2 = {it["title"] for it in db_b.list_items()}
        assert "卡2正式任务" in titles_after_card2, "回复 1 必须全量落盘 project_action，绝不可继承上一轮 pending_ideas_only=True"
        assert "卡2闪念想法" in titles_after_card2
    finally:
        eng_b.close()


# ---------------------------------------------------------------------------
# 2. Web 驾驶舱 6 位验证码防爆破锁定（AUD-P0-3a）
# ---------------------------------------------------------------------------


def test_web_verify_code_locks_out_after_five_wrong_attempts(tmp_path: Path) -> None:
    """连续 5 次输入错误 6 位验证码后必须触发防爆破锁定，第 6 次即便传正确验证码也拒绝签发 Cookie。"""
    eng, db, _, od = _make_engine(tmp_path, lambda *_: "{}")
    try:
        app = create_app(
            settings=eng.settings,
            db=db,
            engine=eng,
            onedrive=od,
            start_background_tasks=False,
        )
        with TestClient(app) as client:
            valid_code = app.state.auth.mint_login_code(300)
            wrong_code = "000000" if valid_code != "000000" else "999999"

            for attempt in range(5):
                resp = client.post("/api/auth/verify-code", json={"code": wrong_code})
                assert resp.status_code == 401, f"第 {attempt + 1} 次错误验证码应返回 401"
                assert COOKIE_NAME not in resp.cookies

            # 第 6 次即便传入原本正确的 6 位码，也必须因锁定/失效被拦截
            sixth = client.post("/api/auth/verify-code", json={"code": valid_code})
            assert sixth.status_code in (401, 429)
            assert COOKIE_NAME not in sixth.cookies
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 3. Web 驾驶舱写接口严格校验、改项目名同步与升级想法约束（AUD-P0-3b）
# ---------------------------------------------------------------------------


def test_web_patch_rejects_invalid_enums_dates_and_syncs_project_id(tmp_path: Path) -> None:
    """PATCH /api/items/{id} 必须拦截非法枚举/日期/倒挂日期，并在修改 project_name 时同步更新 project_id。"""
    eng, db, _, od = _make_engine(tmp_path, lambda *_: "{}")
    try:
        app = create_app(
            settings=eng.settings,
            db=db,
            engine=eng,
            onedrive=od,
            start_background_tasks=False,
        )
        with TestClient(app) as client:
            tok = app.state.auth.mint_magic_token(300)
            assert client.get(f"/auth/magic?token={tok}", follow_redirects=False).status_code == 302

            created = client.post(
                "/api/items",
                json={
                    "title": "核对测试交付清单",
                    "list_type": "project_action",
                    "work_domain": "项目交付",
                    "project_name": "帕莫瑞一期",
                    "planned_start_at": "2026-11-24",
                    "planned_end_at": "2026-11-28",
                    "estimated_hours": 2.0,
                    "priority": "P1",
                },
            )
            assert created.status_code == 200
            item_id = created.json()["created_ids"][0]

            # 非法状态、非法清单类型、非法日期、开始晚于结束 -> 全部 422
            bad_payloads = [
                {"status": "hacked"},
                {"list_type": "invalid"},
                {"planned_start_at": "not-a-date"},
                {"planned_start_at": "2026-11-28", "planned_end_at": "2026-11-24"},
            ]
            for payload in bad_payloads:
                resp = client.patch(f"/api/items/{item_id}", json=payload)
                assert resp.status_code == 422, f"非法更新载荷 {payload} 必须返回 422，实际 {resp.status_code}"

            # 修改项目名必须自动同步关联到 projects 表中对应新项目的真实 id
            rename_resp = client.patch(f"/api/items/{item_id}", json={"project_name": "帕莫瑞二期"})
            assert rename_resp.status_code == 200

            projects = {p["name"]: p for p in db.list_projects()}
            assert "帕莫瑞二期" in projects, "改项目名后必须在 projects 表中存在「帕莫瑞二期」"
            updated_item = next(it for it in db.list_items() if it["id"] == item_id)
            assert updated_item["project_name"] == "帕莫瑞二期"
            assert updated_item["project_id"] == projects["帕莫瑞二期"]["id"], "project_id 必须与新项目同步，不得与旧项目 id 撕裂"
    finally:
        eng.close()


def test_web_promote_requires_idea_and_allows_zero_estimated_hours(tmp_path: Path) -> None:
    """POST /api/items/{id}/promote 仅允许对 idea 执行，且允许 estimated_hours=0.0 升格为 project_action。"""
    eng, db, _, od = _make_engine(tmp_path, lambda *_: "{}")
    try:
        app = create_app(
            settings=eng.settings,
            db=db,
            engine=eng,
            onedrive=od,
            start_background_tasks=False,
        )
        with TestClient(app) as client:
            tok = app.state.auth.mint_magic_token(300)
            assert client.get(f"/auth/magic?token={tok}", follow_redirects=False).status_code == 302

            na_resp = client.post(
                "/api/items",
                json={
                    "title": "普通下一步行动",
                    "list_type": "next_action",
                    "work_domain": "产品研发",
                    "project_name": "通用待办",
                },
            )
            idea_resp = client.post(
                "/api/items",
                json={
                    "title": "边缘检测新方案构想",
                    "list_type": "idea",
                    "work_domain": "产品研发",
                    "project_name": "个人思考",
                },
            )
            na_id = na_resp.json()["created_ids"][0]
            idea_id = idea_resp.json()["created_ids"][0]

            # 对非 idea 项调 promote 必须返回 400 且不改原项
            bad_prom = client.post(
                f"/api/items/{na_id}/promote",
                json={
                    "project_name": "不应改动的项目",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "2026-11-30",
                    "estimated_hours": 1.0,
                },
            )
            assert bad_prom.status_code == 400
            na_item = next(it for it in db.list_items() if it["id"] == na_id)
            assert na_item["list_type"] == "next_action"
            assert na_item["project_name"] == "通用待办"

            # 对 idea 项传 estimated_hours=0.0 必须允许成功升格
            ok_prom = client.post(
                f"/api/items/{idea_id}/promote",
                json={
                    "project_name": "边缘检测一期",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "2026-12-05",
                    "estimated_hours": 0.0,
                },
            )
            assert ok_prom.status_code == 200
            promoted = next(it for it in db.list_items() if it["id"] == idea_id)
            assert promoted["list_type"] == "project_action"
            assert promoted["project_name"] == "边缘检测一期"
            assert promoted["estimated_hours"] == 0.0
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 4. 确认卡落盘顺序（先本地原子提交，后云端归档）与重复确认 CAS 防重（AUD-P0-4a）
# ---------------------------------------------------------------------------


def test_commit_preserves_local_file_when_sqlite_commit_fails_and_blocks_double_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(a) 本地 SQLite 原子提交失败时不得提前上传或删除本地附件；(b) 同一待确认卡重复提交必须 CAS 拦截防翻倍。"""
    # --- 子场景 (a): 先本地原子提交，后云端归档清理 ---
    eng_a, db_a, _, od_a = _make_engine(tmp_path / "fail_first", lambda *_: "{}")
    try:
        local_att = tmp_path / "quote_v3.pdf"
        local_att.write_bytes(b"%PDF-1.4 fake content")

        db_a.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([_action_dict(title="归档报价文件")]),
            source_ids=[],
            pending_files=[{"path": str(local_att), "filename": "quote_v3.pdf", "size": local_att.stat().st_size}],
        )
        pending_a = db_a.get_latest_pending_proposal("owner")
        assert pending_a is not None

        def _boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("disk full")

        monkeypatch.setattr(db_a, "apply_proposal_atomic", _boom)

        with pytest.raises(RuntimeError, match="disk full"):
            eng_a.commit_pending_proposal(pending_a)

        assert local_att.exists(), "本地数据库落盘失败时，临时附件绝不可被提前删除"
        assert od_a.cleanup_upload_calls == 0, "本地数据库落盘失败时，绝不可先调用 OneDrive 上传并删文件"
    finally:
        eng_a.close()

    # --- 子场景 (b): 重复提交同一 pending 字典必须拦截且不翻倍 ---
    eng_b, db_b, _, _ = _make_engine(tmp_path / "double_commit", lambda *_: "{}")
    try:
        db_b.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([_action_dict(title="幂等落盘唯一任务")]),
            source_ids=[],
        )
        pending_b = db_b.get_latest_pending_proposal("owner")
        assert pending_b is not None

        first_reply = eng_b.commit_pending_proposal(pending_b)
        assert first_reply
        assert len(db_b.list_items()) == 1

        second_reply = eng_b.commit_pending_proposal(pending_b)
        assert second_reply
        assert any(kw in second_reply for kw in ("已确认", "已处理", "重复", "失效", "不存在"))
        assert len(db_b.list_items()) == 1, "重复确认同一卡片绝不可造成 list_items 翻倍写入"
    finally:
        eng_b.close()


# ---------------------------------------------------------------------------
# 5. 无想法卡回 `2` 不死锁 & 空动作保护（AUD-P0-4b）
# ---------------------------------------------------------------------------


def test_no_idea_card_reply_two_and_empty_actions_handled_safely(tmp_path: Path) -> None:
    """无想法卡回 2 不落盘且提示可回 1/0 随后可正常作废；空 actions=[] 卡片回 1 自动关闭不阻塞。"""
    eng, db, _, _ = _make_engine(tmp_path, lambda *_: "{}")
    try:
        # 场景 A: 仅含 project_action，无 idea
        db.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([_action_dict(title="纯项目交付任务", list_type="project_action")]),
            source_ids=[],
        )
        r2 = eng.handle_incoming_turn("2")
        assert len(db.list_items()) == 0
        assert any(kw in r2["reply_text"] for kw in ("无想法", "没有想法", "不含想法", "0 条想法"))
        assert "1" in r2["reply_text"] and "0" in r2["reply_text"]
        assert db.get_latest_pending_proposal("owner") is not None

        # 随后回 0 顺利作废
        r0 = eng.handle_incoming_turn("0")
        assert r0["reply_text"]
        assert db.get_latest_pending_proposal("owner") is None

        # 场景 B: 异常产生的 actions=[] 空卡片回 1，必须自动关闭/取消避免死锁
        db.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([], headline="空动作异常卡"),
            source_ids=[],
        )
        r1 = eng.handle_incoming_turn("1")
        assert r1["reply_text"]
        assert db.get_latest_pending_proposal("owner") is None, "空动作卡片回 1 后必须自动关闭，不得永久阻塞后续流程"
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 6. 附件下载路径穿越净化 + ZIP 同前缀穿越与流式解压体积拦截（AUD-P0-5a）
# ---------------------------------------------------------------------------


def test_wecom_download_sanitizes_path_traversal_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """企微 media/get 返回含 ../../ 路径穿越的 Content-Disposition 文件名时，必须净化并严格落在 tmp_dir 内。"""
    settings = _make_settings(tmp_path)

    async def noop_proc(*_args: Any) -> str:
        return "ok"

    gw = WeComGateway(settings, turn_processor=noop_proc)

    async def fake_token() -> str:
        return "fake_wecom_token"

    monkeypatch.setattr(gw, "get_access_token", fake_token)

    class _FakeResp:
        status_code = 200
        content = b"safe body bytes"
        headers = {
            "content-type": "application/octet-stream",
            "content-disposition": 'attachment; filename="../../etc/evil.txt"',
        }

        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResp:
            return _FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    att = asyncio.run(gw._download_media("media_traversal_1"))
    assert att is not None
    saved = Path(att["path"]).resolve()
    assert saved.is_relative_to(gw.tmp_dir.resolve()), f"保存路径越界: {saved} 不在 {gw.tmp_dir.resolve()} 内"
    assert att["filename"] == "evil.txt"
    assert saved.exists()


def test_zip_extractor_blocks_sibling_prefix_traversal_and_streaming_oversize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ZIP 解压必须阻断路径穿越逃逸，并通过真实流式字节计数拦截解压体积超限（含伪造 ZipInfo.file_size 炸弹）。"""
    # 场景 A: 恶意 ../escape.txt 路径穿越 ZIP
    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../escape.txt", "should never escape")
        zf.writestr("safe.txt", "normal text inside zip")

    pages_evil = extract_document_pages(evil_zip)
    assert isinstance(pages_evil, list)
    assert not (tmp_path / "escape.txt").exists()
    combined_evil = "\n".join(str(p.get("text", "")) for p in pages_evil)
    assert "should never escape" not in combined_evil

    # 场景 B: 流式体积超限拦截（含伪造 ZipInfo.file_size 绕过头部检查）
    big_zip = tmp_path / "oversize.zip"
    with zipfile.ZipFile(big_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", "A" * 4096)

    monkeypatch.setattr(extractors, "_MAX_ZIP_UNCOMPRESSED_BYTES", 1024)

    # 先验证真实 4KB > 1KB 被拦截
    pages_over = extract_document_pages(big_zip)
    text_over = "\n".join(str(p.get("text", "")) for p in pages_over)
    assert "超限" in text_over

    # 再伪造 ZipInfo.file_size = 10（但真实解压流仍为 4096 字节），逼迫实现层必须通过流式字节计数拦截
    orig_infolist = zipfile.ZipFile.infolist
    orig_open = zipfile.ZipFile.open

    def _spoofed_infolist(self: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        spoofed: list[zipfile.ZipInfo] = []
        for info in orig_infolist(self):
            cloned = copy.copy(info)
            cloned.file_size = 10
            spoofed.append(cloned)
        return spoofed

    def _real_stream_open(
        self: zipfile.ZipFile,
        name: str | zipfile.ZipInfo,
        mode: str = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> Any:
        target = name.filename if isinstance(name, zipfile.ZipInfo) else name
        return orig_open(self, target, mode=mode, pwd=pwd, force_zip64=force_zip64)

    monkeypatch.setattr(zipfile.ZipFile, "infolist", _spoofed_infolist)
    monkeypatch.setattr(zipfile.ZipFile, "open", _real_stream_open)
    pages_spoofed = extract_document_pages(big_zip)
    text_spoofed = "\n".join(str(p.get("text", "")) for p in pages_spoofed)
    assert "超限" in text_spoofed, "伪造 ZipInfo.file_size 时仍必须通过流式字节计数拦截并返回体积超限提示"
    assert ("A" * 2048) not in text_spoofed


# ---------------------------------------------------------------------------
# 7. tmp_cache 临时文件作废与清理（AUD-P0-5b）
# ---------------------------------------------------------------------------


def test_discard_pending_card_cleans_up_tmp_attachments(tmp_path: Path) -> None:
    """带本地临时附件的待确认卡回复 0 作废后，磁盘上的临时附件必须自动删除。"""
    eng, db, _, _ = _make_engine(tmp_path, lambda *_: "{}")
    try:
        tmp_cache_dir = tmp_path / "tmp_cache"
        tmp_cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_att = tmp_cache_dir / "discard_me.xlsx"
        tmp_att.write_bytes(b"temporary attachment payload")

        db.save_pending_proposal(
            thread_id="owner",
            proposal_dict=_proposal_dict_with_actions([_action_dict(title="待作废附件任务")]),
            source_ids=[],
            pending_files=[{"path": str(tmp_att), "filename": "discard_me.xlsx", "size": tmp_att.stat().st_size}],
        )
        res = eng.handle_incoming_turn("0")
        assert res["reply_text"]
        assert db.get_latest_pending_proposal("owner") is None
        assert not tmp_att.exists(), "待确认卡回复 0 作废后，对应的本地临时附件文件必须自动清理"
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 8. 批量打卡部分/全无效 ID 回报 + `完成 1.5h` 防错杀 `#1` + 重复完成幂等（AUD-P0-6）
# ---------------------------------------------------------------------------


def test_batch_checkin_reports_missing_ids_and_prevents_hours_misparse(tmp_path: Path) -> None:
    """批量打卡须准确回报无效 ID；无编号的「完成 1.5h」绝不可误杀 #1；重复 complete_item 不重复写 span_baseline。"""

    def handler(kwargs: dict[str, Any], _idx: int) -> str:
        return json.dumps({
            "intent": "checkin",
            "confidence": 0.95,
            "target_item_id": None,
            "actual_hours": 1.5,
            "summary": "完成 1.5h 但未提供编号",
        })

    eng, db, _, _ = _make_engine(tmp_path, handler)
    try:
        db.apply_proposal_atomic(
            proposal_id=None,
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="测试项目",
                    title="任务一号",
                    planned_start_at="2026-11-24",
                    planned_end_at="2026-11-26",
                    estimated_hours=2.0,
                ),
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="测试项目",
                    title="任务二号",
                    planned_start_at="2026-11-24",
                    planned_end_at="2026-11-26",
                    estimated_hours=2.0,
                ),
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="测试项目",
                    title="任务三号",
                    planned_start_at="2026-11-24",
                    planned_end_at="2026-11-26",
                    estimated_hours=2.0,
                ),
            ],
            source_ids=[],
            doc_paths=[],
        )

        # (1) 部分有效 + 部分无效
        r_partial = eng.handle_incoming_turn("#1 做完了，#999 开始了")
        assert "#1" in r_partial["reply_text"]
        assert "#999" in r_partial["reply_text"]
        assert any(kw in r_partial["reply_text"] for kw in ("未找到", "不存在", "找不到"))
        item1 = next(it for it in db.list_items() if it["id"] == 1)
        assert item1["status"] == "done"

        # (2) 全无效 ID
        r_missing = eng.handle_incoming_turn("#998 做完了，#999 开始了")
        assert "#998" in r_missing["reply_text"]
        assert "#999" in r_missing["reply_text"]
        assert any(kw in r_missing["reply_text"] for kw in ("未找到", "不存在", "找不到"))

        # (3) 路由到 checkin 但原文仅「完成 1.5h」（无编号，target_item_id=None）
        # 先把 #1 保持 done，确保 #2/#3 保持 todo，同时验证不会误把 1.5h 里的 1 当成 #1 执行完成
        r_no_id = eng.handle_incoming_turn("完成 1.5h")
        assert any(kw in r_no_id["reply_text"] for kw in ("编号", "#", "哪一条", "哪项"))
        assert "已完成 #1" not in r_no_id["reply_text"]
        items_by_id = {it["id"]: it for it in db.list_items()}
        assert items_by_id[2]["status"] == "todo"
        assert items_by_id[3]["status"] == "todo"

        # (4) 对已完成的 #1 再次 complete_item，绝不可向 memory_rules 重复写入第二条 span_baseline
        baselines_before = [r for r in db.list_memory_rules() if r["memory_kind"] == "span_baseline"]
        db.complete_item(1, actual_hours=1.5)
        baselines_after = [r for r in db.list_memory_rules() if r["memory_kind"] == "span_baseline"]
        assert len(baselines_after) == len(baselines_before), "重复完成同一任务绝不可重复写入 span_baseline 规则"
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 9. 企微自建应用单人白名单与定向推送（AUD-P1-1）
# ---------------------------------------------------------------------------


def test_wecom_app_owner_whitelist_blocks_stranger_and_targets_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置 wecom_app_owner_userid 时，陌生人消息静默拦截，推送定向发给老板；留空时兼容 @all。"""
    monkeypatch.setenv("SEGMENT_QUIET_SECONDS", "0.05")
    owner_settings = _make_settings(tmp_path / "owner", wecom_app_owner_userid="JohnXu")

    turns: list[tuple[str, str]] = []
    acks: list[str] = []

    async def proc(text: str, sender: str, atts: list[dict[str, Any]], msgid: str) -> str:
        turns.append((text, sender))
        return "ok"

    gw_owner = WeComGateway(owner_settings, turn_processor=proc)

    async def fake_push_record(content: str) -> dict[str, Any]:
        acks.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(gw_owner, "send_app_push", fake_push_record)

    async def run_whitelist() -> None:
        await gw_owner.handle_callback_event({
            "MsgType": "text",
            "Content": "套取公司机密",
            "FromUserName": "Stranger",
            "MsgId": "m_stranger_1",
        })
        await asyncio.sleep(0.12)

    asyncio.run(run_whitelist())
    assert len(turns) == 0, "非白名单成员发来的自建应用消息必须静默拦截，不得调用 turn_processor"
    assert len(acks) == 0, "非白名单成员消息不得发出到达回执"

    # 测试真实 send_app_push 的 touser 目标字段
    captured_payloads: list[dict[str, Any]] = []

    class _FakePostResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"errcode": 0, "errmsg": "ok"}

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> _FakePostResp:
            if json is not None:
                captured_payloads.append(json)
            return _FakePostResp()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    gw_targeted = WeComGateway(owner_settings, turn_processor=proc)
    gw_broadcast = WeComGateway(_make_settings(tmp_path / "all", wecom_app_owner_userid=""), turn_processor=proc)

    async def fake_tok() -> str:
        return "tok_valid"

    monkeypatch.setattr(gw_targeted, "get_access_token", fake_tok)
    monkeypatch.setattr(gw_broadcast, "get_access_token", fake_tok)

    asyncio.run(gw_targeted.send_app_push("hello owner"))
    asyncio.run(gw_broadcast.send_app_push("hello all"))

    assert captured_payloads[0]["touser"] == "JohnXu"
    assert captured_payloads[1]["touser"] == "@all"


# ---------------------------------------------------------------------------
# 10. send_app_push 检查 errcode 并在 token 过期时自动刷新重试（AUD-P1-2）
# ---------------------------------------------------------------------------


def test_send_app_push_refreshes_expired_token_and_raises_on_persistent_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """send_app_push 遇 errcode=42001 自动刷新 token 重试；遇持续性业务错误码必须抛出 RuntimeError。"""
    settings = _make_settings(tmp_path)

    async def noop_proc(*_args: Any) -> str:
        return "ok"

    gw = WeComGateway(settings, turn_processor=noop_proc)

    state = {"gettoken_calls": 0, "send_calls": 0, "mode": "expire_once"}

    class _FakeResp:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._data

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResp:
            if "gettoken" in url:
                state["gettoken_calls"] += 1
                return _FakeResp({
                    "errcode": 0,
                    "access_token": f"tok_{state['gettoken_calls']}",
                    "expires_in": 7200,
                })
            raise AssertionError(f"Unexpected GET {url}")

        async def post(
            self,
            url: str,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> _FakeResp:
            state["send_calls"] += 1
            if state["mode"] == "expire_once":
                if state["send_calls"] == 1:
                    return _FakeResp({"errcode": 42001, "errmsg": "access_token expired"})
                return _FakeResp({"errcode": 0, "errmsg": "ok"})
            return _FakeResp({"errcode": 60020, "errmsg": "not allow to access from your ip"})

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    # 场景 A: 首次 42001 -> 自动清缓存重取 token -> 第二次成功
    res = asyncio.run(gw.send_app_push("第一条消息"))
    assert res.get("errcode") == 0
    assert state["gettoken_calls"] == 2
    assert state["send_calls"] == 2

    # 场景 B: 持续性错误码 60020 必须抛出 RuntimeError，绝不可静默当成功
    state["mode"] = "persistent_error"
    with pytest.raises(RuntimeError):
        asyncio.run(gw.send_app_push("应当失败的消息"))


# ---------------------------------------------------------------------------
# 11. SQLite 零连接泄漏（ResourceWarning）+ 损坏 JSON 容错（AUD-P1-3）
# ---------------------------------------------------------------------------


def test_database_zero_unclosed_connection_warnings_and_corrupt_json_resilience(tmp_path: Path) -> None:
    """Database 所有常规读写操作不得泄漏未关闭 SQLite 连接；字段 JSON 损坏时须降级为空列表不崩溃。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        db = Database(tmp_path / "app.db")
        db.insert_raw_source(
            source_type="wecom",
            external_msg_id="ext_res_1",
            sender="owner",
            title="连接泄漏检测文档",
            raw_text="测试内容 12345",
        )
        _ = db.search_sources("检测文档")
        db.append_conversation_turn(thread_id="owner", role="user", content="你好", topic_tags=["测试"])
        _ = db.list_items()
        gc.collect()

    res_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert len(res_warnings) == 0, f"检测到未关闭数据库连接警告: {[str(w.message) for w in res_warnings]}"

    # 损坏 JSON 容错测试
    db.save_pending_proposal(
        thread_id="owner",
        proposal_dict=_proposal_dict_with_actions([_action_dict(title="容错卡片")]),
        source_ids=[1],
    )
    conn = sqlite3.connect(tmp_path / "app.db")
    try:
        conn.execute("UPDATE conversation_turns SET topic_tags_json = '{broken'")
        conn.execute("UPDATE pending_proposals SET source_ids_json = '{broken'")
        conn.commit()
    finally:
        conn.close()

    turns = db.get_turns_since(thread_id="owner", after_id=0)
    assert len(turns) >= 1
    assert turns[0]["topic_tags"] == []

    pending = db.get_latest_pending_proposal(thread_id="owner")
    assert pending is not None
    assert pending["source_ids"] == []


# ---------------------------------------------------------------------------
# 12. 确定性审计拦截非法/倒挂日期 + 异构 Critic 收到对话上下文（AUD-P1-4）
# ---------------------------------------------------------------------------


def test_deterministic_critic_rejects_invalid_or_reversed_dates_and_llm_critic_gets_dialogue(
    tmp_path: Path,
) -> None:
    """deterministic_critic_check 必须拦截倒挂/非法日期；work_triage 异构 Critic 必须收到历史对话上下文。"""
    # (a) 倒挂日期: start > end
    reversed_prop = TriageProposal(
        headline="倒挂日期提案",
        executive_summary="安排项目交付测试",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞",
                title="倒挂排期任务",
                planned_start_at="2026-11-28",
                planned_end_at="2026-11-24",
                estimated_hours=1.0,
            )
        ],
    )
    rev_issues = deterministic_critic_check(
        reversed_prop, raw_input="下周安排任务", evidence_text="", tool_outputs_text=""
    )
    assert len(rev_issues) > 0, "开始日期晚于结束日期时 deterministic_critic_check 必须报出问题"

    # (b) 非法日历日期: 2026-02-30
    invalid_date_prop = TriageProposal(
        headline="非法日期提案",
        executive_summary="安排项目交付测试",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞",
                title="非法日期任务",
                planned_start_at="2026-02-30",
                planned_end_at="2026-03-02",
                estimated_hours=1.0,
            )
        ],
    )
    inv_issues = deterministic_critic_check(
        invalid_date_prop, raw_input="二月底安排任务", evidence_text="", tool_outputs_text=""
    )
    assert len(inv_issues) > 0, "非法日历日期 2026-02-30 时 deterministic_critic_check 必须报出问题"

    # (c) 异构 Critic 收到历史对话上下文中的关键数字 38500
    def handler(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model == "qwen3.8-flash":
            return json.dumps({"intent": "work_triage", "confidence": 0.96, "summary": "跟进帕莫瑞报价"})
        if model == "qwen3.8-max":
            return json.dumps({
                "headline": "帕莫瑞报价跟进",
                "executive_summary": "按历史沟通的 38500 元基准跟进最终报价。",
                "actions": [_action_dict(title="确认帕莫瑞报价单", project_name="帕莫瑞")],
                "referenced_numbers": ["38500"],
                "citations": [],
            })
        return json.dumps({
            "passed": True,
            "numeric_fidelity_ok": True,
            "schedule_reasonable": True,
            "issues": [],
            "fix_instructions": "",
        })

    eng, db, completions, _ = _make_engine(tmp_path, handler)
    try:
        db.append_conversation_turn(
            thread_id="owner",
            role="user",
            content="帕莫瑞项目客户上次口头确认的预算基准是 38500 元。",
            intent="conversational_chat",
        )
        res = eng.handle_incoming_turn("按前面说的报价给帕莫瑞安排跟进任务")
        assert res["reply_text"]

        critic_calls = [c for c in completions.calls if c["model"] == "deepseek-v4-pro"]
        assert len(critic_calls) >= 1, "work_triage 流程必须调用异构 critic_model (deepseek-v4-pro)"
        critic_payload = "\n".join(str(m.get("content", "")) for m in critic_calls[-1]["messages"])
        assert "38500" in critic_payload, "发给异构 Critic 的上下文必须包含历史对话中的关键数字 38500"
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 13. undo_last_commit 保护跨批次项目 & 超过 24 小时拒绝撤销（AUD-P1-5）
# ---------------------------------------------------------------------------


def test_undo_protects_shared_project_and_enforces_24h_window(tmp_path: Path) -> None:
    """撤销上一批次时不得删除仍有其他任务的共享项目；超过 24 小时的快照必须拒绝撤销。"""
    # (a) 保护跨批次共享项目
    db_a = Database(tmp_path / "undo_a.db")
    db_a.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞",
                title="批次1任务",
                planned_start_at="2026-11-24",
                planned_end_at="2026-11-26",
                estimated_hours=1.0,
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    proj = next(p for p in db_a.list_projects() if p["name"] == "帕莫瑞")
    proj_id = proj["id"]

    # 直接向同一项目插入跨批次任务 #2（不覆盖 undo_snapshots 中的批次 1 快照）
    conn = sqlite3.connect(tmp_path / "undo_a.db")
    try:
        now_iso = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO list_items
            (list_type, project_id, project_name, work_domain, title, owner,
             planned_start_at, planned_end_at, estimated_hours, priority, status, stage, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "project_action",
                proj_id,
                "帕莫瑞",
                "项目交付",
                "跨批次任务2",
                "本人",
                "2026-11-25",
                "2026-11-28",
                1.0,
                "P1",
                "todo",
                "待执行",
                now_iso,
                now_iso,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    ok, _msg = db_a.undo_last_commit()
    assert ok is True
    remaining_items = db_a.list_items()
    assert all(it["title"] != "批次1任务" for it in remaining_items)
    item2 = next(it for it in remaining_items if it["title"] == "跨批次任务2")
    assert item2["project_id"] == proj_id, "跨批次任务 #2 的 project_id 不得因撤销批次 1 而被置空"
    assert any(p["name"] == "帕莫瑞" for p in db_a.list_projects()), "仍有其他任务归属的项目「帕莫瑞」绝不可被删除"

    # (b) 超过 24 小时拒绝撤销
    db_b = Database(tmp_path / "undo_b.db")
    db_b.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.NEXT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="过期撤销测试",
                title="25小时前的任务",
                planned_start_at="2026-11-23",
                planned_end_at="2026-11-25",
                estimated_hours=1.0,
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    old_ts = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
    conn2 = sqlite3.connect(tmp_path / "undo_b.db")
    try:
        conn2.execute("UPDATE undo_snapshots SET created_at = ?", (old_ts,))
        conn2.commit()
    finally:
        conn2.close()

    ok_old, _msg_old = db_b.undo_last_commit(max_age_hours=24)
    assert ok_old is False, "超过 24 小时的撤销快照必须拒绝撤销"
    assert len(db_b.list_items()) == 1


# ---------------------------------------------------------------------------
# 14. 企微单发「好了」不吞消息 + 合并转发语音转写 + 客服异常走客服回执 + 空输入短路（AUD-P1-6）
# ---------------------------------------------------------------------------


def test_wecom_standalone_haole_not_swallowed_and_merged_voice_asr_and_kf_error_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单发「好了」不吞消息；merged_msg 语音子项须走 ASR；客服异常优先回发客服通道；空白输入 0 LLM 短路。"""
    # 1) QuietAggregator 无待合批时单发「好了」必须正常 flush
    flushed: list[tuple[str, str]] = []

    async def on_flush(sender_key: str, text: str, atts: list[dict[str, Any]], msg_id: str) -> None:
        flushed.append((sender_key, text))

    async def run_aggregator() -> None:
        agg = QuietAggregator(quiet_seconds=0.05, on_flush=on_flush)
        await agg.push("app|JohnXu", text="好了", msg_id="m_haole")
        await asyncio.sleep(0.15)

    asyncio.run(run_aggregator())
    assert len(flushed) == 1, "无待合批消息时单发「好了」绝不可被吞掉"
    assert "好了" in flushed[0][1]

    # 2) merged_msg 内 voice 子项触发 _transcribe_audio_dashscope 并拼进结果文本
    settings = _make_settings(tmp_path)
    kf_sends: list[dict[str, Any]] = []
    app_pushes: list[str] = []
    asr_calls: list[str] = []

    async def failing_proc(text: str, sender: str, atts: list[dict[str, Any]], msg_id: str) -> str:
        raise RuntimeError("simulated turn failure")

    gw = WeComGateway(settings, turn_processor=failing_proc)
    audio_file = tmp_path / "voice_sub.amr"
    audio_file.write_bytes(b"#!AMR\nfakeaudio")

    async def fake_download(media_id: str, fallback_ext: str = ".bin", explicit_filename: str = "") -> dict[str, Any]:
        return {"filename": explicit_filename or f"{media_id}{fallback_ext}", "path": str(audio_file), "size": 16}

    async def fake_asr(local_path: str | Path) -> str:
        asr_calls.append(str(local_path))
        return "客户确认周三签合同"

    async def fake_send_kf(*, touser: str, open_kfid: str, content: str) -> None:
        kf_sends.append({"touser": touser, "open_kfid": open_kfid, "content": content})

    async def fake_app_push(content: str) -> dict[str, Any]:
        app_pushes.append(content)
        return {"errcode": 0}

    monkeypatch.setattr(gw, "_download_media", fake_download)
    monkeypatch.setattr(gw, "_transcribe_audio_dashscope", fake_asr)
    monkeypatch.setattr(gw, "send_kf_text", fake_send_kf)
    monkeypatch.setattr(gw, "send_app_push", fake_app_push)

    parsed_text, _parsed_atts = asyncio.run(
        gw._parse_kf_message({
            "msgtype": "merged_msg",
            "merged_msg": {
                "title": "群聊语音纪要",
                "item": [
                    {
                        "sender_name": "李总",
                        "send_time": 1700000100,
                        "msgtype": "voice",
                        "msg_content": json.dumps({"voice": {"media_id": "voice_mid_01"}}),
                    }
                ],
            },
        })
    )
    assert len(asr_calls) >= 1, "merged_msg 中的 voice 子项必须调用 _transcribe_audio_dashscope"
    assert "客户确认周三签合同" in parsed_text

    # 3) 客服通道 turn_processor 抛异常 -> 优先发 send_kf_text，而非 send_app_push
    asyncio.run(gw._handle_flushed_kf_batch("wm_ext_user_99|wk_open_kf_01", "测试客服消息", [], "m_kf_err"))
    assert len(kf_sends) >= 1, "客服通道异常兜底回复应发往 send_kf_text"
    assert len(app_pushes) == 0, "客服通道异常兜底回复不应越界推送到自建应用通道"

    # 4) 空白无附件输入直接短路返回引导提示，0 次 LLM 调用
    eng, db, completions, _ = _make_engine(tmp_path / "blank", lambda *_: "{}")
    try:
        blank_res = eng.handle_incoming_turn("   \n  ")
        assert blank_res["reply_text"].strip() != ""
        assert len(completions.calls) == 0, "空白且无附件输入必须短路返回引导，0 次大模型调用"
        assert db.count_model_calls() == 0
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 15. 超界工作日防卡死 + LIKE 百分号转义 + 企微 HTTP 回调验签路由 + Web 完整鉴权 CRUD 闭环（AUD-P2-1/2/3）
# ---------------------------------------------------------------------------


def test_calc_business_date_rejects_huge_offset_and_search_escapes_percent(tmp_path: Path) -> None:
    """calc_business_date 拒绝超大偏移防 CPU 卡死；search_sources 对 LIKE 中的 % 正确转义。"""
    with pytest.raises(ValueError):
        calc_business_date("2026-11-24", 10_000_000)

    db = Database(tmp_path / "search.db")
    db.insert_raw_source(
        source_type="wecom",
        external_msg_id="s_pct",
        sender="owner",
        title="折扣政策",
        raw_text="阶梯返点最高支持 100% 抵扣货款",
    )
    db.insert_raw_source(
        source_type="wecom",
        external_msg_id="s_other",
        sender="owner",
        title="发货清单",
        raw_text="本批出厂传感器合计 100台 已装车",
    )

    hits = db.search_sources("100%")
    hit_titles = [h["title"] for h in hits]
    assert "折扣政策" in hit_titles
    assert "发货清单" not in hit_titles, "查询 100% 时不得把 % 当作 SQL LIKE 通配符误命中「100台」"


def test_wecom_http_callback_signature_and_web_full_auth_crud_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证企微 HTTP 回调 GET/POST 验签与解密，以及 Web 驾驶舱从验证码限流登录到 CRUD 登出全闭环。"""
    eng, db, _, od = _make_engine(tmp_path, lambda *_: "{}")
    try:
        async def noop_proc(*_args: Any) -> str:
            return "ok"

        wc_gw = WeComGateway(eng.settings, turn_processor=noop_proc)
        pushed_messages: list[str] = []

        async def fake_push(content: str) -> dict[str, Any]:
            pushed_messages.append(content)
            return {"errcode": 0}

        monkeypatch.setattr(wc_gw, "send_app_push", fake_push)

        app = create_app(
            settings=eng.settings,
            db=db,
            engine=eng,
            gateway=wc_gw,
            onedrive=od,
            start_background_tasks=False,
        )

        with TestClient(app) as client:
            # --- 企微 HTTP 回调验签 ---
            ts = "1732440000"
            nonce = "nonce123"
            cipher_echo = _encrypt_wecom_payload(
                eng.settings.wecom_app_aes_key,
                "echo_plain_ok",
                eng.settings.wecom_corp_id,
            )
            good_sig = compute_signature(eng.settings.wecom_app_token, ts, nonce, cipher_echo)

            bad_get = client.get(
                "/api/wecom/app/callback",
                params={"msg_signature": "bad_sig", "timestamp": ts, "nonce": nonce, "echostr": cipher_echo},
            )
            assert bad_get.status_code == 403

            ok_get = client.get(
                "/api/wecom/app/callback",
                params={"msg_signature": good_sig, "timestamp": ts, "nonce": nonce, "echostr": cipher_echo},
            )
            assert ok_get.status_code == 200
            assert ok_get.text == "echo_plain_ok"

            bad_post = client.post(
                "/api/wecom/app/callback",
                params={"msg_signature": "bad_sig", "timestamp": ts, "nonce": nonce},
                content=f"<xml><Encrypt><![CDATA[{cipher_echo}]]></Encrypt></xml>".encode("utf-8"),
            )
            assert bad_post.status_code == 403

            # --- Web 完整鉴权与 CRUD 闭环 ---
            assert client.get("/api/dashboard/overview").status_code == 401

            # request-code 连发 6 次 -> 第 6 次 429
            for i in range(5):
                rc = client.post("/api/auth/request-code")
                assert rc.status_code == 200, f"第 {i + 1} 次请求验证码应成功"
            rc6 = client.post("/api/auth/request-code")
            assert rc6.status_code == 429

            # 从最后一次企微推送文本中取出 6 位验证码登录
            assert len(pushed_messages) == 5
            m = re.search(r"\b(\d{6})\b", pushed_messages[-1])
            assert m is not None, f"推送文本未包含 6 位验证码: {pushed_messages[-1]}"
            code = m.group(1)

            v_resp = client.post("/api/auth/verify-code", json={"code": code})
            assert v_resp.status_code == 200
            assert COOKIE_NAME in v_resp.cookies

            # 创建 -> 开始 -> 完成 -> 删除 -> 登出 -> 再访 401
            c_resp = client.post(
                "/api/items",
                json={
                    "title": "全链路闭环测试任务",
                    "list_type": "project_action",
                    "work_domain": "项目交付",
                    "project_name": "闭环项目",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "2026-11-28",
                    "estimated_hours": 2.0,
                    "priority": "P0",
                },
            )
            assert c_resp.status_code == 200
            item_id = c_resp.json()["created_ids"][0]

            s_resp = client.post(f"/api/items/{item_id}/start")
            assert s_resp.status_code == 200
            assert s_resp.json()["item"]["status"] == "in_progress"

            done_resp = client.post(f"/api/items/{item_id}/complete", json={"actual_hours": 1.5})
            assert done_resp.status_code == 200
            assert done_resp.json()["item"]["status"] == "done"

            del_resp = client.delete(f"/api/items/{item_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["deleted"] is True

            out_resp = client.post("/api/auth/logout")
            assert out_resp.status_code == 200

            assert client.get("/api/dashboard/overview").status_code == 401
    finally:
        eng.close()


# ---------------------------------------------------------------------------
# 16. OneDrive 真实客户端上传与纪要追加单测
# ---------------------------------------------------------------------------


def test_onedrive_client_put_chunked_upload_and_append_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 OneDrive21VianetClient 小文件 PUT、大文件分片上传、返回 size 不匹配拦截及项目纪要追加。"""
    settings = _make_settings(tmp_path)
    od = OneDrive21VianetClient(settings)
    monkeypatch.setattr(od, "_get_token", lambda: "fake_ms_token")

    recorded: list[dict[str, Any]] = []
    scenario: dict[str, Any] = {
        "put_return_size": None,
        "existing_note": "# 帕莫瑞\n\n## 2026-11-20\n- 旧会议纪要\n".encode("utf-8"),
    }

    class _FakeResp:
        def __init__(self, *, status_code: int = 200, content: bytes = b"", json_data: dict[str, Any] | None = None) -> None:
            self.status_code = status_code
            self.content = content
            self.text = content.decode("utf-8", errors="replace")
            self._json = json_data or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]

        def json(self) -> dict[str, Any]:
            return self._json

    class _FakeHttpClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_FakeHttpClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str, headers: dict[str, str] | None = None) -> _FakeResp:
            recorded.append({"method": "GET", "url": url, "headers": headers or {}})
            return _FakeResp(status_code=200, content=scenario["existing_note"])

        def post(self, url: str, headers: dict[str, str] | None = None, json: dict[str, Any] | None = None) -> _FakeResp:
            recorded.append({"method": "POST", "url": url, "headers": headers or {}, "json": json})
            if "createUploadSession" in url:
                return _FakeResp(
                    status_code=200,
                    json_data={"uploadUrl": "https://upload.sharepoint.cn/session/abc"},
                )
            return _FakeResp(status_code=200, json_data={})

        def put(self, url: str, headers: dict[str, str] | None = None, content: bytes = b"") -> _FakeResp:
            hdrs = headers or {}
            recorded.append({"method": "PUT", "url": url, "headers": hdrs, "content": content})
            if url == "https://upload.sharepoint.cn/session/abc":
                cr = hdrs.get("Content-Range", "")
                # 判断是否为最后一片
                m = re.match(r"bytes (\d+)-(\d+)/(\d+)", cr)
                assert m is not None
                end_b, total_b = int(m.group(2)), int(m.group(3))
                if end_b + 1 < total_b:
                    return _FakeResp(status_code=202, json_data={"nextExpectedRanges": [f"{end_b + 1}-"]})
                return _FakeResp(
                    status_code=201,
                    json_data={"id": "chunk_item_1", "size": total_b, "webUrl": "https://sp.cn/big"},
                )
            ret_size = scenario["put_return_size"] if scenario["put_return_size"] is not None else len(content)
            return _FakeResp(
                status_code=200,
                json_data={"id": "small_item_1", "size": ret_size, "webUrl": "https://sp.cn/small"},
            )

    monkeypatch.setattr(httpx, "Client", _FakeHttpClient)

    # (a) 小文件单次 PUT
    small_res = od.upload_bytes("01_项目归档/small.txt", b"small")
    assert small_res["size"] == 5
    assert recorded[-1]["method"] == "PUT"
    assert recorded[-1]["url"].endswith("/content")

    # (b) 大文件分片上传 (16 字节，阈值 10，分片大小 6 -> 3 片)
    monkeypatch.setattr(OneDrive21VianetClient, "CHUNK_THRESHOLD", 10)
    monkeypatch.setattr(OneDrive21VianetClient, "CHUNK_SIZE", 6)
    recorded.clear()

    big_res = od.upload_bytes("01_项目归档/big.bin", b"0123456789ABCDEF")
    assert big_res["size"] == 16
    assert recorded[0]["method"] == "POST"
    assert "createUploadSession" in recorded[0]["url"]
    chunk_puts = [r for r in recorded if r["method"] == "PUT" and r["url"] == "https://upload.sharepoint.cn/session/abc"]
    assert len(chunk_puts) == 3
    assert [r["headers"]["Content-Range"] for r in chunk_puts] == [
        "bytes 0-5/16",
        "bytes 6-11/16",
        "bytes 12-15/16",
    ]

    # (c) 返回 size 不匹配时抛 RuntimeError
    scenario["put_return_size"] = 2
    with pytest.raises(RuntimeError):
        od.upload_bytes("01_项目归档/mismatch.txt", b"small")
    scenario["put_return_size"] = None

    # (d) append_project_note 在已有内容后追加新纪要（同时保留旧内容）
    monkeypatch.setattr(OneDrive21VianetClient, "CHUNK_THRESHOLD", 4 * 1024 * 1024)
    recorded.clear()
    od.append_project_note("帕莫瑞", "## 2026-11-24\n- 新增验收纪要")
    note_puts = [r for r in recorded if r["method"] == "PUT"]
    assert len(note_puts) == 1
    written_text = note_puts[0]["content"].decode("utf-8")
    assert "旧会议纪要" in written_text
    assert "新增验收纪要" in written_text
