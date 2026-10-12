"""`doctor`の診断の`suggestedAction`（`04_doctor.md` §1・§8、ADR-062 Decision 2）の単体試験。

期待する文言は、管理者が2026-10-12に承認した文言（`fixtures/conformance/Coreの出力文言のレビュー記録.md` PR-4の節）
であり、Coreの出力を写したものではない。`SPEC-DOCTOR-CORE-002`と`SPEC-MULTI-DEPENDENCY-001`には付けず、
`check`などが返す`SPEC-EARS-VERSION-001`にも付けない。
"""

import json
import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from bitz import check as check_mod
from bitz import config as config_mod
from bitz import doctor
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
EARS_ACTION = "設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください"
CORE_ACTION = "CPython 3.12以上でCoreを実行してください"
PLUGIN_ACTION = "--plugin、--plugin-version、--require-core-apiを同時に指定してください"
GIT_ACTION = "Git 2.30以上をインストールし、ワークスペースをGitのリポジトリで管理してください"
FULL = ["--plugin", "bitz-sdd", "--plugin-version", "1.2.3"]


def _cwd_action(name):
    return f"設定キーverify.commands.{name}.cwdのディレクトリを作成するか、正しいパスを指定してください"


def _file_action(name):
    return f"設定キーverify.commands.{name}.argvの先頭の実行可能ファイルをインストールするか、正しいパスを指定してください"


class DoctorSuggestedActionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "-q", str(self.root)], env=self.env, check=True)
        self.write_config(".", CONFIG)

    def write_config(self, path, text):
        spec = self.root / path / ".spec"
        spec.mkdir(parents=True, exist_ok=True)
        (spec / "bitz.yaml").write_text(text, encoding="utf-8")

    def run_doctor(self, *args, env=None):
        return doctor.run(parse_argv(["doctor", "--format", "json", *args]), str(self.root), env or self.env)[0]

    @staticmethod
    def one(result, code):
        found = [d for d in result["diagnostics"] if d["code"] == code]
        assert len(found) == 1, (code, result["diagnostics"])
        return found[0]

    # --- プラグインの要求 ---------------------------------------------------------

    def test_plugin_incomplete_has_short_summary_and_action(self):
        diagnostic = self.one(self.run_doctor("--plugin", "bitz-sdd"), "SPEC-DOCTOR-PLUGIN-001")
        self.assertEqual(diagnostic["summary"], "プラグインの要求が不完全です")
        self.assertEqual(diagnostic["suggestedAction"], PLUGIN_ACTION)

    def test_api_incompatible_interpolates_required_range_as_given(self):
        for required in ("^2.0", ">=1.1 <2.0"):
            with self.subTest(required=required):
                result = self.run_doctor(*FULL, "--require-core-api", required)
                diagnostic = self.one(result, "SPEC-DOCTOR-API-001")
                self.assertEqual(diagnostic["evidence"]["required"], required)
                self.assertEqual(
                    diagnostic["suggestedAction"],
                    f"範囲{required}を満たすCoreへ更新するか、Core APIのバージョン1.0に対応するプラグインを使ってください",
                )

    def test_capability_missing_joins_sorted_names(self):
        result = self.run_doctor(
            *FULL, "--require-core-api", "^1.0",
            "--require-capability", "zeta.v1", "--require-capability", "alpha.v1", "--require-capability", "zeta.v1",
        )
        diagnostic = self.one(result, "SPEC-DOCTOR-CAPABILITY-001")
        self.assertEqual(diagnostic["evidence"]["missing"], ["alpha.v1", "zeta.v1"])
        self.assertEqual(
            diagnostic["suggestedAction"],
            "対応機能alpha.v1、zeta.v1を公開するCoreへ更新するか、プラグインの要求を見直してください",
        )

    def test_capability_missing_single_name(self):
        result = self.run_doctor(*FULL, "--require-core-api", "^1.0", "--require-capability", "nope.v1")
        self.assertEqual(
            self.one(result, "SPEC-DOCTOR-CAPABILITY-001")["suggestedAction"],
            "対応機能nope.v1を公開するCoreへ更新するか、プラグインの要求を見直してください",
        )

    # --- Core・Git ----------------------------------------------------------------

    def test_runtime_version_single_and_all_workspaces(self):
        old = types.SimpleNamespace(version_info=(3, 11, 0))
        with patch.object(doctor, "sys", old):
            single = self.run_doctor()
            self.write_config(".", CONFIG + "multiWorkspace:\n  members: []\n")
            multi = doctor.run(parse_argv(["doctor", "--all-workspaces"]), str(self.root), self.env)[0]
        self.assertEqual(self.one(single, "SPEC-DOCTOR-CORE-001")["suggestedAction"], CORE_ACTION)
        self.assertEqual(self.one(multi, "SPEC-DOCTOR-CORE-001")["suggestedAction"], CORE_ACTION)
        self.assertNotIn("SPEC-DOCTOR-CORE-002", [d["code"] for d in single["diagnostics"] + multi["diagnostics"]])

    def test_git_degraded_has_action(self):
        result = self.run_doctor(env={"PATH": "/dev/null"})
        self.assertEqual(self.one(result, "SPEC-DOCTOR-GIT-001")["suggestedAction"], GIT_ACTION)

    # --- EARS-AI ------------------------------------------------------------------

    def test_ears_version_single_workspace(self):
        self.write_config(".", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\n')
        self.assertEqual(self.one(self.run_doctor(), "SPEC-DOCTOR-EARS-001")["suggestedAction"], EARS_ACTION)

    def test_ears_version_in_all_workspaces_member(self):
        self.write_config(".", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n"
                          "    - id: web\n      path: apps/web\n")
        self.write_config("apps/web", CONFIG + "workspace:\n  id: web\n")
        original = doctor.multiws.precheck

        def precheck_then_change(*args, **kwargs):
            result = original(*args, **kwargs)
            # 全体事前検査を通過した後で、メンバーのEARS-AIのメジャーバージョンを非互換にする。
            self.write_config("apps/web", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\nworkspace:\n  id: web\n')
            return result

        with patch.object(doctor.multiws, "precheck", side_effect=precheck_then_change):
            result, _ = doctor.run(parse_argv(["doctor", "--all-workspaces"]), str(self.root), self.env)
        web = next(w for w in result["workspaces"] if w["id"] == "web")
        self.assertEqual(self.one(web, "SPEC-DOCTOR-EARS-001")["suggestedAction"], EARS_ACTION)

    def test_ears_version_of_root_in_all_workspaces_uses_doctor_code(self):
        # 全体事前検査がルートの設定のEARS-AIのメジャーバージョンの非互換で停止する経路でも、doctorの診断コードと修復手順を返す
        # （診断レジストリの`DOCTOR-EARS-VERSION`。`check`用の`SPEC-EARS-VERSION-001`を返さない。実装の確認事項C31）。
        self.write_config(".", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\nworkspace:\n  id: platform\n'
                          "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
        self.write_config("apps/web", CONFIG + "workspace:\n  id: web\n")
        result, code = doctor.run(parse_argv(["doctor", "--all-workspaces", "--format", "json"]), str(self.root), self.env)
        self.assertEqual(code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertNotIn("SPEC-EARS-VERSION-001", codes)
        self.assertEqual(self.one(result, "SPEC-DOCTOR-EARS-001")["suggestedAction"], EARS_ACTION)

    def test_check_ears_version_has_no_suggested_action(self):
        outcome = config_mod.load_config(b'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\n')
        diagnostics = [d.to_dict() for d in outcome.diagnostics]
        self.assertEqual([d["code"] for d in diagnostics], ["SPEC-EARS-VERSION-001"])
        self.assertNotIn("suggestedAction", diagnostics[0])
        self.write_config(".", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\n')
        result, _ = check_mod.run(parse_argv(["check", "--full", "--format", "json"]), str(self.root), self.env)
        found = [d for d in result["diagnostics"] if d["code"] == "SPEC-EARS-VERSION-001"]
        self.assertEqual(len(found), 1)
        self.assertNotIn("suggestedAction", found[0])

    # --- コマンド -----------------------------------------------------------------

    def test_command_cwd_and_file_use_command_name(self):
        self.write_config(".", CONFIG + "verify:\n  commands:\n"
                          "    alpha:\n      argv: [python]\n      cwd: absent\n"
                          "    beta:\n      argv: [./missing-command]\n      cwd: .\n")
        result = self.run_doctor()
        by_key = {d["source"]["key"]: d for d in result["diagnostics"] if d["code"] == "SPEC-DOCTOR-COMMAND-001"}
        self.assertEqual(by_key["verify.commands.alpha.cwd"]["suggestedAction"], _cwd_action("alpha"))
        self.assertEqual(by_key["verify.commands.beta.argv"]["suggestedAction"], _file_action("beta"))

    def test_command_actions_in_all_workspaces_member(self):
        self.write_config(".", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n"
                          "    - id: api\n      path: services/api\n")
        self.write_config("services/api", CONFIG + "workspace:\n  id: api\nverify:\n  commands:\n"
                          "    alpha:\n      argv: [python]\n      cwd: absent\n"
                          "    beta:\n      argv: [./missing-command]\n      cwd: .\n")
        result, _ = doctor.run(parse_argv(["doctor", "--all-workspaces"]), str(self.root), self.env)
        api = next(w for w in result["workspaces"] if w["id"] == "api")
        by_key = {d["source"]["key"]: d for d in api["diagnostics"]}
        self.assertEqual(by_key["verify.commands.alpha.cwd"]["suggestedAction"], _cwd_action("alpha"))
        self.assertEqual(by_key["verify.commands.beta.argv"]["suggestedAction"], _file_action("beta"))

    # --- 付けない診断 -------------------------------------------------------------

    def test_dependency_diagnostics_have_no_suggested_action(self):
        self.write_config(".", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n"
                          "    - id: api\n      path: services/api\n")
        self.write_config("services/api", CONFIG + "workspace:\n  id: api\n")
        original = doctor.multiws.precheck

        def precheck_then_remove(*args, **kwargs):
            result = original(*args, **kwargs)
            (self.root / "services/api/.spec/bitz.yaml").unlink()
            return result

        with patch.object(doctor.multiws, "precheck", side_effect=precheck_then_remove):
            result, _ = doctor.run(parse_argv(["doctor", "--all-workspaces"]), str(self.root), self.env)
        api = next(w for w in result["workspaces"] if w["id"] == "api")
        dependencies = [d for d in api["diagnostics"] if d["code"] == "SPEC-MULTI-DEPENDENCY-001"]
        self.assertTrue(dependencies)
        for diagnostic in dependencies:
            self.assertNotIn("suggestedAction", diagnostic)


if __name__ == "__main__":
    unittest.main()
