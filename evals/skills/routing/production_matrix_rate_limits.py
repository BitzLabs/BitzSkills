"""固定SDKから標準codexの利用枠メタデータだけを読む。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory


def ordinary_snapshot(result):
    by_id = result.rateLimitsByLimitId or {}
    bucket = by_id.get('codex', result.rateLimits)
    if (not isinstance(bucket, dict) or bucket.get('limitId') != 'codex'
            or result.ordinaryUsageAllowed is False):
        raise ValueError('ordinary codex limits unavailable')
    snapshot = {key: bucket[key] for key in ('limitId', 'rateLimitReachedType', 'spendControlReached')
                if key in bucket}
    for name in ('primary', 'secondary'):
        window = bucket.get(name)
        if not isinstance(window, dict):
            raise ValueError('ordinary codex window unavailable')
        snapshot[name] = {key: window[key] for key in ('usedPercent', 'windowDurationMins', 'resetsAt')
                          if key in window}
    return snapshot


def sdk_read(sdk_path, cli_path):
    """隔離した親環境から開始したSDK worker内だけで使う。"""
    sys.path.insert(0, sdk_path)
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    from pydantic import BaseModel, StrictBool

    class Response(BaseModel):
        rateLimits: dict
        rateLimitsByLimitId: dict | None = None
        ordinaryUsageAllowed: StrictBool | None = None

    if __version__ != '0.160.1':
        raise ValueError('fixed rate reader SDK version drift')
    config = CodexConfig(launch_args_override=(
        cli_path, '-c', 'cli_auth_credentials_store="file"', 'app-server', '--listen', 'stdio://'))
    with CodexClient(config) as client:
        client.initialize()
        result = client.request('account/rateLimits/read',
            dict(excludeResetCreditDetails=True, supportsLunaReserve=False), response_model=Response)
    return ordinary_snapshot(result)


def read(repository, sdk_path, cli_path, auth_path, worker_raw):
    """照合済みworkerを一時CODEX_HOMEで実行し、標準認証は読取り専用で委譲する。"""
    cli_path = Path(cli_path)
    env = dict(PATH=str(cli_path.parent)+':/usr/bin:/bin', LANG='C.UTF-8',
               HOME='/home/hide', CODEX_HOME='/home/hide/.codex', TMPDIR='/tmp')
    try:
        with TemporaryDirectory(prefix='matrix-rate-',dir=repository/'.venv') as temporary:
            base = Path(temporary)
            home = base/'codex-home'
            work = base/'work'
            home.mkdir(mode=0o700)
            work.mkdir(mode=0o700)
            argv = ['bwrap','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent',
                '--ro-bind','/','/','--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run',
                '--proc','/proc','--dev','/dev',
                '--ro-bind',str(sdk_path),str(sdk_path),
                '--ro-bind',str(cli_path.parents[1]),str(cli_path.parents[1]),
                '--bind',str(home),env['CODEX_HOME'],
                '--ro-bind',str(auth_path),env['CODEX_HOME']+'/auth.json',
                '--bind',str(work),str(work),'--chdir',str(work),'--',
                '/usr/bin/python3','-I','-B','-',str(sdk_path),str(cli_path)]
            with subprocess.Popen(argv,cwd=work,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,start_new_session=True) as process:
                try:
                    stdout,_ = process.communicate(worker_raw,timeout=45)
                except BaseException:
                    try:
                        os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    raise
            if process.returncode != 0 or len(stdout) > 4096:
                raise ValueError('invalid rate reader output')
            return json.loads(stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise RuntimeError('ordinary codex rate metadata read failed') from None


if __name__ == '__main__':
    try:
        print(json.dumps(sdk_read(*sys.argv[1:]), allow_nan=False))
    except Exception:
        raise SystemExit(1) from None
