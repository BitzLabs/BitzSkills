#!/usr/bin/env python3
"""worktree の定型操作（作成 / 一覧 / 後片付け / 失敗時破棄）を決定的に行う。

flow-worktree スキルの「判断」に対し、本スクリプトは「決定的な操作」を担う。
スキル本文を読み込まなくても単体実行できる（Python 標準ライブラリのみ）。

サブコマンド:
  add <work-id> --branch <name> [--base origin/main] [--repo <path>]
      worktree を <repoの親>/<repo名>-wt/<work-id>/ に作成する。
      base が origin/ で始まる場合のみ先に fetch する。
  list [--repo <path>]
      git worktree list を表示する（読み取り専用。dry-run 対象外）。
  cleanup <work-id> --branch <name> [--delete-remote] [--repo <path>]
      マージ後の後片付け（worktree remove + branch -d、任意でリモート削除）。
      --squash-pr <number> 指定時は GitHub の MERGED/head SHA 証跡を検証し、
      冪等なローカル cleanup と remote 削除候補報告を行う（remote は削除しない）。
  discard <work-id> --branch <name> [--repo <path>]
      失敗時破棄（worktree remove --force + branch -D）。

安全設計:
  - 状態変更系（add / cleanup / discard）は既定で dry-run。実行するコマンド列を
    "DRY-RUN: git ..." として表示するだけで、副作用を起こさない。
  - 実際に実行するには --execute を付ける。
  - 破棄・削除を伴う cleanup / discard は --execute でも --yes が無ければ実行しない。
  - ガードレール禁止操作（ハード巻き戻し・強制 push・作業ツリー一括削除・特権昇格）は
    いかなる経路でも呼び出さない。

使用例:
  python3 worktree_ops.py add 123 --branch feat/123-topic --base origin/main --repo .
  python3 worktree_ops.py add 123 --branch feat/123-topic --base origin/main --repo . --execute
  python3 worktree_ops.py list --repo .
  python3 worktree_ops.py cleanup 123 --branch feat/123-topic --repo . --execute --yes
  python3 worktree_ops.py discard 123 --branch feat/123-topic --repo . --execute --yes

終了コード: 成功 0 / git 失敗 1 / 使用法・確認不足・証跡不明 2
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# 終了コード定数
EXIT_OK = 0
EXIT_GIT_FAILED = 1
EXIT_USAGE = 2
EXIT_INDETERMINATE = 2

SQUASH_JSON_FIELDS = {
    "occurred_at_utc",
    "decision",
    "exit_code",
    "pr_number",
    "branch",
    "pr_head_sha",
    "merge_commit",
    "default_branch",
    "cleanup_state",
    "checks",
    "completed",
    "skipped",
    "remaining",
    "remote_status",
    "remote_candidate",
    "actor",
    "failed_check",
    "message",
}


def resolve_repo(repo_arg: str | None) -> Path:
    """--repo 省略時は git rev-parse --show-toplevel でリポジトリルートを解決する。"""
    base = Path(repo_arg) if repo_arg else Path.cwd()
    proc = subprocess.run(
        ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write("エラー: git リポジトリを解決できません: " + proc.stderr.strip() + "\n")
        sys.exit(EXIT_GIT_FAILED)
    return Path(proc.stdout.strip())


def worktree_path(repo: Path, work_id: str) -> Path:
    """<repoの親>/<repo名>-wt/<work-id>/ を返す。"""
    return repo.parent / (repo.name + "-wt") / work_id


def show_dry_run(cmds: list[list[str]]) -> None:
    """実行予定のコマンド列を DRY-RUN 行として表示する（副作用なし）。"""
    for cmd in cmds:
        print("DRY-RUN: " + " ".join(cmd))
    print("（dry-run。実際に実行するには --execute を付けてください）")


def execute(cmds: list[list[str]]) -> int:
    """コマンド列を順に実行する。1つでも失敗したらそこで打ち切る。"""
    for cmd in cmds:
        print("$ " + " ".join(cmd))
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            sys.stderr.write(
                "エラー: コマンドが失敗しました（終了コード "
                + str(proc.returncode)
                + "）。以降は中断します。人間の判断に委ねてください。\n"
            )
            return EXIT_GIT_FAILED
    return EXIT_OK


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_timed(command: list[str], *, timeout: int, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=cwd, timeout=timeout, capture_output=True, text=True
    )


def squash_report(
    *, branch: str, default_branch: str, pr_number: int, actor: str | None
) -> dict:
    return {
        "occurred_at_utc": utc_now(),
        "decision": "INDETERMINATE",
        "exit_code": EXIT_INDETERMINATE,
        "pr_number": pr_number,
        "branch": branch,
        "pr_head_sha": None,
        "merge_commit": None,
        "default_branch": default_branch,
        "cleanup_state": "invalid",
        "checks": [],
        "completed": [],
        "skipped": [],
        "remaining": [],
        "remote_status": "unknown",
        "remote_candidate": None,
        "actor": actor,
        "failed_check": None,
        "message": "証跡を確認できないため停止しました。",
    }


def finish_squash(
    report: dict, *, code: int, decision: str, failed_check: str | None, message: str
) -> tuple[int, dict]:
    report.update(
        exit_code=code,
        decision=decision,
        failed_check=failed_check,
        message=message,
    )
    return code, {key: report[key] for key in SQUASH_JSON_FIELDS}


def parse_worktrees(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines() + [""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records


def parse_remote_oid(text: str, branch: str) -> str | None:
    expected_ref = f"refs/heads/{branch}"
    matches = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == expected_ref:
            matches.append(parts[0])
    if len(matches) > 1:
        raise ValueError("remote-ref-ambiguous")
    return matches[0] if matches else None


def guarded_squash_cleanup(
    *,
    repo: Path,
    work_id: str,
    branch: str,
    pr_number: int,
    default_branch: str,
    timeout_seconds: int,
    actor: str | None,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> tuple[int, dict]:
    """MERGED 証跡と期待 SHA を検証してローカル cleanup を前進再開する。"""
    repo = Path(repo).resolve()
    report = squash_report(
        branch=branch,
        default_branch=default_branch,
        pr_number=pr_number,
        actor=actor,
    )

    if (
        not work_id
        or work_id in {".", ".."}
        or Path(work_id).name != work_id
        or "/" in work_id
        or "\\" in work_id
    ):
        return finish_squash(
            report,
            code=EXIT_INDETERMINATE,
            decision="INDETERMINATE",
            failed_check="work-id",
            message="work-id は単一の安全なパス要素で指定してください。",
        )
    if actor is not None and (len(actor) > 64 or any(ord(ch) < 32 for ch in actor)):
        return finish_squash(
            report,
            code=EXIT_INDETERMINATE,
            decision="INDETERMINATE",
            failed_check="actor",
            message="actor label が不正です。",
        )

    target = worktree_path(repo, work_id).resolve()
    worktree_root = (repo.parent / f"{repo.name}-wt").resolve()
    if target.parent != worktree_root:
        return finish_squash(
            report,
            code=EXIT_INDETERMINATE,
            decision="INDETERMINATE",
            failed_check="worktree-boundary",
            message="worktree path が管理境界の外です。",
        )

    if runner is None:
        def invoke(command: list[str], *, timeout: int) -> subprocess.CompletedProcess:
            return run_timed(command, timeout=timeout, cwd=repo)
    else:
        invoke = runner

    git_prefix = ["git", "-C", str(repo)]

    def call(command: list[str]) -> subprocess.CompletedProcess:
        return invoke(command, timeout=timeout_seconds)

    def require_ok(command: list[str], check: str) -> subprocess.CompletedProcess:
        result = call(command)
        if result.returncode != 0:
            raise RuntimeError(check)
        report["checks"].append(check)
        return result

    try:
        for candidate in (branch, default_branch):
            require_ok(git_prefix + ["check-ref-format", "--branch", candidate], "ref-format")
        if branch == default_branch:
            raise RuntimeError("default-branch-protection")

        worktrees = parse_worktrees(
            require_ok(git_prefix + ["worktree", "list", "--porcelain"], "worktree-list").stdout
        )
        local_result = call(git_prefix + ["rev-parse", "--verify", f"refs/heads/{branch}"])
        local_oid = local_result.stdout.strip() if local_result.returncode == 0 else None
        branch_ref = f"refs/heads/{branch}"
        target_record = next(
            (record for record in worktrees if Path(record.get("worktree", "")).resolve() == target),
            None,
        )
        other_users = [
            record
            for record in worktrees
            if record.get("branch") == branch_ref
            and Path(record.get("worktree", "")).resolve() != target
        ]
        if other_users:
            raise RuntimeError("branch-used-by-other-worktree")
        if target_record is not None:
            if not local_oid or target_record.get("branch") != branch_ref:
                raise RuntimeError("worktree-local-state")
            cleanup_state = "initial"
        elif local_oid:
            cleanup_state = "cleanup-partial"
        else:
            cleanup_state = "local-cleaned"
        report["cleanup_state"] = cleanup_state

        current = require_ok(git_prefix + ["branch", "--show-current"], "current-branch").stdout.strip()
        if current != default_branch:
            raise RuntimeError("current-default-branch")
        status = require_ok(git_prefix + ["status", "--porcelain"], "clean-status")
        if status.stdout.strip():
            raise RuntimeError("dirty-worktree")

        require_ok(git_prefix + ["fetch", "--prune", "origin"], "fetch-prune")
        pr_result = require_ok(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "state,headRefName,headRefOid,mergeCommit",
            ],
            "pr-evidence",
        )
        pr = json.loads(pr_result.stdout)
        if not isinstance(pr, dict):
            raise ValueError("pr-json")
        head_oid = pr.get("headRefOid")
        merge_value = pr.get("mergeCommit")
        merge_oid = merge_value.get("oid") if isinstance(merge_value, dict) else None
        report["pr_head_sha"] = head_oid
        report["merge_commit"] = merge_oid
        if pr.get("state") != "MERGED":
            raise RuntimeError("pr-not-merged")
        if pr.get("headRefName") != branch:
            raise RuntimeError("pr-head-name")
        if not isinstance(head_oid, str) or not head_oid or not isinstance(merge_oid, str) or not merge_oid:
            raise RuntimeError("pr-sha-evidence")
        if target_record is not None and target_record.get("HEAD") != head_oid:
            raise RuntimeError("worktree-head-sha")
        if local_oid is not None and local_oid != head_oid:
            raise RuntimeError("local-head-sha")

        remote_result = require_ok(
            git_prefix + ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            "remote-head-query",
        )
        remote_oid = parse_remote_oid(remote_result.stdout, branch)
        if remote_oid is not None and remote_oid != head_oid:
            raise RuntimeError("remote-head-sha")

        require_ok(
            git_prefix + ["merge-base", "--is-ancestor", merge_oid, f"origin/{default_branch}"],
            "merge-commit-reachable",
        )

        require_ok(git_prefix + ["merge", "--ff-only", f"origin/{default_branch}"], "default-fast-forward")
        report["completed"].append("default-fast-forward")
        if cleanup_state == "initial":
            require_ok(git_prefix + ["worktree", "remove", str(target)], "worktree-remove")
            report["completed"].append("worktree-remove")
        else:
            report["skipped"].append("worktree-remove")

        if cleanup_state != "local-cleaned":
            recheck = require_ok(
                git_prefix + ["rev-parse", "--verify", f"refs/heads/{branch}"],
                "local-head-recheck",
            )
            if recheck.stdout.strip() != head_oid:
                raise RuntimeError("local-head-changed")
            require_ok(git_prefix + ["branch", "-D", branch], "local-branch-delete")
            report["completed"].append("local-branch-delete")
        else:
            report["skipped"].append("local-branch-delete")

        require_ok(git_prefix + ["fetch", "--prune", "origin"], "final-fetch-prune")
        final_remote = require_ok(
            git_prefix + ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            "final-remote-query",
        )
        final_oid = parse_remote_oid(final_remote.stdout, branch)
        if final_oid is None:
            report["remote_status"] = "absent"
            report["skipped"].append("remote-candidate")
        elif final_oid != head_oid:
            report["remaining"] = ["remote-preserved"]
            raise RuntimeError("remote-head-sha")
        else:
            report["remote_status"] = "candidate"
            report["remote_candidate"] = {
                "branch": branch,
                "expected_sha": head_oid,
                "checked_at_utc": utc_now(),
                "warning": "削除操作の直前に remote ref を再照会し、期待 SHA と異なれば中止してください。削除コマンドは生成しません。",
            }
            report["remaining"] = ["remote-candidate-human-decision"]

        return finish_squash(
            report,
            code=EXIT_OK,
            decision="COMPLETED",
            failed_check=None,
            message="証跡付きローカル cleanup が完了しました。remote は自動削除していません。",
        )
    except subprocess.TimeoutExpired:
        check = "command-timeout"
    except json.JSONDecodeError:
        check = "pr-json"
    except ValueError as exc:
        check = str(exc) or "invalid-data"
    except (FileNotFoundError, RuntimeError) as exc:
        check = str(exc) or "command-failed"

    return finish_squash(
        report,
        code=EXIT_INDETERMINATE,
        decision="INDETERMINATE",
        failed_check=check,
        message="証跡検証に失敗したため、安全側で停止しました。存在する ref は削除していません。",
    )


def build_add(repo: Path, work_id: str, branch: str, base: str) -> list[list[str]]:
    cmds: list[list[str]] = []
    if base.startswith("origin/"):
        cmds.append(["git", "-C", str(repo), "fetch", "origin"])
    wt = worktree_path(repo, work_id)
    cmds.append(["git", "-C", str(repo), "worktree", "add", str(wt), "-b", branch, base])
    return cmds


def build_cleanup(repo: Path, work_id: str, branch: str, delete_remote: bool) -> list[list[str]]:
    wt = worktree_path(repo, work_id)
    cmds: list[list[str]] = [
        ["git", "-C", str(repo), "worktree", "remove", str(wt)],
        ["git", "-C", str(repo), "branch", "-d", branch],
    ]
    if delete_remote:
        cmds.append(["git", "-C", str(repo), "push", "origin", "--delete", branch])
    return cmds


def build_discard(repo: Path, work_id: str, branch: str) -> list[list[str]]:
    wt = worktree_path(repo, work_id)
    return [
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
        ["git", "-C", str(repo), "branch", "-D", branch],
    ]


def run_stateful(cmds: list[list[str]], execute_mode: bool, needs_yes: bool, yes: bool) -> int:
    """状態変更系サブコマンドの共通実行フロー（dry-run / 確認 / 実行）。"""
    if not execute_mode:
        show_dry_run(cmds)
        return EXIT_OK
    if needs_yes and not yes:
        sys.stderr.write(
            "エラー: 破棄・削除を伴う操作です。--execute に加えて --yes を明示してください。"
            "何も実行していません。\n"
        )
        return EXIT_USAGE
    return execute(cmds)


def cmd_add(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    cmds = build_add(repo, args.work_id, args.branch, args.base)
    # add は破棄・削除を伴わないため --yes 不要
    return run_stateful(cmds, args.execute, needs_yes=False, yes=True)


def cmd_list(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    # 読み取り専用なので常に実行する
    proc = subprocess.run(["git", "-C", str(repo), "worktree", "list"])
    return EXIT_OK if proc.returncode == 0 else EXIT_GIT_FAILED


def cmd_cleanup(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    if args.squash_pr is not None:
        if args.delete_remote:
            sys.stderr.write(
                "エラー: squash cleanup は remote branch を自動削除しません。"
                "--delete-remote を外してください。\n"
            )
            return EXIT_USAGE
        if not args.execute:
            print(
                "DRY-RUN: squash merged PR の state/head SHA、worktree/local/remote ref、"
                "merge commit 到達性を検証してからローカル cleanup を行います"
            )
            print("（dry-run。証跡照会と状態変更には --execute --yes が必要です）")
            return EXIT_OK
        if not args.yes:
            sys.stderr.write(
                "エラー: squash cleanup には --execute に加えて --yes が必要です。"
                "何も実行していません。\n"
            )
            return EXIT_USAGE
        code, report = guarded_squash_cleanup(
            repo=repo,
            work_id=args.work_id,
            branch=args.branch,
            pr_number=args.squash_pr,
            default_branch=args.default_branch,
            timeout_seconds=args.timeout_seconds,
            actor=args.actor,
        )
        if args.as_json:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{report['decision']}: {report['message']}")
            print(
                f"state={report['cleanup_state']} completed={','.join(report['completed']) or '-'} "
                f"skipped={','.join(report['skipped']) or '-'} remote={report['remote_status']}"
            )
            if report["remote_candidate"]:
                print(report["remote_candidate"]["warning"])
        return code
    cmds = build_cleanup(repo, args.work_id, args.branch, args.delete_remote)
    return run_stateful(cmds, args.execute, needs_yes=True, yes=args.yes)


def cmd_discard(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    cmds = build_discard(repo, args.work_id, args.branch)
    return run_stateful(cmds, args.execute, needs_yes=True, yes=args.yes)


def bounded_timeout(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 300:
        raise argparse.ArgumentTypeError("timeout は 1〜300 秒で指定してください")
    return parsed


def positive_pr_number(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("PR 番号は正の整数で指定してください")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="worktree_ops.py",
        description="worktree の定型操作（作成 / 一覧 / 後片付け / 失敗時破棄）。既定は dry-run。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="worktree とブランチを作成する")
    p_add.add_argument("work_id", help="作業 ID（worktree ディレクトリ名になる）")
    p_add.add_argument("--branch", required=True, help="作成するブランチ名")
    p_add.add_argument("--base", default="origin/main", help="起点（既定: origin/main）")
    p_add.add_argument("--repo", default=None, help="リポジトリのパス（省略時は現在地から解決）")
    p_add.add_argument("--execute", action="store_true", help="実際に実行する（既定は dry-run）")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="worktree 一覧を表示する（読み取り専用）")
    p_list.add_argument("--repo", default=None, help="リポジトリのパス（省略時は現在地から解決）")
    p_list.set_defaults(func=cmd_list)

    p_clean = sub.add_parser("cleanup", help="マージ後の後片付け（worktree remove + branch -d）")
    p_clean.add_argument("work_id", help="作業 ID")
    p_clean.add_argument("--branch", required=True, help="削除するブランチ名")
    p_clean.add_argument("--delete-remote", action="store_true", help="リモート追跡ブランチも削除する")
    p_clean.add_argument(
        "--squash-pr",
        type=positive_pr_number,
        default=None,
        help="squash merge 済み PR 番号（指定時は証跡付き cleanup）",
    )
    p_clean.add_argument("--default-branch", default="main", help="デフォルトブランチ（既定: main）")
    p_clean.add_argument(
        "--timeout-seconds", type=bounded_timeout, default=30, help="外部コマンド timeout（1〜300秒）"
    )
    p_clean.add_argument("--json", action="store_true", dest="as_json", help="許可リスト JSON を出力")
    p_clean.add_argument("--actor", default=None, help="監査用 actor label（資格情報は指定しない）")
    p_clean.add_argument("--repo", default=None, help="リポジトリのパス（省略時は現在地から解決）")
    p_clean.add_argument("--execute", action="store_true", help="実際に実行する（既定は dry-run）")
    p_clean.add_argument("--yes", action="store_true", help="破棄・削除の確認（--execute 時に必須）")
    p_clean.set_defaults(func=cmd_cleanup)

    p_disc = sub.add_parser("discard", help="失敗時破棄（worktree remove --force + branch -D）")
    p_disc.add_argument("work_id", help="作業 ID")
    p_disc.add_argument("--branch", required=True, help="破棄するブランチ名")
    p_disc.add_argument("--repo", default=None, help="リポジトリのパス（省略時は現在地から解決）")
    p_disc.add_argument("--execute", action="store_true", help="実際に実行する（既定は dry-run）")
    p_disc.add_argument("--yes", action="store_true", help="破棄の確認（--execute 時に必須）")
    p_disc.set_defaults(func=cmd_discard)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
