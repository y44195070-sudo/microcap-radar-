#!/usr/bin/env python3
"""B2_NUMERIC_V2 — deterministic re-linking of numeric values to evidence spans.
No LLM judgment. Inputs: B2_V2 extraction JSON (candidate values), B2 source artifact (raw 8-K HTML + manifest).
For each candidate numeric value:
  1. normalize document text (HTML -> text, unescape, NBSP/thin spaces -> space, collapse whitespace)
  2. normalize candidate raw (strip trailing punctuation/space)
  3. find every occurrence of raw in text; keep only occurrences not followed by more digits/',digit'/'.digit'/' million' (no truncation)
  4. field-specific PRE-context rule on the 80 chars before the value:
       accept if a field anchor (within 130 chars, not itself preceded by fee/%/percent) is present and no other '$' amount sits between anchor and value
       reject if a modifier ('fee of', 'reimburse', 'not to exceed', 'at least', 'not less than', 'allowance', 'up to') is within 40 chars before the value
     text AFTER the value (e.g. 'before deducting fees and expenses') is ignored
  5. evidence_span = the sentence containing the accepted occurrence (exact substring of normalized text)
  6. no accepted occurrence -> UNRESOLVED
"""
import json, re, html, sys, hashlib, collections

V2, ART, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

ANCHORS = {
    'gross_proceeds': [r'gross proceeds', r'aggregate purchase price', r'aggregate gross proceeds'],
    'price_per_share': [r'price of', r'purchase price', r'offering price', r'at a price', r'per share price'],
    'shares_issued': [r'issue(?:d)? and s(?:ell|old)', r'aggregate of', r'sale of', r'offering of', r'issued'],
}
MODIFIERS = [r'fee of', r'fees of', r'reimburse', r'not to exceed', r'at least', r'not less than', r'allowance', r'up to']
SHARE_EXCLUDE = [r'outstanding', r'option', r'pre-funded', r'reserved', r'authorized']

def doc_text(p):
    t = open(p, 'rb').read().decode('utf-8', 'ignore')
    t = re.sub(r'(?is)<(script|style).*?</\1>', ' ', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = t.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
    return re.sub(r'\s+', ' ', t)

def norm_raw(r):
    r = str(r).replace(' ', ' ').strip()
    return re.sub(r'[\s,.;:]+$', '', r)

def sentence(t, i, j):
    a = max(t.rfind('. ', 0, i) + 2, t.rfind('; ', 0, i) + 2, 0)
    b = t.find('. ', j)
    b = len(t) if b < 0 else b + 1
    return t[a:b].strip()

def accept(field, t, i, raw):
    tail = t[i + len(raw): i + len(raw) + 10]
    if re.match(r'^(,\d|\d|\.\d|\s*(million|billion))', tail, re.I):
        return False, 'TRUNCATED'
    pre = t[max(0, i - 130): i].lower()
    near = t[max(0, i - 40): i].lower()
    if any(re.search(m, near) for m in MODIFIERS):
        return False, 'MODIFIER'
    if field == 'price_per_share' and re.search(r'exercise price|conversion price|exercisable|convertible', t[max(0, i - 60): i].lower()):
        return False, 'PRICE_IS_EXERCISE_OR_CONVERSION'
    if field == 'shares_issued' and re.search(r'warrant|option', t[max(0, i - 60): i].lower()):
        return False, 'SHARES_ARE_WARRANT_OR_OPTION'
    if field == 'shares_issued' and any(re.search(m, t[i: i + len(raw) + 80].lower()) for m in SHARE_EXCLUDE):
        return False, 'SHARE_CONTEXT_EXCLUDED'
    for a in ANCHORS[field]:
        for m in re.finditer(a, pre):
            abs_start = max(0, i - 130) + m.start()
            between = t[abs_start:i]
            # Anchor itself must not be in fee/percentage context.
            anchor_pre = t[max(0, abs_start - 30):abs_start].lower()
            if re.search(r'fee|%|percent', anchor_pre):
                continue
            # No other dollar amount between anchor and target value.
            if '$' in between:
                continue
            return True, 'OK'
    return False, 'NO_ANCHOR'

def candidate(v):
    return isinstance(v, dict) and v.get('raw') is not None and v.get('normalized') is not None

v2 = json.load(open(V2))
manifest = json.load(open(f'{ART}/manifest.json'))
raw_by_acc = {r['accession']: f"{ART}/{r['path']}" for r in manifest['files']}

stats = collections.Counter()
reasons = collections.Counter()
out_records = []
for r in v2['records']:
    o = {k: r.get(k) for k in ('accession','cik','form','known_at')}
    o['item'] = r.get('item') or r.get('items')
    t = doc_text(raw_by_acc[r['accession']])
    for field in ('gross_proceeds','price_per_share','shares_issued'):
        v = r.get(field)
        if v == 'NOT_APPLICABLE':
            o[field] = 'NOT_APPLICABLE'; continue
        if not candidate(v):
            o[field] = 'UNRESOLVED'; continue
        stats[f'{field}_candidates'] += 1
        raw = norm_raw(v['raw'])
        hits = [m.start() for m in re.finditer(re.escape(raw), t)]
        chosen = None; why = 'RAW_NOT_FOUND'
        for i in hits:
            ok, reason = accept(field, t, i, raw)
            if ok:
                sp = sentence(t, i, i + len(raw))
                assert raw in sp and sp in t
                chosen = {'raw': raw, 'normalized': v['normalized'], 'evidence_span': sp}
                why = 'OK'; break
            why = reason
        if chosen:
            o[field] = chosen
            stats[f'{field}_linked'] += 1
        else:
            o[field] = 'UNRESOLVED'
            reasons[f'{field}:{why}'] += 1
    out_records.append(o)

summary = {
    'version':'B2_NUMERIC_V2_DETERMINISTIC',
    'llm_rejudgment_used':False,
    'source_artifact':12882618389,
    'candidate_values_from':'B2_V2',
    'stats':dict(stats),
    'unresolved_reasons':dict(reasons),
    'rule':__doc__.strip(),
}
result = {'summary':summary,'records':out_records}
open(OUT,'w').write(json.dumps(result,indent=1,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2))
print('SHA256', hashlib.sha256(open(OUT,'rb').read()).hexdigest())
