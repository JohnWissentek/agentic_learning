import os
import time
from datetime import date, timedelta
from attendance_audit_integration.config import settings
from attendance_audit_integration.mail_sender import (
    send_html_email,
    render_individual_anomaly_email,
    render_daily_summary_email,
    render_weekly_summary_email,
    render_monthly_finalized_email
)

def send_templated_email(subject: str, html_content: str) -> bool:
    """Send SMTP email (which TEST_MODE intercepts to john.xu@palmarytech.com)."""
    return send_html_email(
        subject=subject,
        html_content=html_content,
        to_email="employee@company.com"
    )

def main():
    print("====================================================")
    print("  WeCom Attendance 6-Month Test Run: 18 Emails Suite ")
    print("====================================================")
    print(f"Test Mode: {settings.TEST_MODE}")
    print(f"Recipient: {settings.TEST_RECIPIENT_EMAIL}")
    print("----------------------------------------------------\n")

    # Define past 6 months: January to June 2026 (based on current date July 2026)
    months = [
        {"name": "2026年06月", "date_prefix": "2026-06", "standard_days": 22},
        {"name": "2026年05月", "date_prefix": "2026-05", "standard_days": 20},
        {"name": "2026年04月", "date_prefix": "2026-04", "standard_days": 21},
        {"name": "2026年03月", "date_prefix": "2026-03", "standard_days": 22},
        {"name": "2026年02月", "date_prefix": "2026-02", "standard_days": 18},
        {"name": "2026年01月", "date_prefix": "2026-01", "standard_days": 21}
    ]

    total_sent = 0

    for m in months:
        month_name = m["name"]
        prefix = m["date_prefix"]
        sd = m["standard_days"]
        
        print(f"Processing Month: {month_name} ({prefix})")
        print("----------------------------------------------------")

        # 1. Daily Report (e.g. 15th of the month)
        daily_date = f"{prefix}-15"
        print(f" -> Generating Daily Report for: {daily_date}")
        
        anomaly_rows = f"""
        <tr style="border-bottom: 1px dashed #e2e8f0;">
            <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
            <td style="padding: 6px; color: #555555;">销售经理</td>
            <td style="padding: 6px; color: #b91c1c;">下午缺卡</td>
            <td style="padding: 6px; color: #555555;">设备校验正常</td>
            <td style="padding: 6px; color: #555555;">{prefix}-17 18:00</td>
        </tr>
        """
        deduction_history = f"• <strong>吕旭东</strong>：于 {daily_date} 缺打卡，已发起对账提醒，限期 T+2 补充申请说明。"
        daily_html = render_daily_summary_email(
            audit_date=daily_date,
            total_expected=18,
            total_normal=17,
            total_on_leave=0,
            total_anomalies=1,
            anomaly_rows_html=anomaly_rows,
            deduction_history_html=deduction_history
        )
        subject_daily = f"公司每日考勤对账汇总日报 ({daily_date})"
        if send_templated_email(subject_daily, daily_html):
            total_sent += 1
        time.sleep(1.0) # Prevent rate limits

        # 2. Weekly Report (e.g. Week of 8th to 14th)
        weekly_range = f"{prefix}-08 至 {prefix}-14"
        print(f" -> Generating Weekly Report for: {weekly_range}")
        
        weekly_rows = """
        <tr style="border-bottom: 1px solid #cbd5e1;">
            <td style="padding: 6px; font-weight: bold; color: #111111;">于艳丽</td>
            <td style="padding: 6px; color: #555555;">技术部</td>
            <td style="padding: 6px; color: #b91c1c;">1 次</td>
            <td style="padding: 6px; color: #b91c1c;">0.5 天</td>
            <td style="padding: 6px; color: #555555;">4.0 小时</td>
        </tr>
        """
        weekly_warning = "• <strong>于艳丽</strong>：上周累计缺卡及待确认事项 1 次，请及时登录系统上传对账说明。"
        weekly_html = render_weekly_summary_email(
            week_range_desc=weekly_range,
            total_week_anomalies=3,
            total_resolved=2,
            total_unresolved=1,
            weekly_anomaly_rows=weekly_rows,
            weekly_warning_list_rows=weekly_warning
        )
        subject_weekly = f"公司上周考勤待确认项汇总周报 ({weekly_range})"
        if send_templated_email(subject_weekly, weekly_html):
            total_sent += 1
        time.sleep(1.0)

        # 3. Monthly Finalized Report
        print(f" -> Generating Monthly Finalized Report for: {month_name}")
        
        final_rows = f"""
        <tr style="border-bottom: 1px dashed #cbd5e1;">
            <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
            <td style="padding: 6px; color: #555555;">北京帕莫瑞科技有限公司</td>
            <td style="padding: 6px; color: #555555;">{sd}</td>
            <td style="padding: 6px; color: #b91c1c;">0.50</td>
            <td style="padding: 6px; color: #b91c1c;">0.00</td>
            <td style="padding: 6px; text-align: right; font-weight: bold; color: #b91c1c;">-0.50 天</td>
        </tr>
        """
        intercepted_logs = f"• <strong>吕旭东</strong> 在 {prefix}-15 发生的缺打卡超期未完成对账，按事假扣减半日薪计入决算。"
        comp_balance_html = """
        <tr style="border-bottom: 1px dashed #cbd5e1;">
            <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
            <td style="padding: 6px; color: #555555;">12.0 H</td>
            <td style="padding: 6px; color: #10b981;">+0.0 H</td>
            <td style="padding: 6px; color: #ef4444;">-0.0 H</td>
            <td style="padding: 6px; text-align: right; font-weight: bold; color: #111111;">12.0 H</td>
        </tr>
        """
        final_html = render_monthly_finalized_email(
            audit_month=month_name,
            standard_workdays=sd,
            total_absent_days=0.0,
            total_unpaid_leave_days=0.5,
            total_accrued_comp=0.0,
            final_rows_html=final_rows,
            intercepted_logs_html=intercepted_logs,
            comp_balance_html=comp_balance_html
        )
        subject_monthly = f"公司上月考勤对账与实发决算报表 (最终锁定版) ({month_name})"
        if send_templated_email(subject_monthly, final_html):
            total_sent += 1
        time.sleep(1.0)
        
        print(f"Month {month_name} reports sent successfully.\n")

    print("====================================================")
    print(f" Success: All {total_sent} test emails dispatched!")
    print(f" Target Recipient Inbox: {settings.TEST_RECIPIENT_EMAIL}")
    print("====================================================")

if __name__ == "__main__":
    main()
