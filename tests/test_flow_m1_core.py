"""FLW-TSK-031: M1-1 core の統合 fault test・契約表照合・変異試験。

各モジュールの単体テストは実装タスク側（coordinator / durable / recovery / sanitize）が持つ。
ここが持つのは次の3つに限る。

1. **契約表照合** — schemas/ と references/ が同じ enum・同じ field 集合を指すこと（横断）
2. **統合 fault** — モジュールをまたいだときに不変条件が保たれること
3. **変異試験** — 上の検査が実際に検出力を持つこと（検査自体を壊して落ちることを確認する）

あわせて、M1 core を足しても**公開面が M0 のまま**であることを固定する。
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
SCHEMA_DIR = SKILL / "schemas"
REF_DIR = SKILL / "references"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import coordinator as C  # noqa: E402
from flowlib import durable as D  # noqa: E402
from flowlib import recovery as RC  # noqa: E402
from flowlib import result as R  # noqa: E402
from flowlib import sanitize as S  # noqa: E402

M0_OPERATIONS = ("repo.inspect", "git.status", "git.diff-summary")
M0_REACHABLE_CODES = {"OK", "INVALID_INPUT", "BLOCKED", "UNAVAILABLE", "STALE", "UNSUPPORTED"}


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def result_schema():
    return _schema("result-v1.schema.json")


@pytest.fixture(scope="module")
def intent_schema():
    return _schema("intent-record-v1.schema.json")


@pytest.fixture(scope="module")
def ledger_schema():
    return _schema("evidence-ledger-entry-v1.schema.json")


def _namespaces(result_schema, intent_schema, ledger_schema) -> dict[str, list[str]]:
    return {
        "code": result_schema["$defs"]["code"]["enum"],
        "write_state": result_schema["$defs"]["write_state"]["enum"],
        "intent_record_state": intent_schema["$defs"]["intent_record_state"]["enum"],
        "gate_status": ledger_schema["$defs"]["gate_status"]["enum"],
        "attempt_status": ledger_schema["$defs"]["attempt_status"]["enum"],
    }


def _check_object(obj: dict, schema: dict) -> None:
    """既存 test_flow_contract の流儀に合わせた最小の構造検査。"""
    required = set(schema["required"])
    allowed = set(schema["properties"])
    assert required <= set(obj), f"必須 key 不足: {sorted(required - set(obj))}"
    assert set(obj) <= allowed, f"契約外 key: {sorted(set(obj) - allowed)}"


# === 1. 契約表照合 ============================================================


def test_five_namespaces_are_separate_fields(result_schema, intent_schema, ledger_schema):
    ns = _namespaces(result_schema, intent_schema, ledger_schema)
    assert len(ns) == 5
    assert len(ns["write_state"]) == 9
    assert len(ns["intent_record_state"]) == 6
    assert len(ns["gate_status"]) == 3
    assert len(ns["attempt_status"]) == 5


def test_every_namespace_value_is_documented(result_schema, intent_schema, ledger_schema):
    """schema にあって output-contract.md に無い値を許さない。"""
    doc = (REF_DIR / "output-contract.md").read_text(encoding="utf-8")
    for name, values in _namespaces(result_schema, intent_schema, ledger_schema).items():
        missing = [v for v in values if v not in doc]
        assert not missing, f"{name} の値が文書化されていない: {missing}"


def test_guard_identity_kinds_agree_across_schemas(result_schema, intent_schema):
    a = result_schema["$defs"]["guard_identity_kind"]["enum"]
    b = intent_schema["$defs"]["guard_identity_kind"]["enum"]
    assert a == b
    doc = (REF_DIR / "output-contract.md").read_text(encoding="utf-8")
    for kind in a:
        assert kind in doc


def test_write_codes_are_a_subset_of_result_codes(result_schema):
    doc = (REF_DIR / "output-contract.md").read_text(encoding="utf-8")
    block = doc.split("write operation が返す `code` は次の7つに限る")[1]
    declared = {w for w in block.split("```")[1].split() if w.isupper()}
    assert len(declared) == 7
    assert declared <= set(result_schema["$defs"]["code"]["enum"])


def test_all_schemas_are_valid_json_with_stable_ids():
    ids = {}
    for path in sorted(SCHEMA_DIR.rglob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert "$id" in schema, path.name
        ids[path.name] = schema["$id"]
    assert ids["intent-record-v1.schema.json"] == "bitz-flow/intent-record/v1"
    assert ids["evidence-ledger-entry-v1.schema.json"] == "bitz-flow/evidence-ledger-entry/v1"


def test_intent_record_sample_matches_schema(intent_schema):
    sample = {
        "schema_version": 1,
        "operation_id": "op-1",
        "repo_identity": {"local_common_dir": R.sha256_of(b"r"), "remote_repository": None},
        "targets": [{"kind": "index", "canonical_key": "index:w1"}],
        "fencing_tokens": {"index:w1": 3},
        "snapshot_digest": R.sha256_of(b"s"),
        "expected_effect_digest": R.sha256_of(b"e"),
        "intent_record_state": "PENDING",
        "created_at": "2026-08-11T00:00:00Z",
        "owner_process": "proc-1",
        "receipt_digest": None,
        "previous_record_digest": None,
    }
    _check_object(sample, intent_schema)
    assert sample["intent_record_state"] in intent_schema["$defs"]["intent_record_state"]["enum"]
    assert sample["targets"][0]["kind"] in intent_schema["$defs"]["guard_identity_kind"]["enum"]


def test_ledger_entry_sample_matches_schema(ledger_schema):
    sample = {
        "ledger_schema": 1,
        "attempt_id": 1,
        "epoch_id": "e1",
        "evaluation_objective_id": "obj-1",
        "leader_epoch": 1,
        "fencing_token": 1,
        "platform": "claude",
        "operation": "git.commit",
        "compatibility_key": R.sha256_of(b"k"),
        "lease_id": "lease:e1:1",
        "eligibility_rule_id": "rule-1",
        "positive_control_ids": ["pc-1"],
        "oracle_digest": R.sha256_of(b"o"),
        "retryable_failure_codes": ["instrument-unavailable"],
        "retry_slot_nonce": "n-1",
        "attempt_status": "STARTED",
        "issued_at": "2026-08-11T00:00:00Z",
        "completed_at": None,
        "expires_at": "2026-08-12T00:00:00Z",
        "evidence_id": "ev-1",
        "previous_entry_digest": None,
    }
    _check_object(sample, ledger_schema)
    assert sample["platform"] in ledger_schema["properties"]["platform"]["enum"]


def test_recovery_matrix_and_catalog_agree_on_write_operations():
    catalog = (REF_DIR / "operation-catalog.md").read_text(encoding="utf-8")
    for operation in RC.WRITE_OPERATIONS:
        assert f"`{operation}`" in catalog


# === 2. 統合 fault ============================================================


class _Replica:
    def __init__(self, ack=True):
        self.ack = ack

    def append_wal(self, entry_bytes, digest):
        return self.ack


class _Store:
    def __init__(self):
        self._d = {}

    def read(self, key):
        return self._d.get(key, (None, 0))

    def compare_and_set(self, key, expected_version, value):
        _, version = self.read(key)
        if version != expected_version:
            return False
        self._d[key] = (value, version + 1)
        return True


class _Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


def test_no_commit_means_recovery_forbids_mutation(tmp_path):
    """durable が commit を返さない状況では、recovery も mutation を許さない。"""
    log = D.DurableLog(
        tmp_path / "intent", replica=_Replica(), step_hook=D.crash_after(D.STEP_TEMP_WRITTEN)
    )
    commit, failure = log.append({"operation_id": "op-1"})
    assert commit is None and failure.code == D.CODE_BLOCKED

    decision = RC.decide(
        operation="git.commit", phase="pre-object-save", code=RC.PENDING_INTENT
    )
    assert decision.recovery_class == RC.RECONCILE_ONLY
    assert RC.validate_next_actions(
        code="INDETERMINATE", next_actions=list(decision.allowed_next)
    ) is None, "reconcile 用の NEXT に mutation が混ざってはならない"


def test_blocked_coordinator_leads_to_human_stop(tmp_path):
    """coordinator が採番を拒んだ状態から自動で mutation へ進む経路が無い。"""
    coord = C.Coordinator(_Store(), _Clock(), epoch_id="e1", leader_epoch=1)
    failure = coord.begin_nonce("n1")
    assert failure is None
    reuse = coord.begin_nonce("n1")
    assert reuse.code == C.CODE_BLOCKED and reuse.indefinite

    decision = RC.decide(
        operation="git.commit", phase="pending-or-quarantine-exists", code="BLOCKED"
    )
    assert decision.stops and decision.allowed_next == ()


def test_crash_then_scan_then_decide_stays_safe(tmp_path):
    """crash → 走査 → 判定の一連で、副作用のない状態のまま停止する。"""
    root = tmp_path / "intent"
    D.DurableLog(root, replica=_Replica(), step_hook=D.crash_after(D.STEP_FILE_FSYNCED)).append(
        {"operation_id": "op-1"}
    )
    log = D.DurableLog(root, replica=_Replica())
    report, _ = log.scan()
    assert report.torn and report.entries == []

    decision = RC.decide(
        operation="git.commit", phase="reconcile-impossible", code="INDETERMINATE"
    )
    assert decision.stops
    assert decision.quarantine_target is True
    assert decision.required_human_input


def test_diagnostics_from_failures_carry_no_secrets(tmp_path):
    """失敗理由を診断へ載せるとき、絶対 path や生値が混ざらない。"""
    log = D.DurableLog(tmp_path / "x", replica=_Replica(ack=False))
    _, failure = log.append({"operation_id": "op-1"})
    diag = S.sanitize_diagnostic({"reason_code": "BLOCKED", "repo_path": str(tmp_path)})
    assert "repo_path" not in diag.values
    assert diag.redactions[0].kind == S.KIND_ABSOLUTE_PATH
    assert str(tmp_path) not in failure.reason


# === 3. 公開面の非退行 ========================================================


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("m1-core-repo")
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True)
    return path


def _flow(*args, repo):
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
    )
    return proc


def _flow_json(*args, repo):
    proc = _flow(*args, "--format", "json", repo=repo)
    return json.loads(proc.stdout), proc.returncode


@pytest.mark.parametrize("operation", M0_OPERATIONS)
def test_m0_operations_still_public(operation, repo):
    domain, action = operation.split(".")
    result, exit_code = _flow_json(domain, action, repo=repo)
    assert exit_code == 0
    assert result["operation"] == operation


@pytest.mark.parametrize(
    "flag", [("--apply",), ("--confirm", "op-1"), ("--approval-ref", "ref-1")]
)
def test_write_flags_remain_unsupported_without_side_effect(flag, repo):
    before = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout
    result, exit_code = _flow_json("git", "status", *flag, repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert exit_code == 8
    assert result["data"]["effects"] == []
    after = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout
    assert before == after


def test_m1_operations_are_not_public_yet(repo):
    for domain, action in (("git", "commit"), ("git", "fetch"), ("git", "stage"), ("repo", "doctor")):
        result, exit_code = _flow_json(domain, action, repo=repo)
        assert result["code"] == "UNSUPPORTED", f"{domain}.{action} は M1-1 で公開しない"
        assert exit_code == 8
        assert result["data"]["effects"] == []


def test_no_raw_command_is_proposed_for_unsupported(repo):
    proc = _flow("git", "commit", repo=repo)
    text = proc.stdout + proc.stderr
    for forbidden in ("git commit", "git push", "$ ", "shell"):
        assert forbidden not in text


def test_reachable_codes_are_still_m0_only(repo):
    seen = set()
    for args in (
        ("repo", "inspect"),
        ("git", "status"),
        ("git", "diff-summary"),
        ("git", "commit"),
        ("git", "status", "--limit", "-1"),
        ("git", "status", "--snapshot", "sha256:" + "0" * 64),
    ):
        result, _ = _flow_json(*args, repo=repo)
        seen.add(result["code"])
    assert seen <= M0_REACHABLE_CODES, f"M1-1 で新しい code に到達した: {seen - M0_REACHABLE_CODES}"


# === 4. 変異試験（検査の検出力）================================================


def test_mutation_removing_a_matrix_row_is_detected(monkeypatch):
    """決定表から1行削ると markdown との照合が落ちる。"""
    monkeypatch.setattr(RC, "MATRIX", RC.MATRIX[:-1])
    rows = [r.md_row for r in RC.MATRIX]
    md = (REF_DIR / "recovery-matrix.md").read_text(encoding="utf-8")
    declared = md.count("| `retry-read` |") + md.count("| `reconcile-only` |") \
        + md.count("| `replan-human` |") + md.count("| `human-stop` |")
    assert len(rows) != declared, "行を削ったのに件数が一致してしまう検査は検出力が無い"


def test_mutation_adding_enum_value_is_detected(result_schema, intent_schema, ledger_schema):
    """enum に未文書化の値を足すと照合が落ちる。"""
    doc = (REF_DIR / "output-contract.md").read_text(encoding="utf-8")
    mutated = list(result_schema["$defs"]["write_state"]["enum"]) + ["teleported"]
    missing = [v for v in mutated if v not in doc]
    assert missing == ["teleported"]


def test_mutation_disabling_sanitizer_is_detected(monkeypatch):
    """遮断パターンを1つ外すと負の対照が通ってしまうことを確認する。"""
    import re

    assert S.classify("a\x00b") == S.KIND_CONTROL_CHAR
    monkeypatch.setattr(S, "_CONTROL_CHARS", re.compile(r"(?!x)x"))
    assert S.classify("a\x00b") != S.KIND_CONTROL_CHAR, "変異が効いていない"


def test_mutation_skipping_dir_fsync_is_detected(tmp_path, monkeypatch):
    """directory fsync を省くと durability commit point の観測が変わる。"""
    fsync_calls = []
    real_fsync = os.fsync

    def spy(fd):
        fsync_calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spy)
    log = D.DurableLog(tmp_path / "a", replica=_Replica())
    commit, failure = log.append({"operation_id": "op-1"})
    assert failure is None and commit is not None
    baseline = len(fsync_calls)
    assert baseline >= 2, "file fsync と directory fsync の2回が観測できなければならない"

    fsync_calls.clear()
    monkeypatch.setattr(D.DurableLog, "_fsync_dir", lambda self: None)
    log2 = D.DurableLog(tmp_path / "b", replica=_Replica())
    log2.append({"operation_id": "op-2"})
    assert len(fsync_calls) < baseline, "dir fsync を省いたのに観測回数が変わらない"
