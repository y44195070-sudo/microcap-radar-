#!/usr/bin/env python3
import argparse,json,os,zipfile
EXPECTED='2bff74f22b1e6d52851eb69d1d2607d20f6954b0fa3e8d62c1798a9aa6e862ef'
def main():
 p=argparse.ArgumentParser(); p.add_argument('--r2',required=True); p.add_argument('--out',required=True); a=p.parse_args()
 z=zipfile.ZipFile(a.r2); m=json.loads(z.read('manifest.json')); path=os.path.join(a.out,'context-integrity.json'); c=json.load(open(path)); exp=m.get('daily_canonical_hashes',{}); got=c.get('per_day_hashes',{}); matches={d:got.get(d)==h for d,h in exp.items()}; c['frozen_expected_per_day_hashes']=exp; c['per_day_hash_matches']=matches; c['hash_matches_count']=sum(matches.values()); c['frozen_manifest_hash']=m.get('manifest_hash'); c['manifest_hash_match']=m.get('manifest_hash')==EXPECTED; c['repaired_fields']=m.get('status_changes'); c['repaired_context_records']=m.get('repaired_context_records'); c['result']='PASS' if len(exp)==20 and sum(matches.values())==20 and m.get('manifest_hash')==EXPECTED and c.get('record_count')==168759 else 'FAIL'; json.dump(c,open(path,'w'),indent=2,sort_keys=True)
 qpath=os.path.join(a.out,'qa-report.json'); q=json.load(open(qpath)); q['context_integrity']=c['result']; json.dump(q,open(qpath,'w'),indent=2,sort_keys=True)
if __name__=='__main__': main()
