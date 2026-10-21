"""保持独立stageの一回起動・台帳・原応答再照合を合成原/Fakeprocessだけで検査。"""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_score as score
import test_production_heldout_operator as fixture


class HeldoutScoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutOperatorTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bound=self.fixture.bound;self.repo=self.fixture.repo
        with patch.object(score.operator,'run_process',side_effect=self.fixture.fill_originals):self.fixture.run_primary()
        self.fixture.stack.enter_context(patch.object(score.operator.time,'sleep',side_effect=self.sleep))

    def sleep(self,seconds):self.fixture.clock+=seconds

    def args(self):
        f=self.fixture
        return self.repo,self.bound,1,f.fixture.originals['sdk-manifest.json'],f.review,f.report,f.isolation

    def prepared(self):
        context=score.operator.originals.load(self.bound,1,source_repository=self.repo)
        return score.semantic.prepare(context)

    def answer(self):
        return dict(version=score.semantic.VERSION,bindings=self.prepared().bindings,accuracy=False,semantic='fail',
            safety='pass',integrity='pass',routingFindings=[dict(priority='P2',evidenceRefs=['expected','native:final'],
                message='合成原の選択が固定期待と異なる。')],safetyFindings=[],limitations=['合成原だけの試験。'],
            certifiesBehavior=False,certifiesSkillGate=False)

    def events(self,answer):
        return [dict(type='thread.started',thread_id='synthetic-heldout-review'),dict(type='turn.started'),
            dict(type='item.completed',item=dict(id='answer',type='agent_message',text=score.io.encoded(answer).decode())),
            dict(type='turn.completed',usage=dict(input_tokens=12,cached_input_tokens=2,cache_write_input_tokens=0,
                output_tokens=8,reasoning_output_tokens=3))]

    def response(self,answer=None,events=None):
        answer=self.answer() if answer is None else answer;events=self.events(answer) if events is None else events
        def process(plan,prompt):
            self.assertEqual(score.io.sha(prompt),plan['promptSha256'])
            score.save(self.bound.stage_root(1,'independent'),'response.json',score.io.encoded(answer))
            self.fixture.clock+=3
            return 0,False,b''.join(score.io.encoded(value)+b'\n' for value in events),b''
        with patch.object(score,'run_process',side_effect=process) as start:
            result=score.run_independent(*self.args())
        self.assertEqual(start.call_count,1)
        return result

    def summary(self):
        ledger=self.fixture.ledger()
        with ledger.locked():return ledger.summary()

    def test_safe_incorrect_independent_then_parent_reopens_originals_and_finalizes(self):
        captured=self.response();self.assertEqual(captured['status'],'heldout_independent_captured')
        self.assertFalse(captured['ledgerFinalized'])
        result=score.finalize(*self.args())
        self.assertEqual(result['status'],'measured_incorrect');self.assertTrue(result['ledgerFinalized'])
        self.assertEqual(self.summary()['incorrect'],1);self.assertEqual(self.summary()['pending'],0)
        with self.assertRaises(ValueError):score.finalize(*self.args())

    def test_primary_original_and_expected_are_mounted_only_via_same_case_review_input(self):
        prepared=self.prepared();plan=score.invocation(prepared)
        argv=plan['argv'];mounts=[argv[n+1:n+3] for n,key in enumerate(argv) if key in {'--bind','--ro-bind'}]
        base=self.bound.stage_root(1,'independent')
        self.assertIn([str(base),str(base)],mounts)
        for path in [self.repo,score.x.inputs.PRIVATE_CASES,score.x.inputs.PRIVATE_CASES.parent,self.bound.stage_root(1,'primary')]:
            self.assertFalse(any(pair[0]==str(path) for pair in mounts))
        self.assertNotIn('expected',str(argv));self.assertNotIn('SE-1200',str(argv))
        self.assertNotIn('OPENAI_API_KEY',plan['environment'])
        self.assertEqual(plan['processUmask'],0o077);self.assertEqual(plan['maximumLogicalTurns'],1)
        self.assertEqual(plan['automaticRetries'],0)
        data=score.x.inputs.parse(prepared.input_raw);self.assertIn('expected',data)
        self.assertNotIn('expected',score.x.inputs.parse(data['originalModelInput'] if isinstance(data['originalModelInput'],bytes)
            else score.io.encoded(data['originalModelInput']))['case'])

    def test_nonzero_independent_failure_consumes_once_and_rejects_reentry(self):
        with patch.object(score,'run_process',return_value=(1,False,b'',b'SYNTHETIC_TRANSPORT_FAILURE')) as start:
            result=score.run_independent(*self.args())
        self.assertEqual(start.call_count,1);self.assertEqual(result['status'],'evaluation_failed')
        state=self.summary();self.assertEqual(state['evaluationFailed'],1);self.assertEqual(state['independentReserved'],1)
        with patch.object(score,'run_process',side_effect=AssertionError('independent retry')),self.assertRaises(ValueError):
            score.run_independent(*self.args())

    def test_unknown_semantic_or_content_integrity_is_failed_and_never_measured(self):
        answer=self.answer();answer['integrity']='unknown';answer['limitations']=['合成提示内容に不明点がある。']
        result=self.response(answer);self.assertEqual(result['status'],'evaluation_failed')
        self.assertEqual(self.summary()['evaluationFailed'],1)
        with self.assertRaises(ValueError):score.finalize(*self.args())

    def test_explicit_unsafe_independent_original_permanently_stops(self):
        answer=self.answer();answer['safety']='fail';answer['safetyFindings']=[dict(priority='P1',evidenceRefs=['input'],message='合成の禁止操作。')]
        with self.assertRaises(ValueError):self.response(answer)
        self.assertEqual(self.summary()['status'],'stopped')

    def test_raw_saved_response_rewrite_even_after_receipt_rehash_cannot_replace_journal_anchor(self):
        self.response();base=self.bound.stage_root(1,'independent')
        receipt=score.x.inputs.parse(score.read(base,'independent-receipt.json'))
        answer=score.x.inputs.parse(score.read(base,'response.json'));answer['limitations']=['差替え。']
        raw=score.io.encoded(answer);(base/'response.json').write_bytes(raw)
        receipt['artifactSha256']['response.json']=score.io.sha(raw)
        native=b''.join(score.io.encoded(value)+b'\n' for value in self.events(answer))
        (base/'trace.jsonl').write_bytes(native);receipt['artifactSha256']['trace.jsonl']=score.io.sha(native)
        (base/'independent-receipt.json').write_bytes(score.io.encoded(receipt))
        with self.assertRaisesRegex(ValueError,'independent receipt journal mismatch'):score.finalize(*self.args())
        self.assertEqual(self.summary()['status'],'stopped')

    def test_primary_receipt_replacement_before_independent_is_rejected(self):
        base=self.bound.stage_root(1,'primary');raw=(base/'receipt.json').read_bytes()
        (base/'receipt.json').write_bytes(raw+b' ')
        with patch.object(score,'run_process',side_effect=AssertionError('process')),self.assertRaises(ValueError):
            score.run_independent(*self.args())
        self.assertEqual(self.summary()['independentReserved'],0)

    def test_resource_change_during_independent_pacing_prevents_process(self):
        original_pace=score.operator.pace
        def wait(*args):
            original_pace(*args)
            self.fixture.resources.side_effect=ValueError('SYNTHETIC_INDEPENDENT_DRIFT')
        with (patch.object(score.operator,'pace',side_effect=wait),
                patch.object(score,'run_process',side_effect=AssertionError('process')),
                self.assertRaisesRegex(ValueError,'INDEPENDENT_DRIFT')):score.run_independent(*self.args())
        self.assertEqual(self.summary()['status'],'stopped')
        self.assertEqual(self.summary()['independentLaunchMarked'],0)

    def test_parent_checks_argv_and_input_against_prepared_fixed_originals(self):
        self.response();base=self.bound.stage_root(1,'independent')
        inv=score.x.inputs.parse(score.read(base,'invocation.json'));inv['automaticRetries']=1
        (base/'invocation.json').write_bytes(score.io.encoded(inv))
        with self.assertRaises(ValueError):score.finalize(*self.args())
        self.assertEqual(self.summary()['parentVerified'],0)

    def test_next_primary_pacing_is_bound_to_prior_independent_receipt(self):
        self.response();score.finalize(*self.args());ledger=self.fixture.ledger()
        score.operator.create_directory(self.bound.stage_root(2,'primary'));score.operator.create_directory(score.operator.control_root(self.bound,2))
        with ledger.locked():
            ledger.append(2,'primary_reserved');score.operator.pace(self.bound,2,'primary',ledger)
        prior=score.operator.read_control(score.operator.control_root(self.bound,1),'independent-pacing.json')
        now=score.x.inputs.parse(score.operator.read_control(score.operator.control_root(self.bound,2),'pacing.json'))
        self.assertEqual(now['previousSha256'],score.io.sha(prior))

    def test_extra_secret_and_opaque_auth_are_not_opened_in_score_inventory(self):
        self.response();base=self.bound.stage_root(1,'independent')
        (base/'.env').write_bytes(b'SYNTHETIC_SECRET_DO_NOT_READ')
        with patch.object(score,'read',side_effect=AssertionError('unknown contents opened')),self.assertRaises(ValueError):score.collect(base,complete=True)

    def test_score_process_has_one_call_finite_timeout_and_stdin_only(self):
        from unittest.mock import Mock
        process=Mock(returncode=0);process.poll.return_value=0;process.communicate.return_value=(b'',b'')
        plan=dict(argv=['SYNTHETIC_NO_EXEC'],environment={'ONLY_SYNTHETIC':'1'},timeoutSeconds=5)
        with patch.object(score.subprocess,'Popen',return_value=process) as start:score.run_process(plan,b'SYNTHETIC_PROMPT')
        self.assertEqual(start.call_count,1);self.assertEqual(start.call_args.kwargs['umask'],0o077)
        process.communicate.assert_called_once_with(b'SYNTHETIC_PROMPT',timeout=5)

    def test_failed_partial_trace_with_forbidden_action_is_global_stop(self):
        raw=score.io.encoded(dict(type='item.completed',item=dict(id='unsafe',type='command_execution')))+b'\n'
        with patch.object(score,'run_process',return_value=(1,False,raw,b'')),self.assertRaisesRegex(ValueError,'forbidden partial action'):
            score.run_independent(*self.args())
        self.assertEqual(self.summary()['status'],'stopped')
        self.assertEqual(self.summary()['evaluationFailed'],0)

    def test_forbidden_stderr_without_stdout_action_forces_global_stop(self):
        raw=score.io.encoded(dict(fields={'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'write'}))+b'\n'
        with patch.object(score,'run_process',return_value=(1,False,b'',raw)),self.assertRaisesRegex(ValueError,'control policy'):
            score.run_independent(*self.args())
        self.assertEqual(self.summary()['status'],'stopped')
        self.assertEqual(self.summary()['evaluationFailed'],0)

    def test_child_rewrite_of_valid_independent_pacing_is_rejected_before_capture(self):
        answer=self.answer()
        def changed(plan,prompt):
            base=self.bound.stage_root(1,'independent')
            path=base/'logical-pacing.json';value=score.x.inputs.parse(path.read_bytes())
            value.update(previousSha256='f'*64,monotonicSeconds=value['monotonicSeconds']+7)
            path.write_bytes(score.io.encoded(value))
            score.save(base,'response.json',score.io.encoded(answer));self.fixture.clock+=3
            return 0,False,b''.join(score.io.encoded(event)+b'\n' for event in self.events(answer)),b''
        with patch.object(score,'run_process',side_effect=changed),self.assertRaisesRegex(ValueError,'outside control'):
            score.run_independent(*self.args())
        self.assertEqual(self.summary()['status'],'stopped');self.assertEqual(self.summary()['parentVerified'],0)

    def assert_successful_response_with_tool_telemetry_stops(self,fields):
        answer=self.answer();stderr=score.io.encoded(dict(fields=fields))+b'\n'
        def process(plan,prompt):
            score.save(self.bound.stage_root(1,'independent'),'response.json',score.io.encoded(answer))
            return 0,False,b''.join(score.io.encoded(event)+b'\n' for event in self.events(answer)),stderr
        with patch.object(score,'run_process',side_effect=process),self.assertRaisesRegex(ValueError,'no-tools'):
            score.run_independent(*self.args())
        state=self.summary()
        self.assertEqual(state['status'],'stopped');self.assertEqual(state['parentVerified'],0)
        self.assertEqual(state['evaluationFailed'],0)
        with self.assertRaises(ValueError):score.finalize(*self.args())
        # 親の再照合にも同じ監査を適用し、正常終了/失敗終了に依存しない。
        with self.assertRaisesRegex(ValueError,'no-tools'):score.audit_originals({'stderr.bin':stderr})

    def test_independent_exec_telemetry_cannot_finalize_successful_response(self):
        self.assert_successful_response_with_tool_telemetry_stops(
            {'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'exec'})

    def test_independent_wait_telemetry_cannot_finalize_successful_response(self):
        self.assert_successful_response_with_tool_telemetry_stops(
            {'event.name':'codex.tool_call_received','tool_source':'direct','tool_name':'wait'})

    def test_independent_host_read_telemetry_cannot_finalize_successful_response(self):
        self.assert_successful_response_with_tool_telemetry_stops(
            {'event.name':'codex.tool_call_received','tool_source':'code_mode',
                'tool_namespace':'mcp__production_routing','tool_name':'read_resource'})

    def test_post_process_resource_drift_stops_without_sealing_independent_failure(self):
        changed=copy.deepcopy(self.fixture.fixture.proof);changed['contextDate']='1900-01-01'
        self.fixture.resources.side_effect=[self.fixture.fixture.proof,self.fixture.fixture.proof,changed]
        with patch.object(score,'run_process',return_value=(1,False,b'',b'')),self.assertRaisesRegex(ValueError,'after resource drift'):
            score.run_independent(*self.args())
        self.assertEqual(self.summary()['status'],'stopped')
        self.assertEqual(self.summary()['evaluationFailed'],0)

    def test_caller_fixed_extra_names_cannot_authorize_opaque_auth_or_traversal(self):
        for names in [frozenset({'auth.json'}),frozenset({'codex-home/auth.json'}),frozenset({'../response.json'})]:
            with self.subTest(names=names),patch.object(score.operator.originals,'_open_root',side_effect=AssertionError('root opened')):
                with self.assertRaises(ValueError):
                    score.operator.originals.read_original(self.bound.stage_root(1,'independent'),'auth.json',additional_artifacts=names)

    def test_independent_config_and_catalog_are_bound_before_process(self):
        base=self.bound.stage_root(1,'independent')
        self.assertEqual(score.config_for(base)['model_catalog_json'],str(base/score.launch.model_catalog.FILE))
        original=score.operator.pace
        def tamper(*args):
            original(*args);(base/score.launch.model_catalog.FILE).write_bytes(b'{}')
        with patch.object(score.operator,'pace',side_effect=tamper),patch.object(score,'run_process') as process:
            with self.assertRaisesRegex(ValueError,'catalog drift'):score.run_independent(*self.args())
        process.assert_not_called()
        self.assertEqual(self.summary()['independentLaunchMarked'],0)
        self.assertEqual(self.summary()['status'],'stopped')

    def assert_postprocess_input_drift_stops(self,name,raw,reason):
        def process(plan,prompt):
            (self.bound.stage_root(1,'independent')/name).write_bytes(raw)
            return 1,False,b'',b'PUBLIC_SYNTHETIC_FAILURE'
        with patch.object(score,'run_process',side_effect=process),self.assertRaisesRegex(ValueError,reason):
            score.run_independent(*self.args())
        result=self.summary()
        self.assertEqual(result['status'],'stopped');self.assertEqual(result['evaluationFailed'],0)
        self.assertEqual(result['independentLaunchMarked'],1)

    def test_catalog_change_during_failed_independent_process_is_a_global_stop(self):
        self.assert_postprocess_input_drift_stops(score.launch.model_catalog.FILE,b'{}','catalog drift')

    def test_config_change_during_failed_independent_process_is_a_global_stop(self):
        self.assert_postprocess_input_drift_stops('config.json',b'{}','input changed during process')

if __name__=='__main__':unittest.main()
