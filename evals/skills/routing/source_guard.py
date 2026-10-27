#!/usr/bin/env python3
"""作業ツリーの対象資源を確定refへ照合する。HEADの移動は停止条件にしない。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def git(repository: Path, *args: str) -> bytes:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(["git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null", *args],
                            cwd=repository, env=env, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("fixed source unavailable")
    return result.stdout


def verify(repository: Path, source_commit: str, names: list[str]) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("full commit required")
    if not names or len(names) != len(set(names)):
        raise ValueError("empty or duplicate paths")
    if any(p.is_symlink() for p in [repository, *repository.parents]):
        raise ValueError("repository symlink")
    repository = repository.resolve(strict=True)
    for name in names:
        if not isinstance(name, str) or "\\" in name:
            raise ValueError("invalid source path")
        parts = name.split("/")
        if Path(name).is_absolute() or any(p in {"", ".", "..", ".git", ".env", ".credentials.json"} or p.startswith(".env.") for p in parts):
            raise ValueError("invalid source path")
        path = repository / name
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(repository)):
            raise ValueError("source symlink")
    hashes = {}
    for name in names:
        expected = git(repository, "show", source_commit + ":" + name)
        actual = (repository / name).read_bytes()
        if actual != expected:
            raise ValueError("fixed source drift")
        hashes[name] = hashlib.sha256(expected).hexdigest()
    return {"status": "fixed_source_matches", "sourceCommit": source_commit,
            "observedHead": git(repository, "rev-parse", "HEAD").decode().strip(),
            "headIsCondition": False, "sourceSha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.source):
            raise ValueError("full commit required")
        name = "evals/skills/routing/held-out-collection-v0.3.json"
        contract = json.loads(git(ROOT, "show", args.source + ":" + name))
        result = verify(ROOT, args.source, contract["sourceFiles"])
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
