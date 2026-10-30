"""PRODUCT-1B-1D integration: collector outputs -> frozen B1/B2 extractors (subprocess, python3.13 -I) -> source-failure propagation
-> labels_from_extractor -> SUPPLY_RISK_TIER_V2 -> joint assessment -> manifest builder inputs. No LLM, no new classification.
Source-failure propagation: known target accession whose document could not be retrieved -> all its fields
value=UNRESOLVED, status=UNRESOLVED_SOURCE, rule_id=SOURCE_FAILURE_PROPAGATION (never FALSE-by-absence), included in joint worst-case.
INCOMPLETE_HISTORY: frozen supply_targets_v1.assessability semantics (assessable only if recent page alone covers the 90d window)."""
import hashlib, json, os, subprocess, sys
import supply_targets_v1 as TG, supply_tier_v2 as TV, supply_assessment_v1 as AS
class PipelineFatal(Exception): pass
SOURCE_FAILURE_RULE = 'SOURCE_FAILURE_PROPAGATION'
def sha_file(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def verify_identities(paths, expected):
    """paths/expected: {name: path}/{name: sha}. Any mismatch -> FROZEN_EXTRACTOR_SHA_MISMATCH."""
    got = {k: sha_file(p) for k, p in paths.items()}
    bad = sorted(k for k in expected if got.get(k) != expected[k])
    if bad: raise PipelineFatal('FROZEN_EXTRACTOR_SHA_MISMATCH:' + ','.join(bad))
    return got
def extractor_command(python, extractor_path, artifact_dir, out_path):
    return [python, '-I', extractor_path, '--artifact', artifact_dir, '--out', out_path]
def run_extractor(python, extractor_path, artifact_dir, out_path):
    man = json.load(open(os.path.join(artifact_dir, 'sha256-manifest.json')))
    for e in man['documents']:
        if e['source_sha256'] != e['sha256']: raise PipelineFatal('SOURCE_SHA_FIELD_MISMATCH')
    r = subprocess.run(extractor_command(python, extractor_path, artifact_dir, out_path), capture_output=True, text=True)
    if r.returncode != 0: raise PipelineFatal('EXTRACTOR_FAILED')
    recs = json.load(open(out_path))['records']
    want = {e['accession']: e['source_sha256'] for e in man['documents']}
    if {x['accession']: x['source_sha256'] for x in recs} != want: raise PipelineFatal('EXTRACTOR_OUTPUT_SOURCE_MISMATCH')
    return recs
def _u(): return {'value': 'UNRESOLVED', 'status': 'UNRESOLVED_SOURCE', 'rule_id': SOURCE_FAILURE_RULE, 'evidence': []}
def source_failure_records(failures, set_name):
    f = ('is_atm', 'baby_shelf_limited') if set_name == 'b1' else ('transaction_type', 'is_dilutive')
    return [dict({'accession': x['accession'], 'record_origin': SOURCE_FAILURE_RULE, 'retrieval_error': x['error']}, **{k: _u() for k in f}) for x in failures]
def assemble_issuers(collection, bundles, b1_records, b2_records, cutoff):
    """Returns (issuers dict for manifest_builder.build, audit counters)."""
    b1, b2, u1, u2 = TV.labels_from_extractor(b1_records, b2_records)
    r1 = {r['accession']: r for r in b1_records}; r2 = {r['accession']: r for r in b2_records}
    out, normal_excl, future_used = {}, 0, 0; cut = TG.P(cutoff)
    for t, info in sorted(collection['issuers'].items()):
        if info['unassessable_reason']:
            sec = 'SEC_SOURCE_FAILURE' if info['unassessable_reason'] == 'SEC_SOURCE_FAILURE' else info['sec_status']
            out[t] = {'cik': info['cik'], 'sec_status': sec, 'unassessable_reason': info['unassessable_reason']}; continue
        rows = TV.tier_filings(bundles[t])
        normal_excl += sum(1 for r in rows if TG.P(r['known_at']) > cut)
        a = AS.assess(cutoff, rows, b1, b2, u1, u2)
        w = {r['acc']: {'form': r['form'], 'known_at': r['known_at']} for r in TV.win(rows, cut, 90)}
        used = set(a['trigger_accessions']) | set(w) | set(info['b1_targets']) | set(info['b2_targets'])
        ka = {r['acc']: r['known_at'] for r in rows}
        future_used += sum(1 for x in used if x not in ka or TG.P(ka[x]) > cut)
        out[t] = {'cik': info['cik'], 'sec_status': info['sec_status'], 'assessment': a, 'window_accessions': w,
                  'b1': {k: r1[k] for k in w if k in r1}, 'b2': {k: r2[k] for k in w if k in r2}}
    if future_used: raise PipelineFatal('FUTURE_DATA_USED_IN_DECISION_PATH')
    return out, {'NORMAL_PIT_EXCLUSION_N': normal_excl, 'FUTURE_DATA_USED_IN_DECISION_PATH': future_used}
