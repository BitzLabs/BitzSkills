"""FLW-FR-001: squash merge 済みブランチ再利用の事前検査。"""

import importlib.util
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "bitz-flow"
    / "skills"
    / "flow-pr"
    / "scripts"
    / "branch_preflight.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("branch_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, *, merged=None, opened=None, counts="0\t1", has_diff=True):
        self.merged = [] if merged is None else merged
        self.opened = [] if opened is None else opened
        self.counts = counts
        self.has_diff = has_diff
        self.commands = []

    def __call__(self, command, *, cwd, timeout):
        self.commands.append(tuple(command))
        if command[:4] == ["gh", "pr", "list", "--head"]:
            payload = self.merged if "merged" in command else self.opened
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if command[:3] == ["git", "rev-list", "--left-right"]:
            return subprocess.CompletedProcess(command, 0, self.counts + "\n", "")
        if command[:3] == ["git", "diff", "--quiet"]:
            return subprocess.CompletedProcess(command, 1 if self.has_diff else 0, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")


def evaluate(module, runner):
    return module.run_preflight(
        repository=REPO_ROOT,
        branch="feat/reused",
        default_branch="main",
        timeout_seconds=30,
        runner=runner,
    )


def test_flw_fr_001_ready_for_new_branch_with_diff():
    module = load_module()
    report = evaluate(module, FakeRunner())
    assert report["decision"] == "READY"
    assert report["exit_code"] == 0
    assert report["ahead"] == 1
    assert report["behind"] == 0


def test_flw_fr_001_blocks_merged_head_reuse():
    module = load_module()
    merged = [{"number": 56, "headRefOid": "abc", "mergedAt": "2026-07-18T00:00:00Z"}]
    report = evaluate(module, FakeRunner(merged=merged))
    assert report["decision"] == "REUSE_BLOCKED"
    assert report["exit_code"] == 3
    assert report["failed_check"] == "merged-pr"
    assert report["merged_prs"] == [56]


def test_flw_fr_001_blocks_empty_diff():
    module = load_module()
    report = evaluate(module, FakeRunner(counts="3\t0", has_diff=False))
    assert report["decision"] == "REUSE_BLOCKED"
    assert report["failed_check"] == "tree-diff"


def test_flw_fr_001_blocks_wrong_base_and_conflict():
    module = load_module()
    opened = [
        {
            "number": 57,
            "baseRefName": "old-base",
            "mergeable": "CONFLICTING",
            "mergeStateStatus": "DIRTY",
        }
    ]
    report = evaluate(module, FakeRunner(opened=opened))
    assert report["decision"] == "REUSE_BLOCKED"
    assert report["failed_check"] == "open-pr"
    assert report["open_prs"][0]["base"] == "old-base"


def test_flw_fr_001_unknown_mergeability_is_indeterminate():
    module = load_module()
    opened = [
        {
            "number": 58,
            "baseRefName": "main",
            "mergeable": "UNKNOWN",
            "mergeStateStatus": "UNKNOWN",
        }
    ]
    report = evaluate(module, FakeRunner(opened=opened))
    assert report["decision"] == "INDETERMINATE"
    assert report["exit_code"] == 2


def test_flw_fr_001_timeout_is_indeterminate_without_raw_output():
    module = load_module()

    def timeout_runner(command, *, cwd, timeout):
        raise subprocess.TimeoutExpired(command, timeout, output="token=secret")

    report = evaluate(module, timeout_runner)
    encoded = json.dumps(report)
    assert report["decision"] == "INDETERMINATE"
    assert report["failed_check"] == "command-timeout"
    assert "secret" not in encoded
    assert set(report) <= module.JSON_FIELDS


def test_flw_fr_001_rejects_invalid_timeout():
    module = load_module()
    assert module.main(["--branch", "feat/x", "--timeout-seconds", "0"]) == 2
