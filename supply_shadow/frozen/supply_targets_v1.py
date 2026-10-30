"""PRODUCT-1B V1 SEC filing parsing, assessability and B1/B2 target selection.
Semantic source: feb_sec_targets.py (sha256 4f754aa7...): filing parse (first-seen accession dedup, form.strip(), items split,
empty acceptanceDateTime -> known_at None), issuer status, assessability, B1/B2 target rule. Ported verbatim; I/O removed."""
import datetime as dt
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
def parse_submissions(d):
    """d = {'cik','root','history':[{'name','data'}|{'name',error}]} -> (cik:int, status, recent_earliest, filings list)."""
    cik = int(d['cik']); hist_ok = all('data' in h for h in d['history'])
    status = 'COMPLETE_HISTORY' if hist_ok else 'INCOMPLETE_HISTORY'
    rec = d['root']['filings']['recent']
    ka_recent = [x for x in rec['acceptanceDateTime'] if x]
    recent_earliest = min(ka_recent) if ka_recent else None
    seen, rows = set(), []
    for c in [rec] + [h['data'] for h in d['history'] if 'data' in h]:
        for i in range(len(c['accessionNumber'])):
            acc = c['accessionNumber'][i]
            if acc in seen: continue
            seen.add(acc)
            rows.append({'acc': acc, 'form': c['form'][i].strip(), 'known_at': c['acceptanceDateTime'][i] or None,
                         'items': {x.strip() for x in ((c.get('items') or [''] * len(c['form']))[i] or '').split(',') if x.strip()},
                         'primaryDocument': c['primaryDocument'][i]})
    return cik, status, recent_earliest, rows
def assessability(cik_raw, status, recent_earliest, cutoff):
    """status: COMPLETE_HISTORY | INCOMPLETE_HISTORY | None(=FAILED). Returns (assessable, reason)."""
    if not cik_raw: return False, 'NULL_CIK'
    cut = P(cutoff); st = status or 'FAILED'
    if st == 'FAILED': return False, 'SEC_ROOT_FAILED'
    if st == 'INCOMPLETE_HISTORY' and not (recent_earliest and P(recent_earliest) <= cut - dt.timedelta(days=90)):
        return False, 'INCOMPLETE_HISTORY_INSUFFICIENT_90D_COVERAGE'
    return True, None
def young_issuer(rows, cutoff):
    cut = P(cutoff); earliest = min((P(r['known_at']) for r in rows if r['known_at']), default=None)
    return bool(earliest and earliest > cut - dt.timedelta(days=1095))
def targets(cik, rows, cutoffs):
    """B1 = 424B5; B2 = 8-K/8-K/A with item 1.01 or 3.02; known_at in (c-90d, c] for any assessable cutoff c of this CIK."""
    cs = [P(c) for c in cutoffs]
    win = lambda ka: ka is not None and any(c - dt.timedelta(days=90) < P(ka) <= c for c in cs)
    b1, b2 = [], []
    for r in rows:
        if not win(r['known_at']): continue
        base = {'cik': str(cik), 'accession': r['acc'], 'primaryDocument': r['primaryDocument'], 'form': r['form'], 'known_at': r['known_at']}
        if r['form'] == '424B5': b1.append(dict(base))
        if r['form'] in ('8-K', '8-K/A') and {'1.01', '3.02'} & r['items']: b2.append(dict(base, items=','.join(sorted(r['items']))))
    key = lambda x: (int(x['cik']), x['known_at'], x['accession'])
    return sorted(b1, key=key), sorted(b2, key=key)
