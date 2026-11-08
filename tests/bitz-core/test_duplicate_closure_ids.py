"""閉包を作るときに辿る文書IDの重複を、`context`・`verify`・`check`が返す単体試験（確認事項C96、関係・トレースモデル §5.1）。

規範（§5.1。コミット`9543de42`の書き直し）: 文書IDの重複（`SPEC-ID-DUPLICATE-001`、`failed`）は、`context`と`verify`では、閉包を作るときに辿るID
（起点、`requires`、`refines`、`addresses`の参照先、置換の参照先（`supersedes`の参照先の旧文書と、起点を置換する後継）、逆参照で閉包に入る文書のID。
`related`の参照先は含めない）が重複していれば、その結果（`verify`は当該の検証対象）へ返す。起点のIDが重複している場合は`CTX-ROOT-MISSING-001`に併記する。
`check`は、文書IDの一意性をカタログ全体の検査として扱い、スコープ（明示対象、引数なし、`--full`）によらず作業ワークスペースのすべての重複を返し、閉包で辿る他のワークスペースの
重複も返す。診断の文言と発生元は`check`の完全検査の診断と同じ（複合ワークスペースでは、重複した文書を所有するワークスペース）。

修正前のCoreは、閉包を作るときに重複したIDを黙って辿らず（重複した文書はどちらも索引に入らない）、`context`と`verify`は`passed`を返した。
各試験の期待値は規範と承認済みの文言のリテラルで、Coreの出力からは導かない。対照の試験（`related`だけで指す重複、閉包と無関係な重複（`context`と`verify`）、重複していない場合）は、
修正前のCoreも通る。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import targetexpand
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
DUPLICATE = "SPEC-ID-DUPLICATE-001"
ROOT_MISSING = "CTX-ROOT-MISSING-001"
HEAD = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
COMMAND = 'verify:\n  commands:\n    default:\n      argv: ["/bin/sh", "-c", "touch ran.marker", "{tests}"]\n      cwd: .\n'


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _relations(**relations: list[str]) -> str:
    items = {name: refs for name, refs in relations.items() if refs}
    if not items:
        return ""
    return "relations:\n" + "".join(f"  {name}: [{', '.join(refs)}]\n" for name, refs in items.items())


def _req(doc_id: str, *, test_path: str = "tests/t.py", status: str = "approved", **relations: list[str]) -> str:
    """規範文AC-01を1件持ち、自身の`tests`でそれを`covers`するREQ。"""

    return (
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: {status}\n{_relations(**relations)}"
        f"tests:\n  - path: {test_path}\n    covers: [{doc_id}:AC-01]\n    command: default\n---\n\n"
        f"# {doc_id} REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, **relations: list[str]) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n{_relations(**relations)}---\n\n"
        f"# {doc_id} TECH\n\n## Context\n\n本文。\n"
    )


def _task(doc_id: str, addresses: list[str]) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 作業\nstatus: open\n{_relations(addresses=addresses)}---\n\n"
        f"# {doc_id} 作業\n\n## Objective\n\n作業する。\n"
    )


def dup_diag(doc_id: str, path: str, workspace_id: str = "root", *, qualified: bool = False) -> dict:
    """`check`の完全検査が返す、文書IDの重複の診断（発生元は重複した写しのうちパスの辞書順で最初のファイル）。"""

    shown = f"{workspace_id}::{doc_id}" if qualified else doc_id
    return {
        "code": DUPLICATE, "severity": "error", "resultStatus": "failed", "summary": f"文書ID {shown}が重複しています",
        "source": {"kind": "file", "workspaceId": workspace_id, "path": path, "key": "id"},
    }


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def commit(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")

    def run_op(self, module, name: str, *argv: str, cwd: Path | None = None):
        return module.run(parse_argv([name, *argv, "--format", "json"]), str(cwd or self.root), self.env)[0]

    def context_diags(self, *roots: str) -> list[dict]:
        return self.run_op(context_mod, "context", *roots, "--purpose", "verify")["diagnostics"]

    def verify_diags(self, root: str) -> list[dict]:
        result = self.run_op(verify_mod, "verify", root)
        found = [t for t in result["targetResults"] if t["target"].endswith(root)]
        self.assertEqual(len(found), 1, result)
        return found[0]["diagnostics"]

    def check_diags(self, *argv: str) -> list[dict]:
        return self.run_op(check_mod, "check", *argv)["diagnostics"]

    def operations(self, root: str) -> dict[str, list[dict]]:
        """同じ起点を3つの操作に与えたときの診断（`verify`は当該の検証対象の診断）。"""

        return {"context": self.context_diags(root), "verify": self.verify_diags(root), "check": self.check_diags(root)}

    def assert_returned(self, root: str, expected: dict, *, only: tuple[str, ...] = ("context", "verify", "check")) -> None:
        for operation, diagnostics in self.operations(root).items():
            if operation in only:
                with self.subTest(operation=operation):
                    self.assertIn(expected, diagnostics)

    def assert_not_returned(self, root: str, *, only: tuple[str, ...] = ("context", "verify", "check")) -> None:
        for operation, diagnostics in self.operations(root).items():
            if operation in only:
                with self.subTest(operation=operation):
                    self.assertNotIn(DUPLICATE, [d["code"] for d in diagnostics])


class SingleWorkspaceTests(_Base):
    """単一ワークスペース。閉包は、`REQ-001`と、それを`refines`する`TECH-001`など。重複した文書は`<ID>.md`と`<ID>-copy.md`の同じ内容の2ファイル。"""

    def build(self, files: dict[str, str]) -> None:
        _write(self.root, ".spec/bitz.yaml", HEAD + COMMAND)
        _write(self.root, "tests/t.py", "x\n")
        for rel, content in files.items():
            _write(self.root, rel, content)
        self.commit()

    def duplicated(self, directory: str, doc_id: str, content: str) -> dict[str, str]:
        return {f".spec/{directory}/{doc_id}.md": content, f".spec/{directory}/{doc_id}-copy.md": content}

    def first_path(self, directory: str, doc_id: str) -> str:
        """パスの辞書順で最初の写し。`-`は`.`より前なので`-copy.md`が先になる。"""

        return f".spec/{directory}/{doc_id}-copy.md"

    # --- 欠陥（修正前のCoreが失敗する） -----------------------------------------------------

    def test_origin_duplicate_is_added_to_root_missing(self):
        """起点のIDが重複して索引にないときは、`CTX-ROOT-MISSING-001`に併記する。"""

        self.build(self.duplicated("requirements", "REQ-001", _req("REQ-001")))
        expected = dup_diag("REQ-001", self.first_path("requirements", "REQ-001"))
        for operation, diagnostics in self.operations("REQ-001").items():
            with self.subTest(operation=operation):
                self.assertIn(ROOT_MISSING, [d["code"] for d in diagnostics])
                self.assertIn(expected, diagnostics)

    def test_origin_duplicate_by_path_and_statement_id(self):
        """起点を規範文IDや文書のパスで指しても、所有する文書のIDの重複を併記する（`context`は文書のパスを受け付けない）。"""

        self.build(self.duplicated("requirements", "REQ-001", _req("REQ-001")))
        expected = dup_diag("REQ-001", self.first_path("requirements", "REQ-001"))
        statement_diags = {"context": self.context_diags("REQ-001:AC-01"), "verify": self.verify_diags("REQ-001:AC-01"),
                           "check": self.check_diags("REQ-001:AC-01")}
        path_diags = {"verify": self.verify_diags(".spec/requirements/REQ-001.md"), "check": self.check_diags(".spec/requirements/REQ-001.md")}
        for root, by_operation in (("REQ-001:AC-01", statement_diags), (".spec/requirements/REQ-001.md", path_diags)):
            for operation, diagnostics in by_operation.items():
                with self.subTest(root=root, operation=operation):
                    self.assertIn(ROOT_MISSING, [d["code"] for d in diagnostics])
                    self.assertIn(expected, diagnostics)

    def test_requires_target_duplicate_is_returned(self):
        files = {".spec/requirements/REQ-001.md": _req("REQ-001", requires=["TECH-003"])}
        files.update(self.duplicated("technical", "TECH-003", _tech("TECH-003")))
        self.build(files)
        self.assert_returned("REQ-001", dup_diag("TECH-003", self.first_path("technical", "TECH-003")))

    def test_refines_target_duplicate_is_returned(self):
        files = {".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"])}
        files.update(self.duplicated("requirements", "REQ-001", _req("REQ-001")))
        self.build(files)
        self.assert_returned("TECH-001", dup_diag("REQ-001", self.first_path("requirements", "REQ-001")))

    def test_reverse_refines_duplicate_is_returned(self):
        """再現済みの欠陥: 閉包に逆参照の`refines`で入る`TECH-002`が2つあるとき、黙って除外せずに返す（`check`は修正前も返す）。"""

        files = {
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"]),
        }
        files.update(self.duplicated("technical", "TECH-002", _tech("TECH-002", refines=["TECH-001"])))
        self.build(files)
        self.assert_returned("REQ-001", dup_diag("TECH-002", self.first_path("technical", "TECH-002")))

    def test_reverse_refines_duplicate_when_only_one_copy_refines(self):
        """重複した写しのどちらかが閉包の文書を`refines`していればよい。"""

        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["REQ-001"]),
            ".spec/technical/TECH-002-copy.md": _tech("TECH-002"),
        })
        self.assert_returned("REQ-001", dup_diag("TECH-002", self.first_path("technical", "TECH-002")))

    def test_addresses_target_duplicate_is_returned(self):
        files = {".spec/tasks/TASK-001.md": _task("TASK-001", ["REQ-001:AC-01"])}
        files.update(self.duplicated("requirements", "REQ-001", _req("REQ-001")))
        self.build(files)
        self.assert_returned("TASK-001", dup_diag("REQ-001", self.first_path("requirements", "REQ-001")), only=("context", "verify"))

    def test_superseding_successor_duplicate_is_returned(self):
        """置換の後継（`supersedes`で起点を置換する文書）のIDが重複していれば返す。"""

        files = {".spec/requirements/REQ-001.md": _req("REQ-001")}
        files.update(self.duplicated("requirements", "REQ-002", _req("REQ-002", test_path="tests/u.py", supersedes=["REQ-001"])))
        self.build(files)
        self.assert_returned("REQ-001", dup_diag("REQ-002", self.first_path("requirements", "REQ-002")))

    def test_only_the_affected_verify_target_gets_the_duplicate(self):
        """独立した検証対象は影響を受けず、そのテストを起動する。重複を返した検証対象のテストは起動しない。"""

        files = {
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/requirements/REQ-002.md": _req("REQ-002", test_path="tests/u.py"),
        }
        files.update(self.duplicated("technical", "TECH-002", _tech("TECH-002", refines=["REQ-001"])))
        self.build(files)
        _write(self.root, "tests/u.py", "x\n")
        result = self.run_op(verify_mod, "verify", "REQ-001", "REQ-002")
        targets = {t["target"]: t for t in result["targetResults"]}
        self.assertEqual(targets["REQ-001"]["status"], "failed")
        self.assertIn(dup_diag("TECH-002", self.first_path("technical", "TECH-002")), targets["REQ-001"]["diagnostics"])
        self.assertEqual(targets["REQ-002"]["status"], "passed")
        self.assertEqual(targets["REQ-002"]["diagnostics"], [])
        self.assertEqual([c["tests"] for c in result["commands"]], [["tests/u.py"]])
        self.assertEqual(result["diagnostics"], [])

    def test_other_roots_are_resolved_when_one_root_is_missing(self):
        """索引にない起点があっても、解決できた起点の閉包で辿る重複を返す。"""

        files = {
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"]),
        }
        files.update(self.duplicated("technical", "TECH-002", _tech("TECH-002", refines=["TECH-001"])))
        self.build(files)
        diagnostics = self.context_diags("REQ-001", "REQ-099")
        self.assertEqual(sorted(d["code"] for d in diagnostics), [ROOT_MISSING, DUPLICATE])

    def test_superseded_old_document_duplicate_is_returned_with_relation_missing(self):
        """閉包の文書が`supersedes`で置き換える旧文書が重複していれば、`requires`の参照先の重複と同じく、`SPEC-RELATION-MISSING-001`と並べて返す。"""

        files = {".spec/requirements/REQ-002.md": _req("REQ-002", test_path="tests/u.py", supersedes=["REQ-001"])}
        files.update(self.duplicated("requirements", "REQ-001", _req("REQ-001")))
        self.build(files)
        expected = dup_diag("REQ-001", self.first_path("requirements", "REQ-001"))
        for operation, diagnostics in {"context": self.context_diags("REQ-002"), "verify": self.verify_diags("REQ-002"),
                                       "check": self.check_diags("REQ-002")}.items():
            with self.subTest(operation=operation):
                self.assertIn(expected, diagnostics)
                if operation != "check":
                    self.assertEqual(sorted(d["code"] for d in diagnostics), [DUPLICATE, "SPEC-RELATION-MISSING-001"])

    def test_multiple_successors_duplicate_is_returned_by_interpret(self):
        """目的`interpret`で、起点を置換する後継の1つが重複していれば返す（重複を解消すると後継が複数になる）。"""

        files = {".spec/requirements/REQ-001.md": _req("REQ-001"),
                 ".spec/requirements/REQ-002.md": _req("REQ-002", test_path="tests/u.py", supersedes=["REQ-001"])}
        files.update(self.duplicated("requirements", "REQ-003", _req("REQ-003", test_path="tests/u.py", supersedes=["REQ-001"])))
        self.build(files)
        diagnostics = self.run_op(context_mod, "context", "REQ-001", "--purpose", "interpret")["diagnostics"]
        self.assertEqual(diagnostics, [dup_diag("REQ-003", self.first_path("requirements", "REQ-003"))])

    def test_requires_closure_of_the_task_origin_is_traversed_by_verify(self):
        """`verify`のTASK起点は、コンテキストへ含めない起点の`requires`の閉包も辿る。その参照先の重複を返す。"""

        files = {
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/tasks/TASK-001.md": _task("TASK-001", ["REQ-001:AC-01"]).replace(
                "relations:\n", "relations:\n  requires: [REQ-005]\n", 1),
        }
        files.update(self.duplicated("requirements", "REQ-005", _req("REQ-005", test_path="tests/u.py")))
        self.build(files)
        self.assertIn(dup_diag("REQ-005", self.first_path("requirements", "REQ-005")), self.verify_diags("TASK-001"))
        self.assertIn(dup_diag("REQ-005", self.first_path("requirements", "REQ-005")), self.context_diags("TASK-001"))

    def test_duplicate_is_kept_with_state_errors_of_the_closure(self):
        """閉包に状態の診断（状態`draft`の`requires`の参照先）があっても、辿る重複を落とさない。"""

        draft = _tech("TECH-003").replace("status: approved", "status: draft")
        files = {".spec/requirements/REQ-001.md": _req("REQ-001", requires=["TECH-003"]), ".spec/technical/TECH-003.md": draft}
        files.update(self.duplicated("technical", "TECH-002", _tech("TECH-002", refines=["REQ-001"])))
        self.build(files)
        diagnostics = self.context_diags("REQ-001")
        self.assertEqual(sorted(d["code"] for d in diagnostics), ["CTX-STATE-001", DUPLICATE])
        self.assertIn(dup_diag("TECH-002", self.first_path("technical", "TECH-002")), diagnostics)

    def test_verify_with_many_unrelated_duplicates_does_not_rebuild_every_closure(self):
        """性能: 起点から強い関係でつながらない重複は、閉包を作り直さずに除く。結果は、つながる重複だけを各検証対象へ返す。"""

        count = 30
        files = {}
        for number in range(1, count + 1):
            files[f".spec/requirements/REQ-{number:03d}.md"] = _req(f"REQ-{number:03d}")
            files.update(self.duplicated("technical", f"TECH-{number:03d}", _tech(f"TECH-{number:03d}", refines=[f"REQ-{number:03d}"])))
        self.build(files)
        real = targetexpand.target_expansion
        with mock.patch.object(targetexpand, "target_expansion", wraps=real) as spy:
            result = self.run_op(verify_mod, "verify")
        for entry in result["targetResults"]:
            number = entry["target"].partition("-")[2]
            self.assertEqual(entry["diagnostics"], [dup_diag(f"TECH-{number}", self.first_path("technical", f"TECH-{number}"))], entry["target"])
        # 検証対象ごとに、基準の1回と、つながる重複の写し2つ分だけ（全重複を試すと30 * (1 + 30 * 2) = 1830回になる）。
        self.assertLessEqual(spy.call_count, count * 3)

    def test_verify_with_a_shared_required_document_does_not_rebuild_every_closure(self):
        """性能: 多くの文書が共通の文書を`requires`するだけでは、重複は起点から辿り着けない（閉包の辺の向きにだけ辿る）。共通の文書から他の起点へ逆戻りして試さない。"""

        count = 30
        files = {".spec/technical/TECH-900.md": _tech("TECH-900")}
        for number in range(1, count + 1):
            files[f".spec/requirements/REQ-{number:03d}.md"] = _req(f"REQ-{number:03d}", requires=["TECH-900"])
            files.update(self.duplicated("technical", f"TECH-{number:03d}", _tech(f"TECH-{number:03d}", refines=[f"REQ-{number:03d}"])))
        self.build(files)
        real = targetexpand.target_expansion
        with mock.patch.object(targetexpand, "target_expansion", wraps=real) as spy:
            result = self.run_op(verify_mod, "verify")
        for entry in result["targetResults"]:
            number = entry["target"].partition("-")[2]
            if number == "900":
                continue
            self.assertEqual(entry["diagnostics"], [dup_diag(f"TECH-{number}", self.first_path("technical", f"TECH-{number}"))], entry["target"])
        self.assertLessEqual(spy.call_count, (count + 1) * 3)

    def test_implement_traverses_the_open_task_that_addresses_a_target_statement(self):
        """目的`implement`では、対象規範文を`addresses`する状態`open`のTASKが逆参照で閉包に入る。そのTASKのIDの重複を返す。"""

        files = {".spec/requirements/REQ-001.md": _req("REQ-001")}
        files.update(self.duplicated("tasks", "TASK-001", _task("TASK-001", ["REQ-001:AC-01"])))
        self.build(files)
        diagnostics = self.run_op(context_mod, "context", "REQ-001", "--purpose", "implement")["diagnostics"]
        self.assertIn(dup_diag("TASK-001", self.first_path("tasks", "TASK-001")), diagnostics)

    # --- 対照 -------------------------------------------------------------------------------

    def test_related_only_duplicate_is_not_returned(self):
        """対照: `related`の参照先は閉包を作るときに辿らないので、重複を返さない。"""

        files = {
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"], related=["TECH-009"]),
        }
        files.update(self.duplicated("technical", "TECH-009", _tech("TECH-009")))
        self.build(files)
        self.assert_not_returned("REQ-001", only=("context", "verify"))
        # 重複した文書は索引に入らないので、`related`の参照切れの警告だけが残り、検証対象は失敗しない。
        self.assertEqual(self.run_op(verify_mod, "verify", "REQ-001")["status"], "passed_with_warnings")
        self.assertEqual([d["code"] for d in self.verify_diags("REQ-001")], ["SPEC-RELATION-ADVISORY-MISSING-001"])

    def test_related_only_duplicate_that_refines_nothing_in_closure_is_not_returned(self):
        """対照: 重複した写しが閉包の文書を`related`するだけなら、逆参照で閉包に入らない。"""

        files = {".spec/requirements/REQ-001.md": _req("REQ-001")}
        files.update(self.duplicated("technical", "TECH-009", _tech("TECH-009", related=["REQ-001"])))
        self.build(files)
        self.assert_not_returned("REQ-001", only=("context", "verify"))

    def test_unrelated_duplicate_is_not_returned_by_context_and_verify_but_by_check_in_every_scope(self):
        """対照: 閉包と無関係な重複は、`context`と`verify`に返さない。`check`は文書IDの一意性をカタログ全体の検査として扱い、スコープ（明示対象、引数なし、`--full`）によらず返す。"""

        files = {".spec/requirements/REQ-001.md": _req("REQ-001")}
        files.update(self.duplicated("technical", "TECH-008", _tech("TECH-008")))
        self.build(files)
        self.assert_not_returned("REQ-001", only=("context", "verify"))
        expected = dup_diag("TECH-008", self.first_path("technical", "TECH-008"))
        for scope in (("REQ-001",), (), ("--full",)):
            with self.subTest(scope=scope):
                self.assertEqual([d for d in self.check_diags(*scope) if d["code"] == DUPLICATE], [expected])

    def test_without_duplicates_nothing_is_added(self):
        """対照: 重複がなければ、3つの操作とも成功し、重複の診断を返さない。"""

        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"]),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["TECH-001"]),
        })
        self.assertEqual(self.operations("REQ-001"), {"context": [], "verify": [], "check": []})


class MultiWorkspaceTests(_Base):
    """複合ワークスペース。ルート`platform`の`REQ-001`と、`web`の`TECH-005`（`platform::REQ-001`を`refines`）など。"""

    def build(self, web_files: dict[str, str], platform_files: dict[str, str] | None = None) -> None:
        _write(
            self.root, ".spec/bitz.yaml",
            HEAD + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"
            + COMMAND,
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", HEAD + "workspace:\n  id: web\n" + COMMAND)
        _write(self.root, "services/api/.spec/bitz.yaml", HEAD + "workspace:\n  id: api\n")
        _write(self.root, "tests/t.py", "x\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        for rel, content in (platform_files or {}).items():
            _write(self.root, rel, content)
        for rel, content in web_files.items():
            _write(self.root, f"apps/web/{rel}", content)
        self.commit()

    @staticmethod
    def web_duplicated(doc_id: str, content: str) -> dict[str, str]:
        return {f".spec/technical/{doc_id}.md": content, f".spec/technical/{doc_id}-copy.md": content}

    def web_dup(self, doc_id: str) -> dict:
        return dup_diag(doc_id, f".spec/technical/{doc_id}-copy.md", "web", qualified=True)

    def test_other_member_reverse_refines_duplicate_is_returned(self):
        """他のメンバー`web`の`TECH-005`が重複し、`platform::REQ-001`を逆参照の`refines`で閉包へ入れる。所有ワークスペースの発生元と修飾IDの文言で返す。"""

        self.build(self.web_duplicated("TECH-005", _tech("TECH-005", refines=["platform::REQ-001"])))
        self.assert_returned("REQ-001", self.web_dup("TECH-005"))

    def test_other_member_duplicate_is_returned_for_verify_all_workspaces(self):
        files = {".spec/technical/TECH-010.md": _tech("TECH-010", refines=["platform::REQ-001:AC-01"])}
        files[".spec/technical/TECH-010.md"] = files[".spec/technical/TECH-010.md"].replace(
            "---\n\n#", "tests:\n  - path: tests/web.py\n    covers: [platform::REQ-001:AC-01]\n    command: default\n---\n\n#", 1)
        files.update(self.web_duplicated("TECH-005", _tech("TECH-005", refines=["platform::REQ-001"])))
        self.build(files)
        result = self.run_op(verify_mod, "verify", "--all-workspaces")
        platform = next(w for w in result["workspaces"] if w["id"] == "platform")
        target = next(t for t in platform["targetResults"] if t["target"] == "platform::REQ-001")
        self.assertEqual(target["status"], "failed")
        self.assertIn(self.web_dup("TECH-005"), target["diagnostics"])

    def test_forward_refines_target_in_other_member_is_returned(self):
        """作業ワークスペース`web`の`TECH-010`が`platform::REQ-001`を`refines`し、その`platform::REQ-001`が重複している。"""

        self.build(
            {".spec/technical/TECH-010.md": _tech("TECH-010", refines=["platform::REQ-001"])},
            platform_files={".spec/requirements/REQ-001-copy.md": _req("REQ-001")},
        )
        expected = dup_diag("REQ-001", ".spec/requirements/REQ-001-copy.md", "platform", qualified=True)
        self.assertIn(expected, self.context_diags("web::TECH-010"))
        self.assertIn(expected, self.verify_diags("web::TECH-010"))
        self.assertIn(expected, self.check_diags("web::TECH-010"))

    def test_origin_duplicate_in_the_working_member(self):
        self.build(self.web_duplicated("TECH-005", _tech("TECH-005", refines=["platform::REQ-001"])))
        for operation, diagnostics in self.operations("web::TECH-005").items():
            with self.subTest(operation=operation):
                self.assertIn(ROOT_MISSING, [d["code"] for d in diagnostics])
                self.assertIn(self.web_dup("TECH-005"), diagnostics)

    def test_check_without_arguments_returns_duplicate_in_strong_closure_of_changed_document(self):
        """引数なしの`check`は、変更から選んだ文書の強い関係の閉包にある他のメンバーの重複を返す。"""

        self.build(
            {".spec/technical/TECH-010.md": _tech("TECH-010", refines=["platform::REQ-001"])},
            platform_files={".spec/requirements/REQ-001-copy.md": _req("REQ-001")},
        )
        _write(self.root, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010", refines=["platform::REQ-001"]) + "\n追記。\n")
        diagnostics = self.check_diags("--workspace", "web")
        self.assertIn(dup_diag("REQ-001", ".spec/requirements/REQ-001-copy.md", "platform", qualified=True), diagnostics)

    def test_working_workspace_duplicate_is_returned_once(self):
        """作業ワークスペース自身の重複は、完全検査の一覧の診断だけが返し、他のメンバーの重複の経路で二重に返さない。"""

        files = {".spec/technical/TECH-020.md": _tech("TECH-020", refines=["REQ-001"]),
                 ".spec/technical/TECH-020-copy.md": _tech("TECH-020", refines=["REQ-001"])}
        self.build({}, platform_files=files)
        expected = dup_diag("TECH-020", ".spec/technical/TECH-020-copy.md", "platform", qualified=True)
        for scope in (("REQ-001",), ("--full",)):
            with self.subTest(scope=scope):
                self.assertEqual([d for d in self.check_diags(*scope) if d["code"] == DUPLICATE], [expected])

    def test_check_with_the_path_of_a_duplicate_document_does_not_fail(self):
        """索引に入らない（重複した）文書のパスを明示しても落ちず、起点の不在に重複を併記する。"""

        self.build({}, platform_files={".spec/requirements/REQ-001-copy.md": _req("REQ-001")})
        diagnostics = self.check_diags(".spec/requirements/REQ-001.md")
        self.assertEqual(sorted(d["code"] for d in diagnostics), [ROOT_MISSING, DUPLICATE])
        self.assertIn(dup_diag("REQ-001", ".spec/requirements/REQ-001-copy.md", "platform", qualified=True), diagnostics)

    def test_all_workspaces_verify_keeps_duplicate_with_dependency_on_an_invalid_document(self):
        """`--all-workspaces`で、閉包が他のワークスペースの無効な文書に依存して遮断される検証対象にも、辿る重複を並べる。"""

        invalid = _req("REQ-201").replace("[CONSTRAINT]", "[BOGUSTAG]")
        platform_files = {"services/api/.spec/requirements/REQ-201.md": invalid}
        web_files = {".spec/requirements/REQ-101.md": _req("REQ-101", requires=["api::REQ-201"]), "tests/t.py": "x\n"}
        web_files.update(self.web_duplicated("TECH-105", _tech("TECH-105", refines=["REQ-101"])))
        self.build(web_files, platform_files=platform_files)
        result = self.run_op(verify_mod, "verify", "--all-workspaces")
        web = next(w for w in result["workspaces"] if w["id"] == "web")
        target = next(t for t in web["targetResults"] if t["target"] == "web::REQ-101")
        codes = sorted(d["code"] for d in target["diagnostics"])
        self.assertIn("SPEC-MULTI-DEPENDENCY-001", codes)
        self.assertIn(self.web_dup("TECH-105"), target["diagnostics"])

    # --- 対照 -------------------------------------------------------------------------------

    def test_check_without_arguments_ignores_other_member_duplicate_without_changes(self):
        """対照: 変更がなければ、他のメンバーの重複は閉包に入らず返さない。"""

        self.build(
            {".spec/technical/TECH-010.md": _tech("TECH-010", refines=["platform::REQ-001"])},
            platform_files={".spec/requirements/REQ-001-copy.md": _req("REQ-001")},
        )
        self.assertNotIn(DUPLICATE, [d["code"] for d in self.check_diags("--workspace", "web")])

    def test_other_member_related_only_duplicate_is_not_returned(self):
        """対照: `platform::REQ-001`が`related`だけで指す`web`の重複は、閉包を作るときに辿らない。"""

        files = self.web_duplicated("TECH-007", _tech("TECH-007"))
        self.build(files, platform_files={".spec/requirements/REQ-001.md": _req("REQ-001", related=["web::TECH-007"])})
        self.assert_not_returned("REQ-001")

    def test_other_member_related_back_reference_is_not_returned(self):
        """対照: 重複した写しが`platform::REQ-001`を`related`するだけなら、逆参照で閉包に入らない。"""

        self.build(self.web_duplicated("TECH-007", _tech("TECH-007", related=["platform::REQ-001"])))
        self.assert_not_returned("REQ-001")

    def test_unrelated_other_member_duplicate_is_not_returned(self):
        """対照: 閉包と無関係な他のメンバーの重複は返さない。"""

        self.build(self.web_duplicated("TECH-008", _tech("TECH-008")))
        self.assert_not_returned("REQ-001")


if __name__ == "__main__":
    unittest.main()
