"""公開カナリアの原bytes・固定入力・共有予約を照合する。採点と台帳の確定は行わない。"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import math
import os
from pathlib import Path
import re
import stat

import production_canary_capture as capture
import production_ledger as ledger
import production_trace as trace
import source_guard as guard

require = trace.require
FIXED_ARTIFACTS = frozenset({
    'contract.json', 'reservation.json', 'invocation.json', 'config.json', 'version.stdout', 'version.stderr',
    'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-stderr.bin', 'trace-safe.jsonl', 'runtime-result.json',
    'isolated-result.json', 'namespace.stdout', 'namespace.stderr', 'model-input.json', 'decision-schema.json',
})
OPTIONAL_ARTIFACTS = frozenset({'host.jsonl'})
OPAQUE_DIRECTORIES = frozenset({'work', 'tmp', 'codex-home', 'logs', 'state'})
STOP_FILES = frozenset({'host-stop.json', 'capture-stop.json', 'dialogue-stop.json', 'proxy-capture-errors.json'})
SNAPSHOT = '.venv/production-routing-preparation-02/snapshot'
CASES = 'evals/skills/routing/production-canary-cases-v0.1.json'
CATALOG = 'evals/skills/event-catalog.json'
INSTRUCTIONS = 'evals/skills/routing/production-canary-instructions-v0.1.txt'
SCHEMA = 'evals/skills/schemas/decision.schema.json'
AUDIT_SOURCES = ['evals/skills/routing/production_canary_evidence.py',
                 'tests/skills/test_production_canary_evidence.py']


def read_original(path: Path):
    return ledger.read_regular(path)


def artifact_name(name):
    require(isinstance(name, str) and name == str(Path(name)) and '\\' not in name and
            not Path(name).is_absolute() and all(p not in {'.', '..', ''} for p in name.split('/')),
            'original artifact path')
    if name in FIXED_ARTIFACTS | OPTIONAL_ARTIFACTS:
        return
    parts = name.split('/')
    require(len(parts) in {3, 4} and parts[0] == 'rollout-traces' and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', parts[1]) and
            parts[1] not in {'auth', 'cache', 'state'}, 'unknown original artifact')
    require(len(parts) == 3 and parts[2] in {'manifest.json', 'trace.jsonl'} or
            len(parts) == 4 and parts[2] == 'payloads' and re.fullmatch(r'[1-9][0-9]*\.json', parts[3]),
            'unknown original rollout artifact')


def artifact_inventory(base, declared):
    """全パスを検査してから内容を読む。opaqueディレクトリには降りない。"""
    require(isinstance(declared, dict) and FIXED_ARTIFACTS <= set(declared), 'required original artifacts')
    for name, digest in declared.items():
        artifact_name(name)
        ledger.pin(digest)
    ledger.safe_tree(base)
    require(base.is_dir(), 'original capture directory required')
    require((base / 'rollout-traces').is_dir() and not (base / 'rollout-traces').is_symlink(),
            'original rollout root required')
    actual = set()
    for child in base.iterdir():
        require(not child.is_symlink(), 'original artifact symlink')
        require(child.name not in STOP_FILES, 'primary stop marker')
        if child.name in OPAQUE_DIRECTORIES:
            require(child.is_dir(), 'opaque runtime directory shape')
            continue
        if child.name == 'receipt.json':
            require(child.is_file(), 'capture receipt shape')
            continue
        if child.name == 'rollout-traces':
            require(child.is_dir(), 'rollout directory required')
            groups = list(child.iterdir())
            require(len(groups) == 1, 'one original rollout required')
            group = groups[0]
            require(not group.is_symlink() and group.is_dir(), 'rollout directory symlink or shape')
            artifact_name(str(group.relative_to(base)) + '/manifest.json')
            for entry in group.iterdir():
                require(not entry.is_symlink(), 'original rollout symlink')
                if entry.name == 'payloads':
                    require(entry.is_dir(), 'rollout payload directory required')
                    for payload in entry.iterdir():
                        require(not payload.is_symlink() and payload.is_file(), 'original payload shape')
                        name = str(payload.relative_to(base))
                        artifact_name(name)
                        actual.add(name)
                else:
                    name = str(entry.relative_to(base))
                    artifact_name(name)
                    require(entry.is_file(), 'original rollout file shape')
                    actual.add(name)
            prefix = str(group.relative_to(base)) + '/'
            require({prefix + 'manifest.json', prefix + 'trace.jsonl'} <= actual and
                    any(n.startswith(prefix + 'payloads/') for n in actual), 'incomplete original rollout')
        else:
            artifact_name(child.name)
            require(child.is_file(), 'original file shape')
            actual.add(child.name)
    require(actual == set(declared), 'original artifact inventory drift')
    return sorted(actual)


@dataclass(frozen=True)
class FixedInputs:
    bound: ledger.BoundInputs
    decision_schema_raw: bytes
    source_evidence: dict
    audit_source_evidence: dict


def load_fixed_inputs(repository, source):
    """レシートの任意パスを使わず、固定Git refと公開snapshotから再構成する。"""
    require(isinstance(source, str) and re.fullmatch(r'[0-9a-f]{40}', source), 'full source commit required')
    require(guard.git(repository, 'rev-parse', source + '^{commit}').decode().strip() == source,
            'exact fixed commit required')
    contract = trace.strict_json(guard.git(repository, 'show', source + ':' + capture.CONTRACT))
    capture.policy(contract)
    require(contract['snapshotRelativePath'] == SNAPSHOT, 'fixed public snapshot path')
    evidence = guard.verify(repository, source, contract['sourceFiles'])
    audit_evidence = guard.verify(repository, source, [*contract['sourceFiles'], *AUDIT_SOURCES])
    manifest_raw = read_original(repository / SNAPSHOT / 'manifest.json')
    require(ledger.sha(manifest_raw) == contract['manifestSha256'], 'fixed manifest drift')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    for name, digest in manifest['resources'].items():
        raw = read_original(repository / SNAPSHOT / name)
        public_path = 'plugins/' + str(Path(name).relative_to('resources'))
        require(ledger.sha(raw) == digest and
                ledger.sha(guard.git(repository, 'show', source + ':' + public_path)) == digest,
                'fixed public resource drift')
    raws = [guard.git(repository, 'show', source + ':' + name) for name in [CASES, CATALOG]]
    raws += [manifest_raw, guard.git(repository, 'show', source + ':' + INSTRUCTIONS),
             ledger.encoded(dict(platform='Linux', codexVersion=contract['codexVersion'], sdkVersion=contract['sdkVersion']))]
    runtime = dict(contract, schemaVersion='1.0', sourceCommit=source, candidateSource=manifest['sourceCommit'],
                   inputSha256={k: ledger.sha(v) for k, v in zip(['cases', 'catalog', 'manifest', 'instructions', 'environment'], raws)})
    bound = ledger.bind_initial_canary_inputs(ledger.encoded(runtime), *raws)
    schema = trace.strict_json(guard.git(repository, 'show', source + ':' + SCHEMA))
    schema['properties']['selectedEntry']['enum'] = [None, *sorted(trace.SKILLS)]
    return FixedInputs(bound, capture.cli.encoded(schema), evidence, audit_evidence)


def load_verified_capture(repository, source, ordinal):
    """読取りのみの構造検査。成功しても独立採点・次枠予約・acceptedには進めない。"""
    fixed = load_fixed_inputs(repository, source)
    bound = fixed.bound
    attempt = bound.attempt(ordinal)
    base = repository / attempt['outputRelativePath']
    receipt_raw = read_original(base / 'receipt.json')
    receipt = trace.strict_json(receipt_raw)
    require(isinstance(receipt, dict) and set(receipt) == {'status', 'sourceCommit', 'attempt', 'sourceGuards',
            'namespaceExitCode', 'timedOut', 'elapsedSeconds', 'artifactSha256', 'primaryModelTrajectories',
            'independentReviewPerformed', 'automaticRetries', 'certifiesApiRequestHardCap',
            'eligibleForMeasurement', 'phaseComplete'}, 'capture receipt fields')
    names = artifact_inventory(base, receipt.get('artifactSha256'))
    originals = {name: read_original(base / name) for name in names}
    require({name: ledger.sha(raw) for name, raw in originals.items()} == receipt['artifactSha256'],
            'original artifact hash drift')
    require(receipt.get('status') == 'primary_capture_awaits_parent_and_independent_review' and
            receipt.get('sourceCommit') == source and trace.json_equal(receipt.get('attempt'), attempt),
            'capture receipt source or attempt drift')
    expected_flags = dict(namespaceExitCode=0, timedOut=False, primaryModelTrajectories=1,
        independentReviewPerformed=False, automaticRetries=0, certifiesApiRequestHardCap=False,
        eligibleForMeasurement=False, phaseComplete=False)
    require(all(trace.json_equal(receipt.get(k), v) for k, v in expected_flags.items()), 'capture status or scope drift')
    require(type(receipt.get('elapsedSeconds')) in {int, float} and
            (type(receipt['elapsedSeconds']) is int or math.isfinite(receipt['elapsedSeconds'])) and
            0 <= receipt['elapsedSeconds'],
            'capture finite elapsed time')
    capture_evidence = dict(fixed.source_evidence, observedHead=source)
    require(trace.json_equal(receipt.get('sourceGuards'), dict.fromkeys(['before', 'invoke', 'after'], capture_evidence)),
            'capture source evidence drift')
    require(originals['contract.json'] == bound.contract_raw and
            originals['reservation.json'] == ledger.encoded(attempt) and
            originals['model-input.json'] == bound.payloads[(ordinal - 1) // bound.repetitions] and
            originals['decision-schema.json'] == fixed.decision_schema_raw, 'fixed original input drift')
    require(trace.json_equal(trace.strict_json(originals['runtime-result.json']),
            dict(exitCode=0, forcedShutdown=False, captureIntegrity=True)) and
            trace.json_equal(trace.strict_json(originals['isolated-result.json']), dict(sdkErrorType=None)),
            'original runtime failed')
    require(originals['version.stdout'].decode().strip() == bound.contract['codexVersion'] and
            originals['version.stderr'] == b'', 'original CLI version drift')
    require(trace.json_equal(trace.strict_json(originals['config.json']), capture.config_for(base, bound.contract, repository=repository)),
            'original runtime config drift')
    invocation = trace.strict_json(originals['invocation.json'])
    require(isinstance(invocation, dict) and set(invocation) == {'argv', 'sourceCommit', 'maximumLogicalTurns', 'modelInputSha256'} and
            invocation['sourceCommit'] == source and type(invocation['maximumLogicalTurns']) is int and
            invocation['maximumLogicalTurns'] == 1 and invocation['modelInputSha256'] == attempt['modelInputSha256'] and
            isinstance(invocation['argv'], list) and bool(invocation['argv']) and
            all(isinstance(v, str) for v in invocation['argv']) and
            trace.json_equal(invocation['argv'], capture.namespace_command(base, bound.contract, repository=repository)),
            'original invocation binding')
    storage = ledger.common_ledger_path(repository)
    ledger.safe_tree(storage)
    info = storage.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            'shared ledger directory ownership or mode')
    campaign = ledger.read_owned(storage / 'campaign.json')
    require(trace.json_equal(campaign, dict(campaignId=bound.contract['campaignId'], **bound.identity,
        reviewReservationRequired=True, attempts=[bound.attempt(i) for i in range(1, 5)])), 'shared campaign binding')
    reservation_path = storage / f'attempt-{ordinal:04d}.json'
    shared = ledger.read_owned(reservation_path)
    shared_raw = read_original(reservation_path)
    require(trace.json_equal(shared, attempt) and shared_raw == originals['reservation.json'], 'shared primary reservation drift')
    require(not (storage / f'review-{ordinal:04d}.json').exists(), 'primary attempt already finalized')
    # 読取り専用の検査context。初期化・lock作成・予約・同期を呼ばない。
    context = ledger.Ledger.__new__(ledger.Ledger)
    context.storage, context.bound, context.require_independent_reviews = storage, bound, True
    require(context.reservations(allow_pending_last=True) == ordinal, 'latest pending primary reservation required')
    result = dict(status='primary_artifacts_and_fixed_inputs_verified', sourceCommit=source, attempt=attempt,
        receiptSha256=ledger.sha(receipt_raw), artifactSha256=receipt['artifactSha256'],
        sharedReservationSha256=ledger.sha(shared_raw), fixedInputSha256=bound.contract['inputSha256'],
        runtimeConfigVerified=True, invocationArgvVerified=True,
        auditSourceEvidence=fixed.audit_source_evidence,
        certifiesProviderWireBodies=False, eligibleForMeasurement=False,
        certifiesBehavior=False, certifiesSkillGate=False, independentReviewPerformed=False,
        ledgerFinalized=False)

    return VerifiedCapture(fixed, base, tuple(originals.items()), ledger.encoded(result))


@dataclass(frozen=True)
class VerifiedCapture:
    fixed: FixedInputs
    base: Path
    original_items: tuple[tuple[str, bytes], ...]
    result_raw: bytes

    @property
    def originals(self):
        return MappingProxyType(dict(self.original_items))

    @property
    def result(self):
        return trace.strict_json(self.result_raw)


def verify_capture(repository, source, ordinal):
    return load_verified_capture(repository, source, ordinal).result
