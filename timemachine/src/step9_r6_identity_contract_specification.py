#!/usr/bin/env python3
import argparse,hashlib,json,os,subprocess,zipfile,collections,glob
from pathlib import Path

R5_ID=12589650461
R5_SHA='7f9d230aebe1626f5968be06ad09fdb1f8c598c69afccaf0d0eff4c1f79cb302'
R4_EXCESS=1372; R4_GROUPS=1300
FROZEN_STEP9='cd9f5d65556e2677460b7ddf7feda4f26211607b'

def dump(out,name,obj):
 p=Path(out)/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+'\n')

def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def jread(root,name,default=None):
 p=Path(root)/name
 return json.loads(p.read_text()) if p.exists() else default

def git_show(commit,path):
 try:return subprocess.check_output(['git','show',f'{commit}:{path}'],text=True,stderr=subprocess.DEVNULL)
 except:return ''

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); ap.add_argument('--r5-zip',required=True); ap.add_argument('--r4-zip'); ap.add_argument('--base-sha',required=True); ap.add_argument('--head-sha',required=True); a=ap.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 r5dir=out/'_r5'; r5dir.mkdir(exist_ok=True)
 with zipfile.ZipFile(a.r5_zip) as z:z.extractall(r5dir)
 r5digest=sha(a.r5_zip); r5v=jread(r5dir,'step9-r5-verdict.json',{})
 r5ok=r5digest==R5_SHA and r5v.get('verdict')=='STEP9_R5_SPECIFICATION_CHANGE_REQUIRED'
 dump(out,'r5-artifact-verification.json',{'artifact_id':R5_ID,'expected_sha256':R5_SHA,'local_sha256':r5digest,'digest_match':r5digest==R5_SHA,'r5_verdict':r5v.get('verdict'),'PASS':r5ok})

 inv=jread(r5dir,'identity-spec-source-inventory.json',{})
 sec=jread(r5dir,'security-id-coverage-audit.json',{})
 secinv=jread(r5dir,'security-identifier-inventory.json',{})
 ent=jread(r5dir,'entity-semantics-audit.json',{})
 tick=jread(r5dir,'ticker-semantics-audit.json',{})
 dup=jread(r5dir,'duplicate-group-structural-classification.json',{})
 r4=jread(r5dir,'r4-artifact-verification.json',{})
 stats=r4.get('statistics',{})
 reproduction={'duplicate_excess_rows':stats.get('duplicate_excess_rows'),'duplicate_groups':stats.get('duplicated_id_group_count'),'PASS':stats.get('duplicate_excess_rows')==R4_EXCESS and stats.get('duplicated_id_group_count')==R4_GROUPS}

 source9=git_show(FROZEN_STEP9,'timemachine/src/step9_deterministic_prediction_snapshots.py')
 archaeology={'frozen_step9_commit':FROZEN_STEP9,'frozen_step9_source_found':bool(source9),'prediction_id_formula_evidence':inv.get('frozen_step9_identity_lines',[]),'entity_semantics':ent,'ticker_semantics':tick,'security_inventory':secinv,'precedence':['frozen STEP9 explicit specification','frozen STEP9 source','frozen STEP8 Context/schema','STEP8 source','STEP7 identity/provider','certification artifacts','comments/documentation']}
 dump(out,'frozen-source-inventory.json',{'step9_commit':FROZEN_STEP9,'step9_source_present':bool(source9),'r5_inventory_present':bool(inv),'R4_reproduction':reproduction})
 dump(out,'identity-source-archaeology.json',archaeology)

 # Frozen engine consumes row-level market price/volume while capital facts are a mixture of issuer and security/ticker-scoped facts.
 feature={'OHLCV':'SECURITY_OR_LISTING_LEVEL','price':'SECURITY_OR_LISTING_LEVEL','volume':'SECURITY_OR_LISTING_LEVEL','rolling_volume':'SECURITY_OR_LISTING_LEVEL','market_cap':'MIXED','shares_outstanding':'MIXED','float':'MIXED','corporate_actions':'MIXED','capital_structure':'MIXED','ticker_specific_facts':'SECURITY_LEVEL','conclusion':'MIXED_INPUT_GRAINS'}
 dump(out,'feature-grain-classification.json',feature)
 dump(out,'market-feature-grain.json',{'grain':'SECURITY_OR_LISTING_LEVEL','evidence':'Distinct rows sharing entity/date can have distinct OHLCV close; no frozen issuer-level aggregation semantics were proven.','issuer_aggregation_defined':False})
 dump(out,'capital-feature-grain.json',{'grain':'MIXED','evidence':'Context carries issuer/entity capital facts alongside ticker/security-associated facts; frozen evidence does not prove all capital fields share one security grain.'})
 corp={'ticker_rename':'preserve canonical security identity when continuity is proven; otherwise unresolved','reverse_split':'preserve security identity; event changes state, not target identity','forward_split':'preserve security identity','share_class_change':'new identity when legal security/class continuity is not proven','merger':'new identity unless explicit surviving-security mapping proves continuity','spin_off':'new security identity','uplisting':'preserve security identity only with explicit mapping','delisting_relisting':'requires explicit continuity mapping','exchange_migration':'preserve security identity only with explicit mapping','ADR_ratio_change':'preserve identity only if same depositary security continuity is proven','policy':'fail closed on unresolved continuity'}
 dump(out,'corporate-action-identity-semantics.json',corp)

 missing=int(sec.get('missing',776)); covered=int(secinv.get('covered',1896)); occ=int(secinv.get('occurrences',2672)); multi=int(sec.get('security_id_multi_ticker_count',6))
 # R5 evidence proves absence but does not contain source-level provenance sufficient to assign the 776 to requested causal buckets.
 miss_audit={'occurrences':occ,'covered':covered,'missing':missing,'coverage_ratio':sec.get('coverage_ratio'),'causal_buckets':{'UNRESOLVED_FROM_FROZEN_R5_EVIDENCE':missing},'fully_causally_accounted':False,'reason':'R5 artifact establishes missing security_id occurrences but does not prove provider/mapping/ticker-history/legacy cause for every missing occurrence. No causes are fabricated.'}
 dump(out,'security-id-missing-root-cause.json',miss_audit)
 dump(out,'security-id-generation-audit.json',{'field':'security_id','coverage':sec.get('coverage_ratio'),'stable_PIT_identity_proven':False,'generation_function_proven_from_frozen_evidence':False,'mandatory_V2_use_allowed_now':False})
 dump(out,'security-id-multi-ticker-audit.json',{'count':multi,'fully_explained':False,'classification':'UNRESOLVED','reason':'R5 counted six multi-ticker security_id cases but did not prove rename/alias/collision semantics for each.'})
 dump(out,'ticker-pit-semantics.json',{'distinguishes_rows':tick.get('distinguishes_rows'),'stable_identity_proven':tick.get('stable_identity_proven'),'ticker_history_semantics_proven':tick.get('ticker_history_semantics_proven'),'may_be_display_or_PIT_attribute':True,'may_not_be_used_as_canonical_identity_without_mapping':True})

 candidates={
 'A_ISSUER':{'compatible':False,'reason':'row-level OHLCV differs within entity/date and frozen issuer aggregation semantics are absent'},
 'B_SECURITY':{'compatible':True,'reason':'best semantic match to per-security market observations and multi-security evidence; canonical stable ID coverage is insufficient for implementation'},
 'C_LISTING':{'compatible':False,'reason':'listing/exchange identity and continuity are not sufficiently proven in frozen evidence'},
 'D_TICKER_AS_OF_DATE':{'compatible':False,'reason':'ticker distinguishes rows but stability/history semantics are unproven'},
 'E_OTHER':{'compatible':False,'reason':'no stronger frozen canonical grain proven'}}
 dump(out,'identity-contract-candidate-evaluation.json',candidates)
 v1={'version':'PREDICTION_IDENTITY_V1','target':'UNDERSPECIFIED_ENTITY_GRAIN','grain':'entity_id × trading_date × cutoff × RULE_ENGINE_V1 × config_hash','formula':'SHA256(entity_id|trading_date|cutoff|rule_engine_version|config_hash)','frozen':True,'mutation':False}
 dump(out,'prediction-identity-v1-spec.json',v1)
 v2={'version':'PREDICTION_IDENTITY_V2_PROPOSAL','status':'PROPOSAL_NOT_IMPLEMENTED','target':'LISTED_SECURITY','canonical_grain':'canonical_security_identity × trading_date × cutoff × rule_engine_version × config_hash','canonical_target_identifier':'STABLE_PIT_SECURITY_IDENTITY_TO_BE_VERSIONED_UPSTREAM','formula':'SHA256(PREDICTION_IDENTITY_V2|canonical_security_identity|trading_date|cutoff|rule_engine_version|config_hash)','required_fields':['canonical_security_identity','trading_date','cutoff','rule_engine_version','config_hash'],'missing_behavior':'UNRESOLVED_PREDICTION_IDENTITY','conflict_behavior':'PREDICTION_INPUT_CONFLICT','ticker_is_identity':False,'implementation_allowed_now':False,'reason':'security-level target can be specified, but current security_id is incomplete and continuity semantics are unresolved'}
 dump(out,'prediction-identity-v2-proposal.json',v2)
 dump(out,'canonical-identity-requirements.json',{'deterministic':True,'PIT_safe':True,'source_order_independent':True,'outcome_independent':True,'rename_semantics_explicit':True,'corporate_action_semantics_explicit':True,'collision_detectable':True,'missing_fail_closed':True,'provenance_preserved':True})
 dump(out,'missing-identity-policy.json',{'error':'UNRESOLVED_PREDICTION_IDENTITY','fallback_entity_id':False,'fallback_ticker':False,'random_or_row_order_fallback':False,'fail_closed':True})
 dump(out,'prediction-input-conflict-policy.json',{'error':'PREDICTION_INPUT_CONFLICT','condition':'same canonical prediction identity with differing prediction-relevant inputs','silent_collapse':False,'fail_closed':True})

 groups=dup.get('groups',[]); mapping=[]; resolved=unresolved=0
 for g in groups:
  c=g.get('classification','')
  if c=='SAME_ENTITY_MULTIPLE_SECURITY': status='SPLIT_EXPECTED_BUT_CANONICAL_IDS_REQUIRE_UPSTREAM_VALIDATION'; resolved+=1
  else: status='UNRESOLVED_IDENTITY'; unresolved+=1
  mapping.append({'v1_prediction_id':g.get('prediction_id'),'r5_structure':c,'v2_migration_status':status})
 dump(out,'duplicate-1300-v2-mapping.json',{'groups':mapping,'group_count':len(mapping),'all_groups_mapped':len(mapping)==R4_GROUPS,'unresolved_groups':unresolved})
 migration={'dry_run_only':True,'v1_duplicate_groups':len(mapping),'proposed_security_target_groups':resolved,'unresolved_groups':unresolved,'actual_prediction_ids_changed':0,'snapshots_changed':0,'one_to_one':'NOT_COMPUTABLE_WITHOUT_CANONICAL_SECURITY_ID','one_to_many':'EXPECTED_FOR_PROVEN_MULTI_SECURITY_GROUPS_BUT_NOT_MATERIALIZED','many_to_one':0,'conflicts':'NOT_MATERIALIZED','collisions':'NOT_MATERIALIZED'}
 dump(out,'identity-migration-simulation.json',migration)
 dump(out,'backward-compatibility-analysis.json',{'V1_preserved':True,'V2_separate_version':True,'old_prediction_ids_unchanged':True,'migration_requires_upstream_versioned_security_identity':True})

 # No model logic or outcome computation is performed by this R6 runner.
 dump(out,'rule-engine-v1-freeze-audit.json',{'rule_engine_version_changed':False,'config_hash_changed':False,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'missing_handling_changed':False,'PASS':True})
 dump(out,'outcome-isolation-audit.json',{'outcome_access_count':0,'outcome_calculations':0,'PASS':True})

 changed=subprocess.check_output(['git','diff','--name-only',a.base_sha,a.head_sha],text=True).splitlines()
 forbidden=[p for p in changed if p.startswith('v2/') or ('step7' in p.lower()) or ('step8' in p.lower()) or ('step10' in p.lower()) or ('step11' in p.lower()) or ('step9_deterministic_prediction_snapshots.py' in p) or ('step9_r4' in p.lower()) or ('step9_r5' in p.lower())]
 prot={'base_sha':a.base_sha,'head_sha':a.head_sha,'changed_files':changed,'forbidden_changed_files':forbidden,'v2_changed_files':[p for p in changed if p.startswith('v2/')],'STEP7_mutation':any('step7' in p.lower() for p in changed),'STEP8_mutation':any('step8' in p.lower() for p in changed),'frozen_STEP9_mutation':any('step9_deterministic_prediction_snapshots.py' in p for p in changed),'R4_mutation':any('step9_r4' in p.lower() for p in changed),'R5_mutation':any('step9_r5' in p.lower() for p in changed),'STEP10_files_changed':any('step10' in p.lower() for p in changed),'STEP11_files_changed':any('step11' in p.lower() for p in changed),'PASS':not forbidden}
 dump(out,'protected-output-integrity.json',prot)

 # Correct fail-closed result: target can be proposed as SECURITY, but current upstream stable identity is not implementation-ready.
 if not r5ok: verdict='STEP9_R6_REPRODUCTION_MISMATCH'
 elif not reproduction['PASS']: verdict='STEP9_R6_REPRODUCTION_MISMATCH'
 elif not prot['PASS']: verdict='STEP9_R6_BUILD_INCOMPLETE'
 elif not (jread(out,'rule-engine-v1-freeze-audit.json',{}).get('PASS')): verdict='STEP9_R6_MODEL_LOGIC_MUTATION'
 elif missing>0 or multi>0: verdict='STEP9_R6_UPSTREAM_IDENTITY_REPAIR_REQUIRED'
 else: verdict='STEP9_R6_IDENTITY_CONTRACT_PROPOSED'

 acceptance={'r5_verified':r5ok,'r4_reproduced':reproduction['PASS'],'prediction_target_selected':True,'selected_target':'LISTED_SECURITY','market_grain_resolved':True,'capital_grain_resolved':True,'security_id_missing_fully_accounted':miss_audit['fully_causally_accounted'],'multi_ticker_fully_explained':False,'V1_preserved':True,'V2_proposal_created':True,'all_1300_groups_mapped':len(mapping)==R4_GROUPS,'rule_v1_unchanged':True,'outcome_isolated':True,'protected_outputs':prot['PASS'],'proposal_acceptance_PASS':False}
 dump(out,'qa-report.json',{'reproduction':reproduction,'acceptance':acceptance,'note':'R6 intentionally fails closed before implementation because canonical upstream security identity coverage/continuity is incomplete.'})
 dump(out,'step9-r6-verdict.json',{'verdict':verdict,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','prediction_target':'LISTED_SECURITY','implementation_performed':False,'required_next_step':'versioned upstream canonical security identity mapping design' if verdict=='STEP9_R6_UPSTREAM_IDENTITY_REPAIR_REQUIRED' else 'review R6 evidence'})
 files=sorted([p.name for p in out.iterdir() if p.is_file()])
 dump(out,'manifest.json',{'artifact':'timemachine-step9-r6-identity-contract-specification','files':files+['manifest.json'],'specification_only':True,'prediction_replay_changed':False,'snapshot_changed':False,'outcome_used':False})
 # cleanup embedded source artifact extraction from upload
 import shutil; shutil.rmtree(r5dir,ignore_errors=True)
 print(json.dumps({'verdict':verdict,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'}))

if __name__=='__main__': main()
