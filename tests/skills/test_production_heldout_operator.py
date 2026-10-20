"""一次親の単回・予約不返却・原照合・局所失敗と恒久停止。実private/model起動0。"""
from contextlib import ExitStack
import copy
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_operator as op
import test_production_heldout_evidence as fixture
import test_production_heldout_launch as launch_fixture


class HeldoutOperatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutEvidenceTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bound=self.fixture.bound;self.repo=self.fixture.capture.repository
        self.private=op.x.inputs.PRIVATE_CASES.parent
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(op.x.ledger,'SHARED_ROOT',self.private/'measurement-ledgers/test-primary'))
        self.stack.enter_context(patch.object(op,'auth_metadata'))
        self.resources=self.stack.enter_context(patch.object(op.preflight,'verify_resources',return_value=self.fixture.proof))
        self.clock=100.0
        self.stack.enter_context(patch.object(op.time,'monotonic',side_effect=lambda:self.clock))
        d=op.x.deployment_for_execution(self.bound.execution_raw,self.bound.deployment_raw)
        manifest=self.repo/d['snapshotRelativePath']/'manifest.json'
        manifest.parent.mkdir(parents=True);manifest.write_bytes(self.fixture.manifest)
        self.review,self.report,self.isolation=launch_fixture.review_bytes(self.bound)

    def ledger(self):return op.x.ledger.open_shared(self.bound.ledger_contract(op.io.encoded(self.fixture.proof)))

    def run_primary(self,ordinal=1):
        return op.run_primary(self.repo,self.bound,ordinal,self.fixture.originals['sdk-manifest.json'],
            self.review,self.report,self.isolation)

    def fill_originals(self,plan):
        base=self.bound.stage_root(plan['primaryIdentity']['ordinal'],'primary')
        for name,raw in self.fixture.originals.items():
            if name in {'namespace.stdout','namespace.stderr','resource-guards.json','logical-pacing.json'}:continue
            path=base/name
            if path.exists():self.assertEqual(path.read_bytes(),raw)
            else:
                path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.write_bytes(raw);path.chmod(0o600)
        self.clock+=3
        return 0,False,b'',b''

    def test_success_real_native_original_loader_then_primary_captured_without_finalizing(self):
        with patch.object(op,'run_process',side_effect=self.fill_originals) as process:
            result=self.run_primary()
        self.assertEqual(process.call_count,1)
        self.assertEqual(result['status'],'heldout_primary_captured_awaits_independent')
        self.assertFalse(result['eligibleForMeasurement'])
        ledger=self.ledger()
        with ledger.locked():
            rows,_=ledger._history();self.assertEqual([row['stage'] for row in rows],
                ['primary_reserved','primary_started','primary_captured'])
            self.assertEqual(ledger.summary()['primaryLaunchMarked'],1)
        self.assertNotIn('expected',op.x.inputs.parse((self.bound.stage_root(1,'primary')/'model-input.json').read_bytes())['case'])

    def test_nonzero_failure_seals_unchanged_guards_and_consumes_slot_without_retry(self):
        with patch.object(op,'run_process',return_value=(1,False,b'',b'SYNTHETIC_CLI_FAILURE')) as process:
            result=self.run_primary()
        self.assertEqual(process.call_count,1);self.assertEqual(result['status'],'evaluation_failed')
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['evaluationFailed'],1)
            self.assertEqual(ledger.summary()['pending'],0)
        with patch.object(op,'run_process',side_effect=AssertionError('retry')),self.assertRaises(ValueError):self.run_primary()

    def test_zero_namespace_exit_with_sdk_error_is_failed_without_claiming_normal_capture(self):
        def sdk_error(plan):
            op.save(self.bound.stage_root(1,'primary'),'isolated-result.json',op.io.encoded(dict(sdkErrorType='RuntimeError')))
            return 0,False,b'',b''
        with patch.object(op,'run_process',side_effect=sdk_error):result=self.run_primary()
        self.assertEqual(result['status'],'evaluation_failed')

    def test_resource_drift_after_launch_permanently_stops_instead_of_local_failure(self):
        changed=copy.deepcopy(self.fixture.proof);changed['contextDate']='1900-01-01'
        self.resources.side_effect=[self.fixture.proof,self.fixture.proof,changed]
        with patch.object(op,'run_process',return_value=(1,False,b'',b'')),self.assertRaises(ValueError):self.run_primary()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['status'],'stopped');self.assertEqual(ledger.summary()['evaluationFailed'],0)

    def test_known_unsafe_stop_and_unknown_secret_are_rejected_without_reading_contents(self):
        for name in ['capture-stop.json','.env']:
            with self.subTest(name=name):
                base=self.private/('partial-'+name.replace('.','-'));op.create_directory(base)
                (base/name).write_bytes(b'SYNTHETIC_DO_NOT_READ')
                with (patch.object(op.originals,'read_original',side_effect=AssertionError('unsafe contents opened')),
                        self.assertRaises(ValueError)):op.collect_partial(base)

    def test_unknown_file_from_failed_process_forces_durable_global_stop(self):
        def unsafe(plan):
            (self.bound.stage_root(1,'primary')/'capture-stop.json').write_bytes(b'SYNTHETIC_STOP')
            return 1,False,b'',b''
        with patch.object(op,'run_process',side_effect=unsafe),self.assertRaises(ValueError):self.run_primary()
        ledger=self.ledger()
        with ledger.locked():self.assertEqual(ledger.summary()['status'],'stopped')

    def test_forbidden_complete_action_in_failed_partial_rpc_forces_global_stop_without_marker(self):
        def forbidden(plan):
            raw=op.io.encoded(dict(method='item/started',params=dict(item=dict(type='commandExecution'))))+b'\n'
            op.save(self.bound.stage_root(1,'primary'),'rpc-out.jsonl',raw)
            return 1,False,b'',b''
        with patch.object(op,'run_process',side_effect=forbidden),self.assertRaisesRegex(ValueError,'unknown action'):
            self.run_primary()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['status'],'stopped');self.assertEqual(ledger.summary()['evaluationFailed'],0)

    def test_truncated_last_rpc_line_remains_evaluation_failure_without_normal_or_safety_claim(self):
        def truncated(plan):
            op.save(self.bound.stage_root(1,'primary'),'rpc-out.jsonl',b'{"method":"item/star')
            return 1,False,b'',b''
        with patch.object(op,'run_process',side_effect=truncated):result=self.run_primary()
        self.assertEqual(result['status'],'evaluation_failed')
        self.assertFalse(result['eligibleForMeasurement'])

    def test_forbidden_tool_in_raw_stderr_without_selected_log_forces_global_stop(self):
        def forbidden(plan):
            raw=op.io.encoded(dict(fields={'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'write'}))+b'\n'
            op.save(self.bound.stage_root(1,'primary'),'runtime-stderr.bin',raw)
            return 1,False,b'',b''
        with patch.object(op,'run_process',side_effect=forbidden),self.assertRaisesRegex(ValueError,'control policy'):
            self.run_primary()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['status'],'stopped');self.assertEqual(ledger.summary()['evaluationFailed'],0)

    def test_partial_raw_diagnostics_are_not_normal_native_claims_and_duplicate_sources_do_not_double_count(self):
        raw=b''.join(op.io.encoded(dict(fields={'event.name':'codex.tool_call_received','tool_source':'direct',
            'tool_name':tool}))+b'\n' for tool in ['exec','wait'])
        op.audit_partial({'trace-safe.jsonl':raw,'runtime-stderr.bin':b'SYNTHETIC_DIAGNOSTIC\n'+raw+b'{"incomplete'})
        forbidden=op.io.encoded(dict(fields={'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'write'}))+b'\n'
        with self.assertRaisesRegex(ValueError,'control policy'):op.audit_partial({'namespace.stderr':forbidden})

    def test_partial_telemetry_unknown_tool_source_and_retry_are_rejected(self):
        faults=[dict(event='ignored',**{'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'write'}),
            {'event.name':'codex.tool_call_received','tool_source':'unknown','tool_name':'read_resource'},
            {'event.name':'codex.api_request','endpoint':'/responses','attempt':1}]
        for fields in faults:
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                op.audit_partial({'trace-safe.jsonl':op.io.encoded(dict(fields=fields))+b'\n'})

    def test_resource_proof_is_rechecked_after_logical_pacing_before_process(self):
        drift=False
        original_pace=op.pace
        def pacing(*args):
            nonlocal drift
            original_pace(*args)
            drift=True
        def resources(*args):
            if drift:raise ValueError('SYNTHETIC_DRIFT_DURING_WAIT')
            return self.fixture.proof
        self.resources.side_effect=resources
        with (patch.object(op,'pace',side_effect=pacing),
                patch.object(op,'run_process',side_effect=AssertionError('process invoked after drift')),
                self.assertRaisesRegex(ValueError,'DRIFT_DURING_WAIT')):self.run_primary()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['primaryLaunchMarked'],0)
            self.assertEqual(ledger.summary()['status'],'stopped')

    def test_child_cannot_change_primary_pacing_before_receipt_is_sealed(self):
        def changed(plan):
            result=self.fill_originals(plan)
            path=self.bound.stage_root(1,'primary')/'logical-pacing.json'
            value=op.x.inputs.parse(path.read_bytes());value['wallSeconds']+=1
            path.write_bytes(op.io.encoded(value))
            return result
        with patch.object(op,'run_process',side_effect=changed),self.assertRaisesRegex(ValueError,'outside control'):
            self.run_primary()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['status'],'stopped');self.assertEqual(ledger.summary()['evaluationFailed'],0)

    def test_prelaunch_rejection_precedes_private_storage_and_reservation(self):
        self.review=op.io.encoded(dict(version='wrong'))
        with (patch.object(op.x.ledger,'open_shared',side_effect=AssertionError('private ledger opened')),
                self.assertRaises(ValueError)):self.run_primary()
        self.assertFalse(self.private.exists())

    def test_new_stage_exclusive_and_owner_only_storage_without_overwrite(self):
        base=self.private/'storage';op.create_directory(base)
        op.save(base,'contract.json',b'SYNTHETIC_ORIGINAL')
        with self.assertRaises(FileExistsError):op.save(base,'contract.json',b'SYNTHETIC_OVERWRITE')
        self.assertEqual((base/'contract.json').read_bytes(),b'SYNTHETIC_ORIGINAL')
        self.assertEqual(base.stat().st_mode & 0o777,0o700)
        self.assertEqual((base/'contract.json').stat().st_mode & 0o777,0o600)
        base.chmod(0o755)
        with self.assertRaises(ValueError):op.save(base,'receipt.json',b'{}')

    def test_opaque_auth_sentinel_never_read_in_partial_failure_collection(self):
        base=self.private/'partial';op.create_directory(base/'codex-home')
        (base/'codex-home/auth.json').write_bytes(b'SYNTHETIC_AUTH_DO_NOT_READ')
        op.save(base,'namespace.stdout',b'')
        opening=os.open
        def guarded(name,*args,**kw):
            self.assertNotEqual(str(name),'auth.json');return opening(name,*args,**kw)
        with patch.object(os,'open',side_effect=guarded):result=op.collect_partial(base)
        self.assertEqual(result,{'namespace.stdout':b''})

    def test_logical_pacing_uses_durable_previous_launch_and_blocks_clock_reversal(self):
        ledger=self.ledger()
        for ordinal in [1,2]:
            op.create_directory(op.control_root(self.bound,ordinal));op.create_directory(self.bound.stage_root(ordinal,'primary'))
        with ledger.locked():
            ledger.append(1,'primary_reserved');op.pace(self.bound,1,'primary',ledger);ledger.append(1,'primary_started')
            pace_raw=op.read_control(op.control_root(self.bound,1),'pacing.json')
            raw=op.io.encoded(dict(artifactSha256={'logical-pacing.json':op.io.sha(pace_raw)}))
            op.save(self.bound.stage_root(1,'primary'),'receipt.json',raw)
            ledger.append(1,'primary_failed',op.io.sha(raw),resource_proof_sha256=op.io.sha(op.io.encoded(self.fixture.proof)))
            ledger.append(2,'primary_reserved');self.clock=99
            with self.assertRaisesRegex(ValueError,'clock drift'):op.pace(self.bound,2,'primary',ledger)
            self.clock=130
            def sleep(seconds):self.clock+=seconds
            with patch.object(op.time,'sleep',side_effect=sleep) as pause:op.pace(self.bound,2,'primary',ledger)
            pause.assert_called_once_with(30)
            prior=op.read_control(op.control_root(self.bound,1),'pacing.json')
            now=op.x.inputs.parse(op.read_control(op.control_root(self.bound,2),'pacing.json'))
            self.assertEqual(now['previousSha256'],op.io.sha(prior));self.assertFalse(now['declaresProviderInvoked'])

    def test_process_is_single_and_owner_only_with_finite_timeout_and_no_inherited_environment(self):
        process=Mock(returncode=1);process.communicate.return_value=(b'',b'');process.poll.return_value=1
        plan=dict(argv=['SYNTHETIC_NO_EXEC'],environment={'ONLY_SYNTHETIC':'1'},timeoutSeconds=7)
        with patch.object(op.subprocess,'Popen',return_value=process) as start:self.assertEqual(op.run_process(plan),(1,False,b'',b''))
        self.assertEqual(start.call_count,1);self.assertEqual(start.call_args.kwargs['umask'],0o077)
        self.assertEqual(start.call_args.kwargs['env'],{'ONLY_SYNTHETIC':'1'})
        process.communicate.assert_called_once_with(timeout=7)

    def test_source_or_resource_failure_precedes_private_read_or_reservation(self):
        self.resources.side_effect=ValueError('SYNTHETIC_SOURCE_DRIFT')
        with (patch.object(op.x.ledger,'open_shared',side_effect=AssertionError('ledger opened')),
                patch.object(op,'run_process',side_effect=AssertionError('process started')),
                self.assertRaises(ValueError)):self.run_primary()
        self.assertFalse(self.private.exists())

    def test_rehashed_pacing_control_cannot_replace_journal_anchored_original(self):
        ledger=self.ledger()
        for ordinal in [1,2]:
            op.create_directory(op.control_root(self.bound,ordinal));op.create_directory(self.bound.stage_root(ordinal,'primary'))
        with ledger.locked():
            ledger.append(1,'primary_reserved');op.pace(self.bound,1,'primary',ledger);ledger.append(1,'primary_started')
            pacing=op.read_control(op.control_root(self.bound,1),'pacing.json')
            raw=op.io.encoded(dict(artifactSha256={'logical-pacing.json':op.io.sha(pacing)}))
            op.save(self.bound.stage_root(1,'primary'),'receipt.json',raw)
            ledger.append(1,'primary_failed',op.io.sha(raw),resource_proof_sha256=op.io.sha(op.io.encoded(self.fixture.proof)))
            ledger.append(2,'primary_reserved');self.clock=200
            forged=op.x.inputs.parse(pacing);forged['monotonicSeconds']=0
            (op.control_root(self.bound,1)/'pacing.json').write_bytes(op.io.encoded(forged))
            with self.assertRaisesRegex(ValueError,'pacing receipt binding'):op.pace(self.bound,2,'primary',ledger)

    def test_control_directory_mode_change_during_write_is_rejected(self):
        base=self.private/'write-drift';op.create_directory(base)
        syncing=op.os.fsync
        def drift(fd):
            syncing(fd)
            base.chmod(0o755)
        with patch.object(op.os,'fsync',side_effect=drift),self.assertRaises(ValueError):op.save(base,'contract.json',b'{}')

    def test_process_timeout_kills_group_without_starting_a_second_process(self):
        process=Mock(returncode=-9,pid=123);process.poll.return_value=-9
        process.communicate.side_effect=[subprocess.TimeoutExpired('synthetic',1),subprocess.TimeoutExpired('synthetic',3),(b'',b'')]
        plan=dict(argv=['SYNTHETIC_NO_EXEC'],environment={},timeoutSeconds=1)
        with patch.object(op.subprocess,'Popen',return_value=process) as start,patch.object(op.os,'killpg') as kill:
            result=op.run_process(plan)
        self.assertTrue(result[1]);self.assertEqual(start.call_count,1);self.assertEqual(kill.call_count,2)

    def test_catalog_change_before_process_stops_without_marking_launch(self):
        original=op.pace
        def tamper(*args):
            original(*args)
            (self.bound.stage_root(1,'primary')/op.launch.model_catalog.FILE).write_bytes(b'{}')
        with patch.object(op,'pace',side_effect=tamper),patch.object(op,'run_process') as process:
            with self.assertRaisesRegex(ValueError,'catalog drift'):self.run_primary()
        process.assert_not_called()
        ledger=self.ledger()
        with ledger.locked():
            self.assertEqual(ledger.summary()['primaryLaunchMarked'],0)
            self.assertEqual(ledger.summary()['status'],'stopped')

if __name__=='__main__':unittest.main()
