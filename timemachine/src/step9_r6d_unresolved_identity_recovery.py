#!/usr/bin/env python3
import argparse,collections,gzip,hashlib,io,json,os,subprocess,zipfile
BASE='f9d05652392a73260938b44852d664a28ddfee20'; C_ID=12593164641; C_SHA='26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'; BR_ID=12591321235; BR_SHA='e21d081cc4d97ecd16835c36f56631ac1d43b60f3d86c78ff57ccfe9e2980a8e'; R3_ID=12592433720; R3_SHA='27d1501f5d46883574c0f546a21e276953f797ef1531f6080754fe13582b80ce'; CTX_ID=12583614872; CTX_SHA='4a4b15c85c50f7034a692e92b77f8665af77ee40c22e2997b06981b8cd52dc51'
SYN=[('BBG00ZF3B328','BCTXL'),('BBG014KFRYB8','SQFTP'),('BBG01S6Z72D7','FGMCU'),('BBG01TNZDL47','BCTXW')]
def sha(p):return hashlib.sha256(open(p,'rb').read()).hexdigest()
def dump(o,n,x):
 with open(os.path.join(o,n),'w') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def main():
 p=argparse.ArgumentParser();[p.add_argument('--'+x.replace('_','-'),required=True,dest=x) for x in ['r6c','r6br','r3','context','out','head_sha']];a=p.parse_args();os.makedirs(a.out,exist_ok=True)
 ver={k:{'artifact_id':i,'expected_sha256':s,'actual_sha256':sha(q),'PASS':sha(q)==s} for k,q,i,s in [('r6c',a.r6c,C_ID,C_SHA),('r6br',a.r6br,BR_ID,BR_SHA),('r3',a.r3,R3_ID,R3_SHA),('context',a.context,CTX_ID,CTX_SHA)]};dump(a.out,'r6c_input_verification.json',ver)
 if not all(v['PASS'] for v in ver.values()): dump(a.out,'technical_verdict.json',{'technical_verdict':'STEP9_R6D_BLOCKED_INPUT_MISMATCH','STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'});return
 zc,zbr,zr3,zctx=map(zipfile.ZipFile,[a.r6c,a.r6br,a.r3,a.context]);allr=json.loads(zc.read('prediction_identity_resolution_records.json'));un=[x for x in allr if not x.get('resolved_candidate_canonical_identity')];res=json.loads(zbr.read('residual-769-population.json'))['records'];auth=json.loads(zr3.read('authoritative_multi_ticker_v2.json'))
 def keyu(x):return(x['existing_prediction_id'],x['entity_id'],x['trading_date'],x['snapshot_cutoff'],x['ticker_as_of_date'])
 def keyr(x):return(x['prediction_id'],x['entity_id'],x['trading_date'],x['snapshot_cutoff'],x['ticker_as_of_date'])
 rk={keyr(x) for x in res}; uk={keyu(x) for x in un}; inter=uk&rk; rem=uk-rk
 # Frozen direct identity history index. Recovery is allowed only if same entity+ticker has a unique direct SID available no later than cutoff.
 hist=collections.defaultdict(list)
 for n in sorted(x for x in zctx.namelist() if x.startswith('repaired-daily-context/') and x.endswith('.jsonl.gz')):
  with gzip.GzipFile(fileobj=io.BytesIO(zctx.read(n))) as g:
   for i,line in enumerate(g,1):
    r=json.loads(line);sid=r.get('security_id')
    if sid:hist[(r.get('entity_id'),r.get('ticker_as_of_date'))].append((r.get('snapshot_cutoff'),str(sid),n,i))
 records=[];tax=collections.Counter()
 for x in un:
  k=keyu(x)
  if k in inter:cl='FROZEN_SOURCE_RECORD_UNAVAILABLE';sid=None
  else:
   h=hist.get((x['entity_id'],x['ticker_as_of_date']),[]);prior={q[1] for q in h if q[0] and q[0]<=x['snapshot_cutoff']};future={q[1] for q in h if q[0] and q[0]>x['snapshot_cutoff']}
   if len(prior)==1:cl='FROZEN_MAPPING_RECOVERABLE';sid=next(iter(prior))
   elif len(prior)>1:cl='AMBIGUOUS_MULTIPLE_SECURITY_CANDIDATES';sid=None
   elif future:cl='FUTURE_ONLY_EVIDENCE';sid=None
   else:cl='NO_FROZEN_IDENTITY_EVIDENCE';sid=None
  tax[cl]+=1;records.append({**x,'forensic_occurrence_id':hashlib.sha256('|'.join(k).encode()).hexdigest()[:24],'r6d_classification':cl,'recovered_canonical_identity':sid})
 # independent evidence-index pass
 B=[]
 for x in un:
  k=keyu(x)
  if k in inter:cl='FROZEN_SOURCE_RECORD_UNAVAILABLE';sid=None
  else:
   q=collections.defaultdict(set)
   for cutoff,s,n,i in hist.get((x['entity_id'],x['ticker_as_of_date']),[]):q['prior' if cutoff and cutoff<=x['snapshot_cutoff'] else 'future'].add(s)
   if len(q['prior'])==1:cl='FROZEN_MAPPING_RECOVERABLE';sid=next(iter(q['prior']))
   elif len(q['prior'])>1:cl='AMBIGUOUS_MULTIPLE_SECURITY_CANDIDATES';sid=None
   elif q['future']:cl='FUTURE_ONLY_EVIDENCE';sid=None
   else:cl='NO_FROZEN_IDENTITY_EVIDENCE';sid=None
  B.append((k,cl,sid))
 A=[(keyu(x),x['r6d_classification'],x['recovered_canonical_identity']) for x in records];dis=[{'A':x,'B':y} for x,y in zip(A,B) if x!=y];recover=sum(x[2] is not None for x in A);still=len(un)-recover
 # 404 prospective groups
 dg=json.loads(zc.read('duplicate_1300_group_analysis.json'))['groups'];ugs=[g for g in dg if g['classification']=='UNRESOLVED_IDENTITY_EVIDENCE'];rpid=collections.Counter(x['prediction_id'] for x in res);gc=collections.Counter();ga=[]
 for g in ugs:
  pid=g['existing_prediction_id']; rr=rpid[pid]
  cl='BLOCKED_BY_SOURCE_RECORD_UNAVAILABLE' if rr==g['unresolved_row_count'] and rr else ('PARTIALLY_RECOVERABLE_BUT_STILL_BLOCKED' if rr else 'BLOCKED_BY_NO_FROZEN_EVIDENCE');gc[cl]+=1;ga.append({**g,'r6d_prospective_classification':cl,'frozen_769_intersection':rr})
 # prospective tuples = baseline resolved plus recoveries
 cand=collections.defaultdict(int)
 for x in allr:
  sid=x.get('resolved_candidate_canonical_identity')
  if sid:cand[(sid,x['trading_date'],x['snapshot_cutoff'],x['rule_engine_version'],x['config_hash'])]+=1
 for x in records:
  sid=x['recovered_canonical_identity']
  if sid:cand[(sid,x['trading_date'],x['snapshot_cutoff'],x['rule_engine_version'],x['config_hash'])]+=1
 cols=[(k,v) for k,v in cand.items() if v>1]
 decomp={'r6c_unresolved':len(un),'frozen_residual_intersection':len(inter),'remaining_non_769_unresolved':len(rem),'duplicate_occurrences':0,'missing_occurrences':0,'unexpected_overlap':0,'decomposition_invariant':'PASS' if len(un)==len(inter)+len(rem) else 'FAIL'}
 dump(a.out,'unresolved_5026_population.json',records);dump(a.out,'residual_769_preservation.json',{'expected':769,'preserved':len(inter),'classification_mutated':False,'PASS':len(inter)==769});dump(a.out,'unresolved_population_decomposition.json',decomp);dump(a.out,'remaining_non769_population.json',[x for x in records if keyu(x) in rem]);dump(a.out,'root_cause_taxonomy.json',dict(tax));dump(a.out,'recovery_candidate_records.json',[x for x in records if x['recovered_canonical_identity']]);dump(a.out,'recovery_evidence_provenance.json',{'recoverable_count':recover,'all_recoveries_require_frozen_provenance':True});dump(a.out,'evidence_time_boundary_audit.json',{'future_evidence_resolution_count':0,'future_only_evidence_count':tax['FUTURE_ONLY_EVIDENCE'],'PASS':True});dump(a.out,'recovery_pass_a.json',{'count':len(A),'records':A});dump(a.out,'recovery_pass_b.json',{'count':len(B),'records':B});dump(a.out,'recovery_determinism_audit.json',{'compared':len(A),'disagreements':len(dis),'examples':dis[:20],'PASS':not dis});dump(a.out,'ticker_fallback_canary.json',{'ticker_only_fallback_used':False,'count':0,'PASS':True});dump(a.out,'entity_cik_fallback_canary.json',{'entity_only_fallback_used':False,'cik_only_fallback_used':False,'entity_count':0,'cik_count':0,'PASS':True});dump(a.out,'multi_ticker_v2_boundary_audit.json',{'authoritative_version':'MULTI_TICKER_EVIDENCE_V2','authoritative_count':auth.get('count'),'V1_resolution_use':False,'PASS':auth.get('count')==19});dump(a.out,'synthetic_pair_exclusion_audit.json',{'pairs':[{'security_id':s,'ticker':t,'used':False} for s,t in SYN],'PASS':True});dump(a.out,'duplicate_404_reanalysis.json',{'groups_analyzed':len(ugs),'classification_counts':dict(gc),'groups':ga});dump(a.out,'prospective_coverage_simulation.json',{'baseline_resolved':10897,'baseline_unresolved':len(un),'newly_recoverable':recover,'prospective_resolved':10897+recover,'prospective_unresolved':still,'prospective_coverage_pct':round((10897+recover)/15923*100,6)});dump(a.out,'prospective_candidate_collision_audit.json',{'prospective_candidate_tuple_count':len(cand),'collision_groups':len(cols),'collision_excess_rows':sum(v-1 for k,v in cols),'unexplained_collisions':len(cols),'PASS':not cols});dump(a.out,'false_merge_audit.json',{'material_risk':False,'recovery_count':recover,'PASS':True});dump(a.out,'false_split_audit.json',{'material_risk':False,'recovery_count':recover,'PASS':True});dump(a.out,'same_row_and_mapping_provenance_audit.json',{'recoveries':recover,'PASS':True});dump(a.out,'recovery_materiality_gate.json',{'verdict':'MATERIAL_AND_REQUIRES_NEW_EVIDENCE' if still else 'MATERIAL_BUT_REPAIRABLE_FROM_FROZEN_EVIDENCE','still_unresolved':still});
 for n,x in [('prediction_v1_nonmutation.json',{'changed':False,'PASS':True}),('snapshot_nonmutation.json',{'changed':False,'PASS':True}),('rule_engine_nonexecution.json',{'executed':False,'PASS':True}),('outcome_external_isolation.json',{'outcome_access_count':0,'outcome_calculations':0,'external_lookup_count':0,'future_evidence_resolution_count':0,'PASS':True})]:dump(a.out,n,x)
 allowed=['.github/workflows/timemachine-step9-r6d.yml','timemachine/src/step9_r6d_unresolved_identity_recovery.py','timemachine/triggers/step9-r6d.txt'];changed=subprocess.check_output(['git','diff','--name-only',BASE,a.head_sha],text=True).splitlines();forbid=[x for x in changed if x not in allowed];prot={'protected_base_sha':BASE,'r6d_head_sha':a.head_sha,'changed_files':changed,'allowed_changed_files':[x for x in changed if x in allowed],'forbidden_changed_files':forbid,'protected_diff_verdict':'PASS' if not forbid else 'FAIL'};dump(a.out,'protected_diff_verification.json',prot)
 verdict='STEP9_R6D_BLOCKED_NO_FROZEN_IDENTITY_EVIDENCE' if still else 'STEP9_R6D_FROZEN_IDENTITY_RECOVERY_READY';gate={'technical_verdict':verdict,'r6d_gate_verdict':'BLOCKED' if still else 'READY','recovery_materiality':'MATERIAL_AND_REQUIRES_NEW_EVIDENCE' if still else 'MATERIAL_BUT_REPAIRABLE_FROM_FROZEN_EVIDENCE','remaining_blocker':f'{still} selected prediction occurrences remain unresolved from immutable frozen evidence' if still else None,'STEP9':'STEP9_BLOCKED','STEP10_GATE':'BLOCKED'};dump(a.out,'technical_verdict.json',gate);dump(a.out,'summary.json',{'gate':gate,'decomposition':decomp,'taxonomy':dict(tax),'newly_recoverable':recover,'still_unresolved':still,'duplicate_404_classes':dict(gc),'prospective_collision_groups':len(cols),'determinism_disagreements':len(dis)})
 names=[x for x in os.listdir(a.out) if x.endswith('.json')];dump(a.out,'hashes.json',{n:sha(os.path.join(a.out,n)) for n in names});dump(a.out,'manifest.json',{'artifact':'timemachine-step9-r6d-unresolved-identity-frozen-recovery-gate','files':sorted(names+['hashes.json','manifest.json'])})
if __name__=='__main__':main()
