"""初回公開カナリアを取得→構造検査→独立採点→親確定の順に進める。"""
import argparse
from pathlib import Path
import time

import production_canary_capture as capture
import production_canary_evidence as evidence
import production_canary_score as score
import production_ledger as ledger
import production_trace as trace

ROOT=Path(__file__).resolve().parents[3]


def save_progress(source,bound,attempt,result):
    base=ROOT/'.venv/production-routing-campaign-public-initial'
    ledger.safe_tree(base);base.mkdir(mode=0o700,parents=True,exist_ok=True)
    record=dict(sourceCommit=source,attempt=bound.attempt(attempt),result=result,recordedAtUnix=time.time(),
                automaticRetry=False,certifiesBehavior=False,certifiesSkillGate=False)
    ledger.exclusive(base/f'attempt-{attempt:04d}.json',ledger.encoded(record))
    return record


def one(source,dry_run=False):
    bound,_=capture.prepare(source)
    if dry_run:return dict(status='canary_campaign_preflight_checked',primaryInvocations=0,independentInvocations=0,certifiesSkillGate=False)
    instance=ledger.open_ledger(ROOT,bound)
    with instance.locked():instance.initialize();completed=instance.reservations()
    if completed==4:return dict(status='finite_canary_four_attempts_accepted',completed=4,certifiesBehavior=False,certifiesSkillGate=False)
    ordinal=completed+1
    owned=False
    def acquired(attempt):
        nonlocal owned
        trace.require(trace.json_equal(attempt,bound.attempt(ordinal)),'this campaign reservation binding')
        owned=True
    # 各呼出しは別途、共有台帳の最新pendingを検査する。未検分中に次を起動しない。
    try:
        code=capture.run(source,expected_ordinal=ordinal,on_reserved=acquired)
        trace.require(owned,'capture did not acquire this campaign reservation')
        if code==0:
            context=evidence.load_verified_capture(ROOT,source,ordinal)
            score.prepare(ROOT,context)
    except (ValueError,OSError,trace.jsonschema.exceptions.ValidationError) as exc:
        # 起動前拒否では予約がない。起動後の不適合だけを実際の予約へ記録する。
        if not owned:raise
        raw=score.original_failure_file(ROOT/bound.attempt(ordinal)['outputRelativePath']/'receipt.json')
        stopped=instance.record_primary_stop(ordinal,'primary-structure-rejected' if raw is not None else 'primary-receipt-missing',ledger.sha(raw) if raw is not None else None)
        return save_progress(source,bound,ordinal,dict(stopped,errorType=type(exc).__name__))
    if code!=0:
        raw=score.original_failure_file(ROOT/bound.attempt(ordinal)['outputRelativePath']/'receipt.json')
        stopped=instance.record_primary_stop(ordinal,'primary-capture-failed' if raw is not None else 'primary-receipt-missing',ledger.sha(raw) if raw is not None else None)
        return save_progress(source,bound,ordinal,stopped)
    try:
        independent=score.run(source,ordinal)
        if independent['status']=='stopped_independent_verification':return save_progress(source,bound,ordinal,independent)
        final=score.finalize(ROOT,source,ordinal)
    except (ValueError,OSError,trace.jsonschema.exceptions.ValidationError) as exc:
        if (instance.storage/f'stop-{ordinal:04d}.json').exists() or (instance.storage/f'review-{ordinal:04d}.json').exists():raise
        if (instance.storage/f'independent-{ordinal:04d}.json').exists():
            final=score.save_independent_failure(ROOT,bound,ordinal,'independent-execution-incomplete',type(exc).__name__)
        else:
            raw=score.original_failure_file(ROOT/bound.attempt(ordinal)['outputRelativePath']/'receipt.json')
            final=instance.record_primary_stop(ordinal,'primary-structure-rejected' if raw is not None else 'primary-receipt-missing',ledger.sha(raw) if raw is not None else None)
    return save_progress(source,bound,ordinal,final)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    print(capture.json.dumps(one(args.source,args.dry_run),ensure_ascii=False))
