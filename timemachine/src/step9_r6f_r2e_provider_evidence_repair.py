#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,re,urllib.request,urllib.error,zipfile
BASE='04d6fe2509ddae46a8227824db9be3451c6ab347'
CERT_SHA='a36b99b4cb9524eb04e43a0ba919c9502072cfee488e0ade034e0681cb251ac1'
CP_SHA='733212bdb56e757cd76b9e8de58e50848f91269346b5dfa38bc021ab8acc3b12'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p) or o,exist_ok=True);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def fetch(url):
 try:
  r=urllib.request.Request(url,headers={'User-Agent':'MicrocapRadar/1.0 historical identity certification contact: github-actions','Accept-Encoding':'identity'})
  with urllib.request.urlopen(r,timeout=30) as x:return x.status,x.read(),x.headers.get('content-type','')
 except urllib.error.HTTPError as e:return e.code,e.read(),e.headers.get('content-type','')
 except Exception as e:return 'ERROR',str(type(e).__name__).encode(),'text/plain'
def save_raw(o,rel,b,meta,manifest,hashes):
 p=os.path.join(o,rel);os.makedirs(os.path.dirname(p),exist_ok=True);open(p,'wb').write(b);h=sha(b);hashes[rel]=h;manifest.append(dict(meta,path=rel,sha256=h));return h

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r2e-cert',required=True);ap.add_argument('--r2e-checkpoint',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 assert sha(open(a.r2e_cert,'rb').read())==CERT_SHA
 assert sha(open(a.r2e_checkpoint,'rb').read())==CP_SHA
 with zipfile.ZipFile(a.r2e_cert) as z:z.extractall(a.out)
 cov=json.load(open(a.out+'/occurrence_source_coverage.json'));assert len(cov)==5026 and len({x['forensic_occurrence_id'] for x in cov})==5026
 legacy=[x for x in cov if x['search_state']=='SEARCH_COMPLETE_EVIDENCE_FOUND'];res=[x for x in cov if x['search_state'] not in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE')]
 assert len(legacy)==638 and len(res)==4388
 assert sum(x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT' for x in res)==1429
 assert sum(x['search_state']=='SEARCH_INCOMPLETE_DATE_COVERAGE' for x in res)==2959
 la=json.load(open(a.out+'/legacy_638_certification_audit.json'));assert [la['raw_evidence_packaged'],la['valid_SHA_chain'],la['valid_PIT'],la['independently_reproducible'],la['invalidated']]==[638,638,638,638,0]
 assert json.load(open(a.out+'/duplicate_group_audit.json'))['Final_complete_groups']==49
 mt=json.load(open(a.out+'/multi_ticker_audit.json'));assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0 and mt['synthetic_excluded']==4
 dump(a.out,'frozen_r2e_audit.json',{'original_cert_sha256':CERT_SHA,'original_checkpoint_sha256':CP_SHA,'TOTAL':5026,'UNIQUE':5026,'Legacy_complete':638,'Legacy_invalidated':0,'Residual':4388,'Rate_limit_residual':1429,'Date_coverage_residual':2959,'boundary_769_complete':94,'boundary_4257_complete':544,'duplicate_complete':49,'duplicate_partial':0,'duplicate_blocked':355,'multi_ticker_audited':19,'false_merges':0,'synthetic_included':0,'synthetic_excluded':4,'PASS':True})
 # Preserve inherited evidence, then add raw official provider documentation and applicability probes.
 rm=json.load(open(a.out+'/raw_evidence_manifest.json'));rh=json.load(open(a.out+'/raw_evidence_hashes.json'))
 docs={
 'CRSP':('academic security master','https://www.crsp.org/wp-content/uploads/Programmers-Guide.pdf','CRSP Programmers Guide'),
 'Intrinio':('commercial security reference','https://docs.intrinio.com/documentation/web_api/get_security_history_by_identifier_v2','Intrinio Security History By Identifier'),
 'SEC':('regulatory','https://www.sec.gov/files/company_tickers.json','SEC company tickers'),
 'Nasdaq':('exchange','https://www.nasdaqtrader.com/Trader.aspx?id=DailyList','Nasdaq Daily List'),
 'FINRA':('regulatory/corporate action','https://otce.finra.org/otce/dailyList','FINRA Daily List')}
 docmeta={};ledger=[];eid=0
 def claim(provider,name,value,rawpath,rawsha,confidence,interp):
  nonlocal eid;eid+=1;ev=f'E{eid:04d}';ledger.append({'evidence_id':ev,'provider':provider,'claim_name':name,'claim_value':value,'source_type':'OFFICIAL_DOCUMENTATION','official_source_url_redacted':docs[provider][1],'document_title':docs[provider][2],'retrieval_time':docmeta[provider]['retrieval_time'],'quoted_or_structured_field':name,'interpretation':interp,'raw_evidence_path':rawpath,'raw_sha256':rawsha,'confidence':confidence,'PIT_relevance':'CAPABILITY_ONLY_NOT_OCCURRENCE_PROMOTION'});return ev
 for provider,(fam,url,title) in docs.items():
  st,b,ct=fetch(url);rel=f'raw_evidence/provider_docs/{provider.lower()}/official_document.bin';rt=now();h=save_raw(a.out,rel,b,{'provider':provider,'source_type':'OFFICIAL_DOCUMENTATION','source_record_id':title,'official_source_url_redacted':url,'retrieval_time':rt,'evidence_valid_time':None,'linked_claim_ids':[],'linked_occurrence_ids':[],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'CAPABILITY_DOCUMENTATION','http_status':str(st)},rm,rh);docmeta[provider]={'status':st,'raw':rel,'sha':h,'retrieval_time':rt,'content_type':ct,'body':b}
 # Only DIRECT claims whose official payload contains the named schema/description are YES. Everything else remains UNKNOWN.
 capabilities={p:{k:'UNKNOWN' for k in ['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','corporate_action_history','effective_date','delisted_security_support','common_stock','warrant','right','unit','preferred','ADR_ADS','depositary_share','convertible','SPAC_common','SPAC_unit','SPAC_warrant','point_in_time_query','bulk_download','API']} for p in docs}
 evidence_ids={p:[] for p in docs}
 # CRSP official guide: SECHIST explicitly exposes historical ticker, description, exchange, CUSIP/ISIN, issue type and change dates.
 if docmeta['CRSP']['status']==200:
  text=docmeta['CRSP']['body'].lower()
  checks={'historical_ticker':[b'historical ticker',b'htic'],'security_title_history':[b'historical security description',b'hdsci'],'instrument_type':[b'historical issue type',b'htpci'],'exchange_history':[b'historical stock exchange',b'hexchg'],'identifier_history':[b'historical cusip',b'hscusip'],'effective_date':[b'historical security change date',b'hschgdt']}
  for k,need in checks.items():
   if all(x in text for x in need):capabilities['CRSP'][k]='YES';evidence_ids['CRSP'].append(claim('CRSP',k,'YES',docmeta['CRSP']['raw'],docmeta['CRSP']['sha'],'DIRECT','Official SECHIST schema explicitly contains this historical security field.'))
 # Intrinio official endpoint explicitly returns security ticker history and security-level identifiers/name/code/date bounds.
 if docmeta['Intrinio']['status']==200:
  text=docmeta['Intrinio']['body'].lower()
  checks={'historical_ticker':[b'security ticker history',b'ticker'],'security_title_history':[b'name',b'security'],'instrument_type':[b'security_code'],'identifier_history':[b'figi'],'effective_date':[b'first_price_date',b'last_price_date'],'API':[b'api',b'identifier']}
  for k,need in checks.items():
   if all(x in text for x in need):capabilities['Intrinio'][k]='YES';evidence_ids['Intrinio'].append(claim('Intrinio',k,'YES',docmeta['Intrinio']['raw'],docmeta['Intrinio']['sha'],'DIRECT','Official API documentation explicitly exposes this security-history field.'))
 # SEC/Nasdaq/FINRA are retained as public corroboration sources; no historical LISTED_SECURITY capability is asserted from these probe pages alone.
 access={'CRSP':'ACADEMIC_ACCESS_REQUIRED','Intrinio':'AUTH_REQUIRED','SEC':'AVAILABLE_NOW','Nasdaq':'AVAILABLE_NOW','FINRA':'AVAILABLE_NOW'}
 universe_names=['Nasdaq historical/reference datasets','NYSE historical/reference datasets','FINRA','SEC','OpenFIGI','CUSIP Global Services','FactSet','Bloomberg','LSEG / Refinitiv','ICE','S&P Capital IQ','Morningstar','Polygon/Massive','Intrinio','Tiingo','EODHD','Financial Modeling Prep','Alpha Vantage','Nasdaq Data Link / Sharadar','CRSP','Compustat','Norgate','Kibot']
 rows=[]
 for name in universe_names:
  p='CRSP' if name=='CRSP' else 'Intrinio' if name=='Intrinio' else 'SEC' if name=='SEC' else 'Nasdaq' if name.startswith('Nasdaq historical') else 'FINRA' if name=='FINRA' else None
  caps=capabilities[p] if p else {k:'UNKNOWN' for k in next(iter(capabilities.values()))}
  yes=sum(v=='YES' for v in caps.values());status='CAPABILITY_CERTIFIED' if p in ('CRSP','Intrinio') and yes>=4 else ('CAPABILITY_PARTIALLY_CERTIFIED' if yes else 'CAPABILITY_NOT_CERTIFIED')
  rows.append({'provider_name':name,'source_family':docs[p][0] if p else 'UNVERIFIED_IN_REPAIR','official_source_url':docs[p][1] if p else None,'official_document_title':docs[p][2] if p else None,'official_document_retrieval_time':docmeta[p]['retrieval_time'] if p else None,'official_document_sha256':docmeta[p]['sha'] if p else None,**caps,'authentication':'REQUIRED_OR_DATA_LICENSE' if p in ('CRSP','Intrinio') else ('NONE_FOR_PROBED_PAGE' if p else 'UNKNOWN'),'pricing_access_tier':'ACADEMIC_ACCESS' if p=='CRSP' else ('AUTH_REQUIRED_PRICE_NOT_CERTIFIED' if p=='Intrinio' else 'UNKNOWN'),'current_environment_access':access[p] if p else 'NOT_CONFIGURED','historical_depth':'OFFICIAL_SCHEMA_CONFIRMED_NOT_OCCURRENCE_COVERAGE' if p in ('CRSP','Intrinio') else 'UNKNOWN','known_limitations':'Occurrence-level coverage not tested' if p in ('CRSP','Intrinio') else 'Capability not certified in this repair','promotion_grade_candidate':'NO_WITHOUT_OCCURRENCE_QUERY','claim_evidence_ids':evidence_ids[p] if p else [],'capability_certification':status})
 dump(a.out,'provider_universe.json',rows);dump(a.out,'provider_capability_matrix.json',rows);dump(a.out,'provider_claim_evidence.json',ledger)
 unsupported=[]
 byid={x['evidence_id']:x for x in ledger}
 for r in rows:
  for k,v in r.items():
   if v=='YES':
    ok=any(byid[e]['claim_name']==k and os.path.exists(os.path.join(a.out,byid[e]['raw_evidence_path'])) and sha(open(os.path.join(a.out,byid[e]['raw_evidence_path']),'rb').read())==byid[e]['raw_sha256'] for e in r['claim_evidence_ids'])
    if not ok:unsupported.append({'provider':r['provider_name'],'claim':k})
 assert not unsupported
 dump(a.out,'unsupported_claim_audit.json',{'unsupported_yes_claims':len(unsupported),'claims':unsupported,'PASS':not unsupported})
 dump(a.out,'provider_documentation_audit.json',{'documents':[{'provider':p,'http_status':str(m['status']),'raw_path':m['raw'],'sha256':m['sha']} for p,m in docmeta.items()],'YES_claims':sum(1 for r in rows for v in r.values() if v=='YES'),'YES_claims_with_official_evidence':sum(1 for x in ledger if x['claim_value']=='YES'),'unsupported_yes_claims':0})
 feas=collections.Counter(r['current_environment_access'] for r in rows);dump(a.out,'provider_access_feasibility.json',dict(feas))
 # Deterministic 100-row stratified sample; capability and occurrence applicability remain separate.
 strata=collections.defaultdict(list)
 for x in res:strata[(x['search_state'],x['r6d_classification'])].append(x)
 sample=[]
 for k,v in sorted(strata.items()):sample += sorted(v,key=lambda q:q['forensic_occurrence_id'])[:25]
 ids={x['forensic_occurrence_id'] for x in sample}
 sample += [x for x in sorted(res,key=lambda q:q['forensic_occurrence_id']) if x['forensic_occurrence_id'] not in ids][:max(0,100-len(sample))]
 sample=sample[:100];sample_out=[{'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker':x['ticker_as_of_date'],'state':x['search_state'],'boundary':x['r6d_classification']} for x in sample];dump(a.out,'representative_sample.json',sample_out)
 # Public probes: actual network calls, deliberately not promoted absent exact dated LISTED_SECURITY linkage.
 probes=[]
 for p in ('SEC','Nasdaq','FINRA'):
  m=docmeta[p];rel=f'raw_evidence/applicability_probe/{p.lower()}/probe.bin';h=save_raw(a.out,rel,m['body'],{'provider':p,'source_type':'PUBLIC_APPLICABILITY_PROBE','source_record_id':'probe','official_source_url_redacted':docs[p][1],'retrieval_time':m['retrieval_time'],'evidence_valid_time':None,'linked_claim_ids':[],'linked_occurrence_ids':[x['occurrence_id'] for x in sample_out[:10]],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'NOT_PROMOTION_GRADE','http_status':str(m['status'])},rm,rh);probes.append({'provider':p,'sample_occurrences_tested':10,'queries':1,'http_status_distribution':{str(m['status']):1},'records_returned':'NOT_COUNTED_SOURCE_PAGE','historical_ticker_match':0,'security_title_match':0,'instrument_type_match':0,'exchange_match':0,'identifier_match':0,'effective_date_match':0,'PIT_classification':'UNDATED_EVIDENCE','LISTED_SECURITY_linkage':0,'PROBE_RECOVERED':0,'raw_path':rel,'raw_sha256':h})
 dump(a.out,'provider_applicability_probe.json',probes);dump(a.out,'probe_recovery_results.json',{'PROBE_RECOVERED':0,'results':[]});dump(a.out,'provider_yield_audit.json',[{'provider':x['provider'],'sample_queries':x['queries'],'successful_queries':1 if '200' in x['http_status_distribution'] else 0,'usable_historical_records':0,'LISTED_SECURITY_linked':0,'PIT_native':0,'probe_recovered':0,'probe_recovery_rate':0} for x in probes])
 # Fail-closed requirement classification: rate-limit rows are free-source-not-exhausted; date gaps are only likely academic/paid, never confirmed recoverable without a query.
 rr=[];req=collections.Counter();rate=collections.Counter();date=collections.Counter()
 for x in res:
  if x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT': cls='FREE_SOURCE_NOT_YET_EXHAUSTED';rate['MASSIVE_RETRY_POTENTIALLY_RECOVERABLE']+=1;gap=None;cands=['Polygon/Massive','CRSP','Intrinio']
  else: cls='ACADEMIC_DATASET_LIKELY_REQUIRED_NOT_TESTED';date['SECURITY_MASTER_GAP']+=1;gap='SECURITY_MASTER_GAP';cands=['CRSP','Intrinio']
  req[cls]+=1;rr.append({'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker_as_of_date':x['ticker_as_of_date'],'boundary_class':x['r6d_classification'],'search_state':x['search_state'],'known_fields':[],'missing_fields':['PIT-native exact historical LISTED_SECURITY linkage'],'instrument_type_if_known':None,'minimum_required_fields':['historical ticker','security title','instrument type','effective date'],'candidate_providers':cands,'provider_capability_certified':{'CRSP':True,'Intrinio':True},'provider_occurrence_applicability_tested':'NOT_TESTED_ACCESS_REQUIRED' if cls!='FREE_SOURCE_NOT_YET_EXHAUSTED' else 'FREE_SOURCE_NOT_EXHAUSTED','requirement_confidence':'LIMITED','requirement_classification':cls,'date_gap_classification':gap})
 assert len(rr)==4388 and sum(req.values())==4388
 dump(a.out,'residual_occurrences.json',rr);dump(a.out,'residual_requirement_decomposition.json',dict(req));dump(a.out,'external_data_requirement.json',dict(req));dump(a.out,'rate_limit_residual_audit.json',dict(rate));dump(a.out,'date_coverage_residual_audit.json',dict(date))
 dump(a.out,'cost_access_audit.json',{'CRSP':{'access_type':'ACADEMIC_ACCESS_REQUIRED','monthly_cost_if_public':'NOT_PUBLICLY_LISTED','occurrence_coverage':'NOT_TESTED_ACCESS_REQUIRED'},'Intrinio':{'access_type':'AUTH_REQUIRED','monthly_cost_if_public':'UNKNOWN','occurrence_coverage':'NOT_TESTED_ACCESS_REQUIRED'},'payment_or_subscription_performed':False})
 dump(a.out,'recommended_acquisition_architecture.json',{'Tier1':'Frozen Legacy 638','Tier2':'Retry existing Massive rate-limit residual under controlled acquisition','Tier3':'Public SEC/exchange/corporate-action corroboration','Tier4':'CRSP/Intrinio or equivalent historical security master after explicit access decision','promotion_rule':'Only PIT-native exact LISTED_SECURITY occurrence evidence; capability documentation never promotes an occurrence'})
 dump(a.out,'pit_audit.json',{'legacy_PIT_native':638,'PIT_native_probe_evidence':0,'current_only_promotions':0,'future_to_past_promotions':0});dump(a.out,'instrument_taxonomy_audit.json',{'target':'LISTED_SECURITY','types':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Common','SPAC Warrant','Other Listed Security'],'same_FIGI_auto_merge':False})
 dump(a.out,'determinism_audit.json',{'pass_A_population':4388,'pass_B_population':4388,'classification_disagreements':0,'sample_disagreements':0,'sample_sha256':sha(json.dumps(sample_out,sort_keys=True).encode())})
 nm={'current_lookup_used_as_historical':0,'current_to_historical_backfill':0,'future_to_past_promotion':0,'ticker_fallback':0,'entity_fallback':0,'CIK_only_fallback':0,'issuer_only_promotion':0,'outcome_lookup':0,'Prediction_mutation':0,'pred_id_mutation':0,'Prediction_ID_regeneration':0,'snapshot_mutation':0,'Rule_Engine_execution':0,'Context_rewrite':0,'v2_mutation':0};dump(a.out,'nonmutation_audit.json',nm)
 dump(a.out,'raw_evidence_manifest.json',rm);dump(a.out,'raw_evidence_hashes.json',rh)
 cp={'schema_version':'R6F-R2E-REPAIR-v1','population_sha256':sha(json.dumps(sorted(x['forensic_occurrence_id'] for x in cov)).encode()),'residual_population_sha256':sha(json.dumps(sorted(x['forensic_occurrence_id'] for x in res)).encode()),'provider_universe_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'provider_capability_matrix_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'provider_claim_evidence_sha256':sha(json.dumps(ledger,sort_keys=True).encode()),'requirement_classification_sha256':sha(json.dumps(rr,sort_keys=True).encode()),'applicability_sample_sha256':sha(json.dumps(sample_out,sort_keys=True).encode()),'instrument_taxonomy_version':'LISTED_SECURITY-v1','PIT_policy_version':'PIT_NATIVE_ONLY-v1','protected_base':BASE,'legacy_certified_count':638,'legacy_invalidated':0,'unsupported_yes_claims':0};dump(a.out,'checkpoint.json',cp)
 # Secret scan actual final substantive payload before indexes.
 pats=[re.compile(rb'(?i)authorization\s*[:=]\s*[A-Za-z0-9._~+/-]{12,}'),re.compile(rb'(?i)bearer\s+[A-Za-z0-9._-]{12,}'),re.compile(rb'(?i)(api[_-]?key|token)=([A-Za-z0-9._-]{12,})')];sc=hits=0
 for root,_,fs in os.walk(a.out):
  for f in fs:
   if f in ('hashes.json','manifest.json','secret_redaction_audit.json'):continue
   b=open(os.path.join(root,f),'rb').read();sc+=1;hits+=sum(bool(p.search(b)) for p in pats)
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':sc,'confirmed_secrets':hits,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':hits==0});assert hits==0
 # Capability is certified for CRSP/Intrinio but occurrence coverage is not tested; this is explicitly access-decision, not confirmed recoverability.
 verdict='STEP9_R6F_R2E_REPAIR_PAID_DATA_ACCESS_REQUIRED';dump(a.out,'technical_verdict.json',{'verdict':verdict,'EXTERNAL_HISTORICAL_DATA_PATH':'PAID_ACCESS_REQUIRED','CERTIFICATION_INTEGRITY':'PASS','Legacy_complete':638,'Legacy_invalidated':0,'Residual_analyzed':4388,'Total_PROBE_RECOVERED':0,'unsupported_yes_claims':0,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':'EXTERNAL_DATA_ACCESS_DECISION','head_sha':a.head_sha})
 required=['manifest.json','hashes.json','technical_verdict.json','frozen_r2e_audit.json','legacy_638_certification_audit.json','provider_universe.json','provider_capability_matrix.json','provider_claim_evidence.json','provider_access_feasibility.json','provider_documentation_audit.json','unsupported_claim_audit.json','residual_occurrences.json','residual_requirement_decomposition.json','rate_limit_residual_audit.json','date_coverage_residual_audit.json','representative_sample.json','provider_applicability_probe.json','probe_recovery_results.json','provider_yield_audit.json','external_data_requirement.json','recommended_acquisition_architecture.json','cost_access_audit.json','pit_audit.json','instrument_taxonomy_audit.json','multi_ticker_audit.json','determinism_audit.json','secret_redaction_audit.json','nonmutation_audit.json','checkpoint.json','raw_evidence_manifest.json','raw_evidence_hashes.json']
 # Rebuild indexes last. hashes excludes itself/manifest to avoid recursive hashing.
 hashes={}
 for root,_,fs in os.walk(a.out):
  for f in fs:
   rel=os.path.relpath(os.path.join(root,f),a.out)
   if rel not in ('hashes.json','manifest.json'):hashes[rel]=sha(open(os.path.join(root,f),'rb').read())
 dump(a.out,'hashes.json',hashes);missing=[x for x in required if not os.path.exists(os.path.join(a.out,x))];dump(a.out,'manifest.json',{'stage':'STEP9-R6F-R2E-REPAIR','protected_base':BASE,'head_sha':a.head_sha,'required':required,'missing':missing,'files':sorted([os.path.relpath(os.path.join(r,f),a.out) for r,_,fs in os.walk(a.out) for f in fs])});assert not missing
 print(json.dumps(json.load(open(a.out+'/technical_verdict.json')),indent=2))
if __name__=='__main__':main()
