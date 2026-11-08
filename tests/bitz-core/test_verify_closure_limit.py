"""`verify`が完全な閉包の上限（`CTX-LIMIT-001`）を判定する単体試験（確認事項C95、`bitz verify`仕様 §4の1.・§9）。

規範（`verify` §4の1.）: 検証対象ごとに、`context` §8と同じ規則で完全な閉包の上限を判定する。使う値は起点を所有するワークスペースの
`context.maxDocuments`と`context.maxBytes`、バイト数は詳細度`standard`の提示で測る。上限を超えた検証対象は診断`CTX-LIMIT-001`（`blocked`）、
`contextDigest: null`、`bindingRefs: []`、`statements: []`とし、テストを起動しない。独立した検証対象は続ける。
§9: 上限で止まる結果には、`related`の参照切れの警告（`SPEC-RELATION-ADVISORY-MISSING-001`）を加えない（`context` §10と同じ）。
文言は`context`の既存の文言（文書数は`コンテキストの完全な閉包が文書数上限を超過しました`、バイト数は`...バイト数上限を超過しました`）を使う。

修正前のCoreは、`verify`が上限を判定せず、上限を超えた閉包を`passed`にしてテストを起動した。
各試験の期待値は規範と承認済みの文言のリテラルで、Coreの定数や`context`の出力からは導かない（ただし`context`との一致は別の試験で確かめる）。
対照の試験（`ControlTests`）は、修正前のCoreも通る。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
LIMIT = "CTX-LIMIT-001"
ADVISORY = "SPEC-RELATION-ADVISORY-MISSING-001"
SUMMARY_DOCUMENTS = "コンテキストの完全な閉包が文書数上限を超過しました"
SUMMARY_BYTES = "コンテキストの完全な閉包がバイト数上限を超過しました"
HEAD = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
# `touch ran.marker`は、コマンドを起動したかを実ファイルで確かめるためのもの。
COMMAND = 'verify:\n  commands:\n    default:\n      argv: ["/bin/sh", "-c", "touch ran.marker", "{tests}"]\n      cwd: .\n'
# 4 KiBは設定できる`context.maxBytes`の最小値。詰め物は、標準の提示がこれを超えるだけの量にする。
PADDING = "この段落は標準提示のバイト数を上限検査のために増やす固定文である。\n" * 40


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, *, test_path: str = "tests/t.py", padding: str = "") -> str:
    """規範文AC-01を1件持ち、自身の`tests`でそれを`covers`するREQ。"""

    return (
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: approved\n"
        f"tests:\n  - path: {test_path}\n    covers: [{doc_id}:AC-01]\n    command: default\n---\n\n"
        f"# {doc_id} REQ\n\n## Intent\n\n意図。\n\n{padding}"
        "## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str, *, related: str | None = None) -> str:
    """`refines`で起点へ到達する、規範文のないTECH（閉包を1文書増やす）。"""

    relations = f"relations:\n  refines: [{refines}]\n" + (f"  related: [{related}]\n" if related else "")
    return f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n{relations}---\n\n# {doc_id} TECH\n\n## Context\n\n本文。\n"


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def commit(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")

    def verify(self, *argv: str, cwd: Path | None = None):
        return verify_mod.run(parse_argv(["verify", *argv, "--format", "json"]), str(cwd or self.root), self.env)

    def context(self, *argv: str, cwd: Path | None = None):
        return context_mod.run(parse_argv(["context", *argv, "--format", "json"]), str(cwd or self.root), self.env)

    def target(self, result: dict, name: str) -> dict:
        found = [t for t in result["targetResults"] if t["target"] == name]
        self.assertEqual(len(found), 1, result)
        return found[0]

    def assert_limit_target(self, entry: dict, summary: str, workspace_id: str, path: str) -> None:
        """上限で止まった検証対象の形: `blocked`、`contextDigest: null`、`statements`と`bindingRefs`は空、診断は`CTX-LIMIT-001`の1件だけ。"""

        self.assertEqual(entry["status"], "blocked")
        self.assertIsNone(entry["contextDigest"])
        self.assertEqual(entry["statements"], [])
        self.assertEqual(entry["bindingRefs"], [])
        self.assertEqual(
            entry["diagnostics"],
            [{"code": LIMIT, "severity": "error", "resultStatus": "blocked", "summary": summary,
              "source": {"kind": "file", "workspaceId": workspace_id, "path": path}}],
        )


class SingleWorkspaceTests(_Base):
    """単一ワークスペース。閉包は、`REQ-001`と、それを`refines`する`TECH-001`の2文書（`REQ-002`は独立）。"""

    def build(self, context_block: str, *, req_padding: str = "", tech_related: str | None = None, with_tech2: bool = False,
              with_req2: bool = False) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", HEAD + context_block + COMMAND)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", padding=req_padding))
        _write(r, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001", related=tech_related))
        if with_tech2:
            _write(r, ".spec/technical/TECH-002.md", _tech("TECH-002", "TECH-001"))
        if with_req2:
            _write(r, ".spec/requirements/REQ-002.md", _req("REQ-002", test_path="tests/u.py"))
            _write(r, "tests/u.py", "x\n")
        _write(r, "tests/t.py", "x\n")
        self.commit()

    @property
    def marker(self) -> Path:
        return self.root / "ran.marker"

    def test_documents_limit_blocks_target(self):
        self.build("context:\n  maxDocuments: 1\n")
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assert_limit_target(self.target(result, "REQ-001"), SUMMARY_DOCUMENTS, "root", ".spec/requirements/REQ-001.md")
        self.assertEqual((result["commands"], result["diagnostics"]), ([], []))
        self.assertFalse(self.marker.exists(), "上限で止まる検証対象のテストは起動しない")

    def test_bytes_limit_blocks_target(self):
        self.build("context:\n  maxBytes: 4096\n", req_padding=PADDING)
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assert_limit_target(self.target(result, "REQ-001"), SUMMARY_BYTES, "root", ".spec/requirements/REQ-001.md")
        self.assertEqual((result["commands"], result["diagnostics"]), ([], []))
        self.assertFalse(self.marker.exists())

    def test_related_warning_is_not_added_to_limit_result(self):
        """警告が出るはずの`related`の参照切れ（`TECH-001`が存在しない`ADR-099`を`related`する）を、上限を超える閉包に置く。"""

        self.build("context:\n  maxDocuments: 1\n", tech_related="ADR-099")
        result, _code = self.verify("REQ-001")
        entry = self.target(result, "REQ-001")
        self.assert_limit_target(entry, SUMMARY_DOCUMENTS, "root", ".spec/requirements/REQ-001.md")
        self.assertNotIn(ADVISORY, [d["code"] for d in entry["diagnostics"]])
        self.assertEqual(result["diagnostics"], [])

    def test_related_warning_precondition_is_returned_within_limit(self):
        """前提の確認: 同じ入力で上限を超えなければ警告が出る（上の試験が警告の不在を恒真で確かめていない）。"""

        self.build("context:\n  maxDocuments: 2\n", tech_related="ADR-099")
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0))
        self.assertEqual([d["code"] for d in self.target(result, "REQ-001")["diagnostics"]], [ADVISORY])

    def test_independent_target_continues(self):
        """`REQ-001`の閉包は3文書（`TECH-002`が`TECH-001`を`refines`する）、`REQ-002`は`REQ-002`だけの1文書。上限は2文書。"""

        self.build("context:\n  maxDocuments: 2\n", with_tech2=True, with_req2=True)
        result, code = self.verify("REQ-001", "REQ-002")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assert_limit_target(self.target(result, "REQ-001"), SUMMARY_DOCUMENTS, "root", ".spec/requirements/REQ-001.md")
        other = self.target(result, "REQ-002")
        self.assertEqual(other["status"], "passed")
        self.assertIsNotNone(other["contextDigest"])
        self.assertEqual(other["bindingRefs"], ["root::default"])
        # 独立した検証対象のテストだけが起動する（`REQ-001`のテストは含まない）。
        self.assertEqual([(c["bindingId"], c["tests"]) for c in result["commands"]], [("root::default", ["tests/u.py"])])
        self.assertTrue(self.marker.exists())

    def test_limit_stops_before_coverage(self):
        """検査の順は、関係の診断、上限、カバレッジ。未テストの`MUST`があっても、上限を超えれば`CTX-LIMIT-001`だけを返す。"""

        self.build("context:\n  maxDocuments: 1\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001").replace(
            "tests:\n  - path: tests/t.py\n    covers: [REQ-001:AC-01]\n    command: default\n", ""))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "no tests")
        result, _code = self.verify("REQ-001")
        self.assertEqual([d["code"] for d in self.target(result, "REQ-001")["diagnostics"]], [LIMIT])

    def assert_same_as_context(self) -> None:
        verified, _ = self.verify("REQ-001")
        contextual, _ = self.context("REQ-001", "--purpose", "verify")
        self.assertEqual(contextual["status"], "blocked")
        self.assertEqual(len(contextual["diagnostics"]), 1)
        self.assertEqual(self.target(verified, "REQ-001")["diagnostics"], contextual["diagnostics"])

    def test_documents_limit_matches_context_with_purpose_verify(self):
        """`verify`の診断は、同じ入力の`context --purpose verify`の診断と、文言・発生元まで一致する（同じ規則）。"""

        self.build("context:\n  maxDocuments: 1\n")
        self.assert_same_as_context()

    def test_bytes_limit_matches_context_with_purpose_verify(self):
        self.build("context:\n  maxBytes: 4096\n", req_padding=PADDING)
        self.assert_same_as_context()


def _normalized_size(text: str) -> int:
    """ファイル全体のテキストから、フロントマターの終端より後の本文を取り、`bodyText`の正規化（§3.1.2。CRLFとCRをLFへ、行末の空白を除く、先頭と末尾の空行を除く、末尾にLFを付ける）
    を適用したUTF-8のバイト数を返す。Coreの`digest.normalize_body_text`とは別に書いた参照計算。"""

    body = text.split("\n---\n", 1)[1]
    lines = [line.rstrip(" \t") for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return len(("\n".join(lines) + "\n").encode("utf-8")) if lines else 0


# 全角文字、行末の空白とタブ、CRLFを含む詰め物。正規化の前後でバイト数が変わる（CRLFのCRと行末の空白を除く）。
NORMALIZED_PADDING = "全角　の本文です。 \t\r\n" * 150


class ByteBoundaryTests(_Base):
    """バイト数の上限の境界（確認事項C95）。標準の提示のバイト数は、正規化した本文のUTF-8の長さの和（起点とそれを直接具体化する文書。ともに提示形式`full`）。

    境界Tは、`context REQ-001 --purpose verify`の判定から求め（Tで通り、T-1で止まる最小の`maxBytes`）、入力から別に導く値と一致することも確かめる。
    本文は全角文字と行末の空白とCRLFを含み、正規化を外した（本文の元の長さで測る）実装は、境界の近くでcontextと判定が分かれる。
    """

    def build(self, max_bytes: int) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", HEAD + f"context:\n  maxBytes: {max_bytes}\n" + COMMAND)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", padding=NORMALIZED_PADDING))
        _write(r, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001"))
        _write(r, "tests/t.py", "x\n")
        if not (r / ".git").exists():
            self.commit()
        else:
            _git(r, "add", "-A")

    def stopped_by_context(self, max_bytes: int) -> bool:
        self.build(max_bytes)
        result, _code = self.context("REQ-001", "--purpose", "verify")
        return LIMIT in [d["code"] for d in result["diagnostics"]]

    def boundary(self) -> int:
        """contextの判定で、止まらない最小の`maxBytes`（設定できる最小値4096以上）。"""

        low, high = 4096, 200000
        self.assertTrue(self.stopped_by_context(low), "詰め物は、最小の上限を超える大きさにする")
        self.assertFalse(self.stopped_by_context(high))
        while low + 1 < high:
            mid = (low + high) // 2
            if self.stopped_by_context(mid):
                low = mid
            else:
                high = mid
        return high

    def test_boundary_is_derived_from_normalized_bodies(self):
        """Tは、入力から導くバイト数（正規化した本文の長さの和）と一致する。Tで通り（`>`であって`>=`ではない）、T-1で止まる。"""

        threshold = self.boundary()
        expected = sum(_normalized_size((self.root / path).read_text(encoding="utf-8"))
                       for path in (".spec/requirements/REQ-001.md", ".spec/technical/TECH-001.md"))
        self.assertEqual(threshold, expected)
        raw = sum(len((self.root / path).read_bytes()) for path in (".spec/requirements/REQ-001.md", ".spec/technical/TECH-001.md"))
        self.assertGreater(raw, threshold, "正規化の前後でバイト数が変わる入力にする")

    def test_verify_boundary_at_T_minus_1_T_and_T_plus_1(self):
        threshold = self.boundary()
        for max_bytes, stopped in ((threshold - 1, True), (threshold, False), (threshold + 1, False)):
            with self.subTest(maxBytes=max_bytes):
                self.build(max_bytes)
                (self.root / "ran.marker").unlink(missing_ok=True)
                verified, code = self.verify("REQ-001")
                entry = self.target(verified, "REQ-001")
                if stopped:
                    self.assertEqual((verified["status"], code), ("blocked", 2))
                    self.assert_limit_target(entry, SUMMARY_BYTES, "root", ".spec/requirements/REQ-001.md")
                    self.assertFalse((self.root / "ran.marker").exists())
                else:
                    self.assertEqual((verified["status"], code), ("passed", 0), verified)
                    self.assertEqual(entry["bindingRefs"], ["root::default"])
                    self.assertTrue((self.root / "ran.marker").exists())

    def test_verify_matches_context_at_boundary(self):
        """T-1・T・T+1で、verifyの判定（止まるか、診断の文言と発生元）がcontextと一致する。"""

        threshold = self.boundary()
        for max_bytes in (threshold - 1, threshold, threshold + 1):
            with self.subTest(maxBytes=max_bytes):
                self.build(max_bytes)
                contextual, _ = self.context("REQ-001", "--purpose", "verify")
                verified, _ = self.verify("REQ-001")
                context_limit = [d for d in contextual["diagnostics"] if d["code"] == LIMIT]
                verify_limit = [d for d in self.target(verified, "REQ-001")["diagnostics"] if d["code"] == LIMIT]
                self.assertEqual(verify_limit, context_limit)
                self.assertEqual(bool(context_limit), max_bytes < threshold)


class CheckOrderTests(_Base):
    """検査の順は、関係の診断（と状態の診断）、上限、カバレッジ。これらが上限の超過と同時に起きるとき、verifyはcontextと同じ診断だけを返し、`CTX-LIMIT-001`を返さない。"""

    def codes(self, result: dict) -> list[str]:
        return [d["code"] for d in result["diagnostics"]]

    def assert_same_as_context(self, expected_code: str) -> None:
        contextual, _ = self.context("REQ-001", "--purpose", "verify")
        verified, code = self.verify("REQ-001")
        entry = self.target(verified, "REQ-001")
        self.assertEqual(self.codes(contextual), [expected_code])
        self.assertEqual([d["code"] for d in entry["diagnostics"]], [expected_code])
        self.assertNotIn(LIMIT, [d["code"] for d in entry["diagnostics"]])
        self.assertEqual(entry["diagnostics"], contextual["diagnostics"])
        self.assertIsNone(entry["contextDigest"])
        self.assertEqual((entry["bindingRefs"], verified["commands"]), ([], []))
        self.assertFalse((self.root / "ran.marker").exists())

    def build(self, *, tech_requires: str | None = None) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", HEAD + "context:\n  maxDocuments: 1\n" + COMMAND)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        tech = _tech("TECH-001", "REQ-001")
        if tech_requires:
            tech = tech.replace("  refines: [REQ-001]\n", f"  refines: [REQ-001]\n  requires: [{tech_requires}]\n", 1)
        _write(r, ".spec/technical/TECH-001.md", tech)
        _write(r, "tests/t.py", "x\n")
        self.commit()

    def test_missing_strong_relation_wins_over_limit(self):
        """閉包は2文書で上限（1文書）を超えるが、強い関係の参照切れ（`SPEC-RELATION-MISSING-001`）があれば、それだけを返して`failed`にする。"""

        self.build(tech_requires="REQ-099")
        self.assert_same_as_context("SPEC-RELATION-MISSING-001")
        verified, code = self.verify("REQ-001")
        self.assertEqual((verified["status"], code), ("failed", 1))

    def test_state_error_wins_over_limit(self):
        """`requires`で到達する文書が`draft`（適用できない状態）なら、状態の診断を返し、上限は判定しない。閉包は3文書で上限（1文書）を超える。"""

        self.build(tech_requires="REQ-002")
        _write(self.root, ".spec/requirements/REQ-002.md", _req("REQ-002", test_path="tests/u.py").replace("status: approved", "status: draft", 1))
        _write(self.root, "tests/u.py", "x\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "draft requires")
        contextual, _ = self.context("REQ-001", "--purpose", "verify")
        verified, _code = self.verify("REQ-001")
        entry = self.target(verified, "REQ-001")
        self.assertNotIn(LIMIT, self.codes(contextual))
        self.assertTrue(contextual["diagnostics"], "前提: contextは状態の診断を返す")
        self.assertEqual(entry["diagnostics"], contextual["diagnostics"])
        self.assertNotEqual(verified["status"], "passed")


class ControlTests(_Base):
    """対照: 上限の内側なら今までどおり通る（修正前のCoreも通る）。"""

    def build(self, context_block: str, *, req_padding: str = "", tech_related: str | None = None) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", HEAD + context_block + COMMAND)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", padding=req_padding))
        _write(r, ".spec/technical/TECH-001.md", _tech("TECH-001", "REQ-001", related=tech_related))
        _write(r, "tests/t.py", "x\n")
        self.commit()

    def assert_passes(self, result: dict, code: int) -> None:
        self.assertEqual((result["status"], code), ("passed", 0), result)
        entry = self.target(result, "REQ-001")
        self.assertEqual(entry["status"], "passed")
        self.assertRegex(entry["contextDigest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(entry["bindingRefs"], ["root::default"])
        self.assertEqual(entry["diagnostics"], [])
        self.assertTrue((self.root / "ran.marker").exists(), "上限の内側ならテストを起動する")

    def test_documents_exactly_at_limit_passes(self):
        """閉包は2文書。上限が2文書ちょうどなら超えない。"""

        self.build("context:\n  maxDocuments: 2\n")
        self.assert_passes(*self.verify("REQ-001"))

    def test_bytes_within_limit_passes(self):
        self.build("context:\n  maxBytes: 4096\n")
        self.assert_passes(*self.verify("REQ-001"))

    def test_default_limits_pass(self):
        self.build("")
        self.assert_passes(*self.verify("REQ-001"))


class MultiWorkspaceTests(_Base):
    """複合ワークスペース（ルート`platform`、メンバー`web`・`api`）。上限は起点を所有するワークスペースの設定を使う。"""

    ROOT = HEAD + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"

    def build(self, *, root_context: str = "", web_context: str = "", api_context: str = "", web_related: str | None = None,
              cross: bool = False) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", self.ROOT + root_context + COMMAND)
        _write(r, "apps/web/.spec/bitz.yaml", HEAD + "workspace:\n  id: web\n" + web_context + COMMAND)
        _write(r, "services/api/.spec/bitz.yaml", HEAD + "workspace:\n  id: api\n" + api_context + COMMAND)
        _write(r, "apps/web/.spec/requirements/REQ-101.md", _req("REQ-101"))
        _write(r, "apps/web/.spec/technical/TECH-101.md", _tech("TECH-101", "REQ-101", related=web_related))
        _write(r, "apps/web/tests/t.py", "x\n")
        _write(r, "services/api/.spec/requirements/REQ-201.md", _req("REQ-201"))
        _write(r, "services/api/tests/t.py", "x\n")
        if cross:
            # ルートのREQ-001を、メンバー`web`のTECH-102が直接`refines`する。閉包はルートの1文書と`web`の1文書。
            _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", test_path="tests/t.py"))
            _write(r, "tests/t.py", "x\n")
            _write(r, "apps/web/.spec/technical/TECH-102.md", _tech("TECH-102", "platform::REQ-001"))
        self.commit()

    def marker(self, member: str) -> Path:
        return self.root / member / "ran.marker"

    def test_single_operation_uses_owner_workspace_limit(self):
        """`verify web::REQ-101`は、起点を所有する`web`の上限（1文書）を使う。ルートの上限は既定の20文書。"""

        self.build(web_context="context:\n  maxDocuments: 1\n")
        result, code = self.verify("web::REQ-101")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["workspace"]["id"], "web")
        self.assert_limit_target(self.target(result, "web::REQ-101"), SUMMARY_DOCUMENTS, "web", ".spec/requirements/REQ-101.md")
        self.assertEqual((result["commands"], result["diagnostics"]), ([], []))
        self.assertFalse(self.marker("apps/web").exists())

    def test_single_operation_bytes_limit(self):
        self.build(web_context="context:\n  maxBytes: 4096\n")
        _write(self.root, "apps/web/.spec/requirements/REQ-101.md", _req("REQ-101", padding=PADDING))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "padding")
        result, _code = self.verify("web::REQ-101")
        self.assert_limit_target(self.target(result, "web::REQ-101"), SUMMARY_BYTES, "web", ".spec/requirements/REQ-101.md")

    def test_single_operation_ignores_root_limit_for_member_target(self):
        """対照: ルートの上限が1文書でも、起点を所有する`web`の上限（既定）で判定するので、`verify web::REQ-101`は通る。"""

        self.build(root_context="context:\n  maxDocuments: 1\n")
        result, code = self.verify("web::REQ-101")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        entry = self.target(result, "web::REQ-101")
        self.assertIsNotNone(entry["contextDigest"])
        self.assertEqual(entry["bindingRefs"], ["web::default"])
        self.assertTrue(self.marker("apps/web").exists())

    def test_cross_workspace_closure_counts_other_workspace_documents(self):
        """ルートのREQ-001の閉包は、ルートの1文書と、直接`refines`する`web`の`TECH-102`の2文書。ルートの上限1文書で止まる。"""

        self.build(root_context="context:\n  maxDocuments: 1\n", cross=True)
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assert_limit_target(self.target(result, "platform::REQ-001"), SUMMARY_DOCUMENTS, "platform", ".spec/requirements/REQ-001.md")
        self.assertFalse((self.root / "ran.marker").exists())
        self.assertFalse(self.marker("apps/web").exists())

    def test_cross_workspace_closure_within_limit_passes(self):
        """対照: 同じ入力で、ルートの上限が2文書なら通る（`web`の上限は関係しない）。"""

        self.build(root_context="context:\n  maxDocuments: 2\n", web_context="context:\n  maxDocuments: 1\n", cross=True)
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertIsNotNone(self.target(result, "platform::REQ-001")["contextDigest"])

    def test_related_warning_is_not_added_to_limit_result(self):
        self.build(web_context="context:\n  maxDocuments: 1\n", web_related="ADR-099")
        result, _code = self.verify("web::REQ-101")
        entry = self.target(result, "web::REQ-101")
        self.assert_limit_target(entry, SUMMARY_DOCUMENTS, "web", ".spec/requirements/REQ-101.md")

    def test_related_warning_precondition_is_returned_within_limit(self):
        self.build(web_related="ADR-099")
        result, code = self.verify("web::REQ-101")
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0))
        self.assertEqual([d["code"] for d in self.target(result, "web::REQ-101")["diagnostics"]], [ADVISORY])

    def test_all_workspaces_uses_each_member_limit_and_continues(self):
        """`web`の上限は1文書（閉包は2文書で超える）、`api`は既定（閉包は1文書）。`api`のテストは起動し、`web`のテストは起動しない。"""

        self.build(web_context="context:\n  maxDocuments: 1\n")
        result, code = self.verify("--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["diagnostics"], [])
        by_id = {w["id"]: w for w in result["workspaces"]}
        web_entry = [t for t in by_id["web"]["targetResults"] if t["target"] == "web::REQ-101"][0]
        self.assert_limit_target(web_entry, SUMMARY_DOCUMENTS, "web", ".spec/requirements/REQ-101.md")
        self.assertEqual(by_id["web"]["status"], "blocked")
        self.assertEqual(by_id["web"]["commands"], [])
        api_entry = [t for t in by_id["api"]["targetResults"] if t["target"] == "api::REQ-201"][0]
        self.assertEqual((api_entry["status"], api_entry["bindingRefs"]), ("passed", ["api::default"]))
        self.assertIsNotNone(api_entry["contextDigest"])
        self.assertEqual([c["bindingId"] for c in by_id["api"]["commands"]], ["api::default"])
        self.assertFalse(self.marker("apps/web").exists())
        self.assertTrue(self.marker("services/api").exists())

    def test_all_workspaces_ignores_other_member_limit(self):
        """対照: `api`の上限が1文書でも、`web`の判定には使わない。`web`の閉包は2文書で、`web`の上限（既定）の内側なので通る。"""

        self.build(api_context="context:\n  maxDocuments: 1\n")
        result, code = self.verify("--all-workspaces")
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0), result["diagnostics"])
        by_id = {w["id"]: w for w in result["workspaces"]}
        statuses = {t["target"]: t["status"] for w in result["workspaces"] for t in w["targetResults"]}
        self.assertEqual(statuses, {"web::REQ-101": "passed", "api::REQ-201": "passed"})
        self.assertEqual(sorted(w for w in by_id), ["api", "platform", "web"])


if __name__ == "__main__":
    unittest.main()
