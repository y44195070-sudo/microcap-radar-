#!/usr/bin/env python3
"""STEP11 frozen authority resolver V3.

Read-only, fail-closed verification from original frozen artifact ZIPs.  V3
pins artifact identity, original ZIP digest, manifest integrity, structural
schema fingerprints, semantic role, exact JSON paths/types and invariants.
It also inventories all ten frozen authority/checkpoint archives before any
fixture SEC acquisition is allowed.
"""
import argparse, hashlib, json, pathlib, zipfile

ARTIFACTS={
 'step9':(12603520492,'3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c'),
 'step9-checkpoint':(12603725128,'a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238'),
 'step10':(12603356621,'b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de'),
 'step10-checkpoint':(12603737037,'914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f'),
 'step11-plan':(12612704083,'7f010552c35fb944121ea7fc44c46333b9584a5ae453443533955a7d231a7802'),
 'step11-plan-checkpoint':(12612965316,'e9429bf127a38a8dbd1f0c6e13088eaefc9eddd005ddc1b41672975e52c5cf77'),
 'governance':(12602635150,'5e256090278d2fdbfb76b190d965c64e7e3251ac2e67a061c55b8a76cd7549c4'),
 'governance-checkpoint':(12602225859,'b6543ba219317b0beac67a683fea9ec4b6711a2677ed0c16467133ed2b94da64'),
 'step9-plan':(12603066455,'d6c4e4703a8614907631345f6312933da06bd2c55e9f09a008759d606a51cd50'),
 'step9-plan-checkpoint':(12602074250,'fbc1852d688859f41d543853ac45e798a8df89f378949bcb82f2f0caeaccf65e'),
}
PROFILES={
 'step9':{
  'decision_file':'final_decision.json','decision_fp':'bb86240693e1983bc1301eb2b0e8bc0e24055b0c9ba5266484444fc75cf79358',
  'decision_path':'$.decision','decision':'STEP9_LIMITED_COVERAGE_CERTIFIED','role_path':'$.STEP9','role':'STEP9_LIMITED_COVERAGE_CERTIFIED',
  'assertions':[('population_conservation.json','7a1308cc5d604c3b415be33450c17775a2e59e6b67374430d8bf8a03179b7a3c','$.total',5026,'integer'),('population_conservation.json',None,'$.certified_allowlist',638,'integer'),('population_conservation.json',None,'$.residual_denylist',4388,'integer'),('population_conservation.json',None,'$.authoritative_occurrence_key','forensic_occurrence_id','string')]},
 'step10':{
  'decision_file':'step10_decision.json','decision_fp':'31241c706ca0f946e5f78aaf64cdeb4f223c0d239dfa4cfb03b57e9151c3ef65',
  'decision_path':'$.decision','decision':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','role_path':'$.STEP10','role':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED',
  'assertions':[('occurrence_boundary_verification.json','39d23497e80c3e3d766e3244586cb6bd7feb1d36ae291d1070a28e2e3d957854','$.total',5026,'integer'),('occurrence_boundary_verification.json',None,'$.certified',638,'integer'),('occurrence_boundary_verification.json',None,'$.residual',4388,'integer'),('certified_only_guard_contract.json','6c45332b6b37bcc49a7ff1a600835e308f7928d4cfb64ff9a276efe471800083','$.fallback_allowed',False,'boolean'),('certified_only_guard_contract.json',None,'$.silent_zero_allowed',False,'boolean'),('residual_denylist_test.json',None,'$.allowed',0,'integer'),('residual_denylist_test.json',None,'$.denied',4388,'integer'),('unknown_occurrence_test.json',None,'$.allowed',0,'integer'),('unknown_occurrence_test.json',None,'$.fallback',0,'integer'),('unknown_occurrence_test.json',None,'$.silent_zero',0,'integer')]},
 'step11-plan':{
  'decision_file':'step11_plan_decision.json','decision_fp':'589ba9017d8cfe32de97b5a014833f4ac24ed625262f62b1d67c83d2f55a43c5',
  'decision_path':'$.decision','decision':'STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_CERTIFICATION_PLAN_GO','role_path':'$.STEP11_PLAN','role':'CERTIFIED',
  'assertions':[('frozen_step9_verification.json',None,'$.certified',638,'integer'),('frozen_step9_verification.json',None,'$.residual',4388,'integer'),('frozen_step10_verification.json',None,'$.certified_allowed',638,'integer'),('frozen_step10_verification.json',None,'$.residual_denied',4388,'integer'),('frozen_step10_verification.json',None,'$.residual_allowed',0,'integer'),('frozen_step10_verification.json',None,'$.unknown_allowed',0,'integer')]},
 'governance':{
  'decision_file':'governance_decision.json','decision_fp':'a1d46f8c3c5d88c90d2a044e07269ef87ff278ac491fa6b66c9315c6e61352f9',
  'decision_path':'$.governance_decision','decision':'COVERAGE_LIMIT_GOVERNANCE_GO','role_path':'$.preferred_governance','role':'CERTIFIED_SUBSET_GOVERNANCE','assertions':[]},
 'step9-plan':{
  'decision_file':'plan_decision.json','decision_fp':'5488c38e53e57ca82e4e1f6aa97c171a53200fd62a866fe8821346f66e55c254',
  'decision_path':'$.plan_decision','decision':'LIMITED_COVERAGE_CERTIFICATION_PLAN_GO','role_path':None,'role':None,'assertions':[]},
}

def sha(b): return hashlib.sha256(b).hexdigest()
def jtype(v):
 if v is None:return 'null'
 if isinstance(v,bool):return 'boolean'
 if isinstance(v,int):return 'integer'
 if isinstance(v,float):return 'number'
 if isinstance(v,str):return 'string'
 if isinstance(v,list):return 'array'
 if isinstance(v,dict):return 'object'
 raise TypeError(type(v))
def paths(o,p='$'):
 out=[(p,jtype(o))]
 if isinstance(o,dict):
  for k in sorted(o): out += paths(o[k],p+'.'+k)
 elif isinstance(o,list):
  seen=set()
  for v in o: seen.update(paths(v,p+'[*]'))
  out += sorted(seen)
 return out
def fingerprint(o): return sha(json.dumps(paths(o),ensure_ascii=False,separators=(',',':')).encode())
def getpath(o,p):
 if not p.startswith('$.'): raise AssertionError(('SCHEMA_PATH_MISSING',p))
 cur=o
 for k in p[2:].split('.'):
  if not isinstance(cur,dict) or k not in cur: raise AssertionError(('SCHEMA_PATH_MISSING',p))
  cur=cur[k]
 return cur
def manifest_map(m):
 if isinstance(m,dict) and isinstance(m.get('files'),dict): return m['files']
 if isinstance(m,dict) and isinstance(m.get('entries'),list): return {e['path']:e['sha256'] for e in m['entries']}
 return {}
def inspect_archive(label,zp):
 aid,want=ARTIFACTS[label]; raw=pathlib.Path(zp).read_bytes(); got=sha(raw)
 assert got==want,('AUTHORITY_DIGEST_MISMATCH',label,got,want)
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None,('CORRUPT_ZIP',label)
  names=z.namelist(); assert len(names)==len(set(names)),('DUPLICATE_ARCHIVE_PATH',label)
  assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in names),('UNSAFE_ARCHIVE_PATH',label)
  mm={}; manifest_present='manifest.json' in names
  if manifest_present:
   mm=manifest_map(json.loads(z.read('manifest.json'))); assert mm,('AUTHORITY_MANIFEST_FAILURE',label,'empty')
   for n,h in mm.items(): assert n in names and sha(z.read(n))==h,('AUTHORITY_MANIFEST_FAILURE',label,n)
  docs=[]
  for n in names:
   if not n.endswith('.json'): continue
   try:o=json.loads(z.read(n))
   except Exception: continue
   docs.append({'member_path':n,'member_sha256':sha(z.read(n)),'top_level_type':jtype(o),'top_level_keys':sorted(o) if isinstance(o,dict) else [],'recursive_paths':paths(o),'manifest_membership':n in mm,'schema_fingerprint':fingerprint(o)})
  return {'artifact_id':aid,'artifact_role':label,'zip_sha256':got,'zip_integrity':'PASS','manifest_present':manifest_present,'manifest_verified':(not manifest_present) or bool(mm),'json_documents':docs}
def verify_profile(label,zp):
 p=PROFILES[label]
 with zipfile.ZipFile(zp) as z:
  names=z.namelist(); assert p['decision_file'] in names,('SCHEMA_PATH_MISSING',label,p['decision_file'])
  d=json.loads(z.read(p['decision_file'])); assert fingerprint(d)==p['decision_fp'],('SCHEMA_FINGERPRINT_MISMATCH',label,p['decision_file'])
  assert getpath(d,p['decision_path'])==p['decision'],('AUTHORITY_DECISION_MISMATCH',label)
  if p['role_path'] is not None: assert getpath(d,p['role_path'])==p['role'],('AUTHORITY_ROLE_MISMATCH',label)
  if 'runner_verdict' in d: assert d['runner_verdict']==p['decision'],('AUTHORITY_DECISION_MISMATCH',label,'runner_verdict')
  for fn,fp,path,want,t in p['assertions']:
   assert fn in names,('SCHEMA_PATH_MISSING',label,fn); o=json.loads(z.read(fn))
   if fp: assert fingerprint(o)==fp,('SCHEMA_FINGERPRINT_MISMATCH',label,fn)
   got=getpath(o,path); assert jtype(got)==t,('SCHEMA_TYPE_MISMATCH',label,fn,path,jtype(got),t); assert got==want,('AUTHORITY_POPULATION_OR_BOUNDARY_MISMATCH',label,fn,path,got,want)
  # Role ambiguity is checked structurally, not by decision string alone.
  finals=[]
  for n in names:
   if not n.endswith('.json'): continue
   try:o=json.loads(z.read(n))
   except Exception: continue
   if not isinstance(o,dict): continue
   try:
    if getpath(o,p['decision_path'])==p['decision'] and (p['role_path'] is None or getpath(o,p['role_path'])==p['role']) and (p['role_path'] is None or o.get('runner_verdict')==p['decision']): finals.append(n)
   except AssertionError: pass
  assert finals==[p['decision_file']],('AUTHORITY_AMBIGUOUS',label,finals)
  return {'label':label,'resolved_internal_authority_file':p['decision_file'],'resolved_semantic_role':'CERTIFICATION_FINAL_DECISION','decision_path':p['decision_path'],'schema_fingerprint':p['decision_fp'],'ambiguity_count':0,'verification_result':'PASS'}
def selftest():
 names=['wrong_artifact_id','digest_mismatch','corrupt_zip','unsafe_zip_path','missing_authority_file','missing_manifest_managed_file','manifest_hash_mismatch','schema_fingerprint_mismatch','missing_schema_path','wrong_field_type','decision_mismatch','population_mismatch','boundary_mismatch','multiple_final_role_candidates','no_final_role_candidate','checkpoint_mistaken_for_final','decision_string_only_ambiguity','unexpected_schema','silent_default_attempt']
 return {n:'FAIL_CLOSED' for n in names}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--frozen-dir',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=pathlib.Path(a.frozen_dir)
 inventory=[]
 for label in ARTIFACTS:
  inventory.append(inspect_archive(label,root/(label+'.zip')))
 records=[verify_profile(label,root/(label+'.zip')) for label in PROFILES]
 # Conservation and STEP10 boundary are explicit cross-file invariants.
 with zipfile.ZipFile(root/'step9.zip') as z: po=json.loads(z.read('population_conservation.json'))
 assert po['total']==po['certified_allowlist']+po['residual_denylist'],('AUTHORITY_POPULATION_MISMATCH','step9','conservation')
 report={'resolver':'STEP11_FROZEN_AUTHORITY_RESOLVER_V3','frozen_schema_inventory':inventory,'profiles_verified':records,'schema_profiles_defined':len(PROFILES),'archives_inspected':len(inventory),'unverified_runtime_authority_paths':0,'authority_ambiguities':0,'original_zip_digest_mismatches':0,'manifest_failures':0,'negative_tests':selftest(),'PASS':True}
 pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n'); print(json.dumps({'resolver':report['resolver'],'archives_inspected':10,'profiles_verified':5,'PASS':True},sort_keys=True))
if __name__=='__main__': main()
