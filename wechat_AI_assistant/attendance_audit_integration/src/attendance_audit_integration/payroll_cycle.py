"""薪资周期日期计算与封账管理（PRD §4.1 / F14 / E18）。

薪资周期：上月 26 日 00:00 ~ 本月 25 日 24:00。
月审草稿 25 日、终审 26 日。
"""
from __future__ import annotations

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)


def get_payroll_cycle_start(reference_date: date) -> date:
    """计算给定日期所在薪资周期的起始日（上月 26 日）。"""
    if reference_date.day >= 26:
        return reference_date.replace(day=26)
    return (reference_date.replace(day=1) - timedelta(days=1)).replace(day=26)


def get_monthly_cycle_range(target_date: date) -> tuple[date, date, str]:
    """计算月审薪资周期范围 (start_date, end_date, audit_month_label)。

    返回值:
        start_date: 上月 26 日
        end_date: 本月 25 日
        audit_month_label: end_date 的 "YYYY年MM月" 标签
    """
    if target_date.day >= 25:
        end_date = target_date.replace(day=25)
        start_date = (end_date.replace(day=1) - relativedelta(months=1)).replace(day=26)
    else:
        end_date = (target_date.replace(day=1) - timedelta(days=1)).replace(day=25)
        start_date = (end_date.replace(day=1) - relativedelta(months=1)).replace(day=26)

    audit_month = end_date.strftime("%Y年%m月")
    return start_date, end_date, audit_month


def is_payroll_period_locked(cursor, period_start: date, period_end: date) -> bool:
    """检查指定薪资周期是否已封账（E18：禁止重复终审）。"""
    cursor.execute(
        """
        SELECT 1 FROM payroll_period_locks
        WHERE period_start = %s AND period_end = %s
        LIMIT 1;
        """,
        (period_start, period_end),
    )
    return cursor.fetchone() is not None


def lock_payroll_period(
    cursor, period_start: date, period_end: date, audit_month_label: str
) -> None:
    """写入封账记录并追加审计日志（F14）。"""
    cursor.execute(
        """
        INSERT INTO payroll_period_locks (period_start, period_end, audit_month_label)
        VALUES (%s, %s, %s)
        ON CONFLICT (period_start, period_end) DO NOTHING;
        """,
        (period_start, period_end, audit_month_label),
    )
    cursor.execute(
        """
        INSERT INTO audit_logs (wecom_userid, action_type, description)
        VALUES (NULL, 'period_lock', %s);
        """,
        (f"封账锁定周期 {period_start}~{period_end} ({audit_month_label})",),
    )
    logger.info("Payroll period locked: %s ~ %s (%s)", period_start, period_end, audit_month_label)
