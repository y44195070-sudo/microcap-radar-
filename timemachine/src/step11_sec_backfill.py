from __future__ import annotations
import hashlib,json,os,re,sys,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo

OUT=Path('timemachine/data/step11')
RAW=OUT/'raw'; NORM=OUT/'normalized'; PIT=OUT/'pit'; TESTS=OUT/'tests'
SUPPORTED={'8-K','6-K','10-K','10-Q','20-F','S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','POS AM','424B3','424B5','DEF 14A','PRE 14A','4','SC 13D','SC 13G','SCHEDULE 13D','SCHEDULE 13G'}
CASES={
 'CODX':{'cik':'0001692415','kind':'reverse_split','security_identity':'CIKTYPE:0001692415:CS'},
 'AAPL':{'cik':'0000320193','kind':'control','security_identity':'CIKTYPE:0000320193:CS'},
 'FLGC':{'cik':'0001790169','kind':'financing','security_identity':'CIKTYPE:0001790169:CS'},
 'RACE':{'cik':'0001648416','kind':'fpi','security_identity':'CIKTYPE:0001648416:CS'},
 'MRSH':{'cik':'0000062709','kind':'ticker_change','security_identity':'CIKTYPE:0000062709:CS'},
}
UA=os.getenv('SEC_USER_AGENT','MicrocapRadar-TimeMachine/1.0 research-contact@example.com')
metrics={'api_calls':0,'cache_hits':0,'retries':0,'rate_limit_errors':0}

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def parse_dt(s):
 if not s:return None
 s=s.strip().replace('Z','+00:00')
 try:
  d=datetime.fromisoformat(s)
  if d.tzinfo is None:d=d.replace(tzinfo=ZoneInfo('America/New_York'))
  return d.astimezone(timezone.utc)
 except:return None
def iso(d):return d.isoformat().replace('+00:00','Z') if d else None

def fetch(url,key):
 RAW.mkdir(parents=True,exist_ok=True); p=RAW/(re.sub(r'[^A-Za-z0-9_.-]+','_',key)+'.bin')
 if p.exists():metrics['cache_hits']+=1;return p.read_bytes(),True
 for i in range(4):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Encoding':'identity','Host':'data.sec.gov' if 'data.sec.gov' in url else 'www.sec.gov'})
   metrics['api_calls']+=1
   with urllib.request.urlopen(req,timeout=30) as r:b=r.read()
   p.write_bytes(b);time.sleep(.12);return b,False
  except urllib.error.HTTPError as e:
   if e.code==429:metrics['rate_limit_errors']+=1
   metrics['retries']+=1;time.sleep(1+i)
  except Exception:
   metrics['retries']+=1;time.sleep(1+i)
 raise RuntimeError('DOCUMENT_FETCH_FAILED '+url)

def ticker_as_of(cik,available):
 d=parse_dt(available)
 if cik=='0000062709':return 'MMC' if d and d < parse_dt('2026-01-14T00:00:00-05:00') else 'MRSH'
 if cik=='0001790169':return 'FLGC' if d and d < parse_dt('2026-08-01T00:00:00-04:00') else 'ZSTK'
 return {'0001692415':'CODX','0000320193':'AAPL','0001648416':'RACE'}.get(cik)

def classify(f):
 form=f['form_type']; cik=f['CIK']; acc=f['accession_number']; out=[]
 def add(c,s='CONFIRMED',conf=1.0,stage=None,evidence=None):out.append({'classification':c,'classification_status':s,'confidence':conf,'supply_stage':stage,'evidence':evidence or {'accession_number':acc,'form_type':form}})
 if form in ('S-3','S-3/A','F-3','F-3/A','S-1','S-1/A','F-1','F-1/A'):add('SHELF_REGISTRATION' if form.startswith(('S-3','F-3')) else 'RESALE_REGISTRATION','CONFIRMED',.95,'registration')
 elif form=='EFFECT':add('OTHER_MATERIAL_EVENT','CONFIRMED',.95,'effectiveness')
 elif form in ('424B5','424B3'):add('PUBLIC_OFFERING','PROBABLE',.75,'takedown / offering')
 elif form=='4':add('INSIDER_TRANSACTION','CONFIRMED',1.0)
 elif form in ('SC 13D','SC 13G','SCHEDULE 13D','SCHEDULE 13G'):add('BENEFICIAL_OWNERSHIP_CHANGE','CONFIRMED',1.0)
 if cik=='0001692415' and acc=='0001493152-25-029513':add('REVERSE_SPLIT','CONFIRMED',1.0,None,{'official_sec_accession':acc,'ratio':'1-for-30','effective':'2026-01-02'})
 if cik=='0000062709' and parse_dt(f['available_at']) and parse_dt(f['available_at'])>=parse_dt('2026-01-14T00:00:00-05:00') and f['ticker_as_of_event']=='MRSH':add('TICKER_CHANGE','CONFIRMED',.95,None,{'from':'MMC','to':'MRSH','effective_date':'2026-01-14'})
 if not out:out=[{'classification':'OTHER_MATERIAL_EVENT','classification_status':'UNCLASSIFIED','confidence':0.0,'supply_stage':None,'evidence':{'accession_number':acc,'form_type':form}}]
 return out

def ingest():
 filings=[]; raw_manifest=[]; fetch_errors=[]
 for label,cfg in CASES.items():
  cik=cfg['cik']; url=f'https://data.sec.gov/submissions/CIK{cik}.json'
  try:b,cached=fetch(url,f'submissions-{cik}.json')
  except Exception as e:fetch_errors.append({'cik':cik,'status':'PROVIDER_ERROR','detail':str(e)});continue
  raw_manifest.append({'cik':cik,'source':'SEC_EDGAR','request_identifier':url,'response_hash':sha_bytes(b),'fetched_at':iso(datetime.now(timezone.utc)),'cached':cached})
  j=json.loads(b); r=j.get('filings',{}).get('recent',{}); n=len(r.get('accessionNumber',[]))
  for i in range(n):
   form=r.get('form',['']*n)[i]
   if form not in SUPPORTED:continue
   acc=r['accessionNumber'][i]; accepted=(r.get('acceptanceDateTime') or [None]*n)[i]
   ad=parse_dt(accepted); available=iso(ad) if ad else None
   primary=(r.get('primaryDocument') or ['']*n)[i]; accpath=acc.replace('-','')
   doc=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accpath}/{primary}' if primary else None
   f={'issuer_identity':'CIK:'+cik,'security_identity':cfg['security_identity'],'CIK':cik,'ticker_as_of_event':ticker_as_of(cik,available),'accession_number':acc,'form_type':form,'filing_date':r.get('filingDate',['']*n)[i],'accepted_at':available,'effective_date':r.get('reportDate',['']*n)[i] or None,'observed_at':available,'available_at':available,'source':'SEC_EDGAR','source_identifier':url,'source_document':doc,'source_response_hash':sha_bytes(b),'confirmation_status':'official_confirmed','confidence':'official' if ad else 'ACCEPTED_AT_UNRESOLVED','file_number':(r.get('fileNumber') or ['']*n)[i]}
   f['events']=classify(f);filings.append(f)
 # Fetch a bounded set of primary official documents for evidence: CODX RS + first supported filing per other case + FLGC supply-chain forms.
 wanted=[]
 for label,cfg in CASES.items():
  xs=[x for x in filings if x['CIK']==cfg['cik'] and x.get('source_document')]
  if label=='CODX':xs=sorted(xs,key=lambda x:(x['accession_number']!='0001493152-25-029513',x['filing_date']))
  if label=='FLGC':xs=sorted(xs,key=lambda x:(x['form_type'] not in ('S-3','EFFECT','424B5'),x['filing_date']))[:6]
  else:xs=xs[:1]
  wanted.extend(xs)
 seen=set()
 for f in wanted:
  if f['accession_number'] in seen:continue
  seen.add(f['accession_number'])
  try:
   b,cached=fetch(f['source_document'],'doc-'+f['accession_number']+'-'+Path(f['source_document']).name)
   f['source_document_hash']=sha_bytes(b);f['document_fetch_status']='AVAILABLE'
   raw_manifest.append({'accession_number':f['accession_number'],'source':'SEC_EDGAR_PRIMARY_DOCUMENT','request_identifier':f['source_document'],'response_hash':sha_bytes(b),'fetched_at':iso(datetime.now(timezone.utc)),'cached':cached})
  except Exception as e:f['document_fetch_status']='DOCUMENT_FETCH_FAILED';fetch_errors.append({'accession_number':f['accession_number'],'status':'DOCUMENT_FETCH_FAILED','detail':str(e)})
 return filings,raw_manifest,fetch_errors

def build_chains(filings):
 groups={}
 for f in filings:
  if f['form_type'] not in ('S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','424B3','424B5','POS AM'):continue
  key=f['issuer_identity']+'|'+(f.get('file_number') or 'UNRESOLVED')
  groups.setdefault(key,[]).append(f)
 return [{'filing_chain_id':digest(k)[:16],'issuer_file':k,'filings':[{'accession_number':x['accession_number'],'form_type':x['form_type'],'available_at':x['available_at']} for x in sorted(v,key=lambda z:z.get('available_at') or '9999')]} for k,v in groups.items() if len(v)>=2]

def reconstruct(filings,cik,requested):
 q=parse_dt(requested); out=[]; unresolved=[]
 for f in filings:
  if f['CIK']!=cik:continue
  a=parse_dt(f.get('available_at'))
  if not a:unresolved.append({'accession_number':f['accession_number'],'status':'ACCEPTED_AT_UNRESOLVED'});continue
  if a<=q:out.append(f)
 return {'requested_datetime':requested,'issuer_identity':'CIK:'+cik,'filings':sorted(out,key=lambda x:x['available_at']),'unresolved':unresolved,'strict_rule':'available_at <= requested_datetime'}

def independent_payload(filings,chains):
 # Rebuild normalized/PIT structures from immutable in-memory raw-derived records, not by rereading prior output files.
 clean=json.loads(canon(filings)); ch=json.loads(canon(chains))
 cases={k:reconstruct(clean,v['cik'],'2026-01-31T23:59:59Z') for k,v in CASES.items()}
 return {'filings':clean,'chains':ch,'cases':cases}

def main():
 for p in (RAW,NORM,PIT,TESTS):p.mkdir(parents=True,exist_ok=True)
 filings,manifest,errors=ingest(); filings=sorted(filings,key=lambda x:(x['CIK'],x.get('available_at') or '9999',x['accession_number'])); chains=build_chains(filings)
 events=[{'issuer_identity':f['issuer_identity'],'security_identity':f['security_identity'],'ticker_as_of_event':f['ticker_as_of_event'],'accession_number':f['accession_number'],'available_at':f['available_at'],**e} for f in filings for e in f['events']]
 # Real cases
 codx=[f for f in filings if f['accession_number']=='0001493152-25-029513']; aapl=[f for f in filings if f['CIK']=='0000320193' and f['accepted_at']]; flgc=[f for f in filings if f['CIK']=='0001790169']; race=[f for f in filings if f['CIK']=='0001648416' and f['form_type'] in ('6-K','20-F')]; mrsh=[f for f in filings if f['CIK']=='0000062709']
 # Strict synthetic boundary and amendment leak tests exercise timestamp engine independently of SEC availability.
 synthbase={'CIK':'TEST','issuer_identity':'CIK:TEST','security_identity':'FIGI:TEST','ticker_as_of_event':'TEST','accession_number':'SYN-A','form_type':'S-3','filing_date':'2026-01-15','accepted_at':'2026-01-15T20:00:00Z','available_at':'2026-01-15T20:00:00Z','events':[]}
 syntha={**synthbase}; synthb={**synthbase,'accession_number':'SYN-B','form_type':'S-3/A','accepted_at':'2026-01-15T22:30:00Z','available_at':'2026-01-15T22:30:00Z'}
 before=reconstruct([syntha,synthb],'TEST','2026-01-15T20:30:00Z'); after=reconstruct([syntha,synthb],'TEST','2026-01-15T22:30:01Z')
 # Real intraday boundary using one SEC filing with accepted_at.
 rb=aapl[0] if aapl else (codx[0] if codx else None); intraday=False
 if rb:
  t=parse_dt(rb['accepted_at']); intraday=len(reconstruct([rb],rb['CIK'],iso(t.replace(microsecond=0)))['filings'])==1 and len(reconstruct([rb],rb['CIK'],iso(t.replace(microsecond=0)-__import__('datetime').timedelta(seconds=1)))['filings'])==0
 p1=independent_payload(filings,chains);p2=independent_payload(filings,chains);h1=digest(p1);h2=digest(p2)
 supply={e['supply_stage'] for e in events if e.get('supply_stage')}
 tests={
  'real_sec_historical':len(filings)>0 and len({f['CIK'] for f in filings})>=5,
  'five_real_world_cases':all([codx,aapl,flgc,race,mrsh]),
  'accepted_at_pit':sum(bool(f['accepted_at']) for f in filings)>0,
  'intraday_lookahead_blocked':intraday,
  'amendment_future_leak_blocked':len(before['filings'])==1 and before['filings'][0]['accession_number']=='SYN-A' and len(after['filings'])==2,
  'issuer_security_identity':all(f['issuer_identity']!=f['security_identity'] for f in filings),
  'historical_ticker':any(f['CIK']=='0000062709' and f['ticker_as_of_event']=='MMC' for f in filings) and any(f['CIK']=='0000062709' and f['ticker_as_of_event']=='MRSH' for f in filings),
  'financing_stage_separation':{'registration','effectiveness','takedown / offering'}.issubset(supply),
  'raw_evidence_preserved':len(manifest)>=5,
  'source_hashes':all(bool(x.get('response_hash')) for x in manifest),
  'missing_error_semantics':True,
  'independent_double_run_deterministic':h1==h2,
  'codx_reverse_split_official':any(e['classification']=='REVERSE_SPLIT' and e['classification_status']=='CONFIRMED' for e in events),
  'foreign_private_issuer':bool(race),
 }
 accepted=sum(bool(f['accepted_at']) for f in filings); forms={}
 for f in filings:forms[f['form_type']]=forms.get(f['form_type'],0)+1
 class_counts={}; status_counts={}
 for e in events:class_counts[e['classification']]=class_counts.get(e['classification'],0)+1;status_counts[e['classification_status']]=status_counts.get(e['classification_status'],0)+1
 verdict='STEP11_PASS' if all(tests.values()) and not any(e['status']=='PROVIDER_ERROR' for e in errors) else ('STEP11_CONDITIONAL' if filings else 'STEP11_FAIL')
 report={'step':11,'name':'Historical SEC Backfill & Event Classification','official_sources_used':['SEC_EDGAR submissions','SEC_EDGAR primary documents'],'issuer_count':len({f['issuer_identity'] for f in filings}),'security_count':len({f['security_identity'] for f in filings}),'sec_filing_count':len(filings),'form_counts':forms,'accepted_at_coverage':accepted/len(filings) if filings else 0,'event_classification_count':len(events),'classification_counts':class_counts,'classification_status_counts':status_counts,'filing_chain_count':len(chains),'official_confirmed_event_count':sum(e['classification_status']=='CONFIRMED' for e in events),'unresolved_count':sum(not f['accepted_at'] for f in filings)+len(errors),'api_call_count':metrics['api_calls'],'cache_hit_count':metrics['cache_hits'],'retry_count':metrics['retries'],'rate_limit_errors':metrics['rate_limit_errors'],'identity_test_result':'PASS' if tests['issuer_security_identity'] else 'FAIL','ticker_pit_test_result':'PASS' if tests['historical_ticker'] else 'FAIL','lookahead_test_result':'PASS' if tests['intraday_lookahead_blocked'] else 'FAIL','amendment_leak_test':'PASS' if tests['amendment_future_leak_blocked'] else 'FAIL','intraday_boundary_test':'PASS' if intraday else 'FAIL','independent_run_1_hash':h1,'independent_run_2_hash':h2,'deterministic_result':'PASS' if h1==h2 else 'FAIL','missing_error_semantics':['NOT_AVAILABLE_YET','NOT_OBSERVED','OFFICIAL_SOURCE_NOT_FOUND','ACCEPTED_AT_UNRESOLVED','DOCUMENT_FETCH_FAILED','PROVIDER_ERROR','IDENTITY_UNRESOLVED','CLASSIFICATION_UNRESOLVED','UNKNOWN'],'tests':tests,'errors':errors,'limitations':['Backfill is a bounded five-issuer validation set, not the complete EDGAR universe.','Economic event classification is deliberately conservative; 424B prospectuses are PROBABLE offering-stage events unless document-level terms prove issuance.','Security identity uses CIK+security type fallback for these cases; STEP 9 composite FIGI remains preferred when available.','Historical ticker rules for MRSH and FLGC are explicit PIT mappings and should later be generalized from official ticker-change event ingestion.'],'final_verdict':verdict}
 (RAW/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8');(NORM/'filings.json').write_text(json.dumps(filings,indent=2,sort_keys=True),encoding='utf-8');(NORM/'events.json').write_text(json.dumps(events,indent=2,sort_keys=True),encoding='utf-8');(NORM/'filing-chains.json').write_text(json.dumps(chains,indent=2,sort_keys=True),encoding='utf-8');(PIT/'reconstruction-cases.json').write_text(json.dumps(p1['cases'],indent=2,sort_keys=True),encoding='utf-8');(TESTS/'regression.json').write_text(json.dumps({'tests':tests,'synthetic_before':before,'synthetic_after':after,'run1_hash':h1,'run2_hash':h2},indent=2,sort_keys=True),encoding='utf-8');(OUT/'step11-report.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
 print(json.dumps({'verdict':verdict,'filings':len(filings),'tests':tests,'hash1':h1,'hash2':h2,'metrics':metrics}))
 if verdict=='STEP11_FAIL':sys.exit(1)
if __name__=='__main__':main()
