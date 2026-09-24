"""複合workspaceのgolden Context Digest fixtureを監査する（Core操作は実行しない）。

`MULTI-002-01`は複合workspaceのgoldenを所有する。commitしたCanonical JSONを、独立に書いた2系統の
参照計算（review済みliteralによるmulti_reference A、入力treeによるmulti_crosscheck B）と照合し、
2回の隔離setupで同じbyte列になることを確かめる。`MULTI-002-02`は同じ入力をverifyの起点にし、
targetの`contextDigest`がgoldenと同じ値であることを固定する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
GOLDEN = "MULTI-002-01"
ROOT_TARGET = "platform::REQ-001"
COMMIT = "0" * 40
REQ_RESULT_PATH = ".spec/requirements/REQ-001.md"
TECH_RESULT_PATH = ".spec/technical/TECH-010.md"
DESCRIPTIONS = {
    "MULTI-002-01": "横断refinesと横断coverageに対する複合workspace golden Digest",
    "MULTI-002-02": "同じ横断Contextをverifyの起点にしDigestとbindingを固定する",
}
CASES = {
    "MULTI-002-01": ["context", ROOT_TARGET, "--purpose", "verify", "--format", "json"],
    "MULTI-002-02": ["verify", ROOT_TARGET, "--format", "json"],
}
LEDGER = [
    {"id": "platform::REQ-001:AC-01", "documentId": ROOT_TARGET, "documentRole": "root",
     "modality": "MUST", "reason": None, "actor": "TargetSystem",
     "activation": {"kind": "ALWAYS"},
     "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}},
    {"id": "platform::REQ-001:AC-02", "documentId": ROOT_TARGET, "documentRole": "root",
     "modality": "SHOULD", "reason": "確認のため", "actor": "TargetSystem",
     "activation": {"kind": "WHEN", "text": "保存した場合"},
     "operation": {"kind": "THEN", "text": "結果を返す"}},
]
COVERAGE = {
    "must": {"total": ["platform::REQ-001:AC-01"], "addressed": [],
             "tested": ["platform::REQ-001:AC-01"],
             "unaddressed": ["platform::REQ-001:AC-01"], "untested": []},
    "should": {"total": ["platform::REQ-001:AC-02"], "addressed": [],
               "tested": ["platform::REQ-001:AC-02"],
               "unaddressed": ["platform::REQ-001:AC-02"], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": [],
}
# workspace ID -> (member path, 文書title, refineする規範文, 実装path, test path, command名)
MEMBERS = {
    "api": ("services/api", "API側のsession実装方針", "platform::REQ-001:AC-02",
            "src/session.py", "tests/test_session.py", "backend"),
    "web": ("apps/web", "Web側の認証実装方針", "platform::REQ-001:AC-01",
            "src/auth/login.py", "tests/auth/test_login.py", "frontend"),
}


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": list(CASES[identifier]), "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/context.json" if identifier == GOLDEN else "expected/verify.json",
                   "reportFileCount": 0},
    }


def member_document(workspace_id):
    path, title, target, implements, test_path, command = MEMBERS[workspace_id]
    body = (multi_reference.API_TECH_BODY if workspace_id == "api" else multi_reference.WEB_TECH_BODY)
    return {
        "id": f"{workspace_id}::TECH-010",
        "workspaceId": workspace_id,
        "kind": "technical",
        "status": "approved",
        "role": "refinement",
        "path": TECH_RESULT_PATH,
        "projection": "full",
        "reachedBy": [f"refines:{workspace_id}::TECH-010"],
        "statementRefs": [],
        "frontmatter": {
            "id": f"{workspace_id}::TECH-010",
            "title": title,
            "status": "approved",
            "relations": {"refines": [target]},
            "implements": [implements],
            "tests": [{"path": test_path, "covers": [target], "command": command}],
        },
        "bodyText": body,
        "untrustedText": True,
    }


def reviewed_context_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "verify",
        "workspace": {"id": "platform", "path": "."},
        "roots": [ROOT_TARGET],
        "contextDigest": context_digest,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {
            "complete": True, "documentCount": 3, "unresolvedStrongRelations": 0,
            "workspaces": [{"id": "platform", "path": "."},
                           {"id": "api", "path": "services/api"},
                           {"id": "web", "path": "apps/web"}],
            "crossWorkspaceEdges": [
                {"relation": "refines", "source": "api::TECH-010", "target": "platform::REQ-001:AC-02"},
                {"relation": "refines", "source": "web::TECH-010", "target": "platform::REQ-001:AC-01"},
            ],
        },
        "projection": {"detail": "standard", "expanded": []},
        "documents": [
            {"id": ROOT_TARGET, "workspaceId": "platform", "kind": "requirement", "status": "approved",
             "role": "root", "path": REQ_RESULT_PATH, "projection": "full", "reachedBy": ["root"],
             "statementRefs": ["platform::REQ-001:AC-01", "platform::REQ-001:AC-02"],
             "frontmatter": {"id": ROOT_TARGET, "title": "認証Contextの基準", "status": "approved"},
             "bodyText": multi_reference.REQ_BODY, "untrustedText": True},
            member_document("api"),
            member_document("web"),
        ],
        "constraintLedger": {"statements": [dict(statement) for statement in LEDGER]},
        "coverage": json.loads(json.dumps(COVERAGE)),
        "durationMs": 0,
        "diagnostics": [],
    }


def binding(workspace_id):
    _, _, target, _, test_path, command = MEMBERS[workspace_id]
    return {
        "bindingId": f"{workspace_id}::{command}",
        "workspaceId": workspace_id,
        "name": command,
        "status": "passed",
        "termination": "exit",
        "cwd": ".",
        "argv": ["/bin/true", test_path],
        "tests": [test_path],
        "covers": [target],
        "exitCode": 0,
        "timeoutSeconds": 300,
        "stdoutExcerpt": "",
        "stderrExcerpt": "",
        "stdoutTruncated": False,
        "stderrTruncated": False,
        "durationMs": 0,
    }


def reviewed_verify_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "platform", "path": "."},
        "targetResults": [{
            "target": ROOT_TARGET,
            "status": "passed",
            "contextDigest": context_digest,
            "statements": ["platform::REQ-001:AC-01", "platform::REQ-001:AC-02"],
            "bindingRefs": ["api::backend", "web::frontend"],
            "diagnostics": [],
        }],
        "revision": {"commit": COMMIT, "dirty": False},
        "commands": [binding("api"), binding("web")],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier, context_digest):
    if identifier == GOLDEN:
        return reviewed_context_result(context_digest)
    return reviewed_verify_result(context_digest)


def validate(root=HERE, identifiers=None):
    errors, prepared, canonical_by_fixture = [], [], {}
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            name = "context" if identifier == GOLDEN else "verify"
            result = json.loads((fixture / f"expected/{name}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            canonical = (fixture / "expected/context.canonical.json").read_bytes()
            if canonical != canonical.decode("utf-8").encode("utf-8") or canonical.endswith(b"\n"):
                raise ValueError("Canonical JSONは末尾改行のないUTF-8である必要があります")
            if canonical.startswith(b"\xef\xbb\xbf"):
                raise ValueError("Canonical JSONはBOMを持ってはいけません")
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier, multi_reference.digest(canonical)):
                raise ValueError("完全結果が審査済み期待値と異なります")
            inputs = multi_reference.reviewed_inputs()
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            for path, kind in ((multi_reference.ROOT_REQ_PATH, "reqFrontmatter"),
                               (multi_reference.WEB_TECH_PATH, "techFrontmatter"),
                               (multi_reference.API_TECH_PATH, "techFrontmatter")):
                frontmatter, _ = multi_crosscheck.split_document(inputs[path].decode())
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-digest-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    computed = multi_crosscheck.references(repository, ROOT_TARGET)
                    if computed != canonical:
                        raise ValueError("commitしたCanonical JSONが参照計算と異なります")
            canonical_by_fixture[identifier] = canonical
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")

    if GOLDEN in canonical_by_fixture:
        golden = canonical_by_fixture[GOLDEN]
        for identifier, canonical in canonical_by_fixture.items():
            # 同じ入力から同じ材料を得るので、verify側のDigestもgoldenとbyte一致する。
            if canonical != golden:
                errors.append(f"{identifier}: Digest材料はgoldenとbyte一致する必要があります")
    elif identifiers is None:
        errors.append(f"{GOLDEN}: 群を比べるにはgolden fixtureが必要です")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
