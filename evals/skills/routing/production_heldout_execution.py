"""保持24枠の型付き実行条件。入力束縛だけで起動・予約を許可しない。"""
from dataclasses import dataclass
from pathlib import Path
import re

import production_heldout_inputs as inputs
import production_heldout_ledger as ledger
import production_matrix_preflight as public

io, require, trace = inputs.io, inputs.require, inputs.trace
VERSION = 'heldout-production-matrix-execution-0.1.0'
PHASE_VERSION = 'heldout-production-matrix-execution-0.2.0'
DEPLOYMENT_VERSION = 'heldout-matrix-deployment-resources-0.1.0'
PINS = {'snapshotManifest', 'runtimeManifest', 'calibrationManifest', 'sdk', 'cli',
    'contextProfile', 'decisionSchema'}
DEPLOYMENT_KEYS = public.DEPLOYMENT_KEYS - {'executionSha256'}


def execution_contract(raw):
    require(isinstance(raw, bytes), 'heldout execution bytes')
    c = inputs.parse(raw)
    require(isinstance(c, dict), 'heldout execution object')
    phased = c.get('version') == PHASE_VERSION
    require(set(c) == {'version', 'campaignId', 'sourceCommit', 'model',
        'inputContractSha256', 'deploymentSha256', 'outputRelativeRoot', 'pins', 'budget',
        'timeoutSeconds', 'cliVersion', 'certifiesSkillGate'} | ({'conditionPhase'} if phased else set()),
        'heldout execution inventory')
    require((c['version'] == VERSION or c['version'] == PHASE_VERSION) and isinstance(c['campaignId'], str)
        and re.fullmatch(r'heldout-matrix-[a-z0-9]+(?:-[a-z0-9]+)*', c['campaignId']) is not None
        and isinstance(c['sourceCommit'], str) and re.fullmatch(r'[0-9a-f]{40}', c['sourceCommit']) is not None
        and c['model'] == 'gpt-6.1-sol' and c['cliVersion'] == '0.160.1'
        and c['certifiesSkillGate'] is False, 'heldout execution identity')
    require(c['outputRelativeRoot'] == 'measurements/'+c['campaignId'], 'heldout private output identity')
    require(trace.json_equal(c['budget'], dict(primary=24, independent=24, automaticRetries=0, delegations=0)),
        'heldout execution budgets')
    timeout = c['timeoutSeconds']
    require(isinstance(timeout, dict) and set(timeout) == {'primary', 'independent'}
        and all(type(v) is int and 1 <= v <= 600 for v in timeout.values()), 'heldout execution timeouts')
    require(isinstance(c['pins'], dict) and set(c['pins']) == PINS, 'heldout execution pin inventory')
    for value in [c['inputContractSha256'], c['deploymentSha256'], *c['pins'].values()]:
        io.pin(value)
    if phased:
        from production_heldout_phases import phase_header, continuation
        require(c['campaignId'] == continuation.CAMPAIGN, 'heldout phase fixed campaign')
        phase_header(c['conditionPhase'])
    return c


def deployment_for_execution(execution_raw, deployment_raw):
    c = execution_contract(execution_raw)
    require(isinstance(deployment_raw, bytes) and io.sha(deployment_raw) == c['deploymentSha256'],
        'heldout deployment fixed bytes')
    d = inputs.parse(deployment_raw)
    require(isinstance(d, dict) and set(d) == DEPLOYMENT_KEYS and d['version'] == DEPLOYMENT_VERSION
        and d['sourceCommit'] == c['sourceCommit'] and d['certifiesSkillGate'] is False,
        'heldout deployment identity')
    require(d['codexPath'] == str(public.capture.fixed_runtime.ROOT/'bin/codex')
        and d['codexVersion'] == 'codex-cli 0.160.1' and d['sdkVersion'] == '0.160.1',
        'heldout fixed runtime versions')
    require(isinstance(d['sdkRelativePath'], str) and re.fullmatch(
        r'\.venv/matrix-codex-python-sdk-deps-[a-z0-9]+(?:-[a-z0-9]+)*', d['sdkRelativePath']) is not None,
        'heldout SDK path')
    require(isinstance(d['snapshotRelativePath'], str) and re.fullmatch(
        r'\.venv/heldout-routing-preparation-[a-z0-9]+(?:-[a-z0-9]+)*/snapshot',
        d['snapshotRelativePath']) is not None, 'heldout snapshot path')
    require(type(d['snapshotResourceCount']) is int and d['snapshotResourceCount'] == 72,
        'heldout frozen product denominator')
    for key, pin in [('manifestSha256', 'snapshotManifest'), ('sdkTreeSha256', 'sdk'),
        ('runtimeManifestSha256', 'runtimeManifest'), ('contextProfileSha256', 'contextProfile'),
        ('calibrationManifestSha256', 'calibrationManifest')]:
        require(io.pin(d[key]) == c['pins'][pin], 'heldout deployment pin drift')
    io.pin(d['sdkManifestSha256'])
    return d


@dataclass(frozen=True, repr=False)
class BoundExecution:
    execution_raw: bytes
    deployment_raw: bytes
    input_contract_raw: bytes
    raw_inputs: tuple[bytes, ...]

    @property
    def contract(self):
        return execution_contract(self.execution_raw)

    @property
    def matrix(self):
        return inputs.bind(self.input_contract_raw, **dict(zip(inputs.INPUT_NAMES, self.raw_inputs)))

    def slot(self, ordinal):
        c = self.contract
        return dict(self.matrix.slot(ordinal), sourceCommit=c['sourceCommit'], campaignId=c['campaignId'],
            executionSha256=io.sha(self.execution_raw))

    def stage_root(self, ordinal, role):
        self.slot(ordinal)
        require(role in {'primary', 'independent'}, 'heldout stage role')
        return inputs.PRIVATE_CASES.parent/self.contract['outputRelativeRoot']/role/f'attempt-{ordinal:04d}'

    def ledger_contract(self, resource_proof_raw):
        # resource proofの現物/意味の検証はpreflightの責務。ここでは同じ条件へ束縛する。
        require(self.contract['version'] != PHASE_VERSION,
            'heldout phase reviewed ledger admission not connected')
        require(isinstance(resource_proof_raw, bytes), 'heldout resource proof bytes')
        proof = inputs.parse(resource_proof_raw)
        require(isinstance(proof, dict) and proof.get('status') == 'heldout_resources_verified_not_launchable'
            and proof.get('sourceCommit') == self.contract['sourceCommit']
            and proof.get('executionSha256') == io.sha(self.execution_raw)
            and proof.get('inputContractSha256') == io.sha(self.input_contract_raw), 'heldout resource proof identity')
        c = self.contract
        raw = io.encoded(dict(version=ledger.VERSION, campaignId=c['campaignId'], sourceCommit=c['sourceCommit'],
            inputContractSha256=c['inputContractSha256'], resourceProofSha256=io.sha(resource_proof_raw),
            model=c['model'], setVersion=inputs.SET_VERSION, budget=c['budget'],
            timeoutSeconds=c['timeoutSeconds'], certifiesSkillGate=False))
        ledger.contract(raw)
        if c['campaignId'] == 'heldout-matrix-survey-remaining23-20261024-01':
            from production_heldout_continuation import contract_from_base
            return contract_from_base(raw)
        return raw


def bind(execution_raw, deployment_raw, input_contract_raw, **raw_inputs):
    matrix = inputs.bind(input_contract_raw, **raw_inputs)
    c = execution_contract(execution_raw)
    require(inputs.parse(input_contract_raw)['sourceCommit'] == c['sourceCommit']
        and io.sha(matrix.contract_raw) == c['inputContractSha256'], 'heldout execution input binding')
    deployment_for_execution(execution_raw, deployment_raw)
    return BoundExecution(execution_raw, deployment_raw, input_contract_raw,
        tuple(raw_inputs[name] for name in inputs.INPUT_NAMES))


def rebound(bound):
    require(isinstance(bound, BoundExecution), 'heldout bound execution required')
    expected = bind(bound.execution_raw, bound.deployment_raw, bound.input_contract_raw,
        **dict(zip(inputs.INPUT_NAMES, bound.raw_inputs)))
    require(expected == bound, 'heldout bound execution drift')
    return bound
