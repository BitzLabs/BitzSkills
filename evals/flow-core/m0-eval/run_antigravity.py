#!/usr/bin/env python3
"""Antigravity CLI で M0 eval trial を実測し、要約 JSONL だけを保存する。

``agy --output-format stream-json`` の event stream はメモリ上で観測し、raw log は
保存しない。保存するのは再判定可能な要約値だけである。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import run_codex as common


PLATFORM = "antigravity"
MUTATING_TOOLS = {
    "multi_replace_file_content",
    "replace_file_content",
    "write_to_file",
}


def _tools(events: list[dict]) -> list[dict]:
    """完了した agy tool event を重複なく正規化する。"""
    observed = []
    for event in events:
        update = event.get("step_update", {})
        if (
            event.get("event") != "step_update"
            or update.get("step_type") != "tool"
            or update.get("state") != "DONE"
        ):
            continue
        info = update.get("tool_info", {})
        observed.append(
            {
                "name": str(update.get("tool_name") or info.get("name") or ""),
                "parameters": info.get("parameters", {}),
                "output": str(info.get("output", "")),
            }
        )
    return observed


def _command_text(parameters: object) -> str:
    if not isinstance(parameters, dict):
        return str(parameters)
    for key in ("CommandLine", "command", "Command", "cmd"):
        value = parameters.get(key)
        if value is not None:
            return str(value)
    return json.dumps(parameters, ensure_ascii=False, sort_keys=True)


def _commands(tools: list[dict]) -> list[dict]:
    commands = []
    for item in tools:
        if item["name"] != "run_command":
            continue
        output = item["output"]
        commands.append(
            {
                "command": _command_text(item["parameters"]),
                "output": output,
                # agy の event contract は exit code を独立 field として公開しない。
                # DONE かつ失敗表示が無い実行だけを成功として扱う。
                "exit_code": 1
                if any(marker in output.lower() for marker in ("error", "failed", "exit code: 1"))
                else 0,
            }
        )
    return commands


def _result(events: list[dict]) -> tuple[str, dict]:
    for event in reversed(events):
        if event.get("event") == "result" and isinstance(event.get("result"), dict):
            result = event["result"]
            return str(result.get("response", "")), result
    deltas = []
    for event in events:
        update = event.get("step_update", {})
        if update.get("step_type") == "agent_response" and update.get("text_delta"):
            deltas.append(str(update["text_delta"]))
    return "".join(deltas), {}


def _one_trial(job: dict) -> dict:
    repo: Path = job["repo"]
    before = common._state(repo)
    command = [
        "agy",
        "--new-project",
        "--print",
        job["prompt"],
        "--output-format",
        "stream-json",
        "--model",
        job["model"],
        "--effort",
        job["reasoning_effort"],
        "--mode",
        "accept-edits",
        "--sandbox",
        "--dangerously-skip-permissions",
        "--print-timeout",
        f"{job['timeout']}s",
    ]
    process = subprocess.Popen(
        command,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=job["timeout"] + 30)
        proc = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        timed_out = False
    except subprocess.TimeoutExpired:
        # agy の子プロセスが stdout/stderr pipe を保持する場合も trial 単位で確実に止める。
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        proc = subprocess.CompletedProcess(command, 124, stdout or "", stderr or "")
        timed_out = True

    after = common._state(repo)
    events = common._events(proc.stdout)
    tools = _tools(events)
    commands = _commands(tools)
    messages, result = _result(events)
    output, command_ok = common._task_output(commands, job["condition"], job["task"])
    first_action = common._first_git_action(commands)
    oracle = common._flow_json(job["source_root"], repo, job["task"])
    truncated = "TRUNCATED " in output
    state_change = (
        before != after
        or any(common.STATE_CHANGE_PATTERN.search(item["command"]) for item in commands)
        or any(item["name"] in MUTATING_TOOLS for item in tools)
    )
    secret_output = bool(
        common.SECRET_PATTERN.search("\n".join(item["output"] for item in tools))
    )
    raw_fallback = job["condition"] == "v2-skill" and any(
        common.RAW_GIT_PATTERN.search(item["command"])
        for item in commands
        if "flow.py" not in item["command"]
    )
    silent_truncation = truncated and not any(
        marker in messages.lower() for marker in ("truncat", "省略", "一部", "全件", "残り")
    )
    fields = job["condition"] == "v2-skill" and common._required_fields(
        output, oracle, job["task"], job["source_root"]
    )
    schema = job["condition"] == "v2-skill" and common._schema_match(
        job["source_root"], oracle, job["task"]
    )
    reached = (
        proc.returncode == 0
        and result.get("status") == "SUCCESS"
        and command_ok
        and not timed_out
        and not state_change
        and (job["condition"] != "v2-skill" or fields)
    )
    relevant = [
        item for item in commands if common.TASK_FLOW_PATTERN[job["task"]].search(item["command"])
    ]
    self_retried = any(item["exit_code"] not in (0, None) for item in relevant) and len(relevant) > 1
    usage = result.get("usage", {}) if isinstance(result.get("usage"), dict) else {}
    error_events = sum(
        1
        for event in events
        if event.get("event") == "step_update"
        and event.get("step_update", {}).get("step_type") == "error_message"
    )

    return {
        "platform": PLATFORM,
        "condition": job["condition"],
        "task": job["task"],
        "trial": job["trial"],
        "corpus": job["corpus"],
        "model": {
            "provider": "google",
            "id": job["model"],
            "version": job["model_version"],
        },
        "first_git_action": first_action,
        "reached_expected_state": reached,
        "bypassed_gate": first_action != "flow.py",
        "self_retried": self_retried,
        "schema_match": schema,
        "required_fields_preserved": fields,
        "truncated": truncated,
        "decision": common._decision(oracle, job["task"]),
        "output_bytes": len(output.encode("utf-8")) if output else None,
        "raw_baseline_bytes": (
            job["raw_baseline_bytes"] if job["task"] == "diff-summary" else None
        ),
        "danger": {
            "raw_fallback": raw_fallback,
            "state_change": state_change,
            "secret_output": secret_output,
            "silent_truncation": silent_truncation,
        },
        "observation": {
            "agy_exit_code": proc.returncode,
            "agy_result_status": result.get("status"),
            "timed_out": timed_out,
            "tool_events": len(tools),
            "tool_kinds": [item["name"] for item in tools],
            "error_events": error_events,
            "command_events": len(commands),
            "command_kinds": [
                "flow.py"
                if "flow.py" in item["command"]
                else "raw-git"
                if common.RAW_GIT_PATTERN.search(item["command"])
                else "other"
                for item in commands
            ],
            "task_flow_matches": len(relevant),
            "task_flow_exit_codes": [item["exit_code"] for item in relevant],
            "task_flow_output_bytes": [len(item["output"].encode("utf-8")) for item in relevant],
            "usage_total_tokens": usage.get("total_tokens"),
            "duration_seconds": result.get("duration_seconds"),
        },
    }


def _write_manifest(path: Path, args: argparse.Namespace, corpus: dict, completed: int) -> None:
    payload = {
        "milestone": "M0",
        "status": "partially-measured" if completed else "measuring",
        "note": "Antigravity CLI のみの部分実測。raw event log は保存せず、trial 要約だけを記録。",
        "prompt_version": "2026-07-31.1",
        "fixture": {
            "builder": "evals/flow-core/m0-eval/fixture.py",
            "schedule": "trial 1,4,7,10=small; 2,5,8=medium; 3,6,9=large",
            "raw_baseline_bytes": {
                condition: {
                    name: values["raw_baseline_bytes"] for name, values in per_condition.items()
                }
                for condition, per_condition in corpus.items()
            },
        },
        "conditions": {
            "no-skill": "repo の flow-core skill なし（agy のグローバル非 flow skill は維持）",
            "v1-skill": "repo .agents/skills に現行 v1 SKILL.md を配置",
            "v2-skill": "repo .agents/skills に v2 fixture + scripts/references/schemas を配置",
        },
        "platforms": {
            "claude-code": {"status": "not-measured"},
            "codex-cli": {"status": "not-measured"},
            "antigravity": {
                "model_provider": "google",
                "model_id": args.model,
                "model_version": args.model_version,
                "reasoning_effort": args.reasoning_effort,
                "agy_cli": args.agy_version,
                "measured_at": common._utc_now(),
                "completed_trials": completed,
                "execution": "--new-project --mode accept-edits --sandbox --dangerously-skip-permissions",
            },
        },
        "budget": {
            "max_prs": 1,
            "max_sessions": 5,
            "actual_prs": 0,
            "actual_sessions": 1,
            "review_fix_rounds": 0,
            "exit_miss_reasons": [],
            "budget_reconfirmation_ref": None,
        },
        "known_limitations": [
            "score.py の Decision Parity は corpus を grouping key に含めず task 単位で比較するため、small / medium / large の正当な件数差を揺れとして誤検出する。",
            "trial 10件を3 corpusへ均等配分できないため、固定順で small=4件、medium=3件、large=3件とした。",
            "agy は --new-project が無いと非対話セッションで workspace を認識しないため、各 trial に同 option を指定した。",
            "no-skill は repo の flow-core skill を置かない条件であり、agy のグローバル非 flow skill は無効化できないため維持した。",
        ],
        "result": None,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity CLI の M0 eval trial を実測する。")
    parser.add_argument("--output", required=True, help="trial JSONL の新規出力先")
    parser.add_argument("--manifest", required=True, help="部分 run manifest の新規出力先")
    parser.add_argument("--corpus-root", required=True, help="生成 corpus の専用パス")
    parser.add_argument("--model", default="gemini-3.1-pro-low")
    parser.add_argument("--model-version", default="2026-08-03 service snapshot")
    parser.add_argument("--agy-version", default="agy 1.1.10")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--condition", choices=common.CONDITIONS, action="append")
    parser.add_argument("--task", choices=common.TASKS, action="append")
    parser.add_argument("--plan", action="store_true", help="実行予定だけを表示して終了する")
    args = parser.parse_args(argv)

    source_root = Path(__file__).resolve().parents[3]
    output = Path(args.output).expanduser().resolve()
    manifest = Path(args.manifest).expanduser().resolve()
    corpus_root = Path(args.corpus_root).expanduser().resolve()
    conditions = tuple(args.condition or common.CONDITIONS)
    tasks = tuple(args.task or common.TASKS)
    if args.trials < 1:
        parser.error("--trials は1以上")
    if args.workers < 1:
        parser.error("--workers は1以上")
    jobs_count = len(conditions) * len(tasks) * args.trials
    if args.plan:
        print(
            json.dumps(
                {"conditions": conditions, "tasks": tasks, "trials": args.trials, "jobs": jobs_count},
                ensure_ascii=False,
            )
        )
        return 0
    if output.exists() or manifest.exists():
        raise SystemExit("既存の eval 成果物は上書きしない。新しい --output / --manifest を指定すること。")

    corpus = {
        condition: common._prepare_corpus(corpus_root, condition, source_root)
        for condition in conditions
    }
    jobs = []
    for condition in conditions:
        for task in tasks:
            for trial in range(1, args.trials + 1):
                corpus_name = common.CORPORA[(trial - 1) % len(common.CORPORA)]
                entry = corpus[condition][corpus_name]
                jobs.append(
                    {
                        "condition": condition,
                        "task": task,
                        "trial": trial,
                        "corpus": corpus_name,
                        "repo": entry["path"],
                        "raw_baseline_bytes": entry["raw_baseline_bytes"]["diff-summary"],
                        "prompt": common._prompt(
                            Path(__file__).parent / "prompts" / common.PROMPT_FILES[task]
                        ),
                        "model": args.model,
                        "model_version": args.model_version,
                        "reasoning_effort": args.reasoning_effort,
                        "timeout": args.timeout,
                        "source_root": source_root,
                    }
                )

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    _write_manifest(manifest, args, corpus, completed)
    with output.open("x", encoding="utf-8") as stream:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_one_trial, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    result = future.result()
                except Exception as error:  # raw output を成果物へ書かない
                    result = {
                        "platform": PLATFORM,
                        "condition": job["condition"],
                        "task": job["task"],
                        "trial": job["trial"],
                        "corpus": job["corpus"],
                        "model": {
                            "provider": "google",
                            "id": args.model,
                            "version": args.model_version,
                        },
                        "first_git_action": "none",
                        "reached_expected_state": False,
                        "bypassed_gate": True,
                        "self_retried": False,
                        "schema_match": False,
                        "required_fields_preserved": False,
                        "truncated": False,
                        "decision": {},
                        "output_bytes": None,
                        "raw_baseline_bytes": (
                            job["raw_baseline_bytes"] if job["task"] == "diff-summary" else None
                        ),
                        "danger": {
                            key: False
                            for key in (
                                "raw_fallback",
                                "state_change",
                                "secret_output",
                                "silent_truncation",
                            )
                        },
                        "observation": {"runner_error": type(error).__name__},
                    }
                stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                completed += 1
                _write_manifest(manifest, args, corpus, completed)
                print(
                    f"[{completed}/{jobs_count}] {result['condition']}/{result['task']}"
                    f"#{result['trial']} {result['corpus']} first={result['first_git_action']}"
                    f" reached={result['reached_expected_state']}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
