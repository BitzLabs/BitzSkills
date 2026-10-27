"""原stderrを復号せず、固定ref・失敗保持・親試験・診断集計を再照合する。"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import native_actor_v02 as actor
HERE=Path(__file__).resolve().parent
summary=json.loads((HERE/'summary.json').read_bytes())
actor.verify(summary['correctedExecutionSource'])
assert hashlib.sha256((ROOT/actor.CONTRACT).read_bytes()).hexdigest()==summary['correctedContractSha256']
old=actor.PRIVATE/'native-authoring-01/preparation'
for name,expected in summary['previousNative']['privateArtifactSha256'].items():
    path=old/name
    raw=actor.collection.legacy.private_file(path)
    assert hashlib.sha256(raw).hexdigest()==expected
    assert path.stat().st_uid==os.geteuid()
    assert path.stat().st_mode&0o777==0o600
assert old.stat().st_mode&0o777==0o700
repo_receipt=ROOT/'.venv/routing-native-authoring-01/preparation-result.json'
assert hashlib.sha256(repo_receipt.read_bytes()).hexdigest()==summary['previousNative']['executionReceiptSha256']
assert (old/'trace.jsonl').stat().st_size==0
assert (old/'stderr.log').stat().st_size==197
assert not (ROOT/'.venv/routing-native-authoring-02').exists()
assert not (actor.PRIVATE/'native-authoring-02').exists()
assert not (actor.PRIVATE/'cases.json').exists()
assert not (actor.PRIVATE/'evidence.json').exists()
local=ROOT/'.venv/held-out-single-replacement-05'
for name,expected in summary['localArtifactSha256'].items():
    assert hashlib.sha256((local/name).read_bytes()).hexdigest()==expected
checks={'parent-after-native-stop-actor-unit.log':16,'parent-after-native-stop-collection-unit.log':14,
        'parent-native-shadow-final-unit.log':9,'parent-native-shadow-final-all-unit.log':285}
for name,count in checks.items():
    raw=(local/name).read_bytes()
    assert f'Ran {count} tests in '.encode() in raw and raw.rstrip().endswith(b'OK')
paths={'readonlyAndMaskedHomeSummary':ROOT/'.venv/native-bootstrap-diagnostics-01/summary.json',
       'selectiveShadowSummary':ROOT/'.venv/native-bootstrap-shadow-diagnostics-02/summary.json',
       'fullNamespaceSummary':ROOT/'.venv/native-bootstrap-full-03/summary.json',
       'offlineBootstrapCode':ROOT/'.venv/native-bootstrap-full-03.py'}
for name,path in paths.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest()==summary['diagnosticArtifactSha256'][name]
assert (HERE/'offline-bootstrap.py').read_bytes()==paths['offlineBootstrapCode'].read_bytes()
full=json.loads(paths['fullNamespaceSummary'].read_bytes())
assert full['networkNamespaceIsolated'] and full['threadStarted']
assert not full['bootstrapFailure'] and not full['readOnlyFilesystem']
assert full['actualExitCode']==-15 and full['errorType']=='TimeoutExpired'
assert not full['certifiesModelCompletion'] and not full['certifiesPreparation']
source_guard=json.loads((local/'parent-native-stop-final-source-guard.json').read_bytes())
assert source_guard['status']=='fixed_source_matches'
assert source_guard['sourceCommit']==summary['collectionSource']
assert source_guard['inputChecks']['candidateResourcesGitMatched']==71
print(json.dumps({'status':'artifact_source_and_stop_bindings_verified','privateArtifactsVerified':7,
                  'newSourceFiles':13,'oldSourceFiles':7,'collectionSourceFiles':15,
                  'candidateResourcesGitMatched':71,'allSkillTests':285,
                  'correctedNativeModelStarted':False,'casesSaved':0,
                  'certifiesPreparation':False,'certifiesSkillGate':False}))
