#!/usr/bin/env python3
"""Stage 2 Probe 2: Verify 21Vianet OneDrive directory init, overwrite, 6MB chunked upload, and 403 isolation."""

from __future__ import annotations

import base64
import json
import os
import sys
import time

import httpx
import msal

from wechat_assistant.config import Settings

PARA_DIRS = (
    "00_我的四大清单",
    "00_原件收件箱",
    "01_项目归档",
    "02_产品与研发",
    "03_公司运营",
    "04_想法与行业参考",
)


def decode_jwt_roles(token: str) -> list[str]:
    parts = token.split(".")
    if len(parts) < 2:
        return []
    padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    return list(payload.get("roles", []))


def ensure_folder(client: httpx.Client, graph_url: str, site_id: str, headers: dict, name: str) -> None:
    url = f"{graph_url}/sites/{site_id}/drive/root/children"
    resp = client.post(
        url,
        headers=headers,
        json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"},
    )
    if resp.status_code in (200, 201, 409):
        return
    resp.raise_for_status()


def acquire_token(settings: Settings) -> str:
    app = msal.ConfidentialClientApplication(
        settings.ms_client_id,
        authority=f"{settings.ms_auth_url.rstrip('/')}/{settings.ms_tenant_id}",
        client_credential=settings.ms_client_secret,
    )
    res = app.acquire_token_for_client(scopes=["https://microsoftgraph.chinacloudapi.cn/.default"])
    if "access_token" not in res:
        raise RuntimeError(f"MSAL error: {res.get('error')} - {res.get('error_description')}")
    return res["access_token"]


def main() -> int:
    settings = Settings.load(require_bailian=False, require_ms365=True)
    graph = settings.ms_graph_url.rstrip("/")

    # Wait briefly if AAD permission cache just revoked Sites.FullControl.All
    token = ""
    roles: list[str] = []
    for attempt in range(4):
        token = acquire_token(settings)
        roles = decode_jwt_roles(token)
        if "Sites.FullControl.All" not in roles:
            break
        print(f"[PROBE-2 wait] AAD token still contains Sites.FullControl.All (attempt {attempt + 1}/4), sleeping 15s...")
        time.sleep(15)

    print(f"[PROBE-2 token_roles] {roles}")
    assert "Sites.Selected" in roles, f"Expected Sites.Selected in JWT roles, got {roles}"
    assert "Sites.FullControl.All" not in roles, f"Sites.FullControl.All still present in JWT roles: {roles}"

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=45.0) as client:
        # 1. Init 6 root directories inside chairman-vault
        for dirname in PARA_DIRS:
            ensure_folder(client, graph, settings.ms_site_id, headers, dirname)
        print(f"[PROBE-2 dirs] initialized {len(PARA_DIRS)} PARA folders OK")

        # 2. Small file upload & overwrite + version check
        small_path = "00_我的四大清单/_probe_test.md"
        put_url = f"{graph}/sites/{settings.ms_site_id}/drive/root:/{small_path}:/content"
        r1 = client.put(put_url, headers={**headers, "Content-Type": "text/markdown"}, content=b"# Probe v1\n")
        r1.raise_for_status()
        r2 = client.put(put_url, headers={**headers, "Content-Type": "text/markdown"}, content=b"# Probe v2\n")
        r2.raise_for_status()
        item_id = r2.json()["id"]
        ver_resp = client.get(f"{graph}/sites/{settings.ms_site_id}/drive/items/{item_id}/versions", headers=headers)
        ver_resp.raise_for_status()
        versions = ver_resp.json().get("value", [])
        assert len(versions) >= 1, "Expected version history on overwritten markdown file"
        client.delete(f"{graph}/sites/{settings.ms_site_id}/drive/items/{item_id}", headers=headers).raise_for_status()
        print(f"[PROBE-2 small_file] upload/overwrite/versions({len(versions)})/cleanup OK")

        # 3. 6 MB chunked upload session
        total_size = 6 * 1024 * 1024
        payload = os.urandom(total_size)
        big_path = "00_原件收件箱/_probe_6mb.bin"
        sess_resp = client.post(
            f"{graph}/sites/{settings.ms_site_id}/drive/root:/{big_path}:/createUploadSession",
            headers=headers,
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        )
        sess_resp.raise_for_status()
        upload_url = sess_resp.json()["uploadUrl"]

        chunk_size = 2 * 1024 * 1024
        uploaded_item = None
        for start in range(0, total_size, chunk_size):
            end = min(start + chunk_size, total_size) - 1
            cr = client.put(
                upload_url,
                headers={
                    "Content-Length": str(end - start + 1),
                    "Content-Range": f"bytes {start}-{end}/{total_size}",
                },
                content=payload[start : end + 1],
            )
            cr.raise_for_status()
            if cr.status_code in (200, 201):
                uploaded_item = cr.json()

        assert uploaded_item is not None and uploaded_item.get("size") == total_size, "6MB size mismatch"
        client.delete(
            f"{graph}/sites/{settings.ms_site_id}/drive/items/{uploaded_item['id']}",
            headers=headers,
        ).raise_for_status()
        print(f"[PROBE-2 chunked_6mb] size={uploaded_item['size']} bytes verified & cleaned OK")

        # 4. Negative cross-site access test (must return 403)
        neg_root = client.get(f"{graph}/sites/root/drive", headers=headers)
        neg_tenant = client.get(f"{graph}/sites/wissentek.sharepoint.cn/drive", headers=headers)
        print(f"[PROBE-2 isolation] sites/root/drive={neg_root.status_code}, tenant_root/drive={neg_tenant.status_code}")
        assert neg_root.status_code == 403, f"Expected 403 on root site drive, got {neg_root.status_code}"
        assert neg_tenant.status_code == 403, f"Expected 403 on tenant site drive, got {neg_tenant.status_code}"

    print("PROBE_02_ALL_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PROBE_02_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
