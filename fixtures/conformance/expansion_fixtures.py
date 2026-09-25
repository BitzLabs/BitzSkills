"""共通target展開とadvisory提示を固定するfixture（Core操作は実行しない）。

matrix §6.11の`SINGLE-106-03`、`SINGLE-106-06`〜`07`と§6.12の`SINGLE-107`〜`110`、`113`を扱う。
contextの期待値は4集合（rootDocuments、contextDocuments、targetStatements、adjacentStatements）を
`roots`、`documents[]`、Constraint Ledger、`coverage.adjacent`として完全比較し、同じ起点のverifyは
contextと同じtarget statement集合を返すことを確認する。

Digest材料はreference A（本moduleのliteral）とreference B（digest_crosscheckが入力treeから導出）の
2系統で計算し、byte一致を要求する。根拠は[関係・トレースモデル §6・§7]、[context仕様 §4・§5]、
[verify仕様 §3・§4]である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG = digest_reference.CONFIG
EMPTY = digest_reference.EMPTY_RELATIONS
TEST_BODY = "def test_fixture():\n    assert True\n"

# --- 入力corpus -----------------------------------------------------------------------
# 文書ごとに (path, Frontmatter YAML, Frontmatter値, 本文, 規範文[(ID, text)]) を固定する。
# Frontmatter値はYAMLの審査済み解釈であり、YAML parserから導出しない。


def statement_line(identifier, text):
    return f"- [{identifier}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n"


def requirement(identifier, title, statements, fields=""):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n{fields}---\n"
    body = (f"# {identifier} {title}\n\n## Intent\n\ntarget展開の検査に使う固定要求。\n\n"
            "## Acceptance Criteria\n\n" + "".join(statement_line(*s) for s in statements)
            + "\n## Verification\n\n宣言したtestで確認する。\n")
    return head, body


def technical(identifier, title, statements, fields="", status="approved"):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n{fields}---\n"
    body = (f"# {identifier} {title}\n\n## Context\n\n具体化する技術契約。\n\n"
            "## Contract\n\n" + "".join(statement_line(*s) for s in statements))
    return head, body


def task(identifier, title, status, fields):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n{fields}---\n"
    body = f"# {identifier} {title}\n\n## Objective\n\n対象句を実装する。\n"
    return head, body


def document(path, parts, frontmatter, statements):
    head, body = parts
    return {"path": path, "bytes": (head + "\n" + body).encode(), "frontmatter": frontmatter,
            "body": body, "statements": statements}


ROOT_STATEMENTS = [("REQ-001:AC-01", "入力を検証する"), ("REQ-001:AC-02", "結果を記録する")]
ROOT_TESTS = [{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01", "REQ-001:AC-02"], "command": "default"}]
ROOT_TESTS_YAML = ("tests:\n  - path: tests/test_root.py\n"
                   "    covers: [REQ-001:AC-01, REQ-001:AC-02]\n    command: default\n")


def fm(identifier, title, status="approved", **fields):
    value = {"id": identifier, "title": title, "status": status}
    value.update(fields)
    return value


def corpus_refinement():
    """107・113: REQ-001がREQ-009をrequires、REQ-099をrelated。TECH-002・003が推移的に具体化する。"""
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "展開の起点要求", ROOT_STATEMENTS,
            "relations:\n  requires: [REQ-009]\n  related: [REQ-099]\n" + ROOT_TESTS_YAML),
            fm("REQ-001", "展開の起点要求", relations={"requires": ["REQ-009"], "related": ["REQ-099"]},
               tests=ROOT_TESTS), ROOT_STATEMENTS),
        document(".spec/requirements/REQ-009.md", requirement(
            "REQ-009", "前提要求", [("REQ-009:AC-01", "前提を満たす")]),
            fm("REQ-009", "前提要求"), [("REQ-009:AC-01", "前提を満たす")]),
        document(".spec/requirements/REQ-099.md", requirement(
            "REQ-099", "閲覧用の関連要求", [("REQ-099:AC-01", "関連情報を示す")]),
            fm("REQ-099", "閲覧用の関連要求"), [("REQ-099:AC-01", "関連情報を示す")]),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001:AC-01]\ntests:\n  - path: tests/test_direct.py\n"
            "    covers: [TECH-002:AC-01]\n    command: default\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001:AC-01"]},
               tests=[{"path": "tests/test_direct.py", "covers": ["TECH-002:AC-01"], "command": "default"}]),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/technical/TECH-003.md", technical(
            "TECH-003", "間接の具体化", [("TECH-003:AC-01", "形式違反を拒否する")],
            "relations:\n  refines: [TECH-002:AC-01]\ntests:\n  - path: tests/test_indirect.py\n"
            "    covers: [TECH-003:AC-01]\n    command: default\n"),
            fm("TECH-003", "間接の具体化", relations={"refines": ["TECH-002:AC-01"]},
               tests=[{"path": "tests/test_indirect.py", "covers": ["TECH-003:AC-01"], "command": "default"}]),
            [("TECH-003:AC-01", "形式違反を拒否する")]),
    ]


def corpus_technical():
    """108: 規範文ありTECH-001がTECH-009をrequiresし、TECH-004が1句を具体化する。"""
    root = [("TECH-001:AC-01", "応答形式を固定する"), ("TECH-001:AC-02", "応答時間を記録する")]
    return [
        document(".spec/technical/TECH-001.md", technical(
            "TECH-001", "規範文を持つ技術契約", root,
            "relations:\n  requires: [TECH-009]\ntests:\n  - path: tests/test_contract.py\n"
            "    covers: [TECH-001:AC-01, TECH-001:AC-02]\n    command: default\n"),
            fm("TECH-001", "規範文を持つ技術契約", relations={"requires": ["TECH-009"]},
               tests=[{"path": "tests/test_contract.py", "covers": ["TECH-001:AC-01", "TECH-001:AC-02"],
                       "command": "default"}]), root),
        document(".spec/technical/TECH-004.md", technical(
            "TECH-004", "契約の具体化", [("TECH-004:AC-01", "形式の詳細を定める")],
            "relations:\n  refines: [TECH-001:AC-01]\ntests:\n  - path: tests/test_detail.py\n"
            "    covers: [TECH-004:AC-01]\n    command: default\n"),
            fm("TECH-004", "契約の具体化", relations={"refines": ["TECH-001:AC-01"]},
               tests=[{"path": "tests/test_detail.py", "covers": ["TECH-004:AC-01"], "command": "default"}]),
            [("TECH-004:AC-01", "形式の詳細を定める")]),
        document(".spec/technical/TECH-009.md", technical(
            "TECH-009", "前提技術契約", [("TECH-009:AC-01", "前提形式を定義する")]),
            fm("TECH-009", "前提技術契約"), [("TECH-009:AC-01", "前提形式を定義する")]),
    ]


def corpus_statement():
    """109: AC-01だけを具体化するTECH-002と、target 2句をaddressesするopen TASK-001。"""
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "兄弟句を持つ要求", ROOT_STATEMENTS, ROOT_TESTS_YAML),
            fm("REQ-001", "兄弟句を持つ要求", tests=ROOT_TESTS), ROOT_STATEMENTS),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001:AC-01]\ntests:\n  - path: tests/test_direct.py\n"
            "    covers: [TECH-002:AC-01]\n    command: default\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001:AC-01"]},
               tests=[{"path": "tests/test_direct.py", "covers": ["TECH-002:AC-01"], "command": "default"}]),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "指定句の実装", "open",
            "relations:\n  addresses: [REQ-001:AC-01, TECH-002:AC-01]\nchanges: [src/validate.py]\n"),
            fm("TASK-001", "指定句の実装", "open",
               relations={"addresses": ["REQ-001:AC-01", "TECH-002:AC-01"]}, changes=["src/validate.py"]), []),
    ]


def corpus_task():
    """110: open TASK-001がdone TASK-002をrequiresし、各TASKが別REQの句をaddressesする。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    tests_yaml = "tests:\n  - path: tests/test_root.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "TASKの対象要求", only, tests_yaml),
                 fm("REQ-001", "TASKの対象要求", tests=[{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"],
                                                    "command": "default"}]), only),
        document(".spec/requirements/REQ-009.md", requirement(
            "REQ-009", "先行TASKの対象要求", [("REQ-009:AC-01", "前提を満たす")]),
            fm("REQ-009", "先行TASKの対象要求"), [("REQ-009:AC-01", "前提を満たす")]),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "対象句の実装", "open",
            "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            fm("TASK-001", "対象句の実装", "open",
               relations={"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]}), []),
        document(".spec/tasks/TASK-002.md", task(
            "TASK-002", "先行作業", "done", "relations:\n  addresses: [REQ-009:AC-01]\n"),
            fm("TASK-002", "先行作業", "done", relations={"addresses": ["REQ-009:AC-01"]}), []),
    ]


def corpus_advisory():
    """106-03: approved REQ-001の句を、draftのTECH-005が具体化する。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "advisory提示の起点", only),
                 fm("REQ-001", "advisory提示の起点"), only),
        document(".spec/technical/TECH-005.md", technical(
            "TECH-005", "検討中の具体化", [("TECH-005:AC-01", "候補形式を示す")],
            "relations:\n  refines: [REQ-001:AC-01]\n", status="draft"),
            fm("TECH-005", "検討中の具体化", "draft", relations={"refines": ["REQ-001:AC-01"]}),
            [("TECH-005:AC-01", "候補形式を示す")]),
    ]


def corpus_distance():
    """106-06: REQ-001がTECH-010をrequiresし、TECH-010がREQ-020をrequires。距離2以上の
    requirementとconstraintは、距離だけを理由にrefinementのようにnormativeへ落とさず、roleに基づき
    fullで提示する（context仕様 §5、ADR-014 Decision 4・5）。"""
    deep_statements = [("REQ-020:AC-01", "秘密鍵を保持しない")]
    tech_head, tech_body = technical("TECH-010", "距離1の前提契約", [], "relations:\n  requires: [REQ-020]\n")
    # 規範文0件のTECHは末尾に空sectionだけの空行を残さない（Digest材料の末尾正規化と一致させる）。
    tech_body = tech_body.rstrip("\n") + "\n"
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "距離2依存の起点要求", ROOT_STATEMENTS,
            "relations:\n  requires: [TECH-010]\n" + ROOT_TESTS_YAML),
            fm("REQ-001", "距離2依存の起点要求", relations={"requires": ["TECH-010"]}, tests=ROOT_TESTS),
            ROOT_STATEMENTS),
        document(".spec/technical/TECH-010.md", (tech_head, tech_body),
            fm("TECH-010", "距離1の前提契約", relations={"requires": ["REQ-020"]}), []),
        document(".spec/requirements/REQ-020.md", requirement(
            "REQ-020", "距離2の前提要求", deep_statements),
            fm("REQ-020", "距離2の前提要求"), deep_statements),
    ]


# ID: (corpus, argv, 期待status, 説明)
CASES = {
    "SINGLE-106-03": (corpus_advisory, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "interpretでdraft refinementをadvisoryのreference projectionで提示する"),
    "SINGLE-107-01": (corpus_refinement, ["context", "REQ-001", "--purpose", "verify", "--format", "json"],
                      "REQ起点のrefinementはtarget、requires先はContextだけにする"),
    "SINGLE-107-02": (corpus_refinement, ["verify", "REQ-001", "--format", "json"],
                      "REQ起点のverifyはcontextと同じtarget statement集合を使う"),
    "SINGLE-108-01": (corpus_technical, ["context", "TECH-001", "--purpose", "verify", "--format", "json"],
                      "規範文ありTECH起点の4集合を完全比較する"),
    "SINGLE-108-02": (corpus_technical, ["verify", "TECH-001", "--format", "json"],
                      "規範文ありTECH起点のverifyはcontextと同じtarget statement集合を使う"),
    "SINGLE-109": (corpus_statement, ["context", "REQ-001:AC-01", "--purpose", "implement", "--format", "json"],
                   "statement起点の指定句とrefinementをtarget、兄弟句をadjacentにする"),
    "SINGLE-110": (corpus_task, ["context", "TASK-001", "--purpose", "verify", "--format", "json"],
                   "verifyの起点TASKはaddresses先だけをtargetとし、requires先TASKを含めない"),
    "SINGLE-113": (corpus_refinement, ["verify", "REQ-001:AC-01", "REQ-001", "REQ-001:AC-01", "--format", "json"],
                   "文書IDと同文書のstatement IDを重複指定してもtargetとbindingを重複排除する"),
    "SINGLE-106-06": (corpus_distance, ["context", "REQ-001", "--purpose", "verify", "--format", "json"],
                      "距離2以上のrequirementとconstraintをroleに基づきfullで提示する"),
    "SINGLE-106-07": (corpus_refinement, ["context", "REQ-001", "--purpose", "verify",
                                          "--detail", "compact", "--format", "json"],
                      "compact detailは全文書をreference提示にしContext Digestを変えない"),
}
# contextの期待展開（審査済み）。verifyは同じ起点のcontext fixtureの集合を参照する。
EXPANSIONS = {
    "SINGLE-106-03": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-005", "advisory", "reference", ["refines:TECH-005"])],
                      "ledger": [], "tested": [], "addressed": [], "adjacent": [], "advisory": ["TECH-005"]},
    "SINGLE-107-01": {"purpose": "verify", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("REQ-009", "requirement", "full", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                    ("TECH-003", "refinement", "normative", ["refines:TECH-003"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
    "SINGLE-108-01": {"purpose": "verify", "root": "TECH-001",
                      "documents": [("TECH-001", "root", "full", ["root"]),
                                    ("TECH-004", "refinement", "full", ["refines:TECH-004"]),
                                    ("TECH-009", "constraint", "full", ["requires:TECH-001"])],
                      "ledger": ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"],
                      "tested": ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
    "SINGLE-109": {"purpose": "implement", "root": "REQ-001:AC-01",
                   "documents": [("REQ-001", "root", "full", ["root"]),
                                 ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                 ("TASK-001", "work", "full", ["addresses:TASK-001"])],
                   "ledger": ["REQ-001:AC-01", "TECH-002:AC-01"],
                   "tested": ["REQ-001:AC-01", "TECH-002:AC-01"],
                   "addressed": ["REQ-001:AC-01", "TECH-002:AC-01"], "adjacent": ["REQ-001:AC-02"],
                   "advisory": []},
    "SINGLE-110": {"purpose": "verify", "root": "TASK-001",
                   "documents": [("TASK-001", "root", "full", ["root"]),
                                 ("REQ-001", "requirement", "full", ["addresses:TASK-001"])],
                   "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"],
                   "addressed": ["REQ-001:AC-01"], "adjacent": [], "advisory": []},
    # 113の文書起点targetは107-01、statement起点targetは次の展開を使う。
    "REQ-001:AC-01": {"purpose": "verify", "root": "REQ-001:AC-01",
                      "ledger": ["REQ-001:AC-01", "TECH-002:AC-01", "TECH-003:AC-01"], "advisory": []},
    "SINGLE-106-06": {"purpose": "verify", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "constraint", "full", ["requires:REQ-001"]),
                                    ("REQ-020", "requirement", "full", ["requires:TECH-010"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02"],
                      "addressed": [], "adjacent": [], "advisory": []},
    # compact detailはprojectionをreferenceへ統一するだけで、107-01と同じcorpus・purpose・
    # 閉包を使うのでContext Digestは変わらない（context仕様 §5・§6）。
    "SINGLE-106-07": {"purpose": "verify", "root": "REQ-001", "detail": "compact",
                      "documents": [("REQ-001", "root", "reference", ["root"]),
                                    ("REQ-009", "requirement", "reference", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "reference", ["refines:TECH-002"]),
                                    ("TECH-003", "refinement", "reference", ["refines:TECH-003"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
}
KIND = {"REQ": "requirement", "TECH": "technical", "ADR": "decision", "TASK": "task"}


def documents(identifier):
    return {entry["path"]: entry for entry in CASES[identifier][0]()}


def by_id(identifier):
    return {entry["frontmatter"]["id"]: entry for entry in documents(identifier).values()}


def reviewed_inputs(identifier):
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode(),
              **{path: entry["bytes"] for path, entry in documents(identifier).items()}}
    for entry in documents(identifier).values():
        for test in entry["frontmatter"].get("tests", []):
            inputs[test["path"]] = TEST_BODY.encode()
    return inputs


def reviewed_manifest(identifier):
    _, argv, description = CASES[identifier]
    operation = argv[0]
    # verifyは設定がindexに無いと起動前に停止するため、commitせずstageする。
    operations = [{"op": "stage", "paths": ["."]}] if operation == "verify" else []
    return {"fixtureId": identifier, "description": description,
            "setup": {"git": True, "operations": operations},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
            "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                       "resultFile": f"expected/{operation}.json", "reportFileCount": 0}}


# --- reference A: Digest材料のliteral ----------------------------------------------


def semantic(statement_id, text):
    return {"id": statement_id, "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
            "modality": "MUST", "reason": None, "operation": {"kind": "CONSTRAINT", "text": text},
            "extensions": []}


def digest_document(entry, advisory):
    value = entry["frontmatter"]
    identifier = value["id"]
    relations = {**EMPTY, **value.get("relations", {})}
    strong = sorted((key, target) for key in ("addresses", "refines", "requires", "supersedes")
                    for target in relations[key])
    return {
        "id": identifier, "workspaceId": "root", "kind": KIND[identifier.split("-")[0]],
        "status": value["status"], "applicability": "advisory" if identifier in advisory else "applicable",
        "frontmatter": {"id": identifier, "title": value["title"], "status": value["status"],
                        "relations": relations, "implements": [], "tests": value.get("tests", []),
                        "verify": None, "changes": value.get("changes", [])},
        "bodyText": entry["body"],
        "statements": [semantic(*s) for s in sorted(entry["statements"])],
        "strongRelations": [{"relation": key, "target": target} for key, target in strong],
    }


def expansion(identifier, target=None):
    """verifyは同じ起点のcontext展開を使う。113だけはtargetごとに展開を選ぶ。"""
    if identifier == "SINGLE-113":
        return EXPANSIONS["SINGLE-107-01" if target == "REQ-001" else target]
    if identifier in {"SINGLE-107-02", "SINGLE-108-02"}:
        return EXPANSIONS[identifier.replace("-02", "-01")]
    return EXPANSIONS[identifier]


def context_documents(identifier, target=None):
    plan = expansion(identifier, target)
    if "documents" in plan:
        return [name for name, _, _, _ in plan["documents"]]
    # statement起点は所有文書・到達文書が文書起点と同じである。
    return context_documents("SINGLE-107-01")


def reviewed_digest_input(identifier, target=None):
    plan = expansion(identifier, target)
    corpus = by_id(identifier)
    verify = plan["purpose"] == "verify"
    commands = [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": plan["purpose"], "requestWorkspaceId": "root", "roots": [plan["root"]],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [digest_document(corpus[name], plan["advisory"])
                      for name in sorted(context_documents(identifier, target))],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}] if verify else [],
            "commands": commands if verify else [],
        },
    }


def context_digest(identifier, target=None):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier, target)))


# --- 完全期待結果 ---------------------------------------------------------------------


def bundle_frontmatter(value):
    """context仕様 §5: 許可fieldを正規化し、空のrelation keyと空配列を省略する。"""
    result = {"id": value["id"], "title": value["title"], "status": value["status"]}
    relations = {key: targets for key, targets in value.get("relations", {}).items() if targets}
    if relations:
        result["relations"] = relations
    for key in ("implements", "tests", "changes"):
        if value.get(key):
            result[key] = value[key]
    return result


def bundle_document(identifier, name, role, projection, reached):
    entry = by_id(identifier)[name]
    value = {"id": name, "kind": KIND[name.split("-")[0]], "status": entry["frontmatter"]["status"],
             "role": role, "path": entry["path"], "projection": projection, "reachedBy": reached}
    if projection == "reference":
        value["expandable"] = True
    else:
        value["statementRefs"] = [statement_id for statement_id, _ in entry["statements"]]
    if projection == "full":
        value["frontmatter"] = bundle_frontmatter(entry["frontmatter"])
        value["bodyText"] = entry["body"]
    value["untrustedText"] = True
    return value


def reviewed_context(identifier):
    plan = EXPANSIONS[identifier]
    corpus = by_id(identifier)
    roles = {name: role for name, role, _, _ in plan["documents"]}
    texts = {sid: text for entry in corpus.values() for sid, text in entry["statements"]}
    ledger = [{"id": sid, "documentId": sid.split(":")[0], "documentRole": roles[sid.split(":")[0]],
               "modality": "MUST", "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
               "operation": {"kind": "CONSTRAINT", "text": texts[sid]}} for sid in plan["ledger"]]
    must = {"total": list(plan["ledger"]), "addressed": list(plan["addressed"]), "tested": list(plan["tested"]),
            "unaddressed": [s for s in plan["ledger"] if s not in plan["addressed"]],
            "untested": [s for s in plan["ledger"] if s not in plan["tested"]]}
    empty = {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": plan["purpose"],
        "workspace": {"id": "root", "path": "."}, "roots": [plan["root"]],
        "contextDigest": context_digest(identifier), "revision": None,
        "resolution": {"complete": True, "documentCount": len(plan["documents"]), "unresolvedStrongRelations": 0},
        "projection": {"detail": plan.get("detail", "standard"), "expanded": []},
        "documents": [bundle_document(identifier, *row) for row in plan["documents"]],
        "constraintLedger": {"statements": ledger},
        "coverage": {"must": must, "should": dict(empty), "may": dict(empty), "adjacent": list(plan["adjacent"])},
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_verify(identifier):
    argv = CASES[identifier][1]
    targets = sorted({value for value in argv[1:] if not value.startswith("--") and value != "json"})
    corpus = by_id(identifier)
    results, tests, covers = [], set(), set()
    for target in targets:
        statements = expansion(identifier, target)["ledger"]
        results.append({"target": target, "status": "passed", "contextDigest": context_digest(identifier, target),
                        "statements": list(statements), "bindingRefs": ["root::default"], "diagnostics": []})
        for entry in corpus.values():
            for test in entry["frontmatter"].get("tests", []):
                if set(test["covers"]) & set(statements):
                    tests.add(test["path"])
                    covers.update(set(test["covers"]) & set(statements))
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."}, "targetResults": results, "revision": None,
        "commands": [{"bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
                      "termination": "exit", "cwd": ".", "argv": ["/bin/true", *sorted(tests)],
                      "tests": sorted(tests), "covers": sorted(covers), "exitCode": 0, "timeoutSeconds": 300,
                      "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False,
                      "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier):
    return reviewed_context(identifier) if CASES[identifier][1][0] == "context" else reviewed_verify(identifier)


# --- 検証 ---------------------------------------------------------------------------

LITERAL_SETS = {
    # 4集合をcontext結果から独立に読み戻す。targets/cases.jsonの対応vectorと同じ内容である。
    "SINGLE-107-01": (["REQ-001"], ["REQ-001", "REQ-009", "TECH-002", "TECH-003"],
                      ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"], []),
    "SINGLE-108-01": (["TECH-001"], ["TECH-001", "TECH-004", "TECH-009"],
                      ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"], []),
    "SINGLE-109": (["REQ-001"], ["REQ-001", "TECH-002", "TASK-001"],
                   ["REQ-001:AC-01", "TECH-002:AC-01"], ["REQ-001:AC-02"]),
    "SINGLE-110": (["TASK-001"], ["TASK-001", "REQ-001"], ["REQ-001:AC-01"], []),
}


def four_sets(result):
    roots = sorted({root.split(":")[0] for root in result["roots"]})
    return (roots, [d["id"] for d in result["documents"]],
            [s["id"] for s in result["constraintLedger"]["statements"]], result["coverage"]["adjacent"])


def check_contract(identifier, result, root):
    """完全比較とは別に、裁定済みの展開規則を結果から直接確かめる。"""
    if identifier in LITERAL_SETS and four_sets(result) != LITERAL_SETS[identifier]:
        raise ValueError("4集合が審査済みの展開と異なります")
    if result["operation"] == "context":
        for entry in result["documents"]:
            if entry["role"] == "advisory" and entry["projection"] != "reference":
                raise ValueError("advisory文書はreferenceで提示する必要があります")
        if identifier == "SINGLE-106-03":
            if [d["projection"] for d in result["documents"]] != ["full", "reference"]:
                raise ValueError("106-03はreference projectionを1件含む必要があります")
            if result["constraintLedger"]["statements"]:
                raise ValueError("advisory文書の規範文をLedgerへ入れてはいけません")
        if identifier == "SINGLE-110" and any(d["id"] in {"TASK-002", "REQ-009"} for d in result["documents"]):
            raise ValueError("verifyの起点TASKのrequires先とそのaddresses先をContextへ含めてはいけません")
        if identifier == "SINGLE-107-01" and "REQ-099" in [d["id"] for d in result["documents"]]:
            raise ValueError("related先をContextへ追加してはいけません")
        if identifier == "SINGLE-106-06":
            lookup = {d["id"]: d for d in result["documents"]}
            for name, role in (("TECH-010", "constraint"), ("REQ-020", "requirement")):
                if lookup[name]["role"] != role or lookup[name]["projection"] != "full":
                    raise ValueError("距離2以上のrequirement/constraintはfull projectionである必要があります")
            if "秘密鍵を保持しない" not in lookup["REQ-020"]["bodyText"]:
                raise ValueError("距離2の規範文のMUST本文がBundleへ現れる必要があります")
        if identifier == "SINGLE-106-07":
            if result["projection"]["detail"] != "compact":
                raise ValueError("106-07はdetail=compactを返す必要があります")
            if any(d["projection"] != "reference" for d in result["documents"]):
                raise ValueError("compact detailは全文書をreference提示にする必要があります")
            expected = json.loads((root / "single/SINGLE-107-01/expected/context.json").read_text())
            if result["contextDigest"] != expected["contextDigest"]:
                raise ValueError("compact detailはContext Digestを変えてはいけません")
        return
    for target in result["targetResults"]:
        source = "SINGLE-113" if identifier == "SINGLE-113" else identifier.replace("-02", "-01")
        expected = (json.loads((root / "single/SINGLE-107-01/expected/context.json").read_text())
                    if identifier == "SINGLE-113" and target["target"] == "REQ-001"
                    else json.loads((root / f"single/{source}/expected/context.json").read_text())
                    if identifier != "SINGLE-113" else None)
        if expected is not None:
            if target["statements"] != [s["id"] for s in expected["constraintLedger"]["statements"]]:
                raise ValueError("verifyのtarget statementが同じ起点のcontextと異なります")
            if target["contextDigest"] != expected["contextDigest"]:
                raise ValueError("verifyのContext Digestが同じ起点のcontextと異なります")
    if identifier == "SINGLE-113":
        if [t["target"] for t in result["targetResults"]] != ["REQ-001", "REQ-001:AC-01"]:
            raise ValueError("113は重複排除した2 targetを辞書順で返す必要があります")
        if len(result["commands"]) != 1 or len(set(result["commands"][0]["tests"])) != len(result["commands"][0]["tests"]):
            raise ValueError("113は共有bindingを1回だけ、test pathを重複なしで実行する必要があります")


def check_git_state(identifier, repository):
    listed = set(git(repository, "ls-files", "-z").decode().split("\0")[:-1])
    expected = set(reviewed_inputs(identifier)) if CASES[identifier][1][0] == "verify" else set()
    if listed != expected:
        raise ValueError("indexのpathが審査済みsetupと異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        return
    raise ValueError("target展開fixtureはcommitを持ってはいけません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    kinds = {"REQ": "reqFrontmatter", "TECH": "techFrontmatter", "TASK": "taskFrontmatter"}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / manifest["expect"]["resultFile"]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            check_contract(identifier, result, root)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            for path, entry in documents(identifier).items():
                parsed, _ = digest_crosscheck.split_document(inputs[path].decode())
                if parsed != json.loads(json.dumps(entry["frontmatter"])):
                    raise ValueError(f"{path}のFrontmatter値が審査済み解釈と異なります")
                kind = kinds[entry["frontmatter"]["id"].split("-")[0]]
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(parsed)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            argv = manifest["invocation"]["argv"]
            targets = ([argv[1]] if argv[0] == "context"
                       else sorted({v for v in argv[1:] if not v.startswith("--") and v != "json"}))
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-expansion-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_git_state(identifier, repository)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    for target in targets:
                        purpose = expansion(identifier, target)["purpose"]
                        derived = digest_crosscheck.canonical_bytes(
                            digest_crosscheck.build(repository, root=target, purpose=purpose))
                        if derived != digest_reference.canonical_bytes(reviewed_digest_input(identifier, target)):
                            raise ValueError(f"{target}: reference AとBのCanonical JSONが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
