#!/usr/bin/env python3
"""SDD-FR-143: guarded and recoverable BitzSDD status transitions."""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_labels import normalize_status  # noqa: E402
from spec_trace import tasks_for_requirement  # noqa: E402
from spec_transaction import (  # noqa: E402
    FileChange,
    MutationError,
    TransactionPlan,
    canonical_json,
    mutate,
    recover,
    recover_lock,
    sha256,
    utc_now,
)

TRANSITIONS = {
    "requirement": {
        ("draft", "approved"): "human",
        ("approved", "implementing"): "agent",
        ("implementing", "approved"): "agent",
        ("implementing", "verified"): "agent",
        ("verified", "promoted"): "human",
        ("draft", "deprecated"): "human",
        ("approved", "deprecated"): "human",
        ("implementing", "deprecated"): "human",
        ("verified", "deprecated"): "human",
        ("promoted", "deprecated"): "human",
    },
    "spec-issue": {
        ("open", "accepted"): "human",
        ("open", "rejected"): "human",
        ("accepted", "superseded"): "human",
        ("accepted", "rejected"): "human",
    },
    "task": {
        ("pending", "implementing"): "agent",
        ("pending", "blocked"): "agent",
        ("implementing", "done"): "agent",
        ("implementing", "blocked"): "agent",
        ("blocked", "implementing"): "agent",
        ("blocked", "pending"): "agent",
    },
}

KIND_DIR = {
    "requirement": "requirements",
    "spec-issue": "spec-issues",
    "task": "tasks",
}


def locate(root: Path, ident: str):
    for kind, subdirectory in KIND_DIR.items():
        path = root / ".spec" / subdirectory / f"{ident}.md"
        if path.exists():
            return kind, path
    return None, None


def read_status(text: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    block = match.group(1) if match else text
    status = re.search(r"^status:\s*(\S+)", block, re.M)
    return status.group(1) if status else ""


def rewrite_status(text: str, new_status: str) -> str:
    match = re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.S)
    if not match:
        raise MutationError("precondition-failed", "frontmatterが見つかりません", 4)
    new_block, count = re.subn(
        r"^status:\s*\S+.*$",
        f"status: {new_status}",
        match.group(2),
        count=1,
        flags=re.M,
    )
    if count == 0:
        raise MutationError("precondition-failed", "status行が見つかりません", 4)
    return match.group(1) + new_block + match.group(3) + text[match.end():]


def validate_actor(actor: str) -> str:
    if not actor or len(actor) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in actor):
        raise MutationError(
            "authorization-required",
            "actorは1〜128文字で改行・ASCII制御文字を含めないでください",
            3,
        )
    return actor


def confirm_interactively(ident: str, old: str, new: str) -> None:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise MutationError(
            "authorization-required",
            "人間裁定必須遷移にはstdin/stderrのTTYが必要です（実行者本人は未検証）",
            3,
        )
    challenge = f"{ident} {old}->{new}"
    print(
        f"対象: {ident}\n遷移: {old} -> {new}\n"
        f"確認のため次を完全一致で入力してください: {challenge}",
        file=sys.stderr,
    )
    entered = input().strip()
    if entered != challenge:
        raise MutationError("authorization-required", "確認文字列が一致しません", 3)


def _check_task_preconditions(root: Path, ident: str, old: str, new: str) -> None:
    if (old, new) not in {("approved", "implementing"), ("implementing", "verified")}:
        return
    tasks = tasks_for_requirement(root, ident)
    if not tasks:
        raise MutationError(
            "precondition-failed",
            f"{ident}をimplementsするlocal taskがありません。spec scaffoldでtaskを起票してください",
            4,
        )
    if new == "verified":
        incomplete = [f"{task.path.relative_to(root)} ({task.status or 'missing'})"
                      for task in tasks if task.status != "done"]
        if incomplete:
            raise MutationError(
                "precondition-failed",
                "未完了local taskがあります: " + ", ".join(incomplete),
                4,
            )


def _state_before(root: Path) -> tuple[Path, bytes]:
    path = root / ".spec" / "STATE.md"
    if path.exists():
        return path, path.read_bytes()
    return path, b"# STATE \xe2\x80\x94 status \xe9\x81\xb7\xe7\xa7\xbb\xe3\x83\xad\xe3\x82\xb0\n\n"


def _state_after(
    before: bytes,
    event_id: str,
    ident: str,
    artifact_path: Path,
    old: str,
    new: str,
    actor: str,
    provenance: str,
    artifact_before: bytes,
    artifact_after: bytes,
    root: Path,
) -> bytes:
    human_suffix = (
        "; 対話入力確認済み（実行者未検証）"
        if provenance == "interactive-confirmation-unverified"
        else ""
    )
    display = f"- {date.today().isoformat()} {ident}: {old} \u2192 {new} ({actor}{human_suffix})\n"
    event = {
        "schema_version": 1,
        "event_id": event_id,
        "timestamp": utc_now(),
        "path": str(artifact_path.relative_to(root)),
        "artifact_id": ident,
        "old": old,
        "new": new,
        "provenance": {"kind": provenance, "actor": actor},
        "artifact_before_hash": sha256(artifact_before),
        "artifact_after_hash": sha256(artifact_after),
    }
    encoded = base64.b64encode(canonical_json(event)).decode("ascii")
    prefix = before if before.endswith(b"\n") else before + b"\n"
    return prefix + display.encode("utf-8") + f"<!-- sdd-event:{encoded} -->\n".encode("ascii")


def _error(error: MutationError, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"ok": False, "code": error.code, "message": str(error)}, ensure_ascii=False))
    else:
        print(f"ERROR [{error.code}]: {error}", file=sys.stderr)
    return error.exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="BitzSDD status遷移ツール")
    parser.add_argument("workspace")
    parser.add_argument("ident", nargs="?")
    parser.add_argument("--to", dest="to")
    parser.add_argument("--interactive-decision", action="store_true")
    parser.add_argument("--actor")
    parser.add_argument("--recover", metavar="EVENT_ID")
    parser.add_argument("--recover-lock", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()
    root = Path(args.workspace).resolve()

    try:
        if args.recover:
            outcome = recover(root, args.recover)
            print(json.dumps({"ok": True, "recovery": outcome}, ensure_ascii=False)
                  if args.json_output else f"復旧: {args.recover} ({outcome})")
            return 0
        if args.recover_lock:
            outcome = recover_lock(root)
            print(json.dumps({"ok": True, "recovery": outcome}, ensure_ascii=False)
                  if args.json_output else f"復旧: {outcome}")
            return 0
        if not args.ident or not args.to:
            parser.error("status遷移にはidentと--toが必要です")

        kind, path = locate(root, args.ident)
        if kind is None:
            raise MutationError("precondition-failed", f"IDが見つかりません: {args.ident}", 2)
        initial = path.read_text(encoding="utf-8")
        old = read_status(initial)
        new = normalize_status(kind, args.to)
        if old == new:
            raise MutationError("precondition-failed", f"{args.ident}は既に{new}です", 2)
        required = TRANSITIONS[kind].get((old, new))
        if required is None:
            raise MutationError("precondition-failed", f"不正遷移: {old} -> {new}", 2)
        if required == "human":
            if not args.interactive_decision:
                raise MutationError(
                    "authorization-required",
                    "人間裁定必須遷移には--interactive-decisionが必要です",
                    3,
                )
            actor = validate_actor(args.actor or "")
            confirm_interactively(args.ident, old, new)
            provenance = "interactive-confirmation-unverified"
        else:
            if args.interactive_decision:
                raise MutationError(
                    "authorization-required",
                    "--interactive-decisionは人間裁定必須遷移にだけ使用できます",
                    3,
                )
            actor = validate_actor(args.actor or "agent")
            provenance = "agent"

        state_path = root / ".spec" / "STATE.md"

        def prepare(owner: dict) -> TransactionPlan:
            current_bytes = path.read_bytes()
            current_text = current_bytes.decode("utf-8")
            current_status = read_status(current_text)
            if current_status != old:
                raise MutationError(
                    "precondition-failed",
                    f"確認後にstatusが変化しました: {old} -> {current_status}",
                    4,
                )
            _check_task_preconditions(root, args.ident, old, new)
            artifact_after = rewrite_status(current_text, new).encode("utf-8")
            actual_state_path, state_before = _state_before(root)
            state_after = _state_after(
                state_before,
                owner["event_id"],
                args.ident,
                path,
                old,
                new,
                actor,
                provenance,
                current_bytes,
                artifact_after,
                root,
            )
            return TransactionPlan(
                changes=(
                    FileChange(path, current_bytes, artifact_after),
                    FileChange(
                        actual_state_path,
                        actual_state_path.read_bytes() if actual_state_path.exists() else None,
                        state_after,
                    ),
                ),
                metadata={
                    "kind": kind,
                    "artifact_id": args.ident,
                    "old": old,
                    "new": new,
                    "provenance": provenance,
                },
            )

        event_id, _ = mutate(root, f"update {args.ident} {old}->{new}", (path, state_path), prepare)
        result = {
            "ok": True,
            "event_id": event_id,
            "artifact_id": args.ident,
            "old": old,
            "new": new,
            "provenance": provenance,
        }
        print(json.dumps(result, ensure_ascii=False) if args.json_output
              else f"遷移: {args.ident} {old} \u2192 {new}（{actor}; {provenance}）")
        return 0
    except MutationError as error:
        return _error(error, args.json_output)


if __name__ == "__main__":
    sys.exit(main())
