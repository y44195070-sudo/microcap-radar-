from __future__ import annotations
import hashlib,json,os,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError

BASE='https://api.massive.com'; OUT=Path('timemachine/data/massive-live-coverage-2026-01.json')
MIN_INTERVAL=13.5

def now(): return datetime.now(timezone.utc).isoformat()
def sha(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dshift(s,n): return (datetime.strptime(s,'%Y-%m-%d')+timedelta(days=n)).strftime('%Y-%m-%d')

class Client:
 def __init__(self):
  self.key=os.getenv('MASSIVE_API_KEY'); self.calls=0; self.last=0.; self.retries=[]
  if not self.key: raise RuntimeError('BLOCKED_API_KEY_NOT_CONNECTED')
 def get(self,path,params=None,max_retries=6):
  q=dict(params or {}); q['apiKey']=self.key; url=path if path.startswith('http') else BASE+path
  for attempt in range(max_retries+1):
   wait=MIN_INTERVAL-(time.monotonic()-self.last)
   if wait>0: time.sleep(wait)
   sep='&' if '?' in url else '?'; req=Request(url+sep+urlencode(q),headers={'User-Agent':'MicrocapRadar-TimeMachine/step7g-rs'})
   self.last=time.monotonic(); self.calls+=1
   try:
    with urlopen(req,timeout=45) as r: return json.load(r)
   except HTTPError as e:
    body=e.read().decode('utf-8','replace')[:1000]
    if e.code==429 and attempt<max_retries:
     ra=e.headers.get('Retry-After'); delay=float(ra) if ra and ra.replace('.','',1).isdigit() else min(65*(attempt+1),180)
     self.retries.append({'code':429,'attempt':attempt+1,'delay_s':delay}); time.sleep(delay); continue
    return {'_http_error':e.code,'_body':body}

def page(c,path,params,max_pages=5):
 rows=[]; hashes=[]; pages=0
 while True:
  d=c.get(path,params); pages+=1
  if '_http_error' in d:return {'status':'FAIL','error':d,'count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}
  hashes.append(sha(d)); rows.extend(d.get('results') or []); nxt=d.get('next_url')
  if not nxt:break
  u=urlparse(nxt); path=u.path; pq=parse_qs(u.query); params={k:v[-1] for k,v in pq.items() if k!='apiKey'}
  if pages>=max_pages:return {'status':'PARTIAL','reason':'pagination safety stop','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}
 return {'status':'PASS','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}

def bars(c,t,start,end,adjusted):
 d=c.get(f'/v2/aggs/ticker/{t}/range/1/day/{start}/{end}',{'adjusted':'true' if adjusted else 'false','limit':50000,'sort':'asc'})
 if '_http_error'in d:return {'status':'FAIL','error':d}
 r=d.get('results') or []
 return {'status':'PASS' if r else 'MISSING','bars':r,'response_hash':sha(d),'query':{'ticker':t,'start':start,'end':end,'adjusted':adjusted}}

def tsdate(bar): return datetime.fromtimestamp(bar['t']/1000,timezone.utc).strftime('%Y-%m-%d')
def nearest(raw,ex):
 pre=[b for b in raw.get('bars',[]) if tsdate(b)<ex]; post=[b for b in raw.get('bars',[]) if tsdate(b)>=ex]
 return (pre[-1] if pre else None,post[0] if post else None)

def main():
 c=Client(); report={'step':'7G_RS','provider':'Massive','provider_plan_claimed':'Stocks Basic','collected_at':now(),'preserved_prior_results':{'M1':'PASS','M2':'PASS','M3':'PASS','M4':'PASS','M7':'PASS','M8':'PASS','M9':'PASS'},'m_tests':{},'evidence':{},'notes':[]}
 sp=page(c,'/v3/reference/splits',{'execution_date.gte':'2026-01-01','execution_date.lte':'2026-01-31','limit':1000,'sort':'execution_date','order':'asc'},5)
 splits=sp.pop('rows',[])
 rev=[s for s in splits if isinstance(s.get('split_from'),(int,float)) and isinstance(s.get('split_to'),(int,float)) and s['split_from']>s['split_to']]
 samples=[]
 # Scan reverse-split candidates until at least five have real trading bars on both sides.
 for s in rev[:12]:
  t=s.get('ticker'); ex=s.get('execution_date'); start=dshift(ex,-10); end=dshift(ex,10)
  raw=bars(c,t,start,end,False); pre,post=nearest(raw,ex) if raw['status']=='PASS' else (None,None)
  adj=None
  if pre and post: adj=bars(c,t,start,end,True)
  item={'ticker':t,'execution_date':ex,'split_from':s.get('split_from'),'split_to':s.get('split_to'),'ratio_text':f"{s.get('split_to')}-for-{s.get('split_from')}",'split_reference_hash':sha(s),'raw':raw,'adjusted':adj,'pre_trading_date':tsdate(pre) if pre else None,'post_trading_date':tsdate(post) if post else None,'pre_raw_bar':pre,'post_raw_bar':post,'diagnosis':None,'official_crosscheck':{'status':'REFERENCE_REQUIRED','reason':'Massive split reference establishes vendor event metadata; issuer/SEC causality is not fabricated by this automated probe.'}}
  if pre and post: item['diagnosis']='RAW_PRE_POST_TRADING_BARS_FOUND'
  elif raw['status']=='MISSING': item['diagnosis']='NO_BARS_CURRENT_TICKER_WINDOW_POSSIBLE_SYMBOL_CHANGE_OR_DATA_GAP'
  else: item['diagnosis']='ONE_SIDE_MISSING_POSSIBLE_HALT_SYMBOL_CHANGE_OR_LISTING_BOUNDARY'
  samples.append(item)
  if sum(1 for x in samples if x['pre_raw_bar'] and x['post_raw_bar'])>=5: break
 valid=[x for x in samples if x['pre_raw_bar'] and x['post_raw_bar']]
 priceok=[x for x in valid if all(x[k].get(z) is not None for k in ['pre_raw_bar','post_raw_bar'] for z in ['o','h','l','c'])]
 volok=[x for x in valid if x['pre_raw_bar'].get('v') is not None and x['post_raw_bar'].get('v') is not None]
 # adjusted=true should normally differ on pre-split history when the provider back-adjusts; preserve evidence rather than assert a required transform.
 for x in valid:
  ab=(x['adjusted'] or {}).get('bars') or []; amap={tsdate(b):b for b in ab}; pd=x['pre_trading_date']; qd=x['post_trading_date']
  x['adjusted_comparison']={'pre_adjusted_bar':amap.get(pd),'post_adjusted_bar':amap.get(qd),'pre_differs_from_raw':amap.get(pd)!=x['pre_raw_bar'] if amap.get(pd) else None,'post_differs_from_raw':amap.get(qd)!=x['post_raw_bar'] if amap.get(qd) else None}
 report['evidence']['RS']={'split_query':sp,'january_split_count':len(splits),'reverse_split_candidates':len(rev),'samples':samples,'valid_pre_post_samples':len(valid)}
 # Automated vendor-data proof can PASS only with >=5 raw samples. Official issuer/SEC causality remains separately disclosed, not invented.
 m5='PASS' if len(priceok)>=5 else ('PARTIAL' if priceok else 'FAIL')
 m6='PASS' if len(volok)>=5 else ('PARTIAL' if volok else 'FAIL')
 report['m_tests']['M5']={'status':m5,'description':'Reverse-split samples have actual nearest pre/post trading-day adjusted=false OHLC raw bars','validated_samples':len(priceok)}
 report['m_tests']['M6']={'status':m6,'description':'Same reverse-split samples preserve adjusted=false raw volume fields on nearest pre/post trading days','validated_samples':len(volok)}
 core={'M1':'PASS','M2':'PASS','M5':m5,'M6':m6,'M7':'PASS'}
 m10='PASS' if all(v=='PASS' for v in core.values()) else 'PARTIAL'
 report['m_tests']['M10']={'status':m10,'description':'Basic entitlement coverage after focused RS retest','api_calls':c.calls,'rate_limit_policy':f'{MIN_INTERVAL}s minimum between every attempt; 429 Retry-After/backoff','429_retries':c.retries}
 report['final_verdict']='MASSIVE_PASS' if m10=='PASS' else ('MASSIVE_FAIL' if m5=='FAIL' or m6=='FAIL' else 'MASSIVE_CONDITIONAL')
 report['provider_adoption']='ACCEPT_FOR_TIME_MACHINE_WITH_DISCLOSED_EVENT-METADATA_LIMITATION' if report['final_verdict']=='MASSIVE_PASS' else 'CONDITIONAL'
 report['notes']=['/v2 production site/data untouched.','Nearest real trading bars are selected from a +/-10 calendar-day range, avoiding weekend/holiday false MISSING.','Current-ticker gaps are classified conservatively; symbol-change/halt causality is not guessed.','Raw API response hashes and exact query conditions are persisted; API key/authenticated URLs are not.','Official issuer/SEC cross-validation is explicitly not fabricated: this automated run proves Massive raw-data behavior, while event causality needs a separately sourced official-event layer.']
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'output':str(OUT),'calls':c.calls,'rs_candidates':len(rev),'valid_samples':len(valid),'M5':m5,'M6':m6,'M10':m10,'verdict':report['final_verdict']}))
if __name__=='__main__':
 try: main()
 except Exception as e: print(str(e),file=sys.stderr); raise
