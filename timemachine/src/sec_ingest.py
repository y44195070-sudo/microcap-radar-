from __future__ import annotations
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .pit import add_fact
from .time_utils import normalize_utc

ET=ZoneInfo("America/New_York")
SUPPORTED_PREFIXES=("8-K","6-K","10-Q","10-K","20-F","S-1","F-1","S-3","F-3","EFFECT","424B")

class SecParseError(ValueError): pass

def accepted_to_utc(raw: str) -> str:
    """EDGAR ACCEPTANCE-DATETIME is interpreted as US Eastern local wall time."""
    dt=datetime.strptime(raw,"%Y%m%d%H%M%S").replace(tzinfo=ET)
    return normalize_utc(dt.isoformat())

def parse_sec_header(text: str) -> dict:
    def one(pattern, required=True):
        m=re.search(pattern,text,re.M)
        if not m and required: raise SecParseError(pattern)
        return m.group(1).strip() if m else None
    return {
      "accession":one(r"ACCESSION NUMBER:\s*([^\r\n]+)"),
      "form":one(r"CONFORMED SUBMISSION TYPE:\s*([^\r\n]+)"),
      "accepted_raw":one(r"<ACCEPTANCE-DATETIME>(\d{14})"),
      "period":one(r"CONFORMED PERIOD OF REPORT:\s*([^\r\n]+)",False),
      "filed_date":one(r"FILED AS OF DATE:\s*([^\r\n]+)",False),
      "cik":one(r"CENTRAL INDEX KEY:\s*([^\r\n]+)"),
    }

def ingest_sec_header(conn, *, header_text: str, ticker: str, collected_at: str, source_url: str):
    meta=parse_sec_header(header_text)
    known_at=accepted_to_utc(meta["accepted_raw"])
    form=meta["form"]
    if not any(form.startswith(p) for p in SUPPORTED_PREFIXES):
        return None
    entity_id=f"CIK{int(meta['cik']):010d}"
    as_of=known_at
    value={"accession":meta["accession"],"form":form,"period":meta["period"],"filed_date":meta["filed_date"],"source_url":source_url}
    try:
        return add_fact(conn,entity_id=entity_id,ticker=ticker,fact_type="sec_filing",value=value,as_of=as_of,known_at=known_at,collected_at=collected_at,source="SEC_EDGAR",source_id=meta["accession"],status="KNOWN",published_at=known_at)
    except Exception as exc:
        # Exact duplicate is idempotent because pit_facts has a unique source/source_id/source_hash key.
        if "UNIQUE constraint failed" in str(exc): return "DUPLICATE_SKIPPED"
        raise
