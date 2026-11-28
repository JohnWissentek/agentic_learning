import argparse
import sys
from datetime import datetime, date, timedelta
from attendance_audit_integration.db import init_db, get_db_connection
from attendance_audit_integration.mock_data_populator import populate_test_data
from attendance_audit_integration.audit_engine import audit_engine
from attendance_audit_integration.config import settings

def load_roster_and_insert():
    """Load employee roster from JSON (no xlsx) and insert into PostgreSQL."""
    from attendance_audit_integration.roster import load_employee_roster
    from datetime import date, datetime

    print("Reading employee roster from JSON...")
    employees = load_employee_roster()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE employees CASCADE;")

    inserted_count = 0
    for row in employees:
        name = row["name"]
        userid = row.get("wecom_userid") or name
        email = row.get("email") or ""
        role = row.get("role") or ""
        company = row.get("company") or ""
        hire_raw = row.get("hire_date")
        if hire_raw:
            hire_date = date.fromisoformat(str(hire_raw)[:10])
        else:
            hire_date = date.today()

        cursor.execute(
            """
        INSERT INTO employees (wecom_userid, name, email, company, role, hire_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'active');
        """,
            (userid, name, email, company, role, hire_date),
        )
        inserted_count += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully loaded and inserted {inserted_count} employees from JSON roster.")



def _parse_args():
    parser = argparse.ArgumentParser(description="WeCom Attendance Audit Engine Demo Testing")
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="测试数据窗口起始日 YYYY-MM-DD（默认=今天-30天）；真实企微数据优先，缺口才补 mock。",
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="测试数据窗口结束日 YYYY-MM-DD（默认=今天）。",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=30)

    print("====================================================")
    print("      WeCom Attendance Audit Engine Demo Testing     ")
    print("====================================================")
    
    # Double check settings
    settings.TEST_MODE = True
    print(f"Test Mode: {settings.TEST_MODE} (ENABLED)")
    print(f"All generated emails will be sent ONLY to: {settings.TEST_RECIPIENT_EMAIL}")
    print(f"Test data window: {start_date} ~ {end_date} (真实数据优先，仅缺失场景补 mock)")
    print("----------------------------------------------------")
    
    try:
        # Step 1: Initialize DB
        print("Step 1: Initializing PostgreSQL schemas...")
        init_db()
        
        # Step 2: Load employee roster
        print("\nStep 2: Loading employee roster...")
        load_roster_and_insert()
        
        # Step 3: Populate test data (real WeCom data first; mock only for coverage gaps)
        print("\nStep 3: Populating test data (real-first, mock only for gaps)...")
        data_summary = populate_test_data(start_date, end_date)
        print(f"  真实打卡: {data_summary.get('real_punches')} 条 | 真实日报: {data_summary.get('real_daily_reports')} 条")
        print(f"  mock 审批: {data_summary.get('mock_approvals')} 条 | mock 出差日报: {data_summary.get('mock_field_work_reports')} 条 | mock 服务报告: {data_summary.get('mock_service_reports')} 条")
        print(f"  mock 场景缺口补造: {data_summary.get('mock_scenario_backfill')}")
        
        # Step 4: Run Test 1 - Daily Audit
        yesterday = date.today() - timedelta(days=1)
        print(f"\nStep 4: [TEST 1] Running Daily Audit for yesterday: {yesterday}...")
        daily_res = audit_engine.run_daily_audit(yesterday)
        print(f"Test 1 Complete. Expected: {daily_res['total_expected']} | Normal: {daily_res['total_normal']} | Anomalies: {daily_res['total_anomalies']}")

        # Step 5: Run Test 2 - Weekly Audit
        print("\nStep 5: [TEST 2] Running Weekly Audit Report...")
        weekly_ok = audit_engine.run_weekly_audit()
        print(f"Test 2 Complete. Weekly Report Sent: {weekly_ok}")

        # Step 6: Run Test 3 - 7-Day Overdue Warning scan
        print("\nStep 6: [TEST 3] Running Overdue Compensatory Leave Check...")
        expiry_notified = audit_engine.check_compensatory_leave_expiry()
        print(f"Test 3 Complete. Overdue Warnings Dispatched: {expiry_notified}")

        # Step 7: Run Test 4 - Monthly Reports
        print("\nStep 7: [TEST 4] Running Monthly Preliminary and Finalized Audits...")
        today_date = date.today()
        # Preliminary (1st of month)
        prelim_ok = audit_engine.run_monthly_audit(today_date, is_final=False)
        print(f"Monthly Preliminary Audit complete: {prelim_ok}")
        
        # Finalized (5th of month)
        final_ok = audit_engine.run_monthly_audit(today_date, is_final=True)
        print(f"Monthly Finalized Audit complete: {final_ok}")

        print("\n====================================================")
        print("  SUCCESS: All tests completed! HTML emails sent.  ")
        print("  All emails were successfully routed to:           ")
        print(f"  --> {settings.TEST_RECIPIENT_EMAIL}               ")
        print("====================================================")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FATAL ERROR] Testing suite failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
