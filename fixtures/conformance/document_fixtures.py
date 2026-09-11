"""Reviewed document fixture evidence; no Core parsing or check implementation."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .ears_fixtures import GOOD
from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
REQ_PATH = ".spec/requirements/REQ-001.md"
ADR_PATH = ".spec/decisions/ADR-001.md"
HEADER = "---\nid: REQ-001\ntitle: 文書の検査\nstatus: approved\n---\n\n# REQ-001 文書の検査\n\n"
INTENT = "## Intent\n\n文書構造を検査する。\n\n"
AC = f"## Acceptance Criteria\n\n{GOOD}\n\n"
VERIFICATION = "## Verification\n\nCore実装後に確認する。現時点では未証明。\n"
DOCUMENT = HEADER + INTENT + AC + VERIFICATION
# ID: (path, complete input, Diagnostic code, summary, source details, doc/statement counts)
CASES = {
    "SINGLE-014": (".spec/requirements/REQ-002.md", DOCUMENT.encode(),
        "SPEC-FILE-NAME-001", "file名IDとFrontmatter IDが一致しません", {"key": "id"}, (0, 0)),
    "SINGLE-016": (REQ_PATH, (HEADER + INTENT + "## Acceptance Criteria\n\n規範文は未記載。\n\n" + VERIFICATION).encode(),
        "SPEC-REQ-STATEMENT-001", "approved REQに妥当な規範文がありません", {}, (0, 0)),
    "SINGLE-017-01": (REQ_PATH, DOCUMENT.replace("# REQ-001 文書の検査", "# REQ-001 異なる見出し").encode(),
        "SPEC-STYLE-H1-001", "H1がFrontmatterと一致しません", {"line": 7, "column": 1}, (1, 1)),
    "SINGLE-017-02": (REQ_PATH, (HEADER + INTENT + AC).encode(),
        "SPEC-STYLE-SECTION-001", "REQ必須section Verificationがありません", {}, (1, 1)),
    "SINGLE-017-03": (ADR_PATH, (
        "---\nid: ADR-001\ntitle: 文書の検査\nstatus: accepted\n---\n\n# ADR-001 文書の検査\n\n"
        "## Context\n\n判断の背景。\n\n## Decision\n\n" + GOOD.replace("REQ-001", "ADR-001") +
        "\n\n## Consequences\n\n規範契約はREQへ置く。\n").encode(),
        "SPEC-STYLE-PLACEMENT-001", "ADRに規範行を配置できません", {"line": 15, "column": 3}, (1, 0)),
    "SINGLE-018-01": (REQ_PATH, (HEADER + VERIFICATION + "\n" + AC + INTENT).encode(),
        None, None, {}, (1, 1)),
    "SINGLE-018-02": (REQ_PATH, (DOCUMENT + "\n## Notes\n").encode(),
        None, None, {}, (1, 1)),
    "SINGLE-018-03": (REQ_PATH, (DOCUMENT + "\n**補足**\n\n太字の疑似節は検査対象外。\n").encode(),
        None, None, {}, (1, 1)),
    "SINGLE-019": (REQ_PATH, DOCUMENT.encode() + b"\n\xff\n",
        "SPEC-INPUT-READ-001", "SPEC fileをUTF-8として復号できません", {}, (0, 0)),
}


def reviewed_manifest(identifier):
    status = "failed" if CASES[identifier][2] else "passed"
    return {
        "fixtureId": identifier, "description": CASES[identifier][3] or "Core対象外のstyleを許容する",
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 1 if status == "failed" else 0,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    path, _, code, summary, location, counts = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "check", "status": "failed" if code else "passed", "scope": "full",
        "workspace": {"id": "root", "path": "."},
        "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
        "checkedDocumentCount": counts[0], "checkedStatementCount": counts[1], "durationMs": 0,
        "diagnostics": [] if not code else [{"code": code, "severity": "error", "resultStatus": "failed",
            "summary": summary, "source": {"kind": "file", "workspaceId": "root", "path": path, **location}}],
    }


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    fm_schema = json.loads((root / "frontmatter.schema.json").read_text())
    for identifier, (path, document, _, _, _, _) in CASES.items():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            validators["manifest"].validate(manifest)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("manifest differs from reviewed invocation")
            result = json.loads((fixture / "expected/check.json").read_text())
            validators["result"].validate(result)
            if result != reviewed_result(identifier):
                raise ValueError("result differs from reviewed complete expectation")
            if (fixture / "repo" / path).read_bytes() != document:
                raise ValueError("document bytes differ from reviewed single cause")
            # Validate only the three fixed plain-string fields, even in the invalid UTF-8 case.
            frontmatter = dict(line.decode().split(": ", 1) for line in document.splitlines()[1:4])
            kind = "adrFrontmatter" if identifier == "SINGLE-017-03" else "reqFrontmatter"
            Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": fm_schema["$defs"]}).validate(frontmatter)
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["side-effects"].validate(effects)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            # Reject coherent snapshot/input tampering too, including additional files.
            input_files = {p.relative_to(fixture / "repo").as_posix()
                           for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if input_files != {".spec/bitz.yaml", path}:
                raise ValueError("additional input introduces an unreviewed cause")
            if (fixture / "repo/.spec/bitz.yaml").read_bytes() != CONFIGS["SINGLE-001"].encode():
                raise ValueError("configuration differs from reviewed minimal input")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-document-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
