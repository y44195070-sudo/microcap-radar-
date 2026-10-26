#!/usr/bin/env python3
"""Independent verifier for frozen STEP9/10/11 GitHub Actions artifacts.
Consumes local ZIP bytes downloaded from exact GitHub artifact IDs. No SEC I/O.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, zipfile

class VerificationError(RuntimeError): pass
ARTIFACTS={
 12603520492:("step9_artifact","3ec6a1f4ec88ff284eade8d7730b301ea65d2d5a932feb11a0f76c0592c7c19c"),
 12603725128:("step9_checkpoint","a77f89137bfe5c299e46e39864e37826cc03ce84c3cbbede8c681bf538e31238"),
 12603356621:("step10_artifact","b9a5a4d40bfc318288a15337fd74c47dcff93de619d6aa281ea9de6001ebf1de"),
 12603737037:("step10_checkpoint","914587ecbbe5bcb579aff464b11c8fec0469f7400ee8eddc3d757f9ab30e181f"),
 12637518208:("step11_forensic","2812577a8bc205988b7d1d4b40c98ca62a4e182de79b257810e5c51c34d56ea8"),
 12637118813:("step11_checkpoint","cb0312d5b15cfb6c244361371f4d378ae14062b30d495a87cc46519af1ba0e8a"),
 12637078890:("step11_certification","a382e1bf23b44faddc38f1b981d51c451d9b9d2a8a884d60af744774d8c936ab"),
}
BINDINGS={
 "step9":{"head":"03457bba70c0297b425ecd68e5e9c568df038f1d","run":"40204385931","job":"121202088334"},
 "step10":{"head":"d07e4cbae552ffed2391904e76bcbae0a5584397","run":"40204853366","job":"121203517495"},
 "step11":{"head":"97a053c93034278df86b9a3983ebf843895a7d2b","run":"40295222293","job":"121479531795","attempt":"1"},
}
SEMANTIC_TOKENS={
 "step9":["STEP9_LIMITED_COVERAGE_CERTIFIED","5026","638","4388"],
 "step10":["STEP10_CERTIFIED_ONLY_CONSUMPTION_GUARD_CERTIFIED","ALLOW","DENY","FORBIDDEN"],
 "step11":["32","ec9fc60f59a72769bd372704379667c76f1e71021e4197ac1af085750d3ee549"],
}
def sha(p:pathlib.Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
 return h.hexdigest()
def inspect(p:pathlib.Path,expected:str)->dict:
 actual=sha(p)
 if actual!=expected: raise VerificationError("DIGEST_MISMATCH")
 with zipfile.ZipFile(p) as z:
  names=z.namelist()
  if len(names)!=len(set(names)): raise VerificationError("DUPLICATE_PATH")
  if z.testzip(): raise VerificationError("ZIP_INTEGRITY")
  text=[]
  for n in names:
   if n.endswith((".json",".txt",".md",".csv")):
    try:text.append(z.read(n).decode("utf-8"))
    except UnicodeDecodeError:pass
 return {"sha256":actual,"size":p.stat().st_size,"files":sorted(names),"text":"\n".join(text)}
def verify(root:pathlib.Path)->dict:
 reports={}
 for aid,(name,digest) in ARTIFACTS.items():
  p=root/f"{aid}.zip"
  if not p.exists(): raise VerificationError(f"MISSING_ARTIFACT:{aid}")
  reports[name]=inspect(p,digest)
 combined={k:"" for k in BINDINGS}
 for name,r in reports.items():
  prefix="step9" if name.startswith("step9") else "step10" if name.startswith("step10") else "step11"
  combined[prefix]+=r.pop("text")+"\n"
 for k,b in BINDINGS.items():
  text=combined[k]
  for value in b.values():
   if value not in text: raise VerificationError(f"BINDING_MISSING:{k}:{value}")
  for token in SEMANTIC_TOKENS[k]:
   if token not in text: raise VerificationError(f"SEMANTIC_TOKEN_MISSING:{k}:{token}")
 return {"verified":True,"artifacts":reports,"bindings":BINDINGS,"semantics":SEMANTIC_TOKENS,"sec_requests":0}
def main()->int:
 ap=argparse.ArgumentParser(); ap.add_argument("--artifact-dir",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
 report=verify(pathlib.Path(a.artifact_dir)); pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8"); print("FROZEN_AUTHORITY_REVALIDATION_PASS"); return 0
if __name__=="__main__": raise SystemExit(main())
