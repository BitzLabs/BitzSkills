"""一次カナリアの原通知・host・最終応答の相関。独立採点・台帳確定は別工程。"""
from __future__ import annotations

import production_canary_evidence as evidence
import production_canary_trace as canary
import production_sdk_trace as sdk
import production_trace as trace

require = trace.require


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


def verify_native(capture):
    """既に原bytesを束縛したcontextだけを専用SDK/native検査へ渡す。"""
    require(isinstance(capture, evidence.VerifiedCapture), 'verified capture context required')
    originals, fixed = capture.originals, capture.fixed
    sent, received = json_lines(originals['rpc-in.jsonl']), json_lines(originals['rpc-out.jsonl'])
    require({name: evidence.ledger.sha(raw) for name, raw in originals.items()} ==
            capture.result['artifactSha256'], 'consumed original artifact binding drift')
    schema = trace.strict_json(fixed.decision_schema_raw)
    sdk.requests(sent, profile='public-canary', output_schema=schema)
    projected, raw = raw_projection(sent, received)
    events = sdk.complete_trace_projection(originals['runtime-stderr.bin'], originals['trace-safe.jsonl'])
    direct = tuple(e['fields'].get('tool_name') for e in events
        if e['fields'].get('event.name') == 'codex.tool_call_received' and e['fields'].get('tool_source') == 'direct')
    profiles = [name for name, value in canary.PROFILES.items() if value == direct]
    require(len(profiles) == 1, 'closed primary parent profile')
    host = json_lines(originals.get('host.jsonl', b''), empty=True)
    result = canary.audit(fixed.bound.raw_inputs[2], host, sent, projected, trace.strict_json(fixed.bound.raw_inputs[1]),
        raw_stderr=originals['runtime-stderr.bin'], selected_log=originals['trace-safe.jsonl'],
        profile=profiles[0], expected_input=originals['model-input.json'],
        base_instructions=evidence.capture.BASE, developer_instructions=evidence.capture.DEVELOPER,
        cwd=str(capture.base / 'work'), actual_exit_code=0, sdk_profile='public-canary', output_schema=schema)
    trace.jsonschema.Draft202012Validator(schema).validate(result['decision'])
    return dict(status='primary_native_and_host_correlated', artifactBinding=capture.result, native=result,
        rawNotificationsValueSha256=sdk.digest(raw), rawNotificationCount=len(raw),
        rawPayloadCorrelationVerified=False, eligibleForMeasurement=False,
        certifiesProviderWireBodies=False, certifiesBehavior=False, certifiesSkillGate=False,
        independentReviewPerformed=False, ledgerFinalized=False)


def verify_complete(capture):
    """原取得・native・固定client context・rollout/raw/usageを接続する。"""
    import production_canary_rollout as rollout
    result = verify_native(capture)
    require(evidence.ledger.sha(capture.fixed.context_profile_raw) == capture.fixed.bound.contract['contextProfileSha256'],
            'consumed fixed context profile drift')
    originals = capture.originals
    groups = {name.split('/')[1] for name in originals if name.startswith('rollout-traces/')}
    require(len(groups) == 1, 'one verified original rollout group')
    prefix = 'rollout-traces/' + next(iter(groups)) + '/'
    payloads = {name.removeprefix(prefix):raw for name,raw in originals.items() if name.startswith(prefix+'payloads/')}
    correlated = rollout.correlate(originals[prefix+'manifest.json'], originals[prefix+'trace.jsonl'], payloads,
        json_lines(originals['rpc-in.jsonl']), json_lines(originals['rpc-out.jsonl']), result['native'],
        trace.strict_json(capture.fixed.context_profile_raw))
    return dict(result, status='primary_original_capture_correlated', rollout=correlated,
        rawPayloadCorrelationVerified=True, eligibleForMeasurement=False,
        independentReviewPerformed=False, ledgerFinalized=False)
