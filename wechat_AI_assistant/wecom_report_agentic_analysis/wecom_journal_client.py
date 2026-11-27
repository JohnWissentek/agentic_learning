"""Deterministic WeCom Journal (汇报) two-step API client & control parser (Slice 0).

Implements the official Enterprise WeChat Journal endpoints:
  1. POST /cgi-bin/oa/journal/get_record_list   (with <=25-day window slicing & cursor pagination)
  2. POST /cgi-bin/oa/journal/get_record_detail (full structured control payload per journal_uuid)
  3. GET  /cgi-bin/department/list + /cgi-bin/user/list (employee directory mapping)

Production guardrails:
- Explicit `timeout` on every HTTP call + bounded exponential backoff retries (<= max_retries).
- Access token caching with single automatic refresh retry on WeCom `errcode == 42001`.
- Fail-fast `RuntimeError` on WeCom authorization/business errors (e.g. `301065`) — zero silent swallowing.
"""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any

import httpx

from wecom_report_agentic_analysis.schemas import (
    DEFAULT_WECOM_TEMPLATES,
    SyncResult,
    TemplateSpec,
    WeComReportRecord,
    WeComUserRecord,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage

logger = logging.getLogger(__name__)

_WECOM_BASE = "https://qyapi.weixin.qq.com"
_TZ_SHANGHAI = timezone(timedelta(hours=8))
_STYLE_SCRIPT_RE = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", flags=re.DOTALL | re.IGNORECASE)
_BR_P_RE = re.compile(r"</?(?:br|p|div|li|tr)\b[^>]*>", flags=re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_rich_text(raw: str) -> str:
    """Strip Microsoft Word / WeCom rich-text HTML markup into crisp plain text."""
    if not raw:
        return ""
    if "<" not in raw and "&" not in raw:
        return raw.strip()
    txt = _STYLE_SCRIPT_RE.sub("", raw)
    txt = _BR_P_RE.sub("\n", txt)
    txt = _HTML_TAG_RE.sub("", txt)
    txt = html.unescape(txt).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def slice_date_windows(
    start_ts: int,
    end_ts: int,
    max_window_days: int = 25,
) -> list[tuple[int, int]]:
    """Split `[start_ts, end_ts]` into contiguous, non-overlapping windows each <= `max_window_days`."""
    if start_ts > end_ts:
        raise ValueError(f"start_ts ({start_ts}) must be <= end_ts ({end_ts})")
    if max_window_days < 1 or max_window_days > 30:
        raise ValueError("max_window_days must be between 1 and 30 for WeCom Journal API")

    max_span = max_window_days * 86400
    windows: list[tuple[int, int]] = []
    cur = int(start_ts)
    end = int(end_ts)
    while cur <= end:
        w_end = min(cur + max_span - 1, end)
        windows.append((cur, w_end))
        cur = w_end + 1
    return windows


def _extract_localized_text(items: Any) -> str:
    """Extract preferred Chinese text from WeCom localized title/option arrays."""
    if isinstance(items, str):
        return items.strip()
    if not isinstance(items, list):
        return ""
    zh_texts: list[str] = []
    fallback_texts: list[str] = []
    for entry in items:
        if isinstance(entry, dict):
            txt = str(entry.get("text") or "").strip()
            if not txt:
                continue
            lang = str(entry.get("lang") or "").lower()
            if "zh" in lang:
                zh_texts.append(txt)
            else:
                fallback_texts.append(txt)
        elif isinstance(entry, str) and entry.strip():
            fallback_texts.append(entry.strip())
    return " / ".join(zh_texts or fallback_texts)


def _extract_control_value(control_type: str, value: dict[str, Any]) -> tuple[str, list[str]]:
    """Parse a single WeCom Journal `apply_data.contents` control into `(text_value, file_ids)`."""
    if not isinstance(value, dict):
        return ("", [])

    ctype = (control_type or "").strip()
    file_ids: list[str] = []

    if ctype in ("Text", "Textarea"):
        return (clean_rich_text(str(value.get("text") or "")), [])
    if ctype == "Number":
        num = value.get("new_number")
        if num is None or num == "":
            num = value.get("number")
        return (str(num).strip() if num is not None else "", [])
    if ctype == "Money":
        money = value.get("new_money")
        if money is None or money == "":
            money = value.get("money")
        return (str(money).strip() if money is not None else "", [])
    if ctype == "Date":
        date_obj = value.get("date") or {}
        ts = date_obj.get("s_timestamp")
        if ts:
            try:
                dt = datetime.fromtimestamp(int(ts), _TZ_SHANGHAI)
                return (dt.strftime("%Y-%m-%d"), [])
            except (ValueError, TypeError):
                pass
        return (str(date_obj.get("value") or "").strip(), [])
    if ctype == "Selector":
        sel = value.get("selector") or {}
        options = sel.get("options") or []
        labels = [_extract_localized_text(opt.get("value")) for opt in options if isinstance(opt, dict)]
        labels = [lbl for lbl in labels if lbl]
        return ("、".join(labels), [])
    if ctype == "File":
        files = value.get("files") or []
        for f in files:
            if isinstance(f, dict):
                fid = str(f.get("file_id") or f.get("media_id") or "").strip()
                if fid:
                    file_ids.append(fid)
        return (f"[附件 {len(file_ids)} 个]" if file_ids else "", file_ids)
    if ctype == "Contact":
        members = value.get("members") or []
        depts = value.get("departments") or []
        names = [str(m.get("name") or m.get("userid") or "").strip() for m in members if isinstance(m, dict)]
        names += [str(d.get("name") or d.get("openapi_id") or "").strip() for d in depts if isinstance(d, dict)]
        return ("、".join(n for n in names if n), [])
    if ctype == "Location":
        loc = value.get("location") or {}
        parts = [str(loc.get("title") or "").strip(), str(loc.get("address") or "").strip()]
        return (" ".join(p for p in parts if p), [])

    # Best-effort fallback for custom/nested controls (e.g. Table / Formula / Tips)
    for fallback_key in ("text", "new_number", "new_money"):
        val = value.get(fallback_key)
        if val is not None and str(val).strip():
            return (str(val).strip(), [])
    return ("", [])


def parse_journal_detail(
    raw_detail: dict[str, Any],
    *,
    template_spec: TemplateSpec,
    user_map: dict[str, WeComUserRecord] | None = None,
) -> WeComReportRecord:
    """Parse official WeCom `oa/journal/get_record_detail` `info` dict into `WeComReportRecord`."""
    info = raw_detail.get("info") if isinstance(raw_detail.get("info"), dict) else raw_detail
    journal_uuid = str(info.get("journal_uuid") or info.get("journaluuid") or "").strip()
    if not journal_uuid:
        raise ValueError("Missing journal_uuid in WeCom journal detail payload")

    report_time_raw = info.get("report_time")
    if report_time_raw is None:
        raise ValueError(f"Missing report_time for journal {journal_uuid}")
    dt_sh = datetime.fromtimestamp(int(report_time_raw), _TZ_SHANGHAI)
    report_date = dt_sh.strftime("%Y-%m-%d")
    submitted_at = dt_sh.isoformat(timespec="seconds")

    submitter_obj = info.get("submitter") or {}
    submitter_userid = str(
        submitter_obj.get("userid") if isinstance(submitter_obj, dict) else info.get("submitter_userid") or ""
    ).strip()
    if not submitter_userid:
        submitter_userid = "unknown"

    submitter_name = ""
    department = ""
    if user_map and submitter_userid in user_map:
        u = user_map[submitter_userid]
        submitter_name = u.name
        department = " / ".join(u.department_names)

    parsed_fields: dict[str, str] = {}
    plain_lines: list[str] = []
    attachment_media_ids: list[str] = []

    apply_data = info.get("apply_data") or {}
    contents = apply_data.get("contents") if isinstance(apply_data, dict) else []
    if isinstance(contents, list):
        for idx, item in enumerate(contents, start=1):
            if not isinstance(item, dict):
                continue
            control_type = str(item.get("control") or "")
            label = _extract_localized_text(item.get("title")) or str(item.get("id") or f"字段{idx}")
            text_val, file_ids = _extract_control_value(control_type, item.get("value") or {})
            if file_ids:
                attachment_media_ids.extend(file_ids)
            if text_val:
                if label in parsed_fields:
                    parsed_fields[label] = f"{parsed_fields[label]}；{text_val}"
                else:
                    parsed_fields[label] = text_val
                if control_type != "File":
                    plain_lines.append(f"{label}：{text_val}")

    return WeComReportRecord(
        journal_uuid=journal_uuid,
        template_id=template_spec.template_id,
        template_name=str(info.get("template_name") or template_spec.template_name).strip(),
        report_type=template_spec.report_type,
        submitter_userid=submitter_userid,
        submitter_name=submitter_name,
        department=department,
        report_date=report_date,
        submitted_at=submitted_at,
        parsed_fields=parsed_fields,
        plain_text="\n".join(plain_lines),
        attachment_media_ids=attachment_media_ids,
        raw_payload=dict(info),
    )


class WeComJournalClient:
    """Official two-step WeCom Journal (汇报) client with bounded retries & fail-fast errors."""

    def __init__(
        self,
        corpid: str,
        secret: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        if not corpid or not secret:
            raise ValueError("corpid and secret must be non-empty")
        self.corpid = corpid.strip()
        self.secret = secret.strip()
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=self.timeout)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def _http_call(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{_WECOM_BASE}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=self.timeout,
                )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"WeCom HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 0.5 * (2**attempt)
                    logger.warning("WeCom %s %s failed (attempt %d/%d): %s; retrying in %.1fs", method, path, attempt + 1, self.max_retries + 1, exc, wait)
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"WeCom {method} {path} failed after {self.max_retries + 1} attempts: {exc}") from exc
        raise RuntimeError(f"WeCom {method} {path} failed: {last_exc}")

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Fetch and cache the WeCom self-built app `access_token`."""
        now = time.time()
        if not force_refresh and self._access_token and now < self._token_expires_at:
            return self._access_token
        data = self._http_call(
            "GET",
            "/cgi-bin/gettoken",
            params={"corpid": self.corpid, "corpsecret": self.secret},
        )
        errcode = int(data.get("errcode", -1))
        if errcode != 0 or not data.get("access_token"):
            raise RuntimeError(
                f"WeCom gettoken failed: errcode={errcode}, errmsg={data.get('errmsg')}"
            )
        self._access_token = str(data["access_token"])
        self._token_expires_at = now + float(data.get("expires_in", 7200)) - 200.0
        return self._access_token

    def _call_authed(
        self,
        method: str,
        path: str,
        *,
        extra_params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated WeCom call with automatic single refresh on `errcode == 42001`."""
        for token_attempt in range(2):
            token = self.get_access_token(force_refresh=(token_attempt == 1))
            params = dict(extra_params or {})
            params["access_token"] = token
            data = self._http_call(method, path, params=params, json_body=json_body)
            errcode = int(data.get("errcode", -1))
            if errcode == 0:
                return data
            if errcode == 42001 and token_attempt == 0:
                logger.warning("WeCom access_token expired (42001) on %s; refreshing once", path)
                self._access_token = None
                self._token_expires_at = 0.0
                continue
            raise RuntimeError(
                f"WeCom API {path} error: errcode={errcode}, errmsg={data.get('errmsg')}"
            )
        raise RuntimeError(f"WeCom API {path} failed after token refresh")

    def fetch_users(self, department_id: int = 1) -> list[WeComUserRecord]:
        """Fetch department map + employee list for `userid -> name/department` resolution."""
        dept_map: dict[int, str] = {}
        try:
            dept_data = self._call_authed("GET", "/cgi-bin/department/list")
            for d in dept_data.get("department") or []:
                if isinstance(d, dict) and d.get("id") is not None:
                    dept_map[int(d["id"])] = str(d.get("name") or "").strip()
        except RuntimeError as exc:
            logger.warning("WeCom department/list unavailable (continuing without dept names): %s", exc)

        userlist: list[dict[str, Any]] = []
        try:
            data = self._call_authed(
                "GET",
                "/cgi-bin/user/list",
                extra_params={"department_id": department_id, "fetch_child": 1},
            )
            userlist = list(data.get("userlist") or [])
        except RuntimeError as exc:
            logger.warning("WeCom user/list unavailable (%s); trying user/simplelist fallback", exc)
            try:
                data = self._call_authed(
                    "GET",
                    "/cgi-bin/user/simplelist",
                    extra_params={"department_id": department_id, "fetch_child": 1},
                )
                userlist = list(data.get("userlist") or [])
            except RuntimeError as exc2:
                logger.warning("WeCom user/simplelist also unavailable: %s", exc2)
                return []

        records: list[WeComUserRecord] = []
        for u in userlist:
            if not isinstance(u, dict) or not u.get("userid"):
                continue
            raw_depts = u.get("department") or []
            dept_names = [dept_map[int(did)] for did in raw_depts if int(did) in dept_map and dept_map[int(did)]]
            records.append(
                WeComUserRecord(
                    userid=str(u["userid"]).strip(),
                    name=str(u.get("name") or u["userid"]).strip(),
                    department_names=dept_names,
                    position=str(u.get("position") or "").strip(),
                    is_active=int(u.get("status", 1)) == 1,
                )
            )
        return records

    def fetch_record_uuids(
        self,
        template_id: str,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 100,
    ) -> list[str]:
        """Fetch all `journaluuid` entries for `template_id` over `[start_ts, end_ts]` using <=25-day slices."""
        page_limit = max(1, min(int(limit), 100))
        seen: set[str] = set()
        ordered_uuids: list[str] = []

        for w_start, w_end in slice_date_windows(start_ts, end_ts, max_window_days=25):
            cursor = 0
            while True:
                payload = {
                    "starttime": w_start,
                    "endtime": w_end,
                    "cursor": cursor,
                    "limit": page_limit,
                    "filters": [{"key": "template_id", "value": template_id}],
                }
                data = self._call_authed("POST", "/cgi-bin/oa/journal/get_record_list", json_body=payload)
                batch = data.get("journaluuid_list") or []
                for uid in batch:
                    s_uid = str(uid).strip()
                    if s_uid and s_uid not in seen:
                        seen.add(s_uid)
                        ordered_uuids.append(s_uid)

                endflag = int(data.get("endflag", 1))
                next_cursor = int(data.get("next_cursor", cursor))
                if endflag == 1 or not batch or next_cursor <= cursor:
                    break
                cursor = next_cursor

        return ordered_uuids

    def fetch_record_detail(self, journal_uuid: str) -> dict[str, Any]:
        """Fetch full structured journal detail for a single `journal_uuid`."""
        data = self._call_authed(
            "POST",
            "/cgi-bin/oa/journal/get_record_detail",
            json_body={"journaluuid": journal_uuid},
        )
        return dict(data.get("info") or data)

    def sync_reports_to_storage(
        self,
        storage: CompanyOpsStorage,
        *,
        start_date: str,
        end_date: str,
        templates: tuple[TemplateSpec, ...] = DEFAULT_WECOM_TEMPLATES,
    ) -> SyncResult:
        """End-to-end deterministic sync of WeCom Journal reports into `ops_*` SQLite tables."""
        d_start = date.fromisoformat(start_date[:10])
        d_end = date.fromisoformat(end_date[:10])
        start_ts = int(datetime.combine(d_start, dt_time(0, 0, 0), tzinfo=_TZ_SHANGHAI).timestamp())
        end_ts = int(datetime.combine(d_end, dt_time(23, 59, 59), tzinfo=_TZ_SHANGHAI).timestamp())

        users = self.fetch_users()
        users_synced = storage.upsert_users(users) if users else 0
        user_map = storage.get_user_map()

        existing_uuids = storage.get_existing_report_uuids()
        total_fetched = 0
        total_inserted = 0
        total_skipped = 0
        errors: list[str] = []

        for tpl in templates:
            uuids = self.fetch_record_uuids(tpl.template_id, start_ts, end_ts)
            total_fetched += len(uuids)
            new_uuids = [uid for uid in uuids if uid not in existing_uuids]
            total_skipped += len(uuids) - len(new_uuids)
            records: list[WeComReportRecord] = []
            for uid in new_uuids:
                raw_info = self.fetch_record_detail(uid)
                records.append(parse_journal_detail(raw_info, template_spec=tpl, user_map=user_map))
            ins, skip = storage.insert_reports(records)
            total_inserted += ins
            total_skipped += skip
            existing_uuids.update(new_uuids)

        return SyncResult(
            start_date=d_start.isoformat(),
            end_date=d_end.isoformat(),
            templates_queried=len(templates),
            records_fetched=total_fetched,
            records_inserted=total_inserted,
            records_skipped_duplicate=total_skipped,
            users_synced=users_synced,
            errors=errors,
        )
