"""独立検分後の証拠を照合する。私的本文・個別判断を出力しない。"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import native_actor_v03 as actor

HERE = Path(__file__).resolve().parent
SUMMARY = json.loads((HERE / 'summary.json').read_bytes())
PRIVATE = actor.PRIVATE
SOURCE = SUMMARY['executionSource']


def bound(path, expected):
    raw = actor.collection.legacy.private_file(path)
    assert hashlib.sha256(raw).hexdigest() == expected
    return raw


def main():
    contract = actor.verify(SOURCE)
    actor.require_previous('reviewer', SOURCE, contract)
    actor.require_budget_approval(SOURCE, ROOT / '.venv/routing-native-authoring-03')
    creation_summary_path = 'evals/skills/results/2026-10-07-single-replacement-created/summary.json'
    previous = actor.collection.load(actor.collection.source_guard.git(ROOT, 'show', SUMMARY['creationResultSource'] + ':' + creation_summary_path))
    for name, digest in previous['collection']['filesSha256'].items():
        bound(PRIVATE / name, digest)
    bound(PRIVATE / 'creation-receipt.json', previous['collection']['receiptSha256'])
    creator_phase = PRIVATE / 'native-authoring-03/creator'
    bound(creator_phase / 'execution-receipt.json', previous['creator']['executionReceiptSha256'])
    preparation = actor.prepared_creator(SOURCE, contract)
    bound(creator_phase / 'native-preparation-receipt.json', previous['embeddedPreparation']['receiptSha256'])
    for name, digest in preparation['filesSha256'].items():
        assert '/' not in name
        bound(creator_phase / name, digest)

    base = actor.collection.load(actor.collection.source_guard.git(ROOT, 'show', SUMMARY['collectionSource'] + ':' + actor.collection.CONTRACT_NAME))
    audit = actor.collection.audit(base, PRIVATE / 'cases.json')
    assert audit['status'] == SUMMARY['parentChecks']['mechanicalAuditStatus']
    assert audit['heldOut']['sha256'] == SUMMARY['casesSha256'] and audit['evidenceSha256'] == SUMMARY['evidenceSha256']
    assert [audit[k] for k in ['newCaseCount', 'retainedCaseCount', 'routingAssessmentCount']] == [1, 11, 12]
    assert audit['heldOut']['caseCount'] == 12
    review = SUMMARY['independentReview']
    receipt = actor.collection.load(bound(PRIVATE / 'independent-receipt.json', review['receiptSha256']))
    for key in ['status', 'severityCounts', 'affectedCaseCount', 'routingSemanticsPassedCount', 'novelNewCaseCount', 'actualTestCounts', 'actualTestExitCodes', 'guardExitCodes', 'existingFilesUnchanged', 'nativeAuditExitCode', 'nativeAuxiliaryCorrections', 'filesSha256']:
        assert receipt[key] == review[key]
    assert receipt['sourceCommit'] == SUMMARY['collectionSource'] and receipt['executionSource'] == SOURCE
    for key in ['setVersion', 'casesSha256', 'evidenceSha256', 'caseCount', 'newCaseCount', 'retainedCaseCount']:
        assert receipt[key] == SUMMARY[key]
    assert receipt['creationReceiptSha256'] == previous['collection']['receiptSha256']
    assert receipt['retentionSha256'] == previous['collection']['filesSha256']['retention.json']
    assert receipt['independentReviewerSolConsumed'] == 1
    assert receipt['primaryModelTrajectories'] == receipt['automaticRetries'] == receipt['delegations'] == 0
    assert receipt['previousStopsPreserved'] and receipt['originalRawByteMissingPreserved']
    assert receipt['certifiesBehavior'] is receipt['certifiesSkillGate'] is receipt['certifiesProductCompletion'] is False
    for name, digest in review['filesSha256'].items():
        assert '/' not in name
        bound(PRIVATE / name, digest)
    guards = actor.collection.load(actor.collection.legacy.private_file(PRIVATE / 'independent-source-guard.json'))
    assert guards == receipt['sourceGuards'] and set(guards) == {'start', 'presave', 'end'}
    for guard in guards.values():
        assert guard['exitCode'] == 0 and guard['execution19Previous13Previous7Verified']
        assert guard['collection']['sourceCommit'] == SUMMARY['collectionSource']
        assert len(guard['collection']['sourceSha256']) == 15
        for name, digest in guard['privateSha256'].items():
            assert '/' not in name
            bound(PRIVATE / name, digest)
    independent_audit = actor.collection.load(actor.collection.legacy.private_file(PRIVATE / 'independent-audit.json'))
    assert all(independent_audit[key] == value for key, value in audit.items())
    assert independent_audit['routingSemanticsPassedCount'] == 12 and independent_audit['novelNewCaseCount'] == 1
    assert independent_audit['severityCounts'] == {'P1': 0, 'P2': 0}
    report = actor.collection.legacy.private_file(PRIVATE / 'independent-review.md').decode()
    cases = actor.collection.load(actor.collection.legacy.private_file(PRIVATE / 'cases.json'))['cases']
    assert len(cases) == 12 and all(case['caseId'] in report for case in cases)
    assert sum(line.startswith('### ') for line in report.splitlines()) == 12

    phase = PRIVATE / 'native-authoring-03/reviewer'
    execution = actor.collection.load(bound(phase / 'execution-receipt.json', SUMMARY['reviewerExecution']['executionReceiptSha256']))
    assert actor.collection.load((ROOT / '.venv/routing-native-authoring-03/reviewer-result.json').read_bytes()) == execution
    for key in ['status', 'actualExitCode', 'nativeTurnCompleted', 'nativeFinalResponseMatched', 'postSourceMatched', 'phaseConditionsMatched', 'wallMs', 'artifactSha256', 'usage']:
        assert execution[key] == SUMMARY['reviewerExecution'][key]
    for name, digest in execution['artifactSha256'].items():
        assert name in {'trace.jsonl', 'stderr.log', 'response.json'}
        bound(phase / name, digest)
    terminal = actor.terminal_result(phase)
    assert terminal['usage'] == execution['usage']
    response = actor.collection.load(actor.collection.legacy.private_file(phase / 'response.json'))
    assert response['status'] == 'completed' and response['severityCounts'] == {'P1': 0, 'P2': 0}
    events = [actor.collection.load(line) for line in (phase / 'trace.jsonl').read_bytes().splitlines() if line.strip()]
    commands = [e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution']
    assert len(commands) == 19 and sum(c['exit_code'] == 0 for c in commands) == 18
    assert sum(c['exit_code'] == 1 for c in commands) == 1
    assert any('unittest' in c.get('command', '') and all(marker in c.get('aggregated_output', '') for marker in ['Ran 16 tests', 'Ran 9 tests', 'Ran 14 tests']) for c in commands)
    error = actor.collection.load(actor.collection.legacy.private_file(PRIVATE / 'independent-invocation-error.json'))
    assert error['exitCode'] == 1 and error['correctionCount'] == 1 and error['paidRetry'] is False

    preflight = phase / 'preflight'
    local = actor.collection.load(bound(preflight / 'receipt.json', SUMMARY['localPreflight']['receiptSha256']))
    assert local['status'] == 'local_preflight_passed' and local['actualTestCount'] == 39 and local['commandExitCode'] == 0
    assert local['networkNamespaceIsolated'] and local['modelCalls'] == local['threadOrTurnRequests'] == 0
    assert local['intentionalServerShutdown'] and local['serverExitCode'] == -15
    for name, digest in local['captureSha256'].items():
        bound(preflight / name, digest)
    log = ROOT / '.venv/held-out-single-replacement-05/parent-native03-review-unit39.log'
    assert not any(p.is_symlink() for p in [log, *log.parents])
    raw = log.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SUMMARY['parentChecks']['testLogSha256']
    assert b'Ran 39 tests' in raw and b'\nOK\n' in raw and b'FAILED' not in raw
    snapshot = ROOT / base['candidate']['snapshotRelativePath']
    manifest = actor.collection.load((snapshot / 'manifest.json').read_bytes())
    assert len(manifest['skills']) == 6 and len(manifest['resources']) == 71
    for name, digest in manifest['resources'].items():
        assert name.startswith('resources/')
        path = 'plugins/' + name.removeprefix('resources/')
        assert actor.collection.digest(actor.collection.source_guard.git(ROOT, 'show', base['candidate']['sourceCommit'] + ':' + path)) == digest
    actor.verify(SOURCE)
    print(json.dumps({'status': 'parent_review_artifacts_verified', 'sourceFiles': 19, 'collectionSourceFiles': 15, 'caseCount': 12, 'routingSemanticsPassedCount': 12, 'novelNewCaseCount': 1, 'independentP1': 0, 'independentP2': 0, 'reportCaseCoverage': 12, 'parentTests': 39, 'candidateResourcesGitMatched': 71, 'nativeAuxiliaryCorrections': 1, 'caseSetAcceptedForMeasurementPreparation': True, 'primaryModelTrajectories': 0, 'certifiesBehavior': False, 'certifiesSkillGate': False}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'errorType': type(error).__name__}))
        raise SystemExit(1)
