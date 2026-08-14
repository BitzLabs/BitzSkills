"""M2-4 reconnaissance/operations evidence fixtures。"""

import dataclasses
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import reconnaissance as R  # noqa: E402


LIMITS = R.ReconnaissanceLimits(10, 100, 10000)
LOCAL_ONLY = R.InFlightWork("feat/local", None, ("plugins/bitz-flow",), False, False, False)


def _inspect(**overrides):
    values = {
        "candidates": (LOCAL_ONLY,),
        "touched_paths": ("plugins/bitz-flow/skills/flow-core",),
        "limits": LIMITS,
        "elapsed_seconds": 1,
        "observed_bytes": 100,
        "source_complete": True,
    }
    values.update(overrides)
    return R.inspect_in_flight(**values)


def test_M2_FLT_045_local_unpushed_branch_without_worktree_or_pr_is_listed():
    result = _inspect(touched_paths=("tests",))
    assert result.code == "DONE" and result.items == (LOCAL_ONLY,)


def test_M2_FLT_046_overlapping_path_is_reported_even_without_work_id_match():
    result = _inspect()
    assert result.overlaps == ("feat/local",)


def test_M2_FLT_047_write_entry_without_reconnaissance_is_blocked():
    assert R.authorize_write_entry(None) == "BLOCKED"
    assert R.authorize_write_entry(_inspect()) == "DONE"


def test_M2_FLT_051_missing_limits_overflow_timeout_and_indeterminate_block():
    assert _inspect(limits=None).code == "BLOCKED"
    assert _inspect(candidates=(LOCAL_ONLY,) * 101).code == "BLOCKED"
    assert _inspect(observed_bytes=10001).code == "BLOCKED"
    assert _inspect(elapsed_seconds=11).code == "BLOCKED"
    uncertain = _inspect(source_complete=False)
    assert uncertain.code == "INDETERMINATE"
    assert R.authorize_write_entry(uncertain) == "BLOCKED"


def test_M2_FLT_052_quarantine_over_two_days_or_unresolved_escalates():
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    assert R.quarantine_escalation(detected_at=now - timedelta(hours=49), now=now, unresolved=False) == "ESCALATE"
    assert R.quarantine_escalation(detected_at=now, now=now, unresolved=True) == "ESCALATE"
    assert R.quarantine_escalation(detected_at=now, now=now, unresolved=False) == "MONITOR"


def test_M2_FLT_055_missing_tampered_or_restored_chain_mismatch_is_indeterminate():
    chain = R.EvidenceChain()
    first = chain.append({"kind": "intent", "id": "op-1"})
    second = chain.append({"kind": "receipt", "id": "op-1"})
    assert R.EvidenceChain.verify(chain.entries()) == "DONE"
    tampered = dataclasses.replace(first, payload={"kind": "intent", "id": "op-x"})
    assert R.EvidenceChain.verify((tampered, second)) == "INDETERMINATE"
    assert R.EvidenceChain.verify((second,)) == "INDETERMINATE"
