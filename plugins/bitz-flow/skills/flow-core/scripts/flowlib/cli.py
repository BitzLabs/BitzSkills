"""単一 dispatcher の CLI 層（FLW-DSN-003 公開入口）。

入力を canonical 化し、adapter から事実を取得し、renderer へ渡す。
状態変更は行わない（M0 は read-only の3 operation のみ）。

未対応の domain / action は ``UNSUPPORTED``（exit 8）で停止し、生の ``git`` /
``gh`` コマンドを代替案として出力しない（references/operation-catalog.md）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from typing import Any, Sequence

from . import __version__, git_read, result as R

# M0 で公開する operation。ここに無い組み合わせは UNSUPPORTED。
M0_OPERATIONS = {
    ("repo", "inspect"),
    ("git", "status"),
    ("git", "diff-summary"),
}

# 公開予定だが当該 milestone まで未対応の operation（UNSUPPORTED の理由付けに使う）。
KNOWN_DOMAINS = {"repo", "git", "worktree", "issue", "pr", "release"}

DEFAULT_ITEM_LIMIT = 50


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Parser(argparse.ArgumentParser):
    """引数エラーでも公開契約に沿った result を返す。

    argparse 既定の exit code 2 は output-contract の ``INVALID_INPUT`` と一致する。
    """

    def error(self, message: str) -> None:  # noqa: D401 - argparse の契約に合わせる
        fmt = "json" if "--format=json" in sys.argv or _format_from_argv() == "json" else "compact"
        _emit(
            _simple_result(
                operation="flow.invalid-input",
                code="INVALID_INPUT",
                repo=os.getcwd(),
                summary="引数を解釈できない",
                stage="validate",
            ),
            fmt,
        )
        raise SystemExit(2)


def _format_from_argv() -> str:
    argv = sys.argv
    for index, token in enumerate(argv):
        if token == "--format" and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith("--format="):
            return token.split("=", 1)[1]
    return "compact"


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="flow.py",
        description="bitz-flow の唯一の公開実行入口（M0: read-only の3 operation）。",
        epilog="未対応の operation は UNSUPPORTED で停止する。生コマンドの代替案は提示しない。",
    )
    parser.add_argument("domain", help="操作ドメイン（repo / git / worktree / issue / pr / release）")
    parser.add_argument("action", help="操作アクション（例: inspect / status / diff-summary）")
    parser.add_argument("--repo", help="対象リポジトリのパス（省略時は current directory から解決）")
    parser.add_argument(
        "--format", choices=("compact", "json"), default="compact", help="出力形式（既定 compact）"
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=None, help="read の timeout 秒（1〜300、既定 30）"
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        help="git diff-summary の比較元（既定 HEAD。index と比較するなら --base index）",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_ITEM_LIMIT, help="items の表示上限（既定 50）"
    )
    parser.add_argument("--snapshot", help="期待する snapshot。一致しなければ STALE を返す")
    # M0 は read-only。状態変更系の引数は受理して UNSUPPORTED を返す（黙殺しない）。
    parser.add_argument("--apply", action="store_true", help="状態変更の実行（M1 以降）")
    parser.add_argument("--confirm", help="plan が返した operation_id（M1 以降）")
    parser.add_argument("--approval-ref", dest="approval_ref", help="外部裁定への参照（M1 以降）")
    return parser


# --- result の組み立て -------------------------------------------------------


def _simple_result(
    *,
    operation: str,
    code: str,
    repo: str,
    summary: str,
    cause: str | None = None,
    stage: str = "inspect",
    next_actions: Sequence[dict] = (),
) -> dict[str, Any]:
    data = R.empty_data()
    data["cause"] = cause
    now = _now()
    return R.build_result(
        operation=operation,
        code=code,
        repo=repo,
        tool_version=__version__,
        started_at=now,
        finished_at=now,
        summary=summary,
        data=data,
        stage=stage,
        next_actions=next_actions,
    )


def _emit(result: dict[str, Any], fmt: str, view: R.CompactView | None = None) -> int:
    print(R.render(result, fmt, view))
    return result["exit_code"]


def _short_sha(sha: str | None) -> str | None:
    return sha[:7] if sha else None


# --- operation 実装 ----------------------------------------------------------


def _op_repo_inspect(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    facts, failure = git_read.inspect(root, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("repo.inspect", root, failure, started), R.CompactView()

    values = facts.values
    snapshot = R.snapshot_of([values["head"], values["branch"], values["upstream"], values["dirty"]])
    data = R.empty_data()
    data["target"] = {"repo_root": root}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["repo root", "HEAD", "branch", "upstream", "remote identity"]
    data["repository"] = values

    result = R.build_result(
        operation="repo.inspect",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=_inspect_summary(values),
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        next_actions=[R.next_action("git", "status", snapshot=snapshot)],
    )
    view = R.CompactView(
        tokens={
            "branch": values["branch"] or ("detached" if values["head"]["detached"] else None),
            "head": _short_sha(values["head"]["sha"]),
            "upstream": values["upstream"],
            "dirty": values["dirty"],
            "remotes": len(values["remotes"]),
        },
        normal=[f"remote {r['name']} {r['host'] or '-'}/{r['owner'] or '-'}/{r['repo'] or '-'}"
                for r in values["remotes"]],
    )
    return result, view


def _inspect_summary(values: dict) -> str:
    branch = values["branch"] or "detached HEAD"
    state = "dirty" if values["dirty"] else "clean"
    return f"{branch} が {state}"


def _op_git_status(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    facts, failure = git_read.status(root, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("git.status", root, failure, started), R.CompactView()

    values = facts.values
    branch, counts, items = values["branch"], values["counts"], values["items"]
    snapshot = R.snapshot_of([branch, items])
    shown, page, truncated = R.paginate(items, args.limit, snapshot)

    data = R.empty_data()
    data["target"] = {"repo_root": root}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["branch", "upstream", "ahead/behind", "変更種別ごとの件数"]
    data["branch"] = branch
    data["counts"] = counts
    data["items"] = shown
    data["page"] = page

    changed_total = counts["staged"] + counts["unstaged"] + counts["untracked"] + counts["conflicted"]
    # base を明示して渡す。省略すると呼出側が「直前のコミットからの差分」を意図しながら
    # index 比較を呼び、rename を取りこぼす（FLW-DSN-010 の next action 改善）。
    next_actions = [R.next_action("git", "diff-summary", base="HEAD", snapshot=snapshot)]
    if truncated:
        next_actions.insert(0, R.next_action("git", "status", limit=page["total"], snapshot=snapshot))

    result = R.build_result(
        operation="git.status",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=f"{changed_total} 件の変更",
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        truncated=truncated,
        next_actions=next_actions,
    )
    conflicted = [f"{item['xy']} {item['path']}" for item in shown if item["state"] == "conflicted"]
    others = [
        f"{item['xy']} {item['path']}"
        + (f" <- {item['orig_path']}" if item["orig_path"] else "")
        for item in shown
        if item["state"] != "conflicted"
    ]
    view = R.CompactView(
        tokens={
            "branch": branch["name"] or ("detached" if branch["detached"] else None),
            "changed": changed_total,
            "ahead": branch["ahead"],
            "behind": branch["behind"],
        },
        blocking=conflicted,
        changed=others,
    )
    return result, view


def _op_git_diff_summary(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    # 既定は HEAD（「直前のコミットからの変更量」が既定の意図）。生 git の `git diff` は
    # index 比較だが、dispatcher はエージェントの意図側に既定を寄せる。index 比較は
    # `--base index` で明示する（git_read は base=None を index 比較として扱う）。
    base = None if args.base == "index" else args.base
    facts, failure = git_read.diff_summary(root, base=base, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("git.diff-summary", root, failure, started), R.CompactView()

    values = facts.values
    totals, items = values["totals"], values["items"]
    snapshot = R.snapshot_of([values["range"], items])
    shown, page, truncated = R.paginate(items, args.limit, snapshot)

    data = R.empty_data()
    data["target"] = {"repo_root": root, "range": values["range"]}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["変更件数", "path", "変更種別", "追加削除行数", "binary 判定"]
    data["totals"] = totals
    data["items"] = shown
    data["page"] = page

    next_actions = []
    if truncated:
        next_actions.append(
            R.next_action(
                "git", "diff-summary", base=args.base, limit=page["total"], snapshot=snapshot
            )
        )

    result = R.build_result(
        operation="git.diff-summary",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=f"{totals['files']} files changed",
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        truncated=truncated,
        next_actions=next_actions,
    )
    lines = []
    for item in shown:
        counts = "binary" if item["binary"] else f"+{item['added']} -{item['deleted']}"
        rename = f" <- {item['orig_path']}" if item["orig_path"] else ""
        lines.append(f"{item['kind'][:1].upper()} {item['path']} {counts}{rename}")
    view = R.CompactView(
        tokens={
            "base": values["range"]["base"],
            "files": totals["files"],
            "added": totals["added"],
            "deleted": totals["deleted"],
            "binary": totals["binary"],
        },
        changed=lines,
    )
    return result, view


def _failure_result(operation: str, repo: str, failure, started: str) -> dict:
    """adapter の失敗を公開 result へ写す（cause と stage だけを載せる）。"""
    code = "UNAVAILABLE"
    if failure.cause in ("not-repository", "invalid-path", "invalid-ref"):
        code = "INVALID_INPUT"
    data = R.empty_data()
    data["cause"] = failure.cause
    return R.build_result(
        operation=operation,
        code=code,
        repo=repo,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary="操作を完了できない",
        data=data,
        stage=failure.stage,
    )


_HANDLERS = {
    ("repo", "inspect"): _op_repo_inspect,
    ("git", "status"): _op_git_status,
    ("git", "diff-summary"): _op_git_diff_summary,
}


# --- dispatcher --------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = _now()
    cwd = os.getcwd()
    operation = f"{args.domain}.{args.action}"

    if args.apply or args.confirm or args.approval_ref:
        return _emit(
            _simple_result(
                operation=operation,
                code="UNSUPPORTED",
                repo=cwd,
                summary="M0 は read-only であり状態変更を受け付けない",
                stage="validate",
            ),
            args.format,
        )

    handler = _HANDLERS.get((args.domain, args.action))
    if handler is None:
        summary = (
            "この operation は現在の milestone では未対応"
            if args.domain in KNOWN_DOMAINS
            else "未知の domain"
        )
        return _emit(
            _simple_result(
                operation=operation,
                code="UNSUPPORTED",
                repo=cwd,
                summary=summary,
                stage="validate",
            ),
            args.format,
        )

    root, failure = git_read.resolve_repo_root(args.repo)
    if failure:
        return _emit(
            _failure_result(operation, os.path.abspath(args.repo or cwd), failure, started),
            args.format,
        )

    result, view = handler(root, args, started)

    # 呼出時の --snapshot と再計算値が違えば STALE（FLW-DSN-005）。
    if args.snapshot and result["ok"] and not R.digest_matches(result.get("snapshot"), args.snapshot):
        stale = _simple_result(
            operation=operation,
            code="STALE",
            repo=root,
            summary="snapshot が要求時点から変化した",
            cause="snapshot-mismatch",
            stage="validate",
            next_actions=[R.next_action(args.domain, args.action)],
        )
        return _emit(stale, args.format)

    return _emit(result, args.format, view)
