"""単一保持payloadの隔離argvと開始前検分を束縛する。processは起動しない。"""
from pathlib import Path

import production_heldout_preflight as preflight

x = preflight.execution
io, require, trace = x.io, x.require, x.trace
ROOT = Path(__file__).resolve().parents[3]
AUTH = Path('/home/hide/.codex/auth.json')
VERSION = 'heldout-primary-launch-0.1.0'
REVIEW_VERSION = 'heldout-pipeline-prelaunch-review-0.1.0'
IDENTITY_KEYS = {'ordinal', 'repetition', 'payloadSha256', 'contractSha256', 'sourceCommit',
    'campaignId', 'executionSha256'}


def condition_sha256(execution_raw, deployment_raw):
    x.deployment_for_execution(execution_raw, deployment_raw)
    return io.sha(io.encoded(dict(executionSha256=io.sha(execution_raw), deploymentSha256=io.sha(deployment_raw))))


def prelaunch_review(execution_raw, deployment_raw, review_raw, report_raw, isolation_raw):
    c = x.execution_contract(execution_raw)
    condition = condition_sha256(execution_raw, deployment_raw)
    review, report, isolation = (x.inputs.parse(raw) for raw in [review_raw, report_raw, isolation_raw])
    require(isinstance(review, dict) and set(review) == {'version', 'scope', 'sourceCommit', 'conditionSha256',
        'reviewReportSha256', 'independentContext', 'severityCounts', 'certifiesSkillGate', 'certifiesRelease'},
        'heldout prelaunch review inventory')
    require(review['version'] == REVIEW_VERSION and review['scope'] == 'heldout-primary-and-independent-launch-only'
        and review['sourceCommit'] == c['sourceCommit'] and review['conditionSha256'] == condition
        and review['reviewReportSha256'] == io.sha(report_raw) and review['independentContext'] is True
        and trace.json_equal(review['severityCounts'], dict(P1=0, P2=0))
        and review['certifiesSkillGate'] is False and review['certifiesRelease'] is False, 'heldout prelaunch scope')
    require(isinstance(report, dict) and report.get('status') == 'heldout_pipeline_concrete_prelaunch_verified'
        and report.get('sourceCommit') == c['sourceCommit'] and report.get('conditionSha256') == condition
        and report.get('independentContext') is True and report.get('findings') == report.get('blockingFindings') == []
        and report.get('cleanBefore') == report.get('cleanAfter') == ''
        and report.get('localIsolationProofSha256') == io.sha(isolation_raw), 'heldout original prelaunch report')
    tests = report.get('tests')
    require(isinstance(tests, dict) and type(tests.get('count')) is int and tests['count'] > 0
        and type(tests.get('exitCode')) is int and tests['exitCode'] == 0, 'heldout prelaunch tests')
    require(isinstance(isolation, dict) and isolation.get('status') == 'heldout_local_isolation_verified'
        and isolation.get('sourceCommit') == c['sourceCommit'] and isolation.get('conditionSha256') == condition
        and all(isolation.get(key) is True for key in ['networkNamespaceIsolated', 'credentialsHidden',
            'privateCorpusHidden', 'primaryPayloadProjectionVerified', 'actualArgvVerified'])
        and type(isolation.get('models')) is int and isolation['models'] == 0
        and type(isolation.get('reservations')) is int and isolation['reservations'] == 0,
        'heldout original local isolation proof')
    return review


def primary_identity(bound, ordinal):
    x.rebound(bound)
    return {key: value for key, value in bound.slot(ordinal).items() if key != 'caseId'}


def checked_identity(execution_raw, value):
    c = x.execution_contract(execution_raw)
    require(isinstance(value, dict) and set(value) == IDENTITY_KEYS, 'heldout primary identity inventory')
    ordinal = value['ordinal']
    require(type(ordinal) is int and 1 <= ordinal <= 24
        and type(value['repetition']) is int and value['repetition'] == (ordinal-1) % 2+1
        and value['sourceCommit'] == c['sourceCommit'] and value['campaignId'] == c['campaignId']
        and value['contractSha256'] == c['inputContractSha256']
        and value['executionSha256'] == io.sha(execution_raw), 'heldout primary identity')
    io.pin(value['payloadSha256'])
    return ordinal


def stage_root(execution_raw, ordinal, role='primary'):
    c = x.execution_contract(execution_raw)
    require(type(ordinal) is int and 1 <= ordinal <= 24 and role in {'primary', 'independent'}, 'heldout stage identity')
    return x.inputs.PRIVATE_CASES.parent/c['outputRelativeRoot']/role/f'attempt-{ordinal:04d}'


def namespace_command(repository, execution_raw, deployment_raw, ordinal):
    """argvだけを作る。認証内容は検査・出力・コピー・hashしない。"""
    require(isinstance(repository, Path) and repository.is_absolute() and '..' not in repository.parts,
        'heldout absolute source root')
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    base = stage_root(execution_raw, ordinal)
    args = ['bwrap', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
        '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
        '--proc', '/proc', '--dev', '/dev']
    paths = [repository/preflight.public.capture.fixed_runtime.MANIFEST,
        repository/d['sdkRelativePath'], repository/d['snapshotRelativePath'], Path(d['codexPath']).parents[1],
        *(repository/name for name in preflight.SOURCE_FILES if name.endswith('.py'))]
    for path in paths:
        args += ['--ro-bind', str(path), str(path)]
    return args+['--bind', str(base), str(base), '--bind', str(base/'codex-home'), '/home/hide/.codex',
        '--ro-bind', str(AUTH), '/home/hide/.codex/auth.json', '--chdir', str(base/'work'), '--',
        '/usr/bin/python3', '-B', str(repository/'evals/skills/routing/production_heldout_capture.py'),
        '--isolated', str(base)]


def environment(execution_raw, deployment_raw, ordinal):
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    base = stage_root(execution_raw, ordinal)
    value = dict(
        PATH=str(Path(d['codexPath']).parents[1]/'bin')+':/usr/bin:/bin', LANG='C.UTF-8',
        HOME='/home/hide', CODEX_HOME='/home/hide/.codex', TMPDIR=str(base/'tmp'),
        PYTHONDONTWRITEBYTECODE='1', TZ='Asia/Tokyo', LOG_FORMAT='json',
        RUST_LOG='codex_otel.trace_safe=info,codex_code_mode::timing=info',
        CODEX_ROLLOUT_TRACE_ROOT=str(base/'rollout-traces'))
    return value


def invocation(repository, execution_raw, deployment_raw, identity):
    ordinal = checked_identity(execution_raw, identity)
    return dict(version=VERSION, primaryIdentity=identity, executionSha256=io.sha(execution_raw),
        deploymentSha256=io.sha(deployment_raw), argv=namespace_command(repository, execution_raw, deployment_raw, ordinal),
        environment=environment(execution_raw, deployment_raw, ordinal),
        maximumLogicalTurns=1, automaticRetries=0, processUmask=0o077,
        timeoutSeconds=x.execution_contract(execution_raw)['timeoutSeconds']['primary'])


def launch_settings(execution_raw, deployment_raw):
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    raw = io.encoded(dict(codexPath=d['codexPath'], diagnosticTracing=preflight.public.capture.sdk.DIAGNOSTIC_TRACING))
    preflight.public.capture.sdk.launch_settings(raw)
    return raw
