"""`doctor`のプラグインの要求の判定（`04_doctor.md` §3・§4.1、ADR-061）の単体試験。

検査2（検査項目`plugin`）と検査3（検査項目`capability`）の組合せ、判定、結果内の位置、診断の発生元と根拠、
`--all-workspaces`での最上位への1回だけの配置を確かめる。字句の不一致（終了コード4）は`test_cliargs.py`が対象。
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import doctor
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
BITZ = Path(sys.executable).parent / "bitz"
FULL = ["--plugin", "bitz-sdd", "--plugin-version", "1.2.3"]


def _request(api, *capabilities):
    args = [*FULL, "--require-core-api", api]
    for name in capabilities:
        args += ["--require-capability", name]
    return args


class DoctorPluginRequestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", str(self.root)], env=self.env, check=True)
        (self.root / ".spec").mkdir()
        (self.root / ".spec" / "bitz.yaml").write_text(CONFIG, encoding="utf-8")

    def run_doctor(self, *args, cwd=None):
        parsed = parse_argv(["doctor", "--format", "json", *args])
        return doctor.run(parsed, str(cwd or self.root), self.env)

    @staticmethod
    def codes(result):
        return [d["code"] for d in result["diagnostics"]]

    @staticmethod
    def check_names(result):
        return [c["name"] for c in result["checks"]]

    @staticmethod
    def check(result, name):
        return next(c for c in result["checks"] if c["name"] == name)

    # --- 要求なし ---------------------------------------------------------------

    def test_no_request_adds_neither_checks_nor_diagnostics(self):
        result, code = self.run_doctor()
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(self.check_names(result), ["core", "workspace", "config", "schema", "ears", "git", "command", "impact"])
        self.assertEqual(result["diagnostics"], [])

    # --- 組合せ -----------------------------------------------------------------

    def test_incomplete_combinations_fail_with_sorted_missing_options(self):
        cases = {
            ("--plugin", "--plugin-version"): ["--require-core-api"],
            ("--plugin", "--require-core-api"): ["--plugin-version"],
            ("--plugin-version", "--require-core-api"): ["--plugin"],
            ("--plugin",): ["--plugin-version", "--require-core-api"],
            ("--plugin-version",): ["--plugin", "--require-core-api"],
            ("--require-core-api",): ["--plugin", "--plugin-version"],
            (): ["--plugin", "--plugin-version", "--require-core-api"],
        }
        values = {"--plugin": "bitz-sdd", "--plugin-version": "1.2.3", "--require-core-api": "^1.0"}
        for given, missing in cases.items():
            with self.subTest(given=given):
                args = [x for name in given for x in (name, values[name])]
                # 組合せが空の場合は`--require-capability`だけで要求を成立させる。
                if not given:
                    args = ["--require-capability", "context.v1"]
                result, code = self.run_doctor(*args)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(self.codes(result), ["SPEC-DOCTOR-PLUGIN-001"])
                diagnostic = result["diagnostics"][0]
                self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"]), ("error", "failed"))
                self.assertEqual(diagnostic["evidence"], {"missing": missing})
                self.assertEqual(self.check(result, "plugin")["status"], "failed")
                self.assertNotIn("capability", self.check_names(result))

    def test_incomplete_request_does_not_judge_api_or_capabilities(self):
        # 検査2・3は行わない。範囲が満たされない値や未知の対応機能があっても`SPEC-DOCTOR-PLUGIN-001`だけを返す。
        result, _ = self.run_doctor("--plugin", "bitz-sdd", "--require-capability", "unknown.v9")
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-PLUGIN-001"])
        self.assertEqual(result["diagnostics"][0]["evidence"], {"missing": ["--plugin-version", "--require-core-api"]})
        self.assertNotIn("capability", self.check_names(result))

    def test_capability_only_request_is_incomplete(self):
        result, code = self.run_doctor("--require-capability", "context.v1")
        self.assertEqual(code, 1)
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-PLUGIN-001"])
        # `--plugin`がないため`identifier`は置かない。
        self.assertEqual(result["diagnostics"][0]["source"], {"kind": "environment", "component": "plugin"})

    def test_incomplete_request_with_plugin_keeps_identifier(self):
        result, _ = self.run_doctor("--plugin", "bitz-sdd")
        self.assertEqual(
            result["diagnostics"][0]["source"],
            {"kind": "environment", "component": "plugin", "identifier": "bitz-sdd"},
        )

    # --- 判定: Core API ---------------------------------------------------------

    def test_core_api_satisfied(self):
        for required in ("1.0", "=1.0", ">=1.0", "^1.0", "<=1.0", "<2.0", ">=1.0 <2.0", ">=0.9 <=1.0", "^1.0 >=0.0", ">0.9"):
            with self.subTest(required=required):
                result, code = self.run_doctor(*_request(required))
                self.assertEqual((result["status"], code), ("passed", 0))
                self.assertEqual(self.check(result, "plugin")["status"], "passed")
                self.assertEqual(self.check(result, "capability")["status"], "passed")
                self.assertEqual(result["diagnostics"], [])

    def test_core_api_not_satisfied(self):
        for required in (">=1.1", "^2.0", "<1.0", ">1.0", ">=0.9 <1.0", "=2.0", "2.0", "^0.9", "^1.1", "<=0.9", ">=1.0 <1.0", "=1.1", "0.0", "^0.0 ^1.0"):
            with self.subTest(required=required):
                result, code = self.run_doctor(*_request(required))
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(self.codes(result), ["SPEC-DOCTOR-API-001"])
                diagnostic = result["diagnostics"][0]
                self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"]), ("error", "blocked"))
                self.assertEqual(diagnostic["evidence"], {"coreApi": "1.0", "required": required})
                self.assertEqual(
                    diagnostic["source"], {"kind": "environment", "component": "plugin", "identifier": "bitz-sdd"}
                )
                self.assertEqual(self.check(result, "plugin")["status"], "blocked")
                # 検査3は独立して行い、要求の対応機能が0件なら通過する。
                self.assertEqual(self.check(result, "capability")["status"], "passed")

    def test_core_api_compares_numerically_not_lexically(self):
        # 文字列比較では"1.10" < "1.9"になるが、整数の組では1.0 < 1.9 < 1.10。
        result, _ = self.run_doctor(*_request("<1.10"))
        self.assertEqual(result["diagnostics"], [])
        result, _ = self.run_doctor(*_request(">=1.10"))
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-API-001"])

    def test_required_range_is_reported_verbatim(self):
        result, _ = self.run_doctor(*_request(">=1.1 <3.0"))
        self.assertEqual(result["diagnostics"][0]["evidence"]["required"], ">=1.1 <3.0")

    # --- 判定: 対応機能 ---------------------------------------------------------

    def test_published_capabilities_pass(self):
        names = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
        result, code = self.run_doctor(*_request("^1.0", *names))
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(self.check_names(result)[:3], ["core", "plugin", "capability"])
        self.assertEqual(self.check(result, "capability"), {"name": "capability", "status": "passed"})

    def test_missing_capabilities_are_blocked_with_sorted_evidence(self):
        result, code = self.run_doctor(*_request("^1.0", "zeta.v1", "context.v2", "context.v1", "Alpha.v1"))
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-CAPABILITY-001"])
        diagnostic = result["diagnostics"][0]
        self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"]), ("error", "blocked"))
        self.assertEqual(diagnostic["evidence"], {"missing": ["Alpha.v1", "context.v2", "zeta.v1"]})
        self.assertEqual(
            diagnostic["source"], {"kind": "environment", "component": "plugin", "identifier": "bitz-sdd"}
        )
        self.assertEqual(self.check(result, "plugin")["status"], "passed")
        self.assertEqual(self.check(result, "capability")["status"], "blocked")

    def test_duplicate_capability_is_reported_once(self):
        result, _ = self.run_doctor(*_request("^1.0", "unknown.v1", "unknown.v1"))
        self.assertEqual(result["diagnostics"][0]["evidence"], {"missing": ["unknown.v1"]})

    def test_api_and_capability_failures_are_independent_and_both_returned(self):
        result, code = self.run_doctor(*_request(">=2.0", "context.v1", "context.v2"))
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-API-001", "SPEC-DOCTOR-CAPABILITY-001"])
        self.assertEqual(self.check(result, "plugin")["status"], "blocked")
        self.assertEqual(self.check(result, "capability")["status"], "blocked")
        self.assertEqual(result["diagnostics"][0]["evidence"], {"coreApi": "1.0", "required": ">=2.0"})
        self.assertEqual(result["diagnostics"][1]["evidence"], {"missing": ["context.v2"]})

    def test_core_api_version_comes_from_the_reported_core_value(self):
        result, _ = self.run_doctor(*_request("=1.0"))
        self.assertEqual(result["core"]["apiVersion"], "1.0")
        self.assertEqual(result["diagnostics"], [])

    # --- 位置 -------------------------------------------------------------------

    def test_plugin_and_capability_follow_core(self):
        result, _ = self.run_doctor(*_request("^1.0", "context.v1"))
        self.assertEqual(
            self.check_names(result),
            ["core", "plugin", "capability", "workspace", "config", "schema", "ears", "git", "command", "impact"],
        )

    def test_independent_of_later_check_failures(self):
        # ワークスペース不在でも、検査2と検査3は行い、その診断を落とさない。
        (self.root / ".spec" / "bitz.yaml").unlink()
        result, code = self.run_doctor(*_request(">=2.0", "context.v2"))
        self.assertEqual(code, 2)
        self.assertEqual(
            self.codes(result),
            ["SPEC-DOCTOR-API-001", "SPEC-DOCTOR-CAPABILITY-001", "SPEC-DOCTOR-WORKSPACE-001"],
        )
        self.assertEqual(self.check_names(result)[:4], ["core", "plugin", "capability", "workspace"])

    def test_independent_of_invalid_config(self):
        (self.root / ".spec" / "bitz.yaml").write_text('schemaVersion: "1.0"\nlanguage: 1\nearsAi: "1.0"\n', encoding="utf-8")
        result, _ = self.run_doctor(*_request("^2.0"))
        self.assertIn("SPEC-DOCTOR-API-001", self.codes(result))
        self.assertIn("SPEC-CONFIG-SCHEMA-001", self.codes(result))
        self.assertEqual(self.check_names(result)[:3], ["core", "plugin", "capability"])

    def test_incomplete_request_does_not_hide_later_check_diagnostics(self):
        (self.root / ".spec" / "bitz.yaml").unlink()
        result, code = self.run_doctor("--plugin", "bitz-sdd")
        # 共通の最悪値の規則（error > failed > blocked）で、`failed`が`blocked`より優先する。
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(self.codes(result), ["SPEC-DOCTOR-PLUGIN-001", "SPEC-DOCTOR-WORKSPACE-001"])

    def test_cpython_below_floor_still_reports_plugin_checks(self):
        from unittest.mock import patch

        with patch.object(doctor.sys, "version_info", (3, 11, 0, "final", 0)):
            result, code = self.run_doctor(*_request(">=2.0", "context.v2"))
        self.assertEqual(code, 2)
        self.assertEqual(self.check_names(result), ["core", "plugin", "capability"])
        self.assertEqual(
            self.codes(result),
            ["SPEC-DOCTOR-API-001", "SPEC-DOCTOR-CAPABILITY-001", "SPEC-DOCTOR-CORE-001"],
        )

    # --- 決定性・テキスト出力 ---------------------------------------------------

    def test_result_is_deterministic_across_runs(self):
        args = _request(">=2.0", "z.v1", "a.v1", "context.v2")
        first, _ = self.run_doctor(*args)
        second, _ = self.run_doctor(*args)
        for result in (first, second):
            result["durationMs"] = 0
        self.assertEqual(json.dumps(first, sort_keys=False), json.dumps(second, sort_keys=False))

    def test_text_output_lists_environment_diagnostics_in_plugin_component(self):
        from bitz.textrender import render_doctor_text

        result, _ = self.run_doctor(*_request(">=2.0", "context.v2"))
        text = render_doctor_text(result)
        self.assertIn("plugin::::", text)
        self.assertIn("SPEC-DOCTOR-API-001", text)
        self.assertIn("SPEC-DOCTOR-CAPABILITY-001", text)
        self.assertNotIn("coreApi", text)  # textは`evidence`を出力しない


class DoctorPluginRequestAllWorkspacesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", str(self.root)], env=self.env, check=True)
        self.write_config(
            ".", "platform",
            "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n",
        )
        self.write_config("apps/web", "web")
        self.write_config("services/api", "api")

    def write_config(self, path, wid, extra=""):
        spec = self.root / path / ".spec"
        spec.mkdir(parents=True, exist_ok=True)
        (spec / "bitz.yaml").write_text(CONFIG + f"workspace:\n  id: {wid}\n" + extra, encoding="utf-8")

    def run_doctor(self, *args):
        parsed = parse_argv(["doctor", "--all-workspaces", "--format", "json", *args])
        return doctor.run(parsed, str(self.root), self.env)

    def test_no_request_keeps_top_level_checks(self):
        result, code = self.run_doctor()
        self.assertEqual(code, 0)
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "git", "catalog"])

    def test_placed_once_at_top_level_after_core_and_not_duplicated_to_members(self):
        result, code = self.run_doctor(*_request(">=2.0", "context.v2"))
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "plugin", "capability", "git", "catalog"])
        self.assertEqual(
            [d["code"] for d in result["diagnostics"]], ["SPEC-DOCTOR-API-001", "SPEC-DOCTOR-CAPABILITY-001"]
        )
        self.assertEqual(len(result["workspaces"]), 3)
        for member in result["workspaces"]:
            self.assertEqual(member["diagnostics"], [])
            self.assertNotIn("plugin", [c["name"] for c in member["checks"]])
            self.assertNotIn("capability", [c["name"] for c in member["checks"]])
            self.assertEqual(member["status"], "passed")

    def test_incomplete_request_at_top_level_only(self):
        result, code = self.run_doctor("--require-capability", "context.v1")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "plugin", "git", "catalog"])
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-DOCTOR-PLUGIN-001"])
        for member in result["workspaces"]:
            self.assertEqual(member["diagnostics"], [])

    def test_satisfied_request_passes(self):
        result, code = self.run_doctor(*_request("^1.0", "multiWorkspace.v1"))
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "plugin", "capability", "git", "catalog"])
        self.assertEqual(result["diagnostics"], [])


class DoctorPluginRequestCliTests(unittest.TestCase):
    """公開CLIでの終了コードと出力の形。"""

    def run_cli(self, cwd, *args):
        return subprocess.run(
            [str(BITZ), "doctor", *args], cwd=cwd, capture_output=True, text=True,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull),
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = temporary.name
        subprocess.run(["git", "init", "-q", self.root], check=True)
        os.makedirs(os.path.join(self.root, ".spec"))
        Path(self.root, ".spec", "bitz.yaml").write_text(CONFIG, encoding="utf-8")

    def test_lexical_error_exits_4_without_stdout(self):
        done = self.run_cli(self.root, "--plugin", "Bad", "--plugin-version", "1.0.0", "--require-core-api", "^1.0")
        self.assertEqual((done.returncode, done.stdout), (4, ""))
        self.assertTrue(done.stderr.startswith("bitz: doctor: "))

    def test_incompatible_api_exits_2_with_json(self):
        done = self.run_cli(self.root, "--format", "json", *_request(">=2.0"))
        self.assertEqual(done.returncode, 2)
        self.assertEqual(json.loads(done.stdout)["diagnostics"][0]["code"], "SPEC-DOCTOR-API-001")

    def test_incomplete_request_exits_1(self):
        done = self.run_cli(self.root, "--plugin", "bitz-sdd")
        self.assertEqual(done.returncode, 1)
        self.assertIn("SPEC-DOCTOR-PLUGIN-001", done.stdout)

    def test_compatible_request_exits_0(self):
        done = self.run_cli(self.root, *_request("^1.0", "context.v1"))
        self.assertEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
