"""Group 4 21Vianet OneDrive Graph Client and pure Markdown 4-list board renderer."""

from __future__ import annotations

import os
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import msal
import requests

from wechat_assistant.config import Settings, today_local
from wechat_assistant.schemas import ListType
from wechat_assistant.storage.db import Database


class _TimeoutRequestsSession(requests.Session):
    """Requests session enforcing a bounded default timeout for MSAL token calls."""

    def __init__(self, timeout: float = 20.0) -> None:
        super().__init__()
        self._default_timeout = timeout

    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, *args, **kwargs)


def render_lists_markdown(db: Database) -> dict[str, str]:
    """Render the 5 Markdown executive boards purely from SQLite state (v2.0 flat task cards)."""
    items = db.list_items(include_done=True)
    projects = db.list_projects()
    rules = db.list_memory_rules()

    # 1. 01_今日与行动待办.md
    action_types = {ListType.PROJECT_ACTION.value, ListType.NEXT_ACTION.value}
    actions = [i for i in items if i["list_type"] in action_types]
    open_actions = [i for i in actions if i["status"] != "done"]
    lines_01 = [
        "# 01｜今日与行动待办（自动重绘）\n",
        f"> 当前未完成行动项：**{len(open_actions)} 项**\n",
        "| ID | 优先级 | 状态 | 任务与交付成果 | 归属项目/板块 | 负责人 / 实施人 / 外部 | 计划起止周期 | 计划/实际完成跨度 |",
        "| :---: | :---: | :---: | :--- | :--- | :--- | :--- | :---: |",
    ]
    for it in actions:
        status_icon = "✅ 已完成" if it["status"] == "done" else ("🔄 进行中" if it["status"] == "in_progress" else "⬜ 待办")
        pe_disp = it["planned_end_at"] or "【待补齐】"
        span = f"{it['planned_start_at'] or '-'} ~ {pe_disp}"
        try:
            from datetime import date as _d
            ps = _d.fromisoformat((it["planned_start_at"] or "")[:10])
            pe = _d.fromisoformat((it["planned_end_at"] or it["planned_start_at"] or "")[:10])
            p_days = max(1, (pe - ps).days + 1)
        except ValueError:
            p_days = 1
        span_col = f"计划 {p_days} 天" if it["planned_end_at"] else "待补齐"
        if it["status"] == "done":
            try:
                from datetime import date as _d
                a_s = _d.fromisoformat((it.get("actual_start_at") or it["planned_start_at"] or it["created_at"])[:10])
                a_e = _d.fromisoformat((it.get("actual_end_at") or it["updated_at"])[:10])
                a_days = max(1, (a_e - a_s).days + 1)
                span_col = f"实耗 {a_days} 天"
                if (it.get("actual_hours") or 0) > 0:
                    span_col += f"（实{it['actual_hours']}h）"
            except ValueError:
                span_col = "已完成"
        deliv = (it.get("deliverable") or "").strip()
        src_lbl = {"outlook": "Outlook", "web": "驾驶舱"}.get(str(it.get("source_channel") or "wechat").lower(), "微信")
        title_cell = f"[{src_lbl}] {it['title']}" + (f"<br>成果：{deliv}" if deliv and deliv != it["title"] else "")
        role_cell = f"{it['owner']} / {it.get('assignee') or it['owner']} / {it.get('external_partner') or '无'}"
        lines_01.append(
            f"| {it['id']} | **{it['priority']}** | {status_icon} | {title_cell} | {it['project_name']}（{it['work_domain']}） | {role_cell} | {span} | {span_col} |"
        )
    if not actions:
        lines_01.append("| - | - | - | 暂无行动待办 | - | - | - | - |")

    # 2. 02_在途项目总览.md
    lines_02 = [
        "# 02｜在途项目总览（自动重绘）\n",
        "| 项目名称 | 板块 | 状态 | 计划周期 | 事项统计 | 最新进展 | 云端文件夹 |",
        "| :--- | :--- | :---: | :--- | :---: | :--- | :--- |",
    ]
    for p in projects:
        span = f"{p['planned_start_date'] or '-'} ~ {p['target_end_date'] or '-'}"
        p_items = [x for x in items if x.get("project_name") == p["name"]]
        p_done = sum(1 for x in p_items if x["status"] == "done")
        stat_str = f"共 {len(p_items)} 项（完成 {p_done}）"
        link = f"[打开云端目录]({p['onedrive_web_url']})" if p.get("onedrive_web_url") else p.get("onedrive_folder", "-")
        lines_02.append(
            f"| **{p['name']}** | {p['work_domain']} | {p['status']} | {span} | {stat_str} | {p['latest_brief'] or '-'} | {link} |"
        )
    if not projects:
        lines_02.append("| 暂无在途项目 | - | - | - | - | - | - |")

    # 3. 03_想法与孵化池.md
    ideas = [i for i in items if i["list_type"] == ListType.IDEA.value]
    lines_03 = ["# 03｜想法与孵化池（自动重绘）\n"]
    for stage_name in ("闪念收集", "调研评估", "准备立项", "留存参考"):
        lines_03.append(f"## {stage_name}")
        matched = [i for i in ideas if i.get("stage", "闪念收集") == stage_name]
        if not matched:
            lines_03.append("- （暂无）\n")
        else:
            for it in matched:
                lines_03.append(
                    f"- `#{it['id']}` **[{it['project_name']}]** {it['title']}（{it['work_domain']}）"
                )
            lines_03.append("")

    # 4. 04_等待他人清单.md
    waits = [i for i in items if i["list_type"] == ListType.WAITING_FOR.value and i["status"] != "done"]
    lines_04 = [
        "# 04｜等待他人清单（自动重绘）\n",
        "| ID | 优先级 | 对方/责任人 | 等待事项 | 所属项目 | 启动~承诺日 | 已等待跨度 |",
        "| :---: | :---: | :--- | :--- | :--- | :--- | :---: |",
    ]
    for it in waits:
        span = f"{it['planned_start_at'] or '-'} ~ {it['planned_end_at'] or '-'}"
        try:
            from datetime import date as _d
            w_s = _d.fromisoformat((it["planned_start_at"] or it["created_at"])[:10])
            w_days = max(0, (today_local() - w_s).days)
        except ValueError:
            w_days = 0
        lines_04.append(
            f"| {it['id']} | **{it['priority']}** | {it['owner']} | {it['title']} | {it['project_name']} | {span} | {w_days} 天 |"
        )
    if not waits:
        lines_04.append("| - | - | - | 暂无外部卡点等待 | - | - | - |")

    # 5. 00_我的个人规则库.md
    lines_00 = ["# 00｜我的个人规则与工时校准库（自动重绘）\n"]
    if not rules:
        lines_00.append("- 暂无规则沉淀，完成打卡或纠偏后会自动累积。")
    else:
        for r in rules[:40]:
            lines_00.append(f"- `[{r['memory_kind']}]` {r['rule_text']}（{r['updated_at']}）")

    return {
        "00_我的个人规则库.md": "\n".join(lines_00) + "\n",
        "01_今日与行动待办.md": "\n".join(lines_01) + "\n",
        "02_在途项目总览.md": "\n".join(lines_02) + "\n",
        "03_想法与孵化池.md": "\n".join(lines_03) + "\n",
        "04_等待他人清单.md": "\n".join(lines_04) + "\n",
    }


class OneDrive21VianetClient:
    """Client for 21Vianet SharePoint/OneDrive (`Sites.Selected` scoped to `chairman-vault`)."""

    CHUNK_THRESHOLD = 4 * 1024 * 1024
    CHUNK_SIZE = 2 * 1024 * 1024

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.graph = settings.ms_graph_url.rstrip("/")
        self._lock = threading.Lock()
        self._token = ""
        self._token_exp = 0.0
        self._msal_app: msal.ConfidentialClientApplication | None = None

    def _get_token(self) -> str:
        with self._lock:
            now = time.time()
            if self._token and now < self._token_exp - 60:
                return self._token
            if self._msal_app is None:
                self._msal_app = msal.ConfidentialClientApplication(
                    self.settings.ms_client_id,
                    authority=f"{self.settings.ms_auth_url.rstrip('/')}/{self.settings.ms_tenant_id}",
                    client_credential=self.settings.ms_client_secret,
                    http_client=_TimeoutRequestsSession(timeout=20.0),
                )
            res = self._msal_app.acquire_token_for_client(
                scopes=["https://microsoftgraph.chinacloudapi.cn/.default"]
            )
            if "access_token" not in res:
                raise RuntimeError(f"MSAL error: {res.get('error')} - {res.get('error_description')}")
            self._token = res["access_token"]
            self._token_exp = now + int(res.get("expires_in", 3600))
            return self._token

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        hdr = {"Authorization": f"Bearer {self._get_token()}"}
        if extra:
            hdr.update(extra)
        return hdr

    @staticmethod
    def _encode_path(remote_path: str) -> str:
        parts = [urllib.parse.quote(p.strip("/")) for p in remote_path.strip("/").split("/") if p]
        return "/".join(parts)

    def upload_bytes(
        self,
        remote_path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload bytes cleanly using PUT (<4MB) or resumable createUploadSession (>=4MB)."""
        encoded = self._encode_path(remote_path)
        site_id = self.settings.ms_site_id

        with httpx.Client(timeout=60.0) as client:
            if len(data) < self.CHUNK_THRESHOLD:
                url = f"{self.graph}/sites/{site_id}/drive/root:/{encoded}:/content"
                r = client.put(url, headers=self._headers({"Content-Type": content_type}), content=data)
                r.raise_for_status()
                item = r.json()
                returned_size = item.get("size")
                if returned_size is not None and int(returned_size) != len(data):
                    raise RuntimeError(
                        f"Uploaded size mismatch for {remote_path}: expected={len(data)}, got={returned_size}"
                    )
                return item

            sess_url = f"{self.graph}/sites/{site_id}/drive/root:/{encoded}:/createUploadSession"
            sr = client.post(
                sess_url,
                headers=self._headers(),
                json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
            )
            sr.raise_for_status()
            upload_url = sr.json()["uploadUrl"]

            total = len(data)
            item: dict[str, Any] = {}
            for start in range(0, total, self.CHUNK_SIZE):
                end = min(start + self.CHUNK_SIZE, total) - 1
                cr = client.put(
                    upload_url,
                    headers={
                        "Content-Length": str(end - start + 1),
                        "Content-Range": f"bytes {start}-{end}/{total}",
                    },
                    content=data[start : end + 1],
                )
                cr.raise_for_status()
                if cr.status_code in (200, 201):
                    item = cr.json()

            if item.get("size") != total:
                raise RuntimeError(f"Uploaded size mismatch for {remote_path}: expected={total}, got={item.get('size')}")
            return item

    def upload_and_cleanup_local(self, remote_path: str, local_path: str | Path) -> dict[str, Any]:
        """Upload local temporary attachment to 21Vianet OneDrive, then delete local cache."""
        p = Path(local_path)
        data = p.read_bytes()
        item = self.upload_bytes(remote_path, data)
        if p.exists():
            os.remove(p)
        return item

    def list_onedrive_tree(self, folder_path: str = "") -> list[dict[str, Any]]:
        site_id = self.settings.ms_site_id
        encoded = self._encode_path(folder_path)
        if encoded:
            url = f"{self.graph}/sites/{site_id}/drive/root:/{encoded}:/children"
        else:
            url = f"{self.graph}/sites/{site_id}/drive/root/children"
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers=self._headers())
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json().get("value", [])

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        """Render all 5 Markdown boards and upload them into `00_我的四大清单/`."""
        rendered = render_lists_markdown(db)
        urls: dict[str, str] = {}
        for filename, md_text in rendered.items():
            item = self.upload_bytes(
                f"00_我的四大清单/{filename}",
                md_text.encode("utf-8"),
                content_type="text/markdown; charset=utf-8",
            )
            urls[filename] = item.get("webUrl", "")
        return urls

    def append_project_note(self, project_name: str, entry_md: str) -> dict[str, Any]:
        """Prepend or append a timestamped note to `01_项目归档/{project}/00_项目沟通与纪要.md`."""
        safe_proj = project_name.replace("/", "_").strip() or "日常事务"
        remote_path = f"01_项目归档/{safe_proj}/00_项目沟通与纪要.md"
        encoded = self._encode_path(remote_path)
        existing = ""
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.graph}/sites/{self.settings.ms_site_id}/drive/root:/{encoded}:/content", headers=self._headers())
            if r.status_code == 200:
                existing = r.text
        header = f"# {safe_proj}｜项目沟通与纪要\n\n" if not existing else ""
        updated = (header + existing).rstrip() + "\n\n" + entry_md.strip() + "\n"
        return self.upload_bytes(remote_path, updated.encode("utf-8"), content_type="text/markdown; charset=utf-8")
