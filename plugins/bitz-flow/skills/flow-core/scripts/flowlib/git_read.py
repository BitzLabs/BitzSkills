"""Git read adapter（FLW-DSN-005 Read operations）。

M0 が扱うのは ``repo.inspect`` / ``git.status`` / ``git.diff-summary`` の3経路だけ。
外部プロセスの実行は必ず :mod:`flowlib.process` を経由し、``subprocess`` を直接呼ばない。
result object にも renderer にも依存しない（依存方向は adapters → process runner）。

read の純粋性:

- 暗黙の fetch や ref 更新を行わない。remote 情報の更新は独立 operation（M1 の
  ``git.fetch``）で行う。
- ``--no-optional-locks`` を付け、status による index の書き戻しを起こさない。
- ``GIT_TERMINAL_PROMPT=0`` で資格情報の対話要求を封じる。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from . import process

# Git config によるページャ・色・external diff・パス引用を無効化する。
# porcelain=v2 は Git 2.11 以降。環境要件の診断は flow-doctor（M1）が担う。
GIT_COMMON_FLAGS = (
    "--no-pager",
    "--no-optional-locks",
    "-c",
    "core.quotepath=false",
    "-c",
    "color.ui=false",
    "-c",
    "diff.external=",
    "-c",
    "advice.detachedHead=false",
)

GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    "LC_ALL": "C",
}

_STAGE_INSPECT = "inspect"
_STAGE_PARSE = "parse"
_STAGE_VALIDATE = "validate"

_SSH_REMOTE = re.compile(r"^(?:ssh://)?(?:[^@/]+@)?(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?$")
_URL_REMOTE = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?(?P<host>[^:/]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?$")


@dataclass(frozen=True)
class GitFailure:
    """許可語彙 cause と失敗 stage だけを持つ失敗情報。"""

    cause: str
    stage: str
    command_name: str = "git"


@dataclass
class ReadFacts:
    """観測した事実。snapshot の材料になる canonical な値だけを持つ。"""

    values: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _decode_path(raw: bytes) -> tuple[str, bool]:
    """パスを decode する。UTF-8 として不正なら可視化して lossy を報告する。"""
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        return raw.decode("utf-8", "backslashreplace"), True


def _run_git(root: str | None, args: Sequence[str], *, timeout_seconds: float | None = None,
             stage: str = _STAGE_INSPECT) -> tuple[process.ProcessOutcome, GitFailure | None]:
    outcome = process.run(
        ["git", *GIT_COMMON_FLAGS, *args],
        cwd=root,
        timeout_seconds=timeout_seconds,
        env_overrides=GIT_ENV,
        stage=stage,
    )
    if outcome.cause:
        return outcome, GitFailure(outcome.cause, outcome.stage)
    if not outcome.ok:
        return outcome, GitFailure(_classify(outcome.stderr), stage)
    return outcome, None


def _classify(stderr: bytes) -> str:
    """Git の失敗を許可語彙 cause へ正規化する（メッセージ本文は公開しない）。"""
    text = stderr.decode("utf-8", "replace").lower()
    if "not a git repository" in text or "no such file or directory" in text:
        return "not-repository"
    if "permission denied" in text or "unable to access" in text:
        return "permission-denied"
    if "unknown revision" in text or "bad revision" in text or "ambiguous argument" in text:
        return "invalid-ref"
    if "pathspec" in text or ("path" in text and "does not exist" in text):
        return "invalid-path"
    if "could not resolve host" in text or "connection" in text:
        return "remote-unavailable"
    # 分類できない Git 失敗。許可語彙に「分類不能」を表す語が無いため、事実を
    # 一意に判定できていない状態として result-indeterminate を割り当てる
    # （語彙の不足は SI-FLW-006 で裁定する。誤った具体 cause を返すより安全側）。
    return "result-indeterminate"


def resolve_repo_root(start: str | None = None) -> tuple[str | None, GitFailure | None]:
    """repo root を canonical 検証して返す（副作用なし）。"""
    target = os.path.abspath(start or os.getcwd())
    if not os.path.isdir(target):
        return None, GitFailure("invalid-path", _STAGE_VALIDATE)
    outcome, failure = _run_git(target, ["rev-parse", "--show-toplevel"], stage=_STAGE_VALIDATE)
    if failure:
        return None, failure
    root = outcome.stdout.decode("utf-8", "replace").strip()
    if not root:
        return None, GitFailure("not-repository", _STAGE_VALIDATE)
    return os.path.realpath(root), None


# --- porcelain v2 の parse ---------------------------------------------------


def _split_nul(raw: bytes) -> list[bytes]:
    records = raw.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    return records


_XY_FALLBACK = ".."


def _safe_int(text: str, default: int | None = None) -> int | None:
    """壊れた出力でも例外を投げない整数変換（不正出力 fixture 対策）。"""
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _parse_status_v2(raw: bytes) -> tuple[dict, list[dict], bool]:
    """``status --porcelain=v2 --branch -z`` を parse する。

    戻り値は (branch 情報, 変更 entry 一覧, lossy path を含むか)。
    """
    branch = {"name": None, "upstream": None, "ahead": None, "behind": None, "detached": False}
    items: list[dict] = []
    lossy = False

    records = _split_nul(raw)
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if record.startswith(b"# "):
            text = record[2:].decode("utf-8", "replace")
            key, _, value = text.partition(" ")
            if key == "branch.head":
                branch["detached"] = value == "(detached)"
                branch["name"] = None if branch["detached"] else value
            elif key == "branch.upstream":
                branch["upstream"] = value
            elif key == "branch.ab":
                ahead, _, behind = value.partition(" ")
                branch["ahead"] = _safe_int(ahead.lstrip("+"))
                branch["behind"] = _safe_int(behind.lstrip("-"))
            continue

        kind = record[:1]
        if kind in (b"1", b"2"):
            fields = record.split(b" ", 8)
            xy = fields[1].decode("ascii", "replace") if len(fields) > 1 else _XY_FALLBACK
            if kind == b"2":
                # 2 <XY> ... <X><score> <path>\0<origPath>
                fields = record.split(b" ", 9)
                path_raw = fields[9] if len(fields) > 9 else b""
                orig_raw = records[index] if index < len(records) else b""
                index += 1
            else:
                path_raw = fields[8] if len(fields) > 8 else b""
                orig_raw = b""
            path, path_lossy = _decode_path(path_raw)
            orig, orig_lossy = _decode_path(orig_raw) if orig_raw else (None, False)
            lossy = lossy or path_lossy or orig_lossy
            items.append({"xy": xy, "path": path, "orig_path": orig, "state": _state_of(xy)})
        elif kind == b"u":
            fields = record.split(b" ", 10)
            xy = fields[1].decode("ascii", "replace") if len(fields) > 1 else _XY_FALLBACK
            path, path_lossy = _decode_path(fields[10] if len(fields) > 10 else b"")
            lossy = lossy or path_lossy
            items.append({"xy": xy, "path": path, "orig_path": None, "state": "conflicted"})
        elif kind in (b"?", b"!"):
            path, path_lossy = _decode_path(record[2:])
            lossy = lossy or path_lossy
            state = "untracked" if kind == b"?" else "ignored"
            items.append({"xy": record[:1].decode() * 2, "path": path, "orig_path": None, "state": state})
    return branch, items, lossy


def _state_of(xy: str) -> str:
    """porcelain v2 の XY から状態を決める。

    v2 は「変更なし」を ``.`` で表す（v1 の空白ではない）。両方を未変更として扱う。
    """
    index_state = xy[:1] or "."
    work_state = xy[1:2] or "."
    unchanged = (".", " ", "?", "!")
    if index_state == "U" or work_state == "U":
        return "conflicted"
    staged = index_state not in unchanged
    unstaged = work_state not in unchanged
    if staged and unstaged:
        return "both"
    if staged:
        return "staged"
    return "unstaged"


def _count_states(items: Sequence[dict]) -> dict[str, int]:
    counts = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
    for item in items:
        state = item["state"]
        if state == "both":
            counts["staged"] += 1
            counts["unstaged"] += 1
        elif state in counts:
            counts[state] += 1
    return counts


# --- 公開 read 経路 ----------------------------------------------------------


def inspect(root: str, *, timeout_seconds: float | None = None) -> tuple[ReadFacts | None, GitFailure | None]:
    """``repo.inspect``: root / HEAD / branch / upstream / dirty / remote を返す。"""
    head_outcome, failure = _run_git(root, ["rev-parse", "HEAD"], timeout_seconds=timeout_seconds)
    head_sha: str | None = None
    if failure is None:
        head_sha = head_outcome.stdout.decode("ascii", "replace").strip() or None
    elif failure.cause not in ("not-repository", "invalid-ref"):
        return None, failure

    status_outcome, failure = _run_git(
        root, ["status", "--porcelain=v2", "--branch", "-z"], timeout_seconds=timeout_seconds
    )
    if failure:
        return None, failure
    branch, items, lossy = _parse_status_v2(status_outcome.stdout)

    remotes, remote_failure = _remotes(root, timeout_seconds=timeout_seconds)
    if remote_failure:
        return None, remote_failure

    facts = ReadFacts(
        values={
            "head": {"sha": head_sha, "detached": branch["detached"]},
            "branch": branch["name"],
            "upstream": branch["upstream"],
            "dirty": bool(items),
            "remotes": remotes,
        }
    )
    if lossy:
        facts.warnings.append("UTF-8 として解釈できないパスを可視化表現へ置換した")
    return facts, None


def _remotes(root: str, *, timeout_seconds: float | None = None) -> tuple[list[dict], GitFailure | None]:
    """remote を canonical identity へ正規化する。URL をそのまま返さない。"""
    outcome, failure = _run_git(root, ["remote", "-v"], timeout_seconds=timeout_seconds)
    if failure:
        return [], failure
    seen: dict[str, dict] = {}
    for line in outcome.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if name in seen:
            continue
        seen[name] = {"name": name, **_remote_identity(url)}
    return list(seen.values()), None


def _remote_identity(url: str) -> dict[str, str | None]:
    """remote URL から host / owner / repo だけを取り出す。

    URL には資格情報が埋め込まれ得るため、そのまま result へ載せない
    （references/output-contract.md の「credential を出力しない」）。
    """
    match = _URL_REMOTE.match(url) or _SSH_REMOTE.match(url)
    if not match:
        return {"host": None, "owner": None, "repo": None}
    path = match.group("path").strip("/")
    segments = [segment for segment in path.split("/") if segment]
    owner = segments[-2] if len(segments) >= 2 else None
    repo = segments[-1] if segments else None
    return {"host": match.group("host"), "owner": owner, "repo": repo}


def status(root: str, *, timeout_seconds: float | None = None) -> tuple[ReadFacts | None, GitFailure | None]:
    """``git.status``: branch / upstream / ahead / behind / 変更 entry を返す。"""
    outcome, failure = _run_git(
        root, ["status", "--porcelain=v2", "--branch", "-z"], timeout_seconds=timeout_seconds
    )
    if failure:
        return None, failure
    branch, items, lossy = _parse_status_v2(outcome.stdout)
    facts = ReadFacts(
        values={
            "branch": {
                "name": branch["name"],
                "upstream": branch["upstream"],
                "ahead": branch["ahead"],
                "behind": branch["behind"],
                "detached": branch["detached"],
            },
            "counts": _count_states(items),
            "items": items,
        }
    )
    if lossy:
        facts.warnings.append("UTF-8 として解釈できないパスを可視化表現へ置換した")
    return facts, None


_KIND_LETTERS = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type-changed",
    "U": "unmerged",
}


def diff_summary(
    root: str, *, base: str | None = None, timeout_seconds: float | None = None
) -> tuple[ReadFacts | None, GitFailure | None]:
    """``git.diff-summary``: path / 変更種別 / 追加削除行数 / binary を返す。

    変更行の内容は返さない（詳細は M1 の ``git.diff-detail``）。
    """
    args = ["diff", "--name-status", "-z"]
    numstat_args = ["diff", "--numstat", "-z"]
    if base:
        args.append(base)
        numstat_args.append(base)

    name_outcome, failure = _run_git(root, args, timeout_seconds=timeout_seconds)
    if failure:
        return None, failure
    num_outcome, failure = _run_git(root, numstat_args, timeout_seconds=timeout_seconds)
    if failure:
        return None, failure

    kinds, lossy_a = _parse_name_status(name_outcome.stdout)
    numbers, lossy_b = _parse_numstat(num_outcome.stdout)

    items: list[dict] = []
    for path, entry in kinds.items():
        added, deleted, binary = numbers.get(path, (0, 0, False))
        items.append(
            {
                "path": path,
                "orig_path": entry["orig_path"],
                "kind": entry["kind"],
                "added": added,
                "deleted": deleted,
                "binary": binary,
            }
        )
    items.sort(key=lambda item: item["path"])
    totals = {
        "files": len(items),
        "added": sum(item["added"] or 0 for item in items),
        "deleted": sum(item["deleted"] or 0 for item in items),
        "binary": sum(1 for item in items if item["binary"]),
    }
    facts = ReadFacts(
        values={
            # base 省略時の `git diff` は index と worktree の比較であり HEAD ではない。
            # range は実際に比較した対象を正直に返す（呼出側は --base HEAD を渡せる）。
            "range": {"base": base or "index", "compare": "worktree"},
            "totals": totals,
            "items": items,
        }
    )
    if lossy_a or lossy_b:
        facts.warnings.append("UTF-8 として解釈できないパスを可視化表現へ置換した")
    return facts, None


def _parse_name_status(raw: bytes) -> tuple[dict[str, dict], bool]:
    records = _split_nul(raw)
    entries: dict[str, dict] = {}
    lossy = False
    index = 0
    while index < len(records):
        token = records[index].decode("ascii", "replace")
        index += 1
        letter = token[:1]
        kind = _KIND_LETTERS.get(letter, "modified")
        if letter in ("R", "C"):
            orig_raw = records[index] if index < len(records) else b""
            path_raw = records[index + 1] if index + 1 < len(records) else b""
            index += 2
            orig, orig_lossy = _decode_path(orig_raw)
            path, path_lossy = _decode_path(path_raw)
            lossy = lossy or orig_lossy or path_lossy
            entries[path] = {"kind": kind, "orig_path": orig}
        else:
            path_raw = records[index] if index < len(records) else b""
            index += 1
            path, path_lossy = _decode_path(path_raw)
            lossy = lossy or path_lossy
            entries[path] = {"kind": kind, "orig_path": None}
    return entries, lossy


def _parse_numstat(raw: bytes) -> tuple[dict[str, tuple[int | None, int | None, bool]], bool]:
    records = _split_nul(raw)
    numbers: dict[str, tuple[int | None, int | None, bool]] = {}
    lossy = False
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if b"\t" not in record:
            continue
        added_raw, deleted_raw, path_raw = record.split(b"\t", 2)
        if path_raw == b"":
            # rename / copy は src と dst が後続 record に入る。
            index += 1  # src は捨てる（対応は name-status 側が持つ）
            path_raw = records[index] if index < len(records) else b""
            index += 1
        path, path_lossy = _decode_path(path_raw)
        lossy = lossy or path_lossy
        binary = added_raw == b"-" or deleted_raw == b"-"
        added = None if binary else _safe_int(added_raw.decode("ascii", "replace"), 0)
        deleted = None if binary else _safe_int(deleted_raw.decode("ascii", "replace"), 0)
        numbers[path] = (added, deleted, binary)
    return numbers, lossy
