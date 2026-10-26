#!/usr/bin/env python3
"""STEP11 Fixture V5 semantic security scanner.
Detects serialized credential material while avoiding scanner-source/test-vector false positives.
"""
import argparse, json, pathlib, re, sys
PATTERNS=[
 ("AUTH_BEARER",re.compile(r"Authorization\s*:\s*Bearer\s+([A-Za-z0-9._-]{10,})",re.I)),
 ("BEARER_TOKEN",re.compile(r"\bBearer\s+([A-Za-z0-9._-]{10,})",re.I)),
 ("CREDENTIAL_QUERY",re.compile(r"[?&](apiKey|token|key)=([^&\s'\"}]+)",re.I)),
 ("GITHUB_TOKEN",re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
]
SAFE_VALUE_MARKERS=("${{","$GH_TOKEN","${GH_TOKEN","os.environ","getenv(")
def redact(s): return "<redacted>" if len(s)<=8 else s[:3]+"…"+s[-3:]
def safe_source_or_test_line(line):
 return any(x in line for x in ("re.compile(","PATTERNS","synthetic_","SAFE_","bads=[","bads = [","invalid=[","invalid = ["))
def classify(line,pid,m):
 raw=m.group(0)
 if safe_source_or_test_line(line): return "SAFE_LITERAL_TEST_PATTERN" if any(x in line for x in ("bads", "invalid")) else "SAFE_SCANNER_SOURCE_LITERAL"
 if "secrets." in raw or "secrets." in line: return "SAFE_GITHUB_EXPRESSION"
 if any(x in raw or x in line for x in SAFE_VALUE_MARKERS): return "SAFE_ENV_REFERENCE"
 return "CREDENTIAL_BEARING_URL" if pid=="CREDENTIAL_QUERY" else "REAL_SECRET"
def scan_file(path):
 p=pathlib.Path(path); out=[]
 try: lines=p.read_text(errors="replace").splitlines()
 except Exception: return out
 for n,line in enumerate(lines,1):
  for pid,pat in PATTERNS:
   for m in pat.finditer(line): out.append({"pattern_id":pid,"file":str(p),"line":n,"redacted_match":redact(m.group(0)),"classification":classify(line,pid,m)})
 return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ap.add_argument("paths",nargs="+"); a=ap.parse_args(); files=[]
 for raw in a.paths:
  p=pathlib.Path(raw)
  if p.is_dir(): files += [x for x in p.rglob("*") if x.is_file()]
  elif p.is_file(): files.append(p)
 files=sorted(set(files),key=lambda x:str(x)); findings=[]
 for p in files: findings += scan_file(p)
 prohibited=[f for f in findings if f["classification"] in {"REAL_SECRET","CREDENTIAL_BEARING_URL","AUTHORIZATION_HEADER_EXPOSURE"}]
 report={"version":"STEP11_FIXTURE_SECURITY_SCAN_V5","files_scanned":len(files),"patterns_evaluated":len(PATTERNS),"matches_found":len(findings),"false_positives":sum(f["classification"].startswith("SAFE_") for f in findings),"confirmed_secrets":sum(f["classification"]=="REAL_SECRET" for f in findings),"credential_bearing_urls":sum(f["classification"]=="CREDENTIAL_BEARING_URL" for f in findings),"authorization_headers":sum(f["pattern_id"]=="AUTH_BEARER" and f in prohibited for f in findings),"api_keys":sum(f["pattern_id"]=="CREDENTIAL_QUERY" and f in prohibited for f in findings),"tokens":sum(f["pattern_id"] in {"BEARER_TOKEN","GITHUB_TOKEN"} and f in prohibited for f in findings),"findings":findings,"PASS":not prohibited}
 pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n"); print(json.dumps({k:report[k] for k in ("files_scanned","matches_found","false_positives","confirmed_secrets","credential_bearing_urls","authorization_headers","PASS")},sort_keys=True))
 if prohibited: sys.exit(1)
if __name__=="__main__": main()
