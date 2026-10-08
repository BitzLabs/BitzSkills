"""確定ref/原ログを照合してSDK接続診断を再現する。モデルを起動しない。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_sdk_trace as sdk
import production_operation_probe as operation
import production_cli_probe as cli
import source_guard

CONTRACT = 'evals/skills/routing/production-operation-probe-v0.5.json'
OUTPUT = ROOT / '.venv/production-sdk-trace-verification-01'
WARNING = ('Under-development features enabled: skip_host_skill_discovery. '
           'Under-development features are incomplete and may behave unpredictably. '
           'To suppress this warning, set `suppress_unstable_features_warning = true` '
           'in /home/hide/.codex/config.toml.')
OLD_RECORD = 'evals/skills/results/2026-10-08-operation-probe/summary.json'
OLD_SOURCE = 'a14e17b0d84cc0a184c5e5bc44a42f8d66111587'
require = sdk.require


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(name: str):
    return sdk.trace.strict_json((ROOT / name).read_bytes())


def frames(base: Path, name: str):
    return [sdk.trace.strict_json(line) for line in (base / name).read_bytes().splitlines()]


def receipt(base: Path, *, expected_sha: str | None = None):
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'artifact symlink')
    raw = (base / 'receipt.json').read_bytes()
    require(expected_sha is None or sha(raw) == expected_sha, 'original receipt hash drift')
    value = sdk.trace.strict_json(raw)
    for name, digest in value['artifactSha256'].items():
        require(Path(name).name == name and not (base / name).is_symlink(), 'artifact path')
        require(sha((base / name).read_bytes()) == digest, 'artifact hash drift')
    for stage in ('before', 'after'):
        guard = value['sourceGuards'][stage]
        require(guard['sourceCommit'] == value['sourceCommit'], 'artifact source binding')
        for name, digest in guard['sourceSha256'].items():
            require(sha(source_guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == digest,
                    'historical source hash drift')
    require(value['namespaceExitCode'] == 0 and value['paidModelCalls'] == 0 and
            value['runtime']['exitCode'] == 0 and value['runtime']['forcedShutdown'] is False, 'probe runtime failed')
    return value, sha(raw)


def check_snapshot(contract: dict):
    snapshot = ROOT / contract['snapshotRelativePath']
    raw = (snapshot / 'manifest.json').read_bytes()
    require(sha(raw) == contract['manifestSha256'], 'snapshot manifest drift')
    manifest, _, _ = sdk.trace.manifest_view(raw)
    require(manifest['sourceCommit'] == contract['candidateSource'], 'candidate ref drift')
    for name, digest in manifest['resources'].items():
        content = (snapshot / name).read_bytes()
        require(sha(content) == digest and content == source_guard.git(ROOT, 'show',
                contract['candidateSource'] + ':plugins/' + name.removeprefix('resources/')), 'candidate bytes drift')
    return raw, len(manifest['resources'])


def run(source: str):
    require(source_guard.git(ROOT, 'status', '--porcelain') == b'', 'clean tree required')
    require(source_guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'verification HEAD required')
    contract = read(CONTRACT)
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    require(operation.CONTRACT == CONTRACT, 'probe contract mismatch')
    require(not any(p.is_symlink() for p in (OUTPUT, *OUTPUT.parents)), 'verification output symlink')
    OUTPUT.mkdir(mode=0o700)
    manifest_raw, resource_count = check_snapshot(contract)
    records = []
    old = sdk.trace.strict_json(source_guard.git(ROOT, 'show', OLD_SOURCE + ':' + OLD_RECORD))
    original = next(r for r in old['records'] if r['outputLabel'] == 'production-operation-read-02')
    base = ROOT / '.venv' / original['outputLabel']
    value, original_hash = receipt(base, expected_sha=original['receiptSha256'])
    result = sdk.diagnose(manifest_raw, frames(base, 'host.jsonl'), frames(base, 'rpc-in.jsonl'),
                          frames(base, 'rpc-out.jsonl'), expected_final_text='LOCAL_SIMULATION_ONLY',
                          actual_exit_code=value['runtime']['exitCode'], allowed_warnings=(WARNING,))
    records.append({'outputLabel': base.name, 'receiptSha256': original_hash, 'sourceCommit': value['sourceCommit'],
                    'diagnostic': result, 'originalProviderResponseAvailable': False})
    base = ROOT / '.venv' / contract['outputLabels']['read']
    value, receipt_hash = receipt(base)
    require(value['sourceCommit'] == source and value['localHttpRequestCount'] == 2 and
            all(value['isolationChecks'].values()), 'new read binding or isolation')
    result = sdk.diagnose_exchange(manifest_raw, frames(base, 'host.jsonl'), frames(base, 'rpc-in.jsonl'),
        frames(base, 'rpc-out.jsonl'), [read(str((base / f'request-{i}.json').relative_to(ROOT))) for i in (1, 2)],
        [(base / f'response-{i}.sse').read_bytes() for i in (1, 2)],
        expected_program=operation.program('read', base), expected_final_text='LOCAL_SIMULATION_ONLY',
        actual_exit_code=value['runtime']['exitCode'], allowed_warnings=(WARNING,))
    records.append({'outputLabel': base.name, 'receiptSha256': receipt_hash, 'sourceCommit': value['sourceCommit'],
                    'diagnostic': result, 'originalProviderResponseAvailable': True})
    base = ROOT / '.venv' / contract['outputLabels']['user-input-stop']
    value, receipt_hash = receipt(base)
    require(value['sourceCommit'] == source and value['localHttpRequestCount'] == 1 and
            value['dialogueStoppedBeforeSdk'] is True and value['sdkErrorType'] == 'TransportClosedError' and
            all(value['isolationChecks'].values()) and value['hostEventCount'] == 0 and
            value['mockTurnCompleted'] is False and not (base / 'response-2.sse').exists(), 'question stop mismatch')
    saved = read(str((base / 'dialogue-stop.json').relative_to(ROOT)))
    native = frames(base, 'rpc-out.jsonl')
    questions = [f for f in native if operation.sdk.question_frame(f)]
    require(len(questions) == 1 and saved == {'reason': 'async-user-input', 'method': questions[0]['method'],
            'itemId': questions[0]['params']['item']['id'], 'forwardedToSdk': False}, 'question gate correspondence')
    require(sdk.scripted_response((base / 'response-1.sse').read_bytes())['name'] == 'request_user_input_async',
            'question response source')
    try:
        sdk.normalized(frames(base, 'rpc-in.jsonl'), native, allowed_warnings=(WARNING,))
    except ValueError as error:
        require(str(error) == 'SDK dialogue or extra message evidence', 'question audit rejection mismatch')
    else:
        raise ValueError('question unexpectedly accepted')
    records.append({'outputLabel': base.name, 'receiptSha256': receipt_hash, 'sourceCommit': value['sourceCommit'],
                    'diagnostic': {'status': 'async_question_stopped_and_rejected', 'localHttpRequests': 1,
                                   'forwardedToSdk': False, 'eligibleForMeasurement': False}})
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1')
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
    for name, raw in (('tests.stdout', process.stdout), ('tests.stderr', process.stderr)):
        cli.exclusive(OUTPUT / name, raw)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    require(process.returncode == 0 and matched is not None, 'full skills suite failed')
    after = source_guard.verify(ROOT, source, contract['sourceFiles'])
    require(before == after and source_guard.git(ROOT, 'status', '--porcelain') == b'', 'verification source drift')
    result = {'status': 'sdk_trace_connection_artifacts_rechecked', 'phase': 4, 'sourceCommit': source,
              'records': records, 'snapshotResourceCount': resource_count, 'originalHashesChecked': True,
              'newMockTrials': 2, 'newLocalHttpRequests': 3, 'paidModelCalls': 0,
              'independentReviewPerformed': False, 'providerParentBindingVerified': False,
              'eligibleForMeasurement': False, 'certifiesBehavior': False, 'certifiesSkillGate': False,
              'phaseComplete': False, 'sourceGuards': {'before': before, 'after': after},
              'tests': {'count': int(matched[1]), 'seconds': float(matched[2]), 'exitCode': process.returncode,
                        'command': command, 'stdoutSha256': sha(process.stdout), 'stderrSha256': sha(process.stderr)}}
    cli.exclusive(OUTPUT / 'summary.json', cli.encoded(result))
    print(json.dumps({'status': result['status'], 'sourceCommit': source, 'newMockTrials': 2,
                      'newLocalHttpRequests': 3, 'paidModelCalls': 0, 'tests': result['tests'],
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    run(args.source)
