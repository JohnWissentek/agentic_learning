"""假期余额与逾期堆积审计服务（v0.7 一阶段，只读同步与告警，严禁静默扣减）。

能力：
1. 调用企微只读接口拉取企业假期配置（getcorpconf）与员工个人余额（getuservacationquota）；
2. 按现网真实 vacation_id（1=年假、4=调休假）幂等同步至本地 vacation_balances；
3. 检出 4 类管理风险：
   - 调休假严重堆积（>=32h，如王旭 219.5h）→ 仅定向推送 PM（孔紫初、王楠）+ F11 抄送，禁发本人；
   - 年假余额偏高（>40h，排除免考核白名单）→ 推 HR 核对跨年与工龄；
   - 离职人员残留余额（status != 'active' 且余额 > 0）→ 推 HR 清理；
   - 病假限额但全员 0 余额风险 + 永久有效无清零规则提醒 → 推 HR 确认。
"""
from __future__ import annotations

from psycopg2.extras import RealDictCursor

from attendance_audit_integration import mail_sender
from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.wecom_api import wecom_client

logger = get_logger(__name__)


def _is_excluded(name: str, userid: str) -> bool:
    return name in settings.EXCLUDED_NAMES or userid in settings.EXCLUDED_USERIDS


def extract_hours_by_vacation_id(quota_lists: list[dict]) -> dict[int, dict[str, float]]:
    """将企微假期余额原始列表（单位：秒）换算为小时，按 vacation_id 索引。"""
    result: dict[int, dict[str, float]] = {}
    for item in quota_lists or []:
        vid = item.get("id")
        if vid is None:
            continue
        vid_int = int(vid)
        raw_remaining = item.get("leftduration")
        if raw_remaining is None:
            raw_remaining = item.get("balance", 0)
        remaining_hours = round(float(raw_remaining or 0) / 3600.0, 2)

        raw_used = item.get("used", 0)
        used_hours = round(float(raw_used or 0) / 3600.0, 2)

        raw_quota = item.get("quota")
        if raw_quota is not None:
            granted_hours = round(float(raw_quota) / 3600.0, 2)
        else:
            granted_hours = round(remaining_hours + used_hours, 2)

        result[vid_int] = {
            "remaining_hours": remaining_hours,
            "granted_hours": granted_hours,
            "used_hours": used_hours,
        }
    return result


def analyze_vacation_anomalies(
    employee_quotas: list[dict],
    corp_conf: list[dict] | None = None,
) -> dict:
    """纯函数：根据员工假期余额快照与企业假期规则，输出结构化风险清单。"""
    comp_backlog: list[dict] = []
    annual_high: list[dict] = []
    leaver_residuals: list[dict] = []
    active_sick_hours: list[float] = []

    for emp in employee_quotas:
        userid = emp.get("wecom_userid", "")
        name = emp.get("name", userid)
        status = emp.get("status", "active")
        annual_h = float(emp.get("annual_hours", 0.0))
        comp_h = float(emp.get("comp_hours", 0.0))
        sick_h = float(emp.get("sick_hours", 0.0))

        if status != "active":
            if annual_h > 0 or comp_h > 0 or sick_h > 0:
                leaver_residuals.append(
                    {
                        "wecom_userid": userid,
                        "name": name,
                        "annual_hours": annual_h,
                        "comp_hours": comp_h,
                        "sick_hours": sick_h,
                    }
                )
            continue

        active_sick_hours.append(sick_h)
        if _is_excluded(name, userid):
            continue

        if comp_h >= settings.VACATION_COMP_BACKLOG_WARN_HOURS:
            comp_backlog.append(
                {
                    "wecom_userid": userid,
                    "name": name,
                    "comp_hours": comp_h,
                    "comp_days": round(comp_h / settings.FULL_DAY_HOURS, 2),
                }
            )
        if annual_h > settings.VACATION_ANNUAL_HIGH_WARN_HOURS:
            annual_high.append(
                {
                    "wecom_userid": userid,
                    "name": name,
                    "annual_hours": annual_h,
                    "annual_days": round(annual_h / settings.FULL_DAY_HOURS, 2),
                }
            )

    comp_backlog.sort(key=lambda x: x["comp_hours"], reverse=True)
    annual_high.sort(key=lambda x: x["annual_hours"], reverse=True)

    permanent_expiry_types: list[str] = []
    sick_is_limited = False
    for conf in corp_conf or []:
        expire_rule = conf.get("expire_rule") or {}
        if expire_rule.get("type") == 4:
            cname = conf.get("name")
            if cname:
                permanent_expiry_types.append(cname)
        if int(conf.get("id", -1)) == settings.WECOM_VACATION_ID_SICK:
            quota_attr = conf.get("quota_attr") or {}
            if quota_attr.get("type") in (1, 2):
                sick_is_limited = True

    zero_sick_limit_risk = (
        sick_is_limited
        and bool(active_sick_hours)
        and all(h == 0.0 for h in active_sick_hours)
    )

    return {
        "comp_backlog": comp_backlog,
        "annual_high": annual_high,
        "leaver_residuals": leaver_residuals,
        "zero_sick_limit_risk": zero_sick_limit_risk,
        "permanent_expiry_types": permanent_expiry_types,
    }


def _render_comp_backlog_html(comp_backlog: list[dict]) -> str:
    rows = "".join(
        "<tr><td style='padding:6px;border-bottom:1px solid #e2e8f0;'>%s</td>"
        "<td style='padding:6px;border-bottom:1px solid #e2e8f0;color:#b91c1c;font-weight:bold;'>"
        "%.1f 小时（≈%.1f 天）</td></tr>"
        % (item["name"], item["comp_hours"], item["comp_days"])
        for item in comp_backlog
    )
    return (
        "<html><body><h3>⚠️ 员工调休假余额堆积提醒（仅项目管理统筹，未通知员工本人）</h3>"
        "<p>以下在职员工企微调休假余额已达到或超过 %.0f 小时预警线，请统筹排期消化：</p>"
        "<table style='border-collapse:collapse;width:100%%;'>"
        "<thead><tr><th style='text-align:left;padding:6px;'>姓名</th>"
        "<th style='text-align:left;padding:6px;'>当前调休余额</th></tr></thead>"
        "<tbody>%s</tbody></table>"
        "<p style='color:#666;font-size:12px;'>注：本系统只做余额同步与预警，绝不自动清零或扣减假期。</p>"
        "</body></html>"
        % (settings.VACATION_COMP_BACKLOG_WARN_HOURS, rows)
    )


def _render_hr_vacation_audit_html(anomalies: dict) -> str:
    sections: list[str] = ["<html><body><h3>📋 企业微信假期台账与逾期风险审计报告</h3>"]
    if anomalies["leaver_residuals"]:
        items = "".join(
            "<li>%s：年假 %.1fh / 调休 %.1fh / 病假 %.1fh</li>"
            % (x["name"], x["annual_hours"], x["comp_hours"], x["sick_hours"])
            for x in anomalies["leaver_residuals"]
        )
        sections.append("<h4>1. 离职人员残留余额（建议清理）</h4><ul>%s</ul>" % items)
    if anomalies["annual_high"]:
        items = "".join(
            "<li>%s：年假 %.1fh（≈%.1f 天）</li>"
            % (x["name"], x["annual_hours"], x["annual_days"])
            for x in anomalies["annual_high"]
        )
        sections.append("<h4>2. 年假余额偏高人员（建议核对工龄与跨年结转）</h4><ul>%s</ul>" % items)
    if anomalies["zero_sick_limit_risk"]:
        sections.append(
            "<h4>3. 病假限额风险</h4><p>企微病假规则为限额模式，但当前在职全员余额均为 0，请假可能被拦截。</p>"
        )
    if anomalies["permanent_expiry_types"]:
        sections.append(
            "<h4>4. 无自动清零/过期规则的假期</h4><p>%s（当前均为永久有效）</p>"
            % "、".join(anomalies["permanent_expiry_types"])
        )
    sections.append(
        "<p style='color:#666;font-size:12px;'>注：所有余额调整须经 HR/员工确认后手工或走审批执行。</p></body></html>"
    )
    return "".join(sections)


def run_vacation_balance_audit(*, send_email: bool = True) -> dict:
    """拉取企微真实假期配置与全员余额，幂等入库并输出堆积/离职/规则异常告警。"""
    logger.info("Running WeCom vacation balance & expiry audit (read-only)...")
    corp_conf = wecom_client.fetch_vacation_corp_conf()

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT wecom_userid, name, email, status FROM employees;")
        employees = cursor.fetchall()

        snapshots: list[dict] = []
        synced_employees = 0

        for emp in employees:
            uid = emp["wecom_userid"]
            raw_quota = wecom_client.fetch_user_vacation_quota(uid)
            by_id = extract_hours_by_vacation_id(raw_quota)

            annual = by_id.get(settings.WECOM_VACATION_ID_ANNUAL, {})
            comp = by_id.get(settings.WECOM_VACATION_ID_COMPENSATORY, {})
            sick = by_id.get(settings.WECOM_VACATION_ID_SICK, {})

            annual_h = annual.get("remaining_hours", 0.0)
            comp_h = comp.get("remaining_hours", 0.0)
            sick_h = sick.get("remaining_hours", 0.0)

            for leave_type, entry in (("annual", annual), ("compensatory", comp)):
                if not entry:
                    continue
                cursor.execute(
                    """
                    INSERT INTO vacation_balances
                        (wecom_userid, leave_type, total_granted, total_used)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (wecom_userid, leave_type) DO UPDATE
                    SET total_granted = EXCLUDED.total_granted,
                        total_used = EXCLUDED.total_used;
                    """,
                    (uid, leave_type, entry["granted_hours"], entry["used_hours"]),
                )

            snapshots.append(
                {
                    "wecom_userid": uid,
                    "name": emp["name"],
                    "status": emp["status"],
                    "annual_hours": annual_h,
                    "comp_hours": comp_h,
                    "sick_hours": sick_h,
                }
            )
            synced_employees += 1

        anomalies = analyze_vacation_anomalies(snapshots, corp_conf)

        if send_email:
            # F11 红线：调休堆积告警仅发 PM + F11_CC，严禁发/抄送被催员工本人
            if anomalies["comp_backlog"]:
                mail_sender.send_html_email(
                    subject="⚠️ 考勤调休余额堆积预警（%d 人超 %.0f 小时）"
                    % (len(anomalies["comp_backlog"]), settings.VACATION_COMP_BACKLOG_WARN_HOURS),
                    html_content=_render_comp_backlog_html(anomalies["comp_backlog"]),
                    to_email=settings.PM_EMAILS[0],
                    cc_list=settings.PM_EMAILS[1:] + settings.F11_CC_EMAILS,
                )

            if (
                anomalies["leaver_residuals"]
                or anomalies["annual_high"]
                or anomalies["zero_sick_limit_risk"]
            ):
                mail_sender.send_html_email(
                    subject="📋 企微假期台账与余额异常审计报告",
                    html_content=_render_hr_vacation_audit_html(anomalies),
                    to_email=settings.ADMIN_EMAILS[0],
                    cc_list=settings.ADMIN_EMAILS[1:],
                )

        cursor.execute(
            """
            INSERT INTO audit_logs (wecom_userid, action_type, description)
            VALUES (NULL, 'vacation_balance_audit', %s);
            """,
            (
                "Synced %d employees; comp_backlog=%d, annual_high=%d, leaver_residuals=%d"
                % (
                    synced_employees,
                    len(anomalies["comp_backlog"]),
                    len(anomalies["annual_high"]),
                    len(anomalies["leaver_residuals"]),
                ),
            ),
        )

        conn.commit()
        cursor.close()
        return {
            "synced_employees": synced_employees,
            "anomalies": anomalies,
        }
    except Exception as exc:
        conn.rollback()
        logger.error("Error in vacation balance audit: %s", exc)
        raise
    finally:
        conn.close()
