"""PRODUCT-1B V1 assessment_status. Semantic source: feb_benchmark.py riskiest() + main() status rule (sha256 450dc9ca...).
REVIEW_REQUIRED_MODE = JOINT_SIMULTANEOUS_WORST_CASE: all UNRESOLVED fields of accessions in the 90d window set simultaneously to
is_atm/baby_shelf_limited=True, transaction_type='ATM_AGREEMENT', is_dilutive='TRUE'; tier recomputed once."""
from supply_tier_v2 import tier, win, RANK, P
def riskiest(cutoff, rows, b1, b2, u1, u2):
    w90 = {r['acc'] for r in win(rows, P(cutoff), 90)}
    B1 = {k: dict(v) for k, v in b1.items()}; B2 = {k: dict(v) for k, v in b2.items()}; any_u = False
    for a in w90:
        for f in u1.get(a, ()): B1[a][f] = True; any_u = True
        for f in u2.get(a, ()): B2[a][f] = 'ATM_AGREEMENT' if f == 'transaction_type' else 'TRUE'; any_u = True
    return any_u, B1, B2
def assess(cutoff, rows, b1, b2, u1, u2):
    """Returns dict(computed_tier, trigger_rule, trigger_accessions, worst_case_tier, assessment_status, unresolved_tier_material_fields)."""
    t, rule, accs = tier(cutoff, rows, b1, b2)
    any_u, B1, B2 = riskiest(cutoff, rows, b1, b2, u1, u2)
    tmax = tier(cutoff, rows, B1, B2)[0] if any_u else t
    w90 = sorted(r['acc'] for r in win(rows, P(cutoff), 90))
    unres = sorted([[a, f] for a in w90 for f in sorted(set(u1.get(a, ())) | set(u2.get(a, ())))])
    return {'computed_tier': t, 'trigger_rule': rule, 'trigger_accessions': accs, 'worst_case_tier': tmax,
            'assessment_status': 'REVIEW_REQUIRED' if RANK[tmax] > RANK[t] else 'RESOLVED', 'unresolved_tier_material_fields': unres if RANK[tmax] > RANK[t] else []}
