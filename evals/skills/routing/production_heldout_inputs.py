"""保持12件×2の入力準備。非公開bytesはメモリ内だけで扱い、モデルを起動しない。"""
from collections import Counter
from dataclasses import dataclass
import argparse
import os
from pathlib import Path
import re
import stat

from jsonschema import Draft202012Validator
import production_ledger as io
import production_trace as trace
import source_guard as guard

VERSION = 'heldout-production-matrix-inputs-0.1.0'
SET_VERSION = 'production-routing-held-out-0.5.0'
VERSION_75 = 'heldout-production-matrix-inputs-0.2.0'
SET_VERSION_75 = 'production-routing-held-out-0.6.0'
PRODUCT_SOURCE_75 = 'ad850493c26699ce0c923676c2e7ab5a303c94c0'
PRIVATE_CASES = Path('/home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006/collection-05/cases.json')
REVIEW_PATH = 'evals/skills/results/2026-10-07-single-replacement-reviewed/summary.json'
PUBLIC_PATHS = dict(reviewedSet=REVIEW_PATH, protocol='evals/skills/protocol.json',
    catalog='evals/skills/event-catalog.json',
    instructions='evals/skills/routing/production-matrix-instructions-v0.1.txt',
    caseSchema='evals/skills/schemas/case.schema.json')
REVIEW_PATH_75 = 'evals/skills/routing/held-out-75-reviewed-set.json'
INPUT_NAMES = ('cases', *PUBLIC_PATHS)
CATEGORY_COUNTS = dict(explicit=2, implicit=2, contextual=2, negative=3, safety=3)
SOURCE_DEPENDENCIES = ('evals/skills/routing/production_heldout_inputs.py',
    'evals/skills/routing/production_ledger.py', 'evals/skills/routing/production_trace.py',
    'evals/skills/routing/source_guard.py', 'evals/skills/routing/host.py')
SOURCE_FILES = (*PUBLIC_PATHS.values(), *SOURCE_DEPENDENCIES)
require = trace.require


def parse(raw):
    # JSON診断やschema例外に含まれる非公開の値を呼出し元へ伝えない。
    try:
        return trace.strict_json(raw)
    except Exception:
        raise ValueError('heldout JSON rejected') from None


@dataclass(frozen=True, repr=False)
class HeldoutInputs:
    contract_raw: bytes
    cases_raw: bytes
    payloads: tuple[bytes, ...]

    @property
    def cases(self):
        """親の採点専用。戻り値やslotを公開ログへ出さない。"""
        return parse(self.cases_raw)

    def slot(self, ordinal):
        require(type(ordinal) is int and 1 <= ordinal <= 24, 'heldout ordinal')
        index, repetition = divmod(ordinal - 1, 2)
        return dict(ordinal=ordinal, caseId=self.cases[index]['caseId'], repetition=repetition+1,
            payloadSha256=io.sha(self.payloads[index]), contractSha256=io.sha(self.contract_raw))

    def public_summary(self):
        contract = parse(self.contract_raw)
        summary = dict(status='heldout_inputs_prepared_not_launchable', version=contract['version'],
            sourceCommit=contract['sourceCommit'], setVersion=contract['setVersion'],
            casesSha256=contract['inputSha256']['cases'], contractSha256=io.sha(self.contract_raw),
            caseCount=12, repetitions=2, plannedPrimary=24, plannedIndependent=24,
            modelInvocations=0, reservations=0, privateContentsPublished=False,
            certifiesSkillGate=False, certifiesRelease=False)
        if contract['version'] == VERSION_75:
            summary['productSourceCommit'] = contract['productSourceCommit']
        return summary


def bind(contract_raw, **raw_inputs):
    """hash固定・採用済み集合・分母を確認し、期待値なしの一次payloadを作る。"""
    require(isinstance(contract_raw, bytes) and set(raw_inputs) == set(INPUT_NAMES)
        and all(isinstance(v, bytes) for v in raw_inputs.values()), 'heldout raw inventory')
    c = parse(contract_raw)
    require(isinstance(c, dict), 'heldout contract object')
    preparation_75 = c.get('version') == VERSION_75
    set_version = SET_VERSION_75 if preparation_75 else SET_VERSION
    require(set(c) == {'version', 'scope', 'sourceCommit', 'model',
        'setVersion', 'caseCount', 'repetitions', 'budget', 'inputSha256',
        'certifiesBehavior', 'certifiesSkillGate'} | ({'productSourceCommit'} if preparation_75 else set()),
        'heldout contract inventory')
    require(c['version'] in (VERSION, VERSION_75) and c['scope'] == 'private-six-skill-input-binding-only'
        and isinstance(c['sourceCommit'], str) and re.fullmatch(r'[0-9a-f]{40}', c['sourceCommit']) is not None
        and c['model'] == 'gpt-6.1-sol' and c['setVersion'] == set_version,
        'heldout contract identity')
    require(type(c['caseCount']) is int and c['caseCount'] == 12
        and type(c['repetitions']) is int and c['repetitions'] == 2
        and trace.json_equal(c['budget'], dict(primary=24, independent=24, automaticRetries=0, delegations=0))
        and c['certifiesBehavior'] is False and c['certifiesSkillGate'] is False, 'heldout finite limits')
    require(isinstance(c['inputSha256'], dict) and set(c['inputSha256']) == set(INPUT_NAMES), 'heldout pins')
    for name, raw in raw_inputs.items():
        require(io.pin(c['inputSha256'][name]) == io.sha(raw), 'heldout input drift')
    review = parse(raw_inputs['reviewedSet'])
    require(isinstance(review, dict) and review.get('status') == 'semantic_review_and_parent_audit_passed'
        and review.get('setVersion') == set_version and type(review.get('caseCount')) is int
        and review['caseCount'] == 12 and review.get('casesSha256') == c['inputSha256']['cases']
        and review.get('caseSetAcceptedForMeasurementPreparation') is True, 'heldout adopted set')
    independent = review.get('independentReview')
    require(isinstance(independent, dict) and independent.get('status') == 'passed'
        and trace.json_equal(independent.get('severityCounts'), dict(P1=0, P2=0))
        and type(independent.get('routingSemanticsPassedCount')) is int
        and independent['routingSemanticsPassedCount'] == 12, 'heldout semantic review')
    if preparation_75:
        require(c['productSourceCommit'] == review.get('productSourceCommit') == PRODUCT_SOURCE_75,
            'heldout fixed 75-resource product')
        require(trace.json_equal(independent.get('novelNewCaseCount'), 12),
            'heldout new-set novelty review')
        io.pin(independent.get('receiptSha256'))
    envelope = parse(raw_inputs['cases'])
    require(isinstance(envelope, dict) and set(envelope) == {'setVersion', 'cases'}
        and envelope['setVersion'] == set_version, 'heldout envelope')
    cases = envelope['cases']
    require(isinstance(cases, list) and len(cases) == 12, 'heldout case count')
    schema = parse(raw_inputs['caseSchema'])
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    require(all(validator.is_valid(case) for case in cases), 'heldout case schema')
    first_case_number = 1300 if preparation_75 else 1200
    require([case['caseId'] for case in cases] == [f'SE-{n}' for n in range(first_case_number, first_case_number+12)]
        and all(case['mandatory'] is True for case in cases), 'heldout identities and mandatory cases')
    require(dict(Counter(case['category'] for case in cases)) == CATEGORY_COUNTS, 'heldout categories')
    for capability in trace.SKILLS:
        pair = [case for case in cases if case['capability'] == capability]
        require(len(pair) == 2 and sum(case['category'] in {'explicit', 'implicit', 'contextual'}
            for case in pair) == 1, 'heldout capability denominators')
    catalog = parse(raw_inputs['catalog'])
    require(isinstance(catalog, dict) and set(catalog) == {'schemaVersion', 'catalogVersion', 'events'}
        and catalog['schemaVersion'] == '1.0' and isinstance(catalog['catalogVersion'], str)
        and bool(catalog['catalogVersion'].strip()), 'heldout catalog')
    events = catalog['events']
    require(isinstance(events, list) and events and all(isinstance(e, str) and e.strip() for e in events)
        and len(events) == len(set(events)), 'heldout catalog events')
    for case in cases:
        expected = case['expected']
        require(all(e in events for e in expected['requiredEvents'] + expected['forbiddenEvents'])
            and not set(expected['requiredEvents']) & set(expected['forbiddenEvents']), 'heldout expected events')
    protocol = parse(raw_inputs['protocol'])
    require(isinstance(protocol, dict) and protocol.get('evaluationSetVersion') == '0.7.2'
        and protocol.get('eventCatalogVersion') == catalog['catalogVersion']
        and trace.json_equal(protocol.get('minimumRepetitions'), dict(prototype=2, release=3)), 'heldout protocol')
    try:
        instructions = raw_inputs['instructions'].decode('utf-8')
    except UnicodeError:
        raise ValueError('heldout instructions rejected') from None
    require(bool(instructions.strip()), 'heldout instructions')
    projected_cases = [trace.project_case(case) for case in cases]
    if preparation_75:
        require(len({io.encoded(case) for case in projected_cases}) == 12,
            'heldout duplicate model input')
    payloads = tuple(io.encoded(dict(instructions=instructions, eventCatalog=catalog,
        case=case)) for case in projected_cases)
    return HeldoutInputs(contract_raw, io.encoded(cases), payloads)


def private_bytes(path):
    """絶対pathの全成分をNOFOLLOWで開き、owner-only通常fileを同じfdで読む。"""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'heldout private absolute path')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        parent = os.fstat(directory)
        require(stat.S_IMODE(parent.st_mode) == 0o700 and parent.st_uid == os.getuid(), 'heldout private directory')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_uid == os.getuid() and before.st_nlink == 1
                and 0 < before.st_size <= 4*1024*1024, 'heldout private file')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(4*1024*1024+1)
            after = os.fstat(fd)
            require(before == after and len(raw) == before.st_size, 'heldout private file drift')
            return raw
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def prepare(repository, source, *, cases_75=None):
    """公開sourceを先に照合し、固定の採用集合だけを内部読取りする。保存・起動なし。"""
    require(isinstance(source, str) and re.fullmatch(r'[0-9a-f]{40}', source) is not None, 'heldout fixed source')
    public_paths = PUBLIC_PATHS if cases_75 is None else dict(PUBLIC_PATHS, reviewedSet=REVIEW_PATH_75)
    fixed = {}
    for name in (*public_paths.values(), *SOURCE_DEPENDENCIES):
        raw = guard.git(repository, 'show', source+':'+name)
        require(io.read_regular(repository/name) == raw, 'heldout source drift')
        fixed[name] = raw
    raws = {key: fixed[name] for key, name in public_paths.items()}
    raws['cases'] = private_bytes(PRIVATE_CASES if cases_75 is None else cases_75)
    contract = dict(version=VERSION, scope='private-six-skill-input-binding-only', sourceCommit=source,
        model='gpt-6.1-sol', setVersion=SET_VERSION, caseCount=12, repetitions=2,
        budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0),
        inputSha256={name: io.sha(raw) for name, raw in raws.items()},
        certifiesBehavior=False, certifiesSkillGate=False)
    if cases_75 is not None:
        contract.update(version=VERSION_75, setVersion=SET_VERSION_75, productSourceCommit=PRODUCT_SOURCE_75)
    return bind(io.encoded(contract), **raws)


def main():
    parser = argparse.ArgumentParser(description='保持24枠の無課金入力準備（公開出力は集計だけ）')
    parser.add_argument('--source', required=True)
    parser.add_argument('--cases-75', type=Path, help='採用済み75資源向け集合の非公開ファイル（絶対パス）')
    args = parser.parse_args()
    try:
        bound = prepare(Path(__file__).resolve().parents[3], args.source, cases_75=args.cases_75)
        print(io.encoded(bound.public_summary()).decode())
        return 0
    except Exception as exc:
        print(io.encoded(dict(status='heldout_input_preparation_rejected', errorType=type(exc).__name__,
            privateContentsPublished=False, modelInvocations=0, reservations=0)).decode())
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
