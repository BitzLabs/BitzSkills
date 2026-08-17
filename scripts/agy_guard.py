#!/usr/bin/env python3
"""Antigravity PreToolUse フック: 危険コマンドを deny、リポジトリ外書き込みを force_ask する。

入出力契約は docs/調査報告/01.Antigravity/04_extensibility_architecture.md に従う
(stdin: camelCase JSON / stdout: {"decision": ...})。
"""
import json
import re
import shlex
import sys

#: ガードレールの実体。これらを書き換え・退避・破壊する操作は、
#: 以後のすべての判定を無意味にするため allow 分岐と独立に deny する
#: （2026-08-15 の事故で実際に使われた操作種別。`FLW-REV-018:SYN-009`）。
GUARD_ASSETS = r"(agy_guard\.py|hooks\.json|settings\.json|\.credentials\.json)"

DENY_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",
    r"\bgit\s+push\s+.*(--force\b|-f\b)",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bsudo\b",
    # ガードレール実体への破壊的操作
    rf"\b(chmod|chown|mv|cp|rm|truncate|tee)\b[^\n]*{GUARD_ASSETS}",
    # 認証情報の読み取り（AGENTS.md の禁止事項）
    r"\.claude/\.credentials\.json",
    # 強制削除
    r"\bgit\s+branch\s+.*(-D\b|--delete\s+--force\b)",
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


#: shell を起動しうる文字。許可形の判定でも、同居する他フィールドでも一律に拒む。
SHELL_METACHARACTERS = ";|&$`<>(){}[]\\\n\r\t\v\f*?!#'\""

#: `--repo` に許すのは絶対パスだけ（展開・置換の余地を残さない）。
SAFE_REPO_ARG = re.compile(r"/[A-Za-z0-9_./-]+")

M2_SUBJECT_SCRIPT = "/evals/flow-core/m2-eval/local_confirmation_subject.py"


def _has_shell_metacharacter(value: str) -> bool:
    return any(char in value for char in SHELL_METACHARACTERS)


def _is_m2_confirmation_subject(command: str) -> bool:
    """ユーザー裁定済みのM2確認subject 1コマンドだけを完全形で許可する。"""
    if _has_shell_metacharacter(command):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if len(parts) != 4 or parts[2] != "--repo":
        return False
    interpreter, script, repo = parts[0], parts[1], parts[3]
    if not (interpreter == "python3" and SAFE_REPO_ARG.fullmatch(repo)):
        return False
    return script == repo + M2_SUBJECT_SCRIPT


#: Antigravity の `run_command` が実際に送る field（2026-08-16 に実測）。
#: 実行されるのは `CommandLine` だけで、他は構造化された付随情報である。
#: **未知の field がある payload は allow しない**（形が変わったら黙って通さない）。
_RUN_COMMAND_FIELDS = frozenset({
    "CommandLine", "Cwd", "BypassSandbox", "RunPersistent", "WaitMsBeforeAsync",
})


def _is_m2_confirmation_payload(args) -> bool:
    """args が確認subject の実行**そのもの**であること。

    以前は「どこかに正規形があり、他の値にシェルメタ文字が無ければ allow」だった。
    しかし `git commit -am pwned` / `git push origin main` / `git branch -D main` /
    `mv scripts/agy_guard.py /tmp/z` / `chmod 000 scripts/agy_guard.py` は
    いずれもメタ文字を含まないため、別フィールドへ相乗りさせると allow を通っていた
    （`FLW-REV-017:RSK-201` / `OPS-301`。2026-08-15 の事故で実際に使われた操作種別）。

    推測で緩めず、実測した payload の形に対する allowlist にする。

    1. 実行される `CommandLine` が正規形と完全一致すること
    2. **`BypassSandbox` が真でないこと**（sandbox 解除を allow で覆わない）
    3. `Cwd` は shell metacharacter を含まない path であること
    4. 未知の field を持たないこと（形が変わったら allow せず既定へ倒す）
    """
    if not isinstance(args, dict):
        return False
    if set(args) - _RUN_COMMAND_FIELDS:
        return False
    if not _is_m2_confirmation_subject(str(args.get("CommandLine", ""))):
        return False
    if args.get("BypassSandbox"):
        return False
    cwd = args.get("Cwd")
    if cwd is not None and (not isinstance(cwd, str) or _has_shell_metacharacter(cwd)):
        return False
    return True


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    args_text = json.dumps(payload.get("toolCall", {}).get("args", {}), ensure_ascii=False)

    # deny は常に allow より先に判定する（許可形が禁止操作を持ち込む経路を作らない）。
    for pattern in DENY_PATTERNS:
        if re.search(pattern, args_text):
            print(json.dumps({
                "decision": "deny",
                "reason": f"AGENTS.md のガードレールで禁止されている操作です (pattern: {pattern})",
            }, ensure_ascii=False))
            return

    # 評価順は DENY → ASK → ALLOW に固定する。allow を ASK より先に置くと、
    # 許可形の `--repo` に実環境のスキル配置先を渡すだけで force_ask を迂回できた
    # （`FLW-REV-018:SYN-009`。実測済み）。
    for pattern in ASK_PATTERNS:
        if re.search(pattern, args_text):
            print(json.dumps({
                "decision": "force_ask",
                "reason": "リポジトリ外（実環境のスキル配置先）への操作にはユーザーの明示承認が必要です",
            }, ensure_ascii=False))
            return

    if _is_m2_confirmation_payload(payload.get("toolCall", {}).get("args", {})):
        command = payload["toolCall"]["args"]["CommandLine"]
        print(json.dumps({
            "decision": "allow",
            "reason": "M2 GP-002用の限定confirmation subject（2026-08-14裁定）",
            # headless 実行でも通常の permission layer がこの正規形だけを許可できるよう、
            # hook 判定と同じ command を override として明示する。全承認フラグは使わない。
            "permissionOverrides": [f"command({command})"],
        }, ensure_ascii=False))
        return

    print("{}")


if __name__ == "__main__":
    main()
