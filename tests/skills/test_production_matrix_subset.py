"""有限subsetの入力・消費・停止を合成原で検査。モデル/予約の実運用は行わない。"""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_ledger as matrix
import production_matrix_semantic as semantic
import test_production_matrix_ledger as fixture


class MatrixSubsetTests(unittest.TestCase):
    def setUp(self):
        f=fixture.MatrixLedgerTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.f=f
        inputs=matrix.strict_json(f.input_raw)
        inputs.update(version=matrix.inputs.SUBSET_VERSION,scope='public-six-skill-subset-input-binding-only',
            caseIds=['SE-004','SE-014','SE-039'],budget=dict(primary=6,independent=6,automaticRetries=0,delegations=0))
        f.input_raw=matrix.io.encoded(inputs)
        f.contract.update(version=matrix.SUBSET_VERSION,caseIds=inputs['caseIds'],
            budget=inputs['budget'],inputContractSha256=matrix.io.sha(f.input_raw))
        f.bound=f.bind();f.instance=f.open()

    def test_arbitrary_cases_have_dense_ordinals_and_exact_original_payloads(self):
        f=self.f
        self.assertEqual([f.bound.slot(n)['caseId'] for n in range(1,7)],
            ['SE-004','SE-004','SE-014','SE-014','SE-039','SE-039'])
        self.assertEqual([f.bound.slot(n)['repetition'] for n in range(1,7)],[1,2,1,2,1,2])
        contract=matrix.strict_json(f.input_raw);contract.update(version=matrix.inputs.VERSION,
            scope='public-six-skill-input-binding-only',budget=dict(primary=92,independent=92,automaticRetries=0,delegations=0))
        del contract['caseIds']
        full=matrix.inputs.bind(matrix.io.encoded(contract),**f.raws)
        for local,original in [(1,7),(3,27),(5,77)]:
            self.assertEqual(f.bound.slot(local)['payloadSha256'],full.slot(original)['payloadSha256'])
        for raw in f.bound.matrix.payloads:
            value=matrix.strict_json(raw)
            self.assertEqual(set(value),{'instructions','eventCatalog','case'})
            self.assertEqual(set(value['case']),{'prompt','context'})
        for ordinal in [0,7,True]:
            with self.subTest(ordinal=ordinal),self.assertRaises(ValueError):f.bound.slot(ordinal)

    def test_subset_completion_counts_only_selected_slots_and_cannot_reserve_seventh(self):
        f=self.f
        self.assertIsInstance(matrix.open_ledger(f.storage,f.repository,f.bound),matrix.MatrixLedger)
        for ordinal in range(1,7):f.complete(ordinal,correct=ordinal!=3)
        result=f.instance.summary()
        self.assertEqual((result['status'],result['maximumPrimary'],result['primaryReserved'],
            result['parentVerified'],result['measuredCorrect'],result['measuredIncorrect'],result['missingMeasurements']),
            ('complete',6,6,6,5,1,0))
        with self.assertRaises(ValueError):f.instance.reserve(7)
        self.assertEqual(f.instance.summary(),result)
        self.assertFalse((f.storage/'attempt-0007.json').exists())

    def test_stop_retains_consumption_and_missing_selected_slots(self):
        f=self.f;f.prepare_primary(1);f.instance.record_interruption(1,'primary')
        result=f.instance.summary()
        self.assertEqual((result['status'],result['primaryReserved'],result['primaryLaunchMarked'],result['missingMeasurements']),
            ('stopped',1,1,6))
        with self.assertRaises(ValueError):f.instance.reserve(2)
        self.assertEqual(f.instance.summary(),result)

    def test_invalid_selection_and_budget_are_rejected(self):
        f=self.f;valid=matrix.strict_json(f.input_raw)
        for ids in [[],['SE-014','SE-004'],['SE-014','SE-014'],['SE-047'],[True],list(range(3)),[f'SE-{n:03d}' for n in range(1,47)]]:
            value=copy.deepcopy(valid);value['caseIds']=ids
            with self.subTest(ids=ids),self.assertRaises(ValueError):matrix.inputs.bind(matrix.io.encoded(value),**f.raws)
        for value in [dict(primary=92,independent=92,automaticRetries=0,delegations=0),
                dict(primary=6,independent=6,automaticRetries=1,delegations=0)]:
            c=copy.deepcopy(valid);c['budget']=value
            with self.assertRaises(ValueError):matrix.inputs.bind(matrix.io.encoded(c),**f.raws)
            c=copy.deepcopy(f.contract);c['budget']=value
            with self.assertRaises(ValueError):matrix.execution_contract(matrix.io.encoded(c))

    def test_execution_input_selection_and_version_cannot_be_mixed(self):
        f=self.f
        for changes in [dict(caseIds=['SE-004','SE-014','SE-038']),dict(version=matrix.VERSION),dict(version=matrix.SURVEY_VERSION)]:
            c=copy.deepcopy(f.contract);c.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                matrix.bind(matrix.io.encoded(c),f.input_raw,**f.raws)

    def test_unknown_ledger_files_above_subset_budget_stop_the_scope(self):
        f=self.f;f.instance.reserve(1)
        (f.storage/'attempt-0007.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):f.instance.reserve(2)
        self.assertTrue((f.storage/'stop.json').exists())

    def test_semantic_review_is_bound_to_selected_case_and_finite_budget(self):
        f=self.f;decision=dict(selectedEntry='quality-plan',selectedPath=None,outcome='proceed',events=['classify-risk'])
        original=dict(method='item/completed',params=dict(item=dict(type='agentMessage',phase='final_answer',text=matrix.io.encoded(decision).decode())))
        context=SimpleNamespace(bound=f.bound,ordinal=1,receipt_raw=b'{}',
            originals={'rpc-out.jsonl':matrix.io.encoded(original)+b'\n','model-input.json':f.bound.matrix.payloads[0]})
        with patch.object(semantic.provider,'verify_bytes',return_value=dict(native=dict(decision=decision))):
            prepared=semantic.prepare(context,source_repository=f.repository,artifact_repository=f.repository)
        contract=matrix.strict_json(prepared.contract_raw);data=matrix.strict_json(prepared.input_raw)
        self.assertEqual(contract['maximumIndependentCampaignInvocations'],6)
        self.assertEqual(contract['scope'],'public-subset-times2-semantic-response-binding-only')
        self.assertEqual(data['slot']['caseId'],'SE-004')
        self.assertIn('選択された公開3ケース×2',data['limitations'][0])
        self.assertEqual(data['expected']['requiredEvents'],['classify-risk'])
        self.assertEqual(contract['automaticRetries'],0)
        self.assertFalse(contract['certifiesSkillGate'])


class MatrixSubsetCaptureTests(unittest.TestCase):
    """実argv/予約/起動印の連鎖を、subprocessと認証だけ合成で置換して検査する。"""
    def setUp(self):
        import test_production_matrix_capture as capture_fixture
        f=capture_fixture.MatrixCaptureTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.f=f;self.capture=capture_fixture.capture;r=f.r
        selected=['SE-004','SE-014','SE-039'];budget=dict(primary=6,independent=6,automaticRetries=0,delegations=0)
        r.input_contract.update(version=matrix.inputs.SUBSET_VERSION,scope='public-six-skill-subset-input-binding-only',
            caseIds=selected,budget=budget)
        r.input_raw=matrix.io.encoded(r.input_contract)
        r.execution.update(version=matrix.SUBSET_VERSION,caseIds=selected,budget=budget,
            inputContractSha256=matrix.io.sha(matrix.io.encoded(r.input_contract)))
        r.bound=r.bind();r.deployment['executionSha256']=matrix.io.sha(r.bound.execution_raw);f.make_review()

    def test_actual_invocation_uses_selected_case_for_every_dense_slot(self):
        f=self.f;c=self.capture;r=f.r
        for ordinal in range(1,7):
            base=f.base.parent/f'attempt-{ordinal:04d}'
            value=c.invocation_for_slot(f.repository,base,r.bound.execution_raw,matrix.io.encoded(r.deployment),r.bound.slot(ordinal))
            self.assertEqual(value['slot'],r.bound.slot(ordinal))
            self.assertIn('--isolated',value['argv'])
            self.assertEqual(value['automaticRetries'],0)
        f.spawn.assert_not_called()

    def test_wrong_case_repetition_and_out_of_budget_slot_are_rejected(self):
        f=self.f;c=self.capture;r=f.r
        for updates in [dict(caseId='SE-001'),dict(caseId='SE-014'),dict(repetition=2),dict(ordinal=7)]:
            slot=dict(r.bound.slot(1),**updates);base=f.base.parent/f"attempt-{slot['ordinal']:04d}"
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                c.invocation_for_slot(f.repository,base,r.bound.execution_raw,matrix.io.encoded(r.deployment),slot)
        f.spawn.assert_not_called()

    def test_capture_reserves_selected_slot_before_single_synthetic_spawn(self):
        f=self.f;result=f.run_capture()
        self.assertEqual(result['status'],'primary_capture_awaits_independent_review')
        f.spawn.assert_called_once()
        summary=f.summary()
        self.assertEqual((summary['maximumPrimary'],summary['primaryReserved'],summary['primaryLaunchMarked']), (6,1,1))
        self.assertEqual(f.r.bound.slot(1)['caseId'],'SE-004')
        with self.assertRaises(ValueError):f.run_capture()
        f.spawn.assert_called_once()


if __name__=='__main__':unittest.main()
