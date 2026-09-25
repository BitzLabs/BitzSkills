"""Diagnostic summary文面を1箇所に集約する。

`Diagnostic registry`（`docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md`）の各条件に
対応する利用者向け日本語文面をここへ集める。可変部分（field名、doc種別名など）は引数で埋める。
fixtureのexpected/*.jsonが`summary`を完全一致で比較するため、文言はここだけで管理し、
呼び出し側（frontmatter.py／document.py／earsai_bridge.py／check.py）はこのmoduleの関数だけを使う。
"""

from __future__ import annotations

import re

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


# --- 関係・trace（`RELATION-*`、`TRACE-*`） -------------------------------------

#: text出力の制御文字無害化（`結果・Diagnostic・終了コード仕様 §7`）と同じ判定を、
#: summaryへ埋め込むpath自体にも使う（制御文字を含むpathを埋め込む場合だけ経路情報を
#: summaryへ足す。通常pathは埋め込まない固定文言を使う）。
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f\x80-\x9f]")

RELATION_MISSING_STRONG = "strong relationの参照先が存在しません"


def relation_missing_strong(source_path: str) -> str:
    if _CONTROL_CHAR_RE.search(source_path):
        return f"参照元{source_path}のstrong relation参照先が存在しません"
    return RELATION_MISSING_STRONG


def relation_type_mismatch(source_kind: str, target_kind: str, relation: str) -> str:
    return f"{source_kind}から{target_kind}への{relation}は許可されません"


def relation_cycle(relation: str) -> str:
    return f"{relation}に禁止循環があります"


RELATION_LEGACY_REFS = "旧refs fieldは使用できません"
RELATION_ADVISORY_MISSING = "relatedの参照先が存在しません"

IMPLEMENTS_PATH_MISSING = "実装pathが存在しません"
IMPLEMENTS_PATH_DRAFT = "draftの実装pathは未作成です"
TEST_PATH_MISSING = "testのpathが存在しません"
TEST_PATH_DRAFT = "draftのtest pathは未作成です"

TEST_COVERAGE_INVALID = "coversが存在しない規範文を参照しています"


# --- TASK境界（`CHECK-TASK-*`） -----------------------------------------------

def task_boundary_violation(path: str, task_id: str) -> str:
    return f"{path}は{task_id}の許可変更path外です"


def task_boundary_no_git(task_id: str) -> str:
    return f"Git不在のため{task_id}の変更境界を検査できません"


# --- 明示対象の解決（`CTX-ROOT-MISSING-*`） -------------------------------------

def root_missing_explicit(target: str) -> str:
    return f"起点{target}が存在しません"


# --- 状態遷移・管理済みSPEC削除（`CHECK-STATE-*`） ------------------------------

DOCUMENT_DELETED = "管理済みSPECが削除されています"


def state_transition_forbidden(kind: str, from_status: str, to_status: str) -> str:
    return f"{from_status} {kind}を{to_status}へ戻すことはできません"


# --- 承認済みREQ保護（`CHECK-APPROVED-MEANING`） --------------------------------

APPROVED_MEANING_CHANGED = "approved REQの意味変更時にstatusが戻されていません"


# --- 影響候補（`CHECK-IMPACT-OUTDATED`） ---------------------------------------

def impact_outdated(source_id: str, changed_id: str) -> str:
    return f"{source_id}が強く依存する{changed_id}が変更されています。再確認してください"


# --- Git縮退（`CHECK-GIT-DEGRADED`） -------------------------------------------

GIT_DEGRADED_FULL_FALLBACK = (
    "Git不在のため全体checkへ縮退します。"
    "承認済みREQ保護、状態遷移、管理済みSPEC削除の差分検査は実施できません"
)


# --- report保存（`REPORT-WRITE`） ----------------------------------------------

REPORT_WRITE_FAILED = "report保存先へ排他的に作成できません"


# --- context（`CTX-*`） -----------------------------------------------------


def task_dependency_incomplete(prereq_task_id: str) -> str:
    return f"先行{prereq_task_id}が完了していません"


def state_inapplicable(doc_id: str) -> str:
    return f"{doc_id}は現在のpurposeに適用できません"


def state_superseded_origin(doc_id: str, successor_id: str) -> str:
    return f"起点{doc_id}は{successor_id}に置換されています"


def state_superseded_dependency(doc_id: str, successor_id: str) -> str:
    return f"依存先{doc_id}は{successor_id}に置換されています"


def state_superseded_multiple(doc_id: str) -> str:
    return f"{doc_id}の有効な後継が複数存在します"


CTX_LIMIT_DOCUMENTS = "完全Context閉包が文書数上限を超過しました"
CTX_LIMIT_BYTES = "完全Context閉包がbyte上限を超過しました"


def coverage_task_unaddressed(modality: str, stmt_id: str) -> str:
    return f"implement対象の{modality} {stmt_id}を実装するTASKがありません"


def coverage_test_untested(modality: str, stmt_id: str) -> str:
    return f"{modality} {stmt_id}がtestされていません"


def projection_outside(expand_id: str) -> str:
    return f"expand対象{expand_id}は完全解決集合にありません"


def projection_limit_exceeded(detail: str) -> str:
    return f"detail {detail}の提示量が1 MiBのhard limitを超過します"


CTX_STALE_MISMATCH = "期待Digestが現在のContext Digestと一致しません"


# --- verify command argv（設定`SPEC-CONFIG-SCHEMA-001`） --------------------------

CONFIG_ARGV_LENGTH_INVALID = "argv templateは256要素以下で指定してください"
CONFIG_ARGV_ELEMENT_NOT_STRING = "argvの要素はstringで指定してください"
CONFIG_ARGV_FIRST_EMPTY = "argv[0]は空stringにできません"
CONFIG_ARGV_ELEMENT_NUL = "argvの要素にNULは使用できません"
CONFIG_ARGV_ELEMENT_TOO_LONG = "argvの各要素はUTF-8で32 KiB以下で指定してください"


# --- verify（`SPEC-VERIFY-*`、`CTX-STATE-*`） ------------------------------------

VERIFY_TARGETS_EMPTY = "verify対象が0件です"
VERIFY_SPAWN_ERROR = "commandの実行形式をOSが拒否しprocessを生成できません"
VERIFY_SIGNAL = "commandがsignalで終了しました"
VERIFY_EXECUTABLE_UNAVAILABLE = "command実行fileをPATHから解決できません"
VERIFY_ARGV_EXPANDED_LIMIT = "{tests}展開後のargvがbyte上限1 MiBを超えます"
VERIFY_CONFIG_UNTRACKED = "設定fileがGit管理下で未追跡です"
VERIFY_TEST_OUTSIDE_CWD = "test pathが実効cwd配下にありません"


def verify_timeout(seconds: int) -> str:
    return f"commandが実効timeout {seconds}秒で終了しませんでした"


def verify_command_undefined(name: str) -> str:
    return f"command名{name}が設定に定義されていません"


def verify_coverage_untested(modality: str, stmt_id: str) -> str:
    return f"対象{modality} {stmt_id}にtest対応がありません"


def verify_executable_unavailable_path() -> str:
    return "command実行fileを解決できません"


def verify_argv_expanded_count_limit() -> str:
    return "{tests}展開後のargvの要素数が上限10,000を超えます"


def verify_cwd_unavailable() -> str:
    return "command cwdが利用できません"


def state_task_cancelled(doc_id: str) -> str:
    return f"起点{doc_id}はcancelledでありverifyに適用できません"


# --- 複合workspace（`SPEC-MULTI-*`） ---------------------------------------------

MULTI_CONFIG_NOT_MAP = "multiWorkspaceはmapで指定してください"
MULTI_CONFIG_MEMBERS_REQUIRED = "multiWorkspace.membersは1件以上指定してください"
MULTI_CONFIG_MEMBERS_TYPE = "multiWorkspace.membersは配列で指定してください"
MULTI_CONFIG_MEMBER_ENTRY_TYPE = "multiWorkspace.membersの要素はmapで指定してください"
MULTI_CONFIG_MAX_MEMBERS_RANGE = "multiWorkspace.maxMembersは1〜100のintegerで指定してください"

MEMBER_CONFIG_MISSING = "memberの.spec/bitz.yamlがありません"
MEMBER_ID_MISMATCH = "memberの設定workspace.idがcatalogのidと一致しません"
MEMBER_NESTED_MULTIWORKSPACE = "memberはmultiWorkspaceを宣言できません"

MULTI_ID_INVALID = "workspace idの形式が不正です"
MULTI_ID_DUPLICATE = "workspace idが複合workspace内で重複しています"

MULTI_PATH_INVALID = "member pathの形式が不正です"
MULTI_PATH_DUPLICATE = "member pathが重複しています"
MULTI_PATH_NESTED = "member pathが別のmemberの配下にあります"
MULTI_PATH_SYMLINK = "member pathの経路にsymlinkが含まれています"
MULTI_PATH_SUBMODULE = "member pathがGit submoduleです"
MULTI_PATH_WORKTREE = "member pathが別のworktreeです"
MULTI_PATH_SEPARATE_REPO = "member pathが別のGit repositoryです"

MULTI_GIT_BOUNDARY_UNKNOWN = "Git repositoryの境界を確定できません"

MULTI_VERSION_SCHEMA_MAJOR = "memberのschemaVersionが未対応majorです"
MULTI_VERSION_EARS_MAJOR = "memberのearsAiが未対応majorです"

MULTI_UNREGISTERED = "Gitが認識する設定fileがcatalogに登録されていません"


def multi_limit_exceeded(dimension: str, limit: int) -> str:
    _LABELS = {
        "memberCount": "member数",
        "specFileCount": "SPEC file数",
        "inputBytes": "入力byte数",
        "statementCount": "規範文数",
        "relationEdgeCount": "relation edge数",
        "traceEntryCount": "trace項目数",
        "commandDefinitionCount": "command定義数",
        "verifyBindingCount": "verify binding数",
    }
    label = _LABELS.get(dimension, dimension)
    return f"{label}が上限{limit:,}を超過しました"


# --- 複合workspace修飾ID解決・所有境界（Step 5B、`SPEC-MULTI-REF-001`／`SPEC-MULTI-OWNERSHIP-001`） ---

MULTI_REF_QUALIFIER_INVALID = "修飾IDの形式が不正です"
MULTI_REF_UNQUALIFIED = "非修飾の参照先が別workspaceにだけ存在します"
MULTI_REF_WORKSPACE_UNKNOWN = "修飾workspaceがcatalogに存在しません"


def multi_ownership_resolved(path: str, workspace_id: str) -> str:
    return f"{path}の解決先が{workspace_id}の所有範囲外です"


def multi_ownership_symlink_base(path: str, workspace_id: str) -> str:
    return f"{path}の基準版のsymlinkが{workspace_id}の所有範囲外を指します"


def multi_ownership_symlink_current(path: str, workspace_id: str) -> str:
    return f"{path}の現在版のsymlinkが{workspace_id}の所有範囲外を指します"
