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
OUTPUT = ROOT / '.venv/production-sdk-parent-links-verification-07'
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    run(parser.parse_args().source)
