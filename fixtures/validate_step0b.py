#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""Read-only Step 0B audit. Missing evidence never counts as a pass."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote

from jsonschema import Draft202012Validator, ValidationError
sys.dont_write_bytecode = True
from conformance.diagnostic_coverage import validate as validate_diagnostic_coverage
from conformance.target_vectors import validate as validate_target_vectors

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
                errors.append(f"{path.relative_to(ROOT)}: missing {link}")
            elif anchor and destination.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(), re.M)
                if anchor not in {slug(h) for h in headings}:
                    errors.append(f"{path.relative_to(ROOT)}: missing anchor {link}")
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
    # EBNF quoted terminals do not use C-style backslash escaping.
    unquoted = re.sub(r'"[^"]*"|\x27[^\x27]*\x27', "", source)
    references = set(re.findall(r"[A-Za-z][A-Za-z0-9-]*", unquoted))
    lexical = {"plain-char", "qchar", "code-char"}
    errors = sorted(references - set(definitions) - lexical)
    if len(definitions) != len(set(definitions)):
        errors.append("duplicate definition")
    return {"definitions": len(definitions), "prose_lexical_definitions": sorted(lexical), "errors": errors}


def matrix():
    text = (COMMON / "04_適合fixture仕様.md").read_text()
    rows = re.findall(r"^\| `(SINGLE-\d{3}(?:-\d{2})?|MONO-\d{3}(?:-\d{2})?)` \|(.*)$", text, re.M)
    ids = [identifier for identifier, _ in rows]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("duplicate matrix ID")
    for identifier, row in rows:
        if identifier.rsplit("-", 1)[0] in ids:
            errors.append(f"{identifier}: family and suffixed ID coexist")
        if re.search(r"元status|passed/0、failed/1", row):
            errors.append(f"{identifier}: ambiguous expected result")
    found = {p.parent.name for p in FIXTURES.glob("*/*/manifest.json")}
    missing = sorted(set(ids) - found)
    for identifier in sorted(found - set(ids)):
        errors.append(f"{identifier}: no matrix row")
    validator = Draft202012Validator(json.loads((FIXTURES / "manifest.schema.json").read_text()))
    result_validator = Draft202012Validator(json.loads((FIXTURES / "result.schema.json").read_text()))
    for path in sorted(FIXTURES.glob("*/*/manifest.json")):
        try:
            manifest = json.loads(path.read_text())
            validator.validate(manifest)
            if manifest["fixtureId"] != path.parent.name:
                errors.append(f"{path}: fixtureId differs from directory")
            if not (path.parent / "repo").is_dir():
                errors.append(f"{path}: missing repo directory")
            referenced = set()
            for key in ("resultFile", "textFile"):
                if key not in manifest["expect"]:
                    continue
                expected = (path.parent / manifest["expect"][key]).resolve()
                if not expected.is_relative_to((path.parent / "expected").resolve()) or not expected.is_file():
                    errors.append(f"{path}: missing or unsafe {key}")
                    continue
                referenced.add(expected)
                if key == "resultFile" and manifest["invocation"]["runner"] == "bitz":
                    result_validator.validate(json.loads(expected.read_text()))
            unreferenced = {p.resolve() for p in (path.parent / "expected").glob("*") if p.is_file()} - referenced
            # Canonical bytes are compared separately by the golden digest check.
            unreferenced = {p for p in unreferenced if p.name != "context.canonical.json"}
            if unreferenced:
                errors.append(f"{path}: unreferenced expectations")
        except (ValueError, ValidationError) as error:
            errors.append(f"{path.relative_to(ROOT)}: {str(error).split(chr(10))[0]}")
    return {"matrix_ids": len(ids), "missing_fixtures": missing, "errors": errors}


def registry():
    path = COMMON / "05_Diagnostic-registry.md"
    rows = re.findall(r"^\| `([^`]+)` \| ([^|]+) \| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| `([^`]+)` \| (\d+) \| (.*)\|$", path.read_text(), re.M)
    ids = [r[0] for r in rows]
    errors = []
    if not rows or len(ids) != len(set(ids)):
        errors.append("empty registry or duplicate conditionId")
    for row in rows:
        if row[3].strip() not in {"info", "warning", "error"} or row[4].strip() not in {"passed", "passed_with_warnings", "failed", "blocked", "error"}:
            errors.append(f"{row[0]}: invalid vocabulary")
    coverage = validate_diagnostic_coverage()
    coverage["errors"] = errors + coverage["errors"]
    return coverage


def main():
    checks = {"public_json": public_json(), "grammar": grammar(), "matrix": matrix(), "registry": registry(), "links": links(), "target_vectors": validate_target_vectors()}
    perf = subprocess.run([sys.executable, str(ROOT / "fixtures/validate_step0p.py")], capture_output=True, text=True, timeout=60)
    checks["step0p"] = json.loads(perf.stdout) if perf.returncode == 0 else {"errors": [perf.stderr]}
    helpers = subprocess.run([sys.executable, "-B", str(FIXTURES / "test_harness.py")], capture_output=True, text=True, timeout=30)
    checks["infrastructure_self_tests"] = {"status": "Passed" if helpers.returncode == 0 else "Failed", "errors": [] if helpers.returncode == 0 else [helpers.stderr]}
    audit_tests = subprocess.run([sys.executable, "-B", str(ROOT / "fixtures/test_step0b_audit.py")], capture_output=True, text=True, timeout=30)
    checks["audit_self_tests"] = {"status": "Passed" if audit_tests.returncode == 0 else "Failed", "errors": [] if audit_tests.returncode == 0 else [audit_tests.stderr]}
    # These checks are deliberately not certified by structural checks or helper tests.
    # Replace each entry only with a check of its actual, reviewed evidence.
    pending = ["independent golden Context Digest", "per-fixture side-effect expectations",
               "conformance inputs and expectations", "full Gate A fresh-checkout repeatability"]
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
