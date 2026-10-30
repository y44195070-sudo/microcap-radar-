import re, html
def norm(path):
    t = open(path, 'rb').read().decode('utf-8', 'ignore')
    t = re.sub(r'(?is)<(script|style).*?</\1>', ' ', t)
    t = re.sub(r'(?i)<(br|p|div|tr|li|h\d)[^>]*>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = t.replace('\xa0', ' ').replace(' ', ' ').replace(' ', ' ').replace('“', '"').replace('”', '"').replace('’', "'")
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    return re.sub(r'\s*\n\s*', '\n', t).replace('\n', ' ')
def ev(acc, doc, rule, t, m, pad=160):
    s, e = max(0, m.start() - pad), min(len(t), m.end() + pad)
    return {'accession': acc, 'document': doc, 'rule_id': rule, 'evidence_text': t[s:e], 'start_offset': s, 'end_offset': e}
