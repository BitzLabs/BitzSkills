"""可変ID・セルと実読取りの限定相関を合成軌跡で検査する。実provider起動0。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_trace as canary
import production_sdk_trace as sdk
import test_production_sdk_trace as fixture


def completion_event(last, thread='t'):
    return dict(timestamp='2026-10-11T17:16:47.198123Z',level='INFO',target='codex_otel.trace_safe',fields={
        'event.name':'codex.sse_event','event.kind':'response.completed',
        'input_token_count':str(last['inputTokens']),'output_token_count':str(last['outputTokens']),
        'cached_token_count':last['cachedInputTokens'],'cache_write_token_count':last['cacheWriteInputTokens'],
        'reasoning_token_count':last['reasoningOutputTokens'],'tool_token_count':str(last['totalTokens']),
        'ttft_ms':10,'model_reasoning_effort':'low','event.timestamp':'2026-10-11T17:16:47.198Z',
        'conversation.id':thread,'app.version':'0.160.1','auth_mode':'Chatgpt',
        'originator':'codex_python_sdk','terminal.type':'unknown','model':'gpt-6.1-sol','slug':'gpt-6.1-sol'})


class PrimaryCanaryTraceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CanaryTraceTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.schema = json.loads((ROOT / 'evals/skills/schemas/decision.schema.json').read_bytes())
        self.schema['properties']['selectedEntry']['enum'] = [None, *sorted(canary.trace.SKILLS)]
        self.fixture.sent[2]['params'].update(modelProvider='bitz_openai_http', experimentalRawEvents=True)
        self.fixture.received[1]['result']['modelProvider'] = 'bitz_openai_http'
        self.fixture.sent[3]['params'].update(outputSchema=copy.deepcopy(self.schema), effort='low')
        original_events = self.fixture.events
        def primary_events(profile):
            events = original_events(profile)
            for event in events:
                if event['fields'].get('event.name') == 'codex.tool_result':event['fields']['auth_mode']='Chatgpt'
                if event['fields'].get('event.name') == 'codex.api_request':
                    event['fields'].update(endpoint='/responses', model='gpt-6.1-sol', **{'app.version': '0.160.1'})
            return events
        self.fixture.events = primary_events

    def check(self, **changes):
        return self.fixture.check(sdk_profile='public-canary', output_schema=self.schema, **changes)

    def test_primary_profiles_preserve_original_params_and_do_not_certify(self):
        before = copy.deepcopy((self.fixture.sent, self.fixture.received))
        for profile in ['single-exec', 'two-exec', 'exec-wait']:
            result = self.check(profile=profile)
            self.assertEqual(result['hostCalls'], 2)
            self.assertFalse(result['eligibleForMeasurement'])
            self.assertFalse(result['certifiesSkillGate'])
        self.assertEqual((self.fixture.sent, self.fixture.received), before)

    def test_primary_auth_metadata_is_bound_without_allowing_unknown_fields(self):
        events=self.fixture.events('two-exec')
        before=copy.deepcopy(events)
        self.check(profile='two-exec',events=events)
        self.assertEqual(events,before)
        for fault in ['missing','type','value','unknown']:
            changed=copy.deepcopy(events)
            f=next(e['fields'] for e in changed if e['fields']['event.name']=='codex.tool_result')
            if fault=='missing':del f['auth_mode']
            elif fault=='type':f['auth_mode']=True
            elif fault=='value':f['auth_mode']='ApiKey'
            else:f['unknown_auth']=True
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.check(profile='two-exec',events=changed)

    def test_completion_telemetry_usage_count_context_and_order_are_bound(self):
        last=dict(inputTokens=10,cachedInputTokens=2,cacheWriteInputTokens=0,outputTokens=5,reasoningOutputTokens=1,totalTokens=15)
        frame=dict(method='thread/tokenUsage/updated',params=dict(threadId='t',turnId='u',
            tokenUsage=dict(last=last,total=last,modelContextWindow=100)))
        api=dict(level='INFO',target='codex_otel.trace_safe',fields={'event.name':'codex.api_request'})
        events=[api,completion_event(last)]
        before=copy.deepcopy((events,frame))
        self.assertEqual(canary.primary_usage_telemetry(events,[frame],'t','u',[0])['count'],1)
        self.assertEqual((events,frame),before)
        for fault in ['missing','duplicate','extra','kind','context','auth','model','version','effort','origin',
                'timestamp','outer-timestamp','ttft','decimal-type','decimal-negative','decimal-leading-zero','cached-bool',
                'arithmetic','native-count','native-context','native-total','order']:
            changed=copy.deepcopy(events);frames=[copy.deepcopy(frame)];indices=[0];f=changed[1]['fields']
            if fault=='missing':changed.pop()
            elif fault=='duplicate':changed.append(copy.deepcopy(changed[1]))
            elif fault=='extra':f['unknown']=True
            elif fault=='kind':f['event.kind']='response.failed'
            elif fault=='context':f['conversation.id']='other'
            elif fault=='auth':f['auth_mode']=True
            elif fault=='model':f['model']='other'
            elif fault=='version':f['app.version']='other'
            elif fault=='effort':f['model_reasoning_effort']='high'
            elif fault=='origin':f['originator']='other'
            elif fault=='timestamp':f['event.timestamp']='2026-99-99T17:16:47.198Z'
            elif fault=='outer-timestamp':changed[1]['timestamp']='2026-10-11T17:16:48.198123Z'
            elif fault=='ttft':f['ttft_ms']=False
            elif fault=='decimal-type':f['input_token_count']=10
            elif fault=='decimal-negative':f['input_token_count']='-1'
            elif fault=='decimal-leading-zero':f['input_token_count']='010'
            elif fault=='cached-bool':f['cached_token_count']=True
            elif fault=='arithmetic':f['tool_token_count']='16'
            elif fault=='native-count':frames=[]
            elif fault=='native-context':frames[0]['params']['turnId']='other'
            elif fault=='native-total':frames[0]['params']['tokenUsage']['total']['inputTokens']=11
            else:changed.reverse();indices=[1]
            with self.subTest(fault=fault),self.assertRaises(ValueError):canary.primary_usage_telemetry(changed,frames,'t','u',indices)

    def test_primary_thread_policy_overrides_and_missing_raw_events_rejected(self):
        for key, value in [('experimentalRawEvents', False), ('experimentalRawEvents', 1),
                           ('model', 'other-model'), ('modelProvider', 'openai'),
                           ('sandbox', 'workspace-write'), ('approvalPolicy', 'on-request'),
                           ('allowProviderModelFallback', True), ('ephemeral', False), ('unknown', True)]:
            sent = copy.deepcopy(self.fixture.sent)
            sent[2]['params'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(sent=sent)
        for key in self.fixture.sent[2]['params']:
            sent = copy.deepcopy(self.fixture.sent)
            del sent[2]['params'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError): self.check(sent=sent)

    def test_primary_schema_effort_and_turn_overrides_rejected(self):
        for key, value in [('outputSchema', {}), ('effort', 'high'), ('effort', None),
                           ('model', 'gpt-6.1-sol'), ('sandbox', 'read-only')]:
            sent = copy.deepcopy(self.fixture.sent)
            sent[3]['params'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(sent=sent)
        for key in ['outputSchema', 'effort']:
            sent = copy.deepcopy(self.fixture.sent)
            del sent[3]['params'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError): self.check(sent=sent)

    def test_diagnostic_and_primary_profiles_are_not_interchangeable(self):
        with self.assertRaises(ValueError): sdk.requests(self.fixture.sent)
        legacy = copy.deepcopy(self.fixture.sent)
        del legacy[2]['params']['experimentalRawEvents']
        for key in ['outputSchema', 'effort']: del legacy[3]['params'][key]
        with self.assertRaises(ValueError): sdk.requests(legacy, profile='public-canary', output_schema=self.schema)
        for profile in ['unknown', None, True]:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                sdk.requests(self.fixture.sent, profile=profile, output_schema=self.schema)

    def test_primary_schema_pin_and_effective_provider_mismatch_rejected(self):
        wrong = copy.deepcopy(self.schema)
        wrong['properties']['selectedEntry']['enum'] = [None]
        with self.assertRaises(ValueError):
            sdk.requests(self.fixture.sent, profile='public-canary', output_schema=wrong)
        received = copy.deepcopy(self.fixture.received)
        received[1]['result']['modelProvider'] = 'openai'
        with self.assertRaises(ValueError): self.check(received=received)


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
