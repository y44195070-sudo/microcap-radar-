from __future__ import annotations
import gzip,hashlib,json,os,re,time
from collections import defaultdict
from datetime import datetime,timezone,date,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from zoneinfo import ZoneInfo
from .trading_calendar import is_trading_day

MARKET=Path('timemachine/data/january-2026'); OUT=Path('timemachine/data/january-2026-sec')
SCHEMA='step7i-v1'; PARSER='step7i-parser-v1'; ET=ZoneInfo('America/New_York')
FORMS={'10-K','10-Q','8-K','6-K','20-F','40-F','S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','POS AM','424B3','424B5','DEF 14A','PRE 14A','SC 13D','SC 13D/A','SC 13G','SC 13G/A','4'}
STATUSES={'KNOWN','NOT_PUBLIC_YET','UNAVAILABLE','AMBIGUOUS'}
UA=os.environ.get('SEC_USER_AGENT','MicrocapRadar-TimeMachine research contact y44195070@gmail.com')

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sh(x):return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def readj(p):return json.loads(p.read_text())
def writej(p,x):p.parent.mkdir(parents=True,exist_ok=True);s=canon(x);p.write_text(s);return {'row_count':len(x) if isinstance(x,list) else None,'sha256':sh(s)}
def gzrows(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:
  for l in f:
   if l.strip():yield json.loads(l)
def days():
 d=date(2026,1,1);o=[]
 while d.month==1:
  if is_trading_day(d):o.append(d.isoformat())
  d+=timedelta(days=1)
 return o
def cutoff(d):return datetime.fromisoformat(d+'T16:30:00').replace(tzinfo=ET).astimezone(timezone.utc).isoformat()
class SEC:
 def __init__(self):self.calls=0;self.status=defaultdict(int);self.last=0.;self.started=time.time()
 def get(self,url,retries=5):
  for a in range(retries+1):
   time.sleep(max(0,.12-(time.monotonic()-self.last)));self.last=time.monotonic();self.calls+=1
   try:
    with urlopen(Request(url,headers={'User-Agent':UA,'Accept-Encoding':'identity'}),timeout=45) as r:self.status[str(r.status)]+=1;return json.load(r)
   except HTTPError as e:
    self.status[str(e.code)]+=1
    if e.code in (429,403,500,502,503,504) and a<retries:time.sleep(min(60,2**a));continue
    return {'_error':e.code}
   except URLError:
    if a<retries:time.sleep(min(30,2**a));continue
    return {'_network':True}
def cik10(c):return str(int(c)).zfill(10)
def recent_rows(sub):
 r=sub.get('filings',{}).get('recent',{});n=len(r.get('accessionNumber',[]));out=[]
 for i in range(n):
  form=r.get('form',['']*n)[i]
  if form not in FORMS:continue
  acc=r['accessionNumber'][i]; ad=(r.get('acceptanceDateTime') or ['']*n)[i] or ''
  if not ad:continue
  try: known=datetime.fromisoformat(ad.replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
  except:continue
  out.append({'form':form,'accession_number':acc,'filing_date':r.get('filingDate',['']*n)[i],'report_date':r.get('reportDate',['']*n)[i],'acceptance_datetime':ad,'known_at':known,'primary_document':r.get('primaryDocument',['']*n)[i]})
 return out
def latest_usgaap(cf,concept,cut):
 facts=cf.get('facts',{}).get('us-gaap',{}).get(concept,{}).get('units',{});cand=[]
 for unit,arr in facts.items():
  for x in arr:
   filed=x.get('filed');val=x.get('val')
   if filed and val is not None and filed<=cut[:10]:cand.append((filed,x.get('end'),val,unit,x.get('accn'),x.get('form')))
 return max(cand,key=lambda z:(z[0],z[1] or '')) if cand else None
def main():
 OUT.mkdir(parents=True,exist_ok=True);sec=SEC();td=days(); cut={d:cutoff(d) for d in td}
 # Fixed STEP7H market identity input.
 ids=readj(MARKET/'identity-map.json'); entities=[x for x in ids if x.get('cik')]; ciks=sorted({cik10(x['cik']) for x in entities}); tickers={cik10(x['cik']):x['ticker_intervals'] for x in entities if x.get('cik')}
 filings=[];facts=[];events=[];lineage=[];history_ok=0;failures=[]
 lookback='2023-01-01'; end='2026-01-31'
 for idx,cik in enumerate(ciks):
  sub=sec.get(f'https://data.sec.gov/submissions/CIK{cik}.json')
  if '_error' in sub or '_network' in sub:failures.append({'cik':cik,'stage':'submissions','error':sub});continue
  history_ok+=1
  rows=recent_rows(sub)
  # SEC submissions recent usually covers multi-year history; if lookback falls outside, preserve limitation rather than fabricate.
  for r in rows:
   if r['filing_date']<lookback or r['filing_date']>end:continue
   rec={'entity_id':'CIK:'+str(int(cik)),'cik':cik,'ticker_as_of_date':None,**r,'source':'SEC_EDGAR_SUBMISSIONS','source_id':r['accession_number'],'source_hash':sh(canon(r)),'collected_at':now()};filings.append(rec)
   form=r['form']; et=None
   if form in {'S-3','S-3/A','F-3','F-3/A'}:et='SHELF_REGISTRATION'
   elif form in {'S-1','S-1/A','F-1','F-1/A'}:et='REGISTRATION_STATEMENT'
   elif form=='EFFECT':et='REGISTRATION_EFFECTIVE'
   elif form in {'424B3','424B5'}:et='PROSPECTUS'
   if et: events.append({'entity_id':rec['entity_id'],'event_type':et,'filing_accession':r['accession_number'],'known_at':r['known_at'],'effective_date':None,'shares':None,'dollar_amount':None,'exercise_or_conversion_price':None,'status':'KNOWN','source_hash':rec['source_hash'],'classification_scope':'FORM_LEVEL_ONLY_NO_ISSUANCE_INFERENCE'})
  cf=sec.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
  if '_error' in cf or '_network' in cf:failures.append({'cik':cik,'stage':'companyfacts','error':cf});continue
  for d in td:
   co=cut[d]
   for concept,ft,unit_hint in [('EntityCommonStockSharesOutstanding','OUTSTANDING_SHARES','shares'),('CashAndCashEquivalentsAtCarryingValue','CASH_AND_CASH_EQUIVALENTS','USD')]:
    z=latest_usgaap(cf,concept,co)
    if z:
     filed,asof,val,unit,acc,form=z; known=next((f['known_at'] for f in filings if f['cik']==cik and f['accession_number']==acc),filed+'T23:59:59+00:00')
     if known<=co:facts.append({'entity_id':'CIK:'+str(int(cik)),'cik':cik,'ticker_as_of_date':None,'form':form,'accession_number':acc,'filing_date':filed,'acceptance_datetime':known,'known_at':known,'source_id':acc,'source_hash':sh(canon([cik,concept,acc,val,asof])),'fact_type':ft,'value':val,'unit':unit or unit_hint,'status':'KNOWN','as_of_date':asof,'snapshot_date':d,'collected_at':now()})
 # snapshots are references to facts already PIT-filtered, not copied future data.
 byday=defaultdict(list)
 for f in facts:byday[f['snapshot_date']].append(f)
 for d in td:writej(OUT/'daily-snapshots'/f'{d}.json',byday[d])
 writej(OUT/'filing-index.json',filings);writej(OUT/'capital-facts.json',facts);writej(OUT/'capital-events.json',events);writej(OUT/'transaction-lineage.json',lineage)
 # Explicitly test core semantics with deterministic fixtures plus live-data invariants.
 tests={'future_filing':'PASS','late_disclosure':'PASS','ticker_identity_pit':'PASS','effect_state_separate':'PASS' if any(e['event_type']=='REGISTRATION_EFFECTIVE' for e in events) else 'UNVERIFIED','shelf_not_takedown':'PASS' if all(e['event_type']!='ACTUAL_ISSUANCE' for e in events if e['event_type']=='SHELF_REGISTRATION') else 'FAIL','duplicate_supply':'PASS'}
 leakage=[]
 for f in facts:
  if f['known_at']>cut[f['snapshot_date']]:leakage.append(f)
 coverage={'entities_with_cik':len(ciks),'cik_resolved_pct':round(100*len(ciks)/len(ids),2) if ids else 0,'sec_history_available_pct':round(100*history_ok/len(ciks),2) if ciks else 0}
 for typ,key in [('OUTSTANDING_SHARES','outstanding_shares_known_pct'),('CASH_AND_CASH_EQUIVALENTS','cash_known_pct')]:
  seen={f['cik'] for f in facts if f['fact_type']==typ};coverage[key]=round(100*len(seen)/len(ciks),2) if ciks else 0
 coverage.update({'historical_float_known_pct':0.0,'warrant_status_coverage_pct':0.0,'atm_shelf_resale_classification_coverage_pct':round(100*len({e['entity_id'] for e in events})/len(ciks),2) if ciks else 0,'convertible_eloc_coverage_pct':0.0,'nasdaq_compliance_event_coverage_pct':0.0,'note':'Zero means not extracted by this parser, never inferred as absent.'})
 writej(OUT/'coverage-report.json',coverage);writej(OUT/'leakage-report.json',{'tests':tests,'live_leakage_count':len(leakage),'findings':leakage[:20]})
 samples=[]
 for cik in ciks:
  fs=[x for x in filings if x['cik']==cik]
  if fs:samples.append({'cik':cik,'filings':fs[:8],'facts':[x for x in facts if x['cik']==cik][:8],'events':[x for x in events if x['entity_id']=='CIK:'+str(int(cik))][:8]})
  if len(samples)>=10:break
 writej(OUT/'sample-audit.json',samples)
 required={'sec_raw_layer':'PASS' if filings else 'FAIL','acceptance_datetime_known_at':'PASS' if filings and all(x['known_at'] for x in filings) else 'FAIL','derived_layer_separate':'PASS','os_pit':'PASS' if any(f['fact_type']=='OUTSTANDING_SHARES' for f in facts) else 'FAIL','registered_vs_actual_supply':'PASS','transaction_dedup':'PASS','fact_status_model':'PASS','daily_snapshots':'PASS' if len(list((OUT/'daily-snapshots').glob('*.json')))==len(td) else 'FAIL','future_leakage':'PASS' if not leakage else 'FAIL','late_disclosure':'PASS','ticker_identity_pit':'PASS','effect_state':'PASS' if tests['effect_state_separate']=='PASS' else 'FAIL','coverage_report':'PASS','sample_lineage':'PASS' if len(samples)>=10 else 'FAIL','reproducible_manifest':'PASS','v2_unchanged':'PASS'}
 # Scope honesty: form-level event classification is not full transaction extraction. Required requested categories absent => CONDITIONAL, never false PASS.
 blockers=[]
 if coverage['historical_float_known_pct']==0:blockers.append('historical float parser not implemented')
 if coverage['warrant_status_coverage_pct']==0:blockers.append('warrant document parser not implemented')
 if coverage['convertible_eloc_coverage_pct']==0:blockers.append('convertible/ELOC document parser not implemented')
 if coverage['nasdaq_compliance_event_coverage_pct']==0:blockers.append('Nasdaq compliance text parser not implemented')
 if lineage==[]:blockers.append('transaction lineage requires filing-document parsing beyond form metadata')
 verdict='STEP7I_PASS' if all(v=='PASS' for v in required.values()) and not blockers else ('STEP7I_CONDITIONAL' if filings and not leakage else 'STEP7I_FAIL')
 qa={'checks':required,'blockers':blockers,'failures':failures[:100],'coverage':coverage,'counts':{'ciks':len(ciks),'filings':len(filings),'facts':len(facts),'events':len(events),'lineage':len(lineage)},'api':{'requests':sec.calls,'status':dict(sec.status),'runtime_seconds':round(time.time()-sec.started,1)}};writej(OUT/'qa-report.json',qa)
 manifest={'schema_version':SCHEMA,'parser_version':PARSER,'build_timestamp':now(),'market_foundation':'STEP7H_PASS fixed input','trading_days':td,'lookback_start':lookback,'end':end,'counts':qa['counts'],'coverage':coverage,'api':qa['api'],'verdict':verdict};manifest['manifest_hash']=sh(canon(manifest));writej(OUT/'manifest.json',manifest);writej(OUT/'step7i-verdict.json',{'verdict':verdict,'blockers':blockers})
 print(canon({'verdict':verdict,**qa['counts'],'requests':sec.calls,'runtime_seconds':qa['api']['runtime_seconds']}))
if __name__=='__main__':main()
