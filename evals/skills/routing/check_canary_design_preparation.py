"""確定した公開設計の入力・過去の原結果・全試験を照合する。有料モデル起動0。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import production_cli_probe as cli
import production_trace as trace
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.24.json'
OUTPUT = '.venv/production-canary-design-check-01'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(source, remediation=False, final_remediation=False):
    trace.require(guard.git(ROOT, 'status', '--porcelain') == b'' and
                  guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip() == source, 'clean fixed HEAD required')
    contract_name = ('evals/skills/routing/sdk-trace-review-v0.26.json' if final_remediation else
                     'evals/skills/routing/sdk-trace-review-v0.25.json' if remediation else CONTRACT)
    output_name = ('.venv/production-canary-design-check-03' if final_remediation else
                   '.venv/production-canary-design-check-02' if remediation else OUTPUT)
    contract = trace.strict_json(guard.git(ROOT, 'show', source + ':' + contract_name))
    before = guard.verify(ROOT, source, contract['sourceFiles'])
    trace.require(contract['maximumInvocations'] == 1 and contract['automaticRetries'] == 0 and
                  contract['primaryModelTrajectories'] == 0, 'finite static review required')
    trace.require(len(contract['payloadFiles']) == len(set(contract['payloadFiles'])) == 6 and
                  set(contract['payloadFiles']) <= set(contract['sourceFiles']), 'public payload inventory')
    inventory = []
    for name in contract['payloadFiles']:
        raw = guard.git(ROOT, 'show', source + ':' + name)
        inventory.append(dict(path=name, bytes=len(raw), sha256=sha(raw)))
    previous = contract['previousReview']
    old = ROOT / previous['outputRelativeRoot']
    trace.require(not any(p.is_symlink() for p in (old, *old.parents)), 'previous output symlink')
    for name, key in [('receipt.json', 'receiptSha256'), ('response.json', 'responseSha256')]:
        trace.require(sha((old / name).read_bytes()) == previous[key], 'previous artifact drift')
    trace.require(trace.strict_json((old / 'receipt.json').read_bytes())['sourceCommit'] == previous['sourceCommit'],
                  'previous source mismatch')
    output = ROOT / output_name
    trace.require(not any(p.is_symlink() for p in (output, *output.parents)), 'output symlink')
    output.mkdir(mode=0o700)
    command = ['uv', '--cache-dir', str(ROOT / '.venv/uv-cache'), 'run', '--offline', '--project',
               'plugins/bitz-core', '--with', 'jsonschema==4.23.0', 'python', '-B', '-m', 'unittest',
               'discover', '-s', 'tests/skills', '-p', 'test_*.py']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/bitz-core/src'), PYTHONDONTWRITEBYTECODE='1'))
    cli.exclusive(output / 'tests.stdout', process.stdout)
    cli.exclusive(output / 'tests.stderr', process.stderr)
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', process.stderr)
    after = guard.verify(ROOT, source, contract['sourceFiles'])
    passed = process.returncode == 0 and matched is not None and before == after and guard.git(ROOT, 'status', '--porcelain') == b''
    value = dict(status='canary_design_preparation_checked' if passed else 'canary_design_preparation_stopped',
                 sourceCommit=source, contractPath=contract_name, outputRelativeRoot=output_name,
                 sourceGuards=dict(before=before, after=after), payloadInventory=inventory,
                 payloadBytes=sum(item['bytes'] for item in inventory),
                 previousPinsMatched=True, independentReviewPerformed=False,
                 primaryModelTrajectories=0, independentSolInvocations=0, automaticRetries=0,
                 eligibleForMeasurement=False, phaseComplete=False,
                 tests=dict(command=command, count=int(matched[1]) if matched else None,
                            seconds=float(matched[2]) if matched else None, exitCode=process.returncode,
                            stdoutSha256=sha(process.stdout), stderrSha256=sha(process.stderr)))
    cli.exclusive(output / 'summary.json', cli.encoded(value))
    print(json.dumps({key: item for key, item in value.items() if key not in {'sourceGuards', 'payloadInventory'}}, ensure_ascii=False))
    trace.require(passed, 'canary design preparation failed; original streams retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--remediation', action='store_true')
    mode.add_argument('--final-remediation', action='store_true')
    args = parser.parse_args()
    run(args.source, remediation=args.remediation, final_remediation=args.final_remediation)
