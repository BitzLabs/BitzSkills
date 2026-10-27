"""テスト割当ての欠落（`SPEC-VERIFY-BLOCKED-001`）の診断を所有ワークスペースごとに返すことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C23に対応する（ADR-051の追加）。テスト対応のコマンド名が設定に定義されていないとき、`verify`は検証対象の`diagnostics`へ
`SPEC-VERIFY-BLOCKED-001`を返す。独立した元の原因（テスト対応のエントリ単位）はそれぞれ主診断を持つ。診断の`source`は`workspaceId`と`path`の組で一意である。
複合ワークスペースで、検証対象の閉包に別のワークスペースの同じ相対パス（どちらも`.spec/technical/TECH-001.md`）の文書があり、
どちらのテスト対応も同じ位置（`tests[0].command`）で欠落しても、所有ワークスペースが異なる別の原因なので2件を返すことを、4件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-039-01` | `verify web::REQ-001`、`.` | `web`と`api`が同じ相対パスのTECH-001を持ち、どちらも定義のないコマンド名を指す。診断は`api`と`web`の2件 |
| `MULTI-039-02` | `verify --all-workspaces`、`.` | 同じ入力。`web::REQ-001`は2件、`web::TECH-001`は`web`の1件、`api::TECH-001`は`api`の1件 |
| `MULTI-039-03` | `verify web::REQ-001`、`.` | 規範文2件を、各TECH-001の1つのエントリが指す。所有ワークスペースごとに1件へ畳み、全体で2件 |
| `MULTI-039-04` | `verify REQ-001`、`.`（単一） | 対照: 単一ワークスペースで、1つのエントリを規範文2件が指しても1件に畳む |

基本のリポジトリは、ルート`platform`（`.`、文書なし）、メンバー`web`（`apps/web`）と`api`（`services/api`）である。
単一ワークスペースの対照は、ルートの設定が`multiWorkspace`を持たない（ワークスペースIDは`root`）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 診断レジストリ §2: 独立した元の原因はそれぞれ主診断を持つ。同じ元の原因（同じ所有ワークスペースの同じ`path`・`key`）は1件に畳む。
  `VERIFY-BINDING-MISSING`は`SPEC-VERIFY-BLOCKED-001`（`blocked`）で、継続単位は`skip-target`（当該検証対象の`diagnostics`へ置く）。
- 結果・診断・終了コード §4・§5: 診断の`source`は`workspaceId`と`path`の組で一意である。診断の順序は、発生元のワークスペースID、`path`、`line`、`column`、`code`の辞書順。
- `verify` §3・§6: 検証対象ごとに目的`verify`のコンテキストを再解決し、通過状態のコンテキストについてテストのパスとコマンド名を解決する。
  コマンド名が設定に定義されていなければテスト割当てを構成できず、検証対象は`blocked`、`bindingRefs: []`で、診断を複製しない。
  規範文のないTECHが起点なら文書単位のテスト対応を使う（関係・トレースモデル §6.4の規則5）。
- 関係・トレースモデル §6.1・§6.3・§6.4: `verify`の閉包は、起点と、起点を`refines`する適用可能な文書（具体化文書）を含む。起点の`refines`の参照先は含めるが、その参照先の
  `requires`と、参照先を`refines`する別の文書は辿らない。対象規範文は起点と具体化文書の規範文で、テスト対応は`covers`が対象規範文を指すエントリである。
- コンテキストのハッシュ値の正規化仕様 §3: `verifyTimeouts`と`commands`は収録したテスト割当てだけから作る。コマンド名が設定にないテスト対応は収録しないので、材料は空である。
  ハッシュ値は、独立に書いた2系統の参照計算（このモジュールのリテラルA、入力の木構造から導出するB）のバイト列の一致を要求する。

参照計算`reference_*`は、入力の木構造から、閉包、対象規範文、テスト対応のエントリ、設定にないコマンド名を導く。Coreの出力は期待値の根拠にしない。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (digest_crosscheck, digest_reference, multi_crosscheck, multi_reference,
               multi_verify_fixtures as verify_fixtures)
from .digest_crosscheck import KIND_BY_DIRECTORY, canonical_bytes, normalize_body, read_statements, read_yaml, split_document
from .harness import setup
from .initial_fixtures import compare_state, observe
from .multi_closure_alias_fixtures import _material_request, load_tree
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = [("web", "apps/web"), ("api", "services/api")]
TECH_PATH = ".spec/technical/TECH-001.md"
TEST_PATH = "tests/test_login.py"
TEST_BYTES = b"def test_login():\n    assert True\n"
REQ_TITLE = "認証の基準"
STATEMENT_TEXTS = ("秘密情報を出力しない", "失敗を記録する")
TECH_TITLES = {"web": "Web側の実装方針", "api": "API側の実装方針", "root": "実装方針"}
# 設定に定義されているコマンド名は、web・api・rootがそれぞれ`frontend`・`backend`・`frontend`だけである。文書のテスト対応は定義のない名前を指す。
MISSING_COMMAND = {"web": "missing", "api": "absent", "root": "missing"}
NO_TARGET = verify_fixtures.NO_TARGET

# id: {op, cwd, argv, corpus, single, targets, outcome}。`targets`は期待する検証対象（修飾ID、複合ワークスペースの結果の順）。
CASES = {
    "MULTI-039-01": dict(cwd=".", argv=["verify", "web::REQ-001"], corpus="cross", single=False, targets=["web::REQ-001"],
                         description="別のワークスペースの同じ相対パスの文書のテスト対応が、どちらも定義のないコマンド名を指すとき、verifyは所有ワークスペースごとにSPEC-VERIFY-BLOCKED-001を返す"),
    "MULTI-039-02": dict(cwd=".", argv=["verify", "--all-workspaces"], corpus="cross", single=False,
                         targets=["api::TECH-001", "web::REQ-001", "web::TECH-001"],
                         description="複合ワークスペース全体のverifyも、検証対象ごとに所有ワークスペースごとのSPEC-VERIFY-BLOCKED-001を返す"),
    "MULTI-039-03": dict(cwd=".", argv=["verify", "web::REQ-001"], corpus="fold-cross", single=False, targets=["web::REQ-001"],
                         description="同じエントリを複数の規範文が指しても、所有ワークスペースごとにSPEC-VERIFY-BLOCKED-001を1件へ畳む"),
    "MULTI-039-04": dict(cwd=".", argv=["verify", "REQ-001"], corpus="fold-single", single=True, targets=["REQ-001"],
                         description="単一ワークスペースでは、同じエントリを複数の規範文が指してもSPEC-VERIFY-BLOCKED-001を1件へ畳む"),
}


def is_all(identifier):
    return "--all-workspaces" in CASES[identifier]["argv"]


def statement_count(corpus):
    return 1 if corpus == "cross" else 2


# --- 入力 -------------------------------------------------------------------------------

def requirement(count):
    """`approved`のREQ-001（`MUST`の規範文`count`件、関係なし）。(ファイルの全文, 正規化した本文)を返す。"""
    head = f"---\nid: REQ-001\ntitle: {REQ_TITLE}\nstatus: approved\n---\n\n"
    lines = "".join(f"- [REQ-001:AC-{number:02d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {STATEMENT_TEXTS[number - 1]}。\n"
                    for number in range(1, count + 1))
    body = (f"# REQ-001 {REQ_TITLE}\n\n## Intent\n\n{REQ_TITLE}の規範を定める。\n\n## Acceptance Criteria\n\n{lines}\n"
            "## Verification\n\nwebのtestで確認する。\n")
    return head + body, body


def technical(workspace, refines, covers):
    """規範文を持たない`approved`のTECH-001。`refines`を1件、テスト対応を1エントリ（`tests[0]`）で持つ。(ファイルの全文, 正規化した本文)を返す。

    コマンド名はそのワークスペースの設定に定義のない名前である。`refines`と`covers`は宣言どおりの文字列（修飾の有無を含む）。
    """
    title = TECH_TITLES[workspace]
    head = (f"---\nid: TECH-001\ntitle: {title}\nstatus: approved\nrelations:\n  refines: [{refines}]\n"
            f"tests:\n  - path: {TEST_PATH}\n    covers: [{', '.join(covers)}]\n    command: {MISSING_COMMAND[workspace]}\n---\n\n")
    body = f"# TECH-001 {title}\n\n## Context\n\n{title}を定める。\n"
    return head + body, body


def declared(workspace, count, single):
    """TECH-001の宣言どおりの`refines`と`covers`。`web`と単一ワークスペースは非修飾、`api`は`web`を修飾する。"""
    prefix = "web::" if workspace == "api" else ""
    return f"{prefix}REQ-001:AC-01", [f"{prefix}REQ-001:AC-{number:02d}" for number in range(1, count + 1)]


def corpus_files(corpus, single):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    count = statement_count(corpus)
    if single:
        refines, covers = declared("root", count, True)
        return {".spec/bitz.yaml": multi_reference.member_config("root", "frontend"),
                ".spec/requirements/REQ-001.md": requirement(count)[0],
                TECH_PATH: technical("root", refines, covers)[0],
                f"{TEST_PATH}": TEST_BYTES.decode()}
    web_refines, web_covers = declared("web", count, False)
    api_refines, api_covers = declared("api", count, False)
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "frontend"),
        multi_reference.API_CONFIG_PATH: multi_reference.member_config("api", "backend"),
        "apps/web/.spec/requirements/REQ-001.md": requirement(count)[0],
        f"apps/web/{TECH_PATH}": technical("web", web_refines, web_covers)[0],
        f"services/api/{TECH_PATH}": technical("api", api_refines, api_covers)[0],
        f"apps/web/{TEST_PATH}": TEST_BYTES.decode(),
        f"services/api/{TEST_PATH}": TEST_BYTES.decode(),
    }


def reviewed_inputs(identifier):
    return {name: (text if isinstance(text, bytes) else text.encode()) for name, text in
            corpus_files(CASES[identifier]["corpus"], CASES[identifier]["single"]).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        # `verify`はテスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をコミットする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": "blocked", "exitCode": 2, "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


# --- 診断（レビュー済みのリテラル） -----------------------------------------------------------------

def binding_missing(workspace_id, name):
    """`tests[0].command`の欠落。IDの`summary`は既存の承認済みの文言「コマンド名{name}が設定に定義されていません」（`SINGLE-061`）。"""
    return {"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
            "summary": f"コマンド名{name}が設定に定義されていません",
            "source": {"kind": "file", "workspaceId": workspace_id, "path": TECH_PATH, "key": "tests[0].command"}}


def reviewed_diagnostics(identifier, target):
    """検証対象`target`の診断。発生元のワークスペースIDの辞書順（`api`、`web`）。"""
    if CASES[identifier]["single"]:
        return [binding_missing("root", MISSING_COMMAND["root"])]
    web, api = binding_missing("web", MISSING_COMMAND["web"]), binding_missing("api", MISSING_COMMAND["api"])
    return {"web::REQ-001": [api, web], "web::TECH-001": [web], "api::TECH-001": [api]}[target]


def reviewed_statements(identifier, target):
    """検証対象の対象規範文。規範文のないTECHは空。"""
    if not target.endswith("REQ-001"):
        return []
    prefix = "" if CASES[identifier]["single"] else "web::"
    return [f"{prefix}REQ-001:AC-{number:02d}" for number in range(1, statement_count(CASES[identifier]["corpus"]) + 1)]


# --- 期待結果 ---------------------------------------------------------------------------------

def revision():
    return {"commit": COMMIT, "dirty": False}


def target_result(identifier, target, context_digest):
    return {"target": target, "status": "blocked", "contextDigest": context_digest,
            "statements": reviewed_statements(identifier, target), "bindingRefs": [],
            "diagnostics": reviewed_diagnostics(identifier, target)}


def reviewed_result(identifier):
    """テスト割当てを構成できないので、検証対象は`blocked`、`bindingRefs: []`で、テストを開始しない（`commands: []`）。コンテキストは完成するので`contextDigest`を持つ。"""
    case = CASES[identifier]
    digests = {target: expected_digest(identifier, target) for target in case["targets"]}
    if not is_all(identifier):
        return {
            "schemaVersion": "1.0", "operation": "verify", "status": "blocked", "scope": "selected",
            "workspace": {"id": "root", "path": "."} if case["single"] else {"id": "web", "path": "apps/web"},
            "targetResults": [target_result(identifier, case["targets"][0], digests[case["targets"][0]])],
            "revision": revision(), "commands": [], "durationMs": 0, "diagnostics": [],
        }

    def no_target(workspace_id, path):
        return verify_fixtures.workspace_result(workspace_id, path, "passed_with_warnings", diagnostics=[
            {**NO_TARGET, "source": {"kind": "file", "workspaceId": workspace_id, "path": ".spec/bitz.yaml"}}])

    def with_targets(workspace_id, path):
        return verify_fixtures.workspace_result(
            workspace_id, path, "blocked",
            targets=[target_result(identifier, target, digests[target]) for target in case["targets"]
                     if target.partition("::")[0] == workspace_id])

    return {
        "schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "blocked",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [no_target("platform", "."), with_targets("api", "services/api"), with_targets("web", "apps/web")],
        "revision": revision(), "durationMs": 0, "diagnostics": [],
    }


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _document(workspace, kind, single, title, body, refines=None, covers=(), command=None, statements=()):
    """ハッシュ値の材料の文書1件。複合ワークスペースでは修飾ID、単一ワークスペースでは修飾しない。"""
    prefix = "" if single else f"{workspace}::"
    local = "REQ-001" if kind == "requirement" else "TECH-001"
    declared_refines = [refines] if refines else []
    entry = [{"path": TEST_PATH, "covers": sorted(covers), "command": command}] if command else []
    return {
        "id": f"{prefix}{local}", "workspaceId": workspace, "kind": kind, "status": "approved", "applicability": "applicable",
        "frontmatter": {"id": f"{prefix}{local}", "title": title, "status": "approved",
                        "relations": {**digest_reference.EMPTY_RELATIONS, "refines": declared_refines},
                        "implements": [], "tests": entry, "verify": None, "changes": []},
        "bodyText": body,
        "statements": [verify_fixtures.statement_material(f"{prefix}REQ-001:AC-{number:02d}", STATEMENT_TEXTS[number - 1])
                       for number in statements],
        "strongRelations": [{"relation": "refines", "target": target} for target in declared_refines],
    }


def reviewed_digest_input(identifier, target):
    """目的`verify`のレビュー済みのハッシュ値の材料（参照計算A）。コマンド名が設定にないので`verifyTimeouts`と`commands`は空。

    閉包は、起点を所有する文書、起点の`refines`の参照先、起点を所有する文書を`refines`する文書（関係・トレースモデル §6.1・§6.3）。
    """
    case = CASES[identifier]
    count, single = statement_count(case["corpus"]), case["single"]
    numbers = range(1, count + 1)
    req_body, web_body, api_body = requirement(count)[1], technical("web", *declared("web", count, False))[1], technical("api", *declared("api", count, False))[1]
    if single:
        _, covers = declared("root", count, True)
        documents = [
            _document("root", "requirement", True, REQ_TITLE, req_body, statements=numbers),
            _document("root", "technical", True, TECH_TITLES["root"], technical("root", "REQ-001:AC-01", covers)[1],
                      refines="REQ-001:AC-01", covers=covers, command=MISSING_COMMAND["root"]),
        ]
        return _material_request(True, [("root", ".")], documents, [], "REQ-001", purpose="verify")
    request = target.partition("::")[0]
    req = _document("web", "requirement", False, REQ_TITLE, req_body, statements=numbers)
    web = _document("web", "technical", False, TECH_TITLES["web"], web_body, refines="web::REQ-001:AC-01",
                    covers=[f"web::REQ-001:AC-{n:02d}" for n in numbers], command=MISSING_COMMAND["web"])
    api = _document("api", "technical", False, TECH_TITLES["api"], api_body, refines="web::REQ-001:AC-01",
                    covers=[f"web::REQ-001:AC-{n:02d}" for n in numbers], command=MISSING_COMMAND["api"])
    members = {"web": ("web", "apps/web"), "api": ("api", "services/api")}
    chosen = {"web::REQ-001": [req, web, api], "web::TECH-001": [req, web], "api::TECH-001": [req, api]}[target]
    reached = sorted({document["workspaceId"] for document in chosen})
    ordered = [request] + [name for name in reached if name != request]
    edges = [{"relation": "refines", "source": document["id"], "target": "web::REQ-001:AC-01"}
             for document in chosen if document["workspaceId"] != "web"]
    return _material_request(False, [members[name] for name in ordered], chosen, edges, target, purpose="verify")


def expected_digest(identifier, target):
    """生成と監査が使う、リテラルの参照計算Aのハッシュ値。"""
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier, target)))


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def refines_of(documents, identifier):
    """`identifier`が`refines`で指す参照（宣言どおりの参照, 修飾した参照）。"""
    document = documents[identifier]
    return [(text, multi_crosscheck.qualify(document["workspaceId"], text))
            for text in document["frontmatter"].get("relations", {}).get("refines", [])]


def statement_ids(documents, identifier):
    document = documents[identifier]
    return [f"{document['workspaceId']}::{item['id']}" for item in read_statements(document["body"])]


def verify_closure(documents, root):
    """目的`verify`の閉包（関係・トレースモデル §6.1・§6.3）と具体化文書。このcorpusは`requires`を使わない。

    起点を所有する文書、その`refines`の参照先の文書（参照先の`requires`と、参照先を`refines`する文書は辿らない）、
    起点を所有する文書またはその規範文を`refines`する適用可能な文書（推移的）。戻り値は(閉包の文書の順序, 具体化文書)。
    """
    root_document = multi_crosscheck.owner(root)
    order, refiners = [root_document], []
    for _, target in refines_of(documents, root_document):
        if multi_crosscheck.owner(target) in documents and multi_crosscheck.owner(target) not in order:
            order.append(multi_crosscheck.owner(target))
    queue = [root_document]
    while queue:
        current = queue.pop(0)
        mine = {current, *statement_ids(documents, current)}
        for candidate in sorted(documents):
            if candidate in order or documents[candidate]["frontmatter"]["status"] != "approved":
                continue
            if documents[candidate]["kind"] not in {"requirement", "technical"}:
                continue
            if {target for _, target in refines_of(documents, candidate)} & mine:
                order.append(candidate)
                refiners.append(candidate)
                queue.append(candidate)
    return order, refiners


def target_statements(documents, root, refiners):
    """対象規範文: 起点を所有する文書と具体化文書の規範文（関係・トレースモデル §6.4の規則1）。"""
    return [item for name in [multi_crosscheck.owner(root), *refiners] for item in statement_ids(documents, name)]


def reference_diagnostics(documents, workspaces, root):
    """検証対象`root`のテスト割当ての欠落の診断。コマンド名が所有ワークスペースの設定にないテスト対応のエントリを、元の原因ごとに1件導く。

    元の原因は(所有ワークスペース, `path`, エントリの添字)の組で識別する。同じエントリを複数の規範文が指しても同じ原因である。
    規範文のないTECHが起点なら、起点のすべてのテスト対応が対象である（同 §6.4の規則5）。
    """
    order, refiners = verify_closure(documents, root)
    statements = target_statements(documents, root, refiners)
    root_document = multi_crosscheck.owner(root)
    entries = []
    if statements:
        for statement in statements:
            for name in order:
                for index, entry in enumerate(documents[name]["frontmatter"].get("tests", [])):
                    covered = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for text in entry["covers"]}
                    if statement in covered:
                        entries.append((name, index, entry))
    elif documents[root_document]["kind"] == "technical":
        entries = [(root_document, index, entry) for index, entry in enumerate(documents[root_document]["frontmatter"].get("tests", []))]
    causes = {}
    for name, index, entry in entries:
        document = documents[name]
        command = entry.get("command") or document["frontmatter"].get("verify")
        defined = workspaces[document["workspaceId"]]["config"].get("verify", {}).get("commands", {})
        if command is None:
            raise ValueError("このcorpusはコマンド名を持たないテスト対応を扱いません")
        if command not in defined:
            causes.setdefault((document["workspaceId"], document["path"], index), command)
    return [{"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
             "summary": f"コマンド名{causes[key]}が設定に定義されていません",
             "source": {"kind": "file", "workspaceId": key[0], "path": key[1], "key": f"tests[{key[2]}].command"}}
            for key in sorted(causes)]


def derived_material(repository, documents, workspaces, root):
    """入力の木構造から導くハッシュ値の材料（参照計算B）。`multi_crosscheck.build`と同じ形を、閉包の規則（上の`verify_closure`）とコマンドの収録の規則で組み立てる。

    設定にないコマンド名のテスト対応は収録しない（正規化仕様 §3）。収録したテスト割当てがなければ`verifyTimeouts`と`commands`は空。
    """
    order, _ = verify_closure(documents, root)
    request = root.partition("::")[0]
    reached = {documents[name]["workspaceId"] for name in order}
    config = workspaces[request]["config"]
    limits = config.get("context", {})
    commands, timeouts = [], []
    for workspace_id in sorted(reached):
        defined = workspaces[workspace_id]["config"].get("verify", {}).get("commands", {})
        used = set()
        for name in order:
            if documents[name]["workspaceId"] != workspace_id:
                continue
            for entry in multi_crosscheck.tests(documents[name]):
                command = entry["command"] if entry["command"] is not None else documents[name]["frontmatter"].get("verify")
                if command is not None and command in defined:
                    used.add(command)
        if used:
            timeouts.append({"workspaceId": workspace_id,
                             "timeoutSeconds": int(workspaces[workspace_id]["config"].get("verify", {}).get("timeoutSeconds", 300))})
        commands += [{"workspaceId": workspace_id, "name": name, "argv": list(defined[name]["argv"]), "cwd": defined[name].get("cwd", ".")}
                     for name in sorted(used)]
    payload = {
        "digestVersion": "1.0", "specSchemaVersion": config["schemaVersion"], "earsAiVersion": config["earsAi"],
        "resolverVersion": "1.0", "purpose": "verify", "requestWorkspaceId": request, "roots": [root],
        "workspaces": [{"id": name, "path": workspaces[name]["path"]} for name in [request, *sorted(reached - {request})]],
        "documents": [], "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": name, "schemaVersion": workspaces[name]["config"]["schemaVersion"],
                                     "earsAi": workspaces[name]["config"]["earsAi"], "language": workspaces[name]["config"]["language"]}
                                    for name in sorted(reached)],
                     "context": {"maxDocuments": int(limits.get("maxDocuments", 20)), "maxBytes": int(limits.get("maxBytes", 131072))},
                     "verifyTimeouts": timeouts, "commands": commands},
    }
    cross = set()
    for name in order:
        document = documents[name]
        relations = multi_crosscheck.relations(document)
        for key in digest_crosscheck.RELATION_KEYS:
            cross |= {(name, key, target) for target in relations[key] if target.partition("::")[0] != document["workspaceId"]}
        payload["documents"].append({
            "id": name, "workspaceId": document["workspaceId"], "kind": document["kind"],
            "status": document["frontmatter"]["status"], "applicability": "applicable",
            "frontmatter": {"id": name, "title": document["frontmatter"]["title"], "status": document["frontmatter"]["status"],
                            "relations": relations, "implements": multi_crosscheck.paths(document["frontmatter"].get("implements", [])),
                            "tests": multi_crosscheck.tests(document), "verify": document["frontmatter"].get("verify"),
                            "changes": multi_crosscheck.paths(document["frontmatter"].get("changes", []))},
            "bodyText": document["body"],
            "statements": sorted((digest_crosscheck._sorted_extensions(dict(item, id=f"{document['workspaceId']}::{item['id']}"))
                                  for item in read_statements(document["body"])), key=lambda item: item["id"]),
            "strongRelations": [{"relation": key, "target": target} for key, target in
                                sorted({(key, target) for key in digest_crosscheck.STRONG for target in relations[key]})],
        })
    payload["documents"].sort(key=lambda item: item["id"])
    payload["crossWorkspaceEdges"] = [{"relation": key, "source": source, "target": target} for source, key, target in sorted(cross)]
    return digest_crosscheck.normalize_strings(payload)


def reference_digest(identifier, repository, documents, workspaces, target):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier, target))
    if CASES[identifier]["single"]:
        derived = canonical_bytes(digest_crosscheck.build(repository, target, "verify", workspace_id="root"))
    else:
        derived = canonical_bytes(derived_material(repository, documents, workspaces, target))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


# --- 監査 ---------------------------------------------------------------------------------------

def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた診断・対象規範文・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = load_tree(repository)
    if single != case["single"]:
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    if is_all(identifier):
        if [item["id"] for item in result["workspaces"]] != ["platform", "api", "web"]:
            raise ValueError("全体の`verify`のワークスペースの順が異なります")
        entries = [entry for workspace in result["workspaces"] for entry in workspace["targetResults"]]
    else:
        entries = result["targetResults"]
    if [entry["target"] for entry in entries] != case["targets"]:
        raise ValueError("検証対象が期待と異なります")
    for entry in entries:
        key = f"{root_id}::{entry['target']}" if single else entry["target"]
        if entry["diagnostics"] != reference_diagnostics(documents, workspaces, key):
            raise ValueError("診断が入力からの参照計算と異なります")
        order, refiners = verify_closure(documents, key)
        wanted = [item if not single else item.partition("::")[2] for item in target_statements(documents, key, refiners)]
        if entry["statements"] != wanted or entry["bindingRefs"] != [] or entry["status"] != "blocked":
            raise ValueError("対象規範文または状態が入力からの参照計算と異なります")
        if entry["contextDigest"] != reference_digest(identifier, repository, documents, workspaces, entry["target"]):
            raise ValueError("ハッシュ値が参照計算と異なります")
    if result["status"] != "blocked":
        raise ValueError("状態が入力からの参照計算と異なります")
    if not is_all(identifier) and result["commands"] != []:
        raise ValueError("テスト割当てを構成できないのでコマンドを実行してはいけません")
    if is_all(identifier) and any(workspace["commands"] for workspace in result["workspaces"]):
        raise ValueError("テスト割当てを構成できないのでコマンドを実行してはいけません")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = load_tree(repository)
    corpus = case["corpus"]
    if single:
        # 単一ワークスペース: 1つのエントリが複数の規範文を指し、そのコマンド名は設定にない。
        entry = documents[f"{root_id}::TECH-001"]["frontmatter"]["tests"]
        if len(entry) != 1 or len(entry[0]["covers"]) < 2:
            raise ValueError("TECH-001は1つのエントリで規範文2件を指す必要があります")
        if entry[0]["command"] in workspaces[root_id]["config"]["verify"]["commands"]:
            raise ValueError("コマンド名は設定に定義されていない必要があります")
        if len(reference_diagnostics(documents, workspaces, f"{root_id}::REQ-001")) != 1:
            raise ValueError("原因は1つのエントリの欠落だけである必要があります")
        return
    web, api = documents["web::TECH-001"], documents["api::TECH-001"]
    # 同じ相対パスの文書が、別のワークスペースにある（所有ワークスペースだけが異なる）。
    if web["path"] != api["path"] or web["path"] != TECH_PATH or web["workspaceId"] == api["workspaceId"]:
        raise ValueError("`web`と`api`は同じ相対パスのTECH-001を持つ必要があります")
    for document in (web, api):
        tests = document["frontmatter"]["tests"]
        defined = workspaces[document["workspaceId"]]["config"]["verify"]["commands"]
        if len(tests) != 1 or tests[0]["command"] in defined or not defined:
            raise ValueError("どちらのテスト対応も、設定に定義のないコマンド名を1エントリで指す必要があります")
        if len(tests[0]["covers"]) != statement_count(corpus):
            raise ValueError("エントリが指す規範文の件数が入力と異なります")
    if api["frontmatter"]["relations"]["refines"] != ["web::REQ-001:AC-01"]:
        raise ValueError("`api::TECH-001`は修飾した宣言で起点の規範文を`refines`する必要があります")
    order, refiners = verify_closure(documents, "web::REQ-001")
    if set(order) != {"web::REQ-001", "web::TECH-001", "api::TECH-001"} or set(refiners) != {"web::TECH-001", "api::TECH-001"}:
        raise ValueError("起点の閉包に、別のワークスペースの文書が含まれる必要があります")
    if len(reference_diagnostics(documents, workspaces, "web::REQ-001")) != 2:
        raise ValueError("原因は2つのワークスペースのエントリの欠落だけである必要があります")
    for workspace in ("web", "api"):
        if (repository / workspaces[workspace]["path"] / TEST_PATH).read_bytes() != TEST_BYTES:
            raise ValueError("テストのパスは存在する入力である必要があります")


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
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-binding-missing-") as temporary:
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
            result = json.loads((fixture / "expected/verify.json").read_text())
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-binding-missing-") as temporary:
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
                        if path.parent.parent.name == ".spec" and path.parent.name in KIND_BY_DIRECTORY:
                            value, _ = split_document(path.read_text(encoding="utf-8"))
                            kind = {"requirements": "reqFrontmatter", "technical": "techFrontmatter"}[path.parent.name]
                            Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": frontmatter["$defs"]}).validate(value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
