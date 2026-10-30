"""PRODUCT-1B V1 3A-1 signals. Semantic source: feb_sec_targets.py signal loop (sha256 4f754aa7...) with
action-3a1-signal-spec-v1.json (sha256 539209fd...). Ported verbatim. Not an input to SUPPLY_RISK_TIER_V2 (display/audit only)."""
import datetime as dt, json, os
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
SPEC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'action-3a1-signal-spec-v1.json')
def load_spec(path=SPEC_FILE): return json.load(open(path))
def signals(spec, rows, status, recent_earliest, cutoff):
    cut = P(cutoff); sig = {}
    for sid, s in spec['signals'].items():
        hits = [r['acc'] for r in rows if r['known_at'] and r['form'] in s['forms'] and ('item' not in s or s['item'] in r['items'])
                and cut - dt.timedelta(days=s['lookback_calendar_days']) < P(r['known_at']) <= cut]
        if status == 'INCOMPLETE_HISTORY' and not hits and not (recent_earliest and P(recent_earliest) <= cut - dt.timedelta(days=s['lookback_calendar_days'])):
            sig[sid] = 'UNRESOLVED_COVERAGE'
        else:
            sig[sid] = bool(hits)
        for a in hits:
            if P(next(r['known_at'] for r in rows if r['acc'] == a)) > cut: raise AssertionError('SEC_FUTURE_ACCESS_VIOLATION')
    return sig
