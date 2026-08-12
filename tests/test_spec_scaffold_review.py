"""SDD-FR-167: spec_scaffold の review 種別。

中心命題: **生成した雛形がそのまま spec_inspect を通る**こと。
雛形が検証を通らなければ、この機能は目的（書いた後の手戻りを無くす）を果たしていない。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
SCAFFOLD = SCRIPTS / "spec_scaffold.py"
INSPECT = SCRIPTS / "spec_inspect.py"
DOMAINS = REPO_ROOT / "plugins" / "bitz-sdd" / ".spec" / "requirements" / "domains.md"

# ダミー ID を直書きすると本リポジトリの spec_inspect が幽霊参照として誤検知するため分割する
REV = "TST-" + "REV"
FR = "TST-" + "FR"
TSK = "TST-" + "TSK"


def rev_id(number: int) -> str:
    return f"{REV}-{number:03d}"


@pytest.fixture
def workspace(tmp_path):
    """spec_inspect が受け付ける最小のワークスペース。"""
    spec = tmp_path / ".spec"
    for name in ("reviews", "requirements", "tasks", "spec-issues"):
        (spec / name).mkdir(parents=True)
    (spec / "requirements" / "domains.md").write_text(
        DOMAINS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def scaffold(workspace, *args):
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), str(workspace), "review", *args],
        capture_output=True, text=True,
    )


def inspect(workspace):
    return subprocess.run(
        [sys.executable, str(INSPECT), str(workspace)], capture_output=True, text=True
    )


def load(workspace, ident):
    return json.loads(
        (workspace / ".spec" / "reviews" / f"{ident}.json").read_text(encoding="utf-8")
    )


# --- 生成 -----------------------------------------------------------------------


def test_review_creates_json_and_markdown(workspace):
    result = scaffold(workspace, "--prefix", REV, "--title", "T", "--owner", "o")
    assert result.returncode == 0, result.stderr
    reviews = workspace / ".spec" / "reviews"
    assert (reviews / f"{rev_id(1)}.json").exists()
    assert (reviews / f"{rev_id(1)}.md").exists()


def test_numbering_increments(workspace):
    for _ in range(3):
        assert scaffold(workspace, "--prefix", REV).returncode == 0
    names = sorted(p.stem for p in (workspace / ".spec" / "reviews").glob("*.json"))
    assert names == [rev_id(n) for n in (1, 2, 3)]


def test_numbering_sees_existing_json(workspace):
    """review は JSON が実体。md だけ見ると採番が衝突する。"""
    (workspace / ".spec" / "reviews" / f"{rev_id(7)}.json").write_text("{}", encoding="utf-8")
    assert scaffold(workspace, "--prefix", REV).returncode == 0
    assert (workspace / ".spec" / "reviews" / f"{rev_id(8)}.json").exists()


def test_existing_file_is_not_overwritten(workspace):
    scaffold(workspace, "--prefix", REV)
    before = (workspace / ".spec" / "reviews" / f"{rev_id(1)}.json").read_text(encoding="utf-8")
    result = scaffold(workspace, "--prefix", REV, "--number", "1")
    assert result.returncode != 0
    assert (workspace / ".spec" / "reviews" / f"{rev_id(1)}.json").read_text(encoding="utf-8") == before


# --- 中心命題: 雛形がそのまま検証を通る -------------------------------------------


def test_empty_template_passes_inspect(workspace):
    scaffold(workspace, "--prefix", REV, "--title", "T", "--owner", "o")
    result = inspect(workspace)
    assert "問題: 0" in result.stdout, result.stdout


def test_template_with_findings_passes_inspect(workspace):
    scaffold(workspace, "--prefix", REV, "--owner", "o",
             "--findings", "3", "--preconditions", "2")
    result = inspect(workspace)
    assert "問題: 0" in result.stdout, result.stdout


def test_many_findings_pass_inspect(workspace):
    scaffold(workspace, "--prefix", REV, "--owner", "o",
             "--findings", "10", "--preconditions", "10")
    assert "問題: 0" in inspect(workspace).stdout


# --- 必須キー（SDD-FR-158 / SDD-FR-161）------------------------------------------


def test_top_level_required_keys(workspace):
    scaffold(workspace, "--prefix", REV)
    payload = load(workspace, rev_id(1))
    for key in ("schema_version", "review_id", "verdict", "aggregate_score",
                "perspective_scores", "findings_summary", "findings",
                "gate_preconditions", "carried_over", "conditional_items"):
        assert key in payload, key
    assert payload["review_id"] == rev_id(1)


def test_finding_has_every_required_key(workspace):
    scaffold(workspace, "--prefix", REV, "--findings", "1")
    finding = load(workspace, rev_id(1))["findings"][0]
    for key in ("id", "priority", "severity", "source", "title", "recommendation",
                "tracked_by", "status"):
        assert key in finding, key
    assert finding["id"] == f"{rev_id(1)}:SYN-001"
    assert finding["source"], "source は空だと必須キー欠落と判定される"


def test_precondition_id_is_gp_form_not_full_id(workspace):
    """tracked_by は <REV-ID>:GP-NNN だが、gate_preconditions の id は GP-NNN。"""
    scaffold(workspace, "--prefix", REV, "--preconditions", "2")
    preconditions = load(workspace, rev_id(1))["gate_preconditions"]
    assert [p["id"] for p in preconditions] == ["GP-001", "GP-002"]


def test_verified_precondition_has_evidence(workspace):
    """basis: verified には evidence が必須。書き忘れではなく埋める欄として置く。"""
    scaffold(workspace, "--prefix", REV, "--preconditions", "1")
    precondition = load(workspace, rev_id(1))["gate_preconditions"][0]
    assert precondition["basis"] == "verified"
    assert precondition["evidence"], "verified なら evidence が要る"


def test_markdown_frontmatter_has_decision(workspace):
    """decision は sdd-report の自動集計が参照する。"""
    scaffold(workspace, "--prefix", REV, "--title", "T", "--owner", "o")
    text = (workspace / ".spec" / "reviews" / f"{rev_id(1)}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    head = text.split("---\n")[1]
    for key in ("id:", "title:", "status:", "version:", "updated:", "owner:", "decision:"):
        assert key in head, key


def test_default_verdict_is_fail(workspace):
    """雛形の既定は FAIL。埋めないまま PASS が残る事故を防ぐ。"""
    scaffold(workspace, "--prefix", REV)
    assert load(workspace, rev_id(1))["verdict"] == "FAIL"
    text = (workspace / ".spec" / "reviews" / f"{rev_id(1)}.md").read_text(encoding="utf-8")
    assert "decision: FAIL" in text


# --- 既存種別の非退行 -------------------------------------------------------------


def test_other_kinds_still_generate(workspace):
    result = subprocess.run(
        [sys.executable, str(SCAFFOLD), str(workspace), "requirement",
         "--prefix", FR, "--domain", "workflow", "--title", "T"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (workspace / ".spec" / "requirements" / f"{FR}-001.md").exists()


def test_task_still_requires_implements(workspace):
    result = subprocess.run(
        [sys.executable, str(SCAFFOLD), str(workspace), "task", "--prefix", TSK],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "--implements" in result.stderr


def test_unknown_kind_is_rejected(workspace):
    result = subprocess.run(
        [sys.executable, str(SCAFFOLD), str(workspace), "nonsense", "--prefix", "X"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
