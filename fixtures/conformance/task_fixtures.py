"""Reviewed TASK scope fixtures; no production selection or boundary logic."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
TASK_PATH = ".spec/tasks/TASK-001.md"
TASK = "---\nid: TASK-001\ntitle: 変更境界の検査\nstatus: open\nchanges: [src/]\n---\n\n# TASK-001 変更境界の検査\n\n## Objective\n\n変更境界を確認する。\n"
CURRENT_TASK = TASK.replace("変更境界を確認する。", "変更境界を確認する。説明を補足する。")
BASE = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(), TASK_PATH: TASK.encode(),
        "src/inside.py": b"# unchanged allowed path\n", "src2/outside.py": b"# before\n"}
CURRENT = {**BASE, TASK_PATH: CURRENT_TASK.encode(), "src2/outside.py": b"# after\n"}
# The same two unstaged paths exercise all three invocation scopes.
CASES = {"SINGLE-034": ("selected", ["TASK-001"], "failed"),
         "SINGLE-035-01": ("changed", [], "passed"),
         "SINGLE-035-02": ("full", ["--full"], "passed")}


def reviewed_manifest(identifier):
    _, targets, status = CASES[identifier]
    return {"fixtureId": identifier, "description": "TASK changesのsegment境界と明示指定時だけの検査",
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": [
            {"op": "update", "path": TASK_PATH, "source": "changes/task.md"},
            {"op": "update", "path": "src2/outside.py", "source": "changes/outside.py"}]},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", *targets, "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 1 if status == "failed" else 0,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    scope, _, status = CASES[identifier]
    result = {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": scope,
        "workspace": {"id": "root", "path": "."},
        "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": True},
        "durationMs": 0, "diagnostics": []}
    if scope == "changed":
        result["selection"] = {"changedPathCount": 2, "targetDocumentCount": 1, "excludedCodeTestPathCount": 1}
    else:
        result.update(checkedDocumentCount=1, checkedStatementCount=0)
    if identifier == "SINGLE-034":
        result["diagnostics"] = [{"code": "SPEC-TASK-BOUNDARY-001", "severity": "error", "resultStatus": "failed",
            "summary": "src2/outside.pyはTASK-001の許可変更path外です",
            "source": {"kind": "file", "workspaceId": "root", "path": "src2/outside.py"}}]
    return result


def reviewed_inputs():
    return {**{"repo/" + path: content for path, content in BASE.items()},
            "changes/task.md": CURRENT[TASK_PATH], "changes/outside.py": CURRENT["src2/outside.py"]}


def check_git_states(repository):
    """Compare exact Git blobs, not an inferred TASK boundary decision."""
    for revision, path_args in (("HEAD:", ("ls-tree", "-r", "--name-only", "-z", "HEAD")),
                                (":", ("ls-files", "-z"))):
        if set(git(repository, *path_args).decode().split("\0")[:-1]) != set(BASE):
            raise ValueError("HEAD/index paths differ from reviewed base")
        for path, content in BASE.items():
            if git(repository, "show", revision + path) != content:
                raise ValueError("HEAD/index bytes differ from reviewed base")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != CURRENT:
        raise ValueError("worktree differs from reviewed two-path change")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    frontmatter = Draft202012Validator({"$ref": "#/$defs/taskFrontmatter", "$defs": schema["$defs"]})
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
                raise ValueError("manifest or complete result differs from reviewed scope expectation")
            files = {p.relative_to(fixture).as_posix(): p for directory in ("repo", "changes")
                     for p in (fixture / directory).rglob("*") if p.is_file() or p.is_symlink()}
            expected = reviewed_inputs()
            if set(files) != set(expected) or any(p.is_symlink() or p.read_bytes() != expected[name] for name, p in files.items()):
                raise ValueError("input differs from reviewed TASK/segment boundary case")
            # Fixed YAML/value pair review only; no general YAML parser.
            frontmatter.validate({"id": "TASK-001", "title": "変更境界の検査", "status": "open", "changes": ["src/"]})
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-task-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_git_states(repository)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and actual != previous):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
