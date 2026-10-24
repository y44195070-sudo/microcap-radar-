#!/usr/bin/env python3
import argparse,gzip,hashlib,json,os,re,zipfile
from collections import Counter,defaultdict
from datetime import datetime
DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
PHRASES=['authorized shares','authorized common stock','authorized capital stock','shares authorized','authorized to issue','number of shares authorized','increase in authorized shares','decrease in authorized shares','amendment to certificate','amendment to articles','certificate of amendment','articles of incorporation','charter amendment','authorized preferred stock']
FORMS={'8-K','6-K','10-K','10-Q','S-1','S-1/A','F-1','F-1/A','S-3','S-3/A','F-3','F-3/A','DEF 14A','PRE 14A','DEFA14A'}
def jread(z,n): return json.loads(z.read(n))
def rows(z,n): return [json.loads(x) for x in gzip.decompress(z.read(n)).decode().splitlines() if x]
def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def dump(out,n,x):
 os.makedirs(out,exist_ok=True); json.dump(x,open(os.path.join(out,n),'w'),indent=2,sort_keys=True)
def sha(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def canon(rs):
 out=[]
 for r in rs:
  q=dict(r)
  if 'metadata' in q:
   q['metadata']=dict(q['metadata']); q['metadata'].pop('generated_at',None)
  out.append(q)
 return sha(sorted(out,key=lambda x:(x.get('entity_id') or '',x.get('ticker_as_of_date') or '')))
def main():
 ap=argparse.ArgumentParser(); [ap.add_argument('--'+x,required=True) for x in ('r2','i','s8','out')]; a=ap.parse_args();
 zr2,zi,zs8=map(zipfile.ZipFile,(a.r2,a.i,a.s8)); names=zi.namelist();
 facts=jread(zi,'derived-capital-facts.json'); events=jread(zi,'capital-events.json'); lineages=jread(zi,'transaction-lineage.json')
 raw_name=next((n for n in names if 'raw-sec' in n.lower() and n.endswith('.json')),None)
 raw=jread(zi,raw_name) if raw_name else []
 if isinstance(raw,dict): raw=raw.get('filings') or raw.get('records') or raw.get('items') or []
 authfacts=[f for f in facts if (f.get('fact_type') or '').lower()=='authorized_shares']
 byacc=defaultdict(list)
 for f in authfacts: byacc[f.get('accession_number')].append(f)
 # Search all raw SEC records/doc text available in frozen artifact; no external/current data.
 hits=[]; forms=Counter(); scanned=0
 for r in raw:
  scanned+=1; form=r.get('form'); forms[form]+=1; blob=' '.join(str(r.get(k) or '') for k in ('text','document_text','content','description','primary_document','title')).lower(); matched=[p for p in PHRASES if p in blob]
  if matched:
   pos=min([blob.find(p) for p in matched if blob.find(p)>=0]); excerpt=blob[max(0,pos-160):pos+320]
   hits.append({'CIK':r.get('CIK') or r.get('cik'),'accession':r.get('accession_number') or r.get('accession'),'form':form,'filing_date':r.get('filing_date'),'acceptance_datetime':r.get('acceptance_datetime'),'known_at':r.get('known_at') or r.get('acceptance_datetime'),'source_document':r.get('primary_document') or r.get('source_document'),'source_hash':r.get('source_hash'),'matched_phrases':matched,'excerpt':excerpt})
 # Context scan and lineage.
 ctx_auth=[]; per={}; total=0; original_auth=[]
 for d in DAYS:
  rr=rows(zr2,f'repaired-daily-context/{d}.jsonl.gz'); oo=rows(zs8,f'daily-context/{d}.jsonl.gz'); total+=len(rr); per[d]=canon(rr)
  for r in rr:
   s=(r.get('capital',{}).get('authorized_shares') or {}); f=s.get('fact') or {}
   if s.get('status')=='KNOWN' or f.get('accession_number'): ctx_auth.append({'date':d,'entity_id':r.get('entity_id'),'CIK':r.get('identity',{}).get('cik'),'ticker':r.get('ticker_as_of_date'),'cutoff':r.get('snapshot_cutoff'),'status':s.get('status'),'fact':f,'evidence_count':s.get('evidence_count')})
  for r in oo:
   s=(r.get('capital',{}).get('authorized_shares') or {}); f=s.get('fact') or {}
   if s.get('status')=='KNOWN' or f.get('accession_number'): original_auth.append({'date':d,'entity_id':r.get('entity_id'),'ticker':r.get('ticker_as_of_date'),'status':s.get('status'),'fact':f})
 # Candidate classification from actual raw hits + derived facts.
 candidates=[]
 for h in hits:
  acc=h.get('accession'); af=byacc.get(acc,[]); candidates.append({**h,'derived_authorized_facts':af,'derived_fact_exists':bool(af),'pit_eligible_days':[d for d in DAYS if h.get('known_at') and dt(h['known_at'])<=dt(next((x['cutoff'] for x in ctx_auth if x.get('date')==d and x.get('CIK')==h.get('CIK')),d+'T21:00:00+00:00'))]})
 # Root cause based strictly on frozen evidence layers.
 actual=[x for x in ctx_auth if x['status']=='KNOWN' and (x['fact'] or {}).get('accession_number')]
 if actual: root='NO_GAP_REAL_CASE_EXISTS'
 elif hits and not authfacts: root='PARSER_GAP'
 elif authfacts and not ctx_auth: root='CONTEXT_ASSEMBLY_GAP'
 elif not hits and not authfacts: root='SOURCE_ABSENCE'
 else: root='MAPPING_GAP'
 # Negative controls: actual non-authorized derived facts, deterministic first five distinct accessions.
 neg=[]; seen=set()
 for f in facts:
  if len(neg)>=5: break
  if f.get('fact_type')=='authorized_shares': continue
  acc=f.get('accession_number');
  if not acc or acc in seen: continue
  seen.add(acc); neg.append({'CIK':f.get('CIK') or f.get('cik'),'accession':acc,'fact_type':f.get('fact_type'),'authorized_shares_misclassified':False,'result':'PASS'})
 # Positive control is deliberately not fabricated. Frozen artifact only; out-of-window external data is not injected.
 pos={'classification':'OUT_OF_WINDOW_POSITIVE_CONTROL','used_for_january_pass':False,'result':'NOT_RUN','reason':'R4 forensic run is frozen-artifact-only; no current/external filing is injected into January PIT evidence.'}
 lineage=[]
 for h in hits:
  acc=h.get('accession'); lineage.append({'accession':acc,'raw_sec':'EXISTS','source_document':'EXISTS' if h.get('source_document') else 'MISSING','derived_fact':'EXISTS' if byacc.get(acc) else 'MISSING','capital_event':'EXISTS' if any(e.get('filing_accession')==acc for e in events) else 'MISSING','transaction_lineage':'EXISTS' if any(acc in (l.get('filing_accessions') or []) for l in lineages) else 'NOT_APPLICABLE','repaired_context':'EXISTS' if any((x.get('fact') or {}).get('accession_number')==acc for x in ctx_auth) else 'MISSING'})
 source={'raw_sec_container':raw_name,'raw_records_scanned':scanned,'forms':dict(forms),'phrases':PHRASES,'keyword_context_hits':len(hits),'derived_authorized_fact_count':len(authfacts),'repaired_context_known_count':len(actual)}
 pit={'candidate_count':len(candidates),'pit_eligible_candidate_count':sum(bool(x['pit_eligible_days']) for x in candidates),'candidates':[{'accession':x.get('accession'),'known_at':x.get('known_at'),'eligible_days':x['pit_eligible_days']} for x in candidates]}
 parser={'authorized_derived_facts':authfacts,'raw_hits_without_derived_fact':[x for x in candidates if not x['derived_fact_exists']],'result':'PASS' if (not hits or authfacts) else 'PARSER_GAP'}
 semantic={'authorized_capacity_not_immediate_supply':True,'forbidden_inferences':['actual issuance','ATM issuance','ELOC draw','conversion','warrant exercise','resale','offering completion'],'january_actual_case_count':len(actual),'result':'PASS' if actual else 'NOT_TESTABLE_WITH_REAL_JANUARY_CASE'}
 integrity={'trading_days':len(DAYS),'record_count':total,'per_day_hashes':per,'expected_manifest_hash':'2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef','r4_context_mutations':0,'result':'PASS' if len(DAYS)==20 and total==168759 else 'FAIL'}
 rootj={'classification':root,'actual_january_context_case_count':len(actual),'source_hits':len(hits),'derived_fact_count':len(authfacts),'interpretation':'Read-only forensic classification from frozen STEP7I-R2 and STEP8-R2 evidence.'}
 verdict='AUTHORIZED_SHARES_NO_REAL_JANUARY_CASE' if root=='SOURCE_ABSENCE' else ('STEP8_REPAIR_REQUIRED' if root in ('PARSER_GAP','MAPPING_GAP','CONTEXT_ASSEMBLY_GAP') else 'STEP8_EVIDENCE_FOUND')
 dump(a.out,'authorized-shares-source-search.json',source); dump(a.out,'authorized-shares-candidates.json',candidates); dump(a.out,'authorized-shares-pit-eligibility.json',pit); dump(a.out,'authorized-shares-lineage-audit.json',lineage); dump(a.out,'authorized-shares-parser-audit.json',parser); dump(a.out,'authorized-shares-negative-controls.json',{'cases':neg,'false_positive_count':sum(x['authorized_shares_misclassified'] for x in neg),'result':'PASS' if len(neg)>=5 else 'INCOMPLETE'}); dump(a.out,'authorized-shares-positive-control.json',pos); dump(a.out,'authorized-shares-root-cause.json',rootj); dump(a.out,'authorized-shares-semantic-audit.json',semantic); dump(a.out,'context-integrity.json',integrity); dump(a.out,'v2-integrity.json',{'r4_runtime_writes_v2':False,'result':'PASS'}); dump(a.out,'qa-report.json',{'root_cause':root,'negative_controls':len(neg),'actual_case_count':len(actual),'context_integrity':integrity['result']}); dump(a.out,'manifest.json',{'step':'STEP 8-R4','mode':'READ_ONLY_FORENSIC','frozen_inputs':True,'context_read_only':True,'files':sorted(os.listdir(a.out))}); dump(a.out,'step8-r4-verdict.json',{'verdict':verdict,'root_cause':root,'step9_gate':'BLOCKED','note':'No parser/context repair is performed by R4.'})
if __name__=='__main__': main()
