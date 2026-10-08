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
    thread = thread_result.get('thread', {}).get('id')
    turn = by_number[3].get('turn', {}).get('id')
    require(isinstance(thread, str) and thread == expected['turn']['threadId'] and
            isinstance(turn, str) and bool(turn), 'SDK thread/turn response mismatch')
    require(thread_result.get('model') == expected['thread']['model'] and
            thread_result.get('modelProvider') == expected['thread'].get('modelProvider') and
            thread_result.get('approvalPolicy') == 'never' and
            thread_result.get('sandbox') == {'type': 'readOnly', 'networkAccess': False} and
            thread_result['thread'].get('ephemeral') is True and
            thread_result.get('instructionSources') == [], 'SDK effective policy mismatch')
    frames, retained, active, completed, deltas = [], [], {}, {}, {}
    user_id = None
    user_done = False
    turn_started = False
    for index, original in enumerate(received):
        if 'id' in original:
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
            require(isinstance(item, dict) and isinstance(item.get('id'), str), 'SDK item required')
            require(params['threadId'] == thread and params['turnId'] == turn, 'SDK item context mismatch')
            ident = item['id']
            if item.get('type') == 'userMessage':
                require(turn_started, 'SDK input before turn started')
                content = [{'type': 'text', 'text': expected['turn']['input'][0]['text'], 'text_elements': []}]
                require(set(item) == {'type', 'id', 'clientId', 'content'} and item['content'] == content and
                        item['clientId'] is None, 'SDK input message mismatch')
                if method == 'item/started':
                    require(user_id is None and not active, 'SDK duplicate or late user input')
                    user_id = ident
                    active[ident] = item
                else:
                    require(ident == user_id and ident in active and active[ident] == item and not user_done,
                            'SDK input lifecycle mismatch')
                    active.pop(ident)
                    user_done = True
                retained.append({'rawIndex': index, 'kind': method + '/userMessage', 'sha256': digest(original)})
                continue
            require(user_done and ident != user_id, 'SDK action before input completed or reused input id')
            if item.get('type') == 'agentMessage':
                require(not item.get('questions') and item.get('delivery') is None and
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
                    terminal['items'] == [v for v in completed.values() if v.get('type') == 'agentMessage' and
                                          v.get('phase') == 'final_answer'], 'SDK turn summary mismatch')
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
    first, last = events[0].get('response'), events[-1].get('response')
    require(isinstance(first, dict) and isinstance(last, dict) and first.get('status') == 'in_progress' and
            first.get('output') == [] and isinstance(first.get('id'), str) and
            first['id'] == last.get('id') and last.get('status') == 'completed', 'SSE response lifecycle')
    done = events[-2]
    item = done.get('item')
    require(isinstance(item, dict) and done.get('output_index') == 0 and last.get('output') == [item],
            'SSE response output mismatch')
    if types == final_types:
        content = item.get('content')
        require(item.get('type') == 'message' and item.get('role') == 'assistant' and
                item.get('phase') == 'final_answer' and item.get('status') == 'completed' and
                isinstance(content, list) and len(content) == 1 and
                set(content[0]) == {'type', 'text', 'annotations'} and content[0]['type'] == 'output_text' and
                isinstance(content[0]['text'], str) and content[0]['annotations'] == [], 'SSE final message')
        added, delta = events[1], events[2]
        require(added.get('output_index') == 0 and added.get('item') == {**item, 'status': 'in_progress', 'content': []},
                'SSE final start mismatch')
        require(delta.get('item_id') == item.get('id') and delta.get('output_index') == 0 and
                delta.get('content_index') == 0 and delta.get('delta') == content[0]['text'], 'SSE final delta mismatch')
    return item


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
    call = scripted_response(provider_responses[0])
    require(set(call) == {'type', 'call_id', 'name', 'namespace', 'input'} and
            call['type'] == 'custom_tool_call' and call['namespace'] == 'functions' and call['name'] == 'exec' and
            isinstance(call['call_id'], str) and bool(call['call_id']) and
            isinstance(expected_program, str) and call['input'] == expected_program, 'scripted exec binding mismatch')
    before, after = [request.get('input') for request in provider_requests]
    require(isinstance(before, list) and isinstance(after, list) and len(after) == len(before) + 2 and
            after[:len(before)] == before, 'provider request prefix drift')
    require(not any(isinstance(i, dict) and i.get('type') in {'custom_tool_call', 'function_call',
                    'custom_tool_call_output', 'function_call_output'} for i in before), 'unexpected earlier provider calls')
    echoed, output = after[-2:]
    require(isinstance(echoed, dict) and set(echoed) == {*call, 'id'} and
            {k: v for k, v in echoed.items() if k != 'id'} == call and
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
                trace.strict_json(content['text']) == event['result'], 'host/provider result mismatch')
    final = scripted_response(provider_responses[1])
    require(final.get('type') == 'message' and final['content'][0]['text'] == expected_final_text,
            'provider/native final mismatch')
    result.update(status='sdk_scripted_exchange_diagnostic_passed', providerCallId=call['call_id'],
                  providerCallOutputBindingVerified=True,
                  providerResponseSha256=[hashlib.sha256(r).hexdigest() for r in provider_responses],
                  providerRequestValueSha256=[digest(r) for r in provider_requests])
    return result
