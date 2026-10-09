"""増分・ID・SSE是正の公開記録を原bytesと確定Gitへ照合する。課金呼出しと書込みはない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace
import production_sdk_trace as sdk
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
    values = list(value['sourceGuards'].values())
    require(values and all(trace.json_equal(v, values[0]) for v in values), 'source guard drift')
    require(values[0]['sourceCommit'] == value['sourceCommit'] and values[0]['headIsCondition'] is False,
            'historical fixed source binding')
    observed = values[0]['observedHead']
    require(guard.git(ROOT, 'rev-parse', observed + '^{commit}').decode().strip() == observed,
            'historical observed HEAD ref')
    for name, expected in values[0]['sourceSha256'].items():
        require(sha(guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == expected,
                'historical Git bytes drift')


def run():
    summary = json.loads(Path(__file__).with_name('summary.json').read_bytes())
    require(summary['phase'] == 4 and not summary['phaseComplete'] and
            not summary['eligibleForMeasurement'], 'scope drift')
    previous = json.loads(guard.git(ROOT, 'show', summary['previousHistoricalReportCommit'] +
        ':evals/skills/results/2026-10-09-sdk-context-remediation/summary.json'))
    total = previous['cumulativeSdkTraceIndependentReviewerSolInvocations']
    outcomes = []
    for meta in summary['independentReviews']:
        base = ROOT / meta['outputRelativeRoot']
        raw = read(base, 'receipt.json')
        require(sha(raw) == meta['receiptSha256'], 'review receipt drift')
        value = json.loads(raw)
        require(trace.json_equal({k: v for k, v in value.items() if k != 'sourceGuards'},
                                 meta['receipt']), 'review summary binding')
        check_guards(value)
        for name, key in (('prompt.txt', 'promptSha256'), ('trace.jsonl', 'stdoutSha256'),
                          ('stderr.bin', 'stderrSha256'), ('response.json', 'responseSha256')):
            require(sha(read(base, name)) == value[key], 'review original bytes drift')
        contract = json.loads(guard.git(ROOT, 'show', value['sourceCommit'] + ':' + meta['contractPath']))
        require(contract['maximumInvocations'] == 1 and contract['automaticRetries'] == 0 and
                contract['primaryModelTrajectories'] == 0 and
                contract['payloadFiles'] == summary['continuingTransmissionApproval']['payloadPaths'],
                'finite review contract or payload paths')
        schema = read(base, 'schema.json')
        require(schema == guard.git(ROOT, 'show', value['sourceCommit'] +
                                     ':evals/skills/routing/sdk-trace-review.schema.json'), 'schema drift')
        response, usage, warnings = review.review_response(
            base, read(base, 'trace.jsonl'), value['sourceCommit'], schema, contract)
        require(trace.json_equal(response['findings'], value['findings']) and
                trace.json_equal(usage, value['usage']) and warnings == value['acceptedStartupWarningHashes'],
                'review terminal response/usage')
        require(value['exitCode'] == 0 and value['timedOut'] is False and
                value['independentReviewerSolInvocations'] == 1 and
                value['primaryModelTrajectories'] == value['automaticRetries'] == 0,
                'review execution budget')
        require(value['status'] == ('review_findings' if response['findings'] else 'static_review_passed'),
                'review verdict binding')
        prompt = read(base, 'prompt.txt').decode()
        for name in contract['payloadFiles']:
            raw = guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)
            block = '\nFILE ' + name + ' SHA256 ' + sha(raw) + '\n'
            block += '\n'.join(f'{i}: {line}' for i, line in enumerate(raw.decode().splitlines(), 1))
            require(prompt.count(block + '\nEND FILE\n') == 1, 'Git payload and prompt projection')
        reservation = json.loads(read(base, 'reservation.json'))
        require(reservation['attemptReserved'] == reservation['maximumInvocations'] == 1 and
                reservation['sourceCommit'] == value['sourceCommit'] and
                reservation['automaticRetry'] is False, 'review reservation')
        total += 1
        outcomes.append({'status': value['status'],
                         'findings': {p: sum(f['priority'] == p for f in value['findings'])
                                      for p in ('P1', 'P2', 'P3')}})
    require(total == summary['cumulativeSdkTraceIndependentReviewerSolInvocations'] and
            len(outcomes) == summary['newIndependentReviewerSolInvocations'], 'review count')
    require(summary['independentRemediationReviewPassed'] ==
            (outcomes[-1]['status'] == 'static_review_passed'), 'final review status')
    for meta in summary['remediationVerifications']:
        base = ROOT / meta['outputRelativeRoot']
        raw = read(base, 'summary.json')
        require(sha(raw) == meta['summarySha256'], 'verification summary drift')
        value = json.loads(raw)
        require(trace.json_equal({k: v for k, v in value.items() if k != 'sourceGuards'},
                                 meta['result']), 'verification summary binding')
        check_guards(value)
        tests = value['tests']
        for name, key in (('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')):
            require(sha(read(base, name)) == tests[key], 'test bytes drift')
        matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', read(base, 'tests.stderr'))
        require(matched and int(matched[1]) == tests['count'] and
                float(matched[2]) == tests['seconds'] and tests['exitCode'] == 0, 'test terminal')
        require(value['status'] == 'sdk_parent_links_artifacts_rechecked' and
                value['allTargetTraceRowsPreserved'] is True and value['originalHashesChecked'] is True and
                value['snapshotResourceCount'] == 71 and not value['eligibleForMeasurement'] and
                not value['phaseComplete'], 'fixed diagnostic scope')
    latest = summary['remediationVerifications'][-1]['result']
    require(latest['sourceCommit'] == summary['sourceCommit'] ==
            summary['independentReviews'][-1]['receipt']['sourceCommit'], 'latest fixed source')
    # 原probe・71資源・全target原行・親子IDを現在の診断コードで再照合する。
    helper_path = ROOT / 'evals/skills/results/2026-10-08-sdk-trace-connection/verify-artifacts.py'
    spec = importlib.util.spec_from_file_location('original_helper', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    original_contract = json.loads(guard.git(ROOT, 'show', latest['probeSourceCommit'] +
        ':evals/skills/routing/production-operation-probe-v0.6.json'))
    manifest, count = helper.check_snapshot(original_contract)
    base = ROOT / '.venv/production-operation-read-06'
    probe, receipt_sha = helper.receipt(base, expected_sha=latest['receiptSha256'])
    require(count == 71 and receipt_sha == latest['receiptSha256'], 'original probe hash/snapshot')
    incoming, outgoing = [helper.frames(base, n) for n in ('rpc-in.jsonl', 'rpc-out.jsonl')]
    result = sdk.diagnose_exchange(manifest, helper.frames(base, 'host.jsonl'), incoming, outgoing,
        [trace.strict_json(read(base, f'request-{i}.json')) for i in (1, 2)],
        [read(base, f'response-{i}.sse') for i in (1, 2)],
        expected_program=helper.operation.program('read', base), expected_final_text='LOCAL_SIMULATION_ONLY',
        actual_exit_code=probe['runtime']['exitCode'], allowed_warnings=(helper.WARNING,))
    require(trace.json_equal(result, latest['diagnostic']), 'original exchange diagnostic drift')
    events = sdk.complete_trace_projection(read(base, 'runtime-stderr.bin'), read(base, 'trace-safe.jsonl'))
    links = sdk.audit_parent_links(events, outgoing, result['providerCallId'])
    require(trace.json_equal(links, latest['parentLinks']), 'parent link diagnostic drift')
    require(summary['newMockTrials'] == summary['newLocalHttpRequests'] ==
            summary['primaryModelTrajectories'] == summary['automaticRetries'] == 0, 'new trial budget')
    print(json.dumps({'status': 'recorded_results_match_original_bytes',
        'tests': latest['tests']['count'], 'newIndependentReviews': len(outcomes),
        'reviewOutcomes': outcomes, 'eligibleForMeasurement': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
