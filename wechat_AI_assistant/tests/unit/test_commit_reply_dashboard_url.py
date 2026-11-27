"""Black-box contract tests for Web dashboard URL & cloud sync status in commit confirmation replies."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.schemas import (
    ActionMutation,
    ListType,
    PriorityLevel,
    TaskTimelineUpdate,
    TimelineEntry,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage.db import Database

REALISTIC_SHAREPOINT_URL = (
    "https://wissentek.sharepoint.cn/sites/chairman-vault/Shared%20Documents/"
    "00_%E6%88%91%E7%9A%84%E5%9B%9B%E5%A4%A7%E6%B8%85%E5%8D%95/"
    "01_%E4%BB%8A%E6%97%A5%E4%B8%8E%E8%A1%8C%E5%8A%A8%E5%BE%85%E5%8A%9E.md"
)
DASHBOARD_URL = "https://assistant.fire-matrix.com/"


class _SharePointSyncStubOneDrive:
    """OneDrive stub returning realistic China 21Vianet SharePoint `.md` URLs."""

    def __init__(self) -> None:
        self.sync_calls: int = 0
        self.notes: list[tuple[str, str]] = []

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        self.sync_calls += 1
        return {"01_今日与行动待办.md": REALISTIC_SHAREPOINT_URL}

    def append_project_note(self, project_name: str, entry_md: str) -> dict[str, Any]:
        self.notes.append((project_name, entry_md))
        return {"id": "note_1"}

    def upload_bytes(self, remote_path: str, data: bytes, **_kw: Any) -> dict[str, Any]:
        return {"id": "m", "webUrl": REALISTIC_SHAREPOINT_URL, "size": len(data)}


class _FailingOneDrive:
    """OneDrive stub simulating transient 503 / network failure during list sync."""

    def __init__(self) -> None:
        self.sync_calls: int = 0

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        self.sync_calls += 1
        raise RuntimeError("onedrive 503")

    def append_project_note(self, project_name: str, entry_md: str) -> dict[str, Any]:
        return {"id": "note_noop"}


class _ZeroCallCompletions:
    """LLM stub enforcing 0 model calls on deterministic confirmation shortcut `1`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        raise AssertionError(f"Confirmation shortcut '1' must not invoke LLM, got call: {kwargs}")


def _mk_settings(
    tmp_path: Path,
    *,
    web_public_base_url: str = "https://assistant.fire-matrix.com",
) -> Settings:
    return Settings(
        dashscope_api_key="sk-fakedashboardurltest123456",
        web_access_secret="dashboard-url-test-hmac-secret-123456",
        web_public_base_url=web_public_base_url,
        data_dir=str(tmp_path / "data"),
    )


def _mk_gateway(settings: Settings) -> tuple[DashScopeLLMGateway, _ZeroCallCompletions]:
    completions = _ZeroCallCompletions()
    gw = DashScopeLLMGateway(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    return gw, completions


def _seed_new_task_proposal(db: Database) -> None:
    proposal = TriageProposal(
        headline="审阅华东客户技术协议",
        executive_summary="新增华东客户技术协议审阅任务，预计净投入 1.5h。",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SALES,
                project_name="华东交付项目",
                title="审阅华东客户技术协议并反馈修改意见",
                deliverable="修订版技术协议",
                owner="徐宏玮",
                assignee="王楠",
                planned_start_at="2026-11-27",
                planned_end_at="2026-12-02",
                estimated_hours=1.5,
                priority=PriorityLevel.P0,
            )
        ],
    )
    db.save_pending_proposal(
        thread_id="owner",
        proposal_dict=proposal.model_dump(mode="json"),
        source_ids=[],
    )


def _seed_existing_task_and_timeline_update_proposal(db: Database) -> int:
    seed = db.apply_proposal_atomic(
        proposal_id=None,
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="亳州电厂项目",
                title="亳州锅炉声波测温接口确认",
                deliverable="确认号角图纸",
                owner="徐宏玮",
                assignee="王楠",
                external_partner="Arnab",
                planned_start_at="2026-11-20",
                planned_end_at="2026-12-01",
                priority=PriorityLevel.P1,
            )
        ],
        source_ids=[],
        doc_paths=[],
    )
    task_id = seed["inserted_item_ids"][0]

    update_proposal = TriageProposal(
        headline="更新亳州锅炉号角图纸邮件进展",
        executive_summary="王楠已发送最新图纸给 Arnab，仅更新已有任务时间轴与阶段。",
        actions=[],
        task_updates=[
            TaskTimelineUpdate(
                target_task_id=task_id,
                target_task_title="亳州锅炉声波测温接口确认",
                match_method="conversation_id",
                timeline_entry=TimelineEntry(
                    timestamp="2026-11-27 10:15",
                    channel="mail_in",
                    from_party="王楠",
                    to_party="Arnab",
                    summary="已发送修订版号角图纸及现场测温数据",
                    source_ref="<bozhou-rev2@wissentek.com>",
                    mail_conversation_id="conv-bozhou-rev2",
                ),
                milestone_stage_update="图纸已发送待外方确认",
            )
        ],
    )
    db.save_pending_proposal(
        thread_id="owner",
        proposal_dict=update_proposal.model_dump(mode="json"),
        source_ids=[],
    )
    return task_id


def test_commit_new_task_shows_dashboard_url_and_sync_status_without_sharepoint_md_url(tmp_path: Path) -> None:
    """[正常] 新建任务确认落盘且 OneDrive 同步成功：展示 Web 驾驶舱链接与「云端清单已同步」，严禁泄露 SharePoint `.md` 裸链。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _SharePointSyncStubOneDrive()
    gw, completions = _mk_gateway(settings)
    _seed_new_task_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        magic_link_factory=lambda: DASHBOARD_URL,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-new-task-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert od.sync_calls == 1
        assert len(db.list_items()) == 1
        assert "已确认落盘" in reply
        assert "云端清单已同步" in reply
        assert DASHBOARD_URL in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()
    finally:
        eng.close()


def test_commit_task_timeline_update_shows_dashboard_url_and_sync_status_without_sharepoint_md_url(
    tmp_path: Path,
) -> None:
    """[正常] 更新已有任务时间轴确认落盘且 OneDrive 同步成功：展示 Web 驾驶舱链接与「云端清单已同步」，严禁泄露 SharePoint `.md` 裸链。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _SharePointSyncStubOneDrive()
    gw, completions = _mk_gateway(settings)
    task_id = _seed_existing_task_and_timeline_update_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        magic_link_factory=lambda: DASHBOARD_URL,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-timeline-update-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert od.sync_calls == 1
        timeline = db.get_task_timeline(task_id)
        assert any("已发送修订版号角图纸" in (e.get("summary") or "") for e in timeline)
        assert "已确认落盘" in reply
        assert f"#{task_id}" in reply
        assert "云端清单已同步" in reply
        assert DASHBOARD_URL in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()
    finally:
        eng.close()


def test_commit_uses_settings_web_public_base_url_when_magic_link_factory_omitted(tmp_path: Path) -> None:
    """[正常] 未显式传入 `magic_link_factory` 时，自动使用 `settings.web_public_base_url` 作为驾驶舱链接且不暴露 SharePoint URL。"""
    settings = _mk_settings(tmp_path, web_public_base_url="https://assistant.fire-matrix.com")
    db = Database(tmp_path / "app.db")
    od = _SharePointSyncStubOneDrive()
    gw, completions = _mk_gateway(settings)
    _seed_new_task_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-default-base-url-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert od.sync_calls == 1
        assert "已确认落盘" in reply
        assert "云端清单已同步" in reply
        assert "https://assistant.fire-matrix.com" in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()
    finally:
        eng.close()


def test_commit_when_onedrive_503_persists_locally_shows_degraded_warning_and_dashboard_url(
    tmp_path: Path,
) -> None:
    """[异常] OneDrive 同步抛出 503 时，本地 SQLite 安全落盘不回滚，如实提示同步波动（绝不谎报已同步），仍提供 Web 驾驶舱链接。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _FailingOneDrive()
    gw, completions = _mk_gateway(settings)
    _seed_new_task_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        magic_link_factory=lambda: DASHBOARD_URL,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-onedrive-503-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert od.sync_calls == 1
        persisted = db.list_items()
        assert len(persisted) == 1
        assert persisted[0]["title"] == "审阅华东客户技术协议并反馈修改意见"
        assert db.get_latest_pending_proposal("owner") is None

        assert "已确认落盘" in reply
        assert "网络波动" in reply or "OneDrive" in reply
        assert "云端清单已同步" not in reply
        assert DASHBOARD_URL in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()
    finally:
        eng.close()


def test_commit_without_onedrive_omits_sync_status_but_shows_dashboard_url(tmp_path: Path) -> None:
    """[边界] 未启用 OneDrive（`onedrive=None`）时，不谎报「云端清单已同步」，仍展示 Web 驾驶舱链接且无 SharePoint 裸链。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    gw, completions = _mk_gateway(settings)
    _seed_new_task_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=None,
        magic_link_factory=lambda: DASHBOARD_URL,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-no-onedrive-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert len(db.list_items()) == 1
        assert "已确认落盘" in reply
        assert "云端清单已同步" not in reply
        assert DASHBOARD_URL in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()
    finally:
        eng.close()


def test_commit_with_empty_dashboard_url_shows_sync_status_without_dangling_colon(tmp_path: Path) -> None:
    """[边界] `magic_link_factory` 返回空字符串且 OneDrive 同步成功时，展示「云端清单已同步」且不出现悬空冒号畸形格式。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    od = _SharePointSyncStubOneDrive()
    gw, completions = _mk_gateway(settings)
    _seed_new_task_proposal(db)

    eng = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        magic_link_factory=lambda: "",
        checkpoints_path=tmp_path / "ckpt.db",
    )
    try:
        res = eng.handle_incoming_turn("1", external_msg_id="commit-empty-dashboard-url-1")
        reply = res["reply_text"]

        assert len(completions.calls) == 0
        assert od.sync_calls == 1
        assert "已确认落盘" in reply
        assert "云端清单已同步" in reply
        assert "sharepoint.cn" not in reply.lower()
        assert ".md" not in reply.lower()

        stripped = reply.rstrip()
        assert not stripped.endswith(("：", ":")), f"回复尾部不应出现悬空冒号: {reply!r}"
        for line in reply.splitlines():
            line_s = line.rstrip()
            assert not line_s.endswith(("看板：", "看板:", "驾驶舱：", "驾驶舱:", "链接：", "链接:")), (
                f"空驾驶舱链接时不应输出悬空无链接标签行: {line!r}\n完整回复:\n{reply}"
            )
    finally:
        eng.close()
