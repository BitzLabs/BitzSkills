"""raw log guard（FLW-NFR-011 / FLW-FR-013）の単体テストと負の対照。

負の対照: group/other から読める permission、redaction を通らない生 log、canary 未検出、
30 日超の保持設定、削除証跡なしの削除、期限超過 log の放置、未許可 role の読み取り。
"""

import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))

import raw_log_guard as G  # noqa: E402

T0 = datetime(2026, 8, 11, tzinfo=timezone.utc)
CANARY = "CANARY-9f3a7c21"
SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123"
LOG_TEXT = f"start {CANARY}\ntoken {SECRET}\npath /home/someone/repo\nok done"


@pytest.fixture
def guard(tmp_path):
    return G.RawLogGuard(tmp_path / "raw", owner="owner-1")


def _store(guard, now=T0):
    log, failure = guard.store("trial.log", LOG_TEXT, canaries=[CANARY], now=now)
    assert failure is None, failure
    return log


# --- 保存と redaction ----------------------------------------------------------


def test_store_redacts_secrets_but_keeps_structure(guard):
    log = _store(guard)
    text = log.path.read_text(encoding="utf-8")
    assert SECRET not in text
    assert "/home/someone/repo" not in text
    assert "REDACTED" in text
    assert text.splitlines()[-1] == "ok done", "無害な行は残す"


def test_redaction_kinds_are_visible(guard):
    log = _store(guard)
    assert G.S.KIND_TOKEN in log.redactions
    assert G.S.KIND_ABSOLUTE_PATH in log.redactions


def test_no_secret_remains_after_redaction(guard):
    log = _store(guard)
    assert guard.check_no_secret_remains(log, [SECRET, "/home/someone/repo"]) is None


def test_digest_is_over_redacted_content(guard):
    log = _store(guard)
    assert log.digest.startswith("sha256:")
    assert log.digest == G.R.sha256_of(log.path.read_text(encoding="utf-8").encode("utf-8"))


# --- canary --------------------------------------------------------------------


def test_canary_undetected_blocks_storage(guard):
    """canary が無い log は「秘密値が無い」ではなく「観測できていない」と扱う。"""
    log, failure = guard.store("x.log", "ordinary lines only", canaries=[CANARY], now=T0)
    assert log is None
    assert failure.code == G.CODE_BLOCKED
    assert "安全とは扱わない" in failure.reason


def test_storing_without_canary_is_rejected(guard):
    log, failure = guard.store("x.log", LOG_TEXT, canaries=[], now=T0)
    assert log is None and failure.code == G.CODE_BLOCKED


def test_canary_is_detected_before_redaction(guard):
    """redaction 後の本文から探すと必ず未検出になるため、原文に対して検出する。"""
    log = _store(guard)
    assert log.canary_detected is True


# --- owner-only 境界 -----------------------------------------------------------


def test_permissions_are_owner_only(guard):
    log = _store(guard)
    assert guard.check_permissions(log) is None
    assert not (log.path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def test_group_readable_permission_is_detected(guard):
    log = _store(guard)
    log.path.chmod(0o640)
    failure = guard.check_permissions(log)
    assert failure.code == G.CODE_BLOCKED


def test_world_readable_directory_is_detected(guard, tmp_path):
    log = _store(guard)
    (tmp_path / "raw").chmod(0o755)
    assert guard.check_permissions(log) is not None


@pytest.mark.parametrize("role", G.ALLOWED_ROLES)
def test_allowed_roles_can_read(guard, role):
    log = _store(guard)
    text, failure = guard.read(log, role=role)
    assert failure is None and text


@pytest.mark.parametrize("role", ["ci", "public", "implementation-owner", ""])
def test_other_roles_cannot_read(guard, role):
    log = _store(guard)
    text, failure = guard.read(log, role=role)
    assert text is None and failure.code == G.CODE_BLOCKED


# --- 保持期限 ------------------------------------------------------------------


def test_retention_defaults_to_30_days(guard):
    log = _store(guard)
    assert log.delete_by == T0 + timedelta(days=G.MAX_RETENTION_DAYS)


def test_retention_over_30_days_is_rejected(tmp_path):
    guard = G.RawLogGuard(tmp_path / "raw", owner="o", retention_days=31)
    log, failure = guard.store("x.log", LOG_TEXT, canaries=[CANARY], now=T0)
    assert log is None and failure.code == G.CODE_INVALID_INPUT


def test_expired_log_left_behind_is_detected(guard):
    log = _store(guard)
    assert guard.check_expiry(log, now=T0 + timedelta(days=29)) is None
    failure = guard.check_expiry(log, now=T0 + timedelta(days=30))
    assert failure.code == G.CODE_BLOCKED


# --- 削除と証跡 ----------------------------------------------------------------


def test_deletion_records_a_receipt(guard):
    log = _store(guard)
    receipt, failure = guard.delete(log, deleted_by="coordinator-operator", now=T0)
    assert failure is None
    assert receipt.target_digest == log.digest
    assert receipt.deleted_by == "coordinator-operator"
    assert not log.path.exists()
    assert guard.receipts() == [receipt.as_dict()]


def test_deletion_without_owner_is_rejected(guard):
    log = _store(guard)
    receipt, failure = guard.delete(log, deleted_by="", now=T0)
    assert receipt is None and failure.code == G.CODE_BLOCKED
    assert log.path.exists(), "証跡が無いなら削除もしない"


# --- manifest への受け渡し -----------------------------------------------------


def test_retention_block_matches_manifest_contract(guard):
    log = _store(guard)
    block = guard.retention_block(log)
    expected_keys = {
        "storage_boundary", "allowed_roles", "redaction_version", "max_retention_days",
        "delete_by", "delete_owner", "canary_detected", "deletion_receipts",
    }
    assert set(block) == expected_keys
    assert block["allowed_roles"] == list(G.ALLOWED_ROLES)
    assert block["max_retention_days"] <= 30
    assert block["canary_detected"] is True


def test_allowed_roles_are_exactly_two():
    assert G.ALLOWED_ROLES == ("owner", "evaluation-reviewer")
