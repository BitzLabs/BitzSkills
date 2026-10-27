"""固定sourceとローカル原証拠を再照合する。モデル呼出し0。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import source_guard
import production_cli_probe as probe


def main():
    summary = json.loads(Path(__file__).with_name('summary.json').read_bytes())
    source = summary['sourceCommit']
    contract = json.loads(source_guard.git(ROOT, 'show', source + ':' + summary['contract']))
    guard = source_guard.verify(ROOT, source, contract['sourceFiles'])
    base = ROOT / summary['localEvidenceRoot']
    assert not any(p.is_symlink() for p in [base, *base.parents]) and base.stat().st_mode & 0o777 == 0o700
    for name, expected in summary['artifactSha256'].items():
        path = base / name
        assert not path.is_symlink() and path.stat().st_mode & 0o777 == 0o600
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    receipt = json.loads((base / 'receipt.json').read_bytes())
    parent = json.loads((base / 'parent-verification.json').read_bytes())
    clean = json.loads((base / 'parent-clean-unit.json').read_bytes())
    reservation = json.loads((base / 'reservation.json').read_bytes())
    assert receipt['status'] == 'passed' and receipt['severityCounts'] == summary['severityCounts'] == {'P1':0,'P2':0}
    assert receipt['reviewerGuardBeforeInitialReadsPerformed'] is True
    assert receipt['actualTestCounts'] == contract['testCounts'] == {'ledger':13,'probe':8,'allSkills':341}
    assert receipt['actualTestExitCodes'] == {'ledger':0,'probe':0,'allSkills':0}
    for record in [receipt, parent, clean]:
        assert record['sourceCommit'] == source
        for observed in record['sourceGuards'].values():
            assert observed['sourceCommit'] == source and observed['status'] == 'fixed_source_matches'
            assert observed['sourceSha256'] == guard['sourceSha256']
    for point in ['before','after']:
        assert json.loads((base / ('reviewer-' + point + '.json')).read_bytes()) == receipt['sourceGuards'][point]
    assert receipt['reportSha256'] == summary['artifactSha256']['review.md']
    assert reservation['sourceCommit'] == source and reservation['attemptReserved'] == reservation['maximumIndependentReviewerCalls'] == 1
    assert reservation['sourceGuard']['sourceSha256'] == guard['sourceSha256']
    assert clean['actualExitCode'] == 0 and clean['cleanTreeBeforeAndAfter'] is True
    assert clean['logSha256'] == reservation['parentCleanUnitLogSha256'] == summary['artifactSha256']['parent-clean-unit.log']
    for key, count in contract['testCounts'].items():
        row = receipt['testLogs'][key]
        path = base / (key + '-tests.log')
        assert Path(row['logPath']) == path and row['logSha256'] == summary['artifactSha256'][path.name]
        assert row['count'] == count and row['exitCode'] == 0
        raw = path.read_text()
        assert re.search(r'Ran ' + str(count) + r' tests', raw) and raw.strip().endswith('OK')
    for name,count in [('parent-clean-unit.log',341),('parent-component-tests.log',21)]:
        raw = (base / name).read_text()
        assert re.search(r'Ran ' + str(count) + r' tests',raw) and raw.strip().endswith('OK')
    assert parent['parentComponentTestCount'] == 21 and parent['parentComponentExitCode'] == 0
    for item in contract['localProbeEvidence']:
        original = ROOT / item['root']
        assert hashlib.sha256((original / 'receipt.json').read_bytes()).hexdigest() == item['receiptSha256']
        raw = (original / 'local-request.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['requestSha256']
        original_receipt = json.loads((original / 'receipt.json').read_bytes())
        assert original_receipt['sourceCommit'] == item['sourceCommit']
        assert original_receipt['status'] == 'local_tool_declaration_stopped' and original_receipt['paidModelCalls'] == 0
        names = probe.declared_tools(json.loads(raw))
        assert 'functions.exec' in names and 'collaboration.spawn_agent' in names and len(names) == 10
    for key,value in [('independentReviewerSolConsumed',1),('primaryModelTrajectories',0),('automaticRetries',0),('delegations',0),('nativeProviderBytesAvailable',False),('certifiesNativeProvider',False),('certifiesSkillGate',False),('certifiesProductCompletion',False)]:
        assert type(receipt[key]) is type(value) and receipt[key] == summary[key] == value
    assert summary['closedTwoToolPolicyVerified'] is False
    print(json.dumps(dict(status='public_infrastructure_artifacts_verified',sourceCommit=source,sourceFileCount=10,independentP1=0,independentP2=0,allSkills=341,parentComponents=21,originalCliRecordsPreserved=True,closedTwoToolPolicyVerified=False,primaryModelTrajectories=0,certifiesSkillGate=False)))


if __name__ == '__main__':
    main()
