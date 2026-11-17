"""Group 2 Scheduling & Workload Tools: deterministic dates and CEO daily capacity check."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wechat_assistant.storage.db import Database


def calc_business_date(base_date_str: str, offset_business_days: int) -> str:
    """Deterministically add business days (Mon-Fri) to an ISO date string."""
    cur = date.fromisoformat(base_date_str[:10])
    step = 1 if offset_business_days >= 0 else -1
    remaining = abs(offset_business_days)
    while remaining > 0:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            remaining -= 1
    return cur.isoformat()


def check_workload_and_schedule(
    db: Database,
    *,
    start_date: str | None = None,
    needed_hours: float = 1.0,
    days: int = 14,
    daily_capacity: float = 6.0,
) -> dict[str, Any]:
    """Return booked net hours per day and suggest the earliest non-overloaded date."""
    report = db.get_daily_workload(start_date=start_date, days=days, daily_capacity=daily_capacity)
    recommended_date = None
    for d_str, info in report["days"].items():
        if info["booked_hours"] + needed_hours <= daily_capacity + 1e-6:
            recommended_date = d_str
            break
    return {
        **report,
        "needed_hours": needed_hours,
        "recommended_start_date": recommended_date or next(iter(report["days"])),
    }
