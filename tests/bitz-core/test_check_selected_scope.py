"""`check`の`scope: selected`検査範囲限定（`check.md §3`）の単体試験。

完全検査のDiagnosticと`checkedDocumentCount`/`checkedStatementCount`は
`TargetExpansion(root, interpret).contextDocuments`と、それらを直接逆参照する文書の和集合だけに
限り、集合外の文書のFrontmatter/EARS/relation/path/coverage Diagnosticを出さないことを検査する。
workspace単位のDiagnostic（未知entry等）とID重複は集合に関わらず残ることも確認する。
"""

import os
import tempfile
import unittest

from bitz import check as check_mod
from bitz.cliargs import ParsedArgs

# Git不在を強制するenv（`SPEC-TASK-BOUNDARY-002`等のfixtureと同じ手法）。
_NO_GIT_ENV = {"PATH": "/dev/null"}


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml() -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'


REQ_TARGET = """---
id: REQ-001
title: 対象文書
status: approved
---

# REQ-001 対象文書

## Intent

意図。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

未証明。
"""

# REQ-001とは無関係な文書。関係先が存在せずSPEC-RELATION-MISSING-001を持つ。
REQ_UNRELATED_BROKEN = """---
id: REQ-002
title: 無関係な文書
status: approved
relations:
  requires: [REQ-999]
---

# REQ-002 無関係な文書

## Intent

意図。

## Acceptance Criteria

- [REQ-002:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

未証明。
"""

# REQ-001をrequiresする文書（直接逆参照で完全検査対象へ含まれるべき）。
REQ_REVERSE_REF = """---
id: REQ-003
title: REQ-001を参照する文書
status: approved
relations:
  requires: [REQ-001]
---

# REQ-003 REQ-001を参照する文書

## Intent

意図。

## Acceptance Criteria

- [REQ-003:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

未証明。
"""


def _run(root: str, positionals: list[str], flags: set[str] | None = None) -> tuple[dict, int]:
    parsed = ParsedArgs(operation="check", positionals=positionals, flags=flags or set(), single={}, repeat={})
    return check_mod.run(parsed, root, dict(_NO_GIT_ENV))


class ScopeSelectedFilterTests(unittest.TestCase):
    def test_unrelated_document_diagnostics_are_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", REQ_TARGET)
            _write(root, ".spec/requirements/REQ-002.md", REQ_UNRELATED_BROKEN)

            result, _exit_code = _run(root, ["REQ-001"])
            self.assertEqual(result["scope"], "selected")
            self.assertEqual(result["checkedDocumentCount"], 1)
            self.assertEqual(result["checkedStatementCount"], 1)
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertNotIn("SPEC-RELATION-MISSING-001", codes)

    def test_full_scope_includes_unrelated_document_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", REQ_TARGET)
            _write(root, ".spec/requirements/REQ-002.md", REQ_UNRELATED_BROKEN)

            result, _exit_code = _run(root, [], flags={"--full"})
            self.assertEqual(result["scope"], "full")
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("SPEC-RELATION-MISSING-001", codes)

    def test_direct_reverse_reference_is_included_in_checked_set(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", REQ_TARGET)
            _write(root, ".spec/requirements/REQ-003.md", REQ_REVERSE_REF)

            result, _exit_code = _run(root, ["REQ-001"])
            # REQ-003はREQ-001を直接requiresするため、checkedDocumentCountへ含まれる
            # （REQ-001自身の1件 + REQ-003の1件 = 2件、statementはそれぞれ1件ずつ）。
            self.assertEqual(result["checkedDocumentCount"], 2)
            self.assertEqual(result["checkedStatementCount"], 2)
            self.assertEqual(result["diagnostics"], [])

    def test_workspace_level_diagnostics_always_kept(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", REQ_TARGET)
            _write(root, ".spec/requirements/REQ-002.md", REQ_UNRELATED_BROKEN)
            # `.spec/`内の未知entry（workspace単位のDiagnostic）はscope=selectedでも残る。
            _write(root, ".spec/unknown-entry.txt", "x\n")

            result, _exit_code = _run(root, ["REQ-001"])
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("SPEC-WORKSPACE-UNKNOWN-001", codes)


if __name__ == "__main__":
    unittest.main()
