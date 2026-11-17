#!/usr/bin/env python3
"""One-time idempotent site permission grant script for 21Vianet Sites.Selected isolation."""

from __future__ import annotations

import json
import sys
import urllib.request

import msal

from wechat_assistant.config import Settings


def main() -> int:
    settings = Settings.load(require_bailian=False, require_ms365=True)
    app = msal.ConfidentialClientApplication(
        settings.ms_client_id,
        authority=f"{settings.ms_auth_url.rstrip('/')}/{settings.ms_tenant_id}",
        client_credential=settings.ms_client_secret,
    )
    tok = app.acquire_token_for_client(scopes=["https://microsoftgraph.chinacloudapi.cn/.default"])
    if "access_token" not in tok:
        print(f"MSAL token acquisition failed: {tok.get('error')} - {tok.get('error_description')}", file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"Bearer {tok['access_token']}",
        "Content-Type": "application/json",
    }
    perm_url = f"{settings.ms_graph_url.rstrip('/')}/sites/{settings.ms_site_id}/permissions"
    with urllib.request.urlopen(urllib.request.Request(perm_url, headers=headers), timeout=15) as resp:
        existing = json.loads(resp.read().decode("utf-8")).get("value", [])

    already_granted = any(
        any(
            ident.get("application", {}).get("id") == settings.ms_client_id
            for ident in item.get("grantedToIdentitiesV2", item.get("grantedToIdentities", []))
        )
        for item in existing
    )
    if already_granted:
        print("Permission already granted for Wissentek-AI-Assistant on chairman-vault.")
        return 0

    payload = json.dumps({
        "roles": ["write"],
        "grantedToIdentities": [
            {
                "application": {
                    "id": settings.ms_client_id,
                    "displayName": "Wissentek-AI-Assistant",
                }
            }
        ],
    }).encode("utf-8")
    req = urllib.request.Request(perm_url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print(f"Granted site write permission: status={resp.status} roles={body.get('roles')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
