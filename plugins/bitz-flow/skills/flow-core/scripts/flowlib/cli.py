"""単一 dispatcher の CLI 層（FLW-DSN-003 公開入口）。

入力を canonical 化し、adapter から事実を取得し、renderer へ渡す。
M0 read-onlyとM2 worktreeの署名capability付きplan/applyを扱う。

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
    __version__, git_read, result as R, worktree_capability, worktree_cleanup,
    worktree_runtime,
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
    return parser


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
) -> dict[str, Any]:
    data = R.empty_data()
    data["cause"] = cause
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


def _op_worktree(root: str, args, started: str) -> tuple[dict, R.CompactView]:
    operation = f"worktree.{args.action}"
    if args.action == "audit":
        # 以前は private `_git` を直呼びし、失敗が result にならず traceback になっていた。
        # `--limit` / `--timeout` も無視していた（`FLW-REV-016:SYN-011`）。
        from pathlib import Path as _Path

        try:
            proc = worktree_runtime._git(_Path(root), "worktree", "list", "--porcelain")
        except (worktree_runtime.WorktreeRuntimeError, OSError, ValueError) as exc:
            return _simple_result(
                operation=operation, code="UNAVAILABLE", repo=root,
                summary=f"worktree 一覧を取得できない（{type(exc).__name__}）", stage="inspect",
            ), R.CompactView()
        registry = worktree_runtime.parse_worktree_registry(proc.stdout)
        survey = worktree_runtime.survey_receipts(_Path(root))

        data = R.empty_data()
        data["evidence"] = ["git worktree list --porcelain", "bitz-flow-v2/receipts"]

        # 突合が成立しない場合は分類を推測しない（`FLW-DSN-016` §8 の audit 行）。
        # receipt を読めないまま比べると、すべての worktree が外部起因に見える。
        if not survey.readable:
            data["cause"] = "result-indeterminate"
            data["recovery_class"] = "human-stop"
            data["required_human_input"] = (
                f"{survey.reason}。worktree の由来を判定できない。"
                "common-dir 配下の bitz-flow-v2/receipts を確認すること"
            )
            result = R.build_result(
                operation=operation, code="INDETERMINATE", repo=root,
                tool_version=__version__, started_at=started, finished_at=_now(),
                summary="receipt との突合が成立せず worktree の由来を判定できない",
                snapshot=R.snapshot_of([survey.status]), data=data, stage="inspect",
                next_actions=(),
            )
            return result, R.CompactView(
                tokens={"worktrees": len(registry), "receipts": "unreadable"})

        # 外部起因は2形ある（`FLW-DSN-016` §7）。registry と receipt を双方向に突き合わせ、
        # どちらから見た欠落も拾う（`FLW-REV-018:SYN-002`）。
        # HEAD の変化は managed worktree での通常の作業でも起きるため、
        # **事実として報告するが違反にはしない**（裁定 2026-08-16）。
        main_worktree = str(_Path(root).resolve())
        rows = worktree_runtime.reconcile_registry(registry, survey, main_worktree)

        limit = args.limit if args.limit and args.limit > 0 else DEFAULT_ITEM_LIMIT
        shown = rows[:limit]
        data["items"] = list(shown)
        data["page"] = {"shown": len(shown), "total": len(rows),
                        "truncated": len(rows) > len(shown)}

        divergent = [row["path"] for row in rows if row["divergence"]]
        if not divergent:
            result = R.build_result(
                operation=operation, code="OK", repo=root, tool_version=__version__,
                started_at=started, finished_at=_now(),
                summary=f"{len(registry)} worktrees",
                snapshot=R.snapshot_of(rows), data=data, stage="inspect",
            )
            return result, R.CompactView(
                tokens={"worktrees": len(registry), "divergent": 0})

        # managed worktree の binding 不整合は、公開 audit から §6 の観測へ接続する。
        # receipt が存在しない外部 worktree はこの観測の対象外であり、存在観測だけから
        # §6 の解除区分を推測しない。
        binding_findings = [
            finding
            for row in rows
            if row["managed"]
            for finding in [worktree_capability.audit_external_binding_change(
                worktree_capability.WorktreeBindingObservation(
                    directory_exists=row["present"],
                    registry_exists=row["registered"],
                    bidirectional_binding_valid=not bool(row["divergence"]),
                )
            )]
            if finding is not None
        ]

        # 検出したら quarantine 相当として停止する（自動修復はしない）。
        # 解除区分は §6 の4区分を `classify_quarantine` で**実データから計算**する。
        # 以前は全フィールド固定リテラルの evidence を渡していたため、
        # 分類ではなく表示だった（`FLW-REV-018:SYN-004`）。
        release_class = worktree_cleanup.classify_quarantine(
            worktree_cleanup.QuarantineEvidence(
                chain_valid=survey.readable,
                completed_steps=survey.completed_steps,
                # 外部起因の乖離には、plan時の intent / instance nonce の一致を
                # 証明できない。存在観測だけで worktree-not-started と推測しない。
                instance_nonce_matches=False,
                mutation_receipts=survey.mutation_receipts,
                all_postconditions_match=False,
            ),
            total_mutating_steps=survey.mutation_receipts,
        )
        reason = f"registry と receipt が食い違う worktree を {len(divergent)} 件検出した"
        data["cause"] = "quarantined"
        data["recovery_class"] = worktree_cleanup.recovery_for(
            "BLOCKED", "quarantined").recovery_class
        data["quarantine"] = {
            "required": True,
            "release_class": release_class,
            "reason": reason,
            "targets": divergent,
            "binding_findings": [finding.reason for finding in binding_findings],
        }
        data["required_human_input"] = (
            f"{release_class}: FLW-DSN-016 §6 の解除区分に従い "
            "evaluation-reviewer の判断を要する。bitz-flow は解除を代行しない"
        )
        result = R.build_result(
            operation=operation, code="BLOCKED", repo=root,
            tool_version=__version__, started_at=started, finished_at=_now(),
            summary=reason, snapshot=R.snapshot_of(rows), data=data,
            stage="inspect",
            # `human-stop` は空 NEXT である（§8）。解除は operation ではなく
            # reviewer の裁定であり、示せる次の operation は存在しない。
            next_actions=(),
        )
        return result, R.CompactView(
            tokens={"worktrees": len(registry), "divergent": len(divergent),
                    "quarantine": release_class})

    missing = [name for name, value in (
        ("--path", args.path), ("--branch", args.branch), ("--worktree-root", args.worktree_root)
    ) if not value]
    if missing:
        return _simple_result(
            operation=operation, code="INVALID_INPUT", repo=root,
            summary="worktree input missing: " + ", ".join(missing), stage="validate",
        ), R.CompactView()
    try:
        plan_value = worktree_runtime.plan(
            root, action=args.action, path=args.path, branch=args.branch,
            worktree_root=args.worktree_root, start_point=args.start_point,
            default_branch=args.default_branch,
        )
    except worktree_runtime.WorktreeRuntimeError as exc:
        return _simple_result(
            operation=operation, code="BLOCKED", repo=root, summary=str(exc), stage="plan",
        ), R.CompactView()

    # 承認モードは配備が決める（`SI-FLW-061`）。registry があれば署名を要求し、無ければ
    # plan digest（`--confirm`）と operation_id 由来の単回 nonce だけで承認する。
    # plan の時点で提示しないと、人間はどちらの承認を求められているか判らない。
    signed_mode = worktree_runtime.signature_mode_available(plan_value.common_dir)
    approval_mode = (
        worktree_runtime.C.MODE_SIGNED_CAPABILITY if signed_mode
        else worktree_runtime.C.MODE_PLAN_DIGEST
    )
    preconditions = ["plan snapshot一致"]
    preconditions.append(
        "単回Ed25519 capability一致" if signed_mode
        else "operation_id一致とoperation_id由来の単回nonce"
    )
    data = R.empty_data()
    data.update({
        "target": {"path": plan_value.path, "branch": plan_value.branch},
        "preconditions": preconditions,
        "effects": list(plan_value.effects),
        "postconditions": ["worktree/branch/receiptを再観測して一致"],
        "concurrency_key": plan_value.context.worktree_dir_guard_key,
        "evidence": ["operation_id", "snapshot", "receipt digest"],
        "capability_context": dataclasses.asdict(plan_value.context),
        "approval_mode": approval_mode,
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
    if not args.confirm or (signed_mode and not args.capability_file):
        required = "--confirm and --capability-file" if signed_mode else "--confirm"
        return _simple_result(
            operation=operation, code="APPROVAL_REQUIRED", repo=root,
            summary=f"{required} are required", stage="validate",
        ), R.CompactView()
    try:
        import json
        from pathlib import Path
        capability = None
        if signed_mode:
            capability = worktree_runtime.capability_from_json(
                json.loads(Path(args.capability_file).read_text(encoding="utf-8"))
            )
        decision = worktree_runtime.apply(
            plan_value, confirm=args.confirm, capability=capability,
            backup_receipt=args.backup_receipt,
        )
    except (OSError, ValueError, KeyError, worktree_runtime.WorktreeRuntimeError) as exc:
        return _simple_result(
            operation=operation, code="BLOCKED", repo=root, summary=str(exc), stage="apply",
        ), R.CompactView()
    data["completed_steps"] = list(decision.completed_steps)
    data["remaining_steps"] = list(decision.remaining_steps)
    data["evidence"] = list(decision.evidence)
    result = R.build_result(
        operation=operation, code=decision.code, repo=root, tool_version=__version__,
        started_at=started, finished_at=_now(), summary=decision.summary,
        snapshot=plan_value.snapshot, operation_id=plan_value.operation_id,
        approval_required="explicit-human",
        # 承認の由来は実際に使ったモードを名乗る。無条件に "signed-capability" と
        # 名乗ると、plan-digest で適用した receipt が承認強度を強く見せる
        # （`SI-FLW-063` / `OPS-303`）。
        approval_source=approval_mode,
        approval_reference=args.approval_ref, stage="apply", data=data,
    )
    return result, R.CompactView(tokens={"action": args.action, "code": decision.code})


def _failure_result(operation: str, repo: str, failure, started: str) -> dict:
    """adapter の失敗を公開 result へ写す（cause と stage だけを載せる）。"""
    code = "UNAVAILABLE"
    if failure.cause in ("not-repository", "invalid-path", "invalid-ref"):
        code = "INVALID_INPUT"
    data = R.empty_data()
    data["cause"] = failure.cause
    return R.build_result(
        operation=operation,
        code=code,
        repo=repo,
        tool_version=__version__,
        started_at=started,
        finished_at=_now(),
        summary="操作を完了できない",
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
    ("worktree", "audit"): _op_worktree,
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

    result, view = handler(root, args, started)

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
