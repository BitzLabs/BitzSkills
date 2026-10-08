"""Python SDK + 模擬ResponsesでCode Mode内部の実操作を診断する。外部通信なし。"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
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
CONTRACT = 'evals/skills/routing/production-operation-probe-v0.2.json'
CODE_FILES = ['production_operation_probe.py', 'production_sdk_probe.py', 'production_cli_probe.py', 'host.py', 'source_guard.py']
SCENARIOS = ('inventory', 'read', 'path-denied', 'shell-denied', 'patch-denied', 'web-denied', 'agent-denied', 'user-input-stop')


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
                    {'id': 'local-question', 'header': 'Local', 'question': 'LOCAL_SIMULATION_ONLY',
                     'options': [{'label': 'Local A', 'description': 'Simulation'}, {'label': 'Local B', 'description': 'Simulation'}]}]})}
    else:
        item = {'type': 'custom_tool_call', 'call_id': 'probe-call', 'name': 'exec', 'namespace': 'functions',
                'input': program(scenario, base)}
    events = [{'type': 'response.created', 'response': {'id': 'probe-response', 'status': 'in_progress', 'output': []}},
              {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
              {'type': 'response.completed', 'response': {'id': 'probe-response', 'status': 'completed', 'output': [item]}}]
    return ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()


def output_objects(request: dict) -> list[dict]:
    objects = []
    for item in request.get('input', []):
        if item.get('type') not in {'custom_tool_call_output', 'function_call_output'} or item.get('call_id') != 'probe-call':
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


def isolated(base: Path):
    contract = json.loads((base / 'contract.json').read_bytes())
    scenario = (base / 'scenario.txt').read_text()
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
            if self.path != '/v1/responses' or len(requests) >= 2:
                errors.append('request limit or path')
                self.send_error(409)
                return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            cli.exclusive(base / f'request-{len(requests) + 1}.json', raw)
            request = json.loads(raw)
            requests.append(request)
            if request.get('model') != contract['model'] or cli.declared_tools(request) != sorted(contract['allowedSurfaceTools']):
                errors.append('model or surface inventory drift')
                self.send_error(409)
                return
            reply = tool_reply(scenario, base) if len(requests) == 1 else cli.simulation_reply()
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
    try:
        client.start()
        client.initialize()
        thread = client.thread_start({'model': contract['model'], 'modelProvider': 'bitz_local_probe',
            'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'ephemeral': True, 'baseInstructions': 'Local operation diagnostic simulation.',
            'developerInstructions': 'LOCAL_SIMULATION_ONLY. No paid model or decision measurement.'})
        turn = client.turn_start(thread.thread.id, 'LOCAL_SIMULATION_ONLY')
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed':
            pass
    except Exception as exc:
        error_type = type(exc).__name__
    finally:
        client.close()
        server.shutdown()
        server.server_close()
    for _ in range(30):
        if (base / 'runtime-result.json').exists():
            break
        time.sleep(0.05)
    frames = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    host_path = base / 'host.jsonl'
    host_events = [json.loads(line) for line in host_path.read_bytes().splitlines()] if host_path.exists() else []
    objects = output_objects(requests[-1]) if len(requests) == 2 else []
    finals = [f for f in frames if f.get('method') == 'item/completed' and f.get('params', {}).get('item', {}).get('type') == 'agentMessage']
    completed = [f for f in frames if f.get('method') == 'turn/completed']
    terminal = len(completed) == 1 and completed[0]['params']['turn']['status'] == 'completed'
    matched = len(finals) == 1 and finals[0]['params']['item'].get('phase') == 'final_answer' and \
        finals[0]['params']['item'].get('text') == 'LOCAL_SIMULATION_ONLY'
    value = {'status': 'operation_diagnostic_captured', 'scenario': scenario, 'localHttpRequestCount': len(requests),
             'outputObjects': objects, 'hostEventCount': len(host_events), 'serverRequestStops': denials,
             'mockTurnCompleted': terminal, 'mockFinalMatched': matched, 'sdkErrorType': error_type,
             'localErrors': errors, 'prohibitedFileExists': (base / 'work/prohibited.txt').exists(),
             'runtime': json.loads((base / 'runtime-result.json').read_bytes()) if (base / 'runtime-result.json').exists() else None,
             'paidModelCalls': 0, 'certifiesNativeProvider': False, 'certifiesSkillGate': False}
    # 捕捉と適合判定は分離する。内部一覧やtraceの未知形式を成功と推定しない。
    if errors or (scenario != 'user-input-stop' and (not terminal or not matched or error_type)):
        value['status'] = 'operation_diagnostic_stopped'
    cli.exclusive(base / 'isolated-result.json', cli.encoded(value))


def run(source: str, scenario: str):
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + CONTRACT))
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    if scenario not in SCENARIOS:
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
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        return sdk.proxy(args.proxy)
    if args.isolated:
        isolated(args.isolated)
        return 0
    if not args.source or not args.scenario:
        parser.error('--source and --scenario required')
    return run(args.source, args.scenario)


if __name__ == '__main__':
    raise SystemExit(main())
