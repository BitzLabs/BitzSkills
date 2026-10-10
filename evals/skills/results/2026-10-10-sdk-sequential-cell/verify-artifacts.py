"""固定2exec捕捉を原bytesとGitへ照合する。読取りだけで認定やモデル起動は行わない。"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import os
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / '.venv/production-operation-sequential-read-10'
SOURCE = '27c399431ab09737927914e1b6942775bd229f43'
RECEIPT_SHA = 'b390a1791cdf06fdce9759f4d56b90cab66e2ce28022f902fd8dff347befb77b'
CONTRACT = 'evals/skills/routing/production-operation-probe-v0.10.json'
spec = importlib.util.spec_from_file_location('sequential_capture_helpers',
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
            value['scenario'] == 'sequential-read' and value['localHttpRequestCount'] == 3 and
            value['hostEventCount'] == 2 and value['eligibleForMeasurement'] is False and
            value['experimentalRawEventsRequested'] is True and value['certifiesNativeProvider'] is False and
            value['certifiesSkillGate'] is False and not value['localErrors'] and
            value['sdkErrorType'] is None and not value['serverRequestStops'] and
            value['prohibitedFileExists'] is False and all(v is True for v in value['isolationChecks'].values()),
            'sequential capture finite scope')
    require(trace.json_equal(value['sourceGuards']['before'], value['sourceGuards']['after']),
            'sequential source guard drift')
    contract = trace.strict_json((BASE / 'contract.json').read_bytes())
    require((BASE / 'contract.json').read_bytes() == raw.cli.encoded(trace.strict_json(
            guard.git(ROOT, 'show', SOURCE + ':' + CONTRACT))) and operation.raw_events_enabled(contract),
            'sequential original contract Git')
    incoming, outgoing, host = [helper.frames(BASE, name) for name in
                               ('rpc-in.jsonl', 'rpc-out.jsonl', 'host.jsonl')]
    thread, turn = raw.check_terminal(value, incoming, outgoing)
    require(len(incoming) == 4 and incoming[2]['method'] == 'thread/start' and
            trace.json_equal(incoming[2]['params'], operation.thread_params(BASE, contract)) and
            incoming[3]['method'] == 'turn/start' and
            incoming[3]['params']['input'] == [{'type': 'text', 'text': 'LOCAL_SIMULATION_ONLY'}],
            'sequential SDK input binding')
    requests = [trace.strict_json((BASE / f'request-{i}.json').read_bytes()) for i in (1, 2, 3)]
    responses = [(BASE / f'response-{i}.sse').read_bytes() for i in (1, 2, 3)]
    call, wait, final = [sdk.scripted_response(r) for r in responses]
    require(responses[0] == operation.tool_reply('sequential-read', BASE) and
            responses[1] == operation.sequential_reply(requests[1]) and
            responses[2] == raw.cli.simulation_reply(), 'sequential fixed original SSE')
    require(call['call_id'] == 'probe-call' and wait['call_id'] == 'probe-read' and
            trace.json_equal(requests[1]['input'][:-2], requests[0]['input']) and
            trace.json_equal(requests[2]['input'][:-2], requests[1]['input']), 'sequential provider prefix')
    captured = [f for f in outgoing if f.get('method', '').startswith('rawResponse')]
    require([f['method'] for f in captured] == [raw.METHODS[0]] * 4 + [raw.METHODS[1]] +
            [raw.METHODS[0]] * 2 + [raw.METHODS[1]] + [raw.METHODS[0]] * 2 + [raw.METHODS[1]],
            'sequential raw sequence')
    delivered = helper.frames(BASE, 'sdk-turn-notifications.jsonl')
    require(trace.json_equal([{k: f[k] for k in ('method', 'params')} for f in captured],
            [f for f in delivered if f.get('method', '').startswith('rawResponse')]), 'sequential SDK/RPC values')
    for f in captured:
        require(set(f) <= {'method', 'params', 'emittedAtMs'} and {'method', 'params'} <= set(f) and
                ('emittedAtMs' not in f or type(f['emittedAtMs']) is int and f['emittedAtMs'] >= 0),
                'sequential original raw fields')
        p = f['params']
        fields = {'threadId', 'turnId', 'item'} if f['method'] == raw.METHODS[0] else {
            'threadId', 'turnId', 'responseId', 'usage', 'usageMetadata'}
        require(set(p) == fields and p['threadId'] == thread and p['turnId'] == turn,
                'sequential raw context')
    items = [f['params']['item'] for f in captured if f['method'] == raw.METHODS[0]]
    require([i['type'] for i in items] == ['message', 'message', 'message', 'custom_tool_call',
            'custom_tool_call_output', 'custom_tool_call', 'custom_tool_call_output', 'message'] and
            all(isinstance(i.get('id'), str) and i['id'] for i in items) and
            len({i['id'] for i in items}) == 8, 'sequential raw item identity')
    require(all(i.get('internal_chat_message_metadata_passthrough', {}).get('turn_id') == turn
                for i in items), 'sequential internal metadata')
    strip = lambda i: {k: v for k, v in i.items() if k != 'internal_chat_message_metadata_passthrough'}
    require(trace.json_equal([strip(i) for i in items[:3]], requests[0]['input'][2:5]),
            'sequential raw initial context')
    for offset, request, scripted in [(3, requests[1], call), (5, requests[2], wait)]:
        require(trace.json_equal([strip(i) for i in items[offset:offset+2]], request['input'][-2:]) and
                trace.json_equal({k: v for k, v in strip(items[offset]).items() if k != 'id'}, scripted),
                'sequential raw call/output binding')
    expected_final = {k: final[k] for k in ('type', 'id', 'role', 'phase')}
    expected_final['content'] = [{'type': 'output_text', 'text': final['content'][0]['text']}]
    require(trace.json_equal(strip(items[-1]), expected_final), 'sequential fixed final projection')
    done = [f for f in captured if f['method'] == raw.METHODS[1]]
    for f, response in zip(done, responses):
        last = [trace.strict_json(l[6:]) for l in response.splitlines() if l.startswith(b'data: ')][-1]
        require(f['params']['responseId'] == last['response']['id'] and
                f['params']['usage'] is None and f['params']['usageMetadata'] is None, 'sequential raw completed')
    stages, observation = operation.sequential_observation(requests, host, responses, BASE)
    require(trace.json_equal(stages, value['outputObjects']) and
            trace.json_equal(observation, value['sequentialExecObservation']), 'original sequential stages and bindings')
    manifest, resource_count = helper.check_snapshot(contract)
    actual, _, view = trace.manifest_view(manifest)
    trace.audit_host(actual, view, host)
    children = [f['params']['item'] for f in outgoing if f.get('method') == 'item/completed' and
                f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
    trace.audit_calls(host, children)
    for payload, key, event in zip(stages, ('listed', 'read'), host):
        require(set(payload) == {'kind', 'stage', key} and payload['kind'] == 'sequential-read',
                'sequential payload shape')
        wrapper = payload[key]
        require(set(wrapper) == {'isError', 'content'} and wrapper['isError'] is False and
                len(wrapper['content']) == 1 and set(wrapper['content'][0]) == {'type', 'text'} and
                wrapper['content'][0]['type'] == 'text' and
                trace.json_equal(trace.strict_json(wrapper['content'][0]['text']), event['result']),
                'sequential host/provider body')
    events = sdk.complete_trace_projection((BASE / 'runtime-stderr.bin').read_bytes(),
                                           (BASE / 'trace-safe.jsonl').read_bytes())
    # 旧監査がwaitを黙って無視して通さないことだけを確認する。新しい複数セル相関監査は別工程。
    try:
        sdk.audit_parent_links(events, outgoing, call['call_id'])
    except ValueError as e:
        require(str(e) == 'unexpected telemetry call', 'unexpected old parent audit stop')
    else:
        raise ValueError('legacy parent audit accepted sequential continuation')
    return {'status': 'fixed_sequential_capture_original_bytes_rechecked', 'sourceCommit': SOURCE,
            'receiptSha256': digest, 'localHttpRequests': 3, 'hostCalls': 2, 'snapshotResources': resource_count,
            'rawItems': 8, 'rawCompleted': 3, 'traceEventCount': len(events),
            'observedCellIds': [e['fields']['cell.id'] for e in events if
                e['fields']['event.name'] == 'codex.tool_call_received' and
                e['fields'].get('tool_source') == 'code_mode'],
            'stages': ['listed', 'read'], 'rpcSdkPayloadsMatch': True,
            'providerHostBodiesMatch': True, 'completeTargetTelemetryPreserved': True,
            'legacyParentAuditStatus': 'stopped_unexpected_telemetry_call',
            'certifiesMultipleCellCorrelation': False, 'certifiesAllNativeLifecycle': False,
            'certifiesNativeProvider': False, 'certifiesSkillGate': False, 'eligibleForMeasurement': False}


def run(source):
    require(guard.git(ROOT, 'status', '--porcelain') == b'' and
            guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean sequential verification HEAD')
    contract = trace.strict_json(guard.git(ROOT, 'show', source + ':evals/skills/routing/sdk-raw-response-review-v0.7.json'))
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    capture = check_capture()
    output = ROOT / '.venv/production-sdk-sequential-capture-verification-01'
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'sequential verification output symlink')
    output.mkdir(mode=0o700)
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1'))
    raw.cli.exclusive(output / 'tests.stdout', process.stdout)
    raw.cli.exclusive(output / 'tests.stderr', process.stderr)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    require(process.returncode == 0 and matched is not None, 'sequential full suite failed')
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    require(before == after and guard.git(ROOT, 'status', '--porcelain') == b'', 'sequential verification source drift')
    value = {'status': 'sdk_sequential_capture_artifacts_rechecked', 'phase': 4, 'sourceCommit': source,
             'capture': capture, 'sourceGuards': {'before': before, 'after': after},
             'newMockTrialsDuringVerification': 0, 'paidModelCalls': 0, 'eligibleForMeasurement': False,
             'phaseComplete': False, 'tests': {'count': int(matched[1]), 'seconds': float(matched[2]),
                 'exitCode': process.returncode, 'command': command,
                 'stdoutSha256': sha(process.stdout), 'stderrSha256': sha(process.stderr)}}
    raw.cli.exclusive(output / 'summary.json', raw.cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'capture', 'sourceGuards'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    run(parser.parse_args().source)
