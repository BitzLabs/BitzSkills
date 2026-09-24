"""参照適合harness(`runner.py`、`package_check.py`)のCoreに依存しない単体試験。

`uv run --with jsonschema==4.23.0 python -m unittest fixtures.conformance.test_runner`
(repository rootから)、または`uv run -m unittest fixtures/conformance/test_runner.py`で実行できる。
Coreを起動せず、normalizer、text置換、終了コード4の出力判定、Git shim、package_checkだけを検査する。
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from conformance import package_check
from conformance.runner import build_git_shim, diff_json, normalize_result, normalize_text, _check_cli_output


class NormalizeResultTests(unittest.TestCase):
    def test_durationMs_excluded_at_any_depth(self):
        value = {"durationMs": 12, "workspaces": [{"durationMs": 3, "commands": [{"durationMs": 4, "name": "x"}]}]}
        normalized, warnings = normalize_result(value)
        self.assertEqual(warnings, [])
        self.assertNotIn("durationMs", normalized)
        self.assertNotIn("durationMs", normalized["workspaces"][0])
        self.assertNotIn("durationMs", normalized["workspaces"][0]["commands"][0])
        self.assertEqual(normalized["workspaces"][0]["commands"][0]["name"], "x")

    def test_valid_commit_becomes_placeholder(self):
        commit = "a" * 40
        value = {"revision": {"base": commit, "commit": commit, "dirty": False}}
        normalized, warnings = normalize_result(value)
        self.assertEqual(warnings, [])
        self.assertEqual(normalized["revision"]["base"], "0" * 40)
        self.assertEqual(normalized["revision"]["commit"], "0" * 40)

    def test_invalid_commit_is_rejected_not_silently_normalized(self):
        value = {"revision": {"base": "not-a-commit", "commit": "A" * 40, "dirty": False}}
        normalized, warnings = normalize_result(value)
        self.assertEqual(len(warnings), 2)
        self.assertEqual(normalized["revision"]["base"], "not-a-commit")
        self.assertEqual(normalized["revision"]["commit"], "A" * 40)

    def test_core_version_patch_excluded(self):
        value = {"core": {"version": "1.0.7", "apiVersion": "1.0"}}
        normalized, warnings = normalize_result(value)
        self.assertEqual(warnings, [])
        self.assertEqual(normalized["core"]["version"], "1.0")

    def test_original_value_not_mutated(self):
        value = {"durationMs": 1}
        normalize_result(value)
        self.assertEqual(value["durationMs"], 1)

    def test_diff_json_matches_after_normalization(self):
        expected = {"durationMs": 1, "status": "passed"}
        actual = {"durationMs": 999, "status": "passed"}
        normalized_expected, _ = normalize_result(expected)
        normalized_actual, _ = normalize_result(actual)
        self.assertEqual(diff_json(normalized_expected, normalized_actual), [])

    def test_diff_json_reports_short_pointer_path(self):
        diffs = diff_json({"a": {"b": 1}}, {"a": {"b": 2}})
        self.assertEqual(len(diffs), 1)
        path, expected, actual = diffs[0]
        self.assertEqual(path, "$/a/b")
        self.assertEqual((expected, actual), ("1", "2"))

    def test_diff_json_detects_array_length_and_order(self):
        self.assertEqual(diff_json([1, 2], [1, 2]), [])
        self.assertTrue(diff_json([1, 2], [2, 1]))
        self.assertTrue(diff_json([1, 2], [1, 2, 3]))


class NormalizeTextTests(unittest.TestCase):
    def test_single_duration_token_replaced(self):
        self.assertEqual(normalize_text("done (12ms)"), "done (<duration>ms)")

    def test_multiple_tokens_on_one_line_replaced(self):
        text = "a (1ms) b (23ms)"
        self.assertEqual(normalize_text(text), "a (<duration>ms) b (<duration>ms)")

    def test_non_duration_parentheses_untouched(self):
        self.assertEqual(normalize_text("note (see docs)"), "note (see docs)")

    def test_surrounding_text_and_counts_not_removed(self):
        actual = normalize_text("passed 3 statements (5ms)")
        expected = normalize_text("passed 3 statements (999ms)")
        self.assertEqual(actual, expected)
        self.assertNotEqual(normalize_text("passed 4 statements (5ms)"), expected)


class CliOutputTests(unittest.TestCase):
    def _fixture(self, tmp, cli_output, exit_code):
        fixture_root = Path(tmp)
        (fixture_root / "cli-output.json").write_text(json.dumps(cli_output), encoding="utf-8")
        manifest = {"expect": {"exitCode": exit_code}}
        return fixture_root, manifest

    def test_single_line_valid_output_has_no_differences(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"", b"bitz: check: reason\n")
        self.assertEqual(differences, [])

    def test_multiple_lines_rejected_when_one_expected(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"", b"bitz: check: a\nbitz: check: b\n")
        self.assertTrue(any("stderrLineCount" in d for d in differences))

    def test_prefix_mismatch_rejected(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"", b"unexpected: reason\n")
        self.assertTrue(any("stderrPrefix" in d for d in differences))

    def test_missing_reason_rejected_when_required(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"", b"bitz: check: \n")
        self.assertTrue(any("理由" in d for d in differences))

    def test_control_characters_rejected(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"", b"bitz: check: bad\x1b[31m\n")
        self.assertTrue(any("制御文字" in d for d in differences))

    def test_nonempty_stdout_rejected(self):
        cli_output = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
                      "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root, manifest = self._fixture(tmp, cli_output, 4)
            differences = _check_cli_output(fixture_root, manifest, 4, b"{}", b"bitz: check: reason\n")
        self.assertTrue(any("stdout" in d for d in differences))


class GitShimTests(unittest.TestCase):
    def test_version_argv_reports_faked_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim_dir = build_git_shim(Path(tmp) / "shim", "2.99.0")
            result = subprocess.run([str(shim_dir / "git"), "--version"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "git version 2.99.0\n")

    def test_other_argv_passed_through_to_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_tree = Path(tmp) / "repo"
            work_tree.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=work_tree, timeout=10, check=True)
            shim_dir = build_git_shim(Path(tmp) / "shim", "2.99.0")
            shimmed = subprocess.run([str(shim_dir / "git"), "rev-parse", "--is-inside-work-tree"],
                                      cwd=work_tree, capture_output=True, text=True, timeout=10)
            real = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                                   cwd=work_tree, capture_output=True, text=True, timeout=10)
        self.assertEqual(shimmed.stdout, real.stdout)
        self.assertEqual(shimmed.returncode, real.returncode)


def _write_wheel(path, requires_dist=(), include_init=True, name="bitz", version="1.0.0"):
    with zipfile.ZipFile(path, "w") as archive:
        if include_init:
            archive.writestr(f"{name}/__init__.py", "")
        metadata_lines = [f"Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
        metadata_lines.extend(f"Requires-Dist: {requirement}" for requirement in requires_dist)
        archive.writestr(f"{name}-{version}.dist-info/METADATA", "\n".join(metadata_lines) + "\n")


class PackageCheckMetadataTests(unittest.TestCase):
    def _pyproject(self, root, requires_python='">=3.12"', with_script=True):
        script = 'bitz = "bitz.cli:main"' if with_script else ""
        (root / "pyproject.toml").write_text(
            "[project]\n"
            'name = "bitz"\n'
            f"requires-python = {requires_python}\n"
            + ('[project.scripts]\n' + script + "\n" if with_script else ""),
            encoding="utf-8")

    def test_accepted_when_name_script_wheel_and_venv_all_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._pyproject(root)
            wheel = root / "bitz-1.0.0-py3-none-any.whl"
            _write_wheel(wheel)
            venv = root / "venv"
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "bitz").write_text("#!/bin/sh\n", encoding="utf-8")
            outcome, reasons = package_check.check("metadata", root, wheel, venv)
        self.assertEqual((outcome, reasons), ("accepted", []))

    def test_rejected_when_requires_python_excludes_312(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._pyproject(root, requires_python='"<3.10"')
            wheel = root / "bitz-1.0.0-py3-none-any.whl"
            _write_wheel(wheel)
            venv = root / "venv"
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "bitz").write_text("#!/bin/sh\n", encoding="utf-8")
            outcome, reasons = package_check.check("metadata", root, wheel, venv)
        self.assertEqual(outcome, "rejected")
        self.assertTrue(any("requires-python" in reason for reason in reasons))

    def test_rejected_when_console_script_missing_from_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._pyproject(root)
            wheel = root / "bitz-1.0.0-py3-none-any.whl"
            _write_wheel(wheel)
            venv = root / "venv"
            (venv / "bin").mkdir(parents=True)
            outcome, reasons = package_check.check("metadata", root, wheel, venv)
        self.assertEqual(outcome, "rejected")
        self.assertTrue(any("bin/bitz" in reason for reason in reasons))

    def test_wheel_only_input_is_incomparable_not_rejected(self):
        # source treeが無いと「検査できたが要件未達」(rejected)と「検査できない」(error)を
        # 区別できないため、harness側のPackageCheckError(比較不能)にする。
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "bitz-1.0.0-py3-none-any.whl"
            _write_wheel(wheel)
            with self.assertRaises(package_check.PackageCheckError):
                package_check.check("metadata", None, wheel, Path(tmp) / "venv")

    def test_missing_pyproject_in_given_source_dir_is_incomparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheel = root / "bitz-1.0.0-py3-none-any.whl"
            _write_wheel(wheel)
            with self.assertRaises(package_check.PackageCheckError):
                package_check.check("metadata", root, wheel, root / "venv")


class PackageCheckDependenciesTests(unittest.TestCase):
    def _project(self, root, dependency="ruamel.yaml==0.18.6"):
        (root / "pyproject.toml").write_text(
            "[project]\nname = \"bitz\"\n" + f'dependencies = ["{dependency}"]\n', encoding="utf-8")

    def _lock(self, root, dep_name="ruamel-yaml", dep_version="0.18.6", extra_dependency=None):
        deps = [dep_name] if extra_dependency is None else [dep_name, extra_dependency]
        lines = ["[[package]]", 'name = "bitz"', 'version = "1.0.0"',
                 "dependencies = [" + ", ".join(f'{{ name = "{d}" }}' for d in deps) + "]", "",
                 "[[package]]", f'name = "{dep_name}"', f'version = "{dep_version}"']
        if extra_dependency:
            lines += ["", "[[package]]", f'name = "{extra_dependency}"', 'version = "1.0"']
        (root / "uv.lock").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _venv_with_dist_infos(self, root, names):
        site_packages = root / "venv" / "lib" / "python3.12" / "site-packages"
        site_packages.mkdir(parents=True)
        for name in names:
            (site_packages / name).mkdir()
        return root / "venv"

    def test_accepted_with_single_exact_pinned_yaml_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            self._lock(root)
            venv = self._venv_with_dist_infos(root, ["bitz-1.0.0.dist-info", "ruamel_yaml-0.18.6.dist-info"])
            outcome, reasons = package_check.check("dependencies", root, root / "unused.whl", venv)
        self.assertEqual((outcome, reasons), ("accepted", []))

    def test_rejected_when_dependency_is_not_exact_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root, dependency="ruamel.yaml>=0.18")
            self._lock(root)
            venv = self._venv_with_dist_infos(root, ["bitz-1.0.0.dist-info", "ruamel_yaml-0.18.6.dist-info"])
            outcome, reasons = package_check.check("dependencies", root, root / "unused.whl", venv)
        self.assertEqual(outcome, "rejected")
        self.assertTrue(any("exact pin" in reason for reason in reasons))

    def test_rejected_when_extra_runtime_dependency_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            self._lock(root, extra_dependency="extra-lib")
            venv = self._venv_with_dist_infos(
                root, ["bitz-1.0.0.dist-info", "ruamel_yaml-0.18.6.dist-info", "extra_lib-1.0.dist-info"])
            outcome, reasons = package_check.check("dependencies", root, root / "unused.whl", venv)
        self.assertEqual(outcome, "rejected")
        self.assertTrue(any("推移閉包" in reason for reason in reasons))

    def test_rejected_when_dist_info_count_does_not_match_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            self._lock(root)
            venv = self._venv_with_dist_infos(
                root, ["bitz-1.0.0.dist-info", "ruamel_yaml-0.18.6.dist-info", "stray-1.0.dist-info"])
            outcome, reasons = package_check.check("dependencies", root, root / "unused.whl", venv)
        self.assertEqual(outcome, "rejected")
        self.assertTrue(any("dist-info" in reason for reason in reasons))

    def test_wheel_only_input_is_incomparable_not_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(package_check.PackageCheckError):
                package_check.check("dependencies", None, Path(tmp) / "unused.whl", Path(tmp) / "venv")

    def test_missing_uv_lock_in_given_source_dir_is_incomparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            with self.assertRaises(package_check.PackageCheckError):
                package_check.check("dependencies", root, root / "unused.whl", root / "venv")


if __name__ == "__main__":
    unittest.main()
