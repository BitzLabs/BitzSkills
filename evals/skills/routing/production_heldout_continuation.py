"""旧停止を変更せず、既消費1枠を引き継ぐ固定23枠の台帳。モデル起動なし。"""
from pathlib import Path

import production_heldout_ledger as legacy

inputs, io, require = legacy.inputs, legacy.io, legacy.require
VERSION = 'heldout-matrix-ledger-0.2.0'
CAMPAIGN = 'heldout-matrix-survey-remaining23-20261024-01'
ROOT_NAME = 'measurement-ledgers/r04-heldout-two-repetitions-remaining23-01'
ANCHOR_PATH = 'evals/skills/routing/production-heldout-prior-stop-v0.1.json'
ANCHOR_SHA256 = '15660dd2d3147e33fdfd34567f0785092af381eb8e1f79c1c49ef5b5efa226e0'
PRIOR_PACING_SHA256 = '5380fb10508667668b4b270d266d7e9343e33d884056535b7f507deba3d25b17'
PRIOR_SOURCE = 'a7cd00a357a084dfab859eed4736d882e9faedc0'


def anchor():
    raw = io.read_regular(Path(__file__).resolve().parents[3]/ANCHOR_PATH)
    require(io.sha(raw) == ANCHOR_SHA256, 'heldout prior stop anchor drift')
    return inputs.parse(raw)


def contract(raw):
    value = inputs.parse(raw)
    require(isinstance(value, dict) and value.get('version') == VERSION
        and value.get('campaignId') == CAMPAIGN and value.get('priorStopAnchorSha256') == ANCHOR_SHA256
        and value.get('sourceCommit') != PRIOR_SOURCE, 'heldout continuation identity')
    base = dict(value, version=legacy.VERSION)
    base.pop('priorStopAnchorSha256')
    legacy.contract(io.encoded(base))
    return value


def contract_from_base(raw):
    base = legacy.contract(raw)
    require(base['campaignId'] == CAMPAIGN, 'heldout fixed continuation campaign')
    result = io.encoded(dict(base, version=VERSION, priorStopAnchorSha256=ANCHOR_SHA256))
    contract(result)
    return result


def verify_prior():
    """固定名12原だけを読取り、旧ledgerへ書き込まず完了と消費を検査する。"""
    import production_heldout_originals as originals
    root = inputs.PRIVATE_CASES.parent
    campaign = root/'measurements/heldout-matrix-survey-20261016-01'
    stage = campaign/'primary/attempt-0001'
    control = campaign/'controls/attempt-0001'
    ledger = root/'measurement-ledgers/r04-heldout-two-repetitions-01'
    refs = {'ledgerContract': (ledger, 'contract.json'),
        **{'event'+str(i): (ledger, f'event-{i:04d}.json') for i in range(1, 4)},
        'execution': (stage, 'contract.json'), 'reservation': (stage, 'reservation.json'),
        'receipt': (stage, 'receipt.json'), 'runtimeResult': (stage, 'runtime-result.json'),
        'sdkResult': (stage, 'isolated-result.json'), 'stagePacing': (stage, 'logical-pacing.json'),
        'controlPacing': (control, 'pacing.json'), 'globalStop': (control, 'global-stop.json')}
    spec = anchor()
    require(set(spec['sha256']) == set(refs), 'heldout prior anchor inventory')
    directory = originals._open_root(ledger)
    try:
        import os
        require(set(os.listdir(directory)) == {'lock', 'contract.json',
            'event-0001.json', 'event-0002.json', 'event-0003.json'}, 'heldout prior journal inventory drift')
    finally:
        os.close(directory)
    raws = {key: originals.read_original(base, name, additional_artifacts=frozenset({name}))
        for key, (base, name) in refs.items()}
    require({key: io.sha(raw) for key, raw in raws.items()} == spec['sha256'], 'heldout prior original drift')
    old_contract = legacy.contract(raws['ledgerContract'])
    require(old_contract['sourceCommit'] == PRIOR_SOURCE and old_contract['setVersion'] == inputs.SET_VERSION,
        'heldout prior purpose drift')
    previous = io.sha(raws['ledgerContract'])
    for i, expected in enumerate(['primary_reserved', 'primary_started', 'global_stop'], 1):
        row = inputs.parse(raws['event'+str(i)])
        require(row['stage'] == expected and row['previousSha256'] == previous
            and row['contractSha256'] == io.sha(raws['ledgerContract']) and row['sequence'] == i
            and row['ordinal'] == (None if i == 3 else 1), 'heldout prior stop journal drift')
        previous = io.sha(raws['event'+str(i)])
    require(row['artifactSha256'] == spec['sha256']['globalStop'], 'heldout prior stop control drift')
    require(inputs.trace.json_equal(inputs.parse(raws['runtimeResult']),
        dict(exitCode=0, forcedShutdown=False, captureIntegrity=True))
        and inputs.trace.json_equal(inputs.parse(raws['sdkResult']), dict(sdkErrorType=None)),
        'heldout prior execution completion required')
    receipt = inputs.parse(raws['receipt'])
    require(raws['stagePacing'] == raws['controlPacing']
        and receipt['artifactSha256']['logical-pacing.json'] == spec['sha256']['stagePacing'],
        'heldout prior receipt pacing drift')
    return raws


def prior_pacing():
    import production_heldout_launch as launch
    raws = verify_prior()
    value = launch.pacing(raws['execution'], inputs.parse(raws['reservation']), raws['stagePacing'])
    return value, io.sha(raws['stagePacing'])


def open_fixed(raw):
    contract(raw)
    return ContinuationLedger(inputs.PRIVATE_CASES.parent/ROOT_NAME, raw)


class ContinuationLedger(legacy.HeldoutLedger):
    """root引数は隔離試験用。製品のfactoryは固定rootのみを使う。"""
    def __init__(self, root, raw):
        self.root = Path(root)
        require(self.root.is_absolute() and '..' not in self.root.parts, 'heldout continuation absolute root')
        self.raw, self.contract, self.digest, self.directory = raw, contract(raw), io.sha(raw), None
        verify_prior()

    def _directory(self):
        verify_prior()
        return super()._directory()

    def _write(self, name, raw):
        verify_prior()
        return super()._write(name, raw)

    def _history(self):
        verify_prior()
        return super()._history()

    def _transition(self, rows, value):
        if not rows and value['stage'] != 'global_stop':
            require(type(value['ordinal']) is int and value['ordinal'] == 2,
                'heldout continuation begins at ordinal2')
            # 先頭の検査にだけ旧規則を使う。保存eventのordinalは2のまま。
            return super()._transition(rows, dict(value, ordinal=1))
        return super()._transition(rows, value)

    def summary(self):
        segment = super().summary()
        segment['status'] = ('stopped' if segment['status'] == 'stopped'
            else 'attempts_recorded' if segment['terminalSlots'] == 23 else 'in_progress')
        return dict(segment, primaryReserved=segment['primaryReserved']+1,
            primaryLaunchMarked=segment['primaryLaunchMarked']+1, unattempted=segment['unattempted']-1,
            pending=segment['pending']+1, priorStoppedSlots=1, priorPending=1,
            accountedSlots=segment['terminalSlots']+1, segment=dict(segment), priorStopPreserved=True)
