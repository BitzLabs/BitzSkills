"""行列用の局所隔離argvと保存先。実provider起動入口は持たない。"""
from pathlib import Path
import re

import production_matrix_preflight as preflight

io = preflight.io
require = preflight.require
PROBE_VERSION = 'public-matrix-local-isolation-0.1.0'
CALIBRATION_VERSION = 'public-matrix-local-calibration-0.1.0'


def probe_layout(source_repository, output_relative_root):
    require(isinstance(source_repository, Path) and source_repository.is_absolute()
            and '..' not in source_repository.parts, 'matrix source repository path')
    io.safe_tree(source_repository)
    require(isinstance(output_relative_root, str) and re.fullmatch(
        r'\.venv/matrix-local-isolation-[a-z0-9]+(?:-[a-z0-9]+)*', output_relative_root) is not None,
        'matrix local probe output path')
    artifact_repository = io.common_ledger_path(source_repository).parent.parent
    return artifact_repository, artifact_repository/output_relative_root


def launch_settings(execution_raw, deployment_raw):
    d = preflight.deployment_for_execution(execution_raw, deployment_raw)
    raw = io.encoded(dict(codexPath=d['codexPath'], diagnosticTracing=preflight.capture.sdk.DIAGNOSTIC_TRACING))
    preflight.capture.sdk.launch_settings(raw)
    return raw


def local_namespace_command(source_repository, base, execution_raw, deployment_raw, *, calibration_only=False):
    require(type(calibration_only) is bool, 'matrix local calibration mode must be boolean')
    d = preflight.deployment_for_execution(execution_raw, deployment_raw)
    require(source_repository.is_absolute() and base.is_absolute() and '..' not in source_repository.parts
            and '..' not in base.parts, 'matrix absolute namespace paths')
    io.safe_tree(source_repository);io.safe_tree(base)
    require(base.parent.name == '.venv' and re.fullmatch(
        r'matrix-local-isolation-[a-z0-9]+(?:-[a-z0-9]+)*', base.name) is not None, 'matrix local base path')
    args = ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
        '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
        '--proc', '/proc', '--dev', '/dev']
    # 全case/expected/保持集合/評価結果やGit領域は子processへmountしない。
    paths = [source_repository/preflight.capture.fixed_runtime.MANIFEST,
        source_repository/d['sdkRelativePath'], source_repository/d['snapshotRelativePath'],
        Path(d['codexPath']).parents[1],
        *(source_repository/name for name in preflight.SOURCE_FILES if name.endswith('.py'))]
    for path in paths:
        args += ['--ro-bind', str(path), str(path)]
    return (args + ['--bind', str(base), str(base), '--chdir', str(base/'work'), '--', '/usr/bin/python3', '-B',
        str(source_repository/'evals/skills/routing/production_matrix_context_probe.py'), '--isolated', str(base)]
        + (['--calibration'] if calibration_only else []))


def local_environment(base, deployment, *, calibration_only=False):
    require(type(calibration_only) is bool, 'matrix local calibration mode must be boolean')
    result = dict(PATH=str(Path(deployment['codexPath']).parents[1]/'bin')+':/usr/bin:/bin',
        LANG='C.UTF-8', HOME='/home/hide', CODEX_HOME=str(base/'codex-home'), PYTHONDONTWRITEBYTECODE='1',
        TMPDIR=str(base/'tmp'), LOG_FORMAT='json',
        RUST_LOG='codex_otel.trace_safe=info,codex_code_mode::timing=info',
        CODEX_ROLLOUT_TRACE_ROOT=str(base/'rollout-traces'))
    if calibration_only:result['TZ']='Asia/Tokyo'
    return result
