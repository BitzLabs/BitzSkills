import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/bitz-quality/skills/quality-review"))

from migration.migration import MigrationEvidence, removal_allowed, rollback_mode
from qualification.qualification import FAULTS, is_current, qualify


def trial(verdict):
    return {"verdict": verdict, "required_fields": True}


def test_qualification_requires_three_trials_and_fault_matrix():
    trials = {"linux": [trial(v) for v in ("green", "red", "stale")], "macos": [trial(v) for v in ("green", "red", "stale")]}
    record = qualify(trials, compatibility_key="model-a/schema-1")
    assert record.fault_matrix == FAULTS - {"unknown"}
    assert not record.qualified
    trials["linux"].append(trial("unknown")); trials["macos"].append(trial("unknown"))
    record = qualify(trials, compatibility_key="model-a/schema-1")
    assert record.qualified
    assert is_current(record, "model-a/schema-1")
    assert not is_current(record, "model-b/schema-1")


def test_removal_requires_two_gates_and_reversible_evidence():
    evidence = MigrationEvidence(True, False, True, True, True, 7)
    assert not removal_allowed(bitz_sdd_gate=False, bitz_quality_gate=True, evidence=evidence)
    assert removal_allowed(bitz_sdd_gate=True, bitz_quality_gate=True, evidence=evidence)
    assert rollback_mode(point_of_no_return=True) == "forward-fix"
