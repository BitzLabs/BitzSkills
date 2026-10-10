"""原traceとHTTP要求のJSON値を比較する。wire bytes・実provider・適格性は認定しない。"""
from __future__ import annotations

import hashlib
import re
import production_trace as trace

require = trace.require


def compare_requests(manifest_raw, events_raw, payloads, wire_requests, *, thread_id, turn_id,
                     model, provider_name):
    """callerが原artifactのhashを照合した後に使う、要求投影だけの限定比較。"""
    manifest = trace.strict_json(manifest_raw)
    require(type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1 and
            manifest.get('root_thread_id') == thread_id and manifest.get('raw_event_log') == 'trace.jsonl' and
            manifest.get('payloads_dir') == 'payloads', 'rollout manifest context')
    require(all(isinstance(v, str) and bool(v) for v in [thread_id, turn_id, model, provider_name]),
            'fixed inference context')
    require(isinstance(payloads, dict) and all(isinstance(k, str) and
            re.fullmatch(r'payloads/[1-9][0-9]*\.json', k) and isinstance(v, bytes)
            for k, v in payloads.items()), 'bounded payload inventory')
    require(isinstance(wire_requests, list) and 1 <= len(wire_requests) <= 3 and
            all(isinstance(v, bytes) for v in wire_requests), 'bounded original requests')
    events = [trace.strict_json(line) for line in events_raw.splitlines()]
    require(bool(events), 'original rollout events missing')
    seen, active, matched, ended = set(), None, [], False
    for ordinal, event in enumerate(events, 1):
        require(isinstance(event, dict) and type(event.get('schema_version')) is int and
                event['schema_version'] == 1 and type(event.get('seq')) is int and event['seq'] == ordinal and
                event.get('rollout_id') == manifest.get('rollout_id') and
                isinstance(event.get('payload'), dict), 'original event sequence or context')
        fields = event['payload']
        kind = fields.get('type')
        if kind == 'codex_turn_ended':
            require(not ended and active is None and fields.get('codex_turn_id') == turn_id and
                    fields.get('status') == 'completed', 'inference turn terminal')
            ended = True
        if isinstance(kind, str) and kind.startswith('inference_'):
            require(not ended and event.get('thread_id') == thread_id and event.get('codex_turn_id') == turn_id,
                    'inference outside original turn')
            require(kind in {'inference_started', 'inference_completed'}, 'failed or unknown inference event')
            ident = fields.get('inference_call_id')
            require(isinstance(ident, str) and bool(ident), 'inference identity')
            if kind == 'inference_started':
                require(active is None and ident not in seen and len(matched) < len(wire_requests) and
                        fields.get('thread_id') == thread_id and fields.get('codex_turn_id') == turn_id and
                        fields.get('model') == model and fields.get('provider_name') == provider_name,
                        'inference start binding')
                ref = fields.get('request_payload')
                require(isinstance(ref, dict) and ref.get('kind') == {'type': 'inference_request'} and
                        isinstance(ref.get('path'), str) and ref['path'] in payloads,
                        'inference request reference missing')
                captured = trace.strict_json(payloads[ref['path']])
                original = trace.strict_json(wire_requests[len(matched)])
                require(isinstance(captured, dict) and captured.get('model') == model and
                        isinstance(captured.get('input'), list) and bool(captured['input']) and
                        trace.json_equal(captured, original), 'inference request JSON value drift')
                active = ident
                seen.add(ident)
                matched.append(dict(inferenceCallId=ident, payloadPath=ref['path'],
                    payloadSha256=hashlib.sha256(payloads[ref['path']]).hexdigest(),
                    wireRequestSha256=hashlib.sha256(wire_requests[len(matched)]).hexdigest(),
                    inputItems=len(captured['input'])))
            else:
                require(active == ident, 'inference completion identity')
                active = None
    require(ended and active is None and len(matched) == len(wire_requests), 'incomplete inference projection')
    return dict(status='original_inference_request_values_matched', requests=len(matched), matches=matched,
                certifiesProviderWireBodies=False, certifiesResponseProjection=False,
                certifiesWholeTrace=False, eligibleForMeasurement=False, certifiesSkillGate=False)
