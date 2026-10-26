"""固定目的の条件phase部品。契約と既存journalのreadonly検査のみ。"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType

import production_heldout_continuation as continuation

legacy, inputs, io, require = (continuation.legacy, continuation.inputs,
    continuation.io, continuation.require)
ANCHOR_PATH = 'evals/skills/routing/production-heldout-condition-genesis-v0.1.json'
ANCHOR_SHA256 = 'd5efb3e140185bba4cae2695a166fce5f8397f94269707288be81508fa85ef81'
HEADER_VERSION = 'heldout-condition-phase-header-0.1.0'
REGISTRY_NAME = 'measurement-ledgers/r04-heldout-condition-phases-01'
SEAL_NAME = 'condition-seal.json'
MAX_PHASES = 64
MAX_METADATA_BYTES = 4*1024*1024
MAX_REGISTRY_BYTES = 64*1024*1024
MAX_EVENTS = 169
EVENT_KEYS = {'version', 'contractSha256', 'sequence', 'previousSha256', 'ordinal',
    'stage', 'artifactSha256', 'resourceProofSha256', 'measuredCorrect', 'stopReason'}


def anchor():
    raw = io.read_regular(Path(__file__).resolve().parents[3]/ANCHOR_PATH)
    require(io.sha(raw) == ANCHOR_SHA256, 'heldout phase genesis anchor drift')
    value = inputs.parse(raw)
    require(value.get('version') == 'heldout-condition-purpose-genesis-0.1.0'
        and value.get('purpose') == continuation.CAMPAIGN
        and value.get('priorStopAnchorSha256') == continuation.ANCHOR_SHA256,
        'heldout phase genesis identity')
    for name, contract in value['genesisContracts'].items():
        require(io.sha(io.encoded(contract)) == value['genesisSha256'][name],
            'heldout phase genesis contract digest')
    return value


def phase_header(value):
    require(isinstance(value, dict) and set(value) == {'version', 'purposeAnchorSha256',
        'index', 'previousActivationSha256', 'previousJournalHeadSha256', 'firstOrdinal'},
        'heldout phase header inventory')
    require(value['version'] == HEADER_VERSION and value['purposeAnchorSha256'] == ANCHOR_SHA256
        and type(value['index']) is int and 1 <= value['index'] <= MAX_PHASES
        and type(value['firstOrdinal']) is int and 4 <= value['firstOrdinal'] <= 24,
        'heldout phase header identity')
    for name in ['previousActivationSha256', 'previousJournalHeadSha256']:
        io.pin(value[name])
    require(value['index'] != 1 or value['previousActivationSha256'] == ANCHOR_SHA256,
        'heldout first phase predecessor')
    return value


def registry_root():
    return inputs.PRIVATE_CASES.parent/REGISTRY_NAME


def phase_root(index):
    require(type(index) is int and 0 <= index <= MAX_PHASES, 'heldout phase index')
    return (inputs.PRIVATE_CASES.parent/continuation.ROOT_NAME if index == 0
        else registry_root()/'ledgers'/f'phase-{index:04d}')


def _originals():
    import production_heldout_originals
    return production_heldout_originals


def _read(root, name, *, maximum=MAX_METADATA_BYTES):
    raw = _originals().read_original(root, name, additional_artifacts=frozenset({name}))
    require(0 < len(raw) <= maximum, 'heldout phase finite metadata')
    return raw


def base_contract(raw):
    value = inputs.parse(raw)
    require(isinstance(value, dict), 'heldout phase base contract object')
    if value.get('version') == continuation.VERSION:
        continuation.contract(raw)
        value = dict(value, version=legacy.VERSION)
        value.pop('priorStopAnchorSha256')
    return legacy.contract(io.encoded(value))


@dataclass(frozen=True, repr=False)
class JournalSnapshot:
    """私的row本文をreprへ出さない。公開呼出側には集計だけを渡す。"""
    contract_raw: bytes
    first_ordinal: int
    rows: tuple
    head: str
    seal_sha256: str | None

    def counts(self):
        count = lambda stage: sum(row['stage'] == stage for row in self.rows)
        failed = count('primary_failed')+count('independent_failed')
        return dict(primaryReserved=count('primary_reserved'),
            primaryLaunchMarked=count('primary_started'),
            independentReserved=count('independent_reserved'),
            independentLaunchMarked=count('independent_started'),
            parentVerified=count('parent_verified'),
            correct=sum(row['measuredCorrect'] is True for row in self.rows),
            incorrect=sum(row['measuredCorrect'] is False for row in self.rows),
            evaluationFailed=failed, terminalSlots=count('parent_verified')+failed,
            stopped=bool(self.rows and self.rows[-1]['stage'] == 'global_stop'))


@contextmanager
def journal_read_lock(root):
    """既存lockをreadonlyで開く。directory/file/lockを一切作成しない。"""
    directory = _originals()._open_root(root)
    lock = None
    try:
        lock = os.open('lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        value = os.fstat(lock)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
            and stat.S_IMODE(value.st_mode) == 0o600 and value.st_nlink == 1 and value.st_size == 0,
            'heldout phase readonly lock metadata')
        fcntl.flock(lock, fcntl.LOCK_SH)
        yield directory
    finally:
        if lock is not None:
            os.close(lock)
        os.close(directory)


def scan_journal(directory, root, contract_raw, first_ordinal, *, seal_sha256=None):
    """callerのlock内で読む。sealは外側のregistryが検証したexact hashだけを許す。"""
    require(type(first_ordinal) is int and 2 <= first_ordinal <= 24,
        'heldout phase first ordinal')
    base = base_contract(contract_raw)
    require(_read(root, 'contract.json', maximum=65536) == contract_raw,
        'heldout phase original contract drift')
    names = set(os.listdir(directory))
    expected_fixed = {'lock', 'contract.json'}
    if seal_sha256 is not None:
        io.pin(seal_sha256)
        require(io.sha(_read(root, SEAL_NAME)) == seal_sha256, 'heldout phase seal drift')
        expected_fixed.add(SEAL_NAME)
    events = names-expected_fixed
    require(all(re.fullmatch(r'event-[0-9]{4}\.json', name) is not None for name in events)
        and len(events) <= MAX_EVENTS
        and events == {f'event-{n:04d}.json' for n in range(1, len(events)+1)},
        'heldout phase journal inventory')
    require(expected_fixed <= names, 'heldout phase missing fixed original')
    validator = legacy.HeldoutLedger(root, io.encoded(base))
    rows, previous = [], io.sha(contract_raw)
    for index in range(1, len(events)+1):
        raw = _read(root, f'event-{index:04d}.json', maximum=65536)
        value = inputs.parse(raw)
        require(isinstance(value, dict) and set(value) == EVENT_KEYS
            and value['version'] == legacy.VERSION and value['contractSha256'] == io.sha(contract_raw)
            and type(value['sequence']) is int and value['sequence'] == index
            and value['previousSha256'] == previous and isinstance(value['stage'], str)
            and value['stage'] in {*legacy.STAGES, *legacy.FAILURES.values(), 'global_stop'},
            'heldout phase journal event identity')
        if value['artifactSha256'] is not None:
            io.pin(value['artifactSha256'])
        if not rows and value['stage'] != 'global_stop':
            require(type(value['ordinal']) is int and value['ordinal'] == first_ordinal
                and value['stage'] == 'primary_reserved', 'heldout phase first event')
            validator._transition(rows, dict(value, ordinal=1))
        else:
            validator._transition(rows, value)
        rows.append(MappingProxyType(value))
        previous = io.sha(raw)
    # lockで固定したdirectoryと現パスの同一性、既存名集合の不変性を再確認する。
    current = _originals()._open_root(root)
    try:
        a, b = os.fstat(directory), os.fstat(current)
        require((a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) and set(os.listdir(directory)) == names,
            'heldout phase journal directory drift')
    finally:
        os.close(current)
    return JournalSnapshot(contract_raw, first_ordinal, tuple(rows), previous, seal_sha256)


def read_journal(root, contract_raw, first_ordinal, *, seal_sha256=None):
    with journal_read_lock(root) as directory:
        return scan_journal(directory, root, contract_raw, first_ordinal, seal_sha256=seal_sha256)


def carry_forward(snapshots):
    """旧停止の消費1を一度だけ加え、全phaseのrowから累積値を再計算する。"""
    require(isinstance(snapshots, (list, tuple)) and 1 <= len(snapshots) <= MAX_PHASES+1,
        'heldout phase bounded prefix')
    totals = dict(primaryReserved=1, primaryLaunchMarked=1, independentReserved=0,
        independentLaunchMarked=0, parentVerified=0, correct=0, incorrect=0,
        evaluationFailed=0, terminalSlots=0)
    for snapshot in snapshots:
        require(isinstance(snapshot, JournalSnapshot)
            and snapshot.first_ordinal == totals['primaryReserved']+1,
            'heldout phase ordinal continuity')
        values = snapshot.counts()
        require(not values['stopped'] and values['primaryReserved'] == values['terminalSlots'],
            'heldout phase terminal or empty boundary required')
        for name in totals:
            totals[name] += values[name]
        require(totals['primaryReserved'] <= 24 and totals['independentReserved'] <= 24
            and totals['terminalSlots'] <= 23, 'heldout phase cumulative budget')
    return dict(totals, priorStoppedSlots=1, priorPending=1, pending=1,
        unattempted=24-totals['primaryReserved'], accountedSlots=totals['terminalSlots']+1,
        nextOrdinal=totals['primaryReserved']+1)
