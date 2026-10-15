"""公開surveyの単枠operator。個別失敗は閉じ、基盤異常は全体停止する。"""
from pathlib import Path
import argparse
import datetime
import math
import time

import production_matrix_capture as capture
import production_matrix_score as score
import production_matrix_survey as survey

p=capture.p
io=p.io
require=p.require
JST=datetime.timezone(datetime.timedelta(hours=9))
PACE_KEYS={'version','sourceCommit','campaignId','conditionSha256','role','ordinal','minimumGapSeconds',
    'monotonicSeconds','waitedSeconds','startedAt','declaresProviderInvoked'}


def stage_summary(value):
    if value is None:return None
    keys={'status','actualNamespaceInvocations','independentInvocations','errorType','timedOut','ledgerFinalized'}
    result={k:value[k] for k in keys if k in value}
    if 'verification' in value and isinstance(value['verification'],dict):
        result['proposedLedgerStatus']=value['verification'].get('proposedLedgerStatus')
    return result


def pace(root,bound,policy,condition,ordinal,role,result,prior_state=None):
    """前枠の正常・失敗終端を確認したoperatorが呼ぶ。SDK内HTTP間隔ではない。"""
    require(role in {'primary','independent'},'survey pacing role')
    prior_path=None;prior_sha=None;previous=None;delay=0.0
    if role=='independent':
        previous=root/f'launch-primary-{ordinal:04d}.json';expected_sha=io.pin(result['launchEvidence']['primary'])
        expected_role='primary';expected_ordinal=ordinal
    elif ordinal>policy['startOrdinal']:
        prior_path=root/f'actual-slot-{ordinal-1:04d}.json';raw=io.read_regular(prior_path);prior_sha=io.sha(raw)
        prior=p.trace.strict_json(raw)
        require(prior['sourceCommit']==bound.contract['sourceCommit'] and prior['campaignId']==bound.contract['campaignId']
            and prior['conditionSha256']==condition and type(prior['ordinal']) is int and prior['ordinal']==ordinal-1
            and isinstance(prior_state,dict) and prior['status']==prior_state['status']
            and prior['failurePhase']==prior_state['phase'] and prior['globalErrorType'] is None
            and set(prior['launchEvidence'])==({'primary','independent'} if prior_state['hasIndependent'] else {'primary'}),'survey previous terminal operator record')
        expected_role='independent' if 'independent' in prior['launchEvidence'] else 'primary'
        expected_ordinal=ordinal-1;expected_sha=io.pin(prior['launchEvidence'][expected_role])
        previous=root/f'launch-{expected_role}-{expected_ordinal:04d}.json'
    elif ordinal==policy['startOrdinal'] and policy['priorSlots']:
        raw=io.read_regular(Path(policy['baselineReportAbsolutePath']));require(io.sha(raw)==policy['baselineReport']['sha256'],'survey baseline publication hash drift')
        baseline=p.trace.strict_json(raw)
        observed=datetime.datetime.fromisoformat(baseline['recordedAt'])
        require(observed.utcoffset()==datetime.timedelta(hours=9)
            and (datetime.datetime.now(JST)-observed).total_seconds()>=60,'survey baseline publication gap')
    if previous is not None:
        raw=io.read_regular(previous);require(io.sha(raw)==expected_sha,'survey previous pacing hash drift')
        value=p.trace.strict_json(raw)
        require(isinstance(value,dict) and set(value)==PACE_KEYS,'survey pacing inventory')
        require(value['version']=='operator-logical-launch-pacing-0.1.0'
            and value['sourceCommit']==bound.contract['sourceCommit'] and value['campaignId']==bound.contract['campaignId']
            and value['conditionSha256']==condition and value['role']==expected_role
            and type(value['ordinal']) is int and value['ordinal']==expected_ordinal
            and type(value['minimumGapSeconds']) is int and value['minimumGapSeconds']==60
            and value['declaresProviderInvoked'] is False,'survey pacing identity')
        require(type(value['monotonicSeconds']) in {int,float} and math.isfinite(value['monotonicSeconds'])
            and value['monotonicSeconds']>=0 and type(value['waitedSeconds']) in {int,float}
            and math.isfinite(value['waitedSeconds']) and 0<=value['waitedSeconds']<=60,
            'survey finite pacing values')
        require(isinstance(value['startedAt'],str) and datetime.datetime.fromisoformat(value['startedAt']).utcoffset()
            ==datetime.timedelta(hours=9),'survey pacing timestamp')
        elapsed=time.monotonic()-value['monotonicSeconds'];require(math.isfinite(elapsed) and elapsed>=0,'survey monotonic drift')
        delay=max(0.0,60.0-elapsed)
        if delay:time.sleep(delay)
    moment=time.monotonic();require(type(moment) in {int,float} and math.isfinite(moment) and moment>=0,'survey current clock')
    if previous is not None:
        require(moment-value['monotonicSeconds']>=60 and io.sha(io.read_regular(previous))==expected_sha,
            'survey pacing minimum gap and stable original')
    if prior_path is not None:require(io.sha(io.read_regular(prior_path))==prior_sha,'survey previous result drift')
    value=dict(version='operator-logical-launch-pacing-0.1.0',sourceCommit=bound.contract['sourceCommit'],
        campaignId=bound.contract['campaignId'],conditionSha256=condition,role=role,ordinal=ordinal,
        minimumGapSeconds=60,monotonicSeconds=moment,waitedSeconds=delay,
        startedAt=datetime.datetime.now(JST).isoformat(),declaresProviderInvoked=False)
    raw=io.encoded(value);io.exclusive(root/f'launch-{role}-{ordinal:04d}.json',raw)
    result['launchEvidence'][role]=io.sha(raw)


def seal_failure(repository,instance,root,bound,ordinal,phase,proof,result):
    d_raw=io.read_regular(root/'deployment.json');sdk_raw=io.read_regular(root/'sdk-manifest.json')
    require(p.verify_resources(repository,bound,d_raw,sdk_raw)==proof,'survey current resources drift')
    artifact=instance.repository
    base=artifact/(bound.contract['outputRelativeRoot']+('' if phase=='primary' else '-independent'))/f'attempt-{ordinal:04d}'
    guards=p.trace.strict_json(io.read_regular(base/'resource-guards.json'))
    require(p.trace.json_equal(guards,dict.fromkeys(['before','invoke','after'],proof)),
        'survey failed stage resource guards must all match')
    control=artifact/'.venv/production-matrix-launch-controls'/bound.contract['campaignId']
    def ref(path):return dict(relativePath=path.relative_to(artifact).as_posix(),sha256=io.sha(io.read_regular(path)))
    receipt=base/('receipt.json' if phase=='primary' else 'independent-receipt.json')
    observation=dict(version=survey.VERSION,slot=bound.slot(ordinal),phase=phase,
        resourceProof=ref(control/'survey-resource-proof.json'),stageReceipt=ref(receipt),
        **{key:result[key] for key in ['primary','independent','parent']})
    path=control/f'failure-observation-{ordinal:04d}.json';io.exclusive(path,io.encoded(observation))
    instance.record_failure(ordinal,phase,ref(path))
    result.update(status='evaluation_failed',failurePhase=phase,eligibleForMeasurement=False)


def run(repository,root,ordinal):
    require(root.is_relative_to(repository/'.venv') and '..' not in root.parts,'survey bound bundle boundary')
    inputs={name:io.read_regular(root/(name+'.input.json')) for name in p.matrix.inputs.INPUT_NAMES}
    bound=p.matrix.bind(io.read_regular(root/'execution.json'),io.read_regular(root/'input-contract.json'),**inputs)
    require(bound.contract['version']==p.matrix.SURVEY_VERSION,'explicit survey execution required')
    d_raw=io.read_regular(root/'deployment.json');sdk_raw=io.read_regular(root/'sdk-manifest.json')
    review_raw=io.read_regular(root/'prelaunch-review.json');code_raw=io.read_regular(root/'code-review.json')
    concrete=p.trace.strict_json(io.read_regular(root/'operational-review.json'))
    condition=capture.condition_sha256(bound,d_raw)
    require(concrete.get('sourceCommit')==bound.contract['sourceCommit'] and concrete.get('conditionSha256')==condition
        and concrete.get('independentContext') is True and concrete.get('findings')==concrete.get('blockingFindings')==[]
        and concrete.get('status')=='matrix_concrete_prelaunch_verified','survey concrete review required')
    own=io.read_regular(Path(__file__))
    require(io.sha(own)==concrete['operatorHelperSha256']['driver']
        and own==p.guard.git(repository,'show',bound.contract['sourceCommit']+':evals/skills/routing/production_matrix_survey_run.py'),
        'survey reviewed fixed operator source required')
    capture.prelaunch_review(bound,d_raw,review_raw,code_raw)
    artifact=io.common_ledger_path(repository).parent.parent
    instance=p.matrix.open_ledger(p.matrix.shared_storage(repository,bound),artifact,bound)
    require(isinstance(instance,survey.SurveyLedger) and ordinal>=instance.first,'survey ordinal boundary')
    policy=dict(instance.policy)
    if policy['baselineReport'] is not None:
        policy['baselineReportAbsolutePath']=str(artifact/policy['baselineReport']['relativePath'])
    manifest_raw=io.read_regular(repository/p.deployment(bound,d_raw)['snapshotRelativePath']/'manifest.json')
    manifest=p.trace.strict_json(manifest_raw)
    require(manifest['resources']==instance.policy['productResources'],'survey product resources changed')
    schema=p.decision_schema(p.guard.git(repository,'show',bound.contract['sourceCommit']+':'+p.inventory.SCHEMA))
    context=p.guard.git(repository,'show',bound.contract['sourceCommit']+':'+p.inventory.CONTEXT)
    record=root/f'actual-slot-{ordinal:04d}.json';require(not p.matrix.present(record),'survey operator observation already exists')
    result=dict(sourceCommit=bound.contract['sourceCommit'],campaignId=bound.contract['campaignId'],conditionSha256=condition,
        ordinal=ordinal,caseId=bound.slot(ordinal)['caseId'],repetition=bound.slot(ordinal)['repetition'],
        status='pending',launchEvidence={},primary=None,independent=None,parent=None,failurePhase=None,
        globalErrorType=None,eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False)
    interruption=None
    try:
        proof=p.verify_resources(repository,bound,d_raw,sdk_raw)
        control=artifact/'.venv/production-matrix-launch-controls'/bound.contract['campaignId']
        with capture.locked_control(control):
            path=control/'survey-resource-proof.json';raw=io.encoded(proof)
            if p.matrix.present(path):require(io.read_regular(path)==raw,'survey pinned resource proof drift')
            else:io.exclusive(path,raw)
        with instance.locked():
            instance.initialize();last=instance.checked_count()
            require(ordinal==last+1 and (last<instance.first or instance.terminal(last)), 'survey previous result pending')
            prior_state=None
            if last>=instance.first:
                normal=p.matrix.present(instance.path('review',last))
                value=instance.read('review' if normal else 'failure',last)
                prior_state=dict(status=value['status'],phase=None if normal else value['phase'],
                    hasIndependent=p.matrix.present(instance.path('independent',last)))
        pace(root,bound,policy,condition,ordinal,'primary',result,prior_state)
        primary=capture.run(repository,bound,d_raw,sdk_raw,review_raw,code_raw,ordinal)
        result['primary']=stage_summary(primary)
        if primary['status']!='primary_capture_awaits_independent_review':
            seal_failure(repository,instance,root,bound,ordinal,'primary',proof,result)
        else:
            pace(root,bound,policy,condition,ordinal,'independent',result)
            independent=score.run(repository,bound,ordinal,manifest_raw,schema,context,review_raw,code_raw)
            result['independent']=stage_summary(independent)
            if independent['status']!='matrix_independent_captured':
                seal_failure(repository,instance,root,bound,ordinal,'independent',proof,result)
            else:
                parent=score.finalize(repository,bound,ordinal,manifest_raw,schema,context,review_raw,code_raw)
                result['parent']=stage_summary(parent)
                if parent.get('ledgerFinalized') is not True:
                    seal_failure(repository,instance,root,bound,ordinal,'parent',proof,result)
                else:
                    result.update(status=parent['verification']['proposedLedgerStatus'],eligibleForMeasurement=True)
    except BaseException as exc:
        result.update(status='globally_stopped',globalErrorType=type(exc).__name__)
        instance.abort(ordinal,'survey-execution-environment-or-evidence-rejected',type(exc).__name__)
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):interruption=exc
    io.exclusive(record,io.encoded(result))
    if interruption:raise interruption
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--ordinal',type=int,required=True)
    args=parser.parse_args();result=run(Path.cwd(),args.bundle.absolute(),args.ordinal)
    print(io.encoded(result).decode());raise SystemExit(1 if result['globalErrorType'] else 0)
