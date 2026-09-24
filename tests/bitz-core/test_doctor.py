"""`bitz doctor`のconfig／schema／ears check分離に対する単体試験。

レビュー是正: Schema major非互換ならchecksは`core, workspace, config(passed), schema(blocked), git`
とし、EARS-AI major非互換なら`ears`もその後に続けてblockedとする。いずれもcommand／impactは
依存出力がないため出さない。
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import doctor
from bitz.cliargs import parse_argv


def _init_repo(root: Path, bitz_yaml: str) -> None:
    (root / ".spec").mkdir(parents=True)
    (root / ".spec" / "bitz.yaml").write_text(bitz_yaml, encoding="utf-8")
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, env=env, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
        cwd=root,
        env=env,
        check=True,
    )


class DoctorCheckStageTests(unittest.TestCase):
    def _run_doctor(self, bitz_yaml: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, bitz_yaml)
            parsed = parse_argv(["doctor", "--format", "json"])
            env = dict(os.environ)
            result, exit_code = doctor.run(parsed, str(root), env)
            return result, exit_code

    def test_schema_major_mismatch_yields_dedicated_schema_check(self):
        result, exit_code = self._run_doctor('schemaVersion: "2.0"\nlanguage: ja\nearsAi: "1.0"\n')
        names = [c["name"] for c in result["checks"]]
        self.assertEqual(names, ["core", "workspace", "config", "schema", "git"])
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["config"]["status"], "passed")
        self.assertEqual(by_name["schema"]["status"], "blocked")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(exit_code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("SPEC-CONFIG-SCHEMA-001", codes)

    def test_ears_major_mismatch_yields_dedicated_ears_check(self):
        result, exit_code = self._run_doctor('schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\n')
        names = [c["name"] for c in result["checks"]]
        self.assertEqual(names, ["core", "workspace", "config", "schema", "ears", "git"])
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["schema"]["status"], "passed")
        self.assertEqual(by_name["ears"]["status"], "blocked")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(exit_code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("SPEC-DOCTOR-EARS-001", codes)

    def test_config_type_error_stops_before_schema_check(self):
        result, _ = self._run_doctor('schemaVersion: "1.0"\nlanguage: 1\nearsAi: "1.0"\n')
        names = [c["name"] for c in result["checks"]]
        self.assertEqual(names, ["core", "workspace", "config", "git"])
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["config"]["status"], "error")

    def test_config_warning_only_maps_to_warning_check_status(self):
        result, _ = self._run_doctor(
            'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nfutureOption: true\n'
        )
        by_name = {c["name"]: c for c in result["checks"]}
        self.assertEqual(by_name["config"]["status"], "warning")
        self.assertEqual(result["status"], "passed_with_warnings")


if __name__ == "__main__":
    unittest.main()
