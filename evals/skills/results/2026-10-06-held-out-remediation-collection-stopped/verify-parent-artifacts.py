import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path('/home/hide/BitzLabs/BitzSkills/.venv/skills-integration-worktree')
PRIVATE = Path('/home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006')
SOURCE = 'f760649f44a3d7bb2bd723181e3ab155b81d4140'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT)

EXPECTED = {
    'cases.json': '17327fa66c83ec69d2357dea9279923bb2207ce4a4e11256fb435c864013add8',
    'creation-audit.json': '508bd1f86b82dbafd35f14a94e970bf28e7b2d540bdaba959f595951bc0840a8',
    'creation-notes.md': '9285488431e6d1ec29319935ef87aeb7837671012f932152418115735bd194a7',
    'creation-receipt.json': '45a1f209c5467c7a9c108a09f5fe33b2dd3174b11a91555013a817066aaa0ed4',
    'evidence.json': 'f2acdf3aae1bcedb3a8d7bc978104979051e1a34e64170d5ebfee408c58448c2',
    'retention.json': '3a9007b4c1925cefe4b213426895a7ef79ffd520eceb5f5a799f22bebffc18fa',
    'source-guard-presave.json': '80d511bd25d80d7cfa63a3e0f863d9b200e39cde1c6849ca984d93524b895118',
    'source-guard-start.json': '80d511bd25d80d7cfa63a3e0f863d9b200e39cde1c6849ca984d93524b895118',
    'independent-review.md': 'cd3364b0d3f6cc03c25f1a17a6af76178edb3b37a9efd130429fa92289ffb078',
    'independent-receipt.json': '67a1bde0bcf479b16ccfba02b775bdaff27dfdf05c43f2bcc9ed3d69d7869937',
    'independent-audit.json': '887f78254107b8a73ec076e83b926b7e6041c6c44e6e63d6ef1d149ba295664b',
    'independent-audit.log': 'dc1fcb3131fd7bf333b5b0327b1507881c99c9b2cf9a6ed44bdabe0218dd561a',
    'independent-source-guard.json': 'bed9e01b1c4f18ecf75cc802ab0a5893827fa135678d47d7aee8b6343b0d3ee0',
    'independent-invocation-error.json': 'a35b284bc47c862766429f3852234cc2c32e26832d66768448253a8e58726d49',
}


def main():
    private = PRIVATE / 'collection-04'
    assert not private.is_symlink() and stat.S_IMODE(private.stat().st_mode) == 0o700
    assert {p.name for p in private.iterdir()} == set(EXPECTED)
    for name, digest in EXPECTED.items():
        path = private / name
        assert path.is_file() and not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert sha(path.read_bytes()) == digest

    contract = json.loads(git('show', SOURCE + ':evals/skills/routing/held-out-collection-v0.4.json'))
    assert len(contract['sourceFiles']) == 12
    actual_sources = {}
    for path in contract['sourceFiles']:
        digest = sha(git('show', SOURCE + ':' + path))
        assert digest == sha((ROOT / path).read_bytes())
        actual_sources[path] = digest
    assert len(contract['inputSha256']) == 7
    for path, digest in contract['inputSha256'].items():
        assert sha((ROOT / path).read_bytes()) == digest

    candidate = contract['candidate']
    snapshot = ROOT / candidate['snapshotRelativePath']
    manifest_raw = (snapshot / 'manifest.json').read_bytes()
    assert sha(manifest_raw) == candidate['manifestSha256']
    manifest = json.loads(manifest_raw)
    assert len(manifest['skills']) == 6 and len(manifest['resources']) == 71
    assert manifest['sourceCommit'] == candidate['sourceCommit']
    for path, digest in manifest['resources'].items():
        assert sha((snapshot / path).read_bytes()) == digest
        assert path.startswith('resources/')
        source_path = 'plugins/' + path.removeprefix('resources/')
        assert sha(git('show', candidate['sourceCommit'] + ':' + source_path)) == digest

    creator = json.loads((private / 'creation-receipt.json').read_text())
    reviewer = json.loads((private / 'independent-receipt.json').read_text())
    assert creator['source'] == reviewer['sourceCommit'] == SOURCE
    for receipt in [creator, reviewer]:
        for name, digest in receipt['filesSha256'].items():
            assert sha((private / name).read_bytes()) == digest
    assert reviewer['existingFilesUnchanged'] is True
    assert reviewer['casesSha256'] == EXPECTED['cases.json']
    assert reviewer['evidenceSha256'] == EXPECTED['evidence.json']
    assert reviewer['retentionSha256'] == EXPECTED['retention.json']
    assert reviewer['creationReceiptSha256'] == EXPECTED['creation-receipt.json']
    assert reviewer['candidate'] == candidate
    assert reviewer['environment'] == contract['environment']
    assert reviewer['status'] == 'stopped_on_p2'
    assert reviewer['severityCounts'] == {'P1': 0, 'P2': 1}
    assert reviewer['affectedCaseCount'] == 1
    assert reviewer['routingSemanticsPassedCount'] == 12
    assert reviewer['retentionFullFieldsMatched'] is True
    assert reviewer['novelNewCaseCount'] == 2
    assert reviewer['nativeAuditExitCode'] == reviewer['finishGuardExitCode'] == 0
    assert creator['creatorSolConsumed'] == reviewer['independentReviewerSolConsumed'] == 1
    for receipt in [creator, reviewer]:
        assert receipt['primaryModelTrajectories'] == receipt['automaticRetries'] == receipt['delegations'] == 0

    guards = [json.loads((private / p).read_text()) for p in ['source-guard-start.json', 'source-guard-presave.json']]
    guards += [creator['finishSourceGuard'], reviewer['presaveGuard'], reviewer['finishGuard']]
    for guard in guards:
        assert guard['status'] == 'fixed_source_matches' and guard['sourceCommit'] == SOURCE
        assert guard['headIsCondition'] is False and guard['sourceSha256'] == actual_sources

    audit = json.loads((private / 'independent-audit.json').read_text())
    parent_audit = json.loads((ROOT / '.venv/held-out-remediation-04/parent-after-review-collection-audit.json').read_text())
    assert audit == parent_audit
    assert audit['status'] == 'mechanical_checks_passed'
    assert audit['heldOut']['sha256'] == EXPECTED['cases.json']
    assert audit['evidenceSha256'] == EXPECTED['evidence.json']
    assert audit['semanticNovelty'] == audit['routingSemantics'] == 'requires_independent_review'
    error = json.loads((private / 'independent-invocation-error.json').read_text())
    assert error['exitCode'] == 127 and error['paidRetryCount'] == 0 and error['correctionCount'] == 1

    cases = json.loads((private / 'cases.json').read_text())['cases']
    report = (private / 'independent-review.md').read_text()
    headings = re.findall(r'^### (SE-[0-9]+)\s*$', report, re.M)
    assert len(headings) == 12 and set(headings) == {case['caseId'] for case in cases}

    old = PRIVATE / 'collection-03'
    old_creator = json.loads((old / 'creation-receipt.json').read_text())
    for name, digest in old_creator['artifactSha256'].items():
        assert sha((old / name).read_bytes()) == digest
    restored = json.loads((ROOT / 'evals/skills/results/2026-10-06-held-out-review-restored/summary.json').read_text())
    for name, digest in restored['privateArtifactSha256'].items():
        assert sha((old / name).read_bytes()) == digest
    old_review = json.loads((old / 'independent-receipt.json').read_text())
    assert len(old_review['existingSevenBeforeSha256']) == 7
    for name, digest in old_review['existingSevenBeforeSha256'].items():
        assert sha((old / name).read_bytes()) == digest
    assert sha((old / 'cases.json').read_bytes()) == restored['casesSha256']
    assert sha((old / 'novelty.json').read_bytes()) == restored['noveltySha256']
    assert sha((PRIVATE / 'cases.json').read_bytes()) == 'b59681809301ea36a7b56f7b3f3d95d167776494176ea614d8d9577f21f995b7'
    assert len(list(old.iterdir())) == 13

    print(json.dumps({
        'status': 'artifact_source_bindings_verified',
        'sourceCommit': SOURCE, 'sourceFileCount': 12, 'inputFileCount': 7,
        'candidateResourceCount': 71, 'privateArtifactsVerified': 14,
        'creatorFilesUnchanged': 8, 'oldCollectionArtifactBindingsVerified': 13,
        'oldCollectionFileCount': 13, 'excludedCollectionsUnchanged': 2,
        'privateArtifactSha256': EXPECTED, 'sourceSha256': actual_sources,
        'nativeGuardCount': len(guards), 'reportCaseCoverage': 12,
        'semanticDecisionAdoptedFromIndependentReceipt': True,
        'severityCounts': reviewer['severityCounts'], 'affectedCaseCount': 1,
        'semanticStatus': reviewer['status'],
        'certifiesSkillGate': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'errorType': type(error).__name__}))
        raise SystemExit(1)
