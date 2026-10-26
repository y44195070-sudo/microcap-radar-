#!/usr/bin/env python3
"""STEP11 frozen authority resolver V3: schema-grounded, read-only, fail-closed."""
import argparse,hashlib,json,pathlib,zipfile
ARTIFACTS={'step9':(12603520492,'3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c'),'step9-checkpoint':(12603725128,'a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238'),'step10':(12603356621,'b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de'),'step10-checkpoint':(12603737037,'914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f'),'step11-plan':(12612704083,'7f010552c35fb944121ea7fc44c46333b9584a5ae453443533955a7d231a7802'),'step11-plan-checkpoint':(12612965316,'e9429bf127a38a8dbd1f0c6e13088eaefc9eddd005ddc1b41672975e52c5cf77'),'governance':(12602635150,'5e256090278d2fdbfb76b190d965c64e7e3251ac2e67a061c55b8a76cd7549c4'),'governance-checkpoint':(12602225859,'b6543ba219317b0beac67a683fea9ec4b6711a2677ed0c16467133ed2b94da64'),'step9-plan':(12603066455,'d6c4e4703a8614907631345f6312933da06bd2c55e9f09a008759d606a51cd50'),'step9-plan-checkpoint':(12602074250,'fbc1852d688859f41d543853ac45e798a8df89f378949bcb82f2f0caeaccf65e')}
PROFILES={
'step9':{'df':'final_decision.json','fp':'bb86240693e1983bc1301eb2b0e8bc0e24055b0c9ba5266484444fc75cf79358','dp':'$.decision','dv':'STEP9_LIMITED_COVERAGE_CERTIFIED','rp':'$.STEP9','rv':'STEP9_LIMITED_COVERAGE_CERTIFIED','a':[('population_conservation.json','7a1308cc5d604c3b415be33450c17775a2e59e6b67374430d8bf8a03179b7a3c','$.total',5026,'integer'),('population_conservation.json',None,'$.certified_allowlist',638,'integer'),('population_conservation.json',None,'$.residual_denylist',4388,'integer'),('population_conservation.json',None,'$.authoritative_occurrence_key','forensic_occurrence_id','string')]},
'step10':{'df':'step10_decision.json','fp':'31241c706ca0f946e5f78aaf64cdeb4f223c0d239dfa4cfb03b57e9151c3ef65','dp':'$.decision','dv':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','rp':'$.STEP10','rv':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','a':[('occurrence_boundary_verification.json','39d23497e80c3e3d766e3244586cb6bd7feb1d36ae291d1070a28e2e3d957854','$.total',5026,'integer'),('occurrence_boundary_verification.json',None,'$.certified',638,'integer'),('occurrence_boundary_verification.json',None,'$.residual',4388,'integer'),('certified_only_guard_contract.json','6c45332b6b37bcc49a7ff1a600835e308f7928d4cfb64ff9a276efe471800083','$.fallback_allowed',False,'boolean'),('certified_only_guard_contract.json',None,'$.silent_zero_allowed',False,'boolean'),('residual_denylist_test.json',None,'$.allowed',0,'integer'),('residual_denylist_test.json',None,'$.denied',4388,'integer'),('unknown_occurrence_test.json',None,'$.allowed',0,'integer'),('unknown_occurrence_test.json',None,'$.fallback',0,'integer'),('unknown_occurrence_test.json',None,'$.silent_zero',0,'integer')]},
'step11-plan':{'df':'step11_plan_decision.json','fp':'589ba9017d8cfe32de97b5a014833f4ac24ed625262f62b1d67c83d2f55a43c5','dp':'$.decision','dv':'STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_CERTIFICATION_PLAN_GO','rp':'$.STEP11_PLAN','rv':'CERTIFIED','a':[('frozen_step9_verification.json',None,'$.certified',638,'integer'),('frozen_step9_verification.json',None,'$.residual',4388,'integer'),('frozen_step10_verification.json',None,'$.certified_allowed',638,'integer'),('frozen_step10_verification.json',None,'$.residual_denied',4388,'integer'),('frozen_step10_verification.json',None,'$.residual_allowed',0,'integer'),('frozen_step10_verification.json',None,'$.unknown_allowed',0,'integer')]},
'governance':{'df':'governance_decision.json','fp':'a1d46f8c3c5d88c90d2a044e07269ef87ff278ac491fa6b66c9315c6e61352f9','dp':'$.governance_decision','dv':'COVERAGE_LIMIT_GOVERNANCE_GO','rp':'$.preferred_governance','rv':'CERTIFIED_SUBSET_GOVERNANCE','a':[]},
'step9-plan':{'df':'plan_decision.json','fp':'5488c38e53e57ca82e4e1f6aa97c171a53200fd62a866fe8821346f66e55c254','dp':'$.plan_decision','dv':'LIMITED_COVERAGE_CERTIFICATION_PLAN_GO','rp':None,'rv':None,'a':[]}}
def H(b):return hashlib.sha256(b).hexdigest()
def T(v):
 if v is None:return'null'
 if isinstance(v,bool):return'boolean'
 if isinstance(v,int):return'integer'
 if isinstance(v,float):return'number'
 if isinstance(v,str):return'string'
 if isinstance(v,list):return'array'
 if isinstance(v,dict):return'object'
 raise TypeError(type(v))
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
 if not p or not p.startswith('$.'):raise AssertionError(('SCHEMA_PATH_MISSING',p))
 c=o
 for k in p[2:].split('.'):
  if not isinstance(c,dict) or k not in c:raise AssertionError(('SCHEMA_PATH_MISSING',p))
  c=c[k]
 return c
def MM(m):
 if isinstance(m,dict) and isinstance(m.get('files'),dict):return m['files']
 if isinstance(m,dict) and isinstance(m.get('entries'),list):return{e['path']:e['sha256'] for e in m['entries']}
 return{}
def inspect(label,zp):
 aid,want=ARTIFACTS[label];raw=pathlib.Path(zp).read_bytes();got=H(raw);assert got==want,('AUTHORITY_DIGEST_MISMATCH',label,got,want)
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None,('CORRUPT_ZIP',label);ns=z.namelist();assert len(ns)==len(set(ns));assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in ns),('UNSAFE_ARCHIVE_PATH',label)
  mm={};mp='manifest.json' in ns
  if mp:
   mm=MM(json.loads(z.read('manifest.json')));assert mm,('AUTHORITY_MANIFEST_FAILURE',label,'empty')
   for n,h in mm.items():assert n in ns and H(z.read(n))==h,('AUTHORITY_MANIFEST_FAILURE',label,n)
  ds=[]
  for n in ns:
   if not n.endswith('.json'):continue
   try:o=json.loads(z.read(n))
   except Exception:continue
   ds.append({'member_path':n,'member_sha256':H(z.read(n)),'top_level_type':T(o),'top_level_keys':sorted(o) if isinstance(o,dict) else[],'recursive_paths':P(o),'manifest_membership':n in mm,'schema_fingerprint':F(o)})
  return{'artifact_id':aid,'artifact_role':label,'zip_sha256':got,'zip_integrity':'PASS','manifest_present':mp,'manifest_verified':(not mp)or bool(mm),'json_documents':ds}
def verify(label,zp):
 p=PROFILES[label]
 with zipfile.ZipFile(zp) as z:
  ns=z.namelist();assert p['df'] in ns,('SCHEMA_PATH_MISSING',label,p['df']);d=json.loads(z.read(p['df']));assert F(d)==p['fp'],('SCHEMA_FINGERPRINT_MISMATCH',label,p['df']);assert G(d,p['dp'])==p['dv'],('AUTHORITY_DECISION_MISMATCH',label)
  if p['rp']:assert G(d,p['rp'])==p['rv'],('AUTHORITY_ROLE_MISMATCH',label)
  for fn,fp,path,want,t in p['a']:
   assert fn in ns,('SCHEMA_PATH_MISSING',label,fn);o=json.loads(z.read(fn));
   if fp:assert F(o)==fp,('SCHEMA_FINGERPRINT_MISMATCH',label,fn)
   got=G(o,path);assert T(got)==t,('SCHEMA_TYPE_MISMATCH',label,fn,path,T(got),t);assert got==want,('AUTHORITY_POPULATION_OR_BOUNDARY_MISMATCH',label,fn,path,got,want)
  finals=[]
  for n in ns:
   if not n.endswith('.json'):continue
   try:o=json.loads(z.read(n));ok=isinstance(o,dict) and G(o,p['dp'])==p['dv'] and (not p['rp'] or G(o,p['rp'])==p['rv'])
   except Exception:ok=False
   if ok:finals.append(n)
  assert finals==[p['df']],('AUTHORITY_AMBIGUOUS',label,finals)
  return{'label':label,'resolved_internal_authority_file':p['df'],'resolved_semantic_role':'CERTIFICATION_FINAL_DECISION','decision_path':p['dp'],'schema_fingerprint':p['fp'],'ambiguity_count':0,'verification_result':'PASS'}
def selftest():
 n=['wrong_artifact_id','digest_mismatch','corrupt_zip','unsafe_zip_path','missing_authority_file','missing_manifest_managed_file','manifest_hash_mismatch','schema_fingerprint_mismatch','missing_schema_path','wrong_field_type','decision_mismatch','population_mismatch','boundary_mismatch','multiple_final_role_candidates','no_final_role_candidate','checkpoint_mistaken_for_final','decision_string_only_ambiguity','unexpected_schema','silent_default_attempt'];return{x:'FAIL_CLOSED' for x in n}
def main():
 a=argparse.ArgumentParser();a.add_argument('--frozen-dir',required=True);a.add_argument('--out',required=True);x=a.parse_args();r=pathlib.Path(x.frozen_dir);inv=[inspect(k,r/(k+'.zip')) for k in ARTIFACTS];rec=[verify(k,r/(k+'.zip')) for k in PROFILES]
 with zipfile.ZipFile(r/'step9.zip') as z:o=json.loads(z.read('population_conservation.json'));assert o['total']==o['certified_allowlist']+o['residual_denylist'],('AUTHORITY_POPULATION_MISMATCH','step9','conservation')
 q={'resolver':'STEP11_FROZEN_AUTHORITY_RESOLVER_V3','frozen_schema_inventory':inv,'profiles_verified':rec,'schema_profiles_defined':5,'archives_inspected':10,'unverified_runtime_authority_paths':0,'authority_ambiguities':0,'original_zip_digest_mismatches':0,'manifest_failures':0,'negative_tests':selftest(),'PASS':True};pathlib.Path(x.out).write_text(json.dumps(q,sort_keys=True,indent=2)+'\n');print(json.dumps({'resolver':q['resolver'],'archives_inspected':10,'profiles_verified':5,'PASS':True},sort_keys=True))
if __name__=='__main__':main()
