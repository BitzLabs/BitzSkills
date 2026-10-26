"""複合ワークスペースの`check`が、自ワークスペースを自身のIDで修飾した`tests[].covers`を非修飾形式と同じに扱うことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C56とADR-051の追加に対応する。複合ワークスペースの`check`は、`web`の文書の`covers: [web::REQ-001:AC-01]`のように、
自ワークスペースを自身のIDで修飾した`tests[].covers`を`SPEC-TEST-COVERAGE-001`で拒否していた。許可する値の集合の自ワークスペースの分を
非修飾の形だけで作り、宣言の参照を修飾したまま比べたため、`refines`と`covers`の書き方（修飾の有無、文書IDか規範文IDか）の組合せによって、
同じ対象が通ったり拒否されたりした。`context`と`verify`は同じ入力を通していた。既存の`MULTI-038-18`・`22`などは自ワークスペースの修飾の`covers`を
含むが`context`しか実行しないので、この欠陥を拾えなかった。この群は、`check`でこの形を通すことを3件、対照を1件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-046-01` | `check --all-workspaces`、`.` | 自ワークスペースの修飾の`covers`（規範文、規範文を持たない文書の自身の文書ID、`refines`で直接参照する規範文・文書の規範文）を通す。`passed`／0 |
| `MULTI-046-02` | `check --full`、`apps/web`（メンバーの単独） | `MULTI-046-01`と同じ入力。メンバーの`web`の単独の完全検査でも通す。`passed`／0 |
| `MULTI-046-03` | `check --all-workspaces`、`.` | 対照（陰性）: 存在しない`web::REQ-001:AC-99`と、`refines`していない`web::REQ-002:AC-01`だけを`SPEC-TEST-COVERAGE-001`で拒否する。`evidence`は宣言どおり（修飾したまま）。`failed`／1 |
| `MULTI-046-04` | `check --all-workspaces`、`.` | 対照: `MULTI-046-01`と同じ文書を、自ワークスペースの参照をすべて非修飾に書き換えた入力。結果は`MULTI-046-01`と同じ。`passed`／0 |

基本のリポジトリは、ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）である。`platform`と`api`は文書をREQ-001の1件ずつ持つ。
`web`の文書（`MULTI-046-01`・`02`・`04`）は次のとおりである。表記は自ワークスペースを修飾した形で書く（`MULTI-046-04`は修飾を外す）。

| 文書 | `refines` | `covers` | `covers`の分類 |
|---|---|---|---|
| `REQ-001`（規範文`AC-01`） | なし | `web::REQ-001:AC-01` | (a) 自身の規範文 |
| `REQ-002`（規範文`AC-01`） | なし | `web::REQ-002:AC-01` | (a) |
| `TECH-010`（規範文`C-01`） | `web::REQ-001:AC-01` | `web::REQ-001:AC-01`、`web::TECH-010:C-01` | (c) 直接参照する規範文そのもの、(a) |
| `TECH-011`（規範文なし） | なし | `web::TECH-011` | (b) 規範文を持たない文書の自身の文書ID |
| `TECH-012`（規範文なし） | `web::REQ-002`（文書ID） | `web::REQ-002:AC-01` | (c) 直接参照する文書の規範文 |
| `TECH-013`（規範文なし） | `REQ-002:AC-01`（非修飾） | `web::REQ-002:AC-01` | (c)。`refines`は非修飾、`covers`は修飾（書き方の組合せの1つ） |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §4: 「`relations`と`tests[].covers`は同じワークスペースを参照するとき非修飾形式を許可し、…同じワークスペースを自身のIDで修飾した参照
  （`web`の文書の`web::REQ-001`）も許可し、非修飾形式と同じ文書または規範文を指すものとして扱う。診断の`evidence`は宣言どおりの表記を保つ」。
- 文書・フロントマター・状態仕様 §5: `covers`に指定できる値は、(a) 宣言する文書自身の規範文ID、(b) 規範文を持たない場合の、その文書自身の文書ID、
  (c) `relations.refines`で直接参照する文書の規範文ID、または直接参照する規範文そのもの。存在しない規範文は重大度`error`。
- 関係・トレースモデル §9: 別のワークスペースの規範文を`covers`へ指定できるのは、宣言する文書が、その規範文またはそれを所有する文書を直接`refines`する場合に限る。
- 結果・診断・終了コード §4: `SPEC-TEST-COVERAGE-001`は`covers`要素を単位とし、`evidence`に参照先を宣言どおりの文字列で持つ。§7: 診断の順序は
  発生元のワークスペースID、`path`、…の辞書順で、すべて同じ診断は宣言の順。診断レジストリ: `SPEC-TEST-COVERAGE-001`は`error`／`failed`、発生元は`file`。

参照計算`reference_*`は、入力の木構造（文書のフロントマターと本文）から、ワークスペースごとの文書数と規範文数、許可する値の集合、拒否する`covers`を導く。
リテラルの期待値がこの結果と一致することを要求する。原因の構成（`check_conditions`）は、入力が欠陥を検出できる形（修飾した自ワークスペースの`covers`を
(a)(b)(c)の各分類で持つこと）であること、対照が陰性になる形であることを、入力の木構造から確かめる。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_check_fixtures, multi_crosscheck, multi_reference
from .digest_crosscheck import read_statements
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = multi_check_fixtures.MEMBERS
WORKSPACE_PATHS = {"platform": ".", "web": "apps/web", "api": "services/api"}
COMMANDS = {"platform": "platform", "web": "frontend", "api": "backend"}
KIND_DIRECTORY = {"REQ": "requirements", "TECH": "technical"}
TEST_BYTES = b"def test_ok():\n    assert True\n"
SUMMARY = "フィールドcoversが存在しない規範文を参照しています"

# id: コーパス, 実行ディレクトリ, 引数列の残り, 状態, 終了コード, 説明。
CASES = {
    "MULTI-046-01": ("qualified", ".", ["check", "--all-workspaces"], "passed", 0,
                     "複合ワークスペースの全体のcheckは、自ワークスペースを自身のIDで修飾したcoversを非修飾形式と同じに扱って通す"),
    "MULTI-046-02": ("qualified", "apps/web", ["check", "--full"], "passed", 0,
                     "メンバーの中の単独のcheck --fullは、自ワークスペースを自身のIDで修飾したcoversを非修飾形式と同じに扱って通す"),
    "MULTI-046-03": ("invalid", ".", ["check", "--all-workspaces"], "failed", 1,
                     "自ワークスペースを修飾したcoversでも、存在しない規範文とrefinesしていない規範文だけを宣言どおりのevidenceで拒否する"),
    "MULTI-046-04": ("plain", ".", ["check", "--all-workspaces"], "passed", 0,
                     "対照: 自ワークスペースの参照をすべて非修飾に書いた同じ文書は、修飾した入力と同じ結果で通る"),
}
WORKING = {"MULTI-046-02": "web"}

# --- 入力の表 -------------------------------------------------------------------------------------
#
# (ワークスペース, ローカルID): dict(title, statement=(ラベル, 文)またはNone, refines=[...], covers=[...])。
# 参照は「修飾した」コーパスの宣言どおりの表記で書く。`plain`のコーパスは、自ワークスペースの接頭辞（`web::`）を外す。
# 規範文は、REQでは`Acceptance Criteria`のAC-01、TECHでは`Constraints`のC-01に置く。
VALID_DOCUMENTS = {
    ("platform", "REQ-001"): dict(title="起点の基準", statement=("AC-01", "秘密情報を出力しない"),
                                  covers=["platform::REQ-001:AC-01"]),
    # `api`は修飾しない`covers`のまま（非修飾形式が引き続き通ることの対照）。
    ("api", "REQ-001"): dict(title="API側の基準", statement=("AC-01", "応答形式を固定する"), covers=["REQ-001:AC-01"]),
    ("web", "REQ-001"): dict(title="Web側の基準", statement=("AC-01", "入力を検証する"), covers=["web::REQ-001:AC-01"]),
    ("web", "REQ-002"): dict(title="Web側のもう1つの基準", statement=("AC-01", "結果を返す"), covers=["web::REQ-002:AC-01"]),
    ("web", "TECH-010"): dict(title="規範文を直接refinesする具体化", statement=("C-01", "検証を呼び出す"),
                              refines=["web::REQ-001:AC-01"], covers=["web::REQ-001:AC-01", "web::TECH-010:C-01"]),
    ("web", "TECH-011"): dict(title="規範文を持たない具体化", statement=None, covers=["web::TECH-011"]),
    ("web", "TECH-012"): dict(title="文書IDでrefinesする具体化", statement=None,
                              refines=["web::REQ-002"], covers=["web::REQ-002:AC-01"]),
    ("web", "TECH-013"): dict(title="非修飾でrefinesし修飾でcoversする具体化", statement=None,
                              refines=["REQ-002:AC-01"], covers=["web::REQ-002:AC-01"]),
}
# 対照（陰性）: 存在しない規範文`web::REQ-001:AC-99`と、`refines`していない存在する規範文`web::REQ-002:AC-01`。
# 同じ文書に、宣言どおり通る修飾の`covers`（`web::REQ-001:AC-01`、`web::TECH-010:C-01`）を併記する。
INVALID_DOCUMENTS = {
    ("platform", "REQ-001"): VALID_DOCUMENTS[("platform", "REQ-001")],
    ("api", "REQ-001"): VALID_DOCUMENTS[("api", "REQ-001")],
    ("web", "REQ-001"): dict(title="Web側の基準", statement=("AC-01", "入力を検証する"),
                             covers=["web::REQ-001:AC-01", "web::REQ-001:AC-99"]),
    ("web", "REQ-002"): VALID_DOCUMENTS[("web", "REQ-002")],
    ("web", "TECH-010"): dict(title="規範文を直接refinesする具体化", statement=("C-01", "検証を呼び出す"),
                              refines=["web::REQ-001:AC-01"], covers=["web::TECH-010:C-01", "web::REQ-002:AC-01"]),
}


def own_prefix(workspace):
    return f"{workspace}::"


def plain(workspace, reference):
    """自ワークスペースの修飾を外す。他のワークスペースの修飾は保つ。"""
    return reference[len(own_prefix(workspace)):] if reference.startswith(own_prefix(workspace)) else reference


def documents_of(identifier):
    corpus = CASES[identifier][0]
    table = INVALID_DOCUMENTS if corpus == "invalid" else VALID_DOCUMENTS
    if corpus != "plain":
        return table
    return {(workspace, local): {**spec, "refines": [plain(workspace, item) for item in spec.get("refines", [])],
                                 "covers": [plain(workspace, item) for item in spec["covers"]]}
            for (workspace, local), spec in table.items()}


def test_path(local):
    return f"tests/test_{local.lower().replace('-', '_')}.py"


def render(workspace, local, spec):
    """文書のファイルの全文。"""
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: approved\n"
    if spec.get("refines"):
        head += f"relations:\n  refines: [{', '.join(spec['refines'])}]\n"
    head += (f"tests:\n  - path: {test_path(local)}\n    covers: [{', '.join(spec['covers'])}]\n"
             f"    command: {COMMANDS[workspace]}\n---\n\n")
    body = f"# {local} {spec['title']}\n\n"
    if local.startswith("REQ"):
        label, text = spec["statement"]
        body += (f"## Intent\n\n{spec['title']}を定める。\n\n## Acceptance Criteria\n\n"
                 f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n\n"
                 "## Verification\n\nそれぞれのtestで確認する。\n")
    else:
        body += f"## Context\n\n{spec['title']}を定める。\n"
        if spec["statement"] is not None:
            label, text = spec["statement"]
            body += (f"\n## Constraints\n\n"
                     f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n")
    return head + body


def reviewed_inputs(identifier):
    """`repo/`の全入力（パス→バイト列）。"""
    files = {
        # ルートワークスペースもテスト対応のコマンドを持つ（メンバーの設定と同じ形のコマンドの定義を、カタログの設定へ足す）。
        ".spec/bitz.yaml": (multi_reference.root_config(MEMBERS)
                            + f"verify:\n  commands:\n    {COMMANDS['platform']}:\n      argv: [\"/bin/true\", \"{{tests}}\"]\n      cwd: .\n").encode(),
        "apps/web/.spec/bitz.yaml": multi_reference.member_config("web", COMMANDS["web"]).encode(),
        "services/api/.spec/bitz.yaml": multi_reference.member_config("api", COMMANDS["api"]).encode(),
    }
    for (workspace, local), spec in documents_of(identifier).items():
        base = "" if WORKSPACE_PATHS[workspace] == "." else WORKSPACE_PATHS[workspace] + "/"
        files[f"{base}.spec/{KIND_DIRECTORY[local.partition('-')[0]]}/{local}.md"] = render(workspace, local, spec).encode()
        files[f"{base}{test_path(local)}"] = TEST_BYTES
    return files


def reviewed_manifest(identifier):
    _, cwd, argv, status, exit_code, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": cwd, "argv": [*argv, "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/check.json", "reportFileCount": 0},
    }


# --- 期待結果（リテラル） -----------------------------------------------------------------------------

REVISION = {"base": COMMIT, "commit": COMMIT, "dirty": False}


def rejection(workspace, path, evidence, key="tests[0].covers"):
    return {
        "code": "SPEC-TEST-COVERAGE-001", "severity": "error", "resultStatus": "failed", "summary": SUMMARY,
        "source": {"kind": "file", "workspaceId": workspace, "path": path, "key": key},
        "evidence": evidence,
    }


def reviewed_result(identifier):
    """リテラルで書いたレビュー済みの期待値。"""
    corpus = CASES[identifier][0]
    if identifier == "MULTI-046-02":
        # `web`の6文書（REQ-001、REQ-002、TECH-010〜013）と規範文3件（REQ-001:AC-01、REQ-002:AC-01、TECH-010:C-01）。
        # `web`の文書は、他のワークスペースの文書を参照しないので、閉包は`web`の文書だけである。
        return {"schemaVersion": "1.0", "operation": "check", "workspace": {"id": "web", "path": "apps/web"},
                "durationMs": 0, "scope": "full", "status": "passed", "revision": dict(REVISION),
                "checkedDocumentCount": 6, "checkedStatementCount": 3, "diagnostics": []}
    web_documents, web_statements = (3, 3) if corpus == "invalid" else (6, 3)
    web_diagnostics = [] if corpus != "invalid" else [
        rejection("web", ".spec/requirements/REQ-001.md", "web::REQ-001:AC-99"),
        rejection("web", ".spec/technical/TECH-010.md", "web::REQ-002:AC-01"),
    ]

    def workspace(identifier_, path, status, documents, statements, diagnostics):
        return {"id": identifier_, "path": path, "status": status, "checkedDocumentCount": documents,
                "checkedStatementCount": statements, "durationMs": 0, "diagnostics": diagnostics}

    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces",
        "status": "failed" if corpus == "invalid" else "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [
            workspace("platform", ".", "passed", 1, 1, []),
            workspace("api", "services/api", "passed", 1, 1, []),
            workspace("web", "apps/web", "failed" if web_diagnostics else "passed", web_documents, web_statements,
                      web_diagnostics),
        ],
        "revision": dict(REVISION), "durationMs": 0, "diagnostics": [],
    }


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def statement_ids(document):
    return [item["id"] for item in read_statements(document["body"])]


def document_path(document):
    kind = {"requirement": "requirements", "technical": "technical"}[document["kind"]]
    return f".spec/{kind}/{document['frontmatter']['id']}.md"


def exists(documents, target):
    """修飾した参照先（文書または規範文）が実在するか。"""
    owner = multi_crosscheck.owner(target)
    if owner not in documents:
        return False
    local = target.partition("::")[2]
    return ":" not in local or local in statement_ids(documents[owner])


def allowed_covers(documents, identifier):
    """`covers`に指定できる修飾した値の集合（文書・フロントマター・状態仕様 §5の(a)(b)(c)）。

    自ワークスペースの修飾は、非修飾形式と同じ対象を指すので、`multi_crosscheck.qualify`で修飾IDにそろえてから比べる。
    """
    document = documents[identifier]
    workspace = document["workspaceId"]
    own = statement_ids(document)
    allowed = {f"{workspace}::{item}" for item in own}
    if not own:
        allowed.add(identifier)
    for text in document["frontmatter"].get("relations", {}).get("refines", []):
        target = multi_crosscheck.qualify(workspace, text)
        if not exists(documents, target):
            continue
        if ":" in target.partition("::")[2]:
            allowed.add(target)
        else:
            allowed |= {f"{target.partition('::')[0]}::{item}" for item in statement_ids(documents[target])}
    return allowed


def reference_rejections(documents):
    """拒否する`covers`の要素を、(ワークスペース, パス, キー, 宣言どおりの文字列)として、診断の順序（結果・診断・終了コード §7）で返す。"""
    found = []
    for identifier, document in documents.items():
        allowed = allowed_covers(documents, identifier)
        for index, entry in enumerate(document["frontmatter"].get("tests", [])):
            for text in entry["covers"]:
                if multi_crosscheck.qualify(document["workspaceId"], text) not in allowed:
                    found.append((document["workspaceId"], document_path(document), f"tests[{index}].covers", text))
    # 同じ発生元は宣言の順（`sorted`は安定で、`documents`の反復順は宣言の順ではないので、ワークスペースとパスで並べる）。
    return sorted(found, key=lambda item: (item[0], item[1]))


def reference_counts(documents):
    """ワークスペースごとの(文書数, 規範文数)。"""
    counts = {}
    for document in documents.values():
        documents_count, statements_count = counts.get(document["workspaceId"], (0, 0))
        counts[document["workspaceId"]] = (documents_count + 1, statements_count + len(statement_ids(document)))
    return counts


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力の木構造からの参照計算と一致することを要求する。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    rejections = reference_rejections(documents)
    by_workspace = {}
    for workspace, path, key, evidence in rejections:
        by_workspace.setdefault(workspace, []).append(rejection(workspace, path, evidence, key))
    counts = reference_counts(documents)
    if identifier == "MULTI-046-02":
        reference = multi_check_fixtures.reference_check(repository, "full", "web", CASES[identifier][1], None)
        if reference["diagnostics"] or rejections:
            raise ValueError("`MULTI-046-02`の入力は、診断を持たない必要があります")
        if (result["workspace"] != reference["workspace"] or result["checkedDocumentCount"] != reference["documentCount"]
                or result["checkedStatementCount"] != reference["statementCount"]
                or sorted(name for name in reference["inspected"] if not name.startswith("web::"))):
            raise ValueError("`workspace`または件数が入力からの参照計算と異なります")
        if (result["checkedDocumentCount"], result["checkedStatementCount"]) != counts["web"]:
            raise ValueError("完全検査の件数が`web`の文書と規範文の件数と異なります")
        if (result["status"] == "passed") != (not rejections) or result["diagnostics"]:
            raise ValueError("状態が診断の有無と一致しません")
        return
    if result["diagnostics"]:
        raise ValueError("全体の`check`の最上位の診断は空である必要があります")
    ordered = [workspaces_entry["id"] for workspaces_entry in result["workspaces"]]
    if ordered != ["platform", *sorted(name for name in workspaces if name != "platform")]:
        raise ValueError("ワークスペースの順がルート、メンバーのID辞書順と異なります")
    for entry in result["workspaces"]:
        documents_count, statements_count = counts[entry["id"]]
        diagnostics = by_workspace.get(entry["id"], [])
        if (entry["path"] != workspaces[entry["id"]]["path"] or entry["checkedDocumentCount"] != documents_count
                or entry["checkedStatementCount"] != statements_count or entry["diagnostics"] != diagnostics
                or entry["status"] != ("failed" if diagnostics else "passed")):
            raise ValueError(f"ワークスペース{entry['id']}の結果が入力からの参照計算と異なります")
    if result["status"] != ("failed" if rejections else "passed"):
        raise ValueError("状態が診断の有無と一致しません")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく入力の木構造から確かめる。"""
    corpus = CASES[identifier][0]
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    if git_dirty(repository):
        raise ValueError("fixtureは変更集合を持ってはいけません")
    if any(document["frontmatter"]["status"] != "approved" for document in documents.values()):
        raise ValueError("文書はすべて状態`approved`である必要があります")
    rejections = reference_rejections(documents)

    # 関係はすべて実在する参照を持つ（`SPEC-RELATION-MISSING-001`の混入を避け、原因を`covers`だけにする）。
    for identifier_, document in documents.items():
        for key, values in document["frontmatter"].get("relations", {}).items():
            if any(not exists(documents, multi_crosscheck.qualify(document["workspaceId"], text)) for text in values):
                raise ValueError(f"{identifier_}の`{key}`は実在する参照である必要があります")
    web = {local: document for name, document in documents.items() if document["workspaceId"] == "web"
           for local in [name.partition("::")[2]]}
    covers = {local: [text for entry in document["frontmatter"]["tests"] for text in entry["covers"]]
              for local, document in web.items()}
    if corpus == "plain":
        # 対照: 自ワークスペースの修飾を、参照のどこにも持たない。
        for document in documents.values():
            texts = [text for entry in document["frontmatter"]["tests"] for text in entry["covers"]]
            texts += [text for values in document["frontmatter"].get("relations", {}).values() for text in values]
            if any("::" in text for text in texts):
                raise ValueError("`plain`のcorpusは修飾した参照を持ってはいけません")
        if rejections:
            raise ValueError("`plain`のcorpusは、拒否する`covers`を持ってはいけません")
        if set(web) != {"REQ-001", "REQ-002", "TECH-010", "TECH-011", "TECH-012", "TECH-013"}:
            raise ValueError("`plain`のcorpusの`web`の文書が異なります")
        return
    # 自ワークスペースの修飾の`covers`を、(a)(b)(c)の各分類で持つ。
    self_qualified = {local: [text for text in texts if text.startswith("web::")] for local, texts in covers.items()}
    if corpus == "invalid":
        wanted = [("web", ".spec/requirements/REQ-001.md", "tests[0].covers", "web::REQ-001:AC-99"),
                  ("web", ".spec/technical/TECH-010.md", "tests[0].covers", "web::REQ-002:AC-01")]
        if rejections != wanted:
            raise ValueError("拒否する`covers`は、存在しない`web::REQ-001:AC-99`と`refines`していない`web::REQ-002:AC-01`の2件だけである必要があります")
        # 存在しない参照と、存在するが許可されない参照を1件ずつ持つ（原因を区別できる）。
        if exists(documents, "web::REQ-001:AC-99") or not exists(documents, "web::REQ-002:AC-01"):
            raise ValueError("1件目は存在せず、2件目は存在する規範文である必要があります")
        if "web::REQ-002:AC-01" in allowed_covers(documents, "web::TECH-010"):
            raise ValueError("`web::TECH-010`は`web::REQ-002:AC-01`を許可されてはいけません")
        # 拒否する`covers`と同じ文書に、通る修飾の`covers`が併記されている（修飾そのものは拒否の原因ではない）。
        if self_qualified["REQ-001"] != ["web::REQ-001:AC-01", "web::REQ-001:AC-99"] or "web::TECH-010:C-01" not in covers["TECH-010"]:
            raise ValueError("通る修飾の`covers`が併記されている必要があります")
        return
    if rejections:
        raise ValueError("`qualified`のcorpusは、拒否する`covers`を持ってはいけません")
    # (a) 自身の規範文。
    if "web::REQ-001:AC-01" not in covers["REQ-001"] or "web::TECH-010:C-01" not in covers["TECH-010"]:
        raise ValueError("(a)自身の規範文を修飾した`covers`が必要です")
    # (b) 規範文を持たない文書の自身の文書ID。
    if statement_ids(web["TECH-011"]) or covers["TECH-011"] != ["web::TECH-011"]:
        raise ValueError("(b)規範文を持たない文書の自身の文書IDを修飾した`covers`が必要です")
    # (c) 直接参照する規範文そのもの、直接参照する文書の規範文（文書IDまたは非修飾の規範文で`refines`）。
    refines = {local: web[local]["frontmatter"].get("relations", {}).get("refines", []) for local in web}
    if refines["TECH-010"] != ["web::REQ-001:AC-01"] or "web::REQ-001:AC-01" not in covers["TECH-010"]:
        raise ValueError("(c)直接参照する規範文そのものを修飾した`covers`が必要です")
    if refines["TECH-012"] != ["web::REQ-002"] or covers["TECH-012"] != ["web::REQ-002:AC-01"] or statement_ids(web["TECH-012"]):
        raise ValueError("(c)文書IDで`refines`する文書の規範文を修飾した`covers`が必要です")
    if refines["TECH-013"] != ["REQ-002:AC-01"] or covers["TECH-013"] != ["web::REQ-002:AC-01"]:
        raise ValueError("`refines`は非修飾、`covers`は修飾の組合せが必要です")
    # `api`の非修飾の`covers`は対照として通り、他のワークスペースの文書は`web`の文書を参照しない（`MULTI-046-02`の閉包を`web`に閉じる）。
    for name, document in documents.items():
        if document["workspaceId"] != "web":
            texts = [text for values in document["frontmatter"].get("relations", {}).values() for text in values]
            if texts:
                raise ValueError("`web`以外の文書は関係を宣言してはいけません")
    if any("::" in text for local, texts in refines.items() for text in texts if not text.startswith("web::")):
        raise ValueError("`web`の文書は、他のワークスペースの文書を参照してはいけません")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


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
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-self-covers-") as temporary:
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-self-covers-") as temporary:
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
                    _, _, documents = multi_crosscheck.load_workspaces(repository)
                    for document in documents.values():
                        Draft202012Validator({"$ref": "#/$defs/" + {
                            "requirement": "reqFrontmatter", "technical": "techFrontmatter"}[document["kind"]],
                            "$defs": frontmatter["$defs"]}).validate(document["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
