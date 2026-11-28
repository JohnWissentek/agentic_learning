"""调休过期检查服务（PRD F7 / E7）。

每日 09:30 Cron 触发（日审之后），扫描所有 released 调休假:
- 超过 7 天未消的调休 → Day 8 发送联合警报邮件
- 不自动清零（E7 明确说明：仅警报，由 HR 跟进）
"""
from __future__ import annotations

from datetime import date

from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)


def check_compensatory_leave_expiry() -> int:
    """Scan all active compensatory leaves. Trigger overdue warning on Day 8.

    Returns:
        Number of overdue warnings sent.
    """
    logger.info("Checking for unconsumed compensatory leaves exceeding 7 days...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        today = date.today()
        cursor.execute(
            """
            SELECT c.*, e.name, e.email
            FROM compensatory_leave_details c
            JOIN employees e ON c.wecom_userid = e.wecom_userid
            WHERE c.status = 'released' AND c.used_hours < c.total_hours;
            """
        )
        active_leaves = cursor.fetchall()

        overdue_notified_count = 0
        for lv in active_leaves:
            accrual_date = lv["accrual_date"]
            days_elapsed = (today - accrual_date).days

            if days_elapsed >= 8:
                name = lv["name"]
                email = lv["email"]
                total = float(lv["total_hours"])
                used = float(lv["used_hours"])
                remaining = total - used

                logger.warning(
                    "Alert: %s has %.1f hours of compensatory leave overdue by %d days.",
                    name,
                    remaining,
                    days_elapsed,
                )

                overdue_body = mail_sender.render_overdue_warning_email(
                    employee_name=name,
                    overtime_date=accrual_date.strftime("%Y-%m-%d"),
                    total_hours=remaining,
                    days_elapsed=days_elapsed,
                )

                # F11（PRD v0.4 §4.2）：催用 TO=PM（孔紫初、王楠），CC=徐宏玮+薛蕾；禁止发/抄送被催员工
                mail_sender.send_html_email(
                    subject="⚠️ 考勤超期警报：员工 %s 调休假超期 7 天未休" % name,
                    html_content=overdue_body,
                    to_email=settings.PM_EMAILS[0],
                    cc_list=settings.PM_EMAILS[1:] + settings.F11_CC_EMAILS,
                )
                overdue_notified_count += 1

                cursor.execute(
                    """
                    INSERT INTO audit_logs (wecom_userid, action_type, description)
                    VALUES (%s, 'overdue_leave_alert', %s);
                    """,
                    (
                        lv["wecom_userid"],
                        "Compensatory leave accrued on %s has elapsed %d days. "
                        "Unused hours: %.1f." % (accrual_date, days_elapsed, remaining),
                    ),
                )

        conn.commit()
        cursor.close()
        return overdue_notified_count
    except Exception as e:
        conn.rollback()
        logger.error("Error in compensatory leave expiry check: %s", e)
        raise
    finally:
        conn.close()
