"""compatibility key v1 と失効規則（FLW-NFR-011）の単体テスト。

負の対照: 欠落 field、未知 field、短命状態が key を揺らすこと、evidence_id の混入、
共通入力の変更を単一 platform 失効で済ませてしまうこと。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))

import compatibility as C  # noqa: E402


def _inputs(**overrides):
    base = {
        "scoring_rule": "sha256:rule-1",
        "runner": "sha256:runner-1",
        "adapter": "sha256:adapter-claude-1",
        "oracle": "sha256:oracle-1",
        "fixture": "sha256:fixture-1",
        "prompt": "sha256:prompt-1",
        "skill": "sha256:skill-1",
        "result_schema": "bitz-flow/result/v1",
        "event_schema": "claude/event-contract/v1",
        "transitive_dependencies": ["git 2.43", "python 3.12"],
        "model_identity": "claude-opus-5@2026-08-01",
        "cli_version": "claude-code 1.0",
        "host_event_contract_version": "v1",
        "trial_assignment": {"Q-NORMAL": 1, "Q-REJECT": 1, "Q-CORRUPT": 1},
    }
    base.update(overrides)
    return base


# --- 閉集合 --------------------------------------------------------------------


def test_key_fields_are_the_closed_set():
    assert len(C.KEY_FIELDS) == 14
    assert C.COMMON_FIELDS | C.PLATFORM_FIELDS == set(C.KEY_FIELDS)
    assert not (C.COMMON_FIELDS & C.PLATFORM_FIELDS), "共通と platform 固有は排他"


def test_key_is_deterministic():
    a = C.build_key(_inputs())
    b = C.build_key(_inputs())
    assert a.usable and a.key == b.key
    assert a.key.startswith("sha256:")


def test_key_ignores_input_ordering():
    forward = _inputs()
    reversed_order = {k: forward[k] for k in reversed(list(forward))}
    assert C.build_key(forward).key == C.build_key(reversed_order).key


@pytest.mark.parametrize("field", C.KEY_FIELDS)
def test_changing_any_key_field_changes_the_key(field):
    before = C.build_key(_inputs()).key
    after = C.build_key(_inputs(**{field: "sha256:changed"})).key
    assert before != after, f"{field} の変更が key に反映されていない"


# --- 欠落・未知 field ----------------------------------------------------------


@pytest.mark.parametrize("field", C.KEY_FIELDS)
def test_missing_field_is_blocked(field):
    inputs = _inputs()
    del inputs[field]
    result = C.build_key(inputs)
    assert result.status == C.STATUS_BLOCKED
    assert result.key is None
    assert field in result.reasons[0]


def test_unknown_field_is_blocked():
    """「知らない field があるが他は同じだから互換」と判断しない。"""
    result = C.build_key(_inputs(mystery_setting="x"))
    assert result.status == C.STATUS_BLOCKED
    assert "未知 field" in result.reasons[0]


def test_blocked_inputs_make_comparison_blocked():
    incomplete = _inputs()
    del incomplete["oracle"]
    assert C.compare(_inputs(), incomplete).status == C.STATUS_BLOCKED
    assert C.compare(incomplete, _inputs()).status == C.STATUS_BLOCKED


# --- 短命状態 ------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(C.EPHEMERAL_FIELDS))
def test_ephemeral_state_does_not_change_the_key(field):
    """credential や rate-limit 残量で key が揺れると再利用が成立しない。"""
    baseline = C.build_key(_inputs()).key
    with_state = C.build_key(_inputs(**{field: "whatever"}))
    assert with_state.usable
    assert with_state.key == baseline


def test_dynamic_fingerprint_tracks_ephemeral_state():
    a = C.dynamic_fingerprint({"credential_class": "write-scoped", "rate_limit_remaining": 100})
    b = C.dynamic_fingerprint({"credential_class": "write-scoped", "rate_limit_remaining": 10})
    assert a != b


def test_dynamic_fingerprint_ignores_key_fields():
    a = C.dynamic_fingerprint({"credential_class": "none", "scoring_rule": "x"})
    b = C.dynamic_fingerprint({"credential_class": "none", "scoring_rule": "y"})
    assert a == b, "compatibility key の要素は fingerprint 側で見ない"


# --- evidence_id との分離 ------------------------------------------------------


def test_evidence_id_is_separate_from_the_key():
    key = C.build_key(_inputs()).key
    first = C.evidence_id(raw_log_digest="sha256:a", attempt_id=1, run_metadata={"host": "h1"})
    second = C.evidence_id(raw_log_digest="sha256:b", attempt_id=2, run_metadata={"host": "h2"})
    assert first != second, "run ごとに異なる"
    assert key != first and key != second


def test_same_conditions_different_runs_share_the_key():
    """同じ条件の別 run は key が同じで evidence_id が違う。"""
    assert C.build_key(_inputs()).key == C.build_key(_inputs()).key
    a = C.evidence_id(raw_log_digest="sha256:a", attempt_id=1, run_metadata={})
    b = C.evidence_id(raw_log_digest="sha256:a", attempt_id=2, run_metadata={})
    assert a != b


# --- 失効規則 ------------------------------------------------------------------


def test_no_change_invalidates_nothing():
    result = C.invalidation_for(_inputs(), _inputs(), platform="claude")
    assert result.scope == "none"
    assert result.changed_fields == ()


@pytest.mark.parametrize("field", sorted(C.COMMON_FIELDS))
def test_common_input_change_invalidates_all_platforms(field):
    result = C.invalidation_for(
        _inputs(), _inputs(**{field: "sha256:changed"}), platform="claude"
    )
    assert result.scope == "all-platforms"
    assert result.invalidates_everything is True
    assert field in result.changed_fields


@pytest.mark.parametrize("field", sorted(C.PLATFORM_FIELDS))
def test_platform_input_change_invalidates_only_that_platform(field):
    result = C.invalidation_for(
        _inputs(), _inputs(**{field: "changed"}), platform="codex"
    )
    assert result.scope == "single-platform"
    assert result.platforms == ("codex",)
    assert result.invalidates_everything is False


def test_mixed_change_invalidates_all_platforms():
    """共通入力が1つでも混ざれば全 platform 失効（安全側）。"""
    result = C.invalidation_for(
        _inputs(), _inputs(adapter="changed", fixture="sha256:changed"), platform="claude"
    )
    assert result.scope == "all-platforms"


# --- 再利用の判定 --------------------------------------------------------------


def test_adapter_change_keeps_other_platforms_reusable():
    """M0 実測で 22% を占めた「単一 platform の adapter 修正」の場面。"""
    stored = {
        "claude": _inputs(adapter="sha256:adapter-claude-1", model_identity="claude-opus-5"),
        "codex": _inputs(adapter="sha256:adapter-codex-1", model_identity="gpt-5.4"),
        "antigravity": _inputs(adapter="sha256:adapter-agy-1", model_identity="gemini-3"),
    }
    current = _inputs()
    reusable, stale = C.reusable_platforms(stored, current, changed_platform="codex")
    assert "claude" in reusable and "antigravity" in reusable
    assert stale == [], "共通入力が同じなら他 platform は再実測不要"


def test_common_change_makes_every_platform_stale():
    stored = {
        "claude": _inputs(adapter="a1"),
        "codex": _inputs(adapter="a2"),
    }
    current = _inputs(fixture="sha256:fixture-2")
    reusable, stale = C.reusable_platforms(stored, current, changed_platform="codex")
    assert reusable == []
    assert sorted(stale) == ["claude", "codex"]


def test_compare_reports_changed_fields():
    result = C.compare(_inputs(), _inputs(prompt="sha256:prompt-2"))
    assert result.status == C.STATUS_INCOMPATIBLE
    assert "prompt" in result.reasons[0]


def test_identical_inputs_are_compatible():
    result = C.compare(_inputs(), _inputs())
    assert result.status == C.STATUS_COMPATIBLE
    assert result.usable
