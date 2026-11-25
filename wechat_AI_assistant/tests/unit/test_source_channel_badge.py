"""Independent black-box contract tests for task source_channel badge & filtering (RED phase).

Strictly derived from Red-Zone contracts & acceptance specs:
- `src/wechat_assistant/schemas.py`: ActionMutation.source_channel in {"wechat", "outlook", "web"}
- `report_templates/task_card_schema.json`: TaskCard.source_channel in ["wechat", "outlook", "web"]

Covers 4 core acceptance scenarios:
1. Legacy DB migration adds `source_channel` (defaulting legacy rows to "wechat") and persists
   "outlook", "wechat", and "web" accurately across DB restarts.
2. Automatic source_channel tagging across all 3 ingestion paths:
   - Outlook mail poller forces "outlook" even when LLM omits or defaults source_channel to "wechat"
   - WeChat turn + confirmation commits with "wechat"
   - Web cockpit POST /api/items (without explicit source_channel) commits with "web"
3. Morning digest (`build_daily_digest_message`) explicitly renders "Outlook" for Outlook tasks
   and "微信" for WeChat tasks.
4. Web cockpit HTML (`GET /`) includes `id="filter-source"` with options wechat/outlook/web,
   frontend `source_channel` badge rendering (Outlook / 微信), and `getFilteredItems` filtering
   by `filter-source`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake import mail_poller
from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.web.app import build_daily_digest_message, create_app

SHANGHAI = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Deterministic external gateway stubs (zero network, zero real LLM calls)
# ---------------------------------------------------------------------------


class _DummyOneDrive:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}

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

    def append_project_note(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


class _ScriptedCompletions:
    """Fake OpenAI completions client recording every call."""

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


def _write_domains_file(tmp_path: Path) -> Path:
    path = tmp_path / "mail_domains.json"
    payload = {
        "domains": [
            "palmarytech.com",
            "wissentek.com",
            "budi.de",
        ],
        "internal_domains": [
            "palmarytech.com",
            "wissentek.com",
        ],
        "partner_domains": [
            "budi.de",
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _make_graph_msg(
    *,
    msg_id: str,
    internet_id: str,
    subject: str,
    sender: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    conversation_id: str = "",
    received_utc: str = "2026-11-25T00:45:00Z",
    body_content: str = "",
) -> dict[str, Any]:
    return {
        "id": msg_id,
        "internetMessageId": internet_id,
        "conversationId": conversation_id,
        "subject": subject,
        "from": {"emailAddress": {"name": sender.split("@")[0], "address": sender}},
        "toRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in to_addrs],
        "ccRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in (cc_addrs or [])],
        "receivedDateTime": received_utc,
        "bodyPreview": body_content[:200],
        "body": {"contentType": "text", "content": body_content},
    }


def _critic_pass_json() -> str:
    return json.dumps(
        {
            "passed": True,
            "numeric_fidelity_ok": True,
            "schedule_reasonable": True,
            "issues": [],
            "fix_instructions": "",
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 1. Legacy DB migration & cross-restart persistence of source_channel
# ---------------------------------------------------------------------------


def test_db_migrates_and_persists_source_channel_compatibly(tmp_path: Path) -> None:
    """[正常+边界] 旧版无 source_channel 列的 list_items 自动无损迁移并默认回填 'wechat'，三渠道写入跨重启准确持久化。"""
    db_path = tmp_path / "legacy_source_channel.db"

    # Seed legacy list_items table WITHOUT source_channel column
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
                'project_action', '历史遗留项目', '项目交付', '旧版存量任务', '本人',
                '2026-11-01', '2026-11-30', 'in_progress',
                '2026-11-01 09:00:00', '2026-11-01 09:00:00'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    # Open via Database -> must migrate losslessly and add source_channel column
    db = Database(db_path)

    check_conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in check_conn.execute("PRAGMA table_info(list_items)").fetchall()}
    finally:
        check_conn.close()
    assert "source_channel" in cols, f"Expected source_channel column after migration, got cols={sorted(cols)}"

    legacy_items = [it for it in db.list_items(include_done=True) if it["title"] == "旧版存量任务"]
    assert len(legacy_items) == 1, "Legacy row must be preserved losslessly"
    assert legacy_items[0].get("source_channel") == "wechat", (
        f"Legacy row must backfill source_channel='wechat', got {legacy_items[0].get('source_channel')!r}"
    )

    # Persist 3 tasks across all 3 channels via apply_proposal_atomic
    created = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="西柏坡项目",
                title="渠道测试-Outlook任务",
                deliverable="确认发运单",
                owner="徐宏玮",
                assignee="王楠",
                planned_start_at="2026-11-25",
                planned_end_at="2026-12-01",
                source_channel="outlook",
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="博州电厂项目",
                title="渠道测试-微信任务",
                deliverable="提交 DCS 点表",
                owner="徐宏玮",
                assignee="王楠",
                planned_start_at="2026-11-25",
                planned_end_at="2026-12-02",
                source_channel="wechat",
            ),
            ActionMutation(
                list_type=ListType.NEXT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="声波测温研发",
                title="渠道测试-Web任务",
                deliverable="输出评审纪要",
                owner="徐宏玮",
                assignee="李文颖",
                planned_start_at="2026-11-25",
                planned_end_at="2026-12-03",
                source_channel="web",
            ),
        ],
        source_ids=[],
        doc_paths=[],
    )
    assert len(created["inserted_item_ids"]) == 3

    # Re-open Database from disk to prove cross-restart persistence
    db_reopened = Database(db_path)
    by_title = {it["title"]: it for it in db_reopened.list_items(include_done=True)}

    assert by_title["旧版存量任务"].get("source_channel") == "wechat"
    assert by_title["渠道测试-Outlook任务"].get("source_channel") == "outlook"
    assert by_title["渠道测试-微信任务"].get("source_channel") == "wechat"
    assert by_title["渠道测试-Web任务"].get("source_channel") == "web"


# ---------------------------------------------------------------------------
# 2. Automatic source_channel tagging for Outlook, WeChat, and Web paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_tags_source_channel_for_outlook_wechat_and_web(tmp_path: Path) -> None:
    """[正常+禁令] Outlook/微信/Web 三条入口自动标记 source_channel：邮件即使模型漏填或默认 wechat 也必须强制标为 outlook。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "channels.db")
    od = _DummyOneDrive()
    domains_path = _write_domains_file(tmp_path)

    # Deliberately omit source_channel (or leave default "wechat") in LLM producer outputs
    outlook_proposal_json = json.dumps(
        {
            "headline": "西柏坡替换麦克风合箱发运",
            "executive_summary": "Budi 确认免费补发替换麦克风，需确认合箱发运方案。",
            "actions": [
                {
                    "list_type": "project_action",
                    "work_domain": "采购供应链",
                    "project_name": "西柏坡项目",
                    "title": "确认西柏坡替换麦克风合箱发运",
                    "deliverable": "回复 Arnab 确认合箱发运方案并收到发货单",
                    "owner": "徐宏玮",
                    "assignee": "王楠",
                    "external_partner": "Arnab",
                    "chairman_role": "owner",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "2026-12-02",
                    "estimated_hours": 0.0,
                    "priority": "P1",
                    # Explicitly simulate LLM returning default "wechat" instead of "outlook"
                    "source_channel": "wechat",
                }
            ],
            "task_updates": [],
            "fyi_notices": [],
            "referenced_numbers": [],
            "citations": [],
        },
        ensure_ascii=False,
    )

    wechat_proposal_json = json.dumps(
        {
            "headline": "安排王楠提交点表",
            "executive_summary": "交办王楠在周五前提交点表。",
            "actions": [
                {
                    "list_type": "project_action",
                    "work_domain": "项目交付",
                    "project_name": "日常事务",
                    "title": "王楠周五前提交点表",
                    "deliverable": "王楠提交的完整点表文档",
                    "owner": "徐宏玮",
                    "assignee": "王楠",
                    "chairman_role": "owner",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "",
                    "estimated_hours": 0.0,
                    "priority": "P1",
                    "missing_required_fields": ["planned_end_at"],
                }
            ],
            "task_updates": [],
            "fyi_notices": [],
            "referenced_numbers": [],
            "citations": [],
        },
        ensure_ascii=False,
    )

    def _llm_handler(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs.get("model", "")
        if model in {settings.fast_model, settings.fast_fallback_model}:
            return json.dumps(
                {
                    "intent": "work_triage",
                    "confidence": 0.96,
                    "summary": "工作任务交办",
                },
                ensure_ascii=False,
            )
        if model in {settings.critic_model, settings.critic_fallback_model}:
            return _critic_pass_json()
        prompt_blob = json.dumps(kwargs.get("messages", []), ensure_ascii=False)
        if "budi.de" in prompt_blob or "Replacement mic shipment" in prompt_blob:
            return outlook_proposal_json
        return wechat_proposal_json

    completions = _ScriptedCompletions(_llm_handler)
    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt_channels.db",
    )

    try:
        # ---- Path A: Outlook mail poller -> confirm "1" -> source_channel == "outlook" ----
        inbox_msg = _make_graph_msg(
            msg_id="m-outlook-tag-1",
            internet_id="<outlook-tag-1@budi.de>",
            subject="Replacement mic shipment",
            sender="Arnab@budi.de",
            to_addrs=["john.xu@palmarytech.com"],
            cc_addrs=["wangnan@wissentek.com"],
            conversation_id="conv-outlook-tag-001",
            received_utc="2026-11-25T00:45:00Z",
            body_content="Please confirm replacement mic shipment consolidation by 2026-12-02.",
        )

        async def _fetch(folder: str, _since_utc: str) -> list[dict[str, Any]]:
            return [inbox_msg] if folder == "inbox" else []

        pushed: list[str] = []

        async def _send_push(text: str) -> None:
            pushed.append(text)

        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=_send_push,
            now_local=datetime(2026, 11, 25, 9, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=_fetch,
        )
        assert len(pushed) == 1, "Expected hourly mail summary card push"
        assert db.get_latest_pending_proposal("owner") is not None

        confirm_outlook = engine.handle_incoming_turn(
            "1",
            sender="owner",
            external_msg_id="confirm-outlook-tag-1",
        )
        assert confirm_outlook["reply_text"]

        outlook_tasks = [
            it for it in db.list_items(include_done=True) if "西柏坡替换麦克风" in it["title"]
        ]
        assert len(outlook_tasks) == 1
        assert outlook_tasks[0].get("source_channel") == "outlook", (
            f"Outlook mail task must be force-tagged 'outlook', got {outlook_tasks[0].get('source_channel')!r}"
        )

        # ---- Path B: WeChat turn -> confirm "1" -> source_channel == "wechat" ----
        wx_preview = engine.handle_incoming_turn(
            "让王楠周五前提交点表",
            sender="owner",
            external_msg_id="wx-tag-1",
        )
        assert wx_preview["reply_text"]
        assert db.get_latest_pending_proposal("owner") is not None

        wx_confirm = engine.handle_incoming_turn(
            "1",
            sender="owner",
            external_msg_id="wx-tag-confirm-1",
        )
        assert wx_confirm["reply_text"]

        wechat_tasks = [
            it for it in db.list_items(include_done=True) if "点表" in it["title"]
        ]
        assert len(wechat_tasks) == 1
        assert wechat_tasks[0].get("source_channel") == "wechat", (
            f"WeChat task must be tagged 'wechat', got {wechat_tasks[0].get('source_channel')!r}"
        )

        # ---- Path C: Web cockpit POST /api/items (no source_channel) -> overview returns "web" ----
        app = create_app(
            settings=settings,
            db=db,
            engine=engine,
            onedrive=od,
            start_background_tasks=False,
        )
        with TestClient(app) as client:
            tok = app.state.auth.mint_magic_token(300)
            login_resp = client.get(f"/auth/magic?token={tok}", follow_redirects=False)
            assert login_resp.status_code == 302

            res_create = client.post(
                "/api/items",
                json={
                    "title": "驾驶舱直建BOM评审",
                    "list_type": "project_action",
                    "work_domain": "产品研发",
                    "project_name": "声波测温研发",
                    "deliverable": "完成国产器件选型评审纪要",
                    "owner": "徐宏玮",
                    "assignee": "李文颖",
                    "planned_start_at": "2026-11-25",
                    "planned_end_at": "2026-12-05",
                    "priority": "P1",
                },
            )
            assert res_create.status_code == 200, res_create.text
            web_item_id = res_create.json()["created_ids"][0]

            ov_resp = client.get("/api/dashboard/overview")
            assert ov_resp.status_code == 200, ov_resp.text
            ov_items = ov_resp.json()["items"]
            web_card = next(it for it in ov_items if it["id"] == web_item_id)
            assert web_card.get("source_channel") == "web", (
                f"Web-created task must be tagged 'web' in overview, got {web_card.get('source_channel')!r}"
            )
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 3. Morning digest renders explicit source channel label ("Outlook" / "微信")
# ---------------------------------------------------------------------------


def test_morning_digest_displays_source_channel_label(tmp_path: Path) -> None:
    """[正常] 早间工作报告中，Outlook 任务行必须显式展示 'Outlook'，微信任务行必须显式展示 '微信'。"""
    db = Database(tmp_path / "digest_source.db")

    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="西柏坡项目",
                title="核对替换麦克风发运清单",
                deliverable="确认发运单与物流单号",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="Arnab",
                planned_start_at="2026-11-25",
                planned_end_at="2026-12-02",
                priority=PriorityLevel.P1,
                source_channel="outlook",
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="博州电厂项目",
                title="提交博州电厂DCS点表与逻辑说明",
                deliverable="经韩工确认的点表文档",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="韩工",
                planned_start_at="2026-11-25",
                planned_end_at="2026-11-28",
                priority=PriorityLevel.P1,
                source_channel="wechat",
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

    assert "【任务 #1】" in msg and "【任务 #2】" in msg

    def _extract_task_block(digest_text: str, task_num: int) -> str:
        marker = f"【任务 #{task_num}】"
        start = digest_text.index(marker)
        tail = digest_text[start + len(marker) :]
        stop_match = re.search(r"(【任务 #\d+】|━{3,}|👉|📊)", tail)
        end_offset = stop_match.start() if stop_match else len(tail)
        return (marker + tail[:end_offset]).strip()

    # Order-independent isolation of Task #1 (Outlook) and Task #2 (WeChat) blocks without footer noise
    task1_block = _extract_task_block(msg, 1)
    task2_block = _extract_task_block(msg, 2)

    task1_lines = [ln.strip() for ln in task1_block.splitlines() if ln.strip()]
    task2_lines = [ln.strip() for ln in task2_block.splitlines() if ln.strip()]

    assert any(
        "Outlook" in ln and ("【任务 #1】" in ln or "来源" in ln)
        for ln in task1_lines
    ), f"Expected Outlook source label on Task #1 header/source line, got:\n{task1_block}"

    assert any(
        "微信" in ln and ("【任务 #2】" in ln or "来源" in ln)
        for ln in task2_lines
    ), f"Expected 微信 source label on Task #2 header/source line, got:\n{task2_block}"

    assert "Outlook" not in task2_block, f"WeChat task block must not be labeled Outlook:\n{task2_block}"
    assert "微信" not in task1_block, f"Outlook task block must not be labeled 微信:\n{task1_block}"


# ---------------------------------------------------------------------------
# 4. Web cockpit HTML includes source filter & source badge rendering logic
# ---------------------------------------------------------------------------


def test_web_cockpit_html_includes_source_badge_and_filter(tmp_path: Path) -> None:
    """[正常] Web 驾驶舱页面包含 id='filter-source'（wechat/outlook/web 三选项）及前端 source_channel 徽章与过滤逻辑。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "cockpit_html.db")
    od = _DummyOneDrive()
    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=_ScriptedCompletions(lambda *_: "{}"))),
    )
    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt_html.db",
    )
    app = create_app(
        settings=settings,
        db=db,
        engine=eng,
        onedrive=od,
        start_background_tasks=False,
    )

    try:
        with TestClient(app) as client:
            resp = client.get("/")
            assert resp.status_code == 200
            html = resp.text
    finally:
        eng.close()

    # 1) <select ... id="filter-source" ...> with wechat, outlook, web options
    select_match = re.search(
        r"""<select\b[^>]*\bid=["']filter-source["'][^>]*>(.*?)</select>""",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert select_match is not None, 'Expected <select id="filter-source"> in cockpit HTML'
    select_inner = select_match.group(1)
    for opt_val in ("wechat", "outlook", "web"):
        assert re.search(
            rf"""<option\b[^>]*\bvalue=["']{opt_val}["']""",
            select_inner,
            flags=re.IGNORECASE,
        ), f'Expected option value="{opt_val}" inside #filter-source select, got:\n{select_inner}'

    # 2) Frontend script renders source_channel badge with Outlook & 微信 labels
    script_blocks = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
    script_text = "\n".join(script_blocks)
    assert "source_channel" in script_text, "Expected frontend script to reference item.source_channel for badges"
    assert "Outlook" in script_text, "Expected frontend script to render 'Outlook' source badge label"
    assert "微信" in script_text, "Expected frontend script to render '微信' source badge label"

    # 3) getFilteredItems filters by filter-source
    fn_match = re.search(
        r"function\s+getFilteredItems\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function\s+|\Z)",
        script_text,
        flags=re.DOTALL,
    )
    assert fn_match is not None, "Expected function getFilteredItems(...) in cockpit frontend script"
    fn_body = fn_match.group(1)
    assert "filter-source" in fn_body, (
        f"Expected getFilteredItems to read #filter-source filter, got:\n{fn_body[:600]}"
    )
    assert "source_channel" in fn_body, (
        f"Expected getFilteredItems to filter items by source_channel, got:\n{fn_body[:600]}"
    )
