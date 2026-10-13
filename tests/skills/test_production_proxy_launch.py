"""CLI起動設定を行列contractへ混入せずに原中継する。外部モデル0。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_sdk_probe as sdk


class ProxyLaunchTests(unittest.TestCase):
    def test_closed_launch_settings_reject_before_native_process(self):
        temp=tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp');self.addCleanup(temp.cleanup);base=Path(temp.name)
        (base/'config.json').write_text('{}')
        good=dict(codexPath='/fixed/codex',diagnosticTracing=sdk.DIAGNOSTIC_TRACING)
        values=[{},dict(good,model='gpt-6.1-sol'),dict(good,budget=92),dict(good,codexPath='../cli'),
                dict(good,codexPath='/fixed/../cli'),dict(good,diagnosticTracing={})]
        raws=[json.dumps(v).encode() for v in values]+[b'{"codexPath":"/one","codexPath":"/two","diagnosticTracing":{}}']
        for raw in raws:
            with self.subTest(raw=raw),patch.object(sdk.subprocess,'Popen') as start:
                with self.assertRaises(ValueError):sdk.proxy(base,launch_contract_raw=raw)
                start.assert_not_called()

    def test_explicit_launch_contract_preserves_matrix_bytes_and_raw_streams(self):
        temp=tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp');self.addCleanup(temp.cleanup);base=Path(temp.name)
        fake=base/'fake-codex';fake.write_text('#!/usr/bin/python3\nimport sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(line);sys.stdout.buffer.flush()\n');fake.chmod(0o700)
        matrix_raw=b'{"version":"public-production-matrix-ledger-0.1.1","model":"gpt-6.1-sol","budget":{"primary":92}}'
        (base/'contract.json').write_bytes(matrix_raw);(base/'config.json').write_text('{}')
        launch_raw=json.dumps(dict(codexPath=str(fake),diagnosticTracing=sdk.DIAGNOSTIC_TRACING)).encode();(base/'launch-settings.json').write_bytes(launch_raw)
        code=('from pathlib import Path;import sys;sys.path.insert(0,"evals/skills/routing");import production_sdk_probe as sdk;'
              'b=Path(sys.argv[1]);sdk.proxy(b,launch_contract_raw=(b/"launch-settings.json").read_bytes())')
        sent=b'{"method":"initialize","id":1,"params":{}}\n'
        result=subprocess.run([sys.executable,'-B','-c',code,str(base)],cwd=ROOT,input=sent,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(result.stdout,sent)
        self.assertEqual((base/'rpc-in.jsonl').read_bytes(),sent);self.assertEqual((base/'rpc-out.jsonl').read_bytes(),sent)
        self.assertEqual((base/'contract.json').read_bytes(),matrix_raw)
        self.assertFalse(json.loads((base/'runtime-result.json').read_bytes())['forcedShutdown'])
        self.assertTrue((base/'trace-safe.jsonl').is_file())


if __name__=='__main__':unittest.main()
