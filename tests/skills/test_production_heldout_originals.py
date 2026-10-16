"""合成private rootのみで原inventoryとowner-only読取り、opaque非読取りを検査。"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_originals as originals
import test_production_heldout_evidence as fixture


class HeldoutOriginalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutEvidenceTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bound=self.fixture.bound;self.base=self.bound.stage_root(1,'primary')
        self.base.mkdir(parents=True,mode=0o700)
        for path in [self.base,*self.base.parents]:
            if path.is_relative_to(originals.x.inputs.PRIVATE_CASES.parent):path.chmod(0o700)
        for name,raw in self.fixture.originals.items():
            path=self.base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o600)
        for name in originals.evidence.inventory.OPAQUE_DIRECTORIES:(self.base/name).mkdir(mode=0o700)
        auth=self.base/'codex-home/auth.json';auth.write_bytes(b'SYNTHETIC_AUTH_SENTINEL_DO_NOT_READ');auth.chmod(0o600)
        for path in self.base.rglob('*'):
            if path.is_dir():path.chmod(0o700)
        receipt=self.base/'receipt.json';receipt.write_bytes(originals.io.encoded(self.fixture.receipt));receipt.chmod(0o600)
        d=originals.x.deployment_for_execution(self.bound.execution_raw,self.bound.deployment_raw)
        manifest=self.fixture.capture.repository/d['snapshotRelativePath']/'manifest.json'
        manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_bytes(self.fixture.manifest)

    def load(self):return originals.load(self.bound,1,source_repository=self.fixture.capture.repository)

    def test_complete_known_private_originals_load_without_reading_opaque_auth_sentinel(self):
        opening=os.open
        def monitor(name,*args,**kwargs):
            self.assertNotEqual(str(name),'auth.json')
            self.assertNotIn('SYNTHETIC_AUTH',str(name))
            return opening(name,*args,**kwargs)
        with patch.object(os,'open',side_effect=monitor):result=self.load()
        self.assertEqual(result.ordinal,1)
        self.assertNotIn('SYNTHETIC_AUTH',repr(result))

    def test_unknown_secret_member_rejected_before_its_contents_are_read(self):
        (self.base/'.env').write_bytes(b'SYNTHETIC_SECRET_DO_NOT_READ')
        with self.assertRaises(ValueError):self.load()

    def test_group_readable_hardlinked_and_symlinked_originals_are_rejected(self):
        path=self.base/'rpc-in.jsonl';path.chmod(0o640)
        with self.assertRaises(ValueError):self.load()
        path.chmod(0o600)
        os.link(path,self.base.parent/'linked-original')
        with self.assertRaises(ValueError):self.load()
        alias=self.base.parent/'alias';alias.symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(OSError):originals.read_original(alias,'receipt.json')

    def test_directory_permission_and_finite_file_size_rejected_before_read(self):
        self.base.chmod(0o755)
        with self.assertRaises(ValueError):originals.read_original(self.base,'receipt.json')
        self.base.chmod(0o700)
        with patch.object(originals,'MAX_FILE_BYTES',8),self.assertRaises(ValueError):
            originals.read_original(self.base,'receipt.json')

    def test_protected_relative_paths_are_rejected_before_opening_root(self):
        for name in ['../receipt.json','codex-home/auth.json','/outside','.env']:
            with self.subTest(name=name),patch.object(originals,'_open_root',side_effect=AssertionError('early root open')):
                with self.assertRaises(ValueError):originals.read_original(self.base,name)
