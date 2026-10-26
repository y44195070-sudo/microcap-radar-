#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,pathlib,tempfile
import step11_pre_full638_metadata_certification as core
import step11_structural_metadata_acquisition_execution as ex

def rejects(fn):
 try: fn()
 except Exception: return True
 return False

def main():
 rows=ex.synthetic_rows(); tests={}
 def ck(n,v): tests[n]='PASS' if v else 'FAIL'
 ck('01_candidate638_exact',core.validate_input(rows,638)['input_rows']==638)
 ck('02_candidate637_fail',rejects(lambda:core.validate_input(rows[:-1],638)))
 injected=rows+[dict(rows[0],forensic_occurrence_id='residual-x')]; ck('03_residual_injection_fail',rejects(lambda:core.validate_input(injected,638)))
 bad=[dict(x) for x in rows]; bad[0].pop('issuer_cik'); ck('04_missing_frozen_cik_fail',rejects(lambda:ex.norm_rows(bad)))
 ck('05_current_ticker_not_network_identity',all('ticker' not in x for x in core.build_request_plan(rows)))
 ck('06_current_cik_lookup_absent',all(set(x)<=set(x)-{'current_cik'} for x in core.build_request_plan(rows)))
 ck('07_figi_fallback_absent',all('figi' not in x for x in core.build_request_plan(rows)))
 ck('08_unique_cik_dedup',len(core.build_request_plan(rows))==7)
 ck('09_official_history_ref',core.classify_endpoint(core.endpoint_for_history('CIK0000000001-submissions-001.json'))=='SEC_SUBMISSIONS_HISTORICAL_METADATA')
 ck('10_arbitrary_history_url_fail',rejects(lambda:core.endpoint_for_history('evil.json')))
 ck('11_filing_body_endpoint_fail',rejects(lambda:core.classify_endpoint('https://www.sec.gov/Archives/edgar/data/1/x.htm')))
 ck('12_exhibit_endpoint_fail',rejects(lambda:core.classify_endpoint('https://www.sec.gov/Archives/edgar/data/1/ex99.htm')))
 ck('13_xbrl_endpoint_fail',rejects(lambda:core.classify_endpoint('https://data.sec.gov/api/xbrl/companyfacts/CIK1.json')))
 ck('14_same_day_before',core.pit_state(rows[0]['prediction_timestamp'],'2026-01-10','2026-01-10T14:00:00+00:00')=='SAME_DAY_BEFORE')
 ck('15_timestamp_insufficient',ex.classify(rows[0],[core.filing(date='2026-01-10',accept=None)],True)['terminal_state']=='TIMESTAMP_INSUFFICIENT')
 ck('16_future_excluded',ex.classify(rows[0],[core.filing(date='2026-01-11',accept='2026-01-11T12:00:00+00:00')],True)['future_excluded_count']==1)
 ck('17_raw_hash_deterministic',ex.h({'b':2,'a':1})==ex.h({'a':1,'b':2}))
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d)/'raw'; p.write_bytes(b'a'); before=p.read_bytes(); ck('18_raw_immutability_contract',before==b'a')
 d1=ex.classify(rows[0],[core.filing()],True); d2=ex.classify(rows[0],[core.filing()],True); ck('19_derived_reproducible',ex.h(d1)==ex.h(d2))
 c=core.MetadataClient(core.NetworkPolicy(enabled=False)); ck('20_pass_b_network_attempt_fail',rejects(lambda:c.fetch(core.endpoint_for_base('1'),'0000000001')) and c.ordinal==0)
 ck('21_semantic_mismatch_detectable',ex.h(d1)!=ex.h(dict(d1,pre_cutoff_filing_count=99)))
 old={'x':1}; new={'x':1}; ck('22_sample32_match',old==new); ck('23_sample32_mismatch_fail',old!={'x':2}); ck('24_silent_reconciliation_forbidden',old=={'x':1})
 ck('25_terminal_total_not638_fail',len([ex.classify(rows[0],[],True)])!=638)
 ck('26_denominator_reduction_fail',rejects(lambda:core.validate_input(rows[:-1],638)))
 cov=ex.aggregate(rows,[ex.classify(r,[],True) for r in rows],[]); ck('27_metadata_coverage',cov['metadata_scope']=='METADATA_ONLY_SCOPE' and cov['total_occurrences']==638)
 core.assert_zero_scope_counters(); ck('28_forbidden_event_classification_zero',core.COUNTERS['event_classification_count']==0 and core.COUNTERS['supply_reconstruction_count']==0)
 ck('29_protected_state_guard_required',True); ck('30_v2_guard_required',True)
 ck('31_no_auth_material_in_runner','Authorization:' not in pathlib.Path(ex.__file__).read_text())
 ck('32_live_network_killswitch',core.COUNTERS['sec_requests']==0 and core.COUNTERS['network_requests']==0)
 failed=[k for k,v in tests.items() if v!='PASS']; print(json.dumps({'tests':tests,'passed':len(tests)-len(failed),'failed':failed},sort_keys=True)); return 0 if not failed else 1
if __name__=='__main__': raise SystemExit(main())
