#!/usr/bin/env python3
"""PRODUCT-1B-1E full historical replay (REGRESSION_REPLAY, not a benchmark rerun; no new precision/recall/thresholds/claims).
Fixture A FEB_GOLD_TIER_REPRODUCTION : collector-format bundles via sec_collector_v1 (fake transport) -> supply_targets_v1 assessability
                                        -> frozen gold/reference labels -> supply_tier_v2.tier   (285 records incl. UNASSESSABLE)
Fixture B FEB_EXTRACTOR_INTEGRATION_REPLAY : per trading date, full production path: collect -> targets -> ephemeral retrieval -> frozen
                                        extractors (python3.13 -I) -> labels -> tier -> joint assessment -> manifest_builder.build.
Inputs are already-open research bytes only. Network blocked."""
import sys, os, re, json, hashlib, collections, socket
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.realpath(os.path.join(HERE, '..', 'src')); sys.path.insert(0, SRC); sys.path.insert(0, HERE)
NET = {'attempts': 0}
def _no_net(*a, **k): NET['attempts'] += 1; raise OSError('NETWORK_BLOCKED')
socket.socket.connect = _no_net; socket.create_connection = _no_net
import sec_collector_v1 as SC, supply_targets_v1 as TG, supply_tier_v2 as TV, supply_pipeline_v1 as PL, manifest_builder_v1 as MB
from test_1b1d_support import Fake, Clock, PATHS, FROZEN, identities, REG, REG_SHA, SECRET, A, J, FB, REPO, PY, canon
U = json.load(open(f'{A}/oos/feb_pub/universe.json'))
BUND = {}
for f in sorted(os.listdir(f'{A}/sec_feb/x/raw')):
    d = json.load(open(f'{A}/sec_feb/x/raw/{f}')); BUND[str(d['cik']).zfill(10)] = d
DOCS = {}
for base in (f'{A}/b1/x', f'{A}/b2/x', f'{A}/feb_docs/b1', f'{A}/feb_docs/b2'):
    m = json.load(open(f'{base}/sha256-manifest.json')); m = m['documents'] if isinstance(m, dict) else m
    for e in m:
        if e['path'].startswith('raw/') and e.get('accession'): DOCS.setdefault(e['accession'].replace('-', ''), open(f'{base}/{e["path"]}', 'rb').read())
GOLD = {(r['ticker'], r['trading_date']): r['tier'] for r in json.load(open(f'{A}/claude_feb/FEB_SUPPLY_RISK_TIER_V2_FROZEN.json'))['records']}
REP = {(r['ticker'], r['trading_date']): r for r in json.load(open(f'{FB}/PRODUCT_1A_FEB_BENCHMARK_V1.json'))['occurrences']}
def gold_labels():
    b1 = {r['accession']: r for r in json.load(open(f'{A}/b1_frozen.json'))['records']}
    b2 = {r['accession']: r for r in json.load(open(f'{A}/b2_frozen.json'))['records']}
    for r in json.load(open(f'{A}/claude_feb/ADJ_B1_FEB_NEW.json')): b1[r['accession']] = r
    for r in json.load(open(f'{A}/claude_feb/ADJ_B2_FEB_NEW.json')): b2[r['accession']] = r
    return b1, b2
def run():
    PL.verify_identities(PATHS, FROZEN)
    by_date = collections.defaultdict(list)
    for o in U: by_date[o['prediction_cutoff']].append(o)
    g1, g2 = gold_labels(); recA, recB, day_sha, audit_tot = [], [], {}, collections.Counter()
    for cut in sorted(by_date):
        occ = by_date[cut]; tick = [o['ticker'] for o in occ]
        tr = json.dumps({str(i): {'cik_str': int(o['cik']), 'ticker': o['ticker'], 'title': 'X'} for i, o in enumerate(occ) if o['cik']}, sort_keys=True).encode()
        fake = Fake(BUND, DOCS, tr); clk = Clock(); c = SC.SecClient(SECRET, transport=fake, clock=clk, sleep=clk.sleep)
        res = SC.collect(c, tick, cut)
        with SC.EphemeralWorkspace(REPO) as ws:
            d1, f1 = SC.retrieve_documents(c, res['b1_targets'], ws.path, 'b1', False); SC.verify_input_contract(d1, False)
            d2, f2 = SC.retrieve_documents(c, res['b2_targets'], ws.path, 'b2', True); SC.verify_input_contract(d2, True)
            x1 = PL.run_extractor(PY, PATHS['b1_deterministic_extractor.py'], d1, os.path.join(ws.path, 'o1.json'))
            x2 = PL.run_extractor(PY, PATHS['b2_deterministic_extractor.py'], d2, os.path.join(ws.path, 'o2.json'))
        iss, aud = PL.assemble_issuers(res['collection'], res['bundles'], x1 + PL.source_failure_records(f1, 'b1'), x2 + PL.source_failure_records(f2, 'b2'), cut)
        audit_tot.update(aud); audit_tot['RETRIEVAL_FAILURES'] += len(f1) + len(f2)
        w, psha = MB.build(cut, {'source_path': 'FIXTURE_FEB_UNIVERSE', 'source_sha256': 'FIXTURE', 'tickers': tick},
                           {'source': SC.TICKERS_URL, 'source_sha256': res['collection']['cik_mapping_source_sha256']}, iss, identities(), REG, REG_SHA, {'trigger': 'replay'})
        day_sha[cut] = psha; man = {r['ticker']: r for r in json.loads(w)['decision_payload']['records']}
        for o in occ:
            k = (o['ticker'], o['trading_date']); info = res['collection']['issuers'][o['ticker'].strip().upper()]; m_ = man[o['ticker'].strip().upper()]
            # Fixture A: gold labels through production tier with collector-format bundle
            tA = 'UNASSESSABLE' if info['unassessable_reason'] else TV.tier(cut, TV.tier_filings(res['bundles'][o['ticker'].strip().upper()]), g1, g2)[0]
            recA.append({'ticker': o['ticker'], 'trading_date': o['trading_date'], 'replay_tier': tA, 'gold_tier': GOLD[k]})
            a = iss[o['ticker'].strip().upper()].get('assessment')
            recB.append({'ticker': o['ticker'], 'trading_date': o['trading_date'], 'gold_tier': GOLD[k], 'computed_tier': m_['computed_tier'], 'assessment_status': m_['assessment_status'],
                         'trigger_rule': a['trigger_rule'] if a else None, 'trigger_accessions': a['trigger_accessions'] if a else [], 'worst_case_tier': a['worst_case_tier'] if a else None,
                         'unassessable_reason': info['unassessable_reason']})
    nA = len(recA); mA = sum(r['replay_tier'] == r['gold_tier'] for r in recA)
    fa = {'fixture_id': 'FEB_GOLD_TIER_REPRODUCTION', 'total_n': nA, 'matched_n': mA, 'denominator_n': nA, 'denominator_scope': 'ALL_RECORDS_INCL_UNASSESSABLE', 'exact_match_rate': mA / nA}
    asb = [r for r in recB if r['assessment_status'] != 'UNASSESSABLE']; mB = sum(r['computed_tier'] == r['gold_tier'] for r in asb)
    fb = {'fixture_id': 'FEB_EXTRACTOR_INTEGRATION_REPLAY', 'total_n': len(recB), 'assessable_n': len(asb), 'unassessable_n': len(recB) - len(asb), 'matched_n': mB,
          'denominator_n': len(asb), 'denominator_scope': 'ASSESSABLE_ONLY', 'exact_match_rate': mB / len(asb),
          'gold_dist': dict(sorted(collections.Counter(r['gold_tier'] for r in recB).items())), 'computed_dist': dict(sorted(collections.Counter(r['computed_tier'] for r in recB).items())),
          'assessment_dist': dict(sorted(collections.Counter(r['assessment_status'] for r in recB).items()))}
    cmp_ = lambda r, q: ((r['computed_tier'] if r['assessment_status'] != 'UNASSESSABLE' else None), r['assessment_status'], r['trigger_rule'], r['trigger_accessions'], r['worst_case_tier']) == \
                        (q['computed_tier'], q['assessment_status'], q.get('trigger_rule'), q.get('trigger_accessions', []), q.get('riskiest_resolution_tier'))
    mism = [[r['ticker'], r['trading_date']] for r in recB if not cmp_(r, REP[(r['ticker'], r['trading_date'])])]
    return {'fixture_a': fa, 'fixture_b': fb, 'assessment_replay': {'compared_n': len(recB), 'exact_n': len(recB) - len(mism), 'mismatch': mism},
            'audit': dict(sorted(audit_tot.items())), 'daily_decision_payload_sha256': day_sha, 'records_a': recA, 'records_b': recB}
if __name__ == '__main__':
    out = run(); out['net_attempts'] = NET['attempts']; b = canon(out); print(json.dumps({'sha256': hashlib.sha256(b).hexdigest(), 'net_attempts': NET['attempts']}))
    open(sys.argv[1], 'wb').write(b)
