"""一次取得の予約/単回起動/停止を公開合成で検査。実provider・秘密読取0。"""
import copy
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_capture as capture
import test_production_matrix_preflight as fixture


class MatrixCaptureTests(unittest.TestCase):
    def setUp(self):
        r=fixture.MatrixPreflightTests(methodName='runTest');r.setUp();self.addCleanup(r.doCleanups)
        self.r=r;self.repository=r.repository;self.report=dict(version='independent-review-1',sourceCommit=r.source,
            status='matrix_primary_capture_prelaunch_code_verified',independentContext=True,findings=[],blockingFindings=[],
            tests=dict(count=1,exitCode=0),cleanBefore='',cleanAfter='')
        self.report_raw=capture.io.encoded(self.report);self.make_review()
        self.proof=dict(publicSyntheticResourceProof=True)
        self.check=self.mock(capture.p,'verify_resources',return_value=self.proof)
        self.mock(capture,'auth_metadata')
        self.mock(capture.io,'common_ledger_path',return_value=self.repository/'.venv/shared-ledger.json')
        self.mock(capture.originals_reader,'load_provider_capture',side_effect=self.load)
        self.verify=self.mock(capture,'verify_launch',return_value=dict(invocationArgvBytesMatched=True,eligibleForMeasurement=False))
        self.spawn=self.mock(capture.subprocess,'Popen',side_effect=self.spawned)
        self.storage=self.repository/'.venv/production-matrix-ledgers'/self.r.bound.contract['campaignId']
        self.base=self.repository/self.r.bound.contract['outputRelativeRoot']/'attempt-0001'

    def mock(self,target,name,**kwargs):
        p=patch.object(target,name,**kwargs);self.addCleanup(p.stop);return p.start()

    def make_review(self):
        d_raw=capture.io.encoded(self.r.deployment)
        self.review=dict(version=capture.REVIEW_VERSION,scope='public-matrix-primary-launch-only',sourceCommit=self.r.source,
            conditionSha256=capture.condition_sha256(self.r.bound,d_raw),reviewReportSha256=capture.io.sha(self.report_raw),
            independentContext=True,severityCounts=dict(P1=0,P2=0),certifiesSkillGate=False,certifiesRelease=False)
        self.review_raw=capture.io.encoded(self.review)
        self.r.execution['pins']['prelaunchReview']=capture.io.sha(self.review_raw);self.r.bound=self.r.bind()
        self.r.deployment['executionSha256']=capture.io.sha(self.r.bound.execution_raw)

    def load(self,*_,**__):return SimpleNamespace(receipt_raw=capture.io.read_regular(self.base/'receipt.json'))

    def spawned(self,*_,**__):
        instance=capture.p.matrix.MatrixLedger(self.storage,self.repository,self.r.bound)
        self.assertEqual(instance.read('attempt',1),self.r.bound.slot(1))
        self.assertEqual(instance.read('started',1),self.r.bound.slot(1))
        self.assertFalse((self.storage/'primary-0001.json').exists())
        for name in capture.p.inventory.FIXED_ARTIFACTS:
            if name in {'namespace.stdout','namespace.stderr'}:continue
            path=self.base/name
            if not path.exists():capture.io.exclusive(path,b'public synthetic runtime')
        group=self.base/'rollout-traces/synthetic';(group/'payloads').mkdir(parents=True)
        for name in ['manifest.json','trace.jsonl','payloads/1.json']:capture.io.exclusive(group/name,b'public synthetic rollout')
        class Process:
            pid=987654321;returncode=0
            def communicate(self,timeout=None):return b'',b''
            def poll(self):return self.returncode
        return Process()

    def run_capture(self):
        return capture.run(self.repository,self.r.bound,capture.io.encoded(self.r.deployment),self.r.sdk_manifest_raw,
            self.review_raw,self.report_raw,1)

    def summary(self):return capture.p.matrix.MatrixLedger(self.storage,self.repository,self.r.bound).summary()

    def test_single_launch_consumes_before_spawn_and_records_primary_only(self):
        result=self.run_capture();self.assertEqual(result['status'],'primary_capture_awaits_independent_review')
        self.spawn.assert_called_once();self.assertEqual(self.check.call_count,3)
        counts=self.summary();self.assertEqual((counts['primaryReserved'],counts['primaryLaunchMarked'],counts['primaryCompleted']),(1,1,1))
        self.assertEqual((counts['independentReserved'],counts['parentVerified']),(0,0));self.assertFalse(result['eligibleForMeasurement'])
        with self.assertRaises(ValueError):self.run_capture()
        self.spawn.assert_called_once()
        with self.assertRaisesRegex(ValueError,'previous review pending'):
            capture.p.matrix.MatrixLedger(self.storage,self.repository,self.r.bound).reserve(2)

    def test_bad_prelaunch_proof_or_original_report_is_rejected_before_resources_and_reservation(self):
        initial=self.report_raw
        for field,value in [('sourceCommit','f'*40),('independentContext',False),('findings',[{'priority':'P2'}]),
            ('tests',{'count':1,'exitCode':True}),('cleanAfter','dirty'),('status','not_verified')]:
            self.report_raw=capture.io.encoded(dict(self.report,**{field:value}));self.make_review()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'report incomplete'):self.run_capture()
            self.assertFalse(self.storage.exists())
        self.report_raw=initial;self.make_review();self.review_raw+=b' '
        with self.assertRaisesRegex(ValueError,'review bytes'):self.run_capture()
        self.check.assert_not_called();self.spawn.assert_not_called()

    def test_condition_has_no_review_hash_cycle_and_binds_execution_and_deployment(self):
        before=self.review['conditionSha256']
        self.assertEqual(capture.condition_sha256(self.r.bound,capture.io.encoded(self.r.deployment)),before)
        self.r.execution['timeoutSeconds']['primary']=239;self.r.bound=self.r.bind()
        self.r.deployment['executionSha256']=capture.io.sha(self.r.bound.execution_raw)
        with self.assertRaisesRegex(ValueError,'condition drift'):self.run_capture()
        self.spawn.assert_not_called();self.assertFalse(self.storage.exists())

    def test_resource_drift_after_reservation_stops_without_marking_or_spawning(self):
        self.check.side_effect=[self.proof,dict(publicSyntheticResourceProof=False)]
        result=self.run_capture();self.assertEqual(result['status'],'primary_capture_stopped');self.spawn.assert_not_called()
        counts=self.summary();self.assertEqual((counts['primaryReserved'],counts['primaryLaunchMarked'],counts['primaryCompleted']),(1,0,0))
        self.assertTrue((self.base/'receipt.json').exists());self.assertTrue((self.storage/'stop.json').exists())
        self.check.side_effect=None;self.check.return_value=self.proof
        with self.assertRaises(ValueError):self.run_capture()

    def test_spawn_failure_never_refunds_started_reservation_or_retries(self):
        self.spawn.side_effect=OSError('public synthetic failure')
        result=self.run_capture();self.assertEqual(result['status'],'primary_capture_stopped')
        self.assertEqual(result['actualNamespaceInvocations'],0);self.assertTrue(result['started']);self.spawn.assert_called_once()
        counts=self.summary();self.assertEqual((counts['primaryReserved'],counts['primaryLaunchMarked'],counts['primaryCompleted']),(1,1,0))
        receipt=capture.io.read_regular(self.base/'receipt.json')
        with self.assertRaises(ValueError):self.run_capture()
        self.assertEqual(capture.io.read_regular(self.base/'receipt.json'),receipt);self.spawn.assert_called_once()

    def test_timeout_terminates_once_and_preserves_originals_and_stop(self):
        class TimeoutProcess:
            pid=987654321;returncode=-15;calls=0
            def communicate(self,timeout):
                self.calls+=1
                if self.calls==1:raise subprocess.TimeoutExpired('public synthetic',timeout)
                return b'public partial stdout',b'public partial stderr'
            def poll(self):return self.returncode
        self.spawn.side_effect=lambda *a,**k:TimeoutProcess()
        with patch.object(capture.os,'killpg') as kill:
            result=self.run_capture();kill.assert_called_once_with(987654321,capture.signal.SIGTERM)
        self.assertTrue(result['timedOut']);self.assertEqual(result['status'],'primary_capture_stopped')
        self.assertEqual((self.base/'namespace.stdout').read_bytes(),b'public partial stdout')
        self.assertEqual(self.summary()['primaryCompleted'],0);self.spawn.assert_called_once()

    def test_native_reader_rejection_preserves_original_receipt_and_permanently_stops(self):
        reader=self.mock(capture.originals_reader,'load_provider_capture',side_effect=ValueError('public original rejected'))
        result=self.run_capture();self.assertEqual(result['status'],'primary_capture_stopped');self.assertTrue((self.base/'capture-stop.json').exists())
        before=(self.base/'receipt.json').read_bytes();self.assertEqual(self.summary()['primaryCompleted'],0)
        with self.assertRaises(ValueError):self.run_capture()
        self.assertEqual(before,(self.base/'receipt.json').read_bytes());self.verify.assert_not_called();reader.assert_called_once()

    def test_interrupt_preserves_stop_and_consumption_then_propagates(self):
        self.spawn.side_effect=KeyboardInterrupt('public synthetic interrupt')
        with self.assertRaises(KeyboardInterrupt):self.run_capture()
        self.assertTrue((self.base/'receipt.json').exists());self.assertEqual(self.summary()['primaryLaunchMarked'],1)
        with self.assertRaises(ValueError):self.run_capture()
        self.spawn.assert_called_once()

    def test_existing_attempt_directory_is_not_modified_on_creation_failure(self):
        self.base.mkdir(parents=True);sentinel=self.base/'public-existing-sentinel';sentinel.write_bytes(b'public original preserved')
        result=self.run_capture();self.assertEqual(result['status'],'primary_capture_stopped')
        self.assertEqual(list(self.base.iterdir()),[sentinel]);self.assertEqual(sentinel.read_bytes(),b'public original preserved')
        self.assertEqual(self.summary()['primaryReserved'],1);self.spawn.assert_not_called()

    def test_auth_metadata_reads_no_contents_and_rejects_link_or_hardlink(self):
        path=self.repository/'public-synthetic-auth-metadata';path.write_bytes(b'PUBLIC SYNTHETIC ONLY')
        # setUpはauth_metadataをmockしたので元関数を別名参照から使う。
        with patch.object(capture,'AUTH',path),patch.object(capture.io,'read_regular',side_effect=AssertionError('contents read')):
            AUTH_METADATA()
            os.link(path,self.repository/'public-synthetic-hardlink')
            with self.assertRaises(ValueError):AUTH_METADATA()
            (self.repository/'public-synthetic-hardlink').unlink();path.unlink();path.symlink_to('public-missing')
            with self.assertRaises(ValueError):AUTH_METADATA()

    def test_argv_has_only_one_standard_auth_mount_and_no_expected_or_git_mounts(self):
        value=capture.invocation(self.repository,self.base,self.r.bound,capture.io.encoded(self.r.deployment),1)
        argv=value['argv'];mounts=[argv[i+1] for i,x in enumerate(argv) if x=='--ro-bind'][1:]
        self.assertEqual(mounts.count('/home/hide/.codex/auth.json'),1)
        self.assertFalse(any(name.endswith(('routing.json','behavior-safety.json','sol-authorization.json')) or '/.git' in name for name in mounts))
        self.assertEqual(value['environment']['TZ'],'Asia/Tokyo');self.assertEqual(value['maximumLogicalTurns'],1)
        bad=dict(self.r.bound.slot(1),repetition=True)
        with self.assertRaises(ValueError):capture.invocation_for_slot(self.repository,self.base,self.r.bound.execution_raw,capture.io.encoded(self.r.deployment),bad)

    def test_fd_discovery_rejects_unknown_tree_before_contents_and_never_descends_opaque(self):
        self.run_capture();unknown=self.base/'public-unread-directory';unknown.mkdir()
        (unknown/'public-unread-sentinel').write_bytes(b'public fixture')
        with patch.object(capture.io,'read_regular',side_effect=AssertionError('early content read')),self.assertRaises(ValueError):
            capture.collect_originals(self.base)
        (unknown/'public-unread-sentinel').unlink();unknown.rmdir()
        opaque=self.base/'codex-home';(opaque/'public-unread-sentinel').write_bytes(b'public opaque fixture')
        names=capture.p.inventory.artifact_names(self.base,additional_artifacts=capture.originals_reader.provider.evidence.PROVIDER_ARTIFACTS)
        self.assertFalse(any('codex-home' in name for name in names))
        with patch.object(Path,'rglob',side_effect=AssertionError('path enumeration')):
            self.assertEqual(set(capture.collect_originals(self.base)),set(names))

    def test_saved_invocation_bytes_are_bound_and_environment_drift_is_rejected(self):
        d_raw=capture.io.encoded(self.r.deployment)
        originals={'deployment.json':d_raw,'invocation.json':capture.io.encoded(capture.invocation(self.repository,self.base,self.r.bound,d_raw,1))}
        context=SimpleNamespace(bound=self.r.bound,ordinal=1,originals=originals)
        with patch.object(capture.originals_reader.provider,'verify_bytes',return_value=dict(eligibleForMeasurement=False)) as byte_checker:
            result=VERIFY_LAUNCH(context,self.repository,self.repository,self.review_raw,self.report_raw)
            self.assertTrue(result['invocationArgvBytesMatched']);self.assertFalse(result['eligibleForMeasurement'])
            value=capture.trace.strict_json(originals['invocation.json']);value['environment']['CODEX_HOME']='/unknown'
            originals['invocation.json']=capture.io.encoded(value)
            with self.assertRaisesRegex(ValueError,'invocation declaration drift'):
                VERIFY_LAUNCH(context,self.repository,self.repository,self.review_raw,self.report_raw)
            self.assertEqual(byte_checker.call_count,2)

    def test_isolated_child_consumes_single_payload_schema_and_closed_sdk_options(self):
        self.base.mkdir(parents=True);(self.base/'work').mkdir()
        d_raw=capture.io.encoded(self.r.deployment)
        schema=capture.p.decision_schema(self.r.originals[capture.p.inventory.SCHEMA])
        inputs={'contract.json':self.r.bound.execution_raw,'deployment.json':d_raw,'reservation.json':capture.io.encoded(self.r.bound.slot(1)),
            'model-input.json':self.r.bound.matrix.payloads[0],'decision-schema.json':schema,'sdk-manifest.json':self.r.sdk_manifest_raw,
            'runtime-manifest.json':self.r.originals[capture.p.capture.fixed_runtime.MANIFEST],
            'launch-settings.json':capture.launch.launch_settings(self.r.bound.execution_raw,d_raw),
            'invocation.json':capture.io.encoded(capture.invocation(self.repository,self.base,self.r.bound,d_raw,1))}
        for name,raw in inputs.items():capture.io.exclusive(self.base/name,raw)
        client=Mock();client.thread_start.return_value=SimpleNamespace(thread=SimpleNamespace(id='synthetic-thread'))
        client.turn_start.return_value=SimpleNamespace(turn=SimpleNamespace(id='synthetic-turn'))
        client.next_turn_notification.return_value=SimpleNamespace(method='turn/completed')
        sdk=SimpleNamespace(__version__='0.160.1',CodexConfig=lambda **kwargs:kwargs)
        module=SimpleNamespace(CodexClient=lambda *args,**kwargs:client)
        with patch.object(capture,'ROOT',self.repository),patch.dict(sys.modules,{'openai_codex':sdk,'openai_codex.client':module}),\
             patch.object(capture.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'codex-cli 0.160.1\n',stderr=b'')):
            capture.isolated(self.base)
        thread=client.thread_start.call_args.args[0]
        self.assertEqual(thread['model'],'gpt-6.1-sol');self.assertFalse(thread['allowProviderModelFallback'])
        self.assertEqual(thread['sandbox'],'read-only');self.assertEqual(thread['approvalPolicy'],'never');self.assertTrue(thread['ephemeral'])
        turn=client.turn_start.call_args.args
        self.assertEqual(turn[1].encode(),self.r.bound.matrix.payloads[0]);self.assertEqual(turn[2]['effort'],'low')
        self.assertEqual(turn[2]['outputSchema'],capture.p.capture.execution_schema(capture.trace.strict_json(schema)))
        client.start.assert_called_once();client.turn_start.assert_called_once();client.close.assert_called_once()
        self.assertEqual(capture.trace.strict_json((self.base/'isolated-result.json').read_bytes()),{'sdkErrorType':None})


AUTH_METADATA=capture.auth_metadata
VERIFY_LAUNCH=capture.verify_launch
if __name__=='__main__':unittest.main()
