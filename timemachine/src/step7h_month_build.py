#!/usr/bin/env python3
"""Month-parameterized STEP7H-compatible sealed source collector.

Usage:
  python timemachine/src/step7h_month_build.py <YYYY-MM> <source_dir>

Contract:
- calendar.json == {"days": [...]} and contains the previous trading day,
  every target-month trading day, and at least five following trading days.
- ohlcv/{date}.jsonl.gz contains Massive grouped-daily adjusted=false bars.
- investable/{date}.jsonl.gz exists for each target-month trading day.
- corporate-actions.json covers through the final horizon trading day.
- Logs/errors never emit price, return, volume, or vendor response bodies.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from .trading_calendar import is_trading_day

BASE = "https://api.massive.com"
MICS = {"XNAS", "XNYS", "XASE"}
EXCLUDE = {"ETF", "ETN", "WARRANT", "RIGHT", "UNIT", "PREFERRED", "FUND", "BOND"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_month(s: str) -> tuple[int, int]:
    try:
        y, m = map(int, s.split("-"))
        date(y, m, 1)
    except Exception:
        raise SystemExit("ERROR_CODE=INVALID_MONTH")
    if y != 2026:
        raise SystemExit("ERROR_CODE=UNSUPPORTED_YEAR")
    return y, m


def month_bounds(y: int, m: int) -> tuple[date, date]:
    first = date(y, m, 1)
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return first, nxt - timedelta(days=1)


def previous_trading_day(d: date) -> date:
    x = d - timedelta(days=1)
    while not is_trading_day(x):
        x -= timedelta(days=1)
    return x


def next_trading_days(d: date, n: int) -> list[date]:
    out = []
    x = d + timedelta(days=1)
    while len(out) < n:
        if is_trading_day(x):
            out.append(x)
        x += timedelta(days=1)
    return out


def target_trading_days(first: date, last: date) -> list[date]:
    out = []
    d = first
    while d <= last:
        if is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


class MassiveClient:
    def __init__(self):
        key = (os.getenv("MASSIVE_API_KEY") or "").strip()
        if not key:
            raise SystemExit("ERROR_CODE=MISSING_MASSIVE_API_KEY")
        self.key = key
        self.last = 0.0
        self.calls = 0
        self.retries_429 = 0
        self.status_counts: dict[str, int] = {}

    def get(self, path: str, params=None, retries: int = 6):
        q = dict(params or {})
        q["apiKey"] = self.key
        url = path if path.startswith("http") else BASE + path
        for attempt in range(retries + 1):
            wait = max(0.0, 12.5 - (time.monotonic() - self.last))
            time.sleep(wait)
            self.calls += 1
            self.last = time.monotonic()
            full = url + ("&" if "?" in url else "?") + urlencode(q)
            try:
                with urlopen(Request(full, headers={"User-Agent": "MicrocapRadar-TimeMachine/OOS"}), timeout=60) as r:
                    self.status_counts[str(r.status)] = self.status_counts.get(str(r.status), 0) + 1
                    return json.load(r)
            except HTTPError as e:
                self.status_counts[str(e.code)] = self.status_counts.get(str(e.code), 0) + 1
                if e.code == 429 and attempt < retries:
                    self.retries_429 += 1
                    retry_after = e.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(60, 15 * 2**attempt)
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"HTTP_{e.code}") from None
            except URLError:
                if attempt < retries:
                    time.sleep(min(60, 5 * 2**attempt))
                    continue
                raise RuntimeError("NETWORK_ERROR") from None
            except Exception as e:
                raise RuntimeError(type(e).__name__) from None
        raise RuntimeError("REQUEST_RETRIES_EXHAUSTED")


def ticker_pages(client: MassiveClient, day: str) -> list[dict]:
    path = "/v3/reference/tickers"
    q = {"market": "stocks", "date": day, "limit": 1000, "sort": "ticker", "order": "asc"}
    rows: list[dict] = []
    pages = 0
    while True:
        data = client.get(path, q)
        pages += 1
        rows.extend(data.get("results") or [])
        nxt = data.get("next_url")
        if not nxt:
            return rows
        if pages >= 30:
            raise RuntimeError("TICKER_PAGINATION_LIMIT")
        u = urlparse(nxt)
        path = u.path
        q = {k: v[-1] for k, v in parse_qs(u.query).items() if k.lower() != "apikey"}


def is_investable(row: dict) -> bool:
    if row.get("primary_exchange") not in MICS:
        return False
    typ = (row.get("type") or "UNKNOWN").upper()
    return not any(x in typ for x in EXCLUDE)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canon(obj), encoding="utf-8")


def write_jsonl_gz(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(canon(x) + "\n" for x in rows).encode("utf-8")
    path.write_bytes(gzip.compress(raw, mtime=0))


def main() -> int:
    if len(sys.argv) != 3:
        print("ERROR_CODE=USAGE", file=sys.stderr)
        return 2
    month, root_arg = sys.argv[1], sys.argv[2]
    y, m = parse_month(month)
    root = Path(root_arg)
    first, last = month_bounds(y, m)
    target = target_trading_days(first, last)
    if not target:
        print("ERROR_CODE=NO_TARGET_TRADING_DAYS", file=sys.stderr)
        return 1
    prior = previous_trading_day(target[0])
    horizon = next_trading_days(target[-1], 5)
    all_days = [prior] + target + horizon
    all_day_s = [d.isoformat() for d in all_days]
    target_s = [d.isoformat() for d in target]
    horizon_end = horizon[-1].isoformat()

    root.mkdir(parents=True, exist_ok=True)
    client = MassiveClient()
    started = time.time()
    stage = "INIT"
    try:
        stage = "CALENDAR"
        # Exact SEALED schema requested by the frozen contract.
        write_json(root / "calendar.json", {"days": all_day_s})

        stage = "INVESTABLE"
        # Preserve the original STEP7H semantics for universe construction:
        # collect PIT investable membership for prior + every target day.
        # The frozen external schema only requires target-day files, but the prior-day
        # file is an allowed same-format extension needed to reproduce the original
        # implicit "investable on prior day" OHLCV condition.
        investable_by_day = {}
        for day in [prior.isoformat()] + target_s:
            rows = ticker_pages(client, day)
            normalized = []
            for r in rows:
                x = {
                    "as_of_date": day,
                    "ticker": r.get("ticker"),
                    "cik": r.get("cik"),
                    "name": r.get("name"),
                    "primary_exchange": r.get("primary_exchange"),
                    "security_type": r.get("type"),
                    "list_date": r.get("list_date"),
                    "share_class_figi": r.get("share_class_figi"),
                    "composite_figi": r.get("composite_figi"),
                    "provider": "Massive",
                    "provider_known_at": None,
                    "collected_at": now_utc(),
                    "source_quality": "VENDOR_RECONSTRUCTED_PIT",
                }
                if is_investable(r):
                    normalized.append(x)
            if not normalized:
                raise RuntimeError("INVESTABLE_EMPTY")
            investable_by_day[day] = {x["ticker"] for x in normalized if x.get("ticker")}
            write_jsonl_gz(root / "investable" / f"{day}.jsonl.gz", normalized)

        stage = "OHLCV"
        # Prior + target OHLCV is filtered to same-day investable tickers, exactly as
        # original STEP7H. Horizon OHLCV remains all grouped bars for later outcomes.
        construction_days = set([prior.isoformat()] + target_s)
        for day in all_day_s:
            gd = client.get(
                f"/v2/aggs/grouped/locale/us/market/stocks/{day}",
                {"adjusted": "false", "include_otc": "false"},
            )
            grouped = gd.get("results") or []
            if not grouped:
                raise RuntimeError("GROUPED_RESULTS_EMPTY")
            allowed = investable_by_day.get(day) if day in construction_days else None
            out = []
            for b in grouped:
                ticker = b.get("T")
                if not ticker:
                    continue
                if allowed is not None and ticker not in allowed:
                    continue
                out.append({
                    "trading_date": day,
                    "ticker_as_of_date": ticker,
                    "open": b.get("o"),
                    "high": b.get("h"),
                    "low": b.get("l"),
                    "close": b.get("c"),
                    "volume": b.get("v"),
                    "vwap": b.get("vw"),
                    "transactions": b.get("n"),
                    "adjusted": False,
                    "provider": "Massive",
                    "collected_at": now_utc(),
                })
            write_jsonl_gz(root / "ohlcv" / f"{day}.jsonl.gz", out)

        stage = "CORPORATE_ACTIONS"
        sd = client.get(
            "/v3/reference/splits",
            {
                "execution_date.gte": prior.isoformat(),
                "execution_date.lte": horizon_end,
                "limit": 1000,
                "sort": "execution_date",
                "order": "asc",
            },
        )
        if sd.get("next_url"):
            raise RuntimeError("SPLIT_PAGINATION_UNHANDLED")
        actions = []
        for s in sd.get("results") or []:
            sf, st = s.get("split_from"), s.get("split_to")
            event_type = "SPLIT"
            try:
                event_type = "REVERSE_SPLIT" if float(sf) > float(st) else "FORWARD_SPLIT"
            except Exception:
                pass
            actions.append({
                "ticker": s.get("ticker"),
                "event_type": event_type,
                "effective_date": s.get("execution_date"),
                "ratio": {"from": sf, "to": st},
            })
        write_json(root / "corporate-actions.json", actions)

        stage = "SCHEMA_ASSERT"
        cal = json.loads((root / "calendar.json").read_text(encoding="utf-8"))
        if cal != {"days": all_day_s}:
            raise RuntimeError("CALENDAR_SCHEMA_MISMATCH")
        for day in [prior.isoformat()] + target_s:
            p = root / "investable" / f"{day}.jsonl.gz"
            if not p.exists():
                raise RuntimeError("INVESTABLE_MISSING")
            with gzip.open(p, "rt", encoding="utf-8") as f:
                if not any(line.strip() for line in f):
                    raise RuntimeError("INVESTABLE_EMPTY")
        for day in all_day_s:
            p = root / "ohlcv" / f"{day}.jsonl.gz"
            if not p.exists():
                raise RuntimeError("OHLCV_MISSING")
            with gzip.open(p, "rt", encoding="utf-8") as f:
                if not any(line.strip() for line in f):
                    raise RuntimeError("OHLCV_EMPTY")
        if not (root / "corporate-actions.json").exists():
            raise RuntimeError("CORPORATE_ACTIONS_MISSING")

        print(f"COLLECTION_STATUS=PASS month={month} days={len(all_day_s)} calls={client.calls}")
        return 0
    except Exception as e:
        # Deliberately sanitized: no row repr, vendor body, prices, returns, or volumes.
        print(f"ERROR_CODE=COLLECTION_FAILED stage={stage} type={type(e).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
