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
                'clientInfo': {'name': 'codex_python_sdk', 'version': '0.160.1', 'title': 'Codex Python SDK'},
                'capabilities': {'experimentalApi': True}}},
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

    def test_active_reasoning_increments_do_not_certify_measurement(self):
        frames = self.frames[:-3] + self.original.reasoning_events() + self.frames[-3:]
        result = self.run_diagnostic(received=frames)
        self.assertEqual(result['status'], 'sdk_child_trace_diagnostic_passed')
        self.assertIs(result['eligibleForMeasurement'], False)

    def test_sdk_thread_start_hidden_history_is_rejected_in_each_path(self):
        hidden = [{'id': 'extra-turn', 'status': 'failed', 'error': {'message': 'failure'},
                   'items': [{'type': 'commandExecution', 'id': 'hidden-command'}]}]
        for indices in ((1,), (2,), (1, 2)):
            frames = copy.deepcopy(self.frames)
            for index in indices:
                frames[index]['result' if index == 1 else 'params']['thread']['turns'] = hidden
            with self.subTest(indices=indices), self.assertRaisesRegex(ValueError, 'native thread start history must be empty'):
                self.run_diagnostic(received=frames)

    def test_sdk_thread_start_error_status_in_response_and_notification_is_rejected(self):
        for indices in ((1,), (2,), (1, 2)):
            frames = copy.deepcopy(self.frames)
            for index in indices:
                frames[index]['result' if index == 1 else 'params']['thread']['status'] = {'type': 'systemError'}
            with self.subTest(indices=indices), self.assertRaisesRegex(ValueError, 'native thread error or unsupported status'):
                self.run_diagnostic(received=frames)

    def test_sdk_thread_system_error_is_rejected_even_after_turn_completion(self):
        error = {'method': 'thread/status/changed', 'params': {'threadId': 't', 'status': {'type': 'systemError'}}}
        with self.assertRaisesRegex(ValueError, 'native thread error or unsupported status'):
            self.run_diagnostic(received=self.frames + [error])
        idle = {'method': 'thread/status/changed', 'params': {'threadId': 't', 'status': {'type': 'idle'}}}
        self.assertEqual(self.run_diagnostic(received=self.frames + [idle])['status'], 'sdk_child_trace_diagnostic_passed')

    def test_telemetry_preview_truncation_is_typed_and_recorded_without_body_certification(self):
        events = self.parent_events()
        before = copy.deepcopy(events)
        for index in (3, 7, 10):
            events[index]['fields']['output_truncated'] = True
        result = sdk.audit_parent_links(events, self.frames, 'probe-call')
        self.assertEqual(result['telemetryTruncatedPreviewCallIds'], ['call-0', 'call-1', 'probe-call'])
        self.assertIs(result['certifiesTelemetryOutputBodies'], False)
        self.assertIs(result['eligibleForMeasurement'], False)
        for index in (3, 7, 10):
            for value in ('true', 'false', 0, 1, None, []):
                changed = copy.deepcopy(before)
                changed[index]['fields']['output_truncated'] = value
                with self.subTest(index=index, value=value), self.assertRaisesRegex(ValueError, 'telemetry preview truncation type'):
                    sdk.audit_parent_links(changed, self.frames, 'probe-call')
        for index in (3, 7, 10):
            events[index]['fields']['output_truncated'] = False
        self.assertEqual(sdk.audit_parent_links(events, self.frames, 'probe-call')['telemetryTruncatedPreviewCallIds'], [])

    def test_failed_turn_start_rpc_is_rejected_even_with_normal_completion(self):
        for status, error in (('failed', {'message': 'failure'}), ('interrupted', None),
                              ('completed', None), ('inProgress', {'message': 'failure'})):
            frames = copy.deepcopy(self.frames)
            frames[3]['result']['turn'].update(status=status, error=error)
            with self.subTest(status=status, error=error), self.assertRaisesRegex(ValueError, 'native turn start state'):
                self.run_diagnostic(received=frames)

    def test_empty_user_message_id_is_rejected_before_input_projection(self):
        frames = copy.deepcopy(self.frames)
        for frame in frames:
            item = frame.get('params', {}).get('item', {})
            if item.get('type') == 'userMessage':
                item['id'] = ''
        with self.assertRaisesRegex(ValueError, 'SDK item required'):
            self.run_diagnostic(received=frames)

    def test_reasoning_increment_and_completed_body_drift_is_rejected(self):
        for index in (2, 3):
            reason = self.original.reasoning_events()
            reason[index]['params']['delta'] = '改変した本文'
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'native streamed body mismatch'):
                self.run_diagnostic(received=self.frames[:-3] + reason + self.frames[-3:])

    def test_reasoning_prefixes_multiple_indices_and_original_frames_are_preserved(self):
        reason = self.original.prefixed_reasoning_events()
        before = copy.deepcopy(reason)
        result = self.run_diagnostic(received=self.frames[:-3] + reason + self.frames[-3:])
        self.assertEqual(result['status'], 'sdk_child_trace_diagnostic_passed')
        self.assertIs(result['eligibleForMeasurement'], False)
        self.assertEqual(reason, before)

    def test_reasoning_increments_before_start_after_completion_or_after_turn_are_rejected(self):
        reason = self.original.reasoning_events()
        for delta in reason[1:4]:
            for frames in (self.frames[:-3] + [delta] + reason + self.frames[-3:],
                           self.frames[:-3] + reason + [delta] + self.frames[-3:],
                           self.frames[:-3] + reason + self.frames[-3:] + [delta]):
                with self.subTest(method=delta['method']), self.assertRaisesRegex(ValueError, 'native increment outside'):
                    self.run_diagnostic(received=frames)

    def test_reasoning_increments_cannot_target_a_phantom_or_agent_item(self):
        reason = self.original.reasoning_events()
        for ident in ('phantom', 'final'):
            for delta in reason[1:4]:
                changed = copy.deepcopy(delta)
                changed['params']['itemId'] = ident
                frames = self.frames[:-3] + reason[:1] + [changed] + reason[1:] + self.frames[-3:]
                with self.subTest(ident=ident, method=delta['method']), self.assertRaisesRegex(ValueError, 'native increment outside active item'):
                    self.run_diagnostic(received=frames)

    def test_reasoning_increment_missing_indices_boolean_indices_and_nontext_are_rejected(self):
        reason = self.original.reasoning_events()
        for delta in reason[1:4]:
            changed = copy.deepcopy(delta)
            index = 'contentIndex' if 'contentIndex' in changed['params'] else 'summaryIndex'
            changes = [(index, False), (index, -1), (index, 0.0), ('extra', True), ('missing', None)]
            if 'delta' in delta['params']: changes.append(('delta', None))
            for key, value in changes:
                changed = copy.deepcopy(delta)
                if key == 'missing': changed['params'].pop(index)
                else: changed['params'][key] = value
                frames = self.frames[:-3] + reason[:1] + [changed] + reason[1:] + self.frames[-3:]
                with self.subTest(method=delta['method'], key=key), self.assertRaisesRegex(ValueError, 'native increment'):
                    self.run_diagnostic(received=frames)

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

    def test_rpc_booleans_cannot_be_replaced_with_integers_or_floats(self):
        for value in (1, 1.0):
            sent = copy.deepcopy(self.sent)
            sent[0]['params']['capabilities']['experimentalApi'] = value
            with self.subTest(capability=value), self.assertRaisesRegex(ValueError, 'fixed SDK initialize params'):
                self.run_diagnostic(sent=sent)
        for value in (0, 0.0):
            frames = copy.deepcopy(self.frames)
            frames[1]['result']['sandbox']['networkAccess'] = value
            with self.subTest(network=value), self.assertRaisesRegex(ValueError, 'SDK effective policy mismatch'):
                self.run_diagnostic(received=frames)

    def test_turn_overrides_and_unknown_request_fields_are_rejected(self):
        for index, key, value in [(3, 'approvalPolicy', 'on-request'), (3, 'sandboxPolicy', {'type': 'dangerFullAccess'}),
                                  (2, 'permissionProfile', 'full-access'), (0, 'unknown', True)]:
            sent = copy.deepcopy(self.sent)
            sent[index]['params'][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(ValueError): self.run_diagnostic(sent=sent)

    def test_initialize_and_thread_responses_must_precede_dependent_events(self):
        reordered = [f for f in self.frames if 'id' not in f] + [f for f in self.frames if 'id' in f]
        with self.assertRaises(ValueError): self.run_diagnostic(received=reordered)
        reordered = [self.frames[1], self.frames[0]] + self.frames[2:]
        with self.assertRaises(ValueError): self.run_diagnostic(received=reordered)

    def test_turn_started_can_precede_turn_response(self):
        frames = self.frames[:3] + self.frames[4:5] + self.frames[3:4] + self.frames[5:]
        self.assertEqual(self.run_diagnostic(received=frames)['status'], 'sdk_child_trace_diagnostic_passed')

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

    def test_empty_questions_cannot_be_represented_by_other_json_types(self):
        for value in (0, False, '', {}):
            frames = copy.deepcopy(self.frames)
            frames[-2]['params']['item']['questions'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'SDK dialogue or extra message evidence'):
                self.run_diagnostic(received=frames)

    def test_known_environment_notifications_are_retained_and_hashed(self):
        metadata = [
            {'method': 'remoteControl/status/changed', 'params': {'status': 'disabled', 'serverName': 'local',
                 'installationId': 'public', 'environmentId': None}, 'emittedAtMs': 1},
            {'method': 'account/rateLimits/updated', 'params': {'rateLimits': {'primary': None}}},
            {'method': 'warning', 'params': {'threadId': 't', 'message': '固定した警告'}},
            {'method': 'mcpServer/startupStatus/updated', 'params': {'threadId': 't', 'name': 'production-routing',
                 'status': 'ready', 'error': None, 'failureReason': None}}]
        frames = self.frames[:3] + metadata + self.frames[3:]
        result = self.run_diagnostic(received=frames, allowed_warnings=('固定した警告',))
        retained = result['nativeEvidence']['retainedNotifications']
        self.assertEqual([r['sha256'] for r in retained[:4]], [sdk.digest(m) for m in metadata])

    def test_fixed_warning_is_limited_to_one_pre_turn_notification(self):
        warning = {'method': 'warning', 'params': {'threadId': 't', 'message': '固定した警告'}}
        allowed = ('固定した警告',)
        self.assertEqual(self.run_diagnostic(received=self.frames[:3] + [warning] + self.frames[3:],
                                            allowed_warnings=allowed)['status'], 'sdk_child_trace_diagnostic_passed')
        for frames in (self.frames[:3] + [warning, warning] + self.frames[3:],
                       self.frames[:5] + [warning] + self.frames[5:], self.frames + [warning],
                       self.frames + [warning, warning]):
            with self.assertRaisesRegex(ValueError, 'SDK warning timing or count'):
                self.run_diagnostic(received=frames, allowed_warnings=allowed)
        for allowed in (('固定した警告', '別の警告'), ('',), (False,)):
            with self.subTest(allowed=allowed), self.assertRaisesRegex(ValueError, 'fixed warning allowlist required'):
                self.run_diagnostic(allowed_warnings=allowed)

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
        for frame in frames:
            item = frame.get('params', {}).get('item', {})
            if item.get('type') == 'agentMessage': item['id'] = 'probe-message'
        frames[-1]['params']['turn']['items'][0]['id'] = 'probe-message'
        tools = [{'type': 'namespace', 'name': 'functions', 'tools': [
            {'type': 'custom' if name == 'exec' else 'function', 'name': name}
            for name in ('exec', 'wait', 'request_user_input_async')]}]
        first = {'model': 'gpt-6.1-sol', 'input': [{'type': 'message', 'role': 'user', 'content': [
            {'type': 'input_text', 'text': '公開の要求'}]}], 'tools': tools}
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

    def raw_exchange(self):
        args = copy.deepcopy(self.exchange())
        args['sent'][2]['params']['experimentalRawEvents'] = True
        first, second = args['provider_requests']
        first['input'][0]['id'] = 'raw-input'
        second['input'][0]['id'] = 'raw-input'
        final = sdk.scripted_response(args['provider_responses'][1])
        final_projection = {k: final[k] for k in ('type', 'id', 'role', 'phase')}
        final_projection['content'] = [{'type': 'output_text', 'text': final['content'][0]['text']}]
        items = [first['input'][0], *second['input'][-2:], final_projection]
        raw = []
        for i, item in enumerate(items):
            item = copy.deepcopy(item)
            item['internal_chat_message_metadata_passthrough'] = {'turn_id': 'u'}
            raw.append({'method': sdk.RAW_METHODS[0], 'emittedAtMs': 1,
                        'params': {'threadId': 't', 'turnId': 'u', 'item': item}})
            if i in (1, 3):
                raw.append({'method': sdk.RAW_METHODS[1], 'emittedAtMs': 1,
                            'params': {'threadId': 't', 'turnId': 'u', 'responseId': 'probe-response',
                                       'usage': None, 'usageMetadata': None}})
        frames = []
        first_call = False
        for frame in args['received']:
            item = frame.get('params', {}).get('item', {})
            if frame.get('method') == 'item/started' and item.get('type') == 'mcpToolCall' and not first_call:
                frames.extend(raw[:3])
                first_call = True
            if frame.get('method') == 'item/started' and item.get('type') == 'agentMessage':
                frames.append(raw[3])
            frames.append(frame)
            if frame.get('method') == 'item/completed' and item.get('type') == 'agentMessage':
                frames.extend(raw[4:])
        args['received'] = frames
        args['sdk_raw_notifications'] = [{'method': f['method'], 'params': copy.deepcopy(f['params'])} for f in raw]
        return args

    def test_raw_exchange_correlates_delivery_and_provider_without_modifying_original_input(self):
        args = self.raw_exchange()
        before = copy.deepcopy(args)
        result = sdk.diagnose_raw_exchange(**args)
        self.assertEqual(args, before)
        self.assertEqual(result['status'], 'sdk_raw_scripted_exchange_diagnostic_passed')
        self.assertEqual((result['rawItemCount'], result['rawCompletedCount']), (4, 2))
        for field in ['sdkRawPayloadsMatchOriginalRpc', 'rawProviderCallOutputBindingVerified']:
            self.assertIs(result[field], True)
        for field in ['eligibleForMeasurement', 'providerParentBindingVerified', 'certifiesAllNativeLifecycle',
                      'rawItemsAreOriginalSseBytes', 'certifiesCompleteRawProviderContext', 'certifiesNativeProvider']:
            self.assertIs(result[field], False)
        with self.assertRaisesRegex(ValueError, 'unknown SDK thread params'):
            sdk.diagnose_exchange(**{k: v for k, v in args.items() if k != 'sdk_raw_notifications'})

    def test_raw_exchange_requires_explicit_true_flag_and_fixed_date(self):
        for flag in [False, 1, None, 'true']:
            args = self.raw_exchange()
            args['sent'][2]['params']['experimentalRawEvents'] = flag
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'explicit SDK raw event request'):
                sdk.diagnose_raw_exchange(**args)
        for date in ['2026-10-10', '', True]:
            with self.subTest(date=date), self.assertRaisesRegex(ValueError, 'fixed diagnostic date'):
                sdk.diagnose_raw_exchange(**self.raw_exchange(), diagnostic_date=date)

    def test_raw_exchange_rejects_missing_modified_foreign_or_reordered_notifications(self):
        for mode in ['missing-side', 'changed-side', 'extra-side', 'foreign-thread', 'foreign-turn',
                     'reversed', 'call-output', 'response-id', 'raw-final', 'internal-turn', 'bool-timestamp',
                     'internal-timestamp', 'unknown-metadata', 'outside-turn', 'duplicate-item-id', 'missing-raw']:
            args = self.raw_exchange()
            raw = [f for f in args['received'] if f.get('method') in sdk.RAW_METHODS]
            if mode == 'missing-side':
                args['sdk_raw_notifications'].pop()
            elif mode == 'changed-side':
                args['sdk_raw_notifications'][0]['params']['item']['content'] = []
            elif mode == 'extra-side':
                args['sdk_raw_notifications'].append(copy.deepcopy(args['sdk_raw_notifications'][0]))
            elif mode in ['foreign-thread', 'foreign-turn']:
                raw[0]['params']['threadId' if mode == 'foreign-thread' else 'turnId'] = 'other'
            elif mode == 'reversed':
                indices = [i for i, f in enumerate(args['received']) if f.get('method') in sdk.RAW_METHODS]
                for index, frame in zip(indices, reversed(raw)):
                    args['received'][index] = frame
            elif mode == 'call-output':
                raw[3]['params']['item']['output'] = []
            elif mode == 'response-id':
                raw[2]['params']['responseId'] = 'other'
            elif mode == 'raw-final':
                raw[4]['params']['item']['content'][0]['text'] = 'wrong'
            elif mode == 'internal-turn':
                raw[0]['params']['item']['internal_chat_message_metadata_passthrough']['turn_id'] = 'other'
            elif mode == 'bool-timestamp':
                raw[0]['emittedAtMs'] = True
            elif mode == 'internal-timestamp':
                raw[0]['params']['item']['internal_chat_message_metadata_passthrough']['create_time'] = float('inf')
            elif mode == 'unknown-metadata':
                raw[0]['params']['item']['internal_chat_message_metadata_passthrough']['unexpected'] = True
            elif mode == 'outside-turn':
                args['received'].remove(raw[0])
                args['received'].append(raw[0])
            elif mode == 'duplicate-item-id':
                raw[1]['params']['item']['id'] = raw[0]['params']['item']['id']
            else:
                args['received'].remove(raw[0])
            if mode not in ['missing-side', 'changed-side', 'extra-side']:
                args['sdk_raw_notifications'] = [{'method': f['method'], 'params': copy.deepcopy(f['params'])}
                                                for f in args['received'] if f.get('method') in sdk.RAW_METHODS]
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                sdk.diagnose_raw_exchange(**args)

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

    def test_native_and_provider_json_results_preserve_number_and_boolean_types(self):
        for changed in ('native', 'provider'):
            args = self.exchange()
            manifest = {**json.loads(args['manifest_raw']), 'candidateVersion': 1}
            args['manifest_raw'] = json.dumps(manifest).encode()
            args['host_events'] = copy.deepcopy(args['host_events'])
            args['host_events'][0]['result'] = sdk.trace.manifest_view(args['manifest_raw'])[2]
            for frame in args['received']:
                item = frame.get('params', {}).get('item', {})
                if frame.get('method') == 'item/completed' and item.get('tool') == 'list_resources':
                    item['result']['content'][0]['text'] = json.dumps({**args['host_events'][0]['result'],
                                                                   'candidateVersion': True if changed == 'native' else 1})
            chunk = args['provider_requests'][1]['input'][-1]['output'][1]
            payload = json.loads(chunk['text'])
            payload['listed']['content'][0]['text'] = json.dumps({**args['host_events'][0]['result'],
                                                               'candidateVersion': True if changed == 'provider' else 1})
            chunk['text'] = json.dumps(payload)
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, f'host/{changed} result mismatch'):
                sdk.diagnose_exchange(**args)

    def test_sse_indices_cannot_be_booleans_or_floats(self):
        for field in ('output_index', 'content_index'):
            for value in (False, 0.0):
                lines = sdk.cli.simulation_reply().decode().splitlines()
                for index, line in enumerate(lines):
                    if line.startswith('data: '):
                        event = json.loads(line[6:])
                        if field in event:
                            event[field] = value
                            lines[index] = 'data: ' + json.dumps(event)
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'SSE (response output|final start|final delta) mismatch'):
                    sdk.scripted_response(('\n'.join(lines) + '\n').encode())

    def test_sse_errors_and_incomplete_details_are_rejected_at_both_boundaries(self):
        for which in (0, 1):
            for boundary in (0, -1):
                for field in ('error', 'incomplete_details'):
                    for value in ({'code': 'server_error'}, False, '', []):
                        args = self.exchange()
                        events = [json.loads(line[6:]) for line in args['provider_responses'][which].decode().splitlines()
                                  if line.startswith('data: ')]
                        events[boundary]['response'][field] = value
                        args['provider_responses'][which] = ''.join(
                            'event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
                        with self.subTest(which=which, boundary=boundary, field=field, value=value), \
                                self.assertRaisesRegex(ValueError, 'SSE error or incomplete response'):
                            sdk.diagnose_exchange(**args)
        args = self.exchange()
        for which, raw in enumerate(args['provider_responses']):
            events = [json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: ')]
            for boundary in (0, -1):
                events[boundary]['response'].update(error=None, incomplete_details=None)
            args['provider_responses'][which] = ''.join(
                'event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
        self.assertEqual(sdk.diagnose_exchange(**args)['status'], 'sdk_scripted_exchange_diagnostic_passed')

    def test_unknown_sse_event_response_and_final_item_fields_are_rejected(self):
        for which, target in ((0, 'event'), (1, 'event'), (0, 'response'), (1, 'response'), (1, 'item')):
            args = self.exchange()
            events = [json.loads(line[6:]) for line in args['provider_responses'][which].decode().splitlines()
                      if line.startswith('data: ')]
            obj = events[-1] if target == 'event' else events[-1]['response'] if target == 'response' else events[-2]['item']
            obj['unrecognized'] = 'hidden'
            args['provider_responses'][which] = ''.join(
                'event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
            with self.subTest(which=which, target=target), self.assertRaises(ValueError):
                sdk.diagnose_exchange(**args)

    def test_sse_response_ids_cannot_be_empty(self):
        lines = sdk.cli.simulation_reply().decode().splitlines()
        for index, line in enumerate(lines):
            if line.startswith('data: '):
                event = json.loads(line[6:])
                if 'response' in event:
                    event['response']['id'] = ''
                    lines[index] = 'data: ' + json.dumps(event)
        with self.assertRaisesRegex(ValueError, 'SSE response lifecycle'):
            sdk.scripted_response(('\n'.join(lines) + '\n').encode())

    def test_matching_wire_prefix_cannot_replace_sdk_user_input(self):
        for replacement in ([{'type': 'input_text', 'text': 'UNRELATED_REQUEST'}], [],
                            [{'type': 'input_text', 'text': '公開の要求'}, {'type': 'input_text', 'text': '余分'}]):
            args = self.exchange()
            for request in args['provider_requests']: request['input'][0]['content'] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_synthetic_profile_cannot_omit_sdk_instructions_from_provider_input(self):
        for name in ('baseInstructions', 'developerInstructions'):
            for value in ('EXTRA_INSTRUCTIONS', '', None):
                args = self.exchange()
                args['sent'] = copy.deepcopy(args['sent'])
                args['sent'][2]['params'][name] = value
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, 'synthetic provider profile forbids extra instructions'):
                    sdk.diagnose_exchange(**args)

    def test_outer_turn_ids_cannot_contradict_start_or_completion(self):
        for method in ('turn/started', 'turn/completed'):
            args = self.exchange()
            next(f for f in args['received'] if f.get('method') == method)['params']['turnId'] = 'other'
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, 'SDK outer turn mismatch'):
                sdk.diagnose_exchange(**args)

    def test_outer_thread_id_cannot_contradict_thread_start(self):
        frames = copy.deepcopy(self.frames)
        next(f for f in frames if f.get('method') == 'thread/started')['params']['threadId'] = 'other'
        with self.assertRaisesRegex(ValueError, 'SDK outer thread mismatch'):
            self.run_diagnostic(received=frames)

    def test_matching_prefix_cannot_add_user_developer_or_unknown_context(self):
        for role in ('user', 'developer', 'system'):
            args = self.exchange()
            for request in args['provider_requests']:
                request['input'].insert(0, {'type': 'message', 'role': role,
                                          'content': [{'type': 'input_text', 'text': 'EXTRA_MESSAGE'}]})
            with self.subTest(role=role), self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_top_level_provider_instructions_cannot_bypass_input_context_checks(self):
        args = self.exchange()
        for request in args['provider_requests']: request['instructions'] = 'EXTRA_INSTRUCTIONS'
        with self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def test_wire_final_id_requires_native_final_correspondence(self):
        args = self.exchange()
        for frame in args['received']:
            item = frame.get('params', {}).get('item', {})
            if item.get('type') == 'agentMessage': item['id'] = 'different-final'
        args['received'][-1]['params']['turn']['items'][0]['id'] = 'different-final'
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

    def test_sse_missing_final_and_delta_ids_are_rejected(self):
        events = [json.loads(line[6:]) for line in sdk.cli.simulation_reply().decode().splitlines() if line.startswith('data: ')]
        for event in events:
            if 'item' in event: event['item'].pop('id', None)
            if event['type'] == 'response.completed': event['response']['output'][0].pop('id', None)
            if event['type'] == 'response.output_text.delta': event.pop('item_id', None)
        raw = ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
        with self.assertRaises(ValueError): sdk.scripted_response(raw)

    def test_scripted_failure_or_yield_cannot_be_reported_as_completed_read(self):
        for text in ('Script running with cell ID pending', 'Script failed\nOutput:\n'):
            args = self.exchange()
            args['provider_requests'][1]['input'][-1]['output'][0]['text'] = text
            with self.assertRaises(ValueError): sdk.diagnose_exchange(**args)

    def parent_events(self):
        def event(name, **fields):
            return {'level': 'INFO', 'target': 'codex_otel.trace_safe',
                    'fields': {'event.name': name, 'conversation.id': 't', **fields}}
        events = [event('codex.tool_call_received', turn_id='u', call_id='probe-call', tool_name='exec',
                        tool_namespace='functions', tool_source='direct')]
        for number, tool in enumerate(('list_resources', 'read_resource')):
            fields = {'call_id': f'call-{number}', 'tool_name': tool,
                      'tool_namespace': 'mcp__production_routing', 'tool_source': 'code_mode'}
            events += [event('codex.tool_call_received', **fields, **{'cell.id': '1', 'runtime_tool_call_id': f'tool-{number}'}),
                       event('codex.code_mode.nested_tool_dispatched', call_id=f'call-{number}', turn_id='u',
                             **{'cell.id': '1', 'runtime_tool_call_id': f'tool-{number}'}),
                       event('codex.tool_result', **fields, success='true'),
                       event('codex.tool_result_ready', **fields, turn_id='u')]
        events.append({'level': 'INFO', 'target': 'codex_code_mode::timing', 'fields': {
            'event.name': 'codex.code_mode.host_timing', 'conversation_id': 't', 'turn_id': 'u',
            'call_id': 'probe-call', 'cell_id': '1', 'tool_name': 'exec', 'code_mode_host_duration_ns': 1}})
        events += [event('codex.tool_result', call_id='probe-call', tool_name='exec', tool_namespace='functions', success='true'),
                   event('codex.tool_result_ready', turn_id='u', call_id='probe-call', tool_name='exec',
                         tool_namespace='functions', tool_source='direct')]
        return events

    def test_parent_cell_and_native_children_are_matched_by_actual_ids(self):
        result = sdk.audit_parent_links(self.parent_events(), self.frames, 'probe-call')
        self.assertEqual(result['nativeChildIds'], ['call-0', 'call-1'])
        self.assertEqual(result['cellId'], '1')
        self.assertFalse(result['eligibleForMeasurement'])
        self.assertFalse(result['certifiesMultipleOrYieldedCells'])

    def test_parent_timing_missing_or_wrong_call_and_cell_are_rejected(self):
        for change in ('missing', 'cell', 'call', 'duplicate'):
            events = self.parent_events()
            if change == 'missing': events.pop(9)
            if change == 'cell': events[9]['fields']['cell_id'] = 'other'
            if change == 'call': events[9]['fields']['call_id'] = 'other'
            if change == 'duplicate': events.insert(10, copy.deepcopy(events[9]))
            with self.subTest(change=change), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_nested_runtime_cell_thread_and_turn_drift_are_rejected(self):
        for key, value in [('cell.id', 'other'), ('runtime_tool_call_id', 'other'), ('turn_id', 'other'), ('conversation.id', 'other')]:
            events = self.parent_events()
            events[2]['fields'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_unlogged_missing_and_repeated_child_milestones_are_rejected(self):
        for events in (self.parent_events()[:-1], self.parent_events()[:4] + self.parent_events()[5:],
                       self.parent_events()[:5] + self.parent_events()[1:5] + self.parent_events()[5:]):
            with self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_extra_tool_receipt_and_unknown_target_or_event_are_rejected(self):
        for change in ('call', 'target', 'event'):
            events = self.parent_events()
            if change == 'call': events[1]['fields']['call_id'] = 'extra-tool'
            if change == 'target': events[1]['target'] = 'arbitrary-output'
            if change == 'event': events[1]['fields']['event.name'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_duplicate_runtime_ids_cannot_merge_two_child_calls(self):
        events = self.parent_events()
        events[5]['fields']['runtime_tool_call_id'] = events[1]['fields']['runtime_tool_call_id']
        with self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_parent_cannot_finish_before_child_results(self):
        events = self.parent_events()
        events = events[:4] + events[9:10] + events[4:9] + events[10:]
        with self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_failed_results_or_different_native_child_ids_are_rejected(self):
        events = self.parent_events()
        events[3]['fields']['success'] = 'false'
        with self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')
        frames = copy.deepcopy(self.frames)
        frames[8]['params']['item']['id'] = 'other'
        with self.assertRaises(ValueError): sdk.audit_parent_links(self.parent_events(), frames, 'probe-call')

    def test_result_events_cannot_contradict_bound_cell_runtime_turn_or_source(self):
        for index in (3, 4):
            for key, value in [('cell.id', 'other'), ('cell_id', 'other'), ('runtime_tool_call_id', 'other'),
                               ('turn_id', 'other'), ('tool_source', 'direct')]:
                events = self.parent_events()
                events[index]['fields'][key] = value
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_dispatch_cannot_contradict_tool_name_namespace_or_source(self):
        for key, value in [('tool_name', 'shell'), ('tool_namespace', 'functions'), ('tool_source', 'direct')]:
            events = self.parent_events()
            events[2]['fields'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_direct_receipt_cannot_introduce_cell_or_runtime_child_ids(self):
        for key in ('cell.id', 'cell_id', 'runtime_tool_call_id', 'parent_call_id'):
            events = self.parent_events()
            events[0]['fields'][key] = 'other'
            with self.subTest(key=key), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_result_origin_and_counter_cannot_contradict_call_identity(self):
        for key, value in [('tool_origin', 'builtin'), ('mcp_tool', False), ('tool_result_seq', 2)]:
            events = self.parent_events()
            events[3]['fields'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): sdk.audit_parent_links(events, self.frames, 'probe-call')

    def test_reversed_or_overlapping_child_telemetry_is_rejected(self):
        events = self.parent_events()
        for changed in (events[:1] + events[5:9] + events[1:5] + events[9:],
                        events[:4] + events[5:6] + events[4:5] + events[6:]):
            with self.assertRaises(ValueError): sdk.audit_parent_links(changed, self.frames, 'probe-call')

    def test_parallel_native_children_cannot_replace_sequential_program_evidence(self):
        frames = self.frames[:8] + self.frames[9:10] + self.frames[8:9] + self.frames[10:]
        with self.assertRaises(ValueError): sdk.audit_parent_links(self.parent_events(), frames, 'probe-call')

    def test_complete_projection_preserves_every_target_row(self):
        selected = b''.join((json.dumps(e) + '\n').encode() for e in self.parent_events())
        other = b'{"target":"unrelated","fields":{}}\n'
        self.assertEqual(sdk.complete_trace_projection(other + selected, selected), self.parent_events())

    def test_projection_cannot_drop_extra_operations_or_unknown_events(self):
        selected = b''.join((json.dumps(e) + '\n').encode() for e in self.parent_events())
        for fields in ({'event.name': 'codex.tool_call_received', 'call_id': 'extra-tool'},
                       {'event.name': 'unknown'}):
            extra = (json.dumps({'target': 'codex_otel.trace_safe', 'level': 'INFO', 'fields': fields}) + '\n').encode()
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                sdk.complete_trace_projection(selected + extra, selected)

    def test_unparseable_original_trace_is_not_silently_removed(self):
        selected = b''.join((json.dumps(e) + '\n').encode() for e in self.parent_events())
        for extra in (b'not-json\n', b'[]\n', b'{}\n'):
            with self.assertRaises(ValueError): sdk.complete_trace_projection(selected + extra, selected)


if __name__ == '__main__':
    unittest.main()
