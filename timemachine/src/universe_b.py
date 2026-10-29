#!/usr/bin/env python3
"""Claude independent universe builder B (written before seeing GPT builder A).
Usage: python universe_b.py <source_dir> <YYYY-MM> <out.json>
source_dir layout (STEP7H-style): calendar.json {"days":[...]}, ohlcv/{d}.jsonl.gz, investable/{d}.jsonl.gz, corporate-actions.json
Frozen V2 rule: target-month trading days whose previous trading day is in calendar.json; investable security_type=='CS',
primary_exchange in {XNAS,XNYS,XASE}; today+previous OHLCV present (key ticker_as_of_date, trading_date), previous close truthy,
today close not None; split on today (event_type contains 'SPLIT', effective_date==today): adj_prior = prior*from/to;
ret = close/adj_prior-1; order (ret ASC, ticker ASC); top 15; cik from same-day investable; cutoff = <date>T21:00:00Z.
Output: canonical 4-field list sorted (trading_date, ticker). Prints nothing but SHA256."""
import gzip, json, sys, hashlib
src, month, out = sys.argv[1:4]
days = json.load(open(f'{src}/calendar.json'))['days']
def load(kind, d, key):
    res = {}
    with gzip.open(f'{src}/{kind}/{d}.jsonl.gz', 'rt') as fh:
        for line in fh:
            r = json.loads(line); res[r[key]] = r
    return res
splits = {}
for e in json.load(open(f'{src}/corporate-actions.json')):
    if 'SPLIT' in e['event_type']:
        splits[(e['ticker'], e['effective_date'])] = (e['ratio']['from'], e['ratio']['to'])
recs = []
for i in range(1, len(days)):
    d, prev = days[i], days[i - 1]
    if not d.startswith(month + '-'): continue
    today, yday, inv = load('ohlcv', d, 'ticker_as_of_date'), load('ohlcv', prev, 'ticker_as_of_date'), load('investable', d, 'ticker')
    cand = []
    for t, r in inv.items():
        if r.get('security_type') != 'CS' or r.get('primary_exchange') not in ('XNAS', 'XNYS', 'XASE'): continue
        b, b0 = today.get(t), yday.get(t)
        if b is None or b0 is None or not b0.get('close') or b.get('close') is None: continue
        f_t = splits.get((t, d))
        pc = b0['close'] * f_t[0] / f_t[1] if f_t else b0['close']
        cand.append((b['close'] / pc - 1, t, r.get('cik')))
    cand.sort()
    recs += [{'ticker': t, 'trading_date': d, 'cik': c, 'prediction_cutoff': f'{d}T21:00:00Z'} for _, t, c in cand[:15]]
recs.sort(key=lambda r: (r['trading_date'], r['ticker']))
s = json.dumps(recs, sort_keys=True, separators=(',', ':'))
open(out, 'w').write(s)
print(f'UNIVERSE_B_SHA256={hashlib.sha256(s.encode()).hexdigest()}')
