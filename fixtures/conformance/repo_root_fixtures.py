"""現在のディレクトリがワークスペースのルートの下位またはメンバーの中のときも、基準版との比較と全体事前検査の結果が変わらないことを固定する（Coreの公開操作は実行しない）。

`SINGLE-158`は、単一ワークスペース（ワークスペースのルートはリポジトリのルート）の下位のディレクトリ`docs`で、`check --full`を実行する。
基準版の`approved`のREQを2件置き、準備手順で1件の`title`を変え（状態は`approved`のまま）、もう1件を削除する。
`check`仕様 §5は、変更集合と基準版の仕様文書の一覧を現在のディレクトリによらずワークスペースのルートを基準に求め、ルートで実行した場合と同じ結果にすると定める。
`--full`でも基準版との比較（削除の検出、承認済み要求の保護）は働く（§3・§5。既存の`SINGLE-029`が`--full`で削除を固定する）。
よって、`title`を変えた`REQ-001`は承認済み要求の保護（`SPEC-SAFETY-APPROVED-001`、文書・フロントマター・状態仕様 §8）、
削除した`REQ-002`は管理済みの仕様文書の削除（`SPEC-STATE-TRANSITION-001`、同 §9）になり、ルートで実行した場合と同じ2件を返す。

`MULTI-030-01`は、複合ワークスペースのメンバー`web`の中（`apps/web`）で、同じ構成の`check --full`を実行する。
`--full`の完全検査の対象は作業ワークスペースのすべての仕様文書で、基準版との比較は作業ワークスペースの文書だけに行い（`check` §6）、診断は作業ワークスペースの名前`web`と、そのルートからの相対パスで返す。

`MULTI-030-02`は、メンバー`web`の中で`check --all-workspaces`を実行する。準備手順で、メンバーの外に未追跡の`tools/x/.spec/bitz.yaml`を置く。
全体操作の候補は現在のディレクトリによらずリポジトリ全体から列挙するので（複合ワークスペース仕様 §8）、
ルートで実行した場合と同じ`SPEC-MULTI-UNREGISTERED-001`（`blocked`）を返す。

期待値の根拠は規範文と、このモジュールの参照計算（`reference_check`）だけである。参照計算は、Gitを常にリポジトリのルートで呼び、
基準版（`HEAD`）の木構造と作業ツリーの木構造から、作業ワークスペース、診断、件数を導く。Coreの出力は期待値の根拠にしない。
参照計算は、実行するディレクトリを変えても結果が変わらないこと（ルートで実行した場合と同じ結果）を、監査が確かめるために現在のディレクトリを引数に取る。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .digest_crosscheck import KIND_BY_DIRECTORY, STRONG, normalize_body, read_statements, read_yaml, split_document
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .multi_check_fixtures import owning_workspace, select_workspace

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = [("web", "apps/web"), ("api", "services/api")]
SPEC_DOCUMENT = re.compile(r"^(?P<prefix>(?:.+/)?)\.spec/(?P<directory>[^/]+)/(?P<name>[^/]+)\.md$")

SINGLE_REQ_1 = ".spec/requirements/REQ-001.md"
SINGLE_REQ_2 = ".spec/requirements/REQ-002.md"
SINGLE_DOCS = "docs/README.md"
WEB_REQ_10 = "apps/web/.spec/requirements/REQ-010.md"
WEB_REQ_11 = "apps/web/.spec/requirements/REQ-011.md"
UNREGISTERED_PATH = "tools/x/.spec/bitz.yaml"
CHANGE_SOURCE = "changes/REQ-changed.md"
CONFIG_SOURCE = "changes/x-bitz.yaml"

# 引数なしの`check`が削除した仕様文書を`selection.targetDocumentCount`に数えるかは、規範文が定めない（実装の確認事項C28）。
# そのため、この群は引数なしの`check`を使わず、`selection`を持たない`--full`で実行する。

SAFETY_SUMMARY = "approved REQの意味変更時にstatusが戻されていません"
DELETED_SUMMARY = "管理済みSPECが削除されています"
UNREGISTERED_SUMMARY = "Gitが認識する設定fileがcatalogに登録されていません"

# id: (種類, corpus, 実行ディレクトリ, 引数列の残り, 状態, 終了コード, 説明)
CASES = {
    "SINGLE-158": ("single", "single", "docs", ["check", "--full"], "failed", 1,
                   "ワークスペースの下位のディレクトリでも、承認済み要求の保護と削除の検出をルートと同じ結果にする"),
    "MULTI-030-01": ("multi", "member", "apps/web", ["check", "--full"], "failed", 1,
                     "メンバーの中でも、承認済み要求の保護と削除の検出を作業ワークスペースの文書にルートと同じ結果で行う"),
    "MULTI-030-02": ("multi", "unregistered", "apps/web", ["check", "--all-workspaces"], "blocked", 2,
                     "メンバーの中でも、メンバーの外の未登録の設定を全体事前検査で検出する"),
}
WORKING = {"SINGLE-158": "root", "MULTI-030-01": "web", "MULTI-030-02": None}


def requirement(identifier, title, statement):
    """状態`approved`のREQ。H1は`title`と一致させる。"""
    return (
        f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n---\n"
        f"\n# {identifier} {title}\n"
        "\n## Intent\n\n基準版との比較を固定する。\n"
        f"\n## Acceptance Criteria\n\n- [{identifier}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {statement}\n"
        "\n## Verification\n\nCore実装後に確認する。現時点では未証明。\n"
    ).encode()


def reviewed_inputs(identifier):
    """`repo/`と`changes/`の全入力（キーは`repo/`または`changes/`を除いたパス）。"""
    kind, corpus = CASES[identifier][0], CASES[identifier][1]
    files, changes = {}, {}
    if kind == "single":
        files[".spec/bitz.yaml"] = CONFIGS["SINGLE-001"].encode()
        files[SINGLE_REQ_1] = requirement("REQ-001", "文書の検査", "秘密情報を出力しない。")
        files[SINGLE_REQ_2] = requirement("REQ-002", "設定の保護", "設定を書き換えない。")
        files[SINGLE_DOCS] = "# 文書\n\n仕様文書ではない、実行するディレクトリのための文書。\n".encode()
        changes[CHANGE_SOURCE.removeprefix("changes/")] = requirement("REQ-001", "変更後の文書検査", "秘密情報を出力しない。")
        return {"files": files, "changes": changes}
    files[multi_reference.ROOT_CONFIG_PATH] = multi_reference.root_config(MEMBERS).encode()
    files[multi_reference.WEB_CONFIG_PATH] = multi_reference.plain_config("web").encode()
    files[multi_reference.API_CONFIG_PATH] = multi_reference.plain_config("api").encode()
    files[WEB_REQ_10] = requirement("REQ-010", "認証の基準", "秘密情報を出力しない。")
    if corpus == "member":
        files[WEB_REQ_11] = requirement("REQ-011", "設定の保護", "設定を書き換えない。")
        changes[CHANGE_SOURCE.removeprefix("changes/")] = requirement("REQ-010", "変更後の認証基準", "秘密情報を出力しない。")
    else:
        changes[CONFIG_SOURCE.removeprefix("changes/")] = multi_reference.plain_config("x").encode()
    return {"files": files, "changes": changes}


def reviewed_manifest(identifier):
    kind, corpus, cwd, argv, status, exit_code, description = CASES[identifier]
    if corpus == "single":
        operations = [{"op": "update", "path": SINGLE_REQ_1, "source": CHANGE_SOURCE},
                      {"op": "delete", "path": SINGLE_REQ_2}]
    elif corpus == "member":
        operations = [{"op": "update", "path": WEB_REQ_10, "source": CHANGE_SOURCE},
                      {"op": "delete", "path": WEB_REQ_11}]
    else:
        operations = [{"op": "create", "path": UNREGISTERED_PATH, "source": CONFIG_SOURCE}]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": cwd, "argv": [*argv, "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def safety(workspace_id, path):
    return {"code": "SPEC-SAFETY-APPROVED-001", "severity": "error", "resultStatus": "failed",
            "summary": SAFETY_SUMMARY,
            "source": {"kind": "file", "workspaceId": workspace_id, "path": path, "key": "title"}}


def deleted(workspace_id, path):
    return {"code": "SPEC-STATE-TRANSITION-001", "severity": "error", "resultStatus": "failed",
            "summary": DELETED_SUMMARY,
            "source": {"kind": "file", "workspaceId": workspace_id, "path": path}}


def reviewed_result(identifier):
    """リテラルで書いたレビュー済みの期待値。"""
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": True}
    if identifier == "MULTI-030-02":
        # 未登録の設定は、どのワークスペースにも属さない。事前検査が非成功なので、メンバーの処理を始めず空配列を返す。
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "blocked",
                "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": [], "revision": revision,
                "durationMs": 0,
                "diagnostics": [{"code": "SPEC-MULTI-UNREGISTERED-001", "severity": "error", "resultStatus": "blocked",
                                 "summary": UNREGISTERED_SUMMARY,
                                 "source": {"kind": "file", "workspaceId": None, "path": UNREGISTERED_PATH}}]}
    workspace = {"id": "root", "path": "."} if identifier == "SINGLE-158" else {"id": "web", "path": "apps/web"}
    # `--full`は現在版の作業ワークスペースのすべての仕様文書を完全検査する。現在版に残るのは変更したREQの1件で、規範文は1件。削除したREQは数えない。
    return {"schemaVersion": "1.0", "operation": "check", "status": "failed", "scope": "full",
            "workspace": workspace, "revision": revision,
            "checkedDocumentCount": 1, "checkedStatementCount": 1,
            "durationMs": 0,
            "diagnostics": [safety(workspace["id"], ".spec/requirements/" + ("REQ-001.md" if identifier == "SINGLE-158" else "REQ-010.md")),
                            deleted(workspace["id"], ".spec/requirements/" + ("REQ-002.md" if identifier == "SINGLE-158" else "REQ-011.md"))]}


# --- 参照計算 --------------------------------------------------------------------------------


def workspaces_of(repository, kind):
    if kind == "single":
        return {"root": {"path": "."}}
    root_id, members = multi_crosscheck.catalog(repository)
    return {root_id: {"path": "."}, **{workspace_id: {"path": path} for workspace_id, path in members}}


def changed_paths(repository):
    """基準版からインデックス、作業ツリー、未追跡までの変更集合。リポジトリのルートで求める。このcorpusは変更と削除だけを扱う。"""
    output = git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode()
    paths = []
    for entry in [item for item in output.split("\0") if item]:
        if entry[:2] not in {" M", "M ", " D", "D "}:
            raise ValueError("この参照計算は、追跡済みのファイルの変更と削除だけを扱います")
        paths.append(entry[3:])
    return sorted(paths)


def documents_of(listing, read, workspace_path):
    """`listing`のパスのうち、作業ワークスペースの仕様文書を、フロントマターのIDで引ける索引として読む。"""
    prefix = "" if workspace_path == "." else workspace_path + "/"
    found = {}
    for path in listing:
        match = SPEC_DOCUMENT.match(path)
        if not match or match["prefix"] != prefix or match["directory"] not in KIND_BY_DIRECTORY:
            continue
        frontmatter, raw = split_document(read(path).decode())
        body = normalize_body(raw)
        if frontmatter["id"] in found:
            raise ValueError("IDが重複しています")
        found[frontmatter["id"]] = {
            "path": path[len(prefix):], "kind": KIND_BY_DIRECTORY[match["directory"]],
            "title": frontmatter["title"], "status": frontmatter["status"],
            "statements": read_statements(body),
            "strong": {key: frontmatter.get("relations", {}).get(key, []) for key in STRONG},
            "relations": frontmatter.get("relations", {}),
        }
    return found


def base_listing(repository):
    """基準版の全パス。`--full-tree`で、現在のディレクトリによらずリポジトリのルートを基準にする。"""
    return git(repository, "ls-tree", "-r", "--name-only", "-z", "--full-tree", "HEAD").decode().split("\0")[:-1]


def current_listing(repository):
    return sorted(path.relative_to(repository).as_posix() for path in repository.rglob("*")
                  if path.is_file() and ".git" not in path.relative_to(repository).parts)


def comparison_diagnostics(workspace_id, base, current):
    """基準版と現在版を文書IDで対応付け、削除と承認済み要求の保護を求める（`check` §5、状態仕様 §8・§9）。"""
    diagnostics = []
    for identifier, before in base.items():
        if identifier not in current:
            diagnostics.append(deleted(workspace_id, before["path"]))
            continue
        after = current[identifier]
        if after["path"] != before["path"] or after["status"] != before["status"]:
            raise ValueError("この参照計算は、パスと状態の変更を扱いません")
        if before["kind"] != "requirement" or before["status"] != "approved":
            continue
        if before["statements"] != after["statements"] or before["strong"] != after["strong"]:
            raise ValueError("この参照計算は、規範文と強い関係の変更を扱いません")
        if before["title"] != after["title"]:
            diagnostics.append(safety(workspace_id, before["path"]))
    return sorted(diagnostics, key=lambda item: (item["source"]["workspaceId"], item["source"]["path"], item["code"]))


def unregistered_configs(listing, catalog_members):
    registered = {".spec/bitz.yaml", *(f"{path}/.spec/bitz.yaml" for _, path in catalog_members)}
    return sorted(path for path in listing
                  if (path == ".spec/bitz.yaml" or path.endswith("/.spec/bitz.yaml")) and path not in registered)


def reference_check(repository, kind, scope, cwd, option):
    """参照計算: 基準版と作業ツリーの木構造から、作業ワークスペース、診断、件数を導く。"""
    if scope == "all-workspaces":
        # 候補は、現在のディレクトリによらずリポジトリ全体から、Gitが認識するパス（追跡、ステージ済み、無視されない未追跡）で列挙する。
        recognized = git(repository, "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")[:-1]
        _, members = multi_crosscheck.catalog(repository)
        base_config = read_yaml(git(repository, "show", "HEAD:.spec/bitz.yaml").decode())
        base_members = [(entry["id"], entry["path"]) for entry in base_config["multiWorkspace"]["members"]]
        if unregistered_configs(base_listing(repository), base_members):
            raise ValueError("この参照計算は、基準版の未登録の設定を扱いません")
        return {"unregistered": unregistered_configs(sorted(set(recognized)), members)}
    workspaces = workspaces_of(repository, kind)
    working = select_workspace(workspaces, cwd, option)
    base = documents_of(base_listing(repository), lambda path: git(repository, "show", "HEAD:" + path), workspaces[working]["path"])
    current = documents_of(current_listing(repository), lambda path: (repository / path).read_bytes(), workspaces[working]["path"])
    if any(document["relations"] for document in current.values()):
        raise ValueError("この参照計算は、関係を持つ文書（閉包と逆参照）を扱いません")
    # `--full`は、作業ワークスペースの現在版のすべての仕様文書を完全検査する。削除した文書は現在版にないので数えない。
    return {
        "workspace": {"id": working, "path": workspaces[working]["path"]},
        "documentCount": len(current),
        "statementCount": sum(len(document["statements"]) for document in current.values()),
        "diagnostics": comparison_diagnostics(working, base, current),
    }


def check_result_against_reference(result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    if "unregistered" in reference:
        if [item["source"]["path"] for item in result["diagnostics"]] != reference["unregistered"]:
            raise ValueError("未登録の設定が入力からの参照計算と異なります")
        if (result["status"] == "blocked") != bool(reference["unregistered"]) or result["workspaces"]:
            raise ValueError("状態またはメンバーの結果が全体事前検査と一致しません")
        if any(item["source"]["workspaceId"] is not None for item in result["diagnostics"]):
            raise ValueError("未登録の設定は、所有ワークスペースを持ちません")
        return
    if result["workspace"] != reference["workspace"]:
        raise ValueError("`workspace`が入力からの参照計算と異なります")
    if result["scope"] != "full" or "selection" in result:
        raise ValueError("`--full`の結果は`scope: full`で、`selection`を持ちません")
    if (result["checkedDocumentCount"] != reference["documentCount"]
            or result["checkedStatementCount"] != reference["statementCount"]):
        raise ValueError("完全検査の件数が入力からの参照計算と異なります")
    if result["diagnostics"] != reference["diagnostics"]:
        raise ValueError("診断が入力からの参照計算と異なります")
    if (result["status"] == "passed") != (not reference["diagnostics"]):
        raise ValueError("状態が診断の有無と一致しません")


def reference_for(identifier, repository, cwd=None, option=None):
    kind, corpus, own_cwd, argv = CASES[identifier][:4]
    scope = "all-workspaces" if "--all-workspaces" in argv else "full"
    return reference_check(repository, kind, scope, own_cwd if cwd is None else cwd, option)


def check_invariance(identifier, repository):
    """実行するディレクトリを変えても、参照計算の結果は変わらない（ルートで実行した場合と同じ結果）。"""
    own = reference_for(identifier, repository)
    if identifier == "SINGLE-158":
        others = [reference_for(identifier, repository, cwd=cwd) for cwd in (".", "docs", ".spec/requirements")]
    elif identifier == "MULTI-030-01":
        others = [reference_for(identifier, repository, cwd=".", option="web"),
                  reference_for(identifier, repository, cwd="apps/web/.spec", option=None)]
    else:
        others = [reference_for(identifier, repository, cwd=cwd) for cwd in (".", "services/api", "tools/x")]
    if any(other != own for other in others):
        raise ValueError("実行するディレクトリによって参照計算の結果が変わります")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく入力の木構造とGitの状態から確かめる。"""
    kind, corpus, cwd = CASES[identifier][:3]
    workspaces = workspaces_of(repository, kind)
    head = base_listing(repository)
    # 実行するディレクトリは、基準版に実在し、ワークスペースのルートの下位（単一）またはメンバーのルート（複合）である。
    if not any(path.startswith(cwd + "/") for path in head):
        raise ValueError("実行するディレクトリが基準版に実在しません")
    working = WORKING[identifier]
    if corpus == "single":
        if cwd == "." or select_workspace(workspaces, cwd, None) != "root":
            raise ValueError("単一ワークスペースのケースは、ワークスペースの下位のディレクトリで実行する必要があります")
    elif select_workspace(workspaces, cwd, None) != "web" or workspaces["web"]["path"] != cwd:
        raise ValueError("複合ワークスペースのケースは、メンバー`web`のルートで実行する必要があります")
    if corpus in {"single", "member"}:
        # 基準版の`approved`のREQ 2件のうち、1件の`title`だけを変え（規範文と状態は同じ）、1件を削除する。
        # 修正前は、現在のディレクトリを基準にした一覧が空になり、この2件の診断が黙って省かれた。
        base = documents_of(head, lambda path: git(repository, "show", "HEAD:" + path), workspaces[working]["path"])
        current = documents_of(current_listing(repository), lambda path: (repository / path).read_bytes(),
                               workspaces[working]["path"])
        if sorted(base) != (["REQ-001", "REQ-002"] if corpus == "single" else ["REQ-010", "REQ-011"]):
            raise ValueError("基準版の仕様文書は、承認済みのREQ 2件だけである必要があります")
        if any(document["status"] != "approved" or document["kind"] != "requirement" for document in base.values()):
            raise ValueError("基準版の仕様文書は、すべて状態`approved`のREQである必要があります")
        changed, removed = sorted(base)
        if sorted(current) != [changed]:
            raise ValueError("現在版に残るREQは、変更した1件だけである必要があります")
        if (current[changed]["status"] != "approved" or current[changed]["title"] == base[changed]["title"]
                or current[changed]["statements"] != base[changed]["statements"]
                or current[changed]["strong"] != base[changed]["strong"]):
            raise ValueError("変更するREQは、状態`approved`のまま`title`だけを変える必要があります")
        if changed_paths(repository) != sorted(
                [base[changed]["path"], base[removed]["path"]] if corpus == "single" else
                [workspaces[working]["path"] + "/" + base[changed]["path"],
                 workspaces[working]["path"] + "/" + base[removed]["path"]]):
            raise ValueError("変更集合は、変更したREQと削除したREQの2件だけである必要があります")
        if git(repository, "diff", "--cached", "--name-only").strip():
            raise ValueError("変更はインデックスへ入れず、作業ツリーに置く必要があります")
        if any(document["relations"] for document in [*base.values(), *current.values()]):
            raise ValueError("このcorpusは、関係を宣言してはいけません")
        if corpus == "member":
            # 他のメンバーは変更を持たず、作業ワークスペースの変更だけが比較の対象になる。
            if any(owning_workspace(workspaces, path) != "web" for path in changed_paths(repository)):
                raise ValueError("変更は作業ワークスペースの文書だけである必要があります")
        return
    # 未登録の設定: メンバーの外の、未追跡で無視されない設定が1件だけある。
    status = git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode().split("\0")
    if [item for item in status if item] != ["?? " + UNREGISTERED_PATH]:
        raise ValueError("変更集合は、未追跡の設定1件だけである必要があります")
    _, members = multi_crosscheck.catalog(repository)
    if UNREGISTERED_PATH in {f"{path}/.spec/bitz.yaml" for _, path in members}:
        raise ValueError("未登録の設定がカタログへ入っています")
    if any(UNREGISTERED_PATH.startswith(path + "/") for _, path in members):
        raise ValueError("未登録の設定は、どのメンバーの外にも置く必要があります")
    if UNREGISTERED_PATH.startswith(cwd + "/") or UNREGISTERED_PATH in head:
        raise ValueError("未登録の設定は、実行するディレクトリの外で、基準版にない必要があります")
    if unregistered_configs(head, members):
        raise ValueError("基準版に未登録の設定があってはいけません")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def fixture_directory(root, identifier):
    return root / CASES[identifier][0] / identifier


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = fixture_directory(root, identifier)
        inputs = reviewed_inputs(identifier)
        for directory, files in (("repo", inputs["files"]), ("changes", inputs["changes"])):
            for name, content in files.items():
                path = fixture / directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-repo-root-") as temporary:
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
        fixture = fixture_directory(root, identifier)
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
            with tempfile.TemporaryDirectory(prefix="bitz-repo-root-") as temporary:
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
                    check_result_against_reference(result, reference_for(identifier, repository))
                    check_invariance(identifier, repository)
                    base_documents = [data for (directory, name), data in entries.items()
                                      if directory == "repo" and SPEC_DOCUMENT.match(name)]
                    for data in base_documents + [data for (directory, _), data in entries.items()
                                                  if directory == "changes" and data.startswith(b"---\nid: REQ")]:
                        Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": frontmatter["$defs"]}).validate(
                            split_document(data.decode())[0])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
