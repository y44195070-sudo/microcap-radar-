# Microcap Radar Time Machine

Research/validation engine isolated from `/v2/`.

Current scope: STEP 5–6 only.

Implemented foundations:
- append-only Point-in-Time facts
- `known_at <= cutoff` context gate
- immutable snapshot hashing
- prediction/outcome store isolation
- leakage/revision/corporate-action/reproducibility tests

Not implemented yet: Rule Engine scoring, January 2026 replay, outcomes/evaluation, UI, February+ data.

Model A target: EOD Pre-Spike Discovery.

Rule skeleton (thresholds intentionally NOT frozen): Supply 25 / Float Scarcity 20 / Catalyst 15 / Short Pressure 15 / Cash-Financing 15 / Pre-Ignition 10.
