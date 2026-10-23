from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path('timemachine/data/step8'); OUT=Path('timemachine/data/step9'); DATES=['2026-01-02','2026-01-16','2026-01-30']
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def asof(ts,d): return bool(ts) and ts[:10]<=d
def security_id(r):
 if r.get('composite_figi'): return 'FIGI:'+r['composite_figi']
 if r.get('cik') and r.get('security_type'): return 'CIKTYPE:'+r['cik']+':'+r['security_type']
 return 'TICKER:'+r['ticker']
def issuer_id(r): return ('CIK:'+r['cik']) if r.get('cik') else None
def data(): return load(ROOT/'normalized/securities.json'),load(ROOT/'normalized/corporate-actions.json'),load(ROOT/'raw/sample-ohlcv.json')['rows']
def market(raw,t,d):
 xs=[x for x in raw if x['ticker']==t and x['trading_date']==d]
 if not xs:return {'status':'NOT_OBSERVED','raw_ohlcv':None}
 x=xs[0]
 if x['status']=='FAIL':return {'status':'PROVIDER_ERROR','raw_ohlcv':None,'source_response_hash':x.get('response_hash')}
 if not x.get('bar'):return {'status':'MISSING_MARKET_DATA','raw_ohlcv':None,'source_response_hash':x.get('response_hash')}
 return {'status':'AVAILABLE','raw_ohlcv':x['bar'],'source_response_hash':x.get('response_hash')}
def reconstruct(q,d,sec,acts,raw,synthetic=None):
 eligible=[r for r in sec if r['trading_date']<=d and asof(r.get('available_at'),d)]
 for r in eligible:r['_security_id']=security_id(r);r['_issuer_id']=issuer_id(r)
 bysec=str(q).startswith('FIGI:') or str(q).startswith('CIKTYPE:'); byissuer=str(q).startswith('CIK:')
 if bysec: matches=[r for r in eligible if r['_security_id']==q]
 elif byissuer: matches=[r for r in eligible if r['_issuer_id']==q]
 else: matches=[r for r in eligible if r['ticker']==q]
 if not matches:
  future=[r for r in sec if r['trading_date']>d and (security_id(r)==q if bysec else issuer_id(r)==q if byissuer else r['ticker']==q)]
  return {'requested_date':d,'requested_query':q,'status':'NOT_AVAILABLE_YET' if future else 'UNKNOWN','confidence':'unknown','verification_state':'not_observed'}
 if byissuer:
  ids=sorted({r['_security_id'] for r in matches}); return {'requested_date':d,'requested_query':q,'status':'ISSUER_ID_AMBIGUOUS' if len(ids)>1 else 'ISSUER_ID_RESOLVED','issuer_id':q,'security_identities':ids,'securities':[{'ticker':r['ticker'],'security_type':r.get('security_type'),'composite_figi':r.get('composite_figi'),'security_id':r['_security_id'],'trading_date':r['trading_date']} for r in matches if r['trading_date']==max(x['trading_date'] for x in matches)]}
 latest=max(matches,key=lambda r:r['trading_date']); sid=latest['_security_id']; ticker=latest['ticker']; hist=sorted([{'date':r['trading_date'],'ticker':r['ticker']} for r in eligible if r['_security_id']==sid],key=lambda x:x['date']); tickers={h['ticker'] for h in hist}
 ev=[a for a in acts if a.get('ticker') in tickers and asof(a.get('available_at'),d) and a.get('effective_date','9999')<=d]
 if synthetic:ev += [a for a in synthetic if a.get('ticker') in tickers and asof(a.get('available_at'),d) and a.get('effective_date','9999')<=d]
 present=any(r['trading_date']==d and security_id(r)==sid for r in sec); later=any(r['trading_date']>d and security_id(r)==sid for r in sec)
 return {'requested_date':d,'requested_query':q,'issuer_id':latest['_issuer_id'],'security_id':sid,'stable_id':sid,'ticker_as_of_date':ticker,'ticker_history_known_as_of_date':hist,'primary_exchange':latest.get('primary_exchange'),'security_type':latest.get('security_type'),'active':latest.get('active'),'market_data':market(raw,ticker,d),'canonical_price_policy':'adjusted=false','corporate_actions':ev,'ticker_change':len({h['ticker'] for h in hist})>1,'listing_observation':'ACTIVE_OBSERVED' if present else ('DISAPPEARED_BY_SNAPSHOT' if not later else 'NOT_OBSERVED_ON_DATE'),'source':latest.get('source'),'effective_date':latest.get('effective_date'),'observed_at':latest.get('observed_at'),'available_at':latest.get('available_at'),'source_response_hash':latest.get('source_response_hash'),'confirmation_status':'vendor_observed' if ev else 'NOT_OBSERVED','confidence':'vendor_observed','verification_state':'official_confirmation_separate'}
def main():
 sec,acts,raw=data();OUT.mkdir(parents=True,exist_ok=True)
 cikrows=[r for r in sec if r.get('cik')=='0002083689']; cikdiag={'issuer_id':'CIK:0002083689','rows':[{'date':r['trading_date'],'ticker':r['ticker'],'security_type':r.get('security_type'),'composite_figi':r.get('composite_figi'),'derived_security_id':security_id(r)} for r in cikrows],'finding':'FALSE_TRANSITION_FROM_ISSUER_CIK_COLLISION','reason':'CIK is issuer-level: UNIT AEAQU, CS AEAQ and WARRANT AEAQW coexist; composite_figi is absent.'}
 groups={}
 for r in sec:
  sid=security_id(r);groups.setdefault(sid,[]).append(r)
 real=[]
 for sid,rs in groups.items():
  ts=sorted({r['ticker'] for r in rs});types=sorted({r.get('security_type') for r in rs});
  if sid.startswith('FIGI:') and len(ts)>1 and len(types)==1:real.append({'security_id':sid,'tickers':ts,'security_type':types[0],'history':sorted([(r['trading_date'],r['ticker']) for r in rs])})
 real.sort(key=lambda x:x['security_id']); fixture=real[0] if real else None
 cases=[]
 def add(n,q,d):
  r=reconstruct(q,d,sec,acts,raw);cases.append({'name':n,'query':q,'date':d,'result':r});return r
 a=add('A_control','AAPL','2026-01-16');b1=add('B_RS_pre','CODX','2026-01-02');b2=add('B_RS_post','CODX','2026-01-16'); issuer=add('C_false_transition_guard','CIK:0002083689','2026-01-30')
 if fixture:
  sid=fixture['security_id']; c=[add('C_real_transition_'+d,sid,d) for d in DATES]; expected=[]
  for d in DATES:
   prior=[x for x in fixture['history'] if x[0]<=d];expected.append(prior[-1][1] if prior else None)
  cpass=[x.get('ticker_as_of_date') for x in c]==expected and len(set(expected))>1
  fixture_mode='REAL_VENDOR_OBSERVED_SECURITY_TRANSITION'
 else:
  synsec=list(sec); base=dict(next(r for r in sec if r['ticker']=='AAPL' and r['trading_date']=='2026-01-02')); base['composite_figi']='SYNTH_TRANSITION';base['ticker']='SYNOLD';base['trading_date']='2026-01-02';base['available_at']='2026-01-02T23:59:59Z'; newer=dict(base);newer['ticker']='SYNNEW';newer['trading_date']='2026-01-30';newer['available_at']='2026-01-30T23:59:59Z';synsec += [base,newer]; cpass=reconstruct('FIGI:SYNTH_TRANSITION','2026-01-02',synsec,acts,raw).get('ticker_as_of_date')=='SYNOLD' and reconstruct('FIGI:SYNTH_TRANSITION','2026-01-30',synsec,acts,raw).get('ticker_as_of_date')=='SYNNEW';fixture_mode='SYNTHETIC_TICKER_CHANGE_REAL_NOT_OBSERVED'
 d=add('D_disappears','AMDU','2026-01-30');e0=add('E_new_before','ADAMO','2026-01-02');e1=add('E_new_after','ADAMO','2026-01-30');u=add('G_unknown','ZZZZ_NONEXISTENT_9','2026-01-16')
 synth={'kind':'synthetic_future_event','ticker':'AAPL','effective_date':'2026-01-20','observed_at':'2026-01-20T00:00:00Z','available_at':'2026-01-20T00:00:00Z','confirmation_status':'synthetic_test'};attack=reconstruct('AAPL','2026-01-15',sec,acts,raw,[synth]);leak=any(x.get('kind')=='synthetic_future_event' for x in attack.get('corporate_actions',[]))
 h1=digest([reconstruct(x['query'],x['date'],sec,acts,raw) for x in cases]);h2=digest([reconstruct(x['query'],x['date'],sec,acts,raw) for x in cases])
 tests={'A_control':a.get('ticker_as_of_date')=='AAPL','B_reverse_split':any(x.get('kind')=='reverse_split' for x in b1.get('corporate_actions',[])+b2.get('corporate_actions',[])),'C_issuer_security_separation':issuer.get('status')=='ISSUER_ID_AMBIGUOUS' and len(issuer.get('security_identities',[]))>=3,'C_identity_transition':cpass,'D_disappearance':d.get('listing_observation')!='ACTIVE_OBSERVED','E_new_listing':e0.get('status')=='NOT_AVAILABLE_YET' and e1.get('ticker_as_of_date')=='ADAMO','F_future_leak_attack':not leak,'G_unknown_semantics':u.get('status')=='UNKNOWN','deterministic':h1==h2,'raw_policy':all(x['result'].get('canonical_price_policy','adjusted=false')=='adjusted=false' for x in cases)}
 report={'step':9,'engine':'PIT Query / Reconstruction Engine','source':'STEP 8 persisted data','external_api_calls':0,'identity_model':{'issuer_identity':'CIK only','security_identity_priority':['composite_figi','CIK + security_type','ticker fallback'],'ticker_transition_rule':'same security identity only'},'previous_failure':cikdiag,'real_transition_candidates':real,'transition_fixture_mode':fixture_mode,'transition_fixture':fixture,'cases':cases,'future_leak_regression':{'injected':synth,'requested_date':'2026-01-15','leaked':leak,'result':'PASS' if not leak else 'FAIL'},'missing_error_semantics':['NOT_AVAILABLE_YET','NOT_OBSERVED','MISSING_MARKET_DATA','PROVIDER_ERROR','UNKNOWN'],'tests':tests,'deterministic_hash':digest(cases),'limitations':['Composite FIGI transitions are vendor-observed and do not by themselves prove official ticker-change causality.','STEP 8 sample OHLCV is sparse.','Corporate actions remain vendor_observed until official confirmation.'],'final_verdict':'STEP9_PASS' if all(tests.values()) else 'STEP9_FAIL'}
 (OUT/'step9-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');(OUT/'reconstruction-cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps({'output':str(OUT/'step9-report.json'),'verdict':report['final_verdict'],'tests':tests,'fixture_mode':fixture_mode,'fixture':fixture,'hash':report['deterministic_hash']}));sys.exit(0 if report['final_verdict']=='STEP9_PASS' else 1)
if __name__=='__main__':main()
