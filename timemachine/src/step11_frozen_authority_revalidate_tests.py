#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, importlib.util, json, pathlib, shutil, sys, tempfile, zipfile
SRC=pathlib.Path(__file__).with_name('step11_frozen_authority_revalidate.py')
spec=importlib.util.spec_from_file_location('v',SRC); v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
def expect_fail(fn):
 try: fn()
 except v.VerificationError: return
 raise AssertionError('EXPECTED_FAIL')
def mutate_json_zip(root,aid,member,mut):
 p=root/f'{aid}.zip'; tmp=p.with_suffix('.tmp')
 with zipfile.ZipFile(p) as zin, zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as zout:
  for n in zin.namelist():
   b=zin.read(n)
   if n==member:
    x=json.loads(b); mut(x); b=(json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
   zout.writestr(n,b)
 tmp.replace(p); name,d,stage=v.ARTIFACTS[aid]; v.ARTIFACTS[aid]=(name,hashlib.sha256(p.read_bytes()).hexdigest(),stage)
def main(root):
 root=pathlib.Path(root); original=copy.deepcopy(v.ARTIFACTS); results={}
 v.verify(root); results['valid_historical_payload_without_embedded_run_id_plus_github_provenance']='PASS'
 def case(name,mutator):
  v.ARTIFACTS.clear(); v.ARTIFACTS.update(copy.deepcopy(original))
  with tempfile.TemporaryDirectory() as td:
   r=pathlib.Path(td); [shutil.copy2(p,r/p.name) for p in root.iterdir() if p.is_file()]
   mutator(r); expect_fail(lambda:v.verify(r)); results[name]='PASS'
 case('wrong_github_run_id',lambda r:(lambda p,x:(x['workflow_run'].__setitem__('id',1),p.write_text(json.dumps(x))))(r/'artifact-12603520492.json',json.loads((r/'artifact-12603520492.json').read_text())))
 case('wrong_artifact_id',lambda r:(lambda p,x:(x.__setitem__('id',1),p.write_text(json.dumps(x))))(r/'artifact-12603520492.json',json.loads((r/'artifact-12603520492.json').read_text())))
 case('tampered_payload_digest',lambda r:(r/'12603520492.zip').write_bytes((r/'12603520492.zip').read_bytes()+b'x'))
 case('wrong_step9_decision',lambda r:mutate_json_zip(r,12603520492,'checkpoint.json',lambda x:x.__setitem__('decision','BAD')))
 case('wrong_638_4388_semantics',lambda r:mutate_json_zip(r,12603520492,'checkpoint.json',lambda x:x.__setitem__('certified',637)))
 case('step10_fallback_semantics_changed',lambda r:mutate_json_zip(r,12603356621,'certified_only_guard_contract.json',lambda x:x.__setitem__('fallback_allowed',True)))
 case('step11_selection_binding_mismatch',lambda r:mutate_json_zip(r,12637078890,'final_decision.json',lambda x:x.__setitem__('selection_hash','BAD')))
 case('artifact_checkpoint_swapped',lambda r:(r/'12603520492.zip').write_bytes((r/'12603725128.zip').read_bytes()))
 text=SRC.read_text(); assert 'if value not in text' not in text and 'GITHUB_ACTIONS_PROVENANCE' in text and 'PAYLOAD_INTEGRITY_PLUS_GITHUB_ARTIFACT_PROVENANCE' in text; results['hardcoded_expected_actual_bypass_rejected']='PASS'
 v.ARTIFACTS.clear(); v.ARTIFACTS.update(original)
 assert len(results)==10 and all(x=='PASS' for x in results.values())
 print(json.dumps({'PASS':True,'tests':results},sort_keys=True)); return 0
if __name__=='__main__':
 if len(sys.argv)!=2: raise SystemExit('usage: tests.py ARTIFACT_DIR')
 raise SystemExit(main(sys.argv[1]))
