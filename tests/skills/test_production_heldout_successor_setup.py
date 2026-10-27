"""後継台帳へ移るための準備と再試行の承認の入口。合成した台帳と資源だけを使い、モデル0。"""
import io as stream
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_run as run
import production_heldout_successor_setup as setup
import test_production_heldout_successor as ledger_fixture
import test_production_heldout_successor_wiring as wiring_fixture

successor, io = setup.successor, setup.io


class PredecessorSetupTests(unittest.TestCase):
    def setUp(self):
        self.f = ledger_fixture.SuccessorLedgerTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_continuation_predecessor_and_carry_without_sealing(self):
        old, expected = self.f.continuation_fixture()
        result = setup.predecessor('continuation-0.2.0')
        self.assertEqual(expected, result['predecessor'])
        carry = result['carry']
        self.assertEqual((carry['correct'], carry['interruptedSlots'], carry['nextOrdinal'], carry['retryCandidates']),
            (2, 1, 4, [1]))
        self.assertNotIn(successor.SEAL_NAME, os.listdir(old.root))
        with old.locked():
            pass
        with self.f.ledger('heldout-matrix-survey-r3-20261027-01', result['predecessor']).locked():
            pass
        with self.assertRaisesRegex(ValueError, 'already has a successor'):
            setup.predecessor('continuation-0.2.0')

    def test_successor_predecessor_reads_the_chain(self):
        first = self.f.first_campaign()
        result = setup.predecessor('successor-0.3.0', 'heldout-matrix-first-01')
        self.assertEqual(self.f.spec(first), result['predecessor'])
        self.assertEqual(result['carry']['retryCandidates'], [2, 3])
        with self.assertRaises((ValueError, OSError)):
            setup.predecessor('successor-0.3.0', 'heldout-matrix-missing-01')


class SuccessorExecutionSetupTests(unittest.TestCase):
    def setUp(self):
        self.w = wiring_fixture.SuccessorWiringTests(methodName='runTest')
        self.w.setUp()
        self.addCleanup(self.w.doCleanups)
        self.f = self.w.f
        self.legacy = dict(self.f.execution, version=setup.x.VERSION)
        for key in ['ledger', 'conditionContextSha256']:
            self.legacy.pop(key)
        self.spec = dict(kind='continuation-0.2.0', campaignId=successor.continuation.CAMPAIGN,
            contractSha256='a'*64, headSha256='b'*64, events=12)

    def build(self, campaign='heldout-matrix-survey-r3-20261027-01'):
        return setup.execution(io.encoded(self.legacy), io.encoded(self.f.deployment), self.f.repository,
            campaign_id=campaign, harness_retries=3, predecessor_value=self.spec)

    def test_execution_keeps_conditions_and_switches_campaign_and_ledger(self):
        raw = self.build()
        value = setup.x.execution_contract(raw)
        self.assertEqual(setup.x.SUCCESSOR_VERSION, value['version'])
        self.assertEqual(('heldout-matrix-survey-r3-20261027-01', 'measurements/heldout-matrix-survey-r3-20261027-01'),
            (value['campaignId'], value['outputRelativeRoot']))
        self.assertEqual(dict(harnessRetries=3, predecessor=self.spec), value['ledger'])
        self.assertEqual(self.f.execution['conditionContextSha256'], value['conditionContextSha256'])
        for key in ['sourceCommit', 'pins', 'budget', 'timeoutSeconds', 'inputContractSha256', 'deploymentSha256']:
            self.assertEqual(self.legacy[key], value[key])
        self.f.execution = value
        ledger = successor.contract(self.f.bind().ledger_contract(io.encoded(self.f.verify())))
        self.assertEqual(self.spec, ledger['predecessor'])
        with self.assertRaises(ValueError):
            self.build(campaign=successor.continuation.CAMPAIGN)

    def test_cli_writes_a_new_file_only(self):
        directory = Path(self.w.private)
        paths = dict(execution=directory/'execution.json', deployment=directory/'deployment.json',
            predecessor=directory/'predecessor.json', output=directory/'successor-execution.json')
        paths['execution'].write_bytes(io.encoded(self.legacy))
        paths['deployment'].write_bytes(io.encoded(self.f.deployment))
        paths['predecessor'].write_bytes(io.encoded(dict(predecessor=self.spec)))
        argv = ['execution', '--execution', str(paths['execution']), '--deployment', str(paths['deployment']),
            '--predecessor', str(paths['predecessor']), '--campaign', 'heldout-matrix-survey-r3-20261027-01',
            '--harness-retries', '3', '--output', str(paths['output'])]
        output = stream.StringIO()
        with patch.object(setup.Path, 'cwd', return_value=self.f.repository), redirect_stdout(output):
            setup.main(argv)
        printed = json.loads(output.getvalue())
        self.assertEqual(io.sha(paths['output'].read_bytes()), printed['executionSha256'])
        self.assertTrue(printed['prelaunchReviewRequired'])
        with patch.object(setup.Path, 'cwd', return_value=self.f.repository), self.assertRaises(FileExistsError):
            setup.main(argv)


class AuthorizeRetryCliTests(unittest.TestCase):
    def test_cli_records_the_authorization(self):
        w = wiring_fixture.SuccessorWiringTests(methodName='runTest')
        w.setUp()
        self.addCleanup(w.doCleanups)
        w.f.execution['ledger']['predecessor'] = w.predecessor()
        proof = w.proof()
        bundle = SimpleNamespace(bound=w.f.bind())
        output = stream.StringIO()
        with patch.object(run, 'load', return_value=bundle), patch.object(run, 'resources', return_value=proof), \
                redirect_stdout(output):
            code = run.main(['--bundle', '.venv/heldout-bound-synthetic', '--authorize-retry', '1',
                '--stop-reason', 'provider_drift', '--prior-artifact', 'd'*64, '--evidence', 'e'*64,
                '--reason', '配信元のモデル一覧が変わった'])
        self.assertEqual(0, code)
        result = json.loads(output.getvalue())
        self.assertEqual(('heldout_retry_authorized', 1, 0), (result['status'], result['ordinal'], result['modelLaunches']))
        rows, summary = run.checkpoint(bundle, proof)
        self.assertEqual(1, summary['pendingRetry'])


if __name__ == '__main__':
    unittest.main()
