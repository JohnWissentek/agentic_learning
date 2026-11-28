"""周审服务（PRD F3 / §4.3）。

每周一 09:00 Cron 触发，生成上周（Mon–Sun）公司考勤异常残留周报:
- 上周异常总数 / 已消除 / 残留
- 月度累积缺卡 ≥2 的高危预警
"""
from __future__ import annotations

from datetime import date, timedelta

from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.payroll_cycle import get_payroll_cycle_start

logger = get_logger(__name__)


def run_weekly_audit() -> bool:
    """Generate Weekly company-wide summary report."""
    logger.info("Running Weekly Audit...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        today = date.today()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)

        week_range_desc = "%s 至 %s" % (
            last_monday.strftime("%Y-%m-%d"),
            last_sunday.strftime("%Y-%m-%d"),
        )

        # Count total anomalies of last week
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM daily_attendance
            WHERE attendance_date >= %s AND attendance_date <= %s AND is_anomaly = TRUE;
            """,
            (last_monday, last_sunday),
        )
        total_week_anomalies = cursor.fetchone()["count"]

        # BUG-06 fix: Query actual resolved/unresolved counts
        cursor.execute(
            """
            SELECT COUNT(DISTINCT da.id) as count
            FROM daily_attendance da
            JOIN approvals a ON da.wecom_userid = a.wecom_userid
              AND a.approval_type = 'punch_correction'
              AND a.status = 'approved'
              AND a.start_time::date = da.attendance_date
            WHERE da.attendance_date >= %s AND da.attendance_date <= %s AND da.is_anomaly = TRUE;
            """,
            (last_monday, last_sunday),
        )
        corrected = cursor.fetchone()["count"]
        total_resolved = corrected
        total_unresolved = total_week_anomalies - corrected

        # Employees with anomaly counts
        cursor.execute(
            """
            SELECT e.name, e.role, COUNT(a.id) as anomaly_count
            FROM daily_attendance a
            JOIN employees e ON a.wecom_userid = e.wecom_userid
            WHERE a.attendance_date >= %s AND a.attendance_date <= %s AND a.is_anomaly = TRUE
            GROUP BY e.name, e.role;
            """,
            (last_monday, last_sunday),
        )
        anomalies = cursor.fetchall()

        weekly_rows_list = []
        for a in anomalies:
            weekly_rows_list.append(
                '<tr style="border-bottom: 1px dashed #cbd5e1;">'
                '<td style="padding: 6px; font-weight: bold; color: #111111;">%s</td>'
                '<td style="padding: 6px; color: #555555;">%s</td>'
                '<td style="padding: 6px; color: #b91c1c;">%s 次</td>'
                '<td style="padding: 6px; color: #b91c1c;">%.1f 天</td>'
                '<td style="padding: 6px; color: #555555;">%.1f 小时</td>'
                "</tr>"
                % (
                    a["name"],
                    a["role"],
                    a["anomaly_count"],
                    a["anomaly_count"] * 0.5,
                    a["anomaly_count"] * 4.0,
                )
            )

        weekly_anomaly_rows = "".join(weekly_rows_list) if weekly_rows_list else (
            '<tr><td colspan="5" style="padding: 10px; text-align: center; color: #666666;">'
            "上周全公司无任何考勤异常残留，表现优异！</td></tr>"
        )

        # BUG-03 fix: Month cumulative uses payroll cycle start (26th)
        cycle_start = get_payroll_cycle_start(today)
        cursor.execute(
            """
            SELECT e.name, COUNT(a.id) as monthly_count
            FROM daily_attendance a
            JOIN employees e ON a.wecom_userid = e.wecom_userid
            WHERE a.attendance_date >= %s AND a.is_anomaly = TRUE
            GROUP BY e.name
            HAVING COUNT(a.id) >= 2;
            """,
            (cycle_start,),
        )
        warnings = cursor.fetchall()

        warning_lines = []
        for w in warnings:
            warning_lines.append(
                "• <strong>%s</strong>：本周期已累计无故缺卡 %s 次，旷工风险升高，请 HR 提前约谈。"
                % (w["name"], w["monthly_count"])
            )
        weekly_warning_list_rows = (
            "<br>".join(warning_lines)
            if warning_lines
            else "本周期无考勤高危预警员工。"
        )

        weekly_report_html = mail_sender.render_weekly_summary_email(
            week_range_desc=week_range_desc,
            total_week_anomalies=total_week_anomalies,
            total_resolved=total_resolved,
            total_unresolved=total_unresolved,
            weekly_anomaly_rows=weekly_anomaly_rows,
            weekly_warning_list_rows=weekly_warning_list_rows,
        )

        mail_sender.send_html_email(
            subject="公司上周考勤异常残留与旷工周报 (%s)" % week_range_desc,
            html_content=weekly_report_html,
            to_email=settings.ADMIN_EMAILS[0],
            cc_list=settings.ADMIN_EMAILS[1:],
        )

        cursor.close()
        return True
    except Exception as e:
        logger.error("Error in weekly audit: %s", e)
        raise
    finally:
        conn.close()
