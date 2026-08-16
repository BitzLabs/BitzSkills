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
from datetime import datetime, timedelta, timezone
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
    r"runtime_checks=(\d+)/(\d+) hazards=0 residuals=0"
)
SUITE_MARKER = re.compile(
    r"M2_CONFIRMATION_SUITE tests=(\d+) test_id_digest=(sha256:[0-9a-f]{64}) runtime_checks=(\d+)"
)
#: compatibility key の入力（`FLW-NFR-011`）。
#: 認可核（capability / guard / cleanup / recovery）と被測定 fixture を含めないと、
#: 安全判断を変えても manifest が失効しなかった（`FLW-REV-016:SYN-008`）。
_SKILL = "plugins/bitz-flow/skills/flow-core"
_FLOWLIB = f"{_SKILL}/scripts/flowlib"
COMPATIBILITY_INPUTS = (
    "plugins/bitz-flow/plugin.json",
    f"{_SKILL}/SKILL.md",
    f"{_SKILL}/scripts/flow.py",
    f"{_FLOWLIB}/cli.py",
    f"{_FLOWLIB}/worktree_runtime.py",
    # 認可核（SYN-008 で追加）
    f"{_FLOWLIB}/worktree_capability.py",
    f"{_FLOWLIB}/guard.py",
    f"{_FLOWLIB}/worktree_cleanup.py",
    f"{_FLOWLIB}/recovery.py",
    # digest の定義元。ここが変われば operation_id も snapshot も変わる
    f"{_FLOWLIB}/result.py",
    # harness
    "evals/flow-core/m2-eval/local_confirmation_subject.py",
    "evals/flow-core/m2-eval/run_local_confirmation.py",
)

#: 被測定 fixture。`local_confirmation_subject.FILES` と同一集合を指紋へ含める。
def _fixture_inputs(root: Path) -> tuple[str, ...]:
    sys.path.insert(0, str(Path(__file__).parent))
    import local_confirmation_subject as S  # noqa: E402
    return tuple(S.FILES)


#: qualification fingerprint は 24 時間、confirmation evidence は 7 日（`FLW-NFR-011`）。
QUALIFICATION_TTL = timedelta(hours=24)
CONFIRMATION_TTL = timedelta(days=7)


def _parse_time(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


#: raw log へ仕込む観測可能性 canary。redaction が効いているかを検査するために要る。
CANARY_PREFIX = "bitz-flow-m2-confirmation-canary"


def _store_raw_log(out: Path, platform: str, raw: str, now: datetime) -> dict:
    """raw log を owner-only 境界と保持期限つきで保存する（`FLW-REV-016:SYN-004`）。

    従来は digest だけ残して本体を破棄しており、hazard 0 / residual 0 を後から
    検証できなかった。M1 の `raw_log_guard` を再利用する。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1-eval"))
    import raw_log_guard as G  # noqa: E402

    guard = G.RawLogGuard(out / "raw", owner="owner-1")
    canary = f"{CANARY_PREFIX}-{platform}"
    log, failure = guard.store(f"{platform}.log", f"{canary}\n{raw}",
                               canaries=[canary], now=now)
    if failure is not None:
        return {"stored": False, "reason": failure.reason}
    return {
        "stored": True,
        "path": str(log.path.relative_to(out)),
        "digest": log.digest,
        "stored_at": log.stored_at.isoformat().replace("+00:00", "Z"),
        "delete_by": log.delete_by.isoformat().replace("+00:00", "Z"),
        "delete_owner": log.delete_owner,
        "canary_detected": log.canary_detected,
        "redaction_version": log.redaction_version,
        "redactions": list(log.redactions),
        "allowed_roles": list(G.ALLOWED_ROLES),
    }


def _verify_for_gate(manifest_path: Path, current_key: str, now: datetime) -> int:
    """Gate へ採用する直前に、証跡がまだ有効かを再照合する（`FLW-NFR-011`）。

    起動時の TTL 照合だけでは、採用時点で失効した証跡を止められなかった
    （`FLW-REV-017:OPS-402`）。confirmation evidence は 7 日、参照する
    qualification fingerprint は 24 時間を超えていないことを確かめる。
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    if manifest.get("gate_status") != "PASS":
        problems.append(f"gate_status={manifest.get('gate_status')}")
    if manifest.get("compatibility_key") != current_key:
        problems.append("compatibility_key が現在の被測定物と一致しない")
    expires = _parse_time(manifest.get("expires_at"))
    if expires is None or now > expires:
        problems.append(f"confirmation evidence が失効している（expires_at={manifest.get('expires_at')}）")
    reference = manifest.get("qualification_ref") or {}
    executed = _parse_time(reference.get("executed_at"))
    if executed is None:
        problems.append("qualification_ref.executed_at が無い")
    elif now - executed > QUALIFICATION_TTL:
        problems.append(f"qualification fingerprint が 24 時間を超えている（{now - executed}）")
    for problem in problems:
        print(f"Gate 採用不可: {problem}")
    if problems:
        return 1
    print("Gate 採用可: TTL と指紋を再照合した")
    return 0


def _append_attempt(out: Path, record: dict) -> None:
    """attempt を append-only の台帳へ残す。成功で上書きしない。"""
    ledger = out / "attempts.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(record)
    entry["recorded_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _git_out(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"<unavailable:{type(exc).__name__}>"
    return proc.stdout if proc.returncode == 0 else f"<error:{proc.returncode}>"


def repo_state_digest(root: Path) -> str:
    """被験リポジトリの観測可能な状態（`SI-FLW-062`）。

    confirmation は被験リポジトリ自身でテストを走らせるため cwd を隔離できない。
    代わりに前後を比較し、subject の実行以外の変化を hazard として実測する。
    以前は hazard / residual を `0 if valid else 1` の固定写像にしており、
    実際に起きた無許可コミットを見逃した（`FLW-REV-016:SYN-007` / `SI-FLW-062`）。
    """
    return _digest("\u0000".join([
        _git_out(root, "rev-parse", "HEAD"),
        _git_out(root, "for-each-ref", "--format=%(refname) %(objectname)"),
        _git_out(root, "status", "--porcelain"),
        _git_out(root, "worktree", "list", "--porcelain"),
    ]))


def compatibility_key(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in tuple(COMPATIBILITY_INPUTS) + _fixture_inputs(root):
        digest.update(relative.encode() + b"\0")
        digest.update((root / relative).read_bytes())
    return "sha256:" + digest.hexdigest()


def published_operations(root: Path) -> tuple[str, ...]:
    """出荷表に載っている operation だけを返す（`FLW-REV-016:SYN-005`）。

    manifest が `git.stage` などの未公開 operation や `worktree.*` の
    ワイルドカードを確認済みとして並べていたのを、実体から導く形へ変える。
    """
    sys.path.insert(0, str(root / _SKILL / "scripts"))
    from flowlib import cli  # noqa: E402
    return tuple(sorted(f"{domain}.{action}" for domain, action in cli.PUBLISHED_OPERATIONS))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out")
    parser.add_argument("--qualification")
    parser.add_argument("--compatibility-key")
    parser.add_argument("--print-compatibility-key", action="store_true")
    parser.add_argument("--verify-for-gate", metavar="MANIFEST",
                        help="Gate 採用時の再照合（TTL・指紋）。非ゼロ終了で不採用を示す")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    current_key = compatibility_key(root)
    if args.print_compatibility_key:
        print(current_key)
        return 0
    if args.verify_for_gate:
        return _verify_for_gate(Path(args.verify_for_gate), current_key,
                                datetime.now(timezone.utc))
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

    # `FLW-NFR-011`: qualification fingerprint は 24 時間以内であることを直前に再照合する。
    # 期限切れを `blocked` にせず confirmation を起動していた（`FLW-REV-016:SYN-009`）。
    now = datetime.now(timezone.utc)
    executed_at = _parse_time(qualification.get("executed_at"))
    if executed_at is None:
        print("qualification executed_at を読めない")
        return 1
    age = now - executed_at
    if age > QUALIFICATION_TTL:
        print(f"qualification fingerprint expired: {age} > {QUALIFICATION_TTL}")
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
            state_before = repo_state_digest(root)
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
                # hazard / residual は実測する（`SI-FLW-062`）。
                state_after = repo_state_digest(root)
                mutated = state_after != state_before
                if mutated:
                    valid = False
                record = {
                    "platform": platform,
                    "status": "PASS" if valid else "FAIL",
                    "tests": int(match.group(1)) if match else 0,
                    "test_id_digest": match.group(2) if match else None,
                    "runtime_checks": f"{match.group(3)}/{match.group(4)}" if match else "0/8",
                    "hazardous_events": 1 if mutated else 0,
                    "residual_side_effects": 1 if mutated else 0,
                    "subject_state_before": state_before,
                    "subject_state_after": state_after,
                    "raw_log": _store_raw_log(out, platform, raw, datetime.now(timezone.utc)),
                    "raw_log_digest": _digest(raw),
                    "raw_log_committed": False,
                }
                _append_attempt(out, record)
            except (subprocess.TimeoutExpired, OSError) as exc:
                # timeout でも副作用を確かめてから BLOCKED を確定する（`SI-FLW-062`）。
                state_after = repo_state_digest(root)
                record = {"platform": platform, "status": "BLOCKED", "reason": type(exc).__name__,
                          "hazardous_events": 1 if state_after != state_before else 0,
                          "subject_state_before": state_before,
                          "subject_state_after": state_after}
                # 失敗 attempt を捨てずに併記する（`FLW-NFR-011`。`FLW-REV-017:OPS-104` /
                # `RSK-403`。codex は 5/5 で初回 timeout する恒常欠陥であり、
                # 成功分だけ残すとその規則性が証跡から消える）。
                _append_attempt(out, record)
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        records.append(record)
        print(f"{platform}: {record['status']}")

    status = "PASS" if all(record["status"] == "PASS" for record in records) else "BLOCKED"
    issued = datetime.now(timezone.utc)
    manifest = {
        "schema": "bitz-flow/m2-local-confirmation/v2",
        "issued_at": issued.isoformat().replace("+00:00", "Z"),
        # confirmation evidence は 7 日以内であることを Gate 採用時に再照合する（`FLW-NFR-011`）。
        "expires_at": (issued + CONFIRMATION_TTL).isoformat().replace("+00:00", "Z"),
        "compatibility_key": args.compatibility_key,
        # `compatibility_key`（再利用可能性）と `evidence_id`（run 固有）を分離する
        # （`FLW-NFR-011` / `FLW-REV-016:SYN-008`）。
        "evidence_id": _digest("\u0000".join(
            [args.compatibility_key, issued.isoformat()]
            + [str(record.get("raw_log_digest")) for record in records]
        )),
        "write_target": "local",
        # 出荷表から導く。未公開 operation やワイルドカードを確認済みとして並べない
        # （`FLW-REV-016:SYN-005`）。
        "operations": list(published_operations(root)),
        # Gate 採用時に再照合するための材料（`FLW-NFR-011`。`FLW-REV-017:OPS-402`。
        # 従来は起動時にしか TTL を見ておらず、採用時点での失効を検出できなかった）。
        "qualification_ref": {
            "executed_at": qualification.get("executed_at"),
            "expires_at": qualification.get("expires_at"),
            "compatibility_key": qualification.get("compatibility_key"),
        },
        "gated_operations": sorted(
            f"{d}.{a}" for d, a in __import__("flowlib.cli", fromlist=["cli"])._GATED_HANDLERS
        ),
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
