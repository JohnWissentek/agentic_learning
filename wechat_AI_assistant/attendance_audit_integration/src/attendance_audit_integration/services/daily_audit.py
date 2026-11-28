"""日审服务（PRD v0.5 F1/F2 / §4.1–4.2；制度 2026-08-21 版）。

每日 09:00 Cron 触发，对 T-1 全天做打卡-假勤勾稽:
1. 同步打卡记录到 attendance_logs
2. 防作弊三维检测（exception_type / 瞬移 / IP）
3. 请假/出差覆盖判定（短假按小时抵扣应出勤）
4. 动态工时判定（work_hours.evaluate_daily_work_hours：
   起算 max(首卡,08:30)，截断 min(末卡,18:30/19:00)，应出勤 8.5h/9.0h−短假）
5. 异常邮件（含缺额公式明细）+ 公司日汇总邮件
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import psycopg2.extras
from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.geo import calculate_haversine_distance
from attendance_audit_integration.holiday import is_workday_db
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.services.roster_sync import sync_employee_roster
from attendance_audit_integration.wecom_api import wecom_client
from attendance_audit_integration.work_hours import evaluate_daily_work_hours

logger = get_logger(__name__)


def _is_excluded(name: str, userid: str) -> bool:
    """检查是否在考核排除名单中（PRD §4.1）。"""
    return name in settings.EXCLUDED_NAMES or userid in settings.EXCLUDED_USERIDS


def sync_real_punches(cursor, employee_ids: list[str], start_ts: int, end_ts: int) -> int:
    """拉取企微真实打卡并写入 attendance_logs（真实数据，不打 mock 标记）。

    抽成公共函数供 run_daily_audit 与 mock_data_populator.populate_test_data 复用，
    避免两处各自实现字段映射、行为不一致；依赖 attendance_logs 的
    UNIQUE(wecom_userid, clock_time, clock_type) 做幂等去重（E23）。
    返回实际写入的真实打卡条数。
    """
    if not employee_ids:
        return 0

    raw_punches = wecom_client.fetch_punches(start_ts, end_ts, employee_ids)
    tz_beijing = timezone(timedelta(hours=8))
    inserted = 0
    for p in raw_punches:
        wecom_userid = p["userid"]
        clock_time = datetime.fromtimestamp(p["checkin_time"], tz_beijing).replace(tzinfo=None)
        if p["checkin_type"] == "上班打卡":
            clock_type = "start_shift"
        elif p["checkin_type"] == "下班打卡":
            clock_type = "end_shift"
        else:
            clock_type = "outdoor"
        location_name = p.get("location_title", "Unknown")
        latitude = p.get("lat") / 1000000.0 if p.get("lat") else None
        longitude = p.get("lng") / 1000000.0 if p.get("lng") else None
        exception_type = (
            p.get("exception_type")
            if p.get("exception_type") and p.get("exception_type") != "未打卡"
            else None
        )

        cursor.execute(
            """
            INSERT INTO attendance_logs
                (wecom_userid, clock_time, clock_type, location_name,
                 latitude, longitude, exception_type, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (
                wecom_userid, clock_time, clock_type, location_name,
                latitude, longitude, exception_type,
                psycopg2.extras.Json(p),
            ),
        )
        if cursor.rowcount:
            inserted += 1

    return inserted


_TZ_BEIJING = timezone(timedelta(hours=8))

_SP_STATUS_MAP: dict[int, str] = {
    1: "pending",
    2: "approved",
    3: "rejected",
    4: "cancelled",
    6: "approved",   # 通过后撤销前兼容
    10: "pending",   # 会签中
}

_LEAVE_SUBTYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("年假", "annual_leave"),
    ("调休", "compensatory_leave"),
    ("事假", "unpaid_leave"),
    ("病假", "sick_leave"),
    ("婚假", "marriage_leave"),
    ("产假", "maternity_leave"),
    ("陪产假", "paternity_leave"),
    ("育儿假", "parental_leave"),
)


def _ts_to_beijing_naive(ts: int | float | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), _TZ_BEIJING).replace(tzinfo=None)


def _infer_approval_type(template_id: str, sp_name: str) -> str:
    reverse_map = {v: k for k, v in settings.WECOM_APPROVAL_TEMPLATES.items()}
    if template_id in reverse_map:
        return reverse_map[template_id]
    if "请假" in sp_name:
        return "leave"
    if "出差" in sp_name:
        return "business_trip"
    if "外出" in sp_name:
        return "outing"
    if "加班" in sp_name:
        return "overtime"
    if "补卡" in sp_name:
        return "punch_correction"
    return sp_name or "unknown"


def _infer_leave_subtype(selector: dict) -> str | None:
    options = selector.get("options") or []
    for opt in options:
        for val in opt.get("value") or []:
            text = (val.get("text") or "").strip()
            for keyword, subtype in _LEAVE_SUBTYPE_KEYWORDS:
                if keyword in text:
                    return subtype
            if text:
                return text
    return None


def parse_approval_detail(detail: dict) -> dict | None:
    """将企微 /oa/getapprovaldetail 返回的 info 解析为本地 approvals 表结构。"""
    if not detail:
        return None
    approval_no = detail.get("sp_no")
    wecom_userid = (detail.get("applyer") or {}).get("userid")
    if not approval_no or not wecom_userid:
        return None

    template_id = detail.get("template_id") or ""
    sp_name = detail.get("sp_name") or ""
    approval_type = _infer_approval_type(template_id, sp_name)
    status = _SP_STATUS_MAP.get(int(detail.get("sp_status", 1)), "pending")

    sub_type: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_hours: float = 0.0
    reasons: list[str] = []

    contents = (detail.get("apply_data") or {}).get("contents") or []
    for ctrl in contents:
        ctype = ctrl.get("control")
        val = ctrl.get("value") or {}

        if ctype == "Vacation":
            vac = val.get("vacation") or {}
            sub_type = _infer_leave_subtype(vac.get("selector") or {})
            dr = (vac.get("attendance") or {}).get("date_range") or {}
            start_time = _ts_to_beijing_naive(dr.get("new_begin"))
            end_time = _ts_to_beijing_naive(dr.get("new_end"))
            if dr.get("new_duration") is not None:
                duration_hours = round(float(dr["new_duration"]) / 3600.0, 2)
        elif ctype == "Attendance":
            att = val.get("attendance") or {}
            dr = att.get("date_range") or {}
            start_time = start_time or _ts_to_beijing_naive(dr.get("new_begin"))
            end_time = end_time or _ts_to_beijing_naive(dr.get("new_end"))
            if dr.get("new_duration") is not None and duration_hours == 0.0:
                duration_hours = round(float(dr["new_duration"]) / 3600.0, 2)
        elif ctype == "DateRange":
            dr = val.get("date_range") or {}
            start_time = start_time or _ts_to_beijing_naive(dr.get("new_begin"))
            end_time = end_time or _ts_to_beijing_naive(dr.get("new_end"))
            if dr.get("new_duration") is not None and duration_hours == 0.0:
                duration_hours = round(float(dr["new_duration"]) / 3600.0, 2)
        elif ctype == "PunchCorrection":
            pc = val.get("punch_correction") or {}
            pc_time = _ts_to_beijing_naive(pc.get("time"))
            start_time = start_time or pc_time
            end_time = end_time or pc_time
        elif ctype in ("Textarea", "Text"):
            text = (val.get("text") or "").strip()
            if text:
                reasons.append(text)

    if duration_hours == 0.0 and start_time and end_time and end_time > start_time:
        duration_hours = round((end_time - start_time).total_seconds() / 3600.0, 2)

    return {
        "approval_no": approval_no,
        "wecom_userid": wecom_userid,
        "approval_type": approval_type,
        "sub_type": sub_type,
        "start_time": start_time,
        "end_time": end_time,
        "duration_hours": duration_hours,
        "status": status,
        "reason": " / ".join(reasons),
        "raw_payload": detail,
    }


def sync_real_approvals(cursor, start_ts: int, end_ts: int) -> int:
    """定时批量拉取企微 5 类假勤审批单并幂等写入 approvals（解决 0 回调断流问题）。"""
    cursor.execute("SELECT wecom_userid FROM employees;")
    rows = cursor.fetchall()
    known_users: set[str] = set()
    for row in rows:
        uid = row["wecom_userid"] if isinstance(row, dict) else row[0]
        known_users.add(uid)

    sp_nos: list[str] = []
    seen_nos: set[str] = set()
    for tpl_id in settings.WECOM_APPROVAL_TEMPLATES.values():
        for sp_no in wecom_client.fetch_approval_ids(start_ts, end_ts, template_id=tpl_id):
            if sp_no not in seen_nos:
                seen_nos.add(sp_no)
                sp_nos.append(sp_no)

    synced = 0
    for sp_no in sp_nos:
        detail = wecom_client.fetch_approval_detail(sp_no)
        parsed = parse_approval_detail(detail)
        if not parsed:
            logger.warning("跳过无法解析的审批单: %s", sp_no)
            continue
        if known_users and parsed["wecom_userid"] not in known_users:
            logger.warning(
                "审批单 %s 申请人 %s 不在本地 employees 表中，跳过落库",
                sp_no,
                parsed["wecom_userid"],
            )
            continue

        cursor.execute(
            """
            INSERT INTO approvals
                (approval_no, wecom_userid, approval_type, sub_type,
                 start_time, end_time, duration_hours, status, reason, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (approval_no) DO UPDATE
            SET approval_type = EXCLUDED.approval_type,
                sub_type = EXCLUDED.sub_type,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                duration_hours = EXCLUDED.duration_hours,
                status = EXCLUDED.status,
                reason = EXCLUDED.reason,
                raw_payload = EXCLUDED.raw_payload;
            """,
            (
                parsed["approval_no"],
                parsed["wecom_userid"],
                parsed["approval_type"],
                parsed["sub_type"],
                parsed["start_time"],
                parsed["end_time"],
                parsed["duration_hours"],
                parsed["status"],
                parsed["reason"],
                psycopg2.extras.Json(parsed["raw_payload"]),
            ),
        )
        synced += 1

    return synced


def sync_single_approval(cursor, sp_no: str) -> bool:
    """按审批单号拉取详情并幂等写入完整字段至 approvals（供 Webhook 回调补全详情）。"""
    if not sp_no:
        return False
    detail = wecom_client.fetch_approval_detail(sp_no)
    parsed = parse_approval_detail(detail)
    if not parsed:
        logger.warning("无法解析单条审批详情: %s", sp_no)
        return False

    cursor.execute("SELECT wecom_userid FROM employees;")
    rows = cursor.fetchall()
    known_users = {row["wecom_userid"] if isinstance(row, dict) else row[0] for row in rows}
    if known_users and parsed["wecom_userid"] not in known_users:
        logger.warning(
            "单条审批 %s 申请人 %s 不在本地 employees 表中，跳过落库",
            sp_no,
            parsed["wecom_userid"],
        )
        return False

    cursor.execute(
        """
        INSERT INTO approvals
            (approval_no, wecom_userid, approval_type, sub_type,
             start_time, end_time, duration_hours, status, reason, raw_payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (approval_no) DO UPDATE
        SET approval_type = EXCLUDED.approval_type,
            sub_type = EXCLUDED.sub_type,
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            duration_hours = EXCLUDED.duration_hours,
            status = EXCLUDED.status,
            reason = EXCLUDED.reason,
            raw_payload = EXCLUDED.raw_payload;
        """,
        (
            parsed["approval_no"],
            parsed["wecom_userid"],
            parsed["approval_type"],
            parsed["sub_type"],
            parsed["start_time"],
            parsed["end_time"],
            parsed["duration_hours"],
            parsed["status"],
            parsed["reason"],
            psycopg2.extras.Json(parsed["raw_payload"]),
        ),
    )
    return True


def sync_period_approvals_and_reports(start_date: date, end_date: date) -> dict:
    """月审前置同步：一次性拉取整个周期的真实审批单与汇报（含客户签字服务报告）。"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())
        approvals_synced = sync_real_approvals(cursor, start_ts, end_ts)
        reports_synced = sync_real_daily_reports(cursor, start_ts, end_ts)
        conn.commit()
        cursor.close()
        return {
            "approvals_synced": approvals_synced,
            "reports_synced": reports_synced,
        }
    except Exception as exc:
        conn.rollback()
        logger.error("Error syncing period approvals/reports: %s", exc)
        raise
    finally:
        conn.close()


def compute_approved_offset_hours(
    active_approvals: list[dict],
    day_start: datetime,
    day_end: datetime,
) -> dict:
    """纯函数：计算当日已审批通过的请假/外出/出差覆盖与应出勤抵扣小时数。"""
    has_trip = any(a.get("approval_type") == "business_trip" for a in active_approvals)
    approved_leave_hours = 0.0
    approved_outing_hours = 0.0

    for approval in active_approvals:
        atype = approval.get("approval_type")
        if atype not in ("leave", "outing"):
            continue
        st = approval.get("start_time")
        et = approval.get("end_time")
        if not st or not et:
            continue
        overlap_start = max(st, day_start)
        overlap_end = min(et, day_end)
        if overlap_end > overlap_start:
            hours = (overlap_end - overlap_start).total_seconds() / 3600.0
            if atype == "leave":
                approved_leave_hours += hours
            else:
                approved_outing_hours += hours

    has_full_day_leave = approved_leave_hours >= settings.FULL_DAY_HOURS
    has_full_day_outing = (
        not has_full_day_leave and approved_outing_hours >= settings.FULL_DAY_HOURS
    )
    if has_full_day_leave or has_full_day_outing:
        partial_offset_hours = 0.0
    else:
        partial_offset_hours = min(
            round(approved_leave_hours + approved_outing_hours, 2),
            settings.FULL_DAY_HOURS,
        )

    return {
        "has_trip": has_trip,
        "has_full_day_leave": has_full_day_leave,
        "has_full_day_outing": has_full_day_outing,
        "approved_leave_hours": round(approved_leave_hours, 2),
        "approved_outing_hours": round(approved_outing_hours, 2),
        "partial_offset_hours": partial_offset_hours,
    }


def _extract_report_text_and_image(raw_report: dict) -> tuple[str, str | None]:
    """从企微日报原始表单里最佳努力抽取文字摘要与第一张图片/文件链接。

    自建应用日报表单的 control_list 结构随企业模板自定义、无固定 schema，
    这里按控件通用字段名做递归兜底扫描（非精确解析）；raw_payload 会完整落库，
    若后续拿到该企业真实模板的 control_id 映射，应改为精确抽取（见伪代码注意事项）。
    """
    texts: list[str] = []
    image_url: str | None = None

    def _walk(node) -> None:
        nonlocal image_url
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    if key in ("text", "value", "content") and value.strip():
                        texts.append(value.strip())
                    elif key in ("url", "file_url", "media_url") and value.startswith("http"):
                        if image_url is None:
                            image_url = value
                else:
                    _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw_report)
    summary = " / ".join(dict.fromkeys(texts)) if texts else ""
    return summary, image_url


def parse_journal_detail(raw_report: dict) -> dict | None:
    """解析企微官方 oa/journal/get_record_detail（兼容旧 report_id 结构）并识别客户手写签名。"""
    if not raw_report:
        return None
    report_no = raw_report.get("journal_uuid") or raw_report.get("report_id")
    submitter = raw_report.get("submitter") or {}
    wecom_userid = (
        submitter.get("userid")
        or raw_report.get("creator_userid")
        or raw_report.get("reporter_userid")
    )
    report_time = raw_report.get("report_time")
    if not report_no or not wecom_userid or not report_time:
        return None

    report_date = datetime.fromtimestamp(float(report_time), _TZ_BEIJING).date()
    work_summary, watermark_image_url = _extract_report_text_and_image(raw_report)
    template_id = raw_report.get("template_id") or ""
    template_name = raw_report.get("template_name") or ""

    is_service_report = (
        template_id == settings.WECOM_JOURNAL_TEMPLATES["field_service_report"]
        or "现场技术支持工作报告" in template_name
    )
    is_customer_signed = False
    signature_image_url: str | None = None

    contents = (raw_report.get("apply_data") or {}).get("contents") or []
    for ctrl in contents:
        title_text = "".join(
            (t.get("text") or "") for t in (ctrl.get("title") or []) if isinstance(t, dict)
        )
        if "签名" in title_text or "签字" in title_text:
            val = ctrl.get("value") or {}
            files = val.get("files") or []
            if files:
                is_customer_signed = True
                first_file = files[0] if isinstance(files[0], dict) else {}
                signature_image_url = (
                    first_file.get("file_url")
                    or first_file.get("url")
                    or first_file.get("file_id")
                )
            elif (val.get("text") or "").strip():
                is_customer_signed = True

    return {
        "report_no": report_no,
        "wecom_userid": wecom_userid,
        "report_date": report_date,
        "work_summary": work_summary,
        "watermark_image_url": watermark_image_url,
        "template_id": template_id,
        "is_service_report": is_service_report,
        "is_customer_signed": is_customer_signed,
        "signature_image_url": signature_image_url,
        "raw_payload": raw_report,
    }


def sync_real_daily_reports(cursor, start_ts: int, end_ts: int) -> int:
    """拉取企微真实汇报（含现场日报与带签名的《现场技术支持工作报告》）并幂等落库。

    - 所有有效汇报写入 field_work_reports（F4）；
    - 《现场技术支持工作报告》同步提取客户手写签名写入 service_reports（打通 F5 真实数据源）。
    """
    raw_reports = wecom_client.fetch_daily_reports(start_ts, end_ts)
    inserted = 0
    for r in raw_reports:
        parsed = parse_journal_detail(r)
        if not parsed:
            logger.warning("跳过字段不全的日报记录: %s", r)
            continue

        cursor.execute(
            """
            INSERT INTO field_work_reports
                (report_no, wecom_userid, report_date, work_summary,
                 watermark_image_url, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (report_no) DO NOTHING;
            """,
            (
                parsed["report_no"],
                parsed["wecom_userid"],
                parsed["report_date"],
                parsed["work_summary"],
                parsed["watermark_image_url"],
                psycopg2.extras.Json(parsed["raw_payload"]),
            ),
        )
        if cursor.rowcount:
            inserted += 1

        if parsed["is_service_report"]:
            cursor.execute(
                """
                INSERT INTO service_reports
                    (report_no, wecom_userid, report_date,
                     is_customer_signed, signature_image_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (report_no) DO UPDATE
                SET is_customer_signed = EXCLUDED.is_customer_signed,
                    signature_image_url = EXCLUDED.signature_image_url;
                """,
                (
                    parsed["report_no"],
                    parsed["wecom_userid"],
                    parsed["report_date"],
                    parsed["is_customer_signed"],
                    parsed["signature_image_url"],
                ),
            )

    return inserted


def run_daily_audit(target_date: date) -> dict:
    """Execute Daily Audit for target_date (reconciling T-1 punches, leaves, and approvals)."""
    logger.info("Running Daily Audit for date: %s", target_date)

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Sync employee roster every run (not just on first cold-start with an
        # empty table) — otherwise corrections made to data/employee_roster.json
        # (e.g. a wrong email domain) or WeCom org-chart changes (new hire /
        # leaver / role change) never propagate once the employees table has
        # any row in it. This is cheap (one extra WeCom API call/day).
        sync_employee_roster()

        # 2. Get active employees
        cursor.execute(
            "SELECT wecom_userid, name, email, role, company FROM employees WHERE status = 'active';"
        )
        employees = cursor.fetchall()

        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())

        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        # 3. Pull punch logs from WeCom and sync to DB
        employee_ids = [
            emp["wecom_userid"]
            for emp in employees
            if not _is_excluded(emp["name"], emp["wecom_userid"])
        ]
        if not employee_ids:
            return {"total_expected": 0, "total_normal": 0, "total_anomalies": 0}

        # Sync punches (真实打卡) + 5 类假勤审批批量兜底拉取 + 官方两步汇报（含签字服务报告）
        sync_real_punches(cursor, employee_ids, start_ts, end_ts)
        # 审批单可能跨多日（如多日出差/年假），向前多拉 7 天确保覆盖当日生效的历史审批
        approval_lookback_ts = int((start_dt - timedelta(days=7)).timestamp())
        sync_real_approvals(cursor, approval_lookback_ts, end_ts)
        sync_real_daily_reports(cursor, start_ts, end_ts)

        conn.commit()

        # 4. Perform daily cross-check for each employee
        is_workday = is_workday_db(target_date, cursor)

        total_expected = 0
        total_normal = 0
        total_on_leave = 0
        total_anomalies = 0

        anomaly_list: list[str] = []

        for emp in employees:
            userid = emp["wecom_userid"]
            name = emp["name"]
            email = emp["email"]

            if _is_excluded(name, userid):
                continue

            # Check if there is a 'business_trip' or 'leave' approval covering this date
            cursor.execute(
                """
                SELECT * FROM approvals
                WHERE wecom_userid = %s AND status = 'approved'
                  AND start_time <= %s AND end_time >= %s;
                """,
                (userid, end_dt, start_dt),
            )
            active_approvals = cursor.fetchall()

            # Fetch punches from DB
            cursor.execute(
                """
                SELECT * FROM attendance_logs
                WHERE wecom_userid = %s AND clock_time >= %s AND clock_time <= %s
                ORDER BY clock_time ASC;
                """,
                (userid, start_dt, end_dt),
            )
            punches = cursor.fetchall()

            offsets = compute_approved_offset_hours(active_approvals, start_dt, end_dt)
            has_trip = offsets["has_trip"]
            has_full_day_leave = offsets["has_full_day_leave"]
            has_full_day_outing = offsets["has_full_day_outing"]
            partial_leave_hours = offsets["partial_offset_hours"]

            status = "normal"
            is_anomaly = False
            anomaly_reason = ""
            security_status = "正常"

            first_in = None
            last_out = None
            if punches:
                first_in = punches[0]["clock_time"]
                last_out = punches[-1]["clock_time"] if len(punches) > 1 else None

            # 3D Anti-Cheating Check (F2):
            # Check 1: WeCom Exception Codes (E11)
            wecom_exceptions = [p["exception_type"] for p in punches if p["exception_type"]]
            if wecom_exceptions:
                is_anomaly = True
                status = "device_anomaly"
                anomaly_reason = (
                    "打卡物理定位偏离（外勤打卡 / 非公司指定设备，"
                    "校验结果: %s）" % ", ".join(wecom_exceptions)
                )
                security_status = "设备环境待确认"

            # Check 2: Speed Feasibility Check — 瞬移超速 >350km/h (E12)
            if len(punches) >= 2:
                for idx in range(len(punches) - 1):
                    p1 = punches[idx]
                    p2 = punches[idx + 1]
                    if p1["latitude"] and p1["longitude"] and p2["latitude"] and p2["longitude"]:
                        dist = calculate_haversine_distance(
                            float(p1["latitude"]),
                            float(p1["longitude"]),
                            float(p2["latitude"]),
                            float(p2["longitude"]),
                        )
                        time_delta_hours = (
                            (p2["clock_time"] - p1["clock_time"]).total_seconds() / 3600.0
                        )
                        if time_delta_hours > 0:
                            speed = dist / time_delta_hours
                            if speed > 350.0:
                                is_anomaly = True
                                status = "location_anomaly"
                                anomaly_reason = (
                                    "打卡位置异常（检测到极短时间内远距离多地打卡，"
                                    "时速: %.1f km/h）" % speed
                                )
                                security_status = "打卡位置待核实"

            # Reconcile punches against workday expectations（PRD v0.5 §4.2-1 动态工时）
            if has_full_day_leave:
                status = "leave" if not is_anomaly else status
                total_on_leave += 1
            elif has_trip:
                status = "business_trip" if not is_anomaly else status
                total_on_leave += 1
            elif has_full_day_outing:
                status = "outing" if not is_anomaly else status
                total_normal += 1
            elif is_workday:
                total_expected += 1
                if not is_anomaly:
                    if not punches:
                        is_anomaly = True
                        status = "absent"
                        anomaly_reason = "正常工作日全天无打卡记录（且未关联请假或出差审批）"
                    elif len(punches) < 2:
                        # 单侧缺卡跨度不可算：标待核推人工（旧「自动折 0.5 天」口径作废）
                        is_anomaly = True
                        status = "pending_single_punch"
                        anomaly_reason = (
                            "工作日仅一次打卡，在岗跨度无法核算，须人工核对"
                            "（外勤/故障核销或按缺勤处理）"
                        )
                    else:
                        verdict = evaluate_daily_work_hours(
                            workday=target_date,
                            first_punch=first_in,
                            last_punch=punches[-1]["clock_time"],
                            approved_partial_leave_hours=partial_leave_hours,
                        )
                        if verdict.status == "normal":
                            status = "normal"
                            total_normal += 1
                        else:
                            is_anomaly = True
                            status = verdict.status
                            anomaly_reason = (
                                "工时缺额：在岗跨度 %.2fh（截断后 %s–%s），"
                                "应出勤 %.2fh%s，缺 %.2fh；"
                                "请当天或当月内在企微申请调休/年假冲抵"
                                "（被动抵扣每月上限 %.0f 小时，超出按无酬缺勤核算）"
                                % (
                                    verdict.presence_span_hours,
                                    verdict.effective_start.strftime("%H:%M"),
                                    verdict.effective_end.strftime("%H:%M"),
                                    verdict.required_presence_hours,
                                    "（已扣当日批假 %.1fh）" % partial_leave_hours
                                    if partial_leave_hours
                                    else "",
                                    verdict.shortfall_hours,
                                    settings.PASSIVE_OFFSET_MONTHLY_CAP_HOURS,
                                )
                            )
            else:
                status = "rest"

            if is_anomaly:
                total_anomalies += 1
                cursor.execute(
                    """
                    INSERT INTO daily_attendance
                        (wecom_userid, attendance_date, first_clock_in,
                         last_clock_out, status, is_anomaly, anomaly_reason)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (wecom_userid, attendance_date) DO UPDATE
                    SET first_clock_in = EXCLUDED.first_clock_in,
                        last_clock_out = EXCLUDED.last_clock_out,
                        status = EXCLUDED.status,
                        is_anomaly = TRUE,
                        anomaly_reason = EXCLUDED.anomaly_reason;
                    """,
                    (userid, target_date, first_in, last_out, status, anomaly_reason),
                )

                # Send individual anomaly email
                if status == "absent":
                    type_desc = "未检测到打卡 / 出勤不足 4 小时"
                elif status == "pending_single_punch":
                    type_desc = "单次打卡待核"
                elif status == "pending_reconciliation":
                    type_desc = "工时缺额待冲抵"
                else:
                    type_desc = "轨迹待复核"

                email_body = mail_sender.render_individual_anomaly_email(
                    employee_name=name,
                    anomaly_date=target_date.strftime("%Y-%m-%d"),
                    anomaly_type_desc=type_desc,
                    anomaly_reason_detail=anomaly_reason,
                    first_clock_in=first_in.strftime("%H:%M:%S") if first_in else "无",
                    last_clock_out=last_out.strftime("%H:%M:%S") if last_out else "无",
                    security_status=security_status,
                )

                cc_list = settings.ADMIN_EMAILS
                mail_sender.send_html_email(
                    subject="考勤对账确认 - %s" % name,
                    html_content=email_body,
                    to_email=email or "test_user@pomeroy.com.cn",
                    cc_list=cc_list,
                )

                # Build anomaly summary row for daily report
                deadline = (date.today() + timedelta(days=2)).strftime("%m-%d")
                anomaly_list.append(
                    '<tr style="border-bottom: 1px dashed #e2e8f0;">'
                    '<td style="padding: 6px; font-weight: bold; color: #111111;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%s</td>'
                    '<td style="padding: 6px; color: #b91c1c;">%s (%s...)</td>'
                    '<td style="padding: 6px; color: #b91c1c;">%s</td>'
                    '<td style="padding: 6px; color: #555555;">%s 18:00</td>'
                    "</tr>"
                    % (name, emp["role"], status, anomaly_reason[:15], security_status, deadline)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO daily_attendance
                        (wecom_userid, attendance_date, first_clock_in,
                         last_clock_out, status, is_anomaly, anomaly_reason)
                    VALUES (%s, %s, %s, %s, %s, FALSE, NULL)
                    ON CONFLICT (wecom_userid, attendance_date) DO UPDATE
                    SET first_clock_in = EXCLUDED.first_clock_in,
                        last_clock_out = EXCLUDED.last_clock_out,
                        status = EXCLUDED.status,
                        is_anomaly = FALSE,
                        anomaly_reason = NULL;
                    """,
                    (userid, target_date, first_in, last_out, status),
                )

        # Build & send Daily Company Report
        anomaly_rows_html = "".join(anomaly_list) if anomaly_list else (
            '<tr><td colspan="5" style="padding: 10px; text-align: center; color: #666666;">'
            "昨日公司全员考勤正常，无任何异常缺卡！</td></tr>"
        )

        cursor.execute(
            """
            SELECT e.name, a.attendance_date, a.status, a.anomaly_reason
            FROM daily_attendance a
            JOIN employees e ON a.wecom_userid = e.wecom_userid
            WHERE a.attendance_date = %s AND a.is_anomaly = TRUE;
            """,
            (target_date,),
        )
        recent_anomalies = cursor.fetchall()

        deduction_lines = []
        for ra in recent_anomalies:
            deduction_lines.append(
                "• %s：因 昨日%s 缺卡，系统已登记 T+2 限期补正，逾期将记录事假扣薪或旷工。"
                % (ra["name"], ra["status"])
            )
        deduction_history_html = (
            "<br>".join(deduction_lines)
            if deduction_lines
            else "暂无历史对账扣发流水变动。"
        )

        daily_report_html = mail_sender.render_daily_summary_email(
            audit_date=target_date.strftime("%Y-%m-%d"),
            total_expected=total_expected,
            total_normal=total_normal,
            total_on_leave=total_on_leave,
            total_anomalies=total_anomalies,
            anomaly_rows_html=anomaly_rows_html,
            deduction_history_html=deduction_history_html,
        )

        mail_sender.send_html_email(
            subject="公司每日考勤汇总日报 - %s" % target_date.strftime("%Y-%m-%d"),
            html_content=daily_report_html,
            to_email=settings.ADMIN_EMAILS[0],
            cc_list=settings.ADMIN_EMAILS[1:],
        )

        conn.commit()
        cursor.close()
        return {
            "total_expected": total_expected,
            "total_normal": total_normal,
            "total_anomalies": total_anomalies,
        }
    except Exception as e:
        conn.rollback()
        logger.error("Error in daily audit: %s", e)
        raise
    finally:
        conn.close()
