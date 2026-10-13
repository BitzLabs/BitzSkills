"""provider構成原の再hash差替えとSDK/rolloutの束縛を合成で検査。モデル0。"""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_provider_evidence as provider
import test_production_matrix_evidence as fixture


class MatrixProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        base=fixture.MatrixEvidenceTests(methodName='runTest');base.setUp();self.addCleanup(base.doCleanups);self.base=base
        self.artifact_repository=base.capture.repository;self.source_repository=self.artifact_repository/'source-tree'
        self.legacy_context=base.bind()
        old_manifest=provider.trace.strict_json(base.manifest);old_source=old_manifest['sourceCommit'];old_digest=provider.io.sha(base.manifest)
        old_manifest['sourceCommit']=base.bound.contract['sourceCommit'];base.manifest=provider.io.encoded(old_manifest)
        mapping={old_source:old_manifest['sourceCommit'],old_digest:provider.io.sha(base.manifest)}
        def convert(value):
            if isinstance(value,dict):return {k:convert(v) for k,v in value.items()}
            if isinstance(value,list):return [convert(v) for v in value]
            if isinstance(value,str):
                if value in mapping:return mapping[value]
                try:parsed=provider.trace.strict_json(value.encode())
                except ValueError:return value
                if isinstance(parsed,(dict,list)):
                    converted=convert(parsed)
                    return provider.io.encoded(converted).decode() if converted!=parsed else value
            return value
        for name,raw in list(base.originals.items()):
            if not raw:continue
            try:
                if name.endswith('.json'):
                    value=provider.trace.strict_json(raw);converted=convert(value)
                    base.originals[name]=provider.io.encoded(converted) if converted!=value else raw
                elif name.endswith('.jsonl') or name in {'runtime-stderr.bin'}:
                    values=provider.evidence.primary.json_lines(raw);converted=[convert(v) for v in values]
                    base.originals[name]=b''.join(provider.io.encoded(v)+b'\n' for v in converted) if converted!=values else raw
            except ValueError:pass
        sdk_files={'openai_codex/__init__.py':provider.io.sha(b'synthetic SDK'),
            'openai_codex-0.160.1.dist-info/METADATA':provider.io.sha(b'Version: 0.160.1')}
        digest=hashlib.sha256()
        for name,value in sorted(sdk_files.items(),key=lambda item:Path(item[0]).parts):digest.update(name.encode()+b'\0');digest.update(bytes.fromhex(value))
        self.sdk_raw=provider.io.encoded(dict(version='0.160.1',files=sdk_files,treeSha256=digest.hexdigest()))
        self.runtime_raw=base.capture.git_raws[provider.preflight.capture.fixed_runtime.MANIFEST]
        profile=provider.trace.strict_json(base.profile)
        canonical_profile=provider.trace.strict_json((ROOT/provider.preflight.inventory.CONTEXT).read_bytes())
        for name in ['calibrationSource','calibrationRequestSha256','calibrationReceiptSha256','systemSkillsDisabled',
                     'primaryModelTrajectories','paidModelCalls','certifiesProviderWireBodies','certifiesSkillGate']:
            profile[name]=canonical_profile[name]
        base.profile=provider.io.encoded(profile)
        runtime_spec=provider.trace.strict_json(self.runtime_raw);c=base.bound.contract
        c['pins']['contextProfile']=provider.io.sha(base.profile)
        c['pins'].update(snapshotManifest=provider.io.sha(base.manifest),sdk=digest.hexdigest(),
            runtimeManifest=provider.io.sha(self.runtime_raw),cli=runtime_spec['files'][provider.preflight.capture.fixed_runtime.VENDOR+'bin/codex'])
        self.bound=provider.evidence.matrix.bind(provider.io.encoded(c),base.bound.matrix.contract_raw,**base.raws)
        self.deployment=dict(version=provider.preflight.VERSION,sourceCommit=c['sourceCommit'],executionSha256=provider.io.sha(self.bound.execution_raw),
            codexPath=str(provider.preflight.capture.fixed_runtime.ROOT/'bin/codex'),codexVersion='codex-cli 0.160.1',
            sdkRelativePath='.venv/matrix-codex-python-sdk-deps-synthetic',sdkVersion='0.160.1',sdkTreeSha256=c['pins']['sdk'],sdkManifestSha256=provider.io.sha(self.sdk_raw),
            snapshotRelativePath='.venv/matrix-routing-preparation-synthetic/snapshot',manifestSha256=c['pins']['snapshotManifest'],snapshotResourceCount=len(old_manifest['resources']),
            runtimeManifestSha256=c['pins']['runtimeManifest'],contextProfileSha256=c['pins']['contextProfile'],calibrationManifestSha256=c['pins']['calibrationManifest'],certifiesSkillGate=False)
        self.originals=copy.deepcopy(base.originals);self.receipt=copy.deepcopy(base.receipt)
        self.receipt.update(version=provider.evidence.PROVIDER_VERSION,slot=self.bound.slot(1))
        self.originals.update({'contract.json':self.bound.execution_raw,'reservation.json':provider.io.encoded(self.bound.slot(1)),
            'deployment.json':provider.io.encoded(self.deployment),'sdk-manifest.json':self.sdk_raw,'runtime-manifest.json':self.runtime_raw,
            'launch-settings.json':provider.io.encoded(dict(codexPath=self.deployment['codexPath'],diagnosticTracing=provider.preflight.capture.sdk.DIAGNOSTIC_TRACING))})
        profile=provider.trace.strict_json(base.profile)
        proof=provider.resource_proof(self.bound,self.deployment,sdk_files,runtime_spec,old_manifest)
        proof.update(deploymentSha256=provider.io.sha(self.originals['deployment.json']),sourceSha256={name:'d'*64 for name in provider.preflight.SOURCE_FILES},
            contextDate=profile['date'],originalCalibration=dict(status='original_local_calibration_matches',calibrationManifestSha256=c['pins']['calibrationManifest'],
            sourceCommit=profile['calibrationSource'],requestSha256=profile['calibrationRequestSha256'],receiptSha256=profile['calibrationReceiptSha256'],
            paidModelCalls=0,primaryModelTrajectories=0,certifiesProviderWireBodies=False))
        self.originals['resource-guards.json']=provider.io.encoded(dict.fromkeys(['before','invoke','after'],proof))
        from types import SimpleNamespace
        self.originals['capture-environment.json']=provider.io.encoded(provider.environment_spec(SimpleNamespace(bound=self.bound,ordinal=1),self.source_repository,self.artifact_repository))
        self.originals['config.json']=provider.io.encoded(provider.preflight.capture.config_for(base.capture.base,self.deployment,repository=self.source_repository))
        self.rehash()

    def rehash(self):self.receipt['artifactSha256']={n:provider.io.sha(raw) for n,raw in self.originals.items()}

    def bind(self):
        return provider.evidence.bind_originals(self.bound,1,self.originals,provider.io.encoded(self.receipt),self.base.manifest,self.base.schema,self.base.profile)

    def verify(self):return provider.verify_bytes(self.bind(),source_repository=self.source_repository,artifact_repository=self.artifact_repository)

    def test_complete_provider_configuration_does_not_claim_live_environment_or_measurement(self):
        result=self.verify();self.assertTrue(result['providerConfigurationBytesMatched']);self.assertTrue(result['rawPayloadCorrelationVerified'])
        for name in ['sourceRuntimeOnDiskVerified','invocationArgvVerified','launchEnvironmentVerified','eligibleForMeasurement','independentReviewPerformed','ledgerFinalized']:
            self.assertFalse(result[name])

    def test_new_additional_originals_cannot_be_used_by_old_version_or_omitted(self):
        self.receipt['version']=provider.evidence.VERSION
        with self.assertRaises(ValueError):self.bind()
        self.receipt['version']=provider.evidence.PROVIDER_VERSION
        for name in provider.evidence.PROVIDER_ARTIFACTS:
            raw=self.originals.pop(name);self.rehash()
            with self.subTest(name=name),self.assertRaises(ValueError):self.bind()
            self.originals[name]=raw

    def test_legacy_original_context_is_diagnostic_only(self):
        with self.assertRaisesRegex(ValueError,'legacy'):provider.verify_bytes(self.legacy_context,source_repository=self.source_repository,artifact_repository=self.artifact_repository)

    def test_rehashed_deployment_launch_sdk_runtime_environment_and_full_config_drift_rejected(self):
        before=copy.deepcopy(self.originals)
        for name in provider.evidence.PROVIDER_ARTIFACTS|{'config.json'}:
            self.originals=copy.deepcopy(before);value=provider.trace.strict_json(self.originals[name]);value['unexpected']=True
            self.originals[name]=provider.io.encoded(value);self.rehash()
            with self.subTest(name=name),self.assertRaises(ValueError):self.verify()

    def test_resource_source_flags_runtime_date_or_three_timepoints_cannot_be_rewritten(self):
        before=copy.deepcopy(self.originals)
        for fault in ['source','after','flag','date','runtime','missing-source','calibration']:
            self.originals=copy.deepcopy(before);guards=provider.trace.strict_json(self.originals['resource-guards.json']);p=guards['before']
            if fault=='source':p['sourceCommit']='f'*40
            elif fault=='after':guards['after']['sdkFileCount']+=1
            elif fault=='flag':p['launchEnabled']=True
            elif fault=='date':p['contextDate']='2000-01-01'
            elif fault=='runtime':p['runtime']['codexPath']='/unknown/cli'
            elif fault=='missing-source':p['sourceSha256'].pop(next(iter(p['sourceSha256'])))
            else:p['originalCalibration']['paidModelCalls']=1
            if fault!='after':guards['invoke']=copy.deepcopy(p);guards['after']=copy.deepcopy(p)
            self.originals['resource-guards.json']=provider.io.encoded(guards);self.rehash()
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify()

    def test_root_role_swap_and_other_artifact_repository_rejected(self):
        with self.assertRaises(ValueError):provider.verify_bytes(self.bind(),source_repository=self.artifact_repository,artifact_repository=self.source_repository)
        with self.assertRaises(ValueError):provider.verify_bytes(self.bind(),source_repository=self.source_repository,artifact_repository=self.artifact_repository/'other')

    def test_complete_provider_bytes_entry_performs_no_reads_or_process_starts(self):
        context=self.bind();expected=self.verify()
        with (patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected disk read')),
              patch.object(provider.io,'read_regular',side_effect=AssertionError('unexpected original read')),
              patch.object(provider.preflight.capture.subprocess,'Popen',side_effect=AssertionError('unexpected process'))):
            self.assertEqual(provider.verify_bytes(context,source_repository=self.source_repository,artifact_repository=self.artifact_repository),expected)


if __name__=='__main__':unittest.main()
