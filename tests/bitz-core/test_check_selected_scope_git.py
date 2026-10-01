"""`scope: selected`（明示対象の`check`）でのGit基準版との比較（状態遷移・承認済み要求の保護）の単体試験。

検収指摘への対応: `check.md §5`「同じ基準版を対象選択、状態遷移、削除の検出、承認済み要求の保護、TASK境界へ
使用」は範囲を限定しないため、明示対象の`check`でも完全検査の対象（`full_check_ids`）に属する文書へは
状態遷移・承認済み要求の保護を適用し、対象外の文書には適用しないことを確認する。
"""

import os
import subprocess
import tempfile
import unittest

from bitz import check as check_mod
from bitz.cliargs import ParsedArgs


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml() -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'


def _task(doc_id: str, title: str, status: str) -> str:
    return f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n"


def _req(doc_id: str, title: str, status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n"
        f"# {doc_id} {title}\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _run(root, positionals):
    parsed = ParsedArgs(operation="check", positionals=positionals, flags=set(), single={"--base": "HEAD"}, repeat={})
    return check_mod.run(parsed, root, dict(os.environ))


class ExplicitTargetStateTransitionTests(unittest.TestCase):
    def test_target_documents_forbidden_transition_is_reported(self):
        # (a) 対象文書自身の禁止遷移（`done -> open`）は明示した`check`で報告される。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/tasks/TASK-001.md", _task("TASK-001", "対象", "done"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            _write(root, ".spec/tasks/TASK-001.md", _task("TASK-001", "対象", "open"))

            result, _exit_code = _run(root, ["TASK-001"])
            self.assertEqual(result["scope"], "selected")
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("SPEC-STATE-TRANSITION-001", codes)

    def test_unrelated_document_forbidden_transition_is_not_reported(self):
        # (b) 対象外（無関係）の文書の禁止遷移は明示した`check`の対象へ含まれず報告されない。
        # TASKだと明示対象のTASK境界検査（無関係なパスの変更）が別の診断を出してしまうため、
        # 互いに無関係なTECH 2件で検査する。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _task("TECH-001", "無関係", "approved"))
            _write(root, ".spec/technical/TECH-002.md", _task("TECH-002", "対象", "approved"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            # TECH-001（対象外）は`approved`から`rejected`への禁止遷移。TECH-002（対象）は無変更。
            _write(root, ".spec/technical/TECH-001.md", _task("TECH-001", "無関係", "rejected"))

            result, _exit_code = _run(root, ["TECH-002"])
            self.assertEqual(result["scope"], "selected")
            self.assertEqual(result["diagnostics"], [])

    def test_target_approved_req_meaning_change_is_reported(self):
        # (c) 対象の状態`approved`のREQの`title`変更（状態を戻していない）は明示した`check`で保護される。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", "旧title"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", "新title"))

            result, _exit_code = _run(root, ["REQ-001"])
            self.assertEqual(result["scope"], "selected")
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("SPEC-SAFETY-APPROVED-001", codes)

    def test_deleted_unrelated_document_is_not_reported_as_deletion(self):
        # 明示した`check`の対象外の仕様文書の削除は、削除された文書IDが`full_check_ids`へ入り得ないため
        # 報告されない（検収指摘: 明示対象の`check`では`CTX-ROOT-MISSING-001`の管轄で、削除
        # の診断そのものを生成しない）。TASKだとTASK境界検査の無関係なパスが別の
        # 診断を出すため、互いに無関係なTECHで検査する。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _task("TECH-001", "対象", "approved"))
            _write(root, ".spec/technical/TECH-002.md", _task("TECH-002", "無関係", "approved"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            os.remove(os.path.join(root, ".spec", "technical", "TECH-002.md"))

            result, _exit_code = _run(root, ["TECH-001"])
            self.assertEqual(result["scope"], "selected")
            self.assertEqual(result["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
