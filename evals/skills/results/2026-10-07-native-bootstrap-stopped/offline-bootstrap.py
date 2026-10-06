"""新namespace全体をnetwork namespace遮断下で起動する。paid modelは呼ばない。"""
import json
import os
from pathlib import Path
import sys

ROOT=Path('/home/hide/BitzLabs/BitzSkills/.venv/skills-integration-worktree')
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import native_actor_v02 as actor
os.umask(0o077)
BASE=ROOT/'.venv/native-bootstrap-full-03'
BASE.mkdir(mode=0o700)
private=BASE/'private';private.mkdir(mode=0o700)
actor.exclusive(private/'retention.json',b'offline-synthetic-retention')
(private/'native-authoring-01').mkdir(mode=0o700)
phase=private/'native-authoring-02/preparation';phase.mkdir(parents=True,mode=0o700)
(phase/'codex-home').mkdir(mode=0o700)
ledger=BASE/'ledger';ledger.mkdir(mode=0o700)
configs=actor.configurations(phase)
cli=['/home/hide/.nvm/versions/node/v26.5.0/bin/codex','exec','--json','--ephemeral','--ignore-user-config',
     '--ignore-rules','--sandbox','workspace-write','--cd',str(ROOT),'--model','gpt-6.1-sol','-']
for key,value in configs.items():cli+=['-c',key+'='+json.dumps(value)]
for name,value in [('prompt.txt',b'Offline bootstrap diagnostic. Do not run tools.\n'),
                   ('model-config.json',actor.encoded(configs)),('invocation.json',actor.encoded({'offline':True}))]:
    actor.exclusive(phase/name,value)
command=actor.namespace(phase,ledger,cli,private=private)
command.insert(1,'--unshare-net')
result=actor.invoke(command,(phase/'prompt.txt').read_bytes(),phase,12)
stderr=(phase/'stderr.log').read_bytes()
events=[]
for line in (phase/'trace.jsonl').read_bytes().splitlines():
    try:events.append(json.loads(line))
    except Exception:pass
result={**result,'scope':'offline-full-namespace-bootstrap','networkNamespaceIsolated':True,
        'bootstrapFailure':b'failed to initialize in-process app-server client' in stderr,
        'readOnlyFilesystem':b'Read-only file system' in stderr,
        'threadStarted':any(e.get('type')=='thread.started' for e in events),
        'eventCount':len(events),'certifiesModelCompletion':False,'certifiesPreparation':False}
actor.exclusive(BASE/'summary.json',actor.encoded(result))
print(json.dumps(result))
