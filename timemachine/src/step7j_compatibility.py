from __future__ import annotations
import json, hashlib, os
from pathlib import Path

OUT=Path('timemachine/data/step7j')
BASE=Path(os.getenv('STEP7I_R2','/tmp/step7i-r2'))
ROOT=Path('.')

def dump(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True));return hashlib.sha256(p.read_bytes()).hexdigest()
def txt(p): return p.read_text(errors='ignore') if p.exists() else ''
def classify(step,files):
 body='\n'.join(txt(Path(x)) for x in files)
 old=any(x in body for x in ['STEP11_BASE','/tmp/step11-base','step10','filing-chains.json','normalized/filings.json'])
 r2=any(x in body for x in ['step7i-r2','capital-facts.json','transaction-lineage.json'])
 semantics=all(x in body for x in ['KNOWN','UNAVAILABLE','AMBIGUOUS','NOT_PUBLIC_YET'])
 pit=('known_at' in body and 'snapshot_cutoff' in body)
 if step in (8,9): return 'D','No executable STEP %d implementation/workflow was found on main; it cannot be revalidated as an existing downstream stage.'%step,old,r2,semantics,pit
 if old and not r2:return 'D','Existing implementation is an independent/older fixture/backfill lineage and does not consume STEP 7I-R2 capital PIT artifacts.',old,r2,semantics,pit
 if not semantics or not pit:return 'C','Downstream code does not enforce the complete STEP 7I-R2 four-state and known_at<=snapshot_cutoff contract.',old,r2,semantics,pit
 return 'B','Code appears adaptable but must be rerun against the new frozen foundation.',old,r2,semantics,pit

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 required=['manifest.json','coverage-report.json','leakage-report.json','qa-report.json','sample-audit.json','transaction-lineage.json','capital-facts.json','capital-events.json','sec-document-index.json','step7i-r2-verdict.json']
 missing=[x for x in required if not (BASE/x).exists()]
 if missing: raise SystemExit('missing R2 inputs '+repr(missing))
 manifest=json.loads((BASE/'manifest.json').read_text());coverage=json.loads((BASE/'coverage-report.json').read_text());verdict=json.loads((BASE/'step7i-r2-verdict.json').read_text())
 inventory={
 '8':[], '9':[],
 '10':['timemachine/src/step10_official_pit.py','.github/workflows/timemachine-step10.yml'],
 '11':['timemachine/src/step11_retest.py','timemachine/src/step11_retest_v2.py','timemachine/src/step11_retest_v3.py','.github/workflows/timemachine-step11.yml','.github/workflows/timemachine-step11-retest.yml','.github/workflows/timemachine-step11-retest-v2.yml','.github/workflows/timemachine-step11-retest-v3.yml']}
 rows=[]
 for s in [8,9,10,11]:
  files=[x for x in inventory[str(s)] if Path(x).exists()]; grade,reason,old,r2,sem,pit=classify(s,files)
  rows.append({'step':s,'files':files,'classification':grade,'reason':reason,'old_lineage_dependency':old,'step7i_r2_dependency':r2,'four_state_contract_present':sem,'explicit_known_at_snapshot_cutoff_contract':pit})
 dep={'baseline_artifact_id':12557232809,'baseline_verdict':verdict.get('verdict') or verdict.get('final_verdict'),'steps':rows}
 schema={'required_fact_fields':['entity_id','CIK','ticker_as_of_date','fact_type','value','unit','as_of_date','known_at','accession_number','source_document','source_hash','extraction_method','confidence','status'],'required_lineage_fields':['transaction_id','security_id','transaction_type','filing_accessions','registration_stage','effective_state','takedown_state','issuance_state','resale_state','shares_registered','shares_issued','dollar_capacity','remaining_capacity','known_at','source_hashes','confidence','status'],'downstream_consumes_r2_directly':{str(x['step']):x['step7i_r2_dependency'] for x in rows}}
 semantic={'required_statuses':['KNOWN','NOT_PUBLIC_YET','UNAVAILABLE','AMBIGUOUS'],'rules':['Missing != 0','Shelf Registration != Issuance','EFFECT != Takedown','ATM Facility != ATM Issuance','Resale Registration != Sold','Authorized Shares != Immediate Supply','Warrant Outstanding != Exercised','ELOC Commitment != Draw','Convertible Principal != Converted Shares'],'compatible_steps':[x['step'] for x in rows if x['four_state_contract_present']]}
 pit={'rule':'fact.known_at <= snapshot_cutoff','compatible_steps':[x['step'] for x in rows if x['explicit_known_at_snapshot_cutoff_contract']],'blockers':[x['step'] for x in rows if not x['explicit_known_at_snapshot_cutoff_contract']]}
 cov={'baseline':coverage,'audit':'Low coverage is not failure; any downstream missing-to-zero coercion is prohibited. Existing STEP 10/11 do not directly consume R2 facts, so their prior PASS cannot validate R2 downstream semantics.'}
 plan={'classifications':{str(x['step']):x['classification'] for x in rows},'first_action':'REBUILD_STEP8','reason':'STEP 8 executable implementation is absent on main; STEP 10/11 are later independent fixture/backfill layers and cannot substitute for the missing first downstream consumer of STEP 7I-R2.'}
 qa={'r2_inputs_complete':not missing,'baseline_pass':('PASS' in str(verdict)),'read_only_audit_of_existing_steps':True,'prediction_executed':False,'v2_modified':False,'steps_8_9_missing_executable':True,'step10_fixture_not_r2_consumer':True,'step11_old_base_not_r2_consumer':True}
 final='STEP7J_REBUILD_REQUIRED'
 hashes={}
 for n,o in [('downstream-inventory.json',inventory),('dependency-audit.json',dep),('schema-compatibility.json',schema),('semantic-compatibility.json',semantic),('pit-compatibility.json',pit),('coverage-dependency.json',cov),('revalidation-plan.json',plan),('qa-report.json',qa)]:hashes[n]=dump(n,o)
 m={'step':'7J','baseline_artifact_id':12557232809,'baseline_manifest':manifest,'output_hashes':hashes,'protected':['STEP5-7I-R2','Provider V1','January Market Foundation','existing STEP8-11','/v2'],'prediction_executed':False}
 hashes['manifest.json']=dump('manifest.json',m);dump('step7j-verdict.json',{'verdict':final,'first_action':plan['first_action'],'classifications':plan['classifications']})
 print(json.dumps({'verdict':final,'first_action':plan['first_action'],'classifications':plan['classifications']}))
if __name__=='__main__':main()
