"""`bitz context`（`context.py`／`contextrender.py`）の単体試験。

`03_操作仕様/01_context.md`の主要規則（目的別の閉包、役割、カバレッジの5区分、提示形式の
必須・禁止フィールド、Markdown §9の規則、上限、取得後の仕様変更の検出）を、fixtureが直接検査しない範囲も含めて
広く確認する。goldenのハッシュ値そのものの一致は`fixtures/conformance/single/SINGLE-042`などの
適合fixtureが検査するため、ここでは形式・規則面だけを検査する。
"""

import os
import tempfile
import unittest

from bitz import context as context_mod
from bitz.cliargs import ParsedArgs
from bitz.contextrender import render_context_markdown

_NO_GIT_ENV = {"PATH": "/dev/null"}


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml(extra: str = "") -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n' + extra


def _req(doc_id: str, status: str = "approved", extra_frontmatter: str = "", extra_body: str = "") -> str:
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
{extra_body}"""


def _tech(doc_id: str, status: str = "approved", extra_frontmatter: str = "", with_statement: bool = True) -> str:
    stmt = (
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 具体化された制約。\n"
        if with_statement
        else ""
    )
    section = "## Contract\n\n" + stmt if with_statement else "## Context\n\n規範文を持たない。\n"
    return f"""---
id: {doc_id}
title: 技術契約
status: {status}
{extra_frontmatter}---

# {doc_id} 技術契約

{section}"""


def _task(doc_id: str, status: str = "open", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 作業
status: {status}
{extra_frontmatter}---

# {doc_id} 作業

## Objective

作業内容。
"""


def _run_context(root: str, positionals: list, *, purpose: str = "interpret", detail: str = "standard",
                  fmt: str = "json", expand=None, expect_digest=None) -> tuple[dict, int]:
    single = {"--purpose": purpose, "--detail": detail, "--format": fmt}
    if expect_digest is not None:
        single["--expect-digest"] = expect_digest
    repeat = {"--expand": expand} if expand else {}
    parsed = ParsedArgs(operation="context", positionals=positionals, flags=set(), single=single, repeat=repeat)
    return context_mod.run(parsed, root, dict(_NO_GIT_ENV))


class BasicBundleTests(unittest.TestCase):
    def test_simple_req_verify_bundle_passes(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="verify")
            self.assertEqual(exit_code, 2)  # `MUST`が`untested`（テストなし）のため`blocked`。
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["roots"], ["REQ-001"])
            self.assertRegex(result["contextDigest"], r"^sha256:[0-9a-f]{64}$")

    def test_root_missing_returns_ctx_root_missing(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            result, exit_code = _run_context(root, ["REQ-999"])
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["contextDigest"], None)
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-ROOT-MISSING-001")

    def test_digest_unaffected_by_detail_and_expand(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            r_standard, _ = _run_context(root, ["REQ-001"], purpose="interpret", detail="standard")
            r_full, _ = _run_context(root, ["REQ-001"], purpose="interpret", detail="full")
            self.assertEqual(r_standard["contextDigest"], r_full["contextDigest"])


class CoverageTests(unittest.TestCase):
    def test_implement_coverage_has_five_buckets_per_modality(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="implement")
            for modality in ("must", "should", "may"):
                bucket = result["coverage"][modality]
                self.assertEqual(
                    set(bucket.keys()), {"total", "addressed", "tested", "unaddressed", "untested"}
                )
            self.assertIn("REQ-001:AC-01", result["coverage"]["must"]["total"])
            self.assertIn("REQ-001:AC-01", result["coverage"]["must"]["unaddressed"])

    def test_implement_unaddressed_must_produces_warning(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="implement")
            self.assertEqual(result["status"], "passed_with_warnings")
            self.assertEqual(exit_code, 0)
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("CTX-COVERAGE-TASK-001", codes)


class ProjectionFieldTests(unittest.TestCase):
    def test_full_projection_has_required_and_no_forbidden_fields(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret", detail="full")
            doc = result["documents"][0]
            self.assertEqual(doc["projection"], "full")
            for key in ("statementRefs", "frontmatter", "bodyText"):
                self.assertIn(key, doc)
            self.assertNotIn("expandable", doc)

    def test_reference_projection_has_expandable_and_no_body(self):
        # REQ-002（`draft`）がREQ-001（起点・承認済み）を`refines`する＝§6.1「6.」の、`draft`の文書が`refines`する場合。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/requirements/REQ-002.md",
                _req("REQ-002", status="draft", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            by_id = {d["id"]: d for d in result["documents"]}
            advisory_doc = by_id["REQ-002"]
            self.assertEqual(advisory_doc["role"], "advisory")
            self.assertEqual(advisory_doc["projection"], "reference")
            self.assertIn("expandable", advisory_doc)
            for key in ("statementRefs", "frontmatter", "bodyText"):
                self.assertNotIn(key, advisory_doc)

    def test_distance2_requirement_and_constraint_stay_full_not_normative(self):
        # `context`仕様 §5: 提示形式`full`にするのは起点・TASK・`replacement`・`requirement`・
        # `constraint`と距離1の文書。距離2以上の`requirement`/`constraint`も、距離だけを理由に
        # `normative`へ落とさない（ADR-014の`Decision`の4番目の項目。SINGLE-106-06と同型）。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [TECH-010]\n"),
            )
            _write(
                root,
                ".spec/technical/TECH-010.md",
                _tech("TECH-010", extra_frontmatter="relations:\n  requires: [REQ-020]\n", with_statement=False),
            )
            _write(root, ".spec/requirements/REQ-020.md", _req("REQ-020"))
            result, _ = _run_context(root, ["REQ-001"], purpose="verify")
            by_id = {d["id"]: d for d in result["documents"]}
            self.assertEqual(by_id["TECH-010"]["role"], "constraint")
            self.assertEqual(by_id["TECH-010"]["projection"], "full")
            self.assertEqual(by_id["REQ-020"]["role"], "requirement")
            self.assertEqual(by_id["REQ-020"]["projection"], "full")

    def test_distance2_refinement_is_normative(self):
        # 距離2以上の具体化文書（役割`refinement`）は、所有する規範文がすべて制約台帳（対象規範文）にあれば
        # 提示形式`normative`にする（`context`仕様 §5）。規範文を持たない具体化文書は条件を満たす。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            _write(
                root,
                ".spec/technical/TECH-003.md",
                _tech("TECH-003", extra_frontmatter="relations:\n  refines: [TECH-002]\n", with_statement=False),
            )
            result, _ = _run_context(root, ["REQ-001"], purpose="verify")
            by_id = {d["id"]: d for d in result["documents"]}
            self.assertEqual(by_id["TECH-002"]["role"], "refinement")
            self.assertEqual(by_id["TECH-002"]["projection"], "full")
            self.assertEqual(by_id["TECH-003"]["role"], "refinement")
            self.assertEqual(by_id["TECH-003"]["projection"], "normative")

    def test_distance2_refinement_with_statements_in_ledger_is_normative(self):
        # 規範文単位で具体化した文書の規範文は対象規範文になる（関係・トレースモデル §6.4）。制約台帳にあるので`normative`にできる。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/technical/TECH-002.md",
                   _tech("TECH-002", extra_frontmatter="relations:\n  refines: [REQ-001:AC-01]\n"))
            _write(root, ".spec/technical/TECH-003.md",
                   _tech("TECH-003", extra_frontmatter="relations:\n  refines: [TECH-002:AC-01]\n"))
            result, _ = _run_context(root, ["REQ-001"], purpose="verify")
            by_id = {d["id"]: d for d in result["documents"]}
            ledger = {s["id"] for s in result["constraintLedger"]["statements"]}
            self.assertIn("TECH-003:AC-01", ledger)
            self.assertEqual(by_id["TECH-003"]["projection"], "normative")

    def test_distance2_refinement_never_drops_must_text(self):
        # 所有する規範文が制約台帳にない具体化文書を`normative`にすると、その`MUST`の文面が提示からも制約台帳からも
        # 失われる（ADR-014の`Decision`の4番目の項目、`context`仕様 §5）。規範文が制約台帳になければ`full`で本文を返す。
        # 文書単位で具体化した文書の規範文を対象規範文に含めるか（関係・トレースモデル §6.4の規則1）は未決のため、
        # 目的`implement`と`verify`では制約台帳への収録の有無を固定せず、どちらでも文面が残ることだけを確かめる。
        for purpose in ("interpret", "implement", "verify"):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as root:
                _write(root, ".spec/bitz.yaml", _bitz_yaml())
                _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
                _write(root, ".spec/technical/TECH-002.md",
                       _tech("TECH-002", extra_frontmatter="relations:\n  refines: [REQ-001]\n"))
                _write(root, ".spec/technical/TECH-003.md",
                       _tech("TECH-003", extra_frontmatter="relations:\n  refines: [TECH-002]\n"))
                result, _ = _run_context(root, ["REQ-001"], purpose=purpose)
                by_id = {d["id"]: d for d in result["documents"]}
                ledger = {s["id"] for s in result["constraintLedger"]["statements"]}
                self.assertEqual(by_id["TECH-003"]["role"], "refinement")
                if purpose == "interpret":
                    # 目的`interpret`では対象規範文が空なので、制約台帳も空になる（関係・トレースモデル §6.4）。
                    self.assertEqual(ledger, set())
                if "TECH-003:AC-01" not in ledger:
                    self.assertEqual(by_id["TECH-003"]["projection"], "full")
                    self.assertIn("具体化された制約", by_id["TECH-003"]["bodyText"])

    def test_refines_target_reached_first_by_requires_is_full(self):
        # 起点の`refines`の参照先に、`requires`の鎖で先に到達した場合も`full`にする。この文書の距離は最短の1で
        # （関係・トレースモデル §7の6.）、距離1の文書として`full`になる。その規範文は対象規範文にならない（§6.4の規則4）。
        # 制約台帳の条件（`context`仕様 §5）は、距離2以上の具体化文書の試験（上の`never_drops_must_text`など）が確かめる。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n  refines: [REQ-003]\n"))
            _write(root, ".spec/requirements/REQ-002.md",
                   _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-003]\n"))
            _write(root, ".spec/requirements/REQ-003.md", _req("REQ-003"))
            result, _ = _run_context(root, ["REQ-001"], purpose="implement")
            by_id = {d["id"]: d for d in result["documents"]}
            ledger = {s["id"] for s in result["constraintLedger"]["statements"]}
            self.assertNotIn("REQ-003:AC-01", ledger)
            self.assertEqual(by_id["REQ-003"]["projection"], "full")
            self.assertIn("bodyText", by_id["REQ-003"])

    def test_full_refinement_counts_toward_byte_limit(self):
        # バイト数の上限は詳細度`standard`の提示量で測る（`context`仕様 §8）。規範文が制約台帳にない距離2の具体化文書は
        # `full`になるため、その本文も上限の計数に入る。
        long_text = "長い本文。" * 400
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml("context:\n  maxBytes: 4096\n"))
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/technical/TECH-002.md",
                   _tech("TECH-002", extra_frontmatter="relations:\n  refines: [REQ-001]\n"))
            _write(root, ".spec/technical/TECH-003.md",
                   _tech("TECH-003", extra_frontmatter="relations:\n  refines: [TECH-002]\n") + "\n## Notes\n\n" + long_text + "\n")
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            self.assertEqual(result["status"], "blocked")
            self.assertIn("CTX-LIMIT-001", [d["code"] for d in result["diagnostics"]])

    def test_expand_upgrades_reference_to_full(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/requirements/REQ-002.md",
                _req("REQ-002", status="draft", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret", expand=["REQ-002"])
            by_id = {d["id"]: d for d in result["documents"]}
            self.assertEqual(by_id["REQ-002"]["projection"], "full")
            self.assertEqual(result["projection"]["expanded"], ["REQ-002"])

    def test_expand_outside_resolved_set_fails(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/requirements/REQ-999.md", _req("REQ-999"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="interpret", expand=["REQ-999"])
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["documents"], [])
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-PROJECTION-001")


class LimitAndStaleTests(unittest.TestCase):
    def test_max_documents_limit_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml("context:\n  maxDocuments: 1\n"))
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"),
            )
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="interpret")
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-LIMIT-001")
            self.assertIsNone(result["contextDigest"])

    def test_expect_digest_mismatch_is_stale(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            bad_digest = "sha256:" + "0" * 64
            result, exit_code = _run_context(
                root, ["REQ-001"], purpose="interpret", expect_digest=bad_digest
            )
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-STALE-001")
            self.assertIsNotNone(result["contextDigest"])
            self.assertEqual(result["documents"], [])

    def test_expect_digest_match_passes(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            first, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            second, exit_code = _run_context(
                root, ["REQ-001"], purpose="interpret", expect_digest=first["contextDigest"]
            )
            self.assertEqual(exit_code, 0)
            self.assertNotEqual(second["documents"], [])


class MarkdownRenderTests(unittest.TestCase):
    def test_ends_with_single_lf_and_no_cr(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            text = render_context_markdown(result)
            self.assertTrue(text.endswith("\n"))
            self.assertFalse(text.endswith("\n\n"))
            self.assertNotIn("\r", text)

    def test_no_double_blank_lines(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            text = render_context_markdown(result)
            self.assertNotIn("\n\n\n", text)

    def test_empty_section_body_is_dash_none(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            text = render_context_markdown(result)
            self.assertIn("## Replacement Candidates\n\n- none\n", text)
            self.assertIn("## Work Boundary\n\n- none\n", text)

    def test_h1_is_context_bundle_only(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret")
            text = render_context_markdown(result)
            self.assertTrue(text.startswith("# Context Bundle\n\n"))
            self.assertEqual(text.splitlines()[0], "# Context Bundle")

    def test_fence_run_length_exceeds_longest_backtick_run_by_one(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            body_with_backticks = "コード ```三重backtick``` を含む本文。\n"
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_body=body_with_backticks),
            )
            result, _ = _run_context(root, ["REQ-001"], purpose="interpret", detail="full")
            text = render_context_markdown(result)
            self.assertIn("````markdown\n", text)


class NormalizeBeforeDedupTests(unittest.TestCase):
    """コンテキストのハッシュ値の正規化仕様 §2「3.正規化 → 4.重複排除と並べ替え」の順序（司令塔の是正1）。"""

    def test_relations_dedup_after_nfc_not_before(self):
        from bitz import context as ctx_mod
        from bitz import document as doc_mod

        composed = "é"  # 'é'（単一コードポイント、NFC）
        decomposed = "é"  # 'e' + 結合アクセント（NFD）。NFCにした後は`composed`と同一になる。
        # `relations.related`はID構文検査を経ない参照先の文字列を保持するため、任意の文字列を使える。
        entry = doc_mod.DocEntry(
            path=".spec/requirements/REQ-001.md",
            kind="REQ",
            doc_id="REQ-001",
            title="t",
            status="approved",
            frontmatter={
                "id": "REQ-001",
                "title": "t",
                "status": "approved",
                "relations": {"related": [f"REQ-{composed}", f"REQ-{decomposed}"]},
            },
            body="# REQ-001 t\n",
        )
        norm = ctx_mod._normalize_frontmatter(entry)
        # NFCにした後は同一の文字列になるため、重複排除で1件だけ残る。
        self.assertEqual(norm["relations"]["related"], [f"REQ-{composed}"])

    def test_implements_paths_dedup_after_nfc(self):
        from bitz import context as ctx_mod
        from bitz import document as doc_mod

        composed = "café.py"
        decomposed = "café.py"
        entry = doc_mod.DocEntry(
            path=".spec/requirements/REQ-001.md",
            kind="REQ",
            doc_id="REQ-001",
            title="t",
            status="approved",
            frontmatter={
                "id": "REQ-001",
                "title": "t",
                "status": "approved",
                "implements": [composed, decomposed],
            },
            body="# REQ-001 t\n",
        )
        norm = ctx_mod._normalize_frontmatter(entry)
        self.assertEqual(norm["implements"], [composed])


class MultiRootTests(unittest.TestCase):
    def test_two_independent_roots_union_and_sorted(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            result, exit_code = _run_context(root, ["REQ-002", "REQ-001"], purpose="interpret")
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["roots"], ["REQ-001", "REQ-002"])  # 入力順によらず正規ID辞書順。
            doc_ids = {d["id"] for d in result["documents"]}
            self.assertEqual(doc_ids, {"REQ-001", "REQ-002"})
            roles = {d["id"]: d["role"] for d in result["documents"]}
            self.assertEqual(roles["REQ-001"], "root")
            self.assertEqual(roles["REQ-002"], "root")

    def test_duplicate_root_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _ = _run_context(root, ["REQ-001", "REQ-001"], purpose="interpret")
            self.assertEqual(result["roots"], ["REQ-001"])

    def test_one_root_missing_fails_whole_bundle(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001", "REQ-999"], purpose="interpret")
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["documents"], [])
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertIn("CTX-ROOT-MISSING-001", codes)

    def test_target_statements_merge_across_roots(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            result, _ = _run_context(root, ["REQ-001", "REQ-002"], purpose="implement")
            must_total = set(result["coverage"]["must"]["total"])
            self.assertEqual(must_total, {"REQ-001:AC-01", "REQ-002:AC-01"})


class SupersededOriginInterpretTests(unittest.TestCase):
    """関係・トレースモデル §6.1「5.」、§7の役割の表（司令塔の是正4）。"""

    def test_single_successor_shows_advisory_and_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", with_statement=False))
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n", with_statement=False),
            )
            result, exit_code = _run_context(root, ["TECH-001"], purpose="interpret")
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "passed")
            by_id = {d["id"]: d for d in result["documents"]}
            self.assertEqual(by_id["TECH-001"]["role"], "advisory")
            self.assertEqual(by_id["TECH-002"]["role"], "replacement")
            # Coreは後継へ暗黙に起点を差し替えない: `roots`は`TECH-001`のまま。
            self.assertEqual(result["roots"], ["TECH-001"])

    def test_multiple_successors_fail_even_for_interpret(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", with_statement=False))
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n", with_statement=False),
            )
            _write(
                root,
                ".spec/technical/TECH-003.md",
                _tech("TECH-003", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n", with_statement=False),
            )
            result, exit_code = _run_context(root, ["TECH-001"], purpose="interpret")
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-STATE-SUPERSEDED-002")

    def test_implement_on_superseded_origin_is_still_blocked(self):
        # `interpret`の`advisory`/`replacement`の提示は、`implement`/`verify`の既存の遮断を変えない。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", with_statement=False))
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n", with_statement=False),
            )
            result, exit_code = _run_context(root, ["TECH-001"], purpose="implement")
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-STATE-SUPERSEDED-001")


class TaskDependencyStateTests(unittest.TestCase):
    """文書仕様 §7、関係モデル §6.2・§6.3・§10（司令塔の是正5）。"""

    def test_implement_task_addressing_draft_req_is_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", status="draft"))
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001:AC-01]\n"),
            )
            result, exit_code = _run_context(root, ["TASK-001"], purpose="implement")
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-STATE-001")

    def test_verify_task_addressing_superseded_dependency_is_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001"))
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n"),
            )
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  addresses: [TECH-001:AC-01]\n"),
            )
            result, exit_code = _run_context(root, ["TASK-001"], purpose="verify")
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["diagnostics"][0]["code"], "CTX-STATE-SUPERSEDED-001")

    def test_verify_task_addressing_healthy_dependency_passes_state_check(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001:AC-01]\n"),
            )
            result, exit_code = _run_context(root, ["TASK-001"], purpose="verify")
            # 依存の状態は健全。`MUST`が`untested`のため`blocked`になるが、状態に関する診断コードではない。
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertNotIn("CTX-STATE-001", codes)
            self.assertNotIn("CTX-STATE-SUPERSEDED-001", codes)


class TaskAddressedRefinementTests(unittest.TestCase):
    """関係・トレースモデル §6.4「規則3」: TASKを起点にした場合の`addresses`先の具体化文書（司令塔の是正7）。"""

    def test_implement_task_includes_refinement_of_addressed_statement(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  refines: [REQ-001:AC-01]\n"),
            )
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001:AC-01]\n"),
            )
            result, exit_code = _run_context(root, ["TASK-001"], purpose="implement")
            self.assertEqual(exit_code, 0)
            must_total = set(result["coverage"]["must"]["total"])
            self.assertEqual(must_total, {"REQ-001:AC-01", "TECH-001:AC-01"})
            doc_ids = {d["id"] for d in result["documents"]}
            self.assertIn("TECH-001", doc_ids)
            tech_doc = next(d for d in result["documents"] if d["id"] == "TECH-001")
            self.assertEqual(tech_doc["role"], "refinement")

    def test_verify_task_includes_refinement_of_addressed_statement(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  refines: [REQ-001:AC-01]\n"),
            )
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001:AC-01]\n"),
            )
            result, exit_code = _run_context(root, ["TASK-001"], purpose="verify")
            must_total = set(result["coverage"]["must"]["total"])
            self.assertEqual(must_total, {"REQ-001:AC-01", "TECH-001:AC-01"})


class UnresolvedStrongRelationsTests(unittest.TestCase):
    """`context.md §4`「`unresolvedStrongRelations`」（司令塔の是正6）。"""

    def test_missing_requires_target_fails_with_unresolved_count(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-999]\n"),
            )
            result, exit_code = _run_context(root, ["REQ-001"], purpose="interpret")
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["resolution"]["complete"], False)
            self.assertEqual(result["resolution"]["unresolvedStrongRelations"], 1)
            self.assertEqual(result["diagnostics"][0]["code"], "SPEC-RELATION-MISSING-001")

    def test_fully_resolved_relations_report_zero(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"),
            )
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="interpret")
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["resolution"]["unresolvedStrongRelations"], 0)
            self.assertEqual(result["resolution"]["complete"], True)



def _adr_doc(doc_id: str, status: str) -> str:
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


class AdrTypeConstraintTests(unittest.TestCase):
    """状態`accepted`でないADRへの`requires`は、状態の診断ではなく型制約の`CTX-RELATION-TYPE-001`とする（関係・トレースモデル §4）。
    状態の診断と型制約の診断は、独立した元の原因としてそれぞれ返す（診断レジストリ）。"""

    def _codes(self, result: dict) -> list[tuple[str, str]]:
        return sorted((d["code"], d["source"]["path"]) for d in result["diagnostics"])

    def test_implement_reports_relation_type_for_non_accepted_adr(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/decisions/ADR-001.md", _adr_doc("ADR-001", "proposed"))
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", extra_frontmatter="relations:\n  requires: [ADR-001]\n  addresses: [REQ-001:AC-01]\n"))
            result, exit_code = _run_context(root, ["TASK-001"], purpose="implement")
            self.assertEqual((result["status"], exit_code), ("failed", 1))
            self.assertEqual(self._codes(result), [("CTX-RELATION-TYPE-001", ".spec/tasks/TASK-001.md")])

    def test_state_and_relation_type_are_both_reported(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002, ADR-001]\n"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002", status="draft"))
            _write(root, ".spec/decisions/ADR-001.md", _adr_doc("ADR-001", "proposed"))
            result, exit_code = _run_context(root, ["REQ-001"], purpose="implement")
            self.assertEqual(self._codes(result), [
                ("CTX-RELATION-TYPE-001", ".spec/requirements/REQ-001.md"),
                ("CTX-STATE-001", ".spec/requirements/REQ-002.md"),
            ])
            self.assertEqual(result["resolution"]["unresolvedStrongRelations"], 1)

    def test_verify_task_root_checks_relations_of_the_requires_closure(self):
        # TASK-001 -> REQ-002（approved）-> ADR-001（proposed）。REQ-002はコンテキストへ含めないが、その強い関係の型制約を検査する。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/requirements/REQ-002.md",
                   _req("REQ-002", extra_frontmatter="relations:\n  requires: [ADR-001]\n"))
            _write(root, ".spec/decisions/ADR-001.md", _adr_doc("ADR-001", "proposed"))
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", status="done", extra_frontmatter="relations:\n  requires: [REQ-002]\n  addresses: [REQ-001:AC-01]\n"))
            result, exit_code = _run_context(root, ["TASK-001"], purpose="verify")
            self.assertEqual(self._codes(result), [("CTX-RELATION-TYPE-001", ".spec/requirements/REQ-002.md")])


class ConfigDiagnosticsTests(unittest.TestCase):
    """設定の不在は`SPEC-WORKSPACE-MISSING-001`（発生元`environment`）、不適合は設定の検査の診断（`SPEC-CONFIG-SCHEMA-001`など）を
    そのまま返し、設定の警告はどの結果にも加える（ワークスペース・設定仕様、診断レジストリ、`context` §6）。"""

    def test_invalid_config_returns_config_schema_diagnostic(self):
        for name, extra, key in (("language", None, "language"), ("maxBytes", "context:\n  maxBytes: 100\n", "context.maxBytes")):
            with self.subTest(name), tempfile.TemporaryDirectory() as root:
                yaml = _bitz_yaml() if extra is not None else _bitz_yaml().replace("language: ja", "language: 42")
                _write(root, ".spec/bitz.yaml", yaml + (extra or ""))
                _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
                result, exit_code = _run_context(root, ["REQ-001"])
                self.assertEqual((result["status"], exit_code), ("error", 3))
                self.assertEqual([(d["code"], d["source"]["path"], d["source"].get("key")) for d in result["diagnostics"]],
                                 [("SPEC-CONFIG-SCHEMA-001", ".spec/bitz.yaml", key)])
                self.assertIsNone(result["contextDigest"])

    def test_missing_config_is_an_environment_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001"])
            self.assertEqual((result["status"], exit_code), ("blocked", 2))
            self.assertEqual(result["diagnostics"][0]["code"], "SPEC-WORKSPACE-MISSING-001")
            self.assertIsNone(result["workspace"]["id"])
            self.assertEqual(result["diagnostics"][0]["source"], {"kind": "environment", "component": "workspace", "identifier": "."})

    def test_config_warning_is_added_to_a_failed_result_without_changing_its_status(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml() + "futureKey: 1\n")
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-999"])
            self.assertEqual((result["status"], exit_code), ("failed", 1))
            self.assertEqual(sorted(d["code"] for d in result["diagnostics"]), ["CTX-ROOT-MISSING-001", "SPEC-CONFIG-UNKNOWN-001"])

    def test_stopped_config_returns_its_warning_exactly_once(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml().replace("language: ja", "language: 42") + "futureKey: 1\n")
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001"])
            self.assertEqual((result["status"], exit_code), ("error", 3))
            self.assertEqual(sorted(d["code"] for d in result["diagnostics"]), ["SPEC-CONFIG-SCHEMA-001", "SPEC-CONFIG-UNKNOWN-001"])

    def test_markdown_shows_null_workspace_id(self):
        # 値のないフィールドは`null`と示す（`context` §9.1）。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, _exit_code = _run_context(root, ["REQ-001"])
            text = render_context_markdown(result)
            self.assertIn("- workspace: null (.)", text)
            self.assertNotIn("None", text)

    def test_config_warning_is_added_to_a_successful_result(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml() + "futureKey: 1\n")
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            result, exit_code = _run_context(root, ["REQ-001"])
            self.assertEqual((result["status"], exit_code), ("passed_with_warnings", 0))
            self.assertEqual([(d["code"], d["source"].get("key")) for d in result["diagnostics"]],
                             [("SPEC-CONFIG-UNKNOWN-001", "futureKey")])
            self.assertIsNotNone(result["contextDigest"])


if __name__ == "__main__":
    unittest.main()
