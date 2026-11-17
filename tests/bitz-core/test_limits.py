"""上限の設定（`bitz.yaml`の`limits`、ADR-076）の単体試験。

規範:
- 安全な入出力・互換性 §4.1（`limits`のキー、絶対上限、適用範囲、文言の規則、発生元、`limits`をハッシュ値の材料に含めない）
- ワークスペース・設定仕様 §5・§6（`limits`の型と値の範囲、`multiWorkspace.exclude`の件数）
- 複合ワークスペース仕様 §10（ルートの設定だけが`limits`を持つ。`check --base`は現在版の上限を基準版にも適用する）
- `doctor` §7（`limits`を宣言した設定だけ、結果の最上位に実際に使う値を返す）
- Coreの出力文言のレビュー記録の2026-11-17の承認済みの対応表（文言）

この試験の対象:
1. 設定の検査（マッピングでない、整数でない、範囲の外、未知のキー、絶対上限ちょうど、空のマッピング）
2. 実際に使う上限の値の決定（省略したキー、適用範囲の選択、`doctor`の結果の値と順）
3. 文言の切替え（絶対上限なら今の文言、小さい値なら承認済みの文言）
4. ファイル単位の上限の適用（フロントマターの大きさの数え方を含む）と、仕様文書のファイル数の超過で`check`を止めること
5. 複合ワークスペースの適用範囲（ルートの設定をメンバーの文書へ、メンバーの設定の`limits`、単一ワークスペースは複合の次元を使わない、
   基準版のスナップショット、除外の件数）
6. `limits`がコンテキストのハッシュ値を変えないこと、出力が`PYTHONHASHSEED`に依存しないこと
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import document as doc_mod
from bitz import gitutil
from bitz import limits as limits_mod
from bitz import messages
from bitz import multiws
from bitz.cliargs import parse_argv
from bitz.config import load_config

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT_YAML = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
WEB_YAML = CONFIG + "workspace:\n  id: web\n"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

KEYS_IN_TABLE_ORDER = [
    "specBytes", "frontmatterBytes", "specFileCount", "documentStatementCount", "documentArrayItemCount",
    "inputBytes", "statementCount", "relationEdgeCount", "traceEntryCount", "commandDefinitionCount",
    "verifyBindingCount", "excludeCount", "expandedArgvCount", "expandedArgvElementBytes", "expandedArgvBytes",
]
ABSOLUTE_VALUES = {
    "specBytes": 1_048_576, "frontmatterBytes": 32_768, "specFileCount": 10_000, "documentStatementCount": 1_000,
    "documentArrayItemCount": 1_000, "inputBytes": 268_435_456, "statementCount": 100_000,
    "relationEdgeCount": 1_000_000, "traceEntryCount": 1_000_000, "commandDefinitionCount": 10_000,
    "verifyBindingCount": 10_000, "excludeCount": 100, "expandedArgvCount": 10_000,
    "expandedArgvElementBytes": 32_768, "expandedArgvBytes": 1_048_576,
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


def _commit(root: Path, message: str = "base") -> None:
    if not (root / ".git").exists():
        _git(root, "init", "-q", "--initial-branch=main")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _req(doc_id: str, statements: int = 1, status: str = "approved") -> str:
    lines = "".join(
        f"- [{doc_id}:AC-{i:02d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報{i}を出力しない。\n\n"
        for i in range(1, statements + 1)
    )
    return (
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: {status}\n---\n\n# {doc_id} REQ\n\n## Intent\n\n意図。\n\n"
        f"## Acceptance Criteria\n\n{lines}## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, statements: int = 1) -> str:
    lines = "".join(
        f"- [{doc_id}:C-{i:02d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 規則{i}を守る。\n\n"
        for i in range(1, statements + 1)
    )
    return f"---\nid: {doc_id}\ntitle: TECH\nstatus: draft\n---\n\n# {doc_id} TECH\n\n## Contract\n\n{lines}"


def _schema_errors(outcome) -> list[tuple[str, str | None, str]]:
    return [(d.code, d.source.get("key"), d.summary) for d in outcome.diagnostics]


class ConfigValidationTests(unittest.TestCase):
    """ワークスペース・設定仕様 §5の`limits`の検査。"""

    def load(self, limits_yaml: str):
        return load_config((CONFIG + limits_yaml).encode("utf-8"))

    def test_non_mapping_and_empty_value_are_type_errors(self):
        for yaml in ("limits: 1024\n", "limits:\n", "limits: [1]\n", 'limits: "a"\n'):
            with self.subTest(yaml=yaml):
                outcome = self.load(yaml)
                self.assertTrue(outcome.stop)
                self.assertEqual(
                    _schema_errors(outcome),
                    [("SPEC-CONFIG-SCHEMA-001", "limits", "設定キーlimitsはマッピングで指定してください")],
                )
                self.assertEqual(outcome.diagnostics[0].resultStatus, "error")
                self.assertIsNone(outcome.workspace_id)

    def test_invalid_values_report_the_key_and_its_range(self):
        cases = {
            "specBytes: 0": ("limits.specBytes", 1_048_576),
            "documentStatementCount: -1": ("limits.documentStatementCount", 1_000),
            "expandedArgvBytes: 1048577": ("limits.expandedArgvBytes", 1_048_576),
            "specFileCount: true": ("limits.specFileCount", 10_000),
            'statementCount: "5"': ("limits.statementCount", 100_000),
            "excludeCount: 1.5": ("limits.excludeCount", 100),
            "inputBytes: null": ("limits.inputBytes", 268_435_456),
        }
        for line, (key, maximum) in cases.items():
            with self.subTest(line=line):
                outcome = self.load(f"limits:\n  {line}\n")
                self.assertEqual(
                    _schema_errors(outcome),
                    [("SPEC-CONFIG-SCHEMA-001", key, f"設定キー{key}は1〜{maximum}の整数で指定してください")],
                )

    def test_every_invalid_key_is_reported_independently(self):
        outcome = self.load("limits:\n  specBytes: 0\n  frontmatterBytes: 40000\n")
        self.assertEqual([k for _c, k, _s in _schema_errors(outcome)], ["limits.specBytes", "limits.frontmatterBytes"])

    def test_unknown_key_is_a_warning_and_is_not_used(self):
        outcome = self.load("limits:\n  futureLimit: 1\n  memberCount: 1\n")
        self.assertFalse(outcome.stop)
        self.assertEqual(
            [(d.code, d.severity, d.source.get("key"), d.summary) for d in outcome.warnings],
            [
                ("SPEC-CONFIG-UNKNOWN-001", "warning", "limits.futureLimit", "未知の設定キーです"),
                ("SPEC-CONFIG-UNKNOWN-001", "warning", "limits.memberCount", "未知の設定キーです"),
            ],
        )
        self.assertEqual(limits_mod.from_config(outcome.config), limits_mod.ABSOLUTE)

    def test_absolute_values_and_empty_mapping_are_valid(self):
        every_key = "limits:\n" + "".join(f"  {k}: {v}\n" for k, v in ABSOLUTE_VALUES.items())
        for yaml in (every_key, "limits: {}\n", "limits:\n  specBytes: 1\n"):
            with self.subTest(yaml=yaml):
                outcome = self.load(yaml)
                self.assertFalse(outcome.stop, outcome.diagnostics)
                self.assertEqual(outcome.warnings, [])

    def test_limits_is_no_longer_an_unknown_top_level_key(self):
        outcome = self.load("limits:\n  specBytes: 2048\n")
        self.assertEqual(outcome.warnings, [])

    def test_member_reading_skips_the_value_check(self):
        outcome = load_config((CONFIG + "limits: 1024\n").encode("utf-8"), validate_limits=False)
        self.assertFalse(outcome.stop)
        self.assertIn("limits", outcome.config)


class EffectiveLimitsTests(unittest.TestCase):
    def test_absolute_table_matches_the_specification(self):
        self.assertEqual(list(limits_mod.ABSOLUTE_LIMITS), KEYS_IN_TABLE_ORDER)
        self.assertEqual(limits_mod.ABSOLUTE_LIMITS, ABSOLUTE_VALUES)
        self.assertEqual(limits_mod.ABSOLUTE.as_result(), ABSOLUTE_VALUES)

    def test_omitted_keys_use_the_absolute_limit(self):
        limits = limits_mod.from_config({"limits": {"specFileCount": 5, "expandedArgvBytes": 4096}})
        expected = dict(ABSOLUTE_VALUES, specFileCount=5, expandedArgvBytes=4096)
        self.assertEqual(limits.as_result(), expected)
        self.assertEqual(list(limits.as_result()), KEYS_IN_TABLE_ORDER)

    def test_absent_or_unusable_limits_are_absolute(self):
        for config in (None, {}, {"limits": {}}, {"limits": None}, {"limits": 5}, {"limits": {"specBytes": 0}}):
            with self.subTest(config=config):
                self.assertEqual(limits_mod.from_config(config), limits_mod.ABSOLUTE)

    def test_scope_selection(self):
        working = {"limits": {"specBytes": 100}}
        root = {"limits": {"specBytes": 200}}
        self.assertEqual(limits_mod.for_workspace(working, root, multi_active=False).specBytes, 100)
        self.assertEqual(limits_mod.for_workspace(working, root, multi_active=True).specBytes, 200)
        self.assertEqual(limits_mod.for_workspace(working, None, multi_active=True), limits_mod.ABSOLUTE)

    def test_doctor_result(self):
        self.assertIsNone(limits_mod.doctor_result({"schemaVersion": "1.0"}, True))
        self.assertIsNone(limits_mod.doctor_result({"limits": {"specBytes": 5}}, False))
        self.assertIsNone(limits_mod.doctor_result(None, True))
        self.assertEqual(limits_mod.doctor_result({"limits": {}}, True), ABSOLUTE_VALUES)
        self.assertEqual(list(limits_mod.doctor_result({"limits": {"specBytes": 5}}, True)), KEYS_IN_TABLE_ORDER)


class WordingTests(unittest.TestCase):
    """文言の切替え（§4.1、承認済みの対応表）。絶対上限のときは今の文言のまま。"""

    def test_byte_labels(self):
        absolute = limits_mod.ABSOLUTE
        small = limits_mod.Limits(specBytes=2048, frontmatterBytes=32_768, expandedArgvBytes=47)
        self.assertEqual(limits_mod.format_bytes(absolute, "specBytes", "1 MiB"), "1 MiB")
        self.assertEqual(limits_mod.format_bytes(small, "specBytes", "1 MiB"), "2,048バイト")
        # 32,768（絶対上限ちょうど）は絶対上限なので単位の表記のまま。
        self.assertEqual(limits_mod.format_bytes(small, "frontmatterBytes", "32 KiB"), "32 KiB")
        self.assertEqual(limits_mod.format_bytes(small, "expandedArgvBytes", "1 MiB"), "47バイト")

    def test_absolute_wording_is_unchanged(self):
        a = limits_mod.ABSOLUTE
        self.assertEqual(
            messages.spec_size_limit(limits_mod.format_bytes(a, "specBytes", "1 MiB")),
            "仕様文書のMarkdownが1 MiB上限を超過しました",
        )
        self.assertEqual(
            messages.frontmatter_size_limit(limits_mod.format_bytes(a, "frontmatterBytes", "32 KiB")),
            "フロントマターが32 KiB上限を超過しました",
        )
        self.assertEqual(messages.statement_count_limit(a.documentStatementCount), "1文書の規範文数が1,000上限を超過しました")
        self.assertEqual(
            messages.array_count_limit("tests", a.documentArrayItemCount),
            "1文書の関係・パスの配列の項目数が1,000上限を超過しました",
        )
        self.assertEqual(messages.spec_file_count_limit(a.specFileCount), "仕様文書のファイルが10,000件上限を超過しました")
        self.assertEqual(
            messages.verify_argv_expanded_count_limit(a.expandedArgvCount), "{tests}展開後のargvの要素数が上限10,000を超えます"
        )
        self.assertEqual(
            messages.multi_config_exclude_count(a.excludeCount), "設定キーmultiWorkspace.excludeは100件以下で指定してください"
        )
        self.assertEqual(messages.multi_limit_exceeded("inputBytes", a.inputBytes), "入力バイト数が上限268,435,456を超過しました")

    def test_small_wording_matches_the_approved_table(self):
        self.assertEqual(messages.spec_size_limit("333バイト"), "仕様文書のMarkdownが333バイト上限を超過しました")
        self.assertEqual(messages.frontmatter_size_limit("51バイト"), "フロントマターが51バイト上限を超過しました")
        self.assertEqual(messages.statement_count_limit(5), "1文書の規範文数が5上限を超過しました")
        self.assertEqual(messages.array_count_limit("tests[0].covers", 3), "1文書の関係・パスの配列の項目数が3上限を超過しました")
        self.assertEqual(messages.spec_file_count_limit(1), "仕様文書のファイルが1件上限を超過しました")
        self.assertEqual(messages.verify_argv_expanded_count_limit(2), "{tests}展開後のargvの要素数が上限2を超えます")
        self.assertEqual(messages.verify_argv_expanded_limit("47バイト"), "{tests}展開後のargvがバイト数上限47バイトを超えます")
        self.assertEqual(
            messages.verify_argv_expanded_element_limit("20バイト"), "{tests}展開後のargvの要素がバイト数上限20バイトを超えます"
        )
        self.assertEqual(messages.multi_config_exclude_count(1), "設定キーmultiWorkspace.excludeは1件以下で指定してください")
        self.assertEqual(messages.multi_limit_exceeded("inputBytes", 4096), "入力バイト数が上限4,096を超過しました")
        self.assertEqual(messages.MEMBER_LIMITS_DECLARED, "メンバーの設定は設定キーlimitsを指定できません")


class DocumentLimitTests(unittest.TestCase):
    """ファイル単位の上限（`specBytes`、`frontmatterBytes`、`documentStatementCount`、`documentArrayItemCount`）。"""

    def process(self, text: str, limits: limits_mod.Limits) -> doc_mod.DocEntry:
        return doc_mod._process_document_content(
            text.encode("utf-8"), ".spec/requirements/REQ-001.md", "REQ", "root", limits
        )

    def summaries(self, entry: doc_mod.DocEntry) -> list[str]:
        return [d.summary for d in entry.hard or []]

    def test_spec_bytes_boundary(self):
        text = _req("REQ-001")
        size = len(text.encode("utf-8"))
        self.assertIsNone(self.process(text, limits_mod.Limits(specBytes=size)).hard)
        entry = self.process(text, limits_mod.Limits(specBytes=size - 1))
        self.assertEqual(self.summaries(entry), [f"仕様文書のMarkdownが{size - 1:,}バイト上限を超過しました"])

    def test_frontmatter_bytes_counts_the_lines_between_the_delimiters(self):
        # `id: REQ-001\ntitle: REQ\nstatus: approved\n`は12+11+17=40バイト（区切りの行を除き、最後の行の改行を含める）。
        text = _req("REQ-001")
        self.assertIsNone(self.process(text, limits_mod.Limits(frontmatterBytes=40)).hard)
        entry = self.process(text, limits_mod.Limits(frontmatterBytes=39))
        self.assertEqual(self.summaries(entry), ["フロントマターが39バイト上限を超過しました"])

    def test_statement_count_boundary(self):
        text = _req("REQ-001", statements=3)
        self.assertEqual(self.process(text, limits_mod.Limits(documentStatementCount=3)).statement_count, 3)
        entry = self.process(text, limits_mod.Limits(documentStatementCount=2))
        self.assertEqual(self.summaries(entry), ["1文書の規範文数が2上限を超過しました"])

    def test_array_item_count_boundary(self):
        text = _req("REQ-001").replace(
            "status: approved\n", "status: approved\nimplements: [src/a.py, src/b.py]\n"
        )
        self.assertIsNone(self.process(text, limits_mod.Limits(documentArrayItemCount=2)).hard)
        entry = self.process(text, limits_mod.Limits(documentArrayItemCount=1))
        self.assertEqual(
            [(d.code, d.source.get("key"), d.summary) for d in entry.hard or []],
            [("SPEC-INPUT-LIMIT-001", "implements", "1文書の関係・パスの配列の項目数が1上限を超過しました")],
        )

    def test_absolute_limits_keep_the_existing_wording(self):
        big = _req("REQ-001") + "x" * (1_048_576 + 1)
        self.assertEqual(self.summaries(self.process(big, limits_mod.ABSOLUTE)), ["仕様文書のMarkdownが1 MiB上限を超過しました"])


class SingleWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def check(self, *argv: str, cwd: Path | None = None) -> tuple[dict, int]:
        parsed = parse_argv(["check", *argv, "--format", "json"])
        return check_mod.run(parsed, str(cwd or self.root), self.env)

    def test_spec_file_count_stops_check_with_only_that_diagnostic(self):
        # `INPUT-LIMIT-SPEC-COUNT`は`stop-operation`。基準版との比較（削除の検出など）へ進まない。
        _write(self.root, ".spec/bitz.yaml", CONFIG + "limits:\n  specFileCount: 1\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
        _commit(self.root)
        for argv in (("--full", "--base", "HEAD"), ()):
            with self.subTest(argv=argv):
                result, code = self.check(*argv)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(
                    result["diagnostics"],
                    [{
                        "code": "SPEC-INPUT-LIMIT-001", "severity": "error", "resultStatus": "failed",
                        "summary": "仕様文書のファイルが1件上限を超過しました",
                        "source": {"kind": "file", "workspaceId": "root", "path": ".spec"},
                    }],
                )

    def test_multi_workspace_dimensions_are_not_used(self):
        dims = "".join(f"  {k}: 1\n" for k in (
            "inputBytes", "statementCount", "relationEdgeCount", "traceEntryCount", "commandDefinitionCount",
            "verifyBindingCount", "excludeCount",
        ))
        _write(self.root, ".spec/bitz.yaml", CONFIG + "limits:\n" + dims)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", statements=3))
        _commit(self.root)
        result, code = self.check("--full", "--base", "HEAD")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual(result["checkedStatementCount"], 3)

    def test_base_documents_use_the_current_limits(self):
        # 基準版の文書は、現在版の設定から決めた上限で解析する（`check --base`。§4.1）。上限を超える基準版の文書は比較の対象から外れる。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", statements=2))
        _commit(self.root)
        size = len(_req("REQ-001", statements=2).encode("utf-8"))
        executable = gitutil.detect_git(str(self.root), self.env).executable
        for limit, expected in ((size, ["REQ-001"]), (size - 1, [])):
            with self.subTest(limit=limit):
                base = doc_mod.build_base_catalog(
                    executable, str(self.root), self.env, "HEAD", str(self.root), "root",
                    limits_mod.Limits(specBytes=limit),
                )
                self.assertEqual(list(base), expected)

    def test_context_digest_does_not_depend_on_limits(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _commit(self.root)
        parsed = parse_argv(["context", "REQ-001", "--format", "json"])
        before, _ = context_mod.run(parsed, str(self.root), self.env)
        _write(self.root, ".spec/bitz.yaml", CONFIG + "limits:\n  specBytes: 4096\n  expandedArgvCount: 1\n")
        _commit(self.root, "limits")
        after, _ = context_mod.run(parsed, str(self.root), self.env)
        self.assertEqual(before["status"], "passed", before["diagnostics"])
        self.assertEqual(before["contextDigest"], after["contextDigest"])


class DoctorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def doctor(self, *argv: str, cwd: Path | None = None) -> dict:
        result, _code = doctor_mod.run(parse_argv(["doctor", *argv, "--format", "json"]), str(cwd or self.root), self.env)
        return result

    def test_single_workspace(self):
        cases = {
            "": None,
            "limits: {}\n": ABSOLUTE_VALUES,
            "limits:\n  expandedArgvBytes: 4096\n  specFileCount: 5\n": dict(
                ABSOLUTE_VALUES, specFileCount=5, expandedArgvBytes=4096
            ),
            "limits:\n  specBytes: 0\n": None,
            "limits:\n": None,
        }
        for yaml, expected in cases.items():
            with self.subTest(yaml=yaml):
                _write(self.root, ".spec/bitz.yaml", CONFIG + yaml)
                result = self.doctor()
                if expected is None:
                    self.assertNotIn("limits", result)
                else:
                    self.assertEqual(result["limits"], expected)
                    self.assertEqual(list(result["limits"]), KEYS_IN_TABLE_ORDER)

    def test_multi_workspace_uses_the_root_config_and_top_level_only(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  inputBytes: 65536\n")
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _commit(self.root)
        expected = dict(ABSOLUTE_VALUES, inputBytes=65536)
        single = self.doctor(cwd=self.root / "apps" / "web")
        self.assertEqual(single["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual(single["limits"], expected)
        whole = self.doctor("--all-workspaces")
        self.assertEqual(whole["limits"], expected)
        self.assertTrue(whole["workspaces"])
        self.assertTrue(all("limits" not in w for w in whole["workspaces"]))

    def test_text_format_is_unchanged(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "limits:\n  specBytes: 2048\n")
        result = self.doctor()
        from bitz.textrender import render_doctor_text

        without = dict(result)
        without.pop("limits")
        self.assertEqual(render_doctor_text(result), render_doctor_text(without))


class MultiWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def check_all(self, base: str = "HEAD") -> tuple[dict, int]:
        parsed = parse_argv(["check", "--all-workspaces", "--base", base, "--format", "json"])
        return check_mod.run(parsed, str(self.root), self.env)

    def build(self, root_limits: str = "", web_extra: str = "", web_statements: int = 2) -> None:
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + root_limits)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML + web_extra)
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", web_statements))
        _commit(self.root)

    def test_member_limits_are_rejected_without_checking_the_value(self):
        for extra in ("limits:\n  specBytes: 2048\n", "limits: 1024\n", "limits:\n  specBytes: 0\n", "limits:\n"):
            with self.subTest(extra=extra):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                self.root = Path(tmp.name)
                self.build(web_extra=extra)
                result, code = self.check_all()
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(result["workspaces"], [])
                self.assertEqual(
                    [(d["code"], d["summary"], d["source"]) for d in result["diagnostics"]],
                    [(
                        "SPEC-MULTI-MEMBER-001", "メンバーの設定は設定キーlimitsを指定できません",
                        {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml",
                         "key": "multiWorkspace.members"},
                    )],
                )

    def test_root_file_limits_apply_to_member_documents(self):
        self.build(root_limits="limits:\n  documentStatementCount: 1\n", web_statements=2)
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("failed", 1))
        by_id = {w["id"]: w for w in result["workspaces"]}
        self.assertEqual(by_id["platform"]["status"], "passed")
        self.assertEqual(
            [(d["code"], d["summary"], d["source"]["path"]) for d in by_id["web"]["diagnostics"]],
            [("SPEC-INPUT-LIMIT-001", "1文書の規範文数が1上限を超過しました", ".spec/technical/TECH-001.md")],
        )

    def test_snapshot_dimension_uses_root_limits(self):
        self.build(root_limits="limits:\n  statementCount: 2\n", web_statements=2)
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(
            result["diagnostics"][0]["evidence"], {"dimension": "statementCount", "limit": 2, "observedAtLeast": 3}
        )
        self.assertEqual(result["diagnostics"][0]["summary"], "規範文数が上限2を超過しました")

    def test_base_snapshot_uses_current_limits(self):
        # 基準版は規範文4件。現在版は`statementCount: 3`を足し、メンバーの文書を1件に減らす（現在版は2件）。
        self.build(web_statements=3)
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  statementCount: 3\n")
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", 1))
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(
            result["diagnostics"][0]["evidence"], {"dimension": "statementCount", "limit": 3, "observedAtLeast": 4}
        )
        # 対照: 基準版の設定の`limits`は使わない。
        _commit(self.root, "limits")
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML)
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_base_snapshot_counts_deleted_files(self):
        # 作業ツリーで消したファイルは基準版にだけある。数え直しを省かずに基準版を数える。
        self.build(root_limits="limits:\n  specFileCount: 2\n")
        _write(self.root, "apps/web/.spec/technical/TECH-002.md", _tech("TECH-002"))
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  specFileCount: 3\n")
        _commit(self.root, "three files")
        (self.root / "apps/web/.spec/technical/TECH-002.md").unlink()
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  specFileCount: 2\n")
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(
            result["diagnostics"][0]["evidence"], {"dimension": "specFileCount", "limit": 2, "observedAtLeast": 3}
        )

    def test_unchanged_base_snapshot_is_not_recounted(self):
        # 基準版のファイルがすべて同じ内容で作業ツリーにあれば（追加だけなら）、基準版の数は現在版を超えないので数え直さない。
        self.build(root_limits="limits:\n  statementCount: 10\n")
        _write(self.root, "apps/web/.spec/technical/TECH-002.md", _tech("TECH-002"))
        with mock.patch.object(gitutil, "BlobReader", side_effect=AssertionError("数え直した")):
            result, code = self.check_all()
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_exclude_count_uses_the_limit(self):
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "  exclude: [tests/a, tests/b]\nlimits:\n  excludeCount: 1\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _commit(self.root)
        result, code = self.check_all()
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            [(d["code"], d["summary"], d["source"].get("key")) for d in result["diagnostics"]],
            [("SPEC-MULTI-CONFIG-001", "設定キーmultiWorkspace.excludeは1件以下で指定してください", "multiWorkspace.exclude")],
        )


class WalkOrderTests(unittest.TestCase):
    def test_base_order_matches_the_working_tree_walk(self):
        names = [
            "requirements/REQ-002.md", "requirements/a/REQ-010.md", "requirements/REQ-001.md",
            "requirements/a/b/REQ-020.md", "requirements/a/REQ-011.md", "requirements/Z/REQ-030.md",
            "technical/TECH-001.md", "decisions/ADR-001.md", "tasks/TASK-001.md", "technical/x/TECH-002.md",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for name in names:
                _write(Path(tmp), f".spec/{name}", "x\n")
            walked = [
                os.path.relpath(p, os.path.join(tmp, ".spec")).replace(os.sep, "/")
                for p in multiws._iter_spec_md_files(tmp)
            ]
        self.assertEqual(sorted(names, key=multiws._walk_order_key), walked)


class DeterminismTests(unittest.TestCase):
    SCRIPT = (
        "import json, os, sys\n"
        "from bitz import check, doctor\n"
        "from bitz.cliargs import parse_argv\n"
        "out = []\n"
        "for argv, op in ((['check', '--all-workspaces', '--base', 'HEAD'], check), (['doctor', '--all-workspaces'], doctor)):\n"
        "    result, code = op.run(parse_argv(argv + ['--format', 'json']), os.getcwd(), dict(os.environ))\n"
        "    result.pop('durationMs', None)\n"
        "    for w in result.get('workspaces', []):\n"
        "        w.pop('durationMs', None)\n"
        "    out.append([code, result])\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )

    def test_output_is_independent_of_hash_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  documentStatementCount: 1\n  futureLimit: 3\n")
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, "apps/web/.spec/bitz.yaml", WEB_YAML)
            _write(root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", 2))
            _commit(root)
            outputs = {}
            for seed in ("0", "1", "12345"):
                proc = subprocess.run(
                    [sys.executable, "-c", self.SCRIPT], cwd=root,
                    env={**os.environ, **_GIT_ENV, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
                    capture_output=True, text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                outputs[seed] = proc.stdout
        self.assertEqual(len(set(outputs.values())), 1, outputs)
        decoded = json.loads(outputs["0"])
        self.assertEqual(decoded[0][1]["status"], "failed")
        self.assertIn("limits", decoded[1][1])


if __name__ == "__main__":
    unittest.main()
