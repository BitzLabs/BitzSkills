"""パスの存在の検査と所有の判定を、シンボリックリンクを辿らず、NFCの字句のパスで行う単体試験（ADR-071。確認事項 C88・C90・N1・N3の後継）。

規範（期待値はすべて次の文から導いたリテラルで、Coreの出力を写さない）:
- 安全な入出力・互換性 §6.1: 宣言したパスとディレクトリの項目名は、どちらもUnicode NFCにしてから、セグメントごとにコードポイントの完全一致
  （大文字と小文字を区別する）で比べる。包含はセグメントの境界で判定する。
- 同 §6.2: パスの存在は、基準のルートから各セグメントを順に、親のディレクトリの項目名と照合して確かめる。0件は不在、2件以上はNFCの衝突で拒否、
  1件ならリンクを辿らない`lstat`で調べる。途中のセグメントがシンボリックリンクならパスを拒否し、末端がシンボリックリンクなら通常のファイルにも
  ディレクトリにも扱わない（不在）。`implements`と`tests[].path`の不在とリンクと別の綴りは`SPEC-PATH-INVALID-001`（「実装パスが存在しません」
  「テストのパスが存在しません」。状態`draft`は`warning`で「状態draftの…は未作成です」）、NFCの衝突は同じコードの専用の文言
  （重大度は不在と同じく状態で分ける）。`cwd`は不在、リンク、別の綴り、NFCの衝突のどれもが`VERIFY-CWD-UNAVAILABLE`
  （`SPEC-VERIFY-BLOCKED-001`、「コマンドの作業ディレクトリが利用できません」）。
- 同 §6.3・複合ワークスペース仕様 §5.1の手順5: 所有の判定はNFCにした字句のパスのセグメント単位の包含で行い、実パスと、デバイスとiノードは使わない。
  ルートワークスペースはメンバーの配下を所有しない。存在する`cwd`だけを字句の包含で判定し、違反は`MULTI-OWNERSHIP-CWD`（`SPEC-MULTI-OWNERSHIP-001`）。
- ワークスペース・設定仕様 §6: テストのパスと実効`cwd`の包含は、字句のパス（NFC）をセグメントの境界で比べ、`cwd`相対の展開も字句の相対とする。
- verify §5.1: `VERIFY-TEST-OUTSIDE-CWD`の発生元は、配下にないテストのパスを宣言した仕様文書（複数ならパスの辞書順で最初）、
  `key`はその文書の`tests[i].path`、テスト割当てごとに1件。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unicodedata
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import pathown
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"check": check_mod, "verify": verify_mod}

TEST_BODY = "def test_t():\n    assert True\n"
# テストのパスの引数を、プロセスの作業ディレクトリから実際に開けるかを確かめる（argvの相対パスの検証）。
_FIND_ARGV = '["/bin/sh", "-c", "for f in \\"$@\\"; do test -f \\"$f\\" || exit 1; done", "sh", "{tests}"]'
_TRUE_ARGV = '["/bin/true", "{tests}"]'

#: 「é」を1文字（NFC）と、「e」＋結合文字（NFD）で書いた名前。
NFC_NAME = unicodedata.normalize("NFC", "café")
NFD_NAME = unicodedata.normalize("NFD", "café")

PATH_INVALID = "SPEC-PATH-INVALID-001"
OWNERSHIP = "SPEC-MULTI-OWNERSHIP-001"
BLOCKED = "SPEC-VERIFY-BLOCKED-001"
CWD_UNAVAILABLE = "コマンドの作業ディレクトリが利用できません"
TEST_MISSING = "テストのパスが存在しません"
TEST_DRAFT = "状態draftのテストのパスは未作成です"
TEST_COLLISION = "NFCで同じ名前になる項目が複数あり、テストのパスが一つに決まりません"
IMPL_MISSING = "実装パスが存在しません"
IMPL_COLLISION = "NFCで同じ名前になる項目が複数あり、実装パスが一つに決まりません"


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


def _req(
    doc_id: str, test_paths: list[str], *, implements: list[str] | None = None, status: str = "approved"
) -> str:
    """REQ。``test_paths``の各パスを`tests[]`として宣言する（すべて同じ規範文をcoversする）。"""

    tests = "".join(
        f"  - path: {p}\n    covers: [{doc_id}:AC-01]\n    command: t\n" for p in test_paths
    )
    impl = "" if implements is None else "implements:\n" + "".join(f"  - {p}\n" for p in implements)
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\n{impl}tests:\n{tests}---\n\n"
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


def _require_nfc_nfd_distinct(directory: Path) -> None:
    """ファイルシステムがNFCとNFDの名前を区別して保つ（Linuxなど）ことを確かめ、そうでなければ試験を飛ばす。"""

    probe = directory / f"probe-{NFC_NAME}"
    probe.write_text("")
    try:
        if (directory / f"probe-{NFD_NAME}").exists():
            raise unittest.SkipTest("ファイルシステムがUnicodeの正規化の違いを同一視する")
    finally:
        probe.unlink()


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # 基準のルートへ至る上位のディレクトリは検査の対象外（安全な入出力・互換性 §6）。macOSなどで一時ディレクトリ自体が
        # シンボリックリンクでも、基準のルートを一定にするため、先に解決した場所をリポジトリの親にする。
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
    def write(
        self, cwd: str = ".", argv: str = _TRUE_ARGV, tests: list[str] | None = None, implements=None,
        status: str = "approved",
    ):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _commands(cwd, argv))
        _write(
            self.root, ".spec/requirements/REQ-001.md",
            _req("REQ-001", tests or ["tests/t.py"], implements=implements, status=status),
        )


class _MultiBase(_Base):
    """ルートワークスペースplatform（`tests/`を持つ）とメンバーweb（`apps/web`）。"""

    def write(
        self, *, web_tests: list[str], web_cwd: str = ".", root_tests: list[str] | None = None,
        root_cwd: str = ".", web_implements=None, root_implements=None, argv: str = _TRUE_ARGV,
        web_path: str = "apps/web",
    ):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + f"workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: {web_path}\n"
            + _commands(root_cwd, argv),
        )
        _write(self.root, f"{web_path}/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + _commands(web_cwd, argv))
        _write(
            self.root, ".spec/requirements/REQ-001.md",
            _req("REQ-001", root_tests or ["tests/test_platform.py"], implements=root_implements),
        )
        _write(
            self.root, f"{web_path}/.spec/requirements/REQ-101.md",
            _req("REQ-101", web_tests, implements=web_implements),
        )
        _write(self.root, "tests/test_platform.py", TEST_BODY)
        _write(self.root, "src/platform.py", "x = 1\n")
        _write(self.root, f"{web_path}/tests/test_web.py", TEST_BODY)
        _write(self.root, f"{web_path}/src/web.py", "x = 1\n")


class SinglePathExistenceTests(_SingleBase):
    """単一ワークスペースの`implements`と`tests[].path`の存在の検査（安全な入出力・互換性 §6.2）。"""

    def path_diagnostics(self, *argv: str):
        result, _code = self.run_op("check", *(argv or ("--full",)))
        diags = [d for d in self.all_diagnostics(result) if d["code"] == PATH_INVALID]
        return result, [(d["severity"], d["summary"], d["source"].get("key")) for d in diags]

    def test_plain_file_passes(self):
        self.write(implements=["src/a.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        _write(self.root, "src/a.py", "x = 1\n")
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [], result)

    def test_test_path_through_an_upper_symlink_to_outside_the_repository_is_invalid(self):
        self.write(tests=["ext/t.py"])
        _write(self.outside, "t.py", TEST_BODY)
        self.link("ext", str(self.outside))
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("error", TEST_MISSING, "tests[0].path")], result)
        self.assertEqual(result["status"], "failed")

    def test_implements_through_an_upper_symlink_to_outside_the_repository_is_invalid(self):
        self.write(implements=["ext/a.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        _write(self.outside, "a.py", "x = 1\n")
        self.link("ext", str(self.outside))
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("error", IMPL_MISSING, "implements")])

    def test_upper_symlink_resolving_inside_the_root_is_still_invalid(self):
        # 実パスが同じワークスペースの中でも、途中のセグメントがシンボリックリンクならパスを拒否する（不在と同じ）。
        self.write(tests=["ext/t.py"], implements=["ext/a.py"])
        _write(self.root, "real/t.py", TEST_BODY)
        _write(self.root, "real/a.py", "x = 1\n")
        self.link("ext", "real")
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(
            sorted(invalid), sorted([("error", IMPL_MISSING, "implements"), ("error", TEST_MISSING, "tests[0].path")])
        )

    def test_symlink_at_the_end_is_invalid_even_when_it_resolves_inside_the_root(self):
        self.write(tests=["tests/link.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.link("tests/link.py", "t.py")
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("error", TEST_MISSING, "tests[0].path")])

    def test_a_directory_is_not_a_regular_file(self):
        self.write(tests=["tests/d"])
        _write(self.root, "tests/d/x.py", TEST_BODY)
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("error", TEST_MISSING, "tests[0].path")])

    def test_different_case_spelling_does_not_exist(self):
        # 大文字と小文字を区別するファイルシステムでも、区別しないファイルシステムでも、別の綴りのパスは存在しない。
        self.write(tests=["Tests/T.py"], implements=["SRC/a.py"])
        _write(self.root, "tests/T.py", TEST_BODY)
        _write(self.root, "src/a.py", "x = 1\n")
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(
            sorted(invalid), sorted([("error", IMPL_MISSING, "implements"), ("error", TEST_MISSING, "tests[0].path")])
        )

    def test_draft_document_reports_an_unlinked_path_as_a_warning(self):
        self.write(tests=["ext/t.py"], status="draft")
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("ext", "real")
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("warning", TEST_DRAFT, "tests[0].path")])
        self.assertEqual(result["status"], "passed_with_warnings")

    def test_nfd_name_on_disk_matches_an_nfc_declaration(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=[f"tests/{NFC_NAME}.py"], implements=[f"src/{NFC_NAME}/a.py"])
        _write(self.root, f"tests/{NFD_NAME}.py", TEST_BODY)
        _write(self.root, f"src/{NFD_NAME}/a.py", "x = 1\n")
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [], result)

    def test_nfc_name_on_disk_matches_an_nfd_declaration(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=[f"tests/{NFD_NAME}.py"])
        _write(self.root, f"tests/{NFC_NAME}.py", TEST_BODY)
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [], result)

    def test_nfc_collision_in_the_last_segment_is_rejected_with_the_dedicated_message(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=[f"tests/{NFC_NAME}.py"], implements=[f"src/{NFD_NAME}.py"])
        _write(self.root, f"tests/{NFC_NAME}.py", TEST_BODY)
        _write(self.root, f"tests/{NFD_NAME}.py", TEST_BODY)
        _write(self.root, f"src/{NFC_NAME}.py", "x = 1\n")
        _write(self.root, f"src/{NFD_NAME}.py", "x = 1\n")
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(
            sorted(invalid),
            sorted([("error", IMPL_COLLISION, "implements"), ("error", TEST_COLLISION, "tests[0].path")]),
            result,
        )

    def test_nfc_collision_in_a_directory_segment_is_rejected(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=[f"{NFC_NAME}/t.py"])
        _write(self.root, f"{NFC_NAME}/t.py", TEST_BODY)
        _write(self.root, f"{NFD_NAME}/t.py", TEST_BODY)
        self.commit()
        _result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("error", TEST_COLLISION, "tests[0].path")])

    def test_nfc_collision_uses_the_same_message_for_a_draft_and_a_warning_severity(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=[f"tests/{NFC_NAME}.py"], status="draft")
        _write(self.root, f"tests/{NFC_NAME}.py", TEST_BODY)
        _write(self.root, f"tests/{NFD_NAME}.py", TEST_BODY)
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [("warning", TEST_COLLISION, "tests[0].path")])
        self.assertEqual(result["status"], "passed_with_warnings")

    def test_a_collision_elsewhere_in_the_directory_does_not_affect_other_names(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        _write(self.root, f"tests/{NFC_NAME}.py", TEST_BODY)
        _write(self.root, f"tests/{NFD_NAME}.py", TEST_BODY)
        self.commit()
        result, invalid = self.path_diagnostics()
        self.assertEqual(invalid, [], result)


class MultiPathOwnershipTests(_MultiBase):
    """複合ワークスペースの`implements`と`tests[].path`の存在と所有（複合ワークスペース仕様 §5.1）。"""

    def ownership(self, result):
        return [c for c in self.codes(result) if c[0] == OWNERSHIP]

    def path_invalid(self, result):
        return [c for c in self.codes(result) if c[0] == PATH_INVALID]

    def test_member_test_path_through_an_upper_symlink_is_invalid_not_owned(self):
        # 上位のディレクトリのシンボリックリンクは辿らない。別のワークスペースの領域へ向いていても、所有境界の違反ではなく不在と同じ。
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.ownership(result), [])
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )

    def test_member_implements_through_an_upper_symlink_is_invalid_not_owned(self):
        self.write(web_tests=["tests/test_web.py"], web_implements=["ext/platform.py"])
        self.link("apps/web/ext", "../../src")
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(self.ownership(result), [])
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "implements")]
        )

    def test_single_operation_from_the_member_reports_the_same(self):
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, _code = self.run_op("check", "--full", cwd=self.root / "apps" / "web")
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )
        self.assertEqual(self.ownership(result), [])

    def test_upper_symlink_to_outside_the_repository_is_invalid(self):
        self.write(web_tests=["ext/t.py"])
        _write(self.outside, "t.py", TEST_BODY)
        self.link("apps/web/ext", str(self.outside))
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )
        self.assertEqual(self.ownership(result), [])

    def test_upper_symlink_resolving_inside_the_member_is_still_invalid(self):
        self.write(web_tests=["ext/test_web.py"], web_implements=["lib/web.py"])
        self.link("apps/web/ext", "tests")
        self.link("apps/web/lib", "src")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(
            sorted(self.path_invalid(result)),
            sorted([
                (PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path"),
                (PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "implements"),
            ]),
        )

    def test_terminal_symlink_resolving_inside_the_member_is_invalid(self):
        # 末端のシンボリックリンクは、同じ所有領域の中のファイルを指しても、通常のファイルとして扱わない（複合ワークスペース仕様 §5.1の手順4）。
        self.write(web_tests=["tests/alias.py"])
        self.link("apps/web/tests/alias.py", "test_web.py")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path")]
        )
        self.assertEqual(self.ownership(result), [])

    def test_plain_files_in_each_own_area_pass(self):
        self.write(web_tests=["tests/test_web.py"], web_implements=["src/web.py"], root_implements=["src/platform.py"])
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

    def test_root_declaration_inside_the_member_tree_is_an_ownership_violation_even_when_the_file_is_absent(self):
        # 字句のパスが別のワークスペースの所有領域にあれば、存在の有無によらず所有境界の違反（複合ワークスペース仕様 §5.1の手順5）。
        self.write(web_tests=["tests/test_web.py"], root_implements=["apps/web/src/not_yet.py"])
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "platform", ".spec/requirements/REQ-001.md", "implements")]
        )
        self.assertEqual(self.path_invalid(result), [])

    def test_root_workspace_reaching_the_member_tree_through_a_symlink_is_invalid(self):
        # 字句のパス`lk/test_web.py`はルートの領域にあり、`lk`はシンボリックリンクなので存在しない。リンク先のメンバーの領域は使わない。
        self.write(web_tests=["tests/test_web.py"], root_tests=["lk/test_web.py"])
        self.link("lk", "apps/web/tests")
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(self.ownership(result), [])
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "platform", ".spec/requirements/REQ-001.md", "tests[0].path")]
        )

    def test_root_workspace_symlink_inside_its_own_tree_is_invalid(self):
        self.write(web_tests=["tests/test_web.py"], root_tests=["lk/test_platform.py"])
        self.link("lk", "tests")
        self.commit()
        result, code = self.run_op("check", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "platform", ".spec/requirements/REQ-001.md", "tests[0].path")]
        )

    def test_a_different_case_spelling_of_the_member_path_is_not_the_member_tree(self):
        # 大文字と小文字を区別する。`Apps/web`は`apps/web`の配下ではないので、所有境界の違反ではなく、存在しないパスである。
        self.write(web_tests=["tests/test_web.py"], root_implements=["Apps/web/src/web.py"])
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(self.ownership(result), [])
        self.assertEqual(
            self.path_invalid(result), [(PATH_INVALID, "platform", ".spec/requirements/REQ-001.md", "implements")]
        )

    def test_an_nfd_spelling_of_a_nfc_member_path_is_the_member_tree(self):
        # 宣言のNFDの綴りは、NFCへ正規化してから包含を判定するので、NFCで宣言したメンバーの領域に入る。
        _require_nfc_nfd_distinct(self.root)
        self.write(
            web_tests=["tests/test_web.py"], web_path=f"apps/{NFC_NAME}",
            root_implements=[f"apps/{NFD_NAME}/src/web.py"],
        )
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        self.assertEqual(
            self.ownership(result), [(OWNERSHIP, "platform", ".spec/requirements/REQ-001.md", "implements")]
        )

    def test_nfc_collision_is_rejected_with_the_dedicated_message_in_a_member(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(web_tests=[f"tests/{NFC_NAME}.py"])
        _write(self.root, f"apps/web/tests/{NFC_NAME}.py", TEST_BODY)
        _write(self.root, f"apps/web/tests/{NFD_NAME}.py", TEST_BODY)
        self.commit()
        result, _code = self.run_op("check", "--all-workspaces")
        diags = [d for d in self.all_diagnostics(result) if d["code"] == PATH_INVALID]
        self.assertEqual([(d["severity"], d["summary"], d["source"]["key"]) for d in diags], [("error", TEST_COLLISION, "tests[0].path")])

    def test_verify_does_not_pass_a_test_owned_through_an_upper_symlink_to_another_workspace(self):
        # 検証対象が使うテスト対応のテストのパスを`check`と同じ規則で検査し（`bitz verify`仕様 §4の4.）、シンボリックリンクを辿るパスは
        # `SPEC-PATH-INVALID-001`（`failed`）で、テストを起動しない。
        self.write(web_tests=["ext/test_platform.py"])
        self.link("apps/web/ext", "../../tests")
        self.commit()
        result, _code = self.run_op("verify", "web::REQ-101")
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["commands"], [])
        self.assertEqual(
            [c for c in self.codes(result) if c[0] == PATH_INVALID],
            [(PATH_INVALID, "web", ".spec/requirements/REQ-101.md", "tests[0].path")],
        )


class VerifyContainmentSingleTests(_SingleBase):
    """単一ワークスペースの`cwd`の存在と、`VERIFY-TEST-OUTSIDE-CWD`の字句の包含の判定（C88）。"""

    def verify(self):
        return self.run_op("verify", "REQ-001")

    def test_a_symlink_cwd_is_unavailable_even_when_it_resolves_inside_the_root(self):
        self.write(cwd="inner", tests=["real/t.py"], argv=_FIND_ARGV)
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("inner", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})
        self.assertEqual(result["commands"], [])

    def test_a_test_path_through_a_symlink_is_an_invalid_test_path(self):
        # テストのパスの途中がシンボリックリンクなら、`cwd`が実在のディレクトリでも、テストのパスが存在しない（`failed`）。
        self.write(cwd="real", tests=["inner/t.py"], argv=_FIND_ARGV)
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("inner", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.codes(result), [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])
        self.assertEqual(result["commands"], [])

    def test_a_symlink_cwd_to_a_deeper_directory_is_unavailable(self):
        self.write(cwd="lk", tests=["a/b/t.py"], argv=_FIND_ARGV)
        _write(self.root, "a/b/t.py", TEST_BODY)
        self.link("lk", "a/b")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])

    def test_a_test_through_a_symlink_that_really_leaves_the_cwd_is_an_invalid_test_path(self):
        self.write(cwd="sub", tests=["sub/link/t.py"], argv=_FIND_ARGV)
        _write(self.root, "other/t.py", TEST_BODY)
        _write(self.root, "sub/keep", "")
        self.link("sub/link", "../other")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.codes(result), [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])
        self.assertEqual(result["commands"], [])

    def test_cwd_outside_the_repository_through_a_symlink_is_unavailable(self):
        self.write(cwd="up", tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.link("up", str(self.outside))
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})
        self.assertEqual(result["commands"], [])

    def test_absent_cwd_is_unavailable(self):
        self.write(cwd="nowhere", tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})

    def test_a_file_is_not_a_cwd(self):
        self.write(cwd="tests/t.py", tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})

    def test_a_different_case_spelling_of_the_cwd_is_unavailable(self):
        self.write(cwd="Sub", tests=["sub/t.py"])
        _write(self.root, "sub/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})

    def test_nfc_collision_of_the_cwd_is_unavailable(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(cwd=NFC_NAME, tests=["tests/t.py"])
        _write(self.root, "tests/t.py", TEST_BODY)
        _write(self.root, f"{NFC_NAME}/keep", "")
        _write(self.root, f"{NFD_NAME}/keep", "")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/bitz.yaml", "verify.commands.t.cwd")])
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})
        self.assertEqual(result["commands"], [])

    def test_nfd_cwd_on_disk_with_an_nfc_declaration_runs_with_a_relative_argv_the_process_can_open(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(cwd=NFC_NAME, tests=[f"{NFC_NAME}/x/t.py"], argv=_FIND_ARGV)
        _write(self.root, f"{NFD_NAME}/x/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        # テストのパスは、宣言したとおりの綴りの`cwd`相対（`cwd`の綴りの差は相対化に影響しない）。
        self.assertEqual([c["argv"][-1] for c in result["commands"]], ["x/t.py"])
        self.assertEqual(result["commands"][0]["exitCode"], 0)

    def test_test_in_a_sibling_directory_with_the_cwd_name_prefix_is_outside_the_cwd(self):
        self.write(cwd="sub", tests=["sub2/t.py"])
        _write(self.root, "sub/keep", "")
        _write(self.root, "sub2/t.py", TEST_BODY)
        self.commit()
        result, _code = self.verify()
        self.assertEqual(self.codes(result), [(BLOCKED, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])

    def test_test_spelled_in_nfd_is_inside_an_nfc_cwd(self):
        # 包含はNFCにした字句のパスで判定する。`cwd`をNFC、テストのパスをNFDで書いても、`cwd`の配下にある。
        _require_nfc_nfd_distinct(self.root)
        self.write(cwd=NFC_NAME, tests=[f"{NFD_NAME}/t.py"], argv=_TRUE_ARGV)
        _write(self.root, f"{NFC_NAME}/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)

    def test_directory_whose_name_starts_with_two_dots_is_inside_the_cwd(self):
        # 相対パスが`..`で始まる文字列でも、`..data`はセグメントの境界では親ディレクトリではない。
        self.write(cwd="sub", tests=["sub/..data/t.py"], argv=_FIND_ARGV)
        _write(self.root, "sub/..data/t.py", TEST_BODY)
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(result["commands"][0]["exitCode"], 0)
        self.assertEqual([c["argv"][-1] for c in result["commands"]], ["..data/t.py"])

    def test_test_through_an_upper_symlink_resolving_inside_the_cwd_is_an_invalid_test_path(self):
        self.write(cwd="sub", tests=["sub/link/t.py"], argv=_FIND_ARGV)
        _write(self.root, "sub/real/t.py", TEST_BODY)
        self.link("sub/link", "real")
        self.commit()
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.codes(result), [(PATH_INVALID, "root", ".spec/requirements/REQ-001.md", "tests[0].path")])


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
        # webのREQ-101が、webの領域の中にあるが実効`cwd`（`src`）の配下にないテストを宣言する。所有領域の外のテストのパスは、
        # テスト対応の検査（`SPEC-MULTI-OWNERSHIP-001`、`failed`）が先に止めるので、この診断はwebの領域の中のテストだけに出る。
        self.write(web_tests=["tests/test_web.py"], web_cwd="src")
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

    def test_a_member_symlink_cwd_is_unavailable_in_the_owning_workspace(self):
        self.write(web_tests=["tests/test_web.py"], web_cwd="esc")
        self.link("apps/web/esc", "../../tests")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] in (BLOCKED, OWNERSHIP)],
            [(BLOCKED, "web", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )
        self.assertEqual({d["summary"] for d in self.all_diagnostics(result)}, {CWD_UNAVAILABLE})

    def test_a_root_symlink_cwd_toward_a_member_is_unavailable_not_owned(self):
        # 存在しない（リンク）`cwd`は所有を判定しない。`VERIFY-CWD-UNAVAILABLE`だけを返す。
        self.write(web_tests=["tests/test_web.py"], root_cwd="lk")
        self.link("lk", "apps/web")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] in (BLOCKED, OWNERSHIP)],
            [(BLOCKED, "platform", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_a_member_cwd_symlink_inside_the_member_is_unavailable(self):
        self.write(web_tests=["tests/test_web.py"], web_cwd="lk", argv=_FIND_ARGV)
        self.link("apps/web/lk", "tests")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(code, 2, result)
        self.assertEqual(
            [c for c in self.codes(result) if c[0] in (BLOCKED, OWNERSHIP)],
            [(BLOCKED, "web", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_an_existing_root_cwd_inside_the_member_is_owned_by_the_member(self):
        self.write(web_tests=["tests/test_web.py"], root_cwd="apps/web")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] in (BLOCKED, OWNERSHIP)],
            [(OWNERSHIP, "platform", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_an_nfd_spelling_of_the_member_path_as_the_root_cwd_is_owned_by_the_member(self):
        _require_nfc_nfd_distinct(self.root)
        self.write(web_tests=["tests/test_web.py"], web_path=f"apps/{NFC_NAME}", root_cwd=f"apps/{NFD_NAME}")
        self.commit()
        result, _code = self.run_op("verify", "--all-workspaces")
        self.assertEqual(
            [c for c in self.codes(result) if c[0] in (BLOCKED, OWNERSHIP)],
            [(OWNERSHIP, "platform", ".spec/bitz.yaml", "verify.commands.t.cwd")],
        )

    def test_a_member_cwd_inside_its_own_area_passes(self):
        self.write(web_tests=["tests/test_web.py"], web_cwd="tests", argv=_FIND_ARGV)
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)


class LexicalPrimitivesTests(unittest.TestCase):
    """`bitz.pathown`の字句の判定（NFC、セグメントの境界、大文字と小文字の区別。ファイルシステムは読まない）。"""

    def test_within_uses_segment_boundaries(self):
        base = "/nowhere/web"
        self.assertTrue(pathown.within("/nowhere/web", base))
        self.assertTrue(pathown.within("/nowhere/web/f", base))
        self.assertTrue(pathown.within("/nowhere/web/missing/x", base))
        self.assertFalse(pathown.within("/nowhere/web2/f", base))
        self.assertFalse(pathown.within("/nowhere/web2", base))
        self.assertFalse(pathown.within("/nowhere", base))

    def test_within_distinguishes_case(self):
        self.assertFalse(pathown.within("/r/Apps/Web/x.py", "/r/apps/web"))
        self.assertFalse(pathown.within("/r/apps/web/x.py", "/r/Apps/Web"))

    def test_within_compares_nfc_normalized_segments(self):
        self.assertNotEqual(NFC_NAME, NFD_NAME)
        self.assertTrue(pathown.within(f"/r/{NFD_NAME}/x.py", f"/r/{NFC_NAME}"))
        self.assertTrue(pathown.within(f"/r/{NFC_NAME}/x.py", f"/r/{NFD_NAME}"))
        self.assertFalse(pathown.within(f"/r/{NFC_NAME}x/x.py", f"/r/{NFD_NAME}"))

    def test_owns_excludes_nested_workspace_roots(self):
        roots = ["/r", "/r/apps/web"]
        self.assertTrue(pathown.owns("/r/x", "/r", roots))
        self.assertFalse(pathown.owns("/r/apps/web/x", "/r", roots))
        self.assertFalse(pathown.owns("/r/apps/web", "/r", roots))
        self.assertTrue(pathown.owns("/r/apps/web/x", "/r/apps/web", roots))
        self.assertFalse(pathown.owns("/r/x", "/r/apps/web", roots))
        self.assertTrue(pathown.owns("/r/apps/webx", "/r", roots))

    def test_owns_uses_nfc_and_case_sensitive_segments(self):
        roots = ["/r", f"/r/apps/{NFC_NAME}"]
        self.assertFalse(pathown.owns(f"/r/apps/{NFD_NAME}/x", "/r", roots))
        self.assertTrue(pathown.owns(f"/r/apps/{NFC_NAME.upper()}/x", "/r", roots))

    def test_relative_to_returns_the_declared_spelling_after_the_base(self):
        self.assertEqual(pathown.relative_to(f"/r/{NFD_NAME}/x/t.py", f"/r/{NFC_NAME}"), "x/t.py")
        self.assertEqual(pathown.relative_to("/r/sub", "/r/sub"), ".")
        self.assertIsNone(pathown.relative_to("/r/sub2/t.py", "/r/sub"))

    def test_nfc_path_index_drops_paths_that_match_two_documents(self):
        index = pathown.build_nfc_path_index(
            [(f".spec/requirements/{NFC_NAME}.md", "A"), (f".spec/requirements/{NFD_NAME}.md", "B"), ("x.md", "C")]
        )
        self.assertEqual(index, {"x.md": "C"})


class PathResolverTests(_Base):
    """:class:`bitz.pathown.PathResolver`の手順（安全な入出力・互換性 §6.2）。"""

    def resolver(self) -> "pathown.PathResolver":
        return pathown.PathResolver(str(self.root))

    def test_exists_returns_the_spelling_on_disk(self):
        _require_nfc_nfd_distinct(self.root)
        _write(self.root, f"{NFD_NAME}/t.py", TEST_BODY)
        found = self.resolver().resolve(f"{NFC_NAME}/t.py", pathown.FILE)
        self.assertEqual((found.status, found.actual), (pathown.EXISTS, (NFD_NAME, "t.py")))

    def test_absent_cases(self):
        _write(self.root, "d/t.py", TEST_BODY)
        resolver = self.resolver()
        self.assertEqual(resolver.resolve("d/none.py", pathown.FILE).status, pathown.ABSENT)
        self.assertEqual(resolver.resolve("none/t.py", pathown.FILE).status, pathown.ABSENT)
        # 途中のセグメントがディレクトリでない。
        self.assertEqual(resolver.resolve("d/t.py/x", pathown.FILE).status, pathown.ABSENT)
        # 種別の不一致。
        self.assertEqual(resolver.resolve("d", pathown.FILE).status, pathown.ABSENT)
        self.assertEqual(resolver.resolve("d/t.py", pathown.DIRECTORY).status, pathown.ABSENT)
        # 別の綴り。
        self.assertEqual(resolver.resolve("D/t.py", pathown.FILE).status, pathown.ABSENT)

    def test_links_are_rejected_in_the_middle_and_at_the_end(self):
        _write(self.root, "real/t.py", TEST_BODY)
        self.link("mid", "real")
        self.link("real/end.py", "t.py")
        self.link("dirlink", "real")
        resolver = self.resolver()
        self.assertEqual(resolver.resolve("mid/t.py", pathown.FILE).status, pathown.LINK)
        self.assertEqual(resolver.resolve("real/end.py", pathown.FILE).status, pathown.LINK)
        self.assertEqual(resolver.resolve("dirlink", pathown.DIRECTORY).status, pathown.LINK)
        # 途中のリンクは、その先の名前が存在しなくても拒否される。
        self.assertEqual(resolver.resolve("mid/none.py", pathown.FILE).status, pathown.LINK)

    def test_dangling_symlink_is_a_link(self):
        self.link("dangling", "no/such/target")
        self.assertEqual(self.resolver().resolve("dangling", pathown.FILE).status, pathown.LINK)

    def test_collision_is_not_absent(self):
        _require_nfc_nfd_distinct(self.root)
        _write(self.root, f"{NFC_NAME}.py", TEST_BODY)
        _write(self.root, f"{NFD_NAME}.py", TEST_BODY)
        self.assertEqual(self.resolver().resolve(f"{NFC_NAME}.py", pathown.FILE).status, pathown.COLLISION)
        self.assertEqual(self.resolver().resolve(f"{NFD_NAME}.py", pathown.FILE).status, pathown.COLLISION)

    def test_root_itself_is_a_directory(self):
        self.assertEqual(self.resolver().resolve(".", pathown.DIRECTORY).status, pathown.EXISTS)
        self.assertEqual(self.resolver().resolve(".", pathown.FILE).status, pathown.ABSENT)

    def test_directory_listings_are_cached_within_one_resolver(self):
        _write(self.root, "d/a.py", TEST_BODY)
        resolver = self.resolver()
        self.assertEqual(resolver.resolve("d/a.py", pathown.FILE).status, pathown.EXISTS)
        _write(self.root, "d/b.py", TEST_BODY)
        # 1回の実行の中では列挙のキャッシュを使う。新しいインスタンスは新しい列挙を読む。
        self.assertEqual(resolver.resolve("d/b.py", pathown.FILE).status, pathown.ABSENT)
        self.assertEqual(self.resolver().resolve("d/b.py", pathown.FILE).status, pathown.EXISTS)


if __name__ == "__main__":
    unittest.main()
