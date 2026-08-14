#!/usr/bin/env python3
"""Antigravity PreToolUse フック: 危険コマンドを deny、リポジトリ外書き込みを force_ask する。

入出力契約は docs/調査報告/01.Antigravity/04_extensibility_architecture.md に従う
(stdin: camelCase JSON / stdout: {"decision": ...})。
"""
import json
import re
import shlex
import sys

DENY_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",
    r"\bgit\s+push\s+.*(--force\b|-f\b)",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bsudo\b",
]

ASK_PATTERNS = [
    r"~/\.claude/skills",
    r"~/\.gemini/config/skills",
    r"/home/[^/\s]+/\.claude/skills",
    r"/home/[^/\s]+/\.gemini/config/skills",
]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _is_m2_confirmation_subject(command: str) -> bool:
    """ユーザー裁定済みのM2確認subject 1コマンドだけを完全形で許可する。"""
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return (
        len(parts) == 4
        and parts[:3] == [
            "python3", "evals/flow-core/m2-eval/local_confirmation_subject.py", "--repo",
        ]
        and bool(parts[3])
    )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    args_text = json.dumps(payload.get("toolCall", {}).get("args", {}), ensure_ascii=False)

    if any(_is_m2_confirmation_subject(value)
           for value in _strings(payload.get("toolCall", {}).get("args", {}))):
        print(json.dumps({
            "decision": "allow",
            "reason": "M2 GP-002用の限定confirmation subject（2026-08-14裁定）",
        }, ensure_ascii=False))
        return

    for pattern in DENY_PATTERNS:
        if re.search(pattern, args_text):
            print(json.dumps({
                "decision": "deny",
                "reason": f"AGENTS.md のガードレールで禁止されている操作です (pattern: {pattern})",
            }, ensure_ascii=False))
            return

    for pattern in ASK_PATTERNS:
        if re.search(pattern, args_text):
            print(json.dumps({
                "decision": "force_ask",
                "reason": "リポジトリ外（実環境のスキル配置先）への操作にはユーザーの明示承認が必要です",
            }, ensure_ascii=False))
            return

    print("{}")


if __name__ == "__main__":
    main()
