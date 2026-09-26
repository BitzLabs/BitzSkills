"""doctorの全体事前検査後のmember診断と公開CLIの回帰試験。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bitz import doctor
from bitz.cliargs import parse_argv


CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
BITZ = Path(sys.executable).parent / "bitz"


class DoctorAllWorkspacesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", str(self.root)], env=self.env, check=True)
        self.write_config(".", "platform", "multiWorkspace:\n  members:\n"
                          "    - id: web\n      path: apps/web\n"
                          "    - id: api\n      path: services/api\n")
        self.write_config("apps/web", "web")
        self.write_config("services/api", "api")

    def write_config(self, path, wid, extra=""):
        spec = self.root / path / ".spec"
        spec.mkdir(parents=True, exist_ok=True)
        (spec / "bitz.yaml").write_text(CONFIG + f"workspace:\n  id: {wid}\n" + extra, encoding="utf-8")

    def run_doctor(self, cwd=None):
        return doctor.run(parse_argv(["doctor", "--all-workspaces"]), str(cwd or self.root), self.env)

    def test_success_from_member_includes_root_and_sorted_members(self):
        result, code = self.run_doctor(self.root / "apps/web")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
        self.assertEqual([(w["id"], w["path"]) for w in result["workspaces"]],
                         [("platform", "."), ("api", "services/api"), ("web", "apps/web")])
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "git", "catalog"])
        for member in result["workspaces"]:
            self.assertEqual(member["status"], "passed")
            self.assertEqual(member["diagnostics"], [])
            self.assertEqual([c["name"] for c in member["checks"]],
                             ["workspace", "config", "schema", "ears", "command", "impact"])
            self.assertEqual(set(member), {"id", "path", "status", "checks", "durationMs", "diagnostics"})

    def test_member_command_failure_continues_and_aggregates(self):
        self.write_config("services/api", "api", 'verify:\n  commands:\n    default:\n'
                          '      argv: [./missing-command]\n      cwd: .\n')
        result, code = self.run_doctor()
        self.assertEqual((result["status"], code), ("blocked", 2))
        by_id = {w["id"]: w for w in result["workspaces"]}
        self.assertEqual(by_id["api"]["status"], "blocked")
        self.assertEqual(by_id["web"]["status"], "passed")
        self.assertEqual(by_id["platform"]["status"], "passed")
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual([d["code"] for d in by_id["api"]["diagnostics"]], ["SPEC-DOCTOR-COMMAND-001"])
        self.assertEqual(by_id["api"]["diagnostics"][0]["source"]["workspaceId"], "api")

    def test_config_warnings_stay_with_owner_and_affect_aggregate(self):
        self.write_config(".", "platform", "multiWorkspace:\n  members:\n"
                          "    - id: web\n      path: apps/web\n"
                          "    - id: api\n      path: services/api\nfuture: true\n")
        self.write_config("apps/web", "web", "future: true\n")
        result, code = self.run_doctor()
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0))
        self.assertEqual([w["status"] for w in result["workspaces"]],
                         ["passed_with_warnings", "passed", "passed_with_warnings"])
        self.assertEqual(result["diagnostics"], [])
        for member in (result["workspaces"][0], result["workspaces"][2]):
            self.assertEqual(len(member["diagnostics"]), 1)
            self.assertEqual(member["diagnostics"][0]["source"]["workspaceId"], member["id"])

    def test_command_is_resolved_from_member_cwd_without_running_it(self):
        self.write_config("apps/web", "web", 'verify:\n  commands:\n    default:\n'
                          '      argv: [./probe]\n      cwd: tools\n')
        tools = self.root / "apps/web/tools"
        tools.mkdir()
        probe = tools / "probe"
        probe.write_text("#!/bin/sh\ntouch should-not-exist\n", encoding="utf-8")
        probe.chmod(0o755)
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result, code = self.run_doctor()
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertFalse((tools / "should-not-exist").exists())
        self.assertFalse(any(self.root.glob("**/.spec/reports")))

    def test_missing_cwd_reports_member_and_continues(self):
        self.write_config("services/api", "api", 'verify:\n  commands:\n    default:\n'
                          '      argv: [python]\n      cwd: absent\n')
        result, code = self.run_doctor()
        self.assertEqual(code, 2)
        api = result["workspaces"][1]
        self.assertEqual(api["diagnostics"][0]["source"]["key"], "verify.commands.default.cwd")
        self.assertEqual(result["workspaces"][2]["status"], "passed")

    def test_invalid_catalog_stops_before_member_checks(self):
        (self.root / "apps/web/.spec/bitz.yaml").unlink()
        result, code = self.run_doctor()
        self.assertEqual(code, 1)
        self.assertEqual(result["workspaces"], [])
        self.assertEqual(result["diagnostics"][0]["code"], "SPEC-MULTI-MEMBER-001")

    def test_config_read_failure_after_precheck_marks_dependencies_and_continues(self):
        original = doctor.multiws.precheck

        def precheck_then_remove(*args, **kwargs):
            result = original(*args, **kwargs)
            self.assertTrue(result.ok)
            (self.root / "services/api/.spec/bitz.yaml").unlink()
            return result

        with patch.object(doctor.multiws, "precheck", side_effect=precheck_then_remove):
            result, code = self.run_doctor()
        self.assertEqual((result["status"], code), ("error", 3))
        by_id = {w["id"]: w for w in result["workspaces"]}
        self.assertEqual(by_id["web"]["status"], "passed")
        diagnostics = by_id["api"]["diagnostics"]
        self.assertEqual(sum(d["code"] == "SPEC-INPUT-READ-001" for d in diagnostics), 1)
        self.assertTrue(all(d["source"]["workspaceId"] == "api" for d in diagnostics))
        dependencies = [d for d in diagnostics if d["code"] == "SPEC-MULTI-DEPENDENCY-001"]
        self.assertEqual({d["evidence"]["stage"] for d in dependencies}, {"schema", "ears", "command", "impact"})
        for diagnostic in dependencies:
            self.assertEqual(diagnostic["evidence"]["dependencyWorkspaces"], ["api"])
            self.assertEqual(diagnostic["evidence"]["dependencySpecRefs"], [])
            self.assertEqual(diagnostic["source"],
                             {"kind": "file", "workspaceId": "api", "path": ".spec/bitz.yaml"})
        self.assertEqual(result["diagnostics"], [])

    def test_cli_json_and_text_show_member_failure(self):
        self.write_config("services/api", "api", 'verify:\n  commands:\n    default:\n'
                          '      argv: [./missing-command]\n      cwd: .\n')
        outputs = {}
        for fmt in ("json", "text"):
            outputs[fmt] = subprocess.run([str(BITZ), "doctor", "--all-workspaces", "--format", fmt],
                                          cwd=self.root, env=self.env, capture_output=True, text=True, timeout=30)
            self.assertEqual(outputs[fmt].returncode, 2)
            self.assertEqual(outputs[fmt].stderr, "")
        result = json.loads(outputs["json"].stdout)
        self.assertEqual(len(result["workspaces"]), 3)
        text = outputs["text"].stdout
        targets = len(result["checks"]) + sum(len(w["checks"]) for w in result["workspaces"])
        self.assertIn(f"targets={targets} diagnostics=1", text)
        self.assertEqual(text.count("SPEC-DOCTOR-COMMAND-001"), 1)
        self.assertIn("api:.spec/bitz.yaml:", text)


if __name__ == "__main__":
    unittest.main()
