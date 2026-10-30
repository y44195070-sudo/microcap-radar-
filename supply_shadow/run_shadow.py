#!/usr/bin/env python3
"""PRODUCT-1B-1I orchestration (NOT a frozen semantic module). VERIFY FREEZE -> CALENDAR -> UNIVERSE -> SEC -> PIPELINE -> GATES -> STAGE.
Never modifies frozen files. Writes only a staging dir (latest.json + history file) for the separate publish job.
Exit codes: 0 PASS(staged) | 10 SKIPPED_NO_RECENT_ELIGIBLE_TRADING_CUTOFF | 1 FAILED (stdout: one JSON status line; never secrets)."""
import argparse, hashlib, json, os, re, sys, datetime as dt
EXPECTED_FREEZE_MANIFEST_SHA256 = 'ff06cfc8dff46d6ed34c34e315ccc89f910e9ba0146abf1d5c2d8edf7641d26f'
FREEZE_MANIFEST_NAME = 'PRODUCT_1B_1_IMPLEMENTATION_FREEZE_MANIFEST.json'
HISTORY_DIR, LATEST = 'v2/data/supply-shadow/history', 'v2/data/supply-shadow/latest.json'
class Fail(Exception): pass
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def verify_freeze(frozen_dir):
    """Step 1: before ANY network. Manifest bytes SHA, then all listed file SHAs."""
    p = os.path.join(frozen_dir, FREEZE_MANIFEST_NAME)
    if not os.path.isfile(p): raise Fail('FREEZE_MANIFEST_MISSING')
    raw = open(p, 'rb').read()
    if sha_bytes(raw) != EXPECTED_FREEZE_MANIFEST_SHA256: raise Fail('FREEZE_MANIFEST_SHA_MISMATCH')
    m = json.loads(raw)
    if m.get('status') != 'FROZEN' or m.get('file_identity_count') != len(m['files']): raise Fail('FREEZE_MANIFEST_INVALID')
    bad = [n for n, e in sorted(m['files'].items()) if not os.path.isfile(os.path.join(frozen_dir, n)) or sha_bytes(open(os.path.join(frozen_dir, n), 'rb').read()) != e['sha256']]
    if bad: raise Fail('FROZEN_FILE_SHA_MISMATCH:' + ','.join(bad))
    return m
SCHEDULE_RECOVERY_WINDOW = dt.timedelta(hours=20)
def resolve_target(cal, now, mode, target_date):
    """scheduled (SCHEDULE_TARGET_POLICY = MOST_RECENT_ELIGIBLE_CUTOFF_WITHIN_20H): target = most recent trading day D with
    0 <= now - cutoff(D) <= 20h (exact UTC datetimes). Only dates in [(now-20h).date(), now.date()] are examined (no unbounded backward
    scan; unsupported calendar year -> UnsupportedCalendarYear -> fail closed). Else SKIP. prediction_cutoff stays D T21:00:00Z.
    manual (unchanged): explicit --target-date required; must be a trading day whose cutoff <= now."""
    if mode == 'scheduled':
        if now.tzinfo is None: raise Fail('NAIVE_DATETIME')
        n = now.astimezone(dt.timezone.utc); d = n.date(); lo = (n - SCHEDULE_RECOVERY_WINDOW).date()
        while d >= lo:
            if cal.is_trading_day(d):
                cut = cal.prediction_cutoff(d); age = n - dt.datetime.fromisoformat(cut.replace('Z', '+00:00'))
                if dt.timedelta(0) <= age <= SCHEDULE_RECOVERY_WINDOW: return d, cut
                if age >= dt.timedelta(0): break   # most recent past cutoff exists but is older than the window
            d -= dt.timedelta(days=1)
        return None, None
    if not target_date: raise Fail('MANUAL_TARGET_DATE_REQUIRED')
    d = dt.date.fromisoformat(target_date)
    if not cal.is_trading_day(d): raise Fail('MANUAL_TARGET_NOT_TRADING_DAY')
    cut = cal.prediction_cutoff(d)
    if dt.datetime.fromisoformat(cut.replace('Z', '+00:00')) > now: raise Fail('MANUAL_TARGET_CUTOFF_IN_FUTURE')
    return d, cut
def load_universe(repo_root):
    raw = open(os.path.join(repo_root, 'v2/data/manifest.json'), 'rb').read(); u = json.loads(raw)
    if not isinstance(u, list) or not u or not all(isinstance(t, str) and t.strip() for t in u): raise Fail('UNIVERSE_INVALID')
    return u, sha_bytes(raw)
TOKEN_PATTERNS = [rb'ghp_[A-Za-z0-9]{20,}', rb'github_pat_[A-Za-z0-9_]{20,}', rb'gh[ousr]_[A-Za-z0-9]{20,}', rb'AKIA[0-9A-Z]{16}', rb'(?i)authorization:', rb'(?i)cookie:', rb'(?i)bearer [a-z0-9._-]{16,}']
HTML_SIGS = [rb'(?i)<html', rb'(?i)<!doctype html', rb'(?i)<body', rb'(?i)</div>']
def scan(blob, ua):
    hits_secret = 0; ua_b = ua.encode()
    if ua_b and ua_b in blob: hits_secret += 1
    for e in re.findall(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', ua):
        if e.encode().lower() in blob.lower(): hits_secret += 1
    hits_secret += sum(1 for p in TOKEN_PATTERNS if re.search(p, blob))
    return hits_secret, sum(1 for p in HTML_SIGS if re.search(p, blob))
def run(args, env=None, now=None, transport=None, clock=None, sleep=None):
    env = os.environ if env is None else env; frozen = os.path.realpath(args.frozen_dir); repo = os.path.realpath(args.repo_root)
    m = verify_freeze(frozen)                                           # 1. identity before network
    sys.path.insert(0, frozen)
    import calendar_engine_v1 as CE, sec_collector_v1 as SC, supply_pipeline_v1 as PL, manifest_builder_v1 as MB
    now = now or dt.datetime.now(dt.timezone.utc); cal = CE.Calendar(os.path.join(frozen, 'calendar_data_v1.json'))
    try: d, cut = resolve_target(cal, now, args.mode, args.target_date)  # 2. calendar
    except CE.UnsupportedCalendarYear: raise Fail('CALENDAR_INTEGRITY_UNSUPPORTED_YEAR')
    if d is None: return {'RUN_STATUS': 'SKIPPED_NO_RECENT_ELIGIBLE_TRADING_CUTOFF', 'PUBLICATION': 0}
    tickers, usha = load_universe(repo)                                 # 3. universe
    try: ua = SC.user_agent_from_env(env)                               # 4. secret (fail closed)
    except SC.CollectorFatal as e: raise Fail(str(e))
    kw = {k: v for k, v in (('transport', transport), ('clock', clock), ('sleep', sleep)) if v is not None}
    client = SC.SecClient(ua, **kw)
    try:
        res = SC.collect(client, tickers, cut)                          # 5. SEC metadata (company_tickers fatal inside)
        gate = SC.systemic_sec_failure(res['collection']['issuers'])
        if gate['SYSTEMIC_FAIL']: raise Fail('SYSTEMIC_SEC_FAILURE')
        with SC.EphemeralWorkspace(repo) as ws:                         # 6. ephemeral docs + frozen extractors
            d1, f1 = SC.retrieve_documents(client, res['b1_targets'], ws.path, 'b1', False); SC.verify_input_contract(d1, False)
            d2, f2 = SC.retrieve_documents(client, res['b2_targets'], ws.path, 'b2', True); SC.verify_input_contract(d2, True)
            x1 = PL.run_extractor(sys.executable, os.path.join(frozen, 'b1_deterministic_extractor.py'), d1, os.path.join(ws.path, 'b1.json'))
            x2 = PL.run_extractor(sys.executable, os.path.join(frozen, 'b2_deterministic_extractor.py'), d2, os.path.join(ws.path, 'b2.json'))
        iss, audit = PL.assemble_issuers(res['collection'], res['bundles'], x1 + PL.source_failure_records(f1, 'b1'), x2 + PL.source_failure_records(f2, 'b2'), cut)
    except SC.CollectorFatal as e: raise Fail(str(e).split(':')[0])
    except PL.PipelineFatal as e: raise Fail(str(e).split(':')[0])
    ids = {n: e['sha256'] for n, e in m['files'].items()}; ids[FREEZE_MANIFEST_NAME] = EXPECTED_FREEZE_MANIFEST_SHA256
    rm = {k: v for k, v in (('generated_at', now.strftime('%Y-%m-%dT%H:%M:%SZ')), ('workflow_run_id', env.get('GITHUB_RUN_ID')), ('workflow_run_attempt', env.get('GITHUB_RUN_ATTEMPT')),
                             ('workflow_commit_sha', env.get('GITHUB_SHA')), ('trigger', args.mode)) if v}
    try:
        wrapper, psha = MB.build(cut, {'source_path': 'v2/data/manifest.json', 'source_sha256': usha, 'tickers': tickers},
                                 {'source': SC.TICKERS_URL, 'source_sha256': res['collection']['cik_mapping_source_sha256']}, iss, ids,
                                 os.path.join(frozen, 'field_validation_registry_v1.json'), ids['field_validation_registry_v1.json'], rm)
    except MB.ManifestBuildError as e: raise Fail('MANIFEST_' + str(e))
    payload = json.loads(wrapper)['decision_payload']                   # 7. publication hard gates
    s = payload['summary']
    if audit['FUTURE_DATA_USED_IN_DECISION_PATH'] != 0: raise Fail('FUTURE_DATA_USED_IN_DECISION_PATH')
    if s['DUPLICATE_RECORDS'] or s['TOTAL_RECORDS'] != s['UNIVERSE_TICKER_COUNT']: raise Fail('RECORD_COUNT_OR_DUPLICATE')
    if sha_bytes(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()) != psha: raise Fail('CANONICAL_SERIALIZATION_FAILURE')
    sec_hits, html_hits = scan(wrapper, ua)
    if sec_hits: raise Fail('SECRET_LEAK_SCAN_HIT')
    if html_hits: raise Fail('RAW_HTML_PUBLIC_OUTPUT_HIT')
    hist = f'{HISTORY_DIR}/{d.isoformat()}.json'                        # 8. stage (no overwrite of canonical history)
    if os.path.exists(os.path.join(repo, hist)):
        rid = env.get('GITHUB_RUN_ID') or 'local'
        if not re.fullmatch(r'[A-Za-z0-9_-]+', rid): raise Fail('INVALID_RUN_ID')
        hist = f'{HISTORY_DIR}/{d.isoformat()}.rerun-{rid}.json'
    st = os.path.realpath(args.staging_dir)
    if os.path.commonpath([st, repo]) == repo: raise Fail('STAGING_INSIDE_REPO')
    for rel in (hist, LATEST):
        os.makedirs(os.path.dirname(os.path.join(st, rel)), exist_ok=True); open(os.path.join(st, rel), 'wb').write(wrapper)
    plan = {'target_date': d.isoformat(), 'prediction_cutoff': cut, 'decision_payload_sha256': psha, 'files': sorted([hist, LATEST])}
    open(os.path.join(st, 'publish_plan.json'), 'w').write(json.dumps(plan, sort_keys=True, separators=(',', ':')))
    return {'RUN_STATUS': 'PASS', 'target_date': d.isoformat(), 'decision_payload_sha256': psha, 'history_file': hist, 'counters': {k: s[k] for k in ('TOTAL_RECORDS', 'UNASSESSABLE_RECORDS', 'REVIEW_REQUIRED_N', 'SEC_SOURCE_FAILURE_N', 'CIK_MAPPING_FAILURE_N')}, 'audit': audit}
def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument('--mode', choices=('scheduled', 'manual'), required=True); ap.add_argument('--target-date')
    ap.add_argument('--frozen-dir', required=True); ap.add_argument('--repo-root', required=True); ap.add_argument('--staging-dir', required=True)
    a = ap.parse_args(argv)
    try: r = run(a)
    except Fail as e: print(json.dumps({'RUN_STATUS': 'FAILED', 'PIPELINE_FAILURE_REASON': str(e)})); return 1
    except Exception as e: print(json.dumps({'RUN_STATUS': 'FAILED', 'PIPELINE_FAILURE_REASON': 'UNEXPECTED_' + type(e).__name__})); return 1
    print(json.dumps(r, sort_keys=True)); return 10 if r['RUN_STATUS'].startswith('SKIPPED_') else 0
if __name__ == '__main__': sys.exit(main())
