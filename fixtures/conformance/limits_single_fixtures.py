"""単一ワークスペースで、`bitz.yaml`の`limits`による上限の設定を固定する（Coreの公開操作は実行しない）。

[ADR-076](../../docs/02.設計書/10_決定記録/ADR-076_上限の値を設定で小さくできるようにし、実寸の上限の検証を手動にする.md)は、
上限の値を`limits`で小さくできるようにし、上限の境界の判定を小さい上限のfixtureで固定すると定める（適合fixture仕様 §3.4）。
この群は、単一ワークスペースの`doctor`の`limits`の出力、`limits`の設定の検査、入力の上限（安全な入出力・互換性 §4.1）、
`{tests}`を展開した後の引数列の上限、複合ワークスペース用のキーを使わないこと、コンテキストのハッシュ値の材料に含めないことを、36件で固定する。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-183-01` | `doctor` | `SINGLE-001`の設定に`limits: {}` | `passed`／0。`limits`は15キーすべて絶対上限 |
| `SINGLE-183-02` | `doctor` | `SINGLE-001`の設定に`limits`の2キー（`expandedArgvBytes: 4096`、`specFileCount: 5`の順に書く） | `passed`／0。`limits`はその2キーの値と残りの絶対上限 |
| `SINGLE-183-03` | `check --full --base HEAD` | `limits`の15キーすべてが絶対上限ちょうど | `passed`／0。診断なし |
| `SINGLE-183-04` | `check --full --base HEAD` | `limits: 1024`（マッピングでない） | `error`／3。`SPEC-CONFIG-SCHEMA-001`（`source.key`は`limits`） |
| `SINGLE-183-05` | `check --full --base HEAD` | `limits`の中の未知のキー`futureLimit: 1` | `passed_with_warnings`／0。`SPEC-CONFIG-UNKNOWN-001`（`source.key`は`limits.futureLimit`） |
| `SINGLE-180-01`、`02` | `check --full --base HEAD` | `specBytes`が仕様文書の大きさちょうど／1小さい | `passed`／`failed`（`SPEC-INPUT-LIMIT-001`） |
| `SINGLE-180-03`、`04` | 同上 | `frontmatterBytes`がフロントマターの大きさ（区切りの行を除き、改行を含む）ちょうど／1小さい | `passed`／`failed` |
| `SINGLE-180-12`、`13` | 同上 | `180-03`・`04`と同じ文書をCRLFの改行にし、同じ`frontmatterBytes`（改行は正規化した後の1バイトで数える） | `passed`／`failed` |
| `SINGLE-180-05`、`06` | 同上 | `documentStatementCount: 3`で規範文が3件／4件 | `passed`／`failed` |
| `SINGLE-180-07`、`08` | 同上 | `documentArrayItemCount: 3`で`covers`が3件／4件 | `passed`／`failed`（`source.key`は`tests[0].covers`） |
| `SINGLE-180-11` | 同上 | `SINGLE-079-01`の設定に`limits.specBytes: 1048576`（絶対上限と同じ値を明示） | `SINGLE-079-01`と同じ結果（文言は`1 MiB上限`のまま） |
| `SINGLE-180-09`、`10` | 同上 | `specFileCount`が2／1で仕様文書が2件 | `passed`／`failed`（`SPEC-INPUT-LIMIT-001`、発生元は`.spec`） |
| `SINGLE-180-14` | `context REQ-001` | `SINGLE-180-10`と同じ入力 | `failed`／1。`SPEC-INPUT-LIMIT-001`の1件だけ。操作を止め、`contextDigest: null`、空の`documents` |
| `SINGLE-180-15` | `verify REQ-001` | `SINGLE-180-10`と同じ入力 | `failed`／1。`SPEC-INPUT-LIMIT-001`の1件だけ。操作を止め、`targetResults`と`commands`は空 |
| `SINGLE-180-16` | `verify REQ-001` | `SINGLE-055`の設定に`specFileCount: 3`（仕様文書の数ちょうど） | `SINGLE-055`と同じ結果 |
| `SINGLE-181` | `context REQ-001 --purpose verify` | `SINGLE-042`の設定に、どの上限も超えない`limits` | `SINGLE-042`と同じ結果。`contextDigest`も同じ |
| `SINGLE-182-01` | `verify REQ-001` | `SINGLE-055`の設定に`expandedArgvCount: 3`（展開した後の要素数ちょうど） | `SINGLE-055`と同じ結果 |
| `SINGLE-182-02`、`03` | 同上 | `expandedArgvElementBytes`が最長の要素のバイト数ちょうど／1小さい | `passed`／`blocked`（`SPEC-VERIFY-BLOCKED-001`） |
| `SINGLE-182-04`、`05` | 同上 | `expandedArgvBytes`が要素のバイト数の総和ちょうど／1小さい | `passed`／`blocked` |
| `SINGLE-182-06` | 同上 | 複合ワークスペースのスナップショット全体の次元のキーをすべて1にする | `SINGLE-055`と同じ結果 |
| `SINGLE-182-07` | 同上 | `expandedArgvCount: 2`（展開した後の要素は3件） | `blocked`（`SPEC-VERIFY-BLOCKED-001`） |
| `SINGLE-183-06`〜`10` | `check --full --base HEAD` | `limits`の値が0、負、絶対上限+1、真偽値、文字列 | `error`／3。`SPEC-CONFIG-SCHEMA-001`（`source.key`は`limits.<キー>`） |
| `SINGLE-183-12` | `check --full --base HEAD` | 値のない`limits:` | `error`／3。`SINGLE-183-04`と同じ |
| `SINGLE-183-11` | `doctor` | `SINGLE-092`の形で、設定の`limits.specBytes`が0 | `error`／3。`limits`を返さない（`doctor` §7） |

期待値の根拠は規範文（安全な入出力・互換性 §4・§4.1、ワークスペース・設定仕様 §5・§6、文書・フロントマター・状態仕様 §11、
コンテキストのハッシュ値の正規化仕様 §3、`doctor` §7、結果・診断・終了コード §2・§5、診断レジストリ）と、承認済みの文言
（`Coreの出力文言のレビュー記録.md`の#22・#41・#80と、2026-11-17の上限の設定の承認済みの対応表）だけである。小さい値を設定したときの`summary`は、
§4.1の規則による。単位を付けた表記（`1 MiB`、`32 KiB`）を持つ文言はその表記を3桁区切りの整数に`バイト`を付けた表記へ置き換え、
値を数として持つ文言は今の形のまま実際の値を3桁区切りの整数で入れる。Coreの出力は根拠にしない。
`SINGLE-180-11`・`16`・`181`・`182-*`・`183-01`・`02`・`11`は、レビュー済みの既存のfixture（`SINGLE-001`・`042`・`055`・`079-01`・`092`）の入力の設定へ`limits`の行を足し、
期待結果をそこから導く。基のfixtureの入力か期待値が変われば、この群の監査が失敗する。

引数列のバイト数は、YAML表記、配列の区切り、終端のNULを含めず、各文字列のUTF-8のバイト数とその総和で測り、展開した後も公開結果の`argv`で測る
（ワークスペース・設定仕様 §6）ので、ちょうどの境界を固定する。フロントマターの大きさは、改行を正規化した後（CRLFとCRをLFへ置き換えた後）の本文で、
開始と終了の区切りの行の間の各行を、その行の改行（1バイト）を含めて数え、区切りの行自身は含めない（文書・フロントマター・状態仕様 §11）ので、
ちょうどの境界を固定する。`SINGLE-180-12`・`13`の文書はCRLFの改行で、原文のバイト数で数えるとちょうどの側も超過になる。CRLFの原文を
リポジトリの`* text=auto eol=lf`で正規化させないため、fixtureのディレクトリに`.gitattributes`（`repo/`の文書の`-text`）を置く。

仕様文書のファイル数の超過（`INPUT-LIMIT-SPEC-COUNT`）は、`parse`の操作（`context`、`check`、`verify`）のどれでも`stop-operation`である（診断レジストリ §2・§3）。
`SINGLE-180-14`・`15`は、`SINGLE-180-10`と同じ入力で`context`と`verify`も操作全体を止めることを固定する。起点の`REQ-001`は存在するので、
`CTX-ROOT-MISSING-001`を返してはならない。設定を読んで同一性を構成した後、仕様文書を解析する前に止まるので、`workspace.id`は`root`、
派生する配列は空、派生する件数は0とし（結果・診断・終了コード §2）、`context`は`contextDigest: null`、`resolution.complete: false`、
空の`documents`・制約台帳・カバレッジを返す。結果の形は、同一性を構成した後に`stop-operation`で止まる既存のfixture
（`context`は`MULTI-040-08`・`MULTI-036-07`、`verify`は`SINGLE-165-01`）と、明示した起点で止まる`SINGLE-166-02`・`SINGLE-126-01`に倣う。
`SINGLE-180-16`は、`verify`でちょうどの仕様文書の数を遮断しないこと（`context`のちょうどの境界は`SINGLE-181`が固定する）を固定する。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .input_limit_fixtures import REQUIREMENT_2, TEST_FILE, TEST_PATH, covers_ids, requirement
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
REQ2_PATH = ".spec/requirements/REQ-002.md"
COMMIT = "0" * 40
CONFIG = CONFIGS["SINGLE-001"]
# 安全な入出力・互換性 §4.1の表。キーの順はこの表の順（`doctor` §7）。値は絶対上限。
ABSOLUTE = {
    "specBytes": 1048576,
    "frontmatterBytes": 32768,
    "specFileCount": 10000,
    "documentStatementCount": 1000,
    "documentArrayItemCount": 1000,
    "inputBytes": 268435456,
    "statementCount": 100000,
    "relationEdgeCount": 1000000,
    "traceEntryCount": 1000000,
    "commandDefinitionCount": 10000,
    "verifyBindingCount": 10000,
    "excludeCount": 100,
    "expandedArgvCount": 10000,
    "expandedArgvElementBytes": 32768,
    "expandedArgvBytes": 1048576,
}
# 複合ワークスペースのスナップショット全体へ適用する次元（複合ワークスペース仕様 §10）。単一ワークスペースでは使わない（§4.1）。
SNAPSHOT_KEYS = ("inputBytes", "statementCount", "relationEdgeCount", "traceEntryCount",
                 "commandDefinitionCount", "verifyBindingCount")
LIMIT_CODE = "SPEC-INPUT-LIMIT-001"
VERIFY_BLOCKED = "SPEC-VERIFY-BLOCKED-001"
ARGV_KEY = "verify.commands.default.argv"
SINGLE_055_ARGV = ["/bin/true", "tests/test_auth.py", "tests/test_session.py"]


def count_text(value):
    """件数の上限の表記（§4.1。3桁区切りの整数）。"""
    return f"{value:,}"


def bytes_text(value):
    """バイト数の上限の表記（§4.1。3桁区切りの整数に`バイト`）。"""
    return f"{value:,}バイト"


def limits_block(entries):
    """`limits`のYAMLの行。`entries`は(キー, 値)の列で、書いた順に並べる。空なら空のマッピングを宣言する。"""
    if not entries:
        return "limits: {}\n"
    return "limits:\n" + "".join(f"  {key}: {value}\n" for key, value in entries)


def effective_limits(entries):
    """`doctor`が返す`limits`。表の順にすべてのキーを持ち、設定した値か絶対上限を使う（`doctor` §7）。"""
    values = dict(entries)
    return {key: values.get(key, absolute) for key, absolute in ABSOLUTE.items()}


# --- 入力 -------------------------------------------------------------------------------------

def frontmatter_content(document):
    """区切りの行（`---`とLF）の間のバイト列。LFの文書だけに使う。"""
    parts = document.split(b"---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError("文書に区切られたフロントマターがありません")
    return parts[1]


def frontmatter_size(document):
    """フロントマターの大きさ（文書・フロントマター・状態仕様 §11）。改行を正規化した後（CRLFとCRをLFへ置き換えた後）の本文で、
    開始と終了の区切りの行の間にある各行を、その行の改行（1バイト）を含めて数えたUTF-8のバイト数の合計。区切りの行自身は含めない。"""
    lines = document.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")
    if lines[0] != b"---" or b"---" not in lines[1:]:
        raise ValueError("文書に区切られたフロントマターがありません")
    end = lines.index(b"---", 1)
    return sum(len(line) + 1 for line in lines[1:end])


def raw_frontmatter_size(document):
    """原文のまま（改行を正規化せずに）区切りの行の間を数えた大きさ。CRLFの文書で、正規化した数え方と結論が分かれることを確かめるためだけに使う。"""
    lines = document.split(b"\n")
    end = next(index for index in range(1, len(lines)) if lines[index].rstrip(b"\r") == b"---")
    return sum(len(line) + 1 for line in lines[1:end])


def crlf(document):
    """すべての改行をCRLFにした文書。"""
    if b"\r" in document:
        raise ValueError("CRを含む文書はCRLFへ変換しません")
    return document.replace(b"\n", b"\r\n")


DOCUMENT_BYTES = DOCUMENT.encode()
DOCUMENT_SIZE = len(DOCUMENT_BYTES)
DOCUMENT_CRLF = crlf(DOCUMENT_BYTES)
FRONTMATTER_SIZE = frontmatter_size(DOCUMENT_BYTES)
# CRLFの原文を`* text=auto eol=lf`（リポジトリの`.gitattributes`）で正規化させない。fixtureのディレクトリに置き、`repo/`の文書だけに当てる。
GITATTRIBUTES = f"repo/{REQ_PATH} -text\n"
ARGV_TOTAL = sum(len(value.encode()) for value in SINGLE_055_ARGV)
ARGV_LONGEST = max(len(value.encode()) for value in SINGLE_055_ARGV)


def case(kind, step, description, **values):
    return dict(kind=kind, step=step, description=description, **values)


CASES = {
    "SINGLE-183-01": case("doctor", 1, "limitsを空のマッピングで宣言したdoctorはlimitsに15キーすべての絶対上限を返す",
                          base="SINGLE-001", limits=[]),
    "SINGLE-183-02": case("doctor", 1, "limitsの一部のキーを小さくしたdoctorはその値と残りの絶対上限を表の順に返す",
                          base="SINGLE-001", limits=[("expandedArgvBytes", 4096), ("specFileCount", 5)]),
    "SINGLE-183-03": case("config", 1, "limitsの15キーすべてが絶対上限ちょうどの設定を受け入れる",
                          limits=list(ABSOLUTE.items()), status="passed"),
    "SINGLE-183-04": case("config", 1, "マッピングでないlimitsを設定の型の不正にする",
                          raw="limits: 1024\n", status="error"),
    "SINGLE-183-05": case("config", 1, "limitsの中の未知のキーを警告にし判定に使わない",
                          limits=[("futureLimit", 1)], status="passed_with_warnings"),
    "SINGLE-183-06": case("config", 1, "limitsの値が0なら設定の値の範囲の不正にする",
                          raw="limits:\n  specBytes: 0\n", status="error", key="specBytes"),
    "SINGLE-183-07": case("config", 1, "limitsの値が負なら設定の値の範囲の不正にする",
                          raw="limits:\n  documentStatementCount: -1\n", status="error", key="documentStatementCount"),
    "SINGLE-183-08": case("config", 1, "limitsの値が絶対上限を1超えれば設定の値の範囲の不正にする",
                          raw="limits:\n  expandedArgvBytes: 1048577\n", status="error", key="expandedArgvBytes"),
    "SINGLE-183-09": case("config", 1, "limitsの値が真偽値なら設定の型の不正にする",
                          raw="limits:\n  specFileCount: true\n", status="error", key="specFileCount"),
    "SINGLE-183-10": case("config", 1, "limitsの値が文字列なら設定の型の不正にする",
                          raw='limits:\n  statementCount: "5"\n', status="error", key="statementCount"),
    "SINGLE-183-12": case("config", 1, "値のないlimitsを設定の型の不正にする",
                          raw="limits:\n", status="error"),
    "SINGLE-183-11": case("doctor-invalid", 1, "limitsの値が不正な設定のdoctorはlimitsを返さない",
                          base="SINGLE-092", raw="limits:\n  specBytes: 0\n", key="specBytes"),
    "SINGLE-180-01": case("input", 2, "specBytesが仕様文書の大きさちょうどなら遮断しない",
                          limits=[("specBytes", DOCUMENT_SIZE)], document="plain", status="passed"),
    "SINGLE-180-02": case("input", 2, "仕様文書がspecBytesを1バイト超えれば文書を検査しない",
                          limits=[("specBytes", DOCUMENT_SIZE - 1)], document="plain", status="failed",
                          summary=f"仕様文書のMarkdownが{bytes_text(DOCUMENT_SIZE - 1)}上限を超過しました"),
    "SINGLE-180-03": case("input", 2, "frontmatterBytesがフロントマターの大きさちょうどなら遮断しない",
                          limits=[("frontmatterBytes", FRONTMATTER_SIZE)], document="plain", status="passed"),
    "SINGLE-180-04": case("input", 2, "フロントマターがfrontmatterBytesを1バイト超えれば文書を検査しない",
                          limits=[("frontmatterBytes", FRONTMATTER_SIZE - 1)], document="plain", status="failed",
                          summary=f"フロントマターが{bytes_text(FRONTMATTER_SIZE - 1)}上限を超過しました"),
    "SINGLE-180-12": case("input", 2, "CRLFの改行のフロントマターも改行を1バイトとして数えfrontmatterBytesちょうどなら遮断しない",
                          limits=[("frontmatterBytes", FRONTMATTER_SIZE)], document="crlf", status="passed"),
    "SINGLE-180-13": case("input", 2, "CRLFの改行のフロントマターがfrontmatterBytesを1バイト超えれば文書を検査しない",
                          limits=[("frontmatterBytes", FRONTMATTER_SIZE - 1)], document="crlf", status="failed",
                          summary=f"フロントマターが{bytes_text(FRONTMATTER_SIZE - 1)}上限を超過しました"),
    "SINGLE-180-05": case("input", 2, "documentStatementCountちょうどの規範文を遮断しない",
                          limits=[("documentStatementCount", 3)], document="statements-3", status="passed"),
    "SINGLE-180-06": case("input", 2, "1文書の規範文がdocumentStatementCountを1件超えれば文書を検査しない",
                          limits=[("documentStatementCount", 3)], document="statements-4", status="failed",
                          summary=f"1文書の規範文数が{count_text(3)}上限を超過しました"),
    "SINGLE-180-07": case("input", 2, "documentArrayItemCountちょうどの配列を遮断しない",
                          limits=[("documentArrayItemCount", 3)], document="covers-3", status="passed"),
    "SINGLE-180-08": case("input", 2, "1文書の配列の項目がdocumentArrayItemCountを1件超えれば文書を検査しない",
                          limits=[("documentArrayItemCount", 3)], document="covers-4", status="failed",
                          summary=f"1文書の関係・パスの配列の項目数が{count_text(3)}上限を超過しました"),
    "SINGLE-180-09": case("input", 2, "specFileCountちょうどの仕様文書の数を遮断しない",
                          limits=[("specFileCount", 2)], document="two-files", status="passed"),
    "SINGLE-180-11": case("derived", 2, "絶対上限と同じspecBytesを明示した超過の文言は絶対上限のときのまま",
                          base="SINGLE-079-01", limits=[("specBytes", ABSOLUTE["specBytes"])]),
    "SINGLE-180-10": case("input", 2, "仕様文書のファイル数がspecFileCountを1超えれば操作を止める",
                          limits=[("specFileCount", 1)], document="two-files", status="failed",
                          summary=f"仕様文書のファイルが{count_text(1)}件上限を超過しました"),
    "SINGLE-180-14": case("input-stop", 3, "仕様文書のファイル数がspecFileCountを1超えればcontextも操作を止める",
                          operation="context", limits=[("specFileCount", 1)], document="two-files", status="failed",
                          summary=f"仕様文書のファイルが{count_text(1)}件上限を超過しました"),
    "SINGLE-180-15": case("input-stop", 4, "仕様文書のファイル数がspecFileCountを1超えればverifyも操作を止める",
                          operation="verify", limits=[("specFileCount", 1)], document="two-files", status="failed",
                          summary=f"仕様文書のファイルが{count_text(1)}件上限を超過しました"),
    "SINGLE-180-16": case("derived", 4, "specFileCountちょうどの仕様文書の数のverifyを止めない",
                          base="SINGLE-055", limits=[("specFileCount", 3)]),
    "SINGLE-181": case("derived", 3, "limitsはコンテキストのハッシュ値の材料に含めない",
                       base="SINGLE-042", limits=None),
    "SINGLE-182-01": case("derived", 4, "expandedArgvCountちょうどの引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvCount", len(SINGLE_055_ARGV))]),
    "SINGLE-182-02": case("derived", 4, "最長の要素がexpandedArgvElementBytesちょうどの引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvElementBytes", ARGV_LONGEST)]),
    "SINGLE-182-03": case("argv-blocked", 4, "要素がexpandedArgvElementBytesを超える引数列のテスト割当てを起動しない",
                          base="SINGLE-055", limits=[("expandedArgvElementBytes", ARGV_LONGEST - 1)],
                          summary=f"{{tests}}展開後のargvの要素がバイト数上限{bytes_text(ARGV_LONGEST - 1)}を超えます"),
    "SINGLE-182-04": case("derived", 4, "全体のバイト数がexpandedArgvBytesちょうどの引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvBytes", ARGV_TOTAL)]),
    "SINGLE-182-05": case("argv-blocked", 4, "全体のバイト数がexpandedArgvBytesを超える引数列のテスト割当てを起動しない",
                          base="SINGLE-055", limits=[("expandedArgvBytes", ARGV_TOTAL - 1)],
                          summary=f"{{tests}}展開後のargvがバイト数上限{bytes_text(ARGV_TOTAL - 1)}を超えます"),
    "SINGLE-182-06": case("derived", 4, "単一ワークスペースは複合ワークスペースのスナップショット全体の次元のキーを使わない",
                          base="SINGLE-055", limits=[(key, 1) for key in SNAPSHOT_KEYS]),
    "SINGLE-182-07": case("argv-blocked", 4, "要素数がexpandedArgvCountを超える引数列のテスト割当てを起動しない",
                          base="SINGLE-055", limits=[("expandedArgvCount", len(SINGLE_055_ARGV) - 1)],
                          summary=f"{{tests}}展開後のargvの要素数が上限{count_text(len(SINGLE_055_ARGV) - 1)}を超えます"),
}


def base_fixture(identifier):
    return HERE / "single" / CASES[identifier]["base"]


def read_tree(directory):
    """fixtureの`repo/`を(パス -> (バイト列, 実行ビット))で読む。シンボリックリンクは扱わない。"""
    tree = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("基のfixtureの入力にシンボリックリンクがあります")
        if path.is_file():
            tree[path.relative_to(directory).as_posix()] = (path.read_bytes(), bool(path.stat().st_mode & 0o111))
    return tree


def context_limits():
    """`SINGLE-181`の`limits`。基の入力の文書を測り直し、どの上限も超えない値にする（ハッシュ値だけを見るため）。"""
    tree = read_tree(HERE / "single/SINGLE-042/repo")
    documents = [content for path, (content, _) in tree.items() if path.endswith(".md")]
    return [
        ("specBytes", max(len(content) for content in documents) + 1),
        ("frontmatterBytes", max(len(frontmatter_content(content)) for content in documents) + 2 * len(b"---\n")),
        ("specFileCount", len(documents)),
        ("documentStatementCount", 2),
        ("documentArrayItemCount", 2),
        ("expandedArgvCount", 1),
        ("expandedArgvElementBytes", 1),
        ("expandedArgvBytes", 1),
    ]


def limits_of(identifier):
    value = CASES[identifier].get("limits")
    return context_limits() if identifier == "SINGLE-181" else value


def config_text(identifier):
    case_ = CASES[identifier]
    if "raw" in case_:
        return CONFIG + case_["raw"]
    return CONFIG + limits_block(limits_of(identifier))


def document_inputs(kind):
    if kind == "plain":
        return {REQ_PATH: DOCUMENT_BYTES}
    if kind == "crlf":
        return {REQ_PATH: DOCUMENT_CRLF}
    if kind == "statements-3":
        return {REQ_PATH: requirement(3, covers_ids(3)), TEST_PATH: TEST_FILE}
    if kind == "statements-4":
        return {REQ_PATH: requirement(4, covers_ids(3)), TEST_PATH: TEST_FILE}
    if kind == "covers-3":
        return {REQ_PATH: requirement(3, covers_ids(3)), TEST_PATH: TEST_FILE}
    if kind == "covers-4":
        return {REQ_PATH: requirement(3, covers_ids(3) + ["REQ-002:AC-01"]), REQ2_PATH: REQUIREMENT_2.encode(),
                TEST_PATH: TEST_FILE}
    if kind == "two-files":
        return {REQ_PATH: DOCUMENT_BYTES, REQ2_PATH: REQUIREMENT_2.encode()}
    raise ValueError(f"未知の文書の種類です: {kind}")


def reviewed_inputs(identifier):
    """`repo/`の(パス -> (バイト列, 実行ビット))。"""
    case_ = CASES[identifier]
    if case_["kind"] == "doctor-invalid":
        # 基の`SINGLE-092`（設定の型の不正の`doctor`）の入力の設定だけを、`SINGLE-001`の最小設定に不正な`limits`を足したものに置き換える。
        tree = read_tree(base_fixture(identifier) / "repo")
        tree[CONFIG_PATH] = (config_text(identifier).encode(), tree[CONFIG_PATH][1])
        return tree
    if "base" in case_:
        tree = read_tree(base_fixture(identifier) / "repo")
        content, executable = tree[CONFIG_PATH]
        tree[CONFIG_PATH] = (content + limits_block(limits_of(identifier)).encode(), executable)
        return tree
    inputs = {CONFIG_PATH: config_text(identifier).encode()}
    if case_["kind"] in {"input", "input-stop"}:
        inputs.update(document_inputs(case_["document"]))
    return {path: (content, False) for path, content in inputs.items()}


# --- 期待値 -----------------------------------------------------------------------------------

def operation(identifier):
    case_ = CASES[identifier]
    if case_["kind"] in {"doctor", "doctor-invalid"}:
        return "doctor"
    if case_["kind"] in {"config", "input"}:
        return "check"
    if case_["kind"] == "input-stop":
        return case_["operation"]
    return json.loads((base_fixture(identifier) / "manifest.json").read_text())["invocation"]["argv"][0]


def reviewed_manifest(identifier):
    case_ = CASES[identifier]
    name = operation(identifier)
    if "base" in case_:
        manifest = json.loads((base_fixture(identifier) / "manifest.json").read_text())
        manifest["fixtureId"] = identifier
        manifest["description"] = case_["description"]
        if case_["kind"] == "argv-blocked":
            manifest["expect"].update(status="blocked", exitCode=2)
        return manifest
    status = case_["status"]
    # `context`と`verify`は`--base`を持たない。起点は`SINGLE-180-10`の入力に存在する`REQ-001`とする。
    argv = ([name, "REQ-001", "--format", "json"] if case_["kind"] == "input-stop"
            else ["check", "--full", "--base", "HEAD", "--format", "json"])
    return {"fixtureId": identifier, "description": case_["description"],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
            "expect": {"status": status,
                       "exitCode": {"passed": 0, "passed_with_warnings": 0, "failed": 1, "error": 3}[status],
                       "stdout": "json", "resultFile": f"expected/{name}.json", "reportFileCount": 0}}


def check_result(status, documents, statements, diagnostics, identity="root"):
    return {"schemaVersion": "1.0", "operation": "check", "status": status,
            "workspace": {"id": identity, "path": "."}, "durationMs": 0, "diagnostics": diagnostics,
            "scope": "full", "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": documents, "checkedStatementCount": statements}


def empty_coverage():
    levels = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}
    return {"must": copy.deepcopy(levels), "should": copy.deepcopy(levels), "may": copy.deepcopy(levels), "adjacent": []}


def stopped_result(name, status, diagnostics):
    """同一性を構成した後、仕様文書を解析する前に`stop-operation`で止まった`context`または`verify`の結果。
    派生する配列は空、派生する件数は0（結果・診断・終了コード §2）。コミットがあるので`revision`を返し、作業ツリーは基準版と同じ。"""
    revision = {"commit": COMMIT, "dirty": False}
    if name == "context":
        # 起点は引数のまま。既定の目的は`interpret`、既定の詳細度は`standard`（`context` §2）。形は`SINGLE-166-02`・`MULTI-040-08`と同じ。
        return {"schemaVersion": "1.0", "operation": "context", "status": status, "purpose": "interpret",
                "workspace": {"id": "root", "path": "."}, "roots": ["REQ-001"], "contextDigest": None,
                "revision": revision,
                "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
                "projection": {"detail": "standard", "expanded": []}, "documents": [],
                "constraintLedger": {"statements": []}, "coverage": empty_coverage(),
                "durationMs": 0, "diagnostics": diagnostics}
    # 明示した検証対象は`scope: selected`。検証対象の解決を始めないので`targetResults`と`commands`は空（`SINGLE-126-01`・`SINGLE-165-01`と同じ形）。
    return {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
            "workspace": {"id": "root", "path": "."}, "targetResults": [], "revision": revision, "commands": [],
            "durationMs": 0, "diagnostics": diagnostics}


def diagnostic(code, severity, status, summary, path, key=None, identity="root"):
    source = {"kind": "file", "workspaceId": identity, "path": path}
    if key is not None:
        source["key"] = key
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": source}


# 入力の上限のfixtureの検査件数（文書、規範文）。`skip-document`で上限を超えた文書は数えない（診断レジストリ）。
INPUT_COUNTS = {"SINGLE-180-01": (1, 1), "SINGLE-180-02": (0, 0), "SINGLE-180-03": (1, 1), "SINGLE-180-04": (0, 0),
                "SINGLE-180-05": (1, 3), "SINGLE-180-06": (0, 0), "SINGLE-180-07": (1, 3), "SINGLE-180-08": (1, 1),
                "SINGLE-180-09": (2, 2), "SINGLE-180-10": (0, 0), "SINGLE-180-12": (1, 1), "SINGLE-180-13": (0, 0)}


def reviewed_result(identifier):
    case_ = CASES[identifier]
    kind = case_["kind"]
    if kind == "doctor":
        result = json.loads((base_fixture(identifier) / "expected/doctor.json").read_text())
        result["limits"] = effective_limits(case_["limits"])
        return result
    if kind == "doctor-invalid":
        # 設定がスキーマに適合しないときは`limits`を返さない（`doctor` §7）。結果の形は`SINGLE-092`と同じで、診断だけが異なる。
        result = json.loads((base_fixture(identifier) / "expected/doctor.json").read_text())
        result["diagnostics"] = [range_diagnostic(case_["key"])]
        return result
    if kind == "derived":
        # `limits`はどの上限も超えず、コンテキストのハッシュ値の材料にも含めないので、基のfixtureと同じ結果になる。
        name = operation(identifier)
        return json.loads((base_fixture(identifier) / f"expected/{name}.json").read_text())
    if kind == "argv-blocked":
        # `SINGLE-126-08`と同じ形: テスト割当てを起動せず、最上位に1件、検証対象は`blocked`で`bindingRefs: []`。
        result = json.loads((base_fixture(identifier) / "expected/verify.json").read_text())
        result["status"] = "blocked"
        for target in result["targetResults"]:
            target.update(status="blocked", bindingRefs=[])
        result["commands"] = []
        result["diagnostics"] = [diagnostic(VERIFY_BLOCKED, "error", "blocked", case_["summary"], CONFIG_PATH, ARGV_KEY)]
        return result
    if kind == "config":
        if identifier in {"SINGLE-183-04", "SINGLE-183-12"}:
            # 設定の型の不正では同一性を構成できない（結果・診断・終了コード §5）。文言は承認済みの#22。
            return check_result("error", 0, 0, [diagnostic(
                "SPEC-CONFIG-SCHEMA-001", "error", "error", "設定キーlimitsはマッピングで指定してください",
                CONFIG_PATH, "limits", identity=None)], identity=None)
        if "key" in case_:
            return check_result("error", 0, 0, [range_diagnostic(case_["key"])], identity=None)
        if identifier == "SINGLE-183-05":
            return check_result("passed_with_warnings", 0, 0, [diagnostic(
                "SPEC-CONFIG-UNKNOWN-001", "warning", "passed_with_warnings", "未知の設定キーです",
                CONFIG_PATH, "limits.futureLimit")])
        return check_result("passed", 0, 0, [])
    if kind == "input-stop":
        # 仕様文書のファイル数の超過は`stop-operation`で、発生元はワークスペース相対の`.spec`（§4.1）。ほかの診断を返さない。
        return stopped_result(case_["operation"], case_["status"], [
            diagnostic(LIMIT_CODE, "error", "failed", case_["summary"], ".spec")])
    documents, statements = INPUT_COUNTS[identifier]
    diagnostics = []
    if case_["status"] == "failed":
        key = "tests[0].covers" if identifier == "SINGLE-180-08" else None
        # 仕様文書のファイル数の超過（`stop-operation`）の発生元はワークスペース相対の`.spec`（§4.1）。
        path = ".spec" if identifier == "SINGLE-180-10" else REQ_PATH
        diagnostics.append(diagnostic(LIMIT_CODE, "error", "failed", case_["summary"], path, key))
    return check_result(case_["status"], documents, statements, diagnostics)


def range_diagnostic(key):
    """`limits`の値の型と範囲の不正（ワークスペース・設定仕様 §5）。文言は承認済みの`設定キー{key}は1〜{max}の整数で指定してください`。
    設定の型の不正では同一性を構成できないので、`workspaceId`は`null`（結果・診断・終了コード §5）。"""
    return diagnostic("SPEC-CONFIG-SCHEMA-001", "error", "error",
                      f"設定キーlimits.{key}は1〜{ABSOLUTE[key]}の整数で指定してください", CONFIG_PATH, f"limits.{key}",
                      identity=None)


def expected_name(identifier):
    return f"expected/{operation(identifier)}.json"


# --- 測り直し -----------------------------------------------------------------------------

def statement_count(document):
    return sum(1 for line in document.splitlines() if line.startswith(b"- [REQ-"))


def covers_count(document):
    return sum(1 for line in document.splitlines() if line.startswith(b"      - REQ-"))


def check_measurements(identifier, inputs):
    """入力のバイト列を測り直し、狙った上限だけをちょうど、または1だけ超えることを確かめる。"""
    case_ = CASES[identifier]
    limits = dict(limits_of(identifier) or [])
    for key, value in limits.items():
        if key in ABSOLUTE and not 1 <= value <= ABSOLUTE[key]:
            raise ValueError(f"{key}の値が1以上、絶対上限以下ではありません")
    if case_["kind"] in {"input", "input-stop"}:
        document = inputs[REQ_PATH][0]
        measured = {"specBytes": len(document), "documentStatementCount": statement_count(document),
                    "documentArrayItemCount": covers_count(document),
                    "specFileCount": sum(1 for path in inputs if path.endswith(".md"))}
        key, value = next(iter(limits.items()))
        over = case_["status"] == "failed"
        if key == "frontmatterBytes":
            # 文書・フロントマター・状態仕様 §11の数え方で、ちょうど上限または上限+1にする。
            if frontmatter_size(document) != (value + 1 if over else value):
                raise ValueError("フロントマターの大きさがちょうど上限または上限+1ではありません")
            if case_["document"] == "crlf":
                # すべての改行がCRLFで、原文のまま数えるとちょうどの側も超過になる（改行の正規化を確かめる入力である）。
                if document != crlf(document.replace(b"\r\n", b"\n")) or raw_frontmatter_size(document) <= value + 1:
                    raise ValueError("CRLFの文書が改行の正規化を区別しません")
            elif b"\r" in document:
                raise ValueError("LFの文書がCRを含みます")
        elif measured[key] != (value + 1 if over else value):
            raise ValueError(f"{key}の実測がちょうど上限または上限+1ではありません")
        for other, absolute in ABSOLUTE.items():
            if other in measured and other != key and measured[other] > absolute:
                raise ValueError(f"{other}も上限を超えています")
    if identifier == "SINGLE-180-16":
        # 基の`SINGLE-055`の仕様文書（`.spec/`の配下のMarkdown）の数が、設定した上限ちょうどである。
        count = sum(1 for path in inputs if path.startswith(".spec/") and path.endswith(".md"))
        if count != limits.get("specFileCount") or sum(1 for path in inputs if path.endswith(".md")) != count:
            raise ValueError("仕様文書の数がspecFileCountちょうどではありません")
    if identifier.startswith("SINGLE-182-"):
        # 基の`SINGLE-055`の`{tests}`を展開した後の引数列を、基の期待結果から読み直す。
        base = json.loads((base_fixture(identifier) / "expected/verify.json").read_text())
        argv = base["commands"][0]["argv"]
        if argv != SINGLE_055_ARGV:
            raise ValueError("基のfixtureの展開した後の引数列が想定と異なります")
        sizes = [len(value.encode()) for value in argv]
        checks = {
            "SINGLE-182-01": len(argv) == limits.get("expandedArgvCount"),
            # 各文字列のUTF-8のバイト数とその総和で測る（終端のNULを含めない。ワークスペース・設定仕様 §6）。
            "SINGLE-182-02": max(sizes) == limits.get("expandedArgvElementBytes"),
            "SINGLE-182-03": max(sizes) == limits.get("expandedArgvElementBytes", 0) + 1,
            "SINGLE-182-04": sum(sizes) == limits.get("expandedArgvBytes"),
            "SINGLE-182-05": sum(sizes) == limits.get("expandedArgvBytes", 0) + 1,
            "SINGLE-182-06": set(limits) == set(SNAPSHOT_KEYS),
            "SINGLE-182-07": len(argv) == limits.get("expandedArgvCount", 0) + 1,
        }
        if not checks[identifier]:
            raise ValueError("引数列の測り直しがレビュー済みの上限と一致しません")


# --- 生成と監査 ---------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def observed_states(fixture, manifest, prefix):
    states = []
    with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append(observe(repository, external))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def write_tree(directory, tree):
    for relative, (content, executable) in tree.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o755 if executable else 0o644)


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        fixture.mkdir(parents=True, exist_ok=False)
        if CASES[identifier].get("document") == "crlf":
            (fixture / ".gitattributes").write_text(GITATTRIBUTES)
        write_tree(fixture / "repo", reviewed_inputs(identifier))
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir()
        (fixture / expected_name(identifier)).write_text(_dump(reviewed_result(identifier)))
        state = observed_states(fixture, manifest, "bitz-limits-single-")
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def check_tree(directory, expected):
    actual = read_tree(directory) if directory.is_dir() else {}
    if actual != expected:
        raise ValueError(f"`{directory.name}`の入力がレビュー済みの入力と異なります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / expected_name(identifier)).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("マニフェストがレビュー済みの起動と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("期待結果がレビュー済みの期待値と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {Path(expected_name(identifier)).name}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            if (fixture / "changes").exists():
                raise ValueError("この群は`changes`を持ちません")
            attributes = fixture / ".gitattributes"
            if CASES[identifier].get("document") == "crlf":
                if not attributes.is_file() or attributes.read_text() != GITATTRIBUTES:
                    raise ValueError("CRLFの文書を正規化させない`.gitattributes`がレビュー済みの内容と異なります")
            elif attributes.exists():
                raise ValueError("CRLFの文書のないfixtureは`.gitattributes`を持ちません")
            inputs = reviewed_inputs(identifier)
            check_tree(fixture / "repo", inputs)
            check_measurements(identifier, inputs)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("上限の判定はファイルを書いてはいけません")
            state = observed_states(fixture, manifest, "bitz-limits-single-")
            if compare_state(effects["before"], state):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
