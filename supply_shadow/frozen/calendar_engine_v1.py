"""PRODUCT-1B V1 calendar engine (data-driven). Semantics identical to trading_calendar.py (1B-1A, 37478428...) but holiday tables
come from calendar_data_v1.json. Years absent from data -> UnsupportedCalendarYear (fail closed). Cutoff fixed D T21:00:00Z."""
import json, os
from datetime import date, datetime, timedelta, timezone
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calendar_data_v1.json')
class UnsupportedCalendarYear(Exception): pass
class Calendar:
    def __init__(self, path=DATA_FILE):
        d = json.load(open(path)); self.version = d['calendar_version']
        self.holidays = {int(y): frozenset(date.fromisoformat(x) for x in v['full_day_closures']) for y, v in d['years'].items()}
    def is_trading_day(self, d):
        if d.year not in self.holidays: raise UnsupportedCalendarYear(d.year)
        return d.weekday() < 5 and d not in self.holidays[d.year]
    def prediction_cutoff(self, d):
        if not self.is_trading_day(d): raise ValueError('NOT_TRADING_DAY')
        return d.isoformat() + 'T21:00:00Z'
    def target_trading_date(self, now_utc):
        if now_utc.tzinfo is None: raise ValueError('NAIVE_DATETIME')
        n = now_utc.astimezone(timezone.utc); d = n.date()
        if not self.is_trading_day(d): return None
        return d if n >= datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc) else None
    def expected_latest_cutoff(self, now_utc):
        n = now_utc.astimezone(timezone.utc); d = n.date()
        if not (self.is_trading_day(d) and n >= datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc)):
            d -= timedelta(days=1)
            while not self.is_trading_day(d): d -= timedelta(days=1)
        return self.prediction_cutoff(d)
