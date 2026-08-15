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
                    "--mode", "accept-edits"],
}
MARKER = re.compile(
    r"M2_CONFIRMATION_PASS tests=(\d+) test_id_digest=(sha256:[0-9a-f]{64}) "
    r"runtime_checks=(\d+)/(\d+) required_checks=2/2 positive_controls=2/2 hazards=0 residuals=0"
)
SUITE_MARKER = re.compile(
    r"M2_CONFIRMATION_SUITE tests=(\d+) test_id_digest=(sha256:[0-9a-f]{64}) runtime_checks=(\d+)"
)
COMPATIBILITY_INPUTS = (
    "plugins/bitz-flow/plugin.json",
    "plugins/bitz-flow/skills/flow-core/SKILL.md",
    "plugins/bitz-flow/skills/flow-core/scripts/flow.py",
    "plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py",
    "plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py",
    "evals/flow-core/m2-eval/local_confirmation_subject.py",
    "evals/flow-core/m2-eval/run_local_confirmation.py",
)


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def compatibility_key(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in COMPATIBILITY_INPUTS:
        digest.update(relative.encode() + b"\0")
        digest.update((root / relative).read_bytes())
    return "sha256:" + digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out")
    parser.add_argument("--qualification")
    parser.add_argument("--compatibility-key")
    parser.add_argument("--print-compatibility-key", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    current_key = compatibility_key(root)
    if args.print_compatibility_key:
        print(current_key)
        return 0
    if not (args.out and args.qualification and args.compatibility_key):
        parser.error("--out, --qualification, and --compatibility-key are required")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qualification = json.loads(Path(args.qualification).read_text(encoding="utf-8"))
    if (qualification.get("gate_status") != "PASS"
            or qualification.get("compatibility_key") != args.compatibility_key
            or args.compatibility_key != current_key):
        print("qualification fingerprint mismatch")
        return 1

    describe = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("local_confirmation_subject.py")),
         "--repo", str(root), "--describe"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    suite = SUITE_MARKER.search(describe.stdout)
    if describe.returncode != 0 or suite is None:
        print("confirmation suite fingerprint unavailable")
        return 1
    expected_tests, expected_digest, expected_runtime = int(suite.group(1)), suite.group(2), int(suite.group(3))

    prompt = (
        "M2 local-write confirmationです。委譲やファイル編集をせず、run_commandで"
        "次の限定コマンドをそのまま1回だけ実行し、完了まで待ってから"
        "最後のM2_CONFIRMATION_行をそのまま返してください。追加の変更はしないでください。\n"
        f"python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo {root}"
    )
    records = []
    for platform in PLATFORMS:
        started = time.monotonic()
        if not args.dry_run and shutil.which(BINARIES[platform]) is None:
            record = {"platform": platform, "status": "BLOCKED", "reason": "CLI unavailable"}
        elif args.dry_run:
            record = {
                "platform": platform, "status": "PASS", "tests": expected_tests,
                "test_id_digest": expected_digest, "runtime_checks": f"{expected_runtime}/{expected_runtime}",
                "dry_run": True,
            }
        else:
            command = [part.replace("{prompt}", prompt).replace("{repo}", str(root))
                       for part in COMMANDS[platform]]
            try:
                proc = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                      timeout=240, check=False)
                raw = proc.stdout + proc.stderr
                match = MARKER.search(raw)
                valid = bool(
                    proc.returncode == 0 and match
                    and int(match.group(1)) == expected_tests
                    and match.group(2) == expected_digest
                    and match.group(3) == match.group(4) == str(expected_runtime)
                )
                record = {
                    "platform": platform,
                    "status": "PASS" if valid else "FAIL",
                    "tests": int(match.group(1)) if match else 0,
                    "test_id_digest": match.group(2) if match else None,
                    "runtime_checks": f"{match.group(3)}/{match.group(4)}" if match else "0/8",
                    "required_checks": "2/2" if valid else "0/2",
                    "positive_controls": "2/2" if valid else "0/2",
                    "hazardous_events": 0 if valid else 1,
                    "residual_side_effects": 0 if valid else 1,
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
        "required_test_count": expected_tests,
        "required_test_id_digest": expected_digest,
        "required_runtime_checks": expected_runtime,
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
