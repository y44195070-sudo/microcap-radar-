"""Shared fixture helpers (verbatim from test_1b1d.py) for 1B-1E replay."""
import sys, os, re, json
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.realpath(os.path.join(HERE, '..', 'src')); sys.path.insert(0, SRC)
import sec_collector_v1 as SC, supply_pipeline_v1 as PL
A = '/home/claude/audit'; J = A + '/product1/jan_dev'; FB = A + '/product1/feb_bench'; REPO = os.path.realpath(os.path.join(HERE, '..'))
PY = sys.executable
FROZEN = {'common.py': '16b2c448014c19489e2095d4c3335beb9f0d9d7ccd0b61dc5a66bd25bc5199d3', 'b1_deterministic_extractor.py': '1a8c66aca8bf4e8fac287e075b298deb13b45ab5ba641272b9b5967713c3db7d',
          'b2_deterministic_extractor.py': '857c87df500c89719fd40a32c0f7c0a6f494f349a7c95d112d43b727f28e768a', 'EXTRACTOR_CONFIG_V1.json': '18d1d556cadc655721daa1b07d4eab3e6c817c04bff19c86dfeb10e8951ef01e'}
PATHS = {'common.py': f'{J}/common.py', 'b1_deterministic_extractor.py': f'{J}/b1_deterministic_extractor.py', 'b2_deterministic_extractor.py': f'{J}/b2_deterministic_extractor.py',
         'EXTRACTOR_CONFIG_V1.json': f'{J}/PRODUCT_1A_EXTRACTOR_CONFIG_V1.json'}
REG = f'{SRC}/field_validation_registry_v1.json'; REG_SHA = PL.sha_file(REG)
canon = lambda o: json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
SECRET = 'TestAgent zz-secret-contact@example.invalid'
class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def sleep(self, s): self.t += s
class Fake:
    def __init__(self, bundles, docs, tickers_raw, fail=()):
        self.b, self.d, self.tr, self.fail, self.calls = bundles, docs, tickers_raw, set(fail), []
    def __call__(self, url, headers):
        self.calls.append(url)
        if url in self.fail: return 500, b''
        if url == SC.TICKERS_URL: return 200, self.tr
        m = re.fullmatch(re.escape(SC.SUBMISSIONS_BASE) + r'/CIK(\d{10})\.json', url)
        if m: b = self.b.get(m.group(1)); return (200, json.dumps(b['root']).encode()) if b else (404, b'')
        if url.startswith(SC.SUBMISSIONS_BASE + '/'):
            n = url.rsplit('/', 1)[1]
            for b in self.b.values():
                for h in b['history']:
                    if h['name'] == n: return (200, json.dumps(h['data']).encode()) if 'data' in h else (500, b'')
            return 404, b''
        if url.startswith(SC.ARCHIVES):
            a = url.split('/')[-2]; return (200, self.d[a]) if a in self.d else (404, b'')
        return 404, b''
def identities():
    ids = {k: PL.sha_file(p) for k, p in PATHS.items()}
    for f in ('supply_3a1_v1.py', 'supply_targets_v1.py', 'supply_tier_v2.py', 'supply_assessment_v1.py', 'field_validation_registry_v1.json', 'calendar_engine_v1.py', 'calendar_data_v1.json', 'manifest_builder_v1.py'):
        ids[f] = PL.sha_file(f'{SRC}/{f}')
    ids['PRODUCT_1B_0_SHADOW_DEPLOYMENT_SPEC.json'] = PL.sha_file(f'{A}/product1b/PRODUCT_1B_0_SHADOW_DEPLOYMENT_SPEC.json')
    for f in ('sec_collector_v1.py', 'supply_pipeline_v1.py'): ids[f] = PL.sha_file(f'{SRC}/{f}')
    return ids
