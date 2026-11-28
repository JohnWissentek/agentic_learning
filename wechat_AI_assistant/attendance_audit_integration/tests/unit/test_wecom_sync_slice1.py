"""Slice 1 黑盒契约测试：审批批量拉取 + 汇报官方两步接口 + 签字服务报告落库。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from attendance_audit_integration.config import settings
from attendance_audit_integration.wecom_api import WeComAPIClient


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class _RecordingCursor:
    def __init__(self, active_userids: set[str] | None = None):
        self.active_userids = active_userids or {"WangXu", "ShiZhiTong"}
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 1
        self._last_rows: list = []

    def execute(self, sql: str, params=None):
        params = tuple(params) if params is not None else ()
        placeholders = len(re.findall(r"%s", sql))
        assert placeholders == len(params), f"SQL placeholders ({placeholders}) != params ({len(params)}): {sql}"
        self.executed.append((" ".join(sql.split()), params))
        if "SELECT wecom_userid FROM employees" in sql:
            self._last_rows = [(u,) for u in sorted(self.active_userids)]
        else:
            self._last_rows = []

    def fetchall(self):
        return list(self._last_rows)


@pytest.mark.unit
class TestWeComConfigLiveConstants:
    def test_live_approval_and_journal_template_ids_present(self):
        assert settings.WECOM_APPROVAL_TEMPLATES["leave"] == "Bs8114rcQrU1NHmkaEctMKKRDqSCo9YEdCeLAfjmv"
        assert settings.WECOM_APPROVAL_TEMPLATES["overtime"] == "C4NvrtgmDKznbXFJCKEw5XGNyrw6dhLquQuNkq8Ze"
        assert settings.WECOM_APPROVAL_TEMPLATES["business_trip"] == "ZvVcpYA7cWdCjM3hr8aDhde5CXcYfGw2pVhiDP"
        assert settings.WECOM_APPROVAL_TEMPLATES["outing"] == "3WK7K6pXKXzaUwzDh9KmqtjXGUvMThtDGwHAKzHo"
        assert settings.WECOM_APPROVAL_TEMPLATES["punch_correction"] == "Bs7zz7rsMzoj5roRdLbs2anYNgm3L1ifMq442xHMZ"

        assert settings.WECOM_JOURNAL_TEMPLATES["field_service_report"] == "C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B"
        assert settings.WECOM_JOURNAL_TEMPLATES["field_daily_report"] == "3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3"
        assert settings.WECOM_JOURNAL_TEMPLATES["morning_briefing"] == "3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP"

    def test_live_vacation_ids_match_wecom_console(self):
        assert settings.WECOM_VACATION_ID_ANNUAL == 1
        assert settings.WECOM_VACATION_ID_PERSONAL == 2
        assert settings.WECOM_VACATION_ID_SICK == 3
        assert settings.WECOM_VACATION_ID_COMPENSATORY == 4


@pytest.mark.unit
class TestWeComApprovalAndJournalAPI:
    def test_fetch_approval_ids_paginates_and_deduplicates(self, monkeypatch):
        client = WeComAPIClient()
        monkeypatch.setattr(client, "get_access_token", lambda: "tok_test")

        calls: list[tuple[str, dict]] = []

        def fake_retry(method, url, **kwargs):
            calls.append((url, kwargs.get("json", {})))
            if kwargs["json"]["cursor"] == 0:
                return _FakeResponse({"errcode": 0, "sp_no_list": ["SP1", "SP2"], "next_cursor": 2})
            return _FakeResponse({"errcode": 0, "sp_no_list": ["SP2", "SP3"], "next_cursor": 0})

        monkeypatch.setattr("attendance_audit_integration.wecom_api._retry_request", fake_retry)

        ids = client.fetch_approval_ids(1700000000, 1700086400, template_id="TPL_LEAVE")
        assert ids == ["SP1", "SP2", "SP3"]
        assert len(calls) == 2
        assert "/cgi-bin/oa/getapprovalinfo" in calls[0][0]
        assert calls[0][1]["filters"] == [{"key": "template_id", "value": "TPL_LEAVE"}]

    def test_fetch_daily_reports_uses_official_two_step_journal_api(self, monkeypatch):
        client = WeComAPIClient()
        monkeypatch.setattr(client, "get_access_token", lambda: "tok_test")

        called_urls: list[str] = []

        def fake_retry(method, url, **kwargs):
            called_urls.append(url)
            if "/oa/journal/get_record_list" in url:
                return _FakeResponse({"errcode": 0, "journaluuid_list": ["J_001"], "endflag": 1})
            if "/oa/journal/get_record_detail" in url:
                return _FakeResponse(
                    {
                        "errcode": 0,
                        "info": {
                            "journal_uuid": "J_001",
                            "template_name": "现场每日10分钟工作报告",
                            "report_time": 1700040000,
                            "submitter": {"userid": "WangXu"},
                            "apply_data": {"contents": []},
                        },
                    }
                )
            raise AssertionError(f"Unexpected endpoint called: {url}")

        monkeypatch.setattr("attendance_audit_integration.wecom_api._retry_request", fake_retry)

        reports = client.fetch_daily_reports(
            1700000000,
            1700086400,
            template_ids=["3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3"],
        )
        assert len(reports) == 1
        assert reports[0]["journal_uuid"] == "J_001"
        assert reports[0]["template_id"] == "3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3"
        assert all("/oa/getreportdata" not in u for u in called_urls)
        assert any("/oa/journal/get_record_list" in u for u in called_urls)
        assert any("/oa/journal/get_record_detail" in u for u in called_urls)


@pytest.mark.unit
class TestApprovalAndJournalParsers:
    def test_parse_leave_approval_extracts_subtype_and_hours(self):
        from attendance_audit_integration.services.daily_audit import parse_approval_detail

        tz8 = timezone(timedelta(hours=8))
        begin_ts = int(datetime(2026, 8, 25, 9, 0, tzinfo=tz8).timestamp())
        end_ts = int(datetime(2026, 8, 25, 13, 0, tzinfo=tz8).timestamp())
        detail = {
            "sp_no": "202608250001",
            "sp_name": "请假",
            "sp_status": 2,
            "template_id": "Bs8114rcQrU1NHmkaEctMKKRDqSCo9YEdCeLAfjmv",
            "applyer": {"userid": "WangXu"},
            "apply_data": {
                "contents": [
                    {
                        "control": "Vacation",
                        "value": {
                            "vacation": {
                                "selector": {
                                    "options": [{"value": [{"text": "调休假", "lang": "zh_CN"}]}]
                                },
                                "attendance": {
                                    "date_range": {
                                        "new_begin": begin_ts,
                                        "new_end": end_ts,
                                        "new_duration": 14400,
                                    }
                                },
                            }
                        },
                    },
                    {"control": "Textarea", "value": {"text": "调休半天"}},
                ]
            },
        }
        parsed = parse_approval_detail(detail)
        assert parsed is not None
        assert parsed["approval_no"] == "202608250001"
        assert parsed["wecom_userid"] == "WangXu"
        assert parsed["approval_type"] == "leave"
        assert parsed["sub_type"] == "compensatory_leave"
        assert parsed["status"] == "approved"
        assert parsed["duration_hours"] == 4.0
        assert parsed["start_time"] == datetime(2026, 8, 25, 9, 0)
        assert parsed["end_time"] == datetime(2026, 8, 25, 13, 0)
        assert parsed["reason"] == "调休半天"

    def test_parse_business_trip_and_overtime_attendance_controls(self):
        from attendance_audit_integration.services.daily_audit import parse_approval_detail

        tz8 = timezone(timedelta(hours=8))
        b_ts = int(datetime(2026, 8, 26, 8, 30, tzinfo=tz8).timestamp())
        e_ts = int(datetime(2026, 8, 27, 17, 0, tzinfo=tz8).timestamp())
        trip_detail = {
            "sp_no": "202608260009",
            "sp_name": "出差申请",
            "sp_status": 2,
            "template_id": "ZvVcpYA7cWdCjM3hr8aDhde5CXcYfGw2pVhiDP",
            "applyer": {"userid": "ShiZhiTong"},
            "apply_data": {
                "contents": [
                    {
                        "control": "Attendance",
                        "value": {
                            "attendance": {
                                "date_range": {
                                    "new_begin": b_ts,
                                    "new_end": e_ts,
                                    "new_duration": 57600,
                                }
                            }
                        },
                    },
                    {"control": "Textarea", "value": {"text": "华能电厂现场调试"}},
                ]
            },
        }
        parsed = parse_approval_detail(trip_detail)
        assert parsed is not None
        assert parsed["approval_type"] == "business_trip"
        assert parsed["duration_hours"] == 16.0
        assert parsed["status"] == "approved"

    def test_parse_service_report_detects_customer_handwritten_signature(self):
        from attendance_audit_integration.services.daily_audit import parse_journal_detail

        tz8 = timezone(timedelta(hours=8))
        rep_ts = int(datetime(2026, 8, 29, 18, 0, tzinfo=tz8).timestamp())
        signed_payload = {
            "journal_uuid": "J_SVC_001",
            "template_id": "C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B",
            "template_name": "现场技术支持工作报告",
            "report_time": rep_ts,
            "submitter": {"userid": "WangXu"},
            "apply_data": {
                "contents": [
                    {
                        "control": "Text",
                        "title": [{"text": "客户单位名称与现场地点"}],
                        "value": {"text": "华能北京热电厂"},
                    },
                    {
                        "control": "File",
                        "title": [{"text": "客户现场确认签名（手机触摸屏手写）"}],
                        "value": {"files": [{"file_id": "sig_file_123", "file_url": "https://img.example.com/sig.png"}]},
                    },
                ]
            },
        }
        parsed = parse_journal_detail(signed_payload)
        assert parsed is not None
        assert parsed["is_service_report"] is True
        assert parsed["is_customer_signed"] is True
        assert parsed["signature_image_url"] == "https://img.example.com/sig.png"

        unsigned_payload = {
            **signed_payload,
            "journal_uuid": "J_SVC_002",
            "apply_data": {
                "contents": [
                    {
                        "control": "Text",
                        "title": [{"text": "客户单位名称与现场地点"}],
                        "value": {"text": "华能北京热电厂"},
                    },
                    {
                        "control": "File",
                        "title": [{"text": "客户现场确认签名（手机触摸屏手写）"}],
                        "value": {"files": []},
                    },
                ]
            },
        }
        parsed_unsigned = parse_journal_detail(unsigned_payload)
        assert parsed_unsigned is not None
        assert parsed_unsigned["is_service_report"] is True
        assert parsed_unsigned["is_customer_signed"] is False

    def test_sync_real_approvals_and_service_reports_write_idempotently(self, monkeypatch):
        from attendance_audit_integration.services import daily_audit

        tz8 = timezone(timedelta(hours=8))
        ts_start = int(datetime(2026, 8, 29, 9, 0, tzinfo=tz8).timestamp())
        ts_end = int(datetime(2026, 8, 29, 17, 0, tzinfo=tz8).timestamp())

        monkeypatch.setattr(
            daily_audit.wecom_client,
            "fetch_approval_ids",
            lambda s, e, template_id=None: ["SP_OT_1"] if template_id == settings.WECOM_APPROVAL_TEMPLATES["overtime"] else [],
        )
        monkeypatch.setattr(
            daily_audit.wecom_client,
            "fetch_approval_detail",
            lambda sp_no: {
                "sp_no": sp_no,
                "sp_name": "加班申请",
                "sp_status": 2,
                "template_id": settings.WECOM_APPROVAL_TEMPLATES["overtime"],
                "applyer": {"userid": "WangXu"},
                "apply_data": {
                    "contents": [
                        {
                            "control": "Attendance",
                            "value": {
                                "attendance": {
                                    "date_range": {
                                        "new_begin": ts_start,
                                        "new_end": ts_end,
                                        "new_duration": 28800,
                                    }
                                }
                            },
                        }
                    ]
                },
            },
        )
        monkeypatch.setattr(
            daily_audit.wecom_client,
            "fetch_daily_reports",
            lambda s, e: [
                {
                    "journal_uuid": "J_SVC_99",
                    "template_id": settings.WECOM_JOURNAL_TEMPLATES["field_service_report"],
                    "report_time": ts_end,
                    "submitter": {"userid": "WangXu"},
                    "apply_data": {
                        "contents": [
                            {
                                "control": "File",
                                "title": [{"text": "客户现场确认签名"}],
                                "value": {"files": [{"file_id": "f1", "file_url": "https://sig.example/1.png"}]},
                            }
                        ]
                    },
                }
            ],
        )

        cursor = _RecordingCursor({"WangXu"})
        synced_approvals = daily_audit.sync_real_approvals(cursor, ts_start, ts_end)
        synced_reports = daily_audit.sync_real_daily_reports(cursor, ts_start, ts_end)

        assert synced_approvals == 1
        assert synced_reports == 1
        sqls = [sql for sql, _ in cursor.executed]
        assert any("INSERT INTO approvals" in s for s in sqls)
        assert any("INSERT INTO field_work_reports" in s for s in sqls)
        assert any("INSERT INTO service_reports" in s for s in sqls)
