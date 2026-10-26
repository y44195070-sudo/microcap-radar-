#!/usr/bin/env python3
"""Fail-closed verifier for immutable STEP9/10/11 artifacts.
Payload integrity/semantics and GitHub Actions provenance are separate evidence layers.
No SEC/provider/current-identifier I/O.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, zipfile
class VerificationError(RuntimeError): pass
ARTIFACTS={
 12603520492:("step9_artifact","3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c","step9"),
 12603725128:("step9_checkpoint","a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238","step9"),
 12603356621:("step10_artifact","b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de","step10"),
 12603737037:("step10_checkpoint","914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f","step10"),
 12637518208:("step11_forensic","2812577a8bc205988b7d1d4b40c98ca62a4e182de79b257810e5c51c34d56ea8","step11"),
 12637118813:("step11_checkpoint","cb0312d5b15cfb6c244361371f4d378ae14062b30d495a87cc46519af1ba0e8a","step11"),
 12637078890:("step11_certification","a382e1bf23b44faddc38f1b981d51c451d9b9d2a8a884d60af744774d8c936ab","step11"),
}
BINDINGS={
 "step9":{"head":"03457bba70c0297b425ecd68e5e9c568df038f1d","run":40204385931,"job":121202088334},
 "step10":{"head":"d07e4cbae552ffed2391904e76bcbae0a5584397","run":40204853366,"job":121203517495},
 "step11":{"head":"97a053c93034278df86b9a3983ebf843895a7d2b","run":40295222293,"job":121479531795,"attempt":1},
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def jread(p): return json.loads(p.read_text(encoding="utf-8"))
def zjson(z,n): return json.loads(z.read(n))
def inspect_zip(p,expected):
 actual=sha(p)
 if actual!=expected: raise VerificationError(f"DIGEST_MISMATCH:{p.name}:{actual}")
 with zipfile.ZipFile(p) as z:
  names=z.namelist()
  if len(names)!=len(set(names)): raise VerificationError("DUPLICATE_PATH")
  if z.testzip(): raise VerificationError("ZIP_INTEGRITY")
 return {"sha256":actual,"size":p.stat().st_size,"files":sorted(names)}
def verify_provenance(root,aid,digest,stage):
 b=BINDINGS[stage]
 mp=root/f"artifact-{aid}.json"; rp=root/f"run-{stage}.json"; jp=root/f"jobs-{stage}.json"
 for p in (mp,rp,jp):
  if not p.exists(): raise VerificationError(f"MISSING_PROVENANCE:{p.name}")
 m=jread(mp); r=jread(rp); jobs=jread(jp)
 if int(m.get("id",-1))!=aid: raise VerificationError(f"ARTIFACT_ID_MISMATCH:{aid}")
 if m.get("digest")!=f"sha256:{digest}": raise VerificationError(f"ARTIFACT_METADATA_DIGEST_MISMATCH:{aid}")
 wr=m.get("workflow_run") or {}
 if int(wr.get("id",-1))!=b["run"] or wr.get("head_sha")!=b["head"]: raise VerificationError(f"ARTIFACT_RUN_BINDING_MISMATCH:{aid}")
 if int(r.get("id",-1))!=b["run"] or r.get("head_sha")!=b["head"]: raise VerificationError(f"RUN_BINDING_MISMATCH:{stage}")
 if stage=="step11" and int(r.get("run_attempt",-1))!=b["attempt"]: raise VerificationError("RUN_ATTEMPT_MISMATCH:step11")
 js=jobs.get("jobs",[])
 if not any(int(x.get("id",-1))==b["job"] and x.get("run_id",b["run"])==b["run"] for x in js): raise VerificationError(f"JOB_BINDING_MISMATCH:{stage}")
 return {"artifact_id":aid,"run_id":b["run"],"job_id":b["job"],"head_sha":b["head"],"binding_source":"GITHUB_ACTIONS_PROVENANCE"}
def verify_semantics(root):
 with zipfile.ZipFile(root/'12603520492.zip') as z:
  c=zjson(z,'checkpoint.json'); p=zjson(z,'population_conservation.json'); f=zjson(z,'final_decision.json')
  if not(c.get('decision')=='STEP9_LIMITED_COVERAGE_CERTIFIED' and c.get('head_sha')==BINDINGS['step9']['head'] and c.get('total')==5026 and c.get('certified')==638 and c.get('residual')==4388): raise VerificationError('STEP9_SEMANTICS_MISMATCH')
  if not(p.get('certified_allowlist')==638 and p.get('residual_denylist')==4388 and p.get('fallback_success',0)==0 and f.get('decision')=='STEP9_LIMITED_COVERAGE_CERTIFIED'): raise VerificationError('STEP9_POPULATION_MISMATCH')
 with zipfile.ZipFile(root/'12603356621.zip') as z:
  c=zjson(z,'checkpoint.json'); g=zjson(z,'certified_only_guard_contract.json'); a=zjson(z,'certified_allowlist_test.json'); d=zjson(z,'residual_denylist_test.json'); u=zjson(z,'unknown_occurrence_test.json')
  if not(c.get('decision')=='STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED' and c.get('head_sha')==BINDINGS['step10']['head'] and c.get('certified')==638 and c.get('residual')==4388): raise VerificationError('STEP10_SEMANTICS_MISMATCH')
  if not(g.get('fallback_allowed') is False and a.get('allowed')==638 and d.get('denied')==4388 and d.get('fallback_attempted')==0 and u.get('fail_closed')==u.get('tested') and u.get('fallback')==0): raise VerificationError('STEP10_GUARD_MISMATCH')
 with zipfile.ZipFile(root/'12637078890.zip') as z:
  f=zjson(z,'final_decision.json'); l=zjson(z,'lineage.json')
  if not(f.get('selected_occurrences')==32 and f.get('selection_hash')=='ec9fc60f59a72769bd372704379667c76f1e71021e4197ac1af085750d3ee549' and f.get('residual_contamination')==0 and f.get('unknown_contamination')==0 and f.get('full_638_backfill_executed') is False): raise VerificationError('STEP11_SEMANTICS_MISMATCH')
  if not(str(l.get('run_id'))==str(BINDINGS['step11']['run']) and l.get('source_head')==BINDINGS['step11']['head']): raise VerificationError('STEP11_PAYLOAD_LINEAGE_MISMATCH')
 return {"step9":"PASS","step10":"PASS","step11":"PASS"}
def verify(root):
 reports={}; prov={}
 for aid,(name,digest,stage) in ARTIFACTS.items():
  p=root/f'{aid}.zip'
  if not p.exists(): raise VerificationError(f'MISSING_ARTIFACT:{aid}')
  reports[name]=inspect_zip(p,digest); prov[name]=verify_provenance(root,aid,digest,stage)
 semantics=verify_semantics(root)
 return {"verified":True,"binding_model":"PAYLOAD_INTEGRITY_PLUS_GITHUB_ARTIFACT_PROVENANCE","historical_payload_run_id_required":False,"artifacts":reports,"provenance":prov,"semantics":semantics,"sec_requests":0,"provider_requests":0,"current_identifier_requests":0,"residual4388_requests":0}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--artifact-dir',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
 report=verify(pathlib.Path(a.artifact_dir)); pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n'); print('FROZEN_AUTHORITY_REVALIDATION_PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
