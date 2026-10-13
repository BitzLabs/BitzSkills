"""固定入力と原SDK/native/host/finalの接続を合成原bytesで検証する。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_review as review
import test_production_canary_evidence as evidence_fixture
import test_production_canary_trace as trace_fixture


class CanaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.capture = evidence_fixture.CanaryEvidenceTests(methodName='runTest')
        if hasattr(self, 'context_profile_raw'):
            self.capture.context_profile_raw = self.context_profile_raw
        if hasattr(self,'cases_raw'):self.capture.cases_raw=self.cases_raw
        if hasattr(self,'instructions_raw'):self.capture.instructions_raw=self.instructions_raw
        self.addCleanup(self.capture.doCleanups)
        self.capture.setUp()
        self.trace = trace_fixture.PrimaryCanaryTraceTests(methodName='runTest')
        self.addCleanup(self.trace.doCleanups)
        self.trace.setUp()
        primary = self.trace.fixture
        primary.sent[3]['params']['outputSchema']=review.evidence.capture.execution_schema(json.loads(self.capture.fixed.decision_schema_raw))
        primary.sent[2]['params'].update(cwd=str(self.capture.base / 'work'),
            baseInstructions=review.evidence.capture.BASE, developerInstructions=review.evidence.capture.DEVELOPER)
        primary.sent[3]['params']['input'][0]['text'] = self.capture.originals['model-input.json'].decode()
        for frame in primary.received:
            if frame.get('params', {}).get('item', {}).get('type') == 'userMessage':
                frame['params']['item']['content'][0]['text'] = primary.sent[3]['params']['input'][0]['text']

    def save(self, profile='single-exec', *, sent=None, received=None, events=None, host=None):
        primary = self.trace.fixture
        sent = copy.deepcopy(primary.sent if sent is None else sent)
        received = copy.deepcopy(primary.received if received is None else received)
        events = primary.events(profile) if events is None else events
        if not any(f.get('method') in review.sdk.RAW_METHODS for f in received):
            raw = [dict(method='rawResponseItem/completed', params=dict(threadId='t', turnId='u',
                       item=dict(type='message', id='raw-public-input', role='user', content=[dict(type='input_text', text='public raw')])), emittedAtMs=1),
                   dict(method='rawResponse/completed', params=dict(threadId='t', turnId='u', responseId='response', usage=None, usageMetadata=None), emittedAtMs=1)]
            received[-1:-1] = raw
        host = primary.host if host is None else host
        originals = {'rpc-in.jsonl': sent, 'rpc-out.jsonl': received, 'host.jsonl': host,
                     'runtime-stderr.bin': events, 'trace-safe.jsonl': events}
        for name, values in originals.items():
            self.capture.rewrite(name, b''.join(review.evidence.ledger.encoded(value) + b'\n' for value in values))
        return review.evidence.load_verified_capture(self.capture.repository, self.capture.source, 1)

    def test_consumed_bytes_and_binding_cannot_be_mutated_after_loading(self):
        from dataclasses import replace
        context = self.save()
        with self.assertRaises(TypeError):
            context.originals['rpc-out.jsonl'] = b'changed'
        report = context.result
        report['artifactSha256']['rpc-out.jsonl'] = '0' * 64
        self.assertNotEqual(context.result, report)
        originals = dict(context.originals)
        originals['rpc-out.jsonl'] += review.evidence.ledger.encoded(dict(method='account/updated',
            params=dict(authMode='chatgpt', planType='plus'))) + b'\n'
        tampered = replace(context, original_items=tuple(originals.items()))
        with self.assertRaisesRegex(ValueError, 'consumed original artifact binding drift'):
            review.verify_native(tampered)

    def test_known_primary_profiles_use_fixed_input_host_and_native_final(self):
        for profile in ['single-exec', 'two-exec', 'exec-wait']:
            with self.subTest(profile=profile):
                result = review.verify_native(self.save(profile))
                self.assertEqual(result['native']['profile'], profile)
                self.assertEqual(result['native']['hostCalls'], 2)
                self.assertFalse(result['rawPayloadCorrelationVerified'])
                self.assertFalse(result['eligibleForMeasurement'])
                self.assertFalse(result['ledgerFinalized'])

    def test_catalog_api_is_bound_and_does_not_displace_model_order(self):
        events = self.trace.fixture.events('two-exec')
        catalog = {'level':'INFO', 'target':'codex_otel.trace_safe', 'fields':{
            'event.name':'codex.api_request', 'endpoint':'/models', 'success':True,
            'auth.header_attached':True, 'attempt':0, 'http.response.status_code':200}}
        result = review.verify_native(self.save('two-exec', events=[catalog, copy.deepcopy(catalog), *events]))
        self.assertEqual(result['native']['apiRequests'], 3)
        self.assertEqual(result['native']['modelCatalogApiRequests'], 2)
        for fault in ['third', 'endpoint', 'context', 'retry', 'success']:
            values = [copy.deepcopy(catalog), *events]
            if fault == 'third': values = [catalog, copy.deepcopy(catalog), copy.deepcopy(catalog), *events]
            elif fault == 'endpoint': values[0]['fields']['endpoint'] = '/unknown'
            elif fault == 'context': values[0]['fields']['conversation.id'] = 'other'
            elif fault == 'retry': values[0]['fields']['attempt'] = 1
            else: values[0]['fields']['success'] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review.verify_native(self.save('two-exec', events=values))

    def test_native_input_and_schema_drift_rejected_even_with_rehashed_artifacts(self):
        for fault in ['input', 'schema', 'provider']:
            sent = copy.deepcopy(self.trace.fixture.sent)
            if fault == 'input': sent[3]['params']['input'][0]['text'] += ' extra'
            elif fault == 'schema': sent[3]['params']['outputSchema'] = {}
            else: sent[2]['params']['modelProvider'] = 'openai'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review.verify_native(self.save(sent=sent))

    def test_raw_context_unknown_fields_and_missing_or_late_raw_stop(self):
        context = self.save()
        received = review.json_lines(context.originals['rpc-out.jsonl'])
        raw_index = next(i for i,f in enumerate(received) if f.get('method') == 'rawResponseItem/completed')
        for fault in ['missing', 'context', 'extra', 'late']:
            frames = copy.deepcopy(received)
            if fault == 'missing': frames = [f for f in frames if f.get('method') not in review.sdk.RAW_METHODS]
            elif fault == 'context': frames[raw_index]['params']['turnId'] = 'another'
            elif fault == 'extra': frames[raw_index]['params']['unknown'] = True
            else: frames.append(frames.pop(raw_index))
            # missingの場合、saveの自動raw追加を避け、原JSONLを直接差し替える。
            self.capture.rewrite('rpc-out.jsonl', b''.join(review.evidence.ledger.encoded(f)+b'\n' for f in frames))
            checked = review.evidence.load_verified_capture(self.capture.repository,self.capture.source,1)
            with self.subTest(fault=fault), self.assertRaises(ValueError): review.verify_native(checked)

    def test_account_metadata_is_typed_without_allowing_unknown_action(self):
        frames = copy.deepcopy(self.trace.fixture.received)
        frames.insert(1, dict(method='account/updated', params=dict(authMode='chatgpt', planType='plus')))
        self.assertFalse(review.verify_native(self.save(received=frames))['eligibleForMeasurement'])
        frames[1]['params']['authMode'] = 'unknown'
        with self.assertRaises(ValueError): review.verify_native(self.save(received=frames))

    def test_host_body_and_final_mismatch_and_unverified_context_are_rejected(self):
        host = copy.deepcopy(self.trace.fixture.host)
        host[-1]['result']['content'] += 'untrusted extra'
        with self.assertRaises(ValueError): review.verify_native(self.save(host=host))
        with self.assertRaises(ValueError): review.verify_native({})


class CanaryCompleteReviewTests(unittest.TestCase):
    def setUp(self):
        import test_production_canary_rollout as rollout_fixture
        original = rollout_fixture.CanaryRolloutTests(methodName='runTest').fixture()
        self.fixture = CanaryReviewTests(methodName='runTest')
        self.fixture.context_profile_raw = review.evidence.ledger.encoded(original['context_profile'])
        if hasattr(self,'cases_raw'):self.fixture.cases_raw=self.cases_raw
        if hasattr(self,'instructions_raw'):self.fixture.instructions_raw=self.instructions_raw
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.capture = self.fixture.capture
        native = review.verify_native(self.fixture.save())['native']
        mapping = {'thread':'t','turn':'u','thread:0':'t:0','parent0':native['parentCallIds'][0],
            'child0':native['nativeChildIds'][0],'child1':native['nativeChildIds'][1],
            'fixed base':review.evidence.capture.BASE,'fixed developer':review.evidence.capture.DEVELOPER,
            'fixed public input':self.capture.originals['model-input.json'].decode()}
        work = str(self.capture.base/'work')
        def convert(value):
            if isinstance(value,dict):return {k:(v if k=='request_kind' else convert(v)) for k,v in value.items()}
            if isinstance(value,list):return [convert(v) for v in value]
            if isinstance(value,str):
                if value in mapping:return mapping[value]
                try:
                    parsed=json.loads(value)
                    if isinstance(parsed,dict):return json.dumps(native['decision'] if parsed==original['native']['decision'] else convert(parsed))
                except ValueError:pass
                return value.replace('/fixed/work',work)
            return value
        events=convert(original['events']);payloads={name:convert(json.loads(raw)) for name,raw in original['payloads'].items()}
        for value in payloads.values():
            if 'input' in value and isinstance(value['input'],list):value['text']['format']['schema']=self.fixture.trace.fixture.sent[3]['params']['outputSchema']
        received=convert(original['received'])
        requests=[payloads[e['payload']['request_payload']['path']] for e in events if e['payload']['type']=='inference_started']
        responses=[payloads[e['payload']['response_payload']['path']] for e in events if e['payload']['type']=='inference_completed']
        def ref(body,kind):
            number=len(payloads)+1;path=f'payloads/{number}.json';payloads[path]=body
            return dict(raw_payload_id=f'raw_payload:{number}',kind=dict(type=kind),path=path)
        expanded=[]
        for event in events:
            expanded.append(event)
            if event['payload']['type']!='inference_completed':continue
            response=payloads[event['payload']['response_payload']['path']]
            call=next((x for x in response['output_items'] if x.get('type')=='custom_tool_call'),None)
            if call is None:continue
            parent=call['call_id'];bindings=native['parentLinks']['childBindings'];cell=bindings[0]['cellId']
            def code(fields,outside=False):
                expanded.append(dict(schema_version=1,seq=0,wall_time_unix_ms=event['wall_time_unix_ms'],rollout_id='t',
                    thread_id=None if outside else 't',codex_turn_id=None if outside else 'u',payload=fields))
            code(dict(type='code_cell_started',runtime_cell_id=cell,model_visible_call_id=parent,source_js=call['input']))
            for number,binding in enumerate(bindings):
                host=self.fixture.trace.fixture.host[number];tool=host['tool'];args=host['arguments'];ident=binding['childId']
                code(dict(type='tool_call_started',tool_call_id=ident,model_visible_call_id=None,
                    code_mode_runtime_tool_id=binding['runtimeToolId'],requester=dict(type='code_cell',runtime_cell_id=cell),
                    kind=dict(type='other',name=tool),summary=dict(type='generic',label='mcp__production_routing.'+tool,
                    input_preview=json.dumps(args),output_preview=None),invocation_payload=ref(dict(tool_name=tool,
                    tool_namespace='mcp__production_routing',payload=dict(type='function',arguments=json.dumps(args))),'tool_invocation')))
                runtime=dict(call_id=ident,turn_id='u',invocation=dict(server='production-routing',tool=tool,arguments=args),read_only_hint=True)
                code(dict(type='tool_call_runtime_started',tool_call_id=ident,runtime_payload=ref(runtime,'tool_runtime_event')))
                code(dict(type='mcp_tool_call_correlation_assigned',tool_call_id=ident,mcp_call_id=f'00000000-0000-0000-0000-{number+1:012d}'),True)
                wrapper=dict(content=[dict(type='text',text=json.dumps(host['result']))],isError=False)
                code(dict(type='tool_call_runtime_ended',tool_call_id=ident,status='completed',runtime_payload=ref(
                    dict(runtime,duration=dict(secs=0,nanos=1),result=dict(Ok=wrapper)),'tool_runtime_event')))
                code(dict(type='tool_call_ended',tool_call_id=ident,status='completed',result_payload=ref(dict(type='code_mode_response',value=wrapper),'tool_result')))
            ns=native['parentLinks']['parentDurationsNs'][parent]
            body=dict(response=dict(Result=dict(cell_id=cell,content_items=requests[1]['input'][-1]['output'],error_text=None,
                code_mode_host_duration=dict(secs=ns//1_000_000_000,nanos=ns%1_000_000_000))))
            for kind in ['code_cell_initial_response','code_cell_ended']:
                code(dict(type=kind,runtime_cell_id=cell,status='completed',response_payload=ref(body,'tool_result')))
        events=expanded
        for number,event in enumerate(events,1):event['seq']=number

        bodies=json.dumps([e['result'] for e in self.fixture.trace.fixture.host])
        for value in payloads.values():
            if isinstance(value.get('input'),list) and value['input'][-1].get('type')=='custom_tool_call_output':
                value['input'][-1]['output'][0]['text']=bodies
        for frame in received:
            item=frame.get('params',{}).get('item',{})
            if item.get('type')=='custom_tool_call_output':item['output'][0]['text']=bodies
        packets=[f for f in received if f.get('method') in (*review.sdk.RAW_METHODS,'thread/tokenUsage/updated')]
        actual=copy.deepcopy(self.fixture.trace.fixture.received)
        # 原入力raw→native user→control raw→native children→result raw→native final→final raw→terminal。
        frames=actual[:5]+packets[:3]+actual[5:7]+packets[3:6]+actual[7:11]+packets[6:7]+actual[11:13]+packets[7:]+actual[13:]
        telemetry=self.fixture.trace.fixture.events('single-exec')
        usage=[f['params']['tokenUsage']['last'] for f in frames if f.get('method')=='thread/tokenUsage/updated']
        api=[i for i,e in enumerate(telemetry) if e['fields'].get('event.name')=='codex.api_request']
        for number in reversed(range(len(usage))):
            end=api[number+1] if number+1<len(api) else len(telemetry)
            telemetry.insert(end,trace_fixture.completion_event(usage[number]))
        self.fixture.save(received=frames,events=telemetry)
        for name in ['rollout-traces/synthetic/payloads/1.json']:
            # 合成入口の初期placeholderを原イベントpayloadで置換する。
            self.capture.originals.pop(name,None);self.capture.receipt['artifactSha256'].pop(name,None)
            (self.capture.base/name).unlink()
        self.capture.rewrite('rollout-traces/synthetic/manifest.json',review.evidence.ledger.encoded(convert(original['manifest'])))
        self.capture.rewrite('rollout-traces/synthetic/trace.jsonl',b''.join(review.evidence.ledger.encoded(e)+b'\n' for e in events))
        for name,value in payloads.items():self.capture.rewrite('rollout-traces/synthetic/'+name,review.evidence.ledger.encoded(value))
        self.capture.persist()

    def loaded(self):
        return review.evidence.load_verified_capture(self.capture.repository,self.capture.source,1)

    def test_complete_original_capture_correlates_without_scoring_or_ledger_mutation(self):
        result=review.verify_complete(self.loaded())
        self.assertEqual(result['status'],'primary_original_capture_correlated')
        self.assertTrue(result['rawPayloadCorrelationVerified'])
        self.assertTrue(result['rollout']['usageCorrelationVerified'])
        self.assertFalse(result['eligibleForMeasurement']);self.assertFalse(result['ledgerFinalized'])
        self.assertFalse((self.capture.storage/'review-0001.json').exists())

    def test_elapsed_context_value_and_original_receipt_are_bound_before_complete(self):
        from dataclasses import replace
        context=self.loaded();value=context.result
        self.assertEqual(value['captureElapsedSeconds'],self.capture.receipt['elapsedSeconds'])
        for elapsed in [None,True,-1,0.0,999.0]:
            changed=dict(value,captureElapsedSeconds=elapsed)
            with self.subTest(elapsed=elapsed),self.assertRaisesRegex(ValueError,'elapsed receipt value drift'):
                review.verify_complete(replace(context,result_raw=review.evidence.ledger.encoded(changed)))
        self.capture.receipt['elapsedSeconds']=3.5;self.capture.persist()
        with self.assertRaisesRegex(ValueError,'elapsed receipt hash drift'):review.verify_complete(context)
        self.assertEqual(review.verify_complete(self.loaded())['rollout']['captureElapsedMilliseconds'],3500)

    def test_finite_elapsed_float_uses_integer_ceil_without_overflow(self):
        for seconds in [0.5,2.0001,1e308]:
            self.capture.receipt['elapsedSeconds']=seconds;self.capture.persist()
            numerator,denominator=seconds.as_integer_ratio();expected=(numerator*1000+denominator-1)//denominator
            result=review.verify_complete(self.loaded())
            self.assertEqual(result['rollout']['captureElapsedMilliseconds'],expected)

    def test_rehashed_code_mode_events_and_payload_drift_reject(self):
        prefix='rollout-traces/synthetic/'
        originals=dict(self.loaded().originals)
        original_events=review.json_lines(originals[prefix+'trace.jsonl'])
        faults=['missing','duplicate','unknown','parent','cell','source','runtime-id','requester','tool','summary',
                'invoke','runtime-turn','runtime-duration','runtime-body','correlation-type','correlation-duplicate',
                'tool-body','cell-status','cell-duration','cell-content','cell-final','stream-order']
        for fault in faults:
            for name,raw in originals.items():self.capture.rewrite(name,raw)
            events=copy.deepcopy(original_events)
            def event(kind):return next(e for e in events if e['payload']['type']==kind)
            def body(kind,key,change):
                path=prefix+event(kind)['payload'][key]['path'];value=review.evidence.trace.strict_json(originals[path]);change(value)
                self.capture.rewrite(path,review.evidence.ledger.encoded(value))
            start=event('code_cell_started')['payload'];tool=event('tool_call_started')['payload']
            if fault=='missing':events.remove(event('code_cell_initial_response'))
            elif fault=='duplicate':events.insert(events.index(event('code_cell_started')),copy.deepcopy(event('code_cell_started')))
            elif fault=='unknown':tool['unknown']=True
            elif fault=='parent':start['model_visible_call_id']='other'
            elif fault=='cell':start['runtime_cell_id']='other'
            elif fault=='source':start['source_js']+='changed'
            elif fault=='runtime-id':tool['code_mode_runtime_tool_id']='other'
            elif fault=='requester':tool['requester']['runtime_cell_id']='other'
            elif fault=='tool':tool['kind']['name']='read_resource'
            elif fault=='summary':tool['summary']['input_preview']='{"unknown":true}'
            elif fault=='invoke':body('tool_call_started','invocation_payload',lambda v:v['payload'].update(arguments='{"unknown":true}'))
            elif fault=='runtime-turn':body('tool_call_runtime_started','runtime_payload',lambda v:v.update(turn_id='other'))
            elif fault=='runtime-duration':body('tool_call_runtime_ended','runtime_payload',lambda v:v['duration'].update(nanos=True))
            elif fault=='runtime-body':body('tool_call_runtime_ended','runtime_payload',lambda v:v['result']['Ok'].update(isError=True))
            elif fault=='correlation-type':event('mcp_tool_call_correlation_assigned')['payload']['mcp_call_id']=True
            elif fault=='correlation-duplicate':
                all_c=[e for e in events if e['payload']['type']=='mcp_tool_call_correlation_assigned'];all_c[1]['payload']['mcp_call_id']=all_c[0]['payload']['mcp_call_id']
            elif fault=='tool-body':body('tool_call_ended','result_payload',lambda v:v['value']['content'][0].update(text='{}'))
            elif fault=='cell-status':event('code_cell_ended')['payload']['status']='failed'
            elif fault=='cell-duration':body('code_cell_initial_response','response_payload',lambda v:v['response']['Result']['code_mode_host_duration'].update(nanos=0))
            elif fault=='cell-content':body('code_cell_initial_response','response_payload',lambda v:v['response']['Result']['content_items'][0].update(text='{}'))
            elif fault=='cell-final':body('code_cell_ended','response_payload',lambda v:v['response']['Result'].update(error_text='error'))
            else:
                changed=event('code_cell_started');events.remove(changed);events.insert(events.index(event('inference_started')),changed)
            for n,e in enumerate(events,1):e['seq']=n
            self.capture.rewrite(prefix+'trace.jsonl',b''.join(review.evidence.ledger.encoded(e)+b'\n' for e in events));self.capture.persist()
            with self.subTest(fault=fault),self.assertRaises(ValueError):review.verify_complete(self.loaded())

    def test_rehashed_raw_usage_omission_and_profile_drift_stop(self):
        from dataclasses import replace
        context=self.loaded();profile=json.loads(context.fixed.context_profile_raw);profile['date']='2026-10-12'
        altered=replace(context,fixed=replace(context.fixed,context_profile_raw=review.evidence.ledger.encoded(profile)))
        with self.assertRaises(ValueError):review.verify_complete(altered)
        frames=review.json_lines(context.originals['rpc-out.jsonl'])
        frames=[f for f in frames if f.get('method')!='thread/tokenUsage/updated']
        self.capture.rewrite('rpc-out.jsonl',b''.join(review.evidence.ledger.encoded(f)+b'\n' for f in frames))
        with self.assertRaises(ValueError):review.verify_complete(self.loaded())

    def test_rehashed_raw_and_next_request_forged_parent_body_rejected(self):
        context=self.loaded()
        for name,raw in context.originals.items():
            if name=='rpc-out.jsonl':
                frames=review.json_lines(raw)
                for frame in frames:
                    item=frame.get('params',{}).get('item',{})
                    if item.get('type')=='custom_tool_call_output':item['output'][0]['text']=json.dumps(dict(host=[e['result'] for e in self.fixture.trace.fixture.host],extra=dict(instruction='unbound')))
                self.capture.rewrite(name,b''.join(review.evidence.ledger.encoded(f)+b'\n' for f in frames))
            elif '/payloads/' in name:
                value=json.loads(raw)
                if isinstance(value.get('input'),list) and value['input'][-1].get('type')=='custom_tool_call_output':
                    value['input'][-1]['output'][0]['text']=json.dumps(dict(host=[e['result'] for e in self.fixture.trace.fixture.host],extra=dict(instruction='unbound')))
                    self.capture.rewrite(name,review.evidence.ledger.encoded(value))
        with self.assertRaises(ValueError):review.verify_complete(self.loaded())


if __name__ == '__main__':
    unittest.main()
