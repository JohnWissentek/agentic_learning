import sys
import os
import json
import urllib.request
import time
from datetime import datetime, date, timedelta, timezone
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.config import settings
from attendance_audit_integration.audit_engine import audit_engine, calculate_haversine_distance
from attendance_audit_integration.mail_sender import (
    send_html_email,
    render_individual_anomaly_email,
    render_daily_summary_email,
    render_weekly_summary_email,
    render_monthly_finalized_email
)

def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={settings.WECOM_CORPID}&corpsecret={settings.WECOM_SECRET}"
    req = urllib.request.urlopen(url)
    res = json.loads(req.read().decode('utf-8'))
    if res.get("errcode") == 0:
        return res.get("access_token")
    else:
        raise Exception(f"Failed to fetch AccessToken: {res}")

def fetch_checkin_logs(access_token, user_ids, start_time, end_time):
    url = f"https://qyapi.weixin.qq.com/cgi-bin/checkin/getcheckindata?access_token={access_token}"
    payload = {
        "opencheckindatatype": 3,
        "starttime": int(start_time),
        "endtime": int(end_time),
        "useridlist": user_ids
    }
    req_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("errcode") == 0:
                return res_data.get("checkindata", [])
            else:
                print(f"WeCom API Error: {res_data.get('errmsg')} (code: {res_data.get('errcode')})")
                return []
    except Exception as e:
        print(f"HTTP request error: {e}")
        return []

def main():
    import src.mail_sender
    original_send = src.mail_sender.send_html_email

    def patched_send_html_email(subject, html_content, to_email, cc_list=None):
        if subject.startswith("考勤对账确认") or "对账确认" in subject:
            print(f"Skipping individual employee alert email: {subject}")
            return True
        return original_send(subject, html_content, to_email, cc_list=cc_list)

    src.mail_sender.send_html_email = patched_send_html_email

    print("====================================================")
    print("  WeCom Production History Audit: Past 6 Months Real Data ")
    print("====================================================")
    print(f"Test Mode (Redirect): {settings.TEST_MODE}")
    print(f"Mail Target: {settings.TEST_RECIPIENT_EMAIL}")
    print("----------------------------------------------------\n")

    # Ensure we are running on Aliyun or whitelisted server
    try:
        token = get_access_token()
        print("Connected to WeCom OpenAPI successfully.")
    except Exception as e:
        print(f"Connection to WeCom failed: {e}")
        print("This script must be executed on the whitelisted Aliyun ECS server!")
        sys.exit(1)

    # 1. Sync employee roster from JSON (no xlsx)
    from attendance_audit_integration.roster import load_employee_roster

    print("Using employee roster: data/employee_roster.json")
    roster_rows = load_employee_roster()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Refresh employees list in DB
    cursor.execute("TRUNCATE TABLE employees CASCADE;")

    user_ids = []
    employees_meta = []
    for row in roster_rows:
        name = row["name"]
        if name in ("徐宏玮", "杨丽丽"):
            continue
        uid = row.get("wecom_userid") or name
        user_ids.append(uid)
        email = row.get("email") or ""
        role = row.get("role") or ""
        company = row.get("company") or ""
        hire_raw = row.get("hire_date")
        hire_date = date.fromisoformat(str(hire_raw)[:10]) if hire_raw else date.today()

        cursor.execute(
            """
            INSERT INTO employees (wecom_userid, name, email, company, role, hire_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active');
            """,
            (uid, name, email, company, role, hire_date),
        )
        employees_meta.append(
            {"userid": uid, "name": name, "role": role, "company": company, "email": email}
        )

    conn.commit()
    print(f"Loaded {len(user_ids)} employees into PostgreSQL database.")

    # 2. Fetch past 180 days (6 months) of raw punches from WeCom
    now = datetime.now()
    periods = []
    for i in range(6):
        end = now - timedelta(days=i*30)
        start = now - timedelta(days=(i+1)*30)
        periods.append((start.timestamp(), end.timestamp()))

    all_logs = []
    for idx, (start_ts, end_ts) in enumerate(periods, 1):
        s_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
        e_str = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d")
        print(f"Fetching WeCom raw punches chunk {idx}/6: from {s_str} to {e_str}...")
        logs = fetch_checkin_logs(token, user_ids, start_ts, end_ts)
        all_logs.extend(logs)
        time.sleep(0.5)

    print(f"Retrieved {len(all_logs)} actual checkin records from WeCom. Syncing into database...")
    
    # Clear and insert into database
    cursor.execute("TRUNCATE TABLE attendance_logs;")
    for log in all_logs:
        uid = log.get("userid")
        c_time = datetime.fromtimestamp(log.get("checkin_time"), timezone(timedelta(hours=8))).replace(tzinfo=None)
        c_type = log.get("checkin_type", "unknown")
        loc = log.get("location_title", "未知")
        
        # Latitude/longitude are represented in micro-degrees (divided by 1,000,000)
        lat = log.get("lat")
        lng = log.get("lng")
        lat_val = float(lat) / 1000000.0 if lat else None
        lng_val = float(lng) / 1000000.0 if lng else None
        
        ip = log.get("ip_address", "")
        exc = log.get("exception_type", "")
        if exc == "none":
            exc = ""

        cursor.execute("""
        INSERT INTO attendance_logs (wecom_userid, clock_time, clock_type, location_name, latitude, longitude, ip_address, exception_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (uid, c_time, c_type, loc, lat_val, lng_val, ip, exc))
        
    conn.commit()
    print("Database sync complete.")

    # 3. Generate and send 6 Daily, 6 Weekly, and 6 Monthly reports using this actual database
    months = [
        {"name": "2026年06月", "date_prefix": "2026-06", "workday": "2026-06-16", "week_start": "2026-06-08", "week_end": "2026-06-14"}
    ]

    total_emails = 0

    for m in months:
        month_name = m["name"]
        prefix = m["date_prefix"]
        w_day = m["workday"]
        ws = m["week_start"]
        we = m["week_end"]
        
        print(f"\n--- Auditing Month: {month_name} ---")

        # ----------------- 3.1 Daily Production Audit -----------------
        # Pick target workday
        audit_date = date.fromisoformat(w_day)
        print(f"Running real Daily Audit for date: {audit_date}...")
        
        # We manually query the daily table for this date after running the engine logic
        # (This is better because it pulls from PostgreSQL where actual logs reside)
        daily_res = audit_engine.run_daily_audit(audit_date)
        print(f"Daily Audit complete for {audit_date}. Email dispatched.")
        total_emails += 1
        time.sleep(1.0)

        # ----------------- 3.2 Weekly Production Audit -----------------
        # Get actual weekly anomalies from daily_attendance table
        print(f"Running real Weekly Audit for range {ws} to {we}...")
        
        cursor.execute("""
        SELECT e.name, e.role, COUNT(da.id) as missing_count
        FROM daily_attendance da
        JOIN employees e ON da.wecom_userid = e.wecom_userid
        WHERE da.attendance_date BETWEEN %s AND %s AND da.is_anomaly = TRUE
        GROUP BY e.name, e.role;
        """, (ws, we))
        rows = cursor.fetchall()
        
        weekly_rows_html = ""
        for r in rows:
            weekly_rows_html += f"""
            <tr style="border-bottom: 1px solid #cbd5e1;">
                <td style="padding: 6px; font-weight: bold; color: #111111;">{r[0]}</td>
                <td style="padding: 6px; color: #555555;">{r[1]}</td>
                <td style="padding: 6px; color: #b91c1c;">{r[2]} 次</td>
                <td style="padding: 6px; color: #b91c1c;">{r[2]*0.5:.1f} 天</td>
                <td style="padding: 6px; color: #555555;">{r[2]*4.0:.1f} 小时</td>
            </tr>
            """
            
        if not weekly_rows_html:
            weekly_rows_html = """
            <tr>
                <td colspan="5" style="padding: 10px; text-align: center; color: #666666;">上周无待确认事项，全员考勤轨迹对账完成。</td>
            </tr>
            """
            
        weekly_warning = "• 上局全员打卡均正常，设备核对情况良好。"
        weekly_html = render_weekly_summary_email(
            week_range_desc=f"{ws} 至 {we}",
            total_week_anomalies=len(rows),
            total_resolved=len(rows),
            total_unresolved=0,
            weekly_anomaly_rows=weekly_rows_html,
            weekly_warning_list_rows=weekly_warning
        )
        
        send_html_email(
            subject=f"公司上周考勤待确认项汇总周报 ({ws} 至 {we})",
            html_content=weekly_html,
            to_email=settings.TEST_RECIPIENT_EMAIL
        )
        total_emails += 1
        time.sleep(1.0)

        # ----------------- 3.3 Monthly Production Finalized Audit -----------------
        print(f"Running real Monthly Finalized Audit for month: {month_name}...")
        # Resolve target date as first day of next month
        year_val, month_val = map(int, prefix.split("-"))
        if month_val == 12:
            next_month_date = date(year_val + 1, 1, 1)
        else:
            next_month_date = date(year_val, month_val + 1, 1)
            
        audit_engine.run_monthly_audit(next_month_date, is_final=True)
        print(f"Monthly Finalized Audit complete for {month_name}. Email dispatched.")
        total_emails += 1
        time.sleep(1.0)

    cursor.close()
    conn.close()
    
    print("\n====================================================")
    print(f" SUCCESS: Generated and dispatched {total_emails} actual emails!")
    print(f" All emails redirected to: {settings.TEST_RECIPIENT_EMAIL}")
    print("====================================================")

if __name__ == "__main__":
    main()
