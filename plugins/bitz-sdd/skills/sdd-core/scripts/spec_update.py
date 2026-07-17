#!/usr/bin/env python3
"""spec_update.py — BitzSDD（sdd-core スキル）の status 遷移ツール（stdlib のみ）

要件 / spec-issue / タスクの status 遷移を行い、sdd-core の権限マトリクス
（references/lifecycle.md）をコードで強制する（CORE-FR-005）。

  - エージェントが実行できる遷移（起票→open / approved→implementing / implementing→verified 等）
    … `--by-human` なしで適用
  - 人間専用遷移（draft→approved / open→accepted / verified→promoted / 任意→deprecated /
    spec-issue の accepted→superseded）… `--by-human` の明示がない限り拒否
  - 権限マトリクスに定義されていない遷移（不正遷移）
    … 誰の権限であっても拒否

遷移適用時は対象ファイルの frontmatter `status` を更新し、`.spec/STATE.md` に
遷移記録（対象 ID・旧→新 status・実行主体）を追記する。

使い方:
  python spec_update.py <workspace> <ID> --to <status> [--by-human] [--actor 名前]
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

# 種別ごとの許可された遷移 → 実行権限（"agent" / "human"）。
# ここに無い (from, to) は不正遷移として誰でも拒否する。
TRANSITIONS = {
    "requirement": {
        ("draft", "approved"): "human",
        ("approved", "implementing"): "agent",
        ("implementing", "approved"): "agent",       # 中断で approved に戻す
        ("implementing", "verified"): "agent",        # 全検証 green（機械判定）
        ("verified", "promoted"): "human",
        ("draft", "deprecated"): "human",
        ("approved", "deprecated"): "human",
        ("implementing", "deprecated"): "human",
        ("verified", "deprecated"): "human",
        ("promoted", "deprecated"): "human",
    },
    "spec-issue": {
        ("open", "accepted"): "human",
        ("open", "rejected"): "human",
        ("accepted", "superseded"): "human",  # 重複解消（SI-SDD-005）。superseded_by: は人間が手動で記入
    },
    "task": {
        ("pending", "implementing"): "agent",
        ("pending", "blocked"): "agent",
        ("implementing", "done"): "agent",
        ("implementing", "blocked"): "agent",
        ("blocked", "implementing"): "agent",
        ("blocked", "pending"): "agent",
    },
}

KIND_DIR = {
    "requirement": "requirements",
    "spec-issue": "spec-issues",
    "task": "tasks",
}


def locate(root: Path, ident: str):
    """ID に対応するファイルを .spec/ 配下から探し (kind, path) を返す。無ければ (None, None)。"""
    for kind, sub in KIND_DIR.items():
        p = root / ".spec" / sub / f"{ident}.md"
        if p.exists():
            return kind, p
    return None, None


def read_status(text: str) -> str:
    """先頭 frontmatter ブロック内の status を返す。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    block = m.group(1) if m else text
    s = re.search(r"^status:\s*(\S+)", block, re.M)
    return s.group(1) if s else ""


def rewrite_status(text: str, new_status: str) -> str:
    """先頭 frontmatter ブロック内の status 行のみを書き換える。"""
    m = re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.S)
    if not m:
        raise ValueError("frontmatter が見つかりません")
    head, block, tail = m.group(1), m.group(2), m.group(3)
    new_block, n = re.subn(r"^status:\s*\S+.*$", f"status: {new_status}", block, count=1, flags=re.M)
    if n == 0:
        raise ValueError("status 行が見つかりません")
    return head + new_block + tail + text[m.end():]


def append_state(root: Path, ident: str, old: str, new: str, actor: str):
    """STATE.md に遷移記録を1行追記する（無ければヘッダ付きで作成）。"""
    state = root / ".spec" / "STATE.md"
    line = f"- {date.today().isoformat()} {ident}: {old} → {new} ({actor})\n"
    if not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("# STATE — status 遷移ログ\n\n" + line, encoding="utf-8")
    else:
        with state.open("a", encoding="utf-8") as fh:
            fh.write(line)


def main():
    parser = argparse.ArgumentParser(description="BitzSDD status 遷移ツール（権限マトリクス強制）")
    parser.add_argument("workspace", help="ワークスペースルート（.spec/ を含む）")
    parser.add_argument("ident", help="対象 ID（例: CORE-FR-004 / SI-CORE-012 / CORE-TSK-001）")
    parser.add_argument("--to", required=True, dest="to", help="遷移先 status")
    parser.add_argument("--by-human", action="store_true", dest="by_human",
                        help="人間専用遷移を許可する（人間が実行することの明示）")
    parser.add_argument("--actor", help="実行主体（STATE.md 記録用。省略時は human/agent）")
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    kind, path = locate(root, args.ident)
    if kind is None:
        print(f"ERROR: ID '{args.ident}' に対応するファイルが .spec/ 配下に見つかりません",
              file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    cur = read_status(text)
    new = args.to

    if cur == new:
        print(f"ERROR: {args.ident} は既に status '{new}' です（遷移不要）", file=sys.stderr)
        return 2

    required = TRANSITIONS[kind].get((cur, new))
    if required is None:
        print(f"ERROR: {kind} の遷移 '{cur}' → '{new}' は権限マトリクスに定義されていません"
              f"（不正遷移）", file=sys.stderr)
        return 2

    if required == "human" and not args.by_human:
        print(f"ERROR: 遷移 '{cur}' → '{new}' は人間専用です。エージェントは実行できません"
              f"（人間が実行する場合のみ --by-human を付与）", file=sys.stderr)
        return 3

    actor = args.actor or ("human" if args.by_human else "agent")
    path.write_text(rewrite_status(text, new), encoding="utf-8")
    append_state(root, args.ident, cur, new, actor)

    print(f"遷移: {args.ident} {cur} → {new}（{actor}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
