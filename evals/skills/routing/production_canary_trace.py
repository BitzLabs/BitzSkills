"""可変IDの限定SDK軌跡を検査する。provider wire未取得層と測定適格性を認定しない。"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
import production_sdk_trace as sdk
import production_trace as trace

require = trace.require
PROFILES = {'no-exec': (), 'single-exec': ('exec',), 'two-exec': ('exec', 'exec'),
            'exec-wait': ('exec', 'wait')}
NEUTRAL = {'codex.conversation_starts', 'codex.startup_phase', 'codex.user_prompt',
           'codex.api_request', 'codex.turn_ttft'}


def primary_usage_telemetry(events, received, thread, turn, api_indices):
    """原完了telemetryをnative各推論usageへ照合し、未知fieldを受理しない。"""
    from production_canary_rollout import counters
    frames = [f for f in received if f.get('method') == 'thread/tokenUsage/updated']
    completions = [(i,e) for i,e in enumerate(events) if e['fields'].get('event.name') == 'codex.sse_event']
    require(len(completions) == len(frames) and (not completions or len(completions) == len(api_indices)),
            'one completion telemetry per native inference usage')
    keys = {'event.name','event.kind','input_token_count','output_token_count','cached_token_count',
            'cache_write_token_count','reasoning_token_count','tool_token_count','ttft_ms',
            'model_reasoning_effort','event.timestamp','conversation.id','app.version','auth_mode',
            'originator','terminal.type','model','slug'}
    totals = None
    previous_timestamp=None
    for number, ((position,event),frame) in enumerate(zip(completions,frames)):
        f = event['fields']
        require(set(f) == keys and event['target'] == 'codex_otel.trace_safe' and
                f['event.kind'] == 'response.completed' and f['conversation.id'] == thread and
                f['app.version'] == '0.160.1' and f['auth_mode'] == 'Chatgpt' and
                f['originator'] == 'codex_python_sdk' and f['terminal.type'] == 'unknown' and
                f['model'] == f['slug'] == 'gpt-6.1-sol' and f['model_reasoning_effort'] == 'low',
                'fixed primary completion telemetry fields and context')
        require(isinstance(f['event.timestamp'],str) and
                re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',f['event.timestamp']) is not None,
                'completion telemetry timestamp')
        stamp=datetime.fromisoformat(f['event.timestamp'].replace('Z','+00:00'))
        require(isinstance(event.get('timestamp'),str),'original completion outer timestamp')
        outer=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))
        require(outer.utcoffset() is not None and outer.replace(microsecond=outer.microsecond//1000*1000)==stamp and
                (previous_timestamp is None or stamp>=previous_timestamp),'original completion timestamp binding and order')
        previous_timestamp=stamp
        require(type(f['ttft_ms']) is int and f['ttft_ms'] >= 0, 'completion telemetry ttft')
        values = {}
        for key, target in [('input_token_count','inputTokens'),('output_token_count','outputTokens'),
                ('tool_token_count','totalTokens')]:
            require(isinstance(f[key],str) and re.fullmatch(r'0|[1-9][0-9]{0,19}',f[key]) is not None,
                    'completion telemetry decimal counter')
            values[target] = int(f[key])
        for key,target in [('cached_token_count','cachedInputTokens'),('cache_write_token_count','cacheWriteInputTokens'),('reasoning_token_count','reasoningOutputTokens')]:
            require(type(f[key]) is int and f[key]>=0, 'completion telemetry integer counter')
            values[target] = f[key]
        p = frame.get('params')
        require(isinstance(p,dict) and set(p) == {'threadId','turnId','tokenUsage'} and
                p['threadId']==thread and p['turnId']==turn and isinstance(p['tokenUsage'],dict) and
                set(p['tokenUsage'])=={'last','total','modelContextWindow'} and
                type(p['tokenUsage']['modelContextWindow']) is int and p['tokenUsage']['modelContextWindow']>0,
                'completion native usage context')
        last = counters(p['tokenUsage']['last'])
        require(counters(values)==last, 'completion telemetry and native usage drift')
        totals = {k:(0 if totals is None else totals[k])+v for k,v in last.items()}
        require(counters(p['tokenUsage']['total']) == totals, 'completion native cumulative usage drift')
        require(api_indices[number] < position < (api_indices[number+1] if number+1<len(api_indices) else len(events)),
                'completion telemetry inference order')
    return {'count':len(completions),'valueSha256':sdk.digest([e for _,e in completions]),
            'nativeUsageMatched':True,'certifiesProviderWireBodies':False}


def audit(manifest_raw, host_events, sent, received, catalog, *, raw_stderr, selected_log, profile, expected_input,
          base_instructions, developer_instructions, cwd, actual_exit_code,
          sdk_profile='diagnostic', output_schema=None, decision_schema_raw=None):
    """原RPC・host本文・全対象telemetryの相関。固定IDへの別名置換は行わない。"""
    require(isinstance(profile, str) and profile in PROFILES, 'bounded canary profile')
    events = sdk.complete_trace_projection(raw_stderr, selected_log)
    require(isinstance(expected_input, bytes) and isinstance(base_instructions, str) and
            isinstance(developer_instructions, str) and isinstance(cwd, str) and bool(cwd), 'fixed canary inputs')
    _, params = sdk.requests(sent, profile=sdk_profile, output_schema=output_schema)
    expected_thread = dict(model='gpt-6.1-sol', modelProvider='bitz_openai_http' if sdk_profile == 'public-canary' else 'openai', allowProviderModelFallback=False,
                           cwd=cwd, sandbox='read-only', approvalPolicy='never', ephemeral=True,
                           baseInstructions=base_instructions, developerInstructions=developer_instructions)
    if sdk_profile == 'public-canary':
        expected_thread['experimentalRawEvents'] = True
    require(trace.json_equal(params['thread'], expected_thread) and
            params['turn']['input'][0]['text'].encode() == expected_input, 'original SDK input drift')
    native = sdk.normalized(sent, received, profile=sdk_profile, output_schema=output_schema)
    items = trace.completed_items(native['frames'])
    finals = [item for item in items if item['type'] == 'agentMessage' and item['phase'] == 'final_answer']
    require(len(finals) == 1, 'one canary final required')
    decision = trace.strict_json(finals[0]['text'])
    integrity = trace.audit(manifest_raw, host_events, native['frames'], decision, catalog,
                            actual_exit_code=actual_exit_code, decision_schema_raw=decision_schema_raw)
    require(len(host_events) <= 2, 'bounded child count')
    tools = [event['tool'] for event in host_events]
    selected = decision['selectedEntry']
    require(tools == ['list_resources', 'read_resource'] if selected else tools in [[], ['list_resources']],
            'selected decision and actual read mismatch')
    require(isinstance(events, list) and bool(events), 'original telemetry required')
    context = next(frame['params'] for frame in received if frame.get('method') == 'turn/started')
    thread, turn = context['threadId'], context['turn']['id']
    direct, api_indices, catalog_indices = [], [], []
    for index, event in enumerate(events):
        require(isinstance(event, dict) and event.get('level') == 'INFO' and
                event.get('target') in {'codex_otel.trace_safe', 'codex_code_mode::timing'} and
                isinstance(event.get('fields'), dict), 'canary telemetry format')
        fields = event['fields']
        for key, expected in [('model', 'gpt-6.1-sol'), ('app.version', '0.160.1'), ('provider_name', 'OpenAI'), *([('auth_mode','Chatgpt')] if sdk_profile=='public-canary' else [])]:
            require(key not in fields or fields[key] == expected, 'canary runtime context contradiction')
        name = fields.get('event.name')
        if sdk_profile == 'public-canary' and name == 'codex.sse_event':
            continue  # 全件の型・文脈・usage・順序はprimary_usage_telemetryで検査する。
        if sdk_profile == 'public-canary' and name == 'codex.api_request':
            require(fields.get('endpoint') in {'/models', '/responses'} and
                    fields.get('auth.header_attached') is True and type(fields.get('attempt')) is int and
                    fields['attempt'] == 0 and type(fields.get('http.response.status_code')) is int and
                    fields['http.response.status_code'] == 200 and
                    fields.get('auth.retry_after_unauthorized', False) is False,
                    'known primary API without retry')
            if fields['endpoint'] == '/models':
                require(event['target'] == 'codex_otel.trace_safe' and fields.get('success') is True and
                        ('conversation.id' not in fields or fields['conversation.id'] == thread) and
                        ('turn_id' not in fields or fields['turn_id'] == turn), 'primary catalog context')
                catalog_indices.append(index)
                continue
            require(fields.get('model') == 'gpt-6.1-sol' and fields.get('app.version') == '0.160.1',
                    'primary model API context')
        if name in NEUTRAL:
            require(event['target'] == 'codex_otel.trace_safe' and fields.get('conversation.id') == thread and
                    ('turn_id' not in fields or fields['turn_id'] == turn), 'canary telemetry context')
            if name == 'codex.api_request':
                require(fields.get('auth.header_attached') is True and type(fields.get('attempt')) is int and
                        fields['attempt'] == 0 and type(fields.get('http.response.status_code')) is int and
                        fields['http.response.status_code'] == 200, 'canary API evidence')
                require('auth.retry_after_unauthorized' not in fields or
                        fields['auth.retry_after_unauthorized'] is False, 'canary authorization retry')
                api_indices.append(index)
        elif name == 'codex.tool_call_received' and fields.get('tool_source') == 'direct':
            require(isinstance(fields.get('call_id'), str) and bool(fields['call_id']), 'canary parent ID')
            direct.append((index, fields['call_id'], fields.get('tool_name')))
    require(tuple(value[2] for value in direct) == PROFILES[profile] and
            len({value[1] for value in direct}) == len(direct), 'canary parent profile drift')
    require(len(api_indices) == len(direct) + 1 and len(api_indices) <= 3 and len(catalog_indices) <= 2, 'canary API count')
    usage_telemetry = primary_usage_telemetry(events,received,thread,turn,api_indices) if sdk_profile=='public-canary' else None
    if profile == 'no-exec':
        require(not host_events and all(event['target'] == 'codex_otel.trace_safe' and
                event['fields']['event.name'] in NEUTRAL | ({'codex.sse_event'} if sdk_profile=='public-canary' else set()) for event in events), 'unexpected negative operation')
        parent_links = None
    else:
        require(bool(host_events), 'exec without observed child is outside bounded profile')
        sdk._require_native_parent_context(received)
        parent_events = [event for index, event in enumerate(events) if index not in catalog_indices and not (sdk_profile=='public-canary' and event['fields'].get('event.name')=='codex.sse_event')]
        parent_links = sdk._audit_parent_links(parent_events, received, direct[0][1],
            wait_call_id=direct[1][1] if profile == 'exec-wait' else None,
            second_exec_call_id=direct[1][1] if profile == 'two-exec' else None,
            api_auth_attached=True, telemetry_auth_mode='Chatgpt' if sdk_profile=='public-canary' else None, child_tools=tuple(tools))
        if len(direct) == 1:
            parent_ready = next(index for index, event in enumerate(events)
                if event['fields'].get('event.name') == 'codex.tool_result_ready' and
                event['fields'].get('call_id') == direct[0][1])
            require(api_indices[0] < direct[0][0] < parent_ready < api_indices[1], 'single exec API order')
    return dict(status='bounded_sdk_routing_trace_diagnostic_passed', profile=profile,
                parentCallIds=[value[1] for value in direct],
                nativeChildIds=[item['id'] for item in items if item['type'] == 'mcpToolCall'],
                hostCalls=len(host_events), apiRequests=len(api_indices), modelCatalogApiRequests=len(catalog_indices),
                totalServiceApiRequests=len(api_indices) + len(catalog_indices), decision=decision,
                nativeEvidence={key: value for key, value in native.items() if key != 'frames'},
                parentLinks=parent_links, childIntegrity=integrity, usageTelemetry=usage_telemetry,
                traceValueSha256=sdk.digest(events), modelInputSha256=hashlib.sha256(expected_input).hexdigest(),
                rawStderrSha256=hashlib.sha256(raw_stderr).hexdigest(),
                selectedLogSha256=hashlib.sha256(selected_log).hexdigest(),
                completeTargetProjectionVerified=True,
                sdkInputValueSha256=sdk.digest(params['turn']['input']),
                certifiesProviderWireBodies=False, certifiesRawPayloads=False,
                eligibleForMeasurement=False, certifiesBehavior=False, certifiesSkillGate=False)
