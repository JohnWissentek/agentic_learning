"""Phase 2 optional read-only 21Vianet Graph Mail poller with prompt-injection fencing."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import httpx

from wechat_assistant.config import Settings
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient

_NOISE_HINTS = ("unsubscribe", "退订", "验证码", "verification code", "noreply", "no-reply")


def wrap_untrusted_email(subject: str, sender: str, body_preview: str) -> str:
    """Wrap external email text inside strict `[UNTRUSTED_EXTERNAL_DATA]` boundaries."""
    return (
        "[UNTRUSTED_EXTERNAL_DATA]\n"
        f"邮件主题：{subject}\n"
        f"发件人：{sender}\n"
        f"正文摘要：{body_preview[:2500]}\n"
        "[/UNTRUSTED_EXTERNAL_DATA]"
    )


async def poll_mailbox_once(
    settings: Settings,
    od_client: OneDrive21VianetClient,
    on_email: Callable[[str, str, str], Awaitable[None]],
) -> int:
    """Poll recent messages via read-only Mail.Read and deduplicate on internetMessageId."""
    if not settings.mail_enabled:
        return 0
    token = od_client._get_token()
    url = f"{settings.ms_graph_url.rstrip('/')}/users/{settings.mail_user}/messages"
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"$top": "5", "$select": "id,internetMessageId,subject,from,bodyPreview,receivedDateTime"},
        )
        r.raise_for_status()
        msgs: list[dict[str, Any]] = r.json().get("value", [])

    processed = 0
    for m in msgs:
        subj = m.get("subject") or ""
        sender = m.get("from", {}).get("emailAddress", {}).get("address", "")
        preview = m.get("bodyPreview") or ""
        combined_lower = f"{subj} {sender} {preview}".lower()
        if any(h in combined_lower for h in _NOISE_HINTS):
            continue
        ext_id = m.get("internetMessageId") or m.get("id", "")
        wrapped = wrap_untrusted_email(subj, sender, preview)
        await on_email(wrapped, sender, ext_id)
        processed += 1
    return processed


async def mail_poller_loop(
    settings: Settings,
    od_client: OneDrive21VianetClient,
    on_email: Callable[[str, str, str], Awaitable[None]],
    interval_seconds: int = 120,
) -> None:
    while True:
        try:
            await poll_mailbox_once(settings, od_client, on_email)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
