"""保持独立の単回隔離採点と親の原照合。私的原は同一collectionの有限stageにだけ保存。"""
import math
import os
from pathlib import Path
import stat
import subprocess
import time

import production_heldout_operator as operator
import production_heldout_semantic as semantic

x, io, require, trace = operator.x, operator.io, operator.require, operator.trace
launch, preflight = operator.launch, operator.preflight
VERSION = 'heldout-independent-operator-0.1.0'
SCOPE = 'heldout12-times2-independent-and-parent-only'
ARTIFACTS = frozenset({'contract.json','review-input.json','bindings.json','prompt.txt','schema.json',
    'execution-schema.json','reservation.json','config.json','invocation.json','resource-guards.json',
    'trace.jsonl','stderr.bin','response.json','logical-pacing.json',launch.model_catalog.FILE})
SAVED = ARTIFACTS | {'independent-receipt.json','parent-verification.json','stop.json'}
OPAQUE = frozenset({'work','tmp','codex-home','logs','state'})
RECEIPT_KEYS = {'version','status','slot','model','scope','consumedReservations','independentLaunchMarked',
    'namespaceInvocations','declaresProviderInvoked','primaryModelTrajectories','automaticRetries','exitCode','timedOut',
    'elapsedSeconds','errorType','artifactSha256','eligibleForMeasurement','certifiesBehavior','certifiesSkillGate'}


def config_for(base):
    return launch.model_catalog.configuration(base, semantic.legacy_terminal.config_for(base))


def namespace_command(bound,ordinal):
    return namespace_for_execution(bound.execution_raw,bound.deployment_raw,ordinal)


def namespace_for_execution(execution_raw,deployment_raw,ordinal):
    d=x.deployment_for_execution(execution_raw,deployment_raw)
    base=launch.stage_root(execution_raw,ordinal,'independent')
    argv=[d['codexPath'],'exec','--json','--ephemeral','--ignore-user-config','--ignore-rules',
        '--skip-git-repo-check','--sandbox','read-only','--cd',str(base/'work'),'--model','gpt-6.1-sol',
        '--output-schema',str(base/'execution-schema.json'),'--output-last-message',str(base/'response.json')]
    for key,value in config_for(base).items():argv+=['-c',key+'='+preflight.public.capture.sdk.toml_value(value)]
    argv+=['-']
    return ['bwrap','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent','--ro-bind','/','/',
        '--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run','--proc','/proc','--dev','/dev',
        '--ro-bind',str(Path(d['codexPath']).parents[1]),str(Path(d['codexPath']).parents[1]),
        '--bind',str(base),str(base),'--bind',str(base/'codex-home'),'/home/hide/.codex',
        '--ro-bind',str(launch.AUTH),'/home/hide/.codex/auth.json','--chdir',str(base/'work'),'--',*argv]


def invocation(prepared):
    semantic.rebound(prepared)
    bound=prepared.context.bound;ordinal=prepared.context.ordinal
    d=x.deployment_for_execution(bound.execution_raw,bound.deployment_raw);base=bound.stage_root(ordinal,'independent')
    env=dict(PATH=str(Path(d['codexPath']).parents[1]/'bin')+':/usr/bin:/bin',LANG='C.UTF-8',
        HOME='/home/hide',CODEX_HOME='/home/hide/.codex',TMPDIR=str(base/'tmp'),TZ='Asia/Tokyo',PYTHONDONTWRITEBYTECODE='1')
    return dict(version=VERSION,slot=bound.slot(ordinal),model='gpt-6.1-sol',scope=SCOPE,
        argv=namespace_command(bound,ordinal),environment=env,promptSha256=io.sha(semantic.prompt(prepared)),
        reviewInputSha256=io.sha(prepared.input_raw),schemaSha256=io.sha(prepared.schema_raw),
        maximumLogicalTurns=1,automaticRetries=0,processUmask=0o077,
        timeoutSeconds=bound.contract['timeoutSeconds']['independent'])


def input_originals(prepared):
    inv=invocation(prepared);bound=prepared.context.bound;ordinal=prepared.context.ordinal
    return {launch.model_catalog.FILE:launch.model_catalog.fixed_catalog(),
        'contract.json':prepared.contract_raw,'review-input.json':prepared.input_raw,
        'bindings.json':prepared.binding_raw,'prompt.txt':semantic.prompt(prepared),'schema.json':prepared.schema_raw,
        'execution-schema.json':io.encoded(preflight.public.capture.execution_schema(trace.strict_json(prepared.schema_raw))),
        'reservation.json':io.encoded(dict(slot=bound.slot(ordinal),reviewInputSha256=io.sha(prepared.input_raw))),
        'config.json':io.encoded(config_for(bound.stage_root(ordinal,'independent'))),'invocation.json':io.encoded(inv)}


def save(base,name,raw):
    require(name in SAVED, 'heldout fixed score write')
    operator.save(base,name,raw,additional_artifacts=SAVED)


def read(base,name):
    require(name in SAVED, 'heldout fixed score read')
    return operator.originals.read_original(base,name,additional_artifacts=SAVED)


def collect(base,*,complete):
    fd=operator.originals._open_root(base)
    try:
        names=set(os.listdir(fd));require(names <= SAVED | OPAQUE and 'stop.json' not in names,
            'heldout unknown or stopped score original')
        for name in names & OPAQUE:
            value=os.stat(name,dir_fd=fd,follow_symlinks=False)
            require(stat.S_ISDIR(value.st_mode) and stat.S_IMODE(value.st_mode)==0o700 and value.st_uid==os.getuid(),
                'heldout score opaque metadata')
        actual=names & ARTIFACTS
        require(not complete or actual == ARTIFACTS, 'heldout complete score originals required')
    finally:os.close(fd)
    values,total={},0
    for name in sorted(actual):
        raw=read(base,name);total+=len(raw)
        require(total <= operator.originals.MAX_TOTAL_BYTES, 'heldout score finite bytes')
        values[name]=raw
    return values


def audit_partial(raw):
    lines=raw.splitlines()
    for index,line in enumerate(lines):
        try:value=x.inputs.parse(line)
        except ValueError:
            require(index==len(lines)-1 and not raw.endswith(b'\n'), 'heldout score malformed complete JSONL')
            continue
        require(isinstance(value,dict) and value.get('type') in
            {'thread.started','turn.started','turn.completed','turn.failed','error','item.completed'},
            'heldout score unknown partial event')
        if value['type']=='item.completed':
            item=value.get('item')
            require(isinstance(item,dict) and item.get('type') in {'reasoning','agent_message','error'},
                'heldout score forbidden partial action')


def audit_originals(values):
    audit_partial(values.get('trace.jsonl',b''))
    stderr=values.get('stderr.bin',b'')
    # 独立採点には一次のexec/wait/Host許可を引き継がない。原stderrも全ツール禁止。
    for line in stderr.splitlines():
        try:value=x.inputs.parse(line)
        except ValueError:continue
        if not isinstance(value,dict):continue
        fields=value.get('fields',{})
        require(isinstance(fields,dict),'heldout score telemetry fields')
        require(fields.get('event.name')!='codex.tool_call_received','heldout score no-tools control policy')
    # 共通のAPI回数・再試行禁止も、保存名や原bytesを変えず適用する。
    operator.audit_partial({'namespace.stderr':stderr})


def run_process(plan,prompt):
    process=None
    try:
        process=subprocess.Popen(plan['argv'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=plan['environment'],start_new_session=True,umask=0o077)
        timed_out=False
        try:stdout,stderr=process.communicate(prompt,timeout=plan['timeoutSeconds'])
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(process.pid,operator.signal.SIGTERM)
            try:stdout,stderr=process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,operator.signal.SIGKILL);stdout,stderr=process.communicate(timeout=3)
        return process.returncode,timed_out,stdout,stderr
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,operator.signal.SIGKILL);process.communicate(timeout=3)


def receipt(prepared,values,elapsed,exit_code,timed_out,status,error):
    return dict(version=VERSION,status=status,slot=prepared.context.bound.slot(prepared.context.ordinal),
        model='gpt-6.1-sol',scope=SCOPE,consumedReservations=1,independentLaunchMarked=1,namespaceInvocations=1,
        declaresProviderInvoked=False,primaryModelTrajectories=0,automaticRetries=0,exitCode=exit_code,timedOut=timed_out,
        elapsedSeconds=elapsed,errorType=error,artifactSha256={name:io.sha(raw) for name,raw in values.items()},
        eligibleForMeasurement=False,certifiesBehavior=False,certifiesSkillGate=False)


def primary(prepared_repository,bound,ordinal,ledger):
    rows,_=ledger._history()
    require(rows and rows[-1]['ordinal']==ordinal and rows[-1]['stage']=='primary_captured',
        'heldout independent requires pending primary')
    context=operator.originals.load(bound,ordinal,source_repository=prepared_repository)
    require(io.sha(context.receipt_raw)==rows[-1]['artifactSha256'], 'heldout primary journal receipt drift')
    operator.verify_pacing(bound,ordinal,'primary',expected_sha256=
        x.inputs.parse(context.receipt_raw)['artifactSha256']['logical-pacing.json'])
    return semantic.prepare(context)


def stop(ledger,bound,ordinal,error,reason='evidence_invalid'):
    raw=io.encoded(dict(version=VERSION,status='globally_stopped',ordinal=ordinal,errorType=type(error).__name__))
    try:
        operator.create_directory(operator.control_root(bound,ordinal))
        operator.save(operator.control_root(bound,ordinal),'global-stop.json',raw)
    except (OSError,ValueError):pass
    ledger.append(None,'global_stop',io.sha(raw),stop_reason=reason)


def run_independent(repository,bound,ordinal,sdk_raw,review_raw,report_raw,isolation_raw):
    x.rebound(bound);bound.slot(ordinal)
    launch.prelaunch_review(bound.execution_raw,bound.deployment_raw,review_raw,report_raw,isolation_raw)
    before=preflight.verify_resources(repository,bound,sdk_raw)
    operator.auth_metadata()
    ledger=x.ledger.open_shared(bound.ledger_contract(io.encoded(before)))
    with ledger.locked():
        # 予約済の独立枠へ再入場しない。原一次を再構成してから予約を消費する。
        rows,_=ledger._history()
        require(rows and rows[-1]['ordinal']==ordinal and rows[-1]['stage']=='primary_captured',
            'heldout independent requires pending primary')
        try:
            prepared=primary(repository,bound,ordinal,ledger)
            ledger.append(ordinal,'independent_reserved')
            return _reserved(prepared,sdk_raw,before,ledger)
        except BaseException as exc:
            stop(ledger,bound,ordinal,exc,'operator_interrupted' if not isinstance(exc,Exception) else 'evidence_invalid')
            raise


def _reserved(prepared,sdk_raw,before,ledger):
    bound=prepared.context.bound;ordinal=prepared.context.ordinal;repository=prepared.context.source_repository
    base=bound.stage_root(ordinal,'independent');operator.create_directory(base.parent)
    fd=operator.originals._open_root(base.parent)
    try:os.mkdir(base.name,mode=0o700,dir_fd=fd);os.fsync(fd)
    finally:os.close(fd)
    for name in OPAQUE:operator.create_directory(base/name)
    for name,raw in input_originals(prepared).items():save(base,name,raw)
    plan=invocation(prepared);prompt_raw=semantic.prompt(prepared)
    operator.pace(bound,ordinal,'independent',ledger)
    pacing_sha=io.sha(operator.verify_pacing(bound,ordinal,'independent'))
    invoke=preflight.verify_resources(repository,bound,sdk_raw)
    require(trace.json_equal(invoke,before),'heldout independent pre-invocation resource drift')
    launch.model_catalog.verify(read(base,launch.model_catalog.FILE))
    ledger.append(ordinal,'independent_started');begin=time.monotonic()
    exit_code,timed_out,stdout,stderr=run_process(plan,prompt_raw)
    elapsed=time.monotonic()-begin
    save(base,'trace.jsonl',stdout);save(base,'stderr.bin',stderr)
    after=preflight.verify_resources(repository,bound,sdk_raw)
    save(base,'resource-guards.json',io.encoded(dict(before=before,invoke=invoke,after=after)))
    require(trace.json_equal(after,before),'heldout independent after resource drift')
    operator.verify_pacing(bound,ordinal,'independent',expected_sha256=pacing_sha)
    values=collect(base,complete=exit_code==0 and not timed_out)
    audit_originals(values)
    result=None
    if exit_code==0 and not timed_out:
        result=semantic.response(prepared,values['trace.jsonl'],values['response.json'])
        require(result['originalResponse']['safety']!='fail','heldout unsafe independent result')
    resolved=result is not None and result['proposedLedgerStatus'] in {'measured_correct','measured_incorrect'}
    status='heldout_independent_captured' if resolved else 'evaluation_failed'
    raw=io.encoded(receipt(prepared,values,elapsed,exit_code,timed_out,status,None if resolved else 'EvaluationIncomplete'))
    save(base,'independent-receipt.json',raw)
    ledger.append(ordinal,'independent_captured' if resolved else 'independent_failed',io.sha(raw),
        resource_proof_sha256=None if resolved else io.sha(io.encoded(before)))
    return dict(version=VERSION,status=status,ordinal=ordinal,independentLaunchMarked=1,namespaceInvocations=1,
        declaresProviderInvoked=False,reservations=1,automaticRetries=0,ledgerFinalized=False,
        eligibleForMeasurement=False,certifiesSkillGate=False)


def verify_originals(prepared,current):
    semantic.rebound(prepared)
    bound=prepared.context.bound;ordinal=prepared.context.ordinal;base=bound.stage_root(ordinal,'independent')
    raw=read(base,'independent-receipt.json');saved=x.inputs.parse(raw)
    require(isinstance(saved,dict) and set(saved)==RECEIPT_KEYS,'heldout independent receipt shape')
    seconds=saved['elapsedSeconds']
    require(type(seconds) in {int,float} and math.isfinite(seconds) and seconds>=0,'heldout independent finite time')
    values=collect(base,complete=True)
    expected=receipt(prepared,values,seconds,0,False,'heldout_independent_captured',None)
    require(trace.json_equal(saved,expected),'heldout independent original receipt mismatch')
    require(all(values[name]==value for name,value in input_originals(prepared).items()),
        'heldout independent fixed original input or argv mismatch')
    require(values['resource-guards.json']==io.encoded(dict.fromkeys(['before','invoke','after'],current)),
        'heldout independent original resource mismatch')
    audit_originals(values)
    operator.verify_pacing(bound,ordinal,'independent',expected_sha256=saved['artifactSha256']['logical-pacing.json'])
    result=semantic.response(prepared,values['trace.jsonl'],values['response.json'])
    return raw,result


def finalize(repository,bound,ordinal,sdk_raw,review_raw,report_raw,isolation_raw):
    x.rebound(bound);bound.slot(ordinal)
    launch.prelaunch_review(bound.execution_raw,bound.deployment_raw,review_raw,report_raw,isolation_raw)
    current=preflight.verify_resources(repository,bound,sdk_raw)
    ledger=x.ledger.open_shared(bound.ledger_contract(io.encoded(current)))
    with ledger.locked():
        rows,_=ledger._history()
        require(rows and rows[-1]['ordinal']==ordinal and rows[-1]['stage']=='independent_captured',
            'heldout parent requires pending independent')
        try:
            context=operator.originals.load(bound,ordinal,source_repository=repository)
            anchors=[row for row in rows if row['ordinal']==ordinal and row['stage']=='primary_captured']
            require(len(anchors)==1 and io.sha(context.receipt_raw)==anchors[0]['artifactSha256'],
                'heldout parent primary receipt journal mismatch')
            operator.verify_pacing(bound,ordinal,'primary',expected_sha256=
                x.inputs.parse(context.receipt_raw)['artifactSha256']['logical-pacing.json'])
            prepared=semantic.prepare(context);raw,result=verify_originals(prepared,current)
            require(io.sha(raw)==rows[-1]['artifactSha256'],'heldout parent independent receipt journal mismatch')
            status=result['proposedLedgerStatus']
            require(status in {'measured_correct','measured_incorrect'},'heldout unresolved parent cannot finalize')
            proof=io.encoded(dict(version=VERSION,status=status,ordinal=ordinal,
                primaryReceiptSha256=io.sha(context.receipt_raw),independentReceiptSha256=io.sha(raw),
                reviewInputSha256=io.sha(prepared.input_raw),verification=result,eligibleForMeasurement=True,
                certifiesSkillGate=False))
            save(bound.stage_root(ordinal,'independent'),'parent-verification.json',proof)
            ledger.append(ordinal,'parent_verified',io.sha(proof),measured_correct=status=='measured_correct')
            return dict(version=VERSION,status=status,ordinal=ordinal,ledgerFinalized=True,
                eligibleForMeasurement=True,independentOriginalResponseVerified=True,certifiesSkillGate=False)
        except BaseException as exc:
            stop(ledger,bound,ordinal,exc)
            raise
