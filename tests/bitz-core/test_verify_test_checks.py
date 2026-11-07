"""`verify`が、その検証対象が使うテスト対応のテストのパスと`covers`を検査する単体試験（確認事項 N2・C92、PR-cの独立レビューのM1）。

欠陥: `verify`は、検証対象が使うテスト対応のテストのパスの存在と所有境界も、`covers`の妥当性も検査していなかった。
そのため、単一ワークスペースでは存在しないパスやディレクトリのテストを起動して`passed`にし、推移的な`refines`の`covers`のような
不正な`covers`を数えて`passed`にした。複合ワークスペースでは、所有領域の外のパスも検査せずに起動した（`check`は同じ入力を`failed`にする）。

規範（`bitz verify`仕様 §4の4.と、その後の段落、§9）:
- 検査の対象は、その検証対象が使うテスト対応（対象規範文を`covers`するテスト対応。規範文のないTECHは文書単位の`tests`）だけである。
- テストのパスの存在と所有境界は`check`と同じ規則、`covers`の妥当性は文書仕様のテスト対応の規則（(a)〜(c)、複合の横断は直接`refines`だけ）で判定する。
- 違反は`check`と同じ診断（不在・不正は`SPEC-PATH-INVALID-001`、複合ワークスペースで所有領域の外は`SPEC-MULTI-OWNERSHIP-001`、
  `covers`は`SPEC-TEST-COVERAGE-001`。文言と発生元は同じ）を検証対象の`diagnostics`へ返し、その検証対象は`failed`、`bindingRefs: []`で、
  テストを起動しない（`skip-target`）。カバレッジ（§4の3.）は宣言どおりのテスト対応で数える。独立した検証対象は続ける。
- 検証対象が使わないテスト対応と`implements`は検査しない（`check`の責務）。

試験名の接頭辞: `test_defect_`は修正前のCoreで失敗する（欠陥の検出）、`test_control_`は修正前のCoreでも通る（対照）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
TECH_PATH = ".spec/technical/TECH-001.md"
CHECK_CODES = ("SPEC-PATH-INVALID-001", "SPEC-MULTI-OWNERSHIP-001", "SPEC-TEST-COVERAGE-001")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str = "x\n") -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _tests_block(tests) -> str:
    """``tests``は`(パス, covers, コマンド名)`の並び。"""
    if not tests:
        return ""
    return "tests:\n" + "".join(
        f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: {command}\n" for path, covers, command in tests
    )


def _req(doc_id: str, *, statements: int = 2, tests=(), implements=()) -> str:
    front = f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
    if implements:
        front += f"implements: [{', '.join(implements)}]\n"
    front += _tests_block(tests)
    lines = "".join(
        f"- [{doc_id}:AC-{n:02d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 規範文{n}を満たす。\n"
        for n in range(1, statements + 1)
    )
    return (
        f"{front}---\n\n# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{lines}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, refines=None, tests=(), implements=()) -> str:
    """規範文を持たないTECH。"""
    front = f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
    if refines:
        front += f"relations:\n  refines: [{', '.join(refines)}]\n"
    if implements:
        front += f"implements: [{', '.join(implements)}]\n"
    front += _tests_block(tests)
    return f"{front}---\n\n# {doc_id} {doc_id}の文書\n\n## Context\n\n本文。\n"


def _without_durations(value):
    if isinstance(value, dict):
        return {k: _without_durations(v) for k, v in value.items() if k != "durationMs"}
    if isinstance(value, list):
        return [_without_durations(v) for v in value]
    return value


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        self.root = self.base / "repo"
        self.outside = self.base / "outside"
        self.root.mkdir()
        self.outside.mkdir()
        _write(self.outside, "test_x.py")
        self.env = dict(os.environ)

    def commit(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def verify(self, *argv: str):
        result, code = verify_mod.run(parse_argv(["verify", *argv, "--format", "json"]), str(self.root), self.env)
        return result, code

    def check_diagnostics(self, *argv: str) -> list[dict]:
        """同じ入力に対する`check`の診断（検査の対象の3コードだけ）。最上位、ワークスペースの順に集める。"""
        result, _ = check_mod.run(parse_argv(["check", *argv, "--base", "HEAD", "--format", "json"]), str(self.root), self.env)
        diagnostics = list(result["diagnostics"])
        for workspace in result.get("workspaces", []):
            diagnostics.extend(workspace["diagnostics"])
        return [d for d in diagnostics if d["code"] in CHECK_CODES]

    @staticmethod
    def targets(result: dict) -> dict[str, dict]:
        items = list(result.get("targetResults", []))
        for workspace in result.get("workspaces", []):
            items += workspace["targetResults"]
        return {item["target"]: item for item in items}

    @staticmethod
    def codes(target: dict) -> list[tuple[str, str, str | None]]:
        return [(d["code"], d["source"]["path"], d["source"].get("key")) for d in target["diagnostics"]]

    def assertSkippedTarget(self, target: dict) -> None:
        """違反した検証対象: `failed`、`bindingRefs: []`、コンテキストは構成済み（`contextDigest`は非`null`）。"""
        self.assertEqual(target["status"], "failed")
        self.assertEqual(target["bindingRefs"], [])
        self.assertIsNotNone(target["contextDigest"])

    def assertSameAsCheck(self, target: dict, *check_argv: str) -> None:
        """検証対象の違反の診断が、同じ入力に対する`check`の診断と、コード・文言・発生元・証拠まで同じである。"""
        found = [d for d in target["diagnostics"] if d["code"] in CHECK_CODES]
        self.assertTrue(found)
        in_check = self.check_diagnostics(*check_argv)
        for diagnostic in found:
            self.assertIn(diagnostic, in_check)


# --- 単一ワークスペース -----------------------------------------------------------------------

class SingleWorkspaceTests(_Base):
    """単一ワークスペース。REQ-001（規範文2件）を、TECH-001が`refines`して`tests`で`covers`する。テストの実体は`tests/a.py`と`tests/b.py`。"""

    def build(self, tests, *, extra=None, links=()):
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, TECH_PATH, _tech("TECH-001", refines=["REQ-001"], tests=tests))
        _write(self.root, "tests/a.py")
        _write(self.root, "tests/b.py")
        for rel, content in (extra or {}).items():
            _write(self.root, rel, content)
        for name, target in links:
            (self.root / name).symlink_to(target)
        self.commit()

    def assertInvalidPath(self, result, code, *, index=1):
        target = self.targets(result)["REQ-001"]
        self.assertSkippedTarget(target)
        self.assertEqual(self.codes(target), [("SPEC-PATH-INVALID-001", TECH_PATH, f"tests[{index}].path")])
        diagnostic = target["diagnostics"][0]
        self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"]), ("error", "failed"))
        self.assertEqual(diagnostic["summary"], "テストのパスが存在しません")
        self.assertEqual(diagnostic["source"], {"kind": "file", "workspaceId": "root", "path": TECH_PATH, "key": f"tests[{index}].path"})
        self.assertEqual((result["status"], code), ("failed", 1))
        # テストを起動しない。独立したテスト割当てもないので、コマンドは0件。
        self.assertEqual(result["commands"], [])
        self.assertSameAsCheck(target, "--full")

    def test_defect_missing_test_path_fails_the_target_without_running_tests(self):
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/nope.py", ["REQ-001:AC-02"], "default")])
        result, code = self.verify("REQ-001")
        self.assertInvalidPath(result, code)

    def test_defect_directory_test_path_fails_the_target(self):
        self.build(
            [("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/suite", ["REQ-001:AC-02"], "default")],
            extra={"tests/suite/c.py": "x\n"},
        )
        result, code = self.verify("REQ-001")
        self.assertInvalidPath(result, code)

    def test_defect_test_path_through_a_linked_parent_to_outside_fails_the_target(self):
        """上位のディレクトリのシンボリックリンクがワークスペースの外へ解決するパスは、存在しないパスと同じに扱う。"""
        self.build(
            [("tests/a.py", ["REQ-001:AC-01"], "default"), ("ext/test_x.py", ["REQ-001:AC-02"], "default")],
            links=[("ext", self.outside)],
        )
        result, code = self.verify("REQ-001")
        self.assertInvalidPath(result, code)

    def test_defect_transitive_refines_covers_fails_the_target(self):
        """TECH-002は`TECH-001`だけを`refines`する。TECH-001が`refines`するREQ-001の規範文は、TECH-002の`covers`に指定できない（推移的）。"""
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default")])
        _write(self.root, ".spec/technical/TECH-002.md", _tech("TECH-002", refines=["TECH-001"], tests=[("tests/b.py", ["REQ-001:AC-02"], "default")]))
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "transitive")
        result, code = self.verify("REQ-001")
        target = self.targets(result)["REQ-001"]
        self.assertSkippedTarget(target)
        path = ".spec/technical/TECH-002.md"
        self.assertEqual(self.codes(target), [("SPEC-TEST-COVERAGE-001", path, "tests[0].covers")])
        diagnostic = target["diagnostics"][0]
        self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"], diagnostic["evidence"]), ("error", "failed", "REQ-001:AC-02"))
        self.assertEqual(diagnostic["source"], {"kind": "file", "workspaceId": "root", "path": path, "key": "tests[0].covers"})
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))
        self.assertSameAsCheck(target, "--full")

    def test_defect_document_unit_tests_of_a_techless_statement_document_are_checked(self):
        """規範文のないTECHを起点にすると、文書単位の`tests`を検査する。"""
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/nope.py", ["REQ-001:AC-02"], "default")])
        result, code = self.verify("TECH-001")
        target = self.targets(result)["TECH-001"]
        self.assertSkippedTarget(target)
        self.assertEqual(self.codes(target), [("SPEC-PATH-INVALID-001", TECH_PATH, "tests[1].path")])
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))

    def test_defect_independent_target_continues(self):
        """違反した検証対象が止まっても、独立した検証対象は続けて実行する。違反したテスト対応のテストのパスは起動しない。"""
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/nope.py", ["REQ-001:AC-02"], "default")])
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", statements=1))
        _write(self.root, ".spec/technical/TECH-003.md", _tech("TECH-003", refines=["REQ-002"], tests=[("tests/b.py", ["REQ-002:AC-01"], "default")]))
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "second")
        result, code = self.verify("REQ-001", "REQ-002")
        targets = self.targets(result)
        self.assertSkippedTarget(targets["REQ-001"])
        self.assertEqual((targets["REQ-002"]["status"], targets["REQ-002"]["bindingRefs"], targets["REQ-002"]["diagnostics"]), ("passed", ["root::default"], []))
        self.assertEqual((result["status"], code), ("failed", 1))
        (command,) = result["commands"]
        self.assertEqual((command["status"], command["tests"], command["covers"]), ("passed", ["tests/b.py"], ["REQ-002:AC-01"]))

    def test_control_unused_invalid_test_correspondence_does_not_stop(self):
        """検証対象が使わないテスト対応（別のREQを`refines`するTECHの不在のパスと不正な`covers`）は検査しない。"""
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/b.py", ["REQ-001:AC-02"], "default")])
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", statements=1))
        _write(
            self.root, ".spec/technical/TECH-003.md",
            _tech("TECH-003", refines=["REQ-002"], tests=[("tests/nope.py", ["REQ-002:AC-01"], "default"), ("tests/a.py", ["REQ-001:AC-01"], "default")]),
        )
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "unused")
        self.assertTrue(self.check_diagnostics("--full"))  # `check`は検出する（検査の責務は`check`にある）。
        result, code = self.verify("REQ-001")
        target = self.targets(result)["REQ-001"]
        self.assertEqual((target["status"], target["diagnostics"], target["bindingRefs"]), ("passed", [], ["root::default"]))
        self.assertEqual((result["status"], code), ("passed", 0))
        (command,) = result["commands"]
        self.assertEqual(command["tests"], ["tests/a.py", "tests/b.py"])

    def test_control_missing_implements_is_not_checked_by_verify(self):
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/b.py", ["REQ-001:AC-02"], "default")])
        _write(
            self.root, TECH_PATH,
            _tech("TECH-001", refines=["REQ-001"], implements=["src/gone.py"], tests=[("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/b.py", ["REQ-001:AC-02"], "default")]),
        )
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "implements")
        self.assertTrue(self.check_diagnostics("--full"))
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(self.targets(result)["REQ-001"]["diagnostics"], [])

    def test_control_valid_test_correspondences_run(self):
        """陽性対照: 不正がなければ、検査を加えても今までどおり起動して通る。"""
        self.build([("tests/a.py", ["REQ-001:AC-01"], "default"), ("tests/b.py", ["REQ-001:AC-02"], "default")])
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(self.check_diagnostics("--full"), [])

    def test_control_test_path_through_a_linked_parent_inside_passes(self):
        self.build(
            [("ext/a.py", ["REQ-001:AC-01"], "default"), ("tests/b.py", ["REQ-001:AC-02"], "default")],
            links=[("ext", "tests")],
        )
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))


# --- 複合ワークスペース -----------------------------------------------------------------------

class MultiWorkspaceTests(_Base):
    """複合ワークスペース。ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）。"""

    @staticmethod
    def root_config() -> str:
        return CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n" + VERIFY

    def build(self, files: dict[str, str], links=()):
        _write(self.root, ".spec/bitz.yaml", self.root_config())
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + VERIFY)
        _write(self.root, "services/api/.spec/bitz.yaml", CONFIG + "workspace:\n  id: api\n" + VERIFY)
        for rel, content in files.items():
            _write(self.root, rel, content)
        for name, target in links:
            (self.root / name).symlink_to(target)
        self.commit()

    def test_defect_member_test_path_resolving_into_another_workspace_is_an_ownership_violation(self):
        """`web`のテストのパスの上位のディレクトリがルートの領域へ解決する。"""
        self.build(
            {
                "apps/web/.spec/requirements/REQ-101.md": _req("REQ-101", statements=1, tests=[("ext/test_x.py", ["REQ-101:AC-01"], "default")]),
                "tests/test_x.py": "x\n",
            },
            links=[("apps/web/ext", "../../tests")],
        )
        result, code = self.verify("web::REQ-101")
        target = self.targets(result)["web::REQ-101"]
        self.assertSkippedTarget(target)
        path = ".spec/requirements/REQ-101.md"
        self.assertEqual(self.codes(target), [("SPEC-MULTI-OWNERSHIP-001", path, "tests[0].path")])
        diagnostic = target["diagnostics"][0]
        self.assertEqual((diagnostic["severity"], diagnostic["resultStatus"]), ("error", "failed"))
        self.assertEqual(diagnostic["summary"], "パスext/test_x.pyの解決先がワークスペースwebの所有領域の外です")
        self.assertEqual(diagnostic["source"], {"kind": "file", "workspaceId": "web", "path": path, "key": "tests[0].path"})
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))
        self.assertSameAsCheck(target, "--all-workspaces")

    def test_defect_root_test_path_declared_inside_a_member_is_an_ownership_violation(self):
        """ルートワークスペースはメンバーの配下を所有しない。"""
        self.build(
            {
                ".spec/requirements/REQ-001.md": _req("REQ-001", statements=1, tests=[("apps/web/t.py", ["REQ-001:AC-01"], "default")]),
                "apps/web/t.py": "x\n",
            }
        )
        result, code = self.verify("REQ-001")
        target = self.targets(result)["platform::REQ-001"]
        self.assertSkippedTarget(target)
        self.assertEqual(self.codes(target), [("SPEC-MULTI-OWNERSHIP-001", ".spec/requirements/REQ-001.md", "tests[0].path")])
        self.assertEqual(target["diagnostics"][0]["summary"], "パスapps/web/t.pyの解決先がワークスペースplatformの所有領域の外です")
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))
        self.assertSameAsCheck(target, "--all-workspaces")

    def test_defect_member_missing_test_path_fails_the_target(self):
        self.build(
            {"apps/web/.spec/requirements/REQ-101.md": _req("REQ-101", statements=1, tests=[("tests/nope.py", ["REQ-101:AC-01"], "default")])}
        )
        result, code = self.verify("web::REQ-101")
        target = self.targets(result)["web::REQ-101"]
        self.assertSkippedTarget(target)
        path = ".spec/requirements/REQ-101.md"
        self.assertEqual(self.codes(target), [("SPEC-PATH-INVALID-001", path, "tests[0].path")])
        self.assertEqual(target["diagnostics"][0]["source"], {"kind": "file", "workspaceId": "web", "path": path, "key": "tests[0].path"})
        self.assertEqual(target["diagnostics"][0]["summary"], "テストのパスが存在しません")
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))
        self.assertSameAsCheck(target, "--all-workspaces")

    def cross_files(self, *, web_tech_refines: str) -> dict[str, str]:
        """ルートのREQ-001（自身の正しいテスト対応を持つ）と、`web`の具体化（`web::TECH-005`が`platform::REQ-001`を`refines`し、
        TECH-010が`web_tech_refines`を`refines`して`platform::REQ-001:AC-01`を`covers`する）。"""
        return {
            ".spec/requirements/REQ-001.md": _req("REQ-001", statements=1, tests=[("tests/root.py", ["REQ-001:AC-01"], "default")]),
            "tests/root.py": "x\n",
            "apps/web/.spec/technical/TECH-005.md": _tech("TECH-005", refines=["platform::REQ-001"]),
            "apps/web/.spec/technical/TECH-010.md": _tech(
                "TECH-010", refines=[web_tech_refines], tests=[("tests/web.py", ["platform::REQ-001:AC-01"], "default")]
            ),
            "apps/web/tests/web.py": "x\n",
        }

    def test_defect_cross_workspace_covers_through_a_transitive_refines_fails_the_target(self):
        """`web::TECH-010`は`web::TECH-005`だけを`refines`する。ルートの規範文は直接`refines`していないので、`covers`に指定できない。"""
        self.build(self.cross_files(web_tech_refines="TECH-005"))
        result, code = self.verify("REQ-001")
        target = self.targets(result)["platform::REQ-001"]
        self.assertSkippedTarget(target)
        path = ".spec/technical/TECH-010.md"
        self.assertEqual(self.codes(target), [("SPEC-TEST-COVERAGE-001", path, "tests[0].covers")])
        diagnostic = target["diagnostics"][0]
        self.assertEqual(
            (diagnostic["source"], diagnostic["evidence"]),
            ({"kind": "file", "workspaceId": "web", "path": path, "key": "tests[0].covers"}, "platform::REQ-001:AC-01"),
        )
        self.assertEqual((result["status"], code, result["commands"]), ("failed", 1, []))
        self.assertSameAsCheck(target, "--all-workspaces")

    def test_control_cross_workspace_covers_with_a_direct_refines_runs(self):
        """対照: 宣言する文書が規範文を直接`refines`するなら、横断の`covers`は指定できる。"""
        self.build(self.cross_files(web_tech_refines="platform::REQ-001:AC-01"))
        result, code = self.verify("REQ-001")
        target = self.targets(result)["platform::REQ-001"]
        self.assertEqual((target["status"], target["diagnostics"]), ("passed", []))
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(self.check_diagnostics("--all-workspaces"), [])

    def all_workspaces_files(self) -> dict[str, str]:
        """`web`のREQ-101は不在のテストのパス、`api`のREQ-201は正しい。ルートは文書を持たない。"""
        return {
            "apps/web/.spec/requirements/REQ-101.md": _req("REQ-101", statements=1, tests=[("tests/nope.py", ["REQ-101:AC-01"], "default")]),
            "services/api/.spec/requirements/REQ-201.md": _req("REQ-201", statements=1, tests=[("tests/ok.py", ["REQ-201:AC-01"], "default")]),
            "services/api/tests/ok.py": "x\n",
        }

    def test_defect_all_workspaces_skips_the_violating_target_and_runs_the_independent_one(self):
        self.build(self.all_workspaces_files())
        result, code = self.verify("--all-workspaces")
        targets = self.targets(result)
        self.assertSkippedTarget(targets["web::REQ-101"])
        self.assertEqual(self.codes(targets["web::REQ-101"]), [("SPEC-PATH-INVALID-001", ".spec/requirements/REQ-101.md", "tests[0].path")])
        self.assertEqual((targets["api::REQ-201"]["status"], targets["api::REQ-201"]["bindingRefs"]), ("passed", ["api::default"]))
        commands = {c["bindingId"]: c for workspace in result["workspaces"] for c in workspace["commands"]}
        self.assertEqual(sorted(commands), ["api::default"])
        self.assertEqual(commands["api::default"]["tests"], ["tests/ok.py"])
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertSameAsCheck(targets["web::REQ-101"], "--all-workspaces")

    def test_control_unused_invalid_member_document_does_not_stop(self):
        """対照: `verify REQ-001`が使わない`web`のテスト対応（不在のパス）は検査しない。"""
        files = self.cross_files(web_tech_refines="platform::REQ-001:AC-01")
        files["apps/web/.spec/requirements/REQ-102.md"] = _req("REQ-102", statements=1, tests=[("tests/nope.py", ["REQ-102:AC-01"], "default")])
        self.build(files)
        self.assertTrue(self.check_diagnostics("--all-workspaces"))
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0))

    def test_defect_diagnostic_output_does_not_depend_on_the_hash_seed(self):
        self.build(self.all_workspaces_files())
        outputs = {}
        for seed in ("0", "1", "12345"):
            proc = subprocess.run(
                [sys.executable, "-m", "bitz.cli", "verify", "--all-workspaces", "--format", "json"], cwd=self.root,
                env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)}, capture_output=True, text=True,
            )
            outputs[seed] = json.dumps([proc.returncode, _without_durations(json.loads(proc.stdout))], ensure_ascii=False)
        self.assertEqual(len(set(outputs.values())), 1)
        self.assertIn("SPEC-PATH-INVALID-001", next(iter(outputs.values())))


if __name__ == "__main__":
    unittest.main()
