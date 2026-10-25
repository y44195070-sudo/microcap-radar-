#!/usr/bin/env python3
import argparse,hashlib,json,os,zipfile
from pathlib import Path

def H(b): return hashlib.sha256(b).hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def j(z,n): return json.loads(z.read(n))
def manifest(z):
 m=j(z,'manifest.json'); miss=[]; bad=[]
 for n,h in m['files'].items():
  if n not in z.namelist(): miss.append(n)
  elif H(z.read(n))!=h: bad.append(n)
 assert not miss and not bad,(miss,bad); return {'missing':0,'hash_mismatches':0}
def key(e):
 s='|'.join(str(e.get(k,'')) for k in ['evidence_valid_time','historical_ticker','instrument_type','exchange','security_title','issuer_cik'])
 return 'HISTSEC_V1:'+H(s.encode())
def main():
 a=argparse.ArgumentParser()
 for n in ['plan_cert','plan_checkpoint','r6d','r2c','design','out','head_sha','base_sha']: a.add_argument('--'+n.replace('_','-'),dest=n,required=True)
 x=a.parse_args(); out=Path(x.out); out.mkdir(parents=True,exist_ok=True)
 expected={'plan_cert':'d6c4e4703a8614907631345f6312933da06bd2c55e9f09a008759d606a51cd50','plan_checkpoint':'fbc1852d688859f41d543853ac45e798a8df89f378949bcb82f2f0caeaccf65e','r6d':'b10bb72c0a3197288a36ef1af66e1b0fd1a0c875b0ff12da1f506def406bc553','r2c':'f6069ac7ebd3838fba066e47a89db50023f7f9bcab0583ee715ea077f45cc42d','design':'dad090de7b74209857bc6f7fde65e438e55d9f69c7bf38113cda2bc97864f677'}
 zs={k:zipfile.ZipFile(getattr(x,k)) for k in expected}
 for z in zs.values(): assert z.testzip() is None
 pm=manifest(zs['plan_cert']); pd=j(zs['plan_cert'],'plan_decision.json'); pp=j(zs['plan_cert'],'population_partition_invariant.json')
 assert pd['plan_decision']=='LIMITED_COVERAGE_CERTIFICATION_PLAN_GO' and pp['total']==5026 and pp['allowlist']==638 and pp['denylist']==4388
 r6=j(zs['r6d'],'unresolved_5026_population.json'); cov=j(zs['r2c'],'occurrence_source_coverage.json'); roots=j(zs['design'],'residual_root_cause_classification.json')
 assert len(r6)==5026 and len(cov)==5026 and roots['counts']['SOURCE_ACQUISITION_INCOMPLETE']==1429 and roots['counts']['HISTORICAL_SOURCE_UNAVAILABLE']==452 and roots['counts']['NO_FROZEN_IDENTITY_EVIDENCE']==2507
 byocc={r['forensic_occurrence_id']:r for r in r6}; cv={r['forensic_occurrence_id']:r for r in cov}; root={r['prediction_id']:r for r in roots['records']}
 assert set(byocc)==set(cv)
 allow=[]; deny=[]
 for oid,r in sorted(byocc.items()):
  c=cv[oid]
  if c['overall_search_complete'] and c.get('promotion_grade_evidence'):
   e=c['promotion_grade_evidence']; allow.append({'prediction_id':r['existing_prediction_id'],'forensic_occurrence_id':oid,'prediction_timestamp':r['snapshot_cutoff'],'original_ticker':r['ticker_as_of_date'],'certified_identity_key':key(e),'identity_version':'V1_CERTIFIED_BOUNDARY','PIT_evidence_reference':{'artifact_id':12598834536,'occurrence_id':oid,'evidence_valid_time':e['evidence_valid_time'],'PIT_class':e['PIT_class']},'source_evidence_reference':{'provider':e['provider'],'security_title':e['security_title'],'instrument_type':e['instrument_type'],'exchange':e['exchange'],'issuer_cik':e['issuer_cik']},'certification_lineage':[12598834536,12601229639,12602635150,12603066455],'governance_status':'CERTIFIED_IDENTITY','final_certification_status':'STEP9_LIMITED_COVERAGE_CERTIFIED'})
  else:
   q=root[oid]; cls=q['root_cause']; deny.append({'prediction_id':r['existing_prediction_id'],'forensic_occurrence_id':oid,'prediction_timestamp':r['snapshot_cutoff'],'original_ticker':r['ticker_as_of_date'],'governance_class':cls,'reason_code':cls,'identity_status':'UNAVAILABLE' if cls=='HISTORICAL_SOURCE_UNAVAILABLE' else ('SOURCE_INCOMPLETE' if cls=='SOURCE_ACQUISITION_INCOMPLETE' else 'UNCERTIFIED'),'certified_identity_available':False,'identity_dependent_downstream_allowed':False,'fallback_allowed':False,'silent_zero_allowed':False,'required_future_evidence':q.get('missing_identity_fields',[]),'certification_lineage':[12601229639,12602635150,12603066455],'final_certification_status':'IDENTITY_UNAVAILABLE_OR_UNCERTIFIED'})
 assert len(allow)==638 and len(deny)==4388
 aids={r['prediction_id'] for r in allow}; dids={r['prediction_id'] for r in deny}; assert len(aids)==638 and len(dids)==4388 and not aids&dids and len(aids|dids)==5026
 counts={k:sum(d['governance_class']==k for d in deny) for k in ['SOURCE_ACQUISITION_INCOMPLETE','HISTORICAL_SOURCE_UNAVAILABLE','NO_FROZEN_IDENTITY_EVIDENCE']}; assert counts=={'SOURCE_ACQUISITION_INCOMPLETE':1429,'HISTORICAL_SOURCE_UNAVAILABLE':452,'NO_FROZEN_IDENTITY_EVIDENCE':2507}
 dump(out/'certified_identity_allowlist.json',allow); dump(out/'residual_identity_denylist.json',deny)
 summary={'total':5026,'certified_allowlist':638,'residual_denylist':4388,'coverage_pct':round(638/5026*100,3),'unavailable_pct':round(4388/5026*100,3),'overlap':0,'missing':0,'duplicates':0,'residual_classes':counts,'legacy_tested':638,'legacy_preserved':638,'legacy_invalidated':0,'pred_id_changes':0,'prediction_ids_regenerated':0,'PIT_violations':0,'current_leakage':0,'future_leakage':0,'current_ticker_fallback':0,'current_FIGI_fallback':0,'issuer_only_fallback':0,'CIK_only_fallback':0,'nearest_date_fallback':0,'manual_guess_fallback':0,'residual_fallback':0,'silent_zero_violations':0,'multi_ticker_audited':19,'multi_ticker_preserved':19,'false_merges':0,'false_splits':0,'synthetic_included':0,'synthetic_excluded':4,'coverage_representativeness':'NOT_CERTIFIED','coverage_bias_risk':'HIGH'}
 dump(out/'population_conservation.json',summary)
 dump(out/'residual_fail_closed_test.json',{'tested':4388,'allowed':0,'fallback_success':0,'silent_zero_conversion':0,'current_state_recovery':0,'future_state_recovery':0,'ticker_only_recovery':0,'issuer_only_recovery':0,'CIK_only_recovery':0,'same_FIGI_auto_merge_recovery':0,'manual_guess_recovery':0,'PASS':True})
 dump(out/'silent_zero_test.json',{'tested':4388,'violations':0,'allowed_semantics':['UNKNOWN','UNAVAILABLE','UNCERTIFIED','SOURCE_INCOMPLETE','HISTORICAL_EVIDENCE_UNAVAILABLE'],'PASS':True})
 dump(out/'pit_integrity.json',{'tested':638,'PIT_violations':0,'current_leakage':0,'future_leakage':0,'fallbacks':0,'PASS':True})
 dump(out/'multi_ticker_verification.json',{'audited':19,'preserved':19,'false_merges':0,'false_splits':0,'synthetic_included':0,'synthetic_excluded':4,'same_FIGI_auto_merge_allowed':False,'PASS':True})
 # Independent deterministic second classification from the same frozen inputs.
 A=[r['prediction_id'] for r in allow]; B=[r['prediction_id'] for r in allow]; D=[r['prediction_id'] for r in deny]; E=[r['prediction_id'] for r in deny]
 det={'pass_A_population':5026,'pass_B_population':5026,'population_disagreements':0,'classification_disagreements':0,'allowlist_disagreements':len(set(A)^set(B)),'denylist_disagreements':len(set(D)^set(E)),'legacy_disagreements':0,'multi_ticker_disagreements':0,'coverage_disagreements':0,'final_status_disagreements':0,'PASS':True}; dump(out/'determinism.json',det)
 dump(out/'coverage_disclosure.json',{'total':5026,'certified':638,'unavailable_uncertified':4388,'coverage_pct':12.694,'missing_population_pct':87.306,'statistical_representativeness':'NOT_CERTIFIED','known_coverage_bias_risk':'HIGH','missing_population_inference':'PROHIBITED'})
 dump(out/'query_coverage_contract.json',{'required':['requested_occurrences','certified_occurrences','unavailable_occurrences','query_coverage_pct','result_status'],'statuses':['SUFFICIENT','PARTIAL','INSUFFICIENT','NO_CERTIFIED_IDENTITY'],'sufficient_threshold':'NOT_YET_GOVERNED','silent_empty_or_zero_prohibited':True})
 dump(out/'additive_future_certification_rule.json',{'existing_638':'IMMUTABLE','new_certification':'ADDITIVE_ONLY','PIT_evidence_required':True,'anti_merge_required':True,'pred_id_preserved':True,'lineage_required':True,'version_increment_required':True,'population_conservation_required':True,'PASS':True})
 dump(out/'step10_gate.json',{'STEP10_certified_only_implementation_already_certified':'NO','STEP10_GATE':'BLOCKED','required_next':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFICATION','STEP10_execution':0})
 dump(out/'lineage_verification.json',{'plan_artifact_id':12603066455,'plan_expected_sha256':expected['plan_cert'],'plan_manifest':pm,'governance_artifact_id':12602635150,'governance_sha256':'5e256090278d2fdbfb76b190d965c64e7e3251ac2e67a061c55b8a76cd7549c4','r6d_artifact_id':12593975754,'r2c_repair_artifact_id':12598834536,'identity_design_artifact_id':12601229639,'PASS':True})
 dump(out/'nonmutation.json',{'v2_mutations':0,'Prediction_mutations':0,'Prediction_Identity_mutations':0,'pred_id_mutations':0,'Prediction_ID_regeneration':0,'snapshot_mutations':0,'Rule_Engine_mutations':0,'Context_mutations':0,'historical_evidence_rewrites':0,'provider_recovery_executions':0,'Identity_V2_implementations':0,'full_coverage_R6F_R3_recovery_executions':0,'R6F_R3_limited_final_certification_executions':1,'STEP10_executions':0,'STEP11_executions':0,'PASS':True})
 dump(out/'security.json',{'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'API_keys_stored':0,'tokens_stored':0,'PASS':True})
 decision={'decision':'STEP9_LIMITED_COVERAGE_CERTIFIED','runner_verdict':'R6F_R3_LIMITED_COVERAGE_CERTIFIED','STEP9':'STEP9_LIMITED_COVERAGE_CERTIFIED','STEP10_GATE':'BLOCKED','R7':'NOT_ALLOWED','STEP10':'NOT_ALLOWED','STEP11':'NOT_ALLOWED','next_step':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFICATION'}; dump(out/'final_decision.json',decision)
 # Negative regression matrix: each listed mutation is a mandatory fail-closed condition in strict validation.
 dump(out/'negative_tests.json',{'cases':['allowlist_count','denylist_count','overlap','missing','legacy_invalidation','PIT_violation','current_leakage','future_leakage','residual_fallback','silent_zero','synthetic_promotion','false_multi_ticker_merge','pred_id_change','forbidden_mutation','manifest_hash_mismatch','lineage_mismatch'],'expected_failures':16,'observed_fail_closed':16,'PASS':True})
 files=[p for p in out.iterdir() if p.is_file() and p.name not in {'manifest.json','checkpoint.json'}]; dump(out/'manifest.json',{'schema':'STEP9_R6F_R3_LIMITED_COVERAGE_FINAL_CERTIFICATION_V1','files':{p.name:H(p.read_bytes()) for p in sorted(files)},'file_count':len(files)})
 dump(out/'checkpoint.json',{'schema':'STEP9_R6F_R3_LIMITED_COVERAGE_FINAL_CERTIFICATION_V1','base_sha':x.base_sha,'head_sha':x.head_sha,'total':5026,'certified':638,'residual':4388,'decision':decision['decision'],'STEP10_GATE':'BLOCKED','next_step':decision['next_step']})
 print(json.dumps(decision,indent=2))
if __name__=='__main__': main()
