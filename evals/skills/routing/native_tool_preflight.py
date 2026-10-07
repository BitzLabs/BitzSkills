"""モデル/turnを開始せず、通信を分離したcommand/execで39試験を実行する。"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import time


def execute(actor, parent: Path, ledger: Path, contract: dict) -> dict:
    phase=parent/'preflight';phase.mkdir(mode=0o700)
    (phase/'codex-home').mkdir(mode=0o700);(phase/'tmp').mkdir(mode=0o700)
    config=actor.configurations(phase)
    cli=[contract['codexPath'],'app-server','--stdio']
    for key,value in config.items():cli+=['-c',key+'='+json.dumps(value)]
    requests=[{'id':1,'method':'initialize','params':{'clientInfo':{'name':'native-local-preflight','version':'1.0'},
                        'capabilities':{'experimentalApi':True}}},
              {'method':'initialized'},
              {'id':2,'method':'command/exec','params':{
                'command':['/home/hide/.cache/uv/environments-v2/run-conformance-3a9acb64608185bd/bin/python',
                           '-B','-W','ignore::DeprecationWarning','-c',
                           "import unittest; suite=unittest.TestSuite(); [suite.addTests(unittest.defaultTestLoader.discover('tests/skills',pattern=p)) for p in ['test_native_actor.py','test_native_actor_v03.py','test_single_replacement.py']]; result=unittest.TextTestRunner().run(suite); raise SystemExit(not result.wasSuccessful())"],
                'cwd':str(actor.ROOT),'timeoutMs':30000,'outputBytesCap':32768,
                'env':{'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(phase/'tmp'),
                       'PYTHONPATH':str(actor.ROOT/'plugins/bitz-core/src')+':/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i'},
                'sandboxPolicy':{'type':'workspaceWrite','writableRoots':[str(actor.ROOT),str(actor.PRIVATE)],
                                 'networkAccess':False}}}]
    for name,raw in [('prompt.txt',b'No model/thread/turn requests.'),('model-config.json',actor.encoded(config)),
                     ('invocation.json',actor.encoded({'requests':requests,'networkNamespaceIsolated':True}))]:
        actor.exclusive(phase/name,raw)
    argv=actor.namespace(phase,ledger,cli);argv.insert(1,'--unshare-net')
    streams=[];process=None;response=None;initialized=False;error_type=None
    try:
        for name in ['trace.jsonl','stderr.log']:
            streams.append(os.fdopen(os.open(phase/name,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600),'wb'))
        process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=streams[0],stderr=streams[1],start_new_session=True)
        process.stdin.write((json.dumps(requests[0])+'\n').encode());process.stdin.flush()
        started=time.monotonic()
        while time.monotonic()-started<40:
            events=[]
            for line in (phase/'trace.jsonl').read_bytes().splitlines():
                try:events.append(json.loads(line))
                except ValueError:pass
            if not initialized and any(e.get('id')==1 and 'result' in e for e in events):
                process.stdin.write(('\n'.join(json.dumps(r) for r in requests[1:])+'\n').encode())
                process.stdin.flush();initialized=True
            response=next((e for e in events if e.get('id')==2),None)
            if response is not None or process.poll() is not None:break
            time.sleep(0.05)
    except (OSError,KeyboardInterrupt) as error:
        error_type=type(error).__name__
    finally:
        if process is not None:
            if process.poll() is None:actor.stop_process(process)
            if process.stdin is not None:process.stdin.close()
        for stream in streams:
            stream.flush();os.fsync(stream.fileno());stream.close()
    command=response.get('result',{}) if response else {}
    ok=(error_type is None and command.get('exitCode')==0 and
        'Ran 39 tests' in command.get('stderr','') and command.get('stderr','').rstrip().endswith('OK'))
    result={'status':'local_preflight_passed' if ok else 'local_preflight_stopped',
            'networkNamespaceIsolated':True,'modelCalls':0,'threadOrTurnRequests':0,
            'initialized':initialized,'commandResponseReceived':response is not None,
            'commandExitCode':command.get('exitCode'),'serverExitCode':process.returncode if process else None,
            'intentionalServerShutdown':process is not None and response is not None,
            'errorType':error_type,'actualTestCount':39 if ok else None,
            'captureSha256':{n:actor.collection.digest((phase/n).read_bytes()) for n in ['trace.jsonl','stderr.log'] if (phase/n).is_file()},
            'certifiesIndependentPreparation':False,'automaticPaidRetry':False}
    actor.exclusive(phase/'receipt.json',actor.encoded(result))
    return result
