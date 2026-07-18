#!/usr/bin/env python3
"""PR 本文の雛形（目的 / 変更点 / 検証結果）を生成する。

flow-pr スキルの「PR 本文には目的 / 変更点 / 検証結果を含める」規定を、
決定的な雛形生成として担う。外部コマンドは一切実行しない純粋な文字列生成で、
スキル本文を読み込まなくても単体実行できる（Python 標準ライブラリのみ）。

引数:
  --title <t>            雛形冒頭に suggested title をコメントとして出す（任意）
  --purpose <text>       「## 目的」節の本文
  --change <text>        「## 変更点」の箇条書き（複数回指定可）
  --verification <text>  「## 検証結果」の箇条書き（複数回指定可）
  --closes <N>           末尾の Closes 行に載せる Issue 番号（複数回指定可）
  --implements <ID>      末尾の Implements 行に載せる要件 ID（複数回指定可）
  --output <file>        出力先ファイル（省略時は標準出力）

未指定の節は TODO プレースホルダを出す。Closes / Implements は指定があるときだけ出す。

使用例:
  python3 pr_helper.py --purpose "認証を実装" --change "トークン更新" --verification "pytest green"
  python3 pr_helper.py --title "feat(auth): 実装" --closes 123 --implements CORE-FR-015 --output PR.md

終了コード: 成功 0 / 使用法エラー 2
"""
import argparse
import sys

TODO = "TODO"


def build_body(
    title: str | None,
    purpose: str | None,
    changes: list[str],
    verifications: list[str],
    closes: list[int],
    implements: list[str],
) -> str:
    """PR 本文 Markdown を組み立てて返す。"""
    parts: list[str] = []

    if title:
        parts.append("<!-- suggested title: " + title + " -->")
        parts.append("")

    parts.append("## 目的")
    parts.append(purpose if purpose else TODO)
    parts.append("")

    parts.append("## 変更点")
    if changes:
        parts.extend("- " + c for c in changes)
    else:
        parts.append(TODO)
    parts.append("")

    parts.append("## 検証結果")
    if verifications:
        parts.extend("- " + v for v in verifications)
    else:
        parts.append(TODO)

    footer: list[str] = []
    if closes:
        footer.append("Closes " + ", ".join("#" + str(n) for n in closes))
    if implements:
        footer.append("Implements: " + ", ".join(implements))
    if footer:
        parts.append("")
        parts.extend(footer)

    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pr_helper.py",
        description="PR 本文の雛形（目的 / 変更点 / 検証結果）を生成する。外部コマンドは実行しない。",
    )
    parser.add_argument("--title", default=None, help="suggested title（冒頭コメントに出す）")
    parser.add_argument("--purpose", default=None, help="「## 目的」節の本文")
    parser.add_argument("--change", action="append", default=[], help="「## 変更点」の項目（複数可）")
    parser.add_argument(
        "--verification", action="append", default=[], help="「## 検証結果」の項目（複数可）"
    )
    parser.add_argument("--closes", action="append", type=int, default=[], help="Closes する Issue 番号（複数可）")
    parser.add_argument("--implements", action="append", default=[], help="Implements する要件 ID（複数可）")
    parser.add_argument("--output", default=None, help="出力先ファイル（省略時は標準出力）")
    args = parser.parse_args(argv)

    body = build_body(
        args.title,
        args.purpose,
        args.change,
        args.verification,
        args.closes,
        args.implements,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(body)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
