import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from attendance_audit_integration.config import settings
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

def send_html_email(subject: str, html_content: str, to_email: str, cc_list: list = None) -> bool:
    """Send an HTML formatted email. In TEST_MODE, overrides all recipients to徐宏玮's email."""
    if cc_list is None:
        cc_list = []

    original_to = to_email
    original_ccs = cc_list

    # TEST MODE Override Interceptor
    if settings.TEST_MODE:
        to_email = settings.TEST_RECIPIENT_EMAIL
        cc_list = []
        subject = f"[TEST MODE] {subject} (原本发给: {original_to}, 抄送: {', '.join(original_ccs)})"
        logger.info("[TEST MODE] Intercepted email. Redirecting from %s (CCs: %s) to %s", original_to, original_ccs, to_email)

    # Build Email Message
    msg = MIMEMultipart()
    msg['From'] = f"{settings.SMTP_SENDER_NAME} <{settings.SMTP_SENDER}>"
    msg['To'] = to_email
    if cc_list:
        msg['Cc'] = ", ".join(cc_list)
    msg['Subject'] = subject

    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    # All recipients (SMTP envelope needs both To and CC addresses)
    all_recipients = [to_email] + cc_list

    try:
        # Connect to SMTP Server
        if settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10.0)
        else:
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10.0)
            if settings.SMTP_USE_TLS:
                server.starttls()

        # Login with SMTP_USERNAME (auth) but send as SMTP_SENDER
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_SENDER, all_recipients, msg.as_string())
        logger.info("Email successfully sent to %s with subject: %s", to_email, subject)
        server.quit()
        return True
    except Exception as e:
        logger.error("[SMTP ERROR] Failed to send email to %s via SMTP server: %s", to_email, e)
        # Fallback logging
        logger.warning("--- Fallback Email Output ---")
        logger.warning("To: %s", to_email)
        logger.warning("CC: %s", cc_list)
        logger.warning("Subject: %s", subject)
        logger.warning("Body Length: %d characters.", len(html_content))
        return False

# ＝＝＝＝＝ HTML 模板渲染器 (Renderers) ＝＝＝＝＝

def render_individual_anomaly_email(employee_name: str, anomaly_date: str, anomaly_type_desc: str, anomaly_reason_detail: str, first_clock_in: str, last_clock_out: str, security_status: str) -> str:
    """Render HTML for the Daily Individual Anomaly Alert email."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #b91c1c; padding-bottom: 5px; margin-bottom: 15px; color: #b91c1c; font-size: 16px;">公司考勤集成审计层 - 昨日考勤打卡需确认</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        核对日期：{anomaly_date} &nbsp;|&nbsp; 生成时间：{generation_time}
    </p>
    
    <p style="margin-top: 15px; font-weight: bold; color: #111111;">尊敬的 {employee_name}：</p>
    <p style="margin-top: 5px; color: #333333;">系统在对昨日您的考勤打卡进行勾稽核对时，发现以下记录需要您的协助确认。请尽快核对并于 2 个工作日内完成补充登记或说明：</p>
    
    <div style="border: 1px solid #fca5a5; background-color: #fef2f2; padding: 12px 15px; margin: 15px 0; border-radius: 4px; color: #991b1b;">
        <strong>待确认打卡明细：</strong><br>
        - **打卡状态**：<span style="font-weight: bold; text-decoration: underline;">{anomaly_type_desc}</span><br>
        - **核实详情**：{anomaly_reason_detail}<br>
        - **打卡记录**：上班打卡：{first_clock_in} | 下班打卡：{last_clock_out}<br>
        - **设备校验状态**：{security_status}
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 打卡核对指引 ]</h3>
    <ol style="padding-left: 20px; margin-top: 5px; color: #555555;">
        <li style="margin-bottom: 4px;"><strong>坐班遗忘打卡</strong>：办公区坐班不设个人遗忘类常规补卡；若因打卡硬件、门禁或网络故障导致异常，请提交“故障核销”并附佐证（制度 3.2.2）。</li>
        <li style="margin-bottom: 4px;"><strong>外勤/出差漏卡</strong>：请提交补卡申请并附行程单、客票或现场工作照片等客观佐证，审核属实后据实核销（制度 3.2.3）。</li>
        <li style="margin-bottom: 4px;"><strong>调休/年假冲抵</strong>：工时缺额请在当天或当月内发起请假审批，使用“调休”或“年假”按小时冲抵（被动抵扣每月合计上限 4 小时，制度 3.2.1）。</li>
        <li style="margin-bottom: 4px;"><strong>逾期未确认</strong>：超出 <strong>T+2 宽限期</strong>未办理的缺额，将按无酬缺勤口径（月基本工资÷21.75÷8×缺勤小时）列入月度对账导出，由 HR 人工处理。</li>
    </ol>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件由系统考勤集成审计层自动发出，请勿直接回复。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        employee_name=employee_name,
        anomaly_date=anomaly_date,
        generation_time=now_str,
        anomaly_type_desc=anomaly_type_desc,
        anomaly_reason_detail=anomaly_reason_detail,
        first_clock_in=first_clock_in,
        last_clock_out=last_clock_out,
        security_status=security_status
    )

def render_daily_summary_email(audit_date: str, total_expected: int, total_normal: int, total_on_leave: int, total_anomalies: int, anomaly_rows_html: str, deduction_history_html: str) -> str:
    """Render HTML for the Daily Company Attendance Summary email."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 1px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司每日考勤对账汇总日报</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        业务日期：{audit_date} &nbsp;|&nbsp; 生成时间：{generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; padding: 12px 0; margin-top: 15px; margin-bottom: 20px; color: #333333; background-color: #f8fafc; padding-left: 10px; border-radius: 4px;">
        <strong>当日考勤数据：</strong><br>
        - 在岗应到人数：{total_expected} 人<br>
        - 正常出勤核对：{total_normal} 人<br>
        - 请假/出差/调休：{total_on_leave} 人<br>
        <strong>- 缺卡/待确认人数：<span style="color: #b91c1c; font-weight: bold;">{total_anomalies} 人</span></strong>
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #b91c1c;">[ 当日打卡待确认人员清单 ]</h3>
    <table style="width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">岗位</th>
                <th style="padding: 6px;">待确认项</th>
                <th style="padding: 6px;">设备校验状态</th>
                <th style="padding: 6px;">复核截止</th>
            </tr>
        </thead>
        <tbody>
            {anomaly_rows_html}
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 历史对账调结/核销流水变动 ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        {deduction_history_html}
    </div>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此日报由系统自动发出，请勿回复。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        audit_date=audit_date,
        generation_time=now_str,
        total_expected=total_expected,
        total_normal=total_normal,
        total_on_leave=total_on_leave,
        total_anomalies=total_anomalies,
        anomaly_rows_html=anomaly_rows_html,
        deduction_history_html=deduction_history_html
    )

def render_weekly_summary_email(week_range_desc: str, total_week_anomalies: int, total_resolved: int, total_unresolved: int, weekly_anomaly_rows: str, weekly_warning_list_rows: str) -> str:
    """Render HTML for the Weekly Company Attendance Summary email."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 1px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司上周考勤待确认项汇总周报</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        业务周期：{week_range_desc} &nbsp;|&nbsp; 生成时间：{generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border: 1px solid #e2e8f0; padding: 12px; margin-bottom: 20px; border-radius: 4px; background-color: #f8fafc; font-size: 12px; color: #333333;">
        <strong>周报对账摘要：</strong><br>
        上周累计产生待确认打卡 {total_week_anomalies} 次，截至今日周一，已通过补充登记核销 {total_resolved} 次，仍有 <strong><span style="color: #b91c1c;">{total_unresolved} 项逾期未确认</span></strong>，系统将转交HR部门进行对账复核。
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #b91c1c;">[ 待确认考勤对账明细 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">部门</th>
                <th style="padding: 6px;">待确认次数</th>
                <th style="padding: 6px;">建议核对天数</th>
                <th style="padding: 6px;">需核实工时</th>
            </tr>
        </thead>
        <tbody>
            {weekly_anomaly_rows}
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 考勤打卡待确认人员提示（月度累计） ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        {weekly_warning_list_rows}
    </div>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此周报由系统自动发出，请勿回复。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        week_range_desc=week_range_desc,
        generation_time=now_str,
        total_week_anomalies=total_week_anomalies,
        total_resolved=total_resolved,
        total_unresolved=total_unresolved,
        weekly_anomaly_rows=weekly_anomaly_rows,
        weekly_warning_list_rows=weekly_warning_list_rows
    )

def render_monthly_preliminary_email(audit_month: str, pending_appeals: int, pending_approvals: int, missing_daily_reports: int, rows_html: str) -> str:
    """Render HTML for the Monthly Company Preliminary (Pre-estimation) email."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #d97706; padding-bottom: 5px; margin-bottom: 15px; color: #d97706; font-size: 16px;">公司月度考勤数据核对预估 (草稿版)</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        核对月份：{audit_month} &nbsp;|&nbsp; 生成时间：{generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border: 1px solid #fcd34d; background-color: #fffbeb; padding: 12px 15px; margin: 15px 0; border-radius: 4px; color: #b45309; font-size: 12px;">
        <strong>⚠️ 提示：</strong><br>
        本报表为 <strong>月度考勤预对账草稿</strong>。用于协助核对本周期（上月26日至本月25日）的打卡记录，由于周期内部分假单、工作日报正在审批中，数据仍在正常流转中。<strong>最终对账决算月报将于每月 26 日正式锁定下发</strong>，届时数据将归档锁定。
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 对账进度统计 ]</h3>
    <ul style="padding-left: 20px; margin-top: 5px; color: #555555;">
        <li style="margin-bottom: 4px;">处于 T+2 宽限期内的待办申诉：<strong>{pending_appeals}</strong> 笔</li>
        <li style="margin-bottom: 4px;">主管审批列表中待处理考勤流程：<strong>{pending_approvals}</strong> 笔</li>
        <li style="margin-bottom: 4px;">出差需补交工作日志天数：<strong>{missing_daily_reports}</strong> 天</li>
    </ul>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 考勤待确认数据预览 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">签约公司</th>
                <th style="padding: 6px;">待确认事假天</th>
                <th style="padding: 6px;">待确认旷工天</th>
                <th style="padding: 6px;">待补充凭证</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件由系统自动发出，请勿回复。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        audit_month=audit_month,
        generation_time=now_str,
        pending_appeals=pending_appeals,
        pending_approvals=pending_approvals,
        missing_daily_reports=missing_daily_reports,
        rows_html=rows_html
    )

def render_monthly_finalized_email(audit_month: str, standard_workdays: int, total_absent_days: float, total_unpaid_leave_days: float, total_accrued_comp: float, unresolved_count: int, final_rows_html: str, intercepted_logs_html: str, comp_balance_html: str) -> str:
    """Render HTML for the Monthly Company Finalized Report email."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #111111; padding-bottom: 5px; margin-bottom: 15px; color: #111111; font-size: 16px;">公司月度考勤对账与实发决算报表 (最终锁定版)</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        结算月份：{audit_month} &nbsp;|&nbsp; 封账时间：{generation_time}
    </p>
    <p style="margin: 5px 0 15px 0; color: #888888; font-style: italic; font-size: 12px;">
        Oh, my money money come!
    </p>
    
    <div style="border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; padding: 12px 0; margin-top: 15px; margin-bottom: 20px; color: #111111; background-color: #f8fafc; padding-left: 10px; border-radius: 4px;">
        <strong>本期全司考勤核定（上月26日至本月25日）：</strong><br>
        - 应计薪满勤天数：{standard_workdays} 天<br>
        - 核定旷工天数：{total_absent_days} 天<br>
        - 核定事假天数：{total_unpaid_leave_days} 天<br>
        - 记增调休工时：{total_accrued_comp} 小时<br>
        <strong>- 月度待核实事项结清数：<span style="color: {unresolved_color}; font-weight: bold;">{unresolved_count} 笔 {unresolved_status}</span></strong>
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px solid #111111; padding-bottom: 4px; margin-top: 20px; margin-bottom: 10px; color: #111111;">[ 💵 本期考勤对账工资变动明细 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 5px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #e2e8f0; text-align: left; font-weight: bold;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">签约公司</th>
                <th style="padding: 6px;">标准计薪天</th>
                <th style="padding: 6px;">事假扣减天</th>
                <th style="padding: 6px;">旷工扣减天</th>
                <th style="padding: 6px; text-align: right;">应折日薪系数</th>
            </tr>
        </thead>
        <tbody>
            {final_rows_html}
        </tbody>
    </table>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #b91c1c;">[ ℹ️ 考勤对账凭证补充与复核说明 ]</h3>
    <div style="font-size: 12px; color: #555555; line-height: 1.8;">
        {intercepted_logs_html}
    </div>
    
    <h3 style="font-size: 13px; font-weight: bold; border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-top: 25px; margin-bottom: 10px; color: #111111;">[ 员工个人调休假余额库变结存 ]</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="border-bottom: 1px solid #cbd5e1; background-color: #f1f5f9; text-align: left;">
                <th style="padding: 6px;">姓名</th>
                <th style="padding: 6px;">上期结转(H)</th>
                <th style="padding: 6px;">本期新增(H)</th>
                <th style="padding: 6px;">本期抵扣/消耗(H)</th>
                <th style="padding: 6px; text-align: right;">本期结余余额(H)</th>
            </tr>
        </thead>
        <tbody>
            {comp_balance_html}
        </tbody>
    </table>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此报表已归档至考勤中间件数据库，并已正式封账，不可擅自更改。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Determine unresolved display color and status text
    if unresolved_count == 0:
        unresolved_color = "#10b981"
        unresolved_status = "(全部处理完毕)"
    else:
        unresolved_color = "#b91c1c"
        unresolved_status = "(仍有未结清项)"
    return template.format(
        audit_month=audit_month,
        generation_time=now_str,
        standard_workdays=standard_workdays,
        total_absent_days=total_absent_days,
        total_unpaid_leave_days=total_unpaid_leave_days,
        total_accrued_comp=total_accrued_comp,
        unresolved_count=unresolved_count,
        unresolved_color=unresolved_color,
        unresolved_status=unresolved_status,
        final_rows_html=final_rows_html,
        intercepted_logs_html=intercepted_logs_html,
        comp_balance_html=comp_balance_html
    )

def render_overdue_warning_email(employee_name: str, overtime_date: str, total_hours: float, days_elapsed: int) -> str:
    """Render HTML for the Day 8 Overdue warning email (CC'd to Xu, Xie, Wang, Kong, Wang)."""
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; color: #111111; line-height: 1.6; font-size: 13px; max-width: 600px; margin: 0 auto; padding: 15px;">
    <h2 style="border-bottom: 2px solid #d97706; padding-bottom: 5px; margin-bottom: 15px; color: #d97706; font-size: 16px;">⚠️ 考勤提示：调休假期使用进度提醒</h2>
    <p style="margin: 5px 0; color: #666666; font-size: 12px;">
        生成时间：{generation_time}
    </p>
    
    <p style="margin-top: 15px; font-weight: bold; color: #111111;">尊敬的 {employee_name}：</p>
    <p style="margin-top: 5px; color: #333333;">系统检测到您有一笔已审核通过的调休假已超出推荐使用时效。为保障您的调休权益与合理休息，请您知悉并尽快安排休假：</p>
    
    <div style="border: 1px solid #fcd34d; background-color: #fffbeb; padding: 12px 15px; margin: 15px 0; border-radius: 4px; color: #b45309;">
        <strong>调休进度明细：</strong><br>
        - **产生日期**：{overtime_date}<br>
        - **可休时长**：{total_hours} 小时<br>
        - **超期天数**：已过期 {days_elapsed} 天（推荐 7 天内休完）<br>
        - **当前状态**：<span style="font-weight: bold; text-decoration: underline;">未休假提醒中 (余额正常保留)</span>
    </div>
    
    <p style="color: #555555; margin-top: 15px;">
        <strong>致相关项目经理及部门主管：</strong><br>
        请主管及项目经理（孔紫初、王楠）合理协调该工段的项目现场进度，在项目空闲期**优先并尽快**安排该员工提交调休审批单，清理积压假期。
    </p>
    
    <p style="font-size: 11px; color: #888888; border-top: 1px dashed #e2e8f0; padding-top: 15px; margin-top: 35px; text-align: center;">
        此邮件抄送至总经理室（徐宏玮）、财务部（薛蕾、王晓）以及项目经理，由考勤集成审计层自动发出，请勿回复。
    </p>
</body>
</html>"""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        employee_name=employee_name,
        overtime_date=overtime_date,
        total_hours=total_hours,
        days_elapsed=days_elapsed,
        generation_time=now_str
    )
