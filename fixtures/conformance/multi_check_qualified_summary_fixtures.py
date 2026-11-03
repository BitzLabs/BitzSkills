"""複合ワークスペースの`check`の影響の候補と文書IDの重複の`summary`が作業ワークスペースの文書IDを修飾し、全体操作でも自ワークスペースを修飾した参照を照合することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C69・C80とADR-051の追加に対応する。`MULTI-047`は、複合ワークスペースの`CTX-STATE-001`などの`summary`が作業ワークスペースの文書IDと規範文IDも
修飾することを固定した。同じ考え方を、`check`の次の2つの診断へ広げる。文型（文言のひな形）は変えず、差し込む値の形だけが変わる。
- `SPEC-IMPACT-OUTDATED-001`（影響の候補）の`summary`に差し込む、依存元と変更された文書の文書ID
- `SPEC-ID-DUPLICATE-001`（文書IDの重複）の`summary`に差し込む文書ID

修正前のCoreは、複合ワークスペース内でも、この2つの`summary`に作業ワークスペースの文書IDを修飾せずに差し込んだ（全体操作と単独の操作の両方）。
さらに、`check --all-workspaces`のメンバーの影響の候補は、自ワークスペースを自身のIDで修飾した参照（`web`の文書の`refines: [web::REQ-001:AC-01]`）を、
変更された文書へ照合せず、その依存元を見落とした（C80。単独の操作は照合していた）。

| fixture | 操作と実行ディレクトリ | 入力 | 期待 |
|---|---|---|---|
| `MULTI-056-01` | `check --all-workspaces --base HEAD`、`.` | `web`の`REQ-001`（状態`draft`）を作業ツリーで変更する。`web`の`TECH-010`は`refines: [web::REQ-001:AC-01]`（自ワークスペースを修飾した参照）、`TECH-011`は`refines: [REQ-001:AC-01]`（非修飾）。`platform`も同じローカルIDの`REQ-001`を持つ | `web`の`diagnostics`に`SPEC-IMPACT-OUTDATED-001`の2件。どちらも`web::`で修飾する。全体と`web`は`passed_with_warnings`／0 |
| `MULTI-056-02` | `check --all-workspaces --base HEAD`、`.` | `MULTI-056-01`から`TECH-011`を除く（依存元は自ワークスペースを修飾した参照の`TECH-010`だけ） | `web`の`diagnostics`に`TECH-010`の1件。修正前のCoreは照合せず、診断なしで`passed`（C80の単独の再現） |
| `MULTI-056-03` | `check --workspace web --full --base HEAD`、`.` | `MULTI-056-01`と同じ入力 | `MULTI-056-01`と同じ2件。単独の操作の結果の形（`workspace`、`scope: full`）。修正前のCoreは件数と対象は同じで、`summary`が非修飾 |
| `MULTI-056-04` | `check --all-workspaces --base HEAD`、`.` | `web`の`REQ-003-a.md`と`REQ-003-b.md`が同じ文書ID`REQ-003`を定義する。`platform`も別の`REQ-003`を持つ（コミット済み） | `web`の`diagnostics`に`SPEC-ID-DUPLICATE-001`の1件で、`web::REQ-003`。`web`は`failed`、全体は`failed`／1 |
| `MULTI-056-05` | `check --workspace web --full --base HEAD`、`.` | `MULTI-056-04`と同じ入力 | `MULTI-056-04`と同じ1件。単独の操作の結果の形。`failed`／1 |

単一ワークスペースの対照は、既存の`SINGLE-033`（影響の候補の`summary`が`TECH-002が強く依存するTECH-001が…`）と`SINGLE-015`（`文書ID TECH-001が重複しています`）が、
修飾しない形のまま固定している。この群はそれを変えない。

基本のリポジトリは、ルート`platform`（`.`）とメンバー`web`（`apps/web`）で、すべてコミットし、`--format json`で起動する。
文書は`REQ`と`TECH`だけで、`TECH`は規範文を持たない（規範文の数を単純にする）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §4: 複合ワークスペース内で実行したCore操作は、文書IDと規範文IDを複合ワークスペースの正規形式（修飾ID）で返す。
  同じワークスペースを自身のIDで修飾した参照（`web`の文書の`web::REQ-001`）は、非修飾形式と同じ文書または規範文を指す。
- `check` §8: 出発点の変更されたREQまたはTECHへ、強く依存する状態`approved`の文書を`SPEC-IMPACT-OUTDATED-001`（`warning`）として示す。`check` §3: `--all-workspaces`は
  カタログ内のすべての仕様文書を完全検査する。`check` §6: 影響の候補は作業ワークスペースの文書だけに行う（単独の操作）。
- 診断レジストリ: `SPEC-IMPACT-OUTDATED-001`は`warning`／`passed_with_warnings`、`SPEC-ID-DUPLICATE-001`は`error`／`failed`で継続単位は`skip-document`。
- `summary`のIDの形は規範文で1つに決まらない。ADR-062により、これは管理者が承認した値である。ユーザーの決定（2026-10-26。`MULTI-047`）の考え方と、確認事項C69の決定で、
  作業ワークスペースのIDも`<ワークスペース>::`で修飾する。
- 結果・診断・終了コード §2.1・§3・§7: `--all-workspaces`の結果は`multiWorkspace`と`workspaces`を持ち、ワークスペースはルートを先頭に、その後をIDの辞書順で並べる。
  診断は所有ワークスペースの`diagnostics`に置き、最上位は複製しない。診断の並びは発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順。
  `checkedDocumentCount`と`checkedStatementCount`は完全検査した文書数と規範文数。
- 文書IDが重複する2つのファイルは、どちらも`skip-document`にして完全検査の文書へ数えない（`SINGLE-015`と同じ。`文書IDの重複と循環のレビュー記録.md`）。

参照計算`reference_*`は、準備手順の後の入力の木構造とGitの変更集合から、診断、件数、状態を導く。さらに、修正前のCoreの結果（作業ワークスペースの文書IDを修飾しない、
全体操作では自ワークスペースを修飾した参照を照合しない）を導き、この入力が欠陥を検出できること（期待する結果と異なること）を要求する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, multi_crosscheck, multi_reference
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = [("web", "apps/web")]
ROOT_ID = "platform"
WORKSPACE_PATHS = {"platform": ".", "web": "apps/web"}
RESULT_ORDER = ("platform", "web")
STRONG = ("requires", "refines", "addresses", "supersedes")
KIND_DIRECTORY = {kind: directory for directory, kind in digest_crosscheck.KIND_BY_DIRECTORY.items()}
SEVERITY_ORDER = ("passed", "passed_with_warnings", "blocked", "failed", "error")
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1}
WEB_REQ_PATH = "apps/web/.spec/requirements/REQ-001.md"
STATEMENT_TEXT = "秘密情報を出力しない"
BASE_INTENT = "意図。"
CHANGED_INTENT = "変更した意図。"

# --- 承認済みの診断の文言（既存のfixtureが固定する文型。差し込む値だけが修飾される） -------------------------
#
# `SINGLE-033`: 「TECH-002が強く依存するTECH-001が変更されています。再確認してください」、`SINGLE-015`: 「文書ID TECH-001が重複しています」。


def impact_summary(source, changed):
    return f"{source}が強く依存する{changed}が変更されています。再確認してください"


def duplicate_summary(identifier):
    return f"文書ID {identifier}が重複しています"


# --- 入力の表（宣言どおりの表記で書く） -----------------------------------------------------------------
#
# corpus名 → [(ワークスペース, ファイル名, ローカルID, 種類, 状態, 関係（宣言した参照の表記）, 規範文のラベルまたは`None`)]。
# `changes`のcorpusは、作業ツリーで内容を変える文書（ワークスペース、ファイル名）。
CORPORA = {
    # `web`の`REQ-001`（`draft`）を変更する。`TECH-010`は自ワークスペースを修飾した参照、`TECH-011`は非修飾の参照。`platform`も同じローカルID`REQ-001`を持つ。
    "impact": dict(
        documents=[
            ("platform", "REQ-001.md", "REQ-001", "requirement", "approved", {}, "AC-01"),
            ("web", "REQ-001.md", "REQ-001", "requirement", "draft", {}, "AC-01"),
            ("web", "TECH-010.md", "TECH-010", "technical", "approved", {"refines": ["web::REQ-001:AC-01"]}, None),
            ("web", "TECH-011.md", "TECH-011", "technical", "approved", {"refines": ["REQ-001:AC-01"]}, None),
        ],
        changed=[("web", "REQ-001.md")]),
    # `impact`から`TECH-011`を除く。依存元は、自ワークスペースを修飾した参照の`TECH-010`だけ。
    "impact-self": dict(
        documents=[
            ("platform", "REQ-001.md", "REQ-001", "requirement", "approved", {}, "AC-01"),
            ("web", "REQ-001.md", "REQ-001", "requirement", "draft", {}, "AC-01"),
            ("web", "TECH-010.md", "TECH-010", "technical", "approved", {"refines": ["web::REQ-001:AC-01"]}, None),
        ],
        changed=[("web", "REQ-001.md")]),
    # `web`の`REQ-003-a.md`と`REQ-003-b.md`が同じ文書ID`REQ-003`を定義する。規範文IDを重ねないよう、ラベルは`AC-01`と`AC-02`にする。
    # `platform`は別の`REQ-003`を持つ。
    "duplicate": dict(
        documents=[
            ("platform", "REQ-003.md", "REQ-003", "requirement", "approved", {}, "AC-01"),
            ("web", "REQ-003-a.md", "REQ-003", "requirement", "approved", {}, "AC-01"),
            ("web", "REQ-003-b.md", "REQ-003", "requirement", "approved", {}, "AC-02"),
        ],
        changed=[]),
}

# id: dict(corpus, op, argv, defect, description)。`op`: `all`（`--all-workspaces`）、`single`（`--workspace web --full`）。
CASES = {
    "MULTI-056-01": dict(corpus="impact", op="all",
                         description="全体のcheckの影響の候補のsummaryは作業ワークスペースの文書IDを修飾し、自ワークスペースを修飾した参照の依存元も警告する"),
    "MULTI-056-02": dict(corpus="impact-self", op="all",
                         description="全体のcheckは、自ワークスペースを修飾した参照だけの依存元も、変更された文書への影響の候補として警告する"),
    "MULTI-056-03": dict(corpus="impact", op="single",
                         description="単独のcheckの影響の候補のsummaryも、作業ワークスペースの文書IDを修飾する"),
    "MULTI-056-04": dict(corpus="duplicate", op="all",
                         description="全体のcheckの文書IDの重複のsummaryは、作業ワークスペースの文書IDを修飾する"),
    "MULTI-056-05": dict(corpus="duplicate", op="single",
                         description="単独のcheckの文書IDの重複のsummaryも、作業ワークスペースの文書IDを修飾する"),
}
ARGV = {"all": ["check", "--all-workspaces", "--base", "HEAD"], "single": ["check", "--workspace", "web", "--full", "--base", "HEAD"]}
RESULT_FILE = "expected/check.json"

# レビュー済みの期待する診断（リテラル）: 条件の名前→(ワークスペース, ファイル名, 関係, summary, 診断の種類)。
# 影響の候補: 発生元は依存元の文書、キーは`relations.<関係>`。文書IDの重複: 発生元はパスの辞書順で先頭のファイル、キーは`id`。


def _impact(path, relation, source, changed):
    return {"code": "SPEC-IMPACT-OUTDATED-001", "severity": "warning", "resultStatus": "passed_with_warnings",
            "summary": impact_summary(source, changed),
            "source": {"kind": "file", "workspaceId": "web", "path": f".spec/technical/{path}", "key": f"relations.{relation}"}}


def _duplicate(path, identifier):
    return {"code": "SPEC-ID-DUPLICATE-001", "severity": "error", "resultStatus": "failed", "summary": duplicate_summary(identifier),
            "source": {"kind": "file", "workspaceId": "web", "path": f".spec/requirements/{path}", "key": "id"}}


IMPACT_010 = _impact("TECH-010.md", "refines", "web::TECH-010", "web::REQ-001")
IMPACT_011 = _impact("TECH-011.md", "refines", "web::TECH-011", "web::REQ-001")
DUPLICATE = _duplicate("REQ-003-a.md", "web::REQ-003")

# corpus→ワークスペース→(診断, 完全検査した文書数, 規範文数)。重複した2つのファイルは完全検査の文書へ数えない。
EXPECTED = {
    "impact": {"platform": ([], 1, 1), "web": ([IMPACT_010, IMPACT_011], 3, 1)},
    "impact-self": {"platform": ([], 1, 1), "web": ([IMPACT_010], 2, 1)},
    "duplicate": {"platform": ([], 1, 1), "web": ([DUPLICATE], 0, 0)},
}
# corpus→リポジトリの`dirty`（作業ツリーが基準版と異なるか）。
DIRTY = {"impact": True, "impact-self": True, "duplicate": False}


# --- 入力 -------------------------------------------------------------------------------

def render(local, kind, status, relations, label, intent=BASE_INTENT):
    """文書のファイルの全文。TECHは規範文を持たない。"""
    title = f"{local}の文書"
    head = f"---\nid: {local}\ntitle: {title}\nstatus: {status}\n"
    if relations:
        head += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations.items())
    head += "---\n\n"
    body = f"# {local} {title}\n\n"
    if kind == "requirement":
        body += (f"## Intent\n\n{intent}\n\n## Acceptance Criteria\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {STATEMENT_TEXT}。\n\n"
                 "## Verification\n\nテスト対応は宣言しない。\n")
    else:
        body += "## Context\n\n実装方針を定める。\n"
    return head + body


def document_path(workspace, name, kind):
    base = "" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace] + "/"
    return f"{base}.spec/{KIND_DIRECTORY[kind]}/{name}"


def reviewed_inputs(identifier):
    """`repo/`と`changes/`の全入力（パス→バイト列）。"""
    corpus = CORPORA[CASES[identifier]["corpus"]]
    files = {".spec/bitz.yaml": multi_reference.root_config(MEMBERS).encode(),
             "apps/web/.spec/bitz.yaml": multi_reference.plain_config("web").encode()}
    changes = {}
    for workspace, name, local, kind, status, relations, label in corpus["documents"]:
        files[document_path(workspace, name, kind)] = render(local, kind, status, relations, label).encode()
        if (workspace, name) in corpus["changed"]:
            changes[name] = render(local, kind, status, relations, label, intent=CHANGED_INTENT).encode()
    return {"files": files, "changes": changes}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    corpus = CORPORA[case["corpus"]]
    operations = [{"op": "update", "path": document_path(workspace, name, "requirement"), "source": f"changes/{name}"}
                  for workspace, name in corpus["changed"]]
    status = reviewed_result(identifier)["status"]
    return {
        "fixtureId": identifier, "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*ARGV[case["op"]], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json", "resultFile": RESULT_FILE, "reportFileCount": 0},
    }


# --- 期待結果 ---------------------------------------------------------------------------------

def worst(statuses):
    return max(statuses, key=SEVERITY_ORDER.index, default="passed")


def build_result(op, corpus, per_workspace):
    """`per_workspace`: ワークスペース→(診断, 文書数, 規範文数)。結果・診断・終了コード §2.1・§9の形に並べる。"""
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": DIRTY[corpus]}
    entries = {workspace: dict(id=workspace, path=WORKSPACE_PATHS[workspace],
                               status=worst(item["resultStatus"] for item in diagnostics),
                               checkedDocumentCount=documents, checkedStatementCount=statements, durationMs=0, diagnostics=diagnostics)
               for workspace, (diagnostics, documents, statements) in per_workspace.items()}
    if op == "all":
        ordered = [entries[workspace] for workspace in RESULT_ORDER]
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": worst(entry["status"] for entry in ordered),
                "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": ordered, "revision": revision, "durationMs": 0, "diagnostics": []}
    web = entries["web"]
    return {"schemaVersion": "1.0", "operation": "check", "workspace": {"id": "web", "path": "apps/web"}, "scope": "full", "status": web["status"],
            "revision": revision, "checkedDocumentCount": web["checkedDocumentCount"], "checkedStatementCount": web["checkedStatementCount"],
            "durationMs": 0, "diagnostics": web["diagnostics"]}


def reviewed_result(identifier):
    case = CASES[identifier]
    return build_result(case["op"], case["corpus"], EXPECTED[case["corpus"]])


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def load_tree(repository):
    """カタログの各ワークスペースの文書を、同じ文書IDの重複も保ったまま、ワークスペースID・パスの順に返す。"""
    root_id, members = multi_crosscheck.catalog(repository)
    documents = []
    for workspace, path in [(root_id, ".")] + members:
        root = repository if path == "." else repository / path
        for directory, kind in digest_crosscheck.KIND_BY_DIRECTORY.items():
            folder = root / ".spec" / directory
            for file in sorted(folder.glob("*.md")) if folder.is_dir() else []:
                frontmatter, raw = digest_crosscheck.split_document(file.read_text(encoding="utf-8"))
                documents.append({"workspaceId": workspace, "kind": kind, "frontmatter": frontmatter, "body": digest_crosscheck.normalize_body(raw),
                                  "path": file.relative_to(root).as_posix(), "repositoryPath": file.relative_to(repository).as_posix()})
    return root_id, dict(MEMBERS, **{root_id: "."}), documents


def changed_paths(repository):
    """基準版からインデックス、作業ツリー、未追跡までの変更集合（リポジトリのルート相対）。このcorpusは追跡済みのファイルの変更だけを扱う。"""
    output = git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode()
    paths = []
    for entry in [item for item in output.split("\0") if item]:
        if entry[:2] != " M":
            raise ValueError("この参照計算は、作業ツリーでの追跡済みのファイルの変更だけを扱います")
        paths.append(entry[3:])
    return sorted(paths)


def sort_key(item):
    """結果・診断・終了コード §7の並べ替えの鍵。この群の診断は`line`、`column`、`specRefs`を持たない`file`の発生元だけ。"""
    source = item["source"]
    if any(name in source for name in ("line", "column")) or "specRefs" in item or source["kind"] != "file":
        raise ValueError("この群の診断は`line`、`column`、`specRefs`を持たない`file`の発生元だけです")
    return (source["workspaceId"], source["path"], item["code"])


def reference_workspace(documents, workspace, changed, *, qualify=True, match_self_qualified=True, active=None):
    """参照計算: ワークスペースの診断と件数を導く。`qualify=False`と`match_self_qualified=False`は修正前のCoreの再現で、期待値の根拠にしない。

    重複した文書IDは、重複した全ファイルを`skip-document`にして完全検査へ数えず、パスの辞書順で先頭のファイルに1件を置く。
    影響の候補は、出発点（変更されたREQまたはTECH）へ強く依存する状態`approved`の文書ごとに、関係ごとに1件。参照は、自ワークスペースを修飾した形と非修飾の形を
    同じ文書として扱い、規範文の参照は所有する文書への参照として扱う。
    """
    own = sorted((item for item in documents if item["workspaceId"] == workspace), key=lambda item: item["path"])
    groups = {}
    for item in own:
        groups.setdefault(item["frontmatter"]["id"], []).append(item)
    duplicated = {identifier for identifier, group in groups.items() if len(group) > 1}
    counted = [item for item in own if item["frontmatter"]["id"] not in duplicated]

    def shown(local):
        return f"{workspace}::{local}" if qualify else local

    found = [{"code": "SPEC-ID-DUPLICATE-001", "severity": "error", "resultStatus": "failed", "summary": duplicate_summary(shown(identifier)),
              "source": {"kind": "file", "workspaceId": workspace, "path": groups[identifier][0]["path"], "key": "id"}}
             for identifier in sorted(duplicated)]
    changed_ids = {item["frontmatter"]["id"] for item in counted
                   if item["repositoryPath"] in changed and item["kind"] in ("requirement", "technical")}
    for item in counted:
        if item["frontmatter"]["status"] != "approved":
            continue
        for relation in STRONG:
            for reference in item["frontmatter"].get("relations", {}).get(relation, []):
                if "::" in reference and not match_self_qualified:
                    continue
                owner = multi_crosscheck.owner(multi_crosscheck.qualify(workspace, reference))
                target_workspace, _, local = owner.partition("::")
                if target_workspace == workspace and local in changed_ids:
                    found.append({"code": "SPEC-IMPACT-OUTDATED-001", "severity": "warning", "resultStatus": "passed_with_warnings",
                                  "summary": impact_summary(shown(item["frontmatter"]["id"]), shown(local)),
                                  "source": {"kind": "file", "workspaceId": workspace, "path": item["path"], "key": f"relations.{relation}"}})
    keys = [sort_key(entry) for entry in found]
    if len(set(keys)) != len(keys):
        raise ValueError("同じワークスペースの診断の並べ替えの鍵が重複しています（宣言の順に頼る入力は使いません）")
    statements = sum(len(digest_crosscheck.read_statements(item["body"])) for item in counted)
    return sorted(found, key=sort_key), len(counted), statements


def reference_result(identifier, repository, **defects):
    """入力の木構造とGitの変更集合から、操作の結果を導く（欠陥の再現は`defects`）。"""
    case = CASES[identifier]
    _, _, documents = load_tree(repository)
    changed = set(changed_paths(repository))
    workspaces = RESULT_ORDER if case["op"] == "all" else ("web",)
    per_workspace = {workspace: reference_workspace(documents, workspace, changed, **defects) for workspace in workspaces}
    if case["op"] == "single":
        # 単独の操作は作業ワークスペースだけを検査するので、他のワークスペースの結果は使わない。
        per_workspace = {"web": per_workspace["web"], "platform": ([], 0, 0)}
    return build_result(case["op"], case["corpus"], per_workspace)


def old_core_result(identifier, repository):
    """修正前のCoreの結果の再現（欠陥の再現。期待値の根拠にしない）。

    全体操作は、作業ワークスペースのIDを修飾せず、自ワークスペースを修飾した参照も照合しない。単独の操作は、修飾しないが、自ワークスペースを修飾した参照は照合する。
    """
    return reference_result(identifier, repository, qualify=False, match_self_qualified=CASES[identifier]["op"] == "single")


# --- 検査 -------------------------------------------------------------------------------------

def check_conditions(identifier, repository, manifest, result):
    """原因の構成と期待結果を、散文ではなく準備手順の後の入力と参照計算から確かめる。"""
    case = CASES[identifier]
    corpus = CORPORA[case["corpus"]]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリである必要があります")
    root_id, workspaces, documents = load_tree(repository)
    if root_id != ROOT_ID or workspaces != {"platform": ".", "web": "apps/web"}:
        raise ValueError("カタログがレビュー済みの入力と異なります")
    # 作業ツリーの変更は、レビュー済みの入力と一致する。変更前の内容は`HEAD`にある。
    changed = changed_paths(repository)
    expected_changed = sorted(document_path(workspace, name, "requirement") for workspace, name in corpus["changed"])
    if changed != expected_changed:
        raise ValueError("変更集合がレビュー済みの入力と異なります")
    for path in changed:
        if git(repository, "show", f"HEAD:{path}") == (repository / path).read_bytes():
            raise ValueError("変更した文書は基準版から変わっている必要があります")
    if (git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip() != b"") != DIRTY[case["corpus"]]:
        raise ValueError("`revision.dirty`の期待が作業ツリーと異なります")
    # 診断の原因は、影響の候補と文書IDの重複だけである。ワークスペースをまたぐ関係と、規範文のない`REQ`・規範文IDの重複を混ぜない。
    web_ids = [item["frontmatter"]["id"] for item in documents if item["workspaceId"] == "web"]
    platform_ids = {item["frontmatter"]["id"] for item in documents if item["workspaceId"] == "platform"}
    for item in documents:
        for values in item["frontmatter"].get("relations", {}).values():
            if any(multi_crosscheck.owner(multi_crosscheck.qualify(item["workspaceId"], value)).partition("::")[0] != item["workspaceId"] for value in values):
                raise ValueError("ワークスペースをまたぐ関係を宣言してはいけません")
        if item["kind"] == "technical" and digest_crosscheck.read_statements(item["body"]):
            raise ValueError("TECHは規範文を持ってはいけません")
    statement_ids = [f"{item['workspaceId']}::{statement['id']}" for item in documents for statement in digest_crosscheck.read_statements(item["body"])]
    if len(set(statement_ids)) != len(statement_ids):
        raise ValueError("規範文IDが重複しています（文書IDの重複と混ぜない）")
    # `platform`は、`web`と同じローカルIDの文書を持つ（作業ワークスペースのIDで修飾することが、診断の読み手に必要な入力）。
    if case["corpus"] in ("impact", "impact-self", "duplicate") and not platform_ids & set(web_ids):
        raise ValueError("`platform`は`web`と同じローカルIDの文書を持つ必要があります")
    by_id = {item["frontmatter"]["id"]: item for item in documents if item["workspaceId"] == "web"}
    if case["corpus"] in ("impact", "impact-self"):
        # 自ワークスペースを修飾した参照の依存元がある。`impact`は、非修飾の参照の依存元も持つ。
        if by_id["TECH-010"]["frontmatter"]["relations"]["refines"] != ["web::REQ-001:AC-01"]:
            raise ValueError("`TECH-010`は自ワークスペースを修飾した参照で`refines`する必要があります")
        if (case["corpus"] == "impact") != ("TECH-011" in by_id) or (
                "TECH-011" in by_id and by_id["TECH-011"]["frontmatter"]["relations"]["refines"] != ["REQ-001:AC-01"]):
            raise ValueError("`TECH-011`は`impact`だけが、非修飾の参照で`refines`する依存元として持ちます")
        if by_id["REQ-001"]["frontmatter"]["status"] != "draft" or any(
                item["frontmatter"]["status"] != "approved" for local, item in by_id.items() if local != "REQ-001"):
            raise ValueError("変更する`REQ-001`だけが状態`draft`である必要があります")
    else:
        # 重複する2つのファイルは、同じ文書IDで、異なる規範文IDと異なるファイル名を持つ。
        duplicates = [item for item in documents if item["workspaceId"] == "web"]
        if len(duplicates) != 2 or len({item["frontmatter"]["id"] for item in duplicates}) != 1 or len({item["path"] for item in duplicates}) != 2:
            raise ValueError("`web`は、同じ文書IDを持つ2つのファイルだけを持つ必要があります")
    reference = reference_result(identifier, repository)
    if result != reference:
        raise ValueError("結果が入力からの参照計算と異なります")
    wanted = {"passed_with_warnings": (0, 0), "failed": (1, 1)}
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (result["status"], EXIT_BY_STATUS[result["status"]]) or result["status"] not in wanted:
        raise ValueError("全体の状態または終了コードが診断からの参照計算と異なります")
    if case["op"] == "all":
        if result["diagnostics"] or [entry["id"] for entry in result["workspaces"]] != ["platform", "web"]:
            raise ValueError("最上位の診断は空で、ワークスペースの並びはルート先頭、ID辞書順である必要があります")
    # 欠陥を検出できる入力であること: 修正前のCoreの結果は、期待する結果と異なる。
    old = old_core_result(identifier, repository)
    if old == result:
        raise ValueError("修正前のCoreの結果が、期待する結果と異なる入力である必要があります")
    # `summary`だけが異なり、件数と対象が同じケース（単独の操作と、全体操作で`TECH-011`を含む入力）と、診断そのものが落ちるケースを区別する。
    old_diagnostics = old["workspaces"][-1]["diagnostics"] if case["op"] == "all" else old["diagnostics"]
    new_diagnostics = result["workspaces"][-1]["diagnostics"] if case["op"] == "all" else result["diagnostics"]
    if case["corpus"] == "impact-self" and case["op"] == "all":
        if old_diagnostics or not new_diagnostics:
            raise ValueError("`impact-self`の全体操作は、修正前のCoreが診断を返さない入力である必要があります")
    elif len(old_diagnostics) > len(new_diagnostics) or {item["summary"] for item in old_diagnostics} & {item["summary"] for item in new_diagnostics}:
        raise ValueError("修正前のCoreの`summary`は、すべて修飾していない文である必要があります")
    # 診断の文に作業ワークスペースの文書IDが、`web::`で修飾して現れる。
    for item in new_diagnostics:
        if "web::" not in item["summary"]:
            raise ValueError("診断の`summary`は作業ワークスペースの文書IDを修飾する必要があります")
    return documents


# --- 書き出しと監査 ---------------------------------------------------------------------------

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
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / RESULT_FILE).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-check-qualified-summary-") as temporary:
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
            result = json.loads((fixture / RESULT_FILE).read_text())
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
                        if path.is_symlink() or path.stat().st_mode & 0o111:
                            raise ValueError(f"{path.relative_to(fixture).as_posix()}はシンボリックリンクでも実行可能でもあってはいけません")
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = path.read_bytes()
            expected = {**{("repo", name): data for name, data in reviewed["files"].items()},
                        **{("changes", name): data for name, data in reviewed["changes"].items()}}
            if entries != expected:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {RESULT_FILE}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-check-qualified-summary-") as temporary:
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
                    documents = check_conditions(identifier, repository, manifest, result)
                    for document in documents:
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
