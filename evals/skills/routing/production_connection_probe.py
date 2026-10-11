"""公式SDKで公開入力の接続だけを診断する。一次評価とGate認定はしない。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

import production_cli_probe as cli
import production_sdk_probe as sdk
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-connection-probe-v0.1.json'
CODE_FILES = ['production_connection_probe.py', 'production_sdk_probe.py', 'production_cli_probe.py', 'source_guard.py']
PROMPT = 'PUBLIC_CONNECTION_DIAGNOSTIC: Return exactly {"ok":true,"scope":"public_connection_diagnostic"}.'
BASE = 'This is a public connection diagnostic. Return the requested JSON without using any tools.'
DEVELOPER = 'Use no tools, files, network tools, questions or delegation. Answer the public input directly.'
FINAL = {'ok': True, 'scope': 'public_connection_diagnostic'}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['ok', 'scope'],
          'properties': {'ok': {'type': 'boolean', 'const': True},
                         'scope': {'type': 'string', 'const': 'public_connection_diagnostic'}}}


def policy(contract):
    if (contract.get('version') != 'production-connection-probe-0.1.0' or
            contract.get('model') != 'gpt-6.1-sol' or contract.get('phase') != 4 or
            contract.get('scope') != 'public-provider-connection-diagnostic-only' or
            any(type(contract.get(key)) is not int or contract[key] != expected for key, expected in
                [('maximumInvocations', 1), ('maximumLogicalTurns', 1), ('timeoutSeconds', 60),
                 ('automaticRetries', 0), ('primaryModelTrajectories', 0), ('expectedObservedApiRequests', 1)])):
        raise ValueError('unknown finite connection diagnostic')


def config_for(base):
    config = {'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
              'apps._default.enabled': False, 'model_provider': 'openai', 'model': 'gpt-6.1-sol',
              'model_providers.openai.request_max_retries': 0, 'model_providers.openai.stream_max_retries': 0,
              'model_providers.openai.supports_websockets': False,
              'log_dir': str(base / 'logs'), 'sqlite_home': str(base / 'state'),
              'agents.enabled': False, 'tools.experimental_request_user_input.enabled': False,
              'tools.update_plan.enabled': False, 'model_reasoning_effort': 'low'}
    for name in ('shell_tool', 'unified_exec', 'shell_snapshot', 'apply_patch_freeform', 'apps',
                 'enable_mcp_apps', 'plugins', 'remote_plugin', 'tool_suggest', 'skill_search',
                 'skill_mcp_dependency_install', 'browser_use', 'browser_use_external',
                 'browser_use_full_cdp_access', 'in_app_browser', 'in_app_chat', 'in_app_local_automation',
                 'computer_use', 'image_generation', 'view_image', 'code_mode', 'code_mode_host',
                 'multi_agent', 'multi_agent_v2', 'goals', 'sleep_tool', 'tool_call_mcp_elicitation',
                 'memories', 'hooks', 'unbounded_connection_retries', 'system_proxy_fallback', 'respect_system_proxy'):
        config['features.' + name] = False
    config['features.skip_host_skill_discovery'] = True
    return config


def reserve(repository, source, contract_raw, storage=None):
    # parentだけで呼ぶ。隔離子processへ台帳や評価コードをmountしない。
    import production_ledger as ledger
    from production_trace import require
    contract = json.loads(contract_raw)
    policy(contract)
    require(isinstance(source, str) and re.fullmatch(r'[0-9a-f]{40}', source), 'fixed source ref')
    if storage is None:
        storage = ledger.common_ledger_path(repository).parent / 'production-provider-diagnostic-ledger'
    ledger.safe_tree(storage)
    storage.mkdir(mode=0o700, exist_ok=True)
    info = storage.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) == 0o700, 'diagnostic ledger owner or mode')
    ledger.sync_directory(storage.parent)
    path = storage / (Path(CONTRACT).stem + '.json')
    value = dict(contractPath=CONTRACT, sourceCommit=source, contractSha256=hashlib.sha256(contract_raw).hexdigest(),
                 maximumInvocations=1, consumedReservations=1, model=contract['model'],
                 role='paidConnectionDiagnostic', primaryModelTrajectories=0, automaticRetry=False)
    ledger.exclusive(path, ledger.encoded(value))
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **value)


def evaluate(sent, frames, api, runtime):
    """原SDK文脈とAPI観測を照合する。HTTP回数の事前強制を意味しない。"""
    from production_trace import require, strict_json, json_equal
    require([f.get('method') for f in sent] == ['initialize', 'initialized', 'thread/start', 'turn/start'],
            'closed caller method sequence')
    require('id' not in sent[1] and all(type(f.get('id')) in {str, int} for f in [sent[0], sent[2], sent[3]]) and
            len({f['id'] for f in [sent[0], sent[2], sent[3]]}) == 3, 'unique caller request ids')
    threads = [f for f in sent if f.get('method') == 'thread/start']
    turns = [f for f in sent if f.get('method') == 'turn/start']
    require(len(threads) == len(turns) == 1, 'one caller thread and turn')
    params = threads[0]['params']
    require(params['model'] == 'gpt-6.1-sol' and params['modelProvider'] == 'openai' and
            params['allowProviderModelFallback'] is False and params['sandbox'] == 'read-only' and
            params['approvalPolicy'] == 'never' and params['ephemeral'] is True and
            params['baseInstructions'] == BASE and params['developerInstructions'] == DEVELOPER,
            'fixed public caller instructions')
    require(json_equal(turns[0]['params']['outputSchema'], SCHEMA) and
            turns[0]['params']['input'] == [{'type': 'text', 'text': PROMPT}], 'fixed public turn')
    starts = [f['params'] for f in frames if f.get('method') == 'turn/started']
    terminals = [f['params'] for f in frames if f.get('method') == 'turn/completed']
    require(len(starts) == len(terminals) == 1, 'one native lifecycle')
    thread, turn = starts[0]['threadId'], starts[0]['turn']['id']
    require(isinstance(thread, str) and bool(thread) and isinstance(turn, str) and bool(turn) and
            turns[0]['params']['threadId'] == thread and terminals[0]['threadId'] == thread and
            terminals[0]['turn']['id'] == turn and terminals[0]['turn']['status'] == 'completed' and
            terminals[0]['turn'].get('error') is None, 'successful original turn context')
    require(next(i for i, f in enumerate(frames) if f.get('method') == 'turn/started') <
            next(i for i, f in enumerate(frames) if f.get('method') == 'turn/completed'), 'native lifecycle order')
    start_index = next(i for i, f in enumerate(frames) if f.get('method') == 'turn/started')
    end_index = next(i for i, f in enumerate(frames) if f.get('method') == 'turn/completed')
    reply_frames = [f for f in frames if 'id' in f and 'result' in f]
    require(len(reply_frames) == 3 and all(type(f['id']) in {str, int} for f in reply_frames) and
            len({f['id'] for f in reply_frames}) == 3 and
            {f['id'] for f in reply_frames} == {sent[i]['id'] for i in [0, 2, 3]}, 'exactly one reply per request')
    replies = {f['id']: f['result'] for f in reply_frames}
    require(replies[threads[0]['id']]['thread']['id'] == thread and
            replies[turns[0]['id']]['turn']['id'] == turn, 'caller reply correlation')
    messages = []
    for index, frame in enumerate(frames):
        require('error' not in frame and frame.get('method') != 'error' and
                not ('method' in frame and 'id' in frame), 'error or server request')
        if frame.get('method') in {'item/started', 'item/completed'}:
            item = frame['params']['item']
            require(start_index < index < end_index and
                    item['type'] in {'userMessage', 'reasoning', 'agentMessage'} and
                    frame['params']['threadId'] == thread and frame['params']['turnId'] == turn,
                    'unknown or tool item')
            if frame['method'] == 'item/completed' and item['type'] == 'agentMessage':
                require(item.get('phase') == 'final_answer', 'nonfinal model message')
                messages.append(strict_json(item['text']))
    require(len(messages) == 1 and json_equal(messages[0], FINAL), 'public final JSON')
    require(len(api) == 1 and type(api[0].get('attempt')) is int and api[0]['attempt'] == 0 and
            type(api[0].get('http.response.status_code')) is int and api[0]['http.response.status_code'] == 200 and
            api[0].get('auth.header_attached') is True, 'one observed authenticated API request')
    require(type(runtime.get('exitCode')) is int and runtime['exitCode'] == 0 and
            runtime.get('forcedShutdown') is False, 'normal process exit')
    return dict(threadId=thread, turnId=turn, observedApiRequests=1, logicalTurns=1, finalMatched=True)


def namespace(base, contract):
    auth = Path('/home/hide/.codex/auth.json')
    if not auth.is_file() or auth.is_symlink():
        raise ValueError('standard CLI authentication unavailable')
    args = ['bwrap', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    for path in [ROOT / contract['sdkRelativePath'], Path(contract['codexPath']).parents[1],
                 *(ROOT / 'evals/skills/routing' / name for name in CODE_FILES)]:
        args += ['--ro-bind', str(path), str(path)]
    return args + ['--bind', str(base), str(base), '--bind', str(base / 'codex-home'), '/home/hide/.codex',
                   '--ro-bind', str(auth), '/home/hide/.codex/auth.json', '--chdir', str(base / 'work'),
                   '--', '/usr/bin/python3', '-B', str(Path(__file__)), '--isolated', str(base)]


def isolated(base):
    contract = json.loads((base / 'contract.json').read_bytes())
    policy(contract)
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
    cli.exclusive(base / 'config.json', cli.encoded(config_for(base)))

    def deny(*_):
        raise ValueError('unexpected SDK server request')

    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny)
    error = None
    try:
        client.start()
        client.initialize()
        thread = client.thread_start({'model': contract['model'], 'modelProvider': 'openai',
            'allowProviderModelFallback': False, 'cwd': str(base / 'work'), 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'ephemeral': True, 'baseInstructions': BASE, 'developerInstructions': DEVELOPER})
        turn = client.turn_start(thread.thread.id, PROMPT, {'outputSchema': SCHEMA, 'effort': 'low'})
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed':
            pass
    except Exception as exc:
        error = type(exc).__name__
    finally:
        client.close()
    for _ in range(30):
        if (base / 'runtime-result.json').exists():
            break
        time.sleep(0.05)
    cli.exclusive(base / 'isolated-result.json', cli.encoded({'sdkErrorType': error}))


def run(source, dry_run=False):
    contract_raw = guard.git(ROOT, 'show', source + ':' + CONTRACT)
    contract = json.loads(contract_raw)
    policy(contract)
    if guard.git(ROOT, 'status', '--porcelain') != b'' or guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() != source:
        raise ValueError('clean fixed HEAD required')
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    if sdk.tree_hash(ROOT / contract['sdkRelativePath']) != contract['sdkTreeSha256']:
        raise ValueError('SDK dependency drift')
    base = ROOT / contract['outputRelativeRoot']
    if any(p.is_symlink() for p in [base, *base.parents]) or base.exists():
        raise ValueError('output already exists or symlink')
    command = namespace(base, contract)
    if dry_run:
        print(json.dumps(dict(status='connection_diagnostic_preflight_checked', sourceCommit=source,
                              maximumLogicalTurns=1, timeoutSeconds=60, paidInvocations=0, eligibleForMeasurement=False)))
        return 0
    reservation = reserve(ROOT, source, contract_raw)
    base.mkdir(mode=0o700)
    for name in ['work', 'tmp', 'codex-home', 'logs', 'state', 'rollout-traces']:
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', contract_raw)
    cli.exclusive(base / 'reservation.json', cli.encoded(reservation))
    cli.exclusive(base / 'invocation.json', cli.encoded({'argv': command, 'sourceCommit': source,
                  'model': contract['model'], 'maximumInvocations': 1, 'promptSha256': hashlib.sha256(PROMPT.encode()).hexdigest()}))
    env = {'PATH': str(Path(contract['codexPath']).parents[1] / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp'), 'LOG_FORMAT': 'json',
           'CODEX_ROLLOUT_TRACE_ROOT': str(base / 'rollout-traces'),
           'RUST_LOG': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}
    invoke = guard.verify(ROOT, source, contract['sourceFiles'])
    if invoke != before:
        raise ValueError('source drift before paid invocation; reservation remains consumed')
    start = time.monotonic()
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=contract['timeoutSeconds'])
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    cli.exclusive(base / 'namespace.stdout', stdout)
    cli.exclusive(base / 'namespace.stderr', stderr)
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    artifact_paths = [p for p in base.rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in base.rglob('*')):
        raise ValueError('artifact symlink; reservation remains consumed')
    value = dict(status='connection_diagnostic_stopped', sourceCommit=source, namespaceExitCode=process.returncode,
                 timedOut=timed_out, elapsedSeconds=time.monotonic() - start,
                 sourceGuards={'before': before, 'invoke': invoke, 'after': after}, sharedReservation=reservation,
                 paidConnectionDiagnosticInvocations=1, primaryModelTrajectories=0, automaticRetries=0,
                 certifiesProviderWireBodies=False, certifiesApiRequestHardCap=False, certifiesAuthorizationRecovery=False,
                 eligibleForMeasurement=False, phaseComplete=False,
                 artifactSha256={str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_paths})
    if process.returncode == 0 and not timed_out and before == invoke == after:
        value['status'] = 'connection_diagnostic_captured'
        value['sdkErrorType'] = json.loads((base / 'isolated-result.json').read_bytes())['sdkErrorType']
        if value['sdkErrorType'] is not None:
            value['status'] = 'connection_diagnostic_stopped'
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'sourceGuards', 'artifactSha256', 'sharedReservation'}}, ensure_ascii=False))
    return 0 if value['status'] == 'connection_diagnostic_captured' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        sdk.proxy(args.proxy, reject_questions=True, reject_actions=True)
    elif args.isolated:
        isolated(args.isolated)
    else:
        if not args.source:
            parser.error('--source required')
        raise SystemExit(run(args.source, args.dry_run))
