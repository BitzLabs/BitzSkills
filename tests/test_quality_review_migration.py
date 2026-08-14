import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/bitz-quality/skills/quality-review"))

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


migration = load_module("quality_migration", "plugins/bitz-quality/skills/quality-review/migration/migration.py")
qualification = load_module("quality_qualification", "plugins/bitz-quality/skills/quality-review/qualification/qualification.py")
MigrationEvidence = migration.MigrationEvidence
removal_allowed = migration.removal_allowed
rollback_mode = migration.rollback_mode
FAULTS = qualification.FAULTS
is_current = qualification.is_current
qualify = qualification.qualify


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
