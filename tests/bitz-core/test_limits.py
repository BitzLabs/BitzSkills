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
4. ファイル単位の上限の適用（フロントマターの大きさの数え方を含む）と、仕様文書のファイル数の超過で`check`、`context`、`verify`を止めること
5. 複合ワークスペースの適用範囲（ルートの設定をメンバーの文書へ、メンバーの設定の`limits`、単一ワークスペースは複合の次元を使わない、
   基準版のスナップショット、除外の件数）
6. 基準版のスナップショットを作業ツリーとインデックスによらず基準版のコミットの内容で数えること、基準版を読めなければ`SPEC-MULTI-GIT-001`にすること、
   基準版の除外の件数を絶対上限で検査すること
7. フロントマターの大きさの数え方（間に行がなければ0バイト、改行の正規化）
8. `limits`がコンテキストのハッシュ値を変えないこと、出力が`PYTHONHASHSEED`に依存しないこと
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
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
from bitz import verify as verify_mod
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
    "historyCommitCount",
]
ABSOLUTE_VALUES = {
    "specBytes": 1_048_576, "frontmatterBytes": 32_768, "specFileCount": 10_000, "documentStatementCount": 1_000,
    "documentArrayItemCount": 1_000, "inputBytes": 268_435_456, "statementCount": 100_000,
    "relationEdgeCount": 1_000_000, "traceEntryCount": 1_000_000, "commandDefinitionCount": 10_000,
    "verifyBindingCount": 10_000, "excludeCount": 100, "expandedArgvCount": 10_000,
    "expandedArgvElementBytes": 32_768, "expandedArgvBytes": 1_048_576, "historyCommitCount": 10_000,
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
            "historyCommitCount: 10001": ("limits.historyCommitCount", 10_000),
            "historyCommitCount: 0": ("limits.historyCommitCount", 10_000),
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

    SPEC_COUNT_DIAG = {
        "code": "SPEC-INPUT-LIMIT-001", "severity": "error", "resultStatus": "failed",
        "summary": "仕様文書のファイルが1件上限を超過しました",
        "source": {"kind": "file", "workspaceId": "root", "path": ".spec"},
    }

    def build_over_count(self, extra: str = "") -> None:
        # `verify`のコマンドは起動すると`ran.marker`を作る。停止したらコマンドを1件も起動しないことを実ファイルで確かめる。
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "verify:\n  commands:\n    default:\n"
            '      argv: ["/bin/sh", "-c", "touch ran.marker", "{tests}"]\n      cwd: .\n'
            "limits:\n  specFileCount: 1\n" + extra,
        )
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
        _commit(self.root)

    def test_spec_file_count_stops_context_with_only_that_diagnostic(self):
        # `context`も起点の解決へ進まず（`CTX-ROOT-MISSING-001`を返さず）、同一性を構成した後の停止の形で返す。
        self.build_over_count()
        revision = {"commit": _git(self.root, "rev-parse", "HEAD"), "dirty": False}
        for roots in (["REQ-001"], ["REQ-002", "REQ-001"], ["REQ-999"]):
            with self.subTest(roots=roots):
                parsed = parse_argv(["context", *roots, "--format", "json"])
                result, code = context_mod.run(parsed, str(self.root), self.env)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(result["diagnostics"], [self.SPEC_COUNT_DIAG])
                self.assertEqual(result["workspace"], {"id": "root", "path": "."})
                self.assertEqual(result["roots"], sorted(roots))
                self.assertIsNone(result["contextDigest"])
                self.assertEqual(result["revision"], revision)
                self.assertEqual(
                    result["resolution"], {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0}
                )
                self.assertEqual((result["documents"], result["constraintLedger"]), ([], {"statements": []}))

    def test_spec_file_count_stops_verify_without_running_commands(self):
        self.build_over_count()
        revision = {"commit": _git(self.root, "rev-parse", "HEAD"), "dirty": False}
        for argv, scope in ((["REQ-001"], "selected"), (["REQ-999"], "selected"), ([], "all")):
            with self.subTest(argv=argv):
                parsed = parse_argv(["verify", *argv, "--format", "json"])
                result, code = verify_mod.run(parsed, str(self.root), self.env)
                self.assertEqual((result["status"], code), ("failed", 1))
                result.pop("durationMs")
                self.assertEqual(
                    result,
                    {
                        "schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": scope,
                        "workspace": {"id": "root", "path": "."}, "targetResults": [], "revision": revision,
                        "commands": [], "diagnostics": [self.SPEC_COUNT_DIAG],
                    },
                )
                self.assertFalse((self.root / "ran.marker").exists())

    def test_spec_file_count_stop_keeps_config_warnings(self):
        # 設定の警告（`continue`）は、停止した結果にも最上位の診断として残す（設定の停止の経路と同じ）。
        self.build_over_count(extra="  futureLimit: 3\n")
        warning = {
            "code": "SPEC-CONFIG-UNKNOWN-001", "severity": "warning", "resultStatus": "passed_with_warnings",
            "summary": "未知の設定キーです",
            "source": {"kind": "file", "workspaceId": "root", "path": ".spec/bitz.yaml", "key": "limits.futureLimit"},
        }
        for op, mod in (("context", context_mod), ("verify", verify_mod), ("check", check_mod)):
            with self.subTest(op=op):
                argv = [op, "--format", "json"] if op == "check" else [op, "REQ-001", "--format", "json"]
                result, code = mod.run(parse_argv(argv), str(self.root), self.env)
                self.assertEqual((result["status"], code), ("failed", 1))
                self.assertEqual(sorted(json.dumps(d, sort_keys=True) for d in result["diagnostics"]),
                                 sorted(json.dumps(d, sort_keys=True) for d in (self.SPEC_COUNT_DIAG, warning)))

    def test_spec_file_count_boundary_does_not_stop_context_and_verify(self):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
            "limits:\n  specFileCount: 2\n",
        )
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
        _commit(self.root)
        result, code = context_mod.run(parse_argv(["context", "REQ-001", "--format", "json"]), str(self.root), self.env)
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertIsNotNone(result["contextDigest"])
        result, _code = verify_mod.run(parse_argv(["verify", "REQ-001", "--format", "json"]), str(self.root), self.env)
        self.assertNotIn("SPEC-INPUT-LIMIT-001", [d["code"] for d in result["diagnostics"]])
        self.assertEqual([t["target"] for t in result["targetResults"]], ["REQ-001"])

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

    def test_unchanged_base_snapshot_within_the_limit_passes(self):
        # 対照: 基準版も現在版も上限以内なら通る（基準版は常に数える。作業ツリーで足しただけのファイルは基準版に現れない）。
        self.build(root_limits="limits:\n  statementCount: 10\n")
        _write(self.root, "apps/web/.spec/technical/TECH-002.md", _tech("TECH-002"))
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


_GIT_001 = {
    "code": "SPEC-MULTI-GIT-001", "severity": "error", "resultStatus": "blocked",
    "summary": "Gitのリポジトリの境界を確定できません", "source": {"kind": "environment", "component": "git"},
}


class BaseSnapshotTests(unittest.TestCase):
    """`check --base`の基準版のスナップショットの上限（複合ワークスペース仕様 §10、安全な入出力・互換性 §4.1）。

    基準版のスナップショットは、作業ツリーとインデックスではなく、基準版のコミットの内容で数える。基準版を読めなければ
    `SPEC-MULTI-GIT-001`（`blocked`）とし、数えずに通さない。
    """

    #: ルートのREQ-001と、メンバー`web`のTECH-001〜003の4件。現在版で1件消すと3件になる。
    TECH_003 = "apps/web/.spec/technical/TECH-003.md"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def run_check(self, *argv: str, cwd: Path | None = None) -> tuple[dict, int]:
        parsed = parse_argv(["check", *argv, "--format", "json"])
        return check_mod.run(parsed, str(cwd or self.root), self.env)

    def build_four_files(self, root_yaml: str = ROOT_YAML, limits: str = "limits:\n  specFileCount: 3\n") -> None:
        _write(self.root, ".spec/bitz.yaml", root_yaml + limits)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        for n in (1, 2, 3):
            _write(self.root, f"apps/web/.spec/technical/TECH-00{n}.md", _tech(f"TECH-00{n}"))
        _commit(self.root)

    def remove(self, rel: str, mode: str) -> None:
        if mode == "index":
            _git(self.root, "rm", "-q", rel)
            return
        if mode == "skip-worktree":
            _git(self.root, "update-index", "--skip-worktree", rel)
        elif mode == "assume-unchanged":
            _git(self.root, "update-index", "--assume-unchanged", rel)
        (self.root / rel).unlink()

    def assert_limit(self, result: dict, code: int, dimension: str, limit: int, observed: int) -> None:
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(
            [(d["code"], d.get("evidence")) for d in result["diagnostics"]],
            [("SPEC-MULTI-LIMIT-001", {"dimension": dimension, "limit": limit, "observedAtLeast": observed})],
        )

    def test_exceeding_base_is_blocked_whatever_the_worktree_and_index_say(self):
        # `git diff <rev>`はskip-worktreeとassume-unchangedのファイルを作業ツリーから消しても削除と報告しない。
        # 差分から基準版の数を推し量らず、基準版のコミットの内容を数える。
        for mode in ("worktree", "index", "skip-worktree", "assume-unchanged"):
            with self.subTest(mode=mode):
                self.setUp()
                self.build_four_files()
                self.remove(self.TECH_003, mode)
                result, code = self.run_check("--all-workspaces", "--base", "HEAD")
                self.assert_limit(result, code, "specFileCount", 3, 4)

    def test_modified_file_hidden_from_git_is_counted_in_the_base(self):
        # 基準版のTECH-001は規範文3件（ルートと合わせて4件）。作業ツリーで1件に減らし、skip-worktreeでGitから隠す。
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  statementCount: 3\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", 3))
        _commit(self.root)
        for flag in ("--skip-worktree", "--assume-unchanged"):
            with self.subTest(flag=flag):
                _git(self.root, "update-index", "--no-skip-worktree", "--no-assume-unchanged",
                     "apps/web/.spec/technical/TECH-001.md")
                _git(self.root, "update-index", flag, "apps/web/.spec/technical/TECH-001.md")
                _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", 1))
                result, code = self.run_check("--all-workspaces", "--base", "HEAD")
                self.assert_limit(result, code, "statementCount", 3, 4)

    def test_single_operations_check_the_base(self):
        # 単独の`check`（メンバーの中から、`--workspace`、修飾IDの対象、ルートの全体検査）も基準版を数える。
        cases = [
            ("apps/web", ()),
            ("apps/web", ("--base", "HEAD")),
            (".", ("--workspace", "web")),
            (".", ("web::TECH-001",)),
            (".", ("--full", "--base", "HEAD")),
        ]
        for mode in ("worktree", "skip-worktree"):
            for cwd, argv in cases:
                with self.subTest(mode=mode, cwd=cwd, argv=argv):
                    self.setUp()
                    self.build_four_files()
                    self.remove(self.TECH_003, mode)
                    result, code = self.run_check(*argv, cwd=self.root / cwd)
                    self.assert_limit(result, code, "specFileCount", 3, 4)

    def test_member_path_change_counts_the_base_catalog(self):
        # 基準版のカタログは`web`を`apps/web`に置く。現在版は`apps/www`へ移し、1件消す（現在版は3件、基準版は4件）。
        self.build_four_files()
        _git(self.root, "mv", "apps/web", "apps/www")
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML.replace("apps/web", "apps/www") + "limits:\n  specFileCount: 3\n")
        (self.root / "apps/www/.spec/technical/TECH-003.md").unlink()
        for argv, cwd in ((("--all-workspaces", "--base", "HEAD"), "."), ((), "apps/www")):
            with self.subTest(argv=argv):
                result, code = self.run_check(*argv, cwd=self.root / cwd)
                self.assert_limit(result, code, "specFileCount", 3, 4)

    def test_member_only_in_the_base_is_counted(self):
        # 基準版のカタログだけにあるメンバー`api`の文書も基準版のスナップショットに含める。
        root_yaml = ROOT_YAML + "    - id: api\n      path: services/api\n"
        _write(self.root, ".spec/bitz.yaml", root_yaml + "limits:\n  specFileCount: 2\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001"))
        _write(self.root, "services/api/.spec/bitz.yaml", CONFIG + "workspace:\n  id: api\n")
        _write(self.root, "services/api/.spec/technical/TECH-101.md", _tech("TECH-101"))
        _commit(self.root)
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "limits:\n  specFileCount: 2\n")
        _git(self.root, "rm", "-q", "-r", "services/api")
        for argv, cwd in ((("--all-workspaces", "--base", "HEAD"), "."), ((), "apps/web"), (("--full",), ".")):
            with self.subTest(argv=argv, cwd=cwd):
                result, code = self.run_check(*argv, cwd=self.root / cwd)
                self.assert_limit(result, code, "specFileCount", 2, 3)

    def test_base_within_the_limit_passes_whatever_the_worktree_says(self):
        # 対照: 基準版が上限以内なら、skip-worktreeで隠した変更があっても上限の診断を返さない。
        self.build_four_files(limits="limits:\n  specFileCount: 4\n")
        self.remove(self.TECH_003, "skip-worktree")
        result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assertNotIn("SPEC-MULTI-LIMIT-001", [d["code"] for d in result["diagnostics"]], result["diagnostics"])
        self.assertNotIn("SPEC-MULTI-GIT-001", [d["code"] for d in result["diagnostics"]], result["diagnostics"])

    # --- 基準版を読めないとき（I-3） ---------------------------------------------------------------

    def assert_git_blocked(self, result: dict, code: int) -> None:
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual([d for d in result["diagnostics"] if d["code"] != "SPEC-MULTI-LIMIT-001"], [_GIT_001])
        self.assertNotIn("SPEC-MULTI-LIMIT-001", [d["code"] for d in result["diagnostics"]])

    def test_unreadable_tree_is_git_001(self):
        self.build_four_files(limits="")
        for argv, cwd in ((("--all-workspaces", "--base", "HEAD"), "."), ((), "apps/web")):
            with self.subTest(argv=argv, cwd=cwd):
                with mock.patch.object(gitutil, "list_tree_blobs", return_value=None):
                    result, code = self.run_check(*argv, cwd=self.root / cwd)
                self.assert_git_blocked(result, code)

    def test_unreadable_member_tree_is_git_001(self):
        # ルートの`.spec`は読めて、メンバーの`.spec`だけ読めない場合も、そのメンバーを数えずに通さない。
        self.build_four_files(limits="")
        real = gitutil.list_tree_blobs

        def fake(executable, toplevel, env, rev, prefix):
            return None if prefix.startswith("apps/web") else real(executable, toplevel, env, rev, prefix)

        with mock.patch.object(gitutil, "list_tree_blobs", side_effect=fake):
            result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assert_git_blocked(result, code)

    def test_unreadable_blob_is_git_001(self):
        self.build_four_files(limits="")
        for failing in ("config", "spec"):
            with self.subTest(failing=failing):
                real_read = gitutil.BlobReader.read
                calls = {"n": 0}

                def fake_read(reader, oid, _failing=failing):
                    calls["n"] += 1
                    # 最初の読取りはルートの設定。`spec`の場合は2件目以降（仕様文書）で失敗させる。
                    if _failing == "config" or calls["n"] > 1:
                        raise gitutil.GitReadError("cat-file")
                    return real_read(reader, oid)

                with mock.patch.object(gitutil.BlobReader, "read", fake_read):
                    result, code = self.run_check("--all-workspaces", "--base", "HEAD")
                self.assert_git_blocked(result, code)

    def test_blob_reader_failure_to_start_is_git_001(self):
        self.build_four_files(limits="")
        real_popen = subprocess.Popen

        def fake_popen(argv, *args, **kwargs):
            if "cat-file" in argv:
                raise OSError("spawn")
            return real_popen(argv, *args, **kwargs)

        with mock.patch.object(gitutil.subprocess, "Popen", side_effect=fake_popen):
            result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assert_git_blocked(result, code)

    def test_missing_object_in_the_repository_is_git_001(self):
        # 実際のGitで、基準版のblobのオブジェクトを消す（partial cloneで取得できない場合に相当）。
        self.build_four_files(limits="")
        oid = _git(self.root, "rev-parse", f"HEAD:{self.TECH_003}")
        (self.root / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
        result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assert_git_blocked(result, code)

    def test_blob_reader_times_out(self):
        # `git cat-file --batch`が応答しない（partial cloneの遅延取得が止まった場合など）ときも、無期限に待たない。
        with tempfile.TemporaryDirectory() as tmp:
            fake_git = Path(tmp) / "git"
            fake_git.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
            fake_git.chmod(0o755)
            started = time.monotonic()
            with gitutil.BlobReader(str(fake_git), tmp, dict(os.environ), timeout=0.5) as reader:
                with self.assertRaises(gitutil.GitReadError):
                    reader.read("0" * 40)
            self.assertLess(time.monotonic() - started, 10)

    def test_blob_reader_reads_contents_and_reports_missing_objects(self):
        self.build_four_files(limits="")
        executable = gitutil.detect_git(str(self.root), self.env).executable
        oid = _git(self.root, "rev-parse", "HEAD:.spec/requirements/REQ-001.md")
        with gitutil.BlobReader(executable, str(self.root), self.env) as reader:
            self.assertEqual(reader.read(oid), _req("REQ-001").encode("utf-8"))
            with self.assertRaises(gitutil.GitReadError):
                reader.read("0" * 40)

    # --- 除外の件数（S-2） ------------------------------------------------------------------------

    def build_exclude(self, base_exclude: list[str], base_limits: str = "") -> None:
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + f"  exclude: [{', '.join(base_exclude)}]\n" + base_limits)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, "vendor/a/.spec/bitz.yaml", CONFIG + "workspace:\n  id: vendored\n")
        _commit(self.root)

    def test_exclude_count_applies_only_to_the_current_root_config(self):
        # 基準版の除外は2件、現在版は1件で`excludeCount: 1`。基準版の除外は絶対上限（100件）で検査するので、
        # 基準版の`vendor/a`の設定も除外の中にあり、未登録の設定にならない。
        self.build_exclude(["vendor/a", "vendor/b"])
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "  exclude: [vendor/a]\nlimits:\n  excludeCount: 1\n")
        for argv in (("--all-workspaces", "--base", "HEAD"), ("--full", "--base", "HEAD"), ()):
            with self.subTest(argv=argv):
                result, code = self.run_check(*argv)
                self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_base_exclude_count_ignores_the_base_limits(self):
        # 基準版の設定自身の`limits.excludeCount`も使わない（絶対上限で検査する）。
        self.build_exclude(["vendor/a", "vendor/b"], base_limits="limits:\n  excludeCount: 1\n")
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "  exclude: [vendor/a]\n")
        result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        git = gitutil.detect_git(str(self.root), self.env)
        self.assertEqual(
            multiws.base_exclude_parts(git, str(self.root), self.env, "HEAD", str(self.root)), [("vendor", "a"), ("vendor", "b")]
        )

    def test_base_exclude_over_the_absolute_limit_is_not_trusted(self):
        # 基準版の除外が101件なら、絶対上限を超えるので信用せず、基準版の`vendor/a`の設定は未登録になる。
        self.build_exclude(["vendor/a"] + [f"other/x{i:03d}" for i in range(100)])
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + "  exclude: [vendor/a]\n")
        result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(
            [(d["code"], d["source"].get("path")) for d in result["diagnostics"]],
            [("SPEC-MULTI-UNREGISTERED-001", "vendor/a/.spec/bitz.yaml")],
        )


class FrontmatterSizeTests(unittest.TestCase):
    """フロントマターの大きさ（文書・フロントマター・状態仕様 §11）。区切りの行の間の各行を改行（正規化後1バイト）を含めて数え、
    区切りの行は含めない。間に行がなければ0バイト。"""

    def size(self, text: str) -> int:
        fm_raw, _body, closing = doc_mod._extract_frontmatter(text)
        self.assertIsNotNone(fm_raw)
        return doc_mod._frontmatter_bytes(fm_raw, closing)

    def test_counting_rule(self):
        self.assertEqual(self.size("---\n---"), 0)
        self.assertEqual(self.size("---\n\n---\n"), 1)
        self.assertEqual(self.size("---\nid: A\n---\n"), 6)
        self.assertEqual(self.size("---\nid: A\nx: y\n---\nbody\n"), 11)
        self.assertEqual(self.size("---\nid: A\n---"), 6)
        self.assertEqual(self.size("---\nあ: い\n---\n"), 9)

    def process(self, raw: bytes, limit: int) -> list[str]:
        entry = doc_mod._process_document_content(
            raw, ".spec/requirements/REQ-001.md", "REQ", "root", limits_mod.Limits(frontmatterBytes=limit)
        )
        return [d.summary for d in entry.hard or [] if d.code == "SPEC-INPUT-LIMIT-001"]

    def test_no_lines_between_the_delimiters_is_zero_bytes(self):
        # 間に行がなければ0バイトなので、最小の上限1でも超過しない（区切りの行と、終わりの区切りの後の改行を数えない）。
        for raw in (b"---\n---", b"---\r\n---"):
            with self.subTest(raw=raw):
                self.assertEqual(self.process(raw, 1), [])

    def test_crlf_is_counted_after_normalization(self):
        # CRLFはLFへ正規化した後に数える。`id: REQ-001\ntitle: REQ\nstatus: approved\n`は40バイト（CRLFのままなら43バイト）。
        raw = _req("REQ-001").replace("\n", "\r\n").encode("utf-8")
        self.assertEqual(self.process(raw, 40), [])
        self.assertEqual(self.process(raw, 39), ["フロントマターが39バイト上限を超過しました"])
        cr = _req("REQ-001").replace("\n", "\r").encode("utf-8")
        self.assertEqual(self.process(cr, 40), [])
        self.assertEqual(self.process(cr, 39), ["フロントマターが39バイト上限を超過しました"])


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
