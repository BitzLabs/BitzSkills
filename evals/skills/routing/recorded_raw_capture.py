"""保存済みSDK捕捉の通知・終端を照合する。モデルや通信を起動しない。"""
import hashlib
import json
import os
from pathlib import Path
import production_operation_probe as operation
import production_cli_probe as cli
import production_sdk_probe as probe
import production_sdk_trace as sdk
import production_trace as trace
import source_guard as guard
import recorded_capture_artifacts as helper

ROOT = Path(__file__).resolve().parents[3]
require = trace.require
METHODS = ('rawResponseItem/completed', 'rawResponse/completed')


def legacy_sdk_records(raw):
    """v0.7の整形された複数JSONを再生成せず読む。JSONL適合とは扱わない。"""
    text, result, offset = raw.decode(), [], 0
    decoder = json.JSONDecoder()
    while offset < len(text):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset == len(text):
            break
        _, end = decoder.raw_decode(text, offset)
        result.append(trace.strict_json(text[offset:end]))
        offset = end
    return result


def raw_values(outgoing, delivered):
    raw = [f for f in outgoing if f.get('method', '').startswith('rawResponse')]
    side = [f for f in delivered if f.get('method', '').startswith('rawResponse')]
    require([f['method'] for f in raw] == [METHODS[0]] * 4 + [METHODS[1]] +
            [METHODS[0]] * 2 + [METHODS[1]], 'fixed raw event sequence')
    for frame in raw:
        require(set(frame) <= {'method', 'params', 'emittedAtMs'} and
                {'method', 'params'} <= set(frame), 'raw event fields')
        require('emittedAtMs' not in frame or type(frame['emittedAtMs']) is int and
                frame['emittedAtMs'] >= 0, 'raw event timestamp')
    # SDKが配送しない外側timestampだけを投影から除く。原RPC bytesには保持する。
    projected = [{k: f[k] for k in ('method', 'params')} for f in raw]
    require(trace.json_equal(projected, side), 'RPC/SDK raw notification payload mismatch')
    return raw


def check_terminal(value, incoming, outgoing):
    """成功フラグを要求し、固定模擬終端を開始RPCと原通知から再計算する。"""
    require(value.get('mockTurnCompleted') is True and value.get('mockFinalMatched') is True,
            'capture success flags')
    bindings = {}
    indices = []
    request_ids = []
    for method, key in [('thread/start', 'thread'), ('turn/start', 'turn')]:
        requests = [f for f in incoming if f.get('method') == method]
        require(len(requests) == 1, 'capture start request count')
        request = requests[0]
        request_id = request.get('id')
        require(type(request_id) in {int, str} and (not isinstance(request_id, str) or bool(request_id)) and
                not any(trace.json_equal(request_id, old) for old in request_ids), 'capture start request binding')
        request_ids.append(request_id)
        replies = [(i, f) for i, f in enumerate(outgoing) if 'id' in f and
                   trace.json_equal(f['id'], request['id'])]
        require(len(replies) == 1 and set(replies[0][1]) == {'id', 'result'} and
                isinstance(replies[0][1]['result'], dict) and
                isinstance(replies[0][1]['result'].get(key), dict), 'capture start response binding')
        item = replies[0][1]['result'][key]
        require(isinstance(item.get('id'), str) and bool(item['id']), 'capture start context ID')
        if key == 'thread':
            trace.check_thread_start(item)
        else:
            require(set(replies[0][1]['result']) == {'turn'}, 'capture turn start response fields')
            trace.check_turn_start(item)
        bindings[key] = item['id']
        indices.append(replies[0][0])
    turn_request = next(f for f in incoming if f.get('method') == 'turn/start')
    started = [(i, f.get('params')) for i, f in enumerate(outgoing) if f.get('method') == 'turn/started']
    require(isinstance(turn_request.get('params'), dict) and
            turn_request['params'].get('threadId') == bindings['thread'] and len(started) == 1 and
            isinstance(started[0][1], dict) and started[0][1].get('threadId') == bindings['thread'] and
            isinstance(started[0][1].get('turn'), dict) and
            started[0][1]['turn'].get('id') == bindings['turn'] and
            indices[0] < indices[1] < started[0][0], 'capture started context correlation')
    trace.check_turn_start(started[0][1]['turn'])
    require(operation.terminal_matches(outgoing, bindings['thread'], bindings['turn']) == (True, True),
            'capture final and completion correlation')
    final_index = next(i for i, f in enumerate(outgoing) if f.get('method') == 'item/completed' and
                       f.get('params', {}).get('item', {}).get('type') == 'agentMessage')
    require(started[0][0] < final_index, 'capture start/final order')
    return bindings['thread'], bindings['turn']


def check_capture(base, receipt_sha, *, legacy=False):
    value, digest = helper.receipt(base, expected_sha=receipt_sha)
    require(value['status'] == 'operation_diagnostic_captured' and value['namespaceExitCode'] == 0 and
            value['runtime'] == {'exitCode': 0, 'forcedShutdown': False} and
            value['localHttpRequestCount'] == value['hostEventCount'] == 2 and
            value['paidModelCalls'] == 0 and value['eligibleForMeasurement'] is False and
            value['experimentalRawEventsRequested'] is True and
            not value['localErrors'] and value['sdkErrorType'] is None and
            not value['serverRequestStops'] and not value['prohibitedFileExists'] and
            all(value['isolationChecks'].values()), 'capture terminal or finite scope')
    incoming, outgoing = [helper.frames(base, name) for name in ('rpc-in.jsonl', 'rpc-out.jsonl')]
    ident, turn = check_terminal(value, incoming, outgoing)
    contract = helper.read(str((base / 'contract.json').relative_to(ROOT)))
    contract_name = 'evals/skills/routing/production-operation-probe-v0.' + ('7' if legacy else '8') + '.json'
    require((base / 'contract.json').read_bytes() == cli.encoded(trace.strict_json(
            guard.git(ROOT, 'show', value['sourceCommit'] + ':' + contract_name))), 'capture contract Git projection')
    require(len(incoming) == 4 and incoming[2]['method'] == 'thread/start' and
            trace.json_equal(incoming[2]['params'], operation.thread_params(base, contract)) and
            incoming[3]['method'] == 'turn/start' and
            incoming[3]['params']['input'] == [{'type': 'text', 'text': 'LOCAL_SIMULATION_ONLY'}],
            'actual SDK raw flag or local input')
    supplied = (base / 'sdk-turn-notifications.jsonl').read_bytes()
    delivered = legacy_sdk_records(supplied) if legacy else [
        trace.strict_json(line) for line in supplied.splitlines()]
    raw = raw_values(outgoing, delivered)
    items = [f['params']['item'] for f in raw if f['method'] == METHODS[0]]
    require([i['type'] for i in items] == ['message', 'message', 'message',
            'custom_tool_call', 'custom_tool_call_output', 'message'], 'raw item kinds')
    for frame in raw:
        params = frame['params']
        fields = {'threadId', 'turnId', 'item'} if frame['method'] == METHODS[0] else {
            'threadId', 'turnId', 'responseId', 'usage', 'usageMetadata'}
        require(set(params) == fields and params['threadId'] == ident and params['turnId'] == turn,
                'raw notification context or fields')
    require(all(isinstance(i.get('id'), str) and bool(i['id']) for i in items) and
            len({i['id'] for i in items}) == 6, 'raw item IDs')
    for item in items:
        metadata = item.get('internal_chat_message_metadata_passthrough')
        require(isinstance(metadata, dict) and metadata.get('turn_id') == turn,
                'raw internal turn metadata')
    requests = [helper.read(str((base / f'request-{i}.json').relative_to(ROOT))) for i in (1, 2)]
    responses = [(base / f'response-{i}.sse').read_bytes() for i in (1, 2)]
    call, final = [sdk.scripted_response(r) for r in responses]
    require(call['input'] == operation.program('read', base) and call['call_id'] == 'probe-call',
            'original scripted program')
    raw_call, raw_output, raw_final = items[3:]
    strip_meta = lambda i: {k: v for k, v in i.items() if k != 'internal_chat_message_metadata_passthrough'}
    require(trace.json_equal({k: v for k, v in strip_meta(raw_call).items() if k != 'id'}, call) and
            trace.json_equal(strip_meta(raw_call), requests[1]['input'][-2]) and
            trace.json_equal(strip_meta(raw_output), requests[1]['input'][-1]), 'raw call/output wire correlation')
    expected_final = {k: final[k] for k in ('type', 'id', 'role', 'phase')}
    expected_final['content'] = [{'type': 'output_text', 'text': final['content'][0]['text']}]
    require(trace.json_equal(strip_meta(raw_final), expected_final), 'fixed final ResponseItem projection')
    for item in items[:3]:
        candidates = [i for i in requests[0]['input'] if i.get('id') == item['id']]
        require(len(candidates) == 1 and trace.json_equal(strip_meta(item), candidates[0]), 'raw input wire correlation')
    for frame, response in zip([f for f in raw if f['method'] == METHODS[1]], responses):
        last = [trace.strict_json(line[6:]) for line in response.splitlines() if line.startswith(b'data: ')][-1]
        require(frame['params']['responseId'] == last['response']['id'] and
                frame['params']['usage'] is None and frame['params']['usageMetadata'] is None,
                'fixed raw completed response')
    manifest, count = helper.check_snapshot(contract)
    host = helper.frames(base, 'host.jsonl')
    actual_manifest, _, view = trace.manifest_view(manifest)
    trace.audit_host(actual_manifest, view, host)
    children = [f['params']['item'] for f in outgoing if f.get('method') == 'item/completed' and
                f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
    trace.audit_calls(host, children)
    payload = trace.strict_json(raw_output['output'][1]['text'])
    require(set(payload) == {'kind', 'listed', 'read'} and payload['kind'] == 'read', 'raw MCP output payload')
    for key, event in zip(('listed', 'read'), host):
        wrapper = payload[key]
        require(isinstance(wrapper, dict) and set(wrapper) == {'isError', 'content'} and
                wrapper['isError'] is False and isinstance(wrapper['content'], list) and
                len(wrapper['content']) == 1, 'raw provider wrapper shape')
        content = wrapper['content'][0]
        require(isinstance(content, dict) and set(content) == {'type', 'text'} and
                content['type'] == 'text' and isinstance(content['text'], str) and
                trace.json_equal(trace.strict_json(content['text']), event['result']), 'raw provider/host body correlation')
    events = sdk.complete_trace_projection((base / 'runtime-stderr.bin').read_bytes(),
                                           (base / 'trace-safe.jsonl').read_bytes())
    links = sdk.audit_parent_links(events, outgoing, call['call_id'])
    try:
        sdk.diagnose_exchange(manifest, host, incoming, outgoing, requests, responses,
            expected_program=call['input'], expected_final_text='LOCAL_SIMULATION_ONLY',
            actual_exit_code=0, allowed_warnings=(helper.WARNING,))
    except ValueError as error:
        require(str(error) == 'unknown SDK thread params', 'unexpected legacy diagnostic stop')
    else:
        raise ValueError('experimental trace incorrectly accepted by legacy diagnostic')
    return {'sourceCommit': value['sourceCommit'], 'receiptSha256': digest, 'snapshotResourceCount': count,
            'rawItemCount': 6, 'rawCompletedCount': 2, 'sdkRawPayloadsMatchOriginalRpc': True,
            'sdkSideFormat': 'pretty-multiple-JSON-documents' if legacy else 'JSONL',
            'sdkDoesNotDeliverOuterTimestamp': True, 'rawNotificationsValueSha256': sdk.digest(raw),
            'parentLinks': links, 'existingSdkDiagnosticStatus': 'stopped_unknown_SDK_thread_params',
            'certifiesAllNativeLifecycle': False, 'rawItemsAreOriginalSseBytes': False,
            'eligibleForMeasurement': False, 'certifiesNativeProvider': False, 'certifiesSkillGate': False}
