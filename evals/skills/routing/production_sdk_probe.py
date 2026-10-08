"""公式Python SDKの実通信を隔離環境で検査する。模擬応答だけを使う。"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import production_cli_probe as cli
import source_guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-sdk-probe-v0.1.json'
MODES = ('sdk-native', 'sdk-minimal')


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('dependency symlink')
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        digest.update(path.relative_to(root).as_posix().encode() + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def config_for(base: Path, port: int, contract: dict, mode: str) -> dict:
    if mode not in MODES:
        raise ValueError('unknown probe mode')
    config = cli.policy(base, port, contract)
    # MCPプロセスにもこの試行だけのTMPDIRを渡す。
    config['mcp_servers.production-routing.env.TMPDIR'] = str(base / 'tmp')
    if mode == 'sdk-minimal':
        # features.multi_agent=falseだけではmodel metadataのv2を打ち消せない。
        config.update({'agents.enabled': False, 'features.multi_agent_v2': False,
                       'tools.experimental_request_user_input.enabled': False,
                       'tools.update_plan.enabled': False})
    return config


def deny_request(method: str, params: dict | None) -> dict:
    # SDK既定handlerのacceptを使用しない。未知要求も承認しない。
    if method in {'item/commandExecution/requestApproval', 'item/fileChange/requestApproval'}:
        return {'decision': 'decline'}
    raise ValueError('unexpected server request')


def evaluate(requests: list[dict], frames: list[dict], contract: dict, exit_code: int) -> dict:
    names = []
    error = None
    try:
        if len(requests) != 1:
            raise ValueError('exactly one local request required')
        if requests[0].get('model') != contract['model']:
            raise ValueError('model mismatch')
        names = cli.declared_tools(requests[0])
    except (ValueError, TypeError, AttributeError) as exc:
        error = type(exc).__name__
    replies = [f for f in frames if 'id' in f and 'result' in f]
    thread_replies = [f for f in replies if 'thread' in f['result']]
    turn_replies = [f for f in replies if 'turn' in f['result']]
    thread = thread_replies[0]['result']['thread']['id'] if len(thread_replies) == 1 else None
    turn = turn_replies[0]['result']['turn']['id'] if len(turn_replies) == 1 else None
    completions = [f for f in frames if f.get('method') == 'turn/completed']
    finals = [f for f in frames if f.get('method') == 'item/completed'
              and f.get('params', {}).get('item', {}).get('type') == 'agentMessage']
    no_actions = not any(f.get('method') == 'item/started' and
                        f.get('params', {}).get('item', {}).get('type') not in {'userMessage', 'agentMessage', 'reasoning'}
                        for f in frames)
    final_matches = len(finals) == 1 and finals[0]['params'].get('threadId') == thread and \
        finals[0]['params'].get('turnId') == turn and \
        finals[0]['params']['item'].get('phase') == 'final_answer' and \
        finals[0]['params']['item'].get('text') == 'LOCAL_SIMULATION_ONLY'
    terminal = len(completions) == 1 and completions[0]['params'].get('threadId') == thread and \
        completions[0]['params']['turn'].get('id') == turn and \
        completions[0]['params']['turn'].get('status') == 'completed' and \
        not completions[0]['params']['turn'].get('error')
    ready = [f.get('params', {}) for f in frames if f.get('method') == 'mcpServer/startupStatus/updated'
             and f.get('params', {}).get('name') == 'production-routing']
    mcp_ready = bool(ready) and ready[-1].get('status') == 'ready'
    rpc_ok = thread is not None and turn is not None and terminal and final_matches and no_actions and \
        exit_code == 0 and mcp_ready and not any('error' in f or f.get('method') == 'error' for f in frames)
    exact = error is None and names == sorted(contract['allowedTools'])
    return {'status': 'local_tool_declaration_passed' if rpc_ok and exact else 'local_tool_declaration_stopped',
            'sdkProtocolPassed': rpc_ok, 'closedTwoToolPolicyVerified': exact,
            'offeredToolNames': names, 'toolInventoryError': error,
            'mockTurnCompleted': terminal, 'mockFinalMatched': final_matches,
            'mcpReady': mcp_ready, 'noToolActionsObserved': no_actions,
            'localHttpRequestCount': len(requests), 'runtimeExitCode': exit_code,
            'certifiesBehavior': False, 'certifiesNativeProvider': False, 'certifiesSkillGate': False}


def question_frame(frame: dict) -> bool:
    item = frame.get('params', {}).get('item', {})
    return frame.get('method') in {'item/started', 'item/completed'} and \
        item.get('type') == 'agentMessage' and (bool(item.get('questions')) or item.get('delivery') == 'async')


def proxy(base: Path, reject_questions: bool = False):
    """SDKと既存CLIの間を原bytesのまま中継・保存する。内容を書き換えない。"""
    config = json.loads((base / 'config.json').read_bytes())
    contract = json.loads((base / 'contract.json').read_bytes())
    argv = [contract['codexPath'], 'app-server', '--stdio']
    for key, value in config.items():
        argv.extend(['-c', key + '=' + json.dumps(value)])
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    handles = [os.fdopen(os.open(base / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb')
               for name in ('rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-stderr.bin')]

    def copy(src, dst, saved, lines=False):
        try:
            while raw := (src.readline() if lines else src.read1(65536)):
                saved.write(raw)
                saved.flush()
                if dst == sys.stdout.buffer and reject_questions:
                    frame = json.loads(raw)
                    if question_frame(frame):
                        cli.exclusive(base / 'dialogue-stop.json', cli.encoded(
                            {'reason': 'async-user-input', 'method': frame['method'],
                             'itemId': frame['params']['item']['id'], 'forwardedToSdk': False}))
                        stop.set()
                        return
                    if stop.is_set():
                        return
                dst.write(raw)
                dst.flush()
        except (BrokenPipeError, OSError, ValueError):
            stop.set()
        finally:
            if dst == process.stdin:
                try:
                    dst.close()
                except (OSError, ValueError):
                    pass

    threads = [threading.Thread(target=copy, args=args, daemon=True) for args in
               [(sys.stdin.buffer, process.stdin, handles[0], True),
                (process.stdout, sys.stdout.buffer, handles[1], True),
                (process.stderr, sys.stderr.buffer, handles[2])]]
    for thread in threads:
        thread.start()
    intentional = False
    try:
        while process.poll() is None and not stop.wait(0.05):
            pass
        if process.poll() is None:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                intentional = True
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    finally:
        for thread in threads[1:]:
            thread.join(timeout=1)
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
        cli.exclusive(base / 'runtime-result.json', cli.encoded(
            {'exitCode': process.returncode, 'forcedShutdown': intentional}))
    return 0


def isolated(base: Path, mode: str):
    contract = json.loads((base / 'contract.json').read_bytes())
    sdk_root = ROOT / contract['sdkRelativePath']
    if tree_hash(sdk_root) != contract['sdkTreeSha256']:
        raise ValueError('SDK dependency drift')
    sys.path.insert(0, str(sdk_root))
    from openai_codex import __version__, CodexConfig
    from openai_codex.client import CodexClient
    if __version__ != contract['sdkVersion']:
        raise ValueError('SDK version mismatch')
    version = subprocess.run([contract['codexPath'], '--version'], capture_output=True, timeout=10)
    cli.exclusive(base / 'version.stdout', version.stdout)
    cli.exclusive(base / 'version.stderr', version.stderr)
    if version.returncode or version.stdout.decode().strip() != contract['codexVersion']:
        raise ValueError('CLI version mismatch')
    requests = []
    errors = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            if self.path != '/v1/responses' or len(requests) >= 1:
                errors.append('unexpected local request')
                self.send_error(409)
                return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            cli.exclusive(base / 'local-request.json', raw)
            requests.append(json.loads(raw))
            reply = cli.simulation_reply()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cli.exclusive(base / 'config.json', cli.encoded(config_for(base, server.server_port, contract, mode)))
    sdk_error = None
    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny_request)
    try:
        client.start()
        client.initialize()
        thread = client.thread_start({'model': contract['model'], 'modelProvider': 'bitz_local_probe',
            'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'ephemeral': True,
            'baseInstructions': 'Local protocol simulation. Do not call tools.',
            'developerInstructions': 'No actual model provider or real measurement is used.'})
        turn = client.turn_start(thread.thread.id, [{'type': 'text', 'text': 'Return LOCAL_SIMULATION_ONLY.'}])
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed':
            pass
    except Exception as exc:
        # SDK例外文字列にはstderrが入る場合がある。公開しない。
        sdk_error = type(exc).__name__
    finally:
        client.close()
        server.shutdown()
        server.server_close()
    runtime_path = base / 'runtime-result.json'
    for _ in range(30):
        if runtime_path.exists():
            break
        time.sleep(0.05)
    runtime = json.loads(runtime_path.read_bytes()) if runtime_path.exists() else {'exitCode': None}
    frames = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    result = evaluate(requests, frames, contract, runtime['exitCode'])
    if sdk_error or errors:
        result.update(status='local_tool_declaration_stopped', sdkProtocolPassed=False)
    result.update(mode=mode, sdkVersion=__version__, sdkErrorType=sdk_error, localErrors=errors,
                  forcedShutdown=runtime.get('forcedShutdown'), paidModelCalls=0, primaryModelTrajectories=0)
    cli.exclusive(base / 'isolated-result.json', cli.encoded(result))


def run(source: str, output: str, mode: str):
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + CONTRACT))
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    if mode not in MODES or output != contract['outputLabels'].get(mode) or not re.fullmatch(r'[a-z0-9-]+', output):
        raise ValueError('invalid probe mode or output')
    base = ROOT / '.venv' / output
    if any(p.is_symlink() for p in [base, *base.parents]):
        raise ValueError('output symlink')
    raw = (ROOT / contract['snapshotRelativePath'] / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != contract['manifestSha256'] or \
            json.loads(raw)['sourceCommit'] != contract['candidateSource']:
        raise ValueError('snapshot mismatch')
    if tree_hash(ROOT / contract['sdkRelativePath']) != contract['sdkTreeSha256']:
        raise ValueError('SDK dependency drift')
    base.mkdir(mode=0o700)
    for name in ('work', 'tmp'):
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', cli.encoded(contract))
    env = {'PATH': '/home/hide/.nvm/versions/node/v26.5.0/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp')}
    command = cli.namespace(base, '/usr/bin/python3', ['-B', str(Path(__file__)), '--isolated', str(base), '--mode', mode])
    try:
        result = subprocess.run(command, env=env, capture_output=True, timeout=45)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    cli.exclusive(base / 'namespace.stdout', stdout)
    cli.exclusive(base / 'namespace.stderr', stderr)
    after = source_guard.verify(ROOT, source, contract['sourceFiles'])
    path = base / 'isolated-result.json'
    value = json.loads(path.read_bytes()) if path.exists() else {'status': 'local_probe_unavailable'}
    value.update(sourceCommit=source, phase=4, mode=mode, namespaceExitCode=code,
                 sourceGuards={'before': before, 'after': after},
                 networkNamespaceIsolated=True, homeCredentialsHidden=True,
                 paidModelCalls=0, primaryModelTrajectories=0,
                 artifactSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()})
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'sourceGuards', 'artifactSha256'}}))
    return 0 if value['status'] == 'local_tool_declaration_passed' and code == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--output')
    parser.add_argument('--mode', choices=MODES)
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        return proxy(args.proxy)
    if args.isolated:
        isolated(args.isolated, args.mode)
        return 0
    if not args.source or not args.output or not args.mode:
        parser.error('--source, --output and --mode required')
    return run(args.source, args.output, args.mode)


if __name__ == '__main__':
    raise SystemExit(main())
