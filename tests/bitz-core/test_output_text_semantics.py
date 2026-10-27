"""診断の出力文言の意味（表記規則 §3.5の7「同じ条件IDの診断は操作によらず同じ文型」）の単体試験。

文言の根拠は`docs/02.設計書/10_決定記録/ADR-062_*.md` Decision 2と`fixtures/conformance/Coreの出力文言のレビュー記録.md`
のPR-3の節で管理者が承認した文言であり、Coreの出力を写したものではない。
対象は次の5点。

- `CTX-STATE-001`: すべての経路が文型`{doc_id}は状態{status}のため目的{purpose}に適用できません`を使う。
  目的`implement`で`cancelled`のTASKを起点にした場合に目的が`verify`と誤って出ない。
- `CTX-COVERAGE-TEST-001`: `context`と`verify`で同じ文言になる。
- `CTX-RELATION-TYPE-001`: 承認されていないADRへの`requires`にだけ状態を添え、種別の組合せの誤りは変えない。
- `CTX-TASK-DEPENDENCY-001`: 先行TASKの状態を差し込み、`suggestedAction`を持つ。
"""

import os
import subprocess
import tempfile
import unittest

from bitz import context as context_mod
from bitz import document as doc_mod
from bitz import relations as rel_mod
from bitz import targetexpand as te_mod
from bitz import verify as verify_mod
from bitz.cliargs import ParsedArgs, parse_argv
from bitz.textrender import render_verify_text

_NO_GIT_ENV = {"PATH": "/dev/null"}


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


_BITZ_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_BITZ_YAML_VERIFY = _BITZ_YAML + 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'


def _req(doc_id: str, status: str = "approved", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 検査対象
status: {status}
{extra_frontmatter}---

# {doc_id} 検査対象

## Intent

意図。

## Acceptance Criteria

- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

未証明。
"""


def _tech(doc_id: str, status: str = "approved", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 技術契約
status: {status}
{extra_frontmatter}---

# {doc_id} 技術契約

## Context

規範文を持たない。
"""


def _adr(doc_id: str, status: str) -> str:
    return f"""---
id: {doc_id}
title: 判断
status: {status}
---

# {doc_id} 判断

## Context

背景。

## Decision

決定。

## Consequences

帰結。
"""


def _task(doc_id: str, status: str = "open", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 作業
status: {status}
{extra_frontmatter}---

# {doc_id} 作業

## Objective

作業する。
"""


def _expand(root: str, root_id: str, purpose: str):
    catalog = doc_mod.build_catalog(root, "root")
    id_index = rel_mod.build_id_index(catalog.entries)
    statement_index = rel_mod.build_statement_index(catalog.entries)
    return te_mod.target_expansion(root_id, purpose, id_index, statement_index)


def _run_context(root: str, root_id: str, purpose: str, fmt: str = "json"):
    single = {"--purpose": purpose, "--detail": "standard", "--format": fmt}
    parsed = ParsedArgs(operation="context", positionals=[root_id], flags=set(), single=single, repeat={})
    return context_mod.run(parsed, root, dict(_NO_GIT_ENV))


def _run_verify(root: str, target: str, fmt: str = "json"):
    parsed = parse_argv(["verify", target, "--format", fmt])
    return verify_mod.run(parsed, root, dict(os.environ))


def _init_repo(root: str) -> None:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, env=env, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
        cwd=root, env=env, check=True,
    )


def _by_code(result: dict, code: str) -> list[dict]:
    return [d for d in result["diagnostics"] if d["code"] == code]


class StateInapplicableTextTests(unittest.TestCase):
    """A: `CTX-STATE-001`はどの経路でも文型`{doc_id}は状態{status}のため目的{purpose}に適用できません`にする。"""

    def _cancelled_root(self, root: str) -> None:
        _write(root, ".spec/bitz.yaml", _BITZ_YAML)
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, ".spec/tasks/TASK-001.md",
               _task("TASK-001", "cancelled", "relations:\n  addresses: [REQ-001:AC-01]\n"))

    def test_cancelled_task_root_reports_the_operation_purpose(self):
        # 修正前は起点が`cancelled`のTASKだと、目的によらず「verifyに適用できません」と出ていた。
        for purpose in ("implement", "verify"):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as root:
                self._cancelled_root(root)
                result, _exit = _run_context(root, "TASK-001", purpose)
                diags = _by_code(result, "CTX-STATE-001")
                self.assertEqual(len(diags), 1)
                self.assertEqual(diags[0]["summary"], f"TASK-001は状態cancelledのため目的{purpose}に適用できません")

    def test_cancelled_task_root_in_verify_operation(self):
        with tempfile.TemporaryDirectory() as root:
            self._cancelled_root(root)
            _write(root, ".spec/bitz.yaml", _BITZ_YAML_VERIFY)
            result, _exit = _run_verify(root, "TASK-001")
            diags = _by_code(result["targetResults"][0], "CTX-STATE-001")
            self.assertEqual([d["summary"] for d in diags], ["TASK-001は状態cancelledのため目的verifyに適用できません"])

    def test_expansion_uses_one_sentence_for_every_path(self):
        # 起点のTASK（cancelled）は目的によらず同じ文型で、目的を差し込む。doneとdraftの経路は下の試験で確かめる。
        cases = [
            ("TASK-001", "implement", "cancelled", "TASK-001は状態cancelledのため目的implementに適用できません"),
            ("TASK-001", "verify", "cancelled", "TASK-001は状態cancelledのため目的verifyに適用できません"),
        ]
        for root_id, purpose, status, expected in cases:
            with self.subTest(purpose=purpose, status=status), tempfile.TemporaryDirectory() as root:
                self._cancelled_root(root)
                result = _expand(root, root_id, purpose)
                self.assertEqual([e["summary"] for e in result.errors if e["code"] == "CTX-STATE-001"], [expected])

    def test_done_task_root_in_implement(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _BITZ_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/tasks/TASK-001.md", _task("TASK-001", "done", "relations:\n  addresses: [REQ-001:AC-01]\n"))
            result = _expand(root, "TASK-001", "implement")
            self.assertEqual([e["summary"] for e in result.errors], ["TASK-001は状態doneのため目的implementに適用できません"])

    def test_inapplicable_dependency_document_uses_its_own_status(self):
        for purpose in ("implement", "verify"):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as root:
                _write(root, ".spec/bitz.yaml", _BITZ_YAML)
                _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
                _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002", "draft"))
                _write(root, ".spec/tasks/TASK-001.md",
                       _task("TASK-001", "open", "relations:\n  addresses: [REQ-001:AC-01, REQ-002:AC-01]\n"))
                result = _expand(root, "TASK-001", purpose)
                self.assertEqual(
                    [e["summary"] for e in result.errors if e["code"] == "CTX-STATE-001"],
                    [f"REQ-002は状態draftのため目的{purpose}に適用できません"],
                )


class CoverageTestTextTests(unittest.TestCase):
    """B: `CTX-COVERAGE-TEST-001`は`context`と`verify`で同じ文言にする。"""

    EXPECTED = "対象規範文MUST REQ-001:AC-01にテスト対応がありません"

    def test_context_and_verify_report_the_same_summary(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _BITZ_YAML_VERIFY)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _init_repo(root)
            ctx_verify, _ = _run_context(root, "REQ-001", "verify")
            ctx_implement, _ = _run_context(root, "REQ-001", "implement")
            ver, _ = _run_verify(root, "REQ-001")
        summaries = {
            "context-verify": [d["summary"] for d in _by_code(ctx_verify, "CTX-COVERAGE-TEST-001")],
            "context-implement": [d["summary"] for d in _by_code(ctx_implement, "CTX-COVERAGE-TEST-001")],
            "verify": [d["summary"] for d in _by_code(ver["targetResults"][0], "CTX-COVERAGE-TEST-001")],
        }
        for name, value in summaries.items():
            self.assertEqual(value, [self.EXPECTED], name)

    def test_should_modality_uses_the_same_sentence(self):
        from bitz import messages

        self.assertEqual(
            messages.coverage_test_untested("SHOULD", "REQ-001:AC-02"),
            "対象規範文SHOULD REQ-001:AC-02にテスト対応がありません",
        )
        self.assertEqual(
            messages.verify_coverage_untested("SHOULD", "REQ-001:AC-02"),
            messages.coverage_test_untested("SHOULD", "REQ-001:AC-02"),
        )


class RelationTypeTextTests(unittest.TestCase):
    """C: 承認されていないADRへの`requires`にだけ状態を添える。種別の組合せの誤りは変えない。"""

    def _context_types(self, root: str, root_id: str, purpose: str = "implement") -> list[str]:
        result, _exit = _run_context(root, root_id, purpose)
        return [d["summary"] for d in _by_code(result, "CTX-RELATION-TYPE-001")]

    def test_non_accepted_adr_carries_its_status(self):
        for status in ("proposed", "rejected", "superseded"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                _write(root, ".spec/bitz.yaml", _BITZ_YAML)
                _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
                _write(root, ".spec/decisions/ADR-001.md", _adr("ADR-001", status))
                _write(root, ".spec/tasks/TASK-001.md",
                       _task("TASK-001", "open", "relations:\n  requires: [ADR-001]\n  addresses: [REQ-001:AC-01]\n"))
                self.assertEqual(
                    self._context_types(root, "TASK-001"),
                    [f"TASKから状態{status}のADRへの関係型requiresは許可されません"],
                )

    def test_non_accepted_adr_from_req_in_expansion_path(self):
        # 展開（`targetexpand`）の経路（`_adr_requires_type_errors`）と、関係の検査（`relations`）の経路が同じ文言を返す。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _BITZ_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", extra_frontmatter="relations:\n  requires: [ADR-001]\n"))
            _write(root, ".spec/decisions/ADR-001.md", _adr("ADR-001", "proposed"))
            self.assertEqual(
                self._context_types(root, "REQ-001"), ["REQから状態proposedのADRへの関係型requiresは許可されません"]
            )

    def test_kind_mismatch_keeps_the_kind_sentence(self):
        # REQはTASKを`requires`できない（種別の誤り）。状態は添えない。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _BITZ_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", extra_frontmatter="relations:\n  requires: [TASK-001]\n"))
            _write(root, ".spec/tasks/TASK-001.md", _task("TASK-001", "open"))
            self.assertEqual(
                self._context_types(root, "REQ-001"), ["REQからTASKへの関係型requiresは許可されません"]
            )

    def test_accepted_adr_requires_is_not_reported(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _BITZ_YAML)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/decisions/ADR-001.md", _adr("ADR-001", "accepted"))
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", "open", "relations:\n  requires: [ADR-001]\n  addresses: [REQ-001:AC-01]\n"))
            self.assertEqual(self._context_types(root, "TASK-001"), [])

    def test_summary_helper(self):
        # 種別の組合せが許可されない関係と、ADR以外の参照先は、状態を添えない。
        class _Entry:
            def __init__(self, kind: str, status: str) -> None:
                self.kind = kind
                self.status = status

        self.assertEqual(
            rel_mod.type_mismatch_summary(_Entry("TASK", "open"), "requires", _Entry("ADR", "proposed")),
            "TASKから状態proposedのADRへの関係型requiresは許可されません",
        )
        self.assertEqual(
            rel_mod.type_mismatch_summary(_Entry("TASK", "open"), "requires", _Entry("REQ", "approved")),
            "TASKからREQへの関係型requiresは許可されません",
        )
        self.assertEqual(
            rel_mod.type_mismatch_summary(_Entry("TASK", "open"), "addresses", _Entry("ADR", "proposed")),
            "TASKからADRへの関係型addressesは許可されません",
        )


class TaskDependencyTextTests(unittest.TestCase):
    """D・E: 先行TASKの状態を差し込み、`suggestedAction`を持つ。未完了も`cancelled`も同じ文型。"""

    def _setup(self, root: str, status: str, bitz_yaml: str = _BITZ_YAML) -> None:
        _write(root, ".spec/bitz.yaml", bitz_yaml)
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, ".spec/tasks/TASK-001.md",
               _task("TASK-001", "open", "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"))
        _write(root, ".spec/tasks/TASK-002.md", _task("TASK-002", status))

    def test_context_reports_status_and_suggested_action(self):
        for status in ("open", "cancelled"):
            for purpose in ("implement", "verify"):
                with self.subTest(status=status, purpose=purpose), tempfile.TemporaryDirectory() as root:
                    self._setup(root, status)
                    result, _exit = _run_context(root, "TASK-001", purpose)
                    diags = _by_code(result, "CTX-TASK-DEPENDENCY-001")
                    self.assertEqual(len(diags), 1)
                    self.assertEqual(diags[0]["summary"], f"先行するTASK-002が状態{status}で、状態doneではありません")
                    self.assertEqual(
                        diags[0]["suggestedAction"],
                        "先行するTASK-002を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください",
                    )

    def test_verify_reports_status_and_suggested_action(self):
        for status in ("open", "cancelled"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                self._setup(root, status, _BITZ_YAML_VERIFY)
                result, _exit = _run_verify(root, "TASK-001")
                diags = _by_code(result["targetResults"][0], "CTX-TASK-DEPENDENCY-001")
                self.assertEqual(len(diags), 1)
                self.assertEqual(diags[0]["summary"], f"先行するTASK-002が状態{status}で、状態doneではありません")
                self.assertEqual(
                    diags[0]["suggestedAction"],
                    "先行するTASK-002を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください",
                )

    def test_text_output_shows_suggested_action_line(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root, "cancelled", _BITZ_YAML_VERIFY)
            result, _exit = _run_verify(root, "TASK-001")
        text = render_verify_text(result)
        self.assertIn(
            "  -> 先行するTASK-002を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください", text
        )

    def test_done_prerequisite_has_no_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root, "done")
            result, _exit = _run_context(root, "TASK-001", "implement")
            self.assertEqual(_by_code(result, "CTX-TASK-DEPENDENCY-001"), [])


if __name__ == "__main__":
    unittest.main()
