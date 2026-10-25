#!/usr/bin/env python3
"""STEP10 certified-only historical identity consumption boundary.

This module is deliberately fail-closed. Certification is keyed only by the
frozen forensic_occurrence_id emitted by STEP9. No ticker/FIGI/issuer/CIK or
current/future-state fallback is accepted.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping

CERTIFIED = "CERTIFIED_IDENTITY"
UNCERTIFIED = "IDENTITY_UNAVAILABLE_OR_UNCERTIFIED"
UNKNOWN = "UNKNOWN_OCCURRENCE"

@dataclass(frozen=True)
class GuardDecision:
    forensic_occurrence_id: str
    status: str
    identity_dependent_downstream_allowed: bool
    governance_class: str | None = None
    certified_identity_key: str | None = None

class CertifiedOnlyConsumptionGuard:
    def __init__(self, allowlist: Iterable[Mapping], denylist: Iterable[Mapping]):
        self._allow: Dict[str, Mapping] = {}
        self._deny: Dict[str, Mapping] = {}
        for row in allowlist:
            oid = row.get("forensic_occurrence_id")
            if not oid or oid in self._allow:
                raise ValueError("invalid/duplicate allowlist occurrence key")
            self._allow[oid] = row
        for row in denylist:
            oid = row.get("forensic_occurrence_id")
            if not oid or oid in self._deny:
                raise ValueError("invalid/duplicate denylist occurrence key")
            self._deny[oid] = row
        overlap = set(self._allow) & set(self._deny)
        if overlap:
            raise ValueError("allowlist/denylist occurrence overlap")

    def decide(self, forensic_occurrence_id: str) -> GuardDecision:
        if forensic_occurrence_id in self._allow:
            row = self._allow[forensic_occurrence_id]
            return GuardDecision(forensic_occurrence_id, CERTIFIED, True,
                                 certified_identity_key=row.get("certified_identity_key"))
        if forensic_occurrence_id in self._deny:
            row = self._deny[forensic_occurrence_id]
            return GuardDecision(forensic_occurrence_id, UNCERTIFIED, False,
                                 governance_class=row.get("governance_class"))
        return GuardDecision(forensic_occurrence_id, UNKNOWN, False)

    def require_certified(self, forensic_occurrence_id: str) -> GuardDecision:
        decision = self.decide(forensic_occurrence_id)
        if not decision.identity_dependent_downstream_allowed:
            raise PermissionError(decision.status)
        return decision

    def query_coverage(self, occurrence_ids: Iterable[str]) -> dict:
        ids: List[str] = list(occurrence_ids)
        decisions = [self.decide(x) for x in ids]
        certified = sum(x.status == CERTIFIED for x in decisions)
        unavailable = sum(x.status == UNCERTIFIED for x in decisions)
        unknown = sum(x.status == UNKNOWN for x in decisions)
        requested = len(ids)
        if certified == 0:
            status = "NO_CERTIFIED_IDENTITY"
        elif unavailable or unknown:
            status = "PARTIAL"
        else:
            # No numeric sufficiency threshold is invented here. Fully certified
            # requests are the only queries marked SUFFICIENT at this boundary.
            status = "SUFFICIENT"
        return {
            "requested_occurrences": requested,
            "certified_occurrences": certified,
            "unavailable_occurrences": unavailable,
            "unknown_occurrences": unknown,
            "query_coverage_pct": round((certified / requested * 100), 3) if requested else 0.0,
            "result_status": status,
            "coverage_representativeness": "NOT_CERTIFIED",
            "coverage_bias_risk": "HIGH",
        }
