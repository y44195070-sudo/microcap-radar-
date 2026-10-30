#!/usr/bin/env python3
"""1B-1E hard assertions over replay evidence + immutability checks. Writes assertion report."""
import sys, os, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); A = '/home/claude/audit'; P1 = A + '/product1'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
r1b = open(os.path.join(HERE, 'replay_1b1e_run1.json'), 'rb').read(); r2b = open(os.path.join(HERE, 'replay_1b1e_run2.json'), 'rb').read(); r = json.loads(r1b)
fa, fb, ar = r['fixture_a'], r['fixture_b'], r['assessment_replay']
P1A = {'PRODUCT_1A_1_GOLD_MANIFEST': (f'{P1}/PRODUCT_1A_1_GOLD_MANIFEST.json', '48eec75530572aa79d78b810788cb3f86f37f8e3a40ca102bbcc33622d05dc6b'),
       'FREEZE_MANIFEST_V1': (f'{P1}/jan_dev/PRODUCT_1A_EXTRACTOR_FREEZE_MANIFEST_V1.json', '9131b818d110427d92e16ba5f3c90afbeee88f79f71c4d8d6d39727f1e57682d'),
       'JAN_DEVELOPMENT_REPORT_V1': (f'{P1}/jan_dev/PRODUCT_1A_JAN_DEVELOPMENT_REPORT_V1.json', '76b42e5d9f7fe08c7d12b85d948f5f6fc63c0f5b03605e4d42e9f9ac8b226f92'),
       'FEB_BENCHMARK_REPORT': (f'{P1}/feb_bench/PRODUCT_1A_FEB_BENCHMARK_V1.json', '82b0585f49dd1487f34d4804991b31d41c9f77d9f30b69500aeb64ce86da317e'),
       'FEB_RUN_MANIFEST': (f'{P1}/feb_bench/PRODUCT_1A_FEB_BENCHMARK_RUN_MANIFEST_V1.json', '9f7ad74961c1ffa14dc2052ff8ca3abe67f89a2a4aaa37c761d57664f6899aff'),
       'FEB_REPORT_ERRATA_1': (f'{P1}/feb_bench/PRODUCT_1A_FEB_BENCHMARK_V1_REPORT_ERRATA_1.json', '45af871c6ac407080e6b2857c155ee4499e17f4efba951a4019f910c59ff3194'),
       'FEB_B1_PREDICTIONS': (f'{P1}/feb_bench/feb_b1_predictions.json', 'eee2ae6e949c904a3c44e258d9c2a52061d25ccbe5d2f7294ca0c0e11c7f6909'),
       'FEB_B2_PREDICTIONS': (f'{P1}/feb_bench/feb_b2_predictions.json', '3677d6326d3f82cee7c9099aea0ff76c0eb5a485ca40cf066d81feeabface97a'),
       'JAN_B1_PREDICTIONS': (f'{P1}/jan_dev/b1_jan_predictions.json', '4a109cd8d9e1def75a53bb90bd941f061b8dd70458ae7f6c375631a433f7063d'),
       'JAN_B2_PREDICTIONS': (f'{P1}/jan_dev/b2_jan_predictions.json', 'deac2e2ca56697247e8524d7b093b7d3642fae885e65c991c4267fb0384a313b'),
       'GOLD_TIER_FEB': (f'{A}/claude_feb/FEB_SUPPLY_RISK_TIER_V2_FROZEN.json', None)}
EXT = {'common.py': '16b2c448014c19489e2095d4c3335beb9f0d9d7ccd0b61dc5a66bd25bc5199d3', 'b1_deterministic_extractor.py': '1a8c66aca8bf4e8fac287e075b298deb13b45ab5ba641272b9b5967713c3db7d',
       'b2_deterministic_extractor.py': '857c87df500c89719fd40a32c0f7c0a6f494f349a7c95d112d43b727f28e768a', 'PRODUCT_1A_EXTRACTOR_CONFIG_V1.json': '18d1d556cadc655721daa1b07d4eab3e6c817c04bff19c86dfeb10e8951ef01e'}
RULE = {'supply_tier_v2.py': '89e8d99403c1255e74d1ac2cfc2a5d8b799251350e64f226847a29c7bb3de8b1', 'supply_assessment_v1.py': '8608aa9c3641de0b74ab6a814e30ca49e7d8a55734d47a0fb3fd5a9d645f18d3',
        'supply_targets_v1.py': '0f8399d7c31d0ff2c443b157aff499cfd98f0ea95289f5a34aa84e83f54fbbc5', 'supply_3a1_v1.py': 'eb30e615b2f2e20009a7a39dd6a52159db4acd38f3b9a7aeebb1dc765c7064ec',
        'field_validation_registry_v1.json': 'fbeecbf6953e38781d2b43739550cfe1d4528559c79540027a1f69affd914df6', 'action-3a1-signal-spec-v1.json': '539209fdc3cd38f329369f20e6f1f8d539a6c28fd5d4c990268aada97bc47045',
        'calendar_data_v1.json': '3106bf3beadb749afd6178d946a23305a4d5d4ab65cd68b5d8d86b933379c8d4'}
gold_tier_sha = sha(P1A['GOLD_TIER_FEB'][0])  # frozen Feb gold tier; reference prefix 2ae3a10c (FEB2026_OOS_RESULT)
X = {
 'A_FIXTURE_A_285_OF_285': fa['total_n'] == fa['matched_n'] == fa['denominator_n'] == 285 and fa['exact_match_rate'] == 1.0,
 'B_FIXTURE_A_SCOPE': fa['denominator_scope'] == 'ALL_RECORDS_INCL_UNASSESSABLE',
 'C_FIXTURE_B_268_OF_280': fb['total_n'] == 285 and fb['assessable_n'] == 280 and fb['unassessable_n'] == 5 and fb['matched_n'] == 268 and fb['denominator_n'] == 280 and fb['exact_match_rate'] == 268 / 280,
 'D_FIXTURE_B_SCOPE': fb['denominator_scope'] == 'ASSESSABLE_ONLY',
 'E_GOLD_DIST': fb['gold_dist'] == {'CRITICAL': 5, 'HIGH': 34, 'LOW': 147, 'MODERATE': 94, 'UNASSESSABLE': 5},
 'F_COMPUTED_DIST': fb['computed_dist'] == {'CRITICAL': 6, 'HIGH': 35, 'LOW': 141, 'MODERATE': 98, 'UNASSESSABLE': 5},
 'G_ASSESSMENT_285_EXACT': ar['compared_n'] == ar['exact_n'] == 285 and not ar['mismatch'],
 'H_ASSESSMENT_DIST': fb['assessment_dist'] == {'RESOLVED': 255, 'REVIEW_REQUIRED': 25, 'UNASSESSABLE': 5},
 'I_FUTURE_DATA_USED_ZERO': r['audit']['FUTURE_DATA_USED_IN_DECISION_PATH'] == 0,
 'J_NO_PRODUCT_1A_MUTATION': all(sha(p) == h for k, (p, h) in P1A.items() if k != 'GOLD_TIER_FEB') and gold_tier_sha.startswith('2ae3a10c'),
 'K_NO_FROZEN_EXTRACTOR_MUTATION': all(sha(f'{P1}/jan_dev/{f}') == h for f, h in EXT.items()),
 'L_NO_RULE_TIER_MUTATION': all(sha(os.path.join(HERE, '..', 'src', f)) == h for f, h in RULE.items()),
 'M_N_TWO_RUN_BYTE_IDENTITY_A_B': r1b == r2b,
 'O_NO_LIVE_NETWORK': r['net_attempts'] == 0,
 'P_NO_WORKFLOW_PUBLISH': not os.path.exists(os.path.join(HERE, '..', '.github')) and not os.path.exists(os.path.join(HERE, '..', 'v2')),
 'EXTRA_RETRIEVAL_FAILURES_ZERO': r['audit']['RETRIEVAL_FAILURES'] == 0}
fixA_payload = hashlib.sha256(json.dumps(r['records_a'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
fixB_payload = hashlib.sha256(json.dumps(r['records_b'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
rep = {'report_id': 'PRODUCT_1B_1E_REPLAY_ASSERTIONS_V1', 'mode': 'REGRESSION_REPLAY', 'no_new_research_claim': True, 'assertions': X, 'all_pass': all(X.values()),
       'replay_artifact_sha256': hashlib.sha256(r1b).hexdigest(), 'fixture_a_records_sha256': fixA_payload, 'fixture_b_records_sha256': fixB_payload,
       'daily_decision_payload_sha256': r['daily_decision_payload_sha256'], 'audit': r['audit'], 'product_1a_gold_tier_sha256': gold_tier_sha}
b = json.dumps(rep, sort_keys=True, separators=(',', ':')).encode(); open(os.path.join(HERE, 'replay_1b1e_assertions.json'), 'wb').write(b)
print(json.dumps({k: v for k, v in X.items()}, indent=0)); print('ALL', rep['all_pass'], hashlib.sha256(b).hexdigest())
