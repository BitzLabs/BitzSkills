"""カナリアの有限境界を無課金で検証する。原モデル行動の認定ではない。"""
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_capture as capture
import production_canary_host as limited
import test_routing_host as host_fixture


class CanaryCaptureTests(unittest.TestCase):
    def test_structure_policy_requires_its_exact_identity_and_output(self):
        contract=dict(self.contract(),version='production-canary-0.1.2',campaignId=capture.ledger.STRUCTURE_CAMPAIGN,
                      outputRelativeRoot='.venv/production-routing-primary-code-mode-structure-01')
        self.assertEqual(contract['version'],'production-canary-0.1.2')
        capture.policy(contract)
        for key,value in [('campaignId',capture.ledger.SCHEMA_CAMPAIGN),
                          ('outputRelativeRoot','.venv/production-routing-primary-schema-projection-01')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'structure measurement identity'):
                capture.policy(dict(contract,**{key:value}))

    def test_reasoning_policy_requires_its_exact_identity_and_output(self):
        contract=dict(self.contract(),version='production-canary-0.1.3',campaignId=capture.ledger.REASONING_CAMPAIGN,
                      outputRelativeRoot='.venv/production-routing-primary-empty-reasoning-01')
        self.assertEqual(contract['version'],'production-canary-0.1.3');capture.policy(contract)
        for key,value in [('campaignId',capture.ledger.STRUCTURE_CAMPAIGN),
                          ('outputRelativeRoot','.venv/production-routing-primary-code-mode-structure-01')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'reasoning measurement identity'):
                capture.policy(dict(contract,**{key:value}))

    def test_clock_policy_requires_its_exact_identity_and_output(self):
        contract=self.contract();self.assertEqual(contract['version'],'production-canary-0.1.4');capture.policy(contract)
        for key,value in [('campaignId',capture.ledger.REASONING_CAMPAIGN),
                          ('outputRelativeRoot','.venv/production-routing-primary-empty-reasoning-01')]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'clock measurement identity'):
                capture.policy(dict(contract,**{key:value}))

    def test_execution_schema_does_not_weaken_canonical_duplicate_event_validation(self):
        schema=json.loads((ROOT/'evals/skills/schemas/decision.schema.json').read_bytes());original=copy.deepcopy(schema)
        wire=capture.execution_schema(schema)
        self.assertEqual(schema,original)
        self.assertNotIn('uniqueItems',wire['properties']['events'])
        decision=dict(selectedEntry=None,selectedPath=None,outcome='not-applicable',events=['invoke-bitz','invoke-bitz'],
            rejectedEvents=[],readyClaimed=False,evidencePresent=False,reason='public duplicate regression')
        capture.trace.jsonschema.Draft202012Validator(wire).validate(decision)
        with self.assertRaises(capture.trace.jsonschema.exceptions.ValidationError):
            capture.trace.jsonschema.Draft202012Validator(schema).validate(decision)

    def test_guarded_proxy_rejects_missing_or_unknown_tracing_before_cli_start(self):
        for tracing in [None, {}, {'format': 'text', 'rustLog': 'unknown'}]:
            base = self.temporary()
            (base / 'config.json').write_text('{}')
            contract = {'codexPath': '/unused/cli'}
            if tracing is not None:
                contract['diagnosticTracing'] = tracing
            (base / 'contract.json').write_text(json.dumps(contract))
            with self.subTest(tracing=tracing), patch.object(capture.sdk.subprocess, 'Popen',
                    side_effect=AssertionError('CLI started before tracing validation')) as start:
                with self.assertRaisesRegex(ValueError, 'tracing'):
                    capture.sdk.proxy(base, capture_guard=lambda *_: True)
                start.assert_not_called()
            self.assertFalse((base / 'runtime-result.json').exists())

    def test_control_notification_with_missing_or_unknown_source_stops(self):
        for source in [None, '', 'unknown', [], {}]:
            value = capture.CaptureGuard(self.temporary())
            direct = {'fields': {'event.name': 'codex.tool_call_received', 'tool_source': 'direct', 'tool_name': 'exec'}}
            self.assertTrue(value('telemetry', direct))
            self.assertTrue(value('telemetry', direct))
            fields = {'event.name': 'codex.tool_call_received', 'tool_name': 'wait'}
            if source is not None:
                fields['tool_source'] = source
            with self.subTest(source=source):
                self.assertFalse(value('telemetry', {'fields': fields}))
                self.assertTrue((value.base / 'capture-stop.json').exists())
                self.assertFalse(value('telemetry', direct))

    def test_known_child_source_preserves_control_limit_and_rejects_masquerading(self):
        value = capture.CaptureGuard(self.temporary())
        direct = {'fields': {'event.name': 'codex.tool_call_received', 'tool_source': 'direct', 'tool_name': 'exec'}}
        self.assertTrue(value('telemetry', direct))
        self.assertTrue(value('telemetry', direct))
        for tool in ['list_resources', 'read_resource']:
            self.assertTrue(value('telemetry', {'fields': {'event.name': 'codex.tool_call_received',
                'tool_source': 'code_mode', 'tool_namespace': 'mcp__production_routing', 'tool_name': tool}}))
        self.assertEqual(value.counts['control'], 2)
        self.assertFalse(value('telemetry', direct))
        for namespace, tool in [('functions', 'exec'), ('mcp__production_routing', 'wait'),
                                ('other', 'read_resource'), (None, 'list_resources')]:
            other = capture.CaptureGuard(self.temporary())
            self.assertFalse(other('telemetry', {'fields': {'event.name': 'codex.tool_call_received',
                'tool_source': 'code_mode', 'tool_namespace': namespace, 'tool_name': tool}}))
            self.assertTrue((other.base / 'capture-stop.json').exists())

    def test_callback_free_legacy_proxy_keeps_optional_tracing_and_result_shape(self):
        base = self.temporary()
        fake = base / 'fake-codex'
        fake.write_text('#!/usr/bin/python3\n')
        fake.chmod(0o700)
        (base / 'config.json').write_text('{}')
        (base / 'contract.json').write_text(json.dumps({'codexPath': str(fake)}))
        code = ('import sys; from pathlib import Path; sys.path.insert(0,"evals/skills/routing"); '
                'import production_sdk_probe as sdk; sdk.proxy(Path(sys.argv[1]))')
        result = subprocess.run([sys.executable, '-B', '-c', code, str(base)], cwd=ROOT,
                                input=b'', capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads((base / 'runtime-result.json').read_bytes()),
                         {'exitCode': 0, 'forcedShutdown': False})
        self.assertFalse((base / 'trace-safe.jsonl').exists())

    def test_host_import_does_not_register_generic_host_module(self):
        result = subprocess.run([sys.executable, '-B', '-c',
            'import sys; sys.path.insert(0, "evals/skills/routing"); import production_canary_host; assert "host" not in sys.modules'],
            cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

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
                           ('diagnosticTracing', None), ('diagnosticTracing', {}),
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
            self.assertTrue(value.call('read_resource', {'path': fixture.manifest['skills'][0]['path']})['isError'])
            if not list_first:
                self.assertFalse(value.listed)

    def test_malformed_capture_fields_are_rejected_with_sticky_marker(self):
        for direction, event in [('telemetry', {'fields': None}), ('telemetry', {'fields': []}),
                                  ('rpc', {'method': 'warning', 'params': None}),
                                  ('rpc', {'method': 'item/started', 'params': {'item': None}}), ('rpc', None)]:
            value = capture.CaptureGuard(self.temporary())
            self.assertFalse(value(direction, event))
            self.assertTrue((value.base / 'capture-stop.json').exists())
            self.assertFalse(value('rpc', {'id': 1, 'result': {}}))

    def test_proxy_monitor_exception_sets_integrity_failure_even_when_cli_exits_zero(self):
        base = self.temporary()
        fake = base / 'fake-codex'
        fake.write_text('#!/usr/bin/python3\nimport sys\nsys.stderr.write(\'{"target":"codex_otel.trace_safe","fields":null}\\n\')\nsys.stderr.flush()\n')
        fake.chmod(0o700)
        (base / 'config.json').write_text('{}')
        (base / 'contract.json').write_text(json.dumps({'codexPath': str(fake), 'diagnosticTracing':
            {'format': 'json', 'rustLog': 'codex_otel.trace_safe=info,codex_code_mode::timing=info'}}))
        code = ('import sys; from pathlib import Path; sys.path.insert(0,"evals/skills/routing"); import production_sdk_probe as sdk; '
                'sdk.proxy(Path(sys.argv[1]), capture_guard=lambda kind,value: value["fields"].get("x") if kind=="telemetry" else True)')
        result = subprocess.run([sys.executable, '-B', '-c', code, str(base)], cwd=ROOT, input=b'', capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        runtime = json.loads((base / 'runtime-result.json').read_bytes())
        self.assertEqual(runtime['exitCode'], 0)
        self.assertFalse(runtime['captureIntegrity'])
        self.assertEqual(json.loads((base / 'proxy-capture-errors.json').read_bytes())['errors'][0]['errorType'], 'AttributeError')

    def test_context_profile_is_pinned_and_rejects_model_claims_or_unfixed_context(self):
        contract=self.contract();raw=(ROOT/capture.CONTEXT).read_bytes()
        self.assertEqual(capture.context_profile(raw,contract)['supplementBlockCount'],2)
        with self.assertRaises(ValueError):capture.context_profile(raw+b' ',contract)
        for key,value in [('systemSkillsDisabled',False),('supplementBlockCount',True),('paidModelCalls',True),
                          ('primaryModelTrajectories',1),('certifiesSkillGate',True),('date','2026-13-01')]:
            profile=json.loads(raw);profile[key]=value;changed=capture.ledger.encoded(profile)
            contract['contextProfileSha256']=capture.ledger.sha(changed)
            with self.subTest(key=key),self.assertRaises(ValueError):capture.context_profile(changed,contract)

    def test_builtin_skills_disabled_and_cli_inline_table_array_is_toml(self):
        import tomllib
        config = capture.config_for(Path('/fixed/base'), json.loads((ROOT / capture.CONTRACT).read_bytes()))
        expected = [dict(name=n, enabled=False) for n in ['imagegen','openai-docs','skill-creator','skill-installer']]
        self.assertEqual(config['skills.config'], expected)
        for value in [expected, ['plain','quoted"value','line\nvalue'], True, 3, 'literal']:
            self.assertEqual(tomllib.loads('value='+capture.sdk.toml_value(value))['value'], value)
        for value in [None, 1.2, {'bad':None}]:
            with self.assertRaises(ValueError):capture.sdk.toml_value(value)

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
        self.assertNotIn('model_providers.bitz_openai_http.include_internal_metadata', config)
