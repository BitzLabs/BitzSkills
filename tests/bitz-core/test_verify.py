"""`bitz verify`（`verify.py`）の単体試験（`03_操作仕様/03_verify.md`）。

時間のかかる試験（timeout系）はtimeoutSecondsを小さくし、数秒で終わるようにする。
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import verify as verify_mod
from bitz.cliargs import parse_argv


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _make_executable(root: str, rel_path: str, body: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(body)
    os.chmod(full, os.stat(full).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _req(doc_id: str, tests_block: str | None = None, status: str = "approved") -> str:
    if tests_block is None:
        tests_block = (
            f"tests:\n  - path: tests/test_auth.py\n    covers: [{doc_id}:AC-01]\n"
            "    command: default\n"
        )
    return f"""---
id: {doc_id}
title: 検査対象
status: {status}
{tests_block}---

# {doc_id} 検査対象

## Intent

意図。

## Acceptance Criteria

- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

test/test_auth.pyで確認する。
"""


def _bitz_yaml(commands_block: str, timeout: str = "") -> str:
    return f'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nverify:\n{timeout}  commands:\n{commands_block}'


def _init_repo(root: str) -> None:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, env=env, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
        cwd=root,
        env=env,
        check=True,
    )


def _run_verify(root: str, positionals: list, *, fmt: str = "json", timeout: str | None = None, env_extra=None):
    single = {"--format": fmt}
    if timeout is not None:
        single["--timeout"] = timeout
    argv = ["verify", *positionals, "--format", fmt]
    if timeout is not None:
        argv += ["--timeout", timeout]
    parsed = parse_argv(argv)
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return verify_mod.run(parsed, root, env)


class BindingPlanTests(unittest.TestCase):
    def _setup_two_targets_shared_command(self, tmp: str) -> None:
        _write(
            tmp,
            ".spec/bitz.yaml",
            _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'),
        )
        _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(tmp, ".spec/requirements/REQ-002.md", _req("REQ-002"))
        _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
        _init_repo(tmp)

    def test_same_workspace_same_command_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._setup_two_targets_shared_command(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001", "REQ-002"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(result["commands"][0]["bindingId"], "root::default")
        # 両targetが同じbindingを参照する。
        refs = {ref for t in result["targetResults"] for ref in t["bindingRefs"]}
        self.assertEqual(refs, {"root::default"})

    def test_duplicate_test_path_deduped_in_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'),
            )
            tests_block = (
                "tests:\n  - path: tests/test_auth.py\n    covers: [REQ-001:AC-01]\n"
                "    command: default\n"
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001", tests_block))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 0)
        argv = result["commands"][0]["argv"]
        self.assertEqual(argv.count("tests/test_auth.py"), 1)

    def test_no_tests_placeholder_runs_argv_once_regardless_of_path_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["commands"][0]["argv"], ["/bin/true"])


class TargetStatusAggregationTests(unittest.TestCase):
    def test_verified_target_has_passed_command_and_nonnull_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 0)
        target = result["targetResults"][0]
        self.assertEqual(target["status"], "passed")
        self.assertIsNotNone(target["contextDigest"])
        self.assertEqual(len(target["bindingRefs"]), 1)
        [command] = [c for c in result["commands"] if c["bindingId"] == target["bindingRefs"][0]]
        self.assertEqual(command["status"], "passed")

    def test_failing_command_marks_target_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/false", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["targetResults"][0]["status"], "failed")


class BindingMissingTests(unittest.TestCase):
    def test_undefined_command_keeps_context_digest_and_reports_each_binding(self):
        # C6（SINGLE-061訂正）: testまたはcommand定義そのものが不足しbindingを構成できない
        # 場合（skip-target）でも、Contextを構成できる限りcontextDigestは非nullで返し、
        # 独立した原因（testエントリ単位）はそれぞれDiagnosticを返す（verify仕様 §8、
        # registry §2）。
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, ".spec/bitz.yaml", _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'))
            _write(
                tmp,
                ".spec/technical/TECH-001.md",
                """---
id: TECH-001
title: 検査対象
status: approved
relations:
  refines: [REQ-001]
implements: [src/x.py]
tests:
  - path: tests/test_a.py
    covers: [REQ-001:AC-01]
    command: missing
  - path: tests/test_b.py
    covers: [REQ-001:AC-02]
    command: missing
---

# TECH-001 検査対象

## Context

規範文を持たない。
""",
            )
            _write(
                tmp,
                ".spec/requirements/REQ-001.md",
                """---
id: REQ-001
title: 検査対象
status: approved
---

# REQ-001 検査対象

## Intent

意図。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。
- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

test/test_a.pyとtest/test_b.pyで確認する。
""",
            )
            _write(tmp, "tests/test_a.py", "def test_a():\n    assert True\n")
            _write(tmp, "tests/test_b.py", "def test_b():\n    assert True\n")
            _write(tmp, "src/x.py", "x = 1\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 2)
        target = result["targetResults"][0]
        self.assertEqual(target["status"], "blocked")
        self.assertIsNotNone(target["contextDigest"])
        self.assertEqual(target["bindingRefs"], [])
        codes = [d["code"] for d in target["diagnostics"]]
        self.assertEqual(codes, ["SPEC-VERIFY-BLOCKED-001", "SPEC-VERIFY-BLOCKED-001"])
        keys = sorted(d["source"]["key"] for d in target["diagnostics"])
        self.assertEqual(keys, ["tests[0].command", "tests[1].command"])


class SpawnBeforeBlockedTests(unittest.TestCase):
    def test_untracked_config_blocks_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            # commitの後にbitz.yamlを未追跡で追加する。
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'),
            )
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("SPEC-VERIFY-BLOCKED-001", codes)
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["targetResults"][0]["bindingRefs"], [])

    def test_missing_executable_blocks_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["bitz-test-absent-tool", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 2)
        diag = result["diagnostics"][0]
        self.assertEqual(diag["code"], "SPEC-VERIFY-BLOCKED-001")
        self.assertEqual(diag["source"]["kind"], "environment")

    def test_cwd_unavailable_blocks_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: absent-dir\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("SPEC-VERIFY-BLOCKED-001", codes)
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["targetResults"][0]["bindingRefs"], [])

    def test_test_path_outside_cwd_blocks_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: subdir\n'),
            )
            _write(tmp, "subdir/.keep", "")
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 2)
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("SPEC-VERIFY-BLOCKED-001", codes)
        self.assertEqual(result["commands"], [])


class TerminationReasonTests(unittest.TestCase):
    def test_exit_zero_and_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, _ = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(result["commands"][0]["termination"], "exit")
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_signal_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_executable(tmp, "bin/signal.sh", "#!/bin/sh\nkill -TERM $$\n")
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["bin/signal.sh", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 3)
        command = result["commands"][0]
        self.assertEqual(command["termination"], "signal")
        self.assertIsNone(command["exitCode"])
        self.assertEqual(command["status"], "error")

    def test_timeout_termination_within_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_executable(
                tmp,
                "bin/hang.sh",
                "#!/bin/sh\ntrap '' TERM\necho ready\nsleep 60\n",
            )
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["bin/hang.sh", "{tests}"]\n      cwd: .\n', timeout="  timeoutSeconds: 1\n"),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"])
        self.assertEqual(exit_code, 3)
        command = result["commands"][0]
        self.assertEqual(command["termination"], "timeout")
        self.assertIsNone(command["exitCode"])
        self.assertEqual(command["stdoutExcerpt"], "ready\n")


class EnvironmentTests(unittest.TestCase):
    def test_pwd_is_set_to_effective_cwd_and_other_vars_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_executable(
                tmp,
                "bin/probe.sh",
                "#!/bin/sh\n"
                'if [ "$PWD" != "$(pwd)" ]; then exit 1; fi\n'
                'if [ "$BITZ_TEST_MARKER" != "kept" ]; then exit 2; fi\n'
                "exit 0\n",
            )
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["bin/probe.sh", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, exit_code = _run_verify(tmp, ["REQ-001"], env_extra={"BITZ_TEST_MARKER": "kept"})
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["commands"][0]["status"], "passed")

    def test_env_var_values_never_appear_in_result_json(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            _make_executable(
                tmp,
                "bin/echoenv.sh",
                "#!/bin/sh\necho \"$BITZ_TEST_SECRET_TOKEN\"\n",
            )
            _write(
                tmp,
                ".spec/bitz.yaml",
                _bitz_yaml('    default:\n      argv: ["bin/echoenv.sh", "{tests}"]\n      cwd: .\n'),
            )
            _write(tmp, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(tmp, "tests/test_auth.py", "def test_x():\n    assert True\n")
            _init_repo(tmp)
            result, _ = _run_verify(
                tmp, ["REQ-001"], env_extra={"BITZ_TEST_SECRET_TOKEN": "super-secret-value-12345"}
            )
        # 出力自体はredactionで置換され、シリアライズ結果に元の値が残らない。
        dumped = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("super-secret-value-12345", dumped)
        self.assertIn("[REDACTED]", result["commands"][0]["stdoutExcerpt"])


if __name__ == "__main__":
    unittest.main()
