"""文書を起点にした対象展開が、起点の文書を文書IDで`refines`する文書の規範文も対象規範文に含めることを固定する（Coreの公開操作は実行しない）。

実装の確認事項C54に対応する。関係・トレースモデル §6.4の規則1は、起点がREQまたは規範文のあるTECHの文書である場合、「その所有するすべての規範文と、
それらの具体化文書が持つ規範文を含める」と定め、「起点の文書を文書IDで`refines`する適用可能な文書も具体化文書であり、その規範文を含める
（規範文IDで`refines`する文書に限らない）」と明記する。用語集と§6.4の本文は、具体化文書を「選択した文書または規範文を`refines`する適用可能な文書」とし、
推移的な具体化を終端まで辿ると定める。修正前のCoreは、規範文IDで`refines`する文書の規範文しか対象規範文に含めなかった。そのため、文書IDで`refines`するTECHは
閉包に入り本文も提示されるのに、その規範文が制約台帳、カバレッジ、`verify`の`statements`に入らず、`verify`はそのTECHの未テストの`MUST`を通していた。

規範は次のとおり。
- 関係・トレースモデル §6.4の規則1: 文書を起点にした場合、起点の文書を文書IDで`refines`する適用可能な文書の規範文も、対象規範文に含める。
- 見つけた具体化文書は選択済みの文書とし、その規範文を規範文IDで`refines`する文書と、その文書を文書IDで`refines`する文書の両方を、推移的に辿る。これはどの起点（規則1・2・3）でも同じ。
- 起点の文書自身を文書IDで`refines`する文書を含めるのは規則1の場合だけ。規則2の起点の所有文書、規則3で`addresses`する規範文のないTECH、規則5の起点は、文書IDの`refines`を辿る起点にしない。
- `context` §4: 制約台帳は対象規範文を1回ずつ保持する。§5: 距離2以上の具体化文書は、所有する規範文がすべて制約台帳にあれば`normative`、1件でも制約台帳になければ`full`。
- `context` §10: 目的`implement`の対象の`MUST`が未対応なら`CTX-COVERAGE-TASK-001`、未テストなら`CTX-COVERAGE-TEST-001`は`passed_with_warnings`。
  目的`verify`の`MUST`の未テストは`blocked`。
- `verify` §8: コンテキストが解決した検証対象の`statements`は対象規範文の重複なし辞書順。`blocked`の検証対象はテストを開始しない（`bindingRefs`は空）。
- 関係・トレースモデル §6.1の末尾: 目的`implement`と`verify`は、`refines`する状態`draft`の文書を閉包へ含めない。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-169-01` | `context REQ-001 --purpose implement` | `TECH-001`（`MUST`1件、テスト対応なし）が`REQ-001`を文書IDで`refines`する | `passed_with_warnings`／0。制約台帳とカバレッジに`TECH-001:C-01`が入る |
| `SINGLE-169-02` | `verify REQ-001` | 同上 | `blocked`／2。`statements`に`TECH-001:C-01`が入り、`CTX-COVERAGE-TEST-001` |
| `SINGLE-169-03` | `context REQ-001 --purpose implement` | `TECH-001`が`REQ-001`、`TECH-002`が`TECH-001`を文書IDで、`TECH-003`が`TECH-002:C-01`を規範文IDで`refines`する | `passed_with_warnings`／0。4件の規範文が入り、距離2以上の2文書は`normative` |
| `SINGLE-169-04` | `verify REQ-001` | 同上 | `blocked`／2。`statements`が4件で、テスト対応のない`TECH-003:C-01`だけが`CTX-COVERAGE-TEST-001` |
| `SINGLE-169-05` | `verify REQ-001:AC-01`（対照） | `SINGLE-169-02`と同じ入力 | `passed`／0。規範文を起点にした場合は文書IDで`refines`する文書の規範文を含めない（修正前のCoreも通る） |
| `SINGLE-169-06` | `verify REQ-001`（対照） | `SINGLE-169-02`と同じ入力。ただし`TECH-001`は状態`draft` | `passed`／0。`draft`の文書は閉包に含めず、規範文を含めない（修正前のCoreも通る） |
| `SINGLE-169-07` | `verify REQ-001` | `TECH-002`が`REQ-001:AC-01`を規範文IDで、`TECH-003`が`TECH-002`を文書IDで`refines`する。`TECH-003`だけテスト対応なし | `blocked`／2。規範文IDで見つけた`TECH-002`を文書IDで`refines`する`TECH-003`の規範文も含む（`statements`が3件、`TECH-003:C-01`が`CTX-COVERAGE-TEST-001`） |
| `SINGLE-169-08` | `verify REQ-001:AC-01` | `TECH-001`が`REQ-001`を文書IDで、`TECH-002`が`REQ-001:AC-01`を規範文IDで、`TECH-003`が`TECH-002`を文書IDで`refines`する。`TECH-001`と`TECH-003`はテスト対応なし | `blocked`／2。規範文を起点にしても、見つけた`TECH-002`からは文書IDの`refines`を辿り`TECH-003:C-01`を含む。起点の所有文書を文書IDで`refines`する`TECH-001`の規範文は含めない |
| `SINGLE-169-09` | `verify TASK-001` | `SINGLE-169-08`と同じ入力に、`REQ-001:AC-01`を`addresses`する状態`open`の`TASK-001`を加える | `blocked`／2。規則3でも`SINGLE-169-08`と同じ`statements`と診断 |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、`digest_crosscheck`の木構造からの導出B）のバイト列の一致を要求する。対象規範文、カバレッジの診断は、準備手順の後の入力の木構造から導く。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import compare_state, observe

HERE = Path(__file__).resolve().parent
CONFIG_PATH = digest_reference.CONFIG_PATH
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}
ACTOR = "TargetSystem"

# 文書ID: dict(kind, directory, title, refines=宣言する参照の既定, statement=(ラベル, 文), test=テストのファイル名または None)。
# 規範文はすべて`[ALWAYS] [MUST] [CONSTRAINT]`の1件で、REQでは`Acceptance Criteria`のAC-01、TECHでは`Constraints`のC-01に置く。
DOCS = {
    "REQ-001": dict(kind="requirement", directory="requirements", title="認証の基準", refines=[],
                    statement=("AC-01", "秘密情報を出力しない"), test="tests/test_req.py"),
    "TECH-001": dict(kind="technical", directory="technical", title="認証の実装方針", refines=["REQ-001"],
                     statement=("C-01", "秘密情報を記録しない"), test="tests/test_tech1.py"),
    "TECH-002": dict(kind="technical", directory="technical", title="記録の実装方針", refines=["TECH-001"],
                     statement=("C-01", "記録に利用者の識別子を含めない"), test="tests/test_tech2.py"),
    "TECH-003": dict(kind="technical", directory="technical", title="監査記録の実装方針", refines=["TECH-002:C-01"],
                     statement=("C-01", "監査記録を追記だけにする"), test="tests/test_tech3.py"),
    # 規範文を持たないTASK。`addresses`はcorpusの`addresses`で宣言する。
    "TASK-001": dict(kind="task", directory="tasks", title="認証の実装", refines=[], statement=None, test=None),
}
# corpus名: dict(docs=文書IDの並び（距離、種別、IDの順）, untested=テスト対応を持たない文書ID, draft=状態`draft`の文書ID,
#   refines=既定と異なる`refines`の宣言, addresses=TASKの`addresses`の宣言)。
CORPORA = {
    # REQ-001（テストあり）を、TECH-001（テストなし）が文書IDで`refines`する。
    "single": dict(docs=["REQ-001", "TECH-001"], untested={"TECH-001"}, draft=set()),
    # REQ-001 <- TECH-001（文書ID） <- TECH-002（文書ID） <- TECH-003（規範文ID）。TECH-003だけテストなし。
    "chain": dict(docs=["REQ-001", "TECH-001", "TECH-002", "TECH-003"], untested={"TECH-003"}, draft=set()),
    # `single`と同じ形で、TECH-001が状態`draft`。
    "draft": dict(docs=["REQ-001", "TECH-001"], untested={"TECH-001"}, draft={"TECH-001"}),
    # REQ-001 <- TECH-002（規範文ID） <- TECH-003（文書ID）。TECH-003だけテストなし。
    "found-document": dict(docs=["REQ-001", "TECH-002", "TECH-003"], untested={"TECH-003"}, draft=set(),
                           refines={"TECH-002": ["REQ-001:AC-01"], "TECH-003": ["TECH-002"]}),
    # `found-document`に、REQ-001を文書IDで`refines`するTECH-001（テストなし）を加える。
    "owner-document": dict(docs=["REQ-001", "TECH-001", "TECH-002", "TECH-003"], untested={"TECH-001", "TECH-003"}, draft=set(),
                           refines={"TECH-001": ["REQ-001"], "TECH-002": ["REQ-001:AC-01"], "TECH-003": ["TECH-002"]}),
    # `owner-document`に、REQ-001:AC-01を`addresses`するTASK-001を加える（TASKは閉包の起点なので先頭）。
    "task": dict(docs=["TASK-001", "REQ-001", "TECH-001", "TECH-002", "TECH-003"], untested={"TECH-001", "TECH-003"}, draft=set(),
                 refines={"TECH-001": ["REQ-001"], "TECH-002": ["REQ-001:AC-01"], "TECH-003": ["TECH-002"]},
                 addresses={"TASK-001": ["REQ-001:AC-01"]}),
}

# id: dict(op, root, purpose, corpus, defect, midway_defect, description)。
#   defect: `origin/main`のCore（文書IDの`refines`を辿らない）が対象規範文を取りこぼし、結果が異なる欠陥のケースか（対照は通る）。
#   midway_defect: 途中のCore（起点の文書からだけ文書IDの`refines`を辿り、見つけた文書の先は規範文IDだけ）が取りこぼすケースか。
CASES = {
    "SINGLE-169-01": dict(op="context", root="REQ-001", purpose="implement", corpus="single", defect=True, midway_defect=False,
                          description="文書IDでrefinesするTECHの規範文が、目的implementの制約台帳とカバレッジに入る"),
    "SINGLE-169-02": dict(op="verify", root="REQ-001", purpose="verify", corpus="single", defect=True, midway_defect=False,
                          description="文書IDでrefinesするTECHの未テストのMUSTを、verifyがblockedにする"),
    "SINGLE-169-03": dict(op="context", root="REQ-001", purpose="implement", corpus="chain", defect=True, midway_defect=False,
                          description="文書IDまたは規範文IDで推移的にrefinesする文書の規範文も、目的implementの制約台帳に入る"),
    "SINGLE-169-04": dict(op="verify", root="REQ-001", purpose="verify", corpus="chain", defect=True, midway_defect=False,
                          description="推移的にrefinesするTECHの未テストのMUSTを、verifyがblockedにする"),
    "SINGLE-169-05": dict(op="verify", root="REQ-001:AC-01", purpose="verify", corpus="single", defect=False, midway_defect=False,
                          description="対照: 規範文を起点にしたverifyは、文書IDでrefinesする文書の規範文を対象にしない"),
    "SINGLE-169-06": dict(op="verify", root="REQ-001", purpose="verify", corpus="draft", defect=False, midway_defect=False,
                          description="対照: 状態draftのTECHは、文書IDでrefinesしていても閉包にも対象規範文にも含めない"),
    "SINGLE-169-07": dict(op="verify", root="REQ-001", purpose="verify", corpus="found-document", defect=True, midway_defect=True,
                          description="規範文IDで見つけた具体化文書を文書IDでrefinesするTECHの未テストのMUSTを、文書の起点のverifyがblockedにする"),
    "SINGLE-169-08": dict(op="verify", root="REQ-001:AC-01", purpose="verify", corpus="owner-document", defect=True, midway_defect=True,
                          targets=["REQ-001:AC-01", "TECH-002:C-01", "TECH-003:C-01"],
                          description="規範文の起点でも、見つけた具体化文書は文書IDのrefinesで辿り、起点の所有文書を文書IDでrefinesするTECHは対象にしない"),
    "SINGLE-169-09": dict(op="verify", root="TASK-001", purpose="verify", corpus="task", defect=True, midway_defect=True,
                          targets=["REQ-001:AC-01", "TECH-002:C-01", "TECH-003:C-01"],
                          description="TASKの起点でも、見つけた具体化文書は文書IDのrefinesで辿り、addressesする規範文の所有文書を文書IDでrefinesするTECHは対象にしない"),
}


def addresses_of(identifier, corpus):
    return CORPORA[corpus].get("addresses", {}).get(identifier, [])


def refines_of(identifier, corpus):
    return CORPORA[corpus].get("refines", {}).get(identifier, DOCS[identifier]["refines"])


def statement_id(identifier):
    if DOCS[identifier]["statement"] is None:
        raise ValueError(f"{identifier}は規範文を持ちません")
    return f"{identifier}:{DOCS[identifier]['statement'][0]}"


def statement_text(identifier):
    return DOCS[identifier]["statement"][1]


def doc_path(identifier):
    return f".spec/{DOCS[identifier]['directory']}/{identifier}.md"


# --- 入力 -------------------------------------------------------------------------------

def document_status(identifier, corpus):
    if DOCS[identifier]["kind"] == "task":
        return "open"
    return "draft" if identifier in CORPORA[corpus]["draft"] else "approved"


def body(identifier):
    head = f"# {identifier} {DOCS[identifier]['title']}\n\n"
    if DOCS[identifier]["kind"] == "task":
        return head + "## Objective\n\nAC-01を実装する。\n"
    label, text = DOCS[identifier]["statement"]
    if DOCS[identifier]["kind"] == "requirement":
        return (head + "## Intent\n\n基準を定める。\n\n## Acceptance Criteria\n\n"
                f"- [{identifier}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
                "## Verification\n\nCore実装後に確認する。現時点では未証明。\n")
    return (head + "## Context\n\n実装方針を定める。\n\n## Constraints\n\n"
            f"- [{identifier}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n")


def has_test(identifier, corpus):
    return identifier not in CORPORA[corpus]["untested"]


def test_entries(identifier, corpus):
    if DOCS[identifier]["kind"] == "task" or not has_test(identifier, corpus):
        return []
    return [{"path": DOCS[identifier]["test"], "covers": [statement_id(identifier)], "command": "default"}]


def document(identifier, corpus):
    spec = DOCS[identifier]
    head = f"---\nid: {identifier}\ntitle: {spec['title']}\nstatus: {document_status(identifier, corpus)}\n"
    relations = {"refines": refines_of(identifier, corpus), "addresses": addresses_of(identifier, corpus)}
    declared = [(key, values) for key, values in relations.items() if values]
    if declared:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in declared)
    for entry in test_entries(identifier, corpus):
        head += f"tests:\n  - path: {entry['path']}\n    covers: [{', '.join(entry['covers'])}]\n    command: {entry['command']}\n"
    return (head + "---\n\n" + body(identifier)).encode()


def reviewed_inputs(identifier):
    corpus = CASES[identifier]["corpus"]
    inputs = {CONFIG_PATH: digest_reference.CONFIG.encode()}
    for doc_id in CORPORA[corpus]["docs"]:
        inputs[doc_path(doc_id)] = document(doc_id, corpus)
        if test_entries(doc_id, corpus):
            inputs[DOCS[doc_id]["test"]] = f"def test_{doc_id.lower().replace('-', '_')}():\n    assert True\n".encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reviewed_status(identifier)
    if case["op"] == "context":
        argv, setup_plan = ["context", case["root"], "--purpose", case["purpose"]], {"git": True, "operations": []}
    else:
        # `verify`は、テスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をステージする。
        argv, setup_plan = ["verify", case["root"]], {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    return {
        "fixtureId": identifier, "description": case["description"], "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*argv, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0},
    }


# --- レビュー済みの対象規範文・診断・状態（リテラル） -----------------------------------------------

def reviewed_closure(identifier):
    """閉包の文書ID（距離、種別、IDの順）。状態`draft`の文書は目的`implement`と`verify`の閉包に含めない。"""
    corpus = CASES[identifier]["corpus"]
    return [doc for doc in CORPORA[corpus]["docs"] if doc not in CORPORA[corpus]["draft"]]


def reviewed_targets(identifier):
    """対象規範文（`contextDocuments`の順）。規範文を起点にした場合は指定した規範文だけ（規則2）。"""
    case = CASES[identifier]
    if "targets" in case:
        return list(case["targets"])
    if ":" in case["root"]:
        return [case["root"]]
    return [statement_id(doc) for doc in reviewed_closure(identifier)]


def reviewed_untested(identifier):
    corpus = CASES[identifier]["corpus"]
    return [target for target in reviewed_targets(identifier) if not has_test(target.partition(":")[0], corpus)]


def coverage_warning(code, doc_id, summary):
    return {"code": code, "severity": "warning", "resultStatus": "passed_with_warnings", "summary": summary,
            "source": {"kind": "file", "workspaceId": "root", "path": doc_path(doc_id)}}


def reviewed_diagnostics(identifier):
    """リテラルの期待値。発生元の`path`、`code`の辞書順（結果・診断・終了コード §7）。"""
    case = CASES[identifier]
    found = []
    if case["purpose"] == "implement":
        for target in reviewed_targets(identifier):
            found.append(coverage_warning("CTX-COVERAGE-TASK-001", target.partition(":")[0],
                                          f"目的implementの対象規範文MUST {target}を実装するTASKがありません"))
    for target in reviewed_untested(identifier):
        doc_id = target.partition(":")[0]
        summary = f"対象規範文MUST {target}にテスト対応がありません"
        if case["purpose"] == "implement":
            found.append(coverage_warning("CTX-COVERAGE-TEST-001", doc_id, summary))
        else:
            found.append({"code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked", "summary": summary,
                          "source": {"kind": "file", "workspaceId": "root", "path": doc_path(doc_id)}})
    return sorted(found, key=lambda item: (item["source"]["path"], item["code"]))


def reviewed_status(identifier):
    diagnostics = reviewed_diagnostics(identifier)
    if any(item["resultStatus"] == "blocked" for item in diagnostics):
        return "blocked"
    return "passed_with_warnings" if diagnostics else "passed"


# --- レビュー済みのハッシュ値の材料（参照計算A） -------------------------------------------

def material_statement(identifier):
    return {"id": statement_id(identifier), "actor": ACTOR, "activation": {"kind": "ALWAYS", "text": None}, "modality": "MUST",
            "reason": None, "operation": {"kind": "CONSTRAINT", "text": statement_text(identifier)}, "extensions": []}


def material_document(identifier, corpus):
    spec = DOCS[identifier]
    refines, addresses = refines_of(identifier, corpus), addresses_of(identifier, corpus)
    return {
        "id": identifier, "workspaceId": "root", "kind": spec["kind"], "status": document_status(identifier, corpus),
        "applicability": "applicable",
        "frontmatter": {"id": identifier, "title": spec["title"], "status": document_status(identifier, corpus),
                        "relations": {**digest_reference.EMPTY_RELATIONS, "refines": list(refines), "addresses": list(addresses)},
                        "implements": [], "tests": test_entries(identifier, corpus), "verify": None, "changes": []},
        "bodyText": body(identifier), "statements": [] if spec["statement"] is None else [material_statement(identifier)],
        "strongRelations": [{"relation": "refines", "target": target} for target in refines]
                           + [{"relation": "addresses", "target": target} for target in addresses],
    }


def reviewed_digest_input(identifier):
    case = CASES[identifier]
    corpus, purpose = case["corpus"], case["purpose"]
    verify = purpose == "verify"
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": purpose, "requestWorkspaceId": "root", "roots": [case["root"]],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [material_document(doc, corpus) for doc in sorted(reviewed_closure(identifier))],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            # 目的`implement`はテスト割当てを記録しない（コンテキスト §6）。
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}] if verify else [],
            "commands": [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}] if verify else [],
        },
    }


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def frontmatter_projection(identifier, corpus):
    spec = DOCS[identifier]
    value = {"id": identifier, "title": spec["title"], "status": document_status(identifier, corpus)}
    if refines_of(identifier, corpus):
        value["relations"] = {"refines": list(refines_of(identifier, corpus))}
    if test_entries(identifier, corpus):
        value["tests"] = test_entries(identifier, corpus)
    return value


def context_document(doc_id, corpus, normative):
    """距離は閉包の並びの添字と同じ（REQ-001が0、以降は1ずつ）。"""
    base = {"id": doc_id, "kind": DOCS[doc_id]["kind"], "status": "approved", "role": "root" if doc_id == "REQ-001" else "refinement",
            "path": doc_path(doc_id), "projection": "normative" if normative else "full",
            "reachedBy": ["root"] if doc_id == "REQ-001" else [f"refines:{doc_id}"],
            "statementRefs": [statement_id(doc_id)]}
    if not normative:
        base["frontmatter"] = frontmatter_projection(doc_id, corpus)
        base["bodyText"] = body(doc_id)
    base["untrustedText"] = True
    return base


def ledger_entry(target):
    doc_id = target.partition(":")[0]
    return {"id": target, "documentId": doc_id, "documentRole": "root" if doc_id == "REQ-001" else "refinement",
            "modality": "MUST", "reason": None, "actor": ACTOR, "activation": {"kind": "ALWAYS"},
            "operation": {"kind": "CONSTRAINT", "text": statement_text(doc_id)}}


def reviewed_context_result(identifier):
    case = CASES[identifier]
    corpus, closure, targets = case["corpus"], reviewed_closure(identifier), reviewed_targets(identifier)
    untested = reviewed_untested(identifier)
    status = reviewed_status(identifier)
    return {
        "schemaVersion": "1.0", "operation": "context", "status": status, "purpose": case["purpose"],
        "workspace": {"id": "root", "path": "."}, "roots": [case["root"]], "contextDigest": context_digest(identifier),
        "revision": None,
        "resolution": {"complete": True, "documentCount": len(closure), "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        # 距離2以上の具体化文書は、所有する規範文がすべて制約台帳にあるので`normative`（`context` §5）。距離1の文書は`full`。
        "documents": [context_document(doc, corpus, normative=position >= 2) for position, doc in enumerate(closure)],
        "constraintLedger": {"statements": [ledger_entry(target) for target in targets]},
        "coverage": {
            "must": {"total": list(targets), "addressed": [], "tested": [t for t in targets if t not in untested],
                     "unaddressed": list(targets), "untested": list(untested)},
            "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": reviewed_diagnostics(identifier),
    }


def reviewed_verify_result(identifier):
    case = CASES[identifier]
    corpus, targets = case["corpus"], reviewed_targets(identifier)
    status = reviewed_status(identifier)
    blocked = status == "blocked"
    # 実行するテスト割当ては、対象規範文を`covers`するテスト対応のコマンド`default`の1件。ファイルは対象規範文のテスト対応の順。
    tests = [] if blocked else [DOCS[t.partition(":")[0]]["test"] for t in targets if has_test(t.partition(":")[0], corpus)]
    entry = {"target": case["root"], "status": status, "contextDigest": context_digest(identifier), "statements": list(targets),
             "bindingRefs": [] if blocked else ["root::default"], "diagnostics": reviewed_diagnostics(identifier)}
    commands = [] if blocked else [{
        "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed", "termination": "exit",
        "cwd": ".", "argv": ["/bin/true", *tests], "tests": tests,
        "covers": [t for t in targets if has_test(t.partition(":")[0], corpus)], "exitCode": 0, "timeoutSeconds": 300,
        "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None, "commands": commands,
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier):
    return reviewed_context_result(identifier) if CASES[identifier]["op"] == "context" else reviewed_verify_result(identifier)


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def result_targets(result):
    """結果の木構造から読み取る対象規範文（`context`は制約台帳、`verify`は`statements`）。"""
    if result["operation"] == "context":
        return [item["id"] for item in result["constraintLedger"]["statements"]]
    return result["targetResults"][0]["statements"]


def old_core_targets(identifier, mode):
    """修正前のCoreの再現。`main`は`origin/main`のCore（文書IDの`refines`を辿らない）、`midway`は途中のCore
    （規則1の起点の文書から文書IDで辿るが、規範文IDで見つけた文書の先は文書IDで辿らない）。"""
    case = CASES[identifier]
    return reference_targets(CORPORA[case["corpus"]], case["root"], mode=mode)


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def load_tree(repository):
    """入力の木構造から、文書ID -> dict(kind, frontmatter, statements, path)を読む。"""
    documents = digest_crosscheck.load_documents(repository)
    return {identifier: dict(kind=item["kind"], frontmatter=item["frontmatter"], path=item["path"],
                             statements=digest_crosscheck.read_statements(item["body"]))
            for identifier, item in documents.items()}


def corpus_documents(corpus):
    """corpusのリテラルの宣言から、`load_tree`と同じ形の文書の索引を作る（`status`は`frontmatter`に置く）。"""
    documents = {}
    for doc in corpus["docs"]:
        relations = {"refines": corpus.get("refines", {}).get(doc, DOCS[doc]["refines"]),
                     "addresses": corpus.get("addresses", {}).get(doc, [])}
        documents[doc] = dict(kind=DOCS[doc]["kind"], statements=[] if DOCS[doc]["statement"] is None else [{"id": statement_id(doc)}],
                              frontmatter={"status": "draft" if doc in corpus["draft"] else ("open" if DOCS[doc]["kind"] == "task" else "approved"),
                                           "relations": relations})
    return documents


def reference_targets(corpus_or_documents, root, mode="current"):
    """関係・トレースモデル §6.4から、起点の対象規範文を導く。

    `corpus_or_documents`は、corpus（`CORPORA`の要素。リテラルの宣言から導くとき）または`load_tree`の結果（入力の木構造から導くとき）。
    - 選択済みの規範文を規範文IDで`refines`する適用可能な文書は、どの起点でも具体化文書として規範文を加える。
    - 文書IDの`refines`を辿るのは、規則1（規範文のある文書の起点）の起点の文書と、見つけた具体化文書である。規則2の起点の所有文書、
      規則3の起点のTASK（`addresses`する規範文のないTECHを含む）、規則5の起点（規範文のないTECH）は、文書IDの`refines`を辿る起点にしない。
    `mode`: `current`は上の規則、`main`は文書IDの`refines`を辿らない（`origin/main`のCoreの再現）、`midway`は規則1の起点の文書と、
    それを文書IDで見つけた文書だけ文書IDで辿る（途中のCoreの再現）。
    """
    documents = corpus_documents(corpus_or_documents) if "docs" in corpus_or_documents else corpus_or_documents
    statements = {doc: [item["id"] for item in documents[doc]["statements"]] for doc in documents}
    known = {statement for ids in statements.values() for statement in ids}
    owner = root.split(":")[0]
    if ":" in root:
        selected_statements, followed = {root}, set()
    elif documents[owner]["kind"] == "task":
        selected_statements = {ref for ref in documents[owner]["frontmatter"].get("relations", {}).get("addresses", []) if ref in known}
        followed = set()
    else:
        selected_statements = set(statements[owner])
        followed = {owner} if statements[owner] and mode != "main" else set()
    targets, found = set(selected_statements), set()
    changed = True
    while changed:
        changed = False
        for doc in sorted(documents):
            item = documents[doc]
            if doc in found or doc == owner or item["kind"] not in ("requirement", "technical") or item["frontmatter"]["status"] != "approved":
                continue
            refined = item["frontmatter"].get("relations", {}).get("refines", [])
            by_statement = any(ref in selected_statements for ref in refined)
            by_document = mode != "main" and any(ref in followed for ref in refined)
            if not (by_statement or by_document):
                continue
            found.add(doc)
            selected_statements.update(statements[doc])
            targets.update(statements[doc])
            if mode == "current" or (mode == "midway" and by_document):
                followed.add(doc)
            changed = True
    return sorted(targets, key=lambda target: (target.partition(":")[0] != owner, target))


def reference_tested(documents, closure):
    return {covered for doc in closure for entry in documents[doc]["frontmatter"].get("tests", []) for covered in entry["covers"]}


def reference_diagnostics(documents, closure, targets, purpose):
    tested = reference_tested(documents, closure)
    found = []
    for target in targets:
        doc_id = target.partition(":")[0]
        if purpose == "implement":
            found.append(coverage_warning("CTX-COVERAGE-TASK-001", doc_id, f"目的implementの対象規範文MUST {target}を実装するTASKがありません"))
        if target not in tested:
            summary = f"対象規範文MUST {target}にテスト対応がありません"
            if purpose == "implement":
                found.append(coverage_warning("CTX-COVERAGE-TEST-001", doc_id, summary))
            else:
                found.append({"code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked", "summary": summary,
                              "source": {"kind": "file", "workspaceId": "root", "path": documents[doc_id]["path"]}})
    return sorted(found, key=lambda item: (item["source"]["path"], item["code"]))


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    documents = load_tree(repository)
    closure, advisory = digest_crosscheck.closure(documents_for_crosscheck(repository), case["root"], case["purpose"])
    if closure != reviewed_closure(identifier) or advisory:
        raise ValueError("閉包がレビュー済みの期待値と異なります")
    targets = reference_targets(documents, case["root"])
    if targets != reviewed_targets(identifier) or result_targets(result) != targets:
        raise ValueError("対象規範文が参照計算と異なります")
    # 入力の木構造から導いた対象規範文は、corpusのリテラルの宣言から導いたものと一致する（どの再現でも）。
    for mode in ("current", "main", "midway"):
        if reference_targets(documents, case["root"], mode) != reference_targets(CORPORA[case["corpus"]], case["root"], mode):
            raise ValueError("入力の木構造から導く対象規範文が、corpusの宣言から導くものと異なります")
    # 修正前のCoreの再現との関係: 欠陥のケースは対象規範文が真部分集合になり、対照は同じである。
    for mode, flag in (("main", case["defect"]), ("midway", case["midway_defect"])):
        old = old_core_targets(identifier, mode)
        if (old != targets) != flag or (flag and not set(old) < set(targets)):
            raise ValueError("修正前のCoreの再現との関係が、種類（欠陥または対照）と一致しません")
    derived = reference_diagnostics(documents, closure, targets, case["purpose"])
    if derived != reviewed_diagnostics(identifier):
        raise ValueError("入力から導く診断がレビュー済みの期待値と異なります")
    status = "blocked" if any(item["resultStatus"] == "blocked" for item in derived) else ("passed_with_warnings" if derived else "passed")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    holder = result["diagnostics"] if case["op"] == "context" else result["targetResults"][0]["diagnostics"]
    other = result["diagnostics"] if case["op"] == "verify" else []
    if holder != derived or other:
        raise ValueError("診断の置き場所または内容が参照計算と異なります")
    # 関係の宣言は、corpusのリテラルと一致する（文書IDの`refines`と規範文IDの`refines`、`addresses`の形をcorpusで固定する）。
    for doc, item in documents.items():
        relations = item["frontmatter"].get("relations", {})
        if (relations.get("refines", []), relations.get("addresses", [])) != (refines_of(doc, case["corpus"]), addresses_of(doc, case["corpus"])):
            raise ValueError("関係の宣言がcorpusと異なります")
    if case["op"] == "context":
        projections = {item["id"]: item["projection"] for item in result["documents"]}
        expected = {doc: ("normative" if position >= 2 else "full") for position, doc in enumerate(closure)}
        if projections != expected:
            raise ValueError("提示形式が距離と制約台帳への収録から導く形と異なります")
    else:
        # `blocked`の検証対象はテストを開始せず、`passed`は対象規範文を`covers`するテスト対応のコマンドを1回実行する。
        entry = result["targetResults"][0]
        if (status == "blocked") != (not result["commands"] and entry["bindingRefs"] == []):
            raise ValueError("`blocked`の結果だけがテストを開始しません")


def documents_for_crosscheck(repository):
    return digest_crosscheck.load_documents(repository)


def check_digest(identifier, repository, result):
    case = CASES[identifier]
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, case["root"], case["purpose"]))
    digest = result["contextDigest"] if case["op"] == "context" else result["targetResults"][0]["contextDigest"]
    if digest_crosscheck.digest(derived) != digest:
        raise ValueError("ハッシュ値が参照計算Bと一致しません")
    if digest_reference.canonical_bytes(reviewed_digest_input(identifier)) != derived:
        raise ValueError("ハッシュ値の参照計算AとBが一致しません")


# --- 書き出しと監査 ---------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "single" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / f"expected/{CASES[identifier]['op']}.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-document-refines-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


def actual_files(fixture):
    """`repo/`の通常のファイル(パス→バイト列)。シンボリックリンクと実行ビットを拒否する。"""
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
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    kinds = {"requirement": "reqFrontmatter", "technical": "techFrontmatter", "task": "taskFrontmatter"}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            case = CASES[identifier]
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{case['op']}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            if actual_files(fixture) != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {f"expected/{case['op']}.json"}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-document-refines-") as temporary:
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
                    check_conditions(identifier, repository, manifest, result)
                    check_digest(identifier, repository, result)
                    for item in digest_crosscheck.load_documents(repository).values():
                        Draft202012Validator({"$ref": "#/$defs/" + kinds[item["kind"]],
                                              "$defs": schema["$defs"]}).validate(item["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
