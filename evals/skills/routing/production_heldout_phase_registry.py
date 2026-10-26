"""条件phaseのproposal/admission。有効化器へ未接続の申請部品。"""
from datetime import date
import production_heldout_phases as phases

io, inputs, require = phases.io, phases.inputs, phases.require
PROPOSAL_VERSION = 'heldout-condition-phase-proposal-0.1.0'
ADMISSION_VERSION = 'heldout-condition-phase-admission-0.1.0'
SEAL_VERSION = 'heldout-condition-phase-seal-0.1.0'
ACTIVATION_VERSION = 'heldout-condition-phase-activation-0.1.0'
CURRENT_RAW_KEYS = {'execution', 'deployment', 'input', 'resourceProof', 'context', 'ledger'}
CONTEXT_DATE_FIELDS = {'date', 'calibrationSource', 'calibrationRequestSha256', 'calibrationReceiptSha256'}


def finite_json(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= phases.MAX_METADATA_BYTES,
        'heldout phase finite JSON bytes')
    return inputs.parse(raw)


def base_for(execution_raw, deployment_raw, input_raw, proof_raw, context_raw, genesis):
    """全引数は公開metadata。snapshot/原読み取りやモデル起動を行わない。"""
    from production_heldout_execution import execution_contract, deployment_for_execution
    import production_heldout_preflight as preflight
    require(io.sha(io.encoded(genesis)) == phases.ANCHOR_SHA256, 'heldout phase fixed genesis metadata')
    c = execution_contract(execution_raw)
    phases.phase_header(c.get('conditionPhase'))
    d = deployment_for_execution(execution_raw, deployment_raw)
    proof, context = finite_json(proof_raw), finite_json(context_raw)
    expected_input = dict(genesis['genesisContracts']['input'], sourceCommit=c['sourceCommit'])
    require(io.encoded(expected_input) == input_raw, 'heldout phase unchanged input and denominator')
    require(c['campaignId'] == genesis['purpose'] and c['outputRelativeRoot'] == 'measurements/'+genesis['purpose']
        and c['timeoutSeconds'] == genesis['genesisContracts']['execution']['timeoutSeconds'],
        'heldout phase purpose and timeouts')
    require(all(c['pins'][name] == digest for name, digest in genesis['stablePins'].items()),
        'heldout phase immutable runtime SDK and schema')
    require(isinstance(context, dict) and CONTEXT_DATE_FIELDS <= set(context)
        and preflight.trace.json_equal({k:v for k,v in context.items() if k not in CONTEXT_DATE_FIELDS},
            genesis['stableContext']) and io.sha(context_raw) == c['pins']['contextProfile'],
        'heldout phase unchanged context projection')
    require(isinstance(proof, dict) and set(proof) == preflight.PROOF_KEYS
        and proof['status'] == 'heldout_resources_verified_not_launchable'
        and proof['sourceCommit'] == c['sourceCommit'] and proof['executionSha256'] == io.sha(execution_raw)
        and proof['deploymentSha256'] == io.sha(deployment_raw)
        and proof['inputContractSha256'] == io.sha(input_raw) == c['inputContractSha256']
        and proof['contextProfileSha256'] == io.sha(context_raw) == d['contextProfileSha256']
        and proof['contextDate'] == context['date']
        and proof['casesSha256'] == genesis['stableInputSha256']['cases']
        and proof['productResourcesSha256'] == genesis['stableProductResourcesSha256']
        and proof['baselineProductSource'] == genesis['baselineProductSource']
        and proof['sdkTreeSha256'] == genesis['stablePins']['sdk']
        and proof['decisionSchemaSha256'] == genesis['stablePins']['decisionSchema']
        and isinstance(proof['originalCalibration'], dict)
        and proof['originalCalibration'].get('status') == 'original_local_calibration_matches'
        and proof['originalCalibration']['calibrationManifestSha256'] == c['pins']['calibrationManifest']
        and proof['launchEnabled'] is False and proof['certifiesSkillGate'] is False
        and proof['certifiesRelease'] is False
        and all(type(proof[name]) is int and proof[name] == 0 for name in ['models', 'reservations']),
        'heldout phase exact resource proof')
    raw = io.encoded(dict(version=phases.legacy.VERSION, campaignId=c['campaignId'],
        sourceCommit=c['sourceCommit'], inputContractSha256=c['inputContractSha256'],
        resourceProofSha256=io.sha(proof_raw), model=c['model'], setVersion=inputs.SET_VERSION,
        budget=c['budget'], timeoutSeconds=c['timeoutSeconds'], certifiesSkillGate=False))
    phases.legacy.contract(raw)
    return raw


def proposal(execution_raw, deployment_raw, input_raw, proof_raw, context_raw,
             genesis, snapshots, previous_context_date, prior_launch):
    """検証済みsnapshotのrowからcarryを求める決定的builder。自己申告carryは受け付けない。"""
    ledger_raw = base_for(execution_raw, deployment_raw, input_raw, proof_raw, context_raw, genesis)
    execution, proof = finite_json(execution_raw), finite_json(proof_raw)
    header = phases.phase_header(execution['conditionPhase'])
    carry = phases.carry_forward(snapshots)
    require(header['index'] == len(snapshots) and header['firstOrdinal'] == carry['nextOrdinal']
        and header['previousJournalHeadSha256'] == snapshots[-1].head and carry['unattempted'] > 0,
        'heldout phase derived next ordinal and previous head')
    require(snapshots[0].contract_raw == io.encoded(genesis['genesisContracts']['ledger'])
        and len(snapshots[0].rows) == genesis['genesisJournalEvents']
        and snapshots[0].head == genesis['genesisJournalHeadSha256'], 'heldout phase fixed initial prefix')
    # 空phaseを飛ばした最後の実起動を、journalと外側で照合したreceipt/pacingへ束縛する。
    started = [(index, item, row) for index, item in enumerate(snapshots)
        for row in item.rows if row['stage'].endswith('_started')]
    require(bool(started), 'heldout phase prior completed launch required')
    index, item, last = started[-1]
    role = last['stage'].removesuffix('_started')
    sealed = [row for row in item.rows if row['ordinal'] == last['ordinal']
        and row['stage'] in {role+'_captured', role+'_failed'}]
    require(len(sealed) == 1 and isinstance(prior_launch, dict)
        and preflight_equal(header['priorLaunch'], prior_launch)
        and prior_launch['phaseIndex'] == index and prior_launch['ordinal'] == last['ordinal']
        and prior_launch['role'] == role and prior_launch['receiptSha256'] == sealed[0]['artifactSha256']
        and prior_launch['sourceCommit'] == phases.base_contract(item.contract_raw)['sourceCommit'],
        'heldout phase prior launch exact sealed original')
    require(type(previous_context_date) is str and type(proof['contextDate']) is str
        and date.fromisoformat(previous_context_date).isoformat() == previous_context_date
        and date.fromisoformat(proof['contextDate']).isoformat() == proof['contextDate']
        and date.fromisoformat(proof['contextDate']) > date.fromisoformat(previous_context_date),
        'heldout phase strictly newer calibration day')
    raws = dict(execution=execution_raw, deployment=deployment_raw, input=input_raw,
        resourceProof=proof_raw, context=context_raw, ledger=ledger_raw)
    return dict(version=PROPOSAL_VERSION, purposeAnchorSha256=phases.ANCHOR_SHA256,
        phaseHeader=header, previousContextDate=previous_context_date, contextDate=proof['contextDate'],
        # seal hashes are intentionally excluded: proposal precedes review and seal in the DAG.
        prefix=[dict(contractSha256=io.sha(item.contract_raw), firstOrdinal=item.first_ordinal,
            journalHeadSha256=item.head) for item in snapshots], carry=carry,
        current={name:raw.decode('utf-8') for name,raw in raws.items()})


def preflight_equal(a, b):
    from production_heldout_preflight import trace
    return trace.json_equal(a, b)


def admission(proposed, review_raw, report_raw, isolation_raw):
    """review原の改行/空白も含めexact bytesをJSON stringとして保持する。"""
    import production_heldout_launch as launch
    require(isinstance(proposed, dict) and proposed.get('version') == PROPOSAL_VERSION,
        'heldout phase proposal required')
    current = proposed['current']
    launch.prelaunch_review(current['execution'].encode(), current['deployment'].encode(),
        review_raw, report_raw, isolation_raw)
    report = finite_json(report_raw)
    require(report.get('conditionPhaseProposalSha256') == io.sha(io.encoded(proposed)),
        'heldout phase proposal independent review binding')
    raw = io.encoded(dict(version=ADMISSION_VERSION, proposal=proposed,
        review=review_raw.decode('utf-8'), report=report_raw.decode('utf-8'),
        isolation=isolation_raw.decode('utf-8')))
    require(len(raw) <= phases.MAX_METADATA_BYTES, 'heldout phase bounded admission')
    return raw


def verify_admission(raw, genesis, snapshots, previous_context_date, prior_launch):
    """wireのcarryやproposalを信用せず、検査済みprefixから全条件を再構成する。"""
    value = finite_json(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'proposal', 'review', 'report', 'isolation'}
        and value['version'] == ADMISSION_VERSION and isinstance(value['proposal'], dict)
        and all(type(value[name]) is str for name in ['review', 'report', 'isolation']),
        'heldout phase admission inventory')
    current = value['proposal'].get('current')
    require(isinstance(current, dict) and set(current) == CURRENT_RAW_KEYS
        and all(type(raw) is str for raw in current.values()), 'heldout phase current raw inventory')
    proposed = proposal(*(current[name].encode() for name in
        ['execution', 'deployment', 'input', 'resourceProof', 'context']),
        genesis, snapshots, previous_context_date, prior_launch)
    require(preflight_equal(proposed, value['proposal']), 'heldout phase recomputed proposal drift')
    require(admission(proposed, value['review'].encode(), value['report'].encode(),
        value['isolation'].encode()) == raw, 'heldout phase canonical admission bytes')
    return value


def seal_record(admitted):
    """前journal headと検分済proposalだけを管理sealへ束縛する。書込みなし。"""
    p = admitted['proposal']
    return dict(version=SEAL_VERSION, purposeAnchorSha256=phases.ANCHOR_SHA256,
        phaseHeader=p['phaseHeader'], proposalSha256=io.sha(io.encoded(p)),
        reviewSha256=io.sha(admitted['review'].encode()), reportSha256=io.sha(admitted['report'].encode()),
        previousLedgerContractSha256=p['prefix'][-1]['contractSha256'],
        previousJournalHeadSha256=p['prefix'][-1]['journalHeadSha256'])


def activation_record(admitted):
    seal = seal_record(admitted)
    return dict(version=ACTIVATION_VERSION, index=admitted['proposal']['phaseHeader']['index'],
        previousActivationSha256=admitted['proposal']['phaseHeader']['previousActivationSha256'],
        proposalSha256=io.sha(io.encoded(admitted['proposal'])),
        sealSha256=io.sha(io.encoded(seal)), admission=admitted)
