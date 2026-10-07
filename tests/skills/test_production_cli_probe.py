"""CLI通信プローブの隔離とtool allowlistを確認する。実モデルを起動しない。"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_cli_probe as probe


class ProductionCliProbeTests(unittest.TestCase):
    def test_extra_tool_is_not_equal_to_allowlist(self):
        names = probe.tool_names([{'type': 'function', 'name': 'read_resource'}, {'type': 'function', 'name': 'exec_command'}])
        self.assertNotEqual(names, ['read_resource'])

    def test_unknown_tool_types_and_duplicate_names_stop(self):
        for tools in [None, [{'type': 'web_search'}], [{'type': 'function', 'name': 3}],
                      [{'type': 'function', 'name': 'read'}, {'type': 'function', 'name': 'read'}]]:
            with self.subTest(tools=tools), self.assertRaises(ValueError):
                probe.tool_names(tools)

    def test_namespace_hides_home_and_has_only_output_writable(self):
        base = ROOT / '.venv' / 'probe-test'
        argv = probe.namespace(base, '/usr/bin/python3', ['-B', 'script.py'])
        self.assertIn('--unshare-net', argv)
        self.assertIn('--unshare-pid', argv)
        self.assertEqual(argv[argv.index('--bind') + 1:argv.index('--bind') + 3], [str(base), str(base)])
        self.assertEqual(argv.count('--bind'), 1)
        self.assertEqual(argv[argv.index('--tmpfs') + 1], '/home/hide')

    def test_policy_no_auth_no_paid_provider_and_shell_disabled(self):
        contract = json.loads((ROOT / probe.CONTRACT).read_bytes())
        values = probe.policy(ROOT / '.venv' / 'probe-test', 1234, contract)
        self.assertFalse(values['model_providers.bitz_local_probe.requires_openai_auth'])
        self.assertEqual(values['model_providers.bitz_local_probe.base_url'], 'http://127.0.0.1:1234/v1')
        self.assertFalse(values['features.shell_tool'])
        self.assertFalse(values['features.multi_agent'])
        self.assertEqual(values['web_search'], 'disabled')
        self.assertEqual(values['mcp_servers.production-routing.enabled_tools'], ['list_resources', 'read_resource'])

    def test_simulated_terminal_is_explicitly_not_real_measurement(self):
        events = [json.loads(l[6:]) for l in probe.simulation_reply().decode().splitlines() if l.startswith('data: ')]
        self.assertEqual(events[-1]['type'], 'response.completed')
        message = events[-1]['response']['output'][0]
        self.assertEqual(message['phase'], 'final_answer')
        self.assertEqual(message['content'][0]['text'], 'LOCAL_SIMULATION_ONLY')


if __name__ == '__main__':
    unittest.main()
