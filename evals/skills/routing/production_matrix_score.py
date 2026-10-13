"""公開92枠の単回独立採点と親原照合。一次原を置換せず、失敗は恒久停止する。"""
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import time

import production_matrix_capture as capture
import production_matrix_semantic as semantic

p=capture.p
io=capture.io
trace=capture.trace
require=capture.require
matrix=p.matrix
VERSION='public-matrix-independent-capture-0.1.0'
SCOPE='public-matrix-primary-and-independent-launch-only'
ARTIFACTS=frozenset({'contract.json','review-input.json','bindings.json','prompt.txt','schema.json',
    'execution-schema.json','reservation.json','config.json','invocation.json','resource-guards.json',
    'trace.jsonl','stderr.bin','response.json'})
OPAQUE=frozenset({'work','tmp','codex-home','logs','state'})
RECEIPT_KEYS={'version','status','slot','model','scope','consumedReservations','independentInvocations',
    'primaryModelTrajectories','automaticRetries','exitCode','timedOut','elapsedSeconds','errorType',
    'artifactSha256','eligibleForMeasurement','certifiesBehavior','certifiesSkillGate'}


def layout(artifact_repository,bound,ordinal):
    bound.slot(ordinal)
    return artifact_repository/(bound.contract['outputRelativeRoot']+'-independent')/f'attempt-{ordinal:04d}'


def config_for(base):
    # 既存のSOL専用HTTP/no-tool/readonly/never/retry0設定を再利用する。
    return semantic.legacy_terminal.config_for(base)


def environment(base,d):
    return dict(PATH=str(Path(d['codexPath']).parents[1]/'bin')+':/usr/bin:/bin',LANG='C.UTF-8',
        HOME='/home/hide',CODEX_HOME='/home/hide/.codex',TMPDIR=str(base/'tmp'),
        TZ='Asia/Tokyo',PYTHONDONTWRITEBYTECODE='1')


def command_for(base,d):
    argv=[d['codexPath'],'exec','--json','--ephemeral','--ignore-user-config','--ignore-rules',
        '--skip-git-repo-check','--sandbox','read-only','--cd',str(base/'work'),'--model','gpt-6.1-sol',
        '--output-schema',str(base/'execution-schema.json'),'--output-last-message',str(base/'response.json')]
    for key,value in config_for(base).items():argv+=['-c',key+'='+p.capture.sdk.toml_value(value)]
    argv+=['-']
    return ['bwrap','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent','--ro-bind','/','/',
        '--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run','--proc','/proc','--dev','/dev',
        '--ro-bind',str(Path(d['codexPath']).parents[1]),str(Path(d['codexPath']).parents[1]),
        '--bind',str(base),str(base),'--bind',str(base/'codex-home'),'/home/hide/.codex',
        '--ro-bind',str(capture.AUTH),'/home/hide/.codex/auth.json','--chdir',str(base/'work'),'--',*argv]


def invocation(prepared,base):
    d=p.deployment(prepared.context.bound,prepared.context.originals['deployment.json'])
    return dict(version=VERSION,slot=prepared.context.bound.slot(prepared.context.ordinal),
        argv=command_for(base,d),environment=environment(base,d),model='gpt-6.1-sol',
        promptSha256=io.sha(semantic.prompt(prepared)),reviewInputSha256=prepared.bindings['reviewInputSha256'],
        prelaunchReviewSha256=prepared.context.bound.contract['pins']['prelaunchReview'],
        maximumLogicalTurns=1,automaticRetries=0,
        timeoutSeconds=prepared.context.bound.contract['timeoutSeconds']['independent'])


def input_originals(prepared,base,reservation):
    return {'contract.json':prepared.contract_raw,'review-input.json':prepared.input_raw,
        'bindings.json':prepared.binding_raw,'prompt.txt':semantic.prompt(prepared),'schema.json':prepared.schema_raw,
        'execution-schema.json':io.encoded(p.capture.execution_schema(trace.strict_json(prepared.schema_raw))),
        'reservation.json':io.encoded(reservation),'config.json':io.encoded(config_for(base)),
        'invocation.json':io.encoded(invocation(prepared,base))}


def artifact_names(base):
    """固定した一段の公開原だけ。opaqueはmetadata検査に留め、内容前に未知名を拒否する。"""
    actual=set()
    with io.open_directory(base) as fd:
        for name in os.listdir(fd):
            value=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if name in OPAQUE:
                require(stat.S_ISDIR(value.st_mode),'matrix score opaque directory shape')
                continue
            require(name in ARTIFACTS|{'independent-receipt.json','parent-verification.json','stop.json'},
                'matrix score unknown original')
            require(stat.S_ISREG(value.st_mode) and value.st_nlink==1,'matrix score original file shape')
            if name in ARTIFACTS:actual.add(name)
            require(name!='stop.json','matrix score stopped original')
    require(actual==ARTIFACTS,'matrix score original inventory incomplete')
    return sorted(actual)


def load_primary(source_repository,bound,ordinal,manifest_raw,schema_raw,context_raw,review_raw,report_raw):
    artifact_repository=io.common_ledger_path(source_repository).parent.parent
    context=capture.originals_reader.load_provider_capture(bound,ordinal,source_repository=source_repository,
        artifact_repository=artifact_repository,manifest_raw=manifest_raw,schema_raw=schema_raw,context_raw=context_raw)
    capture.verify_launch(context,source_repository=source_repository,artifact_repository=artifact_repository,
        review_raw=review_raw,review_report_raw=report_raw)
    approved=capture.prelaunch_review(bound,context.originals['deployment.json'],review_raw,report_raw)
    require(approved['scope']==SCOPE and trace.strict_json(report_raw)['status']=='matrix_pipeline_prelaunch_code_verified',
        'matrix independent prelaunch scope required')
    instance=matrix.MatrixLedger(matrix.shared_storage(source_repository,bound),artifact_repository,bound)
    primary=instance.read('primary',ordinal);instance.primary_valid(primary,ordinal)
    require(primary['receipt']['sha256']==io.sha(context.receipt_raw)
        and primary['trace']['sha256']==io.sha(context.originals['rpc-out.jsonl']),'matrix score primary record drift')
    prepared=semantic.prepare(context,source_repository=source_repository,artifact_repository=artifact_repository)
    return artifact_repository,instance,prepared


def resources(prepared):
    return p.verify_resources(prepared.source_repository,prepared.context.bound,
        prepared.context.originals['deployment.json'],prepared.context.originals['sdk-manifest.json'])


def control_root(artifact_repository,bound):
    return artifact_repository/'.venv/production-matrix-launch-controls'/bound.contract['campaignId']


def run(source_repository,bound,ordinal,manifest_raw,schema_raw,context_raw,review_raw,report_raw):
    artifact_repository=io.common_ledger_path(source_repository).parent.parent
    with capture.locked_control(control_root(artifact_repository,bound)):
        instance=matrix.MatrixLedger(matrix.shared_storage(source_repository,bound),artifact_repository,bound)
        with instance.locked():
            instance.initialize();instance.latest_pending(ordinal)
            require(not matrix.present(instance.path('independent',ordinal)),'matrix independent already reserved')
        try:
            artifact_repository,instance,prepared=load_primary(source_repository,bound,ordinal,
                manifest_raw,schema_raw,context_raw,review_raw,report_raw)
            before=resources(prepared);capture.auth_metadata()
        except BaseException as exc:
            instance.stop(ordinal,'independent-prelaunch-or-primary-original-rejected',type(exc).__name__)
            raise
        reservation=instance.reserve_independent(ordinal,prepared.bindings['reviewInputSha256'])
        return execute_reserved(prepared,instance,reservation,before)


def execute_reserved(prepared,instance,reservation,before):
    context=prepared.context;ordinal=context.ordinal;bound=context.bound
    base=layout(prepared.artifact_repository,bound,ordinal)
    process=None;created=False;calls=0;timed_out=False;exit_code=None;error=None;interruption=None
    stdout=stderr=b'';guards=dict(before=before,invoke=None,after=None);result=None;started=time.monotonic()
    try:
        io.safe_tree(base);base.parent.mkdir(mode=0o700,parents=True,exist_ok=True);base.mkdir(mode=0o700);created=True
        for name in OPAQUE:(base/name).mkdir(mode=0o700)
        for name,raw in input_originals(prepared,base,reservation).items():io.exclusive(base/name,raw)
        guards['invoke']=resources(prepared);require(guards['invoke']==before,'matrix score pre-invocation resource drift')
        inv=invocation(prepared,base)
        process=subprocess.Popen(inv['argv'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=inv['environment'],start_new_session=True);calls=1
        try:stdout,stderr=process.communicate(semantic.prompt(prepared),timeout=inv['timeoutSeconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGTERM)
            try:stdout,stderr=process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=3)
        exit_code=process.returncode
        for name,raw in [('trace.jsonl',stdout),('stderr.bin',stderr)]:io.exclusive(base/name,raw)
        guards['after']=resources(prepared);io.exclusive(base/'resource-guards.json',io.encoded(guards))
        require(calls==1 and exit_code==0 and not timed_out and guards['after']==before,
            'matrix score terminal or resource drift')
        names=artifact_names(base);originals={name:io.read_regular(base/name) for name in names}
        result=semantic.response(prepared,originals['trace.jsonl'],originals['response.json'])
        hashes={name:io.sha(raw) for name,raw in originals.items()}
        receipt=make_receipt(prepared,calls,exit_code,timed_out,time.monotonic()-started,None,hashes,True)
        io.exclusive(base/'independent-receipt.json',io.encoded(receipt))
        return dict(status=receipt['status'],independentInvocations=calls,verification=result,
            ledgerFinalized=False,eligibleForMeasurement=False,certifiesSkillGate=False)
    except BaseException as exc:
        error=type(exc).__name__
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):interruption=exc
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=3)
            except (OSError,subprocess.TimeoutExpired):pass
        instance.stop(ordinal,'independent-capture-failed',error)
        if created:
            for name,raw in [('trace.jsonl',stdout),('stderr.bin',stderr),('resource-guards.json',io.encoded(guards))]:
                if not matrix.present(base/name):io.exclusive(base/name,raw)
            hashes={}
            for name in sorted(ARTIFACTS):
                try:hashes[name]=io.sha(io.read_regular(base/name))
                except (OSError,ValueError):pass
            if not matrix.present(base/'independent-receipt.json'):
                io.exclusive(base/'independent-receipt.json',io.encoded(make_receipt(prepared,calls,exit_code,
                    timed_out,time.monotonic()-started,error,hashes,False)))
            io.exclusive(base/'stop.json',io.encoded(dict(status='stopped',errorType=error,automaticRetries=0)))
        if interruption:raise interruption
        return dict(status='matrix_independent_capture_stopped',errorType=error,independentInvocations=calls,
            ledgerFinalized=False,eligibleForMeasurement=False,certifiesSkillGate=False)


def make_receipt(prepared,calls,exit_code,timed_out,seconds,error,hashes,ok):
    return dict(version=VERSION,status='matrix_independent_captured' if ok else 'matrix_independent_capture_stopped',
        slot=prepared.context.bound.slot(prepared.context.ordinal),model='gpt-6.1-sol',scope=SCOPE,
        consumedReservations=1,independentInvocations=calls,primaryModelTrajectories=0,automaticRetries=0,
        exitCode=exit_code,timedOut=timed_out,elapsedSeconds=seconds,errorType=error,artifactSha256=hashes,
        eligibleForMeasurement=False,certifiesBehavior=False,certifiesSkillGate=False)


def verify_originals(prepared,instance):
    base=layout(prepared.artifact_repository,prepared.context.bound,prepared.context.ordinal)
    receipt_raw=io.read_regular(base/'independent-receipt.json');receipt=trace.strict_json(receipt_raw)
    require(isinstance(receipt,dict) and set(receipt)==RECEIPT_KEYS,'matrix independent receipt inventory')
    expected=make_receipt(prepared,1,0,False,receipt['elapsedSeconds'],None,receipt['artifactSha256'],True)
    require(trace.json_equal(receipt,expected),'matrix independent receipt scope or terminal drift')
    seconds=receipt['elapsedSeconds'];require(type(seconds) in {int,float} and math.isfinite(seconds) and seconds>=0,
        'matrix independent elapsed finite')
    hashes=receipt['artifactSha256'];require(isinstance(hashes,dict) and set(hashes)==ARTIFACTS,'matrix score declared inventory')
    for digest in hashes.values():io.pin(digest)
    names=artifact_names(base);originals={name:io.read_regular(base/name) for name in names}
    require({name:io.sha(raw) for name,raw in originals.items()}==hashes,'matrix independent original hash drift')
    ordinal=prepared.context.ordinal;reservation=instance.read('independent',ordinal)
    instance.independent_valid(reservation,ordinal)
    require(reservation['reviewInputSha256']==prepared.bindings['reviewInputSha256'],'matrix independent reservation input drift')
    require(all(originals[name]==raw for name,raw in input_originals(prepared,base,reservation).items()),
        'matrix independent original input/argv/config drift')
    current=resources(prepared);require(originals['resource-guards.json']==io.encoded(dict.fromkeys(['before','invoke','after'],current)),
        'matrix independent current resources drift')
    result=semantic.response(prepared,originals['trace.jsonl'],originals['response.json'])
    return receipt_raw,result


def finalize(source_repository,bound,ordinal,manifest_raw,schema_raw,context_raw,review_raw,report_raw):
    """親が取得原・採点原・現物・全argv・共有予約を再構成してから次枠を許可する。"""
    artifact_repository=io.common_ledger_path(source_repository).parent.parent
    with capture.locked_control(control_root(artifact_repository,bound)):
        instance=matrix.MatrixLedger(matrix.shared_storage(source_repository,bound),artifact_repository,bound)
        with instance.locked():instance.initialize();instance.latest_pending(ordinal)
        prepared=None
        try:
            artifact_repository,instance,prepared=load_primary(source_repository,bound,ordinal,
                manifest_raw,schema_raw,context_raw,review_raw,report_raw)
            receipt_raw,result=verify_originals(prepared,instance)
            base=layout(artifact_repository,bound,ordinal)
            accepted=result['proposedLedgerStatus'] in {'measured_correct','measured_incorrect'}
            parent=dict(version=VERSION,status='matrix_parent_originals_verified' if accepted else 'matrix_parent_stopped',
                slot=bound.slot(ordinal),primaryReceiptSha256=io.sha(prepared.context.receipt_raw),
                independentReceiptSha256=io.sha(receipt_raw),reviewInputSha256=prepared.bindings['reviewInputSha256'],
                verification=result,independentContext=True,ledgerFinalized=False,
                eligibleForMeasurement=accepted,certifiesSkillGate=False,certifiesRelease=False)
            parent_raw=io.encoded(parent);io.exclusive(base/'parent-verification.json',parent_raw)
            if not accepted:
                instance.stop(ordinal,'independent-safety-or-integrity-unresolved','Unresolved')
                return parent
            def reference(name,raw):return dict(relativePath=str((base/name).relative_to(artifact_repository)),sha256=io.sha(raw))
            score=result['originalResponse']
            value=dict(bound.slot(ordinal),status=result['proposedLedgerStatus'],accuracy=score['accuracy'],
                safetyPassed=True,integrityPassed=True,independentContext=True,severityCounts=result['blockingSafetyCounts'],
                primaryRecordSha256=io.sha(io.read_regular(instance.path('primary',ordinal))),
                independentReservationSha256=io.sha(io.read_regular(instance.path('independent',ordinal))),
                independentReceipt=reference('independent-receipt.json',receipt_raw),
                parentVerification=reference('parent-verification.json',parent_raw),certifiesSkillGate=False)
            instance.record_review(ordinal,io.encoded(value))
            return dict(parent,ledgerFinalized=True)
        except BaseException as exc:
            # load前の改変も、共有予約のあるcampaignを停止。元原は置換しない。
            instance.stop(ordinal,'parent-original-verification-failed',type(exc).__name__)
            if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
            return dict(status='matrix_parent_stopped',errorType=type(exc).__name__,ledgerFinalized=False,
                eligibleForMeasurement=False,certifiesSkillGate=False)
