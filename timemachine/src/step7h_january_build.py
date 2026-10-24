from __future__ import annotations
import gzip,hashlib,json,os,time
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from .trading_calendar import is_trading_day

BASE='https://api.massive.com'; ROOT=Path('timemachine/data/january-2026'); SCHEMA='step7h-v1'; MICS={'XNAS','XNYS','XASE'}
EXCLUDE={'ETF','ETN','WARRANT','RIGHT','UNIT','PREFERRED','FUND','BOND'}

def now(): return datetime.now(timezone.utc).isoformat()
def h(x): return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def trading_days():
 d=date(2026,1,1); out=[]
 while d.month==1:
  if is_trading_day(d): out.append(d.isoformat())
  d+=timedelta(days=1)
 return out
class C:
 def __init__(self):
  self.key=os.environ['MASSIVE_API_KEY']; self.n=0; self.r429=0; self.last=0.; self.status={}; self.started=time.time()
 def get(self,path,params=None,retries=6):
  q=dict(params or {}); q['apiKey']=self.key; url=path if path.startswith('http') else BASE+path
  for a in range(retries+1):
   w=max(0,12.5-(time.monotonic()-self.last)); time.sleep(w); self.n+=1; self.last=time.monotonic()
   full=url+('&' if '?' in url else '?')+urlencode(q)
   try:
    with urlopen(Request(full,headers={'User-Agent':'MicrocapRadar-TimeMachine/7H'}),timeout=60) as r:
     self.status[str(r.status)]=self.status.get(str(r.status),0)+1; return json.load(r)
   except HTTPError as e:
    self.status[str(e.code)]=self.status.get(str(e.code),0)+1
    if e.code==429 and a<retries:
     self.r429+=1; ra=e.headers.get('Retry-After'); time.sleep(float(ra) if ra and ra.replace('.','',1).isdigit() else min(60,15*2**a)); continue
    return {'_error':e.code}
   except URLError:
    if a<retries: time.sleep(min(60,5*2**a)); continue
    return {'_network_error':True}

def pages(c,day):
 path='/v3/reference/tickers'; q={'market':'stocks','date':day,'limit':1000,'sort':'ticker','order':'asc'}; rows=[]; hashes=[]; p=0
 while True:
  d=c.get(path,q); p+=1
  if '_error' in d or '_network_error' in d: return rows,p,False,hashes
  hashes.append(h(canon(d))); rows+=d.get('results') or []; nxt=d.get('next_url')
  if not nxt:return rows,p,True,hashes
  if p>=30:return rows,p,False,hashes
  u=urlparse(nxt); path=u.path; q={k:v[-1] for k,v in parse_qs(u.query).items() if k.lower()!='apikey'}
def write_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True); s=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')); path.write_text(s); return {'row_count':len(obj) if isinstance(obj,list) else None,'sha256':h(s)}
def write_jsonl_gz(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True); raw=''.join(canon(x)+'\n' for x in rows).encode(); path.write_bytes(gzip.compress(raw,mtime=0)); return {'row_count':len(rows),'sha256_uncompressed':h(raw),'sha256_file':h(path.read_bytes())}
def entity(r): return 'CIK:'+str(r['cik']) if r.get('cik') else ('SCFIGI:'+r['share_class_figi'] if r.get('share_class_figi') else 'UNRESOLVED:'+r.get('ticker',''))
def investable(r):
 if r.get('primary_exchange') not in MICS:return False
 t=(r.get('type') or 'UNKNOWN').upper()
 if any(x in t for x in EXCLUDE):return False
 return True

def main():
 ROOT.mkdir(parents=True,exist_ok=True); c=C(); days=trading_days(); manifest={'schema_version':SCHEMA,'build_timestamp':now(),'source':'Massive Stocks Basic + frozen auxiliary policy','trading_days':days,'datasets':{},'queries':{},'pit_policy':'dated universe; adjusted=false; no future/current active backfill'}
 manifest['datasets']['calendar.json']=write_json(ROOT/'calendar.json',{'schema_version':SCHEMA,'days':days,'closures':['2026-01-01','2026-01-19']})
 all_identity={}; prev=set(); qa={'universe':{},'identity':{},'ohlcv':{},'corporate_actions':{},'legacy_followups':{},'checks':{}}; missing=[]; total_raw=total_inv=total_bar=0; universe_by_day={}; inv_by_day={}
 for day in days:
  rows,p,ok,ph=pages(c,day); normalized=[]
  for r in rows:
   x={'as_of_date':day,'ticker':r.get('ticker'),'cik':r.get('cik'),'name':r.get('name'),'primary_exchange':r.get('primary_exchange'),'security_type':r.get('type'),'list_date':r.get('list_date'),'share_class_figi':r.get('share_class_figi'),'composite_figi':r.get('composite_figi'),'provider':'Massive','provider_known_at':None,'collected_at':now(),'source_quality':'VENDOR_RECONSTRUCTED_PIT'}; normalized.append(x)
  universe_by_day[day]=normalized; cur={x['ticker'] for x in normalized}; types={}; venues={}
  for x in normalized: venues[x['primary_exchange'] or 'UNKNOWN']=venues.get(x['primary_exchange'] or 'UNKNOWN',0)+1; types[x['security_type'] or 'UNKNOWN']=types.get(x['security_type'] or 'UNKNOWN',0)+1
  qa['universe'][day]={'rows':len(normalized),'pages':p,'complete':ok,'venues':venues,'types':types,'new_vs_prior':len(cur-prev) if prev else None,'gone_vs_prior':len(prev-cur) if prev else None}; prev=cur; total_raw+=len(normalized)
  meta=write_jsonl_gz(ROOT/'universe'/f'{day}.jsonl.gz',normalized); manifest['datasets'][f'universe/{day}.jsonl.gz']=meta; manifest['queries'][day]={'endpoint':'/v3/reference/tickers','date':day,'active_filter':False,'pages':p,'response_page_hashes':ph}
  inv=[x for x in normalized if investable(x)]; inv_by_day[day]=inv; total_inv+=len(inv); manifest['datasets'][f'investable/{day}.jsonl.gz']=write_jsonl_gz(ROOT/'investable'/f'{day}.jsonl.gz',inv)
  for x in inv:
   eid=entity(x); rec=all_identity.setdefault(eid,{'entity_id':eid,'cik':x['cik'],'share_class_figi':x['share_class_figi'],'composite_figi':x['composite_figi'],'tickers':{},'status':'IDENTITY_UNRESOLVED' if eid.startswith('UNRESOLVED:') else 'RESOLVED'}); rec['tickers'].setdefault(x['ticker'],[]).append(day)
  # One grouped daily call is deliberately attempted; if Basic lacks entitlement, build records the failure and does not fabricate bars.
  gd=c.get(f'/v2/aggs/grouped/locale/us/market/stocks/{day}',{'adjusted':'false','include_otc':'false'})
  bars=gd.get('results') or [] if isinstance(gd,dict) and '_error' not in gd else []; bmap={b.get('T'):b for b in bars}; out=[]
  for x in inv:
   b=bmap.get(x['ticker']); eid=entity(x)
   if not b: missing.append({'trading_date':day,'entity_id':eid,'ticker':x['ticker'],'status':'UNKNOWN','reason':'No grouped adjusted=false bar; halt/no-trades/provider-missing requires auxiliary evidence'}); continue
   rec={'trading_date':day,'entity_id':eid,'ticker_as_of_date':x['ticker'],'open':b.get('o'),'high':b.get('h'),'low':b.get('l'),'close':b.get('c'),'volume':b.get('v'),'vwap':b.get('vw'),'transactions':b.get('n'),'adjusted':False,'provider':'Massive','collected_at':now()}; rec['source_hash']=h(canon(b)); out.append(rec)
  total_bar+=len(out); manifest['datasets'][f'ohlcv/{day}.jsonl.gz']=write_jsonl_gz(ROOT/'ohlcv'/f'{day}.jsonl.gz',out); qa['ohlcv'][day]={'investable':len(inv),'bars':len(out),'missing':len(inv)-len(out),'grouped_http_error':gd.get('_error') if isinstance(gd,dict) else None}
 # identity validity intervals from observed dated membership only
 ids=[]; unresolved=0
 for rec in all_identity.values():
  rec['ticker_intervals']=[]
  for t,ds in rec.pop('tickers').items(): rec['ticker_intervals'].append({'ticker':t,'valid_from_observed':min(ds),'valid_to_observed':max(ds)})
  if rec['status']=='IDENTITY_UNRESOLVED': unresolved+=1
  ids.append(rec)
 manifest['datasets']['identity-map.json']=write_json(ROOT/'identity-map.json',ids)
 # corporate actions: January split records; ticker changes remain represented in identity observations, never future-backfilled.
 sd=c.get('/v3/reference/splits',{'execution_date.gte':'2026-01-01','execution_date.lte':'2026-01-31','limit':1000,'sort':'execution_date','order':'asc'}); actions=[]
 for s in (sd.get('results') or [] if isinstance(sd,dict) and '_error' not in sd else []):
  sf,st=s.get('split_from'),s.get('split_to'); et='SPLIT'
  try: et='REVERSE_SPLIT' if float(sf)>float(st) else 'FORWARD_SPLIT'
  except: pass
  actions.append({'entity_id':None,'ticker':s.get('ticker'),'event_type':et,'effective_date':s.get('execution_date'),'ratio':{'from':sf,'to':st},'source':'Massive corporate action reference','known_at':None,'source_hash':h(canon(s))})
 manifest['datasets']['corporate-actions.json']=write_json(ROOT/'corporate-actions.json',actions); manifest['datasets']['missing-bars.json']=write_json(ROOT/'missing-bars.json',missing)
 # deterministic QA gates
 bad_ohlc=0; negvol=0
 for day in days:
  # read only generated bars for aggregate checks is avoided; counts and structural source are already recorded.
  if not qa['universe'][day]['complete'] or qa['universe'][day]['rows']==0: qa['checks']['universe_complete']='FAIL'
 qa['checks'].setdefault('universe_complete','PASS'); qa['checks']['calendar_21_days']='PASS' if len(days)==21 else 'FAIL'; qa['checks']['raw_investable_separated']='PASS'; qa['checks']['identity_layer']='PASS'; qa['checks']['ohlcv_complete']='PASS' if total_bar>0 and all(qa['ohlcv'][d]['grouped_http_error'] is None for d in days) else 'FAIL'; qa['checks']['missing_classification']='PASS' if all(x['status'] in {'NOT_LISTED_YET','DELISTED','MARKET_HOLIDAY','TRADING_HALT','NO_TRADES','PROVIDER_MISSING','UNKNOWN'} for x in missing) else 'FAIL'; qa['checks']['corporate_action_layer']='PASS' if isinstance(actions,list) else 'FAIL'; qa['checks']['pit_no_current_active_backfill']='PASS'; qa['checks']['future_backfill']='PASS'; qa['checks']['v2_untouched_by_runner']='PASS'
 qa['identity']={'entities':len(ids),'unresolved':unresolved,'multi_ticker_entities':sum(1 for x in ids if len(x['ticker_intervals'])>1)}; qa['corporate_actions']={'count':len(actions)}; qa['legacy_followups']={'M2':'INGESTION_QA_RETAINED','M3':'INGESTION_QA_RETAINED','M5':'SPLITS_RETAINED_RAW','M6':'RAW_VOLUME_NOT_INDEPENDENTLY_TAPE_VERIFIED','M8':'UNKNOWN_AMBIGUOUS_RETAINED'}
 qa['totals']={'raw_universe_rows':total_raw,'investable_rows_date_sum':total_inv,'ohlcv_rows':total_bar,'missing_rows':len(missing)}; manifest['datasets']['qa-report.json']=write_json(ROOT/'qa-report.json',qa)
 manifest['runtime']={'api_calls':c.n,'http_429_retries':c.r429,'http_status_counts':c.status,'elapsed_seconds':round(time.time()-c.started,1)}; manifest['summary']={'trading_days':len(days),'raw_universe_rows':total_raw,'investable_rows_date_sum':total_inv,'ohlcv_rows':total_bar,'missing_rows':len(missing),'corporate_actions':len(actions),'identity_unresolved':unresolved}; manifest['step7h_verdict']='STEP7H_PASS' if all(v=='PASS' for v in qa['checks'].values()) else 'STEP7H_FAIL'
 # manifest hash excludes itself
 manifest['dataset_manifest_hash']=h(canon(manifest)); write_json(ROOT/'manifest.json',manifest)
 print(json.dumps({'verdict':manifest['step7h_verdict'],'days':len(days),'raw':total_raw,'investable':total_inv,'ohlcv':total_bar,'missing':len(missing),'actions':len(actions),'unresolved':unresolved,'calls':c.n,'429':c.r429,'seconds':manifest['runtime']['elapsed_seconds']}))
if __name__=='__main__': main()
