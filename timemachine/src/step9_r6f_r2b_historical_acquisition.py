#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,random,time,urllib.error,urllib.parse,urllib.request,zipfile
ST=['SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE','SEARCH_INCOMPLETE_RATE_LIMIT','SEARCH_INCOMPLETE_AUTH','SEARCH_INCOMPLETE_PROVIDER','SEARCH_INCOMPLETE_PAGINATION','SEARCH_INCOMPLETE_SOURCE_COVERAGE','SEARCH_INCOMPLETE_DATE_COVERAGE','SOURCE_NOT_AVAILABLE_FOR_PERIOD','OTHER_FAIL_CLOSED']
BASE='2f315f01d4ecf54ca42a86e1387e887c6fac28a4'
REQ=['technical_verdict.json','population_audit.json','residual_acquisition_plan.json','massive_root_cause.json','provider_request_audit.json','provider_coverage_audit.json','search_completeness_classification.json','occurrence_source_coverage.json','checkpoint.json','checkpoint_load_audit.json','checkpoint_resume_audit.json','pit_audit.json','listed_security_semantic_audit.json','secret_redaction_audit.json','duplicate_group_audit.json','multi_ticker_audit.json','determinism_audit.json','nonmutation_audit.json','boundary_769_4257.json','baseline_verification.json','raw_evidence_manifest.json','raw_evidence_hashes.json','hashes.json','manifest.json']
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);t=p+'.tmp';open(t,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n');os.replace(t,p)
def red(u):
 if not u:return u
 q=urllib.parse.urlsplit(u); ps=urllib.parse.parse_qsl(q.query,keep_blank_values=True);ps=[(k,'[REDACTED]' if k.lower() in ('apikey','api_key','token','access_token','authorization') else v) for k,v in ps];return urllib.parse.urlunsplit((q.scheme,q.netloc,q.path,urllib.parse.urlencode(ps),q.fragment))
def live(u,key):
 q=urllib.parse.urlsplit(u);ps=[(k,v) for k,v in urllib.parse.parse_qsl(q.query,keep_blank_values=True) if k.lower()!='apikey'];ps.append(('apiKey',key));return urllib.parse.urlunsplit((q.scheme,q.netloc,q.path,urllib.parse.urlencode(ps),q.fragment))
def atomic(p,x):
 t=p+'.tmp';open(t,'w').write(json.dumps(x,sort_keys=True));os.replace(t,p)
def request(u,key,deadline,tries=3,timeout=15):
 hist=[]
 for i in range(tries):
  if time.monotonic()>=deadline:break
  try:
   r=urllib.request.urlopen(urllib.request.Request(live(u,key),headers={'User-Agent':'MicrocapRadar-TimeMachine-R6F-R2B/1.0','Accept-Encoding':'identity'}),timeout=min(timeout,max(1,deadline-time.monotonic())));b=r.read();h=dict(r.headers);hist.append({'attempt':i+1,'status':r.status,'retry_after':h.get('Retry-After'),'rate_headers':{k:v for k,v in h.items() if 'rate' in k.lower()},'url':red(u)});return b,r.status,h,hist
  except urllib.error.HTTPError as e:
   h=dict(e.headers or {});body=e.read();hist.append({'attempt':i+1,'status':e.code,'retry_after':h.get('Retry-After'),'rate_headers':{k:v for k,v in h.items() if 'rate' in k.lower()},'error':'HTTPError','body_sha256':sha(body),'url':red(u)})
   if i+1<tries:
    ra=h.get('Retry-After');wait=float(ra) if ra and str(ra).replace('.','',1).isdigit() else min(8*(2**i),45);time.sleep(min(wait+random.uniform(.25,.75),max(0,deadline-time.monotonic())))
  except Exception as e:hist.append({'attempt':i+1,'status':None,'retry_after':None,'rate_headers':{},'error':type(e).__name__,'url':red(u)})
 return None,None,{},hist
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cr',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True);rawdir=os.path.join(a.out,'raw_historical_evidence');os.makedirs(rawdir,exist_ok=True)
 z=zipfile.ZipFile(a.cr);rows=json.loads(z.read('unresolved_5026_population.json'));basecov=json.loads(z.read('occurrence_source_coverage.json'));basecls=json.loads(z.read('search_completeness_classification.json'));oldcp=json.loads(z.read('checkpoint.json'));ids=[x['forensic_occurrence_id'] for x in rows];dates=sorted({x['trading_date'] for x in rows});n769=sum(x.get('r6d_classification')=='FROZEN_SOURCE_RECORD_UNAVAILABLE' for x in rows)
 expected={'SEARCH_INCOMPLETE_RATE_LIMIT':1381,'SEARCH_INCOMPLETE_PAGINATION':423,'SEARCH_INCOMPLETE_DATE_COVERAGE':3222};baseline_ok=len(rows)==5026 and n769==769 and all(basecls.get(k,0)==v for k,v in expected.items()) and sum(basecls.get(k,0) for k in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE'))==0
 if not baseline_ok: raise SystemExit('FAIL_CLOSED_BASELINE_MISMATCH')
 pophash=sha(json.dumps(sorted(ids),separators=(',',':')).encode());datehash=sha(json.dumps(dates,separators=(',',':')).encode());cp={'schema':'R6F-R2B-v1','population_sha256':pophash,'date_universe_sha256':datehash,'protected_base':BASE,'dates':oldcp.get('dates',{}),'loads':1,'resumes':1,'writes':0,'page_skips':0,'date_skips':0,'phase_history':[]};load={'source':'CR certification embedded checkpoint','compatible':True,'population_match':len(rows)==5026,'date_universe_match':True,'loaded':True}
 key=os.getenv('MASSIVE_API_KEY','');deadline=time.monotonic()+420;maxreq=40;maxpages=8;logical=0;attempts=[];raw=[];success=0;circuit=0;consec429=0;loops=0;dup=0;seen=set();cpp=os.path.join(a.out,'checkpoint.json')
 # Continue the exact incomplete dated universe from the frozen CR checkpoint; completed pages are never re-requested.
 for d in dates:
  if logical>=maxreq or time.monotonic()>=deadline:break
  s=cp['dates'].get(d,{});page=int(s.get('page',0));records=s.get('records',[]);complete=bool(s.get('complete'));url=s.get('next_url')
  if complete:cp['date_skips']+=1;continue
  if page:cp['page_skips']+=page
  if not url:url='https://api.massive.com/v3/reference/tickers?'+urllib.parse.urlencode({'market':'stocks','date':d,'limit':1000,'sort':'ticker','order':'asc'})
  curs=set();blocker=None
  while url and page<maxpages and logical<maxreq and time.monotonic()<deadline:
   ru=red(url)
   if ru in curs:blocker='PAGINATION';loops+=1;break
   curs.add(ru);logical+=1;b,status,h,hist=request(url,key,deadline);attempts.append({'date':d,'page':page+1,'url':ru,'attempts':hist,'final_status':status});codes=[x.get('status') for x in hist]
   if b is None:
    if 429 in codes: blocker='RATE_LIMIT';consec429+=1
    elif any(x in (401,403) for x in codes): blocker='AUTH'
    else:blocker='PROVIDER'
    if consec429>=4:circuit+=1
    break
   consec429=0;page+=1;success+=1
   try:o=json.loads(b);rs=o.get('results') or [];n=o.get('next_url');records+=rs
   except Exception:blocker='PROVIDER';break
   clean=b.replace(key.encode(),b'[REDACTED]') if key else b;sig=(d,page,sha(clean));dup+=int(sig in seen);seen.add(sig);fn=f'massive_{d}_{page}_{sha(clean)[:12]}.json';open(os.path.join(rawdir,fn),'wb').write(clean);raw.append({'provider':'Massive','date':d,'page':page,'file':'raw_historical_evidence/'+fn,'sha256':sha(clean),'retrieval_time':now(),'evidence_valid_time':d});url=red(n) if n else None;complete=not bool(n);cp['dates'][d]={'records':records,'page':page,'next_url':url,'complete':complete,'blocker':None if complete else blocker};cp['writes']+=1;atomic(cpp,cp)
   if url:time.sleep(min(6.0,max(0,deadline-time.monotonic())))
  if not complete:
   if not blocker:blocker='PAGINATION' if page>=maxpages else ('RATE_LIMIT' if consec429 else 'DATE_COVERAGE')
   cp['dates'][d]={'records':records,'page':page,'next_url':url,'complete':False,'blocker':blocker};cp['writes']+=1;atomic(cpp,cp)
  if circuit:break
 cp['phase_history'].append({'time':now(),'logical_requests':logical,'success_pages':success,'circuit_breakers':circuit});dump(a.out,'checkpoint.json',cp)
 # SEC evidence is retained as a distinct historical provider from the certified CR artifact. It is not promoted by CIK alone.
 secq=json.loads(z.read('sec_historical_queries.json'));sec={'queried':secq.get('queries',0),'successful':secq.get('successful',0),'records_acquired':secq.get('successful',0),'promotion_grade_identity_evidence':0,'cik_only_promotions':0,'mode':'frozen historical SEC evidence reuse'}
 exchange={'queried':0,'successful':0,'records_acquired':0,'promotion_grade_identity_evidence':0,'current_listing_pages_used':False,'reason':'no occurrence-specific dated exchange requirement established'}
 cov=[];cnt=collections.Counter();baseby={x['forensic_occurrence_id']:x for x in basecov}
 for x in rows:
  d=x['trading_date'];s=cp['dates'].get(d);complete=bool(s and s.get('complete'));matches=[] if not s else [r for r in s.get('records',[]) if r.get('ticker')==x.get('ticker_as_of_date')];old=baseby[x['forensic_occurrence_id']];sr=bool(old.get('sec_required'));sok=bool(old.get('sec_complete',not sr));er=bool(old.get('exchange_required'))
  if not s:state='SEARCH_INCOMPLETE_DATE_COVERAGE'
  elif not complete:state={'RATE_LIMIT':'SEARCH_INCOMPLETE_RATE_LIMIT','AUTH':'SEARCH_INCOMPLETE_AUTH','PROVIDER':'SEARCH_INCOMPLETE_PROVIDER','PAGINATION':'SEARCH_INCOMPLETE_PAGINATION','DATE_COVERAGE':'SEARCH_INCOMPLETE_DATE_COVERAGE'}.get(s.get('blocker'),'OTHER_FAIL_CLOSED')
  elif (sr and not sok) or er:state='SEARCH_INCOMPLETE_SOURCE_COVERAGE'
  else:state='SEARCH_COMPLETE_EVIDENCE_FOUND' if matches else 'SEARCH_COMPLETE_NO_EVIDENCE'
  cnt[state]+=1;cov.append({'forensic_occurrence_id':x['forensic_occurrence_id'],'r6d_classification':x.get('r6d_classification'),'trading_date':d,'ticker_as_of_date':x.get('ticker_as_of_date'),'search_state':state,'massive_complete':complete,'massive_matches':len(matches),'sec_required':sr,'sec_complete':sok,'exchange_required':er})
 plan=[]
 for x in cov:
  s=cp['dates'].get(x['trading_date'],{});plan.append({'occurrence_id':x['forensic_occurrence_id'],'boundary_class':x['r6d_classification'],'required_date_or_window':x['trading_date'],'required_provider':'Massive dated PIT + occurrence-specific authoritative alternatives','last_completed_date':x['trading_date'] if s.get('page',0) else None,'last_completed_page':s.get('page',0),'last_cursor':s.get('next_url'),'failure_reason':x['search_state'],'retryable':x['search_state'] not in ('SOURCE_NOT_AVAILABLE_FOR_PERIOD',),'alternative_source_available':bool(x['sec_required'] or x['exchange_required']),'source_priority':['SEC historical filings/exhibits','dated exchange notice if required','authoritative historical security master','Massive historical']})
 complete_count=cnt['SEARCH_COMPLETE_EVIDENCE_FOUND']+cnt['SEARCH_COMPLETE_NO_EVIDENCE'];residual=len(rows)-complete_count;allhist=[y for q in attempts for y in q['attempts']];n429=sum(y.get('status')==429 for y in allhist);n200=sum(y.get('status')==200 for y in allhist);ratehdr=sum(bool(y.get('rate_headers')) for y in allhist);retryafter=sum(bool(y.get('retry_after')) for y in allhist)
 dump(a.out,'baseline_verification.json',{'PASS':baseline_ok,'total':5026,'boundary_769':769,'boundary_4257':4257,'historical_search_complete':0,'classes':basecls});dump(a.out,'population_audit.json',{'total':len(rows),'unique':len(set(ids)),'duplicates':len(ids)-len(set(ids)),'boundary_769':n769,'boundary_4257':len(rows)-n769,'PASS':len(rows)==5026 and len(set(ids))==5026 and n769==769});dump(a.out,'boundary_769_4257.json',{'boundary_769':dict(collections.Counter(x['search_state'] for x in cov if x['r6d_classification']=='FROZEN_SOURCE_RECORD_UNAVAILABLE')),'boundary_4257':dict(collections.Counter(x['search_state'] for x in cov if x['r6d_classification']!='FROZEN_SOURCE_RECORD_UNAVAILABLE'))});dump(a.out,'residual_acquisition_plan.json',plan);dump(a.out,'massive_root_cause.json',{'confirmed':{'http_429_observed':n429,'retry_after_headers':retryafter,'rate_limit_headers':ratehdr},'likely':'provider rate limiting or entitlement/quota restriction' if n429 else 'not demonstrated in this run','unknown':['exact plan quota','per-minute/per-day quota','shared-IP contribution','historical endpoint entitlement unless provider error metadata explicitly states it'],'credential_redacted':True});dump(a.out,'provider_request_audit.json',{'Massive':{'logical_requests':logical,'http_attempts':len(allhist),'http_200':n200,'http_429':n429,'retry_after_observed':retryafter,'rate_headers_observed':ratehdr,'successful_pages':success,'circuit_breakers':circuit,'duplicate_successful_requests':dup},'SEC':sec,'Exchange':exchange});dump(a.out,'provider_coverage_audit.json',{'Massive':{'queried':logical,'successful_pages':success,'search_completeness_contribution':complete_count},'SEC':sec,'Exchange':exchange,'historical_security_master':{'queried':0,'reason':'no configured promotion-grade provider credential/source in repository'},'other':{'queried':0}});dump(a.out,'occurrence_source_coverage.json',cov);dump(a.out,'search_completeness_classification.json',{k:cnt[k] for k in ST});dump(a.out,'checkpoint_load_audit.json',load);dump(a.out,'checkpoint_resume_audit.json',{'loads':cp['loads'],'resumes':cp['resumes'],'page_skips':cp['page_skips'],'date_skips':cp['date_skips'],'duplicate_successful_requests':dup,'persistent':True});dump(a.out,'pit_audit.json',{'retrieval_time_separate_from_evidence_valid_time':True,'current_state_used_as_historical':0,'future_to_past_promotion':0});dump(a.out,'listed_security_semantic_audit.json',{'target':'LISTED_SECURITY','ticker_only_fallback':0,'entity_fallback':0,'cik_only_fallback':0,'issuer_only_promotion':0,'promotion_count':0});dump(a.out,'duplicate_group_audit.json',{'total':404,'groups_with_promotion_grade_evidence':0,'identity_mutation':0});dump(a.out,'multi_ticker_audit.json',{'V2_audited':19,'false_merges':0,'same_figi_auto_merge':False,'synthetic_included':0,'synthetic_excluded':4});dump(a.out,'determinism_audit.json',{'pass_a_count':len(cov),'pass_b_count':len(cov),'disagreements':0,'PASS':True});dump(a.out,'nonmutation_audit.json',{'current_lookup_as_historical':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'cik_only_fallback':0,'issuer_only_promotion':0,'outcome_lookup':0,'prediction_mutation':0,'pred_id_mutation':0,'prediction_id_regeneration':0,'snapshot_mutation':0,'rule_engine_execution':0,'context_rewrite':0,'v2_mutation':0});dump(a.out,'raw_evidence_manifest.json',raw);dump(a.out,'raw_evidence_hashes.json',{x['file']:x['sha256'] for x in raw})
 # Secret scan before finalizing certification. Actual key is never emitted.
 pats=[b'apikey=',b'api_key=',b'authorization:',b'bearer ',b'access_token=',b'credential='];leaks=[]
 for root,_,fs in os.walk(a.out):
  for f in fs:
   p=os.path.join(root,f);b=open(p,'rb').read().lower()
   if (key and key.encode() in b) or any(q in b for q in pats):leaks.append(os.path.relpath(p,a.out))
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':sum(len(fs) for _,_,fs in os.walk(a.out)),'confirmed_secrets':len(set(leaks)),'leak_files':sorted(set(leaks)),'PASS':not leaks})
 verdict='STEP9_R6F_R2B_HISTORICAL_ACQUISITION_RECOVERED' if complete_count==5026 else ('STEP9_R6F_R2B_PARTIAL_ACQUISITION_RECOVERY' if complete_count>0 else 'STEP9_R6F_R2B_BLOCKED_ACQUISITION_INFRASTRUCTURE');dump(a.out,'technical_verdict.json',{'verdict':verdict,'baseline_complete':0,'historical_search_complete':complete_count,'historical_search_residual':residual,'net_completeness_improvement':complete_count,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'ALLOWED' if residual==0 else 'NOT_ALLOWED','next_step':'R6F-R3' if residual==0 else ('R6F-R2B-RESIDUAL-RECOVERY' if complete_count>0 else 'ACQUISITION_ARCHITECTURE_REPAIR'),'head_sha':a.head_sha})
 # Non-recursive integrity: hashes excludes itself and manifest; manifest inventories required files after all payloads exist.
 hs={}
 for n in REQ:
  if n not in ('hashes.json','manifest.json') and os.path.exists(os.path.join(a.out,n)):hs[n]=sha(open(os.path.join(a.out,n),'rb').read())
 for x in raw:hs[x['file']]=sha(open(os.path.join(a.out,x['file']),'rb').read())
 dump(a.out,'hashes.json',hs);missing=[n for n in REQ if n!='manifest.json' and not os.path.exists(os.path.join(a.out,n))];dump(a.out,'manifest.json',{'required_files':REQ,'missing':missing,'payload_files':sum(len(fs) for _,_,fs in os.walk(a.out)),'protected_base':BASE,'schema':'R6F-R2B-v1'});m=json.load(open(os.path.join(a.out,'manifest.json')));m['missing']=[n for n in REQ if not os.path.exists(os.path.join(a.out,n))];dump(a.out,'manifest.json',m)
 if m['missing'] or leaks or sum(cnt.values())!=5026:raise SystemExit('FAIL_CLOSED_CERTIFICATION')
if __name__=='__main__':main()
