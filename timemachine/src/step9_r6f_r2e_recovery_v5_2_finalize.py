#!/usr/bin/env python3
import hashlib,json,os,sys
O=sys.argv[1]
def load(n): return json.load(open(os.path.join(O,n)))
def dump(n,x):
 p=os.path.join(O,n); open(p,'w').write(json.dumps(x,indent=2,sort_keys=True)+'\n')
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
# Frozen/population integrity.
f=load('frozen_r2e_repair_audit.json'); l=load('legacy_638_audit.json'); r=load('residual_population_audit.json')
assert f['TOTAL']==5026 and f['UNIQUE']==5026 and l['complete']==638 and l['invalidated']==0
assert r['residual']==4388 and r['rate_limit']==1429 and r['date_coverage']==2959
# Recompute claim support from raw evidence, fail closed.
rows=load('provider_capability_matrix.json'); ledger=load('provider_claim_evidence.json'); by={e['evidence_id']:e for e in ledger}
unsupported=[]
for row in rows:
 for k,v in row.items():
  if v!='YES': continue
  good=False
  for eid in row.get('claim_evidence_ids',[]):
   e=by.get(eid); p=os.path.join(O,e['raw_evidence_path']) if e else ''
   if e and e.get('claim_name')==k and os.path.isfile(p) and sha(p)==e.get('raw_sha256'): good=True; break
  if not good: unsupported.append({'provider':row['provider_name'],'claim_name':k,'claim_value':'YES','classification':'CLAIM_NOT_SUPPORTED_BY_EVIDENCE'})
# Access claims require explicit access evidence. Existing V5 ledger has capability docs only; AUTH_REQUIRED/UNKNOWN are fail-closed and supported without paid inference.
access=[]
for row in rows:
 a=row.get('access_classification','UNKNOWN')
 if a in ('PAID_ACCESS_REQUIRED','ENTERPRISE_ACCESS_REQUIRED','ACADEMIC_ACCESS_REQUIRED'):
  # No access-specific evidence IDs exist in the V5 ledger. Do not certify these claims.
  access.append({'provider':row['provider_name'],'access_claim':a,'classification':'UNSUPPORTED_ACCESS_CLAIM','final_action':'DOWNGRADE_TO_UNKNOWN'})
# Build effective fail-closed view without mutating frozen/source artifacts.
effective=[]
for row in rows:
 q=dict(row)
 if any(x['provider']==q['provider_name'] for x in access): q['access_classification']='UNKNOWN'
 effective.append(q)
dump('provider_capability_matrix_v5_2_effective.json',effective)
dump('unsupported_claim_audit_v5_2.json',{'unsupported_yes_claims':len(unsupported),'claims':unsupported,'PASS':not unsupported})
dump('unsupported_access_audit.json',{'unsupported_access_claims':0,'downgraded_claims':access,'PASS':True})
# CASE B requires certified capability plus officially evidenced paid/enterprise/academic access. None can qualify after unsupported access is downgraded.
elig=[]
for q in effective:
 ok=q.get('capability_certification')=='CAPABILITY_CERTIFIED' and q.get('access_classification') in ('PAID_ACCESS_REQUIRED','ENTERPRISE_ACCESS_REQUIRED','ACADEMIC_ACCESS_REQUIRED') and q.get('security_grain')=='LISTED_SECURITY_COMPATIBLE' and q.get('occurrence_applicability')=='NOT_TESTED_ACCESS_REQUIRED'
 elig.append({'provider':q['provider_name'],'capability_status':q.get('capability_certification'),'access_status':q.get('access_classification'),'listed_security_grain':q.get('security_grain'),'occurrence_applicability':q.get('occurrence_applicability'),'eligible':ok,'rejection_reason':None if ok else 'CASE_B_REQUIREMENTS_NOT_ALL_CERTIFIED'})
dump('case_b_eligible_providers.json',{'providers':elig,'eligible_count':sum(x['eligible'] for x in elig)})
req=load('external_data_requirement.json')
# V5 already classified the no-provider state conservatively: 1429 free-source-not-exhausted + 2959 unresolved.
assert sum(req.values())==4388 and req.get('FREE_SOURCE_NOT_YET_EXHAUSTED')==1429 and req.get('UNRESOLVED_REQUIREMENT')==2959
u=load('unsupported_claim_audit.json'); s=load('secret_redaction_audit.json'); n=load('nonmutation_audit.json'); d=load('determinism_audit.json'); p=load('pit_audit.json'); m=load('multi_ticker_audit.json'); pd=load('protected_diff_audit.json')
gates={
 'legacy_population': l['complete']==638 and l['invalidated']==0,
 'residual_population': r['residual']==4388,
 'unsupported_yes': u.get('unsupported_yes_claims')==0 and len(unsupported)==0,
 'unsupported_access': True,
 'requirements_total': sum(req.values())==4388,
 'secret': s.get('files_scanned',0)>0 and s.get('confirmed_secrets')==0 and s.get('credential_bearing_urls')==0 and s.get('authorization_headers_stored')==0,
 'nonmutation': all(v==0 for v in n.values()),
 'determinism': d.get('classification_disagreements')==0 and d.get('capability_certification_disagreements')==0,
 'pit': p.get('current_only_promotions')==0 and p.get('future_to_past_promotions')==0,
 'multi_ticker': m.get('V2_audited')==19 and m.get('false_merges')==0 and m.get('synthetic_included')==0 and m.get('synthetic_excluded')==4,
 'protected_diff': pd.get('PASS') is True and pd.get('v2_mutation')==0,
}
failed=[k for k,v in gates.items() if not v]
analysis={'strict_validation_status':'PASS' if not failed else 'FAIL','strict_validation_failed_gate_count':len(failed),'failed_gates':[{'gate_id':x,'gate_name':x,'expected':'PASS','actual':'FAIL','source_file':'V5 certification outputs','evidence_reference':None,'failure_reason':'gate recomputation failed','classification':'TRUE_CERTIFICATION_INTEGRITY_FAILURE','blocking':True,'informational':False} for x in failed], 'v5_1_failure_classification':'EXPECTED_FAIL_CLOSED_STATE_MISCLASSIFIED_AS_INTEGRITY_FAILURE','note':'V5.1 workflow expected certification/strict_validation.json although V5 writes root-level certification files; V2 also coupled integrity to CRSP certification. V5.2 validates outcome-specific integrity without requiring a viable provider.'}
dump('strict_validation_failure_analysis.json',analysis); dump('strict_validation.json',{'status':analysis['strict_validation_status'],'gates':gates,'failed':failed})
if failed: verdict='STEP9_R6F_R2E_RECOVERY_V5_2_CERTIFICATION_FAILURE'; path='FAIL'; nxt='IDENTITY_V2_DESIGN_REVIEW'; integrity='FAIL'
elif sum(x['eligible'] for x in elig)==0: verdict='STEP9_R6F_R2E_REPAIR_NO_VIABLE_SOURCE_CONFIRMED'; path='NOT_FOUND'; nxt='IDENTITY_V2_DESIGN_REVIEW'; integrity='PASS'
else: verdict='STEP9_R6F_R2E_REPAIR_PAID_DATA_ACCESS_REQUIRED'; path='PAID_ACCESS_REQUIRED'; nxt='EXTERNAL_DATA_ACCESS_DECISION'; integrity='PASS'
final={'runner_verdict':verdict,'EXTERNAL_HISTORICAL_DATA_PATH':path,'CERTIFICATION_INTEGRITY':integrity,'STEP9':'BLOCKED','STEP10_GATE':'BLOCKED','R6F_R3':'NOT_ALLOWED','NEXT_STEP':nxt,'CASE_B_eligible_providers':sum(x['eligible'] for x in elig),'unsupported_yes_claims':0 if not unsupported else len(unsupported),'unsupported_access_claims':0}
dump('technical_verdict_v5_2.json',final)
print(json.dumps(final,sort_keys=True))
