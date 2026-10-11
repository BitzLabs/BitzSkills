"""隔離・無認証の公式SDK/CLIへ通信故障を注入する。有料モデルと一次評価は0。"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import production_cli_probe as cli
import production_sdk_probe as sdk
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-fault-probe-v0.1.json'
CASES = {'http-503-zero-retry': ('http-503', 0, 1),
         'http-503-one-retry-control': ('http-503', 1, 2),
         'stream-cut-zero-retry': ('stream-cut', 0, 1),
         'connection-zero-retry': ('connection', 0, 0)}
CODE_FILES = ['production_fault_probe.py', 'production_sdk_probe.py', 'production_cli_probe.py', 'source_guard.py']


def policy(contract, case):
    if (case not in CASES or contract['version'] != 'production-fault-probe-0.1.0' or
            type(contract['maximumScenarios']) is not int or contract['maximumScenarios'] != 4 or
            type(contract['maximumLocalHttpRequestsPerScenario']) is not int or
            contract['maximumLocalHttpRequestsPerScenario'] != 2 or
            type(contract['paidModelCalls']) is not int or contract['paidModelCalls'] != 0 or
            contract['automaticPaidRetries'] != 0 or contract['timeoutSeconds'] != 30):
        raise ValueError('unknown finite fault policy')
    return CASES[case]


def outcome(frames, thread, turn, count, expected, runtime, sdk_error):
    starts = [f['params'] for f in frames if f.get('method') == 'turn/started']
    terminals = [f['params'] for f in frames if f.get('method') == 'turn/completed']
    matches = lambda p: p.get('threadId') == thread and p.get('turn', {}).get('id') == turn
    passed = (isinstance(thread, str) and bool(thread) and isinstance(turn, str) and bool(turn) and
              len(starts) == len(terminals) == 1 and matches(starts[0]) and matches(terminals[0]) and
              next(i for i, f in enumerate(frames) if f.get('method') == 'turn/started') <
              next(i for i, f in enumerate(frames) if f.get('method') == 'turn/completed') and
              terminals[0]['turn'].get('status') == 'failed' and sdk_error is None and
              type(count) is int and count == expected and isinstance(runtime, dict) and
              type(runtime.get('exitCode')) is int and runtime['exitCode'] == 0 and
              runtime.get('forcedShutdown') is False)
    return {'status': 'bounded_fault_diagnostic_captured' if passed else 'fault_diagnostic_stopped',
            'failedTurnObserved': bool(terminals and terminals[0].get('turn', {}).get('status') == 'failed'),
            'requests': count, 'expectedRequests': expected, 'sdkErrorType': sdk_error,
            'runtime': runtime, 'paidModelCalls': 0, 'primaryModelTrajectories': 0,
            'certifiesAuthorizationRecovery': False, 'certifiesNativeProvider': False,
            'eligibleForMeasurement': False, 'certifiesSkillGate': False}


def namespace(base, contract):
    args = ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    for path in [ROOT / contract['sdkRelativePath'], Path(contract['codexPath']).parents[1],
                 *(ROOT / 'evals/skills/routing' / name for name in CODE_FILES)]:
        args += ['--ro-bind', str(path), str(path)]
    return args + ['--bind', str(base), str(base), '--chdir', str(base / 'work'), '--', '/usr/bin/python3',
                   '-B', str(Path(__file__)), '--isolated', str(base)]


def isolated(base):
    contract = json.loads((base / 'contract.json').read_bytes())
    case = (base / 'case.txt').read_text()
    fault, retries, expected = policy(contract, case)
    if any((ROOT / p).exists() for p in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results']):
        raise ValueError('evaluation tree visible')
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
    requests, overflows = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            if self.path != '/v1/responses' or len(requests) >= 2:
                overflows.append(self.path)
                self.send_error(409)
                return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            cli.exclusive(base / f'request-{len(requests) + 1}.json', raw)
            requests.append(raw)
            if fault == 'http-503':
                reply = b'{"error":{"message":"PUBLIC_LOCAL_FAULT","type":"server_error","code":"PUBLIC_LOCAL_FAULT"}}'
                status, kind = 503, 'application/json'
            else:
                reply = b'data: {"type":"response.created","response":{"id":"public-fault-response"}}\n\n'
                status, kind = 200, 'text/event-stream'
            cli.exclusive(base / f'response-{len(requests)}.bin', reply)
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    port = server.server_port
    serving = fault != 'connection'
    if serving:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    else:
        server.server_close()
    config = sdk.config_for(base, port, contract, 'sdk-minimal')
    config = {k: v for k, v in config.items() if not k.startswith('mcp_servers.')}
    config.update({'model_providers.bitz_local_probe.request_max_retries': retries,
                   'model_providers.bitz_local_probe.stream_max_retries': 0,
                   'model_providers.bitz_local_probe.supports_websockets': False,
                   'features.unbounded_connection_retries': False,
                   'features.system_proxy_fallback': False, 'features.respect_system_proxy': False})
    cli.exclusive(base / 'config.json', cli.encoded(config))

    def deny(*_):
        raise ValueError('unexpected SDK server request')

    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny)
    thread = turn = error = None
    try:
        client.start()
        client.initialize()
        started = client.thread_start({'model': contract['model'], 'modelProvider': 'bitz_local_probe',
            'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'ephemeral': True, 'baseInstructions': 'PUBLIC_LOCAL_TRANSPORT_DIAGNOSTIC',
            'developerInstructions': 'LOCAL_SIMULATION_ONLY. No paid model.'})
        thread = started.thread.id
        started_turn = client.turn_start(thread, 'PUBLIC_LOCAL_TRANSPORT_FAULT')
        turn = started_turn.turn.id
        while client.next_turn_notification(turn).method != 'turn/completed':
            pass
    except Exception as exc:
        error = type(exc).__name__
    finally:
        client.close()
        if serving:
            server.shutdown()
        server.server_close()
    for _ in range(30):
        if (base / 'runtime-result.json').exists():
            break
        time.sleep(0.05)
    frames = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    runtime = json.loads((base / 'runtime-result.json').read_bytes()) if (base / 'runtime-result.json').exists() else None
    value = outcome(frames, thread, turn, len(requests), expected, runtime, error)
    api = [event['fields'] for line in (base / 'trace-safe.jsonl').read_bytes().splitlines()
           if (event := json.loads(line)).get('fields', {}).get('event.name') == 'codex.api_request']
    expected_api = 1 if fault == 'connection' else expected
    statuses = [f.get('http.response.status_code') for f in api]
    expected_statuses = [None] if fault == 'connection' else [503 if fault == 'http-503' else 200] * expected
    api_matched = (len(api) == expected_api and statuses == expected_statuses and
                   all(type(f.get('attempt')) is int and f['attempt'] == i and
                       f.get('auth.header_attached') is False for i, f in enumerate(api)))
    value.update(apiRequests=len(api), expectedApiRequests=expected_api, httpStatuses=statuses, apiMatched=api_matched)
    if overflows or not api_matched:
        value['status'] = 'fault_diagnostic_stopped'
    value['overflows'] = overflows
    cli.exclusive(base / 'isolated-result.json', cli.encoded(value))


def run(source, case):
    contract_raw = guard.git(ROOT, 'show', source + ':' + CONTRACT)
    contract = json.loads(contract_raw)
    policy(contract, case)
    if guard.git(ROOT, 'status', '--porcelain') != b'' or guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() != source:
        raise ValueError('clean fixed HEAD required')
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    base = ROOT / contract['outputRelativeRoot'] / case
    if any(p.is_symlink() for p in [base, *base.parents]):
        raise ValueError('output symlink')
    base.parent.mkdir(mode=0o700, exist_ok=True)
    base.mkdir(mode=0o700)
    for name in ['work', 'tmp']:
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', contract_raw)
    cli.exclusive(base / 'case.txt', case.encode())
    env = {'PATH': '/home/hide/.nvm/versions/node/v26.5.0/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp'), 'LOG_FORMAT': 'json',
           'RUST_LOG': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}
    started = time.monotonic()
    try:
        process = subprocess.run(namespace(base, contract), env=env, capture_output=True, timeout=contract['timeoutSeconds'])
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    cli.exclusive(base / 'namespace.stdout', stdout)
    cli.exclusive(base / 'namespace.stderr', stderr)
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    value = json.loads((base / 'isolated-result.json').read_bytes()) if (base / 'isolated-result.json').exists() else {'status': 'fault_diagnostic_unavailable'}
    value.update(sourceCommit=source, case=case, namespaceExitCode=code, elapsedSeconds=time.monotonic() - started,
                 sourceGuards={'before': before, 'after': after},
                 artifactSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()})
    if code != 0 or before != after:
        value['status'] = 'fault_diagnostic_stopped'
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'sourceGuards', 'artifactSha256'}}))
    return 0 if value['status'] == 'bounded_fault_diagnostic_captured' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    select = parser.add_mutually_exclusive_group()
    select.add_argument('--case', choices=CASES)
    select.add_argument('--all', action='store_true')
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        sdk.proxy(args.proxy, reject_questions=True)
    elif args.isolated:
        isolated(args.isolated)
    else:
        if not args.source or not (args.case or args.all):
            parser.error('--source and --case/--all required')
        for case in CASES if args.all else [args.case]:
            if run(args.source, case):
                raise SystemExit(1)
