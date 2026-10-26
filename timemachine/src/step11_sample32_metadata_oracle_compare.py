#!/usr/bin/env python3
"""Compare newly acquired metadata with immutable Sample32 raw SEC evidence without overwriting either side."""
import argparse,hashlib,json,pathlib
import step11_pre_full638_metadata_certification as core
import step11_structural_metadata_acquisition_execution as ex
class OracleError(RuntimeError): pass

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--oracle-dir',required=True); ap.add_argument('--input638',required=True); ap.add_argument('--pass-a',required=True); ap.add_argument('--out',required=True); ap.add_argument('--acquisition-state'); a=ap.parse_args()
 od=pathlib.Path(a.oracle_dir); rows={r['forensic_occurrence_id']:r for r in ex.norm_rows(ex.load_rows(pathlib.Path(a.input638)))}; new={r['forensic_occurrence_id']:r for r in json.loads(pathlib.Path(a.pass_a).read_text())['derived']}
 state_by_cik={}
 if a.acquisition_state:
  st=json.loads(pathlib.Path(a.acquisition_state).read_text())
  state_by_cik={x['issuer_cik']:x for x in st.get('rows',[])}
 sel=json.loads((od/'expansion_selected_occurrences.json').read_text()); ids=sel['occurrences']
 if len(ids)!=32: raise OracleError('SAMPLE32_COUNT_MISMATCH')
 results=[]; mismatches=[]
 for oid in ids:
  if oid not in rows or oid not in new: raise OracleError('SAMPLE32_OCCURRENCE_MISSING:'+oid)
  files=list((od/'raw_sec').glob(oid+'_submissions_*.bin'))
  if len(files)!=1: raise OracleError('SAMPLE32_RAW_EVIDENCE_MISSING_OR_AMBIGUOUS:'+oid)
  raw=files[0].read_bytes(); sha=hashlib.sha256(raw).hexdigest(); obj=json.loads(raw); oldfilings=core.parse_recent(obj,sha,'IMMUTABLE_SAMPLE32_ORACLE'); old=ex.classify(rows[oid],oldfilings,True)
  oldset=set(old['pit_safe_accessions']); newset=set(new[oid]['pit_safe_accessions']); missing=sorted(oldset-newset)
  cik=rows[oid]['issuer_cik']; ast=state_by_cik.get(cik); incomplete=(new[oid].get('terminal_state')=='SOURCE_ACQUISITION_INCOMPLETE' or (ast is not None and not ast.get('acquisition_complete',False)))
  if incomplete: status='NEW_ACQUISITION_INCOMPLETE'
  elif missing: status='ORACLE_ACCESSION_MISSING_FROM_COMPLETE_NEW_ACQUISITION'
  elif old['terminal_state']!=new[oid].get('terminal_state'): status='PIT_SEMANTIC_MISMATCH'
  else: status='EXACT_ORACLE_MATCH'
  rec={'forensic_occurrence_id':oid,'issuer_cik':cik,'oracle_raw_sha256':sha,'oracle_pit_safe_count':len(oldset),'new_pit_safe_count':len(newset),'missing_oracle_accessions':missing,'new_terminal_state':new[oid].get('terminal_state'),'acquisition_complete':None if ast is None else ast.get('acquisition_complete'),'status':status}; results.append(rec)
  if status!='EXACT_ORACLE_MATCH': mismatches.append(rec)
 report={'policy':'CANDIDATE_WIDE_REACQUISITION_WITH_IMMUTABLE_SAMPLE32_ORACLE','oracle_mutated':False,'sample_count':32,'comparisons':results,'material_mismatches':len(mismatches),'diagnostic_distribution':dict(sorted(__import__('collections').Counter(x['status'] for x in results).items())),'PASS':not mismatches}
 pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
 if mismatches:
  if any(x['status']=='NEW_ACQUISITION_INCOMPLETE' for x in mismatches): raise OracleError('NEW_ACQUISITION_INCOMPLETE_CANNOT_COMPARE_ORACLE')
  raise OracleError('SOURCE_DRIFT_OR_EVIDENCE_MISMATCH')
 print('SAMPLE32_IMMUTABLE_ORACLE_PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
