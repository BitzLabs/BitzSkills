"""Reviewed implement-purpose coverage vector; runs no Core operation.

`SINGLE-054` is the one Context fixture in this group with a success status, so
it is the only one that delivers a full Bundle and a computed Digest. The Digest
is cross-checked by the same two independent references as the golden family.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from .digest_fixtures import LEDGER, reviewed_result as reviewed_verify_result
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-054"
TASK_PATH = ".spec/tasks/TASK-001.md"
TASK_DOCUMENT = (
    "---\n"
    "id: TASK-001\n"
    "title: SHOULD句の実装\n"
    "status: open\n"
    "relations:\n"
    "  addresses: [REQ-001:AC-02]\n"
    "changes: [src/session.py]\n"
    "---\n"
    "\n"
    "# TASK-001 SHOULD句の実装\n"
    "\n"
    "## Objective\n"
    "\n"
    "AC-02を実装する。AC-01を`addresses`するTASKは意図的に置かない。\n"
)
TASK_BODY = TASK_DOCUMENT[TASK_DOCUMENT.index("\n---\n") + 5:].lstrip("\n")
# Only AC-02 is addressed, so the MUST statement AC-01 stays unaddressed and
# raises exactly one CTX-COVERAGE-TASK-001 warning.
COVERAGE = {
    "must": {"total": ["REQ-001:AC-01"], "addressed": [], "tested": ["REQ-001:AC-01"],
             "unaddressed": ["REQ-001:AC-01"], "untested": []},
    "should": {"total": ["REQ-001:AC-02"], "addressed": ["REQ-001:AC-02"],
               "tested": ["REQ-001:AC-02"], "unaddressed": [], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": [],
}


def reviewed_inputs():
    return {**digest_reference.reviewed_inputs("SINGLE-042"), TASK_PATH: TASK_DOCUMENT.encode()}


def reviewed_digest_input():
    """`implement` adds the addressing TASK to the closure but, unlike `verify`,
    does not name command, so settings records no binding."""
    payload = digest_reference.reviewed_digest_input("SINGLE-042")
    payload["purpose"] = "implement"
    payload["settings"]["verifyTimeouts"] = []
    payload["settings"]["commands"] = []
    task = {
        "id": "TASK-001",
        "workspaceId": "root",
        "kind": "task",
        "status": "open",
        "applicability": "applicable",
        "frontmatter": {
            "id": "TASK-001",
            "title": "SHOULD句の実装",
            "status": "open",
            "relations": {**digest_reference.EMPTY_RELATIONS, "addresses": ["REQ-001:AC-02"]},
            "implements": [],
            "tests": [],
            "verify": None,
            "changes": ["src/session.py"],
        },
        "bodyText": TASK_BODY,
        "statements": [],
        "strongRelations": [{"relation": "addresses", "target": "REQ-001:AC-02"}],
    }
    # documents[] is ordered by code point: REQ-001 < TASK-001 < TECH-001.
    payload["documents"].insert(1, task)
    return payload


def reviewed_manifest():
    return {
        "fixtureId": IDENTIFIER,
        "description": "implement対象MUSTが未addressedでcoverage 5区分を返す",
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "implement", "--format", "json"],
                       "env": {}},
        "expect": {"status": "passed_with_warnings", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(context_digest):
    # The REQ and TECH presentation is unchanged from the golden fixture; only the
    # addressing TASK is added, so the two stay in step by construction.
    documents = json.loads(json.dumps(
        reviewed_verify_result("SINGLE-042", context_digest)["documents"]))
    documents.append({
        "id": "TASK-001", "kind": "task", "status": "open", "role": "work",
        "path": TASK_PATH, "projection": "full", "reachedBy": ["addresses:TASK-001"],
        "statementRefs": [],
        "frontmatter": {"id": "TASK-001", "title": "SHOULD句の実装", "status": "open",
                        "relations": {"addresses": ["REQ-001:AC-02"]},
                        "changes": ["src/session.py"]},
        "bodyText": TASK_BODY, "untrustedText": True,
    })
    ledger = json.loads(json.dumps(LEDGER))
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed_with_warnings",
        "purpose": "implement",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": context_digest,
        "revision": None,
        "resolution": {"complete": True, "documentCount": 3, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": documents,
        "constraintLedger": {"statements": ledger},
        "coverage": json.loads(json.dumps(COVERAGE)),
        "durationMs": 0,
        "diagnostics": [{
            "code": "CTX-COVERAGE-TASK-001", "severity": "warning",
            "resultStatus": "passed_with_warnings",
            "summary": "implement対象のMUST REQ-001:AC-01を実装するTASKがありません",
            "source": {"kind": "file", "workspaceId": "root",
                       "path": ".spec/requirements/REQ-001.md"},
        }],
    }


def references(repository):
    literal = digest_reference.canonical_bytes(reviewed_digest_input())
    derived = digest_crosscheck.canonical_bytes(
        digest_crosscheck.build(repository, purpose="implement"))
    if literal != derived:
        raise ValueError("reference A and reference B disagree on the Canonical JSON")
    return literal


def check_coverage(result):
    buckets = result["coverage"]
    for modality in ("must", "should", "may"):
        bucket = buckets[modality]
        if set(bucket["addressed"]) - set(bucket["total"]) or set(bucket["tested"]) - set(bucket["total"]):
            raise ValueError("coverage reports a statement outside its own total")
        if sorted(bucket["addressed"] + bucket["unaddressed"]) != sorted(bucket["total"]):
            raise ValueError("addressed and unaddressed must partition total")
        if sorted(bucket["tested"] + bucket["untested"]) != sorted(bucket["total"]):
            raise ValueError("tested and untested must partition total")
    if not buckets["must"]["unaddressed"]:
        raise ValueError("the reviewed cause requires an unaddressed MUST")


def validate(root=HERE, identifiers=None):
    if identifiers is not None and IDENTIFIER not in identifiers:
        return {"prepared": [], "setups_per_fixture": 2, "core_execution": "Not run",
                "status": "Passed", "errors": []}
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    fixture = root / "single" / IDENTIFIER
    try:
        manifest = json.loads((fixture / "manifest.json").read_text())
        result = json.loads((fixture / "expected/context.json").read_text())
        effects = json.loads((fixture / "side-effects.json").read_text())
        for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
            validators[name].validate(value)
        canonical = (fixture / "expected/context.canonical.json").read_bytes()
        if canonical.endswith(b"\n") or canonical.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Canonical JSON must be UTF-8 without a BOM or trailing newline")
        if manifest != reviewed_manifest():
            raise ValueError("invocation differs from reviewed expectation")
        if result != reviewed_result(digest_reference.digest(canonical)):
            raise ValueError("complete result differs from reviewed expectation")
        check_coverage(result)
        golden = (root / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        if canonical == golden:
            raise ValueError("implement must not reuse the verify golden digest input")
        inputs = reviewed_inputs()
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("input differs from the reviewed corpus")
        frontmatter, _ = digest_crosscheck.split_document(inputs[TASK_PATH].decode())
        Draft202012Validator({"$ref": "#/$defs/taskFrontmatter", "$defs": schema["$defs"]}).validate(frontmatter)
        if effects["before"] != effects["after"]:
            raise ValueError("read-only expectation permits writes")
        previous = None
        with tempfile.TemporaryDirectory(prefix="bitz-context-coverage-") as temporary:
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
                if references(repository) != canonical:
                    raise ValueError("committed Canonical JSON differs from the reference computation")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
