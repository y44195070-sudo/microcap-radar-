#!/usr/bin/env python3
import argparse, hashlib, json, os, pathlib, time, urllib.error, urllib.request
from datetime import datetime, timezone

OUT = pathlib.Path("action-3b-b1-424b5-artifact")
STATUS = {}
REQUESTS = 0
DOCS = 0


def now(): return datetime.now(timezone.utc).isoformat()
def error_type(e): return type(e).__name__

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()

def fetch_bytes(url, ua, retries=3):
    global REQUESTS, DOCS
    last = None
    for i in range(retries):
        REQUESTS += 1
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                STATUS[str(r.status)] = STATUS.get(str(r.status), 0) + 1
                data = r.read(); DOCS += 1; return data
        except urllib.error.HTTPError as e:
            STATUS[str(e.code)] = STATUS.get(str(e.code), 0) + 1; last = e
            if e.code not in (429, 500, 502, 503, 504): break
        except Exception as e: last = e
        time.sleep(i + 1)
    raise RuntimeError(error_type(last) if last is not None else "UnknownError")

def load_accessions(path):
    obj = json.loads(pathlib.Path(path).read_text())
    vals = obj if isinstance(obj, list) else obj.get("accessions", obj.get("filings", []))
    out = []
    for v in vals:
        if not isinstance(v, dict): raise ValueError("Each accession entry must be an object")
        cik = str(v.get("cik", "")).replace("CIK", "").strip().lstrip("0")
        acc = str(v.get("accession") or v.get("accessionNumber") or "").strip()
        primary = str(v.get("primaryDocument") or v.get("primary_document") or "").strip()
        if not cik or not acc or not primary: raise ValueError("Each entry requires cik, accession, primaryDocument")
        out.append({"cik": cik, "accession": acc, "primaryDocument": primary})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--accessions", required=True); a = ap.parse_args()
    ua = (os.getenv("SEC_USER_AGENT") or os.getenv("SEC_USER_AGENT_VAR") or "").strip()
    if not ua: raise SystemExit("SEC_USER_AGENT secret/variable is required and must not be blank")
    rows = load_accessions(a.accessions); started = now()
    OUT.mkdir(parents=True, exist_ok=True); raw = OUT / "raw"; raw.mkdir(exist_ok=True)
    records, failed = [], []
    for x in rows:
        acc_nodash = x["accession"].replace("-", "")
        url = f'https://www.sec.gov/Archives/edgar/data/{x["cik"]}/{acc_nodash}/{x["primaryDocument"]}'
        collected_at = now()
        try:
            data = fetch_bytes(url, ua)
            name = f'{x["accession"]}_{pathlib.Path(x["primaryDocument"]).name}'
            p = raw / name; p.write_bytes(data)
            records.append({**x, "url": url, "collected_at": collected_at, "path": str(p.relative_to(OUT)), "sha256": sha256(p), "bytes": len(data)})
        except Exception as e:
            failed.append({"cik": x["cik"], "accession": x["accession"], "primaryDocument": x["primaryDocument"], "url": url, "collected_at": collected_at, "error": error_type(e)})
        time.sleep(0.11)
    manifest = {"documents": records}
    (OUT / "sha256-manifest.json").write_text(json.dumps(manifest, indent=2))
    summary = {"accessions_requested": len(rows), "documents_collected": len(records), "accessions_failed": len(failed), "requests_total": REQUESTS, "documents_total": DOCS, "http_status_counts": STATUS, "started_at": started, "finished_at": now()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    if failed: (OUT / "failed.json").write_text(json.dumps(failed, indent=2))
    print(json.dumps(summary))
    if failed or DOCS != len(rows): raise SystemExit(1)

if __name__ == "__main__": main()
