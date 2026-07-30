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
from spec_inspect import gate_field_list, parse_frontmatter_full  # noqa: E402
from spec_labels import normalize_status  # noqa: E402
from spec_trace import tasks_for_requirement  # noqa: E402
from spec_transaction import (  # noqa: E402
    BatchMutationError,
    FileChange,
    MutationError,
    TransactionPlan,
    canonical_json,
    mutate,
    mutate_many,
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


def validate_name(value: str, label: str) -> str:
    if not value or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise MutationError(
            "authorization-required",
            f"{label}は1〜128文字で改行・ASCII制御文字を含めないでください",
            3,
        )
    return value


def validate_actor(actor: str) -> str:
    return validate_name(actor, "actor")


def validate_decision_ref(root: Path, value: str) -> str:
    """SDD-FR-145: 裁定所在参照。workspace相対パス（実在必須）またはhttps URL。"""
    if not value or len(value) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise MutationError(
            "authorization-required",
            "decision-refは1〜512文字で改行・ASCII制御文字を含めないでください",
            3,
        )
    if value.startswith("https://"):
        if len(value) == len("https://"):
            raise MutationError("authorization-required", "decision-refのURLが不完全です", 3)
        return value
    target = value.split("#", 1)[0]
    if not target or target.startswith(("/", "~")) or "\\" in target:
        raise MutationError(
            "authorization-required",
            "decision-refはworkspace相対パスまたはhttps:// URLを指定してください",
            3,
        )
    resolved = (root / target).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise MutationError(
            "authorization-required",
            f"decision-refのパスはworkspace外を指せません: {target}",
            3,
        )
    if not resolved.is_file():
        raise MutationError(
            "authorization-required",
            f"decision-refの参照先が存在しません: {target}",
            3,
        )
    return value


def validate_gate_passage(root: Path, gate_id: str, idents: list) -> None:
    """SDD-FR-157: promoted 遷移が参照する GatePassage の実在・種別・scope 包含を検査する。

    Gate の実行単位は「1 GatePassage = 1回の Gate 実行」であり、対象は scope に明示列挙する
    （feature 単位に固定しない）。scope に無い ID を1件でも含む要求は適用前に拒否する。
    """
    validate_name(gate_id, "gate-passage")
    path = root / ".spec" / "gates" / f"{gate_id}.md"
    if not path.is_file():
        raise MutationError(
            "precondition-failed",
            f"GatePassageが見つかりません: {gate_id}（.spec/gates/{gate_id}.md）",
            4,
        )
    fm = parse_frontmatter_full(path.read_text(encoding="utf-8"))
    if fm.get("gate") != "promotion":
        raise MutationError(
            "precondition-failed",
            f"{gate_id}のgateは'promotion'である必要があります: {fm.get('gate') or 'missing'}",
            4,
        )
    scope = set(gate_field_list(fm, "scope"))
    missing = [ident for ident in idents if ident not in scope]
    if missing:
        raise MutationError(
            "precondition-failed",
            f"{gate_id}のscopeに含まれないIDがあります: " + ", ".join(missing),
            4,
        )


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
    on_behalf_of: str = "",
    decision_ref: str = "",
    gate_passage: str = "",
) -> bytes:
    if provenance == "agent-proxy-unverified":
        schema_version = 2
        display_actor = f"{actor} on behalf of {on_behalf_of}"
        human_suffix = f"; 代行実行・実行者未検証・裁定参照: {decision_ref}"
        provenance_field = {
            "kind": provenance,
            "actor": actor,
            "on_behalf_of": on_behalf_of,
            "decision_ref": decision_ref,
        }
    else:
        schema_version = 1
        display_actor = actor
        human_suffix = (
            "; 対話入力確認済み（実行者未検証）"
            if provenance == "interactive-confirmation-unverified"
            else ""
        )
        provenance_field = {"kind": provenance, "actor": actor}
    if gate_passage:
        human_suffix += f"; Gate\u901a\u904e\u8a18\u9332: {gate_passage}"
    display = (
        f"- {date.today().isoformat()} {ident}: {old} \u2192 {new} "
        f"({display_actor}{human_suffix})\n"
    )
    event = {
        "schema_version": schema_version,
        "event_id": event_id,
        "timestamp": utc_now(),
        "path": str(artifact_path.relative_to(root)),
        "artifact_id": ident,
        "old": old,
        "new": new,
        "provenance": provenance_field,
        "artifact_before_hash": sha256(artifact_before),
        "artifact_after_hash": sha256(artifact_after),
    }
    if gate_passage:
        # SDD-FR-157: 検分の証跡を遷移そのものに残す。schema_version は変更しない
        # （必須キー集合は不変で、追加キーは既存の検査を通る — 順序6 を加法的に保つ）
        event["gate_passage"] = gate_passage
    encoded = base64.b64encode(canonical_json(event)).decode("ascii")
    prefix = before if before.endswith(b"\n") else before + b"\n"
    return prefix + display.encode("utf-8") + f"<!-- sdd-event:{encoded} -->\n".encode("ascii")


def _error(error: MutationError, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"ok": False, "code": error.code, "message": str(error)}, ensure_ascii=False))
    else:
        print(f"ERROR [{error.code}]: {error}", file=sys.stderr)
    return error.exit_code


def _prepare_transition(
    root: Path,
    state_path: Path,
    kind: str,
    path: Path,
    ident: str,
    old: str,
    new: str,
    actor: str,
    provenance: str,
    on_behalf_of: str = "",
    decision_ref: str = "",
    gate_passage: str = "",
):
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
        _check_task_preconditions(root, ident, old, new)
        artifact_after = rewrite_status(current_text, new).encode("utf-8")
        actual_state_path, state_before = _state_before(root)
        state_after = _state_after(
            state_before,
            owner["event_id"],
            ident,
            path,
            old,
            new,
            actor,
            provenance,
            current_bytes,
            artifact_after,
            root,
            on_behalf_of,
            decision_ref,
            gate_passage,
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
                "artifact_id": ident,
                "old": old,
                "new": new,
                "provenance": provenance,
            },
        )

    return prepare


def main() -> int:
    parser = argparse.ArgumentParser(description="BitzSDD status遷移ツール")
    parser.add_argument("workspace")
    parser.add_argument("ident", nargs="*")
    parser.add_argument("--to", dest="to")
    parser.add_argument("--interactive-decision", action="store_true")
    parser.add_argument("--actor")
    parser.add_argument("--on-behalf-of", dest="on_behalf_of")
    parser.add_argument("--decision-ref", dest="decision_ref")
    parser.add_argument("--gate-passage", dest="gate_passage",
                        help="verified→promoted で参照する GatePassage ID（SDD-FR-157。必須）")
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

        idents = args.ident
        if len(set(idents)) != len(idents):
            raise MutationError("precondition-failed", "IDが重複しています", 2)
        proxy = args.on_behalf_of is not None or args.decision_ref is not None
        if proxy and args.interactive_decision:
            raise MutationError(
                "authorization-required",
                "--interactive-decisionと--on-behalf-ofは併用できません",
                3,
            )
        if not proxy and len(idents) > 1:
            raise MutationError(
                "authorization-required",
                "複数IDの一括遷移は代行可視化経路（--on-behalf-of）でのみ使用できます",
                3,
            )

        entries = []
        for ident in idents:
            kind, path = locate(root, ident)
            if kind is None:
                raise MutationError("precondition-failed", f"IDが見つかりません: {ident}", 2)
            old = read_status(path.read_text(encoding="utf-8"))
            new = normalize_status(kind, args.to)
            if old == new:
                raise MutationError("precondition-failed", f"{ident}は既に{new}です", 2)
            required = TRANSITIONS[kind].get((old, new))
            if required is None:
                raise MutationError("precondition-failed", f"不正遷移: {old} -> {new}", 2)
            entries.append((ident, kind, path, old, new, required))

        # SDD-FR-157: verified→promoted は GatePassage の参照を必須とする。
        # 本規律は導入後の遷移にだけ適用し、既存の promoted 済み成果物へは遡及しない。
        promoted = [entry[0] for entry in entries
                    if (entry[3], entry[4]) == ("verified", "promoted")]
        gate_passage = args.gate_passage or ""
        if promoted:
            if not gate_passage:
                raise MutationError(
                    "authorization-required",
                    "verified→promoted遷移には--gate-passage <GatePassage ID>が必要です"
                    "（.spec/gates/ の通過記録に decision-ref の検分を残す）",
                    3,
                )
            validate_gate_passage(root, gate_passage, promoted)
        elif gate_passage:
            raise MutationError(
                "authorization-required",
                "--gate-passageはverified→promoted遷移にだけ使用できます",
                3,
            )

        state_path = root / ".spec" / "STATE.md"

        if proxy:
            # SDD-FR-145: 代行可視化経路。TTYは要求しないが3項と裁定所在参照を要求する
            if not (args.on_behalf_of and args.decision_ref and args.actor):
                raise MutationError(
                    "authorization-required",
                    "代行可視化経路には--on-behalf-of・--decision-ref・--actorの3項すべてが必要です",
                    3,
                )
            non_human = [entry[0] for entry in entries if entry[5] != "human"]
            if non_human:
                raise MutationError(
                    "authorization-required",
                    "代行可視化経路は人間裁定必須遷移にだけ使用できます: " + ", ".join(non_human),
                    3,
                )
            actor = validate_actor(args.actor)
            on_behalf_of = validate_name(args.on_behalf_of, "on-behalf-of")
            decision_ref = validate_decision_ref(root, args.decision_ref)
            provenance = "agent-proxy-unverified"
            prepares = [
                _prepare_transition(
                    root, state_path, kind, path, ident, old, new,
                    actor, provenance, on_behalf_of, decision_ref, gate_passage,
                )
                for ident, kind, path, old, new, _ in entries
            ]
            lock_paths = tuple(entry[2] for entry in entries) + (state_path,)
            results = mutate_many(
                root, f"update {' '.join(idents)} --to {args.to}", lock_paths, prepares,
            )
            if args.json_output:
                print(json.dumps({
                    "ok": True,
                    "provenance": provenance,
                    "results": [
                        {
                            "event_id": event_id,
                            "artifact_id": metadata["artifact_id"],
                            "old": metadata["old"],
                            "new": metadata["new"],
                        }
                        for event_id, metadata in results
                    ],
                }, ensure_ascii=False))
            else:
                for _, metadata in results:
                    print(
                        f"遷移: {metadata['artifact_id']} {metadata['old']} \u2192 "
                        f"{metadata['new']}（{actor} on behalf of {on_behalf_of}; {provenance}）"
                    )
            return 0

        ident, kind, path, old, new, required = entries[0]
        if required == "human":
            if not args.interactive_decision:
                raise MutationError(
                    "authorization-required",
                    "人間裁定必須遷移には--interactive-decision（対話確認経路）"
                    "または--on-behalf-of（代行可視化経路）が必要です",
                    3,
                )
            actor = validate_actor(args.actor or "")
            confirm_interactively(ident, old, new)
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

        prepare = _prepare_transition(
            root, state_path, kind, path, ident, old, new, actor, provenance,
            gate_passage=gate_passage,
        )
        event_id, _ = mutate(root, f"update {ident} {old}->{new}", (path, state_path), prepare)
        result = {
            "ok": True,
            "event_id": event_id,
            "artifact_id": ident,
            "old": old,
            "new": new,
            "provenance": provenance,
        }
        print(json.dumps(result, ensure_ascii=False) if args.json_output
              else f"遷移: {ident} {old} \u2192 {new}（{actor}; {provenance}）")
        return 0
    except BatchMutationError as error:
        applied = [
            {
                "event_id": event_id,
                "artifact_id": metadata.get("artifact_id"),
                "old": metadata.get("old"),
                "new": metadata.get("new"),
            }
            for event_id, metadata in error.applied
        ]
        applied_ids = {item["artifact_id"] for item in applied}
        unapplied = [ident for ident in args.ident if ident not in applied_ids]
        if args.json_output:
            print(json.dumps({
                "ok": False,
                "code": error.code,
                "message": str(error),
                "applied": applied,
                "unapplied": unapplied,
            }, ensure_ascii=False))
        else:
            for item in applied:
                print(
                    f"適用済み: {item['artifact_id']} {item['old']} \u2192 {item['new']}",
                    file=sys.stderr,
                )
            if unapplied:
                print("未適用: " + ", ".join(unapplied), file=sys.stderr)
            print(f"ERROR [{error.code}]: {error}", file=sys.stderr)
        return error.exit_code
    except MutationError as error:
        return _error(error, args.json_output)


if __name__ == "__main__":
    sys.exit(main())
