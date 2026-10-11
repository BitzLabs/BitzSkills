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
from types import SimpleNamespace

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


def bind_initial_canary_inputs(contract_raw, cases_raw, catalog_raw, manifest_raw, instructions_raw, environment_raw):
    """初回案の2件×2反復・一次4/独立4を汎用束縛の後に要求する。"""
    bound = bind_inputs(contract_raw, cases_raw, catalog_raw, manifest_raw, instructions_raw, environment_raw)
    require(len(bound.case_ids) == 2 and bound.repetitions == 2 and
            bound.contract['budget']['primaryModelTrajectories'] == 4 and
            bound.contract['budget']['independentReviewerSol'] == 4, 'initial canary requires two cases and two repetitions')
    return bound


def exclusive(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    sync_directory(path.parent)


def sync_directory(path: Path):
    safe_tree(path)
    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_regular(path: Path, *, owned=False):
    """親ディレクトリもopenat/NOFOLLOWで辿り、regularな原ファイルだけを読む。"""
    require(path.is_absolute(), 'absolute trusted artifact root required')
    parts = path.parts[1:]
    require(bool(parts) and all(p not in {'.', '..', ''} for p in parts), 'original path segments')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in parts[:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(child)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'regular single-link artifact required')
            if owned:
                require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                        'ledger ownership or mode')
        except BaseException:
            os.close(child)
            raise
        with os.fdopen(child, 'rb') as stream:
            return stream.read()
    finally:
        os.close(fd)


def read_owned(path: Path):
    safe_tree(path)
    return strict_json(read_regular(path.absolute(), owned=True))


class Ledger:
    """storage引数は隔離試験用。製品接続は共通repositoryのopen_ledgerだけを使う。"""
    def __init__(self, storage: Path, bound: BoundInputs, *, require_independent_reviews=False):
        require(len(bound.raw_inputs) == 5 and bound == bind_inputs(bound.contract_raw, *bound.raw_inputs), 'bound input tampering')
        require(type(require_independent_reviews) is bool, 'review reservation mode')
        self.require_independent_reviews = require_independent_reviews
        self.storage, self.bound = storage, bound
        safe_tree(storage)
        try:
            storage.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = storage.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'ledger directory ownership or mode')
        # 初回mkdirの名前も同期する。同時初期化で既存となった経路も同期する。
        sync_directory(storage.parent)

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
                        reviewReservationRequired=self.require_independent_reviews,
                        attempts=[self.bound.attempt(i) for i in range(1, len(self.bound.payloads) * self.bound.repetitions + 1)])
        if not path.exists():
            require(set(p.name for p in self.storage.iterdir()) == {'lock'}, 'orphan ledger artifacts')
            exclusive(path, encoded(expected))
        require(read_owned(path) == expected, 'campaign or input change cannot reset ledger')

    def reservations(self, *, allow_pending_last=False):
        files = sorted(self.storage.glob('attempt-*.json'))
        expected_names = {'lock', 'campaign.json'} | {p.name for p in files}
        expected_names |= {f'review-{i:04d}.json' for i in range(1, len(files) + 1)}
        expected_names |= {f'independent-{i:04d}.json' for i in range(1, len(files) + 1)}
        expected_names |= {f'stop-{i:04d}.json' for i in range(1,len(files)+1)}
        require(all(p.name in expected_names for p in self.storage.iterdir()), 'orphan ledger records')
        for i, path in enumerate(files, 1):
            require(path.name == f'attempt-{i:04d}.json' and read_owned(path) == self.bound.attempt(i), 'reservation drift or gap')
            stop=self.storage/f'stop-{i:04d}.json'
            if stop.exists():
                stopped=read_owned(stop)
                if stopped.get('status')=='stopped_independent_verification':self.validate_independent_stop(i,stopped)
                else:self.validate_primary_stop(i,stopped)
                require(False,'primary stopped before independent review')
            review = self.storage / f'review-{i:04d}.json'
            independent = self.storage / f'independent-{i:04d}.json'
            if independent.exists():
                self.validate_independent_reservation(i, read_owned(independent))
            if allow_pending_last and i == len(files) and not review.exists():
                return len(files)
            require(review.is_file(), 'previous attempt awaits independent parent verification')
            value = read_owned(review)
            self.validate_review(i, value)
            if self.require_independent_reviews or 'independentReservationSha256' in value:
                self.validate_review_reservation(i, value)
            require(value['status'] == 'accepted', 'previous attempt stopped')
        return len(files)

    def validate_primary_stop(self,ordinal,value):
        require(isinstance(value,dict) and set(value)==set(self.bound.attempt(ordinal))|{
            'status','reason','primaryReceiptSha256','independentInvocations','automaticRetry'},'primary stop fields')
        for key,expected in self.bound.attempt(ordinal).items():
            require(type(value[key]) is type(expected) and value[key]==expected,'primary stop attempt binding')
        require(value['status']=='stopped_before_independent_review' and value['reason'] in {
            'primary-capture-failed','primary-receipt-missing','primary-structure-rejected'} and
            type(value['independentInvocations']) is int and value['independentInvocations']==0 and
            value['automaticRetry'] is False,'primary stop finite scope')
        if value['reason']=='primary-receipt-missing':require(value['primaryReceiptSha256'] is None,'missing primary receipt hash')
        else:pin(value['primaryReceiptSha256'])

    def record_primary_stop(self,ordinal,reason,receipt_sha256):
        """取得・構造検査の失敗を記録する。独立採点を実施したことにしない。"""
        with self.locked():
            self.initialize()
            require(ordinal==self.reservations(allow_pending_last=True),'only latest pending primary may stop')
            require(not (self.storage/f'independent-{ordinal:04d}.json').exists() and
                not (self.storage/f'review-{ordinal:04d}.json').exists(),'independent already reserved or finalized')
            value=dict(**self.bound.attempt(ordinal),status='stopped_before_independent_review',reason=reason,
                primaryReceiptSha256=receipt_sha256,independentInvocations=0,automaticRetry=False)
            self.validate_primary_stop(ordinal,value)
            exclusive(self.storage/f'stop-{ordinal:04d}.json',encoded(value))
            return value

    def validate_independent_stop(self,ordinal,value):
        require(isinstance(value,dict) and set(value)==set(self.bound.attempt(ordinal))|{
            'status','reason','primaryReceiptSha256','independentReceiptSha256','independentReservationSha256',
            'reviewInputSha256','consumedIndependentReservations','actualIndependentInvocations','automaticRetry'},'independent stop fields')
        for key,expected in self.bound.attempt(ordinal).items():
            require(type(value[key]) is type(expected) and value[key]==expected,'independent stop attempt binding')
        require(value['status']=='stopped_independent_verification' and value['reason'] in {
            'independent-originals-rejected','independent-execution-incomplete'} and
            type(value['consumedIndependentReservations']) is int and value['consumedIndependentReservations']==1 and
            (value['actualIndependentInvocations'] is None or type(value['actualIndependentInvocations']) is int and value['actualIndependentInvocations'] in {0,1}) and
            value['automaticRetry'] is False,'independent stop finite scope')
        for key in ['primaryReceiptSha256','independentReceiptSha256']:
            if value[key] is not None:pin(value[key])
        path=self.storage/f'independent-{ordinal:04d}.json'
        independent=read_owned(path);self.validate_independent_reservation(ordinal,independent)
        require(value['independentReservationSha256']==sha(read_regular(path)) and value['reviewInputSha256']==independent['reviewInputSha256'], 'independent stop shared reservation')

    def record_independent_stop(self,ordinal,reason,primary_receipt_sha256,independent_receipt_sha256,actual_invocations=None):
        """採点実行・親原照合の不適合を恒久停止する。欠測使用量を0へ置換しない。"""
        with self.locked():
            self.initialize()
            require(ordinal==self.reservations(allow_pending_last=True),'only latest pending independent may stop')
            require(not (self.storage/f'review-{ordinal:04d}.json').exists(),'independent already finalized')
            path=self.storage/f'independent-{ordinal:04d}.json'
            independent=read_owned(path);self.validate_independent_reservation(ordinal,independent)
            value=dict(**self.bound.attempt(ordinal),status='stopped_independent_verification',reason=reason,
                primaryReceiptSha256=primary_receipt_sha256,independentReceiptSha256=independent_receipt_sha256,
                independentReservationSha256=sha(read_regular(path)),reviewInputSha256=independent['reviewInputSha256'],
                consumedIndependentReservations=1,actualIndependentInvocations=actual_invocations,automaticRetry=False)
            self.validate_independent_stop(ordinal,value)
            exclusive(self.storage/f'stop-{ordinal:04d}.json',encoded(value))
            return value

    def validate_independent_reservation(self, ordinal, value):
        require(isinstance(value, dict) and set(value) == set(self.bound.attempt(ordinal)) | {
            'reviewModel', 'reviewInputSha256', 'maximumInvocations', 'consumedReservations', 'automaticRetry'},
            'independent reservation fields')
        for key, expected in self.bound.attempt(ordinal).items():
            require(type(value[key]) is type(expected) and value[key] == expected, 'independent attempt binding')
        require(value['reviewModel'] == 'gpt-6.1-sol' and value['automaticRetry'] is False and
                type(value['maximumInvocations']) is int and value['maximumInvocations'] == 1 and
                type(value['consumedReservations']) is int and value['consumedReservations'] == 1, 'finite independent reservation')
        pin(value['reviewInputSha256'])

    def validate_review_reservation(self, ordinal, review):
        path = self.storage / f'independent-{ordinal:04d}.json'
        independent = read_owned(path)
        self.validate_independent_reservation(ordinal, independent)
        require(review.get('independentReservationSha256') == sha(path.read_bytes()) and
                review.get('reviewInputSha256') == independent['reviewInputSha256'], 'verified review reservation binding')

    def reserve_independent_review(self, ordinal, review_input_sha256):
        """親が原一次出力を照合した後、独立検分入力を起動前に固定する。"""
        with self.locked():
            self.initialize()
            require(ordinal == self.reservations(allow_pending_last=True), 'only latest pending attempt can reserve review')
            attempt = self.bound.attempt(ordinal)
            require(not (self.storage / f'review-{ordinal:04d}.json').exists(), 'attempt already finalized')
            value = dict(**attempt, reviewModel='gpt-6.1-sol', reviewInputSha256=pin(review_input_sha256),
                         maximumInvocations=1, consumedReservations=1, automaticRetry=False)
            self.validate_independent_reservation(ordinal, value)
            exclusive(self.storage / f'independent-{ordinal:04d}.json', encoded(value))
            return value

    def record_verified_review(self, ordinal, review_raw: bytes):
        """製品接続用。原証拠を親で照合済みの結果と独立予約を束縛して記録する。"""
        with self.locked():
            self.initialize()
            require(ordinal == self.reservations(allow_pending_last=True), 'only latest pending attempt can be finalized')
            attempt = self.bound.attempt(ordinal)
            require(read_owned(self.storage / f'attempt-{ordinal:04d}.json') == attempt, 'reserved attempt required')
            independent_path = self.storage / f'independent-{ordinal:04d}.json'
            independent = read_owned(independent_path)
            self.validate_independent_reservation(ordinal, independent)
            review = strict_json(review_raw)
            self.validate_review(ordinal, review)
            self.validate_review_reservation(ordinal, review)
            exclusive(self.storage / f'review-{ordinal:04d}.json', review_raw)

    def reserve(self, *, expected_ordinal=None):
        with self.locked():
            self.initialize()
            count = self.reservations()
            if expected_ordinal is not None:
                require(type(expected_ordinal) is int and expected_ordinal==count+1,
                        'next reservation changed before acquisition')
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
        require(not self.require_independent_reviews, 'synthetic review entry is disabled in production ledger')
        with self.locked():
            self.initialize()
            require(read_owned(self.storage / f'attempt-{ordinal:04d}.json') == self.bound.attempt(ordinal), 'reserved attempt required')
            review = strict_json(review_raw)
            self.validate_review(ordinal, review)
            exclusive(self.storage / f'review-{ordinal:04d}.json', review_raw)


INITIAL_CAMPAIGN='public-initial-canary'
SCHEMA_CAMPAIGN='public-schema-projection-01'
STRUCTURE_CAMPAIGN='public-code-mode-structure-01'
REASONING_CAMPAIGN='public-empty-reasoning-01'
CLOCK_CAMPAIGN='public-rollout-clock-01'
REASONING_RECEIPT='skills-integration-worktree/.venv/development-review-20261011/.venv/production-routing-primary-empty-reasoning-01/attempt-0002/receipt.json'
STRUCTURE_RECEIPT='skills-integration-worktree/.venv/development-review-20261011/.venv/production-routing-primary-code-mode-structure-01/attempt-0003/receipt.json'
SCHEMA_RECEIPT='skills-integration-worktree/.venv/development-review-20261011/.venv/production-routing-primary-schema-projection-01/attempt-0001/receipt.json'
INITIAL_RECEIPT='skills-integration-worktree/.venv/development-review-20261011/.venv/production-routing-primary-public-initial/attempt-0001/receipt.json'


def common_ledger_path(repository: Path, campaign_id=None):
    common = Path(source_guard.git(repository, 'rev-parse', '--git-common-dir').decode().strip())
    if not common.is_absolute():
        common = repository / common
    safe_tree(common)
    common = common.resolve(strict=True)
    require(common.name == '.git', 'shared non-bare repository required')
    name={SCHEMA_CAMPAIGN:'production-routing-primary-ledger-schema-projection-01',
          STRUCTURE_CAMPAIGN:'production-routing-primary-ledger-code-mode-structure-01',
          REASONING_CAMPAIGN:'production-routing-primary-ledger-empty-reasoning-01',
          CLOCK_CAMPAIGN:'production-routing-primary-ledger-rollout-clock-01'}.get(campaign_id,'production-routing-primary-ledger')
    return common.parent / '.venv' / name


def verify_predecessor(repository,contract):
    """明示した是正後の有限測定を、全先行停止の不変hashへ束縛する。旧台帳は読取りのみ。"""
    if contract.get('campaignId')==CLOCK_CAMPAIGN:
        first=verify_predecessor(repository,dict(contract,campaignId=REASONING_CAMPAIGN))
        prior=contract.get('stoppedClockPredecessor')
        require(isinstance(prior,dict) and set(prior)=={'campaignId','sourceCommit','ledgerSha256','primaryReceiptSha256','primaryReservationsConsumed','independentReservationsConsumed'} and
                prior['campaignId']==REASONING_CAMPAIGN and isinstance(prior['sourceCommit'],str) and re.fullmatch(r'[0-9a-f]{40}',prior['sourceCommit']) and
                type(prior['primaryReservationsConsumed']) is int and prior['primaryReservationsConsumed']==2 and
                type(prior['independentReservationsConsumed']) is int and prior['independentReservationsConsumed']==1,'stopped clock predecessor fields')
        names={'campaign.json','attempt-0001.json','attempt-0002.json','independent-0001.json','review-0001.json','stop-0002.json'}
        pins=prior['ledgerSha256'];require(isinstance(pins,dict) and set(pins)==names,'stopped clock hash inventory')
        storage=common_ledger_path(repository,REASONING_CAMPAIGN)
        require(set(p.name for p in storage.iterdir())=={'lock',*names},'stopped clock ledger inventory')
        values={}
        for name in sorted(names):
            raw=read_regular(storage/name);require(sha(raw)==pin(pins[name]),'original clock stopped ledger drift');values[name]=read_owned(storage/name)
        campaign=values['campaign.json'];attempts=campaign.get('attempts')
        require(campaign.get('campaignId')==REASONING_CAMPAIGN and campaign.get('reviewReservationRequired') is True and
                isinstance(attempts,list) and len(attempts)==4,'original clock campaign binding')
        pin(campaign['contractSha256'])
        for ordinal,attempt in enumerate(attempts,1):
            require(isinstance(attempt,dict) and type(attempt.get('attempt')) is int and attempt['attempt']==ordinal and
                    attempt.get('sourceCommit')==prior['sourceCommit'] and attempt.get('contractSha256')==campaign['contractSha256'],
                    'original clock ordered attempt binding')
            if ordinal<=2:require(values[f'attempt-{ordinal:04d}.json']==attempt,'original clock reserved attempt drift')
        previous=Ledger.__new__(Ledger);previous.storage=storage;previous.bound=SimpleNamespace(attempt=lambda n:attempts[n-1]);previous.require_independent_reviews=True
        accepted=values['review-0001.json'];previous.validate_review(1,accepted);previous.validate_review_reservation(1,accepted)
        require(accepted['status']=='accepted','original clock preceding review not accepted')
        stop=values['stop-0002.json'];previous.validate_primary_stop(2,stop)
        require(stop['reason']=='primary-structure-rejected' and stop['primaryReceiptSha256']==pin(prior['primaryReceiptSha256']),
                'original clock second stop binding')
        raw=read_regular(storage.parent/REASONING_RECEIPT);receipt=strict_json(raw)
        require(sha(raw)==prior['primaryReceiptSha256'] and receipt.get('status')=='primary_capture_awaits_parent_and_independent_review' and
                receipt.get('sourceCommit')==prior['sourceCommit'] and receipt.get('attempt')==attempts[1],'original stopped clock receipt drift')
        return dict(status='four_original_stopped_campaigns_preserved',predecessors=[first,dict(campaignId=REASONING_CAMPAIGN,
            primaryReservationsConsumed=2,independentReservationsConsumed=1,acceptedPrimary=1,stoppedPrimary=1,primaryReceiptSha256=sha(raw))],
            primaryReservationsConsumed=7,independentReservationsConsumed=3,automaticRetry=False)
    if contract.get('campaignId')==REASONING_CAMPAIGN:
        first=verify_predecessor(repository,dict(contract,campaignId=STRUCTURE_CAMPAIGN))
        prior=contract.get('stoppedReasoningPredecessor')
        require(isinstance(prior,dict) and set(prior)=={'campaignId','sourceCommit','ledgerSha256','primaryReceiptSha256','primaryReservationsConsumed','independentReservationsConsumed'} and
                prior['campaignId']==STRUCTURE_CAMPAIGN and isinstance(prior['sourceCommit'],str) and re.fullmatch(r'[0-9a-f]{40}',prior['sourceCommit']) and
                type(prior['primaryReservationsConsumed']) is int and prior['primaryReservationsConsumed']==3 and
                type(prior['independentReservationsConsumed']) is int and prior['independentReservationsConsumed']==2,'stopped reasoning predecessor fields')
        names={'campaign.json','attempt-0001.json','attempt-0002.json','attempt-0003.json',
               'independent-0001.json','independent-0002.json','review-0001.json','review-0002.json','stop-0003.json'}
        pins=prior['ledgerSha256'];require(isinstance(pins,dict) and set(pins)==names,'stopped reasoning hash inventory')
        storage=common_ledger_path(repository,STRUCTURE_CAMPAIGN)
        require(set(p.name for p in storage.iterdir())=={'lock',*names},'stopped reasoning ledger inventory')
        values={}
        for name in sorted(names):
            raw=read_regular(storage/name);require(sha(raw)==pin(pins[name]),'original reasoning stopped ledger drift');values[name]=read_owned(storage/name)
        campaign=values['campaign.json'];attempts=campaign.get('attempts')
        require(campaign.get('campaignId')==STRUCTURE_CAMPAIGN and campaign.get('reviewReservationRequired') is True and
                isinstance(attempts,list) and len(attempts)==4,'original reasoning campaign binding')
        pin(campaign['contractSha256'])
        for ordinal,attempt in enumerate(attempts,1):
            require(isinstance(attempt,dict) and type(attempt.get('attempt')) is int and attempt['attempt']==ordinal and
                    attempt.get('sourceCommit')==prior['sourceCommit'] and attempt.get('contractSha256')==campaign['contractSha256'],
                    'original reasoning ordered attempt binding')
            if ordinal<=3:require(values[f'attempt-{ordinal:04d}.json']==attempt,'original reasoning reserved attempt drift')
        # 原記録の厳密な型/予約束縛を検査する読取り専用context。予約・確定を呼ばない。
        previous=Ledger.__new__(Ledger);previous.storage=storage;previous.bound=SimpleNamespace(attempt=lambda n:attempts[n-1]);previous.require_independent_reviews=True
        for ordinal in [1,2]:
            accepted=values[f'review-{ordinal:04d}.json'];previous.validate_review(ordinal,accepted)
            previous.validate_review_reservation(ordinal,accepted)
            require(accepted['status']=='accepted','original reasoning preceding review not accepted')
        stop=values['stop-0003.json'];previous.validate_primary_stop(3,stop)
        require(stop['reason']=='primary-structure-rejected' and stop['primaryReceiptSha256']==pin(prior['primaryReceiptSha256']),
                'original reasoning third stop binding')
        raw=read_regular(storage.parent/STRUCTURE_RECEIPT);receipt=strict_json(raw)
        require(sha(raw)==prior['primaryReceiptSha256'] and receipt.get('status')=='primary_capture_awaits_parent_and_independent_review' and
                receipt.get('sourceCommit')==prior['sourceCommit'] and receipt.get('attempt')==attempts[2],'original stopped reasoning receipt drift')
        return dict(status='three_original_stopped_campaigns_preserved',predecessors=[first,dict(campaignId=STRUCTURE_CAMPAIGN,
            primaryReservationsConsumed=3,independentReservationsConsumed=2,acceptedPrimary=2,stoppedPrimary=1,primaryReceiptSha256=sha(raw))],
            primaryReservationsConsumed=5,independentReservationsConsumed=2,automaticRetry=False)
    if contract.get('campaignId')==STRUCTURE_CAMPAIGN:
        first=verify_predecessor(repository,dict(contract,campaignId=SCHEMA_CAMPAIGN))
        prior=contract.get('stoppedStructurePredecessor')
        require(isinstance(prior,dict) and set(prior)=={'campaignId','sourceCommit','campaignSha256','attemptSha256','stopSha256','primaryReceiptSha256'} and
                prior['campaignId']==SCHEMA_CAMPAIGN and isinstance(prior['sourceCommit'],str) and re.fullmatch(r'[0-9a-f]{40}',prior['sourceCommit']),
                'stopped structure predecessor fields')
        storage=common_ledger_path(repository,SCHEMA_CAMPAIGN)
        raws={n:read_regular(storage/n) for n in ['campaign.json','attempt-0001.json','stop-0001.json']}
        require(set(p.name for p in storage.iterdir())=={'lock',*raws},'stopped structure inventory')
        for name,key in [('campaign.json','campaignSha256'),('attempt-0001.json','attemptSha256'),('stop-0001.json','stopSha256')]:
            require(sha(raws[name])==pin(prior[key]),'original structure stopped ledger drift');read_owned(storage/name)
        campaign,attempt,stop=(strict_json(raws[n]) for n in ['campaign.json','attempt-0001.json','stop-0001.json'])
        require(campaign.get('campaignId')==SCHEMA_CAMPAIGN and type(attempt.get('attempt')) is int and attempt['attempt']==1 and
                attempt.get('sourceCommit')==prior['sourceCommit'] and attempt.get('contractSha256')==campaign.get('contractSha256') and
                all(type(stop.get(k)) is type(v) and stop[k]==v for k,v in attempt.items()) and
                stop.get('status')=='stopped_before_independent_review' and stop.get('reason')=='primary-structure-rejected' and
                type(stop.get('independentInvocations')) is int and stop['independentInvocations']==0 and stop.get('automaticRetry') is False and
                stop.get('primaryReceiptSha256')==pin(prior['primaryReceiptSha256']),'original structure predecessor binding')
        raw=read_regular(storage.parent/SCHEMA_RECEIPT);receipt=strict_json(raw)
        require(sha(raw)==prior['primaryReceiptSha256'] and receipt.get('status')=='primary_capture_awaits_parent_and_independent_review' and
                receipt.get('sourceCommit')==prior['sourceCommit'] and receipt.get('attempt')==attempt,'original stopped structure receipt drift')
        return dict(status='two_original_stopped_campaigns_preserved',predecessors=[first,dict(campaignId=SCHEMA_CAMPAIGN,
            primaryReservationsConsumed=1,independentReservationsConsumed=0,primaryReceiptSha256=sha(raw),accepted=False)],
            primaryReservationsConsumed=2,independentReservationsConsumed=0,automaticRetry=False)
    if contract.get('campaignId')!=SCHEMA_CAMPAIGN:return None
    prior=contract.get('stoppedPredecessor')
    require(isinstance(prior,dict) and set(prior)=={'campaignId','sourceCommit','campaignSha256','attemptSha256','stopSha256','primaryReceiptSha256'},'stopped predecessor fields')
    require(prior['campaignId']==INITIAL_CAMPAIGN and re.fullmatch(r'[0-9a-f]{40}',prior['sourceCommit'] or ''),'stopped predecessor identity')
    legacy=common_ledger_path(repository)
    raws={n:read_regular(legacy/n) for n in ['campaign.json','attempt-0001.json','stop-0001.json']}
    for name,key in [('campaign.json','campaignSha256'),('attempt-0001.json','attemptSha256'),('stop-0001.json','stopSha256')]:
        require(sha(raws[name])==pin(prior[key]),'original stopped ledger drift');read_owned(legacy/name)
    campaign,attempt,stop=(strict_json(raws[n]) for n in ['campaign.json','attempt-0001.json','stop-0001.json'])
    require(set(p.name for p in legacy.iterdir())=={'lock',*raws},'original stopped campaign inventory')
    require(campaign.get('campaignId')==INITIAL_CAMPAIGN and attempt.get('attempt')==1 and attempt.get('sourceCommit')==prior['sourceCommit'] and
        attempt.get('contractSha256')==campaign.get('contractSha256') and all(stop.get(k)==v for k,v in attempt.items()) and
        stop.get('status')=='stopped_before_independent_review' and stop.get('reason')=='primary-capture-failed' and stop.get('independentInvocations')==0 and
        stop.get('automaticRetry') is False and stop.get('primaryReceiptSha256')==pin(prior['primaryReceiptSha256']),'original stopped predecessor binding')
    raw=read_regular(legacy.parent/INITIAL_RECEIPT);receipt=strict_json(raw)
    require(sha(raw)==prior['primaryReceiptSha256'] and receipt.get('status')=='primary_capture_stopped' and
        receipt.get('sourceCommit')==prior['sourceCommit'] and receipt.get('attempt')==attempt,'original failed receipt drift')
    return dict(status='original_stopped_campaign_preserved',campaignId=INITIAL_CAMPAIGN,primaryReservationsConsumed=1,
        independentReservationsConsumed=0,primaryReceiptSha256=sha(raw),usage=None,automaticRetry=False)


def open_ledger(repository: Path, bound: BoundInputs):
    # 全worktreeで共通の場所。出力先・campaign変更を台帳の切替に使わない。
    verify_predecessor(repository,bound.contract)
    return Ledger(common_ledger_path(repository,bound.contract.get('campaignId')), bound, require_independent_reviews=True)
