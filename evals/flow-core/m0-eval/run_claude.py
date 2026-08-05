#!/usr/bin/env python3
"""Claude Code CLI で M0 eval trial を実測し、要約 JSONL を保存する。

``claude -p --output-format stream-json`` の event stream はメモリ上で観測し、
成果物へ書くのは再判定可能な要約値だけである。``--keep-logs DIR`` を指定した
run に限り、失敗の事後解析用に raw stdout / stderr を DIR へ保存する。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import run_codex as common


PLATFORM = "claude-code"
MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _install_condition(repo: Path, condition: str, source_root: Path) -> None:
    """Claude Code の project skill 発見パス（``.claude/skills/``）へ条件を配置する。"""
    if condition == "no-skill":
        return
    exclude = repo / ".git" / "info" / "exclude"
    current = exclude.read_text(encoding="utf-8")
    if ".claude/" not in current.splitlines():
        exclude.write_text(current.rstrip("\n") + "\n.claude/\n", encoding="utf-8")

    target = repo / ".claude" / "skills" / "flow-core"
    target.mkdir(parents=True, exist_ok=True)
    if condition == "v1-skill":
        shutil.copy2(
            source_root / "plugins/bitz-flow/skills/flow-core/SKILL.md", target / "SKILL.md"
        )
        return

    live = source_root / "plugins/bitz-flow/skills/flow-core"
    for directory in ("scripts", "references", "schemas"):
        shutil.copytree(live / directory, target / directory)
    shutil.copy2(source_root / "evals/flow-core/fixtures/v2-skill/SKILL.md", target / "SKILL.md")


def _prepare_corpus(
    root: Path,
    condition: str,
    source_root: Path,
    tasks: tuple[str, ...],
    trials: int,
) -> dict[str, dict]:
    """condition × corpus サイズ × task × trial ごとに独立した repo を構築する。

    共有すると他 trial の副作用が before / after 比較へ混入する（SI-FLW-010）。
    判定の正は common（run_codex.py）側の同名関数と揃える。
    """
    import fixture as fixture_builder

    condition_root = root / condition
    result: dict[str, dict] = {
        name: {"paths": {}, "changed_files": None, "raw_baseline_bytes": None}
        for name in fixture_builder.CORPUS_SIZES
    }
    for task in tasks:
        for trial in range(1, trials + 1):
            name = common.CORPORA[(trial - 1) % len(common.CORPORA)]
            repo = fixture_builder.build(
                condition_root / task / f"trial{trial:02d}", fixture_builder.CORPUS_SIZES[name]
            )
            _install_condition(repo, condition, source_root)
            entry = result[name]
            entry["paths"][(task, trial)] = repo
            if entry["raw_baseline_bytes"] is None:
                entry["changed_files"] = fixture_builder.changed_count(repo)
                entry["raw_baseline_bytes"] = fixture_builder.baselines(repo)
    return result


def _content_items(events: list[dict]) -> list[tuple[str, dict]]:
    """assistant / user message の content item を出現順に返す。"""
    items = []
    for event in events:
        if event.get("type") not in ("assistant", "user"):
            continue
        content = event.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict):
                items.append((event["type"], item))
    return items


def _tool_result_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    return "" if content is None else str(content)


def _tools(events: list[dict]) -> list[dict]:
    """tool_use を tool_result と突き合わせて正規化する。"""
    results: dict[str, dict] = {}
    for _, item in _content_items(events):
        if item.get("type") == "tool_result" and item.get("tool_use_id"):
            results[item["tool_use_id"]] = item

    observed = []
    for _, item in _content_items(events):
        if item.get("type") != "tool_use":
            continue
        result = results.get(item.get("id"), {})
        observed.append(
            {
                "name": str(item.get("name", "")),
                "input": item.get("input", {}) if isinstance(item.get("input"), dict) else {},
                "output": _tool_result_text(result.get("content")),
                "is_error": bool(result.get("is_error")),
                "answered": item.get("id") in results,
            }
        )
    return observed


def _commands(tools: list[dict]) -> list[dict]:
    commands = []
    for item in tools:
        if item["name"] != "Bash":
            continue
        commands.append(
            {
                "command": str(item["input"].get("command", "")),
                "output": item["output"],
                "exit_code": 1 if item["is_error"] else 0,
            }
        )
    return commands


def _messages(events: list[dict]) -> str:
    return "\n".join(
        str(item.get("text", ""))
        for source, item in _content_items(events)
        if source == "assistant" and item.get("type") == "text"
    )


def _result(events: list[dict]) -> dict:
    for event in reversed(events):
        if event.get("type") == "result":
            return event
    return {}


def _one_trial(job: dict) -> dict:
    repo: Path = job["repo"]
    before = common._state(repo)
    command = [
        "claude",
        "-p",
        job["prompt"],
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        job["model"],
        "--effort",
        job["reasoning_effort"],
        # project source だけを読み、条件間の唯一の差を「skill を置くか否か」に保つ。
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--permission-mode",
        "bypassPermissions",
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
        stdout, stderr = process.communicate(timeout=job["timeout"])
        proc = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        timed_out = False
    except subprocess.TimeoutExpired:
        # claude の子プロセスが pipe を保持する場合も trial 単位で確実に止める。
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        proc = subprocess.CompletedProcess(command, 124, stdout or "", stderr or "")
        timed_out = True

    after = common._state(repo)
    raw_log = common._save_raw_log(PLATFORM, job, proc)
    events = common._events(proc.stdout)
    tools = _tools(events)
    commands = _commands(tools)
    messages = _messages(events)
    result = _result(events)
    output, command_ok = common._task_output(commands, job["condition"], job["task"])
    first_action = common._first_git_action(commands)
    oracle = common._flow_json(job["source_root"], repo, job["task"])
    truncated = "TRUNCATED " in output
    # 判定根拠を分けて残す（SI-FLW-010）。repo_diff だけが立つ場合、trial 自身は
    # 変更系のコマンドもツールも使っていないのに状態が変わったことを意味する。
    state_change_reasons = {
        "repo_diff": before != after,
        "command": any(common.STATE_CHANGE_PATTERN.search(item["command"]) for item in commands),
        "tool": any(item["name"] in MUTATING_TOOLS for item in tools),
    }
    state_change = any(state_change_reasons.values())
    secret_output = bool(common.SECRET_PATTERN.search("\n".join(item["output"] for item in tools)))
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
        and not result.get("is_error", True)
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

    return {
        "platform": PLATFORM,
        "condition": job["condition"],
        "task": job["task"],
        "trial": job["trial"],
        "corpus": job["corpus"],
        "model": {
            "provider": "anthropic",
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
        "raw_baseline_bytes": job["raw_baseline_bytes"],
        "danger": {
            "raw_fallback": raw_fallback,
            "state_change": state_change,
            "secret_output": secret_output,
            "silent_truncation": silent_truncation,
        },
        "observation": {
            "claude_exit_code": proc.returncode,
            "raw_log": raw_log,
            "claude_result_subtype": result.get("subtype"),
            "claude_is_error": result.get("is_error"),
            "timed_out": timed_out,
            "state_change_reasons": state_change_reasons,
            "tool_events": len(tools),
            "tool_kinds": [item["name"] for item in tools],
            "skill_tool_args": [
                item["input"].get("skill") for item in tools if item["name"] == "Skill"
            ],
            "command_events": len(commands),
            "command_kinds": [
                "flow.py"
                if "flow.py" in item["command"]
                else "raw-git"
                if common.RAW_GIT_PATTERN.search(item["command"])
                else "other"
                for item in commands
            ],
            # Claude Code は system prompt へ git status を自動注入するため、コマンドを
            # 1度も実行せずに回答しうる。その事実を trial 単位で残す。
            "answered_without_command": not commands,
            "task_flow_matches": len(relevant),
            "task_flow_exit_codes": [item["exit_code"] for item in relevant],
            "task_flow_output_bytes": [len(item["output"].encode("utf-8")) for item in relevant],
            "usage_total_tokens": (usage.get("input_tokens", 0) or 0)
            + (usage.get("output_tokens", 0) or 0),
            "total_cost_usd": result.get("total_cost_usd"),
            "num_turns": result.get("num_turns"),
            "duration_seconds": (result.get("duration_ms") or 0) / 1000 or None,
        },
    }


def _write_manifest(path: Path, args: argparse.Namespace, corpus: dict, completed: int) -> None:
    payload = {
        "milestone": "M0",
        "status": "partially-measured" if completed else "measuring",
        "note": "Claude Code CLI のみの部分実測。raw event log は保存せず、trial 要約だけを記録。",
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
            "no-skill": "--setting-sources project かつ repo に .claude/skills を置かない",
            "v1-skill": "repo .claude/skills に現行 v1 SKILL.md を配置",
            "v2-skill": "repo .claude/skills に v2 fixture + scripts/references/schemas を配置",
        },
        "platforms": {
            "claude-code": {
                "model_provider": "anthropic",
                "model_id": args.model,
                "model_version": args.model_version,
                "reasoning_effort": args.reasoning_effort,
                "claude_cli": args.claude_version,
                "measured_at": common._utc_now(),
                "completed_trials": completed,
                "execution": "-p --setting-sources project --strict-mcp-config"
                " --no-session-persistence --permission-mode bypassPermissions",
            },
            "codex-cli": {"status": "not-measured"},
            "antigravity": {"status": "not-measured"},
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
            "score.py の Decision Parity は corpus を grouping key に含めず task 単位で比較するため、"
            "small / medium / large の正当な件数差を揺れとして誤検出する。",
            "trial 10件を3 corpusへ均等配分できないため、固定順で small=4件、medium=3件、large=3件とした。",
            "Claude Code は system prompt へ git status を自動注入するため、no-skill 条件では"
            "コマンドを1度も実行せずに回答しうる。その trial は observation.answered_without_command=true"
            " となり output_bytes が null になる。SI-FLW-007 が定めた dirty-status の分母"
            "（no-skill でエージェントが実際に消費した出力 byte）は本 platform では観測できない。",
            "no-skill でも Claude Code 組み込みの非 flow skill は無効化できないため維持した"
            "（--setting-sources project により user / local 由来の設定と skill は読まない）。",
        ],
        "result": None,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failed_trial(job: dict, args: argparse.Namespace, error: Exception) -> dict:
    return {
        "platform": PLATFORM,
        "condition": job["condition"],
        "task": job["task"],
        "trial": job["trial"],
        "corpus": job["corpus"],
        "model": {
            "provider": "anthropic",
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
        "raw_baseline_bytes": job["raw_baseline_bytes"],
        "danger": {
            key: False
            for key in ("raw_fallback", "state_change", "secret_output", "silent_truncation")
        },
        "observation": {"runner_error": type(error).__name__},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claude Code CLI の M0 eval trial を実測する。")
    parser.add_argument("--output", required=True, help="trial JSONL の新規出力先")
    parser.add_argument("--manifest", required=True, help="部分 run manifest の新規出力先")
    parser.add_argument("--corpus-root", required=True, help="生成 corpus の専用パス")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--model-version", default="2026-08-03 service snapshot")
    parser.add_argument("--claude-version", default="claude-code 2.1.220")
    parser.add_argument(
        "--reasoning-effort", choices=("low", "medium", "high", "xhigh", "max"), default="low"
    )
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--condition", choices=common.CONDITIONS, action="append")
    parser.add_argument("--task", choices=common.TASKS, action="append")
    parser.add_argument("--plan", action="store_true", help="実行予定だけを表示して終了する")
    parser.add_argument(
        "--keep-logs",
        help="raw event log（stdout / stderr）の保存先。未指定なら保存しない",
    )
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
                {
                    "conditions": conditions,
                    "tasks": tasks,
                    "trials": args.trials,
                    "jobs": jobs_count,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if output.exists() or manifest.exists():
        raise SystemExit("既存の eval 成果物は上書きしない。新しい --output / --manifest を指定すること。")

    log_dir = Path(args.keep_logs).expanduser().resolve() if args.keep_logs else None
    corpus = {
        condition: _prepare_corpus(corpus_root, condition, source_root, tasks, args.trials)
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
                        "repo": entry["paths"][(task, trial)],
                        "raw_baseline_bytes": entry["raw_baseline_bytes"].get(task),
                        "prompt": common._prompt(
                            Path(__file__).parent / "prompts" / common.PROMPT_FILES[task]
                        ),
                        "model": args.model,
                        "model_version": args.model_version,
                        "reasoning_effort": args.reasoning_effort,
                        "timeout": args.timeout,
                        "source_root": source_root,
                        "log_dir": log_dir,
                    }
                )
    common.assert_corpus_is_isolated(jobs)

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
                    result = _failed_trial(job, args, error)
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
