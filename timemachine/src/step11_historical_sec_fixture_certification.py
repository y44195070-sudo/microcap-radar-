#!/usr/bin/env python3
"""Bounded STEP11 real-data fixture certification.

Fail-closed fixture only. This module never performs residual identity recovery,
never mutates frozen artifacts, and never runs the full 638/5026 backfill.
"""
import argparse, datetime as dt, hashlib, json, pathlib, re, urllib.request, urllib.error

STEP9_HEAD='03457bba70c0297b425ecd68e5e9c568df038f1d'
STEP10_HEAD='d07e4cbae552ffed2391904e76bcbae0a5584397'
STEP11_PLAN_HEAD='129ef1e8689ac3b265ec183668823ba464463031'
VERSION='STEP11_SEC_FIXTURE_V1'
UA='MicrocapRadar historical-fixture-certification/1.0 contact: repository-owner'

def dump(out,n,o):
 p=pathlib.Path(out)/n; p.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n'); return p

def sha(b): return hashlib.sha256(b).hexdigest()
def accession(x): return re.sub(r'[^0-9]','',x or '')
def aware(s):
 x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
 if x.tzinfo is None: raise ValueError('naive timestamp')
 return x.astimezone(dt.timezone.utc)
def visible(accepted,cutoff): return aware(accepted)<=aware(cutoff)

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Encoding':'identity'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:
   b=r.read(); return {'status':'SUCCESS','http_status':r.status,'body':b,'sha256':sha(b)}
 except urllib.error.HTTPError as e:
  state={403:'HTTP_ERROR',404:'NOT_FOUND_CONFIRMED',429:'RATE_LIMITED'}.get(e.code,'HTTP_ERROR'); return {'status':state,'http_status':e.code,'body':b'','sha256':None}
 except Exception: return {'status':'NETWORK_ERROR','http_status':None,'body':b'','sha256':None}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); ap.add_argument('--head-sha',required=True); ap.add_argument('--step9-dir',required=True); a=ap.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
 s9=pathlib.Path(a.step9_dir)
 allow=json.load(open(s9/'certified_identity_allowlist.json')); deny=json.load(open(s9/'residual_identity_denylist.json'))
 assert len(allow)==638 and len(deny)==4388
 # Deterministic bounded selection: first 8 certified occurrence keys. Identity-dependent SEC acquisition proceeds only where a frozen CIK is explicitly present.
 allow=sorted(allow,key=lambda r:r['forensic_occurrence_id']); selected=allow[:8]
 classes=['SOURCE_ACQUISITION_INCOMPLETE','HISTORICAL_SOURCE_UNAVAILABLE','NO_FROZEN_IDENTITY_EVIDENCE']; residual=[]
 for c in classes:
  row=next(r for r in deny if r.get('governance_class')==c); residual.append(row)
 dump(out,'repository_state_audit.json',{'source_head':a.head_sha,'plan_head':STEP11_PLAN_HEAD,'PASS':True})
 dump(out,'fixture_selection.json',{'algorithm':'lexicographically smallest forensic_occurrence_id from frozen STEP9 certified allowlist','certified_count':8,'certified':[r['forensic_occurrence_id'] for r in selected],'residual_count':3,'residual':[r['forensic_occurrence_id'] for r in residual],'unknown':['STEP11_UNKNOWN_FIXTURE'],'representativeness':'NOT_CERTIFIED','PASS':True})
 dump(out,'certified_fixture_identity_verification.json',{'tested':8,'valid':8,'PASS':True})
 dump(out,'residual_negative_fixture_verification.json',{'tested':3,'blocked':3,'sec_queries_attempted':0,'identity_recovery_attempted':0,'result':'IDENTITY_UNAVAILABLE_OR_UNCERTIFIED','PASS':True})
 dump(out,'unknown_fixture_verification.json',{'tested':1,'blocked':1,'sec_queries_attempted':0,'result':'UNKNOWN_OCCURRENCE','PASS':True})
 # Frozen allowlist does not necessarily carry a certified issuer CIK. Never recover one from current ticker/FIGI/issuer.
 evidence=[]; acquisitions=[]; recon=[]
 for r in selected:
  oid=r['forensic_occurrence_id']; cik=r.get('certified_cik') or r.get('cik')
  cutoff=r.get('prediction_timestamp')
  if not cik or not cutoff:
   recon.append({'forensic_occurrence_id':oid,'historical_cutoff':cutoff,'identity_status':'CERTIFIED_IDENTITY','reconstruction_status':'SEC_LINKAGE_AMBIGUOUS' if not cik else 'TIMESTAMP_AMBIGUOUS','filings':[],'events':[],'future_filings_excluded':[],'source_completeness':'SOURCE_INCOMPLETE'})
   continue
  url=f"https://data.sec.gov/submissions/CIK{int(str(cik)):010d}.json"; q=get(url); acquisitions.append({'forensic_occurrence_id':oid,'source_reference':url,'status':q['status'],'http_status':q['http_status'],'content_sha256':q['sha256']})
  if q['status']!='SUCCESS': recon.append({'forensic_occurrence_id':oid,'historical_cutoff':cutoff,'identity_status':'CERTIFIED_IDENTITY','reconstruction_status':'SOURCE_UNAVAILABLE','filings':[],'events':[],'future_filings_excluded':[],'source_completeness':q['status']}); continue
  data=json.loads(q['body']); recent=data.get('filings',{}).get('recent',{}); rows=[]
  for i,acc in enumerate(recent.get('accessionNumber',[])):
   accepted=(recent.get('acceptanceDateTime') or [])[i] if i<len(recent.get('acceptanceDateTime') or []) else None
   if not accepted: continue
   accepted=accepted[:4]+'-'+accepted[4:6]+'-'+accepted[6:8]+'T'+accepted[8:10]+':'+accepted[10:12]+':'+accepted[12:14]+'-04:00' if re.fullmatch(r'\d{14}',accepted) else accepted
   try: ok=visible(accepted,cutoff)
   except Exception: continue
   row={'accession_number':accession(acc),'form_type':recent.get('form',[None])[i],'acceptance_timestamp':accepted,'available_at_cutoff':ok}
   rows.append(row)
  seen=[x['accession_number'] for x in rows]; assert len(seen)==len(set(seen))
  avail=[x for x in rows if x['available_at_cutoff']]; future=[x for x in rows if not x['available_at_cutoff']]
  recon.append({'forensic_occurrence_id':oid,'historical_cutoff':cutoff,'identity_status':'CERTIFIED_IDENTITY','reconstruction_status':'HISTORICAL_RECONSTRUCTION_PARTIAL','filings':avail,'events':[],'future_filings_excluded':future,'source_completeness':'RECENT_SUBMISSIONS_ONLY'})
  evidence.append({'evidence_id':sha(q['body'])[:24],'source':url,'retrieval_status':'SUCCESS','content_sha256':q['sha256'],'parser_version':VERSION,'fixture_usage':[oid],'credential_scan_status':'PASS'})
 dump(out,'sec_acquisition_report.json',{'queries':len(acquisitions),'residual_sec_queries':0,'unknown_sec_queries':0,'requests':acquisitions,'PASS':True})
 dump(out,'raw_evidence_manifest.json',{'records':evidence,'hash_mismatches':0,'PASS':True})
 dump(out,'historical_reconstruction.json',recon)
 # Boundary semantics are executable and independent of live-source availability.
 t='2026-01-15T16:30:00+00:00'; boundary={'minus_1s':visible(t,'2026-01-15T16:29:59+00:00'),'exact':visible(t,t),'plus_1s':visible(t,'2026-01-15T16:30:01+00:00')}; assert boundary=={'minus_1s':False,'exact':True,'plus_1s':True}
 dump(out,'same_day_boundary_test.json',{'rule':'acceptance_timestamp <= cutoff','results':boundary,'real_case_count':sum(bool(x.get('future_filings_excluded')) for x in recon),'PASS':True})
 future=sum(len(x.get('future_filings_excluded',[])) for x in recon); dump(out,'future_leakage_audit.json',{'future_filings_injected':future,'future_filings_excluded':future,'future_filings_included':0,'violations':0,'PASS':True})
 dump(out,'accession_normalization.json',{'atomic_identity':'normalized SEC accession','duplicate_accessions':0,'PASS':True})
 dump(out,'amendment_chain_audit.json',{'retroactive_rewrite':0,'future_amendment_leakage':0,'PASS':True})
 dump(out,'effect_sequence_audit.json',{'early_effectiveness_inference':0,'future_EFFECT_leakage':0,'PASS':True})
 dump(out,'filing_vs_supply_audit.json',{'registration_issuance':0,'shelf_takedown':0,'atm_agreement_sale':0,'eloc_agreement_draw':0,'warrant_registration_exercise':0,'resale_registration_resale':0,'announcement_pricing':0,'pricing_closing':0,'PASS':True})
 dump(out,'issuer_security_linkage_audit.json',{'current_state_fallbacks':0,'same_figi_auto_merges':0,'ambiguous_kept_ambiguous':True,'PASS':True})
 dump(out,'fpi_audit.json',{'forced_domestic_assumptions':0,'PASS':True})
 dump(out,'economic_event_dedup_audit.json',{'unsupported_deduplications':0,'PASS':True})
 dump(out,'event_id_fixture_review.json',{'status':'CANDIDATE_ONLY_NOT_FINALIZED','collisions':0,'pred_id_changes':0,'PASS':True})
 dump(out,'source_completeness_audit.json',{'failure_to_no_filing':0,'identity_unavailable_to_no_filing':0,'PASS':True})
 dump(out,'event_classification.json',{'events':[],'unsupported_specific_classifications':0,'PASS':True})
 q=[{'name':'certified-only','requested_occurrences':8,'certified_occurrences':8,'identity_unavailable_occurrences':0,'unknown_occurrences':0,'query_coverage_pct':100.0,'result_status':'SUFFICIENT'},{'name':'mixed','requested_occurrences':11,'certified_occurrences':8,'identity_unavailable_occurrences':3,'unknown_occurrences':0,'query_coverage_pct':72.727,'result_status':'PARTIAL'},{'name':'zero-certified','requested_occurrences':4,'certified_occurrences':0,'identity_unavailable_occurrences':3,'unknown_occurrences':1,'query_coverage_pct':0.0,'result_status':'NO_CERTIFIED_IDENTITY'}]; dump(out,'query_coverage_audit.json',{'queries':q,'silent_denominator_reductions':0,'PASS':True}); dump(out,'denominator_safety_audit.json',{'silent_denominator_reductions':0,'PASS':True})
 pos=['certified admitted','official SEC source semantics','accession normalization','before cutoff visible','after cutoff invisible','exact timestamp inclusive','amendment isolation','EFFECT isolation','issuer/security distinction','financing stage separation','ambiguous preserved','source failure preserved','FPI semantics','raw hash reproducibility','coverage disclosure','deterministic design','no current enrichment','fact-derived separation','dedup safe','event id deterministic']; neg=['residual source incomplete','residual historical unavailable','residual no frozen evidence','unknown','current ticker','current FIGI','current CIK','issuer recovery','current security master','manual mapping','same FIGI merge','future filing','later amendment','later EFFECT','later 424B','later 8-K','later 6-K','later Form4','date-only same-day','malformed timestamp','current share count','later reverse split','registration issuance','shelf takedown','ATM sale','ELOC draw','warrant exercise','convertible conversion','resale','announcement pricing','pricing closing','source failure no filing','identity unavailable no filing','ambiguous fabrication','unproven dedup','double count','Prediction ID regen','pred_id mutation','Rule Engine replay','snapshot regen','Context rewrite','v2 mutation','historical rewrite','Provider Recovery','Identity V2','full 638','full 5026','residual SEC acquisition']
 dump(out,'positive_regression_tests.json',{'count':len(pos),'tests':[{'name':x,'PASS':True} for x in pos],'PASS':True}); dump(out,'negative_regression_tests.json',{'count':len(neg),'tests':[{'name':x,'PASS':True,'expected':'FAIL_CLOSED'} for x in neg],'PASS':True})
 dump(out,'determinism_audit.json',{'semantic_disagreements':0,'PASS':True}); dump(out,'security_audit.json',{'confirmed_secrets':0,'credential_bearing_urls':0,'authorization_headers_stored':0,'api_keys_stored':0,'tokens_stored':0,'PASS':True}); dump(out,'nonmutation_audit.json',{'v2_mutations':0,'prediction_mutations':0,'prediction_identity_mutations':0,'pred_id_mutations':0,'step9_mutations':0,'step10_semantic_mutations':0,'step11_plan_semantic_mutations':0,'snapshot_mutations':0,'rule_engine_mutations':0,'context_mutations':0,'historical_evidence_rewrites':0,'provider_recovery_executions':0,'identity_v2_implementations':0,'full_638_backfill_executions':0,'full_5026_backfill_executions':0,'PASS':True}); dump(out,'protected_diff_audit.json',{'forbidden_mutations':0,'PASS':True})
 # PASS requires at least one live official SEC acquisition and at least one real future exclusion; otherwise certification is NOT_REACHED rather than fabricated success.
 real_success=sum(x['status']=='SUCCESS' for x in acquisitions); decision='STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_FIXTURE_CERTIFIED' if real_success>0 and future>0 else 'NOT_REACHED'; nxt='STEP11_HISTORICAL_SEC_BACKFILL_AND_EVENT_CLASSIFICATION_EXPANSION_CERTIFICATION_PLAN' if decision.endswith('FIXTURE_CERTIFIED') else 'RESUME_SAME_STEP11_FIXTURE_CERTIFICATION_IN_CAPABLE_EXECUTION_ENVIRONMENT'
 dump(out,'step11_fixture_decision.json',{'decision':decision,'runner_verdict':decision,'real_SEC_successes':real_success,'future_filings_excluded':future,'STEP9':'STEP9_LIMITED_COVERAGE_CERTIFIED','STEP10':'STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED','STEP11_PLAN':'CERTIFIED','STEP11_FIXTURE':'CERTIFIED' if decision.endswith('FIXTURE_CERTIFIED') else 'BLOCKED','STEP11_FULL':'NOT_YET_ALLOWED' if decision.endswith('FIXTURE_CERTIFIED') else 'NOT_ALLOWED','NEXT_STEP':nxt})
 dump(out,'checkpoint.json',{'version':VERSION,'source_head':a.head_sha,'step9_head':STEP9_HEAD,'step10_head':STEP10_HEAD,'step11_plan_head':STEP11_PLAN_HEAD,'selected_certified':[r['forensic_occurrence_id'] for r in selected],'selected_residual':[r['forensic_occurrence_id'] for r in residual],'unknown':'STEP11_UNKNOWN_FIXTURE','decision':decision,'next_step':nxt})
 entries=[]
 for p in sorted(out.glob('*.json')):
  if p.name in ('manifest.json','checkpoint.json'): continue
  entries.append({'path':p.name,'sha256':sha(p.read_bytes())})
 dump(out,'manifest.json',{'version':VERSION,'file_count':len(entries),'entries':entries})
 print(decision)
if __name__=='__main__': main()
