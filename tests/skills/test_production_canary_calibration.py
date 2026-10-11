"""校正の原hash・ソース・隔離条件・contextを公開合成で検査する。モデル起動0。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_calibration as calibration
import production_canary_capture as capture
import test_production_canary_rollout as rollout_fixture
import test_production_canary_trace as sdk_fixture


class CanaryCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp');self.addCleanup(self.temp.cleanup)
        self.repository=Path(self.temp.name);self.base=self.repository/'.venv/calibration';self.base.mkdir(parents=True)
        self.source='b'*40
        self.patch(calibration,'ROOT',new=self.base)
        primary=sdk_fixture.PrimaryCanaryTraceTests(methodName='runTest');primary.setUp();self.addCleanup(primary.doCleanups)
        sent=copy.deepcopy(primary.fixture.sent)
        sent[2]['params'].update(baseInstructions=capture.BASE,developerInstructions=capture.DEVELOPER,cwd=str(self.base/'work'))
        sent[3]['params']['input'][0]['text']='public calibration input'
        value=rollout_fixture.CanaryRolloutTests(methodName='runTest').fixture()
        profile=value['context_profile'];profile.update(calibrationSource=self.source)
        request=json.loads(next(raw for name,raw in value['payloads'].items() if 'client_metadata' in json.loads(raw)))
        request['prompt_cache_key']='t';request['client_metadata'].update(thread_id='t',turn_id='u',root_turn_id='u',session_id='t')
        request['client_metadata']['x-codex-window-id']='t:0'
        extra=json.loads(request['client_metadata']['x-codex-turn-metadata'])
        extra.update(session_id='t',thread_id='t',turn_id='u',root_turn_id='u',window_id='t:0')
        request['client_metadata']['x-codex-turn-metadata']=json.dumps(extra)
        request['text']['format']['schema']=primary.schema
        request['input'][1]['content'][0]['text']=capture.BASE
        request['input'][2]['content'][0]['text']=capture.DEVELOPER
        for item in request['input'][2:]:item['internal_chat_message_metadata_passthrough']['turn_id']='u'
        request['input'][3]['content'][0]['text']=calibration.sdk._diagnostic_environment(str(self.base/'work'),profile['date'],{profile['date']})
        request['input'][4]['content'][0]['text']='public calibration input'
        source_contract=dict(codexPath='/fixed/bin/codex',sdkRelativePath='.venv/sdk',snapshotRelativePath='.venv/snapshot',
            manifestSha256='1'*64,sourceFiles=['evals/skills/routing/production_canary_capture.py'])
        code='BASE='+repr(capture.BASE)+'\nDEVELOPER='+repr(capture.DEVELOPER)+'\nCODE=[]\n'
        self.git_raws={'evals/skills/routing/production-canary-v0.1.json':calibration.ledger.encoded(source_contract),
            'evals/skills/routing/production_canary_capture.py':code.encode(),
            'evals/skills/routing/production_canary_context_probe.py':b'pass\n',
            'evals/skills/schemas/decision.schema.json':(ROOT/'evals/skills/schemas/decision.schema.json').read_bytes()}
        self.patch(calibration.guard,'git',side_effect=lambda repository,*args:self.git_raws[args[1].split(':',1)[1]])
        evidence=dict(status='fixed_source_matches',sourceCommit=self.source,observedHead=self.source,headIsCondition=False,
            sourceSha256={name:calibration.ledger.sha(self.git_raws[name]) for name in [*source_contract['sourceFiles'],'evals/skills/routing/production_canary_context_probe.py']})
        local=dict(credentialsHidden=True,errorType=None,errors=[],localRequests=1,networkNamespaceIsolated=True,paidModelCalls=0)
        receipt=dict(status='local_primary_context_captured',sourceCommit=self.source,exitCode=0,timedOut=False,
            sourceGuards=dict(before=evidence,after=evidence),localResult=local,paidModelCalls=0,primaryModelTrajectories=0,eligibleForMeasurement=False)
        argv=['bwrap','--unshare-net','--unshare-pid','--unshare-ipc','--new-session','--die-with-parent',
          '--ro-bind','/','/','--tmpfs','/home','--tmpfs','/root','--tmpfs','/tmp','--tmpfs','/run','--proc','/proc','--dev','/dev']
        for p in [self.repository/'.venv/sdk',self.repository/'.venv/snapshot',Path('/fixed'),self.repository/'evals/skills/routing/production_canary_context_probe.py']:
            argv+=['--ro-bind',str(p),str(p)]
        argv+=['--bind',str(self.base),str(self.base),'--chdir',str(self.base/'work'),'--','/usr/bin/python3','-B',str(self.repository/'evals/skills/routing/production_canary_context_probe.py'),'--isolated',str(self.base)]
        config=capture.config_for(self.base,source_contract,repository=self.repository)
        config.update({'model_providers.bitz_openai_http.base_url':'http://127.0.0.1:1234/v1','model_providers.bitz_openai_http.requires_openai_auth':False})
        enc=calibration.ledger.encoded
        self.originals={'request-1.json':enc(request),'receipt.json':enc(receipt),'config.json':enc(config),
            'contract.json':enc(dict(source_contract,sourceCommit=self.source)),
            'invocation.json':enc(dict(argv=argv,maximumLocalRequests=1,paidModelCalls=0,sourceCommit=self.source,timeoutSeconds=60)),
            'rpc-in.jsonl':b''.join(enc(f)+b'\n' for f in sent),'rpc-out.jsonl':enc(dict(method='turn/started',params=dict(turn=dict(id='u'))))+b'\n',
            'model-input.json':b'public calibration input','decision-schema.json':enc(primary.schema),
            'runtime-result.json':enc(dict(exitCode=0,forcedShutdown=False)),'isolated-result.json':enc(local),'version.stdout':b'codex-cli 0.160.1\n'}
        self.profile=profile;self.contract={};self.persist()

    def patch(self,target,name,**args):
        p=patch.object(target,name,**args);p.start();self.addCleanup(p.stop)

    def persist(self):
        for name,raw in self.originals.items():(self.base/name).write_bytes(raw)
        hashes={name:calibration.ledger.sha(raw) for name,raw in self.originals.items()}
        self.manifest=calibration.ledger.encoded(dict(version='primary-client-calibration-originals-0.1.0',sourceCommit=self.source,artifactSha256=hashes))
        self.contract['calibrationManifestSha256']=calibration.ledger.sha(self.manifest)
        self.profile.update(calibrationRequestSha256=hashes['request-1.json'],calibrationReceiptSha256=hashes['receipt.json'])

    def verify(self):return calibration.verify(self.repository,self.manifest,self.profile,self.contract)

    def test_complete_local_originals_bind_without_actual_provider_certification(self):
        result=self.verify();self.assertEqual(result['status'],'original_local_calibration_matches')
        self.assertEqual(result['paidModelCalls'],0);self.assertFalse(result['certifiesProviderWireBodies'])

    def test_missing_changed_hash_or_unsafe_manifest_stops_before_unknown_read(self):
        (self.base/'config.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'bytes drift'):self.verify()
        self.persist();value=json.loads(self.manifest);value['artifactSha256']['codex-home/auth.json']='1'*64
        raw=calibration.ledger.encoded(value);self.contract['calibrationManifestSha256']=calibration.ledger.sha(raw)
        with patch.object(calibration.ledger,'read_regular',side_effect=AssertionError('unsafe read')),self.assertRaises(ValueError):
            calibration.verify(self.repository,raw,self.profile,self.contract)

    def test_rehashed_source_network_auth_config_and_context_drift_stop(self):
        baseline=copy.deepcopy(self.originals)
        for fault in ['source','network','auth','config','tools','supplement','caller','terminal']:
            self.originals=copy.deepcopy(baseline)
            if fault=='source':
                value=json.loads(self.originals['receipt.json']);value['sourceGuards']['before']['sourceSha256']['evals/skills/routing/production_canary_capture.py']='1'*64;name='receipt.json'
            elif fault in {'network','auth'}:
                value=json.loads(self.originals['invocation.json']);name='invocation.json'
                if fault=='network':value['argv'].remove('--unshare-net')
                else:value['argv'][1:1]=['--ro-bind','/unknown/auth.json','/unknown/auth.json']
            elif fault=='config':value=json.loads(self.originals['config.json']);value['model_providers.bitz_openai_http.requires_openai_auth']=True;name='config.json'
            elif fault=='terminal':value=json.loads(self.originals['runtime-result.json']);value['forcedShutdown']=True;name='runtime-result.json'
            else:
                value=json.loads(self.originals['request-1.json']);name='request-1.json'
                if fault=='tools':value['input'][0]['tools'].append(dict(name='extra'))
                elif fault=='supplement':value['input'][2]['content'][1]['text']='extra'
                else:value['input'][1]['content'][0]['text']='other caller'
            self.originals[name]=calibration.ledger.encoded(value);self.persist()
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify()

if __name__=='__main__':unittest.main()
