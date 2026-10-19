#!/usr/bin/env python3
import json, os, re, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'v2'/'data'; STOCKS=DATA/'stocks'
KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST); TODAY=NOW.strftime('%Y-%m-%d')
UA='MicrocapRadar/1.0 contact: github.com/y44195070-sudo/microcap-radar-'

def get_json(url, timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def load(p):
    with open(p,encoding='utf-8') as f:return json.load(f)
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with open(p,'w',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')

def yahoo(t):
    u='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(t)+'?range=10d&interval=1d&events=div%2Csplits'
    try:
        j=get_json(u); r=j['chart']['result'][0]; q=r['indicators']['quote'][0]; ts=r['timestamp']
        rows=[]
        for i,x in enumerate(ts):
            if q['close'][i] is None: continue
            rows.append({'date':datetime.fromtimestamp(x,timezone.utc).strftime('%Y-%m-%d'),'open':q['open'][i],'high':q['high'][i],'low':q['low'][i],'close':q['close'][i],'volume':q['volume'][i]})
        if not rows:return None
        cur=rows[-1]; prev=rows[-2] if len(rows)>1 else None
        if prev and prev['close']:
            cur['changePct']=round((cur['close']/prev['close']-1)*100,2)
            cur['intradayHighVsPrevClosePct']=round((cur['high']/prev['close']-1)*100,2)
        return cur
    except Exception as e:return {'error':str(e)[:180]}

def sec_map():
    try:
        j=get_json('https://www.sec.gov/files/company_tickers.json');return {v['ticker'].upper():str(v['cik_str']).zfill(10) for v in j.values()}
    except Exception:return {}

def sec_recent(cik):
    try:
        j=get_json(f'https://data.sec.gov/submissions/CIK{cik}.json'); r=j.get('filings',{}).get('recent',{})
        out=[]
        for i,form in enumerate(r.get('form',[])[:80]):
            if form in {'8-K','6-K','10-Q','10-K','20-F','F-1','F-1/A','S-1','S-1/A','F-3','F-3/A','S-3','S-3/A','424B3','424B4','EFFECT','DEF 14A','PRE 14A'}:
                out.append({'form':form,'filed':r['filingDate'][i],'accession':r['accessionNumber'][i]})
            if len(out)>=8:break
        return out
    except Exception:return []

def event_days(text):
    # yyyy-mm-dd or mm/dd dates in existing manually validated data
    dates=[]
    for y,m,d in re.findall(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})',text):
        try: dates.append(datetime(int(y),int(m),int(d),tzinfo=KST).date())
        except: pass
    for m,d in re.findall(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)',text):
        try:
            dt=datetime(NOW.year,int(m),int(d),tzinfo=KST).date()
            if -7 <= (dt-NOW.date()).days <= 120: dates.append(dt)
        except: pass
    future=[(x-NOW.date()).days for x in dates if (x-NOW.date()).days>=0]
    return min(future) if future else None

def main():
    manifest=load(DATA/'manifest.json'); cikmap=sec_map(); summary=[]
    for t in manifest:
        p=STOCKS/f'{t}.json'
        if not p.exists():continue
        d=load(p); old=d.get('autoUpdate',{}); px=yahoo(t); filings=sec_recent(cikmap[t]) if t in cikmap else []
        valid_px=px and 'error' not in px and px.get('close') and px.get('volume') is not None
        auto=dict(old)
        auto.update({'checkedAt':NOW.isoformat(),'priceSource':'Yahoo Finance chart API','secSource':'SEC EDGAR submissions','status':'ok' if valid_px else 'partial'})
        if valid_px:auto['market']=px
        else:auto['marketFetchError']=(px or {}).get('error','no market data')
        if filings:auto['recentSecFilings']=filings
        else:auto['secNote']='새 SEC 목록을 확인하지 못해 기존 분석값 유지'
        d['autoUpdate']=auto
        # Never overwrite manually researched structure/short/dilution fields on failed or conflicting fetches.
        save(p,d)
        txt=json.dumps(d,ensure_ascii=False); days=event_days(txt)
        summary.append({'ticker':t,'baseScore':d.get('score'), 'market':auto.get('market'), 'eventDays':days, 'secFresh':filings[0] if filings else None})
        time.sleep(.12)

    # Rebuild ranking safely: base structural score remains manual; daily market/SEC freshness becomes metadata.
    rp=DATA/'rankings.json'; ranks=load(rp) if rp.exists() else {'categories':[]}
    ranks['asOf']=TODAY; ranks['autoUpdatedAt']=NOW.isoformat(); by={x['ticker']:x for x in summary}
    for cat in ranks.get('categories',[]):
        if cat.get('id')=='structure':
            cat['items']=sorted([{'ticker':x['ticker'],'score':x['baseScore']} for x in summary if isinstance(x['baseScore'],(int,float))],key=lambda x:x['score'],reverse=True)
        elif cat.get('id')=='event':
            ev=[x for x in summary if x['eventDays'] is not None]
            ev.sort(key=lambda x:x['eventDays'])
            cat['items']=[{'ticker':x['ticker'],'score':None,'note':f"확인된 기존 일정까지 D-{x['eventDays']} · 최신 SEC {x['secFresh']['form']+' '+x['secFresh']['filed'] if x['secFresh'] else '추가 확인 필요'}"} for x in ev[:10]]
    save(rp,ranks)
    save(DATA/'update-status.json',{'updatedAt':NOW.isoformat(),'dateKST':TODAY,'tracked':len(summary),'marketValidated':sum(bool(x['market']) for x in summary),'secMapped':sum(x['ticker'] in cikmap for x in summary),'policy':'수집 실패/충돌 시 기존 수동 검증값 유지. 자동 수집값은 autoUpdate에 분리 저장.'})
    print(json.dumps({'date':TODAY,'tracked':len(summary),'marketValidated':sum(bool(x['market']) for x in summary)},ensure_ascii=False))
if __name__=='__main__':main()
