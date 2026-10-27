"""通信隔離した実CLIのtool宣言をローカル模擬応答先で捕捉する。有料providerを呼ばない。"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import source_guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-cli-probe-v0.2.json'


def exclusive(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode()


def tool_names(tools, prefix=''):
    if not isinstance(tools, list):
        raise ValueError('tool inventory required')
    names = []
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get('name'), str):
            raise ValueError('unexpected tool declaration')
        name = prefix + tool['name']
        if tool.get('type') == 'namespace':
            names.extend(tool_names(tool.get('tools'), name + '.'))
        elif tool.get('type') in {'function', 'custom'}:
            names.append(name)
        else:
            raise ValueError('unexpected tool declaration')
    if len(names) != len(set(names)):
        raise ValueError('duplicate tools')
    return sorted(names)


def declared_tools(request):
    # CLI0.160.1はtop-level toolsのほかinput.additional_toolsも使用する。
    # 一方だけを見ると、Code Modeや追加agentの宣言を見落とす。
    declarations = list(request.get('tools', []))
    for item in request.get('input', []):
        if item.get('type') == 'additional_tools':
            tools = item.get('tools')
            if not isinstance(tools, list):
                raise ValueError('additional tools inventory required')
            declarations.extend(tools)
    return tool_names(declarations)


def policy(config_root: Path, port: int, contract: dict):
    values = {
        'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
        'apps._default.enabled': False, 'model_provider': 'bitz_local_probe', 'model': 'gpt-6.1-sol',
        'model_providers.bitz_local_probe.name': 'Isolated local simulator',
        'model_providers.bitz_local_probe.base_url': f'http://127.0.0.1:{port}/v1',
        'model_providers.bitz_local_probe.wire_api': 'responses',
        'model_providers.bitz_local_probe.requires_openai_auth': False,
        'model_providers.bitz_local_probe.request_max_retries': 0,
        'model_providers.bitz_local_probe.stream_max_retries': 0,
        'log_dir': str(config_root / 'logs'), 'sqlite_home': str(config_root / 'state'),
        'features.skip_host_skill_discovery': True,
        'mcp_servers.production-routing.command': '/usr/bin/python3',
        'mcp_servers.production-routing.args': ['-B', str(ROOT / 'evals/skills/routing/host.py'),
            '--snapshot', str(ROOT / contract['snapshotRelativePath']), '--manifest-sha256', contract['manifestSha256'],
            '--log', str(config_root / 'host.jsonl')],
        'mcp_servers.production-routing.enabled_tools': ['list_resources', 'read_resource'],
    }
    for name in ('shell_tool', 'unified_exec', 'shell_snapshot', 'apply_patch_freeform', 'apps',
                 'enable_mcp_apps', 'plugins', 'remote_plugin', 'tool_suggest', 'skill_search',
                 'skill_mcp_dependency_install', 'browser_use', 'browser_use_external',
                 'browser_use_full_cdp_access', 'in_app_browser', 'in_app_chat', 'in_app_local_automation',
                 'computer_use', 'image_generation', 'view_image', 'code_mode', 'code_mode_host',
                 'multi_agent', 'goals', 'sleep_tool', 'tool_call_mcp_elicitation', 'memories', 'hooks'):
        values['features.' + name] = False
    values['features.code_mode_host'] = contract.get('codeModeHostEnabled', False)
    return values


def namespace(base: Path, executable: str, args: list[str]):
    node_root = Path('/home/hide/.nvm/versions/node/v26.5.0')
    # home全体を隠す。認証・既存設定・私的評価領域をbindもreadもしない。
    return ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session',
            '--die-with-parent', '--ro-bind', '/', '/', '--tmpfs', '/home/hide', '--tmpfs', '/root',
            '--tmpfs', '/tmp', '--tmpfs', '/run', '--proc', '/proc', '--dev', '/dev',
            '--dir', '/home/hide/BitzLabs', '--ro-bind', str(ROOT), str(ROOT),
            '--dir', '/home/hide/.nvm/versions/node', '--ro-bind', str(node_root), str(node_root),
            '--bind', str(base), str(base), '--chdir', str(base / 'work'), '--', executable, *args]


def simulation_reply():
    item = {'type': 'message', 'id': 'probe-message', 'role': 'assistant', 'phase': 'final_answer',
            'status': 'completed', 'content': [{'type': 'output_text', 'text': 'LOCAL_SIMULATION_ONLY', 'annotations': []}]}
    response = {'id': 'probe-response', 'object': 'response', 'status': 'completed', 'output': [item]}
    events = [
        {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
        {'type': 'response.output_item.added', 'output_index': 0, 'item': {**item, 'status': 'in_progress', 'content': []}},
        {'type': 'response.output_text.delta', 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'delta': 'LOCAL_SIMULATION_ONLY'},
        {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
        {'type': 'response.completed', 'response': response},
    ]
    return ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()


def isolated(base: Path, contract: dict):
    requests = []
    errors = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/v1/responses' or len(requests) >= contract['maximumLocalHttpRequests']:
                errors.append('unexpected-local-request')
                self.send_error(409)
                return
            # ヘッダを保存・出力しない。home遮蔽とrequires_openai_auth=falseで認証を使わない。
            raw = self.rfile.read(int(self.headers['Content-Length']))
            exclusive(base / 'local-request.json', raw)
            requests.append(json.loads(raw))
            reply = simulation_reply()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = policy(base, server.server_port, contract)
    exclusive(base / 'config.json', encoded(config))
    argv = [contract['codexPath'], 'app-server', '--stdio']
    for key, value in config.items():
        argv.extend(['-c', key + '=' + json.dumps(value)])
    env = {'PATH': '/home/hide/.nvm/versions/node/v26.5.0/bin:/usr/bin:/bin',
           'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp')}
    version = subprocess.run([contract['codexPath'], '--version'], env=env, capture_output=True)
    exclusive(base / 'version.stdout', version.stdout)
    exclusive(base / 'version.stderr', version.stderr)
    if version.returncode != 0 or version.stdout.decode().strip() != contract['codexVersion']:
        raise ValueError('CLI version mismatch')
    handles = [os.fdopen(os.open(base / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb')
               for name in ('trace.jsonl', 'stderr.log')]
    process = None
    terminal = False
    sent = 0
    intentional_shutdown = False
    try:
        process = subprocess.Popen(argv, cwd=base / 'work', env=env, stdin=subprocess.PIPE,
                                   stdout=handles[0], stderr=handles[1], start_new_session=True)

        def send(value):
            process.stdin.write((json.dumps(value) + '\n').encode())
            process.stdin.flush()

        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'bitz-local-tool-probe', 'version': '0.1'}, 'capabilities': {'experimentalApi': True}}})
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            frames = []
            for line in (base / 'trace.jsonl').read_bytes().splitlines():
                try:
                    frames.append(json.loads(line))
                except ValueError:
                    continue
            responses = {e['id']: e for e in frames if 'id' in e and ('result' in e or 'error' in e)}
            if sent == 0 and 1 in responses:
                if 'error' in responses[1]:
                    break
                send({'method': 'initialized'})
                send({'id': 2, 'method': 'thread/start', 'params': {'model': 'gpt-6.1-sol', 'modelProvider': 'bitz_local_probe',
                    'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
                    'approvalPolicy': 'never', 'ephemeral': True, 'baseInstructions': 'Local protocol simulation. Do not call tools.',
                    'developerInstructions': 'No actual model provider or real measurement is used.'}})
                sent = 1
            if sent == 1 and 2 in responses:
                if 'error' in responses[2]:
                    break
                thread = responses[2]['result']['thread']['id']
                send({'id': 3, 'method': 'turn/start', 'params': {'threadId': thread, 'input': [{'type': 'text', 'text': 'Return LOCAL_SIMULATION_ONLY.'}]}})
                sent = 2
            completed = [e for e in frames if e.get('method') == 'turn/completed']
            if completed:
                terminal = completed[-1]['params']['turn']['status'] == 'completed'
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
    finally:
        if process is not None:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                intentional_shutdown = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
        server.shutdown()
        server.server_close()
    names = []
    inventory_error = None
    try:
        if len(requests) != 1:
            raise ValueError('local request missing')
        names = declared_tools(requests[0])
    except ValueError as error:
        inventory_error = str(error)
    passed = terminal and not errors and inventory_error is None and names == sorted(contract['allowedTools'])
    value = dict(status='local_tool_declaration_passed' if passed else 'local_tool_declaration_stopped',
                 offeredToolNames=names, toolInventoryError=inventory_error, localHttpRequestCount=len(requests),
                 rawToolTypes=[t.get('type') for t in requests[0].get('tools', [])] if requests else [],
                 localErrors=errors, mockTurnCompleted=terminal, serverExitCode=process.returncode if process else None,
                 intentionalServerShutdown=intentional_shutdown, networkNamespaceIsolated=True,
                 homeCredentialsHidden=True, paidModelCalls=0, primaryModelTrajectories=0,
                 certifiesNativeProvider=False, certifiesSkillGate=False)
    exclusive(base / 'isolated-result.json', encoded(value))


def run(source: str, output: str):
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + CONTRACT))
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    if not re.fullmatch(r'[a-z0-9-]+', output):
        raise ValueError('output label required')
    base = ROOT / '.venv' / output
    if any(p.is_symlink() for p in [base, *base.parents]):
        raise ValueError('output symlink')
    raw = (ROOT / contract['snapshotRelativePath'] / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != contract['manifestSha256'] or json.loads(raw)['sourceCommit'] != contract['candidateSource']:
        raise ValueError('snapshot mismatch')
    base.mkdir(mode=0o700)
    for name in ('work', 'tmp'):
        (base / name).mkdir(mode=0o700)
    exclusive(base / 'contract.json', encoded(contract))
    result = subprocess.run(namespace(base, '/usr/bin/python3', ['-B', str(Path(__file__)), '--isolated', str(base)]),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exclusive(base / 'namespace.stdout', result.stdout)
    exclusive(base / 'namespace.stderr', result.stderr)
    after = source_guard.verify(ROOT, source, contract['sourceFiles'])
    value = json.loads((base / 'isolated-result.json').read_bytes()) if (base / 'isolated-result.json').is_file() else {'status': 'local_probe_unavailable'}
    value.update(sourceCommit=source, phase=4, sourceGuards=dict(before=before, after=after), namespaceExitCode=result.returncode,
                 paidModelCalls=0, primaryModelTrajectories=0, certifiesNativeProvider=False, certifiesSkillGate=False,
                 artifactSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()})
    exclusive(base / 'receipt.json', encoded(value))
    print(json.dumps({k:v for k,v in value.items() if k not in {'sourceGuards', 'artifactSha256'}}))
    return 0 if value['status'] == 'local_tool_declaration_passed' and result.returncode == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--output')
    parser.add_argument('--isolated', type=Path)
    args = parser.parse_args()
    if args.isolated is not None:
        isolated(args.isolated, json.loads((args.isolated / 'contract.json').read_bytes()))
        return 0
    if not args.source or not args.output:
        parser.error('--source and --output required')
    return run(args.source, args.output)


if __name__ == '__main__':
    raise SystemExit(main())
