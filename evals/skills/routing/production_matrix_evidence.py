"""行列の原bytesと固定入力を束縛しRPC/Host/native/rolloutを検査する。

この部品はsource/runtime現物、実起動、独立意味、安全採点、台帳確定を認定しない。
原取得器と起動前の現物検査への接続は別工程。ファイル読取りやモデル起動は行わない。
"""
from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType

import production_canary_evidence as inventory
import production_matrix_ledger as matrix
import production_primary_review as primary
import production_trace as trace

io = matrix.io
require = trace.require
VERSION = 'public-matrix-original-binding-0.1.0'
PROVIDER_VERSION = 'public-matrix-original-binding-0.1.1'
PROVIDER_ARTIFACTS = frozenset({'deployment.json','sdk-manifest.json','runtime-manifest.json',
    'launch-settings.json','resource-guards.json','capture-environment.json'})
RECEIPT_KEYS = {'version', 'sourceCommit', 'slot', 'cwd', 'artifactSha256', 'elapsedSeconds',
                'namespaceExitCode', 'timedOut', 'primaryModelTrajectories', 'independentReviewPerformed',
                'automaticRetries', 'phaseComplete', 'certifiesSkillGate'}


@dataclass(frozen=True)
class MatrixCapture:
    bound: matrix.BoundExecution
    ordinal: int
    original_items: tuple[tuple[str, bytes], ...]
    receipt_raw: bytes
    manifest_raw: bytes
    schema_raw: bytes
    context_raw: bytes

    @property
    def originals(self):
        return MappingProxyType(dict(self.original_items))


def bind_originals(bound, ordinal, originals, receipt_raw, manifest_raw, schema_raw, context_raw):
    require(bound == matrix.bind(bound.execution_raw, bound.matrix.contract_raw,
            **dict(zip(matrix.inputs.INPUT_NAMES, bound.raw_inputs))), 'matrix fixed input drift')
    slot = bound.slot(ordinal)
    require(all(isinstance(raw, bytes) for raw in [receipt_raw, manifest_raw, schema_raw, context_raw]),
            'matrix fixed original bytes')
    receipt = trace.strict_json(receipt_raw)
    require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS and receipt['version'] in {VERSION,PROVIDER_VERSION},
            'matrix receipt inventory')
    require(receipt['sourceCommit'] == slot['sourceCommit'] and trace.json_equal(receipt['slot'], slot),
            'matrix receipt slot or source drift')
    cwd = receipt['cwd']
    require(isinstance(cwd, str) and Path(cwd).is_absolute() and cwd == Path(cwd).as_posix()
            and '..' not in Path(cwd).parts and tuple(Path(cwd).parts[-4:]) == (
                '.venv', bound.contract['outputRelativeRoot'].split('/')[1], f'attempt-{ordinal:04d}', 'work'),
            'matrix capture cwd boundary')
    require(trace.json_equal({k: receipt[k] for k in ['namespaceExitCode', 'timedOut', 'primaryModelTrajectories',
            'independentReviewPerformed', 'automaticRetries', 'phaseComplete', 'certifiesSkillGate']},
            dict(namespaceExitCode=0, timedOut=False, primaryModelTrajectories=1, independentReviewPerformed=False,
                 automaticRetries=0, phaseComplete=False, certifiesSkillGate=False)), 'matrix failed capture or scope drift')
    seconds = receipt['elapsedSeconds']
    require(type(seconds) in {int, float} and seconds >= 0 and (type(seconds) is int or math.isfinite(seconds)),
            'matrix finite capture elapsed')
    declared = receipt['artifactSha256']
    additions = PROVIDER_ARTIFACTS if receipt['version'] == PROVIDER_VERSION else frozenset()
    require(isinstance(declared, dict) and inventory.FIXED_ARTIFACTS | additions <= set(declared),
            'matrix original required inventory')
    # 全名前を検査してから原内容を消費する。opaque・未知pathは受け取らない。
    for name, digest in declared.items():
        if name not in additions:inventory.artifact_name(name)
        io.pin(digest)
    groups = {name.split('/')[1] for name in declared if name.startswith('rollout-traces/')}
    require(len(groups) == 1, 'matrix single original rollout')
    prefix = 'rollout-traces/'+next(iter(groups))+'/'
    require({prefix+'manifest.json', prefix+'trace.jsonl'} <= set(declared)
            and any(name.startswith(prefix+'payloads/') for name in declared), 'matrix complete original rollout')
    require(isinstance(originals, (dict, MappingProxyType)) and set(originals) == set(declared)
            and all(isinstance(raw, bytes) for raw in originals.values()), 'matrix original buffer inventory')
    require({name: io.sha(raw) for name, raw in originals.items()} == declared, 'matrix original hash drift')
    for key, raw in [('snapshotManifest', manifest_raw), ('decisionSchema', schema_raw), ('contextProfile', context_raw)]:
        require(bound.contract['pins'][key] == io.sha(raw), 'matrix fixed '+key+' drift')
    trace.manifest_view(manifest_raw)
    trace.jsonschema.Draft202012Validator.check_schema(trace.strict_json(schema_raw))
    require(originals['contract.json'] == bound.execution_raw
            and originals['reservation.json'] == io.encoded(slot)
            and originals['model-input.json'] == bound.matrix.payloads[(ordinal-1)//2]
            and originals['decision-schema.json'] == schema_raw, 'matrix consumed fixed input drift')
    require(trace.json_equal(trace.strict_json(originals['runtime-result.json']),
            dict(exitCode=0, forcedShutdown=False, captureIntegrity=True))
            and trace.json_equal(trace.strict_json(originals['isolated-result.json']), dict(sdkErrorType=None))
            and originals['version.stdout'] == b'codex-cli 0.160.1\n' and originals['version.stderr'] == b'',
            'matrix native execution terminal drift')
    return MatrixCapture(bound, ordinal, tuple(sorted(originals.items())), receipt_raw, manifest_raw, schema_raw, context_raw)


def verify_complete(context):
    require(isinstance(context, MatrixCapture), 'matrix bound capture required')
    # 手製dataclass、後から差替えたtuple、固定資源の差替えも検査する。
    rebound = bind_originals(context.bound, context.ordinal, context.originals, context.receipt_raw,
                             context.manifest_raw, context.schema_raw, context.context_raw)
    require(rebound == context, 'matrix immutable capture drift')
    receipt = trace.strict_json(context.receipt_raw)
    catalog_raw = context.bound.raw_inputs[matrix.inputs.INPUT_NAMES.index('catalog')]
    native = primary.native(context.originals, context.manifest_raw, catalog_raw, context.schema_raw, cwd=receipt['cwd'])
    rollout = primary.correlate_rollout(context.originals, native['native'], context.context_raw,
                                       context.receipt_raw, io.sha(context.receipt_raw), receipt['elapsedSeconds'])
    return dict(status='matrix_original_bytes_and_native_correlated', slot=context.bound.slot(context.ordinal),
        receiptSha256=io.sha(context.receipt_raw), artifactSha256=receipt['artifactSha256'], **native, rollout=rollout,
        originalInputMatched=True, rawPayloadCorrelationVerified=True, sourceRuntimeOnDiskVerified=False,
        launchEnvironmentVerified=False, independentReviewPerformed=False, ledgerFinalized=False,
        eligibleForMeasurement=False, certifiesSkillGate=False, certifiesRelease=False)
