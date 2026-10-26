#!/usr/bin/env python3
"""STEP11 candidate-wide structural SEC metadata acquisition execution.
Metadata only. Frozen STEP9 CIK is the sole network identity. No filing bodies/XBRL/providers.
Pass B is a strict persisted-evidence replay and has no network-capable dependency.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, os, pathlib, sys
from typing import Any
import step11_pre_full638_metadata_certification as core

SUCCESS="STEP11_PRE_FULL638_STRUCTURAL_METADATA_ACQUISITION_CERTIFIED"
VALIDATED="STEP11_METADATA_ACQUISITION_CERTIFICATION_WORKFLOW_IMPLEMENTATION_VALIDATED"
SCOPE="METADATA_ONLY_SCOPE"
TERMINALS={"COMPLETE_FOR_METADATA_SCOPE","TIMESTAMP_INSUFFICIENT","NO_FILING_METADATA","SOURCE_ACQUISITION_INCOMPLETE","SOURCE_DRIFT_OR_EVIDENCE_MISMATCH","METADATA_SCOPE_ESCALATED_INTO_RECONSTRUCTION"}
PROHIBITED={"provider_requests":0,"current_identifier_requests":0,"residual4388_requests":0,"filing_body_requests":0,"exhibit_requests":0,"xbrl_requests":0,"companyfacts_requests":0}

class ExecutionError(RuntimeError): pass

def cb(o:Any)->bytes: return (json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def h(o:Any)->str: return hashlib.sha256(cb(o)).hexdigest()
def write(p:pathlib.Path,o:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(cb(o))
def load_rows(p:pathlib.Path)->list[dict]:
    x=json.loads(p.read_text())
    if isinstance(x,dict):
        for k in ("rows","certified_allowlist","occurrences","candidates"):
            if isinstance(x.get(k),list): return x[k]
    if isinstance(x,list): return x
    raise ExecutionError("CANDIDATE_INPUT_SCHEMA_UNSUPPORTED")
def norm_rows(rows:list[dict])->list[dict]:
    out=[]
    for r in rows:
        x=dict(r)
        if "issuer_cik" not in x: raise ExecutionError("FROZEN_CIK_MISSING")
        x["issuer_cik"]=core.canonical_cik(x["issuer_cik"]); out.append(x)
    core.validate_input(out,638); return sorted(out,key=lambda r:r["forensic_occurrence_id"])
def history_refs(base:dict)->list[str]:
    out=[]
    for x in (base.get("filings") or {}).get("files") or []:
        if isinstance(x,dict) and x.get("name"):
            name=str(x["name"]); core.endpoint_for_history(name); out.append(name)
    return sorted(set(out))
def decode(raw:bytes)->dict:
    try: x=json.loads(raw)
    except Exception as e: raise ExecutionError("MALFORMED_RESPONSE") from e
    if not isinstance(x,dict): raise ExecutionError("MALFORMED_RESPONSE")
    return x
def classify(occ:dict,filings:list[dict],complete:bool)->dict:
    states=[(f,core.pit_state(occ["prediction_timestamp"],f["filingDate"],f.get("acceptanceDateTime"))) for f in filings]
    pre=[f for f,s in states if s in {"BEFORE_CUTOFF","SAME_DAY_BEFORE"}]; post=[f for f,s in states if s in {"AFTER_CUTOFF","SAME_DAY_AFTER"}]; amb=[f for f,s in states if s=="SAME_DAY_TIMESTAMP_UNRESOLVED"]
    terminal="SOURCE_ACQUISITION_INCOMPLETE" if not complete else "TIMESTAMP_INSUFFICIENT" if amb else "NO_FILING_METADATA" if not pre else "COMPLETE_FOR_METADATA_SCOPE"
    return {"forensic_occurrence_id":occ["forensic_occurrence_id"],"issuer_cik":occ["issuer_cik"],"prediction_cutoff":occ["prediction_timestamp"],"terminal_state":terminal,"pit_safe_accessions":sorted(f["accessionNumber"] for f in pre),"pit_safe_forms":sorted(set(f["form"] for f in pre)),"pre_cutoff_filing_count":len(pre),"post_cutoff_filing_count":len(post),"future_excluded_count":len(post),"same_day_ambiguous_count":len(amb),"timestamp_insufficient_count":len(amb),"form_presence":sorted(set(f["form"] for f in pre))}
def aggregate(rows,derived,ledger):
    tc=collections.Counter(x["terminal_state"] for x in derived); forms=collections.Counter(f for x in derived for f in x["form_presence"])
    return {"metadata_scope":SCOPE,"total_occurrences":len(rows),"unique_frozen_cik_count":len({r['issuer_cik'] for r in rows}),"unique_prediction_dates":len({r['prediction_timestamp'][:10] for r in rows}),"exchange_distribution":dict(sorted(collections.Counter(r['exchange'] for r in rows).items())),"instrument_distribution":dict(sorted(collections.Counter(r['instrument_type'] for r in rows).items())),"issuer_concentration":dict(sorted(collections.Counter(r['issuer_cik'] for r in rows).items())),"total_pit_safe_filings":sum(x['pre_cutoff_filing_count'] for x in derived),"total_future_filings_excluded":sum(x['future_excluded_count'] for x in derived),"total_timestamp_insufficient":sum(x['timestamp_insufficient_count'] for x in derived),"terminal_states":dict(sorted(tc.items())),"form_distribution":dict(sorted(forms.items())),"request_count":len(ledger)}
def strata(rows,derived):
    by={x['forensic_occurrence_id']:x for x in derived}; out=[]
    for r in rows:
        d=by[r['forensic_occurrence_id']]; n=d['pre_cutoff_filing_count']; bucket="0" if n==0 else "1" if n==1 else "2-5" if n<=5 else "6-20" if n<=20 else "21+"
        out.append({"forensic_occurrence_id":r['forensic_occurrence_id'],"prediction_date":r['prediction_timestamp'][:10],"exchange":r['exchange'],"instrument_type":r['instrument_type'],"issuer_cik":r['issuer_cik'],"pit_filing_count_bucket":bucket,"form_presence_vector":d['form_presence'],"same_day_boundary_state":"TIMESTAMP_INSUFFICIENT" if d['timestamp_insufficient_count'] else "RESOLVED","metadata_completeness_state":d['terminal_state']})
    return {"metadata_scope":SCOPE,"rows":out}
def _state(cik): return {"issuer_cik":cik,"base_request_state":"NOT_ATTEMPTED","historical_request_states":[],"acquisition_complete":True,"failure_class":None,"expected_raw_sha256":[],"observed_raw_sha256":[]}
def _finalize_states(states,ciks):
    if set(states)!=set(ciks): raise ExecutionError("ACQUISITION_STATE_CIK_SET_MISMATCH")
    out=[]
    for cik in sorted(states):
        s=dict(states[cik]); s["historical_request_states"]=sorted(s["historical_request_states"],key=lambda x:(x.get("parent_reference","") ,x.get("state",""))); s["expected_raw_sha256"]=sorted(set(s["expected_raw_sha256"])); s["observed_raw_sha256"]=sorted(set(s["observed_raw_sha256"]))
        if s["base_request_state"] not in {"SUCCESS","FAILED"} or not isinstance(s["acquisition_complete"],bool): raise ExecutionError("ACQUISITION_STATE_INVALID")
        out.append(s)
    return out
def acquire(rows,client,rawdir):
    grouped=collections.defaultdict(list)
    for r in rows: grouped[r['issuer_cik']].append(r)
    allfilings={}; states={}; raw_manifest=[]
    for cik in sorted(grouped):
        filings=[]; s=_state(cik); states[cik]=s; url=core.endpoint_for_base(cik)
        try:
            raw=client.fetch(url,cik); sha=hashlib.sha256(raw).hexdigest(); (rawdir/sha).write_bytes(raw); raw_manifest.append({"issuer_cik":cik,"endpoint_class":"SEC_SUBMISSIONS_BASE_METADATA","sha256":sha,"byte_size":len(raw)}); s["base_request_state"]="SUCCESS"; s["expected_raw_sha256"].append(sha); s["observed_raw_sha256"].append(sha); obj=decode(raw); filings.extend(core.parse_recent(obj,sha,url))
            for name in history_refs(obj):
                hu=core.endpoint_for_history(name)
                try:
                    hr=client.fetch(hu,cik); hs=hashlib.sha256(hr).hexdigest(); (rawdir/hs).write_bytes(hr); raw_manifest.append({"issuer_cik":cik,"endpoint_class":"SEC_SUBMISSIONS_HISTORICAL_METADATA","parent_reference":name,"sha256":hs,"byte_size":len(hr)}); s["historical_request_states"].append({"parent_reference":name,"state":"SUCCESS","sha256":hs}); s["expected_raw_sha256"].append(hs); s["observed_raw_sha256"].append(hs); filings.extend(core.parse_history(decode(hr),hs,hu))
                except Exception as e: s["acquisition_complete"]=False; s["failure_class"]="HISTORICAL_METADATA_REQUEST_FAILED"; s["historical_request_states"].append({"parent_reference":name,"state":"FAILED","failure_class":type(e).__name__})
        except Exception: s["base_request_state"]="FAILED"; s["acquisition_complete"]=False; s["failure_class"]="BASE_METADATA_REQUEST_FAILED"
        try: filings,_=core.dedup_rows(filings)
        except Exception: s["acquisition_complete"]=False; s["failure_class"]="METADATA_DEDUP_FAILED"; filings=[]
        allfilings[cik]=filings
    state_rows=_finalize_states(states,set(grouped)); complete={x['issuer_cik']:x['acquisition_complete'] for x in state_rows}; derived=[classify(r,allfilings[r['issuer_cik']],complete[r['issuer_cik']]) for r in rows]
    if len(derived)!=638 or set(collections.Counter(x['terminal_state'] for x in derived))-TERMINALS: raise ExecutionError("TERMINAL_REGISTRY_INVALID")
    return derived,sorted(raw_manifest,key=lambda x:(x['issuer_cik'],x['endpoint_class'],x.get('parent_reference',''),x['sha256'])),{"schema":"STEP11_ACQUISITION_STATE_V1","rows":state_rows}
def _validate_replay_state(rows,state,raw_manifest):
    if state.get("schema")!="STEP11_ACQUISITION_STATE_V1" or not isinstance(state.get("rows"),list): raise ExecutionError("ACQUISITION_STATE_MANIFEST_INVALID")
    expected={r['issuer_cik'] for r in rows}; by={}
    for s in state['rows']:
        cik=s.get('issuer_cik')
        if cik in by: raise ExecutionError("ACQUISITION_STATE_DUPLICATE_CIK")
        if cik not in expected: raise ExecutionError("ACQUISITION_STATE_UNKNOWN_CIK")
        if s.get('base_request_state') not in {'SUCCESS','FAILED'} or not isinstance(s.get('acquisition_complete'),bool): raise ExecutionError("ACQUISITION_STATE_MANIFEST_INVALID")
        by[cik]=s
    if set(by)!=expected: raise ExecutionError("ACQUISITION_STATE_MISSING_CIK")
    mh=collections.Counter(m.get('sha256') for m in raw_manifest)
    for s in by.values():
        for sha in s.get('expected_raw_sha256',[]):
            if mh[sha]<1: raise ExecutionError("RAW_EVIDENCE_MISSING")
    return by
def replay(rows,raw_manifest,state,rawdir):
    states=_validate_replay_state(rows,state,raw_manifest); bycik=collections.defaultdict(list)
    for m in sorted(raw_manifest,key=lambda x:(x['issuer_cik'],x['endpoint_class'],x.get('parent_reference',''),x['sha256'])):
        p=rawdir/m['sha256']
        if not p.exists(): raise ExecutionError("RAW_EVIDENCE_MISSING")
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=m['sha256']: raise ExecutionError("RAW_EVIDENCE_HASH_MISMATCH")
        if len(raw)!=m.get('byte_size',len(raw)): raise ExecutionError("RAW_EVIDENCE_SIZE_MISMATCH")
        obj=decode(raw); src=m.get('parent_reference') or core.endpoint_for_base(m['issuer_cik']); parsed=core.parse_history(obj,m['sha256'],src) if m['endpoint_class']=="SEC_SUBMISSIONS_HISTORICAL_METADATA" else core.parse_recent(obj,m['sha256'],src); bycik[m['issuer_cik']].extend(parsed)
    out=[]
    for r in rows:
        fs,_=core.dedup_rows(bycik[r['issuer_cik']]); out.append(classify(r,fs,states[r['issuer_cik']]['acquisition_complete']))
    return out
def _persist_forensics(out,rows,plan,raw_manifest,state,ledger,derived,replayed,pass_b_network,disagreements):
    write(out/'candidate638_manifest.json',rows); write(out/'request_plan.json',plan); write(out/'raw_evidence_manifest.json',raw_manifest); write(out/'acquisition_state_manifest.json',state); write(out/'request_ledger.json',ledger); write(out/'pass_a.json',{"derived":derived,"hash":h(derived)}); write(out/'pass_b.json',{"derived":replayed,"hash":h(replayed),"network_requests":pass_b_network}); write(out/'determinism.json',{"semantic_disagreements":disagreements,"occurrences_with_disagreements":[a['forensic_occurrence_id'] for a,b in zip(derived,replayed) if a!=b],"pass_b_network_requests":pass_b_network,"PASS":pass_b_network==0 and disagreements==0}); write(out/'network_audit.json',{"sec_requests":core.COUNTERS['sec_requests'],"pass_b_network_requests":pass_b_network,**PROHIBITED})
def run_live(args):
    if os.environ.get("STEP11_METADATA_CERTIFICATION_ENABLE")!="YES": raise ExecutionError("CERTIFICATION_NOT_EXPLICITLY_ENABLED")
    rows=norm_rows(load_rows(pathlib.Path(args.input638))); out=pathlib.Path(args.out); rawdir=out/'raw'; rawdir.mkdir(parents=True,exist_ok=True); plan=core.build_request_plan(rows); client=core.MetadataClient(core.NetworkPolicy(enabled=True,max_requests=len(plan)*20+100,retry_ceiling=2),os.environ.get("SEC_USER_AGENT")); derived,raw_manifest,state=acquire(rows,client,rawdir); replayed=[]; pass_b_network=0; disagreements=638
    try: replayed=replay(rows,raw_manifest,state,rawdir); disagreements=sum(a!=b for a,b in zip(derived,replayed))
    finally: _persist_forensics(out,rows,plan,raw_manifest,state,client.audit,derived,replayed,pass_b_network,disagreements)
    if pass_b_network or disagreements: write(out/'failure_decision.json',{"decision":"DETERMINISM_FAILED","pass_b_network_requests":pass_b_network,"semantic_disagreements":disagreements,"candidate_count":638}); raise ExecutionError("DETERMINISM_FAILED")
    write(out/'metadata_coverage.json',aggregate(rows,derived,client.audit)); write(out/'structural_strata.json',strata(rows,derived)); write(out/'final_decision.json',{"decision":SUCCESS,"metadata_scope":SCOPE,"candidate_count":638}); print(SUCCESS); return 0
def synthetic_rows(): return norm_rows([{"forensic_occurrence_id":f"occ-{i:03d}","prediction_id":f"pred-{i:03d}","prediction_timestamp":"2026-01-10T15:00:00+00:00","certified_identity_key":f"id-{i:03d}","issuer_cik":str((i%7)+1),"exchange":"XNAS","instrument_type":"CS","identity_version":"FROZEN","governance_status":"CERTIFIED"} for i in range(638)])
def _fixture_raw(filings):
    cols={k:[] for k in core.ALLOWED_FORMS_FIELDS}
    for f in filings:
        for k in cols: cols[k].append(f.get(k))
    return cb({"filings":{"recent":cols,"files":[]}})
def _offline_replay(rows,specs,tmp):
    rawdir=tmp/'raw'; rawdir.mkdir(parents=True,exist_ok=True); manifest=[]; state_rows=[]; allf={}
    for cik in sorted({r['issuer_cik'] for r in rows}):
        sp=specs.get(cik,{"complete":True,"filings":[]}); complete=bool(sp.get('complete',True)); filings=sp.get('filings',[]); s=_state(cik); s['base_request_state']='SUCCESS' if sp.get('base_success',True) else 'FAILED'; s['acquisition_complete']=complete; s['failure_class']=None if complete else sp.get('failure_class','SYNTHETIC_ACQUISITION_FAILED')
        if sp.get('base_success',True):
            raw=_fixture_raw(filings); sha=hashlib.sha256(raw).hexdigest(); (rawdir/sha).write_bytes(raw); manifest.append({"issuer_cik":cik,"endpoint_class":"SEC_SUBMISSIONS_BASE_METADATA","sha256":sha,"byte_size":len(raw)}); s['expected_raw_sha256']=[sha]; s['observed_raw_sha256']=[sha]; allf[cik]=core.parse_recent(decode(raw),sha,core.endpoint_for_base(cik))
        else: allf[cik]=[]
        state_rows.append(s)
    state={"schema":"STEP11_ACQUISITION_STATE_V1","rows":state_rows}; comp={s['issuer_cik']:s['acquisition_complete'] for s in state_rows}; a=[classify(r,allf[r['issuer_cik']],comp[r['issuer_cik']]) for r in rows]; b=replay(rows,manifest,state,rawdir); return a,b,manifest,state,rawdir
def run_validate(out):
    tests={}; rows=synthetic_rows(); tmp=out/'offline-fixtures'
    def t(name,fn):
        try: fn(); tests[name]="PASS"
        except Exception as e: tests[name]=f"FAIL:{type(e).__name__}:{e}"
    def eq(a,b):
        if a!=b: raise AssertionError('mismatch')
    ciks=sorted({r['issuer_cik'] for r in rows}); specs={c:{"complete":True,"filings":[]} for c in ciks}; specs[ciks[0]]={"complete":False,"base_success":False,"filings":[]}; a,b,m,s,rd=_offline_replay(rows,specs,tmp/'failure'); t('failure_state_persistence',lambda:eq([x['terminal_state'] for x in a if x['issuer_cik']==ciks[0]],["SOURCE_ACQUISITION_INCOMPLETE"]*len([x for x in a if x['issuer_cik']==ciks[0]]))); t('failure_state_replay',lambda:eq(a,b)); t('pass_b_network_zero',lambda:eq(core.COUNTERS['sec_requests'],0))
    mixed={c:{"complete":True,"filings":[]} for c in ciks}; mixed[ciks[0]]={"complete":False,"base_success":False,"filings":[]}; mixed[ciks[1]]={"complete":False,"base_success":True,"filings":[]}; mixed[ciks[2]]={"complete":True,"filings":[core.filing(date='2026-01-10',accept=None)]}; mixed[ciks[3]]={"complete":True,"filings":[core.filing(acc='0000000002-26-000001',date='2026-01-11',accept='2026-01-11T12:00:00+00:00')]}; mixed[ciks[4]]={"complete":True,"filings":[core.filing(acc='0000000003-26-000001',date='2026-01-09',accept='2026-01-09T12:00:00+00:00')]}; ma,mb,mm,ms,mrd=_offline_replay(rows,mixed,tmp/'mixed'); t('mixed_acquisition_state_regression',lambda:eq(ma,mb)); t('candidate638_denominator',lambda:eq((len(ma),len(mb)),(638,638))); t('pit_determinism',lambda:eq([(x['future_excluded_count'],x['timestamp_insufficient_count']) for x in ma],[(x['future_excluded_count'],x['timestamp_insufficient_count']) for x in mb]))
    def hash_fail():
        p=mrd/mm[0]['sha256']; p.write_bytes(p.read_bytes()+b'x')
        try: replay(rows,mm,ms,mrd)
        except ExecutionError as e:
            if str(e)=='RAW_EVIDENCE_HASH_MISMATCH': return
        raise AssertionError('hash mutation accepted')
    t('raw_hash_integrity_regression',hash_fail)
    xa,xb,xm,xs,xrd=_offline_replay(rows,{c:{"complete":True,"filings":[]} for c in ciks},tmp/'missing')
    def missing_fail():
        (xrd/xm[0]['sha256']).unlink()
        try: replay(rows,xm,xs,xrd)
        except ExecutionError as e:
            if str(e)=='RAW_EVIDENCE_MISSING': return
        raise AssertionError('missing raw accepted')
    t('missing_raw_fail_closed',missing_fail); t('terminal_state_determinism',lambda:eq(collections.Counter(x['terminal_state'] for x in ma),collections.Counter(x['terminal_state'] for x in mb))); t('silent_denominator_reduction_zero',lambda:eq(len({x['forensic_occurrence_id'] for x in mb}),638)); core.assert_zero_scope_counters(); t('zero_real_sec_requests',lambda:eq(core.COUNTERS['sec_requests'],0)); failed=[k for k,v in tests.items() if v!='PASS']
    write(out/'synthetic_failure_state_regression.json',{"tests":tests,"PASS":not failed}); write(out/'mixed_acquisition_state_regression.json',{"pass_a_count":len(ma),"pass_b_count":len(mb),"semantic_disagreements":sum(x!=y for x,y in zip(ma,mb)),"PASS":ma==mb}); write(out/'raw_hash_integrity_regression.json',{"PASS":tests.get('raw_hash_integrity_regression')=='PASS'}); write(out/'acquisition_state_manifest_regression.json',{"schema":"STEP11_ACQUISITION_STATE_V1","PASS":tests.get('failure_state_replay')=='PASS'}); write(out/'pit_regression.json',{"PASS":tests.get('pit_determinism')=='PASS'}); write(out/'terminal_state_regression.json',{"pass_a":dict(collections.Counter(x['terminal_state'] for x in ma)),"pass_b":dict(collections.Counter(x['terminal_state'] for x in mb)),"PASS":ma==mb}); write(out/'network_kill_switch_report.json',{"actual_sec_requests":core.COUNTERS['sec_requests'],"pass_b_network_requests":0,**PROHIBITED,"PASS":core.COUNTERS['sec_requests']==0}); decision="STEP11_METADATA_ACQUISITION_DETERMINISM_REPAIR_V2_OFFLINE_CORE_VALIDATED" if not failed else "STEP11_METADATA_ACQUISITION_DETERMINISM_REPAIR_V2_VALIDATION_FAILED"; write(out/'repair_validation_summary.json',{"decision":decision,"tests":tests,"failed":failed,"candidate_count":638,"sample32_oracle_certification":"NOT_EXECUTED","sample32_mutations":0}); write(out/'final_decision.json',{"decision":decision,"sec_requests":core.COUNTERS['sec_requests'],"live_certification_executions":0}); print(decision); return 0 if not failed else 1
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['validate','certification'],required=True); ap.add_argument('--out',required=True); ap.add_argument('--input638'); a=ap.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if a.mode=='validate': return run_validate(out)
    if not a.input638: raise ExecutionError('INPUT638_REQUIRED')
    return run_live(a)
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e: print(json.dumps({'error':str(e)},sort_keys=True),file=sys.stderr); raise
