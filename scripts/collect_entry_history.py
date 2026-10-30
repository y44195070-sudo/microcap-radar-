#!/usr/bin/env python3
"""ENTRY_SIGNAL_DEV_DATASET_V0 v1.0.0 — STEP ENTRY-1A dedicated history collector.
PRE_CUTOFF_FEATURE_HISTORY_ONLY: grouped daily (adjusted=false, all returned tickers) for every weekday
2025-11-26..2026-03-06 + all splits with execution_date in that range (next_url pagination to the end).
Trading days = weekdays with non-empty grouped results; empty weekdays must be exactly the known US market holidays,
otherwise the build fails. Output is STEP7H-compatible: calendar.json, ohlcv/{date}.jsonl.gz, corporate-actions.json.
No outcome computation. Logs never contain prices/volumes or vendor response bodies."""
import gzip, hashlib, json, os, sys, time, pathlib, urllib.request, urllib.parse, urllib.error
from datetime import date, datetime, timedelta, timezone
BASE = 'https://api.massive.com'
START, END = date(2025, 11, 26), date(2026, 3, 6)
HOLIDAYS = {'2025-11-27', '2025-12-25', '2026-01-01', '2026-01-19', '2026-02-16'}
OUT = pathlib.Path('entry-history-artifact')
canon = lambda o: json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

class Client:
    def __init__(self):
        self.key = (os.getenv('MASSIVE_API_KEY') or '').strip()
        if not self.key: raise SystemExit('ERROR_CODE=MISSING_MASSIVE_API_KEY')
        self.last = 0.0; self.calls = 0; self.status = {}
    def get(self, path, params=None, retries=6):
        q = dict(params or {}); q['apiKey'] = self.key
        url = path if path.startswith('http') else BASE + path
        for a in range(retries + 1):
            time.sleep(max(0.0, 12.5 - (time.monotonic() - self.last))); self.last = time.monotonic(); self.calls += 1
            try:
                with urllib.request.urlopen(urllib.request.Request(url + ('&' if '?' in url else '?') + urllib.parse.urlencode(q),
                                            headers={'User-Agent': 'MicrocapRadar-TimeMachine/ENTRY'}), timeout=60) as r:
                    self.status[str(r.status)] = self.status.get(str(r.status), 0) + 1; return json.load(r)
            except urllib.error.HTTPError as e:
                self.status[str(e.code)] = self.status.get(str(e.code), 0) + 1
                if e.code in (429, 500, 502, 503, 504) and a < retries: time.sleep(60 if e.code == 429 else 10 * (a + 1)); continue
                raise RuntimeError(f'HTTP_{e.code}') from None
            except urllib.error.URLError:
                if a < retries: time.sleep(10 * (a + 1)); continue
                raise RuntimeError('NETWORK_ERROR') from None
        raise RuntimeError('RETRIES_EXHAUSTED')

def main():
    c = Client(); stage = 'INIT'; started = datetime.now(timezone.utc).isoformat()
    try:
        (OUT / 'ohlcv').mkdir(parents=True, exist_ok=True)
        days, empty = [], []
        stage = 'OHLCV'
        d = START
        while d <= END:
            if d.weekday() < 5:
                ds = d.isoformat()
                res = c.get(f'/v2/aggs/grouped/locale/us/market/stocks/{ds}', {'adjusted': 'false', 'include_otc': 'false'}).get('results') or []
                if not res: empty.append(ds)
                else:
                    rows, seen = [], set()
                    for b in res:
                        t = b.get('T')
                        if not t: continue
                        if t in seen: raise RuntimeError('DUPLICATE_TICKER_BAR')
                        seen.add(t)
                        rows.append({'trading_date': ds, 'ticker_as_of_date': t, 'open': b.get('o'), 'high': b.get('h'), 'low': b.get('l'),
                                     'close': b.get('c'), 'volume': b.get('v'), 'vwap': b.get('vw'), 'transactions': b.get('n'),
                                     'adjusted': False, 'provider': 'Massive'})
                    rows.sort(key=lambda x: x['ticker_as_of_date'])
                    (OUT / 'ohlcv' / f'{ds}.jsonl.gz').write_bytes(gzip.compress(''.join(canon(x) + '\n' for x in rows).encode(), mtime=0))
                    days.append(ds)
            d += timedelta(days=1)
        if set(empty) != {h for h in HOLIDAYS if START.isoformat() <= h <= END.isoformat()}:
            raise RuntimeError('TRADING_CALENDAR_MISMATCH')
        (OUT / 'calendar.json').write_text(canon({'days': days}))
        stage = 'SPLITS'
        actions, pages = [], 0
        path, q = '/v3/reference/splits', {'execution_date.gte': START.isoformat(), 'execution_date.lte': END.isoformat(),
                                            'limit': 1000, 'sort': 'execution_date', 'order': 'asc'}
        while True:
            r = c.get(path, q); pages += 1
            for s in r.get('results') or []:
                sf, st = s.get('split_from'), s.get('split_to'); et = 'SPLIT'
                try: et = 'REVERSE_SPLIT' if float(sf) > float(st) else 'FORWARD_SPLIT'
                except Exception: pass
                actions.append({'ticker': s.get('ticker'), 'event_type': et, 'effective_date': s.get('execution_date'), 'ratio': {'from': sf, 'to': st}})
            nxt = r.get('next_url')
            if not nxt: break
            if pages >= 200: raise RuntimeError('SPLIT_PAGINATION_LIMIT')
            u = urllib.parse.urlparse(nxt); path = f'{u.scheme}://{u.netloc}{u.path}'
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query).items() if k.lower() != 'apikey'}
        actions.sort(key=lambda x: (x['effective_date'] or '', x['ticker'] or ''))
        (OUT / 'corporate-actions.json').write_text(canon(actions))
        stage = 'MANIFEST'
        man = [{'path': str(p.relative_to(OUT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
               for p in sorted(OUT.rglob('*')) if p.is_file()]
        (OUT / 'sha256-manifest.json').write_text(json.dumps(man, indent=1))
        summ = {'purpose': 'PRE_CUTOFF_FEATURE_HISTORY_ONLY', 'spec': 'ENTRY_SIGNAL_DEV_DATASET_V0 1.0.0', 'range': [START.isoformat(), END.isoformat()],
                'trading_days': len(days), 'holidays_empty': sorted(empty), 'split_pages': pages, 'split_events': len(actions),
                'corporate_action_coverage': 'COMPLETE', 'api_calls': c.calls, 'http_status_counts': c.status,
                'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat()}
        (OUT / 'summary.json').write_text(json.dumps(summ, indent=1))
        print(f"COLLECTION_STATUS=PASS trading_days={len(days)} split_events={len(actions)} split_pages={pages} calls={c.calls}")
        return 0
    except Exception as e:
        print(f'ERROR_CODE=COLLECTION_FAILED stage={stage} type={type(e).__name__} code={e}', file=sys.stderr)
        return 1
if __name__ == '__main__': raise SystemExit(main())
