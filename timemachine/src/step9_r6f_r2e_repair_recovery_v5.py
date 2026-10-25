#!/usr/bin/env python3
"""V5: fail-closed repair for V4 unsupported YES claims.

V4 exposed a source-level certification bug in V2: CRSP capability fields were
set to YES even when the CRSP guide failed strict content validation.  Evidence
IDs, however, are only created when crsp_ok is true.  That creates unsupported
YES claims by construction.  V5 changes only that assignment gate at runtime;
the frozen V1-V4 sources remain untouched.
"""
from pathlib import Path

SRC = Path(__file__).with_name('step9_r6f_r2e_repair_recovery_v2.py')
source = SRC.read_text()
old = "for c in crsp_claims:caps[c]='YES'"
new = "for c in crsp_claims:\n    if crsp_ok:caps[c]='YES'"
assert source.count(old) == 1, 'V5_PATCH_TARGET_NOT_UNIQUE'
source = source.replace(old, new, 1)
# Keep an audit artifact even if a future unsupported claim reaches the assertion.
old2 = "assert not unsupported;dump(x.out,'unsupported_claim_audit.json',{'unsupported_yes_claims':0,'claims':[],'PASS':True})"
new2 = "dump(x.out,'unsupported_claim_audit.json',{'unsupported_yes_claims':len(unsupported),'claims':unsupported,'PASS':not unsupported});assert not unsupported"
assert source.count(old2) == 1, 'V5_UNSUPPORTED_AUDIT_TARGET_NOT_UNIQUE'
source = source.replace(old2, new2, 1)
code = compile(source, str(SRC) + '#v5-fail-closed', 'exec')
ns = {'__name__': '__main__', '__file__': str(SRC)}
exec(code, ns, ns)
