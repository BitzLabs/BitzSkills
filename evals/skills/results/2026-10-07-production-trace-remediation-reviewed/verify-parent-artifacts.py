"""ローカル原証拠を公開summaryと固定sourceへ照合する。モデルを呼ばない。"""
import hashlib
import json
from pathlib import Path
import re
import sys

import jsonschema

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import source_guard


def main():
    summary = json.loads(Path(__file__).with_name('summary.json').read_bytes())
    source = summary['sourceCommit']
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + summary['contract']))
    guard = source_guard.verify(ROOT, source, contract['sourceFiles'])
    base = ROOT / summary['localEvidenceRoot']
    assert not any(p.is_symlink() for p in [base, *base.parents])
    assert base.stat().st_mode & 0o777 == 0o700
    for name, expected in summary['artifactSha256'].items():
        path = base / name
        assert not path.is_symlink() and path.stat().st_mode & 0o777 == 0o600
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    receipt = json.loads((base / 'receipt.json').read_bytes())
    schema = json.loads(source_guard.git(ROOT, 'show', source + ':' + contract['outputs']['receiptSchema']))
    jsonschema.Draft202012Validator(schema).validate(receipt)
    assert receipt['sourceCommit'] == source and receipt['status'] == summary['independentReviewStatus']
    assert receipt['severityCounts'] == summary['severityCounts'] == {'P1': 0, 'P2': 0}
    assert receipt['reviewerGuardBeforeInitialReadsPerformed'] is False
    assert receipt['sourceGuards']['before']['executionPoint'] == 'after initial source reads; before adversarial review and tests'
    reservation = json.loads((base / 'reservation.json').read_bytes())
    parent = json.loads((base / 'parent-verification.json').read_bytes())
    clean = json.loads((base / 'parent-clean-unit.json').read_bytes())
    for record in [receipt, parent, clean]:
        assert record['sourceCommit'] == source
        for observed in record['sourceGuards'].values():
            assert observed['sourceCommit'] == source and observed['status'] == 'fixed_source_matches'
            assert observed['sourceSha256'] == guard['sourceSha256']
    assert reservation['sourceGuard']['sourceSha256'] == guard['sourceSha256']
    assert reservation['sourceCommit'] == source and reservation['attemptReserved'] == reservation['maximumIndependentReviewerCalls'] == 1
    assert clean['actualExitCode'] == 0 and clean['cleanTreeBeforeAndAfter'] is True
    assert clean['logSha256'] == reservation['parentCleanUnitLogSha256'] == summary['artifactSha256']['parent-clean-unit.log']
    tests = json.loads((base / 'tests.json').read_bytes())
    for key, count, name in [('component', 26, 'component.log'), ('allSkills', 320, 'allSkills.log')]:
        raw = (base / name).read_text()
        assert raw == tests[key]['output'] and raw.strip().endswith('OK')
        assert re.search(r'Ran ' + str(count) + r' tests', raw)
        assert tests[key]['exit'] == receipt['actualTestExitCodes'][key] == 0
        assert receipt['actualTestCounts'][key] == count
    for name, count in [('parent-clean-unit.log', 320), ('parent-component-unit.log', 26)]:
        raw = (base / name).read_text()
        assert re.search(r'Ran ' + str(count) + r' tests', raw) and raw.strip().endswith('OK')
    assert parent['parentComponentExitCode'] == 0 and parent['parentComponentCount'] == 26
    adversarial = json.loads((base / 'adversarial.json').read_bytes())
    assert adversarial['actualExitCode'] == 0 and adversarial['count'] == len(adversarial['results']) == 8
    assert all(row['result'] == 'rejected' for row in adversarial['results'])
    prior = contract['previousFailure']
    for name, key in [('review.md', 'reportSha256'), ('receipt.json', 'receiptSha256'), ('reservation.json', 'reservationSha256')]:
        assert hashlib.sha256((ROOT / prior['rootRelativePath'] / name).read_bytes()).hexdigest() == prior[key]
    old = json.loads((ROOT / prior['rootRelativePath'] / 'receipt.json').read_bytes())
    assert old['severityCounts'] == {'P1': 0, 'P2': 3} and old['independentReviewerSolConsumed1'] == 1
    for key, value in [('independentReviewerSolConsumed', 1), ('primaryModelTrajectories', 0), ('automaticRetries', 0), ('delegations', 0), ('nativeProviderBytesAvailable', False), ('certifiesNativeConnection', False), ('certifiesBehavior', False), ('certifiesSkillGate', False), ('certifiesProductCompletion', False)]:
        assert receipt[key] == summary[key] == value
    assert summary['sourceGuardObservations']['fullyCompliantReviewProcedure'] is False
    print(json.dumps(dict(status='component_artifacts_verified_with_guard_limitation', sourceCommit=source, sourceFileCount=9, independentP1=0, independentP2=0, allSkillCount=320, componentCount=26, adversarialCount=8, previousFailurePreserved=True, certifiesNativeConnection=False, certifiesSkillGate=False)))


if __name__ == '__main__':
    main()
