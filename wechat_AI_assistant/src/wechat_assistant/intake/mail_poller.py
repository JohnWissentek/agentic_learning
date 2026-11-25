"""Read-only Global/HK M365 Outlook Graph Mail hourly workday window poller, From/To/Cc role inference & threading."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import msal
import requests

from wechat_assistant.config import APP_TZ, Settings, now_local as app_now_local, redact_secrets
from wechat_assistant.prompts.system_prompts import MAIL_DIGEST_ONLY_PROMPT
from wechat_assistant.schemas import MailBatchDigest
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient

logger = logging.getLogger("uvicorn.error")

_NOISE_HINTS = ("unsubscribe", "退订", "验证码", "verification code", "noreply", "no-reply")

WORKDAY_MAIL_SLOTS: tuple[str, ...] = (
    "08:30",
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
)
MAIL_SLOT_WINDOW_MINUTES = 5
MAIL_OVERLAP_MINUTES = 2
MAX_INBOX_PER_SLOT = 10
MAX_SENT_PER_SLOT = 10
MAX_SUMMARY_PUSH_CHARS = 1800
_MAX_GRAPH_PAGES = 10

_REPLY_WAIT_HINTS: tuple[str, ...] = (
    "?",
    "？",
    "请回复",
    "请确认",
    "盼复",
    "please confirm",
    "please advise",
    "kindly advise",
)

DEFAULT_MAIL_DOMAINS_PATH = Path(__file__).resolve().parents[3] / "config" / "mail_domains.json"


class _TimeoutRequestsSession(requests.Session):
    """Requests session enforcing a bounded default timeout for MSAL token calls."""

    def __init__(self, timeout: float = 20.0) -> None:
        super().__init__()
        self._default_timeout = timeout

    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, *args, **kwargs)


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _extract_email_body_text(msg: dict[str, Any], *, max_chars: int = 2500) -> str:
    """Prefer full plain-text `body.content` over 255-char `bodyPreview`."""
    body_obj = msg.get("body") or {}
    raw_content = str(body_obj.get("content") or "").strip() if isinstance(body_obj, dict) else ""
    if raw_content:
        ctype = str(body_obj.get("contentType") or "").lower()
        if ctype == "html" or ("<html" in raw_content.lower() or "<div" in raw_content.lower() or "<br" in raw_content.lower()):
            raw_content = html.unescape(_HTML_TAG_RE.sub(" ", raw_content))
        cleaned = re.sub(r"[ \t\r]+", " ", raw_content)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            return cleaned[:max_chars]
    return (msg.get("bodyPreview") or "").strip()[:max_chars]


_BOUNDARY_TAG_RE = re.compile(
    r"\[/?(?:SYSTEM_TRUSTED_MAIL_META|UNTRUSTED_EXTERNAL_DATA)\]",
    flags=re.IGNORECASE,
)


def _sanitize_untrusted_boundary_tags(text: str) -> str:
    """Neutralize spoofed boundary tags inside untrusted external email fields."""
    return _BOUNDARY_TAG_RE.sub("〔已过滤边界标签〕", text or "")


def wrap_untrusted_email(
    subject: str,
    sender: str,
    body_preview: str,
    *,
    to_addrs: list[str] | None = None,
    cc_addrs: list[str] | None = None,
    timestamp: str = "",
    conversation_id: str = "",
    role_hint: dict[str, Any] | None = None,
    matched_task: dict[str, Any] | None = None,
    mail_ref: str = "",
) -> str:
    """Keep trusted system mail metadata OUTSIDE `[UNTRUSTED_EXTERNAL_DATA]`, wrapping only sanitized untrusted content."""
    clean_sender = _sanitize_untrusted_boundary_tags(sender)
    clean_subject = _sanitize_untrusted_boundary_tags(subject)
    clean_body = _sanitize_untrusted_boundary_tags(body_preview[:2500])

    meta_lines: list[str] = ["[SYSTEM_TRUSTED_MAIL_META]"]
    if mail_ref:
        meta_lines.append(f"邮件编号：{mail_ref}")
    meta_lines.append(f"发件人(From)：{clean_sender}")
    if to_addrs:
        meta_lines.append(f"主送(To)：{', '.join(_sanitize_untrusted_boundary_tags(a) for a in to_addrs)}")
    if cc_addrs:
        meta_lines.append(f"抄送(Cc)：{', '.join(_sanitize_untrusted_boundary_tags(a) for a in cc_addrs)}")
    if timestamp:
        meta_lines.append(f"时间：{timestamp}")
    if conversation_id:
        meta_lines.append(f"会话号(conversationId)：{_sanitize_untrusted_boundary_tags(conversation_id)}")
    if role_hint:
        meta_lines.append(
            f"角色推断提示：chairman_role={role_hint.get('chairman_role')}｜"
            f"建议负责人={role_hint.get('suggested_owner')}｜"
            f"建议实施人={role_hint.get('suggested_assignee')}｜"
            f"外部协作={role_hint.get('external_partner')}｜"
            f"依据：{role_hint.get('reason', '')}"
        )
    if matched_task:
        meta_lines.append(
            f"已绑定在途任务：#{matched_task['id']}《{_sanitize_untrusted_boundary_tags(str(matched_task.get('title', '')))}》"
            "（同一邮件会话，请优先通过 task_updates 追加时间轴，不要新建重复任务卡）"
        )
    meta_lines.append("[/SYSTEM_TRUSTED_MAIL_META]")

    untrusted_lines = [
        "[UNTRUSTED_EXTERNAL_DATA]",
        f"邮件主题：{clean_subject}",
        f"正文内容：{clean_body}",
        "[/UNTRUSTED_EXTERNAL_DATA]",
    ]
    return "\n".join(meta_lines + untrusted_lines)


def is_noise_email(msg: dict[str, Any]) -> bool:
    """Return True if an email looks like unsubscribe, verification code, or noreply noise."""
    subj = msg.get("subject") or ""
    sender = msg.get("from", {}).get("emailAddress", {}).get("address", "") or ""
    preview = msg.get("bodyPreview") or ""
    combined_lower = f"{subj} {sender} {preview}".lower()
    return any(h in combined_lower for h in _NOISE_HINTS)


def matches_mail_allowlist(msg: dict[str, Any], allowlist: tuple[str, ...]) -> bool:
    """Legacy substring matcher kept for backward compatibility with `poll_mailbox_once`."""
    if not allowlist or "*" in allowlist:
        return True
    parts: list[str] = [
        msg.get("subject") or "",
        msg.get("bodyPreview") or "",
    ]
    from_ea = msg.get("from", {}).get("emailAddress", {})
    parts.extend([from_ea.get("address") or "", from_ea.get("name") or ""])
    for field_name in ("toRecipients", "ccRecipients"):
        for rec in msg.get(field_name) or []:
            ea = rec.get("emailAddress", {})
            parts.extend([ea.get("address") or "", ea.get("name") or ""])
    haystack = " ".join(parts).lower()
    return any(tok.lower() in haystack for tok in allowlist if tok.strip())


def active_mail_slot(now_local: datetime) -> str | None:
    """Return the active workday slot (`HH:MM`) if within its 5-minute window, else None."""
    if now_local.weekday() >= 5:
        return None
    for slot in WORKDAY_MAIL_SLOTS:
        hour_s, min_s = slot.split(":")
        slot_dt = now_local.replace(hour=int(hour_s), minute=int(min_s), second=0, microsecond=0)
        delta_s = (now_local - slot_dt).total_seconds()
        if 0 <= delta_s < MAIL_SLOT_WINDOW_MINUTES * 60:
            return slot
    return None


def _ensure_aware_local(now_local: datetime | None) -> datetime:
    if now_local is None:
        return app_now_local()
    if now_local.tzinfo is None:
        return now_local.replace(tzinfo=APP_TZ)
    return now_local


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def seed_watermark_utc(now_local: datetime) -> str:
    """Compute initial UTC watermark when `mail_poll_cursor` has no prior record.

    - 08:30 slot: previous workday 21:00 local time (Monday -> last Friday 21:00).
    - 09:00-21:00 slots: today 08:30 local time.
    """
    local_dt = _ensure_aware_local(now_local)
    if (local_dt.hour, local_dt.minute) < (9, 0):
        days_back = 3 if local_dt.weekday() == 0 else 1
        prev_day = local_dt.date() - timedelta(days=days_back)
        seed_local = datetime(prev_day.year, prev_day.month, prev_day.day, 21, 0, 0, tzinfo=local_dt.tzinfo)
    else:
        seed_local = local_dt.replace(hour=8, minute=30, second=0, microsecond=0)
    return _format_utc(seed_local)


def _norm_domain_list(raw_list: Any) -> tuple[str, ...]:
    if not isinstance(raw_list, list):
        raise ValueError("domain list must be a JSON array")
    cleaned: list[str] = []
    for entry in raw_list:
        if not isinstance(entry, str):
            raise ValueError("each domain entry must be a string")
        d = entry.strip().lower().lstrip(".")
        if d and d not in cleaned:
            cleaned.append(d)
    return tuple(cleaned)


def load_mail_domain_groups(
    domains_path: str | Path | None = None,
    *,
    last_good: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, tuple[str, ...]] | None:
    """Load `domains`, `internal_domains`, and `partner_domains` from JSON (legacy compatible)."""
    path = Path(domains_path) if domains_path is not None else DEFAULT_MAIL_DOMAINS_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("mail_domains.json root must be an object")
        internal = _norm_domain_list(raw["internal_domains"]) if "internal_domains" in raw else ()
        partner = _norm_domain_list(raw["partner_domains"]) if "partner_domains" in raw else ()
        if "domains" in raw:
            domains = _norm_domain_list(raw["domains"])
        elif internal or partner:
            merged: list[str] = []
            for d in (*internal, *partner):
                if d not in merged:
                    merged.append(d)
            domains = tuple(merged)
        else:
            raise ValueError("mail_domains.json must contain a 'domains' list")
        return {
            "domains": domains,
            "internal_domains": internal,
            "partner_domains": partner,
        }
    except Exception as exc:
        logger.warning("Failed to load mail_domains.json (%s): %s", path, type(exc).__name__)
        return last_good


def load_mail_domains(
    domains_path: str | Path | None = None,
    *,
    last_good: tuple[str, ...] | None = None,
) -> tuple[str, ...] | None:
    """Reload allowed domains from JSON file; on error fall back to `last_good` (or None)."""
    fallback = (
        {"domains": last_good, "internal_domains": (), "partner_domains": ()}
        if last_good is not None
        else None
    )
    groups = load_mail_domain_groups(domains_path, last_good=fallback)
    if groups is None:
        return None
    return groups["domains"]


def _extract_email_addresses(msg: dict[str, Any]) -> list[str]:
    addrs: list[str] = []
    from_addr = (msg.get("from") or {}).get("emailAddress", {}).get("address") or ""
    if from_addr:
        addrs.append(from_addr)
    for field_name in ("toRecipients", "ccRecipients"):
        for rec in msg.get(field_name) or []:
            addr = (rec.get("emailAddress") or {}).get("address") or ""
            if addr:
                addrs.append(addr)
    return addrs


def _extract_field_addresses(msg: dict[str, Any], field_name: str) -> list[str]:
    out: list[str] = []
    for rec in msg.get(field_name) or []:
        addr = ((rec.get("emailAddress") or {}).get("address") or "").strip()
        if addr:
            out.append(addr)
    return out


def _domain_matches(addr: str, domains: tuple[str, ...]) -> bool:
    clean = (addr or "").strip().lower()
    if "@" not in clean or not domains:
        return False
    dom = clean.rsplit("@", 1)[1]
    return any(dom == d or dom.endswith(f".{d}") for d in domains)


def infer_email_role_hint(
    msg: dict[str, Any],
    *,
    self_email: str = "",
    internal_domains: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Deterministically infer Chairman's role & suggested owner/assignee from From/To/Cc.

    Strictly ensures that when the Chairman is only in Cc (not To), the Chairman is marked
    as `cc_observer` and NEVER assigned as `suggested_owner` or `suggested_assignee`.
    """
    self_norm = (self_email or "").strip().lower()
    norm_internal = tuple(d.strip().lower().lstrip(".") for d in internal_domains if d and d.strip())

    from_addr = ((msg.get("from") or {}).get("emailAddress") or {}).get("address", "").strip()
    to_addrs = _extract_field_addresses(msg, "toRecipients")
    cc_addrs = _extract_field_addresses(msg, "ccRecipients")

    from_norm = from_addr.lower()
    to_norms = [a.lower() for a in to_addrs]
    cc_norms = [a.lower() for a in cc_addrs]

    from_is_self = bool(self_norm and from_norm == self_norm)
    from_is_internal = (not from_is_self) and _domain_matches(from_addr, norm_internal)
    self_in_to = bool(self_norm and self_norm in to_norms)
    self_in_cc = bool(self_norm and self_norm in cc_norms and not self_in_to)

    internal_to = [a for a in to_addrs if a.lower() != self_norm and _domain_matches(a, norm_internal)]
    internal_cc = [a for a in cc_addrs if a.lower() != self_norm and _domain_matches(a, norm_internal)]
    external_to = [a for a in to_addrs if a.lower() != self_norm and not _domain_matches(a, norm_internal)]
    external_cc = [a for a in cc_addrs if a.lower() != self_norm and not _domain_matches(a, norm_internal)]

    if from_is_self:
        return {
            "chairman_role": "owner",
            "suggested_owner": "徐宏玮",
            "suggested_assignee": ", ".join(internal_to or internal_cc) or "本人",
            "external_partner": ", ".join(external_to or external_cc) or "无",
            "from_party": from_addr,
            "to_parties": to_addrs,
            "cc_parties": cc_addrs,
            "reason": "董事长本人主动发出的邮件",
        }

    # Case 1 & 2: Chairman is ONLY in Cc (not in To) -> strictly cc_observer, NEVER owner/assignee!
    if self_in_cc:
        if from_is_internal:
            # Internal colleague -> To internal colleague(s), Cc Chairman (internal delegation/sync)
            if internal_to and not external_to:
                assignee_str = ", ".join(internal_to)
                owner_str = internal_to[0]
                partner = ", ".join(external_cc) or "无"
                return {
                    "chairman_role": "cc_observer",
                    "suggested_owner": owner_str,
                    "suggested_assignee": assignee_str,
                    "external_partner": partner,
                    "from_party": from_addr,
                    "to_parties": to_addrs,
                    "cc_parties": cc_addrs,
                    "reason": f"内部同事({from_addr})主送同事({assignee_str})并仅抄送董事长，董事长为知情监督(cc_observer)，实施人为{assignee_str}",
                }
            # Internal colleague -> To external partner, Cc Chairman
            partner = ", ".join(external_to or external_cc) or "无"
            return {
                "chairman_role": "cc_observer",
                "suggested_owner": from_addr,
                "suggested_assignee": from_addr,
                "external_partner": partner,
                "from_party": from_addr,
                "to_parties": to_addrs,
                "cc_parties": cc_addrs,
                "reason": f"内部同事({from_addr})发给外部({partner})并仅抄送董事长，董事长为知情监督(cc_observer)，实施人为{from_addr}",
            }
        # External -> To colleague, Cc Chairman
        assignee_str = ", ".join(internal_to) if internal_to else "【待补齐】"
        owner_str = internal_to[0] if internal_to else "【待补齐】"
        return {
            "chairman_role": "cc_observer",
            "suggested_owner": owner_str,
            "suggested_assignee": assignee_str,
            "external_partner": from_addr or "无",
            "from_party": from_addr,
            "to_parties": to_addrs,
            "cc_parties": cc_addrs,
            "reason": f"外部({from_addr})主送同事({assignee_str})并仅抄送董事长，董事长为知情监督(cc_observer)，绝非执行人",
        }

    # Case 3: External -> Direct To Chairman (possibly also To/Cc internal colleagues)
    if self_in_to and not from_is_internal:
        colleagues: list[str] = []
        for c in (*internal_to, *internal_cc):
            if c not in colleagues:
                colleagues.append(c)
        assignee_hint = (
            f"【待补齐（同送/抄送含 {', '.join(colleagues)}，可指定）】"
            if colleagues
            else "本人"
        )
        return {
            "chairman_role": "owner",
            "suggested_owner": "徐宏玮",
            "suggested_assignee": assignee_hint,
            "external_partner": from_addr or "无",
            "from_party": from_addr,
            "to_parties": to_addrs,
            "cc_parties": cc_addrs,
            "reason": f"外部({from_addr})直接主送董事长，董事长为决策负责人(owner)",
        }

    # Case 4: Internal colleague -> Direct To Chairman (approval / escalation)
    if self_in_to and from_is_internal:
        return {
            "chairman_role": "approver",
            "suggested_owner": "徐宏玮",
            "suggested_assignee": from_addr,
            "external_partner": ", ".join(external_to or external_cc) or "无",
            "from_party": from_addr,
            "to_parties": to_addrs,
            "cc_parties": cc_addrs,
            "reason": f"内部同事({from_addr})直接主送董事长请示审批，董事长为拍板审批人(approver)，实施人为{from_addr}",
        }

    # Fallback when self_email wasn't explicitly matched
    return {
        "chairman_role": "cc_observer" if internal_to else "owner",
        "suggested_owner": internal_to[0] if internal_to else "徐宏玮",
        "suggested_assignee": ", ".join(internal_to) if internal_to else "【待补齐】",
        "external_partner": from_addr if not from_is_internal else (", ".join(external_to) or "无"),
        "from_party": from_addr,
        "to_parties": to_addrs,
        "cc_parties": cc_addrs,
        "reason": "按邮件收发人关系默认推断",
    }


def matches_domain_allowlist(
    msg: dict[str, Any],
    domains: tuple[str, ...] | list[str],
    *,
    self_email: str = "",
) -> bool:
    """Return True iff non-noise email has a non-self address matching a configured domain or subdomain."""
    if not domains:
        return False
    if is_noise_email(msg):
        return False
    norm_domains = tuple(d.strip().lower().lstrip(".") for d in domains if isinstance(d, str) and d.strip())
    if not norm_domains:
        return False
    self_norm = (self_email or "").strip().lower()
    for raw_addr in _extract_email_addresses(msg):
        addr = raw_addr.strip().lower()
        if not addr or "@" not in addr:
            continue
        if self_norm and addr == self_norm:
            continue
        domain = addr.rsplit("@", 1)[1]
        if any(domain == d or domain.endswith(f".{d}") for d in norm_domains):
            return True
    return False


def needs_reply_hint(subject: str, body_preview: str = "") -> bool:
    """Deterministic marker for sent emails that may be waiting on a counterpart reply."""
    hay = f"{subject or ''} {body_preview or ''}".lower()
    return any(tok in hay for tok in _REPLY_WAIT_HINTS)


_MAIL_APPS: dict[str, msal.ConfidentialClientApplication] = {}
_MAIL_APPS_LOCK = threading.Lock()


def _acquire_mail_token(settings: Settings, od_client: OneDrive21VianetClient | None) -> tuple[str, str]:
    """Return (bearer_token, graph_base_url) using dedicated Global M365 mail creds if configured."""
    if settings.mail_tenant_id and settings.mail_client_id and settings.mail_client_secret:
        with _MAIL_APPS_LOCK:
            app = _MAIL_APPS.get(settings.mail_client_id)
            if app is None:
                app = msal.ConfidentialClientApplication(
                    settings.mail_client_id,
                    authority=f"{settings.mail_auth_url.rstrip('/')}/{settings.mail_tenant_id}",
                    client_credential=settings.mail_client_secret,
                    http_client=_TimeoutRequestsSession(timeout=20.0),
                )
                _MAIL_APPS[settings.mail_client_id] = app
        res = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in res:
            raise RuntimeError(f"Global M365 mail token error: {res.get('error', 'unknown')}")
        return str(res["access_token"]), settings.mail_graph_url.rstrip("/")
    if od_client is None:
        raise RuntimeError("No M365 mail credentials or OneDrive client configured")
    return od_client._get_token(), settings.ms_graph_url.rstrip("/")


async def fetch_mail_folder_messages(
    settings: Settings,
    od_client: OneDrive21VianetClient | None,
    folder: str,
    since_utc: str,
) -> list[dict[str, Any]]:
    """Fetch messages incrementally from `inbox` or `sentitems` with pagination (`$top=50`)."""
    token, graph_base = await asyncio.to_thread(_acquire_mail_token, settings, od_client)
    is_sent = folder == "sent"
    graph_folder = "sentitems" if is_sent else "inbox"
    time_field = "sentDateTime" if is_sent else "receivedDateTime"
    url: str | None = f"{graph_base}/users/{settings.mail_user}/mailFolders/{graph_folder}/messages"
    params: dict[str, str] | None = {
        "$filter": f"{time_field} ge {since_utc}",
        "$orderby": f"{time_field} asc",
        "$top": "50",
        "$select": (
            "id,internetMessageId,conversationId,subject,from,toRecipients,ccRecipients,"
            "bodyPreview,body,hasAttachments,receivedDateTime,sentDateTime"
        ),
    }

    collected: list[dict[str, Any]] = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.body-content-type="text"',
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        for _ in range(_MAX_GRAPH_PAGES):
            if not url:
                break
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            payload = r.json()
            collected.extend(payload.get("value") or [])
            url = payload.get("@odata.nextLink")
            params = None
    return collected


def _msg_ext_id(msg: dict[str, Any]) -> str:
    return str(msg.get("internetMessageId") or msg.get("id") or "").strip()


def _msg_time_utc(msg: dict[str, Any], field: str) -> datetime:
    raw = msg.get(field) or msg.get("receivedDateTime") or msg.get("sentDateTime") or ""
    if raw:
        try:
            return _parse_utc(str(raw))
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _pick_sent_recipient(msg: dict[str, Any], self_email: str) -> str:
    self_norm = (self_email or "").strip().lower()
    fallback = ""
    for field_name in ("toRecipients", "ccRecipients"):
        for rec in msg.get(field_name) or []:
            addr = ((rec.get("emailAddress") or {}).get("address") or "").strip()
            if not addr:
                continue
            if not fallback:
                fallback = addr
            if not self_norm or addr.lower() != self_norm:
                return addr
    return fallback or "未知收件人"


def _format_sent_line(
    msg: dict[str, Any],
    local_tz: Any,
    self_email: str,
    *,
    matched_task_id: int | None = None,
) -> str:
    dt_utc = _msg_time_utc(msg, "sentDateTime")
    hhmm = dt_utc.astimezone(local_tz).strftime("%H:%M") if dt_utc.year > 1 else "--:--"
    recipient = _pick_sent_recipient(msg, self_email)
    cc_addrs = _extract_field_addresses(msg, "ccRecipients")
    cc_tag = f"（抄送：{', '.join(cc_addrs)}）" if cc_addrs else ""
    subj = (msg.get("subject") or "（无主题）").strip()
    preview = msg.get("bodyPreview") or ""
    bound_tag = f"｜已自动归入 #{matched_task_id}" if matched_task_id is not None else ""
    hint = "｜可能在等对方" if needs_reply_hint(subj, preview) else ""
    return f"- {hhmm} 发给 {recipient}{cc_tag}｜{subj}{bound_tag}{hint}"


def _summarize_mail_batch_readonly(engine: Any, batch_prompt: str) -> list[dict[str, Any]]:
    """Ask flagship brain for a read-only per-email digest without touching pending_proposals or DB."""
    gateway = getattr(engine, "gateway", None)
    if gateway is None:
        return []
    try:
        digest_obj, rec = gateway.generate_structured(
            "producer",
            [
                {"role": "system", "content": MAIL_DIGEST_ONLY_PROMPT},
                {"role": "user", "content": batch_prompt},
            ],
            MailBatchDigest,
            max_tokens=1536,
        )
        record_fn = getattr(engine, "_record_latest_call", None)
        if callable(record_fn):
            record_fn(rec)
        return [it.model_dump(mode="json") for it in digest_obj.items]
    except Exception as exc:
        logger.warning("Read-only mail batch digest fallback to deterministic summary: %s", type(exc).__name__)
        return []


def _split_card_footer(prefix: str) -> tuple[str, str]:
    """Split a confirmation card prefix into (body, footer) before warning/action lines."""
    for marker in (
        "\n\n⚠️ 缺失必填提示：",
        "\n\n⚠️ 负荷提醒：",
        "\n\n⚠️ 审计待人工复核点：",
        "\n\n📎 证据出处：",
        "\n\n👉 回复 1 确认落盘",
    ):
        idx = prefix.find(marker)
        if idx != -1:
            return prefix[:idx], prefix[idx:]
    return prefix, ""


def _compose_push_with_sent_cap(prefix: str, sent_lines: list[str], *, max_chars: int = MAX_SUMMARY_PUSH_CHARS) -> str:
    """Insert/append sent-mail summary lines without ever truncating `prefix` (the full decision card)."""
    if not sent_lines:
        return prefix
    total_sent = len(sent_lines)
    body, footer = _split_card_footer(prefix)
    has_card = bool(footer)
    heading = f"【四、你发出 {total_sent} 封（不建卡）】" if has_card else f"你发出 {total_sent} 封（不建卡）："
    sep = "\n\n" if body else ""

    def _assemble(sent_block: str) -> str:
        return f"{body}{sep}{sent_block}{footer}"

    full_msg = _assemble(f"{heading}\n" + "\n".join(sent_lines))
    if len(full_msg) <= max_chars:
        return full_msg

    for keep in range(total_sent - 1, 0, -1):
        omitted = total_sent - keep
        candidate = _assemble(
            f"{heading}\n"
            + "\n".join(sent_lines[:keep])
            + f"\n另有 {omitted} 封已发送未列出"
        )
        if len(candidate) <= max_chars:
            return candidate

    return _assemble(f"另有 {total_sent} 封已发送未列出")


def _build_inbox_batch_prompt(
    inbox_batch: list[dict[str, Any]],
    sent_lines: list[str],
    slot_label: str,
    *,
    local_tz: Any,
    self_email: str,
    internal_domains: tuple[str, ...],
    db: Database | None = None,
) -> str:
    blocks: list[str] = [
        f"以下是 {slot_label} 时段收到的 {len(inbox_batch)} 封白名单工作邮件，请按 From/To/Cc 角色推断与会话号合并分析并输出一份统一提案："
    ]
    for idx, msg in enumerate(inbox_batch, 1):
        subj = (msg.get("subject") or "（无主题）").strip()
        sender = ((msg.get("from") or {}).get("emailAddress") or {}).get("address") or "未知发件人"
        body_text = _extract_email_body_text(msg, max_chars=2500)
        to_addrs = _extract_field_addresses(msg, "toRecipients")
        cc_addrs = _extract_field_addresses(msg, "ccRecipients")
        conv_id = str(msg.get("conversationId") or "").strip()
        dt_utc = _msg_time_utc(msg, "receivedDateTime")
        ts_str = dt_utc.astimezone(local_tz).strftime("%Y-%m-%d %H:%M") if dt_utc.year > 1 else ""
        role_hint = infer_email_role_hint(msg, self_email=self_email, internal_domains=internal_domains)
        matched_task = db.find_task_by_mail_conversation_id(conv_id) if (db is not None and conv_id) else None
        wrapped = wrap_untrusted_email(
            subj,
            sender,
            body_text,
            to_addrs=to_addrs,
            cc_addrs=cc_addrs,
            timestamp=ts_str,
            conversation_id=conv_id,
            role_hint=role_hint,
            matched_task=matched_task,
            mail_ref=f"MAIL-{idx}",
        )
        blocks.append(f"【收件 {idx}/{len(inbox_batch)}】\n{wrapped}")

    if sent_lines:
        sent_wrapped = (
            "[UNTRUSTED_EXTERNAL_DATA]\n"
            + "\n".join(sent_lines)
            + "\n[/UNTRUSTED_EXTERNAL_DATA]"
        )
        blocks.append(
            "以下为你本时段已发送邮件的一行摘要，仅用于判断上述收件是否已经回复，严禁为已发送邮件新建待办：\n"
            + sent_wrapped
        )
    return "\n\n".join(blocks)


_QUOTE_CUT_RE = re.compile(
    r"(?:\n\s*-{3,}\s*(?:Original Message|原始邮件|Forwarded message).*$|\n\s*From:\s.*$|\n\s*发件人[:：]\s.*$|\n\s*On\s.+wrote:\s*$)",
    flags=re.IGNORECASE | re.DOTALL,
)


def _format_recipient_list(msg: dict[str, Any], field: str) -> str:
    """Format Graph recipient list deterministically as readable `Name(email)` or `email`."""
    entries: list[str] = []
    seen: set[str] = set()
    for rec in msg.get(field) or []:
        ea = rec.get("emailAddress") or {}
        addr = (ea.get("address") or "").strip()
        name = (ea.get("name") or "").strip()
        key = addr.lower() or name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if name and addr and name.lower() != addr.lower():
            entries.append(f"{name}({addr})")
        else:
            entries.append(addr or name)
    return "、".join(entries) if entries else "无"


def _format_sender_display(msg: dict[str, Any]) -> str:
    ea = (msg.get("from") or {}).get("emailAddress") or {}
    addr = (ea.get("address") or "").strip()
    name = (ea.get("name") or "").strip()
    if name and addr and name.lower() != addr.lower():
        return f"{name}({addr})"
    return addr or name or "未知发件人"


def _extract_clean_mail_snippet(msg: dict[str, Any], max_chars: int = 140) -> str:
    """Extract concise non-quoted body summary deterministically for fallback/deferred mail digest."""
    raw = _extract_email_body_text(msg, max_chars=1200)
    cut = _QUOTE_CUT_RE.sub("", raw).strip()
    compact = re.sub(r"\s+", " ", cut).strip()
    if not compact:
        compact = "（正文为空，请查看原件或附件）"
    elif len(compact) > max_chars:
        compact = compact[: max_chars - 1].rstrip() + "…"
    if msg.get("hasAttachments"):
        compact = f"{compact} [含附件]"
    return compact


def _deterministic_action_advice(
    msg: dict[str, Any],
    *,
    role_hint: dict[str, Any],
    matched_task: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return `(action_type, action_advice)` deterministically from mail headers, body cues & task match."""
    subj = (msg.get("subject") or "").strip()
    body = _extract_email_body_text(msg, max_chars=800)
    role = role_hint.get("chairman_role") or "owner"
    colleague = role_hint.get("suggested_assignee") or role_hint.get("suggested_owner") or "相关同事"
    asks_reply = needs_reply_hint(subj, body) or any(
        kw in body for kw in ("请审阅", "请批复", "请确认", "请回复", "是否可行", "请指示", "请拍板")
    )

    if matched_task is not None:
        tid = matched_task["id"]
        title = str(matched_task.get("title") or "")[:24]
        if role == "cc_observer":
            return f"归入已有任务 #{tid}", f"已匹配在途任务 #{tid}《{title}》，您仅抄送，由 {colleague} 跟进并追加时间轴。"
        if asks_reply:
            return f"归入已有任务 #{tid}·需回复", f"已匹配在途任务 #{tid}《{title}》，建议回复对方并同步追加进展。"
        return f"归入已有任务 #{tid}", f"已匹配在途任务 #{tid}《{title}》，建议追加往来沟通时间轴持续跟踪。"

    if role == "cc_observer":
        return "团队跟进(仅抄送)", f"您仅被抄送，建议由 {colleague} 负责跟进处理，您知情监督即可。"
    if role == "approver":
        return "需回复/批复", f"内部同事（{colleague}）向您请示/汇报，建议审阅后给出批复意见并跟踪后续执行。"
    if asks_reply:
        return "需回复并跟踪", "对方明确期待回复/确认，建议尽快答复并视情况建卡跟踪截止日。"
    return "需查收跟进", "主送给您，建议查阅正文/附件后决定直接回复或建卡跟进。"


def format_mail_digest_section(
    inbox_batch: list[dict[str, Any]],
    *,
    local_tz: Any,
    self_email: str,
    internal_domains: tuple[str, ...],
    db: Database | None = None,
    llm_digests: list[dict[str, Any]] | None = None,
) -> str:
    """Render standardized 6-element per-email digest for EVERY email in the hourly batch.

    Fields guaranteed for every single email:
    1. 标题 (Title)  2. 发件人 (From)  3. 主送 (To)  4. 抄送 (Cc)  5. 主要内容  6. 建议处理
    """
    digest_by_ref: dict[str, dict[str, Any]] = {}
    for idx_d, d in enumerate(llm_digests or [], 1):
        if not isinstance(d, dict):
            continue
        ref = str(d.get("mail_ref") or f"MAIL-{idx_d}").strip().upper()
        digest_by_ref[ref] = d

    lines: list[str] = [f"【收件逐封明细（共 {len(inbox_batch)} 封）】"]
    for idx, msg in enumerate(inbox_batch, 1):
        ref_key = f"MAIL-{idx}"
        subj = (msg.get("subject") or "（无主题）").strip()
        dt_utc = _msg_time_utc(msg, "receivedDateTime")
        hhmm = dt_utc.astimezone(local_tz).strftime("%H:%M") if dt_utc.year > 1 else ""
        time_tag = f"（{hhmm}）" if hhmm else ""
        sender_disp = _format_sender_display(msg)
        to_disp = _format_recipient_list(msg, "toRecipients")
        cc_disp = _format_recipient_list(msg, "ccRecipients")

        role_hint = infer_email_role_hint(msg, self_email=self_email, internal_domains=internal_domains)
        conv_id = str(msg.get("conversationId") or "").strip()
        matched_task = db.find_task_by_mail_conversation_id(conv_id) if (db is not None and conv_id) else None

        llm_d = digest_by_ref.get(ref_key)
        if llm_d and str(llm_d.get("main_content") or "").strip():
            main_content = str(llm_d["main_content"]).strip()
            if msg.get("hasAttachments") and "附件" not in main_content:
                main_content = f"{main_content} [含附件]"
            act_type = str(llm_d.get("action_type") or "").strip()
            act_advice = str(llm_d.get("suggested_action") or llm_d.get("action_advice") or "").strip()
            if not act_type or not act_advice:
                fb_type, fb_advice = _deterministic_action_advice(msg, role_hint=role_hint, matched_task=matched_task)
                act_type = act_type or fb_type
                act_advice = act_advice or fb_advice
        else:
            main_content = _extract_clean_mail_snippet(msg, max_chars=140)
            act_type, act_advice = _deterministic_action_advice(msg, role_hint=role_hint, matched_task=matched_task)

        lines.append(f"{idx}. 《{subj}》{time_tag}")
        lines.append(f"   • 发件人：{sender_disp} ｜ 主送：{to_disp} ｜ 抄送：{cc_disp}")
        lines.append(f"   • 主要内容：{main_content}")
        lines.append(f"   • 建议处理：【{act_type}】{act_advice}")
    return "\n".join(lines)


def _record_sent_mail_timeline_matches(
    db: Database,
    matched_sent_pairs: list[tuple[int, dict[str, Any]]],
    local_tz: Any,
    self_email: str,
) -> None:
    """Append objective read-only `mail_out` timeline entries for sent mails bound to existing tasks."""
    for task_id, msg in matched_sent_pairs:
        dt_utc = _msg_time_utc(msg, "sentDateTime")
        ts_str = dt_utc.astimezone(local_tz).strftime("%Y-%m-%d %H:%M") if dt_utc.year > 1 else ""
        recipient = _pick_sent_recipient(msg, self_email)
        subj = (msg.get("subject") or "（无主题）").strip()
        preview = (msg.get("bodyPreview") or "").strip()[:140]
        summary = f"回复/发出邮件《{subj}》" + (f"：{preview}" if preview else "")
        db.append_task_timeline(
            task_id,
            summary=summary,
            channel="mail_out",
            from_party=self_email or "徐宏玮",
            to_party=recipient,
            cc_parties=_extract_field_addresses(msg, "ccRecipients"),
            timestamp=ts_str,
            source_ref=_msg_ext_id(msg),
            mail_conversation_id=str(msg.get("conversationId") or "").strip(),
        )


async def run_mail_window_once(
    *,
    settings: Settings,
    db: Database,
    od_client: OneDrive21VianetClient | None,
    engine: Any,
    send_push: Callable[[str], Awaitable[Any]],
    now_local: datetime | None = None,
    domains_path: str | Path | None = None,
    fetch_folder: Callable[[str, str], Awaitable[list[dict[str, Any]]]] | None = None,
    last_good_domains: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Execute one workday hourly mail summary batch according to the hourly window spec."""
    local_now = _ensure_aware_local(now_local)
    slot_label = active_mail_slot(local_now) or local_now.strftime("%H:%M")
    slot_start_utc_dt = local_now.astimezone(timezone.utc).replace(microsecond=0)
    slot_start_utc = _format_utc(slot_start_utc_dt)

    fallback_groups = (
        {"domains": last_good_domains, "internal_domains": (), "partner_domains": ()}
        if last_good_domains is not None
        else None
    )
    domain_groups = load_mail_domain_groups(domains_path, last_good=fallback_groups)
    if domain_groups is None:
        return {"ok": False, "reason": "invalid_domains_config", "domains": last_good_domains}
    domains = domain_groups["domains"]
    internal_domains = domain_groups["internal_domains"]
    if len(domains) == 0:
        return {"ok": True, "reason": "empty_domains", "domains": domains}

    inbox_wm_str = db.get_mail_watermark("inbox") or seed_watermark_utc(local_now)
    sent_wm_str = db.get_mail_watermark("sent") or seed_watermark_utc(local_now)
    inbox_wm_dt = _parse_utc(inbox_wm_str)
    sent_wm_dt = _parse_utc(sent_wm_str)

    is_backlog = (
        (slot_start_utc_dt - inbox_wm_dt) > timedelta(minutes=70)
        or (slot_start_utc_dt - sent_wm_dt) > timedelta(minutes=70)
    )
    header = (
        f"📧 邮件汇总（{slot_label}，含此前未推送的邮件）"
        if is_backlog
        else f"📧 邮件汇总（{slot_label}）"
    )

    inbox_since = _format_utc(inbox_wm_dt - timedelta(minutes=MAIL_OVERLAP_MINUTES))
    sent_since = _format_utc(sent_wm_dt - timedelta(minutes=MAIL_OVERLAP_MINUTES))

    async def _default_fetch(folder: str, since_utc: str) -> list[dict[str, Any]]:
        return await fetch_mail_folder_messages(settings, od_client, folder, since_utc)

    fetcher = fetch_folder or _default_fetch
    raw_inbox = await fetcher("inbox", inbox_since)
    raw_sent = await fetcher("sent", sent_since)

    def _filter_folder(
        msgs: list[dict[str, Any]],
        time_field: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        sorted_msgs = sorted(msgs, key=lambda m: _msg_time_utc(m, time_field))
        matched: list[dict[str, Any]] = []
        skipped_ids: list[str] = []
        local_seen: set[str] = set()
        for m in sorted_msgs:
            ext_id = _msg_ext_id(m)
            if not ext_id or ext_id in local_seen or db.is_external_seen(ext_id):
                continue
            local_seen.add(ext_id)
            if matches_domain_allowlist(m, domains, self_email=settings.mail_user):
                matched.append(m)
            else:
                skipped_ids.append(ext_id)
        return matched, skipped_ids

    inbox_matched, inbox_skipped_ids = _filter_folder(raw_inbox, "receivedDateTime")
    sent_matched, sent_skipped_ids = _filter_folder(raw_sent, "sentDateTime")

    inbox_batch = inbox_matched[:MAX_INBOX_PER_SLOT]
    inbox_overflow = inbox_matched[MAX_INBOX_PER_SLOT:]
    sent_batch = sent_matched[:MAX_SENT_PER_SLOT]
    sent_overflow = sent_matched[MAX_SENT_PER_SLOT:]

    inbox_target_wm = (
        _format_utc(_msg_time_utc(inbox_overflow[0], "receivedDateTime") - timedelta(minutes=MAIL_OVERLAP_MINUTES))
        if inbox_overflow
        else slot_start_utc
    )
    sent_target_wm = (
        _format_utc(_msg_time_utc(sent_overflow[0], "sentDateTime") - timedelta(minutes=MAIL_OVERLAP_MINUTES))
        if sent_overflow
        else slot_start_utc
    )

    if not inbox_batch and not sent_batch:
        for ext_id in inbox_skipped_ids + sent_skipped_ids:
            db.mark_external_seen(ext_id)
        db.set_mail_watermark("inbox", inbox_target_wm)
        db.set_mail_watermark("sent", sent_target_wm)
        return {"ok": True, "pushed": False, "domains": domains}

    # Match sent mails against existing bound task conversationIds
    sent_lines: list[str] = []
    matched_sent_pairs: list[tuple[int, dict[str, Any]]] = []
    for m in sent_batch:
        conv_id = str(m.get("conversationId") or "").strip()
        bound_task = db.find_task_by_mail_conversation_id(conv_id) if conv_id else None
        matched_id = int(bound_task["id"]) if bound_task is not None else None
        if matched_id is not None:
            matched_sent_pairs.append((matched_id, m))
        sent_lines.append(_format_sent_line(m, local_now.tzinfo, settings.mail_user, matched_task_id=matched_id))

    # Case 1: Sent-only batch (no inbox emails) -> 0 LLM calls, auto-append matched sent timelines
    if not inbox_batch:
        msg_text = _compose_push_with_sent_cap(header, sent_lines)
        await send_push(msg_text)
        _record_sent_mail_timeline_matches(db, matched_sent_pairs, local_now.tzinfo, settings.mail_user)
        for ext_id in inbox_skipped_ids + sent_skipped_ids + [_msg_ext_id(m) for m in sent_batch]:
            db.mark_external_seen(ext_id)
        db.set_mail_watermark("inbox", inbox_target_wm)
        db.set_mail_watermark("sent", sent_target_wm)
        return {"ok": True, "pushed": True, "domains": domains, "sent_count": len(sent_batch)}

    # Case 2 & 3: Check pending proposal and optionally run batched triage under engine._turn_lock
    batch_prompt = _build_inbox_batch_prompt(
        inbox_batch,
        sent_lines,
        slot_label,
        local_tz=local_now.tzinfo,
        self_email=settings.mail_user,
        internal_domains=internal_domains,
        db=db,
    )
    batch_ext_id = f"mail_batch:{local_now.strftime('%Y-%m-%d')}:{slot_label}:{_msg_ext_id(inbox_batch[0])}"

    def _check_and_maybe_triage() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        with engine._turn_lock:
            existing_pending = db.get_latest_pending_proposal("owner")
            if existing_pending is not None:
                return existing_pending, None
            reply = engine.handle_incoming_turn(
                batch_prompt,
                sender="mail:hourly_batch",
                external_msg_id=batch_ext_id,
                thread_id="owner",
                force_work_triage=True,
            )
            return None, reply

    existing_pending, triage_reply = await asyncio.to_thread(_check_and_maybe_triage)

    # Case 2: Deferred due to existing pending card -> STILL render standardized 6-field per-email digest!
    if existing_pending is not None:
        readonly_digests = await asyncio.to_thread(_summarize_mail_batch_readonly, engine, batch_prompt)
        digest_block = format_mail_digest_section(
            inbox_batch,
            local_tz=local_now.tzinfo,
            self_email=settings.mail_user,
            internal_domains=internal_domains,
            db=db,
            llm_digests=readonly_digests,
        )
        header_line = f"{header}｜收件 {len(inbox_batch)} 封" + (f" · 发件 {len(sent_batch)} 封" if sent_batch else "")
        defer_prefix = (
            f"{header_line}\n\n"
            f"{digest_block}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ 确认卡 #{existing_pending['id']} 还没回复，本班暂不生成新确认卡"
            f"（以上收件已逐封提炼要点；处理完 #{existing_pending['id']} 后，下一班自动深度分析立卡）。\n"
            "👉 回复 1 确认落盘 ｜ 0 作废 ｜ 或直接发自然语言调整当前确认卡"
        )
        msg_text = _compose_push_with_sent_cap(defer_prefix, sent_lines)
        await send_push(msg_text)
        _record_sent_mail_timeline_matches(db, matched_sent_pairs, local_now.tzinfo, settings.mail_user)
        for ext_id in inbox_skipped_ids + sent_skipped_ids + [_msg_ext_id(m) for m in sent_batch]:
            db.mark_external_seen(ext_id)
        db.set_mail_watermark("sent", sent_target_wm)
        return {
            "ok": True,
            "pushed": True,
            "deferred_inbox": True,
            "domains": domains,
            "sent_count": len(sent_batch),
        }

    # Case 3: Fresh batched triage completed; render standardized 6-field per-email digest + decision card
    assert triage_reply is not None
    created_pid = triage_reply.get("proposal_id")
    llm_digests: list[dict[str, Any]] | None = None
    if isinstance(triage_reply.get("mail_digests"), list) and triage_reply["mail_digests"]:
        llm_digests = triage_reply["mail_digests"]
    if llm_digests is None:
        dec_dict = triage_reply.get("decision")
        if isinstance(dec_dict, dict):
            prop_dict = dec_dict.get("proposal")
            if isinstance(prop_dict, dict) and isinstance(prop_dict.get("mail_digests"), list):
                llm_digests = prop_dict["mail_digests"]
    if llm_digests is None and created_pid is not None:
        saved_pending = db.get_latest_pending_proposal("owner")
        if saved_pending and isinstance(saved_pending.get("proposal"), dict):
            md = saved_pending["proposal"].get("mail_digests")
            if isinstance(md, list):
                llm_digests = md

    digest_block = format_mail_digest_section(
        inbox_batch,
        local_tz=local_now.tzinfo,
        self_email=settings.mail_user,
        internal_domains=internal_domains,
        db=db,
        llm_digests=llm_digests,
    )
    card_body = (triage_reply.get("reply_text") or "").strip()
    header_line = f"{header}｜收件 {len(inbox_batch)} 封" + (f" · 发件 {len(sent_batch)} 封" if sent_batch else "")
    prefix = (
        f"{header_line}\n\n{digest_block}\n\n━━━━━━━━━━━━━━━━━━━━\n{card_body}"
        if card_body
        else f"{header_line}\n\n{digest_block}"
    )
    msg_text = _compose_push_with_sent_cap(prefix, sent_lines)

    try:
        await send_push(msg_text)
    except Exception as exc:
        if created_pid is not None:
            db.cancel_pending_proposal(int(created_pid))
        logger.warning(
            "Hourly mail summary push failed (rolled back card #%s): %s",
            created_pid,
            redact_secrets(f"{type(exc).__name__}: {exc}", settings),
        )
        raise

    _record_sent_mail_timeline_matches(db, matched_sent_pairs, local_now.tzinfo, settings.mail_user)
    for ext_id in (
        inbox_skipped_ids
        + [_msg_ext_id(m) for m in inbox_batch]
        + sent_skipped_ids
        + [_msg_ext_id(m) for m in sent_batch]
    ):
        db.mark_external_seen(ext_id)
    db.set_mail_watermark("inbox", inbox_target_wm)
    db.set_mail_watermark("sent", sent_target_wm)
    return {
        "ok": True,
        "pushed": True,
        "proposal_id": created_pid,
        "inbox_count": len(inbox_batch),
        "sent_count": len(sent_batch),
        "domains": domains,
    }


async def mail_hourly_scheduler_loop(
    *,
    settings: Settings,
    db: Database,
    od_client: OneDrive21VianetClient | None,
    engine: Any,
    send_push: Callable[[str], Awaitable[Any]],
    domains_path: str | Path | None = None,
    poll_interval_seconds: float = 30.0,
) -> None:
    """Background workday hourly mail summary scheduler (08:30 + 09:00..21:00 local time)."""
    completed_slots: list[str] = []
    completed_set: set[str] = set()
    last_good_domains: tuple[str, ...] | None = None

    while True:
        try:
            now_local = app_now_local()
            slot = active_mail_slot(now_local)
            if slot is not None:
                slot_key = f"{now_local.strftime('%Y-%m-%d')}:{slot}"
                if slot_key not in completed_set:
                    res = await run_mail_window_once(
                        settings=settings,
                        db=db,
                        od_client=od_client,
                        engine=engine,
                        send_push=send_push,
                        now_local=now_local,
                        domains_path=domains_path,
                        last_good_domains=last_good_domains,
                    )
                    if res.get("domains") is not None:
                        last_good_domains = res["domains"]
                    if res.get("ok"):
                        completed_set.add(slot_key)
                        completed_slots.append(slot_key)
                        if len(completed_slots) > 64:
                            oldest = completed_slots.pop(0)
                            completed_set.discard(oldest)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Hourly mail scheduler error: %s",
                redact_secrets(f"{type(exc).__name__}: {exc}", settings),
            )
        await asyncio.sleep(poll_interval_seconds)


async def poll_mailbox_once(
    settings: Settings,
    od_client: OneDrive21VianetClient,
    on_email: Callable[[str, str, str], Awaitable[None]],
    *,
    mark_seen: Callable[[str], bool] | None = None,
) -> int:
    """Legacy single-message poller kept for backward compatibility with existing unit tests."""
    if not settings.mail_enabled:
        return 0
    token, graph_base = await asyncio.to_thread(_acquire_mail_token, settings, od_client)
    url = f"{graph_base}/users/{settings.mail_user}/messages"
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$top": "15",
                "$select": "id,internetMessageId,subject,from,toRecipients,ccRecipients,bodyPreview,receivedDateTime",
            },
        )
        r.raise_for_status()
        msgs: list[dict[str, Any]] = r.json().get("value", [])

    processed = 0
    for m in msgs:
        subj = m.get("subject") or ""
        sender = m.get("from", {}).get("emailAddress", {}).get("address", "")
        preview = m.get("bodyPreview") or ""
        if is_noise_email(m):
            continue
        if not matches_mail_allowlist(m, settings.mail_allowlist):
            continue
        ext_id = _msg_ext_id(m)
        bound_db = getattr(mark_seen, "__self__", None) if mark_seen is not None else None
        has_peek = bound_db is not None and hasattr(bound_db, "is_external_seen")
        if has_peek:
            if bound_db.is_external_seen(ext_id):
                continue
        elif mark_seen is not None and not mark_seen(ext_id):
            continue
        wrapped = wrap_untrusted_email(subj, sender, preview)
        await on_email(wrapped, sender, ext_id)
        if has_peek and mark_seen is not None:
            mark_seen(ext_id)
        processed += 1
    return processed


async def mail_poller_loop(
    settings: Settings,
    od_client: OneDrive21VianetClient,
    on_email: Callable[[str, str, str], Awaitable[None]],
    interval_seconds: int = 120,
    *,
    mark_seen: Callable[[str], bool] | None = None,
) -> None:
    """Legacy loop wrapper kept for backward compatibility."""
    while True:
        try:
            await poll_mailbox_once(settings, od_client, on_email, mark_seen=mark_seen)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Mail poller error: %s",
                redact_secrets(f"{type(exc).__name__}: {exc}", settings),
            )
        await asyncio.sleep(interval_seconds)
