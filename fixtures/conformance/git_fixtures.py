"""Fixed base/current Git fixture evidence, without Core state/check logic."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH

HERE = Path(__file__).resolve().parent
TASK_PATH = ".spec/tasks/TASK-001.md"
RENAMED_PATH = ".spec/technical/TECH-001-renamed.md"
TASK = "---\nid: TASK-001\ntitle: 完了した作業\nstatus: done\n---\n\n# TASK-001 完了した作業\n\n## Objective\n\n状態遷移を確認する。\n"
CHANGE = "changes/document.md"
# id: (base document path, base bytes, operation, current bytes, status, code, key, summary)
CASES = {
    "SINGLE-027": (TASK_PATH, TASK, "update", TASK.replace("status: done", "status: open"), "failed",
        "SPEC-STATE-TRANSITION-001", "status", "done TASKをopenへ戻すことはできません"),
    "SINGLE-028": (TASK_PATH, None, "create", TASK, "passed", None, None, None),
    "SINGLE-029": (TECH_PATH, TECH, "delete", None, "failed", "SPEC-STATE-TRANSITION-001", None, "管理済みSPECが削除されています"),
    "SINGLE-030": (TECH_PATH, TECH, "rename", TECH, "passed", None, None, None),
    "SINGLE-031": (REQ_PATH, DOCUMENT, "update", DOCUMENT.replace("文書の検査", "変更後の文書検査"), "failed",
        "SPEC-SAFETY-APPROVED-001", "title", "approved REQの意味変更時にstatusが戻されていません"),
}


def reviewed_inputs(identifier):
    path, base, operation, current, *_ = CASES[identifier]
    files = {"repo/.spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if base is not None:
        files["repo/" + path] = base.encode()
    if operation in {"create", "update"}:
        files[CHANGE] = current.encode()
    return files


def reviewed_manifest(identifier):
    path, _, operation, _, status, *_ = CASES[identifier]
    if operation == "rename":
        operations = [{"op": "rename", "from": path, "to": RENAMED_PATH}, {"op": "stage", "paths": ["."]}]
    else:
        operations = [{"op": operation, "path": path}]
        if operation in {"create", "update"}:
            operations[0]["source"] = CHANGE
    return {"fixtureId": identifier, "description": CASES[identifier][7] or ("新規done TASK" if identifier == "SINGLE-028" else "IDを保ったstaged rename"),
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 0 if status == "passed" else 1,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    path, _, _, _, status, code, key, summary = CASES[identifier]
    source = {"kind": "file", "workspaceId": "root", "path": path}
    if key:
        source["key"] = key
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
        "workspace": {"id": "root", "path": "."}, "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": True},
        "checkedDocumentCount": 0 if identifier == "SINGLE-029" else 1,
        "checkedStatementCount": 1 if identifier == "SINGLE-031" else 0, "durationMs": 0,
        "diagnostics": [] if code is None else [{"code": code, "severity": "error", "resultStatus": status, "summary": summary, "source": source}]}


def check_git_states(repository, identifier):
    """Check real HEAD/index/worktree contents against the reviewed transition."""
    path, base, operation, current, *_ = CASES[identifier]
    base_files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if base is not None:
        base_files[path] = base.encode()
    head_paths = git(repository, "ls-tree", "-r", "--name-only", "-z", "HEAD").decode().split("\0")[:-1]
    if set(head_paths) != set(base_files):
        raise ValueError("HEAD paths differ from reviewed base")
    for name, content in base_files.items():
        if git(repository, "show", "HEAD:" + name) != content:
            raise ValueError("HEAD bytes differ from reviewed base")
    current_files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if current is not None:
        current_files[RENAMED_PATH if operation == "rename" else path] = current.encode()
    index_files = current_files if operation == "rename" else base_files
    index_paths = git(repository, "ls-files", "-z").decode().split("\0")[:-1]
    if set(index_paths) != set(index_files):
        raise ValueError("index paths differ from reviewed staging state")
    for name, content in index_files.items():
        if git(repository, "show", ":" + name) != content:
            raise ValueError("index bytes differ from reviewed staging state")
    actual_files = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
                    if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual_files != current_files:
        raise ValueError("worktree differs from reviewed current state")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("manifest or complete result differs from reviewed expectation")
            files = {p.relative_to(fixture).as_posix(): p for directory in ("repo", "changes")
                     for p in (fixture / directory).rglob("*") if p.is_file() or p.is_symlink()}
            expected_files = reviewed_inputs(identifier)
            if set(files) != set(expected_files) or any(p.is_symlink() or p.read_bytes() != expected_files[name] for name, p in files.items()):
                raise ValueError("base or change bytes differ from reviewed single cause")
            path, base, _, current, *_ = CASES[identifier]
            kind = "taskFrontmatter" if path == TASK_PATH else "reqFrontmatter" if path == REQ_PATH else "techFrontmatter"
            validator = Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]})
            for document in (base, current):
                if document is not None:
                    # These fixed documents contain exactly three plain-string fields.
                    validator.validate(dict(line.split(": ", 1) for line in document.splitlines()[1:4]))
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-git-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_git_states(repository, identifier)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and actual != previous):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, IndexError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
