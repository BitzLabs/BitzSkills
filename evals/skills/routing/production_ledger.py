"""一次入力の固定と起動前台帳。provider接続・期待値採点・Gate認定は行わない。"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from production_trace import manifest_view, project_case, require, strict_json
import source_guard


def sha(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def pin(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None, 'SHA-256 pin required')
    return value


@dataclass(frozen=True)
class BoundInputs:
    contract_raw: bytes
    case_ids: tuple[str, ...]
    payloads: tuple[bytes, ...]
    repetitions: int
    raw_inputs: tuple[bytes, ...]

    @property
    def contract(self):
        return strict_json(self.contract_raw)

    @property
    def identity(self):
        return {'contractSha256': sha(self.contract_raw), 'payloadSha256': [sha(p) for p in self.payloads]}

    def attempt(self, ordinal):
        require(type(ordinal) is int and 1 <= ordinal <= len(self.payloads) * self.repetitions, 'attempt ordinal')
        index, repetition = divmod(ordinal - 1, self.repetitions)
        contract = self.contract
        return {'attempt': ordinal, 'caseId': self.case_ids[index], 'repetition': repetition + 1,
                'modelInputSha256': sha(self.payloads[index]), 'contractSha256': sha(self.contract_raw),
                'sourceCommit': contract['sourceCommit'], 'model': contract['model'],
                'manifestSha256': contract['inputSha256']['manifest'],
                'outputRelativePath': contract['outputRelativeRoot'] + f'/attempt-{ordinal:04d}'}


def bind_inputs(contract_raw, cases_raw, catalog_raw, manifest_raw, instructions_raw, environment_raw):
    raw_inputs = dict(cases=cases_raw, catalog=catalog_raw, manifest=manifest_raw,
                      instructions=instructions_raw, environment=environment_raw)
    require(all(isinstance(raw, bytes) for raw in [contract_raw, *raw_inputs.values()]), 'raw bytes required')
    contract = strict_json(contract_raw)
    require(isinstance(contract, dict) and contract.get('schemaVersion') == '1.0' and contract.get('phase') == 4,
            'execution contract schema')
    require(contract.get('scope') == 'public-production-routing-canary-only', 'public canary scope')
    require(contract.get('model') == 'gpt-6.1-sol', 'authorized SOL model')
    require(isinstance(contract.get('sourceCommit'), str) and re.fullmatch(r'[0-9a-f]{40}', contract['sourceCommit']), 'source ref')
    require(isinstance(contract.get('campaignId'), str) and re.fullmatch(r'[a-z0-9-]+', contract['campaignId']), 'campaign id')
    require(contract.get('certifiesBehavior') is False and contract.get('certifiesSkillGate') is False, 'canary certification scope')
    declared = contract.get('inputSha256')
    require(isinstance(declared, dict) and set(declared) == set(raw_inputs), 'input inventory')
    for name, raw in raw_inputs.items():
        require(pin(declared[name]) == sha(raw), 'fixed input drift')
    manifest, _, _ = manifest_view(manifest_raw)
    require(contract.get('candidateSource') == manifest['sourceCommit'], 'candidate source binding')
    output = contract.get('outputRelativeRoot')
    require(isinstance(output, str) and re.fullmatch(r'\.venv/production-routing-primary-[a-z0-9-]+', output), 'public output root')
    cases = strict_json(cases_raw)
    require(isinstance(cases, list) and 1 <= len(cases) <= 2, 'initial public canary size')
    ids = []
    projected = []
    for case in cases:
        require(isinstance(case, dict) and isinstance(case.get('id'), str) and case['id'].strip(), 'case id')
        ids.append(case['id'])
        projected.append(project_case(case))
    require(len(ids) == len(set(ids)), 'duplicate case id')
    catalog = strict_json(catalog_raw)
    require(isinstance(catalog, dict) and set(catalog) == {'schemaVersion', 'catalogVersion', 'events'}
            and catalog['schemaVersion'] == '1.0', 'common catalog schema')
    require(isinstance(catalog['catalogVersion'], str) and catalog['catalogVersion'].strip(), 'catalog version')
    events = catalog['events']
    require(isinstance(events, list) and all(isinstance(e, str) and e.strip() for e in events)
            and len(events) == len(set(events)), 'common events')
    instructions = instructions_raw.decode('utf-8')
    require(bool(instructions.strip()), 'common instructions')
    require(isinstance(strict_json(environment_raw), dict), 'fixed environment object')
    repetitions = contract.get('repetitions')
    require(type(repetitions) is int and 1 <= repetitions <= 2, 'finite repetitions')
    total = len(cases) * repetitions
    budget = contract.get('budget')
    require(isinstance(budget, dict) and set(budget) == {'primaryModelTrajectories', 'independentReviewerSol', 'automaticRetries', 'delegations'}, 'finite budget inventory')
    require(all(type(v) is int for v in budget.values()) and budget == dict(primaryModelTrajectories=total,
            independentReviewerSol=total, automaticRetries=0, delegations=0), 'finite budget mismatch')
    payloads = tuple(encoded({'instructions': instructions, 'eventCatalog': catalog, 'case': case}) for case in projected)
    return BoundInputs(contract_raw, tuple(ids), payloads, repetitions, tuple(raw_inputs.values()))


def safe_tree(path: Path):
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'ledger symlink')


def exclusive(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_owned(path: Path):
    safe_tree(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
            'ledger ownership or mode')
    return strict_json(path.read_bytes())


class Ledger:
    """storage引数は隔離試験用。製品接続は共通repositoryのopen_ledgerだけを使う。"""
    def __init__(self, storage: Path, bound: BoundInputs):
        require(len(bound.raw_inputs) == 5 and bound == bind_inputs(bound.contract_raw, *bound.raw_inputs), 'bound input tampering')
        self.storage, self.bound = storage, bound
        safe_tree(storage)
        try:
            storage.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = storage.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'ledger directory ownership or mode')

    def locked(self):
        safe_tree(self.storage)
        fd = os.open(self.storage / 'lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600, 'ledger lock mode')
        stream = os.fdopen(fd, 'r+b')
        fcntl.flock(stream, fcntl.LOCK_EX)
        return stream

    def initialize(self):
        path = self.storage / 'campaign.json'
        expected = dict(campaignId=self.bound.contract['campaignId'], **self.bound.identity,
                        attempts=[self.bound.attempt(i) for i in range(1, len(self.bound.payloads) * self.bound.repetitions + 1)])
        if not path.exists():
            require(set(p.name for p in self.storage.iterdir()) == {'lock'}, 'orphan ledger artifacts')
            exclusive(path, encoded(expected))
        require(read_owned(path) == expected, 'campaign or input change cannot reset ledger')

    def reservations(self):
        files = sorted(self.storage.glob('attempt-*.json'))
        expected_names = {'lock', 'campaign.json'} | {p.name for p in files}
        expected_names |= {f'review-{i:04d}.json' for i in range(1, len(files) + 1)}
        require(all(p.name in expected_names for p in self.storage.iterdir()), 'orphan ledger records')
        for i, path in enumerate(files, 1):
            require(path.name == f'attempt-{i:04d}.json' and read_owned(path) == self.bound.attempt(i), 'reservation drift or gap')
            review = self.storage / f'review-{i:04d}.json'
            require(review.is_file(), 'previous attempt awaits independent parent verification')
            self.validate_review(i, read_owned(review))
            require(read_owned(review)['status'] == 'accepted', 'previous attempt stopped')
        return len(files)

    def reserve(self):
        with self.locked():
            self.initialize()
            count = self.reservations()
            value = self.bound.attempt(count + 1)
            exclusive(self.storage / f'attempt-{count + 1:04d}.json', encoded(value))
            return value

    def validate_review(self, ordinal, review):
        require(isinstance(review, dict) and review.get('status') in {'accepted', 'stopped'}, 'review status')
        for key, value in self.bound.attempt(ordinal).items():
            require(type(review.get(key)) is type(value) and review[key] == value, 'review attempt binding')
        for name in ('independentReceiptSha256', 'parentVerificationSha256', 'nativeTraceSha256', 'nativeStderrSha256', 'decisionSha256'):
            pin(review.get(name))
        require(review.get('certifiesBehavior') is False and review.get('certifiesSkillGate') is False, 'review scope')
        require(review.get('automaticRetry') is False, 'review retry policy')
        if review['status'] == 'accepted':
            require(type(review.get('nativeExitCode')) is int and review['nativeExitCode'] == 0
                    and review.get('normalTerminal') is True and review.get('measurementIntegrityPassed') is True,
                    'successful native integrity required')
            counts = review.get('severityCounts')
            require(isinstance(counts, dict) and set(counts) == {'P1', 'P2'} and
                    all(type(v) is int and v == 0 for v in counts.values()), 'independent findings')

    def record_review(self, ordinal, review_raw: bytes):
        with self.locked():
            self.initialize()
            require(read_owned(self.storage / f'attempt-{ordinal:04d}.json') == self.bound.attempt(ordinal), 'reserved attempt required')
            review = strict_json(review_raw)
            self.validate_review(ordinal, review)
            exclusive(self.storage / f'review-{ordinal:04d}.json', review_raw)


def common_ledger_path(repository: Path):
    common = Path(source_guard.git(repository, 'rev-parse', '--git-common-dir').decode().strip())
    if not common.is_absolute():
        common = repository / common
    safe_tree(common)
    common = common.resolve(strict=True)
    require(common.name == '.git', 'shared non-bare repository required')
    return common.parent / '.venv' / 'production-routing-primary-ledger'


def open_ledger(repository: Path, bound: BoundInputs):
    # 全worktreeで共通の場所。出力先・campaign変更を台帳の切替に使わない。
    return Ledger(common_ledger_path(repository), bound)
