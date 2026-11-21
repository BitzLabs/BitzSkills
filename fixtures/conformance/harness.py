"""fixtureの準備手順とスナップショットだけを扱う。Coreの公開操作は実装しない。"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        # 入れ子のGitのメタデータと、別のワークツリーの.gitファイルは比較の対象にしない（ADR-048）。
        if ".git" in relative.split("/"):
            continue
        if path.is_symlink():
            result[relative] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            result[relative] = {"kind": "file", "executable": bool(path.stat().st_mode & 0o111), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        else:
            result[relative] = {"kind": "directory"}
    return result


def differences(before, after):
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def safe_path(root, relative, allow_dot=False):
    if allow_dot and relative == ".":
        return root
    if not relative or "\0" in relative or "\\" in relative or Path(relative).is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError(f"安全でないfixtureのパスです: {relative!r}")
    if relative.split("/")[0] == ".git":
        raise ValueError("fixtureの操作はGitのメタデータを変更できません")
    target = root / relative
    for parent in target.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("fixtureのパスがシンボリックリンクを経由しています")
    return target


# 準備手順のGit操作1回の上限。規模の検証は1万ファイル規模の`git add`を行い、通常は1秒未満だが、
# 他の検証と負荷が重なると10秒を超えたことがある（2026-10-05）。認定の`git`の上限（`certify_gate_a.py`）と同じ値にする。
GIT_TIMEOUT_SECONDS = 120


def git(root, *args, environment=None):
    env = {"PATH": os.environ["PATH"], "LANG": "C", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    return subprocess.check_output(["git", "-c", "user.name=Bitz Fixture", "-c", "user.email=fixture@bitz.invalid",
                                   "-c", "commit.gpgSign=false", "-c", "core.autocrlf=false", "-c", "core.fileMode=true",
                                   "-c", f"core.hooksPath={os.devnull}", "-c", "init.templateDir=", *args],
                                   cwd=root, env={**env, **(environment or {})}, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT_SECONDS)


def tree_digest_bytes(entries):
    """生成した木構造のハッシュ値の材料。パスの昇順で<path>\0<8バイトの長さ><内容>を連結する（ADR-048）。"""
    digest = hashlib.sha256()
    for relative, content in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def write_generated(entries, destination):
    """生成した(パス, 内容)の列を`destination`へ書き出す。"""
    for relative, content in entries:
        path = safe_path(destination, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def materialize(destination, renames):
    """コピーした入力の名前を、Gitの準備より前に付け替える（適合fixture仕様 §3.1の1.5）。

    `repo/`には、Unicodeの正規化形（NFC・NFD）だけが異なる名前や、NFCで同じ名前になる2つの兄弟の項目を、置けない
    （macOSのファイルシステムとGitの既定の設定で、名前が正規化または衝突するため）。そのため`repo/`にはASCIIの名前で置き、
    `setup.materialize`の`to`（JSONの`\\u`エスケープで書いた正規化形が異なる名前）へ、`git init`の前に付け替える。
    付け替えの後の名前が基準版のコミットに入る。`to`は存在してはいけない。名前を付け替えるだけで、内容は変えない。
    """
    for rename in renames:
        source = safe_path(destination, rename["from"])
        target = safe_path(destination, rename["to"])
        if not (source.exists() or source.is_symlink()) or target.exists() or target.is_symlink():
            raise ValueError("`materialize`の前提条件を満たしていません")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)


def setup(fixture, manifest, destination, generated=None):
    if destination.exists():
        raise ValueError("準備手順で作るディレクトリは存在してはいけません")
    plan = manifest["setup"]
    if "generate" in plan:
        if (fixture / "repo").exists():
            raise ValueError("生成fixtureは`repo`ディレクトリを持ってはいけません")
        if generated is None:
            raise ValueError("生成fixtureの準備手順には生成した入力が必要です")
        destination.mkdir(parents=True)
        write_generated(generated, destination)
    else:
        if (fixture / "repo/.git").exists():
            raise ValueError("fixtureの元のディレクトリはGitのメタデータを含んではいけません")
        shutil.copytree(fixture / "repo", destination, symlinks=True)
    materialize(destination, plan.get("materialize", []))
    if plan["git"]:
        git(destination, "init", "--initial-branch=fixture")
    elif "baseCommit" in plan or any(op["op"] in GIT_OPERATIONS for op in plan["operations"]):
        raise ValueError("Gitの操作には`setup.git`が必要です")
    if "baseCommit" in plan:
        paths = plan["baseCommit"]["paths"]
        for path in paths:
            safe_path(destination, path, allow_dot=True)
        git(destination, "add", "-A", "--", *paths)
        git(destination, "commit", "-m", plan["baseCommit"]["message"])
    # マージの途中（`merge`の後、`commit`の前）の状態。`None`はマージの途中でないことを表す（ADR-080）。
    merging = None
    for operation in plan["operations"]:
        kind = operation["op"]
        if kind in HISTORY_OPERATIONS:
            merging = apply_history_operation(destination, operation, merging)
            continue
        if kind == "stage":
            for path in operation["paths"]:
                safe_path(destination, path, allow_dot=True)
            git(destination, "add", "-A", "--", *operation["paths"])
            continue
        path = safe_path(destination, operation.get("path", operation.get("from", "")))
        exists = path.exists() or path.is_symlink()
        if kind in {"create", "update"}:
            if (kind == "create" and exists) or (kind == "update" and (not exists or (path.is_dir() and not path.is_symlink()))):
                raise ValueError("`create`／`update`の前提条件を満たしていません")
            source = safe_path(fixture, operation["source"])
            if not operation["source"].startswith("changes/") or not (source.is_file() or source.is_symlink()):
                raise ValueError("`source`は`changes`のファイルまたはシンボリックリンクである必要があります")
            if exists:
                path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                path.symlink_to(os.readlink(source))
            else:
                # `mtime`を引き継がない。同じバイト数の置換で、基準版のコミットより古い`mtime`と再利用された`inode`が
                # インデックス上の`stat`の情報と一致すると、Gitが内容を比べずに未変更と判定するためである。
                shutil.copyfile(source, path)
                shutil.copymode(source, path)
            if merging is not None:
                merging["resolved"].add(_relative(destination, path))
        elif kind == "delete":
            if not exists:
                raise ValueError("削除対象が存在しません")
            if merging is not None:
                merging["resolved"].add(_relative(destination, path))
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        elif kind in {"submodule", "worktree"}:
            if exists:
                raise ValueError("Git構造を作るパスは存在していてはいけません")
            source = safe_path(fixture, operation["source"])
            if not operation["source"].startswith("changes/") or not source.is_dir():
                raise ValueError("Git構造の`source`は`changes`のディレクトリである必要があります")
            if kind == "submodule":
                add_submodule(destination, path, source)
            else:
                add_worktree(destination, path, source)
        elif kind == "rename":
            target = safe_path(destination, operation["to"])
            if not exists or target.exists() or target.is_symlink():
                raise ValueError("`rename`の前提条件を満たしていません")
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
        else:
            raise ValueError(f"準備手順の未知の操作です: {kind}")
    if merging is not None:
        raise ValueError("準備の処理の最後でマージの途中です")
    return destination


# Gitを使う準備の処理（`setup.git: false`では禁止する。適合fixture仕様 §3.1）。
GIT_OPERATIONS = frozenset({"stage", "submodule", "worktree", "commit", "branch", "checkout", "merge", "shallow"})
# 履歴を作る準備の処理（ADR-080、適合fixture仕様 §3.2）。
HISTORY_OPERATIONS = frozenset({"commit", "branch", "checkout", "merge", "shallow"})
BRANCH_NAME = re.compile(r"[a-z][a-z0-9-]*")


def _relative(root, path):
    return path.relative_to(root).as_posix()


def _git_succeeds(root, *args):
    try:
        git(root, *args)
    except subprocess.CalledProcessError:
        return False
    return True


def _head_commit(root):
    if not _git_succeeds(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}"):
        return None
    return git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()


def _branch_name(operation):
    name = operation.get("name")
    if not isinstance(name, str) or BRANCH_NAME.fullmatch(name) is None:
        raise ValueError("枝の名前は英小文字、数字、`-`だけからなり、英小文字で始まる必要があります")
    return name


def _branch_exists(root, name):
    return _git_succeeds(root, "show-ref", "--verify", "--quiet", f"refs/heads/{name}")


def _clean(root):
    """追跡しているパスのインデックスと作業ツリーが`HEAD`と同じで、無視されていない未追跡のファイルがない。"""
    return git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none").decode() == ""


def apply_history_operation(root, operation, merging):
    """`commit`、`branch`、`checkout`、`merge`、`shallow`を適用し、マージの途中の状態を返す（ADR-080）。

    同一性、時刻、ブランチ名はharnessの固定値（`git`）を使うので、2回の`setup`で同じコミットIDになる。
    """
    kind = operation["op"]
    if kind != "commit" and merging is not None:
        raise ValueError(f"マージの途中に`{kind}`は使えません")
    if kind == "commit":
        if not isinstance(operation.get("message"), str) or not operation["message"]:
            raise ValueError("`commit`には空でない`message`が必要です")
        if git(root, "ls-files", "--unmerged").decode():
            raise ValueError("インデックスに未解決の衝突があります")
        if merging is not None and not merging["conflicts"] <= merging["resolved"]:
            raise ValueError("マージで衝突したパスに`update`または`delete`で内容を与えていません")
        # マージの途中なら、Gitが`MERGE_HEAD`を2つ目の親とするマージコミットを作る。
        git(root, "commit", "--allow-empty", "--no-verify", "--cleanup=verbatim", "-m", operation["message"])
        return None
    if kind == "branch":
        name = _branch_name(operation)
        if _head_commit(root) is None:
            raise ValueError("`branch`には`HEAD`のコミットが必要です")
        if _branch_exists(root, name):
            raise ValueError(f"枝{name}はすでに存在します")
        git(root, "branch", "--no-track", name)
        return None
    if kind == "checkout":
        name = _branch_name(operation)
        if not _branch_exists(root, name):
            raise ValueError(f"枝{name}が存在しません")
        if not _clean(root):
            raise ValueError("`checkout`にはクリーンな作業ツリーが必要です")
        git(root, "checkout", "--quiet", name)
        return None
    if kind == "merge":
        name = _branch_name(operation)
        if not _branch_exists(root, name):
            raise ValueError(f"枝{name}が存在しません")
        head = _head_commit(root)
        if head is None:
            raise ValueError("`merge`には`HEAD`のコミットが必要です")
        tip = git(root, "rev-parse", "--verify", f"refs/heads/{name}^{{commit}}").decode().strip()
        if tip == head or _git_succeeds(root, "merge-base", "--is-ancestor", tip, head):
            raise ValueError(f"枝{name}の先端は`HEAD`と同じか、`HEAD`の祖先です")
        if not _clean(root):
            raise ValueError("`merge`にはクリーンな作業ツリーが必要です")
        # 衝突は準備の誤りにしない。Gitは衝突のときに終了コード1を返し、衝突の印を作業ツリーに残す。
        try:
            git(root, "merge", "--no-ff", "--no-commit", "--no-edit", "--quiet", f"refs/heads/{name}",
                environment={"GIT_MERGE_AUTOEDIT": "no"})
        except subprocess.CalledProcessError:
            pass
        if not _git_succeeds(root, "rev-parse", "--verify", "--quiet", "MERGE_HEAD"):
            raise ValueError(f"枝{name}のマージを始められませんでした")
        conflicts = set(git(root, "diff", "--name-only", "-z", "--diff-filter=U").decode().split("\0")[:-1])
        return {"branch": name, "conflicts": conflicts, "resolved": set()}
    if kind == "shallow":
        revisions = operation.get("revisions")
        if not isinstance(revisions, list) or not revisions or len(set(revisions)) != len(revisions):
            raise ValueError("`revisions`は重複のない1件以上の配列である必要があります")
        commits = []
        for revision in revisions:
            if not isinstance(revision, str) or not revision or revision.startswith("-"):
                raise ValueError(f"リビジョンを解決できません: {revision!r}")
            if not _git_succeeds(root, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"):
                raise ValueError(f"リビジョンを解決できません: {revision!r}")
            commits.append(git(root, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip())
        shallow = root / git(root, "rev-parse", "--git-path", "shallow").decode().strip()
        recorded = shallow.read_text(encoding="ascii").split() if shallow.exists() else []
        for commit in commits:
            if commit not in recorded:
                recorded.append(commit)
        # Gitの`shallow`ファイル（境界のコミットのIDを1行に1つ）。オブジェクトは削除しない。
        shallow.write_text("".join(f"{commit}\n" for commit in recorded), encoding="ascii")
        return None
    raise ValueError(f"準備手順の未知の操作です: {kind}")


def copy_source_tree(source, destination):
    destination.mkdir(parents=True)
    for entry in sorted(source.rglob("*")):
        target = destination / entry.relative_to(source)
        if entry.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.readlink(entry))
        elif entry.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target)


def add_submodule(destination, path, source):
    """メンバーのパスを、`source`と同じ内容の別のリポジトリにし、親へ`gitlink`と`.gitmodules`を記録する。"""
    relative = path.relative_to(destination).as_posix()
    copy_source_tree(source, path)
    git(path, "init", "--initial-branch=fixture")
    git(path, "add", "-A", "--", ".")
    git(path, "commit", "-m", "member")
    modules = destination / ".gitmodules"
    modules.write_text(f'[submodule "{relative}"]\n\tpath = {relative}\n\turl = ./{relative}\n',
                       encoding="utf-8")
    git(destination, "add", "--", ".gitmodules")
    # `gitlink`として記録する。埋め込まれたリポジトリの警告は想定どおりである。
    git(destination, "add", "--", relative)


def add_worktree(destination, path, source):
    """メンバーのパスを、`source`と同じ内容のコミットを持つ同じリポジトリの別のワークツリーにする。"""
    relative = path.relative_to(destination).as_posix()
    staging = destination / ".git" / "fixture-worktree-source"
    copy_source_tree(source, staging)
    index = destination / ".git" / "fixture-worktree-index"
    environment = {"GIT_INDEX_FILE": str(index), "GIT_WORK_TREE": str(staging)}
    git(destination, "add", "-A", "--", ".", environment=environment)
    tree = git(destination, "write-tree", environment=environment).decode().strip()
    commit = git(destination, "commit-tree", tree, "-m", "member").decode().strip()
    index.unlink()
    shutil.rmtree(staging)
    git(destination, "worktree", "add", "--detach", relative, commit)
    return commit
