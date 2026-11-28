"""单元测试：测试数据填充的真伪判定逻辑（真实优先，缺口才造 mock）。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from attendance_audit_integration.mock_data_populator import (
    _approval_covers,
    _looks_like_teleport,
)
from attendance_audit_integration.services.daily_audit import (
    _extract_report_text_and_image,
)


@pytest.mark.unit
class TestApprovalCovers:
    def test_day_within_approval_range_is_covered(self):
        approvals_by_user = {"u1": [(datetime(2026, 7, 1), datetime(2026, 7, 5))]}
        assert _approval_covers(approvals_by_user, "u1", date(2026, 7, 3)) is True

    def test_day_outside_approval_range_is_not_covered(self):
        approvals_by_user = {"u1": [(datetime(2026, 7, 1), datetime(2026, 7, 5))]}
        assert _approval_covers(approvals_by_user, "u1", date(2026, 7, 10)) is False

    def test_unknown_user_is_not_covered(self):
        assert _approval_covers({}, "u_unknown", date(2026, 7, 3)) is False


@pytest.mark.unit
class TestLooksLikeTeleport:
    def test_same_city_short_distance_is_not_teleport(self):
        lats = [39.9042, 39.9100]
        lons = [116.4074, 116.4100]
        times = [datetime(2026, 7, 1, 9, 0), datetime(2026, 7, 1, 18, 0)]
        assert _looks_like_teleport(lats, lons, times) is False

    def test_beijing_shanghai_within_one_hour_is_teleport(self):
        lats = [39.9042, 31.2304]
        lons = [116.4074, 121.4737]
        times = [datetime(2026, 7, 1, 9, 0), datetime(2026, 7, 1, 10, 0)]
        assert _looks_like_teleport(lats, lons, times) is True

    def test_beijing_shanghai_next_day_is_not_teleport(self):
        """跨大距离但间隔足够长（次日），属正常出差轨迹，不应误判。"""
        lats = [39.9042, 31.2304]
        lons = [116.4074, 121.4737]
        times = [datetime(2026, 7, 1, 9, 0), datetime(2026, 7, 2, 9, 0)]
        assert _looks_like_teleport(lats, lons, times) is False

    def test_missing_coordinates_are_skipped_without_error(self):
        lats = [None, 39.9042]
        lons = [None, 116.4074]
        times = [datetime(2026, 7, 1, 9, 0), datetime(2026, 7, 1, 10, 0)]
        assert _looks_like_teleport(lats, lons, times) is False


@pytest.mark.unit
class TestExtractReportTextAndImage:
    def test_extracts_text_and_first_image_url(self):
        raw = {
            "contents": {
                "control_list": [
                    {"type": "Text", "value": "今日出差现场支持"},
                    {"type": "Photo", "url": "http://img.example.com/1.jpg"},
                    {"type": "Photo", "url": "http://img.example.com/2.jpg"},
                ]
            }
        }
        summary, image_url = _extract_report_text_and_image(raw)
        assert "今日出差现场支持" in summary
        assert image_url == "http://img.example.com/1.jpg"

    def test_no_text_or_image_returns_empty_and_none(self):
        summary, image_url = _extract_report_text_and_image({"report_id": "r1"})
        assert summary == ""
        assert image_url is None

    def test_duplicate_texts_are_deduplicated(self):
        raw = {"a": {"text": "重复内容"}, "b": {"value": "重复内容"}}
        summary, _ = _extract_report_text_and_image(raw)
        assert summary == "重复内容"
