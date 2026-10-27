"""複数exec捕捉の記録とP2再現を原bytes・確定Gitへ照合する。モデルや新試行はない。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('sequential_record_artifacts', Path(__file__).with_name('verify-artifacts.py'))
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)
trace, guard, operation, require = artifacts.trace, artifacts.guard, artifacts.operation, artifacts.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check_verification(meta, capture, count):
    base = ROOT / meta['outputRelativeRoot']
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'sequential verification symlink')
    raw = (base / 'summary.json').read_bytes()
    require(sha(raw) == meta['summarySha256'], 'sequential original verification summary')
    value = trace.strict_json(raw)
    require(value['status'] == 'sdk_sequential_capture_artifacts_rechecked' and
            value['sourceCommit'] == meta['sourceCommit'] and trace.json_equal(value['tests'], meta['tests']) and
            trace.json_equal(value['capture'], capture) and value['newMockTrialsDuringVerification'] == 0 and
            value['paidModelCalls'] == 0 and value['phaseComplete'] is False and
            value['eligibleForMeasurement'] is False, 'sequential original verification fields')
    stages = list(value['sourceGuards'].values())
    require(len(stages) == 2 and trace.json_equal(*stages) and stages[0]['observedHead'] == meta['sourceCommit'],
            'sequential verification guards')
    for name, digest in stages[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', meta['sourceCommit'] + ':' + name)) == digest, 'sequential verification Git')
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((base / name).read_bytes()) == meta['tests'][key], 'sequential original tests hash')
    match = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(match and int(match[1]) == meta['tests']['count'] == count and
            float(match[2]) == meta['tests']['seconds'] and meta['tests']['exitCode'] == 0, 'sequential actual tests terminal')


def check_reproductions():
    source = 'af35d0b7c9c9c1c6e1e69c76799e72efbecbbd81'
    old = {'__name__': 'historical_sequential_probe', '__file__': str(ROOT / 'evals/skills/routing/production_operation_probe.py')}
    exec(compile(guard.git(ROOT, 'show', source + ':evals/skills/routing/production_operation_probe.py'),
                 source + ':production_operation_probe.py', 'exec'), old)
    for mode in ('yielded', 'sequential'):
        base = ROOT / ('.venv/production-operation-yielded-read-09' if mode == 'yielded' else
                       '.venv/production-operation-sequential-read-10')
        original_requests = [trace.strict_json((base / f'request-{i}.json').read_bytes()) for i in (1, 2, 3)]
        original_host = artifacts.helper.frames(base, 'host.jsonl')
        responses = [(base / f'response-{i}.sse').read_bytes() for i in (1, 2, 3)]
        args = (operation.program('yielded-read', base),) if mode == 'yielded' else (base,)
        name = 'yielded_observation' if mode == 'yielded' else 'sequential_observation'
        mutations = ('read-arguments', 'list-arguments', 'spaced-duplicate') if mode == 'yielded' else (
            'list-arguments', 'spaced-duplicate')
        for mutation in mutations:
            requests, host = copy.deepcopy((original_requests, original_host))
            if mutation == 'read-arguments': host[1]['arguments'] = {'path': 'foreign.md'}
            elif mutation == 'list-arguments': host[0]['arguments'] = {'unknown': True}
            else:
                # 原出力を壊さずコピーだけを攻撃入力にする。SDK・HTTP・原ログの追加はない。
                requests[2]['input'][-1]['output'] = operation.yielded_output(requests[2],
                    'probe-wait' if mode == 'yielded' else 'probe-read') + '\n ' + json.dumps(
                        operation.output_objects(requests[2], 'probe-wait' if mode == 'yielded' else 'probe-read')[0])
            accepted = old[name](requests, host, responses, *args)
            require(len(accepted[0]) == 2, 'historical two-stage P2 reproduction')
            try:
                getattr(operation, name)(requests, host, responses, *args)
            except ValueError:
                pass
            else:
                raise ValueError('corrected two-stage P2 still accepted')


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    capture = artifacts.check_capture()
    require(trace.json_equal(capture, summary['capture']), 'sequential original capture replay')
    check_verification(summary['verification'], capture, 494)
    check_reproductions()
    spec = importlib.util.spec_from_file_location('sequential_original_reviews',
        ROOT / 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    reviews = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reviews)
    first = reviews.recheck_review(summary['independentReview'])
    require(first['verdict'] == 'findings' and len(first['findings']) == summary['reviewFindingCount'] == 2 and
            all(f['priority'] == 'P2' and f['path'] == 'evals/skills/routing/production_operation_probe.py'
                for f in first['findings']), 'sequential original P2 findings')
    tests, invocations = 494, 1
    if 'remediationVerification' in summary:
        check_verification(summary['remediationVerification'], capture, 496)
        tests = 496
    if 'finalIndependentReview' in summary:
        final = reviews.recheck_review(summary['finalIndependentReview'])
        require(summary['finalIndependentReview']['sourceCommit'] == summary['remediationVerification']['sourceCommit'],
                'sequential tested and reviewed source')
        source = summary['finalIndependentReview']['sourceCommit']
        contract = trace.strict_json(guard.git(ROOT, 'show', source + ':' + summary['remediationReviewContract']))
        first_source = summary['independentReview']['sourceCommit']
        previous_contract = trace.strict_json(guard.git(ROOT, 'show', first_source + ':' + summary['independentReviewContract']))
        require(contract['payloadFiles'] == previous_contract['payloadFiles'] and len(contract['payloadFiles']) == 8 and
                sum(len(guard.git(ROOT, 'show', source + ':' + p)) for p in contract['payloadFiles']) ==
                summary['finalPublicPayloadBytes'] == 130720, 'sequential authorized same eight payloads')
        require(final['verdict'] == 'pass' and final['findings'] == [] and
                summary['finalReviewFindingCount'] == 0 and summary['remediationIndependentlyPassed'] is True,
                'sequential corrected independent review')
        invocations += 1
    else:
        require(summary['remediationIndependentlyPassed'] is False, 'sequential unfinished correction')
    require(summary['mockTrials'] == 1 and summary['localHttpRequests'] == 3 and
            summary['paidModelCalls'] == summary['primaryModelTrajectories'] == summary['automaticRetries'] == 0 and
            summary['independentSolInvocations'] == invocations and summary['phaseComplete'] is False and
            summary['eligibleForMeasurement'] is False, 'sequential counters and scope')
    print(json.dumps({'status': 'recorded_sequential_capture_matches_original_bytes', 'tests': 494,
        'correctedSourceTests': tests, 'reviewFindingCount': 2, 'rawItems': 8, 'rawCompleted': 3,
        'traceRows': 24, 'observedCellIds': ['1', '2'], 'mockTrials': 1, 'localHttpRequests': 3,
        'independentSolInvocations': invocations, 'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
