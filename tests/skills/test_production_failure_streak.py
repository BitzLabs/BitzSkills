"""同じ型の評価失敗の連続の検出と確認記録。モデル呼出しなし。"""
import io as stream
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_failure_streak as streak

FAILED = dict(status='primary_capture_stopped', errorType='ValueError', timedOut=False)


def record(ordinal, status='measured_correct', *, case=None, primary=FAILED, phase='primary'):
    value = dict(ordinal=ordinal, caseId=case or f'SE-{(ordinal+1)//2:03d}', status=status,
        eligibleForMeasurement=status.startswith('measured'), failurePhase=None, primary=None)
    if status == 'evaluation_failed':
        value.update(failurePhase=phase, **{phase: dict(primary)})
    return value


def acknowledgement(next_ordinal, ordinals, signature, **change):
    value = dict(version=streak.ACKNOWLEDGEMENT_VERSION, nextOrdinal=next_ordinal, failedOrdinals=ordinals,
        signature=signature, decision='continue', reason='取得失敗の原因を確認した')
    value.update(change)
    return json.dumps(value).encode()


class FailureStreakTests(unittest.TestCase):
    def items(self, records):
        return [(r['ordinal'], streak.survey_signature(r)) for r in records]

    def test_single_failure_or_success_between_failures_is_clear(self):
        records = [record(1), record(2, 'evaluation_failed'), record(3), record(4, 'evaluation_failed')]
        self.assertEqual('clear', streak.guard(self.items(records), 5)['status'])

    def test_two_identical_failures_block_the_next_slot(self):
        records = [record(1), record(2, 'evaluation_failed'), record(3, 'evaluation_failed')]
        with self.assertRaisesRegex(ValueError, 'consecutive identical evaluation failures'):
            streak.guard(self.items(records), 4)

    def test_different_failure_types_do_not_form_a_streak(self):
        other = dict(FAILED, errorType='TimeoutError')
        records = [record(1, 'evaluation_failed'), record(2, 'evaluation_failed', primary=other)]
        self.assertEqual('clear', streak.guard(self.items(records), 3)['status'])
        records = [record(1, 'evaluation_failed'), record(2, 'evaluation_failed', phase='independent')]
        self.assertEqual('clear', streak.guard(self.items(records), 3)['status'])

    def test_acknowledgement_must_bind_the_streak_and_next_slot(self):
        records = [record(1, 'evaluation_failed'), record(2, 'evaluation_failed')]
        signature = ['primary', 'primary_capture_stopped', 'ValueError', False]
        result = streak.guard(self.items(records), 3, acknowledgement(3, [1, 2], signature))
        self.assertEqual('acknowledged', result['status'])
        for raw in [acknowledgement(4, [1, 2], signature), acknowledgement(3, [2], signature),
                acknowledgement(3, [1, 2], signature[:2]), acknowledgement(3, [1, 2], signature, decision='stop'),
                acknowledgement(3, [1, 2], signature, reason=' '), acknowledgement(3, [1, 2], signature, extra=1)]:
            with self.assertRaises(ValueError):
                streak.guard(self.items(records), 3, raw)

    def test_ledger_terminals_ignore_non_terminal_events(self):
        rows = [dict(ordinal=1, stage='primary_reserved'), dict(ordinal=1, stage='primary_started'),
            dict(ordinal=1, stage='primary_failed'), dict(ordinal=2, stage='primary_reserved'),
            dict(ordinal=2, stage='primary_failed')]
        items = streak.ledger_terminals(rows)
        self.assertEqual([(1, ('primary_failed',)), (2, ('primary_failed',))], items)
        with self.assertRaises(ValueError):
            streak.guard(items, 3)
        rows.append(dict(ordinal=3, stage='parent_verified'))
        self.assertEqual('clear', streak.guard(streak.ledger_terminals(rows), 4)['status'])

    def test_archive_summary_reports_streaks_and_unmeasured_cases(self):
        records = [record(1, case='SE-001'), record(2, case='SE-001'), record(3, case='SE-002'),
            *[record(n, 'evaluation_failed', case=f'SE-{n:03d}') for n in range(4, 7)]]
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)/'evidence.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                for value in reversed(records):
                    raw = json.dumps(value).encode()
                    info = tarfile.TarInfo(f'actual-slot-{value["ordinal"]:04d}.json');info.size = len(raw)
                    bundle.addfile(info, stream.BytesIO(raw))
                info = tarfile.TarInfo('report.json');info.size = 2
                bundle.addfile(info, stream.BytesIO(b'{}'))
            summary = streak.summarize(streak.survey_records(archive))
        self.assertEqual(6, summary['slots'])
        self.assertEqual([dict(first=4, last=6, length=3, signature=['primary', 'primary_capture_stopped',
            'ValueError', False], cases=['SE-004', 'SE-005', 'SE-006'])], summary['streaks'])
        self.assertEqual(['SE-004', 'SE-005', 'SE-006'], summary['casesWithoutMeasurement'])
        self.assertEqual(dict(evaluation_failed=3, measured_correct=3), summary['statusCounts'])

    def test_archive_rejects_mismatched_or_duplicate_ordinals(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)/'evidence.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                raw = json.dumps(record(2)).encode()
                info = tarfile.TarInfo('actual-slot-0001.json');info.size = len(raw)
                bundle.addfile(info, stream.BytesIO(raw))
            with self.assertRaises(ValueError):
                streak.survey_records(archive)


if __name__ == '__main__':
    unittest.main()
