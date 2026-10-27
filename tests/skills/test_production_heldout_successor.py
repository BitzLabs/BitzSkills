"""後継台帳の継続・再試行・印による旧入口の遮断。隔離した合成rootだけを使い、モデル0。"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_successor as s

legacy, io = s.legacy, s.io
DAY1, DAY2 = '1'*64, '2'*64


class SuccessorLedgerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        item = patch.object(s.inputs, 'PRIVATE_CASES', self.base/'cases.json')
        item.start()
        self.addCleanup(item.stop)

    def raw(self, campaign, predecessor=None, retries=4, **change):
        value = dict(version=s.VERSION, campaignId=campaign, conditionSha256='c'*64, model='gpt-6.1-sol',
            setVersion=s.inputs.SET_VERSION, budget=dict(primary=24, independent=24, automaticRetries=0,
                delegations=0, harnessRetries=retries), timeoutSeconds=dict(primary=300, independent=300),
            predecessor=predecessor, certifiesSkillGate=False)
        value.update(change)
        return io.encoded(value)

    def ledger(self, campaign, predecessor=None, retries=4):
        return s.open_for(self.raw(campaign, predecessor, retries))

    def spec(self, ledger, kind='successor-0.3.0'):
        with ledger.locked() as held:
            rows, head = held._history()
        return dict(kind=kind, campaignId=ledger.contract['campaignId'],
            contractSha256=io.sha(ledger.raw), headSha256=head, events=len(rows))

    def step(self, ledger, ordinal, stage, proof=DAY1, **kwargs):
        marker = stage.endswith(('_reserved', '_started'))
        daily = proof if stage.endswith(('_reserved', '_failed')) else None
        return ledger.append(ordinal, stage, None if marker else 'd'*64, resource_proof_sha256=daily, **kwargs)

    def complete(self, ledger, ordinal, correct=True, proof=DAY1):
        for stage in s.STAGES:
            self.step(ledger, ordinal, stage, proof, **({'measured_correct': correct} if stage == 'parent_verified' else {}))

    def fail(self, ledger, ordinal, role='primary', proof=DAY1):
        names = ['primary_reserved', 'primary_started'] if role == 'primary' else list(s.STAGES[:5])
        for stage in names:
            self.step(ledger, ordinal, stage, proof)
        self.step(ledger, ordinal, role+'_failed', proof)

    def stop(self, ledger, reason='evidence_invalid'):
        ledger.append(None, 'global_stop', 'e'*64, stop_reason=reason)

    def retry(self, ledger, ordinal, reason='resource_drift'):
        ledger.append(ordinal, 'retry_authorized', 'f'*64, stop_reason=reason)

    def first_campaign(self, *, stop_reason='evidence_invalid'):
        first = self.ledger('heldout-matrix-first-01')
        with first.locked() as held:
            self.complete(held, 1)
            self.fail(held, 2)
            self.step(held, 3, 'primary_reserved')
            self.step(held, 3, 'primary_started')
            self.stop(held, stop_reason)
        return first

    def test_fresh_ledger_requires_daily_proof_and_ordered_fresh_slots(self):
        with self.ledger('heldout-matrix-fresh-01').locked() as held:
            with self.assertRaises(ValueError):
                held.append(1, 'primary_reserved')
            with self.assertRaises(ValueError):
                self.step(held, 2, 'primary_reserved')
            self.complete(held, 1, proof=DAY1)
            # 日付が変わっても同じ台帳で、予約ごとに当日の証明を記録する。
            self.step(held, 2, 'primary_reserved', DAY2)
            self.step(held, 2, 'primary_started', DAY2)
            with self.assertRaises(ValueError):
                self.step(held, 2, 'primary_failed', DAY1)
            self.step(held, 2, 'primary_failed', DAY2)
            summary = held.summary()
        self.assertEqual((summary['correct'], summary['evaluationFailed'], summary['nextOrdinal']), (1, 1, 3))
        self.assertEqual(summary['retryEligible'], [])
        self.assertEqual(summary['status'], 'in_progress')

    def test_contract_shape_is_strict(self):
        for change in [dict(budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0, harnessRetries=25)),
                dict(budget=dict(primary=24, independent=24, automaticRetries=1, delegations=0, harnessRetries=1)),
                dict(sourceCommit='a'*40), dict(model='other'), dict(campaignId='other-01')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                s.contract(self.raw('heldout-matrix-shape-01', **change))
        own = dict(kind='successor-0.3.0', campaignId='heldout-matrix-shape-01', contractSha256='a'*64,
            headSha256='b'*64, events=0)
        with self.assertRaises(ValueError):
            s.contract(self.raw('heldout-matrix-shape-01', own))

    def test_retry_is_rejected_inside_the_same_campaign(self):
        with self.ledger('heldout-matrix-same-01').locked() as held:
            self.fail(held, 1)
            with self.assertRaises(ValueError):
                self.retry(held, 1)

    def test_successor_carries_results_and_retries_failed_or_interrupted_slots_once(self):
        first = self.first_campaign()
        spec = self.spec(first)
        second = self.ledger('heldout-matrix-second-01', spec, retries=2)
        with second.locked() as held:
            summary = held.summary()
            self.assertEqual(summary['retryEligible'], [2, 3])
            self.assertEqual((summary['correct'], summary['evaluationFailed'], summary['interruptedSlots']), (1, 1, 1))
            self.assertEqual((summary['nextOrdinal'], summary['accountedSlots'], summary['pending']), (4, 3, 0))
            self.assertEqual(summary['primaryReserved'], 3)
            for ordinal, reason in [(1, 'resource_drift'), (3, 'resource_drift'), (2, 'unsafe'), (5, 'resource_drift')]:
                with self.subTest(ordinal=ordinal, reason=reason), self.assertRaises(ValueError):
                    self.retry(held, ordinal, reason)
            # 中断した枠は、停止の理由を同じにした承認だけを受ける。
            self.retry(held, 3, 'evidence_invalid')
            with self.assertRaises(ValueError):
                self.step(held, 4, 'primary_reserved')
            self.complete(held, 3)
            self.retry(held, 2, 'provider_drift')
            self.fail(held, 2)
            with self.assertRaises(ValueError):
                self.retry(held, 2)
            self.complete(held, 4)
            summary = held.summary()
        self.assertEqual((summary['correct'], summary['evaluationFailed'], summary['interruptedSlots']), (3, 1, 0))
        self.assertEqual((summary['retriesUsed'], summary['retriesRemaining'], summary['primaryReserved']), (2, 0, 6))
        self.assertEqual(summary['campaigns'], ['heldout-matrix-first-01', 'heldout-matrix-second-01'])

    def test_retry_budget_is_cumulative(self):
        second = self.ledger('heldout-matrix-second-01', self.spec(self.first_campaign()), retries=1)
        with second.locked() as held:
            self.retry(held, 2)
            self.fail(held, 2)
            with self.assertRaises(ValueError):
                self.retry(held, 3, 'evidence_invalid')

    def test_exhausted_budget_and_reused_campaign_are_rejected(self):
        spec = self.spec(self.first_campaign())
        with self.ledger('heldout-matrix-second-01', spec, retries=0).locked() as held:
            self.assertEqual(held.summary()['retryEligible'], [])

    def test_safety_stop_is_never_retried(self):
        second = self.ledger('heldout-matrix-second-01', self.spec(self.first_campaign(stop_reason='unsafe')))
        with second.locked() as held:
            self.assertEqual(held.summary()['retryEligible'], [2])
            with self.assertRaises(ValueError):
                self.retry(held, 3, 'unsafe')

    def test_seal_blocks_the_predecessor_and_a_second_successor(self):
        first = self.first_campaign()
        spec = self.spec(first)
        with self.ledger('heldout-matrix-second-01', spec).locked():
            pass
        self.assertIn(s.SEAL_NAME, os.listdir(first.root))
        with first.locked() as held:
            self.assertTrue(held.sealed)
            with self.assertRaises(ValueError):
                self.stop(held)
        with self.assertRaises(ValueError), self.ledger('heldout-matrix-third-01', spec).locked():
            pass
        self.assertFalse(s.root_for('heldout-matrix-third-01').joinpath('contract.json').exists())

    def test_predecessor_must_be_at_a_boundary_and_match_its_head(self):
        first = self.ledger('heldout-matrix-first-01')
        with first.locked() as held:
            self.complete(held, 1)
            self.step(held, 2, 'primary_reserved')
        with self.assertRaises(ValueError), self.ledger('heldout-matrix-second-01', self.spec(first)).locked():
            pass
        self.assertNotIn(s.SEAL_NAME, os.listdir(first.root))
        with first.locked() as held:
            self.step(held, 2, 'primary_started')
            self.step(held, 2, 'primary_failed')
        spec = dict(self.spec(first), events=1)
        with self.assertRaises(ValueError), self.ledger('heldout-matrix-second-01', spec).locked():
            pass
        self.assertNotIn(s.SEAL_NAME, os.listdir(first.root))

    def test_predecessor_change_after_sealing_is_detected(self):
        first = self.first_campaign()
        second = self.ledger('heldout-matrix-second-01', self.spec(first))
        with second.locked():
            pass
        # 最後のeventは後続のhash連鎖を持たないので、印のheadとの照合で検出する。
        path = sorted(first.root.glob('event-*.json'))[-1]
        original = path.read_bytes()
        path.write_bytes(io.encoded(dict(json.loads(original), artifactSha256='a'*64)))
        with self.assertRaisesRegex(ValueError, 'seal'), second.locked():
            pass
        path.write_bytes(original)
        with second.locked():
            pass
        path = first.root/'event-0001.json'
        path.write_bytes(io.encoded(dict(json.loads(path.read_bytes()), ordinal=2)))
        with self.assertRaises(ValueError), second.locked():
            pass

    def test_successor_chain_reads_every_predecessor(self):
        first = self.first_campaign()
        second = self.ledger('heldout-matrix-second-01', self.spec(first))
        with second.locked() as held:
            self.retry(held, 3, 'evidence_invalid')
            self.complete(held, 3)
        third = self.ledger('heldout-matrix-third-01', self.spec(second))
        with third.locked() as held:
            summary = held.summary()
            self.assertEqual(summary['retryEligible'], [2])
            self.assertEqual(summary['campaigns'], ['heldout-matrix-first-01', 'heldout-matrix-second-01',
                'heldout-matrix-third-01'])
            self.retry(held, 2)
            self.complete(held, 2)
            self.assertEqual(held.summary()['correct'], 3)

    def continuation_fixture(self):
        continuation = s.continuation
        legacy_contract = dict(version=legacy.VERSION, campaignId=continuation.CAMPAIGN, sourceCommit='a'*40,
            inputContractSha256='b'*64, resourceProofSha256='c'*64, model='gpt-6.1-sol',
            setVersion=s.inputs.SET_VERSION, budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0),
            timeoutSeconds=dict(primary=300, independent=300), certifiesSkillGate=False)
        prior_rows = [dict(ordinal=1, stage='primary_reserved', measuredCorrect=None, stopReason=None),
            dict(ordinal=1, stage='primary_started', measuredCorrect=None, stopReason=None),
            dict(ordinal=None, stage='global_stop', measuredCorrect=None, stopReason='evidence_invalid')]
        prior = s.fold(s.empty_state(), prior_rows, 'heldout-matrix-survey-20261016-01')
        for item in [patch.object(continuation, 'verify_prior', return_value={}),
                patch.object(s, '_continuation_prior', return_value=prior)]:
            item.start()
            self.addCleanup(item.stop)
        raw = continuation.contract_from_base(io.encoded(legacy_contract))
        old = continuation.ContinuationLedger(s.inputs.PRIVATE_CASES.parent/continuation.ROOT_NAME, raw)
        with old.locked() as held:
            for ordinal in [2, 3]:
                for stage in s.STAGES:
                    marker = stage.endswith(('_reserved', '_started'))
                    held.append(ordinal, stage, None if marker else 'd'*64,
                        **({'measured_correct': True} if stage == 'parent_verified' else {}))
            rows, head = held._history()
        spec = dict(kind='continuation-0.2.0', campaignId=continuation.CAMPAIGN, contractSha256=io.sha(raw),
            headSha256=head, events=len(rows))
        return old, spec

    def test_continuation_predecessor_is_sealed_against_the_legacy_entry(self):
        old, spec = self.continuation_fixture()
        successor = self.ledger('heldout-matrix-survey-r3-20261027-01', spec)
        with successor.locked() as held:
            summary = held.summary()
            self.assertEqual((summary['correct'], summary['interruptedSlots'], summary['nextOrdinal']), (2, 1, 4))
            self.assertEqual(summary['retryEligible'], [1])
            self.assertEqual(summary['primaryReserved'], 3)
            self.step(held, 4, 'primary_reserved')
        with self.assertRaises(ValueError), old.locked():
            pass

    def test_reused_campaign_id_cannot_seal_the_predecessor(self):
        old, spec = self.continuation_fixture()
        with self.assertRaisesRegex(ValueError, 'campaign reused'), \
                self.ledger('heldout-matrix-survey-20261016-01', spec).locked():
            pass
        self.assertNotIn(s.SEAL_NAME, os.listdir(old.root))
        with old.locked():
            pass


class StopPolicyTests(unittest.TestCase):
    def authorization(self, **change):
        value = dict(version=s.policy.AUTHORIZATION_VERSION, contractSha256='a'*64, ordinal=3, failedRole='interrupted',
            stopReason='evidence_invalid', causeClass='evidence', priorArtifactSha256='b'*64,
            evidenceSha256=['c'*64], independentReviewSha256='d'*64, reason='未知の通知を評価基盤が拒否した',
            automaticRetry=False)
        value.update(change)
        return io.encoded(value)

    def test_classification_and_exception_mapping(self):
        policy = s.policy
        self.assertEqual([policy.classify(x) for x in ['unsafe', 'unknown_event', 'quota_exhausted']],
            ['safety', 'evidence', 'harness'])
        with self.assertRaises(ValueError):
            policy.classify('other')
        self.assertEqual(policy.stop_reason(policy.HarnessFault('provider_drift', 'catalog changed')), 'provider_drift')
        self.assertEqual(policy.stop_reason(ValueError('x')), 'evidence_invalid')
        self.assertEqual(policy.stop_reason(KeyboardInterrupt()), 'operator_interrupted')
        with self.assertRaises(ValueError):
            policy.HarnessFault('unsafe', 'not a harness reason')

    def test_authorization_requires_review_for_evidence_and_rejects_safety(self):
        authorize = lambda raw: s.policy.authorization(raw, contract_sha256='a'*64, ordinal=3)
        self.assertEqual(authorize(self.authorization())['causeClass'], 'evidence')
        authorize(self.authorization(stopReason='quota_exhausted', causeClass='harness', independentReviewSha256=None))
        for change in [dict(independentReviewSha256=None), dict(stopReason='unsafe', causeClass='safety'),
                dict(causeClass='harness'), dict(ordinal=4), dict(contractSha256='b'*64), dict(automaticRetry=True),
                dict(evidenceSha256=[]), dict(evidenceSha256=['c'*64, 'c'*64]), dict(reason=''), dict(extra=1),
                dict(failedRole='parent')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                authorize(self.authorization(**change))


if __name__ == '__main__':
    unittest.main()
