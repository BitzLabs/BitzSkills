"""標準残量RPCの対象、出力範囲、隔離と停止を合成で検査する。"""
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_rate_limits as limits


def response():
    return SimpleNamespace(rateLimits={'limitId':'premium'},
        rateLimitsByLimitId={'codex':{'limitId':'codex','spendControlReached':False,'rateLimitReachedType':None,
            'credits':'discard', 'primary':{'usedPercent':5,'resetsAt':400,'windowDurationMins':300,'extra':'discard'},
            'secondary':{'usedPercent':2,'resetsAt':900,'windowDurationMins':10080}}},ordinaryUsageAllowed=True)


class MatrixRateLimitsTests(unittest.TestCase):
    def test_standard_rpc_uses_only_ordinary_bucket_and_projects_allowed_fields(self):
        config = MagicMock()
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.return_value = response()
        sdk = SimpleNamespace(CodexConfig=config,__version__='0.160.1')
        with (
            patch.dict(sys.modules,{'openai_codex':sdk,
                'openai_codex.client':SimpleNamespace(CodexClient=lambda options:client),
                'pydantic':SimpleNamespace(BaseModel=object,StrictBool=bool)}),
            patch.object(sys,'path',sys.path[:]),
        ):
            result=limits.sdk_read('/fixed/sdk','/fixed/bin/codex')
        client.initialize.assert_called_once_with()
        self.assertEqual(client.request.call_args.args,
            ('account/rateLimits/read',dict(excludeResetCreditDetails=True,supportsLunaReserve=False)))
        self.assertEqual(result,dict(limitId='codex',spendControlReached=False,rateLimitReachedType=None,
            primary=dict(usedPercent=5,resetsAt=400,windowDurationMins=300),
            secondary=dict(usedPercent=2,resetsAt=900,windowDurationMins=10080)))
        config.assert_called_once_with(launch_args_override=('/fixed/bin/codex','-c',
            'cli_auth_credentials_store="file"','app-server','--listen','stdio://'))

    def test_missing_or_disallowed_standard_bucket_fails_closed(self):
        data = response()
        data.rateLimitsByLimitId = None
        with self.assertRaisesRegex(ValueError,'ordinary codex limits unavailable'):
            limits.ordinary_snapshot(data)
        data = response()
        data.ordinaryUsageAllowed = False
        with self.assertRaisesRegex(ValueError,'ordinary codex limits unavailable'):
            limits.ordinary_snapshot(data)

    def test_worker_has_temporary_state_and_read_only_standard_auth(self):
        folder=ROOT/'.venv/test-temp'
        folder.mkdir(parents=True,exist_ok=True)
        child=MagicMock()
        child.__enter__.return_value=child
        child.returncode=0
        child.communicate.return_value=(b'{"limitId":"codex"}',None)
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            repo=Path(temporary)
            (repo/'.venv').mkdir()
            with patch.object(limits.subprocess,'Popen',return_value=child) as spawn:
                result=limits.read(repo,repo/'.venv/sdk','/fixed/runtime/bin/codex',
                                   '/fixed/auth.json',b'# fixed reader')
            self.assertEqual(result,{'limitId':'codex'})
            argv=spawn.call_args.args[0]
            index=argv.index('/fixed/auth.json')
            self.assertEqual(argv[index-1:index+2],['--ro-bind','/fixed/auth.json','/home/hide/.codex/auth.json'])
            self.assertEqual(argv[-7:],['--','/usr/bin/python3','-I','-B','-',str(repo/'.venv/sdk'),'/fixed/runtime/bin/codex'])
            self.assertEqual(spawn.call_args.kwargs['env']['CODEX_HOME'],'/home/hide/.codex')
            self.assertEqual(list((repo/'.venv').iterdir()),[])
        child.communicate.assert_called_once_with(b'# fixed reader',timeout=45)

    def test_timeout_terminates_only_worker_process_group(self):
        folder=ROOT/'.venv/test-temp'
        folder.mkdir(parents=True,exist_ok=True)
        child=MagicMock(pid=7654)
        child.__enter__.return_value=child
        child.communicate.side_effect=subprocess.TimeoutExpired('synthetic worker',45)
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            repo=Path(temporary)
            (repo/'.venv').mkdir()
            with (
                patch.object(limits.subprocess,'Popen',return_value=child),
                patch.object(limits.os,'killpg') as kill,
            ):
                with self.assertRaisesRegex(RuntimeError,'rate metadata read failed'):
                    limits.read(repo,repo/'.venv/sdk','/fixed/runtime/bin/codex','/fixed/auth.json',b'# worker')
        kill.assert_called_once_with(7654,limits.signal.SIGKILL)
