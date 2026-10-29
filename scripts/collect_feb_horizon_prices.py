#!/usr/bin/env python3
"""Collect 2026-02-02..2026-02-06 raw (adjusted=false) daily OHLCV + splits + dividends for a fixed ticker list,
ONLY to complete the fixed 5-trading-day outcome horizon of the January 2026 V2 prediction cohort.
Development Data Boundary: no February predictions, no February universe, no February performance.
Provider: Massive (same as STEP7H, market-data-provider-v1 FROZEN). Basic plan: <= 5 calls/min.
Fails (exit 1) if any ticker request fails; artifact keeps whatever was collected.
"""
import json, os, sys, time, hashlib, pathlib, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

BASE = "https://api.massive.com"
OUT = pathlib.Path("feb-horizon-prices-artifact")
SPACING = 13.0  # seconds between calls (<= 5/min)

def now(): return datetime.now(timezone.utc).isoformat()

def get(path, params, key):
    q = dict(params); q["apiKey"] = key
    req = urllib.request.Request(f"{BASE}{path}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "MicrocapRadar-TimeMachine/1.0"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = type(e).__name__ + f":{e.code}"
            if e.code not in (429, 500, 502, 503, 504): break
            time.sleep(60 if e.code == 429 else 5 * (attempt + 1))
        except Exception as e:
            last = type(e).__name__; time.sleep(5 * (attempt + 1))
    raise RuntimeError(last or "UnknownError")  # never includes the API key

def main():
    cfg = json.load(open(sys.argv[1]))
    key = (os.getenv("MASSIVE_API_KEY") or "").strip()
    if not key: raise SystemExit("MASSIVE_API_KEY secret is required")
    OUT.mkdir(exist_ok=True); (OUT / "ohlcv").mkdir(exist_ok=True)
    started = now(); failed = []; calls = 0; bars_total = 0
    for t in cfg["tickers"]:
        try:
            d = get(f"/v2/aggs/ticker/{t}/range/1/day/{cfg['date_from']}/{cfg['date_to']}", {"adjusted": "false", "limit": 50}, key); calls += 1
            rows = [{"ticker": t, "date": datetime.fromtimestamp(b["t"] / 1000, timezone.utc).strftime("%Y-%m-%d"),
                     "open": b.get("o"), "high": b.get("h"), "low": b.get("l"), "close": b.get("c"), "volume": b.get("v"), "vwap": b.get("vw"),
                     "adjusted": False, "provider": "Massive", "collected_at": now()} for b in d.get("results") or []]
            bars_total += len(rows)
            (OUT / "ohlcv" / f"{t}.json").write_text(json.dumps(rows, indent=1))
        except Exception as e:
            failed.append({"ticker": t, "error": str(e)})
        time.sleep(SPACING)
    actions = {}
    for kind, path, field in (("splits", "/v3/reference/splits", "execution_date"), ("dividends", "/v3/reference/dividends", "ex_dividend_date")):
        try:
            d = get(path, {f"{field}.gte": cfg["actions_from"], f"{field}.lte": cfg["date_to"], "limit": 1000}, key); calls += 1
            actions[kind] = [x for x in d.get("results") or [] if x.get("ticker") in set(cfg["action_tickers"])]
        except Exception as e:
            failed.append({"reference": kind, "error": str(e)}); actions[kind] = None
        time.sleep(SPACING)
    (OUT / "corporate-actions.json").write_text(json.dumps(actions, indent=1))
    manifest = []
    for p in sorted(OUT.rglob("*.json")):
        b = p.read_bytes(); manifest.append({"path": str(p.relative_to(OUT)), "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)})
    (OUT / "sha256-manifest.json").write_text(json.dumps(manifest, indent=1))
    summary = {"purpose": cfg["purpose"], "date_from": cfg["date_from"], "date_to": cfg["date_to"], "adjusted": False,
               "tickers_requested": len(cfg["tickers"]), "tickers_failed": len([f for f in failed if "ticker" in f]),
               "bars_total": bars_total, "api_calls": calls, "splits_found": None if actions.get("splits") is None else len(actions["splits"]),
               "dividends_found": None if actions.get("dividends") is None else len(actions["dividends"]),
               "started_at": started, "finished_at": now()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    if failed: (OUT / "failed.json").write_text(json.dumps(failed, indent=1))
    print(json.dumps(summary))
    if failed: raise SystemExit(1)

if __name__ == "__main__": main()
