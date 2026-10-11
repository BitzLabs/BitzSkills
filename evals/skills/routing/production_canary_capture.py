"""有限初回カナリアの原取得。採点・独立原照合を完了するまで次を起動しない。"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import production_cli_probe as cli
import production_connection_probe as connection
import production_ledger as ledger
import production_sdk_probe as sdk
import production_trace as trace
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-canary-v0.1.json'
BASE = '公開製品の発火選択だけを評価する。実操作の成功を主張せず、指定JSONで応答する。'
DEVELOPER = '固定された読取りホスト以外の操作・質問・委譲は禁止。最大一覧1回・本文1回・制御2回。'
CODE = ['production_canary_capture.py', 'production_canary_host.py', 'production_connection_probe.py',
        'production_sdk_probe.py', 'production_cli_probe.py', 'production_ledger.py', 'production_trace.py', 'host.py', 'source_guard.py']


def policy(value):
    trace.require(trace.json_equal(value.get('diagnosticTracing'), sdk.DIAGNOSTIC_TRACING),
                  'fixed diagnostic tracing required')
    trace.require(value['version'] == 'production-canary-0.1.0' and value['phase'] == 4 and
                  value['scope'] == 'public-production-routing-canary-only' and value['model'] == 'gpt-6.1-sol', 'canary identity')
    limits = dict(repetitions=2, timeoutSeconds=300, observedModelApiLimit=3,
                  observedCatalogApiLimit=2, maximumHostCalls=2, maximumControlCalls=2)
    trace.require(all(type(value[k]) is int and value[k] == n for k, n in limits.items()), 'fixed finite limits')
    trace.require(trace.json_equal(value['budget'], dict(primaryModelTrajectories=4, independentReviewerSol=4,
                                                       automaticRetries=0, delegations=0)) and
                  all(value[k] is False for k in ['certifiesApiRequestHardCap', 'certifiesBehavior', 'certifiesSkillGate']), 'limited certification')


def prepare(source):
    trace.require(guard.git(ROOT, 'status', '--porcelain') == b'' and
                  guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean fixed HEAD required')
    raw = guard.git(ROOT, 'show', source + ':' + CONTRACT)
    value = trace.strict_json(raw)
    policy(value)
    source_guard = guard.verify(ROOT, source, value['sourceFiles'])
    snapshot = ROOT / value['snapshotRelativePath']
    ledger.safe_tree(snapshot)
    manifest_raw = (snapshot / 'manifest.json').read_bytes()
    trace.require(ledger.sha(manifest_raw) == value['manifestSha256'], 'fixed manifest')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    for name, digest in manifest['resources'].items():
        # snapshotの全資源と公開Git本文を照合。モデルの期待値は含めない。
        path = snapshot / name
        ledger.safe_tree(path)
        public_path = 'plugins/' + str(Path(name).relative_to('resources'))
        trace.require(ledger.sha(path.read_bytes()) == digest and
                      ledger.sha(guard.git(ROOT, 'show', source + ':' + public_path)) == digest, 'public resource drift')
    trace.require(sdk.tree_hash(ROOT / value['sdkRelativePath']) == value['sdkTreeSha256'], 'SDK drift')
    raws = [guard.git(ROOT, 'show', source + ':' + path) for path in
            ['evals/skills/routing/production-canary-cases-v0.1.json', 'evals/skills/event-catalog.json']]
    raws += [manifest_raw, guard.git(ROOT, 'show', source + ':evals/skills/routing/production-canary-instructions-v0.1.txt'),
             ledger.encoded({'platform': 'Linux', 'codexVersion': value['codexVersion'], 'sdkVersion': value['sdkVersion']})]
    runtime = dict(value, schemaVersion='1.0', sourceCommit=source, candidateSource=manifest['sourceCommit'],
                   inputSha256={k: ledger.sha(v) for k, v in zip(['cases', 'catalog', 'manifest', 'instructions', 'environment'], raws)})
    return ledger.bind_initial_canary_inputs(ledger.encoded(runtime), *raws), source_guard


def config_for(base, contract):
    config = connection.http_config_for(base)
    # 固定CLIが無視すると原通知した非対応設定をカナリアには持ち込まない。
    config.pop('model_providers.bitz_openai_http.include_internal_metadata')
    config['suppress_unstable_features_warning'] = True
    config['features.code_mode_host'] = True
    config.update({'mcp_servers.production-routing.command': '/usr/bin/python3',
        'mcp_servers.production-routing.args': ['-B', str(ROOT / 'evals/skills/routing/production_canary_host.py'),
            '--snapshot', str(ROOT / contract['snapshotRelativePath']), '--manifest-sha256', contract['manifestSha256'],
            '--log', str(base / 'host.jsonl')],
        'mcp_servers.production-routing.enabled_tools': ['list_resources', 'read_resource'],
        'mcp_servers.production-routing.default_tools_approval_mode': 'prompt'})
    for name in ['list_resources', 'read_resource']:
        config['mcp_servers.production-routing.tools.' + name + '.approval_mode'] = 'approve'
    return config


class CaptureGuard:
    """応答ログで観測した超過を停止する。送信前のAPI hard capとは異なる。"""
    def __init__(self, base):
        self.base = base
        self.counts = {'/models': 0, '/responses': 0, 'control': 0}
        self.lock = threading.Lock()

    def __call__(self, kind, value):
        with self.lock:
            reason = None
            if (self.base / 'capture-stop.json').exists():
                return False
            if (self.base / 'host-stop.json').exists():
                reason = 'host-policy-stop'
            elif not isinstance(value, dict):
                reason = 'invalid-capture-object'
            elif kind == 'rpc':
                if 'id' in value and 'method' in value:
                    reason = 'server-request'
                elif 'method' in value and (not isinstance(value['method'], str) or not isinstance(value.get('params'), dict)):
                    reason = 'invalid-notification'
                elif value.get('method') in {'item/started', 'item/completed'}:
                    item = value.get('params', {}).get('item', {})
                    if not isinstance(item, dict) or item.get('type') not in {'userMessage', 'agentMessage', 'reasoning', 'mcpToolCall'}:
                        reason = 'unknown-action'
                    elif item.get('type') == 'mcpToolCall' and (item.get('server') != 'production-routing' or
                            item.get('tool') not in {'list_resources', 'read_resource'}):
                        reason = 'unknown-host-tool'
            elif kind == 'telemetry':
                fields = value.get('fields', {})
                if not isinstance(fields, dict):
                    reason = 'invalid-telemetry-fields'
                name = fields.get('event.name') if isinstance(fields, dict) else None
                if name == 'codex.api_request':
                    endpoint = fields.get('endpoint')
                    if endpoint not in {'/models', '/responses'} or type(fields.get('attempt')) is not int or fields['attempt'] != 0 or \
                            fields.get('auth.header_attached') is not True or type(fields.get('http.response.status_code')) is not int or \
                            fields['http.response.status_code'] != 200 or fields.get('auth.retry_after_unauthorized', False) is not False:
                        reason = 'unknown-or-failed-api'
                    else:
                        self.counts[endpoint] += 1
                        if self.counts[endpoint] > (2 if endpoint == '/models' else 3):
                            reason = 'observed-api-limit'
                elif name == 'codex.tool_call_received':
                    source = fields.get('tool_source')
                    if source == 'direct':
                        self.counts['control'] += 1
                        if fields.get('tool_name') not in ('exec', 'wait') or self.counts['control'] > 2:
                            reason = 'control-policy-limit'
                    elif source == 'code_mode':
                        if fields.get('tool_namespace') != 'mcp__production_routing' or fields.get('tool_name') not in ('list_resources', 'read_resource'):
                            reason = 'unknown-child-tool'
                    else:
                        reason = 'unknown-tool-source'
            else:
                reason = 'unknown-capture-direction'
            if reason is not None:
                marker = self.base / 'capture-stop.json'
                if not marker.exists():
                    cli.exclusive(marker, cli.encoded({'reason': reason, 'counts': self.counts, 'certifiesApiRequestHardCap': False}))
                return False
            return True


def namespace(base, contract):
    auth = Path('/home/hide/.codex/auth.json')
    trace.require(auth.is_file() and not auth.is_symlink(), 'standard CLI authentication unavailable')
    args = ['bwrap', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    paths = [ROOT / contract['sdkRelativePath'], ROOT / contract['snapshotRelativePath'], Path(contract['codexPath']).parents[1],
             *(ROOT / 'evals/skills/routing' / name for name in CODE)]
    for path in paths:
        args += ['--ro-bind', str(path), str(path)]
    return args + ['--bind', str(base), str(base), '--bind', str(base / 'codex-home'), '/home/hide/.codex',
        '--ro-bind', str(auth), '/home/hide/.codex/auth.json', '--chdir', str(base / 'work'), '--', '/usr/bin/python3',
        '-B', str(Path(__file__)), '--isolated', str(base)]


def isolated(base):
    contract = trace.strict_json((base / 'contract.json').read_bytes())
    policy(contract)
    trace.require(not any((ROOT / p).exists() for p in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results']), 'evaluation tree visible')
    sys.path.insert(0, str(ROOT / contract['sdkRelativePath']))
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    trace.require(__version__ == contract['sdkVersion'] and sdk.tree_hash(ROOT / contract['sdkRelativePath']) == contract['sdkTreeSha256'], 'SDK drift')
    version = subprocess.run([contract['codexPath'], '--version'], capture_output=True, timeout=10)
    cli.exclusive(base / 'version.stdout', version.stdout)
    cli.exclusive(base / 'version.stderr', version.stderr)
    trace.require(version.returncode == 0 and version.stdout.decode().strip() == contract['codexVersion'], 'CLI drift')
    cli.exclusive(base / 'config.json', cli.encoded(config_for(base, contract)))

    def deny(*_):
        raise ValueError('unexpected SDK request')

    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny)
    error = None
    try:
        client.start()
        client.initialize()
        thread = client.thread_start(dict(model=contract['model'], modelProvider='bitz_openai_http', allowProviderModelFallback=False,
            cwd=str(base / 'work'), sandbox='read-only', approvalPolicy='never', ephemeral=True,
            baseInstructions=BASE, developerInstructions=DEVELOPER, experimentalRawEvents=True))
        turn = client.turn_start(thread.thread.id, (base / 'model-input.json').read_text(),
                                 {'outputSchema': trace.strict_json((base / 'decision-schema.json').read_bytes()), 'effort': 'low'})
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
    bound, before = prepare(source)
    contract = bound.contract
    root = ROOT / contract['outputRelativeRoot']
    ledger.safe_tree(root)
    if dry_run:
        print(json.dumps(dict(status='canary_preflight_checked', primaryInvocations=0, repetitions=2,
                              payloadSha256=bound.identity['payloadSha256'], certifiesApiRequestHardCap=False)))
        return 0
    instance = ledger.open_ledger(ROOT, bound)
    attempt = instance.reserve()
    base = ROOT / attempt['outputRelativePath']
    ledger.safe_tree(base)
    base.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ['work', 'tmp', 'codex-home', 'logs', 'state', 'rollout-traces']:
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', bound.contract_raw)
    cli.exclusive(base / 'reservation.json', ledger.encoded(attempt))
    cli.exclusive(base / 'model-input.json', bound.payloads[(attempt['attempt'] - 1) // bound.repetitions])
    schema = trace.strict_json(guard.git(ROOT, 'show', source + ':evals/skills/schemas/decision.schema.json'))
    schema['properties']['selectedEntry']['enum'] = [None, *sorted(trace.SKILLS)]
    cli.exclusive(base / 'decision-schema.json', cli.encoded(schema))
    command = namespace(base, contract)
    cli.exclusive(base / 'invocation.json', cli.encoded({'argv': command, 'sourceCommit': source, 'maximumLogicalTurns': 1,
                  'modelInputSha256': attempt['modelInputSha256']}))
    invoke = guard.verify(ROOT, source, contract['sourceFiles'])
    trace.require(invoke == before, 'source drift before invocation; reservation consumed')
    env = {'PATH': str(Path(contract['codexPath']).parents[1] / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp'), 'LOG_FORMAT': 'json',
           'CODEX_ROLLOUT_TRACE_ROOT': str(base / 'rollout-traces'),
           'RUST_LOG': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}
    start = time.monotonic()
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=300)
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
    files = connection.original_artifact_paths(base)
    files += [base / n for n in ['model-input.json', 'decision-schema.json', 'host.jsonl', 'host-stop.json', 'capture-stop.json', 'dialogue-stop.json', 'proxy-capture-errors.json'] if (base / n).exists()]
    for path in files:
        ledger.safe_tree(path)
    runtime = trace.strict_json((base / 'runtime-result.json').read_bytes()) if (base / 'runtime-result.json').exists() else None
    result = trace.strict_json((base / 'isolated-result.json').read_bytes()) if (base / 'isolated-result.json').exists() else None
    captured = process.returncode == 0 and not timed_out and before == invoke == after and \
        runtime == {'exitCode': 0, 'forcedShutdown': False, 'captureIntegrity': True} and result == {'sdkErrorType': None} and \
        not any((base / n).exists() for n in ['host-stop.json', 'capture-stop.json', 'dialogue-stop.json'])
    value = dict(status='primary_capture_awaits_parent_and_independent_review' if captured else 'primary_capture_stopped',
        sourceCommit=source, attempt=attempt, sourceGuards=dict(before=before, invoke=invoke, after=after),
        namespaceExitCode=process.returncode, timedOut=timed_out, elapsedSeconds=time.monotonic() - start,
        artifactSha256={str(p.relative_to(base)): ledger.sha(p.read_bytes()) for p in files},
        primaryModelTrajectories=1, independentReviewPerformed=False, automaticRetries=0,
        certifiesApiRequestHardCap=False, eligibleForMeasurement=False, phaseComplete=False)
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'sourceGuards', 'artifactSha256', 'attempt'}}))
    return 0 if captured else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--isolated', type=Path)
    parser.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    if args.proxy:
        sdk.proxy(args.proxy, reject_questions=True, capture_guard=CaptureGuard(args.proxy))
    elif args.isolated:
        isolated(args.isolated)
    elif args.source:
        raise SystemExit(run(args.source, args.dry_run))
    else:
        parser.error('--source required')
