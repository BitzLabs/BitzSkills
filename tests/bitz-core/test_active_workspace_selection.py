"""複合ワークスペース内の単独操作の作業ワークスペースの決定（`bitz.activews`）の単体試験。

`02_仕様文書モデル/05_複合ワークスペース仕様.md` §3の5・§4・§6・§7、`03_操作仕様/03_verify.md` §2、`03_操作仕様/04_doctor.md` §3、
`00_共通契約/01_結果・診断・終了コード.md` §2（複合ワークスペース内の単独操作の`workspace`）を対象にする。
`verify`と`doctor`が、`check`・`context`と同じ規則（修飾IDの起点の所有者 → `--workspace` → 最寄りの設定）で
作業ワークスペースを決めることを確かめる。具体的には次のとおり。

- `verify`は修飾IDのない位置引数、`--workspace`、引数なし（既定の対象）でも複合ワークスペースとして動く。
  既定の対象は作業ワークスペースの文書だけで、修飾IDで返す。ルートで実行した引数なしの`verify`は、メンバーの具体化文書が覆うので`blocked`にならない。
- `doctor --workspace <ID>`はルートまたはメンバーのIDで作業ワークスペースを置き換え、結果の`workspace.path`は
  リポジトリのルートからの相対パスになる。未知のIDは引数不正（終了コード4）。
- `check`・`context`の振る舞いは変わらない。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.errors import CliArgError

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT_YAML = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"
WEB_YAML = CONFIG + 'workspace:\n  id: web\nverify:\n  commands:\n    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
API_YAML = CONFIG + "workspace:\n  id: api\n"

REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
WEB_TECH = (
    "---\nid: TECH-010\ntitle: Web側\nstatus: approved\nrelations:\n  refines: [platform::REQ-001:AC-01]\n"
    "tests:\n  - path: tests/t.py\n    covers: [platform::REQ-001:AC-01]\n    command: frontend\n---\n\n"
    "# TECH-010 Web側\n\n## Context\n\n本文。\n"
)


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML)
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "services/api/.spec/bitz.yaml", API_YAML)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "apps/web/.spec/technical/TECH-010.md", WEB_TECH)
        _write(self.root, "apps/web/tests/t.py", "")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")
        self.web = self.root / "apps" / "web"

    def verify(self, cwd: Path, *argv: str):
        return verify_mod.run(parse_argv(["verify", *argv, "--format", "json"]), str(cwd), dict(os.environ))

    def doctor(self, cwd: Path, *argv: str):
        return doctor_mod.run(parse_argv(["doctor", *argv, "--format", "json"]), str(cwd), dict(os.environ))


class VerifyWorkspaceSelectionTests(_Base):
    def assert_web_target_passes(self, result, exit_code, *, scope):
        self.assertEqual(result["status"], "passed", result["targetResults"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scope"], scope)
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual([t["target"] for t in result["targetResults"]], ["web::TECH-010"])
        self.assertEqual(result["targetResults"][0]["diagnostics"], [])
        self.assertEqual(result["targetResults"][0]["bindingRefs"], ["web::frontend"])

    def test_unqualified_target_inside_member_resolves_in_the_composite_catalog(self):
        result, code = self.verify(self.web, "TECH-010")
        self.assert_web_target_passes(result, code, scope="selected")

    def test_workspace_option_from_root_selects_member(self):
        result, code = self.verify(self.root, "--workspace", "web")
        self.assert_web_target_passes(result, code, scope="all")

    def test_workspace_option_with_unqualified_target_from_root(self):
        result, code = self.verify(self.root, "TECH-010", "--workspace", "web")
        self.assert_web_target_passes(result, code, scope="selected")

    def test_default_targets_inside_member_are_the_member_documents_only(self):
        result, code = self.verify(self.web)
        self.assert_web_target_passes(result, code, scope="all")

    def test_workspace_option_from_member_selects_root(self):
        result, code = self.verify(self.web, "--workspace", "platform")
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        self.assertEqual([t["target"] for t in result["targetResults"]], ["platform::REQ-001"])
        self.assertEqual(result["status"], "passed", result["targetResults"])
        self.assertEqual(code, 0)

    def test_default_targets_at_root_see_member_refinement_and_are_not_blocked(self):
        result, code = self.verify(self.root)
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        self.assertEqual([t["target"] for t in result["targetResults"]], ["platform::REQ-001"])
        self.assertEqual(result["status"], "passed", result["targetResults"])
        self.assertEqual(code, 0)
        self.assertEqual(result["targetResults"][0]["bindingRefs"], ["web::frontend"])

    def test_unknown_workspace_is_argument_error(self):
        with self.assertRaises(CliArgError):
            self.verify(self.root, "--workspace", "nope")

    def test_qualified_owner_and_workspace_option_disagreement_is_argument_error(self):
        with self.assertRaises(CliArgError):
            self.verify(self.root, "web::TECH-010", "--workspace", "api")

    def test_qualified_target_still_works(self):
        result, code = self.verify(self.root, "web::TECH-010")
        self.assert_web_target_passes(result, code, scope="selected")


class DoctorWorkspaceSelectionTests(_Base):
    def test_workspace_option_from_member_selects_root(self):
        result, code = self.doctor(self.web, "--workspace", "platform")
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        self.assertEqual((result["status"], code), ("passed", 0))

    def test_workspace_option_from_root_selects_member(self):
        result, code = self.doctor(self.root, "--workspace", "web")
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual((result["status"], code), ("passed", 0))
        # 作業ワークスペースの設定を診断している（メンバー`web`だけがコマンド`frontend`を持つ）。
        self.assertIn(("command", "passed"), [(c["name"], c["status"]) for c in result["checks"]])

    def test_workspace_option_selects_other_member(self):
        result, _ = self.doctor(self.web, "--workspace", "api")
        self.assertEqual(result["workspace"], {"id": "api", "path": "services/api"})

    def test_workspace_path_inside_member_is_the_member_path(self):
        result, _ = self.doctor(self.web)
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})

    def test_workspace_path_at_root_is_dot(self):
        result, _ = self.doctor(self.root)
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})

    def test_unknown_workspace_is_argument_error(self):
        with self.assertRaises(CliArgError):
            self.doctor(self.root, "--workspace", "nope")
        with self.assertRaises(CliArgError):
            self.doctor(self.web, "--workspace", "nope")

    def test_single_workspace_path_is_dot_and_unknown_id_is_argument_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp)
            _git(single, "init", "-q", "--initial-branch=main")
            _write(single, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: solo\n")
            result, _ = doctor_mod.run(parse_argv(["doctor", "--format", "json"]), str(single), dict(os.environ))
            self.assertEqual(result["workspace"], {"id": "solo", "path": "."})
            with self.assertRaises(CliArgError):
                doctor_mod.run(parse_argv(["doctor", "--workspace", "web", "--format", "json"]), str(single), dict(os.environ))


class DoctorCatalogCheckTests(_Base):
    """複合ワークスペース内の単独の`doctor`は、全体事前検査が成功していれば検査項目`catalog`を置く（`doctor.md` §3検査6）。"""

    @staticmethod
    def names(result):
        return [c["name"] for c in result["checks"]]

    def assert_catalog_between_config_and_schema(self, result):
        names = self.names(result)
        self.assertEqual(names.count("catalog"), 1, names)
        self.assertEqual(names.index("catalog"), names.index("config") + 1, names)
        self.assertEqual(names.index("schema"), names.index("catalog") + 1, names)
        self.assertIn({"name": "catalog", "status": "passed"}, result["checks"])

    def test_inside_member(self):
        result, _ = self.doctor(self.web)
        self.assert_catalog_between_config_and_schema(result)

    def test_at_root(self):
        result, _ = self.doctor(self.root)
        self.assert_catalog_between_config_and_schema(result)

    def test_with_workspace_option(self):
        for cwd, wid in ((self.root, "web"), (self.web, "platform"), (self.web, "api")):
            with self.subTest(cwd=str(cwd), workspace=wid):
                result, _ = self.doctor(cwd, "--workspace", wid)
                self.assert_catalog_between_config_and_schema(result)

    def test_single_workspace_has_no_catalog_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp)
            _git(single, "init", "-q", "--initial-branch=main")
            _write(single, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: solo\n")
            result, _ = doctor_mod.run(parse_argv(["doctor", "--format", "json"]), str(single), dict(os.environ))
            self.assertNotIn("catalog", self.names(result))

    def test_all_workspaces_top_level_catalog_is_unchanged(self):
        result, _ = doctor_mod.run(parse_argv(["doctor", "--all-workspaces", "--format", "json"]), str(self.root), dict(os.environ))
        self.assertEqual([c["name"] for c in result["checks"]], ["core", "git", "catalog"])
        for workspace in result["workspaces"]:
            self.assertNotIn("catalog", [c["name"] for c in workspace["checks"]])


class CheckAndContextUnchangedTests(_Base):
    def test_check_member_default_and_workspace_option(self):
        parsed = parse_argv(["check", "--full", "--format", "json"])
        result, code = check_mod.run(parsed, str(self.web), dict(os.environ))
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        parsed = parse_argv(["check", "--full", "--workspace", "web", "--format", "json"])
        result, _ = check_mod.run(parsed, str(self.root), dict(os.environ))
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        with self.assertRaises(CliArgError):
            check_mod.run(parse_argv(["check", "--workspace", "nope", "--format", "json"]), str(self.root), dict(os.environ))

    def test_context_member_and_workspace_option(self):
        parsed = parse_argv(["context", "TECH-010", "--workspace", "web", "--format", "json"])
        result, code = context_mod.run(parsed, str(self.root), dict(os.environ))
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual(result["roots"], ["web::TECH-010"])
        with self.assertRaises(CliArgError):
            context_mod.run(parse_argv(["context", "TECH-010", "--workspace", "nope", "--format", "json"]), str(self.root), dict(os.environ))


if __name__ == "__main__":
    unittest.main()
