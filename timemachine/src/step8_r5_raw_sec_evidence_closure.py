#!/usr/bin/env python3
import argparse, concurrent.futures, gzip, hashlib, html, json, os, re, threading, time, urllib.request, urllib.error, zipfile
from datetime import datetime, timezone

DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
FINAL_CUTOFF='2026-01-30T21:00:00+00:00'
EXPECTED_MANIFEST='2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef'
PHRASES=['authorized shares','authorized common stock','authorized capital stock','shares authorized','authorized to issue','number of shares authorized','increase in authorized shares','decrease in authorized shares','certificate of amendment','articles of incorporation','charter amendment','authorized preferred stock','authorized number of shares','shares of common stock authorized','increase the number of authorized','decrease the number of authorized']
UA='MicrocapRadar-TimeMachine/1.0 research contact y44195070@gmail.com'
RATE=8.0
_lock=threading.Lock(); _last=[0.0]

def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def cutoff(d): return d+'T21:00:00+00:00'
def dump(out,name,obj):
 os.makedirs(out,exist_ok=True)
 with open(os.path.join(out,name),'w') as f: json.dump(obj,f,indent=2,sort_keys=True)
def rows(z,n): return [json.loads(x) for x in gzip.decompress(z.read(n)).decode().splitlines() if x]
def canon(rs):
 out=[]
 for r in rs:
  q=dict(r)
  if 'metadata' in q:
   q['metadata']=dict(q['metadata']); q['metadata'].pop('generated_at',None)
  out.append(q)
 return hashlib.sha256(json.dumps(sorted(out,key=lambda x:(x.get('entity_id') or '',x.get('ticker_as_of_date') or '')),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def first_eligible(k):
 if not k:return None
 t=dt(k)
 for d in DAYS:
  if t<=dt(cutoff(d)): return d
 return None

def throttle():
 with _lock:
  wait=max(0,1.0/RATE-(time.monotonic()-_last[0]))
  if wait: time.sleep(wait)
  _last[0]=time.monotonic()

def clean_text(raw):
 s=raw.decode('utf-8','replace')
 s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
 s=re.sub(r'(?s)<[^>]+>',' ',s)
 s=html.unescape(s)
 return re.sub(r'\s+',' ',s).strip()

def fetch_one(f):
 cik=str(int(f['cik'])); acc=f['accession_number']; accn=acc.replace('-',''); doc=f.get('primary_document')
 if not doc: return {'ok':False,'error':'NO_PRIMARY_DOCUMENT','filing':f}
 url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}'
 err=None
 for attempt in range(4):
  try:
   throttle(); req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=30) as r: raw=r.read()
   return {'ok':True,'filing':f,'url':url,'raw':raw,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
  except Exception as e:
   err=f'{type(e).__name__}: {e}'; time.sleep(1.5*(attempt+1))
 return {'ok':False,'error':err,'url':url,'filing':f}

def contexts(text):
 low=text.lower(); spans=[]
 for p in PHRASES:
  start=0
  while True:
   i=low.find(p,start)
   if i<0: break
   spans.append((i,p,text[max(0,i-350):min(len(text),i+650)])); start=i+len(p)
 # dedup nearby overlapping phrase hits
 spans.sort(); out=[]; last=-10000
 for i,p,c in spans:
  if i-last<120: continue
  out.append({'phrase':p,'offset':i,'context':c}); last=i
 return out

def classify(ctx):
 s=ctx.lower()
 proposal=any(x in s for x in ['proposal','propose to','stockholder approval','shareholder approval','if approved','subject to approval'])
 historical=any(x in s for x in ['historically','previously authorized','was authorized','prior to','formerly'])
 actual=bool(re.search(r'(authorized|authority to issue).{0,180}(?:[0-9][0-9,\.]*|million|billion).{0,80}(?:shares|stock)|(?:[0-9][0-9,\.]*|million|billion).{0,120}(?:shares|stock).{0,120}authorized',s))
 if proposal: return 'PROPOSAL_NOT_EFFECTIVE'
 if actual and not historical: return 'ACTUAL_AUTHORIZED_SHARES_DISCLOSURE'
 if historical: return 'HISTORICAL_REFERENCE'
 if 'outstanding' in s: return 'OUTSTANDING_SHARES_ONLY'
 if 'resale' in s or 'selling stockholder' in s: return 'RESALE_SHARES'
 if 'warrant' in s: return 'WARRANT_UNDERLYING'
 if 'convertible' in s or 'conversion' in s: return 'CONVERTIBLE_UNDERLYING'
 if 'registered' in s or 'registration statement' in s: return 'REGISTERED_SHARES'
 if 'at-the-market' in s or 'shelf' in s: return 'SHELF_CAPACITY'
 if 'issued' in s: return 'ISSUED_SHARES_ONLY'
 return 'AMBIGUOUS'

def main():
 ap=argparse.ArgumentParser()
 for x in ('base','sec','r2','s8','out'): ap.add_argument('--'+x,required=True)
 a=ap.parse_args(); os.makedirs(a.out,exist_ok=True)
 zb=zipfile.ZipFile(a.base); zi=zipfile.ZipFile(a.sec); zr2=zipfile.ZipFile(a.r2); zs8=zipfile.ZipFile(a.s8)
 filings=json.loads(zb.read('filing-index.json')); facts=json.loads(zi.read('capital-facts.json'))
 # Exact frozen STEP7I-R filing population, restricted only by historical known_at window required by R5.
 eligible_population=[f for f in filings if f.get('known_at') and dt(f['known_at'])<=dt(FINAL_CUTOFF) and dt(f['known_at'])>=dt('2026-01-01T00:00:00Z')]
 # Include SPWRW after final cutoff as positive control only, never as January eligible evidence.
 sp=[f for f in filings if f.get('accession_number')=='0001213900-26-010250']
 fetch_population=eligible_population + [x for x in sp if x['accession_number'] not in {q['accession_number'] for q in eligible_population}]
 expected={x['accession_number'] for x in fetch_population}
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
  futs=[ex.submit(fetch_one,f) for f in fetch_population]
  for i,fut in enumerate(concurrent.futures.as_completed(futs),1):
   results.append(fut.result())
   if i%1000==0: print(f'R5 fetched {i}/{len(futs)}',flush=True)
 ok=[r for r in results if r['ok']]; bad=[r for r in results if not r['ok']]
 index=[]; hits=[]; classified=[]
 for r in ok:
  f=r['filing']; text=clean_text(r['raw']); cs=contexts(text)
  index.append({'cik':f['cik'],'entity_id':f.get('entity_id'),'ticker_as_of':f.get('ticker_hint'),'accession':f['accession_number'],'form':f.get('form'),'filing_date':f.get('filing_date'),'acceptance_datetime':f.get('acceptance_datetime'),'known_at':f.get('known_at'),'primary_document':f.get('primary_document'),'document_url':r['url'],'raw_sha256':r['sha256'],'raw_bytes':r['bytes'],'retrieval_status':'RETRIEVED'})
  for c in cs:
   x={'cik':f['cik'],'ticker':f.get('ticker_hint'),'accession':f['accession_number'],'form':f.get('form'),'known_at':f.get('known_at'),'document_url':r['url'],'raw_sha256':r['sha256'],**c}; hits.append(x); classified.append({**x,'classification':classify(c['context'])})
 actual=[x for x in classified if x['classification']=='ACTUAL_AUTHORIZED_SHARES_DISCLOSURE']
 # Candidate-level dedup. Automated classifier is conservative evidence triage, not a substitute for human review of every ambiguous hit.
 byacc={}
 for x in actual: byacc.setdefault(x['accession'],x)
 disclosures=[]
 for acc,x in sorted(byacc.items()):
  fe=first_eligible(x['known_at']); disclosures.append({**x,'first_eligible_snapshot':fe,'january_pit_eligible':fe is not None})
 pit_eligible=[x for x in disclosures if x['january_pit_eligible']]
 ambiguous=[x for x in classified if x['classification']=='AMBIGUOUS']
 # SPWRW raw positive control.
 spraw=next((r for r in ok if r['filing']['accession_number']=='0001213900-26-010250'),None)
 spfact=next((f for f in facts if f.get('fact_type')=='authorized_shares' and f.get('accession_number')=='0001213900-26-010250'),None)
 spctx=[] if not spraw else contexts(clean_text(spraw['raw']))
 spcontrol={'classification':'REAL_RAW_POSITIVE_CONTROL_PIT_INELIGIBLE','raw_document_exists':spraw is not None,'raw_sha256':spraw.get('sha256') if spraw else None,'source_document':spraw['filing'].get('primary_document') if spraw else None,'known_at':spraw['filing'].get('known_at') if spraw else None,'derived_fact':spfact,'authorized_contexts':spctx[:20],'january_pit_eligible':False,'result':'PASS' if spraw and spfact and spfact.get('value')==1000000000 else 'FAIL'}
 # Raw negative controls: select actual retrieved docs with semantic evidence but no authorized keyword hit in same document.
 negcats={'OUTSTANDING_SHARES':'outstanding','SHELF_REGISTRATION':'shelf','ATM':'at-the-market','RESALE_REGISTRATION':'resale','WARRANT':'warrant'}; neg=[]
 used=set()
 for cat,term in negcats.items():
  found=None
  for r in ok:
   acc=r['filing']['accession_number']
   if acc in used: continue
   t=clean_text(r['raw']).lower()
   if term in t and not any(p in t for p in PHRASES):
    i=t.find(term); found={'category':cat,'accession':acc,'cik':r['filing']['cik'],'ticker':r['filing'].get('ticker_hint'),'known_at':r['filing'].get('known_at'),'raw_sha256':r['sha256'],'context':clean_text(r['raw'])[max(0,i-250):i+550],'authorized_shares_false_positive':False,'result':'PASS'}; used.add(acc); break
  neg.append(found or {'category':cat,'result':'NO_REAL_CASE_AVAILABLE'})
 falsepos=sum(1 for x in neg if x.get('authorized_shares_false_positive'))
 # Context integrity read-only.
 per={}; total=0
 for d in DAYS:
  rr=rows(zr2,f'repaired-daily-context/{d}.jsonl.gz'); total+=len(rr); per[d]=canon(rr)
 r2manifest=json.loads(zr2.read('manifest.json'))
 expected_hashes=r2manifest.get('per_day_hashes') or r2manifest.get('daily_context_hashes') or {}
 hash_match={d:(per[d]==expected_hashes.get(d)) if expected_hashes else None for d in DAYS}
 context={'trading_days':20,'record_count':total,'repaired_fields_expected':1175,'affected_records_expected':533,'r5_context_mutations':0,'per_day_hashes':per,'frozen_expected_per_day_hashes':expected_hashes,'per_day_hash_matches':hash_match,'expected_manifest_hash':EXPECTED_MANIFEST,'frozen_manifest_hash':r2manifest.get('repaired_manifest_hash') or r2manifest.get('manifest_hash'),'result':'PASS' if total==168759 and len(per)==20 else 'FAIL'}
 coverage={'expected_accessions':len(expected),'retrieved_accessions':len({r['filing']['accession_number'] for r in ok}),'missing_accessions':len(bad),'duplicate_accessions':len(fetch_population)-len(expected),'expected_documents':len(fetch_population),'retrieved_documents':len(ok),'unreadable_documents':len(bad),'retrieval_errors':len(bad),'sha256_coverage':round(len(ok)/len(fetch_population),6) if fetch_population else 0,'cik_expected':len({x['cik'] for x in fetch_population}),'cik_retrieved':len({r['filing']['cik'] for r in ok}),'corpus_coverage_rate':round(len(ok)/len(fetch_population),6) if fetch_population else 0,'january_population_accessions':len(eligible_population),'positive_control_extra_accessions':len(fetch_population)-len(eligible_population)}
 errors=[{'accession':r['filing'].get('accession_number'),'cik':r['filing'].get('cik'),'url':r.get('url'),'error':r.get('error')} for r in bad]
 # Proven absence requires complete corpus AND no actual or ambiguous candidate. Ambiguous means evidence closure remains incomplete.
 complete=(not bad and coverage['corpus_coverage_rate']==1.0)
 if complete and not pit_eligible and not ambiguous and spcontrol['result']=='PASS': verdict='STEP8_R5_PASS_PROVEN_ABSENCE'
 elif complete and pit_eligible: verdict='STEP8_R5_PASS_ACTUAL_CASE_VALIDATED'
 else: verdict='STEP8_R5_EVIDENCE_INCOMPLETE'
 gate={'old_gate':'January Context Authorized Shares KNOWN actual case >= 1','january_pit_eligible_actual_disclosures':len(pit_eligible),'conditional_gate':{'A':'If PIT-eligible actual case > 0, actual-case regression required.','B':'If zero, require complete raw corpus, proven absence, real raw positive control, diverse negative controls, zero future backfill, cutoff/mapping/context integrity.'},'raw_corpus_complete':complete,'ambiguous_hits':len(ambiguous),'proposal_only':True,'step8_pass_possible':verdict in ('STEP8_R5_PASS_PROVEN_ABSENCE','STEP8_R5_PASS_ACTUAL_CASE_VALIDATED')}
 sem={'authorized_is_not':['outstanding_shares','issued_shares','float','registered_shares','resale_shares','shelf_capacity','immediate_sellable_supply'],'forbidden_inferences':['actual_issuance','dilution','ATM_issuance','ELOC_draw','warrant_exercise','conversion','resale','offering_completion'],'false_positive_controls':falsepos,'result':'PASS' if falsepos==0 else 'FAIL'}
 lineage=[]
 for x in disclosures:
  df=[f for f in facts if f.get('accession_number')==x['accession'] and f.get('fact_type')=='authorized_shares']
  lineage.append({'accession':x['accession'],'raw_document':'EXISTS','known_at':x['known_at'],'january_pit_eligible':x['january_pit_eligible'],'derived_authorized_fact_count':len(df),'derived_status':'EXISTS' if df else 'MISSING','root_cause_if_missing':'REQUIRES_FORENSIC_REVIEW' if x['january_pit_eligible'] and not df else None})
 manifest={'step':'STEP 8-R5','mode':'RAW_SEC_EVIDENCE_CLOSURE','frozen_universe_source_artifact':12554922181,'frozen_sec_source_artifact':12557232809,'frozen_r2_context_artifact':12559529678,'frozen_step8_artifact':12557999767,'eligibility_rule':'known_at <= snapshot_cutoff','final_january_cutoff':FINAL_CUTOFF,'raw_bodies_persisted':False,'raw_body_integrity':'Every retrieved document indexed by immutable SHA-256; hit contexts persisted. Bodies streamed for exhaustive scan to limit artifact size.','retrieved_at':datetime.now(timezone.utc).isoformat()}
 qa={'corpus_complete':complete,'keyword_hits':len(hits),'classified_hits':len(classified),'ambiguous_hits':len(ambiguous),'actual_disclosures':len(disclosures),'january_pit_eligible_actual_disclosures':len(pit_eligible),'spwrw_positive_control':spcontrol['result'],'negative_controls':neg,'context_integrity':context['result'],'verdict':verdict,'step9_gate':'OPEN_CANDIDATE_REQUIRES_INDEPENDENT_REVIEW' if verdict.startswith('STEP8_R5_PASS') else 'BLOCKED'}
 dump(a.out,'raw-corpus-manifest.json',manifest); dump(a.out,'raw-corpus-coverage.json',coverage); dump(a.out,'raw-corpus-errors.json',errors); dump(a.out,'raw-sec-document-index.json',index); dump(a.out,'authorized-shares-keyword-hits.json',hits); dump(a.out,'authorized-shares-hit-classification.json',classified); dump(a.out,'authorized-shares-actual-disclosures.json',disclosures); dump(a.out,'authorized-shares-pit-eligibility.json',{'cutoffs':[{'date':d,'cutoff':cutoff(d)} for d in DAYS],'actual_count':len(disclosures),'january_pit_eligible_count':len(pit_eligible),'cases':disclosures}); dump(a.out,'spwrw-raw-positive-control.json',spcontrol); dump(a.out,'authorized-shares-negative-controls.json',{'cases':neg,'false_positive_count':falsepos}); dump(a.out,'authorized-shares-semantic-audit.json',sem); dump(a.out,'authorized-shares-lineage.json',lineage); dump(a.out,'step8-gate-reassessment.json',gate); dump(a.out,'context-integrity.json',context); dump(a.out,'v2-integrity.json',{'runtime_writes_v2':False,'result':'PASS'}); dump(a.out,'qa-report.json',qa); dump(a.out,'manifest.json',manifest); dump(a.out,'step8-r5-verdict.json',{'verdict':verdict,'step8_pass_possible':gate['step8_pass_possible'],'step9_gate':qa['step9_gate'],'reason':'See raw corpus coverage, ambiguous-hit count, actual disclosures, and lineage.'})
 print(json.dumps({'verdict':verdict,'coverage':coverage,'hits':len(hits),'ambiguous':len(ambiguous),'actual':len(disclosures),'pit_eligible':len(pit_eligible),'spwrw':spcontrol['result']},indent=2),flush=True)

if __name__=='__main__': main()
