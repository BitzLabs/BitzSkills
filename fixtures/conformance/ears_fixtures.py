"""Fixed EARS fixture evidence audit, not a Core Scanner/Lexer/Parser."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
CASES = json.loads(r'''
[
  [
    "SINGLE-007",
    "approved",
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [WHEN] 保存した場合 [MUST] [REASON] 確認のため [THEN] 結果を返す。",
    "EAI-CORE-SYNTAX-001",
    "failed",
    61
  ],
  [
    "SINGLE-008",
    "draft",
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [WHEN] 保存した場合 [MUST] [REASON] 確認のため [THEN] 結果を返す。",
    "EAI-CORE-SYNTAX-001",
    "passed_with_warnings",
    61
  ],
  [
    "SINGLE-009-01",
    "draft",
    "- [REQ-01:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
    "EAI-CORE-ID-001",
    "failed",
    3
  ],
  [
    "SINGLE-009-02",
    "draft",
    "- [UNKNOWN-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
    "EAI-CORE-ID-001",
    "failed",
    3
  ],
  [
    "SINGLE-009-03",
    "draft",
    "- [REQ-001:AC-02:R-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
    "EAI-CORE-ID-001",
    "failed",
    3
  ],
  [
    "SINGLE-010-01",
    "approved",
    "- [x] 確認済み。",
    null,
    "passed",
    null
  ],
  [
    "SINGLE-010-02",
    "approved",
    "- `[REQ-001:AC-99]` は説明用の例です。",
    null,
    "passed",
    null
  ]
]
''')
CASES.extend(json.loads(r'''
[
  [
    "SINGLE-011",
    "draft",
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
    "EAI-CORE-ID-002",
    "failed",
    3
  ],
  [
    "SINGLE-012-01",
    "approved",
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT 秘密情報を出力しない。",
    "EAI-CORE-SYNTAX-004",
    "failed",
    56
  ],
  [
    "SINGLE-012-02",
    "approved",
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] ログに `secret を出力しない。",
    "EAI-CORE-SYNTAX-005",
    "failed",
    73
  ],
  [
    "SINGLE-012-03",
    "approved",
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない",
    "EAI-CORE-SYNTAX-006",
    "failed",
    79
  ],
  [
    "SINGLE-013",
    "approved",
    "- [REQ-001:AC-02] [quality:LEVEL=\"basic\"] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
    "EAI-EXT-UNKNOWN-001",
    "passed_with_warnings",
    19
  ]
]
'''))
SUMMARIES = {
    "EAI-CORE-ID-001": "規範文IDの形式が不正です",
    "EAI-CORE-ID-002": "規範文IDが重複しています",
    "EAI-CORE-SYNTAX-001": "tagの順序が不正です",
    "EAI-CORE-SYNTAX-004": "tagが閉じられていません",
    "EAI-CORE-SYNTAX-005": "code spanが閉じられていません",
    "EAI-CORE-SYNTAX-006": "規範文末の句点がありません",
    "EAI-EXT-UNKNOWN-001": "未知namespaceのextensionを保持します",
}
GOOD = "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。"
SPEC_PATH = ".spec/requirements/REQ-001.md"


def reviewed_document(status, line):
    return (
        f"---\nid: REQ-001\ntitle: 規範文の検査\nstatus: {status}\n---\n\n"
        "# REQ-001 規範文の検査\n\n## Intent\n\n規範行と説明を区別する。\n\n"
        f"## Acceptance Criteria\n\n{GOOD}\n{line}\n\n## Verification\n\n"
        "Core実装後に適合fixtureで確認する。現時点では未証明。\n"
    )


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    fm_schema = json.loads((root / "frontmatter.schema.json").read_text())
    fm_validator = Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": fm_schema["$defs"]})
    for identifier, doc_status, line, code, status, column in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            validators["manifest"].validate(manifest)
            if (manifest["fixtureId"] != identifier or manifest["setup"] != {
                    "git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
                    or manifest["invocation"] != {"runner": "bitz", "cwd": ".",
                        "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}}
                    or manifest["expect"] != {"status": status, "exitCode": 1 if status == "failed" else 0,
                        "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}):
                raise ValueError("manifest differs from reviewed invocation")
            result = json.loads((fixture / "expected/check.json").read_text())
            validators["result"].validate(result)
            diagnostics = [] if code is None else [{
                "code": code, "severity": "error" if status == "failed" else "warning",
                "resultStatus": status,
                "summary": SUMMARIES[code],
                "source": {"kind": "file", "workspaceId": "root", "path": SPEC_PATH, "line": 16, "column": column},
            }]
            expected = {
                "schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
                "workspace": {"id": "root", "path": "."},
                "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
                "checkedDocumentCount": 0 if status == "failed" else 1,
                "checkedStatementCount": 0 if status == "failed" else 2 if identifier == "SINGLE-013" else 1, "durationMs": 0,
                "diagnostics": diagnostics,
            }
            if result != expected:
                raise ValueError("result differs from reviewed complete expectation")
            document = (fixture / "repo" / SPEC_PATH).read_bytes()
            if document != reviewed_document(doc_status, line).encode():
                raise ValueError("REQ input differs from reviewed single cause")
            # Only the fixed three plain-string fields above; not a general YAML reader.
            fm_lines = document.decode().splitlines()[1:4]
            fm_validator.validate(dict(value.split(": ", 1) for value in fm_lines))
            if code:
                source_line = document.decode().splitlines()[15]
                tokens = {"EAI-CORE-SYNTAX-001": "[REASON]", "EAI-CORE-SYNTAX-004": "[CONSTRAINT",
                          "EAI-CORE-SYNTAX-005": "`", "EAI-EXT-UNKNOWN-001": "[quality:"}
                position = len(source_line) + 1 if code == "EAI-CORE-SYNTAX-006" else source_line.index(tokens.get(code, "[")) + 1
                if position != column:
                    raise ValueError("Diagnostic column does not point to reviewed token")
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["side-effects"].validate(effects)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-ears-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    if (repository / ".spec/bitz.yaml").read_bytes() != CONFIGS["SINGLE-001"].encode():
                        raise ValueError("nonminimal configuration adds another cause")
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and actual != previous):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
