"""公開行列の欠測・期待値混入・予算/入力driftを起動前に拒否。モデル0。"""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_matrix_inputs as matrix


class MatrixInputTests(unittest.TestCase):
    def setUp(self):
        paths=dict(routing='cases/routing.json',behaviorSafety='cases/behavior-safety.json',protocol='protocol.json',
                   catalog='event-catalog.json',instructions='routing/production-matrix-instructions-v0.1.txt',caseSchema='schemas/case.schema.json')
        self.raws={k:(ROOT/'evals/skills'/p).read_bytes() for k,p in paths.items()}
        self.contract=dict(version='public-production-matrix-inputs-0.1.0',scope='public-six-skill-input-binding-only',sourceCommit='a'*40,
                           model='gpt-6.1-sol',repetitions=2,budget=dict(primary=92,independent=92,automaticRetries=0,delegations=0),
                           inputSha256={k:matrix.ledger.sha(v) for k,v in self.raws.items()},certifiesBehavior=False,certifiesSkillGate=False)

    def bind(self):
        return matrix.bind(matrix.ledger.encoded(self.contract),**self.raws)

    def change(self,name,value):
        self.raws[name]=matrix.ledger.encoded(value)
        self.contract['inputSha256'][name]=matrix.ledger.sha(self.raws[name])

    def test_all_slots_have_exact_denominators_and_no_metadata_in_payload(self):
        bound=self.bind();slots=[bound.slot(n) for n in range(1,93)]
        self.assertEqual(len({(s['caseId'],s['repetition']) for s in slots}),92)
        self.assertEqual(slots[-1]['caseId'],'SE-046')
        for raw in bound.payloads:
            value=matrix.trace.strict_json(raw)
            self.assertEqual(set(value),{'instructions','eventCatalog','case'})
            self.assertEqual(set(value['case']),{'prompt','context'})
        for ordinal in [0,93,True,1.0]:
            with self.subTest(ordinal=ordinal),self.assertRaises(ValueError):bound.slot(ordinal)

    def test_expectation_change_does_not_change_primary_payload(self):
        before=self.bind().payloads
        cases=matrix.trace.strict_json(self.raws['routing']);cases[0]['expected']['outcome']='stop'
        self.change('routing',cases)
        self.assertEqual(before,self.bind().payloads)

    def test_changed_fixed_bytes_and_unknown_inventory_rejected(self):
        self.raws['instructions']+=b'changed'
        with self.assertRaises(ValueError):self.bind()
        self.raws['unknown']=b'{}'
        with self.assertRaises(ValueError):self.bind()

    def test_wrong_budget_type_scope_model_and_certification_rejected(self):
        original=copy.deepcopy(self.contract)
        for key,value in [('repetitions',True),('model','other'),('sourceCommit','main'),('certifiesSkillGate',True),('scope','public-production-routing-canary-only')]:
            self.contract=copy.deepcopy(original);self.contract[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()
        for value in [True,91,93]:
            self.contract=copy.deepcopy(original);self.contract['budget']['primary']=value
            with self.subTest(budget=value),self.assertRaises(ValueError):self.bind()

    def test_missing_duplicate_reordered_and_wrong_category_cases_rejected(self):
        original=matrix.trace.strict_json(self.raws['routing'])
        variants=[original[:-1], [original[0]]+original[:-1], list(reversed(original))]
        changed=copy.deepcopy(original);changed[0]['category']='negative';variants.append(changed)
        for cases in variants:
            self.change('routing',cases)
            with self.subTest(caseCount=len(cases)),self.assertRaises(ValueError):self.bind()

    def test_unknown_and_contradictory_expected_events_rejected(self):
        for event in ['invented-event','select-doctor']:
            cases=matrix.trace.strict_json(self.raws['routing']);cases[0]['expected']['forbiddenEvents']=[event]
            self.change('routing',cases)
            with self.subTest(event=event),self.assertRaises(ValueError):self.bind()

    def test_canonical_matrix_payload_requests_null_path_for_every_six_skill_case(self):
        sys.path.insert(0,str(ROOT/'evals/skills'))
        import validate
        bound=self.bind()
        for case,raw in zip(bound.cases,bound.payloads):
            payload=matrix.trace.strict_json(raw)
            self.assertEqual(validate.expected_route(case,'six-skill')[1],None)
            self.assertIn('selectedPathは常にnull',payload['instructions'])
            self.assertNotIn('bitz-core=operate',payload['instructions'])
