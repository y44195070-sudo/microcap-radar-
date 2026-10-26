#!/usr/bin/env python3
"""Repair V1 gate: exact STEP9 CIK adapter + exact approved-HEAD guard. No aliases/fallbacks."""
import argparse,json,os,pathlib,re,subprocess,sys
import step11_pre_full638_metadata_certification as core
SCHEMA_VERSION="STEP9_LIMITED_COVERAGE_CERTIFIED_V1"
CIK_PATH="source_evidence_reference.issuer_cik"
SOURCE="FROZEN_STEP9_SOURCE_EVIDENCE_REFERENCE"
HEAD_MISMATCH="STEP11_METADATA_ACQUISITION_POST_MERGE_HEAD_MISMATCH"
class RepairError(RuntimeError):pass

def canonical(v):
 if v is None:raise RepairError("FROZEN_CIK_NULL")
 s=str(v).strip()
 if not s:raise RepairError("FROZEN_CIK_EMPTY")
 if not re.fullmatch(r"(?:CIK)?\d{1,10}",s,re.I):raise RepairError("FROZEN_CIK_MALFORMED")
 return core.canonical_cik(s)
def normalize_row(r):
 ref=r.get("source_evidence_reference")
 if not isinstance(ref,dict):raise RepairError("FROZEN_SOURCE_EVIDENCE_REFERENCE_MISSING")
 if "issuer_cik" not in ref:raise RepairError("FROZEN_CIK_MISSING")
 nested=canonical(ref.get("issuer_cik"))
 if "issuer_cik" in r:
  direct=canonical(r.get("issuer_cik"))
  if direct!=nested:raise RepairError("FROZEN_CIK_SCHEMA_AMBIGUITY_CONFLICT")
 x=dict(r);x["issuer_cik"]=nested;x["normalized_issuer_cik_provenance"]={"schema_version":SCHEMA_VERSION,"frozen_path":CIK_PATH,"source":SOURCE,"forensic_occurrence_id":r.get("forensic_occurrence_id")};return x
def normalize(rows):
 if len(rows)!=638:raise RepairError("CANDIDATE_DENOMINATOR_MISMATCH")
 out=[normalize_row(r) for r in rows]
 if len({r.get("forensic_occurrence_id") for r in out})!=638:raise RepairError("DUPLICATE_FORENSIC_OCCURRENCE_ID")
 core.validate_input(out,638);return sorted(out,key=lambda r:r["forensic_occurrence_id"])
def head_guard(actual,approved):
 if not approved or not re.fullmatch(r"[0-9a-f]{40}",approved):raise RepairError("APPROVED_CERTIFICATION_HEAD_INVALID_OR_MISSING")
 if not actual or not re.fullmatch(r"[0-9a-f]{40}",actual):raise RepairError("ACTUAL_HEAD_INVALID_OR_MISSING")
 if actual!=approved:raise RepairError(HEAD_MISMATCH)
def load(p):
 x=json.load(open(p));return x if isinstance(x,list) else next((x[k] for k in ("rows","certified_allowlist","occurrences","candidates") if isinstance(x.get(k),list)),None)
def dump(p,x):pathlib.Path(p).write_text(json.dumps(x,sort_keys=True,separators=(",",":")))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['normalize-only','certification'],required=True);ap.add_argument('--input638',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True);rows=normalize(load(a.input638));dump(out/'normalized638.json',rows);plan=core.build_request_plan(rows);dump(out/'request_plan.json',plan);dump(out/'normalization_report.json',{"schema_version":SCHEMA_VERSION,"frozen_cik_path":CIK_PATH,"raw_rows":638,"normalized_rows":638,"normalized_issuer_cik_coverage":sum(bool(r['issuer_cik']) for r in rows),"unique_frozen_cik":len({r['issuer_cik'] for r in rows}),"normalized_issuer_cik_source":SOURCE,"sec_requests":core.COUNTERS['sec_requests']})
 if a.mode=='normalize-only':return 0
 head_guard(os.environ.get('GITHUB_SHA') or os.environ.get('ACTUAL_HEAD'),os.environ.get('APPROVED_CERTIFICATION_HEAD'))
 if os.environ.get('STEP11_METADATA_CERTIFICATION_ENABLE')!='YES':raise RepairError('CERTIFICATION_NOT_EXPLICITLY_ENABLED')
 cmd=[sys.executable,str(pathlib.Path(__file__).with_name('step11_structural_metadata_acquisition_execution.py')),'--mode','certification','--input638',str(out/'normalized638.json'),'--out',str(out/'execution')];return subprocess.call(cmd)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print(json.dumps({'error':str(e)},sort_keys=True),file=sys.stderr);raise
