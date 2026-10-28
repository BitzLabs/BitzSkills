"""複合ワークスペースの`context`と`verify`が、閉包に入った他のワークスペースの文書が宣言する辺の循環も報告することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C44とADR-051の追加に対応する。複合ワークスペースの`context`と`verify`は、循環の診断`CTX-CYCLE-001`を、作業ワークスペース（起点を所有するワークスペース）の
文書が宣言した辺に絞っていた。その結果、次の2つが起きていた。

- ワークスペースをまたぐ循環（`platform::REQ-030` -> `api::REQ-130` -> `platform::REQ-030`）では、作業ワークスペースの辺だけを報告し、他方の辺を落とした。
  `check <修飾ID>`は両側を返していた。
- 閉包に入った他のメンバーの中だけで閉じる循環（`platform::REQ-040` -> `api::REQ-140` <-> `api::REQ-141`）は、まったく報告しなかった。
  `context`と`verify`は成功し、`contextDigest`まで出していた。

この群は、報告の範囲を、`check`の完全検査と同じ「閉包に入ったどのワークスペースの文書が宣言する辺でも」に固定する。参照先の不在など循環以外の関係は、
これまでどおり他のワークスペースの文書では検査しない（対照）。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-050-01` | `context REQ-030 --purpose interpret`、`.` | `platform::REQ-030`と`api::REQ-130`が互いを`requires`する。`CTX-CYCLE-001`を宣言元ごとに2件（`api`、`platform`の順） |
| `MULTI-050-02` | `context REQ-040 --purpose interpret`、`.` | 他のメンバー`api`の中だけで閉じる循環（`REQ-140`と`REQ-141`）が閉包に入る。`CTX-CYCLE-001`が2件（`api`）、`contextDigest: null` |
| `MULTI-050-03` | `verify REQ-040`、`.` | 同じ入力。検証対象の`diagnostics`に`CTX-CYCLE-001`が2件 |
| `MULTI-050-04` | `context REQ-050 --purpose interpret --detail compact`、`.` | 対照: 他のメンバーの文書の参照切れ（存在しない`REQ-999`）は検査しないので成功する |
| `MULTI-050-05` | `context REQ-060 --purpose interpret`、`.` | 3つのワークスペースをまたぐ循環。`CTX-CYCLE-001`が3件（`api`、`platform`、`web`の順） |
| `MULTI-050-06` | `context REQ-001 --purpose interpret --detail compact`、`.` | 対照: 他のメンバーの循環が閉包の外にあれば報告しない |

基本のリポジトリは、ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）で、すべてコミットする。fixtureごとに必要な文書だけを置く。
`platform`だけがテスト対応のコマンドを持つ。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 関係・トレースモデル §6.3の最後の文: 複合ワークスペースの他のワークスペースの文書については、`requires`の型制約と、閉包の文書が宣言する強い関係の循環
  （ワークスペースをまたぐ循環を含む）を検査し、`check`の完全検査（`check` §6）と同じく、閉包に入ったどのワークスペースの文書が宣言する辺でも報告する。
  参照先の不在などそれ以外の関係は検査しない。
- 同 §6: 型、状態、循環、上限を満たさない場合は閉包の全体を非成功とする。§7: 循環を隠さない。§4: 禁止された循環に参加するエッジを宣言した文書ごとに診断する。
- 診断レジストリの`RELATION-CYCLE`（`CTX-CYCLE-001`）。結果・診断・終了コード §7: 診断はワークスペースID、`path`の辞書順に並べる。
- `context` §3: 強い関係の一部を解決できない（禁止された循環を含む）コンテキスト一式を成功にしない。`verify` §9: 検証対象ごとに目的`verify`のコンテキストを
  完全解決するので、`CTX-CYCLE-001`を検証対象の`diagnostics`へ返す。
- コンテキストのハッシュ値の正規化仕様 §3: 閉包の文書ごとの材料。`strongRelations`は参照先を解決できた強い関係だけを持ち、参照先を解決できない関係
  （`MULTI-050-04`の`api::REQ-150`の`REQ-999`）は含めない（宣言は`frontmatter.relations`に残る。ユーザーの決定2026-10-28）。ハッシュ値は、独立に書いた2系統の参照計算（このモジュールのリテラルA、入力の木構造から導出するB）の
  バイト列の一致を要求する。

参照計算は`multi_closure_alias_fixtures`の閉包・循環の参照計算を再利用し、報告の範囲だけをこの群で定める。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, multi_closure_alias_fixtures as alias, multi_crosscheck, multi_reference, multi_verify_fixtures as verify_fixtures
from .digest_crosscheck import KIND_BY_DIRECTORY, split_document
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
MEMBERS = [("web", "apps/web"), ("api", "services/api")]
REQUEST = "platform"
TEST_PATH = "tests/test_login.py"
TEST_BYTES = alias.TEST_BYTES
VERIFY_COMMANDS = 'verify:\n  commands:\n    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
REQ_DIR = ".spec/requirements"
REQ_TEXT = alias.REQ_TEXT

# id: {op, cwd, argv, corpus, root, outcome, description}。`root`は起点の正規ID（修飾ID）、`outcome`は期待する状態。
CASES = {
    "MULTI-050-01": dict(op="context", cwd=".", argv=["context", "REQ-030", "--purpose", "interpret"], corpus="cross", root="platform::REQ-030",
                         outcome="failed",
                         description="ワークスペースをまたぐ循環では、contextは両方のワークスペースの辺のCTX-CYCLE-001を報告する"),
    "MULTI-050-02": dict(op="context", cwd=".", argv=["context", "REQ-040", "--purpose", "interpret"], corpus="member-cycle", root="platform::REQ-040",
                         outcome="failed",
                         description="閉包に入った他のメンバーの中だけで閉じる循環を、contextはCTX-CYCLE-001で報告して失敗する"),
    "MULTI-050-03": dict(op="verify", cwd=".", argv=["verify", "REQ-040"], corpus="member-cycle", root="platform::REQ-040", outcome="failed",
                         description="閉包に入った他のメンバーの中だけで閉じる循環を、verifyは検証対象のdiagnosticsにCTX-CYCLE-001で報告する"),
    "MULTI-050-04": dict(op="context", cwd=".", argv=["context", "REQ-050", "--purpose", "interpret", "--detail", "compact"], corpus="member-missing",
                         root="platform::REQ-050", outcome="passed",
                         description="他のメンバーの文書の参照切れは検査しないので、contextは成功する"),
    "MULTI-050-05": dict(op="context", cwd=".", argv=["context", "REQ-060", "--purpose", "interpret"], corpus="three-way", root="platform::REQ-060",
                         outcome="failed",
                         description="3つのワークスペースをまたぐ循環では、contextは3つのワークスペースの辺のCTX-CYCLE-001を報告する"),
    "MULTI-050-06": dict(op="context", cwd=".", argv=["context", "REQ-001", "--purpose", "interpret", "--detail", "compact"], corpus="member-outside",
                         root="platform::REQ-001", outcome="passed",
                         description="他のメンバーの循環が閉包の外にあるとき、contextは報告せず成功する"),
}
RESULT_FILES = alias.RESULT_FILES

# --- 入力 -------------------------------------------------------------------------------

# corpus: 文書の表。キーは(ワークスペース, ローカルID)、値は(題名, `requires`の宣言)。`tests`はテスト対応を持つ文書。
DOCUMENTS = {
    "cross": {("platform", "REQ-030"): ("起点側の循環の一方", ["api::REQ-130"]),
              ("api", "REQ-130"): ("API側の循環の他方", ["platform::REQ-030"])},
    "member-cycle": {("platform", "REQ-040"): ("起点側の基準", ["api::REQ-140"]),
                     ("api", "REQ-140"): ("API側の循環の一方", ["REQ-141"]),
                     ("api", "REQ-141"): ("API側の循環の他方", ["REQ-140"])},
    "member-missing": {("platform", "REQ-050"): ("起点側の基準", ["api::REQ-150"]),
                       ("api", "REQ-150"): ("API側の参照切れを持つ基準", ["REQ-999"])},
    "three-way": {("platform", "REQ-060"): ("起点側の循環の一部", ["api::REQ-160"]),
                  ("api", "REQ-160"): ("API側の循環の一部", ["web::REQ-260"]),
                  ("web", "REQ-260"): ("Web側の循環の一部", ["platform::REQ-060"])},
    "member-outside": {("platform", "REQ-001"): ("起点側の基準", []),
                       ("api", "REQ-170"): ("閉包の外の循環の一方", ["REQ-171"]),
                       ("api", "REQ-171"): ("閉包の外の循環の他方", ["REQ-170"])},
}
TESTED = {"member-cycle": {("platform", "REQ-040")}}
WORKSPACE_ROOT = {"platform": "", "api": "services/api/", "web": "apps/web/"}


def corpus_files(corpus):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    files = {multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS) + VERIFY_COMMANDS,
             multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web"),
             multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api")}
    for (workspace, local), (title, requires) in DOCUMENTS[corpus].items():
        tests = (workspace, local) in TESTED.get(corpus, set())
        files[f"{WORKSPACE_ROOT[workspace]}{REQ_DIR}/{local}.md"] = alias.requirement(local, title, requires, tests=tests)[0]
    if TESTED.get(corpus):
        files[TEST_PATH] = TEST_BYTES.decode()
    return files


def reviewed_inputs(identifier):
    return {name: text.encode() for name, text in corpus_files(CASES[identifier]["corpus"]).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status, exit_code = {"failed": ("failed", 1), "passed": ("passed", 0)}[case["outcome"]]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- 診断（レビュー済みのリテラル） -----------------------------------------------------------------

# 閉包に入ったどのワークスペースの文書が宣言する辺でも報告する。循環に参加する辺を宣言した文書を、(ワークスペースID, path)の辞書順に並べる。
CYCLE_DECLARERS = {
    "cross": [("api", "REQ-130"), ("platform", "REQ-030")],
    "member-cycle": [("api", "REQ-140"), ("api", "REQ-141")],
    "three-way": [("api", "REQ-160"), ("platform", "REQ-060"), ("web", "REQ-260")],
}


def cycle_diagnostic(workspace_id, local):
    return {"code": "CTX-CYCLE-001", "severity": "error", "resultStatus": "failed", "summary": alias.CYCLE_SUMMARY,
            "source": {"kind": "file", "workspaceId": workspace_id, "path": f"{REQ_DIR}/{local}.md", "key": "relations.requires"}}


def reviewed_diagnostics(identifier):
    return [cycle_diagnostic(workspace, local) for workspace, local in CYCLE_DECLARERS[CASES[identifier]["corpus"]]]


# --- 期待結果 ---------------------------------------------------------------------------------

def purpose_of(identifier):
    argv = CASES[identifier]["argv"]
    return argv[argv.index("--purpose") + 1] if "--purpose" in argv else "verify"


def revision():
    return {"commit": COMMIT, "dirty": False}


def failed_context_result(identifier):
    """完全解決が成立しないので、ハッシュ値を計算せず空のコンテキスト一式を返す（`MULTI-038-02`と同じ形）。禁止された循環は`unresolvedStrongRelations`に数えない。"""
    case = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": purpose_of(identifier),
        "workspace": {"id": REQUEST, "path": "."}, "roots": [case["root"]], "contextDigest": None,
        "revision": revision(),
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0,
                       "workspaces": [{"id": REQUEST, "path": "."}], "crossWorkspaceEdges": []},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [], "constraintLedger": {"statements": []},
        "coverage": {**alias.bucket(), "adjacent": []},
        "durationMs": 0, "diagnostics": reviewed_diagnostics(identifier),
    }


def failed_verify_result(identifier):
    """診断は検証対象の`diagnostics`に置き、ハッシュ値、規範文、テスト割当てを持たず、テストを開始しない（`MULTI-038-03`と同じ形）。"""
    case = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected",
        "workspace": {"id": REQUEST, "path": "."},
        "targetResults": [{"target": case["root"], "status": "failed", "contextDigest": None, "statements": [],
                           "bindingRefs": [], "diagnostics": reviewed_diagnostics(identifier)}],
        "revision": revision(), "commands": [], "durationMs": 0, "diagnostics": [],
    }


def passed_context_result(identifier, context_digest):
    """詳細度`compact`の成功する結果。起点（役割`root`）と、`requires`で到達した他のメンバーの文書（役割`requirement`）だけを持つ。"""
    case = CASES[identifier]
    if case["corpus"] == "member-missing":
        documents = [
            alias.bundle_document("platform::REQ-050", "platform", "requirement", "root", f"{REQ_DIR}/REQ-050.md", ["root"], "reference"),
            alias.bundle_document("api::REQ-150", "api", "requirement", "requirement", f"{REQ_DIR}/REQ-150.md",
                                  ["requires:platform::REQ-050"], "reference"),
        ]
        # `api::REQ-150`の`REQ-999`の参照切れは検査しないので、`unresolvedStrongRelations`は0、解決は完了とする。
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "platform", "path": "."}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "requires", "source": "platform::REQ-050", "target": "api::REQ-150"}]}
    elif case["corpus"] == "member-outside":
        documents = [alias.bundle_document("platform::REQ-001", "platform", "requirement", "root", f"{REQ_DIR}/REQ-001.md", ["root"], "reference")]
        resolution = {"complete": True, "documentCount": 1, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "platform", "path": "."}], "crossWorkspaceEdges": []}
    else:
        raise ValueError("この入力に成功のコンテキストはありません")
    for document in documents:
        document["status"] = "approved"
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": purpose_of(identifier),
        "workspace": {"id": REQUEST, "path": "."}, "roots": [case["root"]], "contextDigest": context_digest,
        "revision": revision(), "resolution": resolution,
        "projection": {"detail": "compact", "expanded": []},
        "documents": documents, "constraintLedger": {"statements": []}, "coverage": {**alias.bucket(), "adjacent": []},
        "durationMs": 0, "diagnostics": [],
    }


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _requirement_material(workspace, local, title, requires, existing=()):
    """文書1件の材料。`strongRelations`は参照先を解決できた`requires`だけを持ち、解決できない宣言は`frontmatter.relations`にだけ残る
    （正規化仕様 §3）。`existing`は、このfixtureで実在する文書の修飾IDである。"""
    qualified = [multi_crosscheck.qualify(workspace, text) for text in requires]
    document = verify_fixtures.document_material(
        None, f"{workspace}::{local}", workspace, "requirement", title, alias.requirement(local, title, requires)[1],
        relations={"requires": qualified} if requires else None,
        statements=[verify_fixtures.statement_material(f"{workspace}::{local}:AC-01", REQ_TEXT)])
    document["strongRelations"] = [item for item in document["strongRelations"] if item["target"] in existing]
    return document


def reviewed_digest_input(identifier):
    """目的`interpret`のレビュー済みのハッシュ値の材料（参照計算A）。到達ワークスペースの閉包の文書だけを置く。"""
    corpus = CASES[identifier]["corpus"]
    if corpus == "member-missing":
        existing = {f"{workspace}::{local}" for workspace, local in DOCUMENTS[corpus]}
        documents = [_requirement_material("platform", "REQ-050", *DOCUMENTS[corpus][("platform", "REQ-050")], existing=existing),
                     _requirement_material("api", "REQ-150", *DOCUMENTS[corpus][("api", "REQ-150")], existing=existing)]
        edges = [{"relation": "requires", "source": "platform::REQ-050", "target": "api::REQ-150"}]
        return alias._material_request(False, [("platform", "."), ("api", "services/api")], documents, edges, "platform::REQ-050")
    if corpus == "member-outside":
        documents = [_requirement_material("platform", "REQ-001", *DOCUMENTS[corpus][("platform", "REQ-001")])]
        return alias._material_request(False, [("platform", ".")], documents, [], "platform::REQ-001")
    raise ValueError("この入力にハッシュ値の材料はありません")


def expected_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reference_digest(identifier, repository):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier))
    derived = multi_crosscheck.canonical_bytes(alias.derived_material(repository, CASES[identifier]["root"], purpose_of(identifier)))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


def reviewed_result(identifier):
    case = CASES[identifier]
    if case["outcome"] == "passed":
        return passed_context_result(identifier, expected_digest(identifier))
    return failed_context_result(identifier) if case["op"] == "context" else failed_verify_result(identifier)


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def reference_diagnostics(documents, closure, request):
    """閉包の文書が宣言する辺のうち診断になるもの（関係・トレースモデル §6.3）。

    循環に参加する辺は、閉包に入ったどのワークスペースの文書が宣言するものでも報告する。参照切れと型違反は、作業ワークスペースの文書だけを検査する
    （他のワークスペースの文書は`requires`の型制約だけを検査し、参照先の不在は検査しない。この群の入力は型違反を使わない）。
    """
    own = [name for name in closure if documents[name]["workspaceId"] == request]
    others = [name for name in closure if documents[name]["workspaceId"] != request]
    cycles = [item for item in alias.reference_diagnostics(documents, others) if item["code"] == "CTX-CYCLE-001"]
    return sorted(alias.reference_diagnostics(documents, own) + cycles, key=alias.diagnostic_key)


def defective_diagnostics(documents, closure, request):
    """修正前の報告の範囲: 作業ワークスペースの文書が宣言する辺だけを検査する。この群の入力が欠陥を検出できることを確かめるために再現する。"""
    return alias.reference_diagnostics(documents, [name for name in closure if documents[name]["workspaceId"] == request])


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた閉包・診断・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, _, workspaces, documents = alias.load_tree(repository)
    if single:
        raise ValueError("この群は複合ワークスペースだけを扱います")
    root = case["root"]
    order, _, _ = alias.interpret_closure(documents, root, "interpret")
    diagnostics = reference_diagnostics(documents, order, REQUEST)
    actual = result["targetResults"][0]["diagnostics"] if case["op"] == "verify" else result["diagnostics"]
    if case["outcome"] == "failed":
        if actual != diagnostics or not diagnostics:
            raise ValueError("診断が入力からの参照計算と異なります")
        if case["op"] == "context":
            counted = sum(1 for item in diagnostics if item["code"] in {"SPEC-RELATION-MISSING-001", "CTX-RELATION-TYPE-001"})
            if result["resolution"]["unresolvedStrongRelations"] != counted:
                raise ValueError("`unresolvedStrongRelations`が入力からの参照計算と異なります")
        return
    if diagnostics or actual != []:
        raise ValueError("成功するfixtureは診断を持ちません")
    expected = alias.reference_context(documents, workspaces, REQUEST, root, "interpret")
    if result["resolution"]["documentCount"] != len(expected["documents"]) or len(result["documents"]) != len(expected["documents"]):
        raise ValueError("文書数が入力からの参照計算と異なります")
    for shown, wanted in zip(result["documents"], expected["documents"]):
        view = {key: shown[key] for key in ("id", "workspaceId", "kind", "role", "path", "reachedBy")}
        reference = {key: wanted[key] for key in ("id", "workspaceId", "kind", "role", "path", "reachedBy")}
        if view != reference or shown["status"] != documents[wanted["id"]]["frontmatter"]["status"]:
            raise ValueError("文書が入力からの参照計算と異なります")
    if (result["resolution"]["workspaces"] != expected["workspaces"] or result["resolution"]["crossWorkspaceEdges"] != expected["edges"]):
        raise ValueError("到達ワークスペースまたは横断するエッジが入力からの参照計算と異なります")
    if result["contextDigest"] != reference_digest(identifier, repository):
        raise ValueError("ハッシュ値が参照計算と異なります")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力から確かめる。欠陥を検出できる入力であること（修正前の範囲の報告が期待と異なること）を含む。"""
    case = CASES[identifier]
    single, _, _, documents = alias.load_tree(repository)
    if single:
        raise ValueError("この群は複合ワークスペースだけを扱います")
    corpus, root = case["corpus"], case["root"]
    order, _, _ = alias.interpret_closure(documents, root, "interpret")
    cyclic = {name for name, _ in alias.cyclic_edges(documents)}
    correct = reference_diagnostics(documents, order, REQUEST)
    old = defective_diagnostics(documents, order, REQUEST)
    if corpus in CYCLE_DECLARERS:
        declarers = {f"{workspace}::{local}" for workspace, local in CYCLE_DECLARERS[corpus]}
        if cyclic != declarers or not cyclic <= set(order):
            raise ValueError("循環に参加する文書がすべて閉包に入る必要があります")
        if len({documents[name]["workspaceId"] for name in cyclic}) != {"cross": 2, "member-cycle": 1, "three-way": 3}[corpus]:
            raise ValueError("循環に参加するワークスペースの数が異なります")
        if corpus == "member-cycle" and any(documents[name]["workspaceId"] == REQUEST for name in cyclic):
            raise ValueError("循環は作業ワークスペースの外だけで閉じる必要があります")
        if corpus != "member-cycle" and not any(documents[name]["workspaceId"] == REQUEST for name in cyclic):
            raise ValueError("ワークスペースをまたぐ循環は作業ワークスペースの辺を含む必要があります")
        # 陰性対照の構成: 修正前の範囲（作業ワークスペースの辺だけ）の報告は、期待する報告より少ない。
        if len(old) >= len(correct) or any(item not in correct for item in old):
            raise ValueError("修正前の範囲の報告は期待する報告の真部分集合である必要があります")
        if corpus == "member-cycle" and old:
            raise ValueError("修正前の範囲では報告が空になる必要があります")
        if case["op"] == "verify" and (repository / TEST_PATH).read_bytes() != TEST_BYTES:
            raise ValueError("起点はテスト対応が通る入力である必要があります")
    elif corpus == "member-missing":
        # 他のメンバーの文書の参照切れ。循環はなく、全文書の辺を検査する参照計算なら参照切れを1件導く（それを報告しないことが期待）。
        if cyclic or "api::REQ-999" in documents or set(order) != {"platform::REQ-050", "api::REQ-150"}:
            raise ValueError("循環はなく、`api::REQ-150`が存在しない`REQ-999`を`requires`する必要があります")
        every = alias.reference_diagnostics(documents, order)
        if [(item["code"], item["source"]["workspaceId"], item["evidence"]) for item in every] != [("SPEC-RELATION-MISSING-001", "api", "REQ-999")]:
            raise ValueError("全文書を検査すれば他のメンバーの参照切れが1件導かれる入力である必要があります")
        if correct or old:
            raise ValueError("参照切れは他のワークスペースの文書では検査しない")
    elif corpus == "member-outside":
        # 他のメンバーの循環は存在するが、閉包の外にある。
        if cyclic != {"api::REQ-170", "api::REQ-171"} or set(order) != {root} or cyclic & set(order):
            raise ValueError("循環は閉包の外の他のメンバーの2文書だけにある必要があります")
        if correct or old:
            raise ValueError("閉包の外の循環は報告しない")
    else:
        raise ValueError(f"未知の入力の種類です: {corpus}")
    if (case["outcome"] == "failed") != bool(correct):
        raise ValueError("失敗するfixtureには、診断になる辺が必要です")
    return order


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
        (fixture / RESULT_FILES[CASES[identifier]["op"]]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-cross-cycle-") as temporary:
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
            result = json.loads((fixture / RESULT_FILES[CASES[identifier]["op"]]).read_text())
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-cross-cycle-") as temporary:
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
                            Draft202012Validator({"$ref": "#/$defs/" + alias.FIXTURE_KINDS[
                                {"requirements": "requirement", "technical": "technical", "decisions": "decision",
                                 "tasks": "task"}[path.parent.name]], "$defs": frontmatter["$defs"]}).validate(value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}

