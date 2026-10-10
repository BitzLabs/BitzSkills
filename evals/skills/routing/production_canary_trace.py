"""可変IDの限定SDK軌跡を検査する。provider wire未取得層と測定適格性を認定しない。"""
from __future__ import annotations

import hashlib
import production_sdk_trace as sdk
import production_trace as trace

require = trace.require
PROFILES = {'no-exec': (), 'single-exec': ('exec',), 'two-exec': ('exec', 'exec'),
            'exec-wait': ('exec', 'wait')}
NEUTRAL = {'codex.conversation_starts', 'codex.startup_phase', 'codex.user_prompt',
           'codex.api_request', 'codex.turn_ttft'}


def audit(manifest_raw, host_events, sent, received, events, catalog, *, profile, expected_input,
          base_instructions, developer_instructions, cwd, actual_exit_code):
    """原RPC・host本文・全対象telemetryの相関。固定IDへの別名置換は行わない。"""
    require(isinstance(profile, str) and profile in PROFILES, 'bounded canary profile')
    require(isinstance(expected_input, bytes) and isinstance(base_instructions, str) and
            isinstance(developer_instructions, str) and isinstance(cwd, str) and bool(cwd), 'fixed canary inputs')
    _, params = sdk.requests(sent)
    expected_thread = dict(model='gpt-6.1-sol', modelProvider='openai', allowProviderModelFallback=False,
                           cwd=cwd, sandbox='read-only', approvalPolicy='never', ephemeral=True,
                           baseInstructions=base_instructions, developerInstructions=developer_instructions)
    require(trace.json_equal(params['thread'], expected_thread) and
            params['turn']['input'][0]['text'].encode() == expected_input, 'original SDK input drift')
    native = sdk.normalized(sent, received)
    items = trace.completed_items(native['frames'])
    finals = [item for item in items if item['type'] == 'agentMessage' and item['phase'] == 'final_answer']
    require(len(finals) == 1, 'one canary final required')
    decision = trace.strict_json(finals[0]['text'])
    integrity = trace.audit(manifest_raw, host_events, native['frames'], decision, catalog,
                            actual_exit_code=actual_exit_code)
    require(len(host_events) <= 2, 'bounded child count')
    tools = [event['tool'] for event in host_events]
    selected = decision['selectedEntry']
    require(tools == ['list_resources', 'read_resource'] if selected else tools in [[], ['list_resources']],
            'selected decision and actual read mismatch')
    require(isinstance(events, list) and bool(events), 'original telemetry required')
    context = next(frame['params'] for frame in received if frame.get('method') == 'turn/started')
    thread, turn = context['threadId'], context['turn']['id']
    direct, api_indices = [], []
    for index, event in enumerate(events):
        require(isinstance(event, dict) and event.get('level') == 'INFO' and
                event.get('target') in {'codex_otel.trace_safe', 'codex_code_mode::timing'} and
                isinstance(event.get('fields'), dict), 'canary telemetry format')
        fields = event['fields']
        name = fields.get('event.name')
        if name in NEUTRAL:
            require(event['target'] == 'codex_otel.trace_safe' and fields.get('conversation.id') == thread and
                    ('turn_id' not in fields or fields['turn_id'] == turn), 'canary telemetry context')
            if name == 'codex.api_request':
                require(fields.get('auth.header_attached') is True and type(fields.get('attempt')) is int and
                        fields['attempt'] == 0 and type(fields.get('http.response.status_code')) is int and
                        fields['http.response.status_code'] == 200, 'canary API evidence')
                api_indices.append(index)
        elif name == 'codex.tool_call_received' and fields.get('tool_source') == 'direct':
            require(isinstance(fields.get('call_id'), str) and bool(fields['call_id']), 'canary parent ID')
            direct.append((index, fields['call_id'], fields.get('tool_name')))
    require(tuple(value[2] for value in direct) == PROFILES[profile] and
            len({value[1] for value in direct}) == len(direct), 'canary parent profile drift')
    require(len(api_indices) == len(direct) + 1, 'canary API count')
    if profile == 'no-exec':
        require(not host_events and all(event['target'] == 'codex_otel.trace_safe' and
                event['fields']['event.name'] in NEUTRAL for event in events), 'unexpected negative operation')
        parent_links = None
    else:
        require(bool(host_events), 'exec without observed child is outside bounded profile')
        sdk._require_native_parent_context(received)
        parent_links = sdk._audit_parent_links(events, received, direct[0][1],
            wait_call_id=direct[1][1] if profile == 'exec-wait' else None,
            second_exec_call_id=direct[1][1] if profile == 'two-exec' else None,
            api_auth_attached=True, child_tools=tuple(tools))
        if len(direct) == 1:
            parent_ready = next(index for index, event in enumerate(events)
                if event['fields'].get('event.name') == 'codex.tool_result_ready' and
                event['fields'].get('call_id') == direct[0][1])
            require(api_indices[0] < direct[0][0] < parent_ready < api_indices[1], 'single exec API order')
    return dict(status='bounded_sdk_routing_trace_diagnostic_passed', profile=profile,
                parentCallIds=[value[1] for value in direct],
                nativeChildIds=[item['id'] for item in items if item['type'] == 'mcpToolCall'],
                hostCalls=len(host_events), apiRequests=len(api_indices), decision=decision,
                nativeEvidence={key: value for key, value in native.items() if key != 'frames'},
                parentLinks=parent_links, childIntegrity=integrity,
                traceValueSha256=sdk.digest(events), modelInputSha256=hashlib.sha256(expected_input).hexdigest(),
                sdkInputValueSha256=sdk.digest(params['turn']['input']),
                certifiesProviderWireBodies=False, certifiesRawPayloads=False,
                eligibleForMeasurement=False, certifiesBehavior=False, certifiesSkillGate=False)
