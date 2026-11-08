"""`verify`が、検証対象ごとに完全な閉包の上限（`CTX-LIMIT-001`）を判定することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C95と、ADR-051の追加に対応する。ユーザーの決定により、規範は次のとおりに明記された（`bitz verify`仕様 §4の1.と§9）。

- `verify`も`context` §8と同じ規則で、完全な閉包の上限を判定する。使う値は起点を所有するワークスペースの`context.maxDocuments`と`context.maxBytes`で、
  バイト数は詳細度`standard`の提示で測る。
- 上限を超えた検証対象は、診断`CTX-LIMIT-001`（`blocked`）、`contextDigest: null`、`statements: []`、`bindingRefs: []`とし、テストを起動しない。独立した検証対象は続ける。
- 上限で止まる結果には、`related`の参照切れの警告（`SPEC-RELATION-ADVISORY-MISSING-001`）を加えない（`context` §10と同じ）。
- 診断の発生元は起点の文書（`context`と同じ）、文言は`context`の既存の承認済みの文言（文書数、バイト数）を使う。新しい文言はない。

修正前のCoreは、`verify`が上限を判定せず、上限を超えた閉包を通過にしてテストを起動した（`context --purpose verify`は`CTX-LIMIT-001`でblockedにする。`SINGLE-048-01`・`02`、`SINGLE-166-06`）。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-176-01` | `verify REQ-001` | `SINGLE-042`のcorpus（閉包は2文書）。`context.maxDocuments: 1` | `blocked`／2。`CTX-LIMIT-001`（文書数）の1件。`contextDigest: null`、`commands`は空 |
| `SINGLE-176-02` | 同上 | `SINGLE-048-02`の入力（REQ-001の本文を詰め物で増やす）。`context.maxBytes: 4096` | `blocked`／2。`CTX-LIMIT-001`（バイト数）の1件 |
| `SINGLE-176-03` | 同上 | `SINGLE-168-03`の入力（`TECH-001`が存在しない`ADR-099`を`related`する）。`context.maxDocuments: 1` | `blocked`／2。`CTX-LIMIT-001`の1件だけ。`related`の警告を加えない |
| `SINGLE-176-04` | `verify REQ-001 REQ-002` | `REQ-001`の閉包は3文書（`TECH-002`が`TECH-001`を`refines`する）、`REQ-002`は2文書。`context.maxDocuments: 2` | `blocked`／2。`REQ-001`は`CTX-LIMIT-001`、`REQ-002`は`passed`でテストを起動する |
| `SINGLE-176-05` | `verify REQ-001` | `SINGLE-176-03`と同じ入力。`context.maxDocuments: 2`（閉包ちょうど） | `passed_with_warnings`／0。対照: 上限ちょうどは通り、`related`の警告を返す |
| `SINGLE-176-06` | 同上 | `SINGLE-042`のcorpus。`context.maxBytes: 4096`（標準の提示は4096バイト以下） | `passed`／0。対照: バイト数の上限の内側は通る |
| `MULTI-064-01` | `verify web::REQ-101` | `web`の閉包は2文書（`REQ-101`と、それを`refines`する`TECH-101`）。`web`の`context.maxDocuments: 1`、ルートは既定 | `blocked`／2。`CTX-LIMIT-001`（`web`、`REQ-101`の文書）の1件 |
| `MULTI-064-02` | 同上 | `MULTI-064-01`と同じ文書。ルートの`context.maxDocuments: 1`、`web`は既定 | `passed`／0。対照: 起点を所有する`web`の上限（既定）で判定し、ルートの上限は使わない |
| `MULTI-064-03` | `verify REQ-001` | ルートの`REQ-001`の閉包は3文書（`MULTI-062-05`と同じ。`web`の2文書を含む）。ルートの`context.maxDocuments: 2`、`web`は既定 | `blocked`／2。`CTX-LIMIT-001`（`platform`）の1件。他のワークスペースの文書も数える |
| `MULTI-064-04` | 同上 | `MULTI-064-03`と同じ文書。ルートの`context.maxDocuments: 3`（閉包ちょうど）、`web`は1 | `passed`／0。対照: 上限ちょうどは通り、`web`の上限は使わない |
| `MULTI-064-05` | `verify --all-workspaces` | `web`の閉包は2文書で`context.maxDocuments: 1`、`api`の`REQ-201`の閉包は1文書で既定 | `blocked`／2。`web::REQ-101`は`CTX-LIMIT-001`、`api::REQ-201`は`passed`でテストを起動する |
| `MULTI-064-06` | `verify web::REQ-101` | `MULTI-064-01`と同じ文書で、`TECH-101`が存在しない`ADR-099`を`related`する | `blocked`／2。`CTX-LIMIT-001`の1件だけ。`related`の警告を加えない |

期待値は、規範と承認済みの文言から導く。参照計算は、入力の木構造から、閉包の文書数（`multi_binding_missing_fixtures.verify_closure`）、標準の提示のバイト数
（起点と距離1の文書の正規化した本文のUTF-8の長さの和。バイト数のケースの閉包は、すべて提示形式`full`の2文書）、起点を所有するワークスペースの上限を求め、
超えたか否かが期待と一致することを要求する。判定する設定は、期待と別のワークスペース（または既定）の設定では結果が変わる入力にしてあり、
起点を所有するワークスペースの設定を使うことを、監査が要求する。`contextDigest`は、リテラルの参照計算Aと、入力の木構造から導く参照計算Bの両方で照合する。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference, multi_binding_missing_fixtures as binding_missing, multi_crosscheck, multi_reference
from . import multi_verify_fixtures as mverify
from . import related_advisory_fixtures as related
from . import verify_test_check_fixtures as tcheck
from .context_limit_fixtures import reviewed_inputs as limit_inputs
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXIT = {"passed": 0, "passed_with_warnings": 0, "blocked": 2}
SUMMARY = {"documents": "コンテキストの完全な閉包が文書数上限を超過しました", "bytes": "コンテキストの完全な閉包がバイト数上限を超過しました"}
DEFAULT_LIMITS = {"maxDocuments": 20, "maxBytes": 131072}
LIMIT_CODE = "CTX-LIMIT-001"
ADVISORY_CODE = "SPEC-RELATION-ADVISORY-MISSING-001"
MEMBERS = tcheck.MEMBERS
REQ_PATH = ".spec/requirements/REQ-001.md"
OTHER = tcheck.OTHER

# --- ケース -------------------------------------------------------------------------------
# 単一（group=single）: corpus〈入力の種類: tree（SINGLE-042）、padded（SINGLE-048-02）、related（SINGLE-168-03）、independent（tree + TECH-002 + REQ-002・TECH-003）〉、
#   limit〈`context`ブロックの設定〉、argv〈`verify`の引数〉、expect〈検証対象→"documents"|"bytes"|"pass"〉
# 複合（group=multi）: docs〈文書の種類: web（web::REQ-101と、それをrefinesするTECH-101）、cross（MULTI-062-05と同じ3文書）、all（webの2文書とapi::REQ-201）〉、
#   related〈TECH-101がrelatedで指す不在の参照先〉、limits〈ワークスペース→設定〉、argv、expect
# 共通: plain〈設定の取り違えを検出する鑑別力を要求しない検証対象（単純な対照）〉、bytes_case〈閉包がバイト数の判定の前提（2文書、すべて提示形式`full`）を満たす対照〉、description、step
CASES = {
    "SINGLE-176-01": dict(group="single", corpus="tree", limit={"maxDocuments": 1}, argv=["REQ-001"], expect={"REQ-001": "documents"}, step=4,
                          description="verifyの完全な閉包が文書数の上限を超えたとき、検証対象をCTX-LIMIT-001でblockedにし、テストを起動しない"),
    "SINGLE-176-02": dict(group="single", corpus="padded", limit={"maxBytes": 4096}, argv=["REQ-001"], expect={"REQ-001": "bytes"}, step=4,
                          description="verifyの完全な閉包が標準の提示のバイト数の上限を超えたとき、検証対象をCTX-LIMIT-001でblockedにする"),
    "SINGLE-176-03": dict(group="single", corpus="related", limit={"maxDocuments": 1}, argv=["REQ-001"], expect={"REQ-001": "documents"}, step=4,
                          description="上限で止まるverifyの検証対象に、relatedの参照切れの警告を加えない"),
    "SINGLE-176-04": dict(group="single", corpus="independent", limit={"maxDocuments": 2}, argv=["REQ-001", "REQ-002"],
                          expect={"REQ-001": "documents", "REQ-002": "pass"}, plain=["REQ-002"], step=4,
                          description="上限で止まる検証対象があっても、独立した検証対象は続け、そのテストを起動する"),
    "SINGLE-176-05": dict(group="single", corpus="related", limit={"maxDocuments": 2}, argv=["REQ-001"], expect={"REQ-001": "pass"}, plain=["REQ-001"], step=4,
                          description="対照: 閉包が文書数の上限ちょうどなら通り、relatedの参照切れの警告を返す"),
    "SINGLE-176-06": dict(group="single", corpus="tree", limit={"maxBytes": 4096}, argv=["REQ-001"], expect={"REQ-001": "pass"}, plain=["REQ-001"], bytes_case=True, step=4,
                          description="対照: 標準の提示のバイト数がバイト数の上限以下なら通る"),
    "MULTI-064-01": dict(group="multi", docs="web", related=None, limits={"web": {"maxDocuments": 1}}, argv=["web::REQ-101"],
                         expect={"web::REQ-101": "documents"}, step=5,
                         description="複合ワークスペースのverifyが、起点を所有するワークスペースの上限で閉包を判定し、超えた検証対象をblockedにする"),
    "MULTI-064-02": dict(group="multi", docs="web", related=None, limits={"platform": {"maxDocuments": 1}}, argv=["web::REQ-101"],
                         expect={"web::REQ-101": "pass"}, step=5,
                         description="対照: 起点を所有するワークスペースの上限（既定）で判定し、ルートワークスペースの上限は使わない"),
    "MULTI-064-03": dict(group="multi", docs="cross", related=None, limits={"platform": {"maxDocuments": 2}}, argv=["REQ-001"],
                         expect={"platform::REQ-001": "documents"}, step=5,
                         description="他のワークスペースの文書も閉包の文書数に数え、起点を所有するワークスペースの上限を超えれば、検証対象をblockedにする"),
    "MULTI-064-04": dict(group="multi", docs="cross", related=None, limits={"platform": {"maxDocuments": 3}, "web": {"maxDocuments": 1}}, argv=["REQ-001"],
                         expect={"platform::REQ-001": "pass"}, step=5,
                         description="対照: 閉包が起点を所有するワークスペースの上限ちょうどなら通り、他のワークスペースの上限は使わない"),
    "MULTI-064-05": dict(group="multi", docs="all", related=None, limits={"web": {"maxDocuments": 1}}, argv=["--all-workspaces"],
                         expect={"web::REQ-101": "documents", "api::REQ-201": "pass"}, plain=["api::REQ-201"], step=5,
                         description="複合ワークスペース全体のverifyが、メンバーごとの上限で検証対象を判定し、独立した検証対象は続ける"),
    "MULTI-064-06": dict(group="multi", docs="web", related="ADR-099", limits={"web": {"maxDocuments": 1}}, argv=["web::REQ-101"],
                         expect={"web::REQ-101": "documents"}, step=5,
                         description="複合ワークスペースで上限で止まる検証対象にも、relatedの参照切れの警告を加えない"),
}


def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def config_block(limits):
    return "context:\n" + "".join(f"  {key}: {value}\n" for key, value in limits.items()) if limits else ""


# --- 単一ワークスペースの入力 -------------------------------------------------------------------

REQ_002_HEAD, REQ_002_BODY, TECH_003_TEXT = tcheck.REQ_002_HEAD, tcheck.REQ_002_BODY, tcheck.tech_003_text()
TECH_002_PATH = ".spec/technical/TECH-002.md"
TECH_002_TEXT = "---\nid: TECH-002\ntitle: 別の実装方針\nstatus: approved\nrelations:\n  refines: [TECH-001]\n---\n\n" + tcheck.TECH_002_BODY


def single_inputs(identifier):
    case = CASES[identifier]
    corpus = case["corpus"]
    if corpus == "padded":
        inputs = dict(limit_inputs("SINGLE-048-02"))
    elif corpus == "related":
        inputs = dict(related.reviewed_inputs("SINGLE-168-03"))
    else:
        inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    if corpus == "independent":
        inputs[TECH_002_PATH] = TECH_002_TEXT.encode()
        inputs[".spec/requirements/REQ-002.md"] = (REQ_002_HEAD + "\n" + REQ_002_BODY).encode()
        inputs[".spec/technical/TECH-003.md"] = TECH_003_TEXT.encode()
        inputs[OTHER] = tcheck.TEST_CONTENT
    # 設定は、`SINGLE-042`の設定（コマンド`default`）に`context`ブロックだけを足す（`SINGLE-048-01`・`02`と同じ）。
    inputs[digest_reference.CONFIG_PATH] = (digest_reference.CONFIG + config_block(case["limit"])).encode()
    return inputs


def single_digest_input(identifier, target):
    """参照計算A（単一）。通過する検証対象だけが持つ。既存のレビュー済みの材料に、`context`の設定だけを替える。"""
    case = CASES[identifier]
    if case["corpus"] == "related":
        payload = copy.deepcopy(related.reviewed_digest_input("SINGLE-168-03"))
    elif target == "REQ-002":
        payload = tcheck.single_digest_input("SINGLE-175-07", "REQ-002")
    else:
        payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["context"] = {**DEFAULT_LIMITS, **case["limit"]}
    return payload


# --- 複合ワークスペースの入力 -------------------------------------------------------------------

def multi_documents(identifier):
    case = CASES[identifier]
    ok = lambda path, cover: (path, [cover])
    if case["docs"] == "cross":
        # `MULTI-062-05`と同じ: ルートのREQ-001、それを`refines`するweb::TECH-005、REQ-001:AC-01を直接`refines`するweb::TECH-010。
        return [tcheck.mdoc("platform", "requirement", "REQ-001", "認証の基準", tests=[ok("tests/root.py", "REQ-001:AC-01")]),
                tcheck.mdoc("web", "technical", "TECH-005", "Webの中間の具体化", refines=["platform::REQ-001"]),
                tcheck.mdoc("web", "technical", "TECH-010", "Webの実装方針", refines=["platform::REQ-001:AC-01"],
                            tests=[ok("tests/web.py", "platform::REQ-001:AC-01")])]
    documents = [tcheck.mdoc("web", "requirement", "REQ-101", "Webの基準", tests=[ok("tests/ok.py", "REQ-101:AC-01")]),
                 tcheck.mdoc("web", "technical", "TECH-101", "Webの具体化", refines=["REQ-101"])]
    if case["docs"] == "all":
        documents.append(tcheck.mdoc("api", "requirement", "REQ-201", "APIの基準", tests=[ok("tests/ok.py", "REQ-201:AC-01")]))
    return documents


def doc_text(identifier, document):
    """文書のファイル。`related`を持つ（`MULTI-064-06`）TECH-101だけ、フロントマターの`relations`へ`related`を足す。"""
    text = tcheck.doc_text(document)
    wanted = CASES[identifier].get("related")
    if wanted and document["id"] == "TECH-101":
        text = text.replace(f"refines: [{', '.join(document['refines'])}]\n", f"refines: [{', '.join(document['refines'])}]\n  related: [{wanted}]\n", 1)
    return text


def multi_inputs(identifier):
    case = CASES[identifier]
    limits = case["limits"]
    has_api = case["docs"] == "all"
    root = multi_reference.root_config(MEMBERS) + tcheck.VERIFY_BLOCK + config_block(limits.get("platform"))
    web = multi_reference.member_config("web", "default") + config_block(limits.get("web"))
    api = (multi_reference.member_config("api", "default") if has_api else multi_reference.plain_config("api")) + config_block(limits.get("api"))
    inputs = {".spec/bitz.yaml": root.encode(), "apps/web/.spec/bitz.yaml": web.encode(), "services/api/.spec/bitz.yaml": api.encode()}
    for document in multi_documents(identifier):
        inputs[tcheck.workspace_prefix(document["workspace"]) + tcheck.doc_path(document)] = doc_text(identifier, document).encode()
    files = {"web": ["apps/web/tests/ok.py"], "all": ["apps/web/tests/ok.py", "services/api/tests/ok.py"],
             "cross": ["tests/root.py", "apps/web/tests/web.py"]}[case["docs"]]
    for path in files:
        inputs[path] = tcheck.TEST_CONTENT
    return inputs


def closure_of(identifier, root):
    """リテラルの記述から導く閉包（参照計算A用）。"""
    case = CASES[identifier]
    if case["docs"] == "cross":
        return ["platform::REQ-001", "web::TECH-005", "web::TECH-010"]
    return ["api::REQ-201"] if root == "api::REQ-201" else ["web::REQ-101", "web::TECH-101"]


def multi_digest_input(identifier, root):
    """参照計算A（複合）。閉包の文書をリテラルの記述から材料にし、到達したワークスペースの設定と、使うコマンドだけを収録する。"""
    case = CASES[identifier]
    by_name = {f"{d['workspace']}::{d['id']}": d for d in multi_documents(identifier)}
    materials, edges, reached = [], [], set()
    for name in closure_of(identifier, root):
        document = by_name[name]
        workspace = document["workspace"]
        reached.add(workspace)
        relations = {"refines": [tcheck.qualify(workspace, ref) for ref in document["refines"]]}
        tests = sorted(({"path": path, "covers": sorted(tcheck.qualify(workspace, c) for c in covers), "command": "default"} for path, covers in document["tests"]),
                       key=lambda entry: (entry["path"], entry["covers"]))
        statements = [mverify.statement_material(f"{workspace}::{document['id']}:AC-01", tcheck.REQ_TEXT)] if document["kind"] == "requirement" else []
        material = mverify.document_material(None, name, workspace, document["kind"], document["title"], tcheck.doc_body(document), relations=relations, statements=statements)
        material["frontmatter"]["tests"] = tests
        if case.get("related") and document["id"] == "TECH-101":
            material["frontmatter"]["relations"]["related"] = [case["related"]]
        materials.append(material)
        edges += [{"relation": "refines", "source": name, "target": target} for target in relations["refines"] if target.partition("::")[0] != workspace]
    request = root.partition("::")[0]
    paths = {"platform": ".", "web": "apps/web", "api": "services/api"}
    limits = {**DEFAULT_LIMITS, **case["limits"].get(request, {})}
    commands = [{"workspaceId": ws, "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."} for ws in sorted(reached)]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0", "purpose": "verify",
        "requestWorkspaceId": request, "roots": [root],
        "workspaces": [{"id": name, "path": paths[name]} for name in [request, *sorted(reached - {request})]],
        "documents": sorted(materials, key=lambda item: item["id"]),
        "crossWorkspaceEdges": sorted(edges, key=lambda e: (e["source"], e["relation"], e["target"])),
        "settings": {"workspaces": [{"id": name, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"} for name in sorted(reached)],
                     "context": limits,
                     "verifyTimeouts": [{"workspaceId": ws, "timeoutSeconds": 300} for ws in sorted(reached)], "commands": commands},
    }


# --- 期待結果 ------------------------------------------------------------------------------

def limit_diagnostic(workspace_id, path, kind):
    return {"code": LIMIT_CODE, "severity": "error", "resultStatus": "blocked", "summary": SUMMARY[kind],
            "source": {"kind": "file", "workspaceId": workspace_id, "path": path}}


def blocked_entry(target, workspace_id, path, kind):
    """上限で止まった検証対象: `contextDigest: null`、`statements`と`bindingRefs`は空、診断は`CTX-LIMIT-001`の1件だけ（検証対象の`diagnostics`）。"""
    return {"target": target, "status": "blocked", "contextDigest": None, "statements": [], "bindingRefs": [],
            "diagnostics": [limit_diagnostic(workspace_id, path, kind)]}


def expected_targets(identifier):
    return sorted(CASES[identifier]["expect"])


def digest_of(identifier, target):
    payload = single_digest_input(identifier, target) if directory_of(identifier) == "single" else multi_digest_input(identifier, target)
    return digest_reference.digest(digest_reference.canonical_bytes(payload))


def single_passed_entry(identifier, target):
    if target == "REQ-002":
        return {"target": target, "status": "passed", "contextDigest": digest_of(identifier, target), "statements": ["REQ-002:AC-01"],
                "bindingRefs": ["root::default"], "diagnostics": []}
    warnings = related.reviewed_diagnostics("SINGLE-168-03") if CASES[identifier]["corpus"] == "related" else []
    return {"target": target, "status": "passed_with_warnings" if warnings else "passed", "contextDigest": digest_of(identifier, target),
            "statements": list(related.STATEMENTS), "bindingRefs": ["root::default"], "diagnostics": copy.deepcopy(warnings)}


def single_commands(identifier):
    if "REQ-002" in CASES[identifier]["expect"]:
        return [mverify.command_result("root", "default", "/bin/true", [OTHER], ["REQ-002:AC-01"])]
    if "pass" in CASES[identifier]["expect"].values():
        return copy.deepcopy(related.reviewed_verify_success("SINGLE-168-03")["commands"])
    return []


def reviewed_single_result(identifier):
    case = CASES[identifier]
    entries = []
    for target in expected_targets(identifier):
        kind = case["expect"][target]
        entries.append(single_passed_entry(identifier, target) if kind == "pass" else blocked_entry(target, "root", REQ_PATH, kind))
    status = "blocked" if any(e["status"] == "blocked" for e in entries) else ("passed_with_warnings" if any(e["status"] == "passed_with_warnings" for e in entries) else "passed")
    return {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected", "workspace": {"id": "root", "path": "."},
            "targetResults": entries, "revision": None, "commands": single_commands(identifier), "durationMs": 0, "diagnostics": []}


DOC_PATH = {"web::REQ-101": ("web", ".spec/requirements/REQ-101.md"), "platform::REQ-001": ("platform", ".spec/requirements/REQ-001.md"),
            "api::REQ-201": ("api", ".spec/requirements/REQ-201.md")}
PASSED = {
    "web::REQ-101": dict(statements=["web::REQ-101:AC-01"], bindings=["web::default"], runs={"web": ("tests/ok.py", "web::REQ-101:AC-01")}),
    "api::REQ-201": dict(statements=["api::REQ-201:AC-01"], bindings=["api::default"], runs={"api": ("tests/ok.py", "api::REQ-201:AC-01")}),
    "platform::REQ-001": dict(statements=["platform::REQ-001:AC-01"], bindings=["platform::default", "web::default"],
                              runs={"platform": ("tests/root.py", "platform::REQ-001:AC-01"), "web": ("tests/web.py", "platform::REQ-001:AC-01")}),
}


def multi_entry(identifier, target):
    kind = CASES[identifier]["expect"][target]
    if kind != "pass":
        workspace_id, path = DOC_PATH[target]
        return blocked_entry(target, workspace_id, path, kind)
    info = PASSED[target]
    return {"target": target, "status": "passed", "contextDigest": digest_of(identifier, target), "statements": list(info["statements"]),
            "bindingRefs": list(info["bindings"]), "diagnostics": []}


def multi_commands(identifier):
    commands = []
    for target in expected_targets(identifier):
        if CASES[identifier]["expect"][target] != "pass":
            continue
        for workspace, (path, cover) in PASSED[target]["runs"].items():
            commands.append(mverify.command_result(workspace, "default", "/bin/true", [path], [cover]))
    order = ["platform", "api", "web"]
    return sorted(commands, key=lambda c: order.index(c["workspaceId"]))


def reviewed_multi_result(identifier):
    case = CASES[identifier]
    entries = [multi_entry(identifier, target) for target in expected_targets(identifier)]
    commands = multi_commands(identifier)
    blocked = any(e["status"] == "blocked" for e in entries)
    status = "blocked" if blocked else "passed"
    if "--all-workspaces" in case["argv"]:
        by_workspace = {"platform": [], "api": [], "web": []}
        for entry in entries:
            by_workspace[entry["target"].partition("::")[0]].append(entry)
        workspaces = [mverify.workspace_result("platform", ".", "passed_with_warnings", diagnostics=[
            {**mverify.NO_TARGET, "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"}}])]
        for workspace, path in (("api", "services/api"), ("web", "apps/web")):
            targets = by_workspace[workspace]
            workspace_status = "blocked" if any(t["status"] == "blocked" for t in targets) else "passed"
            workspaces.append(mverify.workspace_result(workspace, path, workspace_status, targets=targets,
                                                       commands=[c for c in commands if c["workspaceId"] == workspace]))
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": status, "multiWorkspace": {"id": "platform", "path": "."},
                "workspaces": workspaces, "revision": {"commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}
    request = expected_targets(identifier)[0].partition("::")[0]
    return {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
            "workspace": {"id": request, "path": {"platform": ".", "web": "apps/web"}[request]},
            "targetResults": entries, "revision": {"commit": COMMIT, "dirty": False}, "commands": commands, "durationMs": 0, "diagnostics": []}


def reviewed_inputs(identifier):
    return single_inputs(identifier) if directory_of(identifier) == "single" else multi_inputs(identifier)


def reviewed_result(identifier):
    return reviewed_single_result(identifier) if directory_of(identifier) == "single" else reviewed_multi_result(identifier)


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if directory_of(identifier) == "single":
        # `verify`は、テスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をステージする（`SINGLE-168-03`、`SINGLE-175`と同じ）。
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    else:
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    status = reviewed_result(identifier)["status"]
    return {"fixtureId": identifier, "description": case["description"], "setup": setup_plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", *case["argv"], "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0}}


# --- 参照計算（入力の木構造から導く） ---------------------------------------------------------

def reference_outcome(documents, workspaces, target, owner_limits):
    """検証対象`target`（修飾ID）の判定: `("documents"|"bytes"|"pass", 閉包の文書数, 標準の提示のバイト数)`。`owner_limits`は判定に使う設定（`context`ブロック）。

    閉包の文書数は`verify_closure`の文書の数、バイト数は閉包の文書の正規化した本文のUTF-8の長さの和（バイト数のケースの閉包は、すべて提示形式`full`の文書だけ。呼び出し側が確かめる）。
    """
    order, _ = binding_missing.verify_closure(documents, target)
    count = len(order)
    size = sum(len(documents[name]["body"].encode("utf-8")) for name in order)
    limits = {**DEFAULT_LIMITS, **{key: int(value) for key, value in owner_limits.items()}}
    if count > limits["maxDocuments"]:
        return "documents", count, size
    if size > limits["maxBytes"]:
        return "bytes", count, size
    return "pass", count, size


def workspace_limits(workspaces, workspace_id):
    return workspaces[workspace_id]["config"].get("context", {})


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる（Coreの出力は根拠にしない）。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = tcheck.load_tree(repository)
    if single != (directory_of(identifier) == "single"):
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    targets = tcheck.result_targets(result)
    if sorted(targets) != expected_targets(identifier):
        raise ValueError("検証対象が期待と異なります")
    for target, entry in targets.items():
        qualified = f"{root_id}::{target}" if single else target
        owner = qualified.partition("::")[0]
        outcome, count, size = reference_outcome(documents, workspaces, qualified, workspace_limits(workspaces, owner))
        if outcome != case["expect"][target]:
            raise ValueError(f"{target}の上限の判定が、入力から導く結果と期待で異なります")
        # 設定を取り違える実装では結果が変わる入力であること（判定する設定の鑑別力）。単純な対照（`plain`）は要求しない。
        # (1) ルートワークスペースと閉包の文書を所有するワークスペースのうち、起点を所有しないもので、上限を明示したもの（取り違えを検出するための邪魔者）は、その設定で判定すると結果が変わる。
        # (2) 上限で止まる検証対象は、既定の上限なら通る（設定が結果を決めている）。
        if target not in case.get("plain", []):
            order, _ = binding_missing.verify_closure(documents, qualified)
            candidates = ({root_id} | {documents[name]["workspaceId"] for name in order}) - {owner}
            for workspace_id in sorted(candidates):
                if workspace_limits(workspaces, workspace_id) and reference_outcome(documents, workspaces, qualified, workspace_limits(workspaces, workspace_id))[0] == outcome:
                    raise ValueError(f"{target}は、起点を所有しないワークスペース{workspace_id}の設定でも同じ結果になり、設定の取り違えを検出できません")
            if outcome != "pass" and reference_outcome(documents, workspaces, qualified, {})[0] != "pass":
                raise ValueError(f"{target}は、既定の上限でも止まり、設定が結果を決めていません")
        if outcome == "bytes" or case.get("bytes_case"):
            order, _ = binding_missing.verify_closure(documents, qualified)
            if len(order) != 2:
                raise ValueError("バイト数のケースの閉包は、起点とそれを直接具体化する文書の2文書である必要があります")
        status = "blocked" if outcome != "pass" else entry["status"]
        if (entry["status"] != status) or (outcome != "pass" and (entry["contextDigest"] is not None or entry["bindingRefs"] or entry["statements"])):
            raise ValueError(f"{target}の状態または証跡が参照計算と異なります")
        if outcome != "pass":
            codes = [d["code"] for d in entry["diagnostics"]]
            if codes != [LIMIT_CODE]:
                raise ValueError("上限で止まる検証対象の診断は、CTX-LIMIT-001の1件だけである必要があります")
            if entry["diagnostics"][0]["summary"] != SUMMARY[outcome]:
                raise ValueError("診断の文言が、超えた上限の種類と異なります")
    # 上限で止まった検証対象のテストは起動しない。通過した検証対象が使う、テスト対応のパスだけを起動する。
    expected_tests = {}
    for target, entry in targets.items():
        if case["expect"][target] != "pass":
            continue
        qualified = f"{root_id}::{target}" if single else target
        _, used = tcheck.used_entries(documents, qualified)
        for name, _index, test in used:
            expected_tests.setdefault("root" if single else documents[name]["workspaceId"], set()).add(test["path"])
    if {c["workspaceId"]: set(c["tests"]) for c in tcheck.result_commands(result)} != expected_tests:
        raise ValueError("起動するテストが参照計算と異なります")
    status = reviewed_result(identifier)["status"]
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    check_related(identifier, repository, result)


def check_related(identifier, repository, result):
    """`related`の参照切れの警告: 入力に実在する参照切れがあり、上限で止まる検証対象にはなく、通過する検証対象には（参照切れがあれば）ある。"""
    case = CASES[identifier]
    if directory_of(identifier) == "single":
        if case["corpus"] != "related":
            return
        documents = digest_crosscheck.load_documents(repository)
        broken = sorted((d["path"], target) for d in documents.values() for target in d["frontmatter"].get("relations", {}).get("related", [])
                        if not digest_crosscheck.resolves(documents, target))
        # TECH-001の`ADR-099`は閉包の中、閉包に入らないTECH-002の`ADR-098`は閉包の外（警告の範囲の対照）。
        if broken != [(".spec/technical/TECH-001.md", "ADR-099"), (".spec/technical/TECH-002.md", "ADR-098")]:
            raise ValueError("`related`の参照切れが、入力と期待で異なります")
        if related.reference_diagnostics(repository, "SINGLE-168-03") != [related.advisory("ADR-099", related.TECH_PATH)]:
            raise ValueError("警告が出るはずの参照切れの参照計算が、期待と異なります")
    else:
        if not case["related"]:
            return
        _, _, _, documents = tcheck.load_tree(repository)
        declared = documents["web::TECH-101"]["frontmatter"]["relations"].get("related", [])
        if declared != [case["related"]] or f"web::{case['related']}" in documents:
            raise ValueError("TECH-101は、存在しない参照先をrelatedする必要があります")
    for target, entry in tcheck.result_targets(result).items():
        has_warning = any(d["code"] == ADVISORY_CODE for d in entry["diagnostics"])
        if entry["status"] == "blocked" and has_warning:
            raise ValueError("上限で止まる検証対象に、relatedの警告を加えてはいけません")
        if entry["status"] != "blocked" and not has_warning:
            raise ValueError("上限の内側の検証対象は、閉包の参照切れのrelatedの警告を返す必要があります")


def check_digest(identifier, repository, result):
    single, root_id, workspaces, documents = tcheck.load_tree(repository)
    for target, entry in tcheck.result_targets(result).items():
        if entry["contextDigest"] is None:
            continue
        if single:
            derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, root=target))
            literal = digest_reference.canonical_bytes(single_digest_input(identifier, target))
        else:
            derived = digest_reference.canonical_bytes(binding_missing.derived_material(repository, documents, workspaces, target))
            literal = digest_reference.canonical_bytes(multi_digest_input(identifier, target))
        if digest_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{target}のハッシュ値が参照計算Bと一致しません")
        if literal != derived:
            raise ValueError(f"{target}のハッシュ値の参照計算AとBが一致しません")


# --- 書き出しと監査 ---------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / directory_of(identifier) / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-verify-closure-limit-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def actual_files(fixture):
    """`repo/`の通常のファイル(パス→バイト列)。シンボリックリンクと実行ビットを拒否する。"""
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
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text())) for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / directory_of(identifier) / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {"verify.json"}:
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            if actual_files(fixture) != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-closure-limit-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
