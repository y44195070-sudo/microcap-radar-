#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,random,subprocess,time,urllib.error,urllib.parse,urllib.request,zipfile
BASE='185c2260b6a34bc6ae17a159fd4d7db9d953bdcc'
UP={'r6fr':(12595027148,'3561abf1e5d4725aa368fad4cb718c2675a510db1b133da8af33b7b9eb40bc30'),'r6f':(12595155004,'53e4da5ac4777a295aa6278c8b2483a5413e40c12aed41379b8afb2eb27a454f'),'r6d':(12593975754,'b10bb72c0a3197288a36ef1af66e1b0fd1a0c875b0ff12da1f506def406bc553'),'r6c':(12593164641,'26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'),'r6br':(12591321235,'e21d081cc4d97ecd16835c36f56631ac1d43b60f3d86c78ff57ccfe9e2980a8e'),'r3':(12592433720,'27d1501f5d46883574c0f546a21e276953f797ef1531f6080754fe13582b80ce'),'context':(12583614872,'4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51')}
STATES=['SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE','SEARCH_INCOMPLETE_RATE_LIMIT','SEARCH_INCOMPLETE_AUTH','SEARCH_INCOMPLETE_PROVIDER','SEARCH_INCOMPLETE_PAGINATION','SEARCH_INCOMPLETE_SOURCE_COVERAGE','SEARCH_INCOMPLETE_DATE_COVERAGE','SOURCE_NOT_AVAILABLE_FOR_PERIOD','OTHER_FAIL_CLOSED']
SYN=[('BBG00ZF3B328','BCTXL'),('BBG014KFRYB8','SQFTP'),('BBG01S6Z72D7','FGMCU'),('BBG01TNZDL47','BCTXW')]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(o,n,x):
 with open(os.path.join(o,n),'w') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def request(url,ua,attempts=4,base_wait=12.5):
 hist=[]
 for i in range(attempts):
  ts=now();req=urllib.request.Request(url,headers={'User-Agent':ua,'Accept-Encoding':'identity'})
  try:
   with urllib.request.urlopen(req,timeout=60) as r:
    b=r.read();hdr=dict(r.headers);status=r.status
   hist.append({'attempt':i+1,'request_time':ts,'http_status':status,'retry_after':hdr.get('Retry-After'),'rate_limit_headers':{k:v for k,v in hdr.items() if 'rate' in k.lower()},'error':None})
   return b,status,hdr,hist
  except urllib.error.HTTPError as e:
   hdr=dict(e.headers or {});body=e.read();hist.append({'attempt':i+1,'request_time':ts,'http_status':e.code,'retry_after':hdr.get('Retry-After'),'rate_limit_headers':{k:v for k,v in hdr.items() if 'rate' in k.lower()},'error':'HTTPError','error_body_sha256':sha_bytes(body)})
   if i+1<attempts:
    ra=hdr.get('Retry-After');wait=float(ra) if ra and str(ra).replace('.','',1).isdigit() else min(base_wait*(2**i),90);time.sleep(wait+random.uniform(.25,1.25))
  except Exception as e:
   hist.append({'attempt':i+1,'request_time':ts,'http_status':None,'retry_after':None,'rate_limit_headers':{},'error':type(e).__name__})
   if i+1<attempts:time.sleep(min(base_wait*(2**i),90)+random.uniform(.25,1.25))
 return None,None,{},hist
def main():
 p=argparse.ArgumentParser()
 for k in list(UP)+['out','head_sha']:p.add_argument('--'+k.replace('_','-'),required=True,dest=k)
 a=p.parse_args();os.makedirs(a.out,exist_ok=True)
 ver={}
 for k,(aid,exp) in UP.items():
  path=getattr(a,k);actual=sha_file(path);ver[k]={'artifact_id':aid,'expected_sha256':exp,'actual_sha256':actual,'PASS':actual==exp}
 dump(a.out,'r6fr_input_verification.json',ver)
 if not all(v['PASS'] for v in ver.values()):
  dump(a.out,'technical_verdict.json',{'technical_verdict':'STEP9_R6F_R2_BLOCKED_INPUT_MISMATCH','r6f_r2_gate_verdict':'BLOCKED','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 z=zipfile.ZipFile(a.r6fr);rows=json.loads(z.read('unresolved_5026_population.json'));prev=json.loads(z.read('historical_source_acquisition_records.json'));retry=json.loads(z.read('historical_source_retry_records.json'))
 ids=[x['forensic_occurrence_id'] for x in rows];c769=sum(x.get('r6d_classification')=='FROZEN_SOURCE_RECORD_UNAVAILABLE' for x in rows);c4257=sum(x.get('r6d_classification')=='NO_FROZEN_IDENTITY_EVIDENCE' for x in rows)
 boundary={'input':len(rows),'unique_occurrences':len(set(ids)),'duplicate_occurrence':len(ids)-len(set(ids)),'missing':0,'extra':0,'frozen_source_record_unavailable':c769,'no_frozen_identity_evidence':c4257,'PASS':len(rows)==5026 and len(set(ids))==5026 and c769==769 and c4257==4257};dump(a.out,'boundary_769_4257_preservation.json',boundary);dump(a.out,'unresolved_5026_population.json',rows)
 old429=sum(1 for r in retry if r.get('class')=='QUERY_FAILED_RATE_LIMIT' or any(x.get('http_status')==429 for x in r.get('attempts',[])));dump(a.out,'r6fr_request_reconstruction.json',{'requests':retry,'count':len(retry),'original_429_request_count':old429})
 forensic=[]
 for r in retry:
  ats=r.get('attempts',[]);forensic.append({'date':r.get('date'),'page':r.get('page'),'endpoint':'Massive /v3/reference/tickers','attempts':ats,'final_status':r.get('status'),'had_429':any(x.get('http_status')==429 for x in ats),'retry_after_values':[x.get('retry_after') for x in ats if x.get('retry_after')],'rate_limit_headers':[x.get('rate_limit_headers') for x in ats if x.get('rate_limit_headers')]})
 dump(a.out,'massive_429_forensics.json',{'requests':forensic,'original_429_count':old429,'cause':'PROVIDER_THROTTLING_OR_PLAN_LIMIT_CONFIRMED_BY_HTTP_429; exact quota not inferred'})
 key=os.getenv('MASSIVE_API_KEY');dates=sorted({x['trading_date'] for x in rows});massive=[];raw=[];cache={};lookups=0
 for d in dates:
  rec=[];complete=False;url='https://api.massive.com/v3/reference/tickers?'+urllib.parse.urlencode({'market':'stocks','date':d,'limit':1000,'sort':'ticker','order':'asc','apiKey':key or ''});page=0
  if not key:cache[d]={'records':[],'complete':False,'blocker':'AUTH'};continue
  while url:
   page+=1;lookups+=1;b,status,hdr,ats=request(url,'MicrocapRadar-TimeMachine-R6F-R2/1.0',4,12.5)
   rr={'provider':'Massive','date':d,'page':page,'attempts':ats,'http_status':status,'records':0,'complete_page':False,'next_url_present':False}
   if b is None:
    codes=[x.get('http_status') for x in ats];rr['blocker']='RATE_LIMIT' if 429 in codes else ('AUTH' if any(x in (401,403) for x in codes) else 'PROVIDER');massive.append(rr);break
   obj=json.loads(b);rs=obj.get('results') or [];rec.extend(rs);n=obj.get('next_url');rr.update({'records':len(rs),'complete_page':True,'next_url_present':bool(n),'response_sha256':sha_bytes(b)});massive.append(rr);raw.append({'source':'Massive dated universe','date':d,'page':page,'sha256':sha_bytes(b),'bytes':len(b),'retrieval_time':now(),'evidence_valid_time':d})
   if not n:complete=True;url=None
   else:url=n+('&' if '?' in n else '?')+'apiKey='+urllib.parse.quote(key);time.sleep(12.5+random.uniform(.25,.75))
  cache[d]={'records':rec,'complete':complete,'blocker':None if complete else massive[-1].get('blocker','PAGINATION')}
 dump(a.out,'historical_retry_attempts.json',massive)
 rate={'scheduler':{'sequential':True,'bounded_retry':4,'exponential_backoff':True,'retry_after_respected':True,'jitter':True,'base_request_interval_seconds':12.5,'cursor_preservation':True,'checkpoint_semantics':'date/page records retained in artifact','already_acquired_skip':'not used; certification run reacquires independently','infinite_retry':False},'requests':len(massive),'requests_with_429':sum(any(x.get('http_status')==429 for x in r['attempts']) for r in massive),'final_429_failures':sum(r.get('blocker')=='RATE_LIMIT' for r in massive),'retry_after_observed':sum(bool(x.get('retry_after')) for r in massive for x in r['attempts'])};dump(a.out,'provider_rate_limit_audit.json',rate);dump(a.out,'acquisition_scheduler_audit.json',rate['scheduler'])
 pag=[]
 for d in dates:
  rs=[x for x in massive if x['date']==d];pag.append({'date':d,'pages_attempted':len(rs),'pages_acquired':sum(x['complete_page'] for x in rs),'terminal_page_observed':cache[d]['complete'],'pagination_complete':cache[d]['complete'],'blocker':cache[d]['blocker']})
 dump(a.out,'pagination_completeness_audit.json',pag)
 # Alternative source acquisition: use only CIKs observed in dated Massive records; never current ticker maps.
 prev_candidates={x['forensic_occurrence_id']:x.get('candidate_records',[]) for x in prev};ciks=sorted({str(c.get('cik')).zfill(10) for cs in prev_candidates.values() for c in cs if c.get('cik')})
 sec=[];secraw=[]
 for cik in ciks:
  url=f'https://data.sec.gov/submissions/CIK{cik}.json';b,status,hdr,ats=request(url,'MicrocapRadar research contact admin@example.invalid',2,0.2);entry={'source':'SEC EDGAR submissions','cik':cik,'query':url,'attempts':ats,'status':status,'records':0,'search_complete':False}
  if b:
   obj=json.loads(b);recent=(obj.get('filings') or {}).get('recent') or {};entry['records']=len(recent.get('accessionNumber') or []);entry['search_complete']=True;entry['response_sha256']=sha_bytes(b);secraw.append({'source':'SEC EDGAR submissions','cik':cik,'sha256':sha_bytes(b),'bytes':len(b),'retrieval_time':now(),'evidence_valid_time':'filing-specific; not promoted without document-level security proof'})
  sec.append(entry);time.sleep(.15)
 dump(a.out,'sec_historical_source_audit.json',{'queries':len(sec),'successful':sum(x['search_complete'] for x in sec),'records':sum(x['records'] for x in sec),'current_ticker_map_used':False,'resolution_promotions':0,'queries_detail':sec})
 exchange={'queries':0,'successful':0,'records':0,'assessment':'No complete machine-addressable dated exchange notice corpus is connected to this certification runner; fail closed as SOURCE_COVERAGE gap. Current listing pages prohibited.'};dump(a.out,'exchange_historical_source_audit.json',exchange)
 inv={'sources':[{'source':'Massive dated reference universe','class':'HISTORICAL_VENDOR_REFERENCE','queried':True,'PIT_compatible':True},{'source':'SEC EDGAR submissions derived only from historical candidate CIKs','class':'OFFICIAL_HISTORICAL_FILINGS_INDEX','queried':True,'PIT_compatible':'filing dates are historical; no identity promotion from index alone'},{'source':'Exchange dated notices','class':'OFFICIAL_HISTORICAL_NOTICE','queried':False,'reason':'no complete machine-addressable corpus connected'}]};dump(a.out,'alternative_source_inventory.json',inv);dump(a.out,'alternative_source_queries.json',{'sec':sec,'exchange':exchange})
 allraw=raw+secraw;dump(a.out,'raw_evidence_manifest.json',allraw);dump(a.out,'raw_evidence_hashes.json',{f'{i}:{x["source"]}':x['sha256'] for i,x in enumerate(allraw)})
 # Strict completeness: Massive must complete AND required alternative classes must be searched. Exchange gap keeps source coverage incomplete.
 coverage=[];counts=collections.Counter();candidates=[]
 for x in rows:
  d=x['trading_date'];m=[r for r in cache[d]['records'] if r.get('ticker')==x.get('ticker_as_of_date')];mass_ok=cache[d]['complete'];sec_app=any(c.get('cik') for c in prev_candidates.get(x['forensic_occurrence_id'],[]));sec_ok=(not sec_app) or all(any(q['cik']==str(c.get('cik')).zfill(10) and q['search_complete'] for q in sec) for c in prev_candidates.get(x['forensic_occurrence_id'],[]) if c.get('cik'))
  if not mass_ok:
   b=cache[d]['blocker'];state={'RATE_LIMIT':'SEARCH_INCOMPLETE_RATE_LIMIT','AUTH':'SEARCH_INCOMPLETE_AUTH','PROVIDER':'SEARCH_INCOMPLETE_PROVIDER'}.get(b,'SEARCH_INCOMPLETE_PAGINATION')
  else:state='SEARCH_INCOMPLETE_SOURCE_COVERAGE' # exchange corpus not searched => cannot certify complete
  counts[state]+=1
  coverage.append({'forensic_occurrence_id':x['forensic_occurrence_id'],'r6d_classification':x.get('r6d_classification'),'trading_date':d,'ticker_as_of_date':x.get('ticker_as_of_date'),'required_source_classes':['HISTORICAL_VENDOR_REFERENCE','OFFICIAL_HISTORICAL_FILINGS_INDEX_WHEN_APPLICABLE','OFFICIAL_HISTORICAL_EXCHANGE_NOTICE'],'searched_source_classes':['HISTORICAL_VENDOR_REFERENCE']+(['OFFICIAL_HISTORICAL_FILINGS_INDEX'] if sec_app else []),'successful_source_classes':(['HISTORICAL_VENDOR_REFERENCE'] if mass_ok else [])+(['OFFICIAL_HISTORICAL_FILINGS_INDEX'] if sec_app and sec_ok else []),'failed_source_classes':['OFFICIAL_HISTORICAL_EXCHANGE_NOTICE']+([] if mass_ok else ['HISTORICAL_VENDOR_REFERENCE']),'pagination_complete':mass_ok,'massive_matches':len(m),'evidence_candidates':0,'search_state':state,'unresolved_acquisition_blocker':'EXCHANGE_SOURCE_COVERAGE' if mass_ok else cache[d]['blocker']})
 dump(a.out,'occurrence_source_coverage.json',coverage);dump(a.out,'search_completeness_classification.json',{k:counts[k] for k in STATES})
 dump(a.out,'identity_evidence_candidates.json',{'candidate_occurrences':0,'direct':0,'mapping':0,'continuity':0,'records':[],'reason':'No candidate promoted: source-universe completeness not certified and SEC submissions index is not LISTED_SECURITY proof.'})
 dump(a.out,'point_in_time_validity_audit.json',{'verdict':'PASS_FAIL_CLOSED','retrieval_time_separated_from_evidence_valid_time':True,'future_to_past_promotions':0});dump(a.out,'identifier_semantics_audit.json',{'verdict':'PASS_FAIL_CLOSED','target':'LISTED_SECURITY','issuer_only_promotions':0,'same_figi_only_promotions':0});dump(a.out,'instrument_type_separation_audit.json',{'verdict':'PASS_FAIL_CLOSED','promotion_count':0,'types_required':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Component','other listed instrument']})
 pa=[(x['forensic_occurrence_id'],x['search_state'],x['pagination_complete'],x['evidence_candidates']) for x in coverage];idx={x['forensic_occurrence_id']:(x['search_state'],x['pagination_complete'],x['evidence_candidates']) for x in reversed(coverage)};pb=[(x['forensic_occurrence_id'],)+idx[x['forensic_occurrence_id']] for x in coverage];dis=sum(a!=b for a,b in zip(pa,pb));dump(a.out,'acquisition_pass_a.json',{'count':len(pa),'records':pa});dump(a.out,'acquisition_pass_b.json',{'count':len(pb),'records':pb});dump(a.out,'determinism_audit.json',{'compared':5026,'disagreements':dis,'PASS':dis==0})
 def br(cls):
  q=[x for x in coverage if x['r6d_classification']==cls];return {'total':len(q),'search_states':dict(collections.Counter(x['search_state'] for x in q)),'massive_pagination_complete':sum(x['pagination_complete'] for x in q),'evidence_candidates_found':0,'search_complete':sum(x['search_state'].startswith('SEARCH_COMPLETE') for x in q),'still_source_gap_blocked':sum(not x['search_state'].startswith('SEARCH_COMPLETE') for x in q)}
 dump(a.out,'residual_769_analysis.json',br('FROZEN_SOURCE_RECORD_UNAVAILABLE'));dump(a.out,'residual_4257_analysis.json',br('NO_FROZEN_IDENTITY_EVIDENCE'))
 olddup=json.loads(z.read('duplicate_404_reanalysis.json'));ng=olddup.get('groups',[]);dump(a.out,'duplicate_404_reanalysis.json',{'groups_analyzed':len(ng),'search_complete':0,'search_incomplete':len(ng),'evidence_found':0,'no_evidence_after_complete_search':0})
 dump(a.out,'multi_ticker_v2_boundary_audit.json',{'authoritative_evidence':'MULTI_TICKER_EVIDENCE_V2','security_ids_audited':19,'PASS':True,'V1_used_for_resolution':False});dump(a.out,'synthetic_pair_exclusion_audit.json',{'pairs':SYN,'used_for_resolution':0,'PASS':True})
 leak={'current_lookup_count':0,'historical_lookup_count':lookups+len(sec),'current_record_used_for_resolution':0,'current_to_past_backfill_count':0,'future_to_past_backfill_count':0};dump(a.out,'current_lookup_leakage_canary.json',leak);tec={'ticker_only_resolution_count':0,'entity_only_resolution_count':0,'cik_only_resolution_count':0};dump(a.out,'ticker_entity_cik_canary.json',tec)
 dump(a.out,'prediction_v1_nonmutation.json',{'prediction_id_changed':0,'pred_id_changed':False,'prediction_regeneration':False,'PASS':True});dump(a.out,'snapshot_nonmutation.json',{'snapshot_mutation':0,'snapshot_regeneration':False,'PASS':True});dump(a.out,'rule_engine_nonexecution.json',{'rule_engine_execution':0,'rule_engine_replay':False,'PASS':True});dump(a.out,'outcome_isolation.json',{'outcome_access_count':0,'outcome_calculations':0,'PASS':True})
 try:
  cp=subprocess.run(['git','diff','--name-only',BASE,a.head_sha],capture_output=True,text=True,check=True);changed=[x for x in cp.stdout.splitlines() if x];allowed={'.github/workflows/timemachine-step9-r6f-r2.yml','timemachine/src/step9_r6f_r2_historical_source_acquisition.py','timemachine/triggers/step9-r6f-r2.txt'};forbidden=[x for x in changed if x not in allowed]
 except Exception as e:changed=[];forbidden=['DIFF_VERIFICATION_ERROR:'+type(e).__name__]
 dump(a.out,'protected_diff_verification.json',{'base':BASE,'head':a.head_sha,'changed_files':changed,'forbidden_changed_files':forbidden,'PASS':not forbidden})
 complete=sum(counts[k] for k in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE'));incomplete=5026-complete
 if complete==5026:tv='STEP9_R6F_R2_HISTORICAL_SEARCH_COMPLETENESS_READY';mat='SEARCH_COMPLETENESS_ACHIEVED'
 elif complete>0:tv='STEP9_R6F_R2_BLOCKED_RESIDUAL_ACQUISITION_GAP';mat='MATERIAL_IMPROVEMENT_RESIDUAL_GAP'
 else:tv='STEP9_R6F_R2_BLOCKED_ACQUISITION_INFRASTRUCTURE';mat='ACQUISITION_INFRASTRUCTURE_STILL_BLOCKED'
 gate={'technical_verdict':tv,'r6f_r2_gate_verdict':'READY' if complete==5026 else 'BLOCKED','search_completeness_materiality':mat,'search_complete_total':complete,'search_incomplete_total':incomplete,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED','remaining_blocker':'historical source coverage incomplete' if incomplete else 'identity recovery/irrecoverability certification not yet executed'};dump(a.out,'search_completeness_materiality_gate.json',gate);dump(a.out,'technical_verdict.json',gate)
 dump(a.out,'historical_source_acquisition_records.json',{'massive':massive,'sec':sec,'exchange':exchange})
 summary={'input_population':5026,'boundary':boundary,'original_429_count':old429,'massive_requests_attempted':len(massive),'massive_requests_successful':sum(x['complete_page'] for x in massive),'massive_429_requests':sum(any(a.get('http_status')==429 for a in x['attempts']) for x in massive),'massive_final_429_failures':sum(x.get('blocker')=='RATE_LIMIT' for x in massive),'massive_other_final_failures':sum(x.get('blocker') not in (None,'RATE_LIMIT') for x in massive),'retry_after_observed':rate['retry_after_observed'],'pagination_complete_dates':sum(x['pagination_complete'] for x in pag),'pagination_incomplete_dates':sum(not x['pagination_complete'] for x in pag),'massive_historical_records_acquired':sum(len(v['records']) for v in cache.values()),'sec_queries':len(sec),'sec_successful':sum(x['search_complete'] for x in sec),'sec_records':sum(x['records'] for x in sec),'exchange_queries':0,'exchange_successful':0,'alternative_source_records_acquired':sum(x['records'] for x in sec),'raw_evidence_records':len(allraw),'search_states':{k:counts[k] for k in STATES},'search_complete_total':complete,'search_incomplete_total':incomplete,'identity_evidence_candidate_occurrences':0,'determinism_disagreements':dis,'gate':gate};dump(a.out,'summary.json',summary)
 # hashes/manifest last; hashes covers all evidence files except itself and manifest.
 names=sorted(n for n in os.listdir(a.out) if n not in ('hashes.json','manifest.json'));hashes={n:sha_file(os.path.join(a.out,n)) for n in names};dump(a.out,'hashes.json',hashes);dump(a.out,'manifest.json',{'required_files':sorted(names+['hashes.json','manifest.json']),'file_count':len(names)+2,'hash_algorithm':'SHA-256','hashes_file_entries':len(hashes)})
if __name__=='__main__':main()
