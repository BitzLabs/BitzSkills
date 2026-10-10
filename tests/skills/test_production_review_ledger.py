"""静的検分の別worktree再起動・競合・未知CLI終端を拒否する。モデル起動0。"""
import copy
import multiprocessing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_ledger as primary
import production_review_ledger as ledger
import run_sdk_trace_review as review


def contender(storage, gate, queue):
    gate.wait(10)
    try:
        ledger.StaticReviewLedger(Path(storage)).reserve('evals/skills/routing/sdk-trace-review-v0.25.json',
            'a' * 40, primary.encoded(dict(maximumInvocations=1, automaticRetries=0,
                                        primaryModelTrajectories=0, model='gpt-6.1-sol')))
        queue.put('reserved')
    except FileExistsError:
        queue.put('stopped')


class StaticReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.venv/test-temp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.contract_name = 'evals/skills/routing/sdk-trace-review-v0.25.json'
        self.contract = dict(maximumInvocations=1, automaticRetries=0, primaryModelTrajectories=0,
                             model='gpt-6.1-sol', outputRelativeRoot='.venv/first')

    def test_source_output_change_or_stop_cannot_refund_reservation(self):
        storage = self.base / 'shared'
        first = ledger.StaticReviewLedger(storage).reserve(self.contract_name, 'a' * 40, primary.encoded(self.contract))
        changed = {**self.contract, 'outputRelativeRoot': '.venv/second'}
        with self.assertRaises(FileExistsError):
            ledger.StaticReviewLedger(storage).reserve(self.contract_name, 'b' * 40, primary.encoded(changed))
        self.assertEqual(primary.read_owned(Path(first['path']))['sourceCommit'], 'a' * 40)

    def test_repository_connection_anchors_different_worktrees(self):
        storage = self.base / 'common' / 'production-routing-primary-ledger'
        storage.parent.mkdir()
        with patch.object(primary, 'common_ledger_path', return_value=storage) as location:
            ledger.reserve_static_review(self.base / 'worktree-a', self.contract_name, 'a' * 40, primary.encoded(self.contract))
            with self.assertRaises(FileExistsError):
                ledger.reserve_static_review(self.base / 'worktree-b', self.contract_name, 'a' * 40, primary.encoded(self.contract))
        self.assertEqual(location.call_count, 2)

    def test_concurrent_reservations_consume_only_one(self):
        storage = self.base / 'shared'
        ledger.StaticReviewLedger(storage)
        context = multiprocessing.get_context('fork')
        gate, queue = context.Event(), context.Queue()
        workers = [context.Process(target=contender, args=(str(storage), gate, queue)) for _ in range(2)]
        for worker in workers:
            worker.start()
        gate.set()
        outcomes = [queue.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(sorted(outcomes), ['reserved', 'stopped'])

    def test_symlink_unknown_identity_and_non_finite_contract_rejected(self):
        target = self.base / 'target'
        target.mkdir()
        link = self.base / 'link'
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            ledger.StaticReviewLedger(link)
        instance = ledger.StaticReviewLedger(self.base / 'shared')
        for name, contract in [(self.contract_name, {**self.contract, 'maximumInvocations': True}),
                               (self.contract_name, {**self.contract, 'automaticRetries': 1}),
                               ('../another.json', self.contract)]:
            with self.subTest(name=name, contract=contract), self.assertRaises(ValueError):
                instance.reserve(name, 'a' * 40, primary.encoded(contract))

    def test_new_and_existing_static_directory_sync_parent_before_reservation(self):
        for _ in range(2):
            with patch.object(primary, 'sync_directory', wraps=primary.sync_directory) as sync:
                ledger.StaticReviewLedger(self.base / 'shared')
                sync.assert_called_once_with(self.base)
        with patch.object(primary, 'sync_directory', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError): ledger.StaticReviewLedger(self.base / 'shared')
        self.assertEqual(list((self.base / 'shared').iterdir()), [])


class ReviewLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.venv/test-temp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = 'a' * 40
        self.contract = dict(scope='public-sdk-trace-component-static-review-only', payloadFiles=['public.py'])
        self.response = dict(sourceCommit=self.source, scope=self.contract['scope'], verdict='pass', findings=[])
        (self.base / 'response.json').write_bytes(primary.encoded(self.response))
        self.schema = (ROOT / 'evals/skills/routing/sdk-trace-review.schema.json').read_bytes()
        self.events = [dict(type='thread.started', thread_id='native-thread'), dict(type='turn.started'),
                       dict(type='item.completed', item=dict(id='item-1', type='agent_message', text=primary.encoded(self.response).decode())),
                       dict(type='turn.completed', usage=dict(input_tokens=1, cached_input_tokens=0,
                            cache_write_input_tokens=0, output_tokens=1, reasoning_output_tokens=0))]

    def check(self, events):
        return review.review_response(self.base, b'\n'.join(primary.encoded(v) for v in events),
                                      self.source, self.schema, self.contract)

    def test_known_compact_profile_passes_without_inventing_item_start(self):
        value, usage, warnings = self.check(self.events)
        self.assertEqual(value, self.response)
        self.assertEqual(usage['input_tokens'], 1)
        self.assertEqual(warnings, [])

    def test_missing_start_unknown_type_and_terminal_reordering_rejected(self):
        variants = [self.events[1:], self.events[:1] + self.events[2:],
                    self.events[:2] + [dict(type='unknown-event')] + self.events[2:],
                    self.events + [dict(type='unknown-event')], self.events + [self.events[-1]],
                    self.events[:2] + self.events[3:] + self.events[2:3],
                    self.events[:2] + [self.events[1]] + self.events[2:]]
        for events in variants:
            with self.subTest(events=events), self.assertRaises(ValueError):
                self.check(events)

    def test_unknown_item_fields_wrong_usage_and_duplicate_ids_rejected(self):
        for action in ['item-type', 'extra-field', 'bool-usage', 'missing-usage', 'duplicate-id', 'extra-after-final']:
            events = copy.deepcopy(self.events)
            if action == 'item-type': events[2]['item']['type'] = 'command_execution'
            elif action == 'extra-field': events[2]['item']['hidden'] = 'unknown'
            elif action == 'bool-usage': events[-1]['usage']['input_tokens'] = True
            elif action == 'missing-usage': del events[-1]['usage']['input_tokens']
            elif action == 'duplicate-id': events.insert(2, dict(type='item.completed', item=dict(id='item-1', type='reasoning', text='known')))
            else: events.insert(-1, dict(type='item.completed', item=dict(id='item-2', type='reasoning', text='late')))
            with self.subTest(action=action), self.assertRaises(ValueError): self.check(events)

    def test_known_startup_warning_only_before_turn_and_unique(self):
        warning = dict(type='item.completed', item=dict(id='warning', type='error', message=
            'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.'))
        value, _, warnings = self.check(self.events[:1] + [warning] + self.events[1:])
        self.assertEqual(value, self.response)
        self.assertEqual(len(warnings), 1)
        for events in [self.events[:2] + [warning] + self.events[2:], self.events[:1] + [warning, warning] + self.events[1:]]:
            with self.assertRaises(ValueError): self.check(events)

    def test_message_and_file_schema_and_json_types_are_checked_independently(self):
        response = {**self.response, 'verdict': 'findings', 'findings': [dict(priority='P2', path='public.py',
                    line=1, message='condition', reproduction='synthetic', suggestion='correction')]}
        (self.base / 'response.json').write_bytes(primary.encoded(response))
        for value in [True, 1.0]:
            events = copy.deepcopy(self.events)
            message = copy.deepcopy(response)
            message['findings'][0]['line'] = value
            events[2]['item']['text'] = primary.encoded(message).decode()
            with self.subTest(value=value), self.assertRaises((ValueError, review.trace.jsonschema.exceptions.ValidationError)):
                self.check(events)
        events = copy.deepcopy(self.events)
        events[2]['item']['text'] = primary.encoded(response).decode()
        self.assertEqual(self.check(events)[0], response)
        invalid = copy.deepcopy(response)
        invalid['findings'][0]['line'] = True
        (self.base / 'response.json').write_bytes(primary.encoded(invalid))
        with self.assertRaises(review.trace.jsonschema.exceptions.ValidationError): self.check(events)


if __name__ == '__main__':
    unittest.main()
