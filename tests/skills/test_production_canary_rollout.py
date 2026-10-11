"""一次の完整contextと複数rollout/raw/usageを公開合成記録で検証する。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_rollout as rollout
import production_ledger as ledger


class CanaryRolloutTests(unittest.TestCase):
    def test_reasoning_empty_content_omission_preserves_all_other_original_values(self):
        actual=dict(type='reasoning',id='reasoning-id',summary=[],encrypted_content='fixed opaque original')
        expected=dict(actual,content=[])
        self.assertTrue(rollout.original_item_equal(actual,expected))
        self.assertTrue(rollout.original_item_equal(expected,expected))
        self.assertNotIn('content',actual)
        for field,value in [('id','different'),('summary',[{'type':'summary_text','text':'changed'}]),
                            ('encrypted_content','changed'),('extra','unknown')]:
            with self.subTest(field=field):self.assertFalse(rollout.original_item_equal(dict(actual,**{field:value}),expected))
        for content in [None,'',{},False,[{'type':'reasoning_text','text':'nonempty'}]]:
            with self.subTest(content=content):self.assertFalse(rollout.original_item_equal(actual,dict(expected,content=content)))
        self.assertFalse(rollout.original_item_equal(expected,actual))
        self.assertFalse(rollout.original_item_equal(dict(actual,content=None),expected))
        self.assertFalse(rollout.original_item_equal(dict(actual,type='message'),dict(expected,type='message')))

    def fixture(self,profile='single-exec'):
        thread,turn='thread','turn'
        tools=[dict(type='namespace',name='functions',tools=[])];supplement=[dict(type='input_text',text=x) for x in ['synthetic permissions','synthetic mode']]
        profile_value=dict(version='primary-client-context-0.1.0',sdkVersion='0.160.1',codexVersion='codex-cli 0.160.1',systemSkillsDisabled=True,primaryModelTrajectories=0,paidModelCalls=0,
            certifiesProviderWireBodies=False,certifiesSkillGate=False,date='2026-10-11',supplementBlockCount=2,
            toolsValueSha256=rollout.sdk.digest(tools),supplementValueSha256=rollout.sdk.digest(supplement))
        sent=[{}, {},dict(params=dict(baseInstructions='fixed base',developerInstructions='fixed developer',cwd='/fixed/work')),
            dict(params=dict(threadId=thread,input=[dict(type='text',text='fixed public input')],outputSchema=dict(type='object')))]
        def message(i,role,content):
            meta = dict(content_item_kinds=['model.base_instructions']) if i=='base' else dict(turn_id=turn,create_time=1.0,content_item_kinds={
                'supp':['generic.developer_instructions','permissions.instructions','collaboration_mode.instructions'],
                'env':['environments.environment_context'],'user':['user.text']}[i])
            return dict(type='message',id=i,role=role,content=content,internal_chat_message_metadata_passthrough=meta)
        inputs=[dict(type='additional_tools',id='tools',role='developer',tools=tools),
            message('base','developer',[dict(type='input_text',text='fixed base')]),
            message('supp','developer',[dict(type='input_text',text='fixed developer'),*supplement]),
            message('env','user',[dict(type='input_text',text=rollout.sdk._diagnostic_environment('/fixed/work','2026-10-11',{'2026-10-11'}))]),
            message('user','user',[dict(type='input_text',text='fixed public input')])]
        meta=dict(installation_id='installation',session_id=thread,thread_id=thread,agent_name='/root',turn_id=turn,
            window_id=thread+':0',window_number=0,context_window_id='context-window',request_kind='turn',root_turn_id=turn,
            sandbox='seccomp',sandbox_mode='read-only',auto_review_enabled=False,node_repl_auto_review_required=True,
            node_repl_disabled=False,turn_started_at_unix_ms=1,analytics_enabled=True,model='gpt-6.1-sol',reasoning_effort='low')
        request=dict(model='gpt-6.1-sol',input=inputs,tool_choice='auto',parallel_tool_calls=False,
            reasoning=dict(effort='low',context='all_turns'),store=False,stream=True,include=['reasoning.encrypted_content'],
            prompt_cache_key=thread,text=dict(verbosity='low',format=dict(type='json_schema',strict=True,schema=dict(type='object'),name='codex_output_schema')),
            client_metadata={'x-codex-turn-metadata':json.dumps(meta),'x-codex-installation-id':'installation','thread_id':thread,'turn_id':turn,
                'root_turn_id':turn,'session_id':thread,'x-codex-window-id':thread+':0'})
        decision=dict(selectedEntry='bitz-core' if profile!='no-exec' else None,selectedPath='operate' if profile!='no-exec' else None,
            outcome='proceed' if profile!='no-exec' else 'not-applicable',events=[],rejectedEvents=[],readyClaimed=False,evidencePresent=False,reason='synthetic')
        names={'no-exec':(),'single-exec':('exec',),'two-exec':('exec','exec'),'exec-wait':('exec','wait')}[profile]
        native=dict(nativeChildIds=[] if profile=='no-exec' else ['child0','child1'],apiRequests=len(names)+1,parentCallIds=['parent'+str(i) for i in range(len(names))],profile=profile,decision=decision)
        host_events=[] if profile=='no-exec' else [dict(tool='list_resources',arguments={},result=dict(skills=[],resources=[],manifestSha256='1'*64)),
            dict(tool='read_resource',arguments={'path':'public/SKILL.md'},result=dict(path='public/SKILL.md',content='public body',sha256='2'*64,sourceCommit='b'*40))]
        received=[dict(method='turn/started',params=dict(threadId=thread,turn=dict(id=turn)))]
        def rawitem(x):
            x=copy.deepcopy(x);x.setdefault('internal_chat_message_metadata_passthrough',dict(turn_id=turn));received.append(dict(method='rawResponseItem/completed',params=dict(threadId=thread,turnId=turn,item=x)))
        for x in inputs[2:]:rawitem(x)
        payloads={};events=[]
        def reference(value,kind):
            number=len(payloads)+1;name=f'payloads/{number}.json';payloads[name]=ledger.encoded(value)
            return dict(raw_payload_id=f'raw_payload:{number}',kind=dict(type=kind),path=name)
        def event(value,inside=False):events.append(dict(schema_version=1,seq=len(events)+1,wall_time_unix_ms=len(events)+1,
            rollout_id=thread,thread_id=thread if inside else None,codex_turn_id=turn if inside else None,payload=value))
        event(dict(type='rollout_started',trace_id='trace',root_thread_id=thread))
        event(dict(type='thread_started',thread_id=thread,agent_path='/root',metadata_payload=reference(dict(thread_id=thread,agent_path='/root',task_name=None,nickname=None,agent_role=None,session_source='vscode',cwd='/fixed/work',rollout_path=None,model='gpt-6.1-sol',provider_name='bitz_openai_http',approval_policy='never',sandbox_policy='ReadOnly { network_access: false }'),'session_metadata')))
        event(dict(type='protocol_event_observed',event_type='session_configured',event_payload=reference(dict(type='session_configured',session_id=thread,thread_id=thread,model='gpt-6.1-sol',model_provider_id='bitz_openai_http',approval_policy='never',approvals_reviewer='user',cwd='/fixed/work',reasoning_effort='low',permission_profile=dict(type='managed',file_system=dict(type='restricted',entries=[dict(path=dict(type='special',value=dict(kind='root')),access='read')]),network='restricted')),'protocol_event')))
        event(dict(type='codex_turn_started',thread_id=thread,codex_turn_id=turn),True)
        event(dict(type='protocol_event_observed',event_type='turn_started',event_payload=reference(dict(type='task_started',turn_id=turn,root_turn_id=turn,started_at=1,model_context_window=1000,collaboration_mode_kind='default'),'protocol_event')))
        total={k:0 for k in rollout.USAGE.values()}
        for i in range(len(names)+1):
            prior=0 if i==0 else len(host_events) if len(names)==1 else i
            sources=[dict(server_name='production-routing',tool_name=h['tool'],first_turn_id=turn) for h in host_events[:prior]]
            request['client_metadata'].update(guardian_credits_requested='true',mcp_attribution=json.dumps(dict(status='complete',sources=sources) if sources else dict(status='none')))
            call='inference'+str(i);response_id='response'+str(i)
            event(dict(type='inference_started',inference_call_id=call,thread_id=thread,codex_turn_id=turn,model='gpt-6.1-sol',provider_name='OpenAI',
                request_payload=reference(copy.deepcopy(request),'inference_request')),True)
            if i<len(names):
                name=names[i];output=dict(type='custom_tool_call' if name=='exec' else 'function_call',id='control'+str(i),call_id='parent'+str(i),
                    name=name,namespace='functions',**({'input':'text(await tools.read({}));'} if name=='exec' else {'arguments':'{"cell_id":"cell"}'}))
            else:output=dict(type='message',id='final',role='assistant',content=[dict(type='output_text',text=json.dumps(decision))],phase='final_answer')
            usage=dict(input_tokens=10,cached_input_tokens=0,cache_write_input_tokens=0,output_tokens=2,reasoning_output_tokens=0,total_tokens=12)
            response=dict(response_id=response_id,upstream_request_id=None,token_usage=usage,output_items=[output])
            event(dict(type='inference_completed',inference_call_id=call,response_id=response_id,upstream_request_id=None,response_payload=reference(response,'inference_response')),True)
            rawitem(output);last=rollout.counters(usage,snake=True)
            received.append(dict(method='rawResponse/completed',params=dict(threadId=thread,turnId=turn,responseId=response_id,usage=last,usageMetadata=None)))
            for k,n in last.items():total[k]+=n
            received.append(dict(method='thread/tokenUsage/updated',params=dict(threadId=thread,turnId=turn,tokenUsage=dict(last=last,total=dict(total),modelContextWindow=1000))))
            request=copy.deepcopy(request);request['input'].append(output)
            if i<len(names):
                for child in (['child0','child1'] if len(names)==1 else ['child'+str(i)]):
                    for method in ['item/started','item/completed']:
                        received.append(dict(method=method,params=dict(threadId=thread,turnId=turn,item=dict(type='mcpToolCall',id=child))))
                result=dict(type=output['type']+'_output',id='result'+str(i),call_id='parent'+str(i),output=[dict(type='input_text',text=json.dumps([e['result'] for e in (host_events if len(names)==1 else host_events[i:i+1])]))])
                request['input'].append(result);rawitem(result)
        received.append(dict(method='item/completed',params=dict(item=dict(type='agentMessage',id='final',phase='final_answer',text=json.dumps(decision)))))
        event(dict(type='codex_turn_ended',codex_turn_id=turn,status='completed'),True)
        event(dict(type='protocol_event_observed',event_type='turn_complete',event_payload=reference(dict(type='task_complete',turn_id=turn,last_agent_message=json.dumps(decision),started_at=1,completed_at=2,duration_ms=1,time_to_first_token_ms=1),'protocol_event')))
        event(dict(type='protocol_event_observed',event_type='shutdown_complete',event_payload=reference(dict(type='shutdown_complete'),'protocol_event')))
        received.append(dict(method='turn/completed',params=dict(threadId=thread,turn=dict(id=turn))))
        event(dict(type='thread_ended',thread_id=thread,status='completed'));event(dict(type='rollout_ended',status='completed'))
        manifest=dict(schema_version=1,trace_id='trace',root_thread_id=thread,started_at_unix_ms=events[0]['wall_time_unix_ms'],raw_event_log='trace.jsonl',payloads_dir='payloads',rollout_id=thread)
        return dict(manifest=manifest,events=events,payloads=payloads,sent=sent,received=received,native=native,context_profile=profile_value,host_events=host_events)

    def check(self,value):
        return rollout.correlate(ledger.encoded(value['manifest']),b''.join(ledger.encoded(e)+b'\n' for e in value['events']),
            value['payloads'],value['sent'],value['received'],value['native'],value['context_profile'],host_events=value['host_events'])

    def test_no_exec_raw_reasoning_omission_correlates_without_discarding_nonempty_values(self):
        value=self.fixture('no-exec')
        reasoning=dict(type='reasoning',id='reasoning-id',summary=[],encrypted_content='fixed original',content=[])
        self.alter_payload(value,'inference_completed',lambda x:x['output_items'].insert(0,copy.deepcopy(reasoning)))
        index=next(i for i,f in enumerate(value['received']) if f.get('method')=='rawResponseItem/completed' and f['params']['item'].get('id')=='final')
        raw=dict(reasoning);raw.pop('content');raw['internal_chat_message_metadata_passthrough']=dict(turn_id='turn')
        value['received'].insert(index,dict(method='rawResponseItem/completed',params=dict(threadId='thread',turnId='turn',item=raw)))
        before=copy.deepcopy(value);result=self.check(value)
        self.assertEqual(result['inferences'],1);self.assertTrue(result['rawPayloadCorrelationVerified']);self.assertEqual(value,before)
        for fault in ['nonempty','null','encrypted','missing-summary','unknown']:
            changed=copy.deepcopy(value)
            if fault=='nonempty':self.alter_payload(changed,'inference_completed',lambda x:x['output_items'][0].update(content=[dict(type='reasoning_text',text='unmatched')]))
            elif fault=='null':self.alter_payload(changed,'inference_completed',lambda x:x['output_items'][0].update(content=None))
            elif fault=='encrypted':changed['received'][index]['params']['item']['encrypted_content']='changed'
            elif fault=='missing-summary':changed['received'][index]['params']['item'].pop('summary')
            else:changed['received'][index]['params']['item']['unknown']='extra'
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'raw item payload binding'):self.check(changed)

    def test_fixed_cli_seven_manifest_fields_bind_to_original_start_and_reject_drift(self):
        self.check(self.fixture())
        for key,value in [('trace_id','another'),('started_at_unix_ms',2),('started_at_unix_ms',True),
                          ('started_at_unix_ms',1.0),('schema_version',True),('extra','unknown')]:
            fixture=self.fixture();fixture['manifest'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.check(fixture)
        for key in ['trace_id','started_at_unix_ms']:
            fixture=self.fixture();fixture['manifest'].pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError):self.check(fixture)
        for first in [None,[],0]:
            fixture=self.fixture();fixture['events'][0]=first
            with self.subTest(first=first),self.assertRaises(ValueError):self.check(fixture)

    def alter_payload(self,value,kind,change,index=0):
        events=[e for e in value['events'] if e['payload']['type']==kind]
        ref=events[index]['payload']['request_payload' if kind=='inference_started' else 'response_payload'];p=ref['path']
        item=json.loads(value['payloads'][p]);change(item);value['payloads'][p]=ledger.encoded(item)

    def test_four_finite_profiles_keep_original_values_and_do_not_certify(self):
        for profile in ['no-exec','single-exec','two-exec','exec-wait']:
            value=self.fixture(profile);before=copy.deepcopy(value);result=self.check(value)
            self.assertEqual(result['inferences'],value['native']['apiRequests']);self.assertTrue(result['rawPayloadCorrelationVerified'])
            self.assertFalse(result['eligibleForMeasurement']);self.assertFalse(result['certifiesProviderWireBodies']);self.assertEqual(value,before)

    def test_real_guardian_and_mcp_attribution_are_exact_and_ordered(self):
        value=self.fixture('two-exec')
        requests=[json.loads(value['payloads'][e['payload']['request_payload']['path']]) for e in value['events'] if e['payload']['type']=='inference_started']
        for names in [[],['list_resources'],['list_resources','read_resource']]:
            request=copy.deepcopy(requests[len(names)])
            expected=dict(status='complete',sources=[dict(server_name='production-routing',tool_name=n,first_turn_id='turn') for n in names]) if names else dict(status='none')
            request['client_metadata'].update(guardian_credits_requested='true',mcp_attribution=json.dumps(expected))
            rollout.request_policy(request,value['sent'],thread='thread',turn='turn',mcp_sources=names)
            for fault in ['guardian-type','guardian-value','missing','unknown','status','source','order']:
                changed=copy.deepcopy(request);meta=changed['client_metadata'];attrib=copy.deepcopy(expected)
                if fault=='guardian-type':meta['guardian_credits_requested']=True
                elif fault=='guardian-value':meta['guardian_credits_requested']='false'
                elif fault=='missing':del meta['mcp_attribution']
                elif fault=='unknown':meta['unknown']='x'
                elif fault=='status':attrib['status']='unknown'
                elif fault=='source':attrib['sources']=[dict(server_name='other',tool_name='unknown',first_turn_id='turn')]
                elif len(names)==2:attrib['sources'].reverse()
                else:continue
                if fault in ['status','source','order']:meta['mcp_attribution']=json.dumps(attrib)
                with self.subTest(names=names,fault=fault),self.assertRaises(ValueError):
                    rollout.request_policy(changed,value['sent'],thread='thread',turn='turn',mcp_sources=names)

    def test_local_calibration_metadata_profile_cannot_be_selected_by_primary(self):
        value=self.fixture('no-exec')
        e=next(e for e in value['events'] if e['payload']['type']=='inference_started')
        request=json.loads(value['payloads'][e['payload']['request_payload']['path']])
        for key in ['mcp_attribution','guardian_credits_requested']:del request['client_metadata'][key]
        rollout.request_policy(request,value['sent'],thread='thread',turn='turn',profile='local-calibration')
        with self.assertRaisesRegex(ValueError,'client metadata fields'):
            rollout.request_policy(request,value['sent'],thread='thread',turn='turn')
        for profile in ['unknown',None,True]:
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                rollout.request_policy(request,value['sent'],thread='thread',turn='turn',profile=profile)

    def test_removing_attribution_from_every_request_cannot_select_legacy_contract(self):
        value=self.fixture('two-exec')
        for e in value['events']:
            if e['payload']['type']=='inference_started':
                path=e['payload']['request_payload']['path'];body=json.loads(value['payloads'][path])
                for key in ['mcp_attribution','guardian_credits_requested']:del body['client_metadata'][key]
                value['payloads'][path]=ledger.encoded(body)
        with self.assertRaisesRegex(ValueError,'client metadata fields'):self.check(value)

    def test_discovery_catalog_is_fixed_and_only_once_before_first_host_body(self):
        catalog=[dict(name='mcp__production_routing__list_resources',description='固定した製品6スキルの説明と読取り可能な資源の相対パスを一覧する。\n\nexec tool declaration:\n```ts\ndeclare const tools: { mcp__production_routing__list_resources(args: {}): Promise<CallToolResult>; };\n```'),
            dict(name='mcp__production_routing__read_resource',description='一覧にある資源1件だけを固定hashに照合して読む。\n\nexec tool declaration:\n```ts\ndeclare const tools: { mcp__production_routing__read_resource(args: { path: string; }): Promise<CallToolResult>; };\n```')]
        self.assertEqual(rollout.sdk.digest(catalog),rollout.DISCOVERY_VALUE_SHA256)
        host=self.fixture()['host_events'][0]['result']
        blocks=[dict(type='input_text',text=json.dumps(v)) for v in [catalog,host]]
        before=copy.deepcopy(blocks)
        self.assertEqual(rollout.parent_bodies(blocks,[host],allow_discovery=True),[rollout.sdk.digest(host)])
        self.assertEqual(blocks,before)
        for fault in ['not-first','duplicate','changed','unknown','default']:
            changed=copy.deepcopy(blocks)
            if fault=='not-first':changed.reverse()
            elif fault=='duplicate':changed.insert(0,copy.deepcopy(changed[0]))
            elif fault=='changed':altered=copy.deepcopy(catalog);altered[0]['description']+='changed';changed[0]['text']=json.dumps(altered)
            elif fault=='unknown':altered=copy.deepcopy(catalog);altered[0]['unknown']=True;changed[0]['text']=json.dumps(altered)
            with self.subTest(fault=fault),self.assertRaises(ValueError):rollout.parent_bodies(changed,[host],allow_discovery=fault!='default')

    def test_initial_context_or_request_policy_injection_stops(self):
        faults=[lambda r:r['input'].append(copy.deepcopy(r['input'][-1])),lambda r:r['input'][2]['content'][1].update(text='injected'),
            lambda r:r['input'][0]['tools'].append(dict(name='extra')),lambda r:r['input'][3]['content'][0].update(text='wrong environment'),
            lambda r:r['input'][4]['content'][0].update(text='wrong user'),lambda r:r.update(parallel_tool_calls=True),
            lambda r:r['text']['format'].update(schema={}),lambda r:r.update(model='other')]
        for change in faults:
            value=self.fixture();self.alter_payload(value,'inference_started',change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(value)

    def test_missing_unknown_out_of_order_or_unreferenced_rollout_stops(self):
        for fault in ['missing','unknown','order','unreferenced','reference','bool','wrongturn','negativewall']:
            value=self.fixture()
            if fault=='missing':value['events'].pop()
            elif fault=='unknown':value['events'][3]['payload']['type']='inference_failed'
            elif fault=='order':value['events'][3],value['events'][4]=value['events'][4],value['events'][3]
            elif fault=='unreferenced':value['payloads']['payloads/999.json']=b'{}'
            elif fault=='reference':next(e for e in value['events'] if e['payload']['type']=='inference_started')['payload']['request_payload']['path']='../secret'
            elif fault=='bool':value['events'][0]['schema_version']=True
            elif fault=='negativewall':value['events'][0]['wall_time_unix_ms']=-1
            else:next(e for e in value['events'] if e['payload']['type']=='inference_started')['codex_turn_id']='another'
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.check(value)

    def test_raw_usage_cumulative_usage_and_counter_types_stop(self):
        for fault in ['raw','total','bool','negative','missing','overflow','window','nullwindow']:
            value=self.fixture('two-exec')
            if fault=='raw':next(f for f in value['received'] if f.get('method')=='rawResponse/completed')['params']['responseId']='another'
            elif fault=='total':[f for f in value['received'] if f.get('method')=='thread/tokenUsage/updated'][-1]['params']['tokenUsage']['total']['totalTokens']-=1
            elif fault in {'window','nullwindow'}:next(f for f in value['received'] if f.get('method')=='thread/tokenUsage/updated')['params']['tokenUsage']['modelContextWindow']=1 if fault=='window' else None
            elif fault=='missing':value['received']=[f for f in value['received'] if f.get('method')!='thread/tokenUsage/updated']
            elif fault=='overflow':value['received'][1]['params']['item']['internal_chat_message_metadata_passthrough']['create_time']=float('inf')
            else:self.alter_payload(value,'inference_completed',lambda r:r['token_usage'].update(total_tokens=True if fault=='bool' else -1))
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.check(value)

    def test_protocol_policy_metadata_usage_lifecycle_and_native_child_order_stop(self):
        for fault in ['protocol','session','missingprotocol','metadata','lateusage','childorder']:
            value=self.fixture()
            if fault=='protocol':
                e=next(e for e in value['events'] if e['payload'].get('event_type')=='turn_started')
                p=e['payload']['event_payload']['path'];body=json.loads(value['payloads'][p]);body['type']='exec_command';value['payloads'][p]=ledger.encoded(body)
            elif fault=='session':
                p=value['events'][1]['payload']['metadata_payload']['path'];body=json.loads(value['payloads'][p]);body['approval_policy']='on-request';value['payloads'][p]=ledger.encoded(body)
            elif fault=='missingprotocol':
                e=next(e for e in value['events'] if e['payload'].get('event_type')=='turn_started');value['events'].remove(e);del value['payloads'][e['payload']['event_payload']['path']]
                for i,e in enumerate(value['events'],1):e['seq']=i
            elif fault=='metadata':self.alter_payload(value,'inference_started',lambda r:r['input'][1]['internal_chat_message_metadata_passthrough'].update(turn_id='other'))
            elif fault=='lateusage':
                f=next(f for f in value['received'] if f.get('method')=='thread/tokenUsage/updated');value['received'].remove(f);value['received'].append(f)
            else:
                f=next(f for f in value['received'] if f.get('method')=='item/started' and f['params']['item'].get('type')=='mcpToolCall');value['received'].remove(f);value['received'].insert(1,f)
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.check(value)

    def test_control_parent_unknown_action_history_and_final_identity_stop(self):
        faults=[('inference_completed',lambda r:r['output_items'][0].update(call_id='other'),0),
            ('inference_completed',lambda r:r['output_items'][0].update(type='local_shell_call'),0),
            ('inference_started',lambda r:r['input'][0].update(id='changed'),1),
            ('inference_started',lambda r:r['input'][-1].update(call_id='changed'),1),
            ('inference_completed',lambda r:r['output_items'][0]['content'][0].update(text='{}'),1)]
        for kind,change,index in faults:
            value=self.fixture();self.alter_payload(value,kind,change,index)
            with self.subTest(kind=kind,index=index),self.assertRaises(ValueError):self.check(value)
        value=self.fixture();next(f for f in value['received'] if f.get('method')=='item/completed')['params']['item']['id']='another'
        with self.assertRaises(ValueError):self.check(value)

    def test_rehashed_parent_output_without_host_change_stops(self):
        for body in ['forged text', json.dumps({'path':'public/SKILL.md','content':'public body'}),
                     json.dumps([self.fixture()['host_events'][0]['result']])]:
            value=self.fixture()
            self.alter_payload(value,'inference_started',lambda r:r['input'][-1]['output'][0].update(text=body),1)
            for frame in value['received']:
                item=frame.get('params',{}).get('item',{})
                if item.get('type')=='custom_tool_call_output':item['output'][0]['text']=body
            with self.subTest(body=body),self.assertRaises(ValueError):self.check(value)

    def test_wrapped_full_host_json_accepts_and_forged_extra_or_duplicate_rejects(self):
        expected=[e['result'] for e in self.fixture()['host_events']]
        wrapped=dict(listed=dict(content=[dict(type='text',text=json.dumps(expected[0]))],isError=False),
                     read=dict(content=[dict(type='text',text=json.dumps(expected[1]))],isError=False))
        blocks=[dict(type='input_text',text='Script completed\nWall time 0.0 seconds\nOutput:\n'),dict(type='input_text',text=json.dumps(wrapped))]
        self.assertEqual(len(rollout.parent_bodies(blocks,expected)),2)
        for extra in [expected[1],dict(expected[1],content='forged'),dict(host=expected,extra=dict(instruction='unbound'))]:
            bad=copy.deepcopy(blocks);bad.append(dict(type='input_text',text=json.dumps(extra)))
            with self.assertRaises(ValueError):rollout.parent_bodies(bad,expected)


if __name__=='__main__':unittest.main()
