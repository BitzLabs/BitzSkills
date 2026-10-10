"""固定親セル継続監査の記録を原bytesと確定Gitへ照合する。モデル・試行・書込みはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import copy

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('yielded_parent_wrapper',
    ROOT / 'evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
trace, guard, require = wrapper.sdk.trace, wrapper.guard, wrapper.require


def sha(value):
    return hashlib.sha256(value).hexdigest()


def check_verification(meta, capture, count):
    base = ROOT / meta['outputRelativeRoot']
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'yielded parent artifacts symlink')
    private = (base / 'summary.json').read_bytes()
    require(sha(private) == meta['summarySha256'], 'yielded parent original summary')
    value = trace.strict_json(private)
    require(value['status'] == 'sdk_yielded_parent_artifacts_rechecked' and
            value['sourceCommit'] == meta['sourceCommit'] and
            trace.json_equal(value['tests'], meta['tests']) and
            value['independentReviewPerformed'] is False and value['phaseComplete'] is False and
            value['eligibleForMeasurement'] is False, 'yielded parent original fields')
    stages = list(value['sourceGuards'].values())
    require(len(stages) == 2 and trace.json_equal(*stages) and stages[0]['observedHead'] == meta['sourceCommit'],
            'yielded parent source guards')
    for name, digest in stages[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', meta['sourceCommit'] + ':' + name)) == digest, 'yielded parent historical Git')
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((base / name).read_bytes()) == meta['tests'][key], 'yielded parent original tests')
    match = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(match and int(match[1]) == meta['tests']['count'] == count and
            float(match[2]) == meta['tests']['seconds'] and meta['tests']['exitCode'] == 0, 'yielded parent actual test terminal')
    replay = wrapper.check_yielded_capture()
    require(trace.json_equal(replay, value['capture']) and trace.json_equal(replay, capture),
            'yielded parent original capture replay')
    require(value['newMockTrials'] == value['newLocalHttpRequests'] == value['paidModelCalls'] == 0,
            'yielded parent original counters')


def check_reproduction():
    source = '5f874622d77fa10978a2ab56055539af9d28abec'
    code = guard.git(ROOT, 'show', source + ':evals/skills/routing/production_sdk_trace.py')
    original = {'__name__': 'historical_yielded_parent'}
    exec(compile(code, source + ':production_sdk_trace.py', 'exec'), original)
    base = ROOT / '.venv/production-operation-yielded-read-09'
    frames = wrapper.helper.frames(base, 'rpc-out.jsonl')
    events = wrapper.sdk.complete_trace_projection((base / 'runtime-stderr.bin').read_bytes(),
                                                   (base / 'trace-safe.jsonl').read_bytes())
    changed = copy.deepcopy(events)
    api = [e for e in changed if e['fields']['event.name'] == 'codex.api_request'][1]
    api['fields']['turn_id'] = 'other'
    require(original['audit_yielded_parent_links'](changed, frames, 'probe-call', 'probe-wait', '1')['status'] ==
            'scripted_yielded_parent_cell_child_ids_matched', 'foreign API turn historical reproduction')
    try:
        wrapper.sdk.audit_yielded_parent_links(changed, frames, 'probe-call', 'probe-wait', '1')
    except ValueError as error:
        require(str(error) == 'neutral telemetry turn contradiction', 'foreign API turn rejection reason')
    else:
        raise ValueError('foreign API turn accepted after correction')


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    check_verification(summary['verification'], summary['capture'], 488)
    check_reproduction()
    require(summary['newMockTrials'] == summary['newLocalHttpRequests'] == summary['paidModelCalls'] ==
            summary['primaryModelTrajectories'] == summary['automaticRetries'] == 0 and
            summary['phaseComplete'] is False and summary['eligibleForMeasurement'] is False, 'yielded parent counters/scope')
    review = summary['independentReview']
    contract = trace.strict_json(guard.git(ROOT, 'show', review['sourceCommit'] + ':' + review['contractPath']))
    total = sum(len(guard.git(ROOT, 'show', review['sourceCommit'] + ':' + p)) for p in contract['payloadFiles'])
    require(len(contract['payloadFiles']) == 6 and total == summary['publicPayloadBytes'] and
            contract['model'] == 'gpt-6.1-sol' and contract['maximumInvocations'] == 1 and
            contract['primaryModelTrajectories'] == contract['automaticRetries'] == 0,
            'yielded parent finite original review')
    spec = importlib.util.spec_from_file_location('yielded_parent_review_artifacts',
        ROOT / 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    reviews = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reviews)
    first = reviews.recheck_review(review)
    require(review['status'] == 'review_findings' and len(first['findings']) == summary['reviewFindingCount'] == 1 and
            first['findings'][0]['priority'] == 'P2' and first['findings'][0]['path'] ==
            'evals/skills/routing/production_sdk_trace.py', 'yielded parent original finding')
    invocations = 1
    tests = 488
    if 'remediationVerification' in summary:
        check_verification(summary['remediationVerification'], summary['capture'], 489)
        tests = 489
    if 'finalIndependentReview' in summary:
        final = reviews.recheck_review(summary['finalIndependentReview'])
        corrected_source = summary['remediationVerification']['sourceCommit']
        review_source = summary['finalIndependentReview']['sourceCommit']
        final_contract = trace.strict_json(guard.git(ROOT, 'show', review_source + ':' + summary['remediationReviewContract']))
        payloads = [guard.git(ROOT, 'show', review_source + ':' + p) for p in final_contract['payloadFiles']]
        require(final_contract['payloadFiles'] == contract['payloadFiles'] and
                sum(map(len, payloads)) == summary['finalPublicPayloadBytes'] == 192114 and
                all(raw == guard.git(ROOT, 'show', corrected_source + ':' + p) for p, raw in
                    zip(final_contract['payloadFiles'], payloads)), 'corrected tested and reviewed payloads differ')
        require(final['verdict'] == 'pass' and final['findings'] == [] and
                summary['finalIndependentReview']['status'] == 'static_review_passed' and
                summary['independentReviewStatus'] == 'static_review_passed' and
                summary['remediationIndependentlyPassed'] is True, 'yielded parent corrected independent review')
        require(summary['finalReviewFindingCount'] == 0, 'corrected finding count')
        invocations += 1
    else:
        require(summary['independentReviewStatus'] == 'review_findings' and
                summary['remediationIndependentlyPassed'] is False, 'yielded parent unfinished correction')
    require(summary['independentSolInvocations'] == invocations, 'yielded parent original invocation count')
    print(json.dumps({'status': 'recorded_yielded_parent_results_match_original_bytes', 'tests': 488,
                      'correctedSourceTests': tests, 'reviewFindingCount': 1,
                      'nativeChildren': 2, 'traceRows': 24, 'cellId': '1', 'newMockTrials': 0,
                      'newLocalHttpRequests': 0, 'independentSolInvocations': invocations,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
