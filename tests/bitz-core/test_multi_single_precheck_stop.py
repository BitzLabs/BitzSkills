"""複合ワークスペースの単独操作が全体事前検査で停止する規則の単体試験（実装の確認事項C27、ADR-063）。

`05_複合ワークスペース仕様.md` §2・§3・§7・§8・§10、`01_結果・診断・終了コード.md` §2・§8、`04_doctor.md` §3を対象にする。
単独の`context`・`check`・`verify`・`doctor`が、全体事前検査（カタログの不備、選択した最も近い設定の未登録、Gitの境界）で
非成功のとき、作業ワークスペースの処理を始めず、事前検査の診断を最上位の`diagnostics`に置いた単独結果を返すことを確かめる。

- 判定: Gitでルートを確定できるときはルートの設定で判定する。版の非対応で止まった設定は`multiWorkspace`の宣言があれば複合、
  構文などで読めない設定は単一ワークスペースとして扱う。Gitを確定できないときは最も近い設定で判定する。
- 未登録の設定の照合: 単独の`context`・`check`・`verify`は選択した最も近い設定だけ、単独の`doctor`はGitが認識する設定の比較も行う。
- 停止した単独結果の`workspace`・`revision`・操作ごとのフィールド・`--report`の保存先。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合すること。
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

import bitz
from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.errors import CliArgError

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT_YAML = (
    CONFIG
    + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
    + "    - id: api\n      path: services/api\n"
)
WEB_YAML = CONFIG + "workspace:\n  id: web\n"
API_YAML = CONFIG + "workspace:\n  id: api\n"
STRAY_YAML = CONFIG + "workspace:\n  id: stray\n"

REQ_WEB = (
    "---\nid: REQ-050\ntitle: REQ\nstatus: approved\n---\n\n# REQ-050 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-050:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)

UNREGISTERED_SELECTED = "選択した設定ファイルがカタログに登録されていません"
UNREGISTERED_GIT = "Gitが認識する設定ファイルがカタログに登録されていません"

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
        "bad = []\n"
        "for item in json.load(sys.stdin):\n"
        "    errors = [e.message for e in validator.iter_errors(item)]\n"
        "    if errors:\n"
        "        bad.append(errors[:3])\n"
        "print(json.dumps(bad, ensure_ascii=False))\n"
    )
    proc = subprocess.run(
        [uv, "run", "--quiet", "--no-project", "--with", "jsonschema==4.23.0", "python", "-I", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise unittest.SkipTest(f"jsonschemaを用意できません: {proc.stderr.strip()[-200:]}")
    bad = json.loads(proc.stdout)
    if bad:
        raise AssertionError(f"result.schema.jsonに適合しません: {bad}")


class _Base(unittest.TestCase):
    """既定の環境: ルート`platform`、メンバー`web`・`api`の複合ワークスペースをGitのリポジトリに作る。"""

    use_git = True

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = dict(os.environ)
        if self.use_git:
            _git(self.root, "init", "-q", "--initial-branch=main")
            _git(self.root, "config", "user.email", "t@t")
            _git(self.root, "config", "user.name", "t")
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML)
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "services/api/.spec/bitz.yaml", API_YAML)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "apps/web/.spec/requirements/REQ-050.md", REQ_WEB)
        if self.use_git:
            _git(self.root, "add", ".")
            _git(self.root, "commit", "-q", "-m", "base")
        self.web = self.root / "apps" / "web"
        self.results: list[dict] = []

    # --- 操作の実行 ----------------------------------------------------------------
    def _run(self, module, name: str, cwd: Path, argv: tuple[str, ...], env=None):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), env if env is not None else self.env)
        self.results.append(result)
        return result, code

    def check(self, cwd: Path, *argv: str, env=None):
        return self._run(check_mod, "check", cwd, argv, env)

    def context(self, cwd: Path, *argv: str, env=None):
        return self._run(context_mod, "context", cwd, argv, env)

    def verify(self, cwd: Path, *argv: str, env=None):
        return self._run(verify_mod, "verify", cwd, argv, env)

    def doctor(self, cwd: Path, *argv: str, env=None):
        return self._run(doctor_mod, "doctor", cwd, argv, env)

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def root_doc(self, cwd: Path) -> str:
        """`cwd`の最も近い設定が所有する文書のID（`context`の起点に使う）。"""

        return "REQ-050" if self.web in (cwd, *cwd.parents) else "REQ-001"

    def no_multi_diagnostics(self, result):
        self.assertEqual([d["code"] for d in result["diagnostics"] if d["code"].startswith("SPEC-MULTI-")], [])

    # --- 検証の補助 ------------------------------------------------------------------
    def assert_stopped(self, result, code, *, workspace, path, source_path=None, summary=UNREGISTERED_SELECTED):
        """`SPEC-MULTI-UNREGISTERED-001`の1件だけを持つ停止した単独結果であること。"""

        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": workspace, "path": path})
        diagnostics = result["diagnostics"]
        self.assertEqual([d["code"] for d in diagnostics], ["SPEC-MULTI-UNREGISTERED-001"], diagnostics)
        self.assertEqual(diagnostics[0]["summary"], summary)
        self.assertEqual(diagnostics[0]["resultStatus"], "blocked")
        if source_path is None:
            source_path = f"{path}/.spec/bitz.yaml"
        self.assertEqual(
            diagnostics[0]["source"], {"kind": "file", "workspaceId": None, "path": source_path}
        )

    def assert_check_stop_shape(self, result, *, scope):
        self.assertEqual(result["scope"], scope)
        if scope == "changed":
            self.assertEqual(
                result["selection"], {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}
            )
            self.assertNotIn("checkedDocumentCount", result)
        else:
            self.assertEqual((result["checkedDocumentCount"], result["checkedStatementCount"]), (0, 0))
            self.assertNotIn("selection", result)

    def assert_verify_stop_shape(self, result):
        self.assertEqual((result["targetResults"], result["commands"]), ([], []))

    def assert_context_stop_shape(self, result, roots):
        self.assertIsNone(result["contextDigest"])
        self.assertEqual(result["roots"], roots)
        self.assertEqual(
            result["resolution"], {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0}
        )
        self.assertNotIn("workspaces", result["resolution"])
        self.assertNotIn("crossWorkspaceEdges", result["resolution"])
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["constraintLedger"], {"statements": []})
        self.assertEqual(result["coverage"]["adjacent"], [])
        for bucket in result["coverage"]["must"].values():
            self.assertEqual(bucket, [])

    def assert_doctor_stop_shape(self, result, check_names):
        self.assertEqual([c["name"] for c in result["checks"]], check_names)
        for forbidden in ("config", "schema", "ears", "command", "impact", "workspace"):
            self.assertNotIn(forbidden, [c["name"] for c in result["checks"]])
        self.assertNotIn("multiWorkspace", result)
        self.assertNotIn("workspaces", result)


class _WithStray(_Base):
    """カタログにない`tools/x/.spec/bitz.yaml`（未追跡）がある環境。"""

    def setUp(self):
        super().setUp()
        _write(self.root, "tools/x/.spec/bitz.yaml", STRAY_YAML)
        self.stray = self.root / "tools" / "x"


class UnregisteredNearestConfigStopTests(_WithStray):
    """選択した最も近い設定がカタログにないと、4操作が`SPEC-MULTI-UNREGISTERED-001`で止まる（§3の4・§7）。"""

    def test_check_stops_for_each_scope(self):
        result, code = self.check(self.stray)
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_check_stop_shape(result, scope="changed")
        result, code = self.check(self.stray, "--full")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_check_stop_shape(result, scope="full")
        result, code = self.check(self.stray, "REQ-001")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_check_stop_shape(result, scope="selected")

    def test_context_stops_with_input_roots(self):
        result, code = self.context(self.stray, "REQ-002", "REQ-001")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_context_stop_shape(result, ["REQ-001", "REQ-002"])

    def test_verify_stops(self):
        result, code = self.verify(self.stray)
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_verify_stop_shape(result)
        self.assertEqual(result["scope"], "all")
        result, code = self.verify(self.stray, "REQ-001")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assertEqual(result["scope"], "selected")

    def test_doctor_stops_with_top_level_checks_only(self):
        result, code = self.doctor(self.stray)
        # 単独のdoctorはGitが認識する設定の比較も行う。未追跡で無視されていない設定なので、Git側の文言になる（同じパスは1件）。
        self.assert_stopped(result, code, workspace=None, path="tools/x", summary=UNREGISTERED_GIT)
        self.assert_doctor_stop_shape(result, ["core", "git", "catalog"])
        self.assertEqual(result["checks"][2], {"name": "catalog", "status": "blocked"})
        self.assertEqual(result["core"]["version"], "1.0.0")

    def test_workspace_option_does_not_replace_the_selected_config_check(self):
        for ws in ("web", "platform", "nope"):
            with self.subTest(workspace=ws):
                result, code = self.check(self.stray, "--workspace", ws, "--full")
                self.assert_stopped(result, code, workspace=None, path="tools/x")
                result, code = self.context(self.stray, "REQ-001", "--workspace", ws)
                self.assert_stopped(result, code, workspace=None, path="tools/x")
                result, code = self.verify(self.stray, "--workspace", ws)
                self.assert_stopped(result, code, workspace=None, path="tools/x")
                result, code = self.doctor(self.stray, "--workspace", ws)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(result["workspace"], {"id": None, "path": "tools/x"})

    def test_qualified_id_owner_does_not_replace_the_selected_config_check(self):
        result, code = self.context(self.stray, "web::TECH-010")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        result, code = self.verify(self.stray, "web::TECH-010")
        self.assert_stopped(result, code, workspace=None, path="tools/x")

    def test_conflicting_qualified_owners_remain_argument_errors(self):
        with self.assertRaises(CliArgError):
            self.verify(self.stray, "web::TECH-010", "--workspace", "api")
        with self.assertRaises(CliArgError):
            self.context(self.stray, "web::TECH-010", "api::TECH-020")

    def test_stray_inside_a_member_is_also_unregistered(self):
        _write(self.root, "apps/web/sub/.spec/bitz.yaml", STRAY_YAML)
        result, code = self.check(self.web / "sub", "--full")
        self.assert_stopped(result, code, workspace=None, path="apps/web/sub")

    def test_unrelated_unregistered_config_does_not_stop_single_check_context_verify(self):
        # 選択した最も近い設定（メンバー`web`、ルート）はカタログにある。無関係な`tools/x`があってもGitの列挙は行わない。
        for cwd, wid, path in ((self.web, "web", "apps/web"), (self.root, "platform", ".")):
            with self.subTest(cwd=str(cwd)):
                result, code = self.check(cwd, "--full")
                self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
                self.assertEqual(result["workspace"], {"id": wid, "path": path})
                result, code = self.verify(cwd)
                self.no_multi_diagnostics(result)
                self.assertEqual(result["workspace"], {"id": wid, "path": path})
                result, code = self.context(cwd, self.root_doc(cwd))
                self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_single_doctor_still_compares_git_known_configs(self):
        # 無関係な場所の未登録の設定でも、単独のdoctorは--all-workspacesと同じくGitが認識する設定を比較して止まる。
        for cwd in (self.web, self.root):
            with self.subTest(cwd=str(cwd)):
                result, code = self.doctor(cwd)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(
                    [(d["code"], d["summary"], d["source"]["path"]) for d in result["diagnostics"]],
                    [("SPEC-MULTI-UNREGISTERED-001", UNREGISTERED_GIT, "tools/x/.spec/bitz.yaml")],
                )
        # 停止した単独のdoctorのworkspaceは、選択した最も近い設定（登録済み）のID。
        result, _ = self.doctor(self.web)
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        result, _ = self.doctor(self.root)
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})


class DoctorSnapshotComparisonTests(_Base):
    def test_unregistered_config_only_in_head_stops_doctor_but_not_check_or_verify(self):
        _write(self.root, "tools/x/.spec/bitz.yaml", STRAY_YAML)
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "unregistered")
        (self.root / "tools/x/.spec/bitz.yaml").unlink()
        for cwd in (self.web, self.root):
            with self.subTest(cwd=str(cwd)):
                result, code = self.doctor(cwd)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(
                    [(d["code"], d["summary"]) for d in result["diagnostics"]],
                    [("SPEC-MULTI-UNREGISTERED-001", UNREGISTERED_GIT)],
                )
                self.assert_doctor_stop_shape(result, ["core", "git", "catalog"])
                # 単独のcheck・verifyは現在のスナップショットのカタログだけを対象にし、HEADの設定の列挙は行わない。
                result, code = self.check(cwd, "--full")
                self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
                result, code = self.verify(cwd)
                self.no_multi_diagnostics(result)

    def test_git_ignored_unregistered_nearest_config_stops_doctor(self):
        # Gitが無視する未登録の設定は、Gitが認識する設定の比較では見つからないが、選択した最も近い設定の照合で止まる。
        _write(self.root, ".gitignore", "tools/y/\n")
        _write(self.root, "tools/y/.spec/bitz.yaml", STRAY_YAML)
        ignored = self.root / "tools" / "y"
        result, code = self.doctor(ignored)
        self.assert_stopped(result, code, workspace=None, path="tools/y")
        self.assert_doctor_stop_shape(result, ["core", "git", "catalog"])
        # 無視された設定の外にいれば、単独のdoctorは止まらない。
        result, code = self.doctor(self.web)
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_git_ignored_unregistered_nearest_config_stops_other_operations_too(self):
        _write(self.root, ".gitignore", "tools/y/\n")
        _write(self.root, "tools/y/.spec/bitz.yaml", STRAY_YAML)
        ignored = self.root / "tools" / "y"
        result, code = self.check(ignored, "--full")
        self.assert_stopped(result, code, workspace=None, path="tools/y")
        result, code = self.verify(ignored)
        self.assert_stopped(result, code, workspace=None, path="tools/y")
        result, code = self.context(ignored, "REQ-001")
        self.assert_stopped(result, code, workspace=None, path="tools/y")

    def test_selected_and_git_findings_for_the_same_path_are_one_diagnostic(self):
        _write(self.root, "tools/x/.spec/bitz.yaml", STRAY_YAML)
        _write(self.root, "tools/z/.spec/bitz.yaml", STRAY_YAML)
        result, _ = self.doctor(self.root / "tools" / "x")
        self.assertEqual(
            [(d["source"]["path"], d["summary"]) for d in result["diagnostics"]],
            [("tools/x/.spec/bitz.yaml", UNREGISTERED_GIT), ("tools/z/.spec/bitz.yaml", UNREGISTERED_GIT)],
        )


class GitBoundaryNotConfirmedTests(unittest.TestCase):
    """Gitでリポジトリのルートを確定できないときは、最も近い設定で複合ワークスペースかを判定する（§3、§10）。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML)
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "services/api/.spec/bitz.yaml", API_YAML)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "apps/web/.spec/requirements/REQ-050.md", REQ_WEB)
        _write(self.root, "docs/note.md", "メモ。\n")
        _write(self.root, "apps/web/src/main.txt", "x\n")
        self.results: list[dict] = []
        self.no_git_env = {**os.environ, "PATH": str(self.root / "no-such-bin")}
        self.not_a_repo_env = dict(os.environ)

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def run_all(self, cwd: Path, env: dict, *extra: str):
        out = {}
        context_root = "REQ-050" if (self.root / "apps" / "web") in (cwd, *cwd.parents) else "REQ-001"
        for name, module in (("check", check_mod), ("context", context_mod), ("verify", verify_mod), ("doctor", doctor_mod)):
            argv = [name, *(["--full"] if name == "check" else []), *([context_root] if name == "context" else []), *extra, "--format", "json"]
            result, code = module.run(parse_argv(argv), str(cwd), env)
            self.results.append(result)
            out[name] = (result, code)
        return out

    def assert_git_blocked(self, out, *, workspace_id, path):
        for name, (result, code) in out.items():
            with self.subTest(operation=name):
                self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
                self.assertEqual(result["workspace"], {"id": workspace_id, "path": path})
                self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])
                self.assertEqual(result["diagnostics"][0]["summary"], "Gitのリポジトリの境界を確定できません")
                if name != "doctor":
                    self.assertIsNone(result["revision"])
                else:
                    self.assertEqual([c["name"] for c in result["checks"]], ["core", "git"])
                    self.assertEqual(result["checks"][1], {"name": "git", "status": "blocked"})
        self.assertEqual(out["check"][0]["scope"], "full")

    def test_without_git_the_root_and_its_subdirectories_stop(self):
        for cwd in (self.root, self.root / "docs"):
            with self.subTest(cwd=str(cwd)):
                out = self.run_all(cwd, self.no_git_env)
                self.assert_git_blocked(out, workspace_id="platform", path=".")

    def test_not_a_git_repository_stops_the_same_way(self):
        for cwd in (self.root, self.root / "docs"):
            with self.subTest(cwd=str(cwd)):
                out = self.run_all(cwd, self.not_a_repo_env)
                self.assert_git_blocked(out, workspace_id="platform", path=".")

    def test_inside_a_member_the_single_workspace_contract_is_kept(self):
        # 最も近い設定（メンバー）が`multiWorkspace`を宣言していないため、Gitなしでは単一ワークスペースのまま。
        for env in (self.no_git_env, self.not_a_repo_env):
            for cwd in (self.root / "apps" / "web", self.root / "apps" / "web" / "src"):
                with self.subTest(cwd=str(cwd)):
                    out = self.run_all(cwd, env)
                    for name, (result, code) in out.items():
                        self.assertEqual([d for d in result["diagnostics"] if d["code"].startswith("SPEC-MULTI-")], [])
                        self.assertEqual(result["workspace"], {"id": "web", "path": "."})
                    self.assertEqual(out["check"][1], 0)
                    self.assertEqual(out["context"][1], 0)
                    self.assertEqual(out["doctor"][1], 0)

    def test_all_workspaces_discovery_is_unchanged(self):
        # `--all-workspaces`は現在のディレクトリ自身だけを候補にする。サブディレクトリからは発見できず終了コード4。
        with self.assertRaises(CliArgError):
            check_mod.run(parse_argv(["check", "--all-workspaces", "--format", "json"]), str(self.root / "docs"), self.no_git_env)
        result, code = check_mod.run(
            parse_argv(["check", "--all-workspaces", "--format", "json"]), str(self.root), self.no_git_env
        )
        # `--all-workspaces`の停止結果（`revision: null`）も公開スキーマに適合する。
        self.results.append(result)
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])


class RootConfigDeclarationTests(_Base):
    """ルートの設定が読めないときの複合ワークスペースの判定（§3、ADR-063の4）。"""

    def test_unsupported_schema_major_with_multiworkspace_stops(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"'))
        for cwd, wid, path in ((self.root, "platform", "."), (self.web, "web", "apps/web")):
            with self.subTest(cwd=str(cwd)):
                for result, code in (
                    self.check(cwd, "--full"),
                    self.context(cwd, self.root_doc(cwd)),
                    self.verify(cwd),
                ):
                    self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
                    self.assertEqual(result["workspace"], {"id": wid, "path": path})
                    self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-CONFIG-SCHEMA-001"])
                result, code = self.doctor(cwd)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(result["workspace"], {"id": wid, "path": path})
                self.assert_doctor_stop_shape(result, ["core", "git", "catalog"])
                self.assertEqual(result["checks"][2], {"name": "catalog", "status": "blocked"})

    def test_unsupported_earsai_major_with_multiworkspace_stops(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace('earsAi: "1.0"', 'earsAi: "2.0"'))
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-EARS-VERSION-001"])
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        result, _ = self.doctor(self.root)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-DOCTOR-EARS-001"])

    def test_unsupported_major_without_multiworkspace_is_single(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"') + "workspace:\n  id: platform\n")
        result, code = self.check(self.root, "--full")
        # 単一ワークスペースの設定の停止（SPEC-MULTI-*ではない）。
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-CONFIG-SCHEMA-001"])
        self.assertEqual(code, 2)
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_syntax_error_in_root_config_is_treated_as_single_workspace(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "  bad: [unterminated\n")
        # ルートでは、設定の構文エラーがそのまま単一ワークスペースの診断になる。
        for result, code in (self.check(self.root, "--full"), self.context(self.root, "REQ-001"), self.verify(self.root)):
            self.assertEqual(result["workspace"], {"id": None, "path": "."})
            self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-CONFIG-SCHEMA-001"])
            self.assertEqual(code, 3)
        # メンバーでは、複合ワークスペースと判定しないため全体事前検査で止まらず、単一ワークスペースとして成功する。
        for result, code in (self.check(self.web, "--full"), self.verify(self.web), self.context(self.web, "REQ-050")):
            self.no_multi_diagnostics(result)
            self.assertEqual(result["workspace"], {"id": "web", "path": "."})
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_wrong_type_in_root_config_is_treated_as_single_workspace(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace("language: ja", "language: [ja]"))
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])


class CatalogDefectTests(_Base):
    def break_member(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "    - id: ghost\n      path: services/ghost\n")

    def test_catalog_defect_stops_every_operation(self):
        self.break_member()
        for cwd, wid, path in ((self.web, "web", "apps/web"), (self.root, "platform", ".")):
            with self.subTest(cwd=str(cwd)):
                for result, code in (self.check(cwd, "--full"), self.context(cwd, self.root_doc(cwd)), self.verify(cwd)):
                    self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
                    self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
                    # 選択した最も近い設定は登録済みで、設定自身が有効なIDを持つため、そのIDとパスを返す。
                    self.assertEqual(result["workspace"], {"id": wid, "path": path})
                result, code = self.doctor(cwd)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(result["workspace"], {"id": wid, "path": path})
                self.assert_doctor_stop_shape(result, ["core", "git", "catalog"])
                self.assertEqual(result["checks"][2], {"name": "catalog", "status": "failed"})

    def test_unknown_workspace_option_does_not_make_exit_code_4_when_precheck_fails(self):
        self.break_member()
        for argv in (("--workspace", "nope", "--full"),):
            result, code = self.check(self.web, *argv)
            self.assertEqual((result["status"], code), ("failed", 1))
            self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
        for runner, extra in ((self.context, ("REQ-050",)), (self.verify, ()), (self.doctor, ())):
            result, code = runner(self.web, *extra, "--workspace", "nope")
            self.assertEqual((result["status"], code), ("failed", 1))
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})

    def test_unknown_workspace_option_with_valid_catalog_is_still_an_argument_error(self):
        for runner, extra in ((self.check, ()), (self.context, ("REQ-001",)), (self.verify, ()), (self.doctor, ())):
            with self.assertRaises(CliArgError):
                runner(self.root, *extra, "--workspace", "nope")

    def test_unknown_qualified_id_owner_with_precheck_failure_returns_the_stop_result(self):
        self.break_member()
        result, code = self.context(self.web, "nope::REQ-001")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
        result, code = self.verify(self.web, "nope::REQ-001")
        self.assertEqual((result["status"], code), ("failed", 1))

    def test_malformed_catalog_registers_only_the_root(self):
        # members が空（カタログの形が不正）。ルートだけを登録済みとみなし、メンバーの設定は未登録のためIDをnullにする。
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  maxMembers: 5\n  members: []\n")
        result, code = self.check(self.web, "--full")
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-CONFIG-001"])
        self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"})
        result, code = self.check(self.root, "--full")
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        result, code = self.doctor(self.web)
        self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"})

    def test_member_with_invalid_own_config_has_null_id_and_its_path(self):
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML + "  bad: [unterminated\n")
        result, code = self.check(self.web, "--full")
        self.assertEqual((result["status"], code), ("error", 3), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"})

    def test_resource_limit_is_checked_for_single_operations(self):
        members = "".join(f"    - id: m{i}\n      path: libs/m{i}\n" for i in range(3))
        _write(
            self.root,
            ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  maxMembers: 1\n  members:\n" + members,
        )
        for i in range(3):
            _write(self.root, f"libs/m{i}/.spec/bitz.yaml", CONFIG + f"workspace:\n  id: m{i}\n")
        result, code = self.verify(self.root)
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-LIMIT-001"])
        self.assertEqual(result["diagnostics"][0]["evidence"]["dimension"], "memberCount")


class OmittedWorkspaceIdTests(_Base):
    """`workspace.id`の省略時の既定値`root`は、複合ワークスペースでは有効なIDではないので、停止結果の`workspace.id`にしない（§2）。"""

    GHOST = "    - id: ghost\n      path: services/ghost\n"

    def test_root_config_without_workspace_id_has_null_id_when_the_catalog_stops(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace("workspace:\n  id: platform\n", "") + self.GHOST)
        for runner, extra in ((self.check, ("--full",)), (self.verify, ()), (self.context, ("REQ-001",)), (self.doctor, ())):
            result, code = runner(self.root, *extra)
            self.assertEqual(code, 1, result["diagnostics"])
            self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
            self.assertEqual(result["workspace"], {"id": None, "path": "."})
        # 明示したIDを持つメンバーの設定は、ルートがIDを省略していてもそのIDを返す。
        result, _ = self.check(self.web, "--full")
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})

    def test_member_config_without_workspace_id_has_null_id_when_the_catalog_stops(self):
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG)
        for runner, extra in ((self.check, ("--full",)), (self.verify, ()), (self.context, ("REQ-050",)), (self.doctor, ())):
            result, code = runner(self.web, *extra)
            self.assertEqual(code, 1, result["diagnostics"])
            self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
            self.assertEqual(result["workspace"], {"id": None, "path": "apps/web"})

    def test_root_config_without_workspace_id_and_unsupported_major_has_null_id(self):
        _write(
            self.root,
            ".spec/bitz.yaml",
            ROOT_YAML.replace("workspace:\n  id: platform\n", "").replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"'),
        )
        for runner, extra in ((self.check, ("--full",)), (self.doctor, ())):
            result, code = runner(self.root, *extra)
            self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
            self.assertEqual(result["workspace"], {"id": None, "path": "."})

    def test_explicit_id_named_root_is_kept(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace("id: platform", "id: root") + self.GHOST)
        result, _ = self.check(self.root, "--full")
        self.assertEqual(result["workspace"], {"id": "root", "path": "."})


class StoppedResultRevisionTests(_WithStray):
    def test_revision_follows_the_normal_rules_when_the_git_boundary_is_known(self):
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True, check=True
        ).stdout.strip()
        result, _ = self.check(self.stray)
        self.assertEqual(result["revision"], {"base": head, "commit": head, "dirty": True})
        for result, _ in (self.verify(self.stray), self.context(self.stray, "REQ-001")):
            self.assertEqual(result["revision"], {"commit": head, "dirty": True})

    def test_repository_without_commits_has_null_revision_but_keeps_the_scope_rule(self):
        shutil.rmtree(self.root / ".git")
        _git(self.root, "init", "-q", "--initial-branch=main")
        result, code = self.check(self.stray)
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assertIsNone(result["revision"])
        self.assertEqual(result["scope"], "full")
        for result, _ in (self.verify(self.stray), self.context(self.stray, "REQ-001")):
            self.assertIsNone(result["revision"])

    def test_explicit_unresolvable_base_remains_an_argument_error(self):
        with self.assertRaises(CliArgError):
            self.check(self.stray, "--base", "no-such-rev")


class StoppedContextShapeTests(_WithStray):
    def test_context_result_has_no_composite_fields_and_documents_are_empty(self):
        result, code = self.context(self.stray, "REQ-001", "--detail", "full", "--purpose", "implement")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        self.assert_context_stop_shape(result, ["REQ-001"])
        self.assertEqual(result["purpose"], "implement")
        self.assertEqual(result["projection"], {"detail": "full", "expanded": []})
        for document in result["documents"]:
            self.assertNotIn("workspaceId", document)


class StoppedReportTests(_WithStray):
    def reports(self, directory: Path) -> list[Path]:
        return sorted((directory / ".spec" / "reports").glob("*.json")) if (directory / ".spec" / "reports").is_dir() else []

    def test_check_report_is_saved_under_the_selected_candidate(self):
        result, code = self.check(self.stray, "--full", "--report")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        saved = self.reports(self.stray)
        self.assertEqual(len(saved), 1, saved)
        self.assertTrue(saved[0].name.endswith("-check.json"))
        self.assertEqual(json.loads(saved[0].read_text(encoding="utf-8")), result)
        # ルートワークスペースへは保存しない。
        self.assertEqual(self.reports(self.root), [])

    def test_verify_report_is_saved_under_the_selected_candidate(self):
        result, code = self.verify(self.stray, "--report")
        self.assert_stopped(result, code, workspace=None, path="tools/x")
        saved = self.reports(self.stray)
        self.assertEqual(len(saved), 1, saved)
        self.assertTrue(saved[0].name.endswith("-verify.json"))
        self.assertEqual(json.loads(saved[0].read_text(encoding="utf-8")), result)
        self.assertEqual(self.reports(self.root), [])

    def test_report_of_a_registered_member_is_saved_under_the_member(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "    - id: ghost\n      path: services/ghost\n")
        result, _ = self.check(self.web, "--full", "--report")
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual(len(self.reports(self.web)), 1)
        self.assertEqual(self.reports(self.root), [])

    def test_no_report_without_the_flag(self):
        self.check(self.stray, "--full")
        self.verify(self.stray)
        self.assertEqual(self.reports(self.stray), [])

    def test_report_write_failure_is_added_to_the_stopped_result(self):
        (self.stray / ".spec" / "reports").symlink_to(self.root)
        result, code = self.check(self.stray, "--full", "--report")
        self.assertEqual(
            sorted(d["code"] for d in result["diagnostics"]), ["SPEC-MULTI-UNREGISTERED-001", "SPEC-REPORT-WRITE-001"]
        )
        self.assertEqual((result["status"], code), ("error", 3))


class DeterminismTests(_Base):
    def test_stop_output_is_identical_across_hash_seeds(self):
        # 複数の未登録の設定を持つ停止結果の診断の順序が、set・dictの反復順に依存しない。
        for name in ("c", "a", "b", "e", "d"):
            _write(self.root, f"tools/{name}/.spec/bitz.yaml", CONFIG + f"workspace:\n  id: s{name}\n")
        source = Path(bitz.__file__).resolve().parents[1]  # 試験対象のCoreのsrc（PYTHONPATHで差し替えた場合も追従する）
        outputs = []
        for seed in ("0", "12345", "777"):
            env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(source)}
            row = []
            for op in (["doctor"], ["check", "--full"], ["verify"], ["context", "REQ-001"]):
                proc = subprocess.run(
                    [sys.executable, "-m", "bitz.cli", *op, "--format", "json"],
                    cwd=self.root / "tools" / "c", env=env, capture_output=True, text=True,
                )
                payload = json.loads(proc.stdout)
                payload.pop("durationMs")
                row.append((proc.returncode, payload))
            outputs.append(row)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        doctor_result = outputs[0][0][1]
        self.assertEqual(
            [d["source"]["path"] for d in doctor_result["diagnostics"]],
            [f"tools/{n}/.spec/bitz.yaml" for n in "abcde"],
        )
        # check・verify・contextは選択した最も近い設定だけを照合するので1件。
        for _code, payload in outputs[0][1:]:
            self.assertEqual(len(payload["diagnostics"]), 1)


if __name__ == "__main__":
    unittest.main()
