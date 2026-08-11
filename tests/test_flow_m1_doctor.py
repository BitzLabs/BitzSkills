"""repo.doctor v2（FLW-FR-011）— operation 別 capability 診断。

確認したいこと: 対象 project へ書き込まないこと、不足時に stage / 許可語彙 cause /
next action を返すこと、GitHub 非利用時の gh 欠如が warning であること、
診断出力に秘密値・絶対 path が現れないこと。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import doctor as D  # noqa: E402

ALLOWED_CAUSES = {
    "not-repository", "invalid-ref", "invalid-path", "dirty", "detached-head",
    "no-upstream", "non-fast-forward", "conflict", "timeout", "command-unavailable",
    "permission-denied", "snapshot-mismatch", "remote-unavailable", "result-indeterminate",
}


def _git(repo: Path, *args: str, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-qm", "chore: init")
    return path


@pytest.fixture
def plain(tmp_path):
    path = tmp_path / "plain"
    path.mkdir()
    return path


def _snapshot(path: Path) -> set[tuple[str, int]]:
    return {
        (str(p.relative_to(path)), p.stat().st_size)
        for p in path.rglob("*") if p.is_file()
    }


# --- 副作用が無い ---------------------------------------------------------------


def test_diagnosis_does_not_write_to_the_project(repo):
    before = _snapshot(repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout
    D.diagnose(repo)
    assert _snapshot(repo) == before, "診断で project を変更してはならない"
    assert _git(repo, "rev-parse", "HEAD").stdout == head_before


def test_probe_file_is_cleaned_up(repo):
    D.diagnose(repo)
    assert list((repo / ".git").glob(".bitz-flow-doctor-probe")) == []


# --- 正常系 ---------------------------------------------------------------------


def test_healthy_repo_supports_read_operations(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    for operation in ("repo.inspect", "git.status", "git.log", "worktree.list"):
        assert diagnosis.operations[operation]["supported"] is True


def test_local_write_capabilities_are_reported(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    for name in ("owner-only-area", "atomic-rename", "fsync", "native-index-lock"):
        assert diagnosis.capabilities[name] is True


def test_every_operation_has_a_capability_entry(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    assert set(diagnosis.operations) == set(D.OPERATION_CAPABILITIES)
    for entry in diagnosis.operations.values():
        assert set(entry) == {"required", "missing", "supported"}


# --- 不足の報告 -----------------------------------------------------------------


def test_missing_repository_is_reported_with_stage_and_cause(plain):
    diagnosis = D.diagnose(plain, uses_github=False, gh_available=True)
    finding = next(f for f in diagnosis.findings if f.name == "repository")
    assert finding.severity == D.SEVERITY_MISSING
    assert finding.cause == "not-repository"
    assert finding.stage == "inspect"
    assert finding.next_action


def test_missing_remote_is_a_warning(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    finding = next(f for f in diagnosis.findings if f.name == "remote")
    assert finding.severity == D.SEVERITY_WARNING
    assert finding.cause == "remote-unavailable"


def test_remote_operations_are_unsupported_without_remote(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    for operation in ("git.fetch", "git.publish-branch", "git.delete-remote-branch"):
        assert diagnosis.operations[operation]["supported"] is False
        assert "remote" in diagnosis.operations[operation]["missing"]


def test_detached_head_is_a_warning(repo):
    _git(repo, "checkout", "-q", "--detach")
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    finding = next(f for f in diagnosis.findings if f.name == "default-branch")
    assert finding.severity == D.SEVERITY_WARNING
    assert finding.cause == "detached-head"


def test_all_causes_are_from_allowed_vocabulary(plain):
    diagnosis = D.diagnose(plain, uses_github=True, gh_available=False)
    for finding in diagnosis.findings:
        assert finding.cause is None or finding.cause in ALLOWED_CAUSES


def test_every_missing_finding_has_a_next_action(plain):
    diagnosis = D.diagnose(plain, uses_github=True, gh_available=False)
    for finding in diagnosis.blocking:
        assert finding.next_action, f"{finding.name} に next action が無い"


# --- gh の扱い ------------------------------------------------------------------


def test_gh_missing_is_warning_when_github_is_not_used(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=False)
    finding = next(f for f in diagnosis.findings if f.name == "gh")
    assert finding.severity == D.SEVERITY_WARNING


def test_gh_missing_is_blocking_when_github_is_used(repo):
    diagnosis = D.diagnose(repo, uses_github=True, gh_available=False)
    finding = next(f for f in diagnosis.findings if f.name == "gh")
    assert finding.severity == D.SEVERITY_MISSING


def test_gh_present_produces_no_finding(repo):
    diagnosis = D.diagnose(repo, uses_github=True, gh_available=True)
    assert not [f for f in diagnosis.findings if f.name == "gh"]


# --- remote CAS -----------------------------------------------------------------


def test_publish_needs_remote_cas(tmp_path, repo):
    bare = tmp_path / "r.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _git(repo, "remote", "add", "origin", str(bare))

    with_cas = D.diagnose(repo, uses_github=False, gh_available=True, remote_cas=True)
    assert with_cas.operations["git.publish-branch"]["supported"] is True

    without = D.diagnose(repo, uses_github=False, gh_available=True, remote_cas=False)
    assert without.operations["git.publish-branch"]["supported"] is False
    assert "remote-cas" in without.operations["git.publish-branch"]["missing"]


# --- 出力の安全性 ---------------------------------------------------------------


def test_rendered_findings_contain_no_absolute_paths(plain):
    diagnosis = D.diagnose(plain, uses_github=True, gh_available=False)
    for line in D.render_findings(diagnosis, repo_root=plain):
        assert not line.startswith("/")
        assert str(plain) not in line


def test_rendered_findings_redact_unsafe_values(repo):
    diagnosis = D.diagnose(repo, uses_github=False, gh_available=True)
    unsafe = D.Finding(
        "custom", D.SEVERITY_MISSING, "/home/someone/secret",
        next_action="https://user:pass@example.com/x",
    )
    patched = D.Diagnosis((unsafe,), diagnosis.capabilities, diagnosis.operations)
    lines = D.render_findings(patched, repo_root=repo)
    text = "\n".join(lines)
    assert "/home/someone/secret" not in text
    assert "user:pass" not in text
    assert "REDACTED" in text


def test_findings_are_split_into_blocking_and_warnings(plain):
    diagnosis = D.diagnose(plain, uses_github=False, gh_available=False)
    assert diagnosis.blocking
    assert all(f.severity == D.SEVERITY_MISSING for f in diagnosis.blocking)
    assert all(f.severity == D.SEVERITY_WARNING for f in diagnosis.warnings)
