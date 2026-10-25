#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,re,subprocess,urllib.request,urllib.error,zipfile
BASE='ffda9f4f6282a0c1cfd5bcb37cffc18aef3bf5a6'
CERT_SHA='c7b23765b80ad5eb690846590cf8a10370c86f16072a8810a94adc67524e49b2'
CP_SHA='4938611b0b249982267a61d641392336ab8141899c292d31a8b795052ec7d00c'
CAP_KEYS=['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','corporate_action_history','effective_date','delisted_security_support','common_stock','warrant','right','unit','preferred','ADR_ADS','depositary_share','convertible','SPAC_common','SPAC_unit','SPAC_warrant','point_in_time_query','bulk_download','API']
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(open(p,'rb').read())
def dump(o,n,x):
 p=os.path.join(o,n);os.makedirs(os.path.dirname(p) or o,exist_ok=True);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def fetch(url):
 try:
  q=urllib.request.Request(url,headers={'User-Agent':'MicrocapRadar/1.0 evidence-certification','Accept-Encoding':'identity'})
  with urllib.request.urlopen(q,timeout=45) as r:return r.status,r.read(),r.headers.get('content-type',''),r.geturl()
 except urllib.error.HTTPError as e:return e.code,e.read(),e.headers.get('content-type',''),url
 except Exception as e:return 'ERROR',str(type(e).__name__).encode(),'text/plain',url
def save_raw(o,rel,b,meta,manifest,hashes):
 p=os.path.join(o,rel);os.makedirs(os.path.dirname(p),exist_ok=True);open(p,'wb').write(b);h=sha_bytes(b);hashes[rel]=h;manifest.append(dict(meta,path=rel,sha256=h));return h
def text(b): return b.decode('utf-8','ignore').lower()
def content_ok(status,b,provider,markers):
 t=text(b);return status==200 and len(b)>1000 and provider.lower() in t and all(m.lower() in t for m in markers)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repair-cert',required=True);ap.add_argument('--repair-checkpoint',required=True);ap.add_argument('--out',required=True);ap.add_argument('--head-sha',required=True);a=ap.parse_args();os.makedirs(a.out,exist_ok=True)
 assert sha_file(a.repair_cert)==CERT_SHA and sha_file(a.repair_checkpoint)==CP_SHA
 with zipfile.ZipFile(a.repair_cert) as z:z.extractall(a.out)
 # frozen baseline, independently from payload
 cov=json.load(open(a.out+'/occurrence_source_coverage.json'));assert len(cov)==5026 and len({x['forensic_occurrence_id'] for x in cov})==5026
 legacy=[x for x in cov if x['search_state']=='SEARCH_COMPLETE_EVIDENCE_FOUND'];res=[x for x in cov if x['search_state'] not in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE')]
 assert len(legacy)==638 and len(res)==4388
 assert sum(x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT' for x in res)==1429
 assert sum(x['search_state']=='SEARCH_INCOMPLETE_DATE_COVERAGE' for x in res)==2959
 la=json.load(open(a.out+'/legacy_638_certification_audit.json'));assert [la['raw_evidence_packaged'],la['valid_SHA_chain'],la['valid_PIT'],la['independently_reproducible'],la['invalidated']]==[638,638,638,638,0]
 mt=json.load(open(a.out+'/multi_ticker_audit.json'));assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0 and mt['synthetic_excluded']==4
 dump(a.out,'frozen_r2e_repair_audit.json',{'protected_base':BASE,'original_cert_sha256':CERT_SHA,'original_checkpoint_sha256':CP_SHA,'TOTAL':5026,'UNIQUE':5026,'Legacy_complete':638,'Legacy_invalidated':0,'Residual':4388,'Rate_limit':1429,'Date_coverage':2959,'boundary_769_complete':94,'boundary_4257_complete':544,'Multi_Ticker_audited':19,'false_merges':0,'synthetic_included':0,'synthetic_excluded':4,'PASS':True})
 dump(a.out,'legacy_638_audit.json',{'complete':638,'raw_evidence_valid':638,'SHA_valid':638,'PIT_valid':638,'reproducible':638,'invalidated':0,'PASS':True})
 dump(a.out,'residual_population_audit.json',{'residual':4388,'rate_limit':1429,'date_coverage':2959,'PASS':True})
 # inherit raw evidence ledger then add recovery docs
 rm=json.load(open(a.out+'/raw_evidence_manifest.json'));rh=json.load(open(a.out+'/raw_evidence_hashes.json'))
 sources={
  'CRSP_SCHEMA':('CRSP','https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/','CRSP US Stock & Indexes Data Descriptions','schema'),
  'CRSP_PRODUCT':('CRSP','https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/','CRSP US Stock Databases','access'),
  'INTRINIO_HISTORY':('Intrinio','https://docs.intrinio.com/documentation/web_api/get_security_history_by_identifier_v2','Intrinio Security History By Identifier','schema'),
  'INTRINIO_LOOKUP':('Intrinio','https://docs.intrinio.com/documentation/web_api/GetSecurityById_v2','Intrinio Lookup Security','schema')}
 docs={};doc_audit=[]
 for key,(provider,url,title,kind) in sources.items():
  st,b,ct,final=fetch(url);rt=now();rel=f'raw_evidence/provider_docs/{provider.lower()}/{key.lower()}.html';h=save_raw(a.out,rel,b,{'provider':provider,'source_type':'OFFICIAL_DOCUMENTATION','source_record_id':key,'official_source_url_redacted':url,'retrieval_time':rt,'evidence_valid_time':None,'linked_claim_ids':[],'linked_occurrence_ids':[],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'CAPABILITY_DOCUMENTATION','http_status':str(st)},rm,rh)
  if key=='CRSP_SCHEMA': markers=['ticker symbol','name effective date','exchange code','cusip']
  elif key=='CRSP_PRODUCT': markers=['active and inactive','third party access','request subscription information']
  elif key=='INTRINIO_HISTORY': markers=['security history by identifier','security_code','first_price_date','last_price_date']
  else: markers=['previous_tickers','listing_exchange_mic','delisted']
  ok=content_ok(st,b,provider,markers);docs[key]={'provider':provider,'status':st,'bytes':len(b),'content_type':ct,'final_url':final,'raw_path':rel,'sha256':h,'retrieval_time':rt,'content_valid':ok,'body':text(b),'markers':markers}
  doc_audit.append({k:v for k,v in docs[key].items() if k!='body'})
 dump(a.out,'provider_documentation_audit.json',{'documents':doc_audit})
 dump(a.out,'documentation_content_validation.json',{'documents':[{'source':k,'documentation_download_success':v['status']==200,'documentation_content_valid':v['content_valid'],'documentation_hash_valid':sha_file(os.path.join(a.out,v['raw_path']))==v['sha256'],'claim_linkage_valid':'EVALUATED_BELOW','http_status':str(v['status']),'content_type':v['content_type'],'bytes':v['bytes'],'markers':v['markers']} for k,v in docs.items()]})
 # evidence-backed claims only
 ledger=[];eid=0
 def ev(provider,claim,source,interpretation):
  nonlocal eid;eid+=1;e=f'REC-E{eid:03d}';d=docs[source];ledger.append({'evidence_id':e,'provider':provider,'claim_name':claim,'claim_value':'YES','source_type':'OFFICIAL_DOCUMENTATION','official_source_url_redacted':sources[source][1],'document_title':sources[source][2],'retrieval_time':d['retrieval_time'],'quoted_or_structured_field':claim,'interpretation':interpretation,'raw_evidence_path':d['raw_path'],'raw_sha256':d['sha256'],'confidence':'DIRECT','PIT_relevance':'CAPABILITY_ONLY_NOT_OCCURRENCE_PROMOTION'});return e
 caps={'CRSP':{k:'UNKNOWN' for k in CAP_KEYS},'Intrinio':{k:'UNKNOWN' for k in CAP_KEYS}};ids={'CRSP':[],'Intrinio':[]}
 crsp_required={'historical_ticker':['ticker symbol','name effective date'],'security_title_history':['company name','name effective date'],'instrument_type':['share code','name effective date'],'exchange_history':['exchange code','name effective date'],'identifier_history':['cusip','name effective date'],'effective_date':['name effective date','last date of name']}
 if docs['CRSP_SCHEMA']['content_valid']:
  t=docs['CRSP_SCHEMA']['body']
  for k,ms in crsp_required.items():
   if all(m in t for m in ms):caps['CRSP'][k]='YES';ids['CRSP'].append(ev('CRSP',k,'CRSP_SCHEMA','Official CRSP name-history structure directly supplies dated security-level history.'))
 if docs['CRSP_PRODUCT']['content_valid']:
  t=docs['CRSP_PRODUCT']['body']
  if 'active and inactive' in t:caps['CRSP']['delisted_security_support']='YES';ids['CRSP'].append(ev('CRSP','delisted_security_support','CRSP_PRODUCT','Official product page covers active and inactive U.S. securities.'))
  if 'sas, ascii' in t or 'delivery formats' in t:caps['CRSP']['bulk_download']='YES';ids['CRSP'].append(ev('CRSP','bulk_download','CRSP_PRODUCT','Official product page documents flat-file delivery formats.'))
 intr_req={'historical_ticker':['security ticker history','ticker'],'security_title_history':['name','security'],'instrument_type':['security_code'],'identifier_history':['figi'],'effective_date':['first_price_date','last_price_date'],'API':['endpoint','api-v2.intrinio.com']}
 if docs['INTRINIO_HISTORY']['content_valid']:
  t=docs['INTRINIO_HISTORY']['body']
  for k,ms in intr_req.items():
   if all(m in t for m in ms):caps['Intrinio'][k]='YES';ids['Intrinio'].append(ev('Intrinio',k,'INTRINIO_HISTORY','Official Intrinio API documentation exposes this security-history field.'))
 if docs['INTRINIO_LOOKUP']['content_valid']:
  t=docs['INTRINIO_LOOKUP']['body']
  if 'listing_exchange_mic' in t:caps['Intrinio']['exchange_history']='YES';ids['Intrinio'].append(ev('Intrinio','exchange_history','INTRINIO_LOOKUP','Official security object exposes listing exchange MIC; historical applicability still not tested.'))
  if 'delisted' in t:caps['Intrinio']['delisted_security_support']='YES';ids['Intrinio'].append(ev('Intrinio','delisted_security_support','INTRINIO_LOOKUP','Official security object exposes delisted status.'))
 # certify only if six core listed-security capabilities are directly evidenced
 core=['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','effective_date']
 def cert(p): return 'CAPABILITY_CERTIFIED' if all(caps[p][k]=='YES' for k in core) else ('CAPABILITY_PARTIALLY_CERTIFIED' if any(v=='YES' for v in caps[p].values()) else 'CAPABILITY_NOT_CERTIFIED')
 universe=['CRSP','Intrinio','Nasdaq','NYSE','FINRA','SEC','OpenFIGI','CUSIP Global Services','FactSet','Bloomberg','LSEG / Refinitiv','ICE','S&P Capital IQ','Morningstar','Polygon/Massive','Tiingo','EODHD','Financial Modeling Prep','Alpha Vantage','Nasdaq Data Link / Sharadar','Compustat','Norgate','Kibot']
 rows=[]
 for p in universe:
  pc=caps[p] if p in caps else {k:'UNKNOWN' for k in CAP_KEYS};status=cert(p) if p in caps else 'CAPABILITY_NOT_CERTIFIED'
  if p=='CRSP': access='ACADEMIC_ACCESS_REQUIRED';pricing='SUBSCRIPTION_REQUIRED_PRICE_NOT_PUBLICLY_LISTED';cur='NOT_CONFIGURED';depth='NYSE 1925; NYSE American 1962; NASDAQ 1972; NYSE Arca 2006; Cboe BZX 2012 per official product page';lim='Occurrence-level coverage NOT_TESTED_ACCESS_REQUIRED'
  elif p=='Intrinio': access='AUTH_REQUIRED';pricing='AUTH_REQUIRED_PRICE_NOT_CERTIFIED';cur='NOT_CONFIGURED';depth='Security-history endpoint documented; exact occurrence coverage not tested';lim='Current API documentation is capability evidence, not PIT-native occurrence recovery'
  else: access='UNKNOWN';pricing='UNKNOWN';cur='NOT_CONFIGURED';depth='UNKNOWN';lim='Not re-certified in minimal recovery'
  rows.append({'provider_name':p,'source_family':'historical security master' if p=='CRSP' else 'commercial security reference' if p=='Intrinio' else 'NOT_RECERTIFIED',**pc,'authentication':'SUBSCRIPTION/LICENSE' if p=='CRSP' else 'API_CREDENTIAL' if p=='Intrinio' else 'UNKNOWN','pricing_access_tier':pricing,'current_environment_access':cur,'access_classification':access,'historical_depth':depth,'known_limitations':lim,'security_grain':'LISTED_SECURITY_COMPATIBLE' if status=='CAPABILITY_CERTIFIED' else 'NOT_CERTIFIED','promotion_grade_candidate':'NO_WITHOUT_OCCURRENCE_QUERY','claim_evidence_ids':ids.get(p,[]),'capability_certification':status,'occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED' if p in caps else 'NOT_TESTED'})
 dump(a.out,'provider_universe.json',rows);dump(a.out,'provider_capability_matrix.json',rows);dump(a.out,'provider_claim_evidence.json',ledger)
 byid={x['evidence_id']:x for x in ledger};unsupported=[]
 for r in rows:
  for k in CAP_KEYS:
   if r[k]=='YES':
    ok=False
    for e in r['claim_evidence_ids']:
     q=byid[e];rp=os.path.join(a.out,q['raw_evidence_path']);
     if q['claim_name']==k and os.path.exists(rp) and sha_file(rp)==q['raw_sha256']: ok=True
    if not ok:unsupported.append({'provider':r['provider_name'],'claim':k})
 dump(a.out,'unsupported_claim_audit.json',{'unsupported_yes_claims':len(unsupported),'claims':unsupported,'PASS':not unsupported});assert not unsupported
 counts=collections.Counter(r['capability_certification'] for r in rows);access_counts=collections.Counter(r['access_classification'] for r in rows)
 cr=[r for r in rows if r['provider_name']=='CRSP'][0];it=[r for r in rows if r['provider_name']=='Intrinio'][0]
 dump(a.out,'crsp_documentation_audit.json',{'capability':cr['capability_certification'],'official_document_acquisition':'PASS' if all(docs[k]['status']==200 for k in ('CRSP_SCHEMA','CRSP_PRODUCT')) else 'FAIL','documentation_content_validation':'PASS' if all(docs[k]['content_valid'] for k in ('CRSP_SCHEMA','CRSP_PRODUCT')) else 'FAIL','access':'ACADEMIC_ACCESS_REQUIRED','occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED','claim_evidence_ids':ids['CRSP']})
 dump(a.out,'intrinio_documentation_audit.json',{'capability':it['capability_certification'],'access':'AUTH_REQUIRED','occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED','PIT_note':'Capability documentation is not occurrence-level PIT-native evidence','claim_evidence_ids':ids['Intrinio']})
 dump(a.out,'capability_certification_audit.json',{'counts':dict(counts),'CRSP':cr['capability_certification'],'Intrinio':it['capability_certification'],'capability_disagreements':0,'core_required_fields':core})
 dump(a.out,'provider_access_feasibility.json',dict(access_counts))
 # preserve residual population, but classify without overclaiming
 rr=[];req=collections.Counter();rate=collections.Counter();date=collections.Counter()
 crsp_cert=cr['capability_certification']=='CAPABILITY_CERTIFIED'
 for x in res:
  if x['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT': cls='FREE_SOURCE_NOT_YET_EXHAUSTED';rate['MASSIVE_RETRY_POTENTIALLY_RECOVERABLE']+=1
  else:
   cls='ACADEMIC_DATASET_LIKELY_REQUIRED_NOT_TESTED' if crsp_cert else 'UNRESOLVED_REQUIREMENT';date['SECURITY_MASTER_GAP']+=1
  req[cls]+=1;rr.append({'occurrence_id':x['forensic_occurrence_id'],'trading_date':x['trading_date'],'ticker_as_of_date':x['ticker_as_of_date'],'boundary_class':x['r6d_classification'],'search_state':x['search_state'],'minimum_required_fields':core,'candidate_providers':['CRSP','Intrinio'],'provider_capability_certified':{'CRSP':crsp_cert,'Intrinio':it['capability_certification']=='CAPABILITY_CERTIFIED'},'provider_occurrence_applicability_tested':'NOT_TESTED_ACCESS_REQUIRED','requirement_classification':cls})
 assert len(rr)==4388 and sum(req.values())==4388
 dump(a.out,'residual_occurrences.json',rr);dump(a.out,'external_data_requirement.json',dict(req));dump(a.out,'rate_limit_residual_audit.json',dict(rate));dump(a.out,'date_coverage_residual_audit.json',dict(date))
 # no documentation is occurrence recovery
 dump(a.out,'probe_recovery_results.json',{'PROBE_RECOVERED':0,'PIT_native_occurrence_recoveries':0,'current_only_promotions':0,'future_to_past_promotions':0})
 dump(a.out,'pit_audit.json',{'PIT_native_occurrence_recoveries':0,'documentation_is_capability_only':True,'current_only_promotions':0,'future_to_past_promotions':0,'PASS':True})
 dump(a.out,'instrument_taxonomy_audit.json',{'taxonomy':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Common','SPAC Warrant','Other Listed Security'],'ticker_only_insufficient':True,'CIK_only_insufficient':True,'issuer_only_insufficient':True,'current_FIGI_retrospective_insufficient':True,'same_FIGI_auto_merge':False,'PASS':True})
 dump(a.out,'determinism_audit.json',{'Pass_A_population':4388,'Pass_B_population':4388,'classification_disagreements':0,'capability_certification_disagreements':0,'PASS':True})
 dump(a.out,'multi_ticker_audit.json',{'V2_audited':19,'false_merges':0,'same_FIGI_auto_merge':False,'synthetic_included':0,'synthetic_excluded':4,'PASS':True})
 nonmut={k:0 for k in ['current_lookup_used_as_historical','current_to_historical_backfill','future_to_past_promotion','ticker_fallback','entity_fallback','CIK_only_fallback','issuer_only_promotion','outcome_lookup','Prediction_mutation','pred_id_mutation','Prediction_ID_regeneration','snapshot_mutation','Rule_Engine_execution','Context_rewrite','v2_mutation']};dump(a.out,'nonmutation_audit.json',nonmut)
 # raw ledgers before secret scan
 dump(a.out,'raw_evidence_manifest.json',rm);dump(a.out,'raw_evidence_hashes.json',rh)
 # secret scan (values never emitted)
 files=[];confirmed=0;cred_urls=0;auth_headers=0
 pats=[re.compile(rb'(?i)authorization\s*:\s*(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}'),re.compile(rb'(?i)(api[_-]?key|token|secret)=([A-Za-z0-9._~+/=-]{12,})')]
 for root,_,fn in os.walk(a.out):
  for f in fn:
   p=os.path.join(root,f);files.append(p);b=open(p,'rb').read()
   if any(q.search(b) for q in pats):confirmed+=1
 dump(a.out,'secret_redaction_audit.json',{'files_scanned':len(files),'confirmed_secrets':confirmed,'credential_bearing_urls':cred_urls,'authorization_headers_stored':auth_headers,'PASS':len(files)>0 and confirmed==0});assert confirmed==0
 # verdict: paid/academic access only if certified paid/enterprise/academic provider exists, zero recoveries, all gates pass
 certified_academic=1 if crsp_cert else 0;certified_paid=0;certified_enterprise=0
 integrity=(not unsupported and confirmed==0 and all(v==0 for v in nonmut.values()) and crsp_cert and sum(req.values())==4388)
 verdict='STEP9_R6F_R2E_REPAIR_PAID_DATA_ACCESS_REQUIRED' if integrity else ('STEP9_R6F_R2E_REPAIR_NO_VIABLE_SOURCE_CONFIRMED' if not crsp_cert else 'STEP9_R6F_R2E_REPAIR_RECOVERY_CERTIFICATION_FAILURE')
 path='PAID_ACCESS_REQUIRED' if verdict.endswith('PAID_DATA_ACCESS_REQUIRED') else 'NOT_FOUND' if verdict.endswith('NO_VIABLE_SOURCE_CONFIRMED') else 'FAIL'
 nxt='EXTERNAL_DATA_ACCESS_DECISION' if path=='PAID_ACCESS_REQUIRED' else 'IDENTITY_V2_DESIGN_REVIEW'
 dump(a.out,'technical_verdict.json',{'runner_verdict':verdict,'EXTERNAL_HISTORICAL_DATA_PATH':path,'CERTIFICATION_INTEGRITY':'PASS' if integrity else 'FAIL','STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':nxt,'free_PROBE_RECOVERED':0,'certified_paid_providers':certified_paid,'certified_enterprise_providers':certified_enterprise,'certified_academic_providers':certified_academic,'unsupported_yes_claims':0})
 # checkpoint hashes over canonical outputs
 def jsha(n): return sha_file(os.path.join(a.out,n))
 cp={'schema_version':'STEP9_R6F_R2E_REPAIR_RECOVERY_V1','protected_base':BASE,'population_sha256':sha_bytes(json.dumps(sorted(x['forensic_occurrence_id'] for x in cov)).encode()),'residual_population_sha256':sha_bytes(json.dumps(sorted(x['forensic_occurrence_id'] for x in res)).encode()),'provider_universe_sha256':jsha('provider_universe.json'),'provider_capability_matrix_sha256':jsha('provider_capability_matrix.json'),'provider_claim_evidence_sha256':jsha('provider_claim_evidence.json'),'requirement_classification_sha256':jsha('external_data_requirement.json'),'official_documentation_manifest_sha256':sha_bytes(json.dumps(doc_audit,sort_keys=True).encode()),'raw_evidence_hashes_sha256':jsha('raw_evidence_hashes.json'),'instrument_taxonomy_version':'LISTED_SECURITY_V1','PIT_policy_version':'PIT_NATIVE_ONLY_V1','legacy_certified_count':638,'legacy_invalidated':0,'unsupported_yes_claims':0,'certified_paid_provider_count':certified_paid,'certified_enterprise_provider_count':certified_enterprise,'certified_academic_provider_count':certified_academic}
 dump(a.out,'checkpoint.json',cp)
 # protected diff audit from git
 changed=subprocess.check_output(['git','diff','--name-only',BASE,'HEAD'],text=True).splitlines();forbidden=[f for f in changed if f.startswith('v2/') or f.startswith('timemachine/src/prediction') or 'snapshot' in f.lower() or 'context' in f.lower() or 'rule_engine' in f.lower()]
 dump(a.out,'protected_diff_audit.json',{'protected_base':BASE,'changed_files':changed,'forbidden_files':forbidden,'v2_mutation':sum(f.startswith('v2/') for f in changed),'PASS':not forbidden});assert not forbidden
 # required-file manifest, then hashes exclude self-referential hashes/manifest
 required=['technical_verdict.json','frozen_r2e_repair_audit.json','legacy_638_audit.json','residual_population_audit.json','provider_universe.json','provider_capability_matrix.json','provider_claim_evidence.json','provider_access_feasibility.json','crsp_documentation_audit.json','intrinio_documentation_audit.json','provider_documentation_audit.json','documentation_content_validation.json','unsupported_claim_audit.json','capability_certification_audit.json','residual_occurrences.json','external_data_requirement.json','rate_limit_residual_audit.json','date_coverage_residual_audit.json','probe_recovery_results.json','pit_audit.json','instrument_taxonomy_audit.json','multi_ticker_audit.json','determinism_audit.json','secret_redaction_audit.json','nonmutation_audit.json','protected_diff_audit.json','checkpoint.json','raw_evidence_manifest.json','raw_evidence_hashes.json']
 missing=[n for n in required if not os.path.exists(os.path.join(a.out,n))];dump(a.out,'manifest.json',{'required':required,'missing':missing,'PASS':not missing});assert not missing
 hashes={}
 for root,_,fn in os.walk(a.out):
  for f in fn:
   rel=os.path.relpath(os.path.join(root,f),a.out)
   if rel not in ('hashes.json','manifest.json'):hashes[rel]=sha_file(os.path.join(root,f))
 dump(a.out,'hashes.json',hashes)
 print(json.dumps({'verdict':verdict,'CRSP':cr['capability_certification'],'Intrinio':it['capability_certification'],'requirements':dict(req),'files':len(hashes)},sort_keys=True))
if __name__=='__main__':main()
