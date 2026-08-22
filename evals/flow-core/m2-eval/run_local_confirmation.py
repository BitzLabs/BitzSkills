#!/usr/bin/env python3
"""M2 write_target:local の3platform confirmation runner。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _coordinator_module():
    """`flowlib.coordinator` を遅延 import する（測定インフラ側の関心事。`raw_log_guard`
    と同じく harness 自身の位置から解決し、`--repo` の被測定物からは解決しない）。"""
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[3] / "plugins/bitz-flow/skills/flow-core/scripts")
    )
    import importlib

    return importlib.import_module("flowlib.coordinator")


PLATFORMS = ("claude", "codex", "antigravity")
BINARIES = {"claude": "claude", "codex": "codex", "antigravity": "agy"}
SUBJECT_COMMAND = "python3 {repo}/evals/flow-core/m2-eval/local_confirmation_subject.py --repo {repo}"
COMMANDS = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config", "--allowedTools",
               "Bash(python3 evals/flow-core/m2-eval/local_confirmation_subject.py:*)"],
    "codex": ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
              "--sandbox", "workspace-write", "--json", "--cd", "{repo}", "{prompt}"],
    "antigravity": ["agy", "--new-project", "--print", "{prompt}", "--output-format", "stream-json",
                    "--mode", "plan", "--disable-slash-commands", "--sandbox=false"],
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
    # headless Antigravity の限定 command allow。ここが変われば M2 confirmation の
    # 実行権限も変わるため、証跡の再利用対象に含める。
    ".agents/hooks.json",
    "scripts/agy_guard.py",
    # harness
    "evals/flow-core/m2-eval/local_confirmation_subject.py",
    "evals/flow-core/m2-eval/run_local_confirmation.py",
)
PYTEST_RUNTIME_PACKAGES = (
    "_pytest", "pytest", "pluggy", "packaging", "iniconfig", "pygments", "py.py",
)
PYTEST_RUNTIME_DISTRIBUTIONS = ("pytest", "pluggy", "packaging", "iniconfig", "pygments")

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


# --- attempt 台帳（coordinator / lease / hash chain）---------------------------
#
# `FLW-TSK-102`（`SI-FLW-075`）: 出口条件7の証跡は 0.02 秒のゲート照合1件であり、
# 3 platform の実走そのものではなかった。台帳を coordinator が発行する attempt ID・
# lease・hash chain で run と機械的に結び付ける（M1 の `evals/flow-core/m1-eval/
# run_qualification.py` と同じ `flowlib.coordinator.Coordinator` を再利用する）。


class _Store:
    """process 内 in-memory CAS store（m1-eval の `_Store` と同型）。"""

    def __init__(self) -> None:
        self._values: dict[str, tuple[object, int]] = {}

    def read(self, key):
        return self._values.get(key, (None, 0))

    def compare_and_set(self, key, expected_version, value):
        _, version = self.read(key)
        if version != expected_version:
            return False
        self._values[key] = (value, version + 1)
        return True


class _Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def cli_version(platform: str) -> str:
    """trial 証跡へ載せる CLI 版（`FLW-NFR-011`）。取得不能なら `unavailable`/`unknown`。"""
    binary = BINARIES[platform]
    if shutil.which(binary) is None:
        return "unavailable"
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    first_line = proc.stdout.strip().splitlines()
    return first_line[0] if first_line else "unknown"


def new_coordinator(epoch_id: str):
    """単一 authoritative coordinator を作る（`FLW-NFR-011`）。

    1回の confirmation run で共有し、platform をまたいで attempt ID を単調増加させる
    （`Store` を呼出しごとに作り直すと ID が常に 1 に戻り、単調増加にならない）。
    """
    coordinator_module = _coordinator_module()
    return coordinator_module.Coordinator(_Store(), _Clock(), epoch_id=epoch_id, leader_epoch=1)


def _last_ledger_line(ledger: Path) -> str | None:
    if not ledger.exists():
        return None
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines[-1] if lines else None


def verify_attempt_chain(ledger: Path) -> list[str]:
    """台帳の hash chain を検証する。台帳と run を機械的に結び付けられることを示す。"""
    if not ledger.exists():
        return []
    problems: list[str] = []
    previous_line: str | None = None
    seen_ids: set[int] = set()
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"{line_number}行目: JSON を読めない")
            previous_line = line
            continue
        expected_previous = _digest(previous_line) if previous_line is not None else None
        if entry.get("previous_entry_digest") != expected_previous:
            problems.append(f"{line_number}行目: previous_entry_digest が chain と一致しない")
        attempt_id = entry.get("attempt_id")
        if attempt_id in seen_ids:
            problems.append(f"{line_number}行目: attempt_id {attempt_id} が重複している")
        seen_ids.add(attempt_id)
        for field in ("attempt_id", "epoch_id", "lease_id", "fencing_token"):
            if entry.get(field) in (None, ""):
                problems.append(f"{line_number}行目: {field} が無い")
        previous_line = line
    return problems


def _append_attempt(out: Path, record: dict, *, attempt) -> dict:
    """attempt を hash-chain 付き append-only 台帳へ残す。成功で上書きしない。

    coordinator が発行した `attempt_id` / `epoch_id` / `lease_id` / `fencing_token` を
    載せ、`previous_entry_digest` で直前 entry と連結する（`FLW-TSK-102`）。
    """
    ledger = out / "attempts.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    previous_line = _last_ledger_line(ledger)
    entry = dict(record)
    entry.update({
        "attempt_id": attempt.attempt_id,
        "epoch_id": attempt.epoch_id,
        "lease_id": attempt.lease_id,
        "fencing_token": attempt.fencing_token,
        "issued_at": attempt.issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": attempt.expires_at.isoformat().replace("+00:00", "Z"),
        "previous_entry_digest": _digest(previous_line) if previous_line is not None else None,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    line = json.dumps(entry, ensure_ascii=False)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return entry


# --- 検出器の陽性対照（`RSK-402`）----------------------------------------------


def _detector_self_check(now: datetime) -> dict:
    """`repo_state_digest`（hazard 検出器）が実際に変化を検出できることを確認する。

    検出0件と検出器不作動を区別できないと、フェイルオープンな測定になる。使い捨ての
    一時 repo で意図的に変化させ、被測定物には一切触れずに検出器そのものを検査する。
    """
    try:
        with tempfile.TemporaryDirectory(prefix="bitz-flow-m2-detector-check-") as tmp:
            scratch = Path(tmp)
            for args in (
                ["init", "-q", "-b", "main"],
                ["config", "user.email", "detector-check@example.invalid"],
                ["config", "user.name", "detector-check"],
            ):
                subprocess.run(["git", *args], cwd=scratch, check=True, capture_output=True)
            (scratch / "seed.txt").write_text("seed\n", encoding="utf-8")
            subprocess.run(["git", "add", "seed.txt"], cwd=scratch, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=scratch, check=True,
                          capture_output=True)
            before = repo_state_digest(scratch)
            (scratch / "mutation.txt").write_text("mutated\n", encoding="utf-8")
            after = repo_state_digest(scratch)
        detected = before != after
        return {"detected": detected, "checked_at": now.isoformat().replace("+00:00", "Z")}
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "detected": False,
            "checked_at": now.isoformat().replace("+00:00", "Z"),
            "reason": f"陽性対照を実行できない（{type(exc).__name__}）",
        }


# --- residual（`RSK-402`。hazard と同一式で算出しない）-------------------------


def _classify_hazard_and_residual(mutated: bool) -> tuple[int, int | None, str | None]:
    """hazard は直接観測する。residual を hazard と同一式で算出してはならない。

    このharnessはhazard検出後の緩和ステップを持たないため、緩和後に残る量を独立の
    観測から算出できない。算出できない場合はresidualを報告しない（`None`）。
    """
    hazardous = 1 if mutated else 0
    if not mutated:
        return hazardous, 0, None
    return hazardous, None, (
        "緩和ステップを持たないため、hazard検出後の残余量を独立に観測できない。"
        "hazardと同一式では算出しない（FLW-TSK-102 / RSK-402）"
    )


def _apply_raw_log_gate(valid: bool, raw_log: dict) -> bool:
    """raw log の保存に失敗した trial を PASS として採用しない（`FLW-NFR-011` `OPS-101`）。"""
    return valid and bool(raw_log.get("stored"))


# --- 裁定スコープの allow（失効期限・撤去手段・登録者）-------------------------


SCOPE_ALLOWS: tuple[dict, ...] = (
    {
        "id": "m2-gp002-confirmation-subject",
        "scope": (
            "M2 GP-002 用の限定 confirmation subject の実行（agy_guard.py の "
            "read-only allowlist 経由での被験エージェント起動）"
        ),
        "decision_ref": "2026-08-14 GP-002 裁定",
        "registered_by": "repository-owner",
        "registered_at": "2026-08-14T00:00:00Z",
        "expires_at": "2027-02-10T00:00:00Z",
        "revocation": (
            "scripts/agy_guard.py の M2_SUBJECT_SCRIPT allowlist entry を削除し、"
            "この SCOPE_ALLOWS entry も削除する"
        ),
    },
)


def _expired_scope_allows(now: datetime, allows: tuple[dict, ...] = SCOPE_ALLOWS) -> list[dict]:
    """失効期限を過ぎた（または欠けた）scope allow を返す。空でなければ起動しない。"""
    expired = []
    for allow in allows:
        expires = _parse_time(allow.get("expires_at"))
        if expires is None or now >= expires:
            expired.append(allow)
    return expired


def _store_raw_log(out: Path, platform: str, raw: str, now: datetime) -> dict:
    """raw log を owner-only 境界と保持期限つきで保存する（`FLW-REV-016:SYN-004`）。

    従来は digest だけ残して本体を破棄しており、hazard 0 / residual 0 を後から
    検証できなかった。M1 の `raw_log_guard` を再利用する。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1-eval"))
    import raw_log_guard as G  # noqa: E402

    raw_root = out / "raw"
    guard = G.RawLogGuard(raw_root, owner="owner-1")
    canary = f"{CANARY_PREFIX}-{platform}"
    log, failure = guard.store(f"{platform}.log", f"{canary}\n{raw}",
                               canaries=[canary], now=now)
    if failure is not None:
        # 保存先 root は成否によらず証跡から特定できるようにする（`FLW-NFR-011`）。
        return {"stored": False, "reason": failure.reason, "root": str(raw_root)}
    return {
        "stored": True,
        "root": str(raw_root),
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


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _qualification_reference(root: Path, path: Path, qualification: dict) -> dict:
    """Gate へ提出する qualification の出所を、内容 digest とともに固定する。"""
    try:
        relative = path.resolve().relative_to(root)
        source_path = relative.as_posix()
    except ValueError:
        # dry-run の配線検査では pytest の一時成果物を入力にできる。Gate 採用時には
        # `_verify_qualification_reference()` がリポジトリ外 path を必ず拒否する。
        source_path = str(path.resolve())
    return {
        "path": source_path,
        "digest": _file_digest(path),
        "executed_at": qualification.get("executed_at"),
        "expires_at": qualification.get("expires_at"),
        "compatibility_key": qualification.get("compatibility_key"),
        "gate_status": qualification.get("gate_status"),
    }


def _verify_qualification_reference(root: Path, reference: dict) -> list[str]:
    """manifest が指す qualification の存在・内容・採用可否を再照合する。"""
    relative = reference.get("path")
    if not isinstance(relative, str) or not relative:
        return ["qualification_ref.path が無い"]
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ["qualification_ref.path がリポジトリ外を指す"]
    if not candidate.is_file():
        return ["qualification_ref.path の成果物が存在しない"]
    if reference.get("digest") != _file_digest(candidate):
        return ["qualification_ref.digest が成果物と一致しない"]
    try:
        qualification = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["qualification_ref.path の成果物を読めない"]
    problems = []
    for field in ("executed_at", "expires_at", "compatibility_key", "gate_status"):
        if reference.get(field) != qualification.get(field):
            problems.append(f"qualification_ref.{field} が成果物と一致しない")
    if qualification.get("gate_status") != "PASS":
        problems.append(f"qualification の gate_status={qualification.get('gate_status')}")
    return problems


def _evidence_path(manifest_dir: Path, relative: object, *, label: str) -> tuple[Path | None, str | None]:
    """manifest 相対の証跡 path を root escape なしに解決する。"""
    if not isinstance(relative, str) or not relative:
        return None, f"{label}.path が無い"
    candidate = (manifest_dir / relative).resolve()
    try:
        candidate.relative_to(manifest_dir.resolve())
    except ValueError:
        return None, f"{label}.path が manifest root 外を指す"
    return candidate, None


def _verify_confirmation_evidence(manifest_dir: Path, manifest: dict) -> list[str]:
    """raw log と attempt ledger が self-report でなく実体として成立するか検証する。"""
    problems: list[str] = []
    platforms = manifest.get("platforms")
    if not isinstance(platforms, list) or {row.get("platform") for row in platforms if isinstance(row, dict)} != set(PLATFORMS):
        return ["platforms が3 platformの閉集合ではない"]

    ledger_meta = manifest.get("attempt_ledger")
    if not isinstance(ledger_meta, dict):
        problems.append("attempt_ledger が無い")
    else:
        ledger, failure = _evidence_path(manifest_dir, ledger_meta.get("path"), label="attempt_ledger")
        if failure is not None:
            problems.append(failure)
        elif ledger is None or not ledger.is_file():
            problems.append("attempt_ledger の実体が存在しない")
        else:
            if ledger_meta.get("digest") != _file_digest(ledger):
                problems.append("attempt_ledger.digest が実体と一致しない")
            chain_problems = verify_attempt_chain(ledger)
            if chain_problems:
                problems.append("attempt_ledger の hash chain が不正: " + "; ".join(chain_problems))
            try:
                ledger_platforms = {
                    json.loads(line).get("platform")
                    for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()
                }
            except (OSError, json.JSONDecodeError):
                problems.append("attempt_ledger を読めない")
            else:
                if ledger_platforms != set(PLATFORMS):
                    problems.append("attempt_ledger が全 platform の trial を持たない")

    for record in platforms:
        platform = record["platform"]
        raw = record.get("raw_log")
        if not isinstance(raw, dict) or not raw.get("stored"):
            problems.append(f"{platform}: raw_log が保存済みではない")
            continue
        if raw.get("canary_detected") is not True:
            problems.append(f"{platform}: raw_log の canary 検出が確認できない")
        raw_path, failure = _evidence_path(manifest_dir, raw.get("path"), label=f"{platform}.raw_log")
        if failure is not None:
            problems.append(failure)
            continue
        raw_root = raw.get("root")
        if not isinstance(raw_root, str) or not raw_root:
            problems.append(f"{platform}: raw_log.root が無い")
            continue
        if raw_path is None or raw_path.parent != Path(raw_root).resolve():
            problems.append(f"{platform}: raw_log.root と path が一致しない")
            continue
        if not raw_path.is_file():
            problems.append(f"{platform}: raw_log の実体が存在しない")
            continue
        if raw.get("digest") != _file_digest(raw_path):
            problems.append(f"{platform}: raw_log.digest が実体と一致しない")
            continue
        # canary は raw_log_guard が秘密値として検出・redaction する対象である。
        # metadata の検出済み主張だけでなく、保存実体に平文が残っていないことも確認する。
        if f"{CANARY_PREFIX}-{platform}" in raw_path.read_text(encoding="utf-8"):
            problems.append(f"{platform}: raw_log に canary が平文で残っている")
    return problems


def _verify_for_gate(root: Path, manifest_path: Path, current_key: str, now: datetime) -> int:
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
    for problem in _verify_qualification_reference(root, reference):
        problems.append(problem)
    executed = _parse_time(reference.get("executed_at"))
    if executed is None:
        problems.append("qualification_ref.executed_at が無い")
    elif now - executed > QUALIFICATION_TTL:
        problems.append(f"qualification fingerprint が 24 時間を超えている（{now - executed}）")
    for problem in _verify_confirmation_evidence(manifest_path.parent, manifest):
        problems.append(problem)
    for problem in problems:
        print(f"Gate 採用不可: {problem}")
    if problems:
        return 1
    print("Gate 採用可: TTL と指紋を再照合した")
    return 0


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


def _subject_python(root: Path) -> Path:
    """親 runner 側で共有 worktree の検証用 Python を固定する。"""
    common = Path(_git_out(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    candidate = common.parent / ".venv" / "bin" / "python"
    return candidate.absolute() if candidate.is_file() else Path(sys.executable).resolve()


def _materialize_subject_runtime(runtime_parent: Path,
                                 source_python: Path) -> tuple[tempfile.TemporaryDirectory, Path]:
    """成果物root内へ、pytest専用の短命runtimeを作る。"""
    source_venv = source_python.parent.parent
    source_site = (
        source_venv / "lib" /
        f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    )
    # GitHub Actions の setup-python は pytest を仮想環境ではなく
    # `/opt/hostedtoolcache/.../x64` 配下へ導入する。呼出元が固定した Python と
    # 対応する site-packages が存在すれば、ディレクトリ名を `.venv` に限定しない。
    if not source_python.is_absolute() or not source_python.is_file() or not source_site.is_dir():
        raise RuntimeError("shared pytest runtime is unavailable")
    holder = tempfile.TemporaryDirectory(prefix=".bitz-confirmation-runtime-", dir=runtime_parent)
    runtime = Path(holder.name)
    runtime_bin = runtime / "bin"
    runtime_site = (
        runtime / "lib" /
        f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    )
    runtime_bin.mkdir(parents=True)
    runtime_site.mkdir(parents=True)
    runtime_python = runtime_bin / "python"
    shutil.copy2(source_python.resolve(), runtime_python)
    (runtime / "pyvenv.cfg").write_text(
        f"home = {source_python.resolve().parent}\n"
        "include-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n",
        encoding="utf-8",
    )
    for name in PYTEST_RUNTIME_PACKAGES:
        source = source_site / name
        if not source.exists():
            holder.cleanup()
            raise RuntimeError(f"pytest runtime component is unavailable: {name}")
        target = runtime_site / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    for distribution in PYTEST_RUNTIME_DISTRIBUTIONS:
        matches = list(source_site.glob(f"{distribution}-*.dist-info"))
        if len(matches) != 1:
            holder.cleanup()
            raise RuntimeError(f"pytest runtime metadata is ambiguous: {distribution}")
        shutil.copytree(matches[0], runtime_site / matches[0].name)
    return holder, runtime_python


def _platform_command(platform: str, prompt: str, root: Path,
                      subject_python: Path) -> list[str]:
    command = [part.replace("{prompt}", prompt).replace("{repo}", str(root))
               for part in COMMANDS[platform]]
    if platform == "antigravity":
        # 短命pytest runtimeもroot内へ置き、run_command mountは既存worktree 1個に固定する。
        command.extend(["--add-dir", str(root)])
    return command


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
        return _verify_for_gate(root, Path(args.verify_for_gate), current_key,
                                datetime.now(timezone.utc))
    if not (args.out and args.qualification and args.compatibility_key):
        parser.error("--out, --qualification, and --compatibility-key are required")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qualification_path = Path(args.qualification).resolve()
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
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

    # 検出器の陽性対照（`RSK-402`）。検出0件と検出器不作動を区別できない場合は
    # hazard/residualの0件主張を信用できないため、confirmationそのものを起動しない。
    detector_check = _detector_self_check(datetime.now(timezone.utc))
    if not detector_check["detected"]:
        print(f"検出器の陽性対照が検出できていない: {detector_check.get('reason', '')}")
        return 1

    # 裁定スコープのallow（失効期限・撤去手段・登録者）。失効した許可のまま
    # confirmationを起動しない（`FLW-NFR-011`）。
    expired_allows = _expired_scope_allows(datetime.now(timezone.utc))
    if expired_allows:
        for allow in expired_allows:
            print(f"裁定スコープの許可が失効している: {allow['id']}（expires_at={allow['expires_at']}）")
        return 1

    source_python = _subject_python(root)
    runtime_holder = None
    subject_python = source_python
    if not args.dry_run:
        runtime_holder, subject_python = _materialize_subject_runtime(root, source_python)
    subject_env = os.environ.copy()
    subject_env["BITZ_CONFIRMATION_PYTHON"] = str(subject_python)

    # 単一 coordinator を run 全体で共有し、platform をまたいで attempt ID を
    # 単調増加させる（`FLW-NFR-011`）。
    run_coordinator = new_coordinator("m2-local-confirmation")
    records = []
    for platform in PLATFORMS:
        # Antigravity の headless project は caller cwd を引き継がないため絶対 path を使う。
        # Claude / Codex は対象 repo を cwd にするので、Claude の closed allowedTools と同じ
        # 相対形を使う。いずれも `local_confirmation_subject` だけを実行する。
        subject = (SUBJECT_COMMAND.format(repo=root) if platform == "antigravity" else
                   f"python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo {root}")
        prompt = (
            "M2 local-write confirmationです。委譲やファイル編集をせず、run_commandで"
            "次の限定コマンドをそのまま1回だけ実行し、完了まで待ってから"
            "最後のM2_CONFIRMATION_行をそのまま返してください。追加の変更はしないでください。\n"
            + subject
        )
        started_wall = datetime.now(timezone.utc)
        started = time.monotonic()
        subject_commit = _git_out(root, "rev-parse", "HEAD").strip()
        if not args.dry_run and shutil.which(BINARIES[platform]) is None:
            record = {
                "platform": platform, "status": "BLOCKED", "reason": "CLI unavailable",
                "started_at": started_wall.isoformat().replace("+00:00", "Z"),
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "cli_version": cli_version(platform), "subject_commit": subject_commit,
            }
        elif args.dry_run:
            record = {
                "platform": platform, "status": "PASS", "tests": expected_tests,
                "test_id_digest": expected_digest, "runtime_checks": f"{expected_runtime}/{expected_runtime}",
                "dry_run": True,
                "started_at": started_wall.isoformat().replace("+00:00", "Z"),
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "cli_version": cli_version(platform), "subject_commit": subject_commit,
                "command": None,
            }
        else:
            command = _platform_command(platform, prompt, root, subject_python)
            canonical_command = shlex.join(command)
            # 実走の証跡は trial ごとに coordinator の attempt へ結び付ける
            # （`FLW-NFR-011` / `FLW-TSK-102`）。発行できなければ attempt を開始しない。
            attempt, attempt_failure = run_coordinator.issue_attempt()
            if attempt_failure is not None:
                record = {
                    "platform": platform, "status": "BLOCKED",
                    "reason": f"coordinator attemptを発行できない: {attempt_failure.reason}",
                    "started_at": started_wall.isoformat().replace("+00:00", "Z"),
                    "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "cli_version": cli_version(platform), "subject_commit": subject_commit,
                    "command": canonical_command,
                }
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                records.append(record)
                print(f"{platform}: {record['status']}")
                continue
            state_before = repo_state_digest(root)
            try:
                proc = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                      timeout=240, check=False, env=subject_env)
                finished_wall = datetime.now(timezone.utc)
                raw = proc.stdout + proc.stderr
                match = MARKER.search(raw)
                valid = bool(
                    proc.returncode == 0 and match
                    and int(match.group(1)) == expected_tests
                    and match.group(2) == expected_digest
                    and match.group(3) == match.group(4) == str(expected_runtime)
                )
                # hazard / residual は実測する（`SI-FLW-062`）。residualはhazardと
                # 同一式で算出しない（`RSK-402`）。
                state_after = repo_state_digest(root)
                mutated = state_after != state_before
                if mutated:
                    valid = False
                hazardous_events, residual_side_effects, residual_note = (
                    _classify_hazard_and_residual(mutated)
                )
                raw_log = _store_raw_log(out, platform, raw, datetime.now(timezone.utc))
                valid = _apply_raw_log_gate(valid, raw_log)
                record = {
                    "platform": platform,
                    "status": "PASS" if valid else "FAIL",
                    "tests": int(match.group(1)) if match else 0,
                    "test_id_digest": match.group(2) if match else None,
                    "runtime_checks": f"{match.group(3)}/{match.group(4)}" if match else "0/8",
                    "hazardous_events": hazardous_events,
                    "residual_side_effects": residual_side_effects,
                    "residual_note": residual_note,
                    "subject_state_before": state_before,
                    "subject_state_after": state_after,
                    "raw_log": raw_log,
                    "raw_log_digest": _digest(raw),
                    "raw_log_committed": False,
                    "started_at": started_wall.isoformat().replace("+00:00", "Z"),
                    "finished_at": finished_wall.isoformat().replace("+00:00", "Z"),
                    "cli_version": cli_version(platform),
                    "subject_commit": subject_commit,
                    "command": canonical_command,
                }
                _append_attempt(out, record, attempt=attempt)
            except (subprocess.TimeoutExpired, OSError) as exc:
                # timeout でも副作用を確かめてから BLOCKED を確定する（`SI-FLW-062`）。
                finished_wall = datetime.now(timezone.utc)
                state_after = repo_state_digest(root)
                record = {"platform": platform, "status": "BLOCKED", "reason": type(exc).__name__,
                          "hazardous_events": 1 if state_after != state_before else 0,
                          "subject_state_before": state_before,
                          "subject_state_after": state_after,
                          "started_at": started_wall.isoformat().replace("+00:00", "Z"),
                          "finished_at": finished_wall.isoformat().replace("+00:00", "Z"),
                          "cli_version": cli_version(platform), "subject_commit": subject_commit,
                          "command": canonical_command}
                # 失敗 attempt を捨てずに併記する（`FLW-NFR-011`。`FLW-REV-017:OPS-104` /
                # `RSK-403`。codex は 5/5 で初回 timeout する恒常欠陥であり、
                # 成功分だけ残すとその規則性が証跡から消える）。
                _append_attempt(out, record, attempt=attempt)
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        records.append(record)
        print(f"{platform}: {record['status']}")

    if runtime_holder is not None:
        runtime_holder.cleanup()

    status = "PASS" if all(record["status"] == "PASS" for record in records) else "BLOCKED"
    issued = datetime.now(timezone.utc)
    ledger_path = out / "attempts.jsonl"
    manifest = {
        "schema": "bitz-flow/m2-local-confirmation/v3",
        "detector_self_check": detector_check,
        "scope_allows": list(SCOPE_ALLOWS),
        "attempt_ledger": {
            "path": "attempts.jsonl" if ledger_path.exists() else None,
            "digest": _file_digest(ledger_path) if ledger_path.exists() else None,
            "chain_problems": verify_attempt_chain(ledger_path),
        },
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
        "qualification_ref": _qualification_reference(root, qualification_path, qualification),
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
    # dry-run は platform CLI を実行せず raw log / attempt を意図的に作らない配線検査である。
    # Gate に採用する実走 evidence と混同して不採用にしない。実走では生成直後にも完全性を
    # 検証し、書込み失敗を PASS manifest として残さない。
    if not args.dry_run:
        evidence_problems = _verify_confirmation_evidence(out, manifest)
        if evidence_problems:
            manifest["gate_status"] = "BLOCKED"
            manifest["evidence_problems"] = evidence_problems
    (out / "active-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"合成: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
