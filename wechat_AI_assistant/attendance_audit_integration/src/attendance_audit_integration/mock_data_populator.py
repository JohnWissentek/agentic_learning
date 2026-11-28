"""测试数据填充：真实优先，缺口才造假（见 docs/pseudocode/mock_data_populator.md）。"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from attendance_audit_integration.audit_engine import (
    is_workday_db,
    sync_real_daily_reports,
    sync_real_punches,
)
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

# provenance 表用「表名 + 主键列」组合登记 mock 行；找不到主键列的表不参与自动清理
_PK_COLUMN_BY_TABLE = {
    "approvals": "approval_no",
    "field_work_reports": "report_no",
    "service_reports": "report_no",
    "attendance_logs": "id",
    "compensatory_leave_details": "id",
    "vacation_balances": "id",
}

_OFFICE_IP = "125.33.9.60"
_LOCATIONS = (
    "北京朝阳区朝阳北路研发中心",
    "客户现场-北京海淀区腾讯大厦",
    "客户现场-上海张江高科技园",
)


def _tag_mock(cursor, table_name: str, record_pk: str, scenario_id: str, reason: str) -> None:
    """登记一条 mock 记录的来源；未登记的行默认视为真实数据。"""
    cursor.execute(
        """
        INSERT INTO test_data_provenance (table_name, record_pk, scenario_id, reason)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (table_name, record_pk) DO NOTHING;
        """,
        (table_name, str(record_pk), scenario_id, reason),
    )


def _purge_previous_mock_rows(cursor) -> None:
    """只删掉上一轮本脚本登记过的 mock 行；真实数据/生产结果表不碰。"""
    cursor.execute("SELECT table_name, record_pk FROM test_data_provenance;")
    by_table: dict[str, list[str]] = {}
    for table_name, record_pk in cursor.fetchall():
        by_table.setdefault(table_name, []).append(record_pk)

    for table_name, pks in by_table.items():
        column = _PK_COLUMN_BY_TABLE.get(table_name)
        if not column or not pks:
            continue
        cursor.execute(
            "DELETE FROM %s WHERE %s::text = ANY(%%s);" % (table_name, column),
            (pks,),
        )
    cursor.execute("TRUNCATE TABLE test_data_provenance;")


def _seed_vacation_baseline(cursor, userid: str) -> None:
    cursor.execute(
        """
        INSERT INTO vacation_balances (wecom_userid, leave_type, total_granted, total_used)
        VALUES (%s, 'compensatory', 16.0, 4.0)
        ON CONFLICT (wecom_userid, leave_type) DO NOTHING
        RETURNING id;
        """,
        (userid,),
    )
    row = cursor.fetchone()
    if row:
        _tag_mock(cursor, "vacation_balances", row[0], "baseline_seed", "首次造数为该员工建立调休余额基线")


def _generate_mock_approvals_and_reports(cursor, employees: list[tuple], start_date: date, end_date: date) -> dict:
    """请假/出差/加班审批 + 客户签字服务报告：无真实批量拉取渠道，本轮固定按分布造数，全部登记 provenance。"""
    counts = {"approvals": 0, "field_work_reports": 0, "service_reports": 0}
    curr_date = start_date
    while curr_date <= end_date:
        for emp in employees:
            userid, _name = emp
            # is_workday_db 内部按 dict 游标取列(row["day_type"])，本函数用的是普通 tuple 游标，
            # 不能共用；不传 cursor 让它自开短连接（此处非高频路径，可接受连接开销）
            is_workday = is_workday_db(curr_date)
            if is_workday:
                rand = random.random()
                if 0.75 <= rand < 0.85:  # 10%：请假或出差审批
                    app_type = "leave" if random.random() < 0.5 else "business_trip"
                    sub_type = "annual_leave" if app_type == "leave" else None
                    app_no = "SP%s%04d" % (curr_date.strftime("%Y%m%d"), random.randint(1000, 9999))
                    cursor.execute(
                        """
                        INSERT INTO approvals
                            (approval_no, wecom_userid, approval_type, sub_type,
                             start_time, end_time, duration_hours, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 8.0, 'approved')
                        ON CONFLICT (approval_no) DO NOTHING;
                        """,
                        (
                            app_no, userid, app_type, sub_type,
                            datetime.combine(curr_date, datetime.min.time()),
                            datetime.combine(curr_date, datetime.max.time()),
                        ),
                    )
                    _tag_mock(cursor, "approvals", app_no, "E5" if app_type == "business_trip" else "leave_baseline",
                              "审批无真实批量拉取渠道，本轮固定造数覆盖 leave/business_trip 分支")
                    counts["approvals"] += 1

                    if app_type == "business_trip" and random.random() < 0.5:
                        rep_no = "REP%s%04d" % (curr_date.strftime("%Y%m%d"), random.randint(1000, 9999))
                        cursor.execute(
                            """
                            INSERT INTO field_work_reports (report_no, wecom_userid, report_date, work_summary)
                            VALUES (%s, %s, %s, '[MOCK] 出差现场支持，设备开箱调试。')
                            ON CONFLICT (report_no) DO NOTHING;
                            """,
                            (rep_no, userid, curr_date),
                        )
                        _tag_mock(cursor, "field_work_reports", rep_no, "E7_covered",
                                  "配合 mock 出差审批补一条日报，验证「有日报不告警」分支")
                        counts["field_work_reports"] += 1
                    # 50% 不补日报 → 与该 mock 出差审批组合，天然覆盖 E7「出差无日报」分支，无需额外造假
            else:
                if random.random() < 0.15:  # 15%：周末加班
                    app_no = "OT%s%04d" % (curr_date.strftime("%Y%m%d"), random.randint(1000, 9999))
                    day_start = datetime.combine(curr_date, datetime.min.time()) + timedelta(hours=9)
                    day_end = datetime.combine(curr_date, datetime.min.time()) + timedelta(hours=17)
                    cursor.execute(
                        """
                        INSERT INTO approvals
                            (approval_no, wecom_userid, approval_type, start_time, end_time,
                             duration_hours, status)
                        VALUES (%s, %s, 'overtime', %s, %s, 8.0, 'approved')
                        ON CONFLICT (approval_no) DO NOTHING;
                        """,
                        (app_no, userid, day_start, day_end),
                    )
                    _tag_mock(cursor, "approvals", app_no, "overtime_baseline",
                              "审批无真实批量拉取渠道，本轮固定造数覆盖周末加班分支")
                    counts["approvals"] += 1

                    if random.random() < 0.6:
                        rep_no = "SRV%s%04d" % (curr_date.strftime("%Y%m%d"), random.randint(1000, 9999))
                        cursor.execute(
                            """
                            INSERT INTO service_reports
                                (report_no, wecom_userid, report_date, is_customer_signed)
                            VALUES (%s, %s, %s, TRUE)
                            ON CONFLICT (report_no) DO NOTHING;
                            """,
                            (rep_no, userid, curr_date),
                        )
                        _tag_mock(cursor, "service_reports", rep_no, "E6_covered",
                                  "配合 mock 加班审批补一条签字服务报告，验证「有签字放行调休」分支")
                        counts["service_reports"] += 1
                    # 40% 不补签字报告 → 天然覆盖 E6「加班无客户签字」拒绝调休分支
        curr_date += timedelta(days=1)
    return counts


def _fetch_punch_day_summary(cursor, employee_ids: list[str], start_dt: datetime, end_dt: datetime) -> list[tuple]:
    cursor.execute(
        """
        SELECT wecom_userid, clock_time::date AS d, COUNT(*) AS cnt,
               COUNT(*) FILTER (WHERE exception_type IS NOT NULL) AS exc_cnt,
               array_agg(latitude ORDER BY clock_time) AS lats,
               array_agg(longitude ORDER BY clock_time) AS lons,
               array_agg(clock_time ORDER BY clock_time) AS times
        FROM attendance_logs
        WHERE wecom_userid = ANY(%s) AND clock_time BETWEEN %s AND %s
        GROUP BY wecom_userid, clock_time::date;
        """,
        (employee_ids, start_dt, end_dt),
    )
    return cursor.fetchall()


def _approval_covers(approvals_by_user: dict, userid: str, day: date) -> bool:
    for start_dt, end_dt in approvals_by_user.get(userid, []):
        if start_dt.date() <= day <= end_dt.date():
            return True
    return False


def _looks_like_teleport(lats: list, lons: list, times: list) -> bool:
    """粗粒度瞬移探测（复用现有 lat/lon，不引入新依赖）：同日相邻两次打卡跨度大但耗时短。"""
    pts = [(lat, lon, t) for lat, lon, t in zip(lats, lons, times) if lat is not None and lon is not None]
    for i in range(len(pts) - 1):
        lat1, lon1, t1 = pts[i]
        lat2, lon2, t2 = pts[i + 1]
        if abs(float(lat1) - float(lat2)) + abs(float(lon1) - float(lon2)) > 1.0:
            hours = abs((t2 - t1).total_seconds()) / 3600.0
            if 0 < hours < 4:
                return True
    return False


def _backfill_missing_scenarios(
    cursor,
    employees: list[tuple],
    employee_ids: list[str],
    start_date: date,
    end_date: date,
) -> dict:
    """仅当 E1/E11/E12 在真实打卡窗口里完全没出现时，才各补 1 条 mock 记录并登记 provenance。"""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    cursor.execute(
        """
        SELECT approval_no, wecom_userid, start_time, end_time FROM approvals
        WHERE status='approved' AND approval_type IN ('leave','business_trip')
          AND start_time <= %s AND end_time >= %s;
        """,
        (end_dt, start_dt),
    )
    approvals_by_user: dict[str, list] = {}
    for _no, userid, s, e in cursor.fetchall():
        approvals_by_user.setdefault(userid, []).append((s, e))

    day_rows = _fetch_punch_day_summary(cursor, employee_ids, start_dt, end_dt)
    covered_days = {(userid, d) for userid, d, *_ in day_rows}

    e1_found = any(
        cnt < 2 for _u, _d, cnt, _exc, _lats, _lons, _times in day_rows
        if not _approval_covers(approvals_by_user, _u, _d)
    )
    e11_found = any(exc_cnt > 0 for _u, _d, _cnt, exc_cnt, _lats, _lons, _times in day_rows)
    e12_found = any(_looks_like_teleport(lats, lons, times) for _u, _d, _cnt, _exc, lats, lons, times in day_rows)

    injected = {"E1": False, "E11": False, "E12": False}

    if employees and not e1_found:
        userid, _name = employees[0]
        day = _first_workday_without_data(start_date, end_date, userid, covered_days, approvals_by_user)
        if day:
            in_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=8, minutes=50)
            cursor.execute(
                """
                INSERT INTO attendance_logs
                    (wecom_userid, clock_time, clock_type, location_name, latitude, longitude, ip_address)
                VALUES (%s, %s, 'start_shift', %s, 39.9042, 116.4074, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (userid, in_time, _LOCATIONS[0], _OFFICE_IP),
            )
            row = cursor.fetchone()
            if row:
                _tag_mock(cursor, "attendance_logs", row[0], "E1",
                          "真实窗口内未出现漏卡场景，补 1 条仅上班卡缺下班卡的记录")
                injected["E1"] = True

    if employees and not e11_found:
        userid, _name = employees[-1]
        day = _first_workday_without_data(start_date, end_date, userid, covered_days, approvals_by_user)
        if day:
            in_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
            cursor.execute(
                """
                INSERT INTO attendance_logs
                    (wecom_userid, clock_time, clock_type, location_name, latitude, longitude, exception_type)
                VALUES (%s, %s, 'start_shift', 'Unknown Location', 39.9042, 116.4074, 'location_anomaly')
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (userid, in_time),
            )
            row = cursor.fetchone()
            if row:
                _tag_mock(cursor, "attendance_logs", row[0], "E11",
                          "真实窗口内未出现设备/定位异常码，补 1 条 exception_type 记录")
                injected["E11"] = True

    if len(employees) >= 2 and not e12_found:
        userid, _name = employees[len(employees) // 2]
        day = _first_workday_without_data(start_date, end_date, userid, covered_days, approvals_by_user)
        if day:
            t1 = datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
            t2 = datetime.combine(day, datetime.min.time()) + timedelta(hours=10)
            cursor.execute(
                """
                INSERT INTO attendance_logs
                    (wecom_userid, clock_time, clock_type, location_name, latitude, longitude, ip_address)
                VALUES (%s, %s, 'start_shift', %s, 39.9042, 116.4074, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (userid, t1, _LOCATIONS[0], _OFFICE_IP),
            )
            row1 = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO attendance_logs
                    (wecom_userid, clock_time, clock_type, location_name, latitude, longitude, ip_address)
                VALUES (%s, %s, 'outdoor', %s, 31.2304, 121.4737, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (userid, t2, _LOCATIONS[2], "223.104.3.45"),
            )
            row2 = cursor.fetchone()
            if row1 and row2:
                _tag_mock(cursor, "attendance_logs", row1[0], "E12", "真实窗口内未出现瞬移场景，补 2 条北京→上海瞬移打卡（1/2）")
                _tag_mock(cursor, "attendance_logs", row2[0], "E12", "真实窗口内未出现瞬移场景，补 2 条北京→上海瞬移打卡（2/2）")
                injected["E12"] = True

    return injected


def _first_workday_without_data(start_date, end_date, userid, covered_days, approvals_by_user) -> date | None:
    curr = start_date
    while curr <= end_date:
        if (
            is_workday_db(curr)
            and (userid, curr) not in covered_days
            and not _approval_covers(approvals_by_user, userid, curr)
        ):
            return curr
        curr += timedelta(days=1)
    return None


def _seed_expiry_test_fixture(cursor, employees: list[tuple]) -> int:
    """调休到期催告是「未来会怎样」的前瞻性测试夹具，无法从过去真实数据反推，固定造数并登记。"""
    accrual_date = date.today() - timedelta(days=10)
    seeded = 0
    for userid, _name in employees:
        cursor.execute(
            """
            INSERT INTO compensatory_leave_details
                (wecom_userid, accrual_date, total_hours, used_hours, status)
            VALUES (%s, %s, 8.0, 0.0, 'released')
            RETURNING id;
            """,
            (userid, accrual_date),
        )
        row = cursor.fetchone()
        if row:
            _tag_mock(cursor, "compensatory_leave_details", row[0], "expiry_seed",
                      "前瞻性测试夹具：人为造一条 10 天前已放行未消耗的调休，驱动到期催告场景")
            seeded += 1
    return seeded


def populate_test_data(start_date: date, end_date: date) -> dict:
    """填充 [start_date, end_date] 窗口的测试数据：真实优先，仅缺失场景才补 mock。

    - attendance_logs / field_work_reports：优先调企微真实接口拉取（复用 daily_audit 的
      sync_real_punches / sync_real_daily_reports），不清空已有真实历史；只有 E1/E11/E12
      在整个窗口里完全没出现时，才各补 1 条 mock 记录。
    - approvals / service_reports：本仓库暂无批量拉取真实历史的渠道（approvals 靠企微
      Webhook 实时推送；service_reports 无任何真实接口），本轮固定按分布造数，
      但每一行都登记进 test_data_provenance，测试报告可据此区分真伪。
    - 重跑本函数是幂等的：只清理上一轮由本函数登记的 mock 行，不动真实数据。
    """
    logger.info("Populating test data for window %s ~ %s (真实优先，缺口才造假)...", start_date, end_date)
    conn = get_db_connection()
    cursor = conn.cursor()

    _purge_previous_mock_rows(cursor)
    conn.commit()

    cursor.execute("SELECT wecom_userid, name FROM employees WHERE status='active';")
    employees = cursor.fetchall()
    if not employees:
        logger.error("No employees found in database. Run sync-roster first or check data/employee_roster.json.")
        cursor.close()
        conn.close()
        return {"error": "no_employees"}

    employee_ids = [emp[0] for emp in employees]
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())

    real_punches = sync_real_punches(cursor, employee_ids, start_ts, end_ts)
    real_reports = sync_real_daily_reports(cursor, start_ts, end_ts)
    conn.commit()

    for userid, _name in employees:
        _seed_vacation_baseline(cursor, userid)
    conn.commit()

    mock_counts = _generate_mock_approvals_and_reports(cursor, employees, start_date, end_date)
    conn.commit()

    injected_scenarios = _backfill_missing_scenarios(cursor, employees, employee_ids, start_date, end_date)
    conn.commit()

    expiry_seeded = _seed_expiry_test_fixture(cursor, employees)
    conn.commit()

    cursor.close()
    conn.close()

    summary = {
        "window": "%s ~ %s" % (start_date, end_date),
        "real_punches": real_punches,
        "real_daily_reports": real_reports,
        "mock_approvals": mock_counts["approvals"],
        "mock_field_work_reports": mock_counts["field_work_reports"],
        "mock_service_reports": mock_counts["service_reports"],
        "mock_scenario_backfill": injected_scenarios,
        "mock_expiry_fixtures": expiry_seeded,
    }
    logger.info("测试数据填充完成: %s", summary)
    return summary


def populate_mock_data() -> dict:
    """向后兼容旧调用名：默认窗口=近 30 天。新代码请直接调用 populate_test_data 并显式传窗口。"""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    return populate_test_data(start_date, end_date)
