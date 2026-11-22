"""ADR-082の単体試験と、承認済みの契約の保護の検収の指摘（L-1、L-3）の固定。

適合fixtureの準備の処理で作れない入力（部分クローンの欠けたオブジェクト）と、fixtureが区別しない入力を、実際のGitのリポジトリで確かめる。

- 遅延取得をしない（Core実行環境・CLI基盤契約 §4、ADR-082の決定1）: 部分クローンで取得元に届く環境で`check`を実行しても、オブジェクトが増えない。
  `GIT_NO_LAZY_FETCH`と`GIT_ALLOW_PROTOCOL`のそれぞれが単独でも遅延取得を止めること（`GIT_NO_LAZY_FETCH`を解さない版のGitでも止まること）と、
  どちらもなければ遅延取得が起きること（試験の入力が遅延取得を検出できること）を確かめる。
- 読めない基準版（`check` §5、ADR-082の決定2）: 単一ワークスペースで、基準版の仕様文書の一覧または内容をGitから読めなければ、
  基準版との比較を始めず`SPEC-GIT-BASE-001`（`blocked`、`stop-operation`）にする。
- 保護の設定の版（文書・フロントマター・状態仕様 §8、ADR-082の決定4）: 基準版に設定がない場合と、基準版の設定のYAMLの構文が不正な場合は、
  基準版の側を有効とみなす。
- 途中の版の`documentArrayItemCount`（安全な入出力・互換性 §4.1、ADR-082の決定3）。
- L-1: 同じIDの文書が2つある親との比較では、状態を変えたとしない（§8.1、ADR-079の決定4、ADR-081の決定2）。
- L-3: 途中のコミットの読取りで出る`ValueError`、`UnicodeDecodeError`、`RecursionError`は、完全には読めない側にする。

期待値は仕様のリテラルで、Coreの出力からは導かない。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import approvedhistory
from bitz import check as check_mod
from bitz import gitutil
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
DISABLED = CONFIG + "safety:\n  protectApprovedRequirements: false\n"
REQ_PATH = ".spec/requirements/REQ-001.md"
SAFETY = "SPEC-SAFETY-APPROVED-001"
SUMMARY = "状態approvedのREQの意味変更時に文書の状態が戻されていません"
HISTORY_SUMMARY = "状態approvedのREQの意味変更時に文書の状態が戻されていません（途中のコミットを完全には読めません）"
BASE_DIAGNOSTIC = {
    "code": "SPEC-GIT-BASE-001",
    "severity": "error",
    "resultStatus": "blocked",
    "summary": "基準版の仕様文書の内容をGitから読めません",
    "source": {"kind": "environment", "component": "git"},
}


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(*, title: str = "文書の検査", status: str = "approved", related: list[str] | None = None) -> str:
    relations = f"relations:\n  related: [{', '.join(related)}]\n" if related else ""
    return (
        f"---\nid: REQ-001\ntitle: {title}\nstatus: {status}\n{relations}---\n\n# REQ-001 {title}\n\n## Intent\n\n意図。\n\n"
        "## Acceptance Criteria\n\n- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


class _Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.env = {**os.environ, **_GIT_ENV}
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def commit(self, root: Path, message: str, *paths: str) -> str:
        _git(root, "add", "--", *paths)
        _git(root, "commit", "-q", "-m", message)
        return _git(root, "rev-parse", "HEAD")

    def run_check(self, *argv: str, cwd: Path | None = None) -> dict:
        return check_mod.run(parse_argv(["check", *argv, "--format", "json"]), str(cwd or self.root), self.env)[0]

    def protection(self, result: dict) -> list[tuple[str, str, str]]:
        return [(d["source"]["path"], d["source"].get("key"), d["summary"]) for d in result["diagnostics"] if d["code"] == SAFETY]


class _PartialClone(_Repo):
    """基準版、`draft`のコミット、再承認のコミットを持つ取得元と、その`--filter=blob:none`の部分クローン。"""

    def build_clone(self) -> tuple[Path, str]:
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, ".spec/requirements/REQ-002.md", _req().replace("REQ-001", "REQ-002"))
        base = self.commit(self.root, "base", ".")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "draft", ".")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        return clone, base

    def missing(self, clone: Path) -> set[str]:
        out = subprocess.run(
            ["git", "rev-list", "--objects", "--all", "--missing=print"],
            cwd=clone, env={**self.env, "GIT_NO_LAZY_FETCH": "1"}, check=True, capture_output=True, text=True,
        ).stdout
        return {line[1:] for line in out.splitlines() if line.startswith("?")}


class LazyFetchTests(_PartialClone):
    """Coreが起動するGitは遅延取得をしない（ADR-082の決定1）。取得元には届く。"""

    def test_check_does_not_fetch_missing_objects(self):
        clone, base = self.build_clone()
        before = self.missing(clone)
        self.assertTrue(before)
        result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertEqual(self.missing(clone), before)
        # 基準版の仕様文書の内容が欠けているので、比較を始めない。
        self.assertEqual(result["diagnostics"], [BASE_DIAGNOSTIC])

    def test_intermediate_objects_are_not_fetched(self):
        clone, base = self.build_clone()
        # 端点の比較に要る基準版の文書だけを、試験の側で取得しておく（途中のコミットの`draft`の版は欠けたまま）。
        _git(clone, "cat-file", "-p", f"{base}:{REQ_PATH}")
        _git(clone, "cat-file", "-p", f"{base}:.spec/requirements/REQ-002.md")
        draft_blob = _git(self.root, "rev-parse", f"HEAD~1:{REQ_PATH}")
        before = self.missing(clone)
        self.assertIn(draft_blob, before)
        result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertEqual(self.missing(clone), before)
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", HISTORY_SUMMARY)])

    def assert_alone_stops_the_fetch(self, name: str) -> None:
        clone, base = self.build_clone()
        before = self.missing(clone)
        with mock.patch.dict(gitutil.NO_FETCH_ENV, {name: gitutil.NO_FETCH_ENV[name]}, clear=True):
            result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertEqual(self.missing(clone), before)
        self.assertEqual(result["diagnostics"], [BASE_DIAGNOSTIC])

    def test_transport_restriction_alone_stops_the_fetch(self):
        # `GIT_NO_LAZY_FETCH`を解さない版のGitでも、取得に使う転送の禁止（`GIT_ALLOW_PROTOCOL`）だけで止まる。
        self.assert_alone_stops_the_fetch("GIT_ALLOW_PROTOCOL")

    def test_no_lazy_fetch_alone_stops_the_fetch(self):
        self.assert_alone_stops_the_fetch("GIT_NO_LAZY_FETCH")

    def test_control_without_the_mechanisms_fetches(self):
        # 対照: どちらの手段もなければ遅延取得が起き、欠けたオブジェクトが減る（この試験の入力が取得を検出できる）。
        clone, base = self.build_clone()
        before = self.missing(clone)
        with mock.patch.dict(gitutil.NO_FETCH_ENV, {}, clear=True):
            result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertLess(len(self.missing(clone)), len(before))
        self.assertEqual(self.protection(result), [])

    def test_git_env_does_not_change_the_given_environment(self):
        env = {"PATH": "/bin"}
        self.assertEqual(
            gitutil.git_env(env), {"PATH": "/bin", "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "bitz-no-transport"}
        )
        self.assertEqual(env, {"PATH": "/bin"})


class UnreadableBaseTests(_PartialClone):
    """読めない基準版は`SPEC-GIT-BASE-001`（`blocked`）にし、基準版との比較を始めない（`check` §5、ADR-082の決定2）。"""

    def detached_clone(self, filter_spec: str) -> tuple[Path, str]:
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, ".spec/requirements/REQ-002.md", _req().replace("REQ-001", "REQ-002"))
        base = self.commit(self.root, "base", ".")
        # 現在版では、REQ-001の`title`を変え（保護の違反の候補）、REQ-002を削除する（削除の検出）。
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        _git(self.root, "rm", "-q", "--", ".spec/requirements/REQ-002.md")
        self.commit(self.root, "change", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", f"--filter={filter_spec}", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        shutil.move(str(self.root), str(self.tmp / "moved"))
        return clone, base

    def test_missing_base_content_blocks_without_comparison(self):
        clone, base = self.detached_clone("blob:none")
        for argv in (("--full", "--base", base), ("REQ-001", "--base", base)):
            with self.subTest(argv=argv):
                result = self.run_check(*argv, cwd=clone)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["diagnostics"], [BASE_DIAGNOSTIC])
                self.assertEqual((result["checkedDocumentCount"], result["checkedStatementCount"]), (0, 0))
                self.assertEqual(result["revision"]["base"], base)

    def test_missing_base_content_blocks_changed_scope(self):
        clone, base = self.detached_clone("blob:none")
        result = self.run_check("--base", base, cwd=clone)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["diagnostics"], [BASE_DIAGNOSTIC])
        self.assertEqual(
            result["selection"], {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}
        )
        exit_code = check_mod.run(parse_argv(["check", "--base", base, "--format", "json"]), str(clone), self.env)[1]
        self.assertEqual(exit_code, 2)

    def test_missing_base_tree_blocks(self):
        # `--filter=tree:0`では基準版のツリーも欠ける（仕様文書の一覧を読めない）。
        clone, base = self.detached_clone("tree:0")
        result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertEqual(result["diagnostics"], [BASE_DIAGNOSTIC])

    def test_readable_base_is_compared_as_before(self):
        # 対照: 基準版を読めれば、保護の違反と削除の検出を返す。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, ".spec/requirements/REQ-002.md", _req().replace("REQ-001", "REQ-002"))
        base = self.commit(self.root, "base", ".")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        os.remove(self.root / ".spec/requirements/REQ-002.md")
        codes = sorted(d["code"] for d in self.run_check("--full", "--base", base)["diagnostics"])
        self.assertEqual(codes, [SAFETY, "SPEC-STATE-TRANSITION-001"])

    def test_missing_object_outside_the_spec_documents_does_not_block(self):
        # 仕様文書でないファイル（`.spec`の外）の内容が欠けていても、基準版の仕様文書は読める。
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, "docs/note.txt", "v1\n")
        base = self.commit(self.root, "base", ".")
        _write(self.root, "docs/note.txt", "v2\n")
        self.commit(self.root, "note", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        _git(clone, "cat-file", "-p", f"{base}:{REQ_PATH}")
        shutil.move(str(self.root), str(self.tmp / "moved"))
        self.assertIn(_git(clone, "rev-parse", f"{base}:docs/note.txt"), self.missing(clone))
        result = self.run_check("--full", "--base", base, cwd=clone)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["diagnostics"], [])


class ProtectionSettingVersionTests(_Repo):
    """保護は、基準版と現在版の設定のどちらかで有効なら有効（文書・フロントマター・状態仕様 §8、ADR-082の決定4）。"""

    def change_with_disabled_current(self) -> dict:
        _write(self.root, ".spec/bitz.yaml", DISABLED)
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        return self.run_check("--full", "--base", "HEAD")

    def test_base_without_config_counts_as_enabled(self):
        # 基準版に`.spec/bitz.yaml`がない（基準版の仕様文書だけがある）。
        _write(self.root, REQ_PATH, _req())
        self.commit(self.root, "base", ".spec")
        result = self.change_with_disabled_current()
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])
        self.assertEqual(result["status"], "failed")

    def test_base_config_with_yaml_syntax_error_counts_as_enabled(self):
        # 基準版の設定のYAMLの構文が不正（閉じていない流れの配列）。`false`の行を含んでいても、基準版の側は有効。
        _write(self.root, ".spec/bitz.yaml", DISABLED + "verify:\n  commands: [閉じていない\n")
        _write(self.root, REQ_PATH, _req())
        self.commit(self.root, "base", ".spec")
        result = self.change_with_disabled_current()
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])
        # 基準版の設定の不適合は診断しない。
        self.assertEqual([d["code"] for d in result["diagnostics"]], [SAFETY])

    def test_both_disabled_is_disabled(self):
        # 対照: 基準版も`false`なら無効。
        _write(self.root, ".spec/bitz.yaml", DISABLED)
        _write(self.root, REQ_PATH, _req())
        self.commit(self.root, "base", ".spec")
        result = self.change_with_disabled_current()
        self.assertEqual(self.protection(result), [])
        self.assertEqual(result["status"], "passed")

    def test_base_config_is_read_only_when_the_current_setting_is_disabled(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        self.commit(self.root, "base", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        with mock.patch.object(gitutil, "show_base_file", side_effect=AssertionError("基準版の設定を読んだ")):
            result = self.run_check("--full", "--base", "HEAD")
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])


class IntermediateVersionTests(_Repo):
    """途中の版の読み方（§8.1）。"""

    def test_document_array_item_count_applies_to_intermediate_versions(self):
        # 途中の`draft`の版だけが`relations.related`に3件を持つ。上限2なら索引に入らない版（IDを読めない版）、3なら認める。
        for limit, expected in ((2, [(REQ_PATH, "title", SUMMARY)]), (3, [])):
            with self.subTest(limit=limit):
                root = self.tmp / f"array-{limit}"
                root.mkdir()
                _git(root, "init", "-q", "--initial-branch=main")
                _git(root, "config", "user.email", "t@t")
                _git(root, "config", "user.name", "t")
                _write(root, ".spec/bitz.yaml", CONFIG + f"limits:\n  documentArrayItemCount: {limit}\n")
                _write(root, REQ_PATH, _req())
                base = self.commit(root, "base", ".spec")
                _write(root, REQ_PATH, _req(title="変更後の文書検査", status="draft", related=["REQ-002", "REQ-003", "REQ-004"]))
                self.commit(root, "draft", ".spec")
                _write(root, REQ_PATH, _req(title="変更後の文書検査"))
                self.commit(root, "approve", ".spec")
                self.assertEqual(self.protection(self.run_check("--full", "--base", base, cwd=root)), expected)

    def test_parent_with_duplicate_ids_does_not_count_as_changing_the_state(self):
        # L-1: 親に`A/REQ-001.md`（approved）と`REQ-001.md`（draft）を置き、子で`A`を削除して、`draft`の版を1つにする。
        # 子の版は`draft`だが、親は同じIDの文書を2つ持つので、その親との比較では状態を変えたとしない。ほかの親もない。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        base = self.commit(self.root, "base", ".spec")
        _write(self.root, ".spec/requirements/A/REQ-001.md", _req())
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "duplicate", ".spec")
        _git(self.root, "rm", "-q", "--", ".spec/requirements/A/REQ-001.md")
        self.commit(self.root, "remove duplicate", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".spec")
        result = self.run_check("--full", "--base", base)
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])
        self.assertEqual(result["status"], "failed")

    def test_read_errors_are_incomplete(self):
        # L-3: コミットのデータの形の不正（`ValueError`、`UnicodeDecodeError`）と深いツリー（`RecursionError`）は、完全には読めない側にする。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        base = self.commit(self.root, "base", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "draft", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".spec")
        self.assertEqual(self.protection(self.run_check("--full", "--base", base)), [])
        errors = (
            ValueError("bad"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), RecursionError("deep"),
            gitutil.GitReadError("missing"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(approvedhistory.History, "_read_documents_unchecked", side_effect=error):
                    result = self.run_check("--full", "--base", base)
                self.assertEqual(self.protection(result), [(REQ_PATH, "title", HISTORY_SUMMARY)])

    def test_malformed_diff_output_is_incomplete(self):
        # `git diff-tree`の出力のコミットの行が入力と一致しなければ、完全には読めない側にする。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        base = self.commit(self.root, "base", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "draft", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".spec")
        history = approvedhistory.History("git", str(self.root), self.env, base, 10_000)
        self.assertEqual(history._ensure_state(), "ready")
        real_run = subprocess.run

        def broken(argv, *a, **kw):
            proc = real_run(argv, *a, **kw)
            if "diff-tree" in argv:
                proc = subprocess.CompletedProcess(argv, 0, stdout=b"\xff\xfe\0", stderr=b"")
            return proc

        with mock.patch.object(subprocess, "run", broken):
            verdict = history.evaluate(str(self.root), "root", check_mod.limits_mod.ABSOLUTE, {"REQ-001"})
        self.assertEqual(verdict, approvedhistory.INCOMPLETE)


if __name__ == "__main__":
    unittest.main()
