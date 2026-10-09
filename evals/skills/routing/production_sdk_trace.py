"""SDK0.160.1の原RPCを構造診断する。Code Modeの親子因果・一次採点は認定しない。"""
from __future__ import annotations

import copy
import hashlib
import json
from uuid import UUID

import production_trace as trace
import production_cli_probe as cli

require = trace.require
METHODS = ('initialize', 'thread/start', 'turn/start')
DIAGNOSTIC_TOOLS_SHA = 'd3ba928b8cb4b51fa55b403a74ec96eac5b967d9d9b257485d2eb203ec404316'
DIAGNOSTIC_CONTEXT_SHA = 'fa08ee2683ed7e3c31bc034e3a686566da5e3302c3c2cdd0ee9fbf976567b69d'


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def uuid_id(value) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def requests(sent: list) -> tuple[dict, dict]:
    require(isinstance(sent, list) and len(sent) == 4, 'exact SDK request sequence required')
    require(sent[1] == {'method': 'initialized'}, 'SDK initialized notification required')
    selected = [sent[i] for i in (0, 2, 3)]
    bindings = {}
    for index, (method, frame) in enumerate(zip(METHODS, selected), 1):
        require(isinstance(frame, dict) and set(frame) == {'id', 'method', 'params'}, 'SDK request fields')
        require(frame['method'] == method and uuid_id(frame['id']), 'SDK request method or UUID')
        require(frame['id'] not in bindings and isinstance(frame['params'], dict), 'SDK duplicate request')
        bindings[frame['id']] = index
    initialize, thread, turn = [f['params'] for f in selected]
    require(set(initialize) == {'clientInfo', 'capabilities'} and
            trace.json_equal(initialize['capabilities'], {'experimentalApi': True}) and
            isinstance(initialize['clientInfo'], dict) and
            set(initialize['clientInfo']) == {'name', 'title', 'version'} and
            initialize['clientInfo']['title'] == 'Codex Python SDK', 'fixed SDK initialize params')
    require(set(thread) <= {'model', 'modelProvider', 'allowProviderModelFallback', 'cwd', 'sandbox',
                           'approvalPolicy', 'ephemeral', 'baseInstructions', 'developerInstructions'},
            'unknown SDK thread params')
    require(set(turn) == {'threadId', 'input'}, 'SDK turn policy override or unknown params')
    require(initialize.get('clientInfo', {}).get('name') == 'codex_python_sdk' and
            initialize['clientInfo'].get('version') == '0.160.1', 'SDK version required')
    require(thread.get('sandbox') == 'read-only' and thread.get('approvalPolicy') == 'never' and
            thread.get('ephemeral') is True and thread.get('allowProviderModelFallback') is False,
            'SDK thread policy required')
    require(isinstance(thread.get('model'), str) and bool(thread['model']), 'SDK model required')
    require(isinstance(turn.get('threadId'), str) and bool(turn['threadId']), 'SDK requested thread required')
    inputs = turn.get('input')
    require(isinstance(inputs, list) and len(inputs) == 1 and isinstance(inputs[0], dict) and
            set(inputs[0]) == {'type', 'text'} and inputs[0]['type'] == 'text' and
            isinstance(inputs[0]['text'], str), 'single SDK text input required')
    return bindings, {'thread': thread, 'turn': turn}


def normalized(sent: list, received: list, *, allowed_warnings: tuple[str, ...] = ()) -> dict:
    """原フレームを変更せず、検査済みの入力・環境通知を側記録へ分離する。"""
    bindings, expected = requests(sent)
    require(isinstance(received, list), 'SDK received frames required')
    require(isinstance(allowed_warnings, tuple) and all(isinstance(v, str) for v in allowed_warnings),
            'fixed warning allowlist required')
    responses = {}
    for frame in received:
        require(isinstance(frame, dict) and 'error' not in frame, 'SDK error frame')
        if 'id' in frame:
            require(set(frame) == {'id', 'result'} and frame['id'] in bindings and
                    frame['id'] not in responses and isinstance(frame['result'], dict), 'SDK response binding')
            responses[frame['id']] = frame['result']
    require(set(responses) == set(bindings), 'SDK response missing')
    by_number = {bindings[k]: v for k, v in responses.items()}
    thread_result = by_number[2]
    require(set(by_number[3]) == {'turn'}, 'SDK turn response fields')
    trace.check_turn_start(by_number[3]['turn'])
    thread = thread_result.get('thread', {}).get('id')
    turn = by_number[3].get('turn', {}).get('id')
    require(isinstance(thread, str) and thread == expected['turn']['threadId'] and
            isinstance(turn, str) and bool(turn), 'SDK thread/turn response mismatch')
    require(thread_result.get('model') == expected['thread']['model'] and
            thread_result.get('modelProvider') == expected['thread'].get('modelProvider') and
            thread_result.get('approvalPolicy') == 'never' and
            trace.json_equal(thread_result.get('sandbox'), {'type': 'readOnly', 'networkAccess': False}) and
            thread_result['thread'].get('ephemeral') is True and
            thread_result.get('instructionSources') == [], 'SDK effective policy mismatch')
    frames, retained, active, completed, deltas = [], [], {}, {}, {}
    user_id = None
    user_done = False
    turn_started = False
    response_order = []
    for index, original in enumerate(received):
        if 'id' in original:
            number = bindings[original['id']]
            require(number == len(response_order) + 1, 'SDK response sequence mismatch')
            response_order.append(number)
            frames.append({'id': bindings[original['id']], 'result': copy.deepcopy(original['result'])})
            continue
        require(set(original) <= {'method', 'params', 'emittedAtMs'} and
                set(original) >= {'method', 'params'}, 'SDK notification fields')
        if 'emittedAtMs' in original:
            require(type(original['emittedAtMs']) is int and original['emittedAtMs'] >= 0, 'SDK timestamp')
        frame = copy.deepcopy(original)
        frame.pop('emittedAtMs', None)
        method, params = frame['method'], frame['params']
        require(isinstance(params, dict), 'SDK notification params')
        if 'threadId' in params:
            require(params['threadId'] == thread, 'SDK outer thread mismatch')
        if 'turnId' in params:
            require(params['turnId'] == turn, 'SDK outer turn mismatch')
        if method == 'thread/started' or 'threadId' in params:
            require(1 in response_order, 'SDK thread event before initialize response')
        if method == 'turn/started' or 'turnId' in params or method == 'turn/completed':
            require(2 in response_order, 'SDK turn event before thread response')
        if method == 'turn/started':
            require(not turn_started and params.get('threadId') == thread and
                    params.get('turn', {}).get('id') == turn, 'SDK turn start mismatch')
            turn_started = True
        if method in {'remoteControl/status/changed', 'account/rateLimits/updated', 'warning',
                      'mcpServer/startupStatus/updated'}:
            if method == 'remoteControl/status/changed':
                require(set(params) == {'status', 'serverName', 'installationId', 'environmentId'} and
                        params['status'] == 'disabled', 'SDK remote control must be disabled')
            elif method == 'account/rateLimits/updated':
                require(set(params) == {'rateLimits'} and isinstance(params['rateLimits'], dict), 'SDK rate limit fields')
            else:
                require(params.get('threadId') == thread, 'SDK environment thread mismatch')
                if method == 'warning':
                    require(set(params) == {'threadId', 'message'} and params['message'] in allowed_warnings,
                            'SDK unapproved warning')
                else:
                    require(set(params) == {'threadId', 'name', 'status', 'error', 'failureReason'} and
                            params['name'] == trace.SERVER and params['status'] in {'starting', 'ready'} and
                            params['error'] is None and params['failureReason'] is None, 'SDK MCP startup failed')
            retained.append({'rawIndex': index, 'kind': method, 'sha256': digest(original)})
            continue
        if method in {'item/started', 'item/completed'}:
            require(set(params) <= {'threadId', 'turnId', 'item', 'startedAtMs', 'completedAtMs'} and
                    set(params) >= {'threadId', 'turnId', 'item'}, 'SDK item params')
            for key in ('startedAtMs', 'completedAtMs'):
                if key in params:
                    require(type(params[key]) is int and params[key] >= 0, 'SDK item timestamp')
                    params.pop(key)
            item = params['item']
            require(isinstance(item, dict) and isinstance(item.get('id'), str) and bool(item['id']), 'SDK item required')
            require(params['threadId'] == thread and params['turnId'] == turn, 'SDK item context mismatch')
            ident = item['id']
            if item.get('type') == 'userMessage':
                require(turn_started, 'SDK input before turn started')
                content = [{'type': 'text', 'text': expected['turn']['input'][0]['text'], 'text_elements': []}]
                require(set(item) == {'type', 'id', 'clientId', 'content'} and trace.json_equal(item['content'], content) and
                        item['clientId'] is None, 'SDK input message mismatch')
                if method == 'item/started':
                    require(user_id is None and not active, 'SDK duplicate or late user input')
                    user_id = ident
                    active[ident] = item
                else:
                    require(ident == user_id and ident in active and trace.json_equal(active[ident], item) and not user_done,
                            'SDK input lifecycle mismatch')
                    active.pop(ident)
                    user_done = True
                retained.append({'rawIndex': index, 'kind': method + '/userMessage', 'sha256': digest(original)})
                continue
            require(user_done and ident != user_id, 'SDK action before input completed or reused input id')
            if item.get('type') == 'agentMessage':
                require((item.get('questions') is None or trace.json_equal(item['questions'], [])) and item.get('delivery') is None and
                        item.get('memoryCitation') is None, 'SDK dialogue or extra message evidence')
            if method == 'item/started':
                require(ident not in active and ident not in completed, 'SDK duplicate start')
                active[ident] = item
            else:
                require(ident in active and ident not in completed, 'SDK completion without start')
                if ident in deltas:
                    require(active[ident].get('text', '') + ''.join(deltas[ident]) == item.get('text'),
                            'SDK streamed final text mismatch')
                active.pop(ident)
                completed[ident] = item
        elif method == 'item/agentMessage/delta':
            ident = params.get('itemId')
            require(set(params) == {'threadId', 'turnId', 'itemId', 'delta'} and
                    params['threadId'] == thread and params['turnId'] == turn and
                    ident in active and active[ident].get('type') == 'agentMessage' and
                    isinstance(params['delta'], str), 'SDK delta outside active message')
            deltas.setdefault(ident, []).append(params['delta'])
        elif method == 'turn/completed':
            terminal = params.get('turn', {})
            require(terminal.get('itemsView') == 'summary' and isinstance(terminal.get('items'), list) and
                     trace.json_equal(terminal['items'], [v for v in completed.values() if v.get('type') == 'agentMessage' and
                                           v.get('phase') == 'final_answer']), 'SDK turn summary mismatch')
        frames.append(frame)
    require(user_done, 'SDK input lifecycle missing')
    # 既存監査器で開始/完了・tool順序・thread/turn・明示finalを検査する。
    trace.completed_items(frames)
    return {'frames': frames, 'retainedNotifications': retained, 'requestIds': dict(bindings),
            'sentValueSha256': digest(sent), 'receivedValueSha256': digest(received)}


def diagnose(manifest_raw: bytes, host_events: list, sent: list, received: list,
             *, expected_final_text: str, actual_exit_code: int,
             allowed_warnings: tuple[str, ...] = ()) -> dict:
    """native子操作の結果一致だけを診断し、製品測定への適格性は常にfalseにする。"""
    require(type(actual_exit_code) is int and actual_exit_code == 0, 'SDK process failed')
    evidence = normalized(sent, received, allowed_warnings=allowed_warnings)
    manifest, manifest_digest, view = trace.manifest_view(manifest_raw)
    read = trace.audit_host(manifest, view, host_events)
    items = trace.completed_items(evidence['frames'])
    trace.audit_calls(host_events, items)
    finals = [i for i in items if i['type'] == 'agentMessage' and i['phase'] == 'final_answer']
    require(isinstance(expected_final_text, str) and len(finals) == 1 and
            finals[0]['text'] == expected_final_text, 'SDK final text mismatch')
    return {'status': 'sdk_child_trace_diagnostic_passed', 'hostCalls': len(host_events),
            'readResources': sorted(read), 'candidateManifestSha256': manifest_digest,
            'nativeEvidence': {k: v for k, v in evidence.items() if k != 'frames'},
            'providerParentBindingVerified': False, 'eligibleForMeasurement': False,
            'certifiesExpectedDecision': False, 'certifiesBehavior': False, 'certifiesSkillGate': False}


def scripted_response(raw: bytes) -> dict:
    """無課金診断用の固定SSEだけを検査する。実providerの一般形式へ拡張しない。"""
    require(isinstance(raw, bytes), 'original response bytes required')
    events = []
    for block in raw.decode('utf-8').split('\n\n'):
        if not block:
            continue
        lines = block.splitlines()
        require(len(lines) == 2 and lines[0].startswith('event: ') and lines[1].startswith('data: '),
                'unsupported diagnostic SSE framing')
        event = trace.strict_json(lines[1][6:])
        require(isinstance(event, dict) and event.get('type') == lines[0][7:], 'SSE event mismatch')
        events.append(event)
    types = [e['type'] for e in events]
    call_types = ['response.created', 'response.output_item.done', 'response.completed']
    final_types = ['response.created', 'response.output_item.added', 'response.output_text.delta',
                   'response.output_item.done', 'response.completed']
    require(types in (call_types, final_types), 'unsupported diagnostic response events')
    fields = {
        'response.created': {'type', 'response'},
        'response.completed': {'type', 'response'},
        'response.output_item.added': {'type', 'output_index', 'item'},
        'response.output_item.done': {'type', 'output_index', 'item'},
        'response.output_text.delta': {'type', 'item_id', 'output_index', 'content_index', 'delta'},
    }
    require(all(set(e) == fields[e['type']] for e in events), 'unknown diagnostic SSE event fields')
    first, last = events[0].get('response'), events[-1].get('response')
    for response in (first, last):
        require(isinstance(response, dict) and
                {'id', 'status', 'output'} <= set(response) <= {'id', 'object', 'status', 'output', 'error', 'incomplete_details'} and
                response.get('object', 'response') == 'response',
                'unknown or missing diagnostic SSE response fields')
        require(response.get('error') is None and response.get('incomplete_details') is None,
                'SSE error or incomplete response')
    require(isinstance(first, dict) and isinstance(last, dict) and first.get('status') == 'in_progress' and
            first.get('output') == [] and isinstance(first.get('id'), str) and bool(first['id']) and
            first['id'] == last.get('id') and last.get('status') == 'completed', 'SSE response lifecycle')
    done = events[-2]
    item = done.get('item')
    require(isinstance(item, dict) and type(done.get('output_index')) is int and done['output_index'] == 0 and
            trace.json_equal(last.get('output'), [item]),
            'SSE response output mismatch')
    if types == final_types:
        content = item.get('content')
        require(set(item) == {'type', 'id', 'role', 'phase', 'status', 'content'} and
                item.get('type') == 'message' and item.get('role') == 'assistant' and
                item.get('phase') == 'final_answer' and item.get('status') == 'completed' and
                isinstance(item.get('id'), str) and bool(item['id']) and
                isinstance(content, list) and len(content) == 1 and
                set(content[0]) == {'type', 'text', 'annotations'} and content[0]['type'] == 'output_text' and
                isinstance(content[0]['text'], str) and content[0]['annotations'] == [], 'SSE final message')
        added, delta = events[1], events[2]
        require(type(added.get('output_index')) is int and added['output_index'] == 0 and
                trace.json_equal(added.get('item'), {**item, 'status': 'in_progress', 'content': []}),
                'SSE final start mismatch')
        require(delta.get('item_id') == item.get('id') and type(delta.get('output_index')) is int and
                delta['output_index'] == 0 and type(delta.get('content_index')) is int and
                delta['content_index'] == 0 and delta.get('delta') == content[0]['text'], 'SSE final delta mismatch')
    return item


def diagnostic_environment(cwd: str) -> str:
    """2026-10-08に捕捉した局所診断だけの固定SDK環境文。実provider向けではない。"""
    require(isinstance(cwd, str) and bool(cwd), 'diagnostic cwd required')
    return ('<environment_context>\n  <cwd>' + cwd + '</cwd>\n  <shell>bash</shell>\n'
            '  <current_date>2026-10-08</current_date>\n  <timezone>Asia/Tokyo</timezone>\n'
            '  <filesystem><workspace_roots><root>' + cwd + '</root></workspace_roots>'
            '<permission_profile type="managed"><file_system type="restricted">'
            '<entry access="read"><special>:root</special></entry></file_system></permission_profile>'
            '</filesystem>\n</environment_context>')


def audit_provider_input(sent: list, before: list) -> str:
    """前置文脈も固定形へ照合し、同じprefixへの余分なメッセージ混入を拒否する。"""
    params = sent[2]['params']
    expected_input = {'type': 'message', 'role': 'user', 'content': [
        {'type': 'input_text', 'text': sent[3]['params']['input'][0]['text']}]}
    require(isinstance(before, list) and bool(before), 'provider input required')
    messages = []
    for value in before:
        require(isinstance(value, dict), 'provider input item required')
        if value.get('type') == 'additional_tools':
            require(len(before) == 5 and value is before[0] and set(value) == {'type', 'id', 'role', 'tools'} and
                    value['role'] == 'developer' and isinstance(value['id'], str) and bool(value['id']) and
                    digest(value['tools']) == DIAGNOSTIC_TOOLS_SHA, 'diagnostic tool context drift')
            continue
        require(set(value) <= {'type', 'id', 'role', 'content'} and set(value) >= {'type', 'role', 'content'} and
                value['type'] == 'message' and ('id' not in value or isinstance(value['id'], str) and bool(value['id'])),
                'provider message fields')
        messages.append({k: v for k, v in value.items() if k != 'id'})
    if 'cwd' not in params:
        require(not (set(params) & {'baseInstructions', 'developerInstructions'}),
                'synthetic provider profile forbids extra instructions')
        require(trace.json_equal(messages, [expected_input]) and len(before) == 1, 'synthetic provider context mismatch')
        return 'synthetic-one-input-only'
    require(params.get('modelProvider') == 'bitz_local_probe' and len(before) == 5 and len(messages) == 4,
            'fixed local SDK diagnostic context required')
    supplement = messages[1].get('content')
    require(isinstance(supplement, list) and len(supplement) == 4 and
            trace.json_equal(supplement[0], {'type': 'input_text', 'text': params.get('developerInstructions')}) and
            digest(supplement[1:]) == DIAGNOSTIC_CONTEXT_SHA, 'SDK generated context drift')
    expected = [
        {'type': 'message', 'role': 'developer', 'content': [{'type': 'input_text', 'text': params.get('baseInstructions')}]},
        {'type': 'message', 'role': 'developer', 'content': supplement},
        {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': diagnostic_environment(params['cwd'])}]},
        expected_input]
    require(trace.json_equal(messages, expected), 'provider/SDK complete input context mismatch')
    return 'sdk-0.160.1-local-diagnostic-2026-10-08'


def diagnose_exchange(manifest_raw: bytes, host_events: list, sent: list, received: list,
                      provider_requests: list, provider_responses: list[bytes], *,
                      expected_program: str, expected_final_text: str, actual_exit_code: int,
                      allowed_warnings: tuple[str, ...] = ()) -> dict:
    """固定1execのwire結果対応を追加診断する。nativeの親ID欠如は解消済みにしない。"""
    result = diagnose(manifest_raw, host_events, sent, received, expected_final_text=expected_final_text,
                      actual_exit_code=actual_exit_code, allowed_warnings=allowed_warnings)
    require(isinstance(provider_requests, list) and len(provider_requests) == 2 and
            isinstance(provider_responses, list) and len(provider_responses) == 2, 'two scripted exchanges required')
    for request in provider_requests:
        require(isinstance(request, dict) and request.get('model') == sent[2]['params']['model'] and
                cli.declared_tools(request) == ['functions.exec', 'functions.request_user_input_async', 'functions.wait'],
                'provider model or surface mismatch')
        allowed = {'model', 'input', 'tools'} if 'cwd' not in sent[2]['params'] else {
            'model', 'input', 'tool_choice', 'parallel_tool_calls', 'reasoning', 'store', 'stream',
            'include', 'prompt_cache_key', 'text', 'client_metadata'}
        require(set(request) == allowed, 'unknown or missing provider request fields')
    require(trace.json_equal({k: v for k, v in provider_requests[0].items() if k != 'input'},
            {k: v for k, v in provider_requests[1].items() if k != 'input'}), 'provider request settings drift')
    call = scripted_response(provider_responses[0])
    require(set(call) == {'type', 'call_id', 'name', 'namespace', 'input'} and
            call['type'] == 'custom_tool_call' and call['namespace'] == 'functions' and call['name'] == 'exec' and
            isinstance(call['call_id'], str) and bool(call['call_id']) and
            isinstance(expected_program, str) and call['input'] == expected_program, 'scripted exec binding mismatch')
    before, after = [request.get('input') for request in provider_requests]
    require(isinstance(before, list) and isinstance(after, list) and len(after) == len(before) + 2 and
            trace.json_equal(after[:len(before)], before), 'provider request prefix drift')
    profile = audit_provider_input(sent, before)
    require(not any(isinstance(i, dict) and i.get('type') in {'custom_tool_call', 'function_call',
                    'custom_tool_call_output', 'function_call_output'} for i in before), 'unexpected earlier provider calls')
    echoed, output = after[-2:]
    require(isinstance(echoed, dict) and set(echoed) == {*call, 'id'} and
            trace.json_equal({k: v for k, v in echoed.items() if k != 'id'}, call) and
            isinstance(echoed['id'], str) and bool(echoed['id']), 'provider echoed call drift')
    require(isinstance(output, dict) and set(output) == {'type', 'call_id', 'id', 'output'} and
            output['type'] == 'custom_tool_call_output' and output['call_id'] == call['call_id'] and
            isinstance(output['id'], str) and bool(output['id']), 'provider output binding drift')
    chunks = output['output']
    require(isinstance(chunks, list) and len(chunks) == 2 and
            all(isinstance(c, dict) and set(c) == {'type', 'text'} and c['type'] == 'input_text' and
                isinstance(c['text'], str) for c in chunks), 'scripted output chunks required')
    require(chunks[0]['text'].startswith('Script completed\nWall time ') and
            chunks[0]['text'].endswith(' seconds\nOutput:\n'), 'scripted exec completion missing')
    payload = trace.strict_json(chunks[1]['text'])
    require(isinstance(payload, dict) and set(payload) == {'kind', 'listed', 'read'} and
            payload['kind'] == 'read' and len(host_events) == 2 and
            [e['tool'] for e in host_events] == ['list_resources', 'read_resource'], 'scripted read output required')
    for key, event in zip(('listed', 'read'), host_events):
        wrapper = payload[key]
        require(isinstance(wrapper, dict) and set(wrapper) == {'content', 'isError'} and
                wrapper['isError'] is False and isinstance(wrapper['content'], list) and len(wrapper['content']) == 1,
                'scripted MCP wrapper mismatch')
        content = wrapper['content'][0]
        require(isinstance(content, dict) and set(content) == {'type', 'text'} and content['type'] == 'text' and
                trace.json_equal(trace.strict_json(content['text']), event['result']), 'host/provider result mismatch')
    final = scripted_response(provider_responses[1])
    require(final.get('type') == 'message' and final['content'][0]['text'] == expected_final_text,
            'provider/native final mismatch')
    native_finals = [f['params']['item'] for f in received if f.get('method') == 'item/completed' and
                     f.get('params', {}).get('item', {}).get('type') == 'agentMessage' and
                     f['params']['item'].get('phase') == 'final_answer']
    require(len(native_finals) == 1 and native_finals[0]['id'] == final['id'], 'provider/native final id mismatch')
    result.update(status='sdk_scripted_exchange_diagnostic_passed', providerCallId=call['call_id'],
                  providerCallOutputBindingVerified=True,
                  providerContextProfile=profile,
                  providerResponseSha256=[hashlib.sha256(r).hexdigest() for r in provider_responses],
                  providerRequestValueSha256=[digest(r) for r in provider_requests])
    return result


def audit_parent_links(events: list, received: list, provider_call_id: str) -> dict:
    """固定1execの原telemetryの親→cell→native子IDを検査する。複数/待機へ一般化しない。"""
    require(isinstance(events, list) and bool(events), 'original parent telemetry required')
    children = [f['params']['item'] for f in received if f.get('method') == 'item/completed' and
                f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
    require(len(children) == 2 and [c['tool'] for c in children] == ['list_resources', 'read_resource'],
            'two native children required')
    context = next(f['params'] for f in received if f.get('method') == 'turn/started')
    thread, turn = context['threadId'], context['turn']['id']
    expected = {provider_call_id: ('exec', 'functions', 'direct')}
    for item in children:
        require(item['id'] not in expected, 'parent/child id collision')
        expected[item['id']] = (item['tool'], 'mcp__production_routing', 'code_mode')
    received_calls, dispatched, ready, results = {}, {}, {}, {}
    timing = None
    cell = None
    runtime_ids = set()
    truncated_previews = []
    neutral = {'codex.conversation_starts', 'codex.startup_phase', 'codex.user_prompt',
               'codex.api_request', 'codex.turn_ttft'}
    base_fields = {'event.name', 'conversation.id', 'call_id'}
    identity_fields = {'turn_id', 'tool_name', 'tool_namespace', 'tool_source', 'cell.id', 'cell_id', 'runtime_tool_call_id'}
    result_fields = {'tool_result_seq', 'duration_ms', 'success', 'output_truncated', 'arguments_length',
                     'output_length', 'output_line_count', 'tool_origin', 'mcp_tool', 'event.timestamp',
                     'app.version', 'originator', 'terminal.type', 'model', 'slug'}
    for index, event in enumerate(events):
        require(isinstance(event, dict) and event.get('target') in {'codex_otel.trace_safe', 'codex_code_mode::timing'}
                and event.get('level') == 'INFO' and isinstance(event.get('fields'), dict), 'parent telemetry format')
        fields = event['fields']
        name = fields.get('event.name')
        if name in neutral:
            require(event['target'] == 'codex_otel.trace_safe' and fields.get('conversation.id') == thread,
                    'telemetry context drift')
            if name == 'codex.api_request':
                require(fields.get('auth.header_attached') is False and type(fields.get('attempt')) is int and
                        fields['attempt'] == 0 and type(fields.get('http.response.status_code')) is int and
                        fields['http.response.status_code'] == 200, 'diagnostic API request drift')
            continue
        if name == 'codex.code_mode.host_timing':
            require(event['target'] == 'codex_code_mode::timing' and timing is None and
                    set(fields) <= {'event.name', 'message', 'conversation_id', 'turn_id', 'call_id',
                                    'cell_id', 'tool_name', 'code_mode_host_duration_ns'} and
                    fields.get('conversation_id') == thread and fields.get('turn_id') == turn and
                    fields.get('call_id') == provider_call_id and fields.get('tool_name') == 'exec' and
                    isinstance(fields.get('cell_id'), str) and bool(fields['cell_id']) and
                    type(fields.get('code_mode_host_duration_ns')) is int and fields['code_mode_host_duration_ns'] >= 0,
                    'parent timing binding drift')
            timing = (index, fields)
            continue
        require(event['target'] == 'codex_otel.trace_safe' and fields.get('conversation.id') == thread,
                'tool telemetry thread mismatch')
        require(set(fields) <= base_fields | identity_fields |
                (result_fields if name == 'codex.tool_result' else set()), 'unknown tool telemetry fields')
        ident = fields.get('call_id')
        require(ident in expected, 'unexpected telemetry call')
        if name == 'codex.code_mode.nested_tool_dispatched':
            require(ident != provider_call_id and ident not in dispatched and fields.get('turn_id') == turn,
                    'nested dispatch duplicate or context drift')
            for key, value in zip(('tool_name', 'tool_namespace', 'tool_source'), expected[ident]):
                require(key not in fields or fields[key] == value, 'dispatch tool identity contradiction')
            require('cell_id' not in fields or fields['cell_id'] == fields.get('cell.id'), 'dispatch cell alias drift')
            dispatched[ident] = (index, fields)
            continue
        require(name in {'codex.tool_call_received', 'codex.tool_result_ready', 'codex.tool_result'},
                'unknown parent telemetry event')
        tool, namespace, source = expected[ident]
        require(fields.get('tool_name') == tool and fields.get('tool_namespace') == namespace,
                'telemetry tool binding drift')
        if name in {'codex.tool_result', 'codex.tool_result_ready'}:
            require(ident in received_calls, 'result before receipt')
            identity = received_calls[ident][1]
            expected_ids = {'turn_id': turn, 'tool_source': source,
                            'cell.id': identity.get('cell.id', cell), 'cell_id': identity.get('cell.id', cell),
                            'runtime_tool_call_id': identity.get('runtime_tool_call_id')}
            require(all(fields[k] == value for k, value in expected_ids.items() if k in fields),
                    'result cell/runtime/turn/source contradiction')
        if name == 'codex.tool_call_received':
            require(ident not in received_calls and fields.get('tool_source') == source, 'telemetry receipt duplicate/source')
            if source == 'direct':
                require(fields.get('turn_id') == turn and set(fields) == base_fields |
                        {'turn_id', 'tool_name', 'tool_namespace', 'tool_source'}, 'direct receipt context')
            else:
                value = fields.get('cell.id')
                runtime = fields.get('runtime_tool_call_id')
                require(isinstance(value, str) and bool(value) and isinstance(runtime, str) and bool(runtime) and
                        runtime not in runtime_ids and fields.get('turn_id') is None, 'child receipt identity')
                require(cell is None or cell == value, 'multiple diagnostic cells')
                require('cell_id' not in fields or fields['cell_id'] == value, 'receipt cell alias drift')
                cell = value
                runtime_ids.add(runtime)
            received_calls[ident] = (index, fields)
        elif name == 'codex.tool_result_ready':
            require(ident not in ready and fields.get('tool_source') == source and fields.get('turn_id') == turn,
                    'result ready duplicate/context')
            ready[ident] = index
        else:
            require(ident not in results and fields.get('success') == 'true', 'tool result failed or duplicate')
            if 'output_truncated' in fields:
                require(type(fields['output_truncated']) is bool, 'telemetry preview truncation type')
                if fields['output_truncated']:
                    truncated_previews.append(ident)
            for key, value in (('tool_origin', 'builtin' if source == 'direct' else 'mcp'),
                               ('mcp_tool', source == 'code_mode'), ('tool_result_seq', len(results) + 1)):
                require(key not in fields or type(fields[key]) is type(value) and fields[key] == value,
                        'result origin or sequence contradiction')
            results[ident] = index
    require(set(received_calls) == set(ready) == set(results) == set(expected) and
            set(dispatched) == {c['id'] for c in children} and timing is not None, 'parent milestones missing')
    require(timing[1]['cell_id'] == cell, 'parent cell mismatch')
    parent_start = received_calls[provider_call_id][0]
    for child in children:
        ident = child['id']
        start, fields = received_calls[ident]
        dispatch, dispatch_fields = dispatched[ident]
        require(dispatch_fields.get('cell.id') == cell and
                dispatch_fields.get('runtime_tool_call_id') == fields['runtime_tool_call_id'], 'dispatch cell/runtime drift')
        require(parent_start < start < dispatch < results[ident] < ready[ident] < timing[0] <
                results[provider_call_id] < ready[provider_call_id], 'parent milestone order drift')
    require(ready[children[0]['id']] < received_calls[children[1]['id']][0], 'sequential discovery/read telemetry order')
    native_order = [(f['method'], f['params']['item']['id']) for f in received if
                    f.get('method') in {'item/started', 'item/completed'} and
                    f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
    require(native_order == [(method, child['id']) for child in children
                            for method in ('item/started', 'item/completed')], 'sequential native child order')
    return {'status': 'scripted_parent_cell_child_ids_matched', 'scope': 'one-scripted-exec-two-mcp-calls',
            'parentCallId': provider_call_id, 'cellId': cell, 'nativeChildIds': [c['id'] for c in children],
            'traceEventCount': len(events), 'traceValueSha256': digest(events),
            'telemetryTruncatedPreviewCallIds': truncated_previews, 'certifiesTelemetryOutputBodies': False,
            'certifiesMultipleOrYieldedCells': False, 'eligibleForMeasurement': False}


def complete_trace_projection(raw_stderr: bytes, selected_log: bytes) -> list:
    """局所JSON loggerの全対象行と選択ログを原bytesで完全一致させる。欠落を許さない。"""
    require(isinstance(raw_stderr, bytes) and isinstance(selected_log, bytes), 'original log bytes required')
    selected, events = [], []
    for line in raw_stderr.splitlines(keepends=True):
        event = trace.strict_json(line)
        require(isinstance(event, dict) and isinstance(event.get('target'), str), 'unparseable local JSON telemetry')
        if event['target'] in {'codex_otel.trace_safe', 'codex_code_mode::timing'}:
            selected.append(line)
            events.append(event)
    require(b''.join(selected) == selected_log and bool(events), 'selected telemetry incomplete or modified')
    return events
