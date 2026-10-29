#!/usr/bin/env python3
"""GPT independent implementation A for the frozen V2 universe rule.

Usage:
  python timemachine/src/build_v2_universe_month.py <source_dir> <YYYY-MM> <out.json>

Output file is canonical JSON containing only the four public occurrence fields.
stdout is exactly one line: UNIVERSE_A_SHA256=<sha>
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

EXCHANGES = {"XNAS", "XNYS", "XASE"}
PUBLIC_KEYS = {"ticker", "trading_date", "cik", "prediction_cutoff"}


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    if len(sys.argv) != 4:
        print("ERROR_CODE=USAGE", file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    month = sys.argv[2]
    out_path = Path(sys.argv[3])

    try:
        cal_obj = json.loads((source / "calendar.json").read_text(encoding="utf-8"))
        if set(cal_obj.keys()) != {"days"} or not isinstance(cal_obj["days"], list):
            raise RuntimeError("CALENDAR_SCHEMA_MISMATCH")
        calendar = cal_obj["days"]
        if calendar != sorted(calendar) or len(calendar) != len(set(calendar)):
            raise RuntimeError("CALENDAR_ORDER_MISMATCH")

        target_days = [d for d in calendar if d.startswith(month + "-")]
        if not target_days:
            raise RuntimeError("NO_TARGET_DAYS")
        index = {d: i for i, d in enumerate(calendar)}

        actions = json.loads((source / "corporate-actions.json").read_text(encoding="utf-8"))
        if not isinstance(actions, list):
            raise RuntimeError("CORPORATE_ACTIONS_SCHEMA_MISMATCH")
        split = {}
        for e in actions:
            if "SPLIT" not in str(e.get("event_type", "")):
                continue
            key = (e.get("ticker"), e.get("effective_date"))
            ratio = e.get("ratio") or {}
            split[key] = (ratio.get("from"), ratio.get("to"))

        # Load only bars required for target-day ranking and their previous trading days.
        needed_days = set(target_days)
        for d in target_days:
            i = index[d]
            if i <= 0:
                raise RuntimeError("PRIOR_TRADING_DAY_MISSING")
            needed_days.add(calendar[i - 1])

        px = {}
        for d in sorted(needed_days):
            p = source / "ohlcv" / f"{d}.jsonl.gz"
            if not p.exists():
                raise RuntimeError("OHLCV_FILE_MISSING")
            for b in load_jsonl_gz(p):
                if "ticker_as_of_date" not in b or "close" not in b:
                    raise RuntimeError("OHLCV_SCHEMA_MISMATCH")
                px[(b["ticker_as_of_date"], d)] = b

        occurrences = []
        for d in target_days:
            i = index[d]
            prev = calendar[i - 1]
            inv_path = source / "investable" / f"{d}.jsonl.gz"
            if not inv_path.exists():
                raise RuntimeError("INVESTABLE_FILE_MISSING")
            rows = []
            for r in load_jsonl_gz(inv_path):
                required = {"ticker", "security_type", "primary_exchange", "cik"}
                if not required.issubset(r):
                    raise RuntimeError("INVESTABLE_SCHEMA_MISMATCH")
                ticker = r["ticker"]
                if r.get("security_type") != "CS" or r.get("primary_exchange") not in EXCHANGES:
                    continue
                today = px.get((ticker, d))
                prior = px.get((ticker, prev))
                if not today or not prior or not prior.get("close") or today.get("close") is None:
                    continue
                prior_close = prior["close"]
                ratio = split.get((ticker, d))
                if ratio is not None:
                    rf, rt = ratio
                    if rf is None or rt in (None, 0):
                        raise RuntimeError("INVALID_SPLIT_RATIO")
                    prior_close = prior_close * rf / rt
                ret = today["close"] / prior_close - 1
                rows.append((ret, ticker, r.get("cik")))

            rows.sort(key=lambda x: (x[0], x[1]))
            for _, ticker, cik in rows[:15]:
                occurrences.append({
                    "ticker": ticker,
                    "trading_date": d,
                    "cik": cik,
                    "prediction_cutoff": f"{d}T21:00:00Z",
                })

        occurrences.sort(key=lambda r: (r["trading_date"], r["ticker"]))
        if any(set(r.keys()) != PUBLIC_KEYS for r in occurrences):
            raise RuntimeError("PUBLIC_SCHEMA_MISMATCH")
        raw = canonical_bytes(occurrences)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw)
        print("UNIVERSE_A_SHA256=" + hashlib.sha256(raw).hexdigest())
        return 0
    except Exception as e:
        # Sanitized: never print price/return/bar objects or exception messages.
        print(f"ERROR_CODE=UNIVERSE_A_FAILED type={type(e).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
