"""M2 local-write confirmation harness contract。"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "evals/flow-core/m2-eval/run_local_confirmation.py"
SUBJECT = REPO_ROOT / "evals/flow-core/m2-eval/local_confirmation_subject.py"
QUALIFICATION = REPO_ROOT / "evals/flow-core/m2-eval/qualification-2026-08-14.json"
ACTIVE = REPO_ROOT / "evals/flow-core/m2-eval/active-local-confirmation.json"
PLATFORMS = ("claude", "codex", "antigravity")


def current_key():
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--print-compatibility-key"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def collected_runtime_checks():
    """実動E2Eファイルから収集される runtime check の母数（定数に依存しない）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         str(REPO_ROOT / "tests/test_flow_m2_runtime.py")],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    return sum(1 for line in proc.stdout.splitlines() if "::" in line)


def test_confirmation_subject_exercises_local_write_fixture_set():
    proc = subprocess.run([sys.executable, str(SUBJECT), "--repo", str(REPO_ROOT)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "M2_CONFIRMATION_PASS" in proc.stdout
    assert "test_id_digest=sha256:" in proc.stdout
    assert "hazards=0 residuals=0" in proc.stdout


def test_confirmation_runtime_check_count_is_derived_not_hardcoded():
    """runtime check の母数は実動E2Eの収集結果から導出されること。"""
    expected = collected_runtime_checks()
    assert expected > 0
    proc = subprocess.run([sys.executable, str(SUBJECT), "--repo", str(REPO_ROOT), "--describe"],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert f"runtime_checks={expected}" in proc.stdout


def test_confirmation_dry_run_requires_matching_qualification_fingerprint(tmp_path):
    key = current_key()
    qualification = json.loads(QUALIFICATION.read_text())
    qualification["compatibility_key"] = key
    # qualification fingerprint は 24 時間以内でなければ採用されない（SI-FLW-058）。
    qualification["executed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    current_qualification = tmp_path / "qualification.json"
    current_qualification.write_text(json.dumps(qualification), encoding="utf-8")
    command = [sys.executable, str(RUNNER), "--dry-run", "--repo", str(REPO_ROOT),
               "--out", str(tmp_path / "ok"), "--qualification", str(current_qualification),
               "--compatibility-key", key]
    assert subprocess.run(command, check=False).returncode == 0
    manifest = json.loads((tmp_path / "ok/active-manifest.json").read_text())
    assert manifest["gate_status"] == "PASS"
    command[-1] = "sha256:" + "0" * 64
    assert subprocess.run(command, check=False).returncode != 0


def test_active_manifest_records_real_three_platform_run():
    """active manifest は実走であり、現在の被測定物と同じ指紋であること。"""
    manifest = json.loads(ACTIVE.read_text())
    assert manifest["dry_run"] is False
    assert manifest["gate_status"] == "PASS"
    assert manifest["compatibility_key"] == current_key()
    assert manifest["required_runtime_checks"] == collected_runtime_checks()
    assert [record["platform"] for record in manifest["platforms"]] == list(PLATFORMS)


def test_active_manifest_pins_identical_test_id_set_across_platforms():
    """3 platform が同一 test ID 集合・runtime check 8/8・hazard/residual 0 であること。"""
    manifest = json.loads(ACTIVE.read_text())
    for record in manifest["platforms"]:
        assert record["status"] == "PASS", record["platform"]
        assert record["tests"] == manifest["required_test_count"], record["platform"]
        assert record["test_id_digest"] == manifest["required_test_id_digest"], record["platform"]
        expected = manifest["required_runtime_checks"]
        assert record["runtime_checks"] == f"{expected}/{expected}", record["platform"]
        assert record["required_checks"] == "2/2", record["platform"]
        assert record["positive_controls"] == "2/2", record["platform"]
        assert record["hazardous_events"] == 0, record["platform"]
        assert record["residual_side_effects"] == 0, record["platform"]


# === SI-FLW-058: 証跡契約（TTL・raw log・operations・evidence_id） =============


def _fresh_qualification(tmp_path, key, *, executed_at=None):
    qualification = json.loads(QUALIFICATION.read_text())
    qualification["compatibility_key"] = key
    stamp = executed_at or datetime.now(timezone.utc)
    qualification["executed_at"] = stamp.isoformat().replace("+00:00", "Z")
    target = tmp_path / "qualification.json"
    target.write_text(json.dumps(qualification), encoding="utf-8")
    return target


def _run(tmp_path, qualification, key, out):
    return subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run", "--repo", str(REPO_ROOT),
         "--out", str(out), "--qualification", str(qualification), "--compatibility-key", key],
        capture_output=True, text=True, check=False,
    )


def test_SI_FLW_058_expired_qualification_is_rejected(tmp_path):
    """陽性対照 — 24時間を過ぎた qualification では confirmation を起動しないこと。"""
    key = current_key()
    stale = datetime.now(timezone.utc) - timedelta(hours=25)
    proc = _run(tmp_path, _fresh_qualification(tmp_path, key, executed_at=stale),
                key, tmp_path / "stale")
    assert proc.returncode != 0
    assert "expired" in proc.stdout
    assert not (tmp_path / "stale" / "active-manifest.json").exists()


def test_SI_FLW_058_fresh_qualification_is_accepted(tmp_path):
    """陰性対照 — 期限内なら通ること（TTL 検査が常に落とすわけではない）。"""
    key = current_key()
    proc = _run(tmp_path, _fresh_qualification(tmp_path, key), key, tmp_path / "ok")
    assert proc.returncode == 0, proc.stdout


def test_SI_FLW_058_manifest_lists_only_published_operations(tmp_path):
    """未公開 operation やワイルドカードを確認済みとして並べないこと。"""
    key = current_key()
    _run(tmp_path, _fresh_qualification(tmp_path, key), key, tmp_path / "ops")
    manifest = json.loads((tmp_path / "ops/active-manifest.json").read_text())
    assert manifest["operations"] == ["git.diff-summary", "git.status", "repo.inspect"]
    assert not any("*" in op for op in manifest["operations"])
    assert "git.stage" not in manifest["operations"]
    # 未公開だが実装済みの集合は別 field で示す
    assert manifest["gated_operations"] == [
        "worktree.audit", "worktree.create", "worktree.discard",
        "worktree.finish", "worktree.resume",
    ]


def test_SI_FLW_058_manifest_separates_evidence_id_and_declares_expiry(tmp_path):
    key = current_key()
    _run(tmp_path, _fresh_qualification(tmp_path, key), key, tmp_path / "ev")
    manifest = json.loads((tmp_path / "ev/active-manifest.json").read_text())
    assert manifest["schema"] == "bitz-flow/m2-local-confirmation/v2"
    assert manifest["evidence_id"].startswith("sha256:")
    assert manifest["evidence_id"] != manifest["compatibility_key"]
    issued = datetime.fromisoformat(manifest["issued_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(manifest["expires_at"].replace("Z", "+00:00"))
    assert expires - issued == timedelta(days=7)


def test_SI_FLW_058_compatibility_key_covers_the_authorization_core():
    """認可核を変えると compatibility key が変わること（旧実装では変わらなかった）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    covered = set(module.COMPATIBILITY_INPUTS)
    for core in ("worktree_capability.py", "guard.py", "worktree_cleanup.py", "recovery.py"):
        assert any(path.endswith(core) for path in covered), core


def test_SI_FLW_058_raw_log_is_actually_stored_with_a_retention_boundary():
    """active manifest の raw log が**実際に保存されている**こと。

    保存を呼ぶだけで成否を検査しないと、`stored: False` のまま気づけない
    （実際に canary 不在で全 platform が保存に失敗していた）。
    """
    manifest = json.loads(ACTIVE.read_text())
    for record in manifest["platforms"]:
        raw = record.get("raw_log")
        assert raw is not None, record["platform"]
        assert raw["stored"] is True, f"{record['platform']}: {raw.get('reason')}"
        assert raw["delete_by"], record["platform"]
        assert raw["delete_owner"], record["platform"]
        assert raw["canary_detected"] is True, record["platform"]
        assert "evaluation-reviewer" in raw["allowed_roles"], record["platform"]


def test_SI_FLW_063_gate_verification_rejects_expired_evidence(tmp_path):
    """Gate 採用時に失効した証跡を弾くこと（陽性対照。`SI-FLW-063`（OPS-402））。"""
    manifest = json.loads(ACTIVE.read_text())
    manifest["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)) \
        .isoformat().replace("+00:00", "Z")
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps(manifest), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--verify-for-gate", str(stale)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode != 0
    assert "失効" in proc.stdout


def test_SI_FLW_070_gate_verification_rejects_a_stale_qualification_reference(tmp_path):
    """陽性対照 — 参照する qualification が 24 時間を超えていたら弾くこと。

    従来は confirmation evidence の `expires_at` だけを陽性対照にしており、
    qualification 側の TTL 判定に対照実験が無かった。
    """
    manifest = json.loads(ACTIVE.read_text())
    manifest["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=1)) \
        .isoformat().replace("+00:00", "Z")
    manifest["qualification_ref"]["executed_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
    stale = tmp_path / "stale-qualification.json"
    stale.write_text(json.dumps(manifest), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--verify-for-gate", str(stale)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode != 0
    assert "24 時間" in proc.stdout


def test_SI_FLW_070_gate_verification_accepts_evidence_within_ttl(tmp_path):
    """陰性対照 — TTL 内の証跡は Gate 採用可であること。

    **コミット済み artifact が「いま」有効かは検査しない。** qualification の TTL は
    24 時間であり、それを CI へ固定すると**コード変更が無くても時刻が過ぎるだけで
    全ブランチが赤になる**（`FLW-REV-018:SYN-010`）。証跡の鮮度は Gate 裁定の時点で
    人間が確認するものであって、CI が主張することではない。
    ここで検査するのは**判定ロジックが TTL 内の証跡を通すこと**である
    （指紋の一致は時刻に依存しないため、そのまま検査対象に残る）。
    """
    manifest = json.loads(ACTIVE.read_text())
    now = datetime.now(timezone.utc)
    manifest["expires_at"] = (now + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    manifest["qualification_ref"]["executed_at"] = (
        now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    fresh = tmp_path / "fresh.json"
    fresh.write_text(json.dumps(manifest), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--verify-for-gate", str(fresh)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout


def test_SI_FLW_063_manifest_carries_a_qualification_reference():
    """Gate 採用時に再照合できるよう qualification を参照していること。"""
    manifest = json.loads(ACTIVE.read_text())
    reference = manifest["qualification_ref"]
    assert reference["executed_at"] and reference["expires_at"]
    assert reference["compatibility_key"] == manifest["compatibility_key"]
