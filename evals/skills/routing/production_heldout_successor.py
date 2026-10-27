"""後継台帳（ADR-068 D2、D3）。日付で変わる値を契約に持たず、前の台帳を読取り専用で引き継ぐ。

モデル起動・原証拠の採点は行わない。前の台帳へ書くのは、後継を作るときの固定名の印1つだけである。
"""
from contextlib import contextmanager
import copy
import fcntl
import os
import re
import stat
from types import MappingProxyType

import production_heldout_continuation as continuation
import production_heldout_phases as phases
import production_stop_policy as policy

legacy = continuation.legacy
inputs, io, require = legacy.inputs, legacy.io, legacy.require
VERSION = 'heldout-matrix-ledger-0.3.0'
SEAL_VERSION = 'heldout-ledger-successor-seal-0.1.0'
SEAL_NAME = phases.SEAL_NAME
ROOT_PARENT = 'measurement-ledgers'
CAMPAIGN = re.compile(r'heldout-matrix-[a-z0-9]+(?:-[a-z0-9]+)*')
SLOTS = 24
MAX_CHAIN = 16
MAX_EVENTS = 256
STAGES, FAILURES, TERMINALS = legacy.STAGES, legacy.FAILURES, legacy.TERMINALS
EVENT_STAGES = frozenset({*STAGES, *FAILURES.values(), 'retry_authorized', 'global_stop'})
EVENT_KEYS = {'version', 'contractSha256', 'sequence', 'previousSha256', 'ordinal', 'stage',
    'artifactSha256', 'dailyProofSha256', 'measuredCorrect', 'stopReason'}
CONTRACT_KEYS = {'version', 'campaignId', 'conditionSha256', 'model', 'setVersion', 'budget',
    'timeoutSeconds', 'predecessor', 'certifiesSkillGate'}
PREDECESSOR_KINDS = frozenset({'continuation-0.2.0', 'successor-0.3.0'})
RETRYABLE = frozenset({'primary_failed', 'independent_failed', 'interrupted'})


def predecessor_spec(value, campaign_id):
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {'kind', 'campaignId', 'contractSha256',
        'headSha256', 'events'} and value['kind'] in PREDECESSOR_KINDS
        and isinstance(value['campaignId'], str) and CAMPAIGN.fullmatch(value['campaignId']) is not None
        and value['campaignId'] != campaign_id and type(value['events']) is int
        and 0 <= value['events'] <= MAX_EVENTS, 'heldout successor predecessor')
    require(value['kind'] != 'continuation-0.2.0' or value['campaignId'] == continuation.CAMPAIGN,
        'heldout successor continuation predecessor campaign')
    io.pin(value['contractSha256'])
    io.pin(value['headSha256'])
    return value


def contract(raw):
    require(isinstance(raw, bytes), 'heldout successor contract bytes')
    value = inputs.parse(raw)
    require(isinstance(value, dict) and set(value) == CONTRACT_KEYS, 'heldout successor contract inventory')
    require(value['version'] == VERSION and isinstance(value['campaignId'], str)
        and CAMPAIGN.fullmatch(value['campaignId']) is not None and value['model'] == 'gpt-6.1-sol'
        and value['setVersion'] == inputs.SET_VERSION and value['certifiesSkillGate'] is False,
        'heldout successor contract identity')
    io.pin(value['conditionSha256'])
    budget = value['budget']
    require(isinstance(budget, dict) and set(budget) == {'primary', 'independent', 'automaticRetries',
        'delegations', 'harnessRetries'} and budget['primary'] == budget['independent'] == SLOTS
        and budget['automaticRetries'] == budget['delegations'] == 0
        and type(budget['harnessRetries']) is int and 0 <= budget['harnessRetries'] <= SLOTS,
        'heldout successor budgets')
    timeout = value['timeoutSeconds']
    require(isinstance(timeout, dict) and set(timeout) == {'primary', 'independent'}
        and all(type(x) is int and 1 <= x <= 600 for x in timeout.values()), 'heldout successor timeout')
    predecessor_spec(value['predecessor'], value['campaignId'])
    return value


def root_for(campaign_id):
    require(isinstance(campaign_id, str) and CAMPAIGN.fullmatch(campaign_id) is not None,
        'heldout successor campaign root')
    return inputs.PRIVATE_CASES.parent/ROOT_PARENT/campaign_id


def empty_state():
    return dict(attempts={}, retriesUsed=0, primaryReserved=0, primaryLaunchMarked=0,
        independentReserved=0, independentLaunchMarked=0, parentVerified=0, proof={}, campaigns=[])


def fold(state, rows, campaign_id, *, segment=True):
    """全eventから試行と消費を再計算する。版0.1/0.2のrowも同じ規則で数える。"""
    state = copy.deepcopy(state)
    if segment:
        state['campaigns'].append(campaign_id)
    for row in rows:
        stage, ordinal = row['stage'], row['ordinal']
        attempts = state['attempts'].setdefault(ordinal, []) if ordinal is not None else None
        if stage == 'primary_reserved':
            attempts.append(dict(campaignId=campaign_id, outcome='pending', stopReason=None))
            state['primaryReserved'] += 1
            state['proof'] = dict(primary=row.get('dailyProofSha256'))
        elif stage == 'independent_reserved':
            state['independentReserved'] += 1
            state['proof']['independent'] = row.get('dailyProofSha256')
        elif stage in {'primary_started', 'independent_started'}:
            state[('primary' if stage == 'primary_started' else 'independent')+'LaunchMarked'] += 1
        elif stage == 'parent_verified':
            attempts[-1]['outcome'] = 'correct' if row['measuredCorrect'] else 'incorrect'
            state['parentVerified'] += 1
        elif stage in FAILURES.values():
            attempts[-1].update(outcome=stage, artifactSha256=row.get('artifactSha256'))
        elif stage == 'retry_authorized':
            state['retriesUsed'] += 1
            attempts[-1]['retryReason'] = row['stopReason']
        elif stage == 'global_stop':
            for values in state['attempts'].values():
                if values and values[-1]['outcome'] == 'pending':
                    values[-1].update(outcome='interrupted', stopReason=row['stopReason'],
                        artifactSha256=row.get('artifactSha256'))
    return state


def next_fresh(state):
    return next((n for n in range(1, SLOTS+1) if n not in state['attempts']), None)


def boundary(state, rows):
    """後継へ渡せるのは、未完の試行がない終端境界か、停止した台帳だけ。"""
    require(all(values[-1]['outcome'] != 'pending' for values in state['attempts'].values() if values)
        and not (rows and rows[-1]['stage'] == 'retry_authorized'), 'heldout successor predecessor boundary')


def seal_value(spec, successor_raw):
    return dict(version=SEAL_VERSION, successorCampaignId=contract(successor_raw)['campaignId'],
        successorContractSha256=io.sha(successor_raw), predecessorCampaignId=spec['campaignId'],
        predecessorContractSha256=spec['contractSha256'], predecessorHeadSha256=spec['headSha256'],
        predecessorEvents=spec['events'])


def _seal_shape(raw, head, events):
    value = inputs.parse(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'successorCampaignId',
        'successorContractSha256', 'predecessorCampaignId', 'predecessorContractSha256',
        'predecessorHeadSha256', 'predecessorEvents'} and value['version'] == SEAL_VERSION
        and value['predecessorHeadSha256'] == head and value['predecessorEvents'] == events,
        'heldout successor seal binding')
    return value


def _continuation_prior():
    raws = continuation.verify_prior()
    rows = [inputs.parse(raws['event'+str(i)]) for i in range(1, 4)]
    return fold(empty_state(), rows, legacy.contract(raws['ledgerContract'])['campaignId'])


def predecessor_state(spec, *, seal_sha256=None, directory=None, depth=0):
    """前の台帳をreadonlyで検査し、累積の状態を返す。directoryはcallerが排他lock中のfd。"""
    require(depth < MAX_CHAIN, 'heldout successor chain depth')
    if spec['kind'] == 'continuation-0.2.0':
        root = inputs.PRIVATE_CASES.parent/continuation.ROOT_NAME
    else:
        root = root_for(spec['campaignId'])
    if directory is None:
        with phases.journal_read_lock(root) as held:
            return predecessor_state(spec, seal_sha256=seal_sha256, directory=held, depth=depth)
    raw = phases._read(root, 'contract.json', maximum=65536, directory=directory)
    require(io.sha(raw) == spec['contractSha256'], 'heldout successor predecessor contract drift')
    if spec['kind'] == 'continuation-0.2.0':
        continuation.contract(raw)
        snapshot = phases.scan_journal(directory, root, raw, 2, seal_sha256=seal_sha256)
        state = fold(_continuation_prior(), snapshot.rows, spec['campaignId'])
        rows, head = snapshot.rows, snapshot.head
    else:
        ledger = SuccessorLedger(root, raw, depth=depth+1)
        state, rows, head = ledger.scan(directory, seal_sha256=seal_sha256)
    require(len(rows) == spec['events'] and head == spec['headSha256'],
        'heldout successor predecessor journal drift')
    boundary(state, rows)
    return state, root


def open_for(raw):
    return SuccessorLedger(root_for(contract(raw)['campaignId']), raw)


class SuccessorLedger(legacy.HeldoutLedger):
    """root引数は隔離試験用。製品のfactoryはcampaignIdから導いたrootだけを使う。"""
    records_daily_proof = True

    def __init__(self, root, raw, *, depth=0):
        self.raw, self.contract, self.digest = raw, contract(raw), io.sha(raw)
        self.root, self.directory, self.depth = root, None, depth
        require(self.root.is_absolute() and '..' not in self.root.parts, 'heldout successor absolute root')
        self.sealed = False

    def base_state(self):
        """読むたびに前の台帳と印を再照合する。条件の比較可能性は開始前の独立検分が判断する。"""
        spec = self.contract['predecessor']
        if spec is None:
            return fold(empty_state(), [], self.contract['campaignId'])
        expected = io.sha(io.encoded(seal_value(spec, self.raw)))
        base, _ = predecessor_state(spec, seal_sha256=expected, depth=self.depth)
        # 古いcampaignのIDを再利用すると、出力rootと再試行の判定が前の試行と混ざる。
        require(self.contract['campaignId'] not in base['campaigns'], 'heldout successor campaign reused in chain')
        return fold(base, [], self.contract['campaignId'])

    @contextmanager
    def locked(self):
        require(self.directory is None, 'heldout successor nested lock')
        self.directory = self._directory()
        lock = None
        try:
            lock = os.open('lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600, dir_fd=self.directory)
            info = os.fstat(lock)
            require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_size == 0,
                'heldout successor owner lock')
            fcntl.flock(lock, fcntl.LOCK_EX)
            if 'contract.json' not in set(os.listdir(self.directory)):
                require(set(os.listdir(self.directory)) == {'lock'}, 'heldout successor incomplete initialization')
                self._seal_predecessor()
                self._write('contract.json', self.raw)
            require(self._read('contract.json') == self.raw, 'heldout successor condition cannot reset')
            self._history()
            yield self
        finally:
            if lock is not None:
                os.close(lock)
            os.close(self.directory)
            self.directory = None

    def _seal_predecessor(self):
        """前の台帳のlockを排他で取り、全eventを再照合してから印を新規作成する。"""
        spec = self.contract['predecessor']
        if spec is None:
            return
        root = (inputs.PRIVATE_CASES.parent/continuation.ROOT_NAME if spec['kind'] == 'continuation-0.2.0'
            else root_for(spec['campaignId']))
        raw = io.encoded(seal_value(spec, self.raw))
        directory = phases._originals()._open_root(root)
        lock = None
        try:
            lock = os.open('lock', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            fcntl.flock(lock, fcntl.LOCK_EX)
            if SEAL_NAME in set(os.listdir(directory)):
                # 中断後の再初期化だけを許す。別の後継の印は上書きしない。
                require(phases._read(root, SEAL_NAME, directory=directory) == raw,
                    'heldout successor predecessor already sealed')
            else:
                state, _ = predecessor_state(spec, directory=directory, depth=self.depth)
                # 不正な後継が前の台帳へ印を置いて塞がないよう、印の前に検査する。
                require(self.contract['campaignId'] not in state['campaigns'], 'heldout successor campaign reused in chain')
                fd = os.open(SEAL_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=directory)
                try:
                    with os.fdopen(fd, 'wb', closefd=False) as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(fd)
                finally:
                    os.close(fd)
                os.fsync(directory)
            predecessor_state(spec, seal_sha256=io.sha(raw), directory=directory, depth=self.depth)
        finally:
            if lock is not None:
                os.close(lock)
            os.close(directory)

    def scan(self, directory, *, seal_sha256=None):
        """lock中のdirectoryを読取り専用で検査する。前の台帳としての読取りにも使う。"""
        observed = {}
        read = lambda name: phases._read(self.root, name, maximum=65536, directory=directory, observed=observed)
        require(read('contract.json') == self.raw, 'heldout successor contract drift')
        names = set(os.listdir(directory))
        fixed = {'lock', 'contract.json'} | ({SEAL_NAME} if SEAL_NAME in names else set())
        events = names-fixed
        require(len(events) <= MAX_EVENTS and events == {f'event-{n:04d}.json' for n in range(1, len(events)+1)},
            'heldout successor event inventory')
        state, rows, previous = self.base_state(), [], self.digest
        for index in range(1, len(events)+1):
            raw = read(f'event-{index:04d}.json')
            value = inputs.parse(raw)
            require(isinstance(value, dict) and set(value) == EVENT_KEYS and value['version'] == VERSION
                and value['contractSha256'] == self.digest and type(value['sequence']) is int
                and value['sequence'] == index and value['previousSha256'] == previous
                and isinstance(value['stage'], str) and value['stage'] in EVENT_STAGES,
                'heldout successor event identity')
            self._check(state, rows, value)
            rows.append(MappingProxyType(value))
            state = fold(state, [value], self.contract['campaignId'], segment=False)
            previous = io.sha(raw)
        self.sealed = SEAL_NAME in names
        if self.sealed:
            raw = read(SEAL_NAME)
            require(seal_sha256 is None or io.sha(raw) == seal_sha256, 'heldout successor seal drift')
            _seal_shape(raw, previous, len(rows))
        for name in tuple(observed):
            read(name)
        require(set(os.listdir(directory)) == names, 'heldout successor journal directory drift')
        return state, rows, previous

    def _history(self):
        require(self.directory is not None, 'heldout successor lock required')
        state, rows, previous = self.scan(self.directory)
        self._state = state
        return rows, previous

    def _check(self, state, rows, value):
        ordinal, stage = value['ordinal'], value['stage']
        own = self.contract['campaignId']
        require(not rows or rows[-1]['stage'] != 'global_stop', 'heldout successor permanently stopped')
        require(value['measuredCorrect'] is None if stage != 'parent_verified'
            else type(value['measuredCorrect']) is bool, 'heldout successor measured correctness')
        if stage == 'global_stop':
            require(ordinal is None and value['stopReason'] in policy.REASONS
                and value['artifactSha256'] is not None and value['dailyProofSha256'] is None,
                'heldout successor global stop')
            io.pin(value['artifactSha256'])
            return
        require(type(ordinal) is int and 1 <= ordinal <= SLOTS, 'heldout successor slot')
        previous = rows[-1] if rows else None
        at_boundary = previous is None or previous['stage'] in TERMINALS
        if stage == 'retry_authorized':
            attempts = state['attempts'].get(ordinal, [])
            require(at_boundary and value['artifactSha256'] is not None and value['dailyProofSha256'] is None,
                'heldout successor retry boundary')
            io.pin(value['artifactSha256'])
            require(policy.classify(value['stopReason']) != 'safety'
                and len(attempts) == 1 and attempts[-1]['campaignId'] != own
                and attempts[-1]['outcome'] in RETRYABLE
                and (attempts[-1]['outcome'] != 'interrupted' or attempts[-1]['stopReason'] == value['stopReason']),
                'heldout successor retry requires one earlier failed attempt outside this campaign')
            require(state['retriesUsed'] < self.contract['budget']['harnessRetries'], 'heldout successor retry budget')
            return
        require(value['stopReason'] is None, 'heldout successor unexpected stop reason')
        if at_boundary or previous['stage'] == 'retry_authorized':
            require(stage == 'primary_reserved', 'heldout successor next stage')
            expected = previous['ordinal'] if previous is not None and previous['stage'] == 'retry_authorized' \
                else next_fresh(state)
            require(ordinal == expected, 'heldout successor next ordinal')
        else:
            require(ordinal == previous['ordinal'], 'heldout successor previous slot pending')
            before = previous['stage']
            require(stage == STAGES[STAGES.index(before)+1] or stage == FAILURES.get(before),
                'heldout successor stage order')
        marker = stage.endswith('_reserved') or stage.endswith('_started')
        require((value['artifactSha256'] is None) == marker, 'heldout successor evidence required')
        if value['artifactSha256'] is not None:
            io.pin(value['artifactSha256'])
        if stage.endswith('_reserved'):
            io.pin(value['dailyProofSha256'])
        elif stage.endswith('_failed'):
            role = stage.split('_')[0]
            require(value['dailyProofSha256'] == state['proof'].get(role), 'heldout successor failure proof')
        else:
            require(value['dailyProofSha256'] is None, 'heldout successor unexpected daily proof')

    def candidate(self, ordinal, stage, artifact_sha256=None, *, resource_proof_sha256=None,
                  measured_correct=None, stop_reason=None):
        """追記と同じ検査だけを行う。原を保存する前の事前確認に使い、台帳へは書かない。"""
        rows, previous = self._history()
        require(not self.sealed, 'heldout successor ledger sealed by its successor')
        require(stage in EVENT_STAGES, 'heldout successor stage')
        value = dict(version=VERSION, contractSha256=self.digest, sequence=len(rows)+1,
            previousSha256=previous, ordinal=ordinal, stage=stage, artifactSha256=artifact_sha256,
            dailyProofSha256=resource_proof_sha256, measuredCorrect=measured_correct, stopReason=stop_reason)
        self._check(self._state, rows, value)
        return rows, value

    def append(self, ordinal, stage, artifact_sha256=None, *, resource_proof_sha256=None,
               measured_correct=None, stop_reason=None):
        """resource_proof_sha256は当日の資源証明として予約と評価失敗のeventへ記録する。"""
        rows, value = self.candidate(ordinal, stage, artifact_sha256, resource_proof_sha256=resource_proof_sha256,
            measured_correct=measured_correct, stop_reason=stop_reason)
        raw = io.encoded(value)
        self._write(f'event-{len(rows)+1:04d}.json', raw)
        return dict(sequence=len(rows)+1, sha256=io.sha(raw))

    def summary(self):
        rows, _ = self._history()
        state = self._state
        final = {n: values[-1] for n, values in state['attempts'].items() if values}
        count = lambda *outcomes: sum(item['outcome'] in outcomes for item in final.values())
        correct, incorrect = count('correct'), count('incorrect')
        failed, interrupted, pending = count(*FAILURES.values()), count('interrupted'), count('pending')
        accounted = correct+incorrect+failed+interrupted
        stopped = bool(rows and rows[-1]['stage'] == 'global_stop')
        remaining = self.contract['budget']['harnessRetries']-state['retriesUsed']
        eligible = [] if remaining <= 0 or pending or (rows and rows[-1]['stage'] not in TERMINALS) else sorted(
            n for n, values in state['attempts'].items() if len(values) == 1
            and values[-1]['outcome'] in RETRYABLE and values[-1]['campaignId'] != self.contract['campaignId']
            and (values[-1]['outcome'] != 'interrupted' or policy.classify(values[-1]['stopReason']) != 'safety'))
        return dict(status='stopped' if stopped else 'attempts_recorded' if accounted == SLOTS and not pending
            else 'in_progress', primaryReserved=state['primaryReserved'],
            primaryLaunchMarked=state['primaryLaunchMarked'], independentReserved=state['independentReserved'],
            independentLaunchMarked=state['independentLaunchMarked'], parentVerified=state['parentVerified'],
            correct=correct, incorrect=incorrect, evaluationFailed=failed, interruptedSlots=interrupted,
            terminalSlots=correct+incorrect+failed, accountedSlots=accounted, pending=pending,
            unattempted=SLOTS-len(final), nextOrdinal=next_fresh(state), retriesUsed=state['retriesUsed'],
            retriesRemaining=remaining,
            retryEligible=eligible, pendingRetry=rows[-1]['ordinal'] if rows and rows[-1]['stage'] == 'retry_authorized'
            else None, campaigns=list(state['campaigns']), certifiesSkillGate=False)
