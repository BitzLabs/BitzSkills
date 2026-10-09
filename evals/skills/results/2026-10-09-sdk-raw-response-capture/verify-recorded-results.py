"""raw通知捕捉の公開記録を原bytes/Gitへ再照合する。課金呼出し・書込みはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace
import source_guard as guard
import run_sdk_trace_review as review
import production_operation_probe as operation
spec = importlib.util.spec_from_file_location('raw_capture_verifier', Path(__file__).with_name('verify-artifacts.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
require = trace.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    require(summary['phase'] == 4 and not summary['phaseComplete'] and
            not summary['eligibleForMeasurement'] and not summary['independentRawCaptureReviewPassed'], 'scope')
    meta = summary['verification']
    base = ROOT / meta['outputRelativeRoot']
    raw = (base / 'summary.json').read_bytes()
    require(sha(raw) == meta['summarySha256'], 'verification original hash')
    value = trace.strict_json(raw)
    require(trace.json_equal({k: v for k, v in value.items() if k != 'sourceGuards'}, meta['result']) and
            value['sourceCommit'] == summary['sourceCommit'], 'verification fields/source')
    guards = list(value['sourceGuards'].values())
    require(guards and all(trace.json_equal(g, guards[0]) for g in guards), 'source guard drift')
    for name, expected in guards[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == expected, 'historical Git hash')
    tests = value['tests']
    for name, key in (('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')):
        require(sha((base / name).read_bytes()) == tests[key], 'original test bytes')
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(matched and int(matched[1]) == tests['count'] == 465 and float(matched[2]) == tests['seconds'] and
            tests['exitCode'] == 0, 'actual test terminal')
    for i, trial in enumerate(summary['captureTrials']):
        base = ROOT / trial['outputRelativeRoot']
        original, digest = verify.helper.receipt(base, expected_sha=trial['receiptSha256'])
        require(all(trace.json_equal(original[k], v) for k, v in trial['receipt'].items()), 'capture receipt fields')
        result = verify.check_capture(base, digest, legacy=(i == 0))
        require(trace.json_equal(result, value['previousCapture' if i == 0 else 'capture']), 'capture correlations')
        incoming = [trace.strict_json(line) for line in (base / 'rpc-in.jsonl').read_bytes().splitlines()]
        outgoing = [trace.strict_json(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
        ids = {}
        for method, key in [('thread/start', 'thread'), ('turn/start', 'turn')]:
            request = next(f for f in incoming if f.get('method') == method)
            reply = next(f for f in outgoing if f.get('id') == request['id'])
            ids[key] = reply['result'][key]['id']
        require(operation.terminal_matches(outgoing, ids['thread'], ids['turn']) == (True, True),
                'original capture corrected terminal predicate')
    pending = summary['independentReview']
    contract = trace.strict_json(guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + pending['contractPath']))
    require(pending['actualInvocations'] == 1 and
            pending['maximumInvocations'] == contract['maximumInvocations'] == 1 and
            pending['automaticRetries'] == contract['automaticRetries'] == 0 and
            pending['additionalDelegation'] == pending['primaryModelTrajectories'] == 0, 'pending finite review')
    require(contract['payloadFiles'] == [f['path'] for f in pending['payloadFiles']], 'pending payload paths')
    total = 0
    for item in pending['payloadFiles']:
        raw = guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + item['path'])
        require(len(raw) == item['bytes'] and
                sha(raw) == item['sha256'], 'pending payload bytes')
        total += len(raw)
    require(total == pending['payloadBytes'] and len(pending['payloadFiles']) == 8, 'payload count')
    review_base = ROOT / pending['outputRelativeRoot']
    receipt_raw = (review_base / 'receipt.json').read_bytes()
    require(sha(receipt_raw) == pending['receiptSha256'], 'review original receipt')
    receipt = trace.strict_json(receipt_raw)
    require(receipt['status'] == pending['status'] == 'review_findings' and receipt['exitCode'] == 0 and
            receipt['timedOut'] is False and receipt['sourceCommit'] == pending['sourceCommit'] and
            receipt['independentReviewerSolInvocations'] == 1 and receipt['primaryModelTrajectories'] == 0 and
            receipt['automaticRetries'] == 0, 'review terminal')
    for name, key in [('trace.jsonl', 'stdoutSha256'), ('stderr.bin', 'stderrSha256'),
                      ('prompt.txt', 'promptSha256'), ('response.json', 'responseSha256')]:
        require(sha((review_base / name).read_bytes()) == receipt[key], 'review original bytes')
    schema = guard.git(ROOT, 'show', pending['sourceCommit'] + ':evals/skills/routing/sdk-trace-review.schema.json')
    require((review_base / 'schema.json').read_bytes() == schema, 'review schema')
    response, usage, warnings = review.review_response(
        review_base, (review_base / 'trace.jsonl').read_bytes(), pending['sourceCommit'], schema, contract)
    require(trace.json_equal(response['findings'], receipt['findings']) and
            trace.json_equal(usage, receipt['usage']) and trace.json_equal(usage, summary['reviewUsage']) and
            warnings == receipt['acceptedStartupWarningHashes'] and
            receipt['responseSha256'] == pending['responseSha256'], 'review original response fields')
    review_guards = list(receipt['sourceGuards'].values())
    require(len(review_guards) == 3 and all(trace.json_equal(g, review_guards[0]) for g in review_guards), 'review guard drift')
    for name, expected in review_guards[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + name)) == expected and
                sha(guard.git(ROOT, 'show', review_guards[0]['observedHead'] + ':' + name)) == expected,
                'review historical source bytes')
    reservation = trace.strict_json((review_base / 'reservation.json').read_bytes())
    invocation = trace.strict_json((review_base / 'invocation.json').read_bytes())
    require(reservation['sourceCommit'] == invocation['sourceCommit'] == pending['sourceCommit'] and
            reservation['attemptReserved'] == reservation['maximumInvocations'] == invocation['maximumInvocations'] == 1 and
            reservation['automaticRetry'] is False and invocation['model'] == contract['model'] and
            invocation['promptSha256'] == receipt['promptSha256'], 'review finite reservation')
    require(summary['newRawMockTrials'] == 2 and summary['newLocalMockHttpRequests'] == 4 and
            summary['rawMockPaidModelCalls'] == 0 and summary['newRawCaptureIndependentReviewerSolInvocations'] == 1,
            'capture counters')
    counterexample = [{'method': 'turn/completed', 'params': {'threadId': 'other',
                      'turn': {'id': 'other-turn', 'status': 'completed', 'error': {'message': 'failed'}}}},
                      {'method': 'item/completed', 'params': {'threadId': 'other', 'turnId': 'other-turn',
                      'item': {'type': 'agentMessage', 'phase': 'final_answer', 'text': 'LOCAL_SIMULATION_ONLY'}}}]
    require(operation.terminal_matches(counterexample, 'thread', 'turn') == (False, False), 'P2 regression')
    local = summary['localRemediation'].get('verification')
    if local is not None:
        local_base = ROOT / local['outputRelativeRoot']
        local_raw = (local_base / 'summary.json').read_bytes()
        require(sha(local_raw) == local['summarySha256'], 'local verification original summary')
        local_value = trace.strict_json(local_raw)
        require(local_value['sourceCommit'] == local['sourceCommit'] and
                trace.json_equal(local_value['tests'], local['tests']) and
                trace.json_equal(local_value['capture'], value['capture']) and
                trace.json_equal(local_value['previousCapture'], value['previousCapture']) and
                local_value['newMockTrialsDuringVerification'] == local_value['paidModelCalls'] == 0 and
                local_value['eligibleForMeasurement'] is False, 'local verification source and scope')
        local_guards = list(local_value['sourceGuards'].values())
        require(len(local_guards) == 2 and trace.json_equal(*local_guards) and
                local_guards[0]['observedHead'] == local['sourceCommit'], 'local fixed clean ref')
        for name, expected in local_guards[0]['sourceSha256'].items():
            require(sha(guard.git(ROOT, 'show', local['sourceCommit'] + ':' + name)) == expected,
                    'local historical source')
        for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
            require(sha((local_base / name).read_bytes()) == local['tests'][key], 'local original test bytes')
        matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (local_base / 'tests.stderr').read_bytes())
        require(matched and int(matched[1]) == local['tests']['count'] == 466 and
                float(matched[2]) == local['tests']['seconds'] and local['tests']['exitCode'] == 0,
                'local actual test terminal')
    failed = summary['localRemediation']['failedCleanTreeVerification']
    failed_base = ROOT / failed['outputRelativeRoot']
    require(sha((failed_base / 'tests.stderr').read_bytes()) == failed['stderrSha256'] and
            not (failed_base / 'summary.json').exists() and failed['exitCode'] == 1,
            'failed clean-tree verification retained')
    next_review = summary['nextReview']
    next_contract = trace.strict_json(guard.git(ROOT, 'show', next_review['sourceCommit'] + ':' + next_review['contractPath']))
    require(next_review['actualInvocations'] == 0 and not (ROOT / next_review['outputRelativeRoot']).exists() and
            next_review['maximumInvocations'] == next_contract['maximumInvocations'] == 1 and
            next_review['automaticRetries'] == next_contract['automaticRetries'] == 0 and
            next_review['primaryModelTrajectories'] == next_review['additionalDelegation'] == 0 and
            next_contract['payloadFiles'] == contract['payloadFiles'], 'next finite review')
    total = 0
    for name in next_contract['payloadFiles']:
        raw = guard.git(ROOT, 'show', next_review['sourceCommit'] + ':' + name)
        require(raw == (ROOT / name).read_bytes(), 'next committed payload bytes')
        total += len(raw)
    require(total == next_review['payloadBytes'] == 87851 and
            len(next_contract['payloadFiles']) == next_review['payloadFilesCount'] == 8, 'next payload count')
    print(json.dumps({'status': 'recorded_raw_capture_results_match_original_bytes',
                      'tests': tests['count'], 'rawItemsPerCapture': 6, 'rawCompletedPerCapture': 2,
                      'mockTrials': 2, 'localMockHttpRequests': 4, 'rawMockPaidModelCalls': 0,
                      'independentReviewInvocations': 1, 'reviewFindings': len(response['findings']),
                      'correctedSourceTests': local['tests']['count'] if local is not None else None,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
