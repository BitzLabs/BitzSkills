"""fixtureのsetupとsnapshotだけを扱う。Core操作は実装しない。"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        # 入れ子のGitのmetadataと、別worktreeの.git fileは比較の対象にしない（ADR-048）。
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
        raise ValueError(f"安全でないfixture pathです: {relative!r}")
    if relative.split("/")[0] == ".git":
        raise ValueError("fixtureの操作はGitのmetadataを変更できません")
    target = root / relative
    for parent in target.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("fixture pathがsymlinkを経由しています")
    return target


def git(root, *args, environment=None):
    env = {"PATH": os.environ["PATH"], "LANG": "C", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    return subprocess.check_output(["git", "-c", "user.name=Bitz Fixture", "-c", "user.email=fixture@bitz.invalid",
                                   "-c", "commit.gpgSign=false", "-c", "core.autocrlf=false", "-c", "core.fileMode=true",
                                   "-c", f"core.hooksPath={os.devnull}", "-c", "init.templateDir=", *args],
                                   cwd=root, env={**env, **(environment or {})}, stderr=subprocess.PIPE, timeout=10)


def tree_digest_bytes(entries):
    """生成treeのdigest材料。path昇順で<path>\0<8 byteの長さ><内容>を連結する（ADR-048）。"""
    digest = hashlib.sha256()
    for relative, content in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def write_generated(entries, destination):
    """生成した(path, 内容)の列をdestinationへ書き出す。"""
    for relative, content in entries:
        path = safe_path(destination, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def setup(fixture, manifest, destination, generated=None):
    if destination.exists():
        raise ValueError("setup先は存在してはいけません")
    plan = manifest["setup"]
    if "generate" in plan:
        if (fixture / "repo").exists():
            raise ValueError("生成fixtureはrepo directoryを持ってはいけません")
        if generated is None:
            raise ValueError("生成fixtureのsetupには生成した入力が必要です")
        destination.mkdir(parents=True)
        write_generated(generated, destination)
    else:
        if (fixture / "repo/.git").exists():
            raise ValueError("fixtureの元directoryはGitのmetadataを含んではいけません")
        shutil.copytree(fixture / "repo", destination, symlinks=True)
    if plan["git"]:
        git(destination, "init", "--initial-branch=fixture")
    elif "baseCommit" in plan or any(op["op"] in {"stage", "submodule", "worktree"}
                                     for op in plan["operations"]):
        raise ValueError("Gitの操作にはsetup.gitが必要です")
    if "baseCommit" in plan:
        paths = plan["baseCommit"]["paths"]
        for path in paths:
            safe_path(destination, path, allow_dot=True)
        git(destination, "add", "-A", "--", *paths)
        git(destination, "commit", "-m", plan["baseCommit"]["message"])
    for operation in plan["operations"]:
        kind = operation["op"]
        if kind == "stage":
            for path in operation["paths"]:
                safe_path(destination, path, allow_dot=True)
            git(destination, "add", "-A", "--", *operation["paths"])
            continue
        path = safe_path(destination, operation.get("path", operation.get("from", "")))
        exists = path.exists() or path.is_symlink()
        if kind in {"create", "update"}:
            if (kind == "create" and exists) or (kind == "update" and (not exists or (path.is_dir() and not path.is_symlink()))):
                raise ValueError("create／updateの前提条件を満たしていません")
            source = safe_path(fixture, operation["source"])
            if not operation["source"].startswith("changes/") or not (source.is_file() or source.is_symlink()):
                raise ValueError("sourceはchangesのfileまたはsymlinkである必要があります")
            if exists:
                path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                path.symlink_to(os.readlink(source))
            else:
                # mtimeを引き継がない。同じsizeの置換で、base commitより古いmtimeと再利用されたinodeが
                # index上のstat情報と一致すると、Gitが内容を比べずに未変更と判定するためである。
                shutil.copyfile(source, path)
                shutil.copymode(source, path)
        elif kind == "delete":
            if not exists:
                raise ValueError("削除対象が存在しません")
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        elif kind in {"submodule", "worktree"}:
            if exists:
                raise ValueError("Git構造を作るpathは存在していてはいけません")
            source = safe_path(fixture, operation["source"])
            if not operation["source"].startswith("changes/") or not source.is_dir():
                raise ValueError("Git構造のsourceはchangesのdirectoryである必要があります")
            if kind == "submodule":
                add_submodule(destination, path, source)
            else:
                add_worktree(destination, path, source)
        elif kind == "rename":
            target = safe_path(destination, operation["to"])
            if not exists or target.exists() or target.is_symlink():
                raise ValueError("renameの前提条件を満たしていません")
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
        else:
            raise ValueError(f"未知のsetup操作です: {kind}")
    return destination


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
    """member pathを、内容がsourceと同じ別repositoryにし、親へgitlinkと.gitmodulesを記録する。"""
    relative = path.relative_to(destination).as_posix()
    copy_source_tree(source, path)
    git(path, "init", "--initial-branch=fixture")
    git(path, "add", "-A", "--", ".")
    git(path, "commit", "-m", "member")
    modules = destination / ".gitmodules"
    modules.write_text(f'[submodule "{relative}"]\n\tpath = {relative}\n\turl = ./{relative}\n',
                       encoding="utf-8")
    git(destination, "add", "--", ".gitmodules")
    # gitlinkとして記録する。埋め込みrepositoryの警告は想定どおりである。
    git(destination, "add", "--", relative)


def add_worktree(destination, path, source):
    """member pathを、内容がsourceと同じcommitを持つ同じrepositoryの別worktreeにする。"""
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
