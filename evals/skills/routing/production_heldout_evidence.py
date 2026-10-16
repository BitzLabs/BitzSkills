"""保持一次の原bytes/入力/実行構成/native/rolloutを内部照合する。採点・起動なし。"""
from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType

import production_heldout_launch as launch
import production_primary_review as primary
import production_canary_evidence as inventory

x, preflight = launch.x, launch.preflight
io, require, trace = x.io, x.require, x.trace
VERSION = 'heldout-primary-original-binding-0.1.0'
ADDITIONAL = frozenset({'deployment.json', 'sdk-manifest.json', 'runtime-manifest.json',
    'launch-settings.json', 'resource-guards.json', 'prelaunch-review.json', 'prelaunch-report.json',
    'local-isolation-proof.json'})
RECEIPT_KEYS = {'version', 'sourceCommit', 'slot', 'cwd', 'artifactSha256', 'elapsedSeconds',
    'namespaceExitCode', 'timedOut', 'primaryModelTrajectories', 'independentReviewPerformed',
    'automaticRetries', 'phaseComplete', 'certifiesSkillGate'}


@dataclass(frozen=True, repr=False)
class HeldoutCapture:
    bound: x.BoundExecution
    ordinal: int
    source_repository: Path
    original_items: tuple[tuple[str, bytes], ...]
    receipt_raw: bytes
    manifest_raw: bytes
    schema_raw: bytes
    context_raw: bytes

    @property
    def originals(self):
        return MappingProxyType(dict(self.original_items))


def bind_originals(bound, ordinal, originals, receipt_raw, manifest_raw, schema_raw, context_raw, *, source_repository):
    x.rebound(bound)
    require(isinstance(source_repository, Path) and source_repository.is_absolute() and '..' not in source_repository.parts,
        'heldout original source repository')
    slot = bound.slot(ordinal)
    require(all(isinstance(raw, bytes) for raw in [receipt_raw, manifest_raw, schema_raw, context_raw]),
        'heldout original bytes')
    receipt = x.inputs.parse(receipt_raw)
    require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS and receipt['version'] == VERSION
        and receipt['sourceCommit'] == bound.contract['sourceCommit'] and trace.json_equal(receipt['slot'], slot)
        and receipt['cwd'] == str(bound.stage_root(ordinal, 'primary')/'work'), 'heldout receipt identity')
    require(trace.json_equal({key: receipt[key] for key in ['namespaceExitCode', 'timedOut', 'primaryModelTrajectories',
        'independentReviewPerformed', 'automaticRetries', 'phaseComplete', 'certifiesSkillGate']},
        dict(namespaceExitCode=0, timedOut=False, primaryModelTrajectories=1, independentReviewPerformed=False,
            automaticRetries=0, phaseComplete=False, certifiesSkillGate=False)), 'heldout failed receipt')
    seconds = receipt['elapsedSeconds']
    require(type(seconds) in {int, float} and seconds >= 0 and (type(seconds) is int or math.isfinite(seconds)),
        'heldout finite elapsed')
    declared = receipt['artifactSha256']
    require(isinstance(declared, dict) and inventory.FIXED_ARTIFACTS | ADDITIONAL <= set(declared),
        'heldout original inventory')
    for name, digest in declared.items():
        if name not in ADDITIONAL:
            inventory.artifact_name(name)
        io.pin(digest)
    groups = {name.split('/')[1] for name in declared if name.startswith('rollout-traces/')}
    require(len(groups) == 1, 'heldout single original rollout')
    prefix = 'rollout-traces/'+next(iter(groups))+'/'
    require({prefix+'manifest.json', prefix+'trace.jsonl'} <= set(declared)
        and any(name.startswith(prefix+'payloads/') for name in declared), 'heldout complete rollout')
    require(isinstance(originals, (dict, MappingProxyType)) and set(originals) == set(declared)
        and all(isinstance(raw, bytes) for raw in originals.values()), 'heldout original buffer inventory')
    require({name: io.sha(raw) for name, raw in originals.items()} == declared, 'heldout original hash drift')
    d = x.deployment_for_execution(bound.execution_raw, bound.deployment_raw)
    for key, raw in [('snapshotManifest', manifest_raw), ('decisionSchema', schema_raw), ('contextProfile', context_raw)]:
        require(bound.contract['pins'][key] == io.sha(raw), 'heldout fixed resource hash')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    require(manifest['sourceCommit'] == bound.contract['sourceCommit'] and len(manifest['resources']) == 72,
        'heldout original product identity')
    require(originals['contract.json'] == bound.execution_raw and originals['deployment.json'] == bound.deployment_raw
        and originals['reservation.json'] == io.encoded(launch.primary_identity(bound, ordinal))
        and originals['model-input.json'] == bound.matrix.payloads[(ordinal-1)//2]
        and originals['decision-schema.json'] == schema_raw, 'heldout consumed input drift')
    require(originals['invocation.json'] == io.encoded(launch.invocation(source_repository,
        bound.execution_raw, bound.deployment_raw, launch.primary_identity(bound, ordinal))), 'heldout invocation drift')
    require(originals['launch-settings.json'] == launch.launch_settings(bound.execution_raw, bound.deployment_raw),
        'heldout launch settings drift')
    sdk_files = preflight.public.sdk_manifest(originals['sdk-manifest.json'], d)
    runtime_spec = preflight.public.capture.fixed_runtime.specification(originals['runtime-manifest.json'], d)
    require(trace.json_equal(x.inputs.parse(originals['config.json']), preflight.public.capture.config_for(
        bound.stage_root(ordinal, 'primary'), d, repository=source_repository)), 'heldout actual configuration drift')
    launch.prelaunch_review(bound.execution_raw, bound.deployment_raw, originals['prelaunch-review.json'],
        originals['prelaunch-report.json'], originals['local-isolation-proof.json'])
    guards = x.inputs.parse(originals['resource-guards.json'])
    require(isinstance(guards, dict) and set(guards) == {'before', 'invoke', 'after'}
        and all(trace.json_equal(value, guards['before']) for value in guards.values()), 'heldout three resource guards')
    proof = guards['before']
    require(isinstance(proof, dict) and set(proof) == preflight.PROOF_KEYS, 'heldout resource proof inventory')
    bound.ledger_contract(io.encoded(proof))
    require(proof.get('deploymentSha256') == io.sha(bound.deployment_raw)
        and proof.get('casesSha256') == x.inputs.parse(bound.input_contract_raw)['inputSha256']['cases']
        and proof.get('snapshotManifestSha256') == io.sha(manifest_raw) and proof.get('snapshotResourceCount') == 72
        and proof.get('baselineProductSource') == preflight.BASELINE_PRODUCT_SOURCE
        and proof.get('productResourcesSha256') == io.sha(io.encoded(manifest['resources']))
        and isinstance(proof.get('sourceSha256'), dict) and set(proof['sourceSha256']) == set(preflight.SOURCE_FILES)
        and proof.get('contextProfileSha256') == io.sha(context_raw)
        and proof.get('contextDate') == x.inputs.parse(context_raw)['date'], 'heldout resource proof binding')
    for value in proof['sourceSha256'].values():
        io.pin(value)
    require(trace.json_equal({key: proof[key] for key in ['sdkManifestSha256', 'sdkFileCount', 'sdkTreeSha256',
        'decisionSchemaSha256', 'models', 'reservations', 'launchEnabled', 'certifiesSkillGate', 'certifiesRelease']},
        dict(sdkManifestSha256=io.sha(originals['sdk-manifest.json']), sdkFileCount=len(sdk_files),
            sdkTreeSha256=d['sdkTreeSha256'], decisionSchemaSha256=io.sha(schema_raw), models=0,
            reservations=0, launchEnabled=False, certifiesSkillGate=False, certifiesRelease=False))
        and trace.json_equal(proof['runtime'], dict(status='fixed_runtime_bytes_match',
            runtimeManifestSha256=d['runtimeManifestSha256'], codexPath=d['codexPath'], files=len(runtime_spec['files']))),
        'heldout resource proof runtime SDK or scope drift')
    calibration = proof['originalCalibration']
    require(isinstance(calibration, dict) and calibration.get('status') == 'original_local_calibration_matches'
        and calibration.get('calibrationManifestSha256') == d['calibrationManifestSha256']
        and trace.json_equal({key: calibration.get(key) for key in ['paidModelCalls', 'primaryModelTrajectories',
            'certifiesProviderWireBodies']}, dict(paidModelCalls=0, primaryModelTrajectories=0,
            certifiesProviderWireBodies=False)), 'heldout original calibration proof')
    require(trace.json_equal(x.inputs.parse(originals['runtime-result.json']),
        dict(exitCode=0, forcedShutdown=False, captureIntegrity=True))
        and trace.json_equal(x.inputs.parse(originals['isolated-result.json']), dict(sdkErrorType=None))
        and originals['version.stdout'] == b'codex-cli 0.160.1\n' and originals['version.stderr'] == b'',
        'heldout original native terminal')
    return HeldoutCapture(bound, ordinal, source_repository, tuple(sorted(originals.items())),
        receipt_raw, manifest_raw, schema_raw, context_raw)


def verify_complete(context):
    """戻り値は私的な判断/usageを含む。公開には集計とhashだけを別途投影する。"""
    require(isinstance(context, HeldoutCapture), 'heldout capture required')
    expected = bind_originals(context.bound, context.ordinal, context.originals, context.receipt_raw,
        context.manifest_raw, context.schema_raw, context.context_raw, source_repository=context.source_repository)
    require(expected == context, 'heldout immutable original drift')
    receipt = x.inputs.parse(context.receipt_raw)
    catalog = dict(zip(x.inputs.INPUT_NAMES, context.bound.raw_inputs))['catalog']
    native = primary.native(context.originals, context.manifest_raw, catalog, context.schema_raw,
        cwd=receipt['cwd'], path_policy='six-skill')
    rollout = primary.correlate_rollout(context.originals, native['native'], context.context_raw,
        context.receipt_raw, io.sha(context.receipt_raw), receipt['elapsedSeconds'])
    return dict(status='heldout_original_bytes_and_native_correlated', slot=context.bound.slot(context.ordinal),
        receiptSha256=io.sha(context.receipt_raw), artifactSha256=receipt['artifactSha256'], **native, rollout=rollout,
        originalInputMatched=True, rawPayloadCorrelationVerified=True, independentReviewPerformed=False,
        ledgerFinalized=False, eligibleForMeasurement=False, certifiesSkillGate=False)
