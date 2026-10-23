from __future__ import annotations

class OutcomeAccessError(RuntimeError): pass

class PredictionEngine:
    """STEP 5-6 shell only. Rule scoring intentionally not implemented."""
    def __init__(self, context_provider):
        self._context_provider=context_provider

    def context(self, entity_id, cutoff):
        return self._context_provider(entity_id, cutoff)

    def outcomes(self, *args, **kwargs):
        raise OutcomeAccessError("PredictionEngine cannot access Outcome World")

    def score(self, context_packet):
        raise NotImplementedError("Rule Engine V1 thresholds are not approved yet")
