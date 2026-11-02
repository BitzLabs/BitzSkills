"""複合ワークスペースの`context`と`verify`が、横断する`related`の参照切れの警告を返し、`related`を横断のエッジに収録しないことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C78・C79に対応する。単一ワークスペースの対は`related_advisory_fixtures.py`（`SINGLE-168-*`）である。

- C78: `related`の参照切れは、`check`が診断`SPEC-RELATION-ADVISORY-MISSING-001`（`warning`）で返していたが、`context`と`verify`は捨てていた。
  関係・トレースモデル §3と診断レジストリ（`RELATION-TARGET-MISSING-RELATED`、返しうる操作は`context`、`check`、`verify`、継続単位は`skip-edge`）、
  `context` §10、`verify` §9は、閉包の文書が宣言する`related`の参照切れを、コンテキストまたは検証対象を失敗させず、成功・失敗のどちらの結果にも加えると定める。
  `verify`では検証対象の`diagnostics`に置く。参照先が別のワークスペースの文書でも同じである（宣言する文書が起点ワークスペースの文書の場合）。
- C79: 複合ワークスペース仕様 §6は、`related`は閉包を増やさないので、解決できても横断のエッジ（`resolution.crossWorkspaceEdges`）に収録しないと定める
  （`relation`の列挙値は`requires`、`refines`、`addresses`、`supersedes`）。同じ文書が宣言する横断の強い関係は収録する。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-054-01` | `context web::REQ-101 --purpose verify --detail compact` | `web::REQ-101`が`platform::REQ-001`を`requires`し、`api::REQ-201`（存在する）と`platform::REQ-099`（存在しない）を`related`する | `passed_with_warnings`／0。警告1件。横断のエッジは`requires`の1件だけ |
| `MULTI-054-02` | `verify web::REQ-101` | 同上 | `passed_with_warnings`／0。検証対象の`diagnostics`に警告1件 |
| `MULTI-054-03` | `context web::REQ-101 --purpose verify --detail compact`（対照） | 同上。ただし存在しない`platform::REQ-099`を`related`しない | `passed`／0。横断のエッジは`requires`の1件だけ（修正前のCoreも通る） |
| `MULTI-054-04` | `context web::REQ-101 --purpose verify --detail compact` | `01`と同じ`related`に加え、`requires`が存在しない`platform::REQ-098`も宣言する | `failed`／1。警告1件と強い関係の診断1件 |

どのケースも、ルート`platform`（`.`）、メンバー`web`（`apps/web`）、`api`（`services/api`）を、この順で宣言し、`.`で実行する。`web`の`REQ-101`だけがテスト対応を持つ。
`api::REQ-201`は`related`の参照先として存在するが、閉包には入らない。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、`multi_crosscheck`の木構造からの導出B）のバイト列の一致を要求する。警告、横断のエッジ、閉包の文書は、準備手順の後の入力の木構造から導く。
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
from .related_advisory_fixtures import (ADVISORY_CODE, ADVISORY_SUMMARY, EMPTY_BUCKET, EXIT_BY_STATUS, STRONG, STRONG_CODE, STRONG_SUMMARY,
                                       old_core_result, reference_status, result_diagnostics)

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = [("web", "apps/web"), ("api", "services/api")]
ROOT_REQ_PATH = ".spec/requirements/REQ-001.md"
WEB_REQ_PATH = "apps/web/.spec/requirements/REQ-101.md"
API_REQ_PATH = "services/api/.spec/requirements/REQ-201.md"
WEB_TEST_PATH = "apps/web/tests/t.py"
TARGET = "web::REQ-101"
STATEMENT = "web::REQ-101:AC-01"
TITLES = {"platform::REQ-001": "ルートの共通基準", "web::REQ-101": "Webの画面の基準", "api::REQ-201": "APIの認証の基準"}
TEXTS = {"platform::REQ-001": "秘密情報を出力しない", "web::REQ-101": "画面に利用者のIDを表示しない",
         "api::REQ-201": "APIの応答に秘密情報を含めない"}

# id: dict(argv, op, variant, description)。variantは`web::REQ-101`の関係の宣言: `warn`（存在しない`related`を持つ）、`clean`（持たない）、
# `failed`（存在しない`related`と、存在しない`requires`を持つ）。
CASES = {
    "MULTI-054-01": dict(op="context", argv=["context", TARGET, "--purpose", "verify", "--detail", "compact"], variant="warn",
                         description="複合ワークスペースのcontextが、横断のrelatedの参照切れの警告を返し、解決できる横断のrelatedをエッジに収録しない"),
    "MULTI-054-02": dict(op="verify", argv=["verify", TARGET], variant="warn",
                         description="複合ワークスペースのverifyが、横断のrelatedの参照切れの警告を検証対象のdiagnosticsに置く"),
    "MULTI-054-03": dict(op="context", argv=["context", TARGET, "--purpose", "verify", "--detail", "compact"], variant="clean",
                         description="対照: 解決できる横断のrelatedはエッジに収録せず、同じ文書の横断のrequiresは収録する"),
    "MULTI-054-04": dict(op="context", argv=["context", TARGET, "--purpose", "verify", "--detail", "compact"], variant="failed",
                         description="強い関係の参照切れで失敗する複合ワークスペースのcontextにも、横断のrelatedの警告を並べる"),
}
# 修正前のCoreの再現: `context`と`verify`が警告を捨てる。対照の`MULTI-054-03`は警告がないので同じ。
RELATIONS = {
    "warn": {"requires": ["platform::REQ-001"], "related": ["api::REQ-201", "platform::REQ-099"]},
    "clean": {"requires": ["platform::REQ-001"], "related": ["api::REQ-201"]},
    "failed": {"requires": ["platform::REQ-001", "platform::REQ-098"], "related": ["api::REQ-201", "platform::REQ-099"]},
}


# --- 入力 -------------------------------------------------------------------------------

def body(identifier):
    local = identifier.partition("::")[2]
    return (
        f"# {local} {TITLES[identifier]}\n"
        "\n"
        "## Intent\n"
        "\n"
        "ワークスペースの基準を定める。\n"
        "\n"
        "## Acceptance Criteria\n"
        "\n"
        f"- [{local}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {TEXTS[identifier]}。\n"
        "\n"
        "## Verification\n"
        "\n"
        "Core実装後に確認する。現時点では未証明。\n"
    )


def document(identifier, relations=None, tested=False):
    local = identifier.partition("::")[2]
    head = f"---\nid: {local}\ntitle: {TITLES[identifier]}\nstatus: approved\n"
    if relations:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations.items())
    if tested:
        head += f"tests:\n  - path: tests/t.py\n    covers: [{local}:AC-01]\n    command: t\n"
    return (head + "---\n\n" + body(identifier)).encode()


def reviewed_inputs(identifier):
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "t").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
        ROOT_REQ_PATH: document("platform::REQ-001"),
        WEB_REQ_PATH: document(TARGET, RELATIONS[CASES[identifier]["variant"]], tested=True),
        API_REQ_PATH: document("api::REQ-201"),
        WEB_TEST_PATH: b"def test_t():\n    assert True\n",
    }


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reference_status(reviewed_diagnostics(identifier))
    return {
        "fixtureId": identifier, "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0},
    }


# --- レビュー済みの診断 -----------------------------------------------------------------

def advisory(evidence):
    return {"code": ADVISORY_CODE, "severity": "warning", "resultStatus": "passed_with_warnings", "summary": ADVISORY_SUMMARY,
            "source": {"kind": "file", "workspaceId": "web", "path": ".spec/requirements/REQ-101.md", "key": "relations.related"},
            "evidence": evidence}


def strong_missing(evidence):
    return {"code": STRONG_CODE, "severity": "error", "resultStatus": "failed", "summary": STRONG_SUMMARY,
            "source": {"kind": "file", "workspaceId": "web", "path": ".spec/requirements/REQ-101.md", "key": "relations.requires"},
            "evidence": evidence}


def reviewed_diagnostics(identifier):
    """リテラルの期待値。同じ`path`では`code`の辞書順（ADVISORYはMISSINGより前。結果・診断・終了コード §7）。"""
    variant = CASES[identifier]["variant"]
    if variant == "clean":
        return []
    if variant == "warn":
        return [advisory("platform::REQ-099")]
    return [advisory("platform::REQ-099"), strong_missing("platform::REQ-098")]


# --- レビュー済みのハッシュ値の材料（参照計算A） -------------------------------------------

def statement(identifier):
    return {"id": f"{identifier}:AC-01", "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None}, "modality": "MUST",
            "reason": None, "operation": {"kind": "CONSTRAINT", "text": TEXTS[identifier]}, "extensions": []}


def material_document(identifier, relations, strong, tests):
    workspace = identifier.partition("::")[0]
    return {
        "id": identifier, "workspaceId": workspace, "kind": "requirement", "status": "approved", "applicability": "applicable",
        "frontmatter": {"id": identifier, "title": TITLES[identifier], "status": "approved",
                        "relations": {**digest_reference.EMPTY_RELATIONS, **relations}, "implements": [], "tests": tests,
                        "verify": None, "changes": []},
        "bodyText": body(identifier), "statements": [statement(identifier)],
        "strongRelations": [{"relation": key, "target": target} for key, target in strong],
    }


def reviewed_digest_input(identifier):
    """`context web::REQ-101 --purpose verify`のハッシュ値の材料。`related`は閉包を増やさず、横断のエッジにも強い関係にも入らない。"""
    relations = RELATIONS[CASES[identifier]["variant"]]
    if CASES[identifier]["variant"] == "failed":
        raise ValueError("`failed`はハッシュ値を計算しません")
    web = material_document(TARGET, relations, [("requires", "platform::REQ-001")],
                            [{"path": "tests/t.py", "covers": [STATEMENT], "command": "t"}])
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": "web", "roots": [TARGET],
        # 起点ワークスペースが先頭、以降はID辞書順。
        "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "platform", "path": "."}],
        "documents": [material_document("platform::REQ-001", {}, [], []), web],
        "crossWorkspaceEdges": [{"relation": "requires", "source": TARGET, "target": "platform::REQ-001"}],
        "settings": {
            "workspaces": [{"id": "platform", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
                           {"id": "web", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "web", "timeoutSeconds": 300}],
            "commands": [{"workspaceId": "web", "name": "t", "argv": ["/bin/true", "{tests}"], "cwd": "."}],
        },
    }


def context_digest(identifier):
    return multi_reference.digest(multi_reference.canonical_bytes(reviewed_digest_input(identifier)))


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reference_document(identifier, role, reached_by):
    workspace, _, local = identifier.partition("::")
    path = {"web": ".spec/requirements/REQ-101.md", "platform": ".spec/requirements/REQ-001.md"}[workspace]
    return {"id": identifier, "kind": "requirement", "status": "approved", "role": role, "path": path, "projection": "reference",
            "reachedBy": [reached_by], "workspaceId": workspace, "expandable": True, "untrustedText": True}


def reviewed_context_result(identifier, context_digest_value):
    case = CASES[identifier]
    failed = case["variant"] == "failed"
    status = reference_status(reviewed_diagnostics(identifier))
    workspaces = [{"id": "web", "path": "apps/web"}] if failed else [{"id": "web", "path": "apps/web"}, {"id": "platform", "path": "."}]
    edges = [] if failed else [{"relation": "requires", "source": TARGET, "target": "platform::REQ-001"}]
    ledger = [] if failed else [{
        "id": STATEMENT, "documentId": TARGET, "documentRole": "root", "modality": "MUST", "reason": None, "actor": "TargetSystem",
        "activation": {"kind": "ALWAYS"}, "operation": {"kind": "CONSTRAINT", "text": TEXTS[TARGET]}}]
    must = ({"total": [STATEMENT], "addressed": [], "tested": [STATEMENT], "unaddressed": [STATEMENT], "untested": []}
            if not failed else dict(EMPTY_BUCKET))
    return {
        "schemaVersion": "1.0", "operation": "context", "status": status, "purpose": "verify",
        "workspace": {"id": "web", "path": "apps/web"}, "roots": [TARGET],
        "contextDigest": None if failed else context_digest_value,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": not failed, "documentCount": 0 if failed else 2, "unresolvedStrongRelations": 1 if failed else 0,
                       "workspaces": workspaces, "crossWorkspaceEdges": edges},
        "projection": {"detail": "compact", "expanded": []},
        "documents": [] if failed else [reference_document(TARGET, "root", "root"),
                                        reference_document("platform::REQ-001", "requirement", f"requires:{TARGET}")],
        "constraintLedger": {"statements": ledger},
        "coverage": {"must": must, "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": reviewed_diagnostics(identifier),
    }


def reviewed_verify_result(identifier, context_digest_value):
    diagnostics = reviewed_diagnostics(identifier)
    status = reference_status(diagnostics)
    entry = {"target": TARGET, "status": status, "contextDigest": context_digest_value, "statements": [STATEMENT],
             "bindingRefs": ["web::t"], "diagnostics": diagnostics}
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "web", "path": "apps/web"}, "targetResults": [entry],
        "revision": {"commit": COMMIT, "dirty": False},
        "commands": [{
            "bindingId": "web::t", "workspaceId": "web", "name": "t", "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", "tests/t.py"], "tests": ["tests/t.py"], "covers": [STATEMENT], "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier, context_digest_value):
    if CASES[identifier]["op"] == "context":
        return reviewed_context_result(identifier, context_digest_value)
    return reviewed_verify_result(identifier, context_digest_value)


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def expected_digest(identifier):
    return None if CASES[identifier]["variant"] == "failed" else context_digest(identifier)


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def declared_relations(document):
    return document["frontmatter"].get("relations", {})


def reference_diagnostics(documents, closure):
    """起点ワークスペースの閉包の文書が宣言する関係のうち、解決できないものを診断にする。

    他のワークスペースの文書の参照切れは検査しない（関係・トレースモデル §6.3、`context` §3）ので、この群の診断は起点ワークスペースの文書だけが宣言する。
    宣言の順に読み、鍵は発生元の`path`、`code`。同じ鍵は宣言の順（Pythonの整列は安定）。
    """
    found = []
    for name in closure:
        document = documents[name]
        if document["workspaceId"] != "web":
            continue
        for key in (*STRONG, "related"):
            for target in declared_relations(document).get(key, []):
                if digest_crosscheck.resolves(documents, multi_crosscheck.qualify("web", target)):
                    continue
                if key == "related":
                    found.append(advisory(target))
                elif key == "requires":
                    found.append(strong_missing(target))
                else:
                    raise ValueError("この群は`requires`以外の強い関係の参照切れを扱いません")
    return sorted(found, key=lambda item: (item["source"]["path"], item["code"]))


def reference_edges(documents, closure):
    """横断のエッジは、閉包の文書が宣言する、解決できる強い関係だけ（複合ワークスペース仕様 §6）。`related`は収録しない。"""
    edges = set()
    for name in closure:
        document = documents[name]
        for key in STRONG:
            for target in declared_relations(document).get(key, []):
                qualified = multi_crosscheck.qualify(document["workspaceId"], target)
                if qualified.partition("::")[0] != document["workspaceId"] and digest_crosscheck.resolves(documents, qualified):
                    edges.add((name, key, qualified))
    return [{"relation": key, "source": source, "target": target} for source, key, target in sorted(edges)]


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    _, _, documents = multi_crosscheck.load_workspaces(repository)
    closure, _ = multi_crosscheck.closure(documents, TARGET)
    if closure != ["platform::REQ-001", TARGET]:
        raise ValueError("閉包は起点と、`requires`で到達する`platform::REQ-001`の2文書である必要があります")
    derived = reference_diagnostics(documents, closure)
    if derived != reviewed_diagnostics(identifier):
        raise ValueError("入力から導く診断がレビュー済みの期待値と異なります")
    status = reference_status(derived)
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    if result_diagnostics(result) != derived:
        raise ValueError("診断が結果の木構造に重複しています、または置き場所が異なります")
    if case["op"] == "verify":
        if result["diagnostics"] or result["targetResults"][0]["diagnostics"] != derived:
            raise ValueError("`verify`の診断は検証対象の`diagnostics`にだけあります")
    # `related`に、存在する別のワークスペースの文書（`api::REQ-201`）と存在しない参照先（`platform::REQ-099`）がある。
    # 解決できる横断の`related`と横断の`requires`が同じ文書にあり、エッジの列挙が`related`を除くことを確かめられる入力である。
    web = documents[TARGET]
    resolvable = [target for target in declared_relations(web)["related"] if digest_crosscheck.resolves(documents, target)]
    if resolvable != ["api::REQ-201"] or "api::REQ-201" in closure:
        raise ValueError("解決できる横断の`related`は、閉包に入らない`api::REQ-201`だけである必要があります")
    if case["op"] == "context":
        edges = reference_edges(documents, closure)
        expected = [] if case["variant"] == "failed" else edges
        if edges != [{"relation": "requires", "source": TARGET, "target": "platform::REQ-001"}]:
            raise ValueError("横断のエッジは、同じ文書の横断の`requires`1件だけである必要があります")
        if result["resolution"]["crossWorkspaceEdges"] != expected:
            raise ValueError("横断のエッジが参照計算と異なります")
        if case["variant"] != "failed" and [item["id"] for item in result["documents"]] != [TARGET, "platform::REQ-001"]:
            raise ValueError("文書が閉包と異なります")
    if (old_core_result(result) != result) != any(item["code"] == ADVISORY_CODE for item in derived):
        raise ValueError("修正前のCoreの再現との関係が、種類（欠陥または対照）と一致しません")


def check_digest(identifier, repository, result):
    if CASES[identifier]["variant"] == "failed":
        return
    derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, TARGET, "verify"))
    digest = result["contextDigest"] if CASES[identifier]["op"] == "context" else result["targetResults"][0]["contextDigest"]
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
        (fixture / f"expected/{CASES[identifier]['op']}.json").write_text(_dump(reviewed_result(identifier, expected_digest(identifier))))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-related-advisory-") as temporary:
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
            if result != reviewed_result(identifier, expected_digest(identifier)):
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-related-advisory-") as temporary:
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
                        Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": schema["$defs"]}).validate(item["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
