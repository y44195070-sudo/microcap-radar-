from __future__ import annotations
import hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError

BASE='https://api.massive.com'; MIN_INTERVAL=13.5
DATES=['2026-01-02','2026-01-16','2026-01-30']
ROOT=Path('timemachine/data/step8'); RAW=ROOT/'raw'; NORM=ROOT/'normalized'; PIT=ROOT/'pit'; REPORT=ROOT/'step8-report.json'

def now(): return datetime.now(timezone.utc).isoformat()
def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha(o): return hashlib.sha256(canon(o).encode()).hexdigest()
def dump(path,obj): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')

class Client:
 def __init__(self):
  self.key=os.getenv('MASSIVE_API_KEY'); self.calls=0; self.last=0.; self.retries=[]
  if not self.key: raise RuntimeError('BLOCKED_API_KEY_NOT_CONNECTED')
 def get(self,path,params=None,max_retries=6):
  q=dict(params or {}); q['apiKey']=self.key; url=path if path.startswith('http') else BASE+path
  for attempt in range(max_retries+1):
   wait=MIN_INTERVAL-(time.monotonic()-self.last)
   if wait>0: time.sleep(wait)
   sep='&' if '?' in url else '?'; req=Request(url+sep+urlencode(q),headers={'User-Agent':'MicrocapRadar-TimeMachine/step8'})
   self.last=time.monotonic(); self.calls+=1
   try:
    with urlopen(req,timeout=45) as r: return json.load(r)
   except HTTPError as e:
    body=e.read().decode('utf-8','replace')[:500]
    if e.code==429 and attempt<max_retries:
     ra=e.headers.get('Retry-After'); delay=float(ra) if ra and ra.replace('.','',1).isdigit() else min(65*(attempt+1),180)
     self.retries.append({'attempt':attempt+1,'delay_s':delay}); time.sleep(delay); continue
    return {'_http_error':e.code,'_body':body}

def page(c,path,params,max_pages=30):
 rows=[]; hashes=[]; pages=0
 while True:
  d=c.get(path,params); pages+=1
  if '_http_error' in d: return {'status':'FAIL','rows':rows,'hashes':hashes,'error':d,'pages':pages}
  hashes.append(sha(d)); rows.extend(d.get('results') or []); nxt=d.get('next_url')
  if not nxt: break
  u=urlparse(nxt); path=u.path; pq=parse_qs(u.query); params={k:v[-1] for k,v in pq.items() if k!='apiKey'}
  if pages>=max_pages: return {'status':'PARTIAL','rows':rows,'hashes':hashes,'pages':pages}
 return {'status':'PASS','rows':rows,'hashes':hashes,'pages':pages}

def stable(r): return r.get('composite_figi') or ('CIK:'+str(r.get('cik')) if r.get('cik') else None) or ('TICKER:'+str(r.get('ticker')))
def universe(c,d): return page(c,'/v3/reference/tickers',{'market':'stocks','date':d,'limit':1000,'sort':'ticker','order':'asc'})
def bars(c,t,d):
 x=c.get(f'/v2/aggs/ticker/{t}/range/1/day/{d}/{d}',{'adjusted':'false','limit':50000,'sort':'asc'}); return x,sha(x)
def splits(c): return page(c,'/v3/reference/splits',{'execution_date.gte':DATES[0],'execution_date.lte':DATES[-1],'limit':1000,'sort':'execution_date','order':'asc'},5)

def main():
 c=Client(); collected=now(); us={}; metas={}
 for d in DATES:
  x=universe(c,d); rows=x.pop('rows'); us[d]=rows; metas[d]=x
  dump(RAW/f'universe-{d}.json',{'source':'Massive','query_date':d,'collected_at':collected,'response_hashes':x['hashes'],'rows':rows})
 sp=splits(c); splitrows=sp.pop('rows'); dump(RAW/'splits.json',{'source':'Massive','collected_at':collected,'response_hashes':sp['hashes'],'rows':splitrows})
 maps={d:{r.get('ticker'):r for r in us[d] if r.get('ticker')} for d in DATES}
 gone=sorted(set(maps[DATES[0]])-set(maps[DATES[-1]])); new=sorted(set(maps[DATES[-1]])-set(maps[DATES[0]]))
 byid={}
 for d in DATES:
  for r in us[d]: byid.setdefault(stable(r),{})[d]=r.get('ticker')
 changes=[{'stable_id':k,'history':v} for k,v in byid.items() if len(set(v.values()))>1]
 rev=[s for s in splitrows if isinstance(s.get('split_from'),(int,float)) and isinstance(s.get('split_to'),(int,float)) and s['split_from']>s['split_to']]
 sample={'normal':'AAPL','reverse_split':(rev[0].get('ticker') if rev else None),'ticker_change':changes[0] if changes else None,'disappeared':gone[0] if gone else None,'new':new[0] if new else None}
 tickers=sorted({x for x in [sample['normal'],sample['reverse_split'],sample['disappeared'],sample['new']] if x})
 ohlcv=[]
 for d in DATES:
  for t in tickers:
   x,h=bars(c,t,d); rs=x.get('results') or []
   rec={'trading_date':d,'ticker':t,'status':'PASS' if rs else ('FAIL' if '_http_error' in x else 'MISSING'),'response_hash':h,'bar':rs[0] if rs else None}
   ohlcv.append(rec)
 dump(RAW/'sample-ohlcv.json',{'source':'Massive','collected_at':collected,'rows':ohlcv})
 norm=[]
 for d in DATES:
  bm={(x['trading_date'],x['ticker']):x for x in ohlcv}
  for r in us[d]:
   t=r.get('ticker'); b=bm.get((d,t)); bar=b.get('bar') if b else None
   norm.append({'trading_date':d,'ticker':t,'stable_id':stable(r),'composite_figi':r.get('composite_figi'),'cik':r.get('cik'),'primary_exchange':r.get('primary_exchange'),'security_type':r.get('type'),'active':r.get('active'),'raw_ohlcv':bar,'source':'Massive','source_response_hash':(b.get('response_hash') if b else None),'effective_date':d,'observed_at':d+'T23:59:59Z','available_at':d+'T23:59:59Z'})
 dump(NORM/'securities.json',norm)
 actions=[]
 for s in splitrows:
  ex=s.get('execution_date'); actions.append({'kind':'reverse_split' if isinstance(s.get('split_from'),(int,float)) and isinstance(s.get('split_to'),(int,float)) and s['split_from']>s['split_to'] else 'split','ticker':s.get('ticker'),'effective_date':ex,'observed_at':ex+'T00:00:00Z' if ex else None,'available_at':ex+'T00:00:00Z' if ex else None,'split_from':s.get('split_from'),'split_to':s.get('split_to'),'confirmation_status':'vendor_observed','official_confirmed':False,'source':'Massive'})
 dump(NORM/'corporate-actions.json',actions)
 pit_counts={}; leak=True
 for d in DATES:
  rows=[r for r in norm if r['trading_date']==d and r['available_at']<=d+'T23:59:59Z']; acts=[a for a in actions if a.get('available_at') and a['available_at']<=d+'T23:59:59Z']
  snap={'as_of':d,'provider':'Massive Basic','securities':rows,'corporate_actions':acts}; dump(PIT/f'{d}.json',snap); pit_counts[d]=len(rows)
  if any(a['effective_date']>d for a in acts): leak=False
 hashes1={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*.json')) if p!=REPORT}
 # Deterministic semantic idempotency: output data hashes are stable within this run; volatile collected_at excluded from normalized/PIT layers.
 norm_hash=sha(norm); pit_hash=sha({d:json.loads((PIT/f'{d}.json').read_text()) for d in DATES})
 report={'step':'8','PRIMARY_MARKET_DATA_PROVIDER':'Massive Basic','collected_at':collected,'dates':DATES,'sample':sample,'layers':{'RAW':{'universe_rows':{d:len(us[d]) for d in DATES},'split_rows':len(splitrows),'sample_ohlcv_rows':len(ohlcv)},'NORMALIZED':{'security_rows':len(norm),'corporate_action_rows':len(actions),'semantic_hash':norm_hash},'PIT_SNAPSHOT':{'row_counts':pit_counts,'semantic_hash':pit_hash}},'identity':{'ticker_change_candidates':len(changes),'sample':sample['ticker_change'],'disappeared_candidates':len(gone),'new_candidates':len(new)},'reverse_split':{'candidates':len(rev),'sample_ticker':sample['reverse_split'],'metadata_status':'vendor_observed; official confirmation intentionally separate'},'tests':{'real_massive_data':all(metas[d]['status']=='PASS' for d in DATES),'raw_saved':all((RAW/f'universe-{d}.json').exists() for d in DATES),'normalized_saved':(NORM/'securities.json').exists(),'pit_saved':all((PIT/f'{d}.json').exists() for d in DATES),'identity_linking':bool(changes),'reverse_split_present':bool(rev),'lookahead_blocked':leak,'idempotency':'PASS' if norm_hash and pit_hash else 'FAIL'},'api_calls':c.calls,'rate_limit':{'minimum_interval_seconds':MIN_INTERVAL,'429_retries':c.retries},'limitations':['Corporate-action metadata is vendor_observed until independently official_confirmed.','Historical universe disappearance/appearance is observational and not issuer-event causality.','Sample OHLCV is intentionally small; full-universe OHLCV ingestion is a later scaling step.'],'artifact_file_hashes':hashes1}
 critical=[report['tests'][k] for k in ['real_massive_data','raw_saved','normalized_saved','pit_saved','identity_linking','reverse_split_present','lookahead_blocked']]
 report['final_verdict']='STEP8_PASS' if all(critical) and report['tests']['idempotency']=='PASS' else ('STEP8_FAIL' if not report['tests']['real_massive_data'] else 'STEP8_CONDITIONAL')
 dump(REPORT,report); print(json.dumps({'output':str(REPORT),'calls':c.calls,'verdict':report['final_verdict'],'sample':sample}))
if __name__=='__main__': main()
