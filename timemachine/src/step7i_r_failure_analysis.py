from __future__ import annotations
import argparse,json
from pathlib import Path
from collections import Counter,defaultdict

def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.root); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 cps=[]; mans=[]
 for p in root.rglob('checkpoints.json'):
  cps += json.loads(p.read_text())
 for p in root.rglob('manifest.json'):
  try:
   m=json.loads(p.read_text())
   if 'http' in m and 'batch_id' in m: mans.append(m)
  except Exception: pass
 sc=Counter(x.get('status') for x in cps); reasons=defaultdict(list)
 for x in cps:
  e=x.get('error') or ''
  if x.get('status')=='RETRYABLE_ERROR' and 'UnicodeDecodeError' in e and "\\x1f\\x8b" in e: r='GZIP_RESPONSE_NOT_DECOMPRESSED'
  elif x.get('status')=='RETRYABLE_ERROR': r='OTHER_RETRYABLE_ERROR'
  elif x.get('status')=='PARTIAL': r='PARTIAL'
  elif x.get('status')=='PERMANENT_UNAVAILABLE': r='PERMANENT_UNAVAILABLE'
  else: r='COMPLETE'
  reasons[r].append(x.get('cik'))
 classes=[]
 for r,ciks in sorted(reasons.items()):
  classes.append({'reason':r,'cik_count':len(ciks),'representative_ciks':ciks[:10],'retry_required':r in {'GZIP_RESPONSE_NOT_DECOMPRESSED','OTHER_RETRYABLE_ERROR','PARTIAL'},'code_fix_required':r=='GZIP_RESPONSE_NOT_DECOMPRESSED','additional_sec_request_required':r in {'GZIP_RESPONSE_NOT_DECOMPRESSED','OTHER_RETRYABLE_ERROR','PARTIAL'}})
 http={k:sum(m.get('http',{}).get(k,0) for m in mans) for k in ['requests','200','403','404','429','5xx','retries','timeouts','parse_errors']}
 report={'source_run_id':40077670478,'unique_cik_records':len(cps),'status_counts':dict(sc),'http':http,'classifications':classes,'root_cause':'All 6,046 original CIK checkpoints were RETRYABLE_ERROR because SEC returned gzip bytes (magic 1f8b) after the collector explicitly requested gzip, while urllib response bytes were passed directly to json.loads without decompression.' if len(reasons.get('GZIP_RESPONSE_NOT_DECOMPRESSED',[]))==6046 else 'See classifications; root cause is evidence-derived, not assumed.'}
 retry=[x for x in cps if x.get('status') in {'PARTIAL','RETRYABLE_ERROR'}]
 (out/'failure-classification.json').write_text(canon(report)); (out/'retry-ciks.json').write_text(canon([{'cik':x.get('cik'),'entity_id':x.get('entity_id'),'prior_status':x.get('status')} for x in retry])); print(canon(report))
if __name__=='__main__': main()
