"""Deterministic China statutory holiday & weekend makeup-workday calendar (2024–2027).

Zero external dependencies so both macOS dev and Aliyun ECS production run identically.
Used by exact attendance accounting (excluding weekends & CN statutory holidays while
including official weekend makeup workdays per State Council annual schedules).
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _date_range(start_iso: str, end_iso: str) -> set[str]:
    cur = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    out: set[str] = set()
    while cur <= end:
        out.add(cur.isoformat())
        cur += timedelta(days=1)
    return out


# Official State Council China statutory holidays (2024–2027)
CN_STATUTORY_HOLIDAYS: frozenset[str] = frozenset(
    # 2024
    {"2024-01-01"}
    | _date_range("2024-02-10", "2024-02-17")
    | _date_range("2024-04-04", "2024-04-06")
    | _date_range("2024-05-01", "2024-05-05")
    | _date_range("2024-06-08", "2024-06-10")
    | _date_range("2024-09-15", "2024-09-17")
    | _date_range("2024-10-01", "2024-10-07")
    # 2025
    | {"2025-01-01"}
    | _date_range("2025-01-28", "2025-02-04")
    | _date_range("2025-04-04", "2025-04-06")
    | _date_range("2025-05-01", "2025-05-05")
    | _date_range("2025-05-31", "2025-06-02")
    | _date_range("2025-10-01", "2025-10-08")
    # 2026 (State Council 2026 schedule)
    | _date_range("2026-01-01", "2026-01-03")
    | _date_range("2026-02-15", "2026-02-23")
    | _date_range("2026-04-04", "2026-04-06")
    | _date_range("2026-05-01", "2026-05-05")
    | _date_range("2026-06-19", "2026-06-21")
    | _date_range("2026-09-25", "2026-09-27")
    | _date_range("2026-10-01", "2026-10-07")
    # 2027 baseline statutory holidays
    | _date_range("2027-01-01", "2027-01-03")
    | _date_range("2027-02-06", "2027-02-12")
    | _date_range("2027-04-03", "2027-04-05")
    | _date_range("2027-05-01", "2027-05-05")
    | {"2027-06-09", "2027-09-15"}
    | _date_range("2027-10-01", "2027-10-07")
)

# Official State Council makeup-workday weekends (调休补班日)
CN_MAKEUP_WORKDAYS: frozenset[str] = frozenset(
    {
        # 2024
        "2024-02-04",
        "2024-02-18",
        "2024-04-07",
        "2024-04-28",
        "2024-05-11",
        "2024-09-14",
        "2024-09-29",
        "2024-10-12",
        # 2025
        "2025-01-26",
        "2025-02-08",
        "2025-04-27",
        "2025-09-28",
        "2025-10-11",
        # 2026
        "2026-01-04",
        "2026-02-14",
        "2026-02-28",
        "2026-05-09",
        "2026-09-20",
        "2026-10-10",
    }
)


def _to_date(day: date | str) -> date:
    if isinstance(day, date) and not isinstance(day, datetime):
        return day
    if isinstance(day, datetime):
        return day.date()
    return date.fromisoformat(str(day).strip()[:10])


def is_cn_workday(day: date | str) -> bool:
    """Return True if `day` is an official Chinese working day (incl. makeup weekends)."""
    d = _to_date(day)
    iso = d.isoformat()
    if iso in CN_MAKEUP_WORKDAYS:
        return True
    if iso in CN_STATUTORY_HOLIDAYS:
        return False
    return d.weekday() < 5


def count_cn_workdays(start_date: date | str, end_date: date | str) -> list[str]:
    """Return sorted ISO YYYY-MM-DD list of official Chinese workdays in `[start_date, end_date]`."""
    cur = _to_date(start_date)
    end = _to_date(end_date)
    if cur > end:
        return []
    workdays: list[str] = []
    while cur <= end:
        if is_cn_workday(cur):
            workdays.append(cur.isoformat())
        cur += timedelta(days=1)
    return workdays


def is_within_next_morning_grace(
    work_date: date | str,
    submitted_at: datetime | str,
    *,
    grace_cutoff_hhmm: str = "12:00",
) -> bool:
    """Return True if `submitted_at` (Asia/Shanghai) is <= next calendar day `grace_cutoff_hhmm`."""
    wd = _to_date(work_date)
    if isinstance(submitted_at, datetime):
        sub_dt = submitted_at
    else:
        raw = str(submitted_at).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        sub_dt = datetime.fromisoformat(raw)

    if sub_dt.tzinfo is None:
        sub_dt = sub_dt.replace(tzinfo=_TZ_SHANGHAI)
    else:
        sub_dt = sub_dt.astimezone(_TZ_SHANGHAI)

    parts = [int(p) for p in grace_cutoff_hhmm.strip().split(":")]
    hh = parts[0]
    mm = parts[1] if len(parts) > 1 else 0
    ss = parts[2] if len(parts) > 2 else 0
    deadline = datetime.combine(wd + timedelta(days=1), dt_time(hh, mm, ss), tzinfo=_TZ_SHANGHAI)
    return sub_dt <= deadline
