"""故障診断の有限政策と失敗終端の束縛を検査する。有料起動0。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_fault_probe as probe


class FaultProbeTests(unittest.TestCase):
    def test_finite_policy_cannot_enable_paid_or_unbounded_scenarios(self):
        contract = json.loads((ROOT / probe.CONTRACT).read_bytes())
        for case in probe.CASES:
            self.assertEqual(probe.policy(contract, case), probe.CASES[case])
        for key, value in [('maximumScenarios', 5), ('maximumLocalHttpRequestsPerScenario', True),
                           ('paidModelCalls', 1), ('automaticPaidRetries', 1), ('timeoutSeconds', 300)]:
            bad = copy.deepcopy(contract)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): probe.policy(bad, 'http-503-zero-retry')
        with self.assertRaises(ValueError): probe.policy(contract, 'unknown')

    def test_success_requires_original_failed_turn_counts_and_clean_process_shutdown(self):
        frames = [{'method': method, 'params': {'threadId': 'thread', 'turn': {'id': 'turn', 'status': status}}}
                  for method, status in [('turn/started', 'inProgress'), ('turn/completed', 'failed')]]
        runtime = {'exitCode': 0, 'forcedShutdown': False}
        result = probe.outcome(frames, 'thread', 'turn', 1, 1, runtime, None)
        self.assertEqual(result['status'], 'bounded_fault_diagnostic_captured')
        self.assertFalse(result['certifiesAuthorizationRecovery'])
        for changes in [(frames, 'other', 'turn', 1, runtime, None),
                        (frames, 'thread', 'other', 1, runtime, None),
                        (frames, 'thread', 'turn', 2, runtime, None),
                        (frames, 'thread', 'turn', True, runtime, None),
                        (frames, 'thread', 'turn', 1, {'exitCode': 0, 'forcedShutdown': True}, None),
                        (frames, 'thread', 'turn', 1, runtime, 'TimeoutError'),
                        (frames[:-1], 'thread', 'turn', 1, runtime, None),
                        (list(reversed(frames)), 'thread', 'turn', 1, runtime, None),
                        (frames + [frames[-1]], 'thread', 'turn', 1, runtime, None)]:
            f, thread, turn, count, state, error = changes
            self.assertEqual(probe.outcome(f, thread, turn, count, 1, state, error)['status'], 'fault_diagnostic_stopped')
        success = copy.deepcopy(frames)
        success[-1]['params']['turn']['status'] = 'completed'
        self.assertEqual(probe.outcome(success, 'thread', 'turn', 1, 1, runtime, None)['status'], 'fault_diagnostic_stopped')


if __name__ == '__main__':
    unittest.main()
