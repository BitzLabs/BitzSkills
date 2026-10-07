#!/usr/bin/env python3
"""固定したSOL作業枠を独立CLI文脈で実行し、原bytesと中断を保持する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import audit_single_replacement as collection  # noqa: E402

PRIVATE = collection.PRIVATE_BASE / "collection-05"
CONTRACT = "evals/skills/routing/native-authoring-v0.3.json"
ROLES = ("creator", "reviewer")
import native_actor_v02 as previous_execution
import native_tool_preflight as tool_preflight

OLD_SOURCE_FILES = ["evals/skills/routing/native-authoring-v0.1.json","evals/skills/routing/native_actor.py","evals/skills/routing/native-actor-response.schema.json","evals/skills/routing/native-preparation-prompt.md","evals/skills/routing/native-creator-prompt.md","evals/skills/routing/native-reviewer-prompt.md","tests/skills/test_native_actor.py","evals/skills/routing/native-authoring-v0.2.json","evals/skills/routing/native_actor_v02.py","tests/skills/test_native_actor_v02.py","evals/skills/routing/native-preparation-v02-prompt.md","evals/skills/routing/native-creator-v02-prompt.md","evals/skills/routing/native-reviewer-v02-prompt.md"]  # 固定した旧13を保持する
SOURCE_FILES = set(OLD_SOURCE_FILES) | {
    CONTRACT, "evals/skills/routing/native_actor_v03.py", "tests/skills/test_native_actor_v03.py",
    "evals/skills/routing/native_tool_preflight.py",
    *(f"evals/skills/routing/native-{role}-v03-prompt.md" for role in ROLES),
}
OLD_SOURCE = "4736737b25b8e0b190e3863b508e56589e952f1e"
CONTROL_DIRS = (".agents", ".codex", ".aws")

def require_control_dirs(repo: Path = ROOT) -> None:
    for name in CONTROL_DIRS:
        path = repo / name
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise ValueError("empty protected control directories required")

CODEX_HOME_VIEW = Path("/home/hide/.codex")
HOME_SCRATCH_NAMES = {"config.toml", "installation_id", "tmp"}
PREPARATION_ROOT_NAMES = {"retention.json", "native-authoring-01", "native-authoring-02", "native-authoring-03", *CONTROL_DIRS}


def check_preparation_outputs(private: Path = PRIVATE) -> None:
    if {p.name for p in private.iterdir()} != PREPARATION_ROOT_NAMES:
        raise ValueError("preparation produced collection output")


def shadow_home_bindings(directory: Path, home: Path = CODEX_HOME_VIEW) -> list[str]:
    scratch = directory / "codex-home"
    if not scratch.is_dir() or any(p.is_symlink() for p in [scratch, *scratch.parents]):
        raise ValueError("shadow home destination")
    if stat.S_IMODE(scratch.stat().st_mode) != 0o700:
        raise ValueError("shadow home permissions")
    command = ["--bind", str(scratch), str(home)]
    # 既存内容は読まない。CLI初期化状態だけfresh scratchへ隔離し、既存資源はROへ戻す。
    for child in sorted(home.iterdir()):
        if child.name not in HOME_SCRATCH_NAMES:
            command += ["--ro-bind", str(child), str(child)]
    return command


def require_budget_approval(source: str, ledger: Path) -> None:
    path = ledger / "budget-approval.json"
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("approval symlink")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("approval permissions")
    approval = collection.load(path.read_bytes())
    expected = {"status": "remaining_roles_authorized", "executionSource": source,
                "maximumNewInvocations": 2, "additionalPreparationModelCalls": 0,
                "creatorSol": 1, "reviewerSol": 1, "previousAttemptsPreserved": True,
                "transmissionScope": "2026-10-06-private-sol-transmission"}
    if approval != expected:
        raise ValueError("additional preparation approval")


def verify_previous_failure(contract: dict, *, repo: Path = ROOT, private: Path = PRIVATE) -> None:
    path = repo / ".venv/routing-native-authoring-02/preparation-result.json"
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("old execution symlink")
    raw = path.read_bytes()
    expected = contract["previousFailure"]
    if collection.digest(raw) != expected["executionReceiptSha256"]:
        raise ValueError("old execution receipt drift")
    value = collection.load(raw)
    if (value["sourceCommit"] != OLD_SOURCE or value["role"] != "preparation"
            or value["status"] != "native_completed" or value["actualExitCode"] != 0
            or value["artifactSha256"] != expected["captureSha256"]):
        raise ValueError("old execution not retained")
    for name, digest in expected["captureSha256"].items():
        if name not in {"trace.jsonl", "stderr.log", "response.json"}:
            raise ValueError("old capture inventory")
        raw = collection.legacy.private_file(private / "native-authoring-02/preparation" / name)
        if collection.digest(raw) != digest:
            raise ValueError("old capture drift")

    response = collection.load(collection.legacy.private_file(private / "native-authoring-02/preparation/response.json"))
    if response["status"] != "stopped" or (private / "native-authoring-02/preparation/native-preparation-receipt.json").exists():
        raise ValueError("unreviewed previous preparation must remain stopped")


def exclusive(path: Path, raw: bytes) -> None:
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("symlink destination")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def reserve(role: str, source: str, ledger_root: Path) -> Path:
    if role not in ROLES:
        raise ValueError("role")
    if any(p.is_symlink() for p in [ledger_root, *ledger_root.parents]):
        raise ValueError("symlink ledger")
    ledger_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = ledger_root / (role + ".json")
    # sourceや出力先を変えても同じ役割の上限を再利用しない。
    exclusive(path, encoded({"role": role, "sourceCommit": source, "attemptReserved": 1,
                             "maximumAttempts": 1, "automaticRetry": False}))
    return path


def configurations(directory: Path) -> dict:
    values = {"approval_policy": "never", "web_search": "disabled", "apps._default.enabled": False,
              "suppress_unstable_features_warning": True,
              "log_dir": str(directory / "logs"), "sqlite_home": str(directory / "state"),
              "features.skip_host_skill_discovery": True, "features.code_mode_host": True}
    for feature in ("shell_snapshot", "apply_patch_freeform", "apps", "enable_mcp_apps", "plugins", "remote_plugin",
                    "tool_suggest", "skill_search", "skill_mcp_dependency_install", "browser_use", "browser_use_external",
                    "browser_use_full_cdp_access", "in_app_browser", "in_app_chat", "in_app_local_automation", "computer_use",
                    "image_generation", "view_image", "code_mode", "multi_agent", "goals", "sleep_tool",
                    "tool_call_mcp_elicitation"):
        values["features." + feature] = False
    values["features.shell_tool"] = values["features.unified_exec"] = True
    return values


def namespace(directory: Path, ledger_root: Path, cli_argv: list[str], *, repo: Path = ROOT,
              private: Path = PRIVATE) -> list[str]:
    require_control_dirs(repo)
    if not directory.is_relative_to(private / "native-authoring-03"):
        raise ValueError("private execution destination")
    if any(p.is_symlink() for p in [directory, *directory.parents]):
        raise ValueError("symlink execution destination")
    command = ["bwrap", "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
               "--die-with-parent", "--bind", str(repo / ".venv"), str(repo / ".venv")]
    # テストは新しい一時treeを作れるが、既存のsnapshot・ログ・台帳は変更できない。
    for child in sorted((repo / ".venv").iterdir()):
        command += ["--ro-bind", str(child), str(child)]
    command += ["--bind", str(private), str(private)]
    for child in sorted(private.iterdir()):
        command += ["--ro-bind", str(child), str(child)]
    # 今回の新規CLI領域だけ書込み可。旧ファイルはbind mountでunlinkも防ぐ。
    command += ["--bind", str(directory), str(directory), "--ro-bind", str(ledger_root), str(ledger_root),
                ]
    for name in ["prompt.txt", "model-config.json", "invocation.json", "trace.jsonl", "stderr.log"]:
        command += ["--ro-bind", str(directory / name), str(directory / name)]
    if (directory / "preflight").is_dir():
        command += ["--ro-bind", str(directory / "preflight"), str(directory / "preflight")]
    command += shadow_home_bindings(directory)
    command += ["--chdir", str(repo), "--", *cli_argv]
    return command


def stop_process(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def invoke(command: list[str], prompt: bytes, directory: Path, timeout: int,
           *, environment: dict | None = None) -> dict:
    started = time.monotonic()
    process, error_type = None, None
    # file-backed captureにより手動中断にもpartial原bytesを保持する。
    handles, save_errors = [], []
    try:
        for name in ["trace.jsonl", "stderr.log"]:
            fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            handles.append(os.fdopen(fd, "wb"))
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=handles[0], stderr=handles[1],
                                   env=environment, start_new_session=True)
        process.communicate(input=prompt, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        error_type = type(error).__name__
        if process is not None and process.poll() is None:
            stop_process(process)
    finally:
        for handle in handles:
            try:
                handle.flush()
                os.fsync(handle.fileno())
            except OSError as error:
                save_errors.append({"errorType": type(error).__name__, "errno": error.errno})
            finally:
                try:
                    handle.close()
                except OSError as error:
                    save_errors.append({"errorType": type(error).__name__, "errno": error.errno})
    exit_code = process.returncode if process is not None else None
    status = "native_completed" if error_type is None and exit_code == 0 and not save_errors else "native_stopped"
    hashes = {name: collection.digest((directory / name).read_bytes())
              for name in ["trace.jsonl", "stderr.log", "response.json"] if (directory / name).is_file()}
    result = {"status": status, "actualExitCode": exit_code, "errorType": error_type,
              "wallMs": round((time.monotonic() - started) * 1000), "artifactSha256": hashes,
              "nativeOutputAvailable": all((directory / name).is_file() for name in ["trace.jsonl", "stderr.log"]),
              "outputSaveErrors": save_errors, "automaticRetry": False}
    try:
        exclusive(directory / "native-result.json", encoded(result))
    except OSError as error:
        result.update(status="native_stopped", resultSaveError={"errorType": type(error).__name__, "errno": error.errno})
    return result


def verify(source: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("full source required")
    raw = collection.source_guard.git(ROOT, "show", source + ":" + CONTRACT)
    contract = collection.load(raw)
    if set(contract["sourceFiles"]) != SOURCE_FILES or len(contract["sourceFiles"]) != len(SOURCE_FILES):
        raise ValueError("execution source inventory")
    if contract["privateRoot"] != str(PRIVATE) or contract["model"] != "gpt-6.1-sol":
        raise ValueError("execution authorization")
    if contract["budget"] != {"creator": 1, "reviewer": 1, "primaryModelTrajectories": 0,
                               "automaticRetries": 0, "delegations": 0}:
        raise ValueError("execution budget")
    collection.source_guard.verify(ROOT, source, contract["sourceFiles"])
    if contract["previousExecutionSource"] != OLD_SOURCE:
        raise ValueError("previous execution source")
    collection.source_guard.verify(ROOT, OLD_SOURCE, OLD_SOURCE_FILES)
    previous_execution.verify(OLD_SOURCE)
    require_control_dirs()
    require_control_dirs(PRIVATE)
    verify_previous_failure(contract)
    base_raw = collection.source_guard.git(ROOT, "show", contract["collectionSource"] + ":" + collection.CONTRACT_NAME)
    base = collection.load(base_raw)
    if set(base["sourceFiles"]) != collection.SOURCE_NAMES or len(base["sourceFiles"]) != 15:
        raise ValueError("collection source inventory")
    collection.source_guard.verify(ROOT, contract["collectionSource"], base["sourceFiles"])
    collection.public_inputs(base)
    collection.legacy.audit_candidate(base)
    paths = {collection.INITIAL: collection.PRIVATE_BASE / "cases.json",
             collection.OLD: collection.PRIVATE_BASE / "collection-03/cases.json",
             collection.PREVIOUS: collection.PRIVATE_BASE / "collection-04/cases.json"}
    if set(base["excludedSets"]) != set(paths):
        raise ValueError("excluded input inventory")
    for version, path in paths.items():
        declared = base["excludedSets"][version]
        if declared["path"] != str(path) or collection.digest(collection.legacy.private_file(path)) != declared["sha256"]:
            raise ValueError("excluded input drift")
    for name, key in [("independent-review.md", "independentReportSha256"),
                      ("independent-receipt.json", "independentReceiptSha256")]:
        if collection.digest(collection.legacy.private_file(collection.PRIVATE_BASE / "collection-04" / name)) != base["retention"][key]:
            raise ValueError("retention review drift")
    if collection.digest(collection.legacy.private_file(PRIVATE / "retention.json")) != base["retention"]["sha256"]:
        raise ValueError("retention drift")
    return contract


def terminal_result(directory: Path) -> dict:
    events = [collection.load(line) for line in (directory / "trace.jsonl").read_bytes().splitlines() if line.strip()]
    if (sum(e.get("type") == "thread.started" for e in events) != 1
            or sum(e.get("type") == "turn.completed" for e in events) != 1
            or any(e.get("type") in {"turn.failed", "error"} for e in events)):
        raise ValueError("native terminal not successful")
    messages = [e["item"]["text"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "agent_message"]
    if not messages or collection.load(messages[-1].encode()) != collection.load((directory / "response.json").read_bytes()):
        raise ValueError("native final response mismatch")
    completed = next(e for e in events if e.get("type") == "turn.completed")
    usage = completed.get("usage", {})
    usage = {k: v for k, v in usage.items() if k in {"input_tokens", "cached_input_tokens", "output_tokens"}
             and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    return {"nativeTurnCompleted": True, "nativeFinalResponseMatched": True, "usage": usage or "unknown"}


def prepared_creator(source: str, contract: dict) -> dict:
    phase = PRIVATE / "native-authoring-03/creator"
    receipt = collection.load(collection.legacy.private_file(phase / "native-preparation-receipt.json"))
    if (receipt["status"] != "passed" or receipt["severityCounts"] != {"P1": 0, "P2": 0}
            or receipt["sourceCommit"] != source or receipt["collectionSource"] != contract["collectionSource"]):
        raise ValueError("embedded independent preparation not passed")
    return receipt


def require_previous(role: str, source: str, contract: dict) -> None:
    if role != "reviewer":
        return
    execution = collection.load((ROOT / ".venv/routing-native-authoring-03/creator-result.json").read_bytes())
    if (execution["sourceCommit"] != source or execution["role"] != "creator"
            or execution["status"] != "native_completed" or execution["actualExitCode"] != 0
            or not execution["postSourceMatched"] or not execution["phaseConditionsMatched"]
            or not execution["nativeTurnCompleted"]):
        raise ValueError("native creation not completed")
    phase = PRIVATE / "native-authoring-03/creator"
    for name, digest in execution["artifactSha256"].items():
        if name not in {"trace.jsonl", "stderr.log", "response.json"} or collection.digest(collection.legacy.private_file(phase / name)) != digest:
            raise ValueError("native creation output drift")
    if set(execution["artifactSha256"]) != {"trace.jsonl", "stderr.log", "response.json"}:
        raise ValueError("native creation capture inventory")
    prepared_creator(source, contract)
    receipt = collection.load(collection.legacy.private_file(PRIVATE / "creation-receipt.json"))
    if (receipt["status"] != "created-mechanical-pass-awaiting-independent-review"
            or receipt["sourceCommit"] != contract["collectionSource"] or receipt["executionSource"] != source
            or receipt["creatorSolConsumed"] != 1 or receipt["primaryModelTrajectories"] != 0
            or receipt["automaticRetries"] != 0):
        raise ValueError("creation not mechanically passed")
    required = {"cases.json", "evidence.json", "creation-notes.md", "source-guard-start.json",
                "source-guard-presave.json", "creation-audit.json"}
    if not required <= set(receipt["filesSha256"]) <= required | {"creation-invocation-error.json"}:
        raise ValueError("creation artifact inventory")
    for name, digest in receipt["filesSha256"].items():
        if collection.digest(collection.legacy.private_file(PRIVATE / name)) != digest:
            raise ValueError("creation artifact drift")


def run(source: str, role: str) -> dict:
    contract = verify(source)
    require_budget_approval(source, ROOT / ".venv/routing-native-authoring-03")
    require_previous(role, source, contract)
    if role == "creator" and {p.name for p in PRIVATE.iterdir()} - PREPARATION_ROOT_NAMES:
        raise ValueError("preexisting collection output")
    version_command = ["bwrap", "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                       "--die-with-parent", "--", contract["codexPath"], "--version"]
    version = subprocess.run(version_command, capture_output=True, timeout=20)
    if version.returncode or version.stdout.decode().strip() != contract["codexVersion"]:
        raise ValueError("codex version")
    ledger_root = ROOT / ".venv/routing-native-authoring-03"
    reserve(role, source, ledger_root)
    # 原bytesとCLI状態はすべて承認済みprivate root内の新しいowner-only領域に置く。
    os.umask(0o077)
    parent = PRIVATE / "native-authoring-03"
    if parent.is_symlink():
        raise ValueError("symlink execution parent")
    parent.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) != 0o700:
        raise ValueError("execution parent permissions")
    directory = parent / role
    directory.mkdir(mode=0o700)
    (directory / "codex-home").mkdir(mode=0o700)
    preflight = tool_preflight.execute(sys.modules[__name__], directory, ledger_root, contract)
    if preflight["status"] != "local_preflight_passed":
        result = {"status": "local_preflight_stopped", "sourceCommit": source, "role": role,
                  "modelStarted": False, "automaticRetry": False, "preflight": preflight}
        exclusive(ledger_root / (role + "-result.json"), encoded(result))
        return result
    configs = configurations(directory)
    prompt = (ROOT / f"evals/skills/routing/native-{role}-v03-prompt.md").read_text()
    prompt = (f"実行source={source}\n集合source={contract['collectionSource']}\n"
              f"private実行領域={directory}\n\n" + prompt).encode()
    exclusive(directory / "prompt.txt", prompt)
    exclusive(directory / "model-config.json", encoded(configs))
    cli = [contract["codexPath"], "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules",
           "--sandbox", "workspace-write", "--cd", str(ROOT), "--add-dir", str(PRIVATE),
           "--model", contract["model"], "--output-schema", str(HERE / "native-actor-response.schema.json"),
           "--output-last-message", str(directory / "response.json")]
    for key, value in configs.items():
        cli += ["-c", key + "=" + json.dumps(value)]
    cli.append("-")
    command = namespace(directory, ledger_root, cli)
    exclusive(directory / "invocation.json", encoded({"argv": command, "timeoutSeconds": contract["timeoutSeconds"],
              "role": role, "sourceCommit": source, "collectionSource": contract["collectionSource"],
              "model": contract["model"], "codexVersion": contract["codexVersion"], "attemptCount": 1}))
    environment = os.environ.copy()
    temp = directory / "tmp"
    temp.mkdir(mode=0o700)
    environment["TMPDIR"] = str(temp)
    result = invoke(command, prompt, directory, contract["timeoutSeconds"], environment=environment)
    if result["status"] == "native_completed":
        try:
            result.update(terminal_result(directory))
        except Exception as error:
            result.update(status="native_stopped", nativeTerminalErrorType=type(error).__name__, nativeTurnCompleted=False)
    try:
        verify(source)
        source_match = True
    except Exception:
        source_match = False
    phase_match, phase_error = True, None
    try:
        if role == "creator":
            prepared_creator(source, contract)
            base = collection.load(collection.source_guard.git(ROOT, "show", contract["collectionSource"] + ":" + collection.CONTRACT_NAME))
            collection.audit(base, PRIVATE / "cases.json")
    except Exception as error:
        phase_match, phase_error = False, type(error).__name__
    # stderrは復号/表示しない。native完了は成果物の意味合格と区別する。
    result.update(sourceCommit=source, role=role, postSourceMatched=source_match,
                  phaseConditionsMatched=phase_match, phaseErrorType=phase_error,
                  primaryModelTrajectories=0, certifiesSkillGate=False)
    exclusive(ledger_root / (role + "-result.json"), encoded(result))
    exclusive(directory / "execution-receipt.json", encoded(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    args = parser.parse_args()
    try:
        result = run(args.source, args.role)
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__, "automaticRetry": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return int(result["status"] != "native_completed" or not result.get("postSourceMatched") or not result.get("phaseConditionsMatched"))


if __name__ == "__main__":
    raise SystemExit(main())
