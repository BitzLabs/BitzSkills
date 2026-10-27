"""作成後・集合独立検分前の証拠を照合する。私的本文は出力しない。"""
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


def bound_file(path, expected):
    raw = actor.collection.legacy.private_file(path)
    assert hashlib.sha256(raw).hexdigest() == expected, 'bound artifact drift'
    return raw


def capture(phase, declared):
    assert set(declared['artifactSha256']) == {'trace.jsonl', 'stderr.log', 'response.json'}
    for name, digest in declared['artifactSha256'].items():
        bound_file(phase / name, digest)
    terminal = actor.terminal_result(phase)
    assert terminal['nativeTurnCompleted'] and terminal['nativeFinalResponseMatched']
    assert terminal['usage'] == declared['usage']
    return [actor.collection.load(line) for line in (phase / 'trace.jsonl').read_bytes().splitlines() if line.strip()]


def main():
    execution_contract = actor.verify(SOURCE)
    actor.require_budget_approval(SOURCE, ROOT / '.venv/routing-native-authoring-03')
    actor.require_previous('reviewer', SOURCE, execution_contract)
    base = actor.collection.load(actor.collection.source_guard.git(ROOT, 'show', SUMMARY['collectionSource'] + ':' + actor.collection.CONTRACT_NAME))
    audit = actor.collection.audit(base, PRIVATE / 'cases.json')
    assert audit['status'] == SUMMARY['collection']['parentAuditStatus']
    assert audit['heldOut']['caseCount'] == 12 and audit['newCaseCount'] == 1 and audit['retainedCaseCount'] == 11
    assert audit['routingAssessmentCount'] == 12
    assert audit['heldOut']['sha256'] == SUMMARY['collection']['filesSha256']['cases.json']
    assert audit['semanticNovelty'] == audit['routingSemantics'] == 'requires_independent_review'
    assert audit['primaryModelTrajectories'] == 0 and audit['certifiesSkillGate'] is False
    for name, digest in SUMMARY['collection']['filesSha256'].items():
        bound_file(PRIVATE / name, digest)
    creator_receipt = actor.collection.load(bound_file(PRIVATE / 'creation-receipt.json', SUMMARY['collection']['receiptSha256']))
    assert creator_receipt['status'] == SUMMARY['collection']['status']
    assert creator_receipt['sourceCommit'] == SUMMARY['collectionSource'] and creator_receipt['executionSource'] == SOURCE
    assert creator_receipt['nativeAuditExitCode'] == 0
    creation_audit = actor.collection.load(actor.collection.legacy.private_file(PRIVATE / 'creation-audit.json'))
    assert creation_audit['exitCode'] == 0
    assert actor.collection.digest(creation_audit['stdout'].encode()) == creation_audit['stdoutSha256']
    assert actor.collection.digest(creation_audit['stderr'].encode()) == creation_audit['stderrSha256']
    native_audit = json.loads(creation_audit['stdout'])
    assert native_audit['sourceCommit'] == SUMMARY['collectionSource'] and native_audit['sourceFileCount'] == 15
    assert all(native_audit[k] == v for k, v in audit.items())

    old_phase = PRIVATE / 'native-authoring-02/preparation'
    old = SUMMARY['previousPreparation']
    bound_file(old_phase / 'execution-receipt.json', old['executionReceiptSha256'])
    old_events = capture(old_phase, old)
    assert not any(e.get('item', {}).get('type') == 'command_execution' for e in old_events)
    assert actor.collection.load(actor.collection.legacy.private_file(old_phase / 'response.json'))['status'] == 'stopped'
    assert not (old_phase / 'native-preparation-receipt.json').exists()

    phase = PRIVATE / 'native-authoring-03/creator'
    execution = actor.collection.load(bound_file(phase / 'execution-receipt.json', SUMMARY['creator']['executionReceiptSha256']))
    assert actor.collection.load((ROOT / '.venv/routing-native-authoring-03/creator-result.json').read_bytes()) == execution
    for key in ['status', 'actualExitCode', 'nativeTurnCompleted', 'nativeFinalResponseMatched', 'postSourceMatched', 'phaseConditionsMatched', 'wallMs']:
        assert execution[key] == SUMMARY['creator'][key]
    events = capture(phase, SUMMARY['creator'])
    commands = [e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution']
    assert len(commands) == SUMMARY['creator']['completedCommands'] == 19
    assert all(c['exit_code'] == 0 for c in commands)
    assert any('unittest' in c.get('command', '') and 'subprocess.run' in c.get('command', '') and all(marker in c.get('aggregated_output', '') for marker in ['Ran 16 tests', 'Ran 9 tests', 'Ran 14 tests']) for c in commands)
    assert actor.collection.load(actor.collection.legacy.private_file(phase / 'response.json'))['status'] == 'completed'
    prep = actor.collection.load(bound_file(phase / 'native-preparation-receipt.json', SUMMARY['embeddedPreparation']['receiptSha256']))
    bound_file(phase / 'native-preparation-review.md', SUMMARY['embeddedPreparation']['reportSha256'])
    assert prep == actor.prepared_creator(SOURCE, execution_contract)
    assert len(prep['filesSha256']) == SUMMARY['embeddedPreparation']['boundFileCount'] == 14
    for name, digest in prep['filesSha256'].items():
        assert '/' not in name and name not in ('.', '..')
        bound_file(phase / name, digest)
    assert [prep[k] for k in ['nativeTests', 'shadowTests', 'collectionTests']] == [16, 9, 14]
    assert [prep[k] for k in ['nativeTestsExitCode', 'shadowTestsExitCode', 'collectionTestsExitCode', 'sourceGuardExitCode']] == [0, 0, 0, 0]
    assert prep['embeddedInCreatorInvocation'] and prep['additionalPreparationModelCalls'] == 0
    assert prep['primaryModelTrajectories'] == prep['automaticRetries'] == prep['delegations'] == 0
    assert prep['certifiesCollection'] is prep['certifiesSkillGate'] is False

    for role, key in [('operator-preflight', 'operatorReceiptSha256'), ('creator', 'creatorReceiptSha256')]:
        preflight = PRIVATE / 'native-authoring-03' / role / 'preflight'
        receipt = actor.collection.load(bound_file(preflight / 'receipt.json', SUMMARY['localPreflight'][key]))
        assert receipt['status'] == 'local_preflight_passed' and receipt['commandExitCode'] == 0
        assert receipt['networkNamespaceIsolated'] and receipt['modelCalls'] == receipt['threadOrTurnRequests'] == 0
        assert receipt['actualTestCount'] == 39 and receipt['intentionalServerShutdown'] and receipt['serverExitCode'] == -15
        assert receipt['certifiesIndependentPreparation'] is False
        for name, digest in receipt['captureSha256'].items():
            bound_file(preflight / name, digest)

    for name, key, marker in [('parent-native03-all-unit.log', 'allUnitLogSha256', b'Ran 294 tests'), ('parent-native03-unit39.log', 'rerunLogSha256', b'Ran 39 tests')]:
        path = ROOT / '.venv/held-out-single-replacement-05' / name
        assert not any(p.is_symlink() for p in [path, *path.parents])
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == SUMMARY['parentChecks'][key]
        assert marker in raw and b'\nOK\n' in raw and b'FAILED' not in raw
    snapshot = ROOT / base['candidate']['snapshotRelativePath']
    manifest = actor.collection.load((snapshot / 'manifest.json').read_bytes())
    assert len(manifest['skills']) == 6 and len(manifest['resources']) == 71
    for name, digest in manifest['resources'].items():
        assert name.startswith('resources/')
        path = 'plugins/' + name.removeprefix('resources/')
        assert actor.collection.digest(actor.collection.source_guard.git(ROOT, 'show', base['candidate']['sourceCommit'] + ':' + path)) == digest
    ledger = ROOT / '.venv/routing-native-authoring-03'
    assert not (ledger / 'reviewer.json').exists() and not (ledger / 'reviewer-result.json').exists()
    assert not (PRIVATE / 'native-authoring-03/reviewer').exists()
    assert not (PRIVATE / 'independent-receipt.json').exists()
    actor.verify(SOURCE)
    print(json.dumps({'status': 'parent_artifacts_verified', 'sourceFiles': 19, 'collectionSourceFiles': 15, 'caseCount': 12, 'newCaseCount': 1, 'retainedCaseCount': 11, 'candidateResourcesGitMatched': 71, 'preparationP1': 0, 'preparationP2': 0, 'creatorCommandCount': len(commands), 'reviewerReserved': False, 'semanticIndependentReviewPending': True, 'certifiesCaseSet': False, 'certifiesSkillGate': False}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'errorType': type(error).__name__}))
        raise SystemExit(1)
