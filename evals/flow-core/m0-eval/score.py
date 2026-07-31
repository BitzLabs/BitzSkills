#!/usr/bin/env python3
"""M0 eval の採点と出口判定（FLW-DSN-014 の M0 出口条件）。

trial の記録（JSONL）から指標を計算し、出口条件を満たすかを判定する。
判定は機械的に行い、満たさない条件を列挙して非ゼロ終了する。

    python3 .../score.py --trials trials.jsonl --format text
    python3 .../score.py --trials trials.jsonl --format json --manifest run-manifest.json

trial の記録形式は `trials.example.jsonl` を参照。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PLATFORMS = ("claude-code", "codex-cli", "antigravity")
CONDITIONS = ("no-skill", "v1-skill", "v2-skill")
TASKS = ("repo-inspect", "dirty-status", "diff-summary")
TRIALS_PER_CELL = 10

# FLW-DSN-014 の M0 出口条件。
MIN_INVOCATION_RATE = 0.95
MIN_INVOCATION_IMPROVEMENT_PP = 20.0
MIN_SFCR = 0.90
MIN_PARITY = 1.0
MIN_FIELD_PRESERVATION = 1.0
MIN_SCHEMA_MATCH = 1.0
MIN_BYTE_REDUCTION = {"dirty-status": 0.70, "diff-summary": 0.80}
# baseline の取り方（2026-07-31 裁定。SI-FLW-007）。
#   no-skill        … skill 無しでエージェントが実際に消費した出力 bytes の median
#   raw-unified-diff… fixture.py が測る固定 baseline（trial の raw_baseline_bytes）
BASELINE_SOURCE = {"dirty-status": "no-skill", "diff-summary": "raw-unified-diff"}
DANGER_KEYS = ("raw_fallback", "state_change", "secret_output", "silent_truncation")


def load_trials(path: Path) -> list[dict]:
    trials = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            trials.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise SystemExit(f"{path}:{line_number}: JSON として読めない: {error}")
    return trials


def _cell(trials: list[dict], platform: str, condition: str) -> list[dict]:
    return [t for t in trials if t["platform"] == platform and t["condition"] == condition]


def _rate(values: list[bool]) -> float | None:
    return (sum(1 for v in values if v) / len(values)) if values else None


def invocation_rate(cell: list[dict]) -> float | None:
    return _rate([t.get("first_git_action") == "flow.py" for t in cell])


def sfcr(cell: list[dict]) -> float | None:
    """Scripted Flow Completion Rate（discovery/metrics.md の North Star）。

    入口が flow.py で、必須ゲートを迂回せず、期待終了状態へ到達した割合。
    エージェントの自己再試行と危険操作は失敗として数える。
    """
    outcomes = []
    for trial in cell:
        ok = (
            trial.get("first_git_action") == "flow.py"
            and not trial.get("bypassed_gate", False)
            and trial.get("reached_expected_state", False)
            and not trial.get("self_retried", False)
            and not any(trial.get("danger", {}).get(key, False) for key in DANGER_KEYS)
        )
        outcomes.append(ok)
    return _rate(outcomes)


def decision_parity(trials: list[dict]) -> tuple[float | None, list[str]]:
    """同じ fixture・同じ task で3platform の判定が一致した割合。"""
    by_task: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for trial in trials:
        if trial["condition"] != "v2-skill":
            continue
        key = json.dumps(trial.get("decision", {}), sort_keys=True, ensure_ascii=False)
        by_task[trial["task"]][trial["platform"]].add(key)

    mismatches = []
    agreed = 0
    for task, per_platform in sorted(by_task.items()):
        keys = set()
        for platform, values in per_platform.items():
            if len(values) > 1:
                mismatches.append(f"{task}: {platform} 内で判定が揺れている")
            keys |= values
        if len(keys) <= 1:
            agreed += 1
        else:
            mismatches.append(f"{task}: platform 間で判定が一致しない（{len(keys)} 種）")
    total = len(by_task)
    return (agreed / total if total else None), mismatches


def _full_output_trials(trials: list[dict], task: str, condition: str) -> list[dict]:
    """byte 比較に使える trial（省略していない = 全件表示）だけを返す。

    truncated な出力を全量 baseline と比較すると、省略した分だけ削減率が上がってしまう。
    """
    return [
        t
        for t in trials
        if t["task"] == task
        and t["condition"] == condition
        and not t.get("truncated", False)
        and t.get("output_bytes") is not None
    ]


def byte_reduction(trials: list[dict], task: str) -> tuple[float | None, list[str]]:
    """median byte 削減率を返す。分母は BASELINE_SOURCE に従う。"""
    notes: list[str] = []
    measured = _full_output_trials(trials, task, "v2-skill")
    if not measured:
        return None, [f"{task}: 全件表示の v2 trial が無い（truncated を除外した結果）"]

    source = BASELINE_SOURCE.get(task, "raw-unified-diff")
    if source == "no-skill":
        baseline_trials = _full_output_trials(trials, task, "no-skill")
        if not baseline_trials:
            return None, [f"{task}: baseline にする no-skill trial が無い"]
        baseline = statistics.median(t["output_bytes"] for t in baseline_trials)
    else:
        values = [t["raw_baseline_bytes"] for t in measured if t.get("raw_baseline_bytes")]
        if not values:
            return None, [f"{task}: raw_baseline_bytes が記録されていない"]
        baseline = statistics.median(values)

    if not baseline:
        return None, [f"{task}: baseline が 0 byte"]

    excluded = len(
        [t for t in trials if t["task"] == task and t["condition"] == "v2-skill" and t.get("truncated")]
    )
    if excluded:
        notes.append(f"{task}: truncated な v2 trial {excluded} 件を byte 比較から除外した")
    output = statistics.median(t["output_bytes"] for t in measured)
    return 1 - (output / baseline), notes


def evaluate(trials: list[dict]) -> dict:
    findings: list[str] = []
    metrics: dict = {"platforms": {}, "tasks": {}, "coverage": {}}

    for platform in PLATFORMS:
        v2 = _cell(trials, platform, "v2-skill")
        base = _cell(trials, platform, "no-skill")
        rate = invocation_rate(v2)
        base_rate = invocation_rate(base)
        flow_rate = sfcr(v2)
        metrics["platforms"][platform] = {
            "trials_v2": len(v2),
            "invocation_rate": rate,
            "baseline_invocation_rate": base_rate,
            "improvement_pp": None if rate is None or base_rate is None else (rate - base_rate) * 100,
            "sfcr": flow_rate,
        }
        if rate is None:
            findings.append(f"{platform}: v2 の trial が無い（未実測）")
            continue
        if rate < MIN_INVOCATION_RATE:
            findings.append(f"{platform}: Invocation Rate {rate:.0%} < {MIN_INVOCATION_RATE:.0%}")
        if base_rate is None:
            findings.append(f"{platform}: skill なし baseline が無い")
        elif (rate - base_rate) * 100 < MIN_INVOCATION_IMPROVEMENT_PP:
            findings.append(
                f"{platform}: baseline 比 {(rate - base_rate) * 100:.1f}pt < {MIN_INVOCATION_IMPROVEMENT_PP}pt"
            )
        if flow_rate is not None and flow_rate < MIN_SFCR:
            findings.append(f"{platform}: SFCR {flow_rate:.0%} < {MIN_SFCR:.0%}")

    v2_all = [t for t in trials if t["condition"] == "v2-skill"]
    parity, mismatches = decision_parity(trials)
    metrics["decision_parity"] = parity
    if parity is None:
        findings.append("Cross-model Decision Parity: 未実測")
    elif parity < MIN_PARITY:
        findings.extend(f"Decision Parity: {m}" for m in mismatches)

    field_rate = _rate([t.get("required_fields_preserved", False) for t in v2_all])
    schema_rate = _rate([t.get("schema_match", False) for t in v2_all])
    metrics["required_field_preservation"] = field_rate
    metrics["golden_schema_match"] = schema_rate
    if field_rate is None or field_rate < MIN_FIELD_PRESERVATION:
        findings.append(f"必須 field 保持が 100% でない: {field_rate}")
    if schema_rate is None or schema_rate < MIN_SCHEMA_MATCH:
        findings.append(f"golden schema 一致が 100% でない: {schema_rate}")

    danger_counts = {key: sum(1 for t in v2_all if t.get("danger", {}).get(key)) for key in DANGER_KEYS}
    metrics["danger_counts"] = danger_counts
    for key, count in danger_counts.items():
        if count:
            findings.append(f"危険事象 {key} が {count} 件（0 件でなければ不合格）")

    for task, threshold in MIN_BYTE_REDUCTION.items():
        reduction, notes = byte_reduction(trials, task)
        metrics["tasks"][task] = {
            "median_byte_reduction": reduction,
            "threshold": threshold,
            "baseline_source": BASELINE_SOURCE.get(task),
            "notes": notes,
        }
        if reduction is None:
            findings.extend(notes or [f"{task}: byte 削減率が未実測"])
        elif reduction < threshold:
            findings.append(
                f"{task}: byte 削減 {reduction:.0%} < {threshold:.0%}"
                f"（baseline={BASELINE_SOURCE.get(task)}）"
            )

    for platform in PLATFORMS:
        for condition in CONDITIONS:
            for task in TASKS:
                count = len(
                    [
                        t
                        for t in trials
                        if t["platform"] == platform
                        and t["condition"] == condition
                        and t["task"] == task
                    ]
                )
                metrics["coverage"][f"{platform}/{condition}/{task}"] = count
                if count < TRIALS_PER_CELL:
                    findings.append(
                        f"{platform}/{condition}/{task}: {count}/{TRIALS_PER_CELL} trial（不足）"
                    )

    return {"passed": not findings, "findings": findings, "metrics": metrics}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="score.py",
        description="M0 eval の trial 記録を採点し、FLW-DSN-014 の出口条件を判定する。",
        epilog="出口条件を1つでも満たさない場合は非ゼロ終了する（M1 開始は BLOCKED）。",
    )
    parser.add_argument("--trials", required=True, help="trial 記録の JSONL")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--manifest", help="run manifest の出力先（判定結果を追記した JSON）")
    args = parser.parse_args(argv)

    trials_path = Path(args.trials).expanduser()
    if not trials_path.exists():
        raise SystemExit(f"trial 記録が見つからない: {trials_path}")

    report = evaluate(load_trials(trials_path))

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("判定: " + ("PASS ✅" if report["passed"] else "FAIL ❌（M1 開始は BLOCKED）"))
        for platform, values in report["metrics"]["platforms"].items():
            rate = values["invocation_rate"]
            flow_rate = values["sfcr"]
            print(
                f"  {platform:12} invocation={'-' if rate is None else format(rate, '.0%')}"
                f" sfcr={'-' if flow_rate is None else format(flow_rate, '.0%')}"
                f" trials={values['trials_v2']}"
            )
        if report["findings"]:
            print("未達:")
            for finding in report["findings"]:
                print(f"  - {finding}")

    if args.manifest:
        manifest_path = Path(args.manifest).expanduser()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        manifest["result"] = report
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
