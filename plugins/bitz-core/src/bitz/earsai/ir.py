"""Semantic IRの形（EARS-AI仕様 §6）と構文条件kindの定数。

severity・`resultStatus`・draft差分の判定はDiagnostic registry
（`docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md` §4）が所有し、Phase Bが
文書のstatus（draft／それ以外）を見て決める。本moduleとparser.pyはそれを決めず、
「どの条件が成立したか」というconditionのkindだけを返す。kindからDiagnostic
`conditionId`／codeへの対応表はPhase B側に置く。
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

#: 未閉鎖code span（EAI-CORE-SYNTAX-005、`EAI-SYNTAX-CODE-UNCLOSED[-DRAFT]`）。
CONDITION_CODE_UNCLOSED = "code-unclosed"
#: 不正escape・未閉鎖quoted value・不正／未閉鎖tag（EAI-CORE-SYNTAX-004、`EAI-SYNTAX-TAG-UNCLOSED[-DRAFT]`）。
CONDITION_TAG_UNCLOSED = "tag-unclosed"
#: 規範文ID形式不正（EAI-CORE-ID-001、`EAI-ID-FORMAT`）。
CONDITION_ID_FORMAT = "id-format"
#: 規範文ID重複（EAI-CORE-ID-002、`EAI-ID-DUPLICATE`）。draftでもerrorのため単一。
CONDITION_ID_DUPLICATE = "id-duplicate"
#: tag順序不正（EAI-CORE-SYNTAX-001、`EAI-SYNTAX-TAG-ORDER[-DRAFT]`）。
CONDITION_TAG_ORDER = "tag-order"
#: 必須tag不足（EAI-CORE-SYNTAX-002、`EAI-SYNTAX-TAG-REQUIRED[-DRAFT]`）。
CONDITION_TAG_REQUIRED = "tag-required"
#: 発動条件複数（EAI-CORE-SYNTAX-003、`EAI-SYNTAX-TRIGGER-MULTIPLE[-DRAFT]`）。
CONDITION_TRIGGER_MULTIPLE = "trigger-multiple"
#: 句点欠落（EAI-CORE-SYNTAX-006、`EAI-SYNTAX-PERIOD-MISSING[-DRAFT]`）。
CONDITION_PERIOD_MISSING = "period-missing"
#: operand不足（EAI-CORE-SEM-001、`EAI-SEM-OPERAND-MISSING[-DRAFT]`）。
CONDITION_OPERAND_MISSING = "operand-missing"
#: SHOULDの理由field不足（EAI-CORE-SHOULD-001、`EAI-SHOULD-REASON-MISSING`）。draft非依存でwarning固定。
CONDITION_SHOULD_REASON_MISSING = "should-reason-missing"
#: 未知namespaceのopaque extension（EAI-EXT-UNKNOWN-001、`EAI-EXTENSION-UNKNOWN`）。
#: Core 1.0はProfile Manifestを読まないため、Coreが認識するnamespaceは存在しない。
#: したがって出現した拡張は常にこの条件を伴い、`extensions`と`unknownExtensions`は常に一致する。
CONDITION_EXTENSION_UNKNOWN = "extension-unknown"

#: 構文が破綻し、Semantic IRを返せない条件（早期returnでIRなしになるもの）。
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

#: IRを返したうえで併せて返す条件（統語的には妥当だが警告条件を伴うもの）。
SOFT_CONDITIONS = frozenset({CONDITION_SHOULD_REASON_MISSING, CONDITION_EXTENSION_UNKNOWN})


def condition(kind: str, line: int, column: int) -> dict:
    """1件のconditionを組み立てる。`line`／`column`は1始まりUnicode code point単位。"""

    return {"kind": kind, "line": line, "column": column}


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
    """§6の全fieldを規定順で保持するSemantic IR辞書を組み立てる。

    Core 1.0はProfile Manifestを読まないため既知namespaceが存在せず、`unknownExtensions`は
    常に`extensions`と同じ内容・同じ出現順のcopyになる（§3、CONDITION_EXTENSION_UNKNOWN参照）。
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
