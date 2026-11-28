"""月审服务（PRD F3/F4/F5/F6/F14 / §4.4–4.5）。

25 日 23:00 运行草稿版（preliminary）；26 日 09:00 运行终审锁定版（finalized）。
终审包含:
- 周末加班 vs 客户签字服务报告 复核（F5/F6/E5/E6）
- 出差工作日 vs 现场日报+水印照片 复核（F6）
- 缺勤/事假/旷工折算汇总
- 调休余额对账（上期结转 + 本期新增 - 本期消耗 = 期末余额）
- 封账锁定（F14/E18：同周期禁止重复终审）
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.compensatory import decide_compensatory_accrual
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.holiday import is_statutory_holiday, is_workday_db
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.payroll_cycle import (
    get_monthly_cycle_range,
    is_payroll_period_locked,
    lock_payroll_period,
)

logger = get_logger(__name__)


def run_monthly_audit(target_date: date, *, is_final: bool = False) -> bool:
    """Run Monthly Preliminary (25th) or Finalized (26th) Audit.

    Args:
        target_date: Reference date for cycle calculation.
        is_final: True for 终审锁定版 (26th), False for 草稿预估版 (25th).
    """
    start_date, end_date, audit_month = get_monthly_cycle_range(target_date)

    logger.info(
        "Running Monthly Audit (%s) for cycle: %s to %s (Month: %s)",
        "最终锁定版" if is_final else "草稿预估版",
        start_date,
        end_date,
        audit_month,
    )

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # E18: Check if period already locked
        if is_final and is_payroll_period_locked(cursor, start_date, end_date):
            logger.error(
                "薪资周期已封账，拒绝重复终审: %s ~ %s (%s)",
                start_date,
                end_date,
                audit_month,
            )
            raise RuntimeError(
                "payroll period already locked: %s~%s (%s)"
                % (start_date, end_date, audit_month)
            )

        # Count standard workdays using Chinese statutory holiday calendar (BUG-00 fix)
        standard_workdays = 0
        curr = start_date
        while curr <= end_date:
            if is_workday_db(curr, cursor):
                standard_workdays += 1
            curr += timedelta(days=1)

        # Get active employees
        cursor.execute(
            "SELECT wecom_userid, name, company FROM employees WHERE status = 'active';"
        )
        employees = cursor.fetchall()

        # Compound verification in final audit
        if is_final:
            _run_final_compound_checks(cursor, employees, start_date, end_date)

        # Compile payroll summary
        summary_rows: list[str] = []
        intercept_list: list[str] = []
        comp_balance_rows: list[str] = []

        total_absent_days = 0.0
        total_unpaid_leave_days = 0.0
        total_accrued_comp = 0.0

        dt_start = datetime.combine(start_date, datetime.min.time())
        dt_end = datetime.combine(end_date, datetime.max.time())

        for emp in employees:
            userid = emp["wecom_userid"]
            name = emp["name"]

            if (
                name in settings.EXCLUDED_NAMES
                or userid in settings.EXCLUDED_USERIDS
            ):
                continue

            # PRD v0.5（制度 3.1.5.2）：absent（出勤 <4h 无审批）按旷工 1 天预警；
            # 单侧缺卡/工时缺额（pending_*）不再自动折 0.5 天，只计「待核」条数
            # 供人工核销——兼容历史库中旧 'late' 记录一并归入待核。
            cursor.execute(
                """
                SELECT status, COUNT(*) as cnt FROM daily_attendance
                WHERE wecom_userid = %s AND attendance_date >= %s AND attendance_date <= %s
                  AND is_anomaly = TRUE
                  AND status IN ('absent', 'pending_single_punch',
                                 'pending_reconciliation', 'late')
                GROUP BY status;
                """,
                (userid, start_date, end_date),
            )
            anomaly_counts = cursor.fetchall()

            absent_days = 0.0
            pending_reconcile_count = 0
            for ac in anomaly_counts:
                if ac["status"] == "absent":
                    absent_days += ac["cnt"] * 1.0
                else:
                    pending_reconcile_count += ac["cnt"]
            total_absent_days += absent_days

            # Unpaid leave hours
            cursor.execute(
                """
                SELECT SUM(duration_hours) as leave_hours FROM approvals
                WHERE wecom_userid = %s AND approval_type = 'leave'
                  AND sub_type = 'unpaid_leave' AND status = 'approved'
                  AND start_time >= %s AND end_time <= %s;
                """,
                (userid, dt_start, dt_end),
            )
            leave_hours_row = cursor.fetchone()
            unpaid_leave_hours = (
                float(leave_hours_row["leave_hours"]) if leave_hours_row["leave_hours"] else 0.0
            )
            unpaid_leave_days = unpaid_leave_hours / 8.0
            total_unpaid_leave_days += unpaid_leave_days

            # Vacation balances
            cursor.execute(
                "SELECT * FROM vacation_balances WHERE wecom_userid = %s AND leave_type = 'compensatory';",
                (userid,),
            )
            bal_row = cursor.fetchone()
            comp_remaining = float(bal_row["remaining"]) if bal_row else 0.0
            comp_granted = float(bal_row["total_granted"]) if bal_row else 0.0  # noqa: F841
            comp_used = float(bal_row["total_used"]) if bal_row else 0.0  # noqa: F841

            # BUG-02 fix: Calculate carryover properly
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_hours), 0) as period_accrued
                FROM compensatory_leave_details
                WHERE wecom_userid = %s AND accrual_date >= %s AND accrual_date <= %s
                  AND status = 'released';
                """,
                (userid, start_date, end_date),
            )
            period_accrued = float(cursor.fetchone()["period_accrued"])

            cursor.execute(
                """
                SELECT COALESCE(SUM(duration_hours), 0) as period_used
                FROM approvals
                WHERE wecom_userid = %s AND approval_type = 'leave'
                  AND sub_type = 'compensatory_leave' AND status = 'approved'
                  AND start_time >= %s AND end_time <= %s;
                """,
                (userid, dt_start, dt_end),
            )
            period_used = float(cursor.fetchone()["period_used"])

            comp_carryover = comp_remaining - period_accrued + period_used
            total_accrued_comp += period_accrued

            # Build HTML rows
            if is_final:
                summary_rows.append(
                    '<tr style="border-bottom: 1px dashed #cbd5e1;">'
                    '<td style="padding: 6px; font-weight: bold; color: #111111;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%s</td>'
                    '<td style="padding: 6px; color: #b91c1c;">%.2f</td>'
                    '<td style="padding: 6px; color: #b91c1c;">%s</td>'
                    '<td style="padding: 6px; text-align: right; font-weight: bold;'
                    ' color: #b91c1c;">-%.2f 天</td></tr>'
                    % (
                        name,
                        emp["company"],
                        standard_workdays,
                        unpaid_leave_days,
                        "%.2f%s"
                        % (
                            absent_days,
                            "（另待核 %d 条）" % pending_reconcile_count
                            if pending_reconcile_count
                            else "",
                        ),
                        unpaid_leave_days + absent_days,
                    )
                )
                comp_balance_rows.append(
                    '<tr style="border-bottom: 1px dashed #cbd5e1;">'
                    '<td style="padding: 6px; font-weight: bold; color: #111111;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%.1f H</td>'
                    '<td style="padding: 6px; color: #10b981;">+%.1f H</td>'
                    '<td style="padding: 6px; color: #ef4444;">-%.1f H</td>'
                    '<td style="padding: 6px; text-align: right; font-weight: bold;'
                    ' color: #111111;">%.1f H</td></tr>'
                    % (name, comp_carryover, period_accrued, period_used, comp_remaining)
                )
            else:
                summary_rows.append(
                    '<tr style="border-bottom: 1px dashed #cbd5e1;">'
                    '<td style="padding: 6px; font-weight: bold; color: #111111;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%s</td>'
                    '<td style="padding: 6px; color: #d97706;">%.2f</td>'
                    '<td style="padding: 6px; color: #d97706;">%.2f</td>'
                    '<td style="padding: 6px; color: #d97706;">待核 %d 条，月初对账待定中</td></tr>'
                    % (name, emp["company"], unpaid_leave_days, absent_days,
                       pending_reconcile_count)
                )

        # Render & send email
        if is_final:
            cursor.execute(
                """
                SELECT e.name, c.accrual_date, c.total_hours, c.status
                FROM compensatory_leave_details c
                JOIN employees e ON c.wecom_userid = e.wecom_userid
                WHERE c.accrual_date >= %s AND c.accrual_date <= %s AND c.status = 'invalid';
                """,
                (start_date, end_date),
            )
            invalid_leaves = cursor.fetchall()
            for il in invalid_leaves:
                intercept_list.append(
                    "• <strong>%s</strong> 在 %s 的周末加班申请已被系统拦截封锁，原由："
                    "<em>缺失带有客户手写签字的《现场服务报告》电子扫描件</em>。"
                    % (il["name"], il["accrual_date"])
                )
            intercepted_logs_html = (
                "<br>".join(intercept_list)
                if intercept_list
                else "本月无异常加班拦截记录。"
            )

            cursor.execute(
                """
                SELECT COUNT(*) as count FROM daily_attendance
                WHERE attendance_date >= %s AND attendance_date <= %s AND is_anomaly = TRUE;
                """,
                (start_date, end_date),
            )
            unresolved_count = cursor.fetchone()["count"]

            monthly_html = mail_sender.render_monthly_finalized_email(
                audit_month=audit_month,
                standard_workdays=standard_workdays,
                total_absent_days=total_absent_days,
                total_unpaid_leave_days=total_unpaid_leave_days,
                total_accrued_comp=total_accrued_comp,
                unresolved_count=unresolved_count,
                final_rows_html="".join(summary_rows),
                intercepted_logs_html=intercepted_logs_html,
                comp_balance_html="".join(comp_balance_rows),
            )
            subject = "公司月度考勤终审与财务扣薪对账报表 (最终锁定版) - %s" % audit_month
        else:
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM daily_attendance
                WHERE attendance_date >= %s AND attendance_date <= %s AND is_anomaly = TRUE;
                """,
                (start_date, end_date),
            )
            pending_appeals = cursor.fetchone()["count"]

            cursor.execute(
                """
                SELECT COUNT(*) as count FROM approvals
                WHERE status != 'approved' AND start_time >= %s AND end_time <= %s;
                """,
                (dt_start, dt_end),
            )
            pending_result = cursor.fetchone()
            pending_approvals = pending_result["count"] if pending_result else 0

            cursor.execute(
                """
                SELECT COUNT(*) as count FROM daily_attendance
                WHERE attendance_date >= %s AND attendance_date <= %s
                  AND status = 'business_trip' AND is_anomaly = TRUE
                  AND anomaly_reason LIKE '%%缺失现场工作日报%%';
                """,
                (start_date, end_date),
            )
            missing_result = cursor.fetchone()
            missing_daily_reports = missing_result["count"] if missing_result else 0

            monthly_html = mail_sender.render_monthly_preliminary_email(
                audit_month=audit_month,
                pending_appeals=pending_appeals,
                pending_approvals=pending_approvals,
                missing_daily_reports=missing_daily_reports,
                rows_html="".join(summary_rows),
            )
            subject = "公司月度考勤数据预估快报 (草稿版) - %s" % audit_month

        mail_sender.send_html_email(
            subject=subject,
            html_content=monthly_html,
            to_email=settings.ADMIN_EMAILS[0],
            cc_list=settings.ADMIN_EMAILS[1:],
        )

        # F14: Lock payroll period after finalization
        if is_final:
            lock_payroll_period(cursor, start_date, end_date, audit_month)

        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error in monthly audit: %s", e)
        raise
    finally:
        conn.close()


def _run_final_compound_checks(
    cursor, employees: list, start_date: date, end_date: date
) -> None:
    """终审复合校验：周末加班 vs 服务报告、出差 vs 现场日报。"""
    logger.info("Enforcing monthly compound checks for service reports and daily reports...")

    dt_start = datetime.combine(start_date, datetime.min.time())
    dt_end = datetime.combine(end_date, datetime.max.time())

    for emp in employees:
        userid = emp["wecom_userid"]
        name = emp["name"]

        if name in settings.EXCLUDED_NAMES or userid in settings.EXCLUDED_USERIDS:
            continue

        # Check 1: Weekend Overtime vs signed Service Reports (F5/E5/E6)
        cursor.execute(
            """
            SELECT * FROM approvals
            WHERE wecom_userid = %s AND approval_type = 'overtime' AND status = 'approved'
              AND start_time >= %s AND end_time <= %s;
            """,
            (userid, dt_start, dt_end),
        )
        overtimes = cursor.fetchall()

        for ot in overtimes:
            ot_date = ot["start_time"].date()

            cursor.execute(
                """
                SELECT * FROM service_reports
                WHERE wecom_userid = %s AND report_date = %s AND is_customer_signed = TRUE;
                """,
                (userid, ot_date),
            )
            report = cursor.fetchone()

            accrual_status, reason_code = decide_compensatory_accrual(
                is_statutory=is_statutory_holiday(ot_date, cursor),
                has_signed_service_report=report is not None,
            )

            if accrual_status == "released":
                cursor.execute(
                    """
                    INSERT INTO compensatory_leave_details
                        (wecom_userid, accrual_date, total_hours, status)
                    VALUES (%s, %s, %s, 'released')
                    ON CONFLICT DO NOTHING;
                    """,
                    (userid, ot_date, ot["duration_hours"]),
                )
                cursor.execute(
                    """
                    INSERT INTO vacation_balances (wecom_userid, leave_type, total_granted, total_used)
                    VALUES (%s, 'compensatory', %s, 0.0)
                    ON CONFLICT (wecom_userid, leave_type) DO UPDATE
                    SET total_granted = vacation_balances.total_granted + EXCLUDED.total_granted;
                    """,
                    (userid, ot["duration_hours"]),
                )
                logger.info(
                    "Released %s compensatory leave hours for %s on %s.",
                    ot["duration_hours"],
                    name,
                    ot_date,
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO compensatory_leave_details
                        (wecom_userid, accrual_date, total_hours, status)
                    VALUES (%s, %s, %s, 'invalid')
                    ON CONFLICT DO NOTHING;
                    """,
                    (userid, ot_date, ot["duration_hours"]),
                )
                if reason_code == "statutory_holiday_no_comp":
                    logger.warning(
                        "Rejected overtime accrual for %s on %s: "
                        "statutory holiday cannot convert to compensatory leave (E5).",
                        name,
                        ot_date,
                    )
                else:
                    logger.warning(
                        "Rejected overtime accrual for %s on %s "
                        "due to missing signed service report (E6).",
                        name,
                        ot_date,
                    )

        # Check 2: Travel vs Daily Work Reports with photos (F6)
        cursor.execute(
            """
            SELECT * FROM approvals
            WHERE wecom_userid = %s AND approval_type = 'business_trip' AND status = 'approved'
              AND start_time >= %s AND end_time <= %s;
            """,
            (userid, dt_start, dt_end),
        )
        trips = cursor.fetchall()

        for tr in trips:
            curr_day = tr["start_time"].date()
            trip_end = tr["end_time"].date()
            while curr_day <= trip_end:
                if is_workday_db(curr_day, cursor):
                    cursor.execute(
                        """
                        SELECT * FROM field_work_reports
                        WHERE wecom_userid = %s AND report_date = %s
                          AND watermark_image_url IS NOT NULL;
                        """,
                        (userid, curr_day),
                    )
                    rep = cursor.fetchone()
                    if not rep:
                        cursor.execute(
                            """
                            INSERT INTO daily_attendance
                                (wecom_userid, attendance_date, status,
                                 is_anomaly, anomaly_reason)
                            VALUES (%s, %s, 'business_trip', TRUE,
                                    '出差日缺失现场工作日报或环境水印照片')
                            ON CONFLICT (wecom_userid, attendance_date) DO UPDATE
                            SET is_anomaly = TRUE,
                                anomaly_reason = EXCLUDED.anomaly_reason;
                            """,
                            (userid, curr_day),
                        )
                        logger.warning(
                            "Flagged travel anomaly for %s on %s (missing daily work report).",
                            name,
                            curr_day,
                        )
                curr_day += timedelta(days=1)
