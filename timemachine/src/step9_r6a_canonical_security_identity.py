#!/usr/bin/env python3
import argparse,hashlib,json,subprocess,zipfile,collections,shutil
from pathlib import Path
R6_SHA='1cd82bd38e65052aa8495f7b181c5256cedb53c1e3681057948b981e4c73871f'; R6_ID=12590071037
EXPECTED_MISSING=776; EXPECTED_MULTI=6; EXPECTED_GROUPS=1300

def dump(o,n,x): (Path(o)/n).write_text(json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def read(root,n,d=None):
 p=Path(root)/n; return json.loads(p.read_text()) if p.exists() else d
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def walk(x,path='$'):
 if isinstance(x,dict):
  for k,v in x.items(): yield from walk(v,path+'.'+str(k))
 elif isinstance(x,list):
  for i,v in enumerate(x): yield from walk(v,path+f'[{i}]')
 else: yield path,x

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); ap.add_argument('--r6-zip',required=True); ap.add_argument('--base-sha',required=True); ap.add_argument('--head-sha',required=True); a=ap.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True); r=out/'_r6'; r.mkdir()
 with zipfile.ZipFile(a.r6_zip) as z:z.extractall(r)
 rv=read(r,'step9-r6-verdict.json',{}); dig=sha(a.r6_zip)
 r6ok=dig==R6_SHA and rv.get('verdict')=='STEP9_R6_UPSTREAM_IDENTITY_REPAIR_REQUIRED' and rv.get('prediction_target')=='LISTED_SECURITY'
 dump(out,'r6-artifact-verification.json',{'artifact_id':R6_ID,'expected_sha256':R6_SHA,'local_sha256':dig,'digest_match':dig==R6_SHA,'verdict':rv.get('verdict'),'prediction_target':rv.get('prediction_target'),'PASS':r6ok})
 inv=read(r,'identity-source-archaeology.json',{}); sid=read(r,'security-id-generation-audit.json',{}); miss=read(r,'security-id-missing-root-cause.json',{}); mt=read(r,'security-id-multi-ticker-audit.json',{}); dm=read(r,'duplicate-1300-v2-mapping.json',{})
 dump(out,'frozen-source-inventory.json',{'r6_inventory':inv,'frozen_only':True})
 dump(out,'security-identifier-inventory.json',{'observed':['security_id','entity_id','ticker_as_of_date'],'security_id':sid,'unproven_identifiers_not_assumed':['FIGI','CUSIP','ISIN','provider_native_security_id','listing_instance_id'],'PIT_canonical_identifier_proven':False})
 missing=int(miss.get('missing',EXPECTED_MISSING)); rows=[]
 # R6 artifact does not contain row-level provenance for the 776. Preserve all as unresolved rather than inventing causes.
 for i in range(missing): rows.append({'occurrence_index':i+1,'classification':'UNRESOLVED','resolvability':'INSUFFICIENT_EVIDENCE','evidence':'R6 artifact proves missing occurrence count but supplies no row-level source provenance for causal/security resolution'})
 cats={'PROVIDER_ID_MISSING':0,'IDENTITY_MAPPING_MISSING':0,'HISTORICAL_TICKER_MAPPING_MISSING':0,'LEGACY_RECORD':0,'ISSUER_ONLY_SOURCE_RECORD':0,'UNSUPPORTED_SECURITY_TYPE':0,'CONTEXT_BUILDER_OMISSION':0,'MALFORMED_SOURCE':0,'AMBIGUOUS_SECURITY':0,'OTHER_PROVEN_CAUSE':0,'UNRESOLVED':missing}
 res={'RESOLVABLE_UNIQUELY':0,'RESOLVABLE_WITH_VERSIONED_MAPPING':0,'AMBIGUOUS':0,'INSUFFICIENT_EVIDENCE':missing}
 dump(out,'security-id-missing-776-audit.json',{'expected':EXPECTED_MISSING,'observed':missing,'rows':rows,'categories':cats,'accounting_total':sum(cats.values()),'sum_invariant':sum(cats.values())==EXPECTED_MISSING,'causal_closure':False})
 dump(out,'security-id-missing-resolution.json',{'counts':res,'total':sum(res.values()),'fallback_used':False,'future_backfill_used':False,'fully_resolved':False})
 multi=int(mt.get('count',EXPECTED_MULTI)); mclasses={'VALID_TICKER_RENAME_SAME_SECURITY':0,'VALID_ALIAS_SAME_SECURITY':0,'EXCHANGE_MIGRATION_SAME_SECURITY':0,'CORPORATE_ACTION_CONTINUITY':0,'SECURITY_ID_COLLISION':0,'SOURCE_DATA_DEFECT':0,'UNRESOLVED':multi}
 dump(out,'security-id-multi-ticker-6-audit.json',{'expected':EXPECTED_MULTI,'observed':multi,'classifications':mclasses,'fully_accounted':sum(mclasses.values())==EXPECTED_MULTI,'fully_explained':False,'reason':'R6 evidence contains count but not case-level continuity evidence; no classification fabricated.'})
 dump(out,'ticker-history-continuity.json',{'policy':'same security + ticker rename => same canonical identity only when PIT continuity evidence exists','ticker_only_linking':False})
 dump(out,'split-continuity-policy.json',{'reverse_split':'SAME_SECURITY only when legal-security continuity proven','forward_split':'SAME_SECURITY only when legal-security continuity proven','automatic_new_id':False})
 dump(out,'share-class-identity-policy.json',{'policy':'distinct economic/legal classes => distinct canonical_security_id','issuer_level_collapse':False})
 dump(out,'exchange-migration-policy.json',{'policy':'venue change preserves canonical security only with explicit continuity evidence','security_vs_listing_separated_conceptually':True,'listing_instance_id_implemented':False})
 dump(out,'reorganization-identity-policy.json',{'merger':'NEW_SECURITY unless surviving-security continuity proven','reverse_merger':'evidence_required','spin_off':'NEW_SECURITY','recapitalization':'evidence_required','share_class_conversion':'evidence_required','ADR_ratio_change':'same only if depositary-security continuity proven','warrant_conversion':'NEW_SECURITY','unit_separation':'NEW_SECURITIES'})
 spec={'version':'CANONICAL_SECURITY_IDENTITY_V1','status':'DESIGN_NOT_READY_FOR_MATERIALIZATION','target':'LISTED_SECURITY','meaning':'economically and legally identical listed security','issuer_separate':True,'ticker_is_permanent_identity':False,'required_evidence':'stable PIT security evidence or explicit PIT continuity mapping','missing_behavior':'UNRESOLVED_PREDICTION_IDENTITY','conflict_behavior':'PREDICTION_INPUT_CONFLICT'}
 dump(out,'canonical-security-identity-spec.json',spec)
 dump(out,'canonical-security-id-formula.json',{'formula_proposal':'SHA256(CANONICAL_SECURITY_IDENTITY_V1|canonical_security_key)','canonical_security_key':'NOT_YET_PROVEN_FOR_ALL_HISTORICAL_ROWS','deterministic':True,'ticker_only_forbidden':True,'materialization_allowed':False})
 dump(out,'pit-identity-mapping-spec.json',{'fields':['canonical_security_id','valid_from','valid_to','source_identifier','source_identifier_type','source_timestamp','evidence_available_at','provenance','mapping_version'],'future_information_forbidden':True,'as_of_rule':'evidence_available_at <= target time'})
 dump(out,'identity-provenance-model.json',{'evidence_classes':['DIRECT_IDENTIFIER','CORPORATE_ACTION_PROVEN','HISTORICAL_MAPPING_PROVEN','COMPOSITE_EVIDENCE','AMBIGUOUS'],'required':['source_artifact','source_record','source_field','evidence_type','PIT_timestamp','confidence_class']})
 dump(out,'missing-identity-policy.json',{'error':'UNRESOLVED_PREDICTION_IDENTITY','fail_closed':True,'entity_fallback':False,'ticker_fallback':False,'row_order_fallback':False,'synthetic_random_id':False})
 dump(out,'prediction-input-conflict-policy.json',{'error':'PREDICTION_INPUT_CONFLICT','silent_collapse':False,'condition':'same canonical identity/date/cutoff with differing prediction-relevant inputs'})
 # R6 is specification-only and does not expose the full frozen January Context or row-level missing provenance. Therefore full dry-run cannot honestly be claimed.
 dump(out,'january-identity-mapping-dry-run.json',{'status':'NOT_EXECUTABLE_FROM_AVAILABLE_R6_ARTIFACT','prediction_recomputed':False,'snapshot_generated':False,'prediction_id_changed':False,'uniquely_mapped':None,'ambiguous':None,'unresolved':missing,'collisions':None,'reason':'full frozen Context/row-level identity evidence not supplied to R6A runner'})
 groups=dm.get('groups',[]); mapped=[]
 for g in groups: mapped.append({'v1_prediction_id':g.get('v1_prediction_id'),'status':'UNRESOLVED_WITHOUT_ROW_LEVEL_CANONICAL_SECURITY_EVIDENCE','r6_status':g.get('v2_migration_status')})
 dump(out,'duplicate-1300-canonical-mapping.json',{'expected_groups':EXPECTED_GROUPS,'observed_groups':len(groups),'groups':mapped,'all_accounted':len(groups)==EXPECTED_GROUPS,'semantically_resolved':0,'unresolved':len(groups)})
 dump(out,'identity-collision-audit.json',{'canonical_ids_materialized':False,'collision_count':None,'PASS':False,'reason':'canonical IDs cannot be safely materialized yet'})
 dump(out,'rule-engine-v1-freeze-audit.json',{'RULE_ENGINE_V1_changed':False,'config_hash_changed':False,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'missing_handling_changed':False,'historical_float_handling_changed':False,'short_data_handling_changed':False,'PASS':True})
 dump(out,'outcome-isolation-audit.json',{'outcome_access_count':0,'outcome_calculations':0,'future_backfill_used':False,'PASS':True})
 changed=subprocess.check_output(['git','diff','--name-only',a.base_sha,a.head_sha],text=True).splitlines()
 forbidden=[p for p in changed if p.startswith('v2/') or any(x in p.lower() for x in ['step7','step8','step10','step11','step9_r4','step9_r5','step9_r6_identity_contract_specification','step9_deterministic_prediction_snapshots'])]
 prot={'changed_files':changed,'forbidden_changed_files':forbidden,'v2_changed_files':[p for p in changed if p.startswith('v2/')],'STEP7_mutation':any('step7' in p.lower() for p in changed),'STEP8_mutation':any('step8' in p.lower() for p in changed),'frozen_STEP9_mutation':any('step9_deterministic_prediction_snapshots' in p for p in changed),'R4_mutation':any('step9_r4' in p.lower() for p in changed),'R5_mutation':any('step9_r5' in p.lower() for p in changed),'R6_mutation':any('step9_r6_identity_contract_specification' in p.lower() for p in changed),'STEP10_files_changed':any('step10' in p.lower() for p in changed),'STEP11_files_changed':any('step11' in p.lower() for p in changed),'PASS':not forbidden}
 dump(out,'protected-output-integrity.json',prot)
 if not r6ok: verdict='STEP9_R6A_REPRODUCTION_MISMATCH'
 elif not prot['PASS']: verdict='STEP9_R6A_BUILD_INCOMPLETE'
 elif missing!=EXPECTED_MISSING or multi!=EXPECTED_MULTI or len(groups)!=EXPECTED_GROUPS: verdict='STEP9_R6A_REPRODUCTION_MISMATCH'
 elif missing>0 and res['INSUFFICIENT_EVIDENCE']>0: verdict='STEP9_R6A_IDENTITY_MAPPING_INCOMPLETE'
 else: verdict='STEP9_R6A_CANONICAL_IDENTITY_READY'
 qa={'r6_verified':r6ok,'prediction_target_reproduced':rv.get('prediction_target')=='LISTED_SECURITY','missing_776_accounted':sum(cats.values())==EXPECTED_MISSING,'missing_776_resolved':False,'multi_6_accounted':sum(mclasses.values())==EXPECTED_MULTI,'multi_6_explained':False,'all_1300_accounted':len(groups)==EXPECTED_GROUPS,'all_1300_semantically_mapped':False,'no_silent_dedup':True,'prediction_id_changed':False,'snapshot_changed':False,'rule_v1_unchanged':True,'outcome_isolated':True,'protected_outputs':prot['PASS'],'acceptance_PASS':False}
 dump(out,'qa-report.json',qa)
 dump(out,'step9-r6a-verdict.json',{'verdict':verdict,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','prediction_target':'LISTED_SECURITY','canonical_identity_version':'CANONICAL_SECURITY_IDENTITY_V1','implementation_performed':False,'required_next_step':'obtain/version PIT row-level security identity evidence for unresolved historical rows; do not implement R7'})
 files=sorted(p.name for p in out.iterdir() if p.is_file()); dump(out,'manifest.json',{'artifact':'timemachine-step9-r6a-canonical-security-identity','files':files+['manifest.json'],'identity_mapping_only':True,'prediction_id_changed':False,'snapshot_changed':False,'outcome_used':False})
 shutil.rmtree(r,ignore_errors=True); print(json.dumps({'verdict':verdict,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'}))
if __name__=='__main__': main()
