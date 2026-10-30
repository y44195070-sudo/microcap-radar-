"""PRODUCT-1B V1 trading calendar (standalone). Holiday data copied verbatim from timemachine/src/trading_calendar.py
(sha256 dcb2df06...). PRODUCT-1B-0 sec 9/10: prediction_cutoff = D T21:00:00Z fixed (NOT market-close/DST-dependent).
Fail-closed hardening: years without a frozen holiday table raise UnsupportedCalendarYear (research module silently
fell back to weekday-only outside 2026, which PRODUCT-1B-0 sec 11 prohibits)."""
from datetime import date, datetime, timedelta, timezone
CALENDAR_VERSION = 'US_EQUITY_CALENDAR_V1_2026'
HOLIDAYS = {2026: frozenset({date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
                             date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25)})}
class UnsupportedCalendarYear(Exception): pass
def is_trading_day(d: date) -> bool:
    if d.year not in HOLIDAYS: raise UnsupportedCalendarYear(d.year)
    return d.weekday() < 5 and d not in HOLIDAYS[d.year]
def prediction_cutoff(d: date) -> str:
    if not is_trading_day(d): raise ValueError('NOT_TRADING_DAY')
    return d.isoformat() + 'T21:00:00Z'
def target_trading_date(now_utc: datetime):
    """Scheduled run: target = UTC calendar date of now, iff it is a trading day and now >= that date's 21:00Z cutoff; else None (SKIPPED)."""
    if now_utc.tzinfo is None: raise ValueError('NAIVE_DATETIME')
    n = now_utc.astimezone(timezone.utc); d = n.date()
    if not is_trading_day(d): return None
    return d if n >= datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc) else None
def expected_latest_cutoff(now_utc: datetime) -> str:
    """For UI stale logic: most recent trading date D with D T21:00Z <= now."""
    n = now_utc.astimezone(timezone.utc); d = n.date()
    if not (is_trading_day(d) and n >= datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc)):
        d -= timedelta(days=1)
        while not is_trading_day(d): d -= timedelta(days=1)
    return prediction_cutoff(d)
