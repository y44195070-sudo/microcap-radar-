"""PRODUCT-1B-1C SEC collector + ephemeral accession retrieval + extractor input contract. No LLM.
Format parity with research collectors: scripts/collect_sec_submissions.py (f12549c5...) bundle {cik(10-digit), root, history[{name,data}|{name,error}]}
and scripts/collect_3b_b2_8k.py (56f61045...) Archives URL https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{primaryDocument}.
Differences (1B-0): SEC_USER_AGENT from secret env only (research also read a repo variable fallback -> removed); deterministic throttle <=8 req/s
incl. retries; bounded retries; sanitized errors (codes only, never headers/UA/bodies); documents only in an ephemeral directory outside the repo.
Targets come ONLY from supply_targets_v1 (collector never redefines B1/B2 semantics)."""
import hashlib, json, os, shutil, tempfile, time, urllib.error, urllib.request
import supply_targets_v1 as TG
SUBMISSIONS_BASE = 'https://data.sec.gov/submissions'; TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'
ARCHIVES = 'https://www.sec.gov/Archives/edgar/data'
MIN_INTERVAL_S = 0.125; MAX_ATTEMPTS = 3; BACKOFF_S = (1.0, 2.0); RETRY_CODES = {429, 500, 502, 503, 504}
class CollectorFatal(Exception): pass          # run-level fatal (code only)
class FetchError(Exception): pass              # single request failure (code only)
def user_agent_from_env(env=None):
    ua = ((env if env is not None else os.environ).get('SEC_USER_AGENT') or '').strip()
    if not ua: raise CollectorFatal('MISSING_SEC_USER_AGENT_SECRET')
    return ua
def urllib_transport(url, headers, timeout=30):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, b''
    except Exception as e: raise FetchError('NETWORK_' + type(e).__name__) from None
class SecClient:
    def __init__(self, ua, transport=urllib_transport, clock=time.monotonic, sleep=time.sleep):
        self._ua = ua; self.t = transport; self.clock = clock; self.sleep = sleep; self._last = None
        self.request_times = []; self.status_counts = {}; self.requests = 0
    def __repr__(self): return 'SecClient(<redacted>)'
    def _throttle(self):
        if self._last is not None:
            w = MIN_INTERVAL_S - (self.clock() - self._last)
            if w > 0: self.sleep(w)
        self._last = self.clock(); self.request_times.append(self._last)
    def get(self, url):
        last = 'UNKNOWN'
        for i in range(MAX_ATTEMPTS):
            self._throttle(); self.requests += 1
            try: code, body = self.t(url, {'User-Agent': self._ua, 'Accept-Encoding': 'identity'})
            except FetchError as e: code, body, last = None, None, str(e)
            if code is not None:
                self.status_counts[str(code)] = self.status_counts.get(str(code), 0) + 1
                if code == 200: return body
                last = f'HTTP_{code}'
                if code not in RETRY_CODES: break
            if i < MAX_ATTEMPTS - 1: self.sleep(BACKOFF_S[i])
        raise FetchError(last)
def fetch_company_tickers(client):
    """Returns (raw_bytes_sha256, {TICKER: cik10}). Any failure -> CollectorFatal (systemic)."""
    try: raw = client.get(TICKERS_URL)
    except FetchError as e: raise CollectorFatal('COMPANY_TICKERS_UNAVAILABLE:' + str(e)) from None
    try:
        obj = json.loads(raw.decode('utf-8')); m = {}
        for v in obj.values():
            t = str(v['ticker']).strip().upper(); c = str(int(v['cik_str'])).zfill(10)
            if t in m and m[t] != c: raise ValueError('CONFLICT')
            m[t] = c
        if not m: raise ValueError('EMPTY')
    except Exception: raise CollectorFatal('COMPANY_TICKERS_INVALID') from None
    return hashlib.sha256(raw).hexdigest(), m
def fetch_submissions(client, cik10):
    """Returns (bundle, None) or (None, 'SEC_SOURCE_FAILURE'). History page failure kept as {name,error} (-> INCOMPLETE_HISTORY downstream)."""
    try: root = json.loads(client.get(f'{SUBMISSIONS_BASE}/CIK{cik10}.json').decode('utf-8'))
    except Exception: return None, 'SEC_SOURCE_FAILURE'
    b = {'cik': cik10, 'root': root, 'history': []}
    for ent in root.get('filings', {}).get('files', []):
        name = ent.get('name')
        if not name: continue
        try: b['history'].append({'name': name, 'data': json.loads(client.get(f'{SUBMISSIONS_BASE}/{name}').decode('utf-8'))})
        except Exception as e: b['history'].append({'name': name, 'error': str(e) if isinstance(e, FetchError) else 'PARSE_' + type(e).__name__})
    return b, None
def check_pit(rows_used, cutoff):
    """Hard fail if any filing used for targets/tier has known_at > cutoff (future access)."""
    c = TG.P(cutoff)
    for r in rows_used:
        if r['known_at'] is None or TG.P(r['known_at']) > c: raise CollectorFatal('SEC_FUTURE_ACCESS_VIOLATION')
class EphemeralWorkspace:
    """Raw documents live only here. Must be outside repo_root. Removed on exit (also on error)."""
    def __init__(self, repo_root, base=None):
        self.repo_root = os.path.realpath(repo_root); self.base = base or os.environ.get('RUNNER_TEMP') or tempfile.gettempdir()
    def __enter__(self):
        self.path = os.path.realpath(tempfile.mkdtemp(prefix='supply-shadow-src-', dir=self.base))
        if os.path.commonpath([self.path, self.repo_root]) == self.repo_root: shutil.rmtree(self.path); raise CollectorFatal('EPHEMERAL_DIR_INSIDE_REPO')
        return self
    def __exit__(self, *a): shutil.rmtree(self.path, ignore_errors=True); return False
def retrieve_documents(client, targets, ws_dir, set_name, require_known_at):
    """Writes {ws}/{set}/raw/{acc}_{doc} + {ws}/{set}/sha256-manifest.json {'documents':[{accession,path,known_at,source_sha256,cik,form,...}]}.
    Returns (artifact_dir, retrieval_failures[{accession,error}])."""
    d = os.path.join(ws_dir, set_name); os.makedirs(os.path.join(d, 'raw'), exist_ok=True); docs, fails = [], []
    for x in targets:
        if require_known_at and not x.get('known_at'): raise CollectorFatal('B2_KNOWN_AT_MISSING')
        acc = x['accession']; url = f"{ARCHIVES}/{int(x['cik'])}/{acc.replace('-', '')}/{x['primaryDocument']}"
        try: data = client.get(url)
        except FetchError as e: fails.append({'accession': acc, 'error': str(e)}); continue
        rel = f"raw/{acc}_{os.path.basename(x['primaryDocument'])}"; open(os.path.join(d, rel), 'wb').write(data)
        docs.append({'accession': acc, 'path': rel, 'known_at': x['known_at'], 'source_sha256': hashlib.sha256(data).hexdigest(), 'sha256': hashlib.sha256(data).hexdigest(),
                     'cik': x['cik'], 'form': x['form'], 'primaryDocument': x['primaryDocument'], **({'items': x['items']} if 'items' in x else {})})
    docs.sort(key=lambda r: r['accession'])
    open(os.path.join(d, 'sha256-manifest.json'), 'w').write(json.dumps({'documents': docs}, sort_keys=True, separators=(',', ':')))
    return d, sorted(fails, key=lambda f: f['accession'])
def verify_input_contract(artifact_dir, require_known_at):
    man = json.load(open(os.path.join(artifact_dir, 'sha256-manifest.json')))
    for e in man['documents']:
        for k in ('accession', 'path', 'source_sha256') + (('known_at',) if require_known_at else ()):
            if not e.get(k): raise CollectorFatal('EXTRACTOR_INPUT_CONTRACT_VIOLATION:' + k)
        if hashlib.sha256(open(os.path.join(artifact_dir, e['path']), 'rb').read()).hexdigest() != e['source_sha256']: raise CollectorFatal('SOURCE_SHA_MISMATCH')
    return len(man['documents'])
def collect(client, universe_tickers, cutoff):
    """Metadata stage (no documents). Returns dict with deterministic 'collection' summary + in-memory bundles/targets for integration."""
    cmap_sha, cmap = fetch_company_tickers(client)
    issuers, bundles, b1t, b2t = {}, {}, [], []
    for t in sorted({x.strip().upper() for x in universe_tickers}):
        cik = cmap.get(t)
        if not cik: issuers[t] = {'cik': None, 'unassessable_reason': 'CIK_MAPPING_FAILURE', 'sec_status': None}; continue
        b, err = fetch_submissions(client, cik)
        if err: issuers[t] = {'cik': cik, 'unassessable_reason': err, 'sec_status': None}; continue
        cik_i, status, recent_earliest, rows = TG.parse_submissions(b)
        ok, why = TG.assessability(cik, status, recent_earliest, cutoff)
        if not ok: issuers[t] = {'cik': cik, 'unassessable_reason': why, 'sec_status': status}; continue
        x1, x2 = TG.targets(cik_i, rows, [cutoff]); check_pit([{'known_at': r['known_at']} for r in x1 + x2], cutoff)
        issuers[t] = {'cik': cik, 'unassessable_reason': None, 'sec_status': status, 'b1_targets': [r['accession'] for r in x1], 'b2_targets': [r['accession'] for r in x2]}
        bundles[t] = b; b1t += x1; b2t += x2
    key = lambda x: (int(x['cik']), x['known_at'], x['accession'])
    return {'collection': {'prediction_cutoff': cutoff, 'cik_mapping_source': TICKERS_URL, 'cik_mapping_source_sha256': cmap_sha, 'issuers': issuers},
            'bundles': bundles, 'b1_targets': sorted(b1t, key=key), 'b2_targets': sorted(b2t, key=key)}
def systemic_sec_failure(issuers):
    """Publication-gate helper using RAW integer counts (no rounding): fail iff SEC_SOURCE_FAILURE_N * 4 > denominator."""
    den = sum(1 for v in issuers.values() if v['unassessable_reason'] != 'CIK_MAPPING_FAILURE')
    n = sum(1 for v in issuers.values() if v['unassessable_reason'] == 'SEC_SOURCE_FAILURE')
    return {'SEC_SOURCE_FAILURE_N': n, 'SEC_ASSESSMENT_DENOMINATOR_N': den, 'SYSTEMIC_FAIL': n * 4 > den}
