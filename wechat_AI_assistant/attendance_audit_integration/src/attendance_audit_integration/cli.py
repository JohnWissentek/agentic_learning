"""CLI 入口：供 Cron / 运维触发日周月审与库初始化。"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from attendance_audit_integration.audit_engine import audit_engine
from attendance_audit_integration.config import validate
from attendance_audit_integration.db import init_db
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WeCom Attendance Audit Integration CLI",
        epilog="Examples: python -m attendance_audit_integration.cli daily --date 2026-07-04",
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    subparsers.add_parser("init-db", help="Initialize PostgreSQL database tables.")
    subparsers.add_parser("sync-roster", help="Sync employees roster list from WeCom.")

    daily_parser = subparsers.add_parser("daily", help="Run Daily Audit for target date.")
    daily_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date YYYY-MM-DD (Defaults to yesterday).",
    )

    subparsers.add_parser("weekly", help="Run Weekly Audit and send report.")
    subparsers.add_parser(
        "check-expiry",
        help="Scan unconsumed compensatory leaves and send overdue warnings.",
    )
    vac_parser = subparsers.add_parser(
        "vacation-audit",
        help="Sync real WeCom vacation balances (read-only) and audit backlog/leaver anomalies.",
    )
    vac_parser.add_argument(
        "--no-email",
        action="store_true",
        help="Run sync & anomaly analysis without sending alert emails.",
    )

    monthly_parser = subparsers.add_parser("monthly", help="Run Monthly Audit for payroll cycle.")
    monthly_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Reference date YYYY-MM-DD (Defaults to today).",
    )
    expense_parser = subparsers.add_parser(
        "expense-cross",
        help="Run Kingdee travel-subsidy cross audit (F15, read-only) for payroll cycle.",
    )
    expense_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Reference date YYYY-MM-DD (Defaults to today; cycle = prev 26th to 25th).",
    )

    monthly_parser.add_argument(
        "--final",
        action="store_true",
        help="Perform final locking audit (otherwise runs preliminary).",
    )
    monthly_parser.add_argument(
        "--sync",
        action="store_true",
        help="Pre-sync cycle approvals, journal reports, and vacation balances from WeCom.",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command != "init-db":
            validate()

        if args.command == "init-db":
            init_db()
            logger.info("init-db completed")
        elif args.command == "sync-roster":
            audit_engine.sync_employee_roster()
            logger.info("sync-roster completed")
        elif args.command == "daily":
            target_date = (
                date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
            )
            logger.info("Executing daily audit for %s", target_date)
            result = audit_engine.run_daily_audit(target_date)
            logger.info("Daily audit complete: %s", result)
        elif args.command == "weekly":
            logger.info("Executing weekly audit")
            audit_engine.run_weekly_audit()
            logger.info("Weekly audit complete")
        elif args.command == "check-expiry":
            logger.info("Executing compensatory leave expiry scan")
            count = audit_engine.check_compensatory_leave_expiry()
            logger.info("Expiry scan complete, warnings_sent=%s", count)
        elif args.command == "vacation-audit":
            logger.info("Executing WeCom vacation balance & backlog audit")
            vac_result = audit_engine.run_vacation_balance_audit(
                send_email=not bool(args.no_email)
            )
            logger.info("Vacation audit complete: %s", vac_result)
        elif args.command == "monthly":
            target_date = date.fromisoformat(args.date) if args.date else date.today()
            is_final = bool(args.final)
            if bool(args.sync):
                logger.info("Pre-syncing cycle approvals, reports and vacation balances...")
                sync_res = audit_engine.sync_monthly_period_data(target_date)
                logger.info("Monthly pre-sync complete: %s", sync_res)
            logger.info(
                "Executing monthly audit reference=%s final=%s",
                target_date,
                is_final,
            )
            audit_engine.run_monthly_audit(target_date, is_final=is_final)
            logger.info("Monthly audit complete")
        elif args.command == "expense-cross":
            from attendance_audit_integration.audit_engine import (
                get_monthly_cycle_range,
                run_expense_cross_audit,
            )

            reference_date = date.fromisoformat(args.date) if args.date else date.today()
            cycle_start, cycle_end, _ = get_monthly_cycle_range(reference_date)
            logger.info(
                "Executing Kingdee expense cross audit cycle=%s~%s", cycle_start, cycle_end
            )
            cross_result = run_expense_cross_audit(cycle_start, cycle_end)
            logger.info("Expense cross audit complete: %s", cross_result)
    except Exception as exc:
        logger.error("Error executing command '%s': %s", args.command, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
