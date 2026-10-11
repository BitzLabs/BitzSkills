"""実接続原記録の限定照合。旧API合計条件の未達を保持し、wire/Gateを認定しない。"""
import hashlib
import json
from pathlib import Path
import re

import production_cli_probe as cli
import production_connection_probe as connection
import production_ledger as ledger
import production_trace as trace
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rollout_values(manifest_raw, events_raw, payloads, *, thread, turn, native_usage):
    manifest = trace.strict_json(manifest_raw)
    trace.require(manifest['schema_version'] == 1 and manifest['root_thread_id'] == thread and
                  manifest['raw_event_log'] == 'trace.jsonl' and manifest['payloads_dir'] == 'payloads', 'original rollout manifest')
    events = [trace.strict_json(line) for line in events_raw.splitlines()]
    for i, event in enumerate(events, 1):
        trace.require(type(event['seq']) is int and event['seq'] == i and event['schema_version'] == 1 and
                      event['rollout_id'] == manifest['rollout_id'], 'continuous original rollout')
    kinds = [e['payload']['type'] for e in events]
    required = ['rollout_started', 'thread_started', 'codex_turn_started', 'inference_started',
                'inference_completed', 'codex_turn_ended', 'thread_ended', 'rollout_ended']
    trace.require(all(kinds.count(k) == 1 for k in required) and kinds[0] == 'rollout_started' and
                  kinds[-1] == 'rollout_ended' and [kinds.index(k) for k in required] == sorted(kinds.index(k) for k in required),
                  'one completed inference lifecycle')
    trace.require(all(k in {*required, 'protocol_event_observed'} for k in kinds), 'unknown rollout profile')
    start = events[kinds.index('inference_started')]
    completed = events[kinds.index('inference_completed')]
    ended = events[kinds.index('codex_turn_ended')]
    for event in [start, completed, ended]:
        trace.require(event['thread_id'] == thread and event['codex_turn_id'] == turn, 'original inference context')
    value = start['payload']
    trace.require(value['thread_id'] == thread and value['codex_turn_id'] == turn and value['model'] == 'gpt-6.1-sol' and
                  value['provider_name'] == 'OpenAI' and isinstance(value['inference_call_id'], str) and
                  bool(value['inference_call_id']) and completed['payload']['inference_call_id'] == value['inference_call_id'] and
                  ended['payload'].get('status') == 'completed', 'original inference identity and completion')

    def payload(reference, kind):
        trace.require(reference['kind'] == {'type': kind} and isinstance(reference['path'], str) and
                      re.fullmatch(r'payloads/[0-9]+\.json', reference['path']) and reference['path'] in payloads,
                      'hashed original payload reference')
        return payloads[reference['path']]

    request_raw = payload(value['request_payload'], 'inference_request')
    request = trace.strict_json(request_raw)
    response = trace.strict_json(payload(completed['payload']['response_payload'], 'inference_response'))
    trace.require(request['model'] == 'gpt-6.1-sol' and request['text']['format']['type'] == 'json_schema' and
                  request['text']['format']['strict'] is True and
                  trace.json_equal(request['text']['format']['schema'], connection.SCHEMA), 'original public request schema')
    items = request['input']
    roles = [item.get('role') for item in items]
    trace.require(roles == ['developer', 'developer', 'developer', 'user', 'user'] and
                  cli.declared_tools(request) == ['functions.exec', 'functions.request_user_input_async', 'functions.wait'],
                  'bounded original client input and metadata declarations')
    texts = []
    for item in items:
        if item.get('type') == 'additional_tools':
            continue
        trace.require(isinstance(item.get('content'), list) and all(isinstance(c, dict) and c.get('type') == 'input_text' and
                      isinstance(c.get('text'), str) for c in item['content']), 'original text input profile')
        texts.extend(c['text'] for c in item['content'])
    trace.require(all(any(value in text for text in texts) for value in [connection.BASE, connection.DEVELOPER, connection.PROMPT]),
                  'public caller strings present in original client request')
    outputs = response['output_items']
    trace.require(len(outputs) == 1 and outputs[0]['type'] == 'message' and outputs[0]['role'] == 'assistant' and
                  outputs[0]['phase'] == 'final_answer' and
                  all(c.get('type') == 'output_text' and isinstance(c.get('text'), str) for c in outputs[0]['content']) and
                  trace.json_equal(trace.strict_json(''.join(c['text'] for c in outputs[0]['content'])), connection.FINAL),
                  'original rollout final projection')
    usage = response['token_usage']
    mapping = {'input_tokens': 'inputTokens', 'cached_input_tokens': 'cachedInputTokens',
               'cache_write_input_tokens': 'cacheWriteInputTokens', 'output_tokens': 'outputTokens',
               'reasoning_output_tokens': 'reasoningOutputTokens', 'total_tokens': 'totalTokens'}
    trace.require(set(usage) == set(mapping) and all(type(v) is int and v >= 0 for v in usage.values()) and
                  trace.json_equal({k: native_usage[v] for k, v in mapping.items()}, usage), 'native and rollout usage')
    return dict(rolloutEvents=len(events), initialInputRoles=roles, requestPayloadSha256=sha(request_raw), tokenUsage=usage)


def inspect(base, *, source, contract_path, receipt_sha):
    ledger.safe_tree(base)
    raw = (base / 'receipt.json').read_bytes()
    trace.require(sha(raw) == receipt_sha, 'original connection receipt drift')
    receipt = trace.strict_json(raw)
    paths = connection.original_artifact_paths(base)
    trace.require({str(p.relative_to(base)) for p in paths} == set(receipt['artifactSha256']), 'complete allowed artifact inventory')
    required = {'contract.json', 'config.json', 'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-result.json', 'runtime-stderr.bin',
                'trace-safe.jsonl', 'isolated-result.json', 'version.stdout', 'reservation.json', 'invocation.json'}
    trace.require(required <= set(receipt['artifactSha256']), 'required originals hashed')
    for path in paths:
        ledger.safe_tree(path)
        trace.require(sha(path.read_bytes()) == receipt['artifactSha256'][str(path.relative_to(base))], 'original artifact drift')
    contract_raw = guard.git(ROOT, 'show', source + ':' + contract_path)
    contract = trace.strict_json(contract_raw)
    trace.require((base / 'contract.json').read_bytes() == contract_raw, 'original contract bytes')
    expected_sources = {p: sha(guard.git(ROOT, 'show', source + ':' + p)) for p in contract['sourceFiles']}
    before, invoke, after = (receipt['sourceGuards'][key] for key in ['before', 'invoke', 'after'])
    trace.require(trace.json_equal(before, invoke) and trace.json_equal(before, after) and
                  before['sourceCommit'] == before['observedHead'] == receipt['sourceCommit'] == source and
                  before['sourceSha256'] == expected_sources, 'original fixed source guards')
    trace.require(trace.json_equal(trace.strict_json((base / 'config.json').read_bytes()), connection.http_config_for(base)) and
                  (base / 'version.stdout').read_text().strip() == contract['codexVersion'], 'original effective configuration')
    reservation = trace.strict_json((base / 'reservation.json').read_bytes())
    shared = ledger.common_ledger_path(ROOT).parent / 'production-provider-diagnostic-ledger' / (Path(contract_path).stem + '.json')
    ledger.safe_tree(shared)
    shared_raw = shared.read_bytes()
    trace.require(reservation['path'] == str(shared) and sha(shared_raw) == reservation['sha256'] and
                  trace.json_equal(trace.strict_json(shared_raw), {k: v for k, v in reservation.items() if k not in {'path', 'sha256'}}) and
                  reservation['contractPath'] == contract_path and reservation['sourceCommit'] == source and
                  reservation['contractSha256'] == sha(contract_raw) and reservation['automaticRetry'] is False and
                  reservation['consumedReservations'] == reservation['maximumInvocations'] == 1, 'original common reservation')
    sent = [trace.strict_json(line) for line in (base / 'rpc-in.jsonl').read_bytes().splitlines()]
    frames = [trace.strict_json(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    selected = []
    for line in (base / 'runtime-stderr.bin').read_bytes().splitlines(keepends=True):
        try:
            event = trace.strict_json(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(event, dict) and event.get('target') in {'codex_otel.trace_safe', 'codex_code_mode::timing'}:
            selected.append(line)
    trace.require(b''.join(selected) == (base / 'trace-safe.jsonl').read_bytes(), 'complete original telemetry projection')
    api = [e['fields'] for line in selected if (e := trace.strict_json(line)).get('fields', {}).get('event.name') == 'codex.api_request']
    result = connection.evaluate_service_capture(sent, frames, api, trace.strict_json((base / 'runtime-result.json').read_bytes()),
                                                 expected_cwd=str(base / 'work'))
    bundles = list((base / 'rollout-traces').glob('*/manifest.json'))
    trace.require(len(bundles) == 1, 'one original rollout bundle')
    bundle = bundles[0].parent
    native_usage = [f['params']['tokenUsage']['last'] for f in frames if f.get('method') == 'thread/tokenUsage/updated']
    trace.require(len(native_usage) == 1, 'one native token usage')
    rollout = rollout_values((bundle / 'manifest.json').read_bytes(), (bundle / 'trace.jsonl').read_bytes(),
        {str(p.relative_to(bundle)): p.read_bytes() for p in (bundle / 'payloads').glob('*.json')},
        thread=result['threadId'], turn=result['turnId'], native_usage=native_usage[0])
    trace.require(receipt['status'] == 'connection_diagnostic_captured' and receipt['namespaceExitCode'] == 0 and
                  receipt['timedOut'] is False and receipt['sdkErrorType'] is None and
                  trace.strict_json((base / 'isolated-result.json').read_bytes())['sdkErrorType'] is None, 'original capture outcome')
    return {**{k: v for k, v in result.items() if k not in {'threadId', 'turnId'}}, **rollout,
            'artifactCount': len(paths), 'sourceCommit': source, 'primaryModelTrajectories': 0,
            'certifiesWholeTrace': False, 'certifiesPhaseCompletion': False}
