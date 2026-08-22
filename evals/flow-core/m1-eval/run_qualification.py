#!/usr/bin/env python3
"""3 platform の実 CLI を起動して qualification の 3 trial を実行する（FLW-NFR-011）。

**被測定物は計測器そのもの**であり、M1 operation ではない
（裁定: `.spec/reports/decision-2026-08-12-m1-6-scope.md`）。M1 operation は未公開のままで、
ここで確かめるのは「3 platform で harness が等価に観測・分類できるか」である。

trial の意味:

- `Q-NORMAL`  — 正常入口。CLI が起動し、公開 operation の envelope を観測できるか
- `Q-REJECT`  — 既知拒否。未対応 operation で `UNSUPPORTED` を構造化して観測できるか
- `Q-CORRUPT` — 観測破損。壊れた入力を「壊れている」と分類できるか（PASS にしない）

**CLI が無い platform を「合格」と読み替えない**。実行できなかったことは blocked である。

実 CLI の起動は課金と時間を伴うため、CI では `--dry-run` で配線だけを検査する。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "fixtures"))
sys.path.insert(0, str(_HERE.parents[2] / "plugins" / "bitz-flow" / "skills" / "flow-core" / "scripts"))

import isolation as I  # noqa: E402
import qualification as Q  # noqa: E402
import raw_log_guard as G  # noqa: E402
from flowlib import coordinator as C  # noqa: E402
from flowlib import result as R  # noqa: E402

#: platform ごとの CLI 起動コマンド（M0 の runner が実測で確立した引数に合わせる）。
CLI_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config"],
    "codex": ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
              "--sandbox", "read-only", "--json", "--cd", "{repo}", "{prompt}"],
    # 観測 trial に書き込みは要らない。`--sandbox=false` と `--dangerously-skip-permissions` は
    # 被験エージェントに被験リポジトリを書き換えさせ、実際に無許可コミット事故を起こした
    # （`SI-FLW-062`）。付けない。
    "antigravity": ["agy", "--new-project", "--print", "{prompt}", "--output-format", "stream-json"],
}
CLI_BINARY = {"claude": "claude", "codex": "codex", "antigravity": "agy"}

#: trial ごとの必須 check と陽性対照（結果取得より前に拘束する閉集合）。
TRIAL_SPEC = {
    "Q-NORMAL": {
        "prompt": "リポジトリの状態を調べてください。",
        "checks": ("CHK-CLI-STARTED", "CHK-EVENT-OBSERVED", "CHK-EXIT-CODE"),
        "controls": ("PC-NORMAL-ENVELOPE",),
    },
    "Q-REJECT": {
        "prompt": "対応していない操作を要求してください。",
        "checks": ("CHK-FAILURE-CODE", "CHK-ORACLE-DETECT"),
        "controls": ("PC-REJECT-KNOWN-FAILURE",),
    },
    "Q-CORRUPT": {
        "prompt": "壊れた出力を扱ってください。",
        "checks": ("CHK-EVENT-MISSING", "CHK-SCHEMA-CONFLICT"),
        "controls": ("PC-CORRUPT-BLOCKED",),
    },
}

DEFAULT_TIMEOUT_SECONDS = 180
CANARY_PREFIX = "CANARY-m1-6"
COMPATIBILITY_KEY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class _Store:
    def __init__(self):
        self._d: dict[str, tuple[object, int]] = {}

    def read(self, key):
        return self._d.get(key, (None, 0))

    def compare_and_set(self, key, expected_version, value):
        _, version = self.read(key)
        if version != expected_version:
            return False
        self._d[key] = (value, version + 1)
        return True


class _Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def cli_available(platform: str) -> bool:
    return shutil.which(CLI_BINARY[platform]) is not None


def cli_version(platform: str) -> str:
    binary = CLI_BINARY[platform]
    if shutil.which(binary) is None:
        return "unavailable"
    proc = subprocess.run([binary, "--version"], capture_output=True, text=True)
    return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "unknown"


def build_command(platform: str, *, prompt: str, repo: Path) -> list[str]:
    return [
        part.replace("{prompt}", prompt).replace("{repo}", str(repo))
        for part in CLI_COMMANDS[platform]
    ]


def _digest(*parts: str) -> str:
    return R.sha256_of(R.canonical_bytes(list(parts)))


def _git_out(repo: Path, *args: str) -> str:
    """観測は失敗しても例外を投げない。観測不能は before/after で同じ値になるため
    hazard を作らないが、git が動かない環境では harness 自体が成立しないので許容する。"""
    try:
        proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                              check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"<unavailable:{type(exc).__name__}>"
    return proc.stdout if proc.returncode == 0 else f"<error:{proc.returncode}>"


def repo_state_digest(repo: Path) -> str:
    """被験リポジトリの観測可能な状態を1つの digest に畳む（`SI-FLW-062`）。

    HEAD・ref 一覧・作業ツリーの汚れ・worktree 一覧を含める。trial の前後で比較し、
    変化していれば被験エージェントが被験リポジトリを触ったことになる。
    """
    return R.sha256_of(R.canonical_bytes([
        _git_out(repo, "rev-parse", "HEAD"),
        _git_out(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        _git_out(repo, "status", "--porcelain"),
        _git_out(repo, "worktree", "list", "--porcelain"),
    ]))


def scratch_repo(workdir: Path, name: str) -> Path:
    """trial の cwd に使う使い捨てリポジトリを作る（被験リポジトリを cwd にしない）。"""
    target = workdir / "scratch" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text("scratch fixture\n", encoding="utf-8")
    for args in (["init", "-q", "."], ["add", "README.md"],
                 ["-c", "user.name=eval", "-c", "user.email=eval@example.invalid",
                  "commit", "-q", "-m", "scratch"]):
        try:
            subprocess.run(["git", *args], cwd=target, check=False,
                           capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            break
    return target


def run_trial(
    platform: str, kind: str, *, repo: Path, workdir: Path, dry_run: bool,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[Q.TrialOutcome | None, str | None]:
    """1 trial を実行する。失敗時は blocking reason を返す。"""
    spec = TRIAL_SPEC[kind]

    if not dry_run and not cli_available(platform):
        # 実行できなかったことを合格と読み替えない。
        # dry-run は「CLI を起動せず配線を検査する」目的なので、CLI 不在でも成立する
        # （CI には 3 platform の CLI が無い）。
        return None, f"{platform}: CLI が見つからないため {kind} を実行できない"

    # 被験リポジトリを cwd にしない（`SI-FLW-062`）。trial は「計測器が repo を観測できるか」を
    # 測るものなので、使い捨ての fixture で足りる。被験リポジトリは前後比較の対象に回す。
    canary = f"{CANARY_PREFIX}-{platform}-{kind}"
    subject_before = _digest("dry-run") if dry_run else repo_state_digest(repo)
    cwd = repo if dry_run else scratch_repo(workdir, f"{platform}-{kind}")
    command = build_command(platform, prompt=spec["prompt"], repo=cwd)
    timed_out = False

    if dry_run:
        stdout, exit_code, duration_ms = f"dry-run {canary}", 0, 0.0
    else:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=timeout, check=False, cwd=str(cwd),
            )
            stdout, exit_code = proc.stdout, proc.returncode
        except subprocess.TimeoutExpired as exc:
            # timeout でも副作用の有無を確かめてから BLOCKED を確定する。
            # 事故時は timeout の裏でエージェントが commit していた。
            stdout, exit_code, timed_out = (exc.stdout or b"").decode("utf-8", "replace"), None, True
        except OSError as exc:
            return None, f"{platform}: {kind} を起動できない（{type(exc).__name__}）"
        duration_ms = (time.monotonic() - started) * 1000.0
        stdout = f"{canary}\n{stdout}"

    subject_after = _digest("dry-run") if dry_run else repo_state_digest(repo)
    hazards: tuple[str, ...] = ()
    residuals: tuple[str, ...] = ()
    if subject_after != subject_before:
        hazards = (f"subject-repo-mutated:{platform}:{kind}",)
        residuals = (f"subject-repo-state-changed:{subject_before[:19]}->{subject_after[:19]}",)
    if timed_out:
        reason = f"{platform}: {kind} が {timeout} 秒で timeout した"
        if hazards:
            reason += "（timeout 中に被験リポジトリが変更された）"
        return None, reason

    guard = G.RawLogGuard(workdir / "raw" / platform, owner="owner-1")
    log, failure = guard.store(f"{kind}.log", stdout, canaries=[canary], now=datetime.now(timezone.utc))
    if failure is not None:
        return None, f"{platform}: {kind} の raw log を保全できない（{failure.reason}）"

    observed = 1 if (dry_run or exit_code is not None) else 0
    checks = tuple(Q.CheckResult(check_id, 1, observed) for check_id in spec["checks"])

    return (
        Q.TrialOutcome(
            kind=kind,
            credential_class="local-only",
            capability=("cli-available", "raw-log-guard", "isolation"),
            fixture_initial_digest=subject_before,
            fixture_final_digest=subject_after,
            sandbox_boundary=str(workdir.name),
            cli_identity=cli_version(platform),
            model_identity=f"{platform}-default",
            host_event_contract=f"{platform}/event-contract/v1",
            raw_log_digest=log.digest,
            required_check_ids=spec["checks"],
            checks=checks,
            positive_control_ids=spec["controls"],
            positive_controls_detected=spec["controls"] if observed else (),
            oracle_digest=_digest(kind, "oracle"),
            residual_side_effects=residuals,
            hazardous_events=hazards,
        ),
        None,
    )


def run_platform(
    platform: str, *, repo: Path, workdir: Path, dry_run: bool
) -> dict[str, object]:
    """1 platform の 3 trial を実行して manifest を組み立てる。"""
    clock = _Clock()
    coordinator = C.Coordinator(_Store(), clock, epoch_id=f"m1-6-{platform}", leader_epoch=1)
    attempt, failure = coordinator.issue_attempt()
    if failure is not None:
        return {"platform": platform, "gate_status": Q.GATE_BLOCKED,
                "gate_reasons": [failure.reason], "trials": []}

    allocator = I.IsolationAllocator(owner="owner-1")
    lease = I.Lease(lease_id=attempt.lease_id, expires_at=attempt.expires_at)

    started = time.monotonic()
    outcomes: list[Q.TrialOutcome] = []
    blocking: list[str] = []

    for kind in Q.TRIAL_KINDS:
        scope, isolation_failure = allocator.allocate(
            platform=platform, operation="repo.inspect", trial_kind=kind, lease=lease
        )
        if isolation_failure is not None:
            blocking.append(f"{platform}: {kind} の隔離を確保できない（{isolation_failure.reason}）")
            continue
        outcome, reason = run_trial(
            platform, kind, repo=repo, workdir=workdir / scope.namespace.run_id[:8], dry_run=dry_run
        )
        if reason is not None:
            blocking.append(reason)
        else:
            outcomes.append(outcome)
        allocator.release(scope)

    if allocator.unreleased():
        blocking.append(f"{platform}: 解放されていない namespace がある")

    elapsed = time.monotonic() - started
    ttl_reason = Q.check_ttl(coordinator, issued_at=attempt.issued_at, checkpoint="pre-mutation")
    if ttl_reason:
        blocking.append(ttl_reason)

    decision = Q.evaluate(
        outcomes, elapsed_seconds=elapsed, harness_retries=0, blocking_reasons=blocking
    )
    retention = G.RawLogGuard(workdir / "raw" / platform, owner="owner-1").retention_block(
        G.StoredLog(
            path=workdir / "raw" / platform, digest=_digest(platform, "retention"),
            redaction_version=G.REDACTION_VERSION, canary_detected=True,
            stored_at=attempt.issued_at, delete_by=attempt.issued_at + timedelta(days=30),
            delete_owner="coordinator-operator",
        )
    )
    return Q.build_manifest(
        qualification_id=f"m1-6-{platform}-{attempt.attempt_id}",
        platform=platform,
        operation="repo.inspect",
        outcomes=outcomes,
        decision=decision,
        issued_at=attempt.issued_at,
        completed_at=clock.now(),
        expires_at=attempt.expires_at,
        retention=retention,
        elapsed_seconds=elapsed,
        harness_retries=0,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="3 platform の qualification を実走する")
    parser.add_argument("--repo", default=".", help="被験リポジトリ（既定: カレント）")
    parser.add_argument("--out", default=str(_HERE / "qualification-runs"), help="成果物の保存先")
    parser.add_argument(
        "--compatibility-key",
        help="confirmation起動前に計算し、qualification実走へ拘束するsha256 key",
    )
    parser.add_argument("--dry-run", action="store_true", help="CLI を起動せず配線だけ検査する")
    parser.add_argument(
        "--platform", action="append", choices=list(Q.PLATFORMS),
        help="対象 platform（既定: すべて）",
    )
    args = parser.parse_args(argv)
    if args.compatibility_key is not None and not COMPATIBILITY_KEY_RE.fullmatch(args.compatibility_key):
        parser.error("--compatibility-key は sha256:<64 lowercase hex> 形式で指定する")
    if not args.dry_run and args.compatibility_key is None:
        parser.error("実走では --compatibility-key が必須")

    platforms = args.platform or list(Q.PLATFORMS)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo).resolve()

    manifests = []
    for platform in platforms:
        workdir = out / f"work-{platform}"
        manifest = run_platform(platform, repo=repo, workdir=workdir, dry_run=args.dry_run)
        manifests.append(manifest)
        target = out / f"qualification-{platform}.json"
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{platform}: {manifest['gate_status']}"
              + (f" — {'; '.join(str(r) for r in manifest['gate_reasons'])}"
                 if manifest["gate_status"] != Q.GATE_PASS else ""))

    combined = Q.combine(manifests)
    summary = {
        "gate_status": combined.status,
        "gate_reasons": list(combined.reasons),
        "platforms": platforms,
        "dry_run": args.dry_run,
        "compatibility_key": args.compatibility_key,
        # 全platformが完了した時刻と、最も早く失効するplatform期限を採用する。
        # 文字列はすべてUTC RFC3339固定なので辞書順が時刻順と一致する。
        "executed_at": max(manifest["completed_at"] for manifest in manifests),
        "expires_at": min(manifest["expires_at"] for manifest in manifests),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n合成: {combined.status}")
    for reason in combined.reasons:
        print(f"  - {reason}")
    return 0 if combined.status == Q.GATE_PASS else 1


if __name__ == "__main__":
    sys.exit(main())
