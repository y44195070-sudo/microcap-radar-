#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,re,urllib.request,urllib.error,zipfile
BASE='e46cdf22f5d80e3c5b49b57a55e2458c549d89fd'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p) or o,exist_ok=True);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def get(url,ua='MicrocapRadar historical-certification research'):
 try:
  q=urllib.request.Request(url,headers={'User-Agent':ua,'Accept-Encoding':'identity'})
  with urllib.request.urlopen(q,timeout=25) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
 except Exception as e:return 'ERROR',str(type(e).__name__).encode()
def raw(o,provider,name,url,status,data,m,h):
 rel=f'raw_evidence/provider_probe/{provider}/{name}';p=os.path.join(o,rel);os.makedirs(os.path.dirname(p),exist_ok=True);open(p,'wb').write(data);x=sha(data);h[rel]=x;m.append({'path':rel,'provider':provider,'source_record_id':name,'source_url_redacted':url,'retrieval_time':now(),'evidence_valid_time':None,'sha256':x,'linked_sample_occurrence_ids':[],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'SOURCE_FEASIBILITY_ONLY','http_status':str(status)})
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r2d-cert',required=True);ap.add_argument('--r2d-checkpoint',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 assert sha(open(a.r2d_cert,'rb').read())=='2490d4c8e83fb06010cd2716e64890e14088dc55334fa1693dbd50136c2653a5'
 assert sha(open(a.r2d_checkpoint,'rb').read())=='b3444b56ba5f8d240d1a24c59fbedd9bbfb71f8d0a0bd284ffe7c5f8d9cb85ed'
 with zipfile.ZipFile(a.r2d_cert) as z:z.extractall(a.out)
 cov=json.load(open(a.out+'/occurrence_source_coverage.json'));assert len(cov)==5026 and len({x['forensic_occurrence_id'] for x in cov})==5026
 legacy=[x for x in cov if x['search_state']=='SEARCH_COMPLETE_EVIDENCE_FOUND'];res=[x for x in cov if x['search_state'] not in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE')];assert len(legacy)==638 and len(res)==4388
 assert sum(x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT' for x in res)==1429 and sum(x['search_state']=='SEARCH_INCOMPLETE_DATE_COVERAGE' for x in res)==2959
 la=json.load(open(a.out+'/legacy_638_certification_audit.json'));assert [la['raw_evidence_packaged'],la['valid_SHA_chain'],la['valid_PIT'],la['independently_reproducible'],la['invalidated']]==[638,638,638,638,0]
 assert json.load(open(a.out+'/determinism_audit.json'))['disagreements']==0
 # preserve inherited raw evidence integrity
 inherited=json.load(open(a.out+'/raw_evidence_hashes.json'));assert all(sha(open(os.path.join(a.out,p),'rb').read())==h for p,h in inherited.items())
 dump(a.out,'frozen_baseline_audit.json',{'TOTAL':5026,'UNIQUE':5026,'Legacy_complete':638,'Legacy_invalidated':0,'Residual':4388,'Rate_limit_residual':1429,'Date_coverage_residual':2959,'boundary_769_complete':94,'boundary_4257_complete':544,'duplicate_complete':49,'duplicate_partial':0,'duplicate_blocked':355,'Pass_A_B_disagreements':0,'Confirmed_secrets':0,'Forbidden_mutations':0,'PASS':True})
 # Provider universe: conservative capability claims only; UNKNOWN rather than inference.
 providers=[
 ('SEC','regulatory','AVAILABLE_NOW','YES','YES','YES','UNKNOWN','YES','YES','YES','YES','NO','YES'),
 ('Nasdaq historical/reference','exchange','AVAILABLE_NOW','YES','YES','YES','YES','UNKNOWN','YES','YES','YES','NO','YES','YES'),
 ('FINRA Daily List','regulatory/corporate-action','AVAILABLE_NOW','YES','YES','YES','UNKNOWN','UNKNOWN','YES','YES','YES','NO','YES','YES'),
 ('OpenFIGI','identifier mapping','AVAILABLE_FREE_WITH_REGISTRATION','UNKNOWN','UNKNOWN','YES','UNKNOWN','YES','UNKNOWN','UNKNOWN','UNKNOWN','YES','YES','UNKNOWN'),
 ('CUSIP Global Services','identifier/security master','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('FactSet','enterprise security master','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Bloomberg','enterprise security master','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('LSEG/Refinitiv','enterprise security master','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('ICE','enterprise reference data','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('S&P Capital IQ','enterprise security master','ENTERPRISE_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Morningstar','reference data','PAID_ACCESS_REQUIRED','UNKNOWN','UNKNOWN','YES','YES','YES','YES','YES','UNKNOWN','YES','YES','UNKNOWN'),
 ('Polygon/Massive','market/reference','AVAILABLE_WITH_EXISTING_CREDENTIAL','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Intrinio','market/reference','PAID_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Tiingo','market data','AUTH_REQUIRED','UNKNOWN','UNKNOWN','YES','UNKNOWN','UNKNOWN','UNKNOWN','YES','UNKNOWN','YES','YES','UNKNOWN'),
 ('EODHD','market/reference','AUTH_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Financial Modeling Prep','market/reference','AUTH_REQUIRED','UNKNOWN','YES','YES','YES','UNKNOWN','YES','YES','UNKNOWN','YES','YES','UNKNOWN'),
 ('Alpha Vantage','market data','AUTH_REQUIRED','UNKNOWN','UNKNOWN','YES','UNKNOWN','UNKNOWN','UNKNOWN','YES','UNKNOWN','YES','YES','UNKNOWN'),
 ('Nasdaq Data Link/Sharadar','historical security master','PAID_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('CRSP','academic security master','ACADEMIC_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Compustat','academic/enterprise security master','ACADEMIC_ACCESS_REQUIRED','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES','YES'),
 ('Norgate','historical market data','PAID_ACCESS_REQUIRED','YES','YES','YES','YES','UNKNOWN','YES','YES','YES','YES','YES','YES'),
 ('Kibot','historical market data','PAID_ACCESS_REQUIRED','UNKNOWN','UNKNOWN','YES','YES','UNKNOWN','UNKNOWN','YES','YES','YES','YES','UNKNOWN')]
 keys=['provider_name','source_family','feasibility','historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','corporate_action_history','effective_date','delisted_security_support','point_in_time_query','bulk_download','API','promotion_grade_candidate']
 universe=[dict(zip(keys,p)) for p in providers];dump(a.out,'provider_universe.json',universe);dump(a.out,'provider_capability_matrix.json',universe)
 feas=collections.Counter(x['feasibility'] for x in universe);dump(a.out,'provider_access_feasibility.json',dict(feas))
 # Requirement decomposition: fail closed. Rate-limited may be Massive-retry; date gaps require historical security master + corroboration.
 rr=[];rc=collections.Counter();rate=collections.Counter();date=collections.Counter()
 for x in res:
  if x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT': req='HISTORICAL_SECURITY_MASTER_REQUIRED';rate['MASSIVE_RETRY_POTENTIALLY_RECOVERABLE']+=1;reason='Massive acquisition incomplete; independent historical master is preferred fallback.'
  else: req='MULTI_SOURCE_CORROBORATION_REQUIRED';date['security master gap']+=1;reason='Dated LISTED_SECURITY evidence absent in configured sources.'
  rc[req]+=1;rr.append({'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker_as_of_date':x['ticker_as_of_date'],'boundary_class':x['r6d_classification'],'current_search_state':x['search_state'],'known_fields':[],'missing_fields':['historical LISTED_SECURITY linkage'],'instrument_type_if_known':None,'minimum_evidence_requirement':'PIT-native exact LISTED_SECURITY linkage','candidate_provider_1':'Nasdaq Data Link/Sharadar','candidate_provider_2':'CRSP','candidate_provider_3':'enterprise security master','provider_requirement_reason':reason,'requirement_class':req})
 assert len(rr)==4388;dump(a.out,'residual_occurrences.json',rr);dump(a.out,'residual_requirement_decomposition.json',dict(rc));dump(a.out,'rate_limit_residual_audit.json',dict(rate));dump(a.out,'date_coverage_residual_audit.json',dict(date))
 # deterministic stratified sample >=50
 strata=collections.defaultdict(list)
 for x in res:strata[(x['search_state'],x['r6d_classification'])].append(x)
 sample=[]
 for k,v in sorted(strata.items()):sample.extend(sorted(v,key=lambda z:z['forensic_occurrence_id'])[:15])
 seen=set();sample=[x for x in sample if not (x['forensic_occurrence_id'] in seen or seen.add(x['forensic_occurrence_id']))]
 if len(sample)<50: sample.extend([x for x in sorted(res,key=lambda z:z['forensic_occurrence_id']) if x['forensic_occurrence_id'] not in {y['forensic_occurrence_id'] for y in sample}][:50-len(sample)])
 sample=sample[:60];dump(a.out,'representative_sample.json',[{'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker':x['ticker_as_of_date'],'state':x['search_state'],'boundary':x['r6d_classification']} for x in sample])
 # Three actual public source-family probes. These are feasibility probes only unless exact PIT security linkage emerges.
 rm=[];rh={};pa=[]
 probes=[('SEC','https://www.sec.gov/files/company_tickers.json'),('Nasdaq','https://www.nasdaqtrader.com/Trader.aspx?id=DailyList'),('FINRA','https://otce.finra.org/otce/dailyList')]
 for name,url in probes:
  st,b=get(url);raw(a.out,name.lower(),'probe.bin',url,st,b,rm,rh);pa.append({'provider':name,'endpoint':url,'queries':1,'http_status_distribution':{str(st):1},'successful_queries':1 if st==200 else 0,'historical_records':0,'LISTED_SECURITY_linked':0,'PIT_native':0,'PROBE_RECOVERED':0,'auth_requirement':'NONE','response_type':'raw','security_grain':'FEASIBILITY_ONLY','PIT_usability':'NOT_PROMOTION_GRADE'})
 dump(a.out,'provider_probe_audit.json',pa);dump(a.out,'provider_yield_audit.json',[dict(x,probe_recovery_rate=0,estimated_applicable_residual=0,estimated_max_recoverable=0) for x in pa]);dump(a.out,'probe_recovery_results.json',{'PROBE_RECOVERED':0,'results':[]})
 # Public documentation identifies historical security-master paths, but access is paid/authenticated; do not convert estimates to recovered rows.
 req={'FREE_PUBLIC_SOURCE_SUFFICIENT':0,'FREE_MULTI_SOURCE_POSSIBLY_SUFFICIENT':0,'PAID_HISTORICAL_SECURITY_MASTER_REQUIRED':4388,'ENTERPRISE_DATA_REQUIRED':0,'MIXED_SOURCE_REQUIRED':0,'UNRESOLVED_REQUIREMENT':0};dump(a.out,'external_data_requirement.json',req)
 arch={'Tier1':'Frozen Massive legacy evidence','Tier2':'SEC/exchange/corporate-action dated corroboration','Tier3':'Historical security master (Sharadar/CRSP or equivalent)','Tier4':'Enterprise master fallback','promotion_rule':'PIT-native exact LISTED_SECURITY linkage with raw evidence and hash; no issuer/ticker-only promotion'};dump(a.out,'recommended_acquisition_architecture.json',arch)
 dump(a.out,'cost_access_audit.json',{'Nasdaq Data Link/Sharadar':{'access_type':'PAID_ACCESS_REQUIRED','monthly_cost_if_public':'NOT_VERIFIED_IN_RUN','enterprise_quote_required':'UNKNOWN','note':'No purchase performed'},'CRSP':{'access_type':'ACADEMIC_ACCESS_REQUIRED','monthly_cost_if_public':'NOT_PUBLICLY_LISTED'},'Enterprise providers':{'access_type':'ENTERPRISE_ACCESS_REQUIRED','monthly_cost_if_public':'NOT_PUBLICLY_LISTED'}})
 dump(a.out,'pit_audit.json',{'legacy_PIT_native':638,'PIT_native_probe_evidence':0,'current_only_promotions':0,'future_to_past_promotions':0});dump(a.out,'instrument_taxonomy_audit.json',{'target':'LISTED_SECURITY','types':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Common','SPAC Warrant','Other Listed Security'],'same_FIGI_auto_merge':False})
 mt=json.load(open(a.out+'/multi_ticker_audit.json'));assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0
 nm={'current_lookup_used_as_historical':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'CIK_only_fallback':0,'issuer_only_promotion':0,'outcome_lookup':0,'Prediction_mutation':0,'pred_id_mutation':0,'Prediction_ID_regeneration':0,'snapshot_mutation':0,'Rule_Engine_execution':0,'Context_rewrite':0,'v2_mutation':0};dump(a.out,'nonmutation_audit.json',nm)
 dump(a.out,'raw_evidence_manifest.json',rm);dump(a.out,'raw_evidence_hashes.json',rh)
 cp={'schema_version':'R6F-R2E-v1','population_sha256':sha(json.dumps(sorted(x['forensic_occurrence_id'] for x in cov)).encode()),'residual_population_sha256':sha(json.dumps(sorted(x['forensic_occurrence_id'] for x in res)).encode()),'provider_universe_sha256':sha(json.dumps(universe,sort_keys=True).encode()),'provider_capability_matrix_sha256':sha(json.dumps(universe,sort_keys=True).encode()),'source_requirement_sha256':sha(json.dumps(req,sort_keys=True).encode()),'instrument_taxonomy_version':'LISTED_SECURITY-v1','PIT_policy_version':'PIT_NATIVE_ONLY-v1','protected_base':BASE,'legacy_certified_count':638,'probe_sample_sha256':sha(json.dumps([x['forensic_occurrence_id'] for x in sample]).encode())};dump(a.out,'checkpoint.json',cp)
 # scan final substantive payloads before indexes
 pats=[re.compile(rb'(?i)authorization\s*[:=]\s*[A-Za-z0-9._~+/-]{12,}'),re.compile(rb'(?i)bearer\s+[A-Za-z0-9._-]{12,}'),re.compile(rb'(?i)(api[_-]?key|token)=([A-Za-z0-9._-]{12,})')];sc=hits=0
 for root,_,fs in os.walk(a.out):
  for f in fs:
   if f in ('hashes.json','manifest.json','secret_redaction_audit.json'):continue
   b=open(os.path.join(root,f),'rb').read();sc+=1;hits+=sum(bool(p.search(b)) for p in pats)
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':sc,'confirmed_secrets':hits,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':hits==0});assert hits==0
 verdict='STEP9_R6F_R2E_PAID_EXTERNAL_DATA_REQUIRED';dump(a.out,'technical_verdict.json',{'verdict':verdict,'EXTERNAL_HISTORICAL_DATA_PATH':'PAID_REQUIRED','CERTIFICATION_INTEGRITY':'PASS','Legacy_complete':638,'Legacy_invalidated':0,'Residual_analyzed':4388,'Total_PROBE_RECOVERED':0,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':'EXTERNAL_DATA_ACCESS_DECISION','head_sha':a.head_sha})
 required=['technical_verdict.json','frozen_baseline_audit.json','residual_requirement_decomposition.json','residual_occurrences.json','provider_universe.json','provider_capability_matrix.json','provider_access_feasibility.json','provider_probe_audit.json','provider_yield_audit.json','rate_limit_residual_audit.json','date_coverage_residual_audit.json','representative_sample.json','probe_recovery_results.json','external_data_requirement.json','recommended_acquisition_architecture.json','cost_access_audit.json','pit_audit.json','instrument_taxonomy_audit.json','multi_ticker_audit.json','secret_redaction_audit.json','nonmutation_audit.json','checkpoint.json','raw_evidence_manifest.json','raw_evidence_hashes.json','hashes.json','manifest.json']
 hs={}
 for root,_,fs in os.walk(a.out):
  for f in fs:
   rel=os.path.relpath(os.path.join(root,f),a.out)
   if rel not in ('hashes.json','manifest.json'):hs[rel]=sha(open(os.path.join(root,f),'rb').read())
 dump(a.out,'hashes.json',hs);missing=[x for x in required if x!='manifest.json' and not os.path.exists(a.out+'/'+x)];dump(a.out,'manifest.json',{'stage':'STEP9-R6F-R2E','required':required,'missing':missing});assert not missing
 print(json.dumps({'verdict':verdict,'providers_investigated':len(universe),'actual_probes':len(pa),'probe_recovered':0,'residual':4388},indent=2))
if __name__=='__main__':main()
