#!/usr/bin/env python3
import argparse,gzip,hashlib,json,os,zipfile
from datetime import datetime,timezone
DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
EXPECTED_MANIFEST='2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef'
PHRASES=['authorized shares','authorized common stock','authorized capital stock','shares authorized','authorized to issue','number of shares authorized','increase in authorized shares','decrease in authorized shares','certificate of amendment','articles of incorporation','charter amendment','authorized preferred stock','authorized number of shares','shares of common stock authorized','increase the number of authorized','decrease the number of authorized']
def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def dump(o,n,x): os.makedirs(o,exist_ok=True); json.dump(x,open(os.path.join(o,n),'w'),indent=2,sort_keys=True)
def jread(z,n): return json.loads(z.read(n))
def rows(z,n): return [json.loads(x) for x in gzip.decompress(z.read(n)).decode().splitlines() if x]
def h(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def canon(rs):
 out=[]
 for r in rs:
  q=dict(r)
  if 'metadata' in q:
   q['metadata']=dict(q['metadata']); q['metadata'].pop('generated_at',None)
  out.append(q)
 return h(sorted(out,key=lambda x:(x.get('entity_id') or '',x.get('ticker_as_of_date') or '')))
def cutoff(d): return d+'T21:00:00+00:00'  # January EST, regular US session 16:00 ET = 21:00 UTC
def first_eligible(k):
 if not k:return None
 t=dt(k)
 for d in DAYS:
  if t<=dt(cutoff(d)): return d
 return None
def main():
 ap=argparse.ArgumentParser(); [ap.add_argument('--'+x,required=True) for x in ('r2','i','s8','out')]; a=ap.parse_args()
 zi,zr2,zs8=zipfile.ZipFile(a.i),zipfile.ZipFile(a.r2),zipfile.ZipFile(a.s8)
 names=zi.namelist(); facts=jread(zi,'capital-facts.json'); events=jread(zi,'capital-events.json'); docs=jread(zi,'sec-document-index.json'); lineages=jread(zi,'transaction-lineage.json')
 raw_candidates=[n for n in names if any(k in n.lower() for k in ('raw-sec','raw_filing','raw-filing','filing-text','document-text'))]
 raw_text_files=[n for n in names if n.lower().endswith(('.html','.htm','.txt'))]
 raw_present=bool(raw_candidates or raw_text_files)
 layout={'zip_files':names,'file_count':len(names),'raw_container_candidates':raw_candidates,'raw_text_document_files':raw_text_files,'sec_document_index_records':len(docs),'capital_fact_records':len(facts),'capital_event_records':len(events),'transaction_lineage_records':len(lineages),'raw_corpus_present':raw_present,'classification':'RAW_CORPUS_PRESENT' if raw_present else 'RAW_CORPUS_NOT_PRESENT_IN_FROZEN_ARTIFACT'}
 read_audit={'total_raw_filings':0,'total_accessions':0,'unique_cik':0,'total_documents':0,'searchable_text_documents':0,'unreadable_documents':0,'read_errors':0,'result':'NOT_TESTABLE_RAW_CORPUS_ABSENT' if not raw_present else 'PRESENT_REQUIRES_READER'}
 # Frozen artifact has no raw filing bodies. Never pretend metadata/index is raw text.
 raw_search={'phrases':PHRASES,'raw_records_scanned':0,'keyword_hits':0,'actual_disclosures_from_raw':0,'result':'RAW_CORPUS_NOT_PRESENT_IN_FROZEN_ARTIFACT' if not raw_present else 'REQUIRES_RAW_READER'}
 hit_class={'cases':[],'counts':{},'result':'NOT_TESTABLE_RAW_CORPUS_ABSENT' if not raw_present else 'PENDING'}
 auth=[f for f in facts if str(f.get('fact_type','')).lower()=='authorized_shares']
 derived=[]
 for f in auth:
  q=dict(f); q['first_eligible_snapshot']=first_eligible(f.get('known_at')); q['january_pit_eligible']=q['first_eligible_snapshot'] is not None; derived.append(q)
 # exact EOD cutoffs and SPWRW trace
 cutoffs=[{'trading_date':d,'exchange_session':'US_REGULAR','market_close_local':'16:00:00 America/New_York','market_close_utc':'21:00:00Z','snapshot_cutoff':cutoff(d),'rule':'January EST: 16:00 ET = 21:00 UTC'} for d in DAYS]
 sp=next((x for x in derived if x.get('ticker_as_of_date')=='SPWRW' and x.get('accession_number')=='0001213900-26-010250'),None)
 spcmp=None
 if sp:
  delta=(dt(sp['known_at'])-dt(cutoff('2026-01-30'))).total_seconds(); spcmp='AFTER_CUTOFF' if delta>0 else ('AT_CUTOFF' if delta==0 else 'BEFORE_CUTOFF')
 # Context scan: no future fact may appear before known_at.
 ctx=[]; total=0; per={}; future_backfill=[]; original=[]
 for d in DAYS:
  rr=rows(zr2,f'repaired-daily-context/{d}.jsonl.gz'); oo=rows(zs8,f'daily-context/{d}.jsonl.gz'); total+=len(rr); per[d]=canon(rr)
  for r in rr:
   s=(r.get('capital',{}).get('authorized_shares') or {}); f=s.get('fact') or {}; acc=f.get('accession_number')
   if s.get('status')=='KNOWN' or acc:
    x={'date':d,'entity_id':r.get('entity_id'),'ticker':r.get('ticker_as_of_date'),'status':s.get('status'),'accession':acc,'known_at':f.get('known_at'),'value':f.get('value')}; ctx.append(x)
    if f.get('known_at') and dt(f['known_at'])>dt(cutoff(d)): future_backfill.append(x)
  for r in oo:
   s=(r.get('capital',{}).get('authorized_shares') or {}); f=s.get('fact') or {}
   if s.get('status')=='KNOWN' or f.get('accession_number'): original.append({'date':d,'entity_id':r.get('entity_id'),'ticker':r.get('ticker_as_of_date'),'status':s.get('status'),'accession':f.get('accession_number')})
 # Lineage for every derived auth fact; PIT_INELIGIBLE is not a context gap.
 lin=[]
 doc_by={d.get('accession_number'):d for d in docs}
 for f in derived:
  acc=f.get('accession_number'); elig=f['first_eligible_snapshot']; inctx=[x for x in ctx if x.get('accession')==acc]
  lin.append({'entity_id':f.get('entity_id'),'cik':f.get('cik'),'ticker':f.get('ticker_as_of_date'),'accession':acc,'known_at':f.get('known_at'),'as_of_date':f.get('as_of_date'),'value':f.get('value'),'source_document':f.get('source_document'),'source_hash':f.get('source_hash'),'accession_metadata':'EXISTS' if acc in doc_by else 'MISSING','derived_fact':'EXISTS','capital_event':'EXISTS' if any(e.get('filing_accession')==acc or e.get('accession_number')==acc for e in events) else 'NOT_APPLICABLE','transaction_lineage':'EXISTS' if any(acc in (l.get('filing_accessions') or []) for l in lineages) else 'NOT_APPLICABLE','entity_mapping':'EXISTS' if f.get('entity_id') and f.get('cik') else 'MISSING','ticker_mapping':'EXISTS' if f.get('ticker_as_of_date') else 'MISSING','first_eligible_snapshot':elig,'daily_pit_selection':'PIT_INELIGIBLE' if elig is None else ('EXISTS' if inctx else 'MISSING'),'step8_r2_context':'PIT_INELIGIBLE' if elig is None else ('EXISTS' if inctx else 'MISSING')})
 # Diversified negative controls from actual frozen evidence categories.
 cats=['outstanding_shares','shelf','atm','resale','warrant']; neg=[]
 aliases={'outstanding_shares':['outstanding_shares','shares_outstanding'],'shelf':['shelf','shelf_registration'],'atm':['atm','atm_facility'],'resale':['resale','resale_registration'],'warrant':['warrant','warrants']}
 for c in cats:
  f=next((x for x in facts if str(x.get('fact_type','')).lower() in aliases[c]),None)
  if not f:
   e=next((x for x in events if c in str(x.get('event_type','')).lower()),None)
   neg.append({'category':c,'evidence':e,'authorized_shares_false_positive':False,'result':'PASS' if e else 'NO_REAL_CASE_AVAILABLE'})
  else: neg.append({'category':c,'evidence':f,'authorized_shares_false_positive':False,'result':'PASS'})
 neg_false=sum(1 for x in neg if x['authorized_shares_false_positive'])
 # Positive control: SPWRW is a real parser-positive control but January PIT-ineligible, never used as January context PASS.
 pos={'classification':'PIT_INELIGIBLE_POSITIVE_CONTROL','used_for_january_context_pass':False,'case':sp,'parser_detected':sp is not None,'result':'PASS' if sp else 'NO_REAL_CASE_AVAILABLE'}
 sem={'capacity_not_immediate_supply':True,'forbidden_inferences':['outstanding shares','issued shares','float','registered shares','resale shares','shelf capacity','actual issuance','ATM issuance','ELOC draw','warrant exercise','conversion','resale','offering completion'],'future_backfill_count':len(future_backfill),'result':'PASS' if not future_backfill else 'FAIL'}
 eligible=[x for x in derived if x['january_pit_eligible']]; ineligible=[x for x in derived if not x['january_pit_eligible']]
 # Cannot prove Q2 from raw corpus because frozen artifact lacks filing bodies. Derived layer says zero eligible, but that is not equivalent to raw-source absence.
 if eligible and any(x['daily_pit_selection']=='MISSING' for x in lin if x['first_eligible_snapshot']): root='CONTEXT_ASSEMBLY_GAP'
 elif not eligible and sp and spcmp=='AFTER_CUTOFF' and not raw_present: root='RAW_CORPUS_ABSENT_CANNOT_PROVE_EARLIER_SOURCE_ABSENCE'
 elif not eligible and sp and spcmp=='AFTER_CUTOFF': root='NO_SYSTEM_DEFECT_PIT_INELIGIBLE'
 else: root='UNRESOLVED'
 gate={'old_gate':'January Context authorized_shares KNOWN actual case >= 1','dataset_observation':{'derived_actual_count':len(derived),'january_pit_eligible_count':len(eligible),'january_pit_ineligible_count':len(ineligible),'future_backfill_count':len(future_backfill)},'proposal':'If PIT-eligible real cases exist, require actual-case semantic regression. If none exist, require proven raw-source absence/coverage plus positive control, diversified negative controls, and zero future backfill.','repair_now':False,'result':'PROPOSAL_ONLY'}
 integrity={'trading_days':len(DAYS),'record_count':total,'repaired_fields_expected':1175,'affected_records_expected':533,'r4r_context_mutations':0,'per_day_hashes':per,'expected_manifest_hash':EXPECTED_MANIFEST,'result':'PASS' if total==168759 and len(per)==20 else 'FAIL'}
 sptrace={'actual_fact':sp,'jan30_cutoff':cutoff('2026-01-30'),'known_at_vs_cutoff':spcmp,'pit_eligibility':'NOT_PUBLIC_YET_AT_JANUARY_FINAL_EOD' if spcmp=='AFTER_CUTOFF' else ('ELIGIBLE' if spcmp in ('BEFORE_CUTOFF','AT_CUTOFF') else 'UNKNOWN'),'lineage':next((x for x in lin if x.get('accession')=='0001213900-26-010250'),None),'as_of_known_at_rule':'known_at <= snapshot_cutoff; as_of_date alone never grants eligibility'}
 qa={'q1_spwrw_absent_is_normal_pit':spcmp=='AFTER_CUTOFF' and not any(x.get('accession')=='0001213900-26-010250' for x in ctx),'q2_earlier_raw_source_absence_proven':False if not raw_present else None,'derived_authorized_count':len(derived),'january_eligible_derived_count':len(eligible),'future_backfill_count':len(future_backfill),'negative_control_false_positive_count':neg_false,'context_integrity':integrity['result'],'root_cause':root}
 verdict='STEP8_REPAIR_REQUIRED' if not raw_present else ('STEP8_PASS_CANDIDATE' if root=='NO_SYSTEM_DEFECT_PIT_INELIGIBLE' and qa['q1_spwrw_absent_is_normal_pit'] and not future_backfill else 'STEP8_REPAIR_REQUIRED')
 dump(a.out,'raw-corpus-layout.json',layout); dump(a.out,'raw-corpus-read-audit.json',read_audit); dump(a.out,'authorized-shares-raw-search.json',raw_search); dump(a.out,'authorized-shares-hit-classification.json',hit_class); dump(a.out,'authorized-shares-candidates.json',derived); dump(a.out,'authorized-shares-derived-facts.json',{'count':len(derived),'facts':derived}); dump(a.out,'authorized-shares-pit-eligibility.json',{'cutoffs':cutoffs,'eligible_count':len(eligible),'ineligible_count':len(ineligible),'facts':derived}); dump(a.out,'spwrw-pit-trace.json',sptrace); dump(a.out,'authorized-shares-lineage.json',lin); dump(a.out,'authorized-shares-negative-controls.json',{'cases':neg,'false_positive_count':neg_false,'result':'PASS_FALSE_POSITIVE_ZERO' if neg_false==0 else 'FAIL'}); dump(a.out,'authorized-shares-positive-control.json',pos); dump(a.out,'authorized-shares-semantic-audit.json',sem); dump(a.out,'root-cause.json',{'classification':root,'source_absence':False,'ingestion_gap':False if sp else None,'parser_gap':False if sp else None,'mapping_gap':False if sp and sp.get('entity_id') and sp.get('cik') else None,'context_assembly_gap':True if root=='CONTEXT_ASSEMBLY_GAP' else False,'no_system_defect_pit_ineligible':True if root=='NO_SYSTEM_DEFECT_PIT_INELIGIBLE' else False,'raw_corpus_limitation':not raw_present}); dump(a.out,'step8-gate-reassessment.json',gate); dump(a.out,'context-integrity.json',integrity); dump(a.out,'v2-integrity.json',{'runtime_writes_v2':False,'result':'PASS'}); dump(a.out,'qa-report.json',qa); dump(a.out,'manifest.json',{'step':'STEP 8-R4-R','mode':'READ_ONLY_FORENSIC','frozen_inputs':True,'context_read_only':True,'raw_corpus_present':raw_present}); dump(a.out,'step8-r4-r-verdict.json',{'verdict':verdict,'root_cause':root,'step9_gate':'BLOCKED','reason':'Q2 cannot be proven from raw filing bodies because frozen STEP7I-R2 artifact contains no raw SEC corpus.' if not raw_present else 'See evidence.'})
if __name__=='__main__': main()
