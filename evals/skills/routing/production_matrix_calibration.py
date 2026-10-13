"""行列の局所校正原を固定Gitへ束縛。旧Canary校正原の形式・保存先を保持する。"""
from pathlib import Path
import re

import production_matrix_context_probe as probe

p=probe.preflight
io=p.io
require=p.require
VERSION='matrix-client-calibration-originals-0.1.0'
FILES=probe.FIXED_FILES|{'receipt.json'}
MANIFEST_KEYS={'version','sourceCommit','sourceRepository','artifactRepository','outputRelativeRoot','artifactSha256'}


def source_files(repository,source):
    """producerの固定MODULES宣言を読む。過去コードの実行や作業tree照合は行わない。"""
    raw=p.guard.git(repository,'show',source+':evals/skills/routing/production_matrix_preflight.py')
    modules=p.capture.calibration.literal(raw.decode(),'MODULES')
    require(isinstance(modules,tuple) and len(modules)==len(set(modules))
        and {'production_matrix_context_probe','production_matrix_launch','production_matrix_preflight'}<=set(modules)
        and all(isinstance(n,str) and re.fullmatch(r'[a-z_]+',n) is not None for n in modules),
        'matrix calibration fixed source declaration')
    return tuple(dict.fromkeys([*(f'evals/skills/routing/{n}.py' for n in modules),
        *p.INPUT_PATHS.values(),p.inventory.SCHEMA,p.inventory.CONTEXT,p.capture.fixed_runtime.MANIFEST,
        p.capture.calibration.MANIFEST,'evals/skills/sol-authorization.json']))


def verify(repository,manifest_raw,profile,contract):
    require(io.sha(manifest_raw)==io.pin(contract['calibrationManifestSha256']),'fixed matrix calibration manifest hash')
    m=p.trace.strict_json(manifest_raw)
    require(isinstance(m,dict) and set(m)==MANIFEST_KEYS and m['version']==VERSION
        and isinstance(m['sourceCommit'],str) and re.fullmatch(r'[0-9a-f]{40}',m['sourceCommit']) is not None
        and m['sourceCommit']==profile.get('calibrationSource') and isinstance(m['artifactSha256'],dict)
        and set(m['artifactSha256'])==FILES,'fixed matrix calibration inventory')
    for digest in m['artifactSha256'].values():io.pin(digest)
    require(isinstance(m['sourceRepository'],str) and isinstance(m['artifactRepository'],str)
        and isinstance(m['outputRelativeRoot'],str) and re.fullmatch(
            r'\.venv/matrix-local-isolation-calibration-[a-z0-9]+(?:-[a-z0-9]+)*',m['outputRelativeRoot']) is not None,
        'matrix calibration declared roots')
    source_repository=Path(m['sourceRepository']);artifact_repository=Path(m['artifactRepository'])
    require(source_repository.is_absolute() and artifact_repository.is_absolute()
        and '..' not in source_repository.parts and '..' not in artifact_repository.parts
        and source_repository.is_relative_to(artifact_repository),'matrix calibration source/artifact containment')
    io.safe_tree(source_repository);io.safe_tree(artifact_repository)
    expected_artifact=io.common_ledger_path(repository).parent.parent
    require(artifact_repository==expected_artifact
        and io.common_ledger_path(source_repository).parent.parent==expected_artifact,'matrix calibration common repository drift')
    base=artifact_repository/m['outputRelativeRoot']
    # 宣言検査後、有限の公開固定名だけを読む。opaque内部は列挙しない。
    originals={name:io.read_regular(base/name) for name in sorted(FILES)}
    require({name:io.sha(raw) for name,raw in originals.items()}==m['artifactSha256'],'matrix calibration original bytes drift')
    receipt=p.trace.strict_json(originals.pop('receipt.json'))
    source=m['sourceCommit'];names=source_files(repository,source)
    frozen={name:p.guard.git(repository,'show',source+':'+name) for name in names}
    require(originals['context-profile.json']==frozen[p.inventory.CONTEXT],'matrix calibration reference profile outside Git')
    execution_raw=originals['contract.json'];c=p.matrix.execution_contract(execution_raw)
    require(c['sourceCommit']==source,'matrix calibration execution source drift')
    raws={name:frozen[path] for name,path in p.INPUT_PATHS.items()}
    input_raw=io.encoded(dict(version='public-production-matrix-inputs-0.1.0',scope='public-six-skill-input-binding-only',
        sourceCommit=source,model='gpt-6.1-sol',repetitions=2,budget=dict(primary=92,independent=92,automaticRetries=0,delegations=0),
        inputSha256={name:io.sha(raw) for name,raw in raws.items()},certifiesBehavior=False,certifiesSkillGate=False))
    bound=p.matrix.bind(execution_raw,input_raw,**raws)
    d_raw=originals['deployment.json'];d=p.deployment(bound,d_raw)
    sdk_files=p.sdk_manifest(originals['sdk-manifest.json'],d)
    reference=p.capture.context_profile(originals['context-profile.json'],d)
    new_profile=dict(reference,date=profile.get('date'),calibrationSource=source,
        calibrationRequestSha256=m['artifactSha256']['request-1.json'],calibrationReceiptSha256=m['artifactSha256']['receipt.json'])
    p.capture.context_profile(io.encoded(new_profile),dict(d,contextProfileSha256=io.sha(io.encoded(new_profile))))
    require(p.trace.json_equal(profile,new_profile),'matrix calibration profile outside original context')
    schema=p.decision_schema(frozen[p.inventory.SCHEMA])
    require(schema==originals['decision-schema.json'],'matrix calibration canonical Schema outside Git')
    require(io.sha(frozen[p.capture.fixed_runtime.MANIFEST])==d['runtimeManifestSha256']
        and io.sha(frozen[p.capture.calibration.MANIFEST])==d['calibrationManifestSha256'],'matrix calibration producer manifest pins')
    runtime=p.capture.fixed_runtime.verify(frozen[p.capture.fixed_runtime.MANIFEST],d)
    require(p.trace.strict_json(frozen[p.capture.fixed_runtime.MANIFEST])['files'][p.capture.fixed_runtime.VENDOR+'bin/codex']==c['pins']['cli'],
        'matrix calibration CLI executable pin')
    old_calibration=p.capture.calibration.verify(repository,frozen[p.capture.calibration.MANIFEST],reference,d)
    snapshot=source_repository/d['snapshotRelativePath'];snapshot_manifest_raw=io.read_regular(snapshot/'manifest.json')
    require(io.sha(snapshot_manifest_raw)==d['manifestSha256'],'matrix calibration snapshot manifest drift')
    manifest,_,_=p.trace.manifest_view(snapshot_manifest_raw)
    require(manifest['sourceCommit']==source and len(manifest['resources'])==d['snapshotResourceCount']
        and set(manifest['resources'])==p.public_resource_names(repository,source),'matrix calibration complete Git snapshot')
    expected=dict(manifest['resources'],**{'manifest.json':d['manifestSha256']})
    resources=p.exact_tree(snapshot,expected)
    for name,raw in resources.items():
        require(io.sha(raw)==expected[name],'matrix calibration snapshot bytes drift')
        if name!='manifest.json':
            require(raw==p.guard.git(repository,'show',source+':plugins/'+Path(name).relative_to('resources').as_posix()),
                'matrix calibration snapshot outside Git')
    dependencies=p.exact_tree(source_repository/d['sdkRelativePath'],sdk_files)
    require({name:io.sha(raw) for name,raw in dependencies.items()}==sdk_files,'matrix calibration SDK bytes drift')
    proof=dict(status='matrix_local_calibration_resources_verified_launch_not_enabled',sourceCommit=source,
        executionSha256=io.sha(execution_raw),deploymentSha256=io.sha(d_raw),sourceSha256={name:io.sha(raw) for name,raw in frozen.items()},
        sdkManifestSha256=io.sha(originals['sdk-manifest.json']),sdkTreeSha256=d['sdkTreeSha256'],sdkFileCount=len(sdk_files),
        snapshotManifestSha256=io.sha(snapshot_manifest_raw),snapshotResourceCount=len(manifest['resources']),decisionSchemaSha256=io.sha(schema),
        contextProfileSha256=io.sha(originals['context-profile.json']),contextDate=reference['date'],runtime=runtime,
        originalCalibration=old_calibration,oldCanaryBudgetReused=False,physicalMatrixIsolationAndArgvTested=False,
        independentPrelaunchReviewPerformed=False,primaryModelTrajectories=0,realReservations=0,launchEnabled=False,
        eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False,calibrationOnly=True,
        referenceContextDate=reference['date'],calibrationDate=new_profile['date'])
    proof_raw=io.encoded(proof)
    require(originals['resource-preflight.json']==proof_raw,'matrix calibration historical resource proof drift')
    verified=probe.verify_originals(originals,execution_raw=execution_raw,deployment_raw=d_raw,slot=bound.slot(1),cwd=str(base/'work'),
        source_repository=source_repository,context_raw=originals['context-profile.json'],resource_proof_raw=proof_raw,
        calibration_only=True,calibration_date=new_profile['date'],source_files=names)
    elapsed=receipt.get('elapsedSeconds') if isinstance(receipt,dict) else None
    require(type(elapsed) in {int,float} and 0<=elapsed<=65,'matrix calibration finite receipt duration')
    expected_receipt=dict(version=probe.launch.CALIBRATION_VERSION,status='local_calibration_verified',sourceCommit=source,
        executionSha256=io.sha(execution_raw),sourceRepository=str(source_repository),artifactRepository=str(artifact_repository),
        resourceGuards=dict.fromkeys(['before','invoke','after'],proof),namespaceExitCode=0,timedOut=False,elapsedSeconds=elapsed,
        artifactSha256={name:io.sha(raw) for name,raw in originals.items()},originalReadErrors={},verification=verified,error=None,
        primaryModelTrajectories=0,paidModelCalls=0,realReservations=0,automaticRetries=0,launchEnabled=False,
        eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False,calibrationOnly=True,
        calibrationDate=new_profile['date'],referenceContextDate=reference['date'])
    require(p.trace.json_equal(receipt,expected_receipt),'matrix calibration complete successful receipt drift')
    # 開始前proofの共通interfaceを維持。producer形式は固定manifestで識別する。
    return dict(status='original_local_calibration_matches',calibrationManifestSha256=io.sha(manifest_raw),
        sourceCommit=source,requestSha256=new_profile['calibrationRequestSha256'],receiptSha256=new_profile['calibrationReceiptSha256'],
        paidModelCalls=0,primaryModelTrajectories=0,certifiesProviderWireBodies=False)
