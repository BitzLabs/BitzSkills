"""設計準備の記録を原bytesと確定refに照合する。モデル/一次/模擬起動0。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace
import source_guard as guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    meta = public['verification']
    original_root = ROOT / meta['outputRelativeRoot']
    trace.require(not any(p.is_symlink() for p in (original_root, *original_root.parents)), 'original output symlink')
    raw = (original_root / 'summary.json').read_bytes()
    trace.require(sha(raw) == meta['summarySha256'], 'original summary drift')
    original = trace.strict_json(raw)
    source = public['sourceCommit']
    trace.require(original['sourceCommit'] == source and original['contractPath'] == public['contractPath'] and
                  original['status'] == 'canary_design_preparation_checked', 'original preparation binding')
    contract = trace.strict_json(guard.git(ROOT, 'show', source + ':' + public['contractPath']))
    expected = {path: sha(guard.git(ROOT, 'show', source + ':' + path)) for path in contract['sourceFiles']}
    before, after = original['sourceGuards']['before'], original['sourceGuards']['after']
    trace.require(before == after and before['sourceCommit'] == before['observedHead'] == source and
                  before['sourceSha256'] == expected and before['status'] == 'fixed_source_matches', 'original source guards')
    inventory = []
    for path in contract['payloadFiles']:
        body = guard.git(ROOT, 'show', source + ':' + path)
        inventory.append(dict(path=path, bytes=len(body), sha256=sha(body)))
    trace.require(len(inventory) == 6 and len({item['path'] for item in inventory}) == 6 and
                  inventory == original['payloadInventory'] and
                  sum(item['bytes'] for item in inventory) == original['payloadBytes'] == public['payloadBytes'], 'payload inventory drift')
    tests = original['tests']
    for name, key in [('tests.stdout', 'stdoutSha256'), ('tests.stderr', 'stderrSha256')]:
        trace.require(sha((original_root / name).read_bytes()) == tests[key], 'original test stream drift')
    stderr = (original_root / 'tests.stderr').read_bytes()
    matched = re.search(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK\s*$', stderr)
    trace.require(matched is not None and int(matched[1]) == tests['count'] == meta['testCount'] and
                  float(matched[2]) == tests['seconds'] == meta['testSeconds'] and
                  tests['exitCode'] == meta['testExitCode'] == 0 and tests['stderrSha256'] == meta['stderrSha256'], 'actual test result mismatch')
    old = contract['previousReview']
    for name, key in [('receipt.json', 'receiptSha256'), ('response.json', 'responseSha256')]:
        trace.require(sha((ROOT / old['outputRelativeRoot'] / name).read_bytes()) == old[key], 'previous review drift')
    trace.require(not (ROOT / public['approvalReview']['outputRelativeRoot']).exists(), 'approval pending but model output exists')
    trace.require(public['approvalReview']['status'] == 'rejected-before-process-creation' and
                  all(public['approvalReview'][key] == 0 for key in ['modelReservations', 'modelInvocations', 'payloadTransmissions']), 'pre-start rejection counts')
    trace.require(all(public[key] == 0 for key in ['primaryModelTrajectories', 'independentSolInvocations', 'automaticRetries', 'delegations']) and
                  public['eligibleForMeasurement'] is public['phaseComplete'] is False, 'scope drift')
    print(json.dumps(dict(status='recorded_canary_design_preparation_matches_original_bytes', tests=tests['count'],
                         payloadFiles=len(inventory), payloadBytes=public['payloadBytes'],
                         independentSolInvocations=0, primaryModelTrajectories=0,
                         modelOutputAbsent=True, eligibleForMeasurement=False), ensure_ascii=False))


if __name__ == '__main__':
    run()
