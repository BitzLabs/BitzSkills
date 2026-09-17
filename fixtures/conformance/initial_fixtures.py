"""導入・設定fixtureを監査する。Coreを起動も模倣もしない。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, safe_path, setup, snapshot

HERE = Path(__file__).resolve().parent
CASES = {
    "SINGLE-001": ("doctor", "passed", 0),
    "SINGLE-002": ("doctor", "blocked", 2),
    "SINGLE-003": ("check", "blocked", 2),
    "SINGLE-004-01": ("check", "error", 3),
    "SINGLE-004-02": ("check", "error", 3),
    "SINGLE-005-01": ("check", "passed_with_warnings", 0),
    "SINGLE-005-02": ("check", "passed_with_warnings", 0),
    "SINGLE-006-01": ("doctor", "blocked", 2),
    "SINGLE-006-02": ("doctor", "blocked", 2),
}
# 各入力の単一原因を、意図して限定した範囲で独立にreviewする。
# YAML parserでも、本番の設定validatorでもない。
CONFIGS = {
    "SINGLE-001": 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n',
    "SINGLE-003": 'schemaVersion: "2.0"\nlanguage: ja\nearsAi: "1.0"\n',
    "SINGLE-004-01": 'schemaVersion: "1.0"\nlanguage: 42\nearsAi: "1.0"\n',
    "SINGLE-004-02": 'schemaVersion: "1.0"\nlanguage: ja\n',
}
CONFIGS.update({
    "SINGLE-005-01": CONFIGS["SINGLE-001"] + "futureOption: preserve-me\n",
    "SINGLE-005-02": CONFIGS["SINGLE-001"] + "profiles: legacy-profile\n",
    "SINGLE-006-01": CONFIGS["SINGLE-001"] + 'verify:\n  commands:\n    default:\n      argv: ["./missing-command"]\n      cwd: .\n',
    "SINGLE-006-02": CONFIGS["SINGLE-001"] + 'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: missing-directory\n',
})


def check_command_preconditions(identifier, repository, executable=Path("/bin/true")):
    if identifier == "SINGLE-006-01":
        missing = repository / "missing-command"
        if missing.exists() or missing.is_symlink():
            raise ValueError("command fileのcaseには、存在しない明示の実行fileと、存在するcwdが必要です")
    elif identifier == "SINGLE-006-02":
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("cwdのcaseには、Linuxのfixture環境に実行可能な/bin/trueが必要です")
        missing = repository / "missing-directory"
        if missing.exists() or missing.is_symlink():
            raise ValueError("command cwdのcaseには、存在しないcwdが必要です")


def observe(repository, external):
    return {
        "repository": snapshot(repository),
        "git": {
            "status": git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode(),
            "index": git(repository, "ls-files", "--stage").decode(),
        },
        **{name: snapshot(path) for name, path in external.items()},
    }


def compare_state(expected, observed):
    """新しいfile、変わったGit index、外部のcacheを正規化で消さない。"""
    return [name for name in sorted(expected.keys() | observed.keys()) if expected.get(name) != observed.get(name)]


def validate(root=HERE):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier, (operation, status, exit_code) in CASES.items():
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            validators["manifest"].validate(manifest)
            expect = manifest["expect"]
            expected_argv = ["doctor", "--format", "json"] if operation == "doctor" else ["check", "--full", "--base", "HEAD", "--format", "json"]
            expected_setup = {"git": True, "operations": []}
            if operation == "check":
                expected_setup["baseCommit"] = {"message": "base", "paths": ["."]}
            elif identifier == "SINGLE-002":
                expected_setup["operations"] = [{"op": "delete", "path": ".gitkeep"}]
            if (manifest["fixtureId"] != identifier or manifest["setup"] != expected_setup
                    or manifest["invocation"] != {"runner": "bitz", "cwd": ".", "argv": expected_argv, "env": {}}
                    or expect != {"status": status, "exitCode": exit_code, "stdout": "json",
                                  "resultFile": f"expected/{operation}.json", "reportFileCount": 0}):
                raise ValueError("manifestが審査済みの単一原因の起動と異なります")
            expected_path = safe_path(fixture, expect["resultFile"])
            result = json.loads(expected_path.read_text())
            validators["result"].validate(result)
            if result["operation"] != operation or result["status"] != status:
                raise ValueError("manifestと結果の操作またはstatusが一致しません")
            diagnostics = result["diagnostics"]
            if len(diagnostics) != (0 if identifier == "SINGLE-001" else 1):
                raise ValueError("独立した原因の数が想定と異なります")
            identity = None if identifier in {"SINGLE-002", "SINGLE-004-01", "SINGLE-004-02"} else "root"
            if result["workspace"] != {"id": identity, "path": "."}:
                raise ValueError("workspaceの同一性が正しくありません")
            if operation == "check":
                warning = identifier.startswith("SINGLE-005-")
                key = {"SINGLE-003": "schemaVersion", "SINGLE-004-01": "language", "SINGLE-004-02": "earsAi",
                       "SINGLE-005-01": "futureOption", "SINGLE-005-02": "profiles"}[identifier]
                if (result["scope"] != "full" or result["checkedDocumentCount"] != 0 or result["checkedStatementCount"] != 0
                        or result["revision"] is None or result["revision"]["dirty"]):
                    raise ValueError("設定だけのfixtureは文書数0と、cleanなcommit済みrevisionが必要です")
                diagnostic = diagnostics[0]
                if (diagnostic["code"] != ("SPEC-CONFIG-UNKNOWN-001" if warning else "SPEC-CONFIG-SCHEMA-001")
                        or diagnostic["severity"] != ("warning" if warning else "error")
                        or diagnostic["resultStatus"] != status
                        or diagnostic["source"] != {"kind": "file", "workspaceId": identity, "path": ".spec/bitz.yaml", "key": key}):
                    raise ValueError("設定のDiagnosticが正しくありません")
            else:
                checks = ([{"name": name, "status": "info" if name == "impact" else
                            "blocked" if name == "command" and identifier.startswith("SINGLE-006-") else "passed"}
                           for name in ("core", "workspace", "config", "schema", "ears", "git", "command", "impact")]
                          if identifier != "SINGLE-002" else [
                              {"name": "core", "status": "passed"}, {"name": "workspace", "status": "blocked"},
                              {"name": "git", "status": "passed"}])
                if result["checks"] != checks or result["core"] != {
                    "version": "1.0.0", "apiVersion": "1.0",
                    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"],
                }:
                    raise ValueError("doctorのcheckまたはCore 1.0の期待値が正しくありません")
                if identifier.startswith("SINGLE-006-"):
                    key = "verify.commands.default." + ("argv" if identifier.endswith("01") else "cwd")
                    diagnostic = diagnostics[0]
                    if (diagnostic["code"] != "SPEC-DOCTOR-COMMAND-001" or diagnostic["severity"] != "error"
                            or diagnostic["resultStatus"] != "blocked" or diagnostic["source"] != {
                                "kind": "file", "workspaceId": "root", "path": ".spec/bitz.yaml", "key": key}):
                        raise ValueError("commandのDiagnosticが正しくありません")
                elif diagnostics:
                    diagnostic = diagnostics[0]
                    if (diagnostic["code"] != "SPEC-DOCTOR-WORKSPACE-001" or diagnostic["severity"] != "error"
                            or diagnostic["resultStatus"] != "blocked" or diagnostic["source"] != {
                                "kind": "environment", "component": "workspace", "identifier": "."}):
                        raise ValueError("workspace不在のDiagnosticが正しくありません")
                    action = diagnostic.get("suggestedAction", "")
                    if any(text not in action for text in (".spec/bitz.yaml", CONFIGS["SINGLE-001"], ".gitignore", ".spec/reports/", "bitz check --full")):
                        raise ValueError("貼り付けて使える復旧手順がありません")
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["side-effects"].validate(effects)
            if effects["before"] != effects["after"]:
                raise ValueError("read-onlyのfixtureが副作用を許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-initial-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual):
                        raise ValueError("setupが固定した実行前snapshotと異なります")
                    if previous is not None and actual != previous:
                        raise ValueError("隔離した2回のsetupが異なります")
                    previous = actual
                    config = repository / ".spec/bitz.yaml"
                    if identifier in CONFIGS and config.read_bytes() != CONFIGS[identifier].encode():
                        raise ValueError("入力が審査済みの原因と異なります")
                    if identifier == "SINGLE-002" and (repository / ".spec").exists():
                        raise ValueError("workspace不在のfixtureは.spec directoryを持ってはいけません")
                    check_command_preconditions(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
