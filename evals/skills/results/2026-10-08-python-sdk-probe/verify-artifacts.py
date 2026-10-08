"""保存済みSDK通信を再照合し、確定sourceの全スキル試験を実行する。モデルを呼ばない。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
SOURCE = '4fe057a52c455853673a8a4e9467147dd6885474'
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import source_guard


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    contract = json.loads(source_guard.git(ROOT, 'show', SOURCE + ':evals/skills/routing/production-sdk-probe-v0.1.json'))
    before = source_guard.verify(ROOT, SOURCE, contract['sourceFiles'])
    head = source_guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    relative = Path(__file__).relative_to(ROOT).as_posix()
    source_guard.verify(ROOT, head, [relative])
    if source_guard.git(ROOT, 'status', '--porcelain').strip():
        raise ValueError('clean tree required for final tests')
    import production_sdk_probe as sdk
    import production_cli_probe as cli
    if sdk.tree_hash(ROOT / contract['sdkRelativePath']) != contract['sdkTreeSha256']:
        raise ValueError('SDK dependency drift')
    records = []
    for label in ['production-sdk-native-probe-01', 'production-sdk-minimal-probe-01',
                  'production-sdk-native-probe-02', 'production-sdk-minimal-probe-02']:
        base = ROOT / '.venv' / label
        receipt = json.loads((base / 'receipt.json').read_bytes())
        for name, pinned in receipt['artifactSha256'].items():
            if digest(base / name) != pinned:
                raise ValueError('raw artifact drift')
        old_contract = json.loads((base / 'contract.json').read_bytes())
        guard = source_guard.verify(ROOT, receipt['sourceCommit'], old_contract['sourceFiles']) if \
            receipt['sourceCommit'] == SOURCE else None
        # 古い作業treeとの差分は停止記録に残す。Git原bytesと当時のguardだけを別照合する。
        expected = {name: hashlib.sha256(source_guard.git(ROOT, 'show', receipt['sourceCommit'] + ':' + name)).hexdigest()
                    for name in old_contract['sourceFiles']}
        for point in ['before', 'after']:
            if receipt['sourceGuards'][point]['sourceSha256'] != expected:
                raise ValueError('historical guard mismatch')
        record = {'outputLabel': label, 'sourceCommit': receipt['sourceCommit'],
                  'receiptSha256': digest(base / 'receipt.json'), 'originalStatus': receipt['status'],
                  'paidModelCalls': receipt['paidModelCalls']}
        if (base / 'local-request.json').exists():
            request = json.loads((base / 'local-request.json').read_bytes())
            frames = [json.loads(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
            runtime = json.loads((base / 'runtime-result.json').read_bytes())
            result = sdk.evaluate([request], frames, old_contract, runtime['exitCode'])
            if result['closedTwoToolPolicyVerified'] or not result['sdkProtocolPassed']:
                raise ValueError('unexpected reanalysis')
            record.update(requestSha256=digest(base / 'local-request.json'),
                          traceSha256=digest(base / 'rpc-out.jsonl'), reanalysis=result)
        else:
            record['localHttpRequestCount'] = 0
        records.append(record)
    base = ROOT / '.venv' / 'production-sdk-parent-verification-01'
    base.mkdir(mode=0o700)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'))
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline',
               '--project', 'plugins/bitz-core', '--with', 'jsonschema==4.23.0',
               'python', '-B', '-m', 'unittest', 'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
    cli.exclusive(base / 'tests.stdout', result.stdout)
    cli.exclusive(base / 'tests.stderr', result.stderr)
    output = result.stderr.decode()
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$', output)
    if result.returncode or not match:
        raise ValueError('all skills tests failed')
    after = source_guard.verify(ROOT, SOURCE, contract['sourceFiles'])
    summary = {'status': 'sdk_probe_artifacts_rechecked', 'phase': 4, 'probeSourceCommit': SOURCE,
               'verificationSourceCommit': head, 'verificationScriptSha256': digest(Path(__file__)),
               'sourceGuards': {'before': before, 'after': after}, 'records': records,
               'tests': {'count': int(match[1]), 'seconds': match[2], 'exitCode': result.returncode,
                         'command': command, 'PYTHONPATH': env['PYTHONPATH'],
                         'stdoutSha256': digest(base / 'tests.stdout'), 'stderrSha256': digest(base / 'tests.stderr')},
               'paidModelCalls': 0, 'closedTwoToolPolicyVerified': False, 'phaseComplete': False,
               'certifiesNativeProvider': False, 'certifiesBehavior': False, 'certifiesSkillGate': False,
               'independentReviewPerformed': False}
    cli.exclusive(base / 'summary.json', cli.encoded(summary))
    print(json.dumps({'status': summary['status'], 'tests': summary['tests'],
                      'protocolModes': [r['reanalysis']['sdkProtocolPassed'] for r in records if 'reanalysis' in r],
                      'toolCounts': [len(r['reanalysis']['offeredToolNames']) for r in records if 'reanalysis' in r],
                      'paidModelCalls': 0, 'closedTwoToolPolicyVerified': False}))


if __name__ == '__main__':
    main()
