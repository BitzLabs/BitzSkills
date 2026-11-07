"""所有と包含を実パスで判定することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C88・C90と、N1・N3、ADR-051の追加に対応する。ユーザーの決定により、規範は次のとおりに明記された。

- 複合ワークスペース仕様 §5.1の手順4・5: 所有領域は、上位のディレクトリのシンボリックリンクを解決した実パスと、ファイルシステム上の同一性で判定する。
  コード、テスト、TASK、`cwd`のシンボリックリンクは、同じ所有領域の中へ解決する場合だけ許す。リポジトリの外、別のワークスペース、メンバーの`.spec`へ解決すれば
  `SPEC-MULTI-OWNERSHIP-001`とする。ルートワークスペースは、メンバーの配下を所有しない。
- ワークスペース・設定仕様 §6: テストのパスと実効`cwd`の包含は、両方を実パスにして判定する。字句では配下でも実パスが外なら`VERIFY-TEST-OUTSIDE-CWD`
  （`SPEC-VERIFY-BLOCKED-001`、`blocked`）、字句では外でも実パスが配下なら通す。このとき引数列は、実パスどうしの相対で展開する
  （字句の相対パスが実効`cwd`の外を指す場合だけ。配下を指すなら字句の相対パス）。
- ワークスペース・設定仕様 §9: 単一ワークスペースの`implements`と`tests[].path`は、上位のディレクトリのシンボリックリンクを解決した実パスがルートの外
  （リポジトリの外を含む）なら、存在しないパスと同じく`SPEC-PATH-INVALID-001`とする（承認済みの文言「実装パスが存在しません」「テストのパスが存在しません」）。
- `verify` §5.1: `VERIFY-TEST-OUTSIDE-CWD`の`source`は、配下にないテストを宣言した仕様文書（複数あればパスの辞書順で最初の文書）、`key`はその文書の`tests[i].path`
  （配下にないテストのパスが複数あれば最小の添字）で、テスト割当てごとに1件とする。

修正前のCoreは、上位のディレクトリのシンボリックリンクを解決せず（宣言したパスの末端のシンボリックリンクだけを判定した）、包含を字句の相対パスで判定し、
`VERIFY-TEST-OUTSIDE-CWD`の`source`を設定ファイルにしていた。次の「診断の文言」は、承認済みの文言だけを使う。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-174-01` | `check --full --base HEAD` | REQの`tests[0].path`が`ext/env`。`ext -> /usr/bin`（リポジトリの外のディレクトリ） | `failed`／1。`SPEC-PATH-INVALID-001`、キー`tests[0].path`。修正前のCoreは`passed`／0 |
| `SINGLE-174-02` | 同上 | REQの`implements`が`ext/env`。`ext -> /usr/bin` | `failed`／1。`SPEC-PATH-INVALID-001`、キー`implements`。修正前のCoreは`passed`／0 |
| `SINGLE-174-03` | 同上 | REQの`tests[0].path`が`ext/t.py`。`ext -> real`（ワークスペースの中。対照） | `passed`／0。診断なし。修正前のCoreも通る |
| `SINGLE-174-04` | 同上 | REQの`implements`が`ext/a.py`。`ext -> real`（対照） | `passed`／0。診断なし。修正前のCoreも通る |
| `SINGLE-174-05` | `check --full --base HEAD`（`pkg`で実行） | ワークスペースのルートが`pkg`。REQの`tests[0].path`が`ext/t.py`。`pkg/ext -> ../shared`（リポジトリの中でワークスペースの外） | `failed`／1。キー`tests[0].path`。修正前のCoreは`passed`／0 |
| `SINGLE-174-06` | 同上 | 同じ配置で、REQの`implements`が`ext/a.py` | `failed`／1。キー`implements`。修正前のCoreは`passed`／0 |
| `SINGLE-174-07` | `verify REQ-001` | `cwd`が`inner`（`inner -> real`）、テストが`real/test_*.py`（字句では`cwd`の外、実パスでは配下） | `passed`／0。引数列は`cwd`からの実パスどうしの相対（`test_auth.py`、`test_session.py`）。修正前のCoreは`blocked`／2 |
| `SINGLE-174-08` | 同上 | `cwd`が`tests`、テストが`tests/link/test_*.py`（`tests/link -> ../other`。字句では配下、実パスでは外） | `blocked`／2。`SPEC-VERIFY-BLOCKED-001`、発生元は宣言したTECH-001とキー`tests[0].path`。修正前のCoreは`passed`／0 |
| `SINGLE-174-09` | 同上 | `cwd`が`tests`。TECH-001が`tests[0]`に配下のテスト、`tests[1]`に`tests/link/test_auth.py`、TECH-002が`tests[0]`に`tests/link/test_auth.py`を宣言する | `blocked`／2。発生元は辞書順で最初のTECH-001で、キーは`tests[1].path`（配下にないテストの添字。別の文書の添字0ではない）。修正前のCoreは`passed`／0 |
| `SINGLE-174-10` | 同上 | `cwd`が`.`、テストが`ext/test_*.py`（`ext -> real`。字句でも実パスでも配下。対照） | `passed`／0。引数列は字句の相対パス（`ext/test_auth.py`）。修正前のCoreも通る |
| `MULTI-061-01` | `check --all-workspaces --base HEAD` | メンバー`web`のREQの`tests[0].path`が`ext/test_x.py`。`apps/web/ext -> ../../tests`（ルートの領域） | `failed`／1。`web`に`SPEC-MULTI-OWNERSHIP-001`、キー`tests[0].path`（N1）。修正前のCoreは`passed`／0 |
| `MULTI-061-02` | 同上 | ルートのREQの`implements`が`apps/web/src/a.py`（字句でメンバーの配下） | `failed`／1。`platform`に`SPEC-MULTI-OWNERSHIP-001`、キー`implements`。修正前のCoreは`passed`／0 |
| `MULTI-061-03` | 同上 | `web`のREQの`implements`が`ext/a.py`。`apps/web/ext -> real`（`web`の中。対照） | `passed`／0。修正前のCoreも通る |
| `MULTI-061-04` | 同上 | `web`のREQの`implements`が`ext/session.py`。`apps/web/ext -> ../../services/api/src`（別のメンバー） | `failed`／1。`web`に`SPEC-MULTI-OWNERSHIP-001`。修正前のCoreは`passed`／0 |
| `MULTI-061-05` | 同上 | ルートのREQの`implements`が`lk/a.py`。`lk -> apps/web/src`（ルートの領域から、メンバーの配下へ解決） | `failed`／1。`platform`に`SPEC-MULTI-OWNERSHIP-001`。修正前のCoreは`passed`／0 |
| `MULTI-061-06` | 同上 | `web`のREQの`implements`が`ext/env`。`apps/web/ext -> /usr/bin`（リポジトリの外） | `failed`／1。`web`に`SPEC-MULTI-OWNERSHIP-001`。修正前のCoreは`passed`／0 |
| `MULTI-061-07` | 同上 | ルートのREQの`tests[0].path`が`lib/test_x.py`。`lib -> shared`（ルートの領域の中。対照） | `passed`／0。修正前のCoreも通る |

期待値は規範と承認済みの文言から導く参照計算（`real_owner`、`reference_outcome`）で、実パスは`os.path.realpath`（文字列）で、Coreの`os.path.samestat`とは別に求める。
Coreの出力は根拠にしない。fixtureは、1つの原因だけを持つ。

規範から決まらず、既存の形で決めた点:
- `SPEC-PATH-INVALID-001`と`SPEC-MULTI-OWNERSHIP-001`の`key`は、`implements`はフィールド名、`tests`は`tests[i].path`にした（`SINGLE-024`、`MULTI-008`、`verify` §5.1の`tests[i].path`）。
- 失敗した文書も数える（`SINGLE-024`は`checkedDocumentCount`が1、`checkedStatementCount`が1。`MULTI-008`の`web`は文書1件）。
- `VERIFY-TEST-OUTSIDE-CWD`の結果の形（`blocked`、`bindingRefs`は空、`commands`は空、診断は最上位に1件）は、`SINGLE-167-07`の形（`skip-binding`）を引き継いだ。
- リポジトリの外のディレクトリは、サンドボックスの外へfixtureが書けないので、ホストの`/usr/bin`（ほとんどのLinuxとmacOSが持つ）を指す絶対パスのシンボリックリンクで置く。
  `/usr/bin/env`はファイルへ解決する必要がある（シンボリックリンクでもよい。監査が確かめる）。ホストに依存しない同じ性質（リポジトリの中でワークスペースの外）を`SINGLE-174-05`・`06`が押さえる。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import command_cwd_fixtures as command_cwd
from . import digest_crosscheck, digest_reference, multi_reference
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXTERNAL_DIRECTORY = "/usr/bin"
EXTERNAL_FILE = "env"
CODE_CONTENT = b"# implementation\n"
TEST_CONTENT = b'raise RuntimeError("check must not run test code")\n'
TITLE = "実パスの所有"
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
TEST_NAMES = ["test_auth.py", "test_session.py"]
OUTSIDE_SUMMARY = "テストのパスが実効の作業ディレクトリの配下にありません"
PATH_SUMMARIES = {"implements": "実装パスが存在しません", "tests": "テストのパスが存在しません"}
EXIT = {"passed": 0, "failed": 1, "blocked": 2}
MEMBERS = (("web", "apps/web"), ("api", "services/api"))
ROOT_CONFIG_PATH = ".spec/bitz.yaml"
VERIFY_BLOCK = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'

# --- ケース -------------------------------------------------------------------------------
# group: `check`（単一ワークスペースの`check`）、`verify`（単一ワークスペースの`verify`）、`multi`（複合ワークスペースの`check --all-workspaces`）。
# check: workspace〈ワークスペースのルートのリポジトリからの相対パス〉, field〈implements|tests〉, path〈宣言したパス〉, link〈(置き場, 向き先)〉,
#        files〈実ファイルを置くパス〉, outcome〈outside|inside〉
# verify: cwd, link, kind〈passed|blocked〉, documents〈宣言する文書〉, files〈実ファイル〉, argv〈引数列の展開〉
# multi: owner〈宣言するワークスペース〉, field, path, link, files, outcome〈violation|ok〉
# 共通: defective〈修正前のCoreが違う結果を返すか〉, step, description
CASES = {
    "SINGLE-174-01": dict(group="check", workspace=".", field="tests", path="ext/env", link=("ext", EXTERNAL_DIRECTORY), files=[],
                          outcome="outside", defective=True, step=2,
                          description="tests[].pathの上位のディレクトリがリポジトリの外へ解決するシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-02": dict(group="check", workspace=".", field="implements", path="ext/env", link=("ext", EXTERNAL_DIRECTORY), files=[],
                          outcome="outside", defective=True, step=2,
                          description="implementsの上位のディレクトリがリポジトリの外へ解決するシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-03": dict(group="check", workspace=".", field="tests", path="ext/t.py", link=("ext", "real"), files=["real/t.py"],
                          outcome="inside", defective=False, step=2,
                          description="対照: tests[].pathの上位のディレクトリがワークスペースの中へ解決するシンボリックリンクなら通る"),
    "SINGLE-174-04": dict(group="check", workspace=".", field="implements", path="ext/a.py", link=("ext", "real"), files=["real/a.py"],
                          outcome="inside", defective=False, step=2,
                          description="対照: implementsの上位のディレクトリがワークスペースの中へ解決するシンボリックリンクなら通る"),
    "SINGLE-174-05": dict(group="check", workspace="pkg", field="tests", path="ext/t.py", link=("pkg/ext", "../shared"), files=["shared/t.py"],
                          outcome="outside", defective=True, step=2,
                          description="tests[].pathの上位のディレクトリが、リポジトリの中でワークスペースの外へ解決するなら、存在しないパスと同じにする"),
    "SINGLE-174-06": dict(group="check", workspace="pkg", field="implements", path="ext/a.py", link=("pkg/ext", "../shared"), files=["shared/a.py"],
                          outcome="outside", defective=True, step=2,
                          description="implementsの上位のディレクトリが、リポジトリの中でワークスペースの外へ解決するなら、存在しないパスと同じにする"),
    "SINGLE-174-07": dict(group="verify", defective=True, cwd="inner", link=("inner", "real"), kind="passed", step=4,
                          tests=[["real/test_auth.py", "real/test_session.py"]], files=["real/test_auth.py", "real/test_session.py"],
                          description="cwdがシンボリックリンクで、テストが字句ではcwdの外でも実パスでは配下なら通し、引数列は実パスどうしの相対にする"),
    "SINGLE-174-08": dict(group="verify", defective=True, cwd="tests", link=("tests/link", "../other"), kind="blocked", step=4,
                          tests=[["tests/link/test_auth.py", "tests/link/test_session.py"]], files=["other/test_auth.py", "other/test_session.py"],
                          source=(".spec/technical/TECH-001.md", 0),
                          description="テストが字句ではcwdの配下でも実パスでは外なら、宣言した仕様文書とtests[i].pathを発生元にして遮断する"),
    "SINGLE-174-09": dict(group="verify", defective=True, cwd="tests", link=("tests/link", "../other"), kind="blocked", step=4,
                          tests=[["tests/test_ok.py", "tests/link/test_auth.py"], ["tests/link/test_auth.py"]],
                          files=["tests/test_ok.py", "other/test_auth.py"], source=(".spec/technical/TECH-001.md", 1),
                          description="配下にないテストを複数の文書が宣言するとき、パスの辞書順で最初の文書と、その文書の最小の添字を発生元にして1件で遮断する"),
    "SINGLE-174-10": dict(group="verify", defective=False, cwd=".", link=("ext", "real"), kind="passed", step=4,
                          tests=[["ext/test_auth.py", "ext/test_session.py"]], files=["real/test_auth.py", "real/test_session.py"],
                          description="対照: テストが字句でも実パスでもcwdの配下なら、引数列は字句の相対パスのままにする"),
    "MULTI-061-01": dict(group="multi", owner="web", field="tests", path="ext/test_x.py", link=("apps/web/ext", "../../tests"),
                         files=["tests/test_x.py"], outcome="violation", defective=True, step=5,
                         description="メンバーのtests[].pathの上位のディレクトリがルートの領域へ解決するシンボリックリンクなら所有境界の違反にする"),
    "MULTI-061-02": dict(group="multi", owner="platform", field="implements", path="apps/web/src/a.py", link=None,
                         files=["apps/web/src/a.py"], outcome="violation", defective=True, step=5,
                         description="ルートワークスペースがimplementsで字句のままメンバーの配下を宣言したら所有境界の違反にする"),
    "MULTI-061-03": dict(group="multi", owner="web", field="implements", path="ext/a.py", link=("apps/web/ext", "real"),
                         files=["apps/web/real/a.py"], outcome="ok", defective=False, step=5,
                         description="対照: メンバーのimplementsの上位のディレクトリがメンバーの中へ解決するなら通る"),
    "MULTI-061-04": dict(group="multi", owner="web", field="implements", path="ext/session.py", link=("apps/web/ext", "../../services/api/src"),
                         files=["services/api/src/session.py"], outcome="violation", defective=True, step=5,
                         description="メンバーのimplementsの上位のディレクトリが別のメンバーへ解決するシンボリックリンクなら所有境界の違反にする"),
    "MULTI-061-05": dict(group="multi", owner="platform", field="implements", path="lk/a.py", link=("lk", "apps/web/src"),
                         files=["apps/web/src/a.py"], outcome="violation", defective=True, step=5,
                         description="ルートのimplementsの上位のディレクトリがメンバーの配下へ解決するシンボリックリンクなら所有境界の違反にする"),
    "MULTI-061-06": dict(group="multi", owner="web", field="implements", path="ext/env", link=("apps/web/ext", EXTERNAL_DIRECTORY),
                         files=[], outcome="violation", defective=True, step=5,
                         description="メンバーのimplementsの上位のディレクトリがリポジトリの外へ解決するシンボリックリンクなら所有境界の違反にする"),
    "MULTI-061-07": dict(group="multi", owner="platform", field="tests", path="lib/test_x.py", link=("lib", "shared"),
                         files=["shared/test_x.py"], outcome="ok", defective=False, step=5,
                         description="対照: ルートのtests[].pathの上位のディレクトリがルートの領域の中へ解決するなら通る"),
}


# --- 実パスの参照計算（Coreにも`pathown`にも依存しない） ----------------------------------------

def within(path, base):
    """実パスの文字列のセグメントの境界での包含（境界自身を含む）。"""
    return path == base or path.startswith(base.rstrip("/") + "/")


def real_owner(real, roots):
    """実パス`real`を所有するワークスペースのID。ルートの配下から、配下にある別のワークスペースの配下を除く（最も深いルートが所有する）。
    どのルートの配下にもなければ`None`（リポジトリの外、または所有者のいない場所）。"""
    owners = [(len(root), identifier) for identifier, root in roots.items() if within(real, root)]
    return max(owners)[1] if owners else None


def reference_roots(repository, case):
    """複合ワークスペースの各ワークスペースのルートの実パス。"""
    base = os.path.realpath(repository)
    return {"platform": base, **{identifier: os.path.realpath(repository / path) for identifier, path in MEMBERS}}


def reference_outcome(identifier, repository):
    """準備手順の後の入力から、宣言したパスの扱いを導く（`check`と`multi`）。"""
    case = CASES[identifier]
    if case["group"] == "check":
        workspace = repository / case["workspace"]
        real = os.path.realpath(workspace / case["path"])
        if not os.path.isfile(real) or os.path.islink(workspace / case["path"]):
            return "missing"
        return "inside" if within(real, os.path.realpath(workspace)) else "outside"
    roots = reference_roots(repository, case)
    real = os.path.realpath(repository / owner_prefix(case) / case["path"])
    if not os.path.isfile(real):
        return "missing"
    return "ok" if real_owner(real, roots) == case["owner"] else "violation"


def owner_prefix(case):
    return "" if case["owner"] == "platform" else dict(MEMBERS)[case["owner"]]


def old_outcome(identifier, repository):
    """修正前のCoreの読み方。宣言したパスの末端がシンボリックリンクのときだけ実パスを見て、上位のディレクトリのシンボリックリンクは見ない
    （字句のパスの実在だけを要求する）。`check`と`multi`で、結果が期待と異なれば欠陥を検出できる入力である。"""
    case = CASES[identifier]
    if case["group"] == "check":
        path = repository / case["workspace"] / case["path"]
        return "inside" if path.is_file() and not path.is_symlink() else "missing"
    path = repository / owner_prefix(case) / case["path"]
    return "ok" if path.is_file() else "missing"


def lexical_relative(cwd, test):
    """字句の相対パス（実パスを見ない）。"""
    return os.path.relpath(os.path.normpath(test), os.path.normpath(cwd))


def reference_argv(repository, cwd, tests):
    """規範どおりの引数列の展開。実パスで包含を判定し、字句の相対パスが`cwd`の外を指すときだけ実パスどうしの相対にする。"""
    real_cwd = os.path.realpath(repository / cwd)
    result = []
    for test in tests:
        real_test = os.path.realpath(repository / test)
        if not within(real_test, real_cwd):
            return None
        relative = lexical_relative(cwd, test)
        if relative == ".." or relative.startswith("../"):
            relative = os.path.relpath(real_test, real_cwd)
        result.append(relative)
    return result


def old_verify_outcome(identifier):
    """修正前のCoreの`verify`の読み方。字句の相対パスで包含を判定した（`..`で始まれば配下にない）。"""
    case = CASES[identifier]
    for documents in case["tests"]:
        for test in documents:
            relative = lexical_relative(case["cwd"], test)
            if relative == ".." or relative.startswith("../"):
                return "blocked"
    return "passed"


# --- 入力 -------------------------------------------------------------------------------------

def requirement(identifier, implements=(), tests=()):
    head = f"---\nid: {identifier}\ntitle: {TITLE}\nstatus: approved\n"
    if implements:
        head += "implements: [" + ", ".join(implements) + "]\n"
    if tests:
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{identifier}:AC-01]\n    command: default\n" for path in tests)
    return (head + "---\n\n"
            f"# {identifier} {TITLE}\n\n## Intent\n\n実パスの所有を検査する。\n\n## Acceptance Criteria\n\n"
            f"- [{identifier}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
            "## Verification\n\nCore実装後に確認する。現時点では未証明。\n")


def content_of(path):
    return TEST_CONTENT if "test" in Path(path).name or path.startswith("tests/") else CODE_CONTENT


def prefixed(prefix, path):
    return path if prefix in ("", ".") else f"{prefix}/{path}"


def check_inputs(identifier):
    case = CASES[identifier]
    prefix = case["workspace"]
    config = CONFIGS["SINGLE-001"] + (VERIFY_BLOCK if case["field"] == "tests" else "")
    declared = {case["field"]: [case["path"]]} if case["field"] == "implements" else {"tests": [case["path"]]}
    inputs = {prefixed(prefix, ROOT_CONFIG_PATH): config.encode(),
              prefixed(prefix, ".spec/requirements/REQ-001.md"): requirement("REQ-001", **{"implements": declared.get("implements", ()),
                                                                                           "tests": declared.get("tests", ())}).encode()}
    for path in case["files"]:
        inputs[path] = content_of(path)
    return inputs


def corpus(identifier):
    """`SINGLE-042`のcorpus。テストの実体を、ケースの`files`へ移す。"""
    case = CASES[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    for name in TEST_NAMES:
        del inputs[f"tests/{name}"]
    for path in case["files"]:
        inputs[path] = content_of(path)
    inputs[digest_reference.CONFIG_PATH] = digest_reference.CONFIG.replace(
        command_cwd.CWD_LINE, f"      cwd: {case['cwd']}\n").encode()
    return inputs


def tech_documents(identifier):
    """宣言する文書のパス→(ID、`tests`の宣言(パス, 規範文)の並び)。"""
    case = CASES[identifier]
    documents = {"TECH-001": [(path, STATEMENTS[index]) for index, path in enumerate(case["tests"][0])]}
    if len(case["tests"]) > 1:
        documents["TECH-002"] = [(path, STATEMENTS[0]) for path in case["tests"][1]]
    return documents


def tech_text(identifier, document):
    """TECH-001は`SINGLE-042`の文書の`tests`だけを置き換え、TECH-002は`SINGLE-106-02`と同じ形の最小の具体化にする。"""
    tests = tech_documents(identifier)[document]
    block = "tests:\n" + "".join(f"  - path: {path}\n    covers: [{cover}]\n    command: default\n" for path, cover in tests)
    if document == "TECH-001":
        head = digest_reference.TECH_HEAD_FIELDS
        head = head[:head.index("tests:\n")] + block
        return "---\n" + head + "x-owners: [team-auth]\n---\n\n" + digest_reference.TECH_BODY
    return ("---\nid: TECH-002\ntitle: 別の実装方針\nstatus: approved\nrelations:\n  refines: [REQ-001]\n" + block + "---\n\n" + TECH_002_BODY)


TECH_002_BODY = "# TECH-002 別の実装方針\n\n## Context\n\n同じテスト割当てへ別のテストを宣言する。\n"


def verify_inputs(identifier):
    inputs = corpus(identifier)
    for document in tech_documents(identifier):
        inputs[f".spec/technical/{document}.md"] = tech_text(identifier, document).encode()
    return inputs


def multi_config(identifier):
    case = CASES[identifier]
    root = multi_reference.root_config(MEMBERS, "platform")
    return root + (VERIFY_BLOCK if case["owner"] == "platform" and case["field"] == "tests" else "")


def multi_inputs(identifier):
    case = CASES[identifier]
    owner_id = "REQ-001" if case["owner"] == "platform" else "REQ-101"
    inputs = {ROOT_CONFIG_PATH: multi_config(identifier).encode(),
              "apps/web/.spec/bitz.yaml": multi_reference.member_config("web", "default").encode(),
              "services/api/.spec/bitz.yaml": multi_reference.plain_config("api").encode()}
    declared = {"implements": [case["path"]]} if case["field"] == "implements" else {"tests": [case["path"]]}
    inputs[prefixed(owner_prefix(case), f".spec/requirements/{owner_id}.md")] = requirement(owner_id, **declared).encode()
    for path in case["files"]:
        inputs[path] = content_of(path)
    return inputs


def reviewed_inputs(identifier):
    """`repo/`の通常のファイル（パス→バイト列）。シンボリックリンクは`reviewed_links`が持つ。"""
    return {"check": check_inputs, "verify": verify_inputs, "multi": multi_inputs}[CASES[identifier]["group"]](identifier)


def reviewed_links(identifier):
    link = CASES[identifier]["link"]
    return {link[0]: link[1]} if link else {}


def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def result_name(identifier):
    return "expected/verify.json" if CASES[identifier]["group"] == "verify" else "expected/check.json"


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["group"] == "verify":
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
        argv, cwd = ["verify", "REQ-001", "--format", "json"], "."
    else:
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
        if case["group"] == "multi":
            argv, cwd = ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"], "."
        else:
            argv, cwd = ["check", "--full", "--base", "HEAD", "--format", "json"], case["workspace"]
    status = reviewed_status(identifier)
    return {"fixtureId": identifier, "description": case["description"], "setup": setup_plan,
            "invocation": {"runner": "bitz", "cwd": cwd, "argv": argv, "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json", "resultFile": result_name(identifier), "reportFileCount": 0}}


def reviewed_status(identifier):
    case = CASES[identifier]
    if case["group"] == "verify":
        return case["kind"]
    return "failed" if case["outcome"] in ("outside", "violation") else "passed"


# --- 期待結果 ----------------------------------------------------------------------------------

def path_diagnostic(case):
    key = "implements" if case["field"] == "implements" else "tests[0].path"
    return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARIES[case["field"]],
            "source": {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md", "key": key}}


def check_result(identifier):
    case = CASES[identifier]
    rejected = case["outcome"] == "outside"
    return {"schemaVersion": "1.0", "operation": "check", "status": "failed" if rejected else "passed", "scope": "full",
            "workspace": {"id": "root", "path": "."}, "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": 1, "checkedStatementCount": 1, "durationMs": 0,
            "diagnostics": [path_diagnostic(case)] if rejected else []}


def multi_result(identifier):
    case = CASES[identifier]
    violation = case["outcome"] == "violation"
    owner_id = "REQ-001" if case["owner"] == "platform" else "REQ-101"
    diagnostic = {"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
                  "summary": f"パス{case['path']}の解決先がワークスペース{case['owner']}の所有領域の外です",
                  "source": {"kind": "file", "workspaceId": case["owner"], "path": f".spec/requirements/{owner_id}.md",
                            "key": "implements" if case["field"] == "implements" else "tests[0].path"}}
    entries = []
    for identifier_, path in (("platform", "."), ("api", "services/api"), ("web", "apps/web")):
        declares = identifier_ == case["owner"]
        entries.append({"id": identifier_, "path": path, "status": "failed" if declares and violation else "passed",
                        "checkedDocumentCount": 1 if declares else 0, "checkedStatementCount": 1 if declares else 0, "durationMs": 0,
                        "diagnostics": [diagnostic] if declares and violation else []})
    return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed" if violation else "passed",
            "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": entries,
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}


def verify_digest_input(identifier):
    """参照計算A。`SINGLE-042`のレビュー済みの材料に、`cwd`、テストのパス、TECH-002だけを加える（ソートは`tests[].path`の昇順）。"""
    case = CASES[identifier]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["cwd"] = case["cwd"]
    tech = payload["documents"][1]
    declared = tech_documents(identifier)
    tech["frontmatter"]["tests"] = sorted(({"path": path, "covers": [cover], "command": "default"} for path, cover in declared["TECH-001"]),
                                          key=lambda entry: entry["path"])
    if "TECH-002" in declared:
        payload["documents"].append({
            "id": "TECH-002", "workspaceId": "root", "kind": "technical", "status": "approved", "applicability": "applicable",
            "frontmatter": {"id": "TECH-002", "title": "別の実装方針", "status": "approved",
                            "relations": {**digest_reference.EMPTY_RELATIONS, "refines": ["REQ-001"]},
                            "implements": [], "tests": sorted(({"path": path, "covers": [cover], "command": "default"}
                                                                for path, cover in declared["TECH-002"]), key=lambda entry: entry["path"]),
                            "verify": None, "changes": []},
            "bodyText": TECH_002_BODY, "statements": [], "strongRelations": [{"relation": "refines", "target": "REQ-001"}]})
    return payload


def verify_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(verify_digest_input(identifier)))


def declared_tests(identifier):
    """宣言したテストのパス（重複なし。辞書順）。"""
    return sorted({path for tests in CASES[identifier]["tests"] for path in tests})


# レビュー済みの引数列（`passed`のケースだけ）。ケースの定義から手で導いた値で、参照計算（`reference_argv`）とは別に固定する。
ARGV = {"SINGLE-174-07": ["/bin/true", "test_auth.py", "test_session.py"], "SINGLE-174-10": ["/bin/true", "ext/test_auth.py", "ext/test_session.py"]}


def verify_result(identifier):
    case = CASES[identifier]
    blocked = case["kind"] == "blocked"
    entry = {"target": "REQ-001", "status": case["kind"], "contextDigest": verify_digest(identifier), "statements": list(STATEMENTS),
             "bindingRefs": [] if blocked else ["root::default"], "diagnostics": []}
    diagnostic = {"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked", "summary": OUTSIDE_SUMMARY,
                  "source": {"kind": "file", "workspaceId": "root", "path": case.get("source", (None, None))[0],
                            "key": f"tests[{case.get('source', (None, None))[1]}].path"}} if blocked else None
    result = {"schemaVersion": "1.0", "operation": "verify", "status": case["kind"], "scope": "selected",
              "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None, "commands": [], "durationMs": 0,
              "diagnostics": [diagnostic] if blocked else []}
    if not blocked:
        result["commands"] = [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed", "termination": "exit",
            "cwd": case["cwd"], "argv": list(ARGV[identifier]), "tests": declared_tests(identifier), "covers": list(STATEMENTS),
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False,
            "stderrTruncated": False, "durationMs": 0}]
    return result


def reviewed_result(identifier):
    return {"check": check_result, "verify": verify_result, "multi": multi_result}[CASES[identifier]["group"]](identifier)


# --- 準備手順の後の入力の検査 ---------------------------------------------------------------

def tracked_entries(repository):
    """インデックスのエントリ: パス→(モード, 内容)。"""
    result = {}
    for line in git(repository, "ls-files", "--stage", "-z").decode().split("\0")[:-1]:
        head, path = line.split("\t", 1)
        mode = head.split()[0]
        result[path] = (mode, git(repository, "show", ":" + path))
    return result


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
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
    if case["group"] != "verify":
        if git(repository, "status", "--porcelain=v1", "--untracked-files=all", "-z"):
            raise ValueError("作業ツリーは基準版のコミットと同じである必要があります")
        tree = git(repository, "ls-tree", "-r", "-z", "HEAD").decode().split("\0")[:-1]
        if {line.split("\t", 1)[1] for line in tree} != set(entries):
            raise ValueError("基準版のコミットとインデックスの追跡するパスが異なります")
    if case["link"] is not None and os.path.isabs(case["link"][1]):
        # リポジトリの外のディレクトリは、ホストのディレクトリで、宣言するファイルはファイルへ解決する必要がある（シンボリックリンクでもよい）。
        target = Path(case["link"][1]) / EXTERNAL_FILE
        if not target.is_file() or within(os.path.realpath(repository), os.path.realpath(case["link"][1])):
            raise ValueError("リポジトリの外のディレクトリのファイルがファイルとして存在する必要があります")
    if case["group"] in ("check", "multi"):
        outcome = reference_outcome(identifier, repository)
        if outcome != case["outcome"]:
            raise ValueError(f"入力から導く扱いが期待と異なります: {outcome}")
        if (old_outcome(identifier, repository) != case["outcome"]) != case["defective"]:
            raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
        status = "failed" if case["outcome"] in ("outside", "violation") else "passed"
    else:
        tests = declared_tests(identifier)
        if any(not os.path.isfile(repository / test) for test in tests):
            raise ValueError("宣言したテストは実在する通常のファイルである必要があります")
        argv = reference_argv(repository, case["cwd"], tests)
        status = "passed" if argv is not None else "blocked"
        if status != case["kind"]:
            raise ValueError(f"入力から導く結果の種類が期待と異なります: {status}")
        if (old_verify_outcome(identifier) != case["kind"]) != case["defective"]:
            raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
        if status == "passed":
            if ["/bin/true", *argv] != result["commands"][0]["argv"]:
                raise ValueError("引数列が参照計算と異なります")
        else:
            # 発生元は、配下にないテストを宣言した文書のうちパスの辞書順で最初の文書と、その文書の最小の添字。
            real_cwd = os.path.realpath(repository / case["cwd"])
            candidates = []
            for document in sorted(tech_documents(identifier)):
                path = f".spec/technical/{document}.md"
                for index, test in enumerate(path_ for path_, _ in tech_documents(identifier)[document]):
                    if not within(os.path.realpath(repository / test), real_cwd):
                        candidates.append((path, index))
            if min(candidates) != case["source"] or result["diagnostics"][0]["source"] != {
                    "kind": "file", "workspaceId": "root", "path": case["source"][0], "key": f"tests[{case['source'][1]}].path"}:
                raise ValueError("発生元が参照計算と異なります")
            if len(result["diagnostics"]) != 1 or result["commands"] or result["targetResults"][0]["bindingRefs"]:
                raise ValueError("遮断は診断1件で、起動せず、検証対象はテスト割当てを持たない必要があります")
            if len(case["tests"]) > 1 and min(index for _, index in candidates) == case["source"][1]:
                raise ValueError("複数の文書のケースは、全体の最小の添字と、辞書順で最初の文書の添字が異なる必要があります")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")


def check_digest(identifier, repository, result):
    if CASES[identifier]["group"] != "verify":
        return
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
    if digest_crosscheck.digest(derived) != result["targetResults"][0]["contextDigest"]:
        raise ValueError("検証対象のハッシュ値が参照計算Bと一致しません")
    if digest_reference.canonical_bytes(verify_digest_input(identifier)) != derived:
        raise ValueError("検証対象のハッシュ値の参照計算AとBが一致しません")


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
        (fixture / result_name(identifier)).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-real-path-") as temporary:
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
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / directory_of(identifier) / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / result_name(identifier)).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {Path(result_name(identifier)).name} or any(
                    (fixture / name).exists() for name in ("changes", "cli-output.json")):
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            files, links = actual_entries(fixture)
            if files != reviewed_inputs(identifier) or links != reviewed_links(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("実パスの所有の検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-real-path-") as temporary:
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
