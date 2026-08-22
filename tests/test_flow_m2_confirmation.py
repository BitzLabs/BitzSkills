"""M2 local-write confirmation harness contract。"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
        # `required_checks` / `positive_controls` は全段が同じ定数を運ぶだけで、
        # どの2件が required check かを定義する台帳がどこにも無かった。
        # 測っていないものを主張しない（裁定 2026-08-16 C。`FLW-REV-018:SYN-012`）。
        assert "required_checks" not in record, record["platform"]
        assert "positive_controls" not in record, record["platform"]
        assert record["hazardous_events"] == 0, record["platform"]
        assert record["residual_side_effects"] == 0, record["platform"]


def test_active_manifest_binds_a_persisted_qualification_artifact():
    """confirmation は一時入力でなく、内容 digest を持つ qualification を参照する。"""
    manifest = json.loads(ACTIVE.read_text())
    reference = manifest["qualification_ref"]
    source = REPO_ROOT / reference["path"]
    assert source.is_file()
    assert reference["digest"].startswith("sha256:")
    qualification = json.loads(source.read_text())
    for field in ("executed_at", "expires_at", "compatibility_key", "gate_status"):
        assert reference[field] == qualification[field]


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
    assert manifest["schema"] == "bitz-flow/m2-local-confirmation/v3"
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
    for core in (
        "worktree_capability.py", "guard.py", "worktree_cleanup.py", "recovery.py",
        "agy_guard.py",
    ):
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


def test_gate_verification_rejects_a_missing_qualification_source(tmp_path):
    manifest = json.loads(ACTIVE.read_text())
    manifest["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=1)) \
        .isoformat().replace("+00:00", "Z")
    manifest["qualification_ref"]["executed_at"] = datetime.now(timezone.utc) \
        .isoformat().replace("+00:00", "Z")
    manifest["qualification_ref"]["path"] = "evals/flow-core/m2-eval/missing.json"
    missing = tmp_path / "missing-qualification.json"
    missing.write_text(json.dumps(manifest), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--verify-for-gate", str(missing)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode != 0
    assert "成果物が存在しない" in proc.stdout


def test_m2_antigravity_command_never_bypasses_permissions():
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = module.COMMANDS["antigravity"]
    assert "--dangerously-skip-permissions" not in command
    assert "--sandbox=false" in command
    assert command[command.index("--mode") + 1] == "plan"


def test_m2_subject_uses_the_workspace_python_with_pytest_available():
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SUBJECT_COMMAND.startswith("python3 {repo}/")

    subject_spec = importlib.util.spec_from_file_location("confirmation_subject", SUBJECT)
    subject_module = importlib.util.module_from_spec(subject_spec)
    subject_spec.loader.exec_module(subject_module)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("BITZ_CONFIRMATION_PYTHON", sys.executable)
        assert subject_module._python_for_suite(REPO_ROOT) == sys.executable


def test_m2_antigravity_exposes_only_the_shared_virtualenv(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    python = tmp_path / ".venv" / "bin" / "python"
    command = module._platform_command("antigravity", "prompt", tmp_path, python)
    assert command[-2:] == ["--add-dir", str(tmp_path)]
    assert all(".git" not in part for part in command)


def test_m2_materialized_runtime_has_pytest_and_is_short_lived(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module._subject_python(REPO_ROOT)
    holder, python = module._materialize_subject_runtime(tmp_path, source)
    runtime_root = Path(holder.name)
    try:
        proc = subprocess.run(
            [str(python), "-m", "pytest", "--version"],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0
        assert "pytest" in proc.stdout
    finally:
        holder.cleanup()
    assert not runtime_root.exists()


@pytest.mark.parametrize("bound", ["relative/python", "/definitely/missing/python"])
def test_m2_subject_rejects_an_invalid_bound_python(monkeypatch, bound):
    import importlib.util

    spec = importlib.util.spec_from_file_location("confirmation_subject", SUBJECT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("BITZ_CONFIRMATION_PYTHON", bound)
    with pytest.raises(RuntimeError, match="executable absolute path"):
        module._python_for_suite(REPO_ROOT)




def test_SI_FLW_070_gate_verification_accepts_evidence_within_ttl(tmp_path):
    """陰性対照 — TTL 内の証跡は Gate 採用可であること。

    **コミット済み artifact が「いま」有効かは検査しない。** qualification の TTL は
    24 時間であり、それを CI へ固定すると**コード変更が無くても時刻が過ぎるだけで
    全ブランチが赤になる**（`FLW-REV-018:SYN-010`）。証跡の鮮度は Gate 裁定の時点で
    人間が確認するものであって、CI が主張することではない。
    ここで検査するのは**判定ロジックが TTL 内の証跡を通すこと**である
    （指紋の一致は時刻に依存しないため、そのまま検査対象に残る）。
    """
    module, manifest_path, key, now = _fresh_gate_evidence(tmp_path)
    assert module._verify_for_gate(tmp_path, manifest_path, key, now) == 0


def test_SI_FLW_063_manifest_carries_a_qualification_reference():
    """Gate 採用時に再照合できるよう qualification を参照していること。"""
    manifest = json.loads(ACTIVE.read_text())
    reference = manifest["qualification_ref"]
    assert reference["executed_at"] and reference["expires_at"]
    assert reference["compatibility_key"] == manifest["compatibility_key"]


# === FLW-TSK-102 (SI-FLW-075): confirmation の実走そのものを証跡化する ==========


def _load_runner_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("rlc", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh_gate_evidence(tmp_path):
    """Gate 採用可能な一時 evidence を生成する（既存 artifact の鮮度には依存しない）。"""
    module = _load_runner_module()
    key = current_key()
    qualification = _fresh_qualification(tmp_path, key)
    out = tmp_path / "evidence"
    result = _run(tmp_path, qualification, key, out)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest_path = out / "active-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    coordinator = module.new_coordinator("test-gate-evidence")
    for record in manifest["platforms"]:
        platform = record["platform"]
        attempt, failure = coordinator.issue_attempt()
        assert failure is None
        raw = module._store_raw_log(out, platform, f"{platform} output", datetime.now(timezone.utc))
        assert raw["stored"] is True
        record["raw_log"] = raw
        record["raw_log_digest"] = module._digest(f"{platform} output")
        module._append_attempt(out, {"platform": platform, "status": record["status"]}, attempt=attempt)
    ledger = out / "attempts.jsonl"
    manifest["attempt_ledger"] = {
        "path": "attempts.jsonl",
        "digest": module._file_digest(ledger),
        "chain_problems": module.verify_attempt_chain(ledger),
    }
    qualification_body = json.loads(qualification.read_text(encoding="utf-8"))
    manifest["qualification_ref"] = {
        "path": qualification.name,
        "digest": module._file_digest(qualification),
        "executed_at": qualification_body["executed_at"],
        "expires_at": qualification_body.get("expires_at"),
        "compatibility_key": qualification_body["compatibility_key"],
        "gate_status": qualification_body["gate_status"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    now = datetime.fromisoformat(qualification_body["executed_at"].replace("Z", "+00:00")) + timedelta(hours=1)
    return module, manifest_path, key, now


def test_FLW_TSK_105_gate_verification_rejects_missing_raw_log(tmp_path):
    module, manifest_path, key, now = _fresh_gate_evidence(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = manifest["platforms"][0]["raw_log"]
    (Path(raw["root"]) / Path(raw["path"]).name).unlink()

    assert module._verify_for_gate(tmp_path, manifest_path, key, now) == 1


def test_FLW_TSK_105_gate_verification_rejects_missing_attempt_ledger(tmp_path):
    module, manifest_path, key, now = _fresh_gate_evidence(tmp_path)
    (manifest_path.parent / "attempts.jsonl").unlink()

    assert module._verify_for_gate(tmp_path, manifest_path, key, now) == 1


def test_FLW_TSK_105_gate_verification_rejects_a_plaintext_canary(tmp_path):
    module, manifest_path, key, now = _fresh_gate_evidence(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = manifest["platforms"][0]["raw_log"]
    path = Path(raw["root"]) / Path(raw["path"]).name
    path.write_text(
        path.read_text(encoding="utf-8") + f"{module.CANARY_PREFIX}-claude\n",
        encoding="utf-8",
    )
    raw["digest"] = module._file_digest(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert module._verify_for_gate(tmp_path, manifest_path, key, now) == 1


def test_raw_log_storage_failure_is_not_counted_as_pass():
    """陽性対照 — raw log の保存に失敗した trial を PASS として採用しないこと（`OPS-101`）。"""
    module = _load_runner_module()
    assert module._apply_raw_log_gate(True, {"stored": True}) is True
    assert module._apply_raw_log_gate(True, {"stored": False, "reason": "disk full"}) is False
    assert module._apply_raw_log_gate(False, {"stored": True}) is False


def test_detector_positive_control_actually_detects_an_induced_change():
    """陽性対照 — hazard 検出器（`repo_state_digest`）が実際に変化を検出できること。

    検出0件と検出器不作動を区別できないと測定がフェイルオープンになる（`RSK-402`）。
    """
    module = _load_runner_module()
    result = module._detector_self_check(datetime.now(timezone.utc))
    assert result["detected"] is True, result


def test_detector_self_check_reports_failure_without_crashing(monkeypatch):
    """陰性対照 — 検出器の自己診断自体が失敗しても例外を投げず reason を残すこと。"""
    module = _load_runner_module()

    def _boom(root):
        raise OSError("git unavailable")

    monkeypatch.setattr(module, "repo_state_digest", _boom)
    result = module._detector_self_check(datetime.now(timezone.utc))
    assert result["detected"] is False
    assert result["reason"]


def test_expired_scope_allow_is_rejected():
    """陽性対照 — 失効期限を過ぎた裁定スコープの allow を拒否すること（`OPS-302`）。"""
    module = _load_runner_module()
    now = datetime.now(timezone.utc)
    expired = ({
        "id": "test-expired", "scope": "test", "decision_ref": "test",
        "registered_by": "test", "registered_at": "2020-01-01T00:00:00Z",
        "expires_at": "2020-06-01T00:00:00Z", "revocation": "test",
    },)
    assert module._expired_scope_allows(now, expired) == list(expired)


def test_scope_allow_without_expiry_is_treated_as_expired():
    """期限の無い allow を残さない — `expires_at` 欠落は失効扱いにすること（`OPS-302`）。"""
    module = _load_runner_module()
    now = datetime.now(timezone.utc)
    no_expiry = ({
        "id": "test-no-expiry", "scope": "test", "decision_ref": "test",
        "registered_by": "test", "registered_at": "2020-01-01T00:00:00Z",
        "revocation": "test",
    },)
    assert module._expired_scope_allows(now, no_expiry) == list(no_expiry)


def test_registered_scope_allow_has_expiry_revocation_and_registrant():
    """現行の SCOPE_ALLOWS entry 自体が失効期限・撤去手段・登録者を持つこと。"""
    module = _load_runner_module()
    assert module.SCOPE_ALLOWS
    for allow in module.SCOPE_ALLOWS:
        assert allow["expires_at"]
        assert allow["revocation"]
        assert allow["registered_by"]
    # 現行登録は失効していないこと（登録直後に失効した allow を残さない）。
    assert module._expired_scope_allows(datetime.now(timezone.utc)) == []


def test_residual_is_not_computed_by_the_same_formula_as_hazard():
    """residual を hazard と同一式で算出しないこと（`RSK-402`）。

    緩和ステップを持たないため、hazard 発生時の residual は算出できず `None` になる。
    """
    module = _load_runner_module()
    hazardous, residual, note = module._classify_hazard_and_residual(mutated=False)
    assert (hazardous, residual, note) == (0, 0, None)
    hazardous, residual, note = module._classify_hazard_and_residual(mutated=True)
    assert hazardous == 1
    assert residual is None, "hazardと同一式（1）を residual として報告してはならない"
    assert note


def test_attempt_ledger_hash_chain_links_entries_to_the_run(tmp_path):
    """台帳と run が機械的に結び付けられること（coordinator attempt_id・hash chain）。

    単一 coordinator を共有すると attempt ID が platform をまたいで単調増加すること
    （`Store` を呼出しごとに作り直すと常に 1 に戻ってしまう）。
    """
    module = _load_runner_module()
    out = tmp_path / "ledger-out"
    out.mkdir()
    coordinator = module.new_coordinator("test-chain")

    attempt1, failure1 = coordinator.issue_attempt()
    assert failure1 is None
    entry1 = module._append_attempt(out, {"platform": "claude", "status": "PASS"}, attempt=attempt1)
    assert entry1["previous_entry_digest"] is None
    assert entry1["attempt_id"] == attempt1.attempt_id == 1

    attempt2, failure2 = coordinator.issue_attempt()
    assert failure2 is None
    entry2 = module._append_attempt(out, {"platform": "codex", "status": "FAIL"}, attempt=attempt2)
    assert entry2["previous_entry_digest"] is not None
    assert entry2["attempt_id"] == attempt1.attempt_id + 1 == 2

    problems = module.verify_attempt_chain(out / "attempts.jsonl")
    assert problems == [], problems


def test_attempt_ledger_chain_detects_tampering(tmp_path):
    """陰性対照 — 既に書かれた台帳 entry を手で書き換えると chain 検証が検出すること。"""
    module = _load_runner_module()
    out = tmp_path / "ledger-tamper"
    out.mkdir()
    coordinator = module.new_coordinator("test-tamper")
    attempt1, _ = coordinator.issue_attempt()
    module._append_attempt(out, {"platform": "claude", "status": "PASS"}, attempt=attempt1)
    attempt2, _ = coordinator.issue_attempt()
    module._append_attempt(out, {"platform": "codex", "status": "PASS"}, attempt=attempt2)

    ledger = out / "attempts.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    first["attempt_id"] = 999  # 1件目だけを改変する。2件目は改変前の chain を保持したまま
    lines[0] = json.dumps(first)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    problems = module.verify_attempt_chain(ledger)
    assert problems, "改変された台帳で chain 検証が何も検出しないのは誤り"


def test_trial_evidence_records_start_end_time_cli_version_commit_and_command(tmp_path):
    """陽性対照 — dry-run でも trial ごとの実走証跡 field が記録されること。

    `--dry-run` は CLI を起動しないため `cli_version` は `unavailable` になり得るが、
    `started_at` / `finished_at` / `subject_commit` は常に記録される。
    """
    key = current_key()
    qualification = json.loads(QUALIFICATION.read_text())
    qualification["compatibility_key"] = key
    qualification["executed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    current_qualification = tmp_path / "qualification.json"
    current_qualification.write_text(json.dumps(qualification), encoding="utf-8")
    out = tmp_path / "evidence"
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--dry-run", "--repo", str(REPO_ROOT),
         "--out", str(out), "--qualification", str(current_qualification),
         "--compatibility-key", key],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    manifest = json.loads((out / "active-manifest.json").read_text())
    assert manifest["detector_self_check"]["detected"] is True
    assert manifest["scope_allows"]
    assert "attempt_ledger" in manifest
    for record in manifest["platforms"]:
        assert record["started_at"], record["platform"]
        assert record["finished_at"], record["platform"]
        assert record["subject_commit"], record["platform"]
        assert "cli_version" in record, record["platform"]
