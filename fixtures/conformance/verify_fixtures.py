"""processの挙動を必要としないreview済みのverify vector（Core操作は実行しない）。

commandを実行する成功・失敗の形と、commandのspawn前に停止する4つの条件を扱う。
process単位のvector（spawn error、signal、timeout、出力の切り詰め）は別の群が持つ。

すべてのfixtureは入力をstageする。workspaceの設定がindexで未追跡だとverifyは起動を
遮断する（VERIFY-CONFIG-UNTRACKED）ため、何もstageしないunbornのrepositoryではcommandに到達できない。
"""
import copy
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
GOLDEN = digest_reference.digest(
    digest_reference.canonical_bytes(digest_reference.reviewed_digest_input("SINGLE-042")))
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
FAILING_CONFIG = digest_reference.CONFIG.replace('"/bin/true", "{tests}"', '"/bin/false", "{tests}"')
TASK_CANCELLED = (
    "---\nid: TASK-001\ntitle: 取り消した作業\nstatus: cancelled\n"
    "relations:\n  addresses: [REQ-001:AC-01]\n---\n"
    "\n# TASK-001 取り消した作業\n\n## Objective\n\n取り消した作業は検証対象にしない。\n"
)
ONE_TEST = ("tests:\n  - path: tests/test_session.py\n"
            "    covers: [REQ-001:AC-02]\n    command: default\n")
BOTH_TESTS = ("tests:\n  - path: tests/test_auth.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
              "  - path: tests/test_session.py\n    covers: [REQ-001:AC-02]\n    command: default\n")
DESCRIPTIONS = {
    "SINGLE-055": "test成功でtargetResultsとcommandsを1件ずつ返す",
    "SINGLE-056": "testの非0終了をtermination exitとexitCode非0で返す",
    "SINGLE-060": "対象MUSTが未testedでtestを開始しない",
    "SINGLE-061": "command名を解決できずbindingを構成しない",
    "SINGLE-062": "引数なしで対象0件を成功にしない",
    "SINGLE-067": "cancelled TASK起点をblockedにする",
}
CASES = {
    "SINGLE-055": (["REQ-001"], "selected", "passed", 0),
    "SINGLE-056": (["REQ-001"], "selected", "failed", 1),
    "SINGLE-060": (["REQ-001"], "selected", "blocked", 2),
    "SINGLE-061": (["REQ-001"], "selected", "blocked", 2),
    "SINGLE-062": ([], "all", "blocked", 2),
    "SINGLE-067": (["TASK-001"], "selected", "blocked", 2),
}


def technical_document(tests_block):
    head = digest_reference.TECH_HEAD_FIELDS.replace(BOTH_TESTS, tests_block, 1)
    if tests_block != BOTH_TESTS and head == digest_reference.TECH_HEAD_FIELDS:
        raise ValueError("review済みのtests blockが共有corpusにもうありません")
    return "---\n" + head + "x-owners: [team-auth]\n---\n\n" + digest_reference.TECH_BODY


def reviewed_inputs(identifier):
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    if identifier == "SINGLE-056":
        inputs[digest_reference.CONFIG_PATH] = FAILING_CONFIG.encode()
    elif identifier == "SINGLE-060":
        inputs[digest_reference.TECH_PATH] = technical_document(ONE_TEST).encode()
    elif identifier == "SINGLE-061":
        inputs[digest_reference.TECH_PATH] = technical_document(
            BOTH_TESTS.replace("command: default", "command: missing")).encode()
    elif identifier == "SINGLE-062":
        return {
            digest_reference.CONFIG_PATH: digest_reference.CONFIG.encode(),
            digest_reference.REQ_PATH: (
                digest_reference.REQ_HEAD.replace("status: approved", "status: draft")
                + "\n" + digest_reference.REQ_BODY).encode(),
        }
    elif identifier == "SINGLE-067":
        inputs[".spec/tasks/TASK-001.md"] = TASK_CANCELLED.encode()
    return inputs


def reviewed_digest_input(identifier):
    """Digestが必要なのは、Contextが解決する2件のfixtureだけである。"""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    if identifier == "SINGLE-056":
        payload["settings"]["commands"][0]["argv"] = ["/bin/false", "{tests}"]
    elif identifier == "SINGLE-060":
        technical = next(d for d in payload["documents"] if d["id"] == "TECH-001")
        technical["frontmatter"]["tests"] = [
            {"path": "tests/test_session.py", "covers": ["REQ-001:AC-02"], "command": "default"}]
    else:
        raise KeyError(identifier)
    return payload


def context_digest(identifier):
    if identifier == "SINGLE-055":
        return GOLDEN
    if identifier in {"SINGLE-056", "SINGLE-060"}:
        return digest_reference.digest(
            digest_reference.canonical_bytes(reviewed_digest_input(identifier)))
    return None


def reviewed_manifest(identifier):
    targets, _, status, exit_code = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", *targets, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def executed_command(identifier):
    failing = identifier == "SINGLE-056"
    return {
        "bindingId": "root::default", "workspaceId": "root", "name": "default",
        "status": "failed" if failing else "passed", "termination": "exit", "cwd": ".",
        "argv": ["/bin/false" if failing else "/bin/true", *TEST_PATHS],
        "tests": list(TEST_PATHS), "covers": list(STATEMENTS),
        "exitCode": 1 if failing else 0, "timeoutSeconds": 300,
        "stdoutExcerpt": "", "stderrExcerpt": "",
        "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0,
    }


def target_diagnostic(identifier):
    if identifier == "SINGLE-060":
        return [{"code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked",
                 "summary": "対象MUST REQ-001:AC-01にtest対応がありません",
                 "source": {"kind": "file", "workspaceId": "root",
                            "path": digest_reference.REQ_PATH}}]
    if identifier == "SINGLE-061":
        return [{"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
                 "summary": "command名missingが設定に定義されていません",
                 "source": {"kind": "file", "workspaceId": "root",
                            "path": digest_reference.TECH_PATH, "key": "tests[0].command"}}]
    if identifier == "SINGLE-067":
        return [{"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                 "summary": "起点TASK-001はcancelledでありverifyに適用できません",
                 "source": {"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-001.md"}}]
    return []


def reviewed_result(identifier):
    targets, scope, status, _ = CASES[identifier]
    if identifier == "SINGLE-062":
        target_results, commands, diagnostics = [], [], [{
            "code": "SPEC-VERIFY-BLOCKED-002", "severity": "error", "resultStatus": "blocked",
            "summary": "verify対象が0件です",
            "source": {"kind": "invocation"}}]
    else:
        executed = identifier in {"SINGLE-055", "SINGLE-056"}
        target_results = [{
            "target": targets[0],
            "status": status,
            "contextDigest": context_digest(identifier),
            # cancelledのTASK起点は、addressesする規範文に到達しない。
            "statements": [] if identifier == "SINGLE-067" else list(STATEMENTS),
            "bindingRefs": ["root::default"] if executed else [],
            "diagnostics": target_diagnostic(identifier),
        }]
        commands = [executed_command(identifier)] if executed else []
        diagnostics = []
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": scope,
        "workspace": {"id": "root", "path": "."},
        "targetResults": target_results,
        "revision": None,
        "commands": commands,
        "durationMs": 0,
        "diagnostics": diagnostics,
    }


def check_evidence(identifier, result):
    """実行に至らなかったtargetはbindingを持たず、Digestは
    Contextが解決した場合にだけ存在する。"""
    for target in result["targetResults"]:
        if target["bindingRefs"] and not result["commands"]:
            raise ValueError("bindingが参照されているのにcommandが実行されていません")
        if not target["bindingRefs"] and result["commands"]:
            raise ValueError("bindingを要求しないtargetのためにcommandが実行されています")
        if target["contextDigest"] != context_digest(identifier):
            raise ValueError("targetのDigestが審査済みのContextと異なります")
    referenced = {ref for target in result["targetResults"] for ref in target["bindingRefs"]}
    if referenced != {command["bindingId"] for command in result["commands"]}:
        raise ValueError("bindingRefsとcommandsが同じ実行を表していません")
    for command in result["commands"]:
        if command["bindingId"] != f"{command['workspaceId']}::{command['name']}":
            raise ValueError("bindingIdは<workspace-id>::<command-name>である必要があります")


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
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            check_evidence(identifier, result)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    if not digest_crosscheck.read_yaml(
                            (repository / ".spec/bitz.yaml").read_text(encoding="utf-8")):
                        raise ValueError("workspaceの設定を読めません")
                    tracked = subprocess.run(
                        ["git", "ls-files", "--", ".spec/bitz.yaml"], cwd=repository,
                        capture_output=True, text=True, timeout=10).stdout.strip()
                    if tracked != ".spec/bitz.yaml":
                        raise ValueError("verifyにはindexで追跡されている設定が必要です")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    expected_digest = context_digest(identifier)
                    if expected_digest is not None:
                        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                        if digest_crosscheck.digest(derived) != expected_digest:
                            raise ValueError("reference AとBのtargetのDigestが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
