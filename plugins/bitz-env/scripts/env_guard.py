#!/usr/bin/env python3
"""bitz-env PreToolUse ガード: 危険操作を deny する共通ロジック（両プラットフォーム対応）。

stdin の JSON 形状からプラットフォームを自動判別し、それぞれの契約で応答する。

- Claude Code  (stdin: snake_case, "tool_name"/"tool_input")
    -> stdout: {"hookSpecificOutput": {"permissionDecision": "deny"}, ...}
- Antigravity  (stdin: camelCase, "toolCall")
    -> stdout: {"decision": "deny", "reason": ...}

deny 対象は「無害で普遍的な最小集合」に限定する（一般公開プラグインのため、
プロジェクト固有の制限はここに足さず、env-init が生成する permissions 側で行う）。
"""
import json
import re
import sys

DENY_PATTERNS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b", "rm -rf（再帰強制削除）"),
    (r"\bgit\s+push\s+.*(--force\b|-f\b)", "git push --force（強制プッシュ）"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard（作業内容の破棄）"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean -f（未追跡ファイルの削除）"),
    (r"\bsudo\b", "sudo（特権昇格）"),
]

REASON = "bitz-env のガードレールで禁止されている操作です: {label}"


def extract_text(payload: dict) -> tuple[str, str]:
    """(platform, 検査対象テキスト) を返す。platform は 'claude' | 'antigravity' | 'unknown'。"""
    if "toolCall" in payload:
        args = payload.get("toolCall", {}).get("args", {})
        return "antigravity", json.dumps(args, ensure_ascii=False)
    if "tool_name" in payload or "tool_input" in payload:
        return "claude", json.dumps(payload.get("tool_input", {}), ensure_ascii=False)
    return "unknown", json.dumps(payload, ensure_ascii=False)


def respond(platform: str, label: str | None) -> str:
    if label is None:
        return "{}"
    reason = REASON.format(label=label)
    if platform == "antigravity":
        return json.dumps({"decision": "deny", "reason": reason}, ensure_ascii=False)
    return json.dumps({
        "hookSpecificOutput": {"permissionDecision": "deny"},
        "systemMessage": reason,
    }, ensure_ascii=False)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    platform, text = extract_text(payload)
    for pattern, label in DENY_PATTERNS:
        if re.search(pattern, text):
            print(respond(platform, label))
            return
    print("{}")


if __name__ == "__main__":
    main()
