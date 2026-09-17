#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""読取り専用のStep 0B監査。証拠の欠落を合格として数えない。"""
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote

from jsonschema import Draft202012Validator, ValidationError
sys.dont_write_bytecode = True
from conformance import parser_expectations
from conformance.diagnostic_coverage import validate as validate_diagnostic_coverage
from conformance.target_vectors import validate as validate_target_vectors
from conformance.initial_fixtures import validate as validate_initial_fixtures
from conformance.ears_fixtures import validate as validate_ears_fixtures
from conformance.document_fixtures import validate as validate_document_fixtures
from conformance.trace_fixtures import validate as validate_trace_fixtures
from conformance.graph_fixtures import validate as validate_graph_fixtures
from conformance.git_fixtures import validate as validate_git_fixtures
from conformance.task_fixtures import validate as validate_task_fixtures
from conformance.selection_fixtures import validate as validate_selection_fixtures
from conformance.git_environment_fixtures import validate as validate_git_environment_fixtures
from conformance.context_failure_fixtures import validate as validate_context_failure_fixtures
from conformance.digest_fixtures import validate as validate_digest_fixtures
from conformance.context_limit_fixtures import validate as validate_context_limit_fixtures
from conformance.context_coverage_fixtures import validate as validate_context_coverage_fixtures
from conformance.projection_limit_fixtures import validate as validate_projection_limit_fixtures
from conformance.verify_fixtures import validate as validate_verify_fixtures
from conformance.verify_binding_fixtures import validate as validate_verify_binding_fixtures
from conformance.verify_process_fixtures import validate as validate_verify_process_fixtures
from conformance.verify_output_fixtures import validate as validate_verify_output_fixtures
from conformance.verify_document_fixtures import validate as validate_verify_document_fixtures
from conformance.verify_task_root_fixtures import validate as validate_verify_task_root_fixtures
from conformance.report_absent_fixtures import validate as validate_report_absent_fixtures
from conformance.cli_error_fixtures import validate as validate_cli_error_fixtures
from conformance.report_write_fixtures import validate as validate_report_write_fixtures
from conformance.text_fixtures import validate as validate_text_fixtures
from conformance.frontmatter_fixtures import validate as validate_frontmatter_fixtures
from conformance.frontmatter_boundary_fixtures import validate as validate_frontmatter_boundaries
from conformance.side_effect_fixtures import validate as validate_side_effect_fixtures
from conformance.verify_argv_fixtures import validate as validate_verify_argv_fixtures
from conformance.verify_stream_fixtures import validate as validate_verify_stream_fixtures
from conformance.verify_argv_limit_fixtures import validate as validate_verify_argv_limit_fixtures
from conformance.input_limit_fixtures import validate as validate_input_limit_fixtures
from conformance.registry_closure_fixtures import validate as validate_registry_closure_fixtures
from conformance.scanner_fixtures import validate as validate_scanner_fixtures
from conformance.presentation_fixtures import validate as validate_presentation_fixtures
from conformance.target_root_fixtures import validate as validate_target_root_fixtures
from conformance.expansion_fixtures import validate as validate_expansion_fixtures
from conformance.ordering_fixtures import validate as validate_ordering_fixtures
from conformance.environment_fixtures import validate as validate_environment_fixtures

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "docs/03.詳細設計"
COMMON = DETAIL / "00_共通契約"
FIXTURES = ROOT / "fixtures/conformance"


def blocks(path, language):
    return re.findall(r"^```" + language + r"\s*\n(.*?)^```\s*$", path.read_text(), re.M | re.S)


def slug(heading):
    heading = heading.replace("`", "").lower()
    return "".join(c for c in heading if not unicodedata.category(c).startswith("P") or c in "-_").replace(" ", "-")


def links():
    paths = list(DETAIL.rglob("*.md"))
    paths += list((ROOT / "docs/02.設計書").glob("*.md"))
    paths += [p for p in (ROOT / "docs/02.設計書/10_決定記録").glob("*.md") if re.search(r"^status: accepted\s*$", p.read_text(), re.M | re.I)]
    errors = []
    checked = 0
    for path in sorted(set(paths)):
        for link in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", path.read_text()):
            if re.match(r"[a-z]+://", link):
                continue
            target, _, anchor = unquote(link.strip("<>")).partition("#")
            destination = (path.parent / target).resolve() if target else path
            checked += 1
            if not destination.exists():
                errors.append(f"{path.relative_to(ROOT)}: link先がありません {link}")
            elif anchor and destination.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(), re.M)
                if anchor not in {slug(h) for h in headings}:
                    errors.append(f"{path.relative_to(ROOT)}: anchorがありません {link}")
    return {"checked": checked, "errors": errors}


def public_json():
    schema = json.loads((FIXTURES / "result.schema.json").read_text())
    for path in FIXTURES.glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
    validators = {
        "result": Draft202012Validator(schema),
        "diagnostic": Draft202012Validator({"$ref": "#/$defs/diagnostic", "$defs": schema["$defs"]}),
        "manifest": Draft202012Validator(json.loads((FIXTURES / "manifest.schema.json").read_text())),
    }
    checked, other, errors = [], [], []
    for path in sorted(DETAIL.rglob("*.md")):
        for index, source in enumerate(blocks(path, "json"), 1):
            label = f"{path.relative_to(ROOT)}:json-{index}"
            try:
                value = json.loads(source)
                kind = "result" if isinstance(value.get("operation"), str) else "diagnostic" if "code" in value else "manifest" if "fixtureId" in value else None
                if kind:
                    validators[kind].validate(value)
                    checked.append(label)
                else:
                    other.append(label)
            except (ValueError, ValidationError) as error:
                errors.append({"example": label, "error": str(error).split("\n")[0]})
    return {"checked": checked, "non_public_result_examples": other, "errors": errors}


def grammar():
    path = DETAIL / "01_EARS-AI/01_言語・Semantic-IR仕様.md"
    source = "\n".join(blocks(path, "ebnf"))
    definitions = re.findall(r"^([A-Za-z][A-Za-z0-9-]*)\s*=", source, re.M)
    # EBNFのquoted terminalはC言語風のbackslash escapeを使わない。
    unquoted = re.sub(r'"[^"]*"|\x27[^\x27]*\x27', "", source)
    references = set(re.findall(r"[A-Za-z][A-Za-z0-9-]*", unquoted))
    lexical = {"plain-char", "qchar", "code-char"}
    errors = sorted(references - set(definitions) - lexical)
    if len(definitions) != len(set(definitions)):
        errors.append("定義が重複しています")
    return {"definitions": len(definitions), "prose_lexical_definitions": sorted(lexical), "errors": errors}


def matrix():
    text = (COMMON / "04_適合fixture仕様.md").read_text()
    rows = re.findall(r"^\| `(SINGLE-\d{3}(?:-\d{2})?|MULTI-\d{3}(?:-\d{2})?)` \|(.*)$", text, re.M)
    ids = [identifier for identifier, _ in rows]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("matrix IDが重複しています")
    for identifier, row in rows:
        if identifier.rsplit("-", 1)[0] in ids:
            errors.append(f"{identifier}: familyのIDと接尾辞付きIDが併存しています")
        if re.search(r"元status|passed/0、failed/1", row):
            errors.append(f"{identifier}: 期待結果が曖昧です")
    found = {p.parent.name for p in FIXTURES.glob("*/*/manifest.json")}
    missing = sorted(set(ids) - found)
    for identifier in sorted(found - set(ids)):
        errors.append(f"{identifier}: matrixに行がありません")
    validator = Draft202012Validator(json.loads((FIXTURES / "manifest.schema.json").read_text()))
    result_validator = Draft202012Validator(json.loads((FIXTURES / "result.schema.json").read_text()))
    for path in sorted(FIXTURES.glob("*/*/manifest.json")):
        try:
            manifest = json.loads(path.read_text())
            validator.validate(manifest)
            argv = manifest["invocation"]["argv"]
            # --baseを受け付けるのはcheckだけで、context、verify、doctorは基準版のoptionを持たない。
            if argv[0] == "check" and "baseCommit" in manifest["setup"] and "--base" not in argv:
                errors.append(f"{path}: commit済みfixtureには明示の--baseが必要です")
            if not manifest["setup"]["git"] and "--base" in argv:
                errors.append(f"{path}: Git不在fixtureでは--baseを使えません")
            if manifest["fixtureId"] != path.parent.name:
                errors.append(f"{path}: fixtureIdがdirectory名と異なります")
            if not (path.parent / "repo").is_dir():
                errors.append(f"{path}: repo directoryがありません")
            referenced = set()
            for key in ("resultFile", "textFile"):
                if key not in manifest["expect"]:
                    continue
                expected = (path.parent / manifest["expect"][key]).resolve()
                if not expected.is_relative_to((path.parent / "expected").resolve()) or not expected.is_file():
                    errors.append(f"{path}: {key}が存在しないか安全ではありません")
                    continue
                referenced.add(expected)
                if key == "resultFile" and manifest["invocation"]["runner"] == "bitz":
                    result = json.loads(expected.read_text())
                    result_validator.validate(result)
                    status_exit = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
                    if (result["operation"] != manifest["invocation"]["argv"][0]
                            or result["status"] != manifest["expect"].get("status")
                            or status_exit[result["status"]] != manifest["expect"]["exitCode"]):
                        errors.append(f"{path}: manifestと結果の操作、status、終了コードが一致しません")
                elif key == "resultFile":
                    # bitz以外のrunnerの標準出力はoutcomeだけを持つobjectである（ADR-046）。
                    outcome = manifest["expect"]["outcome"]
                    if (json.loads(expected.read_text()) != {"outcome": outcome}
                            or manifest["expect"]["exitCode"] != (1 if outcome == "rejected" else 0)):
                        errors.append(f"{path}: outcomeの出力または終了コードが規定と異なります")
            for _, expected_ir in parser_expectations.files(path.parent, manifest):
                value = json.loads(expected_ir.read_text())
                if not isinstance(value, list):
                    errors.append(f"{path}: Parserの期待値は完全なIRの配列である必要があります")
                referenced.add(expected_ir.resolve())
            unreferenced = {p.resolve() for p in (path.parent / "expected").glob("*") if p.is_file()} - referenced
            # Canonical JSONのbyte列は、golden Digestの検査で別に比べる。
            unreferenced = {p for p in unreferenced if p.name != "context.canonical.json"}
            if unreferenced:
                errors.append(f"{path}: 参照されていない期待値があります")
        except (ValueError, ValidationError) as error:
            errors.append(f"{path.relative_to(ROOT)}: {str(error).split(chr(10))[0]}")
    return {"matrix_ids": len(ids), "missing_fixtures": missing, "errors": errors}


def registry():
    path = COMMON / "05_Diagnostic-registry.md"
    rows = re.findall(r"^\| `([^`]+)` \| ([^|]+) \| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| `([^`]+)` \| (\d+) \| (.*)\|$", path.read_text(), re.M)
    ids = [r[0] for r in rows]
    errors = []
    if not rows or len(ids) != len(set(ids)):
        errors.append("registryが空か、conditionIdが重複しています")
    for row in rows:
        if row[3].strip() not in {"info", "warning", "error"} or row[4].strip() not in {"passed", "passed_with_warnings", "failed", "blocked", "error"}:
            errors.append(f"{row[0]}: 語彙が不正です")
    coverage = validate_diagnostic_coverage()
    coverage["errors"] = errors + coverage["errors"]
    return coverage


def main():
    checks = {"public_json": public_json(), "grammar": grammar(), "matrix": matrix(), "registry": registry(), "links": links(), "target_vectors": validate_target_vectors(), "initial_fixtures": validate_initial_fixtures(), "ears_fixtures": validate_ears_fixtures(), "document_fixtures": validate_document_fixtures(), "trace_fixtures": validate_trace_fixtures()}
    checks["graph_fixtures"] = validate_graph_fixtures()
    checks["git_fixtures"] = validate_git_fixtures()
    checks["task_fixtures"] = validate_task_fixtures()
    checks["selection_fixtures"] = validate_selection_fixtures()
    checks["git_environment_fixtures"] = validate_git_environment_fixtures()
    checks["context_failure_fixtures"] = validate_context_failure_fixtures()
    checks["digest_fixtures"] = validate_digest_fixtures()
    checks["context_limit_fixtures"] = validate_context_limit_fixtures()
    checks["context_coverage_fixtures"] = validate_context_coverage_fixtures()
    checks["projection_limit_fixtures"] = validate_projection_limit_fixtures()
    checks["verify_fixtures"] = validate_verify_fixtures()
    checks["verify_binding_fixtures"] = validate_verify_binding_fixtures()
    checks["verify_process_fixtures"] = validate_verify_process_fixtures()
    checks["verify_output_fixtures"] = validate_verify_output_fixtures()
    checks["verify_document_fixtures"] = validate_verify_document_fixtures()
    checks["verify_task_root_fixtures"] = validate_verify_task_root_fixtures()
    checks["report_absent_fixtures"] = validate_report_absent_fixtures()
    checks["cli_error_fixtures"] = validate_cli_error_fixtures()
    checks["report_write_fixtures"] = validate_report_write_fixtures()
    checks["text_fixtures"] = validate_text_fixtures()
    checks["frontmatter_fixtures"] = validate_frontmatter_fixtures()
    checks["frontmatter_boundary_fixtures"] = validate_frontmatter_boundaries()
    checks["side_effect_fixtures"] = validate_side_effect_fixtures()
    checks["verify_argv_fixtures"] = validate_verify_argv_fixtures()
    checks["verify_stream_fixtures"] = validate_verify_stream_fixtures()
    checks["verify_argv_limit_fixtures"] = validate_verify_argv_limit_fixtures()
    checks["input_limit_fixtures"] = validate_input_limit_fixtures()
    checks["registry_closure_fixtures"] = validate_registry_closure_fixtures()
    checks["scanner_fixtures"] = validate_scanner_fixtures()
    checks["presentation_fixtures"] = validate_presentation_fixtures()
    checks["target_root_fixtures"] = validate_target_root_fixtures()
    checks["expansion_fixtures"] = validate_expansion_fixtures()
    checks["ordering_fixtures"] = validate_ordering_fixtures()
    checks["environment_fixtures"] = validate_environment_fixtures()
    perf = subprocess.run([sys.executable, str(ROOT / "fixtures/validate_step0p.py")], capture_output=True, text=True, timeout=60)
    checks["step0p"] = json.loads(perf.stdout) if perf.returncode == 0 else {"errors": [perf.stderr]}
    helpers = subprocess.run([sys.executable, "-B", str(FIXTURES / "test_harness.py")], capture_output=True, text=True, timeout=30)
    checks["infrastructure_self_tests"] = {"status": "Passed" if helpers.returncode == 0 else "Failed", "errors": [] if helpers.returncode == 0 else [helpers.stderr]}
    audit_tests = subprocess.run([sys.executable, "-B", str(ROOT / "fixtures/test_step0b_audit.py")], capture_output=True, text=True, timeout=180)
    checks["audit_self_tests"] = {"status": "Passed" if audit_tests.returncode == 0 else "Failed", "errors": [] if audit_tests.returncode == 0 else [audit_tests.stderr]}
    # これらの検査は、構造の検査やhelperの試験では意図して保証しない。
    # 各項目は、実際のreview済みの証拠の検査でだけ置き換える。
    pending = ["per-fixture side-effect expectations", "conformance inputs and expectations",
               "full Gate A fresh-checkout repeatability",
               # MULTI-002-01が複合workspaceのgoldenを所有するが、fixtureはまだない。
               "independent multi-workspace golden Context Digest"]
    if checks["digest_fixtures"]["status"] != "Passed":
        pending.insert(0, "independent single-workspace golden Context Digest")
    if checks["registry"]["semantic_coverage"] != "Passed":
        pending.insert(0, "Diagnostic semantic coverage")
    if checks["target_vectors"]["status"] != "Passed":
        pending.insert(0, "target expansion vectors")
    passed = not pending and all(not result.get("errors") for result in checks.values())
    report = {"gateA": "Allowed" if passed else "Blocked", "checks": checks, "pending": pending}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
