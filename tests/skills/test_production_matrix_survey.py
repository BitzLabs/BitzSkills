"""全枠調査の失敗終端・持越し・改変拒否。モデル呼出しなし。"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_survey as survey
import test_production_matrix_ledger as fixture
matrix=survey.matrix
io=matrix.io


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.MatrixLedgerTests(methodName='runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.repository=self.f.repository
        self.policy=dict(version=survey.VERSION,sourceCommit=self.f.contract['sourceCommit'],
            campaignId=self.f.contract['campaignId'],startOrdinal=1,baselineSourceCommit=None,
            baselineCampaignId=None,baselineReport=None,priorSlots=[],baselineExecution=None,
            baselineInputContract=None,baselineDeployment=None,baselineSnapshotManifest=None,
            productResources={f'resources/synthetic{n}/SKILL.md':'d'*64 for n in range(6)})
        self.configure()

    def configure(self):
        self.policy_raw=io.encoded(self.policy)
        self.f.contract.update(version=matrix.SURVEY_VERSION,surveyPolicySha256=io.sha(self.policy_raw))
        self.f.bound=self.f.bind();self.bound=self.f.bound
        self.instance=survey.SurveyLedger(self.f.storage,self.repository,self.bound,self.policy_raw)
        self.f.instance=self.instance
        self.control=self.repository/'.venv/production-matrix-launch-controls'/self.f.contract['campaignId']
        self.control.mkdir(parents=True,exist_ok=True)

    def ref(self,path,raw):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        return dict(relativePath=path.relative_to(self.repository).as_posix(),sha256=io.sha(raw))

    def failure(self,n=1,phase='primary', *, configure=True):
        if configure:
            self.instance.reserve(n);self.instance.mark_primary_started(n)
            if phase!='primary':self.instance.record_primary(n,self.f.primary(n))
            if phase!='primary':self.instance.reserve_independent(n,'c'*64)
            self.instance.stop(n,{'primary':'primary-capture-rejected','independent':'independent-capture-failed',
                'parent':'parent-original-verification-failed'}[phase],'ValueError')
        proof=dict(sourceCommit=self.bound.contract['sourceCommit'],executionSha256=io.sha(self.bound.execution_raw),
            status='matrix_deployment_resources_verified_launch_not_enabled')
        proofref=self.ref(self.control/'survey-resource-proof.json',io.encoded(proof))
        stage=Path(self.f.contract['outputRelativeRoot']+('' if phase=='primary' else '-independent'))/f'attempt-{n:04d}'
        name='receipt.json' if phase=='primary' else 'independent-receipt.json'
        receipt=dict(slot=self.bound.slot(n),primaryModelTrajectories=1,namespaceExitCode=0) if phase=='primary' else dict(slot=self.bound.slot(n),independentInvocations=1,exitCode=1)
        receipt['artifactSha256']={}
        if phase=='primary':
            self.ref(self.repository/stage/'rpc-out.jsonl',b'public synthetic failed trace')
            receipt['artifactSha256']={'rpc-out.jsonl':io.sha(b'public synthetic failed trace')}
            from production_matrix_evidence import PROVIDER_ARTIFACTS
            for artifact_name in PROVIDER_ARTIFACTS:
                self.ref(self.repository/stage/artifact_name,b'public synthetic provider original')
                receipt['artifactSha256'][artifact_name]=io.sha(b'public synthetic provider original')
        receiptref=self.ref(self.repository/stage/name,io.encoded(receipt))
        observation=dict(version=survey.VERSION,slot=self.bound.slot(n),phase=phase,resourceProof=proofref,stageReceipt=receiptref,
            primary={'status':'primary_capture_stopped','actualNamespaceInvocations':1} if phase=='primary' else {'status':'primary_capture_awaits_independent_review'},
            independent=None if phase=='primary' else {'status':'matrix_independent_capture_stopped'},
            parent={'ledgerFinalized':False} if phase=='parent' else None)
        ref=self.ref(self.control/f'failure-observation-{n:04d}.json',io.encoded(observation))
        self.instance.record_failure(n,phase,ref)
        return observation,ref

    def test_primary_failure_allows_next_without_measurement(self):
        self.failure();self.instance.reserve(2);s=self.instance.summary()
        self.assertEqual((s['evaluationFailed'],s['measuredIncorrect'],s['evaluatedSlots'],s['pendingSlots']), (1,0,1,1))
        self.assertFalse((self.f.storage/'stop.json').exists())

    def test_independent_failure_allows_next(self):
        self.failure(phase='independent');self.instance.reserve(2)
        self.assertEqual(self.instance.summary()['evaluationFailed'],1)

    def test_parent_failure_allows_next(self):
        self.failure(phase='parent');self.instance.reserve(2)

    def test_rejection_alone_cannot_advance(self):
        self.instance.reserve(1);self.instance.stop(1,'primary-capture-rejected','ValueError')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertFalse((self.f.storage/'stop.json').exists())

    def test_normal_incorrect_and_failure_are_distinct(self):
        self.f.complete(1,correct=False);self.failure(2);s=self.instance.summary()
        self.assertEqual((s['measuredIncorrect'],s['evaluationFailed'],s['evaluatedSlots']), (1,1,2))

    def test_failure_cannot_be_retried(self):
        self.failure()
        with self.assertRaises(ValueError):self.instance.reserve(1)
        with self.assertRaises(ValueError):self.instance.mark_primary_started(1)

    def test_failure_cannot_become_normal_primary(self):
        self.failure()
        with self.assertRaises(ValueError):self.instance.record_primary(1,self.f.primary(1))

    def test_observation_tampering_stops_even_after_restoration(self):
        _,ref=self.failure();path=self.repository/ref['relativePath'];raw=path.read_bytes();path.write_bytes(b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        path.write_bytes(raw)
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_resource_proof_tampering_stops(self):
        self.failure();(self.control/'survey-resource-proof.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_rejection_tampering_stops(self):
        self.failure();self.instance.path('rejection',1).write_bytes(b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)

    def test_unknown_ledger_record_stops(self):
        self.failure();(self.f.storage/'extra').write_bytes(b'')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_global_failure_cannot_continue(self):
        self.instance.reserve(1);self.instance.stop(1,'stored-evidence-rejected','ValueError')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertEqual(self.instance.summary()['status'],'stopped')

    def test_policy_drift_stops(self):
        self.instance.reserve(1)
        with self.assertRaises(ValueError):survey.SurveyLedger(self.f.storage,self.repository,self.bound,b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)

    def test_wrong_source_policy_rejected(self):
        self.policy['sourceCommit']='e'*40
        with self.assertRaises(ValueError):self.configure()

    def test_prior_coverage_no_reexecution(self):
        self.policy.update(startOrdinal=2,baselineSourceCommit='e'*40,baselineCampaignId='public-matrix-baseline')
        import production_matrix_capture as capture
        old_input=matrix.strict_json(self.f.input_raw);old_input['sourceCommit']='e'*40;old_input_raw=io.encoded(old_input)
        self.policy['baselineInputContract']=self.ref(self.repository/'.venv/baseline/input.json',old_input_raw)
        old_manifest=io.encoded(dict(sourceCommit='e'*40,resources=self.policy['productResources']))
        self.policy['baselineSnapshotManifest']=self.ref(self.repository/'.venv/baseline/manifest.json',old_manifest)
        old_contract=dict(self.f.contract);old_contract.update(version=matrix.VERSION,sourceCommit='e'*40,
            campaignId='public-matrix-baseline',inputContractSha256=io.sha(old_input_raw))
        del old_contract['surveyPolicySha256'];old_contract['pins']=dict(old_contract['pins'],snapshotManifest=io.sha(old_manifest))
        old_raw=io.encoded(old_contract);self.policy['baselineExecution']=self.ref(self.repository/'.venv/baseline/execution.json',old_raw)
        old_deployment=dict(version=capture.p.VERSION,sourceCommit='e'*40,executionSha256=io.sha(old_raw),
            codexPath=str(capture.p.capture.fixed_runtime.ROOT/'bin/codex'),codexVersion='codex-cli 0.160.1',
            sdkRelativePath='.venv/matrix-codex-python-sdk-deps-test',sdkVersion='0.160.1',sdkTreeSha256='b'*64,
            sdkManifestSha256='b'*64,snapshotRelativePath='.venv/matrix-routing-preparation-test/snapshot',
            manifestSha256=io.sha(old_manifest),snapshotResourceCount=6,runtimeManifestSha256='b'*64,
            contextProfileSha256='b'*64,calibrationManifestSha256='b'*64,certifiesSkillGate=False)
        old_deployment_raw=io.encoded(old_deployment)
        self.policy['baselineDeployment']=self.ref(self.repository/'.venv/baseline/deployment.json',old_deployment_raw)
        old_bound=matrix.bind(old_raw,old_input_raw,**self.f.raws)
        old_condition=capture.condition_sha256(old_bound,old_deployment_raw)
        old=dict(sourceCommit='e'*40,campaignId='public-matrix-baseline',conditionSha256=old_condition,ordinal=1,caseId='SE-001',repetition=1,
            errorType='ValueError',parent=None,primary={'actualNamespaceInvocations':1,'status':'primary_capture_stopped'},independent=None)
        reference=self.ref(self.repository/'.venv/baseline/actual-slot-0001.json',io.encoded(old))
        self.policy['priorSlots']=[dict(ordinal=1,status='evaluation_failed',reference=reference)]
        baseline=dict(sourceCommit='e'*40,campaignId='public-matrix-baseline',primaryReserved=1,
            measuredCorrect=0,measuredIncorrect=0,failedSlots=1)
        self.policy['baselineReport']=self.ref(self.repository/'.venv/baseline/report.json',io.encoded(baseline));self.configure()
        with self.assertRaises(ValueError):self.instance.reserve(1)
        self.instance.reserve(2);s=self.instance.summary()
        self.assertEqual((s['primaryReserved'],s['evaluationFailed'],s['carriedSlots']), (2,1,1))
        self.assertFalse(self.instance.path('attempt',1).exists())

    def test_prior_product_change_rejected(self):
        self.test_prior_coverage_no_reexecution()
        self.policy['productResources']['resources/synthetic0/SKILL.md']='f'*64
        with self.assertRaisesRegex(ValueError,'product resources'):self.configure()

    def test_prior_payload_change_rejected(self):
        self.test_prior_coverage_no_reexecution()
        old=self.f.raws['instructions']
        self.f.raws['instructions']=old+b' changed'
        # 新入力を更新しても旧契約へ束縛し直せない。
        contract=matrix.strict_json(self.f.input_raw);contract['inputSha256']['instructions']=io.sha(self.f.raws['instructions'])
        self.f.input_raw=io.encoded(contract);self.f.contract['inputContractSha256']=io.sha(self.f.input_raw)
        with self.assertRaises(ValueError):self.configure()

    def test_carried_primary_launch_is_counted_once(self):
        self.test_prior_coverage_no_reexecution()
        self.assertEqual(self.instance.summary()['primaryLaunchMarked'],1)

    def test_normal_completion_still_valid(self):
        self.f.complete();self.instance.reserve(2)
        self.assertEqual(self.instance.summary()['measuredCorrect'],1)

    def test_legacy_factory_does_not_require_survey_policy(self):
        contract=dict(self.f.contract);contract['version']=matrix.VERSION;del contract['surveyPolicySha256']
        bound=matrix.bind(io.encoded(contract),self.f.input_raw,**self.f.raws)
        old=matrix.open_ledger(self.repository/'.venv/old-ledger',self.repository,bound)
        self.assertIs(type(old),matrix.MatrixLedger)
        old.reserve(1);old.stop(1,'primary-capture-rejected','ValueError')
        with self.assertRaises(ValueError):old.reserve(2)

    def test_survey_factory_requires_bound_policy(self):
        with self.assertRaises(OSError):matrix.open_ledger(self.f.storage,self.repository,self.bound)
        (self.control/'survey-policy.json').write_bytes(self.policy_raw)
        self.assertIsInstance(matrix.open_ledger(self.f.storage,self.repository,self.bound),survey.SurveyLedger)

    def test_failed_trace_drift_prevents_next(self):
        self.failure();(self.repository/self.f.contract['outputRelativeRoot']/'attempt-0001/rpc-out.jsonl').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_failed_receipt_drift_prevents_next(self):
        observation,_=self.failure();(self.repository/observation['stageReceipt']['relativePath']).write_bytes(b'{}')
        with self.assertRaises(ValueError):self.instance.reserve(2)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_missing_rejection_stops_failure_submission(self):
        self.instance.reserve(1)
        with self.assertRaises(OSError):self.instance.record_failure(1,'primary',dict(relativePath='.venv/missing',sha256='a'*64))
        self.assertTrue((self.f.storage/'stop.json').exists())

    def test_failure_cannot_escape_to_credentials(self):
        self.instance.reserve(1);self.instance.stop(1,'primary-capture-rejected','ValueError')
        ref=dict(relativePath='.venv/auth.json',sha256='a'*64)
        with self.assertRaises(ValueError):self.instance.record_failure(1,'primary',ref)
        self.assertTrue((self.f.storage/'stop.json').exists())

    def nested_setup(self, *, failed=False):
        import production_matrix_capture as capture
        self.test_prior_coverage_no_reexecution()
        inherited_raw=self.policy_raw
        inherited_ref=self.ref(self.repository/'.venv/cohort/inherited-policy.json',inherited_raw)
        input_raw=self.f.input_raw
        input_ref=self.ref(self.repository/'.venv/cohort/input.json',input_raw)
        manifest_raw=io.encoded(dict(sourceCommit=self.bound.contract['sourceCommit'],resources=self.policy['productResources']))
        manifest_ref=self.ref(self.repository/'.venv/cohort/manifest.json',manifest_raw)
        old_contract=dict(self.bound.contract);old_contract['pins']=dict(old_contract['pins'],snapshotManifest=io.sha(manifest_raw))
        old_raw=io.encoded(old_contract);old_bound=matrix.bind(old_raw,input_raw,**self.f.raws)
        old_ref=self.ref(self.repository/'.venv/cohort/execution.json',old_raw)
        deployment=matrix.strict_json(self.instance.reference(self.policy['baselineDeployment']))
        deployment.update(sourceCommit=old_contract['sourceCommit'],executionSha256=io.sha(old_raw),manifestSha256=io.sha(manifest_raw))
        d_raw=io.encoded(deployment);d_ref=self.ref(self.repository/'.venv/cohort/deployment.json',d_raw)
        condition=capture.condition_sha256(old_bound,d_raw)
        status='evaluation_failed' if failed else 'measured_correct'
        driver=dict(sourceCommit=old_contract['sourceCommit'],campaignId=old_contract['campaignId'],conditionSha256=condition,
            ordinal=2,caseId='SE-001',repetition=2,status=status,globalErrorType=None,
            failurePhase='primary' if failed else None,parent=None if failed else dict(ledgerFinalized=True,proposedLedgerStatus=status),
            primary=dict(status='primary_capture_stopped' if failed else 'primary_capture_awaits_independent_review',actualNamespaceInvocations=1),
            independent=None if failed else dict(independentInvocations=1))
        driver_ref=self.ref(self.repository/'.venv/cohort/actual-slot-0002.json',io.encoded(driver))
        baseline=dict(sourceCommit=old_contract['sourceCommit'],campaignId=old_contract['campaignId'],
            ledgerSummary=dict(primaryReserved=2,measuredCorrect=0 if failed else 1,measuredIncorrect=0,
                evaluationFailed=2 if failed else 1,pendingSlots=0))
        report_ref=self.ref(self.repository/'.venv/cohort/report.json',io.encoded(baseline))
        self.policy=dict(self.policy,sourceCommit='f'*40,campaignId='public-matrix-followup',startOrdinal=3,
            baselineSourceCommit=old_contract['sourceCommit'],baselineCampaignId=old_contract['campaignId'],
            baselineReport=report_ref,baselineExecution=old_ref,baselineInputContract=input_ref,
            baselineDeployment=d_ref,baselineSnapshotManifest=manifest_ref,baselineSurveyPolicy=inherited_ref,
            priorSlots=self.policy['priorSlots']+[dict(ordinal=2,status=status,reference=driver_ref)])
        self.f.storage=self.repository/'.venv/followup-ledger'
        new_input=matrix.strict_json(input_raw);new_input['sourceCommit']='f'*40;self.f.input_raw=io.encoded(new_input)
        self.f.contract.update(sourceCommit='f'*40,campaignId=self.policy['campaignId'],
            inputContractSha256=io.sha(self.f.input_raw),outputRelativeRoot='.venv/matrix-followup')
        self.configure()

    def test_mixed_survey_and_legacy_coverage_preserved(self):
        self.nested_setup();result=self.instance.summary()
        self.assertEqual((result['carriedSlots'],result['measuredCorrect'],result['evaluationFailed']), (2,1,1))
        self.instance.reserve(3)
        self.assertFalse(self.instance.path('attempt',1).exists())
        self.assertFalse(self.instance.path('attempt',2).exists())

    def test_survey_failed_driver_without_legacy_error_type_preserved(self):
        self.nested_setup(failed=True)
        self.assertEqual(self.instance.summary()['evaluationFailed'],2)
        self.instance.reserve(3)

    def test_missing_inherited_policy_rejected(self):
        self.nested_setup();del self.policy['baselineSurveyPolicy']
        with self.assertRaises(ValueError):self.configure()

    def test_inherited_policy_original_drift_rejected(self):
        self.nested_setup();path=self.repository/self.policy['baselineSurveyPolicy']['relativePath'];path.write_bytes(b'{}')
        with self.assertRaises(ValueError):self.configure()

    def test_inherited_prefix_cannot_be_replaced(self):
        self.nested_setup();self.policy['priorSlots'][0]=dict(self.policy['priorSlots'][0],status='measured_correct')
        with self.assertRaisesRegex(ValueError,'inherited prefix'):self.configure()

    def test_no_progress_inherited_cohort_rejected(self):
        self.nested_setup();self.policy.update(startOrdinal=2,priorSlots=self.policy['priorSlots'][:1])
        with self.assertRaisesRegex(ValueError,'must advance'):self.configure()

    def test_pending_cohort_cannot_be_carried(self):
        self.nested_setup();ref=self.policy['baselineReport'];path=self.repository/ref['relativePath']
        report=matrix.strict_json(path.read_bytes());report['ledgerSummary']['pendingSlots']=1
        self.policy['baselineReport']=self.ref(path,io.encoded(report))
        with self.assertRaisesRegex(ValueError,'coverage binding'):self.configure()

    def test_global_failure_cannot_be_carried_as_slot_failure(self):
        self.nested_setup(failed=True);ref=self.policy['priorSlots'][1]['reference'];path=self.repository/ref['relativePath']
        driver=matrix.strict_json(path.read_bytes());driver.update(status='globally_stopped',globalErrorType='ValueError')
        self.policy['priorSlots'][1]['reference']=self.ref(path,io.encoded(driver))
        with self.assertRaisesRegex(ValueError,'terminal outcome'):self.configure()

    def test_lineage_depth_rejects_bool_and_unbounded_value(self):
        for depth in [True,-1,92]:
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                self.instance.validate_policy(self.bound,self.policy_raw,depth)

if __name__=='__main__':unittest.main()
