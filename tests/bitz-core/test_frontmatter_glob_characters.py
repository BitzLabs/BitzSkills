"""フロントマターのパスが拒否するglobの文字の単体試験（確認事項 C43）。

欠陥: フロントマターのパス（`implements`、`changes`、`tests[].path`）は、globの文字を`*?[`の3つとして判定し、閉じ括弧`]`を含むパスを
受け付けていた。メンバーのパス、除外のパス、コマンドの`cwd`は`*?[]`の4つを拒否しており、同じ「glob」の扱いが分かれていた。

規範:
- ワークスペース・設定仕様 §9: 仕様文書に記録するパスは、絶対パス、`..`、NUL、globの文字`*?[]`を禁止する。
- 文書種別・本文テンプレート: `changes`は、globの文字`*?[]`、絶対パス、`..`を禁止する。
- `frontmatter.schema.json`の`pathString`: `*?[]`のいずれかを含む文字列に適合しない。
- 複合ワークスペース仕様 §2・§5.1、ワークスペース・設定仕様 §6: メンバーのパス、除外のパス、`cwd`の字句も同じ4つの文字を拒否する。

この試験の対象:
1. `implements`（REQ）、`changes`（TASK）、`tests[].path`（REQ）は、4つの文字のどれを含んでも`SPEC-FM-SCHEMA-001`で拒否する。
2. 4つの文字を含まないパスは受理する（対照）。
3. Coreの判定が`frontmatter.schema.json`の`pathString`のパターンと一致する。
4. フロントマター、メンバーと除外のパス、`cwd`が、同じ4つの文字を拒否する。
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

GLOB_CHARACTERS = "*?[]"
SAMPLES = ("src/a{}b.py", "src/{}/app.py", "{}")


def _req(**fields):
    return {"id": "REQ-001", "title": "件名", "status": "approved", **fields}


def _task(**fields):
    return {"id": "TASK-001", "title": "件名", "status": "open", **fields}


def _cases(path: str):
    """``path``を各フィールドに置いた``(名前, 値, 種別, 期待する診断のキー)``。"""

    return (
        ("implements", _req(implements=[path]), "REQ", "implements"),
        ("changes", _task(changes=[path]), "TASK", "changes"),
        ("tests.path", _req(tests=[{"path": path, "covers": ["REQ-001:AC-01"]}]), "REQ", "tests[0].path"),
    )


class FrontmatterGlobCharacterTests(unittest.TestCase):
    def test_each_glob_character_is_rejected_in_every_path_field(self):
        for ch in GLOB_CHARACTERS:
            for sample in SAMPLES:
                path = sample.format(ch)
                for name, value, kind, key in _cases(path):
                    with self.subTest(character=ch, path=path, field=name):
                        outcome = fm.validate(value, kind)
                        self.assertEqual([(i.code, i.key) for i in outcome.hard], [("SPEC-FM-SCHEMA-001", key)])

    def test_path_without_glob_characters_is_accepted(self):
        for path in ("src/app.py", "src/a-b_c.d/app.py", "src/(x)/{y}/app.py", "src/!x/app.py"):
            for name, value, kind, _key in _cases(path):
                with self.subTest(path=path, field=name):
                    self.assertEqual(fm.validate(value, kind).hard, [])


class SchemaAgreementTests(unittest.TestCase):
    def test_core_agrees_with_the_schema_path_pattern(self):
        schema = json.loads(FRONTMATTER_SCHEMA.read_text(encoding="utf-8"))
        pattern = re.compile(schema["$defs"]["pathString"]["pattern"])
        paths = [sample.format(ch) for ch in GLOB_CHARACTERS for sample in SAMPLES]
        paths += ["src/app.py", "src/(x)/{y}/app.py", "src/!x/app.py", "a]", "]", "[", "a/../b", "./a", "/abs"]
        for path in paths:
            with self.subTest(path=path):
                accepted = fm.validate(_req(implements=[path]), "REQ").hard == []
                self.assertEqual(accepted, pattern.search(path) is not None)


class SharedCharacterSetTests(unittest.TestCase):
    def test_frontmatter_member_exclude_and_cwd_reject_the_same_characters(self):
        for ch in GLOB_CHARACTERS + "{}!()^":
            path = f"apps/a{ch}b"
            with self.subTest(character=ch):
                verdicts = {
                    "frontmatter": fm.validate(_req(implements=[path]), "REQ").hard == [],
                    "member-or-exclude": multiws._path_lexically_valid(path),
                    "cwd": config_mod._cwd_lexically_valid(path),
                }
                self.assertEqual(set(verdicts.values()), {ch not in GLOB_CHARACTERS}, verdicts)


if __name__ == "__main__":
    unittest.main()
