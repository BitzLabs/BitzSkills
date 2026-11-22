"""承認済み要求の保護の途中のコミットの単体試験（文書・フロントマター・状態仕様 §8.1、ADR-072、ADR-078、ADR-079、ADR-081）。

適合fixtureの準備の処理では作らない次の入力を、実際のGitのリポジトリで確かめる（承認済みの契約の保護のレビュー記録「fixtureにしなかったもの」）。

- 部分クローンで欠けたオブジェクト: 途中のコミットの仕様文書のファイルをGitから読めなければ、完全には読めない文言の違反にする。
  ルートの外のオブジェクトが欠けていても、完全に読めないとはしない（ADR-079の決定2）。
- 2つ目以降の根となる親のないコミット（`--allow-unrelated-histories`で取り込んだ別の根）: 親のないコミットでは、すべての文書の状態を変えたものとする（ADR-081の決定1）。

あわせて、違反の候補がない場合にGitの呼出しが増えないこと（ADR-072の`Consequences`）、`--all-workspaces`で各ワークスペースの設定の
`safety.protectApprovedRequirements`を使うこと、`git cat-file --batch`の上限を超えるオブジェクトの読み捨てを確かめる。
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
REQ_PATH = ".spec/requirements/REQ-001.md"
CODE = "SPEC-SAFETY-APPROVED-001"
SUMMARY = "状態approvedのREQの意味変更時に文書の状態が戻されていません"
HISTORY_SUMMARY = "状態approvedのREQの意味変更時に文書の状態が戻されていません（途中のコミットを完全には読めません）"
TECH_SUMMARY = "状態approvedのTECHの意味変更時に文書の状態が戻されていません"


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(*, title: str = "文書の検査", status: str = "approved", doc_id: str = "REQ-001") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n\n## Intent\n\n意図。\n\n"
        f"## Acceptance Criteria\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(*, title: str = "出力の制約", status: str = "approved", doc_id: str = "TECH-001") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n\n## Context\n\n本文。\n\n"
        f"## Contract\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
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

    def check(self, *argv: str, cwd: Path | None = None) -> dict:
        return check_mod.run(parse_argv(["check", *argv, "--format", "json"]), str(cwd or self.root), self.env)[0]

    def protection(self, result: dict) -> list[tuple[str, str, str]]:
        return [
            (d["source"]["path"], d["source"].get("key"), d["summary"])
            for d in result["diagnostics"]
            if d["code"] == CODE
        ]


class SecondRootCommitTests(_Repo):
    """2つ目以降の根となる親のないコミット（ADR-081の決定1）。"""

    def build(self, *, other_status: str) -> str:
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        base = self.commit(self.root, "base", ".spec")
        # 別の根: 基準版の履歴と共通の祖先を持たない枝`other`。
        _git(self.root, "checkout", "-q", "--orphan", "other")
        _git(self.root, "rm", "-q", "-r", "--cached", ".")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status=other_status))
        self.commit(self.root, "other root", ".spec")
        _git(self.root, "checkout", "-q", "-f", "main")
        proc = subprocess.run(
            ["git", "merge", "-q", "--allow-unrelated-histories", "--no-edit", "other"],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )
        # `.spec/bitz.yaml`は両方で同じ内容、REQ-001は両方で追加したので衝突する。再承認の版で解く。
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        _git(self.root, "add", "--", REQ_PATH)
        _git(self.root, "commit", "-q", "--no-edit")
        parents = _git(self.root, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
        self.assertEqual(len(parents), 2)
        roots = _git(self.root, "rev-list", "--max-parents=0", "HEAD").split()
        self.assertEqual(len(roots), 2)
        return base

    def test_draft_version_on_second_root_counts_as_changing_the_state(self):
        base = self.build(other_status="draft")
        result = self.check("--full", "--base", base)
        self.assertEqual(self.protection(result), [])
        self.assertEqual(result["status"], "passed")

    def test_approved_version_on_second_root_is_not_an_intermediate_state(self):
        # 親のないコミットでも、版の状態が`draft`または`outdated`でなければ認めない。マージコミットの版は`approved`。
        base = self.build(other_status="approved")
        result = self.check("--full", "--base", base)
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])
        self.assertEqual(result["status"], "failed")

    def test_outdated_version_on_second_root_counts_as_changing_the_state(self):
        base = self.build(other_status="outdated")
        self.assertEqual(self.protection(self.check("--full", "--base", base)), [])


class PartialCloneTests(_Repo):
    """部分クローンで欠けたオブジェクト（ADR-078の決定2、ADR-079の決定2）。

    取得元の`origin`を移して遅延取得を失敗させ、欠けたオブジェクトをGitから読めない状態にする。
    """

    def build(self, workspace: str = "") -> tuple[Path, str]:
        prefix = f"{workspace}/" if workspace else ""
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, f"{prefix}.spec/bitz.yaml", CONFIG)
        _write(self.root, f"{prefix}{REQ_PATH}", _req())
        _write(self.root, "other/note.txt", "v1\n")
        base = self.commit(self.root, "base", ".")
        _write(self.root, f"{prefix}{REQ_PATH}", _req(title="変更後の文書検査", status="draft"))
        _write(self.root, "other/note.txt", "v2\n")
        self.commit(self.root, "draft", ".")
        _write(self.root, f"{prefix}{REQ_PATH}", _req(title="変更後の文書検査"))
        _write(self.root, "other/note.txt", "v3\n")
        self.commit(self.root, "approve", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        _git(clone, "config", "user.email", "t@t")
        _git(clone, "config", "user.name", "t")
        # 基準版の文書は、端点の比較に要るので先に取得しておく。
        _git(clone, "cat-file", "-p", f"{base}:{prefix}{REQ_PATH}")
        return clone, base

    def detach_origin(self) -> None:
        moved = self.tmp / "moved"
        shutil.move(str(self.root), str(moved))

    def missing(self, clone: Path) -> set[str]:
        out = _git(clone, "rev-list", "--objects", "--missing=print", "HEAD")
        return {line[1:] for line in out.splitlines() if line.startswith("?")}

    def test_missing_intermediate_spec_file_keeps_the_violation_with_history_wording(self):
        clone, base = self.build()
        self.detach_origin()
        draft_blob = _git(clone, "rev-parse", f"HEAD~1:{REQ_PATH}")
        self.assertIn(draft_blob, self.missing(clone))
        result = check_mod.run(
            parse_argv(["check", "--full", "--base", base, "--format", "json"]), str(clone), self.env
        )[0]
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", HISTORY_SUMMARY)])
        self.assertEqual(result["status"], "failed")

    def test_readable_intermediate_spec_file_passes_even_if_objects_outside_the_root_are_missing(self):
        # 作業ワークスペースのルートは`ws/`。ルートの外の`other/note.txt`の途中の版は欠けたままにする。
        clone, base = self.build("ws")
        _git(clone, "cat-file", "-p", f"HEAD~1:ws/{REQ_PATH}")
        self.detach_origin()
        outside_blob = _git(clone, "rev-parse", "HEAD~1:other/note.txt")
        self.assertIn(outside_blob, self.missing(clone))
        self.assertNotIn(_git(clone, "rev-parse", f"HEAD~1:ws/{REQ_PATH}"), self.missing(clone))
        result = check_mod.run(
            parse_argv(["check", "--full", "--base", base, "--format", "json"]), str(clone / "ws"), self.env
        )[0]
        self.assertEqual(self.protection(result), [])
        self.assertEqual(result["status"], "passed")

    def test_missing_spec_file_of_a_parent_keeps_the_violation(self):
        # 途中のコミットの親（基準版）の仕様文書のファイルも読む。基準版のREQ-001だけでなく、親の別の仕様文書を欠けさせる。
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, ".spec/requirements/REQ-002.md", _req(doc_id="REQ-002"))
        base = self.commit(self.root, "base", ".")
        _write(self.root, ".spec/requirements/REQ-002.md", _req(doc_id="REQ-002", title="次の版"))
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "draft", ".")
        _write(self.root, ".spec/requirements/REQ-002.md", _req(doc_id="REQ-002"))
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        # 端点（基準版とHEAD）の文書と、途中のコミットのREQ-001は取得し、途中のコミットのREQ-002だけを欠けさせる。
        for rev in (f"{base}:{REQ_PATH}", f"HEAD~1:{REQ_PATH}"):
            _git(clone, "cat-file", "-p", rev)
        self.detach_origin()
        self.assertIn(_git(clone, "rev-parse", "HEAD~1:.spec/requirements/REQ-002.md"), self.missing(clone))
        result = check_mod.run(
            parse_argv(["check", "--full", "--base", base, "--format", "json"]), str(clone), self.env
        )[0]
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", HISTORY_SUMMARY)])


class GitCallCountTests(_Repo):
    """違反の候補がない場合は、途中のコミットを読まず、Gitの呼出しが増えない（ADR-072の`Consequences`、`check` §5）。"""

    def build(self, *, change_title: bool, config: str = CONFIG) -> str:
        _write(self.root, ".spec/bitz.yaml", config)
        _write(self.root, REQ_PATH, _req())
        _write(self.root, ".spec/technical/TECH-001.md", _tech())
        base = self.commit(self.root, "base", ".spec")
        for i in range(3):
            _write(self.root, ".spec/technical/TECH-001.md", _tech(title="出力の制約", status="approved") + f"\n補足{i}。\n")
            self.commit(self.root, f"edit {i}", ".spec")
        if change_title:
            _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        return base

    def count_git_processes(self, *argv: str) -> tuple[int, dict]:
        calls = []
        real_run, real_popen = subprocess.run, subprocess.Popen

        def run(args, *a, **kw):
            calls.append(list(args))
            return real_run(args, *a, **kw)

        class Popen(real_popen):  # type: ignore[misc, valid-type]
            def __init__(self, args, *a, **kw):
                calls.append(list(args))
                super().__init__(args, *a, **kw)

        with mock.patch.object(subprocess, "run", run), mock.patch.object(subprocess, "Popen", Popen):
            result = self.check(*argv)
        return len(calls), result

    def test_no_candidate_does_not_add_git_calls(self):
        base = self.build(change_title=False)
        with_history, result = self.count_git_processes("--full", "--base", base)
        self.assertEqual(self.protection(result), [])
        with mock.patch.object(check_mod, "_new_history", lambda *a, **kw: None):
            without_history, _ = self.count_git_processes("--full", "--base", base)
        self.assertEqual(with_history, without_history)

    def test_history_is_not_touched_without_candidates(self):
        base = self.build(change_title=False)
        created: list[approvedhistory.History] = []
        real = check_mod._new_history

        def spy(*a, **kw):
            history = real(*a, **kw)
            created.append(history)
            return history

        with mock.patch.object(check_mod, "_new_history", spy):
            self.check("--full", "--base", base)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].git_calls, 0)

    def test_candidate_reads_history(self):
        # 対照: 違反の候補があれば途中のコミットを読む（Gitの呼出しが増える）。
        base = self.build(change_title=True)
        with_history, result = self.count_git_processes("--full", "--base", base)
        self.assertEqual(self.protection(result), [(REQ_PATH, "title", SUMMARY)])
        with mock.patch.object(check_mod, "_new_history", lambda *a, **kw: None):
            without_history, _ = self.count_git_processes("--full", "--base", base)
        self.assertGreater(with_history, without_history)

    def test_disabled_protection_does_not_read_history(self):
        # 基準版と現在版の両方の設定で`false`と明示した場合だけ無効（ADR-082の決定4）。
        base = self.build(change_title=True, config=CONFIG + "safety:\n  protectApprovedRequirements: false\n")
        created: list[approvedhistory.History] = []
        real = check_mod._new_history

        def spy(*a, **kw):
            history = real(*a, **kw)
            created.append(history)
            return history

        with mock.patch.object(check_mod, "_new_history", spy):
            result = self.check("--full", "--base", base)
        self.assertEqual(self.protection(result), [])
        self.assertTrue(all(h is None or h.git_calls == 0 for h in created))


class HistoryCommitCountTests(_Repo):
    """`limits.historyCommitCount`: `HEAD`から到達でき基準版から到達できないコミットの数が上限より大きければ完全には読めない（§4.1）。"""

    def build(self, limit: int) -> str:
        _write(self.root, ".spec/bitz.yaml", CONFIG + f"limits:\n  historyCommitCount: {limit}\n")
        _write(self.root, REQ_PATH, _req())
        base = self.commit(self.root, "base", ".spec")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査", status="draft"))
        self.commit(self.root, "draft", ".spec")
        _write(self.root, "note.txt", "メモ\n")
        self.commit(self.root, "note", "note.txt")
        _write(self.root, REQ_PATH, _req(title="変更後の文書検査"))
        self.commit(self.root, "approve", ".spec")
        return base

    def test_count_equal_to_the_limit_is_read(self):
        base = self.build(3)
        self.assertEqual(self.protection(self.check("--full", "--base", base)), [])

    def test_count_above_the_limit_keeps_the_violation(self):
        base = self.build(2)
        self.assertEqual(
            self.protection(self.check("--full", "--base", base)), [(REQ_PATH, "title", HISTORY_SUMMARY)]
        )

    def test_empty_history_ignores_the_limit(self):
        # 基準版が`HEAD`と同じなら途中のコミットはなく、上限に関係なく端点の比較だけで判定する（通常の文言）。
        self.build(1)
        _write(self.root, REQ_PATH, _req(title="さらに変えた文書検査"))
        self.assertEqual(self.protection(self.check("--full", "--base", "HEAD")), [(REQ_PATH, "title", SUMMARY)])


class AllWorkspacesProtectionSettingTests(_Repo):
    """`--all-workspaces`では、各ワークスペースの設定の`safety.protectApprovedRequirements`で保護の有無を決める。"""

    def test_member_setting_disables_only_that_member(self):
        root_yaml = CONFIG + (
            "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            "    - id: api\n      path: services/api\n"
        )
        _write(self.root, ".spec/bitz.yaml", root_yaml)
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\nsafety:\n  protectApprovedRequirements: false\n")
        _write(self.root, "services/api/.spec/bitz.yaml", CONFIG + "workspace:\n  id: api\n")
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", _req(doc_id="REQ-010"))
        _write(self.root, "services/api/.spec/technical/TECH-020.md", _tech(doc_id="TECH-020"))
        base = self.commit(self.root, "base", ".")
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", _req(doc_id="REQ-010", title="変更後の文書検査"))
        _write(self.root, "services/api/.spec/technical/TECH-020.md", _tech(doc_id="TECH-020", title="改訂した出力の制約"))
        self.commit(self.root, "change", ".")
        result = self.check("--all-workspaces", "--base", base)
        found = {
            ws["id"]: [(d["source"]["path"], d["source"].get("key"), d["summary"]) for d in ws["diagnostics"] if d["code"] == CODE]
            for ws in result["workspaces"]
        }
        self.assertEqual(
            found,
            {"platform": [], "web": [], "api": [(".spec/technical/TECH-020.md", "title", TECH_SUMMARY)]},
        )


class BlobReaderMaxBytesTests(_Repo):
    """`git cat-file --batch`で上限を超えるオブジェクトを読み捨て、続く要求を正しく読む（途中のコミットの`specBytes`）。"""

    def test_large_object_is_discarded_and_following_reads_stay_aligned(self):
        _write(self.root, "big.txt", "x" * 200_000)
        _write(self.root, "small.txt", "small\n")
        self.commit(self.root, "files", ".")
        big = _git(self.root, "rev-parse", "HEAD:big.txt")
        small = _git(self.root, "rev-parse", "HEAD:small.txt")
        with gitutil.BlobReader("git", str(self.root), self.env) as reader:
            self.assertEqual(reader.read_object(big, max_bytes=1000), ("blob", None))
            self.assertEqual(reader.read_object(small, max_bytes=1000), ("blob", b"small\n"))
            self.assertEqual(reader.read_object(big, max_bytes=200_000), ("blob", b"x" * 200_000))
            self.assertEqual(reader.read(small), b"small\n")


if __name__ == "__main__":
    unittest.main()
