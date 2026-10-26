#!/usr/bin/env python3
"""Defense-in-depth exact-HEAD guard for STEP11 live metadata certification."""
from __future__ import annotations
import os, re, runpy

FAILURE = "STEP11_METADATA_ACQUISITION_POST_MERGE_HEAD_MISMATCH"

def verify_head(actual: str | None, approved: str | None) -> None:
    if not approved or not re.fullmatch(r"[0-9a-f]{40}", approved):
        raise SystemExit(FAILURE)
    if not actual or not re.fullmatch(r"[0-9a-f]{40}", actual):
        raise SystemExit(FAILURE)
    if actual != approved:
        raise SystemExit(FAILURE)

def main() -> None:
    verify_head(os.environ.get("STEP11_ACTUAL_HEAD"), os.environ.get("STEP11_APPROVED_CERTIFICATION_HEAD"))
    runpy.run_module("step11_structural_metadata_acquisition_execution", run_name="__main__")

if __name__ == "__main__":
    main()
