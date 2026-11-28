"""国家法定节假日日历判定与种子填充（PRD F9 / §4.1）。

运行时仅查询 national_holidays 数据库表，不依赖外部 API 或第三方库。
chinesecalendar 库仅作为初始种子数据源（一次性 seed），之后由总经理手动维护。
"""
from __future__ import annotations

from datetime import date, timedelta

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)


def is_workday_db(target_date: date, cursor=None) -> bool:
    """判断 target_date 是否工作日（查询 national_holidays 表）。

    逻辑:
    1. 数据库中 day_type='holiday' → 非工作日
    2. 数据库中 day_type='workday' → 工作日（调休补班）
    3. 数据库无记录 → 周一至周五为工作日
    """
    from psycopg2.extras import RealDictCursor

    close_cursor = False
    close_conn = False
    conn = None

    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        close_cursor = True
        close_conn = True

    try:
        cursor.execute(
            "SELECT day_type FROM national_holidays WHERE holiday_date = %s;",
            (target_date,),
        )
        row = cursor.fetchone()

        if row:
            return row["day_type"] == "workday"  # 'holiday' -> False, 'workday' -> True
        return target_date.weekday() < 5  # Default: Mon-Fri
    finally:
        if close_cursor:
            cursor.close()
        if close_conn and conn:
            conn.close()


def is_statutory_holiday(target_date: date, cursor=None) -> bool:
    """判断 target_date 是否法定节假日（day_type='holiday'）。"""
    from psycopg2.extras import RealDictCursor

    close_cursor = False
    close_conn = False
    conn = None

    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        close_cursor = True
        close_conn = True

    try:
        cursor.execute(
            "SELECT day_type FROM national_holidays WHERE holiday_date = %s AND day_type = 'holiday';",
            (target_date,),
        )
        return cursor.fetchone() is not None
    finally:
        if close_cursor:
            cursor.close()
        if close_conn and conn:
            conn.close()


def seed_national_holidays(year: int) -> dict:
    """用 chinesecalendar 库一次性填充某年节假日（种子数据，之后手动维护）。"""
    try:
        from chinese_calendar import (
            get_holiday_detail,
            is_holiday,
            is_workday as cn_is_workday,
        )
    except ImportError:
        return {"error": "chinesecalendar library not installed. pip install chinesecalendar"}

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        inserted = 0
        skipped = 0

        start = date(year, 1, 1)
        end = date(year, 12, 31)
        curr = start

        while curr <= end:
            is_default_weekday = curr.weekday() < 5
            is_actual_workday = cn_is_workday(curr)
            is_actual_holiday = is_holiday(curr)

            entry_type = None
            desc = None

            if is_actual_holiday:
                entry_type = "holiday"
                try:
                    _, holiday_name = get_holiday_detail(curr)
                    desc = str(holiday_name) if holiday_name else "法定节假日"
                except Exception:
                    desc = "法定节假日"
                if not is_default_weekday:
                    desc += "(周末)"

            elif not is_default_weekday and is_actual_workday:
                entry_type = "workday"
                desc = "调休补班工作日"

            if entry_type:
                try:
                    cursor.execute(
                        """
                        INSERT INTO national_holidays (holiday_date, day_type, description)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (holiday_date) DO NOTHING;
                        """,
                        (curr, entry_type, desc),
                    )
                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

            curr += timedelta(days=1)

        conn.commit()
        cursor.close()
        return {"year": year, "inserted": inserted, "skipped_existing": skipped}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def send_annual_holiday_reminder() -> None:
    """每年 12-31 发送年度节假日录入提醒邮件给总经理（PRD §4.1 / F9）。"""
    next_year = date.today().year + 1
    subject = f"年度提醒：请录入 {next_year} 年国家法定节假日与调班调休计划"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #d97706; padding-bottom: 5px; color: #d97706;">&#9200; {next_year} 年度法定节假日录入提醒</h2>
    <p>尊敬的 徐宏玮 总经理：</p>
    <p>国务院办公厅通常已于近期发布 <strong>{next_year} 年</strong> 全国法定节假日及调休补班安排。为保障公司考勤审计系统在新年正常运行，请您于近日完成以下操作：</p>
    <ol>
        <li>录入 {next_year} 年所有 <strong>法定节假日</strong>（元旦、春节、清明、劳动节、端午、中秋、国庆）</li>
        <li>录入所有 <strong>调休补班工作日</strong>（因放假调休需要上班的周六/周日）</li>
    </ol>
    <div style="border: 1px solid #fcd34d; background: #fffbeb; padding: 12px; border-radius: 4px; color: #b45309; margin: 15px 0;">
        <strong>提示：</strong>您也可以通过 API <code>POST /holidays/seed/{next_year}</code> 一键自动填充 {next_year} 年数据，然后手动微调。
    </div>
    <p style="font-size: 11px; color: #888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件由考勤集成审计层于每年 12 月 31 日自动发出，请勿回复。
    </p>
</body></html>"""

    mail_sender.send_html_email(
        subject=subject,
        html_content=html,
        to_email=settings.ADMIN_EMAILS[0],
        cc_list=[],
    )
    logger.info("Annual holiday reminder sent for year %s.", next_year)
