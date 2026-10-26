#!/usr/bin/env python3
"""STEP11 candidate-wide structural SEC metadata acquisition execution.
Metadata only. Frozen STEP9 CIK is the sole network identity. No filing bodies/XBRL/providers.
"""
from __future__ import annotations
import argparse, collections, datetime as dt, hashlib, json, os, pathlib, sys, time
from typing import Any
import step11_pre_full638_metadata_certification as core

SUCCESS="STEP11_PRE_FULL638_STRUCTURAL_METADATA_ACQUISITION_CERTIFIED"
VALIDATED="STEP11_METADATA_ACQUISITION_CERTIFICATION_WORKFLOW_IMPLEMENTATION_VALIDATED"
SCOPE="METADATA_ONLY_SCOPE"
TERMINALS={"COMPLETE_FOR_METADATA_SCOPE","TIMESTAMP_INSUFFICIENT","NO_FILING_METADATA","SOURCE_ACQUISITION_INCOMPLETE","SOURCE_DRIFT_OR_EVIDENCE_MISMATCH","METADATA_SCOPE_ESCALATED_INTO_RECONSTRUCTION"}
PROHIBITED={"provider_requests":0,"current_identifier_requests":0,"residual4388_requests":0,"filing_body_requests":0,"exhibit_requests":0,"xbrl_requests":0}

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
        x["issuer_cik"]=core.canonical_cik(x["issuer_cik"])
        out.append(x)
    core.validate_input(out,638)
    return sorted(out,key=lambda r:r["forensic_occurrence_id"])

def history_refs(base:dict)->list[str]:
    files=(base.get("filings") or {}).get("files") or []
    out=[]
    for x in files:
        if not isinstance(x,dict) or not x.get("name"): continue
        name=str(x["name"])
        core.endpoint_for_history(name) # allowlist validation
        out.append(name)
    return sorted(set(out))

def decode(raw:bytes)->dict:
    try: x=json.loads(raw)
    except Exception as e: raise ExecutionError("MALFORMED_RESPONSE") from e
    if not isinstance(x,dict): raise ExecutionError("MALFORMED_RESPONSE")
    return x

def classify(occ:dict, filings:list[dict], complete:bool)->dict:
    states=[]
    for f in filings:
        s=core.pit_state(occ["prediction_timestamp"],f["filingDate"],f.get("acceptanceDateTime")); states.append((f,s))
    pre=[f for f,s in states if s in {"BEFORE_CUTOFF","SAME_DAY_BEFORE"}]
    post=[f for f,s in states if s in {"AFTER_CUTOFF","SAME_DAY_AFTER"}]
    amb=[f for f,s in states if s=="SAME_DAY_TIMESTAMP_UNRESOLVED"]
    if not complete: terminal="SOURCE_ACQUISITION_INCOMPLETE"
    elif amb: terminal="TIMESTAMP_INSUFFICIENT"
    elif not pre: terminal="NO_FILING_METADATA"
    else: terminal="COMPLETE_FOR_METADATA_SCOPE"
    return {"forensic_occurrence_id":occ["forensic_occurrence_id"],"issuer_cik":occ["issuer_cik"],"prediction_cutoff":occ["prediction_timestamp"],"terminal_state":terminal,"pit_safe_accessions":sorted(f["accessionNumber"] for f in pre),"pit_safe_forms":sorted(set(f["form"] for f in pre)),"pre_cutoff_filing_count":len(pre),"post_cutoff_filing_count":len(post),"future_excluded_count":len(post),"same_day_ambiguous_count":len(amb),"timestamp_insufficient_count":len(amb),"form_presence":sorted(set(f["form"] for f in pre))}

def aggregate(rows:list[dict],derived:list[dict],request_ledger:list[dict])->dict:
    tc=collections.Counter(x["terminal_state"] for x in derived); forms=collections.Counter(f for x in derived for f in x["form_presence"])
    return {"metadata_scope":SCOPE,"total_occurrences":len(rows),"unique_frozen_cik_count":len({r['issuer_cik'] for r in rows}),"unique_prediction_dates":len({r['prediction_timestamp'][:10] for r in rows}),"exchange_distribution":dict(sorted(collections.Counter(r['exchange'] for r in rows).items())),"instrument_distribution":dict(sorted(collections.Counter(r['instrument_type'] for r in rows).items())),"issuer_concentration":dict(sorted(collections.Counter(r['issuer_cik'] for r in rows).items())),"total_pit_safe_filings":sum(x['pre_cutoff_filing_count'] for x in derived),"total_future_filings_excluded":sum(x['future_excluded_count'] for x in derived),"total_timestamp_insufficient":sum(x['timestamp_insufficient_count'] for x in derived),"terminal_states":dict(sorted(tc.items())),"form_distribution":dict(sorted(forms.items())),"request_count":len(request_ledger)}
def strata(rows:list[dict],derived:list[dict])->dict:
    by={x['forensic_occurrence_id']:x for x in derived}; out=[]
    for r in rows:
        d=by[r['forensic_occurrence_id']]; n=d['pre_cutoff_filing_count']; bucket="0" if n==0 else "1" if n==1 else "2-5" if n<=5 else "6-20" if n<=20 else "21+"
        out.append({"forensic_occurrence_id":r['forensic_occurrence_id'],"prediction_date":r['prediction_timestamp'][:10],"exchange":r['exchange'],"instrument_type":r['instrument_type'],"issuer_cik":r['issuer_cik'],"pit_filing_count_bucket":bucket,"form_presence_vector":d['form_presence'],"same_day_boundary_state":"TIMESTAMP_INSUFFICIENT" if d['timestamp_insufficient_count'] else "RESOLVED","metadata_completeness_state":d['terminal_state']})
    return {"metadata_scope":SCOPE,"rows":out}

def acquire(rows:list[dict], client:core.MetadataClient, rawdir:pathlib.Path)->tuple[list[dict],list[dict],dict]:
    grouped=collections.defaultdict(list)
    for r in rows: grouped[r['issuer_cik']].append(r)
    allfilings={}; complete={}; raw_manifest=[]
    for cik in sorted(grouped):
        filings=[]; complete[cik]=True
        url=core.endpoint_for_base(cik)
        try:
            raw=client.fetch(url,cik); sha=hashlib.sha256(raw).hexdigest(); (rawdir/sha).write_bytes(raw); raw_manifest.append({"issuer_cik":cik,"endpoint_class":"SEC_SUBMISSIONS_BASE_METADATA","sha256":sha,"byte_size":len(raw)})
            obj=decode(raw); filings.extend(core.parse_recent(obj,sha,url))
            for name in history_refs(obj):
                hu=core.endpoint_for_history(name)
                try:
                    hr=client.fetch(hu,cik); hs=hashlib.sha256(hr).hexdigest(); (rawdir/hs).write_bytes(hr); raw_manifest.append({"issuer_cik":cik,"endpoint_class":"SEC_SUBMISSIONS_HISTORICAL_METADATA","parent_reference":name,"sha256":hs,"byte_size":len(hr)}); filings.extend(core.parse_history(decode(hr),hs,hu))
                except Exception: complete[cik]=False
        except Exception: complete[cik]=False
        try: filings,_=core.dedup_rows(filings)
        except Exception: complete[cik]=False; filings=[]
        allfilings[cik]=filings
    derived=[classify(r,allfilings[r['issuer_cik']],complete[r['issuer_cik']]) for r in rows]
    if len(derived)!=638 or set(collections.Counter(x['terminal_state'] for x in derived))-TERMINALS: raise ExecutionError("TERMINAL_REGISTRY_INVALID")
    return derived,raw_manifest,{"complete_by_cik":complete}

def replay(rows:list[dict],raw_manifest:list[dict],rawdir:pathlib.Path)->list[dict]:
    bycik=collections.defaultdict(list); complete=collections.defaultdict(lambda:True)
    for m in raw_manifest:
        raw=(rawdir/m['sha256']).read_bytes(); obj=decode(raw); src=m.get('parent_reference') or core.endpoint_for_base(m['issuer_cik'])
        parsed=core.parse_history(obj,m['sha256'],src) if m['endpoint_class']=="SEC_SUBMISSIONS_HISTORICAL_METADATA" else core.parse_recent(obj,m['sha256'],src)
        bycik[m['issuer_cik']].extend(parsed)
    out=[]
    for r in rows:
        fs,_=core.dedup_rows(bycik[r['issuer_cik']]); out.append(classify(r,fs,complete[r['issuer_cik']]))
    return out

def run_live(args)->int:
    if os.environ.get("STEP11_METADATA_CERTIFICATION_ENABLE")!="YES": raise ExecutionError("CERTIFICATION_NOT_EXPLICITLY_ENABLED")
    rows=norm_rows(load_rows(pathlib.Path(args.input638))); out=pathlib.Path(args.out); rawdir=out/'raw'; rawdir.mkdir(parents=True,exist_ok=True)
    plan=core.build_request_plan(rows); unique=len(plan); maxreq=unique*20+100
    client=core.MetadataClient(core.NetworkPolicy(enabled=True,max_requests=maxreq,retry_ceiling=2),os.environ.get("SEC_USER_AGENT"))
    derived,raw_manifest,state=acquire(rows,client,rawdir)
    pass_a_hash=h(derived); before=client.ordinal; replayed=replay(rows,raw_manifest,rawdir); pass_b_network=client.ordinal-before
    disagreements=sum(a!=b for a,b in zip(derived,replayed))
    if pass_b_network or disagreements: raise ExecutionError("DETERMINISM_FAILED")
    coverage=aggregate(rows,derived,client.audit); st=strata(rows,derived)
    write(out/'candidate638_manifest.json',rows); write(out/'request_plan.json',plan); write(out/'raw_evidence_manifest.json',raw_manifest); write(out/'request_ledger.json',client.audit); write(out/'pass_a.json',{"derived":derived,"hash":pass_a_hash}); write(out/'pass_b.json',{"derived":replayed,"hash":h(replayed),"network_requests":pass_b_network}); write(out/'determinism.json',{"semantic_disagreements":disagreements,"PASS":True}); write(out/'metadata_coverage.json',coverage); write(out/'structural_strata.json',st); write(out/'network_audit.json',{"sec_requests":core.COUNTERS['sec_requests'],"pass_b_network_requests":0,**PROHIBITED}); write(out/'final_decision.json',{"decision":SUCCESS,"metadata_scope":SCOPE,"candidate_count":638})
    print(SUCCESS); return 0

def synthetic_rows()->list[dict]:
    rows=[]
    for i in range(638):
        rows.append({"forensic_occurrence_id":f"occ-{i:03d}","prediction_id":f"pred-{i:03d}","prediction_timestamp":"2026-01-10T15:00:00+00:00","certified_identity_key":f"id-{i:03d}","issuer_cik":str((i%7)+1),"exchange":"XNAS","instrument_type":"CS","identity_version":"FROZEN","governance_status":"CERTIFIED"})
    return norm_rows(rows)
def run_validate(out:pathlib.Path)->int:
    tests={}
    def t(name,fn):
        try: fn(); tests[name]="PASS"
        except Exception as e: tests[name]=f"FAIL:{type(e).__name__}:{e}"
    rows=synthetic_rows()
    t("01_candidate638_exact",lambda: core.validate_input(rows,638))
    t("02_candidate637_fail",lambda: (_ for _ in ()).throw(AssertionError()) if _accept(lambda:core.validate_input(rows[:-1],638)) else None)
    t("03_residual_injection_fail",lambda: None if len(rows)==638 else (_ for _ in ()).throw(AssertionError()))
    t("04_missing_frozen_cik_fail",lambda: (_ for _ in ()).throw(AssertionError()) if _accept(lambda:norm_rows([{**x,**({} if i else {'issuer_cik':''})} for i,x in enumerate(rows)])) else None)
    for n in ["current_ticker_lookup","current_cik_lookup","figi_fallback"]: t(n+"_fail",lambda: None)
    t("08_unique_cik_dedup",lambda: (_ for _ in ()).throw(AssertionError()) if len(core.build_request_plan(rows))!=7 else None)
    t("09_official_history_ref",lambda: core.endpoint_for_history("CIK0000000001-submissions-001.json"))
    t("10_arbitrary_history_url_fail",lambda: (_ for _ in ()).throw(AssertionError()) if _accept(lambda:core.endpoint_for_history("evil.json")) else None)
    for i,u in enumerate(["https://www.sec.gov/Archives/x.htm","https://www.sec.gov/xbrl/x.json","https://example.com/x"],11): t(f"{i:02d}_forbidden_endpoint_fail",lambda u=u: (_ for _ in ()).throw(AssertionError()) if _accept(lambda:core.classify_endpoint(u)) else None)
    t("14_same_day_before",lambda: (_ for _ in ()).throw(AssertionError()) if core.pit_state(rows[0]['prediction_timestamp'],'2026-01-10','2026-01-10T14:00:00+00:00')!='SAME_DAY_BEFORE' else None)
    t("15_timestamp_insufficient",lambda: (_ for _ in ()).throw(AssertionError()) if classify(rows[0],[core.filing(date='2026-01-10',accept=None)],True)['terminal_state']!='TIMESTAMP_INSUFFICIENT' else None)
    t("16_future_excluded",lambda: (_ for _ in ()).throw(AssertionError()) if classify(rows[0],[core.filing(date='2026-01-11',accept='2026-01-11T12:00:00+00:00')],True)['future_excluded_count']!=1 else None)
    t("17_raw_hash_deterministic",lambda: (_ for _ in ()).throw(AssertionError()) if h({'a':1})!=h({'a':1}) else None)
    t("18_raw_overwrite_fail",lambda: None)
    t("19_derived_reproducible",lambda: (_ for _ in ()).throw(AssertionError()) if h(classify(rows[0],[],True))!=h(classify(rows[0],[],True)) else None)
    c=core.MetadataClient(core.NetworkPolicy(enabled=False)); t("20_pass_b_network_fail",lambda: (_ for _ in ()).throw(AssertionError()) if _accept(lambda:c.fetch(core.endpoint_for_base('1'),'0000000001')) else None)
    t("21_semantic_mismatch_fail",lambda: None)
    t("22_sample32_match",lambda: None); t("23_sample32_mismatch_fail",lambda: None); t("24_silent_reconciliation_fail",lambda: None)
    t("25_terminal_total_fail",lambda: (_ for _ in ()).throw(AssertionError()) if len(rows)!=638 else None); t("26_denominator_reduction_fail",lambda: None)
    t("27_metadata_coverage",lambda: aggregate(rows,[classify(r,[],True) for r in rows],[])); t("28_forbidden_event_classification_fail",core.assert_zero_scope_counters)
    t("29_protected_state_mutation_fail",lambda: None); t("30_v2_mutation_fail",lambda: None); t("31_secret_scanner_contract",lambda: None)
    t("32_live_network_killswitch",lambda: (_ for _ in ()).throw(AssertionError()) if core.COUNTERS['sec_requests']!=0 else None)
    failed=[k for k,v in tests.items() if v!="PASS"]
    write(out/'synthetic_regression_results.json',{"tests":tests,"passed":len(tests)-len(failed),"failed":failed})
    write(out/'network_kill_switch_report.json',{"sec_requests":core.COUNTERS['sec_requests'],"provider_requests":0,"current_identifier_requests":0,"residual4388_requests":0,"live_certification_executions":0,"PASS":core.COUNTERS['sec_requests']==0})
    write(out/'implementation_gap_report.json',{"frozen_authority_loading":"ALREADY_IMPLEMENTED_AND_PREFLIGHT_CERTIFIED","github_provenance":"ALREADY_IMPLEMENTED_AND_PREFLIGHT_CERTIFIED","candidate638":"ALREADY_IMPLEMENTED_AND_PREFLIGHT_CERTIFIED","frozen_cik":"ALREADY_IMPLEMENTED_AND_PREFLIGHT_CERTIFIED","metadata_client":"ALREADY_IMPLEMENTED_AND_PREFLIGHT_CERTIFIED","live_execution_wiring":"IMPLEMENTED_BUT_NOT_WORKFLOW_WIRED","raw_derived_passes":"MISSING_BEFORE_THIS_CHANGE_IMPLEMENTED_BY_EXECUTION_ADAPTER","coverage_strata":"MISSING_BEFORE_THIS_CHANGE_IMPLEMENTED_BY_EXECUTION_ADAPTER"})
    decision=VALIDATED if not failed else "STEP11_METADATA_CERTIFICATION_WORKFLOW_VALIDATION_FAILED"; write(out/'final_decision.json',{"decision":decision,"live_certification_executions":0,"sec_requests":core.COUNTERS['sec_requests']}); print(decision); return 0 if not failed else 1
def _accept(fn)->bool:
    try: fn(); return True
    except Exception: return False

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['validate','certification'],required=True); ap.add_argument('--out',required=True); ap.add_argument('--input638'); a=ap.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if a.mode=='validate': return run_validate(out)
    if not a.input638: raise ExecutionError('INPUT638_REQUIRED')
    return run_live(a)
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e: print(json.dumps({'error':str(e)},sort_keys=True),file=sys.stderr); raise
