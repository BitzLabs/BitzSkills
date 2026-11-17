"""複合ワークスペースで、ルートワークスペースの設定の`limits`による上限の設定を固定する（Coreの公開操作は実行しない）。

[ADR-076](../../docs/02.設計書/10_決定記録/ADR-076_上限の値を設定で小さくできるようにし、実寸の上限の検証を手動にする.md)は、
複合ワークスペースのスナップショット全体の次元の上限（複合ワークスペース仕様 §10）と除外のパスの件数の上限を、ルートワークスペースの設定の
`limits`で小さくできるようにし、上限の境界の判定を小さい上限のfixtureで固定すると定める（適合fixture仕様 §3.4）。実寸の上限の
`MULTI-020-*`、`MULTI-021-*`、`MULTI-041-*`は手動の検証になったので、この群がその境界の判定を毎回固定する。27件である。

| fixture | 起動 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-069-01`〜`14` | `check --all-workspaces --base HEAD`（`verifyBindingCount`だけ`verify --all-workspaces`） | 7つの次元のそれぞれについて、`limits`の値ちょうど（奇数）と1超過（偶数） | ちょうどは`passed`／0、超過は`blocked`／2（`SPEC-MULTI-LIMIT-001`、`evidence.limit`は設定した値） |
| `MULTI-069-15` | `verify --all-workspaces` | `verifyBindingCount: 4`と`commandDefinitionCount: 4`の両方を、テスト割当て5件・コマンド定義5件で超える | `blocked`／2。`verifyBindingCount`を報告する |
| `MULTI-069-16`〜`18` | `verify`＋ルートのREQ全件 | 単独の`verify`で、テスト割当てとコマンド定義が5・5／4・5／4・4（上限はどちらも4） | `verifyBindingCount`／`commandDefinitionCount`の超過、境界値は`passed` |
| `MULTI-069-19` | `verify --workspace nope` | コマンド定義5件（`commandDefinitionCount: 4`）、テスト割当て1件 | 終了コード4。全体事前検査では`commandDefinitionCount`を判定しない |
| `MULTI-069-20` | `check --all-workspaces --base HEAD` | 基準版は規範文6件で`limits`なし。現在版は規範文5件で`statementCount: 5` | `blocked`／2。現在版の上限を基準版へ適用する |
| `MULTI-069-21` | 同上 | 基準版は規範文6件で`statementCount: 5`。現在版は規範文6件で`limits`なし | `passed`／0。基準版の設定の`limits`は使わない（対照） |
| `MULTI-068-01`、`02` | `check --all-workspaces --base HEAD` | `MULTI-037-01`の除外2件に`excludeCount: 2`／`1` | `MULTI-037-01`と同じ／`SPEC-MULTI-CONFIG-001` |
| `MULTI-068-03` | `doctor --all-workspaces`（`apps/web`） | `MULTI-026-01`のルートの設定に`limits` | `limits`を最上位にだけ置く |
| `MULTI-068-04` | `doctor`（`apps/web`） | `MULTI-035-03`のルートの設定に`limits` | 作業ワークスペースは`web`でも、`limits`はルートの設定の値 |
| `MULTI-068-05` | `check --all-workspaces --base HEAD` | `MULTI-001`のルートの設定に`limits.memberCount: 1`（メンバー2件） | `passed_with_warnings`／0。`memberCount`は`limits`のキーではない（未知のキーの警告。判定に使わない） |
| `MULTI-068-06` | 同上 | `MULTI-001`のメンバー`web`の設定に`limits.specBytes: 2048` | `failed`／1。`SPEC-MULTI-CONFIG-001`（発生元は`MULTI-048-04`と同じくカタログの宣言） |

期待値の根拠は規範文（安全な入出力・互換性 §4・§4.1、複合ワークスペース仕様 §7・§10、ワークスペース・設定仕様 §5、`verify` §3・§4・§8、
`doctor` §7、結果・診断・終了コード §2・§5、ADR-066）と、承認済みの文言（`multi_limit_fixtures.SUMMARY_LABELS`、`Coreの出力文言のレビュー記録.md`の
#41と2026-10-18の除外の件数）だけである。小さい値を設定したときの`summary`は、§4.1の規則で上限の表記だけを実際の値へ置き換える
（既存の文言の形のまま、値を3桁区切りの整数で入れる。`inputBytes`も単位を付けない。2026-11-17の承認済みの対応表）。超過はちょうど上限+1にし、`observedAtLeast`は上限+1とする。
入力は、実寸の群と同じ生成器（`multi_generator`）で小さい値を生成し、`repo/`としてバージョン管理する。次元の計数は、生成計画ではなく
生成したバイト列から数え直す（`multi_generator.count`）。期待結果は、実寸の群と同じ参照計算（`multi_limit_fixtures`、
`multi_single_verify_limit_fixtures`、`multi_crosscheck`）で組み立てる。`MULTI-068-*`は、レビュー済みの既存のfixtureの入力の
ルートの設定へ`limits`の行を足し、期待結果をそこから導く。Coreの出力は根拠にしない。
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
    "MULTI-068-01": dict(form="derived", base="MULTI-037-01", limits=[("excludeCount", 2)], outcome="passed"),
    "MULTI-068-02": dict(form="derived", base="MULTI-037-01", limits=[("excludeCount", 1)], outcome="failed"),
    "MULTI-068-03": dict(form="derived", base="MULTI-026-01",
                         limits=[("inputBytes", 65536), ("verifyBindingCount", 50), ("excludeCount", 3)], outcome="passed"),
    "MULTI-068-04": dict(form="derived", base="MULTI-035-03", limits=[("specBytes", 2048), ("statementCount", 10)],
                         outcome="passed"),
    "MULTI-068-05": dict(form="derived", base="MULTI-001", limits=[("memberCount", 1)], outcome="passed_with_warnings"),
    "MULTI-068-06": dict(form="derived", base="MULTI-001", config="apps/web/.spec/bitz.yaml",
                         limits=[("specBytes", 2048)], outcome="failed"),
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
    "MULTI-068-01": "除外のパスの件数がexcludeCountちょうどなら受け入れる",
    "MULTI-068-02": "除外のパスの件数がexcludeCountを超えれば設定不適合にする",
    "MULTI-068-03": "doctor --all-workspacesはlimitsを最上位にだけ置く",
    "MULTI-068-04": "メンバーの中の単独のdoctorはルートの設定のlimitsを返す",
    "MULTI-068-05": "limitsのmemberCountは未知のキーとして警告にし判定に使わない",
    "MULTI-068-06": "メンバーの設定がlimitsを持てば複合ワークスペースの設定不適合にする",
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
    raise ValueError("派生の群は`entries_of`を使いません")


def current_entries(identifier):
    """`base`の群の現在版の木構造（準備の処理を適用した後）。"""
    case = CASES[identifier]
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
        tree[path] = (content + limits_block(case["limits"]).encode(), executable)
        return tree
    return {path: (content, False) for path, content in entries_of(identifier)}


def reviewed_changes(identifier):
    return changes_of(identifier)[0] if CASES[identifier]["form"] == "base" else {}


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


def generated_result(identifier):
    case = CASES[identifier]
    form = case["form"]
    limits = dict(case.get("limits", []))
    if case["outcome"] == "argument":
        return None
    if form == "base":
        if case["outcome"] == "blocked":
            limit = dict(case["current_limits"])[case["report"]]
            return all_blocked_result("check", limit_diagnostic(case["report"], limit), dirty=True)
        result = scale.passed_check_result(multi_generator.workspace_counts(current_entries(identifier)))
        result["revision"]["dirty"] = True
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
    elif identifier == "MULTI-068-06":
        # メンバーの設定の禁止されたキーの診断は、メンバー自身の設定ではなくカタログの宣言を発生元にする
        # （`MULTI-048-04`の「メンバーは設定キーmultiWorkspaceを宣言できません」と同じ形）。文言は承認済みの対応表。
        result = json.loads((HERE / "multi/MULTI-048-04/expected/check.json").read_text())
        result["diagnostics"][0].update(code="SPEC-MULTI-CONFIG-001", summary="メンバーの設定は設定キーlimitsを指定できません")
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
        source = {"MULTI-068-02": "MULTI-037-15", "MULTI-068-06": "MULTI-048-04"}.get(identifier, case["base"])
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
        expect.update({"status": status, "exitCode": {"passed": 0, "blocked": 2}[status], "stdout": "json",
                       "resultFile": expected_name(identifier)})
    operations = changes_of(identifier)[1] if case["form"] == "base" else []
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
    elif form == "base":
        base, current = entries_of(identifier), current_entries(identifier)
        # 上限は現在版の設定から決める（複合ワークスペース仕様 §10）。基準版の設定の`limits`は使わない。
        limits = case["current_limits"]
        crossing = ["statementCount"] if case["outcome"] == "blocked" else []
        check_snapshot(base, limits, crossing)
        check_snapshot(current, limits, [])
        if case["base_limits"]:
            check_snapshot(base, case["base_limits"], ["statementCount"])
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
