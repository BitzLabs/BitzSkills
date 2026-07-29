#!/usr/bin/env python3
"""spec_verify.py — 検証コマンドの実出力から機械可読な証跡を記録する（stdlib のみ）

使い方:
  python3 spec_verify.py record <workspace> --command-id pytest \
      --implements SDD-FR-151 --implements SDD-FR-152 -- .venv/bin/pytest -q

コマンドを実際に実行し、終了コード・件数・commit・tool version を
`.spec/verification/<command-id>--<commit短縮>.json` へ記録する。
raw stdout/stderr・環境変数・秘密値は保存せず、許可リストの要約だけを書く（SDD-FR-152）。
同じ commit で同じ command-id を再実行すると同じファイルを上書きするため冪等で、
実行時間だけが違う再実行が diff を生まない（duration は observed へ分離する。SDD-FR-151）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "bitzsdd/verification-evidence@1"
EVIDENCE_DIRNAME = "verification"

COMMAND_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIREMENT_ID_RE = re.compile(r"^(?:[A-Z0-9]{2,4}-)?(?:FR|NFR|CON)-\d{3}$")

# 秘密値・環境固有パスの混入を防ぐ拒否パターン（SDD-FR-152）
SECRET_TOKEN_RE = re.compile(
    r"(?i)(token|secret|passwd|password|api[_-]?key|credential|authorization|bearer)"
)
HOME_PATH_RE = re.compile(r"(?:^|=)(?:/home/|/Users/|/root/|[A-Za-z]:\\Users\\)")

# pytest の要約行から拾う件数の語彙
PYTEST_COUNT_WORDS = {
    "passed": "passed",
    "failed": "failed",
    "error": "errors",
    "errors": "errors",
    "skipped": "skipped",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
    "deselected": "deselected",
}
PYTEST_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b"
)
PYTEST_DURATION_RE = re.compile(r"\bin\s+([\d.]+)s\b")
VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?(?:[-.][0-9A-Za-z]+)*)\b")


class VerifyError(ValueError):
    """証跡を記録できない入力・状態を表す。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_output(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def resolve_commit(workspace: Path) -> tuple[str, bool]:
    """HEAD の commit SHA と作業ツリーが dirty かを返す。

    証跡ディレクトリ自身の差分は dirty と見なさない。記録が自分自身を dirty にして
    次の記録を拒否する自己ブロックを避けるため。
    """
    sha = git_output(workspace, "rev-parse", "HEAD")
    if not sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise VerifyError(
            "git の HEAD を解決できません。証跡は commit に紐づけて記録するため、"
            "git リポジトリ内で実行してください"
        )
    # パスは repo ルート相対で出るため、ワークスペースが sub-directory でも一致する
    # 部分文字列で証跡ディレクトリを判定する
    status = git_output(workspace, "status", "--porcelain", "--", ".") or ""
    evidence_segment = f".spec/{EVIDENCE_DIRNAME}/"
    dirty = False
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].split(" -> ")[-1].strip('"')
        if evidence_segment not in path:
            dirty = True
            break
    return sha, dirty


def sanitize_command(command: list[str], repo_root: Path) -> list[str]:
    """argv を記録可能な形へ正規化する。秘密値・環境固有パスは拒否する。"""
    if not command:
        raise VerifyError("実行するコマンドが指定されていません（`--` の後ろに記述します）")
    sanitized = []
    root_prefix = str(repo_root) + os.sep
    for index, token in enumerate(command):
        if token.startswith(root_prefix):
            relative = token[len(root_prefix) :]
            # 実行ファイルは相対パスのまま起動できるよう `./` を付ける（PATH 探索に落ちないため）
            token = f".{os.sep}{relative}" if index == 0 else relative
        if SECRET_TOKEN_RE.search(token):
            raise VerifyError(
                f"秘密値を含む可能性がある引数は記録できません: {token[:12]}…（"
                "認証情報は環境変数など証跡に載らない経路で渡してください）"
            )
        if HOME_PATH_RE.search(token):
            raise VerifyError(
                f"環境固有の絶対パスは記録できません: {token}（"
                "ワークスペース相対パスで指定してください）"
            )
        sanitized.append(token)
    return sanitized


def parse_pytest_counts(output: str) -> tuple[dict[str, int] | None, float | None]:
    """pytest の要約行から件数と実行時間を抽出する。要約が無ければ (None, None)。"""
    summary_line = None
    for line in reversed(output.splitlines()):
        if PYTEST_COUNT_RE.search(line):
            summary_line = line
            break
    if summary_line is None:
        return None, None
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for number, word in PYTEST_COUNT_RE.findall(summary_line):
        key = PYTEST_COUNT_WORDS.get(word)
        if key is not None:
            counts[key] = counts.get(key, 0) + int(number)
    duration_match = PYTEST_DURATION_RE.search(summary_line)
    duration = float(duration_match.group(1)) if duration_match else None
    return counts, duration


def detect_tool_version(executable: str, cwd: Path) -> str | None:
    """`<tool> --version` から version 文字列を取る。取れなければ None。"""
    try:
        result = subprocess.run(
            [executable, "--version"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = VERSION_RE.search(result.stdout + result.stderr)
    return match.group(1) if match else None


def evidence_path(workspace: Path, command_id: str, commit: str) -> Path:
    return workspace / ".spec" / EVIDENCE_DIRNAME / f"{command_id}--{commit[:7]}.json"


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def do_record(args) -> int:
    workspace = Path(args.workspace).resolve()
    if not (workspace / ".spec").is_dir():
        raise VerifyError(f"BitzSDD ワークスペースではありません（.spec がない）: {workspace}")
    if not COMMAND_ID_RE.fullmatch(args.command_id):
        raise VerifyError(
            f"command-id は英小文字・数字・ハイフン・アンダースコアで始めます: {args.command_id!r}"
        )
    requirements = sorted(set(args.implements))
    invalid = [rid for rid in requirements if not REQUIREMENT_ID_RE.fullmatch(rid)]
    if invalid:
        raise VerifyError(f"要件 ID の書式が不正です: {', '.join(invalid)}")

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    command = sanitize_command(command, workspace)

    commit, dirty = resolve_commit(workspace)
    if dirty and not args.allow_dirty:
        raise VerifyError(
            "作業ツリーに未コミットの変更があります。証跡は commit に紐づくため、"
            "コミット後に記録するか、暫定記録なら --allow-dirty を明示してください"
        )

    started = time.monotonic()
    completed = subprocess.run(
        command, cwd=str(workspace), capture_output=True, text=True
    )
    elapsed = round(time.monotonic() - started, 2)
    # 実出力は端末へそのまま流す（証跡には保存しない。SDD-FR-152）
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)

    counts, parsed_duration = (None, None)
    tool_name = args.tool_name or Path(command[0]).name
    # auto はコマンド本体と command-id の両方から解析器を推定する
    auto_pytest = args.parser == "auto" and "pytest" in " ".join([*command, args.command_id])
    if args.parser == "pytest" or auto_pytest:
        counts, parsed_duration = parse_pytest_counts(completed.stdout + completed.stderr)

    payload = {
        "schema": SCHEMA,
        "command_id": args.command_id,
        "command": command,
        "commit": commit,
        "dirty": dirty,
        "recorded_at": utc_now(),
        "tool": {"name": tool_name, "version": detect_tool_version(command[0], workspace)},
        "exit_code": completed.returncode,
        "counts": counts,
        "requirements": requirements,
        # observed は非正規の観測値。再実行のたびに変動するため一致判定には使わない
        "observed": {"duration_seconds": parsed_duration if parsed_duration is not None else elapsed},
    }
    target = evidence_path(workspace, args.command_id, commit)
    atomic_write_json(target, payload)

    relative = target.relative_to(workspace)
    summary = "counts=解析なし" if counts is None else " ".join(
        f"{key}={value}" for key, value in sorted(counts.items())
    )
    print(f"記録: {relative}")
    print(f"  commit={commit[:7]}{' (dirty)' if dirty else ''} "
          f"exit_code={completed.returncode} {summary}")
    print(f"  対象要件: {', '.join(requirements)}")
    if completed.returncode != 0:
        print("  注意: 失敗した実行を記録しました。spec_inspect はこれを FAIL として扱います。")
    return 0


def main() -> int:
    # 検証コマンド自身がオプションを持つため、最初の `--` より後ろは argparse に渡さない
    # （REMAINDER 位置引数はサブコマンドのオプションまで飲み込むため使わない）
    argv = sys.argv[1:]
    command: list[str] = []
    if "--" in argv:
        separator = argv.index("--")
        argv, command = argv[:separator], argv[separator + 1 :]

    parser = argparse.ArgumentParser(
        description="BitzSDD: 検証コマンドの実出力から機械可読な証跡を記録する",
        epilog="検証コマンドは `--` の後ろに記述する: "
               "record . --command-id pytest --implements XX-FR-001 -- .venv/bin/pytest -q",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    record = subparsers.add_parser("record", help="コマンドを実行して証跡を記録する")
    record.add_argument("workspace", help="BitzSDD ワークスペース（.spec を持つディレクトリ）")
    record.add_argument("--command-id", required=True,
                        help="検証コマンドの識別子（証跡ファイル名になる。例: pytest）")
    record.add_argument("--implements", action="append", default=[], required=True,
                        metavar="ID", help="この実行が検証する要件 ID（複数指定可）")
    record.add_argument("--tool-name", help="記録する tool 名（既定: 実行ファイル名）")
    record.add_argument("--parser", choices=["auto", "pytest", "none"], default="auto",
                        help="件数の解析器（既定: auto）")
    record.add_argument("--allow-dirty", action="store_true",
                        help="未コミットの変更がある状態でも記録する（暫定記録）")

    args = parser.parse_args(argv)
    args.command = command
    try:
        return do_record(args)
    except VerifyError as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 1
    except OSError as error:
        sys.stderr.write(f"ERROR: 証跡を書き込めません: {error}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
