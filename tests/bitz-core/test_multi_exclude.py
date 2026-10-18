"""複合ワークスペースの除外（`multiWorkspace.exclude`）と入れ子の複合ワークスペースの単体試験（ADR-064）。

`05_複合ワークスペース仕様.md` §2・§2.1・§3・§5.1・§7・§8・§10・§11、`01_ワークスペース・設定仕様.md` §5、
`01_結果・診断・終了コード.md` §2 を対象にする。

- 設定の検証: 管理者が承認した7件の文言（`SPEC-MULTI-CONFIG-001`の6件と`SPEC-MULTI-PATH-001`の1件）の各条件、
  メンバーと除外の重なり、実在しない除外、`exclude`が未知のキーの警告にならないこと。
- 除外の効果: Gitが認識する設定の比較（現在、`HEAD`、基準版のスナップショットはそれぞれ自身の除外を使う）と、
  単独操作の選択した設定の照合が、除外した範囲の中の設定を対象にしない。
- §2.1の決定: 除外した範囲の中の単一ワークスペースと入れ子の複合ワークスペース（再帰を含む）、外側の除外が不正、外側のほかの不備、
  外側の設定が読めない、Gitがない、外側が複合ワークスペースを宣言しない場合。
- 入れ子の複合ワークスペースの結果のパスと、Gitが返すパスの写像（入れ子のルートの外の変更を比較に含めない）。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合すること、`PYTHONHASHSEED`を変えても出力が同じこと。
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
from bitz import config as config_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import gitutil
from bitz import multiws
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.errors import CliArgError

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'

# 管理者が承認した7件の文言（ADR-064の8）。実装の定数とは別に、この試験で一字ずつ固定する。
MSG_EXCLUDE_TYPE = "設定キーmultiWorkspace.excludeは文字列の配列で指定してください"
MSG_EXCLUDE_COUNT = "設定キーmultiWorkspace.excludeは100件以下で指定してください"
MSG_EXCLUDE_INVALID = "除外のパスの形式が不正です"
MSG_EXCLUDE_DUPLICATE = "除外のパスが重複しています"
MSG_EXCLUDE_NESTED = "除外のパスが別の除外のパスの配下にあります"
MSG_EXCLUDE_SPEC = "除外のパスに.specが含まれています"
MSG_PATH_EXCLUDED = "メンバーのパスが除外した範囲にあります"

UNREGISTERED_SELECTED = "選択した設定ファイルがカタログに登録されていません"
UNREGISTERED_GIT = "Gitが認識する設定ファイルがカタログに登録されていません"

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


# `verify`が実行できるよう、どのワークスペースにも成功するコマンドを置く。
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'


def _tech(number: int) -> str:
    return (
        f"---\nid: TECH-001\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [REQ-{number:03d}:AC-01]\n"
        f"tests:\n  - path: tests/t.py\n    covers: [REQ-{number:03d}:AC-01]\n    command: t\n---\n\n"
        "# TECH-001 TECH\n\n## Context\n\n本文。\n"
    )


def _req(number: int) -> str:
    return (
        f"---\nid: REQ-{number:03d}\ntitle: REQ\nstatus: approved\n---\n\n# REQ-{number:03d} REQ\n\n## Intent\n\n意図。\n\n"
        f"## Acceptance Criteria\n\n- [REQ-{number:03d}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _root_yaml(
    ws_id: str, members: list[tuple[str, str]], exclude: list[str] | str | None = None, *, extra: str = ""
) -> str:
    """ルートワークスペースの設定。``exclude``が文字列ならそのまま``exclude:``の値の行として置く。"""

    text = CONFIG + f"workspace:\n  id: {ws_id}\nmultiWorkspace:\n  members:\n"
    for mid, mpath in members:
        text += f"    - id: {mid}\n      path: {mpath}\n"
    if exclude is not None:
        if isinstance(exclude, str):
            text += f"  exclude: {exclude}\n"
        elif not exclude:
            text += "  exclude: []\n"
        else:
            text += "  exclude:\n" + "".join(f"    - {json.dumps(e, ensure_ascii=False)}\n" for e in exclude)
    return text + VERIFY + extra


def _member_yaml(ws_id: str) -> str:
    return CONFIG + f"workspace:\n  id: {ws_id}\n" + VERIFY


def _write_docs(root: Path, base: str, number: int) -> None:
    """``base``（ワークスペースのルートの相対パス。ルートは空）に、REQと、そのREQを検証するTECHとテストファイルを置く。"""

    prefix = f"{base}/" if base else ""
    _write(root, f"{prefix}.spec/requirements/REQ-{number:03d}.md", _req(number))
    _write(root, f"{prefix}.spec/technical/TECH-001.md", _tech(number))
    _write(root, f"{prefix}tests/t.py", "x\n")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    ).stdout.strip()


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


def _without_durations(value):
    """実行時間（`durationMs`）は実行ごとに変わるため、比較から除く。"""

    if isinstance(value, dict):
        return {k: _without_durations(v) for k, v in value.items() if k != "durationMs"}
    if isinstance(value, list):
        return [_without_durations(v) for v in value]
    return value


class _Base(unittest.TestCase):
    """外側の複合ワークスペース`platform`（メンバー`web`）と、除外した`fixtures/`の下の検証用のデータを持つリポジトリ。

    ```
    .spec/bitz.yaml                       platform（members: web、exclude: fixtures, apps/web/vectors）
    apps/web/.spec/bitz.yaml              web
    apps/web/vectors/.spec/bitz.yaml      メンバーの配下の除外にある単一ワークスペース（id: vec）
    fixtures/single/.spec/bitz.yaml       除外した範囲の中の単一ワークスペース（id: fsingle）
    fixtures/nested/.spec/bitz.yaml       入れ子の複合ワークスペース（id: nest、members: a、b、exclude: vendor）
    fixtures/nested/{a,b}/.spec/bitz.yaml nest のメンバー
    fixtures/nested/vendor/single/...     nest の除外の中の単一ワークスペース（id: vsingle）
    fixtures/nested/vendor/inner/...      nest の除外の中の入れ子の複合ワークスペース（id: inner、member: leaf）
    fixtures/stray/.spec/bitz.yaml        どのカタログにもない設定（除外した範囲の中）
    ```
    """

    use_git = True
    outer_exclude: list[str] | str | None = ["fixtures", "apps/web/vectors"]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.env = dict(os.environ)
        self.results: list[dict] = []
        if self.use_git:
            _git(self.root, "init", "-q", "--initial-branch=main")
            _git(self.root, "config", "user.email", "t@t")
            _git(self.root, "config", "user.name", "t")
        self.build()
        if self.use_git:
            _git(self.root, "add", ".")
            _git(self.root, "commit", "-q", "-m", "base")

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web")], self.outer_exclude))
        _write_docs(r, "", 1)
        _write(r, "apps/web/.spec/bitz.yaml", _member_yaml("web"))
        _write_docs(r, "apps/web", 50)
        _write(r, "apps/web/vectors/.spec/bitz.yaml", _member_yaml("vec"))
        _write_docs(r, "apps/web/vectors", 70)
        _write(r, "fixtures/single/.spec/bitz.yaml", _member_yaml("fsingle"))
        _write_docs(r, "fixtures/single", 60)
        _write(r, "fixtures/single/sub/keep.txt", "x\n")
        _write(r, "fixtures/stray/.spec/bitz.yaml", _member_yaml("stray"))
        _write_docs(r, "fixtures/stray", 80)
        _write(r, "fixtures/nested/.spec/bitz.yaml", _root_yaml("nest", [("a", "a"), ("b", "b")], ["vendor"]))
        _write_docs(r, "fixtures/nested", 100)
        _write(r, "fixtures/nested/a/.spec/bitz.yaml", _member_yaml("a"))
        _write_docs(r, "fixtures/nested/a", 110)
        _write(r, "fixtures/nested/b/.spec/bitz.yaml", _member_yaml("b"))
        _write_docs(r, "fixtures/nested/b", 120)
        _write(r, "fixtures/nested/vendor/single/.spec/bitz.yaml", _member_yaml("vsingle"))
        _write_docs(r, "fixtures/nested/vendor/single", 130)
        _write(r, "fixtures/nested/vendor/inner/.spec/bitz.yaml", _root_yaml("inner", [("leaf", "leaf")]))
        _write_docs(r, "fixtures/nested/vendor/inner", 140)
        _write(r, "fixtures/nested/vendor/inner/leaf/.spec/bitz.yaml", _member_yaml("leaf"))
        _write_docs(r, "fixtures/nested/vendor/inner/leaf", 150)

    # --- 操作の実行 ----------------------------------------------------------------
    def _run(self, module, name: str, cwd: Path, argv: tuple[str, ...], env=None):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), env if env is not None else self.env)
        self.results.append(result)
        return result, code

    def check(self, cwd, *argv, env=None):
        return self._run(check_mod, "check", Path(cwd), argv, env)

    def context(self, cwd, *argv, env=None):
        return self._run(context_mod, "context", Path(cwd), argv, env)

    def verify(self, cwd, *argv, env=None):
        return self._run(verify_mod, "verify", Path(cwd), argv, env)

    def doctor(self, cwd, *argv, env=None):
        return self._run(doctor_mod, "doctor", Path(cwd), argv, env)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def assert_passed(self, result, code):
        self.assertIn(result["status"], ("passed", "passed_with_warnings"), result["diagnostics"])
        self.assertEqual(code, 0)

    def precheck_diagnostics(self, rel: str = ".") -> list[dict]:
        git = gitutil.detect_git(str(self.root), self.env)
        pre = multiws.precheck(str(self.path(rel)), git, self.env, compare_git_configs=False)
        return [d.to_dict() for d in pre.diagnostics]

    def rewrite_outer(self, exclude, members=(("web", "apps/web"),)) -> None:
        _write(self.root, ".spec/bitz.yaml", _root_yaml("platform", list(members), exclude))


class ExcludeConfigValidationTests(_Base):
    """設定の検証（`SPEC-MULTI-CONFIG-001`／`SPEC-MULTI-PATH-001`、`failed`）。7件の文言は一字も変えない。"""

    def assert_single_diag(self, exclude, message, *, code="SPEC-MULTI-CONFIG-001", key="multiWorkspace.exclude"):
        self.rewrite_outer(exclude)
        diagnostics = self.precheck_diagnostics()
        self.assertEqual(len(diagnostics), 1, (exclude, diagnostics))
        d = diagnostics[0]
        self.assertEqual((d["code"], d["severity"], d["resultStatus"], d["summary"]), (code, "error", "failed", message))
        self.assertEqual(d["source"], {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": key})

    def test_exclude_must_be_an_array_of_strings(self):
        for exclude in ("fixtures", "{a: b}", "null", "[1]", "[fixtures, 3]", "[[a]]", "true"):
            with self.subTest(exclude=exclude):
                self.assert_single_diag(exclude, MSG_EXCLUDE_TYPE)

    def test_exclude_count_limit(self):
        self.assert_single_diag([f"d{i}" for i in range(101)], MSG_EXCLUDE_COUNT)
        self.rewrite_outer([f"d{i}" for i in range(100)])
        self.assertEqual(self.precheck_diagnostics(), [])
        self.rewrite_outer([])
        self.assertEqual(self.precheck_diagnostics(), [])

    def test_exclude_path_lexical_rules_are_the_same_as_member_paths(self):
        for bad in ("/abs", ".", "", "a/", "../x", "a/../b", "a//b", "./a", "a/*", "a?", "[a]", "a\u0000b"):
            with self.subTest(path=bad):
                self.assert_single_diag([bad], MSG_EXCLUDE_INVALID)

    def test_exclude_duplicate(self):
        self.assert_single_diag(["a", "a"], MSG_EXCLUDE_DUPLICATE)
        # Unicodeの正規化形だけが異なるパスも重複とする（NFCで比べる）。
        self.assert_single_diag(["é", "é"], MSG_EXCLUDE_DUPLICATE)

    def test_exclude_nested_in_another_exclude(self):
        self.assert_single_diag(["a", "a/b"], MSG_EXCLUDE_NESTED)
        self.assert_single_diag(["a/b", "a"], MSG_EXCLUDE_NESTED)
        # ディレクトリの単位で比べる。`a`と`ab`は入れ子ではない。
        self.rewrite_outer(["a", "ab", "a2/b"])
        self.assertEqual(self.precheck_diagnostics(), [])

    def test_exclude_must_not_contain_a_spec_segment(self):
        for bad in (".spec", "x/.spec", ".spec/y", "x/.spec/y"):
            with self.subTest(path=bad):
                self.assert_single_diag([bad], MSG_EXCLUDE_SPEC)
        # `.spec`を部分文字列に含むだけのセグメントは妥当。
        self.rewrite_outer(["x.spec", ".specs", "my.spec/y"])
        self.assertEqual(self.precheck_diagnostics(), [])

    def test_member_path_inside_an_excluded_area(self):
        for exclude in ("apps/web", "apps", "apps/web/".rstrip("/")):
            with self.subTest(exclude=exclude):
                self.assert_single_diag(
                    [exclude], MSG_PATH_EXCLUDED, code="SPEC-MULTI-PATH-001", key="multiWorkspace.members"
                )

    def test_exclude_below_a_member_is_allowed(self):
        self.rewrite_outer(["apps/web/vectors", "apps/web/deep/er"])
        self.assertEqual(self.precheck_diagnostics(), [])

    def test_nonexistent_exclude_is_accepted(self):
        self.rewrite_outer(["does/not/exist", "generated"])
        self.assertEqual(self.precheck_diagnostics(), [])

    def test_each_independent_cause_gets_its_own_diagnostic(self):
        self.rewrite_outer(["", ".spec", "a", "a", "b", "b/c"])
        summaries = sorted(d["summary"] for d in self.precheck_diagnostics())
        self.assertEqual(
            summaries,
            sorted([MSG_EXCLUDE_INVALID, MSG_EXCLUDE_SPEC, MSG_EXCLUDE_DUPLICATE, MSG_EXCLUDE_NESTED]),
        )

    def test_exclude_is_not_an_unknown_key(self):
        outcome = config_mod.read_config(str(self.path(".spec/bitz.yaml")))
        self.assertFalse(outcome.stop)
        self.assertEqual(outcome.warnings, [])
        result, code = self.doctor(self.root)
        self.assertNotIn("SPEC-CONFIG-UNKNOWN-001", [d["code"] for d in result["diagnostics"]])

    def test_all_workspaces_operations_stop_on_invalid_exclude(self):
        self.rewrite_outer(["a", "a"])
        for name, argv in (("check", ("--all-workspaces",)), ("verify", ("--all-workspaces",)), ("doctor", ("--all-workspaces",))):
            with self.subTest(operation=name):
                result, code = getattr(self, name)(self.root, *argv)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(result["workspaces"], [])
                self.assertEqual([d["summary"] for d in result["diagnostics"]], [MSG_EXCLUDE_DUPLICATE])


class ExcludeEffectOnGitComparisonTests(_Base):
    """Gitが認識する設定の比較と、単独操作の選択した設定の照合が、除外した範囲の中の設定を対象にしない（§8）。"""

    def test_unregistered_config_in_excluded_area_does_not_stop_all_workspaces(self):
        for name in ("check", "verify", "doctor"):
            with self.subTest(operation=name):
                result, code = getattr(self, name)(self.root, "--all-workspaces")
                self.assert_passed(result, code)
                self.assertEqual([w["id"] for w in result["workspaces"]], ["platform", "web"])
                self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})

    def test_all_workspaces_from_a_member_directory_is_not_stopped_either(self):
        result, code = self.check(self.path("apps/web"), "--all-workspaces")
        self.assert_passed(result, code)

    def test_single_operations_are_not_stopped(self):
        # 単独の`doctor`は`HEAD`と現在のスナップショットのGitが認識する設定も比べる。
        result, code = self.doctor(self.root)
        self.assert_passed(result, code)
        result, code = self.check(self.root, "--full")
        self.assert_passed(result, code)
        result, code = self.verify(self.root)
        self.assert_passed(result, code)

    def test_unregistered_config_outside_the_excluded_area_still_stops(self):
        _write(self.root, "tools/x/.spec/bitz.yaml", _member_yaml("x"))
        result, code = self.doctor(self.root, "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(
            [(d["code"], d["summary"], d["source"]["path"]) for d in result["diagnostics"]],
            [("SPEC-MULTI-UNREGISTERED-001", UNREGISTERED_GIT, "tools/x/.spec/bitz.yaml")],
        )

    def test_exclusion_is_by_directory_unit(self):
        # `fixtures2`は`fixtures`の配下ではない。
        _write(self.root, "fixtures2/.spec/bitz.yaml", _member_yaml("f2"))
        result, _code = self.doctor(self.root, "--all-workspaces")
        self.assertEqual([d["source"]["path"] for d in result["diagnostics"]], ["fixtures2/.spec/bitz.yaml"])

    def test_exclusion_compares_case_sensitively(self):
        _write(self.root, "Fixtures/x/.spec/bitz.yaml", _member_yaml("fx"))
        result, _code = self.doctor(self.root, "--all-workspaces")
        self.assertEqual([d["source"]["path"] for d in result["diagnostics"]], ["Fixtures/x/.spec/bitz.yaml"])

    def test_untracked_config_in_excluded_area_is_ignored_too(self):
        _write(self.root, "fixtures/new/.spec/bitz.yaml", _member_yaml("new"))
        result, code = self.doctor(self.root, "--all-workspaces")
        self.assert_passed(result, code)

    def test_exclude_below_a_member_ignores_the_configs_there(self):
        _write(self.root, "apps/web/vectors/more/.spec/bitz.yaml", _member_yaml("more"))
        result, code = self.check(self.root, "--all-workspaces")
        self.assert_passed(result, code)

    def test_ownership_boundary_is_not_changed_by_exclusion(self):
        # 除外した範囲の位置は、その位置を所有するワークスペース（ここでは`platform`）が`implements`として所有できる。
        _write(
            self.root,
            ".spec/technical/TECH-001.md",
            "---\nid: TECH-001\ntitle: T\nstatus: draft\nrelations:\n  refines:\n    - REQ-001:AC-01\n"
            "implements:\n  - fixtures/stray/data.txt\n---\n\n# TECH-001 T\n",
        )
        _write(self.root, "fixtures/stray/data.txt", "x\n")
        result, code = self.check(self.root, "--all-workspaces")
        self.assertNotIn("SPEC-MULTI-OWNERSHIP-001", [d["code"] for w in result["workspaces"] for d in w["diagnostics"]])

    # --- スナップショットごとの除外 ----------------------------------------------------
    def commit_all(self, message: str) -> str:
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", message)
        return _git(self.root, "rev-parse", "HEAD")

    def test_base_snapshot_uses_its_own_exclude(self):
        # 基準版は除外を持たず、`fixtures/`の設定がカタログにない。現在版は除外を加えている。
        self.rewrite_outer(None)
        base = self.commit_all("without exclude")
        self.rewrite_outer(["fixtures", "apps/web/vectors"])
        self.commit_all("with exclude")
        result, code = self.check(self.root, "--all-workspaces", "--base", base)
        self.assertEqual((result["status"], code), ("blocked", 2))
        paths = [d["source"]["path"] for d in result["diagnostics"]]
        self.assertTrue(paths and all(d["code"] == "SPEC-MULTI-UNREGISTERED-001" for d in result["diagnostics"]))
        self.assertIn("fixtures/stray/.spec/bitz.yaml", paths)
        # 現在版の除外を基準版へ適用しない。基準版の除外が現在版と同じなら通る。
        result, code = self.check(self.root, "--all-workspaces", "--base", "HEAD")
        self.assert_passed(result, code)

    def test_head_snapshot_of_single_doctor_uses_its_own_exclude(self):
        # `HEAD`には除外がなく、作業ツリーで除外を加えた。単独の`doctor`は`HEAD`のスナップショットでも未登録の設定を検出する。
        self.rewrite_outer(None)
        self.commit_all("without exclude")
        self.rewrite_outer(["fixtures", "apps/web/vectors"])
        result, code = self.doctor(self.root)
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertTrue(all(d["code"] == "SPEC-MULTI-UNREGISTERED-001" for d in result["diagnostics"]))
        # 単独の`check`は`HEAD`のスナップショットのGitが認識する設定を比べないため、止まらない。
        result, code = self.check(self.root, "--full")
        self.assert_passed(result, code)

    def test_base_snapshot_with_exclude_ignores_configs_in_it(self):
        # 基準版が除外を持ち、現在版が除外を外した場合、現在版で未登録になる。基準版側の除外は現在版へ適用しない。
        base = self.commit_all("with exclude")
        self.rewrite_outer(None)
        result, code = self.check(self.root, "--all-workspaces", "--base", base)
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertIn("fixtures/stray/.spec/bitz.yaml", [d["source"]["path"] for d in result["diagnostics"]])

    def test_base_snapshot_with_invalid_exclude_excludes_nothing(self):
        # 妥当でない除外は何も除外しない（信用できない除外では判定しない。ADR-064の3）。
        self.rewrite_outer(["fixtures", "fixtures"])
        base = self.commit_all("invalid exclude")
        self.rewrite_outer(["fixtures", "apps/web/vectors"])
        result, _code = self.check(self.root, "--all-workspaces", "--base", base)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("fixtures/stray/.spec/bitz.yaml", [d["source"]["path"] for d in result["diagnostics"]])


class SingleWorkspaceInExcludedAreaTests(_Base):
    """除外した範囲の中に`multiWorkspace`を宣言した設定がなければ、最も近い設定を単一ワークスペースとして使う（§2.1の2.）。"""

    def test_single_operations_run_as_a_single_workspace(self):
        cwd = self.path("fixtures/single")
        result, code = self.check(cwd, "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        self.assertEqual(result["checkedDocumentCount"], 2)
        result, code = self.doctor(cwd)
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        self.assertNotIn("catalog", [c["name"] for c in result["checks"]])
        result, code = self.verify(cwd)
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        result, code = self.context(cwd, "REQ-060")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        self.assertNotIn("workspaces", result["resolution"])
        self.assertEqual([d["id"] for d in result["documents"]], ["REQ-060", "TECH-001"])

    def test_unregistered_config_in_the_excluded_area_does_not_stop_single_operations(self):
        for name, argv in (("check", ("--full",)), ("doctor", ()), ("verify", ())):
            with self.subTest(operation=name):
                result, code = getattr(self, name)(self.path("fixtures/stray"), *argv)
                self.assert_passed(result, code)
                self.assertEqual(result["workspace"]["id"], "stray")

    def test_start_below_the_nearest_config_in_the_excluded_area(self):
        result, code = self.check(self.path("fixtures/single/sub"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})

    def test_all_workspaces_is_an_argument_error(self):
        for name in ("check", "verify", "doctor"):
            for start in ("fixtures/single", "fixtures/single/sub", "fixtures/stray"):
                with self.subTest(operation=name, start=start):
                    with self.assertRaises(CliArgError):
                        getattr(self, name)(self.path(start), "--all-workspaces")

    def test_all_workspaces_exit_code_is_four_through_the_cli(self):
        proc = self.run_cli(self.path("fixtures/single"), "check", "--all-workspaces", "--format", "json")
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_workspace_option_follows_the_single_workspace_rule(self):
        result, code = self.check(self.path("fixtures/single"), "--full", "--workspace", "fsingle")
        self.assert_passed(result, code)
        with self.assertRaises(CliArgError):
            self.check(self.path("fixtures/single"), "--full", "--workspace", "platform")

    def test_config_in_a_member_exclude_is_a_single_workspace(self):
        result, code = self.check(self.path("apps/web/vectors"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "vec", "path": "."})
        with self.assertRaises(CliArgError):
            self.doctor(self.path("apps/web/vectors"), "--all-workspaces")

    def test_the_nearest_config_is_used_when_several_are_on_the_path(self):
        _write(self.root, "fixtures/single/sub/deep/.spec/bitz.yaml", _member_yaml("deep"))
        result, code = self.check(self.path("fixtures/single/sub/deep"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "deep", "path": "."})

    def test_outer_failures_other_than_exclude_do_not_stop_the_excluded_area(self):
        # 外側のメンバーの設定の不在（`SPEC-MULTI-MEMBER-001`）と、別の場所の未登録の設定は、除外した範囲の操作を止めない。
        os.remove(self.path("apps/web/.spec/bitz.yaml"))
        _write(self.root, "tools/x/.spec/bitz.yaml", _member_yaml("x"))
        outer, outer_code = self.check(self.root, "--full")
        self.assertEqual((outer["status"], outer_code), ("failed", 1))
        for name, argv in (("check", ("--full",)), ("doctor", ()), ("verify", ()), ("context", ("REQ-060",))):
            with self.subTest(operation=name):
                result, code = getattr(self, name)(self.path("fixtures/single"), *argv)
                self.assert_passed(result, code)
                self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})

    def test_unreadable_outer_config_means_single_workspace_discovery(self):
        # 外側の設定の型が不正で読めない（ADR-063の決定4）。除外を決めず、最も近い設定を使う単一の探索になる。
        _write(self.root, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web")], ["fixtures"]) + "context: 5\n")
        result, code = self.check(self.path("fixtures/single"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        # 全体操作は、ルートの候補を発見したうえで、設定の不適合を結果として返す。
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual(result["workspaces"], [])
        self.assertEqual(result["diagnostics"][0]["code"], "SPEC-CONFIG-SCHEMA-001")

    def test_without_a_config_on_the_path_the_outer_rules_apply(self):
        # `fixtures/single/sub`は除外した範囲にあるが、`fixtures`から`sub`までの経路の上に設定がない場合を作る。
        os.remove(self.path("fixtures/single/.spec/bitz.yaml"))
        _git(self.root, "rm", "-q", "-r", "--cached", "fixtures/single/.spec")
        shutil.rmtree(self.path("fixtures/single/.spec"))
        _write(self.root, "tools/x/.spec/bitz.yaml", _member_yaml("x"))
        # 最も近い設定は外側のルートになり、外側の全体事前検査が行われる（単独の`doctor`は別の場所の未登録の設定で止まる）。
        result, code = self.doctor(self.path("fixtures/single/sub"))
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-UNREGISTERED-001"])
        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
        # 外側の全体操作になる。
        result, _code = self.check(self.path("fixtures/single/sub"), "--all-workspaces")
        self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})

    def test_without_git_the_excluded_area_is_not_applied(self):
        no_git = {**self.env, "PATH": os.devnull}
        # Gitがなければ、ADR-063のとおり最も近い設定で判定する。単一ワークスペースの設定は単一として動く。
        result, code = self.check(self.path("fixtures/single"), "--full", env=no_git)
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "fsingle", "path": "."})
        # `multiWorkspace`を宣言した最も近い設定は、Gitを確定できず`SPEC-MULTI-GIT-001`で止まる（入れ子の複合ワークスペースにはしない）。
        result, code = self.check(self.path("fixtures/nested"), "--full", env=no_git)
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])

    def run_cli(self, cwd: Path, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "bitz.cli", *argv], cwd=cwd, env={**self.env, "PYTHONPATH": os.pathsep.join(sys.path)},
            capture_output=True, text=True,
        )


class OuterExcludeUntrustedTests(_Base):
    """外側の除外が妥当でない、または版が非対応のときは、除外した範囲の中でも外側の規則で止まる（ADR-064の3）。"""

    def test_invalid_exclude_stops_inside_the_excluded_area(self):
        self.rewrite_outer(["fixtures", "fixtures"])
        for start in ("fixtures/single", "fixtures/nested", "fixtures/nested/a"):
            for name, argv in (("check", ("--full",)), ("doctor", ()), ("verify", ()), ("context", ("REQ-060",))):
                with self.subTest(operation=name, start=start):
                    result, code = getattr(self, name)(self.path(start), *argv)
                    self.assertEqual((result["status"], code), ("failed", 1))
                    self.assertEqual(
                        [(d["code"], d["summary"]) for d in result["diagnostics"]],
                        [("SPEC-MULTI-CONFIG-001", MSG_EXCLUDE_DUPLICATE)],
                    )

    def test_member_overlap_stops_inside_the_excluded_area(self):
        self.rewrite_outer(["fixtures", "apps"])
        result, code = self.check(self.path("fixtures/single"), "--full")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([d["summary"] for d in result["diagnostics"]], [MSG_PATH_EXCLUDED])

    def test_unsupported_version_stops_inside_the_excluded_area(self):
        text = _root_yaml("platform", [("web", "apps/web")], ["fixtures"]).replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')
        _write(self.root, ".spec/bitz.yaml", text)
        result, code = self.check(self.path("fixtures/single"), "--full")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-CONFIG-SCHEMA-001"])
        # 版が非対応でも`multiWorkspace`を宣言していれば、外側は複合ワークスペースであり、単一の探索へ落ちない。
        result, code = self.doctor(self.path("fixtures/nested"))
        self.assertEqual(result["status"], "blocked")

    def test_outer_that_does_not_declare_multi_workspace_ignores_nested_declarations(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\n")
        # 外側が`multiWorkspace`を宣言しないとき、その下の`multiWorkspace`の設定を複合ワークスペースのルートにしない。
        result, code = self.check(self.path("fixtures/nested"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "nest", "path": "."})
        self.assertEqual(result["checkedDocumentCount"], 2)

    def test_outer_rules_when_start_is_outside_every_excluded_area(self):
        # 除外した範囲の外では、外側の規則のまま（ADR-063）。
        _write(self.root, "tools/x/.spec/bitz.yaml", _member_yaml("x"))
        result, code = self.check(self.path("tools/x"), "--full")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["workspace"], {"id": None, "path": "tools/x"})
        self.assertEqual(result["diagnostics"][0]["summary"], UNREGISTERED_SELECTED)


class OuterMultiWorkspaceInvalidTests(_Base):
    """外側の`multiWorkspace`が設定不適合（`SPEC-MULTI-CONFIG-001`）なら、除外を信用せず決めない（ADR-064の3、§2.1）。"""

    def write_outer_mw(self, mw_body: str) -> None:
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + mw_body)
        _write(self.root, "cases/s/.spec/bitz.yaml", _member_yaml("cs"))
        _write_docs(self.root, "cases/s", 90)

    def assert_stops_on_outer(self, message: str, key: str | None = None):
        for name, argv in (("check", ("--full",)), ("doctor", ()), ("verify", ()), ("context", ("REQ-090",))):
            with self.subTest(operation=name):
                result, code = getattr(self, name)(self.path("cases/s"), *argv)
                self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
                self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-CONFIG-001"])
                self.assertEqual(result["diagnostics"][0]["summary"], message)
                if key is not None:
                    self.assertEqual(result["diagnostics"][0]["source"].get("key"), key)

    def test_members_absent_with_only_exclude(self):
        self.write_outer_mw("  exclude:\n    - cases\n")
        self.assert_stops_on_outer("設定キーmultiWorkspace.membersは1件以上指定してください", "multiWorkspace.members")

    def test_members_not_an_array(self):
        self.write_outer_mw("  members: 3\n  exclude:\n    - cases\n")
        self.assert_stops_on_outer("設定キーmultiWorkspace.membersは配列で指定してください", "multiWorkspace.members")

    def test_members_empty(self):
        self.write_outer_mw("  members: []\n  exclude:\n    - cases\n")
        self.assert_stops_on_outer("設定キーmultiWorkspace.membersは1件以上指定してください")

    def test_members_entry_not_a_map(self):
        self.write_outer_mw("  members:\n    - 3\n  exclude:\n    - cases\n")
        self.assert_stops_on_outer("設定キーmultiWorkspace.membersの要素はマッピングで指定してください")

    def test_max_members_out_of_range(self):
        for value in ("0", "101", "x"):
            with self.subTest(maxMembers=value):
                self.write_outer_mw(
                    f"  maxMembers: {value}\n  members:\n    - id: web\n      path: apps/web\n  exclude:\n    - cases\n"
                )
                self.assert_stops_on_outer("設定キーmultiWorkspace.maxMembersは1〜100の整数で指定してください")

    def test_multi_workspace_not_a_map(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace: 3\n")
        _write(self.root, "cases/s/.spec/bitz.yaml", _member_yaml("cs"))
        _write_docs(self.root, "cases/s", 90)
        self.assert_stops_on_outer("設定キーmultiWorkspaceはマッピングで指定してください")

    def test_path_defect_of_a_member_is_another_defect_and_exclude_is_trusted(self):
        # メンバーのパスの字句の不正（`SPEC-MULTI-PATH-001`）は「ほかの不備」。除外は信用し、除外の中は単一ワークスペースとして動く。
        self.write_outer_mw("  members:\n    - id: web\n      path: ../web\n  exclude:\n    - cases\n")
        result, code = self.check(self.path("cases/s"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "cs", "path": "."})
        result, code = self.check(self.root, "--full")
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-PATH-001"])

    def test_base_snapshot_with_a_defective_multi_workspace_excludes_nothing(self):
        # 基準版・`HEAD`のスナップショットも同じ条件。除外が妥当に見えても、`multiWorkspace`に設定不適合があれば何も除外しない。
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - 3\n"
            "  exclude:\n    - fixtures\n    - apps/web/vectors\n",
        )
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "members defect")
        defective = _git(self.root, "rev-parse", "HEAD")
        git = gitutil.detect_git(str(self.root), self.env)
        root = str(self.root)
        self.assertEqual(multiws.base_exclude_parts(git, root, self.env, defective, root), [])
        # 条件を満たす基準版は、除外を信用する。
        self.rewrite_outer(["fixtures", "apps/web/vectors"])
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "fix")
        self.assertEqual(
            multiws.base_exclude_parts(git, root, self.env, "HEAD", root), [("fixtures",), ("apps", "web", "vectors")]
        )


class NestedMultiWorkspaceTests(_Base):
    """除外した範囲の中の`multiWorkspace`を宣言した設定は、入れ子の複合ワークスペースのルートになる（§2.1の1.）。"""

    def nested(self, rel: str = "fixtures/nested") -> Path:
        return self.path(rel)

    def test_all_workspaces_operations_use_the_nested_catalog(self):
        for name in ("check", "verify", "doctor"):
            for start in ("fixtures/nested", "fixtures/nested/a", "fixtures/nested/b/.spec"):
                with self.subTest(operation=name, start=start):
                    result, code = getattr(self, name)(self.path(start), "--all-workspaces")
                    self.assert_passed(result, code)
                    self.assertEqual(result["multiWorkspace"], {"id": "nest", "path": "."})
                    self.assertEqual(
                        [(w["id"], w["path"]) for w in result["workspaces"]], [("nest", "."), ("a", "a"), ("b", "b")]
                    )

    def test_check_all_workspaces_counts_documents_of_the_nested_catalog_only(self):
        result, _code = self.check(self.nested(), "--all-workspaces")
        self.assertEqual([w["checkedDocumentCount"] for w in result["workspaces"]], [2, 2, 2])

    def test_single_operations_from_the_nested_root_and_a_member(self):
        result, code = self.check(self.nested(), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "nest", "path": "."})
        result, code = self.check(self.nested("fixtures/nested/a"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "a", "path": "a"})
        result, code = self.verify(self.nested("fixtures/nested/a"))
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "a", "path": "a"})
        result, code = self.doctor(self.nested("fixtures/nested/a"))
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "a", "path": "a"})
        self.assertIn({"name": "catalog", "status": "passed"}, result["checks"])
        # `--workspace`で入れ子のカタログのメンバーへ置き換える。
        result, code = self.check(self.nested(), "--full", "--workspace", "b")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "b", "path": "b"})
        # 外側のカタログのIDは入れ子では引数不正（カタログは共有しない）。
        with self.assertRaises(CliArgError):
            self.check(self.nested(), "--full", "--workspace", "web")

    def test_context_uses_the_nested_catalog_and_qualified_ids(self):
        result, code = self.context(self.nested(), "REQ-100")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "nest", "path": "."})
        self.assertEqual(result["roots"], ["nest::REQ-100"])
        self.assertEqual(
            result["resolution"]["workspaces"], [{"id": "nest", "path": "."}]
        )
        result, code = self.context(self.nested("fixtures/nested/a"), "REQ-110")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "a", "path": "a"})
        self.assertEqual(result["roots"], ["a::REQ-110"])
        # 入れ子のメンバーの修飾IDを、入れ子のルートから解決できる。
        result, code = self.context(self.nested(), "b::REQ-120")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "b", "path": "b"})
        # 外側のカタログの修飾IDは解決しない（互いのカタログに含まれない）。
        with self.assertRaises(CliArgError):
            self.context(self.nested(), "web::REQ-050", "b::REQ-120")

    def test_outer_all_workspaces_does_not_include_the_nested_catalog(self):
        result, code = self.check(self.root, "--all-workspaces")
        self.assert_passed(result, code)
        self.assertEqual([w["id"] for w in result["workspaces"]], ["platform", "web"])

    def test_result_paths_are_relative_to_the_nested_root(self):
        _write(self.root, "fixtures/nested/a/.spec/requirements/REQ-110.md", _req(110).replace("意図。", "意図。\n\n[REQ-999]"))
        _write(self.root, "fixtures/nested/b/.spec/requirements/REQ-121.md", "---\nid: REQ-122\n---\n")
        result, _code = self.check(self.nested(), "--all-workspaces")
        for w in result["workspaces"]:
            for d in w["diagnostics"]:
                self.assertFalse(d["source"]["path"].startswith("fixtures"), d)
        self.assertTrue(any(w["diagnostics"] for w in result["workspaces"]))

    def test_unregistered_config_in_the_nested_root_stops_with_a_nested_relative_path(self):
        _write(self.root, "fixtures/nested/zzz/.spec/bitz.yaml", _member_yaml("zzz"))
        result, code = self.check(self.nested(), "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["multiWorkspace"], {"id": "nest", "path": "."})
        self.assertEqual(result["workspaces"], [])
        self.assertEqual(
            [(d["code"], d["summary"], d["source"]) for d in result["diagnostics"]],
            [("SPEC-MULTI-UNREGISTERED-001", UNREGISTERED_GIT, {"kind": "file", "workspaceId": None, "path": "zzz/.spec/bitz.yaml"})],
        )
        # 単独操作は、選択した設定が入れ子のカタログにないため、入れ子のルート相対のパスで止まる。
        result, code = self.check(self.nested("fixtures/nested/zzz"), "--full")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["workspace"], {"id": None, "path": "zzz"})
        self.assertEqual(
            result["diagnostics"][0]["source"], {"kind": "file", "workspaceId": None, "path": "zzz/.spec/bitz.yaml"}
        )
        self.assertEqual(result["diagnostics"][0]["summary"], UNREGISTERED_SELECTED)
        # 入れ子のルートの外（外側の`fixtures/stray`など）の設定は、入れ子の比較に含めない。外側の操作は止まらない。
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual(result["status"], "passed")

    def test_nested_catalog_failures_use_nested_relative_sources(self):
        os.remove(self.path("fixtures/nested/b/.spec/bitz.yaml"))
        result, code = self.doctor(self.path("fixtures/nested/a"), "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            [(d["code"], d["source"]["path"], d["source"]["workspaceId"]) for d in result["diagnostics"]],
            [("SPEC-MULTI-MEMBER-001", ".spec/bitz.yaml", "nest")],
        )

    def test_nested_exclude_validation_applies_to_the_nested_root(self):
        _write(self.root, "fixtures/nested/.spec/bitz.yaml", _root_yaml("nest", [("a", "a"), ("b", "b")], ["vendor", "vendor"]))
        result, code = self.check(self.nested(), "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([d["summary"] for d in result["diagnostics"]], [MSG_EXCLUDE_DUPLICATE])
        self.assertEqual(result["diagnostics"][0]["source"]["workspaceId"], "nest")
        # 入れ子のルートの除外が不正なら、その除外の中も入れ子のルートの規則で止まる（再帰）。
        result, code = self.check(self.path("fixtures/nested/vendor/single"), "--full")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([d["summary"] for d in result["diagnostics"]], [MSG_EXCLUDE_DUPLICATE])

    def test_exclude_recurses_into_the_nested_root(self):
        # 入れ子のルートの除外`vendor`の中の単一ワークスペースは、単一として動く。
        result, code = self.check(self.path("fixtures/nested/vendor/single"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "vsingle", "path": "."})
        with self.assertRaises(CliArgError):
            self.check(self.path("fixtures/nested/vendor/single"), "--all-workspaces")
        # 入れ子のルートの除外`vendor`の中の`multiWorkspace`を宣言した設定は、さらに入れ子の複合ワークスペースのルートになる。
        for start in ("fixtures/nested/vendor/inner", "fixtures/nested/vendor/inner/leaf"):
            result, code = self.check(self.path(start), "--all-workspaces")
            self.assert_passed(result, code)
            self.assertEqual(result["multiWorkspace"], {"id": "inner", "path": "."})
            self.assertEqual([(w["id"], w["path"]) for w in result["workspaces"]], [("inner", "."), ("leaf", "leaf")])
        result, code = self.check(self.path("fixtures/nested/vendor/inner/leaf"), "--full")
        self.assert_passed(result, code)
        self.assertEqual(result["workspace"], {"id": "leaf", "path": "leaf"})

    def test_unregistered_config_inside_the_nested_exclude_does_not_stop(self):
        _write(self.root, "fixtures/nested/vendor/other/.spec/bitz.yaml", _member_yaml("other"))
        result, code = self.doctor(self.nested(), "--all-workspaces")
        self.assert_passed(result, code)

    def test_nearest_declaring_config_to_the_exclude_wins(self):
        # 経路の上に宣言した設定が複数あれば、除外のディレクトリに最も近い（浅い）設定を入れ子のルートにする。
        _write(self.root, "fixtures/nested/a/inner/.spec/bitz.yaml", _root_yaml("deeper", [("c", "c")]))
        _write(self.root, "fixtures/nested/a/inner/c/.spec/bitz.yaml", _member_yaml("c"))
        # `fixtures/nested`が`fixtures`に最も近い宣言した設定。そのカタログにない設定は未登録になる（入れ子の複合ワークスペースは独立）。
        result, code = self.check(self.path("fixtures/nested/a/inner"), "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["multiWorkspace"], {"id": "nest", "path": "."})
        self.assertEqual([d["source"]["path"] for d in result["diagnostics"]], ["a/inner/.spec/bitz.yaml", "a/inner/c/.spec/bitz.yaml"])

    def test_non_declaring_config_closer_to_the_exclude_is_skipped(self):
        # 除外のディレクトリ自身に宣言しない設定があっても、経路の上に宣言した設定があればそれを入れ子のルートにする。
        _write(self.root, "fixtures/wrap/.spec/bitz.yaml", _member_yaml("wrap"))
        _write(self.root, "fixtures/wrap/m/.spec/bitz.yaml", _root_yaml("wrapm", [("wm", "wm")]))
        _write(self.root, "fixtures/wrap/m/wm/.spec/bitz.yaml", _member_yaml("wm"))
        self.rewrite_outer(["fixtures/wrap", "apps/web/vectors"])
        result, code = self.check(self.path("fixtures/wrap/m/wm"), "--all-workspaces")
        self.assert_passed(result, code)
        self.assertEqual(result["multiWorkspace"], {"id": "wrapm", "path": "."})
        # 宣言した設定がなければ、最も近い設定が単一ワークスペース。
        result, code = self.check(self.path("fixtures/wrap"), "--full")
        self.assertEqual(result["workspace"], {"id": "wrap", "path": "."})

    def test_unreadable_config_does_not_declare(self):
        # 読めない設定は宣言しないものとみなす。除外のディレクトリに近い読めない設定は飛ばし、深い宣言した設定を使う。
        _write(self.root, "fixtures/bad/.spec/bitz.yaml", CONFIG + "context: 5\nmultiWorkspace:\n  members: []\n")
        _write(self.root, "fixtures/bad/m/.spec/bitz.yaml", _root_yaml("badm", [("bm", "bm")]))
        _write(self.root, "fixtures/bad/m/bm/.spec/bitz.yaml", _member_yaml("bm"))
        self.rewrite_outer(["fixtures/bad", "apps/web/vectors"])
        result, code = self.check(self.path("fixtures/bad/m"), "--all-workspaces")
        self.assert_passed(result, code)
        self.assertEqual(result["multiWorkspace"], {"id": "badm", "path": "."})
        # 読めない設定しかなければ宣言した設定がなく、最も近い設定（読めない設定）が単一ワークスペースとして使われ、設定の不適合を返す。
        result, code = self.check(self.path("fixtures/bad"), "--full")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["diagnostics"][0]["code"], "SPEC-CONFIG-SCHEMA-001")

    def test_unsupported_version_nested_config_still_declares(self):
        # 版が非対応の設定は、`multiWorkspace`があれば宣言するものとする。入れ子のルートとして全体事前検査で停止する。
        text = _root_yaml("nest", [("a", "a"), ("b", "b")], ["vendor"]).replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')
        _write(self.root, "fixtures/nested/.spec/bitz.yaml", text)
        result, code = self.check(self.path("fixtures/nested/a"), "--full")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-CONFIG-SCHEMA-001"])
        result, code = self.check(self.path("fixtures/nested/a"), "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["workspaces"], [])

    def test_report_is_written_under_the_nested_root(self):
        result, code = self.check(self.nested(), "--all-workspaces", "--report")
        self.assert_passed(result, code)
        reports = list(self.path("fixtures/nested/.spec/reports").rglob("*.json"))
        self.assertTrue(reports, "入れ子のルートの`.spec/reports/`へ保存されること")
        self.assertFalse(self.path(".spec/reports").exists())

    # --- Gitが返すパスの写像 ---------------------------------------------------------
    def test_changes_outside_the_nested_root_are_not_compared(self):
        _write(self.root, ".spec/requirements/REQ-001.md", _req(1).replace("意図。", "変更した意図。"))
        _write(self.root, "apps/web/.spec/requirements/REQ-050.md", _req(50).replace("意図。", "変更した意図。"))
        _write(self.root, "fixtures/nested/a/.spec/requirements/REQ-110.md", _req(110).replace("意図。", "変更した意図。"))
        result, code = self.check(self.nested("fixtures/nested/a"))
        self.assert_passed(result, code)
        self.assertEqual(result["scope"], "changed")
        self.assertEqual(result["selection"]["changedPathCount"], 1)
        self.assertEqual(result["selection"]["targetDocumentCount"], 1)
        # 入れ子のルートのワークスペースは、入れ子のルートの外の変更を含めず、メンバーの配下の変更も所有しない。
        result, code = self.check(self.nested())
        self.assert_passed(result, code)
        self.assertEqual(result["selection"]["changedPathCount"], 0)

    def test_base_comparison_reads_the_same_directory_in_the_base(self):
        base = _git(self.root, "rev-parse", "HEAD")
        # 基準版以降に、入れ子のメンバー`b`を削除し、別のメンバー`c`へ置き換える。
        _write(self.root, "fixtures/nested/.spec/bitz.yaml", _root_yaml("nest", [("a", "a"), ("c", "c")], ["vendor"]))
        _write(self.root, "fixtures/nested/c/.spec/bitz.yaml", _member_yaml("c"))
        _git(self.root, "rm", "-q", "-r", "fixtures/nested/b")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "swap member")
        result, code = self.check(self.nested(), "--all-workspaces", "--base", base)
        # 基準版の入れ子のルート（同じディレクトリ）のカタログを使うため、削除されたメンバー`b`の承認済み要求の削除が検出される。
        self.assertIn(result["status"], ("failed", "blocked"))
        codes = {d["code"] for d in result["diagnostics"]} | {d["code"] for w in result["workspaces"] for d in w["diagnostics"]}
        self.assertIn("SPEC-STATE-TRANSITION-001", codes)
        removed = [d for d in result["diagnostics"] if d["code"] == "SPEC-STATE-TRANSITION-001"]
        self.assertEqual({d["source"]["workspaceId"] for d in removed}, {"b"})
        self.assertTrue(all(not d["source"]["path"].startswith("fixtures") for d in removed), removed)
        self.assertEqual(result["multiWorkspace"], {"id": "nest", "path": "."})

    def test_revision_is_the_whole_repository(self):
        head = _git(self.root, "rev-parse", "HEAD")
        result, _code = self.check(self.nested(), "--all-workspaces")
        self.assertEqual(result["revision"], {"base": head, "commit": head, "dirty": False})
        _write(self.root, "tools/note.txt", "x\n")  # 入れ子のルートの外の変更でも、`dirty`はリポジトリ全体の状態
        result, _code = self.check(self.nested(), "--all-workspaces")
        self.assertTrue(result["revision"]["dirty"])

    def test_git_listings_are_mapped_to_the_nested_root(self):
        git = gitutil.detect_git(str(self.root), self.env)
        nested = str(self.nested())
        self.assertEqual(
            gitutil.list_working_config_paths(git.executable, nested, self.env, nested),
            [".spec/bitz.yaml", "a/.spec/bitz.yaml", "b/.spec/bitz.yaml", "vendor/inner/.spec/bitz.yaml",
             "vendor/inner/leaf/.spec/bitz.yaml", "vendor/single/.spec/bitz.yaml"],
        )
        self.assertEqual(
            sorted(gitutil.list_tree_config_paths(git.executable, nested, self.env, "HEAD", nested)),
            [".spec/bitz.yaml", "a/.spec/bitz.yaml", "b/.spec/bitz.yaml", "vendor/inner/.spec/bitz.yaml",
             "vendor/inner/leaf/.spec/bitz.yaml", "vendor/single/.spec/bitz.yaml"],
        )
        # `workspace_root`を渡さなければ、従来どおりリポジトリのルートからの相対。
        self.assertIn("fixtures/nested/a/.spec/bitz.yaml", gitutil.list_working_config_paths(git.executable, nested, self.env))

    def test_submodule_paths_are_mapped_to_the_nested_root(self):
        git = gitutil.detect_git(str(self.root), self.env)
        sub = tempfile.TemporaryDirectory()
        self.addCleanup(sub.cleanup)
        sub_root = Path(sub.name)
        _git(sub_root, "init", "-q", "--initial-branch=main")
        _git(sub_root, "config", "user.email", "t@t")
        _git(sub_root, "config", "user.name", "t")
        _write(sub_root, "f.txt", "x\n")
        _git(sub_root, "add", ".")
        _git(sub_root, "commit", "-q", "-m", "s")
        _git(self.root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub_root), "fixtures/nested/a/lib")
        nested = str(self.nested())
        self.assertEqual(gitutil.list_submodule_paths(git.executable, nested, self.env, nested), {"a/lib"})
        self.assertEqual(gitutil.list_submodule_paths(git.executable, nested, self.env), {"fixtures/nested/a/lib"})

    def test_member_that_is_a_submodule_is_rejected_with_a_nested_relative_check(self):
        sub = tempfile.TemporaryDirectory()
        self.addCleanup(sub.cleanup)
        sub_root = Path(sub.name)
        _git(sub_root, "init", "-q", "--initial-branch=main")
        _git(sub_root, "config", "user.email", "t@t")
        _git(sub_root, "config", "user.name", "t")
        _write(sub_root, ".spec/bitz.yaml", _member_yaml("sm"))
        _git(sub_root, "add", ".")
        _git(sub_root, "commit", "-q", "-m", "s")
        _git(self.root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub_root), "fixtures/nested/sm")
        _write(self.root, "fixtures/nested/.spec/bitz.yaml", _root_yaml("nest", [("a", "a"), ("b", "b"), ("sm", "sm")], ["vendor"]))
        result, code = self.check(self.nested(), "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual([(d["code"], d["summary"]) for d in result["diagnostics"]], [("SPEC-MULTI-PATH-001", "メンバーのパスがGitのサブモジュールです")])


class DeterminismTests(_Base):
    """`PYTHONHASHSEED`を変えても、除外と入れ子の結果が同じこと。"""

    def run_cli(self, cwd: Path, seed: str, *argv: str) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, "-m", "bitz.cli", *argv, "--format", "json"], cwd=cwd,
            env={**self.env, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
            capture_output=True, text=True,
        )
        return proc.returncode, json.dumps(_without_durations(json.loads(proc.stdout)), ensure_ascii=False)

    def test_output_is_independent_of_hash_seed(self):
        _write(self.root, "fixtures/nested/zzz/.spec/bitz.yaml", _member_yaml("zzz"))
        _write(self.root, "fixtures/nested/yyy/.spec/bitz.yaml", _member_yaml("yyy"))
        cases = [
            ("fixtures/nested", ("check", "--all-workspaces")),
            ("fixtures/nested", ("doctor", "--all-workspaces")),
            ("fixtures/nested", ("check", "--full")),
            ("fixtures/nested/a", ("verify",)),
            ("fixtures/single", ("check", "--full")),
            (".", ("doctor", "--all-workspaces")),
        ]
        for cwd, argv in cases:
            outputs = {seed: self.run_cli(self.path(cwd), seed, *argv) for seed in ("0", "1", "12345")}
            with self.subTest(cwd=cwd, argv=argv):
                self.assertEqual(len({v for v in outputs.values()}), 1, outputs)
                self.assertTrue(next(iter(outputs.values()))[1].startswith("{"))
        # 除外が不正な場合の診断の並びも同じ。
        self.rewrite_outer(["", ".spec", "a", "a", "b", "b/c", "x/*"])
        outputs = {seed: self.run_cli(self.root, seed, "doctor", "--all-workspaces") for seed in ("0", "1", "999")}
        self.assertEqual(len(set(outputs.values())), 1, outputs)
        diagnostics = json.loads(next(iter(outputs.values()))[1])["diagnostics"]
        self.assertEqual(len(diagnostics), 5)


class NoGitTests(unittest.TestCase):
    """Gitのない場所では除外を適用しない（`multiWorkspace`の判定は最も近い設定。ADR-063）。"""

    def test_without_a_git_repository_nothing_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(os.path.realpath(tmp))
            _write(root, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web")], ["fixtures"]))
            _write(root, "apps/web/.spec/bitz.yaml", _member_yaml("web"))
            _write(root, "fixtures/single/.spec/bitz.yaml", _member_yaml("fsingle"))
            env = dict(os.environ)
            parsed = parse_argv(["check", "--full", "--format", "json"])
            result, code = check_mod.run(parsed, str(root / "fixtures" / "single"), env)
            self.assertEqual((result["status"], result["workspace"]), ("passed", {"id": "fsingle", "path": "."}))
            result, code = check_mod.run(parsed, str(root), env)
            self.assertEqual((result["status"], code), ("blocked", 2))
            self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])


if __name__ == "__main__":
    unittest.main()
