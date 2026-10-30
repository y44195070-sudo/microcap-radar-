"""PRODUCT-1B-1B manifest builder (SUPPLY_SHADOW_MANIFEST_V1, schema 1.0.0). Assembly only: never re-derives tier/assessment/field
values; field_authority comes only from field_validation_registry_v1.json. Hard-fails raise ManifestBuildError(code)."""
import json, hashlib, os
from supply_tier_v2 import ACTIVE_B2
SCHEMA_ID, SCHEMA_VERSION = 'SUPPLY_SHADOW_MANIFEST_V1', '1.0.0'
TIER_MODE, VALIDATION_STATUS, COMPUTATION_MODE = 'SHADOW_DETERMINISTIC_V1', 'SHADOW_ONLY', 'AS_COMPUTED_THEN'
UNIVERSE_SCOPE = 'TRACKED_TICKERS_NOT_RESEARCH_TOP15_DECLINERS'
TIERS = {'CRITICAL', 'HIGH', 'MODERATE', 'LOW', 'UNASSESSABLE'}; STATUSES = {'RESOLVED', 'REVIEW_REQUIRED', 'UNASSESSABLE'}
UNASSESSABLE_REASONS = {'CIK_MAPPING_FAILURE', 'SEC_SOURCE_FAILURE', 'NULL_CIK', 'SEC_ROOT_FAILED', 'INCOMPLETE_HISTORY_INSUFFICIENT_90D_COVERAGE'}
EVIDENCE_TEXT_MAX_CHARS = 320
REASON = {'CRITICAL(A,B)': 'ACTIVE_SUPPLY_90D_PLUS_OFFERING_READINESS_30D', 'HIGH_RULE_1': 'ACTIVE_SUPPLY_90D', 'HIGH_RULE_2': 'PIPE_RD_90D',
          'HIGH_RULE_3': 'BABY_SHELF_PLUS_RECENT_OFFERING', 'MODERATE_RULE_1': 'DILUTIVE_B2_90D', 'MODERATE_RULE_2': 'EFFECT_90D', 'MODERATE_RULE_3': '424B5_90D'}
REG_KEY = {('B1', 'is_atm'): 'B1_IS_ATM', ('B1', 'baby_shelf_limited'): 'B1_BABY_SHELF', ('B2', 'transaction_type'): 'B2_TRANSACTION_TYPE',
           ('B2', 'active_supply'): 'B2_ACTIVE_SUPPLY', ('B2', 'pipe_rd'): 'B2_PIPE_RD', ('B2', 'is_dilutive'): 'B2_IS_DILUTIVE'}
REQUIRED_IDENTITIES = ['common.py', 'b1_deterministic_extractor.py', 'b2_deterministic_extractor.py', 'EXTRACTOR_CONFIG_V1.json', 'supply_3a1_v1.py', 'supply_targets_v1.py',
                       'supply_tier_v2.py', 'supply_assessment_v1.py', 'field_validation_registry_v1.json', 'calendar_engine_v1.py', 'calendar_data_v1.json', 'manifest_builder_v1.py',
                       'PRODUCT_1B_0_SHADOW_DEPLOYMENT_SPEC.json']
RUN_METADATA_KEYS = {'generated_at', 'workflow_run_id', 'workflow_run_attempt', 'workflow_commit_sha', 'publication_commit_sha', 'trigger', 'retry_counters', 'cik_mapping_retrieved_at'}
class ManifestBuildError(Exception): pass
canon = lambda o: json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def _fail(code): raise ManifestBuildError(code)
def _norm(t): return t.strip().upper()
def _short(s): return None if s is None else s[:EVIDENCE_TEXT_MAX_CHARS]
def _field(reg, set_, f, value, status, rule_id, accession, form, known_at, evidence_text):
    e = reg['fields'][REG_KEY[(set_, f)]]
    return {'set': set_, 'field': f, 'accession': accession, 'form': form, 'known_at': known_at, 'value': value, 'extraction_status': status, 'rule_id': rule_id,
            'field_authority': e['field_authority'], 'production_authoritative': False, 'evidence_text': _short(evidence_text)}
def _first_ev(x): return x['evidence'][0]['evidence_text'] if x.get('evidence') else None
def _fields_for(reg, acc_meta, b1r, b2r):
    """acc_meta: {acc: {'form','known_at'}} for accessions in 90d window. b1r/b2r: extractor records keyed by accession."""
    out = []
    for acc in sorted(acc_meta):
        m = acc_meta[acc]
        if acc in b1r:
            r = b1r[acc]
            for f in ('is_atm', 'baby_shelf_limited'):
                out.append(_field(reg, 'B1', f, r[f]['value'], r[f]['status'], r[f]['rule_id'], acc, m['form'], m['known_at'], _first_ev(r[f])))
        if acc in b2r:
            r = b2r[acc]; tt = r['transaction_type']
            out.append(_field(reg, 'B2', 'transaction_type', tt['value'], tt['status'], tt['rule_id'], acc, m['form'], m['known_at'], _first_ev(tt)))
            for f, S in (('active_supply', ACTIVE_B2), ('pipe_rd', {'PIPE', 'REGISTERED_DIRECT'})):  # projections = frozen tier sets (supply_tier_v2)
                v = 'UNRESOLVED' if tt['value'] == 'UNRESOLVED' else ('TRUE' if tt['value'] in S else 'FALSE')
                out.append(_field(reg, 'B2', f, v, tt['status'], tt['rule_id'], acc, m['form'], m['known_at'], None))
            d = r['is_dilutive']
            out.append(_field(reg, 'B2', 'is_dilutive', d['value'], d['status'], d['rule_id'], acc, m['form'], m['known_at'], _first_ev(d)))
    return out
def build_record(reg, ticker, prediction_cutoff, issuer):
    """issuer: {'unassessable_reason': str} OR {'cik','sec_status','assessment' (supply_assessment_v1.assess output),'window_accessions':{acc:{form,known_at}},'b1':{acc:rec},'b2':{acc:rec}}"""
    base = {'ticker': ticker, 'prediction_cutoff': prediction_cutoff, 'validation_status': VALIDATION_STATUS, 'tier_mode': TIER_MODE, 'computation_mode': COMPUTATION_MODE}
    if issuer.get('unassessable_reason'):
        if issuer['unassessable_reason'] not in UNASSESSABLE_REASONS: _fail('UNKNOWN_UNASSESSABLE_REASON')
        return dict(base, cik=issuer.get('cik'), computed_tier='UNASSESSABLE', assessment_status='UNASSESSABLE', tier_reasons=[], unresolved_tier_material_fields=[],
                    fields=[], source_integrity={'sec_status': issuer.get('sec_status'), 'unassessable_reason': issuer['unassessable_reason']})
    a = issuer['assessment']
    if a['computed_tier'] not in TIERS - {'UNASSESSABLE'} or a['assessment_status'] not in STATUSES - {'UNASSESSABLE'}: _fail('INVALID_ASSESSMENT_ENUM')
    reasons = [] if a['trigger_rule'] is None else [{'reason': REASON[a['trigger_rule']], 'trigger_rule': a['trigger_rule'], 'evidence_accessions': list(a['trigger_accessions'])}]
    return dict(base, cik=issuer['cik'], computed_tier=a['computed_tier'], assessment_status=a['assessment_status'], tier_reasons=reasons,
                unresolved_tier_material_fields=a['unresolved_tier_material_fields'], fields=_fields_for(reg, issuer['window_accessions'], issuer['b1'], issuer['b2']),
                source_integrity={'sec_status': issuer['sec_status'], 'unassessable_reason': None})
def counters(records, universe_n):
    c = {'TOTAL_RECORDS': len(records), 'UNIVERSE_TICKER_COUNT': universe_n}
    c['UNASSESSABLE_RECORDS'] = sum(r['computed_tier'] == 'UNASSESSABLE' for r in records); c['ASSESSABLE_RECORDS'] = len(records) - c['UNASSESSABLE_RECORDS']
    for k, why in (('SEC_SOURCE_FAILURE', 'SEC_SOURCE_FAILURE'), ('CIK_MAPPING_FAILURE', 'CIK_MAPPING_FAILURE')):
        n = sum(r['source_integrity']['unassessable_reason'] == why for r in records); c[k + '_N'] = n
    need_sec = len(records) - c['CIK_MAPPING_FAILURE_N']
    c['SEC_SOURCE_FAILURE_RATE'] = round(c['SEC_SOURCE_FAILURE_N'] / need_sec, 6) if need_sec else 0.0
    c['CIK_MAPPING_FAILURE_RATE'] = round(c['CIK_MAPPING_FAILURE_N'] / len(records), 6) if records else 0.0
    for t in ('CRITICAL', 'HIGH', 'MODERATE', 'LOW'): c[t + '_N'] = sum(r['computed_tier'] == t for r in records)
    c['RESOLVED_N'] = sum(r['assessment_status'] == 'RESOLVED' for r in records); c['REVIEW_REQUIRED_N'] = sum(r['assessment_status'] == 'REVIEW_REQUIRED' for r in records)
    c['SHADOW_ONLY_N'] = sum(r['validation_status'] == 'SHADOW_ONLY' for r in records)
    for name, s, f in (('B1_ATM', 'B1', 'is_atm'), ('B1_BABY', 'B1', 'baby_shelf_limited'), ('B2_ACTIVE', 'B2', 'active_supply'), ('B2_PIPE_RD', 'B2', 'pipe_rd'), ('B2_DILUTIVE', 'B2', 'is_dilutive')):
        for v in ('TRUE', 'FALSE', 'UNRESOLVED'):
            c[f'{name}_{v}_N'] = sum(1 for r in records for x in r['fields'] if x['set'] == s and x['field'] == f and x['value'] == v)
    c['DUPLICATE_RECORDS'] = len(records) - len({r['ticker'] for r in records})
    return c
def validate(payload, reg, reg_sha_expected):
    if payload.get('tier_mode') != TIER_MODE: _fail('UNKNOWN_TIER_MODE')
    if payload.get('validation_status') != VALIDATION_STATUS: _fail('FORBIDDEN_VALIDATION_STATUS')
    ids = payload['identities']
    if any(not ids.get(k) for k in REQUIRED_IDENTITIES): _fail('MISSING_VERSION_IDENTITY')
    if ids['field_validation_registry_v1.json'] != reg_sha_expected: _fail('FIELD_AUTHORITY_REGISTRY_MISMATCH')
    recs = payload['records']; tick = [r['ticker'] for r in recs]
    if len(tick) != len(set(tick)): _fail('DUPLICATE_RECORDS')
    if tick != payload['universe']['tickers']: _fail('RECORD_UNIVERSE_MISMATCH')
    if tick != sorted(tick): _fail('RECORD_SORT_VIOLATION')
    for r in recs:
        if r['tier_mode'] != TIER_MODE: _fail('UNKNOWN_TIER_MODE')
        if r['validation_status'] != VALIDATION_STATUS: _fail('FORBIDDEN_VALIDATION_STATUS')
        if r['computed_tier'] not in TIERS or r['assessment_status'] not in STATUSES: _fail('INVALID_ENUM')
        if (r['computed_tier'] == 'UNASSESSABLE') != (r['assessment_status'] == 'UNASSESSABLE'): _fail('UNASSESSABLE_AXIS_INCONSISTENT')
        for x in r['fields']:
            if x['production_authoritative'] is not False: _fail('FORBIDDEN_PRODUCTION_AUTHORITATIVE')
            if x['field_authority'] != reg['fields'][REG_KEY[(x['set'], x['field'])]]['field_authority']: _fail('FIELD_AUTHORITY_REGISTRY_MISMATCH')
    s = payload['summary']
    if s['TOTAL_RECORDS'] != s['UNIVERSE_TICKER_COUNT']: _fail('RECORD_COUNT_NE_UNIVERSE_COUNT')
    if s['DUPLICATE_RECORDS']: _fail('DUPLICATE_RECORDS')
def build(prediction_cutoff, universe, cik_mapping, issuers, identities, reg_path, reg_sha_expected, run_metadata):
    """universe={'source_path','source_sha256','tickers':[raw]}; cik_mapping={'source','source_sha256'}; issuers={normalized_ticker: issuer dict}."""
    if set(run_metadata) - RUN_METADATA_KEYS: _fail('UNKNOWN_RUN_METADATA_KEY')
    reg_bytes = open(reg_path, 'rb').read(); reg = json.loads(reg_bytes)
    if hashlib.sha256(reg_bytes).hexdigest() != reg_sha_expected: _fail('FIELD_AUTHORITY_REGISTRY_MISMATCH')
    norm = [_norm(t) for t in universe['tickers']]
    if len(norm) != len(set(norm)): _fail('DUPLICATE_UNIVERSE_TICKER')
    tickers = sorted(norm)
    missing = [t for t in tickers if t not in issuers]
    if missing: _fail('MISSING_TICKER_RECORD')
    if set(issuers) - set(tickers): _fail('RECORD_UNIVERSE_MISMATCH')
    records = [build_record(reg, t, prediction_cutoff, issuers[t]) for t in tickers]
    payload = {'schema_id': SCHEMA_ID, 'schema_version': SCHEMA_VERSION, 'tier_mode': TIER_MODE, 'validation_status': VALIDATION_STATUS, 'computation_mode': COMPUTATION_MODE,
               'prediction_cutoff': prediction_cutoff,
               'universe': {'scope': UNIVERSE_SCOPE, 'source_path': universe['source_path'], 'source_sha256': universe['source_sha256'], 'ticker_count': len(tickers), 'tickers': tickers},
               'cik_mapping': {'source': cik_mapping['source'], 'source_sha256': cik_mapping['source_sha256']},
               'identities': dict(identities), 'field_validation_registry': reg['fields'], 'records': records, 'summary': counters(records, len(tickers))}
    validate(payload, reg, reg_sha_expected)
    pb = canon(payload); psha = hashlib.sha256(pb).hexdigest()
    wrapper = {'decision_payload': payload, 'decision_payload_sha256': psha, 'run_metadata': dict(run_metadata)}
    return canon(wrapper), psha
