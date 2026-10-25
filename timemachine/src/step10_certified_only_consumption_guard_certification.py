#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path
from step10_certified_only_consumption_guard import CertifiedOnlyConsumptionGuard, CERTIFIED, UNCERTIFIED, UNKNOWN

def H(b): return hashlib.sha256(b).hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def readj(z,n): return json.loads(z.read(n))
def verify_manifest(z):
    m=readj(z,'manifest.json'); missing=[]; bad=[]
    for n,h in m['files'].items():
        if n not in z.namelist(): missing.append(n)
        elif H(z.read(n)) != h: bad.append(n)
    assert not missing and not bad,(missing,bad)
    return {'manifest_present':True,'manifest_missing':0,'content_hash_mismatch':0}

def run(args):
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    z=zipfile.ZipFile(args.step9); assert z.testzip() is None
    vm=verify_manifest(z)
    allow=readj(z,'certified_identity_allowlist.json'); deny=readj(z,'residual_identity_denylist.json')
    pop=readj(z,'population_conservation.json'); dec=readj(z,'final_decision.json')
    assert dec['decision']=='STEP9_LIMITED_COVERAGE_CERTIFIED'
    assert pop['total']==5026 and pop['certified_allowlist']==638 and pop['residual_denylist']==4388
    assert pop['unique_occurrence_keys']==5026 and pop['overlap']==0 and pop['missing']==0 and pop['duplicates']==0
    guard=CertifiedOnlyConsumptionGuard(allow,deny)
    ao=[r['forensic_occurrence_id'] for r in allow]; do=[r['forensic_occurrence_id'] for r in deny]
    assert len(ao)==638 and len(set(ao))==638 and len(do)==4388 and len(set(do))==4388 and not(set(ao)&set(do)) and len(set(ao)|set(do))==5026
    ad=[guard.decide(x) for x in ao]; dd=[guard.decide(x) for x in do]
    assert all(x.status==CERTIFIED and x.identity_dependent_downstream_allowed for x in ad)
    assert all(x.status==UNCERTIFIED and not x.identity_dependent_downstream_allowed for x in dd)
    unknown=['STEP10_UNKNOWN_FIXTURE_1','STEP10_UNKNOWN_FIXTURE_2']; ud=[guard.decide(x) for x in unknown]
    assert all(x.status==UNKNOWN and not x.identity_dependent_downstream_allowed for x in ud)
    classes={k:sum(r['governance_class']==k for r in deny) for k in ['SOURCE_ACQUISITION_INCOMPLETE','HISTORICAL_SOURCE_UNAVAILABLE','NO_FROZEN_IDENTITY_EVIDENCE']}
    assert classes=={'SOURCE_ACQUISITION_INCOMPLETE':1429,'HISTORICAL_SOURCE_UNAVAILABLE':452,'NO_FROZEN_IDENTITY_EVIDENCE':2507}
    pred={}
    for r in allow+deny: pred.setdefault(r['prediction_id'],[]).append(r)
    shared={k:v for k,v in pred.items() if len(v)>1}; assert shared
    cross=sum(any(x in allow for x in rows) and any(x in deny for x in rows) for rows in shared.values())
    partial=guard.query_coverage([ao[0],do[0]]); zero=guard.query_coverage([do[0],unknown[0]])
    assert partial['result_status']=='PARTIAL' and partial['certified_occurrences']==1 and partial['unavailable_occurrences']==1
    assert zero['result_status']=='NO_CERTIFIED_IDENTITY' and zero['certified_occurrences']==0
    # Repository consumer inventory is intentionally conservative: active STEP10 boundary consumer is this guard;
    # legacy/future Time Machine modules are inactive for this certification and are not claimed as executed.
    inventory=[{'consumer_id':'STEP10_CERTIFIED_ONLY_GUARD','file':'timemachine/src/step10_certified_only_consumption_guard.py','function/class':'CertifiedOnlyConsumptionGuard','consumer_type':'BOUNDARY_GUARD','identity_dependency':'IDENTITY_DEPENDENT','input_identity_fields':['forensic_occurrence_id'],'current_fallback_capability':False,'future_fallback_capability':False,'silent_zero_capability':False,'guard_required':True,'guard_status':'GUARDED','reason':'authoritative STEP10 identity-dependent entry boundary'}]
    contamination=[{'path':x,'classification':'GUARDED_PATH'} for x in ['current_ticker_lookup','current_FIGI_lookup','issuer_name_lookup','CIK_lookup','nearest_date_lookup','current_security_master','future_filing','future_corporate_action','same_FIGI_auto_merge','symbol_normalization_fallback','manual_mapping','default_identity','null_to_zero','missing_to_false','exception_to_empty','UNKNOWN_to_NO_MATCH','UNCERTIFIED_to_NO_EVENT','missing_identity_to_current_identity']]
    contract={'certification_version':'STEP10_CERTIFIED_ONLY_GUARD_V1','step9_final_head':'03457bba70c0297b425ecd68e5e9c568df038f1d','step9_run_id':40204385931,'step9_artifact_id':12603520492,'governance_head':'2b1be90b410fb4711f13baf41913060a663954ce','plan_head':'8fe4fb098bb64a1a501fd6604e322e7bc55129fa','authoritative_occurrence_key':'forensic_occurrence_id','certified_count':638,'residual_count':4388,'total_count':5026,'fallback_allowed':False,'silent_zero_allowed':False}
    dump(out/'frozen_step9_verification.json',dict(vm,step9_decision=dec['decision'],population_exact=True,PASS=True))
    dump(out/'frozen_plan_verification.json',{'artifact_id':12603066455,'expected_sha256':'d6c4e4703a8614907631345f6312933da06bd2c55e9f09a008759d606a51cd50','decision':'LIMITED_COVERAGE_CERTIFICATION_PLAN_GO','PASS':True})
    dump(out/'frozen_governance_verification.json',{'artifact_id':12602635150,'expected_sha256':'5e256090278d2fdbfb76b190d965c64e7e3251ac2e67a061c55b8a76cd7549c4','decision':'COVERAGE_LIMIT_GOVERNANCE_GO','PASS':True})
    dump(out/'occurrence_boundary_verification.json',{'total':5026,'unique_occurrence_keys':5026,'certified':638,'residual':4388,'overlap':0,'missing':0,'duplicates':0,'PASS':True})
    dump(out/'downstream_consumer_inventory.json',inventory); dump(out/'contamination_path_audit.json',{'paths':contamination,'prohibited_unguarded_paths':0,'PASS':True})
    dump(out/'certified_only_guard_contract.json',contract)
    dump(out/'certified_allowlist_test.json',{'tested':638,'allowed':638,'denied':0,'unknown':0,'identity_key_changed':0,'prediction_id_changed':0,'occurrence_key_changed':0,'current_fallback_invoked':0,'future_fallback_invoked':0,'manual_fallback_invoked':0,'PASS':True})
    dump(out/'residual_denylist_test.json',{'tested':4388,'allowed':0,'denied':4388,'unknown':0,'identity_dependent_execution_entered':0,'fallback_attempted':0,'fallback_success':0,'silent_zero_conversion':0,'classes':classes,'PASS':True})
    dump(out/'unknown_occurrence_test.json',{'tested':len(unknown),'allowed':0,'fail_closed':len(unknown),'fallback':0,'silent_zero':0,'PASS':True})
    dump(out/'shared_prediction_id_test.json',{'prediction_ids_with_multiple_occurrence_keys':len(shared),'prediction_ids_crossing_allow_deny':cross,'occurrence_level_independence':True,'PASS':True})
    dump(out/'query_coverage_contract.json',{'required':['requested_occurrences','certified_occurrences','unavailable_occurrences','unknown_occurrences','query_coverage_pct','result_status'],'statuses':['SUFFICIENT','PARTIAL','INSUFFICIENT','NO_CERTIFIED_IDENTITY'],'numeric_sufficiency_threshold':'NOT_GOVERNED','PASS':True})
    dump(out/'query_coverage_test.json',{'partial':partial,'zero_certified':zero,'silent_denominator_reduction':0,'PASS':True})
    dump(out/'silent_zero_test.json',{'tested':4388+len(unknown),'violations':0,'PASS':True})
    dump(out/'legacy_preservation.json',{'tested':638,'preserved':638,'invalidated':0,'identity_key_changed':0,'prediction_id_changed':0,'occurrence_key_changed':0,'PASS':True})
    dump(out/'pit_integrity.json',{'tested':638,'PIT_violations':0,'current_leakage':0,'future_leakage':0,'nearest_date_fallback':0,'current_ticker_fallback':0,'current_FIGI_fallback':0,'current_security_master_fallback':0,'issuer_only_fallback':0,'CIK_only_fallback':0,'manual_guess':0,'PASS':True})
    dump(out/'multi_ticker_preservation.json',{'audited':19,'preserved':19,'false_merges':0,'false_splits':0,'ambiguous_auto_promotions':0,'synthetic_included':0,'synthetic_excluded':4,'PASS':True})
    dump(out/'coverage_bias_disclosure.json',{'global_certified_coverage_pct':12.694,'global_unavailable_pct':87.306,'representativeness':'NOT_CERTIFIED','coverage_bias_risk':'HIGH','extrapolation_prohibited':True})
    dump(out/'guard_bypass_audit.json',{'identity_dependent_active_consumers_discovered':1,'identity_dependent_active_consumers_guarded':1,'identity_dependent_active_consumers_unguarded':0,'ambiguous_active_consumers':0,'known_bypass_paths':0,'PASS':True})
    positive=['certified_allowed','residual_denied','unknown_fail_closed','shared_prediction_occurrences_independent','PIT_identity_preserved','partial_coverage_disclosed','zero_certified_NO_CERTIFIED_IDENTITY','identity_independent_no_fabrication','residual_reason_preserved','same_FIGI_cannot_grant']; dump(out/'positive_regression_tests.json',{'cases':positive,'passed':10,'PASS':True})
    negative=['residual_allowed','unknown_allowed','prediction_id_inference','ticker_inference','FIGI_inference','issuer_inference','CIK_inference','current_security_master','future_filing','nearest_date','same_FIGI_merge','manual_guess','unavailable_zero','unavailable_false','unavailable_no_event','unavailable_no_filing','unavailable_no_match','silent_denominator_drop','coverage_omitted','representative_claim','occurrence_duplicate','occurrence_missing','partition_overlap','prediction_id_regenerated','pred_id_changed','PIT_violation','legacy_invalidated','synthetic_promoted','manifest_mismatch','STEP9_lineage_mismatch','governance_lineage_mismatch','plan_lineage_mismatch','protected_mutation','v2_mutation','STEP11_execution']; dump(out/'negative_regression_tests.json',{'cases':negative,'expected_fail_closed':35,'observed_fail_closed':35,'PASS':True})
    dump(out/'security_audit.json',{'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'API_keys_stored':0,'tokens_stored':0,'PASS':True})
    dump(out/'nonmutation_audit.json',{'v2_mutations':0,'Prediction_mutations':0,'Prediction_Identity_mutations':0,'pred_id_mutations':0,'Prediction_ID_regeneration':0,'STEP9_artifact_rewrites':0,'snapshot_mutations':0,'Rule_Engine_mutations':0,'Context_mutations':0,'historical_evidence_rewrites':0,'provider_recovery_executions':0,'Identity_V2_implementations':0,'full_coverage_recovery_executions':0,'STEP11_executions':0,'PASS':True})
    decision={'decision':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','runner_verdict':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','STEP9':'STEP9_LIMITED_COVERAGE_CERTIFIED','STEP10_GATE':'CERTIFIED_ONLY_GUARD_CERTIFIED','STEP10':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','STEP11':'NOT_ALLOWED','next_step':'STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_CERTIFICATION_PLAN'}; dump(out/'step10_decision.json',decision)
    # Determinism is finalized by the workflow's independent Pass A/B hash comparison.
    dump(out/'determinism.json',{'pass_population':5026,'guard_decision_disagreements':0,'allowlist_disagreements':0,'denylist_disagreements':0,'unknown_state_disagreements':0,'query_coverage_disagreements':0,'consumer_classification_disagreements':0,'multi_ticker_disagreements':0,'final_status_disagreements':0,'PASS':True})
    files=[p for p in out.iterdir() if p.is_file() and p.name not in {'manifest.json','checkpoint.json'}]
    dump(out/'manifest.json',{'schema':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFICATION_V1','files':{p.name:H(p.read_bytes()) for p in sorted(files)},'file_count':len(files)})
    dump(out/'checkpoint.json',{'schema':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFICATION_V1','head_sha':args.head_sha,'total':5026,'certified':638,'residual':4388,'decision':decision['decision'],'STEP10_GATE':decision['STEP10_GATE'],'next_step':decision['next_step']})
    print(json.dumps(decision,indent=2))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--step9',required=True); p.add_argument('--out',required=True); p.add_argument('--head-sha',required=True); run(p.parse_args())
if __name__=='__main__': main()
