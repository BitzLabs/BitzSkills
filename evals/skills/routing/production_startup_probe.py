"""無認証・network隔離でSDKのinitializeだけを行う。モデル要求を送らない。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import production_connection_probe as connection
import production_cli_probe as cli
import production_sdk_probe as sdk
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/production-provider-startup-v0.1.json'
REMEDIATION_CONTRACT = 'evals/skills/routing/production-provider-startup-v0.2.json'


def namespace(base, contract):
    args = ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    for path in [ROOT / contract['sdkRelativePath'], Path(contract['codexPath']).parents[1],
                 *(ROOT / 'evals/skills/routing' / name for name in ['production_startup_probe.py', *connection.CODE_FILES])]:
        args += ['--ro-bind', str(path), str(path)]
    return args + ['--bind', str(base), str(base), '--bind', str(base / 'codex-home'), '/home/hide/.codex',
                   '--chdir', str(base / 'work'), '--', '/usr/bin/python3', '-B', str(Path(__file__)), '--isolated', str(base)]


def isolated(base):
    contract = json.loads((base / 'contract.json').read_bytes())
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
    cli.exclusive(base / 'config.json', cli.encoded(connection.http_config_for(base)))

    def deny(*_):
        raise ValueError('unknown server request')

    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
                                   cwd=str(base / 'work')), approval_handler=deny)
    error = None
    try:
        client.start()
        client.initialize()
    except Exception as exc:
        error = type(exc).__name__
    finally:
        client.close()
    for _ in range(30):
        if (base / 'runtime-result.json').exists():
            break
        time.sleep(0.05)
    cli.exclusive(base / 'isolated-result.json', cli.encoded({'sdkErrorType': error}))


def run(source, contract_name=CONTRACT):
    if contract_name not in {CONTRACT, REMEDIATION_CONTRACT}:
        raise ValueError('unknown startup contract')
    raw = guard.git(ROOT, 'show', source + ':' + contract_name)
    contract = json.loads(raw)
    if (contract['version'] != ('production-provider-startup-0.2.0' if contract_name == REMEDIATION_CONTRACT else
                                'production-provider-startup-0.1.0') or
            any(type(contract[key]) is not int or contract[key] != value for key, value in
                [('maximumInvocations', 1), ('maximumLogicalTurns', 0), ('timeoutSeconds', 30), ('paidModelCalls', 0)])):
        raise ValueError('unknown unpaid startup policy')
    if guard.git(ROOT, 'status', '--porcelain') != b'' or guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() != source:
        raise ValueError('clean fixed HEAD required')
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    if contract_name == REMEDIATION_CONTRACT:
        previous = contract['previousFailure']
        path = ROOT / previous['outputRelativeRoot'] / 'receipt.json'
        if any(p.is_symlink() for p in [path, *path.parents]) or hashlib.sha256(path.read_bytes()).hexdigest() != previous['receiptSha256']:
            raise ValueError('original unpaid namespace failure drift')
    base = ROOT / contract['outputRelativeRoot']
    if any(p.is_symlink() for p in [base, *base.parents]):
        raise ValueError('output symlink')
    base.mkdir(mode=0o700)
    for name in ['work', 'tmp', 'codex-home', 'logs', 'state']:
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'contract.json', raw)
    env = {'PATH': str(Path(contract['codexPath']).parents[1] / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(base / 'tmp'), 'LOG_FORMAT': 'json',
           'RUST_LOG': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}
    try:
        process = subprocess.run(namespace(base, contract), env=env, capture_output=True, timeout=30)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    cli.exclusive(base / 'namespace.stdout', stdout)
    cli.exclusive(base / 'namespace.stderr', stderr)
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    result = {'status': 'startup_diagnostic_stopped', 'sourceCommit': source, 'namespaceExitCode': code,
              'sourceGuards': {'before': before, 'after': after}, 'paidModelCalls': 0, 'primaryModelTrajectories': 0,
              'eligibleForMeasurement': False, 'phaseComplete': False}
    if code == 0 and before == after:
        sent = [json.loads(line) for line in (base / 'rpc-in.jsonl').read_bytes().splitlines()]
        received = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
        error = json.loads((base / 'isolated-result.json').read_bytes())['sdkErrorType']
        runtime = json.loads((base / 'runtime-result.json').read_bytes())
        replies = [f for f in received if 'id' in f]
        if ([f.get('method') for f in sent] == ['initialize', 'initialized'] and len(replies) == 1 and
                replies[0].get('id') == sent[0]['id'] and isinstance(replies[0].get('result'), dict) and
                error is None and runtime == {'exitCode': 0, 'forcedShutdown': False} and
                (base / 'trace-safe.jsonl').read_bytes() == b''):
            result['status'] = 'unpaid_sdk_initialization_captured'
        result.update(sdkErrorType=error, runtime=runtime, callerMethods=[f.get('method') for f in sent])
    result['artifactSha256'] = {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in connection.original_artifact_paths(base)}
    cli.exclusive(base / 'receipt.json', cli.encoded(result))
    print(json.dumps({k: v for k, v in result.items() if k not in {'sourceGuards', 'artifactSha256'}}))
    return 0 if result['status'] == 'unpaid_sdk_initialization_captured' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--namespace-remediation', action='store_true')
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
        raise SystemExit(run(args.source, REMEDIATION_CONTRACT if args.namespace_remediation else CONTRACT))
