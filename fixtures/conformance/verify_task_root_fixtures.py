"""done TASKを起点とするreview済みvector（Core操作は実行しない）。

`SINGLE-068`は、statusが`done`のTASKをverifyする。cancelledの起点を遮断する`SINGLE-067`に
対応する成功側のfixtureである。Contextは[関係・トレースモデル §6.3]に従い、TASKの起点は
`addresses`の対象を所有する文書を`contextDocuments`に加える。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-068"
TASK_PATH = ".spec/tasks/TASK-001.md"
TITLE = "完了済みの実装作業"
TASK_DOCUMENT = (
    "---\n"
    f"id: TASK-001\ntitle: {TITLE}\nstatus: done\n"
    "relations:\n  addresses: [REQ-001:AC-01]\n"
    "changes: [src/auth.py]\n"
    "---\n"
    f"\n# TASK-001 {TITLE}\n"
    "\n## Objective\n\nAC-01を実装した。done TASKは再検証できる。\n"
)
TASK_BODY = TASK_DOCUMENT[TASK_DOCUMENT.index("\n---\n") + 5:].lstrip("\n")
# AC-01だけをaddressesするので、AC-02はtargetではなく、そのtestも解決しない。
TARGET_STATEMENTS = ["REQ-001:AC-01"]
TEST_PATHS = ["tests/test_auth.py"]


def reviewed_inputs():
    return {**digest_reference.reviewed_inputs("SINGLE-042"), TASK_PATH: TASK_DOCUMENT.encode()}


def reviewed_digest_input():
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["roots"] = ["TASK-001"]
    task = {
        "id": "TASK-001", "workspaceId": "root", "kind": "task", "status": "done",
        "applicability": "applicable",
        "frontmatter": {
            "id": "TASK-001", "title": TITLE, "status": "done",
            "relations": {**digest_reference.EMPTY_RELATIONS, "addresses": ["REQ-001:AC-01"]},
            "implements": [], "tests": [], "verify": None, "changes": ["src/auth.py"]},
        "bodyText": TASK_BODY, "statements": [],
        "strongRelations": [{"relation": "addresses", "target": "REQ-001:AC-01"}],
    }
    # documents[]はコードポイント順: REQ-001 < TASK-001 < TECH-001。
    payload["documents"].insert(1, task)
    return payload


def context_digest():
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input()))


def reviewed_manifest():
    return {
        "fixtureId": IDENTIFIER,
        "description": "done TASK起点の再検証を許可する",
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "TASK-001", "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result():
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "TASK-001", "status": "passed", "contextDigest": context_digest(),
            "statements": list(TARGET_STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", *TEST_PATHS], "tests": list(TEST_PATHS),
            "covers": list(TARGET_STATEMENTS),
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_done_root(result):
    target = result["targetResults"][0]
    if target["status"] != "passed" or target["diagnostics"]:
        raise ValueError("done TASKの起点はDiagnosticなしで再検証できる必要があります")
    if target["statements"] != TARGET_STATEMENTS:
        raise ValueError("target規範文はTASKのaddressesだけから来る必要があります")
    command = result["commands"][0]
    if "tests/test_session.py" in command["tests"] or "REQ-001:AC-02" in command["covers"]:
        raise ValueError("addressesしていない規範文のtestをbindingへ入れてはいけません")


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
        result = json.loads((fixture / "expected/verify.json").read_text())
        effects = json.loads((fixture / "side-effects.json").read_text())
        for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
            validators[name].validate(value)
        if manifest != reviewed_manifest() or result != reviewed_result():
            raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
        check_done_root(result)
        inputs = reviewed_inputs()
        frontmatter, _ = digest_crosscheck.split_document(inputs[TASK_PATH].decode())
        Draft202012Validator({"$ref": "#/$defs/taskFrontmatter",
                              "$defs": schema["$defs"]}).validate(frontmatter)
        if frontmatter["status"] != "done":
            raise ValueError("審査済みの原因にはdone TASKの起点が必要です")
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("入力が審査済みcorpusと異なります")
        if effects["before"] != effects["after"]:
            raise ValueError("read-only期待値が書込みを許しています")
        previous = None
        with tempfile.TemporaryDirectory(prefix="bitz-verify-task-root-") as temporary:
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
                derived = digest_crosscheck.canonical_bytes(
                    digest_crosscheck.build(repository, root="TASK-001"))
                if derived != digest_reference.canonical_bytes(reviewed_digest_input()):
                    raise ValueError("reference AとBのCanonical JSONが一致しません")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
