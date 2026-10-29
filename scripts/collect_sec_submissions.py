#!/usr/bin/env python3
import argparse, hashlib, json, os, pathlib, time, urllib.error, urllib.request
from datetime import datetime, timezone

BASE = "https://data.sec.gov/submissions"
OUT = pathlib.Path("sec-submissions-artifact")
STATUS = {}
REQUESTS = 0
PAGES = 0


def now(): return datetime.now(timezone.utc).isoformat()
def req_json(url, ua, retries=3):
    global REQUESTS, PAGES
    last = None
    for i in range(retries):
        REQUESTS += 1
        r = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"})
        try:
            with urllib.request.urlopen(r, timeout=30) as x:
                code = x.status; STATUS[str(code)] = STATUS.get(str(code), 0) + 1
                data = json.loads(x.read().decode("utf-8")); PAGES += 1; return data
        except urllib.error.HTTPError as e:
            STATUS[str(e.code)] = STATUS.get(str(e.code), 0) + 1; last = e
            if e.code not in (429,500,502,503,504): break
        except Exception as e: last = e
        time.sleep(1.0 * (i + 1))
    raise RuntimeError(str(last))

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--issuers", required=True, help="JSON array/object with CIKs, or newline CIK list")
    a=ap.parse_args(); started=now()
    ua=os.getenv("SEC_USER_AGENT") or os.getenv("SEC_USER_AGENT_VAR")
    if not ua: raise SystemExit("SEC_USER_AGENT secret/variable is required")
    src=pathlib.Path(a.issuers); txt=src.read_text()
    try:
        obj=json.loads(txt)
        if isinstance(obj,list): vals=obj
        elif isinstance(obj,dict): vals=obj.get("issuers") or obj.get("ciks") or []
        else: vals=[]
    except json.JSONDecodeError: vals=[x.strip() for x in txt.splitlines() if x.strip()]
    issuers=[]
    for v in vals:
        if isinstance(v,dict): v=v.get("cik") or v.get("CIK")
        if v is not None: issuers.append(str(v).replace("CIK","").strip().lstrip("0").zfill(10))
    issuers=list(dict.fromkeys(issuers)); OUT.mkdir(parents=True,exist_ok=True); (OUT/"raw").mkdir(exist_ok=True)
    complete=[]; incomplete=[]; failed=[]
    for cik in issuers:
        try:
            root=req_json(f"{BASE}/CIK{cik}.json",ua); files=root.get("filings",{}).get("files",[])
            bundle={"cik":cik,"root":root,"history":[]}
            ok=True
            for ent in files:
                name=ent.get("name")
                if not name: continue
                try: bundle["history"].append({"name":name,"data":req_json(f"{BASE}/{name}",ua)})
                except Exception as e: bundle["history"].append({"name":name,"error":str(e)}); ok=False
                time.sleep(0.11)
            p=OUT/"raw"/f"CIK{cik}.json"; p.write_text(json.dumps(bundle,ensure_ascii=False,separators=(",",":")))
            (complete if ok else incomplete).append(cik)
        except Exception as e: failed.append({"cik":cik,"error":str(e)})
        time.sleep(0.11)
    summary={"issuers_requested":len(issuers),"issuers_complete_history":len(complete),"issuers_incomplete_history":len(incomplete),"issuers_failed":len(failed),"requests_total":REQUESTS,"pages_total":PAGES,"http_status_counts":STATUS,"started_at":started,"finished_at":now()}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
    if failed: (OUT/"failed.json").write_text(json.dumps(failed,indent=2))
    manifest=[]
    for p in sorted(OUT.rglob("*.json")):
        if p.name=="sha256-manifest.json": continue
        manifest.append({"path":str(p.relative_to(OUT)),"sha256":sha256(p),"bytes":p.stat().st_size})
    (OUT/"sha256-manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(summary))
if __name__=="__main__": main()
