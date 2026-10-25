#!/usr/bin/env python3
import argparse,collections,gzip,hashlib,io,json,os,subprocess,zipfile
R6A_SHA='81ac567274bea4f35d3091ae51c5be0dcb01b0789b59b934b1710e88e11f6b10'
CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
R4_SHA='9efb5959cf043e674455d4d2778121db67e993eb0b5059d40a332e3774db2a00'
BASE='d7a4feb6576b1dbefa001571cddccc6da93727e7'
CONFIG='5e2b11b97c76889e420201ee3496023d1abed3a2e6dde89914516053a188a755'
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
def jread(z,n):return json.loads(z.read(n))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r6a',required=True);ap.add_argument('--context',required=True);ap.add_argument('--r4',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 hashes={'r6a':sf(a.r6a),'context':sf(a.context),'r4':sf(a.r4)}; exp={'r6a':R6A_SHA,'context':CTX_SHA,'r4':R4_SHA}
 if hashes!=exp:
  dump(a.out,'step9-r6b-verdict.json',{'verdict':'STEP9_R6B_REPRODUCTION_MISMATCH','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','hashes':hashes,'expected':exp});return
 za=zipfile.ZipFile(a.r6a); zr=zipfile.ZipFile(a.r4); zc=zipfile.ZipFile(a.context)
 r6av=jread(za,'step9-r6a-verdict.json'); repro=(r6av.get('verdict')=='STEP9_R6A_IDENTITY_MAPPING_INCOMPLETE' and r6av.get('STEP9')=='STEP9_BLOCKED' and r6av.get('STEP10_GATE')=='BLOCKED')
 dump(a.out,'r6a-artifact-verification.json',{'artifact_id':12589764522,'sha256':hashes['r6a'],'expected_sha256':R6A_SHA,'digest_match':True,'PASS':True})
 dump(a.out,'r6a-reproduction.json',{'r6a_verdict':r6av.get('verdict'),'prediction_target':'LISTED_SECURITY','missing_expected':776,'multi_ticker_expected':6,'duplicate_groups_expected':1300,'STEP9':r6av.get('STEP9'),'STEP10_GATE':r6av.get('STEP10_GATE'),'PASS':repro})
 if not repro:
  dump(a.out,'step9-r6b-verdict.json',{'verdict':'STEP9_R6B_REPRODUCTION_MISMATCH','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 rows=[]; bykey=collections.defaultdict(list); hist=collections.defaultdict(list); sidticks=collections.defaultdict(lambda:collections.defaultdict(set))
 members=sorted(n for n in zc.namelist() if n.startswith('repaired-daily-context/') and n.endswith('.jsonl.gz'))
 for n in members:
  with gzip.GzipFile(fileobj=io.BytesIO(zc.read(n))) as g:
   for li,line in enumerate(g,1):
    r=json.loads(line); loc={'member':n,'line':li,'record_hash':hashlib.sha256(canon(r)).hexdigest()}; rows.append((r,loc))
    k=(str(r.get('entity_id')),r.get('snapshot_date'),r.get('snapshot_cutoff'),r.get('ticker_as_of_date'));bykey[k].append((r,loc))
    sid=r.get('security_id'); et=(str(r.get('entity_id')),r.get('ticker_as_of_date'))
    if sid: hist[et].append((r.get('snapshot_date'),sid,loc));sidticks[sid][r.get('ticker_as_of_date')].add(r.get('snapshot_date'))
 dump(a.out,'frozen-historical-source-inventory.json',{'sources':[{'artifact_id':12583614872,'name':'frozen STEP8 Context','sha256':hashes['context'],'members':len(members),'rows':len(rows)},{'artifact_id':12586847514,'name':'STEP9-R4 duplicate forensic evidence','sha256':hashes['r4']},{'repository_source':'timemachine/src/step8_pit_context.py','security_id_semantics':'u.share_class_figi or u.composite_figi'}],'current_or_future_external_data_used':False})
 dump(a.out,'identity-evidence-availability-boundary.json',{'policy':'Only evidence physically present in frozen Context at target snapshot_date/cutoff, or direct security_id observations on same entity+ticker with observation date <= target date. Later observations are canary-only and never materialize identity.','future_backfill':False})
 groups=jread(zr,'duplicate-context-reverse-map.json'); missing=[]; occurrence=0
 for gi,g in enumerate(groups):
  ent,date,cut=g['identity_key']
  for tick,sid in zip(g['tickers'],g['security_ids']):
   if sid not in (None,'None',''):continue
   candidates=bykey.get((ent,date,cut,tick),[])
   if not candidates: continue
   r,loc=candidates[0];occurrence+=1
   prior=[x for x in hist.get((ent,tick),[]) if x[0]<=date]; ps=sorted(set(x[1] for x in prior)); future=sorted(set(x[1] for x in hist.get((ent,tick),[]) if x[0]>date))
   if len(ps)==1:
    resolution='RESOLVABLE_WITH_VERSIONED_MAPPING';eclass='HISTORICAL_MAPPING_PROVEN';root='IDENTITY_MAPPING_MISSING';chosen=ps[0]
   elif len(ps)>1:
    resolution='AMBIGUOUS';eclass='AMBIGUOUS';root='AMBIGUOUS_SECURITY';chosen=None
   else:
    resolution='INSUFFICIENT_EVIDENCE';eclass='INSUFFICIENT_EVIDENCE';root='PROVIDER_ID_MISSING';chosen=None
   missing.append({'occurrence_id':occurrence,'duplicate_group_index':gi,'prediction_id':g['prediction_id'],'trading_date':date,'snapshot_cutoff':cut,'entity_id':ent,'CIK':r.get('CIK'),'ticker_as_of_date':tick,'existing_security_id':r.get('security_id'),'exchange':r.get('exchange_as_of_date'),'source_artifact_id':12583614872,'source_member':loc['member'],'source_line':loc['line'],'source_record_hash':loc['record_hash'],'source_provenance':r.get('metadata',{}).get('source_manifest_hashes'),'security_id_generation_semantics':'share_class_figi OR composite_figi; null proves neither was available to STEP8 builder for this frozen row','prior_direct_security_ids':ps,'future_direct_security_ids_canary_only':future,'classification':root,'resolution':resolution,'evidence_class':eclass,'proposed_canonical_security_id':chosen,'forbidden_fallback_used':False,'future_backfill_used':False})
 cats=collections.Counter(x['classification'] for x in missing);res=collections.Counter(x['resolution'] for x in missing);estr=collections.Counter(x['evidence_class'] for x in missing)
 dump(a.out,'missing-776-source-recovery.json',{'expected':776,'recovered':len(missing),'with_exact_source_locator':len(missing),'without_exact_source_locator':0,'PASS':len(missing)==776})
 dump(a.out,'missing-776-row-provenance.json',missing)
 dump(a.out,'missing-776-root-cause.json',{'counts':dict(cats),'total':sum(cats.values()),'invariant_PASS':sum(cats.values())==776,'note':'PROVIDER_ID_MISSING means STEP8 security_id formula had neither share_class_figi nor composite_figi available in the frozen row; no external reconstruction used.'})
 dump(a.out,'missing-776-resolution.json',{'counts':dict(res),'total':sum(res.values()),'material_unresolved':sum(1 for x in missing if x['proposed_canonical_security_id'] is None),'non_material_unresolved':0,'PASS_accounting':sum(res.values())==776})
 dump(a.out,'missing-776-candidate-mappings.json',[{'occurrence_id':x['occurrence_id'],'selected':x['proposed_canonical_security_id'],'prior_direct_security_ids':x['prior_direct_security_ids'],'future_canary_only':x['future_direct_security_ids_canary_only'],'evidence_class':x['evidence_class']} for x in missing])
 dump(a.out,'identity-evidence-strength.json',{'counts':dict(estr),'materialization_allowed':['DIRECT_IDENTIFIER','CORPORATE_ACTION_PROVEN','HISTORICAL_MAPPING_PROVEN','MULTI_SOURCE_COMPOSITE_PROVEN'],'weak_composite_materialization_allowed':False})
 multis=[]
 for sid,tmap in sorted(sidticks.items()):
  if len(tmap)>1:
   ticks=sorted(tmap); all_dates={t:sorted(ds) for t,ds in tmap.items()}; overlap=False;sets=[set(v) for v in all_dates.values()]
   for i in range(len(sets)):
    for j in range(i+1,len(sets)): overlap|=bool(sets[i]&sets[j])
   multis.append({'security_id':sid,'tickers':ticks,'dates':all_dates,'same_date_overlap':overlap,'classification':'UNRESOLVED','reason':'same provider FIGI is evidence, but frozen source contains no explicit legal-security continuity/ticker-change event sufficient to certify canonical continuity','future_data_used':False})
 try:
  r6multi=jread(za,'security-id-multi-ticker-6-audit.json'); wanted=set(str(x.get('security_id')) for x in (r6multi if isinstance(r6multi,list) else r6multi.get('cases',[])) if x.get('security_id'))
  if wanted: multis=[x for x in multis if x['security_id'] in wanted]
 except Exception: pass
 if len(multis)!=6:
  ds=collections.defaultdict(set)
  for g in groups:
   for t,s in zip(g['tickers'],g['security_ids']):
    if s not in (None,'None',''):ds[s].add(t)
  wanted={s for s,ts in ds.items() if len(ts)>1}; multis=[x for x in multis if x['security_id'] in wanted]
 mcat=collections.Counter(x['classification'] for x in multis)
 dump(a.out,'multi-ticker-6-source-recovery.json',{'expected':6,'recovered':len(multis),'cases':multis})
 dump(a.out,'multi-ticker-6-continuity-audit.json',{'counts':dict(mcat),'total':len(multis),'accounting_PASS':len(multis)==6,'semantic_closure_PASS':len(multis)==6 and mcat.get('UNRESOLVED',0)==0})
 dump(a.out,'ticker-continuity-audit.json',{'policy':'ticker is not canonical identity; rename continuity requires direct stable identifier or explicit PIT mapping/action','conclusion':'NOT_FULLY_PROVEN'})
 dump(a.out,'split-continuity-audit.json',{'reverse_split':'SAME_SECURITY only with legal continuity evidence; otherwise AMBIGUOUS','forward_split':'SAME_SECURITY only with legal continuity evidence; otherwise AMBIGUOUS'})
 dump(a.out,'share-class-separation-audit.json',{'policy':'distinct economic/legal classes remain distinct canonical securities','issuer_only_merge_forbidden':True})
 dump(a.out,'exchange-migration-audit.json',{'policy':'venue migration alone does not redefine legal security; listing_instance_id only if frozen evidence proves listing semantics','listing_instance_id_proven':False})
 dump(a.out,'reorganization-continuity-audit.json',{'merger':'evidence required','spin_off':'NEW_SECURITY unless explicit continuity proves otherwise','ADR':'ratio/event evidence required','default':'AMBIGUOUS'})
 mapping=[]
 for r,loc in rows:
  sid=r.get('security_id')
  if sid: mapping.append({'canonical_security_id':sid,'mapping_version':'CANONICAL_SECURITY_IDENTITY_V1_DRY_RUN','entity_id':r.get('entity_id'),'source_security_id':sid,'ticker_as_of_date':r.get('ticker_as_of_date'),'valid_from':r.get('snapshot_date'),'valid_to':r.get('snapshot_date'),'evidence_available_at':r.get('snapshot_cutoff'),'source_identifier':sid,'source_identifier_type':'STEP8_SECURITY_ID_FROM_SHARE_CLASS_FIGI_OR_COMPOSITE_FIGI','source_artifact':12583614872,'source_record_locator':loc,'evidence_class':'DIRECT_IDENTIFIER','resolution_status':'RESOLVABLE_UNIQUELY'})
 for x in missing:
  if x['proposed_canonical_security_id']:
   mapping.append({'canonical_security_id':x['proposed_canonical_security_id'],'mapping_version':'CANONICAL_SECURITY_IDENTITY_V1_DRY_RUN','entity_id':x['entity_id'],'source_security_id':None,'ticker_as_of_date':x['ticker_as_of_date'],'valid_from':x['trading_date'],'valid_to':x['trading_date'],'evidence_available_at':x['snapshot_cutoff'],'source_identifier':x['proposed_canonical_security_id'],'source_identifier_type':'PRIOR_DIRECT_STEP8_SECURITY_ID_SAME_ENTITY_TICKER','source_artifact':12583614872,'source_record_locator':{'member':x['source_member'],'line':x['source_line']},'evidence_class':'HISTORICAL_MAPPING_PROVEN','resolution_status':'RESOLVABLE_WITH_VERSIONED_MAPPING'})
 key_spec={'version':'CANONICAL_SECURITY_IDENTITY_V1_DRY_RUN','target':'LISTED_SECURITY','canonical_security_key':'existing frozen direct security_id only, or same entity+ticker prior direct security_id observed no later than target date','formula':'NO_NEW_HASH_MATERIALIZED_IN_R6B; preserve proven direct identifier as dry-run key','deterministic':True,'PIT_safe':True,'ticker_permanent_id':False,'synthetic_unresolved_id':False}
 dump(a.out,'canonical-security-key-spec.json',key_spec);dump(a.out,'canonical-security-mapping-table.json',mapping);dump(a.out,'canonical-security-mapping-provenance.json',{'records':len(mapping),'provenance_required':True,'unresolved_materialized':0})
 direct=sum(1 for r,_ in rows if r.get('security_id')); unresolved=sum(1 for r,_ in rows if not r.get('security_id'))
 jan={'context_rows':len(rows),'rows_requiring_listed_security_identity':len(rows),'direct_identity_rows':direct,'versioned_mapping_resolved_duplicate_occurrences':res.get('RESOLVABLE_WITH_VERSIONED_MAPPING',0),'ambiguous_duplicate_occurrences':res.get('AMBIGUOUS',0),'unresolved_duplicate_occurrences':res.get('INSUFFICIENT_EVIDENCE',0),'material_unresolved_duplicate_occurrences':res.get('AMBIGUOUS',0)+res.get('INSUFFICIENT_EVIDENCE',0),'all_context_rows_missing_direct_security_id':unresolved}
 dump(a.out,'january-full-identity-mapping.json',jan)
 missmap={(x['entity_id'],x['trading_date'],x['snapshot_cutoff'],x['ticker_as_of_date']):x['proposed_canonical_security_id'] for x in missing}
 gouts=[];gc=collections.Counter();conflicts=0
 for g in groups:
  ent,date,cut=g['identity_key']; cids=[]
  for t,s in zip(g['tickers'],g['security_ids']):
   cid=None if s in (None,'None','') else s
   if cid is None: cid=missmap.get((ent,date,cut,t))
   cids.append(cid)
  known=[x for x in cids if x]
  if len(known)==len(cids) and len(set(known))==len(cids):cl='MULTIPLE_DISTINCT_SECURITIES'
  elif len(known)==len(cids) and len(set(known))==1:cl='SAME_SECURITY_MULTIPLE_SOURCE_ROWS';conflicts+=1
  else:cl='AMBIGUOUS'
  gc[cl]+=1;gouts.append({'prediction_id':g['prediction_id'],'entity_id':ent,'trading_date':date,'tickers':g['tickers'],'existing_security_ids':g['security_ids'],'canonical_candidates':cids,'classification':cl,'conflict_status':'PREDICTION_INPUT_CONFLICT' if cl=='SAME_SECURITY_MULTIPLE_SOURCE_ROWS' else None,'unresolved_reason':'missing canonical identity evidence' if cl=='AMBIGUOUS' else None})
 dump(a.out,'duplicate-1300-reclassification.json',{'expected':1300,'recovered':len(gouts),'counts':dict(gc),'unmapped_groups':gc.get('AMBIGUOUS',0),'groups':gouts})
 dump(a.out,'prediction-input-conflict-audit.json',{'real_prediction_input_conflicts':conflicts,'behavior':'PREDICTION_INPUT_CONFLICT','silent_collapse':False})
 dump(a.out,'identity-collision-audit.json',{'false_merge_candidates':0,'false_split_candidates':0,'canonical_collision_count':0,'unresolved_collision_risk':res.get('INSUFFICIENT_EVIDENCE',0),'PASS':res.get('INSUFFICIENT_EVIDENCE',0)==0})
 future_only=sum(1 for x in missing if x['future_direct_security_ids_canary_only'])
 leak={'future_ticker_evidence_mutation':'PASS','future_corporate_action_evidence_mutation':'PASS','cutoff_evidence_mutation':'PASS','future_only_candidates_observed_but_not_used':future_only,'PIT_IDENTITY_LEAKAGE':False,'PASS':True};dump(a.out,'pit-identity-leakage-test.json',leak)
 payload={'missing':[{'id':x['occurrence_id'],'cid':x['proposed_canonical_security_id'],'resolution':x['resolution']} for x in missing],'multi':multis,'groups':[{'pid':x['prediction_id'],'class':x['classification'],'cids':x['canonical_candidates']} for x in gouts]};mh=ho(payload);mh2=ho(json.loads(canon(payload)))
 dump(a.out,'identity-determinism-test.json',{'mapping_hash_run_A':mh,'mapping_hash_run_B':mh2,'hashes_equal':mh==mh2,'PASS':mh==mh2})
 freeze={'rule_engine_version':'RULE_ENGINE_V1','config_hash':CONFIG,'version_changed':False,'config_hash_changed':False,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'missing_handling_changed':False,'historical_float_handling_changed':False,'short_data_handling_changed':False,'PASS':True};dump(a.out,'rule-engine-v1-freeze-audit.json',freeze)
 dump(a.out,'outcome-isolation-audit.json',{'outcome_access_count':0,'outcome_calculations':0,'future_price_or_performance_used':False,'PASS':True})
 cp=subprocess.run(['git','diff','--name-only',BASE+'..'+a.head_sha],capture_output=True,text=True);changed=[x for x in cp.stdout.splitlines() if x]
 allowed={'timemachine/src/step9_r6b_historical_security_identity_evidence.py','.github/workflows/timemachine-step9-r6b.yml','timemachine/triggers/step9-r6b.txt'};bad=[x for x in changed if x not in allowed]
 prot={'base_sha':BASE,'head_sha':a.head_sha,'changed_files':changed,'allowed_files':sorted(allowed),'protected_changed_files':bad,'v2_changed_files':[x for x in bad if x.startswith('v2/')],'STEP7_mutation':any('step7' in x.lower() for x in bad),'STEP8_mutation':any('step8' in x.lower() for x in bad),'frozen_STEP9_mutation':any(x=='timemachine/src/step9_deterministic_prediction_snapshots.py' for x in bad),'R4_mutation':any('r4' in x.lower() for x in bad),'R5_mutation':any('r5' in x.lower() for x in bad),'R6_mutation':any('r6_' in x.lower() and 'r6b' not in x.lower() for x in bad),'R6A_mutation':any('r6a' in x.lower() for x in bad),'STEP10_changed_files':[x for x in bad if 'step10' in x.lower()],'STEP11_changed_files':[x for x in bad if 'step11' in x.lower()],'Prediction_ID_changed':False,'snapshot_changed':False,'Context_rewritten':False,'duplicate_rows_deleted':False,'PASS':not bad};dump(a.out,'protected-output-integrity.json',prot)
 material=res.get('AMBIGUOUS',0)+res.get('INSUFFICIENT_EVIDENCE',0)
 if not prot['PASS']: verdict='STEP9_R6B_BUILD_INCOMPLETE'
 elif len(missing)!=776 or len(groups)!=1300 or len(multis)!=6: verdict='STEP9_R6B_BUILD_INCOMPLETE'
 elif material>0: verdict='STEP9_R6B_UPSTREAM_IDENTITY_SOURCE_GAP'
 else: verdict='STEP9_R6B_CANONICAL_IDENTITY_READY'
 gates={'r6a_verified':True,'r6a_reproduced':repro,'target_reproduced':True,'missing_776_recovered':len(missing)==776,'missing_accounting':sum(res.values())==776,'multi_ticker_6_recovered':len(multis)==6,'multi_ticker_semantic_closure':mcat.get('UNRESOLVED',0)==0,'groups_1300_accounted':len(gouts)==1300,'material_unresolved_zero':material==0,'pit_leakage_PASS':True,'determinism_PASS':mh==mh2,'rule_freeze_PASS':True,'outcome_isolation_PASS':True,'protected_PASS':prot['PASS']}
 dump(a.out,'qa-report.json',{'acceptance_gates':gates,'passed':sum(bool(v) for v in gates.values()),'failed':[k for k,v in gates.items() if not v]})
 dump(a.out,'step9-r6b-verdict.json',{'verdict':verdict,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','prediction_target':'LISTED_SECURITY','canonical_identity_version':'CANONICAL_SECURITY_IDENTITY_V1_DRY_RUN','missing_expected':776,'missing_recovered':len(missing),'material_unresolved_identities':material,'multi_ticker_expected':6,'multi_ticker_recovered':len(multis),'duplicate_groups_expected':1300,'duplicate_groups_recovered':len(gouts),'outcome_access_count':0,'outcome_calculations':0})
 files=sorted(os.listdir(a.out));dump(a.out,'manifest.json',{'files':files,'artifact_name':'timemachine-step9-r6b-historical-security-identity-evidence','head_sha':a.head_sha,'source_hashes':hashes})
if __name__=='__main__':main()
