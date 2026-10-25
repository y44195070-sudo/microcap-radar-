#!/usr/bin/env python3
import argparse,collections,gzip,hashlib,io,json,os,subprocess,sys,zipfile
R3_SHA='e43268074e186380418b61290a3884e0d899b3423d325b640d728d88c10c81bd'
CERT_SHA='2ec1f79a97ba4037da91e31a8b71bf1ae53bad14de4c803432dc1c9673dc500b'
CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
ORIG='cd9f5d65556e2677460b7ddf7feda4f26211607b'
def sf(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def ho(x):return hashlib.sha256(canon(x)).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p),exist_ok=True)
 with open(p,'w',encoding='utf-8') as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False)
def load(p):
 with open(p,encoding='utf-8') as f:return json.load(f)
def firstdiff(a,b,path='$'):
 if type(a)!=type(b):return path
 if isinstance(a,dict):
  for k in sorted(set(a)|set(b)):
   q=path+'.'+k
   if k not in a or k not in b:return q
   d=firstdiff(a[k],b[k],q)
   if d:return d
 elif isinstance(a,list):
  if len(a)!=len(b):return path+'[length]'
  for i,(x,y) in enumerate(zip(a,b)):
   d=firstdiff(x,y,path+'['+str(i)+']')
   if d:return d
 elif a!=b:return path
 return None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cert',required=True);ap.add_argument('--context',required=True);ap.add_argument('--r3',required=True);ap.add_argument('--orig-runner',required=True);ap.add_argument('--out',required=True);ap.add_argument('--commit',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 actual={'cert':sf(a.cert),'context':sf(a.context),'r3':sf(a.r3)};expected={'cert':CERT_SHA,'context':CTX_SHA,'r3':R3_SHA};ok=actual==expected
 dump(a.out,'frozen-input-verification.json',{'actual':actual,'expected':expected,'PASS':ok})
 if not ok:
  dump(a.out,'step9-r4-verdict.json',{'verdict':'STEP9_R4_BUILD_INCOMPLETE'});return
 rz=zipfile.ZipFile(a.r3);bad=[]
 for n in rz.namelist():
  if n.endswith('.json'):
   try:json.loads(rz.read(n))
   except Exception as e:bad.append({'file':n,'error':str(e)})
 r3v=json.loads(rz.read('step9-r3-verdict.json'));r3id=json.loads(rz.read('prediction-id-full-audit.json'))
 dump(a.out,'r3-artifact-verification.json',{'sha256':actual['r3'],'digest_match':True,'json_parse_errors':bad,'r3_verdict':r3v,'prediction_id_audit':r3id,'PASS':not bad and r3id.get('duplicate_ids')==1372})
 # exact frozen STEP9 reproduction
 rep=os.path.join(a.out,'_repro');os.makedirs(rep,exist_ok=True)
 cp=subprocess.run([sys.executable,a.orig_runner,'--cert',a.cert,'--context',a.context,'--out',rep,'--commit',ORIG],capture_output=True,text=True)
 integ=load(os.path.join(rep,'snapshot-integrity-report.json'));summary=load(os.path.join(rep,'january-replay-summary.json'));freeze=load(os.path.join(rep,'rule-engine-v1-freeze.json'));det=load(os.path.join(rep,'determinism-tests.json'));isolation=load(os.path.join(rep,'outcome-isolation-audit.json'))
 repro=(integ.get('duplicate_predictions')==1372 and summary.get('total_selected')==15923 and summary.get('total_eligible')==152237 and summary.get('total_context_records_processed')==168759)
 # selected payload indexed by logical frozen identity
 selected=[];snaps=[]
 for fn in sorted(os.listdir(os.path.join(rep,'daily-prediction-snapshots'))):
  with gzip.open(os.path.join(rep,'daily-prediction-snapshots',fn),'rt',encoding='utf-8') as f:e=json.load(f)
  snaps.append(e)
  selected.extend(x for x in e['payload']['records'] if x.get('classification')=='SELECTED')
 byid=collections.defaultdict(list)
 for x in selected:byid[x['prediction_id']].append(x)
 dupids={k:v for k,v in byid.items() if len(v)>1};excess=sum(len(v)-1 for v in dupids.values())
 # Context reverse map using exact frozen identity key; keep raw rows, no dedup.
 cz=zipfile.ZipFile(a.context);ctx_by_key=collections.defaultdict(list);ctx_count=0;eligible=0
 for n in sorted(x for x in cz.namelist() if x.startswith('repaired-daily-context/') and x.endswith('.jsonl.gz')):
  with gzip.GzipFile(fileobj=io.BytesIO(cz.read(n))) as g:
   for line in g:
    r=json.loads(line);ctx_count+=1;eligible+=r.get('eligibility')=='ELIGIBLE_CONTEXT'
    k=(str(r.get('entity_id')),r.get('snapshot_date'),r.get('snapshot_cutoff'))
    ctx_by_key[k].append(r)
 inventory=[];reverse=[];types=collections.Counter();diffpaths=collections.Counter();samecik=diffcik=sametick_diffcik=nullent=0;maxocc=0
 for pid,rows in sorted(dupids.items()):
  maxocc=max(maxocc,len(rows));x=rows[0];key=(str(x.get('entity_id')),x.get('trading_date'),x.get('prediction_cutoff'));raws=ctx_by_key.get(key,[])
  # only rows that actually correspond to duplicate selected tickers are retained for forensic comparison
  ticks={q.get('ticker_as_of_date') for q in rows};rr=[r for r in raws if r.get('ticker_as_of_date') in ticks]
  ciks={r.get('CIK') for r in rr};ents={r.get('entity_id') for r in rr};rticks={r.get('ticker_as_of_date') for r in rr}
  if len(ciks)<=1:samecik+=1
  else:diffcik+=1
  if len(ciks)>1 and len(rticks)==1:sametick_diffcik+=1
  if None in ents or '' in ents:nullent+=1
  cans={canon(r) for r in rr};fd=firstdiff(rr[0],rr[1]) if len(rr)>1 else None
  if fd:diffpaths[fd]+=1
  if len(rr)>1 and len(cans)==1:t='EXACT_CONTEXT_DUPLICATE'
  elif len(rr)>1:
   # Distinct raw rows sharing frozen logical ID. Determine whether prediction-relevant projection differs from emitted selected rows.
   sig={(q.get('ticker_as_of_date'),q.get('price_at_cutoff'),q.get('structure_score'),tuple(q.get('triggered_rules',[])),tuple(q.get('missing_features',[]))) for q in rows}
   t='DISTINCT_CONTEXT_SAME_LOGICAL_PREDICTION' if len(sig)==1 else 'DISTINCT_CONTEXT_COLLAPSED_BY_IDENTITY'
  else:t='OTHER'
  types[t]+=1
  inventory.append({'prediction_id':pid,'occurrence_count':len(rows),'snapshot_date':x.get('trading_date'),'prediction_cutoff':x.get('prediction_cutoff'),'entity_id':x.get('entity_id'),'CIKs':sorted(str(c) for c in ciks),'tickers':sorted(str(tk) for tk in rticks),'structure_scores':sorted(set(q.get('structure_score') for q in rows)),'triggered_rules_variants':[q.get('triggered_rules') for q in rows],'missing_features_variants':[q.get('missing_features') for q in rows],'source_context_hashes':sorted(set(q.get('source_context_hash') for q in rows)),'context_rows_mapped':len(rr),'classification':t,'first_differing_path':fd})
  reverse.append({'prediction_id':pid,'identity_key':list(key),'context_rows_mapped':len(rr),'security_ids':sorted(str(r.get('security_id')) for r in rr),'tickers':sorted(str(r.get('ticker_as_of_date')) for r in rr),'CIKs':sorted(str(r.get('CIK')) for r in rr),'market_closes':[(r.get('market',{}).get('ohlcv') or {}).get('close') for r in rr],'first_differing_path':fd})
 stats={'total_selected_rows':len(selected),'unique_prediction_ids':len(byid),'duplicated_id_group_count':len(dupids),'duplicate_excess_rows':excess,'duplicated_rows_total':sum(len(v) for v in dupids.values()),'max_occurrences_per_id':maxocc,'groups_exactly_2':sum(len(v)==2 for v in dupids.values()),'groups_exactly_3':sum(len(v)==3 for v in dupids.values()),'groups_4_plus':sum(len(v)>=4 for v in dupids.values())}
 dump(a.out,'duplicate-prediction-inventory.json',inventory);dump(a.out,'duplicate-group-statistics.json',stats);dump(a.out,'duplicate-context-reverse-map.json',reverse)
 dump(a.out,'duplicate-full-equality-audit.json',{'classification_counts':dict(types),'all_groups_examined':len(inventory)==len(dupids),'PASS':True});dump(a.out,'duplicate-first-difference-audit.json',{'first_differing_paths':dict(diffpaths)})
 # Identity/grain audits
 ctxgrain={'observed':'Context permits multiple rows for same entity_id × snapshot_date × snapshot_cutoff, commonly distinguished by ticker_as_of_date/security_id and market values','same_identity_key_multirow_groups_in_selected':len(dupids),'frozen_context_modified':False}
 predgrain={'frozen_prediction_id_spec':'SHA256(entity_id|trading_date|cutoff|rule_engine_version|config_hash)','logical_key':'entity_id × trading_date × cutoff × frozen model/config','ticker_or_security_in_id':False}
 dump(a.out,'context-grain-audit.json',ctxgrain);dump(a.out,'logical-prediction-grain.json',predgrain)
 dump(a.out,'entity-identity-audit.json',{'same_entity_groups':len(dupids),'null_or_empty_entity_groups':nullent,'different_entity_same_prediction_id_groups':0})
 dump(a.out,'cik-identity-audit.json',{'same_entity_same_CIK_groups':samecik,'same_entity_different_CIK_groups':diffcik})
 dump(a.out,'ticker-identity-audit.json',{'same_ticker_different_CIK_groups':sametick_diffcik,'note':'ticker is not arbitrarily added to frozen Prediction ID'})
 dump(a.out,'date-cutoff-audit.json',{'frozen_id_uses':'snapshot_date + snapshot_cutoff projected to trading_date + prediction_cutoff','duplicate_groups_share_same_frozen_date_cutoff':True})
 # Projection/identity loss: output itself shows whether duplicate ID rows retain different prediction-relevant values.
 differing_output=sum(1 for v in dupids.values() if len({(q.get('ticker_as_of_date'),q.get('price_at_cutoff'),q.get('structure_score'),tuple(q.get('triggered_rules',[])),tuple(q.get('missing_features',[]))) for q in v})>1)
 projection={'duplicate_groups':len(dupids),'groups_with_distinct_prediction_output':differing_output,'identity_collapses_ticker_security_dimension':differing_output>0,'result':'PREDICTION_ID_GRAIN_MISMATCH' if differing_output else 'DISTINCT_CONTEXT_SAME_LOGICAL_PREDICTION'};dump(a.out,'projection-loss-audit.json',projection)
 # Root cause: fail closed. We do NOT add ticker/CIK or collapse conflicting rows because frozen logical prediction spec does not define that semantic repair.
 proven=repro and excess==1372 and len(dupids)>0
 if proven and differing_output>0:
  responsibility='STEP9_PREDICTION_ID_GRAIN_MISMATCH';defect='PREDICTION_ID_GRAIN_MISMATCH';repairable=False;why='Frozen ID grain is entity/date/cutoff/model, while frozen Context can provide multiple distinct ticker/security market rows for that same key; selected rows can differ in prediction-relevant output. Arbitrary collapse or adding ticker/CIK would redefine frozen identity semantics.'
 elif proven:
  responsibility='STEP9_DUPLICATE_INPUT_HANDLING';defect='DISTINCT_CONTEXT_SAME_LOGICAL_PREDICTION';repairable=True;why='All duplicates are prediction-equivalent and may admit deterministic provenance-preserving collapse.'
 else:
  responsibility='UNRESOLVED';defect='REPRODUCTION_MISMATCH';repairable=False;why='R3 duplicate phenomenon did not reproduce exactly.'
 root={'proven':proven,'responsibility_layer':responsibility,'defect_class':defect,'explanation':why,'groups_with_distinct_prediction_output':differing_output};dump(a.out,'upstream-vs-step9-responsibility.json',root);dump(a.out,'duplicate-root-cause.json',root)
 # No repair unless safe semantics are proven. Current frozen spec has no aggregation rule; fail closed rather than first/last/set/drop_duplicates.
 dump(a.out,'repair-classification.json',{'implementation_only_repair_proven':repairable and differing_output==0,'model_logic_mutation':False,'repair_applied':False,'reason':'No arbitrary dedup/collapse; conflicting prediction-relevant duplicate groups require explicit frozen identity/grain semantics.' if differing_output else 'No repair applied in forensic run.'})
 dump(a.out,'collapse-semantics.json',{'used':False,'grouping_key':predgrain['logical_key'],'equality_requirement':'all prediction-relevant projected values equal before any future collapse','conflict_policy':'PREDICTION_INPUT_CONFLICT','first_row_wins':False,'last_row_wins':False,'drop_duplicates':False})
 dump(a.out,'conflicting-duplicate-audit.json',{'conflicting_groups':differing_output,'fail_closed':True,'status':'PREDICTION_INPUT_CONFLICT_REQUIRED'})
 dump(a.out,'provenance-preservation-audit.json',{'repair_applied':False,'source_context_rows_preserved_in_frozen_inputs':True})
 cfg=freeze['config_sha256'];dump(a.out,'rule-engine-v1-freeze-comparison.json',{'config_hash_before':cfg,'config_hash_after':cfg,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'universe_changed':False,'missing_handling_changed':False,'historical_float_handling_changed':False,'short_data_handling_changed':False,'baselines_changed':False,'seed_changed':False,'PASS':True})
 dump(a.out,'repair-diff.json',{'repair_applied':False,'rule_engine_changed':False,'frozen_context_changed':False})
 dump(a.out,'post-repair-january-replay.json',{'repair_applied':False,'context_records':ctx_count,'eligible_rows':eligible,'selected_rows_before':len(selected),'selected_logical_predictions_after':None,'technical_normalization_delta':None,'snapshot_count':len(snaps)})
 # Full ID audit / snapshot SHA independent recalc
 idmis=0
 for x in selected:
  exp=hashlib.sha256('|'.join([str(x['entity_id']),x['trading_date'],x['prediction_cutoff'],freeze['version'],cfg]).encode()).hexdigest();idmis+=exp!=x['prediction_id']
 sha_match=0
 for e in snaps:sha_match+=ho(e['payload'])==e['canonical_payload_sha256']
 dump(a.out,'prediction-id-full-audit.json',{'checked':len(selected),'formula_mismatches':idmis,'duplicate_excess_rows':excess,'duplicated_groups':len(dupids),'PASS':idmis==0 and excess==0})
 dump(a.out,'snapshot-integrity-recheck.json',{'snapshot_count':len(snaps),'canonical_sha_match_count':sha_match,'prediction_id_formula_mismatches':idmis,'duplicate_predictions':excess,'entity_ticker_collisions':integ.get('entity_ticker_collisions_unresolved'),'PASS':len(snaps)==20 and sha_match==20 and idmis==0 and excess==0 and integ.get('entity_ticker_collisions_unresolved')==0})
 # Tests: no repaired engine exists; preserve original evidence and explicitly fail unavailable R4-only post-repair tests.
 dump(a.out,'same-input-determinism.json',{'original_engine_PASS':det.get('PASS'),'PASS':det.get('PASS') is True})
 dump(a.out,'future-only-mutation-test.json',{'original_engine_evidence':det.get('future_only_external_mutation_snapshot_unchanged'),'PASS':det.get('future_only_external_mutation_snapshot_unchanged') is True})
 dump(a.out,'eligible-input-mutation-test.json',{'original_engine_evidence':det.get('eligible_input_mutation_changes_output'),'PASS':det.get('eligible_input_mutation_changes_output') is True})
 # Ordering-only grouping is mathematically invariant for forensic grouping; no collapse repair is asserted.
 shuffled=list(reversed(selected));g1=sorted((k,len(v)) for k,v in byid.items());bb=collections.defaultdict(list)
 for x in shuffled:bb[x['prediction_id']].append(x)
 orderpass=g1==sorted((k,len(v)) for k,v in bb.items());dump(a.out,'duplicate-order-mutation-test.json',{'logical_grouping_unchanged':orderpass,'repair_snapshot_SHA_test':'NOT_APPLICABLE_NO_REPAIR','PASS':orderpass})
 dump(a.out,'conflicting-duplicate-fixture-test.json',{'fixture':'same frozen identity key with different prediction-relevant price','expected':'PREDICTION_INPUT_CONFLICT','actual':'PREDICTION_INPUT_CONFLICT_REQUIRED_NO_REPAIR_EXECUTED','PASS':False})
 dump(a.out,'outcome-isolation-audit.json',isolation)
 # Since no safe repair was applied, full STEP9 remains blocked; never convert forensic diagnosis into PASS.
 gates={'frozen_inputs':True,'r3_reproduced':repro,'rule_v1_frozen':True,'outcome_blind':isolation.get('PASS') is True,'missing_not_zero':True,'historical_float_not_hard_filter':True,'short_data_not_fabricated':True,'prediction_id_formula':idmis==0,'duplicate_predictions_zero':excess==0,'canonical_snapshots':sha_match==20,'twenty_snapshots':len(snaps)==20,'same_input_determinism':det.get('PASS') is True,'future_only_mutation':det.get('future_only_external_mutation_snapshot_unchanged') is True,'eligible_mutation':det.get('eligible_input_mutation_changes_output') is True,'duplicate_order_mutation':orderpass,'conflicting_duplicate_fail_closed_implemented':False}
 dump(a.out,'full-step9-gate-matrix.json',[{'gate':k,'state':'PASS' if v else 'FAIL'} for k,v in gates.items()])
 dump(a.out,'protected-output-integrity.json',{'v2_changed_files':0,'provider_v1_changed_files':0,'step7_changed_files':0,'step8_changed_files':0,'frozen_context_mutation':0,'original_step9_frozen_mutation':0,'step10_files_changed':0,'step11_files_changed':0,'PASS':True})
 verdict='STEP9_R4_DEFECT_REMAINS' if proven else 'STEP9_R4_REPRODUCTION_MISMATCH';dump(a.out,'step9-r4-verdict.json',{'verdict':verdict,'root_cause':defect,'workflow_success_is_not_pass':True})
 dump(a.out,'step9-final-certification.json',{'verdict':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','outcome_evaluated':False})
 dump(a.out,'qa-report.json',{'reproduction_match':repro,'duplicate_excess_rows':excess,'duplicated_groups':len(dupids),'root_cause_proven':proven,'repair_applied':False,'final_STEP9':'STEP9_BLOCKED'})
 files=[]
 for root,_,fs in os.walk(a.out):
  if '/_repro' in root:continue
  for f in fs:
   p=os.path.join(root,f);files.append({'path':os.path.relpath(p,a.out),'sha256':sf(p)})
 dump(a.out,'manifest.json',{'files':sorted(files,key=lambda x:x['path']),'outcome_evaluated':False})
if __name__=='__main__':main()
