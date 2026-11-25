"""Black-box contract tests for the standardized 6-element Hourly Mail Summary template (RED -> GREEN).

Enforces that EVERY hourly mail summary (both normal triage & deferred-pending-card batches)
renders EVERY received email with all 6 mandatory executive elements:
1. Title (`《...》`)
2. Sender (`发件人`)
3. To recipients (`主送`)
4. CC recipients (`抄送`, explicit `无` when empty)
5. Main content summary (`主要内容`)
6. Concrete handling advice (`建议处理`: `【需您回复】`/`【需建卡跟进】`/`【归入已有任务】`/`【团队跟进(您仅抄送)】`/`【纯知会免处理】`)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake import mail_poller
from wechat_assistant.schemas import (
    ActionMutation,
    AgentDecision,
    ListType,
    MailBatchDigest,
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
        dashscope_api_key="sk-fakemailtmpl1234567890ab",
        web_access_secret="mail-tmpl-hmac-secret-1234567890",
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


def _mk_four_real_style_emails() -> list[dict[str, Any]]:
    return [
        {
            "id": "m1",
            "internetMessageId": "<m1@palmarytech.com>",
            "conversationId": "conv-weihai-121",
            "subject": "Re: PAL-3-2611-121威海环文再生能源有限公司_CEMS水分校准",
            "from": {"emailAddress": {"address": "zhangsan@palmarytech.com"}},
            "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "wangnan@wissentek.com"}}],
            "body": {"contentType": "text", "content": "徐总您好，威海环文 CEMS 水分校准现场偏差 3.2%，请您确认是否按新系数修正。"},
            "bodyPreview": "徐总您好，威海环文 CEMS 水分校准现场偏差 3.2%",
            "receivedDateTime": "2026-11-25T06:10:00Z",
        },
        {
            "id": "m2",
            "internetMessageId": "<m2@palmarytech.com>",
            "conversationId": "conv-preamp-bom",
            "subject": "前置放大器改版前后的价格、功能对比",
            "from": {"emailAddress": {"address": "liwenying@palmarytech.com"}},
            "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "徐总，附件为国产替代 v2.0 与旧版前放 BOM 价格下降 38% 及温漂对比，请审批投板。"},
            "bodyPreview": "附件为国产替代 v2.0 与旧版前放 BOM 价格下降 38%",
            "receivedDateTime": "2026-11-25T06:20:00Z",
        },
        {
            "id": "m3",
            "internetMessageId": "<m3@budi.de>",
            "conversationId": "conv-po-038",
            "subject": "回复: New PO BD-PMR-038-20261120",
            "from": {"emailAddress": {"address": "buyer@budi.de"}},
            "toRecipients": [{"emailAddress": {"address": "wangnan@wissentek.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
            "body": {"contentType": "text", "content": "Hi Wang Nan, confirmed PO BD-PMR-038-20261120 delivery on Dec 5."},
            "bodyPreview": "Hi Wang Nan, confirmed PO BD-PMR-038-20261120 delivery on Dec 5.",
            "receivedDateTime": "2026-11-25T06:30:00Z",
        },
        {
            "id": "m4",
            "internetMessageId": "<m4@palmarytech.com>",
            "conversationId": "conv-preamp-sch",
            "subject": "前置放大器改版后（v2.0）的原理图文件",
            "from": {"emailAddress": {"address": "liwenying@palmarytech.com"}},
            "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "徐总，前放 v2.0 原理图已整理完毕，请查收并确认接口定义。"},
            "bodyPreview": "前放 v2.0 原理图已整理完毕",
            "receivedDateTime": "2026-11-25T06:40:00Z",
        },
    ]


@pytest.mark.asyncio
async def test_deferred_mail_batch_renders_standard_6_element_template_for_every_email(tmp_path: Path) -> None:
    """[正常+边界] 即使旧确认卡 #2 未回复，顺延汇总仍须按标准模板逐封展示 6 要素（标题/发件/主送/抄送/主要内容/建议处理），且不覆盖旧卡。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T06:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T06:00:00Z")
    pid = db.save_pending_proposal(
        thread_id="owner",
        proposal_dict={"headline": "旧确认卡", "executive_summary": "待确认", "actions": []},
        source_ids=[],
    )
    assert pid == 1

    digest_resp = MailBatchDigest(
        items=[
            MailDigestItem(
                mail_ref="MAIL-1",
                main_content="反馈威海环文 CEMS 水分校准现场偏差 3.2%，请求确认新系数。",
                action_type="需您回复",
                suggested_action="请确认校准系数方向并回复现场同事。",
            ),
            MailDigestItem(
                mail_ref="MAIL-2",
                main_content="提交国产替代 v2.0 与旧版前放 BOM 降本 38% 及温漂对比表。",
                action_type="需您回复",
                suggested_action="请审阅价格与指标对比后拍板是否投板。",
            ),
            MailDigestItem(
                mail_ref="MAIL-3",
                main_content="Budi 确认新订单 BD-PMR-038-20261120 将于 12 月 5 日发运。",
                action_type="团队跟进(您仅抄送)",
                suggested_action="由王楠继续对接发运，您知情即可。",
            ),
            MailDigestItem(
                mail_ref="MAIL-4",
                main_content="发来前放 v2.0 改版原理图文件，供评审接口定义。",
                action_type="需建卡跟进",
                suggested_action="与前放对比邮件合入同一任务卡审阅归档。",
            ),
        ]
    )

    completions = _ScriptedCompletions(lambda _kw, _i: digest_resp.model_dump_json())
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")
    inbox_msgs = _mk_four_real_style_emails()
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
            now_local=datetime(2026, 11, 25, 15, 0, tzinfo=SHANGHAI),
            domains_path=_mk_domains(tmp_path),
            fetch_folder=fake_fetch,
        )
        assert res["deferred_inbox"] is True
        assert len(pushes) == 1
        msg = pushes[0]

        # Must contain all 6 standardized elements for EVERY email
        assert "【收件逐封明细（共 4 封）】" in msg
        assert "《Re: PAL-3-2611-121威海环文再生能源有限公司_CEMS水分校准》" in msg
        assert "《前置放大器改版前后的价格、功能对比》" in msg
        assert "《回复: New PO BD-PMR-038-20261120》" in msg
        assert "《前置放大器改版后（v2.0）的原理图文件》" in msg
        assert "发件人：zhangsan@palmarytech.com" in msg
        assert "主送：john.xu@palmarytech.com" in msg
        assert "抄送：wangnan@wissentek.com" in msg
        assert "抄送：无" in msg
        assert "发件人：buyer@budi.de" in msg
        assert "抄送：john.xu@palmarytech.com" in msg
        assert "主要内容：反馈威海环文 CEMS 水分校准现场偏差 3.2%" in msg
        assert "建议处理：【需您回复】请确认校准系数方向并回复现场同事。" in msg
        assert "建议处理：【团队跟进(您仅抄送)】由王楠继续对接发运，您知情即可。" in msg
        assert "还没回复" in msg
        assert "「改：…」" not in msg  # no stale v2.0 syntax

        # Safety invariants still 100% locked
        assert db.get_latest_pending_proposal("owner")["id"] == 1
        assert db.is_external_seen("<m1@palmarytech.com>") is False
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_deferred_mail_batch_gracefully_falls_back_to_deterministic_6_elements_on_llm_503(tmp_path: Path) -> None:
    """[异常韧性] 当百炼大模型 503 宕机时，顺延汇总仍确定性渲染完整 6 要素（标题/发件/主送/抄送/清洗正文/角色处理建议），零崩溃。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T06:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T06:00:00Z")
    db.save_pending_proposal(
        thread_id="owner",
        proposal_dict={"headline": "旧卡", "executive_summary": "待确认", "actions": []},
        source_ids=[],
    )

    def outage(_kw, _i):
        raise RuntimeError("503 Service Unavailable")

    completions = _ScriptedCompletions(outage)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")
    inbox_msgs = _mk_four_real_style_emails()[:2]
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
            now_local=datetime(2026, 11, 25, 15, 0, tzinfo=SHANGHAI),
            domains_path=_mk_domains(tmp_path),
            fetch_folder=fake_fetch,
        )
        assert res["deferred_inbox"] is True
        assert len(pushes) == 1
        msg = pushes[0]
        assert "【收件逐封明细（共 2 封）】" in msg
        assert "发件人：zhangsan@palmarytech.com" in msg
        assert "主送：john.xu@palmarytech.com" in msg
        assert "抄送：wangnan@wissentek.com" in msg
        assert "主要内容：" in msg and "3.2%" in msg
        assert "建议处理：【" in msg
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_normal_triage_mail_batch_includes_per_email_6_element_digest_above_card(tmp_path: Path) -> None:
    """[正常] 无阻塞正常整点分拣时，1 次主脑调用同时产出逐封 6 要素明细与确认卡，顶部清晰列出每封邮件。"""
    settings = _mk_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-25T06:00:00Z")
    db.set_mail_watermark("sent", "2026-11-25T06:00:00Z")

    decision = AgentDecision(
        mode="propose",
        proposal=TriageProposal(
            headline="威海环文水分校准与前放改版对比",
            executive_summary="本小时收到 2 封内部请示邮件。",
            actions=[
                ActionMutation(
                    list_type=ListType.PROJECT_ACTION,
                    work_domain=WorkDomain.DELIVERY,
                    project_name="威海环文项目",
                    title="确认威海环文 CEMS 水分校准修正系数",
                    deliverable="答复确认版水分校准参数",
                    owner="徐宏玮",
                    assignee="张三",
                    planned_start_at="2026-11-25",
                    planned_end_at="2026-11-26",
                    mail_conversation_ids=["MAIL-1"],
                )
            ],
            mail_digests=[
                MailDigestItem(
                    mail_ref="MAIL-1",
                    main_content="威海环文 CEMS 水分校准现场偏差 3.2%，请求确认新系数。",
                    action_type="需您回复",
                    suggested_action="请确认新修正系数并回复现场同事。",
                ),
                MailDigestItem(
                    mail_ref="MAIL-2",
                    main_content="提交国产替代 v2.0 与旧版前放 BOM 降本 38% 对比表。",
                    action_type="需建卡跟进",
                    suggested_action="请审阅价格与温漂差异后拍板投板。",
                ),
            ],
        ),
    )

    completions = _ScriptedCompletions(lambda _kw, _i: decision.model_dump_json())
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw, onedrive=_NoOpOneDrive(), checkpoints_path=tmp_path / "ckpt.db")
    inbox_msgs = _mk_four_real_style_emails()[:2]
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
            now_local=datetime(2026, 11, 25, 15, 0, tzinfo=SHANGHAI),
            domains_path=_mk_domains(tmp_path),
            fetch_folder=fake_fetch,
        )
        assert res["ok"] is True and res["proposal_id"] == 1
        assert len(completions.calls) == 1  # ZERO extra LLM calls!
        msg = pushes[0]
        assert "【收件逐封明细（共 2 封）】" in msg
        assert "发件人：zhangsan@palmarytech.com ｜ 主送：john.xu@palmarytech.com ｜ 抄送：wangnan@wissentek.com" in msg
        assert "发件人：liwenying@palmarytech.com ｜ 主送：john.xu@palmarytech.com ｜ 抄送：无" in msg
        assert "主要内容：威海环文 CEMS 水分校准现场偏差 3.2%" in msg
        assert "建议处理：【需您回复】请确认新修正系数并回复现场同事。" in msg
        assert "📋 确认 #1｜" in msg
        assert msg.index("【收件逐封明细（共 2 封）】") < msg.index("📋 确认 #1｜")
    finally:
        eng.close()
