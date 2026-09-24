"""implementのpurposeのcoverageを固定するreview済みvector（Core操作は実行しない）。

`SINGLE-054`はこの群で唯一成功statusのContext fixtureであり、完全なBundleと計算した
Digestを返す唯一のfixtureである。Digestは、golden群と同じ独立した2系統の参照計算で照合する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
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
# AC-02だけをaddressesするので、MUSTのAC-01はunaddressedのまま残り、
# CTX-COVERAGE-TASK-001の警告がちょうど1件出る。
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
    """`implement`は`addresses`するTASKを閉包に加えるが、`verify`と異なり
    commandを挙げないので、settingsはbindingを記録しない。"""
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
    # documents[]はコードポイント順: REQ-001 < TASK-001 < TECH-001。
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
    # REQとTECHの提示はgolden fixtureと同じで、addressesするTASKだけを加える。
    # そのため両者は構成上ずれない。
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
        raise ValueError("reference AとBのCanonical JSONが一致しません")
    return literal


def check_coverage(result):
    buckets = result["coverage"]
    for modality in ("must", "should", "may"):
        bucket = buckets[modality]
        if set(bucket["addressed"]) - set(bucket["total"]) or set(bucket["tested"]) - set(bucket["total"]):
            raise ValueError("coverageが自身のtotal外の規範文を報告しています")
        if sorted(bucket["addressed"] + bucket["unaddressed"]) != sorted(bucket["total"]):
            raise ValueError("addressedとunaddressedはtotalを分割する必要があります")
        if sorted(bucket["tested"] + bucket["untested"]) != sorted(bucket["total"]):
            raise ValueError("testedとuntestedはtotalを分割する必要があります")
    if not buckets["must"]["unaddressed"]:
        raise ValueError("審査済みの原因にはunaddressedのMUSTが必要です")


def validate(root=HERE, identifiers=None):
    if identifiers is not None and IDENTIFIER not in identifiers:
        return {"prepared": [], "setups_per_fixture": 2, "core_execution": "Not run",
                "status": "Passed", "errors": []}
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    fixture = root / "single" / IDENTIFIER
    try:
        manifest = json.loads((fixture / "manifest.json").read_text())
        result = json.loads((fixture / "expected/context.json").read_text())
        effects = json.loads((fixture / "side-effects.json").read_text())
        for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
            validators[name].validate(value)
        canonical = (fixture / "expected/context.canonical.json").read_bytes()
        if canonical.endswith(b"\n") or canonical.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Canonical JSONはBOMと末尾改行のないUTF-8である必要があります")
        if manifest != reviewed_manifest():
            raise ValueError("起動条件が審査済み期待値と異なります")
        if result != reviewed_result(digest_reference.digest(canonical)):
            raise ValueError("完全結果が審査済み期待値と異なります")
        check_coverage(result)
        golden = (root / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        if canonical == golden:
            raise ValueError("implementはverifyのgolden Digest材料を再利用してはいけません")
        inputs = reviewed_inputs()
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("入力が審査済みcorpusと異なります")
        frontmatter, _ = digest_crosscheck.split_document(inputs[TASK_PATH].decode())
        Draft202012Validator({"$ref": "#/$defs/taskFrontmatter", "$defs": schema["$defs"]}).validate(frontmatter)
        if effects["before"] != effects["after"]:
            raise ValueError("read-only期待値が書込みを許しています")
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
                    raise ValueError("隔離setupが固定snapshotと異なります")
                previous = actual
                if references(repository) != canonical:
                    raise ValueError("commitしたCanonical JSONが参照計算と異なります")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
