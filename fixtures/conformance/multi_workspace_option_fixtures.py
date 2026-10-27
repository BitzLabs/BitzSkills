"""複合ワークスペースのメンバーの中から、`--workspace`でルートのIDを指定して作業ワークスペースを置き換えることを固定する（Coreの公開操作は実行しない）。

複合ワークスペース仕様 §3の5.は、「`--workspace <id>`は、カタログ内の**ルートまたはメンバー**のIDと完全に一致するIDで、作業ワークスペースを置き換える」と定める。
既存の`MULTI-029-02`は、ルートからメンバーのIDを指定する。メンバーの中からルートのIDを指定する肯定的なfixtureはなかった（実装の確認事項C7）。

2件とも、ルートワークスペース`platform`と、メンバー`web`（`apps/web`）、`api`（`services/api`）を置き、`apps/web`で実行する。`apps/web`の最寄りの設定のワークスペースは`web`で、
`--workspace platform`がなければ`web`が作業ワークスペースになる。ルートとメンバー`web`は、同じローカルID `REQ-001`の`approved`のREQを持つが、
タイトル・本文・規範文の数が異なり、どちらが解決されたかを結果から見分けられる。どの文書も関係を宣言しない（閉包と逆参照が結果を変えない）。

`MULTI-031-01`は`check --workspace platform --full`である。作業ワークスペースは`platform`（`workspace.path`は`.`）になり、`--full`の完全検査の対象は、
作業ワークスペースのすべての仕様文書（`platform::REQ-001`の1文書）だけである。メンバーの文書（`web::REQ-001`、`web::TECH-010`、`api::TECH-020`）は、強い関係の閉包にも直接の逆参照にも
入らないので対象にしない（`check` §3・§6、複合ワークスペース仕様 §7）。

`MULTI-031-02`は`context --workspace platform REQ-001 --purpose interpret`である。`--workspace`は非修飾IDを解決する基準のワークスペースを明示し（`context` §2）、
`REQ-001`は`platform::REQ-001`に解決される（`web::REQ-001`ではない）。起点ワークスペースは`platform`、`roots`は`["platform::REQ-001"]`で、コンテキスト一式は`platform::REQ-001`の1文書、
到達ワークスペースは`platform`の1件である。目的`interpret`は対象規範文を持たない（関係・トレースモデル §6.4）ので、制約台帳とカバレッジは空である。

期待値の根拠は規範文と、このモジュールの参照計算だけである。`MULTI-031-01`の件数と診断は`multi_check_fixtures.reference_check`（入力の木構造から導く）で、
`MULTI-031-02`の`contextDigest`は、独立に書いた2系統の参照計算（このモジュールのリテラルA、`multi_crosscheck`の木構造からの導出B）で、
`MULTI-031-02`の文書・件数・ワークスペースは、入力の木構造から導く`reference_context`で、それぞれリテラルの期待値と照合する。Coreの出力は期待値の根拠にしない。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_reference, multi_crosscheck, multi_reference
from .digest_crosscheck import read_statements
from .harness import git, setup
from .initial_fixtures import observe, compare_state
from .multi_check_fixtures import (MEMBERS, check_result_against_reference, document_path, front, reference_check,
                                   select_workspace, tech)

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CWD = "apps/web"
ROOT_REQ_PATH = ".spec/requirements/REQ-001.md"
WEB_REQ_PATH = "apps/web/.spec/requirements/REQ-001.md"
WEB_TECH_PATH = "apps/web/.spec/technical/TECH-010.md"
API_TECH_PATH = "services/api/.spec/technical/TECH-020.md"
ROOT_TITLE = "ルートの共通基準"
WEB_TITLE = "Webの画面の基準"
ROOT_BODY = (
    "# REQ-001 ルートの共通基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "ルートワークスペースの共通の基準を定める。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [WHEN] 保存した場合 [SHOULD] [REASON] 確認のため [THEN] 結果を返す。\n"
    "\n"
    "## Verification\n"
    "\n"
    "Core実装後に確認する。現時点では未証明。\n"
)
WEB_BODY = (
    "# REQ-001 Webの画面の基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "メンバーwebの画面の基準を定める。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に利用者のIDを表示しない。\n"
    "\n"
    "## Verification\n"
    "\n"
    "Core実装後に確認する。現時点では未証明。\n"
)

# id: (操作, 引数列の残り, 結果のファイル, 説明)
CASES = {
    "MULTI-031-01": ("check", ["check", "--workspace", "platform", "--full", "--base", "HEAD", "--format", "json"],
                     "expected/check.json",
                     "メンバーの中の`check --workspace platform --full`がルートを作業ワークスペースにし、ルートの文書だけを完全検査する"),
    "MULTI-031-02": ("context", ["context", "--workspace", "platform", "REQ-001", "--purpose", "interpret", "--format", "json"],
                     "expected/context.json",
                     "メンバーの中の`context --workspace platform REQ-001`が非修飾の起点をルートのREQ-001に解決する"),
}


def reviewed_inputs(identifier):
    """`repo/`の全入力。2件は同じ入力を共有する。"""
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
        ROOT_REQ_PATH: (front("REQ-001", ROOT_TITLE, "approved") + "\n" + ROOT_BODY).encode(),
        WEB_REQ_PATH: (front("REQ-001", WEB_TITLE, "approved") + "\n" + WEB_BODY).encode(),
        WEB_TECH_PATH: tech("TECH-010", "Webの無関係な方針", "approved", "ほかの文書と関係を持たない。"),
        API_TECH_PATH: tech("TECH-020", "APIの無関係な方針", "approved", "ほかの文書と関係を持たない。"),
    }


def reviewed_manifest(identifier):
    _, argv, result_file, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": CWD, "argv": list(argv), "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json", "resultFile": result_file, "reportFileCount": 0},
    }


def reviewed_check_result():
    """`platform`の1文書（`REQ-001`）と規範文2件。メンバーの文書は数えない。"""
    return {"schemaVersion": "1.0", "operation": "check", "workspace": {"id": "platform", "path": "."},
            "durationMs": 0, "scope": "full", "status": "passed",
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": 1, "checkedStatementCount": 2, "diagnostics": []}


STATEMENTS = [
    {"id": "platform::REQ-001:AC-01", "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
     "modality": "MUST", "reason": None, "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}, "extensions": []},
    {"id": "platform::REQ-001:AC-02", "actor": "TargetSystem", "activation": {"kind": "WHEN", "text": "保存した場合"},
     "modality": "SHOULD", "reason": "確認のため", "operation": {"kind": "THEN", "text": "結果を返す"}, "extensions": []},
]
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}


def reviewed_context_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "interpret",
        "workspace": {"id": "platform", "path": "."},
        "roots": ["platform::REQ-001"],
        "contextDigest": context_digest,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": True, "documentCount": 1, "unresolvedStrongRelations": 0,
                       "workspaces": [{"id": "platform", "path": "."}], "crossWorkspaceEdges": []},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [
            {"id": "platform::REQ-001", "workspaceId": "platform", "kind": "requirement", "status": "approved",
             "role": "root", "path": ROOT_REQ_PATH, "projection": "full", "reachedBy": ["root"],
             "statementRefs": ["platform::REQ-001:AC-01", "platform::REQ-001:AC-02"],
             "frontmatter": {"id": "platform::REQ-001", "title": ROOT_TITLE, "status": "approved"},
             "bodyText": ROOT_BODY, "untrustedText": True},
        ],
        # 目的`interpret`は対象規範文を持たない（関係・トレースモデル §6.4）ので、制約台帳とカバレッジは空である。
        "constraintLedger": {"statements": []},
        "coverage": {"must": dict(EMPTY_BUCKET), "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_digest_input():
    """`context --workspace platform REQ-001 --purpose interpret`のレビュー済みのハッシュ値の材料（参照計算A）。
    到達ワークスペースは`platform`だけで、`web`と`api`の設定と本文は材料へ入らない（ハッシュ値の正規化仕様 §3）。"""
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "interpret", "requestWorkspaceId": "platform", "roots": ["platform::REQ-001"],
        "workspaces": [{"id": "platform", "path": "."}],
        "documents": [{
            "id": "platform::REQ-001", "workspaceId": "platform", "kind": "requirement", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": "platform::REQ-001", "title": ROOT_TITLE, "status": "approved",
                            "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [], "tests": [],
                            "verify": None, "changes": []},
            "bodyText": ROOT_BODY,
            "statements": [dict(statement) for statement in STATEMENTS],
            "strongRelations": [],
        }],
        "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": "platform", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
                     "context": {"maxDocuments": 20, "maxBytes": 131072}, "verifyTimeouts": [], "commands": []},
    }


def references(repository):
    """同じハッシュ値の材料を、独立に書いた2系統で計算し、バイト列の一致を要求する。"""
    literal = digest_reference.canonical_bytes(reviewed_digest_input())
    derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, "platform::REQ-001", "interpret"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    if digest_reference.digest(literal) != multi_crosscheck.digest(derived):
        raise ValueError("参照計算AとBのハッシュ値が一致しません")
    return literal


def reference_context(repository, cwd, option, argument):
    """参照計算: 入力の木構造から、起点ワークスペース、起点、コンテキストの文書を導く（複合ワークスペース仕様 §3・§4、`context` §2）。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    request = select_workspace(workspaces, cwd, option)
    # 非修飾の起点は、`--workspace`（なければ最寄りの設定）の起点ワークスペースで解決する。
    root = argument if "::" in argument else f"{request}::{argument}"
    selected, _ = multi_crosscheck.closure(documents, root)
    entries = []
    for identifier in selected:
        document = documents[identifier]
        entries.append({
            "id": identifier, "workspaceId": document["workspaceId"], "path": document_path(document),
            "title": document["frontmatter"]["title"], "status": document["frontmatter"]["status"],
            "bodyText": document["body"],
            "statementRefs": [f"{document['workspaceId']}::{statement['id']}" for statement in read_statements(document["body"])],
        })
    return {"workspace": {"id": request, "path": workspaces[request]["path"]}, "roots": [root], "documents": entries,
            "workspaces": [{"id": request, "path": workspaces[request]["path"]}]}


def check_context_against_reference(result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    if result["workspace"] != reference["workspace"] or result["roots"] != reference["roots"]:
        raise ValueError("起点ワークスペースまたは`roots`が入力からの参照計算と異なります")
    if result["resolution"]["workspaces"] != reference["workspaces"] or result["resolution"]["documentCount"] != len(reference["documents"]):
        raise ValueError("到達ワークスペースまたは文書数が入力からの参照計算と異なります")
    actual = [{"id": item["id"], "workspaceId": item["workspaceId"], "path": item["path"],
               "title": item["frontmatter"]["title"], "status": item["status"], "bodyText": item["bodyText"],
               "statementRefs": item["statementRefs"]} for item in result["documents"]]
    if actual != reference["documents"]:
        raise ValueError("文書が入力からの参照計算と異なります")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく入力の木構造から確かめる。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    if sorted(documents) != ["api::TECH-020", "platform::REQ-001", "web::REQ-001", "web::TECH-010"]:
        raise ValueError("文書は、ルートのREQ-001、webのREQ-001とTECH-010、apiのTECH-020だけである必要があります")
    if any(document["frontmatter"]["status"] != "approved" for document in documents.values()):
        raise ValueError("すべての文書は状態`approved`である必要があります")
    if any(document["frontmatter"].get("relations") for document in documents.values()):
        raise ValueError("どの文書も関係を宣言してはいけません（閉包と逆参照が結果を変えます）")
    root, web = documents["platform::REQ-001"], documents["web::REQ-001"]
    if (root["frontmatter"]["title"] == web["frontmatter"]["title"] or root["body"] == web["body"]
            or len(read_statements(root["body"])) == len(read_statements(web["body"]))):
        raise ValueError("ルートとwebのREQ-001は、タイトル・本文・規範文の数が異なる必要があります")
    # `--workspace`がなければ最寄りの設定の`web`になり、`--workspace platform`が`platform`へ置き換える（複合ワークスペース仕様 §3の2・3・5）。
    if select_workspace(workspaces, CWD, None) != "web" or select_workspace(workspaces, CWD, "platform") != "platform":
        raise ValueError("実行ディレクトリの最寄りの設定は`web`で、`--workspace platform`が`platform`に置き換える必要があります")
    if git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("このfixtureは、変更集合を持ってはいけません")
    if CASES[identifier][0] == "check":
        reference = reference_check(repository, "full", "platform", CWD, "platform")
        if reference["inspected"] != ["platform::REQ-001"]:
            raise ValueError("完全検査の対象は`platform::REQ-001`だけである必要があります")
        # 陰性対照: 最寄りの設定のまま`web`を作業ワークスペースにすると、対象の文書数と規範文の数が変わる。
        fallback = reference_check(repository, "full", "web", CWD, None)
        if (fallback["documentCount"], fallback["statementCount"]) == (reference["documentCount"], reference["statementCount"]):
            raise ValueError("最寄りの設定の`web`を作業ワークスペースにした場合と、結果が区別できる必要があります")
    else:
        selected, _ = multi_crosscheck.closure(documents, "platform::REQ-001")
        if selected != ["platform::REQ-001"]:
            raise ValueError("閉包は`platform::REQ-001`だけである必要があります")


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
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        if CASES[identifier][0] == "check":
            (fixture / "expected/check.json").write_text(_dump(reviewed_check_result()))
        else:
            canonical = references(fixture / "repo")
            (fixture / "expected/context.canonical.json").write_bytes(canonical)
            (fixture / "expected/context.json").write_text(
                _dump(reviewed_context_result(digest_reference.digest(canonical))))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-option-") as temporary:
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
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        operation, _, result_file, _ = CASES[identifier]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / result_file).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            canonical = None
            if operation == "check":
                if (fixture / "expected/context.canonical.json").exists():
                    raise ValueError("`check`のfixtureは正規JSONを持ってはいけません")
                expected_result = reviewed_check_result()
            else:
                canonical = (fixture / "expected/context.canonical.json").read_bytes()
                if canonical.startswith(b"\xef\xbb\xbf") or canonical.endswith(b"\n"):
                    raise ValueError("正規JSONはBOMも末尾改行も持ってはいけません")
                expected_result = reviewed_context_result(digest_reference.digest(canonical))
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != expected_result:
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink() or path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = (
                            None if path.is_symlink() else path.read_bytes())
            if entries != {("repo", name): data for name, data in reviewed.items()}:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-option-") as temporary:
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
                    if operation == "check":
                        check_result_against_reference(result, reference_check(repository, "full", "platform", CWD, "platform"))
                    else:
                        if references(repository) != canonical:
                            raise ValueError("コミットした正規JSONが参照計算と異なります")
                        check_context_against_reference(result, reference_context(repository, CWD, "platform", "REQ-001"))
                    _, _, documents = multi_crosscheck.load_workspaces(repository)
                    for document in documents.values():
                        Draft202012Validator({"$ref": "#/$defs/" + {
                            "requirement": "reqFrontmatter", "technical": "techFrontmatter",
                            "decision": "adrFrontmatter", "task": "taskFrontmatter"}[document["kind"]],
                            "$defs": frontmatter["$defs"]}).validate(document["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
