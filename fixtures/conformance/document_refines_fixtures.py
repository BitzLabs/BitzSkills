"""文書を起点にした対象展開が、起点の文書を文書IDで`refines`する文書の規範文も対象規範文に含めることを固定する（Coreの公開操作は実行しない）。

実装の確認事項C54に対応する。関係・トレースモデル §6.4の規則1は、起点がREQまたは規範文のあるTECHの文書である場合、「その所有するすべての規範文と、
それらの具体化文書が持つ規範文を含める」と定め、「起点の文書を文書IDで`refines`する適用可能な文書も具体化文書であり、その規範文を含める
（規範文IDで`refines`する文書に限らない）」と明記する。用語集と§6.4の本文は、具体化文書を「選択した文書または規範文を`refines`する適用可能な文書」とし、
推移的な具体化を終端まで辿ると定める。修正前のCoreは、規範文IDで`refines`する文書の規範文しか対象規範文に含めなかった。そのため、文書IDで`refines`するTECHは
閉包に入り本文も提示されるのに、その規範文が制約台帳、カバレッジ、`verify`の`statements`に入らず、`verify`はそのTECHの未テストの`MUST`を通していた。

規範は次のとおり。
- 関係・トレースモデル §6.4の規則1: 文書を起点にした場合、起点の文書を文書IDで`refines`する適用可能な文書の規範文も、対象規範文に含める。推移的に辿る。
- 規則2: 規範文を起点にした場合は、指定した規範文の具体化文書だけを含め、文書IDで`refines`する文書は含めない。
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

# 文書ID: dict(kind, directory, title, refines=宣言する参照, statement=(ラベル, 文), test=テストのファイル名または None)。
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
}
# corpus名: dict(docs=文書IDの並び, untested=テスト対応を持たない文書ID, draft=状態`draft`の文書ID)。
CORPORA = {
    # REQ-001（テストあり）を、TECH-001（テストなし）が文書IDで`refines`する。
    "single": dict(docs=["REQ-001", "TECH-001"], untested={"TECH-001"}, draft=set()),
    # REQ-001 <- TECH-001（文書ID） <- TECH-002（文書ID） <- TECH-003（規範文ID）。TECH-003だけテストなし。
    "chain": dict(docs=["REQ-001", "TECH-001", "TECH-002", "TECH-003"], untested={"TECH-003"}, draft=set()),
    # `single`と同じ形で、TECH-001が状態`draft`。
    "draft": dict(docs=["REQ-001", "TECH-001"], untested={"TECH-001"}, draft={"TECH-001"}),
}

# id: dict(op, root, purpose, corpus, defect, description)。
#   defect: 修正前のCoreが対象規範文を取りこぼし、結果が異なる欠陥のケースか（対照は修正前のCoreも通る）。
CASES = {
    "SINGLE-169-01": dict(op="context", root="REQ-001", purpose="implement", corpus="single", defect=True,
                          description="文書IDでrefinesするTECHの規範文が、目的implementの制約台帳とカバレッジに入る"),
    "SINGLE-169-02": dict(op="verify", root="REQ-001", purpose="verify", corpus="single", defect=True,
                          description="文書IDでrefinesするTECHの未テストのMUSTを、verifyがblockedにする"),
    "SINGLE-169-03": dict(op="context", root="REQ-001", purpose="implement", corpus="chain", defect=True,
                          description="文書IDまたは規範文IDで推移的にrefinesする文書の規範文も、目的implementの制約台帳に入る"),
    "SINGLE-169-04": dict(op="verify", root="REQ-001", purpose="verify", corpus="chain", defect=True,
                          description="推移的にrefinesするTECHの未テストのMUSTを、verifyがblockedにする"),
    "SINGLE-169-05": dict(op="verify", root="REQ-001:AC-01", purpose="verify", corpus="single", defect=False,
                          description="対照: 規範文を起点にしたverifyは、文書IDでrefinesする文書の規範文を対象にしない"),
    "SINGLE-169-06": dict(op="verify", root="REQ-001", purpose="verify", corpus="draft", defect=False,
                          description="対照: 状態draftのTECHは、文書IDでrefinesしていても閉包にも対象規範文にも含めない"),
}


def statement_id(identifier):
    return f"{identifier}:{DOCS[identifier]['statement'][0]}"


def statement_text(identifier):
    return DOCS[identifier]["statement"][1]


def doc_path(identifier):
    return f".spec/{DOCS[identifier]['directory']}/{identifier}.md"


# --- 入力 -------------------------------------------------------------------------------

def document_status(identifier, corpus):
    return "draft" if identifier in CORPORA[corpus]["draft"] else "approved"


def body(identifier):
    label, text = DOCS[identifier]["statement"]
    head = f"# {identifier} {DOCS[identifier]['title']}\n\n"
    if DOCS[identifier]["kind"] == "requirement":
        return (head + "## Intent\n\n基準を定める。\n\n## Acceptance Criteria\n\n"
                f"- [{identifier}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
                "## Verification\n\nCore実装後に確認する。現時点では未証明。\n")
    return (head + "## Context\n\n実装方針を定める。\n\n## Constraints\n\n"
            f"- [{identifier}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n")


def has_test(identifier, corpus):
    return identifier not in CORPORA[corpus]["untested"]


def test_entries(identifier, corpus):
    if not has_test(identifier, corpus):
        return []
    return [{"path": DOCS[identifier]["test"], "covers": [statement_id(identifier)], "command": "default"}]


def document(identifier, corpus):
    spec = DOCS[identifier]
    head = f"---\nid: {identifier}\ntitle: {spec['title']}\nstatus: {document_status(identifier, corpus)}\n"
    if spec["refines"]:
        head += f"relations:\n  refines: [{', '.join(spec['refines'])}]\n"
    for entry in test_entries(identifier, corpus):
        head += f"tests:\n  - path: {entry['path']}\n    covers: [{', '.join(entry['covers'])}]\n    command: {entry['command']}\n"
    return (head + "---\n\n" + body(identifier)).encode()


def reviewed_inputs(identifier):
    corpus = CASES[identifier]["corpus"]
    inputs = {CONFIG_PATH: digest_reference.CONFIG.encode()}
    for doc_id in CORPORA[corpus]["docs"]:
        inputs[doc_path(doc_id)] = document(doc_id, corpus)
        if has_test(doc_id, corpus):
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
    return {
        "id": identifier, "workspaceId": "root", "kind": spec["kind"], "status": document_status(identifier, corpus),
        "applicability": "applicable",
        "frontmatter": {"id": identifier, "title": spec["title"], "status": document_status(identifier, corpus),
                        "relations": {**digest_reference.EMPTY_RELATIONS, "refines": list(spec["refines"])}, "implements": [],
                        "tests": test_entries(identifier, corpus), "verify": None, "changes": []},
        "bodyText": body(identifier), "statements": [material_statement(identifier)],
        "strongRelations": [{"relation": "refines", "target": target} for target in spec["refines"]],
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
    if spec["refines"]:
        value["relations"] = {"refines": list(spec["refines"])}
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


def old_core_targets(identifier):
    """修正前のCoreの再現: 文書を起点にしたとき、規範文IDで`refines`する文書の規範文だけを対象規範文に含める。"""
    case = CASES[identifier]
    return reference_targets(CORPORA[case["corpus"]], case["root"], include_document_refinements=False)


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def load_tree(repository):
    """入力の木構造から、文書ID -> dict(frontmatter, statements, path)を読む。"""
    documents = digest_crosscheck.load_documents(repository)
    return {identifier: dict(frontmatter=item["frontmatter"], path=item["path"],
                             statements=digest_crosscheck.read_statements(item["body"]))
            for identifier, item in documents.items()}


def _refinement_targets(frontmatter):
    return frontmatter.get("relations", {}).get("refines", [])


def reference_targets(corpus_or_documents, root, include_document_refinements=True):
    """関係・トレースモデル §6.4から、起点の対象規範文を導く。

    `corpus_or_documents`は、corpus（`CORPORA`の要素。リテラルの宣言から導くとき）または`load_tree`の結果（入力の木構造から導くとき）。
    文書を起点にしたとき、起点の文書を文書IDで`refines`する適用可能な文書（`include_document_refinements`）と、
    選択した規範文を規範文IDで`refines`する適用可能な文書の規範文を、推移的に加える。規範文を起点にしたときは文書IDの`refines`を使わない。
    """
    if "docs" in corpus_or_documents:
        corpus = corpus_or_documents
        documents = {doc: dict(frontmatter=dict(relations={"refines": DOCS[doc]["refines"]}), statements=[
            {"id": statement_id(doc)}], status="draft" if doc in corpus["draft"] else "approved") for doc in corpus["docs"]}
    else:
        documents = {doc: dict(item, status=item["frontmatter"]["status"]) for doc, item in corpus_or_documents.items()}
    statements = {doc: [item["id"] for item in documents[doc]["statements"]] for doc in documents}
    owner = root.split(":")[0]
    by_document = ":" not in root
    selected_documents = {owner} if by_document else set()
    selected_statements = set(statements[owner]) if by_document else {root}
    targets = set(selected_statements)
    changed = True
    while changed:
        changed = False
        for doc in sorted(documents):
            item = documents[doc]
            if doc in selected_documents or doc == owner or item["status"] != "approved":
                continue
            refined = _refinement_targets(item["frontmatter"])
            if any(ref in selected_statements for ref in refined) or (
                    include_document_refinements and by_document and any(ref in selected_documents for ref in refined)):
                selected_documents.add(doc)
                selected_statements.update(statements[doc])
                targets.update(statements[doc])
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
    # 修正前のCoreの再現との関係: 欠陥のケースは対象規範文が異なり、対照は同じである。
    if (old_core_targets(identifier) != targets) != case["defect"]:
        raise ValueError("修正前のCoreの再現との関係が、種類（欠陥または対照）と一致しません")
    if case["defect"] and not set(old_core_targets(identifier)) < set(targets):
        raise ValueError("欠陥のケースは、修正前のCoreが対象規範文の一部を取りこぼす入力である必要があります")
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
    # 推移的な鎖は、文書IDの`refines`と規範文IDの`refines`の両方を含む（SINGLE-169-03、04）。
    if case["corpus"] == "chain":
        refines = {doc: documents[doc]["frontmatter"].get("relations", {}).get("refines", []) for doc in documents}
        if refines != {"REQ-001": [], "TECH-001": ["REQ-001"], "TECH-002": ["TECH-001"], "TECH-003": ["TECH-002:C-01"]}:
            raise ValueError("鎖は、文書IDの`refines`2段と規範文IDの`refines`1段である必要があります")
    # 文書IDで`refines`する文書は、規範文IDでは`refines`していない（修正前のCoreが取りこぼす形）。
    if case["corpus"] in ("single", "draft") and documents["TECH-001"]["frontmatter"]["relations"]["refines"] != ["REQ-001"]:
        raise ValueError("`TECH-001`は`REQ-001`を文書IDで`refines`する必要があります")
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
    kinds = {"requirement": "reqFrontmatter", "technical": "techFrontmatter"}
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
