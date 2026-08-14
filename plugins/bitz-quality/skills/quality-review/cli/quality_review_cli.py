#!/usr/bin/env python3
"""Minimal public CLI contract for quality-review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXIT = {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "STALE": 2, "UNKNOWN": 2}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quality-review")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "validate", "synthesize", "import-sdd-review", "compare"):
        command = sub.add_parser(name)
        command.add_argument("--input", type=Path)
        command.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        if args.input is None:
            return 3
        try:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            verdict = payload["verdict"]
        except (OSError, ValueError, KeyError, TypeError):
            return 1
        return EXIT.get(verdict, 2)
    if args.output is not None:
        args.output.write_text(json.dumps({"command": args.command}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
