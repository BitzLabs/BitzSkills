"""操作診断の原通信・隔離mount・有限条件を検査する。実モデルは使わない。"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_operation_probe as probe


class ProductionOperationProbeTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / probe.CONTRACT).read_bytes())
        self.base = ROOT / '.venv' / 'operation-test'

    def test_only_required_files_and_snapshot_are_bound_back(self):
        args = probe.namespace(self.base, self.contract)
        mounts = [args[i + 1:i + 3] for i, arg in enumerate(args) if arg == '--ro-bind']
        self.assertNotIn([str(ROOT), str(ROOT)], mounts)
        self.assertIn(['/home',], [[args[i+1]] for i,arg in enumerate(args) if arg=='--tmpfs'])
        self.assertIn([str(ROOT / self.contract['snapshotRelativePath'])] * 2, mounts)
        self.assertEqual(args.count('--bind'), 1)
        self.assertIn('--unshare-net', args)
        self.assertNotIn(str(ROOT / '.spec'), args)
        self.assertNotIn(str(ROOT / 'tests'), args)

    def test_tool_reply_is_a_real_custom_call_and_not_an_assistant_claim(self):
        events = [json.loads(line[6:]) for line in probe.tool_reply('inventory', self.base).decode().splitlines() if line.startswith('data: ')]
        item = events[1]['item']
        self.assertEqual(item['type'], 'custom_tool_call')
        self.assertEqual(item['name'], 'exec')
        self.assertEqual(item['namespace'], 'functions')
        self.assertIn('ALL_TOOLS', item['input'])

    def test_read_script_uses_discovery_before_selected_body(self):
        code = probe.program('read', self.base)
        self.assertLess(code.index('__list_resources'), code.index('__read_resource'))
        self.assertIn('sdd-plan', code)
        self.assertNotIn('expected', code)

    def test_negative_scripts_save_success_and_failure_without_presuming_rejection(self):
        for name in ['shell-denied', 'patch-denied', 'web-denied', 'agent-denied']:
            code = probe.program(name, self.base)
            self.assertIn('returned:true', code)
            self.assertIn('returned:false', code)
        self.assertIn('.spec/expected-canary.txt', probe.program('path-denied', self.base))
        with self.assertRaises(ValueError):
            probe.program('other', self.base)

    def test_user_input_is_a_separate_native_function_call(self):
        events = [json.loads(line[6:]) for line in probe.tool_reply('user-input-stop', self.base).decode().splitlines() if line.startswith('data: ')]
        self.assertEqual(events[1]['item']['type'], 'function_call')
        self.assertEqual(events[1]['item']['name'], 'request_user_input_async')
        arguments = json.loads(events[1]['item']['arguments'])
        self.assertEqual(arguments, {'questions': [{'title': 'LOCAL_SIMULATION_ONLY', 'options': ['Local A', 'Local B']}]})

    def test_outputs_must_belong_to_the_scripted_call(self):
        obj = {'kind': 'inventory', 'names': ['read']}
        item = {'type': 'custom_tool_call_output', 'call_id': 'probe-call', 'output': 'runtime preamble\n' + json.dumps(obj)}
        self.assertEqual(probe.output_objects({'input': [item]}), [obj])
        self.assertEqual(probe.output_objects({'input': [{**item, 'call_id': 'other'}]}), [])
        self.assertEqual(probe.output_objects({'input': [{'type': 'message', 'content': json.dumps(obj)}]}), [])

    def test_structured_content_and_corrupt_output_are_handled(self):
        item = {'type': 'custom_tool_call_output', 'call_id': 'probe-call', 'output': [{'type': 'text', 'text': '{"kind":"read"}'}]}
        self.assertEqual(probe.output_objects({'input': [item]}), [{'kind': 'read'}])
        item['output'] = 'not JSON'
        self.assertEqual(probe.output_objects({'input': [item]}), [])

    def test_scenarios_outputs_and_budget_are_finite(self):
        self.assertEqual(set(self.contract['outputLabels']), {'read', 'user-input-stop'})
        self.assertTrue(set(self.contract['outputLabels']) <= set(probe.SCENARIOS))
        self.assertEqual(len(set(self.contract['outputLabels'].values())), self.contract['maximumScenarios'])
        self.assertEqual(self.contract['maximumScenarios'], 2)
        self.assertEqual(self.contract['maximumLocalHttpRequestsPerScenario'], 2)
        self.assertEqual(self.contract['paidModelCalls'], 0)
        self.assertFalse(self.contract['certifiesNativeProvider'])

    def test_host_descriptions_truthfully_declare_read_only_operations(self):
        # 宣言の真偽は実host試験で検証済み。ここでは本当に配布するMCP情報を確認する。
        import test_routing_host as fixture
        instance = fixture.RoutingHostTests(methodName='runTest')
        instance.setUp()
        self.addCleanup(instance.doCleanups)
        host = fixture.host.Host(instance.snapshot, fixture.host.sha((instance.snapshot / 'manifest.json').read_bytes()), instance.log)
        self.addCleanup(host.close)
        self.assertEqual({t['name'] for t in host.tools}, {'list_resources', 'read_resource'})
        for tool in host.tools:
            self.assertEqual(tool['annotations'], {'readOnlyHint': True, 'destructiveHint': False,
                                                  'idempotentHint': True, 'openWorldHint': False})

    def test_async_question_events_are_rejected_even_if_they_claim_final_answer(self):
        for method in ['item/started', 'item/completed']:
            frame = {'method': method, 'params': {'item': {'type': 'agentMessage', 'phase': 'final_answer',
                'delivery': 'async', 'questions': [{'title': 'question'}]}}}
            self.assertTrue(probe.sdk.question_frame(frame))
            frame['params']['item']['questions'] = None
            self.assertTrue(probe.sdk.question_frame(frame))

    def test_ordinary_messages_and_rpc_responses_are_not_dialogue_events(self):
        for frame in [{'id': 'rpc', 'result': {}}, {'method': 'item/completed', 'params': {'item': {
            'type': 'agentMessage', 'delivery': None, 'questions': None, 'text': '質問という文字だけ'}}}]:
            self.assertFalse(probe.sdk.question_frame(frame))


if __name__ == '__main__':
    unittest.main()
