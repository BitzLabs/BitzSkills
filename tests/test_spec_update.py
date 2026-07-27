"""SDD-FR-143 guarded spec_update regression tests."""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
    _write(
        root / ".spec" / "requirements" / f"{rid}.md",
        f"---\nid: {rid}\nversion: 1.0\nstatus: {status}\ndomain: tooling\n"
        f"verification_method: unit-test\n---\n\n### {rid} sample\n",
    )
    return rid


def make_issue(root: Path, num: int, status: str):
    iid = f"SI-CORE-{num:03d}"
    _write(root / ".spec" / "spec-issues" / f"{iid}.md",
           f"---\nid: {iid}\nstatus: {status}\n---\n- purpose: sample\n")
    return iid


def make_task(root: Path, num: int, requirement_id: str, status: str):
    tid = f"CORE-{TSK}{num:03d}"
    _write(
        root / ".spec" / "tasks" / f"{tid}.md",
        f"---\nimplements: {requirement_id}\ndepends_on: []\n"
        f"boundary: tests\nstatus: {status}\n---\n\n### task\n",
    )
    return tid


def run(root, ident=None, to=None, *extra):
    command = [sys.executable, str(UPDATE), str(root)]
    if ident is not None:
        command.append(ident)
    if to is not None:
        command.extend(["--to", to])
    command.extend(extra)
    return subprocess.run(command, capture_output=True, text=True)


def run_interactive(root, ident, to, actor="human"):
    master, slave = os.openpty()
    process = subprocess.Popen(
        [
            sys.executable,
            str(UPDATE),
            str(root),
            ident,
            "--to",
            to,
            "--interactive-decision",
            "--actor",
            actor,
        ],
        stdin=slave,
        stderr=slave,
        stdout=subprocess.PIPE,
        text=True,
    )
    os.close(slave)
    old = status_of(root, "requirements" if "-FR-" in ident else "spec-issues", ident)
    os.write(master, f"{ident} {old}->{to}\n".encode())
    stdout, _ = process.communicate(timeout=5)
    os.close(master)
    return SimpleNamespace(returncode=process.returncode, stdout=stdout or "", stderr="")


def status_of(root: Path, subdir: str, ident: str) -> str:
    text = (root / ".spec" / subdir / f"{ident}.md").read_text(encoding="utf-8")
    return re.search(r"^status:\s*(\S+)", text, re.M).group(1)


def state_text(root: Path) -> str:
    path = root / ".spec" / "STATE.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_SDD_FR_143_human_transition_requires_interactive_flag(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run(tmp_path, rid, "approved")
    assert result.returncode == 3
    assert "authorization-required" in result.stderr
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_143_non_tty_interactive_transition_is_rejected(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run(
        tmp_path,
        rid,
        "approved",
        "--interactive-decision",
        "--actor",
        "human",
    )
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_143_interactive_human_can_approve(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run_interactive(tmp_path, rid, "approved", actor="reviewer")
    assert result.returncode == 0
    assert status_of(tmp_path, "requirements", rid) == "approved"
    assert "実行者未検証" in state_text(tmp_path)


def test_SDD_FR_143_old_by_human_flag_is_rejected(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run(tmp_path, rid, "approved", "--by-human")
    assert result.returncode != 0
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_143_actor_rejects_control_characters(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run(
        tmp_path,
        rid,
        "approved",
        "--interactive-decision",
        "--actor",
        "bad\nactor",
    )
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_143_implementing_requires_local_task(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    result = run(tmp_path, rid, "implementing")
    assert result.returncode == 4
    assert "local task" in result.stderr
    assert status_of(tmp_path, "requirements", rid) == "approved"


def test_SDD_FR_143_implementing_accepts_local_task(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    make_task(tmp_path, 1, rid, "pending")
    result = run(tmp_path, rid, "implementing")
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", rid) == "implementing"


def test_SDD_FR_143_verified_rejects_incomplete_local_task(tmp_path):
    rid = make_req(tmp_path, 1, "implementing")
    tid = make_task(tmp_path, 1, rid, "implementing")
    result = run(tmp_path, rid, "verified")
    assert result.returncode == 4
    assert tid in result.stderr
    assert status_of(tmp_path, "requirements", rid) == "implementing"


def test_SDD_FR_143_verified_accepts_all_done_tasks(tmp_path):
    rid = make_req(tmp_path, 1, "implementing")
    make_task(tmp_path, 1, rid, "done")
    result = run(tmp_path, rid, "verified")
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", rid) == "verified"


def test_SDD_FR_143_task_transition_remains_agent_allowed(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    tid = make_task(tmp_path, 1, rid, "pending")
    result = run(tmp_path, tid, "implementing", "--actor", "agent")
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "tasks", tid) == "implementing"


def test_SDD_FR_143_state_contains_canonical_structured_event(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    make_task(tmp_path, 1, rid, "pending")
    result = run(tmp_path, rid, "implementing", "--actor", "agent")
    assert result.returncode == 0
    match = re.search(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", state_text(tmp_path))
    assert match
    decoded = base64.b64decode(match.group(1), validate=True)
    event = json.loads(decoded)
    assert event["artifact_id"] == rid
    assert event["old"] == "approved"
    assert event["new"] == "implementing"
    assert event["provenance"]["kind"] == "agent"
    assert base64.b64encode(decoded).decode() == match.group(1)


def test_SDD_FR_143_json_diagnostic_has_stable_code(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    result = run(tmp_path, rid, "implementing", "--json")
    assert result.returncode == 4
    assert json.loads(result.stdout)["code"] == "precondition-failed"


def test_SDD_FR_143_unknown_transition_is_rejected(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run(tmp_path, rid, "verified")
    assert result.returncode == 2
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_143_japanese_agent_transition_is_normalized(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    make_task(tmp_path, 1, rid, "pending")
    result = run(tmp_path, rid, "実装中")
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", rid) == "implementing"


def test_SDD_FR_143_issue_accept_is_not_agent_allowed(tmp_path):
    iid = make_issue(tmp_path, 1, "open")
    result = run(tmp_path, iid, "accepted")
    assert result.returncode == 3
    assert status_of(tmp_path, "spec-issues", iid) == "open"
