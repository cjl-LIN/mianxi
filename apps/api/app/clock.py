from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

LEVEL_LABEL = {
    "weak": "薄弱",
    "medium": "熟悉中",
    "mastered": "已掌握",
    "fluent": "熟练",
}


def now() -> datetime:
    return datetime.now(TZ)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat(timespec="seconds")


def today_bounds(day=None) -> tuple[str, str]:
    current = now()
    if day is None:
        day = current.date()
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    end = start + timedelta(days=1)
    return iso(start), iso(end)


def at_hour(days_from_today: int, hour: int) -> str:
    day = now().date() + timedelta(days=days_from_today)
    return iso(datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=TZ))


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def review_status(next_review_at: str | None) -> str:
    if not next_review_at:
        return "unscheduled"
    start, end = today_bounds()
    if next_review_at < start:
        return "overdue"
    if next_review_at < end:
        return "today"
    return "upcoming"


def days_until(next_review_at: str | None) -> int | None:
    if not next_review_at:
        return None
    return (parse_iso(next_review_at).date() - now().date()).days
