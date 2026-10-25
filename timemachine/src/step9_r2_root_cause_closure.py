#!/usr/bin/env python3
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile,gzip,io,statistics
from pathlib import Path
FIRST='cd9f5d65556e2677460b7ddf7feda4f26211607b'; ORIG='timemachine/src/step9_deterministic_prediction_snapshots.py'
R_SHA='1f27acc08fc86020195886e12a594be7593310916743221b6819632a70cdd208'; CERT_SHA='2ec1f79a97ba4037da91e31a8b71bf1ae53bad14de4c803432dc1c9673dc500b'; CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def J(p):return json.load(open(p,encoding='utf-8'))
def D(o,n,x):
 p=Path(o)/n;p.parent.mkdir(parents=True,exist_ok=True);json.dump(x,open(p,'w',encoding='utf-8'),indent=2,sort_keys=True,ensure_ascii=False)
def run(script,cert,ctx,out):
 shutil.rmtree(out,ignore_errors=True);os.makedirs(out,exist_ok=True)
 c=subprocess.run([sys.executable,script,'--cert',cert,'--context',ctx,'--out',out,'--commit',FIRST],capture_output=True,text=True)
 return {'returncode':c.returncode,'stdout':c.stdout,'stderr':c.stderr}
def main():
 a=argparse.ArgumentParser();a.add_argument('--cert',required=True);a.add_argument('--context',required=True);a.add_argument('--rdiag',required=True);a.add_argument('--out',required=True);a.add_argument('--repo',default='.');x=a.parse_args();os.makedirs(x.out,exist_ok=True)
 digs={'step9_r':sha(x.rdiag),'cert':sha(x.cert),'context':sha(x.context)}; ok=digs=={'step9_r':R_SHA,'cert':CERT_SHA,'context':CTX_SHA};D(x.out,'frozen-input-verification.json',{'actual':digs,'expected':{'step9_r':R_SHA,'cert':CERT_SHA,'context':CTX_SHA},'PASS':ok})
 if not ok:D(x.out,'step9-r2-verdict.json',{'verdict':'STEP9_R2_BUILD_INCOMPLETE','reason':'DIGEST_MISMATCH'});return
 rz=zipfile.ZipFile(x.rdiag); inv=sorted(rz.namelist()); expected=['first-run-reproduction.json','first-run-gate-matrix.json','first-run-qa.json','first-run-verdict.json','step9-root-cause.json','repair-classification.json','repair-diff.json','step9-r-verdict.json'];D(x.out,'step9-r-artifact-verification.json',{'sha256':digs['step9_r'],'digest_match':True,'entry_count':len(inv)});D(x.out,'step9-r-artifact-inventory.json',{'entries':inv,'expected':{n:('PRESENT' if n in inv else 'MISSING') for n in expected}})
 def rj(n):return json.loads(rz.read(n)) if n in inv else None
 rver=rj('step9-r-verdict.json'); rroot=rj('step9-root-cause.json'); rmatrix=rj('first-run-gate-matrix.json'); D(x.out,'step9-r-verdict-path-audit.json',{'reproduction':rj('first-run-reproduction.json'),'gate_matrix':rmatrix,'root_cause':rroot,'repair_classification':rj('repair-classification.json'),'final':rver,'finding':'STEP9-R emits MODEL_LOGIC_CHANGE_REQUIRED whenever its narrow repairable predicate is false; that fallback does not itself prove model logic must change.'})
 orig='/tmp/step9-r2-original.py';src=subprocess.check_output(['git','show',FIRST+':'+ORIG],cwd=x.repo,text=True);Path(orig).write_text(src,encoding='utf-8')
 source_audit={'commit':FIRST,'path':ORIG,'sha256':hashlib.sha256(src.encode()).hexdigest(),'expects_ELIGIBLE_CONTEXT':"p['eligibility']!='ELIGIBLE_CONTEXT'" in src,'mutation_fixture_expects_ELIGIBLE_CONTEXT':"q.get('eligibility')=='ELIGIBLE_CONTEXT'" in src};D(x.out,'original-step9-source-audit.json',source_audit)
 cz=zipfile.ZipFile(x.context);names=sorted(n for n in cz.namelist() if n.startswith('repaired-daily-context/') and n.endswith('.jsonl.gz'));counts={};samples={};total=0
 for n in names:
  for line in gzip.GzipFile(fileobj=io.BytesIO(cz.read(n))):
   q=json.loads(line);v=q.get('eligibility');counts[str(v)]=counts.get(str(v),0)+1;total+=1;samples.setdefault(str(v),{'keys':sorted(q.keys()),'eligibility':v,'market_status':(q.get('market') or {}).get('status')})
 actual='ELIGIBLE' if counts.get('ELIGIBLE',0)>0 else None
 schema={'trading_days':len(names),'records':total,'eligibility_counts':counts,'samples':samples,'actual_eligible_label':actual};D(x.out,'context-schema-audit.json',schema)
 mapping={'eligibility':{'expected_field':'eligibility','expected_value':'ELIGIBLE_CONTEXT','actual_field':'eligibility','actual_value':actual,'affected_records':counts.get(actual,0) if actual else 0,'match':actual=='ELIGIBLE_CONTEXT'}}
 # Inspect actual keys on an eligible record rather than inventing mappings.
 firstelig=None
 for line in gzip.GzipFile(fileobj=io.BytesIO(cz.read(names[0]))):
  q=json.loads(line)
  if q.get('eligibility')==actual:firstelig=q;break
 if firstelig:
  cap=firstelig.get('capital') or {};m=firstelig.get('market') or {};o=m.get('ohlcv') or {};r=m.get('rolling') or {}
  for k,path,val in [('entity_id','entity_id',firstelig.get('entity_id')),('CIK','CIK',firstelig.get('CIK')),('ticker_as_of','ticker_as_of_date',firstelig.get('ticker_as_of_date')),('trading_date','market.ohlcv.trading_date',o.get('trading_date')),('cutoff','snapshot_cutoff',firstelig.get('snapshot_cutoff')),('price','market.ohlcv.close',o.get('close')),('volume','market.ohlcv.volume',o.get('volume')),('rolling_volume','market.rolling.volume_mean_20',r.get('volume_mean_20'))]:mapping[k]={'actual_path':path,'present':val is not None,'sample_type':type(val).__name__}
  for k in ['outstanding_shares','authorized_shares','atm','shelf','resale','warrant','convertible','eloc','pipe','reverse_split','nasdaq_compliance']:mapping[k]={'actual_path':'capital.'+k,'present':k in cap,'status':(cap.get(k) or {}).get('status')}
 D(x.out,'input-field-mapping-audit.json',mapping)
 # Exact first-run reproduction from frozen source and inputs.
 fr='/tmp/step9-r2-first';rr=run(orig,x.cert,x.context,fr);fv=J(Path(fr)/'step9-verdict.json');fqa=J(Path(fr)/'qa-report.json');fa=J(Path(fr)/'candidate-distribution-audit.json');D(x.out,'first-run-reproduction.json',{'returncode':rr['returncode'],'verdict':fv,'reproduction_match':fv.get('verdict')=='STEP9_DEFECT_FOUND','context_records':fa.get('daily') and sum(d['records'] for d in fa['daily']),'rule_engine_eligible':fa.get('total_eligible'),'selected':fa.get('total_selected'),'daily_eligible':[d['eligible'] for d in fa.get('daily',[])],'daily_selected':[d['selected'] for d in fa.get('daily',[])],'snapshot_count':J(Path(fr)/'snapshot-integrity-report.json').get('snapshot_count')})
 gates=['step8_certification','context_digest','future_field_canary','future_price_canary','determinism','snapshot_integrity','candidate_distribution','trading_days_20','context_records_168759','outcome_access_zero','outcome_calculations_zero','protected_outputs'];matrix=[{'gate':n,'actual':v,'state':'PASS' if v is True else 'FAIL' if v is False else 'BLOCK'} for n,v in zip(gates,fqa.get('gates',[]))];D(x.out,'first-run-gate-matrix.json',matrix);fail=[g for g in matrix if g['state']!='PASS'];D(x.out,'failing-gates.json',fail)
 proven=source_audit['expects_ELIGIBLE_CONTEXT'] and actual=='ELIGIBLE' and fa.get('total_eligible')==0 and counts.get('ELIGIBLE',0)>0
 root={'proven':proven,'defect_class':'INPUT_SCHEMA_MAPPING_DEFECT' if proven else 'UNRESOLVED','expected':'ELIGIBLE_CONTEXT','actual':actual,'affected_records':counts.get('ELIGIBLE',0),'downstream_rule_engine_eligible':fa.get('total_eligible'),'cause':'Frozen STEP8 Context labels eligible records ELIGIBLE, while frozen STEP9 implementation only admits ELIGIBLE_CONTEXT.' if proven else 'Not proven'};D(x.out,'root-cause.json',root)
 D(x.out,'model-logic-change-verification.json',{'step9_r_model_logic_change_required_supported':False if proven else None,'reason':'A proven schema mapping defect is implementation-level, not threshold/weight/signal tuning.' if proven else 'Evidence incomplete','A_rule_logic_caused_zero':False if proven else None,'B_schema_removed_universe':True if proven else None,'C_diagnostic_misclassified':True if proven else None,'D_fallback_without_proof':True if proven else None})
 if not proven:D(x.out,'step9-r2-verdict.json',{'verdict':'STEP9_R2_EVIDENCE_INCOMPLETE'});return
 # Minimal implementation-only repair: comparisons/fixture only. Config text and model logic stay byte-identical.
 patched=src.replace("p['eligibility']!='ELIGIBLE_CONTEXT'","p['eligibility']!='ELIGIBLE'").replace("q.get('eligibility')=='ELIGIBLE_CONTEXT'","q.get('eligibility')=='ELIGIBLE'")
 pp='/tmp/step9-r2-patched.py';Path(pp).write_text(patched,encoding='utf-8');D(x.out,'repair-classification.json',{'classification':'IMPLEMENTATION_DEFECT','repair':'exact eligibility status mapping','model_logic_change':False});D(x.out,'repair-diff.json',{'eligibility_comparisons_changed':True,'mutation_fixture_mapping_changed':True,'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'universe_definition_changed':False,'STEP8_changed':False})
 post='/tmp/step9-r2-post';pr=run(pp,x.cert,x.context,post)
 if not Path(post,'step9-verdict.json').exists():D(x.out,'step9-r2-verdict.json',{'verdict':'STEP9_R2_BUILD_INCOMPLETE','stderr':pr['stderr']});return
 # Copy post evidence, retaining R2-specific files.
 for p in Path(post).iterdir():
  dst=Path(x.out)/p.name
  if p.is_dir():shutil.copytree(p,dst,dirs_exist_ok=True)
  elif p.name not in {'step9-verdict.json','qa-report.json','manifest.json'}:shutil.copy2(p,dst)
 pv=J(Path(post)/'step9-verdict.json');pqa=J(Path(post)/'qa-report.json');pa=J(Path(post)/'candidate-distribution-audit.json');pi=J(Path(post)/'snapshot-integrity-report.json');pd=J(Path(post)/'determinism-tests.json');pf=J(Path(post)/'rule-engine-v1-freeze.json');ff=J(Path(fr)/'rule-engine-v1-freeze.json');iso=J(Path(post)/'outcome-isolation-audit.json');can=J(Path(post)/'leakage-canary-tests.json');prot=J(Path(post)/'protected-output-integrity.json')
 cmp={'config_hash_before':ff['config_sha256'],'config_hash_after':pf['config_sha256'],'match':ff['config_sha256']==pf['config_sha256'],'thresholds_changed':False,'weights_changed':False,'signals_changed':False,'selection_cutoff_changed':False,'missing_handling_changed':False,'baseline_definitions_changed':False,'random_seed_changed':False};D(x.out,'rule-engine-v1-freeze-comparison.json',cmp)
 pm=[{'gate':n,'actual':v,'state':'PASS' if v is True else 'FAIL' if v is False else 'BLOCK'} for n,v in zip(gates,pqa.get('gates',[]))];D(x.out,'post-repair-gate-matrix.json',pm);D(x.out,'outcome-isolation-audit.json',iso);D(x.out,'leakage-canary-tests.json',can);D(x.out,'determinism-tests.json',pd);D(x.out,'canonicalization-audit.json',{'same_input_same_output':pd.get('same_input_same_output'),'canonical_spec':J(Path(post)/'snapshot-canonicalization-spec.json'),'PASS':pd.get('same_input_same_output') is True});D(x.out,'prediction-id-audit.json',{'sample_n':pi.get('prediction_id_sample_n'),'PASS':pi.get('prediction_id_sample_PASS')});D(x.out,'candidate-distribution-audit.json',pa);D(x.out,'snapshot-integrity-report.json',pi);D(x.out,'protected-output-integrity.json',prot)
 passr=(pv.get('verdict')=='STEP9_PASS' and cmp['match'] and can.get('PASS') is True and pd.get('PASS') is True and pi.get('snapshot_count')==20 and pi.get('duplicate_predictions')==0 and pi.get('entity_ticker_collisions_unresolved')==0 and iso.get('outcome_access_count')==0 and iso.get('outcome_calculations_performed')==0 and prot.get('PASS') is True and all(g['state']=='PASS' for g in pm))
 rv='STEP9_R2_PASS' if passr else 'STEP9_R2_DEFECT_REMAINS';final='STEP9_PASS' if passr else 'STEP9_BLOCKED';gate='OPEN' if passr else 'BLOCKED';D(x.out,'qa-report.json',{'first_reproduction_match':fv.get('verdict')=='STEP9_DEFECT_FOUND','root_cause_proven':proven,'post_verdict':pv.get('verdict'),'config_match':cmp['match'],'trading_days':len(pa.get('daily',[])),'context_records':sum(d['records'] for d in pa.get('daily',[])),'eligible':pa.get('total_eligible'),'selected':pa.get('total_selected'),'snapshot_count':pi.get('snapshot_count'),'outcome_access_count':iso.get('outcome_access_count'),'verdict':rv,'Final_STEP9':final,'STEP10_GATE':gate});D(x.out,'step9-r2-verdict.json',{'verdict':rv,'Final_STEP9':final,'STEP10_GATE':gate,'outcome_evaluated':False});D(x.out,'step9-final-certification.json',{'verdict':final,'STEP10_GATE':gate,'basis':'original STEP9 criteria re-evaluated after implementation-only schema mapping repair','PASS':passr});D(x.out,'manifest.json',{'stage':'STEP9-R2','artifact':'timemachine-step9-r2-root-cause-closure','files':sorted(p.name for p in Path(x.out).iterdir())})
if __name__=='__main__':main()
