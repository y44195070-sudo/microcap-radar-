#!/usr/bin/env python3
"""PRODUCT-1 V1 B2 deterministic extractor (8-K). Spec: PRODUCT-1A-0 v1.0.0 sec 6,7,8,11-26 + PRE_EXTRACTOR_DECISIONS_V1.
No LLM, no outcome data, no future filings, no per-accession/ticker tables.
Pipeline:
 1. ITEM SCOPE: operative text = Items 1.01 / 1.02 / 2.03 / 3.02 / 3.03 / 5.02 / 8.01 sections (stop at Item 9.01 / SIGNATURE).
    Forward-looking-statement boilerplate paragraphs are removed. If no operative Item heading is found -> UNRESOLVED_SOURCE.
 2. SENTENCES: split operative text; each sentence tagged CURRENT unless it carries a historical marker (sec 6) without an amendment verb,
    or is FUTURE_POSSIBILITY ('may enter', 'intends to', 'if'), or has no operative verb.
 3. transaction_type (sec 8): first CURRENT sentence that matches >=1 category anchor; within that sentence the earliest anchor wins,
    except specificity overrides listed in OVERRIDE (e.g. prepaid 4-component > ELOC > PIPE). Two different categories whose anchors are
    in the same sentence and not ordered by OVERRIDE -> earliest anchor (document order = primary). ELOC_OR_PREPAID_ADVANCE requires all four
    components (advance funding, equity settlement, market/VWAP pricing, facility) within the transaction window; phrase only -> not prepaid.
    NON_FINANCING only if no financing anchor in any CURRENT sentence AND an affirmative non-financing agreement anchor exists.
 4. is_dilutive (sec 25) computed independently of transaction_type from equity-issuance evidence in CURRENT sentences.
    FALSE only via EXHAUSTIVE_OPERATIVE_SCAN: complete operative scope, zero equity-issuance/conversion/settlement terms anywhere in it,
    plus an affirmative non-equity transaction anchor."""
import re, sys, json, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from common import norm, ev
VERSION = 'B2_RULE_V1.4'
ITEM = re.compile(r'(?i)item\s*(\d)\.\s?(\d\d)\b\.?')
OPERATIVE_ITEMS = {'1.01', '1.02', '2.03', '3.02', '3.03', '5.02', '8.01', '2.01'}
STOP = re.compile(r'(?i)(item\s*9\.\s?01|\bSIGNATURES?\b|pursuant to the requirements of the securities exchange act)')
XREF = re.compile(r'(?i)(exemption (?:from registration )?(?:provided|afforded) by|exempt from (?:the )?registration|in reliance (?:up)?on (?:the )?(?:exemption|section 4)|see item \d\.\d\d|is incorporated (?:herein )?by reference|qualified in its entirety by reference)')
FLS = re.compile(r'(?i)(forward[- ]looking statements?)[^.]{0,40}(within the meaning|are based|involve|this current report)')
HIST = re.compile(r'(?i)\b(as previously (?:disclosed|reported)|previously (?:entered|issued|disclosed|reported)|had (?:previously )?entered|formerly|historically|prior to (?:the date hereof))')
AMEND = re.compile(r'(?i)(?<!as )\b(amend(?:ed|ment|s)?|modif(?:y|ied|ication)|restat(?:e|ed))\b(?! and supplemented)')
FUTURE = re.compile(r'(?i)\b(may (?:in the future )?enter|intends? to (?:enter|seek|raise)|expects? to (?:enter|raise)|if the company (?:enters|elects)|there can be no assurance)')
OPV = re.compile(r'(?i)\b(entered into|enter into|executed|agreed to|agreed|issued|issue|sold|sell|offered|commenced|amended|terminated|closed|consummated|granted|approved|appointed|purchased|exchange[d]?|converted|received|delivered)\b')
C = lambda p: re.compile('(?i)' + p)
CAT = {
 'ATM_AGREEMENT': C(r'(at[- ]the[- ]market (?:offering |issuance )?(?:sales )?agreement|atm (?:sales |offering )?agreement|(?:equity )?distribution agreement|open market sale agreement|controlled equity offering|\bsales agreement\b)'),
 'ELOC': C(r'(equity purchase agreement|equity line|purchase notice|advance notice|committed equity facility|common stock purchase agreement|commit(?:ted|ment) to purchase up to)'),
 'ELOC_OR_PREPAID_ADVANCE': C(r'(pre-?paid advance|prepaid purchase|pre-?paid purchase)'),
 'WARRANT_INDUCEMENT': C(r'(inducement (?:letter|agreement|offer)|induce(?:ment)? (?:the )?(?:holders? )?to exercise|warrant exercise (?:inducement|agreement))'),
 'UNDERWRITTEN_OFFERING': C(r'(underwriting agreement)'),
 'REGISTERED_DIRECT': C(r'(registered direct offering|registered direct)'),
 'PIPE': C(r'(private placement|securities purchase agreement|subscription agreement|share subscription)'),
 'CONVERTIBLE_NOTE': C(r'(convertible (?:promissory )?notes?|convertible debentures?|senior secured convertible|convertible bonds?)'),
 'DEBT_CONVERSION': C(r'(exchange agreement|debt (?:conversion|exchange|settlement) agreement|in (?:full )?satisfaction of (?:the |all )?(?:outstanding )?(?:principal|indebtedness|amounts)|conversion of (?:the |its )?(?:outstanding )?(?:principal|notes?|debt))'),
 'EQUITY_FOR_ACQUISITION': C(r'(merger agreement|agreement and plan of merger|share exchange agreement|asset purchase agreement|stock purchase agreement|business combination agreement|membership interest purchase agreement|share purchase agreement|sale and purchase agreement)'),
 'EQUITY_COMPENSATION': C(r'(employment agreement|consulting agreement|restricted stock units?|stock options? to purchase|equity incentive plan|inducement grants?|compensation)'),
 'OTHER_FINANCING': C(r'(investment agreement|loan agreement|credit agreement|promissory note|term loan|loan and security agreement|note purchase agreement|financing agreement|revenue (?:interest|sharing) (?:purchase )?agreement|preferred stock purchase)'),
}
NONFIN = C(r'(lease agreement|license agreement|supply agreement|collaboration agreement|distribution and supply|services agreement|master services|joint venture|resign(?:ed|ation)|letter of intent|memorandum of understanding|settlement agreement|purchase order|cooperation agreement|strategic partnership)')
FIN_CATS = [k for k in CAT if k not in ('EQUITY_COMPENSATION',)]
# specificity overrides inside one sentence/window: winner beats losers regardless of position
OVERRIDE = [('ELOC_OR_PREPAID_ADVANCE', {'ELOC', 'PIPE', 'CONVERTIBLE_NOTE', 'OTHER_FINANCING'}), ('ELOC', {'PIPE', 'OTHER_FINANCING'}),
            ('WARRANT_INDUCEMENT', {'PIPE'}), ('REGISTERED_DIRECT', {'PIPE'}), ('UNDERWRITTEN_OFFERING', {'PIPE', 'REGISTERED_DIRECT'}),
            ('ATM_AGREEMENT', {'PIPE', 'OTHER_FINANCING'}), ('CONVERTIBLE_NOTE', {'PIPE', 'OTHER_FINANCING'}), ('DEBT_CONVERSION', {'OTHER_FINANCING', 'PIPE'})]
P_ADV = C(r'(pre-?paid advances?|advance(?:d)? (?:to the company |us )?(?:the )?(?:aggregate )?(?:principal )?amount|prepaid purchase)')
P_EQ = C(r'(convert(?:ible|ed)? into (?:shares|common)|shares of (?:the company\'s )?common stock|settle[d]? in shares|purchase shares)')
P_PX = C(r'(vwap|volume[- ]weighted average price|lowest daily|market price|percent of the|% of the (?:lowest|average))')
P_FAC = C(r'(standby equity purchase agreement|\bsepa\b|facility|pre-?paid advance agreement|equity purchase agreement)')
REFPRE = C(r'(that certain|related to|relating to|under the|pursuant to the|in connection with the|terms of the|of the)\s*(?:[A-Z][\w&,.]*\s){0,3}$')
BEST_EFFORTS_PUBLIC = C(r'(best[- ]efforts (?:public )?offering|(?:public|registered) offering[^.]{0,120}placement agent|public offering price)')
MONTHS = 'january|february|march|april|may|june|july|august|september|october|november|december'
DATE = C(r'(' + MONTHS + r')\s+(\d{1,2}),\s+(20\d\d)')
HIST_DAYS = 120
FUT_INTENT = C(r'(expected to|will |no later than|subject to|anticipated|scheduled to)')
ACQ_CTX = C(r'(acqui(?:re|red|sition)|merger|target company|the seller|sellers|membership interests|all of the (?:issued and )?outstanding|business combination|asset purchase)')
FIN_SIGNAL = C(r'(gross proceeds|net proceeds|aggregate purchase price|in exchange for (?:an aggregate )?\$|investment agreement|financing)')
ACQ_EQ = C(r'(shares of (?:the company\'s |its |our |acquiror |parent )?(?:class [ab] )?(?:common stock|ordinary shares|common shares)|consideration shares|preferred stock|share consideration|stock consideration|exchange shares)')
NONFIN_ACQ = C(r'(asset purchase agreement|merger agreement|agreement and plan of merger|stock purchase agreement|share purchase agreement)')
INSTRUMENT = C(r'(?P<conv>convertible (?:promissory )?notes?|convertible debentures?)|(?P<note>(?:senior )?(?:secured )?promissory notes?|(?:senior )?(?:secured )?notes? (?:in|with) (?:an|the) (?:aggregate )?(?:original )?principal)|(?P<eq>shares of (?:series [a-z]+ )?(?:convertible )?preferred stock|shares of (?:the company\'s )?common stock|pre-?funded warrants|ordinary shares)')
ATM_AGENT = C(r'(sales agents?|as (?:the )?agent|distribution agents?|agent and/or principal|as agent or principal)')
EQUITY = C(r'(shares of (?:the company\'s |its |our )?(?:class [ab] )?(?:common stock|ordinary shares|common shares)|pre-?funded warrants?|warrants? to purchase|convertible into|conversion shares|warrant shares|restricted stock|stock options?|issu(?:e|ed|ance of|able) [^.]{0,60}shares|preferred stock|ordinary shares|common stock)')
EQUITY_BLOCK = C(r'(\bunits?\b|equity interests?|ownership interest|warrants?|convertible|conversion|\bshares\b|\bstock\b|equity securities|exchangeable)')
NONEQ_DEBT = C(r'(loan agreement|credit agreement|term loan|promissory note|line of credit|loan and security agreement|revolving)')
SENT = re.compile(r'(?<=[.;])\s+(?=[A-Z•●])')
ABBR = re.compile(r'(?i)(?:\b(?:inc|corp|ltd|co|no|nos|mr|ms|mrs|dr|jr|sr|st|u\.s|l\.l\.c|l\.p|s\.a|n\.v|b\.v|plc|llc|lp|vs|approx|sec|n\.a)|\b[A-Z])\.$')

def scope(t):
    """Return list of (start,end) spans of operative Items; excludes FLS boilerplate."""
    heads = [(m.start(), m.group(1) + '.' + m.group(2)) for m in ITEM.finditer(t)]
    stop = STOP.search(t, heads[0][0] + 10 if heads else 0)
    spans = []
    for i, (s, it) in enumerate(heads):
        e = heads[i + 1][0] if i + 1 < len(heads) else (stop.start() if stop else len(t))
        if stop and s >= stop.start(): break
        if stop: e = min(e, stop.start())
        if it in OPERATIVE_ITEMS and e - s > 60: spans.append((s, e, it))
    return spans

def sentences(t, spans, known_at=None):
    import datetime as _d
    ka = _d.date.fromisoformat(known_at[:10]) if known_at else None
    MI = {m: i + 1 for i, m in enumerate(MONTHS.split('|'))}
    out = []
    for s, e, it in spans:
        seg = t[s:e]; pos = 0; raw = SENT.split(seg); merged = []
        for p in raw:
            if merged and ABBR.search(merged[-1]): merged[-1] = merged[-1] + ' ' + p
            else: merged.append(p)
        for piece in merged:
            k = seg.find(piece, pos); pos = k + len(piece)
            if FLS.search(piece): continue
            st = 'CURRENT'
            if XREF.search(piece) and not re.search(r'(?i)entered into', piece): st = 'CROSS_REFERENCE_OR_EXEMPTION_BOILERPLATE'
            elif FUTURE.search(piece): st = 'FUTURE_POSSIBILITY'
            elif HIST.search(piece) and not AMEND.search(piece): st = 'HISTORICAL_REFERENCE'
            elif ka and DATE.search(piece) and not AMEND.search(piece) and not FUT_INTENT.search(piece) and all((ka - _d.date(int(y), MI[mo.lower()], min(int(d), 28))).days > HIST_DAYS for mo, d, y in DATE.findall(piece)): st = 'HISTORICAL_REFERENCE_DATE_CONTEXT'
            elif not OPV.search(piece): st = 'NO_OPERATIVE_VERB'
            out.append((s + k, piece, st, it))
    return out

class Sp:
    def __init__(s, a, b): s.a, s.b = a, b
    def start(s): return s.a
    def end(s): return s.b

def classify(t, sents, acc, doc):
    cur = [x for x in sents if x[2] == 'CURRENT']; pending_nf = None
    for off, s, st, it in cur:
        if pending_nf is not None and not any(CAT[k].search(s) for k in FIN_CATS): continue
        hits = {}
        for k, r in CAT.items():
            for m in r.finditer(s):
                if REFPRE.search(s[max(0, m.start() - 60):m.start()]) and not re.search(r'(?i)(entered into|enter into|executed)\s+(?:an? |the )?(?:[A-Z][\w&,.]*\s){0,4}$', s[max(0, m.start() - 60):m.start()]): continue
                hits[k] = m; break
        if not hits: continue
        if set(hits) == {'EQUITY_COMPENSATION'} and it not in ('5.02', '3.02', '1.01', '8.01'): continue
        win = t[off:off + 2500]
        if 'ELOC_OR_PREPAID_ADVANCE' in hits or P_ADV.search(s):
            comps = {k: bool(r.search(win)) for k, r in (('advance_funding', P_ADV), ('equity_settlement', P_EQ), ('market_vwap_pricing', P_PX), ('facility', P_FAC))}
            if all(comps.values()): hits.setdefault('ELOC_OR_PREPAID_ADVANCE', P_ADV.search(win) and Sp(P_ADV.search(win).start() - off, P_ADV.search(win).end() - off) or P_ADV.search(s))
            else: hits.pop('ELOC_OR_PREPAID_ADVANCE', None)
        else: comps = None
        if 'ATM_AGREEMENT' in hits and not ATM_AGENT.search(win): hits.pop('ATM_AGREEMENT')
        w800 = t[off:off + len(s) + 800]
        if 'EQUITY_FOR_ACQUISITION' in hits and ACQ_EQ.search(w800) and not ACQ_CTX.search(w800) and re.search(r'(?i)stock purchase agreement|share purchase agreement|sale and purchase agreement', hits['EQUITY_FOR_ACQUISITION'].group(0) if hasattr(hits['EQUITY_FOR_ACQUISITION'],'group') else ''):
            hits['PIPE'] = hits.pop('EQUITY_FOR_ACQUISITION')
        if 'EQUITY_FOR_ACQUISITION' in hits and not ACQ_EQ.search(w800):
            hits.pop('EQUITY_FOR_ACQUISITION')
            if not hits: hits['NON_FINANCING'] = NONFIN_ACQ.search(s) or CAT['EQUITY_FOR_ACQUISITION'].search(s)
        if 'PIPE' in hits and BEST_EFFORTS_PUBLIC.search(w800) and not ({'REGISTERED_DIRECT', 'UNDERWRITTEN_OFFERING'} & set(hits)):
            hits['OTHER_FINANCING'] = Sp(BEST_EFFORTS_PUBLIC.search(w800).start() - off, BEST_EFFORTS_PUBLIC.search(w800).end() - off); hits.pop('PIPE')
        if 'PIPE' in hits and not ({'CONVERTIBLE_NOTE', 'REGISTERED_DIRECT', 'ELOC_OR_PREPAID_ADVANCE', 'ELOC', 'WARRANT_INDUCEMENT'} & set(hits)):
            inst = INSTRUMENT.search(w800)
            if inst:
                k = 'CONVERTIBLE_NOTE' if inst.group('conv') else ('OTHER_FINANCING' if inst.group('note') else None)
                if k: hits[k] = Sp(inst.start() - off, inst.end() - off); hits.pop('PIPE')
        if 'ELOC' in hits and 'ELOC_OR_PREPAID_ADVANCE' not in hits and not C(r'(commit|right, but not the obligation|purchase notice|advance notice|from time to time|equity line)').search(win): hits.pop('ELOC')
        if not hits: continue
        live = set(hits)
        for w, losers in OVERRIDE:
            if w in live: live -= (losers - {w})
        if len(live) > 1 and 'EQUITY_COMPENSATION' in live: live.discard('EQUITY_COMPENSATION')
        best = min(live, key=lambda k: hits[k].start())
        if best == 'NON_FINANCING':
            if pending_nf is None: pending_nf = (off, hits[best], it)
            continue
        m = hits[best]
        e = ev(acc, doc, 'B2_TT_' + best, t, Sp(off + m.start(), off + m.end()))
        res = {'value': best, 'status': 'RESOLVED_RULE', 'rule_id': 'B2_TT_PRIMARY_FIRST_CURRENT_' + best, 'temporal_scope': 'CURRENT_TRANSACTION',
               'item': it, 'is_amendment_context': bool(AMEND.search(s)), 'evidence': [e], 'competing_anchors_in_sentence': sorted(set(hits) - {best})}
        if comps is not None: res['prepaid_four_component_test'] = comps
        res['secondary_current_anchor_categories'] = sorted({k for o2, s2, st2, _ in cur if o2 > off for k, r in CAT.items() if r.search(s2)} - {best})
        return res
    fin_any = any(CAT[k].search(s) for _, s, st, _ in sents for k in FIN_CATS)
    fin_sig = any(FIN_SIGNAL.search(s) for _, s, _, _ in cur)
    if pending_nf is not None and not fin_sig:
        o, m, it = pending_nf
        return {'value': 'NON_FINANCING', 'status': 'RESOLVED_RULE', 'rule_id': 'B2_TT_NON_FINANCING_ACQUISITION_NO_EQUITY_CONSIDERATION', 'item': it,
                'negative_evidence_method': 'NO_EQUITY_CONSIDERATION_IN_WINDOW_AND_NO_LATER_CURRENT_FINANCING_ANCHOR', 'evidence': [ev(acc, doc, 'B2_TT_NON_FINANCING', t, Sp(o + m.start(), o + m.end()))]}
    nf = [(o, s) for o, s, st, _ in cur if NONFIN.search(s)]
    if nf and not fin_sig and pending_nf is None and not any(CAT[k].search(s) for _, s, st, _ in cur for k in FIN_CATS):
        o, s = nf[0]; m = NONFIN.search(s)
        return {'value': 'NON_FINANCING', 'status': 'RESOLVED_RULE', 'rule_id': 'B2_TT_NON_FINANCING_AFFIRMATIVE', 'negative_evidence_method': 'COMPLETE_OPERATIVE_SCOPE_NO_FINANCING_ANCHOR_IN_CURRENT_SENTENCES',
                'evidence': [ev(acc, doc, 'B2_TT_NON_FINANCING', t, Sp(o + m.start(), o + m.end()))]}
    return {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_INSUFFICIENT_CONTEXT' if fin_any else 'UNRESOLVED_NO_EVIDENCE', 'rule_id': 'B2_TT_NONE', 'evidence': []}

def dilutive(t, sents, acc, doc):
    cur = [x for x in sents if x[2] == 'CURRENT']
    for o, s, st, it in cur:
        m = EQUITY.search(s)
        if m and OPV.search(s):
            return {'value': 'TRUE', 'status': 'RESOLVED_RULE', 'rule_id': 'B2_DIL_T1_CURRENT_EQUITY_ISSUANCE', 'evidence': [ev(acc, doc, 'B2_DIL_T1', t, Sp(o + m.start(), o + m.end()))]}
    any_eq = any(EQUITY.search(s) for _, s, _, _ in sents)
    if not any_eq and not any(EQUITY_BLOCK.search(s) for _, s, st, _ in sents if st not in ('CROSS_REFERENCE_OR_EXEMPTION_BOILERPLATE',)):
        for o, s, st, it in cur:
            m = NONEQ_DEBT.search(s) or NONFIN.search(s)
            if m: return {'value': 'FALSE', 'status': 'RESOLVED_RULE', 'rule_id': 'B2_DIL_F_EXHAUSTIVE_NO_EQUITY_TERMS', 'negative_evidence_method': 'EXHAUSTIVE_OPERATIVE_SCAN_ZERO_EQUITY_TERMS_PLUS_AFFIRMATIVE_NON_EQUITY_TRANSACTION',
                          'evidence': [ev(acc, doc, 'B2_DIL_F', t, Sp(o + m.start(), o + m.end()))]}
    return {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_INSUFFICIENT_CONTEXT' if any_eq else 'UNRESOLVED_NO_EVIDENCE', 'rule_id': 'B2_DIL_NONE', 'evidence': []}

def extract(path, acc, doc, known_at=None):
    t = norm(path); sp = scope(t)
    out = {'accession': acc, 'document': doc, 'extractor_version': VERSION, 'source_sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(), 'operative_items': [x[2] for x in sp]}
    if not sp:
        u = {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_SOURCE', 'rule_id': 'B2_NO_OPERATIVE_ITEM', 'evidence': []}
        out['transaction_type'] = dict(u); out['is_dilutive'] = dict(u); return out
    ss = sentences(t, sp, known_at)
    out['transaction_type'] = classify(t, ss, acc, doc); out['is_dilutive'] = dilutive(t, ss, acc, doc)
    return out

if __name__ == '__main__':
    import argparse; ap = argparse.ArgumentParser(allow_abbrev=False); ap.add_argument('--artifact', required=True); ap.add_argument('--out', required=True); A = ap.parse_args()
    man = json.load(open(os.path.join(A.artifact, 'sha256-manifest.json'))); docs = man['documents'] if isinstance(man, dict) else man
    res = [extract(os.path.join(A.artifact, d['path']), d['accession'], d['path'], d.get('known_at')) for d in sorted(docs, key=lambda d: d['accession'])]
    b = json.dumps({'extractor': VERSION, 'records': res}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(); open(A.out, 'wb').write(b)
    print(len(res), hashlib.sha256(b).hexdigest())
