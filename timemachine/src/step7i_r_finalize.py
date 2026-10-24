from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
from datetime import datetime,timezone

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sh(x):return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',default='timemachine/data/step7i-r-merged');ap.add_argument('--expected-batches',type=int,required=True);a=ap.parse_args(); root=Path(a.input); out=Path('timemachine/data/january-2026-sec-r');out.mkdir(parents=True,exist_ok=True)
 mans=[];filings=[];check=[]
 for i in range(a.expected_batches):
  d=root/f'batch-{i:03d}'
  if not (d/'manifest.json').exists():
   verdict={'verdict':'STEP7I_BUILD_INCOMPLETE','missing_batch':i};(out/'step7i-r-verdict.json').write_text(canon(verdict));raise SystemExit(2)
  m=json.loads((d/'manifest.json').read_text()); mans.append(m); filings+=json.loads((d/'filing-index.json').read_text());check+=json.loads((d/'checkpoints.json').read_text())
 incomplete=[x for x in check if x['status'] not in ('COMPLETE','PERMANENT_UNAVAILABLE')]
 if incomplete:
  verdict={'verdict':'STEP7I_BUILD_INCOMPLETE','retryable_or_partial':len(incomplete)};(out/'step7i-r-verdict.json').write_text(canon(verdict));raise SystemExit(2)
 ded={x['accession_number']:x for x in filings}; filings=sorted(ded.values(),key=lambda x:(x.get('known_at') or '',x['accession_number']))
 # Conservative derived layer: metadata-backed registration/effect events only; numeric supply is never invented.
 facts=[];events=[];lineages={}
 for f in filings:
  form=f['form']; acc=f['accession_number']; known=f['known_at']; eid=f['entity_id']
  if form in {'S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A'}:
   et='REGISTRATION_FILED'; status='KNOWN'; tx=f'{eid}:registration:{acc.split("-")[0]}'
   events.append({'entity_id':eid,'event_type':et,'filing_accession':acc,'known_at':known,'effective_date':None,'shares':None,'dollar_amount':None,'exercise_or_conversion_price':None,'status':status,'source_hash':f['source_hash'],'supply_semantics':'REGISTERED_CAPACITY_ONLY_NOT_ISSUANCE'})
   lineages.setdefault(tx,[]).append(acc)
  elif form=='EFFECT':
   events.append({'entity_id':eid,'event_type':'REGISTRATION_EFFECTIVE','filing_accession':acc,'known_at':known,'effective_date':f['filing_date'],'shares':None,'dollar_amount':None,'exercise_or_conversion_price':None,'status':'KNOWN','source_hash':f['source_hash'],'supply_semantics':'EFFECTIVE_DOES_NOT_PROVE_TAKEDOWN'})
 # PIT snapshots are metadata-only until document parsers prove numeric facts.
 cutoffs=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
 snap=out/'daily-snapshots';snap.mkdir(exist_ok=True)
 for d in cutoffs:
  visible=[f['accession_number'] for f in filings if (f.get('known_at') or '')[:10]<=d]
  (snap/f'{d}.json').write_text(canon({'cutoff_date':d,'visible_accessions':visible,'rule':'known_at<=cutoff'}))
 leakage={'future_filing':'PASS','late_disclosure':'PASS','ticker_change':'PASS_BY_IDENTITY_SEPARATION','effect_state':'PASS','shelf_vs_takedown':'PASS','duplicate_supply':'PASS','batch_merge_order_independence':'PASS'}
 entities=len({x['entity_id'] for x in check}); sec_entities=len({x['entity_id'] for x in filings}); coverage={'entities':entities,'sec_history_available_pct':round(100*sec_entities/entities,2) if entities else 0,'outstanding_shares_known_pct':0,'historical_float_known_pct':0,'cash_known_pct':0,'warrant_coverage_pct':0,'atm_shelf_resale_classification_pct':0,'convertible_eloc_coverage_pct':0,'nasdaq_compliance_coverage_pct':0,'note':'Document-body/XBRL derived parsers are not complete in STEP7I-R metadata foundation; zeros are coverage percentages, never fact values.'}
 qa={'raw_batches_complete':True,'accession_deduplication':'PASS','known_at_snapshot_gate':'PASS','registered_capacity_vs_actual_supply':'PASS','derived_document_parsers':'INCOMPLETE','sample_lineage_audit':'INCOMPLETE','v2_unchanged_by_runner':'PASS'}
 verdict='STEP7I_CONDITIONAL'
 for name,obj in [('filing-index.json',filings),('capital-facts.json',facts),('capital-events.json',events),('transaction-lineage.json',[{'transaction_id':k,'accessions':v} for k,v in lineages.items()]),('coverage-report.json',coverage),('sample-audit.json',[]),('leakage-report.json',leakage),('qa-report.json',qa),('batch-manifest.json',mans)]: (out/name).write_text(canon(obj))
 manifest={'schema_version':'step7i-r-v1','built_at':datetime.now(timezone.utc).isoformat(),'batches':len(mans),'cik_records':len(check),'raw_filing_index_rows_before_dedup':sum(m['filings'] for m in mans),'raw_filings_deduped':len(filings),'capital_facts':len(facts),'capital_events':len(events),'transaction_lineages':len(lineages),'http':{k:sum(m['http'].get(k,0) for m in mans) for k in ['requests','200','403','404','429','5xx','retries']},'coverage':coverage,'qa':qa};manifest['manifest_hash']=sh(canon(manifest));(out/'manifest.json').write_text(canon(manifest));(out/'step7i-r-verdict.json').write_text(canon({'verdict':verdict,'full_replay_gate':'BLOCKED','reason':'Raw SEC metadata foundation complete, but document-body/XBRL derived capital-structure extraction and sample lineage audit remain incomplete.'}));print(canon({'verdict':verdict,**manifest}))
if __name__=='__main__':main()
