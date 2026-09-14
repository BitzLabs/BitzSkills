"""Reviewed presentation hard-limit vector; runs no Core operation.

`SINGLE-049` resolves completely inside the configured closure limits and then
fails only because `--detail full` would present more than the fixed 1 MiB
presentation hard limit. The corpus is built so that the standard presentation
stays small while the full presentation crosses the limit.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from .context_limit_fixtures import EMPTY_COVERAGE
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-049"
HARD_LIMIT_BYTES = 1048576
# Both closure dimensions are configured at their maxima, so the closure passes and
# only the fixed presentation hard limit can be crossed.
CONFIG = digest_reference.CONFIG + "context:\n  maxDocuments: 100\n  maxBytes: 1048576\n"
REQ_HEAD = "---\nid: REQ-001\ntitle: 提示量の基準\nstatus: approved\n---\n"
REQ_BODY = (
    "# REQ-001 提示量の基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "提示hard limitの検査に使う固定要求を定義する。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "\n"
    "## Verification\n"
    "\n"
    "提示量の上限で確認する。\n"
)
PAD_LINE = "この段落は提示hard limitを超えるための固定本文であり、意味を持たない。\n"
# Chosen so the two indirect refinements together exceed 1 MiB of body text while
# each file stays under the 1 MiB single-document input limit.
PAD_REPEAT = 5300
SMALL_TECH_BODY = "# TECH-001 直接の具体化\n\n## Context\n\n距離1の具体化。\n"


def large_body(number, title):
    return f"# TECH-{number:03} {title}\n\n## Context\n\n{PAD_LINE * PAD_REPEAT}"


DOCUMENTS = {
    ".spec/technical/TECH-001.md": ("TECH-001", "直接の具体化", "REQ-001", SMALL_TECH_BODY),
    ".spec/technical/TECH-002.md": ("TECH-002", "間接の具体化", "TECH-001", large_body(2, "間接の具体化")),
    ".spec/technical/TECH-003.md": ("TECH-003", "さらに間接の具体化", "TECH-002", large_body(3, "さらに間接の具体化")),
}
ORDER = ["REQ-001", "TECH-001", "TECH-002", "TECH-003"]


def technical_document(path):
    identifier, title, target, body = DOCUMENTS[path]
    return (f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n"
            f"relations:\n  refines: [{target}]\n---\n\n" + body)


def reviewed_inputs():
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode(),
              digest_reference.REQ_PATH: (REQ_HEAD + "\n" + REQ_BODY).encode()}
    for path in DOCUMENTS:
        inputs[path] = technical_document(path).encode()
    return inputs


def reviewed_digest_input():
    documents = [{
        "id": "REQ-001", "workspaceId": "root", "kind": "requirement", "status": "approved",
        "applicability": "applicable",
        "frontmatter": {"id": "REQ-001", "title": "提示量の基準", "status": "approved",
                        "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [],
                        "tests": [], "verify": None, "changes": []},
        "bodyText": REQ_BODY,
        "statements": [dict(digest_reference.STATEMENTS[0])],
        "strongRelations": [],
    }]
    for path in DOCUMENTS:
        identifier, title, target, body = DOCUMENTS[path]
        documents.append({
            "id": identifier, "workspaceId": "root", "kind": "technical", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": identifier, "title": title, "status": "approved",
                            "relations": {**digest_reference.EMPTY_RELATIONS, "refines": [target]},
                            "implements": [], "tests": [], "verify": None, "changes": []},
            "bodyText": body, "statements": [],
            "strongRelations": [{"relation": "refines", "target": target}],
        })
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "verify", "requestWorkspaceId": "root",
        "roots": ["REQ-001"], "workspaces": [{"id": "root", "path": "."}],
        "documents": documents, "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 100, "maxBytes": 1048576},
            "verifyTimeouts": [], "commands": [],
        },
    }


def reviewed_manifest():
    return {
        "fixtureId": IDENTIFIER,
        "description": "detailによる提示量が1 MiBのhard limitを超過する",
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", "--detail", "full",
                                "--format", "json"],
                       "env": {}},
        "expect": {"status": "failed", "exitCode": 1, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": context_digest,
        "revision": None,
        "resolution": {"complete": True, "documentCount": 4, "unresolvedStrongRelations": 0},
        # `detail` echoes the requested mode; `expanded` lists what was actually applied.
        "projection": {"detail": "full", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0,
        "diagnostics": [{
            "code": "CTX-PROJECTION-LIMIT-001", "severity": "error", "resultStatus": "failed",
            "summary": "detail fullの提示量が1 MiBのhard limitを超過します",
            "source": {"kind": "invocation", "argument": "--detail"},
        }],
    }


def check_limits(inputs):
    """The corpus must cross the presentation hard limit only under `--detail full`:
    every large body is projected `normative` at `standard` and `full` at `full`."""
    bodies = {"REQ-001": REQ_BODY, **{DOCUMENTS[path][0]: DOCUMENTS[path][3] for path in DOCUMENTS}}
    full = sum(len(body.encode()) for body in bodies.values())
    standard = sum(len(bodies[identifier].encode()) for identifier in ("REQ-001", "TECH-001"))
    if full <= HARD_LIMIT_BYTES:
        raise ValueError("full presentation does not exceed the 1 MiB hard limit")
    if standard >= HARD_LIMIT_BYTES:
        raise ValueError("standard presentation must stay inside the hard limit")
    for path, payload in inputs.items():
        if path.endswith(".md") and len(payload) >= HARD_LIMIT_BYTES:
            raise ValueError("a single SPEC file must stay under the 1 MiB input limit")
    if len(bodies) > 100:
        raise ValueError("the document count must stay inside the configured closure limit")


def validate(root=HERE, identifiers=None):
    if identifiers is not None and IDENTIFIER not in identifiers:
        return {"prepared": [], "setups_per_fixture": 2, "core_execution": "Not run",
                "status": "Passed", "errors": []}
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
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
        if result["documents"] or result["constraintLedger"]["statements"]:
            raise ValueError("a non-success Context must not deliver Bundle material")
        inputs = reviewed_inputs()
        check_limits(inputs)
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("input differs from the reviewed corpus")
        if effects["before"] != effects["after"]:
            raise ValueError("read-only expectation permits writes")
        previous = None
        with tempfile.TemporaryDirectory(prefix="bitz-projection-limit-") as temporary:
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
                literal = digest_reference.canonical_bytes(reviewed_digest_input())
                derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                if literal != derived:
                    raise ValueError("reference A and reference B disagree on the Canonical JSON")
                if literal != canonical:
                    raise ValueError("committed Canonical JSON differs from the reference computation")
                order = [document["id"] for document in json.loads(derived.decode())["documents"]]
                if order != ORDER:
                    raise ValueError("digest documents are not in the reviewed order")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
