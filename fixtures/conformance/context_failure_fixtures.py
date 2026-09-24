"""Context非成功を固定するreview済みvector（本番のresolverやDigestの処理はない）。"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH
from .git_fixtures import TASK_PATH

HERE = Path(__file__).resolve().parent
CASES = {
    "SINGLE-050": ("TECH-999", "interpret", "failed", "CTX-ROOT-MISSING-001", "起点TECH-999が存在しません"),
    "SINGLE-051": ("TASK-001", "implement", "blocked", "CTX-TASK-DEPENDENCY-001", "先行TASK-002が完了していません"),
    "SINGLE-052-01": ("TECH-001", "implement", "blocked", "CTX-STATE-SUPERSEDED-001", "起点TECH-001はTECH-002に置換されています"),
    "SINGLE-052-02": ("TECH-003", "implement", "blocked", "CTX-STATE-SUPERSEDED-001", "依存先TECH-001はTECH-002に置換されています"),
    "SINGLE-053": ("TECH-001", "implement", "failed", "CTX-STATE-SUPERSEDED-002", "TECH-001の有効な後継が複数存在します"),
    "SINGLE-127-13": ("TECH-999", "interpret", "failed", "CTX-ROOT-MISSING-001", "起点TECH-999が存在しません"),
}
TASK = "---\nid: TASK-001\ntitle: 先行作業の確認\nstatus: open\n---\n\n# TASK-001 先行作業の確認\n\n## Objective\n\n先行作業の完了を確認する。\n"


def reviewed_documents(identifier):
    # YAMLと値の組を固定する。relationの意味はreview済みで、ここでは推測しない。
    if identifier == "SINGLE-051":
        root = TASK.replace("status: open\n---", "status: open\nrelations:\n  requires: [TASK-002]\n---", 1)
        return {TASK_PATH: (root, {"id": "TASK-001", "title": "先行作業の確認", "status": "open", "relations": {"requires": ["TASK-002"]}}),
            ".spec/tasks/TASK-002.md": (TASK.replace("TASK-001", "TASK-002"), {"id": "TASK-002", "title": "先行作業の確認", "status": "open"})}
    documents = {TECH_PATH: (TECH, {"id": "TECH-001", "title": "前提技術", "status": "approved"})}
    if identifier not in {"SINGLE-050", "SINGLE-127-13"}:
        for number in ([2, 3] if identifier == "SINGLE-053" else [2]):
            spec_id = f"TECH-{number:03}"
            doc = TECH.replace("TECH-001", spec_id).replace("status: approved\n---", "status: approved\nrelations:\n  supersedes: [TECH-001]\n---", 1)
            documents[f".spec/technical/{spec_id}.md"] = (doc, {"id": spec_id, "title": "前提技術", "status": "approved", "relations": {"supersedes": ["TECH-001"]}})
    if identifier == "SINGLE-052-02":
        doc = TECH.replace("TECH-001", "TECH-003").replace("status: approved\n---", "status: approved\nrelations:\n  requires: [TECH-001]\n---", 1)
        documents[".spec/technical/TECH-003.md"] = (doc, {"id": "TECH-003", "title": "前提技術", "status": "approved", "relations": {"requires": ["TECH-001"]}})
    return documents


def reviewed_inputs(identifier):
    return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(),
            **{path: doc.encode() for path, (doc, _) in reviewed_documents(identifier).items()}}


def reviewed_manifest(identifier):
    root, purpose, status, _, description = CASES[identifier]
    return {"fixtureId": identifier, "description": description, "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["context", root, "--purpose", purpose, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 1 if status == "failed" else 2,
            "stdout": "json", "resultFile": "expected/context.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    root, purpose, status, code, summary = CASES[identifier]
    if identifier in {"SINGLE-050", "SINGLE-127-13"}:
        source = {"kind": "invocation", "argument": "TECH-999"}
    elif identifier == "SINGLE-051":
        source = {"kind": "file", "workspaceId": "root", "path": TASK_PATH, "key": "relations.requires"}
    else:
        source = {"kind": "file", "workspaceId": "root", "path": TECH_PATH}
    return {"schemaVersion": "1.0", "operation": "context", "status": status, "purpose": purpose,
        "workspace": {"id": "root", "path": "."}, "roots": [root], "contextDigest": None, "revision": None,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []}, "documents": [], "constraintLedger": {"statements": []},
        "coverage": {**{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
                       for modality in ("must", "should", "may")}, "adjacent": []},
        "durationMs": 0, "diagnostics": [{"code": code, "severity": "error", "resultStatus": status, "summary": summary, "source": source}]}


def check_unborn(repository, identifier):
    git(repository, "rev-parse", "--git-dir")
    if git(repository, "symbolic-ref", "HEAD").decode().strip() != "refs/heads/fixture":
        raise ValueError("unbornのbranchが想定と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("Context fixtureに想定外のcommitがあります")
    if git(repository, "for-each-ref") or git(repository, "ls-files", "-z"):
        raise ValueError("Context fixtureはrefもstage済みpathも持ってはいけません")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != reviewed_inputs(identifier):
        raise ValueError("Context fixtureの作業treeが審査済み入力と異なります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
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
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("入力が審査済みの単一原因と異なります")
            for path, (_, fm) in reviewed_documents(identifier).items():
                kind = "taskFrontmatter" if path.startswith(".spec/tasks/") else "techFrontmatter"
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(fm)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-failure-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_unborn(repository, identifier)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
