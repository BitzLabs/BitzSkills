"""`{tests}`展開後のargvの要素の上限と、フロントマターのパスの形式の文言の単体試験（確認事項 C84・C85）。

欠陥（C84）: `verify`は、`{tests}`展開後のargvの1要素がバイト数上限（32 KiB）を超えたときも、総和の上限の文言
「{tests}展開後のargvがバイト数上限1 MiBを超えます」を返し、上限の値が実際と違っていた。
欠陥（C85）: フロントマターのパス（`implements`、`changes`、`tests[].path`）が字句の規則で拒否されたとき、型の不正と同じ
「フロントマターのフィールド{key}は文字列の配列が必要です」を返し、拒否の理由が分からなかった。

規範:
- 診断レジストリ: `VERIFY-ARGV-EXPANDED-LIMIT`は、`{tests}`を展開した後の引数列が要素数またはバイト数の上限を超過した場合。
  `FM-FIELD-TYPE`は、フロントマターのフィールドの型または値域の不正。
- ワークスペース・設定仕様 §9: 仕様文書に記録するパスは、絶対パス、`..`、NUL、globの文字`*?[]`を禁止する。
- 表記規則 §3.5の7: 同じ条件IDの中で原因の内訳が異なる診断は、内訳ごとに文型を分けてよい。
- 文言は出力文言のレビュー記録でユーザーが承認した（ADR-062）。

この試験の対象:
1. 要素の上限を超えたときは「{tests}展開後のargvの要素がバイト数上限32 KiBを超えます」、総和の上限を超えたときは
   今の「{tests}展開後のargvがバイト数上限1 MiBを超えます」を返す（実ファイルで32 KiBの要素は作れないので、上限の定数を差し替える）。
2. フロントマターのパスの字句の違反（globの文字、絶対パス、`.`、`..`、NUL、空文字列）は「フロントマターのフィールド{key}のパスの形式が不正です」。
3. 型の不正（配列でない、文字列でない要素、文字列でない`tests[].path`）は、今の型の不正の文言のまま。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import frontmatter as fm
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY_CONFIG = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
REQ = (
    "---\nid: REQ-001\ntitle: 文書\nstatus: approved\n"
    "tests:\n  - path: tests/test_long_name_for_limit.py\n    covers: [REQ-001:AC-01]\n    command: default\n---\n\n"
    "# REQ-001 文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
    "## Verification\n\n未証明。\n"
)

ELEMENT_SUMMARY = "{tests}展開後のargvの要素がバイト数上限32 KiBを超えます"
TOTAL_SUMMARY = "{tests}展開後のargvがバイト数上限1 MiBを超えます"
PATH_FORM = "フロントマターのフィールド{key}のパスの形式が不正です"


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


class ExpandedArgvLimitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY_CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "tests/test_long_name_for_limit.py", "x\n")
        env = {**os.environ, **_GIT_ENV}
        for args in (["init", "-q", "--initial-branch=main"], ["add", "."],
                     ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"]):
            subprocess.run(["git", *args], cwd=self.root, env=env, check=True, capture_output=True)

    def blocked_summaries(self) -> list[str]:
        result, code = verify_mod.run(parse_argv(["verify", "REQ-001", "--format", "json"]), str(self.root), dict(os.environ))
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        return [d["summary"] for d in result["diagnostics"] if d["code"] == "SPEC-VERIFY-BLOCKED-001"]

    def test_element_limit_reports_the_element_limit(self):
        # 展開した要素（`tests/test_long_name_for_limit.py`、33バイト）だけが上限を超える。
        with mock.patch.object(verify_mod, "_ARGV_ELEMENT_LIMIT", 20):
            self.assertEqual(self.blocked_summaries(), [ELEMENT_SUMMARY])

    def test_total_limit_reports_the_total_limit(self):
        with mock.patch.object(verify_mod, "_ARGV_TOTAL_LIMIT", 40):
            self.assertEqual(self.blocked_summaries(), [TOTAL_SUMMARY])

    def test_within_limits_is_not_blocked(self):
        result, code = verify_mod.run(parse_argv(["verify", "REQ-001", "--format", "json"]), str(self.root), dict(os.environ))
        self.assertNotIn("SPEC-VERIFY-BLOCKED-001", [d["code"] for d in result["diagnostics"]], result)


def _req(**fields):
    return {"id": "REQ-001", "title": "件名", "status": "approved", **fields}


def _task(**fields):
    return {"id": "TASK-001", "title": "件名", "status": "open", **fields}


class FrontmatterPathFormTests(unittest.TestCase):
    BAD_PATHS = ("src/a]b.py", "src/a*b.py", "src/a?b.py", "src/a[b.py", "/abs/a.py", "src/../a.py", "./a.py", "src/a\x00b.py", "")

    def summaries(self, value, kind):
        return [(i.code, i.key, i.summary) for i in fm.validate(value, kind).hard]

    def test_lexical_violations_report_the_path_form(self):
        for path in self.BAD_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.summaries(_req(implements=[path]), "REQ"),
                                 [("SPEC-FM-SCHEMA-001", "implements", PATH_FORM.format(key="implements"))])
                self.assertEqual(self.summaries(_task(changes=["src/ok.py", path]), "TASK"),
                                 [("SPEC-FM-SCHEMA-001", "changes", PATH_FORM.format(key="changes"))])
                value = _req(tests=[{"path": path, "covers": ["REQ-001:AC-01"]}])
                self.assertEqual(self.summaries(value, "REQ"),
                                 [("SPEC-FM-SCHEMA-001", "tests[0].path", PATH_FORM.format(key="tests[0].path"))])

    def test_type_errors_keep_the_type_wording(self):
        cases = (
            (_req(implements="src/a.py"), "REQ", "implements", "フロントマターのフィールドimplementsは文字列の配列が必要です"),
            (_task(changes=42), "TASK", "changes", "フロントマターのフィールドchangesは文字列の配列が必要です"),
            # 文字列でない要素と字句の違反が並ぶときは、型の不正を返す。
            (_req(implements=[1, "src/a]b.py"]), "REQ", "implements", "フロントマターのフィールドimplementsは文字列の配列が必要です"),
            (_req(implements=["src/a]b.py", 1]), "REQ", "implements", "フロントマターのフィールドimplementsは文字列の配列が必要です"),
            (_task(changes=["/abs", None]), "TASK", "changes", "フロントマターのフィールドchangesは文字列の配列が必要です"),
            (_req(tests=[{"path": 3, "covers": ["REQ-001:AC-01"]}]), "REQ", "tests[0].path",
             "フロントマターのフィールドtests[0].pathは文字列が必要です"),
        )
        for value, kind, key, summary in cases:
            with self.subTest(key=key, value=value):
                self.assertEqual(self.summaries(value, kind), [("SPEC-FM-SCHEMA-001", key, summary)])


if __name__ == "__main__":
    unittest.main()
