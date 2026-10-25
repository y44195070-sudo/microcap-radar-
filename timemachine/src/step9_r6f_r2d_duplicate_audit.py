#!/usr/bin/env python3
import argparse,hashlib,json,os,zipfile

def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r6c',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 assert sha(open(a.r6c,'rb').read())=='26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'
 z=zipfile.ZipFile(a.r6c);dg=json.loads(z.read('duplicate_1300_group_analysis.json'));rr=json.loads(z.read('prediction_identity_resolution_records.json'))
 groups=[g for g in dg['groups'] if g['classification']=='UNRESOLVED_IDENTITY_EVIDENCE'];assert len(groups)==404
 cov=json.load(open(os.path.join(a.out,'occurrence_source_coverage.json')));state={(x['trading_date'],x['ticker_as_of_date']):x['search_state'] for x in cov}
 by={}
 for r in rr:by.setdefault(r['existing_prediction_id'],[]).append(r)
 complete=partial=blocked=evidence=0;missing=0
 for g in groups:
  rows=by.get(g['existing_prediction_id'],[]);vals=[]
  for r in rows:
   k=(r.get('trading_date'),r.get('ticker_as_of_date'))
   if k not in state:missing+=1;continue
   vals.append(state[k]=='SEARCH_COMPLETE_EVIDENCE_FOUND')
  if vals and all(vals):complete+=1;evidence+=1
  elif any(vals):partial+=1
  else:blocked+=1
 assert missing==0 and complete+partial+blocked==404
 audit={'total':404,'Legacy_complete_groups':complete,'Newly_complete_groups':0,'Final_complete_groups':complete,'Partially_complete_groups':partial,'Still_blocked_groups':blocked,'Groups_with_promotion_grade_raw_evidence':evidence,'mapping_missing':missing,'identity_mutation':0,'source_artifact_id':12593164641,'source_artifact_sha256':'26dbf2d98256fc837f92a5520431b8f1e05ca0e4fe74dbfbddce98f9b7e96b5e'}
 open(os.path.join(a.out,'duplicate_group_audit.json'),'w').write(json.dumps(audit,indent=2,sort_keys=True)+'\n');print(audit)
if __name__=='__main__':main()
