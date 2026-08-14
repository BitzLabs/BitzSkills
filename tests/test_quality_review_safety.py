import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/bitz-quality/skills/quality-review"))

from runtime.safety import GenerationFence, publish_generation, read_snapshot, redact_log, resolve_timeout


def test_timeout_isolated_by_reviewer_kind():
    assert resolve_timeout(required=False) == {"attempt": "BLOCKED", "run": "CONDITIONAL_PASS"}
    assert resolve_timeout(required=True)["run"] == "BLOCKED"


def test_generation_fence_rejects_stale_writer():
    fence = GenerationFence()
    old, old_token = fence.begin()
    current, current_token = fence.begin()
    assert not fence.accept(old, old_token)
    assert fence.accept(current, current_token)


def test_snapshot_escape_is_rejected(tmp_path):
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    assert read_snapshot(tmp_path, "ok.txt") == b"ok"
    try:
        read_snapshot(tmp_path, "../outside")
    except (PermissionError, FileNotFoundError):
        pass
    else:
        raise AssertionError("snapshot escape accepted")


def test_publish_uses_single_current_pointer(tmp_path):
    manifest = publish_generation(tmp_path, "g1", {"digest": "abc"})
    assert manifest.is_file()
    assert (tmp_path / "current").read_text(encoding="utf-8").strip() == manifest.name


def test_raw_log_is_default_deny_and_redacted_when_opted_in():
    try:
        redact_log("token=abc")
    except PermissionError:
        pass
    else:
        raise AssertionError("raw log was persisted without opt-in")
    assert redact_log("token=abc", opt_in=True) == "token=[REDACTED]"
