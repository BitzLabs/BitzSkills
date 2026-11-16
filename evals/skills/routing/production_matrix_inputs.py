"""公開46×2行列の入力束縛だけ。取得・台帳・Gate認定は別の未接続工程。"""
from collections import Counter
from dataclasses import dataclass
import re

from jsonschema import Draft202012Validator
import production_ledger as ledger
import production_trace as trace

INPUT_NAMES = ('routing', 'behaviorSafety', 'protocol', 'catalog', 'instructions', 'caseSchema')
VERSION = 'public-production-matrix-inputs-0.1.0'
SUBSET_VERSION = 'public-production-subset-inputs-0.1.0'
REGRESSION_CASE_ID = 'SE-047'
STOP_WITH_EVIDENCE_CASE_ID = 'SE-048'
REGRESSION_INPUTS = {
    REGRESSION_CASE_ID: 'stopEvidenceRegression',
    STOP_WITH_EVIDENCE_CASE_ID: 'stopWithEvidenceRegression',
}

CATEGORY_COUNTS = dict(explicit=6, implicit=6, contextual=6, negative=10, conflict=6, behavior=6, safety=6)


@dataclass(frozen=True)
class MatrixInputs:
    contract_raw: bytes
    cases_raw: bytes
    payloads: tuple[bytes, ...]

    @property
    def cases(self):
        return trace.strict_json(self.cases_raw)

    def slot(self, ordinal):
        trace.require(type(ordinal) is int and 1 <= ordinal <= len(self.payloads)*2, 'matrix ordinal')
        index, repetition = divmod(ordinal - 1, 2)
        case = self.cases[index]
        return dict(ordinal=ordinal, caseId=case['caseId'], repetition=repetition+1,
                    payloadSha256=ledger.sha(self.payloads[index]), contractSha256=ledger.sha(self.contract_raw))


def regression_ids(selected):
    if selected in ([REGRESSION_CASE_ID], list(REGRESSION_INPUTS)):
        return selected
    return ()


def input_names(contract):
    selected = contract.get('caseIds') if isinstance(contract, dict) else None
    return (*INPUT_NAMES, *(REGRESSION_INPUTS[case_id] for case_id in regression_ids(selected)))


def valid_subset(selected):
    return bool(regression_ids(selected)) or (
        isinstance(selected, list) and 1 <= len(selected) < 46
        and all(isinstance(n, str) and re.fullmatch(r'SE-0(?:0[1-9]|[1-3][0-9]|4[0-6])', n) for n in selected)
        and selected == sorted(set(selected)))


def bind(contract_raw, **raw_inputs):
    """確定bytes/hashを照合し、期待・制御metadataを含まない一次payloadを作る。"""
    trace.require(isinstance(contract_raw, bytes), 'matrix contract bytes')
    contract = trace.strict_json(contract_raw)
    names = input_names(contract)
    trace.require(set(raw_inputs) == set(names) and all(isinstance(raw, bytes) for raw in raw_inputs.values()),
                  'matrix raw inventory')
    subset = isinstance(contract, dict) and contract.get('version') == SUBSET_VERSION
    extra = {'caseIds'} if subset else set()
    trace.require(isinstance(contract, dict) and set(contract) == {
        'version', 'scope', 'sourceCommit', 'model', 'repetitions', 'budget', 'inputSha256',
        'certifiesBehavior', 'certifiesSkillGate'} | extra, 'matrix contract inventory')
    trace.require(contract['version'] in {VERSION, SUBSET_VERSION}
                  and contract['scope'] == ('public-six-skill-subset-input-binding-only' if subset
                      else 'public-six-skill-input-binding-only')
                  and contract['model'] == 'gpt-6.1-sol'
                  and isinstance(contract['sourceCommit'], str)
                  and re.fullmatch(r'[0-9a-f]{40}', contract['sourceCommit']) is not None,
                  'matrix identity')
    selected = contract.get('caseIds') if subset else [f'SE-{n:03d}' for n in range(1,47)]
    trace.require(not subset or valid_subset(selected), 'matrix selected case inventory')
    maximum = len(selected)*2
    trace.require(type(contract['repetitions']) is int and contract['repetitions'] == 2
                  and trace.json_equal(contract['budget'], dict(primary=maximum, independent=maximum, automaticRetries=0, delegations=0))
                  and contract['certifiesBehavior'] is False and contract['certifiesSkillGate'] is False,
                  'matrix finite limits')
    pins = contract['inputSha256']
    trace.require(isinstance(pins, dict) and set(pins) == set(names), 'matrix pin inventory')
    for name, raw in raw_inputs.items():
        trace.require(ledger.pin(pins[name]) == ledger.sha(raw), 'matrix input drift: '+name)
    schema = trace.strict_json(raw_inputs['caseSchema'])
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    routing, behavior = (trace.strict_json(raw_inputs[n]) for n in ('routing', 'behaviorSafety'))
    trace.require(isinstance(routing, list) and isinstance(behavior, list), 'matrix case collections')
    cases = routing + behavior
    trace.require(len(cases) == 46 and all(isinstance(c, dict) for c in cases), 'matrix distinct case count')
    for case in cases:
        validator.validate(case)
    trace.require([c['caseId'] for c in cases] == [f'SE-{n:03d}' for n in range(1,47)], 'matrix fixed case order')
    trace.require(trace.json_equal(dict(Counter(c['category'] for c in cases)), CATEGORY_COUNTS), 'matrix category denominators')
    for case_id in regression_ids(selected):
        case = trace.strict_json(raw_inputs[REGRESSION_INPUTS[case_id]])
        validator.validate(case)
        trace.require(case['caseId'] == case_id, 'matrix regression case identity')
        cases.append(case)
    catalog = trace.strict_json(raw_inputs['catalog'])
    trace.require(isinstance(catalog, dict) and set(catalog) == {'schemaVersion','catalogVersion','events'}
                  and catalog['schemaVersion'] == '1.0' and isinstance(catalog['catalogVersion'], str)
                  and bool(catalog['catalogVersion'].strip()), 'matrix catalog')
    events = catalog['events']
    trace.require(isinstance(events,list) and events and all(isinstance(e,str) and e.strip() for e in events)
                  and len(events) == len(set(events)), 'matrix catalog events')
    for case in cases:
        expected = case['expected']
        trace.require(all(e in events for e in expected['requiredEvents'] + expected['forbiddenEvents'])
                      and not set(expected['requiredEvents']) & set(expected['forbiddenEvents']), 'matrix expected event binding')
    protocol = trace.strict_json(raw_inputs['protocol'])
    trace.require(isinstance(protocol,dict) and protocol.get('evaluationSetVersion') == '0.7.2'
                  and protocol.get('eventCatalogVersion') == catalog['catalogVersion']
                  and protocol.get('categories') == ['explicit','implicit','contextual','negative','conflict','behavior','safety']
                  and trace.json_equal(protocol.get('minimumRepetitions'), {'prototype':2,'release':3}), 'matrix protocol version')
    instructions = raw_inputs['instructions'].decode('utf-8')
    trace.require(bool(instructions.strip()), 'matrix instructions')
    if subset:
        cases = [case for case in cases if case['caseId'] in selected]
        trace.require([case['caseId'] for case in cases] == selected, 'matrix selected case identity')
    payloads = tuple(ledger.encoded(dict(instructions=instructions,eventCatalog=catalog,case=trace.project_case(c))) for c in cases)
    return MatrixInputs(contract_raw, ledger.encoded(cases), payloads)
