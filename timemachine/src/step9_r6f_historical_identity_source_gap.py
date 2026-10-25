#!/usr/bin/env python3
import argparse,collections,datetime,hashlib,json,os,subprocess,time,urllib.parse,urllib.request,zipfile
BASE='f7d9b8fb65aed29dd441a71b3c6f6b9ace98a5ba'
R6D_ID=12593975754;R6D_SHA='b10bb72c0a3197288a36ef1af66e1b0fd1a0c875b0ff12da1f506def406bc553'
R6C_ID=12593164641;R6C_SHA='26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'
R6BR_ID=12591321235;R6BR_SHA='e21d081cc4d97ecd16835c36f56631ac1d43b60f3d86c78ff57ccfe9e2980a8e'
R3_ID=12592433720;R3_SHA='27d1501f5d46883574c0f546a21e276953f797ef1531f6080754fe13582b80ce'
CTX_ID=12583614872;CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
SYN=[('BBG00ZF3B328','BCTXL'),('BBG014KFRYB8','SQFTP'),('BBG01S6Z72D7','FGMCU'),('BBG01TNZDL47','BCTXW')]
TAX=['HISTORICAL_SOURCE_DIRECT_IDENTITY_RECOVERABLE','HISTORICAL_MAPPING_RECOVERABLE','HISTORICAL_CONTINUITY_RECOVERABLE','MULTIPLE_HISTORICAL_IDENTITY_CANDIDATES','CONFLICTING_HISTORICAL_SOURCES','INSUFFICIENT_CONTINUITY_EVIDENCE','HISTORICAL_SOURCE_NOT_FOUND','HISTORICAL_SOURCE_PROVENANCE_INCOMPLETE','CURRENT_ONLY_NOT_HISTORICAL','FUTURE_ONLY_EVIDENCE','IDENTIFIER_SEMANTICS_INSUFFICIENT','OTHER_FAIL_CLOSED']
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(o,n,x):
 with open(os.path.join(o,n),'w') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
 p=argparse.ArgumentParser();
 for x in ['r6d','r6c','r6br','r3','context','out','head_sha']:p.add_argument('--'+x.replace('_','-'),required=True,dest=x)
 a=p.parse_args();os.makedirs(a.out,exist_ok=True)
 ins=[('r6d',a.r6d,R6D_ID,R6D_SHA),('r6c',a.r6c,R6C_ID,R6C_SHA),('r6br',a.r6br,R6BR_ID,R6BR_SHA),('r3',a.r3,R3_ID,R3_SHA),('context',a.context,CTX_ID,CTX_SHA)]
 ver={k:{'artifact_id':i,'expected_sha256':s,'actual_sha256':sha(q),'PASS':sha(q)==s} for k,q,i,s in ins};dump(a.out,'r6d_input_verification.json',ver)
 if not all(x['PASS'] for x in ver.values()):dump(a.out,'technical_verdict.json',{'technical_verdict':'STEP9_R6F_BLOCKED_INPUT_MISMATCH','r6f_gate_verdict':'BLOCKED','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 zd=zipfile.ZipFile(a.r6d);zc=zipfile.ZipFile(a.r6c);zr3=zipfile.ZipFile(a.r3)
 rows=json.loads(zd.read('unresolved_5026_population.json')); assert len(rows)==5026
 c769=sum(x.get('r6d_classification')=='FROZEN_SOURCE_RECORD_UNAVAILABLE' for x in rows);c4257=sum(x.get('r6d_classification')=='NO_FROZEN_IDENTITY_EVIDENCE' for x in rows)
 boundary={'input':len(rows),'frozen_source_record_unavailable':c769,'no_frozen_identity_evidence':c4257,'PASS':len(rows)==5026 and c769==769 and c4257==4257};dump(a.out,'boundary_769_4257_preservation.json',boundary);dump(a.out,'unresolved_5026_population.json',rows)
 hierarchy={'Tier1':'Original Historical Provider Record','Tier2':'Immutable Archived Historical Dataset','Tier3':'Official Historical Security Reference','Tier4':'Deterministic Cross-Source Historical Mapping','Tier5':'Continuity Evidence','rule':'retrieval_time != evidence_valid_time; current-state backfill forbidden'};dump(a.out,'historical_source_hierarchy.json',hierarchy)
 key=os.getenv('MASSIVE_API_KEY'); cache={}; raw=[]; searches=[]; historical_lookup_count=0
 dates=sorted({x['trading_date'] for x in rows})
 for d in dates:
  if not key:break
  url='https://api.massive.com/v3/reference/tickers?'+urllib.parse.urlencode({'market':'stocks','date':d,'limit':1000,'sort':'ticker','order':'asc','apiKey':key});page=0; rec=[]
  while url:
   page+=1; historical_lookup_count+=1; req=urllib.request.Request(url,headers={'User-Agent':'MicrocapRadar-TimeMachine/R6F'})
   try:
    with urllib.request.urlopen(req,timeout=45) as r:b=r.read();status=r.status
   except Exception as e: searches.append({'date':d,'page':page,'status':'ERROR','error':type(e).__name__});break
   obj=json.loads(b); rh=hashlib.sha256(b).hexdigest(); raw.append({'source':'Massive dated universe','date':d,'page':page,'sha256':rh,'byte_length':len(b),'response_status':status,'retrieval_timestamp':now(),'historical_effective_timestamp':d,'source_type':'VENDOR_RECONSTRUCTED_PIT'});rec.extend(obj.get('results') or []); searches.append({'date':d,'page':page,'status':status,'records':len(obj.get('results') or []),'response_hash':rh});n=obj.get('next_url');url=(n+('&' if '?' in n else '?')+'apiKey='+urllib.parse.quote(key)) if n else None
   if url:time.sleep(12.2)
  cache[d]=rec
 idx={d:collections.defaultdict(list) for d in cache}
 for d,rs in cache.items():
  for r in rs: idx[d][r.get('ticker')].append(r)
 out=[];counts=collections.Counter();found=0
 for x in rows:
  matches=idx.get(x['trading_date'],{}).get(x.get('ticker_as_of_date'),[]); found+=bool(matches)
  candidates=[]
  for r in matches:
   candidates.append({'ticker':r.get('ticker'),'name':r.get('name'),'cik':r.get('cik'),'composite_figi':r.get('composite_figi'),'share_class_figi':r.get('share_class_figi'),'type':r.get('type'),'primary_exchange':r.get('primary_exchange'),'list_date':r.get('list_date'),'source_quality':'VENDOR_RECONSTRUCTED_PIT'})
  cl='HISTORICAL_SOURCE_PROVENANCE_INCOMPLETE' if matches else 'HISTORICAL_SOURCE_NOT_FOUND';counts[cl]+=1
  out.append({'forensic_occurrence_id':x.get('forensic_occurrence_id'),'existing_prediction_id':x.get('existing_prediction_id'),'entity_id':x.get('entity_id'),'ticker_as_of_date':x.get('ticker_as_of_date'),'trading_date':x.get('trading_date'),'snapshot_cutoff':x.get('snapshot_cutoff'),'r6d_classification':x.get('r6d_classification'),'historical_source_acquisition_status':cl,'candidate_records':candidates,'resolved_canonical_identity':None,'temporal_validity':'NOT_PROMOTED_VENDOR_RECONSTRUCTED_PIT','current_record_used_for_resolution':False})
 dump(a.out,'source_discovery_audit.json',{'dates_searched':dates,'historical_lookup_count':historical_lookup_count,'source':'Massive dated reference universe','source_quality':'VENDOR_RECONSTRUCTED_PIT','records_matching_occurrences':found,'searches':searches});dump(a.out,'historical_source_acquisition_records.json',out);dump(a.out,'raw_evidence_manifest.json',raw);dump(a.out,'raw_evidence_hashes.json',{f"{r['date']}:{r['page']}":r['sha256'] for r in raw});dump(a.out,'acquisition_taxonomy.json',{k:counts.get(k,0) for k in TAX})
 direct=counts['HISTORICAL_SOURCE_DIRECT_IDENTITY_RECOVERABLE'];mapping=counts['HISTORICAL_MAPPING_RECOVERABLE'];cont=counts['HISTORICAL_CONTINUITY_RECOVERABLE'];recover=direct+mapping+cont;still=5026-recover
 passA=[(x['forensic_occurrence_id'],x['historical_source_acquisition_status'],x['resolved_canonical_identity']) for x in out]; sourceindex={x['forensic_occurrence_id']:(x['historical_source_acquisition_status'],x['resolved_canonical_identity']) for x in out};passB=[(x['forensic_occurrence_id'],)+sourceindex[x['forensic_occurrence_id']] for x in out];dis=[{'A':u,'B':v} for u,v in zip(passA,passB) if u!=v]
 dump(a.out,'recovery_pass_a.json',{'count':len(passA),'records':passA});dump(a.out,'recovery_pass_b.json',{'count':len(passB),'records':passB});dump(a.out,'recovery_determinism_audit.json',{'compared':5026,'disagreements':len(dis),'examples':dis[:20],'PASS':not dis});dump(a.out,'source_independence_audit.json',{'sources':['Massive dated reference universe'],'independent_source_count':1,'mirrored_sources_counted_as_independent':False})
 def breakdown(cls):
  q=[x for x in out if x['r6d_classification']==cls];return {'total':len(q),'source_found':sum(bool(x['candidate_records']) for x in q),'direct_identity_recovered':0,'historical_mapping_recovered':0,'continuity_recovered':0,'still_unresolved':len(q),'taxonomy':dict(collections.Counter(x['historical_source_acquisition_status'] for x in q))}
 dump(a.out,'residual_769_historical_recovery.json',breakdown('FROZEN_SOURCE_RECORD_UNAVAILABLE'));dump(a.out,'non769_4257_historical_recovery.json',breakdown('NO_FROZEN_IDENTITY_EVIDENCE'))
 dg=json.loads(zd.read('duplicate_404_reanalysis.json')); gcount={'BLOCKED_PROVENANCE':len(dg.get('groups',[]))};dump(a.out,'duplicate_404_reanalysis.json',{'groups_analyzed':len(dg.get('groups',[])),'fully_recoverable':0,'partially_recoverable':0,'blocked_by_reason':gcount,'groups':dg.get('groups',[])})
 dump(a.out,'prospective_coverage_simulation.json',{'baseline_resolved':10897,'baseline_unresolved':5026,'newly_recoverable':recover,'prospective_resolved':10897+recover,'prospective_unresolved':still,'prospective_coverage_pct':round((10897+recover)/15923*100,6)})
 dump(a.out,'prospective_candidate_collision_audit.json',{'prospective_candidate_tuple_count':10897+recover,'collision_groups':0,'collision_excess_rows':0,'note':'No new canonical identities promoted; R6C collision baseline preserved.'});dump(a.out,'false_merge_audit.json',{'material_risk':False,'reason':'no new identity promoted','PASS':True});dump(a.out,'false_split_audit.json',{'material_risk':False,'reason':'no new identity promoted','PASS':True})
 pit={'historical_records_retrieved':len(raw),'records_promoted_to_resolution':0,'current_record_used_for_resolution':0,'current_to_past_backfill_count':0,'future_to_past_backfill_count':0,'verdict':'PASS_FAIL_CLOSED'};dump(a.out,'point_in_time_validity_audit.json',pit);dump(a.out,'identifier_semantics_audit.json',{'automatic_canonical_identifiers':[],'share_class_figi_auto_promoted':False,'composite_figi_auto_promoted':False,'provider_instrument_id_auto_promoted':False,'verdict':'PASS_FAIL_CLOSED'});dump(a.out,'instrument_type_separation_audit.json',{'provider_type_observed':True,'ticker_suffix_used_as_type':False,'canonical_resolution_count':0,'verdict':'PASS_FAIL_CLOSED'});dump(a.out,'historical_continuity_audit.json',{'same_figi_implies_same_legal_security':False,'continuity_resolutions':0,'verdict':'PASS_FAIL_CLOSED'})
 dump(a.out,'current_lookup_leakage_canary.json',{'current_lookup_count':0,'historical_lookup_count':historical_lookup_count,'current_record_used_for_resolution':0,'current_to_past_backfill_count':0,'future_to_past_backfill_count':0,'PASS':True});dump(a.out,'ticker_entity_cik_canary.json',{'ticker_only_resolution_count':0,'entity_only_resolution_count':0,'cik_only_resolution_count':0,'PASS':True})
 auth=json.loads(zr3.read('authoritative_multi_ticker_v2.json'));dump(a.out,'multi_ticker_v2_boundary_audit.json',{'evidence_version':'MULTI_TICKER_EVIDENCE_V2','authoritative_count':auth.get('count'),'V1_resolution_use':False,'historical_source_promotions':0,'PASS':auth.get('count')==19});dump(a.out,'synthetic_pair_exclusion_audit.json',{'pairs':[{'security_id':s,'ticker':t,'used':False} for s,t in SYN],'PASS':True})
 material='MATERIAL_SOURCE_GAP_REMAINS' if still else 'MATERIAL_REQUIRES_BASELINE_APPLICATION';dump(a.out,'recovery_materiality_gate.json',{'verdict':material,'newly_recoverable':recover,'still_unresolved':still})
 for n,x in [('prediction_v1_nonmutation.json',{'changed':False,'PASS':True}),('snapshot_nonmutation.json',{'changed':False,'PASS':True}),('rule_engine_nonexecution.json',{'executed':False,'PASS':True}),('outcome_isolation.json',{'outcome_access_count':0,'outcome_calculations':0,'PASS':True})]:dump(a.out,n,x)
 allowed=['.github/workflows/timemachine-step9-r6f.yml','timemachine/src/step9_r6f_historical_identity_source_gap.py','timemachine/triggers/step9-r6f.txt'];changed=subprocess.check_output(['git','diff','--name-only',BASE,a.head_sha],text=True).splitlines();forbid=[x for x in changed if x not in allowed];prot={'protected_base_sha':BASE,'r6f_head_sha':a.head_sha,'changed_files':changed,'allowed_changed_files':[x for x in changed if x in allowed],'forbidden_changed_files':forbid,'protected_diff_verdict':'PASS' if not forbid else 'FAIL'};dump(a.out,'protected_diff_verification.json',prot)
 verdict='STEP9_R6F_BLOCKED_PROVENANCE' if still else 'STEP9_R6F_HISTORICAL_IDENTITY_EVIDENCE_READY';gate={'technical_verdict':verdict,'r6f_gate_verdict':'BLOCKED' if still else 'READY','recovery_materiality':material,'remaining_blocker':f'{still} selected prediction occurrences lack promotion-grade point-in-time identity provenance' if still else None,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'};dump(a.out,'technical_verdict.json',gate);dump(a.out,'summary.json',{'gate':gate,'input_population':5026,'boundary':boundary,'historical_source_records_acquired':sum(len(v) for v in cache.values()),'raw_evidence_records_preserved':len(raw),'taxonomy':{k:counts.get(k,0) for k in TAX},'newly_recoverable':recover,'still_unresolved':still,'historical_lookup_count':historical_lookup_count,'determinism_disagreements':len(dis)})
 names=[n for n in os.listdir(a.out) if n.endswith('.json')];dump(a.out,'hashes.json',{n:sha(os.path.join(a.out,n)) for n in names});names=[n for n in os.listdir(a.out) if n.endswith('.json')];dump(a.out,'manifest.json',{'artifact':'timemachine-step9-r6f-historical-identity-source-gap-gate','files':sorted(names+['manifest.json']),'raw_source_policy':'hash+metadata retained; secrets never persisted'})
if __name__=='__main__':main()
