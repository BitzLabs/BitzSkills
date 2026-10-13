"""公開行列の一次取得。予約後の単回起動・原保存・構造検査まで。意味採点は別工程。"""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import production_matrix_originals as originals_reader
import production_matrix_launch as launch

p=launch.preflight
io=p.io
require=p.require
trace=p.trace
ROOT=Path(__file__).resolve().parents[3]
AUTH=Path('/home/hide/.codex/auth.json')
VERSION='public-matrix-primary-capture-0.1.0'
REVIEW_VERSION='public-matrix-primary-prelaunch-review-0.1.0'
REVIEW_KEYS={'version','scope','sourceCommit','conditionSha256','reviewReportSha256',
    'independentContext','severityCounts','certifiesSkillGate','certifiesRelease'}


def condition_sha256(bound,deployment_raw):
    """review自身のpinとそれに依存するexecution hashを除き循環を避ける。"""
    d=p.deployment(bound,deployment_raw);c=bound.contract
    del c['pins']['prelaunchReview'];del d['executionSha256']
    return io.sha(io.encoded(dict(execution=c,deployment=d)))


def prelaunch_review(bound,deployment_raw,review_raw,review_report_raw):
    require(isinstance(review_raw,bytes) and io.sha(review_raw)==bound.contract['pins']['prelaunchReview'],
        'matrix fixed prelaunch review bytes required')
    value=trace.strict_json(review_raw)
    require(isinstance(value,dict) and set(value)==REVIEW_KEYS
        and value['version']==REVIEW_VERSION and value['scope'] in {'public-matrix-primary-launch-only','public-matrix-primary-and-independent-launch-only'}
        and value['sourceCommit']==bound.contract['sourceCommit']
        and value['conditionSha256']==condition_sha256(bound,deployment_raw)
        and value['independentContext'] is True and trace.json_equal(value['severityCounts'],dict(P1=0,P2=0))
        and value['certifiesSkillGate'] is False and value['certifiesRelease'] is False,
        'matrix prelaunch review scope or condition drift')
    io.pin(value['reviewReportSha256'])
    require(isinstance(review_report_raw,bytes) and io.sha(review_report_raw)==value['reviewReportSha256'],
        'matrix original prelaunch report required')
    report=trace.strict_json(review_report_raw)
    require(isinstance(report,dict) and report.get('version')=='independent-review-1'
        and report.get('sourceCommit')==bound.contract['sourceCommit']
        and report.get('status')==('matrix_pipeline_prelaunch_code_verified' if value['scope']=='public-matrix-primary-and-independent-launch-only' else 'matrix_primary_capture_prelaunch_code_verified')
        and report.get('independentContext') is True and report.get('findings')==[]
        and report.get('blockingFindings')==[] and isinstance(report.get('tests'),dict)
        and type(report['tests'].get('count')) is int and report['tests']['count']>0
        and trace.json_equal(report['tests'].get('exitCode'),0)
        and report.get('cleanBefore')=='' and report.get('cleanAfter')=='',
        'matrix prelaunch report incomplete or source drift')
    return value


def namespace_command(source_repository,base,execution_raw,deployment_raw):
    """標準CLI認証を委譲するargvだけを構築。認証内容の読取・コピー・hashは行わない。"""
    d=p.deployment_for_execution(execution_raw,deployment_raw)
    c=p.matrix.execution_contract(execution_raw)
    require(source_repository.is_absolute() and base.is_absolute()
        and '..' not in source_repository.parts and '..' not in base.parts,'matrix absolute launch roots')
    require(base.parent.name==c['outputRelativeRoot'].split('/')[1]
        and base.parent.parent.name=='.venv' and base.name.startswith('attempt-')
        and len(base.name)==12 and base.name[8:].isdigit() and 1<=int(base.name[8:])<=92,'matrix primary base path')
    io.safe_tree(source_repository);io.safe_tree(base)
    args=['bwrap','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent',
        '--ro-bind','/','/','--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run','--proc','/proc','--dev','/dev']
    for path in [source_repository/p.capture.fixed_runtime.MANIFEST,source_repository/d['sdkRelativePath'],
        source_repository/d['snapshotRelativePath'],Path(d['codexPath']).parents[1],
        *(source_repository/name for name in p.SOURCE_FILES if name.endswith('.py'))]:
        args+=['--ro-bind',str(path),str(path)]
    return args+['--bind',str(base),str(base),'--bind',str(base/'codex-home'),'/home/hide/.codex',
        '--ro-bind',str(AUTH),'/home/hide/.codex/auth.json','--chdir',str(base/'work'),'--','/usr/bin/python3','-B',
        str(source_repository/'evals/skills/routing/production_matrix_capture.py'),'--isolated',str(base)]


def environment(base,d):
    value=launch.local_environment(base,d,calibration_only=True)
    value['CODEX_HOME']='/home/hide/.codex'
    return value


def auth_metadata():
    with io.open_directory(AUTH.parent) as fd:
        value=os.stat(AUTH.name,dir_fd=fd,follow_symlinks=False)
        require(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.getuid(),
            'standard CLI authentication metadata unavailable')


@contextmanager
def locked_control(root):
    io.safe_tree(root);root.mkdir(parents=True,mode=0o700,exist_ok=True)
    value=root.stat();require(value.st_uid==os.getuid() and stat.S_IMODE(value.st_mode)==0o700,'matrix control directory mode')
    with io.open_directory(root) as opened:
        fd=os.open('launch.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=opened)
    with os.fdopen(fd,'r+b') as stream:
        value=os.fstat(stream.fileno())
        require(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.getuid()
            and stat.S_IMODE(value.st_mode)==0o600,'matrix control lock mode')
        try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise ValueError('matrix launch already running') from error
        yield


def collect_originals(base):
    additions=originals_reader.provider.evidence.PROVIDER_ARTIFACTS
    names=p.inventory.artifact_names(base,additional_artifacts=additions)
    values={name:io.read_regular(base/name) for name in names}
    p.inventory.artifact_inventory(base,{name:io.sha(raw) for name,raw in values.items()},additional_artifacts=additions)
    return values


def invocation(source_repository,base,bound,deployment_raw,ordinal):
    p.deployment(bound,deployment_raw)
    return invocation_for_slot(source_repository,base,bound.execution_raw,deployment_raw,bound.slot(ordinal))


def invocation_for_slot(source_repository,base,execution_raw,deployment_raw,slot):
    d=p.deployment_for_execution(execution_raw,deployment_raw);c=p.matrix.execution_contract(execution_raw)
    ordinal=slot.get('ordinal') if isinstance(slot,dict) else None
    require(type(ordinal) is int and 1<=ordinal<=92 and base.name==f'attempt-{ordinal:04d}', 'matrix launch slot/base drift')
    io.pin(slot.get('payloadSha256'))
    require(set(slot)=={'ordinal','caseId','repetition','payloadSha256','contractSha256','campaignId','sourceCommit','executionSha256'}
        and trace.json_equal(slot,dict(ordinal=ordinal,caseId=f'SE-{(ordinal-1)//2+1:03d}',repetition=(ordinal-1)%2+1,
            payloadSha256=slot['payloadSha256'],contractSha256=c['inputContractSha256'],campaignId=c['campaignId'],
            sourceCommit=c['sourceCommit'],executionSha256=io.sha(execution_raw))),'matrix launch slot identity drift')
    return dict(version=VERSION,sourceCommit=c['sourceCommit'],slot=slot,
        executionSha256=io.sha(execution_raw),deploymentSha256=io.sha(deployment_raw),
        prelaunchReviewSha256=c['pins']['prelaunchReview'],
        argv=namespace_command(source_repository,base,execution_raw,deployment_raw),
        environment=environment(base,d),maximumLogicalTurns=1,automaticRetries=0,
        timeoutSeconds=c['timeoutSeconds']['primary'])


def verify_launch(context,source_repository,artifact_repository,review_raw,review_report_raw):
    """既存の原bytes相関に加え、保存したargv/環境と開始前検分を束縛する。"""
    provider=originals_reader.provider
    proof=provider.verify_bytes(context,source_repository=source_repository,artifact_repository=artifact_repository)
    values=context.originals;d_raw=values['deployment.json']
    prelaunch_review(context.bound,d_raw,review_raw,review_report_raw)
    base=artifact_repository/context.bound.contract['outputRelativeRoot']/f'attempt-{context.ordinal:04d}'
    require(values['invocation.json']==io.encoded(invocation(source_repository,base,context.bound,d_raw,context.ordinal)),
        'matrix actual invocation declaration drift')
    return dict(proof,invocationArgvBytesMatched=True,prelaunchReviewSha256=io.sha(review_raw),
        independentModelExecutionVerified=False,ledgerFinalized=False,eligibleForMeasurement=False)


def run(source_repository,bound,deployment_raw,sdk_manifest_raw,review_raw,review_report_raw,ordinal):
    slot=bound.slot(ordinal);prelaunch_review(bound,deployment_raw,review_raw,review_report_raw)
    before=p.verify_resources(source_repository,bound,deployment_raw,sdk_manifest_raw)
    auth_metadata()
    artifact_repository=io.common_ledger_path(source_repository).parent.parent
    control=artifact_repository/'.venv/production-matrix-launch-controls'/bound.contract['campaignId']
    with locked_control(control):
        for name,raw in [('prelaunch-review.json',review_raw),('prelaunch-report.json',review_report_raw)]:
            saved=control/name
            if p.matrix.present(saved):require(io.read_regular(saved)==raw,'matrix stored prelaunch review drift')
            else:io.exclusive(saved,raw)
        storage=p.matrix.shared_storage(source_repository,bound)
        io.safe_tree(storage.parent);storage.parent.mkdir(mode=0o700,exist_ok=True)
        instance=p.matrix.MatrixLedger(storage,artifact_repository,bound)
        instance.reserve(ordinal)
        return _reserved_capture(source_repository,artifact_repository,bound,deployment_raw,sdk_manifest_raw,review_raw,review_report_raw,
            ordinal,slot,before,control,instance)


def _reserved_capture(source_repository,artifact_repository,bound,d_raw,sdk_raw,review_raw,review_report_raw,ordinal,slot,before,control,instance):
    base=artifact_repository/bound.contract['outputRelativeRoot']/f'attempt-{ordinal:04d}'
    process=None;started=False;created=False;timed_out=False;error=None;values={};result=None;after=None;invoke=None
    stdout=stderr=b'';begin=time.monotonic();caught=None
    try:
        io.safe_tree(base);base.mkdir(parents=True,mode=0o700,exist_ok=False);created=True
        for name in ['work','tmp','codex-home','logs','state','rollout-traces']:(base/name).mkdir(mode=0o700)
        source=slot['sourceCommit'];d=p.deployment(bound,d_raw)
        schema_raw=p.decision_schema(p.guard.git(source_repository,'show',source+':'+p.inventory.SCHEMA))
        context_raw=p.guard.git(source_repository,'show',source+':'+p.inventory.CONTEXT)
        manifest_raw=io.read_regular(source_repository/d['snapshotRelativePath']/'manifest.json')
        capture_env=originals_reader.provider.environment_spec(SimpleNamespace(bound=bound,ordinal=ordinal),source_repository,artifact_repository)
        plan=invocation(source_repository,base,bound,d_raw,ordinal)
        for name,raw in [('contract.json',bound.execution_raw),('deployment.json',d_raw),('sdk-manifest.json',sdk_raw),
            ('reservation.json',io.encoded(slot)),('model-input.json',bound.matrix.payloads[(ordinal-1)//2]),
            ('decision-schema.json',schema_raw),('runtime-manifest.json',p.guard.git(source_repository,'show',source+':'+p.capture.fixed_runtime.MANIFEST)),
            ('launch-settings.json',launch.launch_settings(bound.execution_raw,d_raw)),('capture-environment.json',io.encoded(capture_env)),
            ('invocation.json',io.encoded(plan))]:io.exclusive(base/name,raw)
        invoke=p.verify_resources(source_repository,bound,d_raw,sdk_raw)
        require(invoke==before,'matrix resources changed before invocation; reservation consumed')
        instance.mark_primary_started(ordinal);started=True
        begin=time.monotonic()
        process=subprocess.Popen(plan['argv'],env=plan['environment'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:stdout,stderr=process.communicate(timeout=plan['timeoutSeconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGTERM)
            try:stdout,stderr=process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=3)
        io.exclusive(base/'namespace.stdout',stdout);io.exclusive(base/'namespace.stderr',stderr)
        after=p.verify_resources(source_repository,bound,d_raw,sdk_raw)
        io.exclusive(base/'resource-guards.json',io.encoded(dict(before=before,invoke=invoke,after=after)))
        require(before==after and process.returncode==0 and not timed_out,'matrix primary process or resources stopped')
        values=collect_originals(base)
        receipt=_receipt(bound,ordinal,base,values,time.monotonic()-begin,process.returncode,timed_out,started)
        io.exclusive(base/'receipt.json',io.encoded(receipt))
        context=originals_reader.load_provider_capture(bound,ordinal,source_repository=source_repository,
            artifact_repository=artifact_repository,manifest_raw=manifest_raw,schema_raw=schema_raw,context_raw=context_raw)
        result=verify_launch(context,source_repository,artifact_repository,review_raw,review_report_raw)
        instance.record_primary(ordinal,dict(slot,actualInvocations=1,normalTerminal=True,nativeExitCode=0,integrityPassed=True,
            receipt=dict(relativePath=(base/'receipt.json').relative_to(artifact_repository).as_posix(),sha256=io.sha(context.receipt_raw)),
            trace=dict(relativePath=(base/'rpc-out.jsonl').relative_to(artifact_repository).as_posix(),sha256=io.sha(values['rpc-out.jsonl']))))
    except BaseException as exc:
        caught=exc;error=type(exc).__name__
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=3)
            except Exception:pass
        instance.stop(ordinal,'primary-capture-rejected',error)
        if created:
            for name,raw in [('namespace.stdout',stdout),('namespace.stderr',stderr),
                ('resource-guards.json',io.encoded(dict(before=before,invoke=invoke,after=after)))]:
                if not p.matrix.present(base/name):io.exclusive(base/name,raw)
            if not p.matrix.present(base/'capture-stop.json'):
                io.exclusive(base/'capture-stop.json',io.encoded(dict(reason='primary-capture-rejected',errorType=error)))
            if not p.matrix.present(base/'receipt.json'):
                # 失敗時は既知固定名だけのhash。未知/opaque内容は読まず原をその場へ保持。
                for name in sorted(p.inventory.FIXED_ARTIFACTS|originals_reader.provider.evidence.PROVIDER_ARTIFACTS):
                    try:values[name]=io.read_regular(base/name)
                    except (ValueError,OSError):pass
                io.exclusive(base/'receipt.json',io.encoded(_receipt(bound,ordinal,base,values,time.monotonic()-begin,
                    process.returncode if process else None,timed_out,started)))
    output=dict(version=VERSION,status='primary_capture_awaits_independent_review' if result is not None and error is None else 'primary_capture_stopped',
        sourceCommit=bound.contract['sourceCommit'],slot=slot,started=started,actualNamespaceInvocations=int(process is not None),
        errorType=error,timedOut=timed_out,verification=result,automaticRetries=0,independentModelExecutionVerified=False,
        ledgerFinalized=False,eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False)
    io.exclusive(control/f'result-{ordinal:04d}.json',io.encoded(output))
    if caught is not None and not isinstance(caught,Exception):raise caught
    return output


def _receipt(bound,ordinal,base,values,seconds,exit_code,timed_out,started):
    return dict(version=originals_reader.provider.evidence.PROVIDER_VERSION,sourceCommit=bound.contract['sourceCommit'],
        slot=bound.slot(ordinal),cwd=str(base/'work'),artifactSha256={name:io.sha(raw) for name,raw in values.items()},
        elapsedSeconds=seconds,namespaceExitCode=exit_code,timedOut=timed_out,primaryModelTrajectories=int(started),
        independentReviewPerformed=False,automaticRetries=0,phaseComplete=False,certifiesSkillGate=False)


def isolated(base):
    execution_raw=io.read_regular(base/'contract.json');c=p.matrix.execution_contract(execution_raw)
    d_raw=io.read_regular(base/'deployment.json');d=p.deployment_for_execution(execution_raw,d_raw)
    require(not any((ROOT/name).exists() for name in ['.git','.spec','docs','tests','evals/skills/results']),'matrix evaluation tree visible')
    slot=trace.strict_json(io.read_regular(base/'reservation.json'))
    require(slot.get('executionSha256')==io.sha(execution_raw) and slot.get('sourceCommit')==c['sourceCommit']
        and slot.get('payloadSha256')==io.sha(io.read_regular(base/'model-input.json')),'matrix child input drift')
    require(io.read_regular(base/'invocation.json')==io.encoded(invocation_for_slot(ROOT,base,execution_raw,d_raw,slot)),
        'matrix child invocation drift')
    sdk_files=p.sdk_manifest(io.read_regular(base/'sdk-manifest.json'),d)
    require({name:io.sha(raw) for name,raw in p.exact_tree(ROOT/d['sdkRelativePath'],sdk_files).items()}==sdk_files,'matrix child SDK drift')
    p.capture.fixed_runtime.verify(io.read_regular(base/'runtime-manifest.json'),d)
    schema_raw=io.read_regular(base/'decision-schema.json')
    require(io.sha(schema_raw)==c['pins']['decisionSchema'],'matrix child Schema drift')
    sys.path.insert(0,str(ROOT/d['sdkRelativePath']))
    from openai_codex import CodexConfig,__version__
    from openai_codex.client import CodexClient
    require(__version__==d['sdkVersion'],'matrix child SDK version drift')
    version=subprocess.run([d['codexPath'],'--version'],capture_output=True,timeout=10)
    io.exclusive(base/'version.stdout',version.stdout);io.exclusive(base/'version.stderr',version.stderr)
    require(version.returncode==0 and version.stdout==(d['codexVersion']+'\n').encode() and not version.stderr,'matrix child CLI version drift')
    require(io.read_regular(base/'launch-settings.json')==launch.launch_settings(execution_raw,d_raw),'matrix child launch settings drift')
    io.exclusive(base/'config.json',io.encoded(p.capture.config_for(base,d,repository=ROOT)))
    def deny(*_):raise ValueError('unexpected matrix SDK request')
    client=CodexClient(CodexConfig(launch_args_override=(sys.executable,'-B',str(Path(__file__)),'--proxy',str(base)),
        cwd=str(base/'work')),approval_handler=deny)
    error=None
    try:
        client.start();client.initialize()
        thread=client.thread_start(dict(model=c['model'],modelProvider='bitz_openai_http',allowProviderModelFallback=False,
            cwd=str(base/'work'),sandbox='read-only',approvalPolicy='never',ephemeral=True,
            baseInstructions=p.capture.BASE,developerInstructions=p.capture.DEVELOPER,experimentalRawEvents=True))
        turn=client.turn_start(thread.thread.id,io.read_regular(base/'model-input.json').decode(),
            dict(outputSchema=p.capture.execution_schema(trace.strict_json(schema_raw)),effort='low'))
        while client.next_turn_notification(turn.turn.id).method!='turn/completed':pass
    except Exception as exc:error=type(exc).__name__
    finally:client.close()
    io.exclusive(base/'isolated-result.json',io.encoded(dict(sdkErrorType=error)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--isolated',type=Path);parser.add_argument('--proxy',type=Path);args=parser.parse_args()
    if args.proxy:p.capture.sdk.proxy(args.proxy,reject_questions=True,capture_guard=p.capture.CaptureGuard(args.proxy),
        launch_contract_raw=io.read_regular(args.proxy/'launch-settings.json'))
    elif args.isolated:isolated(args.isolated)
    else:parser.error('isolated/proxy child only; parent requires bound inputs and independent prelaunch review')
