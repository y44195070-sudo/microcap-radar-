from __future__ import annotations
import hashlib,json,os,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE='https://api.massive.com'
OUT=Path('timemachine/data/massive-live-coverage-step7g-r-2026-01.json')
DATES=['2026-01-02','2026-01-16','2026-01-30']
TARGET_MICS={'XNAS','XNYS','XASE'}

def now(): return datetime.now(timezone.utc).isoformat()
def sha(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def clean_body(s): return (s or '')[:600].replace(os.getenv('MASSIVE_API_KEY',''),'***')

class Client:
 def __init__(self):
  self.key=os.getenv('MASSIVE_API_KEY'); self.requests=0; self.retries429=0; self.last=0.0; self.http=[]
  if not self.key: raise RuntimeError('BLOCKED_API_KEY_NOT_CONNECTED')
 def get(self,path,params=None,max_retry=6):
  q=dict(params or {}); q['apiKey']=self.key; url=path if path.startswith('http') else BASE+path
  for attempt in range(max_retry+1):
   wait=max(0,12.5-(time.monotonic()-self.last))
   if wait: time.sleep(wait)
   sep='&' if '?' in url else '?'; full=url+sep+urlencode(q); self.requests+=1; self.last=time.monotonic()
   try:
    with urlopen(Request(full,headers={'User-Agent':'MicrocapRadar-TimeMachine/step7g-r'}),timeout=45) as r:
     data=json.load(r); self.http.append({'path':urlparse(url).path,'status':r.status}); return data
   except HTTPError as e:
    body=clean_body(e.read().decode('utf-8','replace')); self.http.append({'path':urlparse(url).path,'status':e.code,'body':body})
    if e.code==429 and attempt<max_retry:
     self.retries429+=1
     ra=e.headers.get('Retry-After'); delay=float(ra) if ra and ra.replace('.','',1).isdigit() else min(60,15*(2**attempt)); time.sleep(delay); continue
    return {'_http_error':e.code,'_body':body}
   except URLError as e:
    if attempt<max_retry: time.sleep(min(60,5*(2**attempt))); continue
    return {'_network_error':str(e.reason)}

def page_tickers(c,params,max_pages=30):
 path='/v3/reference/tickers'; rows=[]; pages=0; hashes=[]; start_calls=c.requests
 while True:
  d=c.get(path,params); pages+=1
  if '_http_error' in d or '_network_error' in d: return {'status':'FAIL','error':d,'rows':rows,'pages':pages,'api_calls':c.requests-start_calls,'hashes':hashes}
  hashes.append(sha(d)); rows.extend(d.get('results') or []); nxt=d.get('next_url')
  if not nxt: break
  if pages>=max_pages: return {'status':'PARTIAL','reason':'pagination safety stop','rows':rows,'pages':pages,'api_calls':c.requests-start_calls,'hashes':hashes}
  u=urlparse(nxt); path=u.path; pq=parse_qs(u.query); params={k:v[-1] for k,v in pq.items() if k.lower()!='apikey'}
 return {'status':'PASS','rows':rows,'pages':pages,'api_calls':c.requests-start_calls,'hashes':hashes}

def agg(c,ticker,date,adjusted=False):
 p={'adjusted':str(adjusted).lower(),'limit':50000,'sort':'asc'}; d=c.get(f'/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}',p)
 if '_http_error' in d or '_network_error' in d: return {'status':'FAIL','error':d,'query_parameters':p}
 r=d.get('results') or []; return {'status':'PASS' if r else 'UNVERIFIED','bar':r[0] if r else None,'query_parameters':p,'response_hash':sha(d)}
def prevbiz(s):
 d=datetime.fromisoformat(s)
 d-=timedelta(days=1)
 while d.weekday()>4: d-=timedelta(days=1)
 return d.date().isoformat()
def nextbiz(s):
 d=datetime.fromisoformat(s); d+=timedelta(days=1)
 while d.weekday()>4: d+=timedelta(days=1)
 return d.date().isoformat()
def test(status,evidence,reason,limitation='',sample_size=0,http=None): return {'status':status,'evidence':evidence,'sample_size':sample_size,'http_api_evidence':http or {},'limitation':limitation,'reason':reason}

def main():
 c=Client(); report={'step':'7G-R','provider':'Massive','provider_plan_claimed':'Stocks Basic','collected_at':now(),'source_quality':'VENDOR_RECONSTRUCTED_PIT','m_tests':{},'runtime':{},'notes':['No API key or authenticated URL is persisted.']}
 U={}; m1ev={}
 for date in DATES:
  q={'market':'stocks','date':date,'limit':1000,'sort':'ticker','order':'asc'}; u=page_tickers(c,q); rows=u.pop('rows'); U[date]=rows
  venues={}; types={}
  for r in rows: venues[r.get('primary_exchange','UNKNOWN')]=venues.get(r.get('primary_exchange','UNKNOWN'),0)+1; types[r.get('type','UNKNOWN')]=types.get(r.get('type','UNKNOWN'),0)+1
  m1ev[date]={**u,'count':len(rows),'venue_counts':venues,'security_type_counts':types,'query_parameters':q,'source_quality':'VENDOR_RECONSTRUCTED_PIT'}
 m1ok=all(x['status']=='PASS' and x['count']>0 for x in m1ev.values())
 report['m_tests']['M1']=test('PASS' if m1ok else 'FAIL',m1ev,'All three dated universes fully paginated' if m1ok else 'One or more dated universes did not fully paginate',sample_size=3)

 # M2: one current active universe snapshot, compare against Jan-02; absence is evidence of no longer active, conservatively PARTIAL unless 5 have explicit inactive detail.
 cur=page_tickers(c,{'market':'stocks','active':'true','limit':1000,'sort':'ticker','order':'asc'}); current=cur.pop('rows'); current_t={r.get('ticker') for r in current}
 candidates=[r for r in U[DATES[0]] if r.get('ticker') not in current_t and r.get('primary_exchange') in TARGET_MICS][:5]
 ev2=[{'ticker':r.get('ticker'),'name':r.get('name'),'exchange':r.get('primary_exchange'),'cik':r.get('cik'),'share_class_figi':r.get('share_class_figi'),'jan_universe':True,'current_active_universe':False} for r in candidates]
 report['m_tests']['M2']=test('PARTIAL' if len(ev2)>=5 else 'UNVERIFIED',ev2,'Five Jan names absent from current active universe' if len(ev2)>=5 else 'Fewer than five survivorship candidates found','Absence from active universe is not by itself explicit delisting proof; official/current inactive cross-check remains required.',len(ev2))

 # M3: use list_date + membership boundary between the three full snapshots.
 allmaps={d:{r.get('ticker'):r for r in U[d]} for d in DATES}; ev3=[]
 for pre,post in [(DATES[0],DATES[1]),(DATES[1],DATES[2])]:
  for t,r in allmaps[post].items():
   if t not in allmaps[pre] and r.get('list_date') and pre < r['list_date'] <= post:
    ev3.append({'ticker':t,'list_date':r.get('list_date'),'pre_date':pre,'pre_present':False,'post_date':post,'post_present':True,'cik':r.get('cik'),'figi':r.get('share_class_figi')})
    if len(ev3)>=3: break
  if len(ev3)>=3: break
 report['m_tests']['M3']=test('PASS' if len(ev3)>=3 else 'PARTIAL',ev3,'Provider list_date agrees with pre/post universe boundary' if len(ev3)>=3 else 'Insufficient boundary samples',sample_size=len(ev3))

 # M4: detect same stable identity with ticker change across snapshots.
 def ident(r): return r.get('cik') or r.get('share_class_figi')
 first={ident(r):r for r in U[DATES[0]] if ident(r)}; last={ident(r):r for r in U[DATES[-1]] if ident(r)}; ev4=[]
 for k,a in first.items():
  b=last.get(k)
  if b and a.get('ticker')!=b.get('ticker'): ev4.append({'stable_id':k,'old_ticker':a.get('ticker'),'new_ticker':b.get('ticker'),'before':DATES[0],'after':DATES[-1]})
  if len(ev4)>=3: break
 report['m_tests']['M4']=test('PASS' if len(ev4)>=3 else ('PARTIAL' if ev4 else 'UNVERIFIED'),ev4,'Stable CIK/FIGI links ticker change across dated universes','Exact effective date requires ticker-events/official event cross-check.',len(ev4))

 # M5/M6: discover January splits globally, select reverse splits on target venues/tickers, test raw vs adjusted bars around execution date.
 sp=c.get('/v3/reference/splits',{'execution_date.gte':'2026-01-01','execution_date.lte':'2026-01-31','limit':1000,'sort':'execution_date','order':'asc'}); splits=sp.get('results') or [] if isinstance(sp,dict) and '_http_error' not in sp else []
 jan_t=set().union(*(set(x.keys()) for x in allmaps.values())); rev=[]
 for s in splits:
  sf=s.get('split_from'); st=s.get('split_to'); t=s.get('ticker'); ex=s.get('execution_date')
  try: isrev=float(sf)>float(st)
  except: isrev=False
  if isrev and t in jan_t and ex: rev.append(s)
 rs=[]
 for s in rev[:5]:
  t=s['ticker']; ex=s['execution_date']; before=prevbiz(ex); after=nextbiz(ex)
  rb=agg(c,t,before,False); ra=agg(c,t,after,False); ab=agg(c,t,before,True)
  rs.append({'ticker':t,'execution_date':ex,'split_from':s.get('split_from'),'split_to':s.get('split_to'),'before_date':before,'after_date':after,'raw_before':rb,'raw_after':ra,'adjusted_before':ab,'split_source_hash':sha(s)})
 m5ok=len(rs)>=5 and all(x['raw_before']['status']=='PASS' and x['raw_after']['status']=='PASS' for x in rs)
 report['m_tests']['M5']=test('PASS' if m5ok else ('PARTIAL' if rs else 'UNVERIFIED'),rs,'Five reverse-split samples returned pre/post adjusted=false bars' if m5ok else 'Reverse-split sample or bars incomplete','SEC/official corporate-action semantic cross-check is separate from provider split record.',len(rs))
 m6ok=m5ok and all((x['raw_before'].get('bar') or {}).get('v') is not None and (x['raw_after'].get('bar') or {}).get('v') is not None for x in rs)
 report['m_tests']['M6']=test('PARTIAL' if m6ok else 'UNVERIFIED',rs,'Raw volume values returned on RS samples','Independent tape-level volume cross-check not automated; therefore never PASS in 7G-R.',len(rs))

 smoke=[]
 for t in ['AAPL','MSFT','NVDA','AMZN','META']: smoke.append({'ticker':t,'date':'2026-01-16',**agg(c,t,'2026-01-16',False)})
 m7ok=all(x['status']=='PASS' and all(k in (x.get('bar') or {}) for k in ['o','h','l','c','v']) for x in smoke)
 report['m_tests']['M7']=test('PASS' if m7ok else 'FAIL',smoke,'adjusted=false historical OHLCV accessible for all five liquid samples' if m7ok else 'One or more OHLCV samples failed',sample_size=5)

 venue_ok=all(any(r.get('primary_exchange') in TARGET_MICS for r in U[d]) for d in DATES); type_ok=all(any(r.get('type') for r in U[d]) for d in DATES)
 report['m_tests']['M8']=test('PARTIAL' if venue_ok and type_ok else 'FAIL',{'target_mics':sorted(TARGET_MICS),'venue_present':venue_ok,'type_present':type_ok},'Fields are populated across historical snapshots','Official exchange/security-type mapping cross-check not automated; field presence alone is not PASS.',3)

 report['m_tests']['M9']=test('UNVERIFIED',[],'No false PASS: official Nasdaq historical halt samples were not fetched by this runner','Use Nasdaq Trader halt history/search as official auxiliary source.',0)

 est_pages=sum(x['pages'] for x in m1ev.values())/3 if m1ev else 0; trading_days=21; est_calls=round(est_pages*trading_days); est_minutes=round(est_calls/5,1)
 core_access=m1ok and m7ok
 report['m_tests']['M10']=test('PARTIAL' if core_access else 'FAIL',{'historical_reference':m1ok,'historical_universe':m1ok,'aggregate_ohlcv':m7ok,'adjusted_false':m7ok,'pagination':m1ok,'corporate_actions_endpoint':bool(splits),'rate_limit':'5 calls/min','estimated_january_universe_calls':est_calls,'estimated_minutes_at_5_per_min':est_minutes},'Core Basic endpoints operational' if core_access else 'Core endpoint test failed','Later-delisted explicit proof and RS volume semantics remain incomplete.',sample_size=c.requests)

 statuses={k:v['status'] for k,v in report['m_tests'].items()}; critical=[statuses[k] for k in ['M1','M5','M7']]
 if any(x=='FAIL' for x in critical): verdict='REJECT_MASSIVE' if statuses['M1']=='FAIL' and statuses['M7']=='FAIL' else 'MASSIVE_CONDITIONAL'
 elif all(statuses[k]=='PASS' for k in ['M1','M2','M3','M4','M5','M6','M7','M8','M9','M10']): verdict='MASSIVE_PASS'
 else: verdict='MASSIVE_CONDITIONAL'
 report['final_provider_verdict']=verdict; report['runtime']={'total_http_requests':c.requests,'http_429_retries':c.retries429,'http_status_counts':{str(s):sum(1 for x in c.http if x['status']==s) for s in sorted({x['status'] for x in c.http})},'finished_at':now()}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'output':str(OUT),'M1':statuses['M1'],'M2':statuses['M2'],'M3':statuses['M3'],'M4':statuses['M4'],'M5':statuses['M5'],'M6':statuses['M6'],'M7':statuses['M7'],'M8':statuses['M8'],'M9':statuses['M9'],'M10':statuses['M10'],'requests':c.requests,'retries429':c.retries429,'verdict':verdict}))
if __name__=='__main__': main()
