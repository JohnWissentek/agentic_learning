"""PRD v0.5 动态工时判定与 F15 补助口径单元测试。

覆盖异常场景：E24（区间截断）、E27（缺额分级）、E29（9.0h 顺延）、
E30（请假顺延 10:00+N）、E31/E33（补助减半判定边界）。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from attendance_audit_integration.services.expense_cross_audit import (
    decide_subsidy_entitlement,
)
from attendance_audit_integration.work_hours import evaluate_daily_work_hours

WORKDAY = date(2026, 8, 27)


def _dt(hhmm: str) -> datetime:
    hours_str, minutes_str = hhmm.split(":")
    return datetime(2026, 8, 27, int(hours_str), int(minutes_str))


class TestDynamicWorkHours:
    """制度 3.1.1：下班基准 = 上班打卡 + 8.5h，8:30 起算、18:30 封顶。"""

    def test_standard_full_day_10_00_arrival_is_normal(self):
        """10:00 到岗 + 18:30 下班 = 恰好 8.5h → normal（10:00 是推导截止，含边界）。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("10:00"), _dt("18:30"))
        assert verdict.status == "normal"
        assert verdict.presence_span_hours == 8.5

    def test_arrival_after_10_00_creates_shortfall(self):
        """10:30 到岗在窗口内不可能补足 8.5h → 缺额 0.5h 进核销流程。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("10:30"), _dt("18:30"))
        assert verdict.status == "pending_reconciliation"
        assert verdict.shortfall_hours == 0.5

    def test_early_arrival_counts_from_08_30(self):
        """07:30 早到从 08:30 起算（E24）：08:30–17:00 = 8.5h → normal。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("07:30"), _dt("17:00"))
        assert verdict.status == "normal"
        assert verdict.effective_start == _dt("08:30")

    def test_late_stay_capped_at_18_30(self):
        """晚走多坐不计（E24）：11:00 到岗坐到 20:00，截断 18:30 仍缺 1h。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("11:00"), _dt("20:00"))
        assert verdict.effective_end == _dt("18:30")
        assert verdict.status == "pending_reconciliation"
        assert verdict.shortfall_hours == 1.0

    def test_extended_lunch_requires_9_hours_and_caps_at_19_00(self):
        """午休满 1h 顺延（E29）：应出勤 9.0h、封顶 19:00。"""
        verdict = evaluate_daily_work_hours(
            WORKDAY, _dt("10:00"), _dt("19:00"), lunch_hours_taken=1.0
        )
        assert verdict.status == "normal"
        assert verdict.required_presence_hours == 9.0
        assert verdict.effective_end == _dt("19:00")

    def test_morning_leave_shifts_arrival_deadline(self):
        """上午请假 2h（E30）：应出勤 6.5h，12:00 到岗 18:30 下班 → normal（10:00+N）。"""
        verdict = evaluate_daily_work_hours(
            WORKDAY, _dt("12:00"), _dt("18:30"), approved_partial_leave_hours=2.0
        )
        assert verdict.status == "normal"
        assert verdict.required_presence_hours == 6.5

    def test_under_4_hours_actual_work_is_absent(self):
        """实际出勤 <4h 且无审批 → absent 旷工 1 天预警（制度 3.1.5.2）。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("14:00"), _dt("17:00"))
        assert verdict.status == "absent"
        assert verdict.actual_work_hours < 4.0

    def test_exactly_4_hours_actual_work_is_pending(self):
        """实际工作恰满 4h（含边界）→ 待核销而非旷工。"""
        verdict = evaluate_daily_work_hours(WORKDAY, _dt("14:00"), _dt("18:30"))
        assert verdict.actual_work_hours == 4.0
        assert verdict.status == "pending_reconciliation"

    def test_punch_order_violation_raises(self):
        with pytest.raises(ValueError):
            evaluate_daily_work_hours(WORKDAY, _dt("18:00"), _dt("09:00"))


class TestSubsidyEntitlement:
    """制度 4.2.3 差旅补助减半判定（F15，E31/E33 边界）。"""

    def test_onsite_4_hours_is_full(self):
        assert decide_subsidy_entitlement(4.0, 0.0, False) == "full"

    def test_onsite_under_4_hours_is_half(self):
        assert decide_subsidy_entitlement(3.9, 0.0, False) == "half"

    def test_combined_onsite_and_transit_reaches_full(self):
        """合并在岗判定：现场 2h + 在途 2h = 4h 且未折抵假 → 全额。"""
        assert decide_subsidy_entitlement(2.0, 2.0, False) == "full"

    def test_combined_with_leave_offset_stays_half(self):
        """当天办理了请假/年假折抵的，不适用合并在岗 → 减半。"""
        assert decide_subsidy_entitlement(2.0, 2.0, True) == "half"

    def test_combined_still_under_threshold_is_half(self):
        assert decide_subsidy_entitlement(1.0, 2.5, False) == "half"
