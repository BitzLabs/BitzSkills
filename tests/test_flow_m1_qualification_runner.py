"""3 platform qualification runner（FLW-NFR-011）— dry-run での配線検査。

実 CLI の起動は課金と時間を伴うため、CI ではここ（`--dry-run`）だけを回す。
実走は M1-6 の成果物タスクで人手により1回行う。

中心命題: **実行できなかったことを「合格」と読み替えない**。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
M1_EVAL = REPO_ROOT / "evals" / "flow-core" / "m1-eval"
RUNNER = M1_EVAL / "run_qualification.py"
sys.path.insert(0, str(M1_EVAL))
sys.path.insert(0, str(M1_EVAL / "fixtures"))
sys.path.insert(0, str(REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core" / "scripts"))

import qualification as Q  # noqa: E402
import run_qualification as RQ  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    return path


# --- 構成 ----------------------------------------------------------------------


def test_every_platform_has_a_command():
    assert set(RQ.CLI_COMMANDS) == set(Q.PLATFORMS)
    assert set(RQ.CLI_BINARY) == set(Q.PLATFORMS)


def test_every_trial_kind_has_a_spec():
    assert set(RQ.TRIAL_SPEC) == set(Q.TRIAL_KINDS)
    for spec in RQ.TRIAL_SPEC.values():
        assert spec["checks"] and spec["controls"], "必須 check と陽性対照を事前拘束する"
        assert spec["prompt"]


def test_command_substitutes_prompt_and_repo(tmp_path):
    for platform in Q.PLATFORMS:
        command = RQ.build_command(platform, prompt="PROMPT", repo=tmp_path)
        assert command[0] == RQ.CLI_BINARY[platform]
        assert "{prompt}" not in " ".join(command)
        assert "{repo}" not in " ".join(command)


def test_codex_command_receives_repo(tmp_path):
    command = RQ.build_command("codex", prompt="p", repo=tmp_path)
    assert str(tmp_path) in command


# --- dry-run -------------------------------------------------------------------


def test_dry_run_produces_three_trials_per_platform(repo, tmp_path):
    manifest = RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=True)
    assert len(manifest["trials"]) == 3
    assert {t["kind"] for t in manifest["trials"]} == set(Q.TRIAL_KINDS)


def test_dry_run_passes_for_every_platform(repo, tmp_path):
    for platform in Q.PLATFORMS:
        manifest = RQ.run_platform(platform, repo=repo, workdir=tmp_path / platform, dry_run=True)
        assert manifest["gate_status"] == Q.GATE_PASS, manifest["gate_reasons"]


def test_manifest_matches_the_contract(repo, tmp_path):
    schema = json.loads(
        (REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core" / "schemas"
         / "qualification-manifest-v1.schema.json").read_text(encoding="utf-8")
    )
    manifest = RQ.run_platform("codex", repo=repo, workdir=tmp_path / "w", dry_run=True)
    assert set(schema["required"]) <= set(manifest)
    assert set(manifest) <= set(schema["properties"])
    trial_required = set(schema["$defs"]["trial"]["required"])
    for trial in manifest["trials"]:
        assert trial_required <= set(trial)


def test_isolation_namespaces_are_distinct(repo, tmp_path):
    manifest = RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=True)
    boundaries = {t["sandbox_boundary"] for t in manifest["trials"]}
    assert len(boundaries) == 3, "trial ごとに独立した隔離を割り当てる"


def test_raw_log_is_guarded(repo, tmp_path):
    manifest = RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=True)
    for trial in manifest["trials"]:
        assert trial["raw_log_digest"].startswith("sha256:")
    assert manifest["retention"]["canary_detected"] is True
    assert manifest["retention"]["allowed_roles"] == ["owner", "evaluation-reviewer"]


# --- 実行できないことを合格と読み替えない ---------------------------------------


def test_missing_cli_is_blocked_not_passed(repo, tmp_path, monkeypatch):
    """実走時に CLI が無い platform を「合格」にしない。"""
    monkeypatch.setattr(RQ, "cli_available", lambda platform: False)
    manifest = RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=False)
    assert manifest["gate_status"] == Q.GATE_BLOCKED
    assert manifest["trials"] == []
    assert any("CLI が見つからない" in str(r) for r in manifest["gate_reasons"])


def test_dry_run_works_without_any_cli(repo, tmp_path, monkeypatch):
    """dry-run は配線検査なので CLI 不在でも成立する（CI には 3 platform の CLI が無い）。"""
    monkeypatch.setattr(RQ, "cli_available", lambda platform: False)
    monkeypatch.setattr(RQ, "cli_version", lambda platform: "unavailable")
    for platform in Q.PLATFORMS:
        manifest = RQ.run_platform(platform, repo=repo, workdir=tmp_path / platform, dry_run=True)
        assert manifest["gate_status"] == Q.GATE_PASS, manifest["gate_reasons"]
        assert len(manifest["trials"]) == 3


def test_dry_run_never_launches_a_trial(repo, tmp_path, monkeypatch):
    """dry-run で被験 CLI を起動しない（課金と時間を伴わない）。

    `cli_version` は `--version` の取得のために subprocess を使うことがあるため
    ここではスタブにし、**trial の起動**が起きないことだけを見る。
    """
    def _forbidden(*args, **kwargs):
        raise AssertionError("dry-run で trial の CLI を起動してはならない")

    monkeypatch.setattr(RQ, "cli_version", lambda platform: "stub")
    monkeypatch.setattr(RQ.subprocess, "run", _forbidden)
    manifest = RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=True)
    assert manifest["gate_status"] == Q.GATE_PASS
    assert len(manifest["trials"]) == 3


@pytest.fixture
def cli_present(monkeypatch):
    """CLI があることにする（CI には 3 platform の CLI が無い）。"""
    monkeypatch.setattr(RQ, "cli_available", lambda platform: True)
    monkeypatch.setattr(RQ, "cli_version", lambda platform: "stub 1.0")


def test_timeout_is_blocked(repo, tmp_path, monkeypatch, cli_present):
    def _boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(RQ.subprocess, "run", _boom)
    outcome, reason = RQ.run_trial(
        "claude", "Q-NORMAL", repo=repo, workdir=tmp_path / "w", dry_run=False, timeout=1
    )
    assert outcome is None and "timeout" in reason


def test_launch_failure_is_blocked(repo, tmp_path, monkeypatch, cli_present):
    monkeypatch.setattr(RQ.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    outcome, reason = RQ.run_trial(
        "codex", "Q-REJECT", repo=repo, workdir=tmp_path / "w", dry_run=False
    )
    assert outcome is None and "起動できない" in reason


def test_gate_decision_is_delegated_to_qualification(repo, tmp_path, monkeypatch):
    """判定ロジックを runner 側で再実装していない。"""
    called = {}

    original = Q.evaluate

    def _spy(outcomes, **kwargs):
        called["hit"] = True
        return original(outcomes, **kwargs)

    monkeypatch.setattr(Q, "evaluate", _spy)
    RQ.run_platform("claude", repo=repo, workdir=tmp_path / "w", dry_run=True)
    assert called.get("hit") is True


# --- CLI 契約 ------------------------------------------------------------------


def test_cli_rejects_unknown_arguments():
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--bogus"], capture_output=True, text=True
    )
    assert proc.returncode != 0
    assert "unrecognized arguments" in proc.stderr


def test_cli_dry_run_writes_artifacts(tmp_path, repo):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run", "--repo", str(repo), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["gate_status"] == Q.GATE_PASS
    assert summary["dry_run"] is True
    for platform in Q.PLATFORMS:
        assert (out / f"qualification-{platform}.json").exists()


def test_cli_can_target_a_single_platform(tmp_path, repo):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run", "--repo", str(repo),
         "--out", str(out), "--platform", "codex"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0, "platform が欠ければ合成は PASS にしない"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["platforms"] == ["codex"]
    assert any("antigravity" in r for r in summary["gate_reasons"])
