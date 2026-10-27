"""後継台帳へ移るための準備（ADR-068 D3）。前の台帳は読取り専用で検査し、書くのは標準出力か新規ファイルだけ。

1. `predecessor`: 前の台帳を検査し、後継の実行契約に書く`predecessor`と、引き継ぐ状態の要約を出す。
2. `execution`: いまの実行契約から、後継台帳を使う実行契約0.3.0を作る。開始前の独立検分は作り直す必要がある。
前の台帳への印は、後継台帳を最初に開いたときに置かれる。ここでは置かない。モデル起動・予約はしない。
"""
import argparse
import os
from pathlib import Path

import production_heldout_execution as x
import production_heldout_successor as successor

phases, continuation = successor.phases, successor.continuation
inputs, io, require = successor.inputs, successor.io, successor.require
public = x.public


def carry_summary(state):
    """前の台帳の全eventから再計算した状態の要約。枠ごとの結果の内容は出さない。"""
    final = [values[-1] for values in state['attempts'].values() if values]
    count = lambda *outcomes: sum(item['outcome'] in outcomes for item in final)
    eligible = sorted(n for n, values in state['attempts'].items() if len(values) == 1
        and values[-1]['outcome'] in successor.RETRYABLE
        and (values[-1]['outcome'] != 'interrupted' or successor.policy.classify(values[-1]['stopReason']) != 'safety'))
    return dict(correct=count('correct'), incorrect=count('incorrect'),
        evaluationFailed=count(*successor.FAILURES.values()), interruptedSlots=count('interrupted'),
        pending=count('pending'), nextOrdinal=successor.next_fresh(state), retriesUsed=state['retriesUsed'],
        retryCandidates=eligible, primaryReserved=state['primaryReserved'], campaigns=list(state['campaigns']))


def predecessor(kind, campaign_id=None):
    """前の台帳のheadを固定した`predecessor`を作る。すでに後継の印がある台帳は拒否する。"""
    require(kind in successor.PREDECESSOR_KINDS, 'heldout successor setup predecessor kind')
    if kind == 'continuation-0.2.0':
        campaign_id = continuation.CAMPAIGN
        root = inputs.PRIVATE_CASES.parent/continuation.ROOT_NAME
    else:
        root = successor.root_for(campaign_id)
    with phases.journal_read_lock(root) as directory:
        require(successor.SEAL_NAME not in set(os.listdir(directory)), 'heldout predecessor already has a successor')
        raw = phases._read(root, 'contract.json', maximum=65536, directory=directory)
        if kind == 'continuation-0.2.0':
            continuation.contract(raw)
            snapshot = phases.scan_journal(directory, root, raw, 2)
            rows, head = snapshot.rows, snapshot.head
        else:
            _, rows, head = successor.SuccessorLedger(root, raw).scan(directory)
    spec = successor.predecessor_spec(dict(kind=kind, campaignId=campaign_id, contractSha256=io.sha(raw),
        headSha256=head, events=len(rows)), None)
    # 後継と同じ規則（境界、全eventからの再計算）で前の台帳を検査し直す。
    state, _ = successor.predecessor_state(spec)
    return dict(predecessor=spec, carry=carry_summary(state), sealed=False, modelLaunches=0, reservations=0)


def execution(execution_raw, deployment_raw, repository, *, campaign_id, harness_retries, predecessor_value):
    """いまの実行契約の値を引き継ぎ、campaign・出力先・台帳の設定だけを替えた実行契約0.3.0を作る。"""
    c = x.execution_contract(execution_raw)
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    context_raw = public.guard.git(repository, 'show', c['sourceCommit']+':'+public.inventory.CONTEXT)
    context = public.capture.context_profile(context_raw, d)
    keep = ['sourceCommit', 'model', 'inputContractSha256', 'deploymentSha256', 'pins', 'budget',
        'timeoutSeconds', 'cliVersion', 'certifiesSkillGate']
    value = dict({key: c[key] for key in keep}, version=x.SUCCESSOR_VERSION, campaignId=campaign_id,
        outputRelativeRoot='measurements/'+campaign_id,
        ledger=dict(harnessRetries=harness_retries, predecessor=predecessor_value),
        conditionContextSha256=x.condition_context_sha256(context))
    raw = io.encoded(value)
    x.execution_contract(raw)
    return raw


def write_new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    first = commands.add_parser('predecessor', help='前の台帳を検査してpredecessorを出す')
    first.add_argument('--kind', choices=sorted(successor.PREDECESSOR_KINDS), required=True)
    first.add_argument('--campaign', help='kindがsuccessor-0.3.0のときの前のcampaign ID')
    second = commands.add_parser('execution', help='実行契約0.3.0を新規ファイルに書く')
    second.add_argument('--execution', type=Path, required=True, help='いまの実行契約（execution.json）')
    second.add_argument('--deployment', type=Path, required=True)
    second.add_argument('--predecessor', type=Path, required=True, help='predecessorの出力を保存したJSON')
    second.add_argument('--campaign', required=True, help='後継のcampaign ID（heldout-matrix-で始まる）')
    second.add_argument('--harness-retries', type=int, required=True)
    second.add_argument('--output', type=Path, required=True, help='書き出す先。既存のファイルは上書きしない')
    args = parser.parse_args(argv)
    if args.command == 'predecessor':
        print(io.encoded(predecessor(args.kind, args.campaign)).decode())
        return
    saved = inputs.parse(io.read_regular(args.predecessor.absolute()))
    spec = saved.get('predecessor') if isinstance(saved, dict) else None
    raw = execution(io.read_regular(args.execution.absolute()), io.read_regular(args.deployment.absolute()),
        Path.cwd(), campaign_id=args.campaign, harness_retries=args.harness_retries, predecessor_value=spec)
    write_new(args.output, raw)
    print(io.encoded(dict(status='successor_execution_written', executionSha256=io.sha(raw),
        output=str(args.output), prelaunchReviewRequired=True, modelLaunches=0, reservations=0)).decode())


if __name__ == '__main__':
    main()
