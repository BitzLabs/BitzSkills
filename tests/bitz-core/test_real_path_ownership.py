"""所有と包含を実パスで判定する単体試験（確認事項 C88・C90・N1・N3）。

欠陥:
- N1: 複合ワークスペースの`implements`と`tests[].path`の所有は末端のシンボリックリンクしか見ず、上位のディレクトリの
  シンボリックリンク（`apps/web/ext -> ../../tests`）でメンバーが別のワークスペースのテストを所有できた。単一ワークスペースの
  パスの存在検査も上位を見ず、`ext -> <リポジトリの外>`の`ext/t.py`が通った。
- C88: `VERIFY-TEST-OUTSIDE-CWD`の判定が`os.path.relpath`による字句の判定だった。
- C90: 実効`cwd`とパスの所有の包含を文字列の前方一致で判定していた。
- N3: `VERIFY-TEST-OUTSIDE-CWD`の発生元が設定ファイルの`verify.commands.<名前>.cwd`だった。

規範:
- 複合ワークスペース仕様 §5.1の手順4・5: 実パスを得て、各上位のディレクトリと所有領域のルートのファイルシステム上の同一性
  （`os.path.samestat`）で包含を判定する。ルートワークスペースはメンバーの配下を所有しない。
- ワークスペース・設定仕様 §6: テストのパスと実効`cwd`の包含は、両方を実パスにして判定する。
- ワークスペース・設定仕様 §9: 単一ワークスペースの`implements`と`tests[].path`は、上位のシンボリックリンクを解決した実パスが
  ルートの配下にあるときだけ存在するパスとして扱う。外へ解決するパスと、末端がシンボリックリンクのパスは`SPEC-PATH-INVALID-001`。
- verify §5.1: `VERIFY-TEST-OUTSIDE-CWD`の発生元は、配下にないテストのパスを宣言した仕様文書（複数ならパスの辞書順で最初）、
  `key`はその文書の`tests[i].path`、テスト割当てごとに1件。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import types
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"check": check_mod, "verify": verify_mod}

TEST_BODY = "def test_t():\n    assert True\n"
# テストのパスの引数を、プロセスの作業ディレクトリから実際に開けるかを確かめる（argvの相対パスの検証）。
_FIND_ARGV = '["/bin/sh", "-c", "for f in \\"$@\\"; do test -f \\"$f\\" || exit 1; done", "sh", "{tests}"]'
_TRUE_ARGV = '["/bin/true", "{tests}"]'


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _commands(cwd: str, argv: str = _TRUE_ARGV) -> str:
    return f'verify:\n  commands:\n    t:\n      argv: {argv}\n      cwd: "{cwd}"\n'


def _req(doc_id: str, test_paths: list[str], *, implements: list[str] | None = None) -> str:
    """承認済みのREQ。``test_paths``の各パスを`tests[]`として宣言する（すべて同じ規範文をcoversする）。"""

    tests = "".join(
        f"  - path: {p}\n    covers: [{doc_id}:AC-01]\n    command: t\n" for p in test_paths
    )
    impl = "" if implements is None else "implements:\n" + "".join(f"  - {p}\n" for p in implements)
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n{impl}tests:\n{tests}---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {doc_id}:AC-01を守る。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str, test_paths: list[str], *, implements: list[str] | None = None) -> str:
    tests = "".join(f"  - path: {p}\n    covers: [{refines}:AC-01]\n    command: t\n" for p in test_paths)
    impl = "" if implements is None else "implements:\n" + "".join(f"  - {p}\n" for p in implements)
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の方針\nstatus: approved\nrelations:\n  refines: [{refines}:AC-01]\n"
        f"{impl}tests:\n{tests}---\n\n# {doc_id} {doc_id}の方針\n\n## Context\n\n実装する。\n"
    )


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # macOSなどで一時ディレクトリ自体がシンボリックリンクでも、実パスのルートを基準にする。
        self.tmp = Path(os.path.realpath(tmp.name))
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.outside = self.tmp / "outside"
        self.outside.mkdir()

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def link(self, name: str, target: str) -> None:
        full = self.root / name
        full.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, full)

    def run_op(self, op: str, *argv: str, cwd: Path | None = None):
        parsed = parse_argv([op, *argv, "--format", "json"])
        return _OPERATIONS[op].run(parsed, str(cwd or self.root), dict(os.environ))

    @staticmethod
    def all_diagnostics(result) -> list[dict]:
        diags = list(result["diagnostics"])
        for ws in result.get("workspaces", []):
            diags.extend(ws.get("diagnostics", []))
        for target in result.get("targetResults", []):
            diags.extend(target.get("diagnostics", []))
        return diags

    def codes(self, result) -> list[tuple[str, str | None, str | None, str | None]]:
        """``(コード, workspaceId, path, key)``の重複のない並び。"""

        return sorted(
            {
                (d["code"], d["source"].get("workspaceId"), d["source"].get("path"), d["source"].get("key"))
                for d in self.all_diagnostics(result)
            },
            key=repr,
        )


class _SingleBase(_Base):
    def write(self, cwd: str = ".", argv: str = _TRUE_ARGV, tests: list[str] | None = None, implements=None):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _commands(cwd, argv))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", tests or ["tests/t.py"], implements=implements))


class _MultiBase(_Base):
    """ルートワークスペースplatform（`tests/`を持つ）とメンバーweb（`apps/web`）。"""

    def write(
        self, *, web_tests: list[str], web_cwd: str = ".", root_tests: list[str] | None = None,
        root_cwd: str = ".", web_implements=None, root_implements=None, argv: str = _TRUE_ARGV,
    ):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            + _commands(root_cwd, argv),
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + _commands(web_cwd, argv))
        _write(
            self.root, ".spec/requirements/REQ-001.md",
            _req("REQ-001", root_tests or ["tests/test_platform.py"], implements=root_implements),
        )
        _write(self.root, "apps/web/.spec/requirements/REQ-101.md", _req("REQ-101", web_tests, implements=web_implements))
        _write(self.root, "tests/test_platform.py", TEST_BODY)
        _write(self.root, "src/platform.py", "x = 1\n")
        _write(self.root, "apps/web/tests/test_web.py", TEST_BODY)
        _write(self.root, "apps/web/src/web.py", "x = 1\n")


PATH_INVALID = "SPEC-PATH-INVALID-001"
OWNERSHIP = "SPEC-MULTI-OWNERSHIP-001"
BLOCKED = "SPEC-VERIFY-BLOCKED-001"


class SinglePathExistenceTests(_SingleBase):
    """単一ワークスペースの`implements`と`tests[].path`（ワークスペース・設定仕様 §9。N1）。"""

    def check_codes(self):
        result, _code = self.run_op("check", "--full")
        return result, [c for c in self.codes(result) if c[0] == PATH_INVALID]

    def test_test_path_through_an_upper_symlink_to_outside_the_repository_is_invalid(self):
        self.write(tests=["ext/t.py"])
        _write(self.outside, "t.py", TEST_BODY)
        self.link("ext", str(self.outside))
        self.commit()
        result, invalid = self.check_codes()
        self.assertEqual(invalid, [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "tests[0].path")], result)
        self.assertEqual(result["status"], "failed")

    def test_implements_through_an_upper_symlink_to_outside_the_repository_is_invalid(self):
        self.write(implements=["ext/a.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        _write(self.outside, "a.py", "x = 1\n")
        self.link("ext", str(self.outside))
        self.commit()
        _result, invalid = self.check_codes()
        self.assertEqual(invalid, [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "implements")])

    def test_test_path_through_an_upper_symlink_resolving_inside_the_root_passes(self):
        # 対照: 中へ解決する上位のシンボリックリンクは通る。
        self.write(tests=["ext/t.py"], implements=["ext/a.py"])
        _write(self.root, "real/t.py", TEST_BODY)
        _write(self.root, "real/a.py", "x = 1\n")
        self.link("ext", "real")
        self.commit()
        result, invalid = self.check_codes()
        self.assertEqual(invalid, [], result)

    def test_symlink_at_the_end_is_still_invalid(self):
        self.write(tests=["tests/link.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.link("tests/link.py", "t.py")
        self.commit()
        _result, invalid = self.check_codes()
        self.assertEqual(invalid, [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])

    def test_plain_file_passes(self):
        self.write()
        _write(self.root, "tests/t.py", TEST_BODY)
        self.commit()
        result, invalid = self.check_codes()
        self.assertEqual(invalid, [], result)

    def test_sibling_directory_with_the_same_name_prefix_is_not_inside(self):
        # 文字列の前方一致では、ワークスペースのルート`repo`の兄弟`repo-x`の配下が配下に見える。実体の比較では外。
        sibling = self.tmp / (self.root.name + "-x")
        sibling.mkdir()
        _write(sibling, "t.py", TEST_BODY)
        self.write(tests=["ext/t.py"])
        self.link("ext", str(sibling))
        self.commit()
        _result, invalid = self.check_codes()
        self.assertEqual(len(invalid), 1)


class MultiPathOwnershipTests(_MultiBase):
    """複合ワークスペースの`implements`と`tests[].path`の所有（複合ワークスペース仕様 §5.1。N1）。"""

    def ownership(self, result):
        return [c for c in self.codes(result) if c[0] == OWNERSHIP]

    def test_member_cannot_own_another_workspace_test_through_an_upper_symlink(self):
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )

    def test_member_cannot_own_another_workspace_implementation_through_an_upper_symlink(self):
        self.write(web_tests=["tests/test_web.py"], web_implements=["ext/platform.py"])
        self.link("apps/web/ext", "../../src")
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "web", ".spec/requirements/REQ-101.md", "implements")]
        )

    def test_single_operation_from_the_member_also_reports_ownership(self):
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, _code = self.run_op("check", "--full", cwd=self.root / "apps" / "web")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )

    def test_upper_symlink_to_outside_the_repository_is_an_ownership_violation(self):
        self.write(web_tests=["ext/t.py"])
        _write(self.outside, "t.py", TEST_BODY)
        self.link("apps/web/ext", str(self.outside))
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )

    def test_upper_symlink_resolving_inside_the_member_passes(self):
        # 対照: 同じ所有領域の中へ解決する上位のシンボリックリンクは通る。
        self.write(web_tests=["ext/test_web.py"], web_implements=["lib/web.py"])
        self.link("apps/web/ext", "tests")
        self.link("apps/web/lib", "src")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(self.ownership(result), [])

    def test_terminal_symlink_resolving_inside_the_member_still_passes(self):
        self.write(web_tests=["tests/alias.py"])
        self.link("apps/web/tests/alias.py", "test_web.py")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)

    def test_root_workspace_does_not_own_the_member_tree(self):
        self.write(web_tests=["tests/test_web.py"], root_tests=["apps/web/tests/test_web.py"])
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "platform", ".spec/requirements/REQ-001.md", "tests[0].path")]
        )

    def test_root_workspace_does_not_own_the_member_tree_through_an_upper_symlink(self):
        self.write(web_tests=["tests/test_web.py"], root_tests=["lk/test_web.py"])
        self.link("lk", "apps/web/tests")
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "platform", ".spec/requirements/REQ-001.md", "tests[0].path")]
        )

    def test_root_workspace_owns_its_own_tree_through_an_upper_symlink(self):
        # 対照: ルートワークスペースは、自分の領域の中へ解決するパスを所有できる。
        self.write(web_tests=["tests/test_web.py"], root_tests=["lk/test_platform.py"])
        self.link("lk", "tests")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)

    def test_verify_does_not_pass_a_test_owned_through_an_upper_symlink_to_another_workspace(self):
        # N1: 修正前は`check`も`verify`も通った。メンバーのcwd（`.`）の配下にない実パスのため、`verify`は起動を遮断する。
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, _code = self.run_op("verify", "web::REQ-101")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["commands"], [])


class VerifyContainmentSingleTests(_SingleBase):
    """単一ワークスペースの`VERIFY-TEST-OUTSIDE-CWD`の包含の判定（C88）。"""

    def verify(self):
        return self.run_op("verify", "REQ-001")

    def test_a_cwd_symlink_and_test_under_the_real_directory_passes(self):
        # 字句ではテストがcwd（inner）の外にあるが、実パスはcwd（real）の配下。
        self.write(cwd="inner", tests=["real/t.py"], argv=_FIND_ARGV)
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("inner", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        # プロセスの作業ディレクトリは実体の`real`なので、テストは実パスどうしの相対パスで渡す。
        self.assertEqual([c["argv"][-1] for c in result["commands"]], ["t.py"])
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_b_real_cwd_and_test_through_the_symlink_passes(self):
        self.write(cwd="real", tests=["inner/t.py"], argv=_FIND_ARGV)
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("inner", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_cwd_symlink_to_a_deeper_directory_gets_an_argv_the_process_can_open(self):
        # cwdのシンボリックリンクが別の深さの実体を指すとき、字句の相対パス（`../a/b/t.py`）は実体の`..`と一致しない。
        self.write(cwd="lk", tests=["a/b/t.py"], argv=_FIND_ARGV)
        _write(self.root, "a/b/t.py", TEST_BODY)
        self.link("lk", "a/b")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual([c["argv"][-1] for c in result["commands"]], ["t.py"])
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_c_lexically_inside_but_really_outside_is_blocked_with_the_declaring_document_as_source(self):
        # 字句ではテストがcwd（sub）の配下だが、実パスは外（other）。
        self.write(cwd="sub", tests=["sub/link/t.py"], argv=_FIND_ARGV)
        _write(self.root, "other/t.py", TEST_BODY)
        _write(self.root, "sub/keep", "")
        self.link("sub/link", "../other")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(result["commands"], [])
        self.assertEqual(
            self.codes(result),
            [(BLOCKED, "root", ".spec/requirements/REQ-001.md", "tests[0].path")],
        )
        summaries = {d["summary"] for d in self.all_diagnostics(result)}
        self.assertEqual(summaries, {"テストのパスが実効の作業ディレクトリの配下にありません"})

    def test_cwd_outside_the_repository_is_blocked(self):
        self.write(cwd="up", tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.link("up", str(self.outside))
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])
        self.assertEqual(result["commands"], [])

    def test_cwd_sibling_with_the_same_name_prefix_is_outside_the_root(self):
        # 文字列の前方一致では、ルート`repo`の兄弟`repo-x`が所有領域の中に見える。
        sibling = self.tmp / (self.root.name + "-x")
        sibling.mkdir()
        self.write(cwd="up", tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.link("up", str(sibling))
        self.commit()
        result, _code = self.verify()
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])

    def test_test_in_a_sibling_directory_with_the_cwd_name_prefix_is_outside_the_cwd(self):
        self.write(cwd="sub", tests=["sub2/t.py"])
        _write(self.root, "sub/keep", "")
        _write(self.root, "sub2/t.py", TEST_BODY)
        self.commit()
        result, _code = self.verify()
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])

    def test_directory_whose_name_starts_with_two_dots_is_inside_the_cwd(self):
        # 相対パスが`..`で始まる文字列でも、`..data`はセグメントの境界では親ディレクトリではない。
        self.write(cwd="sub", tests=["sub/..data/t.py"], argv=_FIND_ARGV)
        _write(self.root, "sub/..data/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_test_through_an_upper_symlink_resolving_inside_the_cwd_passes(self):
        # 対照: 字句でも実パスでもcwdの配下。
        self.write(cwd="sub", tests=["sub/link/t.py"], argv=_FIND_ARGV)
        _write(self.root, "sub/real/t.py", TEST_BODY)
        self.link("sub/link", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(result["commands"][0]["exitCode"], 0)


class VerifyOutsideCwdSourceTests(_SingleBase):
    """N3: `VERIFY-TEST-OUTSIDE-CWD`の発生元（verify §5.1）。"""

    def setup_two_documents(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _commands("sub"))
        _write(self.root, "sub/ok.py", TEST_BODY)
        _write(self.root, "sub/ok2.py", TEST_BODY)
        _write(self.root, "other.py", TEST_BODY)
        _write(self.root, "other2.py", TEST_BODY)

    def test_source_is_the_lexically_first_declaring_document_and_one_diagnostic_per_binding(self):
        self.setup_two_documents()
        # REQ-001（辞書順で先）は、cwd内のテストとcwd外のテスト2件。REQ-002とTECH-001もcwd外のテストを宣言する。
        _write(
            self.root, ".spec/requirements/REQ-001.md",
            _req("REQ-001", ["sub/ok.py", "other.py", "other2.py"]),
        )
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", ["other.py"]))
        _write(self.root, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001", ["other.py"]))
        self.commit()
        result, _code = self.run_op("verify")
        diags = [d for d in self.all_diagnostics(result) if d["code"] == BLOCKED]
        outside = [d for d in diags if d["summary"] == "テストのパスが実効の作業ディレクトリの配下にありません"]
        self.assertEqual(len(outside), 1, diags)
        self.assertEqual(
            outside[0]["source"],
            {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md", "key": "tests[1].path"},
        )

    def test_source_prefers_the_smaller_path_even_when_another_document_has_a_smaller_index(self):
        self.setup_two_documents()
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["sub/ok.py", "sub/ok2.py", "other.py"]))
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", ["other.py"]))
        self.commit()
        result, _code = self.run_op("verify")
        outside = [d for d in self.all_diagnostics(result) if d["summary"].startswith("テストのパスが実効の作業ディレクトリ")]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["source"]["path"], ".spec/requirements/REQ-001.md")
        self.assertEqual(outside[0]["source"]["key"], "tests[2].path")

    def test_source_does_not_depend_on_the_hash_seed(self):
        self.setup_two_documents()
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["other.py"]))
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", ["other.py"]))
        _write(self.root, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-002", ["other2.py"]))
        self.commit()
        script = (
            "import json, sys\n"
            "from bitz import verify\nfrom bitz.cliargs import parse_argv\n"
            "r, _ = verify.run(parse_argv(['verify', '--format', 'json']), sys.argv[1], {})\n"
            "print(json.dumps([d['source'] for t in r['targetResults'] for d in t.get('diagnostics', [])] + "
            "[d['source'] for d in r['diagnostics']], sort_keys=True))\n"
        )
        outputs = set()
        for seed in ("1", "2", "3"):
            proc = subprocess.run(
                [os.sys.executable, "-c", script, str(self.root)],
                env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs.add(proc.stdout)
        self.assertEqual(len(outputs), 1, outputs)
        self.assertIn(".spec/requirements/REQ-001.md", outputs.pop())


class VerifyContainmentMultiTests(_MultiBase):
    def test_source_names_the_owning_workspace_and_its_relative_document_path(self):
        # webのREQ-101がルート側のテストを上位のシンボリックリンクで宣言する。cwdはweb（`.`）。
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(code, 2, result)
        outside = [d for d in self.all_diagnostics(result) if d["code"] == BLOCKED]
        self.assertEqual(
            [d["source"] for d in outside],
            [{"kind": "file", "workspaceId": "web", "path": ".spec/requirements/REQ-101.md", "key": "tests[0].path"}],
        )
        by_id = {ws["id"]: ws for ws in result["workspaces"]}
        self.assertEqual([d["code"] for d in by_id["web"]["diagnostics"] if d["code"] == BLOCKED], [BLOCKED])
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(by_id["platform"]["status"], "passed")

    def test_cwd_into_another_member_through_a_symlink_is_an_ownership_violation(self):
        self.write(web_tests=["tests/test_web.py"], web_cwd="esc")
        self.link("apps/web/esc", "../../tests")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] == OWNERSHIP],
            [(OWNERSHIP, "web", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_root_cwd_symlink_into_a_member_is_an_ownership_violation(self):
        self.write(web_tests=["tests/test_web.py"], root_cwd="lk")
        self.link("lk", "apps/web")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] == OWNERSHIP],
            [(OWNERSHIP, "platform", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_member_cwd_symlink_inside_the_member_passes(self):
        # 対照。
        self.write(web_tests=["lk/test_web.py"], web_cwd="lk", argv=_FIND_ARGV)
        self.link("apps/web/lk", "tests")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)


class RealPathPrimitivesTests(_Base):
    """`bitz.pathown`の実体の比較（セグメント境界と所有領域）。"""

    def test_within_uses_segment_boundaries(self):
        from bitz import pathown

        (self.tmp / "web").mkdir()
        (self.tmp / "web2").mkdir()
        (self.tmp / "web" / "f").write_text("")
        (self.tmp / "web2" / "f").write_text("")
        base = str(self.tmp / "web")
        self.assertTrue(pathown.within(str(self.tmp / "web"), base))
        self.assertTrue(pathown.within(str(self.tmp / "web" / "f"), base))
        self.assertTrue(pathown.within(str(self.tmp / "web" / "missing" / "x"), base))
        self.assertFalse(pathown.within(str(self.tmp / "web2" / "f"), base))
        self.assertFalse(pathown.within(str(self.tmp / "web2"), base))
        self.assertFalse(pathown.within(str(self.tmp), base))

    def test_owns_excludes_nested_workspace_roots(self):
        from bitz import pathown

        (self.tmp / "r" / "apps" / "web").mkdir(parents=True)
        root = str(self.tmp / "r")
        member = str(self.tmp / "r" / "apps" / "web")
        roots = [root, member]
        self.assertTrue(pathown.owns(root + "/x", root, roots))
        self.assertFalse(pathown.owns(member + "/x", root, roots))
        self.assertTrue(pathown.owns(member + "/x", member, roots))
        self.assertFalse(pathown.owns(root + "/x", member, roots))


def _fake_stat(identity: dict[str, tuple[int, int]]):
    def fake(path, *args, **kwargs):
        key = os.fspath(path)
        if key not in identity:
            raise FileNotFoundError(key)
        dev, ino = identity[key]
        return types.SimpleNamespace(st_dev=dev, st_ino=ino, st_mode=0o040755)

    return fake


class FilesystemIdentityTests(unittest.TestCase):
    """大文字と小文字・Unicodeの正規化の扱いはファイルシステムに任せる（複合ワークスペース仕様 §5.1の手順5）。

    Linuxでは再現できないため、`os.stat`を差し替え、別の綴りが同じ実体（デバイスとiノード）を指すとき、同じと判定することを確かめる。
    """

    @property
    def pathown(self):
        from bitz import pathown

        return pathown

    def patch(self, identity):
        return mock.patch("os.stat", _fake_stat(identity))

    def test_case_variants_of_the_same_entity_are_inside(self):
        identity = {
            "/": (1, 1), "/r": (1, 10), "/r/apps": (1, 50), "/r/Apps": (1, 50),
            "/r/apps/web": (1, 100), "/r/Apps/Web": (1, 100), "/r/apps/web/x.py": (1, 101),
        }
        with self.patch(identity):
            # 綴りが違っても、同じ実体を指すディレクトリが祖先にある。
            self.assertTrue(self.pathown.within("/r/Apps/Web/x.py", "/r/apps/web"))
            self.assertTrue(self.pathown.within("/r/apps/web/x.py", "/r/Apps/Web"))
            self.assertTrue(self.pathown.owns("/r/Apps/Web/x.py", "/r/apps/web", ["/r/apps/web"]))

    def test_different_entities_with_case_variant_names_are_not_inside(self):
        # 陰性対照: 大文字と小文字を区別するファイルシステムでは、綴りが違えば別の実体（iノードが違う）。
        identity = {"/": (1, 1), "/r": (1, 10), "/r/apps": (1, 50), "/r/Apps": (1, 51), "/r/apps/web": (1, 100), "/r/Apps/Web": (1, 101)}
        with self.patch(identity):
            self.assertFalse(self.pathown.within("/r/Apps/Web/x.py", "/r/apps/web"))

    def test_same_inode_on_another_device_is_a_different_entity(self):
        identity = {"/": (1, 1), "/r": (1, 10), "/r/apps/web": (1, 100), "/m/web": (2, 100)}
        with self.patch(identity):
            self.assertFalse(self.pathown.within("/m/web/x.py", "/r/apps/web"))

    def test_normalization_variants_of_the_same_entity_are_inside(self):
        nfc = unicodedata.normalize("NFC", "café")
        nfd = unicodedata.normalize("NFD", "café")
        self.assertNotEqual(nfc, nfd)
        identity = {"/": (1, 1), "/r": (1, 10), f"/r/{nfc}": (1, 70), f"/r/{nfd}": (1, 70)}
        with self.patch(identity):
            self.assertTrue(self.pathown.within(f"/r/{nfd}/x.py", f"/r/{nfc}"))
            self.assertTrue(self.pathown.within(f"/r/{nfc}/x.py", f"/r/{nfd}"))

    def test_cwd_ownership_uses_the_identity_for_the_root_workspace(self):
        # ルートワークスペースのcwdが、綴りの違うメンバーのルートと同じ実体なら、メンバーの配下として所有領域の外。
        identity = {"/": (1, 1), "/r": (1, 10), "/r/apps": (1, 50), "/r/Apps": (1, 50), "/r/apps/web": (1, 100), "/r/Apps/Web": (1, 100)}
        roots = {"platform": "/r", "web": "/r/apps/web"}
        with self.patch(identity):
            diag = verify_mod._cwd_ownership_diag("platform", "t", "Apps/Web", "/r/Apps/Web", roots, "platform")
            same = verify_mod._cwd_ownership_diag("platform", "t", "apps/web", "/r/apps/web", roots, "platform")
        self.assertIsNotNone(diag)
        self.assertEqual(diag["code"], OWNERSHIP)
        self.assertIsNotNone(same)

    def test_resolve_owned_path_uses_the_identity(self):
        # `Apps/Web`と`apps/web`が同じ実体のとき、ルートワークスペースの`Apps/Web/..`の配下はメンバーの所有領域に入る。
        from bitz import multirelate

        identity = {
            "/": (1, 1), "/r": (1, 10), "/r/apps": (1, 50), "/r/Apps": (1, 50), "/r/apps/web": (1, 100),
            "/r/Apps/Web": (1, 100), "/r/Apps/Web/t.py": (1, 101), "/r/apps/web/t.py": (1, 101),
        }
        with self.patch(identity), mock.patch("os.path.lexists", return_value=True), mock.patch("os.path.isfile", return_value=True):
            ok_root, violation_root = multirelate._resolve_owned_path("/r", "/r", "Apps/Web/t.py", ["/r", "/r/apps/web"])
            ok_member, violation_member = multirelate._resolve_owned_path(
                "/r/apps/web", "/r/apps/web", "t.py", ["/r", "/r/apps/web"]
            )
        self.assertEqual((ok_root, violation_root), (False, True))
        self.assertEqual((ok_member, violation_member), (True, False))


class OwnershipResolutionStaysWithinCheckedScopeTests(_MultiBase):
    """TASKの`changes`の所有（複合ワークスペース仕様 §5.2）は、シンボリックリンクのエントリのリンク先の実パスで判定し、通常のファイルの変更はTASKの境界で扱う。"""

    def test_task_change_of_a_symlink_to_another_workspace_is_an_ownership_violation(self):
        from bitz import check as check_mod_local

        self.write(web_tests=["tests/test_web.py"])
        _write(self.root, "apps/web/src/a.py", "x = 1\n")
        self.commit()
        # 基準版の後に、`apps/web/src`を別のワークスペースを指すシンボリックリンクへ置き換える（Gitは`src`をリンクとして扱う）。
        os.rename(self.root / "apps/web/src", self.root / "apps/web/src.bak")
        os.symlink("../../src", self.root / "apps/web/src")
        diag = check_mod_local._task_change_ownership_diag(
            mock.Mock(available=False, executable=None), str(self.root), {}, None, "web",
            str(self.root / "apps" / "web"), {"platform": str(self.root), "web": str(self.root / "apps" / "web")},
            "src", "A",
        )
        self.assertIsNotNone(diag)
        self.assertEqual(diag.code, OWNERSHIP)
        # 対照: 自分の所有領域の中へ解決するパスは違反ではない。
        os.symlink("src.bak", self.root / "apps/web/inner")
        inner = check_mod_local._task_change_ownership_diag(
            mock.Mock(available=False, executable=None), str(self.root), {}, None, "web",
            str(self.root / "apps" / "web"), {"platform": str(self.root), "web": str(self.root / "apps" / "web")},
            "inner", "A",
        )
        self.assertIsNone(inner)

    def test_root_task_change_of_a_regular_file_under_a_member_is_not_an_ownership_violation(self):
        """シンボリックリンクでない変更パスは所有境界違反にせず、TASKの境界で扱う（独立レビューのH1の回帰）。"""
        from bitz import check as check_mod_local

        self.write(web_tests=["tests/test_web.py"])
        _write(self.root, "apps/web/src/a.py", "x = 1\n")
        self.commit()
        _write(self.root, "apps/web/src/b.py", "y = 1\n")
        roots = {"platform": str(self.root), "web": str(self.root / "apps" / "web")}
        for status, path in (("A", "apps/web/src/b.py"), ("M", "apps/web/src/a.py")):
            with self.subTest(status=status):
                diag = check_mod_local._task_change_ownership_diag(
                    mock.Mock(available=False, executable=None), str(self.root), {}, None, "platform",
                    str(self.root), roots, path, status,
                )
                self.assertIsNone(diag)
        # 対照: ルートのシンボリックリンクがメンバーの配下を指せば、ルートはメンバーの配下を所有しないので違反である。
        os.symlink("apps/web/src", self.root / "lk")
        diag = check_mod_local._task_change_ownership_diag(
            mock.Mock(available=False, executable=None), str(self.root), {}, None, "platform",
            str(self.root), roots, "lk", "A",
        )
        self.assertIsNotNone(diag)
        self.assertEqual(diag.code, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
