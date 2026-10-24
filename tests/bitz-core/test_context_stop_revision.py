"""単一ワークスペースの`context`の早期に返す結果が、求めた`revision`を返す規則の単体試験（実装の確認事項C45）。

`01_結果・診断・終了コード.md` §2（`revision`の規則）を対象にする。

- `context`の`null`でない`revision`は、40桁の小文字16進数の`commit`と真偽値の`dirty`だけを持つ。
- 単一ワークスペースでGit不在、またはコミットのないリポジトリだけ`revision: null`とする。それ以外は、結果の状態によらず
  `{commit, dirty}`を返す。`context`が成功する場合だけ`revision`を返す、という規則はない。

`context`は、コンテキスト一式を作る前に結果を返す経路を9つ持つ。この試験は、コミットのある単一ワークスペースで
次のそれぞれを作り、`revision`が`{commit, dirty}`になることを確かめる。

1. 設定がない（`SPEC-WORKSPACE-MISSING-001`）
2. 設定の停止（`SPEC-CONFIG-SCHEMA-001`。版の非対応と型の不正）
3. 起点がない（`CTX-ROOT-MISSING-001`）
4. 強い関係の参照切れ（`SPEC-RELATION-MISSING-001`。対象展開は誤りを返さず、関係の検査だけが失敗する）
5. 対象展開の誤り（状態の診断）と強い関係の検査の失敗が重なる（`CTX-STATE-001`と`CTX-RELATION-TYPE-001`）
6. 閉包の上限の超過（`CTX-LIMIT-001`）
7. 完全解決した集合の外の`--expand`（`CTX-PROJECTION-001`）
8. 提示の絶対上限の超過（`CTX-PROJECTION-LIMIT-001`）
9. `--expect-digest`の不一致（`CTX-STALE-001`）

対照として、コミットなし・Git不在・Gitのリポジトリでないときの`null`、成功した`context`の`revision`、複合ワークスペースの失敗を確かめる。
出力が`docs/03.詳細設計/schemas/result.schema.json`に適合し、`PYTHONHASHSEED`を変えても同じ出力になることも確かめる。
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
from bitz import context as context_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"
WRONG_DIGEST = "sha256:" + "0" * 64
PAD_LINE = "この段落は提示の絶対上限を超えるための固定本文であり、意味を持たない。\n"


def _config(extra: str = "", *, schema: str = "1.0", language: str = "ja", workspace_id: str = "solo") -> str:
    return f'schemaVersion: "{schema}"\nlanguage: {language}\nearsAi: "1.0"\nworkspace:\n  id: {workspace_id}\n' + extra


def _req(doc_id: str = "REQ-001", status: str = "approved", requires: tuple[str, ...] = ()) -> str:
    relations = f"relations:\n  requires: [{', '.join(requires)}]\n" if requires else ""
    return (
        f"---\nid: {doc_id}\ntitle: 検査対象\nstatus: {status}\n{relations}---\n\n# {doc_id} 検査対象\n\n"
        f"## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        f"## Verification\n\n未証明。\n"
    )


def _adr(doc_id: str = "ADR-001", status: str = "proposed") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 判断\nstatus: {status}\n---\n\n# {doc_id} 判断\n\n"
        f"## Context\n\n背景。\n\n## Decision\n\n方式を決める。\n\n## Consequences\n\n影響。\n"
    )


def _tech(doc_id: str, refines: str, body: str = "具体化。\n") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 具体化\nstatus: approved\nrelations:\n  refines: [{refines}]\n---\n\n"
        f"# {doc_id} 具体化\n\n## Context\n\n{body}"
    )


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


# 早期に返す経路: 名前 -> (配置するファイル, 引数, 状態, 終了コード, 診断のコード（順序どおり）, `workspace.id`)。
# 診断の順序は結果・診断・終了コード §7に従う。設定がない場合のファイルは`.spec/bitz.yaml`以外である。
_BIG = PAD_LINE * 5300  # 1ファイルは1文書あたりの入力上限を下回り、2件で提示の絶対上限（1 MiB）を超える。
EARLY_RETURNS = {
    "config-missing": (
        {"README.md": "仕様文書のないリポジトリ。\n"}, ("REQ-001",),
        "blocked", 2, ["SPEC-WORKSPACE-MISSING-001"], None),
    "config-schema-version": (
        {".spec/bitz.yaml": _config(schema="9.9")}, ("REQ-001",),
        "blocked", 2, ["SPEC-CONFIG-SCHEMA-001"], "solo"),
    "config-type": (
        {".spec/bitz.yaml": _config(language="5")}, ("REQ-001",),
        "error", 3, ["SPEC-CONFIG-SCHEMA-001"], None),
    "root-missing": (
        {".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()}, ("REQ-404",),
        "failed", 1, ["CTX-ROOT-MISSING-001"], "solo"),
    "relation-missing": (
        {".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req(requires=("REQ-999",))}, ("REQ-001",),
        "failed", 1, ["SPEC-RELATION-MISSING-001"], "solo"),
    "expansion-error-and-relation-type": (
        {".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req(requires=("REQ-002", "ADR-001")),
         ".spec/requirements/REQ-002.md": _req("REQ-002", "draft"), ".spec/decisions/ADR-001.md": _adr()},
        ("REQ-001", "--purpose", "implement"),
        "failed", 1, ["CTX-RELATION-TYPE-001", "CTX-STATE-001"], "solo"),
    "closure-limit": (
        {".spec/bitz.yaml": _config("context:\n  maxDocuments: 1\n"), ".spec/requirements/REQ-001.md": _req(),
         ".spec/technical/TECH-001.md": _tech("TECH-001", "REQ-001")}, ("REQ-001", "--purpose", "verify"),
        "blocked", 2, ["CTX-LIMIT-001"], "solo"),
    "expand-outside": (
        {".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req(),
         ".spec/decisions/ADR-001.md": _adr(status="accepted")},
        ("REQ-001", "--purpose", "verify", "--expand", "ADR-001"),
        "failed", 1, ["CTX-PROJECTION-001"], "solo"),
    "projection-limit": (
        {".spec/bitz.yaml": _config("context:\n  maxDocuments: 100\n  maxBytes: 1048576\n"),
         ".spec/requirements/REQ-001.md": _req(),
         ".spec/technical/TECH-001.md": _tech("TECH-001", "REQ-001"),
         ".spec/technical/TECH-002.md": _tech("TECH-002", "TECH-001", _BIG),
         ".spec/technical/TECH-003.md": _tech("TECH-003", "TECH-002", _BIG)},
        ("REQ-001", "--purpose", "verify", "--detail", "full"),
        "failed", 1, ["CTX-PROJECTION-LIMIT-001"], "solo"),
    "stale-digest": (
        {".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()},
        ("REQ-001", "--purpose", "verify", "--expect-digest", WRONG_DIGEST),
        "blocked", 2, ["CTX-STALE-001"], "solo"),
}


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        self.results: list[dict] = []
        self.env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        # Git不在: 実行ファイルを見つけられない環境。
        self.no_git_env = {**self.env, "PATH": str(Path(tmp.name) / "no-such-bin")}

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def reset(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()

    def place(self, files: dict[str, str]) -> None:
        for rel, content in files.items():
            _write(self.root, rel, content)

    def init_repository(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def commit_all(self) -> str:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")
        return _git(self.root, "rev-parse", "HEAD")

    def context(self, *argv: str, cwd: Path | None = None, env: dict | None = None):
        parsed = parse_argv(["context", *argv, "--format", "json"])
        result, code = context_mod.run(parsed, str(cwd or self.root), env if env is not None else self.env)
        self.results.append(result)
        return result, code

    def codes(self, result) -> list[str]:
        return [d["code"] for d in result["diagnostics"]]

    def assert_revision(self, result, commit: str | None, dirty: bool = False):
        if commit is None:
            self.assertIsNone(result["revision"], result["diagnostics"])
        else:
            # `context`の`revision`は、40桁の小文字16進の`commit`と真偽値の`dirty`だけを持つ（結果・診断・終了コード §2）。
            self.assertEqual(result["revision"], {"commit": commit, "dirty": dirty}, result["diagnostics"])

    def assert_early_return(self, name: str, result, code: int):
        _, _, status, exit_code, codes, workspace_id = EARLY_RETURNS[name]
        self.assertEqual((result["status"], code), (status, exit_code), result["diagnostics"])
        self.assertEqual(self.codes(result), codes)
        self.assertEqual(result["workspace"]["id"], workspace_id)
        self.assertEqual(result["documents"], [])


class EarlyReturnRevisionTests(_Base):
    """コンテキスト一式を作る前に結果を返す9つの経路。コミットがあれば`revision`は`{commit, dirty}`である。"""

    def build(self, name: str, *, commit: bool = True) -> str | None:
        self.reset()
        self.place(EARLY_RETURNS[name][0])
        self.init_repository()
        return self.commit_all() if commit else None

    def test_revision_is_returned_for_every_early_return_with_a_clean_tree(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                head = self.build(name)
                result, code = self.context(*EARLY_RETURNS[name][1])
                self.assert_early_return(name, result, code)
                self.assert_revision(result, head, dirty=False)

    def test_dirty_is_true_with_an_untracked_file(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                head = self.build(name)
                _write(self.root, "notes.md", "未追跡。\n")
                result, code = self.context(*EARLY_RETURNS[name][1])
                self.assert_early_return(name, result, code)
                self.assert_revision(result, head, dirty=True)

    def test_dirty_is_true_with_a_modified_tracked_file(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                head = self.build(name)
                tracked = next(iter(EARLY_RETURNS[name][0]))
                with (self.root / tracked).open("a", encoding="utf-8") as stream:
                    stream.write("\n")
                result, code = self.context(*EARLY_RETURNS[name][1])
                self.assert_early_return(name, result, code)
                self.assert_revision(result, head, dirty=True)

    def test_revision_follows_head_not_the_staged_or_working_state(self):
        # 2つめのコミットを作ると、`commit`はその新しいHEADになる。
        for name in ("root-missing", "relation-missing", "config-schema-version"):
            with self.subTest(early_return=name):
                first = self.build(name)
                _write(self.root, "notes.md", "追加。\n")
                second = self.commit_all()
                self.assertNotEqual(first, second)
                result, _ = self.context(*EARLY_RETURNS[name][1])
                self.assert_revision(result, second, dirty=False)

    def test_without_commit_revision_is_null(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                self.build(name, commit=False)
                result, code = self.context(*EARLY_RETURNS[name][1])
                self.assert_early_return(name, result, code)
                self.assert_revision(result, None)

    def test_git_absent_revision_is_null(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                self.build(name)  # `.git`はあるが、Gitの実行ファイルを見つけられない環境で実行する。
                result, code = self.context(*EARLY_RETURNS[name][1], env=self.no_git_env)
                self.assert_early_return(name, result, code)
                self.assert_revision(result, None)

    def test_not_a_repository_revision_is_null(self):
        for name in EARLY_RETURNS:
            with self.subTest(early_return=name):
                self.reset()
                self.place(EARLY_RETURNS[name][0])
                result, code = self.context(*EARLY_RETURNS[name][1])
                self.assert_early_return(name, result, code)
                self.assert_revision(result, None)

    def test_each_early_return_is_a_distinct_failure_in_the_same_repository(self):
        # 9つの経路が互いに別の診断であり、同じ入力の取り違えで試験が空振りしていないことを確かめる。
        reached = set()
        for name in EARLY_RETURNS:
            self.build(name)
            result, _ = self.context(*EARLY_RETURNS[name][1])
            reached.add(tuple(self.codes(result)))
        self.assertEqual(reached, {tuple(row[4]) for row in EARLY_RETURNS.values()})
        self.assertEqual(len(reached), 9)


class ControlTests(_Base):
    """対照: 修正の前から正しい経路は、変わらない。"""

    def test_successful_context_returns_commit_and_dirty(self):
        self.place({".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()})
        self.init_repository()
        head = self.commit_all()
        result, code = self.context("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assert_revision(result, head, dirty=False)
        _write(self.root, "notes.md", "未追跡。\n")
        result, _ = self.context("REQ-001")
        self.assert_revision(result, head, dirty=True)

    def test_successful_context_without_commit_is_null(self):
        self.place({".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()})
        self.init_repository()
        result, _ = self.context("REQ-001")
        self.assert_revision(result, None)

    def test_early_return_and_success_share_the_revision_of_the_same_tree(self):
        self.place({".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()})
        self.init_repository()
        self.commit_all()
        ok, _ = self.context("REQ-001")
        failed, _ = self.context("REQ-404")
        self.assertEqual(ok["status"], "passed")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["revision"], ok["revision"])

    def test_the_result_carries_no_other_revision_field(self):
        self.place({".spec/bitz.yaml": _config(), ".spec/requirements/REQ-001.md": _req()})
        self.init_repository()
        self.commit_all()
        result, _ = self.context("REQ-404")
        self.assertEqual(sorted(result["revision"]), ["commit", "dirty"])
        self.assertRegex(result["revision"]["commit"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(result["revision"]["dirty"], bool)


class MultiWorkspaceControlTests(_Base):
    """複合ワークスペースの失敗は、修正の前から`revision`を返している。単一ワークスペースの修正で変わらない。"""

    ROOT = (
        'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
        "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
    )

    def build(self, *, commit: bool = True) -> str | None:
        self.place({
            ".spec/bitz.yaml": self.ROOT,
            "apps/web/.spec/bitz.yaml": _config(workspace_id="web"),
            "apps/web/.spec/requirements/REQ-001.md": _req(),
        })
        self.init_repository()
        return self.commit_all() if commit else None

    def test_root_missing_returns_revision(self):
        head = self.build()
        result, code = self.context("web::REQ-404")
        self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
        self.assertEqual(self.codes(result), ["CTX-ROOT-MISSING-001"])
        self.assertIn("workspaces", result["resolution"])  # 複合ワークスペースの形で返す経路（`_multi_augment`）
        self.assert_revision(result, head)

    def test_stale_digest_returns_revision(self):
        head = self.build()
        result, code = self.context("web::REQ-001", "--purpose", "verify", "--expect-digest", WRONG_DIGEST)
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(self.codes(result), ["CTX-STALE-001"])
        self.assert_revision(result, head)

    def test_without_commit_revision_is_null(self):
        self.build(commit=False)
        result, _ = self.context("web::REQ-404")
        self.assert_revision(result, None)


class DeterminismTests(_Base):
    def cli(self, cwd: Path, seed: str, *argv: str) -> dict:
        source = Path(bitz.__file__).resolve().parents[1]  # 試験対象のCoreのsrc（PYTHONPATHで差し替えた場合も追従する）
        env = {**self.env, "PYTHONHASHSEED": seed, "PYTHONPATH": str(source)}
        proc = subprocess.run([sys.executable, "-m", "bitz.cli", "context", "--format", "json", *argv],
                              cwd=cwd, env=env, capture_output=True, text=True)
        result = json.loads(proc.stdout)
        result["durationMs"] = 0
        return {"returncode": proc.returncode, "result": result}

    def test_json_output_is_identical_for_any_hash_seed(self):
        for name in EARLY_RETURNS:
            if name == "projection-limit":
                continue  # 入力が大きい。ほかの8つの経路と同じ`_empty_bundle`を通るので、時間を節約する。
            with self.subTest(early_return=name):
                self.reset()
                self.place(EARLY_RETURNS[name][0])
                self.init_repository()
                head = self.commit_all()
                outputs = [self.cli(self.root, seed, *EARLY_RETURNS[name][1]) for seed in ("0", "1", "4242")]
                first = outputs[0]
                self.assertEqual(first["returncode"], EARLY_RETURNS[name][3])
                self.assertEqual(first["result"]["revision"], {"commit": head, "dirty": False})
                for other in outputs[1:]:
                    self.assertEqual(other, first)
                self.results.append(first["result"])


if __name__ == "__main__":
    unittest.main()
