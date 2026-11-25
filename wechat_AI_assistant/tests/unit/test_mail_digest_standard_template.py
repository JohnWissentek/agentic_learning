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
    """[方案 A 并行队列] 即使旧确认卡 #1 未回复，本班仍并行生成确认卡 #2 并逐封展示完整 6 要素，且不覆盖旧卡 #1。"""
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

    decision_resp = AgentDecision(
        mode="propose",
        proposal=TriageProposal(
            headline="威海环文水分校准与前放 v2.0 改版审阅",
            executive_summary="本小时收到 4 封邮件，其中 3 封需您回复/建卡，1 封为抄送团队跟进。",
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
            ],
        ),
    )

    completions = _ScriptedCompletions(lambda _kw, _i: decision_resp.model_dump_json())
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
        assert res["ok"] is True and res["proposal_id"] == 2
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
        assert "📋 确认 #2｜" in msg
        assert "#1" in msg and "旧确认卡" in msg
        assert "「改：…」" not in msg  # no stale v2.0 syntax

        # Plan A invariants: old card #1 preserved alongside #2, processed emails marked seen
        assert [p["id"] for p in db.list_pending_proposals("owner")] == [1, 2]
        assert db.is_external_seen("<m1@palmarytech.com>") is True
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_deferred_mail_batch_gracefully_falls_back_to_deterministic_6_elements_on_llm_503(tmp_path: Path) -> None:
    """[异常韧性] 当百炼大模型 503 宕机时，邮件汇总仍确定性渲染完整 6 要素且不破坏旧卡 #1，零崩溃。"""
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
        assert res["llm_degraded"] is True
        assert len(pushes) == 1
        msg = pushes[0]
        assert "【收件逐封明细（共 2 封）】" in msg
        assert "发件人：zhangsan@palmarytech.com" in msg
        assert "主送：john.xu@palmarytech.com" in msg
        assert "抄送：wangnan@wissentek.com" in msg
        assert "主要内容：" in msg and "3.2%" in msg
        assert "建议处理：【" in msg
        assert [p["id"] for p in db.list_pending_proposals("owner")] == [1]
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


def _mk_five_graph_style_emails_with_display_names() -> list[dict[str, Any]]:
    """Mirror real M365 Graph responses with display names + multiple internal/external recipients."""
    return [
        {
            "id": "g1",
            "internetMessageId": "<g1@palmarytech.com>",
            "conversationId": "conv-g1",
            "subject": "Re: PAL-3-2611-121威海环文再生能源有限公司_CEMS水分校准",
            "from": {"emailAddress": {"name": "Xudong.Lv", "address": "lvxudong@palmarytech.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "Kathy-Lei.Xue", "address": "xuelei@palmarytech.com"}},
                {"emailAddress": {"name": "Daniel-Nan.Wang", "address": "wangnan@palmarytech.com"}},
                {"emailAddress": {"name": "紫初 孔", "address": "winni-zichu.kong@wissentek.com"}},
                {"emailAddress": {"name": "Xiao.Wang", "address": "wangxiao@palmarytech.com"}},
                {"emailAddress": {"name": "Xi.Chen", "address": "chenxi@palmarytech.com"}},
                {"emailAddress": {"name": "Mengjia.Xu", "address": "xumengjia@palmarytech.com"}},
            ],
            "ccRecipients": [
                {"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}},
                {"emailAddress": {"name": "Steffi-Lili.Yang", "address": "steffi@palmarytech.com"}},
            ],
            "body": {"contentType": "text", "content": "威海环文CEMS水分校准项目已建号，请王晓开票。"},
            "receivedDateTime": "2026-11-25T04:13:00Z",
        },
        {
            "id": "g2",
            "internetMessageId": "<g2@wissentek.com>",
            "conversationId": "conv-g2",
            "subject": "前置放大器改版前后的价格、功能对比",
            "from": {"emailAddress": {"name": "Will-Wenying.Li", "address": "will-wenying.li@wissentek.com"}},
            "toRecipients": [{"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [
                {"emailAddress": {"name": "Mengjia.Xu", "address": "xumengjia@palmarytech.com"}},
                {"emailAddress": {"name": "Winni-Zichu.Kong", "address": "winni-zichu.kong@wissentek.com"}},
            ],
            "body": {"contentType": "text", "content": "提交前置放大器改版前后关键器件价格与功能对比，请审阅决策。"},
            "hasAttachments": True,
            "receivedDateTime": "2026-11-25T06:50:00Z",
        },
        {
            "id": "g3",
            "internetMessageId": "<g3@palmarytech.com>",
            "conversationId": "conv-g3",
            "subject": "回复: New PO BD-PMR-038-20261120",
            "from": {"emailAddress": {"name": "Xi.Chen", "address": "chenxi@palmarytech.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "martin.brodeck", "address": "martin.brodeck@budi.de"}},
                {"emailAddress": {"name": "Birgit Rombey", "address": "Birgit.Rombey@budi.de"}},
            ],
            "ccRecipients": [
                {"emailAddress": {"name": "Steffi-Lili.Yang", "address": "steffi@palmarytech.com"}},
                {"emailAddress": {"name": "Simone Emunds", "address": "Simone.Emunds@budi.de"}},
                {"emailAddress": {"name": "Andreas Wegner", "address": "Andreas.Wegner@budi.de"}},
                {"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}},
                {"emailAddress": {"name": "Arnab Banerjee", "address": "arnab.banerjee@budi.de"}},
            ],
            "body": {"contentType": "text", "content": "确认将西柏坡替换麦克风与8根石英管合并发货，并请分拆两张发票以便报关。"},
            "receivedDateTime": "2026-11-25T06:55:00Z",
        },
        {
            "id": "g4",
            "internetMessageId": "<g4@wissentek.com>",
            "conversationId": "conv-g4",
            "subject": "前置放大器改版后（v2.0）的原理图文件",
            "from": {"emailAddress": {"name": "Will-Wenying.Li", "address": "will-wenying.li@wissentek.com"}},
            "toRecipients": [{"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "提交前置放大器v2.0原理图，除特定端子外壳外均可在立创商城采购。"},
            "hasAttachments": True,
            "receivedDateTime": "2026-11-25T06:55:00Z",
        },
        {
            "id": "g5",
            "internetMessageId": "<g5@palmarytech.com>",
            "conversationId": "conv-g5",
            "subject": "回复: New PO BD-PMR-038-20261120（赠品声明）",
            "from": {"emailAddress": {"name": "Xi.Chen", "address": "chenxi@palmarytech.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "martin.brodeck", "address": "martin.brodeck@budi.de"}},
                {"emailAddress": {"name": "Birgit Rombey", "address": "Birgit.Rombey@budi.de"}},
            ],
            "ccRecipients": [
                {"emailAddress": {"name": "Steffi-Lili.Yang", "address": "steffi@palmarytech.com"}},
                {"emailAddress": {"name": "John-Hongwei.Xu", "address": "john.xu@palmarytech.com"}},
                {"emailAddress": {"name": "Arnab Banerjee", "address": "arnab.banerjee@budi.de"}},
            ],
            "body": {"contentType": "text", "content": "追加要求Budi签署清关赠品声明，并询问旧麦克风是否退回。"},
            "hasAttachments": True,
            "receivedDateTime": "2026-11-25T07:04:00Z",
        },
    ]


def test_concise_recipient_display_and_whole_email_atomic_chunking() -> None:
    """[防拦腰截断] 内部同事精简显示姓名、外部仅附域名；切分时必须按整封邮件原子切分，绝不把单封邮件拆成两半。"""
    from wechat_assistant.intake.wecom_gateway import WeComGateway

    msgs = _mk_five_graph_style_emails_with_display_names()
    digest = mail_poller.format_mail_digest_section(
        msgs,
        local_tz=SHANGHAI,
        self_email="john.xu@palmarytech.com",
        internal_domains=("palmarytech.com", "wissentek.com"),
        llm_digests=[
            {"mail_ref": "MAIL-1", "main_content": "威海环文项目已建号，吕旭东通知王晓开具2.8万元发票。", "action_type": "团队跟进(您仅抄送)", "suggested_action": "由王晓开票、薛蕾统筹，您无需处理。"},
            {"mail_ref": "MAIL-2", "main_content": "李文英提交前放改版前后关键器件价格与功能对比文件。", "action_type": "需您回复", "suggested_action": "请审阅附件后批复是否采用新版方案。"},
            {"mail_ref": "MAIL-3", "main_content": "陈晞确认西柏坡替换麦克风与8根石英管合并发货并分拆两张发票。", "action_type": "团队跟进(您仅抄送)", "suggested_action": "由陈晞继续对接外方落实发货与发票，您知悉即可。"},
            {"mail_ref": "MAIL-4", "main_content": "李文英提交前放v2.0原理图，其余元件均可在立创商城采购。", "action_type": "需您回复", "suggested_action": "请结合价格对比一并审阅，确认后批复推进打样。"},
            {"mail_ref": "MAIL-5", "main_content": "陈晞追加要求Budi签署清关赠品声明并询问旧件是否退回。", "action_type": "团队跟进(您仅抄送)", "suggested_action": "由陈晞跟进外方签署声明及旧件处理，您无需介入。"},
        ],
    )

    # 1) Concise names for internal colleagues; concise Name(domain) or raw email (no redundant Name(email)) for externals
    assert "发件人：Xudong.Lv" in digest
    assert "lvxudong@palmarytech.com" not in digest
    assert "xuelei@palmarytech.com" not in digest
    assert "Birgit Rombey(budi.de)" in digest
    assert "Birgit.Rombey@budi.de" not in digest
    assert "martin.brodeck(martin.brodeck@budi.de)" not in digest

    # 2) Whole-email atomic chunking under strict WeChat-Plugin-safe budget
    full_msg = (
        "📧 邮件汇总（15:34，含此前未推送的邮件）｜收件 5 封\n\n"
        f"{digest}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ 确认卡 #2 还没回复，本班暂不生成新确认卡。\n"
        "👉 回复 1 确认落盘 ｜ 0 作废 ｜ 或直接发自然语言调整当前确认卡"
    )
    chunks = WeComGateway._split_chunks(full_msg, limit=1100, max_chars=650)
    assert len(chunks) >= 2
    for ch in chunks:
        assert len(ch.encode("utf-8")) <= 1100
        assert len(ch) <= 650

    # Every single email #1..#5 MUST remain 100% intact inside ONE single chunk!
    for idx in range(1, 6):
        title_marker = f"{idx}. 《"
        matching_chunks = [c for c in chunks if title_marker in c]
        assert len(matching_chunks) == 1, f"Email #{idx} missing or duplicated across chunks"
        owner_chunk = matching_chunks[0]
        # Extract that email's slice inside owner_chunk and verify all 4 lines stay together
        after = owner_chunk.split(title_marker, 1)[1]
        next_block = after.split("\n\n", 1)[0]
        assert "• 发件人：" in next_block, f"Email #{idx} was split before 发件人!"
        assert "• 主要内容：" in next_block, f"Email #{idx} was split before 主要内容!"
        assert "• 建议处理：" in next_block, f"Email #{idx} was split before 建议处理!"


@pytest.mark.asyncio
async def test_send_app_push_adds_page_numbers_enforces_wechat_plugin_budget_and_paces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[微信插件防丢包] send_app_push 拆多段时：每段 <=1150 字节且 <=680 字符、自带【i/N】页码、段间节流等待、整封邮件绝不拆半。"""
    import asyncio as _asyncio
    import httpx
    from wechat_assistant.intake.wecom_gateway import WeComGateway

    settings = Settings(
        dashscope_api_key="sk-fakemailtmpl1234567890ab",
        web_access_secret="mail-tmpl-hmac-secret-1234567890",
        data_dir=str(tmp_path / "data"),
        wecom_corp_id="ww-test",
        wecom_app_agent_id="1000002",
        wecom_app_secret="sec-test",
        wecom_app_owner_userid="XuHongWei",
    )

    async def _noop(*_a, **_kw) -> str:
        return ""

    gw = WeComGateway(settings, turn_processor=_noop)
    gw._token_value = "tok-valid"
    gw._token_exp = 9999999999.0

    sent_payloads: list[str] = []
    sleep_calls: list[float] = []

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"errcode": 0, "errmsg": "ok", "msgid": f"mid-{len(sent_payloads)}"}

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, *, params: Any = None, json: dict[str, Any]) -> _FakeResp:
            sent_payloads.append(json["text"]["content"])
            return _FakeResp()

    async def _fake_sleep(sec: float) -> None:
        sleep_calls.append(sec)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(_asyncio, "sleep", _fake_sleep)

    msgs = _mk_five_graph_style_emails_with_display_names()
    digest = mail_poller.format_mail_digest_section(
        msgs,
        local_tz=SHANGHAI,
        self_email="john.xu@palmarytech.com",
        internal_domains=("palmarytech.com", "wissentek.com"),
    )
    full_msg = f"📧 邮件汇总（15:34）｜收件 5 封\n\n{digest}\n\n━━━━━━━━━━━━━━━━━━━━\n⚠️ 确认卡 #2 还没回复。"

    await gw.send_app_push(full_msg)

    assert len(sent_payloads) >= 2
    total = len(sent_payloads)
    # 1) Page numbers present and every sent chunk within strict WeChat-Plugin safe limits
    for idx, content in enumerate(sent_payloads, 1):
        assert content.startswith(f"【{idx}/{total}】\n")
        assert len(content.encode("utf-8")) <= 1150
        assert len(content) <= 680

    # 2) Inter-chunk pacing delay called (total - 1) times with >= 0.5s
    assert len(sleep_calls) == total - 1
    assert all(d >= 0.5 for d in sleep_calls)

    # 3) Every single email #1..#5 stays whole in ONE chunk
    for idx in range(1, 6):
        hits = [c for c in sent_payloads if f"{idx}. 《" in c]
        assert len(hits) == 1
        email_block = hits[0].split(f"{idx}. 《", 1)[1].split("\n\n", 1)[0]
        assert "• 发件人：" in email_block and "• 主要内容：" in email_block and "• 建议处理：" in email_block

    # 4) Single short message should NOT get a 【1/1】 prefix or sleep
    sent_payloads.clear()
    sleep_calls.clear()
    await gw.send_app_push("短通知：任务 #1 已完成。")
    assert sent_payloads == ["短通知：任务 #1 已完成。"]
    assert sleep_calls == []

