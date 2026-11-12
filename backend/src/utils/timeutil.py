"""时间工具：统一 UTC naive 存储 + 相对分钟换算成「业务时钟」。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.config.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") + "Z"


def minutes_to_clock(minutes: int) -> str:
    """相对分钟 -> HH:MM（可跨日，用 +1d 后缀表达）。"""
    minutes = int(minutes)
    day_offset = minutes // (24 * 60)
    minute_of_day = minutes % (24 * 60)
    text = f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"
    return f"{text}+{day_offset}d" if day_offset else text


def clock_to_minutes(clock: str) -> int:
    """HH:MM -> 从 00:00 起算的分钟数。"""
    hour, minute = clock.split(":")[:2]
    return int(hour) * 60 + int(minute)


def local_now(reference: datetime | None = None) -> datetime:
    """把 UTC naive 时间换算成业务时区（默认 UTC+8）的 naive 时间。"""
    base = reference or utcnow()
    return base + timedelta(minutes=settings.app_timezone_offset_minutes)


def local_stamp(value: datetime | None = None) -> str:
    return (value or local_now()).strftime("%Y-%m-%dT%H:%M")


def parse_local_stamp(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M")


def day_start(value: date) -> datetime:
    return datetime(value.year, value.month, value.day)


def human_duration(minutes: int) -> str:
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes}m"
    hours, rest = divmod(minutes, 60)
    return f"{hours}h{rest:02d}m"
