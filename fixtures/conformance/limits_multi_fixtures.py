"""複合ワークスペースで、ルートワークスペースの設定の`limits`による上限の設定を固定する（Coreの公開操作は実行しない）。

[ADR-076](../../docs/02.設計書/10_決定記録/ADR-076_上限の値を設定で小さくできるようにし、実寸の上限の検証を手動にする.md)は、
複合ワークスペースのスナップショット全体の次元の上限（複合ワークスペース仕様 §10）と除外のパスの件数の上限を、ルートワークスペースの設定の
`limits`で小さくできるようにし、上限の境界の判定を小さい上限のfixtureで固定すると定める（適合fixture仕様 §3.4）。実寸の上限の
`MULTI-020-*`、`MULTI-021-*`、`MULTI-041-*`は手動の検証になったので、この群がその境界の判定を毎回固定する。36件である。

| fixture | 起動 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-069-01`〜`14` | `check --all-workspaces --base HEAD`（`verifyBindingCount`だけ`verify --all-workspaces`） | 7つの次元のそれぞれについて、`limits`の値ちょうど（奇数）と1超過（偶数） | ちょうどは`passed`／0、超過は`blocked`／2（`SPEC-MULTI-LIMIT-001`、`evidence.limit`は設定した値） |
| `MULTI-069-15` | `verify --all-workspaces` | `verifyBindingCount: 4`と`commandDefinitionCount: 4`の両方を、テスト割当て5件・コマンド定義5件で超える | `blocked`／2。`verifyBindingCount`を報告する |
| `MULTI-069-16`〜`18` | `verify`＋ルートのREQ全件 | 単独の`verify`で、テスト割当てとコマンド定義が5・5／4・5／4・4（上限はどちらも4） | `verifyBindingCount`／`commandDefinitionCount`の超過、境界値は`passed` |
| `MULTI-069-19` | `verify --workspace nope` | コマンド定義5件（`commandDefinitionCount: 4`）、テスト割当て1件 | 終了コード4。全体事前検査では`commandDefinitionCount`を判定しない |
| `MULTI-069-20` | `check --all-workspaces --base HEAD` | 基準版は規範文6件で`limits`なし。現在版は規範文5件で`statementCount: 5` | `blocked`／2。現在版の上限を基準版へ適用する |
| `MULTI-069-21` | 同上 | 基準版は規範文6件で`statementCount: 5`。現在版は規範文6件で`limits`なし | `passed`／0。基準版の設定の`limits`は使わない（対照） |
| `MULTI-069-25` | 同上 | `MULTI-069-20`の変更をインデックスへステージする（インデックスと作業ツリーは規範文5件、基準版のコミットは6件） | `blocked`／2。基準版はコミットの内容で数える |
| `MULTI-068-01`、`02` | `check --all-workspaces --base HEAD` | `MULTI-037-01`の除外2件に`excludeCount: 2`／`1` | `MULTI-037-01`と同じ／`SPEC-MULTI-CONFIG-001` |
| `MULTI-068-03` | `doctor --all-workspaces`（`apps/web`） | `MULTI-026-01`のルートの設定に`limits` | `limits`を最上位にだけ置く |
| `MULTI-068-04` | `doctor`（`apps/web`） | `MULTI-035-03`のルートの設定に`limits` | 作業ワークスペースは`web`でも、`limits`はルートの設定の値 |
| `MULTI-068-05` | `check --all-workspaces --base HEAD` | `MULTI-001`のルートの設定に`limits.memberCount: 1`（メンバー2件） | `passed_with_warnings`／0。`memberCount`は`limits`のキーではない（未知のキーの警告。判定に使わない） |
| `MULTI-068-06`〜`08` | 同上 | `MULTI-001`のメンバー`web`の設定に`limits.specBytes: 2048`／`limits: 1024`／`limits.specBytes: 0` | `failed`／1。値によらず`SPEC-MULTI-MEMBER-001`の1件（発生元は`MULTI-048-04`と同じくカタログの宣言） |
| `MULTI-068-09` | `doctor --all-workspaces` | `MULTI-007-01`（メンバーの入れ子で`failed`）のルートの設定に`limits` | `failed`／1。`limits`も返す（`doctor` §7） |
| `MULTI-068-10`、`11` | `check --all-workspaces --base HEAD`／`check --full --base HEAD` | `MULTI-037-20`の形で、基準版は`exclude: [vendor/a, vendor/b]`と`vendor/a/.spec/bitz.yaml`。現在版は`exclude: [vendor/a]`と`excludeCount: 1` | `passed`／0。`excludeCount`は現在版の除外にだけ当て、基準版の除外は絶対上限で検査する |
| `MULTI-069-22`、`23` | `check --all-workspaces --base HEAD` | メンバー`m001`の文書だけが規範文2件、ルートの`documentStatementCount`が2／1 | `passed`／`failed`（`m001`の`SPEC-INPUT-LIMIT-001`） |
| `MULTI-069-24` | `verify --all-workspaces` | メンバー`m001`のテスト割当てだけが展開した後に3要素、ルートの`expandedArgvCount: 2` | `blocked`／2（`m001`の`SPEC-VERIFY-BLOCKED-001`） |

期待値の根拠は規範文（安全な入出力・互換性 §4・§4.1、複合ワークスペース仕様 §2・§2.1・§7・§8・§10、`check` §9、ワークスペース・設定仕様 §5、`verify` §3・§4・§8、
`doctor` §7、結果・診断・終了コード §2・§5、ADR-066）と、承認済みの文言（`multi_limit_fixtures.SUMMARY_LABELS`、`Coreの出力文言のレビュー記録.md`の
#41と2026-10-18の除外の件数）だけである。小さい値を設定したときの`summary`は、§4.1の規則で上限の表記だけを実際の値へ置き換える
（既存の文言の形のまま、値を3桁区切りの整数で入れる。`inputBytes`も単位を付けない。2026-11-17の承認済みの対応表）。超過はちょうど上限+1にし、`observedAtLeast`は上限+1とする。
入力は、実寸の群と同じ生成器（`multi_generator`）で小さい値を生成し、`repo/`としてバージョン管理する。次元の計数は、生成計画ではなく
生成したバイト列から数え直す（`multi_generator.count`）。期待結果は、実寸の群と同じ参照計算（`multi_limit_fixtures`、
`multi_single_verify_limit_fixtures`、`multi_crosscheck`）で組み立てる。`MULTI-068-*`は、レビュー済みの既存のfixtureの入力の
ルートの設定へ`limits`の行を足し、期待結果をそこから導く。`MULTI-068-10`・`11`は`MULTI-037-20`の入力から作り、全体の結果は`MULTI-037-20`の
期待結果（`revision.dirty`だけを`true`）から導く。Coreの出力は根拠にしない。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_crosscheck, multi_generator
from . import multi_limit_fixtures as scale
from . import multi_single_verify_limit_fixtures as single_verify
from .harness import setup, write_generated
from .initial_fixtures import compare_state, observe
from .limits_single_fixtures import ABSOLUTE, _dump, count_text, effective_limits, limits_block, read_tree, write_tree
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
ROOT_CONFIG = ".spec/bitz.yaml"
CHECK_ALL = ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"]
VERIFY_ALL = ["verify", "--all-workspaces", "--format", "json"]
UNKNOWN_WORKSPACE = "nope"
# 各次元の小さい上限。生成器のベースライン（3ワークスペース、各1件のテスト割当て文書）を下回らない値にする。
SMALL = {"specFileCount": 4, "inputBytes": 4096, "statementCount": 5, "relationEdgeCount": 3,
         "traceEntryCount": 8, "commandDefinitionCount": 4, "verifyBindingCount": 4}
ORDER = ("specFileCount", "inputBytes", "statementCount", "relationEdgeCount", "traceEntryCount",
         "commandDefinitionCount", "verifyBindingCount")
EXCLUDE_COUNT_SUMMARY = "設定キーmultiWorkspace.excludeは{}件以下で指定してください"
BASE_STATEMENTS = 6
BASE_STATEMENT_LIMIT = 5


def dimension_cases():
    entries = {}
    for index, dimension in enumerate(ORDER):
        limit = SMALL[dimension]
        for offset, value in enumerate((limit, limit + 1)):
            entries[f"MULTI-069-{index * 2 + offset + 1:02d}"] = dict(
                form="all", dimension=dimension, value=value, limits=[(dimension, limit)],
                outcome="blocked" if value > limit else "passed", report=dimension)
    return entries


CASES = dimension_cases()
CASES.update({
    "MULTI-069-15": dict(form="all", dimension="verifyBindingCount", value=5,
                         limits=[("verifyBindingCount", 4), ("commandDefinitionCount", 4)],
                         outcome="blocked", report="verifyBindingCount"),
    "MULTI-069-16": dict(form="targets", bindings=5, commands=5,
                         limits=[("verifyBindingCount", 4), ("commandDefinitionCount", 4)],
                         outcome="blocked", report="verifyBindingCount"),
    "MULTI-069-17": dict(form="targets", bindings=4, commands=5,
                         limits=[("verifyBindingCount", 4), ("commandDefinitionCount", 4)],
                         outcome="blocked", report="commandDefinitionCount"),
    "MULTI-069-18": dict(form="targets", bindings=4, commands=4,
                         limits=[("verifyBindingCount", 4), ("commandDefinitionCount", 4)],
                         outcome="passed", report=None),
    "MULTI-069-19": dict(form="unknown-workspace", bindings=1, commands=5,
                         limits=[("commandDefinitionCount", 4)], outcome="argument", report=None),
    "MULTI-069-20": dict(form="base", base_limits=[], current_limits=[("statementCount", BASE_STATEMENT_LIMIT)],
                         current_statements=BASE_STATEMENT_LIMIT, outcome="blocked", report="statementCount"),
    "MULTI-069-21": dict(form="base", base_limits=[("statementCount", BASE_STATEMENT_LIMIT)], current_limits=[],
                         current_statements=BASE_STATEMENTS, outcome="passed", report=None),
    "MULTI-069-25": dict(form="base", base_limits=[], current_limits=[("statementCount", BASE_STATEMENT_LIMIT)],
                         current_statements=BASE_STATEMENT_LIMIT, outcome="blocked", report="statementCount", stage=True),
    "MULTI-068-01": dict(form="derived", base="MULTI-037-01", limits=[("excludeCount", 2)], outcome="passed"),
    "MULTI-068-02": dict(form="derived", base="MULTI-037-01", limits=[("excludeCount", 1)], outcome="failed"),
    "MULTI-068-03": dict(form="derived", base="MULTI-026-01",
                         limits=[("inputBytes", 65536), ("verifyBindingCount", 50), ("excludeCount", 3)], outcome="passed"),
    "MULTI-068-04": dict(form="derived", base="MULTI-035-03", limits=[("specBytes", 2048), ("statementCount", 10)],
                         outcome="passed"),
    "MULTI-068-05": dict(form="derived", base="MULTI-001", limits=[("memberCount", 1)], outcome="passed_with_warnings"),
    "MULTI-068-06": dict(form="derived", base="MULTI-001", config="apps/web/.spec/bitz.yaml",
                         limits=[("specBytes", 2048)], outcome="failed"),
    "MULTI-068-07": dict(form="derived", base="MULTI-001", config="apps/web/.spec/bitz.yaml",
                         raw="limits: 1024\n", limits=[], outcome="failed"),
    "MULTI-068-08": dict(form="derived", base="MULTI-001", config="apps/web/.spec/bitz.yaml",
                         raw="limits:\n  specBytes: 0\n", limits=[], outcome="failed"),
    "MULTI-068-09": dict(form="derived", base="MULTI-007-01", limits=[("specBytes", 4096), ("excludeCount", 5)],
                         outcome="failed"),
    "MULTI-068-10": dict(form="base-exclude", scope="all", limits=[("excludeCount", 1)], outcome="passed"),
    "MULTI-068-11": dict(form="base-exclude", scope="single", limits=[("excludeCount", 1)], outcome="passed"),
    "MULTI-069-22": dict(form="member-statement", limits=[("documentStatementCount", 2)], outcome="passed"),
    "MULTI-069-23": dict(form="member-statement", limits=[("documentStatementCount", 1)], outcome="failed"),
    "MULTI-069-24": dict(form="member-argv", limits=[("expandedArgvCount", 2)], outcome="blocked"),
})
LABELS = {"specFileCount": "仕様文書のファイル数", "inputBytes": "入力バイト数", "statementCount": "規範文数",
          "relationEdgeCount": "関係のエッジ数", "traceEntryCount": "トレースのエントリ数",
          "commandDefinitionCount": "コマンド定義数", "verifyBindingCount": "テスト割当て数"}
DESCRIPTIONS = {
    "MULTI-069-15": "verify --all-workspacesでテスト割当て数とコマンド定義数の両方がlimitsを超えればテスト割当て数を報告する",
    "MULTI-069-16": "単独のverifyでテスト割当て数とコマンド定義数の両方がlimitsを超えればテスト割当て数を報告する",
    "MULTI-069-17": "単独のverifyでコマンド定義数だけがlimitsを超えればコマンド定義数を報告する",
    "MULTI-069-18": "単独のverifyでテスト割当て数とコマンド定義数がlimitsちょうどなら全件を実行する",
    "MULTI-069-19": "コマンド定義数だけがlimitsを超えカタログにない--workspaceを指定した単独のverifyは引数不正にする",
    "MULTI-069-20": "check --baseは現在版のルートの設定のlimitsを基準版へも適用する",
    "MULTI-069-21": "check --baseは基準版のルートの設定のlimitsを使わない",
    "MULTI-069-25": "check --baseは基準版の上限をインデックスではなく基準版のコミットの内容で数える",
    "MULTI-068-10": "check --all-workspaces --baseはexcludeCountを基準版の設定の除外に当てず絶対上限で検査する",
    "MULTI-068-11": "単独のcheck --baseはexcludeCountを基準版の設定の除外に当てず絶対上限で検査する",
    "MULTI-068-01": "除外のパスの件数がexcludeCountちょうどなら受け入れる",
    "MULTI-068-02": "除外のパスの件数がexcludeCountを超えれば設定不適合にする",
    "MULTI-068-03": "doctor --all-workspacesはlimitsを最上位にだけ置く",
    "MULTI-068-04": "メンバーの中の単独のdoctorはルートの設定のlimitsを返す",
    "MULTI-068-05": "limitsのmemberCountは未知のキーとして警告にし判定に使わない",
    "MULTI-068-06": "メンバーの設定がlimitsを持てばメンバーの不適合にする",
    "MULTI-068-07": "メンバーの設定のlimitsがマッピングでなくてもメンバーの不適合の1件だけにする",
    "MULTI-068-08": "メンバーの設定のlimitsの値が範囲の外でもメンバーの不適合の1件だけにする",
    "MULTI-068-09": "全体事前検査がほかの原因で非成功でもdoctorはルートの設定のlimitsを返す",
    "MULTI-069-22": "ルートの設定のdocumentStatementCountちょうどのメンバーの文書を遮断しない",
    "MULTI-069-23": "メンバーの文書の規範文がルートの設定のdocumentStatementCountを超えればその文書を検査しない",
    "MULTI-069-24": "メンバーのテスト割当ての引数列の要素数がルートの設定のexpandedArgvCountを超えれば起動しない",
}


def description(identifier):
    if identifier in DESCRIPTIONS:
        return DESCRIPTIONS[identifier]
    case = CASES[identifier]
    limit = dict(case["limits"])[case["dimension"]]
    if case["outcome"] == "blocked":
        return f"{LABELS[case['dimension']]}がlimitsの{limit:,}を1超えれば全体を遮断する"
    return f"{LABELS[case['dimension']]}がlimitsの{limit:,}ちょうどなら遮断しない"


# --- 入力 -------------------------------------------------------------------------------------

def with_limits(entries, limits):
    """ルートの設定の末尾へ`limits`の行を足す。`limits`が空の列なら何も足さない。"""
    block = limits_block(limits).encode() if limits else b""
    return [(path, content + block if path == ROOT_CONFIG else content) for path, content in entries]


def draft_statement_entries(statements):
    """`check --base`の群の木構造。ルートの規範文の文書を`draft`にし、規範文の数を`statements - 3`件にする。"""
    entries = multi_generator.emit(multi_generator.plan("statementCount", statements))
    result = []
    for path, content in entries:
        if path.startswith(".spec/technical/") and b"\n## Contract\n" in content and b"\ntests:\n" not in content:
            content = content.replace(b"\nstatus: approved\n", b"\nstatus: draft\n", 1)
        result.append((path, content))
    return result


def entries_of(identifier):
    """`repo/`の(パス, 内容)の列。`base`の群では基準版の木構造。"""
    case = CASES[identifier]
    form = case["form"]
    if form == "all":
        limits = case["limits"]
        value = case["value"]
        if case["dimension"] == "inputBytes":
            # 生成器は設定と仕様文書の合計を値へ合わせる。`limits`の行のバイト数を先に差し引いておく。
            value -= len(limits_block(limits).encode())
        return with_limits(multi_generator.emit(multi_generator.plan(case["dimension"], value)), limits)
    if form in {"targets", "unknown-workspace"}:
        profile = multi_generator.single_verify_plan(case["bindings"], case["commands"],
                                                     "verifyBindingCount" if case["bindings"] == case["commands"]
                                                     else "commandDefinitionCount")
        return with_limits(multi_generator.emit(profile), case["limits"])
    if form == "base":
        return with_limits(draft_statement_entries(BASE_STATEMENTS), case["base_limits"])
    if form in {"member-statement", "member-argv"}:
        return with_limits(member_entries(shared_command=form == "member-argv"), case["limits"])
    if form == "base-exclude":
        return exclude_entries(BASE_EXCLUDES, [])
    raise ValueError("派生の群は`entries_of`を使いません")


EXCLUDE_SOURCE = "MULTI-037-20"
SOURCE_EXCLUDE_BLOCK = b"  exclude:\n    - generated\n"
VENDOR_CONFIG = "vendor/a/.spec/bitz.yaml"
# 除外した範囲の中の単一ワークスペースの設定（`MULTI-037-01`の`cases/single`と同じ形）。カタログには登録しない。
VENDOR_CONFIG_TEXT = b'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: vendor\n'
BASE_EXCLUDES = ["vendor/a", "vendor/b"]
CURRENT_EXCLUDES = ["vendor/a"]
CHECK_SINGLE_FULL = ["check", "--full", "--base", "HEAD", "--format", "json"]


def exclude_entries(excludes, limits):
    """`MULTI-037-20`の入力の、ルートの設定の除外を`excludes`に替え、`limits`を足し、除外した範囲の中に`vendor/a`の設定を置いた木構造。"""
    tree = read_tree(HERE / "multi" / EXCLUDE_SOURCE / "repo")
    if any(executable for _, executable in tree.values()):
        raise ValueError("基のfixtureの入力に実行ビットがあります")
    config = tree[ROOT_CONFIG][0]
    if not config.endswith(SOURCE_EXCLUDE_BLOCK) or config.count(SOURCE_EXCLUDE_BLOCK) != 1:
        raise ValueError("基のfixtureのルートの設定の除外が想定と異なります")
    block = b"  exclude:\n" + b"".join(f"    - {path}\n".encode() for path in excludes)
    entries = {path: content for path, (content, _) in tree.items()}
    entries[ROOT_CONFIG] = config[:-len(SOURCE_EXCLUDE_BLOCK)] + block
    entries[VENDOR_CONFIG] = VENDOR_CONFIG_TEXT
    return with_limits(sorted(entries.items()), limits)


def exclude_paths(config):
    """ルートの設定の`multiWorkspace.exclude`の項目（この群の設定の書き方だけを読む）。"""
    text = config.decode()
    if text.count("  exclude:\n") != 1:
        raise ValueError("ルートの設定の除外が1つではありません")
    paths = []
    for line in text.split("  exclude:\n", 1)[1].split("\n"):
        if not line.startswith("    - "):
            break
        paths.append(line[len("    - "):])
    return paths


MEMBER_DOCUMENT = "members/m001/.spec/technical/TECH-000002.md"
MEMBER_CONFIG = "members/m001/.spec/bitz.yaml"


def member_entries(shared_command):
    """ルートとメンバー`m002`は規範文1件、メンバー`m001`の文書だけが規範文2件（テスト対応2件）を持つ木構造。
    `shared_command`では、`m001`の2件のテスト対応が同じコマンド`c00001`を使い、展開した後の引数列が3要素になる（ほかは2要素）。"""
    profile = multi_generator.plan("verifyBindingCount", 4)
    profile["bindings"] = [1, 2, 1]
    profile["commands"] = [1, 2, 1]
    entries = multi_generator.emit(profile)
    if shared_command:
        entries = [(path, content.replace(b"    command: c00002\n", b"    command: c00001\n")
                    if path == MEMBER_DOCUMENT else content) for path, content in entries]
    return entries


def current_entries(identifier):
    """`base`・`base-exclude`の群の現在版の木構造（準備の処理を適用した後）。"""
    case = CASES[identifier]
    if case["form"] == "base-exclude":
        return exclude_entries(CURRENT_EXCLUDES, case["limits"])
    return with_limits(draft_statement_entries(case["current_statements"]), case["current_limits"])


def changes_of(identifier):
    """`base`の群の`changes/`と準備の処理。基準版と現在版で異なるファイルだけを置き換える。"""
    base = dict(entries_of(identifier))
    current = dict(current_entries(identifier))
    if set(base) != set(current):
        raise ValueError("基準版と現在版のファイルの集合が異なります")
    changes, operations = {}, []
    for path in sorted(base):
        if base[path] != current[path]:
            source = f"changes/{path.rsplit('/', 1)[-1]}"
            changes[source[len("changes/"):]] = (current[path], False)
            operations.append({"op": "update", "path": path, "source": source})
    if CASES[identifier].get("stage"):
        # 変更をインデックスへステージし、インデックスと作業ツリーを同じ内容にする（基準版のコミットだけが異なる）。
        operations.append({"op": "stage", "paths": [operation["path"] for operation in operations]})
    return changes, operations


def base_fixture(identifier):
    return HERE / "multi" / CASES[identifier]["base"]


def reviewed_inputs(identifier):
    """`repo/`の(パス -> (バイト列, 実行ビット))。"""
    case = CASES[identifier]
    if case["form"] == "derived":
        tree = read_tree(base_fixture(identifier) / "repo")
        path = case.get("config", ROOT_CONFIG)
        content, executable = tree[path]
        block = case["raw"] if "raw" in case else limits_block(case["limits"])
        tree[path] = (content + block.encode(), executable)
        return tree
    return {path: (content, False) for path, content in entries_of(identifier)}


CHANGED_FORMS = {"base", "base-exclude"}


def reviewed_changes(identifier):
    return changes_of(identifier)[0] if CASES[identifier]["form"] in CHANGED_FORMS else {}


# --- 期待値 -----------------------------------------------------------------------------------

def targets(identifier):
    case = CASES[identifier]
    profile = multi_generator.single_verify_plan(case["bindings"], case["commands"], "verifyBindingCount")
    return multi_generator.single_verify_targets(profile)


def argv_of(identifier):
    case = CASES[identifier]
    form = case["form"]
    if form == "all":
        return VERIFY_ALL if case["dimension"] == "verifyBindingCount" else CHECK_ALL
    if form == "targets":
        return ["verify", *targets(identifier), "--format", "json"]
    if form == "unknown-workspace":
        return ["verify", "--workspace", UNKNOWN_WORKSPACE, "--format", "json"]
    if form == "member-argv":
        return VERIFY_ALL
    if form == "base-exclude" and case["scope"] == "single":
        return CHECK_SINGLE_FULL
    return CHECK_ALL


def limit_diagnostic(dimension, limit):
    """上限の診断。`summary`は既存の文言の形のまま、上限の値を3桁区切りの整数で入れる（§4.1、承認済みの対応表）。
    `inputBytes`も値を数として持つ文言なので単位を付けない。超過はちょうど上限+1である。"""
    shown = count_text(limit)
    return {
        "code": "SPEC-MULTI-LIMIT-001", "severity": "error", "resultStatus": "blocked",
        "summary": f"{scale.SUMMARY_LABELS[dimension]}が上限{shown}を超過しました",
        "source": {"kind": "file", "workspaceId": "platform", "path": ROOT_CONFIG},
        "evidence": {"dimension": dimension, "limit": limit, "observedAtLeast": limit + 1},
    }


def all_blocked_result(name, diagnostic, dirty=False):
    revision = ({"commit": COMMIT, "dirty": dirty} if name == "verify"
                else {"base": COMMIT, "commit": COMMIT, "dirty": dirty})
    return {"schemaVersion": "1.0", "operation": name, "scope": "all-workspaces", "status": "blocked",
            "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": [], "revision": revision,
            "durationMs": 0, "diagnostics": [diagnostic]}


def binding_digests(entries, repository):
    """`verify --all-workspaces`の検証対象ごとのコンテキストのハッシュ値（`validate_scale.binding_digests`と同じ導出）。"""
    digests = {}
    for workspace, documents in scale.binding_documents(entries).items():
        workspace_id = "platform" if workspace == "." else workspace.rsplit("/", 1)[-1]
        for document in documents:
            target = f"{workspace_id}::{document['id']}"
            digests[target] = multi_crosscheck.digest(
                multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, target)))
    return digests


def workspace_result(result, workspace_id):
    found = [entry for entry in result["workspaces"] if entry["id"] == workspace_id]
    if len(found) != 1 or len(found[0].get("targetResults", [None])) != 1:
        raise ValueError(f"{workspace_id}の結果が1件ではありません")
    return found[0]


def generated_result(identifier):
    case = CASES[identifier]
    form = case["form"]
    limits = dict(case.get("limits", []))
    if case["outcome"] == "argument":
        return None
    if form == "base-exclude":
        # 現在版の除外（1件）は`excludeCount: 1`ちょうど、基準版の除外（2件）は絶対上限（100件）以内で、どちらのスナップショットも
        # 自身のルートの設定の除外で`vendor/a`の設定を列挙しない（安全な入出力・互換性 §4.1、複合ワークスペース仕様 §2.1・§8）。
        # 入力は`MULTI-037-20`と同じカタログと文書なので、全体の結果は`MULTI-037-20`の期待結果で、作業ツリーの変更により`dirty`だけが`true`。
        if case["scope"] == "all":
            result = json.loads((HERE / "multi" / EXCLUDE_SOURCE / "expected/check.json").read_text())
            result["revision"]["dirty"] = True
            return result
        # 単独の`check --full`は、作業ワークスペース（ルート）の文書だけを完全検査する（`check` §9）。ルートのREQ-001は1件・規範文1件で関係を持たない。
        return {"schemaVersion": "1.0", "operation": "check", "status": "passed", "scope": "full",
                "workspace": {"id": "platform", "path": "."},
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
                "checkedDocumentCount": 1, "checkedStatementCount": 1, "durationMs": 0, "diagnostics": []}
    if form == "base":
        if case["outcome"] == "blocked":
            limit = dict(case["current_limits"])[case["report"]]
            return all_blocked_result("check", limit_diagnostic(case["report"], limit), dirty=True)
        result = scale.passed_check_result(multi_generator.workspace_counts(current_entries(identifier)))
        result["revision"]["dirty"] = True
        return result
    if form == "member-statement":
        result = scale.passed_check_result(multi_generator.workspace_counts(entries_of(identifier)))
        if case["outcome"] == "failed":
            # ファイル単位の上限はルートの設定の値をメンバーの文書へも当てる（§4.1）。`skip-document`なので`m001`の文書だけを検査しない。
            member = workspace_result(result, "m001")
            member.update(status="failed", checkedDocumentCount=0, checkedStatementCount=0, diagnostics=[{
                "code": "SPEC-INPUT-LIMIT-001", "severity": "error", "resultStatus": "failed",
                "summary": f"1文書の規範文数が{count_text(limits['documentStatementCount'])}上限を超過しました",
                "source": {"kind": "file", "workspaceId": "m001", "path": ".spec/technical/TECH-000002.md"}}])
            result["status"] = "failed"
        return result
    if form == "member-argv":
        entries = entries_of(identifier)
        with tempfile.TemporaryDirectory(prefix="bitz-limits-multi-context-") as temporary:
            repository = Path(temporary)
            write_generated(entries, repository)
            result = scale.passed_binding_result(entries, binding_digests(entries, repository))
        # 展開した後の引数列の上限もルートの設定の値を使う（§4.1）。起動前の`skip-binding`の診断は、テスト割当てを所有する
        # ワークスペースの`diagnostics`へ置く（`verify` §6、`MULTI-051-03`と同じ形）。
        member = workspace_result(result, "m001")
        member["targetResults"][0].update(status="blocked", bindingRefs=[])
        member.update(status="blocked", commands=[], diagnostics=[{
            "code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
            "summary": f"{{tests}}展開後のargvの要素数が上限{count_text(limits['expandedArgvCount'])}を超えます",
            "source": {"kind": "file", "workspaceId": "m001", "path": ".spec/bitz.yaml", "key": "verify.commands.c00001.argv"}}])
        result["status"] = "blocked"
        return result
    if case["outcome"] == "blocked":
        diagnostic = limit_diagnostic(case["report"], limits[case["report"]])
        if form == "all":
            return all_blocked_result(argv_of(identifier)[0], diagnostic)
        return single_verify.single_result("blocked", [], [], [diagnostic])
    entries = entries_of(identifier)
    if form == "all" and case["dimension"] != "verifyBindingCount":
        return scale.passed_check_result(multi_generator.workspace_counts(entries))
    with tempfile.TemporaryDirectory(prefix="bitz-limits-multi-context-") as temporary:
        repository = Path(temporary)
        write_generated(entries, repository)
        if form == "all":
            return scale.passed_binding_result(entries, binding_digests(entries, repository))
        return single_verify.passed_result(entries, single_verify.context_digests(entries, repository))


def derived_result(identifier):
    case = CASES[identifier]
    name = json.loads((base_fixture(identifier) / "manifest.json").read_text())["invocation"]["argv"][0]
    result = json.loads((base_fixture(identifier) / f"expected/{name}.json").read_text())
    if identifier == "MULTI-068-02":
        # `MULTI-037-15`（除外が101件）と同じ停止。入力は`MULTI-037-01`と同じで、上限の表記だけを設定した値へ置き換える。
        result = json.loads((HERE / "multi/MULTI-037-15/expected/check.json").read_text())
        result["diagnostics"][0]["summary"] = EXCLUDE_COUNT_SUMMARY.format(count_text(dict(case["limits"])["excludeCount"]))
    elif identifier in {"MULTI-068-06", "MULTI-068-07", "MULTI-068-08"}:
        # メンバーの設定が`limits`のキーを持てば、値の型と範囲によらず`multiWorkspace`を宣言したメンバーと同じ`SPEC-MULTI-MEMBER-001`とし、
        # 発生元も同じくカタログの宣言とする（`MULTI-048-04`。複合ワークスペース仕様 §10）。値は検査しないので`SPEC-CONFIG-SCHEMA-001`を返さない。
        result = json.loads((HERE / "multi/MULTI-048-04/expected/check.json").read_text())
        result["diagnostics"][0].update(summary="メンバーの設定は設定キーlimitsを指定できません")
    elif identifier == "MULTI-068-09":
        # ルートの設定を読めてスキーマに適合し`limits`を宣言していれば、全体事前検査がほかの原因で非成功でも返す（`doctor` §7）。
        result["limits"] = effective_limits(case["limits"])
    elif identifier in {"MULTI-068-03", "MULTI-068-04"}:
        result["limits"] = effective_limits(case["limits"])
    elif identifier == "MULTI-068-05":
        # 全体操作は、ルートの設定の警告をルートワークスペースの`diagnostics`へ置く（`MULTI-053-01`と同じ置き場所）。
        result["status"] = "passed_with_warnings"
        root = result["workspaces"][0]
        if root["id"] != "platform":
            raise ValueError("基のfixtureの最初のワークスペースがルートではありません")
        root["status"] = "passed_with_warnings"
        root["diagnostics"] = [{"code": "SPEC-CONFIG-UNKNOWN-001", "severity": "warning",
                                "resultStatus": "passed_with_warnings", "summary": "未知の設定キーです",
                                "source": {"kind": "file", "workspaceId": "platform", "path": ROOT_CONFIG,
                                           "key": "limits.memberCount"}}]
    return result


def reviewed_result(identifier):
    if CASES[identifier]["form"] == "derived":
        return derived_result(identifier)
    return generated_result(identifier)


def expected_name(identifier):
    case = CASES[identifier]
    if case["outcome"] == "argument":
        return None
    if case["form"] == "derived":
        name = json.loads((base_fixture(identifier) / "manifest.json").read_text())["invocation"]["argv"][0]
        return f"expected/{name}.json"
    return f"expected/{argv_of(identifier)[0]}.json"


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["form"] == "derived":
        source = {"MULTI-068-02": "MULTI-037-15", "MULTI-068-06": "MULTI-048-04", "MULTI-068-07": "MULTI-048-04",
                  "MULTI-068-08": "MULTI-048-04"}.get(identifier, case["base"])
        manifest = json.loads((HERE / "multi" / source / "manifest.json").read_text())
        manifest["fixtureId"] = identifier
        manifest["description"] = description(identifier)
        if identifier == "MULTI-068-05":
            manifest["expect"]["status"] = "passed_with_warnings"
        return manifest
    expect = {"reportFileCount": 0}
    if case["outcome"] == "argument":
        expect.update({"exitCode": 4, "stdout": "none"})
    else:
        status = case["outcome"]
        expect.update({"status": status, "exitCode": {"passed": 0, "failed": 1, "blocked": 2}[status], "stdout": "json",
                       "resultFile": expected_name(identifier)})
    operations = changes_of(identifier)[1] if case["form"] in CHANGED_FORMS else []
    return {"fixtureId": identifier, "description": description(identifier),
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": argv_of(identifier), "env": {}},
            "expect": expect}


# --- 測り直し -----------------------------------------------------------------------------

def configured(limits):
    """ルートの設定の`limits`から決まる、スナップショット全体の次元の実効の上限。"""
    values = dict(limits)
    return {name: values.get(name, absolute) for name, absolute in multi_generator.LIMITS.items()
            if name != "memberCount"} | {"memberCount": multi_generator.LIMITS["memberCount"]}


def check_snapshot(entries, limits, crossing):
    """生成したバイト列だけから次元を数え直し、`crossing`の次元だけがちょうど上限+1で、ほかは上限以内であることを確かめる。"""
    counted = multi_generator.count(entries)
    effective = configured(limits)
    over = {name for name, value in counted.items() if value > effective[name]}
    if over != set(crossing):
        raise ValueError(f"超える次元が{sorted(crossing)}ではなく{sorted(over)}です")
    for name in crossing:
        if counted[name] != effective[name] + 1:
            raise ValueError(f"{name}がちょうど上限+1ではありません")
    return counted


def check_measurements(identifier):
    case = CASES[identifier]
    form = case["form"]
    for key, value in case.get("limits", []) + case.get("base_limits", []) + case.get("current_limits", []):
        if key in ABSOLUTE and not 1 <= value <= ABSOLUTE[key]:
            raise ValueError(f"{key}の値が1以上、絶対上限以下ではありません")
    if form == "all":
        entries = entries_of(identifier)
        crossing = []
        if case["outcome"] == "blocked":
            limits = dict(case["limits"])
            crossing = [name for name in limits if name in multi_generator.LIMITS]
        counted = check_snapshot(entries, case["limits"], crossing)
        if counted[case["dimension"]] != case["value"]:
            raise ValueError("狙った次元の値がレビュー済みのケースと異なります")
    elif form in {"targets", "unknown-workspace"}:
        counted = multi_generator.count(entries_of(identifier))
        if (counted["verifyBindingCount"], counted["commandDefinitionCount"]) != (case["bindings"], case["commands"]):
            raise ValueError("テスト割当て数またはコマンド定義数がレビュー済みのケースと異なります")
        effective = configured(case["limits"])
        if any(counted[name] > effective[name] for name in counted
               if name not in {"verifyBindingCount", "commandDefinitionCount"}):
            raise ValueError("ほかの次元も上限を超えています")
        if case["report"] == "verifyBindingCount" and not (
                counted["verifyBindingCount"] > effective["verifyBindingCount"]
                and counted["commandDefinitionCount"] > effective["commandDefinitionCount"]):
            raise ValueError("両方の次元が超える必要があります")
        if case["report"] == "commandDefinitionCount" and not (
                counted["verifyBindingCount"] <= effective["verifyBindingCount"]
                < counted["commandDefinitionCount"] == effective["commandDefinitionCount"] + 1):
            raise ValueError("コマンド定義数だけがちょうど上限+1で超える必要があります")
    elif form == "base-exclude":
        base, current = dict(entries_of(identifier)), dict(current_entries(identifier))
        limit = dict(case["limits"])["excludeCount"]
        base_excludes, current_excludes = exclude_paths(base[ROOT_CONFIG]), exclude_paths(current[ROOT_CONFIG])
        # 現在版の除外はちょうど`excludeCount`。基準版の除外は`excludeCount`を超えるが絶対上限以内（`excludeCount`を基準版にも当てると不適合になる）。
        if len(current_excludes) != limit or not limit < len(base_excludes) <= ABSOLUTE["excludeCount"]:
            raise ValueError("除外の件数が、現在版でちょうど上限、基準版で上限を超え絶対上限以内ではありません")
        if b"limits:" in base[ROOT_CONFIG]:
            raise ValueError("基準版のルートの設定は`limits`を持ちません")
        # どちらのスナップショットでも、未登録の設定は自身の除外の中にだけある（除外を当てなければ未登録になる）。
        for snapshot, excludes in ((base, base_excludes), (current, current_excludes)):
            configs = {path for path in snapshot if path.endswith(".spec/bitz.yaml")}
            if configs != {ROOT_CONFIG, "apps/web/.spec/bitz.yaml", "services/api/.spec/bitz.yaml", VENDOR_CONFIG}:
                raise ValueError("設定の集合が想定と異なります")
            if not VENDOR_CONFIG.startswith(excludes[0] + "/"):
                raise ValueError("未登録の設定が除外した範囲の中にありません")
            if any(path.startswith(f"{exclude}/") for exclude in excludes[1:] for path in snapshot):
                raise ValueError("2件目の除外は実在しない範囲である必要があります")
        changed = {path for path in base if base[path] != current[path]}
        if set(base) != set(current) or changed != {ROOT_CONFIG}:
            raise ValueError("基準版と現在版の差がルートの設定だけではありません")
    elif form == "base":
        base, current = entries_of(identifier), current_entries(identifier)
        # 上限は現在版の設定から決める（複合ワークスペース仕様 §10）。基準版の設定の`limits`は使わない。
        limits = case["current_limits"]
        crossing = ["statementCount"] if case["outcome"] == "blocked" else []
        check_snapshot(base, limits, crossing)
        check_snapshot(current, limits, [])
        if case["base_limits"]:
            check_snapshot(base, case["base_limits"], ["statementCount"])
    elif form in {"member-statement", "member-argv"}:
        entries = dict(entries_of(identifier))
        counted = multi_generator.count(list(entries.items()))
        if any(counted[name] > value for name, value in configured(case["limits"]).items()):
            raise ValueError("スナップショット全体の次元が上限を超えています")
        statements = {path: sum(1 for line in content.decode().split("\n") if multi_generator.STATEMENT.match(line))
                      for path, content in entries.items() if path.endswith(".md")}
        if statements.pop(MEMBER_DOCUMENT) != 2 or set(statements.values()) != {1}:
            raise ValueError("メンバー`m001`の文書だけが規範文2件である必要があります")
        commands = {}
        for path, content in entries.items():
            if path.endswith(".md"):
                workspace = path.split("/.spec/", 1)[0] if "/.spec/" in path else "."
                for line in content.decode().split("\n"):
                    if line.startswith("    command: "):
                        key = (workspace, line[len("    command: "):])
                        commands[key] = commands.get(key, 0) + 1
        elements = {key: count + 1 for key, count in commands.items()}  # `/bin/true`と`{tests}`の展開
        limit = dict(case["limits"]).get("expandedArgvCount")
        if limit is not None:
            over = {key for key, value in elements.items() if value > limit}
            if over != {("members/m001", "c00001")} or elements[("members/m001", "c00001")] != limit + 1:
                raise ValueError("メンバー`m001`のテスト割当てだけがちょうど上限+1の要素数で超える必要があります")
        else:
            limit = dict(case["limits"])["documentStatementCount"]
            if (case["outcome"] == "failed") != (2 > limit) or limit not in {1, 2}:
                raise ValueError("メンバーの文書の規範文数がちょうど上限または上限+1ではありません")
    elif identifier in {"MULTI-068-01", "MULTI-068-02"}:
        config = reviewed_inputs(identifier)[ROOT_CONFIG][0].decode()
        excludes = config.split("  exclude:\n", 1)[1].split("limits:", 1)[0]
        count = sum(1 for line in excludes.splitlines() if line.startswith("    - "))
        limit = dict(case["limits"])["excludeCount"]
        if count != (limit if case["outcome"] == "passed" else limit + 1):
            raise ValueError("除外のパスの件数がちょうど上限または上限+1ではありません")


# --- 生成と監査 ---------------------------------------------------------------------------

def observed_states(fixture, manifest):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-limits-multi-") as temporary:
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


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        fixture.mkdir(parents=True, exist_ok=False)
        write_tree(fixture / "repo", reviewed_inputs(identifier))
        changes = reviewed_changes(identifier)
        if changes:
            write_tree(fixture / "changes", changes)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        name = expected_name(identifier)
        if name is None:
            (fixture / "cli-output.json").write_text(_dump(single_verify.reviewed_cli_output()))
        else:
            (fixture / "expected").mkdir()
            (fixture / name).write_text(_dump(reviewed_result(identifier)))
        state = observed_states(fixture, manifest)
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
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("マニフェストがレビュー済みの起動と異なります")
            name = expected_name(identifier)
            if name is None:
                if (fixture / "expected").exists():
                    raise ValueError("引数不正のfixtureは期待結果のファイルを持ちません")
                if json.loads((fixture / "cli-output.json").read_text()) != single_verify.reviewed_cli_output():
                    raise ValueError("CLIの出力の期待値がレビュー済みの値と異なります")
            else:
                result = json.loads((fixture / name).read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("期待結果がレビュー済みの期待値と異なります")
                if {path.name for path in (fixture / "expected").iterdir()} != {Path(name).name}:
                    raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
                if (fixture / "cli-output.json").exists():
                    raise ValueError("結果を返すfixtureはCLIの出力の期待値を持ちません")
            check_tree(fixture / "repo", reviewed_inputs(identifier))
            check_tree(fixture / "changes", reviewed_changes(identifier))
            check_measurements(identifier)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("上限の判定はファイルを書いてはいけません")
            if compare_state(effects["before"], observed_states(fixture, manifest)):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
