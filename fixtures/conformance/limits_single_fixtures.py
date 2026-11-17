"""単一ワークスペースで、`bitz.yaml`の`limits`による上限の設定を固定する（Coreの公開操作は実行しない）。

[ADR-076](../../docs/02.設計書/10_決定記録/ADR-076_上限の値を設定で小さくできるようにし、実寸の上限の検証を手動にする.md)は、
上限の値を`limits`で小さくできるようにし、上限の境界の判定を小さい上限のfixtureで固定すると定める（適合fixture仕様 §3.4）。
この群は、単一ワークスペースの`doctor`の`limits`の出力、`limits`の設定の検査、入力の上限（安全な入出力・互換性 §4.1）、
`{tests}`を展開した後の引数列の上限、複合ワークスペース用のキーを使わないこと、コンテキストのハッシュ値の材料に含めないことを、21件で固定する。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-183-01` | `doctor` | `SINGLE-001`の設定に`limits: {}` | `passed`／0。`limits`は15キーすべて絶対上限 |
| `SINGLE-183-02` | `doctor` | `SINGLE-001`の設定に`limits`の2キー（`expandedArgvBytes: 4096`、`specFileCount: 5`の順に書く） | `passed`／0。`limits`はその2キーの値と残りの絶対上限 |
| `SINGLE-183-03` | `check --full --base HEAD` | `limits`の15キーすべてが絶対上限ちょうど | `passed`／0。診断なし |
| `SINGLE-183-04` | `check --full --base HEAD` | `limits: 1024`（マッピングでない） | `error`／3。`SPEC-CONFIG-SCHEMA-001`（`source.key`は`limits`） |
| `SINGLE-183-05` | `check --full --base HEAD` | `limits`の中の未知のキー`futureLimit: 1` | `passed_with_warnings`／0。`SPEC-CONFIG-UNKNOWN-001`（`source.key`は`limits.futureLimit`） |
| `SINGLE-180-01`、`02` | `check --full --base HEAD` | `specBytes`が仕様文書の大きさちょうど／1小さい | `passed`／`failed`（`SPEC-INPUT-LIMIT-001`） |
| `SINGLE-180-03`、`04` | 同上 | `frontmatterBytes`が区切りの行を含む大きさ／区切りの行を除く大きさより1小さい | `passed`／`failed` |
| `SINGLE-180-05`、`06` | 同上 | `documentStatementCount: 3`で規範文が3件／4件 | `passed`／`failed` |
| `SINGLE-180-07`、`08` | 同上 | `documentArrayItemCount: 3`で`covers`が3件／4件 | `passed`／`failed`（`source.key`は`tests[0].covers`） |
| `SINGLE-180-09` | 同上 | `specFileCount: 2`で仕様文書が2件 | `passed`／0 |
| `SINGLE-181` | `context REQ-001 --purpose verify` | `SINGLE-042`の設定に、どの上限も超えない`limits` | `SINGLE-042`と同じ結果。`contextDigest`も同じ |
| `SINGLE-182-01` | `verify REQ-001` | `SINGLE-055`の設定に`expandedArgvCount: 3`（展開した後の要素数ちょうど） | `SINGLE-055`と同じ結果 |
| `SINGLE-182-02`、`03` | 同上 | `expandedArgvElementBytes`が最長の要素＋1／最長の要素−1 | `passed`／`blocked`（`SPEC-VERIFY-BLOCKED-001`） |
| `SINGLE-182-04`、`05` | 同上 | `expandedArgvBytes`が要素の合計＋要素数／要素の合計−1 | `passed`／`blocked` |
| `SINGLE-182-06` | 同上 | 複合ワークスペースのスナップショット全体の次元のキーをすべて1にする | `SINGLE-055`と同じ結果 |

期待値の根拠は規範文（安全な入出力・互換性 §4・§4.1、ワークスペース・設定仕様 §5・§6、文書・フロントマター・状態仕様 §11、
コンテキストのハッシュ値の正規化仕様 §3、`doctor` §7、結果・診断・終了コード §2・§5、診断レジストリ）と、承認済みの文言
（`Coreの出力文言のレビュー記録.md`の#22・#41・#76・#78・#79・#140と2026-11-04の要素の文言）だけである。小さい値を設定したときの`summary`は、
§4.1の規則で上限の表記だけを実際の値（件数は3桁区切りの整数、バイト数は3桁区切りの整数に`バイト`）へ置き換える。Coreの出力は根拠にしない。
`SINGLE-181`・`182-*`・`183-01`・`02`は、レビュー済みの既存のfixture（`SINGLE-001`・`042`・`055`）の入力の設定へ`limits`の行を足し、
期待結果をそこから導く。基のfixtureの入力か期待値が変われば、この群の監査が失敗する。

フロントマターの大きさが区切りの行（`---`）を含むか、引数列のバイト数が要素の終端のNULを含むかは、規範文が定めない。
この群は、どちらの数え方でも結論が変わらない値（含む数え方のちょうど、含まない数え方の1超過）を使い、ちょうどの境界は固定しない。
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
    """区切りの行（`---`とLF）の間のバイト列。"""
    parts = document.split(b"---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError("文書に区切られたフロントマターがありません")
    return parts[1]


DOCUMENT_BYTES = DOCUMENT.encode()
DOCUMENT_SIZE = len(DOCUMENT_BYTES)
FRONTMATTER_CONTENT = len(frontmatter_content(DOCUMENT_BYTES))
# 区切りの行2本（`---\n`が2回）を含む大きさ。
FRONTMATTER_WITH_DELIMITERS = FRONTMATTER_CONTENT + 2 * len(b"---\n")
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
    "SINGLE-180-01": case("input", 2, "specBytesが仕様文書の大きさちょうどなら遮断しない",
                          limits=[("specBytes", DOCUMENT_SIZE)], document="plain", status="passed"),
    "SINGLE-180-02": case("input", 2, "仕様文書がspecBytesを1バイト超えれば文書を検査しない",
                          limits=[("specBytes", DOCUMENT_SIZE - 1)], document="plain", status="failed",
                          summary=f"仕様文書のMarkdownが{bytes_text(DOCUMENT_SIZE - 1)}上限を超過しました"),
    "SINGLE-180-03": case("input", 2, "frontmatterBytesが区切りの行を含むフロントマターの大きさなら遮断しない",
                          limits=[("frontmatterBytes", FRONTMATTER_WITH_DELIMITERS)], document="plain", status="passed"),
    "SINGLE-180-04": case("input", 2, "フロントマターがfrontmatterBytesを超えれば文書を検査しない",
                          limits=[("frontmatterBytes", FRONTMATTER_CONTENT - 1)], document="plain", status="failed",
                          summary=f"フロントマターが{bytes_text(FRONTMATTER_CONTENT - 1)}上限を超過しました"),
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
    "SINGLE-181": case("derived", 3, "limitsはコンテキストのハッシュ値の材料に含めない",
                       base="SINGLE-042", limits=None),
    "SINGLE-182-01": case("derived", 4, "expandedArgvCountちょうどの引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvCount", len(SINGLE_055_ARGV))]),
    "SINGLE-182-02": case("derived", 4, "最長の要素がexpandedArgvElementBytes以内の引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvElementBytes", ARGV_LONGEST + 1)]),
    "SINGLE-182-03": case("argv-blocked", 4, "要素がexpandedArgvElementBytesを超える引数列のテスト割当てを起動しない",
                          base="SINGLE-055", limits=[("expandedArgvElementBytes", ARGV_LONGEST - 1)],
                          summary=f"{{tests}}展開後のargvの要素がバイト数上限{bytes_text(ARGV_LONGEST - 1)}を超えます"),
    "SINGLE-182-04": case("derived", 4, "全体のバイト数がexpandedArgvBytes以内の引数列のテスト割当てを起動する",
                          base="SINGLE-055", limits=[("expandedArgvBytes", ARGV_TOTAL + len(SINGLE_055_ARGV))]),
    "SINGLE-182-05": case("argv-blocked", 4, "全体のバイト数がexpandedArgvBytesを超える引数列のテスト割当てを起動しない",
                          base="SINGLE-055", limits=[("expandedArgvBytes", ARGV_TOTAL - 1)],
                          summary=f"{{tests}}展開後のargvがバイト数上限{bytes_text(ARGV_TOTAL - 1)}を超えます"),
    "SINGLE-182-06": case("derived", 4, "単一ワークスペースは複合ワークスペースのスナップショット全体の次元のキーを使わない",
                          base="SINGLE-055", limits=[(key, 1) for key in SNAPSHOT_KEYS]),
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
    if "base" in case_:
        tree = read_tree(base_fixture(identifier) / "repo")
        content, executable = tree[CONFIG_PATH]
        tree[CONFIG_PATH] = (content + limits_block(limits_of(identifier)).encode(), executable)
        return tree
    inputs = {CONFIG_PATH: config_text(identifier).encode()}
    if case_["kind"] == "input":
        inputs.update(document_inputs(case_["document"]))
    return {path: (content, False) for path, content in inputs.items()}


# --- 期待値 -----------------------------------------------------------------------------------

def operation(identifier):
    case_ = CASES[identifier]
    if case_["kind"] == "doctor":
        return "doctor"
    if case_["kind"] in {"config", "input"}:
        return "check"
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
    return {"fixtureId": identifier, "description": case_["description"],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".",
                           "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
            "expect": {"status": status,
                       "exitCode": {"passed": 0, "passed_with_warnings": 0, "failed": 1, "error": 3}[status],
                       "stdout": "json", "resultFile": f"expected/{name}.json", "reportFileCount": 0}}


def check_result(status, documents, statements, diagnostics, identity="root"):
    return {"schemaVersion": "1.0", "operation": "check", "status": status,
            "workspace": {"id": identity, "path": "."}, "durationMs": 0, "diagnostics": diagnostics,
            "scope": "full", "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": documents, "checkedStatementCount": statements}


def diagnostic(code, severity, status, summary, path, key=None, identity="root"):
    source = {"kind": "file", "workspaceId": identity, "path": path}
    if key is not None:
        source["key"] = key
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": source}


# 入力の上限のfixtureの検査件数（文書、規範文）。`skip-document`で上限を超えた文書は数えない（診断レジストリ）。
INPUT_COUNTS = {"SINGLE-180-01": (1, 1), "SINGLE-180-02": (0, 0), "SINGLE-180-03": (1, 1), "SINGLE-180-04": (0, 0),
                "SINGLE-180-05": (1, 3), "SINGLE-180-06": (0, 0), "SINGLE-180-07": (1, 3), "SINGLE-180-08": (1, 1),
                "SINGLE-180-09": (2, 2)}


def reviewed_result(identifier):
    case_ = CASES[identifier]
    kind = case_["kind"]
    if kind == "doctor":
        result = json.loads((base_fixture(identifier) / "expected/doctor.json").read_text())
        result["limits"] = effective_limits(case_["limits"])
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
        if identifier == "SINGLE-183-04":
            # 設定の型の不正では同一性を構成できない（結果・診断・終了コード §5）。文言は承認済みの#22。
            return check_result("error", 0, 0, [diagnostic(
                "SPEC-CONFIG-SCHEMA-001", "error", "error", "設定キーlimitsはマッピングで指定してください",
                CONFIG_PATH, "limits", identity=None)], identity=None)
        if identifier == "SINGLE-183-05":
            return check_result("passed_with_warnings", 0, 0, [diagnostic(
                "SPEC-CONFIG-UNKNOWN-001", "warning", "passed_with_warnings", "未知の設定キーです",
                CONFIG_PATH, "limits.futureLimit")])
        return check_result("passed", 0, 0, [])
    documents, statements = INPUT_COUNTS[identifier]
    diagnostics = []
    if case_["status"] == "failed":
        key = "tests[0].covers" if identifier == "SINGLE-180-08" else None
        diagnostics.append(diagnostic(LIMIT_CODE, "error", "failed", case_["summary"], REQ_PATH, key))
    return check_result(case_["status"], documents, statements, diagnostics)


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
    if case_["kind"] == "input":
        document = inputs[REQ_PATH][0]
        measured = {"specBytes": len(document), "documentStatementCount": statement_count(document),
                    "documentArrayItemCount": covers_count(document),
                    "specFileCount": sum(1 for path in inputs if path.endswith(".md"))}
        key, value = next(iter(limits.items()))
        over = case_["status"] == "failed"
        if key == "frontmatterBytes":
            content = len(frontmatter_content(document))
            with_delimiters = content + 2 * len(b"---\n")
            # 区切りの行を含む／含まないのどちらで数えても、結論が同じになる値に限る。
            if over != (content > value) or over != (with_delimiters > value):
                raise ValueError("フロントマターの数え方によって結論が変わる値です")
            if not over and with_delimiters != value:
                raise ValueError("区切りの行を含むフロントマターの大きさがちょうど上限ではありません")
            if over and content != value + 1:
                raise ValueError("区切りの行を除くフロントマターの大きさが上限+1ではありません")
        elif measured[key] != (value + 1 if over else value):
            raise ValueError(f"{key}の実測がちょうど上限または上限+1ではありません")
        for other, absolute in ABSOLUTE.items():
            if other in measured and other != key and measured[other] > absolute:
                raise ValueError(f"{other}も上限を超えています")
    if identifier.startswith("SINGLE-182-"):
        # 基の`SINGLE-055`の`{tests}`を展開した後の引数列を、基の期待結果から読み直す。
        base = json.loads((base_fixture(identifier) / "expected/verify.json").read_text())
        argv = base["commands"][0]["argv"]
        if argv != SINGLE_055_ARGV:
            raise ValueError("基のfixtureの展開した後の引数列が想定と異なります")
        sizes = [len(value.encode()) for value in argv]
        checks = {
            "SINGLE-182-01": len(argv) == limits.get("expandedArgvCount"),
            # NULの終端を含む／含まないのどちらでも、最長の要素は上限以内、または上限を超える。
            "SINGLE-182-02": max(sizes) + 1 == limits.get("expandedArgvElementBytes"),
            "SINGLE-182-03": max(sizes) == limits.get("expandedArgvElementBytes", 0) + 1,
            "SINGLE-182-04": sum(sizes) + len(sizes) == limits.get("expandedArgvBytes"),
            "SINGLE-182-05": sum(sizes) == limits.get("expandedArgvBytes", 0) + 1,
            "SINGLE-182-06": set(limits) == set(SNAPSHOT_KEYS),
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
