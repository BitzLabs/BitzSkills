"""取得構成とRPC/rolloutを固定bytesへ束縛。実起動・予約・適格性は認定しない。

v0.1.1の6追加原を消費する。旧v0.1.0や4枠Canaryへreceiptを書換えない。
現物再照合・argv権限・独立開始前検分・安全意味・台帳確定は別工程。
"""
from pathlib import Path
import production_matrix_evidence as evidence
import production_matrix_preflight as preflight

io=evidence.io
trace=evidence.trace
require=trace.require
ENV_VERSION='public-matrix-capture-environment-0.1.0'


def absolute_root(value):
    require(isinstance(value,Path) and value.is_absolute() and '..' not in value.parts
        and str(value)==value.as_posix(),'matrix environment absolute root')
    return value


def environment_spec(context,source_repository,artifact_repository):
    source_repository=absolute_root(source_repository);artifact_repository=absolute_root(artifact_repository)
    c=context.bound.contract;slot=context.bound.slot(context.ordinal)
    cwd=artifact_repository/c['outputRelativeRoot']/f'attempt-{context.ordinal:04d}'/'work'
    return dict(version=ENV_VERSION,sourceRepository=str(source_repository),artifactRepository=str(artifact_repository),
        sourceCommit=c['sourceCommit'],executionSha256=io.sha(context.bound.execution_raw),slot=slot,cwd=str(cwd),
        provider='bitz_openai_http',maximumLogicalTurns=1,maximumObservedModelApiRequests=3,
        maximumObservedCatalogApiRequests=2,maximumHostCalls=2,maximumControlCalls=2,
        automaticRetries=0,delegations=0,certifiesApiRequestHardCap=False,launchEnabled=False)


def resource_proof(bound,d,sdk_files,runtime_spec,manifest):
    """閉じた現物検査の宣言形。source/calibration原の現物照合は別工程。"""
    return dict(status='matrix_deployment_resources_verified_launch_not_enabled',sourceCommit=bound.contract['sourceCommit'],
        executionSha256=io.sha(bound.execution_raw),deploymentSha256=None,
        sourceSha256=None,sdkManifestSha256=d['sdkManifestSha256'],sdkTreeSha256=d['sdkTreeSha256'],sdkFileCount=len(sdk_files),
        snapshotManifestSha256=d['manifestSha256'],snapshotResourceCount=len(manifest['resources']),
        decisionSchemaSha256=bound.contract['pins']['decisionSchema'],contextProfileSha256=d['contextProfileSha256'],
        contextDate=None,runtime=dict(status='fixed_runtime_bytes_match',runtimeManifestSha256=d['runtimeManifestSha256'],
            codexPath=d['codexPath'],files=len(runtime_spec['files'])),originalCalibration=None,
        oldCanaryBudgetReused=False,physicalMatrixIsolationAndArgvTested=False,independentPrelaunchReviewPerformed=False,
        primaryModelTrajectories=0,realReservations=0,launchEnabled=False,eligibleForMeasurement=False,
        certifiesSkillGate=False,certifiesRelease=False)


def verify_bytes(context,*,source_repository,artifact_repository):
    require(isinstance(context,evidence.MatrixCapture),'matrix provider bound capture required')
    # 完全な元receiptのversion/hash/inventoryを再検査し、原を差替えずに共通照合する。
    parent=evidence.verify_complete(context)
    receipt=trace.strict_json(context.receipt_raw)
    require(receipt['version']==evidence.PROVIDER_VERSION,'provider capture version required; legacy diagnostic only')
    originals=context.originals
    d=preflight.deployment(context.bound,originals['deployment.json'])
    sdk_files=preflight.sdk_manifest(originals['sdk-manifest.json'],d)
    runtime_spec=preflight.capture.fixed_runtime.specification(originals['runtime-manifest.json'],d)
    require(runtime_spec['files'][preflight.capture.fixed_runtime.VENDOR+'bin/codex']==context.bound.contract['pins']['cli'],
        'matrix original CLI executable pin')
    expected_settings=io.encoded(dict(codexPath=d['codexPath'],diagnosticTracing=preflight.capture.sdk.DIAGNOSTIC_TRACING))
    require(originals['launch-settings.json']==expected_settings,'matrix consumed launch settings drift')
    preflight.capture.sdk.launch_settings(originals['launch-settings.json'])
    manifest=trace.strict_json(context.manifest_raw)
    require(manifest['sourceCommit']==context.bound.contract['sourceCommit']
        and len(manifest['resources'])==d['snapshotResourceCount'],'matrix provider snapshot source or count')
    environment=environment_spec(context,source_repository,artifact_repository)
    require(trace.json_equal(trace.strict_json(originals['capture-environment.json']),environment)
        and receipt['cwd']==environment['cwd'],'matrix capture roots/slot/finite environment drift')
    base=Path(environment['cwd']).parent
    config=preflight.capture.config_for(base,d,repository=source_repository)
    require(trace.json_equal(trace.strict_json(originals['config.json']),config),'matrix complete provider config drift')
    guards=trace.strict_json(originals['resource-guards.json'])
    require(isinstance(guards,dict) and set(guards)=={'before','invoke','after'} and
        all(trace.json_equal(value,guards['before']) for value in guards.values()),'matrix three resource guards drift')
    proof=guards['before'];expected=resource_proof(context.bound,d,sdk_files,runtime_spec,manifest)
    require(isinstance(proof,dict) and set(proof)==set(expected),'matrix resource proof inventory')
    for key,value in expected.items():
        if value is not None:require(trace.json_equal(proof[key],value),'matrix resource proof field drift: '+key)
    require(proof['deploymentSha256']==io.sha(originals['deployment.json']) and isinstance(proof['sourceSha256'],dict)
        and set(proof['sourceSha256'])==set(preflight.SOURCE_FILES),'matrix source proof declared inventory')
    for digest in proof['sourceSha256'].values():io.pin(digest)
    profile=preflight.capture.context_profile(context.context_raw,d)
    require(proof['contextDate']==profile['date'],'matrix original calibrated date drift')
    calibration=proof['originalCalibration']
    require(isinstance(calibration,dict) and set(calibration)=={'status','calibrationManifestSha256','sourceCommit',
        'requestSha256','receiptSha256','paidModelCalls','primaryModelTrajectories','certifiesProviderWireBodies'},
        'matrix calibration proof inventory')
    require(trace.json_equal(calibration,dict(status='original_local_calibration_matches',
        calibrationManifestSha256=d['calibrationManifestSha256'],sourceCommit=profile['calibrationSource'],
        requestSha256=profile['calibrationRequestSha256'],receiptSha256=profile['calibrationReceiptSha256'],
        paidModelCalls=0,primaryModelTrajectories=0,certifiesProviderWireBodies=False)), 'matrix original calibration proof drift')
    return dict(parent,status='matrix_provider_configuration_bytes_bound',providerConfigurationBytesMatched=True,
        deploymentSha256=io.sha(originals['deployment.json']),environmentSha256=io.sha(originals['capture-environment.json']),
        resourceGuardsSha256=io.sha(originals['resource-guards.json']),sourceRepository=str(source_repository),
        artifactRepository=str(artifact_repository),sourceRuntimeOnDiskVerified=False,invocationArgvVerified=False,
        launchEnvironmentVerified=False,eligibleForMeasurement=False,independentReviewPerformed=False,ledgerFinalized=False,
        certifiesSkillGate=False,certifiesRelease=False)
