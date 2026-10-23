from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
from datetime import date
ROOT=Path('timemachine/data/step8'); OUT=Path('timemachine/data/step9'); DATES=['2026-01-02','2026-01-16','2026-01-30']

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def asof(ts,d): return bool(ts) and ts[:10] <= d

def data():
 sec=load(ROOT/'normalized/securities.json'); acts=load(ROOT/'normalized/corporate-actions.json'); raw=load(ROOT/'raw/sample-ohlcv.json')['rows']
 return sec,acts,raw

def classify_market(raw,ticker,d):
 xs=[x for x in raw if x['ticker']==ticker and x['trading_date']==d]
 if not xs: return {'status':'NOT_OBSERVED','raw_ohlcv':None}
 x=xs[0]
 if x['status']=='FAIL': return {'status':'PROVIDER_ERROR','raw_ohlcv':None,'source_response_hash':x.get('response_hash')}
 if not x.get('bar'): return {'status':'MISSING_MARKET_DATA','raw_ohlcv':None,'source_response_hash':x.get('response_hash')}
 return {'status':'AVAILABLE','raw_ohlcv':x['bar'],'source_response_hash':x.get('response_hash')}

def reconstruct(query,d,sec,acts,raw,synthetic=None):
 eligible=[r for r in sec if r['trading_date']<=d and asof(r.get('available_at'),d)]
 byid=str(query).startswith('CIK:') or str(query).startswith('BBG')
 if byid: matches=[r for r in eligible if r['stable_id']==query]
 else: matches=[r for r in eligible if r['ticker']==query]
 if not matches:
  future=[r for r in sec if (r['stable_id']==query if byid else r['ticker']==query) and r['trading_date']>d]
  return {'requested_date':d,'requested_ticker':None if byid else query,'requested_stable_id':query if byid else None,'status':'NOT_AVAILABLE_YET' if future else 'UNKNOWN','confidence':'unknown','verification_state':'not_observed'}
 latest=max(matches,key=lambda r:r['trading_date']); sid=latest['stable_id']; ticker=latest['ticker']
 hist=sorted([{'date':r['trading_date'],'ticker':r['ticker']} for r in eligible if r['stable_id']==sid],key=lambda x:x['date'])
 ev=[a for a in acts if a.get('ticker') in {h['ticker'] for h in hist} and asof(a.get('available_at'),d) and a.get('effective_date','9999')<=d]
 if synthetic: ev += [a for a in synthetic if a.get('ticker') in {h['ticker'] for h in hist} and asof(a.get('available_at'),d) and a.get('effective_date','9999')<=d]
 m=classify_market(raw,ticker,d)
 present=any(r['trading_date']==d and r['stable_id']==sid for r in sec)
 later=any(r['trading_date']>d and r['stable_id']==sid for r in sec)
 listing='ACTIVE_OBSERVED' if present else ('DISAPPEARED_BY_SNAPSHOT' if not later else 'NOT_OBSERVED_ON_DATE')
 return {'requested_date':d,'requested_ticker':None if byid else query,'requested_stable_id':query if byid else None,'stable_id':sid,'ticker_as_of_date':ticker,'ticker_history_known_as_of_date':hist,'primary_exchange':latest.get('primary_exchange'),'security_type':latest.get('security_type'),'active':latest.get('active'),'market_data':m,'canonical_price_policy':'adjusted=false','corporate_actions':ev,'ticker_change':len({h['ticker'] for h in hist})>1,'listing_observation':listing,'source':latest.get('source'),'effective_date':latest.get('effective_date'),'observed_at':latest.get('observed_at'),'available_at':latest.get('available_at'),'source_response_hash':latest.get('source_response_hash'),'confirmation_status':'vendor_observed' if ev else 'NOT_OBSERVED','confidence':'vendor_observed','verification_state':'official_confirmation_separate'}

def main():
 sec,acts,raw=data(); OUT.mkdir(parents=True,exist_ok=True)
 cases=[]
 def add(name,q,d):
  r=reconstruct(q,d,sec,acts,raw); cases.append({'name':name,'query':q,'date':d,'result':r}); return r
 a=add('A_control','AAPL','2026-01-16')
 b1=add('B_RS_pre','CODX','2026-01-02'); b2=add('B_RS_post','CODX','2026-01-16')
 c1=add('C_identity_1','CIK:0002083689','2026-01-02'); c2=add('C_identity_2','CIK:0002083689','2026-01-16'); c3=add('C_identity_3','CIK:0002083689','2026-01-30')
 d=add('D_disappears','AMDU','2026-01-30'); e0=add('E_new_before','ADAMO','2026-01-02'); e1=add('E_new_after','ADAMO','2026-01-30')
 unknown=add('G_unknown','ZZZZ_NONEXISTENT_9','2026-01-16')
 synth={'kind':'synthetic_future_event','ticker':'AAPL','effective_date':'2026-01-20','observed_at':'2026-01-20T00:00:00Z','available_at':'2026-01-20T00:00:00Z','confirmation_status':'synthetic_test'}
 attack=reconstruct('AAPL','2026-01-15',sec,acts,raw,[synth]); leak=any(x.get('kind')=='synthetic_future_event' for x in attack.get('corporate_actions',[]))
 deterministic=digest([reconstruct(x['query'],x['date'],sec,acts,raw) for x in cases])==digest([reconstruct(x['query'],x['date'],sec,acts,raw) for x in cases])
 tests={
 'A_control':a.get('ticker_as_of_date')=='AAPL',
 'B_reverse_split':any(x.get('kind')=='reverse_split' for x in b1.get('corporate_actions',[])+b2.get('corporate_actions',[])),
 'C_identity_transition':[c1.get('ticker_as_of_date'),c2.get('ticker_as_of_date'),c3.get('ticker_as_of_date')]==['AEAQU','AEAQU','AEAQW'],
 'D_disappearance':d.get('listing_observation')!='ACTIVE_OBSERVED',
 'E_new_listing':e0.get('status')=='NOT_AVAILABLE_YET' and e1.get('ticker_as_of_date')=='ADAMO',
 'F_future_leak_attack':not leak,
 'G_unknown_semantics':unknown.get('status')=='UNKNOWN',
 'deterministic':deterministic,
 'raw_policy':all(x['result'].get('canonical_price_policy','adjusted=false')=='adjusted=false' for x in cases),
 }
 report={'step':9,'engine':'PIT Query / Reconstruction Engine','source':'STEP 8 persisted PIT/normalized/raw data','external_api_calls':0,'tested_dates':DATES,'cases':cases,'future_leak_regression':{'injected':synth,'requested_date':'2026-01-15','leaked':leak,'result':'PASS' if not leak else 'FAIL'},'missing_error_semantics':['NOT_AVAILABLE_YET','NOT_OBSERVED','MISSING_MARKET_DATA','PROVIDER_ERROR','UNKNOWN'],'tests':tests,'deterministic_hash':digest(cases),'limitations':['STEP 8 sample OHLCV exists only for selected sample tickers/dates; NOT_OBSERVED is distinct from provider failure.','Corporate actions remain vendor_observed until an official SEC/Nasdaq/issuer event layer confirms them.','Listing/disappearance is snapshot observation, not issuer-event causality.'],'final_verdict':'STEP9_PASS' if all(tests.values()) else 'STEP9_FAIL'}
 (OUT/'step9-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
 (OUT/'reconstruction-cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
 print(json.dumps({'output':str(OUT/'step9-report.json'),'verdict':report['final_verdict'],'tests':tests,'hash':report['deterministic_hash']}))
 if report['final_verdict']!='STEP9_PASS': sys.exit(1)
if __name__=='__main__': main()
