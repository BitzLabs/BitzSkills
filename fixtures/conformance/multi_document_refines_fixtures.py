"""複合ワークスペースで、他のワークスペースの文書が起点の文書を修飾した文書IDで`refines`するとき、その規範文も対象規範文に含めることを固定する（Coreの公開操作は実行しない）。

実装の確認事項C54に対応する。単一ワークスペースの対は`document_refines_fixtures.py`（`SINGLE-169-*`）である。

関係・トレースモデル §6.4の規則1は、文書を起点にした場合、起点の文書を文書IDで`refines`する適用可能な文書も具体化文書とし、その規範文を対象規範文に含めると定める。
複合ワークスペースでは、他のワークスペースの文書が修飾した文書ID（`platform::REQ-001`）で`refines`する場合も同じである（修飾IDは複合ワークスペース仕様 §4）。
規則2（規範文を起点にした場合）は、文書IDで`refines`する文書の規範文を含めない。修正前のCoreは、文書IDで`refines`する文書の規範文を対象規範文に含めず、
その文書は閉包に入るのに、制約台帳、カバレッジ、`verify`の`statements`と実行するテスト割当てに現れなかった。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-055-01` | `context platform::REQ-001 --purpose verify --detail compact` | `web`の`TECH-010`（`MUST`1件、テスト対応あり）が`platform::REQ-001`を文書IDで`refines`する | `passed`／0。制約台帳とカバレッジに`web::TECH-010:C-01`が修飾IDで入る。横断のエッジは`refines`の1件 |
| `MULTI-055-02` | `verify platform::REQ-001` | `web`の`TECH-010`はテスト対応なし | `blocked`／2。`statements`に`web::TECH-010:C-01`が入り、`CTX-COVERAGE-TEST-001`（発生元は`web`） |
| `MULTI-055-03` | `verify platform::REQ-001:AC-01`（対照） | `MULTI-055-02`と同じ入力 | `passed`／0。規範文を起点にした場合は`web::TECH-010:C-01`を含めない（修正前のCoreも通る） |
| `MULTI-055-04` | `verify platform::REQ-001` | `MULTI-055-01`と同じ入力 | `passed`／0。`web`のテスト割当ても実行し、`bindingRefs`は`platform::p`、`web::t` |

どのケースも、ルート`platform`（`.`）、メンバー`web`（`apps/web`）を宣言し、`.`で実行する。`platform`の`REQ-001`（`approved`、`MUST`1件、コマンド`p`のテスト対応）を、
`web`の`TECH-010`（`approved`、`MUST`1件`C-01`）が`platform::REQ-001`で`refines`する。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、`multi_crosscheck`の木構造からの導出B）のバイト列の一致を要求する。対象規範文、横断のエッジ、カバレッジの診断は、準備手順の後の入力の木構造から導く。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference, multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import compare_state, observe
from .multi_related_advisory_fixtures import reference_edges

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}
ACTOR = "TargetSystem"
MEMBERS = [("web", "apps/web")]
ROOT_REQ = "platform::REQ-001"
WEB_TECH = "web::TECH-010"
ROOT_REQ_PATH = ".spec/requirements/REQ-001.md"
WEB_TECH_PATH = "apps/web/.spec/technical/TECH-010.md"
ROOT_TEST_PATH = "tests/p.py"
WEB_TEST_PATH = "apps/web/tests/t.py"
TITLES = {ROOT_REQ: "ルートの共通基準", WEB_TECH: "Webの実装方針"}
TEXTS = {ROOT_REQ: "秘密情報を出力しない", WEB_TECH: "画面に利用者のIDを表示しない"}
LABELS = {ROOT_REQ: "AC-01", WEB_TECH: "C-01"}
STATEMENTS = {ROOT_REQ: "platform::REQ-001:AC-01", WEB_TECH: "web::TECH-010:C-01"}
ROOT_CONFIG_VERIFY = 'verify:\n  commands:\n    p:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'

# id: dict(op, argv, root, variant, defect, description)。variantは`web::TECH-010`のテスト対応: `tested`（あり）、`untested`（なし）。
#   defect: 修正前のCoreが対象規範文を取りこぼし、結果が異なる欠陥のケースか（対照は修正前のCoreも通る）。
CASES = {
    "MULTI-055-01": dict(op="context", argv=["context", ROOT_REQ, "--purpose", "verify", "--detail", "compact"], root=ROOT_REQ,
                         variant="tested", defect=True,
                         description="別のワークスペースの文書が修飾した文書IDでrefinesするとき、その規範文がcontextの制約台帳とカバレッジに修飾IDで入る"),
    "MULTI-055-02": dict(op="verify", argv=["verify", ROOT_REQ], root=ROOT_REQ, variant="untested", defect=True,
                         description="別のワークスペースの文書が修飾した文書IDでrefinesするTECHの未テストのMUSTを、verifyがblockedにする"),
    "MULTI-055-03": dict(op="verify", argv=["verify", f"{ROOT_REQ}:AC-01"], root=f"{ROOT_REQ}:AC-01", variant="untested", defect=False,
                         description="対照: 規範文を起点にしたverifyは、文書IDでrefinesする別のワークスペースの文書の規範文を対象にしない"),
    "MULTI-055-04": dict(op="verify", argv=["verify", ROOT_REQ], root=ROOT_REQ, variant="tested", defect=True,
                         description="別のワークスペースの文書が修飾した文書IDでrefinesするTECHのテスト割当ても、verifyが実行する"),
}


# --- 入力 -------------------------------------------------------------------------------

def body(identifier):
    label, local = LABELS[identifier], identifier.partition("::")[2]
    head = f"# {local} {TITLES[identifier]}\n\n"
    if identifier == ROOT_REQ:
        return (head + "## Intent\n\nワークスペースの基準を定める。\n\n## Acceptance Criteria\n\n"
                f"- [{local}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {TEXTS[identifier]}。\n\n"
                "## Verification\n\nCore実装後に確認する。現時点では未証明。\n")
    return (head + "## Context\n\n実装方針を定める。\n\n## Constraints\n\n"
            f"- [{local}:{label}] [ACTOR:{ACTOR}] [ALWAYS] [MUST] [CONSTRAINT] {TEXTS[identifier]}。\n")


def test_entries(identifier, variant):
    """修飾しない宣言（ワークスペース内のパス・規範文ID）。"""
    local = identifier.partition("::")[2]
    if identifier == ROOT_REQ:
        return [{"path": "tests/p.py", "covers": [f"{local}:{LABELS[identifier]}"], "command": "p"}]
    if variant == "tested":
        return [{"path": "tests/t.py", "covers": [f"{local}:{LABELS[identifier]}"], "command": "t"}]
    return []


def document(identifier, variant):
    local = identifier.partition("::")[2]
    head = f"---\nid: {local}\ntitle: {TITLES[identifier]}\nstatus: approved\n"
    if identifier == WEB_TECH:
        head += f"relations:\n  refines: [{ROOT_REQ}]\n"
    for entry in test_entries(identifier, variant):
        head += f"tests:\n  - path: {entry['path']}\n    covers: [{', '.join(entry['covers'])}]\n    command: {entry['command']}\n"
    return (head + "---\n\n" + body(identifier)).encode()


def reviewed_inputs(identifier):
    variant = CASES[identifier]["variant"]
    inputs = {
        multi_reference.ROOT_CONFIG_PATH: (multi_reference.root_config(MEMBERS) + ROOT_CONFIG_VERIFY).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "t").encode(),
        ROOT_REQ_PATH: document(ROOT_REQ, variant),
        WEB_TECH_PATH: document(WEB_TECH, variant),
        ROOT_TEST_PATH: b"def test_p():\n    assert True\n",
    }
    if variant == "tested":
        inputs[WEB_TEST_PATH] = b"def test_t():\n    assert True\n"
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reviewed_status(identifier)
    return {
        "fixtureId": identifier, "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0},
    }


# --- レビュー済みの対象規範文・診断・状態（リテラル） -----------------------------------------------

def reviewed_targets(identifier):
    """対象規範文（`contextDocuments`の順）。規範文を起点にした場合は指定した規範文だけ（規則2）。"""
    return [STATEMENTS[ROOT_REQ]] if ":" in CASES[identifier]["root"].partition("::")[2] else [STATEMENTS[ROOT_REQ], STATEMENTS[WEB_TECH]]


def reviewed_untested(identifier):
    if CASES[identifier]["variant"] == "tested":
        return []
    return [target for target in reviewed_targets(identifier) if target == STATEMENTS[WEB_TECH]]


def reviewed_diagnostics(identifier):
    """目的`verify`の`MUST`の未テストは`blocked`（`context` §10）。発生元は規範文を所有するワークスペース（`web`）。"""
    return [{"code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked",
             "summary": f"対象規範文MUST {target}にテスト対応がありません",
             "source": {"kind": "file", "workspaceId": "web", "path": ".spec/technical/TECH-010.md"}}
            for target in reviewed_untested(identifier)]


def reviewed_status(identifier):
    return "blocked" if reviewed_diagnostics(identifier) else "passed"


# --- レビュー済みのハッシュ値の材料（参照計算A） -------------------------------------------

def material_statement(identifier):
    return {"id": STATEMENTS[identifier], "actor": ACTOR, "activation": {"kind": "ALWAYS", "text": None}, "modality": "MUST",
            "reason": None, "operation": {"kind": "CONSTRAINT", "text": TEXTS[identifier]}, "extensions": []}


def material_tests(identifier, variant):
    return [{"path": entry["path"], "covers": [f"{identifier.partition('::')[0]}::{covered}" for covered in entry["covers"]],
             "command": entry["command"]} for entry in test_entries(identifier, variant)]


def material_document(identifier, variant):
    workspace = identifier.partition("::")[0]
    refines = [ROOT_REQ] if identifier == WEB_TECH else []
    return {
        "id": identifier, "workspaceId": workspace, "kind": "requirement" if identifier == ROOT_REQ else "technical",
        "status": "approved", "applicability": "applicable",
        "frontmatter": {"id": identifier, "title": TITLES[identifier], "status": "approved",
                        "relations": {**digest_reference.EMPTY_RELATIONS, "refines": refines}, "implements": [],
                        "tests": material_tests(identifier, variant), "verify": None, "changes": []},
        "bodyText": body(identifier), "statements": [material_statement(identifier)],
        "strongRelations": [{"relation": "refines", "target": target} for target in refines],
    }


def reviewed_digest_input(identifier):
    """目的`verify`のハッシュ値の材料。`web`は、テスト割当てを収録するときだけ`verifyTimeouts`と`commands`を持つ。"""
    case = CASES[identifier]
    variant, tested = case["variant"], case["variant"] == "tested"
    settings_workspaces = [{"id": name, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"} for name in ("platform", "web")]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": "platform", "roots": [case["root"]],
        # 起点ワークスペースが先頭、以降はID辞書順。
        "workspaces": [{"id": "platform", "path": "."}, {"id": "web", "path": "apps/web"}],
        "documents": [material_document(ROOT_REQ, variant), material_document(WEB_TECH, variant)],
        "crossWorkspaceEdges": [{"relation": "refines", "source": WEB_TECH, "target": ROOT_REQ}],
        "settings": {
            "workspaces": settings_workspaces,
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "platform", "timeoutSeconds": 300},
                               *([{"workspaceId": "web", "timeoutSeconds": 300}] if tested else [])],
            "commands": [{"workspaceId": "platform", "name": "p", "argv": ["/bin/true", "{tests}"], "cwd": "."},
                         *([{"workspaceId": "web", "name": "t", "argv": ["/bin/true", "{tests}"], "cwd": "."}] if tested else [])],
        },
    }


def context_digest(identifier):
    return multi_reference.digest(multi_reference.canonical_bytes(reviewed_digest_input(identifier)))


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reference_document(identifier):
    workspace = identifier.partition("::")[0]
    root = identifier == ROOT_REQ
    return {"id": identifier, "kind": "requirement" if root else "technical", "status": "approved",
            "role": "root" if root else "refinement", "path": ROOT_REQ_PATH if root else ".spec/technical/TECH-010.md",
            "projection": "reference", "reachedBy": ["root"] if root else [f"refines:{identifier}"],
            "workspaceId": workspace, "expandable": True, "untrustedText": True}


def ledger_entry(identifier):
    root = identifier == ROOT_REQ
    return {"id": STATEMENTS[identifier], "documentId": identifier, "documentRole": "root" if root else "refinement",
            "modality": "MUST", "reason": None, "actor": ACTOR, "activation": {"kind": "ALWAYS"},
            "operation": {"kind": "CONSTRAINT", "text": TEXTS[identifier]}}


def reviewed_context_result(identifier):
    case = CASES[identifier]
    targets, untested = reviewed_targets(identifier), reviewed_untested(identifier)
    return {
        "schemaVersion": "1.0", "operation": "context", "status": reviewed_status(identifier), "purpose": "verify",
        "workspace": {"id": "platform", "path": "."}, "roots": [case["root"]], "contextDigest": context_digest(identifier),
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                       "workspaces": [{"id": "platform", "path": "."}, {"id": "web", "path": "apps/web"}],
                       "crossWorkspaceEdges": [{"relation": "refines", "source": WEB_TECH, "target": ROOT_REQ}]},
        "projection": {"detail": "compact", "expanded": []},
        "documents": [reference_document(ROOT_REQ), reference_document(WEB_TECH)],
        "constraintLedger": {"statements": [ledger_entry(ROOT_REQ), ledger_entry(WEB_TECH)]},
        "coverage": {
            # 目的`verify`は`addressed`を空にし、すべて`unaddressed`に置く（TASKを使わない）。
            "must": {"total": list(targets), "addressed": [], "tested": [t for t in targets if t not in untested],
                     "unaddressed": list(targets), "untested": list(untested)},
            "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": reviewed_diagnostics(identifier),
    }


def executed_command(workspace, name, test, covers):
    return {
        "bindingId": f"{workspace}::{name}", "workspaceId": workspace, "name": name, "status": "passed", "termination": "exit",
        "cwd": ".", "argv": ["/bin/true", test], "tests": [test], "covers": [covers], "exitCode": 0, "timeoutSeconds": 300,
        "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def reviewed_verify_result(identifier):
    case = CASES[identifier]
    targets, status = reviewed_targets(identifier), reviewed_status(identifier)
    blocked = status == "blocked"
    # 実行順は、ルートのテスト割当てを先頭に、以降をワークスペースIDの辞書順（`verify` §7、確認事項C62）。
    commands = [] if blocked else [executed_command("platform", "p", ROOT_TEST_PATH, STATEMENTS[ROOT_REQ])]
    if not blocked and STATEMENTS[WEB_TECH] in targets and case["variant"] == "tested":
        commands.append(executed_command("web", "t", "tests/t.py", STATEMENTS[WEB_TECH]))
    entry = {"target": case["root"], "status": status, "contextDigest": context_digest(identifier), "statements": list(targets),
             "bindingRefs": [] if blocked else [command["bindingId"] for command in commands],
             "diagnostics": reviewed_diagnostics(identifier)}
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "platform", "path": "."}, "targetResults": [entry],
        "revision": {"commit": COMMIT, "dirty": False}, "commands": commands, "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier):
    return reviewed_context_result(identifier) if CASES[identifier]["op"] == "context" else reviewed_verify_result(identifier)


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def result_targets(result):
    if result["operation"] == "context":
        return [item["id"] for item in result["constraintLedger"]["statements"]]
    return result["targetResults"][0]["statements"]


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def reference_targets(documents, root, mode="current"):
    """関係・トレースモデル §6.4から、起点の対象規範文を修飾IDで導く。

    - 選択済みの規範文を規範文IDで`refines`する適用可能な文書は、どの起点でも具体化文書として規範文を加える。
    - 文書IDの`refines`を辿るのは、規則1（規範文のある文書の起点）の起点の文書と、見つけた具体化文書である。規則2の起点の所有文書は、文書IDの`refines`を辿る起点にしない。
    `mode`: `current`は上の規則、`main`は文書IDの`refines`を辿らない（`origin/main`のCoreの再現）。
    """
    statements = {name: [f"{item['workspaceId']}::{statement['id']}" for statement in digest_crosscheck.read_statements(item["body"])]
                  for name, item in documents.items()}
    owner = multi_crosscheck.owner(root)
    by_document = root == owner
    selected_statements = set(statements[owner]) if by_document else {root}
    followed = {owner} if by_document and statements[owner] and mode != "main" else set()
    targets, found = set(selected_statements), set()
    changed = True
    while changed:
        changed = False
        for name in sorted(documents):
            item = documents[name]
            if name in found or name == owner or item["frontmatter"]["status"] != "approved":
                continue
            refined = multi_crosscheck.relations(item)["refines"]
            if any(ref in selected_statements for ref in refined) or (mode != "main" and any(ref in followed for ref in refined)):
                found.add(name)
                selected_statements.update(statements[name])
                targets.update(statements[name])
                followed.add(name)
                changed = True
    return sorted(targets, key=lambda target: (multi_crosscheck.owner(target) != owner, target))


def reference_diagnostics(documents, closure, targets):
    tested = {covered for name in closure for entry in multi_crosscheck.tests(documents[name]) for covered in entry["covers"]}
    found = []
    for target in targets:
        name = multi_crosscheck.owner(target)
        if target not in tested:
            path = {ROOT_REQ: ROOT_REQ_PATH, WEB_TECH: ".spec/technical/TECH-010.md"}[name]
            found.append({"code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked",
                          "summary": f"対象規範文MUST {target}にテスト対応がありません",
                          "source": {"kind": "file", "workspaceId": documents[name]["workspaceId"], "path": path}})
    return sorted(found, key=lambda item: (item["source"]["workspaceId"], item["source"]["path"], item["code"]))


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    _, _, documents = multi_crosscheck.load_workspaces(repository)
    closure, _ = multi_crosscheck.closure(documents, case["root"])
    if closure != [ROOT_REQ, WEB_TECH]:
        raise ValueError("閉包は起点と、それを文書IDで`refines`する`web::TECH-010`の2文書である必要があります")
    # 文書IDで`refines`し、規範文IDでは`refines`していない（修正前のCoreが取りこぼす形）。
    if multi_crosscheck.relations(documents[WEB_TECH])["refines"] != [ROOT_REQ]:
        raise ValueError("`web::TECH-010`は`platform::REQ-001`を修飾した文書IDで`refines`する必要があります")
    targets = reference_targets(documents, case["root"])
    old = reference_targets(documents, case["root"], mode="main")
    if targets != reviewed_targets(identifier) or result_targets(result) != targets:
        raise ValueError("対象規範文が参照計算と異なります")
    if (old != targets) != case["defect"] or (case["defect"] and old != [STATEMENTS[ROOT_REQ]]):
        raise ValueError("修正前のCoreの再現との関係が、種類（欠陥または対照）と一致しません")
    derived = reference_diagnostics(documents, closure, targets)
    if derived != reviewed_diagnostics(identifier):
        raise ValueError("入力から導く診断がレビュー済みの期待値と異なります")
    status = "blocked" if derived else "passed"
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    if case["op"] == "context":
        if result["diagnostics"] != derived:
            raise ValueError("診断の置き場所または内容が参照計算と異なります")
        if result["resolution"]["crossWorkspaceEdges"] != reference_edges(documents, closure):
            raise ValueError("横断のエッジが参照計算と異なります")
        if [item["id"] for item in result["documents"]] != closure:
            raise ValueError("文書が閉包と異なります")
    else:
        entry = result["targetResults"][0]
        if result["diagnostics"] or entry["diagnostics"] != derived:
            raise ValueError("`verify`の診断は検証対象の`diagnostics`にだけあります")
        # `blocked`はテストを開始しない。`passed`は、対象規範文を`covers`するテスト対応のコマンドを、ルート、ワークスペースIDの順に実行する。
        covered = [(multi_crosscheck.owner(target).partition("::")[0], target) for target in targets
                   if target in {c for name in closure for e in multi_crosscheck.tests(documents[name]) for c in e["covers"]}]
        expected = [] if status == "blocked" else [f"{workspace}::{'p' if workspace == 'platform' else 't'}" for workspace, _ in covered]
        if [command["bindingId"] for command in result["commands"]] != expected or entry["bindingRefs"] != expected:
            raise ValueError("実行したテスト割当てが対象規範文の`covers`から導く形と異なります")


def check_digest(identifier, repository, result):
    case = CASES[identifier]
    derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, case["root"], "verify"))
    digest = result["contextDigest"] if case["op"] == "context" else result["targetResults"][0]["contextDigest"]
    if multi_crosscheck.digest(derived) != digest:
        raise ValueError("ハッシュ値が参照計算Bと一致しません")
    if multi_reference.canonical_bytes(reviewed_digest_input(identifier)) != derived:
        raise ValueError("ハッシュ値の参照計算AとBが一致しません")


# --- 書き出しと監査 ---------------------------------------------------------------------

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
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / f"expected/{CASES[identifier]['op']}.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-document-refines-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


def actual_files(fixture):
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
        fixture = root / "multi" / identifier
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-document-refines-") as temporary:
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
                    _, _, documents = multi_crosscheck.load_workspaces(repository)
                    for item in documents.values():
                        Draft202012Validator({"$ref": "#/$defs/" + kinds[item["kind"]],
                                              "$defs": schema["$defs"]}).validate(item["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
