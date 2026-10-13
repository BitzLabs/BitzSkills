"""行列原入力の取り違え・改変・原RPC/rolloutの不整合を合成bytesで検査。モデル0。"""
import copy
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_evidence as evidence
import test_production_matrix_inputs as inputs_fixture
import test_production_canary_review as native_fixture


class MatrixEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture=inputs_fixture.MatrixInputTests(methodName='runTest');fixture.setUp()
        self.raws=fixture.raws;self.input_contract=fixture.contract
        self.input_contract['sourceCommit']='b'*40
        cases=evidence.trace.strict_json(self.raws['routing'])
        small=evidence.trace.strict_json((ROOT/'evals/skills/routing/production-canary-cases-v0.1.json').read_bytes())
        small[0].update(evidence.trace.project_case(cases[0]))
        self.fixture=native_fixture.CanaryCompleteReviewTests(methodName='runTest')
        self.fixture.cases_raw=evidence.io.encoded(small)
        self.fixture.instructions_raw=self.raws['instructions']
        self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        old=self.fixture.loaded();self.capture=self.fixture.capture
        input_raw=evidence.io.encoded(self.input_contract)
        self.manifest=old.fixed.bound.raw_inputs[2];self.schema=old.fixed.decision_schema_raw;self.profile=old.fixed.context_profile_raw
        pins={key:'c'*64 for key in evidence.matrix.PINS}
        pins.update(snapshotManifest=evidence.io.sha(self.manifest),decisionSchema=evidence.io.sha(self.schema),contextProfile=evidence.io.sha(self.profile))
        contract=dict(version=evidence.matrix.VERSION,campaignId='public-matrix-synthetic',sourceCommit='b'*40,
            model='gpt-6.1-sol',inputContractSha256=evidence.io.sha(input_raw),
            outputRelativeRoot=str(self.capture.base.parent.relative_to(self.capture.repository)),pins=pins,
            budget=dict(primary=92,independent=92,automaticRetries=0,delegations=0),
            timeoutSeconds=dict(primary=240,independent=300),cliVersion='0.160.1',certifiesSkillGate=False)
        self.bound=evidence.matrix.bind(evidence.io.encoded(contract),input_raw,**self.raws)
        self.originals=dict(old.originals)
        self.originals.update({'contract.json':self.bound.execution_raw,'reservation.json':evidence.io.encoded(self.bound.slot(1))})
        self.assertEqual(self.originals['model-input.json'],self.bound.matrix.payloads[0])
        self.receipt=dict(version=evidence.VERSION,sourceCommit='b'*40,slot=self.bound.slot(1),cwd=str(self.capture.base/'work'),
            artifactSha256={name:evidence.io.sha(raw) for name,raw in self.originals.items()},elapsedSeconds=2.5,
            namespaceExitCode=0,timedOut=False,primaryModelTrajectories=1,independentReviewPerformed=False,
            automaticRetries=0,phaseComplete=False,certifiesSkillGate=False)

    def bind(self):
        return evidence.bind_originals(self.bound,1,self.originals,evidence.io.encoded(self.receipt),self.manifest,self.schema,self.profile)

    def rehash(self):
        self.receipt['artifactSha256']={name:evidence.io.sha(raw) for name,raw in self.originals.items()}

    def test_matrix_originals_reuse_actual_native_host_and_rollout_correlations(self):
        result=evidence.verify_complete(self.bind())
        self.assertEqual(result['slot']['caseId'],'SE-001')
        self.assertEqual(result['slot']['ordinal'],1)
        self.assertTrue(result['originalInputMatched'])
        self.assertTrue(result['rollout']['usageCorrelationVerified'])
        self.assertEqual(result['native']['hostCalls'],2)
        for name in ['eligibleForMeasurement','ledgerFinalized','independentReviewPerformed','certifiesSkillGate','sourceRuntimeOnDiskVerified','launchEnvironmentVerified']:
            self.assertFalse(result[name])

    def test_other_slot_and_boolean_ids_cannot_relabel_same_native_result(self):
        self.receipt['slot']=self.bound.slot(2)
        with self.assertRaises(ValueError):self.bind()
        self.receipt['slot']=self.bound.slot(1);self.receipt['slot']['ordinal']=True
        with self.assertRaises(ValueError):self.bind()

    def test_repetition_relabel_with_rewritten_metadata_still_rejects_original_sdk_cwd(self):
        self.receipt['slot']=self.bound.slot(2)
        self.receipt['cwd']=str(self.capture.base.parent/'attempt-0002/work')
        self.originals['reservation.json']=evidence.io.encoded(self.bound.slot(2));self.rehash()
        context=evidence.bind_originals(self.bound,2,self.originals,evidence.io.encoded(self.receipt),self.manifest,self.schema,self.profile)
        with self.assertRaises(ValueError):evidence.verify_complete(context)

    def test_expected_and_case_metadata_cannot_be_added_to_primary_input_even_if_rehashed(self):
        value=evidence.trace.strict_json(self.originals['model-input.json']);value['case']['expected']={'invented':'pass'}
        self.originals['model-input.json']=evidence.io.encoded(value);self.rehash()
        with self.assertRaisesRegex(ValueError,'fixed input drift'):self.bind()

    def test_missing_unknown_and_private_artifact_names_are_rejected_before_content_consumption(self):
        before=copy.deepcopy(self.receipt)
        for name in ['.env','codex-home/auth.json','state/private.json','../receipt.json','rollout-traces/auth/manifest.json']:
            self.receipt=copy.deepcopy(before);self.receipt['artifactSha256'][name]='1'*64
            with self.subTest(name=name),self.assertRaises(ValueError):self.bind()
        self.receipt=before;self.originals.pop('rpc-out.jsonl')
        with self.assertRaises(ValueError):self.bind()

    def test_fixed_context_schema_manifest_and_consumed_raw_hashes_are_bound(self):
        for name in ['manifest','schema','profile']:
            before=getattr(self,name);setattr(self,name,before+b' ')
            with self.subTest(name=name),self.assertRaises(ValueError):self.bind()
            setattr(self,name,before)
        self.originals['rpc-out.jsonl']+=b' '
        with self.assertRaisesRegex(ValueError,'hash drift'):self.bind()

    def test_receipt_status_finite_time_and_full_slot_identity_are_closed(self):
        before=copy.deepcopy(self.receipt)
        for key,value in [('sourceCommit','f'*40),('primaryModelTrajectories',True),('namespaceExitCode',False),
                          ('elapsedSeconds',True),('elapsedSeconds',-1),('elapsedSeconds',float('inf')),
                          ('independentReviewPerformed',True),('phaseComplete',True),('cwd','/outside/work')]:
            self.receipt=copy.deepcopy(before);self.receipt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()

    def test_immutable_capture_cannot_be_modified_to_skip_rebinding(self):
        context=self.bind()
        with self.assertRaises(TypeError):context.originals['rpc-out.jsonl']=b'changed'
        original=dict(context.originals);original['rpc-out.jsonl']+=b'changed'
        with self.assertRaises(ValueError):evidence.verify_complete(replace(context,original_items=tuple(original.items())))
        with self.assertRaises(ValueError):evidence.verify_complete({})

    def test_bound_bytes_verification_does_not_read_disk_or_depend_on_ambient_schema(self):
        context=self.bind();expected=evidence.verify_complete(context)
        with (patch.object(evidence.trace,'ROOT',Path('/unbound-schema-root')),
             patch.object(Path,'read_bytes',side_effect=AssertionError('unbound disk schema read')),
             patch.object(evidence.io,'read_regular',side_effect=AssertionError('unbound original read'))):
            self.assertEqual(evidence.verify_complete(context),expected)

    def test_rehashed_original_rpc_policy_and_host_body_tampering_are_rejected(self):
        originals=dict(self.originals)
        for fault in ['provider','schema','input','host']:
            self.originals=dict(originals)
            if fault=='host':
                events=evidence.primary.json_lines(self.originals['host.jsonl']);events[-1]['result']['content']+='changed'
                self.originals['host.jsonl']=b''.join(evidence.io.encoded(x)+b'\n' for x in events)
            else:
                sent=evidence.primary.json_lines(self.originals['rpc-in.jsonl'])
                if fault=='provider':sent[2]['params']['modelProvider']='other'
                elif fault=='schema':sent[3]['params']['outputSchema']={}
                else:sent[3]['params']['input'][0]['text']+='changed'
                self.originals['rpc-in.jsonl']=b''.join(evidence.io.encoded(x)+b'\n' for x in sent)
            self.rehash()
            with self.subTest(fault=fault),self.assertRaises(ValueError):evidence.verify_complete(self.bind())
