"""評価失敗の読取り専用の再検査。合成した原記録だけを使い、モデル0。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_failure_diagnosis as diagnosis


class FailureDiagnosisTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)/'attempt-0058'
        (self.base/'work').mkdir(parents=True)
        (self.base/'rpc-out.jsonl').write_bytes(b'{"private":"case text"}\n')
        (self.base/'capture-stop.json').write_bytes(json.dumps(dict(reason='primary-capture-rejected',
            errorType='ValueError')).encode())
        (self.base/'receipt.json').write_bytes(json.dumps(dict(namespaceExitCode=0, timedOut=False,
            primaryModelTrajectories=1, cwd='/private/path', artifactSha256={'x': 'y'})).encode())
        (self.base/'resource-guards.json').write_bytes(json.dumps(dict(before={'a': 1}, after={'a': 1})).encode())

    def test_writes_and_non_git_processes_are_blocked_inside_the_guard(self):
        target = self.base/'new.json'
        attempts = [lambda: open(target, 'w'), lambda: target.write_bytes(b'x'),
            lambda: os.open(target, os.O_WRONLY | os.O_CREAT), lambda: os.mkdir(self.base/'d'),
            lambda: os.unlink(self.base/'rpc-out.jsonl'), lambda: os.rename(self.base/'rpc-out.jsonl', target),
            lambda: os.chmod(self.base/'rpc-out.jsonl', 0o600), lambda: subprocess.run(['touch', str(target)]),
            lambda: subprocess.run(['git', '-C', str(ROOT), 'commit', '--allow-empty', '-m', 'x'])]
        with diagnosis.read_only():
            for index, attempt in enumerate(attempts):
                with self.subTest(index=index), self.assertRaises(diagnosis.ReadOnlyViolation):
                    attempt()
            self.assertEqual(b'{"private":"case text"}\n', (self.base/'rpc-out.jsonl').read_bytes())
            self.assertTrue(subprocess.run(['git', '--no-optional-locks', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                capture_output=True).stdout)
        self.assertFalse(target.exists())
        target.write_bytes(b'after the guard')
        self.assertEqual(b'after the guard', target.read_bytes())

    def test_only_static_require_messages_are_reported(self):
        def fail(message):
            try:
                diagnosis.require(False, message)
            except ValueError as error:
                return diagnosis.summarize(error, sources="require(x, 'native action not allowed')")
        shown = fail('native action not allowed')
        self.assertEqual(('ValueError', 'native action not allowed', False),
            (shown['errorType'], shown['message'], shown['messageWithheld']))
        self.assertTrue(any(frame['file'] == 'production_trace.py' for frame in shown['frames']))
        withheld = fail('private case SE-030 prompt text')
        self.assertEqual((None, True), (withheld['message'], withheld['messageWithheld']))
        try:
            {}['private-key']
        except KeyError as error:
            other = diagnosis.summarize(error, sources='')
        self.assertEqual(('KeyError', None, False), (other['errorType'], other['message'], other['messageWithheld']))
        try:
            raise ValueError('native action not allowed')
        except ValueError as error:
            direct = diagnosis.summarize(error, sources="'native action not allowed'")
        self.assertIsNone(direct['message'])

    def test_recheck_reports_the_rejecting_check_and_keeps_originals(self):
        def check():
            (self.base/'rpc-out.jsonl').read_bytes()
            diagnosis.require(False, 'diagnosis original attempt directory')
        result = diagnosis.recheck(self.base, check)
        self.assertEqual(('rejected', True), (result['status'], result['originalsUnchanged']))
        self.assertEqual('diagnosis original attempt directory', result['failure']['message'])
        self.assertEqual('reverified', diagnosis.recheck(self.base, lambda: None)['status'])
        attempted = diagnosis.recheck(self.base, lambda: (self.base/'x.json').write_bytes(b'1'))
        self.assertEqual('ReadOnlyViolation', attempted['failure']['errorType'])
        self.assertFalse((self.base/'x.json').exists())

    def test_recheck_detects_a_change_that_bypassed_the_guard(self):
        # 遮断の前に取っておいた元の関数で書き、プロセス内の遮断を回避した変更を作る。
        raw_open = os.open
        def check():
            fd = raw_open(self.base/'rpc-out.jsonl', os.O_WRONLY | os.O_APPEND)
            os.write(fd, b'changed')
            os.close(fd)
        with self.assertRaisesRegex(ValueError, 'diagnosis changed the original attempt'):
            diagnosis.recheck(self.base, check)

    def test_stop_summary_reads_only_content_free_fields(self):
        summary = diagnosis.stop_summary(self.base)
        self.assertEqual(dict(reason='primary-capture-rejected', errorType='ValueError'), summary['capture-stop.json'])
        self.assertEqual(dict(namespaceExitCode=0, timedOut=False, primaryModelTrajectories=1), summary['receipt.json'])
        self.assertTrue(summary['resourcesUnchangedDuringLaunch'])
        self.assertNotIn('private', json.dumps(summary))

    def test_ordinal_ranges(self):
        self.assertEqual([58], list(diagnosis.ordinals('58')))
        self.assertEqual(list(range(58, 93)), list(diagnosis.ordinals('58-92')))
        for text in ['0', '93', '60-58', 'a', '58-']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                diagnosis.ordinals(text)


if __name__ == '__main__':
    unittest.main()
