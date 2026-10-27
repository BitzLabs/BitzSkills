"""複合ワークスペースの`context`の文書と規範文の並びを固定する（Coreの公開操作は実行しない）。

実装の確認事項C46とADR-051の追加に対応する。複合ワークスペースの`context`は、`documents`、`constraintLedger.statements`、`coverage`の各配列を、
起点ワークスペースの文書と規範文を修飾しない内部のID（`TECH-005`）のまま辞書順に比べていた。他のメンバーの文書は修飾したID（`api::TECH-010`）で
比べるので、同じ距離・同じ種別の文書が、出力のID（`api::TECH-010`、`platform::TECH-005`）の辞書順と食い違って並んだ（大文字の`T`が小文字の`a`より前）。
この群は、並びが出力と同じ修飾IDの辞書順になることを3件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-042-01` | `context platform::REQ-001 --purpose interpret --detail compact`、`.` | 起点を3つのワークスペースの文書が距離1と距離2で具体化する。`documents`は距離、種別、修飾IDの順（`api::TECH-010`が`platform::TECH-005`の前） |
| `MULTI-042-02` | `context platform::REQ-001 --purpose implement --detail compact`、`.` | 同じ入力。制約台帳と`coverage`の`total`・`addressed`・`tested`も修飾IDの順。TASKは同じ距離のTECHの後ろ |
| `MULTI-042-03` | `context REQ-001 --purpose implement --detail compact`、`.`（単一） | 対照: 単一ワークスペースの並びは変わらない（IDは修飾しない） |

基本のリポジトリは、ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）である。`platform`のREQ-001は`web`のREQ-003を`requires`し、
`platform`のTECH-005、`api`のTECH-010、`web`のTECH-010がREQ-001の規範文を`refines`する（距離1）。`platform`のTECH-002と`api`のTECH-020がTECH-005の規範文を
`refines`する（距離2）。TASKは`platform`と`api`に1件ずつあり、対象規範文を`addresses`する。`MULTI-042-01`は同じ入力で目的`interpret`を求め、TASKは閉包に含めない。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 関係・トレースモデル §7の6.: 「最短距離、種別の順REQ／TECH／ADR／TASK、IDの辞書順で並べる」。距離は起点を所有する文書を0とし、閉包を作るときに辿ったエッジ1本を1段とする。
  7.: 規範文は文書順、行番号、IDの順で並べる。§6.4: `targetStatements`は`contextDocuments`の順、行番号、IDの順。§8: カバレッジは`targetStatements`だけから得る。
- 複合ワークスペース仕様 §4・§6: 複合ワークスペースの各文書ID、規範文ID、エッジのIDは修飾IDで出力する。
  「IDの辞書順」の比較の対象は、出力するID（修飾ID）である。
- `context` §5: `documents[]`は上の順で出力する。`constraintLedger`と`coverage`は`TargetExpansion`の対象規範文の順を保つ。
- コンテキストのハッシュ値の正規化仕様 §3: 提示の順は材料に含めない（文書は修飾IDの順に材料へ置く）。ハッシュ値は並びの修正の前後で同じ値になる。
  ハッシュ値は、独立に書いた2系統の参照計算（このモジュールのリテラルA、入力の木構造から導出するB）のバイト列の一致を要求する。

参照計算`reference_*`は、入力の木構造から、閉包、距離、役割、対象規範文、カバレッジを導く（`multi_closure_alias_fixtures`の閉包の参照計算を再利用する）。
さらに、修正前の比較（起点ワークスペースの文書と規範文を修飾しないIDで比べる）の並びを導き、複合ワークスペースの入力では期待する並びと異なること
（この入力が欠陥を検出できること）、単一ワークスペースの入力では同じであること（対照）を要求する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (digest_crosscheck, digest_reference, multi_closure_alias_fixtures as alias, multi_crosscheck,
               multi_reference, multi_verify_fixtures as verify_fixtures)
from .digest_crosscheck import KIND_RANK, split_document
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
TEST_BYTES = alias.TEST_BYTES
WORKSPACE_PATHS = {"platform": ".", "web": "apps/web", "api": "services/api", "root": "."}
COMMANDS = {"platform": "platform", "api": "backend", "web": "frontend", "root": "frontend"}
KIND_DIRECTORY = {"requirement": "requirements", "technical": "technical", "task": "tasks"}
KIND_PREFIX = {"requirement": "REQ", "technical": "TECH", "task": "TASK"}
ROLE_LABEL = {"requirement": "要求", "technical": "技術仕様", "task": "作業"}

# --- 入力の表（宣言どおりの表記で書く） ---------------------------------------------------------------
#
# (ワークスペース, ローカルID): dict(title, requires/refines/addresses=宣言した参照, statement=(ラベル, 文), test=テスト対応を持つか)。
# 規範文は、REQでは`Acceptance Criteria`のAC-01、TECHでは`Constraints`のC-01に置く。テスト対応は文書自身の規範文を`covers`する。
MULTI_DOCUMENTS = {
    ("platform", "REQ-001"): dict(title="認証の基準", requires=["web::REQ-003"], statement=("AC-01", "秘密情報を出力しない"), test=True),
    ("platform", "TECH-005"): dict(title="起点側の具体化", refines=["REQ-001:AC-01"], statement=("C-01", "入力を検証する"), test=True),
    ("platform", "TECH-002"): dict(title="起点側の段階2の具体化", refines=["TECH-005:C-01"], statement=("C-01", "結果を記録する"), test=True),
    ("platform", "TASK-001"): dict(title="起点側の実装", addresses=["REQ-001:AC-01", "TECH-005:C-01", "TECH-002:C-01"]),
    ("api", "TECH-010"): dict(title="API側の具体化", refines=["platform::REQ-001:AC-01"], statement=("C-01", "応答形式を固定する"), test=True),
    ("api", "TECH-020"): dict(title="API側の段階2の具体化", refines=["platform::TECH-005:C-01"], statement=("C-01", "形式違反を拒否する"), test=True),
    ("api", "TASK-001"): dict(title="API側の実装", addresses=["platform::REQ-001:AC-01", "TECH-010:C-01", "TECH-020:C-01", "web::TECH-010:C-01"]),
    ("web", "REQ-003"): dict(title="Web側の前提の基準", statement=("AC-01", "画面を表示する")),
    ("web", "TECH-010"): dict(title="Web側の具体化", refines=["platform::REQ-001:AC-01"], statement=("C-01", "入力を検証する"), test=True),
}
SINGLE_DOCUMENTS = {
    ("root", "REQ-001"): dict(title="認証の基準", statement=("AC-01", "秘密情報を出力しない"), test=True),
    ("root", "TECH-005"): dict(title="起点側の具体化", refines=["REQ-001:AC-01"], statement=("C-01", "入力を検証する"), test=True),
    ("root", "TECH-010"): dict(title="別の具体化", refines=["REQ-001:AC-01"], statement=("C-01", "応答形式を固定する"), test=True),
    ("root", "TECH-002"): dict(title="段階2の具体化", refines=["TECH-005:C-01"], statement=("C-01", "結果を記録する"), test=True),
    ("root", "TASK-001"): dict(title="実装", addresses=["REQ-001:AC-01", "TECH-005:C-01", "TECH-010:C-01", "TECH-002:C-01"]),
}

# id: purpose, single, 起点の引数。
CASES = {
    "MULTI-042-01": dict(purpose="interpret", single=False, root="platform::REQ-001",
                         description="複合ワークスペースのinterpretのdocumentsは、同じ距離・同じ種別の文書を修飾IDの辞書順に並べる"),
    "MULTI-042-02": dict(purpose="implement", single=False, root="platform::REQ-001",
                         description="複合ワークスペースのimplementの文書、制約台帳、カバレッジの各配列は、同じ距離・同じ種別の要素を修飾IDの辞書順に並べる"),
    "MULTI-042-03": dict(purpose="implement", single=True, root="REQ-001",
                         description="単一ワークスペースの文書、制約台帳、カバレッジの並びは、修飾しないIDのまま距離、種別、IDの順で変わらない"),
}

# --- レビュー済みの期待する並び（リテラル。参照計算の結果と一致することを要求する） ------------------------------
#
# 距離0: platform::REQ-001。距離1: 種別REQ（web::REQ-003）、種別TECH（api、platform、web の順）、種別TASK（implementだけ。api、platform の順）。
# 距離2: api::TECH-020、platform::TECH-002。platform::TECH-002のローカルIDは距離1のTECH-005より小さいが、距離が遠いので後ろに並ぶ。
EXPECTED_DOCUMENTS = {
    "MULTI-042-01": ["platform::REQ-001", "web::REQ-003", "api::TECH-010", "platform::TECH-005", "web::TECH-010",
                     "api::TECH-020", "platform::TECH-002"],
    "MULTI-042-02": ["platform::REQ-001", "web::REQ-003", "api::TECH-010", "platform::TECH-005", "web::TECH-010",
                     "api::TASK-001", "platform::TASK-001", "api::TECH-020", "platform::TECH-002"],
    "MULTI-042-03": ["REQ-001", "TECH-005", "TECH-010", "TASK-001", "TECH-002"],
}
# 対象規範文（目的implement）: 起点の規範文と具体化文書の規範文。`web::REQ-003`は`requires`で到達しただけなので含めない（§6.4の4.）。
EXPECTED_STATEMENTS = {
    "MULTI-042-02": ["platform::REQ-001:AC-01", "api::TECH-010:C-01", "platform::TECH-005:C-01", "web::TECH-010:C-01",
                     "api::TECH-020:C-01", "platform::TECH-002:C-01"],
    "MULTI-042-03": ["REQ-001:AC-01", "TECH-005:C-01", "TECH-010:C-01", "TECH-002:C-01"],
}
# 役割（§7の表）と`reachedBy`（`<relation>:<宣言した文書のID>`）。
EXPECTED_ROLES = {
    "platform::REQ-001": ("root", ["root"]),
    "web::REQ-003": ("requirement", ["requires:platform::REQ-001"]),
    "api::TECH-010": ("refinement", ["refines:api::TECH-010"]),
    "platform::TECH-005": ("refinement", ["refines:platform::TECH-005"]),
    "web::TECH-010": ("refinement", ["refines:web::TECH-010"]),
    "api::TECH-020": ("refinement", ["refines:api::TECH-020"]),
    "platform::TECH-002": ("refinement", ["refines:platform::TECH-002"]),
    "api::TASK-001": ("work", ["addresses:api::TASK-001"]),
    "platform::TASK-001": ("work", ["addresses:platform::TASK-001"]),
    "REQ-001": ("root", ["root"]),
    "TECH-005": ("refinement", ["refines:TECH-005"]),
    "TECH-010": ("refinement", ["refines:TECH-010"]),
    "TECH-002": ("refinement", ["refines:TECH-002"]),
    "TASK-001": ("work", ["addresses:TASK-001"]),
}
# 境界を越えるエッジ（`source`、`relation`、`target`の辞書順）。MULTI-042-01とMULTI-042-02で、TASKが加わる分だけ異なる。
EXPECTED_CROSS_EDGES = {
    "MULTI-042-01": [("api::TECH-010", "refines", "platform::REQ-001:AC-01"),
                     ("api::TECH-020", "refines", "platform::TECH-005:C-01"),
                     ("platform::REQ-001", "requires", "web::REQ-003"),
                     ("web::TECH-010", "refines", "platform::REQ-001:AC-01")],
    "MULTI-042-02": [("api::TASK-001", "addresses", "platform::REQ-001:AC-01"),
                     ("api::TASK-001", "addresses", "web::TECH-010:C-01"),
                     ("api::TECH-010", "refines", "platform::REQ-001:AC-01"),
                     ("api::TECH-020", "refines", "platform::TECH-005:C-01"),
                     ("platform::REQ-001", "requires", "web::REQ-003"),
                     ("web::TECH-010", "refines", "platform::REQ-001:AC-01")],
}
STATEMENT_TEXT = {f"{ws}::{local}:{spec['statement'][0]}": spec["statement"][1]
                  for table in (MULTI_DOCUMENTS, SINGLE_DOCUMENTS) for (ws, local), spec in table.items() if "statement" in spec}


def documents_of(identifier):
    return SINGLE_DOCUMENTS if CASES[identifier]["single"] else MULTI_DOCUMENTS


def test_path(local):
    return f"tests/test_{local.lower().replace('-', '_')}.py"


# --- 入力 -------------------------------------------------------------------------------

def render(workspace, local, spec):
    """文書の(ファイルの全文, 正規化した本文)。"""
    kind = {"REQ": "requirement", "TECH": "technical", "TASK": "task"}[local.partition("-")[0]]
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: {'open' if kind == 'task' else 'approved'}\n"
    relations = [(key, spec[key]) for key in ("requires", "refines", "addresses") if spec.get(key)]
    if relations:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations)
    if spec.get("test"):
        label = spec["statement"][0]
        prefix = "" if workspace == "root" else f"{workspace}::"
        head += f"tests:\n  - path: {test_path(local)}\n    covers: [{prefix}{local}:{label}]\n    command: {COMMANDS[workspace]}\n"
    if kind == "task":
        head += "changes: [src/work.py]\n"
    body = f"# {local} {spec['title']}\n\n"
    if kind == "requirement":
        label, text = spec["statement"]
        body += (f"## Intent\n\n{spec['title']}の規範を定める。\n\n## Acceptance Criteria\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
                 "## Verification\n\nそれぞれのtestで確認する。\n")
    elif kind == "technical":
        label, text = spec["statement"]
        body += (f"## Context\n\n{spec['title']}を定める。\n\n## Constraints\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n")
    else:
        body += f"## Objective\n\n{spec['title']}を行う。\n"
    return head + "---\n\n" + body, body


def corpus_files(single):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    files = {}
    if single:
        files[".spec/bitz.yaml"] = multi_reference.member_config("root", COMMANDS["root"])
    else:
        # ルートワークスペースもテスト対応のコマンドを持つ（メンバーの設定と同じ形のコマンドの定義を、カタログの設定へ足す）。
        files[".spec/bitz.yaml"] = (multi_reference.root_config(alias.MEMBERS)
                                    + f"verify:\n  commands:\n    {COMMANDS['platform']}:\n      argv: [\"/bin/true\", \"{{tests}}\"]\n      cwd: .\n")
        files["apps/web/.spec/bitz.yaml"] = multi_reference.member_config("web", COMMANDS["web"])
        files["services/api/.spec/bitz.yaml"] = multi_reference.member_config("api", COMMANDS["api"])
    for (workspace, local), spec in (SINGLE_DOCUMENTS if single else MULTI_DOCUMENTS).items():
        base = "" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace] + "/"
        kind = {"REQ": "requirement", "TECH": "technical", "TASK": "task"}[local.partition("-")[0]]
        files[f"{base}.spec/{KIND_DIRECTORY[kind]}/{local}.md"] = render(workspace, local, spec)[0]
        if spec.get("test"):
            files[f"{base}{test_path(local)}"] = TEST_BYTES.decode()
    return files


def reviewed_inputs(identifier):
    return {name: text.encode() for name, text in corpus_files(CASES[identifier]["single"]).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", case["root"], "--purpose", case["purpose"], "--detail", "compact", "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json", "resultFile": "expected/context.json", "reportFileCount": 0},
    }


# --- 期待結果 ---------------------------------------------------------------------------------

def _document_spec(identifier, name):
    """表の項目(ワークスペース, ローカルID, spec)。`name`は期待する並びのID（単一ワークスペースでは修飾しない）。"""
    single = CASES[identifier]["single"]
    workspace, _, local = name.rpartition("::") if not single else ("root", "", name)
    return workspace, local, documents_of(identifier)[(workspace, local)]


def passed_context_result(identifier, context_digest):
    case = CASES[identifier]
    single = case["single"]
    names = EXPECTED_DOCUMENTS[identifier]
    documents = []
    for name in names:
        workspace, local, spec = _document_spec(identifier, name)
        kind = {"REQ": "requirement", "TECH": "technical", "TASK": "task"}[local.partition("-")[0]]
        role, reached = EXPECTED_ROLES[name]
        document = alias.bundle_document(name, None if single else workspace, kind, role,
                                         f".spec/{KIND_DIRECTORY[kind]}/{local}.md", reached, "reference")
        document["status"] = "open" if kind == "task" else "approved"
        documents.append(document)
    resolution = {"complete": True, "documentCount": len(names), "unresolvedStrongRelations": 0}
    if not single:
        resolution.update(
            workspaces=[{"id": "platform", "path": "."}, {"id": "api", "path": "services/api"}, {"id": "web", "path": "apps/web"}],
            crossWorkspaceEdges=[{"relation": relation, "source": source, "target": target}
                                 for source, relation, target in EXPECTED_CROSS_EDGES[identifier]])
    ledger, coverage = [], {"must": dict(alias.EMPTY_BUCKET), "should": dict(alias.EMPTY_BUCKET), "may": dict(alias.EMPTY_BUCKET), "adjacent": []}
    if case["purpose"] == "implement":
        targets = EXPECTED_STATEMENTS[identifier]
        for statement in targets:
            document_id = statement.rpartition(":")[0]
            ledger.append({"id": statement, "documentId": document_id, "documentRole": EXPECTED_ROLES[document_id][0],
                           "modality": "MUST", "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
                           "operation": {"kind": "CONSTRAINT", "text": STATEMENT_TEXT[statement if not single else f"root::{statement}"]}})
        # 目的`implement`の対象規範文はすべてTASKが`addresses`し、テスト対応が`covers`するので、未対応・未テストと警告はない。
        coverage["must"] = {"total": list(targets), "addressed": list(targets), "tested": list(targets), "unaddressed": [], "untested": []}
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": case["purpose"],
        "workspace": {"id": "root", "path": "."} if single else {"id": "platform", "path": "."},
        "roots": [case["root"]], "contextDigest": context_digest,
        "revision": {"commit": COMMIT, "dirty": False}, "resolution": resolution,
        "projection": {"detail": "compact", "expanded": []},
        "documents": documents, "constraintLedger": {"statements": ledger}, "coverage": coverage,
        "durationMs": 0, "diagnostics": [],
    }


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _qualified(single, workspace, reference):
    return reference if single or "::" in reference else f"{workspace}::{reference}"


def _material(identifier, workspace, local, spec):
    """文書1件のハッシュ値の材料（参照計算A）。関係の参照先は修飾IDにそろえ、辞書順に置く（正規化仕様 §3）。"""
    single = CASES[identifier]["single"]
    kind = {"REQ": "requirement", "TECH": "technical", "TASK": "task"}[local.partition("-")[0]]
    name = local if single else f"{workspace}::{local}"
    relations = {key: sorted(_qualified(single, workspace, value) for value in spec[key])
                 for key in ("requires", "refines", "addresses") if spec.get(key)}
    tests, statements = [], []
    if "statement" in spec:
        label, text = spec["statement"]
        statements = [verify_fixtures.statement_material(f"{name}:{label}", text)]
        if spec.get("test"):
            tests = [(test_path(local), f"{name}:{label}", COMMANDS[workspace])]
    document = verify_fixtures.document_material(None, name, workspace, kind, spec["title"], render(workspace, local, spec)[1],
                                                 relations=relations, tests=tests, statements=statements)
    if kind == "task":
        document["status"] = document["frontmatter"]["status"] = "open"
        document["frontmatter"]["changes"] = ["src/work.py"]
    return document


def reviewed_digest_input(identifier):
    case = CASES[identifier]
    single = case["single"]
    names = EXPECTED_DOCUMENTS[identifier]
    documents = [_material(identifier, *_document_spec(identifier, name)) for name in names]
    if single:
        return alias._material_request(True, [("root", ".")], documents, [], case["root"], purpose=case["purpose"])
    edges = [{"relation": relation, "source": source, "target": target} for source, relation, target in EXPECTED_CROSS_EDGES[identifier]]
    # `_material_request`は文書を修飾IDの順に、設定を到達ワークスペースの辞書順に置く。起点ワークスペースを先頭に、以降はIDの辞書順。
    return alias._material_request(False, [("platform", "."), ("api", "services/api"), ("web", "apps/web")], documents, edges,
                                   case["root"], purpose=case["purpose"])


def reference_digest(identifier, repository):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    case = CASES[identifier]
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier))
    if case["single"]:
        derived = digest_crosscheck.canonical_bytes(
            digest_crosscheck.build(repository, case["root"], case["purpose"], workspace_id="root"))
    else:
        derived = multi_crosscheck.canonical_bytes(alias.derived_material(repository, case["root"], case["purpose"]))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


def expected_digest(identifier):
    """生成と監査が使う、リテラルの参照計算Aのハッシュ値。"""
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_result(identifier):
    return passed_context_result(identifier, expected_digest(identifier))


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def reference_order(documents, root, purpose):
    """閉包の文書を、関係・トレースモデル §7の6.の順（最短距離、種別の順REQ/TECH/ADR/TASK、修飾IDの辞書順）に並べる。"""
    order, edges, distance = alias.interpret_closure(documents, root, purpose)
    return sorted(order, key=lambda name: (distance[name], KIND_RANK[documents[name]["kind"]], name)), edges, distance


def defective_order(documents, root, purpose, active):
    """修正前の並び: 起点ワークスペースの文書を修飾しないID、他のメンバーの文書を修飾IDで比べる（欠陥の再現。期待値の根拠にしない）。"""
    order, _, distance = alias.interpret_closure(documents, root, purpose)

    def internal(name):
        workspace, _, local = name.partition("::")
        return local if workspace == active else name

    return sorted(order, key=lambda name: (distance[name], KIND_RANK[documents[name]["kind"]], internal(name)))


def reference_targets(documents, ordered, edges, root):
    """目的`implement`の対象規範文（起点と具体化文書の規範文）を、文書の順、行番号の順に導く（関係・トレースモデル §6.4・§7の7.）。"""
    found = []
    for name in ordered:
        if name == root or alias.role_of(documents, root, name, edges) == "refinement":
            found += alias.statement_ids(documents, name)
    return found


def reference_coverage(documents, ordered, targets):
    """対応済みは閉包のTASKが`addresses`する規範文、テスト済みは閉包の文書が`covers`する規範文（§8）。"""
    addressed = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for name in ordered
                 if documents[name]["kind"] == "task" for text in documents[name]["frontmatter"]["relations"]["addresses"]}
    tested = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for name in ordered
              for entry in documents[name]["frontmatter"].get("tests", []) for text in entry["covers"]}
    return ([s for s in targets if s in addressed], [s for s in targets if s in tested],
            [s for s in targets if s not in addressed], [s for s in targets if s not in tested])


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた並び・対象規範文・カバレッジ・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = alias.load_tree(repository)
    if single != case["single"]:
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    root = f"{root_id}::{case['root']}" if single else case["root"]
    ordered, edges, _ = reference_order(documents, root, case["purpose"])

    def shown(name):
        return alias.unqualified(name) if single else name

    if [shown(name) for name in ordered] != EXPECTED_DOCUMENTS[identifier]:
        raise ValueError("期待する文書の並びが入力からの参照計算と異なります")
    if [item["id"] for item in result["documents"]] != EXPECTED_DOCUMENTS[identifier]:
        raise ValueError("文書の並びが入力からの参照計算と異なります")
    expected = alias.reference_context(documents, workspaces, root_id if single else "platform", root, case["purpose"])
    for item, wanted in zip(result["documents"], expected["documents"]):
        view = {"id": item["id"], "kind": item["kind"], "role": item["role"], "path": item["path"], "reachedBy": item["reachedBy"]}
        reference = {"id": shown(wanted["id"]), "kind": wanted["kind"], "role": wanted["role"], "path": wanted["path"],
                     "reachedBy": [ref.replace(f"{root_id}::", "") for ref in wanted["reachedBy"]] if single else wanted["reachedBy"]}
        if not single:
            view["workspaceId"], reference["workspaceId"] = item["workspaceId"], wanted["workspaceId"]
        if view != reference or EXPECTED_ROLES[item["id"]] != (item["role"], item["reachedBy"]):
            raise ValueError("文書が入力からの参照計算と異なります")
    if not single and (result["resolution"]["workspaces"] != expected["workspaces"]
                       or result["resolution"]["crossWorkspaceEdges"] != expected["edges"]):
        raise ValueError("到達ワークスペースまたは横断するエッジが入力からの参照計算と異なります")
    targets = reference_targets(documents, ordered, edges, root) if case["purpose"] == "implement" else []
    wanted_targets = [shown(item) for item in targets]
    if wanted_targets != EXPECTED_STATEMENTS.get(identifier, []):
        raise ValueError("期待する対象規範文が入力からの参照計算と異なります")
    addressed, tested, unaddressed, untested = reference_coverage(documents, ordered, targets)
    must = result["coverage"]["must"]
    if [item["id"] for item in result["constraintLedger"]["statements"]] != wanted_targets or must["total"] != wanted_targets:
        raise ValueError("制約台帳またはカバレッジの対象規範文が入力からの参照計算と異なります")
    if (must["addressed"], must["tested"], must["unaddressed"], must["untested"]) != tuple(
            [shown(item) for item in values] for values in (addressed, tested, unaddressed, untested)):
        raise ValueError("対応済みまたはテスト済みが入力からの参照計算と異なります")
    if unaddressed or untested or result["diagnostics"]:
        raise ValueError("この入力は未対応・未テストの警告を持ちません")
    if result["contextDigest"] != reference_digest(identifier, repository):
        raise ValueError("ハッシュ値が参照計算と異なります")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, root_id, _, documents = alias.load_tree(repository)
    root = f"{root_id}::{case['root']}" if single else case["root"]
    ordered, edges, distance = reference_order(documents, root, case["purpose"])
    if alias.cyclic_edges(documents) or alias.reference_diagnostics(documents, ordered):
        raise ValueError("原因はIDの比較だけである必要があります（循環・参照切れ・型違反がない）")
    for (workspace, local), spec in documents_of(identifier).items():
        path = repository / (WORKSPACE_PATHS[workspace] if WORKSPACE_PATHS[workspace] != "." else "") / test_path(local)
        if spec.get("test") and path.read_bytes() != TEST_BYTES:
            raise ValueError("テスト対応を持つ文書は、テストのファイルが存在する必要があります")
    old = defective_order(documents, root, case["purpose"], root_id if single else "platform")
    if single:
        # 対照: 単一ワークスペースは修飾しないので、修正の前後で並びが同じ。
        if old != ordered:
            raise ValueError("単一ワークスペースの並びは、内部のIDと出力のIDで同じである必要があります")
        return ordered
    # 欠陥を検出できる入力であること: 距離1のTECHが3つのワークスペースにあり、内部のIDで比べると並びが変わる。
    ties = [name for name in ordered if distance[name] == 1 and documents[name]["kind"] == "technical"]
    if {documents[name]["workspaceId"] for name in ties} != {"platform", "api", "web"} or old == ordered:
        raise ValueError("距離1のTECHが3つのワークスペースにあり、修正前の比較では並びが異なる必要があります")
    # 距離が遠い文書は、IDが小さくても後ろに並ぶ（距離が先）。種別REQは同じ距離のTECHの前、TASKは後ろ。
    if not (ordered.index("platform::TECH-002") > ordered.index("web::TECH-010")
            and ordered.index("web::REQ-003") < ordered.index("api::TECH-010")):
        raise ValueError("距離、種別が修飾IDより先に効く構成である必要があります")
    # 対象規範文の並びも、修正前の比較と異なる（制約台帳・カバレッジの欠陥を検出できる）。
    if case["purpose"] == "implement":
        old_targets = reference_targets(documents, old, edges, root)
        if old_targets == reference_targets(documents, ordered, edges, root):
            raise ValueError("対象規範文の並びも、修正前の比較と異なる必要があります")
    elif {name for name in ordered if documents[name]["kind"] == "task"}:
        raise ValueError("目的`interpret`の閉包はTASKを含めません")
    return ordered


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
        (fixture / "expected/context.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-context-order-") as temporary:
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
            result = json.loads((fixture / "expected/context.json").read_text())
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-context-order-") as temporary:
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
                            value, _ = split_document(path.read_text(encoding="utf-8"))
                            Draft202012Validator({"$ref": "#/$defs/" + alias.FIXTURE_KINDS[
                                {"requirements": "requirement", "technical": "technical", "decisions": "decision",
                                 "tasks": "task"}[path.parent.name]], "$defs": frontmatter["$defs"]}).validate(value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
