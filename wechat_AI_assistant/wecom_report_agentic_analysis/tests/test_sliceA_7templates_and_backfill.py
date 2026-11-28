"""Locked black-box contract tests for Slice A of `wecom_report_agentic_analysis`.

Covers all 7 acceptance scenarios for Slice A (RED phase):
1. Red-Zone 7-template registry & finance role roster verification.
2. Realistic WeCom `Table` (7-column photo table) + `WedriveFile` + `Tips` filtering.
3. Field support handwritten signature (`Canvas`/`Signature`), next-day backfill dual dates
   (`report_date` vs `work_date`), and pre-2026-11-28 legacy report compatibility.
4. Finance confidentiality grading (`finance_restricted`) & R&D work-hours extraction.
5. SQLite sync watermarks (`ops_sync_watermarks`), initial full backfill (incl. disabled
   template & unregistered `legacy_other`), and frozen-template / 7-day incremental skip.
6. Resumable full backfill from an existing `backfill_cursor_date` checkpoint.
7. Offline cold backups (`.jsonl.gz` + SQLite snapshot), zero-network local reparsing,
   and strictly read-only search preserving pre-existing `list_items`.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from wecom_report_agentic_analysis.schemas import (
    ACTIVE_WECOM_TEMPLATES,
    ALL_TEMPLATES_BY_ID,
    ALL_WECOM_TEMPLATES,
    NEW_TEMPLATE_EFFECTIVE_DATE,
    ROSTER_BY_NAME,
    ReportType,
    SmartSyncResult,
    SyncWatermarkRecord,
    TemplateSpec,
    WeComReportRecord,
    WeComUserRecord,
    WorkFunction,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage
from wecom_report_agentic_analysis.wecom_journal_client import (
    WeComJournalClient,
    parse_journal_detail,
)

_TZ_SHANGHAI = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Helpers & deterministic fixtures
# ---------------------------------------------------------------------------


def _sh_ts(year: int, month: int, day: int, hour: int = 18, minute: int = 0, second: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, second, tzinfo=_TZ_SHANGHAI).timestamp())


def _tpl_by_type(report_type: ReportType) -> TemplateSpec:
    for tpl in ALL_WECOM_TEMPLATES:
        if tpl.report_type == report_type:
            return tpl
    raise AssertionError(f"Template not found in ALL_WECOM_TEMPLATES: {report_type}")


def _seed_preexisting_list_items(db_path: Path) -> list[tuple[Any, ...]]:
    """Create a realistic pre-existing Chairman `list_items` table in shared SQLite DB."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT DEFAULT 'P1',
                owner TEXT DEFAULT ''
            )
            """
        )
        rows = [
            (1, "跟进火电厂声波测温标杆验收", "open", "P0", "王楠"),
            (2, "国产质谱仪核心电路板稳定性定型", "in_progress", "P0", "李文颖"),
            (3, "10月财务凭证归档", "done", "P2", "薛蕾"),
        ]
        conn.executemany(
            "INSERT INTO list_items (id, title, status, priority, owner) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return _snapshot_list_items(db_path)


def _snapshot_list_items(db_path: Path) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, title, status, priority, owner FROM list_items ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _sample_user_map() -> dict[str, WeComUserRecord]:
    return {
        "wangnan": WeComUserRecord(
            userid="wangnan",
            name="王楠",
            department_names=["技术支持部"],
            position="技术支持工程师",
        ),
        "liwenying": WeComUserRecord(
            userid="liwenying",
            name="李文颖",
            department_names=["研发部"],
            position="高级硬件研发工程师",
        ),
        "xuelei": WeComUserRecord(
            userid="xuelei",
            name="薛蕾",
            department_names=["财务行政部"],
            position="财务主管",
        ),
        "yanglili": WeComUserRecord(
            userid="yanglili",
            name="杨丽丽",
            department_names=["销售部"],
            position="销售经理",
        ),
    }


def _build_field_daily_raw_detail(
    *,
    journal_uuid: str = "uuid-field-daily-20261128-01",
    report_time: int | None = None,
    work_date_ts: int | None = None,
    submitter_userid: str = "wangnan",
) -> dict[str, Any]:
    """Construct a realistic WeCom `field_daily_10min` payload with 7-col Table, WedriveFile & 600+ char Tips."""
    long_tips_text = (
        "【现场每日10分钟工作报告填报规范】"
        + "请严格按照公司质量与安全管理制度，在每日离开现场前完成当日所有测点操作登记，"
        "每一项设备调试、拆卸、校准或故障处理都必须上传操作前与操作后对比照片，照片须清晰可见设备铭牌与读数。"
        * 12
    )
    assert len(long_tips_text) >= 600

    return {
        "journal_uuid": journal_uuid,
        "template_id": _tpl_by_type(ReportType.FIELD_DAILY_10MIN).template_id,
        "template_name": "现场每日10分钟工作报告",
        "report_time": report_time if report_time is not None else _sh_ts(2026, 11, 28, 19, 30),
        "submitter": {"userid": submitter_userid},
        "apply_data": {
            "contents": [
                {
                    "control": "Tips",
                    "id": "Tips-guide-01",
                    "title": [{"text": "填写说明", "lang": "zh_CN"}],
                    "value": {
                        "text": long_tips_text,
                        "tips": [
                            {
                                "sub_text": [
                                    {
                                        "type": 1,
                                        "content": {"plain_text": {"content": long_tips_text}},
                                    }
                                ]
                            }
                        ],
                    },
                },
                {
                    "control": "Date",
                    "id": "Date-work-day",
                    "title": [{"text": "现场工作日期", "lang": "zh_CN"}],
                    "value": {
                        "date": {
                            "type": "day",
                            "s_timestamp": str(
                                work_date_ts if work_date_ts is not None else _sh_ts(2026, 11, 28, 0, 0)
                            ),
                        }
                    },
                },
                {
                    "control": "Selector",
                    "id": "Selector-product-line",
                    "title": [{"text": "关联产品线", "lang": "zh_CN"}],
                    "value": {
                        "selector": {
                            "type": "multi",
                            "options": [
                                {
                                    "key": "pl-sonic",
                                    "value": [{"text": "声波测温", "lang": "zh_CN"}],
                                }
                            ],
                        }
                    },
                },
                {
                    "control": "Selector",
                    "id": "Selector-role",
                    "title": [{"text": "现场角色", "lang": "zh_CN"}],
                    "value": {
                        "selector": {
                            "type": "single",
                            "options": [
                                {
                                    "key": "role-lead",
                                    "value": [{"text": "现场主责工程师", "lang": "zh_CN"}],
                                }
                            ],
                        }
                    },
                },
                {
                    "control": "Table",
                    "id": "Table-field-ops",
                    "title": [{"text": "当日现场工作明细", "lang": "zh_CN"}],
                    "value": {
                        "children": [
                            {
                                "list": [
                                    {
                                        "control": "Text",
                                        "id": "col-point",
                                        "title": [{"text": "设备/测点", "lang": "zh_CN"}],
                                        "value": {"text": "1号锅炉A侧声波探头"},
                                    },
                                    {
                                        "control": "Selector",
                                        "id": "col-action",
                                        "title": [{"text": "作业类型", "lang": "zh_CN"}],
                                        "value": {
                                            "selector": {
                                                "type": "single",
                                                "options": [
                                                    {
                                                        "key": "act-calib",
                                                        "value": [{"text": "探头校准", "lang": "zh_CN"}],
                                                    }
                                                ],
                                            }
                                        },
                                    },
                                    {
                                        "control": "Textarea",
                                        "id": "col-before-desc",
                                        "title": [{"text": "操作前状态", "lang": "zh_CN"}],
                                        "value": {"text": "回波信号衰减-12dB，法兰有积灰"},
                                    },
                                    {
                                        "control": "WedriveFile",
                                        "id": "col-before-photo",
                                        "title": [{"text": "操作前照片", "lang": "zh_CN"}],
                                        "value": {
                                            "wedrive_files": [{"fileid": "WDF_ROW1_BEFORE_01"}]
                                        },
                                    },
                                    {
                                        "control": "Textarea",
                                        "id": "col-process",
                                        "title": [{"text": "处理措施", "lang": "zh_CN"}],
                                        "value": {"text": "清理波导管积灰并重新标定增益"},
                                    },
                                    {
                                        "control": "WedriveFile",
                                        "id": "col-after-photo",
                                        "title": [{"text": "操作后照片", "lang": "zh_CN"}],
                                        "value": {
                                            "wedrive_files": [{"fileid": "WDF_ROW1_AFTER_01"}]
                                        },
                                    },
                                    {
                                        "control": "Text",
                                        "id": "col-result",
                                        "title": [{"text": "验收结论", "lang": "zh_CN"}],
                                        "value": {"text": "信号恢复正常，信噪比18dB"},
                                    },
                                ]
                            },
                            {
                                "list": [
                                    {
                                        "control": "Text",
                                        "id": "col-point",
                                        "title": [{"text": "设备/测点", "lang": "zh_CN"}],
                                        "value": {"text": "2号锅炉B侧吹扫阀"},
                                    },
                                    {
                                        "control": "Selector",
                                        "id": "col-action",
                                        "title": [{"text": "作业类型", "lang": "zh_CN"}],
                                        "value": {
                                            "selector": {
                                                "type": "single",
                                                "options": [
                                                    {
                                                        "key": "act-repair",
                                                        "value": [{"text": "气路检修", "lang": "zh_CN"}],
                                                    }
                                                ],
                                            }
                                        },
                                    },
                                    {
                                        "control": "Textarea",
                                        "id": "col-before-desc",
                                        "title": [{"text": "操作前状态", "lang": "zh_CN"}],
                                        "value": {"text": "电磁阀轻微漏气导致反吹气压不足"},
                                    },
                                    {
                                        "control": "WedriveFile",
                                        "id": "col-before-photo",
                                        "title": [{"text": "操作前照片", "lang": "zh_CN"}],
                                        "value": {
                                            "wedrive_files": [{"fileid": "WDF_ROW2_BEFORE_01"}]
                                        },
                                    },
                                    {
                                        "control": "Textarea",
                                        "id": "col-process",
                                        "title": [{"text": "处理措施", "lang": "zh_CN"}],
                                        "value": {"text": "更换O型密封圈，待次日复压测试"},
                                    },
                                    {
                                        "control": "WedriveFile",
                                        "id": "col-after-photo",
                                        "title": [{"text": "操作后照片", "lang": "zh_CN"}],
                                        "value": {"wedrive_files": []},
                                    },
                                    {
                                        "control": "Text",
                                        "id": "col-result",
                                        "title": [{"text": "验收结论", "lang": "zh_CN"}],
                                        "value": {"text": "缺操作后照片，明日复压补拍"},
                                    },
                                ]
                            },
                        ]
                    },
                },
                {
                    "control": "WedriveFile",
                    "id": "WedriveFile-top-attach",
                    "title": [{"text": "现场整机验收资料", "lang": "zh_CN"}],
                    "value": {
                        "wedrive_files": [
                            {"fileid": "WDF_TOP_DOC_01"},
                            {"fileid": "WDF_TOP_IMG_02"},
                        ]
                    },
                },
            ]
        },
    }


def _build_simple_report_detail(
    *,
    journal_uuid: str,
    template_id: str,
    template_name: str,
    report_time: int,
    submitter_userid: str,
    summary_text: str,
    extra_contents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    contents: list[dict[str, Any]] = [
        {
            "control": "Textarea",
            "id": "Textarea-main",
            "title": [{"text": "今日完成工作", "lang": "zh_CN"}],
            "value": {"text": summary_text},
        }
    ]
    if extra_contents:
        contents.extend(extra_contents)
    return {
        "journal_uuid": journal_uuid,
        "template_id": template_id,
        "template_name": template_name,
        "report_time": report_time,
        "submitter": {"userid": submitter_userid},
        "apply_data": {"contents": contents},
    }


class FakeWeComServer:
    """In-memory deterministic WeCom HTTP stub driven by `httpx.MockTransport`."""

    def __init__(self, details: list[dict[str, Any]] | None = None) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        for d in details or []:
            self.add_record(d)
        self.list_calls: list[dict[str, Any]] = []
        self.detail_calls: list[str] = []
        self.token_calls: int = 0

    def add_record(self, detail: dict[str, Any]) -> None:
        self.records[str(detail["journal_uuid"])] = detail

    def reset_call_logs(self) -> None:
        self.list_calls.clear()
        self.detail_calls.clear()

    def build_client(self) -> WeComJournalClient:
        transport = httpx.MockTransport(self._handle_request)
        http_client = httpx.Client(transport=transport, timeout=5.0)
        return WeComJournalClient(
            corpid="ww_test_corp",
            secret="test_secret_not_real",
            http_client=http_client,
            max_retries=0,
        )

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/cgi-bin/gettoken":
            self.token_calls += 1
            return httpx.Response(
                200,
                json={"errcode": 0, "errmsg": "ok", "access_token": "fake-token-sliceA", "expires_in": 7200},
            )
        if path == "/cgi-bin/department/list":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "department": [
                        {"id": 1, "name": "维恩科仪"},
                        {"id": 2, "name": "技术支持部"},
                        {"id": 3, "name": "研发部"},
                        {"id": 4, "name": "财务行政部"},
                    ],
                },
            )
        if path == "/cgi-bin/user/list":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "userlist": [
                        {"userid": "wangnan", "name": "王楠", "department": [2], "position": "技术支持工程师", "status": 1},
                        {"userid": "liwenying", "name": "李文颖", "department": [3], "position": "研发工程师", "status": 1},
                        {"userid": "xuelei", "name": "薛蕾", "department": [4], "position": "财务主管", "status": 1},
                        {"userid": "yanglili", "name": "杨丽丽", "department": [1], "position": "销售经理", "status": 1},
                    ],
                },
            )
        if path == "/cgi-bin/oa/journal/get_record_list":
            body = json.loads(request.content.decode("utf-8"))
            self.list_calls.append(body)
            start_ts = int(body["starttime"])
            end_ts = int(body["endtime"])
            filters = body.get("filters") or []
            tpl_filter = None
            for flt in filters:
                if isinstance(flt, dict) and flt.get("key") == "template_id":
                    tpl_filter = str(flt.get("value") or "")

            matched_uuids: list[str] = []
            for uid, rec in sorted(self.records.items()):
                rts = int(rec["report_time"])
                if not (start_ts <= rts <= end_ts):
                    continue
                if tpl_filter and str(rec.get("template_id") or "") != tpl_filter:
                    continue
                matched_uuids.append(uid)

            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "journaluuid_list": matched_uuids,
                    "next_cursor": len(matched_uuids),
                    "endflag": 1,
                },
            )
        if path == "/cgi-bin/oa/journal/get_record_detail":
            body = json.loads(request.content.decode("utf-8"))
            uid = str(body["journaluuid"])
            self.detail_calls.append(uid)
            rec = self.records.get(uid)
            if rec is None:
                return httpx.Response(200, json={"errcode": 301060, "errmsg": "journal not found"})
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok", "info": rec})

        return httpx.Response(404, json={"errcode": 404, "errmsg": f"unexpected path {path}"})


# ---------------------------------------------------------------------------
# Scenario 1: 7-Template Red-Zone Registry & Finance Role Roster
# ---------------------------------------------------------------------------


def test_scenario1_seven_templates_redzone_contract_and_finance_roster() -> None:
    """Verify ALL_WECOM_TEMPLATES (7), ACTIVE_WECOM_TEMPLATES (6), confidentiality, and finance staff roles."""
    assert len(ALL_WECOM_TEMPLATES) == 7
    assert len(ALL_TEMPLATES_BY_ID) == 7
    assert NEW_TEMPLATE_EFFECTIVE_DATE == "2026-11-28"

    all_types = {t.report_type for t in ALL_WECOM_TEMPLATES}
    assert all_types == {
        ReportType.MORNING_BRIEF,
        ReportType.DAILY_10MIN,
        ReportType.FIELD_SUPPORT,
        ReportType.FIELD_SUPPORT_BACKFILL,
        ReportType.RD_TEST_REPAIR,
        ReportType.FINANCE_DAILY_10MIN,
        ReportType.FIELD_DAILY_10MIN,
    }

    finance_tpl = _tpl_by_type(ReportType.FINANCE_DAILY_10MIN)
    assert finance_tpl.status == "active"
    assert finance_tpl.confidentiality_level == "finance_restricted"

    field_daily_tpl = _tpl_by_type(ReportType.FIELD_DAILY_10MIN)
    assert field_daily_tpl.status == "active"
    assert field_daily_tpl.confidentiality_level == "standard"

    backfill_tpl = _tpl_by_type(ReportType.FIELD_SUPPORT_BACKFILL)
    assert backfill_tpl.status == "disabled"

    assert len(ACTIVE_WECOM_TEMPLATES) == 6
    assert all(t.status == "active" for t in ACTIVE_WECOM_TEMPLATES)
    assert ReportType.FIELD_SUPPORT_BACKFILL not in {t.report_type for t in ACTIVE_WECOM_TEMPLATES}

    assert ROSTER_BY_NAME["薛蕾"].work_function == WorkFunction.FINANCE_ADMIN
    assert ROSTER_BY_NAME["王晓"].work_function == WorkFunction.FINANCE_ADMIN


# ---------------------------------------------------------------------------
# Scenario 2: Realistic Table (7-col) + WedriveFile + Tips Filtering
# ---------------------------------------------------------------------------


def test_scenario2_parse_field_daily_table_wedrive_files_and_filter_tips() -> None:
    """Parse 7-col Table with paired/unpaired WedriveFile photos, top-level WedriveFile, and strip 600+ char Tips."""
    raw = _build_field_daily_raw_detail()
    tpl = _tpl_by_type(ReportType.FIELD_DAILY_10MIN)

    rec = parse_journal_detail(raw, template_spec=tpl, user_map=_sample_user_map())

    # Tips static guidance must be completely stripped from parsed_fields and plain_text
    assert "填写说明" not in rec.parsed_fields
    assert "现场每日10分钟工作报告填报规范" not in rec.plain_text
    assert all("现场每日10分钟工作报告填报规范" not in v for v in rec.parsed_fields.values())

    # 2 Table rows extracted into both parsed_fields and plain_text
    joined_fields = " ".join(rec.parsed_fields.values())
    assert "1号锅炉A侧声波探头" in joined_fields
    assert "2号锅炉B侧吹扫阀" in joined_fields
    assert "1号锅炉A侧声波探头" in rec.plain_text
    assert "2号锅炉B侧吹扫阀" in rec.plain_text

    # All nested Table + top-level WedriveFile fileids collected into attachment_media_ids
    expected_fileids = {
        "WDF_ROW1_BEFORE_01",
        "WDF_ROW1_AFTER_01",
        "WDF_ROW2_BEFORE_01",
        "WDF_TOP_DOC_01",
        "WDF_TOP_IMG_02",
    }
    assert expected_fileids.issubset(set(rec.attachment_media_ids))
    assert len(rec.attachment_media_ids) == len(expected_fileids)

    # Structured table metrics & schema metadata
    assert rec.structured_extras.get("table_row_count") == 2
    assert rec.structured_extras.get("table_paired_photo_rows") == 1
    assert isinstance(rec.structured_extras.get("table_rows"), list)
    assert len(rec.structured_extras["table_rows"]) == 2
    assert rec.schema_era == "upgraded_v2"
    assert rec.work_date == "2026-11-28"
    assert rec.report_date == "2026-11-28"


# ---------------------------------------------------------------------------
# Scenario 3: Handwritten Signature + Dual Dates + Legacy Report Compatibility
# ---------------------------------------------------------------------------


def test_scenario3a_field_support_handwritten_signature_detection() -> None:
    """Detect customer handwritten signature via Canvas/Signature controls (present vs absent)."""
    tpl = _tpl_by_type(ReportType.FIELD_SUPPORT)
    user_map = _sample_user_map()

    raw_signed_canvas = _build_simple_report_detail(
        journal_uuid="uuid-fs-signed-canvas",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_time=_sh_ts(2026, 11, 28, 18, 30),
        submitter_userid="wangnan",
        summary_text="完成3号机组声波测温验收并由客户签字确认。",
        extra_contents=[
            {
                "control": "Canvas",
                "id": "Canvas-customer-sign",
                "title": [{"text": "客户手写签名", "lang": "zh_CN"}],
                "value": {"files": [{"file_id": "SIGN_CANVAS_001"}]},
            }
        ],
    )
    rec_canvas = parse_journal_detail(raw_signed_canvas, template_spec=tpl, user_map=user_map)
    assert rec_canvas.schema_era == "upgraded_v2"
    assert rec_canvas.structured_extras.get("has_customer_signature") is True
    assert "SIGN_CANVAS_001" in (rec_canvas.structured_extras.get("signature_file_ids") or [])
    assert "SIGN_CANVAS_001" in rec_canvas.attachment_media_ids

    raw_signed_signature = _build_simple_report_detail(
        journal_uuid="uuid-fs-signed-signature",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_time=_sh_ts(2026, 11, 29, 16, 0),
        submitter_userid="wangnan",
        summary_text="完成客户现场结项交付。",
        extra_contents=[
            {
                "control": "Signature",
                "id": "Signature-customer-sign",
                "title": [{"text": "客户签字", "lang": "zh_CN"}],
                "value": {"wedrive_files": [{"fileid": "SIGN_WDF_002"}]},
            }
        ],
    )
    rec_sig = parse_journal_detail(raw_signed_signature, template_spec=tpl, user_map=user_map)
    assert rec_sig.structured_extras.get("has_customer_signature") is True
    assert "SIGN_WDF_002" in (rec_sig.structured_extras.get("signature_file_ids") or [])

    raw_unsigned = _build_simple_report_detail(
        journal_uuid="uuid-fs-unsigned",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_time=_sh_ts(2026, 11, 28, 19, 0),
        submitter_userid="wangnan",
        summary_text="客户负责人出差，暂未签字。",
        extra_contents=[
            {
                "control": "Canvas",
                "id": "Canvas-customer-sign",
                "title": [{"text": "客户手写签名", "lang": "zh_CN"}],
                "value": {"files": []},
            }
        ],
    )
    rec_unsigned = parse_journal_detail(raw_unsigned, template_spec=tpl, user_map=user_map)
    assert rec_unsigned.structured_extras.get("has_customer_signature") is False
    assert (rec_unsigned.structured_extras.get("signature_file_ids") or []) == []


def test_scenario3b_next_day_backfill_dual_date_separation_and_sqlite_roundtrip(tmp_path: Path) -> None:
    """Next-day backfill at 2026-11-29T10:20+08:00 with work date 2026-11-28 keeps both dates distinct."""
    tpl = _tpl_by_type(ReportType.DAILY_10MIN)
    raw = _build_simple_report_detail(
        journal_uuid="uuid-daily-backfill-1129",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_time=_sh_ts(2026, 11, 29, 10, 20, 0),
        submitter_userid="yanglili",
        summary_text="补交昨日燃煤电厂客户报价沟通记录。",
        extra_contents=[
            {
                "control": "Date",
                "id": "Date-work-date",
                "title": [{"text": "工作日期", "lang": "zh_CN"}],
                "value": {"date": {"type": "day", "s_timestamp": str(_sh_ts(2026, 11, 28, 0, 0))}},
            }
        ],
    )

    rec = parse_journal_detail(raw, template_spec=tpl, user_map=_sample_user_map())
    assert rec.report_date == "2026-11-29"
    assert rec.work_date == "2026-11-28"
    assert rec.schema_era == "upgraded_v2"

    # Also verify SQLite storage preserves new Slice A columns losslessly
    storage = CompanyOpsStorage(tmp_path / "dual_date.db")
    inserted, skipped = storage.insert_reports([rec])
    assert (inserted, skipped) == (1, 0)
    loaded = storage.list_reports()
    assert len(loaded) == 1
    assert loaded[0].report_date == "2026-11-29"
    assert loaded[0].work_date == "2026-11-28"
    assert loaded[0].schema_era == "upgraded_v2"


def test_scenario3c_legacy_pre_cutoff_report_defaults_work_date_and_era() -> None:
    """Historical report before 2026-11-28 without work-date field uses work_date==report_date and legacy_v1."""
    tpl = _tpl_by_type(ReportType.DAILY_10MIN)
    raw = _build_simple_report_detail(
        journal_uuid="uuid-daily-legacy-1120",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_time=_sh_ts(2026, 11, 20, 18, 15, 0),
        submitter_userid="yanglili",
        summary_text="老模板日报内容，无工作日期控件。",
    )

    rec = parse_journal_detail(raw, template_spec=tpl, user_map=_sample_user_map())
    assert rec.report_date == "2026-11-20"
    assert rec.work_date == rec.report_date == "2026-11-20"
    assert rec.schema_era == "legacy_v1"


# ---------------------------------------------------------------------------
# Scenario 4: Finance Confidentiality & R&D Work Hours Extraction
# ---------------------------------------------------------------------------


def test_scenario4_finance_confidentiality_and_rd_work_hours_extraction(tmp_path: Path) -> None:
    """Finance reports carry `finance_restricted`; R&D reports extract numeric work_hours (6.5) & category."""
    user_map = _sample_user_map()

    fin_tpl = _tpl_by_type(ReportType.FINANCE_DAILY_10MIN)
    raw_fin = _build_simple_report_detail(
        journal_uuid="uuid-fin-20261128-01",
        template_id=fin_tpl.template_id,
        template_name=fin_tpl.template_name,
        report_time=_sh_ts(2026, 11, 28, 17, 45),
        submitter_userid="xuelei",
        summary_text="完成11月应付账款核对与回款流水登记。",
    )
    rec_fin = parse_journal_detail(raw_fin, template_spec=fin_tpl, user_map=user_map)
    assert rec_fin.report_type == ReportType.FINANCE_DAILY_10MIN
    assert rec_fin.confidentiality_level == "finance_restricted"
    assert rec_fin.schema_era == "upgraded_v2"

    rd_tpl = _tpl_by_type(ReportType.RD_TEST_REPAIR)
    raw_rd = _build_simple_report_detail(
        journal_uuid="uuid-rd-20261128-01",
        template_id=rd_tpl.template_id,
        template_name=rd_tpl.template_name,
        report_time=_sh_ts(2026, 11, 28, 18, 20),
        submitter_userid="liwenying",
        summary_text="完成国产质谱仪高频电源板温漂测试。",
        extra_contents=[
            {
                "control": "Number",
                "id": "Number-hours",
                "title": [{"text": "今日投入工时(小时)", "lang": "zh_CN"}],
                "value": {"new_number": "6.5"},
            },
            {
                "control": "Selector",
                "id": "Selector-task-type",
                "title": [{"text": "任务类别", "lang": "zh_CN"}],
                "value": {
                    "selector": {
                        "type": "single",
                        "options": [
                            {
                                "key": "rd-core",
                                "value": [{"text": "核心硬件研发", "lang": "zh_CN"}],
                            }
                        ],
                    }
                },
            },
        ],
    )
    rec_rd = parse_journal_detail(raw_rd, template_spec=rd_tpl, user_map=user_map)
    assert rec_rd.confidentiality_level == "standard"
    assert rec_rd.structured_extras.get("work_hours") == pytest.approx(6.5)
    assert rec_rd.parsed_fields.get("任务类别") == "核心硬件研发"

    # Persist both and ensure confidentiality_level and structured_extras survive SQLite roundtrip
    storage = CompanyOpsStorage(tmp_path / "fin_rd.db")
    storage.insert_reports([rec_fin, rec_rd])
    by_uuid = {r.journal_uuid: r for r in storage.list_reports()}
    assert by_uuid["uuid-fin-20261128-01"].confidentiality_level == "finance_restricted"
    assert by_uuid["uuid-rd-20261128-01"].structured_extras.get("work_hours") == pytest.approx(6.5)


# ---------------------------------------------------------------------------
# Scenario 5: Watermark Table + Initial Full Backfill + Frozen & Incremental Skip
# ---------------------------------------------------------------------------


def test_scenario5_full_backfill_legacy_other_and_incremental_frozen_skip(tmp_path: Path) -> None:
    """First run does full backfill incl. disabled & legacy_other; second run skips frozen & existing UUIDs."""
    daily_tpl = _tpl_by_type(ReportType.DAILY_10MIN)
    field_daily_tpl = _tpl_by_type(ReportType.FIELD_DAILY_10MIN)
    backfill_tpl = _tpl_by_type(ReportType.FIELD_SUPPORT_BACKFILL)

    initial_details = [
        _build_simple_report_detail(
            journal_uuid="uuid-daily-1126",
            template_id=daily_tpl.template_id,
            template_name=daily_tpl.template_name,
            report_time=_sh_ts(2026, 11, 26, 18, 0),
            submitter_userid="yanglili",
            summary_text="推进垃圾焚烧电厂SNCR测温项目报价。",
        ),
        _build_field_daily_raw_detail(
            journal_uuid="uuid-field-daily-1128",
            report_time=_sh_ts(2026, 11, 28, 18, 30),
        ),
        _build_simple_report_detail(
            journal_uuid="uuid-disabled-backfill-1015",
            template_id=backfill_tpl.template_id,
            template_name=backfill_tpl.template_name,
            report_time=_sh_ts(2026, 10, 15, 17, 0),
            submitter_userid="wangnan",
            summary_text="历史停用后补模板记录：华电项目现场调试。",
        ),
        _build_simple_report_detail(
            journal_uuid="uuid-unregistered-legacy-1005",
            template_id="3WLegacyUnregisteredTemplate2023",
            template_name="日报",
            report_time=_sh_ts(2026, 10, 5, 18, 0),
            submitter_userid="liwenying",
            summary_text="未登记早期通用日报：样机电路联调。",
        ),
    ]

    server = FakeWeComServer(initial_details)
    client = server.build_client()
    storage = CompanyOpsStorage(tmp_path / "watermarks.db")

    # Round 1: Initial full backfill (incl. disabled template & unregistered legacy reports)
    res1 = client.sync_with_watermarks(
        storage,
        initial_backfill_start_date="2026-10-01",
        end_date="2026-11-28",
        include_unregistered_legacy=True,
    )
    assert isinstance(res1, SmartSyncResult)
    assert res1.mode == "full_backfill"
    assert res1.errors == []
    assert res1.templates_processed == len(ALL_WECOM_TEMPLATES)
    assert res1.templates_skipped_frozen == 0
    assert res1.legacy_unregistered_inserted == 1
    assert res1.records_inserted == 4

    stored = {r.journal_uuid: r for r in storage.list_reports()}
    assert set(stored.keys()) == {
        "uuid-daily-1126",
        "uuid-field-daily-1128",
        "uuid-disabled-backfill-1015",
        "uuid-unregistered-legacy-1005",
    }
    assert stored["uuid-disabled-backfill-1015"].report_type == ReportType.FIELD_SUPPORT_BACKFILL
    assert stored["uuid-unregistered-legacy-1005"].report_type == ReportType.LEGACY_OTHER

    # Disabled template must now be frozen in ops_sync_watermarks
    wm_backfill = storage.get_sync_watermark(backfill_tpl.template_id)
    assert wm_backfill is not None
    assert wm_backfill.template_status == "disabled_frozen"
    assert wm_backfill.full_backfill_completed is True
    assert wm_backfill.total_records_synced >= 1

    wm_daily = storage.get_sync_watermark(daily_tpl.template_id)
    assert wm_daily is not None
    assert wm_daily.template_status == "active"
    assert wm_daily.full_backfill_completed is True
    assert wm_daily.last_synced_at != ""

    all_wms = storage.list_sync_watermarks()
    assert len(all_wms) >= len(ALL_WECOM_TEMPLATES)

    # Round 2: Incremental sync with 1 brand-new report; frozen template & existing UUIDs must be skipped
    server.reset_call_logs()
    server.add_record(
        _build_simple_report_detail(
            journal_uuid="uuid-daily-new-1128",
            template_id=daily_tpl.template_id,
            template_name=daily_tpl.template_name,
            report_time=_sh_ts(2026, 11, 28, 20, 0),
            submitter_userid="yanglili",
            summary_text="增量新增日报：完成CCS/CCUS客户技术交流纪要。",
        )
    )

    res2 = client.sync_with_watermarks(
        storage,
        initial_backfill_start_date="2026-10-01",
        end_date="2026-11-28",
        incremental_overlap_days=7,
    )
    assert res2.mode == "incremental"
    assert res2.errors == []
    assert res2.templates_skipped_frozen >= 1
    assert res2.records_inserted == 1
    assert res2.records_skipped_duplicate >= 2

    # Invariant 1: ZERO get_record_list calls for disabled_frozen template
    queried_template_ids = {
        flt.get("value")
        for call in server.list_calls
        for flt in (call.get("filters") or [])
        if isinstance(flt, dict) and flt.get("key") == "template_id"
    }
    assert backfill_tpl.template_id not in queried_template_ids
    assert daily_tpl.template_id in queried_template_ids
    assert field_daily_tpl.template_id in queried_template_ids

    # Invariant 2: Incremental window stays within (last_synced_at - 7 days), never rescanning October
    wm_last_date = date.fromisoformat(wm_daily.last_synced_at[:10])
    earliest_allowed_date = min(wm_last_date, date(2026, 11, 28)) - timedelta(days=7)
    earliest_allowed_ts = _sh_ts(
        earliest_allowed_date.year, earliest_allowed_date.month, earliest_allowed_date.day, 0, 0, 0
    )
    assert len(server.list_calls) >= 6
    for call in server.list_calls:
        assert int(call["starttime"]) >= earliest_allowed_ts

    # Invariant 3: ZERO duplicate get_record_detail calls for already-persisted UUIDs
    assert server.detail_calls == ["uuid-daily-new-1128"]


# ---------------------------------------------------------------------------
# Scenario 6: Resumable Full Backfill Checkpoint Verification
# ---------------------------------------------------------------------------


def test_scenario6_resumable_full_backfill_skips_completed_slices(tmp_path: Path) -> None:
    """When backfill_cursor_date='2026-11-01' and incomplete, first API slice starts >= 2026-11-01."""
    daily_tpl = _tpl_by_type(ReportType.DAILY_10MIN)
    storage = CompanyOpsStorage(tmp_path / "resume.db")

    storage.upsert_sync_watermark(
        SyncWatermarkRecord(
            template_id=daily_tpl.template_id,
            template_name=daily_tpl.template_name,
            report_type=daily_tpl.report_type.value,
            template_status="active",
            full_backfill_completed=False,
            backfill_cursor_date="2026-11-01",
            earliest_report_date="2026-10-05",
            last_synced_at="",
            total_records_synced=5,
        )
    )

    server = FakeWeComServer(
        [
            _build_simple_report_detail(
                journal_uuid="uuid-old-oct-should-not-scan",
                template_id=daily_tpl.template_id,
                template_name=daily_tpl.template_name,
                report_time=_sh_ts(2026, 10, 10, 18, 0),
                submitter_userid="yanglili",
                summary_text="十月旧切片记录，不应被断点续传重扫。",
            ),
            _build_simple_report_detail(
                journal_uuid="uuid-nov-resumed-01",
                template_id=daily_tpl.template_id,
                template_name=daily_tpl.template_name,
                report_time=_sh_ts(2026, 11, 12, 18, 0),
                submitter_userid="yanglili",
                summary_text="十一月续传切片记录。",
            ),
        ]
    )
    client = server.build_client()

    res = client.sync_with_watermarks(
        storage,
        templates=(daily_tpl,),
        initial_backfill_start_date="2026-10-01",
        end_date="2026-11-28",
    )
    assert res.errors == []
    assert len(server.list_calls) >= 1

    cutoff_ts = _sh_ts(2026, 11, 1, 0, 0, 0)
    assert int(server.list_calls[0]["starttime"]) >= cutoff_ts
    assert all(int(call["starttime"]) >= cutoff_ts for call in server.list_calls)

    stored_uuids = {r.journal_uuid for r in storage.list_reports()}
    assert "uuid-nov-resumed-01" in stored_uuids
    assert "uuid-old-oct-should-not-scan" not in stored_uuids

    wm_after = storage.get_sync_watermark(daily_tpl.template_id)
    assert wm_after is not None
    assert wm_after.full_backfill_completed is True


# ---------------------------------------------------------------------------
# Scenario 7: Cold Backups (.jsonl.gz + SQLite Snapshot) + Offline Reparse + Readonly Search
# ---------------------------------------------------------------------------


def test_scenario7_cold_backups_offline_reparse_and_readonly_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify gzip JSONL archive, SQLite online snapshot, zero-network reparse, and readonly search."""
    db_path = tmp_path / "shared_app.db"
    before_list_items = _seed_preexisting_list_items(db_path)
    storage = CompanyOpsStorage(db_path)

    user_map = _sample_user_map()
    storage.upsert_users(list(user_map.values()))

    field_tpl = _tpl_by_type(ReportType.FIELD_DAILY_10MIN)
    fin_tpl = _tpl_by_type(ReportType.FINANCE_DAILY_10MIN)
    rd_tpl = _tpl_by_type(ReportType.RD_TEST_REPAIR)

    raw_field = _build_field_daily_raw_detail(
        journal_uuid="uuid-arch-field-01",
        report_time=_sh_ts(2026, 11, 28, 19, 30),
        work_date_ts=_sh_ts(2026, 11, 28, 0, 0),
        submitter_userid="wangnan",
    )
    raw_fin = _build_simple_report_detail(
        journal_uuid="uuid-arch-fin-02",
        template_id=fin_tpl.template_id,
        template_name=fin_tpl.template_name,
        report_time=_sh_ts(2026, 11, 28, 17, 30),
        submitter_userid="xuelei",
        summary_text="完成11月银行对账与发票归集。",
    )
    raw_rd = _build_simple_report_detail(
        journal_uuid="uuid-arch-rd-03",
        template_id=rd_tpl.template_id,
        template_name=rd_tpl.template_name,
        report_time=_sh_ts(2026, 11, 22, 18, 0),
        submitter_userid="liwenying",
        summary_text="完成氢燃料电池质谱采样电路板调试。",
        extra_contents=[
            {
                "control": "Number",
                "id": "Number-hours",
                "title": [{"text": "工时", "lang": "zh_CN"}],
                "value": {"new_number": "7.5"},
            }
        ],
    )

    # Seed records directly with raw_payload intact (using minimal fields so this test isolates storage methods)
    seed_records = [
        WeComReportRecord(
            journal_uuid="uuid-arch-field-01",
            template_id=field_tpl.template_id,
            template_name=field_tpl.template_name,
            report_type=field_tpl.report_type,
            submitter_userid="wangnan",
            submitter_name="王楠",
            department="技术支持部",
            report_date="2026-11-28",
            work_date="",
            submitted_at="2026-11-28T19:30:00+08:00",
            schema_era="legacy_v1",
            confidentiality_level="standard",
            parsed_fields={},
            structured_extras={},
            plain_text="STALE_NEEDS_REPARSE",
            attachment_media_ids=[],
            raw_payload=raw_field,
        ),
        WeComReportRecord(
            journal_uuid="uuid-arch-fin-02",
            template_id=fin_tpl.template_id,
            template_name=fin_tpl.template_name,
            report_type=fin_tpl.report_type,
            submitter_userid="xuelei",
            submitter_name="薛蕾",
            department="财务行政部",
            report_date="2026-11-28",
            work_date="2026-11-28",
            submitted_at="2026-11-28T17:30:00+08:00",
            schema_era="upgraded_v2",
            confidentiality_level="finance_restricted",
            parsed_fields={"今日完成工作": "完成11月银行对账与发票归集。"},
            structured_extras={},
            plain_text="今日完成工作：完成11月银行对账与发票归集。",
            attachment_media_ids=[],
            raw_payload=raw_fin,
        ),
        WeComReportRecord(
            journal_uuid="uuid-arch-rd-03",
            template_id=rd_tpl.template_id,
            template_name=rd_tpl.template_name,
            report_type=rd_tpl.report_type,
            submitter_userid="liwenying",
            submitter_name="李文颖",
            department="研发部",
            report_date="2026-11-22",
            work_date="2026-11-22",
            submitted_at="2026-11-22T18:00:00+08:00",
            schema_era="legacy_v1",
            confidentiality_level="standard",
            parsed_fields={"今日完成工作": "完成氢燃料电池质谱采样电路板调试。"},
            structured_extras={},
            plain_text="今日完成工作：完成氢燃料电池质谱采样电路板调试。",
            attachment_media_ids=[],
            raw_payload=raw_rd,
        ),
    ]
    inserted, skipped = storage.insert_reports(seed_records)
    assert (inserted, skipped) == (3, 0)

    # 7.1 Zero-network local reparse from raw_payload_json
    def _forbid_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("reparse_stored_reports() must NEVER make any HTTP network call")

    monkeypatch.setattr(httpx.Client, "request", _forbid_network)
    reparsed_count = storage.reparse_stored_reports(effective_date="2026-11-28")
    assert reparsed_count == 3

    after_reparse = {r.journal_uuid: r for r in storage.list_reports()}
    rebuilt_field = after_reparse["uuid-arch-field-01"]
    assert rebuilt_field.plain_text != "STALE_NEEDS_REPARSE"
    assert "1号锅炉A侧声波探头" in rebuilt_field.plain_text
    assert "现场每日10分钟工作报告填报规范" not in rebuilt_field.plain_text
    assert rebuilt_field.structured_extras.get("table_row_count") == 2
    assert rebuilt_field.structured_extras.get("table_paired_photo_rows") == 1
    assert rebuilt_field.work_date == "2026-11-28"
    assert rebuilt_field.schema_era == "upgraded_v2"
    assert after_reparse["uuid-arch-rd-03"].structured_extras.get("work_hours") == pytest.approx(7.5)

    # 7.2 Gzip JSONL cold archive export with complete raw_payload
    archive_path = tmp_path / "cold_backup" / "reports_archive.jsonl.gz"
    archive_meta = storage.export_reports_archive_jsonl_gz(archive_path)
    assert isinstance(archive_meta, dict)
    assert archive_path.exists()
    with gzip.open(archive_path, "rt", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert len(lines) == 3
    exported_by_uuid = {item["journal_uuid"]: item for item in lines}
    assert set(exported_by_uuid.keys()) == {"uuid-arch-field-01", "uuid-arch-fin-02", "uuid-arch-rd-03"}
    assert exported_by_uuid["uuid-arch-field-01"]["raw_payload"]["journal_uuid"] == "uuid-arch-field-01"
    assert "apply_data" in exported_by_uuid["uuid-arch-field-01"]["raw_payload"]

    # 7.3 Independent SQLite online backup snapshot
    snapshot_dest = tmp_path / "snapshots" / "app_backup.db"
    snapshot_path = storage.backup_sqlite_snapshot(snapshot_dest)
    assert isinstance(snapshot_path, Path)
    assert snapshot_path.exists()
    assert snapshot_path.stat().st_size > 0
    snap_conn = sqlite3.connect(snapshot_path)
    try:
        integrity = snap_conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        report_count = snap_conn.execute("SELECT COUNT(*) FROM ops_wecom_reports").fetchone()[0]
        assert report_count == 3
        list_item_count = snap_conn.execute("SELECT COUNT(*) FROM list_items").fetchone()[0]
        assert list_item_count == 3
    finally:
        snap_conn.close()

    # 7.4 Read-only search by staff_name / keyword / start_date without ever mutating list_items
    by_staff = storage.search_reports_readonly(staff_name="王楠")
    assert [r.journal_uuid for r in by_staff] == ["uuid-arch-field-01"]

    by_keyword = storage.search_reports_readonly(keyword="氢燃料电池")
    assert [r.journal_uuid for r in by_keyword] == ["uuid-arch-rd-03"]

    by_start_date = storage.search_reports_readonly(start_date="2026-11-28")
    assert {r.journal_uuid for r in by_start_date} == {"uuid-arch-field-01", "uuid-arch-fin-02"}

    by_combo = storage.search_reports_readonly(
        staff_name="王楠",
        keyword="声波探头",
        start_date="2026-11-28",
    )
    assert [r.journal_uuid for r in by_combo] == ["uuid-arch-field-01"]

    # Invariant: pre-existing Chairman `list_items` table is 100% untouched
    assert _snapshot_list_items(db_path) == before_list_items
