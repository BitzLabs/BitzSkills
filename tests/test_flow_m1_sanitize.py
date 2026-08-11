"""FLW-TSK-030: 診断出力 sanitizer の単体テストと負の対照。

負の対照（通してはならないもの）: 絶対 path、URL userinfo、token 様文字列、制御文字、
非 ASCII path の生バイト、repo 外の path。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import result as R  # noqa: E402
from flowlib import sanitize as S  # noqa: E402


# --- 遮断（負の対照）----------------------------------------------------------


@pytest.mark.parametrize(
    "value,kind",
    [
        ("/home/someone/secrets/repo", S.KIND_ABSOLUTE_PATH),
        ("C:\\Users\\someone\\repo", S.KIND_ABSOLUTE_PATH),
        ("\\\\server\\share\\repo", S.KIND_ABSOLUTE_PATH),
        ("https://user:pass@github.com/o/r.git", S.KIND_URL_USERINFO),
        ("ssh://git:secret@example.com/r", S.KIND_URL_USERINFO),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123", S.KIND_TOKEN),
        ("github_pat_11ABCDEFG0123456789", S.KIND_TOKEN),
        ("AKIAIOSFODNN7EXAMPLE", S.KIND_TOKEN),
        ("sk-0123456789abcdefghij", S.KIND_TOKEN),
        ("abcdefghijklmnopqrstuvwxyz012345", S.KIND_TOKEN),
        ("branch\x00name", S.KIND_CONTROL_CHAR),
        ("line1\nline2", S.KIND_CONTROL_CHAR),
        ("tab\there", S.KIND_CONTROL_CHAR),
        ("bell\x07", S.KIND_CONTROL_CHAR),
    ],
)
def test_unsafe_values_are_blocked(value, kind):
    safe, redaction = S.sanitize_value("arg", value)
    assert safe is None, f"遮断されなければならない: {value!r}"
    assert redaction.kind == kind


def test_redaction_keeps_length_and_digest_only():
    value = "/home/someone/secret"
    _, redaction = S.sanitize_value("repo_arg", value)
    assert redaction.length == len(value)
    assert redaction.digest == R.sha256_of(value.encode("utf-8"))
    assert value not in redaction.as_line()


def test_redaction_is_visible_not_silent():
    result = S.sanitize_diagnostic({"a": "ok-value", "b": "/abs/path"})
    assert not result.clean
    assert "a" in result.values and "b" not in result.values
    assert result.redactions[0].as_line().startswith("REDACTED field=b")


# --- 許可（正の対照）----------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "--limit",
        "base",
        "HEAD",
        "feat/x",
        "src/a.py",
        "12",
        "sha256:" + "a" * 64,
        "invalid-ref",
        "日本語/ファイル.txt",
    ],
)
def test_safe_values_pass(value):
    safe, redaction = S.sanitize_value("arg", value)
    assert redaction is None, f"遮断してはならない: {value!r}"
    assert safe == value


def test_digest_is_not_mistaken_for_a_token():
    digest = R.sha256_of(b"x")
    assert S.classify(digest) is None


def test_non_ascii_path_is_kept_but_raw_control_bytes_are_not():
    ok, _ = S.sanitize_value("p", "テスト/ファイル.txt")
    assert ok == "テスト/ファイル.txt"
    blocked, redaction = S.sanitize_value("p", "テスト\x01/ファイル.txt")
    assert blocked is None and redaction.kind == S.KIND_CONTROL_CHAR


# --- repo 相対化 ---------------------------------------------------------------


def test_path_inside_repo_is_relativized(tmp_path):
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    safe, redaction = S.relative_to_repo("target_path", str(target), tmp_path)
    assert redaction is None and safe == "src/a.py"


def test_path_outside_repo_is_blocked(tmp_path):
    outside = tmp_path.parent / "elsewhere.txt"
    safe, redaction = S.relative_to_repo("target_path", str(outside), tmp_path)
    assert safe is None and redaction.kind == S.KIND_OUTSIDE_REPO


def test_diagnostic_relativizes_path_fields(tmp_path):
    target = tmp_path / "a.py"
    target.write_text("x", encoding="utf-8")
    result = S.sanitize_diagnostic(
        {"target_path": str(target), "arg": "--limit"}, repo_root=tmp_path
    )
    assert result.clean
    assert result.values["target_path"] == "a.py"


# --- cause の関門 --------------------------------------------------------------


def test_allowed_causes_come_from_result_module():
    assert set(S.allowed_causes()) == set(R.ALLOWED_CAUSES)


def test_raw_git_message_is_not_passed_as_cause():
    assert S.normalize_cause("fatal: not a git repository (or any parent up to mount point /)") is None
    assert S.normalize_cause("not-repository") == "not-repository"
    assert S.normalize_cause(None) is None


# --- canary --------------------------------------------------------------------


def test_canary_detection_is_exact():
    canaries = ["CANARY-abc123", "CANARY-def456"]
    text = "log line with CANARY-abc123 embedded"
    assert S.detect_canaries(text, canaries) == ["CANARY-abc123"]
    assert S.canary_clean(text, canaries) is False


def test_canary_absent_gives_no_false_positive():
    canaries = ["CANARY-abc123"]
    assert S.detect_canaries("ordinary log line", canaries) == []
    assert S.canary_clean("ordinary log line", canaries) is True


def test_empty_canary_is_ignored():
    assert S.detect_canaries("anything", ["", None]) == []


def test_all_canaries_detected_when_all_present():
    canaries = ["C1-xyz", "C2-xyz", "C3-xyz"]
    text = " ".join(canaries)
    assert S.detect_canaries(text, canaries) == canaries


# --- 補助 ----------------------------------------------------------------------


def test_windows_absolute_detection_works_on_posix():
    assert S.windows_path_is_absolute("C:\\repo") is True
    assert S.windows_path_is_absolute("src/a.py") is False


def test_redaction_kinds_are_a_closed_set():
    for value in ("/abs", "https://u:p@h/x", "ghp_" + "a" * 30, "x\x00y"):
        kind = S.classify(value)
        assert kind in S.REDACTION_KINDS
