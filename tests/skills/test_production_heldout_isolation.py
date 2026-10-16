"""局所probeが認証とnetworkを持たず、private入力も本番予約も使わないことを検査。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_isolation as isolation
import test_production_heldout_execution as fixture
import test_production_heldout_launch as launch_fixture


class HeldoutIsolationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutExecutionTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bound=self.fixture.bind();self.repo=self.fixture.repository
        self.base=self.repo/'.venv/heldout-local-isolation-synthetic'

    def test_local_command_removes_auth_mount_and_adds_network_namespace(self):
        argv=isolation.command(self.repo,self.bound.execution_raw,self.bound.deployment_raw,self.base)
        self.assertIn('--unshare-net',argv)
        self.assertNotIn(str(isolation.launch.AUTH),argv)
        self.assertEqual(argv[-2:],['--probe',str(self.base)])
        self.assertIn(str(self.repo/'evals/skills/routing/production_heldout_isolation.py'),argv)
        self.assertNotIn(str(self.bound.stage_root(1,'primary')),argv)
        self.fixture.reader.assert_not_called()

    def test_local_root_cannot_be_private_stage_or_escape_repository(self):
        for base in [self.bound.stage_root(1,'primary'),self.repo/'outside',self.repo/'.venv/../outside']:
            with self.subTest(base=base.name),self.assertRaises(ValueError):
                isolation.command(self.repo,self.bound.execution_raw,self.bound.deployment_raw,base)

    def test_environment_is_closed_and_contains_no_inherited_account_variables(self):
        env=isolation.environment(self.bound.execution_raw,self.bound.deployment_raw,self.base)
        self.assertEqual(env['CODEX_HOME'],'/home/hide/.codex')
        self.assertEqual(env['TMPDIR'],str(self.base/'tmp'))
        self.assertNotIn('OPENAI_API_KEY',env)
        self.assertNotIn('HTTP_PROXY',env)

    def test_primary_only_probe_proof_does_not_authorize_paid_pipeline(self):
        review,report,raw=launch_fixture.review_bytes(self.bound)
        proof=isolation.x.inputs.parse(raw);proof['status']='heldout_primary_local_isolation_verified'
        proof=isolation.io.encoded(proof)
        value=isolation.x.inputs.parse(report);value['localIsolationProofSha256']=isolation.io.sha(proof)
        report=isolation.io.encoded(value)
        value=isolation.x.inputs.parse(review);value['reviewReportSha256']=isolation.io.sha(report)
        with self.assertRaises(ValueError):
            isolation.launch.prelaunch_review(self.bound.execution_raw,self.bound.deployment_raw,
                isolation.io.encoded(value),report,proof)

    def test_source_drift_rejected_before_directory_creation_or_local_process(self):
        self.fixture.old.git_mock.side_effect=ValueError('synthetic source failure')
        # verifyのfixture mockを外し、実verifyの経路へsynthetic失敗を渡す。
        with patch.object(isolation.p.guard,'verify',side_effect=ValueError('synthetic source failure')), \
             patch.object(isolation.subprocess,'run',side_effect=AssertionError('local process started')) as process:
            with self.assertRaises(ValueError):isolation.run(self.repo,self.bound.execution_raw,
                self.bound.deployment_raw,self.fixture.old.sdk_manifest_raw,self.base)
            process.assert_not_called()
        self.assertFalse(self.base.exists())
