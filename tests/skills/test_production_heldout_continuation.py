"""既停止の書換えなしにordinal2..24へ進む。全データは合成、実モデル0。"""
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_continuation as c
REAL_ANCHOR=c.anchor
import test_production_heldout_ledger as ledger_fixture
import test_production_heldout_run as run_fixture
import test_production_heldout_operator as operator_fixture


class ContinuationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.f=ledger_fixture.HeldoutLedgerTests(methodName='runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.base=dict(self.f.contract,campaignId=c.CAMPAIGN)
        self.raw=c.contract_from_base(c.io.encoded(self.base));self.root=self.f.root
        p=patch.object(c,'verify_prior',return_value={});p.start();self.addCleanup(p.stop)

    def instance(self):return c.ContinuationLedger(self.root,self.raw)

    def test_all23_preserve_old_consumption_and_pending_without_fabricated_prefix(self):
        with self.instance().locked() as ledger:
            for ordinal in range(2,25):self.f.complete(ledger,ordinal,ordinal%2==0)
            s=ledger.summary();rows,_=ledger._history()
            self.assertEqual((rows[0]['ordinal'],rows[0]['stage']),(2,'primary_reserved'))
            self.assertEqual(len(rows),23*7)
            self.assertEqual((s['primaryReserved'],s['primaryLaunchMarked'],s['independentReserved']),(24,24,23))
            self.assertEqual((s['terminalSlots'],s['accountedSlots'],s['priorStoppedSlots']),(23,24,1))
            self.assertEqual((s['correct'],s['incorrect'],s['parentVerified']),(12,11,23))
            self.assertEqual((s['pending'],s['segment']['pending'],s['unattempted']),(1,0,0))
            with self.assertRaises(ValueError):self.f.stage(ledger,25,'primary_reserved')
            self.assertFalse(s['certifiesSkillGate'])

    def test_first_event_identity_and_stage_are_strict(self):
        with self.instance().locked() as ledger:
            for ordinal,stage in [(1,'primary_reserved'),(3,'primary_reserved'),(True,'primary_reserved'),
                (2.0,'primary_reserved'),(2,'independent_reserved'),(2,'parent_verified')]:
                with self.subTest(ordinal=ordinal,stage=stage),self.assertRaises(ValueError):
                    self.f.stage(ledger,ordinal,stage)
            self.f.stage(ledger,2,'primary_reserved')

    def test_failed_slot_is_consumed_and_old_slot_cannot_be_retried(self):
        with self.instance().locked() as ledger:
            self.f.stage(ledger,2,'primary_reserved');self.f.stage(ledger,2,'primary_started')
            self.f.stage(ledger,2,'primary_failed',resource_proof_sha256='c'*64)
            with self.assertRaises(ValueError):self.f.stage(ledger,2,'primary_reserved')
            self.f.stage(ledger,3,'primary_reserved')
            s=ledger.summary();self.assertEqual((s['primaryReserved'],s['evaluationFailed'],s['accountedSlots']),(3,1,2))

    def test_new_global_stop_remains_permanent(self):
        with self.instance().locked() as ledger:
            ledger.append(None,'global_stop','d'*64,stop_reason='unsafe')
            with self.assertRaises(ValueError):self.f.stage(ledger,2,'primary_reserved')
        with self.instance().locked() as ledger:self.assertEqual(ledger.summary()['status'],'stopped')

    def test_contract_cannot_reset_consumption_or_change_campaign(self):
        original=c.inputs.parse(self.raw)
        for key,value in [('priorStopAnchorSha256','0'*64),('campaignId',c.CAMPAIGN+'-other'),
            ('version',c.legacy.VERSION),('sourceCommit',c.PRIOR_SOURCE),('carryPrimary',0)]:
            raw=c.io.encoded(dict(original,**{key:value}))
            with self.subTest(key=key),self.assertRaises(ValueError):c.contract(raw)
        with self.instance().locked():pass
        changed=c.io.encoded(dict(original,sourceCommit='f'*40))
        with self.assertRaises(ValueError):
            with c.ContinuationLedger(self.root,changed).locked():pass

    def test_product_factory_resolves_only_one_new_root(self):
        with patch.object(c,'ContinuationLedger') as factory:
            c.legacy.open_shared(self.raw)
            factory.assert_called_once_with(c.inputs.PRIVATE_CASES.parent/c.ROOT_NAME,self.raw)

    def test_anchor_failure_precedes_new_storage(self):
        with patch.object(c,'verify_prior',side_effect=ValueError('SYNTHETIC_PRIOR_DRIFT')):
            with self.assertRaises(ValueError):self.instance()
        self.assertFalse(self.root.exists())


class ContinuationRunTests(unittest.TestCase):
    def setUp(self):
        self.f=run_fixture.HeldoutRunTests(methodName='runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        run=run_fixture.run;x=run.x;b=self.f.bound
        execution=dict(b.contract,campaignId=c.CAMPAIGN,outputRelativeRoot='measurements/'+c.CAMPAIGN)
        bound=x.bind(c.io.encoded(execution),b.deployment_raw,b.input_contract_raw,
            **dict(zip(x.inputs.INPUT_NAMES,b.raw_inputs)))
        self.f.bound=bound;self.f.proof.update(executionSha256=c.io.sha(bound.execution_raw))
        review,report,isolation=run_fixture.review_fixture.review_bytes(bound)
        self.f.bundle=run.Bundle(self.f.repo,bound,self.f.fixture.old.sdk_manifest_raw,review,report,isolation)
        self.f.resources.return_value=self.f.proof
        p=patch.object(c,'verify_prior',return_value={});p.start();self.addCleanup(p.stop)

    def test_driver_attempts_exactly23_and_finishes_with_prior_stop(self):
        run=run_fixture.run
        for _ in range(12):result=run.run(self.f.bundle)
        self.assertEqual(result['status'],'heldout_attempts_recorded_with_prior_stop')
        self.assertEqual((self.f.primary.call_count,self.f.independent.call_count,self.f.parent.call_count),(23,23,23))
        self.assertEqual([v.args[2] for v in self.f.primary.call_args_list],list(range(2,25)))
        self.assertEqual((result['summary']['terminalSlots'],result['summary']['accountedSlots']),(23,24))
        self.assertEqual(run.run(self.f.bundle)['slots'],[])
        self.assertEqual(self.f.primary.call_count,23)

    def test_prior_drift_is_rejected_before_creating_batch_control(self):
        run=run_fixture.run
        with patch.object(c,'verify_prior',side_effect=ValueError('PRIOR_DRIFT')), \
            patch.object(run,'batch_lock') as lock,self.assertRaisesRegex(ValueError,'PRIOR_DRIFT'):
            run.run(self.f.bundle)
        lock.assert_not_called()
        self.assertFalse((self.f.private/c.ROOT_NAME).exists())

    def test_ambiguous_new_start_stops_without_restarting(self):
        self.f.append(2,['primary_reserved','primary_started'])
        result=run_fixture.run.run(self.f.bundle)
        self.assertEqual(result['status'],'heldout_globally_stopped');self.f.primary.assert_not_called()
        self.assertEqual(result['summary']['primaryReserved'],2)


class ContinuationPacingTests(unittest.TestCase):
    def setUp(self):
        self.f=operator_fixture.HeldoutOperatorTests(methodName='runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.op=operator_fixture.op;x=self.op.x;b=self.f.bound
        execution=dict(b.contract,campaignId=c.CAMPAIGN,outputRelativeRoot='measurements/'+c.CAMPAIGN)
        self.bound=x.bind(c.io.encoded(execution),b.deployment_raw,b.input_contract_raw,
            **dict(zip(x.inputs.INPUT_NAMES,b.raw_inputs)))
        self.proof=dict(self.f.fixture.proof,executionSha256=c.io.sha(self.bound.execution_raw))
        self.f.stack.enter_context(patch.object(c,'verify_prior',return_value={}))
        self.f.stack.enter_context(patch.object(c,'PRIOR_WALL_SECONDS',500))
        self.prior=self.f.stack.enter_context(patch.object(c,'prior_pacing',
            return_value=(dict(monotonicSeconds=10**9,wallSeconds=500),c.PRIOR_PACING_SHA256)))
        self.wall_shift=0
        self.f.stack.enter_context(patch.object(self.op.time,'time',side_effect=lambda:1000+self.f.clock+self.wall_shift))
        self.sleep=self.f.stack.enter_context(patch.object(self.op.time,'sleep',side_effect=self.advance))
        self.ledger=c.ContinuationLedger(self.f.private/'new-ledger',self.bound.ledger_contract(c.io.encoded(self.proof)))
        for ordinal,role in [(2,'primary'),(2,'independent'),(3,'primary')]:
            self.op.create_directory(self.op.control_root(self.bound,ordinal));self.op.create_directory(self.bound.stage_root(ordinal,role))

    def advance(self,seconds):self.f.clock+=seconds

    def test_fresh60_after_completion_witness_then_normal_independent_and_next_primary(self):
        op=self.op;io=c.io
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved');op.pace(self.bound,2,'primary',ledger)
            raw=op.verify_pacing(self.bound,2,'primary');v=c.inputs.parse(raw)
            self.assertEqual(v['version'],'heldout-logical-pacing-0.2.0');self.sleep.assert_called_once_with(60.0)
            self.assertEqual(v['previousSha256'],c.PRIOR_PACING_SHA256);self.assertEqual(self.prior.call_count,2)
            self.assertEqual(v['monotonicSeconds']-v['handoff']['witnessMonotonicSeconds'],60)
            ledger.append(2,'primary_started')
            receipt=io.encoded(dict(artifactSha256={'logical-pacing.json':io.sha(raw)}))
            op.save(self.bound.stage_root(2,'primary'),'receipt.json',receipt);ledger.append(2,'primary_captured',io.sha(receipt))
            ledger.append(2,'independent_reserved');self.f.clock+=3;op.pace(self.bound,2,'independent',ledger)
            raw=op.verify_pacing(self.bound,2,'independent');self.assertNotIn('handoff',c.inputs.parse(raw))
            ledger.append(2,'independent_started')
            receipt=io.encoded(dict(artifactSha256={'logical-pacing.json':io.sha(raw)}))
            op.save(self.bound.stage_root(2,'independent'),'independent-receipt.json',receipt,
                additional_artifacts=frozenset({'independent-receipt.json'}))
            ledger.append(2,'independent_captured',io.sha(receipt));ledger.append(2,'parent_verified','e'*64,measured_correct=False)
            ledger.append(3,'primary_reserved');self.f.clock+=3;op.pace(self.bound,3,'primary',ledger)
            self.assertNotIn('handoff',c.inputs.parse(op.verify_pacing(self.bound,3,'primary')))

    def test_first_handoff_cannot_be_downgraded_even_if_both_pacing_copies_change(self):
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved');self.op.pace(self.bound,2,'primary',ledger)
            value=c.inputs.parse(self.op.verify_pacing(self.bound,2,'primary'))
            value.pop('handoff');value.update(version=self.op.launch.PACING_VERSION,waitedSeconds=0,
                monotonicSeconds=1,wallSeconds=1,previousSha256=None)
            raw=c.io.encoded(value)
            (self.op.control_root(self.bound,2)/'pacing.json').write_bytes(raw)
            (self.bound.stage_root(2,'primary')/'logical-pacing.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'first pacing version'):
                self.op.verify_pacing(self.bound,2,'primary')

    def test_wall_regression_between_prior_check_and_witness_is_rejected(self):
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved')
            with patch.object(self.op.time,'time',side_effect=[1000,100,100,100]), \
                self.assertRaisesRegex(ValueError,'prior wall clock'):
                self.op.pace(self.bound,2,'primary',ledger)
        self.sleep.assert_not_called()
        self.assertFalse((self.bound.stage_root(2,'primary')/'logical-pacing.json').exists())

    def test_fake_sleep_cannot_claim60_or_save_pacing(self):
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved')
            with patch.object(self.op.time,'sleep'),self.assertRaisesRegex(ValueError,'minimum logical'):
                self.op.pace(self.bound,2,'primary',ledger)
        self.assertFalse((self.bound.stage_root(2,'primary')/'logical-pacing.json').exists())

    def test_old_wall_clock_regression_rejects_before_sleep(self):
        self.prior.return_value=(dict(monotonicSeconds=1,wallSeconds=10**10),c.PRIOR_PACING_SHA256)
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved')
            with self.assertRaisesRegex(ValueError,'prior wall clock'):self.op.pace(self.bound,2,'primary',ledger)
        self.sleep.assert_not_called()

    def test_anchor_drift_after_wait_rejects_before_pacing_save(self):
        self.prior.side_effect=[(dict(monotonicSeconds=10**9,wallSeconds=500),c.PRIOR_PACING_SHA256),ValueError('PRIOR_DRIFT')]
        with self.ledger.locked() as ledger:
            ledger.append(2,'primary_reserved')
            with self.assertRaisesRegex(ValueError,'PRIOR_DRIFT'):self.op.pace(self.bound,2,'primary',ledger)
        self.assertFalse((self.bound.stage_root(2,'primary')/'logical-pacing.json').exists())


class PriorStopReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.f=ledger_fixture.HeldoutLedgerTests(methodName='runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=Path(self.f.temp.name)
        p=patch.object(c.inputs,'PRIVATE_CASES',self.root/'cases.json');p.start();self.addCleanup(p.stop)
        campaign=self.root/'measurements/heldout-matrix-survey-20261016-01'
        stage=campaign/'primary/attempt-0001';control=campaign/'controls/attempt-0001'
        for path in [campaign.parent,campaign,campaign/'primary',stage,campaign/'controls',control]:path.mkdir(mode=0o700)
        self.old=self.root/'measurement-ledgers/r04-heldout-two-repetitions-01'
        stop=c.io.encoded(dict(errorType='PUBLIC_SYNTHETIC_STOP'))
        contract=dict(self.f.contract,sourceCommit=c.PRIOR_SOURCE)
        with c.legacy.HeldoutLedger(self.old,c.io.encoded(contract)).locked() as ledger:
            ledger.append(1,'primary_reserved');ledger.append(1,'primary_started')
            ledger.append(None,'global_stop',c.io.sha(stop),stop_reason='evidence_invalid')
        pacing=c.io.encoded(dict(publicSyntheticPacing=True))
        self.refs={'ledgerContract':self.old/'contract.json',
            **{'event'+str(i):self.old/f'event-{i:04d}.json' for i in range(1,4)},
            'execution':stage/'contract.json','reservation':stage/'reservation.json','receipt':stage/'receipt.json',
            'runtimeResult':stage/'runtime-result.json','sdkResult':stage/'isolated-result.json',
            'stagePacing':stage/'logical-pacing.json','controlPacing':control/'pacing.json','globalStop':control/'global-stop.json'}
        raws={'execution':b'{}','reservation':b'{}',
            'receipt':c.io.encoded(dict(artifactSha256={'logical-pacing.json':c.io.sha(pacing)})),
            'runtimeResult':c.io.encoded(dict(exitCode=0,forcedShutdown=False,captureIntegrity=True)),
            'sdkResult':c.io.encoded(dict(sdkErrorType=None)),
            'stagePacing':pacing,'controlPacing':pacing,'globalStop':stop}
        for name,raw in raws.items():self.refs[name].write_bytes(raw);self.refs[name].chmod(0o600)
        self.hashes={name:c.io.sha(path.read_bytes()) for name,path in self.refs.items()}
        p=patch.object(c,'anchor',return_value={'sha256':self.hashes});p.start();self.addCleanup(p.stop)

    def test_readonly_validation_preserves_every_old_byte_and_stopped_state(self):
        self.assertEqual(len(c.verify_prior()),12)
        self.assertEqual({name:c.io.sha(path.read_bytes()) for name,path in self.refs.items()},self.hashes)
        self.assertEqual(c.inputs.parse(self.refs['event3'].read_bytes())['stage'],'global_stop')

    def test_old_content_change_prevents_new_directory_creation(self):
        self.refs['receipt'].write_bytes(b'{}')
        contract=c.contract_from_base(c.io.encoded(dict(self.f.contract,campaignId=c.CAMPAIGN)))
        target=self.root/'never-created'
        with self.assertRaisesRegex(ValueError,'prior original drift'):c.ContinuationLedger(target,contract)
        self.assertFalse(target.exists())

    def test_unknown_old_journal_file_rejected_without_following_it(self):
        (self.old/'event-0004.json').write_bytes(b'PUBLIC_UNKNOWN')
        with self.assertRaisesRegex(ValueError,'journal inventory'):c.verify_prior()

    def test_old_receipt_mode_symlink_and_hardlink_are_rejected(self):
        path=self.refs['receipt'];original=path.read_bytes();path.chmod(0o644)
        with self.assertRaises(ValueError):c.verify_prior()
        path.chmod(0o600)
        link=path.with_name('PUBLIC_HARDLINK');link.hardlink_to(path)
        with self.assertRaises(ValueError):c.verify_prior()
        link.unlink();path.unlink();path.symlink_to(self.refs['runtimeResult'])
        with self.assertRaises(OSError):c.verify_prior()

    def test_hash_consistent_but_noncompleted_prior_runtime_is_rejected(self):
        raw=c.io.encoded(dict(exitCode=1,forcedShutdown=False,captureIntegrity=True))
        self.refs['runtimeResult'].write_bytes(raw);self.hashes['runtimeResult']=c.io.sha(raw)
        with self.assertRaisesRegex(ValueError,'execution completion'):c.verify_prior()

    def test_anchor_file_bytes_are_pinned_before_private_read(self):
        # patchを外して実公開manifestを検査する。私的rootの一括列挙やケース読取りはしない。
        with patch.object(c.io,'read_regular',return_value=b'{}'):
            with self.assertRaises(ValueError):REAL_ANCHOR()


if __name__=='__main__':unittest.main()
