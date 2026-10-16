"""合成原bytesで保持一次のnative/rollout結合を実検査。実保持/実モデル0。"""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_evidence as evidence
import test_production_heldout_inputs as input_fixture
import test_production_heldout_launch as launch_fixture
import test_production_canary_review as native_fixture
import test_routing_host as host_fixture

x,io=evidence.x,evidence.io


class HeldoutEvidenceTests(unittest.TestCase):
    def setUp(self):
        # 合成Host fixtureを72資源に拡張し、そのHost/native/rolloutを実検証器へ渡す。
        original_setup=host_fixture.RoutingHostTests.setUp
        def setup_host(test):
            original_setup(test)
            test.manifest['sourceCommit']='b'*40
            for index in range(66):
                name=f'resources/bitz-core/support/fixture-{index:02d}.txt';raw=f'public fixture {index}'.encode()
                path=test.snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                test.manifest['resources'][name]=io.sha(raw)
            test.persist_manifest()
        item=patch.object(host_fixture.RoutingHostTests,'setUp',setup_host);item.start();self.addCleanup(item.stop)
        self.input=input_fixture.HeldoutInputTests(methodName='runTest');self.input.setUp()
        self.input.contract['sourceCommit']='b'*40
        self.raws=self.input.raws
        cases=evidence.trace.strict_json((ROOT/'evals/skills/routing/production-canary-cases-v0.1.json').read_bytes())
        cases[0].update(evidence.trace.project_case(self.input.cases[0]))
        self.fixture=native_fixture.CanaryCompleteReviewTests(methodName='runTest')
        self.fixture.cases_raw=io.encoded(cases);self.fixture.instructions_raw=self.raws['instructions']
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        old=self.fixture.loaded();self.capture=self.fixture.capture
        self.manifest=old.fixed.bound.raw_inputs[2];self.profile=old.fixed.context_profile_raw
        self.schema=evidence.preflight.public.decision_schema(self.capture.git_raws[evidence.preflight.public.inventory.SCHEMA])
        old_schema=evidence.trace.strict_json(old.fixed.decision_schema_raw)
        new_schema=evidence.trace.strict_json(self.schema)
        old_wire=evidence.preflight.public.capture.execution_schema(old_schema)
        new_wire=evidence.preflight.public.capture.execution_schema(new_schema)
        item=patch.object(x.inputs,'PRIVATE_CASES',self.capture.repository/'synthetic-private/cases.json')
        item.start();self.addCleanup(item.stop)
        self.input_raw=io.encoded(self.input.contract)
        sdk_files={'openai_codex/__init__.py':'1'*64,'openai_codex-0.160.1.dist-info/METADATA':'2'*64}
        digest=hashlib.sha256()
        for name,value in sorted(sdk_files.items(),key=lambda pair:Path(pair[0]).parts):
            digest.update(name.encode()+b'\0');digest.update(bytes.fromhex(value))
        sdk=io.encoded(dict(version='0.160.1',files=sdk_files,treeSha256=digest.hexdigest()))
        runtime=self.capture.git_raws[evidence.preflight.public.capture.fixed_runtime.MANIFEST]
        runtime_spec=evidence.trace.strict_json(runtime)
        self.deployment=dict(version=x.DEPLOYMENT_VERSION,sourceCommit='b'*40,
            codexPath=self.capture.contract['codexPath'],codexVersion='codex-cli 0.160.1',
            sdkRelativePath='.venv/matrix-codex-python-sdk-deps-synthetic',sdkVersion='0.160.1',
            sdkTreeSha256=digest.hexdigest(),sdkManifestSha256=io.sha(sdk),
            snapshotRelativePath='.venv/heldout-routing-preparation-synthetic/snapshot',manifestSha256=io.sha(self.manifest),
            snapshotResourceCount=72,runtimeManifestSha256=io.sha(runtime),contextProfileSha256=io.sha(self.profile),
            calibrationManifestSha256='3'*64,certifiesSkillGate=False)
        pins=dict(snapshotManifest=io.sha(self.manifest),decisionSchema=io.sha(self.schema),contextProfile=io.sha(self.profile),
            calibrationManifest='3'*64,runtimeManifest=io.sha(runtime),sdk=digest.hexdigest(),
            cli=runtime_spec['files'][evidence.preflight.public.capture.fixed_runtime.VENDOR+'bin/codex'])
        self.execution=dict(version=x.VERSION,campaignId='heldout-matrix-synthetic-01',sourceCommit='b'*40,
            model='gpt-6.1-sol',inputContractSha256=io.sha(self.input_raw),deploymentSha256=io.sha(io.encoded(self.deployment)),
            outputRelativeRoot='measurements/heldout-matrix-synthetic-01',pins=pins,
            budget=dict(primary=24,independent=24,automaticRetries=0,delegations=0),
            timeoutSeconds=dict(primary=300,independent=300),cliVersion='0.160.1',certifiesSkillGate=False)
        self.bound=x.bind(io.encoded(self.execution),io.encoded(self.deployment),self.input_raw,**self.raws)
        self.originals=dict(old.originals)
        def update_schema(value):
            if isinstance(value,dict):
                if value==old_schema:return copy.deepcopy(new_schema)
                if value==old_wire:return copy.deepcopy(new_wire)
                return {key:update_schema(child) for key,child in value.items()}
            if isinstance(value,list):return [update_schema(child) for child in value]
            if isinstance(value,str):
                try:parsed=json.loads(value)
                except ValueError:return value
                changed=update_schema(parsed)
                return json.dumps(changed) if changed!=parsed else value
            return value
        # 公開canary fixtureのschemaだけを合成保持の六経路schemaへ投影する。
        for name,raw in self.originals.items():
            if name.endswith('.json'):self.originals[name]=io.encoded(update_schema(evidence.trace.strict_json(raw)))
            elif name.endswith('.jsonl'):
                self.originals[name]=b''.join(io.encoded(update_schema(evidence.trace.strict_json(line)))+b'\n' for line in raw.splitlines())
        # cwd置換は合成fixtureの構築だけ。実測原を改変する機能は製品コードに置かない。
        before=str(self.capture.base/'work').encode();after=str(self.bound.stage_root(1,'primary')/'work').encode()
        for name,raw in self.originals.items():
            if name.endswith(('.json','.jsonl')):self.originals[name]=raw.replace(before,after)
        review,report,isolation=launch_fixture.review_bytes(self.bound)
        self.proof=dict(status='heldout_resources_verified_not_launchable',sourceCommit='b'*40,
            executionSha256=io.sha(self.bound.execution_raw),deploymentSha256=io.sha(self.bound.deployment_raw),
            inputContractSha256=io.sha(self.input_raw),casesSha256=io.sha(self.raws['cases']),
            snapshotManifestSha256=io.sha(self.manifest),snapshotResourceCount=72,
            baselineProductSource=evidence.preflight.BASELINE_PRODUCT_SOURCE,
            productResourcesSha256=io.sha(io.encoded(evidence.trace.strict_json(self.manifest)['resources'])),
            sourceSha256={name:'4'*64 for name in evidence.preflight.SOURCE_FILES},
            contextProfileSha256=io.sha(self.profile),contextDate=evidence.trace.strict_json(self.profile)['date'],
            sdkManifestSha256=io.sha(sdk),sdkFileCount=2,sdkTreeSha256=self.deployment['sdkTreeSha256'],
            decisionSchemaSha256=io.sha(self.schema),models=0,reservations=0,launchEnabled=False,
            certifiesSkillGate=False,certifiesRelease=False,
            runtime=dict(status='fixed_runtime_bytes_match',runtimeManifestSha256=io.sha(runtime),
                codexPath=self.deployment['codexPath'],files=len(runtime_spec['files'])),
            originalCalibration=dict(status='original_local_calibration_matches',calibrationManifestSha256='3'*64,
                paidModelCalls=0,primaryModelTrajectories=0,certifiesProviderWireBodies=False))
        self.originals.update({'contract.json':self.bound.execution_raw,'deployment.json':self.bound.deployment_raw,
            'reservation.json':io.encoded(evidence.launch.primary_identity(self.bound,1)),
            'invocation.json':io.encoded(evidence.launch.invocation(self.capture.repository,self.bound.execution_raw,
                self.bound.deployment_raw,evidence.launch.primary_identity(self.bound,1))),
            'config.json':io.encoded(evidence.preflight.public.capture.config_for(self.bound.stage_root(1,'primary'),
                self.deployment,repository=self.capture.repository)),
            'sdk-manifest.json':sdk,'runtime-manifest.json':runtime,
            'launch-settings.json':evidence.launch.launch_settings(self.bound.execution_raw,self.bound.deployment_raw),
            'resource-guards.json':io.encoded(dict.fromkeys(['before','invoke','after'],self.proof)),
            'prelaunch-review.json':review,'prelaunch-report.json':report,'local-isolation-proof.json':isolation})
        self.receipt=dict(version=evidence.VERSION,sourceCommit='b'*40,slot=self.bound.slot(1),
            cwd=str(self.bound.stage_root(1,'primary')/'work'),artifactSha256={},elapsedSeconds=2.5,
            namespaceExitCode=0,timedOut=False,primaryModelTrajectories=1,independentReviewPerformed=False,
            automaticRetries=0,phaseComplete=False,certifiesSkillGate=False)
        self.rehash()

    def rehash(self):self.receipt['artifactSha256']={name:io.sha(raw) for name,raw in self.originals.items()}

    def bind(self):
        return evidence.bind_originals(self.bound,1,self.originals,io.encoded(self.receipt),self.manifest,
            self.schema,self.profile,source_repository=self.capture.repository)

    def test_private_typed_capture_uses_real_native_and_rollout_verifiers_without_gate_claim(self):
        result=evidence.verify_complete(self.bind())
        self.assertTrue(result['rawPayloadCorrelationVerified'])
        self.assertTrue(result['rollout']['usageCorrelationVerified'])
        self.assertEqual(result['slot']['caseId'],'SE-1200')
        self.assertEqual(result['native']['hostCalls'],2)
        self.assertFalse(result['eligibleForMeasurement'])
        self.assertFalse(result['ledgerFinalized'])

    def test_primary_expected_metadata_and_case_id_cannot_be_added_even_after_rehash(self):
        for field in ['expected','caseId']:
            raw=self.originals['model-input.json'];payload=evidence.trace.strict_json(raw);payload['case'][field]='SYNTHETIC'
            self.originals['model-input.json']=io.encoded(payload);self.rehash()
            with self.subTest(field=field),self.assertRaises(ValueError):self.bind()
            self.originals['model-input.json']=raw
        self.rehash()

    def test_unknown_artifact_paths_rejected_before_buffer_consumption(self):
        for name in ['codex-home/auth.json','../cases.json','.env','rollout-traces/auth/manifest.json']:
            self.receipt['artifactSha256'][name]='5'*64
            with self.subTest(name=name),self.assertRaises(ValueError):self.bind()
            self.receipt['artifactSha256'].pop(name)

    def test_source_slot_cwd_receipt_flags_and_bool_relabel_are_rejected(self):
        original=copy.deepcopy(self.receipt)
        for key,value in [('sourceCommit','c'*40),('slot',self.bound.slot(2)),('namespaceExitCode',False),
            ('primaryModelTrajectories',True),('cwd','/outside/work'),('elapsedSeconds',True),
            ('elapsedSeconds',float('inf')),('certifiesSkillGate',True)]:
            self.receipt=copy.deepcopy(original);self.receipt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()

    def test_configuration_invocation_launch_and_three_guard_drift_rejected(self):
        original=dict(self.originals)
        for name in ['invocation.json','config.json','launch-settings.json','prelaunch-report.json','resource-guards.json']:
            self.originals=dict(original);self.originals[name]=b'{}';self.rehash()
            with self.subTest(name=name),self.assertRaises(ValueError):self.bind()

    def test_immutable_capture_rebinds_and_native_mutation_is_not_accepted(self):
        context=self.bind()
        with self.assertRaises(TypeError):context.originals['rpc-out.jsonl']=b'changed'
        raw=dict(context.originals);raw['rpc-out.jsonl']+=b'changed'
        with self.assertRaises(ValueError):
            evidence.verify_complete(replace(context,original_items=tuple(raw.items())))
        self.originals['rpc-out.jsonl']=self.originals['rpc-out.jsonl'].replace(b'turn/completed',b'turn/broken')
        self.rehash()
        with self.assertRaises(ValueError):evidence.verify_complete(self.bind())

    def test_rehashed_resource_proof_scope_runtime_and_unknown_fields_rejected(self):
        for key,value in [('models',True),('launchEnabled',True),('sdkFileCount',207),
            ('runtime',{}),('originalCalibration',{}),('invented',True)]:
            changed=dict(self.proof);changed[key]=value
            self.originals['resource-guards.json']=io.encoded(dict.fromkeys(['before','invoke','after'],changed))
            self.rehash()
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()
