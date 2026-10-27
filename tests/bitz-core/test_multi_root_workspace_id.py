"""複合ワークスペースのルートワークスペースとメンバーが`workspace.id`を省略したときの単体試験（確認事項 C42）。

欠陥: 複合ワークスペースのルートの設定が`workspace.id`を省略しても、全体事前検査が既定値`root`をルートのIDとして使い、
`multiWorkspace.id`、`workspace.id`、修飾ID、診断の発生元に`root`を返して成功していた。メンバーの設定が`workspace.id`を省略し、
カタログの`id`が`root`のときも、既定値`root`がカタログのIDと一致するとみなして通っていた。

規範:
- 複合ワークスペース仕様 §2: ルートワークスペースと全メンバーで`workspace.id`を必須とし、カタログの`id`とメンバー設定の`workspace.id`は一致させる。
  §4.1: 既定値`root`から明示のIDへの写像は、`multiWorkspace`のない基準版との比較だけに使う。
- 診断レジストリ`MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、900）: ルートの条件の不正。`MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910）: カタログのIDと不一致。
- 結果・診断・終了コード §2: 有効なルートワークスペースのIDを構成できない全体結果は`multiWorkspace`を`{"id": null, "path": "."}`、
  `workspaces`を空配列にする。単独結果の`workspace.id`は、ルートでは明示した有効なIDを持つときだけそのIDとする。
  §5: ルートIDの不正で同一性を構成できない診断の`source.workspaceId`は`null`とする。

この試験の対象:
1. ルートがIDを省略した複合ワークスペースは、全体操作と単独操作のすべてで`SPEC-MULTI-CONFIG-001`の1件だけで止まる（ほかのメンバーの不備より優先）。
2. 全体結果の同一性は`null`で、メンバーの単独結果はメンバーの明示したIDを返す。`doctor`の検査項目`catalog`は`failed`。
3. Gitの境界を確定できないときは`SPEC-MULTI-GIT-001`だけを返し、ルートのIDに既定値`root`を使わない。スキーマまたはEARS-AIのメジャーバージョンの
   非対応で止まるときも、全体結果の同一性と診断の`source.workspaceId`は`null`（結果・診断・終了コード §2・§5）。
   `multiWorkspace:`の値が空でも宣言とみなす（§2.1。キーの有無で判定する）。
4. メンバーがIDを省略すると、カタログのIDが`root`でも`SPEC-MULTI-MEMBER-001`の不一致になる。
5. 対照: ルートがIDを明示すれば成功する（明示の`root`も含む）。`multiWorkspace`を宣言しない単一ワークスペースは既定値`root`のまま成功する。
6. 除外を信用できる条件（複合ワークスペース仕様 §2.1）は`multiWorkspace`の設定不適合だけを見るため、ルートのIDの省略では変わらない。
7. 結果は`result.schema.json`に適合する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
MEMBERS = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
ROOT_WITHOUT_ID = CONFIG + MEMBERS
WEB_YAML = CONFIG + "workspace:\n  id: web\n"

REQ_ROOT = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
REQ_WEB = REQ_ROOT.replace("REQ-001", "REQ-050")

ROOT_ID_REQUIRED = "ルートワークスペースの設定キーworkspace.idがありません"
MEMBER_ID_MISMATCH = "メンバーの設定キーworkspace.idがカタログのIDと一致しません"
ROOT_ID_SOURCE = {"kind": "file", "workspaceId": None, "path": ".spec/bitz.yaml", "key": "workspace.id"}

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _validate_against_schema(results: list[dict]) -> None:
    """結果が公開スキーマに適合することを確かめる。Coreの環境に`jsonschema`がないため、`uv`で一時的に用意して別プロセスで検証する。"""

    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "for index, result in enumerate(json.load(sys.stdin)):\n"
        "    errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))\n"
        "    if errors:\n"
        "        print(index, errors[0].message, list(errors[0].path))\n"
        "        sys.exit(1)\n"
    )
    proc = subprocess.run(
        [uv, "run", "--no-project", "--with", "jsonschema==4.23.0", "python", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"スキーマに適合しません: {proc.stdout}{proc.stderr}")


class _Base(unittest.TestCase):
    """既定の環境: ルートがIDを省略し、メンバー`web`がIDを明示した複合ワークスペースをGitのリポジトリに作る。"""

    use_git = True
    root_yaml = ROOT_WITHOUT_ID
    web_yaml = WEB_YAML

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = dict(os.environ)
        if self.use_git:
            _git(self.root, "init", "-q", "--initial-branch=main")
            _git(self.root, "config", "user.email", "t@t")
            _git(self.root, "config", "user.name", "t")
        _write(self.root, ".spec/bitz.yaml", self.root_yaml)
        _write(self.root, "apps/web/.spec/bitz.yaml", self.web_yaml)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ_ROOT)
        _write(self.root, "apps/web/.spec/requirements/REQ-050.md", REQ_WEB)
        if self.use_git:
            _git(self.root, "add", ".")
            _git(self.root, "commit", "-q", "-m", "base")
        self.web = self.root / "apps" / "web"
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def _run(self, module, name: str, cwd: Path, argv: tuple[str, ...]):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), self.env)
        self.results.append(result)
        return result, code

    def check(self, cwd: Path, *argv: str):
        return self._run(check_mod, "check", cwd, argv)

    def context(self, cwd: Path, *argv: str):
        return self._run(context_mod, "context", cwd, argv)

    def verify(self, cwd: Path, *argv: str):
        return self._run(verify_mod, "verify", cwd, argv)

    def doctor(self, cwd: Path, *argv: str):
        return self._run(doctor_mod, "doctor", cwd, argv)

    def single_runs(self, cwd: Path, doc: str):
        return (
            ("check", self.check(cwd, "--full")),
            ("verify", self.verify(cwd)),
            ("context", self.context(cwd, doc)),
            ("doctor", self.doctor(cwd)),
        )

    def all_runs(self, cwd: Path):
        return (
            ("check", self.check(cwd, "--all-workspaces")),
            ("verify", self.verify(cwd, "--all-workspaces")),
            ("doctor", self.doctor(cwd, "--all-workspaces")),
        )

    def assert_root_id_stop(self, result, code, name):
        self.assertEqual((result["status"], code), ("failed", 1), (name, result["diagnostics"]))
        self.assertEqual(
            [(d["code"], d["summary"], d["source"]) for d in result["diagnostics"]],
            [("SPEC-MULTI-CONFIG-001", ROOT_ID_REQUIRED, ROOT_ID_SOURCE)],
            name,
        )
        if name == "doctor":
            self.assertIn({"name": "catalog", "status": "failed"}, result["checks"])


class RootWithoutWorkspaceIdTests(_Base):
    def test_all_workspace_operations_stop_with_null_identity(self):
        for name, (result, code) in self.all_runs(self.root):
            self.assert_root_id_stop(result, code, name)
            self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."}, name)
            self.assertEqual(result["workspaces"], [], name)

    def test_single_operations_of_the_root_stop_with_null_identity(self):
        for name, (result, code) in self.single_runs(self.root, "REQ-001"):
            self.assert_root_id_stop(result, code, name)
            self.assertEqual(result["workspace"], {"id": None, "path": "."}, name)

    def test_single_operations_of_a_member_keep_the_member_identity(self):
        for name, (result, code) in self.single_runs(self.web, "REQ-050"):
            self.assert_root_id_stop(result, code, name)
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"}, name)

    def test_root_id_stop_precedes_other_catalog_defects(self):
        # メンバーの設定の不在（ghost）と、IDの不一致（apps/web）があっても、ルートの条件で単独に止める。
        _write(
            self.root,
            ".spec/bitz.yaml",
            ROOT_WITHOUT_ID + "    - id: ghost\n      path: services/ghost\n",
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: webx\n")
        for name, (result, code) in self.all_runs(self.root):
            self.assert_root_id_stop(result, code, name)

    def test_qualified_ids_never_use_the_default_root(self):
        result, _ = self.check(self.root, "--all-workspaces")
        self.assertNotIn('"root', json.dumps(result, ensure_ascii=False))


class RootWithoutWorkspaceIdAndNoGitTests(_Base):
    use_git = False

    def test_git_boundary_unknown_keeps_null_identity(self):
        env = {**os.environ, "PATH": ""}
        self.env = env
        for name, (result, _code) in self.all_runs(self.root):
            self.assertIn("SPEC-MULTI-GIT-001", [d["code"] for d in result["diagnostics"]], name)
            self.assertNotIn("SPEC-MULTI-CONFIG-001", [d["code"] for d in result["diagnostics"]], name)
            self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."}, name)


class RootWithoutWorkspaceIdAndUnsupportedMajorTests(_Base):
    """版の非対応で止まっても、ルートが有効なIDを明示しなければ同一性は`null`（結果・診断・終了コード §2・§5）。"""

    CASES = (
        ('earsAi: "1.0"', 'earsAi: "2.0"', "earsAi"),
        ('schemaVersion: "1.0"', 'schemaVersion: "2.0"', "schemaVersion"),
    )

    def write_root(self, old: str, new: str, extra: str = "") -> None:
        _write(self.root, ".spec/bitz.yaml", ROOT_WITHOUT_ID.replace(old, new) + extra)

    def test_all_workspace_results_have_null_identity(self):
        for old, new, key in self.CASES:
            self.write_root(old, new)
            for name, (result, code) in self.all_runs(self.root):
                self.assertEqual((result["status"], code), ("blocked", 2), (key, name, result["diagnostics"]))
                self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."}, (key, name))
                self.assertEqual(result["workspaces"], [], (key, name))
                sources = [d["source"] for d in result["diagnostics"]]
                self.assertEqual([src.get("key") for src in sources], [key], (key, name))
                self.assertEqual([src["workspaceId"] for src in sources], [None], (key, name))

    def test_single_operation_of_the_root_has_null_source(self):
        self.write_root('earsAi: "1.0"', 'earsAi: "2.0"')
        result, code = self.check(self.root, "--full")
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": None, "path": "."})
        self.assertEqual([d["source"]["workspaceId"] for d in result["diagnostics"]], [None])

    def test_lexically_invalid_root_id_is_not_explicit(self):
        # スキーマのメジャーバージョンの非対応では`workspace`の字句をまだ検査しない（EARS-AIの非対応は字句の検査の後）。
        # 不正なIDの原文も既定値`root`も同一性に使わない（§2）。
        self.write_root('schemaVersion: "1.0"', 'schemaVersion: "2.0"', "workspace:\n  id: Bad_ID\n")
        result, _ = self.check(self.root, "--all-workspaces")
        self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
        self.assertEqual([d["source"]["workspaceId"] for d in result["diagnostics"]], [None])

    def test_explicit_root_id_is_kept(self):
        self.write_root('earsAi: "1.0"', 'earsAi: "2.0"', "workspace:\n  id: platform\n")
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
        self.assertEqual([d["source"]["workspaceId"] for d in result["diagnostics"]], ["platform"])


class RootWithoutWorkspaceIdAndUnsupportedMajorNoGitTests(_Base):
    use_git = False

    def test_doctor_without_git_has_null_identity(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_WITHOUT_ID.replace('earsAi: "1.0"', 'earsAi: "2.0"'))
        self.env = {**os.environ, "PATH": ""}
        result, _ = self.doctor(self.root, "--all-workspaces")
        self.assertEqual(
            sorted(d["code"] for d in result["diagnostics"]), ["SPEC-DOCTOR-EARS-001", "SPEC-MULTI-GIT-001"]
        )
        self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
        self.assertNotIn('"root"', json.dumps(result))


class NullMultiWorkspaceTests(_Base):
    """`multiWorkspace`の宣言はキーの有無で判定する（§2.1）。値が空でも、ルートのIDの省略は既定値`root`で通さない。"""

    root_yaml = CONFIG + "multiWorkspace:\n"

    def test_null_declaration_without_root_id_stops(self):
        for name, (result, code) in (("check", self.check(self.root, "--all-workspaces")),):
            self.assert_root_id_stop(result, code, name)
            self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
        result, code = self.check(self.root, "--full")
        self.assert_root_id_stop(result, code, "check")
        self.assertEqual(result["workspace"], {"id": None, "path": "."})


class MemberWithoutWorkspaceIdTests(_Base):
    root_yaml = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: root\n      path: apps/web\n"
    web_yaml = CONFIG

    def test_omitted_member_id_is_a_mismatch_even_when_the_catalog_id_is_root(self):
        for name, (result, code) in self.all_runs(self.root):
            self.assertEqual((result["status"], code), ("failed", 1), (name, result["diagnostics"]))
            self.assertEqual(
                [(d["code"], d["summary"]) for d in result["diagnostics"]],
                [("SPEC-MULTI-MEMBER-001", MEMBER_ID_MISMATCH)],
                name,
            )
            self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."}, name)

    def test_single_operation_of_the_member_has_null_identity(self):
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"})


class ExplicitIdControlTests(_Base):
    root_yaml = CONFIG + "workspace:\n  id: platform\n" + MEMBERS

    def commit(self):
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "change")

    def test_explicit_root_id_passes(self):
        # `verify`はコマンドがないと`blocked`なので、`check`と`doctor`で成功を確かめる。
        runs = self.all_runs(self.root)
        for name, (result, code) in (runs[0], runs[2]):
            self.assertEqual(code, 0, (name, result["diagnostics"]))
            self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."}, name)

    def test_explicit_root_id_named_root_passes(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: root\n" + MEMBERS)
        self.commit()
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual(code, 0, result["diagnostics"])
        self.assertEqual(result["multiWorkspace"], {"id": "root", "path": "."})

    def test_explicit_member_id_named_root_passes(self):
        _write(
            self.root,
            ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: root\n      path: apps/web\n",
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: root\n")
        self.commit()
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual(code, 0, result["diagnostics"])
        self.assertEqual([w["id"] for w in result["workspaces"]], ["platform", "root"])


class SingleWorkspaceControlTests(unittest.TestCase):
    def test_single_workspace_without_id_keeps_the_default_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q", "--initial-branch=main")
            _write(root, ".spec/bitz.yaml", CONFIG)
            _write(root, ".spec/requirements/REQ-001.md", REQ_ROOT)
            parsed = parse_argv(["check", "--full", "--format", "json"])
            result, code = check_mod.run(parsed, str(root), dict(os.environ))
            self.assertEqual(code, 0, result["diagnostics"])
            self.assertEqual(result["workspace"], {"id": "root", "path": "."})
            _validate_against_schema([result])


class ExcludeTrustTests(_Base):
    """ルートのIDの省略は`multiWorkspace`の設定不適合ではないので、除外を信用できる条件を変えない（§2.1）。"""

    root_yaml = ROOT_WITHOUT_ID + "  exclude:\n    - fixtures\n"

    def test_single_workspace_in_the_excluded_area_runs_without_the_outer_precheck(self):
        _write(self.root, "fixtures/case/.spec/bitz.yaml", CONFIG + "workspace:\n  id: case\n")
        _write(self.root, "fixtures/case/.spec/requirements/REQ-001.md", REQ_ROOT)
        result, code = self.check(self.root / "fixtures" / "case", "--full")
        self.assertEqual(code, 0, result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": "case", "path": "."})
        self.assertNotIn("multiWorkspace", result)


if __name__ == "__main__":
    unittest.main()
