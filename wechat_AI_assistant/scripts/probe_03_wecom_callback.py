#!/usr/bin/env python3
"""Stage 2 Probe 3: Verify WeCom App access_token, resolve open_kfid (wk...), and push test notification to WeChat Plugin."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

from wechat_assistant.config import Settings


def update_env_kv(path: Path, key: str, value: str) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    settings = Settings.load(require_bailian=False, require_wecom_secret=True)
    secret = settings.wecom_app_secret or settings.wecom_kf_secret

    with httpx.Client(timeout=15.0) as client:
        tok_resp = client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": settings.wecom_corp_id, "corpsecret": secret},
        ).json()
        if tok_resp.get("errcode", 0) != 0:
            raise RuntimeError(f"gettoken failed: errcode={tok_resp.get('errcode')} errmsg={tok_resp.get('errmsg')}")
        access_token = tok_resp["access_token"]
        print("[PROBE-3 token] gettoken OK")

        kf_list = client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/kf/account/list",
            params={"access_token": access_token},
            json={"offset": 0, "limit": 20},
        ).json()
        if kf_list.get("errcode", 0) != 0:
            raise RuntimeError(f"kf/account/list failed: {kf_list}")

        accounts = kf_list.get("account_list", [])
        if accounts:
            open_kfid = accounts[0]["open_kfid"]
            root = Path(__file__).resolve().parents[1]
            update_env_kv(root / "env/.env.wecom", "WECOM_KF_OPEN_KFID", open_kfid)
            update_env_kv(root / ".env", "WECOM_KF_OPEN_KFID", open_kfid)
            print(f"[PROBE-3 kf_account] count={len(accounts)} open_kfid_suffix=...{open_kfid[-6:]} manage_privilege={accounts[0].get('manage_privilege')}")

        if settings.wecom_app_agent_id:
            push = client.post(
                "https://qyapi.weixin.qq.com/cgi-bin/message/send",
                params={"access_token": access_token},
                json={
                    "touser": "@all",
                    "msgtype": "text",
                    "agentid": int(settings.wecom_app_agent_id),
                    "text": {"content": "✅ 【探针 T0】工作助理 → 微信插件 → 绿色个人微信下行主动推送已通！"},
                },
            ).json()
            if push.get("errcode", 0) != 0:
                raise RuntimeError(f"message/send failed: {push}")
            print(f"[PROBE-3 app_push] invaliduser={push.get('invaliduser', '')!r} OK")

    print("PROBE_03_API_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PROBE_03_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
