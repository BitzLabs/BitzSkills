"""Audit the single-workspace Context Digest fixtures; runs no Core operation.

Each fixture is checked against the reviewed expectation, and its committed
Canonical JSON is checked against two independently written reference
computations (digest_reference A from reviewed literals, digest_crosscheck B
from the input tree). Digest equality and inequality across the family are
compared as bytes, not only as hash strings.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference, parser_expectations
from .digest_reference import CASES, DESCRIPTIONS, SAME_AS_GOLDEN
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
GOLDEN = "SINGLE-042"
REQ_RESULT_PATH = ".spec/requirements/REQ-001.md"
TECH_RESULT_PATH = ".spec/technical/TECH-001.md"
LEDGER = [
    {"id": "REQ-001:AC-01", "documentId": "REQ-001", "documentRole": "root", "modality": "MUST",
     "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
     "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}},
    {"id": "REQ-001:AC-02", "documentId": "REQ-001", "documentRole": "root", "modality": "SHOULD",
     "reason": "確認のため", "actor": "TargetSystem",
     "activation": {"kind": "WHEN", "text": "保存した場合"},
     "operation": {"kind": "THEN", "text": "結果を返す"}},
]
COVERAGE = {
    "must": {"total": ["REQ-001:AC-01"], "addressed": [], "tested": ["REQ-001:AC-01"],
             "unaddressed": ["REQ-001:AC-01"], "untested": []},
    "should": {"total": ["REQ-001:AC-02"], "addressed": [], "tested": ["REQ-001:AC-02"],
               "unaddressed": ["REQ-001:AC-02"], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": [],
}


def reviewed_manifest(identifier):
    tail = CASES[identifier][0]
    return {
        **({"parserChecks": [{"path": REQ_RESULT_PATH, "resultFile": "expected/parser-ir.json"}]}
           if identifier in {"SINGLE-096-01", "SINGLE-097-01", "SINGLE-098-01", "SINGLE-101-01"} else {}),
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", *tail, "--format", "json"],
                       "env": {}},
        "expect": {"status": "passed_with_warnings" if identifier == "SINGLE-098-01" else "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(identifier, context_digest):
    _, req_body, tech_body, _ = CASES[identifier]
    detail = "full" if identifier in {"SINGLE-043-01", "SINGLE-106-01"} else "standard"
    expanded = ["TECH-001"] if identifier == "SINGLE-043-02" else []
    if identifier == "SINGLE-127-03":
        expanded = ["REQ-001", "TECH-001"]
    elif identifier == "SINGLE-127-04":
        expanded = ["TECH-001"]
    ledger = [dict(statement) for statement in LEDGER]
    if identifier == "SINGLE-097-01":
        ledger[0] = {**ledger[0], "operation": {"kind": "CONSTRAINT", "text": digest_reference.DECODED_TEXT}}
    if identifier == "SINGLE-096-01":
        ledger[0] = {**ledger[0], "operation": {"kind": "CONSTRAINT", "text": digest_reference.CODE_VALUE}}
    result = {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": context_digest,
        "revision": None,
        "resolution": {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0},
        "projection": {"detail": detail, "expanded": expanded},
        "documents": [
            {"id": "REQ-001", "kind": "requirement", "status": "approved", "role": "root",
             "path": REQ_RESULT_PATH, "projection": "full", "reachedBy": ["root"],
             "statementRefs": ["REQ-001:AC-01", "REQ-001:AC-02"],
             "frontmatter": {"id": "REQ-001", "title": "認証Contextの基準", "status": "approved"},
             "bodyText": req_body, "untrustedText": True},
            {"id": "TECH-001", "kind": "technical", "status": "approved", "role": "refinement",
             "path": TECH_RESULT_PATH, "projection": "full", "reachedBy": ["refines:TECH-001"],
             "statementRefs": [],
             "frontmatter": {"id": "TECH-001", "title": "認証の実装方針", "status": "approved",
                             "relations": {"refines": ["REQ-001"], "related": ["ADR-001"]},
                             "implements": ["src/auth.py", "src/session.py"],
                             "tests": [{"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01"],
                                        "command": "default"},
                                       {"path": "tests/test_session.py", "covers": ["REQ-001:AC-02"],
                                        "command": "default"}]},
             "bodyText": tech_body, "untrustedText": True},
        ],
        "constraintLedger": {"statements": ledger},
        "coverage": json.loads(json.dumps(COVERAGE)),
        "durationMs": 0,
        "diagnostics": [],
    }

    if identifier == "SINGLE-098-01":
        result["status"] = "passed_with_warnings"
        result["diagnostics"] = [{"code": "EAI-EXT-UNKNOWN-001", "severity": "warning",
            "resultStatus": "passed_with_warnings", "summary": "未知namespaceのextensionを保持します",
            "source": {"kind": "file", "workspaceId": "root", "path": REQ_RESULT_PATH,
                       "line": 15, "column": 19}}]
    if identifier == "SINGLE-106-02":
        result["resolution"]["documentCount"] = 3
        result["documents"].append({
            "id": "TECH-002", "kind": "technical", "status": "approved", "role": "refinement",
            "path": digest_reference.NORMATIVE_PATH, "projection": "normative",
            "reachedBy": ["refines:TECH-002"], "statementRefs": [], "untrustedText": True,
        })
    return result


def references(identifier, repository):
    """Two independently written computations of the same digest input."""
    literal = digest_reference.canonical_bytes(digest_reference.reviewed_digest_input(identifier))
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
    if literal != derived:
        raise ValueError("reference A and reference B disagree on the Canonical JSON")
    if digest_reference.digest(literal) != digest_crosscheck.digest(derived):
        raise ValueError("reference A and reference B disagree on the Digest")
    return literal


def validate(root=HERE, identifiers=None):
    errors, prepared, canonical_by_fixture = [], [], {}
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/context.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            canonical = (fixture / "expected/context.canonical.json").read_bytes()
            if canonical != canonical.decode("utf-8").encode("utf-8") or canonical.endswith(b"\n"):
                raise ValueError("Canonical JSON must be UTF-8 without a trailing newline")
            if canonical.startswith(b"\xef\xbb\xbf"):
                raise ValueError("Canonical JSON must not carry a BOM")
            if manifest != reviewed_manifest(identifier):
                raise ValueError("invocation differs from reviewed expectation")
            if result != reviewed_result(identifier, digest_reference.digest(canonical)):
                raise ValueError("complete result differs from reviewed expectation")
            inputs = digest_reference.reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the reviewed corpus")
            for path, kind in ((".spec/requirements/REQ-001.md", "reqFrontmatter"),
                               (".spec/technical/TECH-001.md", "techFrontmatter"),
                               (".spec/decisions/ADR-001.md", "adrFrontmatter")):
                frontmatter, _ = digest_crosscheck.split_document(inputs[path].decode())
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-digest-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
                    parser_expectations.validate_checks(fixture, manifest, repository)
                    computed = references(identifier, repository)
                    if computed != canonical:
                        raise ValueError("committed Canonical JSON differs from the reference computation")
            canonical_by_fixture[identifier] = canonical
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")

    if GOLDEN in canonical_by_fixture:
        golden = canonical_by_fixture[GOLDEN]
        for identifier, canonical in canonical_by_fixture.items():
            same = identifier in SAME_AS_GOLDEN
            if same and canonical != golden:
                errors.append(f"{identifier}: Digest input must be byte-identical to the golden")
            if not same and canonical == golden:
                errors.append(f"{identifier}: Digest input must differ from the golden")
    elif identifiers is None:
        errors.append(f"{GOLDEN}: golden fixture is required to compare the family")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
