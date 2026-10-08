"""公開要約を保存済み原bytesと固定Gitへ再照合する。外部通信・書込みなし。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import run_sdk_trace_review as review
import source_guard as guard

require = review.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, name):
    path = root / name
    require(path.is_relative_to(ROOT) and not any(p.is_symlink() for p in (path, *path.parents)),
            'artifact path or symlink')
    return path.read_bytes()


def check_guards(value):
    guards = list(value['sourceGuards'].values())
    require(guards and all(g == guards[0] for g in guards), 'recorded source guard drift')
    for name, expected in guards[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == expected,
                'historical source bytes drift')


def run():
    summary = json.loads(Path(__file__).with_name('summary.json').read_bytes())
    require(summary['phase'] == 4 and not summary['phaseComplete'] and
            not summary['eligibleForMeasurement'] and not summary['independentRemediationReviewPassed'],
            'scope drift')
    meta = summary['artifactVerification']
    base = ROOT / meta['outputRelativeRoot']
    raw = read(base, 'summary.json')
    require(sha(raw) == meta['summarySha256'], 'verification summary drift')
    original = json.loads(raw)
    check_guards(original)
    require(original['sourceCommit'] == summary['sourceCommit'] and
            original['tests'] == meta['tests'] and original['parentLinks'] == meta['parentLinks'] and
            original['snapshotResourceCount'] == meta['snapshotResourceCount'] == 71,
            'verification binding')
    tests = original['tests']
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        require(sha(read(base, name)) == tests[key], 'test bytes drift')
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', read(base, 'tests.stderr'))
    require(matched and int(matched[1]) == tests['count'] == 416 and
            float(matched[2]) == tests['seconds'] and tests['exitCode'] == 0, 'actual test terminal')
    requests = 0
    for meta in summary['mockTrials']:
        base = ROOT / meta['outputRelativeRoot']
        raw = read(base, 'receipt.json')
        require(sha(raw) == meta['receiptSha256'], 'mock receipt drift')
        value = json.loads(raw)
        check_guards(value)
        for name, expected in value['artifactSha256'].items():
            require(sha(read(base, name)) == expected, 'mock original artifact drift')
        for key, expected in meta.items():
            if key not in {'outputRelativeRoot', 'receiptSha256'}:
                require(value[key] == expected, 'mock summary binding')
        require(value['paidModelCalls'] == 0 and all(value['isolationChecks'].values()), 'mock scope')
        requests += value['localHttpRequestCount']
    require(len(summary['mockTrials']) == summary['newMockTrials'] == 3 and
            requests == summary['newLocalHttpRequests'] == 5, 'mock count')
    for index, meta in enumerate(summary['independentReviews'], 1):
        base = ROOT / meta['outputRelativeRoot']
        raw = read(base, 'receipt.json')
        require(sha(raw) == meta['receiptSha256'], 'review receipt drift')
        value = json.loads(raw)
        check_guards(value)
        for name, key in [('trace.jsonl', 'stdoutSha256'), ('stderr.bin', 'stderrSha256'),
                          ('prompt.txt', 'promptSha256')]:
            require(sha(read(base, name)) == value[key], 'review original bytes drift')
        require(sha(read(base, 'response.json')) == meta['responseSha256'], 'review response drift')
        contract = json.loads(guard.git(ROOT, 'show', value['sourceCommit'] +
                           f':evals/skills/routing/sdk-trace-review-v0.{index}.json'))
        schema = read(base, 'schema.json')
        require(schema == guard.git(ROOT, 'show', value['sourceCommit'] +
                                    ':evals/skills/routing/sdk-trace-review.schema.json'), 'review schema drift')
        stdout = read(base, 'trace.jsonl')
        if index == 1:
            try:
                review.review_response(base, stdout, value['sourceCommit'], schema, contract)
            except ValueError:
                pass
            else:
                raise ValueError('old stopped review was accepted')
            require(value['status'] == 'review_stopped', 'old stop changed')
            response = review.trace.strict_json(read(base, 'response.json'))
            review.trace.jsonschema.Draft202012Validator(json.loads(schema)).validate(response)
            events = [review.trace.strict_json(line) for line in stdout.splitlines()]
            messages = [e['item']['text'] for e in events if e.get('type') == 'item.completed' and
                        e.get('item', {}).get('type') == 'agent_message']
            require(len(messages) == 1 and response == review.trace.strict_json(messages[0]), 'stopped final binding')
            usage = [e['usage'] for e in events if e.get('type') == 'turn.completed']
            require(len(usage) == 1, 'stopped usage count')
            usage = usage[0]
        else:
            response, usage, warnings = review.review_response(base, stdout, value['sourceCommit'], schema, contract)
            require(value['status'] == 'review_findings' and warnings == value['acceptedStartupWarningHashes'],
                    'accepted review status')
        counts = {q: sum(f['priority'] == q for f in response['findings']) for q in ('P1', 'P2', 'P3')}
        require(counts == meta['rawResponseFindingCounts'] and usage == meta['usageFromRawTrace'] and
                response['sourceCommit'] == value['sourceCommit'], 'review counts or usage drift')
        for key in ('status', 'sourceCommit', 'model', 'exitCode', 'timedOut',
                    'independentReviewerSolInvocations', 'primaryModelTrajectories', 'automaticRetries'):
            require(value[key] == meta[key], 'review summary binding')
    require(len(summary['independentReviews']) == summary['independentReviewerSolInvocations'] == 4,
            'review invocation count')
    pending = summary['pendingReview']
    require(pending['actualInvocations'] == 0 and not pending['outputDirectoryExists'] and
            not (ROOT / pending['outputRelativeRoot']).exists(), 'pending invocation changed')
    payload_bytes = 0
    for item in pending['payloadFiles']:
        raw = guard.git(ROOT, 'show', pending['sourceCommit'] + ':' + item['path'])
        require(sha(raw) == item['sha256'] and len(raw) == item['bytes'] and
                read(ROOT, item['path']) == raw, 'pending payload drift')
        payload_bytes += len(raw)
    require(payload_bytes == pending['payloadBytes'] == 86519, 'pending payload size')
    print(json.dumps({'status': 'recorded_results_match_original_bytes', 'tests': 416,
                      'mockTrials': 3, 'localHttpRequests': 5, 'independentReviews': 4,
                      'pendingReviewInvocations': 0, 'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
