"""複合ワークスペースの診断の`summary`が、作業ワークスペースの文書IDと規範文IDも修飾することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C47・C65とADR-051の追加に対応する。複合ワークスペースの次の`summary`は、作業ワークスペースの文書IDと規範文IDを修飾せず、
他のメンバーのIDだけを修飾していた。同じ出力の中で修飾の有無が混在し、すでに修飾していた`CTX-STATE-SUPERSEDED-*`や、`verify`の
`CTX-COVERAGE-TEST-001`とも食い違った。
- `CTX-STATE-001`（目的に適用できない状態）の`summary`
- `CTX-TASK-DEPENDENCY-001`（先行するTASKが未完了）の`summary`と`suggestedAction`
- `context`の`CTX-COVERAGE-TASK-001`と`CTX-COVERAGE-TEST-001`の`summary`

この群は、作業ワークスペースのIDと他のメンバーのIDが、同じ形（`<ワークスペース>::<ID>`）で出ることを5件で固定する。
文型（文言のひな形）は変えない。差し込む値の形だけが変わる。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-047-01` | `context REQ-001 --purpose implement`、`.` | 起点（`platform`のREQ-001、状態`draft`）が目的に適用できない。`CTX-STATE-001`の1件、IDは`platform::REQ-001` |
| `MULTI-047-02` | `context TASK-002 --purpose implement`、`.` | 先行する`platform`のTASK-001と`api`のTASK-100が状態`open`。`CTX-TASK-DEPENDENCY-001`の2件、IDは`platform::TASK-001`と`api::TASK-100`（`summary`と`suggestedAction`） |
| `MULTI-047-03` | `context REQ-050 --purpose implement --detail compact`、`.` | 起点と、それを具体化する`api`のTECH-100の`MUST`にTASKもテスト対応もない。`CTX-COVERAGE-TASK-001`と`CTX-COVERAGE-TEST-001`の各2件、規範文IDは`platform::REQ-050:AC-01`と`api::TECH-100:C-01` |
| `MULTI-047-04` | `context REQ-004 --purpose implement`、`.` | 起点（`approved`）が、状態`draft`の`platform`のREQ-003と`api`のREQ-100を`requires`する。`CTX-STATE-001`の2件、IDは`api::REQ-100`と`platform::REQ-003` |
| `MULTI-047-05` | `context TASK-101 --purpose implement`、`services/api` | 作業ワークスペースがルート以外（`api`）。先行する`api`のTASK-100と`platform`のTASK-001が状態`open`。IDは`api::TASK-100`と`platform::TASK-001` |

基本のリポジトリは、ルート`platform`（`.`）とメンバー`api`（`services/api`）である。どのfixtureも、すべてコミットし、`--format json`で起動する。

期待値の根拠は規範文とユーザーの決定と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §4・§6: 複合ワークスペース内で実行したCore操作の文書`id`、規範文ID、`roots`は複合ワークスペースの正規形式（修飾ID）で返す。
- 表記規則 §3.5の6・7: 差し込む値はそのまま差し込み、同じ条件IDの診断は操作によらず同じ文型にする。
- `summary`のIDの形は規範文で1つに決まらない。ADR-062により、これは管理者が承認した値である。ユーザーの決定（2026-10-26）で、すでに修飾している
  `CTX-STATE-SUPERSEDED-*`と`verify`の`CTX-COVERAGE-TEST-001`にそろえ、作業ワークスペースのIDも`<ワークスペース>::`で修飾する。
- 結果・診断・終了コード §7: 診断の並びは、発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順で、すべて同じものは宣言に現れた順。
- 関係・トレースモデル §6.2: 起点のTASKの`requires`が直接指すTASKがすべて状態`done`でなければ`blocked`（`CTX-TASK-DEPENDENCY-001`）。

参照計算`reference_*`は、入力の木構造から、状態の診断、先行TASKの診断、閉包、対象規範文、カバレッジの診断を導く。さらに、修正前の書き方
（作業ワークスペースのIDを修飾しない）の文を導き、この入力が欠陥を検出できること（期待する文と異なること）を要求する。
ハッシュ値（`MULTI-047-03`）は、独立に書いた2系統の参照計算（このモジュールのリテラルA、入力の木構造から導出するB）のバイト列の一致を要求する。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (digest_reference, multi_closure_alias_fixtures as alias, multi_context_order_fixtures as order, multi_crosscheck,
               multi_reference, multi_verify_fixtures as verify_fixtures)
from .digest_crosscheck import read_statements, split_document
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
MEMBERS = [("api", "services/api")]
WORKSPACE_PATHS = {"platform": ".", "api": "services/api"}
KIND_DIRECTORY = {"requirement": "requirements", "technical": "technical", "task": "tasks"}
KIND_BY_PREFIX = {"REQ": "requirement", "TECH": "technical", "TASK": "task"}
DEFAULT_STATEMENT = "入力を検証する"

# --- 入力の表（宣言どおりの表記で書く） ---------------------------------------------------------------
#
# corpus名 → {(ワークスペース, ローカルID): dict(title, status, requires/refines/addresses=宣言した参照, statement=(ラベル, 文))}。
# 規範文は、REQでは`Acceptance Criteria`のAC-01、TECHでは`Constraints`のC-01に置く。TASKは規範文を持たない。状態の既定は、TASKが`open`、それ以外が`approved`。
CORPORA = {
    # 起点が状態draftのREQ（1件）。
    "state-origin": {
        ("platform", "REQ-001"): dict(title="検討中の起点", status="draft", statement=("AC-01", DEFAULT_STATEMENT)),
    },
    # 起点のTASK-002が、platformのTASK-001とapiのTASK-100（どちらも状態open）をrequiresする。
    "task-dependency": {
        ("platform", "REQ-050"): dict(title="TASKが実装する基準", statement=("AC-01", DEFAULT_STATEMENT)),
        ("platform", "TASK-001"): dict(title="先行する作業", addresses=["REQ-050:AC-01"]),
        ("platform", "TASK-002"): dict(title="起点の作業", addresses=["REQ-050:AC-01"], requires=["TASK-001", "api::TASK-100"]),
        ("api", "REQ-101"): dict(title="API側の基準", statement=("AC-01", DEFAULT_STATEMENT)),
        ("api", "TASK-100"): dict(title="API側の先行する作業", addresses=["REQ-101:AC-01"]),
    },
    # 起点のREQ-050と、それを具体化するapiのTECH-100。どちらもMUSTで、TASKもテスト対応もない。
    "coverage": {
        ("platform", "REQ-050"): dict(title="TASKもテストもない基準", statement=("AC-01", DEFAULT_STATEMENT)),
        ("api", "TECH-100"): dict(title="API側の具体化", refines=["platform::REQ-050:AC-01"], statement=("C-01", "応答形式を固定する")),
    },
    # 起点（approved）が、状態draftのplatformのREQ-003とapiのREQ-100をrequiresする。
    "state-dependencies": {
        ("platform", "REQ-003"): dict(title="検討中の前提", status="draft", statement=("AC-01", "前提を満たす")),
        ("platform", "REQ-004"): dict(title="前提に依存する起点", requires=["REQ-003", "api::REQ-100"], statement=("AC-01", DEFAULT_STATEMENT)),
        ("api", "REQ-100"): dict(title="API側の検討中の前提", status="draft", statement=("AC-01", "応答形式を固定する")),
    },
    # 作業ワークスペースがapi。起点のTASK-101が、apiのTASK-100とplatformのTASK-001（どちらも状態open）をrequiresする。
    "api-task": {
        ("platform", "REQ-050"): dict(title="TASKが実装する基準", statement=("AC-01", DEFAULT_STATEMENT)),
        ("platform", "TASK-001"): dict(title="ルート側の先行する作業", addresses=["REQ-050:AC-01"]),
        ("api", "REQ-101"): dict(title="API側の基準", statement=("AC-01", DEFAULT_STATEMENT)),
        ("api", "TASK-100"): dict(title="API側の先行する作業", addresses=["REQ-101:AC-01"]),
        ("api", "TASK-101"): dict(title="API側の起点の作業", addresses=["REQ-101:AC-01"], requires=["TASK-100", "platform::TASK-001"]),
    },
}

# id: corpus、作業ワークスペース、実行ディレクトリ、引数、起点の修飾ID、期待する状態。
CASES = {
    "MULTI-047-01": dict(corpus="state-origin", workspace="platform", cwd=".", argv=["context", "REQ-001", "--purpose", "implement"],
                         root="platform::REQ-001", outcome="blocked",
                         description="複合ワークスペースのCTX-STATE-001のsummaryは、作業ワークスペースの起点のIDも修飾する"),
    "MULTI-047-02": dict(corpus="task-dependency", workspace="platform", cwd=".", argv=["context", "TASK-002", "--purpose", "implement"],
                         root="platform::TASK-002", outcome="blocked",
                         description="複合ワークスペースのCTX-TASK-DEPENDENCY-001のsummaryとsuggestedActionは、作業ワークスペースの先行TASKのIDも修飾する"),
    "MULTI-047-03": dict(corpus="coverage", workspace="platform", cwd=".",
                         argv=["context", "REQ-050", "--purpose", "implement", "--detail", "compact"],
                         root="platform::REQ-050", outcome="passed_with_warnings",
                         description="複合ワークスペースのCTX-COVERAGE-TASK-001とCTX-COVERAGE-TEST-001のsummaryは、作業ワークスペースの規範文IDも修飾する"),
    "MULTI-047-04": dict(corpus="state-dependencies", workspace="platform", cwd=".", argv=["context", "REQ-004", "--purpose", "implement"],
                         root="platform::REQ-004", outcome="blocked",
                         description="複合ワークスペースのCTX-STATE-001のsummaryは、作業ワークスペースの依存先も他のメンバーの依存先と同じ形で修飾する"),
    "MULTI-047-05": dict(corpus="api-task", workspace="api", cwd="services/api", argv=["context", "TASK-101", "--purpose", "implement"],
                         root="api::TASK-101", outcome="blocked",
                         description="作業ワークスペースがルート以外でも、CTX-TASK-DEPENDENCY-001のsummaryはそのメンバーのIDで修飾する"),
}
RESULT_FILE = "expected/context.json"


# --- レビュー済みの期待する診断（リテラル。参照計算の結果と一致することを要求する） ----------------------------
#
# 文型は変えない。差し込む値だけが、作業ワークスペースの分も`<ワークスペース>::<ID>`になる。

def _state(workspace, path, summary):
    return {"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked", "summary": summary,
            "source": {"kind": "file", "workspaceId": workspace, "path": path}}


def _dependency(workspace, path, target):
    return {"code": "CTX-TASK-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
            "summary": f"先行する{target}が状態openで、状態doneではありません",
            "source": {"kind": "file", "workspaceId": workspace, "path": path, "key": "relations.requires"},
            "suggestedAction": f"先行する{target}を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください"}


def _coverage(workspace, path, code, summary):
    return {"code": code, "severity": "warning", "resultStatus": "passed_with_warnings", "summary": summary,
            "source": {"kind": "file", "workspaceId": workspace, "path": path}}


def _coverage_pair(workspace, path, statement):
    return [
        _coverage(workspace, path, "CTX-COVERAGE-TASK-001", f"目的implementの対象規範文MUST {statement}を実装するTASKがありません"),
        _coverage(workspace, path, "CTX-COVERAGE-TEST-001", f"対象規範文MUST {statement}にテスト対応がありません"),
    ]


EXPECTED_DIAGNOSTICS = {
    "MULTI-047-01": [_state("platform", ".spec/requirements/REQ-001.md", "platform::REQ-001は状態draftのため目的implementに適用できません")],
    # 同じ発生元（TASK-002のrelations.requires）、同じコードなので、宣言の順（platform::TASK-001、api::TASK-100）。
    "MULTI-047-02": [_dependency("platform", ".spec/tasks/TASK-002.md", "platform::TASK-001"),
                     _dependency("platform", ".spec/tasks/TASK-002.md", "api::TASK-100")],
    # 発生元のワークスペースIDの辞書順（api、platform）。同じ発生元の中ではコードの辞書順（TASK、TEST）。
    "MULTI-047-03": [*_coverage_pair("api", ".spec/technical/TECH-100.md", "api::TECH-100:C-01"),
                     *_coverage_pair("platform", ".spec/requirements/REQ-050.md", "platform::REQ-050:AC-01")],
    # 発生元のワークスペースIDの辞書順（api、platform）。
    "MULTI-047-04": [_state("api", ".spec/requirements/REQ-100.md", "api::REQ-100は状態draftのため目的implementに適用できません"),
                     _state("platform", ".spec/requirements/REQ-003.md", "platform::REQ-003は状態draftのため目的implementに適用できません")],
    "MULTI-047-05": [_dependency("api", ".spec/tasks/TASK-101.md", "api::TASK-100"),
                     _dependency("api", ".spec/tasks/TASK-101.md", "platform::TASK-001")],
}
# `MULTI-047-03`（目的implement、詳細度compact）の文書、対象規範文、役割。
EXPECTED_DOCUMENTS = ["platform::REQ-050", "api::TECH-100"]
EXPECTED_STATEMENTS = ["platform::REQ-050:AC-01", "api::TECH-100:C-01"]
EXPECTED_ROLES = {"platform::REQ-050": ("root", ["root"]), "api::TECH-100": ("refinement", ["refines:api::TECH-100"])}
EXPECTED_CROSS_EDGES = [("api::TECH-100", "refines", "platform::REQ-050:AC-01")]
STATEMENT_TEXT = {"platform::REQ-050:AC-01": DEFAULT_STATEMENT, "api::TECH-100:C-01": "応答形式を固定する"}


# --- 入力 -------------------------------------------------------------------------------

def kind_of(local):
    return KIND_BY_PREFIX[local.partition("-")[0]]


def status_of(local, spec):
    return spec.get("status", "open" if kind_of(local) == "task" else "approved")


def render(local, spec):
    """文書の(ファイルの全文, 正規化した本文)。"""
    kind = kind_of(local)
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: {status_of(local, spec)}\n"
    relations = [(key, spec[key]) for key in ("requires", "refines", "addresses") if spec.get(key)]
    if relations:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations)
    if kind == "task":
        head += "changes: [src/work.py]\n"
    body = f"# {local} {spec['title']}\n\n"
    if kind == "requirement":
        label, text = spec["statement"]
        body += (f"## Intent\n\n{spec['title']}の規範を定める。\n\n## Acceptance Criteria\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
                 "## Verification\n\nテスト対応は宣言しない。\n")
    elif kind == "technical":
        label, text = spec["statement"]
        body += (f"## Context\n\n{spec['title']}を定める。\n\n## Constraints\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n")
    else:
        body += f"## Objective\n\n{spec['title']}を行う。\n"
    return head + "---\n\n" + body, body


def corpus_files(corpus):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    files = {".spec/bitz.yaml": multi_reference.root_config(MEMBERS),
             "services/api/.spec/bitz.yaml": multi_reference.plain_config("api")}
    for (workspace, local), spec in CORPORA[corpus].items():
        base = "" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace] + "/"
        files[f"{base}.spec/{KIND_DIRECTORY[kind_of(local)]}/{local}.md"] = render(local, spec)[0]
    return files


def reviewed_inputs(identifier):
    return {name: text.encode() for name, text in corpus_files(CASES[identifier]["corpus"]).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    code = {"blocked": 2, "passed_with_warnings": 0}[case["outcome"]]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": case["outcome"], "exitCode": code, "stdout": "json", "resultFile": RESULT_FILE, "reportFileCount": 0},
    }


# --- 期待結果 ---------------------------------------------------------------------------------

def workspace_entry(workspace):
    return {"id": workspace, "path": WORKSPACE_PATHS[workspace]}


def purpose_of(case):
    return case["argv"][case["argv"].index("--purpose") + 1]


def blocked_context_result(identifier):
    """状態の検査で止まるので、閉包を作らず、ハッシュ値を計算せず、空のコンテキスト一式を返す（`SINGLE-159`、`SINGLE-051`と同じ形）。
    到達ワークスペースは起点ワークスペースだけ（`MULTI-038-08`、`MULTI-027-01`と同じ。規範が定めていない点。レビュー記録に記す）。"""
    case = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "blocked", "purpose": purpose_of(case),
        "workspace": workspace_entry(case["workspace"]), "roots": [case["root"]], "contextDigest": None,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0,
                       "workspaces": [workspace_entry(case["workspace"])], "crossWorkspaceEdges": []},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [], "constraintLedger": {"statements": []}, "coverage": {**alias.bucket(), "adjacent": []},
        "durationMs": 0, "diagnostics": EXPECTED_DIAGNOSTICS[identifier],
    }


def passed_context_result(identifier, context_digest):
    """`MULTI-047-03`: 目的implement、詳細度compactの、警告つきの成功。TASKもテスト対応もないので、対象規範文2件がすべて未対応・未テスト。"""
    case = CASES[identifier]
    documents = []
    for name in EXPECTED_DOCUMENTS:
        workspace, _, local = name.partition("::")
        kind = kind_of(local)
        role, reached = EXPECTED_ROLES[name]
        documents.append(alias.bundle_document(name, workspace, kind, role, f".spec/{KIND_DIRECTORY[kind]}/{local}.md", reached, "reference"))
    ledger = []
    for statement in EXPECTED_STATEMENTS:
        document_id = statement.rpartition(":")[0]
        ledger.append({"id": statement, "documentId": document_id, "documentRole": EXPECTED_ROLES[document_id][0],
                       "modality": "MUST", "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
                       "operation": {"kind": "CONSTRAINT", "text": STATEMENT_TEXT[statement]}})
    coverage = {**alias.bucket(), "adjacent": []}
    coverage["must"] = {"total": list(EXPECTED_STATEMENTS), "addressed": [], "tested": [],
                        "unaddressed": list(EXPECTED_STATEMENTS), "untested": list(EXPECTED_STATEMENTS)}
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed_with_warnings", "purpose": purpose_of(case),
        "workspace": workspace_entry(case["workspace"]), "roots": [case["root"]], "contextDigest": context_digest,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": True, "documentCount": len(EXPECTED_DOCUMENTS), "unresolvedStrongRelations": 0,
                       "workspaces": [workspace_entry("platform"), workspace_entry("api")],
                       "crossWorkspaceEdges": [{"relation": relation, "source": source, "target": target}
                                               for source, relation, target in EXPECTED_CROSS_EDGES]},
        "projection": {"detail": "compact", "expanded": []},
        "documents": documents, "constraintLedger": {"statements": ledger}, "coverage": coverage,
        "durationMs": 0, "diagnostics": EXPECTED_DIAGNOSTICS[identifier],
    }


# --- ハッシュ値の参照計算A（リテラル。`MULTI-047-03`だけ） ---------------------------------------------

def _material(name):
    workspace, _, local = name.partition("::")
    spec = CORPORA["coverage"][(workspace, local)]
    label, text = spec["statement"]
    relations = {key: sorted(spec[key]) for key in ("requires", "refines", "addresses") if spec.get(key)}
    return verify_fixtures.document_material(None, name, workspace, kind_of(local), spec["title"], render(local, spec)[1],
                                             relations=relations, statements=[verify_fixtures.statement_material(f"{name}:{label}", text)])


def reviewed_digest_input(identifier):
    case = CASES[identifier]
    edges = [{"relation": relation, "source": source, "target": target} for source, relation, target in EXPECTED_CROSS_EDGES]
    # 文書は修飾IDの順、設定は到達ワークスペースの辞書順に置く。起点ワークスペースを先頭に、以降はIDの辞書順。
    return alias._material_request(False, [("platform", "."), ("api", "services/api")],
                                   [_material(name) for name in EXPECTED_DOCUMENTS], edges, case["root"], purpose=purpose_of(case))


def reference_digest(identifier, repository):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    case = CASES[identifier]
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier))
    derived = multi_crosscheck.canonical_bytes(alias.derived_material(repository, case["root"], purpose_of(case)))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


def expected_digest(identifier):
    """生成と監査が使う、リテラルの参照計算Aのハッシュ値。"""
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_result(identifier):
    if CASES[identifier]["outcome"] == "blocked":
        return blocked_context_result(identifier)
    return passed_context_result(identifier, expected_digest(identifier))


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def path_of(document):
    return document["path"]


def reference_blocked(documents, root, purpose, qualify_active=True, active="platform"):
    """状態の検査（関係・トレースモデル §6.2、診断レジストリ）を入力の木構造から導く。

    起点がTASKなら、起点の状態が`open`でなければ`CTX-STATE-001`、`open`なら`requires`が直接指すTASKのうち状態`done`でないものごとに
    `CTX-TASK-DEPENDENCY-001`。起点がTASKでなければ、起点と`requires`で到達した文書のうち状態`approved`でないものごとに`CTX-STATE-001`。
    並びは、発生元のワークスペースID、`path`、`code`の辞書順で、同じものは宣言の順（結果・診断・終了コード §7）。
    `qualify_active=False`は修正前の書き方（作業ワークスペースのIDを修飾しない）の再現で、期待値の根拠にしない。
    """
    def shown(name):
        return name.partition("::")[2] if not qualify_active and name.partition("::")[0] == active else name

    found = []

    def state(name):
        document = documents[name]
        found.append({"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                      "summary": f"{shown(name)}は状態{document['frontmatter']['status']}のため目的{purpose}に適用できません",
                      "source": {"kind": "file", "workspaceId": document["workspaceId"], "path": path_of(document)}})

    if documents[root]["kind"] == "task":
        if documents[root]["frontmatter"]["status"] != "open":
            state(root)
        else:
            for _, target, exists in alias.edges_of(documents, root, "requires"):
                if exists and documents[target]["frontmatter"]["status"] != "done":
                    found.append({"code": "CTX-TASK-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
                                  "summary": f"先行する{shown(target)}が状態{documents[target]['frontmatter']['status']}で、状態doneではありません",
                                  "source": {"kind": "file", "workspaceId": documents[root]["workspaceId"], "path": path_of(documents[root]),
                                             "key": "relations.requires"},
                                  "suggestedAction": f"先行する{shown(target)}を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください"})
    else:
        seen, frontier = [root], [root]
        while frontier:
            current = frontier.pop(0)
            for _, target, exists in alias.edges_of(documents, current, "requires"):
                if exists and target not in seen:
                    seen.append(target)
                    frontier.append(target)
        for name in seen:
            if documents[name]["frontmatter"]["status"] != "approved":
                state(name)
    return sorted(found, key=lambda item: (item["source"]["workspaceId"], item["source"]["path"], item["code"]))


def reference_coverage_diagnostics(documents, targets, addressed, tested, qualify_active=True, active="platform"):
    """目的implementの対象規範文のうち、未対応なら`CTX-COVERAGE-TASK-001`、未テストなら`CTX-COVERAGE-TEST-001`（警告）。"""
    def shown(statement):
        return statement.partition("::")[2] if not qualify_active and statement.partition("::")[0] == active else statement

    found = []
    for statement in targets:
        name = statement.rpartition(":")[0]
        document = documents[name]
        modality = {item["id"]: item["modality"] for item in read_statements(document["body"])}[statement.partition("::")[2]]
        source = {"kind": "file", "workspaceId": document["workspaceId"], "path": path_of(document)}
        if statement not in addressed:
            found.append({"code": "CTX-COVERAGE-TASK-001", "severity": "warning", "resultStatus": "passed_with_warnings",
                          "summary": f"目的implementの対象規範文{modality} {shown(statement)}を実装するTASKがありません", "source": dict(source)})
        if statement not in tested:
            found.append({"code": "CTX-COVERAGE-TEST-001", "severity": "warning", "resultStatus": "passed_with_warnings",
                          "summary": f"対象規範文{modality} {shown(statement)}にテスト対応がありません", "source": dict(source)})
    return sorted(found, key=lambda item: (item["source"]["workspaceId"], item["source"]["path"], item["code"]))


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた診断・並び・対象規範文・カバレッジ・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, _, workspaces, documents = alias.load_tree(repository)
    if single:
        raise ValueError("この群は複合ワークスペースだけを扱います")
    root, purpose = case["root"], purpose_of(case)
    if result["diagnostics"] != EXPECTED_DIAGNOSTICS[identifier]:
        raise ValueError("診断がレビュー済みの期待値と異なります")
    if case["outcome"] == "blocked":
        if reference_blocked(documents, root, purpose) != result["diagnostics"]:
            raise ValueError("診断が入力からの参照計算と異なります")
        if result["contextDigest"] is not None or result["documents"] or result["resolution"]["complete"]:
            raise ValueError("状態の検査で止まる結果は、ハッシュ値と文書を持ちません")
        return
    ordered, edges, _ = order.reference_order(documents, root, purpose)
    if ordered != EXPECTED_DOCUMENTS or [item["id"] for item in result["documents"]] != EXPECTED_DOCUMENTS:
        raise ValueError("文書の並びが入力からの参照計算と異なります")
    expected = alias.reference_context(documents, workspaces, case["workspace"], root, purpose)
    for item, wanted in zip(result["documents"], expected["documents"]):
        view = {key: item[key] for key in ("id", "kind", "role", "path", "reachedBy", "workspaceId")}
        reference = {key: wanted[key] for key in ("id", "kind", "role", "path", "reachedBy", "workspaceId")}
        if view != reference or EXPECTED_ROLES[item["id"]] != (item["role"], item["reachedBy"]):
            raise ValueError("文書が入力からの参照計算と異なります")
    if (result["resolution"]["workspaces"] != expected["workspaces"] or result["resolution"]["crossWorkspaceEdges"] != expected["edges"]
            or result["resolution"]["documentCount"] != len(expected["documents"])):
        raise ValueError("到達ワークスペースまたは横断するエッジが入力からの参照計算と異なります")
    targets = order.reference_targets(documents, ordered, edges, root)
    if targets != EXPECTED_STATEMENTS or [item["id"] for item in result["constraintLedger"]["statements"]] != targets:
        raise ValueError("対象規範文が入力からの参照計算と異なります")
    addressed, tested, unaddressed, untested = order.reference_coverage(documents, ordered, targets)
    must = result["coverage"]["must"]
    if (must["total"], must["addressed"], must["tested"], must["unaddressed"], must["untested"]) != (targets, addressed, tested, unaddressed, untested):
        raise ValueError("カバレッジが入力からの参照計算と異なります")
    if reference_coverage_diagnostics(documents, targets, addressed, tested) != result["diagnostics"]:
        raise ValueError("診断が入力からの参照計算と異なります")
    if result["contextDigest"] != reference_digest(identifier, repository):
        raise ValueError("ハッシュ値が参照計算と異なります")


def mentioned(diagnostics):
    """診断の`summary`と`suggestedAction`に現れる、`<ワークスペース>::`で修飾したIDのワークスペースの集合。"""
    return {match.group(1) for item in diagnostics for text in (item["summary"], item.get("suggestedAction", ""))
            for match in re.finditer(r"([A-Za-z0-9_-]+)::(?:REQ|TECH|TASK)-[0-9]+", text)}


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, _, _, documents = alias.load_tree(repository)
    if single:
        raise ValueError("この群は複合ワークスペースだけを扱います")
    if alias.cyclic_edges(documents) or alias.reference_diagnostics(documents, sorted(documents)):
        raise ValueError("原因は状態とカバレッジだけである必要があります（循環・参照切れ・型違反がない）")
    for name in documents:
        for relation in ("requires", "refines", "addresses"):
            if any(not exists for _, _, exists in alias.edges_of(documents, name, relation)):
                raise ValueError("宣言した関係の参照先は、すべて存在する必要があります")
    root, purpose, active = case["root"], purpose_of(case), case["workspace"]
    if root.partition("::")[0] != active:
        raise ValueError("起点の所有ワークスペースが作業ワークスペースである必要があります")
    # 欠陥を検出できる入力であること: 修正前の書き方（作業ワークスペースのIDを修飾しない）の文は、期待する文と異なる。
    if case["outcome"] == "blocked":
        current = reference_blocked(documents, root, purpose)
        defective = reference_blocked(documents, root, purpose, qualify_active=False, active=active)
        diagnostics = current
    else:
        ordered, edges, _ = order.reference_order(documents, root, purpose)
        targets = order.reference_targets(documents, ordered, edges, root)
        addressed, tested, _, _ = order.reference_coverage(documents, ordered, targets)
        current = reference_coverage_diagnostics(documents, targets, addressed, tested)
        defective = reference_coverage_diagnostics(documents, targets, addressed, tested, qualify_active=False, active=active)
        diagnostics = current
    if [item["summary"] for item in current] == [item["summary"] for item in defective] or len(current) != len(defective):
        raise ValueError("修正前の書き方の文が、期待する文と異なる入力である必要があります")
    # 作業ワークスペースのIDが現れる診断を含む。「作業ワークスペースと他のメンバーのIDが同じ出力に出る」入力は、01以外のすべて。
    wanted = {"platform"} if identifier == "MULTI-047-01" else {"platform", "api"}
    if mentioned(diagnostics) != wanted:
        raise ValueError("診断の文に現れるワークスペースの集合が、この入力の想定と異なります")
    return diagnostics


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
        (fixture / RESULT_FILE).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-qualified-summary-") as temporary:
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
            result = json.loads((fixture / RESULT_FILE).read_text())
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-qualified-summary-") as temporary:
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
