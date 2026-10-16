"""保持24枠の現物source/入力/製品/SDK/校正を照合する。起動・予約・保存なし。"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import production_heldout_execution as execution

inputs, public = execution.inputs, execution.public
io, require, trace = inputs.io, inputs.require, inputs.trace
SOURCE_FILES = tuple(dict.fromkeys([*public.SOURCE_FILES, *inputs.SOURCE_FILES,
    'evals/skills/routing/production_heldout_ledger.py',
    'evals/skills/routing/production_heldout_execution.py',
    'evals/skills/routing/production_heldout_preflight.py']))


def verify_resources(repository, bound, sdk_manifest_raw):
    execution.rebound(bound)
    require(isinstance(repository, Path) and repository.is_absolute() and '..' not in repository.parts,
        'heldout absolute source repository')
    io.safe_tree(repository)
    c = bound.contract
    d = execution.deployment_for_execution(bound.execution_raw, bound.deployment_raw)
    source = c['sourceCommit']
    require(public.guard.git(repository, 'rev-parse', source+'^{commit}').decode().strip() == source,
        'heldout exact source commit')
    originals = {name: public.guard.git(repository, 'show', source+':'+name) for name in SOURCE_FILES}
    for name, raw in originals.items():
        require(io.read_regular(repository/name) == raw, 'heldout fixed source drift')
    raw_inputs = dict(zip(inputs.INPUT_NAMES, bound.raw_inputs))
    for name, path in inputs.PUBLIC_PATHS.items():
        require(raw_inputs[name] == originals[path], 'heldout public input outside fixed Git')
    schema_raw = public.decision_schema(originals[public.inventory.SCHEMA])
    require(io.sha(schema_raw) == c['pins']['decisionSchema'], 'heldout decision schema drift')
    context_raw = originals[public.inventory.CONTEXT]
    context = public.capture.context_profile(context_raw, d)
    require(context['date'] == datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat(),
        'heldout current calibration date required')
    runtime_raw = originals[public.capture.fixed_runtime.MANIFEST]
    runtime_spec = public.capture.fixed_runtime.specification(runtime_raw, d)
    require(runtime_spec['files'][public.capture.fixed_runtime.VENDOR+'bin/codex'] == c['pins']['cli'],
        'heldout CLI executable drift')
    snapshot = repository/d['snapshotRelativePath']
    manifest_raw = io.read_regular(snapshot/'manifest.json')
    require(io.sha(manifest_raw) == d['manifestSha256'], 'heldout snapshot manifest drift')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    require(manifest['sourceCommit'] == source and len(manifest['resources']) == 72
        and set(manifest['resources']) == public.public_resource_names(repository, source),
        'heldout product source and complete inventory')
    expected = dict(manifest['resources'], **{'manifest.json': d['manifestSha256']})
    for name, raw in public.exact_tree(snapshot, expected).items():
        require(io.sha(raw) == expected[name], 'heldout snapshot byte drift')
        if name != 'manifest.json':
            path = 'plugins/'+Path(name).relative_to('resources').as_posix()
            require(raw == public.guard.git(repository, 'show', source+':'+path), 'heldout snapshot Git drift')
    sdk_files = public.sdk_manifest(sdk_manifest_raw, d)
    require({name: io.sha(raw) for name, raw in public.exact_tree(repository/d['sdkRelativePath'], sdk_files).items()}
        == sdk_files, 'heldout SDK byte drift')
    runtime = public.capture.fixed_runtime.verify(runtime_raw, d)
    calibration = public.capture.calibration.verify(repository,
        originals[public.capture.calibration.MANIFEST], context, d)
    # 公開sourceと全現物資源・校正の検査後だけ、既採用集合の原bytesを内部再照合する。
    require(inputs.private_bytes(inputs.PRIVATE_CASES) == raw_inputs['cases'], 'heldout original set drift')
    return dict(status='heldout_resources_verified_not_launchable', sourceCommit=source,
        executionSha256=io.sha(bound.execution_raw), deploymentSha256=io.sha(bound.deployment_raw),
        inputContractSha256=io.sha(bound.input_contract_raw),
        sourceSha256={name: io.sha(raw) for name, raw in originals.items()},
        casesSha256=io.sha(raw_inputs['cases']), snapshotManifestSha256=io.sha(manifest_raw),
        snapshotResourceCount=72, sdkManifestSha256=io.sha(sdk_manifest_raw), sdkFileCount=len(sdk_files),
        sdkTreeSha256=d['sdkTreeSha256'], decisionSchemaSha256=io.sha(schema_raw),
        contextProfileSha256=io.sha(context_raw), contextDate=context['date'], runtime=runtime,
        originalCalibration=calibration, models=0, reservations=0, launchEnabled=False,
        certifiesSkillGate=False, certifiesRelease=False)
