"""FLW-NFR-014 / FLW-TSK-114 operability integration tests."""

from __future__ import annotations

import ast
import json
import textwrap
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import worktree_operability as O  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

ORIGINAL = "sha256:" + "a" * 64
TARGET = "sha256:" + "b" * 64
BUNDLE = "sha256:" + "c" * 64


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-qm", "init")
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    observed = WR.RepositoryObserver(repo).snapshot()
    root = common / "bitz-flow-v2" / "transactions" / TARGET[7:]
    tx = T.TargetTransaction(root, target_collision_key=TARGET)
    lease = tx.acquire(operation_id=ORIGINAL, nonce="mutation")
    tx.prepare_intent(
        lease, planned_effects_digest=BUNDLE,
        precondition_digest=observed.digest,
    )
    tx.release(lease)
    P.register_active_operation(
        common, operation_id=ORIGINAL, bundle_digest=BUNDLE
    )
    return repo, common, tx


def invoke(repo, argv, capsys):
    handlers = {**cli._HANDLERS, **cli._GATED_HANDLERS}
    code = cli.main([*argv, "--repo", str(repo), "--format", "json"], handlers=handlers)
    payload = json.loads(capsys.readouterr().out)
    return code, payload


@pytest.mark.parametrize("action", ["doctor", "audit", "verify-receipt"])
def test_read_only_commands_leave_persistent_state_unchanged(repository, action, capsys):
    repo, common, _ = repository
    before = O.persistent_state_digest(common)
    args = ["worktree", action]
    if action != "doctor":
        args += ["--operation-id", ORIGINAL]
    _, payload = invoke(repo, args, capsys)
    after = O.persistent_state_digest(common)
    assert before == after
    assert payload["data"]["automatic_recovery_allowed"] is False
    assert payload["data"]["side_effect_state"] in {"none", "indeterminate"}
    assert payload["data"]["operator_action"]
    assert set(payload["data"]["journal_usage"]) == {
        "event_count", "receipt_count", "closure_count", "bytes",
    }


def test_audit_and_verify_receipt_use_recovery_and_transaction_chain(repository, capsys):
    repo, _, _ = repository
    code, audit = invoke(
        repo, ["worktree", "audit", "--operation-id", ORIGINAL], capsys
    )
    # `confirmed-incomplete` は復旧を要する。以前はこれを exit 0 / `OK` で返しながら
    # `create-reconcile-plan` を促しており、code と operator action が矛盾していた
    # （`FLW-REV-029:SYN-006`）。**復旧を要する分類は成功終了にしない。**
    assert code != 0
    assert audit["code"] == "INDETERMINATE"
    assert audit["data"]["operability"]["classification"] == "confirmed-incomplete"
    assert audit["data"]["operator_action"] == "create-reconcile-plan"
    code, verified = invoke(
        repo, ["worktree", "verify-receipt", "--operation-id", ORIGINAL], capsys
    )
    assert code == 0
    assert verified["data"]["operability"]["chain_valid"] is True


def test_reconcile_plan_and_apply_are_connected_through_dispatcher(repository, capsys):
    repo, _, tx = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    common = [
        "worktree", "reconcile", "--operation-id", ORIGINAL,
        "--decision", "confirmed-incomplete", "--expires-at", expires,
        "--nonce", "reconcile-nonce", "--bundle-digest", BUNDLE,
    ]
    code, planned = invoke(repo, common, capsys)
    assert code == 0 and planned["code"] == "READY"
    operation_id = planned["operation_id"]
    code, applied = invoke(
        repo, [*common, "--apply", "--confirm", operation_id], capsys
    )
    assert code == 0 and applied["code"] == "DONE"
    assert applied["data"]["side_effect_state"] == "closure-only"
    assert applied["data"]["operability"]["marker_released"] is True
    assert len(tx.inspect(ORIGINAL).closures) == 1


def test_reconcile_apply_without_confirmation_is_closed_stop(repository, capsys):
    repo, _, _ = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    code, payload = invoke(repo, [
        "worktree", "reconcile", "--operation-id", ORIGINAL,
        "--decision", "confirmed-incomplete", "--expires-at", expires,
        "--nonce", "reconcile-nonce", "--bundle-digest", BUNDLE, "--apply",
    ], capsys)
    assert code != 0
    for field in (
        "result_code", "cause_code", "side_effect_state",
        "automatic_recovery_allowed", "operator_action", "receipt_path",
        "journal_usage",
    ):
        assert field in payload["data"]
    assert payload["data"]["operator_action"] == "manual-inspection"


def test_reconcile_never_launches_git_mutation(repository, capsys, monkeypatch):
    repo, _, _ = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    planned = O.reconcile_plan(
        repo, operation_id=ORIGINAL, decision="confirmed-incomplete",
        expires_at=expires, nonce="one", bundle_digest=BUNDLE,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Git observation should have been injected before this boundary")

    # Reconcile receives a pre-bound observer; write-capable Git has no import path in operability.
    source = (SKILL / "scripts/flowlib/worktree_operability.py").read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "subprocess" not in imports
    assert planned.plan is not None


def test_signed_capability_is_immediately_rejected_on_public_dispatcher(tmp_path, capsys):
    code = cli.main([
        "worktree", "reconcile", "--capability-file", str(tmp_path / "old.json"),
        "--format", "json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 8
    assert payload["code"] == "UNSUPPORTED"
    assert payload["data"]["cause"] == "unsupported-approval-mode"
    assert "reason" not in payload["data"]


@pytest.mark.parametrize("signal", ["declaration", "trusted-registry"])
def test_retired_approval_configuration_is_rejected_without_downgrade(
    repository, signal, capsys,
):
    repo, common, _ = repository
    if signal == "declaration":
        path = repo / ".bitz-flow" / "approval-mode.json"
    else:
        path = common / "bitz-flow-v2" / "trusted-worktree-keys.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-consumed", encoding="utf-8")
    code, payload = invoke(repo, ["worktree", "doctor"], capsys)
    assert code == 8
    assert payload["data"]["cause"] == "unsupported-approval-mode"
    assert "not-consumed" not in json.dumps(payload)


def test_read_only_operability_commands_are_published(capsys):
    """read-only 3 件が公開集合にあり production 既定 dispatcher から到達すること。

    裁定 2026-08-24（`.spec/reports/decision-2026-08-24-m2-readonly-canary.md`）。
    到達したうえで入力不足や環境不備を返すのは正しい。`command-unavailable` で
    閉じられていないことが要点である。
    """
    for action in ("doctor", "audit", "verify-receipt"):
        assert ("worktree", action) in cli.PUBLISHED_OPERATIONS
        cli.main(["worktree", action, "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["data"].get("cause") != "command-unavailable", action


def test_write_operability_commands_remain_gated_in_production(capsys):
    """write を伴う operation は引き続き公開しないこと。

    `reconcile` は closure event を durable 追記するため read-only ではない。
    """
    expected = {"reconcile", "create", "resume", "finish", "discard"}
    assert expected <= {
        action for domain, action in cli._GATED_HANDLERS if domain == "worktree"
    }
    assert not any(
        ("worktree", action) in cli.PUBLISHED_OPERATIONS for action in expected
    )
    for action in expected:
        code = cli.main(["worktree", action, "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert code == 8 and payload["code"] == "UNSUPPORTED"
        assert payload["data"]["cause"] == "command-unavailable", action


def _coverage_manifest():
    return json.loads(
        (SKILL / "references/m2-operability-coverage.json").read_text(encoding="utf-8")
    )


def _coverage_entries():
    manifest = _coverage_manifest()
    return {**manifest["acceptance_rows"], **manifest["flow_edges"]}


def _calls_with_handler_injection(tree: ast.AST) -> bool:
    """この AST 内に `main(..., handlers=...)` 呼び出しがあるか。"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name == "main" and any(k.arg == "handlers" for k in node.keywords):
            return True
    return False


def _injects_handlers(module_source: str, func_name: str) -> bool:
    """test が（直接またはローカル helper 経由で）handler 注入を使うかを判定する。

    文字列一致だと `_GATED_HANDLERS` を集合比較に使うだけの test まで注入扱いに
    なる。一方、関数の body だけを見ると `_run()` のような helper 内の注入を
    見逃す（実際に見逃した）。そこで **module 内 helper を 1 階層だけ辿る**。
    """
    tree = ast.parse(module_source)
    functions = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    target = functions.get(func_name)
    if target is None:
        return False
    if _calls_with_handler_injection(target):
        return True
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        callee = getattr(node.func, "id", None)
        helper = functions.get(callee) if callee else None
        if helper is not None and _calls_with_handler_injection(helper):
            return True
    return False


def _resolve_test_id(test_id: str):
    """`file.py` / `file.py::func` を実体へ解決する。無ければ理由を返す。"""
    file_part, _, func = test_id.partition("::")
    path = ROOT / file_part
    if not path.exists():
        return None, f"file 不在 {test_id}"
    source = path.read_text(encoding="utf-8")
    if not func:
        return source, None
    tree = ast.parse(source)
    node = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func),
        None,
    )
    if node is None:
        return None, f"関数不在 {test_id}"
    return ast.get_source_segment(source, node) or "", None


def test_coverage_manifest_covers_every_acceptance_row_and_flow_edge():
    manifest = _coverage_manifest()
    assert set(manifest["acceptance_rows"]) == {
        "plan-state-change", "lock-contention", "pre-intent-storage",
        "post-intent-pre-child-crash", "child-unknown", "postcondition-pre-terminal",
        "terminal-pre-marker-release", "journal-corruption", "promotion-failure",
        "readonly-invariance", "reconcile-retry", "unsupported-environment-or-approval",
    }
    assert set(manifest["flow_edges"]) == {
        "plan", "apply-start", "git-mutation", "apply-end", "audit",
        "verify-receipt", "reconcile", "promotion", "startup-gate",
    }
    for name, entry in _coverage_entries().items():
        assert entry["production"] or entry["fixture"], f"{name}: test が 1 件も無い"


def test_coverage_manifest_only_cites_tests_that_exist():
    """名指しした test の実在を検査する（`SI-FLW-090`）。

    以前はキーの網羅と値の非空しか見ておらず、**実在しない test 名でも coverage を
    主張できた**。証跡が実体を伴わないまま緑に見える典型である。
    """
    problems = []
    for name, entry in _coverage_entries().items():
        for test_id in entry["production"] + entry["fixture"]:
            _, reason = _resolve_test_id(test_id)
            if reason:
                problems.append(f"{name}: {reason}")
    assert not problems, f"coverage manifest が実体の無い test を名指ししている: {problems}"


def test_coverage_manifest_declares_a_known_connection_kind():
    """各 entry が fixture 内部の検証か production 経路の実証かを宣言すること。"""
    manifest = _coverage_manifest()
    kinds = set(manifest["connection_kinds"])
    assert kinds == {"production", "fixture"}
    for name, entry in _coverage_entries().items():
        assert entry["connection"] in kinds, f"{name}: connection 宣言が未知"
        expected = "production" if entry["production"] else "fixture"
        assert entry["connection"] == expected, (
            f"{name}: connection 宣言が production list と食い違う"
        )


def test_production_coverage_names_functions_not_whole_files():
    """production 主張は **関数単位** で名指しすること。

    file 単位だと、その file に production test が 1 件あるだけで行全体が
    production 扱いになり、過大主張が再現する。
    """
    coarse = [
        f"{name}: {test_id}"
        for name, entry in _coverage_entries().items()
        for test_id in entry["production"]
        if "::" not in test_id
    ]
    assert not coarse, f"production 主張が file 単位になっている: {coarse}"


def test_production_coverage_never_relies_on_fixture_injection():
    """`production` 宣言の test が handler 注入を使わず、production 入口を通ること。

    `cli.main(handlers=...)` は fixture 専用の注入口であり（`SI-FLW-059`）、
    production 既定 dispatcher からの到達を証明しない。
    """
    problems = []
    for name, entry in _coverage_entries().items():
        for test_id in entry["production"]:
            _, reason = _resolve_test_id(test_id)
            if reason:
                continue                      # 実在検査は別 test の責務
            file_part, _, func = test_id.partition("::")
            module_source = (ROOT / file_part).read_text(encoding="utf-8")
            if func and _injects_handlers(module_source, func):
                problems.append(f"{name}: {test_id} が fixture 注入を使用")
    assert not problems, f"production 宣言が fixture 注入に依存している: {problems}"