"""行列局所校正の固定原・Git・profile・receiptを公開合成で照合。モデル0。"""
import copy
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_calibration as cal
import test_production_matrix_context_probe as probe_fixture

DISPATCH=cal.p.capture.calibration.verify


class MatrixCalibrationTests(unittest.TestCase):
    def setUp(self):
        f=probe_fixture.MatrixContextProbeTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        old=f.base;f.base=f.repository/'.venv/matrix-local-isolation-calibration-synthetic'
        f.originals={name:raw.replace(str(old).encode(),str(f.base).encode()) for name,raw in f.originals.items()}
        f.calibrate();self.fixture=f;self.repository=f.repository;self.base=f.base;self.base.mkdir()
        r=f.resource;r.originals[cal.p.inventory.CONTEXT]=f.context_raw
        r.originals[cal.p.inventory.SCHEMA]=f.schema
        for name in [cal.p.inventory.CONTEXT,cal.p.inventory.SCHEMA]:(r.repository/name).write_bytes(r.originals[name])
        self.patch(cal.p.guard,'git',side_effect=r.git)
        self.patch(cal.io,'common_ledger_path',return_value=self.repository/'.venv/synthetic-ledger')
        clock=self.patch(cal.p,'datetime');clock.now.return_value=datetime.fromisoformat(f.calibration_date)
        proof=cal.p.verify_calibration_resources(self.repository,f.bound,f.deployment_raw,r.sdk_manifest_raw)
        f.resource_proof_raw=cal.io.encoded(proof);f.originals['resource-preflight.json']=f.resource_proof_raw
        verified=f.verify_calibration()
        self.originals=dict(f.originals)
        self.receipt=dict(version=cal.probe.launch.CALIBRATION_VERSION,status='local_calibration_verified',
            sourceCommit=f.bound.contract['sourceCommit'],executionSha256=cal.io.sha(f.bound.execution_raw),
            sourceRepository=str(self.repository),artifactRepository=str(self.repository),
            resourceGuards=dict.fromkeys(['before','invoke','after'],proof),namespaceExitCode=0,timedOut=False,elapsedSeconds=1.25,
            artifactSha256={name:cal.io.sha(raw) for name,raw in self.originals.items()},originalReadErrors={},verification=verified,error=None,
            primaryModelTrajectories=0,paidModelCalls=0,realReservations=0,automaticRetries=0,launchEnabled=False,
            eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False,calibrationOnly=True,
            calibrationDate=f.calibration_date,referenceContextDate=proof['referenceContextDate'])
        self.profile=dict(cal.p.trace.strict_json(f.context_raw),date=f.calibration_date,calibrationSource=f.bound.contract['sourceCommit'])
        self.manifest=dict(version=cal.VERSION,sourceCommit=f.bound.contract['sourceCommit'],sourceRepository=str(self.repository),
            artifactRepository=str(self.repository),outputRelativeRoot=self.base.relative_to(self.repository).as_posix(),artifactSha256={})
        self.persist()

    def patch(self,target,name,**kwargs):
        p=patch.object(target,name,**kwargs);self.addCleanup(p.stop);return p.start()

    def persist(self):
        self.originals['receipt.json']=cal.io.encoded(self.receipt)
        for name,raw in self.originals.items():(self.base/name).write_bytes(raw)
        self.manifest['artifactSha256']={name:cal.io.sha(raw) for name,raw in self.originals.items()}
        self.manifest_raw=cal.io.encoded(self.manifest)
        self.profile.update(calibrationRequestSha256=cal.io.sha(self.originals['request-1.json']),
            calibrationReceiptSha256=cal.io.sha(self.originals['receipt.json']))
        self.contract=dict(calibrationManifestSha256=cal.io.sha(self.manifest_raw))

    def verify(self):return cal.verify(self.repository,self.manifest_raw,self.profile,self.contract)

    def test_complete_matrix_originals_dispatch_and_historical_source_are_verified(self):
        result=self.verify();self.assertEqual(result['status'],'original_local_calibration_matches')
        self.assertEqual(result['calibrationManifestSha256'],cal.io.sha(self.manifest_raw))
        self.assertEqual(len(cal.FILES),23);self.assertEqual(result['paidModelCalls'],0)
        self.assertFalse(result['certifiesProviderWireBodies'])
        self.assertEqual(DISPATCH(self.repository,self.manifest_raw,self.profile,self.contract),result)
        # producerの確定Gitへ照合。後続作業treeの変更を過去source原へ付替えない。
        path=self.repository/'evals/skills/routing/production_matrix_preflight.py';path.write_bytes(b'public later working code')
        self.assertEqual(self.verify(),result)

    def test_unknown_inventory_or_root_is_rejected_before_original_read(self):
        for fault in ['unknown','root','source','absolute']:
            changed=copy.deepcopy(self.manifest)
            if fault=='unknown':changed['artifactSha256']['codex-home/auth.json']='d'*64
            elif fault=='root':changed['outputRelativeRoot']='.venv/../outside'
            elif fault=='source':changed['sourceRepository']='/outside'
            else:changed['outputRelativeRoot']='/outside'
            raw=cal.io.encoded(changed)
            with self.subTest(fault=fault),patch.object(cal.io,'read_regular',side_effect=AssertionError('early original read')),self.assertRaises(ValueError):
                cal.verify(self.repository,raw,self.profile,dict(calibrationManifestSha256=cal.io.sha(raw)))

    def test_original_bytes_and_links_are_rejected_without_following_target(self):
        path=self.base/'request-1.json';raw=path.read_bytes();path.write_bytes(b'changed public original')
        with self.assertRaisesRegex(ValueError,'bytes drift'):self.verify()
        path.unlink();path.symlink_to(self.base/'missing-public-target')
        with self.assertRaises((ValueError,OSError)):self.verify()
        path.unlink();path.write_bytes(raw);self.verify()

    def test_rehashed_receipt_failure_unknown_field_boolean_and_guard_drift_are_rejected(self):
        baseline=copy.deepcopy(self.receipt)
        for key,value in [('status','local_calibration_stopped'),('namespaceExitCode',True),('elapsedSeconds',66),
            ('error',{'message':'failure'}),('paidModelCalls',1),('launchEnabled',True),('unknown',False),('resourceGuards',{})]:
            self.receipt=dict(copy.deepcopy(baseline),**{key:value});self.persist()
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()
        self.receipt=baseline;self.persist();self.verify()

    def test_rehashed_resource_proof_and_profile_cannot_change_fixed_source_or_sdk_context(self):
        proof=cal.p.trace.strict_json(self.originals['resource-preflight.json'])
        changed=copy.deepcopy(proof);changed['sourceSha256'][next(iter(changed['sourceSha256']))]='d'*64
        self.originals['resource-preflight.json']=cal.io.encoded(changed);self.persist()
        with self.assertRaisesRegex(ValueError,'historical resource proof'):self.verify()
        self.originals['resource-preflight.json']=cal.io.encoded(proof);self.persist()
        original=copy.deepcopy(self.profile)
        for key,value in [('date','2099-01-01'),('toolsValueSha256','e'*64),('unknown',True)]:
            self.profile=dict(original,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()

    def test_live_sdk_and_complete_snapshot_still_must_match_producer_git(self):
        path=self.fixture.resource.sdk/'openai_codex/__init__.py';original=path.read_bytes();path.write_bytes(b'changed public sdk')
        with self.assertRaisesRegex(ValueError,'SDK bytes drift'):self.verify()
        path.write_bytes(original)
        self.fixture.resource.originals['plugins/bitz-quality/public-missing.md']=b'public missing resource'
        with self.assertRaisesRegex(ValueError,'complete Git snapshot'):self.verify()


    def test_historical_instruction_mapping_is_bound_to_producer_and_rejects_executable_nodes(self):
        def producer(expression):
            fields={**cal.p.INPUT_PATHS,'instructions':None}
            pairs=[key+'='+ (expression if key=='instructions' else repr(value)) for key,value in fields.items()]
            return ('INPUT_PATHS=dict('+','.join(pairs)+')').encode()
        legacy=producer('inventory.INSTRUCTIONS')
        def historical_git(*args):
            return legacy if args[-1].endswith('production_matrix_preflight.py') else ('INSTRUCTIONS='+repr(cal.p.inventory.INSTRUCTIONS)).encode()
        with patch.object(cal.p.guard,'git',side_effect=historical_git):
            paths=cal.source_input_paths(self.repository,'f'*40)
            self.assertEqual(paths['instructions'],cal.p.inventory.INSTRUCTIONS)
            self.assertNotEqual(paths['instructions'],cal.p.INPUT_PATHS['instructions'])
        for expression in ['load_private()',repr('../private'),repr('evals/skills/cases/heldout.json')]:
            with self.subTest(expression=expression),patch.object(cal.p.guard,'git',return_value=producer(expression)),self.assertRaises(ValueError):
                cal.source_input_paths(self.repository,'f'*40)

if __name__=='__main__':unittest.main()
