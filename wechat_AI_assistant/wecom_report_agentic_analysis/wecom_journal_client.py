"""Deterministic WeCom Journal (汇报) two-step API client & control parser (Slice 0 + Slice A).

Implements the official Enterprise WeChat Journal endpoints:
  1. POST /cgi-bin/oa/journal/get_record_list   (with <=25-day window slicing & cursor pagination)
  2. POST /cgi-bin/oa/journal/get_record_detail (full structured control payload per journal_uuid)
  3. GET  /cgi-bin/department/list + /cgi-bin/user/list (employee directory mapping)

Slice A upgrades (2026-11-28 7-template system):
- Supports all 7 company templates (6 active + 1 disabled historical) + pre-2025 legacy backfill.
- Parses nested 7-column `Table` controls (with paired before/after photo metrics), `WedriveFile`,
  handwritten `Canvas`/`Signature` controls, R&D work hours, and completely filters `Tips` boilerplate.
- Preserves dual dates (`report_date` submission date vs `work_date` actual form date),
  `schema_era` (`legacy_v1` vs `upgraded_v2`), and `confidentiality_level` (`finance_restricted`).
- Watermark-driven resumable 25-day full backfill + active-only 7-day incremental sync.
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
    ALL_TEMPLATES_BY_ID,
    ALL_WECOM_TEMPLATES,
    DEFAULT_WECOM_TEMPLATES,
    NEW_TEMPLATE_EFFECTIVE_DATE,
    ReportType,
    SmartSyncResult,
    SyncResult,
    SyncWatermarkRecord,
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
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_WORK_DATE_TITLE_HINTS = ("工作日期", "现场服务日期", "现场工作日期", "晨会日期", "服务日期")
_BEFORE_PHOTO_HINTS = ("操作前", "更换前", "拆下", "旧件", "处理前", "维修前")
_AFTER_PHOTO_HINTS = ("操作后", "更换后", "换上", "新件", "最终", "整机", "处理后", "维修后", "安装位置")
_SIGNATURE_CONTROL_TYPES = {"Canvas", "Signature", "Handwriting", "Sign"}
_UNREGISTERED_LEGACY_WM_ID = "__unregistered_legacy__"


def _now_iso() -> str:
    return datetime.now(_TZ_SHANGHAI).isoformat(timespec="seconds")


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


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        s = str(item or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _extract_file_ids_from_value(value: dict[str, Any]) -> list[str]:
    """Collect file/media IDs from standard `files`, `wedrive_files`, `images`, or `signature` payloads."""
    found: list[str] = []
    for list_key in ("files", "wedrive_files", "images", "docs"):
        entries = value.get(list_key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                fid = str(
                    entry.get("file_id")
                    or entry.get("fileid")
                    or entry.get("media_id")
                    or entry.get("id")
                    or ""
                ).strip()
                if fid:
                    found.append(fid)
            elif isinstance(entry, str) and entry.strip():
                found.append(entry.strip())

    sig_obj = value.get("signature")
    if isinstance(sig_obj, dict):
        fid = str(sig_obj.get("file_id") or sig_obj.get("fileid") or sig_obj.get("media_id") or "").strip()
        if fid:
            found.append(fid)
    elif isinstance(sig_obj, str) and sig_obj.strip():
        found.append(sig_obj.strip())

    return _dedup_preserve_order(found)


def _parse_table_control(value: dict[str, Any]) -> tuple[str, list[str], list[dict[str, Any]], int]:
    """Parse a WeCom `Table` control into `(text_block, all_file_ids, structured_rows, paired_photo_rows)`."""
    children = value.get("children") or []
    if not isinstance(children, list):
        return ("", [], [], 0)

    row_lines: list[str] = []
    all_file_ids: list[str] = []
    structured_rows: list[dict[str, Any]] = []
    paired_photo_rows = 0

    for row_idx, row in enumerate(children, start=1):
        if not isinstance(row, dict):
            continue
        cells = row.get("list") or []
        if not isinstance(cells, list):
            continue

        row_fields: dict[str, str] = {}
        row_parts: list[str] = []
        row_file_ids: list[str] = []
        before_photo_ids: list[str] = []
        after_photo_ids: list[str] = []
        photo_col_counts: list[int] = []

        for col_idx, cell in enumerate(cells, start=1):
            if not isinstance(cell, dict):
                continue
            cell_ctype = str(cell.get("control") or "").strip()
            if cell_ctype == "Tips":
                continue
            cell_label = _extract_localized_text(cell.get("title")) or str(cell.get("id") or f"列{col_idx}")
            cell_val_obj = cell.get("value") or {}
            cell_text, cell_files = _extract_control_value(cell_ctype, cell_val_obj)

            if cell_files:
                row_file_ids.extend(cell_files)
                all_file_ids.extend(cell_files)

            is_photo_col = cell_ctype in ("File", "WedriveFile", "Image") or ("照片" in cell_label or "图片" in cell_label)
            if is_photo_col:
                photo_col_counts.append(len(cell_files))
                if any(h in cell_label for h in _BEFORE_PHOTO_HINTS):
                    before_photo_ids.extend(cell_files)
                elif any(h in cell_label for h in _AFTER_PHOTO_HINTS):
                    after_photo_ids.extend(cell_files)

            if cell_text:
                row_fields[cell_label] = cell_text
                row_parts.append(f"{cell_label}={cell_text}")

        has_paired_photos = False
        if before_photo_ids and after_photo_ids:
            has_paired_photos = True
        elif not before_photo_ids and not after_photo_ids and sum(1 for c in photo_col_counts if c > 0) >= 2:
            has_paired_photos = True
        if has_paired_photos:
            paired_photo_rows += 1

        if row_fields or row_file_ids:
            structured_rows.append(
                {
                    "row_index": row_idx,
                    "fields": row_fields,
                    "before_photo_ids": _dedup_preserve_order(before_photo_ids),
                    "after_photo_ids": _dedup_preserve_order(after_photo_ids),
                    "file_ids": _dedup_preserve_order(row_file_ids),
                    "has_paired_photos": has_paired_photos,
                }
            )
            row_lines.append(f"[行{row_idx}] " + "｜".join(row_parts))

    return ("\n".join(row_lines), _dedup_preserve_order(all_file_ids), structured_rows, paired_photo_rows)


def _extract_control_value(control_type: str, value: dict[str, Any]) -> tuple[str, list[str]]:
    """Parse a single WeCom Journal `apply_data.contents` control into `(text_value, file_ids)`."""
    if not isinstance(value, dict):
        return ("", [])

    ctype = (control_type or "").strip()
    if ctype == "Tips":
        return ("", [])

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
    if ctype in ("File", "WedriveFile", "Image"):
        file_ids = _extract_file_ids_from_value(value)
        tag = "企微盘附件" if ctype == "WedriveFile" else "附件"
        return (f"[{tag} {len(file_ids)} 个]" if file_ids else "", file_ids)
    if ctype in _SIGNATURE_CONTROL_TYPES:
        sig_ids = _extract_file_ids_from_value(value)
        if sig_ids:
            return (f"[已手写签名 {len(sig_ids)} 个]", sig_ids)
        sig_text = clean_rich_text(str(value.get("text") or ""))
        return (sig_text, [])
    if ctype == "Table":
        table_text, table_files, _, _ = _parse_table_control(value)
        return (table_text, table_files)
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

    # Best-effort fallback for custom/unknown controls (excluding Tips)
    file_ids = _extract_file_ids_from_value(value)
    if file_ids:
        return (f"[附件 {len(file_ids)} 个]", file_ids)
    for fallback_key in ("text", "new_number", "new_money"):
        val = value.get(fallback_key)
        if val is not None and str(val).strip():
            return (clean_rich_text(str(val)), [])
    return ("", [])


def parse_journal_detail(
    raw_detail: dict[str, Any],
    *,
    template_spec: TemplateSpec,
    user_map: dict[str, WeComUserRecord] | None = None,
    effective_date: str = NEW_TEMPLATE_EFFECTIVE_DATE,
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
    structured_extras: dict[str, Any] = {}

    extracted_work_date = ""
    first_any_date = ""
    signature_control_seen = False
    signature_file_ids: list[str] = []
    all_table_rows: list[dict[str, Any]] = []
    total_paired_photo_rows = 0

    apply_data = info.get("apply_data") or {}
    contents = apply_data.get("contents") if isinstance(apply_data, dict) else []
    if isinstance(contents, list):
        for idx, item in enumerate(contents, start=1):
            if not isinstance(item, dict):
                continue
            control_type = str(item.get("control") or "").strip()
            if control_type == "Tips":
                continue

            label = _extract_localized_text(item.get("title")) or str(item.get("id") or f"字段{idx}")
            val_obj = item.get("value") or {}

            if control_type == "Table":
                text_val, file_ids, table_rows, paired_rows = _parse_table_control(val_obj)
                if table_rows:
                    all_table_rows.extend(table_rows)
                    total_paired_photo_rows += paired_rows
            else:
                text_val, file_ids = _extract_control_value(control_type, val_obj)

            if file_ids:
                attachment_media_ids.extend(file_ids)

            # Dual-date extraction (Date controls)
            if control_type == "Date" and _ISO_DATE_RE.match(text_val):
                if not first_any_date:
                    first_any_date = text_val
                if not extracted_work_date and any(h in label for h in _WORK_DATE_TITLE_HINTS):
                    extracted_work_date = text_val

            # Handwritten customer signature extraction (Canvas / Signature controls)
            if control_type in _SIGNATURE_CONTROL_TYPES or ("签名" in label or "签字" in label):
                signature_control_seen = True
                sig_ids = _extract_file_ids_from_value(val_obj)
                if sig_ids:
                    signature_file_ids.extend(sig_ids)
                    attachment_media_ids.extend(sig_ids)

            # Numeric R&D work hours extraction
            if control_type == "Number" and text_val and ("工时" in label or "小时" in label):
                try:
                    structured_extras["work_hours"] = float(text_val)
                except ValueError:
                    pass

            if text_val:
                if label in parsed_fields:
                    parsed_fields[label] = f"{parsed_fields[label]}；{text_val}"
                else:
                    parsed_fields[label] = text_val
                if control_type not in ("File", "WedriveFile", "Image"):
                    plain_lines.append(f"{label}：{text_val}")

    if all_table_rows:
        rows_with_before = sum(1 for r in all_table_rows if r.get("before_photo_ids"))
        rows_with_after = sum(1 for r in all_table_rows if r.get("after_photo_ids"))
        structured_extras["table_rows"] = all_table_rows
        structured_extras["table_row_count"] = len(all_table_rows)
        structured_extras["table_paired_photo_rows"] = total_paired_photo_rows
        structured_extras["rows_with_before_photo"] = rows_with_before
        structured_extras["rows_with_after_photo"] = rows_with_after
        structured_extras["rows_with_paired_photos"] = total_paired_photo_rows

    if signature_control_seen:
        dedup_sig_ids = _dedup_preserve_order(signature_file_ids)
        structured_extras["signature_file_ids"] = dedup_sig_ids
        structured_extras["has_customer_signature"] = len(dedup_sig_ids) > 0

    work_date = extracted_work_date or first_any_date or report_date
    if (
        template_spec.report_type in (ReportType.FINANCE_DAILY_10MIN, ReportType.FIELD_DAILY_10MIN)
        or work_date >= effective_date
    ):
        schema_era = "upgraded_v2"
    else:
        schema_era = "legacy_v1"

    confidentiality = (
        "finance_restricted"
        if template_spec.report_type == ReportType.FINANCE_DAILY_10MIN
        or template_spec.confidentiality_level == "finance_restricted"
        else "standard"
    )

    return WeComReportRecord(
        journal_uuid=journal_uuid,
        template_id=template_spec.template_id,
        template_name=str(info.get("template_name") or template_spec.template_name).strip(),
        report_type=template_spec.report_type,
        submitter_userid=submitter_userid,
        submitter_name=submitter_name,
        department=department,
        report_date=report_date,
        work_date=work_date,
        submitted_at=submitted_at,
        schema_era=schema_era,
        confidentiality_level=confidentiality,
        parsed_fields=parsed_fields,
        structured_extras=structured_extras,
        plain_text="\n".join(plain_lines),
        attachment_media_ids=_dedup_preserve_order(attachment_media_ids),
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
        request_interval_sec: float = 0.0,
    ) -> None:
        if not corpid or not secret:
            raise ValueError("corpid and secret must be non-empty")
        self.corpid = corpid.strip()
        self.secret = secret.strip()
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.request_interval_sec = max(0.0, float(request_interval_sec))
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=self.timeout)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def _http_call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{_WECOM_BASE}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self.request_interval_sec > 0:
                    time.sleep(self.request_interval_sec)
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
                    logger.warning(
                        "WeCom %s %s failed (attempt %d/%d): %s; retrying in %.1fs",
                        method,
                        path,
                        attempt + 1,
                        self.max_retries + 1,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"WeCom {method} {path} failed after {self.max_retries + 1} attempts: {exc}"
                    ) from exc
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

    def _fetch_uuids_in_range(
        self,
        start_ts: int,
        end_ts: int,
        *,
        template_id: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        page_limit = max(1, min(int(limit), 100))
        seen: set[str] = set()
        ordered_uuids: list[str] = []

        for w_start, w_end in slice_date_windows(start_ts, end_ts, max_window_days=25):
            cursor = 0
            while True:
                payload: dict[str, Any] = {
                    "starttime": w_start,
                    "endtime": w_end,
                    "cursor": cursor,
                    "limit": page_limit,
                }
                if template_id:
                    payload["filters"] = [{"key": "template_id", "value": template_id}]
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

    def fetch_record_uuids(
        self,
        template_id: str,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 100,
    ) -> list[str]:
        """Fetch all `journaluuid` entries for `template_id` over `[start_ts, end_ts]` using <=25-day slices."""
        return self._fetch_uuids_in_range(start_ts, end_ts, template_id=template_id, limit=limit)

    def fetch_unfiltered_record_uuids(
        self,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 100,
    ) -> list[str]:
        """Fetch all `journaluuid` entries across all templates (incl. pre-2025 legacy) in <=25d slices."""
        return self._fetch_uuids_in_range(start_ts, end_ts, template_id=None, limit=limit)

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
        effective_date: str = NEW_TEMPLATE_EFFECTIVE_DATE,
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
                records.append(
                    parse_journal_detail(
                        raw_info,
                        template_spec=tpl,
                        user_map=user_map,
                        effective_date=effective_date,
                    )
                )
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

    def sync_with_watermarks(
        self,
        storage: CompanyOpsStorage,
        *,
        templates: tuple[TemplateSpec, ...] = ALL_WECOM_TEMPLATES,
        initial_backfill_start_date: str = "2022-12-01",
        end_date: str | None = None,
        incremental_overlap_days: int = 7,
        include_unregistered_legacy: bool = False,
        force_full: bool = False,
        effective_date: str = NEW_TEMPLATE_EFFECTIVE_DATE,
        archive_output_path: str | None = None,
    ) -> SmartSyncResult:
        """Watermark-driven sync: resumable 25-day full backfill once, then active-only incremental sync."""
        d_end = date.fromisoformat(end_date[:10]) if end_date else datetime.now(_TZ_SHANGHAI).date()
        d_init_start = date.fromisoformat(initial_backfill_start_date[:10])
        if d_init_start > d_end:
            d_init_start = d_end

        users = self.fetch_users()
        users_synced = storage.upsert_users(users) if users else 0
        user_map = storage.get_user_map()
        existing_uuids = storage.get_existing_report_uuids()

        templates_processed = 0
        templates_skipped_frozen = 0
        total_fetched = 0
        total_inserted = 0
        total_skipped = 0
        legacy_unregistered_inserted = 0
        errors: list[str] = []
        modes_used: set[str] = set()
        effective_min_start = d_end

        for tpl in templates:
            wm = storage.get_sync_watermark(tpl.template_id)
            if (
                not force_full
                and wm is not None
                and wm.full_backfill_completed
                and (wm.template_status == "disabled_frozen" or tpl.status == "disabled")
            ):
                if wm.template_status != "disabled_frozen":
                    wm.template_status = "disabled_frozen"
                    storage.upsert_sync_watermark(wm)
                templates_skipped_frozen += 1
                continue

            is_full = force_full or (wm is None) or (not wm.full_backfill_completed)
            modes_used.add("full_backfill" if is_full else "incremental")
            templates_processed += 1

            if wm is None:
                wm = SyncWatermarkRecord(
                    template_id=tpl.template_id,
                    template_name=tpl.template_name,
                    report_type=tpl.report_type.value,
                    template_status="active" if tpl.status == "active" else "disabled_frozen",
                    full_backfill_completed=False,
                    backfill_cursor_date="",
                    earliest_report_date="",
                    last_synced_at="",
                    total_records_synced=0,
                )

            if is_full:
                if (
                    not force_full
                    and wm.backfill_cursor_date
                    and _ISO_DATE_RE.match(wm.backfill_cursor_date)
                ):
                    d_cursor = date.fromisoformat(wm.backfill_cursor_date)
                    d_tpl_start = max(d_init_start, d_cursor)
                else:
                    d_tpl_start = d_init_start
            else:
                if wm.last_synced_at and len(wm.last_synced_at) >= 10:
                    last_d = min(date.fromisoformat(wm.last_synced_at[:10]), d_end)
                else:
                    last_d = d_end
                d_tpl_start = max(d_init_start, last_d - timedelta(days=max(0, int(incremental_overlap_days))))

            if d_tpl_start > d_end:
                d_tpl_start = d_end
            if d_tpl_start < effective_min_start:
                effective_min_start = d_tpl_start

            start_ts = int(datetime.combine(d_tpl_start, dt_time(0, 0, 0), tzinfo=_TZ_SHANGHAI).timestamp())
            end_ts = int(datetime.combine(d_end, dt_time(23, 59, 59), tzinfo=_TZ_SHANGHAI).timestamp())

            earliest_seen = wm.earliest_report_date
            tpl_new_count = 0

            for w_start, w_end in slice_date_windows(start_ts, end_ts, max_window_days=25):
                uuids = self._fetch_uuids_in_range(w_start, w_end, template_id=tpl.template_id)
                total_fetched += len(uuids)
                new_uuids = [uid for uid in uuids if uid not in existing_uuids]
                total_skipped += len(uuids) - len(new_uuids)

                records: list[WeComReportRecord] = []
                for uid in new_uuids:
                    raw_info = self.fetch_record_detail(uid)
                    rec = parse_journal_detail(
                        raw_info,
                        template_spec=tpl,
                        user_map=user_map,
                        effective_date=effective_date,
                    )
                    records.append(rec)
                    rec_day = rec.work_date or rec.report_date
                    if not earliest_seen or rec_day < earliest_seen:
                        earliest_seen = rec_day

                ins, skip = storage.insert_reports(records)
                total_inserted += ins
                total_skipped += skip
                tpl_new_count += ins
                existing_uuids.update(new_uuids)

                if is_full:
                    slice_end_day = datetime.fromtimestamp(w_end, _TZ_SHANGHAI).date()
                    next_cursor_day = min(slice_end_day + timedelta(days=1), d_end)
                    wm.backfill_cursor_date = next_cursor_day.isoformat()
                    wm.earliest_report_date = earliest_seen
                    wm.total_records_synced += ins
                    storage.upsert_sync_watermark(wm)

            wm.template_name = tpl.template_name
            wm.report_type = tpl.report_type.value
            wm.earliest_report_date = earliest_seen
            wm.last_synced_at = datetime.combine(d_end, dt_time(23, 59, 59), tzinfo=_TZ_SHANGHAI).isoformat(
                timespec="seconds"
            )
            if is_full:
                wm.full_backfill_completed = True
                wm.backfill_cursor_date = d_end.isoformat()
                wm.template_status = "disabled_frozen" if tpl.status == "disabled" else "active"
            else:
                wm.total_records_synced += tpl_new_count
            storage.upsert_sync_watermark(wm)

        # Optional one-time backfill for unregistered pre-2025 legacy templates (e.g., built-in "日报")
        if include_unregistered_legacy:
            legacy_wm = storage.get_sync_watermark(_UNREGISTERED_LEGACY_WM_ID)
            if force_full or legacy_wm is None or not legacy_wm.full_backfill_completed:
                if (
                    not force_full
                    and legacy_wm is not None
                    and legacy_wm.backfill_cursor_date
                    and _ISO_DATE_RE.match(legacy_wm.backfill_cursor_date)
                ):
                    d_leg_start = max(d_init_start, date.fromisoformat(legacy_wm.backfill_cursor_date))
                else:
                    d_leg_start = d_init_start
                if d_leg_start > d_end:
                    d_leg_start = d_end
                if d_leg_start < effective_min_start:
                    effective_min_start = d_leg_start

                if legacy_wm is None:
                    legacy_wm = SyncWatermarkRecord(
                        template_id=_UNREGISTERED_LEGACY_WM_ID,
                        template_name="历史未登记汇报全量归档",
                        report_type=ReportType.LEGACY_OTHER.value,
                        template_status="disabled_frozen",
                        full_backfill_completed=False,
                    )

                leg_start_ts = int(datetime.combine(d_leg_start, dt_time(0, 0, 0), tzinfo=_TZ_SHANGHAI).timestamp())
                leg_end_ts = int(datetime.combine(d_end, dt_time(23, 59, 59), tzinfo=_TZ_SHANGHAI).timestamp())
                leg_earliest = legacy_wm.earliest_report_date

                for w_start, w_end in slice_date_windows(leg_start_ts, leg_end_ts, max_window_days=25):
                    all_uuids = self._fetch_uuids_in_range(w_start, w_end, template_id=None)
                    new_legacy_uuids = [uid for uid in all_uuids if uid not in existing_uuids]
                    total_fetched += len(new_legacy_uuids)
                    leg_records: list[WeComReportRecord] = []
                    for uid in new_legacy_uuids:
                        raw_info = self.fetch_record_detail(uid)
                        raw_tid = str(raw_info.get("template_id") or "").strip()
                        raw_tname = str(raw_info.get("template_name") or "历史未登记汇报").strip()
                        matched_tpl = ALL_TEMPLATES_BY_ID.get(raw_tid)
                        if matched_tpl is None:
                            safe_tid = raw_tid if len(raw_tid) >= 8 else f"legacy_{raw_tid or 'unknown'}"
                            matched_tpl = TemplateSpec(
                                template_id=safe_tid,
                                template_name=raw_tname,
                                report_type=ReportType.LEGACY_OTHER,
                                status="disabled",
                            )
                        rec = parse_journal_detail(
                            raw_info,
                            template_spec=matched_tpl,
                            user_map=user_map,
                            effective_date=effective_date,
                        )
                        leg_records.append(rec)
                        rec_day = rec.work_date or rec.report_date
                        if not leg_earliest or rec_day < leg_earliest:
                            leg_earliest = rec_day

                    ins, skip = storage.insert_reports(leg_records)
                    total_inserted += ins
                    total_skipped += skip
                    legacy_unregistered_inserted += ins
                    existing_uuids.update(new_legacy_uuids)

                    slice_end_day = datetime.fromtimestamp(w_end, _TZ_SHANGHAI).date()
                    legacy_wm.backfill_cursor_date = min(slice_end_day + timedelta(days=1), d_end).isoformat()
                    legacy_wm.earliest_report_date = leg_earliest
                    legacy_wm.total_records_synced += ins
                    storage.upsert_sync_watermark(legacy_wm)

                legacy_wm.full_backfill_completed = True
                legacy_wm.backfill_cursor_date = d_end.isoformat()
                legacy_wm.template_status = "disabled_frozen"
                legacy_wm.last_synced_at = datetime.combine(
                    d_end, dt_time(23, 59, 59), tzinfo=_TZ_SHANGHAI
                ).isoformat(timespec="seconds")
                storage.upsert_sync_watermark(legacy_wm)

        archive_saved = ""
        if archive_output_path:
            storage.export_reports_archive_jsonl_gz(archive_output_path)
            archive_saved = str(archive_output_path)

        if modes_used == {"full_backfill"}:
            mode = "full_backfill"
        elif modes_used == {"incremental"}:
            mode = "incremental"
        elif not modes_used:
            mode = "incremental"
        else:
            mode = "mixed"

        return SmartSyncResult(
            mode=mode,
            start_date=effective_min_start.isoformat(),
            end_date=d_end.isoformat(),
            templates_processed=templates_processed,
            templates_skipped_frozen=templates_skipped_frozen,
            records_fetched=total_fetched,
            records_inserted=total_inserted,
            records_skipped_duplicate=total_skipped,
            legacy_unregistered_inserted=legacy_unregistered_inserted,
            users_synced=users_synced,
            archive_path=archive_saved,
            errors=errors,
        )
