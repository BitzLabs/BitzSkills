"""私的原記録を複製せず、照合器の改変拒否を合成データで検証する。"""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'evals/skills/routing'))
import production_connection_evidence as evidence
import production_connection_probe as connection


class ConnectionEvidenceTests(unittest.TestCase):
    def fixture(self):
        manifest = dict(schema_version=1, root_thread_id='thread', raw_event_log='trace.jsonl',
                        payloads_dir='payloads', rollout_id='rollout')
        kinds = ['rollout_started', 'thread_started', 'codex_turn_started', 'inference_started',
                 'inference_completed', 'codex_turn_ended', 'thread_ended', 'rollout_ended']
        events = [dict(schema_version=1, seq=i, rollout_id='rollout', thread_id='thread', codex_turn_id='turn',
                       payload=dict(type=kind)) for i, kind in enumerate(kinds, 1)]
        events[3]['payload'].update(thread_id='thread', codex_turn_id='turn', model='gpt-6.1-sol',
            provider_name='OpenAI', inference_call_id='call', request_payload=dict(path='payloads/1.json', kind=dict(type='inference_request')))
        events[4]['payload'].update(inference_call_id='call', response_payload=dict(path='payloads/2.json', kind=dict(type='inference_response')))
        events[5]['payload']['status'] = 'completed'
        items = [dict(type='additional_tools', role='developer', tools=[dict(type='namespace', name='functions', tools=[
            dict(type='function', name=name) for name in ['exec', 'wait', 'request_user_input_async']])])]
        items += [dict(role=role, content=[dict(type='input_text', text=text)]) for role, text in [
            ('developer', connection.BASE), ('developer', connection.DEVELOPER), ('user', 'public context'), ('user', connection.PROMPT)]]
        request = dict(model='gpt-6.1-sol', input=items,
                       text=dict(format=dict(type='json_schema', strict=True, schema=connection.SCHEMA)))
        usage = dict(input_tokens=100, cached_input_tokens=0, cache_write_input_tokens=0,
                     output_tokens=10, reasoning_output_tokens=0, total_tokens=110)
        native = dict(inputTokens=100, cachedInputTokens=0, cacheWriteInputTokens=0,
                      outputTokens=10, reasoningOutputTokens=0, totalTokens=110)
        response = dict(token_usage=usage, output_items=[dict(type='message', role='assistant', phase='final_answer',
            content=[dict(type='output_text', text=json.dumps(connection.FINAL))])])
        return manifest, events, request, response, native

    def inspect(self, fixture):
        manifest, events, request, response, native = fixture
        return evidence.rollout_values(json.dumps(manifest).encode(),
            b'\n'.join(json.dumps(event).encode() for event in events),
            {'payloads/1.json': json.dumps(request).encode(), 'payloads/2.json': json.dumps(response).encode()},
            thread='thread', turn='turn', native_usage=native)

    def test_original_values_and_usage_match(self):
        result = self.inspect(self.fixture())
        self.assertEqual(result['rolloutEvents'], 8)
        self.assertEqual(result['tokenUsage']['total_tokens'], 110)
        self.assertEqual(len(result['requestPayloadSha256']), 64)

    def test_modified_sequence_context_input_response_and_usage_are_rejected(self):
        for mutation in ['sequence', 'missing-end', 'wrong-thread', 'wrong-turn', 'wrong-call', 'failed',
                         'escaping-reference', 'wrong-role', 'extra-tool', 'schema', 'prompt', 'final', 'usage', 'bool-usage']:
            fixture = copy.deepcopy(self.fixture())
            manifest, events, request, response, native = fixture
            if mutation == 'sequence': events[3]['seq'] = 1
            elif mutation == 'missing-end': events.pop()
            elif mutation == 'wrong-thread': events[3]['thread_id'] = 'other'
            elif mutation == 'wrong-turn': events[5]['codex_turn_id'] = 'other'
            elif mutation == 'wrong-call': events[4]['payload']['inference_call_id'] = 'other'
            elif mutation == 'failed': events[5]['payload']['status'] = 'failed'
            elif mutation == 'escaping-reference': events[3]['payload']['request_payload']['path'] = '../1.json'
            elif mutation == 'wrong-role': request['input'][-1]['role'] = 'assistant'
            elif mutation == 'extra-tool': request['input'][0]['tools'][0]['tools'].append(dict(type='function', name='other'))
            elif mutation == 'schema': request['text']['format']['strict'] = False
            elif mutation == 'prompt': request['input'][-1]['content'][0]['text'] = 'other'
            elif mutation == 'final': response['output_items'][0]['content'][0]['text'] = '{}'
            elif mutation == 'usage': response['token_usage']['total_tokens'] += 1
            elif mutation == 'bool-usage': response['token_usage']['cached_input_tokens'] = False
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                self.inspect(fixture)
