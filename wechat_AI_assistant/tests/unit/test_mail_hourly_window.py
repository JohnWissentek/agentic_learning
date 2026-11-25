"""Black-box contract tests for workday hourly mail summary window (Slice 1).

Strictly derived from:
`docs/superpowers/specs/2026-11-24-mail-hourly-window-design.md`

Covers:
- Workday slot schedule & quiet hours (Mon-Fri 08:30, 09:00..21:00; 5-minute window)
- First-run UTC watermark seeding (Mon 08:30 -> Fri 21:00; daytime -> 08:30)
- Database `mail_poll_cursor` persistence per folder (`inbox` / `sent`)
- Domain allowlist matching (subdomains, colleagues, self-email exclusion, noise filter)
- Single batched triage per slot bypassing `qwen3.8-flash` router (path ④ direct)
- Sent mail summary without triage/card + deterministic reply-wait hint
- Per-slot hot-reload of `config/mail_domains.json` & corrupt-file fallback/preservation
- Existing pending card deferral for inbox while still reporting/advancing sent items
- Push-failure rollback (cancels newly created card, preserves watermark & seen for retry)
- Noise & non-allowlist emails marked seen and advance watermark without pushing
- 10-inbox-email cap preserving 11th email via `receivedDateTime - 2min` watermark
- Duplicate `internetMessageId` skipped inside the 2-minute overlap window
- Long sent list truncated to keep total <= 1800 chars while preserving full card text
- Backlog (>70 min) header wording on Monday 08:30 first run
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake import mail_poller
from wechat_assistant.storage.db import Database

SHANGHAI = ZoneInfo("Asia/Shanghai")

DEFAULT_DOMAINS: list[str] = [
    "palmarytech.com",
    "wissentek.com",
    "budi.de",
    "vandf.com",
    "tera-instruments.com",
]


def _parse_utc(ts: str | None) -> datetime:
    assert ts is not None and isinstance(ts, str) and ts.strip() != ""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert dt.tzinfo is not None and dt.utcoffset() == timedelta(0), f"Expected UTC timestamp, got {ts!r}"
    return dt


def _write_domains(path: Path, domains: list[str] | None = None) -> Path:
    payload = {"domains": DEFAULT_DOMAINS if domains is None else domains}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _make_settings(tmp_path: Path, *, mail_user: str = "info@wissentek.com") -> Settings:
    return Settings(
        dashscope_api_key="sk-fakeunit1234567890abcdef",
        web_access_secret="unit-test-hmac-secret-key-1234567890",
        data_dir=str(tmp_path / "data"),
        mail_enabled=True,
        mail_user=mail_user,
    )


class _DummyOneDrive:
    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.synced_boards: dict[str, str] = {}

    def _get_token(self) -> str:
        return "fake-mail-token"

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        return {}


class _ScriptedCompletions:
    """Deterministic fake OpenAI completions recording every model & message payload."""

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


def _default_proposal_json(
    headline: str = "跟进客户邮件交付与报价",
    executive_summary: str = "汇总本时段客户来信，安排报价核对与排期回复，预计投入 1.0h。",
    actions: list[dict[str, Any]] | None = None,
) -> str:
    if actions is None:
        actions = [
            {
                "list_type": "project_action",
                "work_domain": "客户销售",
                "project_name": "V&F 报价",
                "title": "核对最新报价并回复客户",
                "owner": "本人",
                "planned_start_at": "2026-11-24",
                "planned_end_at": "2026-11-26",
                "estimated_hours": 1.0,
                "priority": "P1",
                "onedrive_target_dir": "01_项目归档/VF报价",
            }
        ]
    return json.dumps(
        {
            "headline": headline,
            "executive_summary": executive_summary,
            "actions": actions,
            "referenced_numbers": [],
            "citations": [],
        },
        ensure_ascii=False,
    )


def _make_engine(
    tmp_path: Path,
    settings: Settings,
    db: Database,
    *,
    proposal_json: str | None = None,
) -> tuple[ChiefOfStaffEngine, _ScriptedCompletions, _DummyOneDrive]:
    prop = proposal_json or _default_proposal_json()

    def handler(kwargs: dict[str, Any], _idx: int) -> str:
        model = kwargs["model"]
        if model == settings.fast_model or model == settings.fast_fallback_model:
            return json.dumps(
                {
                    "intent": "work_triage",
                    "confidence": 0.95,
                    "summary": "router fallback",
                },
                ensure_ascii=False,
            )
        if model == settings.producer_model or model == settings.producer_fallback_model:
            return prop
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

    completions = _ScriptedCompletions(handler)
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    od = _DummyOneDrive()
    engine = ChiefOfStaffEngine(
        settings=settings,
        db=db,
        gateway=gw,
        onedrive=od,
        checkpoints_path=tmp_path / "ckpt.db",
    )
    return engine, completions, od


def _spy_handle_turn(engine: ChiefOfStaffEngine, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    orig = engine.handle_incoming_turn

    def _wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raw_text = args[0] if args else kwargs.get("raw_text", "")
        thread_id = kwargs.get("thread_id", "owner")
        result = orig(*args, **kwargs)
        calls.append(
            {
                "raw_text": raw_text,
                "thread_id": thread_id,
                "args": args,
                "kwargs": kwargs,
                "result": result,
            }
        )
        return result

    monkeypatch.setattr(engine, "handle_incoming_turn", _wrapped)
    return calls


def _make_graph_msg(
    *,
    msg_id: str,
    internet_id: str,
    subject: str,
    sender: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    received_utc: str | None = None,
    sent_utc: str | None = None,
    body_preview: str = "",
    body_content: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "id": msg_id,
        "internetMessageId": internet_id,
        "subject": subject,
        "from": {"emailAddress": {"name": sender.split("@")[0], "address": sender}},
        "toRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in to_addrs],
        "ccRecipients": [{"emailAddress": {"name": a.split("@")[0], "address": a}} for a in (cc_addrs or [])],
        "bodyPreview": body_preview,
        "body": {"contentType": "text", "content": body_content if body_content is not None else body_preview},
    }
    if received_utc is not None:
        msg["receivedDateTime"] = received_utc
    if sent_utc is not None:
        msg["sentDateTime"] = sent_utc
    return msg


# ---------------------------------------------------------------------------
# 1. Workday slots & quiet hours
# ---------------------------------------------------------------------------


def test_active_mail_slot_workdays_and_quiet_hours() -> None:
    """[正常+边界+禁令] 工作日 08:30 及 09:00-21:00 5 分钟窗口返回对应时点；08:00、22:00 与周末返回 None。"""
    mon_0830 = datetime(2026, 11, 23, 8, 30, tzinfo=SHANGHAI)
    tue_1100 = datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI)
    tue_1104 = datetime(2026, 11, 24, 11, 4, tzinfo=SHANGHAI)
    fri_2100 = datetime(2026, 11, 27, 21, 0, tzinfo=SHANGHAI)

    tue_0800 = datetime(2026, 11, 24, 8, 0, tzinfo=SHANGHAI)
    tue_1106 = datetime(2026, 11, 24, 11, 6, tzinfo=SHANGHAI)
    tue_2200 = datetime(2026, 11, 24, 22, 0, tzinfo=SHANGHAI)
    sat_1100 = datetime(2026, 11, 28, 11, 0, tzinfo=SHANGHAI)
    sun_0830 = datetime(2026, 11, 29, 8, 30, tzinfo=SHANGHAI)

    assert mon_0830.weekday() == 0
    assert tue_1100.weekday() == 1
    assert fri_2100.weekday() == 4
    assert sat_1100.weekday() == 5
    assert sun_0830.weekday() == 6

    assert mail_poller.active_mail_slot(tue_1100) == "11:00"
    assert mail_poller.active_mail_slot(tue_1104) == "11:00"
    assert mail_poller.active_mail_slot(mon_0830) == "08:30"
    assert mail_poller.active_mail_slot(fri_2100) == "21:00"

    assert mail_poller.active_mail_slot(tue_0800) is None
    assert mail_poller.active_mail_slot(tue_1106) is None
    assert mail_poller.active_mail_slot(tue_2200) is None
    assert mail_poller.active_mail_slot(sat_1100) is None
    assert mail_poller.active_mail_slot(sun_0830) is None


# ---------------------------------------------------------------------------
# 2. First-run UTC watermark seeding & DB persistence
# ---------------------------------------------------------------------------


def test_seed_watermark_monday_0830_and_wednesday_1500() -> None:
    """[正常+边界] 周一 08:30 首次水位为上周五 21:00 UTC；周三 15:00 首次水位为当天 08:30 UTC。"""
    mon_0830 = datetime(2026, 11, 23, 8, 30, tzinfo=SHANGHAI)
    tue_0830 = datetime(2026, 11, 24, 8, 30, tzinfo=SHANGHAI)
    wed_1500 = datetime(2026, 11, 25, 15, 0, tzinfo=SHANGHAI)

    assert mon_0830.weekday() == 0
    assert tue_0830.weekday() == 1
    assert wed_1500.weekday() == 2

    # Fri 2026-11-20 21:00+08:00 == 2026-11-20T13:00:00Z
    assert _parse_utc(mail_poller.seed_watermark_utc(mon_0830)) == datetime(
        2026, 11, 20, 13, 0, 0, tzinfo=timezone.utc
    )
    # Mon 2026-11-23 21:00+08:00 == 2026-11-23T13:00:00Z
    assert _parse_utc(mail_poller.seed_watermark_utc(tue_0830)) == datetime(
        2026, 11, 23, 13, 0, 0, tzinfo=timezone.utc
    )
    # Wed 2026-11-25 08:30+08:00 == 2026-11-25T00:30:00Z
    assert _parse_utc(mail_poller.seed_watermark_utc(wed_1500)) == datetime(
        2026, 11, 25, 0, 30, 0, tzinfo=timezone.utc
    )


def test_db_mail_watermark_persistence(tmp_path: Path) -> None:
    """[正常] Database 按文件夹独立读写并跨重启持久化 mail_poll_cursor 水位。"""
    db_path = tmp_path / "app.db"
    db = Database(db_path)
    assert db.get_mail_watermark("inbox") is None
    assert db.get_mail_watermark("sent") is None

    db.set_mail_watermark("inbox", "2026-11-24T00:30:00Z")
    assert db.get_mail_watermark("inbox") == "2026-11-24T00:30:00Z"
    assert db.get_mail_watermark("sent") is None

    db.set_mail_watermark("inbox", "2026-11-24T03:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T03:00:00Z")

    reopened = Database(db_path)
    assert reopened.get_mail_watermark("inbox") == "2026-11-24T03:00:00Z"
    assert reopened.get_mail_watermark("sent") == "2026-11-24T03:00:00Z"


# ---------------------------------------------------------------------------
# 3. Domain allowlist: subdomains, colleagues, self exclusion, noise filter
# ---------------------------------------------------------------------------


def test_domain_allowlist_subdomains_colleague_and_self_exclusion() -> None:
    """[正常+边界+禁令] 子域名与同事地址命中，非白名单不命中，仅邮箱自己命中域名绝不放行，退订/验证码/noreply 即使命中域名也过滤。"""
    domains = tuple(DEFAULT_DOMAINS)

    # Direct partner domain hit
    msg_vandf = _make_graph_msg(
        msg_id="m1",
        internet_id="<m1@vandf.com>",
        subject="Quotation update",
        sender="sales@vandf.com",
        to_addrs=["info@wissentek.com"],
        body_preview="Updated pricing attached.",
    )
    assert mail_poller.matches_domain_allowlist(msg_vandf, domains, self_email="info@wissentek.com") is True

    # Subdomain hit
    msg_sub = _make_graph_msg(
        msg_id="m2",
        internet_id="<m2@sales.vandf.com>",
        subject="EU shipment",
        sender="info@sales.vandf.com",
        to_addrs=["info@wissentek.com"],
        body_preview="Shipping next Tuesday.",
    )
    assert mail_poller.matches_domain_allowlist(msg_sub, domains, self_email="info@wissentek.com") is True

    # Lookalike suffix must NOT match subdomain
    msg_fake_sub = _make_graph_msg(
        msg_id="m2b",
        internet_id="<m2b@evilvandf.com>",
        subject="Promo",
        sender="sales@evilvandf.com",
        to_addrs=["info@wissentek.com"],
    )
    assert mail_poller.matches_domain_allowlist(msg_fake_sub, domains, self_email="info@wissentek.com") is False

    # Colleague on same domain (different address from self_email) hits
    msg_colleague = _make_graph_msg(
        msg_id="m3",
        internet_id="<m3@wissentek.com>",
        subject="项目排期同步",
        sender="colleague@wissentek.com",
        to_addrs=["info@wissentek.com"],
        body_preview="本周里程碑更新。",
    )
    assert mail_poller.matches_domain_allowlist(msg_colleague, domains, self_email="info@wissentek.com") is True

    # Non-allowlist sender to self_email (info@wissentek.com) must NOT hit
    msg_random = _make_graph_msg(
        msg_id="m4",
        internet_id="<m4@randomvendor.com>",
        subject="Special offer",
        sender="news@randomvendor.com",
        to_addrs=["info@wissentek.com"],
    )
    assert mail_poller.matches_domain_allowlist(msg_random, domains, self_email="info@wissentek.com") is False

    # Self exclusion on palmarytech.com: only john.xu@palmarytech.com is in allowlist
    msg_self_only = _make_graph_msg(
        msg_id="m5",
        internet_id="<m5@gmail.com>",
        subject="Lunch",
        sender="other@gmail.com",
        to_addrs=["john.xu@palmarytech.com"],
    )
    assert mail_poller.matches_domain_allowlist(msg_self_only, domains, self_email="john.xu@palmarytech.com") is False
    # Case-insensitive self exclusion
    msg_self_case = _make_graph_msg(
        msg_id="m5b",
        internet_id="<m5b@gmail.com>",
        subject="Lunch",
        sender="other@gmail.com",
        to_addrs=["John.Xu@PalmaryTech.com"],
    )
    assert mail_poller.matches_domain_allowlist(msg_self_case, domains, self_email="john.xu@palmarytech.com") is False

    # Noise filters even when domain is allowlisted
    for idx, (sender, subject, preview) in enumerate(
        [
            ("sales@vandf.com", "Newsletter", "Click here to unsubscribe from updates"),
            ("sales@vandf.com", "产品动态", "如不再接收请点击退订"),
            ("security@palmarytech.com", "登录验证码 482910", "5分钟内有效"),
            ("noreply@vandf.com", "Auto notification", "Ticket created"),
            ("no-reply@tera-instruments.com", "System notice", "Order log"),
        ]
    ):
        noise_msg = _make_graph_msg(
            msg_id=f"noise-{idx}",
            internet_id=f"<noise-{idx}@vandf.com>",
            subject=subject,
            sender=sender,
            to_addrs=["info@wissentek.com"],
            body_preview=preview,
        )
        assert (
            mail_poller.matches_domain_allowlist(noise_msg, domains, self_email="info@wissentek.com") is False
        ), f"Noise mail should be filtered: {sender} / {subject} / {preview}"

    # Empty domain allowlist rejects everything
    assert mail_poller.matches_domain_allowlist(msg_vandf, (), self_email="info@wissentek.com") is False


# ---------------------------------------------------------------------------
# 4. Two inbox emails batched into 1 card bypassing qwen3.8-flash router
# ---------------------------------------------------------------------------


async def test_two_inbox_emails_batched_into_single_card_bypassing_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常+禁令] 同一时点 2 封命中收件合成 1 次分拣、0 次路由模型调用、1 张待确认卡、1 条微信，且包裹不可信边界标签。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, completions, od = _make_engine(tmp_path, settings, db)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    inbox_msgs = [
        _make_graph_msg(
            msg_id="g-in-1",
            internet_id="<in-1@vandf.com>",
            subject="V&F 报价更新",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:15:00Z",
            body_preview="请核对新版质谱仪报价单。",
        ),
        _make_graph_msg(
            msg_id="g-in-2",
            internet_id="<in-2@wissentek.com>",
            subject="同事同步交付排期",
            sender="colleague@wissentek.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:40:00Z",
            body_preview="本周四前需确认最终发货清单。",
        ),
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    now_local = datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI)
    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=now_local,
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # Exactly 1 batched handle_incoming_turn call on thread_id="owner"
        assert len(turn_calls) == 1
        assert turn_calls[0]["thread_id"] == "owner"

        # Both emails included and wrapped with [UNTRUSTED_EXTERNAL_DATA]
        raw_batch = turn_calls[0]["raw_text"]
        assert "[UNTRUSTED_EXTERNAL_DATA]" in raw_batch
        assert "V&F 报价更新" in raw_batch
        assert "同事同步交付排期" in raw_batch

        # Invariant: ZERO calls to fast router model (qwen3.8-flash), directly enters work_triage path ④
        fast_router_calls = [c for c in completions.calls if c["model"] == settings.fast_model]
        assert len(fast_router_calls) == 0, f"Router model must be bypassed, got calls: {fast_router_calls}"
        producer_calls = [c for c in completions.calls if c["model"] == settings.producer_model]
        assert len(producer_calls) >= 1
        assert "[UNTRUSTED_EXTERNAL_DATA]" in json.dumps(producer_calls[0]["messages"], ensure_ascii=False)

        # Exactly 1 pending card created and 1 WeCom push sent
        pending = db.get_latest_pending_proposal("owner")
        assert pending is not None
        assert len(pushes) == 1
        assert "11:00" in pushes[0]
        assert f"#{pending['id']}" in pushes[0]
        assert "跟进客户邮件交付与报价" in pushes[0]

        # Both inbox messages marked seen and watermarks advanced to slot start (03:00:00Z)
        assert db.is_external_seen("<in-1@vandf.com>") is True
        assert db.is_external_seen("<in-2@wissentek.com>") is True
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 5. Sent mail not triaged & deterministic reply-wait hint
# ---------------------------------------------------------------------------


async def test_sent_mail_not_triaged_and_marks_waiting_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常+禁令] 已发送白名单邮件不调用分拣模型、不建确认卡，直接汇总并按规则标出「可能在等对方」。"""
    # Direct unit assertions on deterministic reply hint
    assert mail_poller.needs_reply_hint("Re: Spectrometer delivery 请确认", "") is True
    assert mail_poller.needs_reply_hint("Delivery date?", "") is True
    assert mail_poller.needs_reply_hint("交期咨询？", "") is True
    assert mail_poller.needs_reply_hint("Follow up", "PLEASE CONFIRM shipment window") is True
    assert mail_poller.needs_reply_hint("Status", "Please advise on customs docs") is True
    assert mail_poller.needs_reply_hint("Status", "Kindly advise") is True
    assert mail_poller.needs_reply_hint("进度同步", "收到请回复") is True
    assert mail_poller.needs_reply_hint("报价更新", "烦请查阅，盼复") is True
    assert mail_poller.needs_reply_hint("Monthly summary FYI", "No action required.") is False

    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, completions, od = _make_engine(tmp_path, settings, db)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    sent_msgs = [
        _make_graph_msg(
            msg_id="g-sent-1",
            internet_id="<sent-1@wissentek.com>",
            subject="Re: Spectrometer delivery",
            sender="info@wissentek.com",
            to_addrs=["support@tera-instruments.com"],
            sent_utc="2026-11-24T02:40:00Z",  # 10:40 Asia/Shanghai
            body_preview="请确认最终发货日期，谢谢。",
        ),
        _make_graph_msg(
            msg_id="g-sent-2",
            internet_id="<sent-2@wissentek.com>",
            subject="Invoice received FYI",
            sender="info@wissentek.com",
            to_addrs=["sales@vandf.com"],
            sent_utc="2026-11-24T02:45:00Z",  # 10:45 Asia/Shanghai
            body_preview="Thanks, we received the invoice.",
        ),
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return sent_msgs if folder == "sent" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    now_local = datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI)
    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=now_local,
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # ZERO LLM calls & ZERO confirmation cards
        assert len(turn_calls) == 0
        assert len(completions.calls) == 0
        assert db.get_latest_pending_proposal("owner") is None

        # Single WeCom push with sent-only summary
        assert len(pushes) == 1
        msg = pushes[0]
        assert "你发出 2 封（不建卡）" in msg
        assert "没有收件" not in msg
        assert "📋 确认" not in msg

        lines = msg.splitlines()
        tera_lines = [ln for ln in lines if "support@tera-instruments.com" in ln]
        vf_lines = [ln for ln in lines if "sales@vandf.com" in ln]
        assert len(tera_lines) == 1
        assert "Re: Spectrometer delivery" in tera_lines[0]
        assert "可能在等对方" in tera_lines[0]

        assert len(vf_lines) == 1
        assert "Invoice received FYI" in vf_lines[0]
        assert "可能在等对方" not in vf_lines[0]

        assert db.is_external_seen("<sent-1@wissentek.com>") is True
        assert db.is_external_seen("<sent-2@wissentek.com>") is True
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 6. Hot-reload domains.json & corrupt JSON fallback / watermark safety
# ---------------------------------------------------------------------------


async def test_domains_json_reloaded_and_corrupt_json_keeps_watermark(tmp_path: Path) -> None:
    """[边界+禁令] 每班重读 domains.json；JSON 损坏且无缓存时不拉取不推不前移水位；有 last_good_domains 时回退生效。"""
    domains_path = tmp_path / "mail_domains.json"

    # Direct unit tests for load_mail_domains
    assert mail_poller.load_mail_domains(domains_path, last_good=None) is None
    _write_domains(domains_path, ["vandf.com"])
    assert mail_poller.load_mail_domains(domains_path, last_good=None) == ("vandf.com",)

    domains_path.write_text("{corrupt json!!!", encoding="utf-8")
    assert mail_poller.load_mail_domains(domains_path, last_good=None) is None
    assert mail_poller.load_mail_domains(domains_path, last_good=("vandf.com",)) == ("vandf.com",)

    # End-to-end window tests: (a) corrupt + no last_good => no fetch, no push, watermark preserved
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    engine, _completions, od = _make_engine(tmp_path, settings, db)

    fetch_calls: list[tuple[str, str]] = []
    pushes: list[str] = []

    budi_sent = _make_graph_msg(
        msg_id="g-budi-1",
        internet_id="<budi-1@wissentek.com>",
        subject="Budi sensor docs",
        sender="info@wissentek.com",
        to_addrs=["buyer@budi.de"],
        sent_utc="2026-11-24T02:20:00Z",
        body_preview="Attached datasheet.",
    )
    vandf_sent = _make_graph_msg(
        msg_id="g-vf-1",
        internet_id="<vf-sent-1@wissentek.com>",
        subject="V&F confirmation",
        sender="info@wissentek.com",
        to_addrs=["sales@vandf.com"],
        sent_utc="2026-11-24T02:25:00Z",
        body_preview="Confirmed.",
    )

    current_sent: list[dict[str, Any]] = [budi_sent, vandf_sent]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        fetch_calls.append((folder, since_utc))
        return list(current_sent) if folder == "sent" else []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        # (a) Corrupt JSON and no last_good_domains -> abort safely
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
            last_good_domains=None,
        )
        assert fetch_calls == []
        assert pushes == []
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 2, 0, 0, tzinfo=timezone.utc)
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 2, 0, 0, tzinfo=timezone.utc)

        # (b) Still corrupt JSON, WITH last_good_domains=("vandf.com",) -> falls back to vandf.com only
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
            last_good_domains=("vandf.com",),
        )
        assert len(pushes) == 1
        assert "sales@vandf.com" in pushes[0]
        assert "buyer@budi.de" not in pushes[0]

        # (c) Hot-reload: update mail_domains.json to include budi.de (no restart), next slot matches budi.de
        _write_domains(domains_path, ["vandf.com", "budi.de"])
        current_sent = [
            _make_graph_msg(
                msg_id="g-budi-2",
                internet_id="<budi-2@wissentek.com>",
                subject="Budi next slot mail",
                sender="info@wissentek.com",
                to_addrs=["buyer@budi.de"],
                sent_utc="2026-11-24T03:20:00Z",
                body_preview="Updated spec.",
            )
        ]
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 12, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
            last_good_domains=("vandf.com",),
        )
        assert len(pushes) == 2
        assert "buyer@budi.de" in pushes[1]
        assert "Budi next slot mail" in pushes[1]
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 7. Existing pending card defers inbox but still reports sent list
# ---------------------------------------------------------------------------


async def test_existing_pending_card_defers_inbox_but_still_sends_sent_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[边界+禁令] 已有未确认卡 #1 时，新收件不分拣、不标 seen、不前移 inbox 水位；已发送仍同条推送并标 seen、前移 sent 水位。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    card_id = db.save_pending_proposal(
        thread_id="owner",
        proposal_dict={"headline": "旧的待确认卡", "executive_summary": "待确认", "actions": []},
        source_ids=[],
    )
    assert card_id == 1

    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, completions, od = _make_engine(tmp_path, settings, db)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    inbox_msgs = [
        _make_graph_msg(
            msg_id="g-def-1",
            internet_id="<def-1@vandf.com>",
            subject="V&F 报价更新",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:15:00Z",
            body_preview="新报价",
        ),
        _make_graph_msg(
            msg_id="g-def-2",
            internet_id="<def-2@tera-instruments.com>",
            subject="Tera 交期",
            sender="ops@tera-instruments.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:30:00Z",
            body_preview="交期调整",
        ),
    ]
    sent_msgs = [
        _make_graph_msg(
            msg_id="g-sent-def-1",
            internet_id="<sent-def-1@wissentek.com>",
            subject="Re: Spectrometer delivery",
            sender="info@wissentek.com",
            to_addrs=["support@tera-instruments.com"],
            sent_utc="2026-11-24T02:40:00Z",
            body_preview="Got it.",
        )
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else sent_msgs

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # Triage NOT invoked; existing card #1 untouched (read-only digest may run safely without mutating DB)
        assert len(turn_calls) == 0
        pending = db.get_latest_pending_proposal("owner")
        assert pending is not None and pending["id"] == 1
        assert "【收件逐封明细（共 2 封）】" in pushes[0]
        assert "发件人：" in pushes[0] and "sales@vandf.com" in pushes[0]
        assert "主要内容：" in pushes[0] and "建议处理：【" in pushes[0]

        # Deferred inbox emails NOT marked seen & inbox watermark NOT advanced
        assert db.is_external_seen("<def-1@vandf.com>") is False
        assert db.is_external_seen("<def-2@tera-instruments.com>") is False
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 2, 0, 0, tzinfo=timezone.utc)

        # Sent email IS marked seen & sent watermark IS advanced
        assert db.is_external_seen("<sent-def-1@wissentek.com>") is True
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)

        # Single push mentions deferred inbox subjects, card #1, and sent list
        assert len(pushes) == 1
        msg = pushes[0]
        assert "V&F 报价更新" in msg
        assert "Tera 交期" in msg
        assert "#1" in msg
        assert "你发出 1 封（不建卡）" in msg
        assert "support@tera-instruments.com" in msg
        assert "Re: Spectrometer delivery" in msg
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 8. Push failure cancels new card and preserves watermark for next slot retry
# ---------------------------------------------------------------------------


async def test_push_failure_cancels_new_card_and_preserves_watermark_for_retry(tmp_path: Path) -> None:
    """[边界+禁令] 微信推送失败时，取消本班新建确认卡、不标 seen、不前移水位；下一班恢复后整批重试成功。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, _completions, od = _make_engine(tmp_path, settings, db)

    inbox_msgs = [
        _make_graph_msg(
            msg_id="g-retry-in",
            internet_id="<retry-in-1@vandf.com>",
            subject="V&F 紧急交期确认",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:25:00Z",
            body_preview="请确认本周五发货。",
        )
    ]
    sent_msgs = [
        _make_graph_msg(
            msg_id="g-retry-sent",
            internet_id="<retry-sent-1@wissentek.com>",
            subject="Re: Tera sensor",
            sender="info@wissentek.com",
            to_addrs=["support@tera-instruments.com"],
            sent_utc="2026-11-24T02:30:00Z",
            body_preview="Received.",
        )
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else sent_msgs

    attempts = {"n": 0}
    delivered: list[str] = []

    async def flaky_push(text: str) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("wecom push 502 bad gateway")
        delivered.append(text)

    try:
        # Slot 1 (11:00): push fails -> rollback new card, keep seen empty & watermarks unchanged
        try:
            await mail_poller.run_mail_window_once(
                settings=settings,
                db=db,
                od_client=od,
                engine=engine,
                send_push=flaky_push,
                now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
                domains_path=domains_path,
                fetch_folder=fake_fetch,
            )
        except RuntimeError:
            pass

        assert attempts["n"] == 1
        assert delivered == []
        assert db.get_latest_pending_proposal("owner") is None
        assert db.is_external_seen("<retry-in-1@vandf.com>") is False
        assert db.is_external_seen("<retry-sent-1@wissentek.com>") is False
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 2, 0, 0, tzinfo=timezone.utc)
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 2, 0, 0, tzinfo=timezone.utc)

        # Slot 2 (12:00): push recovers -> same emails appear and succeed
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=flaky_push,
            now_local=datetime(2026, 11, 24, 12, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        assert len(delivered) == 1
        assert db.get_latest_pending_proposal("owner") is not None
        assert db.is_external_seen("<retry-in-1@vandf.com>") is True
        assert db.is_external_seen("<retry-sent-1@wissentek.com>") is True
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 4, 0, 0, tzinfo=timezone.utc)
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 4, 0, 0, tzinfo=timezone.utc)
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 9. Noise and non-allowlist emails marked seen & advance watermark without push
# ---------------------------------------------------------------------------


async def test_noise_and_non_allowlist_marked_seen_without_push(tmp_path: Path) -> None:
    """[边界+禁令] 非白名单与退订噪音邮件不推微信、不调模型，但写入 seen 且正常前移水位。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, completions, od = _make_engine(tmp_path, settings, db)

    inbox_msgs = [
        _make_graph_msg(
            msg_id="g-noise-1",
            internet_id="<non-allow-1@randomvendor.com>",
            subject="Cloud discount",
            sender="news@randomvendor.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:10:00Z",
            body_preview="Save 50%",
        ),
        _make_graph_msg(
            msg_id="g-noise-2",
            internet_id="<unsub-1@vandf.com>",
            subject="V&F Newsletter",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:20:00Z",
            body_preview="Click to unsubscribe anytime.",
        ),
    ]
    sent_msgs = [
        _make_graph_msg(
            msg_id="g-noise-3",
            internet_id="<sent-other-1@wissentek.com>",
            subject="Dinner tonight",
            sender="info@wissentek.com",
            to_addrs=["friend@gmail.com"],
            sent_utc="2026-11-24T02:30:00Z",
            body_preview="See you at 7.",
        )
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else sent_msgs

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        assert pushes == []
        assert len(completions.calls) == 0
        assert db.get_latest_pending_proposal("owner") is None
        assert db.is_external_seen("<non-allow-1@randomvendor.com>") is True
        assert db.is_external_seen("<unsub-1@vandf.com>") is True
        assert db.is_external_seen("<sent-other-1@wissentek.com>") is True
        assert _parse_utc(db.get_mail_watermark("inbox")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)
        assert _parse_utc(db.get_mail_watermark("sent")) == datetime(2026, 11, 24, 3, 0, 0, tzinfo=timezone.utc)
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 10. Cap of 10 inbox emails leaves 11th for next slot with -2min watermark
# ---------------------------------------------------------------------------


async def test_inbox_cap_ten_leaves_eleventh_for_next_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[边界] 11 封命中收件时仅分析最旧 10 封，第 11 封不标 seen，且 inbox 水位停在第 11 封时间减 2 分钟。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, _completions, od = _make_engine(tmp_path, settings, db)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    # 11 emails from 02:05:00Z to 02:35:00Z (3-min step); pass in reverse order to test sorting
    base = datetime(2026, 11, 24, 2, 5, 0, tzinfo=timezone.utc)
    ordered_msgs = [
        _make_graph_msg(
            msg_id=f"g-cap-{i:02d}",
            internet_id=f"<cap-{i:02d}@vandf.com>",
            subject=f"CAP-MAIL-{i:02d}",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc=(base + timedelta(minutes=3 * (i - 1))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            body_preview=f"Body for mail {i:02d}",
        )
        for i in range(1, 12)
    ]
    eleventh_received = base + timedelta(minutes=30)  # 02:35:00Z
    unsorted_msgs = list(reversed(ordered_msgs))

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return unsorted_msgs if folder == "inbox" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        assert len(turn_calls) == 1
        assert len(pushes) == 1
        raw_batch = turn_calls[0]["raw_text"]

        # Oldest 10 included and marked seen
        for i in range(1, 11):
            assert f"CAP-MAIL-{i:02d}" in raw_batch
            assert db.is_external_seen(f"<cap-{i:02d}@vandf.com>") is True

        # 11th excluded, NOT marked seen, and watermark stopped at 11th receivedDateTime - 2min
        assert "CAP-MAIL-11" not in raw_batch
        assert db.is_external_seen("<cap-11@vandf.com>") is False
        assert _parse_utc(db.get_mail_watermark("inbox")) == eleventh_received - timedelta(minutes=2)
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 11. Duplicate internetMessageId in 2-minute overlap window skipped
# ---------------------------------------------------------------------------


async def test_duplicate_internet_message_id_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[边界] 2 分钟重叠查询窗口内已 seen 的 internetMessageId 不再重复分拣。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    db.mark_external_seen("<already-seen@vandf.com>")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    engine, _completions, od = _make_engine(tmp_path, settings, db)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    seen_msg = _make_graph_msg(
        msg_id="g-dup-1",
        internet_id="<already-seen@vandf.com>",
        subject="DUPLICATE-OLD-SUBJECT",
        sender="sales@vandf.com",
        to_addrs=["info@wissentek.com"],
        received_utc="2026-11-24T01:59:00Z",
        body_preview="Old content inside overlap window.",
    )
    fresh_msg = _make_graph_msg(
        msg_id="g-fresh-1",
        internet_id="<fresh-new@vandf.com>",
        subject="FRESH-NEW-SUBJECT",
        sender="sales@vandf.com",
        to_addrs=["info@wissentek.com"],
        received_utc="2026-11-24T02:20:00Z",
        body_preview="Brand new content.",
    )

    queried_since: dict[str, str] = {}

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        queried_since[folder] = since_utc
        return [seen_msg, fresh_msg] if folder == "inbox" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # Verify query uses watermark - 2 minutes overlap (01:58:00Z)
        assert _parse_utc(queried_since["inbox"]) == datetime(2026, 11, 24, 1, 58, 0, tzinfo=timezone.utc)
        assert len(turn_calls) == 1
        assert "DUPLICATE-OLD-SUBJECT" not in turn_calls[0]["raw_text"]
        assert "FRESH-NEW-SUBJECT" in turn_calls[0]["raw_text"]
        assert len(pushes) == 1

        # Next slot: returning the already-processed messages again causes 0 new triage & 0 new pushes
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 12, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )
        assert len(turn_calls) == 1
        assert len(pushes) == 1
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 12. Long sent list truncated (>1800 chars) while preserving full card text
# ---------------------------------------------------------------------------


async def test_long_sent_list_truncated_preserving_full_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[边界] 确认卡正文完整保留不截断，超长已发送列表在超过 1800 字时截断并附「另有 N 封已发送未列出」。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    db.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
    db.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
    domains_path = _write_domains(tmp_path / "mail_domains.json")

    long_summary = "长卡片核心分析：" + ("帕莫瑞与维森特技术条款与交期核对说明。" * 28) + "CARD-TAIL-SENTINEL"
    assert len(long_summary) < 800
    long_proposal = _default_proposal_json(
        headline="长确认卡完整保留验证",
        executive_summary=long_summary,
    )
    engine, _completions, od = _make_engine(tmp_path, settings, db, proposal_json=long_proposal)
    turn_calls = _spy_handle_turn(engine, monkeypatch)

    inbox_msgs = [
        _make_graph_msg(
            msg_id="g-trunc-in",
            internet_id="<trunc-in@vandf.com>",
            subject="V&F 技术条款确认",
            sender="sales@vandf.com",
            to_addrs=["info@wissentek.com"],
            received_utc="2026-11-24T02:10:00Z",
            body_preview="请查收条款更新。",
        )
    ]
    base_sent = datetime(2026, 11, 24, 2, 10, 0, tzinfo=timezone.utc)
    sent_msgs = [
        _make_graph_msg(
            msg_id=f"g-trunc-sent-{i:02d}",
            internet_id=f"<trunc-sent-{i:02d}@wissentek.com>",
            subject=f"SENT-ITEM-{i:02d} " + ("Spectrometer calibration and delivery schedule update " * 3),
            sender="info@wissentek.com",
            to_addrs=["support@tera-instruments.com"],
            sent_utc=(base_sent + timedelta(minutes=3 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            body_preview="Update sent.",
        )
        for i in range(1, 11)
    ]

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return inbox_msgs if folder == "inbox" else sent_msgs

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI),
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        assert len(turn_calls) == 1
        assert len(pushes) == 1
        full_card = turn_calls[0]["result"]["reply_text"].strip()
        pushed = pushes[0]

        # Full confirmation card preserved completely untouched (head, body, and action footer)
        for card_line in full_card.splitlines():
            if card_line.strip():
                assert card_line in pushed
        assert "CARD-TAIL-SENTINEL" in pushed
        # Total message capped at 1800 chars with omission counter
        assert len(pushed) <= 1800
        assert re.search(r"另有\s*\d+\s*封已发送未列出", pushed) is not None
        # Oldest kept first, newest omitted
        assert "SENT-ITEM-01" in pushed
        assert "SENT-ITEM-10" not in pushed
    finally:
        engine.close()


# ---------------------------------------------------------------------------
# 13. Backlog (>70 min) header wording on Monday 08:30 first run
# ---------------------------------------------------------------------------


async def test_monday_0830_first_run_uses_seed_watermark_and_backlog_header(tmp_path: Path) -> None:
    """[正常+边界] 周一 08:30 无历史水位时，以周五 21:00 UTC 减 2 分钟为起点，且标题标明「含此前未推送的邮件」。"""
    settings = _make_settings(tmp_path)
    db = Database(tmp_path / "app.db")
    domains_path = _write_domains(tmp_path / "mail_domains.json")
    engine, _completions, od = _make_engine(tmp_path, settings, db)

    queried_since: dict[str, str] = {}
    sent_weekend = _make_graph_msg(
        msg_id="g-wknd-sent",
        internet_id="<wknd-sent-1@wissentek.com>",
        subject="Friday night follow-up",
        sender="info@wissentek.com",
        to_addrs=["sales@vandf.com"],
        sent_utc="2026-11-20T14:30:00Z",  # Fri 22:30+08:00
        body_preview="Please confirm Monday call.",
    )

    async def fake_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        queried_since[folder] = since_utc
        return [sent_weekend] if folder == "sent" else []

    pushes: list[str] = []

    async def fake_push(text: str) -> None:
        pushes.append(text)

    mon_0830 = datetime(2026, 11, 23, 8, 30, tzinfo=SHANGHAI)
    try:
        await mail_poller.run_mail_window_once(
            settings=settings,
            db=db,
            od_client=od,
            engine=engine,
            send_push=fake_push,
            now_local=mon_0830,
            domains_path=domains_path,
            fetch_folder=fake_fetch,
        )

        # Seed watermark is Fri 2026-11-20 13:00:00Z; query uses -2 min overlap -> 12:58:00Z
        expected_since = datetime(2026, 11, 20, 12, 58, 0, tzinfo=timezone.utc)
        assert _parse_utc(queried_since["inbox"]) == expected_since
        assert _parse_utc(queried_since["sent"]) == expected_since

        assert len(pushes) == 1
        assert "📧 邮件汇总（08:30，含此前未推送的邮件）" in pushes[0]
    finally:
        engine.close()
