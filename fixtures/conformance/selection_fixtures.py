"""Reviewed Git selection/impact evidence; does not implement Core selection."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH

HERE = Path(__file__).resolve().parent
CASES = ("SINGLE-033", "SINGLE-039", "SINGLE-040", "SINGLE-041")
DEPENDENT_PATH = ".spec/technical/TECH-002.md"
# Fixed YAML/value pairs for the changed dependency and three control documents.
DOCUMENTS = {TECH_PATH: TECH}
FRONTMATTER = {TECH_PATH: {"id": "TECH-001", "title": "前提技術", "status": "approved"}}
for number, relation, target in ((2, "requires", "TECH-001"), (3, "related", "TECH-001"), (4, "requires", "TECH-002")):
    identifier = f"TECH-{number:03}"
    path = f".spec/technical/{identifier}.md"
    DOCUMENTS[path] = TECH.replace("TECH-001", identifier).replace(
        "status: approved\n---", f"status: approved\nrelations:\n  {relation}: [{target}]\n---", 1)
    FRONTMATTER[path] = {"id": identifier, "title": "前提技術", "status": "approved", "relations": {relation: [target]}}
CHANGED_TECH = TECH.replace("前提技術", "改訂した前提技術")


def base_files(identifier):
    files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(), TECH_PATH: TECH.encode()}
    if identifier == "SINGLE-033":
        files.update({path: content.encode() for path, content in DOCUMENTS.items()})
    elif identifier == "SINGLE-041":
        files["src/unowned.py"] = b"# before\n"
    return files


def current_files(identifier):
    files = base_files(identifier)
    if identifier == "SINGLE-033":
        files[TECH_PATH] = CHANGED_TECH.encode()
    elif identifier == "SINGLE-041":
        files["src/unowned.py"] = b"# after\n"
        files["tests/test_unowned.py"] = b'raise RuntimeError("check must not execute this file")\n'
    return files


def reviewed_inputs(identifier):
    files = {"repo/" + path: content for path, content in base_files(identifier).items()}
    if identifier == "SINGLE-033":
        files["changes/tech.md"] = CHANGED_TECH.encode()
    elif identifier == "SINGLE-041":
        files["changes/code.py"] = current_files(identifier)["src/unowned.py"]
        files["changes/test.py"] = current_files(identifier)["tests/test_unowned.py"]
    return files


def reviewed_manifest(identifier):
    plan = {"git": True, "operations": []}
    if identifier != "SINGLE-039":
        plan["baseCommit"] = {"message": "base", "paths": ["."]}
    if identifier == "SINGLE-033":
        plan["operations"] = [{"op": "update", "path": TECH_PATH, "source": "changes/tech.md"}]
    elif identifier == "SINGLE-041":
        plan["operations"] = [
            {"op": "update", "path": "src/unowned.py", "source": "changes/code.py"},
            {"op": "stage", "paths": ["src/unowned.py"]},
            {"op": "create", "path": "tests/test_unowned.py", "source": "changes/test.py"}]
    args = ["--full", "--base", "HEAD"] if identifier == "SINGLE-033" else []
    descriptions = {"SINGLE-033": "changed TECHの直接strong逆参照だけを影響候補にする",
        "SINGLE-039": "unborn repositoryの引数なしcheck", "SINGLE-040": "変更集合が空のcheck",
        "SINGLE-041": "未所有codeとtest変更を件数だけに残すcheck"}
    return {"fixtureId": identifier, "description": descriptions[identifier], "setup": plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", *args, "--format", "json"], "env": {}},
        "expect": {"status": "passed_with_warnings" if identifier == "SINGLE-033" else "passed", "exitCode": 0,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    full = identifier in {"SINGLE-033", "SINGLE-039"}
    result = {"schemaVersion": "1.0", "operation": "check",
        "status": "passed_with_warnings" if identifier == "SINGLE-033" else "passed", "scope": "full" if full else "changed",
        "workspace": {"id": "root", "path": "."},
        "revision": None if identifier == "SINGLE-039" else {
            "base": "0" * 40, "commit": "0" * 40, "dirty": identifier != "SINGLE-040"},
        "durationMs": 0, "diagnostics": []}
    if full:
        result.update(checkedDocumentCount=4 if identifier == "SINGLE-033" else 1, checkedStatementCount=0)
    else:
        count = 2 if identifier == "SINGLE-041" else 0
        result["selection"] = {"changedPathCount": count, "targetDocumentCount": 0, "excludedCodeTestPathCount": count}
    if identifier == "SINGLE-033":
        result["diagnostics"] = [{"code": "SPEC-IMPACT-OUTDATED-001", "severity": "warning", "resultStatus": "passed_with_warnings",
            "summary": "TECH-002が強く依存するTECH-001が変更されています。再確認してください",
            "source": {"kind": "file", "workspaceId": "root", "path": DEPENDENT_PATH, "key": "relations.requires"}}]
    return result


def check_git_states(repository, identifier):
    base = base_files(identifier)
    if identifier == "SINGLE-039":
        # Failed HEAD resolution alone must not certify an unborn repository.
        git(repository, "rev-parse", "--git-dir")
        if git(repository, "symbolic-ref", "HEAD").decode().strip() != "refs/heads/fixture":
            raise ValueError("unborn HEAD must reference the fixture branch")
        try:
            git(repository, "rev-parse", "--verify", "HEAD")
        except subprocess.CalledProcessError:
            pass
        else:
            raise ValueError("unborn fixture has a commit")
        if git(repository, "for-each-ref") or git(repository, "ls-files", "-z"):
            raise ValueError("unborn fixture must have no refs or staged paths")
    else:
        index = dict(base)
        if identifier == "SINGLE-041":
            index["src/unowned.py"] = current_files(identifier)["src/unowned.py"]
        for revision, args, expected in (("HEAD:", ("ls-tree", "-r", "--name-only", "-z", "HEAD"), base),
                                        (":", ("ls-files", "-z"), index)):
            if set(git(repository, *args).decode().split("\0")[:-1]) != set(expected):
                raise ValueError("HEAD/index paths differ from reviewed selection case")
            for path, content in expected.items():
                if git(repository, "show", revision + path) != content:
                    raise ValueError("HEAD/index bytes differ from reviewed selection case")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != current_files(identifier):
        raise ValueError("worktree differs from reviewed selection case")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    frontmatter = Draft202012Validator({"$ref": "#/$defs/techFrontmatter", "$defs": schema["$defs"]})
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
            expected = reviewed_inputs(identifier)
            if set(files) != set(expected) or any(p.is_symlink() or p.read_bytes() != expected[name] for name, p in files.items()):
                raise ValueError("input differs from reviewed Git selection case")
            # Fixed YAML/value pair review only; no general YAML parser.
            for path in base_files(identifier):
                if path in FRONTMATTER:
                    frontmatter.validate(FRONTMATTER[path])
            if identifier == "SINGLE-033":
                frontmatter.validate({"id": "TECH-001", "title": "改訂した前提技術", "status": "approved"})
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-selection-fixtures-") as temporary:
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
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
