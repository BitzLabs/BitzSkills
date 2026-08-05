#!/usr/bin/env python3
"""M0 eval の固定 corpus を構築し、diff の raw baseline byte 数を測る。

全プラットフォームが**同じリポジトリ状態**を観測しないと Cross-model Decision Parity と
byte 削減率が比較できないため、corpus は本スクリプトだけで作る（手作業で作らない）。

corpus は規模の異なる3 fixture（小 / 中 / 大）で構成する。削減率の median は
その横断で取る（2026-07-31 裁定。`SI-FLW-007`）。

baseline は task ごとに**固定コマンド**である（2026-08-05 裁定。`SI-FLW-009` / `FLW-NFR-008`）。
`dirty-status` は `git status`（引数なしの長形式）、`diff-summary` は生 unified diff。
旧定義（`no-skill` でエージェントが実際に消費した出力を分母にする）は、選ぶ形式と
叩いた回数が platform ごとに違うため同一 renderer が 5.9%〜75.0% に振れて破棄した。

使い方:

    python3 .../fixture.py --path /tmp/m0-corpus --size all
    python3 .../fixture.py --path /tmp/m0-corpus --size all --baseline --format json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# baseline は task ごとに固定する（SI-FLW-009 / FLW-NFR-008）。
# status は parse 入力である --porcelain 系ではなく、エージェントが既定で打つ長形式を分母にする。
BASELINE_COMMANDS = {
    "dirty-status": ["status"],
    "diff-summary": ["diff", "HEAD"],
}

# corpus の規模。変更件数が削減率に効くため、単一 fixture では判定できない。
CORPUS_SIZES = {"small": 4, "medium": 30, "large": 120}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=eval@example.com", "-c", "user.name=eval", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def build(path: Path, modules: int) -> Path:
    """dirty / rename / binary / 非 ASCII を含む決定論的な fixture を作る。

    ``modules`` は変更するソースファイル数。rename 1 件・binary 1 件・untracked 1 件・
    非 ASCII path 1 件が常に加わる。
    """
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    for index in range(modules):
        directory = path / f"src{index // 20}"
        directory.mkdir(exist_ok=True)
        body = "\n".join(f"def f{line}(): return {line}" for line in range(20))
        (directory / f"mod{index}.py").write_text(body + "\n", encoding="utf-8")
    (path / "orig.txt").write_text("a\nb\nc\n", encoding="utf-8")
    (path / "blob.bin").write_bytes(b"\x00\x01\x02binary")
    (path / "日本語 スペース.txt").write_text("x\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "init")

    for index in range(modules):
        target = path / f"src{index // 20}" / f"mod{index}.py"
        target.write_text(target.read_text(encoding="utf-8").replace("return 0", "return 99"), encoding="utf-8")
    git(path, "mv", "orig.txt", "renamed.txt")
    (path / "renamed.txt").write_text("a\nb\nc\nd\n", encoding="utf-8")
    (path / "blob.bin").write_bytes(b"\x00\x09changed")
    (path / "untracked.txt").write_text("new\n", encoding="utf-8")
    return path


def baselines(path: Path) -> dict[str, int]:
    """固定 baseline の UTF-8 byte 数（現在は diff の生 unified diff だけ）。"""
    result = {}
    for task, args in BASELINE_COMMANDS.items():
        proc = git(path, *args, check=False)
        result[task] = len(proc.stdout.encode("utf-8"))
    return result


def changed_count(path: Path) -> int:
    return len([line for line in git(path, "status", "--porcelain").stdout.splitlines() if line])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fixture.py",
        description="M0 eval の固定 fixture を構築し、生 CLI の baseline byte 数を測る。",
    )
    parser.add_argument("--path", required=True, help="corpus を作るパス（既存なら作り直す）")
    parser.add_argument(
        "--size", choices=(*CORPUS_SIZES, "all"), default="all", help="構築する fixture の規模"
    )
    parser.add_argument("--baseline", action="store_true", help="固定 baseline の byte 数も出力する")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.path).expanduser().resolve()
    targets = CORPUS_SIZES if args.size == "all" else {args.size: CORPUS_SIZES[args.size]}

    corpus = {}
    for name, modules in targets.items():
        path = build(root / name, modules)
        entry: dict = {"path": str(path), "changed_files": changed_count(path)}
        if args.baseline:
            entry["raw_baseline_bytes"] = baselines(path)
        corpus[name] = entry

    payload = {
        "corpus": corpus,
        "note": "status 系の baseline は no-skill 条件の実測値を使う（本スクリプトは測らない）。",
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for name, entry in corpus.items():
            print(f"{name}: {entry['path']}（変更 {entry['changed_files']} 件）")
            for task, size in entry.get("raw_baseline_bytes", {}).items():
                print(f"  {task} baseline: {size} bytes（生 unified diff）")
        print(payload["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
