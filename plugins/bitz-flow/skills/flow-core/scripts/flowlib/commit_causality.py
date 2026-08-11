"""REC-COMMIT — commit の因果証跡（FLW-DSN-015 / FLW-FR-005 / FLW-NFR-003）。

**原則: 「条件の一致する commit を後から検索して、今回の成功と見なす」ことをしない。**

同じ parent・tree・message の commit は、別の実行が作ったものかもしれないし、
再実行で偶然一致したものかもしれない。ref が期待の OID を指していることは、
「自分の CAS がそれを書いた」ことを意味しない。だから **CAS を実行した writer の receipt** を
`DONE` の必須条件にする。receipt が無ければ `INDETERMINATE` とし、人間へ回す。

手順（Adapter → Intent Store → Git Object DB → Ref Store）:

1. HEAD / index / tree / message / author / 時刻 / sign 方式を固定する
2. canonical commit bytes と `planned_commit_oid` を**副作用なしで**計算する
3. `old_oid` / `planned_oid` / `operation_id` / fencing token を pre-object intent として保存し fsync
4. canonical bytes を planned OID で object store へ保存する
5. fencing 照合後に `update-ref old_oid -> planned_oid`（CAS）
6. CAS result を同じ operation chain へ receipt として追記し fsync
7. ref を再照合し、`DONE` receipt または quarantine を追記

`PARTIAL` は構築しない。単一 ref の CAS は原子的で、部分完了が存在しないためである。
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
from pathlib import Path
from typing import Sequence

from . import git_read

CODE_DONE = "DONE"
CODE_INDETERMINATE = "INDETERMINATE"
CODE_BLOCKED = "BLOCKED"
CODE_STALE = "STALE"
CODE_INVALID_INPUT = "INVALID_INPUT"
CODE_UNSUPPORTED = "UNSUPPORTED"

# 観測結論（quarantine の解除判断に渡す語彙。正は intent モジュール）
CONCLUSION_ABANDONED_NO_EFFECT = "no-effect"
CONCLUSION_ORPHAN_OBJECT = "orphan-object-no-reachable-effect"
CONCLUSION_CONFIRMED_DONE = "confirmed-done"
CONCLUSION_UNRESOLVED = "unresolved"

_CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|refactor|test|chore|perf|build|ci|style|revert)(\([^)]+\))?!?: .+"
)


@dataclasses.dataclass(frozen=True)
class CommitFailure:
    code: str
    reason: str
    cause: str | None = None
    stage: str = "apply"


@dataclasses.dataclass(frozen=True)
class CommitPlan:
    old_oid: str | None
    tree_oid: str
    planned_oid: str
    canonical_bytes: bytes
    message: str
    ref: str


@dataclasses.dataclass(frozen=True)
class CasReceipt:
    """CAS を実行した writer が残す証跡。これが無い限り DONE へ昇格させない。"""

    operation_id: str
    ref: str
    before_oid: str | None
    after_oid: str
    fencing_token: int


def _git(root: Path, args: Sequence[str], *, input_bytes: bytes | None = None,
         env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    if env:
        environ.update(env)
    return subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root),
        input=input_bytes,
        capture_output=True,
        env=environ,
    )


def lint_message(message: str) -> CommitFailure | None:
    """Conventional Commits と任意の footer を事前検査する。"""
    first = message.splitlines()[0] if message.strip() else ""
    if not _CONVENTIONAL.match(first):
        return CommitFailure(
            CODE_INVALID_INPUT,
            "commit message が Conventional Commits に従っていない",
            stage="validate",
        )
    return None


def resolve_ref(repo: Path, ref: str) -> str | None:
    proc = _git(repo, ["rev-parse", "--verify", "--quiet", ref])
    text = proc.stdout.decode("utf-8", "replace").strip()
    return text or None


def object_exists(repo: Path, oid: str) -> bool:
    proc = _git(repo, ["cat-file", "-e", f"{oid}^{{commit}}"])
    return proc.returncode == 0


def _identity(repo: Path) -> tuple[str, str]:
    name = _git(repo, ["config", "user.name"]).stdout.decode("utf-8", "replace").strip()
    email = _git(repo, ["config", "user.email"]).stdout.decode("utf-8", "replace").strip()
    return name, email


def build_commit_bytes(
    *, tree_oid: str, parents: Sequence[str], name: str, email: str, when: str, message: str
) -> bytes:
    """commit object の canonical bytes を組み立てる。

    `commit-tree` は object store へ書き込むため plan では使えない。同じ bytes を自分で作り、
    `hash-object` を `-w` なしで通して OID だけを得る。
    """
    lines = [f"tree {tree_oid}"]
    lines += [f"parent {p}" for p in parents]
    lines.append(f"author {name} <{email}> {when}")
    lines.append(f"committer {name} <{email}> {when}")
    lines.append("")
    body = message if message.endswith("\n") else message + "\n"
    return ("\n".join(lines) + "\n" + body).encode("utf-8")


def plan_commit(
    repo: Path, *, message: str, ref: str = "HEAD", author: str | None = None,
    when: str = "1767225600 +0000",
) -> tuple[CommitPlan | None, CommitFailure | None]:
    """canonical commit bytes と planned OID を計算する。

    commit object と ref は**触らない**。`hash-object` は `-w` なしで使うため、
    commit object は object store へ書かれない。

    ただし tree の確定には `write-tree` が要る。tree object の書き込みは reachable ref を
    変えず、同じ index からは同じ OID になる冪等操作だが、object store への書き込みではある。
    commit object の保存（`save_object`）とは分けて扱い、pre-object intent が守るのは
    **commit object と ref** である。
    """
    failure = lint_message(message)
    if failure is not None:
        return None, failure

    tree = _git(repo, ["write-tree"])
    if tree.returncode != 0:
        return None, CommitFailure(
            CODE_BLOCKED, "tree を確定できない", cause=git_read._classify(tree.stderr), stage="plan"
        )
    tree_oid = tree.stdout.decode().strip()

    old_oid = resolve_ref(repo, ref)
    name, email = _identity(repo)
    if author:
        name = author

    canonical = build_commit_bytes(
        tree_oid=tree_oid,
        parents=[old_oid] if old_oid else [],
        name=name,
        email=email,
        when=when,
        message=message,
    )

    hashed = _git(repo, ["hash-object", "-t", "commit", "--stdin"], input_bytes=canonical)
    if hashed.returncode != 0:
        return None, CommitFailure(
            CODE_BLOCKED, "planned OID を計算できない",
            cause=git_read._classify(hashed.stderr), stage="plan",
        )

    return (
        CommitPlan(
            old_oid=old_oid,
            tree_oid=tree_oid,
            planned_oid=hashed.stdout.decode().strip(),
            canonical_bytes=canonical,
            message=message,
            ref=ref,
        ),
        None,
    )


def save_object(repo: Path, plan: CommitPlan) -> tuple[str | None, CommitFailure | None]:
    """canonical bytes を planned OID で object store へ保存する（手順4）。

    **pre-object intent の fsync 後にだけ呼ぶ**。reachable ref は変えないが副作用である。
    """
    proc = _git(
        repo, ["hash-object", "-t", "commit", "-w", "--stdin"], input_bytes=plan.canonical_bytes
    )
    if proc.returncode != 0:
        return None, CommitFailure(
            CODE_BLOCKED, "commit object を保存できない", cause=git_read._classify(proc.stderr)
        )
    written = proc.stdout.decode().strip()
    if written != plan.planned_oid:
        return None, CommitFailure(
            CODE_INDETERMINATE, "保存された OID が planned OID と一致しない"
        )
    return written, None


def cas_update_ref(
    repo: Path, plan: CommitPlan, *, operation_id: str, fencing_token: int
) -> tuple[CasReceipt | None, CommitFailure | None]:
    """`update-ref old_oid -> planned_oid` を CAS で行い、receipt を返す。"""
    args = ["update-ref", plan.ref, plan.planned_oid]
    args.append(plan.old_oid if plan.old_oid else "")
    proc = _git(repo, args)
    if proc.returncode != 0:
        return None, CommitFailure(
            CODE_STALE,
            "ref が plan 時点から変化しているため CAS が成立しない",
            cause="snapshot-mismatch",
        )
    return (
        CasReceipt(
            operation_id=operation_id,
            ref=plan.ref,
            before_oid=plan.old_oid,
            after_oid=plan.planned_oid,
            fencing_token=fencing_token,
        ),
        None,
    )


def conclude(
    repo: Path,
    plan: CommitPlan,
    *,
    receipt: CasReceipt | None,
    operation_id: str,
) -> tuple[str, str, CommitFailure | None]:
    """観測から結論を出す。戻り値は (result_code, 観測結論, failure)。

    **ref が planned OID を指していても、receipt が無ければ DONE にしない。**
    """
    current = resolve_ref(repo, plan.ref)

    if receipt is not None:
        if receipt.operation_id != operation_id:
            return (
                CODE_INDETERMINATE,
                CONCLUSION_UNRESOLVED,
                CommitFailure(CODE_INDETERMINATE, "receipt の operation ID が一致しない"),
            )
        if current == plan.planned_oid and receipt.after_oid == plan.planned_oid:
            return CODE_DONE, CONCLUSION_CONFIRMED_DONE, None
        return (
            CODE_INDETERMINATE,
            CONCLUSION_UNRESOLVED,
            CommitFailure(CODE_INDETERMINATE, "receipt と現在の ref が一致しない"),
        )

    # receipt が無い（CAS 直後 crash 等）。ref と object から結論を絞る。
    if current == plan.planned_oid:
        return (
            CODE_INDETERMINATE,
            CONCLUSION_UNRESOLVED,
            CommitFailure(
                CODE_INDETERMINATE,
                "ref は planned OID だが CAS の receipt が無い（DONE と推定しない）",
            ),
        )
    if current == plan.old_oid:
        if object_exists(repo, plan.planned_oid):
            return (
                CODE_INDETERMINATE,
                CONCLUSION_ORPHAN_OBJECT,
                CommitFailure(
                    CODE_INDETERMINATE,
                    "object は存在するが ref は不変（orphan object。object は削除しない）",
                ),
            )
        return CODE_BLOCKED, CONCLUSION_ABANDONED_NO_EFFECT, None

    return (
        CODE_INDETERMINATE,
        CONCLUSION_UNRESOLVED,
        CommitFailure(CODE_INDETERMINATE, "ref が old でも planned でもない（第三者の更新）"),
    )


def find_matching_commit_is_not_proof() -> str:
    """同条件の commit 検索を成功の根拠にしない、という規約の在処を示す。

    実装として「検索して DONE にする」関数を**提供しない**ことで、誤用の入口を塞ぐ。
    """
    return (
        "同じ parent / tree / message の commit を検索して今回の成功と見なさない。"
        "DONE の根拠は CAS を実行した writer の receipt である。"
    )
