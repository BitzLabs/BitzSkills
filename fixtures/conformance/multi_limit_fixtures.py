"""複合workspaceのresource上限の境界を固定するreview済みvector（Core操作は実行しない）。

8つのdimensionについて、`limit - 1`と`limit`は誤って遮断しないこと、`limit + 1`は
`SPEC-MULTI-LIMIT-001`／`blocked`で早期に停止することを固定する。入力はversion管理できない大きさになるため、
[ADR-048](../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)に従い
dataset manifestから生成する（`multi_generator`）。

既定の監査は縮小profileで生成器の決定論とdimensionの計数を照合する。実寸の生成とtree digestの照合は
`uv run fixtures/validate_scale.py`が行う。
"""
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_reference, multi_generator
from .harness import tree_digest_bytes

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
LIMITS = multi_generator.LIMITS
# matrix §7の並び。dimensionごとにlimit - 1、limit、limit + 1を1件ずつ持つ。
ORDER = ("memberCount", "specFileCount", "inputBytes", "statementCount",
         "relationEdgeCount", "traceEntryCount", "commandDefinitionCount", "verifyBindingCount")
VERIFY_DIMENSION = "verifyBindingCount"
# bindingは必ずcommand定義の部分集合なので、binding上限の超過はcommand定義の超過を伴う。
# 複合workspace仕様 §10に従い、報告するdimensionはverify実行計画側とする。
COMPANIONS = {"MULTI-021-08": ["commandDefinitionCount"]}
LABELS = {
    "memberCount": "member数", "specFileCount": "SPEC file数", "inputBytes": "入力byte数",
    "statementCount": "規範文数", "relationEdgeCount": "relation edge数",
    "traceEntryCount": "trace項目数", "commandDefinitionCount": "command定義数",
    "verifyBindingCount": "verify binding数",
}


def cases():
    """fixture ID -> (dimension, 値, 越えるか)。"""
    entries = {}
    for index, dimension in enumerate(ORDER):
        limit = LIMITS[dimension]
        entries[f"MULTI-020-{index * 2 + 1:02d}"] = (dimension, limit - 1, False)
        entries[f"MULTI-020-{index * 2 + 2:02d}"] = (dimension, limit, False)
    for index, dimension in enumerate(ORDER):
        entries[f"MULTI-021-{index + 1:02d}"] = (dimension, LIMITS[dimension] + 1, True)
    return entries


CASES = cases()


def operation(dimension):
    return "verify" if dimension == VERIFY_DIMENSION else "check"


def description(identifier):
    dimension, value, crosses = CASES[identifier]
    kind = "超過を早期に停止する" if crosses else "境界内を誤って遮断しない"
    return f"{LABELS[dimension]}{value:,}の{kind}"


def reviewed_dataset(identifier):
    dimension, value, _ = CASES[identifier]
    return multi_generator.dataset(identifier, dimension, value)


def canonical_digest(value):
    """期待結果と観測値を、Digestと同じRFC 8785 Canonical JSONのSHA-256で固定する。"""
    return digest_reference.digest(digest_reference.canonical_bytes(value))


def reviewed_manifest(identifier, tree_digest, result_digest):
    dimension, _, crosses = CASES[identifier]
    name = operation(dimension)
    argv = [name, "--all-workspaces"]
    if name == "check":
        argv += ["--base", "HEAD"]
    argv += ["--format", "json"]
    return {
        "fixtureId": identifier,
        "description": description(identifier),
        "setup": {"git": True,
                  "generate": {"dataset": "dataset.json", "treeDigest": tree_digest},
                  "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": "blocked" if crosses else "passed",
                   "exitCode": 2 if crosses else 0,
                   "stdout": "json", "resultDigest": result_digest,
                   "reportFileCount": 0},
    }


def limit_diagnostic(dimension, value):
    return {
        "code": "SPEC-MULTI-LIMIT-001", "severity": "error", "resultStatus": "blocked",
        "summary": f"{LABELS[dimension]}が上限{LIMITS[dimension]:,}を超過しました",
        "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"},
        # 早期停止のため正確な総数を求めない。越えたことがわかる最小の値を記録する。
        "evidence": {"dimension": dimension, "limit": LIMITS[dimension], "observedAtLeast": value},
    }


def blocked_result(identifier):
    dimension, value, _ = CASES[identifier]
    name = operation(dimension)
    revision = ({"commit": COMMIT, "dirty": False} if name == "verify"
                else {"base": COMMIT, "commit": COMMIT, "dirty": False})
    return {
        "schemaVersion": "1.0", "operation": name, "scope": "all-workspaces", "status": "blocked",
        "multiWorkspace": {"id": "platform", "path": "."},
        # 事前検査で停止するので、member処理もcommand実行も始めない。
        "workspaces": [],
        "revision": revision,
        "durationMs": 0,
        "diagnostics": [limit_diagnostic(dimension, value)],
    }


def passed_check_result(counts):
    workspaces = []
    for workspace in sorted(counts, key=lambda path: ("" if path == "." else path)):
        documents, statements = counts[workspace]
        workspaces.append({
            "id": "platform" if workspace == "." else workspace.rsplit("/", 1)[-1],
            "path": workspace,
            "status": "passed",
            "checkedDocumentCount": documents,
            "checkedStatementCount": statements,
            "durationMs": 0, "diagnostics": [],
        })
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": workspaces,
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier, counts=None):
    dimension, _, crosses = CASES[identifier]
    if crosses:
        return blocked_result(identifier)
    if dimension == VERIFY_DIMENSION:
        raise ValueError("binding境界の期待結果は別に扱う")
    return passed_check_result(counts)


def binding_documents(entries):
    """生成したtreeから、workspaceごとのbinding文書（ID、規範文、test対応）の列を読み取る。

    Frontmatter 32 KiB上限（文書・Frontmatter・状態仕様 §11）を守るため、1 workspaceのtest対応は
    複数のbinding文書へ分けて生成することがある（multi_generator.BINDINGS_PER_DOCUMENT）。
    そのため1 workspaceにつき複数件のbinding文書を保持できるよう、値はlistで返す。
    """
    documents = {}
    for path, content in entries:
        if not path.endswith(".md"):
            continue
        workspace = path.rsplit("/.spec/", 1)[0] if "/.spec/" in path else "."
        text = content.decode("utf-8")
        head, _, body = text.partition("\n---\n")
        tests = []
        for line in head.split("\n"):
            if line.startswith("  - path: "):
                tests.append({"path": line[len("  - path: "):]})
            elif line.startswith("    covers: ["):
                tests[-1]["covers"] = line[len("    covers: ["):-1]
            elif line.startswith("    command: "):
                tests[-1]["command"] = line[len("    command: "):]
        if not tests:
            continue
        identifier = head.split("\nid: ", 1)[1].split("\n", 1)[0]
        statements = [line[3:].split("]", 1)[0] for line in body.split("\n")
                      if multi_generator.STATEMENT.match(line)]
        documents.setdefault(workspace, []).append(
            {"id": identifier, "statements": statements, "tests": tests})
    return documents


def passed_binding_result(entries, digests):
    """binding境界のverify結果。生成treeのbinding文書とtest対応から組み立てる。"""
    documents = binding_documents(entries)
    workspaces = []
    for workspace in sorted(documents, key=lambda path: ("" if path == "." else path)):
        workspace_id = "platform" if workspace == "." else workspace.rsplit("/", 1)[-1]
        target_results = []
        commands = []
        for document in documents[workspace]:
            target = f"{workspace_id}::{document['id']}"
            document_commands = [{
                "bindingId": f"{workspace_id}::{entry['command']}", "workspaceId": workspace_id,
                "name": entry["command"], "status": "passed", "termination": "exit", "cwd": ".",
                "argv": ["/bin/true", entry["path"]], "tests": [entry["path"]],
                "covers": [f"{workspace_id}::{entry['covers']}"], "exitCode": 0, "timeoutSeconds": 300,
                "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False,
                "stderrTruncated": False, "durationMs": 0,
            } for entry in sorted(document["tests"], key=lambda item: item["command"])]
            target_results.append({
                "target": target, "status": "passed", "contextDigest": digests[target],
                "statements": [f"{workspace_id}::{statement}" for statement in document["statements"]],
                "bindingRefs": [command["bindingId"] for command in document_commands],
                "diagnostics": [],
            })
            commands.extend(document_commands)
        workspaces.append({
            "id": workspace_id, "path": workspace, "status": "passed",
            "targetResults": target_results,
            "commands": commands, "durationMs": 0, "diagnostics": [],
        })
    return {
        "schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": workspaces,
        "revision": {"commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": [],
    }


def check_passed_result(result, dataset):
    """期待結果の件数を、dataset manifestの宣言値と突き合わせる。実寸の生成は要求しない。"""
    dimensions = dataset["dimensions"]
    if result["scope"] != "all-workspaces" or result["status"] != "passed" or result["diagnostics"]:
        raise ValueError("境界内のcaseは遮断も警告も持ちません")
    if len(result["workspaces"]) != dimensions["memberCount"] + 1:
        raise ValueError("member結果の件数がcatalogと一致しません")
    if sum(entry["checkedDocumentCount"] for entry in result["workspaces"]) != dimensions["specFileCount"]:
        raise ValueError("検査した文書数の合計がSPEC file数と一致しません")
    if sum(entry["checkedStatementCount"] for entry in result["workspaces"]) != dimensions["statementCount"]:
        raise ValueError("検査した規範文数の合計が規範文数と一致しません")
    if any(entry["status"] != "passed" or entry["diagnostics"] for entry in result["workspaces"]):
        raise ValueError("境界内のcaseは全workspaceが成功します")


def check_binding_result(result, dataset):
    """verifyの境界内caseは、計画したbindingをすべて実行して成功する。"""
    dimensions = dataset["dimensions"]
    if result["scope"] != "all-workspaces" or result["status"] != "passed" or result["diagnostics"]:
        raise ValueError("境界内のcaseは遮断も警告も持ちません")
    if len(result["workspaces"]) != dimensions["memberCount"] + 1:
        raise ValueError("member結果の件数がcatalogと一致しません")
    executed = {command["bindingId"] for entry in result["workspaces"] for command in entry["commands"]}
    if len(executed) != dimensions["verifyBindingCount"]:
        raise ValueError("実行したbindingの件数がdatasetと一致しません")
    referenced = {binding for entry in result["workspaces"]
                  for target in entry["targetResults"] for binding in target["bindingRefs"]}
    if referenced != executed:
        raise ValueError("参照したbindingと実行したbindingが一致しません")
    for entry in result["workspaces"]:
        for command in entry["commands"]:
            if command["workspaceId"] != entry["id"] or command["status"] != "passed":
                raise ValueError("command実体は所有workspaceへ置き、成功する必要があります")
        for target in entry["targetResults"]:
            if target["status"] != "passed" or target["contextDigest"] is None:
                raise ValueError("境界内のcaseは全targetが成功しDigestを持ちます")


def reduced_dimensions(manifest):
    """縮小profileの宣言値。生成器の計数と照合する。"""
    reduced = multi_generator.reduced(manifest)
    return reduced, multi_generator.count(
        multi_generator.emit(multi_generator.plan(reduced["dimension"], reduced["value"])))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        dimension, value, crosses = CASES[identifier]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            dataset = json.loads((fixture / "dataset.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if (fixture / "repo").exists() or (fixture / "expected").exists():
                raise ValueError("生成fixtureはrepoと期待fileを持ちません")
            if "resultFile" in manifest["expect"] or "resultDigest" not in manifest["expect"]:
                raise ValueError("生成fixtureの期待結果はdigestで固定します")
            if "stateDigest" not in effects or effects["policy"] != "read-only":
                raise ValueError("生成fixtureの副作用期待値はstate digestで固定します")
            # 実寸の生成はscale検証が行う。ここではdataset manifestの宣言だけを照合する。
            if [dataset["schemaVersion"], dataset["fixtureId"], dataset["dimension"],
                    dataset["value"], dataset["limit"], dataset["crosses"]] != [
                    "1.0", identifier, dimension, value, LIMITS[dimension], crosses]:
                raise ValueError("dataset manifestの宣言が審査済みcaseと異なります")
            if set(dataset["dimensions"]) != set(multi_generator.DIMENSIONS):
                raise ValueError("dataset manifestのdimensionが8つそろっていません")
            if manifest != reviewed_manifest(identifier, manifest["setup"]["generate"]["treeDigest"],
                                             manifest["expect"]["resultDigest"]):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if dataset["crosses"] != crosses or dataset["dimensions"][dimension] != value:
                raise ValueError("datasetが狙ったdimensionと異なります")
            companions = COMPANIONS.get(identifier, [])
            if dataset.get("companionDimensions", []) != companions:
                raise ValueError("同時に超過するdimensionの宣言が審査済みcaseと異なります")
            for name, observed in dataset["dimensions"].items():
                if name != dimension and observed > LIMITS[name] and name not in companions:
                    raise ValueError(f"{name}も上限を超えています")
            if crosses and manifest["expect"]["resultDigest"] != canonical_digest(blocked_result(identifier)):
                # 上限超過の期待結果は小さく、生成物に依存しないのでここで完全に照合できる。
                raise ValueError("完全結果が審査済み期待値と異なります")
            # 既定の監査では縮小profileだけを生成し、生成器の決定論と計数を照合する。
            reduced, counted = reduced_dimensions(dataset)
            profile = multi_generator.plan(reduced["dimension"], reduced["value"])
            first = multi_generator.emit(profile)
            second = multi_generator.emit(multi_generator.plan(reduced["dimension"], reduced["value"]))
            if first != second:
                raise ValueError("縮小profileの生成が2回で一致しません")
            if counted[dimension] != reduced["value"]:
                raise ValueError("縮小profileの計数が生成計画と異なります")
            if (counted[dimension] > reduced["limit"]) != crosses:
                raise ValueError("縮小profileが越える側と越えない側を保っていません")
            if tree_digest_bytes(first) != tree_digest_bytes(second):
                raise ValueError("縮小profileのtree digestが2回で一致しません")
            counts = multi_generator.workspace_counts(first)
            if len(counts) != counted["memberCount"] + 1:
                raise ValueError("生成したworkspace数がcatalogと一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "generated_profiles": "reduced", "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
