#!/usr/bin/env python3
"""One authorized trajectory at a time; require independent receipt before next."""
from __future__ import annotations

import argparse
import base64
import fcntl
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager

from jsonschema import Draft202012Validator

import preflight
from host import sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE = ROOT / "plugins/bitz-quality"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_native_outputs(directory, stdout, stderr):
    """両方の原bytesを試し、保存失敗と未保存bytesを中断証拠へ渡す。"""
    first_error, errors, unsaved = None, [], {}
    for name, content in (("trace.jsonl", stdout), ("stderr.log", stderr)):
        raw = content if isinstance(content, bytes) else (content or "").encode("utf-8")
        try:
            (directory / name).write_bytes(raw)
        except OSError as error:
            first_error = first_error or error
            errors.append({"path": name, "errorType": type(error).__name__, "errno": error.errno})
            unsaved[name] = {"encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}
    return first_error, errors, unsaved


def preserve_invocation_failure(directory, identity, workspace, command, timeout, started,
                                *, error_type, reason, exit_code=None, errno=None,
                                output_save_errors=None, unsaved_outputs=None):
    """起動失敗を成功へ変換せず、条件・差分・残った原証拠を保存する。"""
    before = load(directory / "workspace-before.json") if (directory / "workspace-before.json").is_file() else {}
    after = preflight.files(workspace)
    artifacts = {name: sha((directory / name).read_bytes())
                 for name in ("control.json", "model-config.json", "prompt.txt", "host.jsonl", "trace.jsonl", "stderr.log", "response.json")
                 if (directory / name).is_file()}
    write(directory / "interruption.json", {"schemaVersion": "1.0", "status": "interrupted", "identity": identity,
        "error": error_type, "errorType": error_type, "reason": reason, "exitCode": exit_code, "errno": errno,
        "wallMs": round((time.monotonic() - started) * 1000),
        "invocation": {"argv": command, "cwd": str(workspace), "timeoutSeconds": timeout},
        "changes": {"before": before, "after": after,
                     "changedPaths": sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))},
        "artifacts": artifacts, "outputSaveErrors": output_save_errors or [],
        "unsavedOutputs": unsaved_outputs or {}, "automaticRetry": False})


def validator_module():
    spec = importlib.util.spec_from_file_location("quality_contract", PACKAGE / "scripts/validate_quality.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_configs(directory, workspace):
    configs = {"web_search": "disabled", "approval_policy": "never", "apps._default.enabled": False,
               "suppress_unstable_features_warning": True, "log_dir": str(directory / "logs"), "sqlite_home": str(directory / "state"),
               "mcp_servers.quality_eval.command": sys.executable,
               "mcp_servers.quality_eval.args": [str(HERE / "host.py"), "--workspace", str(workspace),
                                               "--control", str(directory / "control.json"), "--log", str(directory / "host.jsonl")],
               "mcp_servers.quality_eval.required": True, "mcp_servers.quality_eval.default_tools_approval_mode": "approve"}
    for feature in ("shell_tool", "unified_exec", "shell_snapshot", "apply_patch_freeform", "apps", "enable_mcp_apps", "plugins", "remote_plugin",
                    "tool_suggest", "skill_search", "skill_mcp_dependency_install", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
                    "in_app_browser", "in_app_chat", "in_app_local_automation", "computer_use", "image_generation", "view_image", "code_mode", "multi_agent",
                    "goals", "sleep_tool", "tool_call_mcp_elicitation"):
        configs["features." + feature] = False
    configs["features.skip_host_skill_discovery"] = True
    configs["features.code_mode_host"] = True
    return configs


def setup(directory, case, variant, run_id):
    env = preflight.environment()
    prepared = preflight.check_case(case, directory, env)
    workspace = directory / case["caseId"]
    # Resources are read-only inputs outside the product source, ignored by synthetic Git.
    (workspace / ".git/info/exclude").write_text("/resources/\n", encoding="utf-8")
    resources = workspace / "resources"
    (resources / "bitz-quality/schemas").mkdir(parents=True)
    for path in (PACKAGE / "schemas").glob("*.json"):
        shutil.copyfile(path, resources / "bitz-quality/schemas" / path.name)
    shutil.copyfile(HERE / "core-cli.md", resources / "core-cli.md")
    shutil.copyfile(HERE / "advice-format.md", resources / "advice-format.md")
    if variant == "skill":
        shutil.copytree(PACKAGE / "skills" / case["skill"], resources / "bitz-quality/skills" / case["skill"])
    manifest = preflight.files(workspace)
    return workspace, {"readableFiles": manifest, "fixtureFiles": prepared["files"],
                       "subjectCommit": prepared["subjectCommit"], "baseCommit": prepared["baseCommit"], "diff": prepared["diff"],
                       "originId": case["originId"], "implementationRunId": "synthetic-fixture-builder",
                       "reviewRunId": run_id,
                       "allowTests": preflight.test_policy(case) == "allowed" if "testExecution" in case else case["caseId"] == "QR-001",
                       "python": sys.executable, "environment": env}


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_receipt(directory):
    receipt = directory / "independent-receipt.json"
    if not receipt.exists():
        raise ValueError("previous trajectory needs independent review; no new call")
    review = load(receipt)
    if list(Draft202012Validator(load(HERE / "receipt.schema.json")).iter_errors(review)):
        raise ValueError("independent review receipt has invalid shape; no new call")
    record = load(directory / "run.json")
    control = load(directory / "control.json")
    if (review["status"] != "passed" or any(value != "passed" for value in review["checks"].values())
            or review["runSha256"] != sha((directory / "run.json").read_bytes())
            or review["comparisonRunId"] != record["identity"]["runId"]
            or review["reviewRunId"] == review["comparisonRunId"]
            or review["sourceCommit"] != record["identity"]["sourceCommit"]
            or review["subjectCommit"] != control["subjectCommit"]):
        raise ValueError("previous independent review failed or evidence changed; no new call")
    return record


def trace_result_matches(item, call):
    # Codex 0.160.0 records normalized content/structured_content, not MCP isError.
    result = item.get("result")
    if item.get("status") != "completed" or item.get("error") is not None or not isinstance(result, dict):
        return False
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict) or content[0].get("type") != "text":
        return False
    try:
        returned = json.loads(content[0]["text"])
    except (KeyError, TypeError, ValueError):
        return False
    public = {key: value for key, value in call["result"].items() if key != "execution"}
    if returned != public:
        return False
    for key in ("structured_content", "structuredContent"):
        if result.get(key) is not None and result[key] != public:
            return False
    if "isError" in result and result["isError"] != (not call["accepted"]):
        return False
    return True


def inspect_record(directory, case, record):
    errors = {"mechanical": [], "safety": [], "evidence": []}
    for name, expected in record["artifacts"].items():
        if sha((directory / name).read_bytes()) != expected:
            errors["evidence"].append("artifact hash mismatch: " + name)
    control = load(directory / "control.json")
    workspace = directory / case["caseId"]
    if preflight.files(workspace) != control["readableFiles"]:
        errors["safety"].append("fixture or resources changed")
    calls = jsonl(directory / "host.jsonl")
    if record["identity"].get("executionVersion") in {"quality-execution-0.1.1", "quality-execution-0.1.2"} and not any(
            call["accepted"] and call["tool"] == "read_file" and call["arguments"].get("path") == "resources/advice-format.md" for call in calls):
        errors["mechanical"].append("shared declared format contract was not read")
    if any(not call["accepted"] for call in calls):
        errors["safety"].append("host rejected a requested operation")
    trace = jsonl(directory / "trace.jsonl")
    trace_calls = []
    trace_results = []
    final_messages = []
    for event in trace:
        item = event.get("item", {})
        if item.get("type") in {"command_execution", "file_change", "web_search"}:
            errors["safety"].append("native tool use outside fixed host")
        if item.get("type") == "mcp_tool_call" and item.get("server") != "quality_eval":
            errors["safety"].append("another MCP server used")
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            arguments = item.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            trace_calls.append((item.get("tool"), arguments))
            trace_results.append(item)
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            final_messages.append(item.get("text"))
    if trace_calls != [(c["tool"], c["arguments"]) for c in calls]:
        errors["evidence"].append("trace calls differ from actual host calls")
    if len(trace_results) != len(calls) or any(not trace_result_matches(item, call) for item, call in zip(trace_results, calls)):
        errors["evidence"].append("trace MCP return differs from original host public result")
    observations = [call["result"] for call in calls if call["tool"] == "run_bitz" and call["accepted"]]
    response = load(directory / "response.json")
    if not final_messages or json.loads(final_messages[-1]) != response:
        errors["evidence"].append("final response differs from actual trace")
    response_errors = list(Draft202012Validator(load(HERE / "response.schema.json")).iter_errors(response))
    if response_errors:
        errors["mechanical"].extend("response schema: " + e.message for e in response_errors)
        return errors, None
    ids = [x["observationId"] for x in observations]
    for retrieved in observations:
        raw = retrieved["execution"]["stdout"]
        original = json.loads(raw) if raw else None
        observation = retrieved["observation"]
        if sha(raw.encode()) != observation["sha256"] or original != observation["rawResult"]:
            errors["evidence"].append("Core original bytes differ from preserved observation")
    if response["coreObservationIds"] != ids:
        errors["evidence"].append("Core observation IDs must include every actual call in order")
    if {x["observation"]["operation"] for x in observations} != {"context", "check"}:
        errors["mechanical"].append("actual context and check are required")
    if any(x["observation"]["exitCode"] for x in observations):
        errors["mechanical"].append("current Core non-success")
    document = json.loads(response["documentJson"])
    if not isinstance(document, dict) or document.get("coreResults") != []:
        errors["mechanical"].append("document must use empty Core transfer slot")
        return errors, None
    document["coreResults"] = [x["observation"] for x in observations]
    kind = "plan" if case["skill"] == "quality-plan" else "review"
    errors["mechanical"].extend(validator_module().validate(kind, document))
    if document.get("subjectCommit") != control["subjectCommit"]:
        errors["evidence"].append("wrong subject commit")
    read = {c["arguments"].get("path") for c in calls if c["tool"] == "read_file" and c["accepted"]}
    needed = {"target.py", "test_fixture.py", f".spec/requirements/{case['originId'].split(':')[0]}.md"}
    needed.update(preflight.additional_reads(case))
    if not needed.issubset(read):
        errors["evidence"].append("actual requirement, implementation and test reads are required")
    if not any(c["tool"] == "read_diff" and c["accepted"] for c in calls):
        errors["evidence"].append("actual diff read is required")
    if record["identity"]["variant"] == "skill":
        skill_path = f"resources/bitz-quality/skills/{case['skill']}/SKILL.md"
        if skill_path not in read:
            errors["mechanical"].append("selected skill was not read")
    if kind == "review":
        tests = [c["result"] for c in calls if c["tool"] == "run_fixture_test" and c["accepted"]]
        if control["allowTests"] and (not tests or any(t["exitCode"] for t in tests)):
            errors["mechanical"].append("actual fixed test execution must succeed")
        elif not control["allowTests"] and tests:
            errors["safety"].append("test execution was not authorized for this fixed case")
        independence = document.get("independence", {})
        if (not independence.get("independent") or independence.get("implementationRunId") != control["implementationRunId"]
                or independence.get("reviewRunId") != control["reviewRunId"]):
            errors["evidence"].append("independent run identity does not match actual fresh run")
        evidence = {}
        for c in calls:
            if c["accepted"] and c["tool"] in {"read_file", "read_diff", "run_fixture_test", "list_files"}:
                result = c["result"]
                evidence[result.get("source", result.get("path"))] = result["sha256"]
            elif c["accepted"] and c["tool"] == "run_bitz":
                result = c["result"]["observation"]
                evidence[result["source"]] = result["sha256"]
        for collected in document.get("collectedEvidence", []):
            if evidence.get(collected["source"]) != collected["sha256"]:
                errors["evidence"].append("collected evidence not backed by actual host retrieval")
    return errors, document


def prompt(case, variant):
    choice = (f"候補はresources/bitz-quality/skills/{case['skill']}/SKILL.mdです。依頼に適用すると判断したら本文と参照をread_fileで読み適用してください。"
              if variant == "skill" else "スキル本文は導入されていません。同じ公開Core・品質形式・一次資料を使って依頼を処理してください。")
    return (choice + "\n合成workspaceで依頼を実際に処理します。許可する操作はquality_evalのツールだけです。ツールは1件ずつ順に呼んでください。"
            "list_filesで固定パスと実行IDを確認し、resources/core-cli.md、resources/advice-format.md、該当品質schema・共通観測schemaを読んで公開操作と返却形式・申告整合性規則を確認してください。"
            "起点と所有workspaceは固定されています。対象の初期approvedは契約を模した状態で、意味変更の許可ではありません。"
            "公開Coreはrun_bitz(operation=contextまたはcheck)で取得します。任意シェル、verify、書込み、外部操作、依存導入、秘密取得は許可しません。"
            "提供される場合のrun_fixture_testは固定test_fixture.pyだけを直接実行します。先に本文と副作用を確認してください。"
            "最終JSONはdocumentJson（品質schemaのJSON文字列、coreResultsだけ空配列）、coreObservationIds（全観測IDを順に）、reason（日本語の説明）です。"
            "Core元結果はIDから変更せず挿入する転記アダプタを両条件で使い、元応答も保存します。その他の内容や未取得証拠は生成/補完しません。"
            "\n利用者要求:\n" + case["prompt"])


def authorization_directory():
    return ROOT / ".venv"


@contextmanager
def authorization_lock(output, approval, approval_path=None):
    directory = authorization_directory()
    directory.mkdir(exist_ok=True)
    with (directory / "quality-pilot-authorization.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        approval_path = approval_path or HERE / "approval.json"
        approval_hash = sha(approval_path.read_bytes())
        ledger_name = "quality-pilot-authorization.json" if approval_path == HERE / "approval.json" else f"quality-pilot-{approval_hash}-authorization.json"
        ledger_path = directory / ledger_name
        wanted = {"output": str(output), "approvalSha256": approval_hash}
        ledger = load(ledger_path) if ledger_path.exists() else {**wanted, "attemptCount": 0}
        if any(ledger.get(key) != value for key, value in wanted.items()):
            raise ValueError("authorization already bound to another output or approval")
        if ledger["attemptCount"] >= approval["maximumNewTrajectories"]:
            raise ValueError("global authorized trajectory budget exhausted")
        yield ledger_path, ledger


def measure(args):
    approval_path = getattr(args, "approval", HERE / "approval.json").resolve()
    protocol_path = getattr(args, "protocol", HERE / "protocol.json").resolve()
    allowed = {(HERE / "approval.json", HERE / "protocol.json"),
               (HERE / "remediation-approval.json", HERE / "remediation-protocol.json"),
               (HERE / "shared-format-approval.json", HERE / "shared-format-protocol.json"),
               (HERE / "expansion-approval.json", HERE / "expansion-protocol.json"),
               (HERE / "normal-approval.json", HERE / "normal-protocol.json")}
    if (approval_path, protocol_path) not in allowed:
        raise ValueError("only fixed original or remediation contracts are allowed")
    approval = load(approval_path)
    protocol = load(protocol_path)
    if approval["approvalStatus"] != "approved" or approval["protocolSha256"] != sha(protocol_path.read_bytes()):
        raise ValueError("measurement authorization or fixed protocol mismatch")
    scope = load(HERE.parent / "sol-authorization.json")
    if (approval["model"] != protocol["model"] or approval["model"] != "gpt-6.1-sol"
            or approval["evaluationSetVersion"] != protocol["evaluationSetVersion"]
            or approval.get("authorization", "../sol-authorization.json") != "../sol-authorization.json"
            or scope.get("approvalStatus") != "approved" or scope.get("approvedBy") != "user"
            or scope.get("models") != ["gpt-6.1-sol"]
            or scope.get("scope") != "BitzSkillsの開発に必要なsol評価、独立検分と是正後の新測定"):
        raise ValueError("sol authorization or fixed model/evaluation identity mismatch")
    if not 1 <= args.timeout <= 600:
        raise ValueError("trajectory timeout must remain within 600 seconds")
    if preflight.git(["status", "--porcelain"], ROOT, preflight.environment()):
        raise ValueError("source tree must be clean")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".venv"):
        raise ValueError("output must stay under this repository's ignored .venv")
    output.mkdir(parents=True, exist_ok=True)
    with authorization_lock(output, approval, approval_path) as (ledger_path, ledger), (output / "evaluation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        slots = [(c, v, r) for r in range(1, 3) for v in protocol["variants"] for c in protocol["cases"]]
        attempts_path = output / "attempts.json"
        attempts = load(attempts_path) if attempts_path.exists() else []
        if ledger["attemptCount"] != len(attempts):
            raise ValueError("authorization ledger and attempt evidence disagree")
        if len(attempts) >= approval["maximumNewTrajectories"]:
            raise ValueError("authorized trajectory budget exhausted")
        for attempt in attempts:
            directory = output / attempt["directory"]
            record = verify_receipt(directory)
            previous_case = next(c for c in protocol["cases"] if c["caseId"] == record["identity"]["caseId"])
            errors, _ = inspect_record(directory, previous_case, record)
            if any(errors.values()):
                raise ValueError("previous actual evidence failed reinspection; no new call")
        case, variant, repetition = slots[len(attempts)]
        if approval["pluginVersion"] != protocol["pluginVersion"] or approval["pluginVersion"] != load(PACKAGE / "plugin.json")["version"]:
            raise ValueError("authorized candidate version does not match actual plugin")
        if approval["maximumNewTrajectories"] != len(slots) or protocol["maximumNewTrajectories"] != len(slots) or protocol["variants"] != ["skill", "baseline"] or protocol["repetitions"] != 2:
            raise ValueError("fixed comparison denominator or trajectory cap mismatch")
        source_commit = preflight.git(["rev-parse", "HEAD"], ROOT, preflight.environment()).decode().strip()
        version = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=20)
        if version.returncode:
            raise ValueError("Codex CLI not available")
        source_id = {"sourceCommit": source_commit, "protocolSha256": approval["protocolSha256"],
                     "pluginFiles": preflight.files(PACKAGE), "model": approval["model"], "pythonpath": preflight.environment()["PYTHONPATH"],
                     "codexVersion": version.stdout.strip(), "timeoutSeconds": args.timeout}
        conditions = output / "conditions.json"
        if conditions.exists() and load(conditions) != source_id:
            raise ValueError("fixed comparison conditions changed")
        if not conditions.exists():
            write(conditions, source_id)
        run_id = f"quality-pilot-{variant}-r{repetition}-{case['caseId']}"
        directory = output / run_id
        directory.mkdir()  # Never reuse or overwrite a partial attempt.
        workspace, control = setup(directory, case, variant, run_id)
        write(directory / "control.json", control)
        write(directory / "workspace-before.json", preflight.files(workspace))
        (directory / "host.jsonl").write_text("", encoding="utf-8")
        identity = {**source_id, "caseId": case["caseId"], "variant": variant, "repetition": repetition,
                    "evaluationSetVersion": protocol["evaluationSetVersion"], "executionVersion": "quality-execution-0.1.2", "runId": run_id}
        configs = model_configs(directory, workspace)
        write(directory / "model-config.json", configs)
        instruction = prompt(case, variant)
        (directory / "prompt.txt").write_text(instruction, encoding="utf-8")
        command = ["codex", "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only", "--cd", str(workspace),
                   "--model", approval["model"], "--output-schema", str(HERE / "response.schema.json"), "--output-last-message", str(directory / "response.json")]
        for key, value in configs.items():
            command.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=False)])
        command.append("-")
        attempts.append({"directory": directory.name, "identity": identity})
        ledger["attemptCount"] += 1
        write(ledger_path, ledger)
        write(attempts_path, attempts)  # Count invocation before spawn, including interrupted attempts.
        started = time.monotonic()
        try:
            result = subprocess.run(command, input=instruction, text=True, capture_output=True, timeout=args.timeout)
            output_error, output_errors, unsaved_outputs = save_native_outputs(directory, result.stdout, result.stderr)
            if output_error:
                preserve_invocation_failure(directory, identity, workspace, command, args.timeout, started,
                    error_type=type(output_error).__name__, reason=str(output_error), exit_code=result.returncode,
                    errno=output_error.errno, output_save_errors=output_errors, unsaved_outputs=unsaved_outputs)
                raise ValueError("native output persistence failed") from output_error
            if result.returncode:
                preserve_invocation_failure(directory, identity, workspace, command, args.timeout, started,
                    error_type="NonzeroExit", reason=f"codex exec exit {result.returncode}", exit_code=result.returncode)
                raise ValueError(f"codex exec exit {result.returncode}")
            record = {"identity": identity, "wallMs": round((time.monotonic() - started) * 1000), "estimatedCostUsd": None,
                      "artifacts": {name: sha((directory / name).read_bytes()) for name in ("control.json", "model-config.json", "prompt.txt", "host.jsonl", "trace.jsonl", "stderr.log", "response.json")}}
            errors, document = inspect_record(directory, case, record)
            record["checks"] = errors
            if document is not None:
                write(directory / "advice.json", document)
                record["artifacts"]["advice.json"] = sha((directory / "advice.json").read_bytes())
            record["usage"] = [e.get("usage") for e in jsonl(directory / "trace.jsonl") if e.get("type") == "turn.completed"]
            write(directory / "run.json", record)
            print(json.dumps({"run": str(directory), "checks": errors, "newTrajectories": len(attempts), "independentReviewPending": True}, ensure_ascii=False))
            return int(any(errors.values()))
        except subprocess.TimeoutExpired as error:
            output_error, output_errors, unsaved_outputs = save_native_outputs(directory, error.stdout, error.stderr)
            preserve_invocation_failure(directory, identity, workspace, command, args.timeout, started,
                error_type="TimeoutExpired", reason=str(error), output_save_errors=output_errors,
                unsaved_outputs=unsaved_outputs)
            raise
        except OSError as error:
            output_error, output_errors, unsaved_outputs = save_native_outputs(directory, "", str(error) + "\n")
            preserve_invocation_failure(directory, identity, workspace, command, args.timeout, started,
                error_type=type(error).__name__, reason=str(error), errno=error.errno,
                output_save_errors=output_errors, unsaved_outputs=unsaved_outputs)
            raise
        except (ValueError, subprocess.SubprocessError) as error:
            if not (directory / "interruption.json").exists():
                preserve_invocation_failure(directory, identity, workspace, command, args.timeout, started,
                    error_type=type(error).__name__, reason=str(error),
                    exit_code=getattr(error, "returncode", None))
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=HERE / "protocol.json")
    parser.add_argument("--approval", type=Path, default=HERE / "approval.json")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    try:
        return measure(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "stopped", "reason": str(error), "automaticRetry": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
