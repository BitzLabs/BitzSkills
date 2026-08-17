#!/usr/bin/env python3
"""Antigravity PreToolUse フック: 危険コマンドを deny、リポジトリ外書き込みを force_ask する。

入出力契約は docs/調査報告/01.Antigravity/04_extensibility_architecture.md に従う
(stdin: camelCase JSON / stdout: {"decision": ...})。
"""
import json
import os
import re
import shlex
import sys

#: ガードレールの実体。これらに言及する payload は既定 deny とし、read-only
#: allowlist（`_is_read_only_command`）だけを通す（`FLW-TSK-101`）。
#: 2026-08-15 の事故で実際に使われた操作種別（`FLW-REV-018:SYN-009`）。
GUARD_ASSETS = r"(agy_guard\.py|hooks\.json|settings\.json|\.credentials\.json)"
GUARD_ASSETS_RE = re.compile(GUARD_ASSETS)

DENY_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",
    r"\bgit\s+push\s+.*(--force\b|-f\b)",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bsudo\b",
    # 認証情報の読み取り（AGENTS.md の禁止事項。read/write を問わず全面禁止であり、
    # ガード資産の read-only allowlist（`_is_read_only_command`）の対象外）。
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

#: ガード資産に言及する payload で唯一許可する読み取り専用コマンド（enumerate allowlist）。
#: 書き込み動詞の列挙（旧方式）は `sed -i` / リダイレクト / `install` / `dd` / `patch` /
#: `ln -sf` / インタプリタからの `open(..., "w")` を素通りさせるため成立しない
#: （`FLW-TSK-101`）。極性を反転し、read-only と確認できたものだけを通す。
READ_ONLY_PROGRAMS = frozenset({
    "cat", "grep", "egrep", "fgrep", "head", "tail", "diff", "wc", "stat", "file",
    "less", "more", "sha256sum", "md5sum",
})
READ_ONLY_GIT_SUBCOMMANDS = frozenset({"show", "log", "diff", "status", "blame", "cat-file"})


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


#: `~` が home 参照として使われている位置（`/` が続くか文字列末尾）だけを展開する。
#: bare `~word`（他ユーザー参照）は展開せずそのまま残す（fail-closed。誤って
#: 無関係な文字列を書き換えない）。
_TILDE_HOME_RE = re.compile(r"~(?=/|$)")


def _normalize_candidate(text: str) -> str:
    """`~` 展開・`.` / `..` / 重複スラッシュの解決を経た正規化後の文字列を返す。

    `ASK_PATTERNS` は生文字列の正規表現であり、`/./` や重複スラッシュを挟むだけで
    照合から外れていた。`os.path.normpath` はスラッシュ区切りの区間だけを畳み込むため、
    コマンド全体（複数語を含む1つの文字列）に適用しても他の語は変化しない
    （`FLW-TSK-101`）。
    """
    if not text:
        return text
    expanded = _TILDE_HOME_RE.sub(os.path.expanduser("~"), text)
    return os.path.normpath(expanded) if "/" in expanded else expanded


def _candidate_strings(args) -> list[str]:
    """payload から正規化済みの候補文字列を再帰的に取り出す（`_strings` を実際に使う）。"""
    return [_normalize_candidate(text) for text in _strings(args) if isinstance(text, str) and text]


def _is_read_only_command(command) -> bool:
    """command 全体が読み取り専用の許可形と完全一致すること（enumerated read allowlist）。

    許可された program（`READ_ONLY_PROGRAMS`）または `git show` 等の読み取り専用
    subcommand に**完全一致**する場合だけ true。shell metacharacter を含む場合は
    偽装（chaining・redirection）の余地があるため無条件に false とする。
    """
    if not isinstance(command, str) or not command or _has_shell_metacharacter(command):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    program = parts[0]
    if program == "git":
        return len(parts) >= 2 and parts[1] in READ_ONLY_GIT_SUBCOMMANDS
    return program in READ_ONLY_PROGRAMS


def _guard_asset_verdict(args, candidates: list[str]) -> dict | None:
    """ガード資産に言及する payload を既定 deny とし、read-only allowlist だけ通す。

    以前の保護は書き込み動詞（`chmod` / `chown` / `mv` / `cp` / `rm` / `truncate` /
    `tee`）の列挙であり、`sed -i` / リダイレクト（`>` は shell metacharacter として
    別途 deny されるが `install` / `dd` / `patch` / `ln -sf` / インタプリタからの
    `open(..., "w")` は動詞に無いため素通りした。動詞の列挙に安全性を載せる方式は
    成立しない（`FLW-TSK-101`）。極性を反転し、ガード資産に言及する payload は
    既定 deny、read-only と確認できたものだけを allow 側へ進める。
    """
    if not any(GUARD_ASSETS_RE.search(candidate) for candidate in candidates):
        return None
    command_line = args.get("CommandLine") if isinstance(args, dict) else None
    bypass = isinstance(args, dict) and bool(args.get("BypassSandbox"))
    if not bypass and _is_read_only_command(command_line):
        return None
    return {
        "decision": "deny",
        "reason": (
            "ガード資産（agy_guard.py / hooks.json / settings.json / .credentials.json）に"
            "言及する操作は読み取り専用の許可形以外すべて拒否します"
        ),
    }


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

    args = payload.get("toolCall", {}).get("args", {})
    # payload から候補文字列を再帰的に取り出し（`_strings`）、正規化後の文字列へ
    # 照合する。正規化前の生文字列だけを見る照合は残さない（`FLW-TSK-101`）。
    candidates = _candidate_strings(args)

    # deny は常に allow より先に判定する（許可形が禁止操作を持ち込む経路を作らない）。
    for pattern in DENY_PATTERNS:
        if any(re.search(pattern, candidate) for candidate in candidates):
            print(json.dumps({
                "decision": "deny",
                "reason": f"AGENTS.md のガードレールで禁止されている操作です (pattern: {pattern})",
            }, ensure_ascii=False))
            return

    guard_asset_verdict = _guard_asset_verdict(args, candidates)
    if guard_asset_verdict is not None:
        print(json.dumps(guard_asset_verdict, ensure_ascii=False))
        return

    # 評価順は DENY → ASK → ALLOW に固定する。allow を ASK より先に置くと、
    # 許可形の `--repo` に実環境のスキル配置先を渡すだけで force_ask を迂回できた
    # （`FLW-REV-018:SYN-009`。実測済み）。
    for pattern in ASK_PATTERNS:
        if any(re.search(pattern, candidate) for candidate in candidates):
            print(json.dumps({
                "decision": "force_ask",
                "reason": "リポジトリ外（実環境のスキル配置先）への操作にはユーザーの明示承認が必要です",
            }, ensure_ascii=False))
            return

    if _is_m2_confirmation_payload(args):
        command = args["CommandLine"]
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
