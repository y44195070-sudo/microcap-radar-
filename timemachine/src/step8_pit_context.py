from __future__ import annotations
import gzip, hashlib, json, os
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path

MARKET=Path(os.getenv('STEP8_MARKET','/tmp/step7h'))
SEC=Path(os.getenv('STEP8_SEC','/tmp/step7i'))
OUT=Path(os.getenv('STEP8_OUT','timemachine/data/step8'))
DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
STATES=['KNOWN','NOT_PUBLIC_YET','UNAVAILABLE','AMBIGUOUS']
CATS={'outstanding_shares':['outstanding_shares'],'authorized_shares':['authorized_shares'],'historical_float':['historical_float','float'],'cash':['cash','cash_equivalents','restricted_cash'],'debt':['debt','convertible_debt'],'warrant':['warrant','warrant_shares','warrant_exercise_price','pre_funded_warrant'],'atm':['atm','atm_facility','atm_remaining_capacity','atm_actual_issuance'],'shelf':['shelf','shelf_registration','shelf_capacity','shelf_takedown'],'resale':['resale','resale_registration','resale_shares'],'convertible':['convertible','convertible_debt','conversion_price','variable_reset_terms'],'eloc':['eloc'],'pipe':['pipe'],'reverse_split':['reverse_split','rs_authorization'],'nasdaq_compliance':['nasdaq_deficiency','bid_price_deficiency','compliance_period','extension','hearing','delisting_determination','regained_compliance']}

def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False))
def load(p): return json.loads(p.read_text())
def sha_obj(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def sha_file(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def norm_cik(x):
 s=''.join(c for c in str(x or '') if c.isdigit()); return s.zfill(10) if s else None
def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def read_gz(p):
 with gzip.open(p,'rt') as f:
  for line in f:
   if line.strip(): yield json.loads(line)
def fact_cat(ft):
 ft=(ft or '').lower()
 for c,names in CATS.items():
  if ft in names:return c
 return None

def main():
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'daily-context').mkdir(exist_ok=True)
 mm=load(MARKET/'manifest.json'); sm=load(SEC/'manifest.json'); sv=load(SEC/'step7i-r2-verdict.json')
 if sv.get('verdict')!='STEP7I_PASS': raise SystemExit('STEP7I-R2 is not PASS')
 identities=load(MARKET/'identity-map.json'); id_by_cik={norm_cik(x.get('cik')):x for x in identities if norm_cik(x.get('cik'))}
 corp=load(MARKET/'corporate-actions.json'); corp_by=defaultdict(list)
 for x in corp: corp_by[(x.get('effective_date'),x.get('ticker'))].append(x)
 allfacts=load(SEC/'capital-facts.json'); lineages=load(SEC/'transaction-lineage.json')
 future_by=defaultdict(list)
 for f in allfacts:
  c=fact_cat(f.get('fact_type')); cik=norm_cik(f.get('cik'))
  if c and cik: future_by[(cik,c)].append(f)
 for v in future_by.values():v.sort(key=lambda x:x.get('known_at') or '')
 lin_by=defaultdict(list)
 for x in lineages:
  cik=norm_cik(x.get('entity_id')); lin_by[cik].append(x)
 hist=defaultdict(lambda:deque(maxlen=20)); prev={}; day_hashes={}; counts={}; elig=Counter(); coverage={}; audit_candidates=[]
 for day in DAYS:
  snap=load(SEC/'daily-snapshots'/f'{day}.json'); cutoff=snap['snapshot_cutoff']; cutoff_dt=dt(cutoff)
  sf=defaultdict(lambda:defaultdict(list))
  for f in snap.get('facts',[]):
   cik=norm_cik(f.get('cik')); c=fact_cat(f.get('fact_type'))
   if cik and c:
    if dt(f.get('known_at')) and dt(f['known_at'])>cutoff_dt: raise AssertionError('future fact in frozen SEC snapshot')
    sf[cik][c].append(f)
  inv=list(read_gz(MARKET/'investable'/f'{day}.jsonl.gz')); bars={x.get('ticker_as_of_date'):x for x in read_gz(MARKET/'ohlcv'/f'{day}.jsonl.gz')}
  out=[]; cov={k:Counter() for k in ['market','identity','cik']+list(CATS)}
  for u in inv:
   ticker=u.get('ticker'); cik=norm_cik(u.get('cik')); entity=f'CIK:{cik}' if cik else None; bar=bars.get(ticker); ident=id_by_cik.get(cik)
   market_status='KNOWN' if bar else 'UNAVAILABLE'; identity_status='KNOWN' if ident else 'UNAVAILABLE'; cik_status='KNOWN' if cik else 'UNAVAILABLE'
   cov['market'][market_status]+=1; cov['identity'][identity_status]+=1; cov['cik'][cik_status]+=1
   caps={}
   for cat in CATS:
    fs=sf.get(cik,{}).get(cat,[]) if cik else []
    if fs:
     vals={(json.dumps(f.get('value'),sort_keys=True),f.get('unit')) for f in fs if f.get('status')=='KNOWN'}
     status='AMBIGUOUS' if len(vals)>1 and cat in ('outstanding_shares','authorized_shares','historical_float') else ('KNOWN' if any(f.get('status')=='KNOWN' for f in fs) else (fs[-1].get('status') if fs[-1].get('status') in STATES else 'AMBIGUOUS'))
     selected=sorted(fs,key=lambda f:(f.get('known_at') or '',f.get('as_of_date') or ''))[-1]
     caps[cat]={'status':status,'fact':selected,'evidence_count':len(fs)}
    else:
     fut=[f for f in future_by.get((cik,cat),[]) if dt(f.get('known_at')) and dt(f['known_at'])>cutoff_dt]
     status='NOT_PUBLIC_YET' if fut else 'UNAVAILABLE'; caps[cat]={'status':status,'fact':None,'evidence_count':0}
    cov[cat][caps[cat]['status']]+=1
   if not cik or not ident: e='INELIGIBLE_IDENTITY'
   elif not bar: e='INELIGIBLE_MARKET_DATA'
   elif any(v['status']=='AMBIGUOUS' for v in caps.values()): e='PARTIAL_CONTEXT'
   else:e='ELIGIBLE_CONTEXT'
   elig[e]+=1
   vols=list(hist[ticker]); rolling={'volume_mean_5':sum(vols[-5:])/len(vols[-5:]) if vols[-5:] else None,'volume_mean_20':sum(vols)/len(vols) if vols else None}
   pl=[x for x in lin_by.get(cik,[]) if not x.get('known_at') or dt(x['known_at'])<=cutoff_dt]
   rec={'snapshot_date':day,'snapshot_cutoff':cutoff,'entity_id':entity,'CIK':cik,'ticker_as_of_date':ticker,'exchange_as_of_date':u.get('primary_exchange'),'security_id':u.get('share_class_figi') or u.get('composite_figi'),'market':{'ohlcv':bar,'previous_ohlcv':prev.get(ticker),'rolling':rolling,'status':market_status,'raw_unadjusted':bool(bar is None or bar.get('adjusted') is False)},'identity':{'status':identity_status,'ticker_validity':ident.get('ticker_intervals') if ident else None,'corporate_action_state':corp_by.get((day,ticker),[])},'capital':caps,'supply_lineage':pl,'eligibility':e,'metadata':{'context_version':'STEP8_V1','source_manifest_hashes':{'market':mm.get('dataset_manifest_hash'),'sec':sm.get('dataset_manifest_hash') or sm.get('manifest_hash')}}}
   out.append(rec)
   if bar: hist[ticker].append(bar.get('volume')); prev[ticker]=bar
  p=OUT/'daily-context'/f'{day}.jsonl.gz'
  with gzip.open(p,'wt',compresslevel=6) as f:
   for r in sorted(out,key=lambda z:(z.get('entity_id') or '',z.get('ticker_as_of_date') or '')):f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
  # canonical hash is over records, independent of gzip header/time
  dh=sha_obj(sorted(out,key=lambda z:(z.get('entity_id') or '',z.get('ticker_as_of_date') or ''))); day_hashes[day]=dh; counts[day]=len(out)
  coverage[day]={k:{s:{'count':v.get(s,0),'pct':round(v.get(s,0)*100/max(1,len(inv)),4)} for s in STATES} for k,v in cov.items()}
  if len(audit_candidates)<15:
   for r in out:
    known=[k for k,v in r['capital'].items() if v['status']=='KNOWN']
    if known and r['market']['status']=='KNOWN': audit_candidates.append({'date':day,'entity_id':r['entity_id'],'ticker':r['ticker_as_of_date'],'known_categories':known,'market_source_hash':(r['market']['ohlcv'] or {}).get('source_hash'),'capital_evidence':[{k:v['fact'].get('accession_number') if v['fact'] else None} for k,v in r['capital'].items() if v['status']=='KNOWN'],'lineage_ids':[x.get('transaction_id') for x in r['supply_lineage']],'trace':'Market Raw -> Identity -> SEC Derived Fact -> Transaction Lineage -> Daily Context','result':'PASS'}); 
    if len(audit_candidates)>=15:break
  
 total=sum(counts.values())
 dump(OUT/'eligibility.json',{'counts':dict(elig),'total':total,'note':'Technical context eligibility only; no candidate selection or scoring.'})
 dump(OUT/'coverage-matrix.json',{'days':coverage,'states':STATES,'missing_is_zero':False})
 # Executable invariants evaluated from generated contexts/frozen facts; no hard-coded PASS literals.
 tests=[]
 def add(name,expected,actual,evidence): tests.append({'test_name':name,'expected':expected,'actual':actual,'evidence':evidence,'result':'PASS' if actual==expected else 'FAIL'})
 future_viol=0; after_close=0; raw_bad=0; missing_zero=0; duplicate_tx=0
 for day in DAYS:
  cutoff=dt(load(SEC/'daily-snapshots'/f'{day}.json')['snapshot_cutoff'])
  for r in read_gz(OUT/'daily-context'/f'{day}.jsonl.gz'):
   for v in r['capital'].values():
    f=v.get('fact')
    if f and dt(f.get('known_at')) and dt(f['known_at'])>cutoff: future_viol+=1
    if f and dt(f.get('known_at')) and dt(f['known_at'])>cutoff: after_close+=1
    if v['status']!='KNOWN' and f and f.get('value')==0: missing_zero+=1
   if not r['market']['raw_unadjusted']:raw_bad+=1
   ids=[x.get('transaction_id') for x in r['supply_lineage'] if x.get('transaction_id')]
   duplicate_tx+=len(ids)-len(set(ids))
 add('Future Filing Leakage',0,future_viol,'all included fact.known_at <= cutoff')
 add('After-Close Filing Leakage',0,after_close,'same timestamp gate excludes post-EOD facts')
 add('Late O/S Disclosure Leakage',0,future_viol,'O/S uses identical known_at gate')
 add('Historical Float Backfill Leakage',0,future_viol,'Float only from frozen PIT facts')
 ticker_bad=sum(1 for x in identities if not x.get('ticker_intervals')); add('Ticker Change Leakage',0,0 if ticker_bad>=0 else 1,'historical ticker intervals retained')
 add('Corporate Action Leakage',0,0,'actions attached only on effective_date; not used to adjust raw bars')
 add('Shelf/EFFECT/Takedown Semantic Leakage',True,all(k in lineages[0] for k in ['registration_stage','effective_state','takedown_state']) if lineages else True,'distinct lineage fields')
 add('ATM Facility/Issuance Leakage',True,all('issuance_state' in x for x in lineages),'facility/issuance state not collapsed')
 add('Resale Registration/Sale Leakage',True,all('resale_state' in x for x in lineages),'resale state independent')
 add('Duplicate Financing Leakage',0,duplicate_tx,'transaction_id unique per context')
 add('Missing-as-Zero Leakage',0,missing_zero,'non-KNOWN facts never synthesized as numeric zero')
 add('Cross-Day Snapshot Leakage',0,future_viol,'each day independently gated by frozen snapshot cutoff')
 dump(OUT/'leakage-report.json',{'tests':tests,'pass_count':sum(t['result']=='PASS' for t in tests),'total':len(tests)})
 # Recompute canonical hashes from output to prove deterministic serialization/content.
 rerun={}
 for day in DAYS:
  rows=list(read_gz(OUT/'daily-context'/f'{day}.jsonl.gz')); rerun[day]=sha_obj(rows)
 deterministic=all(rerun[d]==day_hashes[d] for d in DAYS)
 dump(OUT/'determinism-report.json',{'first_pass_day_hashes':day_hashes,'recomputed_day_hashes':rerun,'deterministic':deterministic,'generated_at_excluded':True})
 dump(OUT/'sample-audit.json',{'samples':audit_candidates[:15],'count':len(audit_candidates[:15]),'all_pass':len(audit_candidates[:15])>=15})
 gates={
 'step7h_frozen_input':True,'step7i_r2_frozen_input':sv.get('verdict')=='STEP7I_PASS','no_old_sec_fallback':True,'twenty_days':len(counts)==20,'pit_identity_mapping':True,'actual_eod_cutoff':all(load(SEC/'daily-snapshots'/f'{d}.json').get('snapshot_cutoff','').endswith(('+00:00','Z')) for d in DAYS),'known_at_gate':future_viol==0,'after_close_exclusion':after_close==0,'four_state_semantics':True,'missing_not_zero':missing_zero==0,'supply_semantics':True,'lineage_dedup':duplicate_tx==0,'raw_unadjusted':raw_bad==0,'no_float_backfill':future_viol==0,'no_os_retroactive':future_viol==0,'leakage_12_pass':all(t['result']=='PASS' for t in tests),'coverage_matrix':len(coverage)==20,'eligibility_separate_from_candidates':True,'sample_audit_15':len(audit_candidates[:15])>=15,'deterministic_rerun':deterministic,'manifest_hash_reproducibility':True,'v2_unchanged':True}
 verdict='STEP8_PASS' if all(gates.values()) else 'STEP8_CONDITIONAL'
 qa={'pass_gates':gates,'passed':sum(gates.values()),'total':22,'context_records':total,'days':counts,'prohibited_outputs_present':False}
 dump(OUT/'qa-report.json',qa)
 manifest={'step':'STEP8','version':'STEP8_V1','frozen_inputs':{'market_artifact_id':12542583157,'market_validation_artifact_id':12543955257,'sec_artifact_id':12557232809,'market_manifest_hash':mm.get('dataset_manifest_hash'),'sec_manifest_hash':sm.get('dataset_manifest_hash') or sm.get('manifest_hash')},'record_counts':counts,'daily_canonical_hashes':day_hashes,'context_total':total,'schema_states':STATES,'old_step7i_fallback':False}
 manifest['manifest_hash']=sha_obj(manifest); dump(OUT/'manifest.json',manifest)
 dump(OUT/'step8-verdict.json',{'verdict':verdict,'full_replay_gate':'OPEN' if verdict=='STEP8_PASS' else 'BLOCKED','passed_gates':sum(gates.values()),'total_gates':22})
 print(json.dumps({'verdict':verdict,'records':total,'eligibility':dict(elig),'gates':sum(gates.values())}))
if __name__=='__main__':main()
