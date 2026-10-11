"""接続診断の予約・停止・原相関を無課金で検証する。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_connection_probe as probe
import production_sdk_probe as sdk


class ConnectionProbeTests(unittest.TestCase):
    def contract(self):
        return json.loads((ROOT / probe.CONTRACT).read_bytes())

    def fixture(self):
        sent = [{'id': 1, 'method': 'initialize', 'params': {}}, {'method': 'initialized'},
                {'id': 2, 'method': 'thread/start', 'params': {'model': 'gpt-6.1-sol', 'modelProvider': 'openai',
                 'allowProviderModelFallback': False, 'sandbox': 'read-only', 'approvalPolicy': 'never',
                 'ephemeral': True, 'baseInstructions': probe.BASE, 'developerInstructions': probe.DEVELOPER}},
                {'id': 3, 'method': 'turn/start', 'params': {'threadId': 'thread', 'outputSchema': probe.SCHEMA,
                 'input': [{'type': 'text', 'text': probe.PROMPT}]}}]
        frames = [{'id': 1, 'result': {}}, {'id': 2, 'result': {'thread': {'id': 'thread'}}},
                  {'method': 'turn/started', 'params': {'threadId': 'thread', 'turn': {'id': 'turn'}}},
                  {'id': 3, 'result': {'turn': {'id': 'turn'}}},
                  {'method': 'item/completed', 'params': {'threadId': 'thread', 'turnId': 'turn',
                   'item': {'type': 'agentMessage', 'phase': 'final_answer', 'text': json.dumps(probe.FINAL)}}},
                  {'method': 'turn/completed', 'params': {'threadId': 'thread',
                   'turn': {'id': 'turn', 'status': 'completed', 'error': None}}}]
        api = [{'attempt': 0, 'http.response.status_code': 200, 'auth.header_attached': True}]
        return sent, frames, api, {'exitCode': 0, 'forcedShutdown': False}

    def test_finite_contract_rejects_extra_turns_retries_models_and_bool_counts(self):
        probe.policy(self.contract())
        for key, value in [('maximumInvocations', True), ('maximumLogicalTurns', 2), ('automaticRetries', 1),
                           ('timeoutSeconds', 300), ('model', 'other'), ('primaryModelTrajectories', 1)]:
            bad = self.contract()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): probe.policy(bad)

    def test_same_contract_reservation_cannot_be_repeated_with_another_source_or_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.venv') as temporary:
            storage = Path(temporary) / 'ledger'
            raw = json.dumps(self.contract()).encode()
            reservation = probe.reserve(ROOT, 'a' * 40, raw, storage)
            self.assertEqual(reservation['role'], 'paidConnectionDiagnostic')
            for source, changed in [('b' * 40, raw), ('a' * 40, json.dumps(dict(self.contract(), outputRelativeRoot='other')).encode())]:
                with self.assertRaises(FileExistsError): probe.reserve(ROOT, source, changed, storage)

    def test_reservation_rejects_symlink_storage(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.venv') as temporary:
            root = Path(temporary)
            (root / 'target').mkdir()
            (root / 'link').symlink_to(root / 'target')
            with self.assertRaises(ValueError): probe.reserve(ROOT, 'a' * 40, json.dumps(self.contract()).encode(), root / 'link')

    def test_original_success_needs_one_api_and_matching_native_and_caller_context(self):
        self.assertTrue(probe.evaluate(*self.fixture())['finalMatched'])
        for mutation in ['extra-api', 'attempt-bool', 'wrong-auth', 'other-turn', 'other-reply', 'post-terminal',
                         'tool', 'caller-prompt', 'schema', 'forced-shutdown', 'failed-turn', 'steer', 'duplicate-reply',
                         'unknown-reply', 'duplicate-request']:
            sent, frames, api, runtime = copy.deepcopy(self.fixture())
            if mutation == 'extra-api': api += copy.deepcopy(api)
            elif mutation == 'attempt-bool': api[0]['attempt'] = False
            elif mutation == 'wrong-auth': api[0]['auth.header_attached'] = False
            elif mutation == 'other-turn': frames[-1]['params']['turn']['id'] = 'other'
            elif mutation == 'other-reply': frames[1]['result']['thread']['id'] = 'other'
            elif mutation == 'post-terminal': frames.append(frames.pop(4))
            elif mutation == 'tool': frames[4]['params']['item']['type'] = 'commandExecution'
            elif mutation == 'caller-prompt': sent[3]['params']['input'][0]['text'] = 'different'
            elif mutation == 'schema': sent[3]['params']['outputSchema']['properties']['ok']['const'] = False
            elif mutation == 'forced-shutdown': runtime['forcedShutdown'] = True
            elif mutation == 'failed-turn': frames[-1]['params']['turn']['status'] = 'failed'
            elif mutation == 'steer': sent.append({'id': 4, 'method': 'turn/steer', 'params': {}})
            elif mutation == 'duplicate-reply': frames.insert(0, {'id': 2, 'result': {'thread': {'id': 'other'}}})
            elif mutation == 'unknown-reply': frames.append({'id': 4, 'result': {}})
            elif mutation == 'duplicate-request': sent[3]['id'] = sent[2]['id']
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                probe.evaluate(sent, frames, api, runtime)

    def test_unknown_actions_and_server_requests_are_stopped_before_forwarding(self):
        for item in ['commandExecution', 'dynamicToolCall', 'mcpToolCall', 'unknown', None]:
            self.assertTrue(sdk.action_frame({'method': 'item/started', 'params': {'item': {'type': item}}}))
        self.assertTrue(sdk.action_frame({'method': 'unknown', 'id': 1, 'params': {}}))
        for item in ['userMessage', 'agentMessage', 'reasoning']:
            self.assertFalse(sdk.action_frame({'method': 'item/started', 'params': {'item': {'type': item}}}))

    def test_native_config_disables_nonbudgeted_connection_retry_and_tools(self):
        config = probe.config_for(Path('/private-diagnostic'))
        self.assertFalse(config['features.unbounded_connection_retries'])
        self.assertFalse(config['features.system_proxy_fallback'])
        self.assertFalse(config['model_providers.openai.supports_websockets'])
        self.assertEqual(config['model_providers.openai.request_max_retries'], 0)
        self.assertFalse(config['features.code_mode_host'])
        self.assertFalse(any(key.startswith('mcp_servers.') for key in config))


if __name__ == '__main__':
    unittest.main()
