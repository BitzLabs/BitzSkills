"""意味中間表現の形（EARS-AI言語・意味中間表現仕様 §6）と、構文の条件の種類（`kind`）の定数。

重大度・`resultStatus`・`draft`の差分の判定は診断レジストリ
（`docs/03.詳細設計/00_共通契約/05_診断レジストリ.md` §4）が所有し、フェーズBが
文書の状態（`draft`／それ以外）を見て決める。本モジュールと`parser.py`はそれを決めず、
「どの条件が成立したか」という条件の種類（`kind`）だけを返す。種類（`kind`）から診断の
`conditionId`／診断コードへの対応表はフェーズBの側に置く。
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

#: 未閉鎖のコードスパン（EAI-CORE-SYNTAX-005、`EAI-SYNTAX-CODE-UNCLOSED[-DRAFT]`）。
CONDITION_CODE_UNCLOSED = "code-unclosed"
#: 不正なエスケープ・未閉鎖の`quoted-value`・不正または未閉鎖のタグ（EAI-CORE-SYNTAX-004、`EAI-SYNTAX-TAG-UNCLOSED[-DRAFT]`）。
CONDITION_TAG_UNCLOSED = "tag-unclosed"
#: 規範文IDの形式の不正（EAI-CORE-ID-001、`EAI-ID-FORMAT`）。
CONDITION_ID_FORMAT = "id-format"
#: 規範文IDの重複（EAI-CORE-ID-002、`EAI-ID-DUPLICATE`）。`draft`でも`error`のため単一。
CONDITION_ID_DUPLICATE = "id-duplicate"
#: タグの順序の不正（EAI-CORE-SYNTAX-001、`EAI-SYNTAX-TAG-ORDER[-DRAFT]`）。
CONDITION_TAG_ORDER = "tag-order"
#: 必須のタグの不足（EAI-CORE-SYNTAX-002、`EAI-SYNTAX-TAG-REQUIRED[-DRAFT]`）。
CONDITION_TAG_REQUIRED = "tag-required"
#: 発動条件が複数（EAI-CORE-SYNTAX-003、`EAI-SYNTAX-TRIGGER-MULTIPLE[-DRAFT]`）。
CONDITION_TRIGGER_MULTIPLE = "trigger-multiple"
#: 句点の欠落（EAI-CORE-SYNTAX-006、`EAI-SYNTAX-PERIOD-MISSING[-DRAFT]`）。
CONDITION_PERIOD_MISSING = "period-missing"
#: オペランドの不足（EAI-CORE-SEM-001、`EAI-SEM-OPERAND-MISSING[-DRAFT]`）。
CONDITION_OPERAND_MISSING = "operand-missing"
#: `SHOULD`の理由フィールドの不足（EAI-CORE-SHOULD-001、`EAI-SHOULD-REASON-MISSING`）。`draft`に依存せず重大度`warning`に固定。
CONDITION_SHOULD_REASON_MISSING = "should-reason-missing"
#: 未知の名前空間の不透明な拡張タグ（EAI-EXT-UNKNOWN-001、`EAI-EXTENSION-UNKNOWN`）。
#: Core 1.0はプロファイルのマニフェストを読まないため、Coreが認識する名前空間は存在しない。
#: したがって出現した拡張は常にこの条件を伴い、`extensions`と`unknownExtensions`は常に一致する。
CONDITION_EXTENSION_UNKNOWN = "extension-unknown"

#: 構文が破綻し、意味中間表現を返せない条件（早期に`return`して意味中間表現なしになるもの）。
HARD_SYNTAX_CONDITIONS = frozenset(
    {
        CONDITION_CODE_UNCLOSED,
        CONDITION_TAG_UNCLOSED,
        CONDITION_ID_FORMAT,
        CONDITION_TAG_ORDER,
        CONDITION_TAG_REQUIRED,
        CONDITION_TRIGGER_MULTIPLE,
        CONDITION_PERIOD_MISSING,
        CONDITION_OPERAND_MISSING,
    }
)

#: 意味中間表現を返したうえで併せて返す条件（統語的には妥当だが警告条件を伴うもの）。
SOFT_CONDITIONS = frozenset({CONDITION_SHOULD_REASON_MISSING, CONDITION_EXTENSION_UNKNOWN})


def condition(kind: str, line: int, column: int, *, detail: str | None = None) -> dict:
    """1件の条件を組み立てる。`line`／`column`は、Unicodeのコードポイント単位で1始まり。

    `detail`は`CONDITION_TAG_UNCLOSED`の原因の種類（"escape"／"quote"／"unclosed"／"invalid"）
    をフェーズB（`document.py`）が文面の選択に使うための、保証せず可能な範囲で与える補助情報で、
    与えられたときだけ含める（他の種類（`kind`）は常に`None`、辞書には現れない）。
    """

    d = {"kind": kind, "line": line, "column": column}
    if detail is not None:
        d["detail"] = detail
    return d


def build_semantic_ir(
    *,
    statement_id: str,
    document_id: str,
    local_id: str,
    path: str,
    line: int,
    column: int,
    actor: str,
    activation: dict,
    modality: str,
    reason: str | None,
    operation: dict,
    extensions: list[dict],
    raw: str,
) -> dict:
    """§6のすべてのフィールドを規定の順で保持する、意味中間表現の辞書を組み立てる。

    Core 1.0はプロファイルのマニフェストを読まないため既知の名前空間が存在せず、`unknownExtensions`は
    常に`extensions`と同じ内容・同じ出現順のコピーになる（§3、`CONDITION_EXTENSION_UNKNOWN`参照）。
    """

    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": statement_id,
        "documentId": document_id,
        "localId": local_id,
        "source": {"path": path, "line": line, "column": column},
        "actor": actor,
        "activation": activation,
        "modality": modality,
        "reason": reason,
        "operation": operation,
        "extensions": extensions,
        "unknownExtensions": [dict(entry) for entry in extensions],
        "untrustedText": True,
        "raw": raw,
    }
