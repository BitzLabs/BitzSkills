"""固定runtimeの差替え・欠測・未知名を起動前に止める。実CLI/認証を使わない。"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_runtime as runtime


def fixture(root, contract):
    root.mkdir(parents=True)
    files={}
    for name in sorted(runtime.REQUIRED):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        raw=('public synthetic '+name).encode();path.write_bytes(raw);files[name]=runtime.ledger.sha(raw)
    (root/'bin/codex').symlink_to(runtime.LINK)
    raw=runtime.ledger.encoded(dict(package='@openai/codex',version='0.160.1',files=files,treeSha256='1'*64))
    contract.update(codexPath=str(root/'bin/codex'),runtimeManifestSha256=runtime.ledger.sha(raw))
    return raw


class CanaryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'runtime';self.contract={};self.raw=fixture(self.root,self.contract)
        patched=patch.object(runtime,'ROOT',self.root);patched.start();self.addCleanup(patched.stop)

    def test_fixed_packaged_symlink_and_known_hardlink_are_bound(self):
        node=self.root/'bin/node';os.link(node,Path(self.temp.name)/'public-hardlink')
        self.assertEqual(runtime.verify(self.raw,self.contract)['status'],'fixed_runtime_bytes_match')
        self.assertEqual(node.stat().st_nlink,2)

    def test_changed_bytes_missing_file_symlink_or_wrong_entry_stops(self):
        node=self.root/'bin/node';original=node.read_bytes()
        for fault in ['bytes','missing','symlink','entry','link']:
            if fault=='bytes':node.write_bytes(b'changed')
            elif fault=='missing':node.unlink()
            elif fault=='symlink':node.unlink();node.symlink_to(self.root/'bin/codex')
            elif fault=='entry':self.contract['codexPath']='/outside/cli'
            else:(self.root/'bin/codex').unlink();(self.root/'bin/codex').symlink_to('/outside/cli')
            with self.subTest(fault=fault),self.assertRaises((ValueError,OSError)):runtime.verify(self.raw,self.contract)
            if fault in {'missing','symlink'}:
                if node.is_symlink():node.unlink()
                node.write_bytes(original)
            elif fault=='bytes':node.write_bytes(original)
            elif fault=='entry':self.contract['codexPath']=str(self.root/'bin/codex')
            else:(self.root/'bin/codex').unlink();(self.root/'bin/codex').symlink_to(runtime.LINK)

    def test_unknown_protected_file_never_opened(self):
        (self.root/'.env').write_bytes(b'SYNTHETIC_DO_NOT_READ')
        with patch.object(runtime,'file_hash',side_effect=AssertionError('read before inventory validation')) as read:
            with self.assertRaisesRegex(ValueError,'unknown runtime'):runtime.verify(self.raw,self.contract)
            read.assert_not_called()

    def test_manifest_escape_and_hash_drift_reject_before_reads(self):
        for name in ['../outside','bin/../auth.json',runtime.PACKAGE+'.env']:
            value=json.loads(self.raw);value['files'][name]='2'*64;raw=runtime.ledger.encoded(value)
            contract=dict(self.contract,runtimeManifestSha256=runtime.ledger.sha(raw))
            with self.subTest(name=name),patch.object(runtime,'file_hash',side_effect=AssertionError('unsafe read')),self.assertRaises(ValueError):runtime.verify(raw,contract)
        with self.assertRaisesRegex(ValueError,'hash'):runtime.verify(self.raw+b' ',self.contract)

if __name__=='__main__':unittest.main()
