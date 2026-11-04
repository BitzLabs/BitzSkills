"""複合ワークスペースの閉包が、逆参照の出発点を起点を所有する文書だけにし、`refines`の参照先の`requires`を辿らないことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C91に対応する。参照計算B（`multi_crosscheck`と`digest_crosscheck`）の閉包は、到達したすべての文書から逆参照を辿り、`refines`の参照先の`requires`も辿っていたので、
関係・トレースモデル §6.1の3.・4.より広い閉包を作った。Coreの閉包（`targetexpand`）は規範どおりであり、この群は、参照計算Bが規範どおりの閉包を導くことを固定する。
`MULTI-052`の生成器は、この欠陥を避けるために閉包をリテラルで書いていた。

- 関係・トレースモデル §6.1の3.: 起点を所有する文書の`refines`の参照先だけを含める。その参照先の`requires`は辿らない。
- §6.1の4.: 起点を所有する文書またはその規範文を`refines`する適用可能な文書を逆参照で含める。逆参照の出発点は起点を所有する文書だけであり、
  `requires`で到達した文書を`refines`する文書は含めない。
- §6.3: `verify`は`interpret`の閉包に、対象規範文のテスト対応、コマンド、実装のパスを加える。複合ワークスペースでは、閉包に入った文書を所有するワークスペースの設定とコマンドだけを材料に含める
  （複合ワークスペース仕様 §6、正規化仕様 §3）。

| fixture | 操作と実行ディレクトリ | 構成 | 期待 |
|---|---|---|---|
| `MULTI-059-01` | `verify --all-workspaces`、`.` | ルート`zeta`、メンバー`beta`・`alpha`。ルートの`REQ-001`（`AC-01`、`AC-02`）を、`alpha`の`TECH-001`が`AC-01`、`beta`の`TECH-001`が`AC-02`について具体化する | 検証対象は3件。`REQ-001`の閉包は3文書、メンバーの`TECH-001`の閉包は自身と`zeta::REQ-001`だけで、同じ`REQ`を具体化する別のメンバーの文書を含まない |
| `MULTI-059-02` | `verify REQ-001`、`.`（ルート） | ルート`zeta`。`REQ-001`が`REQ-002`を`requires`し、`alpha`と`beta`の`TECH-001`が、どちらも`REQ-002:AC-01`を具体化する | 閉包は`zeta::REQ-001`と`zeta::REQ-002`だけ。`requires`で到達した`REQ-002`を具体化するメンバーの文書も、そのワークスペースの設定とコマンドも含まない |
| `MULTI-059-03` | `verify --workspace alpha alpha::TECH-001`、`.` | ルート`zeta`、メンバー`alpha`。`zeta`の`REQ-001`が`REQ-002`を`requires`し、`alpha`の`TECH-001`が`REQ-001:AC-01`を具体化する | 閉包は`alpha::TECH-001`と、その`refines`の参照先`zeta::REQ-001`だけ。参照先が`requires`する`zeta::REQ-002`を含まない |

どのケースも、Coreの閉包は修正前から同じなので、Coreは修正前も通る。欠陥は参照計算Bにあり、修正前の参照計算Bは、`01`でメンバーの`TECH-001`、`02`でメンバーの`TECH-001`2件、`03`で`zeta::REQ-002`を
閉包へ含めて、ハッシュ値が期待値と一致しない（`defective_closure`が、修正前の広い閉包の導出を再現し、この入力が欠陥を検出できることを要求する）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（このモジュールのリテラルA、入力の木構造から導出するB。`multi_crosscheck`）のバイト列の一致を要求する。閉包は、リテラルと参照計算Bの一致を要求する
（検証対象ごとの規範文とテスト割当ては、`MULTI-052`と同じく`multi_context_order_fixtures.reference_order`から導く）。

`requires`を持つ複合ワークスペースの全体の`verify`は、閉包の外の文書が閉包内の文書を`requires`する辺を、参照計算Bが拒否する（既存の監査が固定する）ため、この群は`requires`を持つケースを単独の起点にする。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (multi_closure_alias_fixtures as alias, multi_context_order_fixtures as order, multi_crosscheck, multi_reference,
               multi_verify_fixtures as verify_fixtures)
from .harness import setup
from .initial_fixtures import compare_state, observe
from .multi_binding_order_fixtures import reference_order, reference_plan
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
TEST_BYTES = alias.TEST_BYTES
KIND_DIRECTORY = order.KIND_DIRECTORY
ARGV = ["/bin/true", "{tests}"]


def workspace_path(root, workspace):
    return "." if workspace == root else f"apps/{workspace}"


def kind_of(local):
    return {"REQ": "requirement", "TECH": "technical"}[local.partition("-")[0]]


# --- 構成（ワークスペースごとの文書。宣言どおりの表記で書く） ---------------------------------------------
#
# 文書: {(ワークスペース, ローカルID): dict(title, requires=宣言した参照, refines=宣言した参照, statements=[(ラベル, 文)], tests=[(パス, covers（宣言どおり）, コマンド名)])}。
# コマンド: {ワークスペース: [コマンド名]}。閉包: {検証対象（修飾ID）: [閉包の文書（修飾ID）]}。


def sibling_shape():
    """ルートの`REQ-001`（AC-01、AC-02）を、`alpha`の`TECH-001`が`AC-01`、`beta`の`TECH-001`が`AC-02`について具体化する（どちらも規範文なし）。"""
    documents = {
        ("zeta", "REQ-001"): dict(title="認証の基準", statements=[("AC-01", "秘密情報を出力しない"), ("AC-02", "入力を検証する")],
                                  tests=[("tests/p.py", ["REQ-001:AC-02", "REQ-001:AC-01"], "p")]),
        ("alpha", "TECH-001"): dict(title="AC-01の実装方針", refines=["zeta::REQ-001:AC-01"],
                                    tests=[("tests/t.py", ["zeta::REQ-001:AC-01"], "t")]),
        ("beta", "TECH-001"): dict(title="AC-02の実装方針", refines=["zeta::REQ-001:AC-02"],
                                   tests=[("tests/t.py", ["zeta::REQ-001:AC-02"], "t")]),
    }
    closure = {
        "zeta::REQ-001": ["alpha::TECH-001", "beta::TECH-001", "zeta::REQ-001"],
        "alpha::TECH-001": ["alpha::TECH-001", "zeta::REQ-001"],
        "beta::TECH-001": ["beta::TECH-001", "zeta::REQ-001"],
    }
    return documents, {"zeta": ["p"], "alpha": ["t"], "beta": ["t"]}, closure


def requires_target_shape():
    """ルートの`REQ-001`が`REQ-002`を`requires`し、`alpha`と`beta`の`TECH-001`が、どちらも`REQ-002:AC-01`を具体化する。
    `REQ-002`は`requires`で到達する文書で、逆参照の出発点にならない。"""
    documents = {
        ("zeta", "REQ-001"): dict(title="認証の基準", statements=[("AC-01", "秘密情報を出力しない")], requires=["REQ-002"],
                                  tests=[("tests/p.py", ["REQ-001:AC-01"], "p")]),
        ("zeta", "REQ-002"): dict(title="前提の基準", statements=[("AC-01", "入力を検証する")]),
        ("alpha", "TECH-001"): dict(title="前提の実装方針", refines=["zeta::REQ-002:AC-01"],
                                    tests=[("tests/t.py", ["zeta::REQ-002:AC-01"], "t")]),
        ("beta", "TECH-001"): dict(title="前提の別の実装方針", refines=["zeta::REQ-002:AC-01"],
                                   tests=[("tests/t.py", ["zeta::REQ-002:AC-01"], "t")]),
    }
    return documents, {"zeta": ["p"], "alpha": ["t"], "beta": ["t"]}, {"zeta::REQ-001": ["zeta::REQ-001", "zeta::REQ-002"]}


def refines_target_shape():
    """ルートの`REQ-001`が`REQ-002`を`requires`し、`alpha`の`TECH-001`（規範文`C-01`）が`REQ-001:AC-01`を具体化する。
    `REQ-001`は`alpha::TECH-001`の`refines`の参照先で、その`requires`は辿らない。"""
    documents = {
        ("zeta", "REQ-001"): dict(title="認証の基準", statements=[("AC-01", "秘密情報を出力しない")], requires=["REQ-002"],
                                  tests=[("tests/p.py", ["REQ-001:AC-01"], "p")]),
        ("zeta", "REQ-002"): dict(title="前提の基準", statements=[("AC-01", "入力を検証する")]),
        ("alpha", "TECH-001"): dict(title="AC-01の実装方針", statements=[("C-01", "画面に利用者のIDを表示しない")], refines=["zeta::REQ-001:AC-01"],
                                    tests=[("tests/t.py", ["TECH-001:C-01"], "t")]),
    }
    return documents, {"zeta": ["p"], "alpha": ["t"]}, {"alpha::TECH-001": ["alpha::TECH-001", "zeta::REQ-001"]}


# id: 説明、操作の引数、ルートのID、カタログの宣言の順のメンバー、構成。`target`は単独の操作の起点（修飾ID）、`None`は全体の操作。
CASES = {
    "MULTI-059-01": dict(argv=["verify", "--all-workspaces"], root="zeta", members=["beta", "alpha"], shape=sibling_shape, target=None,
                         description="全体のverifyで、メンバーの文書を起点にした閉包は、同じREQを具体化する別のメンバーの文書を含めない"),
    "MULTI-059-02": dict(argv=["verify", "REQ-001"], root="zeta", members=["beta", "alpha"], shape=requires_target_shape, target="zeta::REQ-001",
                         description="verifyの閉包は、requiresで到達した文書を具体化する別のワークスペースの文書とそのコマンドを含めない"),
    "MULTI-059-03": dict(argv=["verify", "--workspace", "alpha", "alpha::TECH-001"], root="zeta", members=["alpha"], shape=refines_target_shape,
                         target="alpha::TECH-001",
                         description="verifyの閉包は、起点がrefinesする文書のrequiresを辿らず、その参照先の文書を含めない"),
}


def is_all(identifier):
    return CASES[identifier]["target"] is None


def workspace_ids(identifier):
    case = CASES[identifier]
    return [case["root"], *sorted(case["members"])]


# --- レビュー済みの期待値（リテラル。参照計算の結果と一致することを要求する） ------------------------------
#
# 検証対象ごとの(対象規範文, bindingRefs)と、テスト割当て（`<ワークスペース>::<コマンド名>`）ごとの(テストのパス, covers)。
# 実行の順は、ルートを先頭、その後はワークスペースIDの辞書順、同じワークスペースの中はコマンド名の辞書順。
EXPECTED = {
    "MULTI-059-01": (
        ["zeta::p", "alpha::t", "beta::t"],
        {"zeta::p": (["tests/p.py"], ["zeta::REQ-001:AC-01", "zeta::REQ-001:AC-02"]),
         "alpha::t": (["tests/t.py"], ["zeta::REQ-001:AC-01"]),
         "beta::t": (["tests/t.py"], ["zeta::REQ-001:AC-02"])},
        {"zeta::REQ-001": (["zeta::REQ-001:AC-01", "zeta::REQ-001:AC-02"], ["alpha::t", "beta::t", "zeta::p"]),
         "alpha::TECH-001": ([], ["alpha::t"]),
         "beta::TECH-001": ([], ["beta::t"])}),
    "MULTI-059-02": (
        ["zeta::p"],
        {"zeta::p": (["tests/p.py"], ["zeta::REQ-001:AC-01"])},
        {"zeta::REQ-001": (["zeta::REQ-001:AC-01"], ["zeta::p"])}),
    "MULTI-059-03": (
        ["alpha::t"],
        {"alpha::t": (["tests/t.py"], ["alpha::TECH-001:C-01"])},
        {"alpha::TECH-001": (["alpha::TECH-001:C-01"], ["alpha::t"])}),
}


def literal_order(identifier):
    return EXPECTED[identifier][0]


def expected_targets(identifier):
    return EXPECTED[identifier][2]


def literal_closure(identifier, target):
    return CASES[identifier]["shape"]()[2][target]


def defective_closure(documents, target):
    """修正前の参照計算Bの閉包の再現（欠陥の再現。期待値の根拠にしない）: 到達したすべての文書から逆参照と`requires`、`refines`をたどる。"""
    reached, frontier = {target}, [target]
    while frontier:
        current = frontier.pop(0)
        edges = multi_crosscheck.relations(documents[current])
        found = {owner for key in ("requires", "refines") for reference in edges[key] if (owner := multi_crosscheck.owner(reference)) in documents}
        statements = {f"{documents[current]['workspaceId']}::{statement['id']}" for statement in multi_crosscheck.read_statements(documents[current]["body"])}
        mine = {current, *statements}
        found |= {name for name, document in documents.items() if set(multi_crosscheck.relations(document)["refines"]) & mine}
        for name in sorted(found - reached):
            reached.add(name)
            frontier.append(name)
    return sorted(reached)


# --- 入力 -------------------------------------------------------------------------------

def render(local, spec):
    """文書の(ファイルの全文, 正規化した本文)。"""
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: approved\n"
    relations = ""
    for key in ("requires", "refines"):
        if spec.get(key):
            relations += f"  {key}: [{', '.join(spec[key])}]\n"
    if relations:
        head += "relations:\n" + relations
    if spec.get("tests"):
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: {command}\n"
                                     for path, covers, command in spec["tests"])
    lines = "".join(f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n" for label, text in spec.get("statements", []))
    body = f"# {local} {spec['title']}\n\n"
    if kind_of(local) == "requirement":
        body += f"## Intent\n\n{spec['title']}の規範を定める。\n\n## Acceptance Criteria\n\n{lines}\n## Verification\n\nそれぞれのtestで確認する。\n"
    elif lines:
        body += f"## Context\n\n{spec['title']}を定める。\n\n## Constraints\n\n{lines}"
    else:
        body += f"## Context\n\n{spec['title']}を定める。\n"
    return head + "---\n\n" + body, body


def command_block(names):
    argv = ", ".join(f'"{part}"' for part in ARGV)
    return "verify:\n  commands:\n" + "".join(f"    {name}:\n      argv: [{argv}]\n      cwd: .\n" for name in names)


def reviewed_inputs(identifier):
    case = CASES[identifier]
    root = case["root"]
    documents, commands, _ = case["shape"]()
    files = {}
    members = [(member, workspace_path(root, member)) for member in case["members"]]
    for workspace in [root, *case["members"]]:
        base = "" if workspace == root else workspace_path(root, workspace) + "/"
        config = multi_reference.root_config(members, root) if workspace == root else multi_reference.plain_config(workspace)
        files[f"{base}.spec/bitz.yaml"] = config + (command_block(commands[workspace]) if workspace in commands else "")
    for (workspace, local), spec in documents.items():
        base = "" if workspace == root else workspace_path(root, workspace) + "/"
        files[f"{base}.spec/{KIND_DIRECTORY[kind_of(local)]}/{local}.md"] = render(local, spec)[0]
        for path, _, _ in spec.get("tests", []):
            files[f"{base}{path}"] = TEST_BYTES.decode()
    return {name: text.encode() for name, text in files.items()}


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier, "description": CASES[identifier]["description"],
        # `verify`はテスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をコミットする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*CASES[identifier]["argv"], "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_effects(state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _material(workspace, local, spec):
    """文書1件のハッシュ値の材料。関係の参照先と`covers`は修飾IDにそろえ、辞書順に置く（正規化仕様 §3）。"""
    def qualified(value):
        return value if "::" in value else f"{workspace}::{value}"

    name = f"{workspace}::{local}"
    relations = {key: sorted(qualified(value) for value in spec[key]) for key in ("requires", "refines") if spec.get(key)}
    statements = sorted((verify_fixtures.statement_material(f"{name}:{label}", text) for label, text in spec.get("statements", [])),
                        key=lambda item: item["id"])
    document = verify_fixtures.document_material(None, name, workspace, kind_of(local), spec["title"], render(local, spec)[1],
                                                 relations=relations, statements=statements)
    document["frontmatter"]["tests"] = sorted(
        ({"path": path, "covers": sorted(qualified(value) for value in covers), "command": command} for path, covers, command in spec.get("tests", [])),
        key=lambda item: (item["path"], item["covers"]))
    return document


def reviewed_digest_input(identifier, target):
    """検証対象`target`の、目的`verify`のハッシュ値の材料。閉包の文書をリテラルで列挙する。"""
    case = CASES[identifier]
    root = case["root"]
    documents, _, closure = case["shape"]()
    included = {(workspace, local): spec for (workspace, local), spec in documents.items() if f"{workspace}::{local}" in closure[target]}
    reached = sorted({workspace for workspace, _ in included})
    request = target.partition("::")[0]
    workspaces = [request, *sorted(set(reached) - {request})]
    used = {workspace: sorted({command for (owner, _), spec in included.items() if owner == workspace for _, _, command in spec.get("tests", [])})
            for workspace in reached}
    # 横断のエッジは、閉包の文書が宣言する強い関係のうち、参照先が別のワークスペースの文書であるもの（宣言は修飾IDで書く）。
    edges = sorted((f"{workspace}::{local}", relation, reference) for (workspace, local), spec in included.items()
                   for relation in ("requires", "refines") for reference in spec.get(relation, [])
                   if "::" in reference and reference.partition("::")[0] != workspace)
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": request, "roots": [target],
        "workspaces": [{"id": workspace, "path": workspace_path(root, workspace)} for workspace in workspaces],
        "documents": sorted((_material(workspace, local, spec) for (workspace, local), spec in included.items()), key=lambda item: item["id"]),
        "crossWorkspaceEdges": [{"relation": relation, "source": source, "target": reference} for source, relation, reference in edges],
        "settings": {
            "workspaces": [{"id": workspace, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"} for workspace in reached],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": workspace, "timeoutSeconds": 300} for workspace in reached if used[workspace]],
            "commands": [{"workspaceId": workspace, "name": name, "argv": list(ARGV), "cwd": "."} for workspace in reached for name in used[workspace]],
        },
    }


def expected_digest(identifier, target):
    return multi_reference.digest(multi_reference.canonical_bytes(reviewed_digest_input(identifier, target)))


# --- レビュー済みの期待結果 ---------------------------------------------------------------

def command_entry(identifier, binding):
    workspace, name = binding.split("::")
    tests, covers = EXPECTED[identifier][1][binding]
    return {
        "bindingId": binding, "workspaceId": workspace, "name": name, "status": "passed", "termination": "exit", "cwd": ".",
        "argv": ["/bin/true", *tests], "tests": list(tests), "covers": list(covers),
        "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
        "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def target_entry(identifier, target):
    statements, refs = expected_targets(identifier)[target]
    return {"target": target, "status": "passed", "contextDigest": expected_digest(identifier, target),
            "statements": list(statements), "bindingRefs": list(refs), "diagnostics": []}


def reviewed_result(identifier):
    case = CASES[identifier]
    revision = {"commit": COMMIT, "dirty": False}
    bindings = literal_order(identifier)
    if not is_all(identifier):
        workspace = case["target"].partition("::")[0]
        return {"schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
                "workspace": {"id": workspace, "path": workspace_path(case["root"], workspace)},
                "targetResults": [target_entry(identifier, case["target"])], "revision": revision,
                "commands": [command_entry(identifier, binding) for binding in bindings], "durationMs": 0, "diagnostics": []}
    entries = []
    for workspace in workspace_ids(identifier):
        targets = sorted(target for target in expected_targets(identifier) if target.partition("::")[0] == workspace)
        entries.append({
            "id": workspace, "path": workspace_path(case["root"], workspace), "status": "passed",
            "targetResults": [target_entry(identifier, target) for target in targets],
            "commands": [command_entry(identifier, binding) for binding in bindings if binding.partition("::")[0] == workspace],
            "durationMs": 0, "diagnostics": []})
    return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "passed",
            "multiWorkspace": {"id": case["root"], "path": "."}, "workspaces": entries, "revision": revision,
            "durationMs": 0, "diagnostics": []}


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def check_conditions(identifier, repository, result):
    """原因の構成と期待結果を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = alias.load_tree(repository)
    if single or root_id != case["root"] or sorted(workspaces) != sorted(workspace_ids(identifier)):
        raise ValueError("ワークスペースの構成が入力と異なります")
    if [member for member, _ in multi_crosscheck.catalog(repository)[1]] != case["members"]:
        raise ValueError("カタログのメンバーの宣言の順がレビュー済みの入力と異なります")
    targets = sorted(documents) if case["target"] is None else [case["target"]]
    if sorted(expected_targets(identifier)) != targets:
        raise ValueError("検証対象が入力からの参照計算と異なります")
    per_target, bindings = reference_plan(documents, targets)
    if reference_order(root_id, bindings) != literal_order(identifier):
        raise ValueError("期待する実行の順が入力からの参照計算と異なります")
    if {target: (statements, refs) for target, (statements, refs) in per_target.items()} != {
            target: (list(statements), list(refs)) for target, (statements, refs) in expected_targets(identifier).items()}:
        raise ValueError("検証対象の規範文またはbindingRefsが入力からの参照計算と異なります")
    if bindings != {binding: (list(tests), list(covers)) for binding, (tests, covers) in EXPECTED[identifier][1].items()}:
        raise ValueError("テストのパスまたはcoversが入力からの参照計算と異なります")
    # 閉包: リテラルと参照計算Bが一致し、修正前の広い閉包とは、欠陥の入力のある検証対象で異なる。
    wide = 0
    for target in targets:
        selected, _ = multi_crosscheck.closure(documents, target)
        if selected != literal_closure(identifier, target):
            raise ValueError(f"{target}の閉包がレビュー済みの閉包と異なります")
        wide += defective_closure(documents, target) != selected
    if not wide:
        raise ValueError("この入力は、修正前の広い閉包を検出できません")
    if result["status"] != "passed":
        raise ValueError("この入力は診断を持たない通過の結果になります")


def check_digests(identifier, repository, result):
    entries = [target for entry in result.get("workspaces", []) for target in entry["targetResults"]] + list(result.get("targetResults", []))
    loaded = multi_crosscheck.load_workspaces(repository)
    for entry in entries:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, entry["target"], loaded=loaded))
        if multi_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{entry['target']}のハッシュ値が参照計算Bと一致しません")
        if multi_reference.canonical_bytes(reviewed_digest_input(identifier, entry["target"])) != derived:
            raise ValueError(f"{entry['target']}のハッシュ値の参照計算AとBが一致しません")
    return len(entries)


# --- 書き出しと監査 ---------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-closure-origin-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(state)))


def actual_entries(fixture):
    files = {}
    for path in sorted((fixture / "repo").rglob("*")):
        relative = path.relative_to(fixture / "repo").as_posix()
        if path.is_symlink():
            raise ValueError(f"{relative}はシンボリックリンクであってはいけません")
        if path.is_file():
            if path.stat().st_mode & 0o111:
                raise ValueError(f"{relative}は実行ビットを持ってはいけません")
            files[relative] = path.read_bytes()
    return files


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
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            if actual_entries(fixture) != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {"expected/verify.json"}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-closure-origin-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_conditions(identifier, repository, result)
                    check_digests(identifier, repository, result)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
