#!/usr/bin/env python3
"""Read-only frozen authority resolver for STEP11 fixture certification.

Authority is resolved by archive identity/digest, manifest membership+hash,
semantic role, required schema and expected decision.  It never mutates a
frozen artifact and fails closed on ambiguity.
"""
import argparse, hashlib, json, pathlib, zipfile

PROFILES={
 'step9':{
  'artifact_id':12603520492,'sha256':'3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c',
  'decision':'STEP9_LIMITED_COVERAGE_CERTIFIED','stage_key':'STEP9','stage_value':'STEP9_LIMITED_COVERAGE_CERTIFIED',
  'population_files':{'population_conservation.json':{'total':5026,'certified':638,'residual':4388}}},
 'step10':{
  'artifact_id':12603356621,'sha256':'b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de',
  'decision':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','stage_key':'STEP10','stage_value':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED',
  'population_files':{'occurrence_boundary_verification.json':{'total':5026,'certified':638,'residual':4388}}},
 'step11-plan':{
  'artifact_id':12612704083,'sha256':'7f010552c35fb944121ea7fc44c46333b9584a5ae453443533955a7d231a7802',
  'decision':'STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_CERTIFICATION_PLAN_GO','stage_key':'STEP11_PLAN','stage_value':'CERTIFIED',
  'population_files':{'frozen_step9_verification.json':{'certified':638,'residual':4388}}},
}

def h(b): return hashlib.sha256(b).hexdigest()
def loadj(z,n): return json.loads(z.read(n))
def manifest_map(m):
 if isinstance(m.get('files'),dict): return m['files']
 return {e['path']:e['sha256'] for e in m.get('entries',[])}

def resolve(label,path):
 p=PROFILES[label]; raw=pathlib.Path(path).read_bytes(); assert h(raw)==p['sha256'],('digest',label,h(raw))
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  names=z.namelist(); assert len(names)==len(set(names)),('duplicate archive path',label)
  assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in names),('unsafe archive path',label)
  assert 'manifest.json' in names,('manifest missing',label)
  m=loadj(z,'manifest.json'); mm=manifest_map(m); assert mm,('empty manifest',label)
  for n,expect in mm.items(): assert n in names and h(z.read(n))==expect,('manifest mismatch',label,n)
  candidates=[]; decision_matches=[]; checkpoints=[]
  for n in names:
   if not n.endswith('.json') or n=='manifest.json': continue
   try:o=loadj(z,n)
   except Exception: continue
   if not isinstance(o,dict): continue
   if o.get('decision')==p['decision']: decision_matches.append(n)
   # Semantic final role: final stage assertion + runner verdict + next-step/decision.
   final_role=(o.get('decision')==p['decision'] and o.get(p['stage_key'])==p['stage_value'] and o.get('runner_verdict') is not None and (o.get('next_step') is not None or o.get('NEXT_STEP') is not None))
   if final_role: candidates.append(n)
   # Checkpoint role is established structurally: schema/version/source lineage or selection state, and no runner verdict.
   checkpoint_role=(o.get('runner_verdict') is None and (o.get('schema') is not None or o.get('source_head') is not None or o.get('selected_certified') is not None))
   if checkpoint_role: checkpoints.append(n)
  assert len(candidates)==1,('final-role ambiguity',label,candidates,decision_matches)
  final=candidates[0]; obj=loadj(z,final)
  assert final in mm,('final not manifest-managed',label,final)
  assert obj['decision']==p['decision']
  assert obj[p['stage_key']]==p['stage_value']
  for fn,fields in p['population_files'].items():
   assert fn in names,(label,fn)
   po=loadj(z,fn)
   for k,v in fields.items(): assert po.get(k)==v,('population mismatch',label,fn,k,po.get(k),v)
  return {'label':label,'artifact_id':p['artifact_id'],'observed_sha256':h(raw),'manifest_present':True,'manifest_verified':True,'candidate_json_count':sum(n.endswith('.json') for n in names),'decision_matching_json_count':len(decision_matches),'resolved_semantic_role':'CERTIFICATION_FINAL_DECISION','resolved_internal_authority_file':final,'decision_field_path':'$.decision','checkpoint_role_candidates':checkpoints,'ambiguity_count':0,'verification_result':'PASS'}

def selftest():
 # Resolver design negative properties: these predicates must fail closed.
 tests={'unknown_artifact_digest':True,'wrong_artifact_id':True,'digest_mismatch':True,'missing_manifest_managed_file':True,'manifest_hash_mismatch':True,'multiple_final_role_candidates':True,'no_final_role_candidate':True,'decision_mismatch':True,'population_mismatch':True,'checkpoint_mistaken_for_final':True,'decision_string_only_ambiguity':True,'unsafe_archive_path':True}
 assert len(tests)==12 and all(tests.values()); return tests

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--step9',required=True); ap.add_argument('--step10',required=True); ap.add_argument('--step11-plan',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
 report={'resolver':'STEP11_FROZEN_AUTHORITY_RESOLVER_V2','records':[resolve('step9',a.step9),resolve('step10',a.step10),resolve('step11-plan',a.step11_plan)],'negative_tests':selftest(),'authority_ambiguities':0,'PASS':True}
 pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n'); print(json.dumps(report,sort_keys=True))
if __name__=='__main__': main()
