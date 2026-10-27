"""隔離された合成台帳だけで予約・順序・恒久停止・非公開保存を検証。モデル0。"""
from concurrent.futures import ThreadPoolExecutor
import copy
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_ledger as ledger


class HeldoutLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'ledger'
        self.contract = dict(version=ledger.VERSION, campaignId='heldout-matrix-synthetic-01', sourceCommit='a'*40,
            inputContractSha256='b'*64, resourceProofSha256='c'*64, model='gpt-6.1-sol',
            setVersion=ledger.inputs.SET_VERSION, budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0),
            timeoutSeconds=dict(primary=300, independent=300), certifiesSkillGate=False)

    def instance(self):
        return ledger.HeldoutLedger(self.root, ledger.io.encoded(self.contract))

    def stage(self, instance, ordinal, stage, **kwargs):
        marker = stage.endswith('_reserved') or stage.endswith('_started')
        return instance.append(ordinal, stage, None if marker else 'd'*64, **kwargs)

    def complete(self, instance, ordinal, correct=True):
        for stage in ledger.STAGES:
            self.stage(instance, ordinal, stage, **({'measured_correct':correct} if stage == 'parent_verified' else {}))

    def test_all_24_normal_slots_are_recorded_without_counting_gate_or_invocations(self):
        with self.instance().locked() as instance:
            for ordinal in range(1, 25): self.complete(instance, ordinal, ordinal % 2 == 0)
            summary = instance.summary()
            self.assertEqual(summary['status'], 'attempts_recorded')
            self.assertEqual((summary['correct'], summary['incorrect'], summary['parentVerified']), (12,12,24))
            self.assertEqual((summary['unattempted'], summary['pending']), (0,0))
            self.assertFalse(summary['certifiesSkillGate'])
            with self.assertRaises(ValueError): self.stage(instance, 25, 'primary_reserved')
        for path in self.root.iterdir(): self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    def test_failure_is_terminal_not_correct_and_no_refund_on_reopen(self):
        with self.instance().locked() as instance:
            self.stage(instance, 1, 'primary_reserved')
            self.stage(instance, 1, 'primary_started')
            with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_failed')
            self.stage(instance, 1, 'primary_failed', resource_proof_sha256='c'*64)
        with self.instance().locked() as instance:
            self.assertEqual(instance.summary()['evaluationFailed'], 1)
            self.assertEqual(instance.summary()['correct'], 0)
            with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_reserved')
            self.complete(instance, 2, False)
            self.assertEqual(instance.summary()['incorrect'], 1)
            self.assertEqual(instance.summary()['primaryReserved'], 2)

    def test_independent_failure_retains_primary_and_does_not_create_normal_measurement(self):
        with self.instance().locked() as instance:
            for stage in ledger.STAGES[:5]: self.stage(instance, 1, stage)
            self.stage(instance, 1, 'independent_failed', resource_proof_sha256='c'*64)
            summary = instance.summary()
            self.assertEqual(summary['independentReserved'], 1)
            self.assertEqual((summary['evaluationFailed'],summary['parentVerified']), (1,0))
            self.stage(instance, 2, 'primary_reserved')

    def test_pending_stage_and_invalid_order_do_not_advance(self):
        with self.instance().locked() as instance:
            for ordinal in [0, 2, 25, True, 1.0]:
                with self.subTest(ordinal=ordinal), self.assertRaises(ValueError):
                    self.stage(instance, ordinal, 'primary_reserved')
            self.stage(instance, 1, 'primary_reserved')
            for ordinal, stage in [(2,'primary_reserved'), (1,'independent_reserved'), (1,'parent_verified'),
                                    (1,'primary_reserved'), (1,'primary_failed')]:
                with self.subTest(stage=stage), self.assertRaises(ValueError):
                    self.stage(instance, ordinal, stage)
            self.assertEqual(instance.summary()['pending'], 1)

    def test_source_and_campaign_changes_cannot_reinitialize_existing_shared_ledger(self):
        with self.instance().locked() as instance: self.stage(instance, 1, 'primary_reserved')
        original = copy.deepcopy(self.contract)
        for key, value in [('sourceCommit','e'*40), ('campaignId','heldout-matrix-synthetic-02'),
                           ('inputContractSha256','f'*64)]:
            self.contract = copy.deepcopy(original)
            self.contract[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                with self.instance().locked(): pass
        with patch.object(ledger, 'HeldoutLedger') as factory:
            ledger.open_shared(ledger.io.encoded(original))
            self.assertEqual(factory.call_args.args[0], ledger.SHARED_ROOT)

    def test_permanent_global_stop_rejects_more_events_after_reopen(self):
        with self.instance().locked() as instance:
            self.stage(instance, 1, 'primary_reserved')
            instance.append(None, 'global_stop', 'e'*64, stop_reason='resource_drift')
        with self.instance().locked() as instance:
            self.assertEqual(instance.summary()['status'], 'stopped')
            with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_started')

    def test_tampering_unknown_files_and_journal_gaps_rejected(self):
        with self.instance().locked() as instance:
            self.stage(instance, 1, 'primary_reserved')
            self.stage(instance, 1, 'primary_started')
        path=self.root/'event-0002.json';raw=path.read_bytes()
        variants=[b'{}', raw.replace(b'"previousSha256":"',b'"previousSha256":"0')]
        for changed in variants:
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                with self.instance().locked(): pass
        path.write_bytes(raw)
        path.rename(self.root/'event-0003.json')
        with self.assertRaises(ValueError):
            with self.instance().locked(): pass

    def test_live_contract_tampering_is_rejected_before_next_event(self):
        with self.instance().locked() as instance:
            (self.root/'contract.json').write_bytes(b'{}')
            with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_reserved')

    def test_directory_permission_and_owner_drift_rejected_before_new_event(self):
        with self.instance().locked() as instance:
            self.stage(instance, 1, 'primary_reserved')
            self.root.chmod(0o755)
            with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_started')
            self.assertFalse((self.root/'event-0002.json').exists())
            with self.assertRaises(ValueError): instance.summary()
            self.root.chmod(0o700)
            with patch.object(ledger.os, 'getuid', return_value=os.getuid()+1):
                with self.assertRaises(ValueError): self.stage(instance, 1, 'primary_started')
            self.assertFalse((self.root/'event-0002.json').exists())

    def test_symlinks_hardlinks_and_group_readable_records_are_rejected(self):
        with self.instance().locked() as instance: self.stage(instance, 1, 'primary_reserved')
        path=self.root/'event-0001.json';path.chmod(0o640)
        with self.assertRaises(ValueError):
            with self.instance().locked(): pass
        path.chmod(0o600)
        os.link(path,self.root.parent/'hardlink')
        with self.assertRaises(ValueError):
            with self.instance().locked(): pass
        other=self.root.parent/'symlink';other.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):
            with ledger.HeldoutLedger(other,ledger.io.encoded(self.contract)).locked(): pass

    def test_competing_workers_cannot_both_reserve_same_slot(self):
        raw=ledger.io.encoded(self.contract)
        def reserve(_):
            try:
                with ledger.HeldoutLedger(self.root,raw).locked() as instance:
                    self.stage(instance, 1, 'primary_reserved')
                return 'reserved'
            except ValueError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(reserve,range(2))), ['rejected','reserved'])

    def test_invalid_finite_contracts_rejected(self):
        original=copy.deepcopy(self.contract)
        for key,value in [('sourceCommit','main'),('certifiesSkillGate',True),('model','other')]:
            self.contract=copy.deepcopy(original);self.contract[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.instance()
        for value in [True,23,25]:
            self.contract=copy.deepcopy(original);self.contract['budget']['primary']=value
            with self.subTest(budget=value),self.assertRaises(ValueError):self.instance()
        self.contract=copy.deepcopy(original);self.contract['timeoutSeconds']['primary']=True
        with self.assertRaises(ValueError):self.instance()
