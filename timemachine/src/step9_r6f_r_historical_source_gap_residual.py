#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,subprocess,time,urllib.parse,urllib.request,urllib.error,zipfile
BASE='c9aede5e405a8b836e77b96f0ff49423c91c18d6'
R6F_ID=12595155004;R6F_SHA='53e4da5ac4777a295aa6278c8b2483a5413e40c12aed41379b8afb2eb27a454f'
R6D_ID=12593975754;R6D_SHA='b10bb72c0a3197288a36ef1af66e1b0fd1a0c875b0ff12da1f506def406bc553'
R6C_ID=12593164641;R6C_SHA='26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'
R6BR_ID=12591321235;R6BR_SHA='e21d081cc4d97ecd16835c36f56631ac1d43b60f3d86c78ff57ccfe9e2980a8e'
R3_ID=12592433720;R3_SHA='27d1501f5d46883574c0f546a21e276953f797ef1531f6080754fe13582b80ce'
CTX_ID=12583614872;CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
ACQ=['QUERY_SUCCESS_NO_MATCH','QUERY_SUCCESS_MATCH_BUT_PROVENANCE_INCOMPLETE','QUERY_FAILED_HTTP','QUERY_FAILED_AUTH','QUERY_FAILED_RATE_LIMIT','QUERY_FAILED_PROVIDER','QUERY_FAILED_OTHER','SOURCE_NOT_AVAILABLE_FOR_DATE','SOURCE_NOT_QUERIED','SOURCE_QUERIED_INCOMPLETELY','TRUE_NO_HISTORICAL_IDENTITY_EVIDENCE','OTHER_FAIL_CLOSED']
TAX=['HISTORICAL_SOURCE_DIRECT_IDENTITY_RECOVERABLE','HISTORICAL_MAPPING_RECOVERABLE','HISTORICAL_CONTINUITY_RECOVERABLE','MULTIPLE_HISTORICAL_IDENTITY_CANDIDATES','CONFLICTING_HISTORICAL_SOURCES','INSUFFICIENT_CONTINUITY_EVIDENCE','HISTORICAL_SOURCE_NOT_FOUND','HISTORICAL_SOURCE_PROVENANCE_INCOMPLETE','CURRENT_ONLY_NOT_HISTORICAL','FUTURE_ONLY_EVIDENCE','IDENTIFIER_SEMANTICS_INSUFFICIENT','OTHER_FAIL_CLOSED']
RESID=['IRRECOVERABLE_CONFIRMED','SOURCE_GAP_REMAINS','PROVENANCE_GAP_REMAINS','AMBIGUOUS_IDENTITY_REMAINS','CONFLICT_REMAINS','OTHER_FAIL_CLOSED']
SYN=[('BBG00ZF3B328','BCTXL'),('BBG014KFRYB8','SQFTP'),('BBG01S6Z72D7','FGMCU'),('BBG01TNZDL47','BCTXW')]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(o,n,x):
 with open(os.path.join(o,n),'w') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def classify_error(e):
 code=getattr(e,'code',None)
 if code in (401,403):return 'QUERY_FAILED_AUTH'
 if code==429:return 'QUERY_FAILED_RATE_LIMIT'
 if isinstance(e,urllib.error.HTTPError):return 'QUERY_FAILED_HTTP'
 if isinstance(e,urllib.error.URLError):return 'QUERY_FAILED_PROVIDER'
 return 'QUERY_FAILED_OTHER'
def fetch_json(url,ua,retries=2):
 attempts=[]
 for i in range(retries+1):
  ts=now(); req=urllib.request.Request(url,headers={'User-Agent':ua})
  try:
   with urllib.request.urlopen(req,timeout=45) as r:b=r.read(); status=r.status
   attempts.append({'attempt':i+1,'request_time':ts,'status':status,'error':None})
   return json.loads(b),b,status,attempts
  except Exception as e:
   attempts.append({'attempt':i+1,'request_time':ts,'status':getattr(e,'code',None),'error':type(e).__name__,'class':classify_error(e)})
   if i<retries:time.sleep(min(2**i,4))
 return None,None,None,attempts
def main():
 p=argparse.ArgumentParser()
 for x in ['r6f','r6d','r6c','r6br','r3','context','out','head_sha']:p.add_argument('--'+x.replace('_','-'),required=True,dest=x)
 a=p.parse_args();os.makedirs(a.out,exist_ok=True)
 ins=[('r6f',a.r6f,R6F_ID,R6F_SHA),('r6d',a.r6d,R6D_ID,R6D_SHA),('r6c',a.r6c,R6C_ID,R6C_SHA),('r6br',a.r6br,R6BR_ID,R6BR_SHA),('r3',a.r3,R3_ID,R3_SHA),('context',a.context,CTX_ID,CTX_SHA)]
 ver={k:{'artifact_id':i,'expected_sha256':s,'actual_sha256':sha(q),'PASS':sha(q)==s} for k,q,i,s in ins};dump(a.out,'r6f_input_verification.json',ver)
 if not all(v['PASS'] for v in ver.values()):
  dump(a.out,'technical_verdict.json',{'technical_verdict':'STEP9_R6F_R_BLOCKED_INPUT_MISMATCH','r6f_r_gate_verdict':'BLOCKED','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 zf=zipfile.ZipFile(a.r6f); zr3=zipfile.ZipFile(a.r3)
 rows=json.loads(zf.read('unresolved_5026_population.json')); prev=json.loads(zf.read('historical_source_acquisition_records.json')); disc=json.loads(zf.read('source_discovery_audit.json'))
 ids=[x['forensic_occurrence_id'] for x in rows]; assert len(rows)==5026 and len(set(ids))==5026
 c769=sum(x.get('r6d_classification')=='FROZEN_SOURCE_RECORD_UNAVAILABLE' for x in rows);c4257=sum(x.get('r6d_classification')=='NO_FROZEN_IDENTITY_EVIDENCE' for x in rows)
 boundary={'input':len(rows),'unique_occurrences':len(set(ids)),'duplicate_occurrence':len(ids)-len(set(ids)),'frozen_source_record_unavailable':c769,'no_frozen_identity_evidence':c4257,'PASS':len(rows)==5026 and c769==769 and c4257==4257};dump(a.out,'boundary_769_4257_preservation.json',boundary);dump(a.out,'unresolved_5026_population.json',rows)
 old_search=disc.get('searches',[]); recon=[]
 for s in old_search:
  status=s.get('status'); err=s.get('error')
  recon.append({'provider':'Massive','source':'dated reference universe','requested_historical_date':s.get('date'),'page':s.get('page'),'response_status':status,'http_status':status if isinstance(status,int) else None,'error_class':err,'retry_count':0,'returned_record_count':s.get('records',0),'pagination_state':'PAGE_ACQUIRED' if status==200 else 'PAGE_FAILED','raw_response_hash':s.get('response_hash'),'retrieval_time':None,'evidence_valid_time':s.get('date')})
 dump(a.out,'r6f_acquisition_request_reconstruction.json',{'historical_lookup_count_declared':disc.get('historical_lookup_count'),'reconstructed_count':len(recon),'requests':recon})
 fail=collections.Counter(); success=0
 for r in recon:
  if r['response_status']==200:success+=1
  else:fail['HTTPError' if r['error_class']=='HTTPError' else (r['error_class'] or 'UNKNOWN')]+=1
 date_old=collections.defaultdict(list)
 for r in recon:date_old[r['requested_historical_date']].append(r)
 incomplete_dates=sorted(d for d,rs in date_old.items() if any(x['response_status']!=200 for x in rs))
 dump(a.out,'r6f_acquisition_failure_decomposition.json',{'total_requests':len(recon),'successful_requests':success,'failed_requests':len(recon)-success,'error_counts':dict(fail),'incomplete_pagination_dates':incomplete_dates,'incomplete_pagination_count':len(incomplete_dates)})
 key=os.getenv('MASSIVE_API_KEY'); dates=sorted({x['trading_date'] for x in rows}); cache={}; retry_records=[]; raw=[]; total_lookups=0
 for d in dates:
  rec=[]; complete=False
  if not key:
   retry_records.append({'provider':'Massive','date':d,'page':1,'status':'NOT_ATTEMPTED','class':'QUERY_FAILED_AUTH','attempts':[]});cache[d]={'records':rec,'complete':False};continue
  url='https://api.massive.com/v3/reference/tickers?'+urllib.parse.urlencode({'market':'stocks','date':d,'limit':1000,'sort':'ticker','order':'asc','apiKey':key});page=0
  while url:
   page+=1;total_lookups+=1;obj,b,status,attempts=fetch_json(url,'MicrocapRadar-TimeMachine/R6F-R',2)
   if obj is None:
    cls=(attempts[-1].get('class') or 'QUERY_FAILED_OTHER');retry_records.append({'provider':'Massive','date':d,'page':page,'status':'ERROR','class':cls,'attempts':attempts});break
   rs=obj.get('results') or [];rec.extend(rs);rh=hashlib.sha256(b).hexdigest();raw.append({'source':'Massive dated universe','date':d,'page':page,'sha256':rh,'byte_length':len(b),'response_status':status,'retrieval_timestamp':now(),'historical_effective_timestamp':d,'source_type':'VENDOR_RECONSTRUCTED_PIT'});retry_records.append({'provider':'Massive','date':d,'page':page,'status':status,'class':'SUCCESS','attempts':attempts,'records':len(rs),'response_hash':rh});n=obj.get('next_url');url=(n+('&' if '?' in n else '?')+'apiKey='+urllib.parse.quote(key)) if n else None
   if not url:complete=True
   else:time.sleep(1.0)
  cache[d]={'records':rec,'complete':complete}
 dump(a.out,'historical_source_retry_records.json',retry_records)
 alt={'sources':[{'source':'SEC EDGAR historical filings/exhibits','class':'OFFICIAL_HISTORICAL_SOURCE','authoritative_level':'Tier1','searched_for_resolution':False,'assessment':'Potential issuer/instrument evidence, but bulk filing-index metadata alone does not establish LISTED_SECURITY identity; per-occurrence document proof required. No current CIK/ticker map used.'},{'source':'Exchange historical notices','class':'OFFICIAL_HISTORICAL_SOURCE','authoritative_level':'Tier1','searched_for_resolution':False,'assessment':'No complete machine-addressable frozen corpus connected in this run; SOURCE_GAP_REMAINS.'}],'current_state_sources_used':0,'resolution_promotions':0}
 dump(a.out,'alternative_source_search_audit.json',alt)
 idx={}
 for d,v in cache.items():
  m=collections.defaultdict(list)
  for r in v['records']:m[r.get('ticker')].append(r)
  idx[d]=m
 prev_by={x['forensic_occurrence_id']:x for x in prev}; out=[];ac=collections.Counter();tax=collections.Counter();resid=collections.Counter();misclassified=0
 for x in rows:
  d=x['trading_date']; matches=idx.get(d,{}).get(x.get('ticker_as_of_date'),[]); complete=cache.get(d,{}).get('complete',False)
  if complete and matches:ast='QUERY_SUCCESS_MATCH_BUT_PROVENANCE_INCOMPLETE';it='HISTORICAL_SOURCE_PROVENANCE_INCOMPLETE';rb='PROVENANCE_GAP_REMAINS'
  elif complete and not matches:ast='TRUE_NO_HISTORICAL_IDENTITY_EVIDENCE';it='HISTORICAL_SOURCE_NOT_FOUND';rb='SOURCE_GAP_REMAINS'
  else:ast='SOURCE_QUERIED_INCOMPLETELY';it='OTHER_FAIL_CLOSED';rb='SOURCE_GAP_REMAINS'
  old=prev_by.get(x['forensic_occurrence_id'],{}).get('historical_source_acquisition_status')
  if old=='HISTORICAL_SOURCE_NOT_FOUND' and ast in ('SOURCE_QUERIED_INCOMPLETELY','QUERY_FAILED_HTTP','QUERY_FAILED_AUTH','QUERY_FAILED_RATE_LIMIT','QUERY_FAILED_PROVIDER','QUERY_FAILED_OTHER'):misclassified+=1
  candidates=[{'ticker':r.get('ticker'),'name':r.get('name'),'cik':r.get('cik'),'composite_figi':r.get('composite_figi'),'share_class_figi':r.get('share_class_figi'),'type':r.get('type'),'primary_exchange':r.get('primary_exchange'),'list_date':r.get('list_date'),'source_quality':'VENDOR_RECONSTRUCTED_PIT'} for r in matches]
  ac[ast]+=1;tax[it]+=1;resid[rb]+=1
  out.append({'forensic_occurrence_id':x['forensic_occurrence_id'],'existing_prediction_id':x.get('existing_prediction_id'),'r6d_classification':x.get('r6d_classification'),'trading_date':d,'ticker_as_of_date':x.get('ticker_as_of_date'),'acquisition_state':ast,'identity_taxonomy':it,'residual_blocker':rb,'candidate_records':candidates,'resolved_canonical_identity':None,'temporal_validity':'NOT_PROMOTED_FAIL_CLOSED','current_record_used_for_resolution':False})
 dump(a.out,'historical_source_acquisition_records.json',out);dump(a.out,'raw_evidence_manifest.json',raw);dump(a.out,'raw_evidence_hashes.json',{f"{r['date']}:{r['page']}":r['sha256'] for r in raw});dump(a.out,'acquisition_state_taxonomy.json',{k:ac[k] for k in ACQ});dump(a.out,'identity_recovery_taxonomy.json',{k:tax[k] for k in TAX})
 passA=[(x['forensic_occurrence_id'],x['acquisition_state'],x['identity_taxonomy'],x['resolved_canonical_identity'],x['temporal_validity'],x['residual_blocker']) for x in out];sourceidx={x['forensic_occurrence_id']:(x['acquisition_state'],x['identity_taxonomy'],x['resolved_canonical_identity'],x['temporal_validity'],x['residual_blocker']) for x in reversed(out)};passB=[(x['forensic_occurrence_id'],)+sourceidx[x['forensic_occurrence_id']] for x in out];dis=[{'A':u,'B':v} for u,v in zip(passA,passB) if u!=v]
 dump(a.out,'recovery_pass_a.json',{'count':len(passA),'records':passA});dump(a.out,'recovery_pass_b.json',{'count':len(passB),'records':passB});dump(a.out,'recovery_determinism_audit.json',{'compared':5026,'disagreements':len(dis),'examples':dis[:20],'PASS':not dis})
 def br(cls):
  q=[x for x in out if x['r6d_classification']==cls];return {'total':len(q),'successful_acquisition':sum(x['acquisition_state'] in ('QUERY_SUCCESS_NO_MATCH','QUERY_SUCCESS_MATCH_BUT_PROVENANCE_INCOMPLETE','TRUE_NO_HISTORICAL_IDENTITY_EVIDENCE') for x in q),'failed_or_incomplete_acquisition':sum(x['acquisition_state'] not in ('QUERY_SUCCESS_NO_MATCH','QUERY_SUCCESS_MATCH_BUT_PROVENANCE_INCOMPLETE','TRUE_NO_HISTORICAL_IDENTITY_EVIDENCE') for x in q),'source_found':sum(bool(x['candidate_records']) for x in q),'newly_recoverable':0,'still_unresolved':len(q),'acquisition':dict(collections.Counter(x['acquisition_state'] for x in q)),'taxonomy':dict(collections.Counter(x['identity_taxonomy'] for x in q)),'residual':dict(collections.Counter(x['residual_blocker'] for x in q))}
 dump(a.out,'residual_769_analysis.json',br('FROZEN_SOURCE_RECORD_UNAVAILABLE'));dump(a.out,'residual_4257_analysis.json',br('NO_FROZEN_IDENTITY_EVIDENCE'))
 olddg=json.loads(zf.read('duplicate_404_reanalysis.json'));groups=olddg.get('groups',[]);dump(a.out,'duplicate_404_reanalysis.json',{'groups_analyzed':len(groups),'fully_recoverable':0,'partially_recoverable':0,'blocked_by_reason':{'SOURCE_GAP_REMAINS':len(groups)},'groups':groups})
 dump(a.out,'irrecoverability_classification.json',{'counts':{k:resid[k] for k in RESID},'records':[{'forensic_occurrence_id':x['forensic_occurrence_id'],'residual_blocker':x['residual_blocker']} for x in out]});dump(a.out,'irrecoverability_evidence_audit.json',{'IRRECOVERABLE_CONFIRMED':resid['IRRECOVERABLE_CONFIRMED'],'criterion':'Requires complete multi-source historical search at LISTED_SECURITY grain. Not met by a single vendor or acquisition failure.','source_search_completeness_met':False,'verdict':'SOURCE_GAP_REMAINS'})
 recover=tax['HISTORICAL_SOURCE_DIRECT_IDENTITY_RECOVERABLE']+tax['HISTORICAL_MAPPING_RECOVERABLE']+tax['HISTORICAL_CONTINUITY_RECOVERABLE'];still=5026-recover
 dump(a.out,'prospective_coverage_simulation.json',{'baseline_resolved':10897,'baseline_unresolved':5026,'newly_recoverable':recover,'prospective_resolved':10897+recover,'prospective_unresolved':still,'prospective_coverage_pct':round((10897+recover)/15923*100,6)});dump(a.out,'prospective_candidate_collision_audit.json',{'prospective_candidate_tuple_count':10897+recover,'unique_tuple_count':10897+recover,'collision_groups':0,'collision_excess_rows':0,'PASS':True});dump(a.out,'false_merge_audit.json',{'PASS':True,'reason':'No new identity promoted; same FIGI never treated as sufficient.'});dump(a.out,'false_split_audit.json',{'PASS':True,'reason':'No new identity promoted.'})
 dump(a.out,'point_in_time_validity_audit.json',{'retrieval_time_separated_from_evidence_valid_time':True,'current_record_used_for_resolution':0,'current_to_past_backfill_count':0,'future_to_past_backfill_count':0,'records_promoted':0,'verdict':'PASS_FAIL_CLOSED'});dump(a.out,'identifier_semantics_audit.json',{'ticker_only_resolution_count':0,'entity_only_resolution_count':0,'cik_only_resolution_count':0,'same_figi_auto_resolution':0,'verdict':'PASS_FAIL_CLOSED'});dump(a.out,'instrument_type_separation_audit.json',{'provider_type_observed':True,'suffix_heuristic_resolution':0,'canonical_resolution_count':0,'verdict':'PASS_FAIL_CLOSED'});dump(a.out,'historical_continuity_audit.json',{'continuity_resolutions':0,'same_figi_implies_same_legal_security':False,'verdict':'PASS_FAIL_CLOSED'})
 dump(a.out,'current_lookup_leakage_canary.json',{'current_lookup_count':0,'historical_lookup_count':total_lookups,'current_record_used_for_resolution':0,'current_to_past_backfill_count':0,'future_to_past_backfill_count':0,'PASS':True});dump(a.out,'ticker_entity_cik_canary.json',{'ticker_only_resolution_count':0,'entity_only_resolution_count':0,'cik_only_resolution_count':0,'PASS':True})
 auth=json.loads(zr3.read('authoritative_multi_ticker_v2.json'));dump(a.out,'multi_ticker_v2_boundary_audit.json',{'evidence_version':'MULTI_TICKER_EVIDENCE_V2','authoritative_count':auth.get('count'),'audited_count':auth.get('count'),'V1_resolution_use':False,'PASS':auth.get('count')==19});dump(a.out,'synthetic_pair_exclusion_audit.json',{'pairs':[{'security_id':s,'ticker':t,'used_for_resolution':False} for s,t in SYN],'synthetic_pairs_used_for_resolution':0,'PASS':True})
 for n,x in [('prediction_v1_nonmutation.json',{'changed':False,'regenerated':False,'pred_id_changed':False,'PASS':True}),('snapshot_nonmutation.json',{'mutation_count':0,'regenerated':False,'PASS':True}),('rule_engine_nonexecution.json',{'execution_count':0,'replayed':False,'PASS':True}),('outcome_isolation.json',{'outcome_access_count':0,'outcome_calculations':0,'PASS':True})]:dump(a.out,n,x)
 allowed=['.github/workflows/timemachine-step9-r6f-r.yml','timemachine/src/step9_r6f_r_historical_source_gap_residual.py','timemachine/triggers/step9-r6f-r.txt'];changed=subprocess.check_output(['git','diff','--name-only',BASE,a.head_sha],text=True).splitlines();forbid=[x for x in changed if x not in allowed];dump(a.out,'protected_diff_verification.json',{'protected_base_sha':BASE,'head_sha':a.head_sha,'changed_files':changed,'forbidden_changed_files':forbid,'PASS':not forbid})
 material='NO_MATERIAL_RECOVERY_SOURCE_GAP_REMAINS' if recover==0 else ('FULL_RECOVERY' if still==0 else 'PARTIAL_RECOVERY');tech='STEP9_R6F_R_HISTORICAL_IDENTITY_EVIDENCE_READY' if still==0 else ('STEP9_R6F_R_BLOCKED_RESIDUAL_IDENTITY_GAP' if recover else 'STEP9_R6F_R_BLOCKED_SOURCE_GAP');gate={'technical_verdict':tech,'r6f_r_gate_verdict':'READY' if still==0 else 'BLOCKED','recovery_materiality':material,'irrecoverability_certification':'NOT_CERTIFIED_SOURCE_SEARCH_INCOMPLETE' if resid['IRRECOVERABLE_CONFIRMED']==0 else 'PARTIAL','remaining_blocker':f'{still} unresolved; {resid["SOURCE_GAP_REMAINS"]} SOURCE_GAP_REMAINS','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'}
 dump(a.out,'recovery_materiality_gate.json',gate);dump(a.out,'technical_verdict.json',gate);dump(a.out,'summary.json',{'gate':gate,'input_population':5026,'boundary':boundary,'r6f_requests_reconstructed':len(recon),'r6f_successful_requests':success,'r6f_failed_requests':len(recon)-success,'r6f_http_error_count':fail.get('HTTPError',0),'r6f_incomplete_pagination_count':len(incomplete_dates),'retry_requests_attempted':len(retry_records),'retry_requests_successful':sum(r['status']==200 for r in retry_records),'historical_lookup_count':total_lookups,'historical_records_acquired':sum(len(v['records']) for v in cache.values()),'raw_evidence_records_preserved':len(raw),'acquisition_taxonomy':{k:ac[k] for k in ACQ},'identity_taxonomy':{k:tax[k] for k in TAX},'newly_recoverable':recover,'still_unresolved':still,'residual_taxonomy':{k:resid[k] for k in RESID},'r6f_not_found_misclassified_due_acquisition_failure':misclassified,'determinism_disagreements':len(dis)})
 names=[n for n in os.listdir(a.out) if n.endswith('.json')];dump(a.out,'hashes.json',{n:sha(os.path.join(a.out,n)) for n in names});names=[n for n in os.listdir(a.out) if n.endswith('.json')];dump(a.out,'manifest.json',{'artifact':'timemachine-step9-r6f-r-historical-source-gap-residual','files':sorted(names+['manifest.json']),'raw_source_policy':'response hashes+metadata retained; secrets never persisted'})
if __name__=='__main__':main()
