"""Gitの検出とリビジョンの解決。

`Core実行環境・CLI基盤契約 §4` に従い、Git CLIを引数列で直接起動する。シェルを使わない。
"""

from __future__ import annotations

import os
import selectors
import shutil
import subprocess
import time
from dataclasses import dataclass

MIN_GIT_MAJOR = 2
MIN_GIT_MINOR = 30


@dataclass
class GitInfo:
    available: bool
    executable: str | None = None
    version: tuple[int, int] | None = None


#: 部分クローンの遅延取得を止める環境変数（Core実行環境・CLI基盤契約 §4、ADR-082の決定1）。
#:
#: - ``GIT_NO_LAZY_FETCH=1``: 遅延取得そのものを止める（新しいGitが解する変数）。
#: - ``GIT_ALLOW_PROTOCOL``: 値の一覧にない転送をすべて禁じる（`git help git`の環境変数の節。`protocol.allow`を`never`にし、
#:   一覧の転送だけを許すのと同じで、既存の設定より優先する）。実在しない名前だけを置くので、`file`を含むすべての転送を禁じ、
#:   ``GIT_NO_LAZY_FETCH``を解さない版のGitでも、遅延取得の取得が転送の段階で失敗する。
#:
#: 欠けたオブジェクトは、Gitから読めないものとして扱う。
NO_FETCH_ENV: dict[str, str] = {"GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "bitz-no-transport"}


def git_env(env: dict[str, str]) -> dict[str, str]:
    """Coreが起動するGitへ渡す環境変数（``env``に:data:`NO_FETCH_ENV`を重ねる）。``env``自体は変えない。

    Gitの呼出しだけに使い、`verify`が起動するテストのコマンドの環境には加えない。
    """

    return {**env, **NO_FETCH_ENV}


def _run(argv: list[str], cwd: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=git_env(env),
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


def is_dirty(executable: str, cwd: str, env: dict[str, str], *, strict: bool = False) -> bool:
    """作業ツリーの状態（`revision.dirty`）。``strict``（`check`）なら、読取りの失敗を``False``にせず:class:`GitChangesError`にする
    （`check` §5、ADR-083の`Notes`）。``strict``が偽の呼出し（`context`、`verify`）は、従来どおり失敗を``False``にする。"""

    try:
        proc = _run(
            [executable, "--no-optional-locks", "status", "--porcelain"], cwd, env
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        if strict:
            raise GitChangesError(f"git status: {exc}") from exc
        return False
    if proc.returncode != 0:
        if strict:
            raise GitChangesError(f"git status: 終了コード{proc.returncode}")
        return False
    return bool(proc.stdout.strip())


def check_revision(
    executable: str, cwd: str, env: dict[str, str], base_arg: str | None
) -> tuple[str | None, str | None, bool]:
    """`check`の``(HEAD, 基準版, dirty)``を求める（`check` §5、ADR-083の`Notes`）。``HEAD``がなければ``(None, 基準版, False)``。

    - ``cwd``がリポジトリの外なら（:func:`repository_toplevel`）、``HEAD``はないものとする。
    - ``HEAD``がコミットを指さない場合は、Gitがその参照の不在を示したとき（:func:`head_is_unborn`。コミットのないリポジトリ）だけ、
      ``HEAD``はないものとする。そのほか（壊れた参照、参照の先のコミットの欠落）は:class:`GitChangesError`を送出する。
    - 作業ツリーの状態の読取りの失敗も:class:`GitChangesError`にする（``dirty``を偽にしない）。
    - ``base_arg``（明示した`--base`）を解決できなければ、基準版は``None``（呼び出し側が終了コード4にする）。省略なら``HEAD``。
    """

    if repository_toplevel(executable, cwd, env) is None:
        head = None
    else:
        head = resolve_commit(executable, cwd, env, "HEAD")
        if head is None:
            try:
                unborn = head_is_unborn(executable, cwd, env)
            except GitReadError as exc:
                raise GitChangesError(str(exc)) from exc
            if not unborn:
                raise GitChangesError("HEADを解決できません")
    base = head if base_arg is None else resolve_commit(executable, cwd, env, base_arg)
    dirty = is_dirty(executable, cwd, env, strict=True) if head is not None else False
    return head, base, dirty


@dataclass
class ChangedPath:
    """Gitの変更集合の1件（`03_操作仕様/02_check.md` §5）。

    ``status``は``A``（追加。未追跡を含む）、``M``（変更）、``D``（削除）のいずれか。名前の変更は検出せず、移動元の``D``と移動先の``A``の
    2件になる（ADR-083の決定1）。``path``は現在版のパス（削除は基準版のパス）。:func:`collect_changed_paths`は``old_path``を設定しない
    （単体試験などが組み立てる``R``の項目は、呼び出し側が移動元と移動先の両方のパスとして扱う）。
    """

    status: str
    path: str
    old_path: str | None = None


class GitChangesError(Exception):
    """変更集合、または入れ子のワークスペースの判定に使う設定のパスの一覧をGitから求められない（`check` §5、ADR-083の決定3）。

    Gitの起動の失敗、0でない終了コード、出力の形の不正のどれか。呼び出し側は空の結果として扱わず、単一ワークスペースでは
    `SPEC-GIT-CHANGES-001`、複合ワークスペースでは`SPEC-MULTI-GIT-001`として操作を止める。
    """


def _parse_name_status_z(output: str) -> list[ChangedPath]:
    """``git diff -z --name-status --no-renames``の出力を解析する（NUL区切り。`quotePath`でパスが化けない）。

    名前の変更とコピーを検出しないので、項目はどれも1つのパスを持つ。名前の変更またはコピーの項目（`R`、`C`）、パスのない項目など、
    形の不正な出力は:class:`GitChangesError`にする（黙って読み飛ばさない）。
    """

    tokens = output.split("\0")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    changed: list[ChangedPath] = []
    i = 0
    n = len(tokens)
    while i < n:
        code = tokens[i]
        if not code or code[0] in ("R", "C") or i + 1 >= n or not tokens[i + 1]:
            raise GitChangesError("git diff --name-statusの出力の形が不正です")
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
    """変更集合の1つの差分を求める。名前の変更とコピーを検出しない（`--no-renames`。Gitの設定`diff.renames`によらない。ADR-083の決定1）。

    名前の変更の検出をしないので、ファイルの内容のオブジェクトを読まない（部分クローンで欠けたブロブがあっても失敗しない）。
    失敗は:class:`GitChangesError`にする（ADR-083の決定3）。
    """

    try:
        proc = _run(
            [executable, "--no-optional-locks", "diff", "-z", "--no-color", "--no-relative", "--no-renames",
             "--no-ext-diff", "--name-status", *extra_args],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitChangesError(str(exc)) from exc
    if proc.returncode != 0:
        raise GitChangesError(f"git diff: 終了コード{proc.returncode}")
    return _parse_name_status_z(proc.stdout)


def _ls_files_others_z(
    executable: str, cwd: str, env: dict[str, str], toplevel: str | None = None, *, strict: bool = False
) -> list[ChangedPath]:
    """未追跡で、Gitが無視しないパスの一覧。``strict``（変更集合）なら、失敗を:class:`GitChangesError`にする（ADR-083の決定3）。

    ``strict``が偽の呼出し（複合ワークスペースの全体事前検査の設定のパスの一覧）は、従来どおり失敗を空の一覧にする。
    """

    # `git ls-files`は現在のディレクトリの配下しか列挙しないため、リポジトリのルートで実行する。
    cwd = _toplevel_or_cwd(executable, cwd, env, toplevel)
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
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        if strict:
            raise GitChangesError(str(exc)) from exc
        return []
    if proc.returncode != 0:
        if strict:
            raise GitChangesError(f"git ls-files: 終了コード{proc.returncode}")
        return []
    tokens = proc.stdout.split("\0")
    return [ChangedPath(status="A", path=p) for p in tokens if p]


def _toplevel_or_cwd(executable: str, cwd: str, env: dict[str, str], toplevel: str | None = None) -> str:
    """リポジトリのルートを返す。``toplevel``が渡されていれば、Gitを呼ばずにそれを返す。解決できなければ:class:`GitToplevelError`を送出する。

    `git ls-files`は現在のディレクトリの配下だけを列挙するため、リポジトリ全体を対象にする呼び出しはこのディレクトリで実行する。
    """

    if toplevel:
        return toplevel
    toplevel = show_toplevel(executable, cwd, env)
    if not toplevel:
        # 読めないリポジトリのルートを`cwd`で代えない（`check` §5、ADR-083の`Notes`）。
        raise GitToplevelError("リポジトリのルートを求められません")
    return toplevel


def _repo_root_relative_offset(
    executable: str, cwd: str, env: dict[str, str], workspace_root: str, toplevel: str | None = None
) -> str | None:
    """リポジトリのルートから見た``workspace_root``の相対パス（``.``＝一致）を返す。

    リポジトリのルートを解決できなければ、:class:`GitToplevelError`を送出する（リポジトリのルートからの相対のパスを
    ワークスペースのルートからの相対として扱わない。`check` §5、ADR-083の`Notes`）。
    """

    if toplevel is None:
        toplevel = show_toplevel(executable, cwd, env)
    if toplevel is None:
        raise GitToplevelError("リポジトリのルートを求められません")
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

    名前の変更とコピーは検出しない（ADR-083の決定1）。名前の変更は、移動元のパスの削除（`D`）と移動先のパスの追加（`A`）として入る。
    ワークスペースの内と外の間の移動は、内側のパスだけが残る（内から外は削除、外から内は追加）。3つの読取りのどれかが失敗すれば、
    :class:`GitChangesError`を送出する（空の変更集合にしない。ADR-083の決定3）。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)

    raw: list[ChangedPath] = []
    raw.extend(_diff_name_status_z(executable, cwd, env, ["--cached", base_rev]))
    raw.extend(_diff_name_status_z(executable, cwd, env, []))
    raw.extend(_ls_files_others_z(executable, cwd, env, strict=True))

    changed: list[ChangedPath] = []
    seen: set[tuple[str, str]] = set()
    for c in raw:
        p = _to_workspace_relative(c.path, offset)
        if p is None:
            continue
        key = (c.status, p)
        if key in seen:
            continue
        seen.add(key)
        changed.append(ChangedPath(status=c.status, path=p))

    return changed


def list_base_spec_paths(
    executable: str, cwd: str, env: dict[str, str], base_rev: str, workspace_root: str
) -> list[str]:
    """``base_rev``の時点の``.spec/``配下のファイルの一覧を、ワークスペースのルートからの相対パスで返す（`check.md §5・§9`）。

    `git ls-tree`は既定でパスの指定と出力を現在のディレクトリからの相対で扱い、現在のディレクトリの配下だけを列挙する。
    `--full-tree`でどちらもリポジトリのルートからの相対にそろえ、:func:`collect_changed_paths`と同じくワークスペースのルートとの
    相対オフセットを引いて変換する。
    シンボリックリンク（モード ``120000``）は仕様文書として扱わない（ワークスペース・設定仕様 §1-5と同じ規則）。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)
    if offset in (None, ".", ""):
        subdir = ".spec"
    else:
        subdir = f"{offset.rstrip('/')}/.spec"
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-tree", "--full-tree", "-r", "-z", base_rev, "--", subdir],
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


def list_base_spec_blobs(
    executable: str, cwd: str, env: dict[str, str], base_rev: str, workspace_root: str
) -> list[tuple[str, str]] | None:
    """``base_rev``の時点の``.spec/``配下の通常のファイルを、``(ワークスペースのルートからの相対パス, オブジェクトID)``で返す。

    :func:`list_base_spec_paths`と同じ規則で列挙する（`--full-tree`、シンボリックリンクとサブモジュールを除く）。ただし、Gitが失敗した場合
    （ツリーオブジェクトの欠落など）は空の一覧ではなく``None``を返す（基準版の仕様文書の一覧を読めない。`check` §5、ADR-082の決定2）。
    ファイルの大きさを求めない（`-l`を使わない）ので、ファイルの内容のオブジェクトは読まない。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root)
    subdir = ".spec" if offset in (None, ".", "") else f"{offset.rstrip('/')}/.spec"
    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "--literal-pathspecs", "ls-tree", "--full-tree", "-r", "-z",
             base_rev, "--", subdir],
            cwd=cwd, env=git_env(env), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out: list[tuple[str, str]] = []
    for tok in proc.stdout.split(b"\0"):
        if not tok:
            continue
        if b"\t" not in tok:
            return None
        meta, raw_path = tok.split(b"\t", 1)
        parts = meta.split()
        if len(parts) < 3:
            return None
        mode, obj_type, oid = parts[0], parts[1], parts[2]
        if obj_type != b"blob" or mode == b"120000":
            continue
        rel = _to_workspace_relative(raw_path.decode("utf-8", "surrogateescape"), offset)
        if rel is not None:
            out.append((rel, oid.decode("ascii")))
    return out


#: :func:`list_base_config_dirs`が1回の`git ls-tree`へ渡すパスの数の上限（引数列の長さの上限を超えないため）。
_LS_TREE_PATH_CHUNK = 512


def list_base_config_dirs(
    executable: str,
    cwd: str,
    env: dict[str, str],
    base_rev: str,
    workspace_root: str,
    dirs: list[str],
    toplevel: str | None = None,
) -> set[str]:
    """``dirs``（ワークスペースのルートからの相対のディレクトリ）のうち、``base_rev``で``<dir>/.spec/bitz.yaml``を
    通常のファイルとして持つものを返す（`check.md §7`の入れ子のワークスペース。ADR-074）。

    基準版のツリーだけを見て、作業ツリーとインデックスは読まない。``git ls-tree``へ候補の設定のパスだけを渡し
    （`--full-tree`でリポジトリのルートからの相対。`--literal-pathspecs`でパスの`*`などを字句どおりに扱う）、
    基準版の全体を列挙しない。モード``120000``（シンボリックリンク）と、ブロブでないエントリ（`.spec/bitz.yaml`という名前の
    ディレクトリ、`gitlink`）は数えない。途中のセグメントがシンボリックリンクのパスは、Gitがツリーをたどらないので現れない。
    設定の内容は読まない。Gitの呼出しが失敗した場合（起動の失敗、0でない終了コード、出力の形の不正）は、設定を持たないものとせず、
    :class:`GitChangesError`を送出する（入れ子のワークスペースの判定に使う設定のパスの一覧。`check` §5、ADR-083の決定3）。
    """

    if not dirs:
        return set()
    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel)
    prefix = "" if offset in (None, ".", "") else offset.rstrip("/") + "/"
    by_repo_path = {f"{prefix}{d}/.spec/bitz.yaml": d for d in dirs}
    repo_paths = sorted(by_repo_path)
    found: set[str] = set()
    for start in range(0, len(repo_paths), _LS_TREE_PATH_CHUNK):
        chunk = repo_paths[start : start + _LS_TREE_PATH_CHUNK]
        try:
            proc = _run(
                [
                    executable, "--no-optional-locks", "--literal-pathspecs",
                    "ls-tree", "--full-tree", "-z", base_rev, "--", *chunk,
                ],
                cwd,
                env,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise GitChangesError(str(exc)) from exc
        if proc.returncode != 0:
            raise GitChangesError(f"git ls-tree: 終了コード{proc.returncode}")
        for tok in proc.stdout.split("\0"):
            if not tok:
                continue
            if "\t" not in tok:
                raise GitChangesError("git ls-treeの出力の形が不正です")
            meta, path = tok.split("\t", 1)
            parts = meta.split(" ")
            if len(parts) < 2 or parts[1] != "blob" or parts[0] == "120000":
                continue
            d = by_repo_path.get(path)
            if d is not None:
                found.add(d)
    return found


def show_base_file(
    executable: str,
    cwd: str,
    env: dict[str, str],
    base_rev: str,
    workspace_root: str,
    workspace_rel_path: str,
    toplevel: str | None = None,
) -> bytes | None:
    """``base_rev``の時点の``workspace_rel_path``の内容をバイト列で返す（存在しなければ``None``）。

    ``git show``の出力をバイト列のまま受け取り、エンコーディングの復号は呼び出し側（`document.py`）へ委ねる
    （`SPEC-INPUT-READ-001`のUTF-8検査と同じ経路を再利用するため）。
    ``toplevel``はすでに求めたリポジトリのルート。渡すと、ルートを求めるGitの呼び出しを省く。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel)
    if offset in (None, ".", ""):
        repo_path = workspace_rel_path
    else:
        repo_path = f"{offset.rstrip('/')}/{workspace_rel_path}"
    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "show", f"{base_rev}:{repo_path}"],
            cwd=cwd,
            env=git_env(env),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def head_is_unborn(executable: str, cwd: str, env: dict[str, str]) -> bool:
    """``HEAD``がまだコミットを持たない枝（コミットのないリポジトリなど）を指すかを、Gitの出力で判定する。

    `git rev-parse --verify --quiet HEAD^{commit}`が成功すれば偽。失敗した場合は、`git symbolic-ref -q HEAD`で枝の名前を得て、
    `git for-each-ref`がその参照を1つも返さなければ真（Gitが参照の不在を示した）。そのほかの場合（切り離した`HEAD`を解決できない、
    参照はあるのにコミットを解決できない、Gitの呼出しの失敗）は、:class:`GitReadError`を送出する（複合ワークスペース仕様 §2、ADR-083の`Notes`）。
    """

    def run(*args: str) -> subprocess.CompletedProcess:
        try:
            return _run([executable, "--no-optional-locks", *args], cwd, env)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise GitReadError(f"git {args[0]}: {exc}") from exc

    if run("rev-parse", "--verify", "--quiet", "HEAD^{commit}").returncode == 0:
        return False
    sym = run("symbolic-ref", "-q", "HEAD")
    ref = sym.stdout.strip()
    if sym.returncode != 0 or not ref.startswith("refs/"):
        raise GitReadError("HEADを解決できません")
    listed = run("for-each-ref", "--format=%(refname)", ref)
    if listed.returncode != 0:
        raise GitReadError(f"git for-each-ref: 終了コード{listed.returncode}")
    if ref in listed.stdout.split("\n"):
        raise GitReadError("HEADの参照はあるがコミットを解決できません")
    return True


#: :func:`read_tree_file`の結果: Gitがそのパスの不在を示した（リビジョンのツリーに、そのパスの項目がない）。
TREE_FILE_ABSENT = "absent"
#: :func:`read_tree_file`の結果: そのパスの項目はあるが、通常のファイルでない（ディレクトリ、シンボリックリンク、`gitlink`）。
TREE_FILE_NOT_REGULAR = "not-regular"
#: :func:`read_tree_file`の結果: 通常のファイルの内容を読めた。
TREE_FILE_READ = "read"


def read_tree_file(
    executable: str,
    cwd: str,
    env: dict[str, str],
    rev: str,
    workspace_root: str,
    workspace_rel_path: str,
    toplevel: str | None = None,
) -> tuple[str, bytes | None]:
    """``rev``の時点の``workspace_rel_path``を読み、``(結果, 内容)``を返す（複合ワークスペース仕様 §2、ADR-083の`Notes`）。

    不在と読取りの失敗を、Gitの出力で区別する。

    1. `git ls-tree --full-tree -z <rev> -- <パス>`（`--literal-pathspecs`）を実行する。終了コード0で項目がなければ、Gitがそのパスの不在を
       示したものとし、``(TREE_FILE_ABSENT, None)``を返す（途中のディレクトリがない場合も同じ）。項目が通常のファイル（種類`blob`で
       モード``120000``でない）でなければ``(TREE_FILE_NOT_REGULAR, None)``。
    2. 通常のファイルなら、`git cat-file blob <オブジェクトID>`で内容を読み、``(TREE_FILE_READ, 内容)``を返す。

    Gitの起動の失敗、0でない終了コード（リビジョンやツリーのオブジェクトの欠落を含む）、出力の形の不正、内容のオブジェクトの欠落は、
    :class:`GitReadError`を送出する（不在としない）。`git show <rev>:<パス>`は、パスの不在とオブジェクトの欠落をどちらも0でない終了コードで
    返し区別できないので使わない。
    """

    offset = _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel)
    repo_path = workspace_rel_path if offset in (None, ".", "") else f"{offset.rstrip('/')}/{workspace_rel_path}"
    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "--literal-pathspecs", "ls-tree", "--full-tree", "-z", rev, "--", repo_path],
            cwd=cwd, env=git_env(env), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitReadError(f"git ls-tree: {exc}") from exc
    if proc.returncode != 0:
        raise GitReadError(f"git ls-tree: 終了コード{proc.returncode}")
    entries = [tok for tok in proc.stdout.split(b"\0") if tok]
    target = os.fsencode(repo_path)
    entry = None
    for tok in entries:
        if b"\t" not in tok:
            raise GitReadError("git ls-treeの出力の形が不正です")
        meta, raw_path = tok.split(b"\t", 1)
        parts = meta.split()
        if len(parts) != 3:
            raise GitReadError("git ls-treeの出力の形が不正です")
        if raw_path == target:
            entry = parts
    if entry is None:
        if entries:
            # 指定したパスと異なる項目だけが返った（出力の形の不正）。
            raise GitReadError("git ls-treeの出力の形が不正です")
        return TREE_FILE_ABSENT, None
    mode, obj_type, oid = entry
    if obj_type != b"blob" or mode == b"120000":
        return TREE_FILE_NOT_REGULAR, None
    try:
        blob = subprocess.run(
            [executable, "--no-optional-locks", "cat-file", "blob", oid.decode("ascii")],
            cwd=cwd, env=git_env(env), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitReadError(f"git cat-file: {exc}") from exc
    if blob.returncode != 0:
        raise GitReadError(f"git cat-file: 終了コード{blob.returncode}")
    return TREE_FILE_READ, blob.stdout


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
        proc = _run([executable, "--no-optional-locks", "ls-tree", "--full-tree", rev, "--", repo_path], cwd, env)
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


def _map_to_scope(paths: list[str], offset: str | None) -> list[str]:
    """リポジトリのルートからの相対パスを、複合ワークスペースのルートからの相対へ写す。ルートの外のパスは除く（ADR-064の6）。"""

    if offset in (None, ".", ""):
        return paths
    return [mapped for p in paths if (mapped := _to_workspace_relative(p, offset)) is not None]


def list_tree_config_paths(
    executable: str, cwd: str, env: dict[str, str], rev: str, workspace_root: str | None = None,
    toplevel: str | None = None,
) -> list[str]:
    """``rev``の時点でGitが認識する``.spec/bitz.yaml``の、複合ワークスペースのルートからの相対パスを返す（`複合ワークスペース仕様 §8`）。

    ``workspace_root``は複合ワークスペースのルート（絶対パス）。省略時はリポジトリのルート。入れ子の複合ワークスペースでは
    リポジトリのルートからの相対パスを入れ子のルートからの相対へ写し、ルートの外のパスは返さない（§2.1）。
    シンボリックリンク（モード ``120000``）とGitのサブモジュールの`gitlink`（モード ``160000``）は対象にしない。

    読取りが失敗した場合（Gitの起動の失敗、0でない終了コード、出力の形の不正）は、空の一覧とせず:class:`GitReadError`を送出する
    （複合ワークスペース仕様 §2、ADR-083の`Notes`。呼び出し側の全体事前検査が`SPEC-MULTI-GIT-001`にする）。
    """

    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-tree", "--full-tree", "-r", "-z", rev], cwd, env
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitReadError(f"git ls-tree: {exc}") from exc
    if proc.returncode != 0:
        raise GitReadError(f"git ls-tree: 終了コード{proc.returncode}")
    tokens = proc.stdout.split("\0")
    if tokens and tokens[-1] == "":
        tokens = tokens[:-1]
    out: list[str] = []
    for tok in tokens:
        if "\t" not in tok:
            raise GitReadError("git ls-treeの出力の形が不正です")
        meta, path = tok.split("\t", 1)
        parts = meta.split(" ")
        if len(parts) < 2:
            raise GitReadError("git ls-treeの出力の形が不正です")
        mode, obj_type = parts[0], parts[1]
        if obj_type != "blob" or mode == "120000":
            continue
        if path == ".spec/bitz.yaml" or path.endswith("/.spec/bitz.yaml"):
            out.append(path)
    if workspace_root is None:
        return out
    return _map_to_scope(out, _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel))


def list_working_config_paths(
    executable: str, cwd: str, env: dict[str, str], workspace_root: str | None = None,
    toplevel: str | None = None,
) -> list[str]:
    """現在のスナップショット（作業ツリー）でGitが認識する``.spec/bitz.yaml``の、複合ワークスペースのルートからの相対パスを返す。

    ``workspace_root``の扱いは :func:`list_tree_config_paths` と同じ（入れ子の複合ワークスペースのルートからの相対へ写す）。

    追跡対象／ステージ済みのパス（``git ls-files``）と、未追跡で、Gitが無視しないパス（``ls-files --others``）の
    和集合を対象にする（`複合ワークスペース仕様 §8`）。``git ls-files``はインデックス上の追跡対象のパスを
    作業ツリーでの実在の有無に関わらず返すため、`.spec/bitz.yaml`へ実際に作業ツリーで
    到達できるパスだけへ絞る（複合ワークスペース仕様 §8「作業ツリーに存在する追跡対象またはステージ済みのパス」。
    ファイル移動後の旧パスがインデックス上に残っていても、作業ツリー上は既に存在しないため対象にしない）。

    追跡対象の一覧と未追跡の一覧のどちらかの読取りが失敗した場合は、空の一覧とせず:class:`GitReadError`を送出する
    （複合ワークスペース仕様 §2、ADR-083の`Notes`）。
    """

    root = os.path.abspath(_toplevel_or_cwd(executable, cwd, env, toplevel))

    paths: set[str] = set()
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "-z", "--full-name"], root, env
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitReadError(f"git ls-files: {exc}") from exc
    if proc.returncode != 0:
        raise GitReadError(f"git ls-files: 終了コード{proc.returncode}")
    for p in proc.stdout.split("\0"):
        if p:
            paths.add(p)
    try:
        untracked = _ls_files_others_z(executable, cwd, env, toplevel, strict=True)
    except GitChangesError as exc:
        raise GitReadError(str(exc)) from exc
    for c in untracked:
        paths.add(c.path)
    found = sorted(
        p
        for p in paths
        if (p == ".spec/bitz.yaml" or p.endswith("/.spec/bitz.yaml"))
        and os.path.isfile(os.path.join(root, *p.split("/")))
        and not os.path.islink(os.path.join(root, *p.split("/")))
    )
    if workspace_root is None:
        return found
    return _map_to_scope(found, _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel))


def list_submodule_paths(
    executable: str, cwd: str, env: dict[str, str], workspace_root: str | None = None,
    toplevel: str | None = None,
) -> set[str]:
    """作業ツリーのインデックスに`gitlink`（モード ``160000``）として記録された、複合ワークスペースのルートからの相対パスを返す。

    ``workspace_root``の扱いは :func:`list_tree_config_paths` と同じ（入れ子の複合ワークスペースのルートからの相対へ写す）。
    読取りが失敗した場合（起動の失敗、0でない終了コード、出力の形の不正）は、空の集合とせず:class:`GitReadError`を送出する
    （複合ワークスペース仕様 §2、ADR-083の`Notes`）。
    """

    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "-z", "--full-name", "--stage"],
            _toplevel_or_cwd(executable, cwd, env, toplevel),
            env,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitReadError(f"git ls-files --stage: {exc}") from exc
    if proc.returncode != 0:
        raise GitReadError(f"git ls-files --stage: 終了コード{proc.returncode}")
    tokens = proc.stdout.split("\0")
    out: set[str] = set()
    for tok in tokens:
        if not tok:
            continue
        if "\t" not in tok:
            raise GitReadError("git ls-files --stageの出力の形が不正です")
        meta, path = tok.split("\t", 1)
        parts = meta.split(" ")
        if parts and parts[0] == "160000":
            out.add(path)
    if workspace_root is None:
        return out
    return set(_map_to_scope(sorted(out), _repo_root_relative_offset(executable, cwd, env, workspace_root, toplevel)))


def list_worktree_paths(executable: str, cwd: str, env: dict[str, str]) -> set[str]:
    """``git worktree list``が返すすべてのワークツリーの実パス（絶対パス）の集合を返す（自身を含む）。

    読取りが失敗した場合（起動の失敗、0でない終了コード、出力の形の不正）は、空の集合とせず:class:`GitReadError`を送出する
    （複合ワークスペース仕様 §2、ADR-083の`Notes`）。一覧は少なくとも自身のワークツリーを含むので、`worktree`の行が1つもない出力も
    形の不正とする。
    """

    try:
        proc = _run(
            [executable, "--no-optional-locks", "worktree", "list", "--porcelain"], cwd, env
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitReadError(f"git worktree list: {exc}") from exc
    if proc.returncode != 0:
        raise GitReadError(f"git worktree list: 終了コード{proc.returncode}")
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(os.path.abspath(line[len("worktree ") :].strip()))
    if not out:
        raise GitReadError("git worktree listの出力の形が不正です")
    return out


def is_config_tracked(executable: str, cwd: str, env: dict[str, str], path: str) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "--error-unmatch", path], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# --- 基準版のスナップショットのリソースの上限（複合ワークスペース仕様 §10、`check --base`） ------------------------


@dataclass(frozen=True)
class TreeBlob:
    """Gitのツリーオブジェクトの通常のファイルの項目（オブジェクトIDとバイト数）。"""

    oid: str
    size: int


def list_tree_blobs(
    executable: str, toplevel: str, env: dict[str, str], rev: str, prefix: str
) -> dict[str, TreeBlob] | None:
    """``rev``の時点の``prefix``（リポジトリのルートからの相対のディレクトリ）の配下の通常のファイルを、
    リポジトリのルートからの相対パスをキーにして返す。シンボリックリンク（モード ``120000``）とサブモジュールの`gitlink`は除く。

    `--full-tree`でパスの指定と出力をリポジトリのルートからの相対にそろえ、`-z`でパスを原文のまま受け取る（`core.quotePath`に依存しない）。
    ``prefix``は字句どおりのパスとして扱う（`--literal-pathspecs`）。Gitが失敗したとき、出力を解釈できないとき、
    通常のファイルの大きさを得られないとき（オブジェクトの欠落）は``None``を返す。
    """

    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "--literal-pathspecs", "ls-tree", "--full-tree", "-r", "-l", "-z",
             rev, "--", prefix],
            cwd=toplevel, env=git_env(env), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out: dict[str, TreeBlob] = {}
    for tok in proc.stdout.split(b"\0"):
        if not tok:
            continue
        if b"\t" not in tok:
            return None
        meta, raw_path = tok.split(b"\t", 1)
        parts = meta.split()
        if len(parts) < 4:
            return None
        mode, obj_type, oid, size = parts[0], parts[1], parts[2], parts[3]
        if obj_type != b"blob" or mode == b"120000":
            continue
        if not size.isdigit():
            # オブジェクトを読めないとき、`ls-tree -l`は終了コード0のまま大きさを`BAD`などと出す。黙って除かず、失敗とする。
            return None
        path = raw_path.decode("utf-8", "surrogateescape")
        if path != prefix and not path.startswith(prefix.rstrip("/") + "/"):
            continue
        out[path] = TreeBlob(oid=oid.decode("ascii"), size=int(size))
    return out


class GitReadError(Exception):
    """基準版の内容をGitから読めない（起動や読取りの失敗、オブジェクトの欠落、タイムアウト）。

    呼び出し側は、数えずに通過させず、Gitを利用できない場合と同じく`SPEC-MULTI-GIT-001`にする（安全な入出力・互換性 §4.1）。
    """


class GitToplevelError(GitChangesError, GitReadError):
    """リポジトリのルート（`git rev-parse --show-toplevel`）を読めない（`check` §5、ADR-083の`Notes`）。

    変更集合のパスを写すためのリポジトリのルートの読取りの失敗であり、`cwd`で代えない。:class:`GitChangesError`としても
    :class:`GitReadError`としても捕まえられる。`check`は、単一ワークスペースで`SPEC-GIT-CHANGES-001`、複合ワークスペースで
    `SPEC-MULTI-GIT-001`にする（基準版の読取りの途中で起きても`SPEC-GIT-BASE-001`にしない）。
    """


def repository_toplevel(executable: str, cwd: str, env: dict[str, str]) -> str | None:
    """``cwd``を含む作業ツリーのリポジトリのルートを返す。``cwd``がリポジトリの中でなければ``None``。

    リポジトリの外であることは、Gitの出力で判定する。`git rev-parse --show-toplevel`を、メッセージを翻訳しないロケール
    （``LC_ALL=C``、``LANGUAGE=C``）で実行し、0でない終了コードで標準エラー出力が`not a git repository`を含む場合だけ、
    リポジトリの外とする。そのほかの失敗（起動の失敗、ほかの理由の0でない終了コード、空の出力）は、:class:`GitToplevelError`を送出する。
    """

    try:
        proc = subprocess.run(
            [executable, "--no-optional-locks", "rev-parse", "--show-toplevel"],
            cwd=cwd, env={**git_env(env), "LC_ALL": "C", "LANGUAGE": "C"}, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GitToplevelError(f"git rev-parse --show-toplevel: {exc}") from exc
    if proc.returncode != 0:
        if "not a git repository" in (proc.stderr or ""):
            return None
        raise GitToplevelError(f"git rev-parse --show-toplevel: 終了コード{proc.returncode}")
    top = proc.stdout.strip()
    if not top:
        raise GitToplevelError("git rev-parse --show-toplevelの出力が空です")
    return top


#: `git cat-file --batch`の1件の要求から内容を読み終えるまでの時間の上限（秒）。ほかのGitの呼出し（``_run``）の30秒に合わせる。
BLOB_READ_TIMEOUT_SECONDS = 30.0


class BlobReader:
    """`git cat-file --batch`で、オブジェクトIDからファイルの内容を1件ずつ読む。

    1件ごとに要求して読み切るので、内容をすべて同時に保持しない（複合ワークスペース仕様 §10.1）。
    標準出力は非ブロッキングで読み、1件の要求ごとに``timeout``秒の期限を設ける（partial cloneの遅延取得が止まった場合などに
    無期限に待たない）。起動の失敗、オブジェクトの欠落（`<oid> missing`など）、途中の終了、期限の超過は:class:`GitReadError`を送出し、
    以後の読取りもすべて:class:`GitReadError`にする。失敗したときは、終了時にプロセスを待たずに強制終了する。
    """

    def __init__(
        self, executable: str, toplevel: str, env: dict[str, str], *, timeout: float = BLOB_READ_TIMEOUT_SECONDS
    ) -> None:
        self._argv = [executable, "--no-optional-locks", "cat-file", "--batch"]
        self._cwd = toplevel
        self._env = git_env(env)
        self._timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._selector: selectors.BaseSelector | None = None
        self._buf = bytearray()
        self._failed = False

    def __enter__(self) -> "BlobReader":
        try:
            self._proc = subprocess.Popen(
                self._argv, cwd=self._cwd, env=self._env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            assert self._proc.stdout is not None
            fd = self._proc.stdout.fileno()
            os.set_blocking(fd, False)
            self._selector = selectors.DefaultSelector()
            self._selector.register(fd, selectors.EVENT_READ)
        except OSError:
            self._failed = True
        return self

    def __exit__(self, *exc) -> None:
        if self._selector is not None:
            self._selector.close()
            self._selector = None
        proc = self._proc
        if proc is None:
            return
        if self._failed:
            # 応答しないプロセスを待たない。
            try:
                proc.kill()
            except OSError:
                pass
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()

    def _fill(self, deadline: float) -> None:
        selector = self._selector
        proc = self._proc
        assert selector is not None and proc is not None and proc.stdout is not None
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not selector.select(timeout=remaining):
            raise GitReadError("git cat-file --batchが期限内に応答しません")
        try:
            chunk = os.read(proc.stdout.fileno(), 65536)
        except BlockingIOError:
            return
        if not chunk:
            raise GitReadError("git cat-file --batchが途中で終了しました")
        self._buf += chunk

    def _readline(self, deadline: float) -> bytes:
        while (end := self._buf.find(b"\n")) < 0:
            self._fill(deadline)
        line = bytes(self._buf[: end + 1])
        del self._buf[: end + 1]
        return line

    def _read_exact(self, size: int, deadline: float) -> bytes:
        while len(self._buf) < size:
            self._fill(deadline)
        data = bytes(self._buf[:size])
        del self._buf[:size]
        return data

    def _discard_exact(self, size: int, deadline: float) -> None:
        """``size``バイトを読み捨てる（内容を保持しない）。"""

        remaining = size
        while remaining > 0:
            if not self._buf:
                self._fill(deadline)
            taken = min(remaining, len(self._buf))
            del self._buf[:taken]
            remaining -= taken

    def read(self, oid: str) -> bytes:
        """``oid``の内容を返す。読めなければ:class:`GitReadError`を送出する。"""

        _obj_type, data = self.read_object(oid)
        assert data is not None
        return data

    def read_object(self, oid: str, *, max_bytes: int | None = None) -> tuple[str, bytes | None]:
        """``oid``の種類（``blob``、``tree``、``commit``など）と内容を返す。読めなければ:class:`GitReadError`を送出する。

        ``max_bytes``を渡すと、それより大きいオブジェクトは内容を読み捨て、内容の代わりに``None``を返す
        （途中のコミットの仕様文書のファイルごとの上限。内容をすべて保持しない）。
        """

        proc = self._proc
        if self._failed or proc is None or proc.stdin is None or self._selector is None:
            self._failed = True
            raise GitReadError("git cat-file --batchを起動できません")
        try:
            proc.stdin.write(oid.encode("ascii") + b"\n")
            proc.stdin.flush()
            deadline = time.monotonic() + self._timeout
            fields = self._readline(deadline).split()
            if len(fields) != 3 or not fields[2].isdigit():
                # `<oid> missing`、`<oid> ambiguous`など。
                raise GitReadError("基準版のオブジェクトを読めません")
            obj_type = fields[1].decode("ascii")
            size = int(fields[2])
            if max_bytes is not None and size > max_bytes:
                self._discard_exact(size, deadline)
                data: bytes | None = None
                tail = self._read_exact(1, deadline)
            else:
                raw = self._read_exact(size + 1, deadline)
                data, tail = raw[:-1], raw[-1:]
            if tail != b"\n":
                raise GitReadError("git cat-file --batchの出力が不正です")
            return obj_type, data
        except GitReadError:
            self._failed = True
            raise
        except (OSError, ValueError) as exc:
            self._failed = True
            raise GitReadError(str(exc)) from exc
