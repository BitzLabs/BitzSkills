"""調査modeの正常/失敗後pacingをfake clock/IOで検証する。"""
from pathlib import Path
from types import SimpleNamespace
import datetime
import math
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_survey_run as runner
real_io=runner.io


class MemoryIO:
    encoded=staticmethod(real_io.encoded)
    sha=staticmethod(real_io.sha)
    pin=staticmethod(real_io.pin)
    def __init__(self):self.files={}
    def read_regular(self,path):return self.files[str(path)]
    def exclusive(self,path,raw):
        if str(path) in self.files:raise FileExistsError()
        self.files[str(path)]=raw


class PacingTests(unittest.TestCase):
    def setUp(self):
        self.io=MemoryIO();self.root=Path('/synthetic');self.clock=100.0;self.sleeps=[];self.mutate=None;self.short=False
        self.bound=SimpleNamespace(contract=dict(sourceCommit='a'*40,campaignId='public-matrix-survey-test'))
        self.condition='b'*64;self.policy=dict(startOrdinal=1,priorSlots=[])
        self.result=dict(launchEvidence={});self.addCleanup(patch.stopall)
        patch.object(runner,'io',self.io).start();patch.object(runner.time,'monotonic',side_effect=lambda:self.clock).start()
        patch.object(runner.time,'sleep',side_effect=self.sleep).start()

    def sleep(self,delay):
        self.sleeps.append(delay);self.clock+=delay-(.001 if self.short else 0)
        if self.mutate:self.mutate()

    def pace(self,role='primary',n=1,prior=None):
        runner.pace(self.root,self.bound,self.policy,self.condition,n,role,self.result,prior)

    def change(self,updates, *, repin=True):
        path=self.root/'launch-primary-0001.json';v=runner.p.trace.strict_json(self.io.files[str(path)]);v.update(updates)
        self.io.files[str(path)]=self.io.encoded(v)
        if repin:self.result['launchEvidence']['primary']=self.io.sha(self.io.files[str(path)])

    def previous(self,status='evaluation_failed',phase='primary',independent=False):
        self.pace()
        if independent:self.pace('independent')
        prior=dict(sourceCommit=self.bound.contract['sourceCommit'],campaignId=self.bound.contract['campaignId'],
            conditionSha256=self.condition,ordinal=1,status=status,failurePhase=phase,globalErrorType=None,
            launchEvidence=dict(self.result['launchEvidence']))
        self.io.files[str(self.root/'actual-slot-0001.json')]=self.io.encoded(prior)
        self.result=dict(launchEvidence={})
        return dict(status=status,phase=phase,hasIndependent=independent)

    def reject(self,updates):
        self.pace();self.change(updates)
        with self.assertRaises(ValueError):self.pace('independent')

    def test_first_launch_no_sleep(self):
        self.pace();self.assertEqual(self.sleeps,[])

    def test_independent_waits_60(self):
        self.pace();self.pace('independent');self.assertEqual(self.sleeps,[60.0])

    def test_primary_after_failed_primary_waits(self):
        state=self.previous();self.pace(n=2,prior=state);self.assertEqual(self.sleeps,[60.0])

    def test_primary_after_failed_independent_waits(self):
        state=self.previous(phase='independent',independent=True);self.pace(n=2,prior=state)
        self.assertEqual(self.sleeps,[60.0,60.0])

    def test_primary_after_normal_waits_from_independent(self):
        state=self.previous(status='measured_correct',phase=None,independent=True);self.pace(n=2,prior=state)
        self.assertEqual(self.clock,220.0)

    def test_missing_independent_record_not_treated_as_failed_primary(self):
        state=self.previous(status='measured_correct',phase=None,independent=True)
        path=self.root/'actual-slot-0001.json';prior=runner.p.trace.strict_json(self.io.files[str(path)])
        del prior['launchEvidence']['independent'];self.io.files[str(path)]=self.io.encoded(prior)
        with self.assertRaises(ValueError):self.pace(n=2,prior=state)

    def test_previous_outcome_must_match_ledger(self):
        state=self.previous();state['status']='measured_correct'
        with self.assertRaises(ValueError):self.pace(n=2,prior=state)

    def test_previous_result_mutation_during_wait(self):
        state=self.previous();self.mutate=lambda:self.io.files.__setitem__(str(self.root/'actual-slot-0001.json'),b'{}')
        with self.assertRaises(ValueError):self.pace(n=2,prior=state)

    def test_previous_pacing_mutation_during_wait(self):
        self.pace();self.mutate=lambda:self.change(dict(monotonicSeconds=0),repin=False)
        with self.assertRaises(ValueError):self.pace('independent')

    def test_early_sleep_return_rejected(self):
        self.pace();self.short=True
        with self.assertRaises(ValueError):self.pace('independent')

    def test_pacing_file_not_overwritten(self):
        self.pace()
        with self.assertRaises(FileExistsError):self.pace()

    def test_hash_mismatch(self):
        self.pace();self.change(dict(monotonicSeconds=0),repin=False)
        with self.assertRaises(ValueError):self.pace('independent')

    def test_bad_numbers_and_identity(self):
        changes=[dict(monotonicSeconds=True),dict(monotonicSeconds=float('nan')),dict(monotonicSeconds=float('inf')),
            dict(monotonicSeconds=-1),dict(waitedSeconds=True),dict(waitedSeconds=61),dict(minimumGapSeconds=True),
            dict(ordinal=True),dict(role='independent'),dict(sourceCommit='c'*40),dict(campaignId='other'),
            dict(conditionSha256='c'*64),dict(startedAt='2026-10-15T00:00:00'),dict(extra='unknown')]
        for changeset in changes:
            with self.subTest(changes=changeset):
                self.io.files.clear();self.result=dict(launchEvidence={});self.reject(changeset)

    def test_carried_baseline_publication_gap_and_hash(self):
        raw=self.io.encoded(dict(recordedAt=(datetime.datetime.now(runner.JST)-datetime.timedelta(seconds=120)).isoformat()))
        self.io.files['/baseline/report.json']=raw;self.policy.update(startOrdinal=19,priorSlots=[{}],
            baselineReportAbsolutePath='/baseline/report.json',baselineReport=dict(sha256=self.io.sha(raw)))
        self.pace(n=19);self.assertEqual(self.sleeps,[])

    def test_carried_baseline_hash_drift(self):
        self.policy.update(startOrdinal=19,priorSlots=[{}],baselineReportAbsolutePath='/baseline/report.json',
            baselineReport=dict(sha256='b'*64));self.io.files['/baseline/report.json']=b'{}'
        with self.assertRaises(ValueError):self.pace(n=19)

    def test_recent_baseline_requires_gap(self):
        raw=self.io.encoded(dict(recordedAt=datetime.datetime.now(runner.JST).isoformat()))
        self.io.files['/baseline/report.json']=raw;self.policy.update(startOrdinal=19,priorSlots=[{}],
            baselineReportAbsolutePath='/baseline/report.json',baselineReport=dict(sha256=self.io.sha(raw)))
        with self.assertRaises(ValueError):self.pace(n=19)

if __name__=='__main__':unittest.main()
