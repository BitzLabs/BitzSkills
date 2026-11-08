"""公開部分集合を、同じ契約と台帳で未予約の次枠へ進める。"""
import math
from pathlib import Path
import time

import production_matrix_capture as capture
import production_matrix_rate_limits as rate_limits
import production_matrix_score as score

p = capture.p
io = p.io
require = p.require
matrix = p.matrix
MINIMUM_LAUNCH_GAP_SECONDS = 5


def wait_until(snapshot, now):
    """標準枠の残量が不足する場合だけ、Unix秒で再確認予定を返す。"""
    require(isinstance(snapshot, dict) and snapshot.get('limitId') == 'codex'
        and snapshot.get('spendControlReached') is False
        and 'rateLimitReachedType' in snapshot and snapshot['rateLimitReachedType'] is None,
        'matrix continuation rate state unresolved')
    resets = []
    for name, ceiling in (('primary', 80), ('secondary', 98)):
        window = snapshot.get(name)
        require(isinstance(window, dict), 'matrix continuation rate window missing')
        used = window.get('usedPercent')
        reset = window.get('resetsAt')
        duration = window.get('windowDurationMins')
        require(type(used) in {int, float} and math.isfinite(used) and 0 <= used <= 100
            and type(reset) in {int, float} and math.isfinite(reset) and reset > now
            and type(duration) in {int, float} and math.isfinite(duration) and duration > 0,
            'matrix continuation rate window invalid or expired')
        if used >= ceiling:
            resets.append(reset)
    return max(resets, default=None)


def pace():
    """再起動前の単調時計を参照せず、照合済みの前工程から改めて間隔を取る。"""
    start = time.monotonic()
    time.sleep(MINIMUM_LAUNCH_GAP_SECONDS)
    require(time.monotonic()-start >= MINIMUM_LAUNCH_GAP_SECONDS,
        'matrix continuation launch gap not met')


def next_ordinal(instance):
    """呼出し側が起動制御と台帳を排他した状態で再開点を導出する。"""
    instance.initialize()
    if matrix.present(instance.storage/'stop.json'):
        return None, 'stopped'
    last = instance.checked_count()
    if last:
        if not matrix.present(instance.path('review', last)):
            instance.stop(last, 'continuation-reserved-slot-incomplete', 'Interrupted')
            return None, 'stopped'
        if instance.read('review', last)['status'] == 'measured_incorrect':
            instance.stop(last, 'continuation-measured-incorrect', 'MeasuredIncorrect')
            return None, 'stopped'
    if last == instance.maximum:
        return last+1, 'complete'
    return last+1, None


def advance(instance, control, read_limits, verify, verify_completed, primary, independent, finalize):
    """1枠進めるか、予約せず待機を返す。起動中断後の再起動は予約から検知する。"""
    with capture.locked_control(control) as guard:
        with instance.locked():
            ordinal, terminal = next_ordinal(instance)
        if terminal == 'stopped':
            return dict(status=terminal)
        proof = verify()
        if terminal != 'complete':
            if ordinal > 1:
                pace()
            started = time.monotonic()
            snapshot = read_limits()
            require(time.monotonic()-started <= 60, 'matrix continuation rate snapshot stale')
            guard()
            until = wait_until(snapshot, time.time())
            if until is not None:
                return dict(status='waiting_for_rate_window', ordinal=ordinal, waitUntilUnix=until)
        for completed in range(1, ordinal):
            try:
                verify_completed(completed, proof)
            except Exception as error:
                guard()
                with instance.locked():
                    instance.stop(completed, 'continuation-completed-original-rejected', type(error).__name__)
                raise
        if terminal == 'complete':
            return dict(status=terminal)
        def admit():
            require(time.monotonic()-started <= 60 and wait_until(snapshot,time.time()) is None,
                'matrix continuation rate snapshot stale before reservation')
            guard()

        admit()
        try:
            require(primary(ordinal,guard,admit)['status']=='primary_capture_awaits_independent_review',
                'matrix continuation primary stopped')
            pace()
            guard()
            require(independent(ordinal,guard)['status']=='matrix_independent_captured',
                'matrix continuation independent stopped')
            result=finalize(ordinal,guard)
            guard()
            require(result.get('ledgerFinalized') is True, 'matrix continuation parent stopped')
            with instance.locked():
                require(instance.checked_count()==ordinal, 'matrix continuation ledger count drift')
                status=instance.read('review', ordinal)['status']
                require(status==result['verification']['proposedLedgerStatus'],
                    'matrix continuation finalized status drift')
                if status=='measured_incorrect':
                    instance.stop(ordinal, 'continuation-measured-incorrect', 'MeasuredIncorrect')
            return dict(status=status, ordinal=ordinal)
        except BaseException as error:
            guard()
            with instance.locked():
                if matrix.present(instance.path('attempt', ordinal)):
                    instance.stop(ordinal, 'continuation-evaluation-stopped', type(error).__name__)
            raise


def run_next(repository: Path, bundle: Path, approved_condition: str, read_limits=None):
    """独立検分された固定条件について、承認済みの実行器から呼び出す入口。"""
    require(bundle.is_relative_to(repository/'.venv') and '..' not in bundle.parts,
        'matrix continuation bundle boundary')
    raws={name:io.read_regular(bundle/(name+'.input.json')) for name in matrix.inputs.INPUT_NAMES}
    bound=matrix.bind(io.read_regular(bundle/'execution.json'),io.read_regular(bundle/'input-contract.json'),**raws)
    c=bound.contract
    require(c.get('continuationPolicy')==matrix.CONTINUATION_POLICY, 'matrix continuation opt-in required')
    deployment=io.read_regular(bundle/'deployment.json')
    sdk=io.read_regular(bundle/'sdk-manifest.json')
    review=io.read_regular(bundle/'prelaunch-review.json')
    report=io.read_regular(bundle/'code-review.json')
    approved=capture.prelaunch_review(bound,deployment,review,report)
    own=io.read_regular(Path(__file__).absolute())
    require(approved['scope']==score.SCOPE and approved['conditionSha256']==io.pin(approved_condition)
        and p.trace.strict_json(report).get('continuationOperatorSha256')==io.sha(own)
        and own==p.guard.git(repository,'show',c['sourceCommit']+':evals/skills/routing/production_matrix_continuation.py'),
        'matrix continuation reviewed operator and approved condition required')
    d=p.deployment(bound,deployment)
    if read_limits is None:
        path = 'evals/skills/routing/production_matrix_rate_limits.py'
        worker = io.read_regular(repository/path)
        require(worker==p.guard.git(repository,'show',c['sourceCommit']+':'+path)
            and io.sha(worker)==p.trace.strict_json(report).get('rateReaderSha256'),
            'matrix continuation reviewed rate reader required')
        sdk_path = repository/d['sdkRelativePath']

        def read_limits():
            capture.auth_metadata()
            return rate_limits.read(repository,sdk_path,d['codexPath'],capture.AUTH,worker)

    artifact=io.common_ledger_path(repository).parent.parent
    control=score.control_root(artifact,bound)
    storage=matrix.shared_storage(repository,bound)
    io.safe_tree(storage.parent)
    storage.parent.mkdir(mode=0o700,exist_ok=True)
    instance=matrix.open_ledger(storage,artifact,bound)

    def verify():
        return p.verify_resources(repository,bound,deployment,sdk)

    def primary(ordinal, guard, admit):
        return capture._run(repository,bound,deployment,sdk,review,report,ordinal,control_guard=guard,before_reserve=admit)

    def scoring_args(ordinal):
        manifest=io.read_regular(repository/d['snapshotRelativePath']/'manifest.json')
        schema=p.decision_schema(p.guard.git(repository,'show',c['sourceCommit']+':'+p.inventory.SCHEMA))
        context=p.guard.git(repository,'show',c['sourceCommit']+':'+p.inventory.CONTEXT)
        return repository,bound,ordinal,manifest,schema,context,review,report

    return advance(instance,control,read_limits,verify,
        lambda n, proof:score.verify_completed(*scoring_args(n),resource_proof=proof), primary,
        lambda n,guard:score._run(*scoring_args(n),control_guard=guard),
        lambda n,guard:score._finalize(*scoring_args(n),control_guard=guard))



def run_waiting(repository: Path, bundle: Path, approved_condition: str):
    """待機した同じ枠を、日付を条件にせず再確認する。確定・停止は呼出し側へ返す。"""
    while True:
        result = run_next(repository,bundle,approved_condition)
        if result['status'] != 'waiting_for_rate_window':
            return result
        while (remaining := result['waitUntilUnix']-time.time()) > 0:
            time.sleep(min(remaining,60))
