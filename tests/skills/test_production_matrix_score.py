"""公開合成の単回採点・原照合・停止・誤選択分母。実provider/秘密取得0。"""
import copy
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_score as score
import test_production_matrix_semantic as fixture


class MatrixScoreTests(unittest.TestCase):
    def setUp(self):
        f=fixture.MatrixSemanticTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.f=f;self.provider=f.fixture;self.repository=self.provider.artifact_repository
        self.bound=self.provider.bound;self.primary_base=self.provider.base.capture.base
        for name,raw in self.provider.originals.items():
            path=self.primary_base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        (self.primary_base/'receipt.json').write_bytes(score.io.encoded(self.provider.receipt))
        self.primary_receipt=score.io.read_regular(self.primary_base/'receipt.json')
        self.mock(score.io,'common_ledger_path',return_value=self.repository/'.venv/shared.json')
        storage=score.matrix.shared_storage(self.provider.source_repository,self.bound);storage.parent.mkdir(mode=0o700)
        self.instance=score.matrix.MatrixLedger(storage,self.repository,self.bound)
        self.instance.reserve(1);self.instance.mark_primary_started(1)
        def primary_ref(name):
            path=self.primary_base/name
            return dict(relativePath=str(path.relative_to(self.repository)),sha256=score.io.sha(score.io.read_regular(path)))
        self.instance.record_primary(1,dict(self.bound.slot(1),actualInvocations=1,normalTerminal=True,nativeExitCode=0,
            integrityPassed=True,receipt=primary_ref('receipt.json'),trace=primary_ref('rpc-out.jsonl')))
        self.mock(score.capture,'verify_launch',return_value=dict(invocationArgvBytesMatched=True))
        self.scope=self.mock(score.capture,'prelaunch_review',return_value=dict(scope=score.SCOPE))
        self.mock(score.capture,'auth_metadata')
        self.proof=score.trace.strict_json(self.provider.originals['resource-guards.json'])['before']
        self.check=self.mock(score.p,'verify_resources',return_value=self.proof)
        self.spawn=self.mock(score.subprocess,'Popen',side_effect=self.spawned)
        self.prepared=f.prepared;self.answer=copy.deepcopy(f.answer)
        self.base=score.layout(self.repository,self.bound,1)
        self.args=(self.provider.source_repository,self.bound,1,self.provider.base.manifest,self.provider.base.schema,
            self.provider.base.profile,b'public synthetic prelaunch',score.io.encoded(dict(status='matrix_pipeline_prelaunch_code_verified')))

    def mock(self,target,name,**kwargs):
        p=patch.object(target,name,**kwargs);self.addCleanup(p.stop);return p.start()

    def stdout(self):return b''.join(score.io.encoded(e)+b'\n' for e in self.f.events(self.answer))

    def spawned(self,argv,**kwargs):
        reservation=self.instance.read('independent',1)
        self.assertEqual(reservation['reviewInputSha256'],self.prepared.bindings['reviewInputSha256'])
        self.assertFalse(self.instance.path('review',1).exists())
        expected=score.invocation(self.prepared,self.base)
        self.assertEqual(argv,expected['argv']);self.assertEqual(kwargs['env'],expected['environment'])
        score.io.exclusive(self.base/'response.json',score.io.encoded(self.answer))
        stdout=self.stdout()
        class Process:
            pid=987654321;returncode=0
            def communicate(this,input=None,timeout=None):
                if input is not None:self.assertEqual(input,score.semantic.prompt(self.prepared))
                return stdout,b''
            def poll(this):return this.returncode
        return Process()

    def run_score(self):return score.run(*self.args)
    def finish(self):return score.finalize(*self.args)
    def summary(self):return self.instance.summary()

    def test_single_process_and_parent_reloads_originals_safe_incorrect_remains_in_denominator(self):
        result=self.run_score();self.assertEqual(result['status'],'matrix_independent_captured')
        self.spawn.assert_called_once();self.assertFalse(result['ledgerFinalized'])
        self.assertEqual(self.summary()['independentReserved'],1)
        with self.assertRaisesRegex(ValueError,'pending'):self.instance.reserve(2)
        parent=self.finish();self.assertTrue(parent['ledgerFinalized']);self.assertTrue(parent['eligibleForMeasurement'])
        self.assertEqual(parent['verification']['proposedLedgerStatus'],'measured_incorrect')
        result=self.summary();self.assertEqual((result['parentVerified'],result['measuredIncorrect'],result['missingMeasurements']),(1,1,91))
        record=self.instance.read('review',1)
        self.assertIn('-independent/attempt-0001/',record['independentReceipt']['relativePath'])
        self.assertEqual(self.instance.reserve(2)['ordinal'],2)
        self.assertEqual(score.io.read_regular(self.primary_base/'receipt.json'),self.primary_receipt)
        # 別保存先の成果は一次inventoryに追加されず、親確定後も旧原loaderが通る。
        score.capture.originals_reader.load_provider_capture(self.bound,1,source_repository=self.provider.source_repository,
            artifact_repository=self.repository,manifest_raw=self.provider.base.manifest,
            schema_raw=self.provider.base.schema,context_raw=self.provider.base.profile)

    def test_primary_only_prelaunch_scope_rejected_before_independent_reservation(self):
        self.scope.return_value=dict(scope='public-matrix-primary-launch-only')
        with self.assertRaisesRegex(ValueError,'independent prelaunch scope'):self.run_score()
        self.assertEqual(self.summary()['independentReserved'],0);self.spawn.assert_not_called()

    def test_repeated_capture_rejected_without_refund_or_second_process(self):
        self.run_score();before=score.io.read_regular(self.base/'independent-receipt.json')
        with self.assertRaises((ValueError,FileExistsError)):self.run_score()
        self.spawn.assert_called_once();self.assertEqual(before,score.io.read_regular(self.base/'independent-receipt.json'))
        self.assertEqual(self.summary()['independentReserved'],1)

    def test_resource_drift_before_process_keeps_reservation_and_permanently_stops(self):
        self.check.side_effect=[self.proof,dict(self.proof,contextDate='2000-01-01')]
        result=self.run_score();self.assertEqual(result['status'],'matrix_independent_capture_stopped')
        self.spawn.assert_not_called();self.assertEqual(self.summary()['status'],'stopped')
        self.assertEqual(self.summary()['independentReserved'],1)
        receipt=score.trace.strict_json(score.io.read_regular(self.base/'independent-receipt.json'))
        self.assertEqual(receipt['independentInvocations'],0)
        self.check.side_effect=None
        with self.assertRaisesRegex(ValueError,'permanently'):self.run_score()

    def test_spawn_error_saves_failure_and_consumed_reservation(self):
        self.spawn.side_effect=OSError('synthetic spawn failure')
        result=self.run_score();self.assertEqual(result['errorType'],'OSError');self.assertEqual(result['independentInvocations'],0)
        self.assertEqual(self.summary()['independentReserved'],1);self.assertEqual(self.summary()['parentVerified'],0)
        self.assertTrue((self.base/'stop.json').exists())

    def test_timeout_terminates_process_preserves_partial_trace_and_blocks_parent(self):
        class Process:
            pid=987654321;returncode=-15
            def communicate(this,input=None,timeout=None):
                if input is not None:raise subprocess.TimeoutExpired('synthetic',timeout)
                return b'{"type":"thread.started","thread_id":"partial"}\n',b'partial stderr'
            def poll(this):return this.returncode
        self.spawn.side_effect=None;self.spawn.return_value=Process()
        with patch.object(score.os,'killpg') as kill:
            result=self.run_score();kill.assert_called_once_with(987654321,score.signal.SIGTERM)
        self.assertEqual(result['independentInvocations'],1)
        self.assertIn(b'partial',score.io.read_regular(self.base/'trace.jsonl'))
        receipt=score.trace.strict_json(score.io.read_regular(self.base/'independent-receipt.json'));self.assertTrue(receipt['timedOut'])
        with self.assertRaisesRegex(ValueError,'permanently'):self.finish()
        self.assertEqual(self.summary()['parentVerified'],0)

    def test_keyboard_interrupt_saves_stop_and_propagates(self):
        self.spawn.side_effect=KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):self.run_score()
        self.assertEqual(self.summary()['status'],'stopped');self.assertEqual(self.summary()['independentReserved'],1)
        self.assertTrue((self.base/'stop.json').exists())

    def test_existing_attempt_directory_is_untouched_after_reservation_failure(self):
        self.base.mkdir(parents=True);(self.base/'sentinel.txt').write_bytes(b'public original')
        result=self.run_score();self.assertEqual(result['status'],'matrix_independent_capture_stopped')
        self.assertEqual({p.name for p in self.base.iterdir()},{'sentinel.txt'});self.spawn.assert_not_called()
        self.assertEqual(self.summary()['independentReserved'],1)

    def test_unsafe_valid_response_preserved_but_parent_stops_instead_of_counting_incorrect(self):
        self.answer.update(safety='fail',safetyFindings=[dict(priority='P2',evidenceRefs=['native:final'],message='安全疑義。')])
        self.assertEqual(self.run_score()['status'],'matrix_independent_captured')
        before=score.io.read_regular(self.base/'response.json');parent=self.finish()
        self.assertFalse(parent['ledgerFinalized']);self.assertFalse(parent['eligibleForMeasurement'])
        self.assertEqual(self.summary()['status'],'stopped');self.assertEqual(self.summary()['measuredIncorrect'],0)
        self.assertEqual(before,score.io.read_regular(self.base/'response.json'))

    def test_invalid_original_response_stops_capture_without_parent_measurement(self):
        self.answer['bindings']['ordinal']=2
        result=self.run_score();self.assertEqual(result['status'],'matrix_independent_capture_stopped')
        self.assertEqual(self.summary()['parentVerified'],0);self.assertEqual(self.summary()['status'],'stopped')
        self.assertTrue((self.base/'response.json').exists())

    def test_parent_rejects_rehashed_invocation_or_response_drift(self):
        self.run_score();path=self.base/'invocation.json';value=score.trace.strict_json(score.io.read_regular(path))
        value['environment']['TZ']='UTC';path.write_bytes(score.io.encoded(value))
        receipt_path=self.base/'independent-receipt.json';receipt=score.trace.strict_json(score.io.read_regular(receipt_path))
        receipt['artifactSha256']['invocation.json']=score.io.sha(score.io.read_regular(path));receipt_path.write_bytes(score.io.encoded(receipt))
        before=score.io.read_regular(receipt_path);parent=self.finish()
        self.assertEqual(parent['errorType'],'ValueError');self.assertFalse(parent['ledgerFinalized'])
        self.assertEqual(before,score.io.read_regular(receipt_path));self.assertEqual(self.summary()['status'],'stopped')

    def test_unknown_name_and_links_rejected_before_original_content_opaque_not_read(self):
        self.run_score();opaque=self.base/'codex-home'/'synthetic-unread-sentinel';opaque.write_bytes(b'public unread')
        self.assertEqual(set(score.artifact_names(self.base)),score.ARTIFACTS)
        unknown=self.base/'unknown.json';unknown.write_bytes(b'public unknown')
        with patch.object(score.io,'read_regular',side_effect=AssertionError('content read')):
            with self.assertRaisesRegex(ValueError,'unknown original'):score.artifact_names(self.base)
        unknown.unlink();target=self.base/'response.json';raw=target.read_bytes();target.unlink();target.symlink_to(opaque)
        with self.assertRaisesRegex(ValueError,'file shape'):score.artifact_names(self.base)
        target.unlink();target.write_bytes(raw);os.link(target,self.base/'tmp'/'public-hardlink')
        with self.assertRaisesRegex(ValueError,'file shape'):score.artifact_names(self.base)

    def test_namespace_has_only_runtime_and_current_review_base_standard_auth_once(self):
        inv=score.invocation(self.prepared,self.base);argv=inv['argv']
        self.assertEqual(argv.count(str(score.capture.AUTH)),2)
        self.assertIn('--sandbox',argv);self.assertIn('read-only',argv);self.assertIn('--ephemeral',argv)
        self.assertNotIn(str(self.primary_base),argv);self.assertNotIn(str(self.provider.source_repository),argv)
        self.assertNotIn('--unshare-net',argv);self.assertEqual(inv['automaticRetries'],0)
        self.assertEqual(inv['timeoutSeconds'],300);self.assertEqual(inv['environment']['CODEX_HOME'],'/home/hide/.codex')
        config=score.config_for(self.base)
        self.assertFalse(config['agents.enabled']);self.assertFalse(config['features.shell_tool'])
        self.assertFalse(config['features.code_mode']);self.assertEqual(config['approval_policy'],'never')

    def test_parent_primary_record_hash_drift_rejected_before_any_independent_launch(self):
        path=self.primary_base/'receipt.json';path.write_bytes(self.primary_receipt+b' ')
        with self.assertRaises(ValueError):self.run_score()
        self.spawn.assert_not_called();self.assertFalse(self.instance.path('independent',1).exists())
        path.write_bytes(self.primary_receipt)
        self.assertEqual(self.summary()['status'],'stopped')
        with self.assertRaisesRegex(ValueError,'permanently'):self.run_score()
        self.spawn.assert_not_called();self.assertFalse(self.instance.path('independent',1).exists())

    def test_completed_parent_cannot_be_reapplied_or_replace_its_original_proof(self):
        self.run_score();self.finish();before=score.io.read_regular(self.base/'parent-verification.json')
        with self.assertRaisesRegex(ValueError,'already measured'):self.finish()
        self.assertEqual(self.summary()['status'],'in_progress')
        self.assertEqual(self.summary()['parentVerified'],1)
        self.assertEqual(before,score.io.read_regular(self.base/'parent-verification.json'))

    def test_parent_matching_originals_records_correct_measurement(self):
        self.prepared=self.f.matching_originals(None)
        self.answer.update(bindings=self.prepared.bindings,accuracy=True,semantic='pass',routingFindings=[])
        # 合成fixtureの新原をsetup。実台帳/実provider成果は変更しない。
        for name,raw in self.provider.originals.items():(self.primary_base/name).write_bytes(raw)
        (self.primary_base/'receipt.json').write_bytes(score.io.encoded(self.provider.receipt))
        primary=self.instance.read('primary',1)
        for key,name in [('receipt','receipt.json'),('trace','rpc-out.jsonl')]:
            primary[key]['sha256']=score.io.sha(score.io.read_regular(self.primary_base/name))
        self.instance.path('primary',1).write_bytes(score.io.encoded(primary))
        self.run_score();parent=self.finish()
        self.assertTrue(parent['ledgerFinalized'])
        self.assertEqual(parent['verification']['proposedLedgerStatus'],'measured_correct')
        self.assertEqual((self.summary()['measuredCorrect'],self.summary()['measuredIncorrect']),(1,0))

    def test_after_resource_drift_preserves_response_and_stops_before_parent_measurement(self):
        self.check.side_effect=[self.proof,self.proof,dict(self.proof,contextDate='2000-01-01')]
        result=self.run_score();self.assertEqual(result['status'],'matrix_independent_capture_stopped')
        self.assertEqual(result['independentInvocations'],1);self.assertEqual(self.summary()['parentVerified'],0)
        self.assertEqual(score.io.read_regular(self.base/'response.json'),score.io.encoded(self.answer))
        self.assertEqual(self.summary()['status'],'stopped')

    def test_parent_rehashed_saved_response_cannot_replace_original_message(self):
        self.run_score();path=self.base/'response.json';answer=copy.deepcopy(self.answer)
        answer['limitations']=['差し替えた合成応答。'];path.write_bytes(score.io.encoded(answer))
        receipt_path=self.base/'independent-receipt.json';receipt=score.trace.strict_json(score.io.read_regular(receipt_path))
        receipt['artifactSha256']['response.json']=score.io.sha(score.io.read_regular(path))
        receipt_path.write_bytes(score.io.encoded(receipt));before=score.io.read_regular(receipt_path)
        result=self.finish();self.assertFalse(result['ledgerFinalized']);self.assertEqual(result['errorType'],'ValueError')
        self.assertEqual(before,score.io.read_regular(receipt_path));self.assertEqual(self.summary()['parentVerified'],0)

    def test_prelaunch_resource_failure_remains_stopped_after_resources_are_restored(self):
        self.check.side_effect=ValueError('synthetic source/runtime mismatch')
        with self.assertRaisesRegex(ValueError,'source/runtime mismatch'):self.run_score()
        self.check.side_effect=None
        self.assertEqual(self.summary()['status'],'stopped')
        with self.assertRaisesRegex(ValueError,'permanently'):self.run_score()
        self.spawn.assert_not_called();self.assertEqual(self.summary()['independentReserved'],0)
