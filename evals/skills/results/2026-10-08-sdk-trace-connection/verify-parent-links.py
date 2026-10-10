"""既存CLIの原telemetryで固定1execの親子IDを照合する。モデルを起動しない。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

SPEC = importlib.util.spec_from_file_location('sdk_artifact_verifier', Path(__file__).with_name('verify-artifacts.py'))
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
ROOT, sdk, guard, cli = helper.ROOT, helper.sdk, helper.source_guard, helper.cli
SOURCE = '558104ec2557f735658f17ef3a8d097167f3c0d3'
RECEIPT_SHA = '4c60bf95023730815eba9a66aef7e2121d212a3b40ad60dda3a3aac54f5bb311'
CONTRACT = 'evals/skills/routing/production-operation-probe-v0.6.json'
OUTPUT = ROOT / '.venv/production-sdk-parent-links-verification-19'
require = sdk.require


def run(source):
    require(guard.git(ROOT, 'status', '--porcelain') == b'' and
            guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean fixed HEAD required')
    original_contract = sdk.trace.strict_json(guard.git(ROOT, 'show', SOURCE + ':' + CONTRACT))
    names = original_contract['sourceFiles'] + [str(Path(__file__).relative_to(ROOT))]
    before = guard.verify(ROOT, source, names)
    require(not any(p.is_symlink() for p in (OUTPUT, *OUTPUT.parents)), 'output symlink')
    OUTPUT.mkdir(mode=0o700)
    raw, resource_count = helper.check_snapshot(original_contract)
    base = ROOT / '.venv/production-operation-read-06'
    value, receipt_hash = helper.receipt(base, expected_sha=RECEIPT_SHA)
    require(value['sourceCommit'] == SOURCE and value['hostEventCount'] == 2 and
            value['localHttpRequestCount'] == 2 and all(value['isolationChecks'].values()), 'parent probe binding')
    incoming, outgoing = [helper.frames(base, name) for name in ('rpc-in.jsonl', 'rpc-out.jsonl')]
    diagnostic = sdk.diagnose_exchange(raw, helper.frames(base, 'host.jsonl'), incoming, outgoing,
        [helper.read(str((base / f'request-{i}.json').relative_to(ROOT))) for i in (1, 2)],
        [(base / f'response-{i}.sse').read_bytes() for i in (1, 2)],
        expected_program=helper.operation.program('read', base), expected_final_text='LOCAL_SIMULATION_ONLY',
        actual_exit_code=value['runtime']['exitCode'], allowed_warnings=(helper.WARNING,))
    # 部分列ではなく、指定targetの全原行と選択ログを完全照合する。
    events = sdk.complete_trace_projection((base / 'runtime-stderr.bin').read_bytes(),
                                           (base / 'trace-safe.jsonl').read_bytes())
    links = sdk.audit_parent_links(events, outgoing, diagnostic['providerCallId'])
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1')
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
    cli.exclusive(OUTPUT / 'tests.stdout', process.stdout)
    cli.exclusive(OUTPUT / 'tests.stderr', process.stderr)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    require(process.returncode == 0 and matched is not None, 'full suite failed')
    after = guard.verify(ROOT, source, names)
    require(before == after and guard.git(ROOT, 'status', '--porcelain') == b'', 'verification source drift')
    result = {'status': 'sdk_parent_links_artifacts_rechecked', 'phase': 4, 'sourceCommit': source,
              'probeSourceCommit': SOURCE, 'receiptSha256': receipt_hash, 'snapshotResourceCount': resource_count,
              'originalHashesChecked': True, 'traceRowsMatchedOriginalBytes': True,
              'allTargetTraceRowsPreserved': True, 'diagnostic': diagnostic,
              'parentLinks': links, 'paidModelCalls': 0, 'newMockTrials': 1, 'newLocalHttpRequests': 2,
              'independentReviewPerformed': False, 'eligibleForMeasurement': False, 'phaseComplete': False,
              'sourceGuards': {'before': before, 'after': after}, 'tests': {
                  'count': int(matched[1]), 'seconds': float(matched[2]), 'exitCode': process.returncode,
                  'command': command, 'stdoutSha256': helper.sha(process.stdout), 'stderrSha256': helper.sha(process.stderr)}}
    cli.exclusive(OUTPUT / 'summary.json', cli.encoded(result))
    print(json.dumps({'status': result['status'], 'sourceCommit': source, 'probeSourceCommit': SOURCE,
                      'parentLinks': links, 'paidModelCalls': 0, 'tests': result['tests']}, ensure_ascii=False))


def check_raw_capture(base, *, legacy=False):
    spec = importlib.util.spec_from_file_location('raw_capture_components',
        Path(__file__).parent.parent / '2026-10-09-sdk-raw-response-capture/verify-artifacts.py')
    raw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(raw)
    label, expected_source, expected_sha = (
        ('production-operation-read-07', 'c026dabede3e40bc010f895a431050ccdae47a9c',
         '6436ca1ec70adc74a9a3da6b4a54d0a04aaf57ab09f8f1e7ec5b24ce99ac72e3') if legacy else
        ('production-operation-read-08', 'e23222215a79238a082e15e0751b331955f42aa0',
         '985a5bdecffb4cd4408ea9b8a06ffe5173971a334328b68ee82d009e33fa0822'))
    require(base == ROOT / '.venv' / label, 'fixed raw capture path')
    value, receipt_hash = helper.receipt(base, expected_sha=expected_sha)
    require(value['sourceCommit'] == expected_source, 'fixed raw capture source')
    audit = raw.check_capture(base, receipt_hash, legacy=legacy)
    contract = helper.read(str((base / 'contract.json').relative_to(ROOT)))
    manifest, _ = helper.check_snapshot(contract)
    supplied = (base / 'sdk-turn-notifications.jsonl').read_bytes()
    delivered = raw.legacy_sdk_records(supplied) if legacy else [sdk.trace.strict_json(l) for l in supplied.splitlines()]
    diagnostic = sdk.diagnose_raw_exchange(manifest, helper.frames(base, 'host.jsonl'),
        helper.frames(base, 'rpc-in.jsonl'), helper.frames(base, 'rpc-out.jsonl'),
        [helper.read(str((base / f'request-{i}.json').relative_to(ROOT))) for i in (1, 2)],
        [(base / f'response-{i}.sse').read_bytes() for i in (1, 2)],
        sdk_raw_notifications=[n for n in delivered if n['method'] in sdk.RAW_METHODS],
        expected_program=helper.operation.program('read', base), expected_final_text='LOCAL_SIMULATION_ONLY',
        actual_exit_code=value['runtime']['exitCode'], allowed_warnings=(helper.WARNING,), diagnostic_date='2026-10-09')
    return {'probeSourceCommit': expected_source, 'receiptSha256': receipt_hash,
            'artifactAudit': audit, 'rawExchangeAudit': diagnostic}


def run_raw(source):
    require(guard.git(ROOT, 'status', '--porcelain') == b'' and
            guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean fixed HEAD required')
    contract = sdk.trace.strict_json(guard.git(ROOT, 'show',
        'e23222215a79238a082e15e0751b331955f42aa0:evals/skills/routing/production-operation-probe-v0.8.json'))
    names = list(dict.fromkeys(contract['sourceFiles'] + [str(Path(__file__).relative_to(ROOT)),
        'evals/skills/routing/production_sdk_trace.py', 'evals/skills/routing/production_trace.py',
        'tests/skills/test_production_sdk_trace.py', 'tests/skills/test_production_trace.py',
        'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py']))
    before = guard.verify(ROOT, source, names)
    output = ROOT / '.venv/production-sdk-raw-exchange-verification-01'
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'raw audit output symlink')
    output.mkdir(mode=0o700)
    captures = [check_raw_capture(ROOT / '.venv' / name, legacy=legacy) for name, legacy in
                [('production-operation-read-07', True), ('production-operation-read-08', False)]]
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1'))
    cli.exclusive(output / 'tests.stdout', process.stdout)
    cli.exclusive(output / 'tests.stderr', process.stderr)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    require(process.returncode == 0 and matched is not None, 'raw audit full suite failed')
    after = guard.verify(ROOT, source, names)
    require(before == after and guard.git(ROOT, 'status', '--porcelain') == b'', 'raw audit source drift')
    value = {'status': 'sdk_raw_exchange_artifacts_rechecked', 'phase': 4, 'sourceCommit': source,
             'captures': captures, 'newMockTrials': 0, 'newLocalHttpRequests': 0, 'paidModelCalls': 0,
             'independentReviewPerformed': False, 'eligibleForMeasurement': False, 'phaseComplete': False,
             'sourceGuards': {'before': before, 'after': after}, 'tests': {
                 'count': int(matched[1]), 'seconds': float(matched[2]), 'exitCode': process.returncode,
                 'command': command, 'stdoutSha256': helper.sha(process.stdout), 'stderrSha256': helper.sha(process.stderr)}}
    cli.exclusive(output / 'summary.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'captures', 'sourceGuards'}}, ensure_ascii=False))


def check_yielded_capture():
    spec = importlib.util.spec_from_file_location('yielded_original_artifacts',
        ROOT / 'evals/skills/results/2026-10-10-sdk-yielded-cell/verify-recorded-results.py')
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    artifact_audit = capture.check_capture()
    base = capture.BASE
    outgoing = helper.frames(base, 'rpc-out.jsonl')
    events = sdk.complete_trace_projection((base / 'runtime-stderr.bin').read_bytes(),
                                           (base / 'trace-safe.jsonl').read_bytes())
    links = sdk.audit_yielded_parent_links(events, outgoing, 'probe-call', 'probe-wait', '1')
    return {'probeSourceCommit': capture.SOURCE, 'receiptSha256': capture.RECEIPT_SHA,
            'artifactAudit': artifact_audit, 'parentLinks': links,
            'certifiesNativeProvider': False, 'certifiesSkillGate': False, 'eligibleForMeasurement': False}


def run_yielded(source, *, remediation=False):
    require(guard.git(ROOT, 'status', '--porcelain') == b'' and
            guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean yielded parent HEAD')
    contract_name = 'evals/skills/routing/sdk-trace-review-v0.21.json' if remediation else 'evals/skills/routing/sdk-trace-review-v0.20.json'
    contract = sdk.trace.strict_json(guard.git(ROOT, 'show', source + ':' + contract_name))
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    capture = check_yielded_capture()
    output = ROOT / ('.venv/production-sdk-yielded-parent-verification-02' if remediation else
                     '.venv/production-sdk-yielded-parent-verification-01')
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'yielded parent output symlink')
    output.mkdir(mode=0o700)
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1'))
    cli.exclusive(output / 'tests.stdout', process.stdout)
    cli.exclusive(output / 'tests.stderr', process.stderr)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    require(process.returncode == 0 and matched is not None, 'yielded parent full suite failed')
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    require(before == after and guard.git(ROOT, 'status', '--porcelain') == b'', 'yielded parent source drift')
    value = {'status': 'sdk_yielded_parent_artifacts_rechecked', 'sourceCommit': source, 'capture': capture,
             'newMockTrials': 0, 'newLocalHttpRequests': 0, 'paidModelCalls': 0,
             'independentReviewPerformed': False, 'eligibleForMeasurement': False, 'phaseComplete': False,
             'sourceGuards': {'before': before, 'after': after}, 'tests': {
                 'count': int(matched[1]), 'seconds': float(matched[2]), 'exitCode': process.returncode,
                 'command': command, 'stdoutSha256': helper.sha(process.stdout), 'stderrSha256': helper.sha(process.stderr)}}
    cli.exclusive(output / 'summary.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'capture', 'sourceGuards'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--raw-exchange', action='store_true')
    mode.add_argument('--yielded-parent', action='store_true')
    mode.add_argument('--yielded-parent-remediation', action='store_true')
    args = parser.parse_args()
    if args.yielded_parent_remediation:
        run_yielded(args.source, remediation=True)
    else:
        (run_yielded if args.yielded_parent else run_raw if args.raw_exchange else run)(args.source)
