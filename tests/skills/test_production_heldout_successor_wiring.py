"""実行契約0.3.0・停止理由・再試行の承認・連続失敗の遮断の接続。合成資源だけを使い、モデル0。"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_run as run
import production_matrix_survey_run as survey_run
import test_production_heldout_execution as execution_fixture

x, io, operator, policy = run.x, run.io, run.operator, run.policy
successor = x.successor


class SuccessorWiringTests(unittest.TestCase):
    def setUp(self):
        self.f = execution_fixture.HeldoutExecutionTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.private = Path(temp.name)
        self.f.patch(x.inputs, 'PRIVATE_CASES', new=self.private/'cases.json')
        d = x.deployment_for_execution(io.encoded(self.f.execution), io.encoded(self.f.deployment))
        context = x.public.capture.context_profile(self.f.old.originals[x.public.inventory.CONTEXT], d)
        self.f.execution.update(version=x.SUCCESSOR_VERSION, ledger=dict(harnessRetries=3, predecessor=None),
            conditionContextSha256=x.condition_context_sha256(context))

    def proof(self):
        return self.f.verify()

    def test_successor_execution_builds_a_date_free_ledger_contract(self):
        proof = self.proof()
        raw = self.f.bind().ledger_contract(io.encoded(proof))
        value = successor.contract(raw)
        self.assertEqual(value['budget']['harnessRetries'], 3)
        self.assertNotIn('sourceCommit', value)
        self.assertNotIn('resourceProofSha256', value)
        ledger = x.ledger.open_shared(raw)
        self.assertIsInstance(ledger, successor.SuccessorLedger)
        self.assertEqual(ledger.root, self.private/'measurement-ledgers'/self.f.execution['campaignId'])

    def test_condition_ignores_daily_values_and_tracks_meaning(self):
        bound, proof = self.f.bind(), self.proof()
        base = bound.condition_sha256(proof)
        daily = dict(proof, contextDate='2099-01-01', sourceCommit='e'*40, executionSha256='e'*64,
            deploymentSha256='e'*64, inputContractSha256='e'*64, snapshotManifestSha256='e'*64,
            contextProfileSha256='e'*64, originalCalibration=dict(status='other'),
            sourceSha256=dict(proof['sourceSha256'], **{x.public.inventory.CONTEXT: 'e'*64,
                x.public.capture.calibration.MANIFEST: 'e'*64}))
        self.assertEqual(base, bound.condition_sha256(daily))
        ledger_file = 'evals/skills/routing/production_heldout_ledger.py'
        for index, changed in enumerate([dict(proof, productResourcesSha256='e'*64), dict(proof, casesSha256='e'*64),
                dict(proof, sdkTreeSha256='e'*64), dict(proof, runtime=dict(proof['runtime'], files=1)),
                dict(proof, sourceSha256=dict(proof['sourceSha256'], **{ledger_file: 'e'*64}))]):
            with self.subTest(index=index):
                self.assertNotEqual(base, bound.condition_sha256(changed))
        self.f.execution['ledger']['harnessRetries'] = 4
        self.assertNotEqual(base, self.f.bind().condition_sha256(proof))

    def test_execution_rejects_invalid_successor_ledger_and_context_drift(self):
        for ledger in [dict(harnessRetries=25, predecessor=None), dict(harnessRetries=1),
                dict(harnessRetries=1, predecessor=dict(kind='successor-0.3.0', campaignId=self.f.execution['campaignId'],
                    contractSha256='a'*64, headSha256='b'*64, events=0))]:
            self.f.execution['ledger'] = ledger
            with self.subTest(ledger=ledger), self.assertRaises(ValueError):
                self.f.bind()
        self.f.execution['ledger'] = dict(harnessRetries=1, predecessor=None)
        self.f.execution['conditionContextSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'condition context drift'):
            self.proof()

    def test_stop_reason_is_classified_only_for_successor_ledgers(self):
        new, old = SimpleNamespace(records_daily_proof=True), SimpleNamespace()
        fault = policy.HarnessFault('provider_drift', 'catalog')
        self.assertEqual(operator.stop_reason(new, fault), 'provider_drift')
        self.assertEqual(operator.stop_reason(old, fault), 'evidence_invalid')
        self.assertEqual(operator.stop_reason(new, KeyboardInterrupt()), 'operator_interrupted')
        self.assertEqual(operator.daily_proof(new, dict(a=1)), io.sha(io.encoded(dict(a=1))))
        self.assertIsNone(operator.daily_proof(old, dict(a=1)))
        with self.assertRaises(policy.HarnessFault) as caught:
            operator.harness_check('provider_drift', run.require, False, 'catalog changed')
        self.assertEqual(caught.exception.reason, 'provider_drift')
        with self.assertRaises(policy.HarnessFault) as caught:
            operator.same_resources(dict(a=1), dict(a=2), 'resources changed')
        self.assertEqual(caught.exception.reason, 'resource_drift')

    def test_next_stage_handles_pending_retries_and_exhausted_fresh_slots(self):
        terminal = [dict(ordinal=1, stage='parent_verified')]
        self.assertEqual(run.next_stage([], dict(status='in_progress', pendingRetry=3, accountedSlots=24,
            terminalSlots=24)), (3, 'primary'))
        self.assertEqual(run.next_stage(terminal, dict(status='in_progress', pendingRetry=None, accountedSlots=5,
            terminalSlots=5, nextOrdinal=7, primaryReserved=9)), (7, 'primary'))
        self.assertEqual(run.next_stage(terminal, dict(status='in_progress', pendingRetry=None, accountedSlots=23,
            terminalSlots=23, nextOrdinal=None, primaryReserved=24)), (None, 'awaiting_retry'))
        self.assertEqual(run.next_stage(terminal, dict(status='in_progress', terminalSlots=1, primaryReserved=1)),
            (2, 'primary'))

    def bundle(self):
        return SimpleNamespace(bound=self.f.bind())

    def acknowledge(self, ordinal, value):
        control = operator.control_root(self.f.bind(), ordinal)
        operator.create_directory(control)
        operator.save(control, 'failure-acknowledgement.json', json.dumps(value).encode())

    def test_failure_streak_blocks_the_next_slot_until_acknowledged(self):
        rows = [dict(ordinal=1, stage='parent_verified'), dict(ordinal=2, stage='primary_failed'),
            dict(ordinal=3, stage='primary_failed')]
        self.assertFalse(run.failure_blocked(self.bundle(), rows[:2], 3))
        self.assertTrue(run.failure_blocked(self.bundle(), rows, 4))
        self.acknowledge(4, dict(version='evaluation-failure-acknowledgement-0.1.0', nextOrdinal=4,
            failedOrdinals=[2, 3], signature=['primary_failed'], decision='continue', reason='原因を確認した'))
        self.assertFalse(run.failure_blocked(self.bundle(), rows, 4))

    def predecessor(self):
        first = successor.open_for(io.encoded(dict(version=successor.VERSION, campaignId='heldout-matrix-first-01',
            conditionSha256='c'*64, model='gpt-6.1-sol', setVersion=x.inputs.SET_VERSION,
            budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0, harnessRetries=3),
            timeoutSeconds=dict(primary=300, independent=300), predecessor=None, certifiesSkillGate=False)))
        with first.locked() as held:
            for stage in ['primary_reserved', 'primary_started']:
                held.append(1, stage, resource_proof_sha256='1'*64 if stage.endswith('_reserved') else None)
            held.append(1, 'primary_failed', 'd'*64, resource_proof_sha256='1'*64)
            rows, head = held._history()
        return dict(kind='successor-0.3.0', campaignId='heldout-matrix-first-01', contractSha256=io.sha(first.raw),
            headSha256=head, events=len(rows))

    def test_retry_authorization_is_recorded_once_with_its_evidence(self):
        self.f.execution['ledger']['predecessor'] = self.predecessor()
        proof = self.proof()
        bundle = self.bundle()
        self.f.patch(run, 'resources', return_value=proof)
        with self.assertRaises(ValueError):
            run.authorize_retry(bundle, 1, stop_reason='evidence_invalid', prior_artifact_sha256='d'*64,
                evidence_sha256=['e'*64], reason='独立検分がない')
        with self.assertRaises(ValueError):
            run.authorize_retry(bundle, 2, stop_reason='provider_drift', prior_artifact_sha256='d'*64,
                evidence_sha256=['e'*64], reason='未実施の枠')
        result = run.authorize_retry(bundle, 1, stop_reason='provider_drift', prior_artifact_sha256='d'*64,
            evidence_sha256=['e'*64], reason='配信元のモデル一覧が変わった')
        self.assertEqual((result['status'], result['modelLaunches'], result['reservations']),
            ('heldout_retry_authorized', 0, 0))
        control = operator.control_root(bundle.bound, 1)
        raw = (control/'retry-authorization.json').read_bytes()
        self.assertEqual(io.sha(raw), result['authorizationSha256'])
        self.assertEqual(json.loads(raw)['failedRole'], 'primary')
        rows, summary = run.checkpoint(bundle, proof)
        self.assertEqual((rows[-1]['stage'], summary['pendingRetry'], summary['retriesUsed']), ('retry_authorized', 1, 1))
        self.assertEqual(run.next_stage(rows, summary), (1, 'primary'))


class SurveyFailureGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write(self, name, value):
        (self.root/name).write_bytes(json.dumps(value).encode())

    def slot(self, ordinal, status='evaluation_failed'):
        value = dict(ordinal=ordinal, status=status, failurePhase='primary' if status == 'evaluation_failed' else None,
            primary=dict(status='primary_capture_stopped', errorType='ValueError', timedOut=False))
        self.write(f'actual-slot-{ordinal:04d}.json', value)

    def test_two_identical_failures_stop_before_any_reservation(self):
        self.slot(1, 'measured_correct')
        self.slot(2)
        self.assertEqual(survey_run.failure_guard(self.root, 3)['status'], 'clear')
        self.slot(3)
        with self.assertRaisesRegex(ValueError, 'consecutive identical evaluation failures'):
            survey_run.failure_guard(self.root, 4)
        self.write('failure-acknowledgement-0004.json', dict(version='evaluation-failure-acknowledgement-0.1.0',
            nextOrdinal=4, failedOrdinals=[2, 3], signature=['primary', 'primary_capture_stopped', 'ValueError', False],
            decision='continue', reason='取得失敗の原因を確認した'))
        self.assertEqual(survey_run.failure_guard(self.root, 4)['status'], 'acknowledged')

    def test_missing_previous_record_breaks_the_streak(self):
        self.slot(2)
        self.assertEqual(survey_run.failure_guard(self.root, 4)['status'], 'clear')
        self.assertEqual(survey_run.failure_guard(self.root, 1)['status'], 'clear')


if __name__ == '__main__':
    unittest.main()
