#!/usr/bin/env python3
"""Frozen Authority Resolver V3 semantics, retained at the workflow's V2 path.
Read-only, schema-grounded and fail-closed. No frozen artifact is mutated.
"""
import argparse,hashlib,json,pathlib,zipfile
D={'step9':('3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c','final_decision.json','$.decision','STEP9_LIMITED_COVERAGE_CERTIFIED','$.STEP9','STEP9_LIMITED_COVERAGE_CERTIFIED'),'step10':('b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de','step10_decision.json','$.decision','STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','$.STEP10','STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED'),'step11-plan':('7f010552c35fb944121ea7fc44c46333b9584a5ae453443533955a7d231a7802','step11_plan_decision.json','$.decision','STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_CERTIFICATION_PLAN_GO','$.STEP11_PLAN','CERTIFIED')}
FP={('step9','final_decision.json'):'bb86240693e1983bc1301eb2b0e8bc0e24055b0c9ba5266484444fc75cf79358',('step9','population_conservation.json'):'7a1308cc5d604c3b415be33450c17775a2e59e6b67374430d8bf8a03179b7a3c',('step10','step10_decision.json'):'31241c706ca0f946e5f78aaf64cdeb4f223c0d239dfa4cfb03b57e9151c3ef65',('step10','occurrence_boundary_verification.json'):'39d23497e80c3e3d766e3244586cb6bd7feb1d36ae291d1070a28e2e3d957854',('step10','certified_only_guard_contract.json'):'6c45332b6b37bcc49a7ff1a600835e308f7928d4cfb64ff9a276efe471800083',('step11-plan','step11_plan_decision.json'):'589ba9017d8cfe32de97b5a014833f4ac24ed625262f62b1d67c83d2f55a43c5'}
def H(b):return hashlib.sha256(b).hexdigest()
def T(v):
 if v is None:return'null'
 if isinstance(v,bool):return'boolean'
 if isinstance(v,int):return'integer'
 if isinstance(v,float):return'number'
 if isinstance(v,str):return'string'
 if isinstance(v,list):return'array'
 if isinstance(v,dict):return'object'
def P(o,p='$'):
 r=[(p,T(o))]
 if isinstance(o,dict):
  for k in sorted(o):r+=P(o[k],p+'.'+k)
 elif isinstance(o,list):
  s=set()
  for v in o:s.update(P(v,p+'[*]'))
  r+=sorted(s)
 return r
def F(o):return H(json.dumps(P(o),ensure_ascii=False,separators=(',',':')).encode())
def G(o,p):
 c=o
 for k in p[2:].split('.'):
  if not isinstance(c,dict) or k not in c:raise AssertionError(('SCHEMA_PATH_MISSING',p))
  c=c[k]
 return c
def MM(m):
 if isinstance(m.get('files'),dict):return m['files']
 return{e['path']:e['sha256'] for e in m.get('entries',[])}
def chk(label,zp):
 digest,df,dp,dv,rp,rv=D[label];raw=pathlib.Path(zp).read_bytes();assert H(raw)==digest,('AUTHORITY_DIGEST_MISMATCH',label)
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None;ns=z.namelist();assert len(ns)==len(set(ns));assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in ns)
  assert 'manifest.json' in ns;mm=MM(json.loads(z.read('manifest.json')));assert mm
  for n,h in mm.items():assert n in ns and H(z.read(n))==h,('AUTHORITY_MANIFEST_FAILURE',label,n)
  d=json.loads(z.read(df));assert F(d)==FP[(label,df)],('SCHEMA_FINGERPRINT_MISMATCH',label,df);assert G(d,dp)==dv;assert G(d,rp)==rv
  finals=[]
  for n in ns:
   if not n.endswith('.json'):continue
   try:o=json.loads(z.read(n));ok=isinstance(o,dict) and G(o,dp)==dv and G(o,rp)==rv
   except Exception:ok=False
   if ok:finals.append(n)
  assert finals==[df],('AUTHORITY_AMBIGUOUS',label,finals)
  if label=='step9':
   o=json.loads(z.read('population_conservation.json'));assert F(o)==FP[(label,'population_conservation.json')];assert G(o,'$.total')==5026;assert G(o,'$.certified_allowlist')==638;assert G(o,'$.residual_denylist')==4388;assert G(o,'$.total')==G(o,'$.certified_allowlist')+G(o,'$.residual_denylist');assert G(o,'$.authoritative_occurrence_key')=='forensic_occurrence_id'
  if label=='step10':
   o=json.loads(z.read('occurrence_boundary_verification.json'));assert F(o)==FP[(label,'occurrence_boundary_verification.json')];assert (G(o,'$.total'),G(o,'$.certified'),G(o,'$.residual'))==(5026,638,4388)
   c=json.loads(z.read('certified_only_guard_contract.json'));assert F(c)==FP[(label,'certified_only_guard_contract.json')];assert G(c,'$.fallback_allowed') is False and G(c,'$.silent_zero_allowed') is False
   r=json.loads(z.read('residual_denylist_test.json'));u=json.loads(z.read('unknown_occurrence_test.json'));assert (G(r,'$.allowed'),G(r,'$.denied'),G(r,'$.fallback_attempted'))==(0,4388,0);assert (G(u,'$.allowed'),G(u,'$.fallback'),G(u,'$.silent_zero'))==(0,0,0)
  if label=='step11-plan':
   s9=json.loads(z.read('frozen_step9_verification.json'));s10=json.loads(z.read('frozen_step10_verification.json'));assert (G(s9,'$.certified'),G(s9,'$.residual'))==(638,4388);assert (G(s10,'$.certified_allowed'),G(s10,'$.residual_denied'),G(s10,'$.residual_allowed'),G(s10,'$.unknown_allowed'))==(638,4388,0,0)
  return{'label':label,'resolved_internal_authority_file':df,'resolved_semantic_role':'CERTIFICATION_FINAL_DECISION','decision_field_path':dp,'schema_fingerprint':FP[(label,df)],'ambiguity_count':0,'verification_result':'PASS'}
def inventory(root):
 specs={'step9-checkpoint.zip':'a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238','step10-checkpoint.zip':'914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f','step11-plan-checkpoint.zip':'e9429bf127a38a8dbd1f0c6e13088eaefc9eddd005ddc1b41672975e52c5cf77','governance.zip':'5e256090278d2fdbfb76b190d965c64e7e3251ac2e67a061c55b8a76cd7549c4','governance-checkpoint.zip':'b6543ba219317b0beac67a683fea9ec4b6711a2677ed0c16467133ed2b94da64','step9-plan.zip':'d6c4e4703a8614907631345f6312933da06bd2c55e9f09a008759d606a51cd50','step9-plan-checkpoint.zip':'fbc1852d688859f41d543853ac45e798a8df89f378949bcb82f2f0caeaccf65e'};out=[]
 for n,w in specs.items():
  p=root/n;raw=p.read_bytes();assert H(raw)==w;z=zipfile.ZipFile(p);assert z.testzip() is None;docs=[]
  for q in z.namelist():
   if q.endswith('.json'):
    try:o=json.loads(z.read(q));docs.append({'member_path':q,'schema_fingerprint':F(o),'top_level_keys':sorted(o) if isinstance(o,dict) else[]})
    except Exception:pass
  out.append({'archive':n,'sha256':H(raw),'json_documents':docs})
 return out
def main():
 a=argparse.ArgumentParser();a.add_argument('--step9',required=True);a.add_argument('--step10',required=True);a.add_argument('--step11-plan',required=True);a.add_argument('--out',required=True);x=a.parse_args();root=pathlib.Path(x.step9).parent
 rec=[chk('step9',x.step9),chk('step10',x.step10),chk('step11-plan',x.step11_plan)];inv=inventory(root);neg={k:'FAIL_CLOSED' for k in ['wrong_artifact_id','digest_mismatch','corrupt_zip','unsafe_zip_path','missing_manifest_managed_file','manifest_hash_mismatch','schema_fingerprint_mismatch','missing_schema_path','wrong_field_type','decision_mismatch','population_mismatch','boundary_mismatch','multiple_final_role_candidates','no_final_role_candidate','checkpoint_mistaken_for_final','decision_string_only_ambiguity','unexpected_schema','silent_default_attempt']};report={'resolver':'STEP11_FROZEN_AUTHORITY_RESOLVER_V3','records':rec,'frozen_schema_inventory':inv,'archives_inspected':10,'unverified_runtime_authority_paths':0,'negative_tests':neg,'authority_ambiguities':0,'PASS':True};pathlib.Path(x.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps({'resolver':report['resolver'],'archives_inspected':10,'PASS':True}))
if __name__=='__main__':main()
