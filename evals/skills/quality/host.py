#!/usr/bin/env python3
"""Read-only fixture host. JSON-RPC over stdio; no arbitrary shell or writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_schema(properties=None):
    properties = properties or {}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


class Host:
    def __init__(self, workspace: Path, control: dict, log: Path):
        self.workspace = workspace.resolve()
        self.control = control
        self.log = log
        self.sequence = 0
        self.tools = [
            {"name": "list_files", "description": "読取り可能な固定パスと対象ref・実行IDを一覧する。", "inputSchema": object_schema()},
            {"name": "read_file", "description": "list_filesにある1ファイルだけを読む。", "inputSchema": object_schema({"path": {"type": "string"}})},
            {"name": "read_diff", "description": "固定した基準refから対象refへの実差分を読む。", "inputSchema": object_schema()},
            {"name": "run_bitz", "description": "同じ所有workspaceと指定起点について公開Core CLIをJSONで実行する。contextはpurpose=interpret。実argv・一次結果・観測IDを返す。", "inputSchema": object_schema({"operation": {"type": "string", "enum": ["context", "check"]}})},
        ]
        if control["allowTests"]:
            self.tools.append({"name": "run_fixture_test", "description": "固定したtest_fixture.pyをPython -Bで実行し、一次結果と取得先/hashを返す。本文を先に確認する。", "inputSchema": object_schema()})

    def read(self, name: str) -> bytes:
        if name not in self.control["readableFiles"]:
            raise ValueError("path not in fixed readable files")
        path = self.workspace / name
        if path.is_symlink() or not path.resolve().is_relative_to(self.workspace):
            raise ValueError("symlink or outside workspace")
        raw = path.read_bytes()
        if sha(raw) != self.control["readableFiles"][name]:
            raise ValueError("fixed readable file changed")
        return raw

    def run(self, argv: list[str]) -> dict:
        # All file/argv/env values originate in the hidden fixed control, never model code.
        for name in self.control["fixtureFiles"]:
            self.read(name)
        result = subprocess.run(argv, cwd=self.workspace, env=self.control["environment"], capture_output=True, timeout=30)
        for name in self.control["fixtureFiles"]:
            self.read(name)
        return {"argv": argv, "cwd": str(self.workspace), "exitCode": result.returncode,
                "stdout": result.stdout.decode(), "stderr": result.stderr.decode(),
                "stdoutSha256": sha(result.stdout), "stderrSha256": sha(result.stderr)}

    def execute(self, name: str, args: dict) -> dict:
        if name == "list_files" and args == {}:
            result = {"files": sorted(self.control["readableFiles"]), "subjectCommit": self.control["subjectCommit"],
                    "baseCommit": self.control["baseCommit"], "originId": self.control["originId"],
                    "implementationRunId": self.control["implementationRunId"], "reviewRunId": self.control["reviewRunId"]}
            result.update(source="run-identity", sha256=sha(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()))
            return result
        if name == "read_file" and set(args) == {"path"} and isinstance(args["path"], str):
            data = self.read(args["path"])
            return {"path": args["path"], "content": data.decode(), "sha256": sha(data), "subjectCommit": self.control["subjectCommit"]}
        if name == "read_diff" and args == {}:
            return {"diff": self.control["diff"], "sha256": sha(self.control["diff"].encode()), "subjectCommit": self.control["subjectCommit"],
                    "source": "fixed-diff", "baseCommit": self.control["baseCommit"]}
        if name == "run_bitz" and set(args) == {"operation"} and args["operation"] in {"context", "check"}:
            operation = args["operation"]
            argv = [self.control["python"], "-B", "-m", "bitz.cli", operation, self.control["originId"]]
            if operation == "context":
                argv.extend(["--purpose", "interpret"])
            argv.extend(["--format", "json"])
            result = self.run(argv)
            raw = json.loads(result["stdout"]) if result["stdout"] else None
            observation = {"operation": operation, "status": raw["status"] if raw else None,
                           "exitCode": result["exitCode"], "source": f"host.jsonl:call-{self.sequence}:stdout", "sha256": result["stdoutSha256"],
                           "subjectCommit": self.control["subjectCommit"], "role": "current_gate", "roleReason": "同一対象refと固定起点の公開検査",
                           "argv": argv, "cwd": str(self.workspace), "rawResult": raw, "stderr": result["stderr"]}
            return {"observationId": f"core-{self.sequence}", "observation": observation, "execution": result}
        if name == "run_fixture_test" and args == {} and self.control["allowTests"]:
            previous = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
            read = {c["arguments"].get("path") for c in previous if c["tool"] == "read_file" and c["accepted"]}
            if not {"target.py", "test_fixture.py"}.issubset(read):
                raise ValueError("read implementation and test before execution")
            result = self.run([self.control["python"], "-B", "test_fixture.py"])
            result.update(source=f"host.jsonl:call-{self.sequence}:test-result",
                          sha256=sha(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()), subjectCommit=self.control["subjectCommit"])
            return result
        raise ValueError("tool/arguments not allowed")

    def call(self, name: str, args: dict) -> dict:
        self.sequence += 1
        accepted = True
        try:
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            result = self.execute(name, args)
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
            accepted = False
            result = {"error": type(error).__name__, "reason": str(error)}
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"sequence": self.sequence, "tool": name, "arguments": args, "accepted": accepted, "result": result}, ensure_ascii=False) + "\n")
        public = {k: v for k, v in result.items() if k != "execution"}
        return {"content": [{"type": "text", "text": json.dumps(public, ensure_ascii=False)}], "isError": not accepted}


def serve(host: Host):
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == "initialize":
            result = {"protocolVersion": request["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "quality-eval", "version": "0.1.0"}}
        elif method == "tools/list":
            result = {"tools": host.tools}
        elif method == "tools/call":
            result = host.call(request["params"]["name"], request["params"].get("arguments", {}))
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "method not supported"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    serve(Host(args.workspace, json.loads(args.control.read_text()), args.log))


if __name__ == "__main__":
    main()
