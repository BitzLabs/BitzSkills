"""公開行列の現物資源を開始前に照合する。起動・予約・認定は行わない。

旧Canaryの予算や台帳を経由しない。校正原の検証は旧条件のまま保持し、
行列の物理隔離/argv/独立開始前検分の完了へ読み替えない。
"""
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import production_matrix_ledger as matrix
import production_canary_capture as capture
import production_canary_evidence as inventory
import production_trace as trace
import source_guard as guard

io = matrix.io
require = trace.require
VERSION = 'public-matrix-deployment-resources-0.1.0'
INPUT_PATHS = dict(routing='evals/skills/cases/routing.json',
    behaviorSafety='evals/skills/cases/behavior-safety.json', protocol='evals/skills/protocol.json',
    catalog='evals/skills/event-catalog.json', instructions=inventory.INSTRUCTIONS,
    caseSchema='evals/skills/schemas/case.schema.json')
MODULES = ('production_matrix_originals', 'production_matrix_semantic', 'production_matrix_provider_evidence', 'production_matrix_launch', 'production_matrix_context_probe',
    'production_matrix_preflight', 'production_matrix_inputs', 'production_matrix_ledger',
    'production_matrix_evidence', 'production_primary_review', 'production_canary_capture',
    'production_canary_host', 'production_canary_review', 'production_canary_evidence',
    'production_canary_trace', 'production_canary_rollout', 'production_canary_runtime',
    'production_canary_calibration', 'production_trace', 'production_sdk_trace',
    'production_sdk_probe', 'production_connection_probe', 'production_cli_probe',
    'production_ledger', 'source_guard', 'host')
SOURCE_FILES = tuple(dict.fromkeys([*(f'evals/skills/routing/{n}.py' for n in MODULES),
    *INPUT_PATHS.values(), inventory.SCHEMA, inventory.CONTEXT, capture.fixed_runtime.MANIFEST,
    capture.calibration.MANIFEST, 'evals/skills/sol-authorization.json']))
DEPLOYMENT_KEYS = {'version', 'sourceCommit', 'executionSha256', 'codexPath', 'codexVersion',
    'sdkRelativePath', 'sdkVersion', 'sdkTreeSha256', 'sdkManifestSha256', 'snapshotRelativePath',
    'manifestSha256', 'snapshotResourceCount', 'runtimeManifestSha256', 'contextProfileSha256',
    'calibrationManifestSha256', 'certifiesSkillGate'}
SDK_TOP = {'openai_codex', 'openai_codex-0.160.1.dist-info', 'annotated_types',
    'annotated_types-0.8.0.dist-info', 'packaging', 'packaging-26.3.dist-info', 'pydantic',
    'pydantic-2.13.5.dist-info', 'pydantic_core', 'pydantic_core-2.46.5.dist-info',
    'typing_extensions.py', 'typing_extensions-4.16.0.dist-info', 'typing_inspection',
    'typing_inspection-0.4.4.dist-info'}


def deployment(bound, raw):
    require(bound == matrix.bind(bound.execution_raw, bound.matrix.contract_raw,
        **dict(zip(matrix.inputs.INPUT_NAMES, bound.raw_inputs))), 'matrix fixed bound drift')
    return deployment_for_execution(bound.execution_raw, raw)


def deployment_for_execution(execution_raw, raw):
    """子processへ渡す設定を有限policyへ束縛。全入力の現物検査は親が行う。"""
    execution = matrix.execution_contract(execution_raw)
    require(isinstance(raw, bytes), 'matrix deployment bytes')
    d = trace.strict_json(raw)
    require(isinstance(d, dict) and set(d) == DEPLOYMENT_KEYS and d['version'] == VERSION,
            'matrix deployment inventory')
    require(d['sourceCommit'] == execution['sourceCommit']
        and d['executionSha256'] == io.sha(execution_raw) and d['certifiesSkillGate'] is False,
        'matrix deployment source or execution drift')
    require(isinstance(d['sdkRelativePath'], str) and re.fullmatch(
        r'\.venv/matrix-codex-python-sdk-deps-[a-z0-9]+(?:-[a-z0-9]+)*', d['sdkRelativePath']) is not None
        and d['sdkVersion'] == '0.160.1' and d['codexVersion'] == 'codex-cli 0.160.1'
        and d['codexPath'] == str(capture.fixed_runtime.ROOT / 'bin/codex'), 'matrix fixed deployment paths')
    require(isinstance(d['snapshotRelativePath'], str) and re.fullmatch(
        r'\.venv/matrix-routing-preparation-[a-z0-9]+(?:-[a-z0-9]+)*/snapshot',
        d['snapshotRelativePath']) is not None, 'matrix snapshot path')
    require(type(d['snapshotResourceCount']) is int and 6 <= d['snapshotResourceCount'] <= 1024,
            'matrix finite resource count')
    for key, pin in [('manifestSha256', 'snapshotManifest'), ('sdkTreeSha256', 'sdk'),
        ('runtimeManifestSha256', 'runtimeManifest'), ('contextProfileSha256', 'contextProfile'),
        ('calibrationManifestSha256', 'calibrationManifest')]:
        require(io.pin(d[key]) == execution['pins'][pin], 'matrix deployment pin drift: '+pin)
    io.pin(d['sdkManifestSha256'])
    return d


def sdk_manifest(raw, d):
    require(isinstance(raw, bytes) and io.sha(raw) == d['sdkManifestSha256'], 'matrix SDK manifest hash')
    value = trace.strict_json(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'files', 'treeSha256'}
        and value['version'] == '0.160.1' and isinstance(value['files'], dict)
        and 2 <= len(value['files']) <= 4096, 'matrix SDK manifest inventory')
    files = value['files']
    require({'openai_codex/__init__.py', 'openai_codex-0.160.1.dist-info/METADATA'} <= set(files),
            'matrix SDK required package resources')
    for name, digest in files.items():
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.+/-]+', name) is not None
            and name == Path(name).as_posix() and name.split('/')[0] in SDK_TOP
            and not set(name.split('/')) & {'', '.', '..', '.env', 'auth.json', '.credentials.json', '__pycache__'}
            and all(not part.startswith('.env.') for part in name.split('/')) and not name.endswith('.pyc'),
            'matrix SDK public resource path')
        io.pin(digest)
    digest = hashlib.sha256()
    for name, file_digest in sorted(files.items(), key=lambda item: Path(item[0]).parts):
        digest.update(name.encode()+b'\0'); digest.update(bytes.fromhex(file_digest))
    require(digest.hexdigest() == value['treeSha256'] == d['sdkTreeSha256'], 'matrix SDK pinned tree hash')
    return files


def exact_tree(root, files):
    """有限宣言の親だけを辿る。未知名は内容を読む前に拒否する。"""
    require(isinstance(files,dict) and bool(files),'matrix public resource inventory required')
    directories={''};children={}
    for name,digest in files.items():
        require(isinstance(name,str) and name==Path(name).as_posix() and not Path(name).is_absolute()
            and '\\' not in name and not set(name.split('/')) & {'','.','..','.env','auth.json','.credentials.json','__pycache__'}
            and not any(p.startswith('.env.') for p in name.split('/')) and not name.endswith('.pyc'),
            'matrix public resource declared path')
        io.pin(digest);parts=name.split('/')
        for i,part in enumerate(parts):
            parent='/'.join(parts[:i]);children.setdefault(parent,set()).add(part)
            if i<len(parts)-1:directories.add('/'.join(parts[:i+1]))
    require(not set(files)&directories,'matrix resource file/directory collision')
    actual = set()
    @contextmanager
    def directory(fd,name,info):
        require(stat.S_ISDIR(info.st_mode),'matrix resource parent shape')
        child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            observed=os.fstat(child)
            require((observed.st_dev,observed.st_ino)==(info.st_dev,info.st_ino),'matrix resource directory identity drift')
            yield child
        finally:os.close(child)
    def visit(fd,prefix):
        names=os.listdir(fd)
        require(set(names)==children[prefix],'unknown matrix public resource or missing member')
        for child in names:
            name=prefix+'/'+child if prefix else child
            info=os.stat(child,dir_fd=fd,follow_symlinks=False)
            require(not stat.S_ISLNK(info.st_mode),'matrix public resource link')
            if name in directories:
                with directory(fd,child,info) as opened:visit(opened,name)
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'matrix public resource type or hardlink')
                actual.add(name)
    with io.open_directory(root) as opened:visit(opened,'')
    require(actual == set(files), 'matrix public resource missing')
    return {name: io.read_regular(root/name) for name in sorted(files)}


def decision_schema(raw):
    # 旧入口と同じ六製品へのcanonical投影。送信用uniqueItems除去は別の複製で行う。
    schema = trace.strict_json(raw)
    schema['properties']['selectedEntry']['enum'] = [None, *sorted(trace.SKILLS)]
    trace.jsonschema.Draft202012Validator.check_schema(schema)
    return io.encoded(schema)


def public_resource_names(repository, source):
    tree = guard.git(repository, 'ls-tree', '-r', '-z', source, '--',
                     'plugins/bitz-core', 'plugins/bitz-sdd', 'plugins/bitz-quality')
    names = set()
    for item in tree.split(b'\0'):
        if not item:
            continue
        header, path = item.split(b'\t', 1)
        mode, kind, _ = header.split()
        require(kind == b'blob' and mode in {b'100644', b'100755'}, 'matrix regular tracked public resource')
        name = 'resources/'+path.decode().removeprefix('plugins/')
        trace.resource_path(name)
        require('auth.json' not in Path(name).parts, 'matrix protected public resource')
        require(name not in names, 'matrix duplicate public resource')
        names.add(name)
    return names


def verify_resources(repository, bound, deployment_raw, sdk_manifest_raw):
    return _verify_resources(repository, bound, deployment_raw, sdk_manifest_raw, calibration_only=False)


def verify_calibration_resources(repository, bound, deployment_raw, sdk_manifest_raw):
    """過去profileを参照する局所校正専用。通常実測の当日条件を緩めない。"""
    return _verify_resources(repository, bound, deployment_raw, sdk_manifest_raw, calibration_only=True)


def _verify_resources(repository, bound, deployment_raw, sdk_manifest_raw, *, calibration_only):
    require(isinstance(repository, Path) and repository.is_absolute() and '..' not in repository.parts,
            'matrix absolute repository required')
    io.safe_tree(repository)
    d = deployment(bound, deployment_raw)
    sdk_files = sdk_manifest(sdk_manifest_raw, d)
    source = d['sourceCommit']
    require(guard.git(repository, 'rev-parse', source+'^{commit}').decode().strip() == source,
            'matrix exact source ref required')
    # 期待だけを再hashした入力、driverだけを更新した条件も固定Gitへ照合する。
    originals = {name: guard.git(repository, 'show', source+':'+name) for name in SOURCE_FILES}
    for name, raw in originals.items():
        require(io.read_regular(repository/name) == raw, 'matrix fixed source drift')
    for name, raw in zip(matrix.inputs.INPUT_NAMES, bound.raw_inputs):
        require(raw == originals[INPUT_PATHS[name]], 'matrix input outside fixed Git: '+name)
    schema_raw = decision_schema(originals[inventory.SCHEMA])
    require(io.sha(schema_raw) == bound.contract['pins']['decisionSchema'], 'matrix canonical Schema pin')
    context_raw = originals[inventory.CONTEXT]
    context = capture.context_profile(context_raw, d)
    today = datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
    if calibration_only:
        require(context['date'] <= today, 'matrix reference context date is in future')
    else:
        require(context['date'] == today, 'matrix calibrated context date differs')
    runtime_raw = originals[capture.fixed_runtime.MANIFEST]
    specification = capture.fixed_runtime.specification(runtime_raw, d)
    require(specification['files'][capture.fixed_runtime.VENDOR+'bin/codex'] == bound.contract['pins']['cli'],
            'matrix CLI executable pin')
    snapshot = repository/d['snapshotRelativePath']
    manifest_raw = io.read_regular(snapshot/'manifest.json')
    require(io.sha(manifest_raw) == d['manifestSha256'], 'matrix snapshot manifest drift')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    require(manifest['sourceCommit'] == source and len(manifest['resources']) == d['snapshotResourceCount'],
            'matrix snapshot source or count drift')
    require(set(manifest['resources']) == public_resource_names(repository, source),
            'matrix snapshot does not contain complete Git resources')
    expected = dict(manifest['resources'], **{'manifest.json': d['manifestSha256']})
    resources = exact_tree(snapshot, expected)
    for name, raw in resources.items():
        require(io.sha(raw) == expected[name], 'matrix snapshot bytes drift')
        if name != 'manifest.json':
            public_path = 'plugins/'+Path(name).relative_to('resources').as_posix()
            require(raw == guard.git(repository, 'show', source+':'+public_path), 'matrix snapshot Git drift')
    dependencies = exact_tree(repository/d['sdkRelativePath'], sdk_files)
    require({name: io.sha(raw) for name, raw in dependencies.items()} == sdk_files, 'matrix SDK bytes drift')
    runtime = capture.fixed_runtime.verify(runtime_raw, d)
    calibration = capture.calibration.verify(repository, originals[capture.calibration.MANIFEST], context, d)
    result = dict(status='matrix_deployment_resources_verified_launch_not_enabled', sourceCommit=source,
        executionSha256=io.sha(bound.execution_raw), deploymentSha256=io.sha(deployment_raw),
        sourceSha256={name: io.sha(raw) for name, raw in originals.items()},
        sdkManifestSha256=io.sha(sdk_manifest_raw), sdkTreeSha256=d['sdkTreeSha256'], sdkFileCount=len(sdk_files),
        snapshotManifestSha256=io.sha(manifest_raw), snapshotResourceCount=len(manifest['resources']),
        decisionSchemaSha256=io.sha(schema_raw), contextProfileSha256=io.sha(context_raw),
        contextDate=context['date'], runtime=runtime, originalCalibration=calibration,
        oldCanaryBudgetReused=False, physicalMatrixIsolationAndArgvTested=False,
        independentPrelaunchReviewPerformed=False, primaryModelTrajectories=0, realReservations=0,
        launchEnabled=False, eligibleForMeasurement=False, certifiesSkillGate=False, certifiesRelease=False)
    if calibration_only:
        result.update(status='matrix_local_calibration_resources_verified_launch_not_enabled',
            calibrationOnly=True, referenceContextDate=context['date'], calibrationDate=today)
    return result
