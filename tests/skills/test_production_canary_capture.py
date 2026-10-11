"""カナリアの有限境界を無課金で検証する。原モデル行動の認定ではない。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_capture as capture
import production_canary_host as limited
import test_routing_host as host_fixture


class CanaryCaptureTests(unittest.TestCase):
    def contract(self):
        return json.loads((ROOT / capture.CONTRACT).read_bytes())

    def temporary(self):
        value = tempfile.TemporaryDirectory(dir=ROOT / '.venv')
        self.addCleanup(value.cleanup)
        return Path(value.name)

    def api(self, endpoint='/responses', **changes):
        fields = {'event.name': 'codex.api_request', 'endpoint': endpoint, 'attempt': 0,
                  'auth.header_attached': True, 'http.response.status_code': 200}
        fields.update(changes)
        return {'fields': fields}

    def test_policy_rejects_unlimited_or_changed_budget(self):
        capture.policy(self.contract())
        for key, value in [('timeoutSeconds', True), ('timeoutSeconds', 301), ('maximumHostCalls', 3),
                           ('observedModelApiLimit', 4), ('model', 'gpt-6-astra'), ('certifiesApiRequestHardCap', True),
                           ('budget', {'primaryModelTrajectories': 4, 'independentReviewerSol': 4, 'automaticRetries': 1, 'delegations': 0})]:
            bad = self.contract()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): capture.policy(bad)

    def test_api_limit_and_failure_are_sticky_stops(self):
        guard = capture.CaptureGuard(self.temporary())
        for _ in range(2): self.assertTrue(guard('telemetry', self.api('/models')))
        for _ in range(3): self.assertTrue(guard('telemetry', self.api()))
        self.assertFalse(guard('telemetry', self.api()))
        self.assertFalse(guard('rpc', {'method': 'warning', 'params': {}}))
        self.assertEqual(json.loads((guard.base / 'capture-stop.json').read_bytes())['reason'], 'observed-api-limit')
        for fields in [{'attempt': True}, {'attempt': 1}, {'auth.header_attached': False},
                       {'http.response.status_code': 503}, {'auth.retry_after_unauthorized': True}, {'endpoint': '/other'}]:
            other = capture.CaptureGuard(self.temporary())
            self.assertFalse(other('telemetry', self.api(**fields)))

    def test_control_limit_unknown_tool_server_request_and_host_stop_reject(self):
        value = capture.CaptureGuard(self.temporary())
        event = {'fields': {'event.name': 'codex.tool_call_received', 'tool_source': 'direct', 'tool_name': 'exec'}}
        self.assertTrue(value('telemetry', event))
        event['fields']['tool_name'] = 'wait'
        self.assertTrue(value('telemetry', event))
        self.assertFalse(value('telemetry', event))
        invalid = [{'method': 'approval', 'id': 1}, {'method': 'item/started', 'params': {'item': {'type': 'commandExecution'}}},
                   {'method': 'item/started', 'params': {'item': {'type': 'mcpToolCall', 'server': 'other', 'tool': 'read_resource'}}}]
        for frame in invalid:
            other = capture.CaptureGuard(self.temporary())
            self.assertFalse(other('rpc', frame))
        other = capture.CaptureGuard(self.temporary())
        (other.base / 'host-stop.json').write_text('{}')
        self.assertFalse(other('rpc', {'method': 'warning'}))

    def test_limited_host_only_lists_then_reads_one_skill(self):
        fixture = host_fixture.RoutingHostTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        value = limited.CanaryHost(fixture.snapshot, fixture.digest, fixture.log)
        self.addCleanup(value.close)
        self.assertFalse(value.call('list_resources', {})['isError'])
        path = fixture.manifest['skills'][0]['path']
        self.assertFalse(value.call('read_resource', {'path': path})['isError'])
        self.assertTrue(value.call('read_resource', {'path': path})['isError'])
        self.assertTrue((fixture.base / 'host-stop.json').exists())

    def test_limited_host_rejects_first_read_unknown_path_and_second_listing(self):
        for tool, arguments, list_first in [('read_resource', {'path': 'unknown'}, False),
                                            ('read_resource', {'path': []}, True), ('list_resources', {}, True)]:
            fixture = host_fixture.RoutingHostTests(methodName='runTest')
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            value = limited.CanaryHost(fixture.snapshot, fixture.digest, fixture.log)
            self.addCleanup(value.close)
            if list_first: value.call('list_resources', {})
            self.assertTrue(value.call(tool, arguments)['isError'])
            self.assertTrue((fixture.base / 'host-stop.json').exists())

    def test_configuration_uses_same_provider_without_auth_or_url_override(self):
        config = capture.config_for(Path('/private/canary'), self.contract())
        self.assertEqual(config['model_provider'], 'bitz_openai_http')
        self.assertTrue(config['features.code_mode_host'])
        self.assertFalse(config['features.shell_tool'])
        self.assertFalse(config['features.multi_agent_v2'])
        self.assertEqual(config['model_providers.bitz_openai_http.request_max_retries'], 0)
        self.assertEqual(config['model_providers.bitz_openai_http.stream_max_retries'], 0)
        self.assertFalse(config['model_providers.bitz_openai_http.supports_websockets'])
        self.assertFalse(any(key.endswith(('.base_url', '.env_key', '.experimental_bearer_token')) for key in config))
        self.assertEqual(config['mcp_servers.production-routing.enabled_tools'], ['list_resources', 'read_resource'])
