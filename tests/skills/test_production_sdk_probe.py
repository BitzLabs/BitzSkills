"""公式SDKプローブの停止判定と、承認・依存・設定の境界を確認する。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_sdk_probe as sdk


class ProductionSdkProbeTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / sdk.CONTRACT).read_bytes())
        self.request = {'model': 'gpt-6.1-sol', 'input': [], 'tools': [
            {'type': 'function', 'name': name} for name in self.contract['allowedTools']]}
        self.frames = [
            {'id': 'init', 'result': {'userAgent': 'synthetic'}},
            {'id': 'thread', 'result': {'thread': {'id': 't'}}},
            {'id': 'turn', 'result': {'turn': {'id': 'u'}}},
            {'method': 'mcpServer/startupStatus/updated', 'params': {'name': 'production-routing', 'status': 'ready'}},
            {'method': 'item/started', 'params': {'threadId': 't', 'turnId': 'u',
                'item': {'type': 'agentMessage', 'phase': 'final_answer'}}},
            {'method': 'item/completed', 'params': {'threadId': 't', 'turnId': 'u',
                'item': {'type': 'agentMessage', 'phase': 'final_answer', 'text': 'LOCAL_SIMULATION_ONLY'}}},
            {'method': 'turn/completed', 'params': {'threadId': 't', 'turn': {'id': 'u', 'status': 'completed', 'error': None}}},
        ]

    def assess(self, requests=None, frames=None, exit_code=0):
        return sdk.evaluate([self.request] if requests is None else requests,
                            self.frames if frames is None else frames, self.contract, exit_code)

    def test_exact_two_tools_and_complete_mock_protocol(self):
        result = self.assess()
        self.assertEqual(result['status'], 'local_tool_declaration_passed')
        self.assertTrue(result['sdkProtocolPassed'])
        self.assertFalse(result['certifiesNativeProvider'])
        self.assertFalse(result['certifiesBehavior'])

    def test_successful_terminal_with_additional_tools_still_stops(self):
        self.request['input'].append({'type': 'additional_tools', 'tools': [
            {'type': 'namespace', 'name': 'functions', 'tools': [{'type': 'custom', 'name': 'exec'}]}]})
        result = self.assess()
        self.assertTrue(result['sdkProtocolPassed'])
        self.assertFalse(result['closedTwoToolPolicyVerified'])
        self.assertEqual(result['status'], 'local_tool_declaration_stopped')

    def test_missing_duplicate_or_wrong_model_requests_stop(self):
        for requests in [[], [self.request, self.request], [{**self.request, 'model': 'other'}]]:
            with self.subTest(requests=requests):
                self.assertEqual(self.assess(requests=requests)['status'], 'local_tool_declaration_stopped')

    def test_unknown_or_duplicate_tools_stop(self):
        for tools in [[{'type': 'web_search'}], self.request['tools'] * 2]:
            self.assertIsNotNone(self.assess(requests=[{**self.request, 'tools': tools}])['toolInventoryError'])

    def test_wrong_final_phase_text_thread_and_turn_stop(self):
        for target, key, value in [('item', 'phase', 'commentary'), ('item', 'text', 'wrong'),
                                   ('params', 'threadId', 'other'), ('params', 'turnId', 'other')]:
            frames = copy.deepcopy(self.frames)
            params = frames[-2]['params']
            (params['item'] if target == 'item' else params)[key] = value
            self.assertFalse(self.assess(frames=frames)['sdkProtocolPassed'])

    def test_missing_duplicate_or_failed_terminal_stop(self):
        failed = copy.deepcopy(self.frames)
        failed[-1]['params']['turn']['status'] = 'failed'
        for frames in [self.frames[:-1], self.frames + [self.frames[-1]], failed]:
            self.assertFalse(self.assess(frames=frames)['sdkProtocolPassed'])

    def test_tool_actions_and_rpc_errors_stop(self):
        for frame in [{'method': 'item/started', 'params': {'item': {'type': 'commandExecution'}}},
                      {'id': 'unexpected', 'error': {'code': -1}}, {'method': 'error', 'params': {}}]:
            self.assertFalse(self.assess(frames=self.frames + [frame])['sdkProtocolPassed'])

    def test_native_user_message_and_reasoning_are_not_tool_actions(self):
        for kind in ['userMessage', 'reasoning']:
            frames = self.frames[:4] + [{'method': 'item/started', 'params': {'item': {'type': kind}}}] + self.frames[4:]
            self.assertTrue(self.assess(frames=frames)['noToolActionsObserved'])

    def test_nonzero_runtime_exit_and_mcp_failure_stop(self):
        self.assertFalse(self.assess(exit_code=-15)['sdkProtocolPassed'])
        frames = copy.deepcopy(self.frames)
        frames[3]['params']['status'] = 'failed'
        self.assertFalse(self.assess(frames=frames)['sdkProtocolPassed'])

    def test_settings_do_not_modify_model_metadata_or_allow_shell(self):
        base = ROOT / '.venv' / 'synthetic-sdk'
        native = sdk.config_for(base, 1234, self.contract, 'sdk-native')
        minimal = sdk.config_for(base, 1234, self.contract, 'sdk-minimal')
        self.assertFalse(minimal['agents.enabled'])
        self.assertFalse(minimal['tools.experimental_request_user_input.enabled'])
        for config in [native, minimal]:
            self.assertFalse(config['features.shell_tool'])
            self.assertFalse(config['model_providers.bitz_local_probe.requires_openai_auth'])
            self.assertEqual(config['model'], 'gpt-6.1-sol')
            self.assertNotIn('model_catalog_json', config)
        with self.assertRaises(ValueError):
            sdk.config_for(base, 1234, self.contract, 'unknown')

    def test_sdk_default_accept_is_replaced_with_denial(self):
        for method in ['item/commandExecution/requestApproval', 'item/fileChange/requestApproval']:
            self.assertEqual(sdk.deny_request(method, {}), {'decision': 'decline'})
        with self.assertRaises(ValueError):
            sdk.deny_request('unknown', {})

    def test_dependency_hash_binds_content_and_path_but_ignores_bytecode(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.venv') as tmp:
            root = Path(tmp)
            (root / 'module.py').write_bytes(b'original')
            digest = sdk.tree_hash(root)
            (root / 'module.pyc').write_bytes(b'bytecode')
            self.assertEqual(sdk.tree_hash(root), digest)
            (root / 'module.py').write_bytes(b'changed')
            self.assertNotEqual(sdk.tree_hash(root), digest)
            (root / 'module.py').write_bytes(b'original')
            (root / 'module.py').rename(root / 'other.py')
            self.assertNotEqual(sdk.tree_hash(root), digest)
            (root / 'link').symlink_to(root / 'other.py')
            with self.assertRaises(ValueError):
                sdk.tree_hash(root)

    def test_fixed_two_outputs_and_zero_paid_budget(self):
        self.assertEqual(set(self.contract['outputLabels']), set(sdk.MODES))
        self.assertEqual(self.contract['maximumModes'], 2)
        self.assertEqual(self.contract['maximumLocalHttpRequestsPerMode'], 1)
        self.assertEqual(self.contract['paidModelCalls'], 0)

    def proxy_boundary(self,raw,*,trusted):
        settings=json.dumps(dict(codexPath='/PUBLIC_FIXED_CLI',diagnosticTracing=sdk.DIAGNOSTIC_TRACING)).encode()
        kwargs=dict(launch_contract_raw=settings)
        if trusted:kwargs['validated_config_raw']=raw
        read_patch=(patch.object(Path,'read_bytes',side_effect=AssertionError('unchecked config reopen'))
            if trusted else patch.object(Path,'read_bytes',return_value=raw))
        with read_patch as read, \
            patch.object(sdk.subprocess,'Popen',side_effect=RuntimeError('NO_REAL_PROCESS')) as process:
            with self.assertRaisesRegex(RuntimeError,'NO_REAL_PROCESS'):
                sdk.proxy(ROOT/'.venv/PUBLIC_PROXY_ONLY',**kwargs)
        return read,process.call_args.args[0]

    def test_verified_config_bytes_reach_argv_without_any_file_reopen(self):
        read,argv=self.proxy_boundary(b'{"model_catalog_json":"/PUBLIC_VERIFIED"}',trusted=True)
        read.assert_not_called();self.assertIn('model_catalog_json="/PUBLIC_VERIFIED"',argv)

    def test_legacy_proxy_still_reads_its_existing_configuration(self):
        read,argv=self.proxy_boundary(b'{"model_catalog_json":"/PUBLIC_LEGACY"}',trusted=False)
        read.assert_called_once();self.assertIn('model_catalog_json="/PUBLIC_LEGACY"',argv)

    def test_verified_config_rejects_wrong_type_duplicate_nonfinite_or_nonobject_before_popen(self):
        for raw in ['PUBLIC',b'[]',b'{"x":NaN}',b'{"x":1,"x":2}']:
            with self.subTest(raw=raw),patch.object(Path,'read_bytes',side_effect=AssertionError('unchecked read')), \
                patch.object(sdk.subprocess,'Popen') as process,self.assertRaises(ValueError):
                sdk.proxy(ROOT/'.venv/PUBLIC_PROXY_ONLY',validated_config_raw=raw)
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
