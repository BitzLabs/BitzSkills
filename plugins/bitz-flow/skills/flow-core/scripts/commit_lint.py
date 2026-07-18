#!/usr/bin/env python3
"""コミットメッセージを Conventional Commits 規約に照らして検査する（読み取り専用）。

flow-core スキルの「コミット規約」の決定的な検査部分を担う。
スキル本文を読み込まなくても単体実行できる（Python 標準ライブラリのみ）。
実行する git コマンドは参照系（rev-list / log）のみで、履歴を書き換えない。

入力（いずれか1つを必須・排他）:
  --message "<text>"     直接メッセージ文字列を渡す
  --file <path>          ファイルから読む（- で標準入力）
  --range <rev-range>    git rev-list --no-merges <range> の各コミットを検査する

検査内容:
  - タイトル: Conventional Commits 形式
    ^(feat|fix|docs|refactor|test|chore)(\\([^)]+\\))?(!)?: .+$
  - --require-task-id: タイトルに [<ID>]（例 [TSK-042] [#123]）を要求する
  - --require-implements: 本文に "Implements: <参照>" フッター行を要求する

出力:
  違反ごとに "NG <sha または -> <理由>" を1行ずつ、全適合なら "OK <検査件数>"。

使用例:
  python3 commit_lint.py --message "feat(auth): [#123] トークン更新を実装"
  git log -1 --format=%B | python3 commit_lint.py --file -
  python3 commit_lint.py --range origin/main..HEAD --require-implements

終了コード: 適合 0 / 違反 1 / 使用法エラー 2
"""
import argparse
import re
import subprocess
import sys

# 終了コード定数
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

TITLE_RE = re.compile(r"^(feat|fix|docs|refactor|test|chore)(\([^)]+\))?(!)?: .+$")
TASK_ID_RE = re.compile(r"\[[^\]]+\]")
IMPLEMENTS_RE = re.compile(r"^Implements: \S+", re.MULTILINE)


def check_message(message: str, require_task_id: bool, require_implements: bool) -> list[str]:
    """1コミット分のメッセージを検査し、違反理由のリストを返す（空なら適合）。"""
    reasons: list[str] = []
    lines = message.splitlines()
    title = lines[0].strip() if lines else ""

    if not TITLE_RE.match(title):
        reasons.append("Conventional Commits タイトル形式に不適合: " + repr(title))
    if require_task_id and not TASK_ID_RE.search(title):
        reasons.append("タイトルに作業 ID [<ID>] がありません")
    if require_implements and not IMPLEMENTS_RE.search(message):
        reasons.append("本文に 'Implements: <参照>' フッターがありません")
    return reasons


def read_stdin_or_file(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def collect_from_range(rev_range: str) -> list[tuple[str, str]]:
    """rev-range から (短縮 sha, メッセージ本文) のリストを取得する（マージコミット除外）。"""
    proc = subprocess.run(
        ["git", "rev-list", "--no-merges", rev_range],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write("エラー: git rev-list に失敗しました: " + proc.stderr.strip() + "\n")
        sys.exit(EXIT_USAGE)
    shas = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    commits: list[tuple[str, str]] = []
    for sha in shas:
        log = subprocess.run(
            ["git", "log", "-1", "--format=%B", sha],
            capture_output=True,
            text=True,
        )
        if log.returncode != 0:
            sys.stderr.write("エラー: git log に失敗しました: " + log.stderr.strip() + "\n")
            sys.exit(EXIT_USAGE)
        commits.append((sha[:7], log.stdout.rstrip("\n")))
    return commits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="commit_lint.py",
        description="コミットメッセージを Conventional Commits 規約で検査する（読み取り専用）。",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--message", help="検査するメッセージ文字列")
    group.add_argument("--file", help="メッセージを読むファイル（- で標準入力）")
    group.add_argument("--range", dest="rev_range", help="検査する git rev-range")
    parser.add_argument("--require-task-id", action="store_true", help="タイトルに作業 ID を要求する")
    parser.add_argument(
        "--require-implements", action="store_true", help="本文に Implements: フッターを要求する"
    )
    args = parser.parse_args(argv)

    provided = [args.message is not None, args.file is not None, args.rev_range is not None]
    if sum(provided) != 1:
        sys.stderr.write("エラー: --message / --file / --range のいずれか1つを指定してください。\n")
        return EXIT_USAGE

    # (表示用ラベル, メッセージ) の列を作る
    if args.message is not None:
        commits = [("-", args.message)]
    elif args.file is not None:
        commits = [("-", read_stdin_or_file(args.file))]
    else:
        commits = collect_from_range(args.rev_range)

    violations = 0
    for label, message in commits:
        for reason in check_message(message, args.require_task_id, args.require_implements):
            violations += 1
            print("NG " + label + " " + reason)

    if violations:
        return EXIT_VIOLATION
    print("OK " + str(len(commits)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
