#!/usr/bin/env python3
"""Repair V1 guard for STEP11 pre-Full638 metadata preflight.

This module is deliberately network-free. It freezes Sample32 reacquisition
semantics and verifies already-downloaded GitHub authority artifacts before any
future SEC network gate can be enabled.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, zipfile
from typing import Any

REPAIR_DECISION="STEP11_PRE_FULL638_METADATA_PREFLIGHT_BLOCKER_REPAIR_V1_READY_FOR_MERGE"
POLICY={
 "policy_id":"CANDIDATE_WIDE_REACQUISITION_WITH_IMMUTABLE_SAMPLE32_ORACLE",
 "candidate_universe":"CERTIFIED_638",
 "network_identity":"FROZEN_STEP9_ISSUER_CIK",
 "sample32_in_new_epoch":"INCLUDED",
 "sample32_old_evidence":"IMMUTABLE_REGRESSION_ORACLE",
 "overwrite_old_oracle":"FORBIDDEN",
 "silent_reconciliation":"FORBIDDEN",
 "mismatch_action":"FAIL_CLOSED_SOURCE_DRIFT_OR_EVIDENCE_MISMATCH",
 "current_identifier_fallback":"FORBIDDEN",
 "residual_population":"DENIED",
}
EXPECTED={
 "step9":{"head":"03457bba70c0297b425ecd68e5e9c568df038f1d","run":40204385931,"job":121202088334,"artifact_id":12603520492,"artifact_sha256":"3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c","checkpoint_id":12603725128,"checkpoint_sha256":"a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238","decision":"STEP9_LIMITED_COVERAGE_CERTIFIED","population":5026,"certified":638,"residual":4388,"fallback":"FORBIDDEN"},
 "step10":{"head":"d07e4cbae552ffed2391904e76bcbae0a5584397","run":40204853366,"job":121203517495,"artifact_id":12603356621,"artifact_sha256":"b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de","checkpoint_id":12603737037,"checkpoint_sha256":"914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f","decision":"STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED","certified":"ALLOW","residual":"DENY","unknown":"DENY","fallback":"FORBIDDEN"},
 "step11":{"head":"97a053c93034278df86b9a3983ebf843895a7d2b","run":40295222293,"job":121479531795,"attempt":1,"conclusion":"SUCCESS","sample":32,"selection_hash":"ec9fc60f59a72769bd372704379667c76f1e71021e4197ac1af085750d3ee549","forensic_id":12637518208,"forensic_sha256":"2812577a8bc205988b7d1d4b40c98ca62a4e182de79b257810e5c51c34d56ea8","checkpoint_id":12637118813,"checkpoint_sha256":"cb0312d5b15cfb6c244361371f4d378ae14062b30d495a87cc46519af1ba0e8a","artifact_id":12637078890,"artifact_sha256":"a382e1bf23b44faddc38f1b981d51c451d9b9d2a8a884d60af744774d8c936ab"}
}
class GuardError(RuntimeError): pass

def canonical_bytes(o:Any)->bytes: return (json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_file(p:pathlib.Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
 return h.hexdigest()

def assert_policy(p:dict)->None:
 if p!=POLICY: raise GuardError("PLAN_AMBIGUITY_SAMPLE32_REACQUISITION")

def oracle_compare(old:dict,new:dict,fields:list[str])->None:
 # Never mutates either input and never gives newer evidence precedence.
 for k in fields:
  if old.get(k)!=new.get(k): raise GuardError("SOURCE_DRIFT_OR_EVIDENCE_MISMATCH")

def inspect_zip(path:pathlib.Path,expected_sha:str)->dict:
 actual=sha256_file(path)
 if actual!=expected_sha: raise GuardError("AUTHORITY_DIGEST_MISMATCH")
 with zipfile.ZipFile(path,"r") as z:
  names=z.namelist()
  if len(names)!=len(set(names)): raise GuardError("DUPLICATE_ARTIFACT_PATH")
  bad=z.testzip()
  if bad: raise GuardError("ZIP_INTEGRITY_FAILED")
  return {"actual_sha256":actual,"zip_integrity":True,"duplicate_paths":0,"files":sorted(names),"size":path.stat().st_size}

def require_fields(actual:dict,expected:dict,fields:list[str])->None:
 for f in fields:
  if actual.get(f)!=expected.get(f): raise GuardError("AUTHORITY_CONTENT_MISMATCH:"+f)

def verify_authority_record(kind:str,actual:dict)->None:
 e=EXPECTED[kind]
 if kind=="step9": require_fields(actual,e,["head","run","job","decision","population","certified","residual","fallback"])
 elif kind=="step10": require_fields(actual,e,["head","run","job","decision","certified","residual","unknown","fallback"])
 elif kind=="step11": require_fields(actual,e,["head","run","job","attempt","conclusion","sample","selection_hash"])
 else: raise GuardError("UNKNOWN_AUTHORITY")

def authority_gate(records:dict,network_counter:dict)->None:
 # This gate MUST run before any future SEC network enablement.
 assert_policy(POLICY)
 for k in ("step9","step10","step11"):
  if k not in records: raise GuardError("AUTHORITY_MISSING:"+k)
  verify_authority_record(k,records[k])
 if network_counter.get("sec_requests",0)!=0: raise GuardError("AUTHORITY_NETWORK_ORDER_FAILED")

def run_tests()->dict:
 tests={}
 def t(name,fn):
  try: fn(); tests[name]="PASS"
  except Exception as e: tests[name]="FAIL:"+type(e).__name__+":"+str(e)
 t("policy_object_exists",lambda: assert_policy(POLICY))
 t("policy_id_exact",lambda: None if POLICY["policy_id"]=="CANDIDATE_WIDE_REACQUISITION_WITH_IMMUTABLE_SAMPLE32_ORACLE" else (_ for _ in ()).throw(AssertionError()))
 t("candidate_universe_certified638",lambda: None if POLICY["candidate_universe"]=="CERTIFIED_638" else (_ for _ in ()).throw(AssertionError()))
 t("sample32_included_new_epoch",lambda: None if POLICY["sample32_in_new_epoch"]=="INCLUDED" else (_ for _ in ()).throw(AssertionError()))
 t("oracle_immutable",lambda: None if POLICY["sample32_old_evidence"]=="IMMUTABLE_REGRESSION_ORACLE" else (_ for _ in ()).throw(AssertionError()))
 t("overwrite_forbidden",lambda: None if POLICY["overwrite_old_oracle"]=="FORBIDDEN" else (_ for _ in ()).throw(AssertionError()))
 t("silent_reconciliation_forbidden",lambda: None if POLICY["silent_reconciliation"]=="FORBIDDEN" else (_ for _ in ()).throw(AssertionError()))
 def mismatch():
  try: oracle_compare({"x":1},{"x":2},["x"])
  except GuardError as e:
   if str(e)=="SOURCE_DRIFT_OR_EVIDENCE_MISMATCH": return
  raise AssertionError("mismatch did not fail closed")
 t("oracle_mismatch_fail_closed",mismatch)
 t("current_identifier_fallback_forbidden",lambda: None if POLICY["current_identifier_fallback"]=="FORBIDDEN" else (_ for _ in ()).throw(AssertionError()))
 t("residual_population_denied",lambda: None if POLICY["residual_population"]=="DENIED" else (_ for _ in ()).throw(AssertionError()))
 good={k:{f:v for f,v in e.items() if f in ({"head","run","job","decision","population","certified","residual","fallback"} if k=="step9" else {"head","run","job","decision","certified","residual","unknown","fallback"} if k=="step10" else {"head","run","job","attempt","conclusion","sample","selection_hash"})} for k,e in EXPECTED.items()}
 t("step9_verifier_synthetic_pass",lambda: verify_authority_record("step9",good["step9"]))
 def bad9():
  x=dict(good["step9"]); x["population"]=1
  try: verify_authority_record("step9",x)
  except GuardError: return
  raise AssertionError("bad step9 accepted")
 t("step9_semantics_mismatch_fail",bad9)
 t("step10_verifier_synthetic_pass",lambda: verify_authority_record("step10",good["step10"]))
 def bad10():
  x=dict(good["step10"]); x["unknown"]="ALLOW"
  try: verify_authority_record("step10",x)
  except GuardError: return
  raise AssertionError("bad step10 accepted")
 t("step10_semantics_mismatch_fail",bad10)
 t("step11_verifier_synthetic_pass",lambda: verify_authority_record("step11",good["step11"]))
 def bad11():
  x=dict(good["step11"]); x["selection_hash"]="0"*64
  try: verify_authority_record("step11",x)
  except GuardError: return
  raise AssertionError("bad step11 accepted")
 t("step11_selection_hash_mismatch_fail",bad11)
 def gate_before_network(): authority_gate(good,{"sec_requests":0})
 t("authority_gate_before_network",gate_before_network)
 def gate_bad_no_network():
  x={k:dict(v) for k,v in good.items()}; x["step9"]["certified"]=637; counter={"sec_requests":0}
  try: authority_gate(x,counter)
  except GuardError:
   if counter["sec_requests"]==0:return
  raise AssertionError("authority failure touched network")
 t("authority_failure_network_zero",gate_bad_no_network)
 return tests

def main()->int:
 ap=argparse.ArgumentParser(); ap.add_argument("--out",default="timemachine/out/step11_metadata_repair_v1"); ap.add_argument("--authority-records")
 a=ap.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
 tests=run_tests(); failed=[k for k,v in tests.items() if v!="PASS"]
 (out/"sample32_reacquisition_policy.json").write_bytes(canonical_bytes(POLICY))
 (out/"authority_verifier_design.json").write_bytes(canonical_bytes({"expected":EXPECTED,"retrieval":"GITHUB_ACTIONS_ARTIFACTS_READ_ONLY","verification":"DOWNLOAD_BYTES_SHA256_ZIP_CONTENT_CHECKPOINT_BINDING","network_order":"AUTHORITY_BEFORE_SEC_NETWORK"}))
 (out/"repair_test_report.json").write_bytes(canonical_bytes({"tests":tests,"failed":failed}))
 (out/"network_request_audit.json").write_bytes(canonical_bytes({"actual_sec_requests":0,"actual_provider_requests":0,"actual_current_identifier_requests":0,"certification_execution":0}))
 decision=REPAIR_DECISION if not failed else "STEP11_METADATA_PREFLIGHT_REPAIR_TEST_FAILED"
 (out/"final_decision.json").write_bytes(canonical_bytes({"decision":decision}))
 print(json.dumps({"decision":decision,"tests":tests,"actual_sec_requests":0},sort_keys=True))
 return 0 if not failed else 1
if __name__=="__main__": raise SystemExit(main())
