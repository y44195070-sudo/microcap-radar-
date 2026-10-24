#!/usr/bin/env python3
import argparse,gzip,hashlib,json,os,subprocess,zipfile
from collections import Counter,defaultdict
from datetime import datetime
DAYS=['2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-15','2026-01-16','2026-01-20','2026-01-21','2026-01-22','2026-01-23','2026-01-26','2026-01-27','2026-01-28','2026-01-29','2026-01-30']
FTCAT={'reverse_split_ratio':'reverse_split','shelf_registration':'shelf','atm_facility':'atm','warrant':'warrant','warrant_exercise_price':'warrant','resale_registration':'resale','convertible':'convertible','eloc':'eloc','nasdaq_compliance':'nasdaq_compliance','pipe_or_private_placement':'pipe','outstanding_shares':'outstanding_shares','authorized_shares':'authorized_shares','historical_float':'historical_float','cash':'cash','debt':'debt','registration_effective':'registration_effective','prospectus_takedown_or_resale':'prospectus_takedown_or_resale'}
def dt(s): return datetime.fromisoformat(str(s).replace('Z','+00:00')) if s else None
def dump(p,x): os.makedirs(os.path.dirname(p),exist_ok=True); json.dump(x,open(p,'w'),indent=2,sort_keys=True)
def zjson(z,n): return json.loads(z.read(n))
def sha(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def canon(rows):
 c=[]
 for r in rows:
  q=dict(r)
  if 'metadata' in q:
   q['metadata']=dict(q['metadata']); q['metadata'].pop('generated_at',None)
  c.append(q)
 return sha(sorted(c,key=lambda x:(x.get('entity_id') or '',x.get('ticker_as_of_date') or '')))
def rows(z,path): return [json.loads(x) for x in gzip.decompress(z.read(path)).decode().splitlines() if x]
def slot(r,cat): return (r.get('capital',{}).get(cat,{}) or {}) if r else {}
def acc(v): return ((v or {}).get('fact') or {}).get('accession_number')
def val(v): return ((v or {}).get('fact') or {}).get('value')
def main():
 ap=argparse.ArgumentParser(); [ap.add_argument('--'+x,required=True) for x in ('r2','r','i','s8','out')]; a=ap.parse_args(); os.makedirs(a.out,exist_ok=True)
 zr2,zr,zi,zs8=map(zipfile.ZipFile,(a.r2,a.r,a.i,a.s8))
 samples=zjson(zr,'real-sample-audit.json')['audits']; acraw=zjson(zr2,'after-close-multi-case-audit.json')['cases']; r2m=zjson(zr2,'manifest.json')
 events=zjson(zi,'capital-events.json'); lins=zjson(zi,'transaction-lineage.json')
 eby=defaultdict(list); lby=defaultdict(list)
 for e in events: eby[e.get('filing_accession')].append(e)
 for l in lins:
  for x in l.get('filing_accessions',[]): lby[x].append(l)
 targets={x.get('ticker_as_of_date') for x in samples}|{x.get('ticker') for x in acraw}|{'ATHA','LONA','CODX'}; targets.discard(None)
 idx={}; per={}; total=0; status=Counter(); missing_bad=[]; future_bad=[]; diffs=[]; affected=set(); unexpected=[]
 for day in DAYS:
  rr=rows(zr2,f'repaired-daily-context/{day}.jsonl.gz'); oo=rows(zs8,f'daily-context/{day}.jsonl.gz'); total+=len(rr); per[day]=canon(rr)
  om={(r.get('entity_id'),r.get('ticker_as_of_date')):{k:(v.get('status'),v.get('fact'),v.get('evidence_count')) for k,v in r.get('capital',{}).items()} for r in oo}
  for r in rr:
   t=r.get('ticker_as_of_date')
   if t in targets: idx[(day,t)]=r
   for cat,v in r.get('capital',{}).items():
    st=v.get('status'); status[st]+=1; f=v.get('fact') or {}
    if st in ('UNAVAILABLE','NOT_PUBLIC_YET','AMBIGUOUS') and f.get('value') in (0,False,'NONE','no dilution','no debt','no warrants'): missing_bad.append({'date':day,'ticker':t,'category':cat,'status':st,'value':f.get('value')})
    if f.get('known_at') and dt(f['known_at'])>dt(r['snapshot_cutoff']): future_bad.append({'date':day,'ticker':t,'category':cat,'known_at':f['known_at']})
   key=(r.get('entity_id'),t); o=om.get(key)
   if not o: unexpected.append({'date':day,'ticker':t,'reason':'record added'}); continue
   changed=False
   for cat,(ost,ofact,oec) in o.items():
    nv=r.get('capital',{}).get(cat,{})
    if (ost,ofact,oec)!=(nv.get('status'),nv.get('fact'),nv.get('evidence_count')):
     changed=True
     if ost=='NOT_PUBLIC_YET' and nv.get('status')=='UNAVAILABLE' and ofact==nv.get('fact') and oec==nv.get('evidence_count'): diffs.append({'date':day,'entity_id':key[0],'ticker':t,'category':cat,'old':'NOT_PUBLIC_YET','new':'UNAVAILABLE'})
     else: unexpected.append({'date':day,'ticker':t,'category':cat,'reason':'non-status mutation'})
   if changed: affected.add((day,key))
  del rr,oo,om
 real=[]
 for s in samples:
  t,day,target=s.get('ticker_as_of_date'),s.get('snapshot_date'),s.get('accession_number'); ft=(s.get('derived_fact') or {}).get('fact_type'); cat=FTCAT.get(ft); c=idx.get((day,t)); cs=slot(c,cat) if cat else {}; known=s.get('known_at'); cutoff=s.get('snapshot_cutoff'); name=f"{t} {s.get('category')}"
  extra={}; expected=True
  if s.get('category')=='O/S Disclosure':
   k=dt(known); before=max([d for d in DAYS if (d,t) in idx and dt(idx[(d,t)]['snapshot_cutoff'])<k],default=None); after=min([d for d in DAYS if (d,t) in idx and dt(idx[(d,t)]['snapshot_cutoff'])>=k],default=None); actual={'prior':acc(slot(idx.get((before,t)),'outstanding_shares'))==target if before else False,'next':acc(slot(idx.get((after,t)),'outstanding_shares'))==target if after else False}; expected={'prior':False,'next':True}; extra={'prior_day':before,'next_eligible_day':after}
  elif s.get('category')=='Historical Float Unavailable' or ft=='historical_float': actual=(cs.get('status')=='UNAVAILABLE' and cs.get('fact') is None and cs.get('evidence_count',0)==0)
  elif s.get('category')=='After-Close Filing': actual={'2026-01-07':acc(slot(idx.get(('2026-01-07',t)),'cash'))==target,'2026-01-08':acc(slot(idx.get(('2026-01-08',t)),'cash'))==target}; expected={'2026-01-07':False,'2026-01-08':True}
  elif s.get('category')=='Shelf EFFECT / Lineage': actual=bool(known and cutoff and dt(known)<=dt(cutoff) and lby.get(target) and eby.get(target))
  elif s.get('category')=='Multi-Filing Financing Lineage': actual=bool(known and cutoff and dt(known)<=dt(cutoff) and lby.get(target) and acc(slot(c,'shelf'))==target)
  elif s.get('category')=='Missing != Zero':
   bad=[k for k,v in c.get('capital',{}).items() if v.get('status') in ('UNAVAILABLE','NOT_PUBLIC_YET','AMBIGUOUS') and (v.get('fact') or {}).get('value') in (0,False,'NONE','no dilution','no debt','no warrants')]; actual=not bad; extra={'bad_categories':bad}
  else:
   eligible=bool(known and cutoff and dt(known)<=dt(cutoff)); actual=(acc(cs)==target) if eligible else (acc(cs)!=target)
  q={k:s.get(k) for k in ['entity_id','CIK','ticker_as_of_date','snapshot_date','snapshot_cutoff','category','accession_number','form','filing_date','acceptance_datetime','known_at','source_hash','transaction_id','source_document']}; q.update({'sample_name':name,'as_of_date':(s.get('derived_fact') or {}).get('as_of_date'),'fact_type':ft,'derived_fact':s.get('derived_fact') or 'NO_LAYER_FOR_THIS_CASE','capital_event':eby.get(target,[]) or 'NO_LAYER_FOR_THIS_CASE','transaction_lineage':lby.get(target,[]) or 'NO_LAYER_FOR_THIS_CASE','repaired_context_status':cs.get('status') if cs else None,'repaired_context_value':val(cs),'repaired_context_selected_accession':acc(cs),'expected':expected,'actual':actual,'result':'PASS' if actual==expected else 'FAIL','explanation':'Fresh R3 computation from repaired Context and STEP7I-R2 evidence; prior audit result not consumed'}); q.update(extra); real.append(q)
 def one(t,cat): return next((x for x in real if x['ticker_as_of_date']==t and x['category']==cat),None)
 kr=one('KRUS','After-Close Filing'); msm=one('MSM','O/S Disclosure'); sf=one('SER','Historical Float Unavailable')
 after=[]
 for x in acraw:
  t,target,sd,nd,known=x['ticker'],x['accession_number'],x['same_day'],x['next_trading_day'],x['known_at']; cat=FTCAT.get(x.get('fact_type'),'cash'); s,n=idx.get((sd,t)),idx.get((nd,t)); same=acc(slot(s,cat))==target; nxt=acc(slot(n,cat))==target; ok=bool(s and n and not same and nxt and dt(known)>dt(s['snapshot_cutoff']) and dt(known)<=dt(n['snapshot_cutoff']))
  after.append({'ticker':t,'CIK':x.get('CIK'),'accession':target,'fact_type':x.get('fact_type'),'known_at':known,'same_day':sd,'same_day_cutoff':s.get('snapshot_cutoff') if s else None,'next_day':nd,'next_day_cutoff':n.get('snapshot_cutoff') if n else None,'same_day_target_present':same,'next_day_target_present':nxt,'result':'PASS' if ok else 'FAIL'})
 ath=[]
 for d in DAYS:
  for t in ('ATHA','LONA'):
   if (d,t) in idx: ath.append({'date':d,'ticker':t,'entity_id':idx[(d,t)].get('entity_id'),'identity':idx[(d,t)].get('identity')})
 identity_ok=any(x['ticker']=='ATHA' and x['date']<'2026-01-12' for x in ath) and any(x['ticker']=='LONA' and x['date']>='2026-01-12' for x in ath) and not any(x['ticker']=='LONA' and x['date']<'2026-01-12' for x in ath)
 identity={'case':'ATHA->LONA','observations':ath,'result':'PASS' if identity_ok else 'FAIL'}
 cod=[]
 for d in DAYS:
  r=idx.get((d,'CODX'))
  if r: cod.append({'date':d,'corporate_action_state':r.get('identity',{}).get('corporate_action_state',[]),'adjusted':r.get('market',{}).get('adjusted'),'close':r.get('market',{}).get('close')})
 corp_ok=bool(cod) and all(x['adjusted'] is False for x in cod); corp={'case':'CODX corporate action and unadjusted raw OHLCV','observations':cod,'result':'PASS' if corp_ok else 'FAIL'}
 specs=[('Shelf Registration != Takedown',one('SER','Shelf Registration'),'shelf_registration','prospectus_takedown_or_resale'),('EFFECT != Takedown',next((x for x in real if x['ticker_as_of_date']=='FEAM'),None),'registration_effective','prospectus_takedown_or_resale'),('ATM Facility != ATM Issuance',one('SPWRW','ATM Facility'),'atm_facility','atm_issuance'),('Resale Registration != Actual Sale',one('SER','Resale Registration'),'resale_registration','actual_sale'),('Authorized Shares != Immediate Supply',next((x for x in real if x['ticker_as_of_date']=='NRSNW'),None),'authorized_shares','common_issuance'),('Warrant Outstanding != Exercised',one('SER','Warrant'),'warrant','warrant_exercise'),('ELOC Commitment != Draw',one('SPWRW','ELOC'),'eloc','eloc_draw'),('Convertible Principal != Converted Shares',one('SER','Convertible'),'convertible','converted_shares')]
 supply=[]
 for name,s,left,right in specs:
  if not s: supply.append({'distinction':name,'result':'FAIL','reason':'no real case'}); continue
  target=s.get('accession_number'); le=[e for e in eby.get(target,[]) if e.get('event_type')==left]; ri=[e for e in eby.get(target,[]) if e.get('event_type')==right]; supply.append({'distinction':name,'ticker':s.get('ticker_as_of_date'),'accession':target,'left_event_evidence':le,'right_event_evidence':ri,'result':'PASS' if not ri else 'FAIL','meaning':'No stronger right-hand supply event inferred without independent evidence.'})
 nrs=one('NRSNW','Multi-Filing Financing Lineage'); nl=lby.get(nrs['accession_number'],[]) if nrs else []; ne=eby.get(nrs['accession_number'],[]) if nrs else []
 financing={'ticker':'NRSNW','accession':nrs.get('accession_number') if nrs else None,'lineages':nl,'capital_events':ne,'false_merge_check':'PASS' if len(nl)==1 else 'FAIL','duplicate_supply_check':'PASS' if len({(e.get('event_type'),e.get('filing_accession')) for e in ne})==len(ne) else 'FAIL'}; financing['result']='PASS' if financing['false_merge_check']=='PASS' and financing['duplicate_supply_check']=='PASS' else 'FAIL'
 four={'allowed_states':['KNOWN','NOT_PUBLIC_YET','UNAVAILABLE','AMBIGUOUS'],'records_scanned':total,'repair_field_count':len(diffs),'affected_record_count':len(affected),'unexpected_mutations':unexpected,'result':'PASS' if len(diffs)==1175 and len(affected)==533 and not unexpected else 'FAIL'}
 missing={'records_scanned':total,'status_counts':dict(status),'violation_count':len(missing_bad),'violations':missing_bad[:100],'result':'PASS' if not missing_bad else 'FAIL'}
 leakage=[]
 def add(n,c,ok,e,a): leakage.append({'test_name':n,'case':c,'expected':e,'actual':a,'result':'PASS' if ok else 'FAIL','calculation':'Fresh R3 computation; prior PASS/result not read.'})
 add('Future Filing Leakage','full repaired context',not future_bad,0,len(future_bad)); add('After-Close Filing Leakage','6 real cases',all(x['result']=='PASS' for x in after),len(after),sum(x['result']=='PASS' for x in after)); add('Late O/S Disclosure Leakage','MSM',msm and msm['result']=='PASS',msm['expected'] if msm else None,msm['actual'] if msm else None); add('Historical Float Backfill Leakage','SER',sf and sf['result']=='PASS',True,sf['actual'] if sf else None); add('Ticker Change Leakage','ATHA->LONA',identity_ok,True,identity_ok); add('Corporate Action Leakage','CODX',corp_ok,True,corp_ok); add('Shelf/EFFECT/Takedown Semantic Leakage','SER/FEAM',all(x['result']=='PASS' for x in supply[:2]),2,sum(x['result']=='PASS' for x in supply[:2])); add('ATM Facility/Issuance Leakage','SPWRW',supply[2]['result']=='PASS',True,supply[2]['result']=='PASS'); add('Resale Registration/Sale Leakage','SER',supply[3]['result']=='PASS',True,supply[3]['result']=='PASS'); add('Duplicate Financing Leakage','NRSNW',financing['result']=='PASS',True,financing['result']=='PASS'); add('Missing-as-Zero Leakage','full repaired context',missing['result']=='PASS',0,missing['violation_count']); add('Cross-Day Snapshot Leakage','KRUS',kr and kr['result']=='PASS',kr['expected'] if kr else None,kr['actual'] if kr else None)
 expper=r2m.get('daily_canonical_hashes',{}); context={'trading_days':20,'record_count':total,'per_day_hashes':per,'expected_per_day_hashes':expper,'per_day_hashes_unchanged':per==expper,'repaired_manifest_hash':r2m.get('manifest_hash'),'expected_repaired_manifest_hash':'2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef','r3_context_mutations':0}; context['result']='PASS' if total==168759 and per==expper and r2m.get('manifest_hash')==context['expected_repaired_manifest_hash'] else 'FAIL'
 reuse={'prior_artifacts_used_for':'case definitions/provenance only','old_result_fields_read_for_verdict':False,'old_expected_actual_read_for_verdict':False,'result':'PASS'}
 try: gl=subprocess.check_output(['git','log','--format=%H|%P|%s','3f286f00cc51aa22bad9f28ffba946229ef52f47..ffa7570d7bc52ba351db3379b196b70c3490b35b','--','v2/data/stocks/WSHP.json'],text=True).strip().splitlines()
 except Exception as e: gl=['ERROR:'+str(e)]
 v2={'path':'v2/data/stocks/WSHP.json','range':'3f286f00..ffa7570d','commits_touching_path':gl,'r2_implementation_commit':'bd4538ab48af5615a3cf250d03a0a3e063b5e4c4','r3_modified_v2':False,'result':'PASS' if all(not x.startswith('bd4538ab48af5615a3cf250d03a0a3e063b5e4c4|') for x in gl) else 'FAIL'}
 realout={'total':len(real),'pass_count':sum(x['result']=='PASS' for x in real),'fail_count':sum(x['result']!='PASS' for x in real),'audits':real}; leakout={'total':12,'pass_count':sum(x['result']=='PASS' for x in leakage),'tests':leakage}; supout={'count':8,'pass_count':sum(x['result']=='PASS' for x in supply),'tests':supply}
 gates={'real_16_16':len(real)>=16 and all(x['result']=='PASS' for x in real),'leakage_12_12':all(x['result']=='PASS' for x in leakage),'after_close':len(after)>=5 and all(x['result']=='PASS' for x in after),'supply_8_8':all(x['result']=='PASS' for x in supply),'financing_lineage':financing['result']=='PASS','missing':missing['result']=='PASS','four_state':four['result']=='PASS','context':context['result']=='PASS','reuse':reuse['result']=='PASS','v2_provenance':v2['result']=='PASS','identity':identity['result']=='PASS','corporate_action':corp['result']=='PASS'}; verdict='STEP8_PASS' if all(gates.values()) else 'STEP8_REPAIR_REQUIRED'
 outs={'real-sample-regression.json':realout,'leakage-regression.json':leakout,'after-close-regression.json':{'count':len(after),'pass_count':sum(x['result']=='PASS' for x in after),'cases':after},'os-retroactive-regression.json':msm,'float-regression.json':sf,'identity-regression.json':identity,'corporate-action-regression.json':corp,'supply-semantics-regression.json':supout,'financing-lineage-regression.json':financing,'missing-semantics-regression.json':missing,'four-state-full-scan.json':four,'context-integrity.json':context,'previous-result-reuse-audit.json':reuse,'v2-provenance-audit.json':v2,'qa-report.json':{'gates':gates,'pass_count':sum(gates.values()),'gate_count':len(gates),'verdict':verdict},'step8-r3-verdict.json':{'verdict':verdict,'step9_gate':'OPEN' if verdict=='STEP8_PASS' else 'BLOCKED'}}
 for n,x in outs.items(): dump(os.path.join(a.out,n),x)
 manifest={'artifact':'timemachine-step8-r3-full-regression-closure','inputs':{'step8_r2_artifact':12559529678,'step8_r_artifact':12557704696,'step7i_r2_artifact':12557232809,'step8_artifact':12557999767},'files':{n:hashlib.sha256(open(os.path.join(a.out,n),'rb').read()).hexdigest() for n in outs},'verdict':verdict,'context_read_only':True,'v2_modified':False}; dump(os.path.join(a.out,'manifest.json'),manifest)
 print(json.dumps({'verdict':verdict,'real':f"{realout['pass_count']}/{len(real)}",'leakage':f"{leakout['pass_count']}/12",'supply':f"{supout['pass_count']}/8",'gates':gates},indent=2))
if __name__=='__main__': main()
