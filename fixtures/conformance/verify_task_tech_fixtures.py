"""TASKが規範文のないTECHを`addresses`するとき、`verify`がそのTECHの文書単位のテスト割当てを実行することを固定する（Coreの公開操作は実行しない）。

`SINGLE-156`は、TASK-001（`open`）が規範文のないTECH-001だけを`addresses`する。TECH-001は文書単位の`tests`（`covers: [TECH-001]`）を持つ。
`verify`の対象は、TASKが`addresses`する先であり（`verify` §3、関係・トレースモデル §6.4の規則3）、規範文のないTECHは規範文を足さず、
文書単位の`tests`を使う（`verify` §3、文書単位のテスト割当ての定義）。そのため`statements`は`[]`でも、`bindingRefs`は`root::default`の1件で、
`commands`はそのTECHのテストを実行する1件になる。TECHを起点にした`SINGLE-066`と同じ文書単位のテスト割当てを、TASKの起点で固定する。

`SINGLE-157`は、TASK-001が規範文`REQ-001:AC-01`と規範文のないTECH-001を`addresses`する。2つの対象のテスト対応は同じコマンド名`default`なので、
テスト割当ては`root::default`の1件にまとまり（`verify` §4の5.）、そのテストのパスはREQ-001のテストとTECH-001のテストの両方である。
規範文のないTECHが規範文の集合を増やさないこと（`statements`は`REQ-001:AC-01`だけ）も固定する。

`MULTI-028`は、メンバー`web`のTASK-001が、メンバー`api`の規範文のないTECH-020を`addresses`する。TECH-020のテストと、そのコマンド`backend`は
`api`の設定が所有する。修飾IDの`api::TECH-020`を、`:`の有無ではなく索引で文書と判定することも固定する。テスト割当ては所有ワークスペースの
`api::backend`で、`covers`は修飾IDで返す（`verify` §8）。

期待値の根拠は規範文と、このモジュールの参照計算だけである。参照計算は2つある。入力の木構造から、TASKの`addresses`の先とそのテスト対応を読んで
`statements`、`bindingRefs`、`commands`を導く`reference_plan`と、ハッシュ値の材料を導く参照計算A（このモジュールのリテラル）・B
（`digest_crosscheck`と`multi_crosscheck`が入力の木構造から導出）である。Coreの出力は期待値の根拠にしない。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference, multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CONFIG_PATH = digest_reference.CONFIG_PATH
EMPTY_RELATIONS = digest_reference.EMPTY_RELATIONS
KIND_SCHEMA = {"requirement": "reqFrontmatter", "technical": "techFrontmatter",
               "decision": "adrFrontmatter", "task": "taskFrontmatter"}
SINGLE = ("SINGLE-156", "SINGLE-157")
MULTI = ("MULTI-028",)
CASES = (*SINGLE, *MULTI)
DESCRIPTIONS = {
    "SINGLE-156": "TASKが規範文のないTECHをaddressesするとき、verifyがそのTECHの文書単位のテストを実行する",
    "SINGLE-157": "TASKがREQの規範文と規範文のないTECHをaddressesするとき、verifyが両方のテストを1つのテスト割当てで実行する",
    "MULTI-028": "TASKが他のメンバーの規範文のないTECHをaddressesするとき、verifyがそのメンバーの文書単位のテストを実行する",
}

# --- 単一ワークスペースの入力 ----------------------------------------------------------------

TASK_PATH = ".spec/tasks/TASK-001.md"
TECH_PATH = ".spec/technical/TECH-001.md"
REQ_PATH = ".spec/requirements/REQ-001.md"
TECH_TEST_PATH = "tests/test_tech.py"
REQ_TEST_PATH = "tests/test_req.py"
STATEMENT = "REQ-001:AC-01"
TASK_TITLE = "技術契約の実装作業"
TECH_TITLE = "文書単位のテストで確認する技術契約"
REQ_TITLE = "認証の基準"
TASK_BODY = (f"# TASK-001 {TASK_TITLE}\n\n## Objective\n\n"
             "規範文を持たないTECH-001の方針を実装する。確認は文書単位のテストで行う。\n")
TECH_BODY = (f"# TECH-001 {TECH_TITLE}\n\n## Context\n\n"
             "規範文を持たず、文書単位のテストだけを宣言する。\n")
REQ_BODY = (f"# REQ-001 {REQ_TITLE}\n\n## Intent\n\n認証の規範を定める。\n\n"
            "## Acceptance Criteria\n\n"
            f"- [{STATEMENT}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
            "## Verification\n\ntests/test_req.pyで確認する。\n")


def task_document(addresses):
    head = (f"---\nid: TASK-001\ntitle: {TASK_TITLE}\nstatus: open\n"
            f"relations:\n  addresses: [{', '.join(addresses)}]\n---\n")
    return head + "\n" + TASK_BODY


TECH_DOCUMENT = (
    f"---\nid: TECH-001\ntitle: {TECH_TITLE}\nstatus: approved\n"
    f"tests:\n  - path: {TECH_TEST_PATH}\n    covers: [TECH-001]\n    command: default\n---\n"
    "\n" + TECH_BODY)
REQ_DOCUMENT = (
    f"---\nid: REQ-001\ntitle: {REQ_TITLE}\nstatus: approved\n"
    f"tests:\n  - path: {REQ_TEST_PATH}\n    covers: [{STATEMENT}]\n    command: default\n---\n"
    "\n" + REQ_BODY)


def single_inputs(identifier):
    files = {
        CONFIG_PATH: digest_reference.CONFIG.encode(),
        TECH_PATH: TECH_DOCUMENT.encode(),
        TECH_TEST_PATH: b"def test_tech():\n    assert True\n",
    }
    if identifier == "SINGLE-157":
        files[REQ_PATH] = REQ_DOCUMENT.encode()
        files[REQ_TEST_PATH] = b"def test_req():\n    assert True\n"
        files[TASK_PATH] = task_document([STATEMENT, "TECH-001"]).encode()
    else:
        files[TASK_PATH] = task_document(["TECH-001"]).encode()
    return files


# --- 複合ワークスペースの入力 ----------------------------------------------------------------

M_TASK_PATH = "apps/web/.spec/tasks/TASK-001.md"
M_TECH_PATH = "services/api/.spec/technical/TECH-020.md"
M_TEST_PATH = "services/api/tests/test_audit.py"
M_TASK_TITLE = "API側の監査方針の実装作業"
M_TECH_TITLE = "API側の文書単位の監査方針"
M_TASK_BODY = (f"# TASK-001 {M_TASK_TITLE}\n\n## Objective\n\n"
               "規範文を持たないapiのTECH-020の方針を実装する。確認はapiの文書単位のテストで行う。\n")
M_TECH_BODY = (f"# TECH-020 {M_TECH_TITLE}\n\n## Context\n\n"
               "規範文を持たず、文書単位のテストだけを宣言する。\n")
M_TASK_DOCUMENT = (f"---\nid: TASK-001\ntitle: {M_TASK_TITLE}\nstatus: open\n"
                   "relations:\n  addresses: [api::TECH-020]\n---\n\n" + M_TASK_BODY)
M_TECH_DOCUMENT = (
    f"---\nid: TECH-020\ntitle: {M_TECH_TITLE}\nstatus: approved\n"
    "tests:\n  - path: tests/test_audit.py\n    covers: [TECH-020]\n    command: backend\n---\n"
    "\n" + M_TECH_BODY)


def multi_inputs():
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
            [("web", "apps/web"), ("api", "services/api")]).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.member_config("api", "backend").encode(),
        M_TASK_PATH: M_TASK_DOCUMENT.encode(),
        M_TECH_PATH: M_TECH_DOCUMENT.encode(),
        M_TEST_PATH: b"def test_audit():\n    assert True\n",
    }


def reviewed_inputs(identifier):
    return multi_inputs() if identifier in MULTI else single_inputs(identifier)


def reviewed_manifest(identifier):
    if identifier in MULTI:
        setup_entry = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
        argv = ["verify", "web::TASK-001", "--format", "json"]
    else:
        setup_entry = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
        argv = ["verify", "TASK-001", "--format", "json"]
    return {
        "fixtureId": identifier, "description": DESCRIPTIONS[identifier], "setup": setup_entry,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


# --- ハッシュ値の材料（参照計算A） --------------------------------------------------------------

def _document(identifier, workspace, kind, status, title, relations, tests, body, statements, strong, qualified):
    name = f"{workspace}::{identifier}" if qualified else identifier
    return {
        "id": name, "workspaceId": workspace, "kind": kind, "status": status, "applicability": "applicable",
        "frontmatter": {"id": name, "title": title, "status": status,
                        "relations": {**EMPTY_RELATIONS, **relations}, "implements": [], "tests": tests,
                        "verify": None, "changes": []},
        "bodyText": body, "statements": statements,
        "strongRelations": [{"relation": key, "target": target} for key, target in strong],
    }


def reviewed_digest_input(identifier):
    if identifier in MULTI:
        return {
            "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
            "purpose": "verify", "requestWorkspaceId": "web", "roots": ["web::TASK-001"],
            # 起点ワークスペースが先頭、以降はID辞書順。到達しないルートワークスペース`platform`は材料へ入れない。
            "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
            "documents": [
                _document("TECH-020", "api", "technical", "approved", M_TECH_TITLE, {},
                          [{"path": "tests/test_audit.py", "covers": ["api::TECH-020"], "command": "backend"}],
                          M_TECH_BODY, [], [], True),
                _document("TASK-001", "web", "task", "open", M_TASK_TITLE, {"addresses": ["api::TECH-020"]},
                          [], M_TASK_BODY, [], [("addresses", "api::TECH-020")], True),
            ],
            "crossWorkspaceEdges": [{"relation": "addresses", "source": "web::TASK-001", "target": "api::TECH-020"}],
            "settings": {
                "workspaces": [{"id": "api", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
                               {"id": "web", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
                "context": {"maxDocuments": 20, "maxBytes": 131072},
                # `web`はテスト対応を持つ文書を閉包に持たないので、タイムアウトもコマンドも収録しない。
                "verifyTimeouts": [{"workspaceId": "api", "timeoutSeconds": 300}],
                "commands": [{"workspaceId": "api", "name": "backend", "argv": ["/bin/true", "{tests}"], "cwd": "."}],
            },
        }
    with_req = identifier == "SINGLE-157"
    addresses = [STATEMENT, "TECH-001"] if with_req else ["TECH-001"]
    documents = []
    if with_req:
        documents.append(_document(
            "REQ-001", "root", "requirement", "approved", REQ_TITLE, {},
            [{"path": REQ_TEST_PATH, "covers": [STATEMENT], "command": "default"}], REQ_BODY,
            [{"id": STATEMENT, "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
              "modality": "MUST", "reason": None,
              "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}, "extensions": []}],
            [], False))
    documents.append(_document("TASK-001", "root", "task", "open", TASK_TITLE, {"addresses": addresses}, [],
                               TASK_BODY, [], [("addresses", target) for target in addresses], False))
    documents.append(_document(
        "TECH-001", "root", "technical", "approved", TECH_TITLE, {},
        [{"path": TECH_TEST_PATH, "covers": ["TECH-001"], "command": "default"}], TECH_BODY, [], [], False))
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": "root", "roots": ["TASK-001"],
        "workspaces": [{"id": "root", "path": "."}],
        # `documents[]`はコードポイント辞書順: REQ-001 < TASK-001 < TECH-001。
        "documents": documents,
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}],
            "commands": [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}],
        },
    }


def literal_bytes(identifier):
    return digest_reference.canonical_bytes(reviewed_digest_input(identifier))


def literal_digest(identifier):
    return digest_reference.digest(literal_bytes(identifier))


# --- 期待する結果 --------------------------------------------------------------------------

def reviewed_result(identifier, context_digest):
    multi = identifier in MULTI
    workspace = {"id": "web", "path": "apps/web"} if multi else {"id": "root", "path": "."}
    if multi:
        target, statements, binding = "web::TASK-001", [], "api::backend"
        owner, name, tests, covers = "api", "backend", ["tests/test_audit.py"], ["api::TECH-020"]
    elif identifier == "SINGLE-157":
        target, statements, binding = "TASK-001", [STATEMENT], "root::default"
        owner, name, tests, covers = "root", "default", [REQ_TEST_PATH, TECH_TEST_PATH], [STATEMENT, "TECH-001"]
    else:
        target, statements, binding = "TASK-001", [], "root::default"
        owner, name, tests, covers = "root", "default", [TECH_TEST_PATH], ["TECH-001"]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": workspace,
        "targetResults": [{"target": target, "status": "passed", "contextDigest": context_digest,
                           "statements": statements, "bindingRefs": [binding], "diagnostics": []}],
        "revision": {"commit": COMMIT, "dirty": False} if multi else None,
        "commands": [{
            "bindingId": binding, "workspaceId": owner, "name": name, "status": "passed",
            "termination": "exit", "cwd": ".", "argv": ["/bin/true", *tests], "tests": tests,
            "covers": covers, "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False,
            "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


# --- 入力の木構造からの参照計算 ----------------------------------------------------------------

def load_corpus(repository, multi):
    """(文書の索引, ワークスペースの設定, 修飾の規則)を返す。単一ワークスペースのIDは修飾しない。"""
    if multi:
        _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
        return documents, {name: entry["config"] for name, entry in workspaces.items()}, multi_crosscheck.qualify
    documents = {}
    for identifier, document in digest_crosscheck.load_documents(repository).items():
        documents[identifier] = {"workspaceId": "root", "kind": document["kind"],
                                 "frontmatter": document["frontmatter"], "body": document["body"]}
    config = digest_crosscheck.read_yaml((repository / CONFIG_PATH).read_text(encoding="utf-8"))
    return documents, {"root": config}, lambda workspace, reference: reference


def reference_plan(repository, root, multi):
    """TASKの`addresses`の先から、`statements`、`bindingRefs`、`commands`の実行計画を導く（`verify` §3・§4、関係・トレースモデル §6.4）。

    先の規範文は対象規範文に加える。規範文のない文書（TECH）の先は規範文を足さず、その文書の`tests`をすべて使う。規範文の先は、
    その規範文を`covers`するテスト対応だけを使う。コマンド名は`tests[].command`、なければ文書の`verify`の順で解決し、
    `(workspaceId, commandName)`ごとにテストのパスと`covers`をまとめる。
    """
    documents, configs, qualify = load_corpus(repository, multi)

    def document_of(reference):
        workspace, _, rest = reference.partition("::") if multi else ("root", "", reference)
        return f"{workspace}::{rest.split(':')[0]}" if multi else rest.split(":")[0]

    owned = {}
    for identifier, document in documents.items():
        for statement in digest_crosscheck.read_statements(document["body"]):
            owned.setdefault(identifier, []).append(qualify(document["workspaceId"], statement["id"]))
    known = {statement for items in owned.values() for statement in items}
    task = documents[root]
    targets = sorted(qualify(task["workspaceId"], target)
                     for target in task["frontmatter"].get("relations", {}).get("addresses", []))
    statements, needs = [], {}
    for target in targets:
        document_id = document_of(target)
        document = documents[document_id]
        if target in known:
            statements.append(target)
        elif target != document_id or owned.get(document_id):
            raise ValueError("`addresses`の先は、規範文か、規範文を持たない文書でなければなりません")
        for entry in document["frontmatter"].get("tests", []):
            covers = sorted({qualify(document["workspaceId"], item) for item in entry["covers"]})
            # 規範文の先は、その規範文を`covers`するテスト対応だけを使う。規範文のない文書の先は、`tests`をすべて使い、`covers`の和集合を取る。
            if target in known and target not in covers:
                continue
            name = entry.get("command") or document["frontmatter"].get("verify")
            if name is None:
                raise ValueError("コマンド名を解決できません")
            bucket = needs.setdefault((document["workspaceId"], name), {"tests": set(), "covers": set()})
            bucket["tests"].add(entry["path"])
            if target in known:
                bucket["covers"].add(target)
            else:
                bucket["covers"].update(covers)
    commands = []
    for (workspace, name), bucket in sorted(needs.items()):
        config = configs[workspace]
        definition = config["verify"]["commands"][name]
        tests = sorted(bucket["tests"])
        argv = [item for part in definition["argv"] for item in (tests if part == "{tests}" else [part])]
        commands.append({"bindingId": f"{workspace}::{name}", "workspaceId": workspace, "name": name,
                         "cwd": definition.get("cwd", "."), "argv": argv, "tests": tests,
                         "covers": sorted(bucket["covers"]),
                         "timeoutSeconds": int(config["verify"].get("timeoutSeconds", 300))})
    return {"statements": sorted(set(statements)), "bindingRefs": [item["bindingId"] for item in commands],
            "commands": commands}


def check_result(result, plan):
    """結果の`statements`、`bindingRefs`、`commands`が、入力から導いた計画と一致することを確かめる。"""
    target = result["targetResults"][0]
    if (result["status"], target["status"]) != ("passed", "passed") or target["diagnostics"] or result["diagnostics"]:
        raise ValueError("TASKの`addresses`の先のテストは、診断なしで`passed`になる必要があります")
    if target["statements"] != plan["statements"]:
        raise ValueError("対象規範文は`addresses`する規範文だけで、規範文のないTECHは規範文を足してはいけません")
    if target["bindingRefs"] != plan["bindingRefs"] or not plan["bindingRefs"]:
        raise ValueError("規範文のないTECHの文書単位のテストでも、テスト割当てを参照する必要があります")
    if len(result["commands"]) != len(plan["commands"]):
        raise ValueError("テスト割当てごとにコマンドを1件だけ実行する必要があります")
    for command, expected in zip(result["commands"], plan["commands"]):
        for key, value in expected.items():
            if command[key] != value:
                raise ValueError(f"コマンドの`{key}`が入力から導いた計画と異なります")
        if command["status"] != "passed" or command["exitCode"] != 0:
            raise ValueError("実行したコマンドは成功している必要があります")


def check_conditions(identifier, repository, schema):
    """原因を、散文ではなく入力の木構造から確かめる。

    原因は、TASKが規範文のないTECHを`addresses`し、そのTECHが文書単位の`tests`を持つことだけである。ほかの関係、文書の`verify`、
    規範文のあるTECHは置かない。
    """
    multi = identifier in MULTI
    documents, configs, _ = load_corpus(repository, multi)
    expected_ids = {"MULTI-028": {"web::TASK-001", "api::TECH-020"},
                    "SINGLE-156": {"TASK-001", "TECH-001"},
                    "SINGLE-157": {"TASK-001", "TECH-001", "REQ-001"}}[identifier]
    if set(documents) != expected_ids:
        raise ValueError("文書の集合がレビュー済みの入力と異なります")
    for document in documents.values():
        Draft202012Validator({"$ref": "#/$defs/" + KIND_SCHEMA[document["kind"]],
                              "$defs": schema["$defs"]}).validate(document["frontmatter"])
        if "verify" in document["frontmatter"]:
            raise ValueError("コマンド名は`tests[].command`だけが与え、文書の`verify`を置いてはいけません")
        relations = {key: value for key, value in document["frontmatter"].get("relations", {}).items() if value}
        if document["kind"] != "task" and relations:
            raise ValueError("TASK以外の文書は関係を宣言してはいけません")
    task = documents["web::TASK-001" if multi else "TASK-001"]
    if set(task["frontmatter"]) != {"id", "title", "status", "relations"}:
        raise ValueError("起点のTASKは、`changes`などの追加のフィールドを持ってはいけません")
    tech_id = "api::TECH-020" if multi else "TECH-001"
    tech = documents[tech_id]
    addresses = {"MULTI-028": ["api::TECH-020"], "SINGLE-156": ["TECH-001"],
                 "SINGLE-157": [STATEMENT, "TECH-001"]}[identifier]
    if (task["kind"] != "task" or task["frontmatter"]["status"] != "open"
            or task["frontmatter"]["relations"] != {"addresses": addresses}):
        raise ValueError("起点のTASK-001は、状態が`open`で、指定した先だけを`addresses`する必要があります")
    if tech["kind"] != "technical" or tech["frontmatter"]["status"] != "approved":
        raise ValueError("`addresses`の先のTECHは、状態が`approved`である必要があります")
    if digest_crosscheck.read_statements(tech["body"]):
        raise ValueError("原因のTECHは規範文を持ってはいけません")
    entries = tech["frontmatter"].get("tests", [])
    own = tech["frontmatter"]["id"]
    command = "backend" if multi else "default"
    workspace = "api" if multi else "root"
    if (len(entries) != 1 or entries[0]["covers"] != [own] or entries[0].get("command") != command
            or command not in configs[workspace]["verify"]["commands"]
            or "timeoutSeconds" in configs[workspace]["verify"]):
        raise ValueError("TECHは、自身の文書IDを`covers`し、設定が定義するコマンドを指す文書単位のテスト対応を1件だけ持つ必要があります")
    test_root = repository / ("services/api" if multi else ".")
    if not (test_root / entries[0]["path"]).is_file():
        raise ValueError("TECHのテストのファイルが存在しません")
    for workspace in (["api"] if multi else ["root"]):
        definition = configs[workspace]["verify"]["commands"][command]
        if definition["argv"] != ["/bin/true", "{tests}"] or definition.get("cwd", ".") != ".":
            raise ValueError("コマンドは`/bin/true {tests}`を作業ディレクトリ`.`で実行する必要があります")
    if multi:
        if configs["web"].get("verify", {}).get("commands"):
            raise ValueError("`web`はコマンドを定義してはいけません（コマンドは所有ワークスペースの`api`の設定で解決する）")
        if list(configs["api"]["verify"]["commands"]) != ["backend"]:
            raise ValueError("`api`の設定は`backend`だけを定義する必要があります")
        return
    if list(configs["root"]["verify"]["commands"]) != ["default"]:
        raise ValueError("設定は`default`だけを定義する必要があります")
    if identifier == "SINGLE-157":
        req = documents["REQ-001"]
        statements = digest_crosscheck.read_statements(req["body"])
        reqs = req["frontmatter"].get("tests", [])
        if (req["frontmatter"]["status"] != "approved" or [item["id"] for item in statements] != [STATEMENT]
                or statements[0]["modality"] != "MUST"):
            raise ValueError("REQ-001は、状態が`approved`で、`MUST`のREQ-001:AC-01だけを持つ必要があります")
        if (len(reqs) != 1 or reqs[0]["covers"] != [STATEMENT] or reqs[0].get("command") != "default"
                or reqs[0]["path"] == entries[0]["path"] or not (repository / reqs[0]["path"]).is_file()):
            raise ValueError("REQ-001は、TECH-001と異なるテストのパスで、同じコマンド名のテスト対応を1件だけ持つ必要があります")


def references(identifier, repository):
    """同じハッシュ値の材料を、独立に書いた2系統で計算し、バイト列の一致を要求する。"""
    literal = literal_bytes(identifier)
    if identifier in MULTI:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, root="web::TASK-001"))
    else:
        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, root="TASK-001"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    if digest_reference.digest(literal) != digest_crosscheck.digest(derived):
        raise ValueError("参照計算AとBのハッシュ値が一致しません")
    return literal


def check_settings_material(identifier, canonical):
    """材料の`commands`と`verifyTimeouts`は、TECHのテスト対応が与えたコマンドを所有ワークスペースの設定から収録した1件である。"""
    settings = json.loads(canonical.decode("utf-8"))["settings"]
    workspace, name = ("api", "backend") if identifier in MULTI else ("root", "default")
    if settings["commands"] != [{"workspaceId": workspace, "name": name, "argv": ["/bin/true", "{tests}"], "cwd": "."}]:
        raise ValueError("材料の`commands`が、TECHのテスト対応が与えた1件ではありません")
    if settings["verifyTimeouts"] != [{"workspaceId": workspace, "timeoutSeconds": 300}]:
        raise ValueError("材料の`verifyTimeouts`が、所有ワークスペースの既定値の1件ではありません")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def fixture_directory(root, identifier):
    return root / ("multi" if identifier in MULTI else "single") / identifier


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = fixture_directory(root, identifier)
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier, literal_digest(identifier))))
        with tempfile.TemporaryDirectory(prefix="bitz-verify-task-tech-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_directory(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for kind, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[kind].validate(value)
            digest = literal_digest(identifier)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier, digest):
                raise ValueError("起動条件または完全結果がレビュー済みの期待値と異なります")
            check_settings_material(identifier, literal_bytes(identifier))
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-task-tech-") as temporary:
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
                    check_conditions(identifier, repository, schema)
                    root_id = "web::TASK-001" if identifier in MULTI else "TASK-001"
                    check_result(result, reference_plan(repository, root_id, identifier in MULTI))
                    references(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
