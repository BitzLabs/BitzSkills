"""可変ID・セルと実読取りの限定相関を合成軌跡で検査する。実provider起動0。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_trace as canary
import test_production_sdk_trace as fixture


class CanaryTraceTests(unittest.TestCase):
    def setUp(self):
        self.original = fixture.ProductionSdkTraceTests(methodName='runTest')
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.sent, self.received = copy.deepcopy((self.original.sent, self.original.frames))
        self.sent[2]['params'].update(modelProvider='openai', cwd='/fixed/work',
                                      baseInstructions='Fixed public instructions', developerInstructions='Fixed common context')
        self.received[1]['result']['modelProvider'] = 'openai'
        self.host = copy.deepcopy(self.original.original.log)
        self.catalog = copy.deepcopy(self.original.original.catalog)

    def events(self, profile):
        if profile == 'two-exec': result = self.original.sequential_parent_events()
        elif profile == 'exec-wait': result = self.original.yielded_parent_events()
        else:
            result = self.original.parent_events()
            api = {'level': 'INFO', 'target': 'codex_otel.trace_safe', 'fields': {
                'event.name': 'codex.api_request', 'conversation.id': 't', 'auth.header_attached': False,
                'attempt': 0, 'http.response.status_code': 200}}
            result = [copy.deepcopy(api), *result, copy.deepcopy(api)]
        parent_map = {'probe-call': 'actual-parent-a', 'probe-read': 'actual-parent-b', 'probe-wait': 'actual-parent-wait'}
        for event in result:
            f = event['fields']
            if f.get('call_id') in parent_map: f['call_id'] = parent_map[f['call_id']]
            for key in ['cell.id', 'cell_id']:
                if key in f: f[key] = {'1': 'cell-alpha', '2': 'cell-beta'}[f[key]]
            if f.get('event.name') == 'codex.api_request': f['auth.header_attached'] = True
        return result

    def check(self, profile='single-exec', **changes):
        events = changes.pop('events', self.events(profile))
        selected = b''.join(json.dumps(event).encode() + b'\n' for event in events)
        args = dict(manifest_raw=self.original.original.raw, host_events=self.host,
                    sent=self.sent, received=self.received, raw_stderr=selected, selected_log=selected, catalog=self.catalog,
                    profile=profile, expected_input=self.sent[3]['params']['input'][0]['text'].encode(),
                    base_instructions='Fixed public instructions', developer_instructions='Fixed common context',
                    cwd='/fixed/work', actual_exit_code=0)
        args.update(changes)
        return canary.audit(**args)

    def test_variable_parent_ids_and_cells_pass_without_aliasing_or_certification(self):
        for profile in ['single-exec', 'two-exec', 'exec-wait']:
            events = self.events(profile)
            before = copy.deepcopy((events, self.sent, self.received, self.host))
            result = self.check(profile, events=events)
            self.assertEqual(result['parentCallIds'][0], 'actual-parent-a')
            self.assertEqual(result['parentLinks']['cellId'], 'cell-alpha')
            self.assertFalse(result['eligibleForMeasurement'])
            self.assertFalse(result['certifiesProviderWireBodies'])
            self.assertEqual((events, self.sent, self.received, self.host), before)

    def test_context_input_policy_and_exit_mismatch_stop(self):
        for args in [dict(expected_input=b'changed'), dict(base_instructions='changed'),
                     dict(developer_instructions='changed'), dict(cwd='/another'), dict(actual_exit_code=True),
                     dict(actual_exit_code=1), dict(profile='parallel')]:
            with self.subTest(args=args), self.assertRaises(ValueError): self.check(**args)

    def test_unknown_parent_cell_api_and_original_body_mismatch_stop(self):
        for fault in ['extra-api', 'retry', 'auth', 'auth-retry', 'model', 'version', 'provider', 'parent-id', 'cell', 'unknown-event', 'body']:
            events = self.events('two-exec')
            host = copy.deepcopy(self.host)
            if fault == 'extra-api': events.append(copy.deepcopy(events[0]))
            elif fault == 'retry': events[0]['fields']['attempt'] = 1
            elif fault == 'auth': events[0]['fields']['auth.header_attached'] = False
            elif fault == 'auth-retry': events[0]['fields']['auth.retry_after_unauthorized'] = True
            elif fault == 'model': events[0]['fields']['model'] = 'other-model'
            elif fault == 'version': events[0]['fields']['app.version'] = 'unknown'
            elif fault == 'provider': events[0]['fields']['provider_name'] = 'Other provider'
            elif fault == 'parent-id':
                next(e['fields'] for e in events if e['fields']['event.name'] == 'codex.code_mode.host_timing')['call_id'] = 'another'
            elif fault == 'cell':
                next(e['fields'] for e in events if e['fields']['event.name'] == 'codex.code_mode.nested_tool_dispatched')['cell.id'] = 'wrong'
            elif fault == 'unknown-event': events.append({'level':'INFO','target':'codex_otel.trace_safe','fields':{'event.name':'unknown'}})
            else: host[-1]['result']['content'] += 'changed'
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.check('two-exec', events=events, host_events=host)

    def negative(self, *, listed):
        received = copy.deepcopy(self.received)
        host = self.host[:1] if listed else []
        decision = {**self.original.original.decision, 'selectedEntry': None, 'selectedPath': None,
                    'outcome': 'not-applicable', 'reason': '公開合成負例'}
        kept = []
        for frame in received:
            item = frame.get('params', {}).get('item', {})
            if item.get('type') == 'mcpToolCall' and (not listed or item['tool'] == 'read_resource'):
                continue
            if item.get('type') == 'agentMessage' and frame['method'] == 'item/completed': item['text'] = json.dumps(decision)
            if frame.get('method') == 'turn/completed':
                frame['params']['turn']['items'][0]['text'] = json.dumps(decision)
            kept.append(frame)
        events = self.events('single-exec')
        if listed:
            events = [event for event in events if event['fields'].get('call_id') != 'call-1']
        else:
            events = [events[0]]
        return kept, host, events

    def test_explicit_runtime_contradictions_on_every_original_event_stop(self):
        for profile in ['single-exec', 'two-exec', 'exec-wait']:
            original = self.events(profile)
            for index, event in enumerate(original):
                for key, wrong in [('model', 'other-model'), ('app.version', 'unknown'), ('provider_name', 'Other provider')]:
                    events = copy.deepcopy(original)
                    events[index]['fields'][key] = wrong
                    with self.subTest(profile=profile, event=event['fields']['event.name'], key=key):
                        with self.assertRaisesRegex(ValueError, 'canary runtime context contradiction'):
                            self.check(profile, events=events)
        events = self.events('single-exec')
        for event in events:
            if event['fields']['event.name'] == 'codex.tool_result':
                event['fields'].update(model='gpt-6.1-sol', **{'app.version': '0.160.1'})
        self.assertFalse(self.check(events=events)['eligibleForMeasurement'])

    def test_negative_no_operation_or_listing_only_keeps_body_read_zero(self):
        for listed in [False, True]:
            received, host, events = self.negative(listed=listed)
            result = self.check('single-exec' if listed else 'no-exec', received=received, host_events=host, events=events)
            self.assertIsNone(result['decision']['selectedEntry'])
            self.assertEqual(result['hostCalls'], 1 if listed else 0)
            self.assertFalse(result['eligibleForMeasurement'])

    def test_negative_cannot_hide_original_body_read_or_unknown_action(self):
        received, _, events = self.negative(listed=False)
        with self.assertRaises(ValueError): self.check('no-exec', received=received, events=events)
        unknown = copy.deepcopy(events)
        unknown.append({'level':'INFO','target':'codex_otel.trace_safe','fields':{'event.name':'codex.tool_call_received',
                       'conversation.id':'t','call_id':'hidden','tool_source':'direct','tool_name':'exec'}})
        with self.assertRaises(ValueError): self.check('no-exec', received=received, host_events=[], events=unknown)

    def test_original_stderr_extra_api_or_unknown_operation_cannot_be_omitted(self):
        events = self.events('single-exec')
        original = b''.join(json.dumps(event).encode() + b'\n' for event in events)
        for extra in [events[0], {'level':'INFO','target':'codex_otel.trace_safe','fields':{
                'event.name':'codex.tool_call_received','conversation.id':'t','call_id':'hidden-operation'}}]:
            raw = original + json.dumps(extra).encode() + b'\n'
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'selected telemetry incomplete'):
                self.check(raw_stderr=raw, selected_log=original)
            with self.subTest(extra=extra), self.assertRaises(ValueError): self.check(raw_stderr=raw, selected_log=raw)
        non_target = json.dumps({'target':'known.other.logger','message':'unrelated'}).encode() + b'\n'
        result = self.check(raw_stderr=non_target + original, selected_log=original)
        self.assertTrue(result['completeTargetProjectionVerified'])
        self.assertNotEqual(result['rawStderrSha256'], result['selectedLogSha256'])


if __name__ == '__main__':
    unittest.main()
