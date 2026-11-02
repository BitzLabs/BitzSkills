"""単一ワークスペースの`context`と`verify`が、閉包の文書が宣言する`related`の参照切れの警告を返すことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C78に対応する。`related`の参照切れは、`check`が診断`SPEC-RELATION-ADVISORY-MISSING-001`（`warning`）で返していたが、
`context`と`verify`は関係の診断からエラーだけを残し、この警告を捨てていた。規範は次のとおり定めている。

- 関係・トレースモデル §3: `related`は閉包を増やさず、参照切れは診断`SPEC-RELATION-ADVISORY-MISSING-001`（重大度`warning`）とする。
  診断レジストリの条件`RELATION-TARGET-MISSING-RELATED`は、返しうる操作を`context`、`check`、`verify`、結果への効果を`passed_with_warnings`、
  継続単位を`skip-edge`と定める。
- `context` §10: 閉包の文書が宣言する`related`の参照先が存在しない場合の警告は、コンテキストを失敗させず、成功・失敗のどちらの結果にも加える。
- `verify` §9: 閉包の文書が宣言する`related`の参照切れは、検証対象を失敗させず、展開した後のどの結果にもその検証対象の`diagnostics`へ加える。
- 結果・診断・終了コード §4: 関係のエッジを単位とする診断は、`evidence`に参照先を宣言どおりの文字列で持つ。§7: 診断は発生元のワークスペースID、`path`、`line`、
  `column`、`code`、`specRefs`の辞書順に並べ、これらがすべて同じ診断は生成元の宣言に現れた順（関係の配列の順）とする。
- 結果・診断・終了コード §3: `warning`だけなら`passed_with_warnings`で終了コード0。`failed`の診断があれば`failed`で終了コード1。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-168-01` | `context REQ-001 --purpose interpret` | `TECH-001`が存在しない`ADR-099`を`related`する | `passed_with_warnings`／0。警告1件 |
| `SINGLE-168-02` | `context REQ-001 --purpose implement` | 同上。`TASK-001`が両方の規範文を`addresses`する | `passed_with_warnings`／0。警告1件 |
| `SINGLE-168-03` | `verify REQ-001` | 同上（`SINGLE-168-01`と同じ入力） | `passed_with_warnings`／0。検証対象の`diagnostics`に警告1件 |
| `SINGLE-168-04` | `context REQ-001 --purpose interpret` | `REQ-001`が存在しない`REQ-099`を`requires`し、存在しない`TECH-099`、`ADR-099`を`related`する | `failed`／1。警告2件と強い関係の診断1件 |
| `SINGLE-168-05` | `verify REQ-001` | 同上 | `failed`／1。検証対象の`diagnostics`に3件 |
| `SINGLE-168-06` | `check --full --base HEAD`（対照） | `SINGLE-168-01`と同じ入力 | `passed_with_warnings`／0。警告2件（修正前のCoreも通る） |

`SINGLE-168-01`〜`03`、`06`は`SINGLE-042`のcorpusを基に、`TECH-001`の`related`を`[ADR-001, ADR-099]`にする（`ADR-001`は存在し、`ADR-099`は存在しない。
存在する参照先は警告にならない）。さらに、閉包に入らない`TECH-002`（`REQ-001`と関係を持たない）が存在しない`ADR-098`を`related`する。閉包の外の文書の警告は
`context`と`verify`に加えず、`check --full`は全文書を検査するので加える（`context` §10・`verify` §9の「閉包の文書が宣言する」の範囲）。
`SINGLE-168-04`と`05`は`SINGLE-020`と同じ最小の入力（`REQ-001`1件）に関係を足す。`related`の宣言の順は`TECH-099`、`ADR-099`で、辞書順と異なる
（同じ鍵の診断を宣言の順に並べることを固定する）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、入力の木構造から導出するB）のバイト列の一致を要求する。警告の件数と順序は、準備手順の後の入力の木構造から導く。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .digest_fixtures import LEDGER, reviewed_result as digest_result
from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import setup
from .initial_fixtures import CONFIGS, compare_state, observe

HERE = Path(__file__).resolve().parent
SINGLE = HERE / "single"
COMMIT = "0" * 40
CONFIG_PATH = digest_reference.CONFIG_PATH
TECH_PATH = digest_reference.TECH_PATH
OUTSIDE_PATH = ".spec/technical/TECH-002.md"
TASK_PATH = ".spec/tasks/TASK-001.md"
STRONG = ("requires", "refines", "addresses", "supersedes")
ADVISORY_CODE = "SPEC-RELATION-ADVISORY-MISSING-001"
STRONG_CODE = "SPEC-RELATION-MISSING-001"
ADVISORY_SUMMARY = "関係型relatedの参照先が存在しません"
STRONG_SUMMARY = "強い関係の参照先が存在しません"
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}

OUTSIDE_DOCUMENT = (
    "---\n"
    "id: TECH-002\n"
    "title: 閉包に含まれない方針\n"
    "status: approved\n"
    "relations:\n"
    "  related: [ADR-098]\n"
    "---\n"
    "\n"
    "# TECH-002 閉包に含まれない方針\n"
    "\n"
    "## Context\n"
    "\n"
    "REQ-001と関係を持たない。\n"
)
TASK_DOCUMENT = (
    "---\n"
    "id: TASK-001\n"
    "title: 認証の実装\n"
    "status: open\n"
    "relations:\n"
    "  addresses: [REQ-001:AC-01, REQ-001:AC-02]\n"
    "changes: [src/session.py]\n"
    "---\n"
    "\n"
    "# TASK-001 認証の実装\n"
    "\n"
    "## Objective\n"
    "\n"
    "AC-01とAC-02を実装する。\n"
)
TASK_BODY = TASK_DOCUMENT[TASK_DOCUMENT.index("\n---\n") + 5:].lstrip("\n")
# `SINGLE-020`と同じ最小の入力に、存在しない参照先を足す。`related`の宣言の順は辞書順（ADR-099、TECH-099）と異なる。
MINIMAL_DOCUMENT = DOCUMENT.replace(
    "status: approved\n---\n", "status: approved\nrelations:\n  requires: [REQ-099]\n  related: [TECH-099, ADR-099]\n---\n", 1)

# id: dict(op, argv, corpus, purpose, description)。
#   corpus: `tree`（SINGLE-042の木構造）、`tree-task`（同、TASK-001を加える）、`minimal`（REQ-001だけ）。
CASES = {
    "SINGLE-168-01": dict(op="context", argv=["context", "REQ-001", "--purpose", "interpret"], corpus="tree", purpose="interpret",
                          description="contextの目的interpretの成功の結果にrelatedの参照切れの警告を加える"),
    "SINGLE-168-02": dict(op="context", argv=["context", "REQ-001", "--purpose", "implement"], corpus="tree-task", purpose="implement",
                          description="contextの目的implementの成功の結果にrelatedの参照切れの警告を加える"),
    "SINGLE-168-03": dict(op="verify", argv=["verify", "REQ-001"], corpus="tree", purpose="verify",
                          description="verifyの成功の検証対象のdiagnosticsにrelatedの参照切れの警告を加える"),
    "SINGLE-168-04": dict(op="context", argv=["context", "REQ-001", "--purpose", "interpret"], corpus="minimal", purpose="interpret",
                          description="強い関係の参照切れで失敗するcontextの結果にもrelatedの参照切れの警告を並べる"),
    "SINGLE-168-05": dict(op="verify", argv=["verify", "REQ-001"], corpus="minimal", purpose="verify",
                          description="強い関係の参照切れで失敗するverifyの検証対象にもrelatedの参照切れの警告を並べる"),
    "SINGLE-168-06": dict(op="check", argv=["check", "--full", "--base", "HEAD"], corpus="tree", purpose=None,
                          description="対照: checkは閉包の外の文書も含めrelatedの参照切れの警告を返す"),
}
# 修正前のCoreが`context`と`verify`で警告を返さなかったことを再現する対象の操作。`check`は修正前から返していた。
DEFECT_OPERATIONS = ("context", "verify")


# --- 入力 -------------------------------------------------------------------------------

def reviewed_inputs(identifier):
    corpus = CASES[identifier]["corpus"]
    if corpus == "minimal":
        return {CONFIG_PATH: CONFIGS["SINGLE-001"].encode(), REQ_PATH: MINIMAL_DOCUMENT.encode()}
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    tech = inputs[TECH_PATH].decode()
    if "  related: [ADR-001]\n" not in tech:
        raise ValueError("SINGLE-042の`TECH-001`が想定した`related`を持っていません")
    inputs[TECH_PATH] = tech.replace("  related: [ADR-001]\n", "  related: [ADR-001, ADR-099]\n", 1).encode()
    inputs[OUTSIDE_PATH] = OUTSIDE_DOCUMENT.encode()
    if corpus == "tree-task":
        inputs[TASK_PATH] = TASK_DOCUMENT.encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reviewed_result(identifier)["status"]
    if case["op"] == "check":
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    elif case["op"] == "context":
        setup_plan = {"git": True, "operations": []}
    else:
        # `verify`は、テスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をステージする。
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    return {
        "fixtureId": identifier, "description": case["description"], "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0},
    }


# --- レビュー済みの診断 -----------------------------------------------------------------

def advisory(evidence, path):
    return {"code": ADVISORY_CODE, "severity": "warning", "resultStatus": "passed_with_warnings", "summary": ADVISORY_SUMMARY,
            "source": {"kind": "file", "workspaceId": "root", "path": path, "key": "relations.related"}, "evidence": evidence}


def strong_missing(evidence, path):
    return {"code": STRONG_CODE, "severity": "error", "resultStatus": "failed", "summary": STRONG_SUMMARY,
            "source": {"kind": "file", "workspaceId": "root", "path": path, "key": "relations.requires"}, "evidence": evidence}


def reviewed_diagnostics(identifier):
    """リテラルの期待値。並びは、発生元の`path`、`code`の辞書順と、同じ鍵の診断は宣言の順（結果・診断・終了コード §7）。"""
    case = CASES[identifier]
    if case["corpus"] == "minimal":
        # 同じ`path`では`code`の辞書順（ADVISORYはMISSINGより前）。`related`の2件は宣言の順（TECH-099、ADR-099）。
        return [advisory("TECH-099", REQ_PATH), advisory("ADR-099", REQ_PATH), strong_missing("REQ-099", REQ_PATH)]
    if case["op"] == "check":
        # 全文書を検査する。`path`の辞書順で`TECH-001`（閉包の文書）、`TECH-002`（閉包の外）。
        return [advisory("ADR-099", TECH_PATH), advisory("ADR-098", OUTSIDE_PATH)]
    # `context`と`verify`は閉包の文書の警告だけを返す。`TECH-002`は閉包に入らない。
    return [advisory("ADR-099", TECH_PATH)]


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def task_material():
    """目的`implement`のハッシュ値の材料のTASK-001（参照計算A）。"""
    return {
        "id": "TASK-001", "workspaceId": "root", "kind": "task", "status": "open", "applicability": "applicable",
        "frontmatter": {
            "id": "TASK-001", "title": "認証の実装", "status": "open",
            "relations": {**digest_reference.EMPTY_RELATIONS, "addresses": list(STATEMENTS)},
            "implements": [], "tests": [], "verify": None, "changes": ["src/session.py"],
        },
        "bodyText": TASK_BODY, "statements": [],
        "strongRelations": [{"relation": "addresses", "target": target} for target in STATEMENTS],
    }


def reviewed_digest_input(identifier):
    """参照計算A。`SINGLE-042`のレビュー済みの材料に、目的、`TECH-001`の`related`、目的`implement`のTASK-001だけを替える。"""
    purpose = CASES[identifier]["purpose"]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["purpose"] = purpose
    # `related`は宣言をそのまま持つ（存在しない参照先も、強い関係と異なり`strongRelations`には入らないだけで`relations`に残る）。
    payload["documents"][1]["frontmatter"]["relations"]["related"] = ["ADR-001", "ADR-099"]
    if purpose != "verify":
        # 目的`implement`と`interpret`はテスト割当てを記録しない（コンテキスト §6）。
        payload["settings"]["verifyTimeouts"] = []
        payload["settings"]["commands"] = []
    if purpose == "implement":
        # 文書は、コードポイント辞書順: REQ-001 < TASK-001 < TECH-001。
        payload["documents"].insert(1, task_material())
    return payload


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_context_success(identifier):
    purpose = CASES[identifier]["purpose"]
    result = copy.deepcopy(digest_result("SINGLE-042", context_digest(identifier)))
    result["status"] = "passed_with_warnings"
    result["purpose"] = purpose
    result["documents"][1]["frontmatter"]["relations"]["related"] = ["ADR-001", "ADR-099"]
    result["diagnostics"] = reviewed_diagnostics(identifier)
    if purpose == "interpret":
        # 目的`interpret`は対象規範文を持たない（関係・トレースモデル §6.4）ので、制約台帳とカバレッジは空である。
        result["constraintLedger"] = {"statements": []}
        result["coverage"] = {"must": dict(EMPTY_BUCKET), "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []}
        return result
    # 目的`implement`: TASK-001が両方の規範文を`addresses`し、テスト対応も両方にあるので、未対応・未テストはなく、ほかの警告は出ない。
    result["resolution"]["documentCount"] = 3
    result["documents"].append({
        "id": "TASK-001", "kind": "task", "status": "open", "role": "work", "path": TASK_PATH, "projection": "full",
        "reachedBy": ["addresses:TASK-001"], "statementRefs": [],
        "frontmatter": {"id": "TASK-001", "title": "認証の実装", "status": "open",
                        "relations": {"addresses": list(STATEMENTS)}, "changes": ["src/session.py"]},
        "bodyText": TASK_BODY, "untrustedText": True})
    result["constraintLedger"] = {"statements": copy.deepcopy(LEDGER)}
    result["coverage"] = {
        "must": {"total": [STATEMENTS[0]], "addressed": [STATEMENTS[0]], "tested": [STATEMENTS[0]], "unaddressed": [], "untested": []},
        "should": {"total": [STATEMENTS[1]], "addressed": [STATEMENTS[1]], "tested": [STATEMENTS[1]], "unaddressed": [], "untested": []},
        "may": dict(EMPTY_BUCKET), "adjacent": []}
    return result


def reviewed_context_failure(identifier):
    """強い関係の参照切れは完全解決を失敗させるので、ハッシュ値を計算せず、空のコンテキスト一式を返す（`SINGLE-166-04`と同じ形）。"""
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": CASES[identifier]["purpose"],
        "workspace": {"id": "root", "path": "."}, "roots": ["REQ-001"], "contextDigest": None, "revision": None,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 1},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": {"must": dict(EMPTY_BUCKET), "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": reviewed_diagnostics(identifier),
    }


def reviewed_verify_success(identifier):
    entry = {"target": "REQ-001", "status": "passed_with_warnings", "contextDigest": context_digest(identifier),
             "statements": list(STATEMENTS), "bindingRefs": ["root::default"], "diagnostics": reviewed_diagnostics(identifier)}
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed_with_warnings", "scope": "selected",
        "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
            "termination": "exit", "cwd": ".", "argv": ["/bin/true", *TEST_PATHS], "tests": list(TEST_PATHS),
            "covers": list(STATEMENTS), "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_verify_failure(identifier):
    """コンテキストを構成できない検証対象は、ハッシュ値、規範文、テスト割当てを持たず、テストを開始しない（`MULTI-038-06`と同じ形）。"""
    entry = {"target": "REQ-001", "status": "failed", "contextDigest": None, "statements": [], "bindingRefs": [],
             "diagnostics": reviewed_diagnostics(identifier)}
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected",
        "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None, "commands": [],
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_check_result(identifier):
    documents = ["REQ-001", "TECH-001", "TECH-002", "ADR-001"]
    return {
        "schemaVersion": "1.0", "operation": "check", "status": "passed_with_warnings",
        "workspace": {"id": "root", "path": "."}, "durationMs": 0, "diagnostics": reviewed_diagnostics(identifier), "scope": "full",
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "checkedDocumentCount": len(documents), "checkedStatementCount": len(STATEMENTS),
    }


def reviewed_result(identifier):
    case = CASES[identifier]
    failure = case["corpus"] == "minimal"
    if case["op"] == "check":
        return reviewed_check_result(identifier)
    if case["op"] == "context":
        return reviewed_context_failure(identifier) if failure else reviewed_context_success(identifier)
    return reviewed_verify_failure(identifier) if failure else reviewed_verify_success(identifier)


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def result_diagnostics(result):
    """結果の木構造に実在する診断の全体（最上位と検証対象）。"""
    return [*result["diagnostics"], *(item for target in result.get("targetResults", []) for item in target["diagnostics"])]


def old_core_result(result):
    """修正前のCoreの出力の再現: `context`と`verify`は、関係の診断からエラーだけを残し、`related`の警告を捨てていた。

    警告が消えれば、成功の結果は警告のない`passed`になる。失敗の結果は強い関係の診断だけを残す。
    """
    old = copy.deepcopy(result)
    if old["operation"] not in DEFECT_OPERATIONS:
        return old

    def keep(items):
        return [item for item in items if item["code"] != ADVISORY_CODE]

    old["diagnostics"] = keep(old["diagnostics"])
    for target in old.get("targetResults", []):
        target["diagnostics"] = keep(target["diagnostics"])
        if target["status"] == "passed_with_warnings" and not target["diagnostics"]:
            target["status"] = "passed"
    if old["status"] == "passed_with_warnings" and not result_diagnostics(old):
        old["status"] = "passed"
    return old


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def reference_scope(documents, identifier):
    """警告を返す範囲の文書ID。`context`と`verify`は閉包の文書、`check --full`は全文書（`check` §3、`context` §10、`verify` §9）。"""
    case = CASES[identifier]
    if case["op"] == "check":
        return sorted(documents)
    if case["corpus"] == "minimal":
        # 単一の文書。強い関係が解決できないので、閉包は起点だけである。
        return ["REQ-001"]
    scope, _ = digest_crosscheck.closure(documents, "REQ-001", case["purpose"])
    return scope


def reference_diagnostics(repository, identifier):
    """入力の木構造から診断を導く。範囲の文書ごとに、`related`と強い関係の宣言を宣言の順に読み、解決できないものを診断にする。"""
    documents = digest_crosscheck.load_documents(repository)
    found = []
    for doc_id in reference_scope(documents, identifier):
        document = documents[doc_id]
        declared = document["frontmatter"].get("relations", {})
        for key in (*STRONG, "related"):
            for target in declared.get(key, []):
                if digest_crosscheck.resolves(documents, target):
                    continue
                found.append(advisory(target, document["path"]) if key == "related" else _strong(key, target, document["path"]))
    # 鍵は発生元の`path`、`code`。同じ鍵は宣言の順（Pythonの整列は安定）。
    return sorted(found, key=lambda item: (item["source"]["path"], item["code"]))


def _strong(key, target, path):
    if key != "requires":
        raise ValueError("この群は`requires`以外の強い関係の参照切れを扱いません")
    return strong_missing(target, path)


def reference_status(diagnostics):
    if any(item["resultStatus"] == "failed" for item in diagnostics):
        return "failed"
    return "passed_with_warnings" if diagnostics else "passed"


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    documents = digest_crosscheck.load_documents(repository)
    derived = reference_diagnostics(repository, identifier)
    if derived != reviewed_diagnostics(identifier):
        raise ValueError("入力から導く診断がレビュー済みの期待値と異なります")
    status = reference_status(derived)
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    # 診断は結果の木構造にちょうど1回だけ現れ、置き場所は操作で決まる（最上位、または検証対象）。
    if case["op"] == "verify":
        if result["diagnostics"] or result["targetResults"][0]["diagnostics"] != derived:
            raise ValueError("`verify`の診断は検証対象の`diagnostics`にだけあります")
    elif result["diagnostics"] != derived:
        raise ValueError("診断は最上位の`diagnostics`にあります")
    if result_diagnostics(result) != derived:
        raise ValueError("診断が結果の木構造に重複しています")
    # 存在する`related`の参照先（ADR-001）は警告にならず、存在しない参照先だけが警告になる。
    if case["corpus"] != "minimal":
        tech = documents["TECH-001"]["frontmatter"]["relations"]
        if tech["related"] != ["ADR-001", "ADR-099"] or "ADR-001" not in documents or "ADR-099" in documents:
            raise ValueError("`TECH-001`は存在する`ADR-001`と存在しない`ADR-099`を`related`する必要があります")
        if "TECH-002" not in documents or "ADR-098" in documents or "REQ-001" in documents["TECH-002"]["frontmatter"].get("relations", {}).get("refines", []):
            raise ValueError("閉包に入らない`TECH-002`は、存在しない`ADR-098`を`related`し、`REQ-001`と強い関係を持たない必要があります")
        if case["op"] != "check" and "TECH-002" in reference_scope(documents, identifier):
            raise ValueError("`TECH-002`は`context`と`verify`の閉包に入ってはいけません")
        if case["op"] == "context" and len(reference_scope(documents, identifier)) != result["resolution"]["documentCount"]:
            raise ValueError("閉包の文書数が結果の`documentCount`と異なります")
    else:
        declared = documents["REQ-001"]["frontmatter"]["relations"]
        if declared["requires"] != ["REQ-099"] or declared["related"] != ["TECH-099", "ADR-099"] or len(documents) != 1:
            raise ValueError("最小の入力は、存在しない参照先だけを宣言する`REQ-001`1件である必要があります")
    # 警告の根拠の再現: 修正前のCoreの再現は、`context`と`verify`の欠陥を持つケースの結果と異なる。`check`は同じ。
    if (old_core_result(result) != result) != (case["op"] in DEFECT_OPERATIONS):
        raise ValueError("修正前のCoreの再現との関係が、種類（欠陥または対照）と一致しません")


def check_digest(identifier, repository, result):
    case = CASES[identifier]
    if case["op"] == "check" or case["corpus"] == "minimal":
        return
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, "REQ-001", case["purpose"]))
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
        with tempfile.TemporaryDirectory(prefix="bitz-related-advisory-") as temporary:
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
    kinds = {"requirement": "reqFrontmatter", "technical": "techFrontmatter", "decision": "adrFrontmatter", "task": "taskFrontmatter"}
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
            with tempfile.TemporaryDirectory(prefix="bitz-related-advisory-") as temporary:
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
                    for document in digest_crosscheck.load_documents(repository).values():
                        Draft202012Validator({"$ref": "#/$defs/" + kinds[document["kind"]],
                                              "$defs": schema["$defs"]}).validate(document["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
