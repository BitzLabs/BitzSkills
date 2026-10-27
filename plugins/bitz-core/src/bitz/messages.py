"""診断の`summary`の文面を1箇所に集約する。

診断レジストリ（`docs/03.詳細設計/00_共通契約/05_診断レジストリ.md`）の各条件に
対応する、利用者向けの日本語の文面をここへ集める。可変の部分（フィールド名、文書種別名など）は引数で埋める。
fixtureの`expected/*.json`が`summary`を完全一致で比較するため、文言はここだけで管理し、
呼び出し側（`frontmatter.py`／`document.py`／`earsai_bridge.py`／`check.py`）はこのモジュールの関数だけを使う。
"""

from __future__ import annotations

import re

# --- 入出力・上限（`INPUT-*`） -------------------------------------------------

SPEC_UTF8_INVALID = "仕様文書のファイルをUTF-8として復号できません"
SPEC_IO_UNREADABLE = "仕様文書のファイルを読み取れません"
SPEC_SIZE_LIMIT = "仕様文書のMarkdownが1 MiB上限を超過しました"
FRONTMATTER_SIZE_LIMIT = "フロントマターが32 KiB上限を超過しました"
STATEMENT_COUNT_LIMIT = "1文書の規範文数が1,000上限を超過しました"


def spec_file_count_limit(limit: int = 10_000) -> str:
    return f"仕様文書のファイルが{limit:,}件上限を超過しました"


def array_count_limit(key: str) -> str:
    return "1文書の関係・パスの配列の項目数が1,000上限を超過しました"


SPEC_BOM = "仕様文書のファイル先頭のBOMを除いて解析を続行します"


# --- ワークスペースの探索 --------------------------------------------------------

WORKSPACE_UNKNOWN_ENTRY = ".spec/内の未知のファイルを仕様文書として読みません"


# --- フロントマターのYAML構文の層 -------------------------------------------------

FRONTMATTER_LABEL = "フロントマター"
FRONTMATTER_YAML_LABEL = "フロントマターのYAML"


def frontmatter_yaml_syntax_invalid() -> str:
    return f"{FRONTMATTER_YAML_LABEL}の構文が不正です"


# --- フロントマターのフィールド --------------------------------------------------

def fm_type_error(key: str, expected: str) -> str:
    return f"フロントマターのフィールド{key}は{expected}が必要です"


def fm_required_missing(key: str) -> str:
    return f"フロントマターの必須フィールド{key}がありません"


def fm_null_forbidden(key: str) -> str:
    return f"フロントマターのフィールド{key}にnullは指定できません"


def fm_empty_forbidden(key: str) -> str:
    return f"フロントマターのフィールド{key}は空文字列にできません"


TITLE_LENGTH_RULE = "フロントマターのフィールドtitleは改行を含まない1〜120文字で指定してください"


def fm_id_format_invalid(kind: str) -> str:
    return f"フロントマターのフィールドidの形式が不正です"


def fm_status_invalid(kind: str) -> str:
    return "フロントマターのフィールドstatusの値が不正です"


def fm_unavailable(kind_label: str, key: str) -> str:
    return f"{kind_label}ではフィールド{key}を使用できません"


def fm_unknown_field(key: str) -> str:
    return "未知のフロントマターのフィールドを無視します"


def fm_extension_invalid(key: str) -> str:
    return f"フロントマターのフィールド{key}はスカラー・スカラーの配列・文字列のキーを持つマッピングだけを使用できます"


def fm_relations_unknown_key(key: str) -> str:
    return f"フィールドrelationsに未知のキー{key}があります"


def fm_relations_duplicate(key: str) -> str:
    return f"フィールドrelations.{key}に重複した値があります"


def fm_array_duplicate(key: str) -> str:
    return f"フィールド{key}に重複した値があります"


TESTS_DUPLICATE = "フィールドtestsに重複した要素があります"
TESTS_COVERS_EMPTY = "フィールドtests[].coversは1件以上指定してください"


def fm_tests_unknown_key(index: int, key: str) -> str:
    return f"フィールドtestsの要素に未知のキー{key}があります"


# --- IDの一意性・ファイル名 ------------------------------------------------------

FILE_NAME_MISMATCH = "ファイル名のIDとフロントマターのIDが一致しません"


def doc_id_duplicate(doc_id: str) -> str:
    return f"文書ID {doc_id}が重複しています"


# --- REQ本文検査 ------------------------------------------------------------

REQ_STATEMENT_EMPTY = "状態approvedのREQに妥当な規範文がありません"

H1_MISSING = "H1がありません"
H1_MULTIPLE = "H1が複数あります"
H1_MISMATCH = "H1がフロントマターと一致しません"


def section_missing(name: str) -> str:
    return f"REQの必須の節{name}がありません"


def section_empty(name: str) -> str:
    return f"REQの必須の節{name}が空です"


def placement_invalid(kind_label: str) -> str:
    return f"{kind_label}に規範文を配置できません"


# --- EARS-AI構文条件 ---------------------------------------------------

EAI_CODE_UNCLOSED = "コードスパンが閉じられていません"
EAI_TAG_UNCLOSED = "タグが閉じられていません"
EAI_UNKNOWN_ESCAPE = "未知のエスケープです"
EAI_QUOTE_UNCLOSED = "拡張タグの値の引用符が閉じられていません"
EAI_TAG_INVALID = "タグが不正です"
EAI_ID_FORMAT = "規範文IDの形式が不正です"
EAI_ID_DOCUMENT_MISMATCH = "規範文IDの文書部分が文書IDと一致しません"
EAI_ID_DUPLICATE = "規範文IDが重複しています"
EAI_TAG_ORDER = "タグの順序が不正です"
EAI_TAG_REQUIRED = "必須のタグが不足しています"
EAI_TRIGGER_MULTIPLE = "発動条件が複数あります"
EAI_PERIOD_MISSING = "規範文末の句点がありません"
EAI_OPERAND_MISSING = "オペランドが不足しています"
EAI_SHOULD_REASON_MISSING = "SHOULDに[REASON]がありません"
EAI_EXTENSION_UNKNOWN = "未知の名前空間の拡張タグを保持します"


# --- 関係・トレース（`RELATION-*`、`TRACE-*`） -------------------------------------

#: テキスト出力の制御文字の無害化（結果・診断・終了コード §7）と同じ判定を、
#: `summary`へ埋め込むパス自体にも使う（制御文字を含むパスを埋め込む場合だけ経路情報を
#: `summary`へ足す。通常のパスは埋め込まない固定の文言を使う）。
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f\x80-\x9f]")

RELATION_MISSING_STRONG = "強い関係の参照先が存在しません"


def relation_missing_strong(source_path: str) -> str:
    if _CONTROL_CHAR_RE.search(source_path):
        return f"参照元{source_path}の強い関係の参照先が存在しません"
    return RELATION_MISSING_STRONG


def relation_type_mismatch(source_kind: str, target_kind: str, relation: str) -> str:
    return f"{source_kind}から{target_kind}への関係型{relation}は許可されません"


def relation_requires_adr_not_accepted(source_kind: str, status: str) -> str:
    """承認されていないADRへの`requires`。種別の組合せの文型の参照先の部分にだけ状態を添える。"""

    return f"{source_kind}から状態{status}のADRへの関係型requiresは許可されません"


def relation_cycle(relation: str) -> str:
    return f"関係型{relation}に禁止された循環があります"


RELATION_LEGACY_REFS = "旧フィールドrefsは使用できません"
RELATION_ADVISORY_MISSING = "関係型relatedの参照先が存在しません"

IMPLEMENTS_PATH_MISSING = "実装パスが存在しません"
IMPLEMENTS_PATH_DRAFT = "状態draftの実装パスは未作成です"
TEST_PATH_MISSING = "テストのパスが存在しません"
TEST_PATH_DRAFT = "状態draftのテストのパスは未作成です"

# 参照先の不在と、対応できない参照（`refines`していない規範文など）の両方に使う（C67。2026-10-26に管理者が承認。一字も変えない）。
TEST_COVERAGE_INVALID = "フィールドcoversの参照先が存在しないか、対応できません"


# --- TASK境界（`CHECK-TASK-*`） -----------------------------------------------

def task_boundary_violation(path: str, task_id: str) -> str:
    return f"パス{path}は{task_id}の変更許可パスの外です"


def task_boundary_no_git(task_id: str) -> str:
    return f"Git不在のため{task_id}のTASK境界を検査できません"


# --- 明示対象の解決（`CTX-ROOT-MISSING-*`） -------------------------------------

def root_missing_explicit(target: str) -> str:
    return f"起点{target}が存在しません"


# --- 状態遷移・管理済みの仕様文書の削除（`CHECK-STATE-*`） ------------------------------

DOCUMENT_DELETED = "管理済みの仕様文書が削除されています"


def state_transition_forbidden(kind: str, from_status: str, to_status: str) -> str:
    return f"状態{from_status}の{kind}を状態{to_status}へ戻すことはできません"


# --- 承認済み要求の保護（`CHECK-APPROVED-MEANING`） --------------------------------

APPROVED_MEANING_CHANGED = "状態approvedのREQの意味変更時に文書の状態が戻されていません"


# --- 影響候補（`CHECK-IMPACT-OUTDATED`） ---------------------------------------

def impact_outdated(source_id: str, changed_id: str) -> str:
    return f"{source_id}が強く依存する{changed_id}が変更されています。再確認してください"


# --- Git縮退（`CHECK-GIT-DEGRADED`） -------------------------------------------

GIT_DEGRADED_FULL_FALLBACK = (
    "Git不在のため全体検査へ縮退します。"
    "承認済み要求の保護、状態遷移、管理済みの仕様文書の削除の差分検査は実施できません"
)


# --- レポートの保存（`REPORT-WRITE`） ----------------------------------------------

REPORT_WRITE_FAILED = "レポートの保存先へ排他的に作成できません"


# --- `context`操作（`CTX-*`） -----------------------------------------------------


def task_dependency_incomplete(prereq_task_id: str, status: str) -> str:
    return f"先行する{prereq_task_id}が状態{status}で、状態doneではありません"


def task_dependency_suggested_action(prereq_task_id: str) -> str:
    return f"先行する{prereq_task_id}を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください"


def state_inapplicable(doc_id: str, status: str, purpose: str) -> str:
    return f"{doc_id}は状態{status}のため目的{purpose}に適用できません"


def state_superseded_origin(doc_id: str, successor_id: str) -> str:
    return f"起点{doc_id}は{successor_id}に置換されています"


def state_superseded_dependency(doc_id: str, successor_id: str) -> str:
    return f"依存先{doc_id}は{successor_id}に置換されています"


def state_superseded_multiple(doc_id: str) -> str:
    return f"{doc_id}の有効な後継が複数存在します"


CTX_LIMIT_DOCUMENTS = "コンテキストの完全な閉包が文書数上限を超過しました"
CTX_LIMIT_BYTES = "コンテキストの完全な閉包がバイト数上限を超過しました"


def coverage_task_unaddressed(modality: str, stmt_id: str) -> str:
    return f"目的implementの対象規範文{modality} {stmt_id}を実装するTASKがありません"


def coverage_test_untested(modality: str, stmt_id: str) -> str:
    return f"対象規範文{modality} {stmt_id}にテスト対応がありません"


def projection_outside(expand_id: str) -> str:
    return f"展開指定の対象{expand_id}は完全解決した集合にありません"


def projection_limit_exceeded(detail: str) -> str:
    return f"詳細度{detail}の提示量が1 MiBの絶対上限を超過します"


CTX_STALE_MISMATCH = "期待したハッシュ値が現在のコンテキストのハッシュ値と一致しません"


# --- `verify`のテストコマンドの引数列（設定`SPEC-CONFIG-SCHEMA-001`） --------------------------

CONFIG_ARGV_LENGTH_INVALID = "引数列テンプレートは256要素以下で指定してください"
CONFIG_ARGV_ELEMENT_NOT_STRING = "argvの要素は文字列で指定してください"
CONFIG_ARGV_FIRST_EMPTY = "argv[0]は空文字列にできません"
CONFIG_ARGV_ELEMENT_NUL = "argvの要素にNULは使用できません"
CONFIG_ARGV_ELEMENT_TOO_LONG = "argvの各要素はUTF-8で32 KiB以下で指定してください"


# --- `verify`操作（`SPEC-VERIFY-*`、`CTX-STATE-*`） ------------------------------------

VERIFY_TARGETS_EMPTY = "検証対象がありません"
VERIFY_SPAWN_ERROR = "コマンドの実行形式をOSが拒否しプロセスを生成できません"
VERIFY_SIGNAL = "コマンドがシグナルで終了しました"
VERIFY_EXECUTABLE_UNAVAILABLE = "コマンドの実行可能ファイルを環境変数PATHから解決できません"
VERIFY_ARGV_EXPANDED_LIMIT = "{tests}展開後のargvがバイト数上限1 MiBを超えます"
VERIFY_CONFIG_UNTRACKED = "設定ファイルがGit管理下で未追跡です"
VERIFY_TEST_OUTSIDE_CWD = "テストのパスが実効の作業ディレクトリの配下にありません"


def verify_timeout(seconds: int) -> str:
    return f"コマンドが実効タイムアウト{seconds}秒で終了しませんでした"


def verify_command_undefined(name: str) -> str:
    return f"コマンド名{name}が設定に定義されていません"


def verify_coverage_untested(modality: str, stmt_id: str) -> str:
    return coverage_test_untested(modality, stmt_id)


def verify_executable_unavailable_path() -> str:
    return "コマンドの実行可能ファイルを解決できません"


def verify_argv_expanded_count_limit() -> str:
    return "{tests}展開後のargvの要素数が上限10,000を超えます"


def verify_cwd_unavailable() -> str:
    return "コマンドの作業ディレクトリが利用できません"


# --- 複合ワークスペース（`SPEC-MULTI-*`） ---------------------------------------------

MULTI_CONFIG_NOT_MAP = "設定キーmultiWorkspaceはマッピングで指定してください"
MULTI_CONFIG_MEMBERS_REQUIRED = "設定キーmultiWorkspace.membersは1件以上指定してください"
MULTI_CONFIG_MEMBERS_TYPE = "設定キーmultiWorkspace.membersは配列で指定してください"
MULTI_CONFIG_MEMBER_ENTRY_TYPE = "設定キーmultiWorkspace.membersの要素はマッピングで指定してください"
MULTI_CONFIG_MAX_MEMBERS_RANGE = "設定キーmultiWorkspace.maxMembersは1〜100の整数で指定してください"
# ルートワークスペースのIDの省略（C42。2026-10-25に管理者が承認。一字も変えない）。
MULTI_CONFIG_ROOT_ID_REQUIRED = "ルートワークスペースの設定キーworkspace.idがありません"
# 除外の指定（ADR-064の8。管理者が承認した7件の一つ。一字も変えない）。
MULTI_CONFIG_EXCLUDE_TYPE = "設定キーmultiWorkspace.excludeは文字列の配列で指定してください"
MULTI_CONFIG_EXCLUDE_COUNT = "設定キーmultiWorkspace.excludeは100件以下で指定してください"
MULTI_EXCLUDE_INVALID = "除外のパスの形式が不正です"
MULTI_EXCLUDE_DUPLICATE = "除外のパスが重複しています"
MULTI_EXCLUDE_NESTED = "除外のパスが別の除外のパスの配下にあります"
MULTI_EXCLUDE_SPEC = "除外のパスに.specが含まれています"

MEMBER_CONFIG_MISSING = "メンバーの.spec/bitz.yamlがありません"
MEMBER_ID_MISMATCH = "メンバーの設定キーworkspace.idがカタログのIDと一致しません"
MEMBER_NESTED_MULTIWORKSPACE = "メンバーは設定キーmultiWorkspaceを宣言できません"

MULTI_ID_INVALID = "ワークスペースIDの形式が不正です"
MULTI_ID_DUPLICATE = "ワークスペースIDが複合ワークスペース内で重複しています"

MULTI_PATH_INVALID = "メンバーのパスの形式が不正です"
MULTI_PATH_DUPLICATE = "メンバーのパスが重複しています"
MULTI_PATH_NESTED = "メンバーのパスが別のメンバーの配下にあります"
MULTI_PATH_SYMLINK = "メンバーのパスの経路にシンボリックリンクが含まれています"
MULTI_PATH_SUBMODULE = "メンバーのパスがGitのサブモジュールです"
MULTI_PATH_WORKTREE = "メンバーのパスが別のワークツリーです"
MULTI_PATH_SEPARATE_REPO = "メンバーのパスが別のGitのリポジトリです"
MULTI_PATH_EXCLUDED = "メンバーのパスが除外した範囲にあります"

MULTI_GIT_BOUNDARY_UNKNOWN = "Gitのリポジトリの境界を確定できません"

MULTI_VERSION_SCHEMA_MAJOR = "メンバーの設定キーschemaVersionのメジャーバージョンが未対応です"
MULTI_VERSION_EARS_MAJOR = "メンバーの設定キーearsAiのメジャーバージョンが未対応です"

MULTI_UNREGISTERED = "Gitが認識する設定ファイルがカタログに登録されていません"
# 単独操作が選んだ最も近い設定の照合（複合ワークスペース仕様 §3の4・§7、ADR-063）。
MULTI_UNREGISTERED_SELECTED = "選択した設定ファイルがカタログに登録されていません"


MULTI_VERIFY_TARGETS_EMPTY = "検証対象がありません"

MULTI_DEPENDENCY_CONTEXT = "依存するワークスペースの非成功によりコンテキストを構成できません"


def multi_limit_exceeded(dimension: str, limit: int) -> str:
    _LABELS = {
        "memberCount": "メンバー数",
        "specFileCount": "仕様文書のファイル数",
        "inputBytes": "入力バイト数",
        "statementCount": "規範文数",
        "relationEdgeCount": "関係のエッジ数",
        "traceEntryCount": "トレースのエントリ数",
        "commandDefinitionCount": "コマンド定義数",
        "verifyBindingCount": "テスト割当て数",
    }
    label = _LABELS.get(dimension, dimension)
    return f"{label}が上限{limit:,}を超過しました"


# --- 複合ワークスペースの修飾ID解決・所有境界（Step 5B、`SPEC-MULTI-REF-001`／`SPEC-MULTI-OWNERSHIP-001`） ---

MULTI_REF_QUALIFIER_INVALID = "修飾IDの形式が不正です"
MULTI_REF_UNQUALIFIED = "非修飾の参照先が別のワークスペースにだけ存在します"
MULTI_REF_WORKSPACE_UNKNOWN = "修飾したワークスペースがカタログに存在しません"


def multi_ownership_resolved(path: str, workspace_id: str) -> str:
    return f"パス{path}の解決先がワークスペース{workspace_id}の所有領域の外です"


def multi_ownership_symlink_base(path: str, workspace_id: str) -> str:
    return f"パス{path}の基準版のシンボリックリンクがワークスペース{workspace_id}の所有領域の外を指します"


def multi_ownership_symlink_current(path: str, workspace_id: str) -> str:
    return f"パス{path}の現在版のシンボリックリンクがワークスペース{workspace_id}の所有領域の外を指します"


# --- doctorのプラグインの要求（`SPEC-DOCTOR-PLUGIN-001`／`SPEC-DOCTOR-API-001`／`SPEC-DOCTOR-CAPABILITY-001`、ADR-061） ---

DOCTOR_PLUGIN_REQUEST_INCOMPLETE = "プラグインの要求が不完全です"
DOCTOR_API_INCOMPATIBLE = "CoreのAPIのバージョンがプラグインの要求する範囲を満たしません"
DOCTOR_CAPABILITY_MISSING = "プラグインの要求する対応機能をCoreが公開していません"


# --- doctorの診断の`suggestedAction`（`04_doctor.md` §1・§8、ADR-062 Decision 2。管理者が2026-10-12に承認した文言） ---

DOCTOR_RUNTIME_VERSION_ACTION = "CPython 3.12以上でCoreを実行してください"
DOCTOR_PLUGIN_REQUEST_ACTION = "--plugin、--plugin-version、--require-core-apiを同時に指定してください"
DOCTOR_EARS_VERSION_ACTION = "設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください"
DOCTOR_GIT_DEGRADED_ACTION = "Git 2.30以上をインストールし、ワークスペースをGitのリポジトリで管理してください"


def doctor_api_incompatible_action(required: str, core_api: str) -> str:
    return f"範囲{required}を満たすCoreへ更新するか、Core APIのバージョン{core_api}に対応するプラグインを使ってください"


def doctor_capability_missing_action(missing: list[str]) -> str:
    return f"対応機能{'、'.join(missing)}を公開するCoreへ更新するか、プラグインの要求を見直してください"


def doctor_command_cwd_action(name: str) -> str:
    return f"設定キーverify.commands.{name}.cwdのディレクトリを作成するか、正しいパスを指定してください"


def doctor_command_file_action(name: str) -> str:
    return f"設定キーverify.commands.{name}.argvの先頭の実行可能ファイルをインストールするか、正しいパスを指定してください"
