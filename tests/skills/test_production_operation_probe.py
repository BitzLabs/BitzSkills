"""操作診断の原通信・隔離mount・有限条件を検査する。実モデルは使わない。"""
import json
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_operation_probe as probe


class ProductionOperationProbeTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / probe.CONTRACT).read_bytes())
        self.base = ROOT / '.venv' / 'operation-test'

    def test_yielded_policy_has_one_scenario_three_local_requests_and_no_paid_model(self):
        contract = json.loads((ROOT / 'evals/skills/routing/production-operation-probe-v0.9.json').read_bytes())
        self.assertIs(probe.raw_events_enabled(contract), True)
        self.assertIs(probe.thread_params(self.base, contract)['experimentalRawEvents'], True)
        for field, value in [('maximumLocalHttpRequestsPerScenario', 2),
                             ('maximumLocalHttpRequestsPerScenario', 4),
                             ('maximumLocalHttpRequestsPerScenario', True),
                             ('maximumScenarios', 2), ('paidModelCalls', 1),
                             ('outputLabels', {'read': 'x'})]:
            bad = copy.deepcopy(contract)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                probe.raw_events_enabled(bad)

    def test_yielded_read_lists_before_yield_and_reads_after_bounded_promise(self):
        code = probe.program('yielded-read', self.base)
        self.assertLess(code.index('const listed='), code.index('await yield_control()'))
        self.assertLess(code.index('await yield_control()'), code.index('setTimeout(resolve,200)'))
        self.assertLess(code.index('setTimeout(resolve,200)'), code.index('const read='))
        self.assertIn('await new Promise', code)
        self.assertNotIn('expected', code)

    def test_wait_reply_requires_first_yielded_marker_and_preserves_input(self):
        request = {'input': [{'type': 'custom_tool_call_output', 'call_id': 'probe-call',
                             'output': [{'type': 'input_text', 'text': 'Script running with cell ID 1\nOutput:\n'},
                                        {'type': 'input_text', 'text': '{"kind":"yielded-read","stage":"listed"}'}]}]}
        before = copy.deepcopy(request)
        events = [json.loads(l[6:]) for l in probe.wait_reply(request).decode().splitlines()
                  if l.startswith('data: ')]
        item = events[1]['item']
        self.assertEqual((item['type'], item['namespace'], item['name'], item['call_id']),
                         ('function_call', 'functions', 'wait', 'probe-wait'))
        self.assertEqual(json.loads(item['arguments']), {'cell_id': '1', 'yield_time_ms': 10000, 'max_tokens': 10000})
        self.assertEqual(request, before)
        for text in ['Script completed\n', 'prefix Script running with cell ID 1\n',
                     'Script running with cell ID 2\n']:
            bad = copy.deepcopy(request)
            bad['input'][0]['output'][0]['text'] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                probe.wait_reply(bad)
        for items in [[], request['input'] * 2]:
            with self.subTest(items=items), self.assertRaises(ValueError):
                probe.wait_reply({'input': items})

    def test_wait_output_objects_are_bound_to_followup_call(self):
        request = {'input': [{'type': 'function_call_output', 'call_id': 'probe-wait',
                             'output': 'Script completed\n{"kind":"yielded-read","stage":"read"}'}]}
        self.assertEqual(probe.output_objects(request), [])
        self.assertEqual(probe.output_objects(request, 'probe-wait'), [{'kind': 'yielded-read', 'stage': 'read'}])
        self.assertTrue(probe.yielded_output(request, 'probe-wait').startswith('Script completed\n'))

    @staticmethod
    def yielded_fixture():
        host = [{'tool': tool, 'accepted': True, 'result': {'value': i}} for i, tool in
                enumerate(('list_resources', 'read_resource'))]
        outputs = []
        for stage, header, event in zip(('listed', 'read'),
                ('Script running with cell ID 1\n', 'Script completed\n'), host):
            payload = {'kind': 'yielded-read', 'stage': stage, stage: {
                'isError': False, 'content': [{'type': 'text', 'text': json.dumps(event['result'])}]}}
            outputs.append(header + json.dumps(payload))
        initial = {'type': 'message', 'content': 'initial'}
        call = {'type': 'custom_tool_call', 'call_id': 'probe-call'}
        result = {'type': 'custom_tool_call_output', 'call_id': 'probe-call', 'output': outputs[0]}
        wait = {'type': 'function_call', 'call_id': 'probe-wait'}
        ended = {'type': 'function_call_output', 'call_id': 'probe-wait', 'output': outputs[1]}
        return [{'input': [initial]}, {'input': [initial, call, result]},
                {'input': [copy.deepcopy(initial), copy.deepcopy(call), copy.deepcopy(result), wait, ended]}], host

    def test_yielded_observation_binds_original_stages_and_host_bodies_without_mutation(self):
        requests, host = self.yielded_fixture()
        before = copy.deepcopy((requests, host))
        objects, observation = probe.yielded_observation(requests, host)
        self.assertEqual([o['stage'] for o in objects], ['listed', 'read'])
        self.assertEqual(observation, {'cellId': '1', 'waitCompleted': True, 'stages': ['listed', 'read']})
        self.assertEqual((requests, host), before)

    def test_yielded_observation_rejects_reposted_fabrication_from_independent_review(self):
        requests, host = self.yielded_fixture()
        requests[1]['input'][-1]['output'] = 'Script running with cell ID 1\n'
        requests[2]['input'][2]['output'] = '{"kind":"other","stage":"listed"}'
        requests[2]['input'][-1]['output'] = 'Script completed\n{"kind":"other","stage":"read"}'
        with self.assertRaises(ValueError):
            probe.yielded_observation(requests, host)

    def test_yielded_observation_rejects_missing_extra_wrong_or_unbound_payload(self):
        for stage in (0, 1):
            for mode in ('missing', 'duplicate', 'kind', 'stage', 'body', 'error', 'type-drift',
                         'duplicate-key', 'nan', 'wrapper', 'host-tool', 'host-unaccepted'):
                requests, host = self.yielded_fixture()
                frame = requests[stage+1]['input'][-1]
                header, text = frame['output'].split('\n', 1)
                payload = json.loads(text)
                key = ('listed', 'read')[stage]
                if mode == 'missing': text = ''
                elif mode == 'duplicate': text += '\n' + text
                elif mode in ('kind', 'stage'): payload[mode] = 'other'
                elif mode == 'body': payload.pop(key)
                elif mode == 'error': payload[key]['isError'] = True
                elif mode == 'type-drift': payload[key]['content'][0]['text'] = '{"value":false}'
                elif mode == 'duplicate-key': text = text.replace('"kind":', '"kind":"wrong","kind":')
                elif mode == 'nan': payload[key]['content'][0]['text'] = '{"value":NaN}'
                elif mode == 'wrapper': payload[key]['content'] = []
                elif mode == 'host-tool': host[stage]['tool'] = 'wrong'
                elif mode == 'host-unaccepted': host[stage]['accepted'] = False
                if mode not in ('missing', 'duplicate', 'duplicate-key'):
                    text = json.dumps(payload)
                frame['output'] = header + '\n' + text
                if stage == 0:
                    requests[2]['input'][2] = copy.deepcopy(frame)
                with self.subTest(stage=stage, mode=mode), self.assertRaises(ValueError):
                    probe.yielded_observation(requests, host)

    def test_yielded_observation_rejects_changed_history_and_incomplete_wait(self):
        for mode in ('history', 'wait', 'requests', 'hosts'):
            requests, host = self.yielded_fixture()
            if mode == 'history': requests[2]['input'][0]['content'] = 'modified'
            elif mode == 'wait': requests[2]['input'][-1]['output'] = 'Script running with cell ID 1\n'
            elif mode == 'requests': requests.pop()
            else: host.pop()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                probe.yielded_observation(requests, host)

    def test_raw_event_policy_preserves_read_only_finite_thread_settings(self):
        contract = json.loads((ROOT / 'evals/skills/routing/production-operation-probe-v0.8.json').read_bytes())
        original = copy.deepcopy(contract)
        params = probe.thread_params(self.base, contract)
        self.assertIs(params['experimentalRawEvents'], True)
        self.assertIs(params['allowProviderModelFallback'], False)
        self.assertEqual(params['sandbox'], 'read-only')
        self.assertEqual(params['approvalPolicy'], 'never')
        self.assertIs(params['ephemeral'], True)
        self.assertEqual(contract, original)
        self.assertNotIn('experimentalRawEvents', probe.thread_params(self.base, self.contract))
        for field, value in (('experimentalRawEvents', False), ('experimentalRawEvents', 1),
                             ('maximumScenarios', 2), ('maximumScenarios', True),
                             ('maximumLocalHttpRequestsPerScenario', 3), ('maximumLocalHttpRequestsPerScenario', 2.0),
                             ('paidModelCalls', 1), ('paidModelCalls', False), ('outputLabels', {'read': 'x', 'inventory': 'y'})):
            bad = copy.deepcopy(contract)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'unknown raw event policy'):
                probe.thread_params(self.base, bad)

    def test_terminal_matches_requires_started_scope_success_and_final_before_completion(self):
        frames = [{'method': 'item/completed', 'params': {'threadId': 'thread', 'turnId': 'turn',
                   'item': {'type': 'agentMessage', 'phase': 'final_answer', 'text': 'LOCAL_SIMULATION_ONLY'}}},
                  {'method': 'turn/completed', 'params': {'threadId': 'thread',
                   'turn': {'id': 'turn', 'status': 'completed', 'error': None}}}]
        before = copy.deepcopy(frames)
        self.assertEqual(probe.terminal_matches(frames, 'thread', 'turn'), (True, True))
        for field, value in [('final-thread', 'other'), ('final-turn', 'other'), ('end-thread', 'other'),
                             ('end-turn', 'other'), ('error', {'message': 'failed'}), ('error', False),
                             ('status', 'failed'), ('reverse', None), ('missing-final', None),
                             ('duplicate-end', None), ('malformed-end', None), ('text', 'wrong')]:
            bad = copy.deepcopy(frames)
            if field == 'reverse':
                bad.reverse()
            elif field == 'missing-final':
                bad.pop(0)
            elif field == 'duplicate-end':
                bad.append(copy.deepcopy(bad[-1]))
            elif field == 'malformed-end':
                bad[-1]['params'] = None
            elif field.startswith('final-'):
                bad[0]['params']['threadId' if field == 'final-thread' else 'turnId'] = value
            elif field == 'end-thread':
                bad[-1]['params']['threadId'] = value
            elif field == 'text':
                bad[0]['params']['item']['text'] = value
            else:
                bad[-1]['params']['turn']['id' if field == 'end-turn' else field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(probe.terminal_matches(bad, 'thread', 'turn'), (False, False))
        for thread_id, turn_id in [(None, 'turn'), ('thread', None), ('', 'turn'), ('thread', True)]:
            self.assertEqual(probe.terminal_matches(frames, thread_id, turn_id), (False, False))
        self.assertEqual(frames, before)

    def test_sdk_notification_stream_is_one_complete_json_object_per_line(self):
        records = [{'method': 'rawResponseItem/completed', 'params': {'item': {'text': '日本語\n複数行'}}},
                   {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}]
        raw = b''.join(probe.notification_line(n) for n in records)
        self.assertEqual(len(raw.splitlines()), len(records))
        self.assertEqual([json.loads(line) for line in raw.splitlines()], records)
        with self.assertRaises(ValueError):
            probe.notification_line({'value': float('nan')})

    def test_sdk_unknown_raw_notifications_are_copied_without_mutating_payload(self):
        params = {'threadId': 'thread', 'turnId': 'turn', 'item': {'type': 'custom_tool_call', 'input': 'raw program'}}
        notification = SimpleNamespace(method='rawResponseItem/completed', payload=SimpleNamespace(params=params))
        result = probe.sdk_notification_record(notification)
        self.assertEqual(result, {'method': notification.method, 'params': params})
        result['params']['item']['input'] = 'changed'
        self.assertEqual(params['item']['input'], 'raw program')
        with self.assertRaises(ValueError):
            probe.sdk_notification_record(SimpleNamespace(method='', payload=SimpleNamespace(params=params)))

    @staticmethod
    def raw_verifier():
        path = ROOT / 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py'
        spec = importlib.util.spec_from_file_location('raw_fixture_verifier', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_raw_rpc_and_sdk_payload_mismatches_are_rejected_without_mutation(self):
        verifier = self.raw_verifier()
        methods = [verifier.METHODS[0]] * 4 + [verifier.METHODS[1]] + [verifier.METHODS[0]] * 2 + [verifier.METHODS[1]]
        original = [{'method': method, 'params': {'value': i, 'text': '通知'}, 'emittedAtMs': 1}
                    for i, method in enumerate(methods)]
        side = [{'method': f['method'], 'params': copy.deepcopy(f['params'])} for f in original]
        before = copy.deepcopy(original)
        self.assertEqual(verifier.raw_values(original, side), original)
        self.assertEqual(original, before)
        for mode in ('missing', 'type-drift', 'reversed'):
            bad = copy.deepcopy(side)
            if mode == 'missing':
                bad.pop()
            elif mode == 'type-drift':
                bad[1]['params']['value'] = True
            else:
                bad.reverse()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'RPC/SDK raw notification payload mismatch'):
                verifier.raw_values(original, bad)
        bad = copy.deepcopy(original)
        bad[0]['emittedAtMs'] = True
        with self.assertRaisesRegex(ValueError, 'raw event timestamp'):
            verifier.raw_values(bad, side)

    @staticmethod
    def terminal_fixture():
        value = {'status': 'operation_diagnostic_captured', 'namespaceExitCode': 0,
                 'runtime': {'exitCode': 0, 'forcedShutdown': False},
                 'localHttpRequestCount': 2, 'hostEventCount': 2, 'paidModelCalls': 0,
                 'eligibleForMeasurement': False, 'experimentalRawEventsRequested': True,
                 'localErrors': [], 'sdkErrorType': None, 'serverRequestStops': [],
                 'prohibitedFileExists': False, 'isolationChecks': {'repo': True},
                 'mockTurnCompleted': True, 'mockFinalMatched': True}
        turn = {'id': 'turn', 'status': 'inProgress', 'items': [], 'error': None}
        incoming = [{'id': 2, 'method': 'thread/start', 'params': {}},
                    {'id': 3, 'method': 'turn/start', 'params': {'threadId': 'thread'}}]
        outgoing = [{'id': 2, 'result': {'thread': {'id': 'thread', 'ephemeral': True, 'turns': []}}},
                    {'id': 3, 'result': {'turn': copy.deepcopy(turn)}},
                    {'method': 'turn/started', 'params': {'threadId': 'thread', 'turn': turn}},
                    {'method': 'item/completed', 'params': {'threadId': 'thread', 'turnId': 'turn',
                     'item': {'type': 'agentMessage', 'phase': 'final_answer', 'text': 'LOCAL_SIMULATION_ONLY'}}},
                    {'method': 'turn/completed', 'params': {'threadId': 'thread',
                     'turn': {'id': 'turn', 'status': 'completed', 'error': None}}}]
        return value, incoming, outgoing

    def test_capture_verifier_requires_true_success_flags_even_with_captured_status(self):
        verifier = self.raw_verifier()
        value, incoming, outgoing = self.terminal_fixture()
        for field in ['mockTurnCompleted', 'mockFinalMatched']:
            for invalid in [False, 1, None, 'true']:
                bad = copy.deepcopy(value)
                bad[field] = invalid
                with self.subTest(field=field, value=invalid), \
                     patch.object(verifier.helper, 'receipt', return_value=(bad, 'digest')), \
                     patch.object(verifier.helper, 'frames', side_effect=[incoming, outgoing]), \
                     self.assertRaisesRegex(ValueError, 'capture success flags'):
                    verifier.check_capture(self.base, 'digest')

    def test_capture_terminal_recomputes_rpc_bindings_and_order_without_mutation(self):
        verifier = self.raw_verifier()
        value, incoming, outgoing = self.terminal_fixture()
        before = copy.deepcopy((value, incoming, outgoing))
        self.assertEqual(verifier.check_terminal(value, incoming, outgoing), ('thread', 'turn'))
        for mode in ['foreign-thread', 'foreign-turn', 'failed', 'error', 'reverse', 'missing-reply',
                     'duplicate-reply', 'bool-request-id', 'same-request-id', 'wrong-request-thread',
                     'wrong-started-turn', 'early-final', 'failed-start', 'started-error']:
            sent, received = copy.deepcopy((incoming, outgoing))
            if mode == 'foreign-thread':
                received[-1]['params']['threadId'] = 'other'
            elif mode == 'foreign-turn':
                received[-1]['params']['turn']['id'] = 'other'
            elif mode in ['failed', 'error']:
                received[-1]['params']['turn']['status' if mode == 'failed' else 'error'] = (
                    'failed' if mode == 'failed' else {'message': 'failed'})
            elif mode == 'reverse':
                received[-2:] = list(reversed(received[-2:]))
            elif mode == 'missing-reply':
                received.pop(1)
            elif mode == 'duplicate-reply':
                received.append(copy.deepcopy(received[1]))
            elif mode == 'bool-request-id':
                sent[1]['id'] = True
            elif mode == 'same-request-id':
                sent[1]['id'] = sent[0]['id']
            elif mode == 'wrong-request-thread':
                sent[1]['params']['threadId'] = 'other'
            elif mode == 'wrong-started-turn':
                received[2]['params']['turn']['id'] = 'other'
            elif mode == 'early-final':
                received[2:4] = list(reversed(received[2:4]))
            elif mode == 'failed-start':
                received[1]['result']['turn']['status'] = 'failed'
            else:
                received[2]['params']['turn']['error'] = {'message': 'failed'}
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verifier.check_terminal(value, sent, received)
        self.assertEqual((value, incoming, outgoing), before)

    def test_capture_verifier_checks_rpc_terminal_even_when_receipt_success_flags_are_true(self):
        verifier = self.raw_verifier()
        value, incoming, outgoing = self.terminal_fixture()
        outgoing[-1]['params']['turn']['error'] = {'message': 'failed'}
        with patch.object(verifier.helper, 'receipt', return_value=(value, 'digest')), \
             patch.object(verifier.helper, 'frames', side_effect=[incoming, outgoing]), \
             self.assertRaisesRegex(ValueError, 'capture final and completion correlation'):
            verifier.check_capture(self.base, 'digest')

    def test_legacy_pretty_stream_is_read_without_claiming_jsonl_or_rewriting(self):
        verifier = self.raw_verifier()
        values = [{'method': 'rawResponseItem/completed', 'params': {'text': '日本語\n行'}},
                  {'method': 'turn/completed', 'params': {}}]
        raw = b'\n'.join(json.dumps(v, ensure_ascii=False, indent=2).encode() for v in values)
        before = bytes(raw)
        self.assertEqual(verifier.legacy_sdk_records(raw), values)
        self.assertEqual(raw, before)
        for malformed in (b'{"x":1,"x":2}', b'{"x":NaN}', raw + b'garbage'):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                verifier.legacy_sdk_records(malformed)

    def test_only_required_files_and_snapshot_are_bound_back(self):
        args = probe.namespace(self.base, self.contract)
        mounts = [args[i + 1:i + 3] for i, arg in enumerate(args) if arg == '--ro-bind']
        self.assertNotIn([str(ROOT), str(ROOT)], mounts)
        self.assertIn(['/home',], [[args[i+1]] for i,arg in enumerate(args) if arg=='--tmpfs'])
        self.assertIn([str(ROOT / self.contract['snapshotRelativePath'])] * 2, mounts)
        self.assertEqual(args.count('--bind'), 1)
        self.assertIn('--unshare-net', args)
        self.assertNotIn(str(ROOT / '.spec'), args)
        self.assertNotIn(str(ROOT / 'tests'), args)

    def test_tool_reply_is_a_real_custom_call_and_not_an_assistant_claim(self):
        events = [json.loads(line[6:]) for line in probe.tool_reply('inventory', self.base).decode().splitlines() if line.startswith('data: ')]
        item = events[1]['item']
        self.assertEqual(item['type'], 'custom_tool_call')
        self.assertEqual(item['name'], 'exec')
        self.assertEqual(item['namespace'], 'functions')
        self.assertIn('ALL_TOOLS', item['input'])

    def test_read_script_uses_discovery_before_selected_body(self):
        code = probe.program('read', self.base)
        self.assertLess(code.index('__list_resources'), code.index('__read_resource'))
        self.assertIn('sdd-plan', code)
        self.assertNotIn('expected', code)

    def test_negative_scripts_save_success_and_failure_without_presuming_rejection(self):
        for name in ['shell-denied', 'patch-denied', 'web-denied', 'agent-denied']:
            code = probe.program(name, self.base)
            self.assertIn('returned:true', code)
            self.assertIn('returned:false', code)
        self.assertIn('.spec/expected-canary.txt', probe.program('path-denied', self.base))
        with self.assertRaises(ValueError):
            probe.program('other', self.base)

    def test_user_input_is_a_separate_native_function_call(self):
        events = [json.loads(line[6:]) for line in probe.tool_reply('user-input-stop', self.base).decode().splitlines() if line.startswith('data: ')]
        self.assertEqual(events[1]['item']['type'], 'function_call')
        self.assertEqual(events[1]['item']['name'], 'request_user_input_async')
        arguments = json.loads(events[1]['item']['arguments'])
        self.assertEqual(arguments, {'questions': [{'title': 'LOCAL_SIMULATION_ONLY', 'options': ['Local A', 'Local B']}]})

    def test_outputs_must_belong_to_the_scripted_call(self):
        obj = {'kind': 'inventory', 'names': ['read']}
        item = {'type': 'custom_tool_call_output', 'call_id': 'probe-call', 'output': 'runtime preamble\n' + json.dumps(obj)}
        self.assertEqual(probe.output_objects({'input': [item]}), [obj])
        self.assertEqual(probe.output_objects({'input': [{**item, 'call_id': 'other'}]}), [])
        self.assertEqual(probe.output_objects({'input': [{'type': 'message', 'content': json.dumps(obj)}]}), [])

    def test_structured_content_and_corrupt_output_are_handled(self):
        item = {'type': 'custom_tool_call_output', 'call_id': 'probe-call', 'output': [{'type': 'text', 'text': '{"kind":"read"}'}]}
        self.assertEqual(probe.output_objects({'input': [item]}), [{'kind': 'read'}])
        item['output'] = 'not JSON'
        self.assertEqual(probe.output_objects({'input': [item]}), [])

    def test_scenarios_outputs_and_budget_are_finite(self):
        self.assertEqual(set(self.contract['outputLabels']), {'read', 'user-input-stop'})
        self.assertTrue(set(self.contract['outputLabels']) <= set(probe.SCENARIOS))
        self.assertEqual(len(set(self.contract['outputLabels'].values())), self.contract['maximumScenarios'])
        self.assertEqual(self.contract['maximumScenarios'], 2)
        self.assertEqual(self.contract['maximumLocalHttpRequestsPerScenario'], 2)
        self.assertEqual(self.contract['paidModelCalls'], 0)
        self.assertFalse(self.contract['certifiesNativeProvider'])

    def test_host_descriptions_truthfully_declare_read_only_operations(self):
        # 宣言の真偽は実host試験で検証済み。ここでは本当に配布するMCP情報を確認する。
        import test_routing_host as fixture
        instance = fixture.RoutingHostTests(methodName='runTest')
        instance.setUp()
        self.addCleanup(instance.doCleanups)
        host = fixture.host.Host(instance.snapshot, fixture.host.sha((instance.snapshot / 'manifest.json').read_bytes()), instance.log)
        self.addCleanup(host.close)
        self.assertEqual({t['name'] for t in host.tools}, {'list_resources', 'read_resource'})
        for tool in host.tools:
            self.assertEqual(tool['annotations'], {'readOnlyHint': True, 'destructiveHint': False,
                                                  'idempotentHint': True, 'openWorldHint': False})

    def test_async_question_events_are_rejected_even_if_they_claim_final_answer(self):
        for method in ['item/started', 'item/completed']:
            frame = {'method': method, 'params': {'item': {'type': 'agentMessage', 'phase': 'final_answer',
                'delivery': 'async', 'questions': [{'title': 'question'}]}}}
            self.assertTrue(probe.sdk.question_frame(frame))
            frame['params']['item']['questions'] = None
            self.assertTrue(probe.sdk.question_frame(frame))

    def test_ordinary_messages_and_rpc_responses_are_not_dialogue_events(self):
        for frame in [{'id': 'rpc', 'result': {}}, {'method': 'item/completed', 'params': {'item': {
            'type': 'agentMessage', 'delivery': None, 'questions': None, 'text': '質問という文字だけ'}}}]:
            self.assertFalse(probe.sdk.question_frame(frame))


if __name__ == '__main__':
    unittest.main()
