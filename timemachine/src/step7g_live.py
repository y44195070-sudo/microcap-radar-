from __future__ import annotations
import hashlib,json,os,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError

BASE='https://api.massive.com'; OUT=Path('timemachine/data/massive-live-coverage-2026-01.json')
DATES=['2026-01-02','2026-01-16','2026-01-30']; MIN_INTERVAL=13.5

def now(): return datetime.now(timezone.utc).isoformat()
def sha(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def day(s,n): return (datetime.strptime(s,'%Y-%m-%d')+timedelta(days=n)).strftime('%Y-%m-%d')

class Client:
 def __init__(self):
  self.key=os.getenv('MASSIVE_API_KEY'); self.calls=0; self.last=0.; self.retries=[]
  if not self.key: raise RuntimeError('BLOCKED_API_KEY_NOT_CONNECTED')
 def get(self,path,params=None,max_retries=6):
  q=dict(params or {}); q['apiKey']=self.key; url=path if path.startswith('http') else BASE+path
  for attempt in range(max_retries+1):
   wait=MIN_INTERVAL-(time.monotonic()-self.last)
   if wait>0: time.sleep(wait)
   sep='&' if '?' in url else '?'; req=Request(url+sep+urlencode(q),headers={'User-Agent':'MicrocapRadar-TimeMachine/step7g-retest'})
   self.last=time.monotonic(); self.calls+=1
   try:
    with urlopen(req,timeout=45) as r: return json.load(r)
   except HTTPError as e:
    body=e.read().decode('utf-8','replace')[:1000]
    if e.code==429 and attempt<max_retries:
     ra=e.headers.get('Retry-After'); delay=float(ra) if ra and ra.replace('.','',1).isdigit() else min(65*(attempt+1),180)
     self.retries.append({'code':429,'attempt':attempt+1,'delay_s':delay}); time.sleep(delay); continue
    return {'_http_error':e.code,'_body':body}

def page(c,path,params,max_pages=30):
 rows=[]; hashes=[]; pages=0
 while True:
  d=c.get(path,params); pages+=1
  if '_http_error' in d:return {'status':'FAIL','error':d,'count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}
  hashes.append(sha(d)); rows.extend(d.get('results') or []); nxt=d.get('next_url')
  if not nxt:break
  u=urlparse(nxt); path=u.path; pq=parse_qs(u.query); params={k:v[-1] for k,v in pq.items() if k!='apiKey'}
  if pages>=max_pages:return {'status':'PARTIAL','reason':'pagination safety stop','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}
 return {'status':'PASS','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}

def universe(c,date): return page(c,'/v3/reference/tickers',{'market':'stocks','date':date,'limit':1000,'sort':'ticker','order':'asc'})
def agg(c,t,date):
 d=c.get(f'/v2/aggs/ticker/{t}/range/1/day/{date}/{date}',{'adjusted':'false','limit':50000,'sort':'asc'})
 if '_http_error'in d:return {'status':'FAIL','error':d}
 r=d.get('results') or []; return {'status':'PASS' if r else 'MISSING','bar':r[0] if r else None,'response_hash':sha(d)}

def main():
 c=Client(); report={'step':'7G_RETEST','provider':'Massive','provider_plan_claimed':'Stocks Basic','collected_at':now(),'source_quality':'VENDOR_RECONSTRUCTED_PIT','secret_present':True,'m_tests':{},'evidence':{},'notes':[]}
 U={}; meta={}
 for dt in DATES:
  x=universe(c,dt); rows=x.pop('rows',[]); U[dt]=rows; meta[dt]=x
  venues={}; types={}
  for r in rows:
   venues[r.get('primary_exchange','UNKNOWN')]=venues.get(r.get('primary_exchange','UNKNOWN'),0)+1; types[r.get('type','UNKNOWN')]=types.get(r.get('type','UNKNOWN'),0)+1
  x['venue_counts']=venues;x['security_type_counts']=types
 report['evidence']['M1']=meta
 m1='PASS' if all(meta[d]['status']=='PASS' and meta[d]['count']>0 for d in DATES) else 'FAIL';report['m_tests']['M1']={'status':m1,'description':'3 complete historical date universes'}

 # M2/M3: empirical survivorship/new-listing behavior between historical snapshots.
 a={r.get('ticker'):r for r in U[DATES[0]] if r.get('ticker')}; b={r.get('ticker'):r for r in U[DATES[-1]] if r.get('ticker')}
 gone=sorted(set(a)-set(b))[:5]; new=sorted(set(b)-set(a))[:3]
 report['evidence']['M2']={'samples':gone,'count_candidates':len(set(a)-set(b))}; report['m_tests']['M2']={'status':'PASS' if len(gone)>=5 else 'UNVERIFIED','description':'At least 5 symbols disappear across historical PIT snapshots (survivorship observable)'}
 report['evidence']['M3']={'samples':new,'count_candidates':len(set(b)-set(a))}; report['m_tests']['M3']={'status':'PASS' if len(new)>=3 else 'UNVERIFIED','description':'At least 3 symbols appear across historical PIT snapshots (new listings observable)'}

 # M4: same stable identifier, different ticker across snapshots.
 def ids(rows):
  out={}
  for r in rows:
   ident=r.get('composite_figi') or r.get('cik')
   if ident: out.setdefault(ident,set()).add(r.get('ticker'))
  return out
 ia,ib=ids(U[DATES[0]]),ids(U[DATES[-1]]); changes=[]
 for ident in set(ia)&set(ib):
  if ia[ident]!=ib[ident]: changes.append({'id':ident,'from':sorted(ia[ident]),'to':sorted(ib[ident])})
 report['evidence']['M4']={'samples':changes[:3],'count_candidates':len(changes)};report['m_tests']['M4']={'status':'PASS' if len(changes)>=3 else ('PARTIAL' if changes else 'UNVERIFIED'),'description':'Stable FIGI/CIK maps to ticker changes across PIT snapshots'}

 # M5/M6: discover January reverse splits, then inspect unadjusted bars around execution date.
 sp=page(c,'/v3/reference/splits',{'execution_date.gte':'2026-01-01','execution_date.lte':'2026-01-31','limit':1000,'sort':'execution_date','order':'asc'},5)
 splits=sp.pop('rows',[]); rev=[s for s in splits if isinstance(s.get('split_from'),(int,float)) and isinstance(s.get('split_to'),(int,float)) and s['split_from']>s['split_to']][:5]
 rs=[]
 for s in rev:
  t=s.get('ticker'); ex=s.get('execution_date'); pre=agg(c,t,day(ex,-1)); post=agg(c,t,ex); rs.append({'ticker':t,'execution_date':ex,'split_from':s.get('split_from'),'split_to':s.get('split_to'),'pre':pre,'post':post})
 valid=[x for x in rs if x['pre']['status']=='PASS' and x['post']['status']=='PASS']
 report['evidence']['M5']={'split_query':sp,'samples':rs};report['m_tests']['M5']={'status':'PASS' if len(valid)>=5 else ('PARTIAL' if valid else 'UNVERIFIED'),'description':'5 reverse-split samples expose adjusted=false pre/post raw price bars'}
 volok=[x for x in valid if x['pre']['bar'].get('v') is not None and x['post']['bar'].get('v') is not None]
 report['evidence']['M6']={'validated_samples':len(volok)};report['m_tests']['M6']={'status':'PASS' if len(volok)>=5 else ('PARTIAL' if volok else 'UNVERIFIED'),'description':'Raw volume present on reverse-split pre/post bars'}

 smoke=[]
 for t in ['AAPL','MSFT','NVDA','AMZN','META']: smoke.append({'ticker':t,'date':'2026-01-16',**agg(c,t,'2026-01-16')})
 report['evidence']['M7']=smoke;report['m_tests']['M7']={'status':'PASS' if all(x['status']=='PASS' for x in smoke) else 'FAIL','description':'adjusted=false OHLCV endpoint 5/5 live access'}

 complete=m1=='PASS'; fields=complete and all(any(r.get('primary_exchange') for r in U[d]) and any(r.get('type') for r in U[d]) for d in DATES)
 report['evidence']['M8']={d:{'venue_counts':meta[d].get('venue_counts'),'security_type_counts':meta[d].get('security_type_counts')} for d in DATES};report['m_tests']['M8']={'status':'PASS' if fields else 'FAIL','description':'Exchange/type fields present in all complete historical universes'}

 # M9: missing bar is distinguishable from transport/API failure; sample known weekend and trading day.
 miss=agg(c,'AAPL','2026-01-17'); live=agg(c,'AAPL','2026-01-16'); report['evidence']['M9']={'known_nontrading_day':miss,'known_trading_day':live};report['m_tests']['M9']={'status':'PASS' if miss['status']=='MISSING' and live['status']=='PASS' else 'UNVERIFIED','description':'Provider distinguishes successful empty result from API failure (halt-specific semantics remain conservative)'}

 core=[report['m_tests'][k]['status'] for k in ['M1','M2','M5','M6','M7']]
 report['m_tests']['M10']={'status':'PASS' if all(x=='PASS' for x in core) else 'PARTIAL','description':'Basic entitlement coverage across PIT reference + raw aggregates + split reference','api_calls':c.calls,'rate_limit_policy':f'{MIN_INTERVAL}s minimum between every attempt; 429 Retry-After/backoff','429_retries':c.retries}
 report['final_verdict']='MASSIVE_PASS' if all(x=='PASS' for x in core) else ('MASSIVE_FAIL' if any(x=='FAIL' for x in core) else 'MASSIVE_CONDITIONAL')
 report['notes']+=['No API key or authenticated URL is persisted. Raw response hashes only.','M2/M3/M4 validate vendor PIT behavior; they are not issuer/SEC event-causality proofs.','M9 validates missing-vs-error semantics, not a dedicated exchange halt flag.']
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'output':str(OUT),'calls':c.calls,'M1':m1,'M5':report['m_tests']['M5']['status'],'M6':report['m_tests']['M6']['status'],'M7':report['m_tests']['M7']['status'],'verdict':report['final_verdict']}))
if __name__=='__main__':
 try:main()
 except Exception as e:print(str(e),file=sys.stderr);raise
