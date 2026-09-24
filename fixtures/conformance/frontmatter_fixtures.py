"""固定したBOM・Frontmatterの証拠（YAML loaderもCoreも実装しない）。"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
# ID: titleの行の置換え, 条件code, source key, 人向けの理由
CASES = {
    "SINGLE-081": (None, "SPEC-INPUT-BOM-001", None, "設定file先頭のBOMを除いて解析を続行します"),
    "SINGLE-082": (None, "SPEC-INPUT-BOM-001", None, "SPEC file先頭のBOMを除いて解析を続行します"),
    "SINGLE-084": ("title: 文書の検査\nchanges: [src/ignored.py]", "SPEC-FM-UNAVAILABLE-001", "changes", "REQではchangesを使用できません"),
    "SINGLE-085": ("title: 文書の検査\nfutureOption: true", "SPEC-FM-UNKNOWN-001", "futureOption", "未知のFrontmatter fieldを無視します"),
    "SINGLE-086": ("title: [文書の検査", "SPEC-FM-SCHEMA-001", "title", "Frontmatter YAMLの構文が不正です"),
    "SINGLE-087-01": ("title: !custom 文書の検査", "SPEC-FM-SCHEMA-001", "title", "Frontmatterのcustom tagは禁止です"),
    "SINGLE-087-02": ("title: &label 文書の検査", "SPEC-FM-SCHEMA-001", "title", "Frontmatterのanchorは禁止です"),
    "SINGLE-087-03": ("title: *label", "SPEC-FM-SCHEMA-001", "title", "Frontmatterのaliasは禁止です"),
    "SINGLE-087-04": ("title: 文書の検査\n<<: {}", "SPEC-FM-SCHEMA-001", "<<", "Frontmatterのmerge keyは禁止です"),
    "SINGLE-087-05": ("title: 文書の検査\ntitle: 文書の検査", "SPEC-FM-SCHEMA-001", "title", "Frontmatterの重複mapping keyは禁止です"),
    "SINGLE-088": ("title: 42", "SPEC-FM-SCHEMA-001", "title", "Frontmatter titleはstringが必要です"),
}
WARNING = {"SINGLE-081", "SINGLE-082", "SINGLE-084", "SINGLE-085"}


def reviewed_inputs(identifier):
    replacement = CASES[identifier][0]
    doc = DOCUMENT if replacement is None else DOCUMENT.replace("title: 文書の検査", replacement, 1)
    config = CONFIGS["SINGLE-001"].encode()
    content = doc.encode()
    if identifier == "SINGLE-081":
        config = b"\xef\xbb\xbf" + config
    elif identifier == "SINGLE-082":
        content = b"\xef\xbb\xbf" + content
    return {CONFIG_PATH: config, REQ_PATH: content}


def reviewed_manifest(identifier):
    return {"fixtureId": identifier, "description": CASES[identifier][3],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
            "expect": {"status": "passed_with_warnings" if identifier in WARNING else "failed",
                       "exitCode": 0 if identifier in WARNING else 1, "stdout": "json",
                       "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    _, code, key, summary = CASES[identifier]
    warning = identifier in WARNING
    status = "passed_with_warnings" if warning else "failed"
    location = {"kind": "file", "workspaceId": "root", "path": CONFIG_PATH if identifier == "SINGLE-081" else REQ_PATH}
    if key is not None:
        location["key"] = key
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
            "workspace": {"id": "root", "path": "."},
            "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
            "checkedDocumentCount": 1 if warning else 0, "checkedStatementCount": 1 if warning else 0,
            "durationMs": 0, "diagnostics": [{"code": code, "severity": "warning" if warning else "error",
                "resultStatus": status, "summary": summary, "source": location}]}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
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
                raise ValueError("manifestまたは結果が審査済みの単一条件と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("BOMとFrontmatterの処理はfileを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-frontmatter-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
