"""一次と同じ公開contextを隔離局所SDKから取得する。外部モデル起動0。"""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

import production_canary_capture as capture
import production_cli_probe as cli
import production_ledger as ledger
import production_sdk_probe as sdk
import production_trace as trace
import source_guard as guard

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = '.venv/primary-context-calibration-05'
SOURCES = ['evals/skills/routing/production_canary_context_probe.py']
CODE = [*capture.CODE, 'production_canary_context_probe.py']


def namespace(base, contract):
    args = ['bwrap', '--unshare-net', '--unshare-pid', '--unshare-ipc', '--new-session', '--die-with-parent',
            '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root', '--tmpfs', '/tmp', '--tmpfs', '/run',
            '--proc', '/proc', '--dev', '/dev']
    for path in [ROOT / capture.fixed_runtime.MANIFEST, ROOT / contract['sdkRelativePath'], ROOT / contract['snapshotRelativePath'],
                 Path(contract['codexPath']).parents[1], *(ROOT / 'evals/skills/routing' / n for n in CODE)]:
        args += ['--ro-bind', str(path), str(path)]
    return args + ['--bind', str(base), str(base), '--chdir', str(base / 'work'), '--',
                  '/usr/bin/python3', '-B', str(Path(__file__)), '--isolated', str(base)]


def isolated(base):
    contract = trace.strict_json((base / 'contract.json').read_bytes())
    capture.policy(contract)
    trace.require(not any((ROOT / n).exists() for n in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results']), 'evaluation tree visible')
    sys.path.insert(0, str(ROOT / contract['sdkRelativePath']))
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    trace.require(__version__ == contract['sdkVersion'] and sdk.tree_hash(ROOT / contract['sdkRelativePath']) == contract['sdkTreeSha256'], 'SDK drift')
    capture.fixed_runtime.verify((ROOT/capture.fixed_runtime.MANIFEST).read_bytes(),contract)
    version = subprocess.run([contract['codexPath'], '--version'], capture_output=True, timeout=10)
    cli.exclusive(base / 'version.stdout', version.stdout)
    trace.require(version.returncode == 0 and version.stdout.decode().strip() == contract['codexVersion'], 'CLI drift')
    requests, errors = [], []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            errors.append('unexpected local GET')
            self.send_error(409)
        def do_POST(self):
            if self.path != '/v1/responses' or requests:
                errors.append('unexpected local request or budget exceeded')
                self.send_error(409)
                return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            requests.append(raw)
            cli.exclusive(base / 'request-1.json', raw)
            decision = dict(selectedEntry=None, selectedPath=None, outcome='not-applicable', events=[], rejectedEvents=[],
                            readyClaimed=False, evidencePresent=False, reason='LOCAL_CONTEXT_CALIBRATION_ONLY')
            item = dict(type='message', id='calibration-final', role='assistant', phase='final_answer', status='completed',
                        content=[dict(type='output_text', text=json.dumps(decision), annotations=[])])
            events = [dict(type='response.created', response=dict(id='calibration-response', status='in_progress', output=[])),
                      dict(type='response.output_item.done', output_index=0, item=item),
                      dict(type='response.completed', response=dict(id='calibration-response', status='completed', output=[item]))]
            body = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers()
            self.wfile.write(body);self.wfile.flush()
    server = HTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True);worker.start()
    config = capture.config_for(base, contract)
    config.update({'model_providers.bitz_openai_http.base_url':f'http://127.0.0.1:{server.server_port}/v1',
                   'model_providers.bitz_openai_http.requires_openai_auth':False})
    cli.exclusive(base / 'config.json', cli.encoded(config))
    def deny(*_): raise ValueError('unexpected local server request')
    client = CodexClient(CodexConfig(launch_args_override=(sys.executable,'-B',str(Path(__file__)),'--proxy',str(base)),
                                   cwd=str(base/'work')),approval_handler=deny)
    error = None
    try:
        client.start();client.initialize()
        thread = client.thread_start(dict(model=contract['model'],modelProvider='bitz_openai_http',allowProviderModelFallback=False,
            cwd=str(base/'work'),sandbox='read-only',approvalPolicy='never',ephemeral=True,baseInstructions=capture.BASE,
            developerInstructions=capture.DEVELOPER,experimentalRawEvents=True))
        turn = client.turn_start(thread.thread.id,(base/'model-input.json').read_text(),
                                {'outputSchema':capture.execution_schema(trace.strict_json((base/'decision-schema.json').read_bytes())),'effort':'low'})
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed': pass
    except Exception as exc: error = type(exc).__name__
    finally:
        client.close();server.shutdown();server.server_close();worker.join(2)
    cli.exclusive(base/'isolated-result.json',ledger.encoded(dict(errorType=error,localRequests=len(requests),errors=errors,
        paidModelCalls=0,networkNamespaceIsolated=True,credentialsHidden=True)))


def run(source):
    bound, before = capture.prepare_calibration(source)
    verify = guard.verify(ROOT,source,list(dict.fromkeys([*bound.contract['sourceFiles'],*SOURCES])))
    runtime_raw=guard.git(ROOT,'show',source+':'+capture.fixed_runtime.MANIFEST)
    runtime_before=capture.fixed_runtime.verify(runtime_raw,bound.contract)
    base = ROOT / OUTPUT
    ledger.safe_tree(base);base.mkdir(mode=0o700)
    for name in ['work','tmp','codex-home','logs','state','rollout-traces']:(base/name).mkdir(mode=0o700)
    cli.exclusive(base/'contract.json',bound.contract_raw)
    cli.exclusive(base/'model-input.json',bound.payloads[0])
    schema=trace.strict_json(guard.git(ROOT,'show',source+':evals/skills/schemas/decision.schema.json'))
    schema['properties']['selectedEntry']['enum']=[None,*sorted(trace.SKILLS)]
    cli.exclusive(base/'decision-schema.json',cli.encoded(schema))
    command=namespace(base,bound.contract)
    cli.exclusive(base/'invocation.json',ledger.encoded(dict(argv=command,sourceCommit=source,maximumLocalRequests=1,
        timeoutSeconds=60,paidModelCalls=0)))
    env=dict(PATH=str(Path(bound.contract['codexPath']).parents[1]/'bin')+':/usr/bin:/bin',LANG='C.UTF-8',
             PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(base/'tmp'),LOG_FORMAT='json',
             RUST_LOG='codex_otel.trace_safe=info,codex_code_mode::timing=info',CODEX_ROLLOUT_TRACE_ROOT=str(base/'rollout-traces'))
    runtime_invoke=capture.fixed_runtime.verify(runtime_raw,bound.contract)
    trace.require(runtime_invoke==runtime_before,'local calibration runtime drift')
    process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    timed_out=False
    try: stdout,stderr=process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        timed_out=True;os.killpg(process.pid,signal.SIGTERM)
        try:stdout,stderr=process.communicate(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
    cli.exclusive(base/'namespace.stdout',stdout);cli.exclusive(base/'namespace.stderr',stderr)
    after=guard.verify(ROOT,source,list(dict.fromkeys([*bound.contract['sourceFiles'],*SOURCES])))
    runtime_after=capture.fixed_runtime.verify(runtime_raw,bound.contract)
    result=trace.strict_json((base/'isolated-result.json').read_bytes()) if (base/'isolated-result.json').exists() else None
    ok=process.returncode==0 and not timed_out and result==dict(errorType=None,localRequests=1,errors=[],paidModelCalls=0,
        networkNamespaceIsolated=True,credentialsHidden=True) and verify==after and runtime_before==runtime_invoke==runtime_after
    receipt=dict(status='local_primary_context_captured' if ok else 'local_primary_context_stopped',sourceCommit=source,
        exitCode=process.returncode,timedOut=timed_out,sourceGuards=dict(before=verify,after=after),
        runtimeGuards=dict(before=runtime_before,invoke=runtime_invoke,after=runtime_after),
        localResult=result,paidModelCalls=0,primaryModelTrajectories=0,eligibleForMeasurement=False)
    cli.exclusive(base/'receipt.json',ledger.encoded(receipt));print(json.dumps({k:v for k,v in receipt.items() if k!='sourceGuards'}))
    return 0 if ok else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--isolated',type=Path);p.add_argument('--proxy',type=Path);a=p.parse_args()
    if a.proxy:raise SystemExit(sdk.proxy(a.proxy))
    if a.isolated:isolated(a.isolated)
    else:raise SystemExit(run(a.source))
