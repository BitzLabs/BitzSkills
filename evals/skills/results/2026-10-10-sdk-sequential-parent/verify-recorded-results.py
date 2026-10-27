"""固定2exec/2cellの親監査の記録を原bytesと確定Gitへ照合する。モデル・試行・書込みはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import copy

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('sequential_parent_wrapper',
    ROOT / 'evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
trace, guard, require = wrapper.sdk.trace, wrapper.guard, wrapper.require


def sha(value):
    return hashlib.sha256(value).hexdigest()


def check_verification(meta, capture, count):
    base = ROOT / meta['outputRelativeRoot']
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'sequential parent artifacts symlink')
    private = (base / 'summary.json').read_bytes()
    require(sha(private) == meta['summarySha256'], 'sequential parent original summary')
    value = trace.strict_json(private)
    require(value['status'] == 'sdk_sequential_parent_artifacts_rechecked' and
            value['sourceCommit'] == meta['sourceCommit'] and
            trace.json_equal(value['tests'], meta['tests']) and
            value['independentReviewPerformed'] is False and value['phaseComplete'] is False and
            value['eligibleForMeasurement'] is False, 'sequential parent original fields')
    stages = list(value['sourceGuards'].values())
    require(len(stages) == 2 and trace.json_equal(*stages) and stages[0]['observedHead'] == meta['sourceCommit'],
            'sequential parent source guards')
    for name, digest in stages[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', meta['sourceCommit'] + ':' + name)) == digest, 'sequential parent historical Git')
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((base / name).read_bytes()) == meta['tests'][key], 'sequential parent original tests')
    match = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(match and int(match[1]) == meta['tests']['count'] == count and
            float(match[2]) == meta['tests']['seconds'] and meta['tests']['exitCode'] == 0, 'sequential parent actual test terminal')
    replay = wrapper.check_sequential_capture()
    require(trace.json_equal(replay, value['capture']) and trace.json_equal(replay, capture),
            'sequential parent original capture replay')
    require(value['newMockTrials'] == value['newLocalHttpRequests'] == value['paidModelCalls'] == 0,
            'sequential parent original counters')


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    require(summary['sourceCommit'] == summary['verification']['sourceCommit'] ==
            summary['independentReview']['sourceCommit'], 'sequential tested and reviewed source')
    check_verification(summary['verification'], summary['capture'], 501)
    spec = importlib.util.spec_from_file_location('sequential_parent_original_review',
        ROOT / 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    reviews = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reviews)
    response = reviews.recheck_review(summary['independentReview'])
    require(response['verdict'] == 'pass' and response['findings'] == [] and
            summary['reviewFindingCount'] == 0, 'sequential parent independent original response')
    contract = trace.strict_json(guard.git(ROOT, 'show', summary['sourceCommit'] + ':' +
                                         summary['independentReview']['contractPath']))
    require(len(contract['payloadFiles']) == 6 and sum(len(guard.git(ROOT, 'show',
            summary['sourceCommit'] + ':' + p)) for p in contract['payloadFiles']) ==
            summary['publicPayloadBytes'] == 202879, 'sequential parent authorized public payload')
    links = summary['capture']['parentLinks']
    require(links['parentCallIds'] == ['probe-call', 'probe-read'] and links['cellIds'] == ['1', '2'] and
            links['certifiesProviderWireBodies'] is False and
            links['certifiesArbitraryMultipleOrYieldedCells'] is False and
            links['eligibleForMeasurement'] is False, 'sequential parent fixed scope')
    require(summary['newMockTrials'] == summary['newLocalHttpRequests'] == summary['paidModelCalls'] ==
            summary['primaryModelTrajectories'] == summary['automaticRetries'] == 0 and
            summary['independentSolInvocations'] == 1 and summary['phaseComplete'] is False and
            summary['eligibleForMeasurement'] is False, 'sequential parent counters')
    print(json.dumps({'status': 'recorded_sequential_parent_matches_original_bytes', 'tests': 501,
                      'nativeChildren': 2, 'traceRows': 24, 'cellIds': ['1', '2'], 'newMockTrials': 0,
                      'newLocalHttpRequests': 0, 'independentSolInvocations': 1, 'reviewFindings': 0,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
