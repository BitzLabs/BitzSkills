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
    pending = summary['pendingReview']
    contract = trace.strict_json(guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + pending['contractPath']))
    require(pending['actualInvocations'] == 0 and
            not (ROOT / pending['outputRelativeRoot']).exists() and
            pending['maximumInvocations'] == contract['maximumInvocations'] == 1 and
            pending['automaticRetries'] == contract['automaticRetries'] == 0 and
            pending['additionalDelegation'] == pending['primaryModelTrajectories'] == 0, 'pending finite review')
    require(contract['payloadFiles'] == [f['path'] for f in pending['payloadFiles']], 'pending payload paths')
    total = 0
    for item in pending['payloadFiles']:
        raw = guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + item['path'])
        require(raw == (ROOT / item['path']).read_bytes() and len(raw) == item['bytes'] and
                sha(raw) == item['sha256'], 'pending payload bytes')
        total += len(raw)
    require(total == pending['payloadBytes'] and len(pending['payloadFiles']) == 8, 'payload count')
    require(summary['newRawMockTrials'] == 2 and summary['newLocalMockHttpRequests'] == 4 and
            summary['rawMockPaidModelCalls'] == summary['newRawCaptureIndependentReviewerSolInvocations'] == 0,
            'capture counters')
    print(json.dumps({'status': 'recorded_raw_capture_results_match_original_bytes',
                      'tests': tests['count'], 'rawItemsPerCapture': 6, 'rawCompletedPerCapture': 2,
                      'mockTrials': 2, 'localMockHttpRequests': 4, 'rawMockPaidModelCalls': 0,
                      'pendingReviewInvocations': 0, 'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
