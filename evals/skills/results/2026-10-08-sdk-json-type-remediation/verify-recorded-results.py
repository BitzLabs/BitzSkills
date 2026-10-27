"""JSON型是正の公開要約を原保存物とGitへ照合する。モデルを呼ばず書き込まない。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace
import run_sdk_trace_review as review
import source_guard as guard

require = trace.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(base, name):
    path = base / name
    require(path.is_relative_to(ROOT) and not any(p.is_symlink() for p in (path, *path.parents)),
            'artifact path or symlink')
    return path.read_bytes()


def check_guards(value):
    guards = list(value['sourceGuards'].values())
    require(guards and all(trace.json_equal(g, guards[0]) for g in guards), 'source guard drift')
    for name, expected in guards[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == expected,
                'historical Git bytes drift')


def run():
    summary = json.loads(Path(__file__).with_name('summary.json').read_bytes())
    require(summary['phase'] == 4 and not summary['phaseComplete'] and
            not summary['eligibleForMeasurement'] and not summary['independentRemediationReviewPassed'], 'scope drift')
    meta = summary['remediationVerification']
    base = ROOT / meta['outputRelativeRoot']
    raw = read(base, 'summary.json')
    require(sha(raw) == meta['summarySha256'], 'verification summary drift')
    value = json.loads(raw)
    check_guards(value)
    require(value['sourceCommit'] == summary['sourceCommit'] and meta['sourceGuardsEqual'] is True, 'source binding')
    for key in ('status', 'probeSourceCommit', 'receiptSha256', 'snapshotResourceCount',
                'originalHashesChecked', 'allTargetTraceRowsPreserved', 'parentLinks', 'tests'):
        require(trace.json_equal(value[key], meta[key]), 'verification field binding')
    tests = value['tests']
    for name, key in (('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')):
        require(sha(read(base, name)) == tests[key], 'test bytes drift')
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', read(base, 'tests.stderr'))
    require(matched and int(matched[1]) == tests['count'] == 426 and
            float(matched[2]) == tests['seconds'] and tests['exitCode'] == 0, 'actual test terminal')
    require(sha(read(ROOT / '.venv/production-operation-read-06', 'receipt.json')) == meta['receiptSha256'],
            'probe receipt drift')
    original = summary['originalReview']
    base = ROOT / original['outputRelativeRoot']
    raw = read(base, 'receipt.json')
    require(sha(raw) == original['receiptSha256'], 'review receipt drift')
    value = json.loads(raw)
    check_guards(value)
    for key, expected in original.items():
        if key not in {'outputRelativeRoot', 'receiptSha256', 'sourceGuardsEqual'}:
            require(trace.json_equal(value[key], expected), 'review summary binding')
    for name, key in (('prompt.txt', 'promptSha256'), ('trace.jsonl', 'stdoutSha256'),
                      ('stderr.bin', 'stderrSha256'), ('response.json', 'responseSha256')):
        require(sha(read(base, name)) == value[key], 'review original bytes drift')
    contract = json.loads(guard.git(ROOT, 'show', value['sourceCommit'] +
                         ':evals/skills/routing/sdk-trace-review-v0.5.json'))
    schema = read(base, 'schema.json')
    require(schema == guard.git(ROOT, 'show', value['sourceCommit'] +
                                ':evals/skills/routing/sdk-trace-review.schema.json'), 'review schema drift')
    response, usage, warnings = review.review_response(base, read(base, 'trace.jsonl'), value['sourceCommit'], schema, contract)
    require(trace.json_equal(response['findings'], value['findings']) and
            trace.json_equal(usage, value['usage']) and warnings == value['acceptedStartupWarningHashes'],
            'review response or usage binding')
    require(value['status'] == 'review_findings' and value['exitCode'] == 0 and
            [f['priority'] for f in response['findings']] == ['P2', 'P3'], 'review outcome')
    previous = json.loads(guard.git(ROOT, 'show', summary['previousHistoricalReportCommit'] +
                          ':evals/skills/results/2026-10-08-sdk-trace-connection/summary.json'))
    require(previous['independentReviewerSolInvocations'] + value['independentReviewerSolInvocations'] ==
            summary['cumulativeSdkTraceIndependentReviewerSolInvocations'] == 5, 'review call count')
    pending = summary['pendingReview']
    require(pending['sourceCommit'] == summary['sourceCommit'] and pending['actualInvocations'] == 0 and
            not pending['outputDirectoryExists'] and not (ROOT / pending['outputRelativeRoot']).exists(),
            'pending invocation changed')
    contract = json.loads(guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + pending['contractPath']))
    require(contract['payloadFiles'] == [item['path'] for item in pending['payloadFiles']] and
            contract['maximumInvocations'] == 1 and contract['automaticRetries'] == 0 and
            contract['previousFailure']['receiptSha256'] == original['receiptSha256'], 'pending contract')
    total = 0
    for item in pending['payloadFiles']:
        raw = guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + item['path'])
        require(sha(raw) == item['sha256'] and len(raw) == item['bytes'] and
                raw == read(ROOT, item['path']), 'pending payload drift')
        total += len(raw)
    require(total == pending['payloadBytes'] == 108907 and len(pending['payloadFiles']) == 6, 'payload count')
    print(json.dumps({'status': 'recorded_results_match_original_bytes', 'tests': 426,
                      'originalReviewFindings': {'P2': 1, 'P3': 1}, 'newIndependentReviews': 1,
                      'pendingReviewInvocations': 0, 'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
