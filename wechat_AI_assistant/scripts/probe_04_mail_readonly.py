#!/usr/bin/env python3
"""Stage 2 Probe 4: Verify Global/HK or 21Vianet Graph Mail.Read (metadata only, zero content printed) and 403 Send prohibition."""

from __future__ import annotations

import sys

import httpx
import msal

from wechat_assistant.config import Settings


def main() -> int:
    settings = Settings.load(require_bailian=False, require_ms365=False)
    if settings.mail_tenant_id and settings.mail_client_id and settings.mail_client_secret:
        client_id = settings.mail_client_id
        tenant_id = settings.mail_tenant_id
        client_secret = settings.mail_client_secret
        auth_url = settings.mail_auth_url.rstrip("/")
        graph = settings.mail_graph_url.rstrip("/")
        scope = "https://graph.microsoft.com/.default"
        cloud_label = "global_hk"
    else:
        settings = Settings.load(require_bailian=False, require_ms365=True)
        client_id = settings.ms_client_id
        tenant_id = settings.ms_tenant_id
        client_secret = settings.ms_client_secret
        auth_url = settings.ms_auth_url.rstrip("/")
        graph = settings.ms_graph_url.rstrip("/")
        scope = "https://microsoftgraph.chinacloudapi.cn/.default"
        cloud_label = "china_21vianet"

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"{auth_url}/{tenant_id}",
        client_credential=client_secret,
    )
    tok = app.acquire_token_for_client(scopes=[scope])
    if "access_token" not in tok:
        raise RuntimeError(f"MSAL ({cloud_label}) error: {tok.get('error')} - {tok.get('error_description', '')}")

    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    mailbox = settings.mail_user
    if not mailbox:
        raise RuntimeError("MAIL_USER is empty; set the target Outlook email address in env/.env.ms365")

    with httpx.Client(timeout=30.0) as client:
        # 1. Read-only listing (never log subject, sender, or body)
        r_read = client.get(
            f"{graph}/users/{mailbox}/messages",
            headers=headers,
            params={"$top": "3", "$select": "id,internetMessageId,receivedDateTime,hasAttachments"},
        )
        r_read.raise_for_status()
        msgs = r_read.json().get("value", [])
        with_msg_id = sum(1 for m in msgs if m.get("internetMessageId"))
        with_att = sum(1 for m in msgs if m.get("hasAttachments"))
        print(
            f"[PROBE-4 mail_read cloud={cloud_label} mailbox={mailbox}] "
            f"status={r_read.status_code} fetched={len(msgs)} has_internet_id={with_msg_id} with_attachments={with_att}"
        )

        # 2. Negative outbound send test (must return 403)
        r_send = client.post(
            f"{graph}/users/{mailbox}/sendMail",
            headers=headers,
            json={
                "message": {
                    "subject": "probe-should-fail-403",
                    "body": {"contentType": "Text", "content": "forbidden"},
                    "toRecipients": [{"emailAddress": {"address": mailbox}}],
                }
            },
        )
        print(f"[PROBE-4 mail_send_negative] status={r_send.status_code}")
        assert r_send.status_code == 403, f"Expected 403 on sendMail, got {r_send.status_code}"

    print("PROBE_04_ALL_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PROBE_04_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
