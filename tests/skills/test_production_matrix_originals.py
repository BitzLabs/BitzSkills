"""provider原読取りの完全集合・link拒否・opaque非読取りを合成で確認。モデル0。"""
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_originals as originals
import test_production_matrix_provider_evidence as fixture


class MatrixOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.MatrixProviderEvidenceTests(methodName='runTest')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.base=self.fixture.base.capture.base
        for name,raw in self.fixture.originals.items():
            path=self.base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.persist()

    def persist(self):(self.base/'receipt.json').write_bytes(originals.io.encoded(self.fixture.receipt))

    def load(self):
        f=self.fixture
        return originals.load_provider_capture(f.bound,1,source_repository=f.source_repository,
            artifact_repository=f.artifact_repository,manifest_raw=f.base.manifest,schema_raw=f.base.schema,context_raw=f.base.profile)

    def reads(self,expected_failure=None):
        observed=[];regular=originals.io.read_regular
        def read(path):observed.append(str(path.relative_to(self.base)));return regular(path)
        with patch.object(originals.io,'read_regular',side_effect=read):
            if expected_failure:
                with self.assertRaises(expected_failure):self.load()
            else:self.load()
        return observed

    def test_complete_provider_inventory_is_loaded_without_receipt_rewrite_or_launch(self):
        context=self.load();self.assertEqual(context,self.fixture.bind())
        expected=originals.provider.verify_bytes(context,source_repository=self.fixture.source_repository,
            artifact_repository=self.fixture.artifact_repository)
        for key in ['sourceRuntimeOnDiskVerified','invocationArgvVerified','launchEnvironmentVerified',
            'eligibleForMeasurement','ledgerFinalized']:self.assertFalse(expected[key])
        with patch.object(originals.provider.preflight.capture.subprocess,'Popen',side_effect=AssertionError('process')):
            self.assertEqual(self.load(),context)

    def test_opaque_contents_are_not_enumerated_or_opened(self):
        for name in originals.provider.evidence.inventory.OPAQUE_DIRECTORIES:
            path=self.base/name;path.mkdir(exist_ok=True);(path/'synthetic-unread-sentinel').write_bytes(b'public sentinel')
        observed=self.reads()
        self.assertEqual(set(observed),{'receipt.json',*self.fixture.originals})
        self.assertEqual(len(observed),len(self.fixture.originals)+1)

    def test_unknown_declared_private_traversal_or_receipt_version_rejected_before_artifact_reads(self):
        before=copy.deepcopy(self.fixture.receipt)
        for name in ['codex-home/auth.json','../outside','unknown.json','rollout-traces/auth/manifest.json']:
            self.fixture.receipt=copy.deepcopy(before);self.fixture.receipt['artifactSha256'][name]='f'*64;self.persist()
            with self.subTest(name=name):self.assertEqual(self.reads(ValueError),['receipt.json'])
        self.fixture.receipt=before;self.fixture.receipt['version']=originals.provider.evidence.VERSION;self.persist()
        self.assertEqual(self.reads(ValueError),['receipt.json'])

    def test_unknown_actual_file_rejected_before_any_artifact_content(self):
        (self.base/'unknown.json').write_bytes(b'public unknown sentinel')
        self.assertEqual(self.reads(ValueError),['receipt.json'])

    def test_missing_required_addition_rejected_before_content_reads(self):
        name='resource-guards.json';(self.base/name).unlink()
        self.assertEqual(self.reads(ValueError),['receipt.json'])

    def test_artifact_symlink_and_hardlink_rejected_before_other_artifact_reads(self):
        path=self.base/'namespace.stderr';raw=path.read_bytes();path.unlink()
        target=self.fixture.artifact_repository/'synthetic-link-target';target.write_bytes(raw);path.symlink_to(target)
        self.assertEqual(self.reads(ValueError),['receipt.json'])
        path.unlink();path.write_bytes(raw);os.link(path,self.fixture.artifact_repository/'synthetic-hardlink')
        self.assertEqual(self.reads(ValueError),['receipt.json'])

    def test_receipt_symlink_and_hardlink_rejects_without_opening_target(self):
        path=self.base/'receipt.json';raw=path.read_bytes();path.unlink()
        target=self.fixture.artifact_repository/'synthetic-receipt-target';target.write_bytes(raw);path.symlink_to(target)
        with self.assertRaises(OSError):self.load()
        path.unlink();path.write_bytes(raw);os.link(path,self.fixture.artifact_repository/'synthetic-receipt-hardlink')
        with self.assertRaises(ValueError):self.load()

    def test_ordinal_boolean_root_and_receipt_slot_relabel_rejected(self):
        f=self.fixture
        for ordinal in [True,0,93]:
            with self.subTest(ordinal=ordinal),self.assertRaises(ValueError):
                originals.load_provider_capture(f.bound,ordinal,source_repository=f.source_repository,
                    artifact_repository=f.artifact_repository,manifest_raw=f.base.manifest,schema_raw=f.base.schema,context_raw=f.base.profile)
        f.receipt['slot']=f.bound.slot(2);self.persist()
        self.assertEqual(self.reads(ValueError),['receipt.json'])

    def test_changed_content_without_receipt_rehash_and_rehashed_false_config_rejected(self):
        path=self.base/'config.json';raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(ValueError,'hash drift'):self.load()
        changed=originals.trace.strict_json(raw);changed['unknown-provider-setting']=True;raw=originals.io.encoded(changed)
        path.write_bytes(raw);self.fixture.receipt['artifactSha256']['config.json']=originals.io.sha(raw);self.persist()
        with self.assertRaisesRegex(ValueError,'config drift'):self.load()


if __name__=='__main__':unittest.main()
