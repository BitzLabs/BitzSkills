"""独立採点の原入力・予約・終端・使用量・親確定を公開合成で検証する。課金0。"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_score as score
import test_production_canary_review as primary_fixture


class CanaryScoreTests(unittest.TestCase):
    def setUp(self):
        self.primary=primary_fixture.CanaryCompleteReviewTests(methodName='runTest')
        cases=json.loads((ROOT/score.evidence.CASES).read_bytes())
        cases[0].update(prompt='公開合成のSDD計画を作成して',expected=dict(sixSkill='sdd-plan',outcome='proceed'))
        self.primary.cases_raw=score.ledger.encoded(cases)
        self.primary.setUp();self.addCleanup(self.primary.doCleanups)
        self.capture=self.primary.capture;self.repository=self.capture.repository
        for name in [score.CONTRACT,score.SCHEMA,'evals/skills/sol-authorization.json']:
            self.capture.git_raws[name]=(ROOT/name).read_bytes()
        self.context=self.primary.loaded();self.prepared=score.prepare(self.repository,self.context)
        self.result=dict(self.prepared.bindings,semantic='pass',safety='pass',verdict='pass',findings=[],
            limitations=['public routing only'],certifiesBehavior=False,certifiesSkillGate=False)
        self.base=self.repository/score.OUTPUT/'attempt-0001'

    def trace(self,result=None):
        result=self.result if result is None else result
        return [dict(type='thread.started',thread_id='independent-original-thread'),dict(type='turn.started'),
            dict(type='item.completed',item=dict(id='score-final',type='agent_message',text=json.dumps(result))),
            dict(type='turn.completed',usage=dict(input_tokens=10,cached_input_tokens=2,cache_write_input_tokens=0,output_tokens=5,reasoning_output_tokens=1))]

    def check(self,events,result=None):
        return score.response(b''.join(score.ledger.encoded(e)+b'\n' for e in events),score.ledger.encoded(self.result if result is None else result),
            self.prepared.schema_raw,self.prepared.bindings)

    def create_review(self,result=None):
        result=self.result if result is None else result
        reservation=self.capture.instance.reserve_independent_review(1,self.prepared.bindings['reviewInputSha256'])
        self.base.mkdir(parents=True)
        for name in score.OPAQUE:(self.base/name).mkdir()
        enc=score.ledger.encoded;prompt=score.prompt(self.prepared)
        self.originals={'contract.json':self.prepared.contract_raw,'review-input.json':self.prepared.input_raw,'prompt.txt':prompt,
            'schema.json':self.prepared.schema_raw,'reservation.json':enc(reservation),'config.json':enc(score.config_for(self.base)),
            'invocation.json':enc(dict(argv=score.command_for(self.base,self.capture.bound.contract),sourceCommit=self.capture.source,model='gpt-6.1-sol',
                maximumInvocations=1,promptSha256=score.ledger.sha(prompt),reviewInputSha256=self.prepared.bindings['reviewInputSha256'])),
            'trace.jsonl':b''.join(enc(e)+b'\n' for e in self.trace(result)),'stderr.bin':b'','response.json':enc(result)}
        runtime=score.capture.fixed_runtime.verify(self.capture.git_raws[score.capture.fixed_runtime.MANIFEST],self.capture.bound.contract)
        self.receipt=dict(status='independent_score_captured',sourceCommit=self.capture.source,attempt=self.capture.attempt,model='gpt-6.1-sol',scope=score.SCOPE,
            independentInvocations=1,consumedReservations=1,primaryModelTrajectories=0,automaticRetries=0,exitCode=0,timedOut=False,elapsedSeconds=1,errorType=None,
            sourceGuards=dict.fromkeys(['before','invoke','after'],self.capture.source_evidence),runtimeGuards=dict.fromkeys(['before','invoke','after'],runtime),
            artifactSha256={},usage=self.trace()[-1]['usage'],acceptedStartupWarningHashes=[],eligibleForMeasurement=False,certifiesBehavior=False,certifiesSkillGate=False)
        self.persist()

    def persist(self):
        for name,raw in self.originals.items():(self.base/name).write_bytes(raw)
        self.receipt['artifactSha256']={name:score.ledger.sha(raw) for name,raw in self.originals.items()}
        (self.base/'receipt.json').write_bytes(score.ledger.encoded(self.receipt))

    def test_prepare_binds_expected_and_original_public_bodies_without_ledger_mutation(self):
        data=json.loads(self.prepared.input_raw)
        self.assertEqual(data['expected'],{'sixSkill':'sdd-plan','outcome':'proceed'})
        self.assertEqual(data['originalHost'],self.primary.fixture.trace.fixture.host)
        self.assertEqual(data['originalModelInput'],json.loads(self.context.originals['model-input.json']))
        self.assertEqual(self.prepared.bindings['reviewInputSha256'],score.ledger.sha(self.prepared.input_raw))
        self.assertFalse((self.capture.storage/'independent-0001.json').exists())
        self.assertEqual(self.check(self.trace())[0],self.result)

    def test_unknown_action_retry_missing_terminal_usage_type_and_binding_reject(self):
        for fault in ['tool','retry','missing','bool','usage','binding','float','late','mismatch']:
            events=self.trace();result=copy.deepcopy(self.result)
            if fault=='tool':events.insert(2,dict(type='item.started',item=dict(id='tool',type='command_execution')))
            elif fault=='retry':events.insert(2,dict(type='turn.started'))
            elif fault=='missing':events.pop()
            elif fault=='bool':events[-1]['usage']['input_tokens']=True
            elif fault=='usage':events[-1]['usage']['cached_input_tokens']=11
            elif fault=='late':events.append(dict(type='turn.started'))
            else:
                if fault=='binding':result['reviewInputSha256']='1'*64
                elif fault=='float':result['attempt']=1.0
                else:result['semantic']='fail';result['findings']=[dict(priority='P2',evidenceRefs=['input'],message='failure')];result['verdict']='findings'
                if fault!='mismatch':events[2]['item']['text']=json.dumps(result)
            with self.subTest(fault=fault),self.assertRaises((ValueError,score.trace.jsonschema.exceptions.ValidationError)):self.check(events,result)

    def test_original_review_is_read_only_until_parent_finalize(self):
        self.create_review()
        with patch.object(score.ledger.Ledger,'record_verified_review',side_effect=AssertionError('unexpected finalize')):
            _,result,_=score.load_review(self.repository,self.context,self.prepared)
        self.assertEqual(result,self.result);self.assertFalse((self.capture.storage/'review-0001.json').exists())
        final=score.finalize(self.repository,self.capture.source,1)
        self.assertTrue(final['eligibleForMeasurement']);self.assertFalse(final['certifiesSkillGate'])
        record=score.ledger.read_owned(self.capture.storage/'review-0001.json');self.assertEqual(record['status'],'accepted')
        self.assertEqual(self.capture.instance.reserve()['attempt'],2)

    def test_rehashed_fixed_input_usage_source_and_evidence_reference_drift_reject(self):
        self.create_review();baseline=copy.deepcopy(self.originals);receipt=copy.deepcopy(self.receipt)
        for fault in ['input','argv','usage','source','reference','unsafe']:
            self.originals=copy.deepcopy(baseline);self.receipt=copy.deepcopy(receipt)
            if fault=='input':self.originals['review-input.json']+=b' '
            elif fault=='argv':
                value=json.loads(self.originals['invocation.json']);value['argv'].remove('--tmpfs');self.originals['invocation.json']=score.ledger.encoded(value)
            elif fault=='usage':self.receipt['usage']['input_tokens']=20
            elif fault=='source':self.receipt['sourceGuards']['after']['sourceCommit']='a'*40
            elif fault=='reference':
                result=dict(self.result,verdict='findings',findings=[dict(priority='P3',evidenceRefs=['control:2'],message='nonexistent')])
                self.originals['response.json']=score.ledger.encoded(result);self.originals['trace.jsonl']=b''.join(score.ledger.encoded(e)+b'\n' for e in self.trace(result))
            self.persist()
            if fault=='unsafe':
                self.receipt['artifactSha256']['codex-home/auth.json']='1'*64;(self.base/'receipt.json').write_bytes(score.ledger.encoded(self.receipt))
            with self.subTest(fault=fault),self.assertRaises(ValueError):score.load_review(self.repository,self.context,self.prepared)
        self.assertFalse((self.capture.storage/'review-0001.json').exists())

    def test_semantic_failure_is_final_stop_and_blocks_next_primary_or_review(self):
        result=dict(self.result,semantic='fail',verdict='findings',findings=[dict(priority='P2',evidenceRefs=['input'],message='synthetic mismatch')])
        self.create_review(result);final=score.finalize(self.repository,self.capture.source,1)
        self.assertFalse(final['eligibleForMeasurement']);self.assertEqual(final['severityCounts'],dict(P1=0,P2=1))
        self.assertEqual(score.ledger.read_owned(self.capture.storage/'review-0001.json')['status'],'stopped')
        with self.assertRaises(ValueError):self.capture.instance.reserve()
        with self.assertRaises(ValueError):self.capture.instance.reserve_independent_review(1,self.prepared.bindings['reviewInputSha256'])

    def test_single_reserved_run_uses_exact_prompt_and_preserves_real_cli_trace(self):
        from types import SimpleNamespace
        original_git=score.guard.git
        def git(repository,*args):
            if args==('status','--porcelain'):return b''
            if args==('rev-parse','HEAD'):return self.capture.source.encode()+b'\n'
            return original_git(repository,*args)
        def invoke(command,**kwargs):
            self.assertEqual(command,score.command_for(self.base,self.capture.bound.contract))
            (self.base/'response.json').write_bytes(score.ledger.encoded(self.result))
            def communicate(raw,timeout):
                self.assertEqual(raw,score.prompt(self.prepared));self.assertEqual(timeout,300)
                return b''.join(score.ledger.encoded(e)+b'\n' for e in self.trace()),b'original public stderr'
            return SimpleNamespace(returncode=0,pid=123456,communicate=communicate)
        original_is_file=Path.is_file
        def is_file(path):return True if str(path)=='/home/hide/.codex/auth.json' else original_is_file(path)
        with patch.object(score,'ROOT',self.repository),patch.object(score.guard,'git',side_effect=git),\
             patch.object(Path,'is_file',is_file),patch.object(score.subprocess,'Popen',side_effect=invoke) as start:
            result=score.run(self.capture.source,1)
        self.assertEqual(result['status'],'independent_score_captured');self.assertEqual(start.call_count,1)
        self.assertFalse((self.capture.storage/'review-0001.json').exists())
        loaded=score.load_review(self.repository,self.context,self.prepared)
        self.assertEqual(loaded[1],self.result)
        self.assertEqual((self.base/'stderr.bin').read_bytes(),b'original public stderr')
        with self.assertRaises(FileExistsError):self.capture.instance.reserve_independent_review(1,self.prepared.bindings['reviewInputSha256'])

    def test_policy_and_command_keep_one_sol_context_tools_disabled_and_no_repo_mount(self):
        value=json.loads(self.prepared.contract_raw);score.policy(value)
        for name,v in [('maximumInvocations',True),('timeoutSeconds',301),('automaticRetries',1),('model','gpt-6-astra')]:
            bad=dict(value);bad[name]=v
            with self.subTest(name=name),self.assertRaises(ValueError):score.policy(bad)
        command=score.command_for(self.base,self.capture.bound.contract)
        self.assertIn('--ignore-user-config',command);self.assertNotIn(str(self.repository),command)
        config=score.config_for(self.base)
        for name in ['code_mode','code_mode_host','multi_agent','shell_tool','apps']:self.assertIs(config['features.'+name],False)
        self.assertEqual(config['model_providers.bitz_openai_http.request_max_retries'],0)
        self.assertNotIn('model_providers.bitz_openai_http.base_url',config)

if __name__=='__main__':unittest.main()
