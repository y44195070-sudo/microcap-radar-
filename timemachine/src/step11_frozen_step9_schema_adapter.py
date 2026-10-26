#!/usr/bin/env python3
"""Explicit, zero-network adapter for immutable STEP9 certified allowlist schema.

Authority path is fixed to source_evidence_reference.issuer_cik. This module never
performs identity lookup and never mutates the immutable source artifact.
"""
from __future__ import annotations
import argparse, json, pathlib, re

SCHEMA_VERSION = "STEP9_CERTIFIED_ALLOWLIST_V1_NESTED_SOURCE_EVIDENCE_CIK"
FROZEN_CIK_PATH = "source_evidence_reference.issuer_cik"
PROVENANCE = "FROZEN_STEP9_SOURCE_EVIDENCE_REFERENCE"
CIK_RE = re.compile(r"^[0-9]{1,10}$")

class FrozenSchemaError(RuntimeError):
    pass

def canonical_cik(value):
    if value is None:
        raise FrozenSchemaError("FROZEN_CIK_NULL")
    s = str(value).strip()
    if not s:
        raise FrozenSchemaError("FROZEN_CIK_EMPTY")
    if not CIK_RE.fullmatch(s):
        raise FrozenSchemaError("FROZEN_CIK_MALFORMED")
    return s.zfill(10)

def normalize_row(row):
    if not isinstance(row, dict):
        raise FrozenSchemaError("FROZEN_ROW_NOT_OBJECT")
    src = row.get("source_evidence_reference")
    if not isinstance(src, dict):
        raise FrozenSchemaError("FROZEN_SOURCE_EVIDENCE_REFERENCE_MISSING")
    if "issuer_cik" not in src:
        raise FrozenSchemaError("FROZEN_CIK_MISSING")
    nested = canonical_cik(src.get("issuer_cik"))
    if "issuer_cik" in row:
        direct = canonical_cik(row.get("issuer_cik"))
        if direct != nested:
            raise FrozenSchemaError("FROZEN_CIK_SCHEMA_AMBIGUITY")
    out = dict(row)
    out["issuer_cik"] = nested
    out["normalized_issuer_cik_provenance"] = {
        "schema_version": SCHEMA_VERSION,
        "source_path": FROZEN_CIK_PATH,
        "source_authority": PROVENANCE,
    }
    return out

def normalize_rows(rows, expected=638):
    if not isinstance(rows, list):
        raise FrozenSchemaError("FROZEN_ALLOWLIST_NOT_LIST")
    if len(rows) != expected:
        raise FrozenSchemaError("FROZEN_ALLOWLIST_DENOMINATOR_MISMATCH")
    ids = [r.get("forensic_occurrence_id") for r in rows if isinstance(r, dict)]
    if len(ids) != expected or any(not x for x in ids) or len(set(ids)) != expected:
        raise FrozenSchemaError("FROZEN_OCCURRENCE_ID_INVALID")
    out = [normalize_row(r) for r in rows]
    if len(out) != expected:
        raise FrozenSchemaError("NORMALIZED_DENOMINATOR_MISMATCH")
    return sorted(out, key=lambda r: r["forensic_occurrence_id"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    raw = json.loads(pathlib.Path(a.input).read_text())
    rows = raw if isinstance(raw, list) else raw.get("rows")
    normalized = normalize_rows(rows, 638)
    unique = len({r["issuer_cik"] for r in normalized})
    pathlib.Path(a.out).write_text(json.dumps(normalized, sort_keys=True, separators=(",", ":")))
    report = {
        "decision": "REAL_FROZEN_ALLOWLIST_TO_LIVE_RUNNER_SCHEMA_COMPATIBILITY_PASS",
        "schema_version": SCHEMA_VERSION,
        "frozen_cik_path": FROZEN_CIK_PATH,
        "normalized_issuer_cik_source": PROVENANCE,
        "raw_rows": len(rows),
        "normalized_rows": len(normalized),
        "raw_frozen_cik_coverage": sum(isinstance(r.get("source_evidence_reference"), dict) and bool(r["source_evidence_reference"].get("issuer_cik")) for r in rows),
        "normalized_issuer_cik_coverage": sum(bool(r.get("issuer_cik")) for r in normalized),
        "unique_frozen_cik": unique,
        "sec_requests": 0,
        "provider_requests": 0,
        "current_identifier_requests": 0,
        "residual4388_requests": 0,
    }
    if report["raw_frozen_cik_coverage"] != 638 or report["normalized_issuer_cik_coverage"] != 638 or unique != 239:
        raise FrozenSchemaError("REAL_FROZEN_SCHEMA_COMPATIBILITY_FAILED")
    pathlib.Path(a.report).write_text(json.dumps(report, sort_keys=True, indent=2))
    print(report["decision"])

if __name__ == "__main__":
    main()
