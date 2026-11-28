"""员工花名册同步服务（PRD F8）。

合并企微通讯录与本地 JSON 花名册，UPSERT 到 employees 表。
"""
from __future__ import annotations

from datetime import date, timedelta

from attendance_audit_integration.config import settings
from attendance_audit_integration.db import get_db_connection
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.roster import load_employee_roster
from attendance_audit_integration.wecom_api import wecom_client

logger = get_logger(__name__)


def sync_employee_roster() -> list[str]:
    """Sync employees: WeCom members + local JSON roster emails (F8, no xlsx).

    Returns:
        List of synced wecom_userid strings.
    """
    local_by_name: dict[str, dict] = {}
    try:
        for row in load_employee_roster():
            local_by_name[row["name"]] = row
    except FileNotFoundError:
        logger.warning("Local JSON roster missing; sync will rely on WeCom profile fields only")

    users = wecom_client.fetch_users()
    if not users:
        logger.warning("No users fetched from WeCom.")
        return []

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        synced_userids: list[str] = []
        for u in users:
            wecom_userid = u["userid"]
            name = u["name"]
            local = local_by_name.get(name, {})
            email = local.get("email") or u.get("email") or ""
            role = local.get("role") or u.get("position") or "Staff"
            company = local.get("company") or (
                settings.DEFAULT_COMPANY_A
                if u.get("department", [1])[0] != 2
                else settings.DEFAULT_COMPANY_B
            )
            hire_raw = local.get("hire_date")
            if hire_raw:
                hire_date = date.fromisoformat(str(hire_raw)[:10])
            else:
                hire_date = date.today() - timedelta(days=365)

            # WeCom's userid for an existing employee is not guaranteed stable
            # (observed in production: case changes, or an org-merge suffix
            # like "XuHongWei@CorpAlias" appearing on an already-known person).
            # Match the existing row by name FIRST so a userid rename updates
            # the same row instead of INSERT-ing a duplicate under the new id
            # (which happened on 2026-07-14 and caused duplicate audit emails).
            cursor.execute("SELECT wecom_userid FROM employees WHERE name = %s;", (name,))
            existing = cursor.fetchone()

            if existing and existing[0] != wecom_userid:
                cursor.execute(
                    """
                    UPDATE employees
                    SET wecom_userid = %s, email = %s, role = %s, company = %s
                    WHERE name = %s
                    RETURNING wecom_userid;
                    """,
                    (wecom_userid, email, role, company, name),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO employees (wecom_userid, name, email, company, role, hire_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    ON CONFLICT (wecom_userid) DO UPDATE
                    SET name = EXCLUDED.name, email = EXCLUDED.email,
                        role = EXCLUDED.role, company = EXCLUDED.company
                    RETURNING wecom_userid;
                    """,
                    (wecom_userid, name, email, company, role, hire_date),
                )

            row = cursor.fetchone()
            if row:
                synced_userids.append(row[0])

        conn.commit()
        cursor.close()
        logger.info("Synced %d employees from WeCom + JSON roster", len(synced_userids))
        return synced_userids
    except Exception as e:
        conn.rollback()
        logger.error("Error syncing employee roster: %s", e)
        raise
    finally:
        conn.close()
