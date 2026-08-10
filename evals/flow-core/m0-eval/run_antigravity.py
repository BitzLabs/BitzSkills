#!/usr/bin/env python3
"""Antigravity CLI で M0 eval trial を実測し、要約 JSONL を保存する。

``agy --output-format stream-json`` の event stream はメモリ上で観測し、
成果物へ書くのは再判定可能な要約値だけである。``--keep-logs DIR`` を指定した
run に限り、失敗の事後解析用に raw stdout / stderr を DIR へ保存する。
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
# agy の event contract は exit code を公開しない。推測せず「不明」を記録する（SI-FLW-020）。
EXIT_CODE_SOURCE = "unavailable"
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
                # 旧実装は出力に `error` / `failed` / `exit code: 1` を含むかで代用したが、
                # flow.py の失敗行（`INVALID_INPUT ... cause=invalid-ref stage=inspect`、実 exit 2）は
                # どの marker にも一致せず、242 回の呼出で一度も非ゼロを記録できなかった
                # ＝計測器が沈黙して失敗していた（SI-FLW-020）。推測せず「不明」を記録し、
                # 成否の判定は result code 側で行う。
                "exit_code": None,
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
    return common.run_trial(job, _one_attempt)


def _one_attempt(job: dict) -> dict:
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
        # agy の --sandbox は既定 true の bool flag であり、bare 指定では解除できない
        # （`--sandbox=<true|false>`。docs/調査報告/01.Antigravity/02_cli_reference.md）。
        # sandbox が有効だとターミナル隔離でコマンドを実行できず、
        # --dangerously-skip-permissions があっても ask_permission へ落ちる。
        "--sandbox=false",
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
    raw_log = common._save_raw_log(PLATFORM, job, proc)
    events = common._events(proc.stdout)
    tools = _tools(events)
    commands = _commands(tools)
    messages, result = _result(events)
    output, command_ok = common._task_output(
        commands, job["condition"], job["task"], job["source_root"]
    )
    first_action = common._first_git_action(commands)
    oracle = common._flow_json(job["source_root"], repo, job["task"])
    truncated = "TRUNCATED " in output
    # 判定根拠を分けて残す（SI-FLW-010）。第2ラウンドの diff-summary#9 は
    # repo_diff だけが立った誤検知で、真偽の切り分けに raw log が要った。
    # `tool` は書込先パスが corpus 配下のときだけ立てる（SI-FLW-031）。agy は長い一覧を
    # 自分の brain ディレクトリ（corpus 外）へ書き出して本文から参照する動作をするため、
    # パスを見ない判定はリポジトリ無変更の trial を状態変更と誤検出した。
    tool_inside, tool_path_unknown = common.tool_state_change(
        tools, MUTATING_TOOLS, repo, "parameters"
    )
    state_change_reasons = {
        "repo_diff": before != after,
        "command": any(common.STATE_CHANGE_PATTERN.search(item["command"]) for item in commands),
        "tool": tool_inside,
    }
    state_change = any(state_change_reasons.values())
    secret_output = bool(
        common.SECRET_PATTERN.search("\n".join(item["output"] for item in tools))
    )
    raw_fallback = job["condition"] == "v2-skill" and any(
        common.RAW_GIT_PATTERN.search(item["command"])
        for item in commands
        if "flow.py" not in item["command"]
    )
    silent_truncation = truncated and not common.truncation_disclosed(output, messages)
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
    retried = common.self_retried(relevant, job["source_root"])
    usage = result.get("usage", {}) if isinstance(result.get("usage"), dict) else {}
    error_events = sum(
        1
        for event in events
        if event.get("event") == "step_update"
        and event.get("step_update", {}).get("step_type") == "error_message"
    )
    # quota 枯渇（`RESOURCE_EXHAUSTED (code 429)`）で 0 command・0 tool・0 token・0 秒で
    # 終わった trial は測定不能である（SI-FLW-030）。第12ラウンドはこれを素点の FAIL として
    # 集計し、harness 再試行も発動しなかった。
    agy_error = str(result.get("error") or "")
    unavailable = common.agent_unavailable(
        command_events=len(commands),
        tool_events=len(tools),
        usage_tokens=usage.get("total_tokens"),
        duration_seconds=result.get("duration_seconds"),
        error_text=agy_error,
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
        "self_retried": retried,
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
        "observation": common.build_observation(
            commands=commands,
            relevant=relevant,
            output=output,
            condition=job["condition"],
            source_root=job["source_root"],
            exit_code_source=EXIT_CODE_SOURCE,
            runner_exit_code=proc.returncode,
            raw_log=raw_log,
            timed_out=timed_out,
            state_change_reasons=state_change_reasons,
            agent_unavailable=unavailable,
            unavailable_reason=(agy_error.strip()[:200] or None) if unavailable else None,
            tool_path_unknown=tool_path_unknown,
            platform_fields={
                "agy_result_status": result.get("status"),
                "tool_events": len(tools),
                "tool_kinds": [item["name"] for item in tools],
                "error_events": error_events,
                "usage_total_tokens": usage.get("total_tokens"),
                "duration_seconds": result.get("duration_seconds"),
            },
        ),
    }


def _write_manifest(
    path: Path,
    args: argparse.Namespace,
    corpus: dict,
    completed: int,
    trials_per_condition: dict[str, int],
) -> None:
    payload = {
        "milestone": "M0",
        "status": "partially-measured" if completed else "measuring",
        "note": "Antigravity CLI のみの部分実測。raw event log は保存せず、trial 要約だけを記録。",
        "prompt_version": "2026-07-31.1",
        "fixture": {
            "builder": "evals/flow-core/m0-eval/fixture.py",
            "schedule": "corpus は trial 番号の 3 剰余で割当（1=small, 2=medium, 0=large）",
            "raw_baseline_bytes": {
                condition: {
                    name: values["raw_baseline_bytes"] for name, values in per_condition.items()
                }
                for condition, per_condition in corpus.items()
            },
        },
        # ラウンドの母数と再試行上限を証跡として残す。どの条件で測った記録かを
        # 事後に確かめられるようにする（SI-FLW-026 / SI-FLW-025）。
        "trials_per_condition": trials_per_condition,
        "harness_retries": args.harness_retries,
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
                "agy_cli": common.cli_version(["agy", "--version"], args.agy_version),
                "measured_at": common._utc_now(),
                "completed_trials": completed,
                "execution": "--new-project --mode accept-edits --sandbox --dangerously-skip-permissions",
            },
        },
        "budget": {
            **common.M0_BUDGET,
            # 実績は runner が知り得ないため未指定なら null を書く（0 は事実でない）。
            "actual_prs": args.actual_prs,
            "actual_sessions": args.actual_sessions,
            "review_fix_rounds": args.review_fix_rounds,
            "exit_miss_reasons": [],
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
    # 既定値リテラルは実環境と乖離したまま記録される（SI-FLW-034）。未指定なら実測し、
    # 実測もできなければ null（未記入）にする。事実でない値を書かない。
    parser.add_argument(
        "--model-version",
        default=None,
        help="model の version / date。未指定なら null（推測しない）",
    )
    parser.add_argument(
        "--agy-version",
        default=None,
        help="agy CLI の版。未指定なら `agy --version` を実測する",
    )
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"), default="low")
    parser.add_argument(
        "--harness-retries",
        type=int,
        default=2,
        help="測定不能（task 対象の flow.py 呼出の出力が失われた事象。SI-FLW-012）を"
        "検出したときに harness 側でやり直す上限回数。エージェントの自己再試行とは別物であり"
        "self_retried には計上しない。codex-cli は aggregated_output が確率的に空になる"
        "構造的な要因を持つため既定 5、本 runner は既知の欠落要因が無いため保守的な安全網として 2 とする",
    )
    parser.add_argument(
        "--trials",
        type=int,
        help="全 condition へ一律に適用する trial 数。既定は condition ごとの所要数"
        f"（{common.TRIALS_PER_CELL}）を使う。smoke run で少なく回すとき以外は指定しないこと",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--condition", choices=common.CONDITIONS, action="append")
    parser.add_argument("--task", choices=common.TASKS, action="append")
    parser.add_argument(
        "--actual-prs",
        type=int,
        help="本ラウンド時点の milestone 実績 PR 数。未指定なら null を記録する"
        "（0 のような事実でない既定値を書かない。FLW-REV-006 GP-001）",
    )
    parser.add_argument("--actual-sessions", type=int, help="同・実績 session 数")
    parser.add_argument("--review-fix-rounds", type=int, help="同・レビュー修正回数")
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
    if args.trials is not None and args.trials < 1:
        parser.error("--trials は1以上")
    if args.workers < 1:
        parser.error("--workers は1以上")
    trials_per_condition = {
        condition: (args.trials if args.trials is not None else common.TRIALS_PER_CELL[condition])
        for condition in conditions
    }
    jobs_count = sum(len(tasks) * count for count in trials_per_condition.values())
    if args.plan:
        print(
            json.dumps(
                {
                    "conditions": conditions,
                    "tasks": tasks,
                    "trials_per_condition": trials_per_condition,
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
        condition: common._prepare_corpus(
            corpus_root, condition, source_root, tasks, trials_per_condition[condition]
        )
        for condition in conditions
    }
    jobs = []
    for condition in conditions:
        for task in tasks:
            for trial in range(1, trials_per_condition[condition] + 1):
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
                        "harness_retries": args.harness_retries,
                    }
                )
    common.assert_corpus_is_isolated(jobs)

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    _write_manifest(manifest, args, corpus, completed, trials_per_condition)
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
                        # runner の異常終了は測定不能ではなく失敗として数える
                        # （SI-FLW-012 の除外規則を runner のバグの隠れ蓑にしない）。
                        "measurable": True,
                        "observation": common.failed_observation(EXIT_CODE_SOURCE, error),
                    }
                stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                completed += 1
                _write_manifest(manifest, args, corpus, completed, trials_per_condition)
                print(
                    f"[{completed}/{jobs_count}] {result['condition']}/{result['task']}"
                    f"#{result['trial']} {result['corpus']} first={result['first_git_action']}"
                    f" reached={result['reached_expected_state']}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
