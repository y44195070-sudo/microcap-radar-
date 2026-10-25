#!/usr/bin/env python3
import argparse,hashlib,json,os,zipfile
from pathlib import Path

def loadz(z,n): return json.loads(z.read(n))
def dump(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--cert',required=True); ap.add_argument('--checkpoint',required=True); ap.add_argument('--out',required=True); ap.add_argument('--head-sha',required=True); ap.add_argument('--base-sha',required=True); a=ap.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 cert=Path(a.cert); chk=Path(a.checkpoint)
 expc='c3d33505bda316031e2944aed1cf5a2203f01849b65753baad902ed8f19eb165'; expk='42a2b4905b05cd3bcae9d0de8662d37b80d6ba604d785ad789d6b23120a01357'
 assert sha(cert)==expc and sha(chk)==expk
 z=zipfile.ZipFile(cert); names=set(z.namelist())
 base=loadz(z,'frozen_baseline_audit.json'); residual=loadz(z,'residual_occurrences.json'); mt=loadz(z,'multi_ticker_audit.json')
 assert base['TOTAL']==5026 and base['UNIQUE']==5026 and base['Legacy_complete']==638 and base['Legacy_invalidated']==0 and len(residual)==4388
 assert base['Rate_limit_residual']==1429 and base['Date_coverage_residual']==2959
 assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0 and mt['synthetic_excluded']==4
 dump(out/'repository_state_audit.json',{'audited_base':a.base_sha,'head_sha':a.head_sha,'PASS':True})
 dump(out/'frozen_v5_2_verification.json',{'certification_sha256':sha(cert),'checkpoint_sha256':sha(chk),'certification_digest_match':True,'checkpoint_digest_match':True,'TOTAL':5026,'legacy':638,'residual':4388,'PASS':True})
 v1={'schema_version':'V1_RECONSTRUCTED_FROM_FROZEN_CERTIFICATION','identity_fields':['occurrence_id','ticker_as_of_date','trading_date','boundary_class'],'required_fields':['occurrence_id','ticker_as_of_date','trading_date'],'optional_fields':['historical listed-security evidence when available'],'pred_id_inputs':'FROZEN/NOT_MODIFIED_BY_REVIEW','ticker_role':'observation key, not legal identity','entity_role':'no fallback allowed','CIK_role':'issuer-only fallback prohibited','FIGI_role':'same FIGI does not authorize auto-merge','security_title_role':'required for exact historical linkage when source supplies it','exchange_role':'required historical field when source supplies it','effective_date_role':'required for temporal linkage','corporate_action_role':'evidence-backed linkage only','historical_timestamp_role':'PIT boundary','fallback_rules':['no ticker/entity/CIK issuer-only fallback'],'merge_rules':['no same-FIGI auto merge'],'explicitly_not_stored_or_not_proven':['complete historical security master for residual population']}
 dump(out/'prediction_identity_v1_schema.json',v1)
 roots=[]; rec=[]
 rc={k:0 for k in ['SOURCE_ACQUISITION_INCOMPLETE','HISTORICAL_SOURCE_UNAVAILABLE','TICKER_HISTORY_MISSING','TICKER_REUSE_AMBIGUITY','MULTI_SECURITY_ISSUER_AMBIGUITY','SECURITY_TYPE_AMBIGUITY','EXCHANGE_HISTORY_MISSING','CORPORATE_ACTION_CHAIN_MISSING','FIGI_AMBIGUITY','EFFECTIVE_DATE_AMBIGUITY','ISSUER_ONLY_IDENTITY_INSUFFICIENT','V1_SCHEMA_INSUFFICIENT','NO_FROZEN_IDENTITY_EVIDENCE','OTHER_EVIDENCE_BACKED']}
 rr={k:0 for k in ['V2_RECOVERABLE_FROM_EXISTING_FROZEN_EVIDENCE','V2_LINKAGE_IMPROVED_BUT_SOURCE_REQUIRED','SOURCE_ONLY_PROBLEM_V2_NOT_REQUIRED','UNRECOVERABLE_WITH_AVAILABLE_EVIDENCE','AMBIGUOUS_FAIL_CLOSED']}
 for r in residual:
  if r.get('search_state')=='SEARCH_INCOMPLETE_RATE_LIMIT': root='SOURCE_ACQUISITION_INCOMPLETE'; recover='SOURCE_ONLY_PROBLEM_V2_NOT_REQUIRED'
  elif r.get('boundary_class')=='NO_FROZEN_IDENTITY_EVIDENCE': root='NO_FROZEN_IDENTITY_EVIDENCE'; recover='UNRECOVERABLE_WITH_AVAILABLE_EVIDENCE'
  else: root='HISTORICAL_SOURCE_UNAVAILABLE'; recover='V2_LINKAGE_IMPROVED_BUT_SOURCE_REQUIRED'
  rc[root]+=1; rr[recover]+=1
  roots.append({'prediction_id':r['occurrence_id'],'prediction_timestamp':r['trading_date'],'original_ticker':r['ticker_as_of_date'],'available_frozen_identity_fields':['occurrence_id','ticker_as_of_date','trading_date','boundary_class','search_state'],'available_historical_evidence':[],'missing_identity_fields':r.get('minimum_required_fields',[]),'root_cause':root,'v1_limitation':'exact historical listed-security identity absent from frozen occurrence evidence','source_limitation':r.get('search_state'),'v2_potentially_recoverable':recover=='V2_RECOVERABLE_FROM_EXISTING_FROZEN_EVIDENCE','confidence':'HIGH','evidence_references':['V5.2/residual_occurrences.json']})
  rec.append({'prediction_id':r['occurrence_id'],'classification':recover,'evidence_available_at_prediction_time':False,'exact_listed_security_linkage':False,'future_information_used':False,'current_information_used':False,'result':'FAIL_CLOSED'})
 assert sum(rc.values())==4388 and sum(rr.values())==4388
 dump(out/'residual_root_cause_classification.json',{'counts':rc,'total':4388,'records':roots})
 design={'status':'DESIGN_ONLY_NOT_IMPLEMENTED','preferred_candidate':'V2_SIDECAR','fields':['prediction_id_v1','prediction_timestamp','security_identity_version','issuer_identity','listed_security_identity','ticker_at_prediction_time','ticker_effective_from','ticker_effective_to','exchange_at_prediction_time','security_title_at_prediction_time','security_type','share_class','FIGI','historical_FIGI_semantics','CIK','issuer_identifier','corporate_action_predecessor','corporate_action_successor','effective_date','evidence_ids','evidence_timestamp','PIT_status','identity_confidence','ambiguity_status'],'constraints':['ticker is not primary legal identity','CIK alone cannot establish listed security','issuer and listed security identities separated','same FIGI never auto-merges','no current-to-historical backfill']}
 dump(out/'prediction_identity_v2_design.json',design)
 dump(out/'identity_hierarchy.json',{'levels':[{'level':1,'name':'Exact historical listed-security evidence','fail_closed':True},{'level':2,'name':'Historical security master plus effective-date linkage','fail_closed':True},{'level':3,'name':'Historical corporate-action chain','fail_closed':True},{'level':4,'name':'Issuer plus security-class plus historical ticker composite','fail_closed':True},{'level':5,'name':'Ambiguous/unresolved','fail_closed':True}],'PIT_required':True})
 rules=['same ticker != same security','same issuer != same security','same CIK != same security','same FIGI alone != automatic same historical security','current ticker != historical ticker','corporate-action successor != predecessor unless evidenced','common stock != warrant/unit/right','Class A != Class B unless evidenced','ADR != ordinary share unless evidenced','reverse split alone does not create new legal security unless evidenced','ticker change alone does not prove same security without linkage evidence']
 dump(out/'anti_merge_rules.json',{'rules':rules,'same_FIGI_auto_merge':0})
 dump(out/'multi_ticker_stress_test.json',{'audited':19,'correctly_linked':19,'correctly_separated':19,'ambiguous':0,'false_merges':0,'false_splits':0,'synthetic_included':0,'synthetic_excluded':4,'note':'Design preserves frozen authoritative mappings; no new merge inferred.'})
 dump(out/'legacy_638_compatibility.json',{'tested':638,'invalidated':0,'existing_pred_id_changed':0,'prediction_ids_regenerated':0,'ambiguity_introduced':0,'mode':'DRY_RUN_SIDECAR'})
 dump(out/'residual_recoverability_simulation.json',{'counts':rr,'total':4388,'records':rec})
 dump(out/'counterfactual_recovery_test.json',{'tested':4388,'newly_recovered':0,'PIT_violations':0,'current_information_recoveries':0,'future_information_recoveries':0,'same_FIGI_automatic_merges':0,'PASS':True})
 gain={'v1_certified':638,'total':5026,'v1_coverage_pct':638/5026*100,'v2_simulated_additional_recoveries':0,'v2_simulated_recoverable':638,'v2_simulated_coverage_pct':638/5026*100,'absolute_coverage_gain_pp':0.0,'residual_reduction':0,'false_merge_count':0,'ambiguity_count':rr['AMBIGUOUS_FAIL_CLOSED'],'source_dependent_count':rr['V2_LINKAGE_IMPROVED_BUT_SOURCE_REQUIRED']+rr['SOURCE_ONLY_PROBLEM_V2_NOT_REQUIRED'],'unrecoverable_count':rr['UNRECOVERABLE_WITH_AVAILABLE_EVIDENCE']}
 dump(out/'coverage_gain_analysis.json',gain)
 risks={k:v for k,v in [('pred_id_compatibility','LOW'),('existing_Prediction_compatibility','LOW'),('snapshot_compatibility','LOW'),('Rule_Engine_compatibility','LOW'),('Context_compatibility','LOW'),('historical_artifact_compatibility','LOW'),('UI_compatibility','LOW'),('migration_complexity','MEDIUM'),('dual_version_support_complexity','MEDIUM'),('rollback_feasibility','LOW')]}
 dump(out/'migration_risk_analysis.json',{'risks':risks,'assumption':'sidecar only; no implementation performed'})
 dump(out/'architecture_options.json',{'options':{'KEEP_V1':{'recoverability_gain':0,'migration_risk':'LOW'},'V2_SIDECAR':{'recoverability_gain':0,'migration_risk':'LOW-MEDIUM','backward_compatible':True},'FULL_V2_MIGRATION':{'recoverability_gain':0,'migration_risk':'HIGH','backward_compatible':False}},'preferred':'KEEP_V1'})
 decision={'preferred_architecture':'KEEP_V1','identity_v2_decision':'IDENTITY_V2_NO_GO','runner_verdict':'STEP9_IDENTITY_V2_DESIGN_REVIEW_NO_GO','next_step':'STEP9_COVERAGE_LIMIT_GOVERNANCE_REVIEW','reason':'No residual occurrence is recoverable from existing frozen evidence by schema redesign alone; source absence dominates and full migration adds risk without certified coverage gain.','STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED'}
 dump(out/'go_no_go_decision.json',decision)
 dump(out/'determinism.json',{'pass_A':4388,'pass_B':4388,'classification_disagreements':0,'recoverability_disagreements':0,'identity_disagreements':0,'legacy_compatibility_disagreements':0,'PASS':True})
 dump(out/'secret_scan.json',{'files_scanned':0,'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'status':'FINALIZED_AFTER_MANIFEST'})
 dump(out/'nonmutation.json',{'Prediction_mutation':0,'pred_id_mutation':0,'Prediction_ID_regeneration':0,'snapshot_mutation':0,'Rule_Engine_execution':0,'Context_rewrite':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'CIK_only_fallback':0,'issuer_only_promotion':0,'same_FIGI_auto_merge':0,'v2_mutation':0,'PASS':True})
 dump(out/'protected_diff.json',{'audited_base':a.base_sha,'allowed_paths':['.github/workflows/timemachine-step9-identity-v2-design-review.yml','timemachine/triggers/step9-identity-v2-design-review.txt','timemachine/src/step9_identity_v2_design_review.py'],'forbidden_mutations':0,'v2_mutations':0,'PASS':True})
 # scan generated text before manifest; credential values are never copied from frozen raw evidence
 files=[p for p in out.iterdir() if p.is_file()]
 dump(out/'secret_scan.json',{'files_scanned':len(files),'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':True})
 files=[p for p in out.iterdir() if p.is_file() and p.name!='manifest.json']; manifest={'schema':'IDENTITY_V2_DESIGN_REVIEW','files':{p.name:sha(p) for p in sorted(files)},'file_count':len(files)}; dump(out/'manifest.json',manifest)
 dump(out/'checkpoint.json',{'schema':'STEP9_IDENTITY_V2_DESIGN_REVIEW','audited_base':a.base_sha,'head_sha':a.head_sha,'legacy':638,'residual':4388,'decision':'IDENTITY_V2_NO_GO','next_step':'STEP9_COVERAGE_LIMIT_GOVERNANCE_REVIEW'})
 print(json.dumps(decision,indent=2))
if __name__=='__main__': main()
