"""製品発火評価の入力投影とapp-server証拠監査。モデル起動・期待値採点は行わない。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import jsonschema

HOST_SPEC = importlib.util.spec_from_file_location('production_trace_readonly_host', Path(__file__).with_name('host.py'))
HOST = importlib.util.module_from_spec(HOST_SPEC)
HOST_SPEC.loader.exec_module(HOST)
SKILLS = HOST.SKILLS
resource_path = HOST.resource_path

ROOT = Path(__file__).resolve().parents[3]
SERVER = 'production-routing'
PATHS = {'bitz-core': 'operate', 'sdd-plan': 'plan', 'sdd-implement': 'implement',
         'sdd-converge': 'converge', 'quality-plan': 'plan', 'quality-review': 'review'}
NEUTRAL = {'thread/tokenUsage/updated', 'thread/status/changed'}
INCREMENTS = {
    'item/agentMessage/delta': ('agentMessage', None, True),
    'item/reasoning/textDelta': ('reasoning', 'contentIndex', True),
    'item/reasoning/summaryTextDelta': ('reasoning', 'summaryIndex', True),
    'item/reasoning/summaryPartAdded': ('reasoning', 'summaryIndex', False),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def strict_json(raw: bytes | str):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result

    def bad_constant(_):
        raise ValueError('non-finite JSON value')

    return json.loads(raw.decode('utf-8') if isinstance(raw, bytes) else raw,
                      object_pairs_hook=pairs, parse_constant=bad_constant)


def json_equal(left, right) -> bool:
    """JSONの型と配列順序を保って照合する。objectのキー順序は証拠差としない。"""
    def encoded(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return encoded(left) == encoded(right)


def reasoning_bodies(item: dict) -> dict:
    """SDK0.160.1の省略/nullまたは文字列配列を保ち、原アイテムと状態を共有しない。"""
    values = {name: item.get(name) for name in ('content', 'summary')}
    require(all(v is None or isinstance(v, list) and all(isinstance(s, str) for s in v)
                for v in values.values()), 'native reasoning body fields')
    return {name: list(value) if value is not None else None for name, value in values.items()}


def check_turn_start(value: dict):
    """固定診断の開始turnだけを検査し、状態がない合成値で失敗証拠を補完しない。"""
    require(isinstance(value, dict) and {'id', 'status', 'items'} <= set(value) <= {
        'id', 'status', 'items', 'itemsView', 'error', 'startedAt', 'completedAt', 'durationMs'},
        'native turn start fields')
    require(isinstance(value['id'], str) and bool(value['id']) and value['status'] == 'inProgress' and
            value['items'] == [] and value.get('itemsView', 'notLoaded') == 'notLoaded' and
            value.get('error') is None and value.get('completedAt') is None and value.get('durationMs') is None,
            'native turn start state')
    require(value.get('startedAt') is None or type(value['startedAt']) is int and value['startedAt'] >= 0,
            'native turn start timestamp')


def project_case(case: dict) -> dict:
    """caseId/expected/category/control等を列挙せず、要求と文字列contextだけを投影する。"""
    require(isinstance(case, dict), 'case object required')
    prompt, context = case.get('prompt'), case.get('context')
    require(isinstance(prompt, str) and bool(prompt.strip()), 'prompt required')
    require(isinstance(context, list) and all(isinstance(v, str) for v in context), 'string context required')
    return {'prompt': prompt, 'context': list(context)}


def manifest_view(raw: bytes) -> tuple[dict, str, dict]:
    manifest = strict_json(raw)
    require(isinstance(manifest, dict), 'manifest object required')
    require(manifest.get('schemaVersion') == '1.0' and manifest.get('scope') == 'production-resource-snapshot-only', 'manifest schema or scope')
    require(re.fullmatch(r'[0-9a-f]{40}', manifest.get('sourceCommit', '')) is not None, 'candidate ref required')
    skills, resources = manifest.get('skills'), manifest.get('resources')
    require(isinstance(skills, list) and len(skills) == 6, 'six skills required')
    require(all(isinstance(s, dict) for s in skills) and {s.get('name') for s in skills} == SKILLS, 'skill inventory')
    require(isinstance(resources, dict) and bool(resources), 'resource inventory')
    for name, digest in resources.items():
        resource_path(name)
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest) is not None, 'resource digest')
    for skill in skills:
        require(skill.get('path') in resources and skill['path'].endswith('/skills/' + skill['name'] + '/SKILL.md'), 'skill path')
        require(isinstance(skill.get('description'), str) and bool(skill['description'].strip()), 'skill description')
        require(isinstance(skill.get('version'), str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', skill['version']) is not None, 'skill version')
    digest = hashlib.sha256(raw).hexdigest()
    view = {'skills': [{k: s[k] for k in ['name', 'description', 'version', 'path']} for s in skills],
            'resources': sorted(resources), 'sourceCommit': manifest['sourceCommit'],
            'candidateVersion': manifest['candidateVersion'], 'manifestSha256': digest}
    return manifest, digest, view


def audit_host(manifest: dict, view: dict, events: list) -> set[str]:
    read = set()
    listed = False
    require(isinstance(events, list), 'host log required')
    for sequence, event in enumerate(events, 1):
        require(isinstance(event, dict) and set(event) == {'sequence', 'tool', 'arguments', 'accepted', 'result'}, 'host event fields')
        require(type(event['sequence']) is int and event['sequence'] == sequence, 'host sequence')
        require(event['accepted'] is True, 'host rejected call')
        tool, args, result = event['tool'], event['arguments'], event['result']
        if tool == 'list_resources':
            require(args == {} and isinstance(args, dict) and json_equal(result, view), 'host discovery mismatch')
            listed = True
        elif tool == 'read_resource':
            require(listed and isinstance(args, dict) and set(args) == {'path'}, 'host read arguments')
            path = args['path']
            require(isinstance(path, str) and path in manifest['resources'], 'unlisted resource')
            require(isinstance(result, dict) and set(result) == {'path', 'content', 'sha256', 'sourceCommit'}, 'host read result')
            require(result['path'] == path and result['sourceCommit'] == manifest['sourceCommit'], 'host resource binding')
            require(isinstance(result['content'], str), 'resource content required')
            digest = hashlib.sha256(result['content'].encode('utf-8')).hexdigest()
            require(result['sha256'] == manifest['resources'][path] == digest, 'resource bytes mismatch')
            read.add(path)
        else:
            raise ValueError('host tool not allowed')
    return read


def completed_items(frames: list) -> list:
    """CLI0.160.1のapp-server通知形式を扱う。未知の形式を黙って除外しない。"""
    require(isinstance(frames, list), 'native frames required')
    thread = turn = None
    finished = False
    final_started = False
    final_completed = False
    responses = {}
    started = {}
    completed = set()
    bodies, streamed = {}, {}
    items = []
    for frame in frames:
        require(isinstance(frame, dict) and 'error' not in frame, 'native error frame')
        if 'method' not in frame:
            require(set(frame) == {'id', 'result'} and type(frame['id']) is int and frame['id'] in {1, 2, 3}, 'native response fields')
            require(frame['id'] not in responses and isinstance(frame['result'], dict), 'native response repeated')
            responses[frame['id']] = frame['result']
            if frame['id'] == 3:
                require(set(frame['result']) == {'turn'}, 'native turn response fields')
                check_turn_start(frame['result']['turn'])
            continue
        method, params = frame['method'], frame.get('params')
        require(set(frame) == {'method', 'params'}, 'native notification fields')
        require(isinstance(params, dict), 'native notification params')
        if method == 'thread/started':
            require(thread is None and turn is None, 'multiple native threads')
            thread = params['thread']['id']
            require(isinstance(thread, str) and bool(thread), 'thread id required')
            require(('threadId' not in params or params['threadId'] == thread) and 'turnId' not in params,
                    'native thread start outer context mismatch')
            continue
        require(thread is not None and params.get('threadId') == thread, 'native thread mismatch')
        if method == 'turn/started':
            require(turn is None and not finished, 'multiple native turns')
            check_turn_start(params.get('turn'))
            turn = params['turn']['id']
            require(isinstance(turn, str) and bool(turn), 'turn id required')
            require('turnId' not in params or params['turnId'] == turn, 'native turn start outer context mismatch')
            continue
        if 'turnId' in params:
            require(turn is not None and params['turnId'] == turn, 'native outer turn mismatch')
        if method in INCREMENTS:
            require(turn is not None and not finished, 'native increment outside turn')
            kind, index_key, has_delta = INCREMENTS[method]
            fields = {'threadId', 'turnId', 'itemId'} | ({index_key} if index_key else set()) | ({'delta'} if has_delta else set())
            require(set(params) == fields, 'native increment fields')
            ident = params['itemId']
            require(isinstance(ident, str) and bool(ident) and ident in started and ident not in completed and
                    started[ident][0] == kind, 'native increment outside active item')
            require(not has_delta or isinstance(params['delta'], str), 'native increment text')
            if index_key:
                require(type(params[index_key]) is int and params[index_key] >= 0, 'native increment index')
            if kind == 'agentMessage':
                bodies[ident]['text'] += params['delta']
                streamed[ident].add('text')
            else:
                field = 'content' if index_key == 'contentIndex' else 'summary'
                values, index = bodies[ident][field], params[index_key]
                require(isinstance(values, list), 'native reasoning start body unavailable')
                if not has_delta:
                    require(index == len(values), 'native reasoning index lifecycle')
                    values.append('')
                else:
                    if field == 'content' and index == len(values):
                        values.append('')
                    require(index < len(values), 'native reasoning index lifecycle')
                    values[index] += params['delta']
                streamed[ident].add(field)
            continue
        if method in NEUTRAL:
            if 'turnId' in params:
                require(turn is not None and params['turnId'] == turn, 'neutral turn mismatch')
            continue
        require(turn is not None and not finished, 'native event outside turn')
        if method == 'turn/completed':
            terminal = params['turn']
            require(terminal['id'] == turn and terminal['status'] == 'completed' and terminal.get('error') is None, 'native turn failed')
            finished = True
            continue
        require(method in {'item/started', 'item/completed'} and params.get('turnId') == turn, 'native action not allowed')
        item = params['item']
        require(isinstance(item, dict) and item.get('type') in {'mcpToolCall', 'agentMessage', 'reasoning'}, 'forbidden native item')
        ident = item.get('id')
        require(isinstance(ident, str) and bool(ident), 'item id required')
        if item['type'] == 'mcpToolCall':
            require(not final_started, 'tool after final response started')
        if item['type'] == 'agentMessage':
            require(isinstance(item.get('text'), str), 'native message text required')
            require(item.get('phase') in {'commentary', 'final_answer'}, 'explicit message phase required')
            if item['phase'] == 'commentary':
                require(not final_started, 'commentary after final response started')
        if item['type'] == 'reasoning':
            reasoning = reasoning_bodies(item)
        if method == 'item/started':
            require(ident not in started and ident not in completed, 'item start repeated')
            if item['type'] == 'agentMessage' and item['phase'] == 'final_answer':
                require(not final_started, 'multiple final responses')
                require(all(i in completed for i, binding in started.items() if binding[0] == 'mcpToolCall'), 'tool incomplete before final response')
                final_started = True
            if item['type'] == 'mcpToolCall':
                require(item.get('status') == 'inProgress' and item.get('result') is None and item.get('error') is None, 'native tool start state')
            elif item['type'] in {'reasoning', 'agentMessage'}:
                bodies[ident] = reasoning if item['type'] == 'reasoning' else {'text': item['text']}
                streamed[ident] = {name for name, value in bodies[ident].items() if value}
            started[ident] = (item['type'], item.get('server'), item.get('tool'), item.get('arguments'), item.get('phase'))
        else:
            require(ident in started and ident not in completed, 'item completion without unique start')
            require(json_equal(started[ident], (item['type'], item.get('server'), item.get('tool'), item.get('arguments'), item.get('phase'))), 'item binding drift')
            if item['type'] in {'reasoning', 'agentMessage'}:
                final_body = reasoning if item['type'] == 'reasoning' else {'text': item['text']}
                require(all(json_equal(final_body[name], bodies[ident][name]) for name in streamed[ident]),
                        'native streamed body mismatch')
            if item['type'] == 'agentMessage' and item['phase'] == 'final_answer':
                require(final_started and not final_completed, 'multiple final response completions')
                final_completed = True
            completed.add(ident)
            items.append(item)
    require(finished and final_completed and set(started) == completed and set(responses) == {1, 2, 3}, 'native terminal missing')
    require(responses[2].get('thread', {}).get('id') == thread and responses[3].get('turn', {}).get('id') == turn, 'native response binding')
    return items


def audit_calls(host_events: list, items: list) -> None:
    """host一次結果と完了済みnative MCP結果を照合する共通処理。"""
    calls = [item for item in items if item['type'] == 'mcpToolCall']
    require(len(calls) == len(host_events), 'host/native count mismatch')
    for item, event in zip(calls, host_events):
        require(item.get('server') == SERVER and item.get('tool') == event['tool'], 'native tool mismatch')
        require(item.get('status') == 'completed' and item.get('error') is None, 'native tool failed')
        require(json_equal(item.get('arguments'), event['arguments']), 'native arguments mismatch')
        result = item.get('result')
        require(isinstance(result, dict) and set(result) <= {'content', 'structuredContent', '_meta'}, 'native tool result fields')
        content = result.get('content')
        require(isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and set(content[0]) == {'type', 'text'} and content[0]['type'] == 'text', 'native tool content')
        require(isinstance(content[0]['text'], str), 'native tool text required')
        require(json_equal(strict_json(content[0]['text']), event['result']), 'host/native result mismatch')
        require((result.get('structuredContent') is None or json_equal(result['structuredContent'], event['result'])) and
                result.get('_meta') in (None, {}), 'native extra result')


def audit(manifest_raw: bytes, host_events: list, frames: list, decision: dict,
          event_catalog: dict, *, actual_exit_code: int) -> dict:
    require(type(actual_exit_code) is int and actual_exit_code == 0, 'native process failed')
    manifest, manifest_digest, view = manifest_view(manifest_raw)
    read = audit_host(manifest, view, host_events)
    items = completed_items(frames)
    audit_calls(host_events, items)
    messages = [item for item in items if item['type'] == 'agentMessage' and item['phase'] == 'final_answer']
    require(len(messages) == 1 and json_equal(strict_json(messages[0]['text']), decision), 'final response mismatch')
    schema = copy.deepcopy(strict_json((ROOT / 'evals/skills/schemas/decision.schema.json').read_bytes()))
    schema['properties']['selectedEntry']['enum'] = [None, *sorted(SKILLS)]
    jsonschema.Draft202012Validator(schema).validate(decision)
    selected = decision['selectedEntry']
    require(decision['selectedPath'] == (PATHS[selected] if selected else None), 'selected path mismatch')
    catalog = event_catalog.get('events')
    require(isinstance(catalog, list) and all(isinstance(v, str) for v in catalog) and len(set(catalog)) == len(catalog), 'event catalog required')
    require(set(decision['events'] + decision['rejectedEvents']) <= set(catalog), 'unknown decision event')
    if selected:
        path = next(s['path'] for s in manifest['skills'] if s['name'] == selected)
        require(path in read, 'selected skill not read')
    return {'status': 'measurement_integrity_passed', 'selectedSkillBodyRead': selected is not None,
            'hostCalls': len(host_events), 'candidateManifestSha256': manifest_digest,
            'certifiesExpectedDecision': False, 'certifiesBehavior': False, 'certifiesSkillGate': False}
