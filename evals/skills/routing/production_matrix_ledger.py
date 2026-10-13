"""公開92枠の台帳部品。実provider取得器・独立採点器への接続は未実装。

ここに渡す完了証明は親検分結果であり、台帳がnative軌跡を採点した証拠ではない。
製品用の起動入口は公開しない。MatrixLedgerのstorage引数は隔離試験用。
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re
import stat

import production_ledger as io
import production_matrix_inputs as inputs
from production_trace import require, strict_json, json_equal


VERSION = 'public-production-matrix-ledger-0.1.1'
PINS = {'snapshotManifest', 'runtimeManifest', 'calibrationManifest', 'prelaunchReview', 'sdk', 'cli',
        'contextProfile', 'decisionSchema'}
STAGES = ('attempt', 'started', 'primary', 'independent', 'review')


def present(path):
    """dangling symlinkも提出済み。読取り時にNOFOLLOWで拒否する。"""
    return os.path.lexists(path)


@dataclass(frozen=True)
class BoundExecution:
    execution_raw: bytes
    matrix: inputs.MatrixInputs
    raw_inputs: tuple[bytes, ...]

    @property
    def contract(self):
        return strict_json(self.execution_raw)

    def slot(self, ordinal):
        c = self.contract
        return dict(self.matrix.slot(ordinal), campaignId=c['campaignId'], sourceCommit=c['sourceCommit'],
                    executionSha256=io.sha(self.execution_raw))


def execution_contract(execution_raw):
    """子process向けの有限実行policy。全入力のGit一致・起動許可は別検査。"""
    require(isinstance(execution_raw, bytes), 'matrix execution bytes required')
    c = strict_json(execution_raw)
    require(isinstance(c, dict) and set(c) == {'version', 'campaignId', 'sourceCommit', 'model',
            'inputContractSha256', 'outputRelativeRoot', 'pins', 'budget', 'timeoutSeconds',
            'cliVersion', 'certifiesSkillGate'}, 'matrix execution inventory')
    require(c['version'] == VERSION and isinstance(c['campaignId'], str)
            and re.fullmatch(r'public-matrix-[a-z0-9]+(?:-[a-z0-9]+)*', c['campaignId']) is not None,
            'matrix campaign identity')
    require(isinstance(c['sourceCommit'], str) and re.fullmatch(r'[0-9a-f]{40}', c['sourceCommit']) is not None
            and c['model'] == 'gpt-6.1-sol' and c['cliVersion'] == '0.160.1'
            and c['certifiesSkillGate'] is False, 'matrix source and input binding')
    require(isinstance(c['outputRelativeRoot'], str)
            and re.fullmatch(r'\.venv/[a-z0-9]+(?:-[a-z0-9]+)*', c['outputRelativeRoot']) is not None,
            'matrix output boundary')
    require(isinstance(c['pins'], dict) and set(c['pins']) == PINS, 'matrix runtime pin inventory')
    for value in c['pins'].values():
        io.pin(value)
    require(json_equal(c['budget'], dict(primary=92, independent=92, automaticRetries=0, delegations=0)),
            'matrix execution limits')
    require(isinstance(c['timeoutSeconds'], dict) and set(c['timeoutSeconds']) == {'primary', 'independent'}
            and all(type(v) is int and 1 <= v <= 600 for v in c['timeoutSeconds'].values()),
            'matrix finite timeouts')
    io.pin(c['inputContractSha256'])
    return c


def bind(execution_raw, input_contract_raw, **raw_inputs):
    matrix = inputs.bind(input_contract_raw, **raw_inputs)
    c = execution_contract(execution_raw)
    require(c['sourceCommit'] == strict_json(input_contract_raw)['sourceCommit']
            and c['inputContractSha256'] == io.sha(input_contract_raw), 'matrix source and input binding')
    return BoundExecution(execution_raw, matrix, tuple(raw_inputs[name] for name in inputs.INPUT_NAMES))


def shared_storage(repository: Path, bound: BoundExecution):
    """既存Git共通領域の解決を再利用する。保存・起動はしない。"""
    require(bound == bind(bound.execution_raw, bound.matrix.contract_raw,
                         **dict(zip(inputs.INPUT_NAMES, bound.raw_inputs))), 'matrix bound bytes drift')
    return io.common_ledger_path(repository).parent / 'production-matrix-ledgers' / bound.contract['campaignId']


class MatrixLedger:
    def __init__(self, storage: Path, repository: Path, bound: BoundExecution):
        require('..' not in storage.parts and '..' not in repository.parts, 'matrix repository path escape')
        require(bound == bind(bound.execution_raw, bound.matrix.contract_raw,
                             **dict(zip(inputs.INPUT_NAMES, bound.raw_inputs))), 'matrix bound bytes drift')
        self.storage, self.repository, self.bound = storage.absolute(), repository.absolute(), bound
        self._slots = tuple(bound.slot(n) for n in range(1, 93))
        require(self.storage.is_relative_to(self.repository / '.venv'), 'matrix storage outside repository')
        self.output = self.repository / bound.contract['outputRelativeRoot']
        require(not self.storage.is_relative_to(self.output) and not self.output.is_relative_to(self.storage),
                'matrix output and storage overlap')
        io.safe_tree(self.repository)
        io.safe_tree(self.storage)
        self.storage.mkdir(mode=0o700, exist_ok=True)
        info = self.storage.stat()
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, 'matrix directory mode')
        io.sync_directory(self.storage.parent)

    @contextmanager
    def locked(self):
        io.safe_tree(self.storage)
        fd = os.open(self.storage / 'lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'r+b') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) == 0o600, 'matrix lock mode')
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('matrix campaign already running') from error
            yield

    def initialize(self):
        expected = dict(version=VERSION, contractSha256=io.sha(self.bound.execution_raw),
                        slots=list(self._slots))
        path = self.storage / 'campaign.json'
        try:
            if not present(path):
                require({p.name for p in self.storage.iterdir()} == {'lock'}, 'orphan matrix ledger')
                io.exclusive(path, io.encoded(expected))
            require(json_equal(io.read_owned(path), expected), 'matrix campaign drift cannot reset consumption')
        except Exception as error:
            self.stop(None, 'stored-campaign-rejected', type(error).__name__)
            raise

    def path(self, stage, ordinal):
        self.slot(ordinal)
        require(stage in STAGES, 'matrix stage')
        return self.storage / f'{stage}-{ordinal:04d}.json'

    def slot(self, ordinal):
        require(type(ordinal) is int and 1 <= ordinal <= 92, 'matrix ordinal')
        return dict(self._slots[ordinal-1])

    def read(self, stage, ordinal):
        return io.read_owned(self.path(stage, ordinal))

    def stop(self, ordinal, reason, error_type):
        path = self.storage / 'stop.json'
        if not present(path):
            io.exclusive(path, io.encoded(dict(status='stopped', ordinal=ordinal, reason=reason,
                errorType=error_type, executionSha256=io.sha(self.bound.execution_raw), automaticRetries=0)))

    def reject_submission(self, ordinal, phase, raw, error):
        """不正な提出bytesも保持する。保存失敗でも恒久停止を省略しない。"""
        try:
            if isinstance(raw, bytes):
                io.exclusive(self.storage / f'rejected-{phase}-{ordinal:04d}.bin', raw)
        finally:
            self.stop(ordinal, 'submitted-'+phase+'-rejected', type(error).__name__)

    def identity(self, value, ordinal, keys):
        slot = self.slot(ordinal)
        require(isinstance(value, dict) and set(value) == set(slot) | set(keys), 'matrix record inventory')
        require(json_equal({k: value[k] for k in slot}, slot), 'matrix record identity')

    def original(self, reference, ordinal):
        require(isinstance(reference, dict) and set(reference) == {'relativePath', 'sha256'},
                'matrix original reference')
        relative = reference['relativePath']
        require(isinstance(relative, str) and re.fullmatch(r'[a-zA-Z0-9./_-]+', relative) is not None,
                'matrix original name')
        path = Path(relative)
        prefix = Path(self.bound.contract['outputRelativeRoot']) / f'attempt-{ordinal:04d}'
        require(relative == path.as_posix() and not path.is_absolute() and path.parent == prefix
                and not set(path.parts) & {'..', 'state', 'logs', 'auth.json', '.env', '.git', 'codex-home'}
                and path.name in {'receipt.json', 'rpc-out.jsonl', 'independent-receipt.json', 'parent-verification.json'},
                'matrix original boundary')
        require(io.sha(io.read_regular(self.repository / path)) == io.pin(reference['sha256']),
                'matrix original hash drift')

    def primary_valid(self, value, ordinal):
        self.identity(value, ordinal, {'actualInvocations', 'normalTerminal', 'nativeExitCode',
                                      'integrityPassed', 'receipt', 'trace'})
        require(type(value['actualInvocations']) is int and value['actualInvocations'] == 1
                and type(value['nativeExitCode']) is int and value['nativeExitCode'] == 0
                and value['normalTerminal'] is True and value['integrityPassed'] is True,
                'matrix primary incomplete or unsafe')
        self.original(value['receipt'], ordinal)
        self.original(value['trace'], ordinal)
        require(Path(value['receipt']['relativePath']).name == 'receipt.json'
                and Path(value['trace']['relativePath']).name == 'rpc-out.jsonl', 'matrix primary original roles')

    def independent_valid(self, value, ordinal):
        self.identity(value, ordinal, {'reviewInputSha256', 'model', 'maximumInvocations', 'consumedReservations'})
        io.pin(value['reviewInputSha256'])
        require(value['model'] == 'gpt-6.1-sol' and type(value['maximumInvocations']) is int
                and value['maximumInvocations'] == 1 and type(value['consumedReservations']) is int
                and value['consumedReservations'] == 1, 'matrix independent budget')

    def review_valid(self, value, ordinal):
        self.identity(value, ordinal, {'status', 'accuracy', 'safetyPassed', 'integrityPassed',
                'independentContext', 'severityCounts', 'primaryRecordSha256', 'independentReservationSha256',
                'independentReceipt', 'parentVerification', 'certifiesSkillGate'})
        require(type(value['accuracy']) is bool and value['status'] == ('measured_correct' if value['accuracy']
                else 'measured_incorrect') and value['safetyPassed'] is True and value['integrityPassed'] is True
                and value['independentContext'] is True and value['certifiesSkillGate'] is False
                and json_equal(value['severityCounts'], {'P1': 0, 'P2': 0}), 'matrix review unsafe or incomplete')
        for key, stage in [('primaryRecordSha256', 'primary'), ('independentReservationSha256', 'independent')]:
            require(value[key] == io.sha(io.read_regular(self.path(stage, ordinal))), 'matrix review reservation drift')
        self.original(value['independentReceipt'], ordinal)
        self.original(value['parentVerification'], ordinal)
        require(Path(value['independentReceipt']['relativePath']).name == 'independent-receipt.json'
                and Path(value['parentVerification']['relativePath']).name == 'parent-verification.json',
                'matrix independent original roles')

    def checked_count(self):
        require(not present(self.storage / 'stop.json'), 'matrix campaign permanently stopped')
        ordinal = None
        try:
            files = {p.name for p in self.storage.iterdir()}
            allowed = {'lock', 'campaign.json'} | {f'{stage}-{n:04d}.json' for stage in STAGES for n in range(1, 93)}
            require(files <= allowed, 'unknown matrix ledger record')
            count = sum(name.startswith('attempt-') for name in files)
            require({f'attempt-{n:04d}.json' for n in range(1, count+1)} <= files, 'matrix reservation gap')
            for ordinal in range(1, 93):
                if ordinal > count:
                    require(not any(present(self.path(stage, ordinal)) for stage in STAGES[1:]), 'unreserved matrix stage')
                    continue
                require(json_equal(self.read('attempt', ordinal), self.slot(ordinal)), 'matrix attempt drift')
                previous = True
                for stage in STAGES[1:]:
                    path = self.path(stage, ordinal)
                    submitted = present(path)
                    require(not submitted or previous, 'matrix stage gap')
                    if submitted:
                        value = self.read(stage, ordinal)
                        if stage == 'started':require(json_equal(value, self.slot(ordinal)), 'matrix start drift')
                        elif stage == 'primary':self.primary_valid(value, ordinal)
                        elif stage == 'independent':self.independent_valid(value, ordinal)
                        else:self.review_valid(value, ordinal)
                    previous = submitted
                require(ordinal == count or present(self.path('review', ordinal)), 'matrix unfinished preceding slot')
            return count
        except Exception as error:
            self.stop(ordinal, 'stored-evidence-rejected', type(error).__name__)
            raise

    def reserve(self, ordinal):
        with self.locked():
            self.initialize()
            count = self.checked_count()
            require(type(ordinal) is int and ordinal == count+1 and ordinal <= 92, 'matrix fixed order or limit')
            require(count == 0 or present(self.path('review', count)), 'matrix previous review pending')
            value = self.slot(ordinal)
            io.exclusive(self.path('attempt', ordinal), io.encoded(value))
            return value

    def latest_pending(self, ordinal):
        require(type(ordinal) is int and ordinal == self.checked_count() and ordinal > 0,
                'matrix only latest reserved slot')
        require(not present(self.path('review', ordinal)), 'matrix slot already measured')

    def mark_primary_started(self, ordinal):
        with self.locked():
            self.initialize()
            self.latest_pending(ordinal)
            io.exclusive(self.path('started', ordinal), io.encoded(self.slot(ordinal)))

    def record_primary(self, ordinal, value):
        with self.locked():
            self.initialize()
            self.latest_pending(ordinal)
            require(present(self.path('started', ordinal)), 'matrix primary launch not marked')
            require(not present(self.path('primary', ordinal)), 'matrix primary already recorded')
            try:
                self.primary_valid(value, ordinal)
            except Exception as error:
                self.stop(ordinal, 'submitted-primary-rejected', type(error).__name__)
                raise
            io.exclusive(self.path('primary', ordinal), io.encoded(value))

    def reserve_independent(self, ordinal, review_input_sha256):
        with self.locked():
            self.initialize()
            self.latest_pending(ordinal)
            require(present(self.path('primary', ordinal)), 'matrix primary evidence pending')
            value = dict(self.slot(ordinal), reviewInputSha256=io.pin(review_input_sha256),
                         model='gpt-6.1-sol', maximumInvocations=1, consumedReservations=1)
            io.exclusive(self.path('independent', ordinal), io.encoded(value))
            return value

    def record_review(self, ordinal, review_raw):
        with self.locked():
            self.initialize()
            self.latest_pending(ordinal)
            require(present(self.path('independent', ordinal)), 'matrix independent reservation pending')
            try:
                value = strict_json(review_raw)
                self.review_valid(value, ordinal)
            except Exception as error:
                self.reject_submission(ordinal, 'review', review_raw, error)
                raise
            io.exclusive(self.path('review', ordinal), review_raw)

    def record_interruption(self, ordinal, phase):
        with self.locked():
            self.initialize()
            self.latest_pending(ordinal)
            require(phase in {'primary', 'independent'}, 'matrix interrupted phase')
            require(present(self.path('started' if phase == 'primary' else 'independent', ordinal)),
                    'matrix interruption requires consumed launch or reservation')
            self.stop(ordinal, phase+'-interrupted', 'Interrupted')

    def summary(self):
        """停止時も予約と完了を区別する。破損記録を成功や誤選択へ数えない。"""
        with self.locked():
            self.initialize()
            stopped = present(self.storage / 'stop.json')
            if not stopped:self.checked_count()
            counts = {stage: 0 for stage in STAGES}
            correct = incorrect = 0
            for ordinal in range(1, 93):
                for stage in STAGES:
                    path = self.path(stage, ordinal)
                    if not present(path):continue
                    value = self.read(stage, ordinal)
                    if stage in {'attempt', 'started'}:require(json_equal(value, self.slot(ordinal)), 'summary identity')
                    elif stage == 'primary':self.primary_valid(value, ordinal)
                    elif stage == 'independent':self.independent_valid(value, ordinal)
                    else:
                        self.review_valid(value, ordinal)
                        correct += value['accuracy'] is True
                        incorrect += value['accuracy'] is False
                    counts[stage] += 1
            return dict(status='stopped' if stopped else 'complete' if counts['review'] == 92 else 'in_progress',
                maximumPrimary=92, primaryReserved=counts['attempt'], primaryLaunchMarked=counts['started'],
                primaryCompleted=counts['primary'], independentReserved=counts['independent'],
                parentVerified=counts['review'], measuredCorrect=correct, measuredIncorrect=incorrect,
                missingMeasurements=92-counts['review'], certifiesSkillGate=False)
