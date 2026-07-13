"""CORE-FR-005 spec_update.py の回帰テスト（テスト先行）。

status 遷移スクリプトが sdd-core の権限マトリクスをコード強制することを検証する:
人間専用遷移の --by-human なし拒否、--by-human ありでの許可、
エージェント許容遷移の適用、不正遷移の拒否、STATE.md への遷移記録追記。
"""
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
)
UPDATE = SCRIPTS_DIR / "spec_update.py"

FR = "FR-"
TSK = "TSK-"


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_req(root: Path, num: int, status: str):
    rid = f"CORE-{FR}{num:03d}"
    _write(root / ".spec" / "requirements" / f"{rid}.md",
           f"---\nid: {rid}\nversion: 1.0\nstatus: {status}\ndomain: tooling\n"
           f"verification_method: example-test\n---\n\n### {rid} サンプル\n")
    return rid


def make_issue(root: Path, num: int, status: str):
    iid = f"SI-CORE-{num:03d}"
    _write(root / ".spec" / "spec-issues" / f"{iid}.md",
           f"---\nid: {iid}\nstatus: {status}\n---\n- 目的: サンプル\n")
    return iid


def make_task(root: Path, num: int, status: str):
    tid = f"CORE-{TSK}{num:03d}"
    _write(root / ".spec" / "tasks" / f"{tid}.md",
           f"---\nimplements: CORE-{FR}001\ndepends_on: []\nstatus: {status}\n---\n\n### {tid} サンプル\n")
    return tid


def run(root, rid, to, *extra):
    return subprocess.run(
        [sys.executable, str(UPDATE), str(root), rid, "--to", to, *extra],
        capture_output=True, text=True)


def status_of(root: Path, subdir: str, rid: str) -> str:
    text = (root / ".spec" / subdir / f"{rid}.md").read_text(encoding="utf-8")
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    return m.group(1) if m else ""


def state_text(root: Path) -> str:
    p = root / ".spec" / "STATE.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --- 人間専用遷移の拒否 ------------------------------------------------------

def test_agent_cannot_approve_requirement(tmp_path):
    """draft→approved はエージェント（--by-human なし）では拒否される。"""
    rid = make_req(tmp_path, 1, "draft")
    res = run(tmp_path, rid, "approved")
    assert res.returncode != 0, "draft→approved は人間専用でなければならない"
    assert status_of(tmp_path, "requirements", rid) == "draft", "拒否時は status を変えない"
    assert rid not in state_text(tmp_path), "拒否時は STATE.md に書かない"


def test_agent_cannot_accept_issue(tmp_path):
    """open→accepted はエージェントでは拒否される。"""
    iid = make_issue(tmp_path, 1, "open")
    res = run(tmp_path, iid, "accepted")
    assert res.returncode != 0
    assert status_of(tmp_path, "spec-issues", iid) == "open"


def test_agent_cannot_promote(tmp_path):
    """verified→promoted は人間専用。"""
    rid = make_req(tmp_path, 1, "verified")
    res = run(tmp_path, rid, "promoted")
    assert res.returncode != 0
    assert status_of(tmp_path, "requirements", rid) == "verified"


def test_agent_cannot_deprecate(tmp_path):
    """任意→deprecated は人間専用。"""
    rid = make_req(tmp_path, 1, "approved")
    res = run(tmp_path, rid, "deprecated")
    assert res.returncode != 0
    assert status_of(tmp_path, "requirements", rid) == "approved"


# --- --by-human ありでの許可 -------------------------------------------------

def test_human_can_approve_requirement(tmp_path):
    """--by-human 明示なら draft→approved を適用する。"""
    rid = make_req(tmp_path, 1, "draft")
    res = run(tmp_path, rid, "approved", "--by-human")
    assert res.returncode == 0, res.stderr
    assert status_of(tmp_path, "requirements", rid) == "approved"


def test_human_can_accept_issue(tmp_path):
    """--by-human 明示なら open→accepted を適用する。"""
    iid = make_issue(tmp_path, 1, "open")
    res = run(tmp_path, iid, "accepted", "--by-human")
    assert res.returncode == 0, res.stderr
    assert status_of(tmp_path, "spec-issues", iid) == "accepted"


# --- エージェント許容遷移 ----------------------------------------------------

def test_agent_can_start_implementing(tmp_path):
    """approved→implementing はエージェントで適用できる。"""
    rid = make_req(tmp_path, 1, "approved")
    res = run(tmp_path, rid, "implementing")
    assert res.returncode == 0, res.stderr
    assert status_of(tmp_path, "requirements", rid) == "implementing"


def test_agent_can_verify(tmp_path):
    """implementing→verified はエージェント（機械判定）で適用できる。"""
    rid = make_req(tmp_path, 1, "implementing")
    res = run(tmp_path, rid, "verified")
    assert res.returncode == 0, res.stderr
    assert status_of(tmp_path, "requirements", rid) == "verified"


def test_agent_can_advance_task(tmp_path):
    """タスク pending→implementing はエージェントで適用できる。"""
    tid = make_task(tmp_path, 1, "pending")
    res = run(tmp_path, tid, "implementing")
    assert res.returncode == 0, res.stderr
    assert status_of(tmp_path, "tasks", tid) == "implementing"


# --- 不正遷移の拒否 ----------------------------------------------------------

def test_undefined_transition_rejected_even_for_human(tmp_path):
    """権限マトリクス未定義の遷移は --by-human でも拒否する。"""
    rid = make_req(tmp_path, 1, "draft")
    res = run(tmp_path, rid, "verified", "--by-human")  # draft→verified は未定義
    assert res.returncode != 0
    assert status_of(tmp_path, "requirements", rid) == "draft"


# --- STATE.md 追記 -----------------------------------------------------------

def test_records_transition_in_state(tmp_path):
    """遷移適用時に STATE.md へ対象 ID・旧→新 status・実行主体を追記する。"""
    rid = make_req(tmp_path, 1, "approved")
    res = run(tmp_path, rid, "implementing", "--actor", "planエージェント")
    assert res.returncode == 0, res.stderr
    st = state_text(tmp_path)
    assert rid in st
    assert "approved" in st and "implementing" in st
