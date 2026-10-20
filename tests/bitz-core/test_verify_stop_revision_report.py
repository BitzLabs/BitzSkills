"""`verify`の早期に返す結果（設定がない、設定の停止、検証対象が0件）が、`revision`を求め、`--report`を保存する規則の単体試験
（実装の確認事項C41）。

`01_結果・診断・終了コード.md` §2（`revision`の規則）と§8（レポート）を対象にする。

- `revision`: 単一ワークスペースでGit不在、またはコミットのないリポジトリだけ`null`とする。設定の停止と検証対象が0件の結果も、
  コミットがあれば`{commit, dirty}`を返す。`dirty`は実行時の作業ツリーの状態で、レポートの保存より前に求める。
  複合ワークスペースの検証対象が0件の結果も同じ。
- `--report`: `check`と`verify`は、状態にかかわらず、指定された場合だけ`.spec/reports/`へ結果のJSONを保存する。保存の内容は標準出力の結果と一致する。
  `--report`がなければレポートを作らず、既存のレポートを変えない。保存に失敗すれば`SPEC-REPORT-WRITE-001`を加え、元の結果と診断は保持する。
- 設定がない場合（`.spec/bitz.yaml`がない）の`verify --report`は、`check --report`と同じく、保存先の`.spec`がなければ保存に失敗する。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合し、`PYTHONHASHSEED`を変えても同じ出力になる。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bitz
from bitz import check as check_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"
REPORT_NAME = re.compile(r"^[0-9]{8}T[0-9]{6}Z-verify(?:-[1-9][0-9]*)?\.json$")
MISSING_CONFIG = "SPEC-WORKSPACE-MISSING-001"
EMPTY_TARGETS = "SPEC-VERIFY-BLOCKED-002"
REPORT_WRITE = "SPEC-REPORT-WRITE-001"
CONFIG_SCHEMA = "SPEC-CONFIG-SCHEMA-001"
EARS_VERSION = "SPEC-EARS-VERSION-001"


def _config(*, schema: str = "1.0", ears: str = "1.0", language: str = "ja", workspace_id: str = "solo") -> str:
    return f'schemaVersion: "{schema}"\nlanguage: {language}\nearsAi: "{ears}"\nworkspace:\n  id: {workspace_id}\n'


# 設定の停止: 名前 -> (設定, 診断コード, 状態, 終了コード, `workspace.id`)。版の非対応は同一性が確定するので`solo`、構文などの不正は`null`。
STOPS = {
    "schema": (_config(schema="9.9"), CONFIG_SCHEMA, "blocked", 2, "solo"),
    "ears": (_config(ears="2.0"), EARS_VERSION, "blocked", 2, "solo"),
    "syntax": (_config() + "  : bad: [\n", CONFIG_SCHEMA, "error", 3, None),
    "anchor": (_config(language="&a ja"), CONFIG_SCHEMA, "error", 3, None),
    "type": (_config(language="5"), CONFIG_SCHEMA, "error", 3, None),
}
# 設定が停止せず、`approved`のREQがないので、引数なしの検証対象は0件になる。
DRAFT_REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: draft\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
ROOT_PLATFORM = (
    'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
    "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
)
WEB = _config(workspace_id="web")


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    proc = subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


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
    """作業ツリーを一時ディレクトリに作る。Gitのリポジトリにするか、コミットするかは各試験が決める。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.results: list[dict] = []
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        # Git不在: 実行ファイルを見つけられない環境。
        self.no_git_env = {**self.env, "PATH": str(self.root / "no-such-bin")}

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def init_repository(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def commit_all(self) -> str:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")
        return _git(self.root, "rev-parse", "HEAD")

    def reports_dir(self, root: Path | None = None) -> Path:
        return (root or self.root) / ".spec" / "reports"

    def reports(self, root: Path | None = None) -> list[Path]:
        directory = self.reports_dir(root)
        return sorted(p for p in directory.iterdir() if p.is_file()) if directory.is_dir() else []

    def run_op(self, module, name: str, cwd: Path, argv: tuple[str, ...] = (), env: dict | None = None):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), env if env is not None else self.env)
        self.results.append(result)
        return result, code

    def verify(self, *argv: str, cwd: Path | None = None, env: dict | None = None):
        return self.run_op(verify_mod, "verify", cwd or self.root, argv, env)

    def codes(self, result) -> list[str]:
        return [d["code"] for d in result["diagnostics"]]

    def assert_revision(self, result, commit: str | None, dirty: bool = False):
        if commit is None:
            self.assertIsNone(result["revision"], result["diagnostics"])
        else:
            # `verify`の`revision`は、40桁の小文字16進の`commit`と真偽値の`dirty`だけを持つ（結果・診断・終了コード §2）。
            self.assertEqual(result["revision"], {"commit": commit, "dirty": dirty}, result["diagnostics"])

    def assert_saved_once(self, result, root: Path | None = None) -> Path:
        """`.spec/reports/`にちょうど1件のレポートがあり、その内容が標準出力の結果と一致する。"""
        saved = self.reports(root)
        self.assertEqual(len(saved), 1, saved)
        self.assertRegex(saved[0].name, REPORT_NAME)
        self.assertEqual(json.loads(saved[0].read_text(encoding="utf-8")), result)
        return saved[0]

    def leftovers(self, root: Path | None = None) -> list[str]:
        directory = self.reports_dir(root)
        return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp")) if directory.is_dir() else []


class _SingleBase(_Base):
    """単一ワークスペース（`solo`）。設定は各試験が置く。"""

    def put_config(self, text: str) -> None:
        _write(self.root, ".spec/bitz.yaml", text)

    def put_draft_requirement(self) -> None:
        _write(self.root, ".spec/requirements/REQ-001.md", DRAFT_REQ)

    def stop_cases(self):
        for name, (config, code, status, exit_code, workspace_id) in STOPS.items():
            yield name, config, code, status, exit_code, workspace_id


class ConfigStopTests(_SingleBase):
    """設定の停止（版の非対応、構文などの不正）の`verify`は、コミットがあれば`revision`を返し、`--report`なら保存する。"""

    def prepare(self, config: str, *, commit: bool = True) -> str | None:
        self.put_config(config)
        self.init_repository()
        return self.commit_all() if commit else None

    def test_revision_is_returned_without_report_and_no_file_is_created(self):
        for name, config, code, status, exit_code, workspace_id in self.stop_cases():
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                head = self.prepare(config)
                result, actual = self.verify()
                self.assertEqual((result["status"], actual), (status, exit_code), result["diagnostics"])
                self.assertEqual(self.codes(result), [code])
                self.assertEqual(result["workspace"], {"id": workspace_id, "path": "."})
                self.assert_revision(result, head)
                # `--report`がなければ、レポートのディレクトリも作らない（結果・診断・終了コード §8）。
                self.assertFalse(self.reports_dir().exists())

    def test_dirty_reflects_the_working_tree(self):
        head = self.prepare(STOPS["schema"][0])
        _write(self.root, "notes.md", "未追跡。\n")
        result, _ = self.verify()
        self.assert_revision(result, head, dirty=True)

    def test_report_is_saved_for_every_stop_and_matches_stdout(self):
        for name, config, code, status, exit_code, workspace_id in self.stop_cases():
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                head = self.prepare(config)
                plain, _ = self.verify()
                result, actual = self.verify("--report")
                # 結果の本体、状態、終了コードは`--report`の有無で変わらない（`durationMs`を除く）。
                self.assertEqual((result["status"], actual), (status, exit_code))
                self.assertEqual({**result, "durationMs": 0}, {**plain, "durationMs": 0})
                self.assertEqual(self.codes(result), [code])
                # 実行時の状態は、レポートの保存より前に求める。保存したレポートで`dirty`が`true`にならない。
                self.assert_revision(result, head, dirty=False)
                self.assert_saved_once(result)
                self.assertEqual(self.leftovers(), [])

    def test_existing_reports_are_kept_and_never_overwritten(self):
        self.prepare(STOPS["schema"][0], commit=False)
        existing = self.reports_dir() / "existing.json"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b'{"note": "pre-existing"}\n')
        self.commit_all()
        result, _ = self.verify("--report")
        self.assertEqual(existing.read_bytes(), b'{"note": "pre-existing"}\n')
        created = [p for p in self.reports() if p != existing]
        self.assertEqual(len(created), 1)
        self.assertEqual(json.loads(created[0].read_text(encoding="utf-8")), result)

    def test_without_commit_revision_is_null_but_the_report_is_still_saved(self):
        for name, config, code, status, exit_code, workspace_id in self.stop_cases():
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                self.prepare(config, commit=False)
                result, actual = self.verify("--report")
                self.assertEqual((result["status"], actual), (status, exit_code))
                self.assert_revision(result, None)
                self.assert_saved_once(result)

    def test_git_absent_revision_is_null_but_the_report_is_still_saved(self):
        for name, config, code, status, exit_code, workspace_id in self.stop_cases():
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                self.prepare(config)  # `.git`はあるが、Gitの実行ファイルを見つけられない環境で実行する。
                result, actual = self.verify("--report", env=self.no_git_env)
                self.assertEqual((result["status"], actual), (status, exit_code))
                self.assert_revision(result, None)
                self.assert_saved_once(result)

    def test_not_a_repository_revision_is_null_but_the_report_is_still_saved(self):
        self.put_config(STOPS["schema"][0])
        result, actual = self.verify("--report")
        self.assertEqual((result["status"], actual), ("blocked", 2))
        self.assert_revision(result, None)
        self.assert_saved_once(result)

    def test_report_failure_adds_a_diagnostic_and_keeps_the_original_result(self):
        for name, config, code, status, exit_code, workspace_id in self.stop_cases():
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                self.put_config(config)
                # `.spec/reports`を通常のファイルで塞ぐ（ディレクトリの権限に依存しない）。
                _write(self.root, ".spec/reports", "occupied\n")
                self.init_repository()
                head = self.commit_all()
                result, actual = self.verify("--report")
                # 元の診断は端末に保持され、保存の失敗が加わって`error`／3になる（結果・診断・終了コード §8）。
                self.assertEqual(sorted(self.codes(result)), sorted([code, REPORT_WRITE]))
                self.assertEqual((result["status"], actual), ("error", 3))
                self.assert_revision(result, head)
                self.assertTrue((self.root / ".spec/reports").is_file())

    def test_json_output_is_identical_for_any_hash_seed(self):
        for name in ("schema", "anchor"):
            with self.subTest(stop=name):
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir()
                self.prepare(STOPS[name][0])
                outputs = []
                for seed in ("0", "1", "4242"):
                    copy_root = Path(tempfile.mkdtemp(prefix="bitz-seed-"))
                    self.addCleanup(shutil.rmtree, copy_root, True)
                    shutil.copytree(self.root, copy_root, dirs_exist_ok=True)
                    outputs.append(self.cli(copy_root, seed, "--report"))
                first = outputs[0]
                self.assertEqual(first["returncode"], STOPS[name][3])
                self.assertIsNotNone(first["result"]["revision"])
                for other in outputs[1:]:
                    self.assertEqual(other["returncode"], first["returncode"])
                    self.assertEqual(other["result"], first["result"])
                    self.assertEqual(other["report"], first["result"])

    def cli(self, cwd: Path, seed: str, *argv: str) -> dict:
        source = Path(bitz.__file__).resolve().parents[1]  # 試験対象のCoreのsrc（PYTHONPATHで差し替えた場合も追従する）
        env = {**self.env, "PYTHONHASHSEED": seed, "PYTHONPATH": str(source)}
        proc = subprocess.run([sys.executable, "-m", "bitz.cli", "verify", "--format", "json", *argv],
                              cwd=cwd, env=env, capture_output=True, text=True)
        result = json.loads(proc.stdout)
        result["durationMs"] = 0
        saved = sorted((cwd / ".spec" / "reports").glob("*.json")) if (cwd / ".spec" / "reports").is_dir() else []
        report = None
        if len(saved) == 1:
            report = json.loads(saved[0].read_text(encoding="utf-8"))
            report["durationMs"] = 0
        return {"returncode": proc.returncode, "result": result, "report": report}


class EmptyTargetsTests(_SingleBase):
    """検証対象が0件の`verify`も、コミットがあれば`revision`を返し、`--report`なら保存する。"""

    def prepare_variants(self):
        """検証対象が0件になる2つの作り方: 仕様文書がない、`approved`の文書がない（`draft`のREQだけ）。"""
        yield "no-documents", lambda: None
        yield "draft-only", self.put_draft_requirement

    def build(self, setup, *, commit: bool = True) -> str | None:
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.put_config(_config())
        setup()
        self.init_repository()
        return self.commit_all() if commit else None

    def test_revision_is_returned_and_scope_is_all(self):
        for name, setup in self.prepare_variants():
            with self.subTest(variant=name):
                head = self.build(setup)
                result, actual = self.verify()
                self.assertEqual((result["status"], actual), ("blocked", 2))
                self.assertEqual(self.codes(result), [EMPTY_TARGETS])
                self.assertEqual((result["scope"], result["targetResults"], result["commands"]), ("all", [], []))
                self.assert_revision(result, head)
                self.assertFalse(self.reports_dir().exists())

    def test_report_is_saved_and_matches_stdout(self):
        for name, setup in self.prepare_variants():
            with self.subTest(variant=name):
                head = self.build(setup)
                result, actual = self.verify("--report")
                self.assertEqual((result["status"], actual), ("blocked", 2))
                self.assert_revision(result, head, dirty=False)
                self.assert_saved_once(result)
                self.assertEqual(self.leftovers(), [])

    def test_without_commit_and_git_absent_revision_is_null_but_the_report_is_saved(self):
        for name, setup in self.prepare_variants():
            with self.subTest(variant=name, git="no-commit"):
                self.build(setup, commit=False)
                result, _ = self.verify("--report")
                self.assert_revision(result, None)
                self.assert_saved_once(result)
            with self.subTest(variant=name, git="absent"):
                self.build(setup)
                result, _ = self.verify("--report", env=self.no_git_env)
                self.assert_revision(result, None)
                self.assert_saved_once(result)

    def test_report_failure_adds_a_diagnostic_and_keeps_the_original_result(self):
        head = self.build(lambda: _write(self.root, ".spec/reports", "occupied\n"))
        result, actual = self.verify("--report")
        self.assertEqual(sorted(self.codes(result)), sorted([EMPTY_TARGETS, REPORT_WRITE]))
        self.assertEqual((result["status"], actual), ("error", 3))
        self.assert_revision(result, head)

    def test_a_target_argument_is_not_an_early_return(self):
        # 対照: 存在しない明示の対象は、検証対象の診断を持つ`targetResults`を返す経路で、`scope`は`selected`。
        # 早期に返す結果ではないが、`revision`と`--report`の規則は同じ。
        head = self.build(lambda: None)
        result, _ = self.verify("REQ-404", "--report")
        self.assertEqual(result["scope"], "selected")
        self.assert_revision(result, head)
        self.assert_saved_once(result)


class MissingConfigTests(_Base):
    """設定がない（`.spec/bitz.yaml`がない）`verify`。`.spec`がなければ`--report`は`check --report`と同じ保存の失敗になる。"""

    def make(self, *, commit: bool = True, spec_dir: bool = False) -> str | None:
        _write(self.root, "README.md", "仕様文書のないリポジトリ。\n")
        if spec_dir:
            (self.root / ".spec").mkdir()
        self.init_repository()
        return self.commit_all() if commit else None

    def test_revision_is_returned_without_report(self):
        head = self.make()
        result, actual = self.verify()
        self.assertEqual((result["status"], actual), ("blocked", 2))
        self.assertEqual(self.codes(result), [MISSING_CONFIG])
        self.assertEqual(result["workspace"], {"id": None, "path": "."})
        self.assert_revision(result, head)
        self.assertFalse(self.reports_dir().exists())

    def test_without_commit_and_git_absent_revision_is_null(self):
        self.make(commit=False)
        result, _ = self.verify()
        self.assert_revision(result, None)
        result, _ = self.verify(env=self.no_git_env)
        self.assert_revision(result, None)

    def test_report_without_spec_directory_fails_like_check(self):
        head = self.make()
        verify_result, verify_code = self.verify("--report")
        check_result, check_code = self.run_op(check_mod, "check", self.root, ("--report",))
        # `.spec`がないので保存に失敗し、元の診断に`SPEC-REPORT-WRITE-001`が加わる。`check`と同じ状態と終了コード。
        self.assertEqual((verify_result["status"], verify_code), ("error", 3))
        self.assertEqual((verify_result["status"], verify_code), (check_result["status"], check_code))
        self.assertEqual(sorted(self.codes(verify_result)), sorted([MISSING_CONFIG, REPORT_WRITE]))
        self.assertEqual(sorted(self.codes(verify_result)), sorted(self.codes(check_result)))
        # 診断の順序（結果・診断・終了コード §7）: `workspaceId: null`のファイルの発生元（保存先）が、環境の発生元（設定がない）より先。
        self.assertEqual(self.codes(verify_result), [REPORT_WRITE, MISSING_CONFIG])
        failure = next(d for d in verify_result["diagnostics"] if d["code"] == REPORT_WRITE)
        self.assertEqual(failure["source"], {"kind": "file", "workspaceId": None, "path": ".spec/reports"})
        self.assertEqual((failure["severity"], failure["resultStatus"]), ("error", "error"))
        self.assert_revision(verify_result, head)
        # 保存先の`.spec`を作らず、何も作らない。
        self.assertFalse((self.root / ".spec").exists())

    def test_report_with_an_empty_spec_directory_is_saved_like_check(self):
        # `.spec`が（設定なしで）あれば、`.spec/reports`を作って保存できる。`check --report`と同じ。
        head = self.make(spec_dir=True)
        result, actual = self.verify("--report")
        self.assertEqual(self.codes(result), [MISSING_CONFIG])
        self.assertEqual((result["status"], actual), ("blocked", 2))
        self.assert_revision(result, head)
        self.assert_saved_once(result)
        check_result, check_code = self.run_op(check_mod, "check", self.root, ("--report",))
        self.assertEqual((check_result["status"], check_code), ("blocked", 2))
        self.assertEqual(self.codes(check_result), [MISSING_CONFIG])


class MultiWorkspaceEmptyTargetsTests(_Base):
    """複合ワークスペースの検証対象が0件の経路。`revision`は`null`にせず、レポートは作業ワークスペースの`.spec/reports/`へ保存する。"""

    def build(self, *, commit: bool = True) -> str | None:
        _write(self.root, ".spec/bitz.yaml", ROOT_PLATFORM)
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB)
        _write(self.root, ".spec/requirements/REQ-001.md", DRAFT_REQ)
        self.init_repository()
        return self.commit_all() if commit else None

    def test_revision_is_returned_from_the_root_and_a_member(self):
        head = self.build()
        for label, cwd, workspace in (("root", self.root, {"id": "platform", "path": "."}),
                                      ("member", self.root / "apps" / "web", {"id": "web", "path": "apps/web"})):
            with self.subTest(cwd=label):
                result, actual = self.verify(cwd=cwd)
                self.assertEqual((result["status"], actual), ("blocked", 2))
                self.assertEqual(self.codes(result), [EMPTY_TARGETS])
                self.assertEqual(result["workspace"], workspace)
                self.assert_revision(result, head)
                self.assertFalse(self.reports_dir(cwd).exists())

    def test_report_is_saved_in_the_working_workspace(self):
        head = self.build()
        root_result, _ = self.verify("--report")
        self.assert_revision(root_result, head, dirty=False)
        self.assert_saved_once(root_result)
        self.assertEqual(self.reports(self.root / "apps" / "web"), [])
        # 作業ワークスペースがメンバーなら、メンバーの`.spec/reports/`へ保存する。ルートのレポートは未追跡なので`dirty`は`true`。
        member = self.root / "apps" / "web"
        member_result, _ = self.verify("--report", cwd=member)
        self.assert_revision(member_result, head, dirty=True)
        self.assert_saved_once(member_result, member)
        self.assertEqual(len(self.reports()), 1)

    def test_without_commit_revision_is_null_but_the_report_is_saved(self):
        self.build(commit=False)
        result, _ = self.verify("--report")
        self.assertEqual(self.codes(result), [EMPTY_TARGETS])
        self.assert_revision(result, None)
        self.assert_saved_once(result)

    def test_without_report_no_file_is_created(self):
        self.build()
        self.verify()
        self.verify(cwd=self.root / "apps" / "web")
        self.assertFalse(self.reports_dir().exists())
        self.assertFalse(self.reports_dir(self.root / "apps" / "web").exists())


if __name__ == "__main__":
    unittest.main()
