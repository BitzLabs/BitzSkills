#!/usr/bin/env python3
"""M0 eval の固定 fixture を構築し、生 CLI の baseline byte 数を測る。

全プラットフォームが**同じリポジトリ状態**を観測しないと Cross-model Decision Parity と
byte 削減率が比較できないため、fixture は本スクリプトだけで作る（手作業で作らない）。

使い方:

    python3 <このスキル>/../evals/flow-core/m0-eval/fixture.py --path /tmp/m0-fixture
    python3 .../fixture.py --path /tmp/m0-fixture --baseline --format json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 生 CLI の baseline。同じ情報を得るために人間・エージェントが打つ標準的なコマンド。
BASELINE_COMMANDS = {
    "repo-inspect": ["status", "--short", "--branch"],
    "dirty-status": ["status"],
    # diff の baseline は生の unified diff とする（discovery/metrics.md の
    # 「diff summary は生 unified diff 比で median 80%以上削減」）。
    "diff-summary": ["diff", "HEAD"],
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=eval@example.com", "-c", "user.name=eval", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def build(path: Path) -> Path:
    """dirty / rename / binary / 非 ASCII を含む決定論的な fixture を作る。"""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    (path / "orig.txt").write_text("a\nb\nc\n", encoding="utf-8")
    (path / "blob.bin").write_bytes(b"\x00\x01\x02binary")
    (path / "日本語 スペース.txt").write_text("x\n", encoding="utf-8")
    (path / "src").mkdir()
    (path / "src" / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "init")

    git(path, "mv", "orig.txt", "renamed.txt")
    (path / "renamed.txt").write_text("a\nb\nc\nd\n", encoding="utf-8")
    (path / "blob.bin").write_bytes(b"\x00\x09changed")
    (path / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (path / "untracked.txt").write_text("new\n", encoding="utf-8")
    return path


def baselines(path: Path) -> dict[str, int]:
    """生 CLI で同じ情報を得たときの UTF-8 byte 数（削減率の分母）。"""
    result = {}
    for task, args in BASELINE_COMMANDS.items():
        proc = git(path, *args, check=False)
        result[task] = len(proc.stdout.encode("utf-8"))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fixture.py",
        description="M0 eval の固定 fixture を構築し、生 CLI の baseline byte 数を測る。",
    )
    parser.add_argument("--path", required=True, help="fixture を作るパス（既存なら作り直す）")
    parser.add_argument("--baseline", action="store_true", help="baseline byte 数も出力する")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    path = build(Path(args.path).expanduser().resolve())
    payload: dict = {"fixture": str(path)}
    if args.baseline:
        payload["raw_baseline_bytes"] = baselines(path)

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"fixture: {path}")
        for task, size in payload.get("raw_baseline_bytes", {}).items():
            print(f"  {task}: {size} bytes（生 CLI）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
