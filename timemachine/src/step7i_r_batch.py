from __future__ import annotations
import argparse, gzip, hashlib, json, os, time, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('timemachine/data/january-2026'); OUT=Path('timemachine/data/step7i-r'); UA=os.getenv('SEC_USER_AGENT','MicrocapRadar-TimeMachine research contact y44195070@gmail.com')
FORMS={'10-K','10-Q','8-K','6-K','20-F','40-F','S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','POS AM','424B3','424B5','DEF 14A','PRE 14A','SC 13D','SC 13D/A','SC 13G','SC 13G/A','4'}

def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sh(x): return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def gzrows(p):
 with gzip.open(p,'rt',encoding='utf8') as f:
  for l in f:
   if l.strip(): yield json.loads(l)
def universe():
 ids={}
 for p in sorted((ROOT/'investable').glob('*.jsonl.gz')):
  for r in gzrows(p):
   cik=str(r.get('cik') or '').lstrip('0'); eid=r.get('entity_id');
   if cik: ids[cik]={'cik':cik,'entity_id':eid,'ticker':r.get('ticker')}
 return [ids[k] for k in sorted(ids,key=lambda x:int(x))]
class SEC:
 def __init__(self): self.stats={'requests':0,'200':0,'403':0,'404':0,'429':0,'5xx':0,'retries':0}; self.last=0
 def get(self,url):
  for n in range(5):
   wait=max(0,.13-(time.time()-self.last)); time.sleep(wait); self.last=time.time(); self.stats['requests']+=1
   try:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Encoding':'gzip, deflate','Host':'data.sec.gov'})
    with urllib.request.urlopen(req,timeout=30) as r:
     b=r.read(); self.stats['200']+=1; return b
   except urllib.error.HTTPError as e:
    k=str(e.code) if e.code in (403,404,429) else ('5xx' if e.code>=500 else str(e.code)); self.stats[k]=self.stats.get(k,0)+1
    if e.code==404:return None
    if e.code==429:
     delay=float(e.headers.get('Retry-After','1') or 1)
    elif e.code>=500 or e.code==403: delay=min(2**n,16)
    else: raise
    self.stats['retries']+=1; time.sleep(delay)
  return None

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--batch',type=int,required=True); ap.add_argument('--size',type=int,default=400); a=ap.parse_args(); start=time.time(); allu=universe(); lo=a.batch*a.size; rows=allu[lo:lo+a.size]; d=OUT/f'batch-{a.batch:03d}'; d.mkdir(parents=True,exist_ok=True); sec=SEC(); filings=[]; checkpoints=[]
 for u in rows:
  cik=u['cik']; status='COMPLETE'; err=None
  try:
   b=sec.get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json')
   if not b: status='PERMANENT_UNAVAILABLE'
   else:
    raw=json.loads(b); recent=raw.get('filings',{}).get('recent',{}); n=len(recent.get('accessionNumber',[]))
    for i in range(n):
     form=recent.get('form',['']*n)[i]
     if form not in FORMS: continue
     fd=recent.get('filingDate',['']*n)[i]
     if fd and fd>'2026-01-31': continue
     acc=recent['accessionNumber'][i]; at=(recent.get('acceptanceDateTime') or ['']*n)[i] if i<len(recent.get('acceptanceDateTime') or []) else ''
     filings.append({'entity_id':u['entity_id'],'cik':cik,'ticker_hint':u['ticker'],'form':form,'accession_number':acc,'filing_date':fd,'acceptance_datetime':at,'known_at':at or fd,'primary_document':recent.get('primaryDocument',['']*n)[i],'source_id':f'CIK{int(cik):010d}.json','source_hash':sh(b),'status':'KNOWN'})
  except Exception as e: status='RETRYABLE_ERROR'; err=repr(e)
  checkpoints.append({'cik':cik,'entity_id':u['entity_id'],'status':status,'error':err})
 (d/'filing-index.json').write_text(canon(filings)); (d/'checkpoints.json').write_text(canon(checkpoints)); manifest={'schema_version':'step7i-r-batch-v1','batch_id':a.batch,'batch_size':a.size,'universe_total_unique_cik':len(allu),'slice':[lo,lo+len(rows)],'ciks':[x['cik'] for x in rows],'completed':sum(x['status']=='COMPLETE' for x in checkpoints),'failed':sum(x['status']!='COMPLETE' for x in checkpoints),'filings':len(filings),'http':sec.stats,'elapsed_seconds':round(time.time()-start,2),'built_at':datetime.now(timezone.utc).isoformat(),'filing_index_sha256':sh((d/'filing-index.json').read_bytes()),'checkpoint_sha256':sh((d/'checkpoints.json').read_bytes())}; (d/'manifest.json').write_text(canon(manifest)); print(canon(manifest))
if __name__=='__main__': main()
