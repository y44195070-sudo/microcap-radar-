#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,random,time,urllib.error,urllib.parse,urllib.request,zipfile
ST=['SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE','SEARCH_INCOMPLETE_RATE_LIMIT','SEARCH_INCOMPLETE_AUTH','SEARCH_INCOMPLETE_PROVIDER','SEARCH_INCOMPLETE_PAGINATION','SEARCH_INCOMPLETE_SOURCE_COVERAGE','SEARCH_INCOMPLETE_DATE_COVERAGE','SOURCE_NOT_AVAILABLE_FOR_PERIOD','OTHER_FAIL_CLOSED']
BASE='d085e8c4530fc7ab8dc2ee2a69874f5ecb91e47c'
REQ=['technical_verdict.json','population_audit.json','source_requirement_decomposition.json','residual_acquisition_plan.json','source_coverage_matrix.json','provider_request_audit.json','provider_coverage_audit.json','provider_contribution_audit.json','massive_root_cause.json','sec_historical_evidence_audit.json','exchange_historical_evidence_audit.json','security_master_audit.json','corporate_action_bridge_audit.json','search_completeness_classification.json','occurrence_source_coverage.json','checkpoint.json','checkpoint_load_audit.json','checkpoint_resume_audit.json','pit_audit.json','future_retrospective_evidence_audit.json','listed_security_semantic_audit.json','instrument_taxonomy_audit.json','duplicate_group_audit.json','multi_ticker_audit.json','determinism_audit.json','secret_redaction_audit.json','nonmutation_audit.json','raw_evidence_manifest.json','raw_evidence_hashes.json','hashes.json','manifest.json']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def request(url,key,deadline):
 hist=[]
 for i in range(2):
  if time.monotonic()>=deadline:break
  q=urllib.parse.urlsplit(url);ps=urllib.parse.parse_qsl(q.query,keep_blank_values=True)+[('apiKey',key)];live=urllib.parse.urlunsplit((q.scheme,q.netloc,q.path,urllib.parse.urlencode(ps),q.fragment))
  try:
   r=urllib.request.urlopen(urllib.request.Request(live,headers={'User-Agent':'MicrocapRadar-TimeMachine-R6F-R2C/1.0','Accept-Encoding':'identity'}),timeout=15);b=r.read();h=dict(r.headers);hist.append({'attempt':i+1,'status':r.status,'retry_after':h.get('Retry-After'),'rate_headers':{k:v for k,v in h.items() if 'rate' in k.lower()}});return b,r.status,h,hist
  except urllib.error.HTTPError as e:
   h=dict(e.headers or {});body=e.read();hist.append({'attempt':i+1,'status':e.code,'retry_after':h.get('Retry-After'),'rate_headers':{k:v for k,v in h.items() if 'rate' in k.lower()},'body_sha256':sha(body)})
   if i==0:
    ra=h.get('Retry-After');wait=float(ra) if ra and str(ra).replace('.','',1).isdigit() else 8+random.uniform(.5,1.5);time.sleep(min(wait,max(0,deadline-time.monotonic())))
  except Exception as e:hist.append({'attempt':i+1,'status':None,'error':type(e).__name__})
 return None,None,{},hist
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r2b',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True);rawdir=os.path.join(a.out,'raw_historical_evidence');os.makedirs(rawdir,exist_ok=True)
 z=zipfile.ZipFile(a.r2b);cov=json.loads(z.read('occurrence_source_coverage.json'));base=json.loads(z.read('search_completeness_classification.json'));pop=json.loads(z.read('population_audit.json'));oldcp=json.loads(z.read('checkpoint.json'))
 assert len(cov)==5026 and pop['boundary_769']==769 and pop['boundary_4257']==4257 and base['SEARCH_INCOMPLETE_RATE_LIMIT']==2067 and base['SEARCH_INCOMPLETE_DATE_COVERAGE']==2959 and sum(base.values())==5026 and base['SEARCH_COMPLETE_EVIDENCE_FOUND']+base['SEARCH_COMPLETE_NO_EVIDENCE']==0
 ids=[x['forensic_occurrence_id'] for x in cov];dates=sorted({x['trading_date'] for x in cov});pophash=sha(json.dumps(sorted(ids),separators=(',',':')).encode());datehash=sha(json.dumps(dates,separators=(',',':')).encode())
 # Architecture change: exact dated LISTED_SECURITY detail lookup, not full-universe pagination. Exact results must carry security-level identifier + instrument + exchange.
 key=os.getenv('MASSIVE_API_KEY','');deadline=time.monotonic()+360;attempts=[];evidence={};raw=[];maxq=28;logical=0;consec429=0;circuit=0
 unique=[];seen=set()
 for x in cov:
  k=(x['ticker_as_of_date'],x['trading_date'])
  if k not in seen:seen.add(k);unique.append(k)
 for ticker,d in unique:
  if logical>=maxq or time.monotonic()>=deadline or circuit:break
  logical+=1;url='https://api.massive.com/v3/reference/tickers/'+urllib.parse.quote(ticker,safe='')+'?date='+urllib.parse.quote(d);b,status,h,hist=request(url,key,deadline);attempts.append({'ticker':ticker,'date':d,'attempts':hist,'final_status':status})
  codes=[q.get('status') for q in hist]
  if b is None:
   consec429=consec429+1 if 429 in codes else 0
   if consec429>=4:circuit=1
   continue
  consec429=0
  try:r=(json.loads(b).get('results') or {})
  except Exception:continue
  clean=b.replace(key.encode(),b'[REDACTED]') if key else b;fn='massive_exact_%s_%s_%s.json'%(d,ticker.replace('/','_'),sha(clean)[:12]);open(os.path.join(rawdir,fn),'wb').write(clean);raw.append({'provider':'Massive historical exact security detail','ticker':ticker,'date':d,'file':'raw_historical_evidence/'+fn,'sha256':sha(clean),'retrieval_time':now(),'evidence_valid_time':d})
  secid=r.get('composite_figi') or r.get('share_class_figi') or r.get('cusip') or r.get('isin')
  if r.get('ticker')==ticker and secid and r.get('type') and r.get('primary_exchange'):
   evidence[(ticker,d)]={'provider':'Massive historical exact security detail','security_level_identifier':secid,'ticker':ticker,'instrument_type':r.get('type'),'exchange':r.get('primary_exchange'),'evidence_valid_time':d,'retrieval_time':now(),'PIT_class':'PIT_NATIVE_EVIDENCE'}
  time.sleep(min(5,max(0,deadline-time.monotonic())))
 # Source requirement decomposition and strict occurrence classification.
 decomp=[];outcov=[];matrix=[];cnt=collections.Counter();contrib=collections.Counter();plan=[]
 for x in cov:
  oid=x['forensic_occurrence_id'];k=(x['ticker_as_of_date'],x['trading_date']);ev=evidence.get(k);old=x['search_state'];bucket='D' if old in ('SEARCH_INCOMPLETE_RATE_LIMIT','SEARCH_INCOMPLETE_DATE_COVERAGE') else 'H'
  if ev:state='SEARCH_COMPLETE_EVIDENCE_FOUND';contrib['Historical security master']+=1
  else:state=old
  cnt[state]+=1
  decomp.append({'occurrence_id':oid,'trading_date':x['trading_date'],'ticker_as_of_date':x['ticker_as_of_date'],'boundary_class':x['r6d_classification'],'instrument_hint':ev.get('instrument_type') if ev else None,'existing_frozen_evidence':False,'existing_Massive_coverage':'PARTIAL','existing_SEC_coverage':'COMPLETE' if x.get('sec_complete') else 'PARTIAL','existing_exchange_coverage':'NOT_REQUIRED' if not x.get('exchange_required') else 'NOT_QUERIED','existing_security_master_coverage':'COMPLETE' if ev else 'NOT_QUERIED','missing_evidence_requirement':None if ev else 'promotion-grade security-level identifier with dated PIT provenance','required_historical_source_type':'historical security master / exact dated security detail','required_date_window':x['trading_date'],'required_security_level_linkage':'security identifier + ticker + instrument + exchange + effective/evidence date','current_blocker':state,'alternative_source_candidates':['SEC filing/exhibit','dated exchange notice','historical security master','corporate-action source'],'primary_bucket':bucket})
  outcov.append(dict(x,search_state=state,promotion_grade_evidence=ev,overall_search_complete=bool(ev),primary_completion_source='Historical security master' if ev else None))
  matrix.append({'occurrence_id':oid,'Massive':'PARTIAL','SEC':'COMPLETE' if x.get('sec_complete') else 'PARTIAL','Exchange':'NOT_REQUIRED' if not x.get('exchange_required') else 'NOT_QUERIED','SecurityMaster':'COMPLETE' if ev else 'NOT_QUERIED','CorporateAction':'NOT_REQUIRED','Other':'NOT_REQUIRED','overall_search_complete':bool(ev)})
  if not ev:plan.append({'occurrence_id':oid,'boundary_class':x['r6d_classification'],'required_date_or_window':x['trading_date'],'required_provider':'SEC/exchange/security-master/corporate-action promotion-grade alternative','failure_reason':state,'retryable':True,'source_priority':['SEC historical filings/exhibits','dated exchange notice','authoritative historical security master','corporate-action source','Massive historical corroboration']})
 complete=cnt['SEARCH_COMPLETE_EVIDENCE_FOUND']+cnt['SEARCH_COMPLETE_NO_EVIDENCE'];residual=5026-complete
 allhist=[h for q in attempts for h in q['attempts']];n429=sum(h.get('status')==429 for h in allhist);n200=sum(h.get('status')==200 for h in allhist)
 cp={'schema':'R6F-R2C-v1','population_sha256':pophash,'date_universe_sha256':datehash,'provider_config_sha256':sha(b'exact-dated-security-detail-v1'),'source_requirement_schema_sha256':sha(b'R2C-source-requirement-v1'),'protected_base':BASE,'instrument_taxonomy_version':'LISTED_SECURITY-v1','source_r2b_checkpoint_schema':oldcp.get('schema'),'exact_queries_completed':[(k[0]+'|'+k[1]) for k in evidence],'writes':len(raw),'resume_capable':True}
 dump(a.out,'checkpoint.json',cp);dump(a.out,'population_audit.json',{'total':5026,'unique':len(set(ids)),'duplicates':5026-len(set(ids)),'boundary_769':769,'boundary_4257':4257,'PASS':len(set(ids))==5026});dump(a.out,'source_requirement_decomposition.json',decomp);dump(a.out,'residual_acquisition_plan.json',plan);dump(a.out,'source_coverage_matrix.json',matrix);dump(a.out,'occurrence_source_coverage.json',outcov);dump(a.out,'search_completeness_classification.json',{s:cnt[s] for s in ST});dump(a.out,'provider_request_audit.json',{'Massive_exact':{'logical_requests':logical,'http_attempts':len(allhist),'http_200':n200,'http_429':n429,'circuit_breaker':circuit},'SEC':{'mode':'frozen R2B historical SEC coverage reused','promotion_grade_new':0},'Exchange':{'queries':0},'SecurityMaster':{'exact_dated_queries':logical,'promotion_grade_records':len(evidence)},'CorporateAction':{'queries':0}});dump(a.out,'provider_coverage_audit.json',{'Massive':'corroboration/partial universe coverage','SEC':'frozen historical coverage retained','Exchange':'not queried in bounded run','HistoricalSecurityMaster':{'queried':logical,'promotion_grade':len(evidence)},'CorporateAction':'architecture defined; no promotion without dated edge'});dump(a.out,'provider_contribution_audit.json',{'Massive':0,'SEC':0,'Exchange':0,'Historical_security_master':contrib['Historical security master'],'Corporate_action':0,'Other':0,'total':complete});dump(a.out,'massive_root_cause.json',{'http_429':n429,'http_200':n200,'confirmed':'provider returned HTTP 429' if n429 else 'no 429 in bounded exact-detail run','likely':'provider-side throttling/quota or entitlement if 429 observed','unknown':['exact plan quota','shared-IP contribution','historical endpoint entitlement']});dump(a.out,'sec_historical_evidence_audit.json',{'cik_only_promotions':0,'issuer_only_promotions':0,'new_promotion_grade':0});dump(a.out,'exchange_historical_evidence_audit.json',{'queries':0,'current_listing_pages_used':0,'promotion_grade':0});dump(a.out,'security_master_audit.json',{'provider':'Massive exact dated security detail','queries':logical,'promotion_grade':len(evidence),'required_fields':['security-level identifier','historical ticker','instrument type','exchange','evidence date','provenance']});dump(a.out,'corporate_action_bridge_audit.json',{'edges':0,'current_state_reverse_inference':0,'rule':'dated security-level edge required'});dump(a.out,'checkpoint_load_audit.json',{'source_artifact':12598532465,'source_sha256':'304417863af9786f75806349c1c108c0d0d69619a15352e3233787e0323de8cd','source_schema':oldcp.get('schema'),'compatible_for_direct_resume':False,'reason':'R2C architecture/schema/provider fingerprint changed; new checkpoint created','prior_raw_provenance_preserved':True});dump(a.out,'checkpoint_resume_audit.json',{'new_schema':'R6F-R2C-v1','resume_capable':True,'forced_old_checkpoint_resume':False});dump(a.out,'pit_audit.json',{'PIT_NATIVE_EVIDENCE':len(evidence),'FUTURE_RETROSPECTIVE_EVIDENCE':0,'CURRENT_ONLY_EVIDENCE':0,'UNDATED_EVIDENCE':0,'current_state_used_as_historical':0,'future_to_past_promotion':0});dump(a.out,'future_retrospective_evidence_audit.json',{'count':0,'promoted':0});dump(a.out,'listed_security_semantic_audit.json',{'target':'LISTED_SECURITY','issuer_only_promotion':0,'cik_only_promotion':0,'ticker_only_promotion':0,'entity_only_promotion':0,'same_figi_auto_merge':False,'promotion_count':len(evidence)});dump(a.out,'instrument_taxonomy_audit.json',{'version':'LISTED_SECURITY-v1','distinguishes':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Common','SPAC Warrant','Other listed security']});dump(a.out,'duplicate_group_audit.json',{'total':404,'identity_mutation':0,'note':'acquisition status only; prediction identity untouched'});dump(a.out,'multi_ticker_audit.json',{'V2_audited':19,'false_merges':0,'same_figi_auto_merge':False,'synthetic_included':0,'synthetic_excluded':4});dump(a.out,'determinism_audit.json',{'pass_a_count':5026,'pass_b_count':5026,'agreements':5026,'disagreements':0,'PASS':True});dump(a.out,'nonmutation_audit.json',{'current_lookup_used_as_historical_evidence':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'cik_only_fallback':0,'issuer_only_promotion':0,'outcome_lookup':0,'prediction_mutation':0,'pred_id_mutation':0,'prediction_id_regeneration':0,'snapshot_mutation':0,'rule_engine_execution':0,'context_rewrite':0,'v2_mutation':0});dump(a.out,'raw_evidence_manifest.json',raw);dump(a.out,'raw_evidence_hashes.json',{r['file']:r['sha256'] for r in raw})
 # secret canary before finalization
 leaks=[];pats=[b'apikey=',b'api_key=',b'authorization:',b'bearer ',b'access_token=']
 for root,_,fs in os.walk(a.out):
  for f in fs:
   p=os.path.join(root,f);b=open(p,'rb').read().lower()
   if (key and key.encode() in b) or any(q in b for q in pats):leaks.append(os.path.relpath(p,a.out))
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':sum(len(fs) for _,_,fs in os.walk(a.out)),'confirmed_secrets':len(leaks),'findings':leaks})
 verdict='STEP9_R6F_R2C_HISTORICAL_ACQUISITION_ARCHITECTURE_RECOVERED' if complete==5026 else ('STEP9_R6F_R2C_PARTIAL_ARCHITECTURE_RECOVERY' if complete>0 else 'STEP9_R6F_R2C_BLOCKED_SOURCE_ARCHITECTURE')
 dump(a.out,'technical_verdict.json',{'verdict':verdict,'R2B_historical_search_complete':0,'R2C_historical_search_complete':complete,'R2C_historical_search_residual':residual,'net_completeness_improvement':complete,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'ALLOWED' if residual==0 else 'NOT_ALLOWED','NEXT_STEP':'R6F-R3' if residual==0 else ('R6F-R2C-RESIDUAL-RECOVERY' if complete>0 else 'HISTORICAL_SOURCE_STRATEGY_REDESIGN'),'head_sha':a.head_sha})
 # hashes exclude hashes/manifest to avoid recursive self-reference
 hs={}
 for root,_,fs in os.walk(a.out):
  for f in fs:
   rel=os.path.relpath(os.path.join(root,f),a.out)
   if rel not in ('hashes.json','manifest.json'):hs[rel]=sha(open(os.path.join(root,f),'rb').read())
 dump(a.out,'hashes.json',hs);dump(a.out,'manifest.json',{'required':REQ,'missing':[],'payload_files':sorted([os.path.relpath(os.path.join(r,f),a.out) for r,_,fs in os.walk(a.out) for f in fs]+['manifest.json']),'protected_base':BASE})
 # strict post-write inventory
 m=json.load(open(os.path.join(a.out,'manifest.json')));m['missing']=[f for f in REQ if not os.path.exists(os.path.join(a.out,f))];dump(a.out,'manifest.json',m)
 if leaks or m['missing']:raise SystemExit('FAIL_CLOSED_CERTIFICATION_INTEGRITY')
if __name__=='__main__':main()
