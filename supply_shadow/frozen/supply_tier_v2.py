"""PRODUCT-1B V1 SUPPLY_RISK_TIER_V2. Semantic source: scripts/feb_tier.py (sha256 eab1f3fb...) filing index + tier(), verbatim
(also identical to feb_benchmark.py tier(), sha256 450dc9ca...). Label dicts: b1[acc]={'is_atm':bool,'baby_shelf_limited':bool},
b2[acc]={'transaction_type':str,'is_dilutive':'TRUE'|'FALSE'|'UNRESOLVED'}."""
import datetime as dt
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
ACTIVE_B2 = {'ATM_AGREEMENT', 'ELOC', 'ELOC_OR_PREPAID_ADVANCE'}
RANK = {'LOW': 0, 'MODERATE': 1, 'HIGH': 2, 'CRITICAL': 3}
def tier_filings(d):
    """feb_tier.py filing parse: skip empty acceptanceDateTime BEFORE first-seen dedup (differs from targets parse by design of source)."""
    seen, out = set(), []
    for c in [d['root']['filings']['recent']] + [h['data'] for h in d['history'] if 'data' in h]:
        for i in range(len(c['accessionNumber'])):
            a = c['accessionNumber'][i]
            if a in seen or not c['acceptanceDateTime'][i]: continue
            seen.add(a); out.append({'form': c['form'][i].strip(), 'known_at': c['acceptanceDateTime'][i], 'acc': a})
    return out
win = lambda rows, cut, n: [r for r in rows if cut - dt.timedelta(days=n) < P(r['known_at']) <= cut]
def pair(X, Y):
    for x in X:
        for y in Y:
            if x != y: return [x, y]
def tier(cutoff, rows, b1, b2):
    cut = P(cutoff); w90, w30 = win(rows, cut, 90), win(rows, cut, 30)
    active = [r['acc'] for r in w90 if b1.get(r['acc'], {}).get('is_atm') is True or b2.get(r['acc'], {}).get('transaction_type') in ACTIVE_B2]
    ready = [r['acc'] for r in w30 if r['form'] in ('EFFECT', '424B5')]
    p = pair(active, ready)
    if p: return 'CRITICAL', 'CRITICAL(A,B)', p
    if active: return 'HIGH', 'HIGH_RULE_1', active[:1]
    pr = [r['acc'] for r in w90 if b2.get(r['acc'], {}).get('transaction_type') in ('PIPE', 'REGISTERED_DIRECT')]
    if pr: return 'HIGH', 'HIGH_RULE_2', pr[:1]
    p = pair([r['acc'] for r in w90 if b1.get(r['acc'], {}).get('baby_shelf_limited') is True], ready)
    if p: return 'HIGH', 'HIGH_RULE_3', p
    for r in w90:
        if b2.get(r['acc'], {}).get('is_dilutive') == 'TRUE': return 'MODERATE', 'MODERATE_RULE_1', [r['acc']]
    for f, rule in (('EFFECT', 'MODERATE_RULE_2'), ('424B5', 'MODERATE_RULE_3')):
        for r in w90:
            if r['form'] == f: return 'MODERATE', rule, [r['acc']]
    return 'LOW', None, []
def labels_from_extractor(b1_records, b2_records):
    """Extractor output -> (b1, b2, u1, u2). Verbatim of feb_benchmark.py extractor_labels()."""
    b1, b2, u1, u2 = {}, {}, {}, {}
    for r in b1_records:
        b1[r['accession']] = {'is_atm': r['is_atm']['value'] == 'TRUE', 'baby_shelf_limited': r['baby_shelf_limited']['value'] == 'TRUE'}
        u1[r['accession']] = {f for f in ('is_atm', 'baby_shelf_limited') if r[f]['value'] == 'UNRESOLVED'}
    for r in b2_records:
        b2[r['accession']] = {'transaction_type': r['transaction_type']['value'], 'is_dilutive': r['is_dilutive']['value']}
        u2[r['accession']] = {f for f in ('transaction_type', 'is_dilutive') if r[f]['value'] == 'UNRESOLVED'}
    return b1, b2, u1, u2
