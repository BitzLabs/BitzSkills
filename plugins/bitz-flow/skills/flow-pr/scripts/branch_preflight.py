#!/usr/bin/env python3
"""FLW-FR-001: Draft PR 前にブランチ再利用事故を検出する。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


READY = 0
INDETERMINATE = 2
REUSE_BLOCKED = 3
JSON_FIELDS = {
    "occurred_at_utc",
    "decision",
    "exit_code",
    "branch",
    "default_branch",
    "merged_prs",
    "open_prs",
    "behind",
    "ahead",
    "has_diff",
    "failed_check",
    "message",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_command(
    command: Sequence[str], *, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), cwd=cwd, timeout=timeout, capture_output=True, text=True
    )


def report_base(branch: str, default_branch: str) -> dict:
    return {
        "occurred_at_utc": utc_now(),
        "decision": "INDETERMINATE",
        "exit_code": INDETERMINATE,
        "branch": branch,
        "default_branch": default_branch,
        "merged_prs": [],
        "open_prs": [],
        "behind": None,
        "ahead": None,
        "has_diff": None,
        "failed_check": None,
        "message": "検査を完了できませんでした。人間が状態を確認してください。",
    }


def finish(report: dict, decision: str, code: int, check: str | None, message: str) -> dict:
    report.update(
        decision=decision,
        exit_code=code,
        failed_check=check,
        message=message,
    )
    return {key: report[key] for key in JSON_FIELDS}


def decode_prs(result: subprocess.CompletedProcess[str]) -> list[dict]:
    if result.returncode != 0:
        raise RuntimeError("gh-query-failed")
    value = json.loads(result.stdout)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("gh-json-invalid")
    return value


def run_preflight(
    *,
    repository: Path,
    branch: str,
    default_branch: str,
    timeout_seconds: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
) -> dict:
    """検査結果を許可リスト形式で返す。外部コマンドの生出力は返さない。"""
    report = report_base(branch, default_branch)
    repository = Path(repository).resolve()

    try:
        for candidate in (branch, default_branch):
            checked = runner(
                ["git", "check-ref-format", "--branch", candidate],
                cwd=repository,
                timeout=timeout_seconds,
            )
            if checked.returncode != 0:
                return finish(
                    report,
                    "INDETERMINATE",
                    INDETERMINATE,
                    "ref-format",
                    "ブランチ名が Git ref として不正です。",
                )
        if branch == default_branch:
            return finish(
                report,
                "REUSE_BLOCKED",
                REUSE_BLOCKED,
                "default-branch",
                "デフォルトブランチ自体は作業ブランチとして使用できません。",
            )

        fetched = runner(
            ["git", "fetch", "origin"], cwd=repository, timeout=timeout_seconds
        )
        if fetched.returncode != 0:
            raise RuntimeError("fetch-failed")

        merged_result = runner(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "merged",
                "--json",
                "number,mergedAt,headRefOid",
            ],
            cwd=repository,
            timeout=timeout_seconds,
        )
        merged = decode_prs(merged_result)
        report["merged_prs"] = [item.get("number") for item in merged if isinstance(item.get("number"), int)]
        if merged:
            return finish(
                report,
                "REUSE_BLOCKED",
                REUSE_BLOCKED,
                "merged-pr",
                "同じ head の merged PR が存在します。最新のデフォルトブランチから新しいブランチを作成してください。",
            )

        counts = runner(
            [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                f"origin/{default_branch}...{branch}",
            ],
            cwd=repository,
            timeout=timeout_seconds,
        )
        if counts.returncode != 0:
            raise RuntimeError("rev-list-failed")
        parts = counts.stdout.strip().split()
        if len(parts) != 2:
            raise ValueError("rev-list-invalid")
        report["behind"], report["ahead"] = int(parts[0]), int(parts[1])

        diff = runner(
            ["git", "diff", "--quiet", f"origin/{default_branch}..{branch}"],
            cwd=repository,
            timeout=timeout_seconds,
        )
        if diff.returncode not in (0, 1):
            raise RuntimeError("diff-failed")
        report["has_diff"] = diff.returncode == 1
        if not report["has_diff"]:
            return finish(
                report,
                "REUSE_BLOCKED",
                REUSE_BLOCKED,
                "tree-diff",
                "デフォルトブランチとの差分がありません。空の PR は作成しません。",
            )

        open_result = runner(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number,baseRefName,mergeable,mergeStateStatus",
            ],
            cwd=repository,
            timeout=timeout_seconds,
        )
        opened = decode_prs(open_result)
        report["open_prs"] = [
            {
                "number": item.get("number"),
                "base": item.get("baseRefName"),
                "mergeable": item.get("mergeable"),
                "merge_state": item.get("mergeStateStatus"),
            }
            for item in opened
        ]
        for item in report["open_prs"]:
            if item["base"] != default_branch or item["mergeable"] == "CONFLICTING" or item["merge_state"] == "DIRTY":
                return finish(
                    report,
                    "REUSE_BLOCKED",
                    REUSE_BLOCKED,
                    "open-pr",
                    "open PR の base または競合状態が通常フローの前提を満たしません。",
                )
            if item["mergeable"] in (None, "UNKNOWN") or item["merge_state"] in (None, "UNKNOWN"):
                return finish(
                    report,
                    "INDETERMINATE",
                    INDETERMINATE,
                    "mergeability",
                    "GitHub の mergeability が未確定です。時間を置いて再検査してください。",
                )

        return finish(
            report,
            "READY",
            READY,
            None,
            "ブランチは通常の Draft PR フローを続行できます。",
        )
    except subprocess.TimeoutExpired:
        return finish(
            report,
            "INDETERMINATE",
            INDETERMINATE,
            "command-timeout",
            "外部コマンドが timeout しました。副作用を伴う操作は行わず停止します。",
        )
    except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError):
        return finish(
            report,
            "INDETERMINATE",
            INDETERMINATE,
            "command-or-data",
            "git / gh の検査または応答解析に失敗しました。人間が状態を確認してください。",
        )


def bounded_timeout(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 300:
        raise argparse.ArgumentTypeError("timeout は 1〜300 秒で指定してください")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft PR 前の branch preflight")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--timeout-seconds", type=bounded_timeout, default=30)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    report = run_preflight(
        repository=args.repo,
        branch=args.branch,
        default_branch=args.default_branch,
        timeout_seconds=args.timeout_seconds,
    )
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{report['decision']}: {report['message']}")
        print(
            f"branch={report['branch']} default={report['default_branch']} "
            f"behind={report['behind']} ahead={report['ahead']}"
        )
    return int(report["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
