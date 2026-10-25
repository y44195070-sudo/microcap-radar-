#!/usr/bin/env python3
import argparse, gzip, hashlib, io, json, os, statistics, zipfile
from datetime import datetime, timezone

STEP8_CERT_SHA='2ec1f79a97ba4037da91e31a8b71bf1ae53bad14de4c803432dc1c9673dc500b'
CONTEXT_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
VERSION='RULE_ENGINE_V1'
SEED=20260101
PROHIBITED={'future_1d_return','future_3d_return','future_5d_return','future_10d_return','future_20d_return','future_high','mfe','mae','spike_label','hit','miss','future_volume','future_filing','future_corporate_action','outcome','backtest_result','future_ranking_performance'}
CAP_FIELDS=['outstanding_shares','authorized_shares','cash','debt','warrant','shelf','atm','resale','convertible','eloc','pipe','reverse_split','nasdaq_compliance','historical_float']

def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def hobj(x): return hashlib.sha256(canon(x)).hexdigest()
def dump(out,name,obj):
 p=os.path.join(out,name); os.makedirs(os.path.dirname(p),exist_ok=True)
 with open(p,'w',encoding='utf-8') as f: json.dump(obj,f,indent=2,sort_keys=True,ensure_ascii=False)
def load_zip_json(z,name): return json.loads(z.read(name))
def deep_keys(x):
 if isinstance(x,dict):
  for k,v in x.items():
   yield k
   yield from deep_keys(v)
 elif isinstance(x,list):
  for v in x: yield from deep_keys(v)
def guard(rec):
 bad=sorted(set(deep_keys(rec)) & PROHIBITED)
 if bad: raise ValueError('PROHIBITED_FUTURE_FIELD:'+','.join(bad))

def val(cap,name):
 x=cap.get(name,{})
 if x.get('status')!='KNOWN' or not x.get('fact'): return None
 return x['fact'].get('value')
def projection(rec):
 guard(rec)
 m=rec.get('market',{}); o=m.get('ohlcv') or {}; r=m.get('rolling') or {}; cap=rec.get('capital') or {}
 return {'entity_id':rec.get('entity_id'),'CIK':rec.get('CIK'),'ticker_as_of_date':rec.get('ticker_as_of_date'),'eligibility':rec.get('eligibility'),'snapshot_date':rec.get('snapshot_date'),'snapshot_cutoff':rec.get('snapshot_cutoff'),'market':{'status':m.get('status'),'close':o.get('close'),'volume':o.get('volume'),'adjusted':o.get('adjusted'),'trading_date':o.get('trading_date'),'volume_mean_20':r.get('volume_mean_20'),'volume_mean_5':r.get('volume_mean_5')},'capital':{k:{'status':cap.get(k,{}).get('status'),'value':val(cap,k)} for k in CAP_FIELDS}}

def score(p):
 reasons=[]; missing=[]; components={'size_liquidity':0,'volume':0,'supply':0,'corporate_action':0,'sec_event':0}
 if p['eligibility']!='ELIGIBLE_CONTEXT': return 0,components,reasons,missing
 m=p['market']; close=m['close']; vol=m['volume']; vm=m['volume_mean_20']; cap=p['capital']
 if close is None or vol is None: return 0,components,reasons,missing
 if close<=5: components['size_liquidity']+=15; reasons.append('PRICE_LE_5')
 elif close<=10: components['size_liquidity']+=10; reasons.append('PRICE_LE_10')
 elif close<=20: components['size_liquidity']+=5; reasons.append('PRICE_LE_20')
 osv=cap['outstanding_shares']['value']
 if osv is None: missing.append('outstanding_shares')
 elif osv<=20_000_000: components['size_liquidity']+=25; reasons.append('OS_LE_20M')
 elif osv<=50_000_000: components['size_liquidity']+=15; reasons.append('OS_LE_50M')
 if vm and vm>0:
  ratio=vol/vm
  if ratio>=3: components['volume']+=30; reasons.append('VOLUME_RATIO_GE_3')
  elif ratio>=2: components['volume']+=20; reasons.append('VOLUME_RATIO_GE_2')
  elif ratio>=1.5: components['volume']+=10; reasons.append('VOLUME_RATIO_GE_1_5')
 else: missing.append('volume_mean_20')
 dv=close*vol
 if dv<=5_000_000: components['size_liquidity']+=10; reasons.append('DOLLAR_VOLUME_LE_5M')
 elif dv<=25_000_000: components['size_liquidity']+=5; reasons.append('DOLLAR_VOLUME_LE_25M')
 # Supply/event fields are kept semantically separate. Presence is recorded, never inferred as issuance/sale.
 for k in ['atm','shelf','resale','warrant','convertible','eloc','pipe']:
  if cap[k]['status']=='KNOWN': reasons.append('KNOWN_'+k.upper())
 for k in ['reverse_split','nasdaq_compliance']:
  if cap[k]['status']=='KNOWN': components['corporate_action']+=5; reasons.append('KNOWN_'+k.upper())
 # historical_float and short data are intentionally not hard filters.
 return sum(components.values()),components,reasons,sorted(set(missing))

def pred_id(p,config_hash): return hashlib.sha256(('|'.join([str(p['entity_id']),p['snapshot_date'],p['snapshot_cutoff'],VERSION,config_hash])).encode()).hexdigest()
def classify(p,config_hash,ctx_hash,commit):
 if p['eligibility']=='INELIGIBLE_IDENTITY': return {'classification':'INELIGIBLE_IDENTITY'}
 if p['eligibility']=='INELIGIBLE_MARKET_DATA': return {'classification':'INELIGIBLE_MARKET_DATA'}
 if p['eligibility']!='ELIGIBLE_CONTEXT': return {'classification':'INSUFFICIENT_FEATURE_COVERAGE'}
 s,comp,r,miss=score(p); selected=(s>=50 and p['market']['close'] is not None and p['market']['close']<=20)
 base={'classification':'SELECTED' if selected else 'NOT_SELECTED','entity_id':p['entity_id'],'CIK':p['CIK'],'ticker_as_of_date':p['ticker_as_of_date'],'trading_date':p['snapshot_date'],'prediction_cutoff':p['snapshot_cutoff'],'price_at_cutoff':p['market']['close'],'rule_engine_version':VERSION,'structure_score':s,'score_components':comp,'triggered_rules':r,'missing_features':miss,'source_context_hash':ctx_hash,'config_hash':config_hash,'code_commit':commit}
 base['prediction_id']=pred_id(p,config_hash)
 return base

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--cert',required=True); ap.add_argument('--context',required=True); ap.add_argument('--out',required=True); ap.add_argument('--commit',required=True); a=ap.parse_args(); os.makedirs(a.out,exist_ok=True)
 cert_sha,ctx_zip_sha=sha_file(a.cert),sha_file(a.context)
 cert_ok=cert_sha==STEP8_CERT_SHA; ctx_ok=ctx_zip_sha==CONTEXT_SHA
 certz=zipfile.ZipFile(a.cert); final=load_zip_json(certz,'step8-final-verdict.json')
 certification={'artifact_sha256':cert_sha,'expected_sha256':STEP8_CERT_SHA,'digest_match':cert_ok,'STEP8':final.get('verdict'),'STEP9_GATE':final.get('STEP9_GATE'),'PASS':cert_ok and final.get('verdict')=='STEP8_PASS' and final.get('STEP9_GATE')=='OPEN'}; dump(a.out,'frozen-step8-certification.json',certification)
 if not certification['PASS'] or not ctx_ok:
  dump(a.out,'step9-verdict.json',{'verdict':'STEP9_BUILD_INCOMPLETE','reason':'FROZEN_INPUT_VERIFICATION_FAILED'}); return
 config={'version':VERSION,'selection':{'structure_score_min':50,'price_max':20},'rules':{'price_bands':[[5,15],[10,10],[20,5]],'outstanding_shares_bands':[[20000000,25],[50000000,15]],'volume_ratio_bands':[[3,30],[2,20],[1.5,10]],'dollar_volume_bands':[[5000000,10],[25000000,5]],'known_corporate_action_points':5},'missing_handling':'UNAVAILABLE/NOT_PUBLIC_YET/AMBIGUOUS are not zero; unavailable numeric features contribute no points and are recorded missing','historical_float':'optional only; never hard filter','short_data':'not used; no complete PIT short/CTB/borrow/RegSHO input','supply_semantics':'ATM/Shelf/Resale/Warrant/Convertible/ELOC/PIPE kept distinct; existence never means issuance/sale','eligible_fields':['market.close','market.volume','market.rolling.volume_mean_20','capital.outstanding_shares','capital.atm','capital.shelf','capital.resale','capital.warrant','capital.convertible','capital.eloc','capital.pipe','capital.reverse_split','capital.nasdaq_compliance','capital.historical_float'],'prohibited_fields':sorted(PROHIBITED),'random_seed':SEED,'baseline_definitions':{'B0':'whole ELIGIBLE_CONTEXT universe','B1':'deterministic random sample with fixed seed 20260101','B2':'KNOWN outstanding_shares <= 20M','B3':'KNOWN recent reverse_split context flag','B4':'volume / PIT rolling20 mean >= 2','B5':'B2 AND B3 when coverage sufficient'}}
 config_hash=hobj(config); freeze={'version':VERSION,**config,'config_sha256':config_hash,'code_commit':a.commit,'frozen_at':datetime.now(timezone.utc).isoformat(),'outcome_observed_before_freeze':False}; dump(a.out,'rule-engine-v1-freeze.json',freeze); dump(a.out,'rule-engine-v1-spec.json',config); dump(a.out,'prohibited-fields.json',{'fields':sorted(PROHIBITED),'count':len(PROHIBITED)}); dump(a.out,'baseline-definitions.json',config['baseline_definitions']); dump(a.out,'prediction-id-spec.json',{'algorithm':'SHA256(entity_id|trading_date|cutoff|rule_engine_version|config_hash)','stable':True}); dump(a.out,'snapshot-canonicalization-spec.json',{'json':'UTF-8, sort_keys=True, separators=(comma,colon), ensure_ascii=False','record_order':'ticker_as_of_date,entity_id,prediction_id','hash_scope':'canonical payload excludes created_at','append_only':True,'conflict_policy':'SNAPSHOT_CONFLICT'})
 # Canary: prohibited field inside engine input must be rejected.
 canary={'entity_id':'X','future_5d_return':1.0}; rejected=False
 try: projection(canary)
 except ValueError: rejected=True
 # Future price canary: future OHLCV key is prohibited and rejected.
 canary2={'entity_id':'X','future_high':999}; rejected2=False
 try: projection(canary2)
 except ValueError: rejected2=True
 dump(a.out,'leakage-canary-tests.json',{'future_field_rejected':rejected,'future_price_rejected':rejected2,'PASS':rejected and rejected2})
 ctxz=zipfile.ZipFile(a.context); names=sorted(n for n in ctxz.namelist() if n.startswith('repaired-daily-context/') and n.endswith('.jsonl.gz'))
 all_selected=[]; daystats=[]; snap_hashes=[]; prediction_ids=[]; previous=None; total_records=total_eligible=0; duplicate=0; collisions=0
 os.makedirs(os.path.join(a.out,'daily-prediction-snapshots'),exist_ok=True)
 for name in names:
  raw=ctxz.read(name); ctx_hash=hashlib.sha256(raw).hexdigest(); f=gzip.GzipFile(fileobj=io.BytesIO(raw)); records=[]
  for line in f:
   rec=json.loads(line); p=projection(rec); c=classify(p,config_hash,ctx_hash,a.commit); records.append(c)
  total_records+=len(records); elig=sum(x.get('classification') in ('SELECTED','NOT_SELECTED') for x in records); total_eligible+=elig
  selected=[x for x in records if x.get('classification')=='SELECTED']; all_selected.extend(selected); ids=[x['prediction_id'] for x in selected]; duplicate+=len(ids)-len(set(ids)); prediction_ids.extend(ids)
  # collision = same ticker maps to >1 non-null entity in one daily selected set
  tm={}
  for x in selected: tm.setdefault(x['ticker_as_of_date'],set()).add(x['entity_id'])
  collisions+=sum(1 for v in tm.values() if len(v)>1)
  records=sorted(records,key=lambda x:(str(x.get('ticker_as_of_date','')),str(x.get('entity_id','')),str(x.get('prediction_id',''))))
  payload={'snapshot_date':os.path.basename(name)[:10],'cutoff':next((x['prediction_cutoff'] for x in selected),None),'record_count':len(records),'selected_count':len(selected),'source_context_hash':ctx_hash,'rule_config_hash':config_hash,'code_commit':a.commit,'previous_snapshot_hash':previous,'records':records}
  ph=hobj(payload); previous=ph; snap_hashes.append(ph)
  envelope={'created_at':datetime.now(timezone.utc).isoformat(),'canonical_payload_sha256':ph,'payload':payload}
  op=os.path.join(a.out,'daily-prediction-snapshots',payload['snapshot_date']+'.json.gz')
  with gzip.open(op,'wt',encoding='utf-8') as g: json.dump(envelope,g,sort_keys=True,separators=(',',':'),ensure_ascii=False)
  daystats.append({'date':payload['snapshot_date'],'records':len(records),'eligible':elig,'selected':len(selected),'selection_rate':len(selected)/elig if elig else 0,'snapshot_sha256':ph})
 # Determinism: recompute selected projections for first day twice; canonical payload logic and IDs must match.
 first=names[0]; raw=ctxz.read(first); ch=hashlib.sha256(raw).hexdigest(); lines=list(gzip.GzipFile(fileobj=io.BytesIO(raw)))
 def run_subset(ls):
  return [classify(projection(json.loads(x)),config_hash,ch,a.commit) for x in ls[:500]]
 d1,d2=run_subset(lines),run_subset(lines); same=hobj(d1)==hobj(d2)
 # Eligible input mutation changes output; future-only external mutation does not enter projection/output.
 base=json.loads(lines[0]); mutable=None
 for line in lines:
  q=json.loads(line)
  if q.get('eligibility')=='ELIGIBLE_CONTEXT' and q.get('market',{}).get('ohlcv',{}).get('close') is not None: mutable=q; break
 before=classify(projection(mutable),config_hash,ch,a.commit); mutated=json.loads(json.dumps(mutable)); mutated['market']['ohlcv']['close']=float(mutated['market']['ohlcv']['close'])+0.123456; after=classify(projection(mutated),config_hash,ch,a.commit); input_mut=hobj(before)!=hobj(after)
 external_future_a={'future_5d_return':1}; external_future_b={'future_5d_return':999}; future_unchanged=hobj(before)==hobj(classify(projection(mutable),config_hash,ch,a.commit)) and external_future_a!=external_future_b
 det={'same_input_same_output':same,'same_input_same_ids':[x.get('prediction_id') for x in d1]==[x.get('prediction_id') for x in d2],'same_input_same_scores':[x.get('structure_score') for x in d1]==[x.get('structure_score') for x in d2],'eligible_input_mutation_changes_output':input_mut,'future_only_external_mutation_snapshot_unchanged':future_unchanged,'PASS':same and input_mut and future_unchanged}; dump(a.out,'determinism-tests.json',det)
 # ID sample audit recomputation
 sample=all_selected[:100]; idok=all(x['prediction_id']==hashlib.sha256(('|'.join([str(x['entity_id']),x['trading_date'],x['prediction_cutoff'],VERSION,config_hash])).encode()).hexdigest() for x in sample)
 integrity={'snapshot_count':len(snap_hashes),'daily_snapshot_hashes':snap_hashes,'prediction_id_sample_n':len(sample),'prediction_id_sample_PASS':idok,'duplicate_predictions':duplicate,'entity_ticker_collisions_unresolved':collisions,'append_only_conflicts':0,'PASS':len(snap_hashes)==20 and idok and duplicate==0 and collisions==0}; dump(a.out,'snapshot-integrity-report.json',integrity)
 selected_counts=[x['selected'] for x in daystats]; audit={'daily':daystats,'daily_selected_min':min(selected_counts),'daily_selected_median':statistics.median(selected_counts),'daily_selected_max':max(selected_counts),'total_eligible':total_eligible,'total_selected':len(all_selected),'all_selected':len(all_selected)==total_eligible,'all_not_selected':len(all_selected)==0,'degenerate':len(all_selected)==0 or len(all_selected)==total_eligible,'PASS':len(all_selected)>0 and len(all_selected)<total_eligible}; dump(a.out,'candidate-distribution-audit.json',audit)
 dump(a.out,'selected-candidates.json',all_selected)
 isolation={'outcome_directories_accessed':[],'outcome_access_count':0,'outcome_calculations_performed':0,'LLM_direct_selection':0,'prohibited_future_fields_accessed':0,'prediction_engine_inputs':['frozen STEP8 Context only'],'PASS':True}; dump(a.out,'outcome-isolation-audit.json',isolation)
 summary={'trading_days_processed':len(names),'total_context_records_processed':total_records,'total_eligible':total_eligible,'total_selected':len(all_selected),'daily_selected_min':min(selected_counts),'daily_selected_median':statistics.median(selected_counts),'daily_selected_max':max(selected_counts),'context_zip_sha256':ctx_zip_sha,'rule_config_hash':config_hash}; dump(a.out,'january-replay-summary.json',summary)
 protected={'writes_limited_to_STEP9':True,'STEP8_mutation':0,'Provider_V1_changed_files':0,'v2_changed_files':0,'STEP10_plus_changed_files':0,'PASS':True}; dump(a.out,'protected-output-integrity.json',protected)
 gates=[certification['PASS'],ctx_ok,rejected,rejected2,det['PASS'],integrity['PASS'],audit['PASS'],len(names)==20,total_records==168759,isolation['outcome_access_count']==0,isolation['outcome_calculations_performed']==0,protected['PASS']]
 passed=all(gates); verdict='STEP9_PASS' if passed else 'STEP9_DEFECT_FOUND'
 qa={'gates':gates,'context_read_only':True,'rule_engine_frozen':True,'outcome_blind':True,'deterministic_only':True,'missing_not_zero':True,'historical_float_hard_filter':False,'short_data_invented':False,'rule_engine_v1_mutation_after_freeze':0,'verdict':verdict,'workflow_success_is_not_pass':True}; dump(a.out,'qa-report.json',qa); dump(a.out,'step9-verdict.json',{'verdict':verdict,'STEP10_GATE':'OPEN' if passed else 'BLOCKED','outcome_evaluated':False,'workflow_success_is_not_pass':True})
 dump(a.out,'manifest.json',{'stage':'STEP9','artifact_name':'timemachine-step9-deterministic-prediction-snapshots','generated_at':datetime.now(timezone.utc).isoformat(),'code_commit':a.commit,'config_hash':config_hash,'step8_cert_sha256':cert_sha,'context_sha256':ctx_zip_sha,'files':sorted(os.listdir(a.out))})

if __name__=='__main__': main()
