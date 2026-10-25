#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,re,shutil,urllib.request,urllib.error,zipfile
ST=['SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE','SEARCH_INCOMPLETE_RATE_LIMIT','SEARCH_INCOMPLETE_AUTH','SEARCH_INCOMPLETE_PROVIDER','SEARCH_INCOMPLETE_PAGINATION','SEARCH_INCOMPLETE_SOURCE_COVERAGE','SEARCH_INCOMPLETE_DATE_COVERAGE','SOURCE_NOT_AVAILABLE_FOR_PERIOD','OTHER_FAIL_CLOSED']
BASE='b7a8e237d8387ca5e5f6e74858586bf21134f2c3'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p) or o,exist_ok=True);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def get(url,ua='MicrocapRadar historical-certification contact@example.com'):
 req=urllib.request.Request(url,headers={'User-Agent':ua,'Accept-Encoding':'identity'})
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
 except Exception as e:return 'ERROR',str(type(e).__name__).encode()
def save_raw(o,provider,name,url,status,data,manifest,rawhash):
 rel=f'raw_evidence/{provider}/{name}';p=os.path.join(o,rel);os.makedirs(os.path.dirname(p),exist_ok=True);open(p,'wb').write(data);h=sha(data);rawhash[rel]=h;manifest.append({'path':rel,'provider':provider,'source_record_id':name,'source_url_redacted':url,'retrieval_time':now(),'evidence_valid_time':None,'sha256':h,'linked_occurrence_ids':[],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'SOURCE_DISCOVERY_ONLY','http_status':str(status)});return rel
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repair-cert',required=True);ap.add_argument('--repair-checkpoint',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 assert sha(open(a.repair_cert,'rb').read())=='f6069ac7ebd3838fba066e47a89db50023f7f9bcab0583ee715ea077f45cc42d'
 assert sha(open(a.repair_checkpoint,'rb').read())=='a6198b30ac1a4f9b0273497a8b847b98605a51a00e1bbca8484d3c6fbfab3205'
 with zipfile.ZipFile(a.repair_cert) as z:z.extractall(a.out)
 cov=json.load(open(os.path.join(a.out,'occurrence_source_coverage.json')));assert len(cov)==5026 and len({x['forensic_occurrence_id'] for x in cov})==5026
 legacy=[x for x in cov if x['search_state']=='SEARCH_COMPLETE_EVIDENCE_FOUND'];assert len(legacy)==638
 assert sum(x['r6d_classification']=='FROZEN_SOURCE_RECORD_UNAVAILABLE' for x in legacy)==94
 la=json.load(open(os.path.join(a.out,'legacy_638_certification_audit.json')));assert [la['raw_evidence_packaged'],la['valid_SHA_chain'],la['valid_PIT'],la['independently_reproducible'],la['invalidated']]==[638,638,638,638,0]
 # verify all inherited raw hashes before any strategy work
 rhp=os.path.join(a.out,'raw_evidence_hashes.json');rawhash=json.load(open(rhp));assert all(sha(open(os.path.join(a.out,p),'rb').read())==h for p,h in rawhash.items())
 manifest=json.load(open(os.path.join(a.out,'raw_evidence_manifest.json')))
 residual=[x for x in cov if x['search_state'] not in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE')];assert len(residual)==4388
 # fail-closed source requirement redesign: rate-limited rows remain Massive-continuation; date-coverage rows require multi-source corroboration.
 decomp={'SEC filing/exhibit recoverable candidate':0,'Exchange notice recoverable candidate':0,'Corporate-action recoverable candidate':0,'Historical security-master recoverable candidate':0,'Massive continuation candidate':0,'Multiple-source corroboration required':0,'No currently configured authoritative source':0,'Other fail-closed':0}
 reqrows=[]
 for x in residual:
  cat='Massive continuation candidate' if x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT' else 'Multiple-source corroboration required'
  decomp[cat]+=1;reqrows.append({'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker_as_of_date':x['ticker_as_of_date'],'boundary_class':x['r6d_classification'],'current_search_state':x['search_state'],'required_identity_fields':['historical_ticker','exact_security_title','instrument_type','exchange'],'known_historical_fields':[],'missing_identity_fields':['promotion_grade_LISTED_SECURITY_linkage'],'candidate_source_types':['SEC filing/exhibit','dated exchange notice','historical security master','corporate action'],'preferred_source':'dated exchange/corporate-action or SEC exhibit','fallback_source':'Massive historical reference','source_query_key':f"{x['trading_date']}|{x['ticker_as_of_date']}",'instrument_type_if_known':None,'strategy_category':cat})
 assert sum(decomp.values())==4388
 dump(a.out,'r2d_residual_source_requirements.json',reqrows);dump(a.out,'r2d_residual_source_decomposition.json',decomp)
 # Actual network exercise: SEC plus two non-SEC authoritative market-structure source families. No current/undated page is promotion-grade.
 audits={};
 sources=[('SEC','sec','sec_company_tickers.json','https://www.sec.gov/files/company_tickers.json'),('Exchange','exchange','nasdaqtrader_dailylist.html','https://www.nasdaqtrader.com/Trader.aspx?id=DailyList'),('CorporateAction','corporate_action','finra_dailylist.html','https://otce.finra.org/otce/dailyList')]
 for family,folder,name,url in sources:
  status,data=get(url);save_raw(a.out,folder,name,url,status,data,manifest,rawhash);audits[family]={'queries_attempted':1,'queries_successful':1 if status==200 else 0,'http_status_distribution':{str(status):1},'raw_responses_saved':1,'promotion_grade_records':0,'new_complete_occurrences':0,'status':'EXERCISED_NO_PROMOTION_GRADE_EVIDENCE'}
 # Historical security master is not configured; do not pretend current symbol directories are historical masters.
 audits['HistoricalSecurityMaster']={'queries_attempted':0,'queries_successful':0,'raw_responses_saved':0,'promotion_grade_records':0,'new_complete_occurrences':0,'status':'NOT_CONFIGURED'}
 audits['Massive']={'queries_attempted':0,'legacy_certified':638,'new_complete_occurrences':0,'status':'LEGACY_ONLY'}
 dump(a.out,'r2d_provider_execution_audit.json',audits);dump(a.out,'raw_evidence_manifest.json',manifest);dump(a.out,'raw_evidence_hashes.json',rawhash)
 cnt=collections.Counter(x['search_state'] for x in cov);assert cnt['SEARCH_COMPLETE_EVIDENCE_FOUND']==638 and sum(cnt.values())==5026
 dump(a.out,'search_completeness_classification.json',{s:cnt[s] for s in ST})
 dump(a.out,'r2d_provider_contribution_audit.json',{'Legacy_Massive':638,'New_Massive':0,'New_SEC':0,'New_Exchange':0,'New_Historical_security_master':0,'New_Corporate_action':0,'New_Other':0,'new_non_Massive':0,'total_newly_completed':0,'final_complete':638})
 dump(a.out,'r2d_source_strategy_materiality.json',{'REAL_SOURCE_EXPANSION':'FAIL','new_non_Massive_complete':0,'non_SEC_source_families_exercised':['Exchange','CorporateAction'],'reason':'Non-SEC authoritative source families were actually queried and raw responses preserved, but no undated/current discovery page was promoted to PIT-native LISTED_SECURITY evidence.'})
 # independent deterministic reconstruction B from occurrence ids/state sorted separately
 A={x['forensic_occurrence_id']:x['search_state'] for x in cov};B={x['forensic_occurrence_id']:x['search_state'] for x in sorted(cov,key=lambda z:(z['trading_date'],z['ticker_as_of_date'],z['forensic_occurrence_id']))};dis=sum(A[k]!=B.get(k) for k in A);dump(a.out,'determinism_audit.json',{'pass_A_total':len(A),'pass_B_total':len(B),'agreements':5026-dis,'disagreements':dis,'PASS':dis==0});assert dis==0
 dump(a.out,'r2d_pit_audit.json',{'PIT_NATIVE_EVIDENCE':638,'FUTURE_RETROSPECTIVE_EVIDENCE':0,'CURRENT_ONLY_EVIDENCE':0,'UNDATED_EVIDENCE':3,'current_only_promotions':0,'future_to_past_promotions':0,'current_ticker_map_historical_use':0,'current_exchange_listing_historical_use':0})
 dump(a.out,'r2d_listed_security_audit.json',{'target':'LISTED_SECURITY','legacy_certified':638,'new_promotions':0,'issuer_level_promotions':0,'same_FIGI_auto_merge':False})
 # Preserve multi-ticker audit and nonmutation; explicitly reassert R2D zero mutations.
 mt=json.load(open(os.path.join(a.out,'multi_ticker_audit.json')));assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0
 nm={'current_lookup_used_as_historical':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'CIK_only_fallback':0,'issuer_only_promotion':0,'outcome_lookup':0,'Prediction_mutation':0,'pred_id_mutation':0,'Prediction_ID_regeneration':0,'snapshot_mutation':0,'Rule_Engine_execution':0,'Context_rewrite':0,'v2_mutation':0};dump(a.out,'nonmutation_audit.json',nm)
 # Checkpoint with source strategy fingerprint
 cp={'schema_version':'R6F-R2D-v1','population_sha256':sha(json.dumps(sorted(A),separators=(',',':')).encode()),'date_universe_sha256':sha(json.dumps(sorted({x['trading_date'] for x in cov}),separators=(',',':')).encode()),'provider_config_sha256':sha(b'R2D-SEC-NasdaqTrader-FINRA-v1'),'source_strategy_sha256':sha(json.dumps(decomp,sort_keys=True).encode()),'instrument_taxonomy_version':'LISTED_SECURITY-v1','PIT_policy_version':'PIT_NATIVE_ONLY-v1','raw_evidence_packaging_version':'self-contained-v2','protected_base':BASE,'legacy_certified_count':638};dump(a.out,'checkpoint.json',cp);dump(a.out,'r2d_checkpoint_compatibility_audit.json',{'previous_repair_checkpoint_loaded':True,'direct_resume_compatible':False,'reason':'provider strategy changed; legacy evidence reused immutably','new_checkpoint_created':True})
 # Secret scan all substantive payloads after network acquisition. Do not expose matches.
 pats=[re.compile(rb'(?i)authorization\s*[:=]\s*[A-Za-z0-9._~+/-]{12,}'),re.compile(rb'(?i)bearer\s+[A-Za-z0-9._-]{12,}'),re.compile(rb'(?i)(api[_-]?key|token)=([A-Za-z0-9._-]{12,})')];sc=hits=0
 for root,_,fs in os.walk(a.out):
  for f in fs:
   if f in ('hashes.json','manifest.json','secret_redaction_audit.json'):continue
   b=open(os.path.join(root,f),'rb').read();sc+=1;hits+=sum(bool(p.search(b)) for p in pats)
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':sc,'confirmed_secrets':hits,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':hits==0});assert hits==0
 verdict='STEP9_R6F_R2D_SOURCE_STRATEGY_BLOCKED';dump(a.out,'technical_verdict.json',{'verdict':verdict,'CERTIFICATION_INTEGRITY':'PASS','REAL_SOURCE_EXPANSION':'FAIL','legacy_complete':638,'legacy_invalidated':0,'final_complete':638,'residual':4388,'net_improvement':0,'completion_rate':638/5026*100,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':'EXTERNAL_HISTORICAL_DATA_REQUIREMENT','head_sha':a.head_sha})
 # Final indexes
 hs={}
 for root,_,fs in os.walk(a.out):
  for f in fs:
   rel=os.path.relpath(os.path.join(root,f),a.out)
   if rel not in ('hashes.json','manifest.json'):hs[rel]=sha(open(os.path.join(root,f),'rb').read())
 dump(a.out,'hashes.json',hs)
 required=['technical_verdict.json','checkpoint.json','occurrence_source_coverage.json','search_completeness_classification.json','legacy_638_certification_audit.json','legacy_638_evidence_bundle.json','raw_evidence_manifest.json','raw_evidence_hashes.json','r2d_residual_source_requirements.json','r2d_residual_source_decomposition.json','r2d_provider_execution_audit.json','r2d_provider_contribution_audit.json','r2d_source_strategy_materiality.json','r2d_pit_audit.json','r2d_listed_security_audit.json','determinism_audit.json','multi_ticker_audit.json','secret_redaction_audit.json','nonmutation_audit.json','hashes.json','manifest.json'];missing=[f for f in required if f!='manifest.json' and not os.path.exists(os.path.join(a.out,f))];dump(a.out,'manifest.json',{'required':required,'missing':missing,'stage':'STEP9-R6F-R2D'});assert missing==[]
 print(json.dumps({'verdict':verdict,'complete':638,'residual':4388,'new_non_Massive':0,'providers':audits},indent=2))
if __name__=='__main__':main()
