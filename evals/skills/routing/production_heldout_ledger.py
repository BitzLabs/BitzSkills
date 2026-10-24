"""保持24枠の追記専用台帳部品。原証拠の採点・モデル起動・開始許可は行わない。"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import stat

import production_heldout_inputs as inputs

io, require = inputs.io, inputs.require
VERSION = 'heldout-matrix-ledger-0.1.0'
# worktree/ref/outputを変更しても同じ評価目的の予約を返却しない。
SHARED_ROOT = inputs.PRIVATE_CASES.parent/'measurement-ledgers/r04-heldout-two-repetitions-01'
STAGES = ('primary_reserved', 'primary_started', 'primary_captured',
    'independent_reserved', 'independent_started', 'independent_captured', 'parent_verified')
FAILURES = {'primary_started': 'primary_failed', 'independent_started': 'independent_failed'}
TERMINALS = {'parent_verified', 'primary_failed', 'independent_failed'}
STOP_REASONS = {'source_drift', 'resource_drift', 'unsafe', 'unknown_event', 'evidence_invalid',
    'storage_failure', 'independent_rejected', 'operator_interrupted'}


def contract(raw):
    require(isinstance(raw, bytes), 'heldout ledger bytes')
    value = inputs.parse(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'campaignId', 'sourceCommit',
        'inputContractSha256', 'resourceProofSha256', 'model', 'setVersion', 'budget',
        'timeoutSeconds', 'certifiesSkillGate'}, 'heldout ledger contract inventory')
    require(value['version'] == VERSION and isinstance(value['campaignId'], str)
        and re.fullmatch(r'heldout-matrix-[a-z0-9]+(?:-[a-z0-9]+)*', value['campaignId']) is not None
        and isinstance(value['sourceCommit'], str) and re.fullmatch(r'[0-9a-f]{40}', value['sourceCommit']) is not None
        and value['model'] == 'gpt-6.1-sol' and value['setVersion'] == inputs.SET_VERSION
        and value['certifiesSkillGate'] is False, 'heldout ledger identity')
    for name in ['inputContractSha256', 'resourceProofSha256']:
        io.pin(value[name])
    require(inputs.trace.json_equal(value['budget'], dict(primary=24, independent=24,
        automaticRetries=0, delegations=0)), 'heldout ledger budgets')
    timeout = value['timeoutSeconds']
    require(isinstance(timeout, dict) and set(timeout) == {'primary', 'independent'}
        and all(type(x) is int and 1 <= x <= 600 for x in timeout.values()), 'heldout ledger timeout')
    return value


def open_shared(contract_raw):
    """製品接続用の所在解決だけ。contractの開始前独立検分は後続adapterの責務。"""
    if inputs.parse(contract_raw).get('campaignId') == 'heldout-matrix-survey-remaining23-20261024-01':
        from production_heldout_continuation import open_fixed
        return open_fixed(contract_raw)
    return HeldoutLedger(SHARED_ROOT, contract_raw)


class HeldoutLedger:
    """root引数は隔離試験用。渡された原hashの意味/安全性を自己認定しない。"""
    def __init__(self, root, contract_raw):
        self.root = Path(root)
        require(self.root.is_absolute() and '..' not in self.root.parts, 'heldout ledger absolute root')
        self.raw = contract_raw
        self.contract = contract(contract_raw)
        self.digest = io.sha(contract_raw)
        self.directory = None

    def _directory(self):
        directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            current = Path('/')
            for part in self.root.parts[1:]:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory)
                    os.fsync(directory)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
                current /= part
                if current.is_relative_to(inputs.PRIVATE_CASES.parent):
                    value = os.fstat(directory)
                    require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid(),
                        'heldout private ancestor directory')
            value = os.fstat(directory)
            require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid(), 'heldout ledger owner directory')
            return directory
        except BaseException:
            os.close(directory)
            raise

    def _read(self, name):
        # パスの再解決を避け、ロックしたdirectory fdの下だけを読む。
        self._check_directory()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_uid == os.getuid() and before.st_nlink == 1
                and 0 < before.st_size <= 65536, 'heldout ledger owner file')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(65537)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_nlink,
                before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_nlink,
                 after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and len(raw) == before.st_size, 'heldout ledger read drift')
            self._check_directory()
            return raw
        finally:
            os.close(fd)

    def _write(self, name, raw):
        self._check_directory()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600, dir_fd=self.directory)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(fd)
            require(os.fstat(fd).st_nlink == 1, 'heldout ledger write hardlink')
        finally:
            os.close(fd)
        os.fsync(self.directory)
        self._check_directory()

    def _check_directory(self):
        require(self.directory is not None, 'heldout ledger lock required')
        value = os.fstat(self.directory)
        require(stat.S_ISDIR(value.st_mode) and stat.S_IMODE(value.st_mode) == 0o700
            and value.st_uid == os.getuid() and value.st_nlink >= 2, 'heldout ledger directory drift')

    @contextmanager
    def locked(self):
        require(self.directory is None, 'heldout ledger nested lock')
        self.directory = self._directory()
        lock = None
        try:
            lock = os.open('lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600, dir_fd=self.directory)
            info = os.fstat(lock)
            require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_size == 0,
                'heldout ledger owner lock')
            fcntl.flock(lock, fcntl.LOCK_EX)
            names = set(os.listdir(self.directory))
            if 'contract.json' not in names:
                require(names == {'lock'}, 'heldout ledger incomplete initialization')
                self._write('contract.json', self.raw)
            require(self._read('contract.json') == self.raw, 'heldout ledger condition cannot reset')
            self._history()
            yield self
        finally:
            if lock is not None:
                os.close(lock)
            os.close(self.directory)
            self.directory = None

    def _transition(self, rows, value):
        ordinal, stage = value['ordinal'], value['stage']
        require(not rows or rows[-1]['stage'] != 'global_stop', 'heldout ledger permanently stopped')
        if stage == 'global_stop':
            require(ordinal is None and value['stopReason'] in STOP_REASONS
                and value['artifactSha256'] is not None and value['measuredCorrect'] is None
                and value['resourceProofSha256'] is None, 'heldout global stop')
            return
        require(type(ordinal) is int and 1 <= ordinal <= 24 and value['stopReason'] is None, 'heldout ledger slot')
        previous = rows[-1] if rows else None
        if previous is None or previous['stage'] in TERMINALS:
            next_ordinal = 1 if previous is None else previous['ordinal']+1
            require(ordinal == next_ordinal and stage == 'primary_reserved', 'heldout ledger next ordinal')
        else:
            require(ordinal == previous['ordinal'], 'heldout ledger previous slot pending')
            before = previous['stage']
            expected = STAGES[STAGES.index(before)+1]
            require(stage == expected or stage == FAILURES.get(before), 'heldout ledger stage order')
        marker = stage.endswith('_reserved') or stage.endswith('_started')
        require((value['artifactSha256'] is None) == marker, 'heldout ledger evidence required')
        if stage.endswith('_failed'):
            require(value['resourceProofSha256'] == self.contract['resourceProofSha256']
                and value['measuredCorrect'] is None, 'heldout failure requires unchanged resource proof')
        else:
            require(value['resourceProofSha256'] is None, 'heldout ledger unexpected resource proof')
        require(type(value['measuredCorrect']) is bool if stage == 'parent_verified'
            else value['measuredCorrect'] is None, 'heldout ledger measured correctness')

    def _history(self):
        require(self.directory is not None, 'heldout ledger lock required')
        require(self._read('contract.json') == self.raw, 'heldout ledger contract drift')
        names = set(os.listdir(self.directory)) - {'lock', 'contract.json'}
        require(all(re.fullmatch(r'event-[0-9]{4}\.json', name) is not None for name in names)
            and len(names) <= 169, 'heldout ledger event inventory')
        require(names == {f'event-{i:04d}.json' for i in range(1, len(names)+1)}, 'heldout ledger journal gap')
        rows, previous = [], self.digest
        for index in range(1, len(names)+1):
            raw = self._read(f'event-{index:04d}.json')
            value = inputs.parse(raw)
            require(isinstance(value, dict) and set(value) == {'version', 'contractSha256',
                'sequence', 'previousSha256', 'ordinal', 'stage', 'artifactSha256',
                'resourceProofSha256', 'measuredCorrect', 'stopReason'}, 'heldout ledger event shape')
            require(value['version'] == VERSION and value['contractSha256'] == self.digest
                and type(value['sequence']) is int and value['sequence'] == index
                and value['previousSha256'] == previous and isinstance(value['stage'], str) and value['stage'] in {*STAGES,
                    *FAILURES.values(), 'global_stop'}, 'heldout ledger event identity')
            if value['artifactSha256'] is not None:
                io.pin(value['artifactSha256'])
            self._transition(rows, value)
            rows.append(value)
            previous = io.sha(raw)
        return rows, previous

    def append(self, ordinal, stage, artifact_sha256=None, *, resource_proof_sha256=None,
               measured_correct=None, stop_reason=None):
        """呼出し元が検査した原hashを追記する。native検査・採点の代替ではない。"""
        rows, previous = self._history()
        require(stage in {*STAGES, *FAILURES.values(), 'global_stop'}, 'heldout ledger stage')
        if artifact_sha256 is not None:
            io.pin(artifact_sha256)
        value = dict(version=VERSION, contractSha256=self.digest, sequence=len(rows)+1,
            previousSha256=previous, ordinal=ordinal, stage=stage, artifactSha256=artifact_sha256,
            resourceProofSha256=resource_proof_sha256, measuredCorrect=measured_correct, stopReason=stop_reason)
        self._transition(rows, value)
        raw = io.encoded(value)
        self._write(f'event-{len(rows)+1:04d}.json', raw)
        return dict(sequence=len(rows)+1, sha256=io.sha(raw))

    def summary(self):
        rows, _ = self._history()
        counts = {stage: sum(row['stage'] == stage for row in rows) for stage in [*STAGES, *FAILURES.values()]}
        done = sum(counts[stage] for stage in TERMINALS)
        stopped = bool(rows and rows[-1]['stage'] == 'global_stop')
        return dict(status='stopped' if stopped else 'attempts_recorded' if done == 24 else 'in_progress',
            primaryReserved=counts['primary_reserved'], primaryLaunchMarked=counts['primary_started'],
            independentReserved=counts['independent_reserved'], independentLaunchMarked=counts['independent_started'],
            parentVerified=counts['parent_verified'], correct=sum(row['measuredCorrect'] is True for row in rows),
            incorrect=sum(row['measuredCorrect'] is False for row in rows),
            evaluationFailed=counts['primary_failed']+counts['independent_failed'], terminalSlots=done,
            unattempted=24-counts['primary_reserved'], pending=counts['primary_reserved']-done,
            certifiesSkillGate=False)
