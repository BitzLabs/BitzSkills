"""操作診断の原証拠を再照合する。モデル起動や新しい操作試行は行わない。"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
SOURCE = '8637cebc10166c7626137015bef80f69653879b9'
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import source_guard
import production_cli_probe as cli
import production_operation_probe as probe
import production_sdk_probe as sdk


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frames_at(base):
    return [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]


def main():
    contract = json.loads(source_guard.git(ROOT, 'show', SOURCE + ':' + probe.CONTRACT))
    guard = source_guard.verify(ROOT, SOURCE, contract['sourceFiles'])
    head = source_guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    source_guard.verify(ROOT, head, [Path(__file__).relative_to(ROOT).as_posix()])
    require(not source_guard.git(ROOT, 'status', '--porcelain').strip(), 'clean tree required')
    require(sdk.tree_hash(ROOT / contract['sdkRelativePath']) == contract['sdkTreeSha256'], 'SDK drift')
    snapshot = ROOT / contract['snapshotRelativePath']
    require(sha(snapshot / 'manifest.json') == contract['manifestSha256'], 'manifest drift')
    manifest = json.loads((snapshot / 'manifest.json').read_bytes())
    for name, pin in manifest['resources'].items():
        require(sha(snapshot / name) == pin, 'resource drift')
        actual = (snapshot / name).read_bytes()
        require(actual == source_guard.git(ROOT, 'show', manifest['sourceCommit'] + ':' + name.replace('resources/', 'plugins/', 1)), 'candidate Git drift')
    history = []
    for suffix, scenarios in [('01', ['inventory', 'read', 'patch-denied', 'path-denied', 'shell-denied']),
                              ('02', list(probe.SCENARIOS)), ('03', ['user-input-stop']), ('04', ['user-input-stop'])]:
        for scenario in scenarios:
            label = f'production-operation-{scenario}-{suffix}'
            base = ROOT / '.venv' / label
            receipt = json.loads((base / 'receipt.json').read_bytes())
            for name, pin in receipt['artifactSha256'].items():
                require(Path(name).name == name and sha(base / name) == pin, 'raw artifact drift')
            original = json.loads((base / 'contract.json').read_bytes())
            expected = {name: hashlib.sha256(source_guard.git(ROOT, 'show', receipt['sourceCommit'] + ':' + name)).hexdigest()
                        for name in original['sourceFiles']}
            require(all(receipt['sourceGuards'][point]['sourceSha256'] == expected for point in ['before', 'after']), 'historical source mismatch')
            history.append({'outputLabel': label, 'sourceCommit': receipt['sourceCommit'], 'receiptSha256': sha(base / 'receipt.json'),
                            'localHttpRequests': receipt.get('localHttpRequestCount', 0), 'paidModelCalls': receipt['paidModelCalls']})
    inventory_base = ROOT / '.venv/production-operation-inventory-02'
    inventory = json.loads((inventory_base / 'isolated-result.json').read_bytes())['outputObjects'][0]['names']
    require(inventory == ['apply_patch', 'clock__curr_time', 'list_mcp_resource_templates', 'list_mcp_resources',
                          'mcp__production_routing__list_resources', 'mcp__production_routing__read_resource', 'read_mcp_resource'], 'internal inventory drift')
    outcomes = []
    for scenario in probe.SCENARIOS:
        suffix = '04' if scenario == 'user-input-stop' else '02'
        base = ROOT / '.venv' / f'production-operation-{scenario}-{suffix}'
        receipt = json.loads((base / 'receipt.json').read_bytes())
        frames = frames_at(base)
        requests = [json.loads(path.read_bytes()) for path in sorted(base.glob('request-*.json'))]
        require(receipt['namespaceExitCode'] == 0 and receipt['runtime']['exitCode'] == 0, 'runtime failure')
        require(not receipt['localErrors'] and receipt['paidModelCalls'] == 0, 'unexpected local error')
        require(all(r['model'] == contract['model'] and cli.declared_tools(r) == sorted(contract['allowedSurfaceTools']) for r in requests), 'surface drift')
        host = [json.loads(line) for line in (base / 'host.jsonl').read_bytes().splitlines()]
        objects = probe.output_objects(requests[-1]) if len(requests) == 2 else []
        calls = [(i, f['params']['item']) for i, f in enumerate(frames) if f.get('method') == 'item/completed'
                 and f.get('params', {}).get('item', {}).get('type') == 'mcpToolCall']
        require(len(calls) == len(host), 'host/native count mismatch')
        for (_, call), event in zip(calls, host):
            require(call['server'] == 'production-routing' and call['tool'] == event['tool'] and call['arguments'] == event['arguments'], 'host/native binding')
            require(json.loads(call['result']['content'][0]['text']) == event['result'], 'host/native content mismatch')
            require(call['status'] == ('completed' if event['accepted'] else 'failed'), 'host/native status mismatch')
        if scenario == 'user-input-stop':
            stop = json.loads((base / 'dialogue-stop.json').read_bytes())
            require(len(requests) == 1 and stop['forwardedToSdk'] is False and receipt['dialogueStoppedBeforeSdk'], 'dialogue continued')
            require(receipt['sdkErrorType'] == 'TransportClosedError' and not receipt['mockTurnCompleted'], 'dialogue did not stop')
            require(all(receipt['isolationChecks'].values()), 'evaluation tree exposed')
            require(any(sdk.question_frame(f) for f in frames), 'actual question missing')
            outcome = 'async_question_stopped_before_sdk'
        else:
            require(len(requests) == 2 and receipt['mockTurnCompleted'] and receipt['mockFinalMatched'], 'mock protocol incomplete')
            require(len(objects) == 1 and objects[0]['kind'] == scenario, 'operation output missing')
            final_starts = [i for i, f in enumerate(frames) if f.get('method') == 'item/started'
                            and f.get('params', {}).get('item', {}).get('type') == 'agentMessage']
            require(len(final_starts) == 1 and all(i < final_starts[0] for i, _ in calls), 'read after final started')
            if scenario == 'read':
                require([e['tool'] for e in host] == ['list_resources', 'read_resource'] and all(e['accepted'] for e in host), 'body not read')
                require([e['sequence'] for e in host] == [1, 2], 'host order')
                for key, event in zip(['listed', 'read'], host):
                    require(json.loads(objects[0][key]['content'][0]['text']) == event['result'], 'Code Mode result drift')
                result = host[1]['result']
                require(result['sha256'] == manifest['resources'][result['path']] == hashlib.sha256(result['content'].encode()).hexdigest(), 'body hash')
                require(result['content'].encode() == (snapshot / result['path']).read_bytes(), 'body bytes')
                outcome = 'fixed_body_host_native_provider_correspondence'
            elif scenario == 'path-denied':
                require(len(host) == 1 and host[0]['accepted'] is False and objects[0]['result']['isError'] is True, 'host path allowed')
                outcome = 'host_path_refused'
            elif scenario == 'patch-denied':
                require(objects[0]['returned'] is False and 'read-only sandbox' in objects[0]['error'], 'patch did not hit sandbox refusal')
                require(not (base / 'work/prohibited.txt').exists() and not receipt['prohibitedFileExists'], 'prohibited write occurred')
                outcome = 'read_only_sandbox_patch_refused'
            elif scenario in {'shell-denied', 'web-denied', 'agent-denied'}:
                require(objects[0]['returned'] is False and 'is not a function' in objects[0]['error'], 'unexpected exposed operation')
                outcome = 'named_entry_unavailable_not_os_refusal'
            else:
                outcome = 'seven_internal_operations_captured'
        outcomes.append({'scenario': scenario, 'outcome': outcome, 'productionMustStop': scenario not in {'inventory', 'read'}})
    base = ROOT / '.venv/production-operation-parent-verification-01'
    base.mkdir(mode=0o700)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'))
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project', 'plugins/bitz-core',
               '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest', 'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    tests = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
    cli.exclusive(base / 'tests.stdout', tests.stdout)
    cli.exclusive(base / 'tests.stderr', tests.stderr)
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$', tests.stderr.decode())
    require(tests.returncode == 0 and match, 'full skills tests failed')
    source_guard.verify(ROOT, SOURCE, contract['sourceFiles'])
    summary = {'status': 'operation_diagnostic_artifacts_rechecked', 'phase': 4, 'verificationSourceCommit': head,
               'operationSourceCommit': SOURCE, 'records': history, 'internalOperations': inventory, 'outcomes': outcomes,
               'tests': {'count': int(match[1]), 'seconds': match[2], 'exitCode': tests.returncode, 'command': command,
                         'stdoutSha256': sha(base / 'tests.stdout'), 'stderrSha256': sha(base / 'tests.stderr'), 'PYTHONPATH': env['PYTHONPATH']},
               'allHistoricalArtifactHashesChecked': True, 'sourceGuard': guard,
               'totalLocalHttpRequests': sum(r['localHttpRequests'] for r in history), 'paidModelCalls': 0,
               'independentReviewPerformed': False, 'codeModeParentIdExported': False,
               'certifiesProductionRunner': False, 'certifiesNativeProvider': False, 'certifiesSkillGate': False, 'phaseComplete': False}
    cli.exclusive(base / 'summary.json', cli.encoded(summary))
    print(json.dumps({k: v for k, v in summary.items() if k not in {'records', 'sourceGuard', 'tests'}}))
    print(json.dumps(summary['tests']))


if __name__ == '__main__':
    main()
