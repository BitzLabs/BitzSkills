#!/usr/bin/env python3
"""製品発火測定用の固定資源読取りホスト。操作実行や正解提示は行わない。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

VERSION = "production-routing-host-0.1.1"
SKILLS = {"bitz-core", "sdd-plan", "sdd-implement", "sdd-converge", "quality-plan", "quality-review"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def schema(properties: dict | None = None) -> dict:
    properties = properties or {}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def resource_path(name: str) -> PurePosixPath:
    if not isinstance(name, str) or "\\" in name or any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("invalid resource path")
    path = PurePosixPath(name)
    if path.is_absolute() or len(path.parts) < 3 or path.parts[0] != "resources" or path.parts[1] not in {"bitz-core", "bitz-sdd", "bitz-quality"}:
        raise ValueError("outside resource packages")
    if any(part == ".git" or part == ".env" or part.startswith(".env.") or part == ".credentials.json" for part in path.parts):
        raise ValueError("protected path")
    return path


class Host:
    def __init__(self, snapshot: Path, manifest_sha256: str, log: Path):
        if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
            raise ValueError("invalid manifest pin")
        if any(p.is_symlink() for p in [snapshot, *snapshot.parents]):
            raise ValueError("symlink snapshot")
        self.snapshot = snapshot.resolve(strict=True)
        manifest_path = self.snapshot / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError("symlink manifest")
        raw = manifest_path.read_bytes()
        if sha(raw) != manifest_sha256:
            raise ValueError("manifest drift")
        self.manifest = json.loads(raw)
        if self.manifest["schemaVersion"] != "1.0" or self.manifest["scope"] != "production-resource-snapshot-only":
            raise ValueError("unexpected manifest scope")
        if not re.fullmatch(r"[0-9a-f]{40}", self.manifest["sourceCommit"]):
            raise ValueError("invalid source commit")
        self.resources = self.manifest["resources"]
        if not isinstance(self.resources, dict) or not self.resources:
            raise ValueError("missing resources")
        # すべての名前を先に検査し、禁止パスを一度も開かない。
        for name, digest in self.resources.items():
            resource_path(name)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid resource pin")
        skills = self.manifest["skills"]
        if len(skills) != 6 or {skill["name"] for skill in skills} != SKILLS:
            raise ValueError("unexpected skills")
        for skill in skills:
            if skill["path"] not in self.resources or not skill["path"].endswith("/skills/" + skill["name"] + "/SKILL.md"):
                raise ValueError("unlisted skill")
            if not isinstance(skill["description"], str) or not skill["description"].strip():
                raise ValueError("missing skill description")
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", skill["version"]):
                raise ValueError("invalid skill version")
        self.manifest_sha256 = manifest_sha256
        for name in self.resources:
            self.read(name)
        # 既存ログや候補内への書込みを拒否する。モデルへログのパスは提示しない。
        if log.resolve().is_relative_to(self.snapshot):
            raise ValueError("log inside snapshot")
        if any(p.is_symlink() for p in [log, *log.parents]):
            raise ValueError("symlink log")
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.log = os.fdopen(fd, "w", encoding="utf-8")
        self.sequence = 0
        self.tools = [
            {"name": "list_resources", "description": "固定した製品6スキルの説明と読取り可能な資源の相対パスを一覧する。", "inputSchema": schema()},
            {"name": "read_resource", "description": "一覧にある資源1件だけを固定hashに照合して読む。", "inputSchema": schema({"path": {"type": "string"}})},
        ]
        for tool in self.tools:
            tool['annotations'] = {'readOnlyHint': True, 'destructiveHint': False,
                                   'idempotentHint': True, 'openWorldHint': False}

    def read(self, name: str) -> bytes:
        relative = resource_path(name)
        if name not in self.resources:
            raise ValueError("unlisted resource")
        path = self.snapshot / relative
        if any(part.is_symlink() for part in [path, *path.parents] if part.is_relative_to(self.snapshot)):
            raise ValueError("symlink resource")
        if not path.is_file() or not path.resolve().is_relative_to(self.snapshot):
            raise ValueError("outside snapshot")
        raw = path.read_bytes()
        if sha(raw) != self.resources[name]:
            raise ValueError("resource drift")
        return raw

    def execute(self, name: str, arguments: dict) -> dict:
        if name == "list_resources" and arguments == {}:
            # manifestの任意の追加情報をモデル資源へ転送しない。
            return {"skills": [{key: skill[key] for key in ("name", "description", "version", "path")} for skill in self.manifest["skills"]],
                    "resources": sorted(self.resources), "sourceCommit": self.manifest["sourceCommit"],
                    "candidateVersion": self.manifest["candidateVersion"], "manifestSha256": self.manifest_sha256}
        if name == "read_resource" and set(arguments) == {"path"} and isinstance(arguments["path"], str):
            raw = self.read(arguments["path"])
            return {"path": arguments["path"], "content": raw.decode("utf-8"), "sha256": sha(raw),
                    "sourceCommit": self.manifest["sourceCommit"]}
        raise ValueError("tool or arguments not allowed")

    def call(self, name: str, arguments: dict) -> dict:
        self.sequence += 1
        accepted = True
        try:
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object")
            result = self.execute(name, arguments)
        except (OSError, ValueError, TypeError, KeyError) as error:
            accepted = False
            result = {"errorType": type(error).__name__}
        self.log.write(json.dumps({"sequence": self.sequence, "tool": name, "arguments": arguments,
                                   "accepted": accepted, "result": result}, ensure_ascii=False) + "\n")
        self.log.flush()
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": not accepted}

    def close(self) -> None:
        self.log.close()


def serve(host: Host) -> None:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request.get("method")
        if method == "initialize":
            result = {"protocolVersion": request["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "production-routing", "version": VERSION}}
        elif method == "tools/list":
            result = {"tools": host.tools}
        elif method == "tools/call":
            result = host.call(request["params"]["name"], request["params"].get("arguments", {}))
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "unsupported method"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    host = Host(args.snapshot, args.manifest_sha256, args.log)
    try:
        serve(host)
    finally:
        host.close()


if __name__ == "__main__":
    main()
