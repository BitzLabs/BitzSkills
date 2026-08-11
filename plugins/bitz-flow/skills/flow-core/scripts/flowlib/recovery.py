"""失敗 result を安全な契約内へ着地させる recovery class 決定器（FLW-DSN-015）。

`references/recovery-matrix.md` と本モジュールの `MATRIX` は同一の決定表を表す。人間向けの表を
実装がパースすると表記ゆれで壊れるため、**実装側を機械可読な正とし、markdown 表との一致を
テストで機械照合する**（このリポジトリで宣言と実装の二重定義を防ぐときの定番手）。
各 Rule は照合用に markdown の行ラベル `md_row` を保持する。

安全側に倒す既定:

- 未登録の tuple、未知の code、到達不能と宣言された組み合わせは例外なく `human-stop`。
  「該当行が無いので安全側の retry」という暗黙 default を作らない。
- 停止するときは空の `next_actions` を返す。安全な候補が無いのに何か提案することを、
  停止することより優先しない。
"""

from __future__ import annotations

import dataclasses
from collections import deque
from typing import Iterable, Mapping, Sequence

# recovery class（閉集合。FLW-DSN-010 と同一）
RETRY_READ = "retry-read"
RECONCILE_ONLY = "reconcile-only"
REPLAN_HUMAN = "replan-human"
HUMAN_STOP = "human-stop"
RECOVERY_CLASSES = (RETRY_READ, RECONCILE_ONLY, REPLAN_HUMAN, HUMAN_STOP)

ANY_READ = "*read"
ANY_WRITE = "*write"

#: 分類できない観測結果（timeout / 出力上限超過 / 未分類）を表す擬似 code。
UNCLASSIFIED_OUTCOME = "UNCLASSIFIED_OUTCOME"
#: intent は永続化済みだが object 保存前の状態を表す擬似 code。
PENDING_INTENT = "PENDING_INTENT"

#: postcondition の再照合はこの回数までとし、それ以上は INDETERMINATE へ倒す。
MAX_POSTCONDITION_RECHECKS = 2

READ_OPERATIONS = (
    "repo.inspect",
    "repo.doctor",
    "git.status",
    "git.diff-summary",
    "git.diff-detail",
    "git.log",
    "git.branches",
    "git.conflicts",
    "worktree.list",
)
WRITE_OPERATIONS = (
    "git.fetch",
    "git.stage",
    "git.commit",
    "git.sync",
    "git.publish-branch",
    "git.delete-remote-branch",
)

#: 構造上あり得ない (operation, code)。暗黙 default に頼らず明示する。
UNREACHABLE = {
    ("git.commit", "PARTIAL"): (
        "単一 ref の CAS は原子的で部分完了が存在しない。receipt 欠落は INDETERMINATE とする"
    ),
}


@dataclasses.dataclass(frozen=True)
class Rule:
    operations: tuple[str, ...]
    phase: str
    code: str
    recovery_class: str
    allowed_next: tuple[str, ...]
    forbidden: tuple[str, ...]
    md_row: tuple[str, str, str]
    """recovery-matrix.md の (operation, phase, code) 列。照合テスト用。"""


MATRIX: tuple[Rule, ...] = (
    Rule(
        (ANY_READ,), "pre-inspect", "INVALID_INPUT", RETRY_READ,
        ("同一 read ＋ 正規化済み候補",), ("shell", "生値 echo"),
        ("全 read", "inspect 前", "`INVALID_INPUT`"),
    ),
    Rule(
        (ANY_WRITE,), "pre-apply", "STALE", REPLAN_HUMAN,
        ("inspect", "新 plan"), ("apply 自動連結",),
        ("全 write", "apply 前", "`STALE`"),
    ),
    Rule(
        ("git.stage", "git.sync", "git.publish-branch"), "post-apply", "PARTIAL", RECONCILE_ONLY,
        ("operation 固有 read reconcile",), ("残 step 自動 apply",),
        ("stage / sync / publish", "apply 後", "`PARTIAL`"),
    ),
    Rule(
        (ANY_WRITE,), "post-apply", UNCLASSIFIED_OUTCOME, RECONCILE_ONLY,
        ("postcondition 最大2回",), ("command blind retry",),
        ("全 write", "apply 後", "timeout / output-limit / unclassified"),
    ),
    Rule(
        (ANY_WRITE,), "reconcile-impossible", "INDETERMINATE", HUMAN_STOP,
        (), ("mutation 全般",),
        ("全 write", "reconcile 不能", "`INDETERMINATE`"),
    ),
    Rule(
        (ANY_WRITE,), "pending-or-quarantine-exists", "BLOCKED", HUMAN_STOP,
        (), ("新 plan / apply",),
        ("全 write", "pending / quarantine 既存", "`BLOCKED`"),
    ),
    Rule(
        (ANY_WRITE,), "precondition-conflict", "STALE", REPLAN_HUMAN,
        ("inspect", "新 plan"), ("旧 operation ID 再利用",),
        ("全 write", "precondition 競合", "`STALE`"),
    ),
    Rule(
        ("git.commit",), "pre-object-save", PENDING_INTENT, RECONCILE_ONLY,
        ("planned OID と object 有無の照合",), ("commit object blind 再生成",),
        ("commit", "object 保存前", "`PENDING_INTENT`"),
    ),
    Rule(
        ("git.commit",), "post-cas-no-receipt", "INDETERMINATE", HUMAN_STOP,
        (), ("DONE 推定", "再 commit"),
        ("commit", "CAS 後 receipt なし", "`INDETERMINATE`"),
    ),
    Rule(
        ("git.fetch",), "partial-ref-set", "PARTIAL", RECONCILE_ONLY,
        ("completed / remaining ref 集合の確定",), ("fetch 再実行",),
        ("fetch", "ref 集合の一部更新", "`PARTIAL`"),
    ),
    Rule(
        ("git.stage",), "index-digest-mismatch", "STALE", REPLAN_HUMAN,
        ("index / worktree 再 inspect",), ("旧 patch apply",),
        ("stage", "index digest 不一致", "`STALE`"),
    ),
    Rule(
        ("git.sync",), "fetched-branch-not-updated", "PARTIAL", RECONCILE_ONLY,
        ("completed=fetch、remaining=branch-update の提示",), ("自動 branch 更新",),
        ("sync", "fetch 済み・branch 未更新", "`PARTIAL`"),
    ),
    Rule(
        ("git.publish-branch",), "remote-ref-mismatch", "STALE", REPLAN_HUMAN,
        ("remote ref 全件再照会", "新 plan"), ("force / update 再実行",),
        ("publish", "remote ref 不一致", "`STALE`"),
    ),
)


@dataclasses.dataclass(frozen=True)
class Decision:
    recovery_class: str
    allowed_next: tuple[str, ...]
    forbidden: tuple[str, ...]
    stop_reason: str | None = None
    required_human_input: tuple[str, ...] = ()
    quarantine_target: bool = False
    max_postcondition_rechecks: int = 0

    @property
    def stops(self) -> bool:
        return self.recovery_class == HUMAN_STOP


def _fail_closed(reason: str, *, quarantine: bool = False) -> Decision:
    return Decision(
        recovery_class=HUMAN_STOP,
        allowed_next=(),
        forbidden=("mutation 全般",),
        stop_reason=reason,
        required_human_input=(
            "対象 target の現在状態の確認",
            "intent record と receipt の照合結果",
            "続行または中止の裁定",
        ),
        quarantine_target=quarantine,
    )


def _is_write(operation: str) -> bool:
    return operation in WRITE_OPERATIONS


def _is_read(operation: str) -> bool:
    return operation in READ_OPERATIONS


def _matches(rule: Rule, operation: str) -> bool:
    if operation in rule.operations:
        return True
    if ANY_READ in rule.operations and _is_read(operation):
        return True
    if ANY_WRITE in rule.operations and _is_write(operation):
        return True
    return False


def decide(*, operation: str, phase: str, code: str) -> Decision:
    """(operation, phase, code) から recovery class と許可された次の一手を決める。

    具体行を既定行より優先する。どちらにも当たらなければ `human-stop` へ fail-closed する。
    """
    if operation not in READ_OPERATIONS and operation not in WRITE_OPERATIONS:
        return _fail_closed(f"未登録の operation: {operation}")

    unreachable = UNREACHABLE.get((operation, code))
    if unreachable is not None:
        return _fail_closed(f"到達不能と宣言された組み合わせを観測した（{unreachable}）", quarantine=True)

    specific = [r for r in MATRIX if operation in r.operations and r.phase == phase and r.code == code]
    generic = [r for r in MATRIX if _matches(r, operation) and r.phase == phase and r.code == code]
    rule = (specific or generic or [None])[0]
    if rule is None:
        return _fail_closed(
            f"決定表に登録の無い組み合わせ（operation={operation} phase={phase} code={code}）",
            quarantine=_is_write(operation) and code in ("INDETERMINATE", UNCLASSIFIED_OUTCOME),
        )

    if rule.recovery_class == HUMAN_STOP:
        return _fail_closed(
            f"{rule.md_row[0]} / {rule.md_row[1]} は自動継続できない",
            quarantine=code in ("INDETERMINATE", UNCLASSIFIED_OUTCOME),
        )

    return Decision(
        recovery_class=rule.recovery_class,
        allowed_next=rule.allowed_next,
        forbidden=rule.forbidden,
        quarantine_target=False,
        max_postcondition_rechecks=(
            MAX_POSTCONDITION_RECHECKS if rule.code == UNCLASSIFIED_OUTCOME else 0
        ),
    )


# --- next_actions グラフの到達可能性 -----------------------------------------

#: この code から人間の新しい裁定なしに mutation へ到達してはならない。
NO_AUTO_MUTATION_CODES = frozenset({"PARTIAL", "STALE", "INDETERMINATE", UNCLASSIFIED_OUTCOME})


def reaches_mutation(start: Iterable[str], graph: Mapping[str, Sequence[str]]) -> list[str]:
    """`start` から `graph` を辿って到達できる mutation operation を返す。

    1 段だけでなく推移的に検査する（許可グラフの到達可能性）。
    """
    seen: set[str] = set()
    found: list[str] = []
    queue = deque(start)
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if _is_write(node):
            found.append(node)
        queue.extend(graph.get(node, ()))
    return found


def validate_next_actions(
    *, code: str, next_actions: Iterable[str], graph: Mapping[str, Sequence[str]] | None = None
) -> str | None:
    """許可されない next_actions を拒否する。問題があれば理由を返す。"""
    actions = list(next_actions)
    if code not in NO_AUTO_MUTATION_CODES:
        return None

    reachable = reaches_mutation(actions, graph or {})
    if reachable:
        return (
            f"{code} から人間の新しい裁定なしに mutation へ到達できる next_actions は不正: "
            + ", ".join(sorted(set(reachable)))
        )
    return None


def project_write_state(write_state: str) -> str:
    """応答喪失時の write_state を決定表の phase へ射影する（未分類のまま返さない）。"""
    mapping = {
        "pending-intent": "pre-object-save",
        "mutating": "post-apply",
        "reconciling": "post-apply",
    }
    return mapping.get(write_state, "reconcile-impossible")
