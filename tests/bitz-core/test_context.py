"""`bitz context`（`context.py`／`contextrender.py`）の単体試験。

`03_操作仕様/01_context.md`の主要規則（purpose別閉包、role、coverage 5区分、projectionの
必須・禁止field、Markdown §9の規則、上限、stale検出）を、fixtureが直接検査しない範囲も含めて
広く確認する。golden Digest値そのものの一致は`fixtures/conformance/single/SINGLE-042`等の
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
            self.assertEqual(exit_code, 2)  # MUSTがuntested（testなし）のためblocked。
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
        # REQ-002（draft）がREQ-001（起点・承認済み）をrefinesする＝§6.1「6.」のdraft refinement。
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
    """Digest正規化仕様 §2「3.正規化 → 4.重複排除とsort」の順序（司令塔の是正1）。"""

    def test_relations_dedup_after_nfc_not_before(self):
        from bitz import context as ctx_mod
        from bitz import document as doc_mod

        composed = "é"  # 'é'（単一code point、NFC）
        decomposed = "é"  # 'e' + 結合アクセント（NFD）。NFC後は`composed`と同一になる。
        # `relations.related`はID構文検査を経ないtarget文字列を保持するため、任意文字列を使える。
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
        # NFC後は同一文字列になるため、重複排除で1件だけ残る。
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
    """関係・トレースモデル §6.1「5.」、§7 role表（司令塔の是正4）。"""

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
            # Coreは後継へ暗黙に起点を差し替えない: rootsはTECH-001のまま。
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
        # interpretのadvisory/replacement表示は、implement/verifyの既存の遮断を変えない。
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
            # 依存状態は健全。MUSTがuntestedのためblockedになるが、状態系codeではない。
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertNotIn("CTX-STATE-001", codes)
            self.assertNotIn("CTX-STATE-SUPERSEDED-001", codes)


class TaskAddressedRefinementTests(unittest.TestCase):
    """関係・トレースモデル §6.4「規則3」: TASK起点のaddresses先のapplicable refinement（司令塔の是正7）。"""

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
    """context.md §4「unresolvedStrongRelations」（司令塔の是正6）。"""

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


if __name__ == "__main__":
    unittest.main()
