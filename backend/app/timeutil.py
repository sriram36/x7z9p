"""Time helpers. All stored timestamps are UTC; business logic is in UK local time."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")
SLOT = timedelta(minutes=30)


def parse_utc(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_date(dt: datetime) -> date:
    return dt.astimezone(LONDON).date()


def local_hhmm(dt: datetime) -> str:
    return dt.astimezone(LONDON).strftime("%H:%M")


def local_hour(dt: datetime) -> int:
    return dt.astimezone(LONDON).hour


def delivery_slots(day: date) -> list:
    """Half-hour slot start times (UTC) covering one UK local delivery day.

    48 slots normally, 46 / 50 on the DST change days.
    """
    start = datetime.combine(day, time(0, 0), LONDON).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0, 0), LONDON).astimezone(UTC)
    out, t = [], start
    while t < end:
        out.append(t)
        t += SLOT
    return out


def cutoff_utc(day: date, hhmm: str) -> datetime:
    """Decision cutoff: HH:MM UK local time on the day *before* the delivery day."""
    h, m = (int(x) for x in hhmm.split(":"))
    local = datetime.combine(day - timedelta(days=1), time(h, m), LONDON)
    return local.astimezone(UTC)
