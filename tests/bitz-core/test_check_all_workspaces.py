"""`check --all-workspaces`のmember処理（Step 5B）の単体試験。

`02_SPECモデル/05_複合workspace仕様.md` §6・§8・§9、`03_操作仕様/02_check.md`を対象にする。
`tests/bitz-core/test_multiws.py`は全体事前検査（Step 5A）だけを対象にするため、本fileは事前検査を
通過した後のmember単位check（横断relation解決、所有境界、集約status、workspace identity）を扱う。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz.cliargs import ParsedArgs

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {wid}\n'


def _git_env() -> dict[str, str]:
    return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root, *args) -> None:
    subprocess.run(["git", *args], cwd=root, env=_git_env(), check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, title: str = "REQ", status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n\n"
        "## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, title: str = "TECH", status: str = "approved", *, relations: str = "", extra: str = "") -> str:
    return f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n{relations}{extra}---\n\n# {doc_id} {title}\n\n## Context\n\n本文。\n"


def _run_all(root, *, base="HEAD", report=False) -> tuple[dict, int]:
    flags = {"--all-workspaces"}
    if report:
        flags.add("--report")
    parsed = ParsedArgs(operation="check", positionals=[], flags=flags, single={"--base": base}, repeat={})
    return check_mod.run(parsed, str(root), dict(os.environ))


def _run_target(root, target, *, base="HEAD") -> tuple[dict, int]:
    parsed = ParsedArgs(operation="check", positionals=[target], flags=set(), single={"--base": base}, repeat={})
    return check_mod.run(parsed, str(root), dict(os.environ))


class AllWorkspacesAggregationTests(unittest.TestCase):
    def _basic_repo(self, root: Path) -> None:
        _init_repo(root)
        _write(
            root, ".spec/bitz.yaml",
            ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            "    - id: api\n      path: services/api\n",
        )
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
        _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_root_first_then_member_id_order_and_passed_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._basic_repo(root)

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["scope"], "all-workspaces")
            self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
            ids = [w["id"] for w in result["workspaces"]]
            # root先頭、以降workspace ID辞書順（複合workspace仕様 §8）。
            self.assertEqual(ids, ["platform", "api", "web"])
            for w in result["workspaces"]:
                self.assertEqual(w["status"], "passed")
                self.assertEqual(w["diagnostics"], [])

    def test_one_member_failure_does_not_stop_others(self):
        # 複合workspace仕様 §8「事前検査通過後はworkspace全体ではなく…」: 1memberの非成功でも
        # 後続memberのcheckedDocumentCount等は正常に計算される。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._basic_repo(root)
            # webのTECH文書のfile名IDをわざと不一致にする（hard fail）。
            _write(root, "apps/web/.spec/technical/TECH-999.md", _tech("TECH-010"))

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            by_id = {w["id"]: w for w in result["workspaces"]}
            self.assertEqual(by_id["web"]["status"], "failed")
            self.assertEqual(by_id["api"]["status"], "passed")
            self.assertEqual(by_id["platform"]["status"], "passed")
            codes = [d["code"] for d in by_id["web"]["diagnostics"]]
            self.assertIn("SPEC-FILE-NAME-001", codes)

    def test_report_flag_writes_single_report_at_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._basic_repo(root)

            result, exit_code = _run_all(root, report=True)
            self.assertEqual(exit_code, 0)
            reports_dir = root / ".spec" / "reports"
            self.assertTrue(reports_dir.is_dir())
            written = list(reports_dir.glob("*-check.json"))
            self.assertEqual(len(written), 1)
            # memberのworkspace内には作らない。
            self.assertFalse((root / "apps" / "web" / ".spec" / "reports").exists())

    def test_default_all_workspaces_does_not_write_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._basic_repo(root)
            _run_all(root, report=False)
            self.assertFalse((root / ".spec" / "reports").exists())


class CrossWorkspaceRelationTests(unittest.TestCase):
    def test_cross_workspace_refines_resolves_and_unqualified_elsewhere_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
                "    - id: api\n      path: services/api\n",
            )
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(
                root, "apps/web/.spec/technical/TECH-010.md",
                _tech("TECH-010", relations="relations:\n  refines: [platform::REQ-001:AC-01]\n"),
            )
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _write(
                root, "services/api/.spec/technical/TECH-020.md",
                # 非修飾"REQ-001"はapi自身には無く、platformにだけある。
                _tech("TECH-020", relations="relations:\n  refines: [REQ-001]\n"),
            )
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 1)
            by_id = {w["id"]: w for w in result["workspaces"]}
            self.assertEqual(by_id["web"]["status"], "passed")
            self.assertEqual(by_id["api"]["status"], "failed")
            codes = [d["code"] for d in by_id["api"]["diagnostics"]]
            self.assertIn("SPEC-MULTI-REF-001", codes)

    def test_qualified_target_selects_owning_workspace(self):
        # 複合workspace仕様 §3「修飾IDを起点にする場合は、その所有workspaceを選択する」。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
            )
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            result, exit_code = _run_target(root, "web::TECH-010")
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["scope"], "selected")
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})


class SingleToMultiIdentityMappingTests(unittest.TestCase):
    """複合workspace仕様 §4.1後段（単一→複合workspace化するGit比較のID写像）の単体試験。"""

    _BASE_SINGLE_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'

    def _current_multi_root_yaml(self, root_id: str = "platform") -> str:
        return (
            f'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {root_id}\n'
            "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
        )

    def test_approved_req_meaning_change_is_protected_after_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", self._BASE_SINGLE_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", title="旧title"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            _write(root, ".spec/bitz.yaml", self._current_multi_root_yaml())
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", title="新title"))

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 1)
            by_id = {w["id"]: w for w in result["workspaces"]}
            codes = [d["code"] for d in by_id["platform"]["diagnostics"]]
            self.assertIn("SPEC-SAFETY-APPROVED-001", codes)

    def test_root_document_deletion_is_detected_after_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", self._BASE_SINGLE_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            _write(root, ".spec/bitz.yaml", self._current_multi_root_yaml())
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            os.remove(root / ".spec" / "requirements" / "REQ-001.md")

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 1)
            by_id = {w["id"]: w for w in result["workspaces"]}
            codes = [d["code"] for d in by_id["platform"]["diagnostics"]]
            self.assertIn("SPEC-STATE-TRANSITION-001", codes)

    def test_mapping_not_applied_when_base_has_explicit_id(self):
        # baseに明示IDがあれば写像しない。base id "solo" はcurrentのroot id "platform"と一致しない
        # ため、rootは「新規workspace」として扱われ、削除検出は働かない。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: solo\n',
            )
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            _write(root, ".spec/bitz.yaml", self._current_multi_root_yaml())
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            os.remove(root / ".spec" / "requirements" / "REQ-001.md")

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 0)
            by_id = {w["id"]: w for w in result["workspaces"]}
            self.assertEqual(by_id["platform"]["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
