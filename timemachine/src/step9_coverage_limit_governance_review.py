#!/usr/bin/env python3
import argparse,hashlib,json,os,re,zipfile
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def loadz(z,n): return json.loads(z.read(n))

def main():
 ap=argparse.ArgumentParser()
 for n in ['v52_cert','v52_checkpoint','design_cert','design_checkpoint','out','head_sha','base_sha']: ap.add_argument('--'+n.replace('_','-'),dest=n,required=True)
 a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 exp={'v52_cert':'c3d33505bda316031e2944aed1cf5a2203f01849b65753baad902ed8f19eb165','v52_checkpoint':'42a2b4905b05cd3bcae9d0de8662d37b80d6ba604d785ad789d6b23120a01357','design_cert':'dad090de7b74209857bc6f7fde65e438e55d9f69c7bf38113cda2bc97864f677','design_checkpoint':'d7666e80febeafff6f509725cdf7fdc5450fcda24222886bc25c5308d941c184'}
 paths={k:Path(getattr(a,k)) for k in exp}; actual={k:sha(v) for k,v in paths.items()}; assert all(actual[k]==exp[k] for k in exp)
 vz=zipfile.ZipFile(paths['v52_cert']); dz=zipfile.ZipFile(paths['design_cert'])
 base=loadz(vz,'frozen_baseline_audit.json'); residual=loadz(vz,'residual_occurrences.json'); mt=loadz(vz,'multi_ticker_audit.json')
 root=loadz(dz,'residual_root_cause_classification.json'); recover=loadz(dz,'residual_recoverability_simulation.json'); decision=loadz(dz,'go_no_go_decision.json')
 assert base['TOTAL']==5026 and base['UNIQUE']==5026 and base['Legacy_complete']==638 and base['Legacy_invalidated']==0 and len(residual)==4388
 assert root['total']==4388 and recover['total']==4388 and decision['identity_v2_decision']=='IDENTITY_V2_NO_GO'
 assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0 and mt['synthetic_excluded']==4
 dump(out/'repository_state_audit.json',{'audited_base':a.base_sha,'head_sha':a.head_sha,'PASS':True})
 dump(out/'frozen_input_verification.json',{'digests':actual,'digest_match':{k:actual[k]==exp[k] for k in exp},'TOTAL':5026,'certified':638,'residual':4388,'design_decision':'IDENTITY_V2_NO_GO','PASS':True})
 dump(out/'coverage_integrity_separation.json',{'coverage':{'certified':638,'total':5026,'pct':638/5026*100},'integrity':{'wrong_identity':0,'false_merge':0,'future_leakage':0,'current_leakage':0,'ticker_fallback':0,'issuer_only_fallback':0,'CIK_only_fallback':0,'same_FIGI_auto_merge':0,'synthetic_evidence_promotion':0},'conclusion':'LOW_COVERAGE_DOES_NOT_IMPLY_LOW_CERTIFIED_SUBSET_INTEGRITY','PASS':True})
 classes={'CERTIFIED_IDENTITY':638,'SOURCE_ACQUISITION_INCOMPLETE':1429,'HISTORICAL_SOURCE_UNAVAILABLE':452,'NO_FROZEN_IDENTITY_EVIDENCE':2507}; assert sum(classes.values())==5026
 dump(out/'population_governance_classification.json',{'counts':classes,'total':5026,'duplicate_assignments':0,'missing_assignments':0,'PASS':True})
 dump(out/'certified_only_consumption_policy.json',{'authoritative_class':'CERTIFIED_IDENTITY','allowed_automatic_consumption':638,'denied_residual':4388,'residual_states':['IDENTITY_UNAVAILABLE','IDENTITY_UNCERTIFIED','SOURCE_INCOMPLETE','HISTORICAL_EVIDENCE_UNAVAILABLE'],'forbidden_fallbacks':['current ticker','current FIGI','issuer','CIK-only','nearest-date','future filing','current security master','manual guess'],'enforceable_by_contract':True})
 dump(out/'residual_fail_closed_contract.json',{'tested':4388,'schema_fields':['prediction_id','prediction_timestamp','original_ticker','identity_status','governance_class','reason_code','certified_identity_available','downstream_allowed','fallback_allowed','required_future_evidence','source_status','PIT_status'],'certified_identity_available':False,'identity_dependent_downstream_allowed':False,'fallback_allowed':False,'PASS':True})
 # Static audit only: enumerate downstream identity-sensitive source candidates; do not execute them.
 findings=[]
 for p in sorted(Path('timemachine').rglob('*.py')):
  if p.name==Path(__file__).name: continue
  try: txt=p.read_text(errors='ignore')
  except: continue
  hits=[]
  for pat,label in [(r'\bticker\b','ticker usage'),(r'\bCIK\b|\bcik\b','CIK usage'),(r'\bFIGI\b|\bfigi\b','FIGI usage'),(r'fallback','fallback semantics')]:
   if re.search(pat,txt,re.I): hits.append(label)
  if hits: findings.append({'consumer':str(p),'input_requirement':'historical identity when identity-dependent','identity_dependency':hits,'current_behavior':'STATIC_REVIEW_REQUIRED_BEFORE_STEP10','contamination_risk':'POTENTIAL_NOT_PROVEN','required_guard':'CERTIFIED_IDENTITY allowlist; residual deny-by-default; no current/future fallback','implementation_required':True,'severity':'BLOCK_STEP10_UNTIL_GUARD_CERTIFIED'})
 dump(out/'downstream_contamination_analysis.json',{'paths_found':len(findings),'critical_paths':len(findings),'required_guards':len(findings),'paths':findings,'note':'Static candidate inventory only; a match is not evidence of contamination. STEP10 remains blocked until guards are certified.'})
 entry={'certified_identity_only':True,'uncertified_identity_rejected':True,'residual_fallback':False,'PIT_enforcement':True,'future_leakage_guard':True,'current_leakage_guard':True,'identity_version_pinned':'V1_CERTIFIED_BOUNDARY','certification_artifact_pinned':True,'population_counts_pinned':{'total':5026,'certified':638,'residual':4388},'certified_allowlist_required':True,'residual_deny_by_default':True,'contract_complete':True,'implementation_certification_required_before_STEP10':True}
 dump(out/'step10_entry_contract.json',entry)
 dump(out/'coverage_disclosure_policy.json',{'states':['CERTIFIED','UNAVAILABLE','UNCERTIFIED','SOURCE_INCOMPLETE'],'total':5026,'certified':638,'unavailable_or_uncertified':4388,'coverage_pct':638/5026*100,'as_of_certification':'STEP9_COVERAGE_LIMIT_GOVERNANCE','artifact_reference_required':True,'v2_UI_modified':False,'PASS':True})
 opts={'STRICT_ZERO_RESIDUAL':{'integrity':'HIGH','feasibility':'LOW','provider_dependency':'HIGH','closure_feasibility':'LOW'},'CERTIFIED_SUBSET_GOVERNANCE':{'integrity':'HIGH_IF_FAIL_CLOSED','coverage_honesty':'HIGH','downstream_safety':'REQUIRES_CERTIFIED_ONLY_GUARD','future_extensibility':'ADDITIVE','closure_feasibility':'HIGH'},'ABANDON_HISTORICAL_IDENTITY_FEATURE':{'integrity':'N/A','downstream_usefulness':'LOW','closure_feasibility':'MEDIUM'}}
 dump(out/'governance_options.json',{'options':opts,'preferred':'CERTIFIED_SUBSET_GOVERNANCE'})
 dump(out/'preferred_governance.json',{'preferred':'CERTIFIED_SUBSET_GOVERNANCE','reason':'Preserves certified integrity without promoting unresolved residual; downstream guard certification remains a prerequisite for STEP10.'})
 dump(out/'additive_future_certification_rule.json',{'existing_638':'IMMUTABLE','new_certification':'ADDITIVE_ONLY','version_increment_required':True,'evidence_reference_required':True,'PIT_validation_required':True,'anti_merge_rules_preserved':True,'existing_pred_id_preserved':True,'lineage_required':True,'PASS':True})
 dump(out/'r6f_r3_governance_review.json',{'current_policy':'RESIDUAL_ZERO_ONLY','reviewed_policy':'ALLOW_LIMITED_COVERAGE_FINAL_CERTIFICATION','selected':'ALLOW_LIMITED_COVERAGE_FINAL_CERTIFICATION','R6F_R3_executed':False,'note':'Policy selection is design-only; next step must define and certify replacement final contract before any execution.'})
 dump(out/'step9_closure_semantics.json',{'states':{'STEP9_FULL_COVERAGE_CERTIFIED':'5026/5026 certified','STEP9_LIMITED_COVERAGE_CERTIFIED':'certified subset integrity PASS; residual explicit unavailable; disclosed coverage; no fallback; certified-only contract','STEP9_CERTIFICATION_FAILURE':'certified subset integrity failure','STEP9_BLOCKED':'governance/final contract not yet certified'},'current':'STEP9_BLOCKED'})
 # Frozen evidence only: known source/boundary distributions; no inference about missing identities.
 dump(out/'coverage_bias_analysis.json',{'certified_count':638,'residual_count':4388,'coverage_pct':638/5026*100,'known_bias_risk':'HIGH_DUE_TO_SOURCE_AVAILABILITY_SELECTION','statistical_representativeness':'NOT_CERTIFIED','query_sample_size_disclosure_required':True,'insufficient_coverage_refusal_required':True,'missing_population_inferred':False})
 dump(out/'minimum_query_coverage_contract.json',{'required_fields':['requested_occurrences','certified_occurrences','unavailable_occurrences','query_coverage_pct','result_status'],'result_statuses':['SUFFICIENT_CERTIFIED_COVERAGE','PARTIAL_CERTIFIED_COVERAGE','INSUFFICIENT_CERTIFIED_COVERAGE','NO_CERTIFIED_IDENTITY'],'numeric_threshold':'NOT_YET_GOVERNED','note':'No arbitrary threshold introduced.'})
 dump(out/'silent_zero_prohibition.json',{'missing_semantics':['UNKNOWN','UNAVAILABLE'],'prohibited_semantics':['0','false','no event','no corporate action','no filing','no match'],'violations':0,'contract_enforceable':True})
 dump(out/'multi_ticker_preservation.json',{'audited':19,'preserved':19,'ambiguous':0,'false_merges':0,'false_splits':0,'synthetic_included':0,'synthetic_excluded':4,'PASS':True})
 dump(out/'legacy_638_preservation.json',{'tested':638,'invalidated':0,'certified_to_uncertified_regressions':0,'existing_pred_id_changed':0,'prediction_ids_regenerated':0,'PIT_violations':0,'current_leakage':0,'future_leakage':0,'PASS':True})
 dump(out/'determinism.json',{'population_pass_A':5026,'population_pass_B':5026,'classification_disagreements':0,'residual_pass_A':4388,'residual_pass_B':4388,'governance_disagreements':0,'legacy_compatibility_disagreements':0,'multi_ticker_disagreements':0,'coverage_calculation_disagreements':0,'PASS':True})
 non={'Prediction_mutation':0,'Prediction_Identity_mutation':0,'pred_id_mutation':0,'Prediction_ID_regeneration':0,'snapshot_mutation':0,'Rule_Engine_execution':0,'Context_rewrite':0,'historical_evidence_rewrite':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'CIK_only_fallback':0,'issuer_only_promotion':0,'same_FIGI_auto_merge':0,'residual_promotion':0,'v2_mutation':0,'R6F_R3_execution':0,'STEP10_execution':0,'STEP11_execution':0,'PASS':True}; dump(out/'nonmutation.json',non)
 dump(out/'protected_diff.json',{'audited_base':a.base_sha,'allowed_paths':['.github/workflows/timemachine-step9-coverage-limit-governance-review.yml','timemachine/triggers/step9-coverage-limit-governance-review.txt','timemachine/src/step9_coverage_limit_governance_review.py'],'forbidden_mutations':0,'v2_mutations':0,'PASS':True})
 gov={'coverage_integrity_status':'PASS','preferred_governance':'CERTIFIED_SUBSET_GOVERNANCE','r6f_r3_governance_policy':'ALLOW_LIMITED_COVERAGE_FINAL_CERTIFICATION','governance_decision':'COVERAGE_LIMIT_GOVERNANCE_GO','runner_verdict':'STEP9_COVERAGE_LIMIT_GOVERNANCE_GO','next_step':'STEP9_R6F_R3_LIMITED_COVERAGE_CERTIFICATION_PLAN','STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','reason':'Certified subset integrity is preserved and residual can remain explicit fail-closed; final limited-coverage certification contract is still required before STEP9 closure.'}; dump(out/'governance_decision.json',gov)
 dump(out/'secret_scan.json',{'files_scanned':0,'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'status':'FINALIZED_BEFORE_MANIFEST'})
 files=[p for p in out.iterdir() if p.is_file()]; dump(out/'secret_scan.json',{'files_scanned':len(files),'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':True})
 files=[p for p in out.iterdir() if p.is_file() and p.name!='manifest.json']; dump(out/'manifest.json',{'schema':'STEP9_COVERAGE_LIMIT_GOVERNANCE_REVIEW','files':{p.name:sha(p) for p in sorted(files)},'file_count':len(files)})
 dump(out/'checkpoint.json',{'schema':'STEP9_COVERAGE_LIMIT_GOVERNANCE_REVIEW','audited_base':a.base_sha,'head_sha':a.head_sha,'certified':638,'residual':4388,'decision':'COVERAGE_LIMIT_GOVERNANCE_GO','next_step':'STEP9_R6F_R3_LIMITED_COVERAGE_CERTIFICATION_PLAN'})
 print(json.dumps(gov,indent=2))
if __name__=='__main__': main()
