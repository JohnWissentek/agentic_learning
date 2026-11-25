"""Group 2 Scheduling Tools: deterministic business dates and daily schedule-density check."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wechat_assistant.storage.db import Database


MAX_BUSINESS_DAY_OFFSET = 3650


def calc_business_date(base_date_str: str, offset_business_days: int) -> str:
    """Deterministically add business days (Mon-Fri) to an ISO date string."""
    offset = int(offset_business_days)
    if abs(offset) > MAX_BUSINESS_DAY_OFFSET:
        raise ValueError(
            f"offset_business_days={offset} exceeds safety limit (+/-{MAX_BUSINESS_DAY_OFFSET})"
        )
    cur = date.fromisoformat(base_date_str[:10])
    step = 1 if offset >= 0 else -1
    remaining = abs(offset)
    while remaining > 0:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            remaining -= 1
    return cur.isoformat()


DEFAULT_MAX_ITEMS_PER_DAY = 5


def check_workload_and_schedule(
    db: Database,
    *,
    start_date: str | None = None,
    days: int = 14,
    max_items_per_day: int = DEFAULT_MAX_ITEMS_PER_DAY,
    **_legacy_ignored: Any,
) -> dict[str, Any]:
    """Return scheduled item counts per day and suggest the earliest non-crowded date.

    Span-only model: no personal net-hour estimation. A day is "crowded" when it already
    has >= `max_items_per_day` open items starting on it. Legacy `needed_hours` /
    `daily_capacity` kwargs are accepted and ignored for backward compatibility.
    """
    report = db.get_daily_workload(start_date=start_date, days=days)
    density: dict[str, dict[str, Any]] = {}
    recommended_date = None
    for d_str, info in report["days"].items():
        items = info.get("items", [])
        cnt = len(items)
        p0 = sum(1 for it in items if it.get("priority") == "P0")
        crowded = cnt >= max_items_per_day
        density[d_str] = {"item_count": cnt, "p0_count": p0, "crowded": crowded}
        if recommended_date is None and not crowded:
            recommended_date = d_str
    return {
        "days": report["days"],
        "density": density,
        "max_items_per_day": max_items_per_day,
        "recommended_start_date": recommended_date or next(iter(report["days"])),
    }
