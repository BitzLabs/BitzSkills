#!/usr/bin/env python3
"""CIの適合試験matrixを作り、分割ごとの予測時間を表示する。"""
import argparse
import json
from pathlib import Path

from conformance.selection import MODEL_SOURCE, estimated_seconds, partition_plan, step_ids


def duration_label(seconds):
    rounded = round(seconds)
    minutes, remainder = divmod(rounded, 60)
    return f"{minutes}分{remainder:02d}秒" if minutes else f"{remainder}秒"


def build_plan(step, shards, replicas):
    partitions = partition_plan(step_ids(step), shards)
    matrix = {"include": [
        {"replica": replica, "shard": row["shard"],
         "predicted": duration_label(row["predictedSeconds"])}
        for replica in range(1, replicas + 1) for row in partitions
    ]}
    return {"step": step, "shards": shards, "replicas": replicas,
            "source": MODEL_SOURCE, "partitions": partitions, "matrix": matrix}


def markdown(plan):
    lines = ["### 適合試験の分割予測", "",
             f"予測元: [GitHub Actions run {MODEL_SOURCE['runUrl'].rsplit('/', 1)[-1]}]({MODEL_SOURCE['runUrl']})、"
             f"commit `{MODEL_SOURCE['commit'][:8]}`、独立{MODEL_SOURCE['replicas']}組の中央値。",
             "予測時間はcheckout・artifact処理を含むjob時間の目安で、合否条件には使用しません。", "",
             "| 分割 | fixture | 予測時間 | 主なfixture |", "|---:|---:|---:|---|"]
    for row in plan["partitions"]:
        heavy = sorted(row["fixtures"], key=lambda value: (-estimated_seconds(value), value))[:4]
        lines.append(f"| {row['shard']} | {row['fixtureCount']} | "
                     f"{duration_label(row['predictedSeconds'])} | {', '.join(f'`{value}`' for value in heavy)} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True, type=int)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--replicas", required=True, type=int, choices=(1, 2))
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--github-summary", type=Path)
    args = parser.parse_args(argv)
    plan = build_plan(args.step, args.shards, args.replicas)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"step={plan['step']}\nreplica-count={plan['replicas']}\n")
            output.write("matrix=" + json.dumps(plan["matrix"], separators=(",", ":")) + "\n")
    if args.github_summary:
        with args.github_summary.open("a", encoding="utf-8") as summary:
            summary.write(markdown(plan))
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
