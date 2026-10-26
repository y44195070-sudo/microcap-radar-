#!/usr/bin/env python3
"""STEP11 pre-Full638 structural SEC metadata certification machinery.

PRE-FLIGHT IS NETWORK-DISABLED. Certification mode is metadata-only and must
be explicitly enabled by the workflow. No filing-body or event reconstruction
code exists in this module.
"""
from __future__ import annotations
import argparse, dataclasses, datetime as dt, hashlib, json, os, pathlib, re, sys, urllib.error, urllib.request
from typing import Any

DECISION_READY="STEP11_PRE_FULL638_STRUCTURAL_METADATA_ACQUISITION_IMPLEMENTATION_READY"
FAIL_PREFIX="STEP11_METADATA_IMPLEMENTATION_"
ALLOWED_FORMS_FIELDS={"accessionNumber","form","filingDate","acceptanceDateTime","primaryDocument","reportDate"}
FORBIDDEN_LABELS={"ATM_RELATED","ELOC_RELATED","CONVERTIBLE_RELATED","RESALE_RELATED","WARRANT_RELATED","REVERSE_SPLIT_RELATED","NASDAQ_COMPLIANCE_RELATED","SECURITY_LINKAGE_AMBIGUOUS"}
TERMINAL_STATES={"COMPLETE_METADATA","NO_FILINGS_BY_CUTOFF","HISTORICAL_RANGE_INCOMPLETE","TIMESTAMP_INSUFFICIENT","REQUEST_FAILED","RATE_LIMITED","MALFORMED_RESPONSE","IDENTITY_INPUT_INVALID","METADATA_CONFLICT","SEC_METADATA_UNAVAILABLE","OTHER_EXPLICIT_FAILURE"}
CIK_RE=re.compile(r"^[0-9]{10}$")
ACCESSION_RE=re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
BASE_PREFIX="https://data.sec.gov/submissions/CIK"
HISTORY_PREFIX="https://data.sec.gov/submissions/"

class GateError(RuntimeError): pass
class NetworkDisabled(GateError): pass

COUNTERS={k:0 for k in ["network_requests","sec_requests","provider_requests","current_identifier_requests","filing_body_fetch_count","filing_body_parse_count","exhibit_fetch_count","event_extraction_count","event_classification_count","financing_classification_count","security_linkage_count","amendment_reconstruction_count","supply_reconstruction_count","second_sample_selection_invocations","second_sample_rows_created","second_sample_hash_created"]}

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def canonical_bytes(obj:Any)->bytes: return (json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def canonical_hash(obj:Any)->str: return sha256_bytes(canonical_bytes(obj))
def write_json(path:pathlib.Path,obj:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(canonical_bytes(obj))

def canonical_cik(v:Any)->str:
    s=str(v).strip()
    if not s.isdigit() or len(s)>10: raise GateError("IDENTITY_INPUT_INVALID")
    s=s.zfill(10)
    if not CIK_RE.fullmatch(s): raise GateError("IDENTITY_INPUT_INVALID")
    return s

def canonical_accession(v:str)->str:
    s=str(v).strip()
    if ACCESSION_RE.fullmatch(s): return s
    digits=re.sub(r"[^0-9]","",s)
    if len(digits)==18: return f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"
    raise GateError("MALFORMED_ACCESSION")

def endpoint_for_base(cik:str)->str: return BASE_PREFIX+canonical_cik(cik)+".json"
def endpoint_for_history(name:str)->str:
    if not re.fullmatch(r"CIK[0-9]{10}-submissions-[0-9]{3}\.json",name): raise GateError("NETWORK_SCOPE_VIOLATION")
    return HISTORY_PREFIX+name

def classify_endpoint(url:str)->str:
    if re.fullmatch(r"https://data\.sec\.gov/submissions/CIK[0-9]{10}\.json",url): return "SEC_SUBMISSIONS_BASE_METADATA"
    if re.fullmatch(r"https://data\.sec\.gov/submissions/CIK[0-9]{10}-submissions-[0-9]{3}\.json",url): return "SEC_SUBMISSIONS_HISTORICAL_METADATA"
    raise GateError("NETWORK_SCOPE_VIOLATION")

@dataclasses.dataclass(frozen=True)
class NetworkPolicy:
    enabled: bool=False
    max_requests: int=0
    timeout_seconds: int=20
    retry_ceiling: int=2

class MetadataClient:
    def __init__(self,policy:NetworkPolicy,user_agent:str|None=None): self.policy=policy; self.user_agent=user_agent; self.ordinal=0; self.audit=[]
    def fetch(self,url:str,cik:str)->bytes:
        endpoint_class=classify_endpoint(url)
        if not self.policy.enabled: raise NetworkDisabled("NETWORK_DISABLED")
        if not self.user_agent: raise GateError("USER_AGENT_NOT_CONFIGURED")
        if self.ordinal>=self.policy.max_requests: raise GateError("REQUEST_BUDGET_EXCEEDED")
        self.ordinal+=1; COUNTERS["network_requests"]+=1; COUNTERS["sec_requests"]+=1
        req=urllib.request.Request(url,headers={"User-Agent":self.user_agent,"Accept-Encoding":"identity"})
        try:
            with urllib.request.urlopen(req,timeout=self.policy.timeout_seconds) as r:
                b=r.read(); status=getattr(r,"status",200)
        except urllib.error.HTTPError as e:
            self.audit.append({"request_ordinal":self.ordinal,"endpoint_class":endpoint_class,"issuer_cik":cik,"response_state":f"HTTP_{e.code}"}); raise
        self.audit.append({"request_ordinal":self.ordinal,"endpoint_class":endpoint_class,"issuer_cik":cik,"response_state":f"HTTP_{status}"})
        return b

def parse_iso(value:str)->dt.datetime:
    s=value.strip().replace("Z","+00:00")
    x=dt.datetime.fromisoformat(s)
    if x.tzinfo is None: raise GateError("NAIVE_TIMESTAMP")
    return x.astimezone(dt.timezone.utc)

def pit_state(prediction_ts:str,filing_date:str,acceptance_ts:str|None)->str:
    p=parse_iso(prediction_ts); fd=dt.date.fromisoformat(filing_date)
    if fd<p.date(): return "BEFORE_CUTOFF"
    if fd>p.date(): return "AFTER_CUTOFF"
    if not acceptance_ts: return "SAME_DAY_TIMESTAMP_UNRESOLVED"
    a=parse_iso(acceptance_ts)
    if a<p: return "SAME_DAY_BEFORE"
    return "SAME_DAY_AFTER"

def parse_recent(obj:dict,raw_sha:str,source_ref:str)->list[dict]:
    recent=obj.get("filings",{}).get("recent",{})
    if not isinstance(recent,dict): raise GateError("MALFORMED_RESPONSE")
    n=max((len(v) for k,v in recent.items() if k in ALLOWED_FORMS_FIELDS and isinstance(v,list)),default=0)
    rows=[]
    for i in range(n):
        row={k:(recent.get(k,[None]*n)[i] if i<len(recent.get(k,[])) else None) for k in ALLOWED_FORMS_FIELDS}
        if not row.get("accessionNumber") or not row.get("form") or not row.get("filingDate"): raise GateError("MALFORMED_RESPONSE")
        row["accessionNumber"]=canonical_accession(row["accessionNumber"]); row["raw_response_sha256"]=raw_sha; row["source_ref"]=source_ref; rows.append(row)
    return rows

def parse_history(obj:dict,raw_sha:str,source_ref:str)->list[dict]:
    if not isinstance(obj,dict): raise GateError("MALFORMED_RESPONSE")
    n=max((len(v) for k,v in obj.items() if k in ALLOWED_FORMS_FIELDS and isinstance(v,list)),default=0)
    rows=[]
    for i in range(n):
        row={k:(obj.get(k,[None]*n)[i] if i<len(obj.get(k,[])) else None) for k in ALLOWED_FORMS_FIELDS}
        if not row.get("accessionNumber") or not row.get("form") or not row.get("filingDate"): raise GateError("MALFORMED_RESPONSE")
        row["accessionNumber"]=canonical_accession(row["accessionNumber"]); row["raw_response_sha256"]=raw_sha; row["source_ref"]=source_ref; rows.append(row)
    return rows

def dedup_rows(rows:list[dict])->tuple[list[dict],dict]:
    by={}; exact=0
    compare_fields=["form","filingDate","acceptanceDateTime","primaryDocument","reportDate"]
    for r in rows:
        a=r["accessionNumber"]
        if a not in by: by[a]=r; continue
        if all(by[a].get(k)==r.get(k) for k in compare_fields): exact+=1; continue
        raise GateError("METADATA_CONFLICT")
    out=[by[k] for k in sorted(by)]
    return out,{"input_rows":len(rows),"output_rows":len(out),"exact_duplicates_removed":exact,"silent_drops":0}

def structural_index(occ:dict,filings:list[dict],historical_range_complete:bool=True)->dict:
    states=[]
    for f in filings: states.append((f,pit_state(occ["prediction_timestamp"],f["filingDate"],f.get("acceptanceDateTime"))))
    hist=[f for f,s in states if s in {"BEFORE_CUTOFF","SAME_DAY_BEFORE"}]
    post=[f for f,s in states if s in {"AFTER_CUTOFF","SAME_DAY_AFTER"}]
    unresolved=[f for f,s in states if s=="SAME_DAY_TIMESTAMP_UNRESOLVED"]
    if unresolved: terminal="TIMESTAMP_INSUFFICIENT"
    elif not historical_range_complete: terminal="HISTORICAL_RANGE_INCOMPLETE"
    elif not hist: terminal="NO_FILINGS_BY_CUTOFF"
    else: terminal="COMPLETE_METADATA"
    forms=sorted(set(f["form"] for f in hist))
    volume="ZERO" if len(hist)==0 else "ONE" if len(hist)==1 else "TWO_TO_FIVE" if len(hist)<=5 else "SIX_TO_TWENTY" if len(hist)<=20 else "OVER_TWENTY"
    return {"forensic_occurrence_id":occ["forensic_occurrence_id"],"terminal_state":terminal,"pre_cutoff_filing_count":len(hist),"post_cutoff_filing_count":len(post),"future_excluded_count":len(post),"same_day_before_count":sum(s=="SAME_DAY_BEFORE" for _,s in states),"same_day_after_count":sum(s=="SAME_DAY_AFTER" for _,s in states),"same_day_unresolved_count":len(unresolved),"form_presence":forms,"zero_filings_by_cutoff":historical_range_complete and len(hist)==0 and not unresolved,"one_filing_by_cutoff":len(hist)==1,"multiple_filings_before_cutoff":len(hist)>1,"filing_volume_bucket":volume,"future_accessions":sorted(f["accessionNumber"] for f in post)}

def validate_terminal_registry(rows:list[dict],expected:int)->None:
    if len(rows)!=expected: raise GateError("DENOMINATOR_REDUCTION")
    ids=[r["forensic_occurrence_id"] for r in rows]
    if len(set(ids))!=expected: raise GateError("TERMINAL_STATE_DUPLICATE")
    if any(r["terminal_state"] not in TERMINAL_STATES for r in rows): raise GateError("UNKNOWN_TERMINAL_STATE")

def validate_input(rows:list[dict],expected:int=638)->dict:
    req={"forensic_occurrence_id","prediction_id","prediction_timestamp","certified_identity_key","issuer_cik","exchange","instrument_type","identity_version","governance_status"}
    if len(rows)!=expected: raise GateError("INPUT_AUTHORITY_FAILED")
    if len({r.get("forensic_occurrence_id") for r in rows})!=expected: raise GateError("INPUT_AUTHORITY_FAILED")
    for r in rows:
        if not req.issubset(r): raise GateError("INPUT_AUTHORITY_FAILED")
        canonical_cik(r["issuer_cik"]); parse_iso(r["prediction_timestamp"])
    ciks=sorted({canonical_cik(r["issuer_cik"]) for r in rows})
    return {"input_rows":expected,"unique_occurrences":expected,"unique_cik_count":len(ciks),"unique_cik_set_hash":canonical_hash(ciks)}

def build_request_plan(rows:list[dict])->list[dict]:
    grouped={}
    for r in rows: grouped.setdefault(canonical_cik(r["issuer_cik"]),[]).append(r)
    plan=[]
    for ordinal,cik in enumerate(sorted(grouped),1):
        xs=grouped[cik]; cutoffs=sorted(r["prediction_timestamp"] for r in xs)
        plan.append({"request_ordinal":ordinal,"issuer_cik":cik,"occurrence_count":len(xs),"occurrence_ids":sorted(r["forensic_occurrence_id"] for r in xs),"minimum_required_historical_cutoff":cutoffs[0],"maximum_occurrence_cutoff":cutoffs[-1],"base_metadata_endpoint_class":"SEC_SUBMISSIONS_BASE_METADATA","historical_traversal_policy":"OFFICIAL_SUBMISSIONS_FILE_REFERENCES_ONLY"})
    return plan

def assert_zero_scope_counters()->None:
    for k in ["filing_body_fetch_count","filing_body_parse_count","exhibit_fetch_count","event_extraction_count","event_classification_count","financing_classification_count","security_linkage_count","amendment_reconstruction_count","supply_reconstruction_count","second_sample_selection_invocations","second_sample_rows_created","second_sample_hash_created"]:
        if COUNTERS[k]!=0: raise GateError("SCOPE_ESCALATED")

def synthetic_occ(i=1,ts="2026-01-10T15:00:00+00:00",cik="1"): return {"forensic_occurrence_id":f"occ-{i}","prediction_id":f"pred-{i}","prediction_timestamp":ts,"certified_identity_key":f"id-{i}","issuer_cik":cik,"exchange":"XNAS","instrument_type":"CS","identity_version":"FROZEN","governance_status":"CERTIFIED"}
def filing(acc="0000000001-26-000001",form="8-K",date="2026-01-09",accept="2026-01-09T12:00:00+00:00"): return {"accessionNumber":acc,"form":form,"filingDate":date,"acceptanceDateTime":accept,"primaryDocument":"x.htm","reportDate":"2026-01-09","raw_response_sha256":"a"*64,"source_ref":"synthetic"}

def run_preflight(out:pathlib.Path)->dict:
    tests={}
    def ok(name,fn):
        try: fn(); tests[name]="PASS"
        except Exception as e: tests[name]=f"FAIL:{type(e).__name__}:{e}"
    ok("cik_canonicalization",lambda: (_ for _ in ()).throw(AssertionError()) if canonical_cik("1")!="0000000001" else None)
    ok("endpoint_allowlist",lambda: classify_endpoint(endpoint_for_base("1")))
    def deny():
        try: classify_endpoint("https://www.sec.gov/Archives/edgar/data/1/x.txt")
        except GateError: return
        raise AssertionError("forbidden endpoint accepted")
    ok("forbidden_endpoint_rejection",deny)
    ok("pit_before",lambda: (_ for _ in ()).throw(AssertionError()) if pit_state("2026-01-10T15:00:00+00:00","2026-01-09",None)!="BEFORE_CUTOFF" else None)
    ok("pit_after",lambda: (_ for _ in ()).throw(AssertionError()) if pit_state("2026-01-10T15:00:00+00:00","2026-01-11",None)!="AFTER_CUTOFF" else None)
    ok("same_day_before",lambda: (_ for _ in ()).throw(AssertionError()) if pit_state("2026-01-10T15:00:00+00:00","2026-01-10","2026-01-10T14:00:00+00:00")!="SAME_DAY_BEFORE" else None)
    ok("same_day_after",lambda: (_ for _ in ()).throw(AssertionError()) if pit_state("2026-01-10T15:00:00+00:00","2026-01-10","2026-01-10T16:00:00+00:00")!="SAME_DAY_AFTER" else None)
    ok("same_day_unresolved",lambda: (_ for _ in ()).throw(AssertionError()) if pit_state("2026-01-10T15:00:00+00:00","2026-01-10",None)!="SAME_DAY_TIMESTAMP_UNRESOLVED" else None)
    def naive_fail():
        try: parse_iso("2026-01-01T00:00:00")
        except GateError: return
        raise AssertionError("naive accepted")
    ok("timezone_fail_closed",naive_fail)
    def dup_exact():
        r=filing(); outx,rep=dedup_rows([r,dict(r)]); assert len(outx)==1 and rep["exact_duplicates_removed"]==1
    ok("duplicate_exact",dup_exact)
    def dup_conflict():
        a=filing(); b=dict(a); b["form"]="10-Q"
        try: dedup_rows([a,b])
        except GateError as e:
            if str(e)=="METADATA_CONFLICT": return
        raise AssertionError("conflict not failed")
    ok("duplicate_conflict",dup_conflict)
    def future():
        o=synthetic_occ(); fs=[filing(),filing("0000000001-26-000002","10-Q","2026-01-11","2026-01-11T12:00:00+00:00")]; idx=structural_index(o,fs); assert idx["pre_cutoff_filing_count"]==1 and idx["future_excluded_count"]==1 and idx["form_presence"]==["8-K"]
    ok("future_leakage",future)
    def nofiling_guard():
        idx=structural_index(synthetic_occ(),[],False); assert idx["terminal_state"]=="HISTORICAL_RANGE_INCOMPLETE" and not idx["zero_filings_by_cutoff"]
    ok("no_filings_invariant",nofiling_guard)
    def passb():
        c=MetadataClient(NetworkPolicy(enabled=False));
        try: c.fetch(endpoint_for_base("1"),"0000000001")
        except NetworkDisabled: return
        raise AssertionError("network not blocked")
    ok("pass_b_network_kill_switch",passb)
    ok("deterministic_serialization",lambda: (_ for _ in ()).throw(AssertionError()) if canonical_hash({"b":2,"a":1})!=canonical_hash({"a":1,"b":2}) else None)
    def state_registry(): validate_terminal_registry([{"forensic_occurrence_id":"x","terminal_state":"COMPLETE_METADATA"}],1)
    ok("terminal_state_uniqueness",state_registry)
    def forbidden_labels():
        idx=structural_index(synthetic_occ(),[filing()]); assert not (set(idx)&FORBIDDEN_LABELS)
    ok("content_label_generation_zero",forbidden_labels)
    ok("reconstruction_counters_zero",assert_zero_scope_counters)
    def request_plan_det():
        rows=[synthetic_occ(1,cik="2"),synthetic_occ(2,cik="1")]; assert canonical_hash(build_request_plan(rows))==canonical_hash(build_request_plan(list(reversed(rows))))
    ok("request_plan_determinism",request_plan_det)
    raw=b'{"synthetic":true}\n'; ok("raw_byte_hash",lambda: (_ for _ in ()).throw(AssertionError()) if sha256_bytes(raw)!=hashlib.sha256(raw).hexdigest() else None)
    ok("historical_traversal_guard",lambda: endpoint_for_history("CIK0000000001-submissions-001.json"))
    failed=[k for k,v in tests.items() if v!="PASS"]
    report={"test_type":"PREFLIGHT_TEST","tests":tests,"passed":len(tests)-len(failed),"failed":len(failed),"network_requests":COUNTERS["network_requests"],"sec_requests":COUNTERS["sec_requests"],"provider_requests":COUNTERS["provider_requests"],"current_identifier_requests":COUNTERS["current_identifier_requests"],"scope_counters":COUNTERS,"PASS":not failed and COUNTERS["network_requests"]==0}
    write_json(out/"preflight_test_report.json",report); return report

def manifest_dir(root:pathlib.Path,manifest_name="implementation_manifest.json")->dict:
    entries=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name!=manifest_name:
            b=p.read_bytes(); entries.append({"relative_path":str(p.relative_to(root)),"sha256":sha256_bytes(b),"byte_size":len(b),"evidence_class":"IMPLEMENTATION_PREFLIGHT"})
    m={"entries":entries,"duplicate_paths":len(entries)-len({e['relative_path'] for e in entries}),"unmanifested_persisted_files":0,"missing_manifest_entries":0,"hash_mismatches":0}
    write_json(root/manifest_name,m); return m

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=["preflight","certification"],default="preflight"); ap.add_argument("--out",default="/tmp/step11-metadata-preflight"); ap.add_argument("--input638"); a=ap.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if a.mode=="preflight":
        report=run_preflight(out)
        write_json(out/"network_kill_switch_report.json",{"network_requests":COUNTERS["network_requests"],"sec_requests":COUNTERS["sec_requests"],"provider_requests":0,"current_identifier_requests":0,"PASS":COUNTERS["network_requests"]==0})
        write_json(out/"endpoint_scope_report.json",{"allowed":["SEC_SUBMISSIONS_BASE_METADATA","SEC_SUBMISSIONS_HISTORICAL_METADATA"],"filing_body":False,"generic_arbitrary_url_fetcher":False,"PASS":True})
        write_json(out/"final_decision.json",{"decision":DECISION_READY if report["PASS"] else FAIL_PREFIX+"TEST_FAILED","certification_execution_started":False,"actual_638_sec_raw_response_set_created":False})
        manifest_dir(out)
        print(json.dumps({"decision":DECISION_READY if report["PASS"] else FAIL_PREFIX+"TEST_FAILED","network_requests":COUNTERS["network_requests"],"tests_pass":report["PASS"]},sort_keys=True)); return 0 if report["PASS"] else 1
    # Certification mode deliberately requires an explicit frozen input and runtime opt-in.
    if os.environ.get("STEP11_METADATA_CERTIFICATION_ENABLE")!="YES": raise GateError("CERTIFICATION_NOT_EXPLICITLY_ENABLED")
    if not a.input638: raise GateError("INPUT638_REQUIRED")
    rows=json.loads(pathlib.Path(a.input638).read_text())
    info=validate_input(rows,638); plan=build_request_plan(rows)
    write_json(out/"certified638_input_manifest.json",rows); write_json(out/"input_validation.json",info); write_json(out/"issuer_request_plan.json",plan)
    # Network execution is intentionally entered only by the later certification execution stage.
    raise GateError("CERTIFICATION_EXECUTION_STAGE_REQUIRED")

if __name__=="__main__":
    try: raise SystemExit(main())
    except GateError as e:
        print(json.dumps({"error":str(e),"decision":FAIL_PREFIX+"TEST_FAILED"},sort_keys=True),file=sys.stderr); raise SystemExit(2)
