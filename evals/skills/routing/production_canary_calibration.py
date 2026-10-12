"""局所校正の原記録と固定Gitソースを照合する。実provider測定ではない。"""
from __future__ import annotations
import ast
from pathlib import Path
import re

import production_canary_runtime as runtime
import production_ledger as ledger
import production_trace as trace
import source_guard as guard

ROOT=runtime.ROOT.parent/'development-review-20261011/.venv/primary-context-calibration-06'
MANIFEST='evals/skills/routing/production-canary-calibration-v0.1.json'
FILES={'request-1.json','receipt.json','config.json','contract.json','invocation.json','rpc-in.jsonl','rpc-out.jsonl',
       'model-input.json','decision-schema.json','runtime-result.json','isolated-result.json','version.stdout'}
require=trace.require


def literal(source,name):
    values=[ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id==name for t in node.targets)]
    require(len(values)==1,'one fixed calibration source constant')
    return values[0]


def lines(raw):
    return [trace.strict_json(line) for line in raw.splitlines()]


def verify(repository, manifest_raw, profile, contract):
    import production_sdk_trace as sdk
    require(ledger.sha(manifest_raw)==ledger.pin(contract['calibrationManifestSha256']),'fixed calibration manifest hash')
    manifest=trace.strict_json(manifest_raw)
    require(isinstance(manifest,dict) and set(manifest)=={'version','sourceCommit','artifactSha256'} and
        manifest['version'] in {'primary-client-calibration-originals-0.1.1','primary-client-calibration-originals-0.1.2'} and
        manifest['sourceCommit']==profile['calibrationSource'] and re.fullmatch(r'[0-9a-f]{40}',manifest['sourceCommit']) and
        isinstance(manifest['artifactSha256'],dict) and set(manifest['artifactSha256'])==FILES,'fixed calibration inventory')
    for digest in manifest['artifactSha256'].values():ledger.pin(digest)
    # 有限な公開artifact名だけを開く。private領域を列挙しない。
    originals={name:ledger.read_regular(ROOT/name) for name in sorted(FILES)}
    require({name:ledger.sha(raw) for name,raw in originals.items()}==manifest['artifactSha256'],'original calibration bytes drift')
    require(ledger.sha(originals['receipt.json'])==profile['calibrationReceiptSha256'] and
        ledger.sha(originals['request-1.json'])==profile['calibrationRequestSha256'],'profile and original calibration hash')
    source=manifest['sourceCommit']
    source_contract=trace.strict_json(guard.git(repository,'show',source+':evals/skills/routing/production-canary-v0.1.json'))
    saved_contract=trace.strict_json(originals['contract.json'])
    require(all(trace.json_equal(saved_contract.get(k),v) for k,v in source_contract.items()) and
        saved_contract.get('sourceCommit')==source,'original calibration source contract')
    source_files=list(dict.fromkeys([*source_contract['sourceFiles'],'evals/skills/routing/production_canary_context_probe.py']))
    source_hash={name:ledger.sha(guard.git(repository,'show',source+':'+name)) for name in source_files}
    receipt=trace.strict_json(originals['receipt.json'])
    source_evidence=dict(status='fixed_source_matches',sourceCommit=source,observedHead=source,
        headIsCondition=False,sourceSha256=source_hash)
    runtime_proof=runtime.verify(guard.git(repository,'show',source+':'+runtime.MANIFEST),source_contract)
    require(trace.json_equal(receipt,dict(status='local_primary_context_captured',sourceCommit=source,exitCode=0,timedOut=False,
        sourceGuards=dict(before=source_evidence,after=source_evidence),
        localResult=dict(credentialsHidden=True,errorType=None,errors=[],localRequests=1,networkNamespaceIsolated=True,paidModelCalls=0),
        runtimeGuards=dict.fromkeys(['before','invoke','after'],runtime_proof),
        paidModelCalls=0,primaryModelTrajectories=0,eligibleForMeasurement=False)),'original successful local calibration receipt')
    require(trace.json_equal(trace.strict_json(originals['isolated-result.json']),receipt['localResult']) and
        trace.json_equal(trace.strict_json(originals['runtime-result.json']),dict(exitCode=0,forcedShutdown=False)) and
        originals['version.stdout']==(profile['codexVersion']+'\n').encode(),'original calibration terminal')
    capture_source=guard.git(repository,'show',source+':evals/skills/routing/production_canary_capture.py').decode()
    base,developer,code=(literal(capture_source,k) for k in ['BASE','DEVELOPER','CODE'])
    require(isinstance(code,list) and all(isinstance(n,str) and re.fullmatch(r'[a-z_]+\.py',n) for n in code),'fixed calibration code mounts')
    old_repository=ROOT.parents[1]
    argv=['bwrap','--unshare-net','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent',
          '--ro-bind','/','/','--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run','--proc','/proc','--dev','/dev']
    for path in [old_repository/runtime.MANIFEST,old_repository/source_contract['sdkRelativePath'],old_repository/source_contract['snapshotRelativePath'],
            Path(source_contract['codexPath']).parents[1],*(old_repository/'evals/skills/routing'/n for n in [*code,'production_canary_context_probe.py'])]:
        argv += ['--ro-bind',str(path),str(path)]
    argv += ['--bind',str(ROOT),str(ROOT),'--chdir',str(ROOT/'work'),'--','/usr/bin/python3','-B',
             str(old_repository/'evals/skills/routing/production_canary_context_probe.py'),'--isolated',str(ROOT)]
    require(trace.json_equal(trace.strict_json(originals['invocation.json']),dict(argv=argv,maximumLocalRequests=1,
        paidModelCalls=0,sourceCommit=source,timeoutSeconds=60)),'original calibration isolated invocation')
    import production_canary_capture as capture
    config=trace.strict_json(originals['config.json'])
    require(isinstance(config,dict) and isinstance(config.get('model_providers.bitz_openai_http.base_url'),str) and
        re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}/v1',config['model_providers.bitz_openai_http.base_url']), 'calibration local endpoint')
    expected=capture.config_for(ROOT,source_contract,repository=old_repository)
    expected.update({'model_providers.bitz_openai_http.base_url':config['model_providers.bitz_openai_http.base_url'],
                     'model_providers.bitz_openai_http.requires_openai_auth':False})
    require(trace.json_equal(config,expected),'complete original calibration config')
    sent=lines(originals['rpc-in.jsonl']);received=lines(originals['rpc-out.jsonl'])
    schema=trace.strict_json(guard.git(repository,'show',source+':evals/skills/schemas/decision.schema.json'))
    schema['properties']['selectedEntry']['enum']=[None,*sorted(trace.SKILLS)]
    require(trace.json_equal(trace.strict_json(originals['decision-schema.json']),schema),'original calibration schema')
    wire_schema=capture.execution_schema(schema) if manifest['version']=='primary-client-calibration-originals-0.1.2' else schema
    sdk.requests(sent,profile='public-canary',output_schema=wire_schema)
    require(sent[2]['params']['baseInstructions']==base==capture.BASE and
        sent[2]['params']['developerInstructions']==developer==capture.DEVELOPER and
        sent[2]['params']['cwd']==str(ROOT/'work') and
        sent[3]['params']['input'][0]['text'].encode()==originals['model-input.json'],'original calibration caller input')
    import production_canary_review as review
    projected,raw=review.raw_projection(sent,received)
    native=sdk.normalized(sent,projected,profile='public-canary',output_schema=wire_schema)
    items=trace.completed_items(native['frames'])
    require(all(i['type'] in {'userMessage','agentMessage','reasoning'} for i in items),'calibration unknown native action')
    finals=[i for i in items if i['type']=='agentMessage' and i['phase']=='final_answer']
    expected_decision=dict(selectedEntry=None,selectedPath=None,outcome='not-applicable',events=[],rejectedEvents=[],
        readyClaimed=False,evidencePresent=False,reason='LOCAL_CONTEXT_CALIBRATION_ONLY')
    require(len(finals)==1 and trace.json_equal(trace.strict_json(finals[0]['text']),expected_decision),'calibration original final decision')
    trace.jsonschema.Draft202012Validator(schema).validate(trace.strict_json(finals[0]['text']))
    turns=[f['params']['turn']['id'] for f in received if f.get('method')=='turn/started']
    require(len(turns)==1,'one original calibration turn')
    request=trace.strict_json(originals['request-1.json'])
    import production_canary_rollout as rollout
    rollout.request_policy(request,sent,thread=sent[3]['params']['threadId'],turn=turns[0],profile='local-calibration')
    rollout.initial_context(request,sent,profile,turn=turns[0])
    require([f['method'] for f in raw]==[sdk.RAW_METHODS[0]]*4+[sdk.RAW_METHODS[1]],'calibration complete original raw inventory')
    for frame,item in zip(raw[:3],request['input'][2:]):
        require(trace.json_equal(rollout.metadata(frame['params']['item'],turns[0]),rollout.metadata(item,turns[0])), 'calibration original initial raw context')
    final_raw=rollout.metadata(raw[3]['params']['item'],turns[0])
    require(set(final_raw)=={'type','id','role','content','phase'} and final_raw['type']=='message' and final_raw['role']=='assistant' and
        final_raw['phase']=='final_answer' and final_raw['id']==finals[0]['id'] and
        final_raw['content']==[dict(type='output_text',text=finals[0]['text'])] and raw[4]['params']['usage'] is None and
        raw[4]['params']['usageMetadata'] is None and raw[4]['params']['responseId']=='calibration-response','calibration original raw final/response')
    return dict(status='original_local_calibration_matches',calibrationManifestSha256=ledger.sha(manifest_raw),
        sourceCommit=source,requestSha256=profile['calibrationRequestSha256'],receiptSha256=profile['calibrationReceiptSha256'],
        paidModelCalls=0,primaryModelTrajectories=0,certifiesProviderWireBodies=False)
