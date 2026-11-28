import os
from datetime import date, timedelta
from attendance_audit_integration.config import settings
from attendance_audit_integration.mail_sender import (
    send_html_email,
    render_individual_anomaly_email,
    render_daily_summary_email,
    render_weekly_summary_email,
    render_monthly_preliminary_email,
    render_monthly_finalized_email,
    render_overdue_warning_email
)

def save_and_send_preview(name: str, subject: str, html_content: str):
    """Save the HTML content locally as a preview file and attempt to send via SMTP."""
    preview_dir = "preview"
    os.makedirs(preview_dir, exist_ok=True)
    file_path = os.path.join(preview_dir, f"{name}.html")
    
    # Save file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved local HTML preview to: [preview/{name}.html](file://{os.path.abspath(file_path)})")
    
    # Send email (TEST_MODE forces recipient to be john.xu@palmarytech.com)
    send_html_email(
        subject=subject,
        html_content=html_content,
        to_email="employee@company.com"
    )

def main():
    print("====================================================")
    print("      WeCom Attendance HTML Email Mock Testing      ")
    print("====================================================")
    print(f"Settings Mode: TEST_MODE = {settings.TEST_MODE}")
    print(f"SMTP Server: {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
    print(f"Default Redirect Target: {settings.TEST_RECIPIENT_EMAIL}")
    print("----------------------------------------------------\n")
    
    # Test 1: Daily Individual Anomaly Alert (Yesterday)
    print("[Test 1/5] Generating Daily Individual Anomaly Alert...")
    individual_html = render_individual_anomaly_email(
        employee_name="刘页",
        anomaly_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
        anomaly_type_desc="轨迹待对账",
        anomaly_reason_detail="打卡时间间隔较短：北京与海淀外勤打卡间隔 10 分钟，系统提示核实",
        first_clock_in="09:00:15 (北京朝阳研发中心)",
        last_clock_out="09:10:45 (海淀腾讯大厦)",
        security_status="设备打卡位置待核实"
    )
    save_and_send_preview("1_individual_anomaly", "考勤对账确认 - 刘页", individual_html)
    print("")

    # Test 2: Daily Company Summary (Yesterday)
    print("[Test 2/5] Generating Daily Company Attendance Summary...")
    anomaly_rows = """
    <tr style="border-bottom: 1px dashed #e2e8f0;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">刘页</td>
        <td style="padding: 6px; color: #555555;">技术工程师</td>
        <td style="padding: 6px; color: #b91c1c;">位置待核实</td>
        <td style="padding: 6px; color: #b91c1c;">设备打卡位置待核实</td>
        <td style="padding: 6px; color: #555555;">07-07 18:00</td>
    </tr>
    <tr style="border-bottom: 1px dashed #e2e8f0;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
        <td style="padding: 6px; color: #555555;">销售经理</td>
        <td style="padding: 6px; color: #b91c1c;">下午缺卡</td>
        <td style="padding: 6px; color: #555555;">正常</td>
        <td style="padding: 6px; color: #555555;">07-07 18:00</td>
    </tr>
    """
    deduction_history = """
    • <strong>刘页</strong>：因 昨日位置校验待确认，系统已登记 T+2 核对流程，请尽快确认补充说明。<br>
    • <strong>吕旭东</strong>：因 昨日下午缺卡，已发送对账提醒，建议 2 天内通过登记或说明折抵。
    """
    daily_summary_html = render_daily_summary_email(
        audit_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
        total_expected=19,
        total_normal=15,
        total_on_leave=2,
        total_anomalies=2,
        anomaly_rows_html=anomaly_rows,
        deduction_history_html=deduction_history
    )
    save_and_send_preview("2_daily_summary", "公司每日考勤对账汇总日报", daily_summary_html)
    print("")

    # Test 3: Weekly Company Report
    print("[Test 3/5] Generating Weekly Company Attendance Report...")
    weekly_anomaly_rows = """
    <tr style="border-bottom: 1px solid #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
        <td style="padding: 6px; color: #555555;">销售部</td>
        <td style="padding: 6px; color: #b91c1c;">2 次</td>
        <td style="padding: 6px; color: #b91c1c;">1.0 天</td>
        <td style="padding: 6px; color: #555555;">0.0 小时</td>
    </tr>
    <tr style="border-bottom: 1px solid #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">牛海庆</td>
        <td style="padding: 6px; color: #555555;">技术部</td>
        <td style="padding: 6px; color: #b91c1c;">1 次</td>
        <td style="padding: 6px; color: #b91c1c;">0.5 天</td>
        <td style="padding: 6px; color: #555555;">4.0 小时</td>
    </tr>
    """
    weekly_warning = """
    • <strong>吕旭东</strong>：本月已累计缺卡及待确认事项较多，建议HR协助跟进核实。
    """
    weekly_html = render_weekly_summary_email(
        week_range_desc="2026-06-29 至 2026-07-05",
        total_week_anomalies=5,
        total_resolved=3,
        total_unresolved=2,
        weekly_anomaly_rows=weekly_anomaly_rows,
        weekly_warning_list_rows=weekly_warning
    )
    save_and_send_preview("3_weekly_summary", "公司上周考勤待确认项汇总周报", weekly_html)
    print("")

    # Test 4: Monthly Preliminary Report (1st of month)
    print("[Test 4/5] Generating Monthly Preliminary (Pre-estimation) Report...")
    preliminary_rows = """
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
        <td style="padding: 6px; color: #555555;">北京帕莫瑞科技有限公司</td>
        <td style="padding: 6px; color: #d97706;">2.0 天</td>
        <td style="padding: 6px; color: #d97706;">1.5 天</td>
        <td style="padding: 6px; color: #d97706;">对账流转中</td>
    </tr>
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">石志同</td>
        <td style="padding: 6px; color: #555555;">维恩科仪（北京）机械自动化设备有限公司</td>
        <td style="padding: 6px; color: #d97706;">0.0 天</td>
        <td style="padding: 6px; color: #d97706;">0.5 天</td>
        <td style="padding: 6px; color: #d97706;">对账流转中</td>
    </tr>
    """
    prelim_html = render_monthly_preliminary_email(
        audit_month="2026年06月",
        pending_appeals=4,
        pending_approvals=3,
        missing_daily_reports=2,
        rows_html=preliminary_rows
    )
    save_and_send_preview("4_monthly_preliminary", "公司上月考勤数据核对预估（月初对账版）", prelim_html)
    print("")

    # Test 5: Monthly Finalized Report (5th of month)
    print("[Test 5/5] Generating Monthly Finalized Report...")
    final_rows = """
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
        <td style="padding: 6px; color: #555555;">北京帕莫瑞科技有限公司</td>
        <td style="padding: 6px; color: #555555;">21.75</td>
        <td style="padding: 6px; color: #b91c1c;">2.00</td>
        <td style="padding: 6px; color: #b91c1c;">1.50</td>
        <td style="padding: 6px; text-align: right; font-weight: bold; color: #b91c1c;">-3.50 天</td>
    </tr>
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">石志同</td>
        <td style="padding: 6px; color: #555555;">维恩科仪（北京）机械自动化设备有限公司</td>
        <td style="padding: 6px; color: #555555;">21.75</td>
        <td style="padding: 6px; color: #b91c1c;">0.00</td>
        <td style="padding: 6px; color: #b91c1c;">0.50</td>
        <td style="padding: 6px; text-align: right; font-weight: bold; color: #b91c1c;">-0.50 天</td>
    </tr>
    """
    intercepted_logs = """
    • <strong>石志同</strong> 在 2026-06-14 的周末加班因 <em>未上传带有客户签字的现场服务报告扫描件</em>，暂不能确认为调休假。<br>
    • <strong>于艳丽</strong> 在 2026-06-20 出差日因 <em>未匹配到现场工作日报</em>，需核实补充出差说明。
    """
    comp_balance_html = """
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">吕旭东</td>
        <td style="padding: 6px; color: #555555;">8.0 H</td>
        <td style="padding: 6px; color: #10b981;">+8.0 H</td>
        <td style="padding: 6px; color: #ef4444;">-4.0 H</td>
        <td style="padding: 6px; text-align: right; font-weight: bold; color: #111111;">12.0 H</td>
    </tr>
    <tr style="border-bottom: 1px dashed #cbd5e1;">
        <td style="padding: 6px; font-weight: bold; color: #111111;">石志同</td>
        <td style="padding: 6px; color: #555555;">16.0 H</td>
        <td style="padding: 6px; color: #10b981;">+0.0 H (未上传凭证待补交)</td>
        <td style="padding: 6px; color: #ef4444;">-0.0 H</td>
        <td style="padding: 6px; text-align: right; font-weight: bold; color: #111111;">16.0 H</td>
    </tr>
    """
    final_html = render_monthly_finalized_email(
        audit_month="2026年06月",
        standard_workdays=22,
        total_absent_days=2.0,
        total_unpaid_leave_days=2.0,
        total_accrued_comp=8.0,
        final_rows_html=final_rows,
        intercepted_logs_html=intercepted_logs,
        comp_balance_html=comp_balance_html
    )
    save_and_send_preview("5_monthly_finalized", "公司上月考勤对账与实发决算报表 (最终锁定版)", final_html)
    print("")

    # Test 6: 7-Day Overdue Warning Email
    print("[Test 6/6] Generating Day 8 Overdue Warning Alert...")
    overdue_html = render_overdue_warning_email(
        employee_name="李文颖",
        overtime_date=(date.today() - timedelta(days=10)).strftime("%Y-%m-%d"),
        total_hours=8.0,
        days_elapsed=3
    )
    save_and_send_preview("6_overdue_warning", "⚠️ 考勤提示：调休假期使用进度提醒", overdue_html)
    print("")

    print("====================================================")
    print("  All HTML preview templates generated successfully! ")
    print("  You can view them locally in your browser.        ")
    print("====================================================")

if __name__ == "__main__":
    main()
