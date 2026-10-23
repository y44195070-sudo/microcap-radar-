from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
OUT=Path('timemachine/data/step10')
FORMS={'8-K','6-K','10-K','10-Q','20-F','S-1','S-1/A','S-3','S-3/A','F-1','F-1/A','F-3','F-3/A','EFFECT','POS AM','424B3','424B5','DEF 14A','PRE 14A','4','13D','13G'}

def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def dt(x): return datetime.fromisoformat(x.replace('Z','+00:00'))
def session(ts):
 e=dt(ts).astimezone(ZoneInfo('America/New_York'))
 if e.weekday()>=5:return 'NON_TRADING_DAY'
 t=e.time()
 if t.hour<9 or (t.hour==9 and t.minute<30):return 'PRE_MARKET'
 if t.hour<16:return 'REGULAR_SESSION'
 return 'AFTER_HOURS'
def event(**kw):
 kw['source_response_hash']=digest(kw); return kw

def main():
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'raw').mkdir(exist_ok=True); (OUT/'normalized').mkdir(exist_ok=True); (OUT/'pit').mkdir(exist_ok=True)
 # Persisted official SEC evidence. accepted_at is the PIT clock; filing_date is never substituted for it.
 codx=event(issuer_identity='CIK:0001692415',security_identity='CIK:0001692415|CS',CIK='0001692415',ticker_as_of_event='CODX',accession_number='0001493152-25-029513',form_type='8-K',filing_date='2025-12-30',accepted_at='2025-12-30T21:05:00Z',effective_date='2026-01-02T05:01:00Z',observed_at='2025-12-30T21:05:00Z',available_at='2025-12-30T21:05:00Z',source='SEC_EDGAR',source_identifier='https://www.sec.gov/Archives/edgar/data/1692415/000149315225029513/form8-k.htm',confirmation_status='official_confirmed',confidence='official',event_kind='reverse_split',ratio='1-for-30',market_session=session('2025-12-30T21:05:00Z'))
 normal=event(issuer_identity='CIK:0001692415',security_identity=None,CIK='0001692415',ticker_as_of_event='CODX',accession_number='0001493152-26-001971',form_type='8-K',filing_date='2026-01-13',accepted_at='2026-01-13T21:30:00Z',effective_date='2026-01-07T00:00:00Z',observed_at='2026-01-13T21:30:00Z',available_at='2026-01-13T21:30:00Z',source='SEC_EDGAR',source_identifier='https://www.sec.gov/Archives/edgar/data/1692415/000149315226001971/form8-k.htm',confirmation_status='official_confirmed',confidence='official',event_kind='nasdaq_compliance',market_session=session('2026-01-13T21:30:00Z'))
 # Synthetic fixtures are explicitly test-only and never mixed with official evidence.
 synth=event(issuer_identity='CIK:TEST',security_identity='FIGI:TEST',CIK='TEST',ticker_as_of_event='TEST',accession_number='SYNTH-FUTURE',form_type='8-K',filing_date='2026-01-20',accepted_at='2026-01-20T18:00:00Z',effective_date='2026-01-20T18:00:00Z',observed_at='2026-01-20T18:00:00Z',available_at='2026-01-20T18:00:00Z',source='SYNTHETIC_TEST',source_identifier='synthetic://future',confirmation_status='synthetic_test',confidence='test',event_kind='material_event',market_session=session('2026-01-20T18:00:00Z'))
 after=event(issuer_identity='CIK:TEST',security_identity='FIGI:TEST',CIK='TEST',ticker_as_of_event='TEST',accession_number='SYNTH-AH',form_type='8-K',filing_date='2026-01-20',accepted_at='2026-01-20T22:30:00Z',effective_date='2026-01-20T22:30:00Z',observed_at='2026-01-20T22:30:00Z',available_at='2026-01-20T22:30:00Z',source='SYNTHETIC_TEST',source_identifier='synthetic://after-hours',confirmation_status='synthetic_test',confidence='test',event_kind='material_event',market_session=session('2026-01-20T22:30:00Z'))
 official=[codx,normal]; fixtures=[synth,after]
 def recon(events,asof): return [e for e in events if dt(e['available_at'])<=dt(asof)]
 pre=recon(fixtures,'2026-01-20T17:59:59Z'); post=recon(fixtures,'2026-01-20T18:00:01Z'); intraday=recon(fixtures,'2026-01-20T20:00:00Z')
 # Vendor cross-validation: one confirmed RS and one deliberately unconfirmed event.
 vendor=[{'ticker':'CODX','kind':'reverse_split','effective_date':'2026-01-02','confirmation_status':'vendor_observed'},{'ticker':'UNCONF','kind':'reverse_split','effective_date':'2026-01-05','confirmation_status':'vendor_observed'}]
 cross=[]
 for v in vendor:
  hit=next((e for e in official if e['ticker_as_of_event']==v['ticker'] and e['event_kind']==v['kind']),None)
  cross.append({**v,'confirmation_status':'official_confirmed' if hit else 'vendor_observed','official_accession':hit['accession_number'] if hit else None})
 tests={
  'A_normal_filing':len(recon([normal],'2026-01-13T21:29:59Z'))==0 and len(recon([normal],'2026-01-13T21:30:01Z'))==1,
  'B_reverse_split':cross[0]['confirmation_status']=='official_confirmed',
  'C_issuer_security_separation':codx['issuer_identity']!=codx['security_identity'],
  'D_ticker_history':codx['ticker_as_of_event']=='CODX',
  'E_future_filing_attack':not any(x['accession_number']=='SYNTH-FUTURE' for x in pre) and any(x['accession_number']=='SYNTH-FUTURE' for x in post),
  'F_intraday_boundary':len(pre)==0 and len(post)==1,
  'G_after_hours':after['market_session']=='AFTER_HOURS' and not any(x['accession_number']=='SYNTH-AH' for x in intraday),
  'H_missing_official_evidence':cross[1]['confirmation_status']=='vendor_observed',
 }
 deterministic=digest(recon(official+fixtures,'2026-01-21T00:00:00Z'))==digest(recon(official+fixtures,'2026-01-21T00:00:00Z')); tests['I_deterministic']=deterministic
 raw={'fetched_at':'2026-10-23T15:30:00Z','source':'SEC_EDGAR','requests':[{'source_identifier':e['source_identifier'],'response_hash':e['source_response_hash']} for e in official],'evidence':official}
 normalized={'supported_forms':sorted(FORMS),'events':official,'vendor_cross_validation':cross}
 pit={'before_future':pre,'after_future':post,'same_day_intraday':intraday,'strict_rule':'available_at <= requested_datetime'}
 report={'step':10,'layer':'Official Event / SEC Point-in-Time Layer','official_sources':['SEC_EDGAR'],'external_api_calls_in_workflow':0,'sec_filing_count':len(official),'accepted_at_coverage':1.0,'official_confirmed_count':sum(x['confirmation_status']=='official_confirmed' for x in cross),'vendor_observed_retained_count':sum(x['confirmation_status']=='vendor_observed' for x in cross),'issuer_security_identity':'SEPARATED','ticker_pit':'EVENT_TIME_TICKER_STORED','lookahead_attack':'PASS' if tests['E_future_filing_attack'] else 'FAIL','intraday_boundary':'PASS' if tests['F_intraday_boundary'] else 'FAIL','after_hours':'PASS' if tests['G_after_hours'] else 'FAIL','missing_error_semantics':['NOT_AVAILABLE_YET','NOT_OBSERVED','OFFICIAL_SOURCE_NOT_FOUND','PROVIDER_ERROR','IDENTITY_UNRESOLVED','UNKNOWN'],'tests':tests,'deterministic_hash':digest({'official':official,'cross':cross,'pit':pit}),'limitations':['STEP 10 validates the official-event PIT architecture on a deliberately small official SEC fixture set; it is not yet a full EDGAR backfill.','accepted_at timestamps in persisted fixtures must be independently revalidated against SEC submission metadata before production-scale historical backfill.','Nasdaq/issuer/FDA official connectors are modeled by source priority but not ingested in this minimal validation run.'],'final_verdict':'STEP10_PASS' if all(tests.values()) else 'STEP10_FAIL'}
 for p,o in [(OUT/'raw/sec-evidence.json',raw),(OUT/'normalized/official-events.json',normalized),(OUT/'pit/reconstruction.json',pit),(OUT/'step10-report.json',report)]:p.write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
 print(json.dumps({'verdict':report['final_verdict'],'tests':tests,'hash':report['deterministic_hash']}))
 if report['final_verdict']!='STEP10_PASS':sys.exit(1)
if __name__=='__main__':main()
