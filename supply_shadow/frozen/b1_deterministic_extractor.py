#!/usr/bin/env python3
"""PRODUCT-1 V1 B1 deterministic extractor (424B5).
Spec: PRODUCT-1A-0 v1.0.0 sec 9 + ERRATA_10_2_V1 + PRE_EXTRACTOR_DECISIONS_V1. No LLM, no outcome data, no per-accession tables.
is_atm (sec 9.1 'relevant offering/facility'):
  TRUE  B1_ATM_T1_CURRENT_OFFERING : cover section of current offering has ATM mechanism + agent + from-time-to-time.
  TRUE  B1_ATM_T2_EXISTING_FACILITY: anywhere in doc, a NAMED ATM-type agreement with concrete execution language (entered into / dated) within
                                     250 chars, agent + from-time-to-time within a 700-char window, not inside base-prospectus method-list boilerplate
                                     (Rule 415(a)(4) / 'we may sell the securities through...'), and no termination/exhaustion language in that window.
  FALSE B1_ATM_F_<STRUCT>          : no live facility found AND cover affirmatively identifies a non-ATM current structure (sec 9.2).
  FALSE B1_ATM_F_TERMINATED        : facility windows found but every one carries termination/expiry/exhaustion language, and cover is non-ATM.
  else UNRESOLVED (absence of ATM keyword alone never yields FALSE).
baby_shelf_limited: FROZEN_B1_IB6_LIMITATION_FLAG (ERRATA_10_2_V1): TRUE iff an operative reference to General Instruction I.B.6 (S-3) /
  I.B.5 (F-3) appears within 400 chars of limitation language (one-third / baby shelf / limits the amount / sales limitations / offering
  limits), INCLUDING 'no longer subject' statements per errata; otherwise UNRESOLVED (never FALSE). Current applicability deferred to B3."""
import re, sys, json, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from common import norm, ev
VERSION = 'B1_RULE_V1.4'; COVER_CHARS = 4000; WIN = 700
ATM_MECH = re.compile(r'(?i)(at[- ]the[- ]market|at market issuance|sales agreement|equity distribution agreement|controlled equity offering|atm (?:sales |offering )?agreement|open market sale agreement|equity offering sales agreement|distribution agreement)')
AGENT = re.compile(r'(?i)(sales agents?|as (?:our |the )?(?:sales )?agent|acting as (?:our |the )?(?:sales )?agent|as agent or principal|agent and/or principal|distribution agents?|"agent"|through (?:the )?agents?)')
FTT = re.compile(r'(?i)(from time[- ]to[- ]time|at[- ]the[- ]market offerings?|ordinary brokers?\'? transactions)')
FAC_AGMT = re.compile(r'(?i)(at[- ]the[- ]market (?:offering |issuance )?(?:sales )?agreement|atm (?:sales |offering )?agreement|(?:equity )?(?:sales|distribution|equity distribution|open market sale|capital on demand|controlled equity offering) (?:sales )?agreement)')
CONCRETE = re.compile(r'(?i)(entered into|previously entered|that certain|pursuant to the terms of|dated (?:as of )?[A-Z][a-z]+ \d|(?:on|as of) [A-Z][a-z]+ \d{1,2}, \d{4})')
BOILER = re.compile(r'(?i)(within the meaning of Rule 415\(a\)\(4\)|we may sell (?:the )?securities (?:to or )?(?:through|directly)|in one or more of the following ways|any of the following methods|through underwriters or dealers)')
EXIST = re.compile(r'(?i)(entered into|dated (?:as of )?[A-Z][a-z]+ \d|previously entered|have an?|existing|pursuant to (?:the|our|that certain) [^.]{0,60}agreement|remain(?:s|ed)? available|under the (?:atm |sales |equity distribution )?(?:sales )?agreement)')
TERM = re.compile(r'(?i)(terminat(?:ed|ion of)|expired|no longer (?:available|in effect)|fully (?:utilized|exhausted|sold)|has been exhausted|sold all|ceased|will not (?:make any further )?(?:sell|sales))')
HYPO = re.compile(r'(?i)\b(may (?:in the future )?(?:enter|establish)|could|if we (?:enter|sell)|future (?:at[- ]the[- ]market|atm))')
RESALE = re.compile(r'(?i)(relates to the (?:offer and )?resale|by the selling (?:stock|share)holders?|selling (?:stock|share)holders? (?:named|identified)|the selling (?:stock|share)holders[^.]{0,80}may offer)')
UW = re.compile(r'(?i)(underwriting agreement|firm commitment|underwritten (?:public )?offering|as (?:the )?(?:sole |lead )?(?:book[- ]running )?(?:manager|representative)s? of the (?:several )?underwriters)')
RD = re.compile(r'(?i)(registered direct offering|directly to (?:certain )?(?:institutional |accredited )?(?:investors?|purchasers?)|securities purchase agreement)')
PA = re.compile(r'(?i)(exclusive placement agent|placement agent (?:has agreed|is not purchasing|has no obligation)|reasonable best efforts|best efforts basis)')
FIXED = re.compile(r'(?i)((?:public )?offering price (?:is|of|for each)|at a (?:public )?offering price of|purchase price (?:for|of) (?:the|each)|at a price of \$|sold at a price of)')
ELOC = re.compile(r'(?i)(standby equity purchase agreement|pre-?paid advance agreement|equity line of credit|common stock purchase agreement with)')
CONSID = re.compile(r'(?i)(issued (?:only )?(?:as|in) consideration|will not receive any proceeds)')
NEG = [('RESALE', RESALE), ('UNDERWRITTEN', UW), ('REGISTERED_DIRECT', RD), ('BEST_EFFORTS_PLACEMENT', PA), ('FIXED_PRICE', FIXED), ('NON_CASH_CONSIDERATION', CONSID), ('ELOC_OR_PREPAID', ELOC)]
IB = re.compile(r'(?i)General Instruction I\.B\.(6|5)')
THIRD = re.compile(r'(?i)(one[- ]third|1/3|baby shelf|limit(?:s|ed|ation|ations)? (?:on )?(?:the )?(?:amount|sales|offering)|sales limitations|offering limits|which limits)')

class Off:
    def __init__(s, m, o): s.m, s.o = m, o
    def start(s): return s.m.start() + s.o
    def end(s): return s.m.end() + s.o

def facilities(t):
    """Return list of (window_start, mech_match, terminated_flag) for ATM facility windows across the full document."""
    out = []; last = -10**9
    for m in FAC_AGMT.finditer(t):
        if m.start() - last < WIN // 2: continue
        s = max(0, m.start() - WIN // 2); w = t[s:m.end() + WIN // 2]; near = t[max(0, m.start() - 250):m.end() + 250]
        if AGENT.search(w) and FTT.search(w) and CONCRETE.search(near) and not BOILER.search(near) and not HYPO.search(t[max(0, m.start() - 120):m.end() + 40]):
            out.append((s, m, bool(TERM.search(w)))); last = m.start()
    return out

def extract(path, acc, doc):
    t = norm(path); m0 = re.search(r'(?i)filed pursuant to', t); c0 = m0.start() if m0 else 0
    cov = t[c0:c0 + COVER_CHARS]
    out = {'accession': acc, 'document': doc, 'extractor_version': VERSION, 'source_sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(), 'cover_marker_found': bool(m0)}
    a, g, f = ATM_MECH.search(cov), AGENT.search(cov), FTT.search(cov)
    neg = sorted([(r.search(cov).start(), n, r.search(cov)) for n, r in NEG if r.search(cov)])
    fac = facilities(t); live = [x for x in fac if not x[2]]
    if a and g and f and not (neg and neg[0][0] < a.start()):
        out['is_atm'] = {'value': 'TRUE', 'status': 'RESOLVED_RULE', 'rule_id': 'B1_ATM_T1_CURRENT_OFFERING', 'temporal_scope': 'CURRENT_OFFERING',
                         'evidence': [ev(acc, doc, 'B1_ATM_MECH', t, Off(a, c0)), ev(acc, doc, 'B1_ATM_AGENT', t, Off(g, c0)), ev(acc, doc, 'B1_ATM_FTT', t, Off(f, c0))]}
    elif live:
        out['is_atm'] = {'value': 'TRUE', 'status': 'RESOLVED_RULE', 'rule_id': 'B1_ATM_T2_EXISTING_FACILITY', 'temporal_scope': 'EXISTING_FACILITY_NOT_TERMINATED',
                         'evidence': [ev(acc, doc, 'B1_ATM_T2_EXISTING_FACILITY', t, x[1]) for x in live[:3]]}
    elif neg and fac:
        out['is_atm'] = {'value': 'FALSE', 'status': 'RESOLVED_RULE', 'rule_id': 'B1_ATM_F_TERMINATED', 'negative_evidence_method': 'REFERENCED_FACILITY_TERMINATED_AND_CURRENT_NON_ATM',
                         'evidence': [ev(acc, doc, 'B1_ATM_F_TERMINATED', t, x[1]) for x in fac[:3]] + [ev(acc, doc, 'B1_ATM_F_' + neg[0][1], t, Off(neg[0][2], c0))]}
    elif neg:
        _, n, m = neg[0]
        out['is_atm'] = {'value': 'FALSE', 'status': 'RESOLVED_RULE', 'rule_id': 'B1_ATM_F_' + n, 'negative_evidence_method': 'AFFIRMATIVE_NON_ATM_CURRENT_STRUCTURE_AND_NO_LIVE_FACILITY',
                         'evidence': [ev(acc, doc, 'B1_ATM_F_' + n, t, Off(m, c0))]}
    else:
        out['is_atm'] = {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_INSUFFICIENT_CONTEXT', 'rule_id': 'B1_ATM_NONE', 'evidence': []}
    hit = None
    for m in IB.finditer(t):
        if THIRD.search(t[max(0, m.start() - 400): m.end() + 400]): hit = m; break
    out['baby_shelf_limited'] = ({'value': 'TRUE', 'status': 'RESOLVED_RULE', 'rule_id': 'B1_BS_T1_IB_THIRD', 'evidence': [ev(acc, doc, 'B1_BS_T1_IB_THIRD', t, hit)]} if hit else
                                 {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_NO_EVIDENCE', 'rule_id': 'B1_BS_NONE', 'evidence': []})
    return out

if __name__ == '__main__':
    import argparse; ap = argparse.ArgumentParser(allow_abbrev=False); ap.add_argument('--artifact', required=True); ap.add_argument('--out', required=True); A = ap.parse_args()
    man = json.load(open(os.path.join(A.artifact, 'sha256-manifest.json'))); docs = man['documents'] if isinstance(man, dict) else man
    res = [extract(os.path.join(A.artifact, d['path']), d['accession'], d['path']) for d in sorted(docs, key=lambda d: d['accession'])]
    b = json.dumps({'extractor': VERSION, 'records': res}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(); open(A.out, 'wb').write(b)
    print(len(res), hashlib.sha256(b).hexdigest())
