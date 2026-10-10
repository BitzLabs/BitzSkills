"""固定親セル継続監査の記録を原bytesと確定Gitへ照合する。モデル・試行・書込みはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('yielded_parent_wrapper',
    ROOT / 'evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
trace, guard, require = wrapper.sdk.trace, wrapper.guard, wrapper.require


def sha(value):
    return hashlib.sha256(value).hexdigest()


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    meta = summary['verification']
    base = ROOT / meta['outputRelativeRoot']
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'yielded parent artifacts symlink')
    private = (base / 'summary.json').read_bytes()
    require(sha(private) == meta['summarySha256'], 'yielded parent original summary')
    value = trace.strict_json(private)
    require(value['status'] == 'sdk_yielded_parent_artifacts_rechecked' and
            value['sourceCommit'] == summary['sourceCommit'] == meta['sourceCommit'] and
            trace.json_equal(value['tests'], meta['tests']) and
            value['independentReviewPerformed'] is False and value['phaseComplete'] is False and
            value['eligibleForMeasurement'] is False, 'yielded parent original fields')
    stages = list(value['sourceGuards'].values())
    require(len(stages) == 2 and trace.json_equal(*stages) and stages[0]['observedHead'] == summary['sourceCommit'],
            'yielded parent source guards')
    for name, digest in stages[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', summary['sourceCommit'] + ':' + name)) == digest, 'yielded parent historical Git')
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((base / name).read_bytes()) == meta['tests'][key], 'yielded parent original tests')
    match = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(match and int(match[1]) == meta['tests']['count'] == 488 and
            float(match[2]) == meta['tests']['seconds'] and meta['tests']['exitCode'] == 0, 'yielded parent actual test terminal')
    replay = wrapper.check_yielded_capture()
    require(trace.json_equal(replay, value['capture']) and trace.json_equal(replay, summary['capture']),
            'yielded parent original capture replay')
    require(summary['newMockTrials'] == summary['newLocalHttpRequests'] == summary['paidModelCalls'] ==
            value['newMockTrials'] == value['newLocalHttpRequests'] == value['paidModelCalls'] == 0 and
            summary['independentSolInvocations'] == summary['primaryModelTrajectories'] == summary['automaticRetries'] == 0 and
            summary['independentReviewStatus'] == 'not_started_auto_review_rejected' and
            summary['phaseComplete'] is False and summary['eligibleForMeasurement'] is False, 'yielded parent counters/scope')
    contract = trace.strict_json(guard.git(ROOT, 'show', summary['sourceCommit'] + ':' + summary['independentReviewContract']))
    total = sum(len(guard.git(ROOT, 'show', summary['sourceCommit'] + ':' + p)) for p in contract['payloadFiles'])
    require(len(contract['payloadFiles']) == 6 and total == summary['publicPayloadBytes'] and
            contract['model'] == 'gpt-6.1-sol' and contract['maximumInvocations'] == 1 and
            contract['primaryModelTrajectories'] == contract['automaticRetries'] == 0,
            'yielded parent finite pending review')
    print(json.dumps({'status': 'recorded_yielded_parent_results_match_original_bytes', 'tests': 488,
                      'nativeChildren': 2, 'traceRows': 24, 'cellId': '1', 'newMockTrials': 0,
                      'newLocalHttpRequests': 0, 'independentSolInvocations': 0,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
