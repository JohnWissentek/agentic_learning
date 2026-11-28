"""金蝶差旅报销交叉审计服务（F15；PRD v0.5 §4.2-12；制度 4.2.3）。

一期只做差旅补助减半核对：
- 只读拉取金蝶差旅/费用报销单的补助明细日；
- 与企微出差打卡/日报核定的「单日现场技术工作时长」对表；
- 金额口径不符 → 输出「补助待核」差异行邮件给财务与 HR（E31）；
- 金蝶不可用 → 重试后降级跳过并告警，不阻塞考勤主流程（E32）；
- 判定不了的场景（客观等待待命等）只标待核，不判错（E33）。

严禁：回写金蝶、自动扣发、修改单据状态。
"""
from __future__ import annotations

import time
from datetime import date, datetime

from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.kingdee_client import (
    KingdeeAuthError,
    KingdeeClient,
    KingdeeQueryError,
)
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

_LOGIN_MAX_ATTEMPTS = 3  # 首次 + 重试 2 次
_RETRY_BACKOFF_SECONDS = 5.0

# 补助明细查询字段（须按企业真实账套元数据核对，见伪代码注意事项）：
# 单据编号 / 报销人姓名 / 费用日期 / 费用项目名称 / 报销金额
_EXPENSE_FIELD_KEYS = (
    "FBillNo,FProposerID.FName,FEntity_FDate,FEntity_FExpID.FName,FEntity_FAmount"
)


def decide_subsidy_entitlement(
    onsite_hours: float,
    transit_hours: float,
    has_leave_offset_that_day: bool,
) -> str:
    """制度 4.2.3 应发口径判定（纯函数）：返回 'full' 或 'half'。

    - 现场技术工作 ≥4h → 全额；
    - 现场 <4h 但「现场 + 当日在途」合计 ≥4h 且当日未办理请假/年假折抵
      → 全额（合并在岗判定）；
    - 其余 → 减半。
    """
    threshold = settings.TRIP_ONSITE_HALF_SUBSIDY_HOURS
    if onsite_hours >= threshold:
        return "full"
    if (onsite_hours + transit_hours) >= threshold and not has_leave_offset_that_day:
        return "full"
    return "half"


def _estimate_onsite_hours(cursor, wecom_userid: str, work_date: date) -> float | None:
    """由企微外勤/出差打卡首末点估算单日现场时长；无记录返回 None（待核）。"""
    cursor.execute(
        """
        SELECT MIN(clock_time) AS first_ts, MAX(clock_time) AS last_ts, COUNT(*) AS cnt
        FROM attendance_logs
        WHERE wecom_userid = %s AND clock_type = 'outdoor'
          AND clock_time::date = %s;
        """,
        (wecom_userid, work_date),
    )
    row = cursor.fetchone()
    if not row or not row["cnt"] or row["cnt"] < 2:
        return None
    span_seconds = (row["last_ts"] - row["first_ts"]).total_seconds()
    return max(span_seconds / 3600.0, 0.0)


def run_expense_cross_audit(cycle_start: date, cycle_end: date) -> dict:
    """对薪资周期内的金蝶差旅补助明细做减半规则核对。

    返回 {"skipped": bool, "bills": int, "checked_days": int, "diffs": int}。
    任何金蝶侧失败都降级为 skipped=True，绝不向上抛出阻塞月审（E32）。
    """
    if not KingdeeClient.is_configured():
        logger.warning("F15 未配置金蝶凭证（KINGDEE_*），本轮交叉审计跳过")
        return {"skipped": True, "bills": 0, "checked_days": 0, "diffs": 0}

    client = KingdeeClient()
    try:
        for attempt in range(1, _LOGIN_MAX_ATTEMPTS + 1):
            try:
                client.login()
                break
            except (KingdeeAuthError, Exception) as login_error:  # noqa: BLE001 —
                # 金蝶侧任何失败（网络/认证/网关）统一走降级路径，E32
                if attempt == _LOGIN_MAX_ATTEMPTS:
                    logger.error("金蝶登录连续 %d 次失败: %s", attempt, login_error)
                    _alert_admin_kingdee_down(str(login_error))
                    return {"skipped": True, "bills": 0, "checked_days": 0, "diffs": 0}
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt)

        filter_string = (
            "FEntity_FDate >= '%s' AND FEntity_FDate <= '%s'"
            % (cycle_start.isoformat(), cycle_end.isoformat())
        )
        try:
            bill_rows = client.query_expense_bills(filter_string, _EXPENSE_FIELD_KEYS)
        except (KingdeeQueryError, Exception) as query_error:  # noqa: BLE001
            logger.error("金蝶报销单查询失败: %s", query_error)
            _alert_admin_kingdee_down(str(query_error))
            return {"skipped": True, "bills": 0, "checked_days": 0, "diffs": 0}
    finally:
        client.close()

    conn = get_db_connection()
    diffs: list[str] = []
    checked_days = 0
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        for row in bill_rows:
            try:
                bill_no, employee_name, expense_date_raw, expense_item, amount = row[:5]
            except (ValueError, TypeError):
                diffs.append("单据行解析失败（字段结构与预期不符），原始行已记日志待核")
                logger.warning("金蝶单据行解析失败: %r", row)
                continue
            if "补助" not in str(expense_item) and "补贴" not in str(expense_item):
                continue  # 纯交通/住宿费报销行不参与补助减半核对

            expense_date = _parse_kingdee_date(expense_date_raw)
            if expense_date is None:
                diffs.append("%s %s：费用日期解析失败，标待核" % (bill_no, employee_name))
                continue

            cursor.execute(
                "SELECT wecom_userid FROM employees WHERE name = %s;", (employee_name,)
            )
            emp_row = cursor.fetchone()
            if not emp_row:
                diffs.append(
                    "%s %s：花名册无法匹配报销人，标待核（E21 口径）"
                    % (bill_no, employee_name)
                )
                continue

            checked_days += 1
            onsite_hours = _estimate_onsite_hours(
                cursor, emp_row["wecom_userid"], expense_date
            )
            if onsite_hours is None:
                # 无外勤打卡记录：可能是客观等待待命（主管书面确认引擎读不到），
                # 只标待核、不判错（E33）
                diffs.append(
                    "%s %s %s：当日无外勤打卡里程碑，现场时长不可核，标待核"
                    % (bill_no, employee_name, expense_date)
                )
                continue

            # 一期在途时长票据口径不可得，取 0 并在差异行注明（PRD §1.1 暂缓项）
            entitlement = decide_subsidy_entitlement(
                onsite_hours=onsite_hours,
                transit_hours=0.0,
                has_leave_offset_that_day=False,
            )
            if entitlement == "half":
                diffs.append(
                    "%s %s %s：企微核定现场 %.1fh（<%.0fh），按制度 4.2.3 该日补助应减半，"
                    "金蝶实发 %s 元，请财务复核（在途时长未计入，若有客票/待命确认请人工修正）"
                    % (
                        bill_no,
                        employee_name,
                        expense_date,
                        onsite_hours,
                        settings.TRIP_ONSITE_HALF_SUBSIDY_HOURS,
                        amount,
                    )
                )

        if diffs:
            _send_diff_report(cycle_start, cycle_end, diffs)
            cursor.execute(
                """
                INSERT INTO audit_logs (action_type, description)
                VALUES ('expense_cross_audit', %s);
                """,
                ("周期 %s~%s 差旅补助待核 %d 条" % (cycle_start, cycle_end, len(diffs)),),
            )
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise  # 本地库写入失败属基础设施故障，须让月审感知
    finally:
        conn.close()

    logger.info(
        "F15 交叉审计完成：单据行 %d，核对补助日 %d，待核差异 %d",
        len(bill_rows), checked_days, len(diffs),
    )
    return {
        "skipped": False,
        "bills": len(bill_rows),
        "checked_days": checked_days,
        "diffs": len(diffs),
    }


def _parse_kingdee_date(raw_value) -> date | None:
    if isinstance(raw_value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw_value[:19], fmt).date()
            except ValueError:
                continue
    return None


def _alert_admin_kingdee_down(error_detail: str) -> None:
    """金蝶不可用告警（降级路径的一部分；邮件失败也不上抛）。"""
    try:
        mail_sender.send_html_email(
            subject="【告警】F15 金蝶交叉审计本轮跳过",
            html_content=(
                "<p>金蝶云星空接口连续失败，本轮差旅补助交叉审计已降级跳过，"
                "考勤主流程不受影响。</p><p>错误详情：%s</p>" % error_detail
            ),
            to_email=settings.ADMIN_EMAILS[0],
            cc_list=settings.ADMIN_EMAILS[1:],
        )
    except Exception as mail_error:  # noqa: BLE001 — 告警邮件失败只记日志
        logger.error("金蝶降级告警邮件发送失败: %s", mail_error)


def _send_diff_report(cycle_start: date, cycle_end: date, diffs: list[str]) -> None:
    rows_html = "".join(
        '<li style="margin-bottom:6px;color:#991b1b;">%s</li>' % line for line in diffs
    )
    mail_sender.send_html_email(
        subject="差旅补助交叉审计待核清单 %s~%s（%d 条）"
        % (cycle_start, cycle_end, len(diffs)),
        html_content=(
            "<p>以下补助明细与企微考勤核定的现场时长口径不符或不可核，"
            "请财务在金蝶复核阶段人工确认（制度 4.2.3：现场不足 4 小时补助减半；"
            "现场+在途合计满 4 小时且未折抵假的全额）。系统只读金蝶，"
            "不回写、不自动扣发。</p><ul>%s</ul>" % rows_html
        ),
        to_email=settings.ADMIN_EMAILS[0],
        cc_list=settings.ADMIN_EMAILS[1:],
    )
