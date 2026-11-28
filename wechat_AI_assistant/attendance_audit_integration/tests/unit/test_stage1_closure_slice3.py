"""Slice 3 黑盒契约测试：外出/请假抵扣计算、单条审批详情补全、月审前置同步与 HTTP/CLI 接线。"""
from __future__ import annotations

from datetime import datetime

import pytest

from attendance_audit_integration.audit_engine import audit_engine


@pytest.mark.unit
class TestApprovedOffsetCalculation:
    def test_outing_full_day_and_partial_day_offsets(self):
        from attendance_audit_integration.services.daily_audit import (
            compute_approved_offset_hours,
        )

        day_start = datetime(2026, 8, 25, 0, 0, 0)
        day_end = datetime(2026, 8, 25, 23, 59, 59)

        # 3 小时外出审批 → partial_offset_hours = 3.0，不视作全天请假/外出
        partial = compute_approved_offset_hours(
            [
                {
                    "approval_type": "outing",
                    "start_time": datetime(2026, 8, 25, 9, 0),
                    "end_time": datetime(2026, 8, 25, 12, 0),
                }
            ],
            day_start,
            day_end,
        )
        assert partial["has_full_day_outing"] is False
        assert partial["partial_offset_hours"] == 3.0

        # 全天 8.5 小时外出审批 → has_full_day_outing = True
        full = compute_approved_offset_hours(
            [
                {
                    "approval_type": "outing",
                    "start_time": datetime(2026, 8, 25, 8, 30),
                    "end_time": datetime(2026, 8, 25, 17, 0),
                }
            ],
            day_start,
            day_end,
        )
        assert full["has_full_day_outing"] is True
        assert full["partial_offset_hours"] == 0.0

    def test_leave_and_outing_combine_up_to_full_day_cap(self):
        from attendance_audit_integration.services.daily_audit import (
            compute_approved_offset_hours,
        )

        day_start = datetime(2026, 8, 25, 0, 0, 0)
        day_end = datetime(2026, 8, 25, 23, 59, 59)
        combined = compute_approved_offset_hours(
            [
                {
                    "approval_type": "leave",
                    "start_time": datetime(2026, 8, 25, 9, 0),
                    "end_time": datetime(2026, 8, 25, 11, 0),
                },
                {
                    "approval_type": "outing",
                    "start_time": datetime(2026, 8, 25, 14, 0),
                    "end_time": datetime(2026, 8, 25, 16, 0),
                },
            ],
            day_start,
            day_end,
        )
        assert combined["has_full_day_leave"] is False
        assert combined["has_full_day_outing"] is False
        assert combined["partial_offset_hours"] == 4.0


@pytest.mark.unit
class TestSingleApprovalEnrichmentAndFacadeWiring:
    def test_sync_single_approval_enriches_full_fields(self, monkeypatch):
        from attendance_audit_integration.services import daily_audit

        executed: list[tuple[str, tuple]] = []

        class _Cur:
            def execute(self, sql, params=None):
                executed.append((" ".join(sql.split()), tuple(params or ())))

            def fetchall(self):
                return [("WangXu",)]

        monkeypatch.setattr(
            daily_audit.wecom_client,
            "fetch_approval_detail",
            lambda sp_no: {
                "sp_no": sp_no,
                "sp_name": "外出申请",
                "sp_status": 2,
                "template_id": "3WK7K6pXKXzaUwzDh9KmqtjXGUvMThtDGwHAKzHo",
                "applyer": {"userid": "WangXu"},
                "apply_data": {
                    "contents": [
                        {
                            "control": "Attendance",
                            "value": {
                                "attendance": {
                                    "date_range": {
                                        "new_begin": 1787619600,
                                        "new_end": 1787630400,
                                        "new_duration": 10800,
                                    }
                                }
                            },
                        }
                    ]
                },
            },
        )

        ok = audit_engine.sync_single_approval(_Cur(), "SP_OUT_001")
        assert ok is True
        assert any("INSERT INTO approvals" in sql for sql, _ in executed)

    def test_fastapi_exposes_vacation_audit_endpoint(self):
        from attendance_audit_integration.main import app

        paths = {route.path for route in app.routes}
        assert "/audit/vacation" in paths

    def test_facade_exposes_monthly_period_presync(self, monkeypatch):
        assert hasattr(audit_engine, "sync_monthly_period_data")
        assert callable(audit_engine.sync_monthly_period_data)
