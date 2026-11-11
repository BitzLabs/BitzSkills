"""合成12件で非公開入力分離・採用hash・24分母・安全な読取りを検証。モデル0。"""
from contextlib import redirect_stdout
import copy
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_execution as execution
import production_heldout_inputs as held


class HeldoutInputTests(unittest.TestCase):
    def setUp(self):
        self.raws = {name: (ROOT/path).read_bytes() for name, path in held.PUBLIC_PATHS.items()}
        # 公開fixtureからの合成。非公開の実ケースは試験で読み取らない。
        public = held.parse((ROOT/'evals/skills/cases/routing.json').read_bytes())
        self.cases = []
        for index, skill in enumerate(sorted(held.trace.SKILLS)):
            base = copy.deepcopy(next(c for c in public if c['capability'] == skill))
            base.update(caseId=f'SE-{1200+index*2}', mandatory=True,
                category=['explicit', 'implicit', 'contextual'][index//2],
                prompt=f'SYNTHETIC_PRIVATE_PROMPT_{index}', context=[f'SYNTHETIC_CONTEXT_{index}'])
            self.cases.append(base)
            other = copy.deepcopy(base)
            other.update(caseId=f'SE-{1201+index*2}', category='negative' if index < 3 else 'safety')
            self.cases.append(other)
        self.review = dict(status='semantic_review_and_parent_audit_passed', setVersion=held.SET_VERSION,
            caseCount=12, caseSetAcceptedForMeasurementPreparation=True,
            independentReview=dict(status='passed', severityCounts=dict(P1=0, P2=0), routingSemanticsPassedCount=12))
        self.contract = dict(version=held.VERSION, scope='private-six-skill-input-binding-only',
            sourceCommit='a'*40, model='gpt-6.1-sol', setVersion=held.SET_VERSION, caseCount=12, repetitions=2,
            budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0),
            inputSha256={}, certifiesBehavior=False, certifiesSkillGate=False)
        self.repin_cases()

    def repin_cases(self):
        self.raws['cases'] = held.io.encoded(dict(setVersion=self.contract['setVersion'], cases=self.cases))
        self.review['casesSha256'] = held.io.sha(self.raws['cases'])
        self.raws['reviewedSet'] = held.io.encoded(self.review)
        self.repin()

    def repin(self):
        self.contract['inputSha256'] = {name: held.io.sha(raw) for name, raw in self.raws.items()}

    def bind(self):
        return held.bind(held.io.encoded(self.contract), **self.raws)

    def test_24_slots_and_only_prompt_context_in_model_payload(self):
        bound = self.bind()
        slots = [bound.slot(n) for n in range(1, 25)]
        self.assertEqual(len({(s['caseId'], s['repetition']) for s in slots}), 24)
        self.assertEqual(slots[-1]['caseId'], 'SE-1211')
        for raw in bound.payloads:
            payload = held.parse(raw)
            self.assertEqual(set(payload), {'instructions', 'eventCatalog', 'case'})
            self.assertEqual(set(payload['case']), {'prompt', 'context'})
        for value in [0, 25, True, 1.0]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                bound.slot(value)

    def test_expectation_changes_do_not_change_primary_payload(self):
        before = self.bind().payloads
        self.cases[0]['expected']['outcome'] = 'stop'
        self.repin_cases()
        self.assertEqual(before, self.bind().payloads)

    def test_public_summary_and_repr_do_not_contain_private_inputs_or_case_labels(self):
        bound = self.bind()
        output = held.io.encoded(bound.public_summary()).decode() + repr(bound)
        for case in self.cases:
            for forbidden in [case['prompt'], case['context'][0], case['caseId']]:
                self.assertNotIn(forbidden, output)
        self.assertNotIn('payloadSha256', output)
        self.assertEqual(bound.public_summary()['modelInvocations'], 0)

    def test_review_pin_failure_and_not_adopted_set_rejected(self):
        self.review['casesSha256'] = '0'*64
        self.raws['reviewedSet'] = held.io.encoded(self.review)
        self.repin()
        with self.assertRaises(ValueError): self.bind()
        self.repin_cases()
        for key, value in [('status', 'stopped'), ('caseSetAcceptedForMeasurementPreparation', False),
                           ('caseCount', True)]:
            old = self.review[key]
            self.review[key] = value
            self.repin_cases()
            with self.subTest(key=key), self.assertRaises(ValueError): self.bind()
            self.review[key] = old

    def test_review_p2_rejected(self):
        self.review['independentReview']['severityCounts']['P2'] = 1
        self.repin_cases()
        with self.assertRaises(ValueError): self.bind()

    def test_wrong_budget_type_scope_and_model_rejected(self):
        original = copy.deepcopy(self.contract)
        for key, value in [('repetitions', True), ('caseCount', True), ('model', 'other'),
                           ('sourceCommit', 'main'), ('scope', 'public-six-skill-input-binding-only'),
                           ('certifiesSkillGate', True)]:
            self.contract = copy.deepcopy(original)
            self.contract[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.bind()
        for value in [True, 23, 25]:
            self.contract = copy.deepcopy(original)
            self.contract['budget']['primary'] = value
            with self.subTest(budget=value), self.assertRaises(ValueError): self.bind()

    def test_wrong_case_denominators_and_schema_rejected_without_secret_in_errors(self):
        original = copy.deepcopy(self.cases)
        variants = [original[:-1], list(reversed(original))]
        unknown = copy.deepcopy(original)
        unknown[0]['SYNTHETIC_SECRET_EXTRA_FIELD'] = 'SYNTHETIC_SECRET_VALUE'
        variants.append(unknown)
        category = copy.deepcopy(original)
        category[0]['category'] = 'negative'
        variants.append(category)
        for cases in variants:
            self.cases = cases
            self.repin_cases()
            with self.subTest(size=len(cases)), self.assertRaises(ValueError) as error:
                self.bind()
            self.assertNotIn('SYNTHETIC_SECRET', str(error.exception))

    def test_unknown_or_contradictory_events_rejected(self):
        for event in ['invented-event', self.cases[0]['expected']['requiredEvents'][0]]:
            self.cases[0]['expected']['forbiddenEvents'] = [event]
            self.repin_cases()
            with self.subTest(event=event), self.assertRaises(ValueError): self.bind()

    def test_unknown_raw_and_mutated_fixed_input_rejected(self):
        self.raws['instructions'] += b'changed'
        with self.assertRaises(ValueError): self.bind()
        self.repin()
        self.raws['unknown'] = b'{}'
        with self.assertRaises(ValueError): self.bind()

    def test_private_reader_rejects_permissions_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            os.chmod(directory, 0o700)
            path = directory/'cases.json'
            path.write_bytes(b'private-test')
            path.chmod(0o600)
            self.assertEqual(held.private_bytes(path), b'private-test')
            path.chmod(0o644)
            with self.assertRaises(ValueError): held.private_bytes(path)
            path.chmod(0o600)
            alias = directory/'alias'
            alias.symlink_to(path)
            with self.assertRaises(OSError): held.private_bytes(alias)
            os.link(path, directory/'hardlink')
            with self.assertRaises(ValueError): held.private_bytes(path)

    def test_prepare_rejects_source_drift_before_reading_private_cases(self):
        with patch.object(held.guard, 'git', return_value=b'fixed'), \
             patch.object(held.io, 'read_regular', return_value=b'drift'), \
             patch.object(held, 'private_bytes') as reader:
            with self.assertRaises(ValueError): held.prepare(ROOT, 'a'*40)
            reader.assert_not_called()

    def test_host_dependency_drift_rejected_before_private_read_with_real_git(self):
        source = held.guard.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
        gitdir = held.guard.git(ROOT, 'rev-parse', '--absolute-git-dir').decode().strip()
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp)
            (mirror/'.git').write_text('gitdir: '+gitdir+'\n')
            for name in held.SOURCE_FILES:
                path = mirror/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(held.guard.git(ROOT, 'show', source+':'+name))
            host = mirror/'evals/skills/routing/host.py'
            host.write_bytes(host.read_bytes()+b'\n# synthetic drift\n')
            # Git読取りは実処理。private readerだけ合成境界へ置換する。
            with patch.object(held, 'private_bytes', side_effect=ValueError('synthetic boundary')) as reader:
                with self.assertRaises(ValueError): held.prepare(mirror, source)
                reader.assert_not_called()

    def test_json_diagnostic_hides_raw_values(self):
        for raw in [b'{"SYNTHETIC_SECRET":"broken}', b'{"x":1,"x":2}', b'{"x":NaN}']:
            with self.assertRaises(ValueError) as error: held.parse(raw)
            self.assertEqual(str(error.exception), 'heldout JSON rejected')


    def select_75_resources(self):
        self.contract.update(version=held.VERSION_75, setVersion=held.SET_VERSION_75,
            productSourceCommit=held.PRODUCT_SOURCE_75)
        self.review.update(setVersion=held.SET_VERSION_75, productSourceCommit=held.PRODUCT_SOURCE_75)
        self.review['independentReview'].update(novelNewCaseCount=12, receiptSha256='b'*64)
        for index, case in enumerate(self.cases):
            case.update(caseId=f'SE-{1300+index}', prompt=f'SYNTHETIC_75_PROMPT_{index}')
        self.repin_cases()

    def test_75_preparation_reads_fixed_review_and_explicit_private_input(self):
        self.select_75_resources()
        fixed = {path: self.raws[name] for name, path in held.PUBLIC_PATHS.items() if name != 'reviewedSet'}
        fixed[held.REVIEW_PATH_75] = self.raws['reviewedSet']
        fixed.update({path: (ROOT/path).read_bytes() for path in held.SOURCE_DEPENDENCIES})
        source = self.contract['sourceCommit']
        cases_path = ROOT/'.venv'/'synthetic-cases.json'
        with patch.object(held.guard, 'git', side_effect=lambda _, command, ref: fixed[ref.removeprefix(source+':')]), \
             patch.object(held.io, 'read_regular', side_effect=lambda path: fixed[path.relative_to(ROOT).as_posix()]), \
             patch.object(held, 'private_bytes', return_value=self.raws['cases']) as reader:
            prepared = held.prepare(ROOT, source, cases_75=cases_path)
            reader.assert_called_once_with(cases_path)
            with patch.object(sys, 'argv', ['prepare', '--source', source, '--cases-75', str(cases_path)]), \
                 redirect_stdout(StringIO()) as output:
                self.assertEqual(held.main(), 0)
            self.assertEqual(held.parse(output.getvalue().encode()), prepared.public_summary())
            reader.reset_mock()
            fixed.pop(held.REVIEW_PATH_75)
            with self.assertRaises(KeyError):
                held.prepare(ROOT, source, cases_75=cases_path)
            reader.assert_not_called()
        self.assertEqual(prepared.contract_raw, held.io.encoded(self.contract))
        self.assertEqual(prepared.public_summary()['setVersion'], held.SET_VERSION_75)
        self.assertEqual(prepared.public_summary()['productSourceCommit'], held.PRODUCT_SOURCE_75)
        self.assertEqual(prepared.public_summary()['plannedPrimary'], 24)
        self.assertEqual(prepared.slot(24)['caseId'], 'SE-1311')
        self.assertEqual(len({(prepared.slot(n)['caseId'], prepared.slot(n)['repetition'])
            for n in range(1, 25)}), 24)
        self.assertNotIn(b'SYNTHETIC_75_PROMPT', held.io.encoded(prepared.public_summary()))
        self.assertEqual(set(held.parse(prepared.payloads[0])['case']), {'prompt', 'context'})
        with patch.object(execution, 'execution_contract', return_value={}):
            with self.assertRaisesRegex(ValueError, 'input version is preparation-only'):
                execution.bind(b'', b'', prepared.contract_raw, **self.raws)

    def test_75_preparation_requires_review_and_product_identity(self):
        self.select_75_resources()
        original = copy.deepcopy(self.review)
        for key, value in [('productSourceCommit', 'f'*40), ('setVersion', held.SET_VERSION)]:
            self.review = dict(original, **{key: value})
            self.repin_cases()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.bind()
        self.review = original
        self.review['independentReview']['novelNewCaseCount'] = 11
        self.repin_cases()
        with self.assertRaisesRegex(ValueError, 'novelty review'):
            self.bind()

    def test_75_preparation_rejects_invalid_case_order_and_distribution(self):
        self.select_75_resources()
        self.cases[1]['prompt'] = self.cases[0]['prompt']
        self.repin_cases()
        with self.assertRaisesRegex(ValueError, 'duplicate model input'):
            self.bind()
        self.cases[1]['prompt'] += '_distinct'
        self.cases[1]['capability'] = self.cases[2]['capability']
        self.repin_cases()
        with self.assertRaisesRegex(ValueError, 'capability denominators'):
            self.bind()
        self.cases.reverse()
        self.repin_cases()
        with self.assertRaisesRegex(ValueError, 'identities and mandatory cases'):
            self.bind()
