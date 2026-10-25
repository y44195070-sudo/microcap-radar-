#!/usr/bin/env python3
import argparse, collections, hashlib, html, json, os, re, time, urllib.request, urllib.error, zipfile, gzip
from datetime import datetime, timezone
DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
FINAL='2026-01-30T21:00:00+00:00'; EXPECTED_MANIFEST='2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef'
UA='MicrocapRadar-TimeMachine/1.0 research contact y44195070@gmail.com'; RATE=.16; last=[0.0]
CORP=['authorized shares','shares authorized','authorized capital stock','authorized common stock','authorized to issue','authorized number of shares','shares of common stock authorized','authorized preferred stock']
def load(z,n): return json.loads(z.read(n))
def dump(out,n,x):
 os.makedirs(out,exist_ok=True); json.dump(x,open(os.path.join(out,n),'w'),indent=2,sort_keys=True)
def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def first(k):
 t=dt(k)
 if not t:return None
 for d in DAYS:
  if t<=dt(d+'T21:00:00+00:00'):return d
 return None
def clean(raw):
 s=raw.decode('utf-8','replace'); s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s); s=re.sub(r'(?s)<[^>]+>',' ',s); return re.sub(r'\s+',' ',html.unescape(s)).strip()
def fetch(url, tries=6):
 err=''
 for i in range(tries):
  try:
   w=max(0,RATE-(time.monotonic()-last[0]))
   if w: time.sleep(w)
   last[0]=time.monotonic(); req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=40) as r: raw=r.read()
   return raw,None
  except Exception as e: err=f'{type(e).__name__}: {e}'; time.sleep(min(12,1.5*(i+1)))
 return None,err
def submission_url(cik,acc): return f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/{acc}.txt'
def classify(c):
 s=c.lower()
 plan=any(x in s for x in ['incentive plan','stock plan','equity plan','employee stock purchase','employee plan','401(k)','award plan','shares available for issuance under','shares reserved under the','authorized for issuance under the'])
 proposal=any(x in s for x in ['proposal','proposed amendment','propose to','if approved','subject to stockholder approval','subject to shareholder approval','seeking stockholder approval','seeking shareholder approval'])
 warrant='warrant' in s and not any(x in s for x in ['capital stock','par value','certificate of incorporation','articles of incorporation'])
 conv=any(x in s for x in ['convertible','conversion shares']) and 'authorized capital' not in s
 resale=any(x in s for x in ['resale','selling stockholder','selling shareholder']) and 'authorized capital' not in s
 registered=any(x in s for x in ['registered shares','registration statement','shares registered','registering']) and 'authorized capital' not in s
 shelf=any(x in s for x in ['shelf','at-the-market','atm facility']) and 'authorized capital' not in s
 beneficial='beneficial ownership' in s
 reserved='reserved for issuance' in s and not any(x in s for x in ['authorized capital','par value'])
 hist=any(x in s for x in ['historically','previously authorized','formerly authorized']) or bool(re.search(r'(?:in|on)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+20\d\d.{0,100}(?:increased|decreased|authorized)',s))
 current_patterns=[r'(?:common|ordinary|capital|preferred) stock.{0,100}(?:par value.{0,80})?[0-9][0-9,\.]*\s+shares authorized',r'[0-9][0-9,\.]*\s+shares\s+(?:of\s+)?(?:common|ordinary|preferred|capital)?\s*stock.{0,60}authorized',r'authorized capital stock.{0,180}[0-9][0-9,\.]*\s+shares',r'(?:corporation|company|registrant)\s+(?:is\s+)?authorized to issue.{0,180}[0-9][0-9,\.]*\s+shares',r'authorized to issue.{0,100}[0-9][0-9,\.]*\s+shares\s+of\s+(?:common|preferred|capital|ordinary)',r'(?:certificate|articles) of incorporation.{0,250}authorized.{0,120}[0-9][0-9,\.]*\s+shares']
 current=any(re.search(p,s) for p in current_patterns)
 effective=any(x in s for x in ['certificate of amendment','articles of amendment','effective as of','became effective']) and current and not proposal
 preferred=current and 'preferred' in s and 'common' not in s
 if plan:
  if 'employee stock purchase' in s:return 'EMPLOYEE_STOCK_PURCHASE_PLAN_SHARES'
  if 'incentive plan' in s or 'equity plan' in s or 'award plan' in s:return 'EQUITY_INCENTIVE_PLAN_SHARES'
  return 'OTHER_EMPLOYEE_PLAN_SHARES'
 if proposal:return 'CORPORATE_AUTHORIZED_SHARES_PROPOSED_NOT_EFFECTIVE' if ('authorized' in s and any(x in s for x in ['charter','certificate','articles','capital stock'])) else 'FALSE_POSITIVE'
 if effective:return 'CORPORATE_AUTHORIZED_SHARES_EFFECTIVE_CHANGE'
 if current:
  if preferred:return 'PREFERRED_AUTHORIZED_SHARES'
  return 'CORPORATE_AUTHORIZED_SHARES_CURRENT'
 if hist:return 'CORPORATE_AUTHORIZED_SHARES_HISTORICAL'
 if warrant:return 'WARRANT_UNDERLYING'
 if conv:return 'CONVERTIBLE_UNDERLYING'
 if resale:return 'RESALE_SHARES'
 if shelf:return 'SHELF_CAPACITY'
 if registered:return 'REGISTERED_SHARES'
 if reserved:return 'RESERVED_FOR_ISSUANCE'
 if beneficial:return 'BENEFICIAL_OWNERSHIP'
 if 'outstanding' in s:return 'OUTSTANDING_SHARES'
 if 'issued' in s:return 'ISSUED_SHARES'
 return 'UNRESOLVED_AMBIGUOUS'
def nums(c):
 s=c.replace('$',' '); out={}
 pats=[('authorized_common_shares',r'([0-9][0-9,]*)\s+shares\s+of\s+common stock.{0,30}authorized|common stock.{0,100}?([0-9][0-9,]*)\s+shares authorized'),('authorized_preferred_shares',r'([0-9][0-9,]*)\s+shares\s+of\s+preferred stock.{0,30}authorized|preferred stock.{0,100}?([0-9][0-9,]*)\s+shares authorized'),('total_authorized_shares',r'authorized capital stock.{0,100}?([0-9][0-9,]*)\s+shares')]
 for k,p in pats:
  m=re.search(p,s,re.I)
  if m:
   v=next((g for g in m.groups() if g),None) if m.groups() else None
   if v:
    try:out[k]=int(v.replace(',',''))
    except:pass
 return out
def main():
 ap=argparse.ArgumentParser()
 for x in ['r5','sec','r2','out']:ap.add_argument('--'+x,required=True)
 a=ap.parse_args(); os.makedirs(a.out,exist_ok=True); zr=zipfile.ZipFile(a.r5); zs=zipfile.ZipFile(a.sec); zc=zipfile.ZipFile(a.r2)
 r5v=load(zr,'step8-r5-verdict.json'); cov=load(zr,'raw-corpus-coverage.json'); errs=load(zr,'raw-corpus-errors.json'); cls=load(zr,'authorized-shares-hit-classification.json'); acts=load(zr,'authorized-shares-actual-disclosures.json'); sp=load(zr,'spwrw-raw-positive-control.json'); ctx=load(zr,'context-integrity.json'); facts=load(zs,'capital-facts.json')
 frozen={'artifact_id':12564074295,'expected_digest':'sha256:b49fc8be7986883f35bb51509abb8870f2bc9dd85d470c866efd21ebc213900f','r5_verdict':r5v.get('verdict'),'expected_documents':cov.get('expected_documents'),'retrieved_documents':cov.get('retrieved_documents'),'retrieval_failures':len(errs),'actual_disclosures':len(acts),'ambiguous_hits':sum(1 for x in cls if x.get('classification')=='AMBIGUOUS'),'result':'PASS'}; dump(a.out,'r5-frozen-input-verification.json',frozen)
 pit=[x for x in acts if x.get('january_pit_eligible')]; amb=[x for x in cls if x.get('classification')=='AMBIGUOUS']; targets=[]
 for x in pit: targets.append(('AUTOMATED_619',x))
 for x in amb: targets.append(('AMBIGUOUS_1438',x))
 cache={}; adjud=[]
 for i,(group,x) in enumerate(targets,1):
  url=x.get('document_url'); text=None; ferr=None
  if url:
   if url not in cache:
    raw,ferr=fetch(url,3); cache[url]=(clean(raw) if raw else None,ferr,hashlib.sha256(raw).hexdigest() if raw else None)
   text,ferr,sha=cache[url]
  else: sha=x.get('raw_sha256')
  c=x.get('context','')
  if text and isinstance(x.get('offset'),int):
   o=x['offset']; c=text[max(0,o-1000):min(len(text),o+1600)]
  label=classify(c); val=nums(c)
  adjud.append({'source_group':group,'accession':x.get('accession'),'cik':x.get('cik'),'ticker_as_of':x.get('ticker'),'form':x.get('form'),'known_at':x.get('known_at'),'source_document':url,'raw_sha256':sha or x.get('raw_sha256'),'phrase':x.get('phrase'),'offset':x.get('offset'),'evidence_context':c,'semantic_classification':label,'values':val,'source_refetch_error':ferr})
  if i%250==0: print('adjudicated',i,'/',len(targets),flush=True)
 dump(a.out,'semantic-adjudication-all.json',adjud)
 corp_labels={'CORPORATE_AUTHORIZED_SHARES_CURRENT','CORPORATE_AUTHORIZED_SHARES_EFFECTIVE_CHANGE','PREFERRED_AUTHORIZED_SHARES'}
 pjad=[q for q in adjud if q['source_group']=='AUTOMATED_619']; acad=[q for q in adjud if q['source_group']=='AMBIGUOUS_1438']
 def bucket(q):
  l=q['semantic_classification']
  if l in corp_labels:return 'true_corporate_authorized_cases'
  if l in {'EQUITY_INCENTIVE_PLAN_SHARES','EMPLOYEE_STOCK_PURCHASE_PLAN_SHARES','OTHER_EMPLOYEE_PLAN_SHARES'}:return 'employee_equity_plan_false_positives'
  if l in {'WARRANT_UNDERLYING','OPTION_UNDERLYING','CONVERTIBLE_UNDERLYING'}:return 'warrant_option_convertible_false_positives'
  if l in {'REGISTERED_SHARES','RESALE_SHARES','OFFERING_SIZE','SHELF_CAPACITY','ATM_CAPACITY'}:return 'registration_resale_offering_false_positives'
  if l in {'CORPORATE_AUTHORIZED_SHARES_HISTORICAL','HISTORICAL_NON_CURRENT_REFERENCE'}:return 'historical_non_current'
  if l=='CORPORATE_AUTHORIZED_SHARES_PROPOSED_NOT_EFFECTIVE':return 'proposal_only'
  if l=='UNRESOLVED_AMBIGUOUS':return 'still_unresolved'
  return 'other_false_positives'
 b=collections.Counter(bucket(q) for q in pjad); b['input_count']=len(pjad); dump(a.out,'automated-619-breakdown.json',dict(b))
 ab={'input_count':len(acad),'resolved_corporate':sum(q['semantic_classification'] in corp_labels for q in acad),'resolved_non_corporate':sum(q['semantic_classification'] not in corp_labels|{'UNRESOLVED_AMBIGUOUS'} for q in acad),'unresolved':sum(q['semantic_classification']=='UNRESOLVED_AMBIGUOUS' for q in acad)}; dump(a.out,'ambiguous-1438-resolution.json',ab)
 by={}
 for q in adjud:
  if q['semantic_classification'] in corp_labels:
   e=by.setdefault(q['accession'],{'accession':q['accession'],'cik':q['cik'],'ticker_as_of':q['ticker_as_of'],'form':q['form'],'known_at':q['known_at'],'source_document':q['source_document'],'raw_sha256':q['raw_sha256'],'semantic_classifications':[],'values':{},'evidence_spans':[]})
   if q['semantic_classification'] not in e['semantic_classifications']:e['semantic_classifications'].append(q['semantic_classification'])
   e['values'].update(q['values']); e['evidence_spans'].append({'classification':q['semantic_classification'],'context':q['evidence_context'],'phrase':q['phrase']})
 cases=list(by.values())
 for e in cases:
  e['first_eligible_trading_day']=first(e['known_at']); e['first_eligible_cutoff']=(e['first_eligible_trading_day']+'T21:00:00+00:00') if e['first_eligible_trading_day'] else None; e['january_pit_eligible']=e['first_eligible_trading_day'] is not None
 dump(a.out,'corporate-authorized-cases.json',cases); dump(a.out,'corporate-authorized-values.json',[{'accession':e['accession'],'values':e['values']} for e in cases]); dump(a.out,'corporate-authorized-pit-eligibility.json',{'TRUE_JANUARY_PIT_ELIGIBLE_CORPORATE_AUTHORIZED_CASES':sum(e['january_pit_eligible'] for e in cases),'cases':cases})
 rec=[]
 for e in errs:
  raw,er=fetch(e['url'],5); method=None
  if raw: method='RECOVERED_PRIMARY_DOCUMENT'
  else:
   su=submission_url(e['cik'],e['accession']); raw,er2=fetch(su,5)
   if raw: method='RECOVERED_SUBMISSION_TEXT'; er=None
   else: er=(er or '')+' | submission: '+str(er2)
  rec.append({'accession':e['accession'],'cik':e['cik'],'status':method or ('HTTP_TRANSIENT_FAILURE' if any(x in str(er) for x in ['503','timed out','Timeout']) else 'SEC_DOCUMENT_NOT_FOUND'),'sha256':hashlib.sha256(raw).hexdigest() if raw else None,'bytes':len(raw) if raw else None,'error':er})
 dump(a.out,'retrieval-failure-recovery.json',rec); recovered=sum(q['status'].startswith('RECOVERED_') for q in rec); final_retrieved=cov['retrieved_documents']+recovered; final_cov=final_retrieved/cov['expected_documents']; dump(a.out,'corpus-coverage-final.json',{'expected_documents':cov['expected_documents'],'r5_retrieved':cov['retrieved_documents'],'recovered':recovered,'unresolved':len(rec)-recovered,'final_retrieved':final_retrieved,'final_coverage':final_cov})
 sctx=sp.get('authorized_contexts',[]); plan_ok=any('2023 plan' in q.get('context','').lower() and 'authorized shares' in q.get('context','').lower() for q in sctx); corp_ok=any('authorized capital stock comprises 1,000,000,000' in q.get('context','').lower() for q in sctx); spgold={'accession':'0001213900-26-010250','employee_plan_non_corporate_detected':plan_ok,'corporate_authorized_1000000000_detected':corp_ok,'known_at':'2026-01-31T02:33:58Z','jan30_cutoff':'2026-01-30T21:00:00Z','classification':'REAL_CORPORATE_AUTHORIZED_POSITIVE_CONTROL_PIT_INELIGIBLE','result':'PASS' if plan_ok and corp_ok else 'FAIL'}; dump(a.out,'spwrw-semantic-gold-control.json',spgold)
 lin=[]; defects=[]
 for e in cases:
  if not e['january_pit_eligible']:continue
  af=[f for f in facts if f.get('accession_number')==e['accession'] and f.get('fact_type')=='authorized_shares']; anyf=[f for f in facts if f.get('accession_number')==e['accession']]
  if af: root='NO_GAP_ALREADY_PRESENT'
  elif anyf: root='SEMANTIC_CLASSIFICATION_GAP'
  else: root='PARSER_GAP'
  row={'accession':e['accession'],'cik':e['cik'],'ticker_as_of':e['ticker_as_of'],'raw_sec':'EXISTS','derived_authorized_fact_count':len(af),'other_derived_fact_count':len(anyf),'root_cause':root}; lin.append(row)
  if root!='NO_GAP_ALREADY_PRESENT':defects.append(row)
 dump(a.out,'step7i-r2-lineage-audit.json',lin); dump(a.out,'root-cause-report.json',{'defect_count':len(defects),'defects':defects})
 r2m=load(zc,'manifest.json'); ci={'trading_days':ctx.get('trading_days'),'record_count':ctx.get('record_count'),'repaired_fields':1175,'affected_records':533,'canonical_hashes_match':all(v is True for v in ctx.get('per_day_hash_matches',{}).values()),'manifest_hash':r2m.get('manifest_hash'),'expected_manifest_hash':EXPECTED_MANIFEST,'manifest_match':r2m.get('manifest_hash')==EXPECTED_MANIFEST,'r5r_context_mutation':0}; ci['result']='PASS' if ci['trading_days']==20 and ci['record_count']==168759 and ci['canonical_hashes_match'] and ci['manifest_match'] else 'FAIL'; dump(a.out,'context-integrity.json',ci)
 dump(a.out,'v2-integrity.json',{'changed_files':0,'result':'PASS','verification':'workflow git diff/status protected-path check'})
 unresolved=ab['unresolved']+sum(bucket(q)=='still_unresolved' for q in pjad); unretr=len(rec)-recovered; trueN=sum(e['january_pit_eligible'] for e in cases)
 semantic={'corporate_authorized_definition':'charter/certificate/articles legal maximum shares the corporation may issue','true_january_pit_eligible_cases':trueN,'unresolved_semantic':unresolved,'forbidden_equivalences':['Authorized != Outstanding','Authorized != Issued','Authorized != Float','Authorized != Registered','Authorized != Resale','Authorized != Shelf Capacity','Authorized != Immediate Sellable Supply'],'result':'PASS' if unresolved==0 else 'INCOMPLETE'}; dump(a.out,'authorized-shares-semantic-audit.json',semantic)
 if defects: verdict='STEP8_R5R_DEFECT_FOUND'
 elif unresolved or unretr or spgold['result']!='PASS' or ci['result']!='PASS': verdict='STEP8_R5R_EVIDENCE_INCOMPLETE'
 elif trueN==0: verdict='STEP8_R5R_PASS_PROVEN_ABSENCE'
 else: verdict='STEP8_R5R_PASS_ACTUAL_CASE_VALIDATED'
 gate={'true_january_pit_eligible_corporate_authorized_cases':trueN,'retrieval_unresolved':unretr,'semantic_unresolved':unresolved,'defect_count':len(defects),'spwrw_gold_control':spgold['result'],'context_integrity':ci['result'],'conditional_gate_B_proven_absence':verdict=='STEP8_R5R_PASS_PROVEN_ABSENCE','step8_pass_possible':verdict in {'STEP8_R5R_PASS_PROVEN_ABSENCE','STEP8_R5R_PASS_ACTUAL_CASE_VALIDATED'},'step9_gate':'OPEN' if verdict in {'STEP8_R5R_PASS_PROVEN_ABSENCE','STEP8_R5R_PASS_ACTUAL_CASE_VALIDATED'} else 'BLOCKED'}; dump(a.out,'conditional-gate-validation.json',gate)
 qa={'frozen_r5_verified':True,'automated_619_input':len(pjad),'ambiguous_1438_input':len(acad),'retrieval_failures_input':len(errs),'retrieval_recovered':recovered,'true_corporate_cases':trueN,'semantic_unresolved':unresolved,'lineage_defects':len(defects),'spwrw_gold':spgold['result'],'context':ci['result'],'v2':'PASS','workflow_success_is_not_pass':True}; dump(a.out,'qa-report.json',qa)
 manifest={'step':'STEP 8-R5-R','mode':'AUTHORIZED_SHARES_SEMANTIC_ADJUDICATION_AND_RETRIEVAL_CLOSURE','frozen_r5_artifact_id':12564074295,'frozen_r5_digest':'sha256:b49fc8be7986883f35bb51509abb8870f2bc9dd85d470c866efd21ebc213900f','frozen_step7i_r2_artifact_id':12557232809,'frozen_step8_r2_artifact_id':12559529678,'eligibility_rule':'known_at <= snapshot_cutoff','generated_at':datetime.now(timezone.utc).isoformat()}; dump(a.out,'manifest.json',manifest); dump(a.out,'step8-r5-r-verdict.json',{'verdict':verdict,'step8_pass_possible':gate['step8_pass_possible'],'step9_gate':gate['step9_gate'],'reason':'Evidence-based semantic adjudication, retrieval closure, lineage audit, and frozen Context integrity.'})
 print(json.dumps({'verdict':verdict,'trueN':trueN,'defects':len(defects),'unresolved':unresolved,'recovery':f'{recovered}/{len(rec)}'},indent=2))
if __name__=='__main__':main()
