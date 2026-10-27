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
import production_stop_policy as policy

x, evidence = originals.x, originals.evidence
launch, preflight = evidence.launch, evidence.preflight
io, require, trace = x.io, x.require, x.trace
VERSION = 'heldout-primary-operator-0.1.0'
CONTROL_FILES = {'pacing.json', 'primary-result.json', 'failure.json', 'global-stop.json', 'independent-pacing.json',
    'failure-acknowledgement.json', 'retry-authorization.json', 'retry-review.json'}


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


def save(base, name, raw, *, additional_artifacts=frozenset()):
    """固定basenameだけをlock中のprivate rootへEXCL/NOFOLLOWで新規保存する。"""
    originals.additional_names(additional_artifacts)
    require(name in evidence.inventory.FIXED_ARTIFACTS | evidence.ADDITIONAL
        | {'receipt.json', *CONTROL_FILES} | additional_artifacts, 'heldout write fixed name')
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


def successor_ledger(ledger):
    return getattr(ledger, 'records_daily_proof', False)


def stop_reason(ledger, error):
    # 版0.1/0.2の台帳は従来の2理由だけを受ける。区分は後継台帳だけに記録する（ADR-068 D1）。
    if successor_ledger(ledger):
        return policy.stop_reason(error)
    return 'operator_interrupted' if not isinstance(error, Exception) else 'evidence_invalid'


def daily_proof(ledger, proof):
    return io.sha(io.encoded(proof)) if successor_ledger(ledger) else None


def harness_check(reason, check, *args):
    """評価環境の変化と判定できる検査の失敗だけを、評価基盤の障害として型付けする。"""
    try:
        return check(*args)
    except policy.HarnessFault:
        raise
    except ValueError as exc:
        raise policy.HarnessFault(reason, str(exc)) from None


def same_resources(before, current, message):
    if not trace.json_equal(before, current):
        raise policy.HarnessFault('resource_drift', message)


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


def verify_pacing(bound, ordinal, role, *, expected_sha256=None):
    """子へmountしない外側controlと、子stageの原bytesを直接照合する。"""
    require(role in {'primary','independent'}, 'heldout pacing role')
    name = 'pacing.json' if role == 'primary' else 'independent-pacing.json'
    control = read_control(control_root(bound,ordinal),name)
    raw = originals.read_original(bound.stage_root(ordinal,role),'logical-pacing.json')
    require(raw == control, 'heldout pacing differs from outside control')
    if expected_sha256 is not None:
        require(io.sha(raw) == io.pin(expected_sha256), 'heldout pacing differs from prelaunch original')
    launch.pacing(bound.execution_raw,launch.primary_identity(bound,ordinal),raw,role=role)
    return raw


def pace(bound, ordinal, role, ledger):
    """lock中の直前journal/receiptへ束縛する60秒の論理起動間隔。HTTP間隔は認定しない。"""
    require(role in {'primary','independent'}, 'heldout pacing role')
    rows,_=ledger._history();started=[row for row in rows if row['stage'].endswith('_started')]
    previous_sha,previous=None,None
    handoff = None
    if started:
        last=started[-1];previous_role=last['stage'].removesuffix('_started')
        require(previous_role in {'primary','independent'}, 'heldout prior launch role')
        # 後継台帳は再試行の枠を番号順の外で予約する。順序は台帳の遷移規則が検査する。
        require((role=='independent' and previous_role=='primary' and last['ordinal']==ordinal)
            or (role=='primary' and (successor_ledger(ledger) or last['ordinal']==ordinal-1)),
            'heldout previous pacing stage order')
        name='pacing.json' if previous_role=='primary' else 'independent-pacing.json'
        raw=read_control(control_root(bound,last['ordinal']),name);previous_sha=io.sha(raw)
        previous=launch.pacing(bound.execution_raw,launch.primary_identity(bound,last['ordinal']),raw,role=previous_role)
        anchors=[row for row in rows if row['ordinal']==last['ordinal']
            and row['stage'] in {previous_role+'_captured',previous_role+'_failed'}]
        require(len(anchors)==1, 'heldout previous launch has no sealed original')
        previous_base=bound.stage_root(last['ordinal'],previous_role)
        receipt_name='receipt.json' if previous_role=='primary' else 'independent-receipt.json'
        receipt_raw=originals.read_original(previous_base,receipt_name,
            additional_artifacts=frozenset({'independent-receipt.json'}))
        require(io.sha(receipt_raw)==anchors[0]['artifactSha256'], 'heldout prior receipt journal binding')
        receipt_value=x.inputs.parse(receipt_raw)
        require(receipt_value.get('artifactSha256',{}).get('logical-pacing.json')==previous_sha
            and originals.read_original(previous_base,'logical-pacing.json')==raw, 'heldout prior pacing receipt binding')
    else:
        from production_heldout_continuation import ContinuationLedger, prior_pacing, ANCHOR_SHA256
        if successor_ledger(ledger):
            # campaignの最初の起動は、前のcampaignの原を参照せず、新しい時計で必ず60秒待つ。
            require(role == 'primary', 'heldout successor first launch')
            previous = dict(monotonicSeconds=time.monotonic(), wallSeconds=time.time())
        elif isinstance(ledger, ContinuationLedger):
            require(role == 'primary' and ordinal == 2, 'heldout continuation first launch')
            old, previous_sha = prior_pacing()
            require(time.time() >= old['wallSeconds'], 'heldout prior wall clock drift')
            previous = dict(monotonicSeconds=time.monotonic(), wallSeconds=time.time())
            require(previous['wallSeconds'] >= old['wallSeconds'], 'heldout prior wall clock drift')
            handoff = dict(priorStopAnchorSha256=ANCHOR_SHA256, witnessMonotonicSeconds=previous['monotonicSeconds'],
                witnessWallSeconds=previous['wallSeconds'])
        else:
            require(role=='primary' and ordinal==1, 'heldout first logical launch')
    now,wall=time.monotonic(),time.time();delay=0.0
    if previous is not None:
        elapsed=now-previous['monotonicSeconds']
        require(elapsed>=0 and wall>=previous['wallSeconds'], 'heldout pacing clock drift')
        delay=60.0 if handoff is not None or previous_sha is None else max(0.0,60-elapsed)
        if delay:time.sleep(delay)
        require(time.monotonic()-previous['monotonicSeconds']>=60, 'heldout minimum logical launch interval')
        if handoff is not None:
            require(prior_pacing()[1] == previous_sha, 'heldout prior stop changed during handoff')
        elif previous_sha is not None:
            require(io.sha(read_control(control_root(bound,last['ordinal']),name))==previous_sha, 'heldout previous pacing drift')
    value=dict(version=launch.PACING_VERSION,sourceCommit=bound.contract['sourceCommit'],executionSha256=io.sha(bound.execution_raw),
        ordinal=ordinal,role=role,monotonicSeconds=time.monotonic(),wallSeconds=time.time(),waitedSeconds=delay,
        previousSha256=previous_sha,declaresProviderInvoked=False,minimumGapSeconds=60)
    if handoff is not None:value.update(version='heldout-logical-pacing-0.2.0', handoff=handoff)
    raw=io.encoded(value);launch.pacing(bound.execution_raw,launch.primary_identity(bound,ordinal),raw,role=role)
    save(control_root(bound,ordinal),'pacing.json' if role=='primary' else 'independent-pacing.json',raw)
    save(bound.stage_root(ordinal,role),'logical-pacing.json',raw)


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
    return {launch.model_catalog.FILE:launch.model_catalog.fixed_catalog(),
        'config.json':io.encoded(launch.model_catalog.configuration(bound.stage_root(ordinal,'primary'),
            preflight.public.capture.config_for(bound.stage_root(ordinal,'primary'),d,repository=repository))),
        'contract.json':bound.execution_raw, 'deployment.json':bound.deployment_raw,
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
    audit_partial(values)
    return values


def audit_partial(values):
    """途中JSONLの末尾欠落は未完のまま保持し、認識可能な禁止操作は失敗封印しない。"""
    for name in ['rpc-out.jsonl','trace-safe.jsonl','runtime-stderr.bin','namespace.stderr']:
        # 選択logとその原stderrは同じeventを含むため、各原を独立に検査する。
        counts = {'control':0, '/models':0, '/responses':0}
        diagnostic = name in {'runtime-stderr.bin','namespace.stderr'}
        raw = values.get(name,b'')
        lines = raw.splitlines()
        for index,line in enumerate(lines):
            try:value = x.inputs.parse(line)
            except ValueError:
                if diagnostic:continue
                require(index == len(lines)-1 and not raw.endswith(b'\n'), 'heldout partial malformed complete JSONL')
                continue
            if diagnostic and not isinstance(value,dict):continue
            require(isinstance(value,dict), 'heldout partial JSONL object')
            if name == 'rpc-out.jsonl':
                require(not ('id' in value and 'method' in value), 'heldout partial server request')
                if 'method' in value:
                    require(isinstance(value['method'],str) and isinstance(value.get('params'),dict),
                        'heldout partial notification shape')
                if value.get('method') in {'item/started','item/completed'}:
                    item = value['params'].get('item')
                    require(isinstance(item,dict) and item.get('type') in
                        {'userMessage','agentMessage','reasoning','mcpToolCall'}, 'heldout partial unknown action')
                    if item['type'] == 'mcpToolCall':
                        require(item.get('server') == 'production-routing' and item.get('tool') in
                            {'list_resources','read_resource'}, 'heldout partial unknown host tool')
            else:
                fields = value.get('fields',{})
                require(isinstance(fields,dict), 'heldout partial telemetry fields')
                if fields.get('event.name') == 'codex.tool_call_received':
                    source = fields.get('tool_source')
                    if source == 'direct':
                        counts['control'] += 1
                        require(fields.get('tool_name') in {'exec','wait'} and counts['control'] <= 2,
                            'heldout partial control policy')
                    else:
                        require(source == 'code_mode' and fields.get('tool_namespace') == 'mcp__production_routing'
                            and fields.get('tool_name') in {'list_resources','read_resource'},
                            'heldout partial unknown child source or tool')
                elif fields.get('event.name') == 'codex.api_request':
                    endpoint = fields.get('endpoint')
                    require(endpoint in {'/models','/responses'} and type(fields.get('attempt')) is int
                        and fields['attempt'] == 0 and fields.get('auth.retry_after_unauthorized',False) is False,
                        'heldout partial unknown API or retry')
                    counts[endpoint] += 1
                    require(counts[endpoint] <= (2 if endpoint == '/models' else 3), 'heldout partial API limit')


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
        ledger.append(ordinal, 'primary_reserved', resource_proof_sha256=daily_proof(ledger, before))
        try:return _reserved_primary(repository, bound, ordinal, sdk_raw, review_raw, report_raw, isolation_raw, before, ledger)
        except BaseException as exc:
            error_raw=io.encoded(dict(version=VERSION,status='globally_stopped',ordinal=ordinal,errorType=type(exc).__name__))
            try:
                create_directory(control_root(bound,ordinal));save(control_root(bound,ordinal),'global-stop.json',error_raw)
            except (OSError,ValueError):pass
            # started前の保存失敗や不明な状態も次枠へ進ませず、消費を返さない。
            ledger.append(None, 'global_stop', io.sha(error_raw), stop_reason=stop_reason(ledger, exc))
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
    expected_inputs = inputs_for_primary(repository,bound,ordinal,sdk_raw,review_raw,report_raw,isolation_raw)
    for name,raw in expected_inputs.items():save(base,name,raw)
    pace(bound,ordinal,'primary',ledger)
    pacing_sha = io.sha(verify_pacing(bound,ordinal,'primary'))
    invoke = preflight.verify_resources(repository,bound,sdk_raw)
    same_resources(before, invoke, 'heldout resources changed before primary launch')
    harness_check('provider_drift', launch.model_catalog.verify, originals.read_original(base, launch.model_catalog.FILE))
    require(all(originals.read_original(base,name) == raw for name,raw in expected_inputs.items()),
        'heldout primary input changed before launch')
    ledger.append(ordinal,'primary_started')
    plan = launch.invocation(repository,bound.execution_raw,bound.deployment_raw,launch.primary_identity(bound,ordinal))
    begin = time.monotonic()
    exit_code,timed_out,stdout,stderr = run_process(plan)
    elapsed = time.monotonic()-begin
    save(base,'namespace.stdout',stdout);save(base,'namespace.stderr',stderr)
    after = preflight.verify_resources(repository,bound,sdk_raw)
    guards = dict(before=before,invoke=invoke,after=after)
    save(base,'resource-guards.json',io.encoded(guards))
    same_resources(before, after, 'heldout resources changed after primary launch')
    verify_pacing(bound,ordinal,'primary',expected_sha256=pacing_sha)
    # 途中原でも未知名/stop markerを先に拒否し、通常終端を自己申告だけで扱わない。
    partial = collect_partial(base)
    harness_check('provider_drift', launch.model_catalog.verify, partial.get(launch.model_catalog.FILE))
    require(all(partial.get(name) == raw for name,raw in expected_inputs.items()),
        'heldout primary input changed during process')
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
