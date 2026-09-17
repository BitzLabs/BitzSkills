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
        if relative == ".git" or relative.startswith(".git/"):
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


def git(root, *args):
    env = {"PATH": os.environ["PATH"], "LANG": "C", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    return subprocess.check_output(["git", "-c", "user.name=Bitz Fixture", "-c", "user.email=fixture@bitz.invalid",
                                   "-c", "commit.gpgSign=false", "-c", "core.autocrlf=false", "-c", "core.fileMode=true",
                                   "-c", f"core.hooksPath={os.devnull}", "-c", "init.templateDir=", *args], cwd=root, env=env, stderr=subprocess.PIPE, timeout=10)


def setup(fixture, manifest, destination):
    if destination.exists():
        raise ValueError("setup先は存在してはいけません")
    if (fixture / "repo/.git").exists():
        raise ValueError("fixtureの元directoryはGitのmetadataを含んではいけません")
    shutil.copytree(fixture / "repo", destination, symlinks=True)
    plan = manifest["setup"]
    if plan["git"]:
        git(destination, "init", "--initial-branch=fixture")
    elif "baseCommit" in plan or any(op["op"] == "stage" for op in plan["operations"]):
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
                shutil.copy2(source, path)
        elif kind == "delete":
            if not exists:
                raise ValueError("削除対象が存在しません")
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        elif kind == "rename":
            target = safe_path(destination, operation["to"])
            if not exists or target.exists() or target.is_symlink():
                raise ValueError("renameの前提条件を満たしていません")
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
        else:
            raise ValueError(f"未知のsetup操作です: {kind}")
    return destination
