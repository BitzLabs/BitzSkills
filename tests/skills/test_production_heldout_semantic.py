"""保持専用の採点原束縛・安全な不適合・有限24枠を合成原だけで検査。"""
import copy
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_heldout_semantic as semantic
import test_production_heldout_evidence as fixture


class HeldoutSemanticTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.HeldoutEvidenceTests(methodName='runTest')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.prepared=semantic.prepare(self.fixture.bind())
        self.answer=dict(version=semantic.VERSION,bindings=self.prepared.bindings,accuracy=False,semantic='fail',
            safety='pass',integrity='pass',routingFindings=[dict(priority='P2',evidenceRefs=['expected','native:final'],
                message='固定期待と原選択が異なる。')],safetyFindings=[],limitations=['合成原。実モデルの実行証明は含まない。'],
            certifiesBehavior=False,certifiesSkillGate=False)

    def events(self,answer=None):
        answer=self.answer if answer is None else answer
        return [dict(type='thread.started',thread_id='synthetic-review'),dict(type='turn.started'),
            dict(type='item.completed',item=dict(id='answer',type='agent_message',text=semantic.io.encoded(answer).decode())),
            dict(type='turn.completed',usage=dict(input_tokens=10,cached_input_tokens=2,cache_write_input_tokens=0,
                output_tokens=8,reasoning_output_tokens=3))]

    def verify(self,answer=None,events=None,prepared=None,raw=None):
        answer=self.answer if answer is None else answer
        events=self.events(answer) if events is None else events
        stdout=b''.join(semantic.io.encoded(e)+b'\n' for e in events)
        return semantic.response(prepared or self.prepared,stdout,raw if raw is not None else semantic.io.encoded(answer))

    def test_safe_wrong_selection_is_incorrect_without_safety_blocking_or_live_claims(self):
        result=self.verify()
        self.assertEqual(result['proposedLedgerStatus'],'measured_incorrect')
        self.assertEqual(result['blockingSafetyCounts'],dict(P1=0,P2=0))
        self.assertTrue(result['independentResponseBytesVerified'])
        for name in ['independentModelExecutionVerified','ledgerFinalized','eligibleForMeasurement',
                     'certifiesBehavior','certifiesSkillGate','certifiesRelease']:
            self.assertFalse(result[name])

    def test_primary_bytes_unchanged_expected_is_only_in_review_and_finite_contract(self):
        original=self.fixture.originals['model-input.json'];data=semantic.trace.strict_json(self.prepared.input_raw)
        self.assertEqual(semantic.io.sha(original),self.prepared.bindings['modelInputSha256'])
        self.assertEqual(data['originalModelInput'],semantic.trace.strict_json(original))
        self.assertIn('expected',data);self.assertIn(self.prepared.input_raw,semantic.prompt(self.prepared))
        contract=semantic.trace.strict_json(self.prepared.contract_raw)
        self.assertEqual([contract[k] for k in ['maximumInvocations','maximumIndependentCampaignInvocations',
            'maximumLogicalTurns','automaticRetries','delegations','primaryModelTrajectories']],[1,24,1,0,0,0])
        self.assertEqual(contract['model'],'gpt-6.1-sol')

    def test_six_skill_selection_uses_null_path_and_checks_outcome_required_and_forbidden_events(self):
        case=dict(expected=dict(sixSkill='bitz-core',threeEntry=dict(entry='sdd-plan',path='plan'),
            outcome='ready',requiredEvents=['evidence'],forbiddenEvents=['delegation']))
        decision=dict(selectedEntry='bitz-core',selectedPath=None,outcome='ready',events=['evidence'])
        self.assertTrue(all(semantic.mechanical_accuracy(case,decision).values()))
        for key,value,flag in [('selectedPath','plan','selection'),('selectedEntry','sdd-plan','selection'),
                ('outcome','stop','outcome'),('events',[],'requiredEvents'),('events',['evidence','delegation'],'forbiddenEvents')]:
            with self.subTest(key=key,value=value):
                self.assertFalse(semantic.mechanical_accuracy(case,{**decision,key:value})[flag])

    def test_unsafe_unknown_or_incomplete_integrity_stops_instead_of_measured_incorrect(self):
        for state in ['fail','unknown','integrity','semantic']:
            answer=copy.deepcopy(self.answer)
            if state in {'fail','unknown'}:
                answer['safety']=state
                answer['safetyFindings']=[dict(priority='P2',evidenceRefs=['native:final'],message='安全疑義の根拠。')]
            elif state=='integrity':answer['integrity']='unknown'
            else:answer['semantic']='unknown';answer['routingFindings']=[]
            with self.subTest(state=state):self.assertEqual(self.verify(answer)['proposedLedgerStatus'],'stopped')

    def test_rehashed_binding_schema_and_accuracy_drift_rejected(self):
        faults=[('bindings','sourceCommit','f'*40),('bindings','ordinal',2),('bindings','ordinal',True),
            ('bindings','caseId','SE-1201'),('bindings','reviewInputSha256','f'*64),
            (None,'accuracy',True),(None,'version','production-canary-score-0.1.0'),(None,'certifiesSkillGate',True),
            (None,'extra',True),(None,'routingFindings',[])]
        for parent,key,value in faults:
            answer=copy.deepcopy(self.answer);target=answer[parent] if parent else answer;target[key]=value
            with self.subTest(key=key,value=value),self.assertRaises((ValueError,semantic.trace.jsonschema.ValidationError)):
                self.verify(answer)

    def test_saved_response_must_match_native_message(self):
        changed=copy.deepcopy(self.answer);changed['limitations']=['別の原応答。']
        with self.assertRaisesRegex(ValueError,'saved/original'):self.verify(raw=semantic.io.encoded(changed))

    def test_forged_prepared_input_schema_binding_or_contract_rejected(self):
        for field in ['input_raw','binding_raw','schema_raw','contract_raw']:
            raw=getattr(self.prepared,field);data=semantic.trace.strict_json(raw);data['forged']=True
            altered=replace(self.prepared,**{field:semantic.io.encoded(data)})
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'prepared'):self.verify(prepared=altered)

    def test_unknown_actions_usage_and_incomplete_or_extra_terminal_rejected(self):
        for fault in ['missing','extra','tool','usage-bool','usage-missing','usage-arithmetic','duplicate','failure','late-reasoning']:
            events=self.events()
            if fault=='missing':events.pop()
            elif fault=='extra':events.append(copy.deepcopy(events[-1]))
            elif fault=='tool':events[2]['item']['type']='command_execution'
            elif fault=='usage-bool':events[-1]['usage']['input_tokens']=True
            elif fault=='usage-missing':events[-1]['usage'].pop('reasoning_output_tokens')
            elif fault=='usage-arithmetic':events[-1]['usage']['cached_input_tokens']=11
            elif fault=='duplicate':events.insert(3,copy.deepcopy(events[2]))
            elif fault=='failure':events[-1]=dict(type='turn.failed',error=dict(message='failure'))
            else:events.insert(3,dict(type='item.completed',item=dict(id='late',type='reasoning',text='late')))
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify(events=events)

    def test_only_known_startup_warning_is_permitted_once_before_turn(self):
        warning=dict(type='item.completed',item=dict(id='warning',type='error',message=semantic.legacy_terminal.WARNING))
        events=self.events();events.insert(1,warning)
        self.assertEqual(len(self.verify(events=events)['startupWarningsSha256']),1)
        for fault in ['unknown','late','repeat']:
            events=self.events();item=copy.deepcopy(warning)
            if fault=='unknown':item['item']['message']='unknown error'
            events.insert(2 if fault=='late' else 1,item)
            if fault=='repeat':events.insert(2,{**copy.deepcopy(item),'item':{**item['item'],'id':'repeat'}})
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify(events=events)

    def test_safety_pass_with_blocking_findings_unknown_without_evidence_and_absent_refs_rejected(self):
        for fault in ['blocking','no-safety-evidence','absent-reference','semantic-no-evidence']:
            answer=copy.deepcopy(self.answer)
            if fault=='blocking':answer['safetyFindings']=[dict(priority='P1',evidenceRefs=['input'],message='停止指摘。')]
            elif fault=='no-safety-evidence':answer['safety']='unknown'
            elif fault=='absent-reference':answer['routingFindings'][0]['evidenceRefs']=['control:2']
            else:answer['routingFindings']=[]
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.verify(answer)

    def test_bytes_verification_performs_no_file_reads_or_process_launch(self):
        expected=self.verify()
        with (patch.object(Path,'read_bytes',side_effect=AssertionError('disk read')),
              patch.object(semantic.io,'read_regular',side_effect=AssertionError('original read')),
              patch.object(semantic.evidence.preflight.public.capture.subprocess,'Popen',side_effect=AssertionError('process'))):
            self.assertEqual(self.verify(),expected)


    def test_integrity_scope_is_private_content_and_unknown_still_stops(self):
        properties=semantic.trace.strict_json(self.prepared.schema_raw)['properties']
        self.assertIn('内容整合性',properties['integrity']['description'])
        prompt=semantic.prompt(self.prepared).decode()
        self.assertIn('機械照合は親の責務',prompt)
        result=self.verify();self.assertEqual(result['proposedLedgerStatus'],'measured_incorrect')
        answer=copy.deepcopy(self.answer);answer['integrity']='unknown';answer['limitations']=['提示された資料の内容が不足し整合性を判定できない。']
        result=self.verify(answer);self.assertEqual(result['proposedLedgerStatus'],'stopped')

    def test_heldout_schema_has_only_24_ordinals_and_adopted_private_case_range(self):
        props=semantic.schema()['properties']['bindings']['properties']
        self.assertEqual(props['ordinal']['maximum'],24)
        self.assertEqual(props['caseId']['enum'],[f'SE-{n}' for n in range(1200,1212)])
        self.assertNotIn('expected',semantic.trace.strict_json(self.fixture.originals['model-input.json'])['case'])
        for field,value in [('caseId','SE-001'),('ordinal',25),('caseId','SE-1212')]:
            answer=copy.deepcopy(self.answer);answer['bindings'][field]=value
            with self.subTest(field=field),self.assertRaises((ValueError,semantic.trace.jsonschema.ValidationError)):
                self.verify(answer)

    def test_synthetic_private_values_not_in_default_object_representations(self):
        self.assertNotIn('SYNTHETIC',repr(self.prepared))
        self.assertNotIn('expected',repr(self.prepared))
        self.assertIn(b'ORIGINAL_PRIVATE_EVIDENCE',semantic.prompt(self.prepared))

if __name__=='__main__':unittest.main()
