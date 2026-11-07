"""パスの字句の規則（空のセグメント、末尾の`/`、制御文字）の単体試験（確認事項 C101〜C103）。

欠陥（C101）: フロントマターのパス（`implements`、`changes`、`tests[].path`）は、空のセグメント（`a//b`）と末尾の`/`を受け付けていた。
欠陥（C102）: 改行などの制御文字を含むパスを、Coreは受け付け、スキーマは（`.`が改行に一致しないため）拒否していた。`cwd`、メンバーのパス、
除外のパスも、NUL以外の制御文字を受け付けていた。
C103: ワークスペース・設定仕様 §9の禁止の列挙に`.`のセグメントがなかった（スキーマとCoreは拒否していた）。

規範:
- ワークスペース・設定仕様 §9: 絶対パス、`.`と`..`のセグメント、空のセグメント（`a//b`と末尾の`/`。TASKの`changes`のディレクトリの接頭辞の末尾の`/`だけを除く）、
  NULを含む制御文字（U+0000〜U+001F、U+007F）、globの文字`*?[]`を禁止する。§6の`cwd`、複合ワークスペース仕様 §2のメンバーと除外のパスも制御文字を禁止する。
- `frontmatter.schema.json`の`pathString`（`changes`は`changesPathString`）。

この試験の対象:
1. フロントマターのパスの空のセグメント、末尾の`/`、制御文字は「…のパスの形式が不正です」。TASKの`changes`の末尾の`/`1つだけは受理する。
2. Coreの判定がスキーマの2つのパターンと一致する。
3. `cwd`、メンバーと除外のパスの字句も制御文字を拒否する。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from bitz import config as config_mod
from bitz import frontmatter as fm
from bitz import multiws

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "frontmatter.schema.json"
PATH_FORM = "フロントマターのフィールド{key}のパスの形式が不正です"

CONTROL = ["\x00", "\x01", "\t", "\n", "\r", "\x1b", "\x1f", "\x7f"]
EMPTY_SEGMENTS = ["src//a.py", "src/a.py/", "src/", "src//"]
ACCEPTED = ["src/a.py", "src/a b.py", "src/é.py", "src/\x80.py", "src/(x)/a.py"]


def _req(**fields):
    return {"id": "REQ-001", "title": "件名", "status": "approved", **fields}


def _task(**fields):
    return {"id": "TASK-001", "title": "件名", "status": "open", **fields}


def _hard(value, kind):
    return [(i.code, i.key, i.summary) for i in fm.validate(value, kind).hard]


class FrontmatterPathTests(unittest.TestCase):
    def assert_rejected(self, path):
        self.assertEqual(_hard(_req(implements=[path]), "REQ"),
                         [("SPEC-FM-SCHEMA-001", "implements", PATH_FORM.format(key="implements"))])
        value = _req(tests=[{"path": path, "covers": ["REQ-001:AC-01"]}])
        self.assertEqual(_hard(value, "REQ"),
                         [("SPEC-FM-SCHEMA-001", "tests[0].path", PATH_FORM.format(key="tests[0].path"))])

    def test_empty_segments_and_trailing_slash_are_rejected(self):
        for path in EMPTY_SEGMENTS:
            with self.subTest(path=path):
                self.assert_rejected(path)

    def test_control_characters_are_rejected(self):
        for ch in CONTROL:
            for path in (f"src/a{ch}b.py", f"src/a.py{ch}", f"{ch}src/a.py"):
                with self.subTest(path=path):
                    self.assert_rejected(path)
                    self.assertEqual(_hard(_task(changes=[path]), "TASK"),
                                     [("SPEC-FM-SCHEMA-001", "changes", PATH_FORM.format(key="changes"))])

    def test_changes_accepts_only_a_single_trailing_slash(self):
        self.assertEqual(_hard(_task(changes=["src/", "src/a/", "src/a.py"]), "TASK"), [])
        for path in ("src//", "src//a/", "/", "src/./"):
            with self.subTest(path=path):
                self.assertEqual(_hard(_task(changes=[path]), "TASK"),
                                 [("SPEC-FM-SCHEMA-001", "changes", PATH_FORM.format(key="changes"))])

    def test_ordinary_paths_are_accepted(self):
        for path in ACCEPTED:
            with self.subTest(path=path):
                self.assertEqual(_hard(_req(implements=[path]), "REQ"), [])


class SchemaAgreementTests(unittest.TestCase):
    def test_core_agrees_with_both_schema_patterns(self):
        defs = json.loads(FRONTMATTER_SCHEMA.read_text(encoding="utf-8"))["$defs"]
        path_pattern = re.compile(defs["pathString"]["pattern"])
        changes_pattern = re.compile(defs["changesPathString"]["pattern"])
        samples = EMPTY_SEGMENTS + ACCEPTED + ["src/a/", "./a", "a/./b", "a/..", "/abs", "a]b", "src//a/"]
        samples += [f"src/a{ch}b.py" for ch in CONTROL] + [f"src/a.py{ch}" for ch in CONTROL]
        for path in samples:
            with self.subTest(path=path):
                implements_ok = _hard(_req(implements=[path]), "REQ") == []
                changes_ok = _hard(_task(changes=[path]), "TASK") == []
                self.assertEqual(implements_ok, path_pattern.search(path) is not None)
                self.assertEqual(changes_ok, changes_pattern.search(path) is not None)


class OtherPathLexiconTests(unittest.TestCase):
    def test_cwd_member_and_exclude_paths_reject_control_characters(self):
        for ch in CONTROL:
            path = f"apps/a{ch}b"
            with self.subTest(character=repr(ch)):
                self.assertFalse(config_mod._cwd_lexically_valid(path))
                self.assertFalse(multiws._path_lexically_valid(path))
        self.assertTrue(config_mod._cwd_lexically_valid("apps/ab"))
        self.assertTrue(multiws._path_lexically_valid("apps/ab"))


if __name__ == "__main__":
    unittest.main()
