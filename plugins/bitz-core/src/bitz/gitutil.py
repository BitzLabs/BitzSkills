"""Gitの検出とリビジョンの解決。

`Core実行環境・CLI基盤契約 §4` に従い、Git CLIを引数列で直接起動する。シェルを使わない。
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
    """Gitの変更集合の1件（`03_操作仕様/02_check.md` §5）。

    ``status``は``A``（追加。未追跡を含む）、``M``（変更）、``D``（削除）、``R``（リネーム）のいずれか。
    ``path``は現在版のパス（削除は基準版のパス）、``old_path``はリネームの旧パスだけに設定する。
    """

    status: str
    path: str
    old_path: str | None = None


def _parse_name_status_z(output: str) -> list[ChangedPath]:
    """``git diff -z --name-status``の出力を解析する（NUL区切り。`quotePath`でパスが化けない）。"""

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
    """リポジトリのルートから見た``workspace_root``の相対パス（``.``＝一致）を返す。

    リポジトリのルートを解決できなければ``None``を返し、呼び出し側はリポジトリのルートからの相対の
    パスをそのままワークスペースのルートからの相対として扱う（フォールバック。単一ワークスペースの検査対象のリポジトリの
    大半はワークスペースのルート＝リポジトリのルートであるため、この場合は実害がない）。
    """

    toplevel = show_toplevel(executable, cwd, env)
    if toplevel is None:
        return None
    toplevel_abs = os.path.abspath(toplevel)
    workspace_abs = os.path.abspath(workspace_root)
    rel = os.path.relpath(workspace_abs, toplevel_abs)
    return rel.replace(os.sep, "/")


def _to_workspace_relative(path: str, offset: str | None) -> str | None:
    """リポジトリのルートからの相対``path``をワークスペースのルートからの相対へ変換する。ワークスペースのルートの外なら``None``。"""

    if offset is None or offset in (".", ""):
        return path
    prefix = offset.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


def collect_changed_paths(
    executable: str, cwd: str, env: dict[str, str], base_rev: str, workspace_root: str
) -> list[ChangedPath]:
    """基準版から現在（作業ツリー）までの変更集合を、ワークスペースのルートからの相対パスで返す（`check.md §5`）。

    変更集合は次の3つの和集合である（安全な入出力 §6、check.md §5）。

    - 基準版からインデックス（`git diff --cached <base>`）
    - インデックスから作業ツリー（`git diff`、引数なし）
    - 未追跡で、Gitが無視しないパス（`git ls-files --others --exclude-standard`）

    `git diff <base>`（作業ツリーと基準版の直接の比較）1回では、ステージした後に作業ツリーを
    基準版の内容へ戻したパス（インデックスの差分はあるが基準版→作業ツリーの差分がない）が消えるため、
    2回の`git diff`を別々に取って和集合にする（上の1つ目・2つ目）。

    出力はNUL区切り（``-z``）で読む。`--no-optional-locks`と組み合わせても、通常のタブ区切りの
    出力はファイル名にタブ・改行・非ASCIIを含む場合に`quotePath`で` "..."`へ変換され、読み違える
    （安全な入出力 §6の正規化がパス全体を対象にする以上、原文のバイト列で受け取る必要がある）。

    `git diff`はリポジトリのルートからの相対パスを返すが、`git ls-files`は既定で現在のディレクトリからの相対に
    なるため`--full-name`でリポジトリのルートからの相対へ揃える。そのうえでワークスペースのルートとの相対オフセットを
    引いてワークスペースのルートからの相対へ変換し、ワークスペースのルートの外のパスは変更集合から除外する（TASK
    の`changes`はワークスペース内のパスしか宣言できず、境界外の追跡対象のパスの表記を持たないため）。
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
                # 移動先がワークスペースの外: ワークスペース側からは削除に相当。
                entry = ChangedPath(status="D", path=old_path)
            elif new_path is not None:
                # 移動元がワークスペースの外: ワークスペース側からは追加に相当。
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


def list_base_spec_paths(
    executable: str, cwd: str, env: dict[str, str], base_rev: str, workspace_root: str
) -> list[str]:
    """``base_rev``の時点の``.spec/``配下のファイルの一覧を、ワークスペースのルートからの相対パスで返す（`check.md §5・§9`）。

    `git ls-tree -r`はツリーオブジェクトの構造をたどるだけで`cwd`に依存しない。返るパスは常にリポジトリのルートからの相対で
    あるため、:func:`collect_changed_paths`と同じくワークスペースのルートとの相対オフセットを引いて変換する。
    シンボリックリンク（モード ``120000``）は仕様文書として扱わない（ワークスペース・設定仕様 §1-5と同じ規則）。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)
    if offset in (None, ".", ""):
        subdir = ".spec"
    else:
        subdir = f"{offset.rstrip('/')}/.spec"
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-tree", "-r", "-z", base_rev, "--", subdir],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    tokens = proc.stdout.split("\0")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    out: list[str] = []
    for tok in tokens:
        if "\t" not in tok:
            continue
        meta, path = tok.split("\t", 1)
        parts = meta.split(" ")
        if len(parts) < 2:
            continue
        mode, obj_type = parts[0], parts[1]
        if obj_type != "blob" or mode == "120000":
            continue
        rel = _to_workspace_relative(path, offset)
        if rel is not None:
            out.append(rel)
    return out


def show_base_file(
    executable: str,
    cwd: str,
    env: dict[str, str],
    base_rev: str,
    workspace_root: str,
    workspace_rel_path: str,
) -> bytes | None:
    """``base_rev``の時点の``workspace_rel_path``の内容をバイト列で返す（存在しなければ``None``）。

    ``git show``の出力をバイト列のまま受け取り、エンコーディングの復号は呼び出し側（`document.py`）へ委ねる
    （`SPEC-INPUT-READ-001`のUTF-8検査と同じ経路を再利用するため）。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)
    if offset in (None, ".", ""):
        repo_path = workspace_rel_path
    else:
        repo_path = f"{offset.rstrip('/')}/{workspace_rel_path}"
    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "show", f"{base_rev}:{repo_path}"],
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def base_tree_entry_mode(
    executable: str, cwd: str, env: dict[str, str], rev: str, workspace_root: str, workspace_rel_path: str
) -> str | None:
    """``rev``の時点の``workspace_rel_path``のGitのモードを返す（`120000`＝シンボリックリンク）。不在なら``None``。

    複合ワークスペース仕様 §5.2「基準版のシンボリックリンクはGitのツリーオブジェクトのモードとリンク先から解決する」を実装する。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)
    if offset in (None, ".", ""):
        repo_path = workspace_rel_path
    else:
        repo_path = f"{offset.rstrip('/')}/{workspace_rel_path}"
    try:
        proc = _run([executable, "--no-optional-locks", "ls-tree", rev, "--", repo_path], cwd, env)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    line = proc.stdout.strip().split("\n")[0] if proc.stdout.strip() else ""
    if not line:
        return None
    meta, _, _path = line.partition("\t")
    parts = meta.split(" ")
    return parts[0] if parts and parts[0] else None


def list_tree_config_paths(executable: str, cwd: str, env: dict[str, str], rev: str) -> list[str]:
    """``rev``の時点でGitが認識する``.spec/bitz.yaml``の、リポジトリのルートからの相対パスを返す（`複合ワークスペース仕様 §8`）。

    シンボリックリンク（モード ``120000``）とGitのサブモジュールの`gitlink`（モード ``160000``）は対象にしない。
    """

    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-tree", "-r", "-z", rev], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    tokens = proc.stdout.split("\0")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    out: list[str] = []
    for tok in tokens:
        if "\t" not in tok:
            continue
        meta, path = tok.split("\t", 1)
        parts = meta.split(" ")
        if len(parts) < 2:
            continue
        mode, obj_type = parts[0], parts[1]
        if obj_type != "blob" or mode == "120000":
            continue
        if path == ".spec/bitz.yaml" or path.endswith("/.spec/bitz.yaml"):
            out.append(path)
    return out


def list_working_config_paths(executable: str, cwd: str, env: dict[str, str]) -> list[str]:
    """現在のスナップショット（作業ツリー）でGitが認識する``.spec/bitz.yaml``の、リポジトリのルートからの相対パスを返す。

    追跡対象／ステージ済みのパス（``git ls-files``）と、未追跡で、Gitが無視しないパス（``ls-files --others``）の
    和集合を対象にする（`複合ワークスペース仕様 §8`）。``git ls-files``はインデックス上の追跡対象のパスを
    作業ツリーでの実在の有無に関わらず返すため、`.spec/bitz.yaml`へ実際に作業ツリーで
    到達できるパスだけへ絞る（複合ワークスペース仕様 §8「作業ツリーに存在する追跡対象またはステージ済みのパス」。
    ファイル移動後の旧パスがインデックス上に残っていても、作業ツリー上は既に存在しないため対象にしない）。
    """

    toplevel = show_toplevel(executable, cwd, env)
    root = os.path.abspath(toplevel) if toplevel else os.path.abspath(cwd)

    paths: set[str] = set()
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "-z", "--full-name"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0:
        tokens = proc.stdout.split("\0")
        for p in tokens:
            if p:
                paths.add(p)
    for c in _ls_files_others_z(executable, cwd, env):
        paths.add(c.path)
    return sorted(
        p
        for p in paths
        if (p == ".spec/bitz.yaml" or p.endswith("/.spec/bitz.yaml"))
        and os.path.isfile(os.path.join(root, *p.split("/")))
        and not os.path.islink(os.path.join(root, *p.split("/")))
    )


def list_submodule_paths(executable: str, cwd: str, env: dict[str, str]) -> set[str]:
    """作業ツリーのインデックスに`gitlink`（モード ``160000``）として記録された、リポジトリのルートからの相対パスを返す。"""

    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "-z", "--full-name", "--stage"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode != 0:
        return set()
    tokens = proc.stdout.split("\0")
    out: set[str] = set()
    for tok in tokens:
        if not tok or "\t" not in tok:
            continue
        meta, path = tok.split("\t", 1)
        parts = meta.split(" ")
        if parts and parts[0] == "160000":
            out.add(path)
    return out


def list_worktree_paths(executable: str, cwd: str, env: dict[str, str]) -> set[str]:
    """``git worktree list``が返すすべてのワークツリーの実パス（絶対パス）の集合を返す（自身を含む）。"""

    try:
        proc = _run(
            [executable, "--no-optional-locks", "worktree", "list", "--porcelain"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode != 0:
        return set()
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(os.path.abspath(line[len("worktree ") :].strip()))
    return out


def is_config_tracked(executable: str, cwd: str, env: dict[str, str], path: str) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "--error-unmatch", path], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
