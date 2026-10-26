#!/usr/bin/env python3
"""STEP11 Fixture V5 semantic security scanner.
Detects serialized credential material while avoiding scanner-source/test-vector false positives.
"""
import argparse, json, pathlib, re, sys, tempfile
PATTERNS=[
 ("AUTH_BEARER",re.compile(r"Authorization\s*:\s*Bearer\s+([A-Za-z0-9._-]{10,})",re.I)),
 ("BEARER_TOKEN",re.compile(r"\bBearer\s+([A-Za-z0-9._-]{10,})",re.I)),
 ("CREDENTIAL_QUERY",re.compile(r"[?&](apiKey|token|key)=([^&\s'\"}]+)",re.I)),
 ("GITHUB_TOKEN",re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
]
SAFE_VALUE_MARKERS=("${{","$GH_TOKEN","${GH_TOKEN","os.environ","getenv(")
SOURCE_SUFFIXES={".py",".yml",".yaml",".sh",".md",".txt"}
TEST_CONTAINER_RE=re.compile(r"\b(?:bads|invalid|safe_lines|safe_cases|unsafe_cases)\s*=\s*\[")
def redact(s): return "<redacted>" if len(s)<=8 else s[:3]+"…"+s[-3:]
def source_like(path):
 p=pathlib.Path(path)
 return p.suffix.lower() in SOURCE_SUFFIXES and "/tmp/expansion-cert/" not in str(p)
def low_entropy_test_query(m):
 try: value=m.group(2)
 except IndexError: return False
 return len(value)<=8 and re.fullmatch(r"[A-Za-z0-9_.-]+",value) is not None
def safe_source_or_test_line(path,line,pid,m):
 if any(x in line for x in ("re.compile(","PATTERNS")): return "SAFE_SCANNER_SOURCE_LITERAL"
 if source_like(path) and TEST_CONTAINER_RE.search(line):
  if "SYNTHETIC_" in line or "REDACTED" in line or "NONE" in line:
   return "SAFE_LITERAL_TEST_PATTERN"
  if pid=="CREDENTIAL_QUERY" and low_entropy_test_query(m):
   return "SAFE_LITERAL_TEST_PATTERN"
 if any(x in line for x in ("synthetic_","SAFE_","bads=[","bads = [")):
  return "SAFE_LITERAL_TEST_PATTERN" if "bads" in line else "SAFE_SCANNER_SOURCE_LITERAL"
 return None
def classify(path,line,pid,m):
 raw=m.group(0)
 safe=safe_source_or_test_line(path,line,pid,m)
 if safe: return safe
 if "secrets." in raw or "secrets." in line: return "SAFE_GITHUB_EXPRESSION"
 if any(x in raw or x in line for x in SAFE_VALUE_MARKERS): return "SAFE_ENV_REFERENCE"
 return "CREDENTIAL_BEARING_URL" if pid=="CREDENTIAL_QUERY" else "REAL_SECRET"
def scan_file(path):
 p=pathlib.Path(path); out=[]
 try: lines=p.read_text(errors="replace").splitlines()
 except Exception: return out
 for n,line in enumerate(lines,1):
  for pid,pat in PATTERNS:
   for m in pat.finditer(line): out.append({"pattern_id":pid,"file":str(p),"line":n,"redacted_match":redact(m.group(0)),"classification":classify(p,line,pid,m)})
 return out
def run_regression_v3():
 td=pathlib.Path(tempfile.mkdtemp())
 safe=[
  ("safe.py","api_key = None"),("safe.py","access_token = None"),("safe.yml","token: ${{ secrets.SOMETHING }}"),("safe.yml","token: ${GH_TOKEN}"),("safe.txt","REDACTED"),("safe.txt","NONE"),("safe.txt","PLACEHOLDER"),("safe.py","PATTERNS=[re.compile(r'[?&]api_key=')]"),("safe.py","PATTERNS=[re.compile(r'Authorization: Bearer')]"),("safe.py","synthetic_test_vector = 'token'"),("safe.yml","bads=['https://x.test/?apiKey=' + 'X'*24]"),("safe.yml","invalid=['a'*63,a+'?token=x']"),("safe.py","SAFE_CASE='?api_key='"),("safe.yml","token: REDACTED"),("safe.yml","api_key: NONE")]
 for i,(name,text) in enumerate(safe):
  p=td/f"{i}-{name}";p.write_text(text+"\n")
  if any(f["classification"] in {"REAL_SECRET","CREDENTIAL_BEARING_URL","AUTHORIZATION_HEADER_EXPOSURE"} for f in scan_file(p)): raise AssertionError(("safe regression failed",i))
 v="X"*24
 unsafe=["https://x.test/?apiKey="+v,"https://x.test/?token="+v,"Authorization: Bearer "+v,"https://x.test/?apiKey="+v+"&x=1","https://data.sec.gov/submissions/x.json?key="+v,'{"url":"https://x.test/?token='+v+'"}','url: "https://x.test/?token='+v+'"',"https://x.test/?x=1&token="+v,"https://x.test/?token="+("X%5F"*10),"https://x.test/?ToKeN="+v,"Bearer "+v,"gh"+"p_"+("X"*30),"https://x.test/?key="+v,"https://x.test/?token="+("Y"*24)]
 for i,text in enumerate(unsafe):
  p=td/f"unsafe-{i}.json";p.write_text(text+"\n")
  if not any(f["classification"] in {"REAL_SECRET","CREDENTIAL_BEARING_URL","AUTHORIZATION_HEADER_EXPOSURE"} for f in scan_file(p)): raise AssertionError(("unsafe regression failed",i))
 return {"safe_cases":len(safe),"safe_pass":len(safe),"unsafe_cases":len(unsafe),"unsafe_fail_closed":len(unsafe),"PASS":True}
def main():
 regression=run_regression_v3()
 ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ap.add_argument("paths",nargs="+"); a=ap.parse_args(); files=[]
 for raw in a.paths:
  p=pathlib.Path(raw)
  if p.is_dir(): files += [x for x in p.rglob("*") if x.is_file()]
  elif p.is_file(): files.append(p)
 files=sorted(set(files),key=lambda x:str(x)); findings=[]
 for p in files: findings += scan_file(p)
 prohibited=[f for f in findings if f["classification"] in {"REAL_SECRET","CREDENTIAL_BEARING_URL","AUTHORIZATION_HEADER_EXPOSURE"}]
 report={"version":"STEP11_FIXTURE_SECURITY_SCAN_V5","files_scanned":len(files),"patterns_evaluated":len(PATTERNS),"matches_found":len(findings),"false_positives":sum(f["classification"].startswith("SAFE_") for f in findings),"confirmed_secrets":sum(f["classification"]=="REAL_SECRET" for f in findings),"credential_bearing_urls":sum(f["classification"]=="CREDENTIAL_BEARING_URL" for f in findings),"authorization_headers":sum(f["pattern_id"]=="AUTH_BEARER" and f in prohibited for f in findings),"api_keys":sum(f["pattern_id"]=="CREDENTIAL_QUERY" and f in prohibited for f in findings),"tokens":sum(f["pattern_id"] in {"BEARER_TOKEN","GITHUB_TOKEN"} and f in prohibited for f in findings),"findings":findings,"security_regression_v3":regression,"PASS":not prohibited}
 pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n"); print(json.dumps({k:report[k] for k in ("files_scanned","matches_found","false_positives","confirmed_secrets","credential_bearing_urls","authorization_headers","PASS")},sort_keys=True))
 if prohibited: sys.exit(1)
if __name__=="__main__": main()
