#!/usr/bin/env python3
"""Codex CLI で M0 eval trial を実測し、要約 JSONL を保存する。

Codex の ``--json`` event stream はメモリ上で観測し、成果物へ書くのは
``trials.example.jsonl`` と同じ再判定可能な要約値だけである。
``--keep-logs DIR`` を指定した run に限り、失敗の事後解析用に raw stdout /
stderr を DIR へ保存する（成果物ディレクトリとは別に置くこと）。
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import fixture as fixture_builder
# condition ごとの所要 trial 数の正は採点側（M0 出口条件の実装）にある。runner が
# それを読むことで、起動オプションの揃え忘れが旧条件の測定を生むことを防ぐ
# （SI-FLW-026 / FLW-NFR-001）。
from score import TRIALS_PER_CELL


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

# `exit_code` の由来。runner ごとに実体が違うため、等価であるかのように扱わない
# （SI-FLW-020）。採点は `exit_code` ではなく result code で行い、本 field は
# trial 記録の観測メタデータとしてのみ残す。
#   native     … process の実 exit code
#   error-flag … tool 側の失敗フラグを 0/1 へ写したもの（実値ではない）
#   unavailable… runner が exit code を公開しない（`exit_code` は None）
EXIT_CODE_SOURCE = "native"

# result envelope の code のうち成功（`ok: true` / exit 0）を表すもの。
# 正は `references/output-contract.md` の code 表。語彙そのものは published schema から
# 読み、下の分類が schema の enum を網羅しなくなったら loud に落とす
# （黙って誤分類すると「実装が事実上の仕様」になる。SI-FLW-019 / SI-FLW-020）。
# M0 の予算。2026-08-08 の GP-001 裁定で再校正した値であり、正は `FLW-DSN-014` の
# 「M0の予算実績と残予算」節である。
#
# 旧実装はここを `max_prs: 1 / max_sessions: 5 / actual_prs: 0 / actual_sessions: 1 /
# budget_reconfirmation_ref: None` のリテラルで書いており、**全10ラウンドで一度も
# 更新されなかった**。`FLW-DSN-014` は「実績PR数・実績session数・レビュー修正回数・
# 出口未達理由を run manifest へ記録し、人間が次budgetの維持または変更を確認する」と
# 定めているが、記録先が定数だったため手順は実質的に動いていなかった
# （`FLW-REV-006` SYN-003 / GP-001 が「安全弁が一度も発動しなかった」とした機械的な理由）。
#
# 実績値は runner が知り得ない。**既定は `None`（未記入）**とし、`0` のような
# 事実でない値を書かない。`--actual-prs` / `--actual-sessions` で明示的に与える。
M0_BUDGET = {
    # GP-001 裁定の M0 残予算（実装 1 PR + 検証 2 PR）に、2026-08-08 の再提示・第1回で
    # 検証 +1 PR、同・第2回で検証 +2 PR（是正 PR と実測 PR を分離）を加えた改訂値。
    # **裁定のたびにここを追随させる** — 追随を怠ると `SI-FLW-027` で是正したばかりの
    # 「予算定数が更新されない」を再生産する。
    # 第2回は PR 枠のみ増やし session 枠は据え置いた（session が制約になっていないため）。
    "max_prs": 6,
    "max_sessions": 14,
    # 再校正の時点で既に消費していた PR 数（#158〜#178）。
    "consumed_prs_before_recalibration": 17,
    # 予算を再確認した裁定を古い順に並べる。最後の要素が現行の根拠。
    "budget_reconfirmation_refs": [
        "plugins/bitz-flow/.spec/reports/decision-2026-08-08-gp-001-m0-budget-exit-criteria.md",
        "plugins/bitz-flow/.spec/reports/decision-2026-08-08-m0-budget-overrun.md",
        "plugins/bitz-flow/.spec/reports/decision-2026-08-08-m0-budget-overrun-2.md",
    ],
}

SUCCESS_CODES = frozenset({"OK", "READY", "DONE"})
FAILURE_CODES = frozenset(
    {
        "INVALID_INPUT",
        "BLOCKED",
        "APPROVAL_REQUIRED",
        "UNAVAILABLE",
        "STALE",
        "PARTIAL",
        "UNSUPPORTED",
        "INDETERMINATE",
    }
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


def _prepare_corpus(
    root: Path,
    condition: str,
    source_root: Path,
    tasks: tuple[str, ...],
    trials: int,
) -> dict[str, dict]:
    """condition × corpus サイズ × task × trial ごとに独立した repo を構築する。

    corpus を trial 間で共有すると、ある trial の副作用が同じ repo を使う別 trial の
    before / after 比較へ混入し、何も変更していない trial が state_change として
    記録される（第2ラウンドの antigravity/v2-skill/diff-summary#9 が該当。SI-FLW-010）。
    共有は task をまたいでも起きていた——repo のキーに task が入っていなかったため、
    1 condition あたり small=12 / medium・large=各9 trial が同じ repo を使っていた。

    fixture.py は決定論的に構築できるため、分離しても全 trial の内容は同一に保てる。
    `changed_files` と `raw_baseline_bytes` は corpus サイズごとに一意であり、
    同サイズの最初の repo で1回だけ測る。
    """
    condition_root = root / condition
    result: dict[str, dict] = {
        name: {"paths": {}, "changed_files": None, "raw_baseline_bytes": None}
        for name in fixture_builder.CORPUS_SIZES
    }
    for task in tasks:
        for trial in range(1, trials + 1):
            name = CORPORA[(trial - 1) % len(CORPORA)]
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


def assert_corpus_is_isolated(jobs: list[dict]) -> None:
    """同一 run 内で2つの trial が同じ repo を使っていないことを機械的に確かめる。

    trial 間の独立性は測定の前提であり、崩れると無実の trial が state_change として
    計上される（SI-FLW-010）。回帰を実測前に落とすため、job 構築直後に検査する。
    """
    repos = [str(job["repo"]) for job in jobs]
    if len(set(repos)) != len(repos):
        raise SystemExit(
            "corpus が trial 間で共有されている（SI-FLW-010 の回帰）。"
            "_prepare_corpus が condition × corpus サイズ × task × trial 単位で"
            "repo を作っているか確認すること。"
        )


def _save_raw_log(platform: str, job: dict, proc: subprocess.CompletedProcess) -> str | None:
    """trial の raw event log を保存し、保存先の相対パスを返す。

    要約値だけでは「flow.py が exit 0 なのに出力 0 byte」のような観測を事後に
    切り分けられない（harness の欠陥か platform の挙動かを判別できない）。
    ``--keep-logs DIR`` を指定した run では raw stdout / stderr を残す。
    """
    directory = job.get("log_dir")
    if directory is None:
        return None
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{platform}-{job['condition']}-{job['task']}-{job['trial']:02d}"
    (directory / f"{name}.stdout.jsonl").write_text(proc.stdout or "", encoding="utf-8")
    stderr = proc.stderr or ""
    if stderr:
        (directory / f"{name}.stderr.txt").write_text(stderr, encoding="utf-8")
    return name


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


HELP_PATTERN = re.compile(r"(?:^|\s)(?:--help|-h)(?:\s|$)")


def _is_help(command: str) -> bool:
    """`--help` / `-h` を伴う実行か。

    `--help` が返すのは argparse の usage であり result envelope ではない。
    operation の実行ではないため task の実行として採点してはならない（SI-FLW-014）。
    """
    return bool(HELP_PATTERN.search(command))


@functools.lru_cache(maxsize=None)
def _result_code_vocabulary(source_root: Path) -> frozenset[str]:
    """result envelope の code 語彙を published schema から読む。

    harness へ語彙を書き写すと code が増えるたびに測定器が腐るため、正は schema から
    取る（`SI-FLW-020` の採らない案「marker 文字列の強化」への対応）。harness 側の
    成功／失敗の分類が schema の enum を網羅しなくなったら、黙って誤分類せず落とす。
    """
    schema = json.loads(
        (source_root / "plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    codes = frozenset(schema["$defs"]["code"]["enum"])
    classified = SUCCESS_CODES | FAILURE_CODES
    if classified != codes:
        raise SystemExit(
            "result code の分類が schema と食い違う（harness を更新すること）: "
            f"schema のみ={sorted(codes - classified)} harness のみ={sorted(classified - codes)}"
        )
    return codes


def result_code(output: str, source_root: Path) -> str | None:
    """flow.py の出力から result code を読む。result envelope でなければ None。

    compact 出力の先頭 token は code であり（`render_compact` の判定行）、`--format json`
    なら `code` field を持つ。いずれも **platform の event contract に依存せず読める**ため、
    runner ごとに実体の違う `exit_code` の代わりにこれで成否を判定する（`SI-FLW-020`）。
    `--help` の usage テキストなど result envelope でない出力は None を返す。
    """
    text = output.strip()
    if not text:
        return None
    codes = _result_code_vocabulary(source_root)
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        code = parsed.get("code") if isinstance(parsed, dict) else None
        return code if code in codes else None
    token = text.splitlines()[0].split(maxsplit=1)[0] if text.splitlines() else ""
    return token if token in codes else None


def _succeeded(item: dict, source_root: Path) -> bool:
    return result_code(item["output"], source_root) in SUCCESS_CODES


def self_retried(relevant: list[dict], source_root: Path) -> bool:
    """エージェント自身が失敗を受けて呼び直したか（SFCR の減点要因）。

    旧実装は `exit_code` の非ゼロで判定していたが、実体が runner ごとに違い
    antigravity では構造的に永久 false であった（`SI-FLW-020`）。result code で判定する。
    """
    return len(relevant) > 1 and any(
        result_code(item["output"], source_root) in FAILURE_CODES for item in relevant
    )


def _task_output(
    commands: list[dict], condition: str, task: str, source_root: Path
) -> tuple[str, bool]:
    """task の答えとして採点する出力と、その成否を返す。

    採点対象は「省略が無く、成功した呼出のうち最後のもの」を優先する。正解を得たあとに
    探索的な失敗呼出を1回足しただけで不合格になる問題（`SI-FLW-017`）を、`exit_code` では
    なく result code で解く（`SI-FLW-020`）。成功呼出が1件も無い trial は従来どおり
    不合格であり、「失敗をなかったことにする」方向へは倒さない（`SI-FLW-014` の歯止め）。
    """
    if condition == "v2-skill":
        matches = [
            item
            for item in commands
            if TASK_FLOW_PATTERN[task].search(item["command"]) and not _is_help(item["command"])
        ]
        if not matches:
            # `--help` しか実行しなかった場合もここへ来る。task を実行していない以上、
            # 従来どおり失敗として扱う（除外が「なかったこと」にならない）。
            return "", False
        complete = [item for item in matches if "TRUNCATED " not in item["output"]]
        pool = complete or matches
        succeeded = [item for item in pool if _succeeded(item, source_root)]
        selected = (succeeded or pool)[-1]
        return selected["output"], _succeeded(selected, source_root)

    # skill なし / v1 baseline は生 git であり result envelope を返さない。ここだけは
    # `exit_code` を使うが、`None`（runner が公開しない）は失敗と見なさない。
    raw = [item for item in commands if RAW_GIT_PATTERN.search(item["command"])]
    return "".join(item["output"] for item in raw), bool(raw) and all(
        item["exit_code"] in (0, None) for item in raw
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


def _empty_output_positions(commands: list[dict]) -> list[int]:
    """出力0かつ exit 0 の flow.py 実行の位置（1始まり）を返す。

    codex の event stream は `aggregated_output` が唯一の出力搬送路であり、確率的に
    空になることがある（`SI-FLW-012`）。エージェントには出力が届いているため失敗ではなく
    **測定不能**であり、失敗として数えてはならない。
    """
    return [
        index
        for index, item in enumerate(commands, start=1)
        # `None` は runner が exit code を公開しないことを指し、失敗ではない（SI-FLW-020）。
        if "flow.py" in item["command"] and item["exit_code"] in (0, None) and not item["output"]
    ]


# 3 runner が必ず書く observation の共通部（`FLW-REV-006` GP-003）。
#
# 判定ロジック（`_task_output` 等）は共有していたのに `observation` は各 runner が個別に
# 構築していたため、`SI-FLW-012` / `SI-FLW-014` の裁定で置いた歯止めが **codex-cli でしか
# 効いていなかった**（`SI-FLW-025`）。集計側は `t.get(key, default)` で吸収するため
# 「記録されていない」と「記録されたが偽」が区別できず、その事実がデータ構造上検出できない。
# 共通部をここで一括生成し、欠けたら採点側がエラーにする。
REQUIRED_OBSERVATION_KEYS = frozenset(
    {
        "runner_exit_code",
        "exit_code_source",
        "raw_log",
        "timed_out",
        "state_change_reasons",
        "command_events",
        "command_kinds",
        "command_result_codes",
        "task_flow_matches",
        "task_flow_exit_codes",
        "task_flow_result_codes",
        "task_flow_output_bytes",
        "empty_output_positions",
        "help_invocations",
        "task_output_missing",
        "harness_attempts",
    }
)


def build_observation(
    *,
    commands: list[dict],
    relevant: list[dict],
    output: str,
    condition: str,
    source_root: Path,
    exit_code_source: str,
    runner_exit_code: int | None,
    raw_log: str | None,
    timed_out: bool,
    state_change_reasons: dict,
    platform_fields: dict | None = None,
) -> dict:
    """observation の共通部を組み立てる。platform 固有 field は `platform_fields` で足す。

    `harness_attempts` は `run_trial` が再試行回数を確定した時点で上書きする。
    """
    observation = {
        # runner process の exit code。実体は runner ごとに違うため由来を必ず添える
        # （`exit_code_source`。SI-FLW-020）。採点には使わない。
        "runner_exit_code": runner_exit_code,
        "exit_code_source": exit_code_source,
        "raw_log": raw_log,
        "timed_out": timed_out,
        "state_change_reasons": state_change_reasons,
        "command_events": len(commands),
        "command_kinds": [
            "flow.py"
            if "flow.py" in item["command"]
            else "raw-git"
            if RAW_GIT_PATTERN.search(item["command"])
            else "other"
            for item in commands
        ],
        # per-call の result code。出力全文を残さずに事後の再解析を厳密に行うための
        # 一次証拠である（`FLW-REV-006` GP-005）。byte 長による近似では
        # `repo-inspect`（OK 99B / INVALID_INPUT 61B）を分離できなかった。
        "command_result_codes": [result_code(item["output"], source_root) for item in commands],
        "task_flow_matches": len(relevant),
        "task_flow_exit_codes": [item["exit_code"] for item in relevant],
        "task_flow_result_codes": [result_code(item["output"], source_root) for item in relevant],
        "task_flow_output_bytes": [len(item["output"].encode("utf-8")) for item in relevant],
        # 正常な空結果と測定不能を区別するために位置を残す（SI-FLW-012）。
        "empty_output_positions": _empty_output_positions(commands),
        # 採点対象から外した `--help` 実行を残す。黙って捨てない（SI-FLW-014）。
        "help_invocations": [item["command"] for item in commands if _is_help(item["command"])],
        # 測定不能と見なすのは **task 対象の呼び出し**の出力が失われた場合だけ。
        # 探索目的の呼び出しが欠けても、task 対象の出力が観測できていれば採点はできる。
        "task_output_missing": condition == "v2-skill" and bool(relevant) and not output,
        "harness_attempts": 1,
    }
    observation.update(platform_fields or {})
    missing = REQUIRED_OBSERVATION_KEYS - set(observation)
    if missing:
        raise SystemExit(f"observation の共通部が欠けている: {sorted(missing)}")
    return observation


def failed_observation(exit_code_source: str, error: Exception) -> dict:
    """runner が例外で終わったときの observation。共通部の key は必ず埋める。

    runner の異常終了は測定不能ではなく失敗として数える（SI-FLW-012 の除外規則を
    runner のバグの隠れ蓑にしない）。
    """
    observation = {
        "runner_error": type(error).__name__,
        "runner_exit_code": None,
        "exit_code_source": exit_code_source,
        "raw_log": None,
        "timed_out": False,
        "state_change_reasons": {},
        "command_events": 0,
        "command_kinds": [],
        "command_result_codes": [],
        "task_flow_matches": 0,
        "task_flow_exit_codes": [],
        "task_flow_result_codes": [],
        "task_flow_output_bytes": [],
        "empty_output_positions": [],
        "help_invocations": [],
        "task_output_missing": False,
        "harness_attempts": 1,
    }
    missing = REQUIRED_OBSERVATION_KEYS - set(observation)
    if missing:
        raise SystemExit(f"observation の共通部が欠けている: {sorted(missing)}")
    return observation


def run_trial(job: dict, attempt) -> dict:
    """測定不能（SI-FLW-012）を検出したら harness 側で trial をやり直す（3 runner 共通）。

    エージェントの自己再試行（`self_retried`）とは別物であり、そちらへは計上しない。
    再試行を尽くしても解消しない場合は `measurable: false` として記録し、採点側が
    根拠つきで母数から外せるようにする。

    この機構は `SI-FLW-012` の裁定で導入したが **codex-cli にしか入っていなかった**。
    claude-code のレート制限拒否（第9ラウンド。v2 30 trial が全滅）が「測定不能」ではなく
    素点の FAIL として集計されたのはこのためである（`SI-FLW-025` / GP-003）。
    """
    attempts = []
    for _ in range(1 + max(0, int(job.get("harness_retries", 0)))):
        record = attempt(job)
        attempts.append(record)
        if not record["observation"]["task_output_missing"]:
            break
    record = attempts[-1]
    record["measurable"] = not record["observation"]["task_output_missing"]
    record["observation"]["harness_attempts"] = len(attempts)
    return record


def _one_trial(job: dict) -> dict:
    return run_trial(job, _one_attempt)


def _one_attempt(job: dict) -> dict:
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
    raw_log = _save_raw_log(PLATFORM, job, proc)
    events = _events(proc.stdout)
    commands = _commands(events)
    messages = _messages(events)
    output, command_ok = _task_output(
        commands, job["condition"], job["task"], job["source_root"]
    )
    first_action = _first_git_action(commands)
    oracle = _flow_json(job["source_root"], repo, job["task"])
    truncated = "TRUNCATED " in output
    # 判定根拠を分けて残す。repo_diff だけが立つ場合、trial 自身は何も実行していないのに
    # 状態が変わったことを意味する（corpus 分離後は起こらないはずの事象）。raw log と
    # 突き合わせずに真偽を切り分けられるようにする（SI-FLW-010）。
    state_change_reasons = {
        "repo_diff": before != after,
        "command": any(STATE_CHANGE_PATTERN.search(item["command"]) for item in commands),
    }
    state_change = any(state_change_reasons.values())
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
    retried = self_retried(relevant, job["source_root"])

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
        "self_retried": retried,
        "schema_match": schema,
        "required_fields_preserved": fields,
        "truncated": truncated,
        "decision": _decision(oracle, job["task"]),
        "output_bytes": len(output.encode("utf-8")) if output else None,
        "raw_baseline_bytes": job["raw_baseline_bytes"],
        "danger": {
            "raw_fallback": raw_fallback,
            "state_change": state_change,
            "secret_output": secret_output,
            "silent_truncation": silent_truncation,
        },
        "observation": build_observation(
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
        "note": "Codex CLI のみの部分実測。raw Codex event log は保存せず、trial 要約だけを記録。",
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
            **M0_BUDGET,
            # 実績は runner が知り得ないため未指定なら null を書く（0 は事実でない）。
            "actual_prs": args.actual_prs,
            "actual_sessions": args.actual_sessions,
            "review_fix_rounds": args.review_fix_rounds,
            "exit_miss_reasons": [],
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
    parser.add_argument(
        "--harness-retries",
        type=int,
        default=5,
        help="測定不能（出力欠落。SI-FLW-012）を検出したときに harness 側でやり直す上限回数。"
        "エージェントの自己再試行とは別物であり self_retried には計上しない。"
        "出力欠落は必ずセッション内2番目のコマンドで起き、再試行しても同じ位置へ戻るため"
        "（repo-inspect は task 対象の呼び出しがその位置に来る）、回数だけでは収束しない。"
        "測定可能 10 件を確保するには --trials も併せて増やすこと",
    )
    parser.add_argument(
        "--trials",
        type=int,
        help="全 condition へ一律に適用する trial 数。既定は condition ごとの所要数"
        f"（{TRIALS_PER_CELL}）を使う。smoke run で少なく回すとき以外は指定しないこと",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--condition", choices=CONDITIONS, action="append")
    parser.add_argument("--task", choices=TASKS, action="append")
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
    conditions = tuple(args.condition or CONDITIONS)
    tasks = tuple(args.task or TASKS)
    if args.trials is not None and args.trials < 1:
        parser.error("--trials は1以上")
    trials_per_condition = {
        condition: (args.trials if args.trials is not None else TRIALS_PER_CELL[condition])
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
        condition: _prepare_corpus(
            corpus_root, condition, source_root, tasks, trials_per_condition[condition]
        )
        for condition in conditions
    }
    jobs = []
    for condition in conditions:
        for task in tasks:
            for trial in range(1, trials_per_condition[condition] + 1):
                corpus_name = CORPORA[(trial - 1) % len(CORPORA)]
                entry = corpus[condition][corpus_name]
                jobs.append(
                    {
                        "condition": condition,
                        "task": task,
                        "trial": trial,
                        "corpus": corpus_name,
                        "repo": entry["paths"][(task, trial)],
                        "raw_baseline_bytes": entry["raw_baseline_bytes"].get(task),
                        "prompt": _prompt(Path(__file__).parent / "prompts" / PROMPT_FILES[task]),
                        "model": args.model,
                        "model_version": args.model_version,
                        "reasoning_effort": args.reasoning_effort,
                        "timeout": args.timeout,
                        "source_root": source_root,
                        "log_dir": log_dir,
                        "harness_retries": args.harness_retries,
                    }
                )
    assert_corpus_is_isolated(jobs)

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
                        # runner の異常終了は測定不能ではなく失敗として数える（SI-FLW-012 の
                        # 除外規則を runner のバグの隠れ蓑にしない）。
                        "measurable": True,
                        "observation": failed_observation(EXIT_CODE_SOURCE, error),
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
