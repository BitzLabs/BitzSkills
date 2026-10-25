"""`verify`の`targetResults[].statements`の並びを、出力する規範文IDの重複なし辞書順に固定する（Coreの公開操作は実行しない）。

実装の確認事項C52とADR-051の追加に対応する。`verify`は`targetResults[].statements`を、対象規範文の内部の並び
（起点の規範文を文書順・行番号で並べ、その後に具体化文書の規範文を足した順）のまま出力していた。そのため、次の入力で辞書順にならなかった。

- 文書の中で、規範文を番号の順に書かないとき（`AC-10`を`AC-02`より前に書く）。
- 起点より辞書順で前の文書が起点を具体化するとき（`TECH-003`が`TECH-005`を具体化する）。
- 複合ワークスペースで、他のメンバーの文書が起点を具体化するとき（`api::TECH-010:C-01`が`platform::REQ-001:AC-01`より前）。

この群は、並びが出力と同じ規範文ID（複合ワークスペースでは修飾ID）の重複なし辞書順になることを3件で固定し、対照を1件置く。

同じ入力（規範文を番号の順に書かない文書）は、`context`のハッシュ値の材料でも欠陥を踏んだ（実装の確認事項C60）。Coreは材料の`documents[].statements`を
文書に書いた順のまま入れていたが、規範は`id`のコードポイント辞書順を求める（ハッシュ値の正規化仕様 §3の表）。`MULTI-044-05`がこれを固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-044-01` | `verify REQ-001`、`.`（単一） | 1つの文書で`AC-10`、`AC-02`の順に書く。`statements`は`["REQ-001:AC-02", "REQ-001:AC-10"]` |
| `MULTI-044-02` | `verify TECH-005`、`.`（単一） | `TECH-003`が`TECH-005:C-01`を`refines`する。`statements`は`["TECH-003:C-01", "TECH-005:C-01"]` |
| `MULTI-044-03` | `verify REQ-001`、`.`（複合。ルート`platform`、メンバー`api`） | `api`の`TECH-010`が`platform::REQ-001:AC-01`を`refines`する。`statements`は`["api::TECH-010:C-01", "platform::REQ-001:AC-01"]` |
| `MULTI-044-04` | `verify REQ-001`、`.`（単一） | 対照: 最初から辞書順の入力（`AC-01`、`AC-02`の順、`TECH-010`が`REQ-001:AC-01`を具体化）。修正の前後で同じ |
| `MULTI-044-05` | `context REQ-001 --purpose interpret --detail compact`、`.`（単一） | `MULTI-044-01`と同じ入力。`contextDigest`は、材料の規範文を`id`の辞書順（`AC-02`、`AC-10`）に置いた値（C60） |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- `verify` §8の`targetResults[]`の表: `statements`は「検証対象が検証する規範文。重複なし辞書順」。複合ワークスペースでは検証対象、規範文、`covers`のIDを修飾IDで返す。
- 複合ワークスペース仕様 §4・§6: 各文書ID、規範文IDは修飾IDで出力する。辞書順の比較の対象は、出力するID（修飾ID）である。
- 関係・トレースモデル §6.4: 検証対象が文書なら、その文書が所有するすべての規範文と、具体化文書の規範文が対象規範文である。
- `verify` §3・§4: 全`MUST`に1件以上のテスト対応を要求し、通過した検証対象のテスト割当てを`<ワークスペースID>::<コマンド名>`ごとにまとめて1回実行する。
  テストのパスは所有ワークスペース相対で重複排除して辞書順に並べる。
- コンテキストのハッシュ値の正規化仕様 §3: 提示の順は材料に含めない。材料の`documents[].statements`は`id`のコードポイント辞書順に置く。
  `statements`の並びの修正（C52）では`contextDigest`は変わらない。規範文を番号の順に書かない文書（`01`）では、材料の規範文の並びの修正（C60）で変わる。
  ハッシュ値は、独立に書いた2系統の参照計算（このモジュールのリテラルA、入力の木構造から導出するB）のバイト列の一致を要求する。

参照計算`reference_*`は、入力の木構造から、閉包、対象規範文、テスト割当てを導く（`multi_closure_alias_fixtures`の閉包と
`multi_context_order_fixtures`の対象規範文の参照計算を再利用する）。さらに、修正前の並び（対象規範文の内部の並び）を導き、欠陥を持つ3件では
期待する並びと異なること（この入力が欠陥を検出できること）、対照では同じであることを要求する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (digest_crosscheck, digest_reference, multi_closure_alias_fixtures as alias, multi_context_order_fixtures as order,
               multi_crosscheck, multi_reference, multi_verify_fixtures as verify_fixtures)
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
TEST_BYTES = alias.TEST_BYTES
WORKSPACE_PATHS = {"platform": ".", "api": "services/api", "root": "."}
COMMANDS = {"platform": "platform", "api": "backend", "root": "default"}
KIND_DIRECTORY = order.KIND_DIRECTORY
MEMBERS = [("api", "services/api")]
EXPECTED_WORKSPACES = {"MULTI-044-03": [("platform", "."), ("api", "services/api")]}

# --- 入力の表（宣言どおりの表記で書く） ---------------------------------------------------------------
#
# (ワークスペース, ローカルID): dict(title, refines=宣言した参照, statements=[(ラベル, 文)]（文書に書く順）, tests=[(パス, covers（宣言どおり）)])。
# 規範文は、REQでは`Acceptance Criteria`、TECHでは`Constraints`に、書く順のまま置く。テスト対応のコマンドはワークスペースごとに1つである。
DOCUMENTS = {
    # 1つの文書の中で、`AC-10`を`AC-02`より前に書く。
    "MULTI-044-01": {
        ("root", "REQ-001"): dict(title="認証の基準", statements=[("AC-10", "秘密情報を出力しない"), ("AC-02", "入力を検証する")],
                                  tests=[("tests/test_req_001.py", ["REQ-001:AC-02", "REQ-001:AC-10"])]),
    },
    # 起点`TECH-005`より辞書順で前の`TECH-003`が起点の規範文を具体化する。
    "MULTI-044-02": {
        ("root", "TECH-005"): dict(title="起点の技術仕様", statements=[("C-01", "入力を検証する")],
                                   tests=[("tests/test_tech_005.py", ["TECH-005:C-01"])]),
        ("root", "TECH-003"): dict(title="起点を具体化する技術仕様", refines=["TECH-005:C-01"], statements=[("C-01", "結果を記録する")],
                                   tests=[("tests/test_tech_003.py", ["TECH-003:C-01"])]),
    },
    # `api`の文書が、ルート`platform`の起点の規範文を具体化する。起点にはテスト対応がなく、`api`のテストが両方の規範文を`covers`する。
    "MULTI-044-03": {
        ("platform", "REQ-001"): dict(title="認証の基準", statements=[("AC-01", "秘密情報を出力しない")]),
        ("api", "TECH-010"): dict(title="API側の具体化", refines=["platform::REQ-001:AC-01"], statements=[("C-01", "応答形式を固定する")],
                                  tests=[("tests/test_tech_010.py", ["api::TECH-010:C-01", "platform::REQ-001:AC-01"])]),
    },
    # 対照: 規範文を番号の順に書き、具体化文書の規範文のIDは起点の規範文のIDより後ろにある。
    "MULTI-044-04": {
        ("root", "REQ-001"): dict(title="認証の基準", statements=[("AC-01", "秘密情報を出力しない"), ("AC-02", "入力を検証する")],
                                  tests=[("tests/test_req_001.py", ["REQ-001:AC-01", "REQ-001:AC-02"])]),
        ("root", "TECH-010"): dict(title="起点を具体化する技術仕様", refines=["REQ-001:AC-01"], statements=[("C-01", "結果を記録する")],
                                   tests=[("tests/test_tech_010.py", ["TECH-010:C-01"])]),
    },
}
# `context`のハッシュ値の材料の規範文の並び（C60）は、`MULTI-044-01`と同じ入力で固定する。
DOCUMENTS["MULTI-044-05"] = DOCUMENTS["MULTI-044-01"]

# id: 操作、説明、単一か、起点の引数、結果の`target`（`context`では`roots`の値）。
CASES = {
    "MULTI-044-01": dict(operation="verify", single=True, argument="REQ-001", target="REQ-001",
                         description="verifyの規範文は、1つの文書で番号の順に書かない規範文を出力するIDの辞書順に並べる"),
    "MULTI-044-02": dict(operation="verify", single=True, argument="TECH-005", target="TECH-005",
                         description="verifyの規範文は、起点より辞書順で前の文書が起点を具体化するとき、出力するIDの辞書順に並べる"),
    "MULTI-044-03": dict(operation="verify", single=False, argument="REQ-001", target="platform::REQ-001",
                         description="複合ワークスペースのverifyの規範文は、他のメンバーの具体化文書の規範文を含めて修飾IDの辞書順に並べる"),
    "MULTI-044-04": dict(operation="verify", single=True, argument="REQ-001", target="REQ-001",
                         description="最初から辞書順の入力のverifyの規範文は、並びの修正の前後で同じ順に出力する"),
    "MULTI-044-05": dict(operation="context", single=True, argument="REQ-001", target="REQ-001",
                         description="contextのハッシュ値の材料は、規範文を番号の順に書かない文書でも、規範文をidの辞書順に置く"),
}

# --- レビュー済みの期待値（リテラル。参照計算の結果と一致することを要求する） ------------------------------
#
# 規範文: 出力するID（複合ワークスペースでは修飾ID）の重複なし辞書順。
EXPECTED_STATEMENTS = {
    "MULTI-044-01": ["REQ-001:AC-02", "REQ-001:AC-10"],
    "MULTI-044-05": ["REQ-001:AC-02", "REQ-001:AC-10"],
    "MULTI-044-02": ["TECH-003:C-01", "TECH-005:C-01"],
    "MULTI-044-03": ["api::TECH-010:C-01", "platform::REQ-001:AC-01"],
    "MULTI-044-04": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-010:C-01"],
}
# 修正前の並び（対象規範文の内部の並び: 起点の規範文を文書順・行番号で並べ、その後に具体化文書の規範文を足す）。期待値の根拠にしない。
DEFECTIVE_STATEMENTS = {
    "MULTI-044-01": ["REQ-001:AC-10", "REQ-001:AC-02"],
    "MULTI-044-05": ["REQ-001:AC-10", "REQ-001:AC-02"],
    "MULTI-044-02": ["TECH-005:C-01", "TECH-003:C-01"],
    "MULTI-044-03": ["platform::REQ-001:AC-01", "api::TECH-010:C-01"],
    "MULTI-044-04": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-010:C-01"],
}
# 閉包の文書（ハッシュ値の材料は修飾IDの順に置く）。
EXPECTED_CLOSURE = {
    "MULTI-044-01": ["REQ-001"],
    "MULTI-044-05": ["REQ-001"],
    "MULTI-044-02": ["TECH-003", "TECH-005"],
    "MULTI-044-03": ["api::TECH-010", "platform::REQ-001"],
    "MULTI-044-04": ["REQ-001", "TECH-010"],
}
# テスト割当て: (所有ワークスペース, コマンド名, テストのパス（所有ワークスペース相対、辞書順）, `covers`（対象規範文のうちテスト対応が宣言したもの、辞書順）)。
EXPECTED_BINDINGS = {
    "MULTI-044-01": [("root", "default", ["tests/test_req_001.py"], ["REQ-001:AC-02", "REQ-001:AC-10"])],
    "MULTI-044-02": [("root", "default", ["tests/test_tech_003.py", "tests/test_tech_005.py"], ["TECH-003:C-01", "TECH-005:C-01"])],
    "MULTI-044-03": [("api", "backend", ["tests/test_tech_010.py"], ["api::TECH-010:C-01", "platform::REQ-001:AC-01"])],
    "MULTI-044-04": [("root", "default", ["tests/test_req_001.py", "tests/test_tech_010.py"],
                      ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-010:C-01"])],
}
# 境界を越えるエッジ（`source`、`relation`、`target`の辞書順）。
EXPECTED_CROSS_EDGES = {"MULTI-044-03": [("api::TECH-010", "refines", "platform::REQ-001:AC-01")]}


def documents_of(identifier):
    return DOCUMENTS[identifier]


def kind_of(local):
    return {"REQ": "requirement", "TECH": "technical", "TASK": "task"}[local.partition("-")[0]]


def prefix_of(identifier, workspace):
    return "" if CASES[identifier]["single"] else f"{workspace}::"


# --- 入力 -------------------------------------------------------------------------------

def render(identifier, workspace, local, spec):
    """文書の(ファイルの全文, 正規化した本文)。"""
    kind = kind_of(local)
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: approved\n"
    if spec.get("refines"):
        head += f"relations:\n  refines: [{', '.join(spec['refines'])}]\n"
    if spec.get("tests"):
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: {COMMANDS[workspace]}\n"
                                     for path, covers in spec["tests"])
    lines = "".join(f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n" for label, text in spec["statements"])
    body = f"# {local} {spec['title']}\n\n"
    if kind == "requirement":
        body += f"## Intent\n\n{spec['title']}の規範を定める。\n\n## Acceptance Criteria\n\n{lines}\n## Verification\n\nそれぞれのtestで確認する。\n"
    else:
        body += f"## Context\n\n{spec['title']}を定める。\n\n## Constraints\n\n{lines}"
    return head + "---\n\n" + body, body


def corpus_files(identifier):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    single = CASES[identifier]["single"]
    files = {}
    if single:
        files[".spec/bitz.yaml"] = multi_reference.member_config("root", COMMANDS["root"])
    else:
        # ルート`platform`はテスト対応を持たないので、コマンドを定義しない（カタログの設定だけ）。
        files[".spec/bitz.yaml"] = multi_reference.root_config(MEMBERS)
        files["services/api/.spec/bitz.yaml"] = multi_reference.member_config("api", COMMANDS["api"])
    for (workspace, local), spec in documents_of(identifier).items():
        base = "" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace] + "/"
        files[f"{base}.spec/{KIND_DIRECTORY[kind_of(local)]}/{local}.md"] = render(identifier, workspace, local, spec)[0]
        for path, _ in spec.get("tests", []):
            files[f"{base}{path}"] = TEST_BYTES.decode()
    return files


def reviewed_inputs(identifier):
    return {name: text.encode() for name, text in corpus_files(identifier).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    argv = (["verify", case["argument"], "--format", "json"] if case["operation"] == "verify" else
            ["context", case["argument"], "--purpose", "interpret", "--detail", "compact", "--format", "json"])
    return {
        "fixtureId": identifier,
        "description": case["description"],
        # `verify`はテスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をコミットする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json", "resultFile": f"expected/{case['operation']}.json", "reportFileCount": 0},
    }


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _qualified(single, workspace, reference):
    return reference if single or "::" in reference else f"{workspace}::{reference}"


def _material(identifier, workspace, local, spec):
    """文書1件のハッシュ値の材料（参照計算A）。関係の参照先と`covers`は修飾IDにそろえ、辞書順に置く（正規化仕様 §3）。"""
    single = CASES[identifier]["single"]
    name = local if single else f"{workspace}::{local}"
    relations = {"refines": sorted(_qualified(single, workspace, value) for value in spec["refines"])} if spec.get("refines") else {}
    statements = sorted((verify_fixtures.statement_material(f"{name}:{label}", text) for label, text in spec["statements"]),
                        key=lambda item: item["id"])
    document = verify_fixtures.document_material(None, name, workspace, kind_of(local), spec["title"], render(identifier, workspace, local, spec)[1],
                                                 relations=relations, statements=statements)
    document["frontmatter"]["tests"] = sorted(
        ({"path": path, "covers": sorted(_qualified(single, workspace, value) for value in covers), "command": COMMANDS[workspace]}
         for path, covers in spec.get("tests", [])), key=lambda item: (item["path"], item["covers"]))
    return document


def _spec_of(identifier, name):
    """閉包の文書の名前（単一ワークスペースでは修飾しない）に対する表の項目(ワークスペース, ローカルID, spec)。"""
    single = CASES[identifier]["single"]
    workspace, _, local = name.rpartition("::") if not single else ("root", "", name)
    return workspace, local, documents_of(identifier)[(workspace, local)]


def reviewed_digest_input(identifier):
    case = CASES[identifier]
    single = case["single"]
    documents = [_material(identifier, *_spec_of(identifier, name)) for name in EXPECTED_CLOSURE[identifier]]
    workspaces = [("root", ".")] if single else EXPECTED_WORKSPACES[identifier]
    # 目的`interpret`は、コマンドとタイムアウトを材料に含めない（正規化仕様 §3）。
    bindings = EXPECTED_BINDINGS[identifier] if case["operation"] == "verify" else []
    owners = sorted({workspace for workspace, *_ in bindings})
    request = workspaces[0][0]
    edges = [{"relation": relation, "source": source, "target": target}
             for source, relation, target in EXPECTED_CROSS_EDGES.get(identifier, [])]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify" if case["operation"] == "verify" else "interpret", "requestWorkspaceId": request,
        "roots": [case["target"]],
        "workspaces": [{"id": workspace_id, "path": path} for workspace_id, path in workspaces],
        "documents": sorted(documents, key=lambda item: item["id"]),
        "crossWorkspaceEdges": edges,
        "settings": {
            "workspaces": [{"id": workspace_id, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}
                           for workspace_id, _ in sorted(workspaces)],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": workspace, "timeoutSeconds": 300} for workspace in owners],
            "commands": [{"workspaceId": workspace, "name": name, "argv": ["/bin/true", "{tests}"], "cwd": "."}
                         for workspace, name, _, _ in sorted(bindings)],
        },
    }


def reference_digest(identifier, repository):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    case = CASES[identifier]
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier))
    if case["single"]:
        derived = digest_crosscheck.canonical_bytes(
            digest_crosscheck.build(repository, case["argument"], "verify" if case["operation"] == "verify" else "interpret", workspace_id="root"))
    else:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, case["target"], "verify"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


def expected_digest(identifier):
    """生成と監査が使う、リテラルの参照計算Aのハッシュ値。"""
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


# --- 期待結果 ---------------------------------------------------------------------------------

def passed_verify_result(identifier, context_digest):
    case = CASES[identifier]
    single = case["single"]
    bindings = EXPECTED_BINDINGS[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."} if single else {"id": "platform", "path": "."},
        "targetResults": [{
            "target": case["target"], "status": "passed", "contextDigest": context_digest,
            "statements": list(EXPECTED_STATEMENTS[identifier]),
            "bindingRefs": sorted(f"{workspace}::{name}" for workspace, name, _, _ in bindings),
            "diagnostics": [],
        }],
        "revision": {"commit": COMMIT, "dirty": False},
        "commands": [verify_fixtures.command_result(workspace, name, "/bin/true", tests, covers) for workspace, name, tests, covers in bindings],
        "durationMs": 0, "diagnostics": [],
    }


def passed_context_result(identifier, context_digest):
    """`MULTI-044-05`: 単一ワークスペースの`context REQ-001 --purpose interpret --detail compact`。起点の文書だけを含み、制約台帳とカバレッジは空である。"""
    names = EXPECTED_CLOSURE[identifier]
    documents = [alias.bundle_document(name, None, kind_of(name), "root", f".spec/{KIND_DIRECTORY[kind_of(name)]}/{name}.md", ["root"], "reference")
                 for name in names]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "interpret",
        "workspace": {"id": "root", "path": "."}, "roots": [CASES[identifier]["target"]], "contextDigest": context_digest,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": True, "documentCount": len(names), "unresolvedStrongRelations": 0},
        "projection": {"detail": "compact", "expanded": []},
        "documents": documents, "constraintLedger": {"statements": []},
        "coverage": {"must": dict(alias.EMPTY_BUCKET), "should": dict(alias.EMPTY_BUCKET), "may": dict(alias.EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier):
    if CASES[identifier]["operation"] == "context":
        return passed_context_result(identifier, expected_digest(identifier))
    return passed_verify_result(identifier, expected_digest(identifier))


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def reference_statements(documents, root, order_of_documents=None):
    """対象規範文（起点の文書が所有する規範文と、具体化文書の規範文。関係・トレースモデル §6.4の1.）を、内部の並びで導く。

    `order_of_documents`は文書の並び。省略すると関係・トレースモデル §7の6.の並び（修正前の並びの再現には`order.defective_order`を渡す）。
    """
    ordered, edges, _ = order.reference_order(documents, root, "interpret")
    return order.reference_targets(documents, order_of_documents if order_of_documents is not None else ordered, edges, root), ordered


def reference_bindings(documents, ordered, targets):
    """通過した検証対象が要求するテスト割当て（`verify` §4の4.〜5.）。全`MUST`にテスト対応があることを要求する。

    2つ以上のワークスペースのテスト割当てを受け取ったら止める。単独の操作が複数のワークスペースのテスト割当てを実行するときの`commands[]`の並びは、
    規範から導けない（確認事項C62）ので、この群は固定しない。
    """
    wanted = set(targets)
    grouped = {}
    for name in ordered:
        document = documents[name]
        workspace = document["workspaceId"]
        for entry in document["frontmatter"].get("tests", []):
            covers = {multi_crosscheck.qualify(workspace, text) for text in entry["covers"]}
            if not covers & wanted:
                continue
            command = entry.get("command") or document["frontmatter"].get("verify")
            slot = grouped.setdefault((workspace, command), {"tests": set(), "covers": set()})
            slot["tests"].add(entry["path"])
            slot["covers"] |= covers & wanted
    if set().union(*(slot["covers"] for slot in grouped.values())) != wanted:
        raise ValueError("対象のすべての`MUST`にテスト対応がある必要があります")
    if len({workspace for workspace, _ in grouped}) > 1:
        raise ValueError("複数のワークスペースのテスト割当ての`commands[]`の並びは規範から導けないため、この群は扱いません（確認事項C62）")
    # 1つのワークスペースの中は、コマンド名の辞書順（`verify` §4の6.）。
    keys = sorted(grouped, key=lambda key: (key[0], key[1]))
    return [(workspace, command, sorted(grouped[(workspace, command)]["tests"]), sorted(grouped[(workspace, command)]["covers"]))
            for workspace, command in keys]


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた対象規範文・テスト割当て・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = alias.load_tree(repository)
    if single != case["single"]:
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    root = f"{root_id}::{case['argument']}"

    def shown(name):
        return alias.unqualified(name) if single else name

    targets, ordered = reference_statements(documents, root)
    if case["operation"] == "context":
        # `context`は閉包の文書だけを確かめ、ハッシュ値の材料の規範文を`id`の辞書順に置く参照計算A・Bのバイト列の一致を要求する（C60）。
        if [shown(name) for name in ordered] != EXPECTED_CLOSURE[identifier] or [item["id"] for item in result["documents"]] != EXPECTED_CLOSURE[identifier]:
            raise ValueError("文書が入力からの参照計算と異なります")
        if result["contextDigest"] != reference_digest(identifier, repository):
            raise ValueError("ハッシュ値が参照計算と異なります")
        return
    # 出力する規範文IDの重複なし辞書順。
    wanted = sorted({shown(item) for item in targets})
    if wanted != EXPECTED_STATEMENTS[identifier]:
        raise ValueError("期待する規範文の並びが入力からの参照計算と異なります")
    target = result["targetResults"]
    if len(target) != 1 or target[0]["target"] != case["target"] or target[0]["statements"] != wanted:
        raise ValueError("規範文が入力からの参照計算と異なります")
    bindings = reference_bindings(documents, ordered, targets)
    if [(workspace, command, tests, [shown(item) for item in covers]) for workspace, command, tests, covers in bindings] != EXPECTED_BINDINGS[identifier]:
        raise ValueError("期待するテスト割当てが入力からの参照計算と異なります")
    if target[0]["bindingRefs"] != sorted(f"{workspace}::{command}" for workspace, command, _, _ in bindings):
        raise ValueError("`bindingRefs`が入力からの参照計算と異なります")
    expected_commands = []
    for workspace, command, tests, covers in bindings:
        argv = [tests_part for part in workspaces[workspace]["config"]["verify"]["commands"][command]["argv"]
                for tests_part in (tests if part == "{tests}" else [part])]
        expected_commands.append(verify_fixtures.command_result(workspace, command, argv[0], tests, [shown(item) for item in covers]))
    if result["commands"] != expected_commands:
        raise ValueError("コマンドが入力からの参照計算と異なります")
    if result["status"] != "passed" or target[0]["status"] != "passed" or target[0]["diagnostics"] or result["diagnostics"]:
        raise ValueError("この入力は診断を持たない通過の結果になります")
    if target[0]["contextDigest"] != reference_digest(identifier, repository):
        raise ValueError("ハッシュ値が参照計算と異なります")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, root_id, _, documents = alias.load_tree(repository)
    root = f"{root_id}::{case['argument']}"
    targets, ordered = reference_statements(documents, root)
    _, edges, _ = order.reference_order(documents, root, "interpret")
    if alias.cyclic_edges(documents) or alias.reference_diagnostics(documents, ordered):
        raise ValueError("原因は規範文IDの比較だけである必要があります（循環・参照切れ・型違反がない）")
    for (workspace, _), spec in documents_of(identifier).items():
        base = repository / ("" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace])
        for path, _ in spec.get("tests", []):
            if (base / path).read_bytes() != TEST_BYTES:
                raise ValueError("テスト対応を持つ文書は、テストのファイルが存在する必要があります")

    def shown(name):
        return alias.unqualified(name) if single else name

    # 修正前の並び: 起点の規範文を文書順・行番号で並べ、その後に具体化文書の規範文を足した順（`reference_targets`の順）。
    old = [shown(item) for item in targets]
    if sorted(old) != EXPECTED_STATEMENTS[identifier] or len(set(old)) != len(old):
        raise ValueError("対象規範文の集合が、重複のない期待する規範文と一致する必要があります")
    if old != DEFECTIVE_STATEMENTS[identifier]:
        raise ValueError("修正前の並びがレビュー済みの並びと異なります")
    if identifier == "MULTI-044-04":
        # 対照: 最初から辞書順なので、修正前の並びと期待する並びが同じ。
        if old != EXPECTED_STATEMENTS[identifier]:
            raise ValueError("対照の入力は、修正前の並びが辞書順である必要があります")
        return
    # 欠陥を検出できる入力であること: 修正前の並びが辞書順と異なる。
    if old == EXPECTED_STATEMENTS[identifier]:
        raise ValueError("修正前の並びが辞書順と異なる必要があります")
    if identifier in {"MULTI-044-01", "MULTI-044-05"}:
        written = alias.statement_ids(documents, root)
        if written != sorted(written)[::-1] or len(written) != 2:
            raise ValueError("起点の文書に、番号の大きい規範文を先に書く必要があります")
    if identifier == "MULTI-044-02":
        if not (case["argument"] > "TECH-003" and edges[f"{root_id}::TECH-003"] and ordered == [root, f"{root_id}::TECH-003"]):
            raise ValueError("起点より辞書順で前の文書が起点を具体化する必要があります")
    if identifier == "MULTI-044-03":
        if documents["api::TECH-010"]["workspaceId"] == root_id or ordered != [root, "api::TECH-010"]:
            raise ValueError("他のメンバーの文書が起点を具体化する必要があります")


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / f"expected/{CASES[identifier]['operation']}.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-verify-order-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{CASES[identifier]['operation']}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key] for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-verify-order-") as temporary:
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
                    check_conditions(identifier, repository)
                    check_against_reference(identifier, repository, result)
                    for path in sorted(repository.rglob("*.md")):
                        if path.parent.parent.name == ".spec" and path.parent.name in alias.KIND_BY_DIRECTORY:
                            value, _ = digest_crosscheck.split_document(path.read_text(encoding="utf-8"))
                            Draft202012Validator({"$ref": "#/$defs/" + alias.FIXTURE_KINDS[
                                {"requirements": "requirement", "technical": "technical", "decisions": "decision",
                                 "tasks": "task"}[path.parent.name]], "$defs": frontmatter["$defs"]}).validate(value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
