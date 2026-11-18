"""`bitz --help`、`bitz <操作> --help`、`bitz --version`の単体試験（ADR-075、Core実行環境・CLI基盤契約 §5.1）。

- 各操作の`--help`は、操作仕様（`docs/03.詳細設計/03_操作仕様/0*.md`）の§2の公開構文を一字も変えずに含み、公開構文のすべての
  オプションを説明する。全体の`--help`は公開の4つの操作をすべて挙げる。
- `--help`と`--version`は、ワークスペースの外でも、Gitの実行ファイルがなくても、終了コード0で標準出力だけへ書く。Gitを呼ばず、
  ファイルを作らない。標準出力はロケールの文字コードによらずUTF-8で、改行で終わる。
- `--version`の1行は、`doctor`の結果の`core.version`と同じ値を使う。
- 操作の`--help`は、ほかの引数不正より優先する。完全に一致しない`--help=1`、未知の操作、ほかの要素を伴う`--version`は終了コード4のまま。
- 出力は`PYTHONHASHSEED`によらず同じである。
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bitz
from bitz import cli, messages
from bitz.cliargs import OPERATIONS, InfoRequest, detect_info_request

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATION_SPECS = REPO_ROOT / "docs" / "03.詳細設計" / "03_操作仕様"
SPEC_FILES = {
    "context": "01_context.md",
    "check": "02_check.md",
    "verify": "03_verify.md",
    "doctor": "04_doctor.md",
}
SOURCE_DIR = str(Path(bitz.__file__).resolve().parents[1])  # 試験対象のCoreのsrc（PYTHONPATHで差し替えた場合も追従する）
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'

INFO_ARGVS = (
    ["--help"],
    ["--help", "--no-such-option"],
    ["--version"],
    *([op, "--help"] for op in OPERATIONS),
)


def public_syntax(operation: str) -> list[str]:
    """操作仕様の§2の最初の`text`のコードブロック（公開構文）の行。"""
    text = (OPERATION_SPECS / SPEC_FILES[operation]).read_text(encoding="utf-8")
    section = text.split("\n## 2.", 1)[1].split("\n## 3.", 1)[0]
    match = re.search(r"```text\n(.*?)\n```", section, re.S)
    assert match is not None, operation
    return match.group(1).split("\n")


def run_in_process(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class InfoRequestDetectionTests(unittest.TestCase):
    def test_detection(self):
        cases = [
            (["--help"], InfoRequest("help")),
            (["--help", "--no-such-option"], InfoRequest("help")),
            (["--help", "--version"], InfoRequest("help")),
            (["--help", "foo"], InfoRequest("help")),
            (["check", "--help"], InfoRequest("help", "check")),
            (["check", "--no-such-option", "--help"], InfoRequest("help", "check")),
            (["verify", "REQ-001", "--help", "--timeout"], InfoRequest("help", "verify")),
            (["context", "REQ-001", "--purpose", "--help"], InfoRequest("help", "context")),
            (["check", "--full", "--full", "--help"], InfoRequest("help", "check")),
            (["check", "", "--help"], InfoRequest("help", "check")),
            (["check", "--format=json", "--help"], InfoRequest("help", "check")),
            (["doctor", "--help", "--help"], InfoRequest("help", "doctor")),
            (["--version"], InfoRequest("version")),
            ([], None),
            (["check"], None),
            (["foo", "--help"], None),
            (["check", "--help=1"], None),
            (["check", "--HELP"], None),
            (["check", "-h"], None),
            (["--version", "check"], None),
            (["--version", "--version"], None),
            (["check", "--version"], None),
            (["--version", "--help"], None),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(detect_info_request(argv), expected)


class HelpTextTests(unittest.TestCase):
    def test_top_help_lists_every_public_operation(self):
        code, out, err = run_in_process(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, messages.HELP_TOP)
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assertRegex(out, rf"(?m)^  {operation} ")
        self.assertIn("bitz --version", out)
        self.assertIn("bitz <操作> --help", out)

    def test_operation_help_contains_public_syntax_verbatim(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                code, out, err = run_in_process([operation, "--help"])
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(out, messages.HELP_BY_OPERATION[operation])
                syntax = public_syntax(operation)
                self.assertTrue(syntax[0].startswith(f"bitz {operation}"), syntax)
                block = "\n".join("  " + line for line in syntax) + "\n"
                self.assertIn(block, out)

    def test_operation_help_describes_every_option_of_public_syntax(self):
        for operation in OPERATIONS:
            options = sorted(set(re.findall(r"--[a-z][a-z-]*", "\n".join(public_syntax(operation)))))
            self.assertTrue(options, operation)
            out = messages.HELP_BY_OPERATION[operation]
            for option in [*options, "--help"]:
                with self.subTest(operation=operation, option=option):
                    # 構文の写しとは別に、オプションの説明の行（2字下げでオプション名から始まる行）がある。
                    self.assertRegex(out, rf"(?m)^  {re.escape(option)}( |$)")

    def test_positional_arguments_of_public_syntax_are_described(self):
        for operation in ("context", "check", "verify"):
            first = public_syntax(operation)[0]
            positional = re.search(r"<[a-z-]+>\.\.\.", first)
            self.assertIsNotNone(positional, first)
            with self.subTest(operation=operation):
                self.assertRegex(messages.HELP_BY_OPERATION[operation], rf"(?m)^  {re.escape(positional.group(0))}$")

    def test_texts_are_non_empty_and_end_with_newline(self):
        for text in [messages.HELP_TOP, *messages.HELP_BY_OPERATION.values(), messages.version_line("1.0.0")]:
            self.assertTrue(text.strip())
            self.assertTrue(text.endswith("\n"))
            self.assertFalse(text.endswith("\n\n"))
            self.assertNotRegex(text, r"[\x00-\x09\x0b-\x1f\x7f]")
        self.assertEqual(set(messages.HELP_BY_OPERATION), set(OPERATIONS))

    def test_operation_help_takes_priority_over_argument_errors(self):
        for argv in (
            ["check", "--no-such-option", "--help"],
            ["verify", "REQ-001", "--help", "--timeout"],
            ["context", "REQ-001", "--purpose", "--help"],
            ["check", "--full", "--full", "--help"],
            ["check", "", "--help"],
            ["check", "--format=json", "--help"],
            ["doctor", "--help", "--help"],
            ["context", "--help"],
        ):
            with self.subTest(argv=argv):
                code, out, err = run_in_process(argv)
                self.assertEqual((code, out, err), (0, messages.HELP_BY_OPERATION[argv[0]], ""))

    def test_non_matching_forms_keep_exit_code_4(self):
        for argv, context in (
            (["foo", "--help"], "(no-operation)"),
            (["check", "--help=1"], "check"),
            (["--version", "check"], "(no-operation)"),
            (["--version", "--version"], "(no-operation)"),
            (["check", "--version"], "check"),
        ):
            with self.subTest(argv=argv):
                code, out, err = run_in_process(argv)
                self.assertEqual((code, out), (4, ""))
                self.assertTrue(err.startswith(f"bitz: {context}: "), err)
                self.assertEqual(err.count("\n"), 1)


class SubprocessTests(unittest.TestCase):
    """コンソールスクリプトと同じ`bitz.cli`を別プロセスで起動し、環境に依存しないことを確かめる。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.empty_bin = self.base / "empty-bin"
        self.empty_bin.mkdir()
        self.outside = self.base / "outside"  # ワークスペースでもGitのリポジトリでもないディレクトリ
        self.outside.mkdir()
        self.env = {
            **os.environ,
            "PYTHONPATH": SOURCE_DIR,
            "GIT_CEILING_DIRECTORIES": str(self.base),
        }

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, argv, *, cwd, env=None):
        return subprocess.run(
            [sys.executable, "-m", "bitz.cli", *argv], cwd=cwd, env=env or self.env,
            capture_output=True, timeout=60,
        )

    def snapshot(self, root: Path) -> list[str]:
        return sorted(str(p.relative_to(root)) for p in root.rglob("*"))

    def assert_info_output(self, proc, argv):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        text = proc.stdout.decode("utf-8")  # UTF-8であること
        if argv == ["--version"]:
            expected = messages.version_line(self.doctor_core_version())
        elif argv[0] == "--help":
            expected = messages.HELP_TOP
        else:
            expected = messages.HELP_BY_OPERATION[argv[0]]
        self.assertEqual(text, expected)

    def doctor_core_version(self) -> str:
        repo = self.base / "repo"
        if not repo.exists():
            (repo / ".spec").mkdir(parents=True)
            (repo / ".spec" / "bitz.yaml").write_text(CONFIG, encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(repo)], env=self.env, check=True, capture_output=True)
        proc = self.run_cli(["doctor", "--format", "json"], cwd=repo)
        return json.loads(proc.stdout.decode("utf-8"))["core"]["version"]

    def test_runs_outside_any_workspace_and_creates_nothing(self):
        for argv in INFO_ARGVS:
            with self.subTest(argv=argv):
                proc = self.run_cli(argv, cwd=self.outside)
                self.assert_info_output(proc, argv)
                self.assertEqual(self.snapshot(self.outside), [])

    def test_runs_without_git_on_path(self):
        env = {**self.env, "PATH": str(self.empty_bin)}
        for argv in INFO_ARGVS:
            with self.subTest(argv=argv):
                self.assert_info_output(self.run_cli(argv, cwd=self.outside, env=env), argv)

    def test_does_not_invoke_git(self):
        # PATHの先頭に、呼ばれたら印のファイルを作るgitを置く。`--help`と`--version`の後に印がなければ、Gitを呼んでいない。
        shim_dir = self.base / "shim-bin"
        shim_dir.mkdir()
        marker = self.base / "git-called"
        shim = shim_dir / "git"
        shim.write_text(f"#!/bin/sh\necho called >> '{marker}'\nexit 1\n", encoding="utf-8")
        shim.chmod(0o755)
        env = {**self.env, "PATH": f"{shim_dir}{os.pathsep}{self.env.get('PATH', '')}"}
        repo = self.base / "broken"
        (repo / ".spec").mkdir(parents=True)
        (repo / ".spec" / "bitz.yaml").write_text('schemaVersion: "1.0"\nearsAi: [\n', encoding="utf-8")
        for cwd in (self.outside, repo):
            for argv in INFO_ARGVS:
                with self.subTest(cwd=cwd.name, argv=argv):
                    self.assert_info_output(self.run_cli(argv, cwd=cwd, env=env), argv)
                    self.assertFalse(marker.exists())
        # 対照: 印のファイルで呼出しを観測できることを、通常の操作で確かめる。
        self.run_cli(["doctor", "--format", "json"], cwd=self.outside, env=env)
        self.assertTrue(marker.exists())

    def test_report_is_not_written(self):
        repo = self.base / "ws"
        (repo / ".spec").mkdir(parents=True)
        (repo / ".spec" / "bitz.yaml").write_text(CONFIG, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(repo)], env=self.env, check=True, capture_output=True)
        before = self.snapshot(repo)
        for argv in (["check", "--format", "json", "--report", "--help"], ["verify", "REQ-001", "--report", "--help"]):
            with self.subTest(argv=argv):
                self.assert_info_output(self.run_cli(argv, cwd=repo), argv)
                self.assertEqual(self.snapshot(repo), before)
        self.assertFalse((repo / ".spec" / "reports").exists())

    def test_stdout_is_utf8_regardless_of_locale_encoding(self):
        env = {**self.env, "PYTHONIOENCODING": "ascii", "LC_ALL": "C", "PYTHONUTF8": "0"}
        for argv in (["--help"], ["check", "--help"], ["--version"]):
            with self.subTest(argv=argv):
                self.assert_info_output(self.run_cli(argv, cwd=self.outside, env=env), argv)

    def test_version_matches_doctor_core_version(self):
        proc = self.run_cli(["--version"], cwd=self.outside)
        core_version = self.doctor_core_version()
        self.assertEqual(proc.stdout, f"bitz {core_version}\n".encode("utf-8"))
        self.assertRegex(core_version, r"^[0-9]+\.[0-9]+\.[0-9]+$")

    def test_output_is_independent_of_hash_seed(self):
        for argv in INFO_ARGVS:
            outputs = set()
            for seed in ("0", "1", "12345"):
                proc = self.run_cli(argv, cwd=self.outside, env={**self.env, "PYTHONHASHSEED": seed})
                outputs.add((proc.returncode, proc.stdout, proc.stderr))
            with self.subTest(argv=argv):
                self.assertEqual(len(outputs), 1)


if __name__ == "__main__":
    unittest.main()
