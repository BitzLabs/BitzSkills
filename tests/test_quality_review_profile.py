import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/bitz-quality/skills/quality-review"))

from profile.sdd_v4 import PERSPECTIVES, evaluate


def scores(value=4.5):
    return {name: value for name in PERSPECTIVES}


def test_v4_profile_pass_records_contract_metadata():
    result = evaluate(scores(), aggregate=4.5, sample_size=7)
    assert result["verdict"] == "PASS"
    assert len(result["profile_digest"]) == 64
    assert result["sample_size"] == 7


def test_v4_profile_blocks_missing_perspective():
    partial = scores()
    partial.pop("measurability")
    assert evaluate(partial, aggregate=5, sample_size=1)["verdict"] == "BLOCKED"


def test_v4_profile_never_passes_pending_charter():
    assert evaluate(scores(), aggregate=5, sample_size=1, charter_status="pending")["verdict"] == "CONTRACT_PENDING"


def test_v4_profile_fails_major_finding():
    assert evaluate(scores(), aggregate=5, major=1, sample_size=1)["verdict"] == "FAIL"
