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


# --- SDD-FR-145: 代行可視化経路（on-behalf-of + decision-ref） ---

REF_ISSUE_ID = "SI-CORE-" + "099"  # 直書きすると本リポジトリのspec_inspectが幽霊参照として誤検知する


def make_ref(root: Path) -> str:
    _write(root / ".spec" / "spec-issues" / f"{REF_ISSUE_ID}.md",
           f"---\nid: {REF_ISSUE_ID}\nstatus: accepted\n---\n- 裁定記録\n")
    return f".spec/spec-issues/{REF_ISSUE_ID}.md"


def run_proxy(root, idents, to, *extra):
    command = [sys.executable, str(UPDATE), str(root), *idents, "--to", to, *extra]
    return subprocess.run(command, capture_output=True, text=True)


def proxy_args(ref):
    return ("--on-behalf-of", "hide", "--decision-ref", ref, "--actor", "claude")


def test_SDD_FR_145_proxy_transition_succeeds_without_tty(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    ref = make_ref(tmp_path)
    result = run_proxy(tmp_path, [rid], "approved", *proxy_args(ref))
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", rid) == "approved"
    state = state_text(tmp_path)
    assert "claude on behalf of hide" in state
    assert "裁定参照" in state
    assert "実行者未検証" in state


def test_SDD_FR_145_proxy_requires_all_three_fields(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    ref = make_ref(tmp_path)
    for extra in (
        ("--on-behalf-of", "hide", "--decision-ref", ref),
        ("--on-behalf-of", "hide", "--actor", "claude"),
        ("--decision-ref", ref, "--actor", "claude"),
    ):
        result = run_proxy(tmp_path, [rid], "approved", *extra)
        assert result.returncode == 3, result.stderr
        assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_145_proxy_rejects_missing_decision_ref_path(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run_proxy(
        tmp_path, [rid], "approved",
        "--on-behalf-of", "hide",
        "--decision-ref", ".spec/spec-issues/NOPE.md",
        "--actor", "claude",
    )
    assert result.returncode == 3
    assert "存在しません" in result.stderr
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_145_proxy_rejects_escaping_decision_ref(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    (tmp_path.parent / "outside.md").write_text("x", encoding="utf-8")
    result = run_proxy(
        tmp_path, [rid], "approved",
        "--on-behalf-of", "hide", "--decision-ref", "../outside.md", "--actor", "claude",
    )
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_145_proxy_accepts_https_decision_ref(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    result = run_proxy(
        tmp_path, [rid], "approved",
        "--on-behalf-of", "hide",
        "--decision-ref", "https://github.com/BitzLabs/BitzSkills/pull/109",
        "--actor", "claude",
    )
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", rid) == "approved"


def test_SDD_FR_145_proxy_rejects_agent_transition(tmp_path):
    rid = make_req(tmp_path, 1, "approved")
    make_task(tmp_path, 1, rid, "pending")
    ref = make_ref(tmp_path)
    result = run_proxy(tmp_path, [rid], "implementing", *proxy_args(ref))
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", rid) == "approved"


def test_SDD_FR_145_proxy_with_interactive_flag_is_rejected(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    ref = make_ref(tmp_path)
    result = run_proxy(
        tmp_path, [rid], "approved", "--interactive-decision", *proxy_args(ref),
    )
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", rid) == "draft"


def test_SDD_FR_145_proxy_event_is_schema_v2_with_reference(tmp_path):
    rid = make_req(tmp_path, 1, "draft")
    ref = make_ref(tmp_path)
    result = run_proxy(tmp_path, [rid], "approved", *proxy_args(ref))
    assert result.returncode == 0
    markers = re.findall(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", state_text(tmp_path))
    event = json.loads(base64.b64decode(markers[-1], validate=True))
    assert event["schema_version"] == 2
    assert event["provenance"]["kind"] == "agent-proxy-unverified"
    assert event["provenance"]["actor"] == "claude"
    assert event["provenance"]["on_behalf_of"] == "hide"
    assert event["provenance"]["decision_ref"] == ref


def test_SDD_FR_145_batch_shares_decision_ref_across_events(tmp_path):
    r1 = make_req(tmp_path, 1, "draft")
    r2 = make_req(tmp_path, 2, "draft")
    ref = make_ref(tmp_path)
    result = run_proxy(tmp_path, [r1, r2], "approved", *proxy_args(ref))
    assert result.returncode == 0, result.stderr
    assert status_of(tmp_path, "requirements", r1) == "approved"
    assert status_of(tmp_path, "requirements", r2) == "approved"
    markers = re.findall(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", state_text(tmp_path))
    events = [json.loads(base64.b64decode(m, validate=True)) for m in markers]
    assert len(events) == 2
    assert {e["artifact_id"] for e in events} == {r1, r2}
    assert {e["provenance"]["decision_ref"] for e in events} == {ref}
    assert len({e["event_id"] for e in events}) == 2
    assert not (tmp_path / ".spec" / ".mutation-lock").exists()
    transactions = tmp_path / ".spec" / ".transactions"
    assert not transactions.exists() or not list(transactions.glob("*.json"))


def test_SDD_FR_145_batch_rejects_unknown_id_upfront(tmp_path):
    r1 = make_req(tmp_path, 1, "draft")
    ref = make_ref(tmp_path)
    result = run_proxy(tmp_path, [r1, f"CORE-{FR}999"], "approved", *proxy_args(ref))
    assert result.returncode == 2
    assert status_of(tmp_path, "requirements", r1) == "draft"


def test_SDD_FR_145_batch_requires_proxy_route(tmp_path):
    r1 = make_req(tmp_path, 1, "draft")
    r2 = make_req(tmp_path, 2, "draft")
    result = run_proxy(tmp_path, [r1, r2], "approved", "--actor", "agent")
    assert result.returncode == 3
    assert status_of(tmp_path, "requirements", r1) == "draft"
    assert status_of(tmp_path, "requirements", r2) == "draft"


# --- promoted 遷移の GatePassage 必須化（SDD-FR-157） --------------------------

GATE = "GATE-"
GATE_ID = f"CORE-{GATE}001"
DECISION_REF = ".spec/reports/decision-sample.md"


def make_gate(root: Path, scope, *, gate="promotion", gate_id=GATE_ID):
    _write(root / DECISION_REF, "# 裁定記録\n")
    body = ["---", f"id: {gate_id}", f"gate: {gate}", "date: 2026-07-30",
            "arbiter: hide", "scope: [" + ", ".join(scope) + "]",
            "confirmed_decision_refs:", f"  - {DECISION_REF}",
            "checklist_ref: refs/gates.md#3-promotion-gate", "---", "", "# 通過記録"]
    _write(root / ".spec" / "gates" / f"{gate_id}.md", "\n".join(body) + "\n")
    return gate_id


def promote(root, *idents, gate_passage=None, actor="agent"):
    extra = ["--on-behalf-of", "hide", "--decision-ref", DECISION_REF, "--actor", actor]
    if gate_passage is not None:
        extra += ["--gate-passage", gate_passage]
    command = [sys.executable, str(UPDATE), str(root), *idents, "--to", "promoted", *extra]
    return subprocess.run(command, capture_output=True, text=True)


def setup_promotable(root: Path, count=1):
    idents = []
    for index in range(1, count + 1):
        rid = make_req(root, index, "verified")
        make_task(root, index, rid, "done")
        idents.append(rid)
    _write(root / DECISION_REF, "# 裁定記録\n")
    return idents


def req_status(root: Path, ident: str) -> str:
    return status_of(root, "requirements", ident)


def test_SDD_FR_157_promotion_without_gate_passage_is_rejected(tmp_path):
    """--gate-passage が無い verified→promoted は対象を変更せず非ゼロで終了する"""
    (ident,) = setup_promotable(tmp_path)

    result = promote(tmp_path, ident)

    assert result.returncode != 0
    assert "--gate-passage" in result.stderr
    assert req_status(tmp_path, ident) == "verified"
    assert not (tmp_path / ".spec" / "STATE.md").exists()


def test_SDD_FR_157_promotion_with_valid_gate_passage_succeeds(tmp_path):
    """scope に含まれる ID は GatePassage を参照して promoted へ遷移できる"""
    (ident,) = setup_promotable(tmp_path)
    gate_id = make_gate(tmp_path, [ident])

    result = promote(tmp_path, ident, gate_passage=gate_id)

    assert result.returncode == 0, result.stderr
    assert req_status(tmp_path, ident) == "promoted"


def test_SDD_FR_157_gate_passage_is_recorded_in_state_event(tmp_path):
    """検分の証跡が STATE の構造化 event に残り、schema_version は 2 のまま"""
    (ident,) = setup_promotable(tmp_path)
    gate_id = make_gate(tmp_path, [ident])

    assert promote(tmp_path, ident, gate_passage=gate_id).returncode == 0

    state = (tmp_path / ".spec" / "STATE.md").read_text(encoding="utf-8")
    marker = re.search(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", state)
    event = json.loads(base64.b64decode(marker.group(1)))
    assert event["gate_passage"] == gate_id
    assert event["schema_version"] == 2
    assert f"Gate通過記録: {gate_id}" in state


def test_SDD_FR_157_unknown_gate_passage_is_rejected(tmp_path):
    """実在しない GatePassage を指す要求は適用前に拒否する"""
    (ident,) = setup_promotable(tmp_path)

    result = promote(tmp_path, ident, gate_passage=GATE_ID)

    assert result.returncode != 0
    assert "GatePassageが見つかりません" in result.stderr
    assert req_status(tmp_path, ident) == "verified"


def test_SDD_FR_157_non_promotion_gate_kind_is_rejected(tmp_path):
    """gate 種別が promotion でない GatePassage は promoted 遷移に使えない"""
    (ident,) = setup_promotable(tmp_path)
    gate_id = make_gate(tmp_path, [ident], gate="design")

    result = promote(tmp_path, ident, gate_passage=gate_id)

    assert result.returncode != 0
    assert "'promotion'である必要があります" in result.stderr
    assert req_status(tmp_path, ident) == "verified"


def test_SDD_FR_157_id_outside_scope_is_rejected(tmp_path):
    """scope に1件でも欠けがあれば全体を適用せず拒否する"""
    first, second = setup_promotable(tmp_path, count=2)
    gate_id = make_gate(tmp_path, [first])

    result = promote(tmp_path, first, second, gate_passage=gate_id)

    assert result.returncode != 0
    assert second in result.stderr
    assert req_status(tmp_path, first) == "verified"
    assert req_status(tmp_path, second) == "verified"


def test_SDD_FR_157_scope_as_id_set_allows_batch_promotion(tmp_path):
    """1つの GatePassage が ID の集合を scope に列挙して一括昇格できる"""
    first, second = setup_promotable(tmp_path, count=2)
    gate_id = make_gate(tmp_path, [first, second])

    result = promote(tmp_path, first, second, gate_passage=gate_id)

    assert result.returncode == 0, result.stderr
    assert req_status(tmp_path, first) == "promoted"
    assert req_status(tmp_path, second) == "promoted"


def test_SDD_FR_157_gate_passage_rejected_on_other_transitions(tmp_path):
    """--gate-passage は verified→promoted 以外では黙認せず拒否する"""
    rid = make_req(tmp_path, 1, "draft")
    make_gate(tmp_path, [rid])

    result = run(tmp_path, rid, "approved", "--on-behalf-of", "hide",
                 "--decision-ref", DECISION_REF, "--actor", "agent",
                 "--gate-passage", GATE_ID)

    assert result.returncode != 0
    assert "verified→promoted遷移にだけ" in result.stderr
    assert req_status(tmp_path, rid) == "draft"


def test_SDD_FR_157_other_transitions_need_no_gate_passage(tmp_path):
    """promoted 以外の遷移は従来どおり GatePassage 無しで通る"""
    rid = make_req(tmp_path, 1, "approved")
    make_task(tmp_path, 1, rid, "pending")

    result = run(tmp_path, rid, "implementing", "--actor", "agent")

    assert result.returncode == 0, result.stderr
    assert req_status(tmp_path, rid) == "implementing"


# --- SDD-FR-166: verified からの再着手（verified → implementing） ---


def test_SDD_FR_166_verified_reentry_requires_human_decision(tmp_path):
    """人間裁定経路なしでは拒否され、対象も STATE も変わらない。"""
    rid = make_req(tmp_path, 1, "verified")
    make_task(tmp_path, 1, rid, "pending")

    result = run(tmp_path, rid, "implementing", "--actor", "agent")

    assert result.returncode != 0
    assert "authorization-required" in (result.stderr + result.stdout)
    assert req_status(tmp_path, rid) == "verified"
    assert rid not in state_text(tmp_path)


def test_SDD_FR_166_verified_reentry_succeeds_via_proxy(tmp_path):
    """代行可視化経路（--on-behalf-of + --decision-ref）なら遷移する。"""
    rid = make_req(tmp_path, 1, "verified")
    make_task(tmp_path, 1, rid, "pending")
    ref = make_ref(tmp_path)

    result = run_proxy(tmp_path, [rid], "implementing", *proxy_args(ref))

    assert result.returncode == 0, result.stderr
    assert req_status(tmp_path, rid) == "implementing"
    state = state_text(tmp_path)
    assert "claude on behalf of hide" in state
    assert ref in state


def test_SDD_FR_166_verified_reentry_records_provenance(tmp_path):
    """裁定参照が STATE の構造化イベントに残る。"""
    rid = make_req(tmp_path, 1, "verified")
    make_task(tmp_path, 1, rid, "pending")
    ref = make_ref(tmp_path)

    run_proxy(tmp_path, [rid], "implementing", *proxy_args(ref))

    events = re.findall(r"<!-- sdd-event:([A-Za-z0-9+/=]+) -->", state_text(tmp_path))
    payload = json.loads(base64.b64decode(events[-1]))
    assert payload["old"] == "verified" and payload["new"] == "implementing"
    assert payload["provenance"]["kind"] == "agent-proxy-unverified"
    assert payload["provenance"]["decision_ref"] == ref


def test_SDD_FR_166_verified_reentry_keeps_verification_evidence(tmp_path):
    """既存の検証証跡を削除も改変もしない。"""
    rid = make_req(tmp_path, 1, "verified")
    make_task(tmp_path, 1, rid, "pending")
    ref = make_ref(tmp_path)
    evidence = tmp_path / ".spec" / "verification" / "pytest--abc1234.json"
    _write(evidence, '{"result": "green"}')
    before = evidence.read_text(encoding="utf-8")

    run_proxy(tmp_path, [rid], "implementing", *proxy_args(ref))

    assert evidence.exists(), "検証証跡を削除してはならない"
    assert evidence.read_text(encoding="utf-8") == before


def test_SDD_FR_166_promoted_cannot_return_to_implementing(tmp_path):
    """Promotion Gate を通ったものは deprecated 経由でのみ変更する。"""
    rid = make_req(tmp_path, 1, "promoted")
    make_task(tmp_path, 1, rid, "pending")
    ref = make_ref(tmp_path)

    result = run_proxy(tmp_path, [rid], "implementing", *proxy_args(ref))

    assert result.returncode != 0
    assert "precondition-failed" in (result.stderr + result.stdout)
    assert req_status(tmp_path, rid) == "promoted"


def test_SDD_FR_166_existing_verified_transitions_still_work(tmp_path):
    """deprecated への遷移など、既存の verified 起点の遷移を壊さない。"""
    rid = make_req(tmp_path, 1, "verified")
    ref = make_ref(tmp_path)

    result = run_proxy(tmp_path, [rid], "deprecated", *proxy_args(ref))

    assert result.returncode == 0, result.stderr
    assert req_status(tmp_path, rid) == "deprecated"
