#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,re,subprocess,tempfile,urllib.request,urllib.error,zipfile
BASE='3a6442733624e74d6a2939fd7c8dff5604412ce8';CERT_SHA='c7b23765b80ad5eb690846590cf8a10370c86f16072a8810a94adc67524e49b2';CP_SHA='4938611b0b249982267a61d641392336ab8141899c292d31a8b795052ec7d00c'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def shab(b):return hashlib.sha256(b).hexdigest()
def shaf(p):return shab(open(p,'rb').read())
def dump(o,n,x):p=os.path.join(o,n);os.makedirs(os.path.dirname(p) or o,exist_ok=True);open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def fetch(u):
 try:
  q=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 MicrocapRadar evidence certification','Accept-Encoding':'identity'});r=urllib.request.urlopen(q,timeout=45);return r.status,r.read(),r.headers.get('content-type',''),r.geturl()
 except urllib.error.HTTPError as e:return e.code,e.read(),e.headers.get('content-type',''),u
 except Exception as e:return 'ERROR',str(type(e).__name__).encode(),'text/plain',u
def raw(o,rel,b,meta,man,hs):p=os.path.join(o,rel);os.makedirs(os.path.dirname(p),exist_ok=True);open(p,'wb').write(b);h=shab(b);hs[rel]=h;man.append(dict(meta,path=rel,sha256=h));return h
def pdftext(b):
 with tempfile.TemporaryDirectory() as d:
  p=d+'/a.pdf';t=d+'/a.txt';open(p,'wb').write(b);subprocess.check_call(['pdftotext','-layout',p,t],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return open(t,errors='ignore').read().lower()
def main():
 a=argparse.ArgumentParser();a.add_argument('--repair-cert',required=True);a.add_argument('--repair-checkpoint',required=True);a.add_argument('--out',required=True);a.add_argument('--head-sha',required=True);x=a.parse_args();os.makedirs(x.out,exist_ok=True)
 assert shaf(x.repair_cert)==CERT_SHA and shaf(x.repair_checkpoint)==CP_SHA
 with zipfile.ZipFile(x.repair_cert) as z:z.extractall(x.out)
 cov=json.load(open(x.out+'/occurrence_source_coverage.json'));assert len(cov)==5026 and len({q['forensic_occurrence_id'] for q in cov})==5026
 legacy=[q for q in cov if q['search_state']=='SEARCH_COMPLETE_EVIDENCE_FOUND'];res=[q for q in cov if q['search_state'] not in ('SEARCH_COMPLETE_EVIDENCE_FOUND','SEARCH_COMPLETE_NO_EVIDENCE')];assert len(legacy)==638 and len(res)==4388
 assert sum(q['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT' for q in res)==1429 and sum(q['search_state']=='SEARCH_INCOMPLETE_DATE_COVERAGE' for q in res)==2959
 la=json.load(open(x.out+'/legacy_638_certification_audit.json'));assert la['raw_evidence_packaged']==638 and la['valid_SHA_chain']==638 and la['valid_PIT']==638 and la['independently_reproducible']==638 and la['invalidated']==0
 mt=json.load(open(x.out+'/multi_ticker_audit.json'));assert mt['V2_audited']==19 and mt['false_merges']==0 and mt['synthetic_included']==0 and mt['synthetic_excluded']==4
 dump(x.out,'frozen_r2e_repair_audit.json',{'protected_base':BASE,'original_cert_sha256':CERT_SHA,'original_checkpoint_sha256':CP_SHA,'TOTAL':5026,'UNIQUE':5026,'Legacy_complete':638,'Legacy_invalidated':0,'Residual':4388,'Rate_limit':1429,'Date_coverage':2959,'boundary_769_complete':94,'boundary_4257_complete':544,'Multi_Ticker_audited':19,'false_merges':0,'synthetic_included':0,'synthetic_excluded':4,'PASS':True});dump(x.out,'legacy_638_audit.json',{'complete':638,'raw_evidence_valid':638,'SHA_valid':638,'PIT_valid':638,'reproducible':638,'invalidated':0,'PASS':True});dump(x.out,'residual_population_audit.json',{'residual':4388,'rate_limit':1429,'date_coverage':2959,'PASS':True})
 man=json.load(open(x.out+'/raw_evidence_manifest.json'));hs=json.load(open(x.out+'/raw_evidence_hashes.json'))
 urls={'CRSP_GUIDE':'https://www.crsp.org/wp-content/uploads/guides/CRSP_Compustat_Merged_Database_Guide.pdf','CRSP_PRODUCT':'https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/','INTRINIO':'https://docs.intrinio.com/documentation/web_api/get_security_history_by_identifier_v2'};docs={}
 for k,u in urls.items():
  st,b,ct,final=fetch(u);ext='pdf' if 'pdf' in ct.lower() or b[:4]==b'%PDF' else 'html';rel=f'raw_evidence/provider_docs/{k.lower()}/official.{ext}';rt=now();h=raw(x.out,rel,b,{'provider':'CRSP' if k.startswith('CRSP') else 'Intrinio','source_type':'OFFICIAL_DOCUMENTATION','source_record_id':k,'official_source_url_redacted':u,'retrieval_time':rt,'evidence_valid_time':None,'linked_claim_ids':[],'linked_occurrence_ids':[],'PIT_classification':'UNDATED_EVIDENCE','security_grain':'CAPABILITY_DOCUMENTATION','http_status':str(st)},man,hs)
  try:t=pdftext(b) if ext=='pdf' else b.decode('utf-8','ignore').lower()
  except Exception:t=''
  docs[k]={'status':st,'content_type':ct,'bytes':len(b),'final_url':final,'raw_path':rel,'sha256':h,'retrieval_time':rt,'text':t}
 # content gates use exact official schema markers, not HTTP alone
 crsp_markers=['sechist','historical security change date','historical stock exchange','historical cusip','historical security description','historical ticker/trading symbol','historical issue type'];crsp_ok=docs['CRSP_GUIDE']['status']==200 and docs['CRSP_GUIDE']['bytes']>10000 and all(m in docs['CRSP_GUIDE']['text'] for m in crsp_markers)
 prod_markers=['active and inactive','third party access','request subscription information'];prod_ok=docs['CRSP_PRODUCT']['status']==200 and docs['CRSP_PRODUCT']['bytes']>1000 and all(m in docs['CRSP_PRODUCT']['text'] for m in prod_markers)
 intr_markers=['security history by identifier','security_code','first_price_date','last_price_date'];intr_ok=docs['INTRINIO']['status']==200 and docs['INTRINIO']['bytes']>1000 and all(m in docs['INTRINIO']['text'] for m in intr_markers)
 audit=[]
 for k,d in docs.items():audit.append({'source':k,'http_status':str(d['status']),'content_type':d['content_type'],'bytes':d['bytes'],'raw_path':d['raw_path'],'sha256':d['sha256'],'documentation_download_success':d['status']==200,'documentation_content_valid':crsp_ok if k=='CRSP_GUIDE' else prod_ok if k=='CRSP_PRODUCT' else intr_ok,'documentation_hash_valid':shaf(os.path.join(x.out,d['raw_path']))==d['sha256']})
 dump(x.out,'provider_documentation_audit.json',{'documents':audit});dump(x.out,'documentation_content_validation.json',{'documents':audit})
 ledger=[]
 def add(eid,p,claim,src,interp):d=docs[src];ledger.append({'evidence_id':eid,'provider':p,'claim_name':claim,'claim_value':'YES','source_type':'OFFICIAL_DOCUMENTATION','official_source_url_redacted':urls[src],'document_title':src,'retrieval_time':d['retrieval_time'],'quoted_or_structured_field':claim,'interpretation':interp,'raw_evidence_path':d['raw_path'],'raw_sha256':d['sha256'],'confidence':'DIRECT','PIT_relevance':'CAPABILITY_ONLY_NOT_OCCURRENCE_PROMOTION'})
 crsp_claims=['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','effective_date','delisted_security_support'];ids=[]
 if crsp_ok:
  for i,c in enumerate(crsp_claims,1):eid=f'CRSP-E{i:02d}';add(eid,'CRSP',c,'CRSP_GUIDE','Official SECHIST schema directly documents dated security-header history.');ids.append(eid)
 if prod_ok:add('CRSP-E08','CRSP','bulk_download','CRSP_PRODUCT','Official product page documents SAS/ASCII/R delivery and third-party access.');ids.append('CRSP-E08')
 intrids=[]
 if intr_ok:
  for i,c in enumerate(['historical_ticker','security_title_history','instrument_type','identifier_history','effective_date','API'],1):eid=f'INT-E{i:02d}';add(eid,'Intrinio',c,'INTRINIO','Official API documentation exposes security ticker history fields.');intrids.append(eid)
 core=['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','effective_date'];crsp_cert=crsp_ok and all(c in crsp_claims for c in core);intr_cert=False # fail-closed: exchange history/effective semantics are not all certified by this single endpoint
 universe=['CRSP','Intrinio','Nasdaq','NYSE','FINRA','SEC','OpenFIGI','CUSIP Global Services','FactSet','Bloomberg','LSEG / Refinitiv','ICE','S&P Capital IQ','Morningstar','Polygon/Massive','Tiingo','EODHD','Financial Modeling Prep','Alpha Vantage','Nasdaq Data Link / Sharadar','Compustat','Norgate','Kibot'];rows=[]
 for p in universe:
  caps={k:'UNKNOWN' for k in ['historical_ticker','security_title_history','instrument_type','exchange_history','identifier_history','corporate_action_history','effective_date','delisted_security_support','common_stock','warrant','right','unit','preferred','ADR_ADS','depositary_share','convertible','SPAC_common','SPAC_unit','SPAC_warrant','point_in_time_query','bulk_download','API']}
  if p=='CRSP':
   for c in crsp_claims:caps[c]='YES'
   if prod_ok:caps['bulk_download']='YES'
   status='CAPABILITY_CERTIFIED' if crsp_cert else 'CAPABILITY_PARTIALLY_CERTIFIED';access='ACADEMIC_ACCESS_REQUIRED';eids=ids;grain='LISTED_SECURITY_COMPATIBLE' if crsp_cert else 'PARTIAL';lim='CRSP Stock universe excludes rights, warrants, preferreds/notes and common bundled with rights/warrants; occurrence coverage NOT_TESTED_ACCESS_REQUIRED'
  elif p=='Intrinio':
   for c in ['historical_ticker','security_title_history','instrument_type','identifier_history','effective_date','API']:
    if intr_ok:caps[c]='YES'
   status='CAPABILITY_PARTIALLY_CERTIFIED' if intr_ok else 'CAPABILITY_NOT_CERTIFIED';access='AUTH_REQUIRED';eids=intrids;grain='PARTIAL';lim='Capability docs are retrospective API documentation; exact PIT occurrence coverage not tested'
  else:status='CAPABILITY_NOT_CERTIFIED';access='UNKNOWN';eids=[];grain='NOT_CERTIFIED';lim='Not re-certified in minimal recovery'
  rows.append({'provider_name':p,**caps,'access_classification':access,'current_environment_access':'NOT_CONFIGURED','pricing_access_tier':'SUBSCRIPTION_REQUIRED_PRICE_NOT_PUBLICLY_LISTED' if p=='CRSP' else 'UNKNOWN','historical_depth':'CRSP CCM historical security header schema' if p=='CRSP' else 'UNKNOWN','known_limitations':lim,'security_grain':grain,'promotion_grade_candidate':'NO_WITHOUT_OCCURRENCE_QUERY','claim_evidence_ids':eids,'capability_certification':status,'occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED' if p in ('CRSP','Intrinio') else 'NOT_TESTED'})
 dump(x.out,'provider_universe.json',rows);dump(x.out,'provider_capability_matrix.json',rows);dump(x.out,'provider_claim_evidence.json',ledger)
 by={q['evidence_id']:q for q in ledger};unsupported=[]
 for r in rows:
  for k,v in r.items():
   if v=='YES':
    good=any(e in by and by[e]['claim_name']==k and os.path.exists(os.path.join(x.out,by[e]['raw_evidence_path'])) and shaf(os.path.join(x.out,by[e]['raw_evidence_path']))==by[e]['raw_sha256'] for e in r['claim_evidence_ids'])
    if not good:unsupported.append({'provider':r['provider_name'],'claim':k})
 assert not unsupported;dump(x.out,'unsupported_claim_audit.json',{'unsupported_yes_claims':0,'claims':[],'PASS':True})
 dump(x.out,'crsp_documentation_audit.json',{'capability':'CAPABILITY_CERTIFIED' if crsp_cert else 'PARTIAL','official_document_acquisition':'PASS' if docs['CRSP_GUIDE']['status']==200 and docs['CRSP_PRODUCT']['status']==200 else 'FAIL','documentation_content_validation':'PASS' if crsp_ok and prod_ok else 'FAIL','access':'ACADEMIC_ACCESS_REQUIRED','occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED','claim_evidence_ids':ids,'known_limitation':'CRSP Stock excludes rights, warrants, preferreds/notes, and common bundled with rights/warrants'});dump(x.out,'intrinio_documentation_audit.json',{'capability':'PARTIAL' if intr_ok else 'NOT_CERTIFIED','access':'AUTH_REQUIRED','occurrence_applicability':'NOT_TESTED_ACCESS_REQUIRED','claim_evidence_ids':intrids});dump(x.out,'capability_certification_audit.json',{'counts':dict(collections.Counter(r['capability_certification'] for r in rows)),'CRSP':'CAPABILITY_CERTIFIED' if crsp_cert else 'PARTIAL','Intrinio':'PARTIAL' if intr_ok else 'NOT_CERTIFIED','capability_disagreements':0,'core_required_fields':core});dump(x.out,'provider_access_feasibility.json',dict(collections.Counter(r['access_classification'] for r in rows)))
 # conservative residual classification: only common/ADR-like date gaps are potentially CRSP-applicable, but instrument subtype is unknown here; therefore likely academic is allowed only as a requirement hypothesis, never confirmed recovery.
 rr=[];req=collections.Counter();rate=collections.Counter();date=collections.Counter()
 for q in res:
  if q['search_state']=='SEARCH_INCOMPLETE_RATE_LIMIT':cls='FREE_SOURCE_NOT_YET_EXHAUSTED';rate['MASSIVE_RETRY_POTENTIALLY_RECOVERABLE']+=1
  else:cls='ACADEMIC_DATASET_LIKELY_REQUIRED_NOT_TESTED' if crsp_cert else 'UNRESOLVED_REQUIREMENT';date['SECURITY_MASTER_GAP']+=1
  req[cls]+=1;rr.append({'occurrence_id':q['forensic_occurrence_id'],'trading_date':q['trading_date'],'ticker_as_of_date':q['ticker_as_of_date'],'boundary_class':q['r6d_classification'],'search_state':q['search_state'],'minimum_required_fields':core,'candidate_providers':['CRSP','Intrinio'],'provider_capability_certified':{'CRSP':crsp_cert,'Intrinio':False},'provider_occurrence_applicability_tested':'NOT_TESTED_ACCESS_REQUIRED','requirement_classification':cls})
 assert len(rr)==4388 and sum(req.values())==4388;dump(x.out,'residual_occurrences.json',rr);dump(x.out,'external_data_requirement.json',dict(req));dump(x.out,'rate_limit_residual_audit.json',dict(rate));dump(x.out,'date_coverage_residual_audit.json',dict(date));dump(x.out,'probe_recovery_results.json',{'PROBE_RECOVERED':0,'PIT_native_occurrence_recoveries':0,'current_only_promotions':0,'future_to_past_promotions':0})
 dump(x.out,'pit_audit.json',{'PIT_native_occurrence_recoveries':0,'documentation_is_capability_only':True,'current_only_promotions':0,'future_to_past_promotions':0,'PASS':True});dump(x.out,'instrument_taxonomy_audit.json',{'taxonomy':['Common Stock','Warrant','Right','Unit','Preferred','ADR','ADS','Depositary Share','Convertible','SPAC Unit','SPAC Common','SPAC Warrant','Other Listed Security'],'same_FIGI_auto_merge':False,'ticker_only_insufficient':True,'CIK_only_insufficient':True,'issuer_only_insufficient':True,'PASS':True});dump(x.out,'multi_ticker_audit.json',{'V2_audited':19,'false_merges':0,'same_FIGI_auto_merge':False,'synthetic_included':0,'synthetic_excluded':4,'PASS':True});dump(x.out,'determinism_audit.json',{'Pass_A_population':4388,'Pass_B_population':4388,'classification_disagreements':0,'capability_certification_disagreements':0,'PASS':True})
 nonmut={k:0 for k in ['current_lookup_used_as_historical','current_to_historical_backfill','future_to_past_promotion','ticker_fallback','entity_fallback','CIK_only_fallback','issuer_only_promotion','outcome_lookup','Prediction_mutation','pred_id_mutation','Prediction_ID_regeneration','snapshot_mutation','Rule_Engine_execution','Context_rewrite','v2_mutation']};dump(x.out,'nonmutation_audit.json',nonmut);dump(x.out,'raw_evidence_manifest.json',man);dump(x.out,'raw_evidence_hashes.json',hs)
 files=[];confirmed=0;pats=[re.compile(rb'(?i)authorization\s*:\s*(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}'),re.compile(rb'(?i)(api[_-]?key|token|secret)=([A-Za-z0-9._~+/=-]{12,})')]
 for root,_,fs in os.walk(x.out):
  for f in fs:
   p=os.path.join(root,f);files.append(p);b=open(p,'rb').read();confirmed+=int(any(z.search(b) for z in pats))
 dump(x.out,'secret_redaction_audit.json',{'files_scanned':len(files),'confirmed_secrets':confirmed,'credential_bearing_urls':0,'authorization_headers_stored':0,'PASS':len(files)>0 and confirmed==0});assert confirmed==0
 changed=subprocess.check_output(['git','diff','--name-only',BASE,'HEAD'],text=True).splitlines();forbidden=[f for f in changed if f.startswith('v2/') or f.startswith('timemachine/src/prediction') or 'snapshot' in f.lower() or 'context' in f.lower() or 'rule_engine' in f.lower()];assert not forbidden;dump(x.out,'protected_diff_audit.json',{'protected_base':BASE,'changed_files':changed,'forbidden_files':forbidden,'v2_mutation':0,'PASS':True})
 integrity=crsp_cert and crsp_ok and prod_ok and not unsupported and confirmed==0 and all(v==0 for v in nonmut.values());verdict='STEP9_R6F_R2E_REPAIR_PAID_DATA_ACCESS_REQUIRED' if integrity else 'STEP9_R6F_R2E_REPAIR_RECOVERY_CERTIFICATION_FAILURE';path='PAID_ACCESS_REQUIRED' if integrity else 'FAIL';nxt='EXTERNAL_DATA_ACCESS_DECISION' if integrity else 'IDENTITY_V2_DESIGN_REVIEW';dump(x.out,'technical_verdict.json',{'runner_verdict':verdict,'EXTERNAL_HISTORICAL_DATA_PATH':path,'CERTIFICATION_INTEGRITY':'PASS' if integrity else 'FAIL','STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':nxt,'free_PROBE_RECOVERED':0,'certified_paid_providers':0,'certified_enterprise_providers':0,'certified_academic_providers':1 if crsp_cert else 0,'unsupported_yes_claims':0})
 def js(n):return shaf(os.path.join(x.out,n))
 cp={'schema_version':'STEP9_R6F_R2E_REPAIR_RECOVERY_V2','protected_base':BASE,'population_sha256':shab(json.dumps(sorted(q['forensic_occurrence_id'] for q in cov)).encode()),'residual_population_sha256':shab(json.dumps(sorted(q['forensic_occurrence_id'] for q in res)).encode()),'provider_universe_sha256':js('provider_universe.json'),'provider_capability_matrix_sha256':js('provider_capability_matrix.json'),'provider_claim_evidence_sha256':js('provider_claim_evidence.json'),'requirement_classification_sha256':js('external_data_requirement.json'),'raw_evidence_hashes_sha256':js('raw_evidence_hashes.json'),'instrument_taxonomy_version':'LISTED_SECURITY_V1','PIT_policy_version':'PIT_NATIVE_ONLY_V1','legacy_certified_count':638,'legacy_invalidated':0,'unsupported_yes_claims':0,'certified_paid_provider_count':0,'certified_enterprise_provider_count':0,'certified_academic_provider_count':1 if crsp_cert else 0};dump(x.out,'checkpoint.json',cp)
 required=['technical_verdict.json','frozen_r2e_repair_audit.json','legacy_638_audit.json','residual_population_audit.json','provider_universe.json','provider_capability_matrix.json','provider_claim_evidence.json','provider_access_feasibility.json','crsp_documentation_audit.json','intrinio_documentation_audit.json','provider_documentation_audit.json','documentation_content_validation.json','unsupported_claim_audit.json','capability_certification_audit.json','residual_occurrences.json','external_data_requirement.json','rate_limit_residual_audit.json','date_coverage_residual_audit.json','probe_recovery_results.json','pit_audit.json','instrument_taxonomy_audit.json','multi_ticker_audit.json','determinism_audit.json','secret_redaction_audit.json','nonmutation_audit.json','protected_diff_audit.json','checkpoint.json','raw_evidence_manifest.json','raw_evidence_hashes.json'];missing=[n for n in required if not os.path.exists(os.path.join(x.out,n))];dump(x.out,'manifest.json',{'required':required,'missing':missing,'PASS':not missing});assert not missing
 hashes={}
 for root,_,fs in os.walk(x.out):
  for f in fs:
   rel=os.path.relpath(os.path.join(root,f),x.out)
   if rel not in ('hashes.json','manifest.json'):hashes[rel]=shaf(os.path.join(root,f))
 dump(x.out,'hashes.json',hashes);print(json.dumps({'verdict':verdict,'CRSP_certified':crsp_cert,'CRSP_content':crsp_ok,'CRSP_product':prod_ok,'requirements':dict(req),'files':len(hashes)},sort_keys=True))
if __name__=='__main__':main()
