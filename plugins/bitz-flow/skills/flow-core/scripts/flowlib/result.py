"""result object と renderer（FLW-DSN-003 / FLW-DSN-012）。

依存方向は ``renderer ← result object`` の一方向で、本 module は adapter にも
process runner にも依存しない。raw command / stdout / stderr / environment /
credential へアクセスしない。

公開契約の正は ``schemas/result-v1.schema.json`` と
``references/output-contract.md``。本 module はその実装であり、両者が食い違った
場合は schema と reference を正とする。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "bitz-flow/result/v1"

# code → exit code（references/output-contract.md の表）。
CODE_EXIT_CODES: dict[str, int] = {
    "OK": 0,
    "READY": 0,
    "DONE": 0,
    "INVALID_INPUT": 2,
    "BLOCKED": 3,
    "APPROVAL_REQUIRED": 4,
    "UNAVAILABLE": 5,
    "STALE": 6,
    "PARTIAL": 7,
    "UNSUPPORTED": 8,
    "INDETERMINATE": 9,
}

# M0（read-only）で到達し得る code。write operation は M1 以降で追加する。
M0_CODES = frozenset({"OK", "INVALID_INPUT", "BLOCKED", "UNAVAILABLE", "STALE", "UNSUPPORTED"})

ALLOWED_CAUSES = frozenset(
    {
        "not-repository",
        "invalid-ref",
        "invalid-path",
        "dirty",
        "detached-head",
        "no-upstream",
        "non-fast-forward",
        "conflict",
        "timeout",
        "command-unavailable",
        "permission-denied",
        "snapshot-mismatch",
        "remote-unavailable",
        "result-indeterminate",
    }
)

ALLOWED_STAGES = frozenset({"inspect", "parse", "validate", "plan", "apply", "post-check"})

DIGEST_KEY = "result_digest"


# --- canonical 表現と digest -------------------------------------------------


def canonical_bytes(value: Any) -> bytes:
    """UTF-8・key 辞書順・余分な空白なしの canonical JSON byte 列を返す。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_of(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def compute_result_digest(result: Mapping[str, Any]) -> str:
    """``result_digest`` 自身を除く result の canonical byte 列から digest を計算する。"""
    without_digest = {key: value for key, value in result.items() if key != DIGEST_KEY}
    return sha256_of(canonical_bytes(without_digest))


def verify_result_digest(result: Mapping[str, Any]) -> bool:
    """保存・転送された result の digest を再計算して一致を確かめる。

    result と digest を同時に変更できる主体に対する耐改ざん性は保証しない
    （references/output-contract.md）。
    """
    return result.get(DIGEST_KEY) == compute_result_digest(result)


def snapshot_of(parts: Iterable[Any]) -> str:
    """観測した事実の canonical bytes から snapshot fingerprint を計算する。"""
    return sha256_of(canonical_bytes(list(parts)))


def new_invocation_id() -> str:
    return f"uuid:{uuid.uuid4()}"


# compact 表示で digest を短縮する桁数（FLW-DSN-003 の描画例 `snapshot=sha256:ab12`）。
# JSON は常に完全な digest を返す。呼出側が渡す `--snapshot` は前方一致で照合する。
ABBREV_HEX_DIGITS = 4


def abbrev_digest(value: str, digits: int = ABBREV_HEX_DIGITS) -> str:
    """``sha256:<64hex>`` を ``sha256:<Nhex>`` へ短縮する。digest 以外はそのまま返す。"""
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return value
    return f"sha256:{value[7 : 7 + digits]}"


def digest_matches(observed: str | None, provided: str | None) -> bool:
    """短縮形を許して digest を照合する（compact 出力を貼り戻せるようにするため）。"""
    if not observed or not provided:
        return False
    if not provided.startswith("sha256:"):
        return False
    return observed.startswith(provided)


# --- result object -----------------------------------------------------------


def empty_data() -> dict[str, Any]:
    """共通 data 契約の骨格（FLW-DSN-012）。operation 別 schema が field を加える。"""
    return {
        "target": {},
        "preconditions": [],
        "effects": [],
        "postconditions": [],
        "concurrency_key": None,
        "evidence": [],
        "completed_steps": [],
        "remaining_steps": [],
        "cause": None,
        "items": [],
        "page": {"shown": 0, "total": 0, "cursor": None},
    }


def paginate(items: Sequence[Any], limit: int | None, snapshot: str | None) -> tuple[list, dict, bool]:
    """items を上限まで切り、page と truncated を返す。

    継続位置を表す `cursor` は返さない。受け取る引数が無いため、提示すると呼出側が
    渡そうとして `INVALID_INPUT` になる（SI-FLW-015）。残りが要るなら `--limit` を
    大きくして取り直す。打ち切りの可視化は `shown` / `total` が担う。
    """
    total = len(items)
    if limit is None or total <= limit:
        return list(items), {"shown": total, "total": total}, False
    shown = max(0, limit)
    return list(items[:shown]), {"shown": shown, "total": total}, True


def build_result(
    *,
    operation: str,
    code: str,
    repo: str,
    tool_version: str,
    started_at: str,
    finished_at: str,
    summary: str = "",
    snapshot: str | None = None,
    data: Mapping[str, Any] | None = None,
    approval_required: str = "none",
    approval_source: str | None = None,
    approval_reference: str | None = None,
    operation_id: str | None = None,
    idempotency_id: str | None = None,
    invocation_id: str | None = None,
    parent_invocation_id: str | None = None,
    attempt: int = 1,
    stage: str = "inspect",
    warnings: Sequence[str] = (),
    truncated: bool = False,
    next_actions: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """envelope を組み立てて digest を付与する。

    schema 違反になり得る組み合わせ（未知 code、不正 stage、cause 語彙外）は
    ここで弾く。renderer より前段で落とすことで、壊れた result を出力しない。
    """
    if code not in CODE_EXIT_CODES:
        raise ValueError(f"未知の code: {code}")
    if stage not in ALLOWED_STAGES:
        raise ValueError(f"未知の stage: {stage}")

    payload = dict(empty_data())
    if data:
        payload.update(data)
    cause = payload.get("cause")
    if cause is not None and cause not in ALLOWED_CAUSES:
        raise ValueError(f"許可語彙外の cause: {cause}")

    exit_code = CODE_EXIT_CODES[code]
    result: dict[str, Any] = {
        "schema": SCHEMA,
        DIGEST_KEY: "",
        "operation": operation,
        "ok": exit_code == 0,
        "code": code,
        "exit_code": exit_code,
        "repo": repo,
        "snapshot": snapshot,
        "operation_id": operation_id,
        "idempotency_id": idempotency_id,
        "approval": {
            "required": approval_required,
            "source": approval_source,
            "reference": approval_reference,
        },
        "summary": summary,
        "data": payload,
        "audit": {
            "tool_version": tool_version,
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "invocation": {
            "id": invocation_id or new_invocation_id(),
            "parent_id": parent_invocation_id,
            "attempt": attempt,
            "stage": stage,
        },
        "warnings": list(warnings),
        "truncated": truncated,
        "next_actions": [dict(action) for action in next_actions],
    }
    result[DIGEST_KEY] = compute_result_digest(result)
    return result


def next_action(domain: str, action: str, **args: Any) -> dict[str, Any]:
    """許可された domain / action と必要引数だけを返す（shell 文字列を作らない）。"""
    return {"domain": domain, "action": action, "args": dict(args)}


# --- renderer ----------------------------------------------------------------


@dataclass(frozen=True)
class CompactView:
    """compact renderer への入力。

    operation 層が事実から組み立てる。renderer は raw output を知らない。
    """

    tokens: Mapping[str, Any] = field(default_factory=dict)
    blocking: Sequence[str] = ()
    changed: Sequence[str] = ()
    normal: Sequence[str] = ()


def render_compact(result: Mapping[str, Any], view: CompactView | None = None) -> str:
    """固定 token・固定順序・1項目1行で描画する。

    行順は 判定行 → blocking/error → 変更対象 → 通常項目 → TRUNCATED → NEXT。
    0 件 field と null は省略する。
    """
    view = view or CompactView()
    head = [result["code"], result["operation"]]

    cause = result["data"].get("cause")
    if cause:
        head.append(f"cause={cause}")
    stage = result["invocation"]["stage"]
    if not result["ok"]:
        head.append(f"stage={stage}")
    if result.get("snapshot"):
        head.append(f"snapshot={abbrev_digest(result['snapshot'])}")
    for key, value in view.tokens.items():
        # null と空文字だけを省略する。0 は事実（例: behind=0）であり
        # 「不明」と区別できなくなるため落とさない（FLW-DSN-003 の描画例）。
        if value is None or value == "":
            continue
        head.append(f"{key}={_compact_value(value)}")

    lines = [" ".join(head)]
    # 1項目1行を renderer が保証する（呼出側の組み立てに依存しない）。
    lines.extend(escape_line(line) for line in view.blocking)
    lines.extend(escape_line(line) for line in view.changed)
    lines.extend(escape_line(line) for line in view.normal)

    page = result["data"].get("page") or {}
    if result.get("truncated"):
        # cursor は出さない。受け取る引数が無い値を見せない（SI-FLW-015）。
        lines.append(
            f"TRUNCATED shown={page.get('shown', 0)} total={page.get('total', 0)}"
        )
    for action in result.get("next_actions", []):
        tokens = " ".join(
            f"{key}={_compact_value(value)}"
            for key, value in action.get("args", {}).items()
            if value is not None
        )
        entry = f"NEXT {action['domain']}.{action['action']}"
        lines.append(f"{entry} {tokens}".rstrip())
    for warning in result.get("warnings", []):
        lines.append(f"WARN {warning}")
    return "\n".join(lines)


_CONTROL_ESCAPES = {
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\v": "\\v",
    "\f": "\\f",
    "\0": "\\0",
}


def escape_line(text: str) -> str:
    """1項目1行を機械的に守る。

    パスやブランチ名には改行・タブを含められる。素通しすると compact 出力の
    行数がずれるだけでなく、**別の判定行を偽装できる**（例: 改行のあとに
    ``OK git.status ...`` を含むファイル名）。renderer 側で必ずエスケープする。
    """
    if not isinstance(text, str):
        return text
    for raw, escaped in _CONTROL_ESCAPES.items():
        text = text.replace(raw, escaped)
    return "".join(char if char.isprintable() or char == " " else repr(char)[1:-1] for char in text)


def _compact_value(value: Any) -> str:
    """compact 表示用に値を短くする（digest は短縮、bool は小文字）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return escape_line(abbrev_digest(value))
    return str(value)


def render_json(result: Mapping[str, Any]) -> str:
    """operation 別 JSON Schema を満たす result をそのまま出力する。"""
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def render(result: Mapping[str, Any], fmt: str, view: CompactView | None = None) -> str:
    if fmt == "json":
        return render_json(result)
    return render_compact(result, view)
