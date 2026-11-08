"""日付境界とプロセス再起動を実台帳・合成応答で検査する。"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'evals/skills/routing'))
import production_matrix_continuation as continuation
import test_production_canary_rollout as rollout_fixture
import test_production_matrix_ledger as ledger_fixture
import test_production_matrix_preflight as preflight_fixture

matrix = continuation.matrix
JST = ZoneInfo('Asia/Tokyo')


def select(f, execution):
    budget = dict(primary=2, independent=2, automaticRetries=0, delegations=0)
    inputs = matrix.strict_json(f.input_raw)
    inputs.update(version=matrix.inputs.SUBSET_VERSION, scope='public-six-skill-subset-input-binding-only',
                  caseIds=['SE-041'], budget=budget)
    f.input_raw = matrix.io.encoded(inputs)
    execution.update(version=matrix.SUBSET_VERSION, caseIds=inputs['caseIds'], budget=budget,
                     continuationPolicy=matrix.CONTINUATION_POLICY, inputContractSha256=matrix.io.sha(f.input_raw))
    f.bound = f.bind()


def limits(reset, *, short=0, weekly=0):
    return dict(limitId='codex', spendControlReached=False, rateLimitReachedType=None,
                primary=dict(usedPercent=short, resetsAt=reset, windowDurationMins=300),
                secondary=dict(usedPercent=weekly, resetsAt=reset+604800, windowDurationMins=10080))


class MatrixContinuationTests(unittest.TestCase):
    def setUp(self):
        f = ledger_fixture.MatrixLedgerTests('runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        select(f, f.contract)
        f.instance = f.open()
        self.f = f
        self.control = f.repository/'.venv/control'
        self.read_limits = Mock()
        self.verify = Mock()
        self.verify_completed = Mock()
        self.calls = []
        self.now = datetime(2026, 11, 8, 23, 59, tzinfo=JST).timestamp()
        with_clock = patch.object(continuation.time, 'time', side_effect=lambda: self.now)
        self.addCleanup(with_clock.stop)
        with_clock.start()
        pacing = patch.object(continuation, 'pace')
        self.addCleanup(pacing.stop)
        self.pace = pacing.start()
        self.read_limits.return_value = limits(self.now+300)

    def primary(self, ordinal):
        self.calls.append(('primary', ordinal))
        self.f.prepare_primary(ordinal)
        return dict(status='primary_capture_awaits_independent_review')

    def independent(self, ordinal):
        self.calls.append(('independent', ordinal))
        self.f.instance.reserve_independent(ordinal, 'c'*64)
        return dict(status='matrix_independent_captured')

    def finalize(self, ordinal, *, correct=True):
        self.calls.append(('parent', ordinal))
        review = self.f.review(ordinal, correct)
        self.f.instance.record_review(ordinal, matrix.io.encoded(review))
        return dict(ledgerFinalized=True, verification=dict(proposedLedgerStatus=review['status']))

    def advance(self, *, primary=None, finalize=None):
        return continuation.advance(self.f.instance,self.control,self.read_limits,self.verify,self.verify_completed,
            lambda n,guard:(primary or self.primary)(n),lambda n,guard:self.independent(n),
            lambda n,guard:(finalize or self.finalize)(n))

    def test_cross_day_wait_and_process_restart_continue_exact_next_slot(self):
        self.assertEqual(self.advance(), dict(status='measured_correct', ordinal=1))
        first = self.f.instance.path('review', 1).read_bytes()
        reset = self.now+300
        self.read_limits.return_value = limits(reset, short=80)
        self.assertEqual(self.advance(), dict(status='waiting_for_rate_window', ordinal=2, waitUntilUnix=reset))
        self.assertFalse(self.f.instance.path('attempt', 2).exists())
        self.assertFalse((self.f.storage/'stop.json').exists())
        self.now = reset+1
        self.read_limits.return_value = limits(self.now+300)
        self.f.instance = self.f.open()
        self.assertEqual(self.advance(), dict(status='measured_correct', ordinal=2))
        self.assertEqual(self.advance(), dict(status='complete'))
        self.assertEqual(self.f.instance.path('review', 1).read_bytes(), first)
        self.assertEqual(self.calls, [(stage,n) for n in (1,2) for stage in ('primary','independent','parent')])
        self.assertEqual(self.f.instance.summary()['primaryReserved'], 2)

    def test_reviewed_bundle_entry_runs_the_same_pipeline_and_rejects_another_condition(self):
        f = self.f
        bundle = f.repository/'.venv/bound'
        bundle.mkdir()
        condition = 'a'*64
        report = dict(continuationOperatorSha256=matrix.io.sha(Path(continuation.__file__).read_bytes()))
        files = {'execution.json':f.bound.execution_raw, 'input-contract.json':f.input_raw,
                 'deployment.json':b'{}', 'sdk-manifest.json':b'{}', 'prelaunch-review.json':b'{}',
                 'code-review.json':matrix.io.encoded(report),
                 **{name+'.input.json':raw for name,raw in f.raws.items()}}
        for name, raw in files.items():
            (bundle/name).write_bytes(raw)
        manifest = f.repository/'.venv/snapshot/manifest.json'
        manifest.parent.mkdir()
        manifest.write_bytes(b'{}')
        with (
            patch.object(continuation.capture,'prelaunch_review',return_value=dict(
                scope=continuation.score.SCOPE,conditionSha256=condition)),
            patch.object(continuation.p,'deployment',return_value=dict(snapshotRelativePath='.venv/snapshot')),
            patch.object(continuation.p.guard,'git',side_effect=lambda *args:
                Path(continuation.__file__).read_bytes() if args[-1].endswith('continuation.py') else b'{}'),
            patch.object(continuation.p,'decision_schema',return_value=b'{}'),
            patch.object(continuation.p,'verify_resources',self.verify),
            patch.object(matrix.io,'common_ledger_path',return_value=f.repository/'.venv/common.json'),
            patch.object(matrix,'shared_storage',return_value=f.storage),
            patch.object(continuation.capture,'_run',side_effect=lambda *args,**kwargs:self.primary(args[-1])),
            patch.object(continuation.score,'_run',side_effect=lambda *args,**kwargs:self.independent(args[2])),
            patch.object(continuation.score,'_finalize',side_effect=lambda *args,**kwargs:self.finalize(args[2])),
        ):
            with self.assertRaisesRegex(ValueError,'approved condition required'):
                continuation.run_next(f.repository,bundle,'b'*64,self.read_limits)
            self.read_limits.assert_not_called()
            self.assertEqual(continuation.run_next(f.repository,bundle,condition,self.read_limits),
                             dict(status='measured_correct',ordinal=1))
        self.assertEqual(self.calls,[('primary',1),('independent',1),('parent',1)])

    def test_reserved_but_unfinished_slot_stops_without_second_launch(self):
        self.f.instance.reserve(1)
        original = self.f.instance.path('attempt', 1).read_bytes()
        self.f.instance = self.f.open()
        self.assertEqual(self.advance(), dict(status='stopped'))
        self.assertEqual(self.f.instance.path('attempt', 1).read_bytes(), original)
        self.read_limits.assert_not_called()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.f.instance.summary()['primaryReserved'], 1)

    def test_parallel_operator_cannot_take_the_next_slot(self):
        def while_locked(ordinal):
            with self.assertRaisesRegex(ValueError, 'already running'):
                self.advance()
            return self.primary(ordinal)
        self.assertEqual(self.advance(primary=while_locked), dict(status='measured_correct', ordinal=1))
        self.assertEqual(self.f.instance.summary()['primaryReserved'], 1)

    def test_incorrect_stops_and_preserves_measurement(self):
        result = self.advance(finalize=lambda n:self.finalize(n,correct=False))
        self.assertEqual(result, dict(status='measured_incorrect', ordinal=1))
        self.assertEqual(self.advance(), dict(status='stopped'))
        self.assertEqual(self.f.instance.summary()['measuredIncorrect'], 1)
        self.assertFalse(self.f.instance.path('attempt', 2).exists())

    def test_unresolved_quota_and_changed_resources_do_not_reserve(self):
        self.read_limits.return_value['rateLimitReachedType'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'rate state unresolved'):
            self.advance()
        self.read_limits.return_value = limits(self.now+300)
        self.verify.side_effect = ValueError('fixed resource drift')
        with self.assertRaisesRegex(ValueError, 'resource drift'):
            self.advance()
        self.assertEqual(self.f.instance.summary()['primaryReserved'], 0)
        self.assertEqual(self.calls, [])

    def test_changed_completed_original_is_rejected_before_next_reservation(self):
        self.assertEqual(self.advance()['status'], 'measured_correct')

        def change_during_rate_read():
            self.verify_completed.side_effect = ValueError('completed original drift')
            return limits(self.now+300)

        self.read_limits.side_effect = change_during_rate_read
        with self.assertRaisesRegex(ValueError, 'completed original drift'):
            self.advance()
        self.assertFalse(self.f.instance.path('attempt', 2).exists())
        stop = matrix.io.read_owned(self.f.storage/'stop.json')
        self.assertEqual(stop['ordinal'], 1)
        self.assertEqual(self.f.instance.summary()['status'], 'stopped')

    def test_quota_snapshot_expiring_during_original_checks_does_not_reserve(self):
        self.assertEqual(self.advance()['status'], 'measured_correct')
        with patch.object(continuation.time,'monotonic',side_effect=[0,0,61]):
            with self.assertRaisesRegex(ValueError, 'stale before reservation'):
                self.advance()
        self.assertFalse(self.f.instance.path('attempt', 2).exists())
        self.assertFalse((self.f.storage/'stop.json').exists())

    def test_completed_scope_rechecks_earlier_originals_without_quota(self):
        self.advance()
        self.advance()
        self.read_limits.reset_mock()
        self.verify_completed.side_effect = ValueError('oldest original drift')
        with self.assertRaisesRegex(ValueError, 'oldest original drift'):
            self.advance()
        self.read_limits.assert_not_called()
        self.assertEqual(matrix.io.read_owned(self.f.storage/'stop.json')['ordinal'], 1)

    def test_replaced_control_lock_does_not_reserve_or_stop_another_caller(self):
        lock = self.control/'launch.lock'

        def replace_lock():
            lock.rename(self.control/'previous.lock')
            lock.touch(mode=0o600)
            return limits(self.now+300)

        self.read_limits.side_effect = replace_lock
        with self.assertRaisesRegex(ValueError, 'lock identity drift'):
            self.advance()
        self.assertFalse(self.f.instance.path('attempt', 1).exists())
        self.assertFalse((self.f.storage/'stop.json').exists())

    def test_opt_in_requires_the_coordinated_entry(self):
        bound=self.f.bound
        args=(self.f.repository,bound,1,b'',b'',b'',b'',b'')
        with self.assertRaisesRegex(ValueError, 'continuation operator required'):
            continuation.capture.run(self.f.repository,bound,b'',b'',b'',b'',1)
        for entry in (continuation.score.run,continuation.score.finalize):
            with self.assertRaisesRegex(ValueError, 'continuation operator required'):
                entry(*args)

    def test_failed_acquisition_with_reservation_is_terminal(self):
        def failed(ordinal):
            self.primary(ordinal)
            return dict(status='failed')
        with self.assertRaisesRegex(ValueError, 'primary stopped'):
            self.advance(primary=failed)
        self.assertEqual(self.advance(), dict(status='stopped'))
        self.assertEqual(self.calls, [('primary', 1)])
        self.assertEqual(self.f.instance.summary()['primaryReserved'], 1)


class MatrixContinuationResourceTests(unittest.TestCase):
    def test_fixed_resource_proof_survives_a_date_change(self):
        f = preflight_fixture.MatrixPreflightTests('runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        select(f,f.execution)
        f.deployment['executionSha256'] = matrix.io.sha(f.bound.execution_raw)
        today = datetime.now(JST)
        with patch.object(continuation.p, 'datetime') as clock:
            clock.now.return_value = today
            first = f.verify()
            clock.now.return_value = today+timedelta(days=7)
            self.assertEqual(f.verify(),first)
            clock.now.return_value = today-timedelta(days=1)
            with self.assertRaisesRegex(ValueError, 'in future'):
                f.verify()


class MatrixContinuationContextTests(unittest.TestCase):
    def test_actual_date_is_audited_without_changing_fixed_environment_fields(self):
        rollout = rollout_fixture.rollout
        case = rollout_fixture.CanaryRolloutTests('runTest').fixture('no-exec')
        request = next(rollout.trace.strict_json(raw) for raw in case['payloads'].values()
                       if 'input' in rollout.trace.strict_json(raw))
        environment = request['input'][3]
        content = environment['content'][0]
        observed = datetime(2026,11,9,tzinfo=JST).timestamp()
        environment['internal_chat_message_metadata_passthrough']['create_time'] = observed
        content['text'] = rollout.sdk._diagnostic_environment('/fixed/work','2026-11-09',{'2026-11-09'})
        with self.assertRaisesRegex(ValueError,'fixed entire environment'):
            rollout.initial_context(request,case['sent'],case['context_profile'],turn='turn')
        interval = (int(observed*1000)-1,int(observed*1000)+1)
        self.assertEqual(rollout.initial_context(request,case['sent'],case['context_profile'],turn='turn',
            observe_date=True,rollout_interval=interval),'2026-11-09')
        with self.assertRaisesRegex(ValueError,'timestamp outside rollout'):
            rollout.initial_context(request,case['sent'],case['context_profile'],turn='turn',
                observe_date=True,rollout_interval=(interval[1],interval[1]+1))
        content['text'] = content['text'].replace('bash','other')
        with self.assertRaisesRegex(ValueError,'fixed entire environment'):
            rollout.initial_context(request,case['sent'],case['context_profile'],turn='turn',
                observe_date=True,rollout_interval=interval)


    def test_request_environment_must_precede_first_inference_across_midnight(self):
        rollout = rollout_fixture.rollout
        case = rollout_fixture.CanaryRolloutTests('runTest').fixture('no-exec')
        midnight = datetime(2026,11,9,tzinfo=JST).timestamp()
        first = next(event for event in case['events'] if event['payload']['type']=='inference_started')
        offset = int(midnight*1000)-2-first['wall_time_unix_ms']
        for event in case['events']:
            event['wall_time_unix_ms'] += offset
        case['manifest']['started_at_unix_ms'] += offset
        request_path = first['payload']['request_payload']['path']
        request = rollout.trace.strict_json(case['payloads'][request_path])
        raw_environment = next(frame['params']['item'] for frame in case['received']
                               if frame['params'].get('item',{}).get('id')=='env')

        def recorded(date, created):
            for item in (request['input'][3], raw_environment):
                item['content'][0]['text'] = rollout.sdk._diagnostic_environment('/fixed/work',date,{date})
                item['internal_chat_message_metadata_passthrough']['create_time'] = created
            case['payloads'][request_path] = matrix.io.encoded(request)

        def verify():
            return rollout.correlate(matrix.io.encoded(case['manifest']),
                b''.join(matrix.io.encoded(event)+b'\n' for event in case['events']),case['payloads'],
                case['sent'],case['received'],case['native'],case['context_profile'],
                host_events=case['host_events'],capture_elapsed_ms=5000,observe_date=True)

        recorded('2026-11-08',midnight-0.003)
        self.assertEqual(verify()['observedContextDate'],'2026-11-08')
        raw_environment['internal_chat_message_metadata_passthrough']['create_time'] = midnight-0.004
        with self.assertRaisesRegex(ValueError,'raw environment timestamp drift'):
            verify()
        recorded('2026-11-09',midnight)
        with self.assertRaisesRegex(ValueError,'timestamp outside rollout'):
            verify()
