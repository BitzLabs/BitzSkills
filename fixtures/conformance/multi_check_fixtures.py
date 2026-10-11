"""複合ワークスペースの中で、引数なしの`check`、`--full`、`--workspace`が統合索引で作業ワークスペースを検査することを固定する（Coreの公開操作は実行しない）。

`MULTI-029-01`は、メンバー`web`の中（`apps/web`）で`check --full`を実行する。`web`の文書は`api::TECH-020`を`requires`し、
`platform::REQ-001:AC-01`を`refines`する。修飾した参照は統合索引で解決できるので、`SPEC-RELATION-MISSING-001`にしない。
結果の`workspace`は作業ワークスペースの`web`とそのパス`apps/web`である（複合ワークスペース仕様 §3・§4、`check` §9）。
`--full`は作業ワークスペースのすべての仕様文書を完全検査し（`check` §3）、他のメンバーについては、横断する強い関係の閉包で到達した文書だけを
完全検査する。無関係なメンバーの文書は完全検査しない（複合ワークスペース仕様 §7）。その文書は`SPEC-RELATION-MISSING-001`を起こす入力を持たせ、
返らないことで確かめる（陰性対照）。

`MULTI-029-02`は、同じ入力のリポジトリのルートで`check --workspace web --full`を実行する。ルートで`--workspace`を指定すると、
作業ワークスペースが`platform`ではなく`web`になる（複合ワークスペース仕様 §3の5.）。結果は`MULTI-029-01`と同じである。

`MULTI-029-03`は、`web`の文書を1件変更し、`apps/web`で引数なしの`check`を実行する（`scope: changed`）。変更した文書（`web::TECH-030`）は
`api::TECH-020`を`requires`する。`api`には、`web::TECH-030`を`refines`する文書（`TECH-040`。直接の逆参照）、`TECH-020`を`refines`する文書
（`TECH-060`。閉包で到達した文書の逆参照）、どれとも関係のない文書（`TECH-050`）を置く。4件はいずれも存在しない参照を1件持つ。
`web::TECH-030`の変更から、強い関係の閉包は`api::TECH-020`へ到達し、`api::TECH-040`は`web`の文書を1段で参照するので完全検査の対象になる。
`TECH-050`は無関係、`TECH-060`は閉包で到達した他のメンバーの文書の逆参照なので、対象にしない。診断は所有ワークスペースの`api`の名前で返す。

期待値の根拠は規範文と、このモジュールの参照計算（`reference_check`）だけである。参照計算は入力の木構造（`changed`ではGitの変更集合も）から、
作業ワークスペース、変更集合、強い関係の閉包、直接の逆参照、診断を導く。Coreの出力は期待値の根拠にしない。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, multi_crosscheck, multi_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
STRONG = ("requires", "refines", "addresses", "supersedes")
RELATIONS = (*STRONG, "related")
KIND_DIRECTORY = {kind: directory for directory, kind in digest_crosscheck.KIND_BY_DIRECTORY.items()}
MEMBERS = [("web", "apps/web"), ("api", "services/api")]

REQ_PATH = ".spec/requirements/REQ-001.md"
WEB_TECH_10 = "apps/web/.spec/technical/TECH-010.md"
WEB_TECH_11 = "apps/web/.spec/technical/TECH-011.md"
WEB_TECH_30 = "apps/web/.spec/technical/TECH-030.md"
API_TECH_20 = "services/api/.spec/technical/TECH-020.md"
API_TECH_40 = "services/api/.spec/technical/TECH-040.md"
API_TECH_50 = "services/api/.spec/technical/TECH-050.md"
API_TECH_60 = "services/api/.spec/technical/TECH-060.md"
# id: (種類, 実行ディレクトリ, 引数列の残り, 状態, 終了コード, 説明)
CASES = {
    "MULTI-029-01": ("full", "apps/web", ["check", "--full"], "passed", 0,
                     "メンバー内の`check --full`が修飾した参照を解決し、作業ワークスペースと閉包で到達した文書だけを完全検査する"),
    "MULTI-029-02": ("full", ".", ["check", "--workspace", "web", "--full"], "passed", 0,
                     "ルートの`check --workspace web --full`がメンバーを作業ワークスペースにして同じ結果を返す"),
    "MULTI-029-03": ("changed", "apps/web", ["check"], "failed", 1,
                     "メンバー内の引数なしの`check`が、他のメンバーの閉包と直接の逆参照を所有ワークスペースの名前で診断する"),
}
WORKING = {"MULTI-029-01": "web", "MULTI-029-02": "web", "MULTI-029-03": "web"}
OPTION = {"MULTI-029-01": None, "MULTI-029-02": "web", "MULTI-029-03": None}


def front(identifier, title, status, relations=None):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n"
    if relations:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations)
    return head + "---\n"


def tech(identifier, title, status, body, relations=None):
    return (front(identifier, title, status, relations)
            + f"\n# {identifier} {title}\n\n## Context\n\n{body}\n").encode()


REQ = (
    front("REQ-001", "認証の基準", "approved")
    + "\n# REQ-001 認証の基準\n"
    "\n## Intent\n\n複合ワークスペースの検査の基準を定める。\n"
    "\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "\n## Verification\n\nwebのtestで確認する。\n"
).encode()


def reviewed_inputs(identifier):
    """`repo/`と`changes/`の全入力。"""
    files = {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
    }
    changes = {}
    if CASES[identifier][0] == "full":
        files[REQ_PATH] = REQ
        files[WEB_TECH_10] = tech("TECH-010", "Web側の認証実装方針", "approved",
                                  "platformのMUSTをapiのsession処理に依存して実装する。",
                                  [("requires", ["api::TECH-020"]), ("refines", ["platform::REQ-001:AC-01"])])
        files[WEB_TECH_11] = tech("TECH-011", "閉包に含まれないWeb側の方針", "approved", "ほかの文書と関係を持たない。")
        files[API_TECH_20] = tech("TECH-020", "API側のsession方針", "approved", "ほかの文書を参照しない。")
        # 無関係なメンバーの文書。完全検査の対象に入れば`SPEC-RELATION-MISSING-001`が返る。
        files[API_TECH_50] = tech("TECH-050", "APIの無関係な方針", "approved", "webと関係を持たない。",
                                  [("requires", ["TECH-998"])])
    else:
        files[WEB_TECH_30] = tech("TECH-030", "Web側の変更する方針", "approved", "変更前の本文。",
                                  [("requires", ["api::TECH-020"])])
        files[API_TECH_20] = tech("TECH-020", "API側の閉包で到達する方針", "approved", "webから依存される。",
                                  [("requires", ["TECH-999"])])
        # `web::TECH-030`を直接参照する。状態`draft`は影響候補の対象（`approved`だけ）にならない。
        files[API_TECH_40] = tech("TECH-040", "APIの直接の逆参照の方針", "draft", "webの方針を具体化する。",
                                  [("refines", ["web::TECH-030"]), ("requires", ["TECH-997"])])
        files[API_TECH_50] = tech("TECH-050", "APIの無関係な方針", "approved", "webと関係を持たない。",
                                  [("requires", ["TECH-998"])])
        files[API_TECH_60] = tech("TECH-060", "APIの閉包の逆参照の方針", "approved", "閉包で到達した方針を具体化する。",
                                  [("refines", ["TECH-020"]), ("requires", ["TECH-996"])])
        changes["TECH-030.md"] = tech("TECH-030", "Web側の変更する方針", "approved", "変更後の本文。",
                                      [("requires", ["api::TECH-020"])])
    return {"files": files, "changes": changes}


def reviewed_manifest(identifier):
    kind, cwd, argv, status, exit_code, description = CASES[identifier]
    operations = []
    if kind == "changed":
        operations = [{"op": "update", "path": WEB_TECH_30, "source": "changes/TECH-030.md"}]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": cwd, "argv": [*argv, "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def missing(evidence, key, workspace_id, path):
    return {
        "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
        "summary": "strong relationの参照先が存在しません", "evidence": evidence,
        "source": {"kind": "file", "workspaceId": workspace_id, "path": path, "key": key},
    }


def reviewed_result(identifier):
    """リテラルで書いたレビュー済みの期待値。"""
    kind = CASES[identifier][0]
    common = {"schemaVersion": "1.0", "operation": "check", "workspace": {"id": "web", "path": "apps/web"},
              "durationMs": 0}
    if kind == "full":
        # `web::TECH-010`、`web::TECH-011`、閉包の`api::TECH-020`、閉包の`platform::REQ-001`。規範文は`REQ-001:AC-01`の1件。
        return {**common, "scope": "full", "status": "passed",
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
                "checkedDocumentCount": 4, "checkedStatementCount": 1, "diagnostics": []}
    return {**common, "scope": "changed", "status": "failed",
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
            "selection": {"changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0},
            "diagnostics": [
                missing("TECH-999", "relations.requires", "api", ".spec/technical/TECH-020.md"),
                missing("TECH-997", "relations.requires", "api", ".spec/technical/TECH-040.md"),
            ]}


# --- 参照計算 --------------------------------------------------------------------------------


def document_path(document):
    return f".spec/{KIND_DIRECTORY[document['kind']]}/{document['frontmatter']['id']}.md"


def statement_ids(document):
    return {item["id"] for item in digest_crosscheck.read_statements(document["body"])}


def declared_edges(documents, identifier, keys):
    """文書の宣言した関係を、宣言の順に(関係型, 宣言どおりの文字列, 修飾した参照先)として返す。"""
    document = documents[identifier]
    edges = []
    for key, values in document["frontmatter"].get("relations", {}).items():
        if key in keys:
            edges += [(key, text, multi_crosscheck.qualify(document["workspaceId"], text)) for text in values]
    return edges


def resolve(documents, target):
    """修飾した参照先が実在すれば、所有する文書の修飾IDを返す。規範文の参照は規範文の実在も確かめる。"""
    owner = multi_crosscheck.owner(target)
    if owner not in documents:
        return None
    local = target.partition("::")[2]
    if ":" in local and local not in statement_ids(documents[owner]):
        return None
    return owner


def strong_closure(documents, starts):
    """強い関係を前方へ推移的にたどる。起点を含み、ワークスペースをまたぐ。"""
    reached, frontier = set(starts), sorted(starts)
    while frontier:
        current = frontier.pop(0)
        for _, _, target in declared_edges(documents, current, STRONG):
            owner = resolve(documents, target)
            if owner is not None and owner not in reached:
                reached.add(owner)
                frontier.append(owner)
    return reached


def direct_reverse(documents, anchors, excluded):
    """`anchors`の文書またはその規範文を、5種のどれかの関係で1段で参照する、`excluded`の外の文書。"""
    found = set()
    for identifier in documents:
        if identifier in excluded:
            continue
        for _, _, target in declared_edges(documents, identifier, RELATIONS):
            if resolve(documents, target) in anchors:
                found.add(identifier)
    return found


def relation_diagnostics(documents, inspected):
    diagnostics = []
    for identifier in sorted(inspected, key=lambda name: (documents[name]["workspaceId"],
                                                          document_path(documents[name]))):
        document = documents[identifier]
        for key, text, target in declared_edges(documents, identifier, STRONG):
            if resolve(documents, target) is None:
                diagnostics.append(missing(text, f"relations.{key}", document["workspaceId"],
                                           document_path(document)))
    return diagnostics


def select_workspace(workspaces, cwd, option):
    """複合ワークスペース仕様 §3: `--workspace`を優先し、なければ最寄りの設定のワークスペースにする。"""
    if option is not None:
        if option not in workspaces:
            raise ValueError("`--workspace`のIDがカタログにありません")
        return option
    nearest, nearest_length = None, -1
    for workspace_id, entry in workspaces.items():
        path = entry["path"]
        inside = path == "." or cwd == path or cwd.startswith(path + "/")
        length = 0 if path == "." else len(path)
        if inside and length > nearest_length:
            nearest, nearest_length = workspace_id, length
    return nearest


def owning_workspace(workspaces, path):
    """リポジトリのルート相対のパスを所有するワークスペース。メンバーの配下はメンバーが所有し、それ以外はルートが所有する。"""
    best, best_length = None, -1
    for workspace_id, entry in workspaces.items():
        prefix = entry["path"]
        inside = prefix == "." or path == prefix or path.startswith(prefix + "/")
        length = 0 if prefix == "." else len(prefix)
        if inside and length > best_length:
            best, best_length = workspace_id, length
    return best


def changed_paths(repository):
    """基準版からインデックス、作業ツリー、未追跡までの変更集合。このcorpusは作業ツリーの変更だけを扱う。"""
    output = git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode()
    paths = []
    for entry in [item for item in output.split("\0") if item]:
        if entry[:2] not in {" M", "M ", "MM"}:
            raise ValueError("この参照計算は、追跡済みのファイルの変更だけを扱います")
        paths.append(entry[3:])
    return sorted(paths)


def reference_check(repository, kind, working_id, cwd, option):
    """参照計算: 入力の木構造（`changed`はGitの変更集合も）から、期待する結果の主要部分を導く。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    working = select_workspace(workspaces, cwd, option)
    if working != working_id:
        raise ValueError("作業ワークスペースが期待と異なります")
    own = {name for name, document in documents.items() if document["workspaceId"] == working}
    if kind == "full":
        starts, selection = own, None
    else:
        owned = [path for path in changed_paths(repository) if owning_workspace(workspaces, path) == working]
        prefix = "" if workspaces[working]["path"] == "." else workspaces[working]["path"] + "/"
        starts = set()
        for path in owned:
            relative = path[len(prefix):]
            matches = [name for name in own if document_path(documents[name]) == relative]
            if len(matches) != 1:
                raise ValueError("このcorpusは、仕様文書の変更だけを扱います")
            starts.add(matches[0])
        selection = {"changedPathCount": len(owned), "targetDocumentCount": len(starts),
                     "excludedCodeTestPathCount": 0}
    reached = strong_closure(documents, starts)
    # 直接の逆参照は、作業ワークスペースの文書（出発点と、閉包に入った作業ワークスペースの文書）を参照する他の文書に限る。
    # 閉包で到達した他のメンバーの文書の逆参照へは広げない。
    anchors = {name for name in reached if name in own}
    inspected = reached | direct_reverse(documents, anchors, reached)
    result = {
        "workspace": {"id": working, "path": workspaces[working]["path"]},
        "inspected": sorted(inspected),
        "documentCount": len(inspected),
        "statementCount": sum(len(statement_ids(documents[name])) for name in inspected),
        "diagnostics": relation_diagnostics(documents, inspected),
    }
    if selection is not None:
        result["selection"] = selection
    return result


def check_result_against_reference(result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    if result["workspace"] != reference["workspace"]:
        raise ValueError("`workspace`が入力からの参照計算と異なります")
    if result["diagnostics"] != reference["diagnostics"]:
        raise ValueError("診断が入力からの参照計算と異なります")
    if result["scope"] == "full":
        if (result["checkedDocumentCount"] != reference["documentCount"]
                or result["checkedStatementCount"] != reference["statementCount"]):
            raise ValueError("完全検査の件数が入力からの参照計算と異なります")
    elif result["selection"] != reference["selection"]:
        raise ValueError("`selection`が入力からの参照計算と異なります")
    if (result["status"] == "passed") != (not reference["diagnostics"]):
        raise ValueError("状態が診断の有無と一致しません")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく入力の木構造から確かめる。"""
    kind = CASES[identifier][0]
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    working = WORKING[identifier]
    own = {name for name, document in documents.items() if document["workspaceId"] == working}
    unresolved = {name: [(key, text) for key, text, target in declared_edges(documents, name, STRONG)
                         if resolve(documents, target) is None] for name in documents}
    broken = {name for name, items in unresolved.items() if items}
    if kind == "full":
        # 修飾した参照はすべて実在し、起点の`web`と閉包の文書は診断を持たない。
        # 誤りを持つ文書は、無関係な`api::TECH-050`の1件だけである（完全検査の対象に入れば診断が返る陰性対照）。
        if broken != {"api::TECH-050"}:
            raise ValueError("誤りを持つ文書は、無関係な`api::TECH-050`だけである必要があります")
        reference = reference_check(repository, "full", working, CASES[identifier][1], OPTION[identifier])
        if "api::TECH-050" in reference["inspected"]:
            raise ValueError("無関係な文書が完全検査の対象に入っています")
        if sorted(reference["inspected"]) != ["api::TECH-020", "platform::REQ-001", "web::TECH-010", "web::TECH-011"]:
            raise ValueError("完全検査の対象は、`web`の2文書と、閉包で到達した2文書である必要があります")
        # 閉包の外の`web::TECH-011`も、`--full`では作業ワークスペースの文書として数える。
        if "web::TECH-011" in strong_closure(documents, {"web::TECH-010"}):
            raise ValueError("`web::TECH-011`は閉包に含まれてはいけません")
        # 他のメンバーから作業ワークスペースの文書への参照はなく、直接の逆参照の解釈に依存しない。
        if direct_reverse(documents, own, own):
            raise ValueError("このcorpusは、他のメンバーの文書から`web`の文書への参照を持ってはいけません")
        if any(declared_edges(documents, "web::TECH-010", {"related"})):
            raise ValueError("`related`を宣言してはいけません")
        # 閉包の外の`web::TECH-011`は関係を持たず、`--full`が作業ワークスペースの全文書を数えることだけを固定する。
        if declared_edges(documents, "web::TECH-011", RELATIONS):
            raise ValueError("`web::TECH-011`は関係を宣言してはいけません")
        if any(document["frontmatter"]["status"] != "approved" for document in documents.values()):
            raise ValueError("`--full`のcorpusの文書は、すべて状態`approved`である必要があります")
        if git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip():
            raise ValueError("`--full`のfixtureは、変更集合を持ってはいけません")
        return
    # changed: 変更は`web::TECH-030`の1件だけで、基準版から内容が変わっている。
    if changed_paths(repository) != [WEB_TECH_30]:
        raise ValueError("変更集合は`web::TECH-030`の1件だけである必要があります")
    if git(repository, "show", f"HEAD:{WEB_TECH_30}") == (repository / WEB_TECH_30).read_bytes():
        raise ValueError("`web::TECH-030`は基準版から変わっている必要があります")
    if broken != {"api::TECH-020", "api::TECH-040", "api::TECH-050", "api::TECH-060"}:
        raise ValueError("誤りを持つ文書は、`api`の4文書だけである必要があります")
    if any(len(items) != 1 for name, items in unresolved.items() if items):
        raise ValueError("誤りは文書ごとに存在しない参照を1件だけにする必要があります")
    reference = reference_check(repository, "changed", working, CASES[identifier][1], OPTION[identifier])
    if sorted(reference["inspected"]) != ["api::TECH-020", "api::TECH-040", "web::TECH-030"]:
        raise ValueError("完全検査の対象は、変更した文書、閉包で到達した文書、直接の逆参照の3文書である必要があります")
    # 陰性対照の2文書は、実在する関係を持つが対象外である。
    closure = strong_closure(documents, {"web::TECH-030"})
    if closure != {"web::TECH-030", "api::TECH-020"}:
        raise ValueError("閉包は`web::TECH-030`と`api::TECH-020`だけである必要があります")
    if "api::TECH-060" in reference["inspected"] or "api::TECH-050" in reference["inspected"]:
        raise ValueError("閉包の逆参照と無関係な文書は、完全検査の対象に入ってはいけません")
    if "api::TECH-020" not in {resolve(documents, target)
                               for _, _, target in declared_edges(documents, "api::TECH-060", STRONG)}:
        raise ValueError("`api::TECH-060`は閉包で到達した`api::TECH-020`を参照する必要があります")
    if resolve(documents, "web::TECH-030") not in {resolve(documents, target)
                                                   for _, _, target in declared_edges(documents, "api::TECH-040", RELATIONS)}:
        raise ValueError("`api::TECH-040`は変更した`web::TECH-030`を参照する必要があります")
    # `web`には、変更した文書へ依存する文書がなく、影響候補は作業ワークスペースに生じない。
    # 他のメンバーの影響候補は、状態`draft`にして避ける（影響候補は状態`approved`の文書だけ。`check` §8）。
    if documents["api::TECH-040"]["frontmatter"]["status"] != "draft":
        raise ValueError("`api::TECH-040`は状態`draft`である必要があります")
    if direct_reverse(documents, {"web::TECH-030"}, {"web::TECH-030"}) != {"api::TECH-040"}:
        raise ValueError("`web::TECH-030`を参照する文書は`api::TECH-040`だけである必要があります")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        inputs = reviewed_inputs(identifier)
        for name, content in inputs["files"].items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for name, content in inputs["changes"].items():
            path = fixture / "changes" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-check-") as temporary:
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
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink() or path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = (
                            None if path.is_symlink() else path.read_bytes())
            expected = {**{("repo", name): data for name, data in reviewed["files"].items()},
                        **{("changes", name): data for name, data in reviewed["changes"].items()}}
            if entries != expected:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-check-") as temporary:
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
                    kind, cwd = CASES[identifier][0], CASES[identifier][1]
                    check_result_against_reference(
                        result, reference_check(repository, kind, WORKING[identifier], cwd, OPTION[identifier]))
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
            "status": "Passed" if not errors else "Failed", "errors": errors}
