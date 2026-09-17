"""単一workspaceのContext Digest fixtureを監査する（Core操作は実行しない）。

各fixtureを審査済み期待値と照合し、commitしたCanonical JSONを、独立に書いた2系統の
参照計算（review済みliteralによるdigest_reference A、入力treeによるdigest_crosscheck B）と
照合する。群の中でのDigestの一致・不一致は、hash文字列だけでなくbyte列で比べる。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference, parser_expectations
from .digest_reference import CASES, DESCRIPTIONS, SAME_AS_GOLDEN
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
GOLDEN = "SINGLE-042"
REQ_RESULT_PATH = ".spec/requirements/REQ-001.md"
TECH_RESULT_PATH = ".spec/technical/TECH-001.md"
LEDGER = [
    {"id": "REQ-001:AC-01", "documentId": "REQ-001", "documentRole": "root", "modality": "MUST",
     "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
     "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}},
    {"id": "REQ-001:AC-02", "documentId": "REQ-001", "documentRole": "root", "modality": "SHOULD",
     "reason": "確認のため", "actor": "TargetSystem",
     "activation": {"kind": "WHEN", "text": "保存した場合"},
     "operation": {"kind": "THEN", "text": "結果を返す"}},
]
COVERAGE = {
    "must": {"total": ["REQ-001:AC-01"], "addressed": [], "tested": ["REQ-001:AC-01"],
             "unaddressed": ["REQ-001:AC-01"], "untested": []},
    "should": {"total": ["REQ-001:AC-02"], "addressed": [], "tested": ["REQ-001:AC-02"],
               "unaddressed": ["REQ-001:AC-02"], "untested": []},
    "may": {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []},
    "adjacent": [],
}


def reviewed_manifest(identifier):
    tail = CASES[identifier][0]
    return {
        **({"parserChecks": [{"path": REQ_RESULT_PATH, "resultFile": "expected/parser-ir.json"}]}
           if identifier in {"SINGLE-096-01", "SINGLE-097-01", "SINGLE-098-01", "SINGLE-101-01"} else {}),
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", *tail, "--format", "json"],
                       "env": {}},
        "expect": {"status": "passed_with_warnings" if identifier == "SINGLE-098-01" else "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(identifier, context_digest):
    _, req_body, tech_body, _ = CASES[identifier]
    detail = "full" if identifier in {"SINGLE-043-01", "SINGLE-106-01"} else "standard"
    expanded = ["TECH-001"] if identifier == "SINGLE-043-02" else []
    if identifier == "SINGLE-127-03":
        expanded = ["REQ-001", "TECH-001"]
    elif identifier == "SINGLE-127-04":
        expanded = ["TECH-001"]
    ledger = [dict(statement) for statement in LEDGER]
    if identifier == "SINGLE-097-01":
        ledger[0] = {**ledger[0], "operation": {"kind": "CONSTRAINT", "text": digest_reference.DECODED_TEXT}}
    if identifier == "SINGLE-096-01":
        ledger[0] = {**ledger[0], "operation": {"kind": "CONSTRAINT", "text": digest_reference.CODE_VALUE}}
    result = {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": context_digest,
        "revision": None,
        "resolution": {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0},
        "projection": {"detail": detail, "expanded": expanded},
        "documents": [
            {"id": "REQ-001", "kind": "requirement", "status": "approved", "role": "root",
             "path": REQ_RESULT_PATH, "projection": "full", "reachedBy": ["root"],
             "statementRefs": ["REQ-001:AC-01", "REQ-001:AC-02"],
             "frontmatter": {"id": "REQ-001", "title": "認証Contextの基準", "status": "approved"},
             "bodyText": req_body, "untrustedText": True},
            {"id": "TECH-001", "kind": "technical", "status": "approved", "role": "refinement",
             "path": TECH_RESULT_PATH, "projection": "full", "reachedBy": ["refines:TECH-001"],
             "statementRefs": [],
             "frontmatter": {"id": "TECH-001", "title": "認証の実装方針", "status": "approved",
                             "relations": {"refines": ["REQ-001"], "related": ["ADR-001"]},
                             "implements": ["src/auth.py", "src/session.py"],
                             "tests": [{"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01"],
                                        "command": "default"},
                                       {"path": "tests/test_session.py", "covers": ["REQ-001:AC-02"],
                                        "command": "default"}]},
             "bodyText": tech_body, "untrustedText": True},
        ],
        "constraintLedger": {"statements": ledger},
        "coverage": json.loads(json.dumps(COVERAGE)),
        "durationMs": 0,
        "diagnostics": [],
    }

    if identifier == "SINGLE-098-01":
        result["status"] = "passed_with_warnings"
        result["diagnostics"] = [{"code": "EAI-EXT-UNKNOWN-001", "severity": "warning",
            "resultStatus": "passed_with_warnings", "summary": "未知namespaceのextensionを保持します",
            "source": {"kind": "file", "workspaceId": "root", "path": REQ_RESULT_PATH,
                       "line": 15, "column": 19}}]
    if identifier == "SINGLE-106-02":
        result["resolution"]["documentCount"] = 3
        result["documents"].append({
            "id": "TECH-002", "kind": "technical", "status": "approved", "role": "refinement",
            "path": digest_reference.NORMATIVE_PATH, "projection": "normative",
            "reachedBy": ["refines:TECH-002"], "statementRefs": [], "untrustedText": True,
        })
    return result


def references(identifier, repository):
    """同じDigest材料を、独立に書いた2系統で計算する。"""
    literal = digest_reference.canonical_bytes(digest_reference.reviewed_digest_input(identifier))
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
    if literal != derived:
        raise ValueError("reference AとBのCanonical JSONが一致しません")
    if digest_reference.digest(literal) != digest_crosscheck.digest(derived):
        raise ValueError("reference AとBのDigestが一致しません")
    return literal


def validate(root=HERE, identifiers=None):
    errors, prepared, canonical_by_fixture = [], [], {}
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
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
            canonical = (fixture / "expected/context.canonical.json").read_bytes()
            if canonical != canonical.decode("utf-8").encode("utf-8") or canonical.endswith(b"\n"):
                raise ValueError("Canonical JSONは末尾改行のないUTF-8である必要があります")
            if canonical.startswith(b"\xef\xbb\xbf"):
                raise ValueError("Canonical JSONはBOMを持ってはいけません")
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier, digest_reference.digest(canonical)):
                raise ValueError("完全結果が審査済み期待値と異なります")
            inputs = digest_reference.reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            for path, kind in ((".spec/requirements/REQ-001.md", "reqFrontmatter"),
                               (".spec/technical/TECH-001.md", "techFrontmatter"),
                               (".spec/decisions/ADR-001.md", "adrFrontmatter")):
                frontmatter, _ = digest_crosscheck.split_document(inputs[path].decode())
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-digest-") as temporary:
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
                    parser_expectations.validate_checks(fixture, manifest, repository)
                    computed = references(identifier, repository)
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
            same = identifier in SAME_AS_GOLDEN
            if same and canonical != golden:
                errors.append(f"{identifier}: Digest材料はgoldenとbyte一致する必要があります")
            if not same and canonical == golden:
                errors.append(f"{identifier}: Digest材料はgoldenと異なる必要があります")
    elif identifiers is None:
        errors.append(f"{GOLDEN}: 群を比べるにはgolden fixtureが必要です")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
