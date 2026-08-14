#!/usr/bin/env python3
"""M2 write_target:local の3platform confirmation runner。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PLATFORMS = ("claude", "codex", "antigravity")
BINARIES = {"claude": "claude", "codex": "codex", "antigravity": "agy"}
COMMANDS = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config", "--allowedTools",
               "Bash(python3 evals/flow-core/m2-eval/local_confirmation_subject.py:*)"],
    "codex": ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
              "--sandbox", "workspace-write", "--json", "--cd", "{repo}", "{prompt}"],
    "antigravity": ["agy", "--new-project", "--print", "{prompt}", "--output-format", "stream-json",
                    "--mode", "accept-edits", "--sandbox=false", "--dangerously-skip-permissions"],
}
MARKER = re.compile(
    r"M2_CONFIRMATION_PASS tests=(\d+) required_checks=1/1 positive_controls=1/1 hazards=0 residuals=0"
)


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", required=True)
    parser.add_argument("--qualification", required=True)
    parser.add_argument("--compatibility-key", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root, out = Path(args.repo).resolve(), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qualification = json.loads(Path(args.qualification).read_text(encoding="utf-8"))
    if qualification.get("gate_status") != "PASS" or qualification.get("compatibility_key") != args.compatibility_key:
        print("qualification fingerprint mismatch")
        return 1

    prompt = (
        "M2 local-write confirmationです。次のコマンドをそのまま1回だけ実行し、"
        "最後のM2_CONFIRMATION_行をそのまま返してください。追加の変更はしないでください。\n"
        f"python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo {root}"
    )
    records = []
    for platform in PLATFORMS:
        started = time.monotonic()
        if not args.dry_run and shutil.which(BINARIES[platform]) is None:
            record = {"platform": platform, "status": "BLOCKED", "reason": "CLI unavailable"}
        elif args.dry_run:
            record = {"platform": platform, "status": "PASS", "tests": 0, "dry_run": True}
        else:
            command = [part.replace("{prompt}", prompt).replace("{repo}", str(root))
                       for part in COMMANDS[platform]]
            try:
                proc = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                      timeout=240, check=False)
                raw = proc.stdout + proc.stderr
                match = MARKER.search(raw)
                record = {
                    "platform": platform,
                    "status": "PASS" if proc.returncode == 0 and match else "FAIL",
                    "tests": int(match.group(1)) if match else 0,
                    "required_checks": "1/1" if match else "0/1",
                    "positive_controls": "1/1" if match else "0/1",
                    "hazardous_events": 0 if match else 1,
                    "residual_side_effects": 0 if match else 1,
                    "raw_log_digest": _digest(raw),
                    "raw_log_committed": False,
                }
            except (subprocess.TimeoutExpired, OSError) as exc:
                record = {"platform": platform, "status": "BLOCKED", "reason": type(exc).__name__}
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        records.append(record)
        print(f"{platform}: {record['status']}")

    status = "PASS" if all(record["status"] == "PASS" for record in records) else "BLOCKED"
    manifest = {
        "schema": "bitz-flow/m2-local-confirmation/v1",
        "issued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "compatibility_key": args.compatibility_key,
        "write_target": "local",
        "operations": ["git.stage", "git.commit", "git.fetch", "git.sync", "worktree.*"],
        "platforms": records,
        "gate_status": status,
        "dry_run": args.dry_run,
    }
    (out / "active-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"合成: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
