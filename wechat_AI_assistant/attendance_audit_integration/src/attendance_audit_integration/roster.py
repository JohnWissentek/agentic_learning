"""本地员工花名册：从 JSON 加载姓名/邮箱等（不再使用 xlsx）。"""
from __future__ import annotations

import json
from pathlib import Path

from attendance_audit_integration.config import ROOT_DIR, get
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ROSTER_PATH = ROOT_DIR / "data" / "employee_roster.json"


def get_roster_path() -> Path:
    configured = get("EMPLOYEE_ROSTER_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_ROSTER_PATH


def load_employee_roster(path: Path | None = None) -> list[dict]:
    """加载花名册 JSON，返回 employees 列表。

    期望结构::
        {"version": 1, "employees": [{"name": "...", "email": "...", ...}]}
    """
    roster_path = path or get_roster_path()
    if not roster_path.is_file():
        logger.error("花名册文件不存在: %s", roster_path)
        raise FileNotFoundError(f"employee roster not found: {roster_path}")

    raw = json.loads(roster_path.read_text(encoding="utf-8"))
    employees = raw.get("employees")
    if not isinstance(employees, list):
        raise ValueError(f"invalid roster format in {roster_path}: missing employees list")

    cleaned: list[dict] = []
    for row in employees:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        cleaned.append(
            {
                "name": name,
                "email": str(row.get("email") or "").strip(),
                "wecom_userid": str(row.get("wecom_userid") or "").strip(),
                "role": str(row.get("role") or "").strip(),
                "company": str(row.get("company") or "").strip(),
                "hire_date": row.get("hire_date"),
                "status": str(row.get("status") or "active").strip() or "active",
            }
        )

    logger.info("Loaded %d employees from roster %s", len(cleaned), roster_path)
    return cleaned


# 外勤 GPS 围栏：超过此距离（米）打卡无效（PRD F13 / E14）
OUTDOOR_GPS_MAX_RADIUS_METERS = 200.0


def evaluate_outdoor_gps_distance(distance_meters: float) -> str:
    """根据与审批目的地距离判定外勤打卡结果。

    返回:
        - ``valid``：≤ 200m
        - ``invalid``：> 200m
    """
    if distance_meters <= OUTDOOR_GPS_MAX_RADIUS_METERS:
        return "valid"
    return "invalid"
