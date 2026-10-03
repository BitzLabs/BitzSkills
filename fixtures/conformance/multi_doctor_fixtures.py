"""複合ワークスペース全体の`doctor`の診断とメンバーの継続を固定するレビュー済みの入力と期待値。"""
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
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
CASES = {
    "MULTI-026-01": "rootと全memberを順序どおりdoctor診断する",
    "MULTI-026-02": "memberのcommand失敗後も後続memberを診断して全体へ集約する",
}


def api_config(identifier):
    value = multi_reference.plain_config("api")
    if identifier == "MULTI-026-02":
        value += (
            "verify:\n"
            "  commands:\n"
            "    backend:\n"
            "      argv: [./missing-command]\n"
            "      cwd: .\n"
        )
    return value


def reviewed_inputs(identifier):
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
            [("web", "apps/web"), ("api", "services/api")]).encode(),
        multi_reference.API_CONFIG_PATH: api_config(identifier).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
    }


def reviewed_manifest(identifier):
    text = identifier == "MULTI-026-02"
    expect = {
        "status": "blocked" if text else "passed",
        "exitCode": 2 if text else 0,
        "stdout": "text" if text else "json",
        "resultFile": "expected/doctor.json",
        "reportFileCount": 0,
    }
    if text:
        expect["textFile"] = "expected/doctor.txt"
    return {
        "fixtureId": identifier,
        "description": CASES[identifier],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": []},
        "invocation": {"runner": "bitz", "cwd": "apps/web",
                       "argv": ["doctor", "--all-workspaces"] + ([] if text else ["--format", "json"]),
                       "env": {}},
        "expect": expect,
    }


def checks(command="passed"):
    return [
        {"name": "workspace", "status": "passed"},
        {"name": "config", "status": "passed"},
        {"name": "schema", "status": "passed"},
        {"name": "ears", "status": "passed"},
        {"name": "command", "status": command},
        {"name": "impact", "status": "info"},
    ]


def command_diagnostic():
    return {
        "code": "SPEC-DOCTOR-COMMAND-001",
        "severity": "error",
        "resultStatus": "blocked",
        "summary": "command実行fileを解決できません",
        "source": {"kind": "file", "workspaceId": "api", "path": ".spec/bitz.yaml",
                   "key": "verify.commands.backend.argv"},
    }


def workspace(workspace_id, path, status="passed", command="passed", diagnostics=()):
    return {
        "id": workspace_id,
        "path": path,
        "status": status,
        "checks": checks(command),
        "durationMs": 0,
        "diagnostics": [dict(entry) for entry in diagnostics],
    }


def reviewed_result(identifier):
    failed = identifier == "MULTI-026-02"
    return {
        "schemaVersion": "1.0",
        "operation": "doctor",
        "status": "blocked" if failed else "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "core": dict(CORE),
        "checks": [
            {"name": "core", "status": "passed"},
            {"name": "git", "status": "passed"},
            {"name": "catalog", "status": "passed"},
        ],
        "workspaces": [
            workspace("platform", "."),
            workspace("api", "services/api", "blocked", "blocked", [command_diagnostic()])
            if failed else workspace("api", "services/api"),
            workspace("web", "apps/web"),
        ],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_text(identifier):
    if identifier != "MULTI-026-02":
        raise ValueError("テキストの期待値を持たないfixtureです")
    return (
        "doctor blocked targets=21 diagnostics=1 (0ms)\n"
        "api:.spec/bitz.yaml::: error: SPEC-DOCTOR-COMMAND-001: "
        "command実行fileを解決できません\n"
    )


def check_precondition(identifier, repository):
    root_id, members = multi_crosscheck.catalog(repository)
    catalog_order = [("web", "apps/web"), ("api", "services/api")]
    result_order = [("api", "services/api"), ("web", "apps/web")]
    if root_id != "platform" or members != catalog_order or sorted(members) != result_order:
        raise ValueError("全体操作の`doctor`のワークスペースの集合または順序が不正です")
    if identifier == "MULTI-026-02":
        config = multi_crosscheck.read_yaml(
            (repository / multi_reference.API_CONFIG_PATH).read_text(encoding="utf-8"))
        argv = config["verify"]["commands"]["backend"]["argv"]
        if argv != ["./missing-command"] or (repository / "services/api/missing-command").exists():
            raise ValueError("メンバーのコマンド不在条件が成立していません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/doctor.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if identifier == "MULTI-026-02" and (
                    fixture / "expected/doctor.txt").read_text() != reviewed_text(identifier):
                raise ValueError("テキストの期待値がレビュー済みの期待値と異なります")
            entries = {path.relative_to(fixture / "repo").as_posix(): path.read_bytes()
                       for path in (fixture / "repo").rglob("*") if path.is_file()}
            if entries != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_precondition(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
