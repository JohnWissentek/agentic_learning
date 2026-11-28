"""Independent blind black-box contract tests for Slice A of `wecom_report_agentic_analysis`.

Covers the 5 authoritative acceptance scenarios across Happy Path, Edge Cases, and Invariants:
1. 7-template registry & confidentiality/status classification (`schemas.py`).
2. Rich control parsing: nested 7-column `Table` with before/after photos, `WedriveFile`,
   `Canvas`/`Signature` customer signature detection, and `Tips` noise exclusion (`wecom_journal_client.py`).
3. Dual-date (`work_date` vs `submitted_at`) handling, `legacy_v1` vs `upgraded_v2` era boundary
   at `2026-11-28`, and `finance_restricted` confidentiality tagging.
4. Watermark-driven resumable full backfill -> disabled template freezing -> permanent incremental
   sync with 7-day lookback, deduplicated detail skipping, and pre-2025 unregistered legacy recovery.
5. Cold backup (`export_reports_archive_jsonl_gz`), online SQLite snapshot (`backup_sqlite_snapshot`),
   zero-network offline reparse (`reparse_stored_reports`), and strictly read-only search
   (`search_reports_readonly`) preserving Chairman's `list_items` table untouched.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from wecom_report_agentic_analysis.schemas import (
    ACTIVE_WECOM_TEMPLATES,
    ALL_TEMPLATES_BY_ID,
    ALL_WECOM_TEMPLATES,
    NEW_TEMPLATE_EFFECTIVE_DATE,
    ReportType,
    SmartSyncResult,
    SyncWatermarkRecord,
    TemplateSpec,
    WeComReportRecord,
    WeComUserRecord,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage
from wecom_report_agentic_analysis.wecom_journal_client import (
    WeComJournalClient,
    parse_journal_detail,
)

TZ_SHANGHAI = timezone(timedelta(hours=8))

MORNING_TPL_ID = "3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP"
DAILY_10MIN_TPL_ID = "C4c9RoeekLMSRRcqyurjgee3x7c6MUgPqN96rLmFr"
FIELD_SUPPORT_TPL_ID = "C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B"
DISABLED_BACKFILL_TPL_ID = "C4c5FCnCK487vAdZ1mpe6gNMeFabs6zPTSHWmV5Dr"
RD_TEST_REPAIR_TPL_ID = "3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8"
FINANCE_TPL_ID = "3WPHEvnos5s9srSXWAqcs5hUgib4WwJYkb8yxAsZ"
FIELD_DAILY_10MIN_TPL_ID = "3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3"


# ---------------------------------------------------------------------------
# Deterministic test data builders & SQLite isolation helpers
# ---------------------------------------------------------------------------


def _ts_shanghai(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, second, tzinfo=TZ_SHANGHAI).timestamp())


def _seed_chairman_list_items(db_path: Path) -> list[tuple[Any, ...]]:
    """Seed realistic Chairman `list_items` rows in shared `app.db` and return snapshot."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT DEFAULT 'P1',
                work_domain TEXT DEFAULT '',
                owner TEXT DEFAULT '',
                due_date TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )
        rows = [
            (1, "推动声波测温在华能电厂标杆落地", "open", "P0", "客户销售", "杨丽丽", "2026-12-10", "2026-11-28T08:00:00+08:00"),
            (2, "核查国产质谱仪核心电路板测试交付", "in_progress", "P0", "产品研发", "李文颖", "2026-12-15", "2026-11-28T09:00:00+08:00"),
            (3, "完成11月历史账目归档", "done", "P2", "公司治理与人事", "薛蕾", "2026-11-25", "2026-11-25T17:30:00+08:00"),
        ]
        conn.executemany(
            """
            INSERT INTO list_items (id, title, status, priority, work_domain, owner, due_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
            "SELECT id, title, status, priority, work_domain, owner, due_date, updated_at "
            "FROM list_items ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _make_7col_table_row(
    *,
    product_line: str,
    device_sn: str,
    issue_desc: str,
    action_taken: str,
    before_photo_control: dict[str, Any],
    after_photo_control: dict[str, Any],
    retest_result: str,
) -> dict[str, Any]:
    """Build a realistic 7-column WeCom `Table` row under `value.children[].list`."""
    return {
        "list": [
            {
                "control": "Selector",
                "id": "Selector-product",
                "title": [{"text": "设备产品线", "lang": "zh_CN"}],
                "value": {
                    "selector": {
                        "type": "single",
                        "options": [
                            {"key": "opt-prod", "value": [{"text": product_line, "lang": "zh_CN"}]}
                        ],
                    }
                },
            },
            {
                "control": "Text",
                "id": "Text-sn",
                "title": [{"text": "设备编号", "lang": "zh_CN"}],
                "value": {"text": device_sn},
            },
            {
                "control": "Text",
                "id": "Text-issue",
                "title": [{"text": "故障或巡检现象", "lang": "zh_CN"}],
                "value": {"text": issue_desc},
            },
            {
                "control": "Textarea",
                "id": "Textarea-action",
                "title": [{"text": "现场处理措施", "lang": "zh_CN"}],
                "value": {"text": action_taken},
            },
            before_photo_control,
            after_photo_control,
            {
                "control": "Text",
                "id": "Text-retest",
                "title": [{"text": "复测结果", "lang": "zh_CN"}],
                "value": {"text": retest_result},
            },
        ]
    }


def _make_rich_field_support_raw_detail(
    *,
    journal_uuid: str = "uuid-rich-v2-001",
    work_date_ts: int | None = None,
    report_time: int | None = None,
    with_signature: bool = True,
    signature_control_type: str = "Canvas",
) -> dict[str, Any]:
    """Build a realistic v2 Field Support detail payload with Date, Table, WedriveFile, Canvas/Signature, Tips."""
    w_ts = work_date_ts if work_date_ts is not None else _ts_shanghai(2026, 11, 28, 0, 0, 0)
    r_ts = report_time if report_time is not None else _ts_shanghai(2026, 11, 29, 10, 0, 0)

    row_paired = _make_7col_table_row(
        product_line="声波测温",
        device_sn="ST-2026-01",
        issue_desc="发射端积灰导致信号衰减",
        action_taken="清理声学波导管并重新校准频谱",
        before_photo_control={
            "control": "WedriveFile",
            "id": "WedriveFile-before",
            "title": [{"text": "操作前照片", "lang": "zh_CN"}],
            "value": {"wedrive_files": [{"fileid": "wd-before-r1", "filename": "before_r1.jpg"}]},
        },
        after_photo_control={
            "control": "WedriveFile",
            "id": "WedriveFile-after",
            "title": [{"text": "操作后照片", "lang": "zh_CN"}],
            "value": {"wedrive_files": [{"fileid": "wd-after-r1", "filename": "after_r1.jpg"}]},
        },
        retest_result="信噪比恢复至32dB",
    )

    row_before_only = _make_7col_table_row(
        product_line="进口V&F质谱仪",
        device_sn="VF-2026-02",
        issue_desc="进样管路压降偏高",
        action_taken="更换过滤膜片待明日复测",
        before_photo_control={
            "control": "File",
            "id": "File-before",
            "title": [{"text": "操作前照片", "lang": "zh_CN"}],
            "value": {"files": [{"file_id": "file-before-r2"}]},
        },
        after_photo_control={
            "control": "File",
            "id": "File-after",
            "title": [{"text": "操作后照片", "lang": "zh_CN"}],
            "value": {"files": []},
        },
        retest_result="待次日复测",
    )

    row_after_only = _make_7col_table_row(
        product_line="CEMS",
        device_sn="CEMS-2026-03",
        issue_desc="零点标气校准",
        action_taken="完成通标气漂移修正",
        before_photo_control={
            "control": "WedriveFile",
            "id": "WedriveFile-before",
            "title": [{"text": "操作前照片", "lang": "zh_CN"}],
            "value": {"wedrive_files": []},
        },
        after_photo_control={
            "control": "WedriveFile",
            "id": "WedriveFile-after",
            "title": [{"text": "操作后照片", "lang": "zh_CN"}],
            "value": {"wedrive_files": [{"fileid": "wd-after-r3", "filename": "after_r3.jpg"}]},
        },
        retest_result="零点误差0.2%合格",
    )

    sig_value: dict[str, Any] = (
        {"files": [{"file_id": "sig-canvas-001"}]} if with_signature else {"files": []}
    )

    return {
        "journal_uuid": journal_uuid,
        "template_name": "现场技术支持工作报告",
        "report_time": r_ts,
        "submitter": {"userid": "wangnan"},
        "apply_data": {
            "contents": [
                {
                    "control": "Date",
                    "id": "Date-work-date",
                    "title": [{"text": "工作日期", "lang": "zh_CN"}],
                    "value": {"date": {"type": "day", "s_timestamp": str(w_ts)}},
                },
                {
                    "control": "Tips",
                    "id": "Tips-guide-01",
                    "title": [{"text": "填写说明", "lang": "zh_CN"}],
                    "value": {
                        "tips": [
                            {
                                "text": "TIPS_NOISE_MARKER_DO_NOT_POLLUTE 请拍照上传清晰工单",
                                "lang": "zh_CN",
                            }
                        ],
                        "text": "TIPS_NOISE_MARKER_DO_NOT_POLLUTE 备用说明字段",
                    },
                },
                {
                    "control": "Text",
                    "id": "Text-customer",
                    "title": [{"text": "客户名称", "lang": "zh_CN"}],
                    "value": {"text": "华能某燃煤电厂"},
                },
                {
                    "control": "Table",
                    "id": "Table-maintenance",
                    "title": [{"text": "现场设备维护明细表", "lang": "zh_CN"}],
                    "value": {"children": [row_paired, row_before_only, row_after_only]},
                },
                {
                    "control": "WedriveFile",
                    "id": "WedriveFile-report",
                    "title": [{"text": "微盘交付附件", "lang": "zh_CN"}],
                    "value": {
                        "wedrive_files": [
                            {"fileid": "wd-top-001", "filename": "现场验收单.pdf"},
                            {"fileid": "wd-top-002", "filename": "声波频谱数据.xlsx"},
                        ]
                    },
                },
                {
                    "control": signature_control_type,
                    "id": "Canvas-customer-sign",
                    "title": [{"text": "客户现场确认签名", "lang": "zh_CN"}],
                    "value": sig_value,
                },
            ]
        },
    }


def _make_simple_detail(
    *,
    journal_uuid: str,
    template_name: str,
    report_time: int,
    userid: str = "liwenying",
    work_date_ts: int | None = None,
    summary: str = "推进国产质谱仪核心板稳定性验证与温漂排查。",
) -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    if work_date_ts is not None:
        contents.append(
            {
                "control": "Date",
                "id": "Date-1",
                "title": [{"text": "日期", "lang": "zh_CN"}],
                "value": {"date": {"type": "day", "s_timestamp": str(work_date_ts)}},
            }
        )
    contents.append(
        {
            "control": "Textarea",
            "id": "Textarea-work",
            "title": [{"text": "今日核心工作", "lang": "zh_CN"}],
            "value": {"text": summary},
        }
    )
    return {
        "journal_uuid": journal_uuid,
        "template_name": template_name,
        "report_time": report_time,
        "submitter": {"userid": userid},
        "apply_data": {"contents": contents},
    }


# ===========================================================================
# 1. 7-Template Registry & Confidentiality / Active-Disabled Classification
# ===========================================================================


def test_seven_template_registry_and_active_filtering():
    """ALL_WECOM_TEMPLATES has 7 templates incl. finance_restricted & field_daily_10min; ACTIVE has 6."""
    assert len(ALL_WECOM_TEMPLATES) == 7
    assert len(ALL_TEMPLATES_BY_ID) == 7
    assert NEW_TEMPLATE_EFFECTIVE_DATE == "2026-11-28"
    assert ReportType.LEGACY_OTHER.value == "legacy_other"

    finance_tpl = ALL_TEMPLATES_BY_ID[FINANCE_TPL_ID]
    assert finance_tpl.report_type == ReportType.FINANCE_DAILY_10MIN
    assert finance_tpl.confidentiality_level == "finance_restricted"
    assert finance_tpl.status == "active"

    field_10min_tpl = ALL_TEMPLATES_BY_ID[FIELD_DAILY_10MIN_TPL_ID]
    assert field_10min_tpl.report_type == ReportType.FIELD_DAILY_10MIN
    assert field_10min_tpl.confidentiality_level == "standard"
    assert field_10min_tpl.status == "active"

    disabled_tpl = ALL_TEMPLATES_BY_ID[DISABLED_BACKFILL_TPL_ID]
    assert disabled_tpl.report_type == ReportType.FIELD_SUPPORT_BACKFILL
    assert disabled_tpl.status == "disabled"

    # Active registry must have exactly 6 active templates and exclude the disabled backfill template
    assert len(ACTIVE_WECOM_TEMPLATES) == 6
    active_ids = {t.template_id for t in ACTIVE_WECOM_TEMPLATES}
    assert DISABLED_BACKFILL_TPL_ID not in active_ids
    assert FINANCE_TPL_ID in active_ids
    assert FIELD_DAILY_10MIN_TPL_ID in active_ids
    assert all(t.status == "active" for t in ACTIVE_WECOM_TEMPLATES)

    # Non-finance templates must remain standard confidentiality
    for tpl in ALL_WECOM_TEMPLATES:
        if tpl.template_id != FINANCE_TPL_ID:
            assert tpl.confidentiality_level == "standard"


# ===========================================================================
# 2. Rich Controls Parsing: Table + WedriveFile + Canvas/Signature + Tips
# ===========================================================================


def test_parse_table_wedrive_canvas_and_skip_tips():
    """Parse nested 7-column Table + WedriveFile + signed Canvas while strictly excluding Tips noise."""
    tpl = ALL_TEMPLATES_BY_ID[FIELD_SUPPORT_TPL_ID]
    user_map = {
        "wangnan": WeComUserRecord(userid="wangnan", name="王楠", department_names=["技术支持部"])
    }
    raw = _make_rich_field_support_raw_detail(
        journal_uuid="uuid-table-signed-01",
        with_signature=True,
        signature_control_type="Canvas",
    )

    rec = parse_journal_detail(raw, template_spec=tpl, user_map=user_map)

    assert rec.submitter_name == "王楠"
    assert rec.department == "技术支持部"

    # Table row text must appear in plain_text
    for expected_snippet in (
        "ST-2026-01",
        "清理声学波导管并重新校准频谱",
        "VF-2026-02",
        "更换过滤膜片待明日复测",
        "CEMS-2026-03",
        "零点误差0.2%合格",
    ):
        assert expected_snippet in rec.plain_text

    # All photo fileids/file_ids from Table rows + top-level WedriveFile must be extracted
    extracted_ids = set(rec.attachment_media_ids)
    for expected_file_id in (
        "wd-before-r1",
        "wd-after-r1",
        "file-before-r2",
        "wd-after-r3",
        "wd-top-001",
        "wd-top-002",
    ):
        assert expected_file_id in extracted_ids

    # Structured table & photo pairing statistics
    assert rec.structured_extras["table_row_count"] == 3
    assert rec.structured_extras["rows_with_before_photo"] == 2
    assert rec.structured_extras["rows_with_after_photo"] == 2
    assert rec.structured_extras["rows_with_paired_photos"] == 1

    # Canvas signature present -> True
    assert rec.structured_extras["has_customer_signature"] is True

    # Invariant: Tips control must be completely skipped and never pollute parsed_fields or plain_text
    assert "填写说明" not in rec.parsed_fields
    assert "TIPS_NOISE_MARKER_DO_NOT_POLLUTE" not in rec.plain_text
    assert all("TIPS_NOISE_MARKER_DO_NOT_POLLUTE" not in str(v) for v in rec.parsed_fields.values())


def test_parse_empty_signature_control_sets_has_customer_signature_false():
    """An empty Canvas/Signature control must explicitly parse `has_customer_signature == False`."""
    tpl = ALL_TEMPLATES_BY_ID[FIELD_SUPPORT_TPL_ID]
    raw_unsigned = _make_rich_field_support_raw_detail(
        journal_uuid="uuid-table-unsigned-02",
        with_signature=False,
        signature_control_type="Signature",
    )

    rec = parse_journal_detail(raw_unsigned, template_spec=tpl)

    assert "has_customer_signature" in rec.structured_extras
    assert rec.structured_extras["has_customer_signature"] is False
    assert "sig-canvas-001" not in rec.attachment_media_ids


# ===========================================================================
# 3. Dual Dates (`work_date` vs `submitted_at`), Era Boundary & Confidentiality
# ===========================================================================


def test_dual_date_next_morning_backfill_and_upgraded_v2_boundary():
    """Next-morning 10:00 backfill for 2026-11-28 keeps work_date=2026-11-28, submitted_at=2026-11-29T10:00:00+08:00."""
    tpl = ALL_TEMPLATES_BY_ID[DAILY_10MIN_TPL_ID]
    raw = _make_simple_detail(
        journal_uuid="uuid-dual-date-v2",
        template_name=tpl.template_name,
        work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 29, 10, 0, 0),
        summary="次日上午10点补交昨日工作日报。",
    )

    rec = parse_journal_detail(raw, template_spec=tpl)

    assert rec.work_date == "2026-11-28"
    assert rec.submitted_at == "2026-11-29T10:00:00+08:00"
    assert rec.schema_era == "upgraded_v2"
    assert rec.confidentiality_level == "standard"


def test_schema_era_legacy_v1_before_boundary_and_finance_confidentiality():
    """work_date < 2026-11-28 is `legacy_v1` even if submitted on 2026-11-28; finance template is `finance_restricted`."""
    daily_tpl = ALL_TEMPLATES_BY_ID[DAILY_10MIN_TPL_ID]
    raw_legacy_backfilled = _make_simple_detail(
        journal_uuid="uuid-era-legacy-boundary",
        template_name=daily_tpl.template_name,
        work_date_ts=_ts_shanghai(2026, 11, 27, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 28, 9, 30, 0),
        summary="补交切换日前一天11月27日工作。",
    )
    rec_legacy = parse_journal_detail(raw_legacy_backfilled, template_spec=daily_tpl)
    assert rec_legacy.work_date == "2026-11-27"
    assert rec_legacy.submitted_at == "2026-11-28T09:30:00+08:00"
    assert rec_legacy.schema_era == "legacy_v1"

    finance_tpl = ALL_TEMPLATES_BY_ID[FINANCE_TPL_ID]
    raw_finance = _make_simple_detail(
        journal_uuid="uuid-finance-v2-01",
        template_name=finance_tpl.template_name,
        userid="xuelei",
        work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 28, 17, 45, 0),
        summary="完成应收账款核对及现金流日报汇总。",
    )
    rec_finance = parse_journal_detail(raw_finance, template_spec=finance_tpl)
    assert rec_finance.work_date == "2026-11-28"
    assert rec_finance.schema_era == "upgraded_v2"
    assert rec_finance.confidentiality_level == "finance_restricted"


def test_storage_roundtrip_persists_slice_a_columns(tmp_path: Path):
    """Persisting and reading back WeComReportRecord retains work_date, schema_era, confidentiality_level, structured_extras."""
    storage = CompanyOpsStorage(tmp_path / "roundtrip.db")
    tpl = ALL_TEMPLATES_BY_ID[FIELD_SUPPORT_TPL_ID]
    raw = _make_rich_field_support_raw_detail(journal_uuid="uuid-roundtrip-01")
    rec = parse_journal_detail(raw, template_spec=tpl)

    inserted, skipped = storage.insert_reports([rec])
    assert (inserted, skipped) == (1, 0)

    loaded = storage.list_reports()
    assert len(loaded) == 1
    got = loaded[0]
    assert got.work_date == "2026-11-28"
    assert got.submitted_at == "2026-11-29T10:00:00+08:00"
    assert got.schema_era == "upgraded_v2"
    assert got.confidentiality_level == "standard"
    assert got.structured_extras["table_row_count"] == 3
    assert got.structured_extras["rows_with_paired_photos"] == 1
    assert got.structured_extras["has_customer_signature"] is True


# ===========================================================================
# 4. Watermark-Driven Full Backfill -> Frozen Disabled -> Permanent Incremental
# ===========================================================================


def test_sync_with_watermarks_full_backfill_freeze_legacy_then_incremental(tmp_path: Path):
    """Run 1 does full backfill across all 7 templates + 2022-12-30 legacy; Run 2 switches to incremental, skips frozen tpl 3 & cached UUIDs."""
    storage = CompanyOpsStorage(tmp_path / "watermarks.db")

    ts_legacy_2022 = _ts_shanghai(2022, 12, 30, 18, 0, 0)
    ts_disabled_hist = _ts_shanghai(2026, 11, 10, 17, 0, 0)
    ts_morning_run1 = _ts_shanghai(2026, 11, 25, 9, 15, 0)
    ts_finance_run1 = _ts_shanghai(2026, 11, 28, 17, 30, 0)
    ts_morning_run2 = _ts_shanghai(2026, 11, 28, 9, 20, 0)

    # Mock remote journal store keyed by journal_uuid
    remote_records: dict[str, dict[str, Any]] = {
        "uuid-legacy-2022-12-30": {
            "template_id": None,  # Unregistered pre-2025 legacy template
            "report_time": ts_legacy_2022,
            "detail": _make_simple_detail(
                journal_uuid="uuid-legacy-2022-12-30",
                template_name="日报",
                userid="wangnan",
                report_time=ts_legacy_2022,
                summary="2022年底早期旧模板现场调试日报。",
            ),
        },
        "uuid-backfill-hist-1": {
            "template_id": DISABLED_BACKFILL_TPL_ID,
            "report_time": ts_disabled_hist,
            "detail": _make_simple_detail(
                journal_uuid="uuid-backfill-hist-1",
                template_name="现场技术支持工作报告（后补）",
                userid="wangnan",
                work_date_ts=_ts_shanghai(2026, 11, 9, 0, 0, 0),
                report_time=ts_disabled_hist,
                summary="已停用后补模板的历史现场工单记录。",
            ),
        },
        "uuid-morning-1": {
            "template_id": MORNING_TPL_ID,
            "report_time": ts_morning_run1,
            "detail": _make_simple_detail(
                journal_uuid="uuid-morning-1",
                template_name="晨会简报",
                userid="kongzichu",
                work_date_ts=_ts_shanghai(2026, 11, 25, 0, 0, 0),
                report_time=ts_morning_run1,
                summary="今日晨会同步华能电厂声波测温发货进度。",
            ),
        },
        "uuid-finance-1": {
            "template_id": FINANCE_TPL_ID,
            "report_time": ts_finance_run1,
            "detail": _make_simple_detail(
                journal_uuid="uuid-finance-1",
                template_name="财务每日10分钟工作简报",
                userid="xuelei",
                work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
                report_time=ts_finance_run1,
                summary="核对本月回款与供应商付款排期。",
            ),
        },
    }

    phase = {"current": "run1"}
    run2_list_requests: list[dict[str, Any]] = []
    run2_detail_uuids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/cgi-bin/gettoken":
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok", "access_token": "tok-sync-1", "expires_in": 7200})
        if path == "/cgi-bin/department/list":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "department": [
                        {"id": 1, "name": "维恩科仪"},
                        {"id": 2, "name": "技术支持部"},
                        {"id": 3, "name": "财务部"},
                    ],
                },
            )
        if path in ("/cgi-bin/user/list", "/cgi-bin/user/simplelist"):
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "userlist": [
                        {"userid": "wangnan", "name": "王楠", "department": [2], "position": "技术支持工程师", "status": 1},
                        {"userid": "kongzichu", "name": "孔紫初", "department": [1], "position": "项目经理", "status": 1},
                        {"userid": "xuelei", "name": "薛蕾", "department": [3], "position": "财务", "status": 1},
                    ],
                },
            )
        if path == "/cgi-bin/oa/journal/get_record_list":
            payload = json.loads(request.content.decode("utf-8"))
            if phase["current"] == "run2":
                run2_list_requests.append(payload)

            start_ts = int(payload["starttime"])
            end_ts = int(payload["endtime"])
            filters = payload.get("filters") or []
            tpl_filter: str | None = None
            for f in filters:
                if f.get("key") == "template_id":
                    tpl_filter = str(f.get("value"))

            matched: list[str] = []
            for uuid, item in remote_records.items():
                rt = int(item["report_time"])
                if not (start_ts <= rt <= end_ts):
                    continue
                if tpl_filter is None or item["template_id"] == tpl_filter:
                    matched.append(uuid)

            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "journaluuid_list": matched,
                    "next_cursor": len(matched),
                    "endflag": 1,
                },
            )
        if path == "/cgi-bin/oa/journal/get_record_detail":
            payload = json.loads(request.content.decode("utf-8"))
            uuid = payload["journaluuid"]
            if phase["current"] == "run2":
                run2_detail_uuids.append(uuid)
            item = remote_records[uuid]
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok", "info": item["detail"]})
        raise AssertionError(f"Unexpected endpoint called: {path}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = WeComJournalClient("ww-corp", "secret", http_client=http_client, timeout=15.0, max_retries=2)

    # --- RUN 1: Initial Full Backfill (all 7 templates + unregistered 2022-12-30 legacy) ---
    res1 = client.sync_with_watermarks(
        storage,
        templates=ALL_WECOM_TEMPLATES,
        initial_backfill_start_date="2022-12-20",
        end_date="2026-11-28",
        incremental_overlap_days=7,
        include_unregistered_legacy=True,
    )

    assert isinstance(res1, SmartSyncResult)
    assert res1.mode == "full_backfill"
    assert res1.templates_processed == 7
    assert res1.templates_skipped_frozen == 0
    assert res1.records_inserted == 4
    assert res1.legacy_unregistered_inserted == 1
    assert res1.errors == []

    # Verify stored records including unregistered legacy & finance_restricted
    by_uuid = {r.journal_uuid: r for r in storage.list_reports()}
    assert set(by_uuid.keys()) == {
        "uuid-legacy-2022-12-30",
        "uuid-backfill-hist-1",
        "uuid-morning-1",
        "uuid-finance-1",
    }
    legacy_rec = by_uuid["uuid-legacy-2022-12-30"]
    assert legacy_rec.report_type == ReportType.LEGACY_OTHER
    assert legacy_rec.report_date == "2022-12-30"
    assert legacy_rec.schema_era == "legacy_v1"
    assert by_uuid["uuid-finance-1"].confidentiality_level == "finance_restricted"

    # Verify watermarks persisted for all 7 registered templates, all completed, disabled tpl 3 frozen
    watermarks = storage.list_sync_watermarks()
    wm_by_id = {w.template_id: w for w in watermarks}
    for tpl in ALL_WECOM_TEMPLATES:
        assert tpl.template_id in wm_by_id
        assert wm_by_id[tpl.template_id].full_backfill_completed is True
    assert wm_by_id[DISABLED_BACKFILL_TPL_ID].template_status == "disabled_frozen"
    for tpl in ACTIVE_WECOM_TEMPLATES:
        assert wm_by_id[tpl.template_id].template_status == "active"

    # --- RUN 2: Subsequent Incremental Sync ---
    # Add 1 brand-new morning report within the 7-day lookback window; old ones remain in remote list
    remote_records["uuid-morning-new-2"] = {
        "template_id": MORNING_TPL_ID,
        "report_time": ts_morning_run2,
        "detail": _make_simple_detail(
            journal_uuid="uuid-morning-new-2",
            template_name="晨会简报",
            userid="kongzichu",
            work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
            report_time=ts_morning_run2,
            summary="新增11月28日晨会简报，验证增量同步与去重跳过。",
        ),
    }
    phase["current"] = "run2"

    res2 = client.sync_with_watermarks(
        storage,
        templates=ALL_WECOM_TEMPLATES,
        initial_backfill_start_date="2022-12-20",
        end_date="2026-11-28",
        incremental_overlap_days=7,
        include_unregistered_legacy=False,
    )

    assert res2.mode == "incremental"
    assert res2.templates_skipped_frozen >= 1
    assert res2.templates_processed == 6
    assert res2.records_inserted == 1
    assert res2.records_skipped_duplicate >= 2  # uuid-morning-1 and uuid-finance-1 already stored
    assert res2.errors == []

    # Invariant 1: Disabled frozen template 3 must NEVER be queried in Run 2
    queried_tpl_ids = {
        f["value"]
        for req in run2_list_requests
        for f in (req.get("filters") or [])
        if f.get("key") == "template_id"
    }
    assert DISABLED_BACKFILL_TPL_ID not in queried_tpl_ids

    # Invariant 2: Incremental mode only looks back 7 days (from 2026-11-21), never back to 2022
    lookback_floor_ts = _ts_shanghai(2026, 11, 21, 0, 0, 0)
    assert len(run2_list_requests) >= 6
    assert all(int(req["starttime"]) >= lookback_floor_ts for req in run2_list_requests)

    # Invariant 3: Already-persisted UUIDs must NOT trigger redundant get_record_detail calls
    assert run2_detail_uuids == ["uuid-morning-new-2"]
    assert "uuid-morning-1" not in run2_detail_uuids
    assert "uuid-finance-1" not in run2_detail_uuids
    assert len(storage.list_reports()) == 5


def test_sync_watermark_storage_crud_and_idempotency(tmp_path: Path):
    """Watermark table supports get (None when absent), idempotent upsert, and ordered listing."""
    storage = CompanyOpsStorage(tmp_path / "wm_crud.db")
    assert storage.get_sync_watermark(MORNING_TPL_ID) is None
    assert storage.list_sync_watermarks() == []

    wm_initial = SyncWatermarkRecord(
        template_id=DISABLED_BACKFILL_TPL_ID,
        template_name="现场技术支持工作报告（后补）",
        report_type=ReportType.FIELD_SUPPORT_BACKFILL.value,
        template_status="active",
        full_backfill_completed=False,
        backfill_cursor_date="2024-06-01",
        total_records_synced=12,
    )
    storage.upsert_sync_watermark(wm_initial)
    got1 = storage.get_sync_watermark(DISABLED_BACKFILL_TPL_ID)
    assert got1 is not None
    assert got1.full_backfill_completed is False
    assert got1.total_records_synced == 12

    wm_frozen = wm_initial.model_copy(
        update={
            "template_status": "disabled_frozen",
            "full_backfill_completed": True,
            "backfill_cursor_date": "2026-11-28",
            "earliest_report_date": "2023-03-15",
            "total_records_synced": 45,
        }
    )
    storage.upsert_sync_watermark(wm_frozen)
    got2 = storage.get_sync_watermark(DISABLED_BACKFILL_TPL_ID)
    assert got2 is not None
    assert got2.template_status == "disabled_frozen"
    assert got2.full_backfill_completed is True
    assert got2.earliest_report_date == "2023-03-15"
    assert got2.total_records_synced == 45
    assert len(storage.list_sync_watermarks()) == 1


# ===========================================================================
# 5. Cold Backup Archive, SQLite Online Snapshot, Offline Reparse & Readonly Search
# ===========================================================================


def test_export_reports_archive_jsonl_gz_preserves_full_raw_payload(tmp_path: Path):
    """export_reports_archive_jsonl_gz produces valid .jsonl.gz restoring complete raw_payload line-by-line."""
    storage = CompanyOpsStorage(tmp_path / "archive_src.db")
    tpl_field = ALL_TEMPLATES_BY_ID[FIELD_SUPPORT_TPL_ID]
    tpl_fin = ALL_TEMPLATES_BY_ID[FINANCE_TPL_ID]

    raw1 = _make_rich_field_support_raw_detail(
        journal_uuid="uuid-arch-001",
        work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 28, 18, 0, 0),
    )
    raw2 = _make_simple_detail(
        journal_uuid="uuid-arch-002",
        template_name=tpl_fin.template_name,
        userid="xuelei",
        work_date_ts=_ts_shanghai(2026, 11, 20, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 20, 18, 0, 0),
        summary="11月20日财务日报归档验证。",
    )
    rec1 = parse_journal_detail(raw1, template_spec=tpl_field)
    rec2 = parse_journal_detail(raw2, template_spec=tpl_fin)
    storage.insert_reports([rec1, rec2])

    archive_file = tmp_path / "cold_backups" / "reports_20261128.jsonl.gz"
    meta = storage.export_reports_archive_jsonl_gz(archive_file)

    assert archive_file.exists()
    assert archive_file.stat().st_size > 0
    assert isinstance(meta, dict)

    with gzip.open(archive_file, "rt", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]

    assert len(lines) == 2
    by_uuid = {row["journal_uuid"]: row for row in lines}
    assert set(by_uuid.keys()) == {"uuid-arch-001", "uuid-arch-002"}
    assert by_uuid["uuid-arch-001"]["raw_payload"] == raw1
    assert by_uuid["uuid-arch-002"]["raw_payload"] == raw2

    # Filtered date range export
    filtered_file = tmp_path / "cold_backups" / "reports_recent.jsonl.gz"
    storage.export_reports_archive_jsonl_gz(filtered_file, start_date="2026-11-25", end_date="2026-11-29")
    with gzip.open(filtered_file, "rt", encoding="utf-8") as fh:
        recent_lines = [json.loads(line) for line in fh if line.strip()]
    assert [r["journal_uuid"] for r in recent_lines] == ["uuid-arch-001"]


def test_backup_sqlite_snapshot_creates_independent_queryable_copy(tmp_path: Path):
    """backup_sqlite_snapshot produces a consistent, independently queryable SQLite database copy."""
    src_db = tmp_path / "app.db"
    _seed_chairman_list_items(src_db)
    storage = CompanyOpsStorage(src_db)

    tpl = ALL_TEMPLATES_BY_ID[MORNING_TPL_ID]
    raw = _make_simple_detail(
        journal_uuid="uuid-snap-001",
        template_name=tpl.template_name,
        report_time=_ts_shanghai(2026, 11, 28, 9, 0, 0),
    )
    storage.insert_reports([parse_journal_detail(raw, template_spec=tpl)])
    storage.upsert_sync_watermark(
        SyncWatermarkRecord(
            template_id=MORNING_TPL_ID,
            template_name=tpl.template_name,
            report_type=tpl.report_type.value,
            template_status="active",
            full_backfill_completed=True,
            total_records_synced=1,
        )
    )

    dest_path = tmp_path / "snapshots" / "app_backup_20261128.db"
    returned_path = storage.backup_sqlite_snapshot(dest_path)

    assert returned_path == dest_path
    assert dest_path.exists()

    # Mutate source DB after snapshot to verify true independence
    raw_after = _make_simple_detail(
        journal_uuid="uuid-after-snap-002",
        template_name=tpl.template_name,
        report_time=_ts_shanghai(2026, 11, 28, 11, 0, 0),
    )
    storage.insert_reports([parse_journal_detail(raw_after, template_spec=tpl)])

    conn = sqlite3.connect(dest_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"
        snap_uuids = [r[0] for r in conn.execute("SELECT journal_uuid FROM ops_wecom_reports").fetchall()]
        assert snap_uuids == ["uuid-snap-001"]
        wm_count = conn.execute("SELECT COUNT(*) FROM ops_sync_watermarks").fetchone()[0]
        assert wm_count == 1
    finally:
        conn.close()


def test_reparse_stored_reports_rebuilds_fields_offline_with_zero_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """reparse_stored_reports rebuilds parsed_fields/structured_extras/work_date/schema_era offline with 0 HTTP calls."""
    storage = CompanyOpsStorage(tmp_path / "reparse.db")
    tpl = ALL_TEMPLATES_BY_ID[FIELD_SUPPORT_TPL_ID]
    raw_v2 = _make_rich_field_support_raw_detail(
        journal_uuid="uuid-reparse-001",
        work_date_ts=_ts_shanghai(2026, 11, 28, 0, 0, 0),
        report_time=_ts_shanghai(2026, 11, 29, 10, 0, 0),
        with_signature=True,
    )

    # Seed a degraded/outdated parsed record that still has the intact raw_payload
    stale_record = WeComReportRecord(
        journal_uuid="uuid-reparse-001",
        template_id=tpl.template_id,
        template_name=tpl.template_name,
        report_type=tpl.report_type,
        submitter_userid="wangnan",
        submitter_name="王楠",
        department="技术支持部",
        report_date="2026-11-29",
        work_date="",
        submitted_at="2026-11-29T10:00:00+08:00",
        schema_era="legacy_v1",
        confidentiality_level="standard",
        parsed_fields={"旧解析字段": "陈旧且残缺", "填写说明": "TIPS_NOISE_MARKER_DO_NOT_POLLUTE"},
        structured_extras={},
        plain_text="陈旧未解析表格",
        attachment_media_ids=[],
        raw_payload=raw_v2,
    )
    storage.insert_reports([stale_record])

    # Invariant: forbid ANY outbound network call during offline reparse
    def _forbid_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("reparse_stored_reports must NEVER perform any network call")

    monkeypatch.setattr(httpx.Client, "send", _forbid_network)
    monkeypatch.setattr(httpx.Client, "request", _forbid_network)

    reparsed_count = storage.reparse_stored_reports(effective_date="2026-11-28")
    assert reparsed_count == 1

    reloaded = storage.list_reports()
    assert len(reloaded) == 1
    rec = reloaded[0]
    assert rec.work_date == "2026-11-28"
    assert rec.schema_era == "upgraded_v2"
    assert rec.structured_extras["table_row_count"] == 3
    assert rec.structured_extras["rows_with_before_photo"] == 2
    assert rec.structured_extras["rows_with_after_photo"] == 2
    assert rec.structured_extras["rows_with_paired_photos"] == 1
    assert rec.structured_extras["has_customer_signature"] is True
    assert "wd-before-r1" in rec.attachment_media_ids
    assert "wd-top-001" in rec.attachment_media_ids
    assert "ST-2026-01" in rec.plain_text
    assert "填写说明" not in rec.parsed_fields
    assert "TIPS_NOISE_MARKER_DO_NOT_POLLUTE" not in rec.plain_text


def test_search_reports_readonly_filters_accurately_and_never_touches_list_items(tmp_path: Path):
    """search_reports_readonly filters by staff/keyword/date/type and leaves Chairman `list_items` byte-identical."""
    db_path = tmp_path / "shared_app.db"
    before_list_items = _seed_chairman_list_items(db_path)
    storage = CompanyOpsStorage(db_path)

    records = [
        WeComReportRecord(
            journal_uuid="uuid-s-01",
            template_id=RD_TEST_REPAIR_TPL_ID,
            template_name="研发产品性能测试和客户返厂维护维修设备日报",
            report_type=ReportType.RD_TEST_REPAIR,
            submitter_userid="liwenying",
            submitter_name="李文颖",
            department="研发部",
            report_date="2026-11-26",
            work_date="2026-11-26",
            submitted_at="2026-11-26T18:00:00+08:00",
            schema_era="legacy_v1",
            plain_text="完成国产质谱仪高频电源板温漂测试。",
            raw_payload={"journal_uuid": "uuid-s-01"},
        ),
        WeComReportRecord(
            journal_uuid="uuid-s-02",
            template_id=FIELD_SUPPORT_TPL_ID,
            template_name="现场技术支持工作报告",
            report_type=ReportType.FIELD_SUPPORT,
            submitter_userid="wangnan",
            submitter_name="王楠",
            department="技术支持部",
            report_date="2026-11-28",
            work_date="2026-11-28",
            submitted_at="2026-11-28T19:10:00+08:00",
            schema_era="upgraded_v2",
            plain_text="华能电厂声波测温装置完成安装调试与客户验收。",
            raw_payload={"journal_uuid": "uuid-s-02"},
        ),
        WeComReportRecord(
            journal_uuid="uuid-s-03",
            template_id=FIELD_DAILY_10MIN_TPL_ID,
            template_name="现场每日10分钟工作报告",
            report_type=ReportType.FIELD_DAILY_10MIN,
            submitter_userid="wangnan",
            submitter_name="王楠",
            department="技术支持部",
            report_date="2026-11-29",
            work_date="2026-11-29",
            submitted_at="2026-11-29T18:30:00+08:00",
            schema_era="upgraded_v2",
            plain_text="声波测温复测稳定，准备转场垃圾焚烧电厂。",
            raw_payload={"journal_uuid": "uuid-s-03"},
        ),
    ]
    storage.insert_reports(records)

    # Filter by staff_name
    by_staff = storage.search_reports_readonly(staff_name="李文颖")
    assert [r.journal_uuid for r in by_staff] == ["uuid-s-01"]

    # Filter by keyword + date range
    by_kw_date = storage.search_reports_readonly(
        keyword="声波测温", start_date="2026-11-28", end_date="2026-11-28"
    )
    assert [r.journal_uuid for r in by_kw_date] == ["uuid-s-02"]

    # Filter by report_type + limit
    by_limit = storage.search_reports_readonly(staff_name="王楠", limit=1)
    assert len(by_limit) == 1

    by_type = storage.search_reports_readonly(report_type=ReportType.FIELD_DAILY_10MIN)
    assert [r.journal_uuid for r in by_type] == ["uuid-s-03"]

    # Edge / Invariant: SQL-injection style keyword must be safely parameterized
    inj = storage.search_reports_readonly(keyword="' OR 1=1 --")
    assert inj == []

    # Invariant: Chairman's pre-existing `list_items` table must remain completely untouched
    after_list_items = _snapshot_list_items(db_path)
    assert after_list_items == before_list_items
