"""TASKの`changes`、メンバーのパス、Gitのパスと宣言の照合を、シンボリックリンクを辿らず、NFCの字句のパスで行う単体試験（ADR-071）。

規範（期待値は次の文から導いたリテラルで、Coreの出力を写さない）:
- 安全な入出力・互換性 §6.4: `changes`の許可はNFCにした字句のパスで判定する（ファイルは完全一致、末尾が`/`のディレクトリはセグメント単位の子孫一致）。
  シンボリックリンクの解決先へ許可を広げず、`changes`に書いたパスについてファイルシステムを読まない。差分に現れたシンボリックリンクのエントリは、
  そのエントリ自身の字句のパスだけで許可を判定し、リンク先は使わない。複合ワークスペースでも、`changes`に所有境界の診断は出さず、TASK境界だけで判定する。
- 複合ワークスペース仕様 §2・§5.1・§5.2: メンバーのパスは、シンボリックリンクを辿らずに存在するディレクトリとする。途中または末端のシンボリックリンクと、
  NFCで同じ名前になる項目が複数あるパスは`SPEC-MULTI-PATH-001`。メンバーのパスどうしの同一と親子関係は、NFCにしたセグメントの完全一致
  （大文字と小文字を区別する）で判定する。別の綴りのパスは存在しない（メンバーの設定がない）。
- check §2・§6: Gitから得た変更のパスと`implements`・`tests[].path`の逆索引の照合、CLIで明示した仕様文書のパスの照合は、NFCにしたセグメントの
  完全一致で行う。NFCで2つ以上の仕様文書のパスに一致するパスは、一致しないパスと同じ（`CTX-ROOT-MISSING-001`）。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unicodedata
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import gitutil
from bitz import multiws
from bitz import pathown
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

NFC_NAME = unicodedata.normalize("NFC", "café")
NFD_NAME = unicodedata.normalize("NFD", "café")

TASK_BOUNDARY = "SPEC-TASK-BOUNDARY-001"
OWNERSHIP = "SPEC-MULTI-OWNERSHIP-001"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _commit(root: Path) -> None:
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "add", ".")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _require_nfc_nfd_distinct(directory: Path) -> None:
    probe = directory / f"probe-{NFC_NAME}"
    probe.write_text("")
    try:
        if (directory / f"probe-{NFD_NAME}").exists():
            raise unittest.SkipTest("ファイルシステムがUnicodeの正規化の違いを同一視する")
    finally:
        probe.unlink()


def _task(doc_id: str, changes: list[str]) -> str:
    listed = "".join(f"  - {c}\n" for c in changes)
    return f"---\nid: {doc_id}\ntitle: 変更\nstatus: open\nchanges:\n{listed}---\n\n# {doc_id} 変更\n"


def _run(op: str, root: Path, *argv: str):
    parsed = parse_argv([op, *argv, "--format", "json"])
    module = {"check": check_mod, "verify": verify_mod}[op]
    return module.run(parsed, str(root), dict(os.environ))


def _codes(result) -> list[tuple[str, str]]:
    """``(コード, summary)``の並び（最上位の診断）。"""

    return sorted((d["code"], d["summary"]) for d in result["diagnostics"])


class _TmpBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.root = self.tmp / "repo"
        self.root.mkdir()


class TaskChangesLexicalTests(_TmpBase):
    """単一ワークスペースの、TASKを明示した`check`（`SPEC-TASK-BOUNDARY-001`）。"""

    def start(self, changes: list[str], base_files: dict[str, str] | None = None):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/tasks/TASK-001.md", _task("TASK-001", changes))
        _write(self.root, "README.md", "x\n")
        for rel, content in (base_files or {}).items():
            _write(self.root, rel, content)
        _commit(self.root)

    def check_task(self):
        return _run("check", self.root, "TASK-001", "--base", "HEAD")

    def test_a_change_inside_a_directory_prefix_is_allowed(self):
        self.start(["src/"])
        _write(self.root, "src/a.py", "x = 1\n")
        result, code = self.check_task()
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_a_change_outside_the_allowed_paths_is_a_task_boundary_violation(self):
        self.start(["src/"])
        _write(self.root, "lib/a.py", "x = 1\n")
        result, code = self.check_task()
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスlib/a.pyはTASK-001の変更許可パスの外です")])

    def test_a_directory_prefix_matches_by_segments_not_by_string_prefix(self):
        self.start(["src/"])
        _write(self.root, "src2/a.py", "x = 1\n")
        result, _code = self.check_task()
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスsrc2/a.pyはTASK-001の変更許可パスの外です")])

    def test_a_file_declaration_matches_exactly(self):
        self.start(["src/a.py"])
        _write(self.root, "src/a.py", "x = 1\n")
        _write(self.root, "src/a.pyc", "x = 1\n")
        result, _code = self.check_task()
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスsrc/a.pycはTASK-001の変更許可パスの外です")])

    def test_a_different_case_spelling_is_not_allowed(self):
        self.start(["src/A.py"])
        _write(self.root, "src/a.py", "x = 1\n")
        result, _code = self.check_task()
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスsrc/a.pyはTASK-001の変更許可パスの外です")])

    def test_an_nfd_git_path_matches_an_nfc_file_declaration(self):
        _require_nfc_nfd_distinct(self.tmp)
        self.start([f"src/{NFC_NAME}.py"])
        _write(self.root, f"src/{NFD_NAME}.py", "x = 1\n")
        result, code = self.check_task()
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_an_nfc_git_path_matches_an_nfd_directory_declaration(self):
        _require_nfc_nfd_distinct(self.tmp)
        self.start([f"lib/{NFD_NAME}/"])
        _write(self.root, f"lib/{NFC_NAME}/a.py", "x = 1\n")
        result, code = self.check_task()
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_a_symlink_entry_is_judged_by_its_own_path_and_allowed_when_that_path_is_allowed(self):
        # リンク先（リポジトリの外）は判定に使わない。`src/link`は許可された`src/`の配下にあるエントリ。
        self.start(["src/"])
        (self.root / "src").mkdir()
        os.symlink("/etc/hostname", self.root / "src" / "link")
        result, code = self.check_task()
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_a_symlink_entry_outside_the_allowed_paths_is_reported_at_its_own_path(self):
        # リンク先`src/a.py`は許可された範囲にあるが、許可はリンク先へ広がらない。エントリ自身のパス`lib/link`で判定する。
        self.start(["src/"], {"src/a.py": "x = 1\n"})
        (self.root / "lib").mkdir()
        os.symlink("../src/a.py", self.root / "lib" / "link")
        result, code = self.check_task()
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスlib/linkはTASK-001の変更許可パスの外です")])

    def test_a_changed_symlink_target_does_not_matter(self):
        # 基準版のリンク先も現在版のリンク先も読まない。リンクのエントリの変更（`M`）は、エントリ自身のパスだけで判定する。
        self.start(["src/"])
        (self.root / "src").mkdir()
        os.symlink("first", self.root / "src" / "link")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "link")
        os.unlink(self.root / "src" / "link")
        os.symlink("second", self.root / "src" / "link")
        result, code = self.check_task()
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_a_changes_path_through_a_symlink_is_not_rejected_and_matches_no_diff_path(self):
        # `changes`は字句の許可で、ファイルシステムを読まない。上位のディレクトリがシンボリックリンクのパスも拒否せず、どの差分のパスにも一致しないだけ。
        self.start(["lk/a.py"])
        (self.root / "real").mkdir()
        os.symlink("real", self.root / "lk")
        _write(self.root, "real/a.py", "x = 1\n")
        result, _code = self.check_task()
        self.assertEqual(
            _codes(result),
            [(TASK_BOUNDARY, "パスlkはTASK-001の変更許可パスの外です"),
             (TASK_BOUNDARY, "パスreal/a.pyはTASK-001の変更許可パスの外です")],
        )


class TaskChangesMultiWorkspaceTests(_TmpBase):
    def start(self, root_changes: list[str], web_changes: list[str]):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, ".spec/tasks/TASK-001.md", _task("TASK-001", root_changes))
        _write(self.root, "apps/web/.spec/tasks/TASK-010.md", _task("TASK-010", web_changes))
        _write(self.root, "services/api/keep", "x\n")
        _commit(self.root)

    def test_a_member_symlink_entry_toward_another_workspace_is_judged_only_by_its_own_path(self):
        self.start([], ["src/"])
        (self.root / "apps/web/src").mkdir()
        os.symlink("../../../services/api", self.root / "apps/web/src" / "link")
        result, code = _run("check", self.root, "web::TASK-010", "--base", "HEAD")
        self.assertEqual((result["status"], code, _codes(result)), ("passed", 0, []))

    def test_a_member_symlink_entry_outside_the_task_changes_is_a_boundary_violation_not_an_ownership_violation(self):
        self.start([], ["src/"])
        (self.root / "apps/web/lib").mkdir()
        os.symlink("../../../services/api", self.root / "apps/web/lib" / "link")
        result, code = _run("check", self.root, "web::TASK-010", "--base", "HEAD")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスlib/linkはweb::TASK-010の変更許可パスの外です")])

    def test_the_root_task_change_under_a_member_is_a_boundary_violation_and_not_an_ownership_violation(self):
        # ルートワークスペースのTASKがメンバーの配下の通常のファイルを変更しても、所有境界の違反にはせず、TASK境界で扱う。
        self.start(["src/"], ["src/"])
        _write(self.root, "apps/web/src/b.py", "y = 1\n")
        result, _code = _run("check", self.root, "platform::TASK-001", "--base", "HEAD")
        self.assertEqual(_codes(result), [(TASK_BOUNDARY, "パスapps/web/src/b.pyはplatform::TASK-001の変更許可パスの外です")])


class MemberPathTests(_TmpBase):
    """`multiws.precheck`のメンバーのパス（複合ワークスペース仕様 §2・§5.1）。"""

    def precheck(self):
        git = gitutil.detect_git(str(self.root), dict(os.environ))
        return multiws.precheck(str(self.root), git, dict(os.environ), extra_config_revs=[])

    def root_yaml(self, *members: tuple[str, str]) -> str:
        listed = "".join(f"    - id: {wid}\n      path: {path}\n" for wid, path in members)
        return CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n" + listed

    def member_yaml(self, wid: str) -> str:
        return CONFIG + f"workspace:\n  id: {wid}\n"

    def messages(self, pre) -> list[tuple[str, str]]:
        return [(d.code, d.summary) for d in pre.diagnostics]

    def test_a_terminal_symlink_member_is_a_path_violation(self):
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", "apps/web")))
        _write(self.root, "real_web/.spec/bitz.yaml", self.member_yaml("web"))
        (self.root / "apps").mkdir()
        os.symlink("../real_web", self.root / "apps" / "web")
        _commit(self.root)
        pre = self.precheck()
        self.assertFalse(pre.ok)
        self.assertEqual(self.messages(pre), [("SPEC-MULTI-PATH-001", "メンバーのパスの経路にシンボリックリンクが含まれています")])

    def test_an_intermediate_symlink_is_a_path_violation(self):
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", "apps/web")))
        _write(self.root, "real_apps/web/.spec/bitz.yaml", self.member_yaml("web"))
        os.symlink("real_apps", self.root / "apps")
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(self.messages(pre), [("SPEC-MULTI-PATH-001", "メンバーのパスの経路にシンボリックリンクが含まれています")])

    def test_a_symlink_member_without_a_config_is_still_a_path_violation(self):
        # メンバーの設定を読む前に、パスの存在の検査が拒否する。
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", "apps/web")))
        (self.root / "empty").mkdir()
        (self.root / "empty" / "keep").write_text("x")
        (self.root / "apps").mkdir()
        os.symlink("../empty", self.root / "apps" / "web")
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(self.messages(pre), [("SPEC-MULTI-PATH-001", "メンバーのパスの経路にシンボリックリンクが含まれています")])

    def test_a_different_case_spelling_of_the_member_path_has_no_member_config(self):
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", "Apps/web")))
        _write(self.root, "apps/web/.spec/bitz.yaml", self.member_yaml("web"))
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(self.messages(pre)[0], ("SPEC-MULTI-MEMBER-001", "メンバーの.spec/bitz.yamlがありません"))

    def test_an_nfc_collision_in_the_member_path_is_a_path_violation_with_the_dedicated_message(self):
        _require_nfc_nfd_distinct(self.tmp)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", f"apps/{NFC_NAME}")))
        _write(self.root, f"apps/{NFC_NAME}/.spec/bitz.yaml", self.member_yaml("web"))
        _write(self.root, f"apps/{NFD_NAME}/.spec/bitz.yaml", self.member_yaml("web"))
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(
            self.messages(pre),
            [("SPEC-MULTI-PATH-001", "NFCで同じ名前になる項目が複数あり、メンバーのパスが一つに決まりません")],
        )

    def test_an_nfd_directory_on_disk_matches_an_nfc_declaration_and_the_member_root_uses_the_disk_spelling(self):
        _require_nfc_nfd_distinct(self.tmp)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", f"apps/{NFC_NAME}")))
        _write(self.root, f"apps/{NFD_NAME}/.spec/bitz.yaml", self.member_yaml("web"))
        _commit(self.root)
        pre = self.precheck()
        self.assertTrue(pre.ok, pre.diagnostics)
        (member,) = pre.members
        self.assertEqual(member.path, f"apps/{NFC_NAME}")
        self.assertEqual(member.root, str(self.root / "apps" / NFD_NAME))

    def test_two_spellings_of_one_member_path_reach_the_same_directory(self):
        # NFCとNFDの綴りは同じディレクトリを指す。2件目のメンバーは、同じ設定のID（web）がカタログのID（web2）と一致しない。
        _require_nfc_nfd_distinct(self.tmp)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", f"apps/{NFC_NAME}"), ("web2", f"apps/{NFD_NAME}")))
        _write(self.root, f"apps/{NFC_NAME}/.spec/bitz.yaml", self.member_yaml("web"))
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(
            self.messages(pre), [("SPEC-MULTI-MEMBER-001", "メンバーの設定キーworkspace.idがカタログのIDと一致しません")]
        )

    def test_a_member_under_another_member_in_a_different_normalization_is_nested(self):
        _require_nfc_nfd_distinct(self.tmp)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", f"apps/{NFC_NAME}"), ("sub", f"apps/{NFD_NAME}/sub")))
        _write(self.root, f"apps/{NFC_NAME}/.spec/bitz.yaml", self.member_yaml("web"))
        _write(self.root, f"apps/{NFC_NAME}/sub/.spec/bitz.yaml", self.member_yaml("sub"))
        _commit(self.root)
        pre = self.precheck()
        self.assertEqual(self.messages(pre), [("SPEC-MULTI-PATH-001", "メンバーのパスが別のメンバーの配下にあります")])

    def test_members_that_differ_only_by_case_are_not_duplicates(self):
        _write(self.root, ".spec/bitz.yaml", self.root_yaml(("web", "apps/web"), ("web2", "apps/Web")))
        _write(self.root, "apps/web/.spec/bitz.yaml", self.member_yaml("web"))
        _write(self.root, "apps/Web/.spec/bitz.yaml", self.member_yaml("web2"))
        _commit(self.root)
        pre = self.precheck()
        self.assertTrue(pre.ok, pre.diagnostics)
        self.assertEqual([m.id for m in pre.members], ["web", "web2"])


class GitPathMatchingTests(_TmpBase):
    """Gitのパスと`implements`・`tests[].path`の逆索引の照合、CLIで明示したパスの照合（NFCの完全一致）。"""

    def test_an_nfd_git_path_selects_the_document_that_declares_the_nfc_implements_path(self):
        _require_nfc_nfd_distinct(self.tmp)
        req = (
            f"---\nid: REQ-001\ntitle: 要求\nstatus: draft\nimplements:\n  - src/{NFC_NAME}.py\n---\n\n"
            "# REQ-001 要求\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
            "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 守る。\n\n## Verification\n\n未証明。\n"
        )
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", req)
        _write(self.root, f"src/{NFD_NAME}.py", "x = 1\n")
        _commit(self.root)
        _write(self.root, f"src/{NFD_NAME}.py", "x = 2\n")
        result, code = _run("check", self.root, "--base", "HEAD")
        # 宣言（NFC）と、実体と差分のパス（NFD）は同じパスなので、実装パスは存在し、変更が所有する文書REQ-001へ対応する。
        self.assertEqual(
            result["selection"], {"changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0}
        )
        self.assertEqual([d for d in result["diagnostics"] if d["code"] == "SPEC-PATH-INVALID-001"], [], result)

    def test_exclude_member_paths_compares_nfc_segments(self):
        changed = [
            gitutil.ChangedPath(status="M", path=f"apps/{NFD_NAME}/a.py"),
            gitutil.ChangedPath(status="M", path=f"apps/{NFC_NAME}x/a.py"),
            gitutil.ChangedPath(status="M", path="apps/other/a.py"),
        ]
        kept = check_mod._exclude_member_paths(changed, [f"apps/{NFC_NAME}"])
        self.assertEqual([c.path for c in kept], [f"apps/{NFC_NAME}x/a.py", "apps/other/a.py"])

    def test_an_explicit_path_matches_the_document_path_in_nfc(self):
        doc_path = f".spec/requirements/{NFD_NAME}.md"
        index = pathown.build_nfc_path_index([(doc_path, "REQ-001")])
        for resolve in (check_mod._resolve_target, verify_mod._resolve_target):
            with self.subTest(resolve=resolve.__module__):
                self.assertEqual(resolve(f".spec/requirements/{NFC_NAME}.md", {}, {}, index), "REQ-001")
                self.assertEqual(resolve(doc_path, {}, {}, index), "REQ-001")
                self.assertIsNone(resolve(f".spec/requirements/{NFC_NAME.upper()}.md", {}, {}, index))

    def test_an_explicit_path_matching_two_documents_in_nfc_is_unresolved(self):
        index = pathown.build_nfc_path_index(
            [
                (f".spec/requirements/{NFC_NAME}.md", "REQ-001"),
                (f".spec/requirements/{NFD_NAME}.md", "REQ-002"),
                (".spec/requirements/REQ-003.md", "REQ-003"),
            ]
        )
        for resolve in (check_mod._resolve_target, verify_mod._resolve_target):
            with self.subTest(resolve=resolve.__module__):
                self.assertIsNone(resolve(f".spec/requirements/{NFC_NAME}.md", {}, {}, index))
                self.assertIsNone(resolve(f".spec/requirements/{NFD_NAME}.md", {}, {}, index))
                self.assertEqual(resolve(".spec/requirements/REQ-003.md", {}, {}, index), "REQ-003")

    def test_ambiguity_is_counted_over_all_spec_file_paths_including_skipped_documents(self):
        # 2つ目は文書の検査を省略した文書（索引へ入らない）。曖昧さは全仕様ファイルのパスで数えるので、索引へ入れない。
        pairs = [(f".spec/requirements/{NFC_NAME}.md", "REQ-001")]
        every = [f".spec/requirements/{NFC_NAME}.md", f".spec/requirements/{NFD_NAME}.md"]
        self.assertEqual(pathown.build_nfc_path_index(pairs), {pathown.nfc(f".spec/requirements/{NFC_NAME}.md"): "REQ-001"})
        self.assertEqual(pathown.build_nfc_path_index(pairs, all_paths=every), {})
        self.assertEqual(pathown.build_nfc_path_index(pairs, all_paths=every[:1]), {pathown.nfc(every[0]): "REQ-001"})

    def test_an_explicit_path_matching_a_skipped_document_too_is_missing_for_check_and_verify(self):
        _require_nfc_nfd_distinct(self.tmp)
        _write(self.root, ".spec/bitz.yaml", CONFIG)

        def req(doc_id: str) -> str:
            return (
                f"---\nid: {doc_id}\ntitle: 曖昧\nstatus: approved\n---\n\n# {doc_id} 曖昧\n\n## Intent\n\n意図。\n\n"
                f"## Acceptance Criteria\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 守る。\n\n## Verification\n\n未証明。\n"
            )

        _write(self.root, f".spec/requirements/REQ-001-{NFC_NAME}.md", req("REQ-001"))
        # ファイル名のIDとフロントマターのIDが一致しない（`skip-document`）。
        _write(self.root, f".spec/requirements/REQ-001-{NFD_NAME}.md", req("REQ-002"))
        _commit(self.root)
        argument = f".spec/requirements/REQ-001-{NFC_NAME}.md"
        for op in ("check", "verify"):
            with self.subTest(op=op):
                result, code = _run(op, self.root, argument, *(["--base", "HEAD"] if op == "check" else []))
                diagnostics = result["diagnostics"] if op == "check" else result["targetResults"][0]["diagnostics"]
                self.assertEqual([d["code"] for d in diagnostics], ["CTX-ROOT-MISSING-001"])
                self.assertEqual((result["status"], code), ("failed", 1))
        # 対照: NFD側の仕様ファイルがなければ、同じパスは解決する。
        (self.root / f".spec/requirements/REQ-001-{NFD_NAME}.md").unlink()
        result, code = _run("check", self.root, argument)
        self.assertEqual((result["status"], code, result["checkedDocumentCount"]), ("passed", 0, 1))


class ProcessArgvSpellingTests(_TmpBase):
    """`{tests}`の展開: プロセスへ渡す引数は、存在の検査で一致したファイルシステム上の綴りで組み立てる。公開結果の`argv`・`tests`は宣言の綴り（ワークスペース・設定仕様 §6）。

    Linuxの一時ディレクトリにNFDの名前のファイルとディレクトリを作り、宣言はNFCにして、プロセスが実際に受け取った引数を標準出力から読む。
    """

    PRINT = 'for f; do printf "%s\\n" "$f"; done'

    def start(self, tests_path: str, on_disk: str, cwd: str = ".", cwd_on_disk: str | None = None) -> None:
        _require_nfc_nfd_distinct(self.root)
        config = (
            CONFIG
            + f"verify:\n  commands:\n    t:\n      argv: [\"/bin/sh\", \"-c\", '{self.PRINT}', \"sh\", \"{{tests}}\"]\n"
            + f"      cwd: \"{cwd}\"\n"
        )
        _write(self.root, ".spec/bitz.yaml", config)
        _write(
            self.root,
            ".spec/requirements/REQ-001.md",
            f"---\nid: REQ-001\ntitle: 引数の綴り\nstatus: approved\ntests:\n  - path: \"{tests_path}\"\n    covers: [REQ-001:AC-01]\n    command: t\n---\n\n"
            "# REQ-001 引数の綴り\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
            "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n",
        )
        _write(self.root, on_disk, "x\n")
        _commit(self.root)

    def run_verify(self):
        result, code = _run("verify", self.root, "REQ-001")
        self.assertEqual((result["status"], code, result["diagnostics"]), ("passed", 0, []))
        self.assertEqual(len(result["commands"]), 1)
        return result["commands"][0]

    def test_a_declared_nfc_file_is_passed_to_the_process_in_the_disk_nfd_spelling(self):
        self.start(f"tests/{NFC_NAME}.py", f"tests/{NFD_NAME}.py")
        # 宣言の綴り（NFC）では、このファイルシステムでは開けない（前提）。
        self.assertFalse((self.root / f"tests/{NFC_NAME}.py").exists())
        command = self.run_verify()
        self.assertEqual(command["stdoutExcerpt"], f"tests/{NFD_NAME}.py\n")
        # 公開結果は宣言の綴り。
        self.assertEqual(command["argv"][-1], f"tests/{NFC_NAME}.py")
        self.assertEqual(command["tests"], [f"tests/{NFC_NAME}.py"])

    def test_a_disk_nfd_directory_in_the_middle_is_used_for_the_cwd_relative_argument(self):
        self.start(f"tests/{NFC_NAME}/a.py", f"tests/{NFD_NAME}/a.py", cwd="tests")
        self.assertFalse((self.root / f"tests/{NFC_NAME}").exists())
        command = self.run_verify()
        self.assertEqual(command["stdoutExcerpt"], f"{NFD_NAME}/a.py\n")
        self.assertEqual(command["argv"][-1], f"{NFC_NAME}/a.py")
        self.assertEqual(command["cwd"], "tests")

    def test_a_disk_nfd_cwd_directory_is_used_for_the_process_and_the_argument_is_cwd_relative(self):
        self.start(f"{NFC_NAME}/t.py", f"{NFD_NAME}/t.py", cwd=NFC_NAME)
        self.assertFalse((self.root / NFC_NAME).exists())
        command = self.run_verify()
        # `cwd`は実在の綴りで起動し、相対の引数は`cwd`の下の名前だけなので、綴りが分かれない。
        self.assertEqual(command["stdoutExcerpt"], "t.py\n")
        self.assertEqual((command["cwd"], command["argv"][-1]), (NFC_NAME, "t.py"))

    def test_an_ascii_path_is_unchanged(self):
        self.start("tests/t.py", "tests/t.py")
        command = self.run_verify()
        self.assertEqual((command["stdoutExcerpt"], command["argv"][-1]), ("tests/t.py\n", "tests/t.py"))


if __name__ == "__main__":
    unittest.main()
