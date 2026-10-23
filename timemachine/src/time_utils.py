from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

class TimestampError(ValueError):
    pass

def normalize_utc(value: str, *, source_timezone: str | None = None) -> str:
    """Return canonical UTC ISO-8601 with Z. Naive input is rejected unless source_timezone is explicit."""
    if not isinstance(value, str) or not value.strip():
        raise TimestampError("timestamp must be a non-empty ISO-8601 string")
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TimestampError(f"invalid ISO-8601 timestamp: {value}") from exc
    if dt.tzinfo is None:
        if not source_timezone:
            raise TimestampError(f"naive timestamp requires explicit source_timezone: {value}")
        dt = dt.replace(tzinfo=ZoneInfo(source_timezone))
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def normalize_optional(value: str | None, *, source_timezone: str | None = None) -> str | None:
    return None if value is None else normalize_utc(value, source_timezone=source_timezone)

def utc_le(left: str, right: str) -> bool:
    return normalize_utc(left) <= normalize_utc(right)
