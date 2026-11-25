"""Black-box TDD tests for default new-task deadline = +3 business days after creation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from wechat_assistant.config import DashScopeLLMGateway, Settings, today_local
from wechat_assistant.graph import ChiefOfStaffEngine, build_calendar_anchor_text
from wechat_assistant.schemas import ActionMutation, AgentDecision, ListType, TriageProposal, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.schedule_tools import calc_business_date
from wechat_assistant.web.app import create_app


class _NoOpOneDrive:
    def upload_bytes(self, remote_path: str, data: bytes, **_kw: Any) -> dict[str, Any]:
        return {"id": "m", "webUrl": f"https://sp.cn/{remote_path}", "size": len(data)}

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        return {}

    def append_project_note(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


class _ScriptedCompletions:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        out = self.handler(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=30, completion_tokens=20, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=out, tool_calls=None, reasoning_content=""))],
        )


def _mk_settings(tmp_path: Path) -> Settings:
    return Settings(
        dashscope_api_key="sk-fakedefault3biz12345678",
        web_access_secret="default-3biz-hmac-secret-123456",
        data_dir=str(tmp_path / "data"),
    )


def test_calendar_anchor_text_exposes_default_three_business_day_deadline() -> None:
    """日历锚点表必须显式给出「建立后3个工作日」默认截止日（自动跳过周末）。"""
    # 2026-11-25 is Wednesday -> +3 business days = Monday 2026-11-30
    txt = build_calendar_anchor_text(date(2026, 11, 25))
    assert "2026-11-30" in txt
    assert "3个工作日" in txt


def test_new_task_defaults_planned_end_at_to_three_business_days_without_missing_warning(tmp_path: Path) -> None:
    """新任务未指定截止时间时，自动设为建立后 3 个工作日，绝不再弹出「缺失必填提示：目标截止时间」；明确指定截止日时原样保留。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    today_d = today_local()
    today_str = today_d.isoformat()
    expected_default_end = calc_business_date(today_str, 3)
    future_start = calc_business_date(today_str, 5)
    expected_future_end = calc_business_date(future_start, 3)
    explicit_end = calc_business_date(today_str, 10)

    decision = AgentDecision(
        mode="propose",
        proposal=TriageProposal(
            headline="前放改版与下周项目排期",
            executive_summary="测试默认 3 个工作日截止时间。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.RD,
                    project_name="前置放大器改版",
                    title="审阅前放 v2.0 原理图",
                    deliverable="审阅批复意见",
                    owner="徐宏玮",
                    assignee="李文英",
                    planned_start_at=today_str,
                    planned_end_at="",
                    missing_required_fields=["planned_end_at"],
                ),
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="未来启动项目",
                    title="下周启动的客户测试",
                    deliverable="测试报告",
                    owner="徐宏玮",
                    assignee="王楠",
                    planned_start_at=future_start,
                    planned_end_at="",
                    missing_required_fields=["planned_end_at"],
                ),
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.SALES,
                    project_name="明确截止项目",
                    title="提交正式报价单",
                    deliverable="签章报价单",
                    owner="徐宏玮",
                    assignee="陈晞",
                    planned_start_at=today_str,
                    planned_end_at=explicit_end,
                    missing_required_fields=[],
                ),
            ],
        ),
    )

    completions = _ScriptedCompletions(lambda _kw, _i: decision.model_dump_json())
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")

    try:
        res = eng.handle_incoming_turn("安排审阅前放原理图和下周客户测试")
        card = res["reply_text"]
        assert f"目标截止：{expected_default_end}" in card
        assert f"目标截止：{expected_future_end}" in card
        assert f"目标截止：{explicit_end}" in card
        assert "缺失必填提示" not in card
        assert "缺少：目标截止时间" not in card
        assert "目标截止：【待补齐】" not in card

        saved_pending = db.get_latest_pending_proposal("owner")
        assert saved_pending is not None
        acts = saved_pending["proposal"]["actions"]
        assert acts[0]["planned_end_at"] == expected_default_end
        assert "planned_end_at" not in (acts[0].get("missing_required_fields") or [])
        assert acts[1]["planned_end_at"] == expected_future_end
        assert acts[2]["planned_end_at"] == explicit_end
    finally:
        eng.close()


def test_web_api_create_item_defaults_planned_end_at_to_three_business_days(tmp_path: Path) -> None:
    """驾驶舱新建任务未填截止日时，默认设为开始/建立日后 3 个工作日，且不标 missing_required_fields。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    today_str = today_local().isoformat()
    expected_end = calc_business_date(today_str, 3)

    app = create_app(settings=settings, db=db, onedrive=_NoOpOneDrive(), start_background_tasks=False)
    with TestClient(app) as client:
        tok = app.state.auth.mint_magic_token()
        assert client.get(f"/auth/magic?token={tok}", follow_redirects=False).status_code == 302
        resp = client.post(
            "/api/items",
            json={
                "title": "驾驶舱默认三工作日截止测试",
                "project_name": "日常事务",
                "planned_end_at": "",
            },
        )
        assert resp.status_code == 200
        item_id = resp.json()["created_ids"][0]
        it = db.get_item(item_id)
        assert it is not None
        assert it["planned_end_at"] == expected_end
        assert it["missing_required_fields"] == []
