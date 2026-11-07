"""`verify`が、その検証対象が使うテスト対応のテストのパスと`covers`を検査することを固定する（Coreの公開操作は実行しない）。

実装の確認事項N2・C92と、PR-cの独立レビューのM1、ADR-051の追加に対応する。ユーザーの決定により、規範は次のとおりに明記された（`bitz verify`仕様 §4の4.と§9）。

- 検査の対象は、その検証対象が使うテスト対応（対象規範文を`covers`するテスト対応。規範文のないTECHは文書単位の`tests`）だけである。
- テストのパスの存在と所有境界は`check`と同じ規則（関係・トレースモデル §9、ワークスペース・設定仕様 §9、複合ワークスペース仕様 §5.1）、
  `covers`の妥当性は文書・フロントマター・状態仕様のテスト対応の規則（(a)自身の規範文、(b)規範文を持たない文書は自身のID、(c)直接`refines`する文書の規範文または
  直接`refines`する規範文。複合ワークスペースの横断は、宣言する文書が直接`refines`する場合だけ）で判定する。
- 違反は`check`と同じ診断（不在・不正は`SPEC-PATH-INVALID-001`、複合ワークスペースで所有領域の外は`SPEC-MULTI-OWNERSHIP-001`、`covers`は`SPEC-TEST-COVERAGE-001`。
  文言と発生元は同じ）を検証対象の`diagnostics`へ返す。その検証対象は`failed`、`bindingRefs: []`で、テストを起動しない（`skip-target`）。独立した検証対象は続ける。
  コンテキストは完成しているので`contextDigest`と`statements`は値を持つ。
- 検証対象が使わないテスト対応と`implements`は検査しない（`check`の責務）。

修正前のCoreは、この検査をせず、存在しないパスやディレクトリのテスト、所有領域の外のテスト、不正な`covers`のテストを起動して`passed`にした。
次の「診断の文言」は、承認済みの文言だけを使う。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-175-01` | `verify REQ-001` | TECH-001の`tests[2].path`が存在しない`tests/nope.py`（`AC-01`を`covers`。ほかの2件は正しい） | `failed`／1。`REQ-001`は`failed`、`SPEC-PATH-INVALID-001`、キー`tests[2].path`。`bindingRefs`と`commands`は空 |
| `SINGLE-175-02` | 同上 | `tests[2].path`がディレクトリ`tests/suite` | 同上 |
| `SINGLE-175-03` | 同上 | `tests[2].path`が`ext/env`。`ext -> /usr/bin`（リポジトリの外） | 同上 |
| `SINGLE-175-04` | 同上 | TECH-002が`TECH-001`だけを`refines`し、`REQ-001:AC-02`を`covers`する（推移的） | `failed`／1。`SPEC-TEST-COVERAGE-001`（TECH-002、キー`tests[0].covers`、証拠`REQ-001:AC-02`） |
| `SINGLE-175-05` | `verify TECH-001` | 規範文のないTECH-001の文書単位の`tests[2].path`が存在しない | `failed`／1。`SPEC-PATH-INVALID-001`、キー`tests[2].path`。`statements`は空 |
| `SINGLE-175-06` | `verify REQ-001 REQ-002` | `SINGLE-175-01`の入力に、独立したREQ-002とTECH-003（正しいテスト）を足す | `failed`／1。`REQ-001`は`failed`、`REQ-002`は`passed`でテストを起動する。`REQ-001`の正しいテストは起動しない |
| `SINGLE-175-07` | `verify REQ-002` | `SINGLE-175-06`と同じ入力 | `passed`／0。対照: `REQ-001`の不在のパスは、使わないので検査しない |
| `SINGLE-175-08` | `verify REQ-001` | TECH-001の`implements`が存在しない`src/gone.py`。テスト対応は正しい | `passed`／0。対照: `implements`は検査しない |
| `MULTI-062-01` | `verify web::REQ-101` | `web`のREQ-101の`tests[1].path`が`ext/test_x.py`。`apps/web/ext -> ../../tests`（ルートの領域） | `failed`／1。`SPEC-MULTI-OWNERSHIP-001`（`web`、キー`tests[1].path`） |
| `MULTI-062-02` | 同上 | `tests[1].path`が存在しない`tests/nope.py` | `failed`／1。`SPEC-PATH-INVALID-001`（`web`） |
| `MULTI-062-03` | `verify REQ-001` | ルートのREQ-001の`tests[1].path`が`apps/web/t.py`（字句でメンバーの配下） | `failed`／1。`SPEC-MULTI-OWNERSHIP-001`（`platform`） |
| `MULTI-062-04` | `verify REQ-001` | `web::TECH-010`が`web::TECH-005`だけを`refines`し、`platform::REQ-001:AC-01`を`covers`する（横断で直接`refines`なし） | `failed`／1。`SPEC-TEST-COVERAGE-001`（`web`、証拠`platform::REQ-001:AC-01`） |
| `MULTI-062-05` | 同上 | 対照: `web::TECH-010`が`platform::REQ-001:AC-01`を直接`refines`する | `passed`／0。`platform::default`と`web::default`を起動する |
| `MULTI-062-06` | `verify --all-workspaces` | `web`のREQ-101は`tests[1].path`が不在、`api`のREQ-201は正しい | `failed`／1。`web::REQ-101`は`failed`、`api::REQ-201`は`passed`で起動する |
| `MULTI-062-07` | `verify REQ-001` | `MULTI-062-05`の入力に、使わない`web`のREQ-102（不在のパス）を足す | `passed`／0。対照: 使わないテスト対応は検査しない |

fixtureは、1つの原因だけを持つ。違反するエントリは、ほかの正しいエントリと同じ規範文を`covers`する（正しいエントリが規範文を数えるので、違反したエントリをカバレッジに数えるかどうかに依存しない）。
`SINGLE-175-04`の入力は、TECH-001とTECH-002の正しいテストだけで全規範文が`covers`される。

期待値は規範と承認済みの文言から導く参照計算（`reference_target`）で、Coreの出力は根拠にしない。`reference_target`は、入力の木構造から、閉包、対象規範文、
使うテスト対応、テストのパスの扱い（`os.path.realpath`で求めた実パスのセグメントの境界の包含。Coreの`os.path.samestat`とは別）、`covers`の妥当性（(a)〜(c)）を導き、診断の`code`、`summary`、
`source`、`evidence`を組み立てて、期待結果の診断と一致することを要求する。

規範から決まらず、既存の形で決めた点:
- 違反した検証対象の`contextDigest`と`statements`は、コンテキストが完成するので値を持つ（`CTX-COVERAGE-TEST-001`、`VERIFY-BINDING-MISSING`と同じ。`verify` §8は`contextDigest`が`null`になるのを
  コンテキストを構成できない場合だけとする）。
- 違反した検証対象が使う、ほかの正しいテスト対応のテストも起動しない（`SINGLE-175-06`の`tests/test_auth.py`）。`skip-target`で、検証対象を丸ごと実行計画へ入れない。
- `SPEC-PATH-INVALID-001`と`SPEC-MULTI-OWNERSHIP-001`の`key`は`tests[i].path`、`SPEC-TEST-COVERAGE-001`は`tests[i].covers`（`check`と同じ。`SINGLE-026`、`MULTI-008`）。
- リポジトリの外のディレクトリは、fixtureが書けないので、ホストの`/usr/bin`を指す絶対パスのシンボリックリンクで置く（`SINGLE-175-03`だけ。`real_path_ownership_fixtures`と同じ）。
- Stepの割当ては、同じ操作・同じ診断の既存のfixtureに合わせた（単一の`verify`はStep 4、複合はStep 5）。
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
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXTERNAL_DIRECTORY = "/usr/bin"
EXTERNAL_FILE = "env"
TEST_CONTENT = b"def test_ok():\n    assert True\n"
PATH_SUMMARY = "テストのパスが存在しません"
COVERS_SUMMARY = "フィールドcoversの参照先が存在しないか、対応できません"
EXIT = {"passed": 0, "failed": 1, "blocked": 2}
MEMBERS = (("web", "apps/web"), ("api", "services/api"))
VERIFY_BLOCK = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
TECH_001_PATH = ".spec/technical/TECH-001.md"
TECH_002_PATH = ".spec/technical/TECH-002.md"
AUTH, SESSION, OTHER, NOPE = "tests/test_auth.py", "tests/test_session.py", "tests/test_other.py", "tests/nope.py"
BASE_TESTS = [(AUTH, "REQ-001:AC-01"), (SESSION, "REQ-001:AC-02")]
STATEMENTS = {"REQ-001": ["REQ-001:AC-01", "REQ-001:AC-02"], "REQ-002": ["REQ-002:AC-01"], "TECH-001": []}

# --- ケース -------------------------------------------------------------------------------
# 単一ワークスペース（group=single）: argv〈`verify`の引数〉、tech1〈TECH-001の`tests`の宣言順（パス, covers）〉、tech2〈TECH-002（`TECH-001`を`refines`）の`tests`〉、
#   second〈独立したREQ-002とTECH-003（正しいテスト）を置くか〉、files〈実ファイル〉、link〈(置き場, 向き先)〉、implements〈TECH-001の`implements`〉、
#   expect〈検証対象→違反（kind: path|covers, doc, index, evidence）、通過は`None`〉、runs〈通過する検証対象→起動するテスト対応（パス, covers）〉
# 複合ワークスペース（group=multi）: argv、expect〈検証対象→違反（kind: path|ownership|covers, workspace, doc, index, path, evidence）または`None`〉、
#   runs〈通過する検証対象→[(ワークスペース, テストのパス, covers)]〉、files〈実ファイル〉、link〈(置き場, 向き先)〉
# 共通: defective〈修正前のCoreが違う結果を返すか〉、step、description
CASES = {
    "SINGLE-175-01": dict(group="single", argv=["REQ-001"], tech1=BASE_TESTS + [(NOPE, "REQ-001:AC-01")], tech2=None, second=False,
                          files=[AUTH, SESSION], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-001": dict(kind="path", doc=TECH_001_PATH, index=2, evidence=None)}, runs={}, defective=True, step=4,
                          description="使うテスト対応のテストのパスが存在しないとき、検証対象をfailedにし、テストを起動しない"),
    "SINGLE-175-02": dict(group="single", argv=["REQ-001"], tech1=BASE_TESTS + [("tests/suite", "REQ-001:AC-01")], tech2=None, second=False,
                          files=[AUTH, SESSION, "tests/suite/test_inner.py"], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-001": dict(kind="path", doc=TECH_001_PATH, index=2, evidence=None)}, runs={}, defective=True, step=4,
                          description="使うテスト対応のテストのパスがディレクトリのとき、検証対象をfailedにし、テストを起動しない"),
    "SINGLE-175-03": dict(group="single", argv=["REQ-001"], tech1=BASE_TESTS + [("ext/env", "REQ-001:AC-01")], tech2=None, second=False,
                          files=[AUTH, SESSION], link=("ext", EXTERNAL_DIRECTORY), implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-001": dict(kind="path", doc=TECH_001_PATH, index=2, evidence=None)}, runs={}, defective=True, step=4,
                          description="使うテスト対応のテストのパスの上位のディレクトリがリポジトリの外へ解決するシンボリックリンクなら、検証対象をfailedにする"),
    "SINGLE-175-04": dict(group="single", argv=["REQ-001"], tech1=BASE_TESTS, tech2=[(OTHER, "REQ-001:AC-02")], second=False,
                          files=[AUTH, SESSION, OTHER], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-001": dict(kind="covers", doc=TECH_002_PATH, index=0, evidence="REQ-001:AC-02")}, runs={}, defective=True, step=4,
                          description="使うテスト対応のcoversが推移的なrefinesの規範文を指すとき、検証対象をfailedにし、テストを起動しない"),
    "SINGLE-175-05": dict(group="single", argv=["TECH-001"], tech1=BASE_TESTS + [(NOPE, "REQ-001:AC-01")], tech2=None, second=False,
                          files=[AUTH, SESSION], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"TECH-001": dict(kind="path", doc=TECH_001_PATH, index=2, evidence=None)}, runs={}, defective=True, step=4,
                          description="規範文のないTECHを起点にしたとき、文書単位のテスト対応のテストのパスを検査し、不在ならfailedにする"),
    "SINGLE-175-06": dict(group="single", argv=["REQ-001", "REQ-002"], tech1=BASE_TESTS + [(NOPE, "REQ-001:AC-01")], tech2=None, second=True,
                          files=[AUTH, SESSION, OTHER], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-001": dict(kind="path", doc=TECH_001_PATH, index=2, evidence=None), "REQ-002": None},
                          runs={"REQ-002": [(OTHER, "REQ-002:AC-01")]}, defective=True, step=4,
                          description="違反した検証対象が止まっても、独立した検証対象のテストは起動し、違反した検証対象の正しいテストは起動しない"),
    "SINGLE-175-07": dict(group="single", argv=["REQ-002"], tech1=BASE_TESTS + [(NOPE, "REQ-001:AC-01")], tech2=None, second=True,
                          files=[AUTH, SESSION, OTHER], link=None, implements=["src/auth.py", "src/session.py"],
                          expect={"REQ-002": None}, runs={"REQ-002": [(OTHER, "REQ-002:AC-01")]}, defective=False, step=4,
                          description="対照: 検証対象が使わないテスト対応の不在のパスは検査しない"),
    "SINGLE-175-08": dict(group="single", argv=["REQ-001"], tech1=BASE_TESTS, tech2=None, second=False,
                          files=[AUTH, SESSION], link=None, implements=["src/gone.py"],
                          expect={"REQ-001": None}, runs={"REQ-001": BASE_TESTS}, defective=False, step=4,
                          description="対照: implementsが存在しないパスでも、verifyは検査しない"),
    "MULTI-062-01": dict(group="multi", argv=["web::REQ-101"], files=["tests/test_x.py", "apps/web/tests/ok.py"], link=("apps/web/ext", "../../tests"),
                         expect={"web::REQ-101": dict(kind="ownership", workspace="web", doc=".spec/requirements/REQ-101.md", index=1, path="ext/test_x.py", evidence=None)},
                         runs={}, defective=True, step=5,
                         description="複合ワークスペースで、使うテスト対応のテストのパスが所有領域の外へ解決するとき、検証対象をfailedにし、SPEC-MULTI-OWNERSHIP-001を返す"),
    "MULTI-062-02": dict(group="multi", argv=["web::REQ-101"], files=["apps/web/tests/ok.py"], link=None,
                         expect={"web::REQ-101": dict(kind="path", workspace="web", doc=".spec/requirements/REQ-101.md", index=1, path=NOPE, evidence=None)},
                         runs={}, defective=True, step=5,
                         description="複合ワークスペースで、使うテスト対応のテストのパスが存在しないとき、検証対象をfailedにする"),
    "MULTI-062-03": dict(group="multi", argv=["REQ-001"], files=["tests/root.py", "apps/web/t.py"], link=None,
                         expect={"platform::REQ-001": dict(kind="ownership", workspace="platform", doc=".spec/requirements/REQ-001.md", index=1, path="apps/web/t.py", evidence=None)},
                         runs={}, defective=True, step=5,
                         description="ルートワークスペースの使うテスト対応のテストのパスが字句でメンバーの配下のとき、所有領域の外として検証対象をfailedにする"),
    "MULTI-062-04": dict(group="multi", argv=["REQ-001"], files=["tests/root.py", "apps/web/tests/web.py"], link=None,
                         expect={"platform::REQ-001": dict(kind="covers", workspace="web", doc=".spec/technical/TECH-010.md", index=0, path=None,
                                                          evidence="platform::REQ-001:AC-01")},
                         runs={}, defective=True, step=5,
                         description="別のワークスペースの規範文を、直接refinesせずにcoversするとき、検証対象をfailedにし、SPEC-TEST-COVERAGE-001を返す"),
    "MULTI-062-05": dict(group="multi", argv=["REQ-001"], files=["tests/root.py", "apps/web/tests/web.py"], link=None,
                         expect={"platform::REQ-001": None},
                         runs={"platform::REQ-001": [("platform", "tests/root.py", "platform::REQ-001:AC-01"), ("web", "tests/web.py", "platform::REQ-001:AC-01")]},
                         defective=False, step=5,
                         description="対照: 宣言する文書が別のワークスペースの規範文を直接refinesするなら、横断のcoversは指定でき、テストを起動する"),
    "MULTI-062-06": dict(group="multi", argv=["--all-workspaces"], files=["apps/web/tests/ok.py", "services/api/tests/ok.py"], link=None,
                         expect={"web::REQ-101": dict(kind="path", workspace="web", doc=".spec/requirements/REQ-101.md", index=1, path=NOPE, evidence=None),
                                 "api::REQ-201": None},
                         runs={"api::REQ-201": [("api", "tests/ok.py", "api::REQ-201:AC-01")]}, defective=True, step=5,
                         description="複合ワークスペース全体のverifyでも、違反した検証対象をfailedにし、独立した検証対象のテストは起動する"),
    "MULTI-062-07": dict(group="multi", argv=["REQ-001"], files=["tests/root.py", "apps/web/tests/web.py"], link=None,
                         expect={"platform::REQ-001": None},
                         runs={"platform::REQ-001": [("platform", "tests/root.py", "platform::REQ-001:AC-01"), ("web", "tests/web.py", "platform::REQ-001:AC-01")]},
                         defective=False, step=5,
                         description="対照: 検証対象が使わないメンバーの文書の不在のパスは検査しない"),
}


# --- 参照計算（Coreにも`pathown`にも依存しない） ----------------------------------------------

def within(path, base):
    """実パスの文字列のセグメントの境界での包含（境界自身を含む）。"""
    return path == base or path.startswith(base.rstrip("/") + "/")


def real_owner(real, roots):
    """実パス`real`を所有するワークスペースのID（最も深いルートが所有する）。どのルートの配下でもなければ`None`。"""
    owners = [(len(root), identifier) for identifier, root in roots.items() if within(real, root)]
    return max(owners)[1] if owners else None


def allowed_covers(documents, name):
    """宣言する文書`name`の`covers`に指定できる規範文と文書（文書・フロントマター・状態仕様のテスト対応の規則(a)〜(c)）。値は修飾ID。"""
    own = set(binding_missing.statement_ids(documents, name))
    allowed = set(own) | ({name} if not own else set())
    for _, target in binding_missing.refines_of(documents, name):
        allowed |= set(binding_missing.statement_ids(documents, target)) if target in documents else {target}
    return allowed


def used_entries(documents, root):
    """検証対象`root`が使うテスト対応: [(文書, 添字, エントリ)]。対象規範文を`covers`するエントリ、規範文のないTECHは起点の`tests`すべて（関係・トレースモデル §6.4）。"""
    order, refiners = binding_missing.verify_closure(documents, root)
    statements = set(binding_missing.target_statements(documents, root, refiners))
    entries = []
    if statements:
        for name in order:
            for index, entry in enumerate(documents[name]["frontmatter"].get("tests", [])):
                covered = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for text in entry["covers"]}
                if covered & statements:
                    entries.append((name, index, entry))
    elif documents[root]["kind"] == "technical":
        entries = [(root, index, entry) for index, entry in enumerate(documents[root]["frontmatter"].get("tests", []))]
    return statements, entries


def reference_target(repository, root, single, workspaces, documents):
    """検証対象`root`（修飾ID）の違反の診断（辞書の並び）と、通過した使うエントリ（[(文書, 添字, エントリ)]）を、入力の木構造から導く。"""
    roots = {identifier: os.path.realpath(repository if info["path"] == "." else repository / info["path"]) for identifier, info in workspaces.items()}
    _, entries = used_entries(documents, root)
    diagnostics, good = [], []
    for name, index, entry in entries:
        document = documents[name]
        workspace = document["workspaceId"]
        source = {"kind": "file", "workspaceId": "root" if single else workspace, "path": document["path"]}
        declared = entry["path"]
        real = os.path.realpath(os.path.join(roots[workspace], declared))
        valid = True
        if not os.path.isfile(real):
            valid = False
            diagnostics.append({"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARY,
                                "source": {**source, "key": f"tests[{index}].path"}})
        elif real_owner(real, roots) != workspace:
            valid = False
            if single:
                diagnostics.append({"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARY,
                                    "source": {**source, "key": f"tests[{index}].path"}})
            else:
                diagnostics.append({"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
                                    "summary": f"パス{declared}の解決先がワークスペース{workspace}の所有領域の外です",
                                    "source": {**source, "key": f"tests[{index}].path"}})
        allowed = allowed_covers(documents, name)
        for text in entry["covers"]:
            if multi_crosscheck.qualify(workspace, text) not in allowed:
                valid = False
                diagnostics.append({"code": "SPEC-TEST-COVERAGE-001", "severity": "error", "resultStatus": "failed", "summary": COVERS_SUMMARY,
                                    "source": {**source, "key": f"tests[{index}].covers"}, "evidence": text})
        if valid:
            good.append((name, index, entry))
    diagnostics.sort(key=lambda d: (d["source"]["workspaceId"], d["source"]["path"], d["code"], d["source"]["key"]))
    return diagnostics, good


# --- 単一ワークスペースの入力 -------------------------------------------------------------------

TECH_002_BODY = "# TECH-002 別の実装方針\n\n## Context\n\nTECH-001をさらに具体化する。\n"
REQ_002_HEAD = "---\nid: REQ-002\ntitle: 監査の基準\nstatus: approved\n---\n"
REQ_002_BODY = (
    "# REQ-002 監査の基準\n\n## Intent\n\n独立した検証対象を定める。\n\n## Acceptance Criteria\n\n"
    "- [REQ-002:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査記録を残す。\n\n## Verification\n\ntests/test_other.pyで確認する。\n")
TECH_003_BODY = "# TECH-003 監査の実装方針\n\n## Context\n\n独立した検証対象の実装方針。\n"


def tests_block(tests):
    return "tests:\n" + "".join(f"  - path: {path}\n    covers: [{cover}]\n    command: default\n" for path, cover in tests)


def tech_001_text(case):
    head = digest_reference.TECH_HEAD_FIELDS
    head = head[:head.index("implements:")] + f"implements: [{', '.join(case['implements'])}]\n" + tests_block(case["tech1"])
    return "---\n" + head + "x-owners: [team-auth]\n---\n\n" + digest_reference.TECH_BODY


def tech_002_text(case):
    return ("---\nid: TECH-002\ntitle: 別の実装方針\nstatus: approved\nrelations:\n  refines: [TECH-001]\n" + tests_block(case["tech2"]) + "---\n\n" + TECH_002_BODY)


def tech_003_text():
    return ("---\nid: TECH-003\ntitle: 監査の実装方針\nstatus: approved\nrelations:\n  refines: [REQ-002]\n" + tests_block([(OTHER, "REQ-002:AC-01")]) + "---\n\n" + TECH_003_BODY)


def single_inputs(identifier):
    case = CASES[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    for path in (AUTH, SESSION, "src/auth.py", "src/session.py"):
        del inputs[path]
    inputs[digest_reference.TECH_PATH] = tech_001_text(case).encode()
    if case["tech2"]:
        inputs[TECH_002_PATH] = tech_002_text(case).encode()
    if case["second"]:
        inputs[".spec/requirements/REQ-002.md"] = (REQ_002_HEAD + "\n" + REQ_002_BODY).encode()
        inputs[".spec/technical/TECH-003.md"] = tech_003_text().encode()
    for path in case["files"]:
        inputs[path] = TEST_CONTENT
    for path in case["implements"]:
        if path.startswith("src/") and path != "src/gone.py":
            inputs[path] = digest_reference.CODE_FILES[path].encode()
    return inputs


def single_digest_input(identifier, target):
    """参照計算A（単一）。`SINGLE-042`のレビュー済みの材料に、TECH-001の`implements`と`tests`、TECH-002、REQ-002・TECH-003だけを加える。"""
    case = CASES[identifier]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["roots"] = [target]
    if target == "REQ-002":
        payload["documents"] = [
            {"id": "REQ-002", "workspaceId": "root", "kind": "requirement", "status": "approved", "applicability": "applicable",
             "frontmatter": {"id": "REQ-002", "title": "監査の基準", "status": "approved", "relations": dict(digest_reference.EMPTY_RELATIONS),
                             "implements": [], "tests": [], "verify": None, "changes": []},
             "bodyText": REQ_002_BODY,
             "statements": [{"id": "REQ-002:AC-01", "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None}, "modality": "MUST",
                             "reason": None, "operation": {"kind": "CONSTRAINT", "text": "監査記録を残す"}, "extensions": []}],
             "strongRelations": []},
            {"id": "TECH-003", "workspaceId": "root", "kind": "technical", "status": "approved", "applicability": "applicable",
             "frontmatter": {"id": "TECH-003", "title": "監査の実装方針", "status": "approved",
                             "relations": {**digest_reference.EMPTY_RELATIONS, "refines": ["REQ-002"]}, "implements": [],
                             "tests": [{"path": OTHER, "covers": ["REQ-002:AC-01"], "command": "default"}], "verify": None, "changes": []},
             "bodyText": TECH_003_BODY, "statements": [], "strongRelations": [{"relation": "refines", "target": "REQ-002"}]},
        ]
        return payload
    tech = payload["documents"][1]
    tech["frontmatter"]["implements"] = sorted(case["implements"])
    tech["frontmatter"]["tests"] = sorted(({"path": path, "covers": [cover], "command": "default"} for path, cover in case["tech1"]),
                                          key=lambda entry: (entry["path"], entry["covers"]))
    if case["tech2"]:
        payload["documents"].append({
            "id": "TECH-002", "workspaceId": "root", "kind": "technical", "status": "approved", "applicability": "applicable",
            "frontmatter": {"id": "TECH-002", "title": "別の実装方針", "status": "approved",
                            "relations": {**digest_reference.EMPTY_RELATIONS, "refines": ["TECH-001"]}, "implements": [],
                            "tests": sorted(({"path": path, "covers": [cover], "command": "default"} for path, cover in case["tech2"]),
                                            key=lambda entry: (entry["path"], entry["covers"])),
                            "verify": None, "changes": []},
            "bodyText": TECH_002_BODY, "statements": [], "strongRelations": [{"relation": "refines", "target": "TECH-001"}]})
    return payload


# --- 複合ワークスペースの入力 -------------------------------------------------------------------
# 文書の記述: (ワークスペース, 種類, ID, タイトル, refines（宣言どおり）, tests（(パス, covers（宣言どおり）)の宣言順）)。規範文は、REQのAC-01の1件だけ。

REQ_TEXT = "秘密情報を出力しない"


def mdoc(workspace, kind, identifier, title, refines=(), tests=()):
    return dict(workspace=workspace, kind=kind, id=identifier, title=title, refines=list(refines), tests=list(tests))


def multi_documents(identifier):
    """このケースの文書。各ケースが違う1つの原因だけを持ち、違反するエントリは正しいエントリと同じ規範文を`covers`する。"""
    ok = lambda p, c: (p, [c])
    if identifier == "MULTI-062-01":
        return [mdoc("web", "requirement", "REQ-101", "Webの基準", tests=[ok("tests/ok.py", "REQ-101:AC-01"), ok("ext/test_x.py", "REQ-101:AC-01")])]
    if identifier == "MULTI-062-02":
        return [mdoc("web", "requirement", "REQ-101", "Webの基準", tests=[ok("tests/ok.py", "REQ-101:AC-01"), ok(NOPE, "REQ-101:AC-01")])]
    if identifier == "MULTI-062-03":
        return [mdoc("platform", "requirement", "REQ-001", "認証の基準", tests=[ok("tests/root.py", "REQ-001:AC-01"), ok("apps/web/t.py", "REQ-001:AC-01")])]
    if identifier == "MULTI-062-06":
        return [mdoc("web", "requirement", "REQ-101", "Webの基準", tests=[ok("tests/ok.py", "REQ-101:AC-01"), ok(NOPE, "REQ-101:AC-01")]),
                mdoc("api", "requirement", "REQ-201", "APIの基準", tests=[ok("tests/ok.py", "REQ-201:AC-01")])]
    direct = identifier in ("MULTI-062-05", "MULTI-062-07")
    documents = [
        mdoc("platform", "requirement", "REQ-001", "認証の基準", tests=[ok("tests/root.py", "REQ-001:AC-01")]),
        mdoc("web", "technical", "TECH-005", "Webの中間の具体化", refines=["platform::REQ-001"]),
        mdoc("web", "technical", "TECH-010", "Webの実装方針", refines=["platform::REQ-001:AC-01" if direct else "TECH-005"],
             tests=[ok("tests/web.py", "platform::REQ-001:AC-01")]),
    ]
    if identifier == "MULTI-062-07":
        documents.append(mdoc("web", "requirement", "REQ-102", "使わないWebの基準", tests=[ok(NOPE, "REQ-102:AC-01")]))
    return documents


def doc_path(document):
    return f".spec/{'requirements' if document['kind'] == 'requirement' else 'technical'}/{document['id']}.md"


def doc_body(document):
    if document["kind"] == "requirement":
        return mverify.requirement_body(document["id"], document["title"], f"{document['id']}:AC-01", REQ_TEXT)
    return mverify.technical_body(document["id"], document["title"], f"{document['title']}を定める。")


def doc_text(document):
    head = f"---\nid: {document['id']}\ntitle: {document['title']}\nstatus: approved\n"
    if document["refines"]:
        head += f"relations:\n  refines: [{', '.join(document['refines'])}]\n"
    if document["tests"]:
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: default\n" for path, covers in document["tests"])
    return head + "---\n\n" + doc_body(document)


def workspace_prefix(workspace):
    return {"platform": "", "web": "apps/web/", "api": "services/api/"}[workspace]


def multi_inputs(identifier):
    case = CASES[identifier]
    root = multi_reference.root_config(MEMBERS) + VERIFY_BLOCK
    inputs = {".spec/bitz.yaml": root.encode(), "apps/web/.spec/bitz.yaml": multi_reference.member_config("web", "default").encode(),
              "services/api/.spec/bitz.yaml": (multi_reference.member_config("api", "default") if identifier == "MULTI-062-06"
                                               else multi_reference.plain_config("api")).encode()}
    for document in multi_documents(identifier):
        inputs[workspace_prefix(document["workspace"]) + doc_path(document)] = doc_text(document).encode()
    for path in case["files"]:
        inputs[path] = TEST_CONTENT
    return inputs


def qualify(workspace, reference):
    return reference if "::" in reference else f"{workspace}::{reference}"


def multi_digest_input(identifier, root):
    """参照計算A（複合）。閉包の文書をリテラルの記述から材料にし、到達したワークスペースの設定と、使うコマンドだけを収録する。"""
    documents = multi_documents(identifier)
    by_name = {f"{d['workspace']}::{d['id']}": d for d in documents}
    # 閉包: `MULTI-062-04`・`05`・`07`は、REQ-001と、REQ-001を`refines`するweb::TECH-005と、それを（推移的に、または直接）`refines`するweb::TECH-010。ほかは起点だけ。
    chosen = ["platform::REQ-001", "web::TECH-005", "web::TECH-010"] if identifier in ("MULTI-062-04", "MULTI-062-05", "MULTI-062-07") else [root]
    materials, edges, reached = [], [], set()
    for name in chosen:
        document = by_name[name]
        workspace = document["workspace"]
        reached.add(workspace)
        relations = {"refines": [qualify(workspace, ref) for ref in document["refines"]]}
        tests = sorted(({"path": path, "covers": sorted(qualify(workspace, c) for c in covers), "command": "default"} for path, covers in document["tests"]),
                       key=lambda entry: (entry["path"], entry["covers"]))
        statements = ([mverify.statement_material(f"{workspace}::{document['id']}:AC-01", REQ_TEXT)] if document["kind"] == "requirement" else [])
        material = mverify.document_material(None, name, workspace, document["kind"], document["title"], doc_body(document), relations=relations, statements=statements)
        material["frontmatter"]["tests"] = tests
        materials.append(material)
        edges += [{"relation": "refines", "source": name, "target": target} for target in relations["refines"]
                  if target.partition("::")[0] != workspace]
    request = root.partition("::")[0]
    paths = {"platform": ".", "web": "apps/web", "api": "services/api"}
    commands = [{"workspaceId": ws, "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."} for ws in sorted(reached)]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0", "purpose": "verify",
        "requestWorkspaceId": request, "roots": [root],
        "workspaces": [{"id": name, "path": paths[name]} for name in [request, *sorted(reached - {request})]],
        "documents": sorted(materials, key=lambda item: item["id"]),
        "crossWorkspaceEdges": sorted(edges, key=lambda e: (e["source"], e["relation"], e["target"])),
        "settings": {"workspaces": [{"id": name, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"} for name in sorted(reached)],
                     "context": {"maxDocuments": 20, "maxBytes": 131072},
                     "verifyTimeouts": [{"workspaceId": ws, "timeoutSeconds": 300} for ws in sorted(reached)], "commands": commands},
    }


# --- 共通の入力と期待結果 --------------------------------------------------------------------

def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def reviewed_inputs(identifier):
    """`repo/`の通常のファイル（パス→バイト列）。シンボリックリンクは`reviewed_links`が持つ。"""
    return single_inputs(identifier) if CASES[identifier]["group"] == "single" else multi_inputs(identifier)


def reviewed_links(identifier):
    link = CASES[identifier]["link"]
    return {link[0]: link[1]} if link else {}


def targets_of(identifier):
    return sorted(CASES[identifier]["expect"])


def reviewed_status(identifier):
    return "failed" if any(CASES[identifier]["expect"].values()) else "passed"


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["group"] == "single":
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    else:
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    status = reviewed_status(identifier)
    return {"fixtureId": identifier, "description": case["description"], "setup": setup_plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", *case["argv"], "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0}}


def violation_diagnostic(violation, workspace_id):
    """期待する違反の診断（レビュー済みのリテラル。参照計算の結果と一致することを監査が要求する）。"""
    source = {"kind": "file", "workspaceId": violation.get("workspace", workspace_id), "path": violation["doc"]}
    if violation["kind"] == "covers":
        return {"code": "SPEC-TEST-COVERAGE-001", "severity": "error", "resultStatus": "failed", "summary": COVERS_SUMMARY,
                "source": {**source, "key": f"tests[{violation['index']}].covers"}, "evidence": violation["evidence"]}
    key = f"tests[{violation['index']}].path"
    if violation["kind"] == "ownership":
        return {"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
                "summary": f"パス{violation['path']}の解決先がワークスペース{violation['workspace']}の所有領域の外です", "source": {**source, "key": key}}
    return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARY, "source": {**source, "key": key}}


def target_statements_of(identifier, target):
    if CASES[identifier]["group"] == "single":
        return list(STATEMENTS[target])
    return {"web::REQ-101": ["web::REQ-101:AC-01"], "api::REQ-201": ["api::REQ-201:AC-01"], "platform::REQ-001": ["platform::REQ-001:AC-01"]}[target]


def digest_of(identifier, target):
    case = CASES[identifier]
    payload = single_digest_input(identifier, target) if case["group"] == "single" else multi_digest_input(identifier, target)
    return digest_reference.digest(digest_reference.canonical_bytes(payload))


def target_entry(identifier, target):
    case = CASES[identifier]
    violation = case["expect"][target]
    if violation:
        return {"target": target, "status": "failed", "contextDigest": digest_of(identifier, target), "statements": target_statements_of(identifier, target),
                "bindingRefs": [], "diagnostics": [violation_diagnostic(violation, "root")]}
    if case["group"] == "single":
        bindings = ["root::default"]
    else:
        bindings = sorted({f"{workspace}::default" for workspace, _, _ in case["runs"][target]})
    return {"target": target, "status": "passed", "contextDigest": digest_of(identifier, target), "statements": target_statements_of(identifier, target),
            "bindingRefs": bindings, "diagnostics": []}


def command_entries(identifier):
    """起動するテスト割当て（通過した検証対象のテスト対応を、ワークスペースの処理順、コマンド名の辞書順にまとめる）。"""
    case = CASES[identifier]
    grouped = {}
    for target, runs in case["runs"].items():
        for run in runs:
            workspace, path, cover = ("root", *run) if case["group"] == "single" else run
            bucket = grouped.setdefault(workspace, {"tests": set(), "covers": set()})
            bucket["tests"].add(path)
            bucket["covers"].add(qualify_cover(case, workspace, cover))
    order = ["root"] if case["group"] == "single" else ["platform", "api", "web"]
    return [mverify.command_result(workspace, "default", "/bin/true", sorted(grouped[workspace]["tests"]), sorted(grouped[workspace]["covers"]))
            for workspace in order if workspace in grouped]


def qualify_cover(case, workspace, cover):
    return cover if case["group"] == "single" else qualify(workspace, cover)


def reviewed_result(identifier):
    case = CASES[identifier]
    status = reviewed_status(identifier)
    entries = [target_entry(identifier, target) for target in targets_of(identifier)]
    commands = command_entries(identifier)
    if case["group"] == "single":
        for command in commands:
            command["covers"] = sorted(command["covers"])
        return {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected", "workspace": {"id": "root", "path": "."},
                "targetResults": entries, "revision": None, "commands": commands, "durationMs": 0, "diagnostics": []}
    if "--all-workspaces" in case["argv"]:
        by_workspace = {"platform": [], "api": [], "web": []}
        for entry in entries:
            by_workspace[entry["target"].partition("::")[0]].append(entry)
        commands_by = {command["workspaceId"]: [command] for command in commands}
        workspaces = [mverify.workspace_result("platform", ".", "passed_with_warnings", diagnostics=[
            {**mverify.NO_TARGET, "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"}}])]
        for workspace, path in (("api", "services/api"), ("web", "apps/web")):
            targets = by_workspace[workspace]
            workspace_status = "failed" if any(t["status"] == "failed" for t in targets) else "passed"
            workspaces.append(mverify.workspace_result(workspace, path, workspace_status, targets=targets, commands=commands_by.get(workspace, [])))
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": status, "multiWorkspace": {"id": "platform", "path": "."},
                "workspaces": workspaces, "revision": {"commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}
    request = case["argv"][0].partition("::")[0] if "::" in case["argv"][0] else "platform"
    return {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
            "workspace": {"id": request, "path": {"platform": ".", "web": "apps/web"}[request]},
            "targetResults": entries, "revision": {"commit": COMMIT, "dirty": False}, "commands": commands, "durationMs": 0, "diagnostics": []}


# --- 準備手順の後の入力の検査 -----------------------------------------------------------------

def load_tree(repository):
    """(単一か, ルートワークスペースのID, ワークスペース, 文書)。文書のキーは`<ワークスペース>::<ID>`。単一ワークスペースの設定は`workspace.id`を持たなくてよく、IDは`root`になる。"""
    config = digest_crosscheck.read_yaml((repository / ".spec/bitz.yaml").read_text(encoding="utf-8"))
    single = "multiWorkspace" not in config
    root_id = config.get("workspace", {}).get("id", "root")
    members = [] if single else multi_crosscheck.catalog(repository)[1]
    workspaces, documents = {}, {}
    for workspace_id, path in [(root_id, ".")] + members:
        root = repository if path == "." else repository / path
        workspaces[workspace_id] = {"path": path, "config": digest_crosscheck.read_yaml((root / ".spec/bitz.yaml").read_text(encoding="utf-8"))}
        for directory, kind in digest_crosscheck.KIND_BY_DIRECTORY.items():
            folder = root / ".spec" / directory
            if not folder.is_dir():
                continue
            for file in sorted(folder.glob("*.md")):
                frontmatter, raw = digest_crosscheck.split_document(file.read_text(encoding="utf-8"))
                documents[f"{workspace_id}::{frontmatter['id']}"] = {
                    "workspaceId": workspace_id, "kind": kind, "frontmatter": frontmatter,
                    "body": digest_crosscheck.normalize_body(raw), "path": file.relative_to(root).as_posix()}
    return single, root_id, workspaces, documents


def tracked_entries(repository):
    from .harness import git
    result = {}
    for line in git(repository, "ls-files", "--stage", "-z").decode().split("\0")[:-1]:
        head, path = line.split("\t", 1)
        result[path] = (head.split()[0], git(repository, "show", ":" + path))
    return result


def result_targets(result):
    entries = list(result.get("targetResults", []))
    for workspace in result.get("workspaces", []):
        entries += workspace["targetResults"]
    return {entry["target"]: entry for entry in entries}


def result_commands(result):
    commands = list(result.get("commands", []))
    for workspace in result.get("workspaces", []):
        commands += workspace["commands"]
    return commands


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる（Coreの出力は根拠にしない）。"""
    case = CASES[identifier]
    entries = tracked_entries(repository)
    files = {path: data for path, (mode, data) in entries.items() if mode == "100644"}
    links = {path: data.decode() for path, (mode, data) in entries.items() if mode == "120000"}
    if {path for path, (mode, _) in entries.items() if mode not in ("100644", "120000")}:
        raise ValueError("追跡するエントリは通常のファイルとシンボリックリンクだけである必要があります")
    if files != reviewed_inputs(identifier) or links != reviewed_links(identifier):
        raise ValueError("インデックスがレビュー済みの入力と異なります")
    for path, target in links.items():
        if not (repository / path).is_symlink() or os.readlink(repository / path) != target:
            raise ValueError("作業ツリーのシンボリックリンクがレビュー済みの入力と異なります")
    if case["link"] is not None and os.path.isabs(case["link"][1]):
        target = Path(case["link"][1]) / EXTERNAL_FILE
        if not target.is_file() or within(os.path.realpath(repository), os.path.realpath(case["link"][1])):
            raise ValueError("リポジトリの外のディレクトリのファイルがファイルとして存在する必要があります")
    single, _root_id, workspaces, documents = load_tree(repository)
    if single != (case["group"] == "single"):
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    targets = result_targets(result)
    if sorted(targets) != targets_of(identifier):
        raise ValueError("検証対象が期待と異なります")
    any_violation = False
    runs = {}
    for target, entry in targets.items():
        qualified = f"root::{target}" if single else (target if "::" in target else f"platform::{target}")
        diagnostics, good = reference_target(repository, qualified, single, workspaces, documents)
        if diagnostics != entry["diagnostics"]:
            raise ValueError(f"{target}の診断が参照計算と異なります")
        if bool(diagnostics) != bool(case["expect"][target]):
            raise ValueError(f"{target}の違反の有無が期待と異なります")
        statements, _ = used_entries(documents, qualified)
        expected_statements = sorted(s.partition("::")[2] if single else s for s in statements)
        if entry["statements"] != expected_statements:
            raise ValueError(f"{target}の対象規範文が参照計算と異なります")
        if diagnostics:
            any_violation = True
            if entry["status"] != "failed" or entry["bindingRefs"]:
                raise ValueError("違反した検証対象はfailedで、bindingRefsは空である必要があります")
        else:
            if entry["status"] != "passed":
                raise ValueError("違反のない検証対象はpassedである必要があります")
            runs[target] = good
    if any_violation != case["defective"]:
        raise ValueError("欠陥を検出できる入力、または対照の入力ではありません")
    # 起動するテスト: 通過した検証対象が使う、正しいテスト対応のパスだけ（違反した検証対象のテストは起動しない）。
    expected_tests = {}
    for target, good in runs.items():
        for name, _index, entry in good:
            workspace = documents[name]["workspaceId"]
            expected_tests.setdefault("root" if single else workspace, set()).add(entry["path"])
    commands = result_commands(result)
    if {c["workspaceId"]: set(c["tests"]) for c in commands} != expected_tests:
        raise ValueError("起動するテストが参照計算と異なります")
    status = reviewed_status(identifier)
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")


def check_digest(identifier, repository, result):
    single, _root_id, workspaces, documents = load_tree(repository)
    for target, entry in result_targets(result).items():
        if single:
            derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, root=target))
            literal = digest_reference.canonical_bytes(single_digest_input(identifier, target))
        else:
            qualified = target if "::" in target else f"platform::{target}"
            derived = digest_reference.canonical_bytes(binding_missing.derived_material(repository, documents, workspaces, qualified))
            literal = digest_reference.canonical_bytes(multi_digest_input(identifier, qualified))
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
        for name, target in reviewed_links(identifier).items():
            link = fixture / "repo" / name
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink():
                link.unlink()
            link.symlink_to(target)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-verify-test-check-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def actual_entries(fixture):
    """`repo/`の通常のファイル(パス→バイト列)とシンボリックリンク(パス→向き先)。リンクの先へは入らない。"""
    files, links = {}, {}
    base = fixture / "repo"
    for directory, names, filenames in os.walk(base, followlinks=False):
        for name in [*names, *filenames]:
            path = Path(directory) / name
            relative = path.relative_to(base).as_posix()
            if path.is_symlink():
                links[relative] = os.readlink(path)
            elif path.is_file():
                if path.stat().st_mode & 0o111:
                    raise ValueError(f"{relative}は実行ビットを持ってはいけません")
                files[relative] = path.read_bytes()
    return files, links


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
            if {p.name for p in (fixture / "expected").glob("*")} != {"verify.json"} or any((fixture / name).exists() for name in ("changes", "cli-output.json")):
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            files, links = actual_entries(fixture)
            if files != reviewed_inputs(identifier) or links != reviewed_links(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-test-check-") as temporary:
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
