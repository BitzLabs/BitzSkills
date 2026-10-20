"""局所probeが認証とnetworkを持たず、private入力も本番予約も使わないことを検査。"""
import copy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
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

    def test_independent_probe_derives_same_mounts_and_only_replaces_auth_network_command(self):
        import production_heldout_score as score
        original=score.namespace_for_execution(self.bound.execution_raw,self.bound.deployment_raw,1)
        argv=isolation.independent_command(self.repo,self.bound.execution_raw,self.bound.deployment_raw,self.base)
        self.assertNotIn(str(isolation.launch.AUTH),argv);self.assertEqual(argv.count('--unshare-net'),1)
        self.assertEqual(argv[argv.index('--')+1:argv.index('--')+5],['/usr/bin/python3','-B','-c',isolation.INDEPENDENT_PROBE])
        mounts=lambda args:[args[n+1:n+3] for n,k in enumerate(args[:args.index('--')]) if k in {'--bind','--ro-bind'}]
        paid=str(self.bound.stage_root(1,'independent'))
        expected=[[str(self.base)+v[len(paid):] if v.startswith(paid) else v for v in pair]
            for pair in mounts(original) if pair[0]!=str(isolation.launch.AUTH)]
        self.assertEqual(mounts(argv),expected)
        self.assertEqual(mounts(argv),[["/","/"],[str(Path(self.fixture.deployment['codexPath']).parents[1])]*2,
            [str(self.base)]*2,[str(self.base/'codex-home'),'/home/hide/.codex']])
        self.fixture.reader.assert_not_called()

    def test_both_nested_proofs_are_required_and_bound_to_source_condition_and_hash(self):
        _,_,raw=launch_fixture.review_bytes(self.bound);proof=isolation.x.inputs.parse(raw)
        isolation.launch.local_pair_proof(self.bound.execution_raw,self.bound.deployment_raw,proof)
        for role in ['primary','independent']:
            for key,value in [('actualExitCode',True),('actualExitCode',1),('models',True),('models',1),
                ('privateCaseContentsRead',True),('sourceCommit','f'*40),('conditionSha256','f'*64),
                ('privateCorpusHidden',False),(role+'PayloadProjectionVerified',False)]:
                bad=copy.deepcopy(proof);bad[role+'Proof'][key]=value
                bad[role+'ProofSha256']=isolation.io.sha(isolation.io.encoded(bad[role+'Proof']))
                with self.subTest(role=role,key=key,value=value),self.assertRaises(ValueError):
                    isolation.launch.local_pair_proof(self.bound.execution_raw,self.bound.deployment_raw,bad)
            bad=copy.deepcopy(proof);bad.pop(role+'Proof')
            with self.assertRaises(ValueError):isolation.launch.local_pair_proof(self.bound.execution_raw,self.bound.deployment_raw,bad)
            bad=copy.deepcopy(proof);bad[role+'ProofSha256']='f'*64
            with self.assertRaises(ValueError):isolation.launch.local_pair_proof(self.bound.execution_raw,self.bound.deployment_raw,bad)

    def test_pair_builder_cannot_turn_failed_or_primary_only_result_into_approval(self):
        _,_,raw=launch_fixture.review_bytes(self.bound);proof=isolation.x.inputs.parse(raw)
        primary,independent=proof['primaryProof'],proof['independentProof']
        pair=isolation.pair_proof(self.bound.execution_raw,self.bound.deployment_raw,primary,independent)
        self.assertEqual(pair['status'],'heldout_local_isolation_verified');self.assertFalse(pair['certifiesHeldoutLaunch'])
        bad=dict(independent,status='heldout_independent_local_isolation_failed')
        with self.assertRaises(ValueError):isolation.pair_proof(self.bound.execution_raw,self.bound.deployment_raw,primary,bad)
        with self.assertRaises(ValueError):isolation.pair_proof(self.bound.execution_raw,self.bound.deployment_raw,primary,primary)

    def test_independent_probe_source_failure_precedes_any_process_or_directory(self):
        with patch.object(isolation.p.guard,'verify',side_effect=ValueError('source drift')), \
                patch.object(isolation.subprocess,'run',side_effect=AssertionError('process')):
            with self.assertRaises(ValueError):isolation.run_independent(self.repo,self.bound.execution_raw,
                self.bound.deployment_raw,self.base)
        self.assertFalse(self.base.exists());self.fixture.reader.assert_not_called()

    def test_independent_probe_saves_original_argv_and_public_synthetic_payload_without_model(self):
        def process(argv,**kwargs):
            self.assertEqual(kwargs['umask'],0o077);self.assertEqual(kwargs['timeout'],60)
            self.assertNotIn(str(isolation.launch.AUTH),argv)
            result=dict(status='heldout_independent_local_probe_completed',networkNamespaceIsolated=True,
                credentialsHidden=True,privateCorpusHidden=True,independentPayloadProjectionVerified=True,
                cliVersionVerified=True,models=0,reservations=0)
            isolation.io.exclusive(self.base/'probe-result.json',isolation.io.encoded(result))
            return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
        with patch.object(isolation.p.guard,'verify'),patch.object(isolation.p.capture.fixed_runtime,'verify'), \
                patch.object(isolation.subprocess,'run',side_effect=process) as start:
            result=isolation.run_independent(self.repo,self.bound.execution_raw,self.bound.deployment_raw,self.base)
        self.assertEqual(start.call_count,1);self.assertEqual(result['status'],'heldout_independent_local_isolation_verified')
        self.assertEqual(result['models'],0);self.assertFalse(result['privateCaseContentsRead'])
        self.assertEqual(isolation.io.read_regular(self.base/'review-input.json'),isolation.io.encoded(isolation.INDEPENDENT_PROMPT))
        self.fixture.reader.assert_not_called()
