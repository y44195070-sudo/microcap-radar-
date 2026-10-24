from __future__ import annotations
import argparse, gzip, hashlib, json, os, time, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('timemachine/data/january-2026'); OUT=Path('timemachine/data/step7i-r-repair'); UA=os.getenv('SEC_USER_AGENT','MicrocapRadar-TimeMachine research contact y44195070@gmail.com')
FORMS={'10-K','10-Q','8-K','6-K','20-F','40-F','S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','POS AM','424B3','424B5','DEF 14A','PRE 14A','SC 13D','SC 13D/A','SC 13G','SC 13G/A','4'}
LOOKBACK_FROM='2022-01-01'; CUTOFF='2026-01-31'

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
   cik=str(r.get('cik') or '').lstrip('0'); eid=r.get('entity_id')
   if cik: ids[cik]={'cik':cik,'entity_id':eid,'ticker':r.get('ticker')}
 return [ids[k] for k in sorted(ids,key=lambda x:int(x))]

class SEC:
 def __init__(self): self.stats={'requests':0,'200':0,'403':0,'404':0,'429':0,'5xx':0,'retries':0,'timeouts':0,'parse_errors':0}; self.last=0
 def get(self,url):
  for n in range(5):
   wait=max(0,.13-(time.time()-self.last)); time.sleep(wait); self.last=time.time(); self.stats['requests']+=1
   try:
    # Request identity encoding. SEC frequently returns gzip when explicitly requested; urllib does not auto-decompress it.
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json','Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=30) as r:
     b=r.read(); enc=(r.headers.get('Content-Encoding') or '').lower()
     if enc=='gzip' or b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
     self.stats['200']+=1; return b,'OK'
   except urllib.error.HTTPError as e:
    k=str(e.code) if e.code in (403,404,429) else ('5xx' if e.code>=500 else str(e.code)); self.stats[k]=self.stats.get(k,0)+1
    if e.code==404:return None,'NOT_FOUND'
    if e.code==429: delay=float(e.headers.get('Retry-After','1') or 1)
    elif e.code>=500 or e.code==403: delay=min(2**n,16)
    else: return None,f'HTTP_{e.code}'
    self.stats['retries']+=1; time.sleep(delay)
   except TimeoutError:
    self.stats['timeouts']+=1; self.stats['retries']+=1; time.sleep(min(2**n,16))
   except Exception:
    self.stats['retries']+=1; time.sleep(min(2**n,16))
  return None,'RETRY_EXHAUSTED'

def rows_from_recent(recent,u,source_id,source_hash):
 out=[]; accs=recent.get('accessionNumber') or []; n=len(accs)
 for i in range(n):
  form=(recent.get('form') or ['']*n)[i] if i<len(recent.get('form') or []) else ''
  if form not in FORMS: continue
  fd=(recent.get('filingDate') or ['']*n)[i] if i<len(recent.get('filingDate') or []) else ''
  if fd and (fd>CUTOFF or fd<LOOKBACK_FROM): continue
  at=(recent.get('acceptanceDateTime') or ['']*n)[i] if i<len(recent.get('acceptanceDateTime') or []) else ''
  pd=(recent.get('primaryDocument') or ['']*n)[i] if i<len(recent.get('primaryDocument') or []) else ''
  out.append({'entity_id':u['entity_id'],'cik':u['cik'],'ticker_hint':u['ticker'],'form':form,'accession_number':accs[i],'filing_date':fd,'acceptance_datetime':at,'known_at':at or fd,'primary_document':pd,'source_id':source_id,'source_hash':source_hash,'status':'KNOWN'})
 return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--batch',type=int,required=True); ap.add_argument('--size',type=int,default=400); a=ap.parse_args(); start=time.time(); allu=universe(); lo=a.batch*a.size; rows=allu[lo:lo+a.size]; d=OUT/f'batch-{a.batch:03d}'; d.mkdir(parents=True,exist_ok=True); sec=SEC(); filings=[]; checkpoints=[]; hist_needed=0; hist_files=0
 for u in rows:
  cik=u['cik']; status='COMPLETE'; err=None; history=[]
  try:
   b,state=sec.get(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json')
   if state=='NOT_FOUND': status='PERMANENT_UNAVAILABLE'
   elif not b: status='RETRYABLE_ERROR'; err=state
   else:
    try: raw=json.loads(b)
    except Exception as e: sec.stats['parse_errors']+=1; raise RuntimeError(f'primary_json_parse:{e!r}')
    filings += rows_from_recent(raw.get('filings',{}).get('recent',{}),u,f'CIK{int(cik):010d}.json',sh(b))
    old=raw.get('filings',{}).get('files') or []
    eligible=[]
    for x in old:
     ffrom=x.get('filingFrom') or ''; fto=x.get('filingTo') or ''
     if ffrom<=CUTOFF and (not fto or fto>=LOOKBACK_FROM): eligible.append(x)
    if eligible: hist_needed+=1
    for x in eligible:
     name=x.get('name');
     if not name: continue
     hb,hstate=sec.get('https://data.sec.gov/submissions/'+name)
     if not hb:
      if hstate!='NOT_FOUND': status='PARTIAL'; history.append({'name':name,'status':hstate})
      else: history.append({'name':name,'status':'NOT_FOUND'})
      continue
     try: hraw=json.loads(hb)
     except Exception as e:
      sec.stats['parse_errors']+=1; status='PARTIAL'; history.append({'name':name,'status':'PARSE_ERROR','error':repr(e)}); continue
     filings += rows_from_recent(hraw,u,name,sh(hb)); hist_files+=1; history.append({'name':name,'status':'COMPLETE'})
  except Exception as e: status='RETRYABLE_ERROR'; err=repr(e)
  checkpoints.append({'cik':cik,'entity_id':u['entity_id'],'status':status,'error':err,'historical_files':history})
 # Dedup within batch while preserving source lineage by accession.
 ded={}
 for f in filings:
  acc=f['accession_number']; ded.setdefault(acc,f)
 filings=sorted(ded.values(),key=lambda x:(x.get('known_at') or '',x['accession_number']))
 (d/'filing-index.json').write_text(canon(filings)); (d/'checkpoints.json').write_text(canon(checkpoints))
 counts={k:sum(x['status']==k for x in checkpoints) for k in ['COMPLETE','PARTIAL','RETRYABLE_ERROR','PERMANENT_UNAVAILABLE']}
 manifest={'schema_version':'step7i-r-repair-batch-v2','batch_id':a.batch,'batch_size':a.size,'universe_total_unique_cik':len(allu),'slice':[lo,lo+len(rows)],'ciks':[x['cik'] for x in rows],'status_counts':counts,'historical_lookback_from':LOOKBACK_FROM,'historical_files_needed_ciks':hist_needed,'historical_files_fetched':hist_files,'filings':len(filings),'http':sec.stats,'elapsed_seconds':round(time.time()-start,2),'built_at':datetime.now(timezone.utc).isoformat(),'filing_index_sha256':sh((d/'filing-index.json').read_bytes()),'checkpoint_sha256':sh((d/'checkpoints.json').read_bytes())}; (d/'manifest.json').write_text(canon(manifest)); print(canon(manifest))
if __name__=='__main__': main()
