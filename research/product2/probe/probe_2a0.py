#!/usr/bin/env python3
"""PRODUCT-2 STEP 2A-0 PROBE (read-only, stdlib only).

Questions answered (no model, no outcome inspection):
  P1  Earliest grouped-daily date available on the current Massive plan.
  P2  Daily-bar session composition: does the grouped daily bar (adjusted=false)
      equal the REGULAR session (09:30-16:00 ET, or 13:00 on early-close days)
      or the FULL extended session (04:00-20:00 ET)?  -> decides whether D-bar
      fields are known by the D T21:00Z cutoff and whether entry-day HIGH can
      contain pre-market prints before the entry OPEN.
  P3  Splits endpoint: history depth / page count for the library window.
  P4  Reference-tickers date snapshot: inside vs outside the 2-year window.

Probe dates avoid 2026-03 (QUARANTINE) and 2026-04..2026-09 (FINAL OOS).
The API key is read from MASSIVE_API_KEY, sent only as an Authorization header,
and never printed. The report contains summary numbers only (no raw dumps).
"""
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE = "https://api.massive.com"
ET = ZoneInfo("America/New_York")
SPACING_S = 13.0          # 5 calls/min plan limit -> one call per >=12 s
MAX_RETRY = 3
FORBIDDEN_RANGES = [(dt.date(2026, 3, 1), dt.date(2026, 9, 30))]  # quarantine + final OOS

# (date, early_close) ; EDT and EST samples + one early close each
BAR_DATES = [
    ("2025-07-15", False),   # EDT, development period
    ("2025-07-03", True),    # EDT early close 13:00 ET
    ("2025-11-28", True),    # EST early close 13:00 ET
    ("2025-12-15", False),   # EST
    ("2026-10-15", False),   # EDT, after final OOS window
]
TICKERS_PER_DATE = 4

_last_call = [0.0]
_stats = {"requests": 0, "http_429": 0, "retries": 0, "failures": 0}


def _check_allowed(d):
    for lo, hi in FORBIDDEN_RANGES:
        if lo <= d <= hi:
            raise SystemExit(f"PROBE_ABORT: date {d} is inside a protected range")


def call(path, params=None):
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        raise SystemExit("BLOCKED_API_KEY_NOT_CONNECTED")
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    if "apiKey=" in url:
        raise SystemExit("PROBE_ABORT: key must not be in URL")
    for attempt in range(MAX_RETRY + 1):
        wait = SPACING_S - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        _stats["requests"] += 1
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + key,
            "Accept-Encoding": "gzip",
            "User-Agent": "microcap-radar-product2-probe/1",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                if e.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                payload = json.loads(body)
            except Exception:
                payload = {"raw_len": len(body)}
            if e.code == 429 and attempt < MAX_RETRY:
                _stats["http_429"] += 1
                _stats["retries"] += 1
                time.sleep(65)
                continue
            if e.code >= 500 and attempt < MAX_RETRY:
                _stats["retries"] += 1
                time.sleep(20)
                continue
            _stats["failures"] += 1
            # keep only non-secret diagnostic fields
            return e.code, {k: payload.get(k) for k in ("status", "error", "message", "request_id") if isinstance(payload, dict)}
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRY:
                _stats["retries"] += 1
                time.sleep(20)
                continue
            _stats["failures"] += 1
            return -1, {"error": type(e).__name__}
    return -1, {"error": "exhausted"}


def grouped(d):
    _check_allowed(d)
    return call(f"/v2/aggs/grouped/locale/us/market/stocks/{d.isoformat()}",
                {"adjusted": "false", "include_otc": "false"})


# ---------------------------------------------------------------- P1
def probe_earliest(today):
    """Binary search over weekdays for the earliest date returning bars."""
    def has_data(d):
        # step forward over weekend/holiday (0 results) up to 4 days
        for k in range(5):
            x = d + dt.timedelta(days=k)
            if x.weekday() >= 5:
                continue
            st, js = grouped(x)
            n = js.get("resultsCount", 0) if st == 200 else 0
            log.append({"date": x.isoformat(), "http": st, "results": n,
                        "status": js.get("status"), "message": (js.get("message") or js.get("error"))})
            if st == 200 and n > 0:
                return True, x
            if st != 200:
                return False, x
        return False, d
    log = []
    lo = today - dt.timedelta(days=365 * 3)       # assumed unavailable
    hi = today - dt.timedelta(days=365 * 2 - 30)  # assumed available
    ok_hi, _ = has_data(hi)
    ok_lo, _ = has_data(lo)
    result = {"probe_log": log}
    if not ok_hi:
        result["verdict"] = "INCONCLUSIVE_HI_UNAVAILABLE"
        return result
    if ok_lo:
        result["verdict"] = "AVAILABLE_BEYOND_3Y"
        result["earliest_available"] = None
        return result
    while (hi - lo).days > 3:
        mid = lo + (hi - lo) / 2
        ok, _ = has_data(mid)
        if ok:
            hi = mid
        else:
            lo = mid
    result["verdict"] = "BOUNDARY_FOUND"
    result["earliest_available_approx"] = hi.isoformat()
    result["latest_unavailable_approx"] = lo.isoformat()
    result["window_days_from_today"] = (today - hi).days
    return result


# ---------------------------------------------------------------- P2
def session_bounds(d, early):
    o = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
    c = dt.datetime(d.year, d.month, d.day, 13 if early else 16, 0, tzinfo=ET)
    return o, c


def agg(bars):
    if not bars:
        return None
    return {"o": bars[0]["o"], "h": max(b["h"] for b in bars), "l": min(b["l"] for b in bars),
            "c": bars[-1]["c"], "v": sum(b["v"] for b in bars), "n_min": len(bars)}


def rel_eq(a, b, tol=1e-6):
    if a is None or b is None:
        return None
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def probe_bar(dstr, early):
    d = dt.date.fromisoformat(dstr)
    st, js = grouped(d)
    out = {"date": dstr, "early_close": early, "grouped_http": st}
    if st != 200 or not js.get("results"):
        out["verdict"] = "NO_GROUPED_DATA"
        return out
    rows = [r for r in js["results"] if 0.2 <= r.get("c", 0) <= 20 and r.get("v", 0) > 0
            and r.get("T", "").isalpha() and len(r.get("T", "")) <= 5]
    rows.sort(key=lambda r: r["v"] * r["c"], reverse=True)
    picks = rows[:TICKERS_PER_DATE]
    o_et, c_et = session_bounds(d, early)
    o_utc, c_utc = o_et.astimezone(dt.timezone.utc), c_et.astimezone(dt.timezone.utc)
    cutoff = dt.datetime(d.year, d.month, d.day, 21, 0, tzinfo=dt.timezone.utc)
    out.update({"regular_open_utc": o_utc.isoformat(), "regular_close_utc": c_utc.isoformat(),
                "cutoff_utc": cutoff.isoformat(),
                "regular_close_le_cutoff": c_utc <= cutoff,
                "grouped_bar_t_utc": None, "tickers": []})
    for r in picks:
        t = r["T"]
        out["grouped_bar_t_utc"] = dt.datetime.fromtimestamp(r["t"] / 1000, dt.timezone.utc).isoformat()
        st2, mj = call(f"/v2/aggs/ticker/{urllib.parse.quote(t)}/range/1/minute/{dstr}/{dstr}",
                       {"adjusted": "false", "sort": "asc", "limit": 50000})
        rec = {"ticker_rank": len(out["tickers"]) + 1, "minute_http": st2}
        bars = mj.get("results") or [] if st2 == 200 else []
        if not bars:
            rec["verdict"] = "NO_MINUTE_DATA"
            out["tickers"].append(rec)
            continue
        o_ms, c_ms, cut_ms = o_utc.timestamp() * 1000, c_utc.timestamp() * 1000, cutoff.timestamp() * 1000
        full = agg(bars)
        reg = agg([b for b in bars if o_ms <= b["t"] < c_ms])
        pre_cut = agg([b for b in bars if b["t"] < cut_ms])
        post = [b for b in bars if b["t"] >= c_ms]
        pre = [b for b in bars if b["t"] < o_ms]
        g = {k: r.get(k) for k in ("o", "h", "l", "c", "v")}
        rec.update({
            "minutes_pre_market": len(pre), "minutes_post_market": len(post),
            "minutes_after_cutoff": len([b for b in bars if b["t"] >= cut_ms]),
            "last_minute_utc": dt.datetime.fromtimestamp(bars[-1]["t"] / 1000, dt.timezone.utc).isoformat(),
            "match_regular": {k: rel_eq(g[k], reg[k] if reg else None, 1e-6 if k != "v" else 0.02) for k in g},
            "match_full": {k: rel_eq(g[k], full[k], 1e-6 if k != "v" else 0.02) for k in g},
            "match_pre_cutoff": {k: rel_eq(g[k], pre_cut[k] if pre_cut else None, 1e-6 if k != "v" else 0.02) for k in g},
            "volume_ratio_daily_over_regular": (g["v"] / reg["v"]) if reg and reg["v"] else None,
            "volume_ratio_daily_over_full": (g["v"] / full["v"]) if full["v"] else None,
            "premarket_high_exceeds_regular_high": bool(pre) and reg is not None and max(b["h"] for b in pre) > reg["h"],
            "postmarket_high_exceeds_regular_high": bool(post) and reg is not None and max(b["h"] for b in post) > reg["h"],
        })
        out["tickers"].append(rec)
    return out


def summarize_bar(results):
    fields = ("o", "h", "l", "c", "v")
    s = {}
    for mode in ("match_regular", "match_full", "match_pre_cutoff"):
        s[mode] = {}
        for f in fields:
            vals = [t[mode][f] for r in results for t in r.get("tickers", []) if mode in t and t[mode][f] is not None]
            s[mode][f] = {"true": sum(1 for v in vals if v), "n": len(vals)}
    n = s["match_regular"]["h"]["n"]
    # discriminating cases: regular-session value differs from full-session value
    disc = {}
    for f in fields:
        reg_only = full_only = both = neither = 0
        for r in results:
            for t in r.get("tickers", []):
                if "match_regular" not in t:
                    continue
                a, b = t["match_regular"][f], t["match_full"][f]
                if a and not b:
                    reg_only += 1
                elif b and not a:
                    full_only += 1
                elif a and b:
                    both += 1
                else:
                    neither += 1
        disc[f] = {"matches_regular_only": reg_only, "matches_full_only": full_only,
                   "indistinguishable": both, "matches_neither": neither}
    s["discriminating"] = disc

    def all_true(mode, f):
        x = s[mode][f]
        return x["n"] > 0 and x["true"] == x["n"]
    verdict = {}
    for f in fields:
        if all_true("match_regular", f) and not all_true("match_full", f):
            verdict[f] = "REGULAR_SESSION"
        elif all_true("match_full", f) and not all_true("match_regular", f):
            verdict[f] = "FULL_EXTENDED_SESSION"
        elif all_true("match_full", f) and all_true("match_regular", f):
            verdict[f] = "INDISTINGUISHABLE_IN_SAMPLE"
        else:
            verdict[f] = "MIXED_OR_OTHER"
    return {"field_match_counts": s, "field_verdict": verdict, "ticker_days": n}


# ---------------------------------------------------------------- P3 / P4
def probe_splits(start, end):
    st, js = call("/v3/reference/splits", {"execution_date.gte": start.isoformat(),
                                           "execution_date.lte": end.isoformat(),
                                           "limit": 1000, "order": "asc", "sort": "execution_date"})
    res = js.get("results") or [] if st == 200 else []
    st_old, js_old = call("/v3/reference/splits", {"execution_date.lte": (start - dt.timedelta(days=400)).isoformat(),
                                                   "limit": 5, "order": "desc", "sort": "execution_date"})
    return {"http": st, "first_page_n": len(res), "has_next_page": bool(js.get("next_url")) if st == 200 else None,
            "first_execution_date": res[0].get("execution_date") if res else None,
            "last_execution_date_on_page": res[-1].get("execution_date") if res else None,
            "reverse_on_page": sum(1 for x in res if x.get("split_from", 0) > x.get("split_to", 0)),
            "older_than_window_http": st_old,
            "older_than_window_n": len(js_old.get("results") or []) if st_old == 200 else None,
            "message": js.get("message") or js.get("error")}


def probe_reference(d_in, d_out):
    out = {}
    for label, d in (("inside_window", d_in), ("outside_window", d_out)):
        st, js = call("/v3/reference/tickers", {"market": "stocks", "date": d.isoformat(),
                                                "active": "true", "limit": 1000})
        res = js.get("results") or [] if st == 200 else []
        types = {}
        for x in res:
            types[x.get("type")] = types.get(x.get("type"), 0) + 1
        out[label] = {"date": d.isoformat(), "http": st, "first_page_n": len(res),
                      "has_next_page": bool(js.get("next_url")) if st == 200 else None,
                      "type_counts_first_page": types,
                      "cik_present_first_page": sum(1 for x in res if x.get("cik")),
                      "message": js.get("message") or js.get("error")}
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "probe_2a0_report.json"
    today = dt.datetime.now(dt.timezone.utc).date()
    rep = {"step": "PRODUCT_2_STAGE_2A_STEP_0_PROBE", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "plan_assumed": "Stocks Basic", "protected_ranges": [[a.isoformat(), b.isoformat()] for a, b in FORBIDDEN_RANGES]}
    rep["P2_bar_session"] = {"samples": [probe_bar(d, e) for d, e in BAR_DATES]}
    rep["P2_bar_session"]["summary"] = summarize_bar(rep["P2_bar_session"]["samples"])
    rep["P1_earliest_grouped_daily"] = probe_earliest(today)
    start = today - dt.timedelta(days=730)
    rep["P3_splits"] = probe_splits(start, dt.date(2025, 12, 31))
    rep["P4_reference_snapshot"] = probe_reference(dt.date(2024, 12, 2), dt.date(2023, 6, 1))
    rep["call_stats"] = dict(_stats)
    body = json.dumps(rep, ensure_ascii=False, sort_keys=True, indent=1)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)
    print("PROBE_DONE sha256=" + hashlib.sha256(body.encode()).hexdigest())
    print(json.dumps({"P1": {k: v for k, v in rep["P1_earliest_grouped_daily"].items() if k != "probe_log"},
                      "P2": rep["P2_bar_session"]["summary"]["field_verdict"],
                      "calls": _stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
