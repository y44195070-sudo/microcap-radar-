#!/usr/bin/env python3
"""STEP11 Fixture V5 semantic security scanner.
Detects serialized credential material while avoiding scanner-source/self-match false positives.
"""
import argparse, json, pathlib, re, sys

PATTERNS = [
    ("AUTH_BEARER", re.compile(r"Authorization\s*:\s*Bearer\s+([A-Za-z0-9._-]{10,})", re.I)),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+([A-Za-z0-9._-]{10,})", re.I)),
    ("CREDENTIAL_QUERY", re.compile(r"[?&](apiKey|token|key)=([^&\s'\"}]+)", re.I)),
    ("GITHUB_TOKEN", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
]
SAFE_VALUE_MARKERS = ("${{", "$GH_TOKEN", "${GH_TOKEN", "os.environ", "getenv(")
SOURCE_SUFFIXES = {".py", ".yml", ".yaml", ".md", ".txt"}

def redact(s):
    if len(s) <= 8: return "<redacted>"
    return s[:3] + "…" + s[-3:]

def scanner_source_line(line):
    # Regex definitions / examples are code describing detectors, not serialized credentials.
    return any(x in line for x in ("re.compile(", "PATTERNS", "synthetic_", "SAFE_"))

def classify(path, line, pattern_id, match):
    raw = match.group(0)
    if scanner_source_line(line): return "SAFE_SCANNER_SOURCE_LITERAL"
    if any(m in raw or m in line for m in SAFE_VALUE_MARKERS): return "SAFE_ENV_REFERENCE"
    if "secrets." in raw or "secrets." in line: return "SAFE_GITHUB_EXPRESSION"
    if pattern_id == "CREDENTIAL_QUERY": return "CREDENTIAL_BEARING_URL"
    return "REAL_SECRET"

def scan_file(path):
    p=pathlib.Path(path); findings=[]
    try: text=p.read_text(errors="replace")
    except Exception: return findings
    for lineno,line in enumerate(text.splitlines(),1):
        for pid,pat in PATTERNS:
            for m in pat.finditer(line):
                cls=classify(str(p),line,pid,m)
                findings.append({"pattern_id":pid,"file":str(p),"line":lineno,"redacted_match":redact(m.group(0)),"classification":cls})
    return findings

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ap.add_argument("paths",nargs="+"); a=ap.parse_args()
    files=[]
    for raw in a.paths:
        p=pathlib.Path(raw)
        if p.is_dir(): files += [x for x in p.rglob("*") if x.is_file()]
        elif p.is_file(): files.append(p)
    findings=[]
    for p in sorted(set(files), key=lambda x:str(x)): findings += scan_file(p)
    prohibited=[f for f in findings if f["classification"] in {"REAL_SECRET","CREDENTIAL_BEARING_URL","AUTHORIZATION_HEADER_EXPOSURE"}]
    report={"version":"STEP11_FIXTURE_SECURITY_SCAN_V5","files_scanned":len(set(map(str,files))),"patterns_evaluated":len(PATTERNS),"matches_found":len(findings),"false_positives":sum(f["classification"].startswith("SAFE_") for f in findings),"confirmed_secrets":sum(f["classification"]=="REAL_SECRET" for f in findings),"credential_bearing_urls":sum(f["classification"]=="CREDENTIAL_BEARING_URL" for f in findings),"authorization_headers":sum(f["pattern_id"]=="AUTH_BEARER" and f in prohibited for f in findings),"api_keys":sum(f["pattern_id"]=="CREDENTIAL_QUERY" and f in prohibited for f in findings),"tokens":sum(f["pattern_id"] in {"BEARER_TOKEN","GITHUB_TOKEN"} and f in prohibited for f in findings),"findings":findings,"PASS":not prohibited}
    pathlib.Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("files_scanned","matches_found","false_positives","confirmed_secrets","credential_bearing_urls","authorization_headers","PASS")},sort_keys=True))
    if prohibited: sys.exit(1)
if __name__=="__main__": main()
