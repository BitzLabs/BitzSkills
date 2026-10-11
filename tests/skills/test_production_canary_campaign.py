"""有限実行入口の停止・再開禁止・順序を実台帳で検証する。モデル起動0。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_campaign as campaign
import test_production_ledger as ledger_fixture


class CanaryCampaignTests(unittest.TestCase):
    def setUp(self):
        fixture=ledger_fixture.ProductionLedgerTests(methodName='runTest');fixture.setUp()
        self.addCleanup(fixture.doCleanups);self.fixture=fixture
        self.repository=fixture.storage.parent;self.bound=fixture.bound;self.source=self.bound.contract['sourceCommit']
        for target,name,value in [(campaign,'ROOT',self.repository),(campaign.ledger,'common_ledger_path',lambda repo:fixture.storage)]:
            handle=patch.object(target,name,value);handle.start();self.addCleanup(handle.stop)
        handle=patch.object(campaign.capture,'prepare',return_value=(self.bound,{}));handle.start();self.addCleanup(handle.stop)
        self.instance=campaign.ledger.open_ledger(self.repository,self.bound)

    def primary(self,code=0,receipt=True):
        attempt=self.instance.reserve()
        if receipt:
            base=self.repository/attempt['outputRelativePath'];base.mkdir(parents=True)
            campaign.ledger.exclusive(base/'receipt.json',b'{"public":"synthetic-primary"}')
        return code

    def test_dry_run_has_no_reservations_or_model_calls(self):
        with patch.object(campaign.capture,'run') as primary,patch.object(campaign.score,'run') as independent:
            result=campaign.one(self.source,dry_run=True)
        primary.assert_not_called();independent.assert_not_called()
        self.assertEqual(result['primaryInvocations'],0);self.assertEqual(result['independentInvocations'],0)
        self.assertFalse((self.fixture.storage/'campaign.json').exists())

    def test_capture_failure_records_stop_before_independent_and_survives_restart(self):
        with patch.object(campaign.capture,'run',side_effect=lambda s:self.primary(1)),patch.object(campaign.score,'run') as independent:
            result=campaign.one(self.source)
            self.assertEqual(result['result']['reason'],'primary-capture-failed')
            with self.assertRaises(ValueError):campaign.one(self.source)
        independent.assert_not_called();self.assertFalse((self.fixture.storage/'independent-0001.json').exists())
        self.assertTrue((self.repository/'.venv/production-routing-campaign-public-initial/attempt-0001.json').is_file())

    def test_post_reservation_exception_with_missing_receipt_permanently_stops(self):
        def fail(source):self.primary(receipt=False);raise OSError('synthetic acquisition failure')
        with patch.object(campaign.capture,'run',side_effect=fail),patch.object(campaign.score,'run') as independent:
            result=campaign.one(self.source)
        self.assertEqual(result['result']['reason'],'primary-receipt-missing');independent.assert_not_called()
        with self.assertRaises(ValueError):self.instance.reserve()

    def test_pre_reservation_rejection_does_not_forge_attempt_or_stop(self):
        with patch.object(campaign.capture,'run',side_effect=ValueError('synthetic preflight drift')):
            with self.assertRaises(ValueError):campaign.one(self.source)
        self.assertFalse((self.fixture.storage/'attempt-0001.json').exists())
        self.assertFalse((self.fixture.storage/'stop-0001.json').exists())

    def test_structure_rejection_skips_independent_and_stops_same_reservation(self):
        with patch.object(campaign.capture,'run',side_effect=lambda s:self.primary()),\
             patch.object(campaign.evidence,'load_verified_capture',side_effect=ValueError('synthetic usage drift')),\
             patch.object(campaign.score,'run') as independent:
            result=campaign.one(self.source)
        self.assertEqual(result['result']['reason'],'primary-structure-rejected');independent.assert_not_called()
        with self.assertRaises(ValueError):campaign.one(self.source)

    def test_four_accepted_attempts_are_sequential_and_fifth_invokes_nothing(self):
        order=[]
        def primary(source):order.append('primary');return self.primary()
        def review(source,ordinal):
            order.append('independent');self.instance.reserve_independent_review(ordinal,'2'*64)
            return dict(status='independent_score_captured')
        def final(repo,source,ordinal):
            order.append('parent');value=self.fixture.accepted(self.bound.attempt(ordinal))
            raw=campaign.ledger.read_regular(self.fixture.storage/f'independent-{ordinal:04d}.json')
            value.update(reviewInputSha256='2'*64,independentReservationSha256=campaign.ledger.sha(raw))
            self.instance.record_verified_review(ordinal,campaign.ledger.encoded(value))
            return dict(status='parent_semantic_originals_verified',eligibleForMeasurement=True,certifiesSkillGate=False)
        with patch.object(campaign.capture,'run',side_effect=primary) as start,\
             patch.object(campaign.evidence,'load_verified_capture',return_value=object()),\
             patch.object(campaign.score,'prepare'),patch.object(campaign.score,'run',side_effect=review) as score,\
             patch.object(campaign.score,'finalize',side_effect=final):
            for ordinal in range(1,5):
                result=campaign.one(self.source);self.assertEqual(result['attempt']['attempt'],ordinal)
            result=campaign.one(self.source)
        self.assertEqual(order,['primary','independent','parent']*4)
        self.assertEqual(start.call_count,4);self.assertEqual(score.call_count,4)
        self.assertEqual(result['completed'],4);self.assertFalse(result['certifiesSkillGate'])

    def test_independent_reserved_failure_cannot_relaunch_or_finalize(self):
        def fail(source,ordinal):
            self.instance.reserve_independent_review(ordinal,'2'*64)
            raise OSError('synthetic score source changed after reservation')
        with patch.object(campaign.capture,'run',side_effect=lambda s:self.primary()),\
             patch.object(campaign.evidence,'load_verified_capture',return_value=object()),patch.object(campaign.score,'prepare'),\
             patch.object(campaign.score,'run',side_effect=fail),patch.object(campaign.score,'finalize') as parent:
            result=campaign.one(self.source)
        self.assertEqual(result['result']['status'],'stopped_independent_verification')
        self.assertIsNone(result['result']['actualIndependentInvocations']);parent.assert_not_called()
        with self.assertRaises(ValueError):campaign.one(self.source)


if __name__=='__main__':unittest.main()
