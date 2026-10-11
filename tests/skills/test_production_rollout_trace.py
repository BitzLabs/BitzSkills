"""要求投影の型・相関・欠落を合成入力で検査する。私的捕捉や実providerは使わない。"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_rollout_trace as rollout


class RolloutRequestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(schema_version=1, root_thread_id='thread', rollout_id='rollout',
                             raw_event_log='trace.jsonl', payloads_dir='payloads')
        self.request = dict(model='gpt-6.1-sol', input=[dict(role='developer', content='Fixed public instructions'),
                                                      dict(role='user', content='PUBLIC_DIAGNOSTIC')], stream=True)
        self.start = dict(type='inference_started', inference_call_id='call', thread_id='thread', codex_turn_id='turn',
                          model='gpt-6.1-sol', provider_name='Isolated local simulator',
                          request_payload=dict(kind={'type': 'inference_request'}, path='payloads/1.json'))
        self.events = [dict(schema_version=1, seq=i, rollout_id='rollout', thread_id='thread', codex_turn_id='turn',
                            payload=p) for i, p in enumerate([self.start,
                          dict(type='inference_completed', inference_call_id='call'),
                          dict(type='codex_turn_ended', codex_turn_id='turn', status='completed')], 1)]

    def check(self, *, manifest=None, events=None, payloads=None, wire=None):
        encoded = lambda v: json.dumps(v).encode()
        return rollout.compare_requests(encoded(self.manifest if manifest is None else manifest),
            b'\n'.join(encoded(e) for e in (self.events if events is None else events)),
            {'payloads/1.json': encoded(self.request)} if payloads is None else payloads,
            [encoded(self.request)] if wire is None else wire,
            thread_id='thread', turn_id='turn', model='gpt-6.1-sol', provider_name='Isolated local simulator')

    def test_original_values_match_without_certifying_wire_or_whole_trace(self):
        before = copy.deepcopy((self.manifest, self.request, self.events))
        result = self.check(wire=[json.dumps(self.request, indent=2).encode()])
        self.assertEqual(result['requests'], 1)
        self.assertFalse(result['eligibleForMeasurement'])
        self.assertFalse(result['certifiesWholeTrace'])
        self.assertEqual((self.manifest, self.request, self.events), before)

    def test_extra_instruction_missing_reference_and_bool_number_drift_stop(self):
        for mutate in [lambda r: r['input'].append(dict(role='developer', content='Hidden context')),
                       lambda r: r.update(stream=1), lambda r: r.update(model='other')]:
            changed = copy.deepcopy(self.request)
            mutate(changed)
            with self.assertRaises(ValueError): self.check(wire=[json.dumps(changed).encode()])
        with self.assertRaises(ValueError): self.check(payloads={})
        with self.assertRaises(ValueError): self.check(payloads={'../outside': b'{}'})

    def test_context_sequence_missing_terminal_and_unknown_inference_stop(self):
        for index, key, value in [(0, 'seq', True), (1, 'seq', 4), (0, 'thread_id', 'other'), (1, 'codex_turn_id', 'other'),
                                  (2, 'thread_id', 'other'), (2, 'codex_turn_id', 'other')]:
            events = copy.deepcopy(self.events)
            events[index][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(events=events)
        for field, value in [('provider_name', 'Other'), ('model', 'other'), ('inference_call_id', ''),
                             ('type', 'inference_failed')]:
            events = copy.deepcopy(self.events)
            events[0]['payload'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(events=events)
        for events in [self.events[:-1], [self.events[0], self.events[-1]]]:
            with self.assertRaises(ValueError): self.check(events=events)
        events = copy.deepcopy(self.events)
        events[1]['payload']['inference_call_id'] = 'other'
        with self.assertRaises(ValueError): self.check(events=events)

    def test_omitted_extra_or_post_terminal_attempt_cannot_be_accepted(self):
        extra = copy.deepcopy(self.events[:2])
        extra[0]['payload']['inference_call_id'] = extra[1]['payload']['inference_call_id'] = 'extra'
        for order in [self.events[:2] + extra + self.events[2:], self.events + extra]:
            events = copy.deepcopy(order)
            for i, e in enumerate(events, 1): e['seq'] = i
            with self.assertRaises(ValueError): self.check(events=events)


class RecordedCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'evals/skills/results/2026-10-11-sdk-rollout-trace-capture/verify-recorded-results.py'
        spec = importlib.util.spec_from_file_location('rollout_capture_record_test', path)
        cls.record = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.record)

    def test_every_used_original_file_must_be_hash_bound(self):
        inventory = {name: '0' * 64 for name in ['contract.json', 'rpc-out.jsonl', 'request-1.json', 'request-2.json', 'request-3.json']}
        self.record.require_artifact_membership(inventory, 3)
        for missing in inventory:
            bad = dict(inventory)
            del bad[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.record.require_artifact_membership(bad, 3)
        for count in [True, 0, 4]:
            with self.assertRaises(ValueError): self.record.require_artifact_membership(inventory, count)

    def test_role_only_input_does_not_require_type_and_unknown_role_stops(self):
        self.assertEqual(self.record.input_roles({'input': [{'role': 'developer'}, {'role': 'user'}, {'type': 'custom_tool_call'}]}),
                         ['developer', 'user', 'custom_tool_call'])
        for item in [{}, {'role': None}, {'role': True}, {'role': 'unknown_role'}, {'type': 'unknown_item'}]:
            with self.assertRaises(ValueError): self.record.input_roles({'input': [item]})


if __name__ == '__main__':
    unittest.main()
