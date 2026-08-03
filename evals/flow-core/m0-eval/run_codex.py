#!/usr/bin/env python3
"""Codex CLI で M0 eval trial を実測し、要約 JSONL だけを保存する。

Codex の ``--json`` event stream はメモリ上で観測し、raw log は保存しない。
保存するのは ``trials.example.jsonl`` と同じ再判定可能な要約値だけである。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import fixture as fixture_builder


PLATFORM = "codex-cli"
CONDITIONS = ("no-skill", "v1-skill", "v2-skill")
TASKS = ("repo-inspect", "dirty-status", "diff-summary")
CORPORA = ("small", "medium", "large")
PROMPT_FILES = {
    "repo-inspect": "repo-inspect.md",
    "dirty-status": "dirty-status.md",
    "diff-summary": "diff-summary.md",
}
FLOW_ARGS = {
    "repo-inspect": ("repo", "inspect"),
    "dirty-status": ("git", "status", "--limit", "1000"),
    "diff-summary": ("git", "diff-summary", "--base", "HEAD", "--limit", "1000"),
}
FLOW_OPERATION = {
    "repo-inspect": "repo.inspect",
    "dirty-status": "git.status",
    "diff-summary": "git.diff-summary",
}
TASK_FLOW_PATTERN = {
    "repo-inspect": re.compile(r"\bflow\.py\b.*\brepo\s+inspect\b", re.DOTALL),
    "dirty-status": re.compile(r"\bflow\.py\b.*\bgit\s+status\b", re.DOTALL),
    "diff-summary": re.compile(r"\bflow\.py\b.*\bgit\s+diff-summary\b", re.DOTALL),
}
RAW_GIT_PATTERN = re.compile(r"(?:^|[;&|()\s'\"])git(?:\s|$)")
STATE_CHANGE_PATTERN = re.compile(
    r"\bgit\s+(?:add|commit|checkout|switch|reset|clean|mv|rm|merge|rebase|cherry-pick|stash)\b"
    r"|\b(?:rm|mv|cp|touch)\s"
    r"|(?:^|\s)(?:>|>>)(?:\s|$)"
)
SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{12,}|github_pat_[A-Za-z0-9_]{12,}"
    r"|(?:OPENAI|CODEX|GH)_API_KEY\s*=|Authorization:\s*Bearer)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _prompt(path: Path) -> str:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("<!--")]
    return "\n".join(lines).strip()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _state(repo: Path) -> tuple[str, bytes]:
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v2", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    return head, status


def _install_condition(repo: Path, condition: str, source_root: Path) -> None:
    if condition == "no-skill":
        return
    exclude = repo / ".git" / "info" / "exclude"
    current = exclude.read_text(encoding="utf-8")
    if ".agents/" not in current.splitlines():
        exclude.write_text(current.rstrip("\n") + "\n.agents/\n", encoding="utf-8")

    target = repo / ".agents" / "skills" / "flow-core"
    target.mkdir(parents=True, exist_ok=True)
    if condition == "v1-skill":
        shutil.copy2(source_root / "plugins/bitz-flow/skills/flow-core/SKILL.md", target / "SKILL.md")
        return

    live = source_root / "plugins/bitz-flow/skills/flow-core"
    for directory in ("scripts", "references", "schemas"):
        shutil.copytree(live / directory, target / directory)
    shutil.copy2(source_root / "evals/flow-core/fixtures/v2-skill/SKILL.md", target / "SKILL.md")


def _prepare_corpus(root: Path, condition: str, source_root: Path) -> dict[str, dict]:
    condition_root = root / condition
    result: dict[str, dict] = {}
    for name, modules in fixture_builder.CORPUS_SIZES.items():
        repo = fixture_builder.build(condition_root / name, modules)
        _install_condition(repo, condition, source_root)
        result[name] = {
            "path": repo,
            "changed_files": fixture_builder.changed_count(repo),
            "raw_baseline_bytes": fixture_builder.baselines(repo),
        }
    return result


def _events(stdout: str) -> list[dict]:
    parsed = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            parsed.append(event)
    return parsed


def _commands(events: list[dict]) -> list[dict]:
    commands = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if item.get("type") != "command_execution":
            continue
        commands.append(
            {
                "command": str(item.get("command", "")),
                "output": str(item.get("aggregated_output", "")),
                "exit_code": item.get("exit_code"),
            }
        )
    return commands


def _messages(events: list[dict]) -> str:
    return "\n".join(
        str(event.get("item", {}).get("text", ""))
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    )


def _first_git_action(commands: list[dict]) -> str:
    for item in commands:
        command = item["command"]
        if "flow.py" in command:
            return "flow.py"
        if RAW_GIT_PATTERN.search(command):
            return "raw-git"
    return "none"


def _task_output(commands: list[dict], condition: str, task: str) -> tuple[str, bool]:
    if condition == "v2-skill":
        matches = [item for item in commands if TASK_FLOW_PATTERN[task].search(item["command"])]
        if not matches:
            return "", False
        complete = [item for item in matches if "TRUNCATED " not in item["output"]]
        selected = (complete or matches)[-1]
        return selected["output"], selected["exit_code"] == 0

    raw = [item for item in commands if RAW_GIT_PATTERN.search(item["command"])]
    return "".join(item["output"] for item in raw), bool(raw) and all(
        item["exit_code"] == 0 for item in raw
    )


def _flow_json(source_root: Path, repo: Path, task: str) -> dict:
    flow = source_root / "plugins/bitz-flow/skills/flow-core/scripts/flow.py"
    proc = subprocess.run(
        [sys.executable, str(flow), "--repo", str(repo), "--format", "json", *FLOW_ARGS[task]],
        capture_output=True,
        text=True,
        check=True,
        cwd=source_root,
    )
    return json.loads(proc.stdout)


def _schema_match(source_root: Path, result: dict, task: str) -> bool:
    schemas = source_root / "plugins/bitz-flow/skills/flow-core/schemas"
    envelope = json.loads((schemas / "result-v1.schema.json").read_text(encoding="utf-8"))
    operation = json.loads(
        (schemas / "operations" / f"{FLOW_OPERATION[task]}.schema.json").read_text(encoding="utf-8")
    )
    try:
        if not set(envelope["required"]) <= set(result) <= set(envelope["properties"]):
            return False
        defs = envelope["$defs"]
        if result["schema"] != "bitz-flow/result/v1":
            return False
        if result["code"] not in defs["code"]["enum"]:
            return False
        if result["exit_code"] not in envelope["properties"]["exit_code"]["enum"]:
            return False
        if result["ok"] is not (result["exit_code"] == 0):
            return False
        if not set(defs["data"]["required"]) <= set(result["data"]):
            return False
        if not set(operation["required"]) <= set(result["data"]):
            return False
        return result["operation"] == FLOW_OPERATION[task]
    except (KeyError, TypeError):
        return False


def _required_fields(output: str, result: dict, task: str, source_root: Path) -> bool:
    if not output or result.get("code") != "OK" or result.get("operation") != FLOW_OPERATION[task]:
        return False
    try:
        observed = json.loads(output)
    except json.JSONDecodeError:
        observed = None
    if isinstance(observed, dict):
        return (
            not observed.get("truncated", False)
            and _schema_match(source_root, observed, task)
            and _decision(observed, task) == _decision(result, task)
        )
    first = output.splitlines()[0] if output.splitlines() else ""
    if task == "repo-inspect":
        repo = result["data"]["repository"]
        required = (
            "OK repo.inspect",
            f"branch={repo['branch']}",
            f"head={repo['head']['sha'][:7]}",
            f"dirty={str(repo['dirty']).lower()}",
            f"remotes={len(repo['remotes'])}",
        )
        return all(value in first for value in required)

    if task == "dirty-status":
        data = result["data"]
        if not all(
            value in first
            for value in (
                "OK git.status",
                f"branch={data['branch']['name']}",
                f"changed={sum(data['counts'].values())}",
            )
        ):
            return False
        return all(item["path"] in output and item["xy"] in output for item in data["items"])

    data = result["data"]
    totals = data["totals"]
    if not all(
        value in first
        for value in (
            "OK git.diff-summary",
            f"files={totals['files']}",
            f"added={totals['added']}",
            f"deleted={totals['deleted']}",
            f"binary={totals['binary']}",
        )
    ):
        return False
    return all(
        item["path"] in output and (item["orig_path"] is None or item["orig_path"] in output)
        for item in data["items"]
    )


def _decision(result: dict, task: str) -> dict:
    if task == "repo-inspect":
        repo = result["data"]["repository"]
        return {
            "code": result["code"],
            "branch": repo["branch"],
            "dirty": repo["dirty"],
            "remotes": len(repo["remotes"]),
        }
    if task == "dirty-status":
        data = result["data"]
        return {
            "code": result["code"],
            "branch": data["branch"]["name"],
            "changed": data["page"]["total"],
        }
    totals = result["data"]["totals"]
    return {
        "code": result["code"],
        "files": totals["files"],
        "binary": totals["binary"],
        "renamed": sum(1 for item in result["data"]["items"] if item["kind"] == "renamed"),
    }


def _one_trial(job: dict) -> dict:
    repo: Path = job["repo"]
    before = _state(repo)
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--json",
        "--model",
        job["model"],
        "-c",
        f"model_reasoning_effort={job['reasoning_effort']}",
        "--cd",
        str(repo),
        job["prompt"],
    ]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=job["timeout"],
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as error:
        proc = subprocess.CompletedProcess(command, 124, error.stdout or "", error.stderr or "")
        timed_out = True

    after = _state(repo)
    events = _events(proc.stdout)
    commands = _commands(events)
    messages = _messages(events)
    output, command_ok = _task_output(commands, job["condition"], job["task"])
    first_action = _first_git_action(commands)
    oracle = _flow_json(job["source_root"], repo, job["task"])
    truncated = "TRUNCATED " in output
    state_change = before != after or any(STATE_CHANGE_PATTERN.search(item["command"]) for item in commands)
    secret_output = bool(SECRET_PATTERN.search("\n".join(item["output"] for item in commands)))
    raw_fallback = job["condition"] == "v2-skill" and any(
        RAW_GIT_PATTERN.search(item["command"]) for item in commands if "flow.py" not in item["command"]
    )
    silent_truncation = truncated and not any(
        marker in messages.lower() for marker in ("truncat", "省略", "一部", "全件", "残り")
    )
    fields = job["condition"] == "v2-skill" and _required_fields(
        output, oracle, job["task"], job["source_root"]
    )
    schema = job["condition"] == "v2-skill" and _schema_match(job["source_root"], oracle, job["task"])
    reached = (
        proc.returncode == 0
        and command_ok
        and not timed_out
        and not state_change
        and (job["condition"] != "v2-skill" or fields)
    )
    relevant = [item for item in commands if TASK_FLOW_PATTERN[job["task"]].search(item["command"])]
    self_retried = any(item["exit_code"] not in (0, None) for item in relevant) and len(relevant) > 1

    return {
        "platform": PLATFORM,
        "condition": job["condition"],
        "task": job["task"],
        "trial": job["trial"],
        "corpus": job["corpus"],
        "model": {
            "provider": "openai",
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
        "decision": _decision(oracle, job["task"]),
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
            "codex_exit_code": proc.returncode,
            "timed_out": timed_out,
            "command_events": len(commands),
            "command_kinds": [
                "flow.py"
                if "flow.py" in item["command"]
                else "raw-git"
                if RAW_GIT_PATTERN.search(item["command"])
                else "other"
                for item in commands
            ],
            "task_flow_matches": len(relevant),
            "task_flow_exit_codes": [item["exit_code"] for item in relevant],
            "task_flow_output_bytes": [len(item["output"].encode("utf-8")) for item in relevant],
        },
    }


def _write_manifest(path: Path, args: argparse.Namespace, corpus: dict, completed: int) -> None:
    payload = {
        "milestone": "M0",
        "status": "partially-measured" if completed else "measuring",
        "note": "Codex CLI のみの部分実測。raw Codex event log は保存せず、trial 要約だけを記録。",
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
            "no-skill": "--ignore-user-config + repo skill なし",
            "v1-skill": "repo .agents/skills に現行 v1 SKILL.md を配置",
            "v2-skill": "repo .agents/skills に v2 fixture + scripts/references/schemas を配置",
        },
        "platforms": {
            "claude-code": {"status": "not-measured"},
            "codex-cli": {
                "model_provider": "openai",
                "model_id": args.model,
                "model_version": args.model_version,
                "reasoning_effort": args.reasoning_effort,
                "codex_cli": args.codex_version,
                "measured_at": _utc_now(),
                "completed_trials": completed,
            },
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
        "result": None,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex CLI の M0 eval trial を実測する。")
    parser.add_argument("--output", required=True, help="trial JSONL の新規出力先")
    parser.add_argument("--manifest", required=True, help="部分 run manifest の新規出力先")
    parser.add_argument("--corpus-root", required=True, help="生成 corpus の専用パス")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--model-version", default="2026-08-03 service snapshot")
    parser.add_argument("--codex-version", default="codex-cli 0.146.0")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--condition", choices=CONDITIONS, action="append")
    parser.add_argument("--task", choices=TASKS, action="append")
    parser.add_argument("--plan", action="store_true", help="実行予定だけを表示して終了する")
    args = parser.parse_args(argv)

    source_root = Path(__file__).resolve().parents[3]
    output = Path(args.output).expanduser().resolve()
    manifest = Path(args.manifest).expanduser().resolve()
    corpus_root = Path(args.corpus_root).expanduser().resolve()
    conditions = tuple(args.condition or CONDITIONS)
    tasks = tuple(args.task or TASKS)
    if args.trials < 1:
        parser.error("--trials は1以上")
    jobs_count = len(conditions) * len(tasks) * args.trials
    if args.plan:
        print(json.dumps({"conditions": conditions, "tasks": tasks, "trials": args.trials, "jobs": jobs_count}, ensure_ascii=False))
        return 0
    if output.exists() or manifest.exists():
        raise SystemExit("既存の eval 成果物は上書きしない。新しい --output / --manifest を指定すること。")

    corpus = {
        condition: _prepare_corpus(corpus_root, condition, source_root) for condition in conditions
    }
    jobs = []
    for condition in conditions:
        for task in tasks:
            for trial in range(1, args.trials + 1):
                corpus_name = CORPORA[(trial - 1) % len(CORPORA)]
                entry = corpus[condition][corpus_name]
                jobs.append(
                    {
                        "condition": condition,
                        "task": task,
                        "trial": trial,
                        "corpus": corpus_name,
                        "repo": entry["path"],
                        "raw_baseline_bytes": entry["raw_baseline_bytes"]["diff-summary"],
                        "prompt": _prompt(Path(__file__).parent / "prompts" / PROMPT_FILES[task]),
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
                        "model": {"provider": "openai", "id": args.model, "version": args.model_version},
                        "first_git_action": "none",
                        "reached_expected_state": False,
                        "bypassed_gate": True,
                        "self_retried": False,
                        "schema_match": False,
                        "required_fields_preserved": False,
                        "truncated": False,
                        "decision": {},
                        "output_bytes": None,
                        "raw_baseline_bytes": job["raw_baseline_bytes"] if job["task"] == "diff-summary" else None,
                        "danger": {key: False for key in ("raw_fallback", "state_change", "secret_output", "silent_truncation")},
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
