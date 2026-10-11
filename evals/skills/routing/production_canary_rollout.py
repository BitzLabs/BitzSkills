"""固定された一次client contextと原rollout/raw/native usageを相関する。"""
from __future__ import annotations

import math
import re

import production_sdk_trace as sdk
import production_trace as trace

require = trace.require
USAGE = dict(input_tokens='inputTokens', cached_input_tokens='cachedInputTokens',
             cache_write_input_tokens='cacheWriteInputTokens', output_tokens='outputTokens',
             reasoning_output_tokens='reasoningOutputTokens', total_tokens='totalTokens')
REQUEST_KEYS = {'model', 'input', 'tool_choice', 'parallel_tool_calls', 'reasoning', 'store', 'stream',
                'include', 'prompt_cache_key', 'text', 'client_metadata'}
PROTOCOL_EVENTS = {'session_configured', 'turn_started', 'turn_complete', 'shutdown_complete'}


def nonempty(value):
    return isinstance(value, str) and bool(value)


def metadata(item, turn, *, required=True):
    value = item.get('internal_chat_message_metadata_passthrough')
    if value is None and not required:
        return {k:v for k,v in item.items() if k != 'internal_chat_message_metadata_passthrough'}
    require(isinstance(value, dict) and {'turn_id'} <= set(value) <= {'turn_id', 'create_time', 'content_item_kinds'} and
            value['turn_id'] == turn, 'raw internal metadata context')
    if 'create_time' in value:
        require(type(value['create_time']) in {int, float} and math.isfinite(value['create_time']) and
                value['create_time'] >= 0, 'raw internal finite timestamp')
    if 'content_item_kinds' in value:
        require(isinstance(value['content_item_kinds'], list) and all(nonempty(v) for v in value['content_item_kinds']),
                'raw content metadata type')
    return {k:v for k,v in item.items() if k != 'internal_chat_message_metadata_passthrough'}


def counters(value, *, snake=False):
    keys = set(USAGE) if snake else set(USAGE.values())
    require(isinstance(value, dict) and set(value) == keys and
            all(type(v) is int and v >= 0 for v in value.values()), 'exact nonnegative usage counters')
    result = {v:value[k] for k,v in USAGE.items()} if snake else dict(value)
    require(result['totalTokens'] == result['inputTokens'] + result['outputTokens'] and
            result['cachedInputTokens'] <= result['inputTokens'] and
            result['cacheWriteInputTokens'] <= result['inputTokens'] and
            result['reasoningOutputTokens'] <= result['outputTokens'], 'usage arithmetic')
    return result


def initial_context(request, sent, context_profile, *, turn):
    require(context_profile.get('version') == 'primary-client-context-0.1.0' and
            context_profile.get('sdkVersion') == '0.160.1' and context_profile.get('codexVersion') == 'codex-cli 0.160.1',
            'fixed primary client context profile')
    inputs = request['input']
    require(isinstance(inputs, list) and len(inputs) == 5 and
            [v.get('role') for v in inputs] == ['developer', 'developer', 'developer', 'user', 'user'],
            'complete primary input roles')
    tools = inputs[0]
    require(set(tools) == {'type', 'id', 'role', 'tools'} and tools['type'] == 'additional_tools' and
            nonempty(tools['id']) and sdk.digest(tools['tools']) == context_profile['toolsValueSha256'],
            'fixed complete primary tool declarations')
    messages = []
    for position, value in enumerate(inputs[1:],1):
        require(set(value) == {'type', 'id', 'role', 'content', 'internal_chat_message_metadata_passthrough'} and
                value['type'] == 'message' and nonempty(value['id']), 'initial message fields')
        if position == 1:
            require(value['internal_chat_message_metadata_passthrough'] == {'content_item_kinds':['model.base_instructions']},
                    'fixed base instructions metadata')
        else:
            metadata(value, turn)
            kinds = {2:['generic.developer_instructions','permissions.instructions','collaboration_mode.instructions'],
                     3:['environments.environment_context'],4:['user.text']}[position]
            require(set(value['internal_chat_message_metadata_passthrough']) == {'turn_id','create_time','content_item_kinds'} and
                    value['internal_chat_message_metadata_passthrough']['content_item_kinds'] == kinds, 'fixed initial content kinds')
        require(isinstance(value['content'], list) and all(isinstance(c, dict) and set(c) == {'type', 'text'} and
                c['type'] == 'input_text' and isinstance(c['text'], str) for c in value['content']), 'complete initial text blocks')
        messages.append(value['content'])
    params = sent[2]['params']
    require(messages[0] == [dict(type='input_text', text=params['baseInstructions'])] and type(context_profile.get('supplementBlockCount')) is int and
            context_profile['supplementBlockCount'] == 2 and len(messages[1]) == 3 and
            messages[1][0] == dict(type='input_text', text=params['developerInstructions']) and
            sdk.digest(messages[1][1:]) == context_profile['supplementValueSha256'], 'fixed caller and SDK supplement')
    date = context_profile['date']
    require(isinstance(date, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date), 'fixed context date')
    expected_env = sdk._diagnostic_environment(params['cwd'], date, {date})
    require(messages[2] == [dict(type='input_text', text=expected_env)] and
            messages[3] == [dict(type='input_text', text=sent[3]['params']['input'][0]['text'])],
            'fixed entire environment and model input')
    require(len({v['id'] for v in inputs}) == len(inputs), 'unique initial message IDs')


def request_policy(request, sent, *, thread, turn):
    require(isinstance(request, dict) and set(request) == REQUEST_KEYS and request['model'] == 'gpt-6.1-sol' and
            request['tool_choice'] == 'auto' and request['parallel_tool_calls'] is False and
            request['reasoning'] == dict(effort='low', context='all_turns') and request['store'] is False and
            request['stream'] is True and request['include'] == ['reasoning.encrypted_content'] and
            request['prompt_cache_key'] == thread and
            trace.json_equal(request['text'], dict(verbosity='low', format=dict(type='json_schema', strict=True,
                schema=sent[3]['params']['outputSchema'], name='codex_output_schema'))), 'fixed entire client request policy')
    value = request['client_metadata']
    require(isinstance(value, dict) and set(value) == {'x-codex-turn-metadata', 'x-codex-installation-id', 'thread_id',
            'turn_id', 'root_turn_id', 'session_id', 'x-codex-window-id'}, 'client metadata fields')
    require(all(nonempty(v) for v in value.values()) and value['thread_id'] == value['session_id'] == thread and
            value['turn_id'] == value['root_turn_id'] == turn and value['x-codex-window-id'] == thread + ':0',
            'client metadata context')
    extra = trace.strict_json(value['x-codex-turn-metadata'])
    fixed = dict(session_id=thread, thread_id=thread, agent_name='/root', turn_id=turn, window_id=thread+':0', window_number=0,
        request_kind='turn', root_turn_id=turn, sandbox='seccomp', sandbox_mode='read-only', auto_review_enabled=False,
        node_repl_auto_review_required=True, node_repl_disabled=False, analytics_enabled=True, model='gpt-6.1-sol', reasoning_effort='low')
    require(isinstance(extra, dict) and set(extra) == {*fixed, 'installation_id', 'context_window_id', 'turn_started_at_unix_ms'} and
            all(type(extra[k]) is type(v) and extra[k] == v for k,v in fixed.items()) and
            extra['installation_id'] == value['x-codex-installation-id'] and nonempty(extra['context_window_id']) and
            type(extra['turn_started_at_unix_ms']) is int and extra['turn_started_at_unix_ms'] >= 0, 'fixed client turn metadata')


def parent_bodies(output, expected):
    """モデルへ返ったJSON本文からhost全文を順に抽出する。要約・部分一致は証拠にしない。"""
    found = []
    visited = 0
    def inspect(value, depth=0):
        nonlocal visited
        visited += 1
        require(depth <= 16 and visited <= 4096, 'bounded parent output JSON')
        if isinstance(value, dict):
            if ({'skills', 'resources', 'manifestSha256'} <= set(value) or
                    {'path', 'content', 'sha256', 'sourceCommit'} <= set(value)):
                found.append(value)
            elif set(value)=={'content','isError'}:
                require(value['isError'] is False and isinstance(value['content'],list) and len(value['content'])==1,
                        'successful complete parent MCP wrapper')
                part=value['content'][0]
                require(isinstance(part,dict) and set(part)=={'type','text'} and part['type']=='text' and
                        isinstance(part['text'],str), 'parent MCP text shape')
                inspect(trace.strict_json(part['text']),depth+1)
            elif set(value) in ({'listed','read'},{'listed'},{'read'},{'kind','listed','read'}):
                require('kind' not in value or value['kind']=='read','fixed parent wrapper label')
                for name in ['listed','read']:
                    if name in value:inspect(value[name],depth+1)
            else:require(False,'unknown parent JSON wrapper or additional context')
        elif isinstance(value,list):
            require(bool(value),'nonempty parent JSON list')
            for nested in value:inspect(nested,depth+1)
        else:require(False,'unknown parent JSON value')
    for block in output:
        value=block['text']
        # 実行ヘッダは独立したblockだけ許す。本文への任意文字列追加は受理しない。
        if re.fullmatch(r'Script completed\nWall time [0-9]+(?:\.[0-9]+)? seconds\nOutput:\n',value):continue
        try:parsed=trace.strict_json(value)
        except ValueError:
            lines=value.splitlines()
            require(bool(lines) and all(line.strip() for line in lines),'complete parent JSON lines')
            for line in lines:inspect(trace.strict_json(line))
        else:inspect(parsed)
    require(trace.json_equal(found, expected), 'original parent output and complete host bodies')
    return [sdk.digest(value) for value in found]


def correlate(manifest_raw, events_raw, payloads, sent, received, native, context_profile, *, host_events):
    """原artifact検査後の値比較。wire bytesやserver内部入力は認定しない。"""
    require(isinstance(host_events,list) and len(host_events) == len(native['nativeChildIds']), 'original host child body count')
    host_results = [event['result'] for event in host_events]
    parent_hashes = []
    thread = sent[3]['params']['threadId']
    turn = next(f['params']['turn']['id'] for f in received if f.get('method') == 'turn/started')
    manifest = trace.strict_json(manifest_raw)
    require(isinstance(manifest, dict) and set(manifest) == {'schema_version', 'root_thread_id', 'raw_event_log', 'payloads_dir', 'rollout_id'} and
            type(manifest['schema_version']) is int and manifest['schema_version'] == 1 and
            manifest['root_thread_id'] == thread and manifest['rollout_id'] == thread and
            manifest['raw_event_log'] == 'trace.jsonl' and manifest['payloads_dir'] == 'payloads', 'original primary rollout manifest')
    require(isinstance(payloads, dict) and all(isinstance(k,str) and re.fullmatch(r'payloads/[1-9][0-9]*\.json',k) and
            isinstance(v,bytes) for k,v in payloads.items()), 'hashed payload inventory')
    used = set()
    def load(ref, kind):
        require(isinstance(ref,dict) and set(ref) == {'raw_payload_id','kind','path'} and
                ref['kind'] == {'type':kind} and ref['path'] in payloads and ref['path'] not in used and
                ref['raw_payload_id'] == 'raw_payload:' + ref['path'].removeprefix('payloads/').removesuffix('.json'),
                'unique original payload reference')
        used.add(ref['path']);return trace.strict_json(payloads[ref['path']])
    events = [trace.strict_json(line) for line in events_raw.splitlines()]
    require(bool(events), 'original rollout missing')
    kinds = []
    requests, responses, seen = [], [], set()
    stage = 0
    active = None
    last_wall = -1
    protocols = []
    protocol_start = None
    context_window = None
    milestones = ['rollout_started','thread_started','codex_turn_started','codex_turn_ended','thread_ended','rollout_ended']
    for seq, event in enumerate(events,1):
        require(isinstance(event,dict) and set(event) == {'schema_version','seq','wall_time_unix_ms','rollout_id','thread_id','codex_turn_id','payload'} and
                type(event['schema_version']) is int and event['schema_version'] == 1 and type(event['seq']) is int and
                event['seq'] == seq and event['rollout_id'] == thread and
                type(event['wall_time_unix_ms']) is int and event['wall_time_unix_ms'] >= 0 and event['wall_time_unix_ms'] >= last_wall and
                isinstance(event['payload'],dict), 'original rollout sequence')
        last_wall = event['wall_time_unix_ms'];fields = event['payload'];kind = fields.get('type');kinds.append(kind)
        if kind in milestones:
            require(stage < len(milestones) and kind == milestones[stage] and active is None, 'closed rollout lifecycle order')
            stage += 1
            if kind == 'rollout_started': require(set(fields)=={'type','trace_id','root_thread_id'} and nonempty(fields['trace_id']) and fields['root_thread_id']==thread, 'rollout start')
            elif kind == 'thread_started':
                require(set(fields)=={'type','thread_id','agent_path','metadata_payload'} and fields['thread_id']==thread and fields['agent_path']=='/root', 'root thread start')
                session = load(fields['metadata_payload'],'session_metadata')
                require(session == dict(thread_id=thread,agent_path='/root',task_name=None,nickname=None,agent_role=None,
                    session_source='vscode',cwd=sent[2]['params']['cwd'],rollout_path=None,model='gpt-6.1-sol',
                    provider_name='bitz_openai_http',approval_policy='never',sandbox_policy='ReadOnly { network_access: false }'),
                    'fixed complete original session metadata')
            elif kind in {'codex_turn_started','codex_turn_ended'}:
                require(event['thread_id']==thread and event['codex_turn_id']==turn and fields.get('codex_turn_id')==turn, 'rollout turn context')
                if kind == 'codex_turn_started': require(set(fields)=={'type','thread_id','codex_turn_id'} and fields['thread_id']==thread,'turn start')
                else: require(set(fields)=={'type','codex_turn_id','status'} and fields['status']=='completed' and bool(responses), 'turn completion')
            elif kind == 'thread_ended': require(fields==dict(type=kind,thread_id=thread,status='completed'),'thread completion')
            else: require(fields==dict(type=kind,status='completed'),'rollout completion')
            if kind not in {'codex_turn_started','codex_turn_ended'}:
                require(event['thread_id'] is None and event['codex_turn_id'] is None, 'root lifecycle outer context')
        elif kind == 'protocol_event_observed':
            require(2 <= stage <= 4 and set(fields)=={'type','event_type','event_payload'} and
                    fields['event_type'] in PROTOCOL_EVENTS and event['thread_id'] is None and event['codex_turn_id'] is None,
                    'closed original protocol event')
            protocol = fields['event_type']
            require(protocol not in protocols, 'unique protocol lifecycle')
            protocols.append(protocol)
            body = load(fields['event_payload'],'protocol_event')
            require(isinstance(body,dict), 'protocol payload object')
            if protocol == 'session_configured':
                require(stage==2 and body == dict(type='session_configured',session_id=thread,thread_id=thread,model='gpt-6.1-sol',
                    model_provider_id='bitz_openai_http',approval_policy='never',approvals_reviewer='user',cwd=sent[2]['params']['cwd'],
                    reasoning_effort='low',permission_profile=dict(type='managed',file_system=dict(type='restricted',entries=[
                        dict(path=dict(type='special',value=dict(kind='root')),access='read')]),network='restricted')), 'fixed protocol session policy')
            elif protocol == 'turn_started':
                require(stage==3 and not requests and set(body)=={'type','turn_id','root_turn_id','started_at','model_context_window','collaboration_mode_kind'} and
                    body['type']=='task_started' and body['turn_id']==body['root_turn_id']==turn and body['collaboration_mode_kind']=='default' and
                    type(body['started_at']) is int and body['started_at']>=0 and type(body['model_context_window']) is int and body['model_context_window']>0,
                    'protocol original turn start')
                protocol_start=body['started_at'];context_window=body['model_context_window']
            elif protocol == 'turn_complete':
                require(stage==4 and set(body)=={'type','turn_id','last_agent_message','started_at','completed_at','duration_ms','time_to_first_token_ms'} and
                    body['type']=='task_complete' and body['turn_id']==turn and body['started_at']==protocol_start and
                    all(type(body[k]) is int and body[k]>=0 for k in ['started_at','completed_at','duration_ms','time_to_first_token_ms']) and
                    body['completed_at']>=body['started_at'] and isinstance(body['last_agent_message'],str) and
                    trace.json_equal(trace.strict_json(body['last_agent_message']),native['decision']), 'protocol original completed final')
            else: require(stage==4 and body==dict(type='shutdown_complete'),'protocol shutdown completion')
        elif kind in {'inference_started','inference_completed'}:
            require(stage==3 and event['thread_id']==thread and event['codex_turn_id']==turn, 'inference inside original turn')
            ident=fields.get('inference_call_id');require(nonempty(ident),'inference call ID')
            if kind == 'inference_started':
                require(set(fields)=={'type','inference_call_id','thread_id','codex_turn_id','model','provider_name','request_payload'} and
                        active is None and ident not in seen and len(requests)<3 and fields['thread_id']==thread and
                        fields['codex_turn_id']==turn and fields['model']=='gpt-6.1-sol' and fields['provider_name']=='OpenAI', 'closed inference start')
                seen.add(ident);active=ident;requests.append(load(fields['request_payload'],'inference_request'))
            else:
                require(set(fields)=={'type','inference_call_id','response_id','upstream_request_id','response_payload'} and active==ident and
                        nonempty(fields['response_id']) and (fields['upstream_request_id'] is None or nonempty(fields['upstream_request_id'])), 'matching inference completion')
                value=load(fields['response_payload'],'inference_response')
                require(isinstance(value,dict) and set(value)=={'response_id','upstream_request_id','token_usage','output_items'} and
                        value['response_id']==fields['response_id'] and value['upstream_request_id']==fields['upstream_request_id'], 'response payload identity')
                responses.append(value);active=None
        else: require(False,'unknown original rollout event')
    require(stage==6 and active is None and len(requests)==len(responses)==native['apiRequests'] and used==set(payloads),
            'complete rollout and inference inventory')
    require(protocols == ['session_configured','turn_started','turn_complete','shutdown_complete'], 'complete original protocol lifecycle')
    require(len({r['response_id'] for r in responses})==len(responses),'unique response IDs')
    initial_context(requests[0],sent,context_profile,turn=turn)
    raw = [f for f in received if f.get('method') in sdk.RAW_METHODS]
    cursor = 0
    raw_ids = set()
    def consume(item):
        nonlocal cursor
        require(cursor < len(raw) and raw[cursor]['method']==sdk.RAW_METHODS[0], 'raw item notification order')
        value = metadata(raw[cursor]['params']['item'],turn);cursor += 1
        expected = metadata(item,turn,required=False)
        require(nonempty(value.get('id')) and value['id'] not in raw_ids, 'unique original raw item ID')
        raw_ids.add(value['id'])
        require(nonempty(value.get('id')) and trace.json_equal(
            {k:v for k,v in value.items() if k != 'id' or 'id' in expected}, expected), 'original raw item payload binding')
        return value
    for item in requests[0]['input'][2:]:consume(item)
    usage_frames = [f for f in received if f.get('method')=='thread/tokenUsage/updated']
    require(len(usage_frames)==len(responses),'one native usage update per inference')
    native_end = [i for i,f in enumerate(received) if f.get('method')=='turn/completed']
    response_positions=[i for i,f in enumerate(received) if f.get('method')==sdk.RAW_METHODS[1]]
    usage_positions=[i for i,f in enumerate(received) if f.get('method')=='thread/tokenUsage/updated']
    require(len(native_end)==1 and len(response_positions)==len(responses) and all(
        response_positions[i] < position < (response_positions[i+1] if i+1<len(responses) else native_end[0])
        for i,position in enumerate(usage_positions)), 'native usage lifecycle and inference order')
    total={k:0 for k in USAGE.values()};parent_index=0;calls=[]
    history=requests[0]['input']
    for index,(request,response) in enumerate(zip(requests,responses)):
        request_policy(request,sent,thread=thread,turn=turn)
        require(trace.json_equal(request['input'],history), 'unaltered request history prefix')
        outputs=response['output_items'];require(isinstance(outputs,list) and bool(outputs),'response output items')
        echoed=[]
        for item in outputs:
            require(isinstance(item,dict),'output object')
            kind=item.get('type')
            if kind in {'custom_tool_call','function_call'}:
                argument = 'input' if kind == 'custom_tool_call' else 'arguments'
                require({'type','call_id','name','namespace',argument} <= set(item) <=
                        {'type','call_id','name','namespace',argument,'id'} and
                        ('id' not in item or nonempty(item['id'])) and nonempty(item['call_id']) and
                        item['namespace']=='functions' and isinstance(item[argument],str), 'closed original control call')
                expected = {'single-exec':('exec',),'two-exec':('exec','exec'),'exec-wait':('exec','wait'),'no-exec':()}[native['profile']]
                require(parent_index<len(expected) and item['name']==expected[parent_index] and
                        kind==('custom_tool_call' if item['name']=='exec' else 'function_call') and
                        item['call_id']==native['parentCallIds'][parent_index], 'original parent call identity')
                calls.append(item);parent_index+=1
            elif kind=='message':
                require(set(item)=={'type','id','role','content','phase'} and nonempty(item['id']) and item['role']=='assistant' and
                        item['phase'] in {'commentary','final_answer'} and isinstance(item['content'],list) and bool(item['content']) and
                        all(isinstance(c,dict) and set(c)=={'type','text'} and c['type']=='output_text' and isinstance(c['text'],str) for c in item['content']), 'closed original agent output')
            elif kind=='reasoning':
                require({'type','id','summary'} <= set(item) <= {'type','id','summary','content','encrypted_content'} and nonempty(item['id']), 'bounded reasoning output')
            else: require(False,'unknown original output action')
            echoed.append(consume(item))
        require(cursor<len(raw) and raw[cursor]['method']==sdk.RAW_METHODS[1],'raw inference completion order')
        completed=raw[cursor]['params'];cursor+=1
        require(completed['responseId']==response['response_id'],'raw response identity')
        last=counters(response['token_usage'],snake=True)
        require(counters(completed['usage'])==last,'raw and rollout usage')
        info=completed['usageMetadata']
        require(info is None or isinstance(info,dict) and set(info)=={'amount','metadata'} and
                (info['amount'] is None or isinstance(info['amount'],str)), 'typed raw usage metadata')
        native_params=usage_frames[index]['params']
        require(set(native_params)=={'threadId','turnId','tokenUsage'} and native_params['threadId']==thread and
                native_params['turnId']==turn, 'native usage original context')
        usage=native_params['tokenUsage']
        require(set(usage)=={'last','total','modelContextWindow'} and
                type(usage['modelContextWindow']) is int and usage['modelContextWindow']==context_window, 'native usage envelope')
        for key,n in last.items():total[key]+=n
        require(counters(usage['last'])==last and counters(usage['total'])==total,'native last and cumulative rollout usage')
        history=[*history,*echoed]
        if index+1<len(requests):
            next_history=requests[index+1]['input'];require(isinstance(next_history,list) and len(next_history)==len(history)+1 and
                trace.json_equal(next_history[:len(request['input'])],request['input']) and
                trace.json_equal([metadata(x,turn,required=False) for x in next_history[len(request['input']):len(history)]],echoed),
                'one complete original tool result after response')
            result=next_history[-1]
            result_fields=metadata(result,turn,required=False)
            require(outputs[-1]['type'] in {'custom_tool_call','function_call'} and isinstance(result,dict) and
                    set(result_fields)=={'type','id','call_id','output'} and nonempty(result_fields['id']) and
                    result_fields['type']==outputs[-1]['type']+'_output' and
                    result_fields['call_id']==outputs[-1]['call_id'] and
                    isinstance(result_fields['output'],list) and bool(result_fields['output']) and
                    all(isinstance(c,dict) and set(c)=={'type','text'} and c['type']=='input_text' and isinstance(c['text'],str)
                        for c in result_fields['output']), 'original control result binding')
            expected_bodies = host_results if native['profile']=='single-exec' else host_results[index:index+1]
            parent_hashes.append(parent_bodies(result_fields['output'], expected_bodies))
            consume(result);history=next_history
    require(cursor==len(raw) and parent_index==len(native['parentCallIds']),'complete original raw and parent inventory')
    child_ids = native['nativeChildIds']
    starts = {f['params']['item']['id']:i for i,f in enumerate(received) if f.get('method')=='item/started' and
              f.get('params',{}).get('item',{}).get('type')=='mcpToolCall'}
    ends = {f['params']['item']['id']:i for i,f in enumerate(received) if f.get('method')=='item/completed' and
            f.get('params',{}).get('item',{}).get('type')=='mcpToolCall'}
    require(set(starts)==set(ends)==set(child_ids), 'complete original native children')
    for parent,call in enumerate(calls):
        children = child_ids if len(calls)==1 else [child_ids[parent]]
        original_result = next(i for i,f in enumerate(received) if f.get('method')==sdk.RAW_METHODS[0] and
            f['params']['item'].get('type') in {'custom_tool_call_output','function_call_output'} and
            f['params']['item'].get('call_id')==call['call_id'])
        require(all(response_positions[parent] < starts[child] < ends[child] < original_result for child in children),
                'raw parent response native child and original result order')
    finals=[x for r in responses for x in r['output_items'] if x.get('type')=='message' and x.get('phase')=='final_answer']
    require(len(finals)==1 and finals[0] is responses[-1]['output_items'][-1] and
            trace.json_equal(trace.strict_json(''.join(c['text'] for c in finals[0]['content'])), native['decision']), 'original final and native decision')
    final_raw=metadata(next(f['params']['item'] for f in reversed(raw) if f['method']==sdk.RAW_METHODS[0]),turn)
    native_finals=[f['params']['item'] for f in received if f.get('method')=='item/completed' and
                   f.get('params',{}).get('item',{}).get('type')=='agentMessage' and
                   f['params']['item'].get('phase')=='final_answer']
    require(len(native_finals)==1 and native_finals[0]['id']==final_raw['id'] and
            native_finals[0]['text']==''.join(c['text'] for c in final_raw['content']), 'raw and native final identity')
    return dict(status='primary_client_rollout_raw_usage_correlated',inferences=len(requests),rolloutEvents=len(events),
        totalTokenUsage=total,modelContextWindow=context_window,parentHostBodiesVerified=True,
        parentHostBodyValueSha256=parent_hashes,initialContextVerified=True,rawPayloadCorrelationVerified=True,usageCorrelationVerified=True,
        originalRequestValueSha256=[sdk.digest(x) for x in requests],originalResponseValueSha256=[sdk.digest(x) for x in responses],
        contextProfileValueSha256=sdk.digest(context_profile),certifiesProviderWireBodies=False,eligibleForMeasurement=False,
        certifiesBehavior=False,certifiesSkillGate=False)
