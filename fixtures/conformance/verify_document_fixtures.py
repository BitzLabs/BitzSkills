"""文書単位のbindingを固定するreview済みvector（Core操作は実行しない）。

`SINGLE-066`は、規範文を持たず文書単位のtestを宣言するTECHをtargetにする。そのため
targetは`statements: []`を返しつつ、`bindingRefs`の要素を持つ。
"""
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
IDENTIFIER = "SINGLE-066"
TECH_PATH = ".spec/technical/TECH-001.md"
TEST_PATH = "tests/test_auth.py"
TITLE = "文書単位testの実装方針"
# 文書・Frontmatter仕様 §: only a TECH without normative statements may put a
# coversに文書IDを置く。これがこのfixtureの固定する文書単位のbindingである。
TECH_FRONTMATTER = (
    f"id: TECH-001\ntitle: {TITLE}\nstatus: approved\n"
    "implements: [src/auth.py]\n"
    "tests:\n"
    f"  - path: {TEST_PATH}\n"
    "    covers: [TECH-001]\n"
    "    command: default\n"
)
TECH_BODY = (f"# TECH-001 {TITLE}\n\n## Context\n\n規範文を持たず文書単位のtestだけを宣言する。\n")
TECH_DOCUMENT = "---\n" + TECH_FRONTMATTER + "---\n\n" + TECH_BODY


def reviewed_inputs():
    return {
        digest_reference.CONFIG_PATH: digest_reference.CONFIG.encode(),
        TECH_PATH: TECH_DOCUMENT.encode(),
        "src/auth.py": digest_reference.CODE_FILES["src/auth.py"].encode(),
        TEST_PATH: digest_reference.CODE_FILES[TEST_PATH].encode(),
    }


def reviewed_digest_input():
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "verify", "requestWorkspaceId": "root",
        "roots": ["TECH-001"], "workspaces": [{"id": "root", "path": "."}],
        "documents": [{
            "id": "TECH-001", "workspaceId": "root", "kind": "technical", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {
                "id": "TECH-001", "title": TITLE, "status": "approved",
                "relations": dict(digest_reference.EMPTY_RELATIONS),
                "implements": ["src/auth.py"],
                "tests": [{"path": TEST_PATH, "covers": ["TECH-001"], "command": "default"}],
                "verify": None, "changes": []},
            "bodyText": TECH_BODY, "statements": [], "strongRelations": []}],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}],
            "commands": [{"workspaceId": "root", "name": "default",
                          "argv": ["/bin/true", "{tests}"], "cwd": "."}]},
    }


def context_digest():
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input()))


def reviewed_manifest():
    return {
        "fixtureId": IDENTIFIER,
        "description": "規範文なしTECHが文書単位testのbindingを保持する",
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "TECH-001", "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result():
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "TECH-001", "status": "passed", "contextDigest": context_digest(),
            # 規範文は所有しないが、文書単位のbindingは成立する。
            "statements": [], "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", TEST_PATH], "tests": [TEST_PATH], "covers": ["TECH-001"],
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_document_binding(result):
    target = result["targetResults"][0]
    if target["statements"]:
        raise ValueError("規範文のないTECHは規範文を返してはいけません")
    if not target["bindingRefs"]:
        raise ValueError("文書単位のtestでもbindingを作る必要があります")
    if result["commands"][0]["covers"] != ["TECH-001"]:
        raise ValueError("文書単位のbindingは文書自身を対象にする必要があります")


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
        check_document_binding(result)
        inputs = reviewed_inputs()
        frontmatter, body = digest_crosscheck.split_document(inputs[TECH_PATH].decode())
        Draft202012Validator({"$ref": "#/$defs/techFrontmatter",
                              "$defs": schema["$defs"]}).validate(frontmatter)
        if digest_crosscheck.read_statements(digest_crosscheck.normalize_body(body)):
            raise ValueError("審査済みの原因には規範文のないTECHが必要です")
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("入力が審査済みcorpusと異なります")
        if effects["before"] != effects["after"]:
            raise ValueError("read-only期待値が書込みを許しています")
        previous = None
        with tempfile.TemporaryDirectory(prefix="bitz-verify-document-") as temporary:
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
                    digest_crosscheck.build(repository, root="TECH-001"))
                if derived != digest_reference.canonical_bytes(reviewed_digest_input()):
                    raise ValueError("reference AとBのCanonical JSONが一致しません")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
