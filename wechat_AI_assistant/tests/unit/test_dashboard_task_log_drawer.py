"""Black-box TDD tests for Dashboard Task Updates & Chronological Notes Drawer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from wechat_assistant.config import Settings
from wechat_assistant.storage.db import Database
from wechat_assistant.web.app import create_app


class _NoOpOneDrive:
    def upload_bytes(self, remote_path: str, data: bytes, **_kw: Any) -> dict[str, Any]:
        return {"id": "m", "webUrl": f"https://sp.cn/{remote_path}", "size": len(data)}

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        return {}

    def append_project_note(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


def _mk_settings(tmp_path: Path) -> Settings:
    return Settings(
        dashscope_api_key="sk-fakedrawer1234567890ab",
        web_access_secret="drawer-hmac-secret-1234567890",
        data_dir=str(tmp_path / "data"),
    )


def test_dashboard_html_exposes_task_updates_drawer_and_note_composer(tmp_path: Path) -> None:
    """Dashboard HTML 必须包含每行日志气泡入口、右侧抽屉、分类筛选与提交备注/进展/评价交互。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    app = create_app(settings=settings, db=db, onedrive=_NoOpOneDrive(), start_background_tasks=False)

    with TestClient(app) as client:
        html = client.get("/").text
        assert "updates-trigger-btn" in html
        assert "openTaskDrawer(" in html
        assert "submitDrawerNote(" in html
        assert "drawer-note-input" in html
        assert "/note" in html
        assert "ceo_evaluation" in html
        assert "drawer-root" in html


def test_task_notes_append_chronologically_with_exact_timestamps_without_overwriting(tmp_path: Path) -> None:
    """同一任务多次追加备注/进展/CEO评价时，均保留完整历史且每条带精确日期时间戳，绝不互相覆盖。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    app = create_app(settings=settings, db=db, onedrive=_NoOpOneDrive(), start_background_tasks=False)

    with TestClient(app) as client:
        tok = app.state.auth.mint_magic_token()
        assert client.get(f"/auth/magic?token={tok}", follow_redirects=False).status_code == 302

        c_resp = client.post(
            "/api/items",
            json={"title": "前置放大器 v2.0 原理图评审", "project_name": "前置放大器改版"},
        )
        assert c_resp.status_code == 200
        item_id = c_resp.json()["created_ids"][0]

        r1 = client.post(
            f"/api/items/{item_id}/note",
            json={"kind": "comment", "content": "今天想到要先核对 4P 科发端子封装尺寸"},
        )
        r2 = client.post(
            f"/api/items/{item_id}/note",
            json={"kind": "comment", "content": "明天再核对金属屏蔽壳的供应商交期"},
        )
        r3 = client.post(
            f"/api/items/{item_id}/note",
            json={"kind": "progress", "content": "已与李文英电话对齐初步改版方向"},
        )
        r4 = client.post(
            f"/api/items/{item_id}/note",
            json={"kind": "ceo_evaluation", "content": "国产替代优先，控制BOM成本下降30%以上"},
        )
        assert all(r.status_code == 200 for r in (r1, r2, r3, r4))

        ov = client.get("/api/dashboard/overview").json()
        item = next(it for it in ov["items"] if it["id"] == item_id)

        assert len(item["comments"]) == 2
        assert item["comments"][0]["content"] == "今天想到要先核对 4P 科发端子封装尺寸"
        assert item["comments"][1]["content"] == "明天再核对金属屏蔽壳的供应商交期"
        assert len(item["comments"][0]["date"]) == 10
        assert len(item["comments"][0]["timestamp"]) == 16  # YYYY-MM-DD HH:MM

        assert len(item["ceo_evaluation"]) == 1
        assert len(item["ceo_evaluation"][0]["timestamp"]) == 16

        assert len(item["timeline"]) == 1
        assert item["timeline"][0]["summary"] == "已与李文英电话对齐初步改版方向"
        assert item["timeline"][0]["channel"] == "web"


def test_wechat_conversation_can_append_multiple_comments_and_view_all_logs(tmp_path: Path) -> None:
    """在微信 AI工作助理里通过自然语言对话，可给特定任务连续多轮追加备注日志，并随时查看全部备注与进展。"""
    from types import SimpleNamespace
    from wechat_assistant.config import DashScopeLLMGateway
    from wechat_assistant.graph import ChiefOfStaffEngine
    from wechat_assistant.schemas import ActionMutation, AgentDecision, ListType, TaskNoteAppend, WorkDomain

    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.RD,
                project_name="前置放大器改版",
                title="审阅前放 v2.0 原理图",
                deliverable="审阅批复",
                owner="徐宏玮",
                assignee="李文英",
                planned_start_at="2026-11-25",
                planned_end_at="2026-11-30",
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    tid = seed["inserted_item_ids"][0]

    script = [
        AgentDecision(
            mode="direct_ops",
            note_appends=[TaskNoteAppend(task_id=tid, kind="comment", content="今天想到要先问立创 4P 科发端子交期")],
        ).model_dump_json(),
        AgentDecision(
            mode="direct_ops",
            note_appends=[TaskNoteAppend(task_id=tid, kind="comment", content="明天顺便让李文英对比屏蔽壳打样报价")],
        ).model_dump_json(),
        AgentDecision(mode="direct_ops", view_timeline_ids=[tid]).model_dump_json(),
    ]
    call_idx = {"n": 0}

    class _Completions:
        def create(self, **_kw: Any) -> Any:
            call_idx["n"] += 1
            return SimpleNamespace(
                usage=SimpleNamespace(prompt_tokens=20, completion_tokens=20, completion_tokens_details=None),
                choices=[SimpleNamespace(message=SimpleNamespace(content=script[call_idx["n"] - 1], tool_calls=None, reasoning_content=""))],
            )

    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_Completions())))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")
    try:
        r1 = eng.handle_incoming_turn("关于前放原理图那个任务，记一条备注：今天想到要先问立创 4P 科发端子交期")
        assert "追加备注日志（共 1 条）" in r1["reply_text"]
        r2 = eng.handle_incoming_turn("给 #1 再补充一条日志：明天顺便让李文英对比屏蔽壳打样报价")
        assert "追加备注日志（共 2 条）" in r2["reply_text"]
        r3 = eng.handle_incoming_turn("看一下 #1 的所有备注和日志")
        assert "今天想到要先问立创 4P 科发端子交期" in r3["reply_text"]
        assert "明天顺便让李文英对比屏蔽壳打样报价" in r3["reply_text"]

        item = db.get_item(tid)
        assert item is not None and len(item["comments"]) == 2
        assert len(item["comments"][0]["timestamp"]) == 16
        assert len(item["comments"][1]["timestamp"]) == 16
    finally:
        eng.close()

