"""考勤审计引擎门面（Facade）。

本文件原为 1113 行的巨型模块，现已按框架总纲 4.9「1模块=1文件」铁律拆分。
此门面保留 ``AuditEngine`` 类和全部旧公开 API，确保 ``cli.py``、``main.py``
及已有测试的 import 路径不变。

真正的实现已迁入:
- geo.py              → calculate_haversine_distance
- holiday.py           → is_workday_db, is_statutory_holiday, seed_national_holidays, ...
- payroll_cycle.py     → get_payroll_cycle_start, get_monthly_cycle_range, lock/check
- compensatory.py      → decide_compensatory_accrual
- services/roster_sync.py    → sync_employee_roster
- services/daily_audit.py    → run_daily_audit, sync_real_punches, sync_real_daily_reports
- services/weekly_audit.py   → run_weekly_audit
- services/monthly_audit.py  → run_monthly_audit
- services/expiry_checker.py → check_compensatory_leave_expiry
- work_hours.py              → evaluate_daily_work_hours（v0.5 动态工时判定）
- services/expense_cross_audit.py → run_expense_cross_audit（F15 金蝶交叉审计）
"""
from __future__ import annotations

from datetime import date

# ── 公共 re-exports（向后兼容旧 import 路径）────────────────────
from attendance_audit_integration.compensatory import decide_compensatory_accrual  # noqa: F401
from attendance_audit_integration.geo import calculate_haversine_distance  # noqa: F401
from attendance_audit_integration.holiday import (  # noqa: F401
    is_statutory_holiday,
    is_workday_db,
    seed_national_holidays,
    send_annual_holiday_reminder,
)
from attendance_audit_integration.payroll_cycle import (  # noqa: F401
    get_monthly_cycle_range,
    get_payroll_cycle_start,
    is_payroll_period_locked,
    lock_payroll_period,
)
from attendance_audit_integration.services.daily_audit import (  # noqa: F401
    compute_approved_offset_hours,
    parse_approval_detail,
    parse_journal_detail,
    run_daily_audit,
    sync_period_approvals_and_reports,
    sync_real_approvals,
    sync_real_daily_reports,
    sync_real_punches,
    sync_single_approval,
)
from attendance_audit_integration.services.expense_cross_audit import (  # noqa: F401
    decide_subsidy_entitlement,
    run_expense_cross_audit,
)
from attendance_audit_integration.services.expiry_checker import check_compensatory_leave_expiry
from attendance_audit_integration.services.monthly_audit import run_monthly_audit
from attendance_audit_integration.services.roster_sync import sync_employee_roster
from attendance_audit_integration.services.vacation_audit import (  # noqa: F401
    analyze_vacation_anomalies,
    extract_hours_by_vacation_id,
    run_vacation_balance_audit,
)
from attendance_audit_integration.services.weekly_audit import run_weekly_audit
from attendance_audit_integration.work_hours import evaluate_daily_work_hours  # noqa: F401


class AuditEngine:
    """向后兼容的门面类——代理到独立 service 函数。"""

    @staticmethod
    def sync_employee_roster() -> list[str]:
        return sync_employee_roster()

    @staticmethod
    def run_daily_audit(target_date: date) -> dict:
        return run_daily_audit(target_date)

    @staticmethod
    def run_weekly_audit() -> bool:
        return run_weekly_audit()

    @staticmethod
    def run_monthly_audit(target_date: date, is_final: bool = False) -> bool:
        return run_monthly_audit(target_date, is_final=is_final)

    @staticmethod
    def check_compensatory_leave_expiry() -> int:
        return check_compensatory_leave_expiry()

    @staticmethod
    def run_vacation_balance_audit(*, send_email: bool = True) -> dict:
        return run_vacation_balance_audit(send_email=send_email)

    @staticmethod
    def sync_single_approval(cursor, sp_no: str) -> bool:
        return sync_single_approval(cursor, sp_no)

    @staticmethod
    def sync_monthly_period_data(reference_date: date) -> dict:
        """月审前置同步：同步周期审批、汇报（含签字服务报告）与企微真实假期余额。"""
        start_date, end_date, _ = get_monthly_cycle_range(reference_date)
        sync_stats = sync_period_approvals_and_reports(start_date, end_date)
        vac_stats = run_vacation_balance_audit(send_email=False)
        return {
            **sync_stats,
            "vacations_synced": vac_stats["synced_employees"],
        }


# 单例（cli.py 和 main.py 通过 ``from audit_engine import audit_engine`` 使用）
audit_engine = AuditEngine()
