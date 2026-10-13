"""局所隔離argvとSDK原の差替えを合成で検査。外部モデル・実予約0。"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_matrix_context_probe as probe
import test_production_matrix_preflight as resource_fixture
import test_production_canary_calibration as calibration_fixture


class MatrixContextProbeTests(unittest.TestCase):
    def setUp(self):
        resource=resource_fixture.MatrixPreflightTests(methodName='runTest');resource.setUp();self.addCleanup(resource.doCleanups)
        calibration=calibration_fixture.CanaryCalibrationTests(methodName='runTest');calibration.setUp();self.addCleanup(calibration.doCleanups)
        patcher=patch.object(probe.preflight.capture.fixed_runtime,'ROOT',resource.runtime_root);patcher.start();self.addCleanup(patcher.stop)
        self.resource=resource;self.repository=resource.repository;self.base=self.repository/'.venv/matrix-local-isolation-synthetic'
        self.schema=calibration.originals['decision-schema.json'];self.context_raw=probe.io.encoded(calibration.profile)
        resource.execution['pins'].update(decisionSchema=probe.io.sha(self.schema),contextProfile=probe.io.sha(self.context_raw));resource.bound=resource.bind()
        resource.deployment.update(executionSha256=probe.io.sha(resource.bound.execution_raw),contextProfileSha256=probe.io.sha(self.context_raw))
        self.bound=resource.bound;self.deployment_raw=probe.io.encoded(resource.deployment);self.slot=self.bound.slot(1)
        self.resource_proof_raw=b'{"syntheticPublicResources":true}'
        self.originals={name:b'' for name in probe.FIXED_FILES}
        self.originals.update(calibration.originals);self.originals.pop('receipt.json')
        self.originals.update({'contract.json':self.bound.execution_raw,'deployment.json':self.deployment_raw,
            'sdk-manifest.json':resource.sdk_manifest_raw,'reservation.json':probe.io.encoded(self.slot),
            'resource-preflight.json':self.resource_proof_raw,'model-input.json':self.bound.matrix.payloads[0],
            'context-profile.json':self.context_raw,'launch-settings.json':probe.launch.launch_settings(self.bound.execution_raw,self.deployment_raw),
            'version.stderr':b'', 'isolated-result.json':probe.io.encoded(dict(errorType=None,localRequests=1,errors=[],paidModelCalls=0,
                networkNamespace='net:[2]',networkNamespaceIsolated=True,credentialsMounted=False))})
        sent=probe.primary.json_lines(self.originals['rpc-in.jsonl']);received=probe.primary.json_lines(self.originals['rpc-out.jsonl'])
        sent[2]['params']['cwd']=str(self.base/'work');sent[3]['params']['input'][0]['text']=self.originals['model-input.json'].decode()
        sent[3]['params']['outputSchema']=probe.preflight.capture.execution_schema(probe.trace.strict_json(self.schema))
        request=probe.trace.strict_json(self.originals['request-1.json'])
        request['text']['format']['schema']=sent[3]['params']['outputSchema']
        request['input'][3]['content'][0]['text']=probe.sdk_trace._diagnostic_environment(str(self.base/'work'),calibration.profile['date'],{calibration.profile['date']})
        request['input'][4]['content'][0]['text']=self.originals['model-input.json'].decode()
        for frame in received:
            item=frame.get('params',{}).get('item',{})
            if item.get('type')=='userMessage':item['content'][0]['text']=self.originals['model-input.json'].decode()
            if item.get('type')=='agentMessage' and item.get('phase')=='final_answer':item['text']=json.dumps(probe.FINAL)
            if frame.get('method')=='turn/completed':
                for i in frame['params']['turn']['items']:
                    if i.get('type')=='agentMessage' and i.get('phase')=='final_answer':i['text']=json.dumps(probe.FINAL)
        raw=[f for f in received if f.get('method') in probe.sdk_trace.RAW_METHODS]
        for frame,item in zip(raw[:3],request['input'][2:]):frame['params']['item']=copy.deepcopy(item)
        raw[3]['params']['item']['content'][0]['text']=json.dumps(probe.FINAL);raw[4]['params']['responseId']='matrix-local-response'
        self.originals['rpc-in.jsonl']=b''.join(probe.io.encoded(f)+b'\n' for f in sent)
        self.originals['rpc-out.jsonl']=b''.join(probe.io.encoded(f)+b'\n' for f in received)
        self.originals['request-1.json']=probe.io.encoded(request)
        self.originals['invocation.json']=probe.io.encoded(dict(version=probe.launch.PROBE_VERSION,
            argv=probe.launch.local_namespace_command(self.repository,self.base,self.bound.execution_raw,self.deployment_raw),
            environment=probe.launch.local_environment(self.base,resource.deployment),sourceCommit=self.bound.contract['sourceCommit'],
            executionSha256=probe.io.sha(self.bound.execution_raw),slot=self.slot,maximumLocalRequests=1,maximumLogicalTurns=1,
            timeoutSeconds=60,paidModelCalls=0,parentNetworkNamespace='net:[1]'))
        config=probe.preflight.capture.config_for(self.base,resource.deployment,repository=self.repository)
        config.update({'model_providers.bitz_openai_http.base_url':'http://127.0.0.1:1234/v1',
            'model_providers.bitz_openai_http.requires_openai_auth':False})
        self.originals['config.json']=probe.io.encoded(config)

    def verify(self):
        return probe.verify_originals(self.originals,execution_raw=self.bound.execution_raw,deployment_raw=self.deployment_raw,
            slot=self.slot,cwd=str(self.base/'work'),source_repository=self.repository,context_raw=self.context_raw,
            resource_proof_raw=self.resource_proof_raw)

    def test_complete_local_sdk_originals_do_not_claim_primary_or_launch_permission(self):
        result=self.verify();self.assertEqual(result['localHttpRequests'],1);self.assertEqual(result['rawNotificationCount'],5)
        self.assertEqual(result['realReservations'],0);self.assertEqual(result['paidModelCalls'],0)
        self.assertFalse(result['launchEnabled']);self.assertFalse(result['eligibleForMeasurement'])

    def test_namespace_has_network_isolation_and_only_explicit_public_mounts(self):
        value=json.loads(self.originals['invocation.json']);argv=value['argv'];self.assertIn('--unshare-net',argv)
        mounts=[argv[i+1] for i,v in enumerate(argv) if v=='--ro-bind'][1:]
        self.assertFalse(any('/auth.json' in p or p.endswith(('routing.json','behavior-safety.json','sol-authorization.json')) for p in mounts))
        self.assertFalse(any('/.git' in p or '/results/' in p or '/docs/' in p for p in mounts))
        self.assertIn(str(self.repository/self.resource.sdk_relative),mounts)
        self.assertEqual(value['environment']['CODEX_HOME'],str(self.base/'codex-home'))

    def test_network_auth_argv_environment_and_full_config_drift_are_rejected(self):
        before=copy.deepcopy(self.originals)
        for fault in ['network','auth-mount','environment','auth-config','url','unknown-config']:
            self.originals=copy.deepcopy(before)
            if fault in {'network','auth-mount','environment'}:
                name='invocation.json';v=json.loads(self.originals[name])
                if fault=='network':v['argv'].remove('--unshare-net')
                elif fault=='auth-mount':v['argv'][1:1]=['--ro-bind','/unknown/auth.json','/unknown/auth.json']
                else:v['environment']['CODEX_HOME']='/unknown/home'
            else:
                name='config.json';v=json.loads(self.originals[name])
                if fault=='auth-config':v['model_providers.bitz_openai_http.requires_openai_auth']=True
                elif fault=='url':v['model_providers.bitz_openai_http.base_url']='https://external.invalid/v1'
                else:v['unexpected']=True
            self.originals[name]=probe.io.encoded(v)
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify()

    def test_changed_original_resource_proof_slot_input_and_schema_are_rejected(self):
        before=copy.deepcopy(self.originals)
        for name in ['resource-preflight.json','contract.json','deployment.json','reservation.json','model-input.json','decision-schema.json','sdk-manifest.json']:
            self.originals=copy.deepcopy(before);self.originals[name]=b'{}'
            with self.subTest(name=name),self.assertRaises(ValueError):self.verify()

    def test_incomplete_child_and_same_network_namespace_are_rejected(self):
        before=copy.deepcopy(self.originals)
        for key,value in [('localRequests',True),('localRequests',2),('credentialsMounted',True),('paidModelCalls',1),
                          ('networkNamespace','net:[1]'),('errorType','Failure'),('errors',['unexpected'])]:
            self.originals=copy.deepcopy(before);v=json.loads(self.originals['isolated-result.json']);v[key]=value
            self.originals['isolated-result.json']=probe.io.encoded(v)
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()

    def test_raw_context_final_and_response_rewrites_cannot_pass_sdk_normalization(self):
        before=copy.deepcopy(self.originals)
        for fault in ['raw-context','raw-final','missing-raw','usage','response-id','request-context']:
            self.originals=copy.deepcopy(before)
            if fault=='request-context':
                v=json.loads(self.originals['request-1.json']);v['input'][2]['content'][0]['text']='changed'
                self.originals['request-1.json']=probe.io.encoded(v)
            else:
                frames=probe.primary.json_lines(self.originals['rpc-out.jsonl']);raw=[f for f in frames if f.get('method') in probe.sdk_trace.RAW_METHODS]
                if fault=='raw-context':raw[0]['params']['item']['content'][0]['text']='changed'
                elif fault=='raw-final':raw[3]['params']['item']['content'][0]['text']='{}'
                elif fault=='missing-raw':frames.remove(raw[0])
                elif fault=='usage':raw[4]['params']['usage']={'invented':1}
                else:raw[4]['params']['responseId']='other'
                self.originals['rpc-out.jsonl']=b''.join(probe.io.encoded(f)+b'\n' for f in frames)
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify()

    def test_common_artifact_repository_is_shared_across_source_worktrees(self):
        common=self.repository/'.venv/ignored-ledger'
        with patch.object(probe.launch.io,'common_ledger_path',return_value=common):
            first=probe.launch.probe_layout(self.repository/'.venv/source-a','.venv/matrix-local-isolation-public')
            second=probe.launch.probe_layout(self.repository/'.venv/source-b','.venv/matrix-local-isolation-public')
        self.assertEqual(first,second);self.assertEqual(first[0],self.repository)
        self.assertEqual(first[1],self.repository/'.venv/matrix-local-isolation-public')

    def test_rejected_original_is_recorded_without_reading_link_target_or_losing_good_raw(self):
        base=self.repository/'.venv/rejected-originals';base.mkdir()
        good=b'public raw preserved';(base/'rpc-out.jsonl').write_bytes(good)
        (base/'runtime-result.json').symlink_to('missing-private-target')
        originals,errors=probe.read_probe_files(base)
        self.assertEqual(originals,{'rpc-out.jsonl':good});self.assertIn('runtime-result.json',errors)
        self.assertEqual(len(errors),len(probe.FIXED_FILES)-1)

    def test_unknown_or_private_original_inventory_rejected_before_consumption(self):
        self.originals['codex-home/auth.json']=b'SYNTHETIC_PRIVATE_SENTINEL'
        with self.assertRaisesRegex(ValueError,'inventory'):self.verify()
        with self.assertRaises(ValueError):probe.launch.probe_layout(self.repository,'.venv/../outside')


if __name__=='__main__':unittest.main()
