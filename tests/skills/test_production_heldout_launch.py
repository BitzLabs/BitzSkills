"""合成データで単一payloadのnamespace構成とSDK worker境界を検証。実モデル0。"""
import copy
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_launch as launch
import production_heldout_capture as child
import test_production_heldout_execution as fixture


def review_bytes(bound):
    io = launch.io
    condition = launch.condition_sha256(bound.execution_raw,bound.deployment_raw)
    isolation = io.encoded(dict(status='heldout_local_isolation_verified',sourceCommit=bound.contract['sourceCommit'],
        conditionSha256=condition,networkNamespaceIsolated=True,credentialsHidden=True,privateCorpusHidden=True,
        primaryPayloadProjectionVerified=True,actualArgvVerified=True,models=0,reservations=0))
    report = io.encoded(dict(status='heldout_pipeline_concrete_prelaunch_verified',sourceCommit=bound.contract['sourceCommit'],
        conditionSha256=condition,independentContext=True,findings=[],blockingFindings=[],cleanBefore='',cleanAfter='',
        tests=dict(count=1,exitCode=0),localIsolationProofSha256=io.sha(isolation)))
    review = io.encoded(dict(version=launch.REVIEW_VERSION,scope='heldout-primary-and-independent-launch-only',
        sourceCommit=bound.contract['sourceCommit'],conditionSha256=condition,reviewReportSha256=io.sha(report),
        independentContext=True,severityCounts=dict(P1=0,P2=0),certifiesSkillGate=False,certifiesRelease=False))
    return review,report,isolation


class HeldoutLaunchTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutExecutionTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bound=self.fixture.bind();self.repo=self.fixture.repository

    def test_primary_identity_and_argv_never_include_case_metadata_or_corpus_mount(self):
        identity=launch.primary_identity(self.bound,1)
        self.assertNotIn('caseId',identity)
        argv=launch.namespace_command(self.repo,self.bound.execution_raw,self.bound.deployment_raw,1)
        mounts=[argv[i+1:i+3] for i,arg in enumerate(argv) if arg in {'--bind','--ro-bind'}]
        base=self.bound.stage_root(1,'primary')
        self.assertIn([str(base),str(base)],mounts)
        self.assertIn([str(base/'codex-home'),'/home/hide/.codex'],mounts)
        for path in [self.repo,self.repo/'.git',self.repo/'evals/skills/cases',launch.x.inputs.PRIVATE_CASES,
                     launch.x.inputs.PRIVATE_CASES.parent,base.parent,base.parent.parent]:
            self.assertFalse(any(pair[0]==str(path) for pair in mounts))
        self.assertNotIn('SE-1200',str(argv))
        self.assertIn(['--tmpfs','/home'],[argv[i:i+2] for i in range(len(argv)-1)])
        self.assertEqual(argv[-2:],['--isolated',str(base)])
        plan=launch.invocation(self.repo,self.bound.execution_raw,self.bound.deployment_raw,identity)
        self.assertEqual(plan['processUmask'],0o077)
        self.assertEqual(plan['automaticRetries'],0)

    def test_identity_wrong_ordinal_case_label_and_repetition_rejected(self):
        original=launch.primary_identity(self.bound,1)
        for key,value in [('ordinal',True),('ordinal',25),('repetition',2),('repetition',True),
                          ('executionSha256','0'*64),('caseId','SE-1200')]:
            identity=dict(original);identity[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                launch.invocation(self.repo,self.bound.execution_raw,self.bound.deployment_raw,identity)

    def test_only_current_concrete_independent_review_allows_worker_validation(self):
        review,report,isolation=review_bytes(self.bound)
        launch.prelaunch_review(self.bound.execution_raw,self.bound.deployment_raw,review,report,isolation)
        original=launch.x.inputs.parse(review)
        for key,value in [('independentContext',False),('scope','public-matrix-primary-launch-only'),
                          ('sourceCommit','f'*40),('conditionSha256','0'*64),('certifiesRelease',True)]:
            changed=dict(original);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                launch.prelaunch_review(self.bound.execution_raw,self.bound.deployment_raw,
                    launch.io.encoded(changed),report,isolation)
        with self.assertRaises(ValueError):
            launch.prelaunch_review(self.bound.execution_raw,self.bound.deployment_raw,review,report+b' ',isolation)

    def test_failed_private_isolation_proof_cannot_be_rehashed_into_prelaunch_pass(self):
        _,report,isolation=review_bytes(self.bound)
        proof=launch.x.inputs.parse(isolation);proof['privateCorpusHidden']=False
        isolation=launch.io.encoded(proof)
        report=launch.x.inputs.parse(report);report['localIsolationProofSha256']=launch.io.sha(isolation)
        report=launch.io.encoded(report)
        review=launch.x.inputs.parse(review_bytes(self.bound)[0]);review['reviewReportSha256']=launch.io.sha(report)
        with self.assertRaises(ValueError):
            launch.prelaunch_review(self.bound.execution_raw,self.bound.deployment_raw,
                launch.io.encoded(review),report,isolation)

    def child_fixture(self):
        root=self.repo/'child-root';root.mkdir()
        item=patch.object(child,'ROOT',root);item.start();self.addCleanup(item.stop)
        item=patch.object(launch.x.inputs,'PRIVATE_CASES',self.repo/'synthetic-private/cases.json')
        item.start();self.addCleanup(item.stop)
        d=launch.x.deployment_for_execution(self.bound.execution_raw,self.bound.deployment_raw)
        for name in [d['snapshotRelativePath'],d['sdkRelativePath']]:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(self.repo/name,target)
        base=self.bound.stage_root(1,'primary');base.mkdir(parents=True,mode=0o700)
        (base/'work').mkdir(mode=0o700)
        review,report,isolation=review_bytes(self.bound)
        identity=launch.primary_identity(self.bound,1)
        originals={'contract.json':self.bound.execution_raw,'deployment.json':self.bound.deployment_raw,
            'reservation.json':launch.io.encoded(identity),'prelaunch-review.json':review,'prelaunch-report.json':report,
            'local-isolation-proof.json':isolation,'model-input.json':self.bound.matrix.payloads[0],
            'invocation.json':launch.io.encoded(launch.invocation(root,self.bound.execution_raw,self.bound.deployment_raw,identity)),
            'sdk-manifest.json':self.fixture.old.sdk_manifest_raw,
            'runtime-manifest.json':self.fixture.old.originals[fixture.preflight.public.capture.fixed_runtime.MANIFEST],
            'decision-schema.json':fixture.preflight.public.decision_schema(
                self.fixture.old.originals[fixture.preflight.public.inventory.SCHEMA]),
            'launch-settings.json':launch.launch_settings(self.bound.execution_raw,self.bound.deployment_raw)}
        for name,raw in originals.items():(base/name).write_bytes(raw)
        return root,base,originals

    def test_child_validates_only_one_primary_payload_and_rejects_hidden_corpus_visibility(self):
        root,base,_=self.child_fixture()
        c,d,payload,schema=child.child_inputs(base)
        self.assertEqual(payload,self.bound.matrix.payloads[0])
        self.assertEqual(c['budget']['primary'],24)
        (root/'.git').write_bytes(b'synthetic visible repository')
        with self.assertRaisesRegex(ValueError,'corpus visible'):child.child_inputs(base)

    def test_rehashed_primary_payload_with_expected_is_rejected_before_sdk_start(self):
        _,base,originals=self.child_fixture()
        payload=launch.x.inputs.parse(originals['model-input.json']);payload['case']['expected']={'sentinel':'private'}
        raw=launch.io.encoded(payload);(base/'model-input.json').write_bytes(raw)
        identity=launch.x.inputs.parse(originals['reservation.json']);identity['payloadSha256']=launch.io.sha(raw)
        (base/'reservation.json').write_bytes(launch.io.encoded(identity))
        with self.assertRaisesRegex(ValueError,'projection'):child.child_inputs(base)

    def test_sdk_worker_passes_only_projected_input_with_no_real_client_or_process(self):
        _,base,_=self.child_fixture();calls={}
        class FakeClient:
            def __init__(self,config,approval_handler):calls['config']=config;calls['deny']=approval_handler
            def start(self):calls['start']=True
            def initialize(self):pass
            def thread_start(self,value):calls['thread']=value;return SimpleNamespace(thread=SimpleNamespace(id='fake-thread'))
            def turn_start(self,thread,text,options):calls['text']=text;return SimpleNamespace(turn=SimpleNamespace(id='fake-turn'))
            def next_turn_notification(self,turn):return SimpleNamespace(method='turn/completed')
            def close(self):calls['closed']=True
        sdk=ModuleType('openai_codex');sdk.__version__='0.160.1';sdk.CodexConfig=lambda **kw:kw
        client=ModuleType('openai_codex.client');client.CodexClient=FakeClient
        version=SimpleNamespace(returncode=0,stdout=b'codex-cli 0.160.1\n',stderr=b'')
        with patch.dict(sys.modules,{'openai_codex':sdk,'openai_codex.client':client}), \
             patch.object(child.subprocess,'run',return_value=version),patch.object(child.os,'umask'):
            child.isolated(base)
        self.assertEqual(calls['text'].encode(),self.bound.matrix.payloads[0])
        self.assertEqual(set(launch.x.inputs.parse(calls['text'])['case']),{'prompt','context'})
        self.assertTrue(calls['closed'])
        with self.assertRaises(ValueError):calls['deny']('unexpected')
        self.assertEqual(launch.x.inputs.parse((base/'isolated-result.json').read_bytes()),{'sdkErrorType':None})
