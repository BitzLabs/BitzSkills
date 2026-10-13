"""固定RPC/Host/native/rolloutの原bytes検査。台帳予約とモデル起動は行わない。"""
import math
import production_canary_capture as capture
import production_canary_trace as canary
import production_canary_rollout as rollout
import production_sdk_trace as sdk
import production_trace as trace
import production_ledger as io
require=trace.require

def json_lines(raw, *, empty=False):
    require(isinstance(raw, bytes), 'original JSONL bytes')
    values = [trace.strict_json(line) for line in raw.splitlines()]
    require((bool(values) or empty) and all(isinstance(value, dict) for value in values), 'original JSONL objects')
    return values

def raw_projection(sent, received):
    """原raw通知を保持し、native検査向け投影を明示する。原payload照合は後続で必須。"""
    bindings, _ = sdk.requests(sent, profile='public-canary', output_schema=sent[3]['params']['outputSchema'])
    replies = {bindings[f['id']]: f['result'] for f in received if 'id' in f and f['id'] in bindings}
    require(2 in replies and 3 in replies, 'raw original context replies')
    thread, turn = replies[2]['thread']['id'], replies[3]['turn']['id']
    starts = [i for i, f in enumerate(received) if f.get('method') == 'turn/started']
    ends = [i for i, f in enumerate(received) if f.get('method') == 'turn/completed']
    require(len(starts) == len(ends) == 1 and starts[0] < ends[0], 'raw native turn lifecycle')
    raw, projected = [], []
    for index, frame in enumerate(received):
        if frame.get('method') not in sdk.RAW_METHODS:
            projected.append(frame)
            continue
        require(set(frame) in ({'method', 'params'}, {'method', 'params', 'emittedAtMs'}) and
                isinstance(frame.get('params'), dict) and starts[0] < index < ends[0], 'raw notification envelope and order')
        if 'emittedAtMs' in frame:
            require(type(frame['emittedAtMs']) is int and frame['emittedAtMs'] >= 0, 'raw notification timestamp')
        params = frame['params']
        expected = {'threadId', 'turnId', 'item'} if frame['method'] == sdk.RAW_METHODS[0] else {
            'threadId', 'turnId', 'responseId', 'usage', 'usageMetadata'}
        require(set(params) == expected and params['threadId'] == thread and params['turnId'] == turn,
                'raw notification fields and context')
        raw.append(frame)
    require(bool(raw), 'primary raw notifications missing')
    return projected, raw

def native(originals, manifest_raw, catalog_raw, schema_raw, *, cwd):
    sent,received=json_lines(originals['rpc-in.jsonl']),json_lines(originals['rpc-out.jsonl'])
    schema=trace.strict_json(schema_raw)
    wire_schema=capture.execution_schema(schema)
    sdk.requests(sent,profile='public-canary',output_schema=wire_schema)
    projected,raw=raw_projection(sent,received)
    events=sdk.complete_trace_projection(originals['runtime-stderr.bin'],originals['trace-safe.jsonl'])
    direct=tuple(e['fields'].get('tool_name') for e in events if e['fields'].get('event.name')=='codex.tool_call_received' and e['fields'].get('tool_source')=='direct')
    profiles=[name for name,value in canary.PROFILES.items() if value==direct]
    require(len(profiles)==1,'closed primary parent profile')
    host=json_lines(originals.get('host.jsonl',b''),empty=True)
    result=canary.audit(manifest_raw,host,sent,projected,trace.strict_json(catalog_raw),
        raw_stderr=originals['runtime-stderr.bin'],selected_log=originals['trace-safe.jsonl'],profile=profiles[0],
        expected_input=originals['model-input.json'],base_instructions=capture.BASE,developer_instructions=capture.DEVELOPER,
        cwd=cwd,actual_exit_code=0,sdk_profile='public-canary',output_schema=wire_schema)
    trace.jsonschema.Draft202012Validator(schema).validate(result['decision'])
    return dict(native=result,rawNotificationsValueSha256=sdk.digest(raw),rawNotificationCount=len(raw))


def correlate_rollout(originals,native_result,context_profile_raw,receipt_raw,receipt_sha256,seconds):
    require(io.sha(receipt_raw)==io.pin(receipt_sha256),'consumed elapsed receipt hash drift')
    require(trace.json_equal(seconds,trace.strict_json(receipt_raw).get('elapsedSeconds')),'consumed elapsed receipt value drift')
    require(type(seconds) in {int,float} and seconds>=0 and (type(seconds) is int or math.isfinite(seconds)),
            'captured elapsed time type')
    if type(seconds) is int:elapsed_ms=seconds*1000
    else:
        numerator,denominator=seconds.as_integer_ratio()
        elapsed_ms=(numerator*1000+denominator-1)//denominator
    groups={name.split('/')[1] for name in originals if name.startswith('rollout-traces/')}
    require(len(groups)==1,'one verified original rollout group')
    prefix='rollout-traces/'+next(iter(groups))+'/'
    payloads={name.removeprefix(prefix):raw for name,raw in originals.items() if name.startswith(prefix+'payloads/')}
    return rollout.correlate(originals[prefix+'manifest.json'],originals[prefix+'trace.jsonl'],payloads,
        json_lines(originals['rpc-in.jsonl']),json_lines(originals['rpc-out.jsonl']),native_result,
        trace.strict_json(context_profile_raw),host_events=json_lines(originals.get('host.jsonl',b''),empty=True),capture_elapsed_ms=elapsed_ms)
