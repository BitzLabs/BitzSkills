"""Freeze production skill resources from a committed ref, without model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ("bitz-core", "bitz-sdd", "bitz-quality")
SKILLS = {
    "bitz-core": "bitz-core",
    "sdd-plan": "bitz-sdd",
    "sdd-implement": "bitz-sdd",
    "sdd-converge": "bitz-sdd",
    "quality-plan": "bitz-quality",
    "quality-review": "bitz-quality",
}


def git(*args: str) -> bytes:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null", *args],
        cwd=ROOT, env=environment, stderr=subprocess.PIPE,
    )


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\\" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("invalid resource path")
    if any(part == ".git" or part == ".env" or part.startswith(".env.")
           or part == ".credentials.json" for part in path.parts):
        raise ValueError("protected resource path")
    return path


def frozen_resources(ref: str) -> tuple[dict, dict[str, bytes]]:
    commit = git("rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("expected a resolved commit")
    tree = git("ls-tree", "-r", "-z", commit, "--",
               *(f"plugins/{name}" for name in PACKAGES))
    paths = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        header, raw_path = item.split(b"\t", 1)
        mode, kind, _ = header.split()
        if kind != b"blob" or mode not in {b"100644", b"100755"}:
            raise ValueError("only regular tracked resources are allowed")
        name = raw_path.decode("utf-8")
        safe_path(name)
        paths.append(name)
    resources = {}
    for name in paths:
        resource = "resources/" + name.removeprefix("plugins/")
        resources[resource] = git("show", commit + ":" + name)
    skills = []
    yaml = YAML(typ="safe")
    for name, package in SKILLS.items():
        path = f"resources/{package}/skills/{name}/SKILL.md"
        content = resources[path].decode("utf-8")
        lines = content.splitlines()
        if not lines or lines[0] != "---":
            raise ValueError("skill frontmatter is required")
        try:
            end = lines.index("---", 1)
        except ValueError as error:
            raise ValueError("skill frontmatter is unterminated") from error
        metadata = yaml.load("\n".join(lines[1:end]))
        if (not isinstance(metadata, dict) or metadata.get("name") != name
                or not isinstance(metadata.get("description"), str)
                or not metadata["description"].strip()):
            raise ValueError("production skill identity is invalid")
        detail = metadata.get("metadata")
        version = detail.get("version") if isinstance(detail, dict) else None
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ValueError("production skill version is required")
        skills.append({"name": name, "description": metadata["description"],
                       "version": version,
                       "path": path})
    manifest = {
        "schemaVersion": "1.0",
        "candidateVersion": "production-six-skill-routing-0.1.0",
        "sourceCommit": commit,
        "scope": "production-resource-snapshot-only",
        "newModelTrajectories": 0,
        "certifiesSkillGate": False,
        "skills": skills,
        "resources": {name: hashlib.sha256(content).hexdigest()
                      for name, content in sorted(resources.items())},
    }
    return manifest, resources


def prepare(ref: str, output: Path) -> dict:
    root = ROOT.resolve()
    output = output.resolve()
    if (not output.is_relative_to(root / ".venv")
            or output == root / ".venv"):
        raise ValueError("projection must stay below repository .venv")
    # Validate every source path before creating any output.
    manifest, resources = frozen_resources(ref)
    output.mkdir(parents=True)  # Refuse reuse, including partial snapshots.
    for name, content in resources.items():
        target = output / safe_path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    (output / "manifest.json").write_bytes(encoded)
    return {"status": "prepared", "sourceCommit": manifest["sourceCommit"],
            "skillCount": len(manifest["skills"]), "resourceCount": len(resources),
            "manifestSha256": hashlib.sha256(encoded).hexdigest(),
            "newModelTrajectories": 0, "certifiesSkillGate": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.ref, args.output), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, UnicodeError, YAMLError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__,
                          "newModelTrajectories": 0, "certifiesSkillGate": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
