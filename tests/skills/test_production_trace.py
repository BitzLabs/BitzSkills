"""合成traceと実hostで、入力漏洩と証拠偽装の拒否を確認する。モデルを呼ばない。"""
import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as audit
import test_routing_host as host_fixture

host = host_fixture.host


class ProductionTraceTests(unittest.TestCase):
    def setUp(self):
        fixture = host_fixture.RoutingHostTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.raw = (fixture.snapshot / 'manifest.json').read_bytes()
        self.manifest = json.loads(self.raw)
        self.selected = 'sdd-plan'
        self.path = next(s['path'] for s in self.manifest['skills'] if s['name'] == self.selected)
        with_host = host.Host(fixture.snapshot, host.sha(self.raw), fixture.log)
        try:
            with_host.call('list_resources', {})
            with_host.call('read_resource', {'path': self.path})
        finally:
            with_host.close()
        self.log = [json.loads(line) for line in fixture.log.read_text().splitlines()]
        self.decision = {'selectedEntry': 'sdd-plan', 'selectedPath': 'plan', 'outcome': 'proceed',
                         'events': [], 'rejectedEvents': [], 'readyClaimed': False,
                         'evidencePresent': False, 'reason': '合成の発火判断'}
        self.catalog = {'events': ['synthetic.allowed']}
        self.frames = self.make_frames(self.log, self.decision)

    @staticmethod
    def make_frames(log, decision):
        def notification(method, **params):
            return {'method': method, 'params': {'threadId': 't', 'turnId': 'u', **params}}
        frames = [{'id': 1, 'result': {'userAgent': 'synthetic'}},
                  {'id': 2, 'result': {'thread': {'id': 't'}}},
                  {'method': 'thread/started', 'params': {'thread': {'id': 't'}}},
                  {'id': 3, 'result': {'turn': {'id': 'u', 'status': 'inProgress', 'items': [], 'error': None}}},
                  notification('turn/started', turn={'id': 'u', 'status': 'inProgress', 'items': [], 'error': None})]
        for i, event in enumerate(log):
            item = {'type': 'mcpToolCall', 'id': f'call-{i}', 'server': audit.SERVER,
                    'tool': event['tool'], 'arguments': event['arguments'], 'status': 'completed',
                    'result': {'content': [{'type': 'text', 'text': json.dumps(event['result'])}]}}
            start = copy.deepcopy(item)
            start['status'] = 'inProgress'
            start['result'] = None
            frames += [notification('item/started', item=start), notification('item/completed', item=item)]
        message = {'type': 'agentMessage', 'id': 'final', 'phase': 'final_answer', 'text': json.dumps(decision)}
        frames += [notification('item/started', item={**message, 'text': ''}),
                   notification('item/completed', item=message),
                   notification('turn/completed', turn={'id': 'u', 'status': 'completed', 'error': None})]
        return frames

    def run_audit(self, **changes):
        args = {'manifest_raw': self.raw, 'host_events': self.log, 'frames': self.frames,
                'decision': self.decision, 'event_catalog': self.catalog, 'actual_exit_code': 0}
        args.update(changes)
        return audit.audit(**args)

    @staticmethod
    def reasoning_events():
        def frame(method, **params):
            return {'method': method, 'params': {'threadId': 't', 'turnId': 'u', **params}}
        item = {'type': 'reasoning', 'id': 'reason', 'summary': [], 'content': []}
        return [frame('item/started', item=item),
                frame('item/reasoning/summaryPartAdded', itemId='reason', summaryIndex=0),
                frame('item/reasoning/summaryTextDelta', itemId='reason', summaryIndex=0, delta='公開の要約'),
                frame('item/reasoning/textDelta', itemId='reason', contentIndex=0, delta='公開の合成内容'),
                frame('item/completed', item={**item, 'summary': ['公開の要約'], 'content': ['公開の合成内容']})]

    def test_active_reasoning_increments_are_accepted(self):
        frames = self.frames[:-3] + self.reasoning_events() + self.frames[-3:]
        self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')

    @staticmethod
    def prefixed_reasoning_events():
        def frame(method, **params):
            return {'method': method, 'params': {'threadId': 't', 'turnId': 'u', **params}}
        item = {'type': 'reasoning', 'id': 'reason', 'summary': ['既存要約'], 'content': ['既存本文']}
        return [frame('item/started', item=item),
                frame('item/reasoning/summaryTextDelta', itemId='reason', summaryIndex=0, delta='追記'),
                frame('item/reasoning/textDelta', itemId='reason', contentIndex=0, delta='追記'),
                frame('item/reasoning/summaryPartAdded', itemId='reason', summaryIndex=1),
                frame('item/reasoning/summaryTextDelta', itemId='reason', summaryIndex=1, delta='新規要約'),
                frame('item/reasoning/textDelta', itemId='reason', contentIndex=1, delta='新規本文'),
                frame('item/completed', item={**item, 'summary': ['既存要約追記', '新規要約'],
                                             'content': ['既存本文追記', '新規本文']})]

    def test_turn_completion_summary_cannot_hide_operations_or_invalid_fields(self):
        hidden = [{'type': 'commandExecution', 'id': 'hidden-command'}]
        for changes in ({'itemsView': 'summary', 'items': hidden}, {'items': []},
                        {'itemsView': 'summary'}, {'itemsView': 'full', 'items': []},
                        {'unknown': None}, {'durationMs': False}, {'completedAt': -1}):
            frames = copy.deepcopy(self.frames)
            frames[-1]['params']['turn'].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'native turn completion'):
                self.run_audit(frames=frames)
        frames = copy.deepcopy(self.frames)
        frames[-1]['params']['turn'].update(itemsView='summary', items=[copy.deepcopy(frames[-2]['params']['item'])])
        self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')
        for index in (4, -1):
            frames = copy.deepcopy(self.frames)
            frames[index]['params']['hidden'] = hidden
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'native turn (start|completion) params'):
                self.run_audit(frames=frames)

    def test_new_thread_start_history_and_ephemeral_state_are_checked(self):
        hidden = [{'id': 'extra-turn', 'status': 'failed', 'error': {'message': 'failure'},
                   'items': [{'type': 'commandExecution', 'id': 'hidden-command'}]}]
        for index in (1, 2):
            for field, value in (('turns', hidden), ('turns', None), ('turns', {}), ('turns', False),
                                 ('ephemeral', False), ('ephemeral', 1)):
                frames = copy.deepcopy(self.frames)
                frames[index]['result' if index == 1 else 'params']['thread'][field] = value
                with self.subTest(index=index, field=field, value=value), self.assertRaisesRegex(ValueError, 'native thread start'):
                    self.run_audit(frames=frames)
            frames = copy.deepcopy(self.frames)
            frames[index]['result' if index == 1 else 'params']['thread'].update(turns=[], ephemeral=True)
            self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')

    def test_thread_start_objects_reject_error_status_in_response_and_notification(self):
        for index in (1, 2):
            for status in ({'type': 'systemError'}, {'type': 'unknown'},
                           {'type': 'active', 'activeFlags': ['waitingOnUserInput']}, None):
                frames = copy.deepcopy(self.frames)
                frames[index]['result' if index == 1 else 'params']['thread']['status'] = status
                with self.subTest(index=index, status=status), self.assertRaisesRegex(ValueError, 'native thread error or unsupported status'):
                    self.run_audit(frames=frames)
            frames = copy.deepcopy(self.frames)
            frames[index]['result' if index == 1 else 'params']['thread']['status'] = {'type': 'idle'}
            self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')

    def test_thread_status_rejects_system_errors_unknown_states_and_waiting_flags(self):
        for status in ({'type': 'idle'}, {'type': 'active', 'activeFlags': []}):
            event = {'method': 'thread/status/changed', 'params': {'threadId': 't', 'status': status}}
            self.assertEqual(self.run_audit(frames=self.frames[:5] + [event] + self.frames[5:])['status'],
                             'measurement_integrity_passed')
        for status in ({'type': 'systemError'}, {'type': 'unknown'}, {'type': 'active'},
                       {'type': 'active', 'activeFlags': ['waitingOnApproval']},
                       {'type': 'active', 'activeFlags': ['waitingOnUserInput']},
                       {'type': 'idle', 'error': 'failure'}, None):
            for location in (5, len(self.frames)):
                event = {'method': 'thread/status/changed', 'params': {'threadId': 't', 'status': status}}
                with self.subTest(status=status, location=location), \
                        self.assertRaisesRegex(ValueError, 'native thread error or unsupported status'):
                    self.run_audit(frames=self.frames[:location] + [event] + self.frames[location:])
        event = {'method': 'thread/status/changed', 'params': {'threadId': 't', 'status': {'type': 'active', 'activeFlags': []}}}
        with self.assertRaisesRegex(ValueError, 'native active status after completion'):
            self.run_audit(frames=self.frames + [event])

    def test_turn_start_response_and_notification_reject_failed_or_incomplete_state(self):
        for index in (3, 4):
            for field, value in (('status', 'failed'), ('status', 'interrupted'), ('status', 'completed'),
                                 ('error', {'message': 'failure'}), ('error', False), ('items', [{}]),
                                 ('completedAt', 0), ('durationMs', 0), ('startedAt', False), ('unknown', None)):
                frames = copy.deepcopy(self.frames)
                turn = frames[index]['result' if index == 3 else 'params']['turn']
                turn[field] = value
                with self.subTest(index=index, field=field, value=value), self.assertRaisesRegex(ValueError, 'native turn start'):
                    self.run_audit(frames=frames)
            frames = copy.deepcopy(self.frames)
            frames[index]['result' if index == 3 else 'params']['turn'].pop('status')
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'native turn start fields'):
                self.run_audit(frames=frames)

    def test_reasoning_initial_text_and_multiple_indices_are_preserved(self):
        before = copy.deepcopy(self.prefixed_reasoning_events())
        frames = self.frames[:-3] + before + self.frames[-3:]
        self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')
        self.assertEqual(before, self.prefixed_reasoning_events())

    def test_reasoning_deltas_must_match_completed_content_and_summary(self):
        for index in (2, 3):
            reason = self.reasoning_events()
            reason[index]['params']['delta'] = '改変した本文'
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'native streamed body mismatch'):
                self.run_audit(frames=self.frames[:-3] + reason + self.frames[-3:])

    def test_reasoning_indices_cannot_skip_or_recreate_parts(self):
        for index in (1, 2, 3):
            reason = self.reasoning_events()
            key = 'contentIndex' if index == 3 else 'summaryIndex'
            reason[index]['params'][key] = 2
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'native reasoning index lifecycle'):
                self.run_audit(frames=self.frames[:-3] + reason + self.frames[-3:])
        reason = self.reasoning_events()
        with self.assertRaisesRegex(ValueError, 'native reasoning index lifecycle'):
            self.run_audit(frames=self.frames[:-3] + reason[:2] + reason[1:] + self.frames[-3:])

    def test_reasoning_body_types_missing_completed_body_and_hidden_start_are_checked(self):
        for key in ('content', 'summary'):
            for value in (None, [1], '本文'):
                reason = self.reasoning_events()
                reason[-1]['params']['item'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.run_audit(frames=self.frames[:-3] + reason + self.frames[-3:])
            reason = self.reasoning_events()
            reason[0]['params']['item'][key] = None
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'native reasoning start body unavailable'):
                self.run_audit(frames=self.frames[:-3] + reason + self.frames[-3:])

    def test_common_agent_delta_matches_final_body_and_rejects_drift(self):
        for text, valid in ((self.frames[-2]['params']['item']['text'], True), ('改変した応答', False)):
            delta = {'method': 'item/agentMessage/delta', 'params': {
                'threadId': 't', 'turnId': 'u', 'itemId': 'final', 'delta': text}}
            frames = self.frames[:-2] + [delta] + self.frames[-2:]
            if valid:
                self.assertEqual(self.run_audit(frames=frames)['status'], 'measurement_integrity_passed')
            else:
                with self.assertRaisesRegex(ValueError, 'native streamed body mismatch'):
                    self.run_audit(frames=frames)

    def test_reasoning_increments_require_an_active_item_and_unfinished_turn(self):
        reason = self.reasoning_events()
        for delta in reason[1:4]:
            for placement in ('before', 'after', 'after-turn', 'unknown'):
                if placement == 'before': frames = self.frames[:-3] + [delta] + reason + self.frames[-3:]
                if placement == 'after': frames = self.frames[:-3] + reason + [delta] + self.frames[-3:]
                if placement == 'after-turn': frames = self.frames[:-3] + reason + self.frames[-3:] + [delta]
                if placement == 'unknown':
                    changed = copy.deepcopy(delta)
                    changed['params']['itemId'] = 'phantom'
                    frames = self.frames[:-3] + reason[:1] + [changed] + reason[1:] + self.frames[-3:]
                with self.subTest(method=delta['method'], placement=placement), self.assertRaisesRegex(ValueError, 'native increment outside'):
                    self.run_audit(frames=frames)

    def test_reasoning_increment_fields_types_and_indices_are_checked(self):
        reason = self.reasoning_events()
        for delta in reason[1:4]:
            index = 'contentIndex' if 'contentIndex' in delta['params'] else 'summaryIndex'
            changes = [('missing', None), ('extra', True), (index, False), (index, -1), (index, 0.0)]
            if 'delta' in delta['params']: changes.append(('delta', None))
            for key, value in changes:
                changed = copy.deepcopy(delta)
                if key == 'missing': changed['params'].pop(index)
                else: changed['params'][key] = value
                frames = self.frames[:-3] + reason[:1] + [changed] + reason[1:] + self.frames[-3:]
                with self.subTest(method=delta['method'], key=key, value=value), self.assertRaisesRegex(ValueError, 'native increment'):
                    self.run_audit(frames=frames)

    def test_agent_deltas_cannot_target_unknown_completed_or_reasoning_items(self):
        delta = {'method': 'item/agentMessage/delta', 'params': {
            'threadId': 't', 'turnId': 'u', 'itemId': 'final', 'delta': '合成増分'}}
        reason = self.reasoning_events()
        wrong_kind = copy.deepcopy(delta)
        wrong_kind['params']['itemId'] = 'reason'
        for frames in (self.frames[:-3] + [delta] + self.frames[-3:],
                       self.frames[:-1] + [delta] + self.frames[-1:], self.frames + [delta],
                       self.frames[:-3] + reason[:1] + [wrong_kind] + reason[1:] + self.frames[-3:]):
            with self.assertRaisesRegex(ValueError, 'native increment outside'):
                self.run_audit(frames=frames)

    def test_only_request_and_context_are_projected(self):
        case = {'prompt': '公開の合成要求', 'context': ['公開の文脈'], 'caseId': 'hidden',
                'expected': {'reason': 'SECRET_EXPECTED'}, 'category': 'SECRET_CATEGORY', 'control': 'SECRET_CONTROL'}
        projected = audit.project_case(case)
        self.assertEqual(projected, {'prompt': case['prompt'], 'context': case['context']})
        self.assertNotIn('SECRET_', json.dumps(projected))
        projected['context'].append('change')
        self.assertEqual(case['context'], ['公開の文脈'])

    def test_native_result_cannot_replace_json_number_with_boolean(self):
        for number, boolean in ((1, True), (0, False)):
            manifest = {**self.manifest, 'candidateVersion': number}
            raw = json.dumps(manifest).encode()
            log = copy.deepcopy(self.log)
            log[0]['result'] = audit.manifest_view(raw)[2]
            frames = self.make_frames(log, self.decision)
            self.assertEqual(self.run_audit(manifest_raw=raw, host_events=log, frames=frames)['status'],
                             'measurement_integrity_passed')
            for item in audit.completed_items(frames):
                if item.get('tool') == 'list_resources':
                    item['result']['content'][0]['text'] = json.dumps({**log[0]['result'], 'candidateVersion': boolean})
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, 'host/native result mismatch'):
                self.run_audit(manifest_raw=raw, host_events=log, frames=frames)

    def test_structured_result_cannot_replace_json_number_with_boolean(self):
        manifest = {**self.manifest, 'candidateVersion': 1}
        raw = json.dumps(manifest).encode()
        log = copy.deepcopy(self.log)
        log[0]['result'] = audit.manifest_view(raw)[2]
        frames = self.make_frames(log, self.decision)
        frames[6]['params']['item']['result']['structuredContent'] = {**log[0]['result'], 'candidateVersion': True}
        with self.assertRaisesRegex(ValueError, 'native extra result'):
            self.run_audit(manifest_raw=raw, host_events=log, frames=frames)

    def test_host_result_cannot_replace_json_number_with_boolean(self):
        manifest = {**self.manifest, 'candidateVersion': 1}
        raw = json.dumps(manifest).encode()
        log = copy.deepcopy(self.log)
        log[0]['result'] = {**audit.manifest_view(raw)[2], 'candidateVersion': True}
        with self.assertRaisesRegex(ValueError, 'host discovery mismatch'):
            self.run_audit(manifest_raw=raw, host_events=log)

    def test_final_decision_boolean_cannot_be_replaced_with_integer(self):
        frames = copy.deepcopy(self.frames)
        frames[-2]['params']['item']['text'] = json.dumps({**self.decision, 'readyClaimed': 0})
        with self.assertRaisesRegex(ValueError, 'final response mismatch'):
            self.run_audit(frames=frames)

    def test_outer_turn_id_cannot_contradict_start_or_completion(self):
        for method in ('turn/started', 'turn/completed'):
            frames = copy.deepcopy(self.frames)
            next(f for f in frames if f.get('method') == method)['params']['turnId'] = 'other'
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, 'native (turn start outer context|outer turn) mismatch'):
                self.run_audit(frames=frames)

    def test_thread_start_cannot_claim_a_different_thread_or_future_turn(self):
        for name, value in [('threadId', 'other'), ('turnId', 'u')]:
            frames = copy.deepcopy(self.frames)
            next(f for f in frames if f.get('method') == 'thread/started')['params'][name] = value
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'native thread start outer context mismatch'):
                self.run_audit(frames=frames)

    def test_json_object_key_order_is_not_an_evidence_difference(self):
        for frame in self.frames:
            item = frame.get('params', {}).get('item', {})
            if item.get('result'):
                value = json.loads(item['result']['content'][0]['text'])
                item['result']['content'][0]['text'] = json.dumps(dict(reversed(list(value.items()))))
        self.assertEqual(self.run_audit()['status'], 'measurement_integrity_passed')

    def test_generic_host_module_is_not_imported_or_replaced(self):
        sentinel = types.ModuleType('host')
        with patch.dict(sys.modules, {'host': sentinel}):
            spec = importlib.util.spec_from_file_location('isolated_production_trace', ROOT / 'evals/skills/routing/production_trace.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertIs(sys.modules['host'], sentinel)
            self.assertEqual(module.SKILLS, host.SKILLS)

    def test_nested_context_and_blank_request_are_rejected(self):
        for case in [{'prompt': ' ', 'context': []}, {'prompt': 'x', 'context': [{'expected': 'hidden'}]},
                     {'prompt': 'x', 'context': 'hidden'}]:
            with self.subTest(case=case), self.assertRaises(ValueError):
                audit.project_case(case)

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        for raw in ['{"nested":{"a":1,"a":2}}', '{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                audit.strict_json(raw)

    def test_real_host_log_matches_synthetic_native_trace(self):
        result = self.run_audit()
        self.assertEqual(result['status'], 'measurement_integrity_passed')
        self.assertTrue(result['selectedSkillBodyRead'])
        self.assertFalse(result['certifiesExpectedDecision'])
        self.assertFalse(result['certifiesBehavior'])
        self.assertFalse(result['certifiesSkillGate'])

    def test_commentary_missing_or_unknown_phase_cannot_replace_final(self):
        for phase in ['commentary', 'unknown', None]:
            frames = copy.deepcopy(self.frames)
            for frame in frames:
                item = frame.get('params', {}).get('item', {})
                if item.get('type') == 'agentMessage':
                    if phase is None:
                        item.pop('phase', None)
                    else:
                        item['phase'] = phase
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_final_phase_is_bound_between_start_and_completion(self):
        frames = copy.deepcopy(self.frames)
        frames[9]['params']['item']['phase'] = 'commentary'
        with self.assertRaises(ValueError):
            self.run_audit(frames=frames)

    def test_selected_body_must_complete_before_final_starts(self):
        for frames in [self.frames[:7] + self.frames[9:11] + self.frames[7:9] + self.frames[11:],
                       self.frames[:8] + [self.frames[9], self.frames[8], self.frames[10], self.frames[11]]]:
            with self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_invalid_or_missing_manifest_scope_and_schema_are_rejected(self):
        for key, value in [('scope', 'not-production'), ('schemaVersion', 'invalid'),
                           ('scope', None), ('schemaVersion', None)]:
            manifest = copy.deepcopy(self.manifest)
            if value is None:
                manifest.pop(key)
            else:
                manifest[key] = value
            raw = json.dumps(manifest).encode()
            log = copy.deepcopy(self.log)
            log[0]['result']['manifestSha256'] = hashlib.sha256(raw).hexdigest()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.run_audit(manifest_raw=raw, host_events=log, frames=self.make_frames(log, self.decision))

    def test_commentary_before_read_and_final_is_supported(self):
        start = {'method': 'item/started', 'params': {'threadId': 't', 'turnId': 'u',
                 'item': {'type': 'agentMessage', 'id': 'progress', 'phase': 'commentary', 'text': ''}}}
        completed = copy.deepcopy(start)
        completed['method'] = 'item/completed'
        completed['params']['item']['text'] = '調査します。'
        result = self.run_audit(frames=self.frames[:5] + [start, completed] + self.frames[5:])
        self.assertEqual(result['status'], 'measurement_integrity_passed')

    def test_none_selection_can_complete_without_skill_read(self):
        decision = {**self.decision, 'selectedEntry': None, 'selectedPath': None, 'outcome': 'not-applicable'}
        result = self.run_audit(host_events=[], frames=self.make_frames([], decision), decision=decision)
        self.assertFalse(result['selectedSkillBodyRead'])

    def test_private_manifest_extra_fields_cannot_enter_discovery(self):
        log = copy.deepcopy(self.log)
        log[0]['result']['notForModel'] = 'HIDDEN_EXPECTATION_SENTINEL'
        with self.assertRaises(ValueError):
            self.run_audit(host_events=log, frames=self.make_frames(log, self.decision))

    def test_host_denials_sequence_gaps_and_boolean_sequence_are_rejected(self):
        for patch in [{'accepted': False}, {'accepted': 1}, {'sequence': 2}, {'sequence': True}]:
            log = copy.deepcopy(self.log)
            log[0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.run_audit(host_events=log)

    def test_read_without_discovery_is_rejected(self):
        log = [copy.deepcopy(self.log[1])]
        log[0]['sequence'] = 1
        with self.assertRaises(ValueError):
            self.run_audit(host_events=log, frames=self.make_frames(log, self.decision))

    def test_resource_content_drift_is_rejected_even_if_traces_agree(self):
        log = copy.deepcopy(self.log)
        log[1]['result']['content'] += '改変'
        with self.assertRaises(ValueError):
            self.run_audit(host_events=log, frames=self.make_frames(log, self.decision))

    def test_selected_skill_must_have_been_read(self):
        log = [self.log[0]]
        with self.assertRaises(ValueError):
            self.run_audit(host_events=log, frames=self.make_frames(log, self.decision))

    def test_native_tool_server_arguments_and_result_drift_are_rejected(self):
        for key, value in [('server', 'other'), ('tool', 'shell'), ('arguments', {'path': 'other'}),
                           ('result', {'content': [{'type': 'text', 'text': '{}'}]}), ('status', 'failed')]:
            frames = copy.deepcopy(self.frames)
            frames[6]['params']['item'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_extra_or_missing_native_calls_are_rejected(self):
        with self.assertRaises(ValueError):
            self.run_audit(host_events=[self.log[0]])

    def test_builtin_shell_and_file_changes_are_rejected(self):
        for kind in ['commandExecution', 'fileChange', 'webSearch', 'dynamicToolCall']:
            frames = copy.deepcopy(self.frames)
            frames[5]['params']['item']['type'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_duplicate_items_and_missing_item_start_are_rejected(self):
        for frames in [self.frames[:7] + [self.frames[6]] + self.frames[7:], self.frames[:5] + self.frames[6:]]:
            with self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_cross_thread_and_cross_turn_items_are_rejected(self):
        for key in ['threadId', 'turnId']:
            frames = copy.deepcopy(self.frames)
            frames[6]['params'][key] = 'other'
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_audit(frames=frames)

    def test_failed_truncated_and_second_turn_traces_are_rejected(self):
        frames = copy.deepcopy(self.frames)
        frames[-1]['params']['turn']['status'] = 'failed'
        for trace in [frames, self.frames[:-1], self.frames + [self.frames[4]]]:
            with self.assertRaises(ValueError):
                self.run_audit(frames=trace)

    def test_unknown_notifications_and_late_actions_are_rejected(self):
        for extra in [{'method': 'unknown', 'params': {'threadId': 't'}}, self.frames[5]]:
            with self.assertRaises(ValueError):
                self.run_audit(frames=self.frames + [extra])

    def test_nonzero_process_and_boolean_exit_are_rejected(self):
        for code in [1, -15, False]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.run_audit(actual_exit_code=code)

    def test_final_response_and_event_catalog_binding_are_required(self):
        with self.assertRaises(ValueError):
            self.run_audit(decision={**self.decision, 'reason': 'different'})
        decision = {**self.decision, 'events': ['unknown']}
        with self.assertRaises(ValueError):
            self.run_audit(decision=decision, frames=self.make_frames(self.log, decision))

    def test_aggregator_entries_and_wrong_product_path_are_rejected(self):
        for changes in [{'selectedEntry': 'bitz-sdd'}, {'selectedPath': 'review'}]:
            decision = {**self.decision, **changes}
            with self.subTest(changes=changes), self.assertRaises((ValueError, audit.jsonschema.ValidationError)):
                self.run_audit(decision=decision, frames=self.make_frames(self.log, decision))


if __name__ == '__main__':
    unittest.main()
