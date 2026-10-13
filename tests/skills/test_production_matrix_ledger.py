"""行列台帳の隔離試験。原取得とモデル呼出しは行わない。"""
from dataclasses import replace
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_matrix_ledger as matrix
import test_production_matrix_inputs as fixture_inputs


def contend(storage, repository, bound, ready, go, queue):
    instance = matrix.MatrixLedger(Path(storage), Path(repository), bound)
    ready.set()
    go.wait(10)
    try:
        instance.reserve(1)
        queue.put('reserved')
    except ValueError:
        queue.put('rejected')


class MatrixLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp')
        self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name)
        (self.repository/'.venv').mkdir()
        fixture = fixture_inputs.MatrixInputTests(methodName='runTest')
        fixture.setUp()
        self.raws = fixture.raws
        self.input_raw = matrix.io.encoded(fixture.contract)
        self.contract = dict(version=matrix.VERSION, campaignId='public-matrix-synthetic', sourceCommit='a'*40,
            model='gpt-6.1-sol', inputContractSha256=matrix.io.sha(self.input_raw),
            outputRelativeRoot='.venv/matrix-synthetic', pins={n:'b'*64 for n in matrix.PINS},
            budget=dict(primary=92, independent=92, automaticRetries=0, delegations=0),
            timeoutSeconds=dict(primary=240, independent=300), cliVersion='0.160.1', certifiesSkillGate=False)
        self.bound = self.bind()
        self.storage = self.repository/'.venv/ledger'
        self.instance = self.open()

    def bind(self):
        return matrix.bind(matrix.io.encoded(self.contract), self.input_raw, **self.raws)

    def open(self, bound=None):
        return matrix.MatrixLedger(self.storage, self.repository, bound or self.bound)

    def original(self, ordinal, name, raw=b'public synthetic original'):
        relative=Path(self.contract['outputRelativeRoot'])/f'attempt-{ordinal:04d}'/name
        path=self.repository/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
        return dict(relativePath=relative.as_posix(), sha256=matrix.io.sha(raw))

    def primary(self, ordinal=1):
        return dict(self.bound.slot(ordinal), actualInvocations=1, normalTerminal=True, nativeExitCode=0,
            integrityPassed=True, receipt=self.original(ordinal,'receipt.json'),
            trace=self.original(ordinal,'rpc-out.jsonl'))

    def prepare_primary(self, ordinal=1):
        self.instance.reserve(ordinal)
        self.instance.mark_primary_started(ordinal)
        self.instance.record_primary(ordinal,self.primary(ordinal))

    def review(self, ordinal=1, correct=True):
        return dict(self.bound.slot(ordinal), status='measured_correct' if correct else 'measured_incorrect',
            accuracy=correct, safetyPassed=True, integrityPassed=True, independentContext=True,
            severityCounts={'P1':0,'P2':0},
            primaryRecordSha256=matrix.io.sha(matrix.io.read_regular(self.instance.path('primary',ordinal))),
            independentReservationSha256=matrix.io.sha(matrix.io.read_regular(self.instance.path('independent',ordinal))),
            independentReceipt=self.original(ordinal,'independent-receipt.json'),
            parentVerification=self.original(ordinal,'parent-verification.json'), certifiesSkillGate=False)

    def complete(self, ordinal=1, correct=True):
        self.prepare_primary(ordinal)
        self.instance.reserve_independent(ordinal,'c'*64)
        self.instance.record_review(ordinal,matrix.io.encoded(self.review(ordinal,correct)))

    def test_safe_incorrect_measurement_remains_in_denominator_and_allows_next(self):
        self.complete(correct=False)
        self.assertEqual(self.instance.reserve(2)['repetition'],2)
        result=self.instance.summary()
        self.assertEqual((result['primaryReserved'],result['primaryCompleted'],result['parentVerified']), (2,1,1))
        self.assertEqual((result['measuredCorrect'],result['measuredIncorrect'],result['missingMeasurements']), (0,1,91))
        self.assertFalse(result['certifiesSkillGate'])

    def test_missing_review_waits_without_stopping_or_refunding(self):
        self.prepare_primary()
        self.instance.reserve_independent(1,'c'*64)
        with self.assertRaisesRegex(ValueError,'pending'):self.instance.reserve(2)
        self.assertFalse((self.storage/'stop.json').exists())
        self.instance.record_review(1,matrix.io.encoded(self.review()))
        self.assertEqual(self.open().reserve(2)['ordinal'],2)

    def test_invalid_submitted_review_permanently_stops_after_restoration(self):
        for raw in [b'{', b'[]', b'{"accuracy":NaN}', b'{"status":"x","status":"y"}']:
            with self.subTest(raw=raw):
                self.storage=self.repository/'.venv'/('ledger-'+str(len(list((self.repository/'.venv').iterdir()))))
                self.instance=self.open();self.prepare_primary();self.instance.reserve_independent(1,'c'*64)
                good=matrix.io.encoded(self.review())
                with self.assertRaises(ValueError):self.instance.record_review(1,raw)
                self.assertEqual((self.storage/'rejected-review-0001.bin').read_bytes(),raw)
                with self.assertRaisesRegex(ValueError,'permanently'):self.open().record_review(1,good)
                with self.assertRaises(ValueError):self.open().reserve(2)
                self.assertEqual(len(list(self.storage.glob('attempt-*.json'))),1)

    def test_failed_safety_and_false_evidence_cannot_be_safe_incorrect(self):
        for key,value in [('safetyPassed',False),('integrityPassed',False),('independentContext',False),
                          ('accuracy',0),('severityCounts',{'P1':0,'P2':1}),('severityCounts',{'P1':False,'P2':0}),
                          ('certifiesSkillGate',True),('ordinal',True)]:
            with self.subTest(key=key,value=value):
                self.storage=self.repository/'.venv'/('ledger-'+str(len(list((self.repository/'.venv').iterdir()))))
                self.instance=self.open();self.prepare_primary();self.instance.reserve_independent(1,'c'*64)
                review=self.review(correct=False);review[key]=value
                with self.assertRaises(ValueError):self.instance.record_review(1,matrix.io.encoded(review))
                self.assertTrue((self.storage/'stop.json').exists())

    def test_changed_original_permanently_stops_even_if_bytes_restored(self):
        self.complete()
        path=self.repository/self.review()['independentReceipt']['relativePath']
        before=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash drift'):self.instance.reserve(2)
        path.write_bytes(before)
        with self.assertRaisesRegex(ValueError,'permanently'):self.open().reserve(2)

    def test_interruption_consumes_one_slot_without_fake_measurement(self):
        self.instance.reserve(1);self.instance.mark_primary_started(1)
        self.instance.record_interruption(1,'primary')
        result=self.instance.summary()
        self.assertEqual((result['primaryReserved'],result['primaryLaunchMarked'],result['primaryCompleted']), (1,1,0))
        self.assertEqual(result['missingMeasurements'],92)
        with self.assertRaises(ValueError):self.open().reserve(1)

    def test_independent_interruption_preserves_both_consumed_reservations(self):
        self.prepare_primary();self.instance.reserve_independent(1,'c'*64)
        self.instance.record_interruption(1,'independent')
        result=self.instance.summary()
        self.assertEqual((result['primaryReserved'],result['primaryCompleted'],result['independentReserved']), (1,1,1))
        self.assertEqual((result['parentVerified'],result['missingMeasurements']), (0,92))
        with self.assertRaises(ValueError):self.open().reserve_independent(1,'c'*64)

    def test_all_92_slots_complete_once_and_reject_the_93rd(self):
        for ordinal in range(1,93):self.complete(ordinal,correct=ordinal%2==0)
        result=self.instance.summary()
        self.assertEqual(result['status'],'complete')
        self.assertEqual((result['primaryReserved'],result['primaryCompleted'],result['independentReserved'],result['parentVerified']), (92,92,92,92))
        self.assertEqual((result['measuredCorrect'],result['measuredIncorrect'],result['missingMeasurements']), (46,46,0))
        with self.assertRaises(ValueError):self.open().reserve(93)
        self.assertEqual(len(list(self.storage.glob('attempt-*.json'))),92)

    def test_double_reservation_wrong_order_and_bool_ordinal_do_not_consume(self):
        for ordinal in [0,True,1.0,2,93]:
            with self.subTest(ordinal=ordinal),self.assertRaises(ValueError):self.instance.reserve(ordinal)
        self.instance.reserve(1)
        for ordinal in [1,2]:
            with self.assertRaises(ValueError):self.open().reserve(ordinal)
        self.instance.mark_primary_started(1)
        with self.assertRaises(FileExistsError):self.open().mark_primary_started(1)
        self.instance.record_primary(1,self.primary())
        self.instance.reserve_independent(1,'c'*64)
        with self.assertRaises(FileExistsError):self.open().reserve_independent(1,'c'*64)
        self.assertEqual(len(list(self.storage.glob('attempt-*.json'))),1)

    def test_changed_execution_or_source_pair_cannot_reset_existing_ledger(self):
        self.instance.reserve(1)
        original=dict(self.contract)
        for key,value in [('outputRelativeRoot','.venv/other'),('pins',{n:'d'*64 for n in matrix.PINS})]:
            self.contract=dict(original);self.contract[key]=value
            changed=self.bind()
            with self.assertRaisesRegex(ValueError,'cannot reset'):self.open(changed).reserve(1)
        self.contract=dict(original);self.contract['sourceCommit']='f'*40
        with self.assertRaises(ValueError):self.bind()
        self.assertEqual(len(list(self.storage.glob('attempt-*.json'))),1)

    def test_storage_and_original_symlink_hardlink_and_path_escape_rejected(self):
        self.instance.reserve(1);self.instance.mark_primary_started(1)
        primary=self.primary();reference=primary['receipt'];p=self.repository/reference['relativePath']
        p.rename(p.with_name('saved.json'));p.symlink_to('saved.json')
        with self.assertRaises(OSError):self.instance.record_primary(1,primary)
        self.assertTrue((self.storage/'stop.json').exists())
        for relative in ['.venv/matrix-synthetic/attempt-0001/../receipt.json',
                         '.venv/matrix-synthetic/attempt-0001/state/receipt.json',
                         '/tmp/receipt.json']:
            with self.subTest(path=relative),self.assertRaises(ValueError):
                self.instance.original(dict(relativePath=relative,sha256='b'*64),1)
        link=self.repository/'.venv/storage-link';link.symlink_to(self.storage)
        with self.assertRaises(ValueError):matrix.MatrixLedger(link,self.repository,self.bound)
        with self.assertRaises(ValueError):matrix.MatrixLedger(self.repository/'.venv/../../outside',self.repository,self.bound)

    def test_hardlinked_original_rejected_and_consumption_not_refunded(self):
        self.instance.reserve(1);self.instance.mark_primary_started(1)
        primary=self.primary();path=self.repository/primary['receipt']['relativePath']
        os.link(path,path.with_name('linked.json'))
        with self.assertRaises(ValueError):self.instance.record_primary(1,primary)
        with self.assertRaisesRegex(ValueError,'permanently'):self.open().reserve(1)

    def test_shared_storage_uses_git_common_directory_across_worktrees(self):
        common=self.repository/'.git';common.mkdir()
        with patch.object(matrix.io.source_guard,'git',return_value=str(common).encode()):
            first=matrix.shared_storage(self.repository/'worktree-one',self.bound)
            second=matrix.shared_storage(self.repository/'worktree-two',self.bound)
        self.assertEqual(first,second)
        self.assertEqual(first,self.repository/'.venv/production-matrix-ledgers/public-matrix-synthetic')
        self.assertFalse(first.exists())

    def test_unknown_record_and_tampered_stage_are_quarantined(self):
        self.instance.reserve(1)
        matrix.io.exclusive(self.storage/'review-0002.json',b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        (self.storage/'review-0002.json').unlink()
        with self.assertRaisesRegex(ValueError,'permanently'):self.open().reserve(2)

    def test_malformed_stored_identity_cannot_reopen_after_restoration(self):
        self.prepare_primary()
        path=self.instance.path('attempt',1);before=path.read_bytes()
        corrupted=matrix.strict_json(before);corrupted['ordinal']=True;path.write_bytes(matrix.io.encoded(corrupted))
        with self.assertRaises(ValueError):self.instance.reserve_independent(1,'c'*64)
        path.write_bytes(before)
        with self.assertRaisesRegex(ValueError,'permanently'):self.open().reserve_independent(1,'c'*64)

    def test_contract_finite_budget_pins_and_immutable_payloads(self):
        original=dict(self.contract)
        for key,value in [('budget',dict(primary=True,independent=92,automaticRetries=0,delegations=0)),
                          ('timeoutSeconds',dict(primary=True,independent=300)),('model','other'),
                          ('inputContractSha256','d'*64),('outputRelativeRoot','../outside'),
                          ('pins',{'sdk':'b'*64}),('certifiesSkillGate',True)]:
            self.contract=dict(original);self.contract[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()
        forged=replace(self.bound,matrix=replace(self.bound.matrix,payloads=(b'forged',)*46))
        with self.assertRaises(ValueError):self.open(forged)

    def test_concurrent_first_reservation_consumes_exactly_one(self):
        context=multiprocessing.get_context('fork');ready=context.Event();go=context.Event();queue=context.Queue()
        process=context.Process(target=contend,args=(str(self.storage),str(self.repository),self.bound,ready,go,queue))
        process.start()
        try:
            self.assertTrue(ready.wait(10));go.set()
            try:self.instance.reserve(1);own='reserved'
            except ValueError:own='rejected'
            self.assertEqual(sorted([own,queue.get(timeout=15)]),['rejected','reserved'])
            process.join(15);self.assertEqual(process.exitcode,0)
            self.assertEqual(len(list(self.storage.glob('attempt-*.json'))),1)
        finally:
            if process.is_alive():process.terminate();process.join()
