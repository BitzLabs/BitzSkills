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
                  {'id': 3, 'result': {'turn': {'id': 'u'}}},
                  notification('turn/started', turn={'id': 'u'})]
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

    def test_only_request_and_context_are_projected(self):
        case = {'prompt': '公開の合成要求', 'context': ['公開の文脈'], 'caseId': 'hidden',
                'expected': {'reason': 'SECRET_EXPECTED'}, 'category': 'SECRET_CATEGORY', 'control': 'SECRET_CONTROL'}
        projected = audit.project_case(case)
        self.assertEqual(projected, {'prompt': case['prompt'], 'context': case['context']})
        self.assertNotIn('SECRET_', json.dumps(projected))
        projected['context'].append('change')
        self.assertEqual(case['context'], ['公開の文脈'])

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
