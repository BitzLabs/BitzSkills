"""固定yield/wait捕捉を原bytesとGitへ照合する。読取りだけで認定やモデル起動は行わない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / '.venv/production-operation-yielded-read-09'
SOURCE = '5ddc3c3f1ac052e5990df32e3ed2de806ce6af85'
RECEIPT_SHA = 'eba92afac912898ffc7fa7e159fd47fd86f67196212ec3d0adfa11128b8f3904'
CONTRACT = 'evals/skills/routing/production-operation-probe-v0.9.json'
spec = importlib.util.spec_from_file_location('yielded_capture_helpers',
    ROOT / 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py')
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)
helper, operation, sdk, trace, guard = raw.helper, raw.operation, raw.sdk, raw.trace, raw.guard
require = trace.require


def sha(value):
    return hashlib.sha256(value).hexdigest()


def check_capture():
    value, digest = helper.receipt(BASE, expected_sha=RECEIPT_SHA)
    require(value['sourceCommit'] == SOURCE and value['status'] == 'operation_diagnostic_captured' and
            value['scenario'] == 'yielded-read' and value['localHttpRequestCount'] == 3 and
            value['hostEventCount'] == 2 and value['eligibleForMeasurement'] is False and
            value['experimentalRawEventsRequested'] is True and value['certifiesNativeProvider'] is False and
            value['certifiesSkillGate'] is False and not value['localErrors'] and
            value['sdkErrorType'] is None and not value['serverRequestStops'] and
            value['prohibitedFileExists'] is False and all(v is True for v in value['isolationChecks'].values()),
            'yielded capture finite scope')
    require(trace.json_equal(value['sourceGuards']['before'], value['sourceGuards']['after']),
            'yielded source guard drift')
    contract = trace.strict_json((BASE / 'contract.json').read_bytes())
    require((BASE / 'contract.json').read_bytes() == raw.cli.encoded(trace.strict_json(
            guard.git(ROOT, 'show', SOURCE + ':' + CONTRACT))) and operation.raw_events_enabled(contract),
            'yielded original contract Git')
    incoming, outgoing, host = [helper.frames(BASE, name) for name in
                               ('rpc-in.jsonl', 'rpc-out.jsonl', 'host.jsonl')]
    thread, turn = raw.check_terminal(value, incoming, outgoing)
    require(len(incoming) == 4 and incoming[2]['method'] == 'thread/start' and
            trace.json_equal(incoming[2]['params'], operation.thread_params(BASE, contract)) and
            incoming[3]['method'] == 'turn/start' and
            incoming[3]['params']['input'] == [{'type': 'text', 'text': 'LOCAL_SIMULATION_ONLY'}],
            'yielded SDK input binding')
    requests = [trace.strict_json((BASE / f'request-{i}.json').read_bytes()) for i in (1, 2, 3)]
    responses = [(BASE / f'response-{i}.sse').read_bytes() for i in (1, 2, 3)]
    call, wait, final = [sdk.scripted_response(r) for r in responses]
    require(responses[0] == operation.tool_reply('yielded-read', BASE) and
            responses[1] == operation.wait_reply(requests[1]) and
            responses[2] == raw.cli.simulation_reply(), 'yielded fixed original SSE')
    require(call['call_id'] == 'probe-call' and wait['call_id'] == 'probe-wait' and
            trace.json_equal(requests[1]['input'][:-2], requests[0]['input']) and
            trace.json_equal(requests[2]['input'][:-2], requests[1]['input']), 'yielded provider prefix')
    captured = [f for f in outgoing if f.get('method', '').startswith('rawResponse')]
    require([f['method'] for f in captured] == [raw.METHODS[0]] * 4 + [raw.METHODS[1]] +
            [raw.METHODS[0]] * 2 + [raw.METHODS[1]] + [raw.METHODS[0]] * 2 + [raw.METHODS[1]],
            'yielded raw sequence')
    delivered = helper.frames(BASE, 'sdk-turn-notifications.jsonl')
    require(trace.json_equal([{k: f[k] for k in ('method', 'params')} for f in captured],
            [f for f in delivered if f.get('method', '').startswith('rawResponse')]), 'yielded SDK/RPC values')
    for f in captured:
        require(set(f) <= {'method', 'params', 'emittedAtMs'} and {'method', 'params'} <= set(f) and
                ('emittedAtMs' not in f or type(f['emittedAtMs']) is int and f['emittedAtMs'] >= 0),
                'yielded original raw fields')
        p = f['params']
        fields = {'threadId', 'turnId', 'item'} if f['method'] == raw.METHODS[0] else {
            'threadId', 'turnId', 'responseId', 'usage', 'usageMetadata'}
        require(set(p) == fields and p['threadId'] == thread and p['turnId'] == turn,
                'yielded raw context')
    items = [f['params']['item'] for f in captured if f['method'] == raw.METHODS[0]]
    require([i['type'] for i in items] == ['message', 'message', 'message', 'custom_tool_call',
            'custom_tool_call_output', 'function_call', 'function_call_output', 'message'] and
            all(isinstance(i.get('id'), str) and i['id'] for i in items) and
            len({i['id'] for i in items}) == 8, 'yielded raw item identity')
    require(all(i.get('internal_chat_message_metadata_passthrough', {}).get('turn_id') == turn
                for i in items), 'yielded internal metadata')
    strip = lambda i: {k: v for k, v in i.items() if k != 'internal_chat_message_metadata_passthrough'}
    require(trace.json_equal([strip(i) for i in items[:3]], requests[0]['input'][2:5]),
            'yielded raw initial context')
    for offset, request, scripted in [(3, requests[1], call), (5, requests[2], wait)]:
        require(trace.json_equal([strip(i) for i in items[offset:offset+2]], request['input'][-2:]) and
                trace.json_equal({k: v for k, v in strip(items[offset]).items() if k != 'id'}, scripted),
                'yielded raw call/output binding')
    expected_final = {k: final[k] for k in ('type', 'id', 'role', 'phase')}
    expected_final['content'] = [{'type': 'output_text', 'text': final['content'][0]['text']}]
    require(trace.json_equal(strip(items[-1]), expected_final), 'yielded fixed final projection')
    done = [f for f in captured if f['method'] == raw.METHODS[1]]
    for f, response in zip(done, responses):
        last = [trace.strict_json(l[6:]) for l in response.splitlines() if l.startswith(b'data: ')][-1]
        require(f['params']['responseId'] == last['response']['id'] and
                f['params']['usage'] is None and f['params']['usageMetadata'] is None, 'yielded raw completed')
    stages = operation.output_objects(requests[1]) + operation.output_objects(requests[2], 'probe-wait')
    require(operation.yielded_cell_id(requests[1]) == '1' and
            operation.yielded_output(requests[2], 'probe-wait').startswith('Script completed\n') and
            [p.get('stage') for p in stages] == ['listed', 'read'] and
            trace.json_equal(stages, value['outputObjects']) and
            trace.json_equal(value['yieldedCellObservation'],
                {'cellId': '1', 'waitCompleted': True, 'stages': ['listed', 'read']}), 'yielded output stages')
    manifest, resource_count = helper.check_snapshot(contract)
    actual, _, view = trace.manifest_view(manifest)
    trace.audit_host(actual, view, host)
    children = [f['params']['item'] for f in outgoing if f.get('method') == 'item/completed' and
                f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
    trace.audit_calls(host, children)
    for payload, key, event in zip(stages, ('listed', 'read'), host):
        require(set(payload) == {'kind', 'stage', key} and payload['kind'] == 'yielded-read',
                'yielded payload shape')
        wrapper = payload[key]
        require(set(wrapper) == {'isError', 'content'} and wrapper['isError'] is False and
                len(wrapper['content']) == 1 and set(wrapper['content'][0]) == {'type', 'text'} and
                wrapper['content'][0]['type'] == 'text' and
                trace.json_equal(trace.strict_json(wrapper['content'][0]['text']), event['result']),
                'yielded host/provider body')
    events = sdk.complete_trace_projection((BASE / 'runtime-stderr.bin').read_bytes(),
                                           (BASE / 'trace-safe.jsonl').read_bytes())
    # 旧監査がwaitを黙って無視して通さないことだけを確認する。新しい継続相関監査は別工程。
    try:
        sdk.audit_parent_links(events, outgoing, call['call_id'])
    except ValueError as e:
        require(str(e) == 'unexpected telemetry call', 'unexpected old parent audit stop')
    else:
        raise ValueError('legacy parent audit accepted yielded continuation')
    return {'status': 'fixed_yielded_capture_original_bytes_rechecked', 'sourceCommit': SOURCE,
            'receiptSha256': digest, 'localHttpRequests': 3, 'hostCalls': 2, 'snapshotResources': resource_count,
            'rawItems': 8, 'rawCompleted': 3, 'traceEventCount': len(events), 'cellId': '1',
            'stages': ['listed', 'read'], 'rpcSdkPayloadsMatch': True,
            'providerHostBodiesMatch': True, 'completeTargetTelemetryPreserved': True,
            'legacyParentAuditStatus': 'stopped_unexpected_telemetry_call',
            'certifiesYieldedParentCorrelation': False, 'certifiesAllNativeLifecycle': False,
            'certifiesNativeProvider': False, 'certifiesSkillGate': False, 'eligibleForMeasurement': False}


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    require(trace.json_equal(check_capture(), summary['capture']), 'yielded recorded capture')
    tests = summary['tests']
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((BASE / name).read_bytes()) == tests[key], 'yielded original tests hash')
    match = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (BASE / 'tests.stderr').read_bytes())
    require(match and int(match[1]) == tests['count'] == 476 and float(match[2]) == tests['seconds'] and
            tests['exitCode'] == 0 and tests['sourceCommit'] == SOURCE, 'yielded actual tests terminal')
    require(summary['newMockTrials'] == 1 and summary['newLocalHttpRequests'] == 3 and
            summary['paidModelCalls'] == summary['independentSolInvocations'] == 0 and
            summary['phaseComplete'] is False and summary['eligibleForMeasurement'] is False and
            summary['independentReviewStatus'] == 'not_started_auto_review_rejected', 'yielded counters/scope')
    print(json.dumps({'status': 'recorded_yielded_capture_matches_original_bytes', 'tests': 476,
                      'rawItems': 8, 'rawCompleted': 3, 'traceRows': 24, 'mockTrials': 1,
                      'localHttpRequests': 3, 'paidModelCalls': 0, 'independentSolInvocations': 0,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
