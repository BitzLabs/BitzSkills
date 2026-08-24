"""単一 dispatcher の CLI 層（FLW-DSN-003 公開入口）。

入力を canonical 化し、adapter から事実を取得し、renderer へ渡す。
M0 read-onlyとM2 worktreeのplan-digest付きplan/applyを扱う。

未対応の domain / action は ``UNSUPPORTED``（exit 8）で停止し、生の ``git`` /
``gh`` コマンドを代替案として出力しない（references/operation-catalog.md）。
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import os
import sys
from typing import Any, Mapping, Sequence

from . import (
    __version__, git_read, result as R, worktree_cleanup,
    worktree_operability, worktree_recovery, worktree_runtime,
)

# 公開 operation の SSOT。ここに無い組み合わせは UNSUPPORTED。
#
# 現在の出荷面は **M0 read-only の 3 operation だけ**である（裁定 2026-08-15、
# `.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`）。
# M2 worktree の安全核と runtime adapter は実装済みだが、M2 出口が未達（`FLW-REV-016` FAIL）の
# 間は ROADMAP の縮退規則3 に従って公開しない。ゲート通過時にここへ戻す。
PUBLISHED_OPERATIONS = {
    ("repo", "inspect"),
    ("git", "status"),
    ("git", "diff-summary"),
}

# 公開予定だが当該 milestone まで未対応の operation（UNSUPPORTED の理由付けに使う）。
KNOWN_DOMAINS = {"repo", "git", "worktree", "issue", "pr", "release"}

DEFAULT_ITEM_LIMIT = 50


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Parser(argparse.ArgumentParser):
    """引数エラーでも公開契約に沿った result を返す。

    argparse 既定の exit code 2 は output-contract の ``INVALID_INPUT`` と一致する。
    """

    def error(self, message: str) -> None:  # noqa: D401 - argparse の契約に合わせる
        fmt = "json" if "--format=json" in sys.argv or _format_from_argv() == "json" else "compact"
        _emit(
            _simple_result(
                operation="flow.invalid-input",
                code="INVALID_INPUT",
                repo=os.getcwd(),
                summary="引数を解釈できない",
                cause="invalid-path",
                stage="validate",
            ),
            fmt,
        )
        raise SystemExit(2)


def _format_from_argv() -> str:
    argv = sys.argv
    for index, token in enumerate(argv):
        if token == "--format" and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith("--format="):
            return token.split("=", 1)[1]
    return "compact"


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="flow.py",
        description="bitz-flow の唯一の公開実行入口（M0: read-only の3 operation）。",
        epilog="未対応の operation は UNSUPPORTED で停止する。生コマンドの代替案は提示しない。",
    )
    parser.add_argument("domain", help="操作ドメイン（repo / git / worktree / issue / pr / release）")
    parser.add_argument("action", help="操作アクション（例: inspect / status / diff-summary）")
    parser.add_argument("--repo", help="対象リポジトリのパス（省略時は current directory から解決）")
    parser.add_argument(
        "--format", choices=("compact", "json"), default="compact", help="出力形式（既定 compact）"
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=None, help="read の timeout 秒（1〜300、既定 30）"
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        # 「比較元」とだけ書くと git diff A B 型の ref..ref 比較と読まれ、
        # 「直前のコミットからの変更」を HEAD~1 と解釈されて invalid-ref で落ちる（SI-FLW-028）。
        help=(
            "git diff-summary の比較対象。作業ツリーを <base> と比較する"
            "（既定 HEAD ＝ 直前のコミット以降の変更）。ref..ref の比較ではないため "
            "HEAD~1 等を渡す必要はない。index と比較するなら --base index"
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_ITEM_LIMIT, help="items の表示上限（既定 50）"
    )
    parser.add_argument("--snapshot", help="期待する snapshot。一致しなければ STALE を返す")
    # M0 は read-only。状態変更系の引数は受理して UNSUPPORTED を返す（黙殺しない）。
    parser.add_argument("--apply", action="store_true", help="状態変更の実行（M1 以降）")
    parser.add_argument("--confirm", help="plan が返した operation_id（M1 以降）")
    parser.add_argument("--approval-ref", dest="approval_ref", help="外部裁定への参照（M1 以降）")
    # worktree 系の引数は受理するが、operation 自体が M2 出口通過まで UNSUPPORTED である
    # （裁定 2026-08-15）。黙殺せず受理して UNSUPPORTED を返すのは M0 の read-only 系と同じ扱い。
    gated = "（worktree は M2 出口通過まで UNSUPPORTED）"
    parser.add_argument("--path", help=f"worktree path{gated}")
    parser.add_argument("--branch", help=f"worktree branch{gated}")
    parser.add_argument("--worktree-root", dest="worktree_root", help=f"承認済みworktree root{gated}")
    parser.add_argument("--start-point", default="HEAD", help=f"worktree.createの開始ref{gated}")
    parser.add_argument("--default-branch", default="main",
                        help=f"finish到達性を確認するdefault branch{gated}")
    parser.add_argument("--capability-file", help=f"署名済み単回capability JSON{gated}")
    parser.add_argument("--backup-receipt", action="store_true",
                        help=f"dirty内容を退避済みであることを提示{gated}")
    parser.add_argument("--operation-id", help=f"audit/reconcile対象のoperation ID{gated}")
    parser.add_argument("--decision", choices=(
        "confirmed-complete", "confirmed-incomplete", "quarantine",
    ), help=f"reconcileで明示する人間判断{gated}")
    parser.add_argument("--expires-at", help=f"reconcile planのRFC3339 UTC期限{gated}")
    parser.add_argument("--nonce", help=f"reconcile planの単回nonce{gated}")
    parser.add_argument("--bundle-digest", help=f"reconcile対象contract bundle digest{gated}")
    return parser


# apply() の RuntimeDecision は構造化 cause を持たないため、decision.code から
# 一意に決まる粗い分類を使う（`FLW-TSK-100`）。PARTIAL/STALE は recovery_for の
# 既登録 tuple と一致させ、reconcile-only / replan-human を引けるようにする。
_APPLY_FAILURE_CAUSE = {
    "PARTIAL": "step-interrupted",
    "STALE": "snapshot-mismatch",
    "BLOCKED": "conflict",
    "UNSUPPORTED": "command-unavailable",
}


# --- result の組み立て -------------------------------------------------------


def _simple_result(
    *,
    operation: str,
    code: str,
    repo: str,
    summary: str,
    cause: str | None = None,
    stage: str = "inspect",
    next_actions: Sequence[dict] = (),
    required_human_input: str | None = None,
) -> dict[str, Any]:
    """`build_result` の非ok契約（cause/recovery_class/next_actions）を自動で満たす。

    `recovery_class` は `worktree_cleanup.recovery_for(code, cause)` から決定する
    （matrix を引かずに手で置かない。`FLW-DSN-016` §8）。未登録の組合せは
    fail-closed に `human-stop` へ倒れるため、呼出側が明示的に `next_actions` を
    渡さない限り既定で安全側になる。
    """
    data = R.empty_data()
    data["cause"] = cause
    if R.CODE_EXIT_CODES[code] != 0:
        recovery_class = worktree_cleanup.recovery_for(code, cause).recovery_class
        data["recovery_class"] = recovery_class
        if recovery_class == "human-stop":
            next_actions = ()
            data["required_human_input"] = required_human_input or summary
    now = _now()
    return R.build_result(
        operation=operation,
        code=code,
        repo=repo,
        tool_version=__version__,
        started_at=now,
        finished_at=now,
        summary=summary,
        data=data,
        stage=stage,
        next_actions=next_actions,
    )


def _emit(result: dict[str, Any], fmt: str, view: R.CompactView | None = None) -> int:
    print(R.render(result, fmt, view))
    return result["exit_code"]


def _short_sha(sha: str | None) -> str | None:
    return sha[:7] if sha else None


# --- operation 実装 ----------------------------------------------------------


def _op_repo_inspect(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    facts, failure = git_read.inspect(root, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("repo.inspect", root, failure, started), R.CompactView()

    values = facts.values
    snapshot = R.snapshot_of([values["head"], values["branch"], values["upstream"], values["dirty"]])
    data = R.empty_data()
    data["target"] = {"repo_root": root}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["repo root", "HEAD", "branch", "upstream", "remote identity"]
    data["repository"] = values

    result = R.build_result(
        operation="repo.inspect",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=_inspect_summary(values),
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        # snapshot は operation ごとに観測対象が違うため、別 operation へ引き渡すと必ず
        # snapshot-mismatch になる。NEXT が snapshot を載せるのは「次も同じ operation」
        # のとき（ページング）だけとする（SI-FLW-011）。
        next_actions=[R.next_action("git", "status")],
    )
    view = R.CompactView(
        tokens={
            "branch": values["branch"] or ("detached" if values["head"]["detached"] else None),
            "head": _short_sha(values["head"]["sha"]),
            "upstream": values["upstream"],
            "dirty": values["dirty"],
            "remotes": len(values["remotes"]),
        },
        normal=[f"remote {r['name']} {r['host'] or '-'}/{r['owner'] or '-'}/{r['repo'] or '-'}"
                for r in values["remotes"]],
    )
    return result, view


def _inspect_summary(values: dict) -> str:
    branch = values["branch"] or "detached HEAD"
    state = "dirty" if values["dirty"] else "clean"
    return f"{branch} が {state}"


def _op_git_status(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    facts, failure = git_read.status(root, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("git.status", root, failure, started), R.CompactView()

    values = facts.values
    branch, counts, items = values["branch"], values["counts"], values["items"]
    snapshot = R.snapshot_of([branch, items])
    shown, page, truncated = R.paginate(items, args.limit, snapshot)

    data = R.empty_data()
    data["target"] = {"repo_root": root}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["branch", "upstream", "ahead/behind", "変更種別ごとの件数"]
    data["branch"] = branch
    data["counts"] = counts
    data["items"] = shown
    data["page"] = page

    changed_total = counts["staged"] + counts["unstaged"] + counts["untracked"] + counts["conflicted"]
    # base を明示して渡す。省略すると呼出側が「直前のコミットからの差分」を意図しながら
    # index 比較を呼び、rename を取りこぼす（FLW-DSN-010 の next action 改善）。
    # diff-summary は git.status とは別の事実（range + items）を観測するため snapshot が
    # 一致しない。別 operation への NEXT には載せない（SI-FLW-011）。
    next_actions = [R.next_action("git", "diff-summary", base="HEAD")]
    if truncated:
        # ページングは同一 operation なので snapshot が一致する。打ち切られた一覧を辿る間の
        # 変更を検出できる唯一の場面であり、ここは温存する（SI-FLW-011）。
        next_actions.insert(0, R.next_action("git", "status", limit=page["total"], snapshot=snapshot))

    result = R.build_result(
        operation="git.status",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=f"{changed_total} 件の変更",
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        truncated=truncated,
        next_actions=next_actions,
    )
    conflicted = [f"{item['xy']} {item['path']}" for item in shown if item["state"] == "conflicted"]
    others = [
        f"{item['xy']} {item['path']}"
        + (f" <- {item['orig_path']}" if item["orig_path"] else "")
        for item in shown
        if item["state"] != "conflicted"
    ]
    view = R.CompactView(
        tokens={
            "branch": branch["name"] or ("detached" if branch["detached"] else None),
            "changed": changed_total,
            "ahead": branch["ahead"],
            "behind": branch["behind"],
        },
        blocking=conflicted,
        changed=others,
    )
    return result, view


def _op_git_diff_summary(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    # 既定は HEAD（「直前のコミットからの変更量」が既定の意図）。生 git の `git diff` は
    # index 比較だが、dispatcher はエージェントの意図側に既定を寄せる。index 比較は
    # `--base index` で明示する（git_read は base=None を index 比較として扱う）。
    base = None if args.base == "index" else args.base
    facts, failure = git_read.diff_summary(root, base=base, timeout_seconds=args.timeout_seconds)
    if failure:
        return _failure_result("git.diff-summary", root, failure, started), R.CompactView()

    values = facts.values
    totals, items = values["totals"], values["items"]
    snapshot = R.snapshot_of([values["range"], items])
    shown, page, truncated = R.paginate(items, args.limit, snapshot)

    data = R.empty_data()
    data["target"] = {"repo_root": root, "range": values["range"]}
    data["postconditions"] = ["snapshot 付き result を返した"]
    data["evidence"] = ["変更件数", "path", "変更種別", "追加削除行数", "binary 判定"]
    data["totals"] = totals
    data["items"] = shown
    data["page"] = page

    next_actions = []
    if truncated:
        next_actions.append(
            R.next_action(
                "git", "diff-summary", base=args.base, limit=page["total"], snapshot=snapshot
            )
        )

    result = R.build_result(
        operation="git.diff-summary",
        code="OK",
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=f"{totals['files']} files changed",
        snapshot=snapshot,
        data=data,
        warnings=facts.warnings,
        truncated=truncated,
        next_actions=next_actions,
    )
    lines = []
    for item in shown:
        counts = "binary" if item["binary"] else f"+{item['added']} -{item['deleted']}"
        rename = f" <- {item['orig_path']}" if item["orig_path"] else ""
        lines.append(f"{item['kind'][:1].upper()} {item['path']} {counts}{rename}")
    view = R.CompactView(
        tokens={
            "base": values["range"]["base"],
            "files": totals["files"],
            "added": totals["added"],
            "deleted": totals["deleted"],
            "binary": totals["binary"],
        },
        changed=lines,
    )
    return result, view


def _classify_divergent_target(
    root: str,
    row: Mapping[str, Any],
    *,
    receipt_records: tuple[dict, ...],
    registry: Mapping[str, str | None],
) -> dict[str, Any]:
    """1 target 分の §6/§7 分類を実観測から算出し `data.quarantine.targets` の1件を返す。

    `chain_valid=True` を固定するのは、呼出元（`worktree.audit`）が既に
    `survey.readable` を確認したうえでこの関数へ到達しているため（store 全体が
    読めない場合は audit がここへ来る前に `INDETERMINATE` を返す）。
    """
    from pathlib import Path as _Path

    path = row["path"]
    target_records = tuple(
        record for record in receipt_records
        if (record.get("target") or {}).get("path") == path
    )
    branch = (target_records[-1].get("target") or {}).get("branch") if target_records else None
    ref_exists = False
    if branch:
        proc = worktree_runtime._git(
            _Path(root), "rev-parse", "--verify", f"refs/heads/{branch}", check=False
        )
        ref_exists = proc.returncode == 0
    # instance identity の再照合（§5）はここでは HEAD OID 一致だけに限る。§5 が求める
    # 4要素（registry gitdir / .git file entry / HEAD OID / create 時 nonce）のうち
    # 後者3つは receipt log に永続化されておらず、本 boundary（worktree_runtime.py
    # 不可変更）では再導出できない（既知の残余限界。要 spec-issue）。
    expected_head = (
        (target_records[-1].get("target") or {}).get("expected_head") if target_records else None
    )
    observed_head = registry.get(path)
    instance_nonce_matches = bool(
        target_records and expected_head is not None and observed_head is not None
        and expected_head == observed_head
    )
    release_class, undetermined_reason = worktree_cleanup.classify_quarantine_target(
        chain_valid=True,
        records=target_records,
        directory_exists=row["present"],
        registry_exists=row["registered"],
        ref_exists=ref_exists,
        instance_nonce_matches=instance_nonce_matches,
    )
    return {
        "path": path,
        "divergence": row["divergence"],
        "release_class": release_class,
        "undetermined_reason": undetermined_reason,
    }


def _operability_result(root: str, started: str, decision,
                        *, operation: str) -> tuple[dict, R.CompactView]:
    data = R.empty_data()
    data.update({
        "result_code": decision.code,
        "cause_code": decision.cause,
        "side_effect_state": decision.side_effect_state,
        "automatic_recovery_allowed": False,
        "operator_action": decision.operator_action,
        "receipt_path": decision.receipt_path,
        "journal_usage": decision.journal_usage.as_mapping(),
        "operability": decision.details,
    })
    next_actions: Sequence[dict] = ()
    if R.CODE_EXIT_CODES[decision.code] != 0:
        data["cause"] = decision.cause
        recovery = worktree_cleanup.recovery_for(decision.code, decision.cause)
        data["recovery_class"] = recovery.recovery_class
        data["required_human_input"] = decision.operator_action
    result = R.build_result(
        operation=operation,
        code=decision.code,
        repo=root,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=decision.summary,
        snapshot=decision.details.get("persistent_state_digest"),
        operation_id=decision.operation_id,
        approval_required="explicit-human" if decision.code in {"READY", "DONE"} else None,
        approval_source="plan-digest" if decision.code == "DONE" else None,
        stage="apply" if decision.code == "DONE" else "inspect",
        data=data,
        next_actions=next_actions,
    )
    return result, R.CompactView(tokens={
        "code": decision.code,
        "action": decision.operator_action,
        "events": decision.journal_usage.event_count,
        "receipts": decision.journal_usage.receipt_count,
        "bytes": decision.journal_usage.bytes,
    })


def _operability_failure(root: str, started: str, operation: str,
                         *, code: str, cause: str, summary: str):
    public_code = {
        "BLOCKED_LOCK_BUSY": "BLOCKED",
        "BLOCKED_STORAGE": "BLOCKED",
        "UNSUPPORTED_FILESYSTEM": "UNSUPPORTED",
    }.get(code, code)
    public_cause = {
        "BLOCKED_LOCK_BUSY": "conflict",
        "BLOCKED_STORAGE": "permission-denied",
        "UNSUPPORTED_FILESYSTEM": "unsupported-filesystem",
        "STALE": "snapshot-mismatch",
        "INDETERMINATE": "result-indeterminate",
    }.get(code, cause)
    recovery = worktree_cleanup.recovery_for(public_code, public_cause)
    data = R.empty_data()
    data.update({
        "cause": public_cause,
        "recovery_class": recovery.recovery_class,
        "result_code": public_code,
        "cause_code": public_cause,
        "side_effect_state": "indeterminate",
        "automatic_recovery_allowed": False,
        "operator_action": "manual-inspection",
        "receipt_path": None,
        "journal_usage": {
            "event_count": 0, "receipt_count": 0, "closure_count": 0, "bytes": 0,
        },
    })
    next_actions: Sequence[dict] = ()
    if recovery.recovery_class == "human-stop":
        data["required_human_input"] = "manual-inspection"
    else:
        action = operation.split(".", 1)[1]
        next_actions = [R.next_action("worktree", action)]
    result = R.build_result(
        operation=operation, code=public_code, repo=root, tool_version=__version__,
        started_at=started, finished_at=_now(), summary=summary, data=data,
        stage="apply" if operation == "worktree.reconcile" else "inspect",
        next_actions=next_actions,
    )
    return result, R.CompactView(tokens={"code": public_code, "action": "manual-inspection"})


def _legacy_approval_detected(root: str, args) -> bool:
    """廃止済み承認方式の入力を、**内容を解析せず**検出する（`SI-FLW-085`）。

    M2 の承認契約は plan-digest に一本化されている（`FLW-DSN-017` §2）。
    旧 signed-capability の宣言・capability file・trusted key registry は、
    いずれも mutation 前にここで閉じる。検出は存在の有無だけで行い、内容を読んで
    妥当性を判定したり plan-digest へ暗黙に降格したりしない。
    """
    return bool(args.capability_file or worktree_operability.has_unsupported_approval_input(root))


def _op_worktree_operability(root: str, args, started: str):
    operation = f"worktree.{args.action}"
    if _legacy_approval_detected(root, args):
        return _operability_failure(
            root, started, operation, code="UNSUPPORTED", cause="unsupported-approval-mode",
            summary="この承認方式はサポートされていない",
        )
    try:
        if args.action == "doctor":
            decision = worktree_operability.doctor(root)
        else:
            if not args.operation_id:
                return _operability_failure(
                    root, started, operation, code="INVALID_INPUT", cause="invalid-path",
                    summary="--operation-id is required",
                )
            if args.action == "audit":
                decision = worktree_operability.audit_operation(
                    root, operation_id=args.operation_id
                )
            elif args.action == "verify-receipt":
                decision = worktree_operability.verify_receipt(
                    root, operation_id=args.operation_id
                )
            else:
                if not (args.decision and args.expires_at and args.nonce):
                    return _operability_failure(
                        root, started, operation, code="INVALID_INPUT", cause="invalid-path",
                        summary="--decision, --expires-at and --nonce are required",
                    )
                planned = worktree_operability.reconcile_plan(
                    root,
                    operation_id=args.operation_id,
                    decision=args.decision,
                    expires_at=args.expires_at,
                    nonce=args.nonce,
                    bundle_digest=args.bundle_digest,
                )
                if not args.apply:
                    decision = planned
                elif not args.confirm:
                    return _operability_failure(
                        root, started, operation, code="APPROVAL_REQUIRED", cause=None,
                        summary="--confirm <reconcile operation_id> is required",
                    )
                else:
                    decision = worktree_operability.reconcile_apply(
                        root,
                        plan=planned.plan,
                        confirm=args.confirm,
                        now=_dt.datetime.now(_dt.timezone.utc),
                        timeout_seconds=args.timeout_seconds or 0.0,
                    )
        return _operability_result(root, started, decision, operation=operation)
    except worktree_operability.OperabilityError as exc:
        return _operability_failure(
            root, started, operation, code=exc.code, cause=exc.cause, summary=exc.summary,
        )
    except worktree_recovery.RecoveryError as exc:
        return _operability_failure(
            root, started, operation, code=exc.code,
            cause="result-indeterminate", summary=exc.cause,
        )
    except (OSError, ValueError, KeyError) as exc:
        return _operability_failure(
            root, started, operation, code="INDETERMINATE",
            cause="result-indeterminate", summary=f"operability contract error: {type(exc).__name__}",
        )


def _op_worktree(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    operation = f"worktree.{args.action}"
    if args.action in {"doctor", "audit", "verify-receipt", "reconcile"}:
        return _op_worktree_operability(root, args, started)
    # `audit` は上の operability 委譲で処理済みである。以前ここにあった registry 走査は
    # 到達不能なまま legacy `worktree_capability` を production handler から参照していた
    # ため除去した（`SI-FLW-085`）。
    missing = [name for name, value in (
        ("--path", args.path), ("--branch", args.branch), ("--worktree-root", args.worktree_root)
    ) if not value]
    if missing:
        return _simple_result(
            operation=operation, code="INVALID_INPUT", repo=root,
            summary="worktree input missing: " + ", ".join(missing),
            cause="invalid-path", stage="validate",
        ), R.CompactView()
    try:
        plan_value = worktree_runtime.plan(
            root, action=args.action, path=args.path, branch=args.branch,
            worktree_root=args.worktree_root, start_point=args.start_point,
            default_branch=args.default_branch,
            # budget を渡さないと worktree 経路の child だけ無期限になる（`SI-FLW-086`）。
            timeout_seconds=args.timeout_seconds,
        )
    except worktree_runtime.WorktreeChildTimeoutError as exc:
        # 終了を証明できない child は「失敗」ではない。副作用の有無が不明なので
        # `INDETERMINATE` へ閉じる（`FLW-DSN-017` §13.2）。
        data = R.empty_data()
        data["cause"] = "result-indeterminate"
        data["evidence"] = [exc.command, exc.cause]
        result = R.build_result(
            operation=operation, code="INDETERMINATE", repo=root, tool_version=__version__,
            started_at=started, finished_at=_now(), summary=str(exc),
            data=data, stage="plan",
        )
        return result, R.CompactView(tokens={"child": "timeout"})
    except worktree_runtime.WorktreeUnsupportedPlatformError as exc:
        # 環境が対象外であることを `BLOCKED / conflict` へ丸めない。運用者は
        # 「競合で止まった」のか「この filesystem では動かない」のかを区別できる
        # 必要がある（`SI-FLW-084`）。理由は closed evidence をそのまま載せる。
        data = R.empty_data()
        data["cause"] = "unsupported-filesystem"
        data["evidence"] = list(exc.reasons)
        result = R.build_result(
            operation=operation, code="UNSUPPORTED", repo=root, tool_version=__version__,
            started_at=started, finished_at=_now(), summary=str(exc),
            data=data, stage="plan",
        )
        return result, R.CompactView(tokens={"platform": "unsupported"})
    except worktree_runtime.WorktreeRuntimeError as exc:
        return _simple_result(
            operation=operation, code="BLOCKED", repo=root, summary=str(exc),
            cause="conflict", stage="plan",
        ), R.CompactView()

    # M2 の承認は plan-digest に一本化した（`FLW-DSN-017` §2、`SI-FLW-085`）。
    # 旧 signed-capability の宣言・capability file・trusted key registry は、内容を解析せず
    # mutation 前に閉じる。ここで降格させると、人間はどちらの承認を求められているか判らない。
    if _legacy_approval_detected(root, args):
        return _simple_result(
            operation=operation, code="UNSUPPORTED", repo=root,
            summary="この承認方式はサポートされていない",
            cause="unsupported-approval-mode", stage="validate",
        ), R.CompactView()

    preconditions = [
        "plan snapshot一致",
        "operation_id一致とoperation_id由来の単回nonce",
    ]
    data = R.empty_data()
    data.update({
        "target": {"path": plan_value.path, "branch": plan_value.branch},
        "preconditions": preconditions,
        "effects": list(plan_value.effects),
        "postconditions": ["worktree/branch/receiptを再観測して一致"],
        "concurrency_key": plan_value.context.target_collision_key,
        "evidence": ["operation_id", "snapshot", "receipt digest"],
        "capability_context": dataclasses.asdict(plan_value.context),
        "approval_mode": worktree_runtime.C.MODE_PLAN_DIGEST,
    })
    if not args.apply:
        result = R.build_result(
            operation=operation, code="READY", repo=root, tool_version=__version__,
            started_at=started, finished_at=_now(), summary="worktree plan ready",
            snapshot=plan_value.snapshot, operation_id=plan_value.operation_id,
            approval_required="explicit-human", approval_reference=args.approval_ref,
            stage="plan", data=data,
        )
        return result, R.CompactView(tokens={"action": args.action, "branch": args.branch})
    if not args.confirm:
        return _simple_result(
            operation=operation, code="APPROVAL_REQUIRED", repo=root,
            summary="--confirm are required", stage="validate",
        ), R.CompactView()
    try:
        decision = worktree_runtime.apply(
            plan_value, confirm=args.confirm, capability=None,
            backup_receipt=args.backup_receipt,
        )
    except (OSError, ValueError, KeyError, worktree_runtime.WorktreeRuntimeError) as exc:
        return _simple_result(
            operation=operation, code="BLOCKED", repo=root, summary=str(exc),
            cause="conflict", stage="apply",
        ), R.CompactView()
    data["completed_steps"] = list(decision.completed_steps)
    data["remaining_steps"] = list(decision.remaining_steps)
    data["evidence"] = list(decision.evidence)
    apply_next_actions: Sequence[dict] = ()
    if decision.code != "DONE":
        # 非ok の cause は decision.code から一意に決まる粗い分類である
        # （`RuntimeDecision` は構造化 cause を持たず summary の自由文しか無いため。
        # 細分類には worktree_runtime.py 側の変更が要り本タスクの boundary 外）。
        cause = _APPLY_FAILURE_CAUSE[decision.code]
        data["cause"] = cause
        recovery = worktree_cleanup.recovery_for(decision.code, cause)
        data["recovery_class"] = recovery.recovery_class
        if recovery.recovery_class == "human-stop":
            data["required_human_input"] = decision.summary
        elif decision.code == "PARTIAL":
            # reconcile-only — 残 step の自動 apply はしない。read-only reconcile
            # として worktree.audit を提示する（recovery-matrix.md の許可 NEXT）。
            apply_next_actions = [R.next_action("worktree", "audit")]
        elif decision.code == "STALE":
            # replan-human — 旧 operation ID を再利用せず、同じ action を新規 plan する。
            apply_next_actions = [R.next_action("worktree", args.action)]
    result = R.build_result(
        operation=operation, code=decision.code, repo=root, tool_version=__version__,
        started_at=started, finished_at=_now(), summary=decision.summary,
        snapshot=plan_value.snapshot, operation_id=plan_value.operation_id,
        approval_required="explicit-human",
        # 承認の由来は実際に使ったモードを名乗る（`SI-FLW-063` / `OPS-303`）。
        # M2 は plan-digest 一本であり、signed-capability を名乗ることはない。
        approval_source=worktree_runtime.C.MODE_PLAN_DIGEST,
        approval_reference=args.approval_ref, stage="apply", data=data,
        next_actions=apply_next_actions,
    )
    return result, R.CompactView(tokens={"action": args.action, "code": decision.code})


def _failure_result(operation: str, repo: str, failure, started: str) -> dict:
    """adapter の失敗を公開 result へ写す（cause と stage だけを載せる）。"""
    code = "UNAVAILABLE"
    if failure.cause in ("not-repository", "invalid-path", "invalid-ref"):
        code = "INVALID_INPUT"
    summary = "操作を完了できない"
    data = R.empty_data()
    data["cause"] = failure.cause
    recovery_class = worktree_cleanup.recovery_for(code, failure.cause).recovery_class
    data["recovery_class"] = recovery_class
    if recovery_class == "human-stop":
        data["required_human_input"] = summary
    return R.build_result(
        operation=operation,
        code=code,
        repo=repo,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary=summary,
        data=data,
        stage=failure.stage,
    )


_HANDLERS = {
    ("repo", "inspect"): _op_repo_inspect,
    ("git", "status"): _op_git_status,
    ("git", "diff-summary"): _op_git_diff_summary,
}

#: M2 出口が閉じたときに `_HANDLERS` へ戻す handler（実装は残すが今は公開しない）。
_GATED_HANDLERS = {
    ("worktree", "doctor"): _op_worktree,
    ("worktree", "audit"): _op_worktree,
    ("worktree", "verify-receipt"): _op_worktree,
    ("worktree", "reconcile"): _op_worktree,
    ("worktree", "create"): _op_worktree,
    ("worktree", "resume"): _op_worktree,
    ("worktree", "finish"): _op_worktree,
    ("worktree", "discard"): _op_worktree,
}

if set(_HANDLERS) != PUBLISHED_OPERATIONS:
    # 宣言（PUBLISHED_OPERATIONS）と実体（_HANDLERS）の二重定義で乖離させない
    # （`FLW-REV-016:SYN-016`）。import 時に落として出荷面のズレを検出する。
    raise RuntimeError(
        "公開集合の宣言と dispatcher の実体が一致しない: "
        f"{sorted(PUBLISHED_OPERATIONS ^ set(_HANDLERS))}"
    )


# --- dispatcher --------------------------------------------------------------


def main(argv: Sequence[str] | None = None, *, handlers: Mapping | None = None) -> int:
    """公開実行入口。

    `handlers` は fixture 専用の注入口である（`SI-FLW-059`、裁定 2026-08-16）。
    出荷面は 2026-08-15 の裁定で M0 read-only に限定されており、worktree は
    `_GATED_HANDLERS` に退避している。出口条件が求めるのは「dispatcher の
    コード経路を通ること」であって事前公開ではないため、fixture が
    `{**_HANDLERS, **_GATED_HANDLERS}` を渡して公開経路を丸ごと検証できるようにする。
    **production では既定（`_HANDLERS`）以外を渡さない。** 実行時に破壊的 operation を
    公開する切替スイッチや環境変数は設けない。
    """
    table = _HANDLERS if handlers is None else handlers
    args = build_parser().parse_args(argv)
    started = _now()
    cwd = os.getcwd()
    operation = f"{args.domain}.{args.action}"

    # 旧 signed capability は、worktree operationの公開可否より先に閉じた契約で拒否する。
    # command-unavailableへ丸めると承認強度の誤設定を運用者が識別できない。
    if args.domain == "worktree" and args.capability_file:
        return _emit(
            _simple_result(
                operation=operation,
                code="UNSUPPORTED",
                repo=cwd,
                summary="この承認方式はサポートされていない",
                cause="unsupported-approval-mode",
                stage="validate",
            ),
            args.format,
        )

    # 出荷面は M0 read-only だけなので、状態変更系のフラグは受け付けない
    # （裁定 2026-08-15）。判定は「いま dispatcher が扱える operation か」で行う。
    # production の既定表に worktree は無いため挙動は変わらない。fixture が
    # `_GATED_HANDLERS` を注入したときだけ、その operation の apply が通る。
    write_capable = (args.domain, args.action) in table and args.domain == "worktree"
    if (args.apply or args.confirm or args.approval_ref) and not write_capable:
        return _emit(
            _simple_result(
                operation=operation,
                code="UNSUPPORTED",
                repo=cwd,
                summary="M0 は read-only であり状態変更を受け付けない",
                cause="command-unavailable",
                stage="validate",
            ),
            args.format,
        )

    handler = table.get((args.domain, args.action))
    if handler is None:
        summary = (
            "この operation は現在の milestone では未対応"
            if args.domain in KNOWN_DOMAINS
            else "未知の domain"
        )
        return _emit(
            _simple_result(
                operation=operation,
                code="UNSUPPORTED",
                repo=cwd,
                summary=summary,
                cause="command-unavailable",
                stage="validate",
            ),
            args.format,
        )

    root, failure = git_read.resolve_repo_root(args.repo)
    if failure:
        return _emit(
            _failure_result(operation, os.path.abspath(args.repo or cwd), failure, started),
            args.format,
        )

    try:
        result, view = handler(root, args, started)
    except Exception as exc:  # noqa: BLE001 — 公開経路へ traceback を出さないための網
        # 例外型を列挙する方式は穴が開く。`ContractError` は `ValueError` 派生であり
        # handler 側の except 3 型のいずれでもなかったため traceback になっていた
        # （`FLW-REV-028:SYN-007`）。型ごとの写像は各 handler が行い、**取りこぼしを
        # ここで受け止める**。内部型名・traceback・path 断片は公開 result へ載せない。
        return _emit(
            _simple_result(
                operation=operation,
                code="UNAVAILABLE",
                repo=root,
                summary="operation を完了できなかった",
                cause="result-indeterminate",
                stage="inspect",
            ),
            args.format,
        )

    # 呼出時の --snapshot と再計算値が違えば STALE（FLW-DSN-005）。
    if args.snapshot and result["ok"] and not R.digest_matches(result.get("snapshot"), args.snapshot):
        stale = _simple_result(
            operation=operation,
            code="STALE",
            repo=root,
            summary="snapshot が要求時点から変化した",
            cause="snapshot-mismatch",
            stage="validate",
            next_actions=[R.next_action(args.domain, args.action)],
        )
        return _emit(stale, args.format)

    return _emit(result, args.format, view)
