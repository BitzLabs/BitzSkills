"""保持24枠の有限batch入口。固定公開bundle→private内部束縛→最大2枠、同枠retryなし。"""
import argparse
from contextlib import contextmanager
import fcntl
import os
import stat
from dataclasses import dataclass
from pathlib import Path
import re

import production_failure_streak as streak
import production_heldout_score as score

operator, x, io = score.operator, score.x, score.io
policy = operator.policy
launch, preflight, require = score.launch, score.preflight, score.require
VERSION = 'heldout-finite-batch-0.1.0'
ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True,repr=False)
class Bundle:
    repository:Path
    bound:x.BoundExecution
    sdk_raw:bytes
    review_raw:bytes
    report_raw:bytes
    isolation_raw:bytes


def load(repository,base):
    require(isinstance(repository,Path) and repository.is_absolute() and isinstance(base,Path)
        and base.parent==repository/'.venv' and re.fullmatch(r'heldout-bound-[a-z0-9]+(?:-[a-z0-9]+)*',base.name),
        'heldout public bundle root')
    io.safe_tree(repository);io.safe_tree(base)
    execution_raw=io.read_regular(base/'execution.json');c=x.execution_contract(execution_raw)
    # metadataだけの後続commitは許す。実sourceは固定refの全原bytesへ直接照合する。
    require(preflight.public.guard.git(repository,'status','--porcelain')==b'', 'heldout clean source repository required')
    preflight.public.guard.verify(repository,c['sourceCommit'],list(preflight.SOURCE_FILES))
    deployment_raw=io.read_regular(base/'deployment.json');input_raw=io.read_regular(base/'input-contract.json')
    sdk_raw=io.read_regular(base/'sdk-manifest.json');review_raw=io.read_regular(base/'prelaunch-review.json')
    report_raw=io.read_regular(base/'prelaunch-report.json');isolation_raw=io.read_regular(base/'local-isolation-proof.json')
    launch.prelaunch_review(execution_raw,deployment_raw,review_raw,report_raw,isolation_raw)
    raws={name:preflight.public.guard.git(repository,'show',c['sourceCommit']+':'+path)
        for name,path in x.inputs.PUBLIC_PATHS.items()}
    raws['cases']=x.inputs.private_bytes(x.inputs.PRIVATE_CASES)
    bound=x.bind(execution_raw,deployment_raw,input_raw,**raws)
    return Bundle(repository,bound,sdk_raw,review_raw,report_raw,isolation_raw)


def resources(bundle):
    require(isinstance(bundle,Bundle), 'heldout bundle required')
    launch.prelaunch_review(bundle.bound.execution_raw,bundle.bound.deployment_raw,
        bundle.review_raw,bundle.report_raw,bundle.isolation_raw)
    return preflight.verify_resources(bundle.repository,bundle.bound,bundle.sdk_raw)


def ledger_for(bundle,proof):
    return x.ledger.open_shared(bundle.bound.ledger_contract(io.encoded(proof)))


def checkpoint(bundle,proof):
    ledger=ledger_for(bundle,proof)
    with ledger.locked():
        rows,_=ledger._history();summary=ledger.summary()
    return rows,summary


def next_stage(rows,summary):
    if summary['status']=='stopped':return None,'stopped'
    if summary.get('pendingRetry') is not None:return summary['pendingRetry'],'primary'
    if summary.get('accountedSlots',summary['terminalSlots'])==24:return None,'complete'
    if not rows or rows[-1]['stage'] in x.ledger.TERMINALS:
        ordinal=summary.get('nextOrdinal',summary['primaryReserved']+1)
        return (ordinal,'primary') if ordinal is not None else (None,'awaiting_retry')
    stage=rows[-1]['stage'];ordinal=rows[-1]['ordinal']
    if stage=='primary_captured':return ordinal,'independent'
    if stage=='independent_captured':return ordinal,'parent'
    return ordinal,'ambiguous'


def failure_blocked(bundle,rows,ordinal):
    """ADR-068 D4: 同じ型の評価失敗が続いたら、確認記録なしに次の枠を予約しない。台帳へ書かない。"""
    control=operator.control_root(bundle.bound,ordinal);name='failure-acknowledgement.json'
    raw=operator.read_control(control,name) if (control/name).exists() else None
    try:streak.guard(streak.ledger_terminals(rows),ordinal,raw)
    except ValueError:return True
    return False


def authorize_retry(bundle,ordinal,*,stop_reason,prior_artifact_sha256,evidence_sha256,reason,
                    independent_review_raw=None):
    """ADR-068 D2: 前のcampaignで評価失敗または中断した枠を、承認記録を残して1回だけ再試行可能にする。"""
    proof=resources(bundle);ledger=ledger_for(bundle,proof)
    require(operator.successor_ledger(ledger),'heldout retry requires a successor ledger')
    with batch_lock(bundle),ledger.locked():
        require(ordinal in ledger.summary()['retryEligible'],'heldout retry ordinal not eligible')
        attempt=ledger._state['attempts'][ordinal][-1]
        require(attempt.get('artifactSha256')==prior_artifact_sha256,'heldout retry prior artifact binding')
        role={'primary_failed':'primary','independent_failed':'independent'}.get(attempt['outcome'],'interrupted')
        raw=io.encoded(dict(version=policy.AUTHORIZATION_VERSION,contractSha256=ledger.digest,ordinal=ordinal,
            failedRole=role,stopReason=stop_reason,causeClass=policy.classify(stop_reason),
            priorArtifactSha256=prior_artifact_sha256,evidenceSha256=list(evidence_sha256),
            independentReviewSha256=None if independent_review_raw is None else io.sha(independent_review_raw),
            reason=reason,automaticRetry=False))
        policy.authorization(raw,contract_sha256=ledger.digest,ordinal=ordinal)
        # 保存したEXCLの原が残って同じ枠の承認を塞がないよう、台帳の検査を先に通す。
        ledger.candidate(ordinal,'retry_authorized',io.sha(raw),stop_reason=stop_reason)
        control=operator.control_root(bundle.bound,ordinal);operator.create_directory(control)
        if independent_review_raw is not None:operator.save(control,'retry-review.json',independent_review_raw)
        operator.save(control,'retry-authorization.json',raw)
        ledger.append(ordinal,'retry_authorized',io.sha(raw),stop_reason=stop_reason)
    return dict(version=VERSION,status='heldout_retry_authorized',ordinal=ordinal,authorizationSha256=io.sha(raw),
        modelLaunches=0,reservations=0,automaticRetries=0,certifiesSkillGate=False)


def args(bundle,ordinal):
    return bundle.repository,bundle.bound,ordinal,bundle.sdk_raw,bundle.review_raw,bundle.report_raw,bundle.isolation_raw


def unsealed_launch(rows):
    # 予約だけで起動の印がない枠はモデルを起動していない。起動後に結果を封印していない枠だけを区別する。
    return bool(rows) and rows[-1]['stage'].endswith('_started')


def stop(bundle,proof,ordinal,reason,*,unsealed=False):
    ledger=ledger_for(bundle,proof)
    with ledger.locked():
        if ledger.summary()['status']!='stopped':
            # 封印されていない起動が残る枠は、後継台帳では独立検分なしに再試行させない。
            code='evidence_invalid' if unsealed and operator.successor_ledger(ledger) else 'operator_interrupted'
            score.stop(ledger,bundle.bound,ordinal,ValueError(reason),reason=code)


def preflight_only(bundle):
    proof=resources(bundle)
    return dict(version=VERSION,status='heldout_bundle_resources_and_review_verified_not_launched',
        sourceCommit=bundle.bound.contract['sourceCommit'],executionSha256=io.sha(bundle.bound.execution_raw),
        resourceProofSha256=io.sha(io.encoded(proof)),plannedPrimary=24,plannedIndependent=24,
        privateLedgerOpened=False,remainingReservationsVerified=False,modelLaunches=0,reservations=0,
        certifiesHeldoutLaunch=False,certifiesSkillGate=False)


@contextmanager
def batch_lock(bundle):
    base=x.inputs.PRIVATE_CASES.parent/bundle.bound.contract['outputRelativeRoot']/'controls'
    operator.create_directory(base)
    directory=operator.originals._open_root(base)
    fd=None
    try:
        fd=os.open('batch.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=directory)
        value=os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and value.st_uid==os.getuid() and value.st_nlink==1
            and stat.S_IMODE(value.st_mode)==0o600 and value.st_size==0, 'heldout batch lock metadata')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        operator.check_directory(base,directory)
        yield
        operator.check_directory(base,directory)
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


def run(bundle,*,maximum_slots=2):
    require(type(maximum_slots) is int and 1<=maximum_slots<=2, 'heldout maximum2 slots per batch')
    proof=resources(bundle);operator.auth_metadata()
    # 新継続factoryの旧原検査を、batch controlの新規保存より前にも行う。
    ledger_for(bundle,proof)
    with batch_lock(bundle):return _run_locked(bundle,proof,maximum_slots)


def _run_locked(bundle,proof,maximum_slots):

    results=[];interruption=None
    for _ in range(maximum_slots):
        rows,summary=checkpoint(bundle,proof);ordinal,stage=next_stage(rows,summary)
        if stage in {'stopped','complete','awaiting_retry'}:break
        if stage=='primary' and summary.get('pendingRetry') is None and failure_blocked(bundle,rows,ordinal):
            results.append(dict(ordinal=ordinal,status='blocked_consecutive_failures'))
            break
        try:
            if stage=='ambiguous':
                stop(bundle,proof,ordinal,'unfinished_prior_launch_no_retry',unsealed=unsealed_launch(rows))
                results.append(dict(ordinal=ordinal,status='globally_stopped',reason='unfinished_prior_launch_no_retry'))
                break
            if stage=='primary':
                primary=operator.run_primary(*args(bundle,ordinal))
                if primary['status']=='evaluation_failed':
                    results.append(dict(ordinal=ordinal,status='evaluation_failed',phase='primary'))
                    continue
                require(primary['status']=='heldout_primary_captured_awaits_independent', 'heldout primary unexpected result')
                stage='independent'
            if stage=='independent':
                independent=score.run_independent(*args(bundle,ordinal))
                if independent['status']=='evaluation_failed':
                    results.append(dict(ordinal=ordinal,status='evaluation_failed',phase='independent'))
                    continue
                require(independent['status']=='heldout_independent_captured', 'heldout independent unexpected result')
                stage='parent'
            require(stage=='parent', 'heldout batch stage')
            result=score.finalize(*args(bundle,ordinal))
            require(result['ledgerFinalized'] is True and result['status'] in {'measured_correct','measured_incorrect'},
                'heldout parent unresolved')
            results.append(dict(ordinal=ordinal,status=result['status'],phase='parent'))
        except BaseException as exc:
            stop(bundle,proof,ordinal,type(exc).__name__)
            results.append(dict(ordinal=ordinal,status='globally_stopped',errorType=type(exc).__name__))
            if not isinstance(exc,Exception):interruption=exc
            break
    _,summary=checkpoint(bundle,proof)
    result=dict(version=VERSION,status=('heldout_attempts_recorded_with_prior_stop' if summary.get('priorStoppedSlots') else 'heldout_attempts_recorded') if summary.get('accountedSlots',summary['terminalSlots'])==24 and summary['status']!='stopped'
        else 'heldout_globally_stopped' if summary['status']=='stopped' else 'heldout_batch_recorded',
        sourceCommit=bundle.bound.contract['sourceCommit'],executionSha256=io.sha(bundle.bound.execution_raw),
        slots=results,summary=summary,automaticRetries=0,certifiesFullR04=False,certifiesSkillGate=False)
    if interruption is not None:raise interruption
    return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--maximum-slots',type=int,choices=[1,2]);parser.add_argument('--preflight-only',action='store_true')
    # ADR-068 D2: 前のcampaignで失敗または中断した枠の再試行を承認する。モデルは起動しない。
    parser.add_argument('--authorize-retry',type=int,metavar='ORDINAL');parser.add_argument('--stop-reason')
    parser.add_argument('--prior-artifact');parser.add_argument('--evidence',action='append',default=[])
    parser.add_argument('--reason');parser.add_argument('--independent-review',type=Path)
    args_value=parser.parse_args(argv)
    retry_options=[args_value.stop_reason,args_value.prior_artifact,args_value.reason,args_value.independent_review]
    if args_value.authorize_retry is None and (any(x is not None for x in retry_options) or args_value.evidence):
        parser.error('retry options require --authorize-retry')
    if args_value.authorize_retry is not None and args_value.preflight_only:
        parser.error('--authorize-retry writes the ledger and cannot be combined with --preflight-only')
    if args_value.maximum_slots is not None and (args_value.authorize_retry is not None or args_value.preflight_only):
        parser.error('--maximum-slots applies only to evaluation runs')
    try:
        bundle=load(ROOT,args_value.bundle)
        if args_value.authorize_retry is not None:
            review=None if args_value.independent_review is None else io.read_regular(args_value.independent_review.absolute())
            result=authorize_retry(bundle,args_value.authorize_retry,stop_reason=args_value.stop_reason,
                prior_artifact_sha256=args_value.prior_artifact,evidence_sha256=args_value.evidence,
                reason=args_value.reason,independent_review_raw=review)
            print(io.encoded(result).decode())
            return 0
        result=preflight_only(bundle) if args_value.preflight_only else run(bundle,maximum_slots=args_value.maximum_slots or 2)
        print(io.encoded(result).decode())
        return 1 if result['status']=='heldout_globally_stopped' else 0
    except BaseException as exc:
        # 私的なschema/SDK例外の本文やtracebackを出さない。既消費を0扱いしない。
        print(io.encoded(dict(version=VERSION,status='heldout_batch_rejected',errorType=type(exc).__name__,
            priorConsumptionMayExist=True,automaticRetries=0,certifiesSkillGate=False)).decode())
        return 1


if __name__=='__main__':raise SystemExit(main())
