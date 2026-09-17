"""複合workspace全体のverifyを固定するreview済みvector（Core操作は実行しない）。

`verify --all-workspaces`はroot workspaceを先頭、以降をworkspace ID辞書順に処理し、通過targetのbindingを
和集合として1回ずつ実行する。この群は、派生遮断（`MULTI-012`）、共有binding（`MULTI-013`）、
失敗後の継続（`MULTI-014`）、member単位の対象0件（`MULTI-015`）、全体の対象0件（`MULTI-016`）を扱う。

Digestが必要なfixtureでは、review済みliteral（参照計算A）で期待値を作り、監査で入力treeからの導出
（参照計算B、multi_crosscheck）と照合する。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EMPTY_RELATIONS = multi_reference.EMPTY_RELATIONS
DESCRIPTIONS = {
    "MULTI-012": "invalid文書へ強く依存するtargetを遮断し独立targetを実行する",
    "MULTI-013": "異なる2つのContextが同じbindingを1回だけ実行する",
    "MULTI-014": "command失敗後も独立bindingを実行する",
    "MULTI-015": "対象0件のmemberをwarningにし全体を成功させる",
    "MULTI-016": "複合workspace全体の対象0件を成功にしない",
}
STATUS = {"MULTI-012": ("failed", 1), "MULTI-013": ("passed", 0), "MULTI-014": ("failed", 1),
          "MULTI-015": ("passed_with_warnings", 0), "MULTI-016": ("blocked", 2)}
NO_TARGET = {
    "code": "SPEC-VERIFY-BLOCKED-002", "severity": "warning", "resultStatus": "passed_with_warnings",
    "summary": "検証対象がありません",
}
DUPLICATE_ID = {
    "code": "EAI-CORE-ID-002", "severity": "error", "resultStatus": "failed",
    "summary": "規範文IDが文書内で重複しています",
    "source": {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-020.md",
               "line": 13, "column": 3},
}


def requirement(identifier, title, statement_id, text="秘密情報を出力しない"):
    return (
        f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n---\n"
        f"\n# {identifier} {title}\n"
        "\n## Intent\n"
        f"\n{title}の規範を定める。\n"
        "\n## Acceptance Criteria\n"
        f"\n- [{statement_id}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n"
        "\n## Verification\n"
        "\nmemberのtestで確認する。\n"
    )


def technical(identifier, title, body, refines=None, requires=None, tests=(), statements=()):
    head = [f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n"]
    if refines or requires:
        head.append("relations:\n")
        if requires:
            head.append(f"  requires: [{requires}]\n")
        if refines:
            head.append(f"  refines: [{refines}]\n")
    if tests:
        head.append("tests:\n")
        for path, covers, command in tests:
            head.append(f"  - path: {path}\n    covers: [{covers}]\n    command: {command}\n")
    head.append("---\n")
    text = "".join(head) + f"\n# {identifier} {title}\n\n## Context\n\n{body}\n"
    if statements:
        text += "\n## Acceptance Criteria\n\n" + "".join(statements)
    return text


# 同じIDの規範文を2件持つ文書。Coreはこれをskip-documentとして扱う。
DUPLICATE_STATEMENTS = (
    "- [TECH-020:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを残す。\n",
    "- [TECH-020:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを保持する。\n",
)


def reviewed_inputs(identifier):
    """fixtureごとのrepo/入力。MULTI-013だけがmember 1件で、ほかはweb・apiの2件を持つ。"""
    members = [("web", "apps/web")] if identifier == "MULTI-013" else [("web", "apps/web"),
                                                                       ("api", "services/api")]
    files = {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(members).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "frontend").encode(),
    }
    if identifier != "MULTI-013":
        files[multi_reference.API_CONFIG_PATH] = multi_reference.member_config("api", "backend").encode()
    if identifier == "MULTI-016":
        # どのworkspaceもverifyの対象を持たない。設定だけの複合workspaceである。
        return files
    if identifier == "MULTI-015":
        files[multi_reference.ROOT_REQ_PATH] = requirement(
            "REQ-001", "認証の基準", "REQ-001:AC-01").encode()
        files[multi_reference.WEB_TECH_PATH] = technical(
            "TECH-010", "Web側の実装方針", "webでREQ-001を実装する。",
            refines="platform::REQ-001:AC-01",
            tests=[("tests/auth/test_login.py", "platform::REQ-001:AC-01", "frontend")]).encode()
        files["apps/web/tests/auth/test_login.py"] = b"def test_login():\n    assert True\n"
        return files
    if identifier == "MULTI-012":
        files[multi_reference.ROOT_REQ_PATH] = requirement(
            "REQ-001", "認証の基準", "REQ-001:AC-01").encode()
        files[".spec/requirements/REQ-002.md"] = requirement(
            "REQ-002", "監査の基準", "REQ-002:AC-01", "監査logを記録する").encode()
        files[multi_reference.WEB_TECH_PATH] = technical(
            "TECH-010", "Web側の実装方針", "webでREQ-001を実装する。",
            refines="platform::REQ-001:AC-01", requires="api::TECH-020",
            tests=[("tests/auth/test_login.py", "platform::REQ-001:AC-01", "frontend")]).encode()
        files[multi_reference.API_TECH_PATH.replace("TECH-010", "TECH-020")] = technical(
            "TECH-020", "API側の監査方針", "監査logの方針を定める。",
            tests=[("tests/test_audit.py", "api::TECH-020:AC-01", "backend")],
            statements=DUPLICATE_STATEMENTS).encode()
        files["services/api/.spec/technical/TECH-030.md"] = technical(
            "TECH-030", "API側の監査実装方針", "apiでREQ-002を実装する。",
            refines="platform::REQ-002:AC-01",
            tests=[("tests/test_report.py", "platform::REQ-002:AC-01", "backend")]).encode()
        files["apps/web/tests/auth/test_login.py"] = b"def test_login():\n    assert True\n"
        files["services/api/tests/test_audit.py"] = b"def test_audit():\n    assert True\n"
        files["services/api/tests/test_report.py"] = b"def test_report():\n    assert True\n"
        return files
    # MULTI-013とMULTI-014は、2つのtargetが同じcommand名のbindingを共有する。
    failing = identifier == "MULTI-014"
    files[multi_reference.ROOT_REQ_PATH] = requirement(
        "REQ-001", "認証の基準", "REQ-001:AC-01").encode()
    files[multi_reference.WEB_TECH_PATH] = technical(
        "TECH-010", "Web側の実装方針", "webでREQ-001を実装する。",
        refines="platform::REQ-001:AC-01",
        tests=[("tests/auth/test_login.py", "platform::REQ-001:AC-01", "frontend")]).encode()
    files["apps/web/tests/auth/test_login.py"] = b"def test_login():\n    assert True\n"
    if failing:
        # webのcommandだけを失敗させ、apiの独立bindingが後続で実行されることを見る。
        files[multi_reference.WEB_CONFIG_PATH] = multi_reference.member_config(
            "web", "frontend").replace('"/bin/true"', '"/bin/false"').encode()
        files[".spec/requirements/REQ-002.md"] = requirement(
            "REQ-002", "監査の基準", "REQ-002:AC-01", "監査logを記録する").encode()
        files["services/api/.spec/technical/TECH-030.md"] = technical(
            "TECH-030", "API側の監査実装方針", "apiでREQ-002を実装する。",
            refines="platform::REQ-002:AC-01",
            tests=[("tests/test_report.py", "platform::REQ-002:AC-01", "backend")]).encode()
        files["services/api/tests/test_report.py"] = b"def test_report():\n    assert True\n"
    return files


def reviewed_manifest(identifier):
    status, exit_code = STATUS[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        # verifyはbinding所有workspaceの設定がindexで未追跡だと起動を遮断するため、入力をstageする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "--all-workspaces", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


# --- 参照計算A: このcorpus群のreview済みDigest材料 ---------------------------------

def document_material(identifier, document_id, workspace_id, kind, title, body, relations=None,
                      tests=(), statements=()):
    declared = {**EMPTY_RELATIONS, **(relations or {})}
    strong = sorted({(key, target) for key in ("requires", "refines", "addresses", "supersedes")
                     for target in declared[key]})
    return {
        "id": document_id,
        "workspaceId": workspace_id,
        "kind": kind,
        "status": "approved",
        "applicability": "applicable",
        "frontmatter": {
            "id": document_id, "title": title, "status": "approved",
            "relations": declared,
            "implements": [],
            "tests": [{"path": path, "covers": [covers], "command": command}
                      for path, covers, command in tests],
            "verify": None, "changes": [],
        },
        "bodyText": body,
        "statements": list(statements),
        "strongRelations": [{"relation": key, "target": target} for key, target in strong],
    }


def statement_material(statement_id, text):
    return {"id": statement_id, "actor": "TargetSystem",
            "activation": {"kind": "ALWAYS", "text": None}, "modality": "MUST",
            "reason": None, "operation": {"kind": "CONSTRAINT", "text": text},
            "extensions": []}


def requirement_body(identifier, title, statement_id, text="秘密情報を出力しない"):
    return (f"# {identifier} {title}\n\n## Intent\n\n{title}の規範を定める。\n\n"
            "## Acceptance Criteria\n\n"
            f"- [{statement_id}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
            "## Verification\n\nmemberのtestで確認する。\n")


def technical_body(identifier, title, body):
    return f"# {identifier} {title}\n\n## Context\n\n{body}\n"


def reviewed_digest_input(identifier, root):
    """通過targetのDigest材料。Contextが完成するtargetだけが持つ。"""
    workspaces = {"platform": ".", "web": "apps/web", "api": "services/api"}
    web_tech = document_material(
        identifier, "web::TECH-010", "web", "technical", "Web側の実装方針",
        technical_body("TECH-010", "Web側の実装方針", "webでREQ-001を実装する。"),
        relations={"refines": ["platform::REQ-001:AC-01"]},
        tests=[("tests/auth/test_login.py", "platform::REQ-001:AC-01", "frontend")])
    req_001 = document_material(
        identifier, "platform::REQ-001", "platform", "requirement", "認証の基準",
        requirement_body("REQ-001", "認証の基準", "REQ-001:AC-01"),
        statements=[statement_material("platform::REQ-001:AC-01", "秘密情報を出力しない")])
    req_002 = document_material(
        identifier, "platform::REQ-002", "platform", "requirement", "監査の基準",
        requirement_body("REQ-002", "監査の基準", "REQ-002:AC-01", "監査logを記録する"),
        statements=[statement_material("platform::REQ-002:AC-01", "監査logを記録する")])
    api_tech_030 = document_material(
        identifier, "api::TECH-030", "api", "technical", "API側の監査実装方針",
        technical_body("TECH-030", "API側の監査実装方針", "apiでREQ-002を実装する。"),
        relations={"refines": ["platform::REQ-002:AC-01"]},
        tests=[("tests/test_report.py", "platform::REQ-002:AC-01", "backend")])
    if root in {"platform::REQ-001", "web::TECH-010"}:
        documents = [req_001, web_tech]
        command = {"workspaceId": "web", "name": "frontend",
                   "argv": ["/bin/false" if identifier == "MULTI-014" else "/bin/true", "{tests}"],
                   "cwd": "."}
        reached = ["platform", "web"]
        timeouts = [{"workspaceId": "web", "timeoutSeconds": 300}]
    else:
        documents = [req_002, api_tech_030]
        command = {"workspaceId": "api", "name": "backend", "argv": ["/bin/true", "{tests}"], "cwd": "."}
        reached = ["api", "platform"]
        timeouts = [{"workspaceId": "api", "timeoutSeconds": 300}]
    request = root.partition("::")[0]
    ordered = [request] + sorted(set(reached) - {request})
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "verify",
        "requestWorkspaceId": request,
        "roots": [root],
        "workspaces": [{"id": name, "path": workspaces[name]} for name in ordered],
        "documents": sorted(copy.deepcopy(documents), key=lambda item: item["id"]),
        "crossWorkspaceEdges": [
            {"relation": "refines", "source": document["id"], "target": target}
            for document in documents
            for target in document["frontmatter"]["relations"]["refines"]
            if target.partition("::")[0] != document["workspaceId"]],
        "settings": {
            "workspaces": [{"id": name, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}
                           for name in sorted(reached)],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": timeouts,
            "commands": [command],
        },
    }


def digest(identifier, root):
    return multi_reference.digest(
        multi_reference.canonical_bytes(reviewed_digest_input(identifier, root)))


# --- review済みの期待結果 ---------------------------------------------------------

def target(name, status, context_digest=None, statements=(), bindings=(), diagnostics=()):
    return {"target": name, "status": status, "contextDigest": context_digest,
            "statements": list(statements), "bindingRefs": list(bindings),
            "diagnostics": [copy.deepcopy(entry) for entry in diagnostics]}


def command_result(workspace_id, name, executable, tests, covers, status="passed", exit_code=0):
    return {
        "bindingId": f"{workspace_id}::{name}", "workspaceId": workspace_id, "name": name,
        "status": status, "termination": "exit", "cwd": ".",
        "argv": [executable, *tests], "tests": list(tests), "covers": list(covers),
        "exitCode": exit_code, "timeoutSeconds": 300,
        "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False,
        "durationMs": 0,
    }


def dependency_diagnostic(path, workspace_id):
    return {
        "code": "SPEC-MULTI-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
        "summary": "依存するworkspaceの非成功によりContextを構成できません",
        "source": {"kind": "file", "workspaceId": workspace_id, "path": path},
        "evidence": {"stage": "context", "dependencyWorkspaces": ["api"],
                     "dependencySpecRefs": ["api::TECH-020"]},
    }


def workspace_result(workspace_id, path, status, targets=(), commands=(), diagnostics=()):
    return {"id": workspace_id, "path": path, "status": status,
            "targetResults": [copy.deepcopy(entry) for entry in targets],
            "commands": [copy.deepcopy(entry) for entry in commands],
            "durationMs": 0, "diagnostics": [copy.deepcopy(entry) for entry in diagnostics]}


def reviewed_result(identifier):
    status, _ = STATUS[identifier]
    if identifier == "MULTI-012":
        workspaces = [
            workspace_result("platform", ".", "blocked", targets=[
                target("platform::REQ-001", "blocked",
                       diagnostics=[dependency_diagnostic(".spec/requirements/REQ-001.md", "platform")]),
                target("platform::REQ-002", "passed", digest(identifier, "platform::REQ-002"),
                       ["platform::REQ-002:AC-01"], ["api::backend"]),
            ]),
            workspace_result("api", "services/api", "failed", targets=[
                target("api::TECH-020", "failed", diagnostics=[DUPLICATE_ID]),
                target("api::TECH-030", "passed", digest(identifier, "api::TECH-030"),
                       bindings=["api::backend"]),
            ], commands=[command_result("api", "backend", "/bin/true", ["tests/test_report.py"],
                                        ["platform::REQ-002:AC-01"])]),
            workspace_result("web", "apps/web", "blocked", targets=[
                target("web::TECH-010", "blocked",
                       diagnostics=[dependency_diagnostic(".spec/technical/TECH-010.md", "web")]),
            ]),
        ]
    elif identifier == "MULTI-013":
        # 2つのtargetは別のContextを持ち、同じbindingを1回だけ実行する。
        # どのworkspaceも対象を持つので、0件のwarningは現れない。
        workspaces = [
            workspace_result("platform", ".", "passed", targets=[
                target("platform::REQ-001", "passed", digest(identifier, "platform::REQ-001"),
                       ["platform::REQ-001:AC-01"], ["web::frontend"]),
            ]),
            workspace_result("web", "apps/web", "passed", targets=[
                target("web::TECH-010", "passed", digest(identifier, "web::TECH-010"),
                       bindings=["web::frontend"]),
            ], commands=[command_result("web", "frontend", "/bin/true",
                                        ["tests/auth/test_login.py"], ["platform::REQ-001:AC-01"])]),
        ]
    elif identifier == "MULTI-014":
        workspaces = [
            workspace_result("platform", ".", "failed", targets=[
                target("platform::REQ-001", "failed", digest(identifier, "platform::REQ-001"),
                       ["platform::REQ-001:AC-01"], ["web::frontend"]),
                target("platform::REQ-002", "passed", digest(identifier, "platform::REQ-002"),
                       ["platform::REQ-002:AC-01"], ["api::backend"]),
            ]),
            workspace_result("api", "services/api", "passed", targets=[
                target("api::TECH-030", "passed", digest(identifier, "api::TECH-030"),
                       bindings=["api::backend"]),
            ], commands=[command_result("api", "backend", "/bin/true", ["tests/test_report.py"],
                                        ["platform::REQ-002:AC-01"])]),
            workspace_result("web", "apps/web", "failed", targets=[
                target("web::TECH-010", "failed", digest(identifier, "web::TECH-010"),
                       bindings=["web::frontend"]),
            ], commands=[command_result("web", "frontend", "/bin/false",
                                        ["tests/auth/test_login.py"], ["platform::REQ-001:AC-01"],
                                        status="failed", exit_code=1)]),
        ]
    elif identifier == "MULTI-015":
        workspaces = [
            workspace_result("platform", ".", "passed", targets=[
                target("platform::REQ-001", "passed", digest(identifier, "platform::REQ-001"),
                       ["platform::REQ-001:AC-01"], ["web::frontend"]),
            ]),
            workspace_result("api", "services/api", "passed_with_warnings",
                             diagnostics=[{**NO_TARGET, "source": {
                                 "kind": "file", "workspaceId": "api", "path": ".spec/bitz.yaml"}}]),
            workspace_result("web", "apps/web", "passed", targets=[
                target("web::TECH-010", "passed", digest(identifier, "web::TECH-010"),
                       bindings=["web::frontend"]),
            ], commands=[command_result("web", "frontend", "/bin/true",
                                        ["tests/auth/test_login.py"], ["platform::REQ-001:AC-01"])]),
        ]
    else:
        # 全体で対象0件。workspace単位は警告、複合workspace全体だけをerror／blockedとする。
        workspaces = [
            workspace_result(workspace_id, path, "passed_with_warnings",
                             diagnostics=[{**NO_TARGET, "source": {
                                 "kind": "file", "workspaceId": workspace_id,
                                 "path": ".spec/bitz.yaml"}}])
            for workspace_id, path in (("platform", "."), ("api", "services/api"), ("web", "apps/web"))
        ]
    diagnostics = []
    if identifier == "MULTI-016":
        diagnostics = [{"code": "SPEC-VERIFY-BLOCKED-002", "severity": "error",
                        "resultStatus": "blocked", "summary": "検証対象がありません",
                        "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"}}]
    return {
        "schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": status,
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": workspaces,
        "revision": {"commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": diagnostics,
    }


def check_digests(identifier, repository, result):
    """通過targetのDigestを、入力treeからの導出（参照計算B）と照合する。"""
    checked = 0
    for workspace in result["workspaces"]:
        for entry in workspace["targetResults"]:
            if entry["contextDigest"] is None:
                continue
            derived = multi_crosscheck.canonical_bytes(
                multi_crosscheck.build(repository, entry["target"]))
            if multi_crosscheck.digest(derived) != entry["contextDigest"]:
                raise ValueError(f"{entry['target']}のDigestが参照計算Bと一致しません")
            literal = multi_reference.canonical_bytes(
                reviewed_digest_input(identifier, entry["target"]))
            if literal != derived:
                raise ValueError(f"{entry['target']}のreference AとBが一致しません")
            checked += 1
    if identifier == "MULTI-016" and checked:
        raise ValueError("対象0件のfixtureはDigestを持ちません")
    return checked


def check_corpus(identifier, repository, result):
    """fixtureが名乗る条件を、散文ではなくsetup後の入力から確かめる。"""
    _, _, documents = multi_crosscheck.load_workspaces(repository)
    if identifier == "MULTI-012":
        duplicates = [statement["id"] for statement
                      in multi_crosscheck.read_statements(documents["api::TECH-020"]["body"])]
        if len(duplicates) == len(set(duplicates)):
            raise ValueError("派生遮断のcaseは、規範文IDが重複するinvalid文書が必要です")
        if "api::TECH-020" not in multi_crosscheck.relations(documents["web::TECH-010"])["requires"]:
            raise ValueError("遮断されるtargetはinvalid文書へ強く依存する必要があります")
        if "api::TECH-020" in multi_crosscheck.relations(documents["api::TECH-030"])["requires"]:
            raise ValueError("独立targetはinvalid文書へ依存しない必要があります")
    if identifier == "MULTI-013":
        if {document["workspaceId"] for document in documents.values()} != {"platform", "web"}:
            raise ValueError("共有bindingのcaseは、すべてのworkspaceが対象を持つ必要があります")
    if identifier == "MULTI-015":
        if any(document["workspaceId"] == "api" for document in documents.values()):
            raise ValueError("対象0件のmemberはSPECを持ちません")
    if identifier == "MULTI-016":
        if documents:
            raise ValueError("全体0件のcaseはSPECを持ちません")
    if identifier == "MULTI-014":
        configs = (repository / multi_reference.WEB_CONFIG_PATH).read_text(encoding="utf-8")
        if "/bin/false" not in configs:
            raise ValueError("失敗継続のcaseは、失敗するcommandが必要です")
    # bindingを実行するcommandは、実行結果を持つworkspaceが所有する。
    for workspace in result["workspaces"]:
        for command in workspace["commands"]:
            if command["workspaceId"] != workspace["id"]:
                raise ValueError("command実体は所有workspaceへ置く必要があります")
    executed = {command["bindingId"] for workspace in result["workspaces"]
                for command in workspace["commands"]}
    referenced = {binding for workspace in result["workspaces"]
                  for entry in workspace["targetResults"] for binding in entry["bindingRefs"]}
    if referenced != executed:
        raise ValueError("参照されたbindingと実行したbindingが一致しません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in DESCRIPTIONS:
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
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果が審査済み期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-verify-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    check_corpus(identifier, repository, result)
                    check_digests(identifier, repository, result)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
