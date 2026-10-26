#!/usr/bin/env python3
"""STEP11 Retry V3 repair wrapper.
Fail-closed acquisition eligibility and SEC request-contract repair.
Live use remains exact-head/workflow gated; offline validation performs zero network.
"""
from __future__ import annotations
import argparse, collections, json, os, pathlib, sys, urllib.error, urllib.request
import step11_pre_full638_metadata_certification as core
import step11_structural_metadata_acquisition_execution as ex

CORE_VALIDATED = "CORE_METADATA_REPLAY_VALIDATED"
INCOMPLETE = "STEP11_PRE_FULL638_STRUCTURAL_METADATA_ACQUISITION_INCOMPLETE"
UA_DEFAULT = "MicrocapRadar historical-expansion-certification/1.0 contact: repository-owner"

class RepairedMetadataClient(core.MetadataClient):
    """Metadata-only client matching the previously successful Expansion request contract."""
    def build_request(self, url: str):
        core.classify_endpoint(url)
        ua = self.user_agent or UA_DEFAULT
        return urllib.request.Request(url, method="GET", headers={
            "User-Agent": ua,
            "Accept-Encoding": "identity",
            "Accept": "application/json,text/plain,*/*",
        })

    def fetch(self, url: str, cik: str) -> bytes:
        endpoint_class = core.classify_endpoint(url)
        if not self.policy.enabled:
            raise core.NetworkDisabled("NETWORK_DISABLED")
        if self.ordinal >= self.policy.max_requests:
            raise core.GateError("REQUEST_BUDGET_EXCEEDED")
        req = self.build_request(url)
        self.ordinal += 1
        core.COUNTERS["network_requests"] += 1
        core.COUNTERS["sec_requests"] += 1
        try:
            with urllib.request.urlopen(req, timeout=self.policy.timeout_seconds) as r:
                body = r.read(); status = getattr(r, "status", 200)
        except urllib.error.HTTPError as e:
            self.audit.append({"request_ordinal":self.ordinal,"endpoint_class":endpoint_class,"issuer_cik":cik,"response_state":f"HTTP_{e.code}"})
            raise
        except Exception as e:
            self.audit.append({"request_ordinal":self.ordinal,"endpoint_class":endpoint_class,"issuer_cik":cik,"response_state":"NETWORK_ERROR","error_type":type(e).__name__})
            raise
        self.audit.append({"request_ordinal":self.ordinal,"endpoint_class":endpoint_class,"issuer_cik":cik,"response_state":f"HTTP_{status}"})
        return body

def eligibility(rows, state, derived, raw_manifest, ledger):
    states = state.get("rows", [])
    complete_ciks = sum(bool(s.get("acquisition_complete")) for s in states)
    incomplete_ciks = len(states) - complete_ciks
    incomplete_candidates = sum(x.get("terminal_state") == "SOURCE_ACQUISITION_INCOMPLETE" for x in derived)
    failed_requests = sum(str(x.get("response_state","")).startswith("HTTP_") and x.get("response_state") != "HTTP_200" or x.get("response_state") == "NETWORK_ERROR" for x in ledger)
    report = {
        "total_frozen_cik": len(states),
        "complete_frozen_cik": complete_ciks,
        "incomplete_frozen_cik": incomplete_ciks,
        "total_candidates": len(rows),
        "complete_acquisition_candidates": len(rows)-incomplete_candidates,
        "source_acquisition_incomplete_candidates": incomplete_candidates,
        "successful_raw_objects": len(raw_manifest),
        "failed_requests": failed_requests,
        "status": "PASS" if incomplete_ciks == 0 and incomplete_candidates == 0 else "FAIL",
    }
    report["decision"] = "ACQUISITION_COMPLETE" if report["status"] == "PASS" else "ACQUISITION_INCOMPLETE"
    return report

def run_live(args):
    if os.environ.get("STEP11_METADATA_CERTIFICATION_ENABLE") != "YES":
        raise ex.ExecutionError("CERTIFICATION_NOT_EXPLICITLY_ENABLED")
    rows = ex.norm_rows(ex.load_rows(pathlib.Path(args.input638)))
    out = pathlib.Path(args.out); rawdir = out/"raw"; rawdir.mkdir(parents=True, exist_ok=True)
    plan = core.build_request_plan(rows)
    client = RepairedMetadataClient(core.NetworkPolicy(enabled=True,max_requests=len(plan)*20+100,retry_ceiling=2), os.environ.get("SEC_USER_AGENT") or UA_DEFAULT)
    derived, raw_manifest, state = ex.acquire(rows, client, rawdir)
    replayed=[]; pass_b_network=0; disagreements=638
    try:
        replayed = ex.replay(rows, raw_manifest, state, rawdir)
        disagreements = sum(a != b for a,b in zip(derived,replayed))
    finally:
        ex._persist_forensics(out,rows,plan,raw_manifest,state,client.audit,derived,replayed,pass_b_network,disagreements)
    if pass_b_network or disagreements:
        ex.write(out/"failure_decision.json",{"decision":"DETERMINISM_FAILED","pass_b_network_requests":pass_b_network,"semantic_disagreements":disagreements,"candidate_count":638})
        raise ex.ExecutionError("DETERMINISM_FAILED")
    ex.write(out/"metadata_coverage.json", ex.aggregate(rows,derived,client.audit))
    ex.write(out/"structural_strata.json", ex.strata(rows,derived))
    gate = eligibility(rows,state,derived,raw_manifest,client.audit)
    ex.write(out/"acquisition_eligibility.json",gate)
    if gate["status"] != "PASS":
        ex.write(out/"failure_decision.json",{"decision":INCOMPLETE,"certification_status":"NOT_CERTIFIED",**gate})
        raise ex.ExecutionError(INCOMPLETE)
    ex.write(out/"core_decision.json",{"decision":CORE_VALIDATED,"metadata_scope":ex.SCOPE,"candidate_count":638,"certification_status":"NOT_CERTIFIED_PENDING_MANDATORY_GATES"})
    print(CORE_VALIDATED)
    return 0

def _assert_request_contract():
    c=RepairedMetadataClient(core.NetworkPolicy(enabled=False,max_requests=0),UA_DEFAULT)
    req=c.build_request(core.endpoint_for_base("1"))
    headers={k.lower():v for k,v in req.header_items()}
    assert req.get_method()=="GET"
    assert req.full_url=="https://data.sec.gov/submissions/CIK0000000001.json"
    assert headers.get("user-agent")==UA_DEFAULT
    assert headers.get("accept")=="application/json,text/plain,*/*"
    assert headers.get("accept-encoding")=="identity"
    assert "authorization" not in headers and "cookie" not in headers

def run_validate(out):
    # Hard zero-network validation: no fetch() call is permitted.
    before=core.COUNTERS["network_requests"]
    _assert_request_contract()
    rows=ex.synthetic_rows(); ciks=sorted({r['issuer_cik'] for r in rows})
    specs={c:{"complete":False,"base_success":False,"filings":[],"failure_class":"HTTP_403"} for c in ciks}
    a,b,m,s,rd=ex._offline_replay(rows,specs,out/"all403")
    gate=eligibility(rows,s,a,m,[{"response_state":"HTTP_403"} for _ in ciks])
    assert len(a)==len(b)==638 and a==b
    assert sum(x['terminal_state']=="SOURCE_ACQUISITION_INCOMPLETE" for x in a)==638
    assert gate['status']=="FAIL" and gate['decision']=="ACQUISITION_INCOMPLETE" and len(m)==0
    partial={c:{"complete":True,"filings":[]} for c in ciks}; partial[ciks[0]]={"complete":False,"base_success":False,"filings":[]}
    pa,pb,pm,ps,prd=ex._offline_replay(rows,partial,out/"partial"); pg=eligibility(rows,ps,pa,pm,[])
    assert pa==pb and len(pa)==638 and pg['status']=="FAIL"
    success={c:{"complete":True,"filings":[]} for c in ciks}
    sa,sb,sm,ss,srd=ex._offline_replay(rows,success,out/"success"); sg=eligibility(rows,ss,sa,sm,[])
    assert sa==sb and len(sa)==638 and sg['status']=="PASS"
    assert core.COUNTERS["network_requests"]==before==0
    ex.write(out/"sec_request_contract_regression.json",{"successful_historical_reference":"STEP11 Expansion Run 40295222293","user_agent":UA_DEFAULT,"accept":"application/json,text/plain,*/*","accept_encoding":"identity","authorization_header":False,"PASS":True})
    ex.write(out/"all403_regression.json",{"candidate_count":638,"pass_a_source_acquisition_incomplete":638,"pass_b_source_acquisition_incomplete":638,"semantic_disagreements":0,"pass_b_network":0,"certification_eligibility":"FAIL_AS_EXPECTED","certified_decision_emitted":0,"PASS":True})
    ex.write(out/"partial_acquisition_regression.json",{"candidate_count":638,"semantic_disagreements":0,"certification_eligibility":"FAIL_AS_EXPECTED","PASS":True})
    ex.write(out/"full_acquisition_regression.json",{"candidate_count":638,"semantic_disagreements":0,"certification_eligibility":"PASS_TO_LATER_GATES_ONLY","final_certification_emitted":False,"PASS":True})
    ex.write(out/"network_kill_switch_report.json",{"actual_sec_requests":0,"actual_external_network_requests":0,"pass_b_network_requests":0,"PASS":True})
    ex.write(out/"repair_validation_summary.json",{"decision":"STEP11_LIVE_RETRY_V3_ACQUISITION_AND_CERTIFICATION_GATE_REPAIR_OFFLINE_VALIDATED","zero_real_network":True,"candidate_count":638,"sample32_mutations":0,"live_certification_executions":0,"PASS":True})
    print("STEP11_LIVE_RETRY_V3_ACQUISITION_AND_CERTIFICATION_GATE_REPAIR_OFFLINE_VALIDATED")
    return 0

def main():
    p=argparse.ArgumentParser(); p.add_argument("--mode",choices=["validate","certification"],required=True); p.add_argument("--out",required=True); p.add_argument("--input638"); a=p.parse_args(); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if a.mode=="validate": return run_validate(out)
    if not a.input638: raise ex.ExecutionError("INPUT638_REQUIRED")
    return run_live(a)
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e: print(json.dumps({"error":str(e)},sort_keys=True),file=sys.stderr); raise
