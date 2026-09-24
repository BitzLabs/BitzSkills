"""Diagnostic summary文面を1箇所に集約する。

`Diagnostic registry`（`docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md`）の各条件に
対応する利用者向け日本語文面をここへ集める。可変部分（field名、doc種別名など）は引数で埋める。
fixtureのexpected/*.jsonが`summary`を完全一致で比較するため、文言はここだけで管理し、
呼び出し側（frontmatter.py／document.py／earsai_bridge.py／check.py）はこのmoduleの関数だけを使う。
"""

from __future__ import annotations

# --- 入出力・上限（`INPUT-*`） -------------------------------------------------

SPEC_UTF8_INVALID = "SPEC fileをUTF-8として復号できません"
SPEC_IO_UNREADABLE = "SPEC fileを読み取れません"
SPEC_SIZE_LIMIT = "SPEC Markdownが1 MiB上限を超過しました"
FRONTMATTER_SIZE_LIMIT = "Frontmatterが32 KiB上限を超過しました"
STATEMENT_COUNT_LIMIT = "1文書の規範文数が1,000上限を超過しました"


def spec_file_count_limit(limit: int = 10_000) -> str:
    return f"SPEC fileが{limit:,}件上限を超過しました"


def array_count_limit(key: str) -> str:
    return "1文書の関係・path配列の項目数が1,000上限を超過しました"


SPEC_BOM = "SPEC file先頭のBOMを除いて解析を続行します"


# --- workspace探索 --------------------------------------------------------

WORKSPACE_UNKNOWN_ENTRY = ".spec/内の未知fileをSPECとして読みません"


# --- Frontmatter YAML構文層 -------------------------------------------------

FRONTMATTER_LABEL = "Frontmatter"
FRONTMATTER_YAML_LABEL = "Frontmatter YAML"


def frontmatter_yaml_syntax_invalid() -> str:
    return f"{FRONTMATTER_YAML_LABEL}の構文が不正です"


# --- Frontmatter field --------------------------------------------------

def fm_type_error(key: str, expected: str) -> str:
    return f"Frontmatter {key}は{expected}が必要です"


def fm_required_missing(key: str) -> str:
    return f"Frontmatterの必須field {key}がありません"


def fm_null_forbidden(key: str) -> str:
    return f"Frontmatter {key}にnullは指定できません"


def fm_empty_forbidden(key: str) -> str:
    return f"Frontmatter {key}は空文字列にできません"


TITLE_LENGTH_RULE = "Frontmatter titleは改行を含まない1〜120文字で指定してください"


def fm_id_format_invalid(kind: str) -> str:
    return f"Frontmatter idの形式が不正です"


def fm_status_invalid(kind: str) -> str:
    return "Frontmatter statusの値が不正です"


def fm_unavailable(kind_label: str, key: str) -> str:
    return f"{kind_label}では{key}を使用できません"


def fm_unknown_field(key: str) -> str:
    return "未知のFrontmatter fieldを無視します"


def fm_extension_invalid(key: str) -> str:
    return f"Frontmatter {key}はscalar・scalar配列・文字列keyのmapだけを使用できます"


def fm_relations_unknown_key(key: str) -> str:
    return f"relationsに未知のkey {key}があります"


def fm_relations_duplicate(key: str) -> str:
    return f"relations.{key}に重複した値があります"


def fm_array_duplicate(key: str) -> str:
    return f"{key}に重複した値があります"


TESTS_DUPLICATE = "testsに重複した要素があります"
TESTS_COVERS_EMPTY = "tests[].coversは1件以上指定してください"


def fm_tests_unknown_key(index: int, key: str) -> str:
    return f"testsの要素に未知のkey {key}があります"


# --- ID一意性・file名 ------------------------------------------------------

FILE_NAME_MISMATCH = "file名IDとFrontmatter IDが一致しません"


def doc_id_duplicate(doc_id: str) -> str:
    return f"文書ID {doc_id}が重複しています"


# --- REQ本文検査 ------------------------------------------------------------

REQ_STATEMENT_EMPTY = "approved REQに妥当な規範文がありません"

H1_MISSING = "H1がありません"
H1_MULTIPLE = "H1が複数あります"
H1_MISMATCH = "H1がFrontmatterと一致しません"


def section_missing(name: str) -> str:
    return f"REQ必須section {name}がありません"


def section_empty(name: str) -> str:
    return f"REQ必須section {name}が空です"


def placement_invalid(kind_label: str) -> str:
    return f"{kind_label}に規範行を配置できません"


# --- EARS-AI構文条件 ---------------------------------------------------

EAI_CODE_UNCLOSED = "code spanが閉じられていません"
EAI_TAG_UNCLOSED = "tagが閉じられていません"
EAI_UNKNOWN_ESCAPE = "未知のescapeです"
EAI_QUOTE_UNCLOSED = "extension値のquoteが閉じられていません"
EAI_TAG_INVALID = "tagが不正です"
EAI_ID_FORMAT = "規範文IDの形式が不正です"
EAI_ID_DUPLICATE = "規範文IDが重複しています"
EAI_TAG_ORDER = "tagの順序が不正です"
EAI_TAG_REQUIRED = "必須tagが不足しています"
EAI_TRIGGER_MULTIPLE = "発動条件が複数あります"
EAI_PERIOD_MISSING = "規範文末の句点がありません"
EAI_OPERAND_MISSING = "operandが不足しています"
EAI_SHOULD_REASON_MISSING = "SHOULDに[REASON]がありません"
EAI_EXTENSION_UNKNOWN = "未知namespaceのextensionを保持します"
