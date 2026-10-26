"""条件phaseの型・readonly原照合・消費継続。実評価/私的原への書込み0。"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_phases as p
import test_production_heldout_ledger as fixture


class PhasePrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.HeldoutLedgerTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        for item in [patch.object(p.inputs, 'PRIVATE_CASES', self.f.root.parent/'cases.json'),
                patch.object(p.continuation, 'verify_prior', return_value={})]:
            item.start()
            self.addCleanup(item.stop)
        self.raw = p.continuation.contract_from_base(p.io.encoded(
            dict(self.f.contract, campaignId=p.continuation.CAMPAIGN)))
        with p.continuation.ContinuationLedger(self.f.root, self.raw).locked() as ledger:
            self.f.complete(ledger, 2)
            self.f.complete(ledger, 3)

    def snapshot(self):
        return p.read_journal(self.f.root, self.raw, 2)

    def header(self):
        return dict(version=p.HEADER_VERSION, purposeAnchorSha256=p.ANCHOR_SHA256,
            index=1, previousActivationSha256=p.ANCHOR_SHA256,
            previousJournalHeadSha256=self.snapshot().head, firstOrdinal=4)

    def phase_fixture(self, first, slots=(), *, pending=(), stopped=False):
        root = self.f.root.parent/('phase-'+str(len(list(self.f.root.parent.iterdir()))))
        root.mkdir(mode=0o700)
        raw = p.io.encoded(dict(self.f.contract, campaignId=p.continuation.CAMPAIGN))
        for name, data in [('lock', b''), ('contract.json', raw)]:
            fd = os.open(root/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
        stages = []
        for ordinal, terminal in slots:
            if terminal == 'parent_verified':
                names = p.legacy.STAGES
            elif terminal == 'primary_failed':
                names = ('primary_reserved', 'primary_started', 'primary_failed')
            else:
                names = (*p.legacy.STAGES[:5], 'independent_failed')
            stages.extend((ordinal, name) for name in names)
        stages.extend(pending)
        if stopped:
            stages.append((None, 'global_stop'))
        previous = p.io.sha(raw)
        for index, (ordinal, stage) in enumerate(stages, 1):
            value = dict(version=p.legacy.VERSION, contractSha256=p.io.sha(raw), sequence=index,
                previousSha256=previous, ordinal=ordinal, stage=stage,
                artifactSha256=None if stage.endswith(('_reserved', '_started')) else 'd'*64,
                resourceProofSha256=self.f.contract['resourceProofSha256'] if stage.endswith('_failed') else None,
                measuredCorrect=True if stage == 'parent_verified' else None,
                stopReason='unsafe' if stage == 'global_stop' else None)
            data = p.io.encoded(value)
            fd = os.open(root/f'event-{index:04d}.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            previous = p.io.sha(data)
        return p.read_journal(root, raw, first)

    def test_anchor_is_exact_original_public_metadata(self):
        value = p.anchor()
        self.assertEqual(value['genesisJournalEvents'], 14)
        self.assertEqual(value['genesisContracts']['ledger']['budget']['primary'], 24)
        with patch.object(p.io, 'read_regular', return_value=b'{}'), self.assertRaises(ValueError):
            p.anchor()

    def test_header_is_bounded_and_rejects_downgrade_and_extra_keys(self):
        value = self.header()
        self.assertEqual(p.phase_header(value), value)
        for name, replacement in [('version', 'legacy'), ('purposeAnchorSha256', '0'*64),
                ('index', True), ('index', 0), ('index', p.MAX_PHASES+1), ('firstOrdinal', True),
                ('firstOrdinal', 3), ('firstOrdinal', 25), ('firstOrdinal', 4.0),
                ('previousActivationSha256', '0'*64), ('previousJournalHeadSha256', 'unknown'),
                ('claimedCarry', 0)]:
            with self.subTest(name=name, replacement=replacement), self.assertRaises(ValueError):
                p.phase_header(dict(value, **{name:replacement}))

    def test_roots_have_no_caller_selected_directory(self):
        self.assertEqual(p.phase_root(0), p.inputs.PRIVATE_CASES.parent/p.continuation.ROOT_NAME)
        self.assertEqual(p.phase_root(1), p.registry_root()/'ledgers/phase-0001')
        for value in [True, -1, p.MAX_PHASES+1, '1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.phase_root(value)

    def test_existing_journal_read_does_not_change_any_original_or_initialize_new_root(self):
        before = {f.name:f.read_bytes() for f in self.f.root.iterdir()}
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot.rows), 14)
        self.assertEqual(snapshot.counts()['correct'], 2)
        self.assertNotIn('primary_reserved', repr(snapshot))
        with self.assertRaises(TypeError):
            snapshot.rows[0]['stage'] = 'parent_verified'
        self.assertEqual(before, {f.name:f.read_bytes() for f in self.f.root.iterdir()})
        missing = self.f.root.parent/'not-created'
        with self.assertRaises(FileNotFoundError):
            p.read_journal(missing, self.raw, 2)
        self.assertFalse(missing.exists())

    def test_carry_adds_original_stop_only_once_and_keeps_pending(self):
        value = p.carry_forward([self.snapshot()])
        self.assertEqual((value['primaryReserved'], value['independentReserved']), (3, 2))
        self.assertEqual((value['correct'], value['terminalSlots'], value['accountedSlots']), (2, 2, 3))
        self.assertEqual((value['pending'], value['unattempted'], value['nextOrdinal']), (1, 21, 4))

    def test_empty_phases_consume_nothing_and_have_a_finite_bound(self):
        first = self.snapshot()
        empty = self.phase_fixture(4)
        self.assertEqual(p.carry_forward([first, empty]), p.carry_forward([first]))
        self.assertEqual(p.carry_forward([first]+[empty]*p.MAX_PHASES)['nextOrdinal'], 4)
        with self.assertRaises(ValueError):
            p.carry_forward([first]+[empty]*(p.MAX_PHASES+1))

    def test_failed_primary_and_independent_remain_consumed(self):
        for terminal in ['primary_failed', 'independent_failed']:
            with self.subTest(terminal=terminal):
                next_phase = self.phase_fixture(4, slots=[(4, terminal)])
                value = p.carry_forward([self.snapshot(), next_phase])
                self.assertEqual((value['primaryReserved'], value['terminalSlots'], value['nextOrdinal']), (4, 3, 5))
                self.assertEqual((value['correct'], value['evaluationFailed'], value['pending']), (2, 1, 1))

    def test_pending_or_global_stop_cannot_be_transferred(self):
        for phase in [self.phase_fixture(4, pending=[(4, 'primary_reserved')]),
                self.phase_fixture(4, stopped=True)]:
            with self.subTest(counts=phase.counts()), self.assertRaises(ValueError):
                p.carry_forward([self.snapshot(), phase])

    def test_discontinuous_ordinal_is_not_counted_as_new_budget(self):
        with self.assertRaises(ValueError):
            p.carry_forward([self.snapshot(), self.phase_fixture(5)])

    def test_all_remaining21_end_at_24_without_returning_previous_consumption(self):
        rest = self.phase_fixture(4, slots=[(n, 'parent_verified') for n in range(4, 25)])
        value = p.carry_forward([self.snapshot(), rest])
        self.assertEqual((value['primaryReserved'], value['independentReserved']), (24, 23))
        self.assertEqual((value['terminalSlots'], value['accountedSlots'], value['unattempted']), (23, 24, 0))
        self.assertEqual((value['correct'], value['pending']), (23, 1))

    def test_seal_is_unknown_to_legacy_and_unregistered_readers(self):
        seal = p.io.encoded(dict(version='PUBLIC_SYNTHETIC_SEAL'))
        fd = os.open(self.f.root/p.SEAL_NAME, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(seal)
        with self.assertRaises(ValueError):
            self.snapshot()
        with self.assertRaises(ValueError):
            with p.continuation.ContinuationLedger(self.f.root, self.raw).locked():
                pass
        allowed = p.read_journal(self.f.root, self.raw, 2, seal_sha256=p.io.sha(seal))
        self.assertEqual((len(allowed.rows), allowed.counts()['correct']), (14, 2))
        with self.assertRaises(ValueError):
            p.read_journal(self.f.root, self.raw, 2, seal_sha256='0'*64)

    def test_unknown_files_contract_or_chain_changes_are_rejected(self):
        changed = p.io.encoded(dict(p.inputs.parse(self.raw), sourceCommit='f'*40))
        with self.assertRaises(ValueError):
            p.read_journal(self.f.root, changed, 2)
        path = self.f.root/'event-0002.json'
        original = path.read_bytes()
        value = p.inputs.parse(original)
        for replacement in [dict(value, sequence=True), dict(value, previousSha256='0'*64),
                dict(value, ordinal=1), dict(value, unknown=None)]:
            path.write_bytes(p.io.encoded(replacement))
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.snapshot()
        path.write_bytes(original)
        (self.f.root/'unexpected.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_hardlinked_original_is_rejected(self):
        path = self.f.root/'event-0002.json'
        os.link(path, self.f.root.parent/'second-link')
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_last_event_changed_after_read_cannot_return_a_stale_snapshot(self):
        original, fired = p._read, []

        def change(root, name, **kwargs):
            raw = original(root, name, **kwargs)
            if name == 'event-0014.json' and not fired:
                row = p.inputs.parse(raw)
                (root/name).write_bytes(p.io.encoded(dict(row, measuredCorrect=False)))
                fired.append(True)
            return raw

        with patch.object(p, '_read', side_effect=change), self.assertRaises(ValueError):
            self.snapshot()
        self.assertEqual(self.snapshot().counts()['correct'], 1)

    def test_contract_changed_during_last_event_read_is_rejected(self):
        original, fired = p._read, []

        def change(root, name, **kwargs):
            raw = original(root, name, **kwargs)
            if name == 'event-0014.json' and not fired:
                (root/'contract.json').write_bytes(p.io.encoded(
                    dict(p.inputs.parse(self.raw), sourceCommit='f'*40)))
                fired.append(True)
            return raw

        with patch.object(p, '_read', side_effect=change), self.assertRaises(ValueError):
            self.snapshot()

    def test_directory_exchange_cannot_supply_rows_from_an_unlocked_directory(self):
        alternate = self.f.root.parent/'alternate'
        alternate.mkdir(mode=0o700)
        for path in self.f.root.iterdir():
            raw = path.read_bytes()
            if path.name == 'event-0014.json':
                raw = p.io.encoded(dict(p.inputs.parse(raw), measuredCorrect=False))
            fd = os.open(alternate/path.name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
        original, fired = p._read, []
        backup = self.f.root.parent/'temporarily-moved'

        def swap(root, name, **kwargs):
            if name == 'event-0014.json' and not fired:
                root.rename(backup)
                alternate.rename(root)
                fired.append(True)
                try:
                    return original(root, name, **kwargs)
                finally:
                    root.rename(alternate)
                    backup.rename(root)
            return original(root, name, **kwargs)

        with patch.object(p, '_read', side_effect=swap), self.assertRaises(ValueError):
            self.snapshot()
        self.assertEqual(self.snapshot().counts()['correct'], 2)


if __name__ == '__main__':
    unittest.main()
