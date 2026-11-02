"""複合ワークスペースの全体操作が、各ワークスペースの設定の警告を、そのワークスペースの`diagnostics`へ置くことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C22とADR-051の追加に対応する。診断レジストリは、設定の警告の4つの条件（`INPUT-BOM-CONFIG`、`CONFIG-SCHEMA-MINOR-NEWER`、`CONFIG-KEY-PROFILES`、
`CONFIG-KEY-UNKNOWN`）の返しうる操作を`all`、継続単位を`continue`と定める。結果・診断・終了コード §2は、全体事前検査を通過した各ワークスペースの設定の警告を、
`doctor`、`check`、`verify`のどの全体操作でも、そのワークスペースの`workspaces[].diagnostics`へ置き、最上位の`diagnostics`へ複製しないと定める。
修正前のCoreは、`doctor`の全体操作だけがこの警告を返し、`check`と`verify`の全体操作は1件も返さず、状態も`passed`にしていた（単独の操作は返していた）。
この群は、その欠陥と、警告を持つワークスペースが同じワークスペースの別の診断と並ぶときの順序を6件で固定する。

| fixture | 操作と実行ディレクトリ | 入力 | 期待 |
|---|---|---|---|
| `MULTI-053-01` | `check --all-workspaces --base HEAD`、`.` | 4つのワークスペース。`platform`（ルート）は未知のキー`futureOption`、`api`は設定の先頭にBOM、`web`は予約キー`profiles`、`cli`は警告なし | 各警告を所有するワークスペースの`diagnostics`に1件ずつ置き、最上位は空。3つのワークスペースと全体は`passed_with_warnings`／0、`cli`は`passed` |
| `MULTI-053-02` | `verify --all-workspaces`、`.` | `MULTI-053-01`と同じ入力 | `check`と同じ置き場所と状態。どのワークスペースの検証対象も通過し、コマンドも1回ずつ実行する |
| `MULTI-053-03` | `doctor --all-workspaces`、`.` | `MULTI-053-01`と同じ入力 | 対照: `doctor`は同じ警告を同じ置き場所に返す。修正前のCoreも通る |
| `MULTI-053-04` | `check --all-workspaces --base HEAD`、`.` | `web`が設定にBOMと`profiles`を持ち、`.spec/aaa.txt`と`.spec/notes.txt`（未知のファイル）を置く | `web`の`diagnostics`は、`.spec/aaa.txt`、`.spec/bitz.yaml`の`profiles`、同じ`.spec/bitz.yaml`のBOM、`.spec/notes.txt`の順 |
| `MULTI-053-05` | `verify --all-workspaces`、`.` | `web`が設定にBOMと`profiles`を持ち、検証対象を持たない。`platform`は検証対象を持つ | `web`の`diagnostics`は、`profiles`、BOM、`SPEC-VERIFY-BLOCKED-002`の順（発生元が同じ`.spec/bitz.yaml`で、診断コードの辞書順） |
| `MULTI-053-06` | `check --all-workspaces --base HEAD`、`.` | `api`が未知のキーと存在しない参照先、`web`がBOM、`platform`は警告なし | `api`は設定の警告と`SPEC-RELATION-MISSING-001`を並べ`failed`、`web`は`passed_with_warnings`、`platform`は`passed`。全体は`failed`／1 |

基本のリポジトリは、ルートの`.spec/bitz.yaml`と、各ワークスペースの`.spec/bitz.yaml`、`.spec/requirements/REQ-001.md`、`tests/t.py`である。検証対象を持つワークスペースは、
コマンド`t`（`/bin/true`と`{tests}`）を持ち、`REQ-001`の規範文`AC-01`を`tests/t.py`が`covers`する。カタログの宣言の順はワークスペースIDの辞書順にしない。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 診断レジストリ: `INPUT-BOM-CONFIG`（`SPEC-INPUT-BOM-001`）、`CONFIG-KEY-PROFILES`と`CONFIG-KEY-UNKNOWN`（どちらも`SPEC-CONFIG-UNKNOWN-001`）は`warning`／`passed_with_warnings`、
  返しうる操作は`all`、継続単位は`continue`。`WORKSPACE-ENTRY-UNKNOWN`（`SPEC-WORKSPACE-UNKNOWN-001`）は`check`と`doctor`、`VERIFY-MEMBER-TARGETS-EMPTY`
  （`SPEC-VERIFY-BLOCKED-002`）は`verify`（複合ワークスペースの1つのワークスペースの対象が0件のとき`warning`）。`CONFIG-SCHEMA-MINOR-NEWER`は、Coreが未実装（確認事項C93）なので扱わない。
- 結果・診断・終了コード §2: 全体事前検査を通過した各ワークスペースの設定の警告は、どの全体操作でも、そのワークスペースの`diagnostics`へ置く。最上位の`diagnostics`は複製しない。
  §3: `warning`だけならワークスペースと全体は`passed_with_warnings`で、終了コードは0。最悪値の集約は`error > failed > blocked > passed_with_warnings > passed`。
- 結果・診断・終了コード §5: 発生元は`file`で、`path`はワークスペースからの相対パス。設定の警告の`path`は`.spec/bitz.yaml`。
- 結果・診断・終了コード §7: 診断の順序は、発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順。すべて同じ診断は、生成元の宣言に現れた順になる。
  この群は、その最後の規則に頼らないよう、同じワークスペースの診断の並べ替えの鍵がすべて異なる入力だけを使う（鍵の重複は参照計算が拒否する）。
- ワークスペース・設定仕様 §5: 標準のキーは`schemaVersion`、`language`、`earsAi`、`context`、`verify`、`safety`、`workspace`、`multiWorkspace`。`profiles`は予約キーで、それ以外は未知の標準キー。
  安全な入出力・互換性: 既存のBOMは`SPEC-INPUT-BOM-001`の警告とし、BOMを除いて解析を続ける（ハッシュ値の材料もBOMを含まない設定の値で決まる）。
- 診断の文言は、`Coreの出力文言のレビュー記録.md`が承認済みの行（#40、#41、#74の`summary`）と、既存のfixtureが固定する文言（`SINGLE-083`、`MULTI-038-04`、`SINGLE-005-01`）だけを使う。新しい文言を作らない。

`doctor`の`config`の検査項目の状態は、設定の警告を持つワークスペースを`warning`とする（`doctor`仕様 §3の検査5。当初は`SINGLE-093`の慣例で決め、
独立レビューの指摘を受けてユーザーが決定し、規範に明記した）。規範から決まらず、既存の慣例で決めた点は次の1つである
（`複合ワークスペースの設定の警告のレビュー記録.md`に理由を書く）。

1. 警告を持たない`doctor`のワークスペース固有の検査項目は、`MULTI-026-01`と同じ（`impact`だけ`info`）。
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_crosscheck, multi_reference, multi_verify_fixtures as verify_fixtures
from .digest_crosscheck import normalize_body, read_statements, read_yaml, split_document
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
BOM = b"\xef\xbb\xbf"
CONFIG_PATH = ".spec/bitz.yaml"
ROOT_ID = "platform"
TITLE = "認証の基準"
STATEMENT_TEXT = "秘密情報を出力しない"
TEST_PATH = "tests/t.py"
TEST_BYTES = b"def test_login():\n    assert True\n"
COMMAND = "t"
ARGV = ["/bin/true", "{tests}"]
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
# ワークスペース・設定仕様 §5の標準のキー（最上位）。ほかのキーは未知の標準キー、`profiles`は予約キー。
STANDARD_KEYS = ("schemaVersion", "language", "earsAi", "context", "verify", "safety", "workspace", "multiWorkspace")
RESERVED_KEY = "profiles"
# 結果・診断・終了コード §3の最悪値の集約の順（大きいほど悪い）。
SEVERITY_ORDER = ("passed", "passed_with_warnings", "blocked", "failed", "error")
CONFIG_CODES = ("SPEC-INPUT-BOM-001", "SPEC-CONFIG-UNKNOWN-001")

# --- 承認済みの診断の文言（Coreの出力文言のレビュー記録.md #40、#41、#74。既存のfixtureが固定する文言） -----------------
SUMMARY_UNKNOWN_KEY = "未知の設定キーです"
SUMMARY_PROFILES = "設定キーprofilesはCore 1.0では使用しません"
SUMMARY_BOM = "設定ファイル先頭のBOMを除いて解析を続行します"
SUMMARY_UNKNOWN_FILE = ".spec/内の未知のファイルを仕様文書として読みません"
SUMMARY_NO_TARGETS = "検証対象がありません"
SUMMARY_RELATION_MISSING = "強い関係の参照先が存在しません"


# --- 入力の構成 -------------------------------------------------------------------------------
#
# ワークスペース: dict(id, path, extra=最上位の追加のキー（設定の末尾に置く行）, bom=設定の先頭のBOM, requires=REQ-001の`requires`の参照先,
#   documents=REQ-001を置くか, unknown=`.spec/`の直下に置く未知のファイル)。カタログの宣言の順は`members`の並びである。

def _workspace(workspace_id, path, extra=(), bom=False, requires=(), documents=True, unknown=()):
    return dict(id=workspace_id, path=path, extra=list(extra), bom=bom, requires=list(requires), documents=documents, unknown=list(unknown))


INPUTS = {
    # 3種類の警告と、警告のないワークスペース。カタログの宣言の順（web、api、cli）はID辞書順（api、cli、web）ではない。
    "warned": dict(root=_workspace(ROOT_ID, ".", extra=["futureOption: preserve-me"]),
                   members=[_workspace("web", "apps/web", extra=["profiles: legacy-profile"]),
                            _workspace("api", "services/api", bom=True),
                            _workspace("cli", "apps/cli")]),
    # 同じ設定ファイルのBOMと`profiles`が、未知のファイルの診断の間に並ぶ。
    "order-check": dict(root=_workspace(ROOT_ID, "."),
                        members=[_workspace("web", "apps/web", extra=["profiles: legacy-profile"], bom=True,
                                            unknown=["aaa.txt", "notes.txt"])]),
    # `web`は検証対象を持たない。設定の警告と`SPEC-VERIFY-BLOCKED-002`が同じ発生元（`.spec/bitz.yaml`）になる。
    "order-verify": dict(root=_workspace(ROOT_ID, "."),
                         members=[_workspace("web", "apps/web", extra=["profiles: legacy-profile"], bom=True, documents=False)]),
    # 設定の警告と文書の診断（存在しない参照先）が同じワークスペースに並び、そのワークスペースは`failed`になる。
    "failed": dict(root=_workspace(ROOT_ID, "."),
                   members=[_workspace("web", "apps/web", bom=True),
                            _workspace("api", "services/api", extra=["futureOption: preserve-me"], requires=["REQ-999"])]),
}

# id: dict(op, inputs, status, exit, defect, description)。`defect`は、修正前のCoreが期待値と異なる結果を返す（陰性対照が成り立つ）かどうか。
CASES = {
    "MULTI-053-01": dict(op="check", inputs="warned", status="passed_with_warnings", exit=0, defect=True,
                         description="全体のcheckは、各ワークスペースの設定の警告を、所有するワークスペースのdiagnosticsに置く"),
    "MULTI-053-02": dict(op="verify", inputs="warned", status="passed_with_warnings", exit=0, defect=True,
                         description="全体のverifyは、各ワークスペースの設定の警告を、所有するワークスペースのdiagnosticsに置く"),
    "MULTI-053-03": dict(op="doctor", inputs="warned", status="passed_with_warnings", exit=0, defect=False,
                         description="対照: 全体のdoctorは、各ワークスペースの設定の警告を、所有するワークスペースのdiagnosticsに置く。修正の前後で同じ"),
    "MULTI-053-04": dict(op="check", inputs="order-check", status="passed_with_warnings", exit=0, defect=True,
                         description="全体のcheckの設定の警告は、同じワークスペースの未知のファイルの診断と、診断の順序の規則で並ぶ"),
    "MULTI-053-05": dict(op="verify", inputs="order-verify", status="passed_with_warnings", exit=0, defect=True,
                         description="全体のverifyの設定の警告は、同じ発生元の検証対象なしの診断と、診断コードの辞書順で並ぶ"),
    "MULTI-053-06": dict(op="check", inputs="failed", status="failed", exit=1, defect=True,
                         description="全体のcheckの設定の警告は、同じワークスペースのfailedの診断と並び、ほかのワークスペースの警告も欠かさない"),
}
RESULT_FILES = {"check": "expected/check.json", "verify": "expected/verify.json", "doctor": "expected/doctor.json"}

# 診断の条件（リテラル）: 名前→(code, severity, resultStatus, summary, keyを持つか)。
CONDITIONS = {
    "unknown-key": ("SPEC-CONFIG-UNKNOWN-001", "warning", "passed_with_warnings", SUMMARY_UNKNOWN_KEY),
    "profiles": ("SPEC-CONFIG-UNKNOWN-001", "warning", "passed_with_warnings", SUMMARY_PROFILES),
    "bom": ("SPEC-INPUT-BOM-001", "warning", "passed_with_warnings", SUMMARY_BOM),
    "unknown-file": ("SPEC-WORKSPACE-UNKNOWN-001", "warning", "passed_with_warnings", SUMMARY_UNKNOWN_FILE),
    "no-targets": ("SPEC-VERIFY-BLOCKED-002", "warning", "passed_with_warnings", SUMMARY_NO_TARGETS),
    "relation-missing": ("SPEC-RELATION-MISSING-001", "error", "failed", SUMMARY_RELATION_MISSING),
}

# レビュー済みの期待する診断の並び（リテラル）: fixture→ワークスペース→[(条件, パスまたは`None`=設定, key, evidence)]。ワークスペースの結果の並びはルート、ID辞書順。
EXPECTED_DIAGNOSTICS = {
    "MULTI-053-01": {"platform": [("unknown-key", None, "futureOption", None)], "api": [("bom", None, None, None)], "cli": [],
                     "web": [("profiles", None, "profiles", None)]},
    "MULTI-053-02": {"platform": [("unknown-key", None, "futureOption", None)], "api": [("bom", None, None, None)], "cli": [],
                     "web": [("profiles", None, "profiles", None)]},
    "MULTI-053-03": {"platform": [("unknown-key", None, "futureOption", None)], "api": [("bom", None, None, None)], "cli": [],
                     "web": [("profiles", None, "profiles", None)]},
    "MULTI-053-04": {"platform": [],
                     "web": [("unknown-file", ".spec/aaa.txt", None, None), ("profiles", None, "profiles", None), ("bom", None, None, None),
                             ("unknown-file", ".spec/notes.txt", None, None)]},
    "MULTI-053-05": {"platform": [],
                     "web": [("profiles", None, "profiles", None), ("bom", None, None, None), ("no-targets", None, None, None)]},
    "MULTI-053-06": {"platform": [], "api": [("unknown-key", None, "futureOption", None), ("relation-missing", ".spec/requirements/REQ-001.md", "relations.requires", "REQ-999")],
                     "web": [("bom", None, None, None)]},
}


def workspace_specs(inputs):
    """ルートを先頭に、以降をカタログの宣言の順に並べたワークスペース。"""
    return [INPUTS[inputs]["root"], *INPUTS[inputs]["members"]]


def result_order(inputs):
    """結果と材料のワークスペースの並び: ルートを先頭、その後をIDの辞書順（複合ワークスペース仕様 §8）。"""
    root, members = INPUTS[inputs]["root"], INPUTS[inputs]["members"]
    return [root, *sorted(members, key=lambda item: item["id"])]


def inputs_of(identifier):
    return CASES[identifier]["inputs"]


# --- 入力の書き出し ---------------------------------------------------------------------------

def config_text(spec, members):
    """ワークスペースの設定。`members`はルートだけが持つカタログの宣言（ID、パス）。追加のキーは設定の末尾に置く。"""
    lines = ['schemaVersion: "1.0"\n', "language: ja\n", 'earsAi: "1.0"\n', "workspace:\n", f"  id: {spec['id']}\n"]
    if members is not None:
        lines += ["multiWorkspace:\n", "  members:\n"]
        for member in members:
            lines += [f"    - id: {member['id']}\n", f"      path: {member['path']}\n"]
    if spec["documents"]:
        lines += ["verify:\n", "  commands:\n", f"    {COMMAND}:\n", f"      argv: [{', '.join(json.dumps(part) for part in ARGV)}]\n", "      cwd: .\n"]
    lines += [f"{line}\n" for line in spec["extra"]]
    return "".join(lines)


def requirement_text(spec):
    """`REQ-001`の(ファイルの全文, 正規化する前の本文)。規範文は`AC-01`の1件、テスト対応は`tests/t.py`の1件。`requires`は任意。"""
    head = f"---\nid: REQ-001\ntitle: {TITLE}\nstatus: approved\n"
    if spec["requires"]:
        head += f"relations:\n  requires: [{', '.join(spec['requires'])}]\n"
    head += f"tests:\n  - path: {TEST_PATH}\n    covers: [REQ-001:AC-01]\n    command: {COMMAND}\n"
    body = (f"# REQ-001 {TITLE}\n\n## Intent\n\n{TITLE}の規範を定める。\n\n## Acceptance Criteria\n\n"
            f"- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {STATEMENT_TEXT}。\n\n## Verification\n\nそれぞれのtestで確認する。\n")
    return head + "---\n\n" + body, body


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    inputs = INPUTS[inputs_of(identifier)]
    files = {}
    for spec in workspace_specs(inputs_of(identifier)):
        base = "" if spec["path"] == "." else spec["path"] + "/"
        text = config_text(spec, inputs["members"] if spec is inputs["root"] else None).encode()
        files[f"{base}{CONFIG_PATH}"] = (BOM if spec["bom"] else b"") + text
        if spec["documents"]:
            files[f"{base}.spec/requirements/REQ-001.md"] = requirement_text(spec)[0].encode()
            files[f"{base}{TEST_PATH}"] = TEST_BYTES
        for name in spec["unknown"]:
            files[f"{base}.spec/{name}"] = b"memo\n"
    return files


def reviewed_manifest(identifier):
    case = CASES[identifier]
    argv = {"check": ["check", "--all-workspaces", "--base", "HEAD"], "verify": ["verify", "--all-workspaces"], "doctor": ["doctor", "--all-workspaces"]}[case["op"]]
    return {
        "fixtureId": identifier, "description": case["description"],
        # `verify`はテスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をコミットする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*argv, "--format", "json"], "env": {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json", "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果（リテラル） -------------------------------------------------------------

def diagnostic(workspace_id, condition, path, key, evidence):
    code, severity, status, summary = CONDITIONS[condition]
    source = {"kind": "file", "workspaceId": workspace_id, "path": path or CONFIG_PATH}
    if key is not None:
        source["key"] = key
    entry = {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": source}
    if evidence is not None:
        entry["evidence"] = evidence
    return entry


def worst(statuses):
    return max(statuses, key=SEVERITY_ORDER.index, default="passed")


def workspace_diagnostics(identifier, workspace_id):
    return [diagnostic(workspace_id, *item) for item in EXPECTED_DIAGNOSTICS[identifier][workspace_id]]


def digest_input(spec):
    """検証対象`<ID>::REQ-001`の目的`verify`のハッシュ値の材料（参照計算A）。閉包はその文書1件で、ほかのワークスペースへ到達しない。"""
    name = f"{spec['id']}::REQ-001"
    text, body = requirement_text(spec)
    document = verify_fixtures.document_material(
        None, name, spec["id"], "requirement", TITLE, body,
        statements=[verify_fixtures.statement_material(f"{name}:AC-01", STATEMENT_TEXT)])
    document["frontmatter"]["tests"] = [{"path": TEST_PATH, "covers": [f"{name}:AC-01"], "command": COMMAND}]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": spec["id"], "roots": [name],
        "workspaces": [{"id": spec["id"], "path": spec["path"]}],
        "documents": [document], "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": spec["id"], "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": spec["id"], "timeoutSeconds": 300}],
            "commands": [{"workspaceId": spec["id"], "name": COMMAND, "argv": list(ARGV), "cwd": "."}],
        },
    }


def expected_digest(spec):
    return multi_reference.digest(multi_reference.canonical_bytes(digest_input(spec)))


def check_workspace(identifier, spec):
    diagnostics = workspace_diagnostics(identifier, spec["id"])
    return {"id": spec["id"], "path": spec["path"], "status": worst(item["resultStatus"] for item in diagnostics),
            "checkedDocumentCount": 1 if spec["documents"] else 0, "checkedStatementCount": 1 if spec["documents"] else 0,
            "durationMs": 0, "diagnostics": diagnostics}


def command_entry(spec):
    name = spec["id"]
    return {"bindingId": f"{name}::{COMMAND}", "workspaceId": name, "name": COMMAND, "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", TEST_PATH], "tests": [TEST_PATH], "covers": [f"{name}::REQ-001:AC-01"], "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def verify_workspace(identifier, spec):
    diagnostics = workspace_diagnostics(identifier, spec["id"])
    targets, commands = [], []
    if spec["documents"]:
        name = f"{spec['id']}::REQ-001"
        targets = [{"target": name, "status": "passed", "contextDigest": expected_digest(spec), "statements": [f"{name}:AC-01"],
                    "bindingRefs": [f"{spec['id']}::{COMMAND}"], "diagnostics": []}]
        commands = [command_entry(spec)]
    status = worst([item["resultStatus"] for item in diagnostics] + [item["status"] for item in targets] + [item["status"] for item in commands])
    return {"id": spec["id"], "path": spec["path"], "status": status, "targetResults": targets, "commands": commands, "durationMs": 0, "diagnostics": diagnostics}


def doctor_workspace(identifier, spec):
    diagnostics = workspace_diagnostics(identifier, spec["id"])
    warned = any(item["code"] in CONFIG_CODES for item in diagnostics)
    checks = [{"name": "workspace", "status": "passed"}, {"name": "config", "status": "warning" if warned else "passed"},
              {"name": "schema", "status": "passed"}, {"name": "ears", "status": "passed"}, {"name": "command", "status": "passed"},
              {"name": "impact", "status": "info"}]
    return {"id": spec["id"], "path": spec["path"], "status": worst(item["resultStatus"] for item in diagnostics), "checks": checks,
            "durationMs": 0, "diagnostics": diagnostics}


def reviewed_result(identifier):
    case = CASES[identifier]
    order = result_order(case["inputs"])
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    if case["op"] == "doctor":
        entries = [doctor_workspace(identifier, spec) for spec in order]
        return {"schemaVersion": "1.0", "operation": "doctor", "status": worst(entry["status"] for entry in entries),
                "multiWorkspace": {"id": ROOT_ID, "path": "."}, "core": json.loads(json.dumps(CORE)),
                "checks": [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"}, {"name": "catalog", "status": "passed"}],
                "workspaces": entries, "durationMs": 0, "diagnostics": []}
    build = check_workspace if case["op"] == "check" else verify_workspace
    entries = [build(identifier, spec) for spec in order]
    return {"schemaVersion": "1.0", "operation": case["op"], "scope": "all-workspaces", "status": worst(entry["status"] for entry in entries),
            "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": entries,
            "revision": revision if case["op"] == "check" else {"commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}


def reviewed_effects(state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def old_core_result(result):
    """修正前のCoreの`check`と`verify`の全体操作の再現: 設定の警告の4つの条件の診断を返さない（欠陥の再現。期待値の根拠にしない）。"""
    old = json.loads(json.dumps(result))
    for entry in old["workspaces"]:
        entry["diagnostics"] = [item for item in entry["diagnostics"] if item["code"] not in CONFIG_CODES]
        entry["status"] = worst([item["resultStatus"] for item in entry["diagnostics"]] + [item["status"] for item in entry.get("targetResults", [])]
                                + [item["status"] for item in entry.get("commands", [])])
    old["status"] = worst(entry["status"] for entry in old["workspaces"])
    return old


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def load_tree(repository):
    """カタログの宣言の順のワークスペース: dict(id, path, raw=設定のバイト列, config=BOMを除いた設定の値, unknown=`.spec/`直下の未知のファイル, documents=REQの索引)。"""
    raw_root = (repository / CONFIG_PATH).read_bytes()
    root_config = read_yaml(raw_root.removeprefix(BOM).decode("utf-8"))
    declared = [(root_config["workspace"]["id"], ".")] + [(entry["id"], entry["path"]) for entry in root_config["multiWorkspace"]["members"]]
    loaded = []
    for workspace_id, path in declared:
        root = repository if path == "." else repository / path
        raw = (root / CONFIG_PATH).read_bytes()
        config = read_yaml(raw.removeprefix(BOM).decode("utf-8"))
        if config["workspace"]["id"] != workspace_id:
            raise ValueError("カタログのIDとワークスペースの設定のIDが一致しません")
        unknown = sorted(entry.name for entry in (root / ".spec").iterdir()
                         if entry.is_file() and entry.name != "bitz.yaml")
        documents = {}
        folder = root / ".spec/requirements"
        for file in sorted(folder.glob("*.md")) if folder.is_dir() else []:
            frontmatter, body = split_document(file.read_text(encoding="utf-8"))
            documents[frontmatter["id"]] = {"frontmatter": frontmatter, "body": normalize_body(body), "path": file.relative_to(root).as_posix()}
        loaded.append({"id": workspace_id, "path": path, "raw": raw, "config": config, "unknown": unknown, "documents": documents})
    return loaded


def sort_key(item):
    """結果・診断・終了コード §7の並べ替えの鍵。この群の診断は`line`と`column`を持たず、`specRefs`も持たない。"""
    source = item["source"]
    if any(name in source for name in ("line", "column")) or "specRefs" in item or source["kind"] != "file":
        raise ValueError("この群の診断は`line`、`column`、`specRefs`を持たない`file`の発生元だけです")
    return (source["workspaceId"], source["path"], item["code"])


def reference_diagnostics(operation, workspace):
    """参照計算: ワークスペースの設定、`.spec/`直下のファイル、文書から、そのワークスペースの`diagnostics`を導く（結果・診断・終了コード §7の順）。"""
    workspace_id = workspace["id"]

    def entry(condition, path=None, key=None, evidence=None):
        return diagnostic(workspace_id, condition, path, key, evidence)

    found = []
    # 設定の警告（診断レジストリ: 返しうる操作は`all`）。
    if workspace["raw"].startswith(BOM):
        found.append(entry("bom"))
    for key in workspace["config"]:
        if key == RESERVED_KEY:
            found.append(entry("profiles", key=key))
        elif key not in STANDARD_KEYS:
            found.append(entry("unknown-key", key=key))
    # 未知のファイル（診断レジストリ: `check`と`doctor`）。
    if operation in ("check", "doctor"):
        found += [entry("unknown-file", path=f".spec/{name}") for name in workspace["unknown"]]
    # 強い関係の参照先の不在（`check`）。参照先はワークスペースの内のローカルID。
    if operation == "check":
        for document in workspace["documents"].values():
            for target in document["frontmatter"].get("relations", {}).get("requires", []):
                if target not in workspace["documents"]:
                    found.append(entry("relation-missing", path=document["path"], key="relations.requires", evidence=target))
    # 検証対象が0件のワークスペース（診断レジストリ: `verify`、複合ワークスペースの1つのワークスペースでは`warning`）。
    if operation == "verify" and not reference_targets(workspace):
        found.append(entry("no-targets"))
    keys = [sort_key(item) for item in found]
    if len(set(keys)) != len(keys):
        raise ValueError("同じワークスペースの診断の並べ替えの鍵が重複しています（宣言の順に頼る入力は使いません）")
    return sorted(found, key=sort_key)


def reference_targets(workspace):
    """`approved`のREQで、`MUST`の規範文を持つ文書（`verify` §2・§7）。規範文ごとにテスト対応を要求する。"""
    targets = []
    for local, document in workspace["documents"].items():
        statements = [item for item in read_statements(document["body"]) if item["modality"] == "MUST"]
        if document["frontmatter"]["status"] == "approved" and statements:
            targets.append(local)
    return sorted(targets)


def reference_result_statuses(operation, loaded):
    """ワークスペースごとの`diagnostics`と状態、全体の状態を導く。"""
    entries = {}
    for workspace in loaded:
        diagnostics = reference_diagnostics(operation, workspace)
        entries[workspace["id"]] = (diagnostics, worst(item["resultStatus"] for item in diagnostics))
    return entries, worst(status for _, status in entries.values())


def stripped_copy(repository, destination):
    """設定のBOMを除いた複製（参照計算B）。既存のBOMは除いて解析を続けるので、ハッシュ値の材料はBOMを含まない設定の値で決まる。"""
    shutil.copytree(repository, destination, ignore=shutil.ignore_patterns(".git"))
    for path in destination.rglob("bitz.yaml"):
        path.write_bytes(path.read_bytes().removeprefix(BOM))
    return destination


# --- 検査 -------------------------------------------------------------------------------------

def check_conditions(identifier, repository, manifest, result):
    """原因の構成と期待結果を、散文ではなく準備手順の後の入力と参照計算から確かめる。"""
    case = CASES[identifier]
    operation = case["op"]
    if not (repository / ".git").exists() or git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("Gitのリポジトリで、作業ツリーがコミット済みと同じである必要があります")
    loaded = load_tree(repository)
    if [item["id"] for item in loaded] != [spec["id"] for spec in workspace_specs(case["inputs"])]:
        raise ValueError("カタログの宣言の順がレビュー済みの入力と異なります")
    if [item["id"] for item in loaded[1:]] == sorted(item["id"] for item in loaded[1:]) and len(loaded) > 2:
        raise ValueError("カタログの宣言の順がID辞書順です（結果の並びの規則を区別できません）")
    # 設定の警告の原因は、入力のバイト列とキーの有無で成り立つ。
    for workspace, spec in zip(loaded, workspace_specs(case["inputs"])):
        if workspace["raw"].startswith(BOM) != spec["bom"]:
            raise ValueError("設定の先頭のBOMがレビュー済みの入力と異なります")
        if workspace["raw"][len(BOM):].startswith(BOM):
            raise ValueError("BOMは1つだけです")
    entries, overall = reference_result_statuses(operation, loaded)
    # 結果のワークスペースの並び（ルートを先頭、その後をID辞書順）と、状態の集約。
    by_id = {entry["id"]: entry for entry in result["workspaces"]}
    if [entry["id"] for entry in result["workspaces"]] != [loaded[0]["id"], *sorted(item["id"] for item in loaded[1:])] or set(by_id) != {item["id"] for item in loaded}:
        raise ValueError("ワークスペースの結果の並びがルート先頭、ID辞書順ではありません")
    for workspace_id, (diagnostics, status) in entries.items():
        entry = by_id[workspace_id]
        if entry["diagnostics"] != diagnostics:
            raise ValueError(f"{workspace_id}の診断が入力からの参照計算と異なります")
        if entry["status"] != status:
            raise ValueError(f"{workspace_id}の状態が診断からの参照計算と異なります")
    # 設定の警告は、最上位へ複製しない（結果・診断・終了コード §2）。最上位の診断は空で、同じ診断は結果の木構造に1件ずつだけ現れる。
    if result["diagnostics"]:
        raise ValueError("最上位の診断は空である必要があります")
    seen = [json.dumps(item, ensure_ascii=False, sort_keys=True) for entry in result["workspaces"] for item in entry["diagnostics"]]
    if len(seen) != len(set(seen)):
        raise ValueError("同じ診断が重複しています")
    if result["status"] != overall or (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (overall, {"passed": 0, "passed_with_warnings": 0, "failed": 1}[overall]):
        raise ValueError("全体の状態または終了コードが診断からの参照計算と異なります")
    # 警告だけのワークスペースと警告のないワークスペースを区別する（`warned`の`cli`は`passed`）。
    if case["inputs"] == "warned" and by_id["cli"]["status"] != "passed":
        raise ValueError("警告のないワークスペースは`passed`である必要があります")
    # 修正前のCoreの結果と異なる（欠陥を検出できる）か、対照として同じである。
    if operation in ("check", "verify"):
        if (old_core_result(result) != result) != case["defect"]:
            raise ValueError("修正前のCoreの結果との関係がfixtureの名乗る種類と異なります")
    elif case["defect"]:
        raise ValueError("`doctor`は修正前から設定の警告を返すので、欠陥を名乗れません")
    if operation == "verify":
        check_verify_reference(repository, loaded, result)
    if operation == "doctor":
        for entry in result["workspaces"]:
            warned = any(item["code"] in CONFIG_CODES for item in entry["diagnostics"])
            if [item["name"] for item in entry["checks"]] != ["workspace", "config", "schema", "ears", "command", "impact"] \
                    or {item["name"]: item["status"] for item in entry["checks"]}["config"] != ("warning" if warned else "passed"):
                raise ValueError("`doctor`の検査項目が設定の警告からの参照計算と異なります")


def check_verify_reference(repository, loaded, result):
    """`verify`の検証対象、規範文、テスト割当てを入力から導く。コマンドは所有ワークスペースの`commands[]`に1件だけ置く。"""
    by_id = {entry["id"]: entry for entry in result["workspaces"]}
    if not any(reference_targets(workspace) for workspace in loaded):
        raise ValueError("複合ワークスペース全体の検証対象が0件になります")
    for workspace in loaded:
        entry = by_id[workspace["id"]]
        targets = [f"{workspace['id']}::{local}" for local in reference_targets(workspace)]
        if [item["target"] for item in entry["targetResults"]] != targets:
            raise ValueError(f"{workspace['id']}の検証対象が入力からの参照計算と異なります")
        for item in entry["targetResults"]:
            local = item["target"].partition("::")[2]
            statements = [f"{item['target']}:{statement['id'].partition(':')[2]}" for statement in read_statements(workspace["documents"][local]["body"])]
            tests = workspace["documents"][local]["frontmatter"]["tests"]
            if item["statements"] != statements or item["bindingRefs"] != [f"{workspace['id']}::{entry_['command']}" for entry_ in tests] or item["status"] != "passed":
                raise ValueError(f"{item['target']}の規範文またはテスト割当てが入力からの参照計算と異なります")
        if [item["bindingId"] for item in entry["commands"]] != [f"{workspace['id']}::{COMMAND}" for _ in targets[:1]]:
            raise ValueError(f"{workspace['id']}のコマンドが入力からの参照計算と異なります")
    # ハッシュ値は、リテラルのA（`digest_input`）と、BOMを除いた入力の木構造から導くB（`multi_crosscheck`）のバイト列の一致を要求する。
    with tempfile.TemporaryDirectory(prefix="bitz-multi-config-warning-") as temporary:
        stripped = stripped_copy(repository, Path(temporary) / "repo")
        loaded_b = multi_crosscheck.load_workspaces(stripped)
        for entry in result["workspaces"]:
            for item in entry["targetResults"]:
                derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(stripped, item["target"], loaded=loaded_b))
                spec = next(spec for spec in workspace_specs_of(result) if spec["id"] == entry["id"])
                if multi_crosscheck.digest(derived) != item["contextDigest"]:
                    raise ValueError(f"{item['target']}のハッシュ値が参照計算Bと一致しません")
                if multi_reference.canonical_bytes(digest_input(spec)) != derived:
                    raise ValueError(f"{item['target']}のハッシュ値の参照計算AとBが一致しません")


def workspace_specs_of(result):
    """結果に現れたワークスペースの構成（ID→構成）。ハッシュ値の参照計算Aが使う。"""
    known = {spec["id"]: spec for inputs in INPUTS.values() for spec in [inputs["root"], *inputs["members"]]}
    return [known[entry["id"]] for entry in result["workspaces"]]


# --- 書き出しと監査 ---------------------------------------------------------------------------

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
        with tempfile.TemporaryDirectory(prefix="bitz-multi-config-warning-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(state)))


def actual_entries(fixture):
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
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[CASES[identifier]["op"]]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            if actual_entries(fixture) != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {RESULT_FILES[CASES[identifier]["op"]]}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-config-warning-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
