"""SDKの要求相関・環境通知・入力・対話・native証拠の不整合を拒否する。"""
import copy
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_sdk_trace as sdk
import production_operation_probe as operation
import test_production_trace as fixture


class ProductionSdkTraceTests(unittest.TestCase):
    def setUp(self):
        self.original = fixture.ProductionTraceTests(methodName='runTest')
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        ids = [f'00000000-0000-4000-8000-00000000000{i}' for i in (1, 2, 3)]
        self.sent = [
            {'id': ids[0], 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'codex_python_sdk', 'version': '0.160.1'}}},
            {'method': 'initialized'},
            {'id': ids[1], 'method': 'thread/start', 'params': {
                'model': 'gpt-6.1-sol', 'modelProvider': 'local', 'sandbox': 'read-only',
                'approvalPolicy': 'never', 'ephemeral': True, 'allowProviderModelFallback': False}},
            {'id': ids[2], 'method': 'turn/start', 'params': {
                'threadId': 't', 'input': [{'type': 'text', 'text': '公開の要求'}]}}]
        self.frames = copy.deepcopy(self.original.frames)
        for f in self.frames:
            if 'id' in f:
                f['id'] = ids[f['id'] - 1]
        self.frames[1]['result'].update({
            'model': 'gpt-6.1-sol', 'modelProvider': 'local', 'approvalPolicy': 'never',
            'sandbox': {'type': 'readOnly', 'networkAccess': False}, 'instructionSources': []})
        self.frames[1]['result']['thread']['ephemeral'] = True
        user = {'type': 'userMessage', 'id': 'input', 'clientId': None,
                'content': [{'type': 'text', 'text': '公開の要求', 'text_elements': []}]}
        self.frames[5:5] = [{'method': method, 'params': {'threadId': 't', 'turnId': 'u', 'item': copy.deepcopy(user)}}
                            for method in ('item/started', 'item/completed')]
        self.frames[-1]['params']['turn'].update({'itemsView': 'summary', 'items': [copy.deepcopy(self.frames[-2]['params']['item'])]})
        self.final = self.frames[-2]['params']['item']['text']
        self.frames[-3]['params']['item']['text'] = ''

    def run_diagnostic(self, **changes):
        args = {'manifest_raw': self.original.raw, 'host_events': self.original.log,
                'sent': self.sent, 'received': self.frames, 'expected_final_text': self.final,
                'actual_exit_code': 0}
        args.update(changes)
        return sdk.diagnose(**args)

    def test_sdk_child_results_are_checked_without_certifying_parent_or_measurement(self):
        result = self.run_diagnostic()
        self.assertEqual(result['status'], 'sdk_child_trace_diagnostic_passed')
        self.assertEqual(result['hostCalls'], 2)
        self.assertEqual(result['readResources'], [self.original.path])
        for key in ('providerParentBindingVerified', 'eligibleForMeasurement', 'certifiesExpectedDecision',
                    'certifiesBehavior', 'certifiesSkillGate'):
            self.assertIs(result[key], False)

    def test_inputs_and_raw_evidence_are_not_mutated(self):
        before = copy.deepcopy((self.sent, self.frames))
        normalized = sdk.normalized(self.sent, self.frames)
        self.assertEqual((self.sent, self.frames), before)
        normalized['frames'][0]['result']['changed'] = True
        self.assertEqual((self.sent, self.frames), before)
        self.assertEqual(len(normalized['retainedNotifications']), 2)

    def test_uuid_missing_duplicate_and_unmatched_responses_are_rejected(self):
        for change in ('integer', 'duplicate', 'unmatched', 'missing'):
            frames = copy.deepcopy(self.frames)
            if change == 'integer': frames[0]['id'] = 1
            if change == 'duplicate': frames.insert(1, copy.deepcopy(frames[0]))
            if change == 'unmatched': frames[0]['id'] = '00000000-0000-4000-8000-000000000004'
            if change == 'missing': frames.pop(0)
            with self.subTest(change=change), self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_additional_thread_or_turn_requests_are_rejected(self):
        for sent in (self.sent + [self.sent[-1]], self.sent[:2] + self.sent[3:], self.sent[::-1]):
            with self.assertRaises(ValueError): self.run_diagnostic(sent=sent)

    def test_effective_policy_and_input_policy_drift_are_rejected(self):
        for key, value in [('approvalPolicy', 'on-request'), ('sandbox', 'danger-full-access'),
                           ('ephemeral', False), ('allowProviderModelFallback', True)]:
            sent = copy.deepcopy(self.sent)
            sent[2]['params'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.run_diagnostic(sent=sent)
        frames = copy.deepcopy(self.frames)
        frames[1]['result']['sandbox']['networkAccess'] = True
        with self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_wrong_thread_user_input_and_extra_attachments_are_rejected(self):
        for key in ('thread', 'content', 'attachment'):
            frames = copy.deepcopy(self.frames)
            for f in frames[5:7]:
                if key == 'thread': f['params']['threadId'] = 'other'
                if key == 'content': f['params']['item']['content'][0]['text'] = '期待値の混入'
                if key == 'attachment': f['params']['item']['content'].append({'type': 'image', 'url': 'hidden'})
            with self.subTest(key=key), self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_repeated_missing_or_late_user_input_is_rejected(self):
        for frames in (self.frames[:5] + self.frames[7:], self.frames[:7] + self.frames[5:7] + self.frames[7:],
                       self.frames[:5] + self.frames[7:9] + self.frames[5:7] + self.frames[9:]):
            with self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_questions_and_async_delivery_cannot_be_scored_as_final(self):
        for key, value in [('questions', [{'title': '確認'}]), ('delivery', 'async'), ('memoryCitation', {'path': 'hidden'})]:
            for offset in (-3, -2):
                frames = copy.deepcopy(self.frames)
                frames[offset]['params']['item'][key] = value
                with self.subTest(key=key, offset=offset), self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_known_environment_notifications_are_retained_and_hashed(self):
        metadata = [
            {'method': 'remoteControl/status/changed', 'params': {'status': 'disabled', 'serverName': 'local',
                 'installationId': 'public', 'environmentId': None}, 'emittedAtMs': 1},
            {'method': 'account/rateLimits/updated', 'params': {'rateLimits': {'primary': None}}},
            {'method': 'warning', 'params': {'threadId': 't', 'message': '固定した警告'}},
            {'method': 'mcpServer/startupStatus/updated', 'params': {'threadId': 't', 'name': 'production-routing',
                 'status': 'ready', 'error': None, 'failureReason': None}}]
        frames = self.frames[:5] + metadata + self.frames[5:]
        result = self.run_diagnostic(received=frames, allowed_warnings=('固定した警告',))
        retained = result['nativeEvidence']['retainedNotifications']
        self.assertEqual([r['sha256'] for r in retained[:4]], [sdk.digest(m) for m in metadata])

    def test_unapproved_warnings_and_unknown_notifications_are_rejected(self):
        for notification in [
            {'method': 'warning', 'params': {'threadId': 't', 'message': '新しい警告'}},
            {'method': 'unknown', 'params': {'threadId': 't'}},
            {'method': 'item/fileChange/requestApproval', 'id': 'request', 'params': {}}]:
            with self.assertRaises(ValueError): self.run_diagnostic(received=self.frames[:5] + [notification] + self.frames[5:])

    def test_active_remote_control_and_failed_mcp_startup_are_rejected(self):
        for notification in [
            {'method': 'remoteControl/status/changed', 'params': {'status': 'enabled', 'serverName': 'local',
                 'installationId': 'public', 'environmentId': None}},
            {'method': 'mcpServer/startupStatus/updated', 'params': {'threadId': 't', 'name': 'production-routing',
                 'status': 'failed', 'error': 'failure', 'failureReason': None}}]:
            with self.assertRaises(ValueError): self.run_diagnostic(received=self.frames[:5] + [notification] + self.frames[5:])

    def test_delta_requires_active_message_and_matching_turn(self):
        delta = {'method': 'item/agentMessage/delta', 'params': {'threadId': 't', 'turnId': 'u',
                 'itemId': 'final', 'delta': self.final}}
        self.run_diagnostic(received=self.frames[:-2] + [delta] + self.frames[-2:])
        for frames in (self.frames[:5] + [delta] + self.frames[5:], self.frames + [delta]):
            with self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_streamed_text_cannot_differ_from_completed_final(self):
        delta = {'method': 'item/agentMessage/delta', 'params': {'threadId': 't', 'turnId': 'u',
                 'itemId': 'final', 'delta': '原終端とは異なるテキスト'}}
        with self.assertRaises(ValueError):
            self.run_diagnostic(received=self.frames[:-2] + [delta] + self.frames[-2:])

    def test_input_id_cannot_be_reused_for_native_actions(self):
        frames = copy.deepcopy(self.frames)
        frames[7]['params']['item']['id'] = 'input'
        with self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_input_cannot_precede_turn_start(self):
        frames = self.frames[:4] + self.frames[5:7] + self.frames[4:5] + self.frames[7:]
        with self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_turn_summary_cannot_hide_an_extra_action_or_different_final(self):
        for change in ('missing', 'drift', 'extra'):
            frames = copy.deepcopy(self.frames)
            items = frames[-1]['params']['turn']['items']
            if change == 'missing': items.clear()
            if change == 'drift': items[0]['text'] = '別の応答'
            if change == 'extra': items.append({'type': 'fileChange', 'id': 'hidden'})
            with self.subTest(change=change), self.assertRaises(ValueError): self.run_diagnostic(received=frames)

    def test_final_text_and_host_bytes_still_require_exact_evidence(self):
        with self.assertRaises(ValueError): self.run_diagnostic(expected_final_text='別の応答')
        events = copy.deepcopy(self.original.log)
        events[1]['result']['content'] += '改変'
        with self.assertRaises(ValueError): self.run_diagnostic(host_events=events)

    def test_prohibited_native_actions_and_truncated_trace_are_rejected(self):
        for kind in ('commandExecution', 'fileChange', 'webSearch', 'dynamicToolCall', 'collabAgentToolCall'):
            frames = copy.deepcopy(self.frames)
            frames[7]['params']['item']['type'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.run_diagnostic(received=frames)
        with self.assertRaises(ValueError): self.run_diagnostic(received=self.frames[:-1])

    def exchange(self):
        frames = copy.deepcopy(self.frames)
        frames[-2]['params']['item']['text'] = 'LOCAL_SIMULATION_ONLY'
        frames[-1]['params']['turn']['items'][0]['text'] = 'LOCAL_SIMULATION_ONLY'
        tools = [{'type': 'namespace', 'name': 'functions', 'tools': [
            {'type': 'custom' if name == 'exec' else 'function', 'name': name}
            for name in ('exec', 'wait', 'request_user_input_async')]}]
        first = {'model': 'gpt-6.1-sol', 'input': [{'type': 'message', 'role': 'user', 'content': []}], 'tools': tools}
        response = operation.tool_reply('read', ROOT / '.venv/operation-test')
        call = sdk.scripted_response(response)
        payload = {'kind': 'read'}
        for key, event in zip(('listed', 'read'), self.original.log):
            payload[key] = {'isError': False, 'content': [{'type': 'text', 'text': json.dumps(event['result'])}]}
        second = {**first, 'input': copy.deepcopy(first['input']) + [{**call, 'id': 'native-call'}, {
            'type': 'custom_tool_call_output', 'id': 'output', 'call_id': call['call_id'], 'output': [
                {'type': 'input_text', 'text': 'Script completed\nWall time 0.0 seconds\nOutput:\n'},
                {'type': 'input_text', 'text': json.dumps(payload)}]}]}
        return {'manifest_raw': self.original.raw, 'host_events': self.original.log, 'sent': self.sent,
                'received': frames, 'provider_requests': [first, second],
                'provider_responses': [response, sdk.cli.simulation_reply()], 'expected_program': call['input'],
                'expected_final_text': 'LOCAL_SIMULATION_ONLY', 'actual_exit_code': 0}

    def test_scripted_wire_correspondence_does_not_invent_native_parent_binding(self):
        result = sdk.diagnose_exchange(**self.exchange())
        self.assertEqual(result['status'], 'sdk_scripted_exchange_diagnostic_passed')
        self.assertIs(result['providerCallOutputBindingVerified'], True)
        self.assertIs(result['providerParentBindingVerified'], False)
        self.assertIs(result['eligibleForMeasurement'], False)

    def test_wire_call_id_program_and_prefix_drift_are_rejected(self):
        for change in ('call-id', 'program', 'prefix', 'extra'):
            args = self.exchange()
            inputs = args['provider_requests'][1]['input']
            if change == 'call-id': inputs[-1]['call_id'] = 'another'
            if change == 'program': args['expected_program'] = 'arbitraryCode()'
            if change == 'prefix': inputs[0]['content'] = ['改変した入力']
            if change == 'extra': inputs.insert(-1, {'type': 'function_call', 'name': 'shell'})
            with self.subTest(change=change), self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_wire_output_cannot_claim_a_different_host_result(self):
        args = self.exchange()
        chunk = args['provider_requests'][1]['input'][-1]['output'][1]
        payload = json.loads(chunk['text'])
        payload['read']['content'][0]['text'] = '{}'
        chunk['text'] = json.dumps(payload)
        with self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_missing_or_extra_wire_responses_are_rejected(self):
        for length in (0, 1, 3):
            args = self.exchange()
            args['provider_responses'] = (args['provider_responses'] * 2)[:length]
            with self.subTest(length=length), self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_wire_model_and_surface_inventory_drift_are_rejected(self):
        for change in ('model', 'surface'):
            args = self.exchange()
            if change == 'model': args['provider_requests'][1]['model'] = 'another-model'
            else: args['provider_requests'][1]['tools'] = []
            with self.subTest(change=change), self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_sse_event_output_and_delta_mismatches_are_rejected(self):
        raw = sdk.cli.simulation_reply()
        for changed in (raw.replace(b'event: response.completed', b'event: response.failed'),
                        raw.replace(b'"output_index": 0', b'"output_index": 1'),
                        raw.replace(b'"delta": "LOCAL_SIMULATION_ONLY"', b'"delta": "other"'),
                        raw + raw, b'data: {"type":"unknown"}\n\n'):
            with self.assertRaises(ValueError): sdk.scripted_response(changed)

    def test_sse_function_calls_are_not_accepted_as_scripted_exec(self):
        args = self.exchange()
        args['provider_responses'][0] = operation.tool_reply('user-input-stop', ROOT / '.venv/operation-test')
        with self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_scripted_failure_or_yield_cannot_be_reported_as_completed_read(self):
        for text in ('Script running with cell ID pending', 'Script failed\nOutput:\n'):
            args = self.exchange()
            args['provider_requests'][1]['input'][-1]['output'][0]['text'] = text
            with self.assertRaises(ValueError): sdk.diagnose_exchange(**args)


if __name__ == '__main__':
    unittest.main()
