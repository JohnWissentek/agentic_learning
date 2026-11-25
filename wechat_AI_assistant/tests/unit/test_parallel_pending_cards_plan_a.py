"""Black-box TDD contract tests for Plan A: Parallel Pending Confirmation Card Queue.

Verifies:
1. Hourly mail batches NEVER block on an unreplied older pending card — they create a new
   pending card in parallel while keeping older pending cards intact, mark processed emails
   seen & advance inbox watermark (zero hourly repeat spam), and show a concise queue hint.
2. Multi-card confirm/discard by `target_proposal_ids` (e.g., confirm #1 & #3, discard #2)
   and default latest-card confirm/discard (`1`/`0`) with remaining-queue reminders.
3. Targeted single-card revision (`replace_proposal_id`) supersedes ONLY that card without
   touching other pending cards in the queue.
4. ContextAssembler surfaces ALL pending cards to the flagship brain.
5. DashScope 503 during mail batch still delivers deterministic 6-element digest without
   corrupting existing pending cards or losing emails.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.context_assembler import ContextAssembler
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake import mail_poller
from wechat_assistant.schemas import (
    ActionMutation,
    AgentDecision,
    ListType,
    MailDigestItem,
    TriageProposal,
    WorkDomain,
)
from wechat_assistant.storage.db import Database

SHANGHAI = ZoneInfo("Asia/Shanghai")


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
            usage=SimpleNamespace(prompt_tokens=40, completion_tokens=30, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=out, tool_calls=None, reasoning_content=""))],
        )


def _mk_settings(tmp_path: Path) -> Settings:
    return Settings(
        dashscope_api_key="sk-fakeplana1234567890abcd",
        web_access_secret="plana-hmac-secret-1234567890",
        data_dir=str(tmp_path / "data"),
        mail_enabled=True,
        mail_user="john.xu@palmarytech.com",
    )


def _mk_domains(tmp_path: Path) -> Path:
    p = tmp_path / "mail_domains.json"
    p.write_text(
        json.dumps(
            {
                "internal_domains": ["palmarytech.com", "wissentek.com"],
                "partner_domains": ["budi.de", "vandf.com", "tera-instruments.com"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


def _sample_proposal(headline: str, title: str, *, end_date: str = "2026-11-27") -> dict[str, Any]:
    return TriageProposal(
        headline=headline,
        executive_summary=f"摘要：{headline}",
        actions=[
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.DELIVERY,
                project_name="帕莫瑞项目",
                title=title,
                deliverable=f"交付：{title}",
                owner="徐宏玮",
                assignee="李文英",
                planned_start_at="2026-11-25",
                planned_end_at=end_date,
            )
        ],
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_plan_a_mail_batch_creates_parallel_card_without_blocking_or_overwriting_old_card(tmp_path: Path) -> None:
    """[方案 A 核心] 旧确认卡 #1 未回复时，新一小时邮件不阻塞，直接并行生成确认卡 #2、推进水位防重复骚扰，且 #1 完好保留。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T06:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T06:00:00Z")
    old_id = db.save_pending_proposal(
        thread_id="owner",
        proposal_dict=_sample_proposal("中午旧待确认事项", "审阅中午旧邮件报价"),
        source_ids=[],
    )
    assert old_id == 1

    decision = AgentDecision(
        mode="propose",
        proposal=TriageProposal(
            headline="审阅前置放大器 v2.0 对比与原理图",
            executive_summary="李文英发来前放 v2.0 价格功能对比与原理图，请审阅批复。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.RD,
                    project_name="前置放大器改版",
                    title="审阅前放 v2.0 价格对比与原理图并批复",
                    deliverable="确认 v2.0 改版方案批复意见",
                    owner="徐宏玮",
                    assignee="李文英",
                    planned_start_at="2026-11-25",
                    planned_end_at="2026-11-27",
                    mail_conversation_ids=["MAIL-1"],
                )
            ],
            mail_digests=[
                MailDigestItem(
                    mail_ref="MAIL-1",
                    main_content="李文英提交前放 v2.0 价格功能对比与原理图，请审阅批复。",
                    action_type="需您回复",
                    suggested_action="请查阅附件后回复李文英是否批准投产。",
                )
            ],
        ),
    )

    completions = _ScriptedCompletions(lambda _kw, _i: decision.model_dump_json())
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")

    inbox_msgs = [
        {
            "id": "m1",
            "internetMessageId": "<preamp-v2@wissentek.com>",
            "conversationId": "conv-preamp-v2",
            "subject": "前置放大器改版前后的价格、功能对比",
            "from": {"emailAddress": {"name": "Will-Wenying.Li", "address": "will-wenying.li@wissentek.com"}},
            "toRecipients": [{"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "徐总，请审阅前放 v2.0 对比数据。"},
            "hasAttachments": True,
            "receivedDateTime": "2026-11-25T06:50:00Z",
        }
    ]
    pushes: list[str] = []

    async def fake_fetch(folder: str, _since: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else []

    async def fake_push(txt: str) -> None:
        pushes.append(txt)

    try:
        res = await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=_NoOpOneDrive(),
            engine=eng,
            send_push=fake_push,
            now_local=datetime(2026, 11, 25, 16, 0, tzinfo=SHANGHAI),
            domains_path=_mk_domains(tmp_path),
            fetch_folder=fake_fetch,
        )
        assert res["ok"] is True
        assert res["pushed"] is True
        assert res.get("deferred_inbox") is not True
        assert res["proposal_id"] == 2

        # Both card #1 and card #2 MUST coexist in pending queue!
        pending_list = db.list_pending_proposals("owner")
        assert [p["id"] for p in pending_list] == [1, 2]

        # Email MUST be marked seen and inbox watermark advanced -> zero repeat spam next hour!
        assert db.is_external_seen("<preamp-v2@wissentek.com>") is True
        assert mail_poller._parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc)

        # Push message includes 6-element digest + new card #2 + queue reminder mentioning #1
        assert len(pushes) == 1
        msg = pushes[0]
        assert "【收件逐封明细（共 1 封）】" in msg
        assert "📋 确认 #2｜" in msg
        assert "#1" in msg and "中午旧待确认事项" in msg
    finally:
        eng.close()


def test_plan_a_multi_card_confirm_discard_revision_and_context_visibility(tmp_path: Path) -> None:
    """[多卡队列全操作] 支持按编号批量确认/作废、定向修改单卡不影响其它卡、上下文可见全部待确认卡。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    p1 = db.save_pending_proposal(thread_id="owner", proposal_dict=_sample_proposal("卡片一", "任务一"), source_ids=[])
    p2 = db.save_pending_proposal(thread_id="owner", proposal_dict=_sample_proposal("卡片二", "任务二"), source_ids=[])
    p3 = db.save_pending_proposal(thread_id="owner", proposal_dict=_sample_proposal("卡片三", "任务三"), source_ids=[])
    assert [p["id"] for p in db.list_pending_proposals("owner")] == [p1, p2, p3]

    # 1) ContextAssembler must expose ALL 3 pending cards
    ctx = ContextAssembler(db).assemble("owner", "确认卡 1 2 3 都是啥")
    assert [p["id"] for p in ctx.pending_proposals] == [p1, p2, p3]
    assert "#1" in ctx.pending_proposal_text and "卡片一" in ctx.pending_proposal_text
    assert "#2" in ctx.pending_proposal_text and "卡片二" in ctx.pending_proposal_text
    assert "#3" in ctx.pending_proposal_text and "卡片三" in ctx.pending_proposal_text

    # Scripted brain responses for: (1) targeted revision of #2, (2) batch confirm #1 & #4, (3) targeted discard #3
    script = [
        AgentDecision(
            mode="propose",
            replace_proposal_id=2,
            proposal=TriageProposal.model_validate(_sample_proposal("卡片二（已改期）", "任务二改期", end_date="2026-11-30")),
        ).model_dump_json(),
        AgentDecision(mode="confirm_pending", target_proposal_ids=[1, 4]).model_dump_json(),
        AgentDecision(mode="discard_pending", target_proposal_ids=[3]).model_dump_json(),
    ]
    completions = _ScriptedCompletions(lambda _kw, i: script[i - 1])
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")

    try:
        # Step A: Revise ONLY #2 -> supersedes #2 into #4, leaves #1 and #3 intact!
        r_rev = eng.handle_incoming_turn("把确认卡 #2 的截止日改成下周一")
        assert r_rev["proposal_id"] == 4
        assert [p["id"] for p in db.list_pending_proposals("owner")] == [1, 3, 4]

        # Step B: Confirm #1 and #4 together -> commits both, leaves #3 still pending with reminder!
        r_conf = eng.handle_incoming_turn("确认 #1 和 #4")
        assert [p["id"] for p in db.list_pending_proposals("owner")] == [3]
        assert "#3" in r_conf["reply_text"] and "卡片三" in r_conf["reply_text"]
        titles = {it["title"] for it in db.list_items()}
        assert {"任务一", "任务二改期"} == titles

        # Step C: Discard #3 -> queue now empty
        r_disc = eng.handle_incoming_turn("作废 #3")
        assert db.list_pending_proposals("owner") == []
        assert "#3" in r_disc["reply_text"]
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_plan_a_mail_batch_llm_503_still_pushes_deterministic_6_element_digest_and_keeps_old_card(
    tmp_path: Path,
) -> None:
    """[异常韧性] 邮件批次遇到百炼 503 时，仍降级推送确定性 6 要素明细，不破坏旧卡 #1，且不标 seen 以便下班重试立卡。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T06:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T06:00:00Z")
    db.save_pending_proposal(thread_id="owner", proposal_dict=_sample_proposal("旧卡", "旧任务"), source_ids=[])

    def outage(_kw, _i):
        raise RuntimeError("503 Service Unavailable")

    completions = _ScriptedCompletions(outage)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")
    inbox_msgs = [
        {
            "id": "m503",
            "internetMessageId": "<m503@palmarytech.com>",
            "conversationId": "conv-503",
            "subject": "前放 v2.0 原理图确认",
            "from": {"emailAddress": {"name": "Will-Wenying.Li", "address": "will-wenying.li@wissentek.com"}},
            "toRecipients": [{"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "徐总，请确认前放 v2.0 原理图接口定义。"},
            "receivedDateTime": "2026-11-25T06:55:00Z",
        }
    ]
    pushes: list[str] = []

    async def fake_fetch(folder: str, _since: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else []

    async def fake_push(txt: str) -> None:
        pushes.append(txt)

    try:
        res = await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=_NoOpOneDrive(),
            engine=eng,
            send_push=fake_push,
            now_local=datetime(2026, 11, 25, 16, 0, tzinfo=SHANGHAI),
            domains_path=_mk_domains(tmp_path),
            fetch_folder=fake_fetch,
        )
        assert res["ok"] is True and res["pushed"] is True
        assert res.get("llm_degraded") is True
        assert len(pushes) == 1
        msg = pushes[0]
        assert "【收件逐封明细（共 1 封）】" in msg
        assert "发件人：Will-Wenying.Li" in msg
        assert "主要内容：" in msg and "原理图接口定义" in msg
        assert "建议处理：【" in msg
        # Old card #1 untouched, email stays unseen so next slot retries card creation
        assert [p["id"] for p in db.list_pending_proposals("owner")] == [1]
        assert db.is_external_seen("<m503@palmarytech.com>") is False
    finally:
        eng.close()
