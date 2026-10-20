"""有限batchの順序/上限/再開/停止を合成台帳だけで検査。実private/model/process0。"""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_run as run
import test_production_heldout_execution as fixture
import test_production_heldout_launch as review_fixture


class HeldoutRunTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutExecutionTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.repo=self.fixture.repository;self.bound=self.fixture.bind()
        self.private=self.repo/'synthetic-private';self.private.mkdir(mode=0o700)
        self.stack.enter_context(patch.object(run.x.inputs,'PRIVATE_CASES',self.private/'cases.json'))
        self.stack.enter_context(patch.object(run.x.ledger,'SHARED_ROOT',self.private/'measurement-ledger'))
        self.proof=dict(status='heldout_resources_verified_not_launchable',sourceCommit=self.bound.contract['sourceCommit'],
            executionSha256=run.io.sha(self.bound.execution_raw),inputContractSha256=run.io.sha(self.bound.input_contract_raw))
        review,report,isolation=review_fixture.review_bytes(self.bound)
        self.bundle=run.Bundle(self.repo,self.bound,self.fixture.old.sdk_manifest_raw,review,report,isolation)
        self.resources=self.stack.enter_context(patch.object(run.preflight,'verify_resources',return_value=self.proof))
        self.auth=self.stack.enter_context(patch.object(run.operator,'auth_metadata'))
        self.primary=self.stack.enter_context(patch.object(run.operator,'run_primary',side_effect=self.fake_primary))
        self.independent=self.stack.enter_context(patch.object(run.score,'run_independent',side_effect=self.fake_independent))
        self.parent=self.stack.enter_context(patch.object(run.score,'finalize',side_effect=self.fake_parent))

    def append(self,ordinal,stages,*,correct=False):
        with run.ledger_for(self.bundle,self.proof).locked() as ledger:
            for stage in stages:
                marker=stage.endswith('_reserved') or stage.endswith('_started')
                kwargs={'measured_correct':correct} if stage=='parent_verified' else {}
                if stage.endswith('_failed'):kwargs['resource_proof_sha256']=run.io.sha(run.io.encoded(self.proof))
                ledger.append(ordinal,stage,None if marker else 'd'*64,**kwargs)

    def fake_primary(self,*args):
        self.append(args[2],['primary_reserved','primary_started','primary_captured'])
        return dict(status='heldout_primary_captured_awaits_independent')

    def fake_independent(self,*args):
        self.append(args[2],['independent_reserved','independent_started','independent_captured'])
        return dict(status='heldout_independent_captured')

    def fake_parent(self,*args):
        self.append(args[2],['parent_verified'])
        return dict(status='measured_incorrect',ledgerFinalized=True)

    def test_two_slots_then_24_total_without_repeating_primary_or_independent(self):
        first=run.run(self.bundle)
        self.assertEqual(first['summary']['parentVerified'],2)
        self.assertEqual([v['ordinal'] for v in first['slots']],[1,2])
        for _ in range(11):last=run.run(self.bundle)
        self.assertEqual(last['status'],'heldout_attempts_recorded')
        self.assertEqual(last['summary']['incorrect'],24)
        self.assertEqual((self.primary.call_count,self.independent.call_count,self.parent.call_count),(24,24,24))
        done=run.run(self.bundle);self.assertEqual(done['slots'],[])
        self.assertEqual(self.primary.call_count,24)
        text=run.io.encoded(last).decode()+repr(self.bundle)
        for forbidden in ['SYNTHETIC_PRIVATE_PROMPT','SYNTHETIC_CONTEXT','SE-1200','expected','trace.jsonl']:
            self.assertNotIn(forbidden,text)

    def test_maximum_slots_rejects_bool_zero_three_before_private_write(self):
        for count in [True,0,3,1.0]:
            with self.subTest(count=count),self.assertRaises(ValueError):run.run(self.bundle,maximum_slots=count)
        self.auth.assert_not_called();self.assertEqual(list(self.private.iterdir()),[])

    def test_resume_primary_captured_only_runs_independent_then_parent(self):
        self.fake_primary(*run.args(self.bundle,1))
        result=run.run(self.bundle,maximum_slots=1)
        self.primary.assert_not_called();self.assertEqual(self.independent.call_count,1)
        self.assertEqual(result['summary']['parentVerified'],1)

    def test_resume_independent_captured_only_runs_parent(self):
        self.fake_primary(*run.args(self.bundle,1));self.fake_independent(*run.args(self.bundle,1))
        result=run.run(self.bundle,maximum_slots=1)
        self.primary.assert_not_called();self.independent.assert_not_called()
        self.assertEqual(result['summary']['parentVerified'],1)

    def test_reserved_or_started_interruption_stops_without_retry(self):
        self.append(1,['primary_reserved','primary_started'])
        result=run.run(self.bundle)
        self.assertEqual(result['status'],'heldout_globally_stopped')
        self.assertEqual(result['summary']['evaluationFailed'],0)
        self.primary.assert_not_called();self.independent.assert_not_called();self.parent.assert_not_called()
        self.assertEqual(run.run(self.bundle)['slots'],[])

    def test_failure_counts_and_next_slot_is_attempted_without_retry(self):
        def fail(*args):
            self.append(args[2],['primary_reserved','primary_started','primary_failed'])
            return dict(status='evaluation_failed')
        self.primary.side_effect=fail
        result=run.run(self.bundle)
        self.assertEqual(result['summary']['evaluationFailed'],2)
        self.assertEqual([v['ordinal'] for v in result['slots']],[1,2])
        self.independent.assert_not_called();self.parent.assert_not_called()

    def test_stage_exception_is_durably_stopped_and_private_error_text_not_returned(self):
        self.primary.side_effect=ValueError('SYNTHETIC_PRIVATE_PROMPT_DO_NOT_PRINT')
        result=run.run(self.bundle)
        self.assertEqual(result['status'],'heldout_globally_stopped')
        self.assertNotIn('SYNTHETIC_PRIVATE_PROMPT',run.io.encoded(result).decode())
        self.assertEqual(self.primary.call_count,1);self.independent.assert_not_called()

    def test_preflight_only_opens_no_private_ledger_and_does_not_claim_remaining_budget(self):
        with patch.object(run,'ledger_for',side_effect=AssertionError('ledger opened')):
            result=run.preflight_only(self.bundle)
        self.assertFalse(result['privateLedgerOpened']);self.assertFalse(result['remainingReservationsVerified'])
        self.assertEqual(result['modelLaunches'],0);self.auth.assert_not_called()
        self.assertEqual(list(self.private.iterdir()),[])

    def test_review_rejection_precedes_private_lock_auth_and_stage(self):
        invalid=replace(self.bundle,review_raw=b'{}')
        with self.assertRaises(ValueError):run.run(invalid)
        self.auth.assert_not_called();self.primary.assert_not_called()
        self.assertEqual(list(self.private.iterdir()),[])

    def test_two_batch_owners_cannot_hold_lock_together(self):
        with run.batch_lock(self.bundle):
            with self.assertRaises(BlockingIOError):
                with run.batch_lock(self.bundle):self.fail('second owner acquired lock')
        self.primary.assert_not_called()

    def bundle_directory(self):
        base=self.repo/'.venv/heldout-bound-synthetic';base.mkdir()
        originals={'execution.json':self.bound.execution_raw,'deployment.json':self.bound.deployment_raw,
            'input-contract.json':self.bound.input_contract_raw,'sdk-manifest.json':self.bundle.sdk_raw,
            'prelaunch-review.json':self.bundle.review_raw,'prelaunch-report.json':self.bundle.report_raw,
            'local-isolation-proof.json':self.bundle.isolation_raw}
        for name,raw in originals.items():(base/name).write_bytes(raw)
        return base

    def test_load_source_failure_precedes_private_case_read(self):
        base=self.bundle_directory()
        with patch.object(run.preflight.public.guard,'git',return_value=b''), \
                patch.object(run.preflight.public.guard,'verify',side_effect=ValueError('source drift')):
            with self.assertRaises(ValueError):run.load(self.repo,base)
        self.fixture.reader.assert_not_called()

    def test_load_review_failure_precedes_private_case_read(self):
        base=self.bundle_directory();(base/'prelaunch-review.json').write_bytes(b'{}')
        with patch.object(run.preflight.public.guard,'git',return_value=b''), \
                patch.object(run.preflight.public.guard,'verify'):
            with self.assertRaises(ValueError):run.load(self.repo,base)
        self.fixture.reader.assert_not_called()

    def test_load_binds_reviewed_public_bundle_before_one_private_original_read(self):
        base=self.bundle_directory();original_git=self.fixture.old.git_mock.side_effect
        def git(repository,*args):
            if args==('status','--porcelain'):return b''
            if args==('rev-parse','HEAD'):return (self.bound.contract['sourceCommit']+'\n').encode()
            return original_git(repository,*args)
        with patch.object(run.preflight.public.guard,'git',side_effect=git):
            loaded=run.load(self.repo,base)
        self.assertEqual(loaded.bound,self.bound);self.fixture.reader.assert_called_once_with(run.x.inputs.PRIVATE_CASES)
        self.assertEqual(list(self.private.iterdir()),[])


if __name__=='__main__':unittest.main()
