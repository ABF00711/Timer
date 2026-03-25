from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional


def local_now() -> datetime:
    return datetime.now().astimezone().replace(tzinfo=None)


def today_local() -> date:
    return local_now().date()


def start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def end_of_day(d: date) -> datetime:
    return datetime.combine(d, time(23, 59, 59, 999999))


def next_midnight(after: Optional[datetime] = None) -> datetime:
    base = after or local_now()
    d = base.date()
    return start_of_day(d + timedelta(days=1))


def ms_until(target: datetime) -> int:
    delta = target - local_now()
    ms = int(delta.total_seconds() * 1000)
    return max(ms, 0)
