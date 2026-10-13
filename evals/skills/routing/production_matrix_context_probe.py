"""行列専用namespaceで実SDK/CLIの局所応答を検査。認証・外部モデル・予約0。"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import production_matrix_launch as launch
import production_matrix_preflight as preflight
import production_primary_review as primary
import production_canary_rollout as rollout
import production_sdk_trace as sdk_trace

ROOT = Path(__file__).resolve().parents[3]
io = preflight.io
trace = preflight.trace
require = trace.require
FINAL = dict(selectedEntry=None, selectedPath=None, outcome='not-applicable', events=[], rejectedEvents=[],
    readyClaimed=False, evidencePresent=False, reason='LOCAL_MATRIX_ISOLATION_ONLY')
FIXED_FILES = {'contract.json', 'deployment.json', 'sdk-manifest.json', 'reservation.json',
    'resource-preflight.json', 'model-input.json', 'decision-schema.json', 'context-profile.json',
    'launch-settings.json', 'invocation.json', 'config.json', 'version.stdout', 'version.stderr',
    'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-stderr.bin', 'trace-safe.jsonl', 'runtime-result.json',
    'isolated-result.json', 'request-1.json', 'namespace.stdout', 'namespace.stderr'}


def isolated(base):
    execution_raw = io.read_regular(base/'contract.json')
    c = preflight.matrix.execution_contract(execution_raw)
    deployment_raw = io.read_regular(base/'deployment.json')
    d = preflight.deployment_for_execution(execution_raw, deployment_raw)
    settings_raw = io.read_regular(base/'launch-settings.json')
    require(settings_raw == launch.launch_settings(execution_raw, deployment_raw), 'matrix CLI settings drift')
    require(not any((ROOT/p).exists() for p in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results']),
            'matrix evaluation tree visible')
    invocation = trace.strict_json(io.read_regular(base/'invocation.json'))
    network_namespace = os.readlink('/proc/self/ns/net')
    require(network_namespace != invocation['parentNetworkNamespace'], 'matrix network namespace not isolated')
    sdk_raw = io.read_regular(base/'sdk-manifest.json');sdk_files = preflight.sdk_manifest(sdk_raw, d)
    dependencies = preflight.exact_tree(ROOT/d['sdkRelativePath'], sdk_files)
    require({name:io.sha(raw) for name,raw in dependencies.items()} == sdk_files, 'matrix SDK drift in child')
    preflight.capture.fixed_runtime.verify(io.read_regular(ROOT/preflight.capture.fixed_runtime.MANIFEST), d)
    sys.path.insert(0, str(ROOT/d['sdkRelativePath']))
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    require(__version__ == d['sdkVersion'], 'matrix SDK version drift')
    version = subprocess.run([d['codexPath'], '--version'], capture_output=True, timeout=10)
    io.exclusive(base/'version.stdout', version.stdout);io.exclusive(base/'version.stderr', version.stderr)
    require(version.returncode == 0 and version.stdout == (d['codexVersion']+'\n').encode(), 'matrix CLI version drift')
    payload = io.read_regular(base/'model-input.json');slot = trace.strict_json(io.read_regular(base/'reservation.json'))
    require(slot['executionSha256'] == io.sha(execution_raw) and slot['sourceCommit'] == c['sourceCommit']
        and slot['payloadSha256'] == io.sha(payload), 'matrix child input drift')
    schema_raw = io.read_regular(base/'decision-schema.json')
    require(io.sha(schema_raw) == c['pins']['decisionSchema'], 'matrix child canonical Schema drift')
    requests, errors = [], []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):pass
        def do_GET(self):
            errors.append('unexpected local GET');self.send_error(409)
        def do_POST(self):
            if self.path != '/v1/responses' or requests:
                errors.append('local request inventory or limit');self.send_error(409);return
            raw = self.rfile.read(int(self.headers['Content-Length']))
            requests.append(raw);io.exclusive(base/'request-1.json', raw)
            item = dict(type='message', id='matrix-local-final', role='assistant', phase='final_answer', status='completed',
                content=[dict(type='output_text', text=json.dumps(FINAL), annotations=[])])
            events = [dict(type='response.created', response=dict(id='matrix-local-response', status='in_progress', output=[])),
                dict(type='response.output_item.done', output_index=0, item=item),
                dict(type='response.completed', response=dict(id='matrix-local-response', status='completed', output=[item]))]
            body = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers()
            self.wfile.write(body);self.wfile.flush()
    server = HTTPServer(('127.0.0.1',0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True);worker.start()
    config = preflight.capture.config_for(base, d, repository=ROOT)
    config.update({'model_providers.bitz_openai_http.base_url':f'http://127.0.0.1:{server.server_port}/v1',
        'model_providers.bitz_openai_http.requires_openai_auth':False})
    io.exclusive(base/'config.json', io.encoded(config))
    def deny(*_):raise ValueError('unexpected local SDK server request')
    client = CodexClient(CodexConfig(launch_args_override=(sys.executable,'-B',str(Path(__file__)), '--proxy',str(base)),
        cwd=str(base/'work')), approval_handler=deny)
    error = None
    try:
        client.start();client.initialize()
        thread = client.thread_start(dict(model=c['model'],modelProvider='bitz_openai_http',allowProviderModelFallback=False,
            cwd=str(base/'work'),sandbox='read-only',approvalPolicy='never',ephemeral=True,
            baseInstructions=preflight.capture.BASE,developerInstructions=preflight.capture.DEVELOPER,experimentalRawEvents=True))
        turn = client.turn_start(thread.thread.id,payload.decode(),
            dict(outputSchema=preflight.capture.execution_schema(trace.strict_json(schema_raw)),effort='low'))
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed':pass
    except Exception as exc:error=type(exc).__name__
    finally:
        client.close();server.shutdown();server.server_close();worker.join(2)
    io.exclusive(base/'isolated-result.json',io.encoded(dict(errorType=error,localRequests=len(requests),errors=errors,
        paidModelCalls=0,networkNamespace=network_namespace,networkNamespaceIsolated=True,credentialsMounted=False)))


def verify_originals(originals, *, execution_raw, deployment_raw, slot, cwd, source_repository, context_raw, resource_proof_raw):
    require(isinstance(originals, dict) and set(originals) == FIXED_FILES
            and all(isinstance(raw,bytes) for raw in originals.values()), 'matrix local original inventory')
    require(isinstance(resource_proof_raw,bytes) and originals['resource-preflight.json'] == resource_proof_raw,
            'matrix local resource proof drift')
    d = preflight.deployment_for_execution(execution_raw,deployment_raw)
    require(originals['contract.json'] == execution_raw and originals['deployment.json'] == deployment_raw
        and originals['reservation.json'] == io.encoded(slot) and io.sha(originals['model-input.json']) == slot['payloadSha256']
        and originals['launch-settings.json'] == launch.launch_settings(execution_raw,deployment_raw), 'matrix local consumed input drift')
    preflight.sdk_manifest(originals['sdk-manifest.json'],d)
    require(originals['context-profile.json'] == context_raw and io.sha(context_raw) == d['contextProfileSha256'],
            'matrix local context original drift')
    c = preflight.matrix.execution_contract(execution_raw)
    require(io.sha(originals['decision-schema.json']) == c['pins']['decisionSchema'], 'matrix local Schema original drift')
    require(originals['version.stdout'] == b'codex-cli 0.160.1\n' and originals['version.stderr'] == b''
        and trace.json_equal(trace.strict_json(originals['runtime-result.json']),dict(exitCode=0,forcedShutdown=False)),
        'matrix local runtime incomplete')
    child = trace.strict_json(originals['isolated-result.json'])
    require(isinstance(child,dict) and set(child)=={'errorType','localRequests','errors','paidModelCalls',
        'networkNamespace','networkNamespaceIsolated','credentialsMounted'} and child['errorType'] is None
        and trace.json_equal({k:child[k] for k in ['localRequests','errors','paidModelCalls','networkNamespaceIsolated','credentialsMounted']},
            dict(localRequests=1,errors=[],paidModelCalls=0,networkNamespaceIsolated=True,credentialsMounted=False)),
        'matrix local child incomplete')
    invocation = trace.strict_json(originals['invocation.json'])
    base=Path(cwd).parent
    require(trace.json_equal(invocation,dict(version=launch.PROBE_VERSION,
        argv=launch.local_namespace_command(source_repository,base,execution_raw,deployment_raw),
        environment=launch.local_environment(base,d),sourceCommit=c['sourceCommit'],executionSha256=io.sha(execution_raw),
        slot=slot,maximumLocalRequests=1,maximumLogicalTurns=1,timeoutSeconds=60,paidModelCalls=0,
        parentNetworkNamespace=invocation.get('parentNetworkNamespace'))), 'matrix local invocation drift')
    require(isinstance(child['networkNamespace'],str) and re_network(child['networkNamespace'])
        and isinstance(invocation['parentNetworkNamespace'],str) and re_network(invocation['parentNetworkNamespace'])
        and child['networkNamespace'] != invocation['parentNetworkNamespace'], 'matrix local network original drift')
    config = trace.strict_json(originals['config.json']);url=config.get('model_providers.bitz_openai_http.base_url')
    import re
    require(isinstance(url,str) and re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}/v1',url) is not None
        and 1 <= int(url.split(':')[2].split('/')[0]) <= 65535, 'matrix local loopback URL')
    expected_config=preflight.capture.config_for(base,d,repository=source_repository)
    expected_config.update({'model_providers.bitz_openai_http.base_url':url,'model_providers.bitz_openai_http.requires_openai_auth':False})
    require(trace.json_equal(config,expected_config), 'matrix local complete config drift')
    sent=primary.json_lines(originals['rpc-in.jsonl']);received=primary.json_lines(originals['rpc-out.jsonl'])
    wire_schema=preflight.capture.execution_schema(trace.strict_json(originals['decision-schema.json']))
    sdk_trace.requests(sent,profile='public-canary',output_schema=wire_schema)
    require(sent[2]['params']['cwd']==cwd and sent[2]['params']['baseInstructions']==preflight.capture.BASE
        and sent[2]['params']['developerInstructions']==preflight.capture.DEVELOPER
        and sent[3]['params']['input'][0]['text'].encode()==originals['model-input.json'], 'matrix local original SDK input')
    projected,raw=primary.raw_projection(sent,received)
    native=sdk_trace.normalized(sent,projected,profile='public-canary',output_schema=wire_schema)
    items=trace.completed_items(native['frames']);finals=[i for i in items if i['type']=='agentMessage' and i['phase']=='final_answer']
    require(all(i['type'] in {'userMessage','agentMessage','reasoning'} for i in items) and len(finals)==1
        and trace.json_equal(trace.strict_json(finals[0]['text']),FINAL),'matrix local scripted final or action drift')
    trace.jsonschema.Draft202012Validator(trace.strict_json(originals['decision-schema.json'])).validate(FINAL)
    turns=[f['params']['turn']['id'] for f in received if f.get('method')=='turn/started'];require(len(turns)==1,'matrix local one turn')
    request=trace.strict_json(originals['request-1.json'])
    rollout.request_policy(request,sent,thread=sent[3]['params']['threadId'],turn=turns[0],profile='local-calibration')
    rollout.initial_context(request,sent,trace.strict_json(context_raw),turn=turns[0])
    require([f['method'] for f in raw] == [sdk_trace.RAW_METHODS[0]]*4+[sdk_trace.RAW_METHODS[1]],
            'matrix local complete raw notification inventory')
    for frame,item in zip(raw[:3],request['input'][2:]):
        require(trace.json_equal(rollout.metadata(frame['params']['item'],turns[0]),rollout.metadata(item,turns[0])),
                'matrix local original raw context')
    final_raw=rollout.metadata(raw[3]['params']['item'],turns[0])
    require(trace.json_equal(final_raw,dict(type='message',id=finals[0]['id'],role='assistant',phase='final_answer',
        content=[dict(type='output_text',text=finals[0]['text'])])) and raw[4]['params']['usage'] is None
        and raw[4]['params']['usageMetadata'] is None and raw[4]['params']['responseId']=='matrix-local-response',
        'matrix local original raw final/response')
    return dict(status='matrix_local_sdk_context_verified',rawNotificationCount=len(raw),primaryModelTrajectories=0,
        paidModelCalls=0,realReservations=0,localHttpRequests=1,launchEnabled=False,eligibleForMeasurement=False,
        certifiesSkillGate=False,certifiesRelease=False)


def re_network(value):
    import re
    return re.fullmatch(r'net:\[[0-9]+\]',value) is not None


def read_probe_files(base):
    """固定名だけを読む。壊れた原があっても他の原と拒否理由を保持する。"""
    originals,errors={},{}
    for name in sorted(FIXED_FILES):
        try:
            originals[name]=io.read_regular(base/name)
        except Exception as exc:
            errors[name]=type(exc).__name__
    return originals,errors


def run_probe(source_repository,bound,deployment_raw,sdk_manifest_raw,output_relative_root):
    before=preflight.verify_resources(source_repository,bound,deployment_raw,sdk_manifest_raw)
    d=preflight.deployment(bound,deployment_raw);source=bound.contract['sourceCommit'];slot=bound.slot(1)
    artifact_repository,base=launch.probe_layout(source_repository,output_relative_root)
    io.safe_tree(base);base.mkdir(mode=0o700)
    for name in ['work','tmp','codex-home','logs','state','rollout-traces']:(base/name).mkdir(mode=0o700)
    schema_raw=preflight.decision_schema(preflight.guard.git(source_repository,'show',source+':'+preflight.inventory.SCHEMA))
    context_raw=preflight.guard.git(source_repository,'show',source+':'+preflight.inventory.CONTEXT)
    for name,raw in [('contract.json',bound.execution_raw),('deployment.json',deployment_raw),('sdk-manifest.json',sdk_manifest_raw),
        ('reservation.json',io.encoded(slot)),('resource-preflight.json',io.encoded(before)),('model-input.json',bound.matrix.payloads[0]),
        ('decision-schema.json',schema_raw),('context-profile.json',context_raw),('launch-settings.json',launch.launch_settings(bound.execution_raw,deployment_raw))]:
        io.exclusive(base/name,raw)
    command=launch.local_namespace_command(source_repository,base,bound.execution_raw,deployment_raw)
    environment=launch.local_environment(base,d)
    io.exclusive(base/'invocation.json',io.encoded(dict(version=launch.PROBE_VERSION,argv=command,environment=environment,
        sourceCommit=source,executionSha256=io.sha(bound.execution_raw),slot=slot,maximumLocalRequests=1,maximumLogicalTurns=1,
        timeoutSeconds=60,paidModelCalls=0,parentNetworkNamespace=os.readlink('/proc/self/ns/net'))))
    invoke=preflight.verify_resources(source_repository,bound,deployment_raw,sdk_manifest_raw)
    require(invoke==before,'matrix local pre-invocation drift; output retained')
    start=time.monotonic();process=subprocess.Popen(command,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    timed_out=False
    try:stdout,stderr=process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        timed_out=True;os.killpg(process.pid,signal.SIGTERM)
        try:stdout,stderr=process.communicate(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
    io.exclusive(base/'namespace.stdout',stdout);io.exclusive(base/'namespace.stderr',stderr)
    originals,original_errors=read_probe_files(base)
    after=None;verification=None;error=None
    try:
        after=preflight.verify_resources(source_repository,bound,deployment_raw,sdk_manifest_raw)
        require(before==after and process.returncode==0 and not timed_out,'matrix local process or resource drift')
        require(not original_errors,'matrix local missing or rejected original')
        verification=verify_originals(originals,execution_raw=bound.execution_raw,deployment_raw=deployment_raw,slot=slot,
            cwd=str(base/'work'),source_repository=source_repository,context_raw=context_raw,resource_proof_raw=io.encoded(before))
    except Exception as exc:error=dict(errorType=type(exc).__name__,message=str(exc))
    receipt=dict(version=launch.PROBE_VERSION,status='local_isolation_verified' if verification is not None else 'local_isolation_stopped',
        sourceCommit=source,executionSha256=io.sha(bound.execution_raw),sourceRepository=str(source_repository),artifactRepository=str(artifact_repository),
        resourceGuards=dict(before=before,invoke=invoke,after=after),namespaceExitCode=process.returncode,timedOut=timed_out,
        elapsedSeconds=time.monotonic()-start,artifactSha256={name:io.sha(raw) for name,raw in originals.items()},originalReadErrors=original_errors,
        verification=verification,error=error,primaryModelTrajectories=0,paidModelCalls=0,realReservations=0,
        automaticRetries=0,launchEnabled=False,eligibleForMeasurement=False,certifiesSkillGate=False,certifiesRelease=False)
    io.exclusive(base/'receipt.json',io.encoded(receipt))
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--isolated',type=Path);parser.add_argument('--proxy',type=Path);args=parser.parse_args()
    if args.proxy:
        preflight.capture.sdk.proxy(args.proxy,reject_questions=True,reject_actions=True,
            launch_contract_raw=io.read_regular(args.proxy/'launch-settings.json'))
    elif args.isolated:isolated(args.isolated)
    else:parser.error('local --isolated or --proxy required; no provider launch entry')
