"""Python SDK + 模擬ResponsesでCode Mode内部の実操作を診断する。外部通信なし。"""
from __future__ import annotations

import argparse
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import production_cli_probe as cli
import production_sdk_probe as sdk
import source_guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-operation-probe-v0.5.json'
CODE_FILES = ['production_operation_probe.py', 'production_sdk_probe.py', 'production_cli_probe.py', 'host.py', 'source_guard.py']
SCENARIOS = ('inventory', 'read', 'yielded-read', 'path-denied', 'shell-denied', 'patch-denied', 'web-denied', 'agent-denied', 'user-input-stop')


def raw_events_enabled(contract: dict) -> bool:
    if 'experimentalRawEvents' not in contract:
        return False
    profile = {'production-operation-probe-0.7.0': ('read', 2),
               'production-operation-probe-0.8.0': ('read', 2),
               'production-operation-probe-0.9.0': ('yielded-read', 3)}.get(contract['version'])
    if (contract['experimentalRawEvents'] is not True or profile is None or
            set(contract['outputLabels']) != {profile[0]} or type(contract['maximumScenarios']) is not int or
            contract['maximumScenarios'] != 1 or type(contract['maximumLocalHttpRequestsPerScenario']) is not int or
            contract['maximumLocalHttpRequestsPerScenario'] != profile[1] or type(contract['paidModelCalls']) is not int or
            contract['paidModelCalls'] != 0):
        raise ValueError('unknown raw event policy')
    return True


def thread_params(base: Path, contract: dict) -> dict:
    params = {'model': contract['model'], 'modelProvider': 'bitz_local_probe',
              'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
              'approvalPolicy': 'never', 'ephemeral': True, 'baseInstructions': 'Local operation diagnostic simulation.',
              'developerInstructions': 'LOCAL_SIMULATION_ONLY. No paid model or decision measurement.'}
    if raw_events_enabled(contract):
        # SDK生成型から除外されたexperimental字段は、SDKの公開dict入口でそのまま送る。
        params['experimentalRawEvents'] = True
    return params


def sdk_notification_record(notification) -> dict:
    """SDKが配送した値の側記録。原RPC bytesはproxyが別に保持する。"""
    payload = notification.payload
    params = payload.params if hasattr(payload, 'params') else payload.model_dump(mode='json', by_alias=True)
    if not isinstance(notification.method, str) or not notification.method or not isinstance(params, dict):
        raise ValueError('SDK notification record shape')
    return {'method': notification.method, 'params': copy.deepcopy(params)}


def notification_line(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def namespace(base: Path, contract: dict):
    # home/評価treeを隠して、今回必要なコード・固定資源だけを戻す。
    args = ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    for relative in [contract['sdkRelativePath'], contract['snapshotRelativePath']]:
        path = ROOT / relative
        args += ['--ro-bind', str(path), str(path)]
    for name in CODE_FILES:
        path = ROOT / 'evals/skills/routing' / name
        args += ['--ro-bind', str(path), str(path)]
    node_root = Path(contract['codexPath']).parents[1]
    args += ['--ro-bind', str(node_root), str(node_root), '--bind', str(base), str(base),
             '--chdir', str(base / 'work'), '--', '/usr/bin/python3', '-B', str(Path(__file__)), '--isolated', str(base)]
    return args


def program(scenario: str, base: Path) -> str:
    if scenario == 'inventory':
        return 'text(JSON.stringify({kind:"inventory",names:ALL_TOOLS.map(t=>t.name).sort()}));'
    discover = 'const find=s=>{const a=ALL_TOOLS.filter(t=>t.name.endsWith(s));if(a.length!==1)throw new Error("resource tool unavailable");return a[0].name;};'
    list_call = 'const listed=await tools[find("__list_resources")]({});const listing=JSON.parse(listed.content[0].text);'
    if scenario == 'read':
        return discover + list_call + 'const p=listing.skills.find(s=>s.name==="sdd-plan").path;const read=await tools[find("__read_resource")]({path:p});text(JSON.stringify({kind:"read",listed,read}));'
    if scenario == 'yielded-read':
        return (discover + list_call +
                'text(JSON.stringify({kind:"yielded-read",stage:"listed",listed}));await yield_control();'
                'await new Promise(resolve=>setTimeout(resolve,200));'
                'const p=listing.skills.find(s=>s.name==="sdd-plan").path;'
                'const read=await tools[find("__read_resource")]({path:p});'
                'text(JSON.stringify({kind:"yielded-read",stage:"read",read}));')
    if scenario == 'path-denied':
        return discover + 'const result=await tools[find("__read_resource")]({path:".spec/expected-canary.txt"});text(JSON.stringify({kind:"path-denied",result}));'
    targets = {'shell-denied': ('exec_command', {'cmd': 'pwd'}),
               'patch-denied': ('apply_patch', '*** Begin Patch\n*** Add File: ' + str(base / 'work/prohibited.txt') + '\n+LOCAL_SIMULATION_ONLY\n*** End Patch'),
               'web-denied': ('web__run', {'search_query': [{'q': 'LOCAL_SIMULATION_ONLY'}]}),
               'agent-denied': ('spawn_agent', {'message': 'LOCAL_SIMULATION_ONLY'})}
    if scenario not in targets:
        raise ValueError('unknown exec scenario')
    name, arguments = targets[scenario]
    # 成功も例外も原結果に残す。例外発生をOS拒否と自動的に同一視しない。
    return 'try{const result=await tools[' + json.dumps(name) + '](' + json.dumps(arguments) + \
        ');text(JSON.stringify({kind:' + json.dumps(scenario) + ',returned:true,result}));}catch(e){text(JSON.stringify({kind:' + \
        json.dumps(scenario) + ',returned:false,error:String(e)}));}'


def tool_reply(scenario: str, base: Path) -> bytes:
    if scenario == 'user-input-stop':
        item = {'type': 'function_call', 'call_id': 'probe-call', 'name': 'request_user_input_async',
                'namespace': 'functions', 'arguments': json.dumps({'questions': [
                    {'title': 'LOCAL_SIMULATION_ONLY', 'options': ['Local A', 'Local B']}]})}
    else:
        item = {'type': 'custom_tool_call', 'call_id': 'probe-call', 'name': 'exec', 'namespace': 'functions',
                'input': program(scenario, base)}
    return response_item(item)


def response_item(item: dict) -> bytes:
    events = [{'type': 'response.created', 'response': {'id': 'probe-response', 'status': 'in_progress', 'output': []}},
              {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
              {'type': 'response.completed', 'response': {'id': 'probe-response', 'status': 'completed', 'output': [item]}}]
    return ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()


def output_objects(request: dict, call_id: str = 'probe-call') -> list[dict]:
    objects = []
    for item in request.get('input', []):
        if item.get('type') not in {'custom_tool_call_output', 'function_call_output'} or item.get('call_id') != call_id:
            continue
        output = item.get('output')
        texts = [output] if isinstance(output, str) else [x.get('text', '') for x in output or [] if isinstance(x, dict)]
        for text in texts:
            for line in text.splitlines():
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and 'kind' in parsed:
                    objects.append(parsed)
    return objects


def yielded_output(request: dict, call_id: str) -> str:
    items = [i for i in request.get('input', []) if isinstance(i, dict) and
             i.get('type') in {'custom_tool_call_output', 'function_call_output'} and i.get('call_id') == call_id]
    if len(items) != 1:
        raise ValueError('one yielded call output required')
    output = items[0].get('output')
    if isinstance(output, str):
        return output
    if (not isinstance(output, list) or not output or
            not all(isinstance(i, dict) and i.get('type') == 'input_text' and isinstance(i.get('text'), str) for i in output)):
        raise ValueError('yielded output text required')
    return ''.join(i['text'] for i in output)


def yielded_cell_id(request: dict) -> str:
    match = re.match(r'\AScript running with cell ID ([^\s]+)\n', yielded_output(request, 'probe-call'))
    if match is None or match[1] != '1':
        raise ValueError('fixed first yielded cell required')
    return match[1]


def wait_reply(request: dict) -> bytes:
    return response_item({'type': 'function_call', 'call_id': 'probe-wait', 'name': 'wait', 'namespace': 'functions',
                          'arguments': json.dumps({'cell_id': yielded_cell_id(request), 'yield_time_ms': 10000, 'max_tokens': 10000})})


def yielded_observation(requests: list[dict], host_events: list[dict]) -> tuple[list[dict], dict]:
    """元の中断出力と継続の再掲を照合し、両段階の本文を原ホスト結果へ結ぶ。"""
    def strict_json(text):
        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise ValueError('duplicate yielded JSON key')
                result[key] = value
            return result

        def constant(_):
            raise ValueError('nonfinite yielded JSON')
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)

    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))

    if (not isinstance(requests, list) or len(requests) != 3 or
            not all(isinstance(r, dict) and isinstance(r.get('input'), list) for r in requests) or
            not isinstance(host_events, list) or len(host_events) != 2):
        raise ValueError('three yielded exchanges and two host results required')
    if canonical(requests[2]['input'][:-2]) != canonical(requests[1]['input']):
        raise ValueError('yielded provider history changed')
    cell = yielded_cell_id(requests[1])
    texts = [yielded_output(requests[1], 'probe-call'), yielded_output(requests[2], 'probe-wait')]
    if not texts[1].startswith('Script completed\n'):
        raise ValueError('yielded cell did not complete')
    objects = []
    for text, stage, key, tool, event in zip(texts, ('listed', 'read'), ('listed', 'read'),
                                          ('list_resources', 'read_resource'), host_events):
        payloads = [strict_json(line) for line in text.splitlines() if line.startswith('{')]
        if (len(payloads) != 1 or not isinstance(payloads[0], dict) or
                set(payloads[0]) != {'kind', 'stage', key} or payloads[0]['kind'] != 'yielded-read' or
                payloads[0]['stage'] != stage):
            raise ValueError('one complete yielded stage required')
        payload = payloads[0]
        wrapper = payload[key]
        if (not isinstance(wrapper, dict) or set(wrapper) != {'isError', 'content'} or
                wrapper['isError'] is not False or not isinstance(wrapper['content'], list) or
                len(wrapper['content']) != 1 or not isinstance(wrapper['content'][0], dict) or
                set(wrapper['content'][0]) != {'type', 'text'} or wrapper['content'][0]['type'] != 'text' or
                not isinstance(wrapper['content'][0]['text'], str) or not isinstance(event, dict) or
                event.get('tool') != tool or event.get('accepted') is not True or 'result' not in event):
            raise ValueError('yielded wrapper or host result required')
        if canonical(strict_json(wrapper['content'][0]['text'])) != canonical(event['result']):
            raise ValueError('yielded provider/host body mismatch')
        objects.append(payload)
    return objects, {'cellId': cell, 'waitCompleted': True, 'stages': ['listed', 'read']}


def terminal_matches(frames: list[dict], thread_id: str | None, turn_id: str | None) -> tuple[bool, bool]:
    """固定模擬応答の最終回答と完了を、SDK開始結果と配送順に照合する。"""
    if not isinstance(thread_id, str) or not thread_id or not isinstance(turn_id, str) or not turn_id:
        return False, False
    finals = [(i, f.get('params')) for i, f in enumerate(frames)
              if f.get('method') == 'item/completed' and isinstance(f.get('params'), dict) and
              isinstance(f['params'].get('item'), dict) and f['params']['item'].get('type') == 'agentMessage']
    completed = [(i, f.get('params')) for i, f in enumerate(frames) if f.get('method') == 'turn/completed']
    if len(finals) != 1 or len(completed) != 1:
        return False, False
    final_index, final = finals[0]
    completed_index, end = completed[0]
    if not isinstance(end, dict) or not isinstance(end.get('turn'), dict):
        return False, False
    turn = end['turn']
    matched = (final_index < completed_index and final.get('threadId') == thread_id and
               final.get('turnId') == turn_id and end.get('threadId') == thread_id and
               turn.get('id') == turn_id and turn.get('status') == 'completed' and
               turn.get('error') is None and final['item'].get('phase') == 'final_answer' and
               final['item'].get('text') == 'LOCAL_SIMULATION_ONLY')
    return matched, matched


def isolated(base: Path):
    contract = json.loads((base / 'contract.json').read_bytes())
    scenario = (base / 'scenario.txt').read_text()
    isolation_checks = {name: not (ROOT / name).exists() for name in ('.git', '.spec', 'tests', 'docs', 'evals/skills/results')}
    if not all(isolation_checks.values()):
        raise ValueError('evaluation tree visible in namespace')
    sys.path.insert(0, str(ROOT / contract['sdkRelativePath']))
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    if __version__ != contract['sdkVersion'] or sdk.tree_hash(ROOT / contract['sdkRelativePath']) != contract['sdkTreeSha256']:
        raise ValueError('SDK drift')
    version = subprocess.run([contract['codexPath'], '--version'], capture_output=True, timeout=10)
    cli.exclusive(base / 'version.stdout', version.stdout)
    cli.exclusive(base / 'version.stderr', version.stderr)
    if version.returncode or version.stdout.decode().strip() != contract['codexVersion']:
        raise ValueError('CLI drift')
    requests, errors, denials = [], [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            limit = contract['maximumLocalHttpRequestsPerScenario']
            if self.path != '/v1/responses' or len(requests) >= limit:
                errors.append('request limit or path')
                self.send_error(409)
                return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            cli.exclusive(base / f'request-{len(requests) + 1}.json', raw)
            request = json.loads(raw)
            requests.append(request)
            if (base / 'dialogue-stop.json').exists():
                self.send_error(409)
                return
            if request.get('model') != contract['model'] or cli.declared_tools(request) != sorted(contract['allowedSurfaceTools']):
                errors.append('model or surface inventory drift')
                self.send_error(409)
                return
            try:
                reply = (tool_reply(scenario, base) if len(requests) == 1 else
                         wait_reply(request) if scenario == 'yielded-read' and len(requests) == 2 else cli.simulation_reply())
            except ValueError as exc:
                errors.append(str(exc))
                self.send_error(409)
                return
            # 生成し直した応答を証拠として扱わず、送信直前の原bytesを保存する。
            cli.exclusive(base / f'response-{len(requests)}.sse', reply)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    def deny(method, params):
        denials.append({'method': method})
        raise ValueError('server request stops evaluation')

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = sdk.config_for(base, server.server_port, contract, 'sdk-minimal')
    config['mcp_servers.production-routing.default_tools_approval_mode'] = 'prompt'
    for tool in ('list_resources', 'read_resource'):
        config['mcp_servers.production-routing.tools.' + tool + '.approval_mode'] = 'approve'
    cli.exclusive(base / 'config.json', cli.encoded(config))
    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny)
    error_type = None
    thread_id = turn_id = None
    notifications = []
    try:
        client.start()
        client.initialize()
        thread = client.thread_start(thread_params(base, contract))
        thread_id = thread.thread.id
        turn = client.turn_start(thread_id, 'LOCAL_SIMULATION_ONLY')
        turn_id = turn.turn.id
        while True:
            notification = client.next_turn_notification(turn.turn.id)
            if raw_events_enabled(contract):
                notifications.append(sdk_notification_record(notification))
            if notification.method == 'turn/completed':
                break
    except Exception as exc:
        error_type = type(exc).__name__
    finally:
        client.close()
        server.shutdown()
        server.server_close()
    if raw_events_enabled(contract):
        cli.exclusive(base / 'sdk-turn-notifications.jsonl', b''.join(notification_line(n) for n in notifications))
    for _ in range(30):
        if (base / 'runtime-result.json').exists():
            break
        time.sleep(0.05)
    frames = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    host_path = base / 'host.jsonl'
    host_events = [json.loads(line) for line in host_path.read_bytes().splitlines()] if host_path.exists() else []
    limit = contract['maximumLocalHttpRequestsPerScenario']
    objects = output_objects(requests[-1]) if len(requests) == limit else []
    wait_observed = None
    if scenario == 'yielded-read':
        objects = []
        try:
            objects, wait_observed = yielded_observation(requests, host_events)
        except ValueError as exc:
            errors.append(str(exc))
    terminal, matched = terminal_matches(frames, thread_id, turn_id)
    value = {'status': 'operation_diagnostic_captured', 'scenario': scenario, 'localHttpRequestCount': len(requests),
             'outputObjects': objects, 'hostEventCount': len(host_events), 'serverRequestStops': denials,
             'mockTurnCompleted': terminal, 'mockFinalMatched': matched, 'sdkErrorType': error_type,
             'localErrors': errors, 'prohibitedFileExists': (base / 'work/prohibited.txt').exists(),
             'runtime': json.loads((base / 'runtime-result.json').read_bytes()) if (base / 'runtime-result.json').exists() else None,
             'isolationChecks': isolation_checks,
             'dialogueStoppedBeforeSdk': (base / 'dialogue-stop.json').exists(),
             'paidModelCalls': 0, 'certifiesNativeProvider': False, 'certifiesSkillGate': False}
    if scenario == 'yielded-read':
        value['yieldedCellObservation'] = wait_observed
    if raw_events_enabled(contract):
        value.update(experimentalRawEventsRequested=True,
                     rawResponseItemNotificationCount=sum(f.get('method') == 'rawResponseItem/completed' for f in frames),
                     sdkRawResponseItemNotificationCount=sum(f['method'] == 'rawResponseItem/completed' for f in notifications),
                     eligibleForMeasurement=False)
    # 捕捉と適合判定は分離する。内部一覧やtraceの未知形式を成功と推定しない。
    if errors or (scenario != 'user-input-stop' and (not terminal or not matched or error_type)):
        value['status'] = 'operation_diagnostic_stopped'
    cli.exclusive(base / 'isolated-result.json', cli.encoded(value))


def run(source: str, scenario: str, contract_name: str = CONTRACT):
    if contract_name not in {CONTRACT, 'evals/skills/routing/production-operation-probe-v0.6.json',
                             'evals/skills/routing/production-operation-probe-v0.7.json',
                             'evals/skills/routing/production-operation-probe-v0.8.json',
                             'evals/skills/routing/production-operation-probe-v0.9.json'}:
        raise ValueError('unknown operation contract')
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + contract_name))
    raw_events_enabled(contract)
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    if scenario not in SCENARIOS or scenario not in contract['outputLabels']:
        raise ValueError('unknown scenario')
    base = ROOT / '.venv' / contract['outputLabels'][scenario]
    if any(p.is_symlink() for p in [base, *base.parents]):
        raise ValueError('output symlink')
    raw = (ROOT / contract['snapshotRelativePath'] / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != contract['manifestSha256'] or json.loads(raw)['sourceCommit'] != contract['candidateSource']:
        raise ValueError('snapshot drift')
    if sdk.tree_hash(ROOT / contract['sdkRelativePath']) != contract['sdkTreeSha256']:
        raise ValueError('SDK drift')
    base.mkdir(mode=0o700)
    for name in ['work', 'tmp']:
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', cli.encoded(contract))
    cli.exclusive(base / 'scenario.txt', scenario.encode())
    env = {'PATH': '/home/hide/.nvm/versions/node/v26.5.0/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp')}
    if 'diagnosticTracing' in contract:
        tracing = contract['diagnosticTracing']
        if tracing != {'format': 'json', 'rustLog': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}:
            raise ValueError('unknown diagnostic tracing policy')
        env.update(LOG_FORMAT=tracing['format'], RUST_LOG=tracing['rustLog'])
    try:
        process = subprocess.run(namespace(base, contract), env=env, capture_output=True, timeout=45)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    cli.exclusive(base / 'namespace.stdout', stdout)
    cli.exclusive(base / 'namespace.stderr', stderr)
    after = source_guard.verify(ROOT, source, contract['sourceFiles'])
    result_path = base / 'isolated-result.json'
    value = json.loads(result_path.read_bytes()) if result_path.exists() else {'status': 'operation_diagnostic_unavailable'}
    value.update(sourceCommit=source, scenario=scenario, namespaceExitCode=code, paidModelCalls=0,
                 sourceGuards={'before': before, 'after': after},
                 artifactSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()})
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'outputObjects', 'sourceGuards', 'artifactSha256'}}))
    return 0 if code == 0 and value['status'] == 'operation_diagnostic_captured' else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--scenario', choices=SCENARIOS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--trace-parent', action='store_true')
    mode.add_argument('--raw-events', action='store_true')
    mode.add_argument('--yielded-cell', action='store_true')
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        return sdk.proxy(args.proxy, reject_questions=True)
    if args.isolated:
        isolated(args.isolated)
        return 0
    if not args.source or not args.scenario:
        parser.error('--source and --scenario required')
    contract_name = ('evals/skills/routing/production-operation-probe-v0.9.json' if args.yielded_cell else
                     'evals/skills/routing/production-operation-probe-v0.8.json' if args.raw_events else
                     'evals/skills/routing/production-operation-probe-v0.6.json' if args.trace_parent else CONTRACT)
    return run(args.source, args.scenario, contract_name)


if __name__ == '__main__':
    raise SystemExit(main())
