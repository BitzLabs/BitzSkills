"""SDK raw交換監査の公開記録を、原bytesと確定Gitへ再照合する。書込み・モデル呼出しはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper = load('raw_exchange_record_wrapper', 'evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py')
reviews = load('raw_exchange_review_records', 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
trace, guard, require = wrapper.sdk.trace, wrapper.guard, wrapper.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    summary = trace.strict_json(Path(__file__).with_name('summary.json').read_bytes())
    meta = summary['verification']
    base = ROOT / meta['outputRelativeRoot']
    raw = (base / 'summary.json').read_bytes()
    require(sha(raw) == meta['summarySha256'], 'raw exchange original summary')
    value = trace.strict_json(raw)
    require(value['status'] == 'sdk_raw_exchange_artifacts_rechecked' and value['sourceCommit'] == summary['sourceCommit'] and
            trace.json_equal(value['tests'], meta['tests']) and summary['eligibleForMeasurement'] is False and
            summary['phaseComplete'] is False and value['eligibleForMeasurement'] is False and value['phaseComplete'] is False,
            'raw exchange source/tests/scope')
    stages = list(value['sourceGuards'].values())
    require(len(stages) == 2 and trace.json_equal(*stages) and stages[0]['observedHead'] == summary['sourceCommit'],
            'raw exchange source guard drift')
    for name, digest in stages[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', summary['sourceCommit'] + ':' + name)) == digest, 'historical raw exchange Git')
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha((base / name).read_bytes()) == meta['tests'][key], 'original raw exchange tests')
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', (base / 'tests.stderr').read_bytes())
    require(matched and int(matched[1]) == meta['tests']['count'] == 472 and
            float(matched[2]) == meta['tests']['seconds'] and meta['tests']['exitCode'] == 0, 'raw exchange actual test terminal')
    for i, (label, legacy) in enumerate([('production-operation-read-07', True), ('production-operation-read-08', False)]):
        replay = wrapper.check_raw_capture(ROOT / '.venv' / label, legacy=legacy)
        require(trace.json_equal(replay, value['captures'][i]), 'raw exchange original capture replay')
        record = summary['captures'][i]
        require(replay['probeSourceCommit'] == record['probeSourceCommit'] and
                replay['receiptSha256'] == record['receiptSha256'] and
                replay['artifactAudit']['snapshotResourceCount'] == record['snapshotResourceCount'] and
                all(trace.json_equal(replay['rawExchangeAudit'][k], v) for k, v in record['rawExchangeAudit'].items()),
                'raw exchange recorded projections')
    response = reviews.recheck_review(summary['independentReview'])
    require(response['verdict'] == 'pass' and response['findings'] == [] and
            summary['independentReview']['sourceCommit'] == summary['sourceCommit'], 'raw exchange independent review')
    require(value['newMockTrials'] == value['newLocalHttpRequests'] == value['paidModelCalls'] ==
            summary['newMockTrials'] == summary['newLocalHttpRequests'] == summary['probePaidModelCalls'] == 0 and
            summary['newIndependentReviewerSolInvocations'] == 1 and summary['automaticRetries'] ==
            summary['primaryModelTrajectories'] == 0, 'raw exchange counters')
    print(json.dumps({'status': 'recorded_raw_exchange_results_match_original_bytes', 'tests': 472,
                      'capturesReplayed': 2, 'rawItemsPerCapture': 6, 'newMockTrials': 0,
                      'newLocalHttpRequests': 0, 'independentSolInvocations': 1, 'reviewFindings': 0,
                      'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
