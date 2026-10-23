from __future__ import annotations
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from .time_utils import normalize_utc

ET=ZoneInfo("America/New_York")
# Official 2026 US equity closures relevant to Model A. Extend by year before replaying another year.
HOLIDAYS_2026={date(2026,1,1),date(2026,1,19),date(2026,2,16),date(2026,4,3),date(2026,5,25),date(2026,6,19),date(2026,7,3),date(2026,9,7),date(2026,11,26),date(2026,12,25)}
EARLY_CLOSE_2026={date(2026,11,27):time(13,0),date(2026,12,24):time(13,0)}

def is_trading_day(d: date) -> bool:
    return d.weekday()<5 and d not in HOLIDAYS_2026

def get_eod_cutoff(trading_date: str) -> str:
    d=date.fromisoformat(trading_date)
    if not is_trading_day(d): raise ValueError(f"not a regular US equity trading day: {d}")
    close=EARLY_CLOSE_2026.get(d,time(16,0))
    local=datetime.combine(d,close,tzinfo=ET)
    return normalize_utc(local.isoformat())
