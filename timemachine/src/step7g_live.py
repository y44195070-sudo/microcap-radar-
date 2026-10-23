from __future__ import annotations
import hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE='https://api.massive.com'
OUT=Path('timemachine/data/massive-live-coverage-2026-01.json')
DATES=['2026-01-02','2026-01-16','2026-01-30']

def now(): return datetime.now(timezone.utc).isoformat()
def sha(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class Client:
    def __init__(self):
        self.key=os.getenv('MASSIVE_API_KEY')
        if not self.key: raise RuntimeError('BLOCKED_API_KEY_NOT_CONNECTED')
        self.calls=0
    def get(self,path,params=None):
        q=dict(params or {}); q['apiKey']=self.key
        url=path if path.startswith('http') else BASE+path
        sep='&' if '?' in url else '?'
        req=Request(url+sep+urlencode(q),headers={'User-Agent':'MicrocapRadar-TimeMachine/step7g'})
        try:
            with urlopen(req,timeout=45) as r: data=json.load(r)
        except HTTPError as e:
            body=e.read().decode('utf-8','replace')[:1000]
            return {'_http_error':e.code,'_body':body}
        self.calls+=1
        time.sleep(12.2)  # Basic documented 5 calls/min ceiling
        return data

def public_query(params):
    return {k:v for k,v in params.items() if k.lower()!='apikey'}

def page_universe(c,date):
    params={'market':'stocks','date':date,'limit':1000,'sort':'ticker','order':'asc'}
    path='/v3/reference/tickers'; rows=[]; pages=0; hashes=[]
    while True:
        d=c.get(path,params); pages+=1
        if '_http_error' in d: return {'status':'FAIL','error':d,'count':len(rows),'pages':pages}
        hashes.append(sha(d)); rows.extend(d.get('results') or [])
        nxt=d.get('next_url')
        if not nxt: break
        u=urlparse(nxt); path=u.path; pq=parse_qs(u.query); params={k:v[-1] for k,v in pq.items() if k!='apiKey'}
        if pages>=30: return {'status':'PARTIAL','reason':'pagination safety stop','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}
    return {'status':'PASS','count':len(rows),'pages':pages,'rows':rows,'hashes':hashes}

def agg(c,ticker,date):
    params={'adjusted':'false','limit':50000,'sort':'asc'}
    d=c.get(f'/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}',params)
    if '_http_error' in d: return {'status':'FAIL','error':d}
    r=(d.get('results') or [])
    return {'status':'PASS' if r else 'UNVERIFIED','bar':r[0] if r else None,'response_hash':sha(d),'query_parameters':params}

def main():
    c=Client(); collected=now()
    report={'step':'7G','provider':'Massive','provider_plan_claimed':'Stocks Basic','collected_at':collected,'source_quality':'VENDOR_RECONSTRUCTED_PIT','secret_present':True,'m_tests':{},'evidence':{},'notes':[]}
    universes={}
    for d in DATES:
        u=page_universe(c,d); rows=u.pop('rows',[]); universes[d]=rows
        venues={}; types={}
        for r in rows:
            venues[r.get('primary_exchange','UNKNOWN')]=venues.get(r.get('primary_exchange','UNKNOWN'),0)+1
            types[r.get('type','UNKNOWN')]=types.get(r.get('type','UNKNOWN'),0)+1
        u['venue_counts']=venues; u['security_type_counts']=types
        report['evidence'].setdefault('M1',{})[d]=u
    m1='PASS' if all(report['evidence']['M1'][d]['status']=='PASS' and report['evidence']['M1'][d]['count']>0 for d in DATES) else 'FAIL'
    report['m_tests']['M1']={'status':m1,'description':'Historical date universe API'}

    # Basic entitlement + raw OHLCV smoke test on liquid names; this proves endpoint access, not RS semantics.
    smoke=[]
    for t in ['AAPL','MSFT','NVDA','AMZN','META']:
        smoke.append({'ticker':t,'date':'2026-01-16',**agg(c,t,'2026-01-16')})
    report['evidence']['M7']=smoke
    report['m_tests']['M7']={'status':'PASS' if all(x['status']=='PASS' for x in smoke) else 'FAIL','description':'adjusted=false OHLCV endpoint live access; cross-source raw semantics still requires RS test'}

    # M8 is evidenced by returned reference fields, but classification completeness is evaluated conservatively.
    has_exchange=has_type=False
    for rows in universes.values():
        has_exchange |= any(r.get('primary_exchange') for r in rows)
        has_type |= any(r.get('type') for r in rows)
    report['m_tests']['M8']={'status':'PARTIAL' if has_exchange and has_type else 'FAIL','description':'Exchange/type fields present; mapping completeness not yet cross-checked'}

    # M2-M6/M9 require curated event samples + official cross-check; never auto-PASS from docs.
    for k,desc in {
      'M2':'Delisted survivorship 5 samples','M3':'New listing 3 samples','M4':'Ticker change/entity 3 samples',
      'M5':'Reverse split raw price 5 samples','M6':'Reverse split raw volume','M9':'Halt vs missing'
    }.items(): report['m_tests'][k]={'status':'UNVERIFIED','description':desc}

    report['m_tests']['M10']={'status':'PASS' if m1=='PASS' and report['m_tests']['M7']['status']=='PASS' else 'PARTIAL','description':'Basic entitlement observed for historical reference + adjusted=false aggregate endpoints','api_calls':c.calls,'rate_limit_assumption':'5 calls/min; runner throttled 12.2s/call'}
    core=[report['m_tests'][k]['status'] for k in ['M1','M2','M5','M6','M7']]
    report['final_verdict']='MASSIVE_PASS' if all(x=='PASS' for x in core) else ('MASSIVE_FAIL' if any(x=='FAIL' for x in core) else 'MASSIVE_CONDITIONAL')
    report['notes'].append('No API key or authenticated URL is persisted. Raw response hashes only.')
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'calls':c.calls,'M1':m1,'M7':report['m_tests']['M7']['status'],'verdict':report['final_verdict']}))

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(str(e),file=sys.stderr); raise
