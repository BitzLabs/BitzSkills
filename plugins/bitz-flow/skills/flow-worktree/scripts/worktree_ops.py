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

終了コード: 成功 0 / git 失敗 1 / 使用法・確認不足 2
"""
import argparse
import subprocess
import sys
from pathlib import Path

# 終了コード定数
EXIT_OK = 0
EXIT_GIT_FAILED = 1
EXIT_USAGE = 2


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
    cmds = build_cleanup(repo, args.work_id, args.branch, args.delete_remote)
    return run_stateful(cmds, args.execute, needs_yes=True, yes=args.yes)


def cmd_discard(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    cmds = build_discard(repo, args.work_id, args.branch)
    return run_stateful(cmds, args.execute, needs_yes=True, yes=args.yes)


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
