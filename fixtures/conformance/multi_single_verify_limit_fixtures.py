"""複合ワークスペースの単独の`verify`が、リソースの上限を実行計画の確定後に判定することを固定する（Coreの公開操作は実行しない）。

[ADR-066](../../docs/02.設計書/10_決定記録/ADR-066_単独のverifyの上限を実行計画の確定後に判定する.md)（実装の確認事項C40）は、
複合ワークスペースの単独の`verify`が、`--all-workspaces`と同じく、`commandDefinitionCount`を全体事前検査では判定せず、実行計画を確定した後
（対象展開とテスト割当ての重複排除が終わった後、コマンドを1件も起動する前）に`verifyBindingCount`と合わせて判定すると定める。
両方が超過していれば`verifyBindingCount`、`commandDefinitionCount`だけが超過していればそれを、診断`SPEC-MULTI-LIMIT-001`（`blocked`）で報告する
（複合ワークスペース仕様 §10）。この群は、その判定を4件で固定する。ADR-063の決定8の以前の扱い（全体事前検査で`commandDefinitionCount`を先に判定する）では
`MULTI-041-01`と`MULTI-041-04`が成立しない。

| fixture | 起動 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-041-01` | `verify`＋ルートのREQ全件、`.` | 実行計画のテスト割当て10,001件、コマンド定義10,001件（両方が超過） | `blocked`／2。`dimension=verifyBindingCount`、`limit=10000`、`observedAtLeast=10001` |
| `MULTI-041-02` | `verify`＋ルートのREQ全件、`.` | 実行計画のテスト割当て10,000件（上限内）、コマンド定義10,001件（超過） | `blocked`／2。`dimension=commandDefinitionCount`、`limit=10000`、`observedAtLeast=10001` |
| `MULTI-041-03` | `verify`＋ルートのREQ全件、`.` | 実行計画のテスト割当て10,000件、コマンド定義10,000件（境界値） | `passed`／0。10,000件のコマンドをすべて実行する（`MULTI-020-16`の単独版） |
| `MULTI-041-04` | `verify --workspace nope`、`.` | 実行計画は小さく、コマンド定義10,001件（超過）。`--workspace`のIDがカタログにない | 終了コード4（結果なし）。全体事前検査が成功するので、上限より引数不正を先に返す |

入力は、`MULTI-020-*`・`MULTI-021-*`と同じくバージョン管理できない大きさになるため、[ADR-048](../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造の準備の処理を確定する.md)に従い
データセットのマニフェストから生成する（`multi_generator.single_verify_plan`）。既存の生成計画（`plan`の`verifyBindingCount`）は割当てを全ワークスペースへ散らし、
各文書が自分のワークスペースの規範文を`covers`するので、ルートからの1回の単独の`verify`では、ルートの分にしか届かない。この群の生成計画は、
ルート`platform`が検証対象のREQだけを持ち、メンバーのTECHがそのREQを`refines`して`covers`する。ルートで`verify`にREQを全件並べると、
1回の実行計画がメンバー全体のテスト割当てになる。1件のREQだけでは、コンテキストの閉包の上限（20文書・128 KiB。コンテキスト仕様 §8）に収まらない。

期待値の根拠は規範文（複合ワークスペース仕様 §7・§10、`verify` §3・§4・§8、結果・診断・終了コード §2、ADR-066）と、このモジュールの参照計算だけである。
Coreの出力は期待値の根拠にしない。診断の文言は`Coreの出力文言のレビュー記録.md`の承認済みの文字列（`multi_limit_fixtures.SUMMARY_LABELS`）である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_crosscheck, multi_generator
from .harness import setup, tree_digest_bytes, write_generated
from .initial_fixtures import observe
from .multi_limit_fixtures import COMMIT, LIMITS, canonical_digest, limit_diagnostic
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
LIMIT = LIMITS["verifyBindingCount"]
assert LIMIT == LIMITS["commandDefinitionCount"] == 10000
UNKNOWN_WORKSPACE = "nope"
# id: dict(形, 超過の判定の次元, テスト割当て数, コマンド定義数, 結果, 同時に超える次元, 説明)
CASES = {
    "MULTI-041-01": dict(form="targets", dimension="verifyBindingCount", bindings=LIMIT + 1, commands=LIMIT + 1,
                         outcome="blocked", companions=["commandDefinitionCount"],
                         description="単独のverifyで実行計画のテスト割当てが10,001件、コマンド定義数も10,001件のとき、テスト割当て数を優先して超過を報告する"),
    "MULTI-041-02": dict(form="targets", dimension="commandDefinitionCount", bindings=LIMIT, commands=LIMIT + 1,
                         outcome="blocked", companions=[],
                         description="単独のverifyで実行計画のテスト割当てが上限内の10,000件で、コマンド定義数だけが10,001件のとき、コマンド定義数の超過を報告する"),
    "MULTI-041-03": dict(form="targets", dimension="verifyBindingCount", bindings=LIMIT, commands=LIMIT,
                         outcome="passed", companions=[],
                         description="単独のverifyで実行計画のテスト割当てもコマンド定義数も境界値の10,000件のとき、誤って遮断せず全件を実行する"),
    "MULTI-041-04": dict(form="unknown-workspace", dimension="commandDefinitionCount", bindings=1, commands=LIMIT + 1,
                         outcome="argument", companions=[],
                         description="コマンド定義数だけが超過しカタログにない--workspaceを指定した単独のverifyは、全体事前検査が成功するので上限ではなく引数不正として拒否する"),
}


def crosses(identifier):
    case = CASES[identifier]
    return case["outcome"] in {"blocked", "argument"}


def profile(identifier):
    case = CASES[identifier]
    return multi_generator.single_verify_plan(case["bindings"], case["commands"], case["dimension"])


def dataset_value(identifier):
    case = CASES[identifier]
    return case["bindings"] if case["dimension"] == "verifyBindingCount" else case["commands"]


def reviewed_dataset(identifier):
    """fixtureへコミットするデータセットのマニフェスト。宣言値は、生成物のバイト列からの計数と一致する。"""
    case = CASES[identifier]
    totals = multi_generator.count(multi_generator.emit(profile(identifier)))
    dataset = {
        "schemaVersion": "1.0",
        "fixtureId": identifier,
        "dimension": case["dimension"],
        "value": dataset_value(identifier),
        "limit": LIMIT,
        "crosses": crosses(identifier),
        "profile": {"kind": "single-verify-plan", "bindings": case["bindings"], "commands": case["commands"]},
        "dimensions": {name: totals[name] for name in multi_generator.DIMENSIONS},
    }
    if case["companions"]:
        dataset["companionDimensions"] = list(case["companions"])
    return dataset


def targets(identifier):
    return multi_generator.single_verify_targets(profile(identifier))


def argv_of(identifier):
    if CASES[identifier]["form"] == "unknown-workspace":
        return ["verify", "--workspace", UNKNOWN_WORKSPACE, "--format", "json"]
    return ["verify", *targets(identifier), "--format", "json"]


def reviewed_manifest(identifier, tree_digest, result_digest=None):
    case = CASES[identifier]
    expect = {"reportFileCount": 0}
    if case["outcome"] == "argument":
        expect.update({"exitCode": 4, "stdout": "none"})
    else:
        blocked = case["outcome"] == "blocked"
        expect.update({"status": "blocked" if blocked else "passed", "exitCode": 2 if blocked else 0,
                       "stdout": "json", "resultDigest": result_digest})
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True,
                  "generate": {"dataset": "dataset.json", "treeDigest": tree_digest},
                  "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv_of(identifier), "env": {}},
        "expect": expect,
    }


def reviewed_cli_output():
    """引数不正（終了コード4）は結果を作らず、標準エラーに1行の理由を書く（Core実行環境・CLI基盤契約 §5）。"""
    return {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: verify: ", "stderrLineCount": 1,
            "stderrReasonRequired": True, "stderrTerminalControls": False}


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def single_result(status, target_results, commands, diagnostics):
    """複合ワークスペース内の単独の`verify`の結果（結果・診断・終了コード §2）。明示対象なので`scope`は`selected`。"""
    return {
        "schemaVersion": "1.0", "operation": "verify", "scope": "selected", "status": status,
        "workspace": {"id": "platform", "path": "."},
        "targetResults": target_results,
        "commands": commands,
        "revision": {"commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": diagnostics,
    }


def blocked_result(identifier):
    """上限の超過は複合ワークスペース全体を`blocked`にし、部分的な結果やコマンドの実行へ進まない（複合ワークスペース仕様 §10）。
    実行計画を確定した後に判定しても、検証対象ごとの結果とコマンドは返さない。"""
    case = CASES[identifier]
    # 早期停止のため正確な総数を求めない。越えたことがわかる最小の値（上限+1）を記録する。ここでの超過はちょうど上限+1である。
    return single_result("blocked", [], [], [limit_diagnostic(case["dimension"], LIMIT + 1)])


def refining_documents(entries):
    """生成した木構造から、メンバーのTECH（検証対象のREQを`refines`する具体化文書）を読み取る。"""
    documents = []
    for path, content in entries:
        if "/.spec/technical/" not in path:
            continue
        workspace_id = path.split("/.spec/", 1)[0].rsplit("/", 1)[-1]
        head = content.decode("utf-8").partition("\n---\n")[0]
        tests, refined = [], None
        for line in head.split("\n"):
            if line.startswith("  refines: ["):
                refined = line[len("  refines: ["):-1]
            elif line.startswith("  - path: "):
                tests.append({"path": line[len("  - path: "):]})
            elif line.startswith("    covers: ["):
                tests[-1]["covers"] = line[len("    covers: ["):-1].split(", ")
            elif line.startswith("    command: "):
                tests[-1]["command"] = line[len("    command: "):]
        documents.append({"workspace": workspace_id, "refines": refined, "tests": tests})
    return documents


def requirements(entries):
    """生成した木構造から、ルートのREQ（検証対象）と、その規範文のIDを読み取る。"""
    found = {}
    for path, content in entries:
        if not path.startswith(".spec/requirements/"):
            continue
        body = content.decode("utf-8").partition("\n---\n")[2]
        identifier = path.rsplit("/", 1)[-1][:-3]
        found[f"platform::{identifier}"] = [f"platform::{line[3:].split(']', 1)[0]}" for line in body.split("\n")
                                            if multi_generator.STATEMENT.match(line)]
    return found


def context_digests(entries, repository):
    """検証対象ごとのコンテキストのハッシュ値を、入力の木構造からの導出で求める（`multi_crosscheck`）。"""
    loaded = multi_crosscheck.load_workspaces(repository)
    return {target: multi_crosscheck.digest(multi_crosscheck.canonical_bytes(
                multi_crosscheck.build(repository, target, loaded=loaded)))
            for target in requirements(entries)}


def passed_result(entries, digests):
    """境界値の単独の`verify`の結果。検証対象ごとの結果と、所有ワークスペースが1回だけ実行したコマンドを、生成した木構造から組み立てる。"""
    statements = requirements(entries)
    documents = refining_documents(entries)
    refs = {target: [] for target in statements}
    runs = {}
    for document in documents:
        target = document["refines"]
        for entry in document["tests"]:
            binding = f"{document['workspace']}::{entry['command']}"
            refs[target].append(binding)
            run = runs.setdefault(binding, {"workspace": document["workspace"], "name": entry["command"],
                                            "tests": set(), "covers": set()})
            run["tests"].add(entry["path"])
            run["covers"].update(entry["covers"])
    target_results = [{
        "target": target, "status": "passed", "contextDigest": digests[target],
        "statements": sorted(statements[target]), "bindingRefs": sorted(set(refs[target])),
        "diagnostics": [],
    } for target in sorted(statements)]
    commands = []
    # ワークスペースの処理順（ルート、その後はIDの辞書順）、コマンド名の辞書順（`verify` §4の6.）。
    for binding in sorted(runs, key=lambda value: (runs[value]["workspace"], runs[value]["name"])):
        run = runs[binding]
        tests = sorted(run["tests"])
        commands.append({
            "bindingId": binding, "workspaceId": run["workspace"], "name": run["name"],
            "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", *tests], "tests": tests, "covers": sorted(run["covers"]),
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0,
        })
    return single_result("passed", target_results, commands, [])


def expected_body(identifier, entries, repository):
    """生成fixtureの期待結果（偽Coreと規模の検証が使う）。引数不正は結果を持たない。"""
    outcome = CASES[identifier]["outcome"]
    if outcome == "argument":
        return None
    if outcome == "blocked":
        return blocked_result(identifier)
    return passed_result(entries, context_digests(entries, repository))


def check_passed_result(result, dataset):
    """境界値のケースは、計画したテスト割当てをすべて1回ずつ実行して成功する。"""
    dimensions = dataset["dimensions"]
    if result["scope"] != "selected" or result["status"] != "passed" or result["diagnostics"]:
        raise ValueError("境界値のケースは遮断も警告も持ちません")
    executed = [command["bindingId"] for command in result["commands"]]
    if len(executed) != dimensions["verifyBindingCount"] or len(set(executed)) != len(executed):
        raise ValueError("実行したテスト割当ての件数がデータセットと一致しません")
    referenced = {binding for target in result["targetResults"] for binding in target["bindingRefs"]}
    if referenced != set(executed):
        raise ValueError("参照したテスト割当てと実行したテスト割当てが一致しません")
    if len(result["targetResults"]) != dimensions["statementCount"]:
        raise ValueError("検証対象の件数が規範文の件数と一致しません")
    for target in result["targetResults"]:
        if target["status"] != "passed" or target["contextDigest"] is None or not target["statements"]:
            raise ValueError("境界値のケースは全検証対象が成功しハッシュ値を持ちます")
    for command in result["commands"]:
        if command["status"] != "passed" or command["bindingId"].split("::")[0] != command["workspaceId"]:
            raise ValueError("コマンド実体は所有ワークスペースへ置き、成功する必要があります")


# --- 生成 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def observed_state(fixture, manifest, entries, sandbox):
    repository = setup(fixture, manifest, sandbox / "repo", generated=entries)
    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
    for path in external.values():
        path.mkdir()
    return observe(repository, external)


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。期待結果と副作用の期待値は、隔離した準備手順の観測と参照計算で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        fixture.mkdir(parents=True, exist_ok=True)
        dataset = reviewed_dataset(identifier)
        (fixture / "dataset.json").write_text(_dump(dataset))
        entries = multi_generator.generate(dataset)
        tree_digest = tree_digest_bytes(entries)
        outcome = CASES[identifier]["outcome"]
        result_digest = None
        with tempfile.TemporaryDirectory(prefix="bitz-single-verify-limit-") as temporary:
            sandbox = Path(temporary)
            if outcome == "passed":
                repository = sandbox / "context"
                repository.mkdir()
                write_generated(entries, repository)
                result_digest = canonical_digest(passed_result(entries, context_digests(entries, repository)))
            elif outcome == "blocked":
                result_digest = canonical_digest(blocked_result(identifier))
            manifest = reviewed_manifest(identifier, tree_digest, result_digest)
            (fixture / "manifest.json").write_text(_dump(manifest))
            state = observed_state(fixture, manifest, entries, sandbox / "run")
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "stateDigest": canonical_digest(state)}))
        if outcome == "argument":
            (fixture / "cli-output.json").write_text(_dump(reviewed_cli_output()))


# --- 監査 ---------------------------------------------------------------------------------

def reduced_profile(identifier):
    """縮小した生成計画。上限も同じ比率（1/100）で縮め、越える／越えないの関係をそのまま保つ。"""
    case = CASES[identifier]
    scaled = LIMIT // 100

    def shrink(value):
        return value - LIMIT + scaled if value > scaled else value

    return {"bindings": shrink(case["bindings"]), "commands": shrink(case["commands"]), "limit": scaled}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        case = CASES[identifier]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            dataset = json.loads((fixture / "dataset.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if (fixture / "repo").exists() or (fixture / "expected").exists():
                raise ValueError("生成fixtureは`repo`と期待結果のファイルを持ちません")
            if "resultFile" in manifest["expect"]:
                raise ValueError("生成fixtureの期待結果はハッシュ値で固定します")
            if "stateDigest" not in effects or effects["policy"] != "read-only":
                raise ValueError("生成fixtureの副作用の期待値は状態のハッシュ値で固定します")
            declared = reviewed_dataset_declaration(identifier)
            actual = {key: dataset.get(key) for key in declared}
            if actual != declared:
                raise ValueError("データセットのマニフェストの宣言がレビュー済みのケースと異なります")
            if set(dataset["dimensions"]) != set(multi_generator.DIMENSIONS):
                raise ValueError("データセットのマニフェストの次元が8つそろっていません")
            if dataset["dimensions"]["verifyBindingCount"] != case["bindings"] \
                    or dataset["dimensions"]["commandDefinitionCount"] != case["commands"]:
                raise ValueError("データセットがテスト割当て数とコマンド定義数を宣言どおりに持ちません")
            if dataset.get("companionDimensions", []) != case["companions"]:
                raise ValueError("同時に超える次元の宣言がレビュー済みのケースと異なります")
            for name, observed in dataset["dimensions"].items():
                if observed > LIMITS[name] and name not in {case["dimension"], *case["companions"]}:
                    raise ValueError(f"{name}も上限を超えています")
            if case["outcome"] == "passed" and any(
                    observed > LIMITS[name] for name, observed in dataset["dimensions"].items()):
                raise ValueError("境界値のケースはどの次元も上限を超えません")
            if manifest != reviewed_manifest(identifier, manifest["setup"]["generate"]["treeDigest"],
                                             manifest["expect"].get("resultDigest")):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if case["outcome"] == "blocked":
                result = blocked_result(identifier)
                validators["result"].validate(result)
                if manifest["expect"]["resultDigest"] != canonical_digest(result):
                    raise ValueError("完全結果がレビュー済みの期待値と異なります")
                if result["diagnostics"][0]["evidence"] != {
                        "dimension": case["dimension"], "limit": LIMIT, "observedAtLeast": LIMIT + 1}:
                    raise ValueError("診断のevidenceが規範の次元と異なります")
            if case["outcome"] == "argument":
                cli_output = json.loads((fixture / "cli-output.json").read_text())
                if cli_output != reviewed_cli_output():
                    raise ValueError("標準エラーの期待値がレビュー済みの期待値と異なります")
            elif (fixture / "cli-output.json").exists():
                raise ValueError("結果を返すfixtureは`cli-output.json`を持ちません")
            # 既定の監査では縮小した生成計画だけを生成し、生成器の決定論、次元の計数、期待結果の組立てを照合する。
            reduced = reduced_profile(identifier)
            first = multi_generator.emit(multi_generator.single_verify_plan(
                reduced["bindings"], reduced["commands"], case["dimension"]))
            second = multi_generator.emit(multi_generator.single_verify_plan(
                reduced["bindings"], reduced["commands"], case["dimension"]))
            if first != second or tree_digest_bytes(first) != tree_digest_bytes(second):
                raise ValueError("縮小した生成計画の生成が2回で一致しません")
            counted = multi_generator.count(first)
            if counted["verifyBindingCount"] != reduced["bindings"] or counted["commandDefinitionCount"] != reduced["commands"]:
                raise ValueError("縮小した生成計画の計数が計画の値と異なります")
            if (counted[case["dimension"]] > reduced["limit"]) != crosses(identifier):
                raise ValueError("縮小した生成計画が越える側と越えない側を保っていません")
            if case["dimension"] == "commandDefinitionCount" and counted["verifyBindingCount"] > reduced["limit"]:
                raise ValueError("計画のテスト割当てが上限を超えています")
            check_reduced_result(first)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "generated_profiles": "reduced", "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}


def reviewed_dataset_declaration(identifier):
    """データセットのマニフェストのうち、ケースから決まる宣言。"""
    case = CASES[identifier]
    return {"schemaVersion": "1.0", "fixtureId": identifier, "dimension": case["dimension"],
            "value": dataset_value(identifier), "limit": LIMIT, "crosses": crosses(identifier),
            "profile": {"kind": "single-verify-plan", "bindings": case["bindings"], "commands": case["commands"]}}


def check_reduced_result(entries):
    """縮小した木構造から、成功する場合の期待結果を組み立て、検証対象とコマンドの対応を保つことを照合する（越える側の入力も同じ形の木構造である）。"""
    totals = multi_generator.count(entries)
    with tempfile.TemporaryDirectory(prefix="bitz-single-verify-reduced-") as temporary:
        repository = Path(temporary)
        write_generated(entries, repository)
        result = passed_result(entries, context_digests(entries, repository))
    check_passed_result(result, {"dimensions": totals})
