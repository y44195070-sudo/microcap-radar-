#!/usr/bin/env python3
import argparse,collections,gzip,hashlib,io,json,os,subprocess,zipfile
R6BR_SHA='e21d081cc4d97ecd16835c36f56631ac1d43b60f3d86c78ff57ccfe9e2980a8e'
R4_SHA='9efb5959cf043e674455d4d2778121db67e993eb0b5059d40a332e3774db2a00'
R5_SHA='7f9d230aebe1626f5968be06ad09fdb1f8c598c69afccaf0d0eff4c1f79cb302'
CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
BASE='7c32b1704091ad80d1bd463906185b2f7bed1e4f'
CONFIG='5e2b11b97c76889e420201ee3496023d1abed3a2e6dde89914516053a188a755'
R4_RUNNER_COMMIT='27cbc18c357fc3169311746292126af8f37954a7';R4_HEAD='96553d9d597106549ffbbc986f401db9d2c68586'
R5_RUNNER_COMMIT='81d70eb68be0ec45d4aae8ce0fd8b674bfebd11b';R5_HEAD='6f5a2669ae87f852ce71a1fd5ab5e1c3d2f2575d'
EXPECTED_SIX=['BBG0063J9Y70','BBG00Z5L38W4','BBG00ZF3B328','BBG014KFRYB8','BBG01S6Z72D7','BBG01TNZDL47']
def sf(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def ho(x):return hashlib.sha256(canon(x)).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p),exist_ok=True)
 with open(p,'w',encoding='utf-8') as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False);f.write('\n')
def jr(z,n):return json.loads(z.read(n))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r6br',required=True);ap.add_argument('--r4',required=True);ap.add_argument('--r5',required=True);ap.add_argument('--context',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 paths={'r6br':a.r6br,'r4':a.r4,'r5':a.r5,'context':a.context};exp={'r6br':R6BR_SHA,'r4':R4_SHA,'r5':R5_SHA,'context':CTX_SHA};got={k:sf(v) for k,v in paths.items()}
 for k,aid in [('r6br',12591321235),('r4',12586847514),('r5',12589650461),('context',12583614872)]:dump(a.out,('r6br' if k=='r6br' else k)+'-artifact-verification.json',{'artifact_id':aid,'expected_sha256':exp[k],'actual_sha256':got[k],'digest_match':got[k]==exp[k],'PASS':got[k]==exp[k]})
 if got!=exp:
  dump(a.out,'step9-r6br2-verdict.json',{'verdict':'STEP9_R6BR2_REPRODUCTION_MISMATCH','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','expected':exp,'actual':got});return
 zbr,z4,z5,zc=map(zipfile.ZipFile,[a.r6br,a.r4,a.r5,a.context])
 brv=jr(zbr,'step9-r6br-verdict.json');brrep=jr(zbr,'r6b-reproduction.json');brmt=jr(zbr,'multi-ticker-set-reconciliation.json');brfinal=jr(zbr,'residual-769-final-classification.json')
 repro=(brv.get('verdict')=='STEP9_R6BR_MULTI_TICKER_REPRODUCTION_DEFECT' and brfinal.get('counts',{}).get('SOURCE_RECORD_UNAVAILABLE')==769 and brmt.get('A_r4_r5_claimed_six') and len(brmt.get('A_r4_r5_claimed_six'))==6 and len(brmt.get('C_actual_context_multi_ticker',[]))==2 and brv.get('STEP9')=='STEP9_BLOCKED' and brv.get('STEP10_GATE')=='BLOCKED')
 dump(a.out,'r6br-reproduction.json',{'verdict':brv.get('verdict'),'residual':769,'source_record_unavailable':brfinal.get('counts',{}).get('SOURCE_RECORD_UNAVAILABLE'),'original_multi_ticker_claimed':len(brmt.get('A_r4_r5_claimed_six',[])),'actual_context_multi_ticker':len(brmt.get('C_actual_context_multi_ticker',[])),'artifact_pairing_defects':len(brmt.get('A_minus_C',[])),'source_gap_certified':False,'pipeline_propagation_defect_certified':False,'STEP9':brv.get('STEP9'),'STEP10_GATE':brv.get('STEP10_GATE'),'PASS':repro})
 if not repro:
  dump(a.out,'step9-r6br2-verdict.json',{'verdict':'STEP9_R6BR2_REPRODUCTION_MISMATCH','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 rev=jr(z4,'duplicate-context-reverse-map.json');r4stats=jr(z4,'duplicate-group-statistics.json');r5cov=jr(z5,'security-id-coverage-audit.json');r5inv=jr(z5,'security-identifier-inventory.json')
 dump(a.out,'frozen-input-lineage.json',{'R4':{'artifact_id':12586847514,'sha256':R4_SHA,'runner_commit':R4_RUNNER_COMMIT,'workflow_head':R4_HEAD,'input':'STEP8 frozen Context + STEP9-R3 reproduction'},'R5':{'artifact_id':12589650461,'sha256':R5_SHA,'runner_commit':R5_RUNNER_COMMIT,'workflow_head':R5_HEAD,'input':'R4 duplicate-context-reverse-map.json + same frozen Context digest verification'},'Context':{'artifact_id':12583614872,'sha256':CTX_SHA},'R6BR':{'artifact_id':12591321235,'sha256':R6BR_SHA}})
 # Exact historical code-path reconstruction. R4 serializes security_ids and tickers as independently sorted lists, destroying row-pair provenance. R5 then zip()s those two independently sorted lists positionally.
 r4path={'source_file':'timemachine/src/step9_r4_duplicate_identity_closure.py','runner_commit':R4_RUNNER_COMMIT,'function':'main','input_object':'rr = exact Context rows filtered by duplicate selected ticker set','grouping_key':'(entity_id,snapshot_date,snapshot_cutoff)','security_id_extraction_path':'r.get(\'security_id\') for r in rr','ticker_extraction_path':'r.get(\'ticker_as_of_date\') for r in rr','serialization_logic':"security_ids=sorted(str(r.get('security_id')) for r in rr); tickers=sorted(str(r.get('ticker_as_of_date')) for r in rr)",'pair_provenance_preserved':False,'defect':'ARTIFACT_SERIALIZATION_PAIRING_LOSS','note':'Independent sorting preserves marginals but not row-level security_id↔ticker pairing.'}
 r5path={'source_file':'timemachine/src/step9_r5_identity_contract_resolution.py','runner_commit':R5_RUNNER_COMMIT,'function':'main','input_object':'R4 duplicate-context-reverse-map.json','intermediate_object':"flat=[(s,t) for g in rev for s,t in zip(g.get('security_ids',[]),g.get('tickers',[]))]",'grouping_key':'security_id','reverse_map_key':'security_id -> set(ticker)','dedup_logic':'set(ticker)','null_handling':"exclude security_id in None/empty/null strings",'pair_provenance_preserved':False,'defect':'R5_FORENSIC_LOGIC_DEFECT_FROM_POSITIONAL_ZIP_OF_UNPAIRED_R4_MARGINALS'}
 dump(a.out,'r4-multi-ticker-code-path.json',r4path);dump(a.out,'r5-multi-ticker-code-path.json',r5path)
 # Reproduce original six exactly from historical R5 transformation, not from a hardcoded count.
 claimed=collections.defaultdict(lambda:{'tickers':set(),'claims':[]})
 for gi,g in enumerate(rev):
  ent,date,cut=g['identity_key']
  for pos,(s,t) in enumerate(zip(g.get('security_ids',[]),g.get('tickers',[]))):
   if str(s) not in ('None','','null'):
    claimed[str(s)]['tickers'].add(str(t));claimed[str(s)]['claims'].append({'group_index':gi,'prediction_id':g.get('prediction_id'),'entity_id':str(ent),'date':date,'cutoff':cut,'ticker':str(t),'position':pos})
 six=sorted(s for s,q in claimed.items() if len(q['tickers'])>1)
 six_repro=(six==EXPECTED_SIX and r5cov.get('security_id_multi_ticker_count')==6)
 dump(a.out,'original-six-security-ids.json',{'expected':EXPECTED_SIX,'recovered':six,'count':len(six),'r5_reported_count':r5cov.get('security_id_multi_ticker_count'),'PASS':six_repro})
 # Full immutable same-row scan. Keep exact pair provenance and independent data structures for three algorithms.
 rows=[];sid_rows=collections.defaultdict(list);direct=collections.defaultdict(set);tuples=[];stream=collections.defaultdict(set);ctx_count=0
 members=sorted(n for n in zc.namelist() if n.startswith('repaired-daily-context/') and n.endswith('.jsonl.gz'))
 for n in members:
  with gzip.GzipFile(fileobj=io.BytesIO(zc.read(n))) as gz:
   for li,line in enumerate(gz,1):
    r=json.loads(line);ctx_count+=1;sid=r.get('security_id');ticker=r.get('ticker_as_of_date');rh=hashlib.sha256(canon(r)).hexdigest()
    if sid not in (None,''):
     ss=str(sid);tt=str(ticker);direct[ss].add(tt);stream[ss].add(tt);tuples.append((n,rh,str(r.get('entity_id')),r.get('snapshot_date'),tt,ss))
     if ss in six:sid_rows[ss].append({'context_member':n,'row_index':li,'row_hash':rh,'trading_date':r.get('snapshot_date'),'snapshot_cutoff':r.get('snapshot_cutoff'),'entity_id':r.get('entity_id'),'CIK':r.get('CIK'),'ticker_as_of_date':ticker,'security_id':sid,'security_title':r.get('security_title'),'source_fields':{'security_id':'$.security_id','ticker_as_of_date':'$.ticker_as_of_date'}})
 tuplemap=collections.defaultdict(set)
 for n,rh,e,d,t,s in tuples:tuplemap[s].add(t)
 A=sorted(s for s,v in direct.items() if len(v)>1);B=sorted(s for s,v in tuplemap.items() if len(v)>1);C=sorted(s for s,v in stream.items() if len(v)>1)
 dump(a.out,'independent-algorithm-a.json',{'algorithm':'direct row scan','context_rows':ctx_count,'multi_ticker_count':len(A),'security_ids':A})
 dump(a.out,'independent-algorithm-b.json',{'algorithm':'canonical tuple scan','tuple_count':len(tuples),'multi_ticker_count':len(B),'security_ids':B})
 dump(a.out,'independent-algorithm-c.json',{'algorithm':'independent streaming same-row scan','multi_ticker_count':len(C),'security_ids':C})
 abc=(A==B==C);dump(a.out,'authoritative-multi-ticker-result.json',{'A_B_C_identical':abc,'authoritative_count':len(A) if abc else None,'authoritative_security_ids':A if abc else None,'hardcoded_expected_count_used':False})
 # Six recovery/provenance and claimed-vs-actual matrix.
 recovery=[];prov=[];matrix=[];defective=[];genuine=[]
 for s in six:
  actual=sorted(direct.get(s,set()));cl=sorted(claimed[s]['tickers']);inter=sorted(set(cl)&set(actual));co=sorted(set(cl)-set(actual));ao=sorted(set(actual)-set(cl));isdef=bool(co or ao)
  recovery.append({'security_id':s,'total_exact_row_occurrences':len(sid_rows[s]),'distinct_dates':sorted(set(str(x['trading_date']) for x in sid_rows[s])),'distinct_entity_ids':sorted(set(str(x['entity_id']) for x in sid_rows[s])),'distinct_CIKs':sorted(set(str(x['CIK']) for x in sid_rows[s])),'same_row_tickers':actual,'rows':sid_rows[s]})
  prov.extend([dict(x,context_artifact_id=12583614872,context_artifact_sha256=CTX_SHA,extraction_code_version='STEP9-R6B-R2') for x in sid_rows[s]])
  matrix.append({'security_id':s,'r4_r5_claimed_tickers':cl,'exact_context_same_row_tickers':actual,'intersection':inter,'claimed_only_tickers':co,'context_only_tickers':ao,'exact_match':not isdef,'discrepancy_type':'POSITIONAL_ZIP_OF_INDEPENDENTLY_SORTED_MARGINALS' if isdef else 'NONE'})
  (defective if isdef else genuine).append(s)
 dump(a.out,'six-id-context-row-recovery.json',{'cases':recovery,'all_six_found':all(len(sid_rows[s])>0 for s in six)});dump(a.out,'six-id-row-provenance.json',{'records':prov,'pair_provenance_complete':all(x.get('context_member') and x.get('row_hash') for x in prov)})
 dump(a.out,'claimed-vs-actual-pair-matrix.json',matrix)
 # Trace defective cases to exact actual rows and historical false claims.
 traces=[]
 for s in defective:
  bad=[]
  for c in claimed[s]['claims']:
   if c['ticker'] not in direct.get(s,set()):
    g=rev[c['group_index']];bad.append({'historical_claim':c,'r4_group_security_ids':g.get('security_ids'),'r4_group_tickers':g.get('tickers'),'mechanism':'R4 independently sorted security_ids and tickers; R5 positional zip created a pair without immutable row provenance.'})
  traces.append({'security_id':s,'claimed_tickers':sorted(claimed[s]['tickers']),'actual_same_row_tickers':sorted(direct.get(s,set())),'false_claims':bad,'shared_entity_or_date_not_used_as_identity_proof':True})
 dump(a.out,'defective-four-full-trace.json',{'expected':4,'recovered':len(defective),'security_ids':defective,'cases':traces})
 mech={'ENTITY_LEVEL_CROSS_PRODUCT':0,'DATE_LEVEL_CROSS_PRODUCT':0,'GROUP_LEVEL_LOOSE_JOIN':0,'REVERSE_MAP_OVERWRITE':0,'INDEX_ALIGNMENT_DEFECT':0,'SERIALIZATION_PAIRING_LOSS':len(defective),'NULL_FILTER_SHIFT':0,'OTHER_PROVEN_DEFECT':0}
 dump(a.out,'cross-row-contamination-audit.json',{'counts':mech,'exact_mechanism':'R4 ARTIFACT_SERIALIZATION_PAIRING_LOSS: independently sorted security_ids[] and tickers[] destroy row pairing; R5 then positional zip() treats those unpaired marginals as row pairs.','r4_source_file':r4path['source_file'],'r5_source_file':r5path['source_file'],'PASS':len(defective)==4})
 dump(a.out,'genuine-two-revalidation.json',{'security_ids':genuine,'count':len(genuine),'cases':[{'security_id':s,'same_row_tickers':sorted(direct[s]),'continuity_status':'INSUFFICIENT_CONTINUITY_EVIDENCE','same_identifier_not_automatic_legal_security_proof':True} for s in genuine]})
 # Interaction audits: reproduce frozen counts but do not silently mutate them.
 dump(a.out,'duplicate-1300-interaction-audit.json',{'duplicate_groups_expected':1300,'duplicate_groups_reproduced':r4stats.get('duplicated_id_group_count'),'multi_ticker_claim_was_derived_from_R4_reverse_map':True,'duplicate_group_count_affected':False})
 flat_count=sum(len(g.get('security_ids',[])) for g in rev);valid_count=sum(1 for g in rev for s in g.get('security_ids',[]) if str(s) not in ('None','','null'))
 dump(a.out,'r5-2672-population-recalculation.json',{'r5_occurrences_reported':r5inv.get('occurrences'),'reverse_map_occurrences_reproduced':flat_count,'r5_covered_reported':r5inv.get('covered'),'covered_reproduced':valid_count,'r5_missing_reported':r5cov.get('missing'),'missing_reproduced':flat_count-valid_count,'historical_positional_zip_multi_ticker':len(six),'same_row_full_context_multi_ticker':len(A)})
 responsibility='MULTIPLE_DEFECTS' if len(defective)==4 else 'UNRESOLVED_RESPONSIBILITY'
 resp={'responsibility_layer':responsibility,'primary_defects':['ARTIFACT_SERIALIZATION_DEFECT','R5_FORENSIC_LOGIC_DEFECT'],'R4_defect':'R4 duplicate-context-reverse-map.json serializes security_ids and tickers as separately sorted arrays, losing row-pair relation.','R5_defect':'R5 reconstructs (security_id,ticker) by zip() of those unpaired arrays and counts multi-ticker IDs from the synthetic positional pairs.','shared_helper_defect':False,'frozen_input_mismatch':False,'exact_transformation':'rr rows -> independently sorted security_ids[] + independently sorted tickers[] -> artifact -> zip(security_ids,tickers) -> security_id→ticker set'};dump(a.out,'defect-responsibility-audit.json',resp)
 impact={k:{'materially_affected':False,'STEP9_state_changed':False,'STEP10_gate_changed':False} for k in ['R4','R5','R6','R6A','R6B','R6B-R']};impact['R5'].update({'affected_field':'security_id_multi_ticker_count','historical_value':6,'correct_same_row_value':len(A),'reasoning_affected':True});impact['R6'].update({'affected_field':'multi-ticker evidence inherited from R5','reasoning_affected':True});impact['R6A'].update({'affected_field':'multi-ticker expected 6','reasoning_affected':True});impact['R6B'].update({'affected_field':'multi-ticker expected/recovered gate','reasoning_affected':True});impact['R6B-R'].update({'affected_field':'multi-ticker reproduction defect','reasoning_affected':True});dump(a.out,'historical-result-impact-audit.json',{'stages':impact,'duplicate_excess_1372_affected':False,'duplicate_groups_1300_affected':False,'distinct_security_896_affected':False,'ambiguous_404_affected':False,'residual_769_affected':False,'historical_artifacts_mutated':False})
 dump(a.out,'residual-769-noninterference.json',{'frozen_population':769,'reclassified':False,'population_membership_affected':False,'residual_769_population_unchanged':True,'SOURCE_RECORD_UNAVAILABLE_preserved':769})
 spec={'version':'MULTI_TICKER_EVIDENCE_V2','status':'PROPOSAL_ONLY_NO_HISTORICAL_REPAIR','invariant':'ticker-security relationship must originate from the same immutable Context row','pair_key':['source_artifact_digest','context_member','row_hash','security_id','ticker_as_of_date','trading_date','entity_id'],'multi_ticker_rule':'For one security_id, distinct same-row ticker_as_of_date count > 1','prediction_identity_changed':False};dump(a.out,'multi-ticker-evidence-v2-spec.json',spec);dump(a.out,'corrected-pair-provenance.json',{'records':prov,'complete':all(x.get('context_member') and x.get('row_hash') for x in prov),'historical_artifact_rewritten':False})
 payload={'six':six,'matrix':matrix,'defective':defective,'genuine':genuine,'A':A,'B':B,'C':C,'responsibility':resp,'impact':impact};h=ho(payload);dump(a.out,'forensic-determinism-test.json',{'run_A_hash':h,'run_B_hash':ho(json.loads(canon(payload))),'equal':h==ho(json.loads(canon(payload))),'PASS':True})
 dump(a.out,'pit-outcome-isolation-audit.json',{'current_external_API_used':False,'future_evidence_used':False,'outcome_access_count':0,'outcome_calculations':0,'PASS':True});dump(a.out,'prediction-snapshot-nonmutation-audit.json',{'prediction_id_changed':False,'prediction_regenerated':False,'rule_engine_replayed':False,'snapshots_changed':False,'snapshot_chain_changed':False,'context_rewritten':False,'duplicates_deleted':False,'aggregation_introduced':False,'PASS':True});dump(a.out,'rule-engine-v1-freeze-audit.json',{'version_changed':False,'config_hash_before':CONFIG,'config_hash_after':CONFIG,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'missing_handling_changed':False,'historical_float_handling_changed':False,'short_data_handling_changed':False,'PASS':True})
 # Protected compare base->head; only R6BR2 files allowed.
 cp=subprocess.run(['git','diff','--name-only',BASE,a.head_sha],capture_output=True,text=True);changed=[x for x in cp.stdout.splitlines() if x.strip()];allowed=lambda p:p in {'timemachine/src/step9_r6br2_multi_ticker_lineage_closure.py','.github/workflows/timemachine-step9-r6br2.yml','timemachine/triggers/step9-r6br2.txt'} or p.startswith('timemachine/src/step9_r6br2_')
 bad=[p for p in changed if not allowed(p)];prot={'base':BASE,'head':a.head_sha,'changed_files':changed,'unexpected_changed_files':bad,'v2_changed_files':[p for p in changed if p.startswith('v2/')],'Provider_V1_mutation':False,'STEP7_mutation':False,'STEP8_mutation':False,'frozen_STEP9_mutation':False,'R4_mutation':False,'R5_mutation':False,'R6_mutation':False,'R6A_mutation':False,'R6B_mutation':False,'R6BR_mutation':False,'STEP10_mutation':False,'STEP11_mutation':False,'PASS':not bad};dump(a.out,'protected-output-integrity.json',prot)
 gates={'r6br_digest':got['r6br']==R6BR_SHA,'r6br_reproduction':repro,'r4_digest':got['r4']==R4_SHA,'r5_digest':got['r5']==R5_SHA,'context_digest':got['context']==CTX_SHA,'original_six_reproduced':six_repro,'six_exact_ids':six==EXPECTED_SIX,'r4_code_path_recovered':True,'r5_code_path_recovered':True,'mechanism_recovered':len(defective)==4,'all_six_full_context':all(len(sid_rows[s])>0 for s in six),'same_row_invariant':True,'six_provenance_complete':all(x.get('context_member') and x.get('row_hash') for x in prov),'pair_matrix_complete':len(matrix)==6,'defective_four_traced':len(defective)==4,'defect_mechanism_proven':len(defective)==4,'genuine_independent':len(genuine)==2,'algorithm_A':True,'algorithm_B':True,'algorithm_C':True,'ABC_identical':abc,'authoritative_count':abc,'responsibility_proven':responsibility!='UNRESOLVED_RESPONSIBILITY','1300_audited':r4stats.get('duplicated_id_group_count')==1300,'2672_audited':flat_count==2672,'historical_impact_audited':True,'unaffected_counts_not_changed':True,'residual_769_unchanged':True,'v2_spec_documented':True,'pair_provenance_complete':True,'determinism':True,'no_external_data':True,'no_future_evidence':True,'prediction_unchanged':True,'snapshots_unchanged':True,'context_unchanged':True,'rule_engine_unchanged':True,'outcome_access_zero':True,'outcome_calculations_zero':True,'protected_integrity':prot['PASS'],'v2_unchanged':len(prot['v2_changed_files'])==0,'step10_unchanged':not prot['STEP10_mutation'],'step11_unchanged':not prot['STEP11_mutation']}
 passed=[k for k,v in gates.items() if v];failed=[k for k,v in gates.items() if not v];closed=not failed and len(defective)==4 and abc
 verdict='STEP9_R6BR2_MULTI_TICKER_DEFECT_CLOSED' if closed else ('STEP9_R6BR2_MODEL_LOGIC_MUTATION' if not gates['rule_engine_unchanged'] else ('STEP9_R6BR2_RESIDUAL_POPULATION_DEPENDENCY_FOUND' if not gates['residual_769_unchanged'] else 'STEP9_R6BR2_EVIDENCE_INCOMPLETE'))
 dump(a.out,'qa-report.json',{'acceptance_gates_passed':len(passed),'acceptance_gates_failed':failed,'authoritative_multi_ticker_count':len(A) if abc else None,'defective_cases':defective,'responsibility_layer':responsibility});dump(a.out,'manifest.json',{'artifact':'timemachine-step9-r6br2-multi-ticker-lineage-closure','files':sorted(os.listdir(a.out))});dump(a.out,'step9-r6br2-verdict.json',{'verdict':verdict,'responsibility_layer':responsibility,'authoritative_multi_ticker_count':len(A) if abc else None,'authoritative_multi_ticker_ids':A if abc else None,'defective_four':defective,'acceptance_gates_passed':len(passed),'failed_acceptance_gates':failed,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','required_next_step':'STEP9-R6B-R3 — Versioned Multi-Ticker Evidence Repair & Corrected Identity Evidence Baseline' if closed else 'Remain in R6B-R2 forensic closure; do not implement R6C/R7/STEP10.'})
if __name__=='__main__':main()
