"""动态工时判定（制度 2026-08-21 版 3.1.1/3.1.2/3.1.5.2；PRD v0.5 §4.2-1）。

纯函数模块：给定当日首末打卡与已批短假小时，按公式算出截断后跨度、
实际工作时长、缺额与状态。不连库、不发邮件。

判定禁止写死 10:00——全勤到岗截止是「封顶 − 应出勤跨度」的推导值
（标准日 18:30 − 8.5h = 10:00；上午请假 N 小时自然顺延为 10:00 + N）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from attendance_audit_integration.config import settings


@dataclass
class WorkHoursVerdict:
    """单日动态工时判定结果。"""

    status: str  # normal / pending_reconciliation / absent
    effective_start: datetime
    effective_end: datetime
    presence_span_hours: float
    actual_work_hours: float
    required_presence_hours: float
    shortfall_hours: float


def _clock_on(workday: date, hhmm: str) -> datetime:
    hours_str, minutes_str = hhmm.split(":")
    return datetime.combine(workday, time(int(hours_str), int(minutes_str)))


def evaluate_daily_work_hours(
    workday: date,
    first_punch: datetime,
    last_punch: datetime,
    approved_partial_leave_hours: float = 0.0,
    lunch_hours_taken: float | None = None,
) -> WorkHoursVerdict:
    """按制度公式判定单日出勤状态。

    - 起算 = max(首卡, 08:30)（早到从 08:30 起算）
    - 截断 = min(末卡, 18:30 / 顺延日 19:00)（晚走多坐不计，E24）
    - 应出勤 = 8.5h（午休满 1h → 9.0h，E29）− 已批短假小时（E30）
    """
    if first_punch > last_punch:
        raise ValueError(
            "first_punch (%s) 晚于 last_punch (%s)，调用方应先按时间排序"
            % (first_punch, last_punch)
        )

    lunch_hours = (
        settings.LUNCH_DEFAULT_HOURS if lunch_hours_taken is None else lunch_hours_taken
    )
    is_extended_day = lunch_hours >= settings.LUNCH_EXTENDED_HOURS

    required_hours = (
        settings.REQUIRED_PRESENCE_HOURS_EXTENDED
        if is_extended_day
        else settings.REQUIRED_PRESENCE_HOURS
    )
    required_hours = max(required_hours - approved_partial_leave_hours, 0.0)

    window_start = _clock_on(workday, settings.WORK_DAY_WINDOW_START)
    window_cap = _clock_on(
        workday,
        settings.WORK_DAY_WINDOW_END_EXTENDED
        if is_extended_day
        else settings.WORK_DAY_WINDOW_END,
    )

    effective_start = max(first_punch, window_start)
    effective_end = min(last_punch, window_cap)

    span_hours = max(
        (effective_end - effective_start).total_seconds() / 3600.0, 0.0
    )
    actual_work_hours = max(span_hours - lunch_hours, 0.0)
    shortfall_hours = max(required_hours - span_hours, 0.0)

    if span_hours >= required_hours:
        status = "normal"
    elif actual_work_hours >= settings.ABSENT_DAY_THRESHOLD_HOURS:
        status = "pending_reconciliation"
    else:
        # 实际出勤 <4h 且短假不足以覆盖 → 旷工 1 天预警（制度 3.1.5.2）；
        # 系统只预警导出，处分由 HR 按 3.1.5.6 程序人工执行。
        status = "absent"

    return WorkHoursVerdict(
        status=status,
        effective_start=effective_start,
        effective_end=effective_end,
        presence_span_hours=round(span_hours, 2),
        actual_work_hours=round(actual_work_hours, 2),
        required_presence_hours=round(required_hours, 2),
        shortfall_hours=round(shortfall_hours, 2),
    )
