#!/usr/bin/env python3
"""M1 milestone budget manifest の内部整合を検査する。

FLW-FR-012 が要求する「milestone 開始時の予算・実績・出口・縮退境界の記録」が、
FLW-DSN-014 の総枠と FLW-DSN-015 の PR 区分の双方に対して破れていないことを機械判定する。
散文の予算は機械から見えないため、区分配賦の合計が総枠と一致することをここで固定する。
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).with_name("run-manifest-m1-entry.json")

REQUIRED_SECTIONS = (
    "totals",
    "allocations",
    "partition_totals",
    "m0_actuals",
    "exit_criteria",
    "degraded_shipping_boundary",
    "stop_rules",
)


def _check(manifest: dict) -> list[str]:
    """整合違反を並べて返す（空なら PASS）。"""
    problems: list[str] = []

    missing = [s for s in REQUIRED_SECTIONS if s not in manifest]
    if missing:
        problems.append(f"必須区画が欠落: {', '.join(missing)}")
        return problems

    totals = manifest["totals"]
    allocations = manifest["allocations"]

    pr_sum = sum(a["pr"] for a in allocations)
    session_sum = sum(a["sessions"] for a in allocations)

    if pr_sum != totals["pr_budget"]:
        problems.append(f"区分配賦のPR合計 {pr_sum} が総枠 {totals['pr_budget']} と一致しない")
    if session_sum != totals["session_budget"]:
        problems.append(
            f"区分配賦のsession合計 {session_sum} が総枠 {totals['session_budget']} と一致しない"
        )

    split_sum = totals["implementation_pr"] + totals["verification_pr"]
    if split_sum != totals["pr_budget"]:
        problems.append(
            f"実装予算 {totals['implementation_pr']} + 検証予算 {totals['verification_pr']} "
            f"が総枠 {totals['pr_budget']} と一致しない"
        )

    # partition_totals は allocations からの導出値であり、二重定義を許さない。
    derived: dict[str, dict[str, int]] = {}
    for a in allocations:
        bucket = derived.setdefault(a["partition"], {"pr": 0, "sessions": 0})
        bucket["pr"] += a["pr"]
        bucket["sessions"] += a["sessions"]
    if derived != manifest["partition_totals"]:
        problems.append("partition_totals が allocations からの導出値と一致しない")

    order = manifest.get("dependency", {}).get("order", [])
    if order and order != [a["id"] for a in allocations]:
        problems.append("dependency.order が allocations の並びと一致しない")

    blocking = [a["id"] for a in allocations if a.get("blocking_gate")]
    if blocking != ["M1-2"]:
        problems.append(f"blocking Go/No-Go は M1-2 のみのはずだが {blocking} が宣言されている")

    roi = [a["id"] for a in allocations if a.get("roi_gated")]
    if roi != ["M1-5"]:
        problems.append(f"ROI ゲート対象は M1-5 のみのはずだが {roi} が宣言されている")

    consumed = manifest.get("consumption", {})
    if consumed.get("pr_used", 0) > totals["pr_budget"]:
        problems.append("実績PR数が総枠を超過している — 人間へ再提示すること")
    if consumed.get("sessions_used", 0) > totals["session_budget"]:
        problems.append("実績session数が総枠を超過している — 人間へ再提示すること")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M1 milestone budget manifest の整合検査")
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(DEFAULT_MANIFEST),
        help="検査する manifest（既定: run-manifest-m1-entry.json）",
    )
    args = parser.parse_args(argv)

    path = Path(args.manifest)
    if not path.is_file():
        print(f"FAIL: manifest が存在しない: {path}", file=sys.stderr)
        return 1

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: JSON として妥当でない: {exc}", file=sys.stderr)
        return 1

    problems = _check(manifest)
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1

    totals = manifest["totals"]
    print(
        f"PASS: {manifest['milestone']} budget 整合 — "
        f"{totals['pr_budget']} PR / {totals['session_budget']} session、"
        f"区分 {len(manifest['allocations'])} 件"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
