"""カナリア実行器の準備失敗・静的検分を原出力へ照合する。一次成功を認定しない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace
import production_ledger as ledger
import source_guard as guard


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    review = module('canary_static_review', 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    prepare = module('canary_static_preparation', 'evals/skills/results/2026-10-10-production-canary-design/verify-recorded-results.py')
    for stage in public['staticReviewStages']:
        prepare.check_stage(stage, review)
    for row in public['failedPreparations']:
        trace.require(re.fullmatch(r'\.venv/production-canary-capture-check-[0-9]+', row['outputRelativeRoot']), 'private output root')
        base = ROOT / row['outputRelativeRoot']
        ledger.safe_tree(base)
        raw = (base / 'summary.json').read_bytes()
        trace.require(hashlib.sha256(raw).hexdigest() == row['summarySha256'], 'failed preparation drift')
        original = trace.strict_json(raw)
        trace.require(original['sourceCommit'] == row['sourceCommit'] and original['contractPath'] == row['contractPath'] and
                      original['tests']['exitCode'] == row['testExitCode'] == 1 and
                      original['status'] == 'canary_design_preparation_stopped', 'original failed outcome')
        stdout, stderr = [(base / name).read_bytes() for name in ('tests.stdout', 'tests.stderr')]
        trace.require(hashlib.sha256(stdout).hexdigest() == original['tests']['stdoutSha256'] and
                      hashlib.sha256(stderr).hexdigest() == original['tests']['stderrSha256'] == row['stderrSha256'], 'failed original streams')
        match = re.search(rb'Ran ([0-9]+) tests in ([0-9.]+)s\s+FAILED \(errors=([0-9]+)\)', stderr)
        trace.require(match is not None and int(match[1]) == row['testCount'] and float(match[2]) == row['testSeconds'] and
                      int(match[3]) == row['testErrors'], 'failed original test counts')
        contract = trace.strict_json(guard.git(ROOT, 'show', row['sourceCommit'] + ':' + row['contractPath']))
        expected = {p: hashlib.sha256(guard.git(ROOT, 'show', row['sourceCommit'] + ':' + p)).hexdigest() for p in contract['sourceFiles']}
        before, after = original['sourceGuards']['before'], original['sourceGuards']['after']
        trace.require(trace.json_equal(before, after) and before['sourceCommit'] == before['observedHead'] == row['sourceCommit'] and
                      before['sourceSha256'] == expected, 'failed fixed source guards')
    trace.require(len(public['staticReviewStages']) == public['staticSolInvocations'] and
                  public['primaryModelTrajectories'] == public['primaryIndependentReviews'] == 0 and
                  all(public[k] is False for k in ['certifiesBehavior', 'certifiesSkillGate', 'phaseComplete']), 'limited scope')
    print(json.dumps(dict(status='recorded_canary_capture_preparation_matches_original_bytes',
                         staticSolInvocations=public['staticSolInvocations'], primaryModelTrajectories=0, phaseComplete=False)))


if __name__ == '__main__':
    run()
