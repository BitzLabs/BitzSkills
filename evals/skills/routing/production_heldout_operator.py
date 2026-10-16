"""保持一次の有限親operator。固定開始条件→追記予約→単回隔離取得→私的原照合。"""
import math
import os
import re
from pathlib import Path
import signal
import stat
import subprocess
import time

import production_heldout_originals as originals

x, evidence = originals.x, originals.evidence
launch, preflight = evidence.launch, evidence.preflight
io, require, trace = x.io, x.require, x.trace
VERSION = 'heldout-primary-operator-0.1.0'
CONTROL_FILES = {'pacing.json', 'primary-result.json', 'failure.json', 'global-stop.json'}


def check_directory(base, fd):
    value = os.fstat(fd)
    require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid()
        and value.st_nlink >= 2, 'heldout control directory drift')
    current = originals._open_root(base)
    try:
        other = os.fstat(current)
        require((value.st_dev,value.st_ino) == (other.st_dev,other.st_ino), 'heldout control directory identity drift')
    finally:os.close(current)


def create_directory(path):
    """既承認private境界内の新規dirだけ。既存fileを削除/上書きしない。"""
    root = x.inputs.PRIVATE_CASES.parent
    require(isinstance(path, Path) and path.is_absolute() and path.is_relative_to(root)
        and '..' not in path.parts, 'heldout private write boundary')
    parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    current = Path('/')
    try:
        for part in path.parts[1:]:
            current /= part
            if current.is_relative_to(root):
                try:
                    os.mkdir(part, mode=0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
            if current.is_relative_to(root):
                value = os.fstat(parent)
                require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid()
                    and value.st_nlink >= 2, 'heldout write directory metadata')
    finally:
        os.close(parent)


def save(base, name, raw):
    """固定basenameだけをlock中のprivate rootへEXCL/NOFOLLOWで新規保存する。"""
    require(name in evidence.inventory.FIXED_ARTIFACTS | evidence.ADDITIONAL
        | {'receipt.json', *CONTROL_FILES}, 'heldout write fixed name')
    require(isinstance(raw, bytes) and len(raw) <= originals.MAX_FILE_BYTES, 'heldout finite saved bytes')
    fd = originals._open_root(base)
    try:
        file = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(file, 'wb', closefd=False) as stream:
                stream.write(raw);stream.flush();os.fsync(file)
            value = os.fstat(file)
            require(value.st_uid == os.getuid() and stat.S_IMODE(value.st_mode) == 0o600
                and value.st_nlink == 1, 'heldout saved file metadata')
        finally:
            os.close(file)
        os.fsync(fd)
        check_directory(base,fd)
    finally:
        os.close(fd)


def auth_metadata():
    # Agentは認証内容を開かない。親dirと単一fileのmetadataだけを確認する。
    with io.open_directory(launch.AUTH.parent) as fd:
        value = os.stat(launch.AUTH.name, dir_fd=fd, follow_symlinks=False)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid() and value.st_nlink == 1,
            'heldout standard CLI auth metadata unavailable')


def control_root(bound, ordinal):
    bound.slot(ordinal)
    return x.inputs.PRIVATE_CASES.parent/bound.contract['outputRelativeRoot']/'controls'/f'attempt-{ordinal:04d}'


def read_control(base, name):
    require(name in CONTROL_FILES, 'heldout fixed control read')
    fd = originals._open_root(base)
    try:
        file = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            value = os.fstat(file)
            require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
                and stat.S_IMODE(value.st_mode) == 0o600 and value.st_nlink == 1
                and 0 < value.st_size <= 65536, 'heldout control file metadata')
            with os.fdopen(file, 'rb', closefd=False) as stream:
                raw = stream.read(65537)
            after = os.fstat(file)
            fields = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            require(fields(value) == fields(after) and len(raw) == value.st_size, 'heldout control read drift')
            check_directory(base,fd)
            return raw
        finally:
            os.close(file)
    finally:
        os.close(fd)


def pace(bound, ordinal, role, ledger):
    """lock中の直前起動markerへ束縛する60秒の論理起動間隔。HTTP間隔の認定ではない。"""
    require(role == 'primary', 'heldout primary pacing role')
    rows, _ = ledger._history()
    started = [row for row in rows if row['stage'].endswith('_started')]
    previous_sha, previous = None, None
    if started:
        last = started[-1]
        # 独立処理の接続前は一次のみを許可する。後続adapterが独立markerを別途接続する。
        require(last['stage'] == 'primary_started', 'heldout independent pacing adapter not connected')
        raw = read_control(control_root(bound, last['ordinal']), 'pacing.json')
        previous_sha = io.sha(raw);previous = x.inputs.parse(raw)
        launch.pacing(bound.execution_raw,launch.primary_identity(bound,last['ordinal']),raw)
        anchors=[row for row in rows if row['ordinal'] == last['ordinal']
            and row['stage'] in {'primary_captured','primary_failed'}]
        require(len(anchors) == 1, 'heldout previous primary launch has no sealed original')
        receipt_raw=originals.read_original(bound.stage_root(last['ordinal'],'primary'),'receipt.json')
        require(io.sha(receipt_raw) == anchors[0]['artifactSha256'], 'heldout prior receipt journal binding')
        receipt_value=x.inputs.parse(receipt_raw)
        require(receipt_value.get('artifactSha256',{}).get('logical-pacing.json') == previous_sha
            and originals.read_original(bound.stage_root(last['ordinal'],'primary'),'logical-pacing.json') == raw,
            'heldout prior pacing receipt binding')
    now, wall = time.monotonic(), time.time()
    delay = 0.0
    if previous is not None:
        elapsed = now-previous['monotonicSeconds']
        require(elapsed >= 0 and wall >= previous['wallSeconds'], 'heldout pacing clock drift')
        delay = max(0.0, 60-elapsed)
        if delay:time.sleep(delay)
        require(time.monotonic()-previous['monotonicSeconds'] >= 60,
            'heldout minimum logical launch interval')
        require(io.sha(read_control(control_root(bound, last['ordinal']), 'pacing.json')) == previous_sha,
            'heldout previous pacing drift')
    value = dict(version=launch.PACING_VERSION, sourceCommit=bound.contract['sourceCommit'], executionSha256=io.sha(bound.execution_raw),
        ordinal=ordinal, role=role, monotonicSeconds=time.monotonic(), wallSeconds=time.time(),
        waitedSeconds=delay, previousSha256=previous_sha, declaresProviderInvoked=False, minimumGapSeconds=60)
    require(all(type(value[key]) in {int, float} and math.isfinite(value[key]) and value[key] >= 0
        for key in ['monotonicSeconds', 'wallSeconds', 'waitedSeconds']), 'heldout current pacing finite')
    launch.pacing(bound.execution_raw,launch.primary_identity(bound,ordinal),io.encoded(value))
    save(control_root(bound, ordinal), 'pacing.json', io.encoded(value))
    save(bound.stage_root(ordinal,'primary'),'logical-pacing.json',io.encoded(value))


def run_process(plan):
    """呼出し側のdurable started marker後だけ使用する。retryなし・有限timeout。"""
    process = None
    try:
        process = subprocess.Popen(plan['argv'], env=plan['environment'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, umask=0o077)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=plan['timeoutSeconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate(timeout=3)
        return process.returncode, timed_out, stdout, stderr
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=3)


def inputs_for_primary(repository, bound, ordinal, sdk_raw, review_raw, report_raw, isolation_raw):
    c = bound.contract;d = x.deployment_for_execution(bound.execution_raw, bound.deployment_raw)
    plan = launch.invocation(repository, bound.execution_raw, bound.deployment_raw, launch.primary_identity(bound, ordinal))
    return {'contract.json':bound.execution_raw, 'deployment.json':bound.deployment_raw,
        'sdk-manifest.json':sdk_raw, 'reservation.json':io.encoded(launch.primary_identity(bound, ordinal)),
        'model-input.json':bound.matrix.payloads[(ordinal-1)//2],
        'decision-schema.json':preflight.public.decision_schema(preflight.public.guard.git(repository, 'show',
            c['sourceCommit']+':'+preflight.public.inventory.SCHEMA)),
        'runtime-manifest.json':preflight.public.guard.git(repository, 'show',
            c['sourceCommit']+':'+preflight.public.capture.fixed_runtime.MANIFEST),
        'launch-settings.json':launch.launch_settings(bound.execution_raw, bound.deployment_raw),
        'invocation.json':io.encoded(plan), 'prelaunch-review.json':review_raw,
        'prelaunch-report.json':report_raw, 'local-isolation-proof.json':isolation_raw}


def collect(base):
    names = evidence.inventory.artifact_names(base, additional_artifacts=evidence.ADDITIONAL)
    require(len(names) <= originals.MAX_ORIGINALS, 'heldout finite collected originals')
    values, total = {}, 0
    for name in names:
        raw = originals.read_original(base, name);total += len(raw)
        require(total <= originals.MAX_TOTAL_BYTES, 'heldout finite collected original bytes')
        values[name] = raw
    return values


def collect_partial(base):
    """失敗時も既知原だけ。opaqueはmetadataのみ、未知/unsafe名は内容前で拒否。"""
    pending, names = [''], []
    while pending:
        relative = pending.pop()
        directory = base/relative
        fd = originals._open_root(directory)
        try:
            children = os.listdir(fd)
            if relative == 'rollout-traces':require(len(children) <= 1, 'heldout failed rollout group count')
            require(len(children) <= originals.MAX_ORIGINALS, 'heldout partial inventory bound')
            for name in children:
                path = str(Path(relative)/name) if relative else name
                value = os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(not stat.S_ISLNK(value.st_mode), 'heldout failed original symlink')
                if not relative and name in evidence.inventory.OPAQUE_DIRECTORIES:
                    require(stat.S_ISDIR(value.st_mode) and stat.S_IMODE(value.st_mode) == 0o700
                        and value.st_uid == os.getuid(), 'heldout failed opaque metadata')
                    continue
                if stat.S_ISDIR(value.st_mode):
                    parts = Path(path).parts
                    require(parts == ('rollout-traces',) or len(parts) == 2 and parts[0] == 'rollout-traces'
                        or len(parts) == 3 and parts[0] == 'rollout-traces' and parts[2] == 'payloads',
                        'heldout failed unknown directory')
                    if len(parts) >= 2:evidence.inventory.artifact_name('/'.join(parts[:2])+'/manifest.json')
                    pending.append(path)
                    require(len(pending) <= 3, 'heldout partial rollout group count')
                else:
                    if path not in evidence.ADDITIONAL:evidence.inventory.artifact_name(path)
                    require(stat.S_ISREG(value.st_mode), 'heldout failed nonregular original')
                    names.append(path)
                    require(len(names) <= originals.MAX_ORIGINALS, 'heldout partial original count')
        finally:
            os.close(fd)
    values, total = {}, 0
    for name in sorted(names):
        raw = originals.read_original(base,name);total += len(raw)
        require(total <= originals.MAX_TOTAL_BYTES, 'heldout partial original bytes')
        values[name] = raw
    return values


def receipt(bound, ordinal, values, elapsed, exit_code, timed_out):
    return dict(version=evidence.VERSION, sourceCommit=bound.contract['sourceCommit'], slot=bound.slot(ordinal),
        cwd=str(bound.stage_root(ordinal, 'primary')/'work'), artifactSha256={name:io.sha(raw) for name,raw in values.items()},
        elapsedSeconds=elapsed, namespaceExitCode=exit_code, timedOut=timed_out, primaryModelTrajectories=1,
        independentReviewPerformed=False, automaticRetries=0, phaseComplete=False, certifiesSkillGate=False)


def run_primary(repository, bound, ordinal, sdk_raw, review_raw, report_raw, isolation_raw):
    """本番private書込み・モデル入口。具体的独立開始前検分が未成立なら予約も行わない。"""
    x.rebound(bound);bound.slot(ordinal)
    launch.prelaunch_review(bound.execution_raw, bound.deployment_raw, review_raw, report_raw, isolation_raw)
    before = preflight.verify_resources(repository, bound, sdk_raw)
    auth_metadata()
    ledger = x.ledger.open_shared(bound.ledger_contract(io.encoded(before)))
    with ledger.locked():
        ledger.append(ordinal, 'primary_reserved')
        try:return _reserved_primary(repository, bound, ordinal, sdk_raw, review_raw, report_raw, isolation_raw, before, ledger)
        except BaseException as exc:
            error_raw=io.encoded(dict(version=VERSION,status='globally_stopped',ordinal=ordinal,errorType=type(exc).__name__))
            try:
                create_directory(control_root(bound,ordinal));save(control_root(bound,ordinal),'global-stop.json',error_raw)
            except (OSError,ValueError):pass
            # started前の保存失敗や不明な状態も次枠へ進ませず、消費を返さない。
            ledger.append(None, 'global_stop', io.sha(error_raw),
                stop_reason='operator_interrupted' if not isinstance(exc, Exception) else 'evidence_invalid')
            raise


def _reserved_primary(repository, bound, ordinal, sdk_raw, review_raw, report_raw, isolation_raw, before, ledger):
    base = bound.stage_root(ordinal, 'primary');control = control_root(bound, ordinal)
    # EXCLのstage作成を確認してから、同じprivate rootを再解決する。
    create_directory(base.parent)
    fd = originals._open_root(base.parent)
    try:os.mkdir(base.name, mode=0o700, dir_fd=fd);os.fsync(fd)
    finally:os.close(fd)
    for name in ['work', 'tmp', 'codex-home', 'logs', 'state', 'rollout-traces']:create_directory(base/name)
    create_directory(control)
    for name,raw in inputs_for_primary(repository,bound,ordinal,sdk_raw,review_raw,report_raw,isolation_raw).items():save(base,name,raw)
    invoke = preflight.verify_resources(repository,bound,sdk_raw)
    require(trace.json_equal(before,invoke), 'heldout resources changed before primary launch')
    pace(bound,ordinal,'primary',ledger)
    ledger.append(ordinal,'primary_started')
    plan = launch.invocation(repository,bound.execution_raw,bound.deployment_raw,launch.primary_identity(bound,ordinal))
    begin = time.monotonic()
    exit_code,timed_out,stdout,stderr = run_process(plan)
    elapsed = time.monotonic()-begin
    save(base,'namespace.stdout',stdout);save(base,'namespace.stderr',stderr)
    after = preflight.verify_resources(repository,bound,sdk_raw)
    guards = dict(before=before,invoke=invoke,after=after)
    save(base,'resource-guards.json',io.encoded(guards))
    require(trace.json_equal(before,after), 'heldout resources changed after primary launch')
    # 途中原でも未知名/stop markerを先に拒否し、通常終端を自己申告だけで扱わない。
    partial = collect_partial(base)
    sdk_terminal = x.inputs.parse(partial['isolated-result.json']) if 'isolated-result.json' in partial else None
    if sdk_terminal is not None:
        require(isinstance(sdk_terminal,dict) and set(sdk_terminal) == {'sdkErrorType'} and
            (sdk_terminal['sdkErrorType'] is None or isinstance(sdk_terminal['sdkErrorType'],str)
                and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',sdk_terminal['sdkErrorType']) is not None),
            'heldout SDK terminal shape')
    runtime_terminal = x.inputs.parse(partial['runtime-result.json']) if 'runtime-result.json' in partial else None
    if runtime_terminal is not None:
        require(isinstance(runtime_terminal,dict) and set(runtime_terminal) == {'exitCode','forcedShutdown','captureIntegrity'}
            and type(runtime_terminal['exitCode']) is int and type(runtime_terminal['forcedShutdown']) is bool
            and runtime_terminal['captureIntegrity'] is True, 'heldout unsafe or unknown native terminal')
    normal = (exit_code == 0 and not timed_out and sdk_terminal == {'sdkErrorType':None}
        and trace.json_equal(runtime_terminal,dict(exitCode=0,forcedShutdown=False,captureIntegrity=True)))
    if normal:
        values = collect(base)
        raw = io.encoded(receipt(bound,ordinal,values,elapsed,exit_code,timed_out));save(base,'receipt.json',raw)
        context = originals.load(bound,ordinal,source_repository=repository)
        verified = evidence.verify_complete(context)
        ledger.append(ordinal,'primary_captured',io.sha(raw))
        result = dict(version=VERSION,status='heldout_primary_captured_awaits_independent',
            ordinal=ordinal,receiptSha256=io.sha(raw),rawPayloadCorrelationVerified=verified['rawPayloadCorrelationVerified'],
            primaryLaunchMarked=1,namespaceInvocations=1,declaresProviderInvoked=False,reservations=1,automaticRetries=0,ledgerFinalized=False,eligibleForMeasurement=False,certifiesSkillGate=False)
    else:
        # 失敗原は許可固定名だけ読み、その場に保持。未知file/停止markerを成功扱いしない。
        values = partial
        raw=io.encoded(receipt(bound,ordinal,values,elapsed,exit_code,timed_out));save(base,'receipt.json',raw)
        failure=dict(version=VERSION,ordinal=ordinal,status='evaluation_failed',phase='primary',
            receiptSha256=io.sha(raw),resourceProofSha256=io.sha(io.encoded(before)),automaticRetries=0)
        save(control,'failure.json',io.encoded(failure))
        ledger.append(ordinal,'primary_failed',io.sha(raw),resource_proof_sha256=io.sha(io.encoded(before)))
        result=dict(version=VERSION,status='evaluation_failed',ordinal=ordinal,primaryLaunchMarked=1,namespaceInvocations=1,declaresProviderInvoked=False,reservations=1,
            automaticRetries=0,ledgerFinalized=False,eligibleForMeasurement=False,certifiesSkillGate=False)
    save(control,'primary-result.json',io.encoded(result))
    return result
