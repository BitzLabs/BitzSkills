"""固定入力と永続台帳の競合・再起動・停止を合成証拠で試験する。モデル呼出し0。"""
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_ledger as ledger
import test_routing_host as host_fixture


def contender(storage, bound, event, queue):
    event.wait(10)
    try:
        value = ledger.Ledger(Path(storage), bound).reserve()
        queue.put(('reserved', value['attempt']))
    except ValueError:
        queue.put(('stopped', None))


class ProductionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.venv' / 'test-temp')
        self.addCleanup(self.temp.cleanup)
        self.storage = Path(self.temp.name) / 'ledger'
        fixture = host_fixture.RoutingHostTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.raw_inputs = [
            ledger.encoded([{'id': 'PUBLIC-A', 'prompt': '公開の合成要求A', 'context': ['公開の状況'],
                             'expected': {'hidden': 'operator-only'}, 'control': 'operator-only'},
                            {'id': 'PUBLIC-B', 'prompt': '公開の合成要求B', 'context': []}]),
            ledger.encoded({'schemaVersion': '1.0', 'catalogVersion': '1.0.0', 'events': ['synthetic-event']}),
            (fixture.snapshot / 'manifest.json').read_bytes(), b'Common synthetic instructions', b'{"synthetic":true}',
        ]
        self.contract = {'schemaVersion': '1.0', 'phase': 4, 'scope': 'public-production-routing-canary-only',
                         'model': 'gpt-6.1-sol', 'sourceCommit': 'a' * 40, 'campaignId': 'public-canary',
                         'candidateSource': json.loads(self.raw_inputs[2])['sourceCommit'],
                         'certifiesBehavior': False, 'certifiesSkillGate': False,
                         'outputRelativeRoot': '.venv/production-routing-primary-synthetic',
                         'repetitions': 2, 'budget': {'primaryModelTrajectories': 4, 'independentReviewerSol': 4,
                                                      'automaticRetries': 0, 'delegations': 0},
                         'inputSha256': {k: ledger.sha(v) for k,v in zip(['cases','catalog','manifest','instructions','environment'], self.raw_inputs)}}
        self.bound = self.bind()

    def bind(self, contract=None, raws=None):
        return ledger.bind_inputs(ledger.encoded(contract or self.contract), *(raws or self.raw_inputs))

    def accepted(self, attempt):
        return {**attempt, 'status': 'accepted', 'independentReceiptSha256': '1' * 64,
                'parentVerificationSha256': '2' * 64, 'nativeTraceSha256': '3' * 64,
                'nativeStderrSha256': '4' * 64, 'decisionSha256': '5' * 64,
                'nativeExitCode': 0, 'normalTerminal': True, 'measurementIntegrityPassed': True,
                'severityCounts': {'P1': 0, 'P2': 0}, 'automaticRetry': False,
                'certifiesBehavior': False, 'certifiesSkillGate': False}

    def test_model_payload_excludes_id_expected_and_control(self):
        payload = json.loads(self.bound.payloads[0])
        self.assertEqual(set(payload), {'instructions', 'eventCatalog', 'case'})
        self.assertEqual(set(payload['case']), {'prompt', 'context'})
        self.assertNotIn('PUBLIC-A', self.bound.payloads[0].decode())
        self.assertNotIn('operator-only', self.bound.payloads[0].decode())

    def test_initial_canary_requires_exact_two_cases_two_repetitions(self):
        self.assertEqual(ledger.bind_initial_canary_inputs(ledger.encoded(self.contract), *self.raw_inputs), self.bound)
        smaller = {**self.contract, 'repetitions': 1,
                   'budget': {**self.contract['budget'], 'primaryModelTrajectories': 2, 'independentReviewerSol': 2}}
        self.assertEqual(self.bind(smaller).repetitions, 1)
        with self.assertRaises(ValueError):
            ledger.bind_initial_canary_inputs(ledger.encoded(smaller), *self.raw_inputs)

    def test_initialization_syncs_parent_for_new_and_existing_directory(self):
        for _ in range(2):
            with patch.object(ledger, 'sync_directory', wraps=ledger.sync_directory) as sync:
                ledger.Ledger(self.storage, self.bound)
                sync.assert_called_once_with(self.storage.parent)
        with patch.object(ledger, 'sync_directory', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError): ledger.Ledger(self.storage, self.bound)
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_independent_review_reservation_is_permanent_and_binds_input(self):
        instance = ledger.Ledger(self.storage, self.bound)
        attempt = instance.reserve()
        review_reservation = instance.reserve_independent_review(1, 'b' * 64)
        self.assertEqual(review_reservation['caseId'], attempt['caseId'])
        restarted = ledger.Ledger(self.storage, self.bound)
        for digest in ['b' * 64, 'c' * 64]:
            with self.subTest(digest=digest), self.assertRaises(FileExistsError):
                restarted.reserve_independent_review(1, digest)
        with self.assertRaises(ValueError): restarted.reserve()
        review = {**self.accepted(attempt), 'reviewInputSha256': 'b' * 64,
                  'independentReservationSha256': ledger.sha((self.storage / 'independent-0001.json').read_bytes())}
        for key, value in [('reviewInputSha256', 'c' * 64), ('independentReservationSha256', 'd' * 64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                restarted.record_verified_review(1, ledger.encoded({**review, key: value}))
        restarted.record_verified_review(1, ledger.encoded(review))
        with self.assertRaises(ValueError): restarted.reserve_independent_review(1, 'b' * 64)
        self.assertEqual(restarted.reserve()['attempt'], 2)

    def test_verified_review_requires_independent_reservation_and_stopped_is_final(self):
        instance = ledger.Ledger(self.storage, self.bound)
        attempt = instance.reserve()
        with self.assertRaises(FileNotFoundError): instance.record_verified_review(1, ledger.encoded(self.accepted(attempt)))
        instance.reserve_independent_review(1, 'b' * 64)
        stopped = {**self.accepted(attempt), 'status': 'stopped', 'reviewInputSha256': 'b' * 64,
                   'independentReservationSha256': ledger.sha((self.storage / 'independent-0001.json').read_bytes())}
        instance.record_verified_review(1, ledger.encoded(stopped))
        with self.assertRaises(ValueError): instance.reserve()
        with self.assertRaises(ValueError): instance.reserve_independent_review(1, 'b' * 64)

    def test_future_review_or_orphan_independent_record_rejected(self):
        instance = ledger.Ledger(self.storage, self.bound)
        instance.reserve()
        with self.assertRaises(ValueError): instance.reserve_independent_review(2, 'b' * 64)
        ledger.exclusive(self.storage / 'independent-0002.json', b'{}')
        with self.assertRaises(ValueError): instance.reserve_independent_review(1, 'b' * 64)

    def test_verified_review_dependency_missing_or_changed_stops_next_attempt(self):
        for fault in ['missing', 'changed']:
            storage = self.storage.parent / fault
            instance = ledger.Ledger(storage, self.bound, require_independent_reviews=True)
            attempt = instance.reserve()
            independent = instance.reserve_independent_review(1, 'b' * 64)
            path = storage / 'independent-0001.json'
            review = {**self.accepted(attempt), 'reviewInputSha256': 'b' * 64,
                      'independentReservationSha256': ledger.sha(path.read_bytes())}
            instance.record_verified_review(1, ledger.encoded(review))
            if fault == 'missing': path.unlink()
            else: path.write_bytes(ledger.encoded({**independent, 'reviewInputSha256': 'c' * 64}))
            with self.subTest(fault=fault), self.assertRaises((ValueError, FileNotFoundError)):
                instance.reserve()
            self.assertFalse((storage / 'attempt-0002.json').exists())

    def test_production_connection_disables_synthetic_reviews_and_mode_reset(self):
        with patch.object(ledger, 'common_ledger_path', return_value=self.storage):
            instance = ledger.open_ledger(ROOT, self.bound)
        self.assertTrue(instance.require_independent_reviews)
        attempt = instance.reserve()
        with self.assertRaises(ValueError): instance.record_review(1, ledger.encoded(self.accepted(attempt)))
        with self.assertRaises(ValueError): ledger.Ledger(self.storage, self.bound).reserve()

    def test_each_raw_input_is_hash_bound(self):
        for index in range(5):
            raws = list(self.raw_inputs)
            raws[index] += b' '
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.bind(raws=raws)

    def test_model_repetitions_and_budgets_are_finite_and_exact(self):
        for name, value in [('model', 'gpt-6-astra'), ('repetitions', True), ('repetitions', 3),
                            ('budget', {**self.contract['budget'], 'automaticRetries': 1}),
                            ('budget', {**self.contract['budget'], 'primaryModelTrajectories': 5}),
                            ('outputRelativeRoot', '/tmp/another-output')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.bind({**self.contract, name: value})

    def test_duplicate_case_ids_and_catalog_events_rejected(self):
        for index, key in [(0, 'cases'), (1, 'catalog')]:
            raws = list(self.raw_inputs)
            value = json.loads(raws[index])
            if index == 0:
                value[1]['id'] = value[0]['id']
            else:
                value['events'] *= 2
            raws[index] = ledger.encoded(value)
            contract = {**self.contract, 'inputSha256': {**self.contract['inputSha256'], key: ledger.sha(raws[index])}}
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.bind(contract, raws)

    def test_payload_or_repetition_tampering_cannot_open_ledger(self):
        for bound in [replace(self.bound, payloads=(b'{}', *self.bound.payloads[1:])),
                      replace(self.bound, repetitions=3)]:
            with self.assertRaises(ValueError):
                ledger.Ledger(self.storage, bound)

    def test_restart_preserves_consumed_reservation_and_blocks_next(self):
        first = ledger.Ledger(self.storage, self.bound).reserve()
        self.assertEqual(first['attempt'], 1)
        with self.assertRaises(ValueError):
            ledger.Ledger(self.storage, self.bound).reserve()
        self.assertEqual(len(list(self.storage.glob('attempt-*.json'))), 1)

    def test_accepted_reviews_enable_next_and_cap_is_four(self):
        instance = ledger.Ledger(self.storage, self.bound)
        for i in range(1,5):
            attempt = instance.reserve()
            self.assertEqual(attempt['attempt'], i)
            self.assertEqual(attempt['repetition'], 1 + (i-1) % 2)
            instance.record_review(i, ledger.encoded(self.accepted(attempt)))
        with self.assertRaises(ValueError):
            instance.reserve()
        self.assertEqual(len(list(self.storage.glob('attempt-*.json'))), 4)

    def test_stopped_review_is_permanent_and_not_refunded(self):
        instance = ledger.Ledger(self.storage, self.bound)
        attempt = instance.reserve()
        review = {**self.accepted(attempt), 'status': 'stopped', 'nativeExitCode': 1, 'normalTerminal': False}
        instance.record_review(1, ledger.encoded(review))
        with self.assertRaises(ValueError):
            instance.reserve()
        with self.assertRaises(FileExistsError):
            instance.record_review(1, ledger.encoded(self.accepted(attempt)))

    def test_mismatched_review_and_boolean_success_fields_rejected(self):
        instance = ledger.Ledger(self.storage, self.bound)
        attempt = instance.reserve()
        for key,value in [('modelInputSha256', 'f'*64), ('attempt', True), ('nativeExitCode', False),
                          ('severityCounts', {'P1': False, 'P2': 0}), ('independentReceiptSha256', 'missing'),
                          ('measurementIntegrityPassed', False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                instance.record_review(1, ledger.encoded({**self.accepted(attempt), key: value}))
        self.assertFalse((self.storage/'review-0001.json').exists())

    def test_changed_campaign_output_or_inputs_cannot_reset(self):
        ledger.Ledger(self.storage, self.bound).reserve()
        for name,value in [('campaignId','renamed'), ('outputRelativeRoot','.venv/production-routing-primary-renamed')]:
            other = self.bind({**self.contract,name:value})
            with self.subTest(name=name), self.assertRaises(ValueError):
                ledger.Ledger(self.storage, other).reserve()

    def test_symlinks_permissions_and_orphan_reviews_stop(self):
        target = Path(self.temp.name)/'target'; target.mkdir()
        self.storage.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            ledger.Ledger(self.storage,self.bound)
        self.storage.unlink()
        instance = ledger.Ledger(self.storage,self.bound)
        self.storage.chmod(0o755)
        with self.assertRaises(ValueError):
            ledger.Ledger(self.storage,self.bound)
        self.storage.chmod(0o700)
        (self.storage/'review-0001.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):
            instance.reserve()

    def test_concurrent_processes_reserve_only_one_unreviewed_attempt(self):
        ctx = multiprocessing.get_context('fork')
        event, queue = ctx.Event(), ctx.Queue()
        processes = [ctx.Process(target=contender,args=(str(self.storage),self.bound,event,queue)) for _ in range(2)]
        for p in processes:p.start()
        event.set()
        results = [queue.get(timeout=15) for _ in processes]
        for p in processes:
            p.join(timeout=15)
            self.assertFalse(p.is_alive())
            self.assertEqual(p.exitcode,0)
        self.assertEqual(sorted(r[0] for r in results), ['reserved','stopped'])

    def test_git_common_directory_anchors_all_worktrees(self):
        common = Path(self.temp.name)/'shared'/'.git'
        common.mkdir(parents=True)
        with patch.object(ledger.source_guard,'git',return_value=str(common).encode()):
            first = ledger.common_ledger_path(ROOT)
            second = ledger.common_ledger_path(Path(self.temp.name)/'other-worktree')
        self.assertEqual(first, second)
        self.assertEqual(first, common.parent/'.venv'/'production-routing-primary-ledger')


if __name__ == '__main__':
    unittest.main()
