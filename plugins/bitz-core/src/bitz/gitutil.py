"""Git検出とrevision解決。

`Core実行環境・CLI基盤契約 §4` に従い、Git CLIをargvで直接起動する。shellを使わない。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

MIN_GIT_MAJOR = 2
MIN_GIT_MINOR = 30


@dataclass
class GitInfo:
    available: bool
    executable: str | None = None
    version: tuple[int, int] | None = None


def _run(argv: list[str], cwd: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def detect_git(cwd: str, env: dict[str, str]) -> GitInfo:
    path_value = env.get("PATH", "")
    executable = shutil.which("git", path=path_value)
    if not executable:
        return GitInfo(available=False)
    try:
        proc = _run([executable, "--version"], cwd, env)
    except (OSError, subprocess.SubprocessError):
        return GitInfo(available=False)
    if proc.returncode != 0:
        return GitInfo(available=False)
    first_line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
    version = _parse_git_version(first_line)
    if version is None:
        return GitInfo(available=False)
    major, minor = version
    if (major, minor) < (MIN_GIT_MAJOR, MIN_GIT_MINOR):
        return GitInfo(available=False, executable=executable, version=version)
    return GitInfo(available=True, executable=executable, version=version)


def _parse_git_version(line: str) -> tuple[int, int] | None:
    prefix = "git version "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix) :].strip()
    parts = rest.split(".")
    if len(parts) < 2:
        return None
    major_s, minor_s = parts[0], parts[1]
    if not major_s.isdigit() or not minor_s.isdigit():
        return None
    return int(major_s), int(minor_s)


def show_toplevel(executable: str, cwd: str, env: dict[str, str]) -> str | None:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "rev-parse", "--show-toplevel"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def resolve_commit(executable: str, cwd: str, env: dict[str, str], rev: str) -> str | None:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "rev-parse", "--verify", f"{rev}^{{commit}}"],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if len(out) != 40:
        return None
    return out


def is_dirty(executable: str, cwd: str, env: dict[str, str]) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "status", "--porcelain"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


@dataclass
class ChangedPath:
    """Git変更集合の1件（`03_操作仕様/02_check.md` §5）。

    ``status``は``A``（追加。未追跡を含む）、``M``（変更）、``D``（削除）、``R``（rename）のいずれか。
    ``path``は現在版のpath（削除は基準版のpath）、``old_path``はrenameの旧pathだけに設定する。
    """

    status: str
    path: str
    old_path: str | None = None


def _parse_name_status_z(output: str) -> list[ChangedPath]:
    """``git diff -z --name-status``の出力を解析する（NUL区切り。quotePathでpathが化けない）。"""

    tokens = output.split("\0")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    changed: list[ChangedPath] = []
    i = 0
    n = len(tokens)
    while i < n:
        code = tokens[i]
        if not code:
            i += 1
            continue
        if code[0] in ("R", "C"):
            if i + 2 >= n:
                break
            changed.append(ChangedPath(status="R", path=tokens[i + 2], old_path=tokens[i + 1]))
            i += 3
            continue
        if i + 1 >= n:
            break
        path = tokens[i + 1]
        if code == "D":
            changed.append(ChangedPath(status="D", path=path))
        else:
            changed.append(ChangedPath(status="M" if code == "M" else "A", path=path))
        i += 2
    return changed


def _diff_name_status_z(
    executable: str, cwd: str, env: dict[str, str], extra_args: list[str]
) -> list[ChangedPath]:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "diff", "-z", "--no-color", "-M", "--name-status", *extra_args],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return _parse_name_status_z(proc.stdout)


def _ls_files_others_z(executable: str, cwd: str, env: dict[str, str]) -> list[ChangedPath]:
    try:
        proc = _run(
            [
                executable,
                "--no-optional-locks",
                "ls-files",
                "-z",
                "--others",
                "--exclude-standard",
                "--full-name",
            ],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    tokens = proc.stdout.split("\0")
    return [ChangedPath(status="A", path=p) for p in tokens if p]


def _repo_root_relative_offset(executable: str, cwd: str, env: dict[str, str], workspace_root: str) -> str | None:
    """repository rootから見た``workspace_root``の相対path（``.``＝一致）を返す。

    repository rootを解決できなければ``None``を返し、呼び出し側はrepository root相対の
    pathをそのままworkspace root相対として扱う（fallback。単一workspace検査対象repositoryの
    大半はworkspace root＝repository rootであるため、この場合は実害がない）。
    """

    toplevel = show_toplevel(executable, cwd, env)
    if toplevel is None:
        return None
    toplevel_abs = os.path.abspath(toplevel)
    workspace_abs = os.path.abspath(workspace_root)
    rel = os.path.relpath(workspace_abs, toplevel_abs)
    return rel.replace(os.sep, "/")


def _to_workspace_relative(path: str, offset: str | None) -> str | None:
    """repository root相対``path``をworkspace root相対へ変換する。workspace root外なら``None``。"""

    if offset is None or offset in (".", ""):
        return path
    prefix = offset.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


def collect_changed_paths(
    executable: str, cwd: str, env: dict[str, str], base_rev: str, workspace_root: str
) -> list[ChangedPath]:
    """基準版から現在（working tree）までの変更集合をworkspace root相対pathで返す（`check.md §5`）。

    変更集合は次3つの和集合である（安全な入出力仕様 §6、check.md §5）。

    - 基準版からindex（`git diff --cached <base>`）
    - indexからworking tree（`git diff`、引数なし）
    - 未追跡かつ非ignore path（`git ls-files --others --exclude-standard`）

    `git diff <base>`（working treeと基準版の直接比較）1回では、stageした後にworking treeを
    基準版の内容へ戻したpath（index差分はあるがbase→working tree差分がない）が消えるため、
    2回のdiffを別々に取って和集合にする（上の1つ目・2つ目）。

    出力はNUL区切り（``-z``）で読む。`--no-optional-locks`と組み合わせても、通常のtab区切り
    出力はfile名にtab・改行・非ASCIIを含む場合にquotePathで` "..."`へ変換され読み違える
    （安全な入出力仕様 §6の正規化がpath全体を対象にする以上、原文のbyte列で受け取る必要がある）。

    `git diff`はrepository root相対pathを返すが、`git ls-files`は既定でcurrent directory相対に
    なるため`--full-name`でrepository root相対へ揃える。そのうえでworkspace rootとの相対offsetを
    引いてworkspace root相対へ変換し、workspace root外のpathは変更集合から除外する（TASK
    `changes`はworkspace内pathしか宣言できず、境界外のtracked path表記を持たないため）。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)

    raw: list[ChangedPath] = []
    raw.extend(_diff_name_status_z(executable, cwd, env, ["--cached", base_rev]))
    raw.extend(_diff_name_status_z(executable, cwd, env, []))
    raw.extend(_ls_files_others_z(executable, cwd, env))

    changed: list[ChangedPath] = []
    seen: set[tuple[str, str, str | None]] = set()
    for c in raw:
        entry: ChangedPath | None
        if c.status == "R" and c.old_path is not None:
            new_path = _to_workspace_relative(c.path, offset)
            old_path = _to_workspace_relative(c.old_path, offset)
            if new_path is not None and old_path is not None:
                entry = ChangedPath(status="R", path=new_path, old_path=old_path)
            elif old_path is not None:
                # destinationがworkspace外: workspace側からはdeletion相当。
                entry = ChangedPath(status="D", path=old_path)
            elif new_path is not None:
                # sourceがworkspace外: workspace側からはaddition相当。
                entry = ChangedPath(status="A", path=new_path)
            else:
                entry = None
        else:
            p = _to_workspace_relative(c.path, offset)
            entry = ChangedPath(status=c.status, path=p) if p is not None else None
        if entry is None:
            continue
        key = (entry.status, entry.path, entry.old_path)
        if key in seen:
            continue
        seen.add(key)
        changed.append(entry)

    return changed


def is_config_tracked(executable: str, cwd: str, env: dict[str, str], path: str) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "--error-unmatch", path], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
