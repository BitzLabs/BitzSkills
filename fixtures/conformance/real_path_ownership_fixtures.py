"""所有と包含を字句のパスで判定し、シンボリックリンクを辿らないことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C88・C90、N1・N3、ADR-051の追加と、ADR-071 Decision 1（2026-11-15の訂正）に対応する。このモジュールは、はじめ実パスの規範（ADR-042）で書き、
ユーザーの決定（ADR-071）で、次の字句の規範に直した。期待値の訂正はADR-051による（管理者の承認済み。根拠はADR-071と書き直した規範文）。

- 安全な入出力・互換性 §6: パスのシンボリックリンクを辿らない。途中のセグメントがシンボリックリンクのパスは拒否し、末端がシンボリックリンクのパスは通常のファイルにもディレクトリにも扱わない。
  存在は、基準のルートから各セグメントを親のディレクトリの項目名とNFCで完全一致させて確かめる。所有は、NFCにした字句のパスのセグメント単位の包含で判定し、実パスを使わない。
- ワークスペース・設定仕様 §9、関係・トレースモデル §9: `implements`と`tests[].path`は、通常のファイルとして存在するときだけ存在するパスとして扱い、途中または末端がシンボリックリンクのパスは、
  存在しないパスと同じく`SPEC-PATH-INVALID-001`（`error`／`failed`。承認済みの文言「実装パスが存在しません」「テストのパスが存在しません」。キーは`implements`、`tests[0].path`）とする。
  これは、リンク先がワークスペースの中でも外でも同じである（複合ワークスペースも同じ。複合ワークスペース仕様 §5.1の手順4）。字句のパスが別のワークスペースの所有領域にあれば`SPEC-MULTI-OWNERSHIP-001`とする。
- `verify` §4の4.: 使うテスト対応のテストのパスが、存在しない、途中または末端がシンボリックリンクなら、`SPEC-PATH-INVALID-001`（その検証対象は`failed`、`bindingRefs: []`、テストを起動しない）。
  これはテスト割当ての起動前の検査（`VERIFY-CWD-UNAVAILABLE`、`VERIFY-TEST-OUTSIDE-CWD`）より前なので、テストのパスが不正なら`cwd`は判定しない。
- `verify` §5.1・ワークスペース・設定仕様 §6: 実効`cwd`がディレクトリとして存在しなければ（途中または末端がシンボリックリンクを含む）`VERIFY-CWD-UNAVAILABLE`
  （`SPEC-VERIFY-BLOCKED-001`、`blocked`、`skip-binding`、`source`は設定ファイルの`verify.commands.<名前>.cwd`）。`cwd`の判定は、テストのパスと`cwd`の包含の判定の前提なので、
  `cwd`が利用できなければ、テストのパスが`cwd`の配下にないことは判定しない。

修正前のCore（`968bc84`）は、上位のディレクトリのシンボリックリンクを解決した実パスで判定し、リンク先がワークスペースの中なら受け付けていた。次の「診断の文言」は、承認済みの文言だけを使う。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-174-01` | `check --full --base HEAD` | REQの`tests[0].path`が`ext/env`。`ext -> /usr/bin`（リポジトリの外のディレクトリ） | `failed`／1。`SPEC-PATH-INVALID-001`、キー`tests[0].path`。修正前のCoreも通る |
| `SINGLE-174-02` | 同上 | REQの`implements`が`ext/env`。`ext -> /usr/bin` | `failed`／1。`SPEC-PATH-INVALID-001`、キー`implements`。修正前のCoreも通る |
| `SINGLE-174-03` | 同上 | REQの`tests[0].path`が`ext/t.py`。`ext -> real`（ワークスペースの中。2026-11-15に`passed`から`failed`へ訂正） | `failed`／1。キー`tests[0].path`。修正前のCoreは`passed`／0 |
| `SINGLE-174-04` | 同上 | REQの`implements`が`ext/a.py`。`ext -> real`（同上の訂正） | `failed`／1。キー`implements`。修正前のCoreは`passed`／0 |
| `SINGLE-174-05` | `check --full --base HEAD`（`pkg`で実行） | ワークスペースのルートが`pkg`。REQの`tests[0].path`が`ext/t.py`。`pkg/ext -> ../shared`（リポジトリの中でワークスペースの外） | `failed`／1。キー`tests[0].path`。修正前のCoreも通る |
| `SINGLE-174-06` | 同上 | 同じ配置で、REQの`implements`が`ext/a.py` | `failed`／1。キー`implements`。修正前のCoreも通る |
| `SINGLE-174-07` | `verify REQ-001` | `cwd`が`inner`（`inner -> real`）、テストが`real/test_*.py`（実在する通常のファイル。字句では`cwd`の外。2026-11-15に`passed`から`blocked`へ訂正） | `blocked`／2。`VERIFY-CWD-UNAVAILABLE`。修正前のCoreは`passed`／0 |
| `SINGLE-174-08` | 同上 | `cwd`が`tests`、テストが`tests/link/test_*.py`（`tests/link -> ../other`。途中のセグメントがシンボリックリンク。同上の訂正） | `failed`／1。TECH-001の`tests[0].path`・`tests[1].path`が`SPEC-PATH-INVALID-001`。修正前のCoreは`blocked`／2 |
| `SINGLE-174-09` | 同上 | `cwd`が`tests`。TECH-001が`tests[0]`に配下のテスト、`tests[1]`に`tests/link/test_auth.py`、TECH-002が`tests[0]`に`tests/link/test_auth.py`を宣言する | `failed`／1。TECH-001の`tests[1].path`とTECH-002の`tests[0].path`が`SPEC-PATH-INVALID-001`（同上の訂正）。修正前のCoreは`blocked`／2 |
| `SINGLE-174-10` | 同上 | `cwd`が`.`、テストが`ext/test_*.py`（`ext -> real`。同上の訂正） | `failed`／1。TECH-001の`tests[0].path`・`tests[1].path`が`SPEC-PATH-INVALID-001`。修正前のCoreは`passed`／0 |
| `MULTI-061-01` | `check --all-workspaces --base HEAD` | メンバー`web`のREQの`tests[0].path`が`ext/test_x.py`。`apps/web/ext -> ../../tests`（ルートの領域） | `failed`／1。`web`に`SPEC-PATH-INVALID-001`、キー`tests[0].path`（2026-11-15に`SPEC-MULTI-OWNERSHIP-001`から訂正） |
| `MULTI-061-02` | 同上 | ルートのREQの`implements`が`apps/web/src/a.py`（字句でメンバーの配下。変更なし） | `failed`／1。`platform`に`SPEC-MULTI-OWNERSHIP-001`、キー`implements` |
| `MULTI-061-03` | 同上 | `web`のREQの`implements`が`ext/a.py`。`apps/web/ext -> real`（`web`の中。2026-11-15に`passed`から`failed`へ訂正） | `failed`／1。`web`に`SPEC-PATH-INVALID-001`、キー`implements`。修正前のCoreは`passed`／0 |
| `MULTI-061-04` | 同上 | `web`のREQの`implements`が`ext/session.py`。`apps/web/ext -> ../../services/api/src`（別のメンバー） | `failed`／1。`web`に`SPEC-PATH-INVALID-001`（同上の訂正） |
| `MULTI-061-05` | 同上 | ルートのREQの`implements`が`lk/a.py`。`lk -> apps/web/src` | `failed`／1。`platform`に`SPEC-PATH-INVALID-001`（同上の訂正） |
| `MULTI-061-06` | 同上 | `web`のREQの`implements`が`ext/env`。`apps/web/ext -> /usr/bin`（リポジトリの外） | `failed`／1。`web`に`SPEC-PATH-INVALID-001`（同上の訂正） |
| `MULTI-061-07` | 同上 | ルートのREQの`tests[0].path`が`lib/test_x.py`。`lib -> shared`（ルートの領域の中。同上の訂正） | `failed`／1。`platform`に`SPEC-PATH-INVALID-001`、キー`tests[0].path`。修正前のCoreは`passed`／0 |

期待値は規範と承認済みの文言から導く参照計算（`lexical_path_reference`と、このモジュールの`reference_outcome`・`reference_verify`）で、`realpath`と`resolve`を使わない。
Coreの出力は根拠にしない。fixtureは、1つの原因だけを持つ（`cwd`がシンボリックリンクのケースは、テストが字句で`cwd`の外にもあるが、`cwd`の判定がその前提なので`cwd`だけが原因になる）。

規範から決まらず、既存の形で決めた点:
- `SPEC-PATH-INVALID-001`と`SPEC-MULTI-OWNERSHIP-001`の`key`は、`implements`はフィールド名、`tests`は`tests[i].path`にした（`SINGLE-024`、`MULTI-008`、`verify` §5.1の`tests[i].path`）。
- 失敗した文書も数える（`SINGLE-024`は`checkedDocumentCount`が1、`checkedStatementCount`が1。`MULTI-008`の`web`は文書1件）。
- `VERIFY-CWD-UNAVAILABLE`の結果の形（`blocked`、`bindingRefs`は空、`commands`は空、診断は最上位に1件、`source`は設定ファイル）は、`SINGLE-167-07`の形（`skip-binding`）と同じである。
- テストのパスの不正の結果の形（検証対象が`failed`、`bindingRefs`は空、診断は検証対象に1件ずつ）は、`SINGLE-175-01`の形（`skip-target`）と同じである。違反したエントリごとに1件で、
  `source`の仕様文書のパスと`key`の順に並べる。
- リポジトリの外のディレクトリは、サンドボックスの外へfixtureが書けないので、ホストの`/usr/bin`（ほとんどのLinuxとmacOSが持つ）を指す絶対パスのシンボリックリンクで置く。
  `/usr/bin/env`はファイルへ解決する必要がある（シンボリックリンクでもよい。監査が確かめる）。ホストに依存しない同じ性質（リポジトリの中でワークスペースの外）を`SINGLE-174-05`・`06`が押さえる。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unicodedata

from jsonschema import Draft202012Validator, ValidationError

from . import command_cwd_fixtures as command_cwd
from . import digest_crosscheck, digest_reference, multi_reference
from . import lexical_path_reference as lexical
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
CWD_SUMMARY = "コマンドの作業ディレクトリが利用できません"
PATH_SUMMARIES = {"implements": "実装パスが存在しません", "tests": "テストのパスが存在しません"}
EXIT = {"passed": 0, "failed": 1, "blocked": 2}
MEMBERS = (("web", "apps/web"), ("api", "services/api"))
ROOT_CONFIG_PATH = ".spec/bitz.yaml"
VERIFY_BLOCK = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'

# --- ケース -------------------------------------------------------------------------------
# group: `check`（単一ワークスペースの`check`）、`verify`（単一ワークスペースの`verify`）、`multi`（複合ワークスペースの`check --all-workspaces`）。
# check: workspace〈ワークスペースのルートのリポジトリからの相対パス〉, field〈implements|tests〉, path〈宣言したパス〉, link〈(置き場, 向き先)〉,
#        files〈実ファイルを置くパス〉, outcome〈missing（途中または末端がシンボリックリンクなので存在しないパスと同じ）|ok〉
# verify: cwd, link, kind〈passed|blocked|failed〉, tests〈宣言する文書ごとのテストのパス〉, files〈実ファイル〉, invalid〈`failed`のとき、不正なエントリ(文書, 添字)〉
# multi: owner〈宣言するワークスペース〉, field, path, link, files, outcome〈missing|violation（字句のパスが別の所有領域）|ok〉
# 共通: defective〈修正前のCore（`968bc84`）が違う結果を返すか。陰性対照で確かめた事実〉, step, description
CASES = {
    "SINGLE-174-01": dict(group="check", workspace=".", field="tests", path="ext/env", link=("ext", EXTERNAL_DIRECTORY), files=[],
                          outcome="missing", defective=False, step=2,
                          description="tests[].pathの上位のディレクトリがリポジトリの外を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-02": dict(group="check", workspace=".", field="implements", path="ext/env", link=("ext", EXTERNAL_DIRECTORY), files=[],
                          outcome="missing", defective=False, step=2,
                          description="implementsの上位のディレクトリがリポジトリの外を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-03": dict(group="check", workspace=".", field="tests", path="ext/t.py", link=("ext", "real"), files=["real/t.py"],
                          outcome="missing", defective=True, step=2,
                          description="tests[].pathの上位のディレクトリがワークスペースの中を指すシンボリックリンクでも、辿らず、存在しないパスと同じにする"),
    "SINGLE-174-04": dict(group="check", workspace=".", field="implements", path="ext/a.py", link=("ext", "real"), files=["real/a.py"],
                          outcome="missing", defective=True, step=2,
                          description="implementsの上位のディレクトリがワークスペースの中を指すシンボリックリンクでも、辿らず、存在しないパスと同じにする"),
    "SINGLE-174-05": dict(group="check", workspace="pkg", field="tests", path="ext/t.py", link=("pkg/ext", "../shared"), files=["shared/t.py"],
                          outcome="missing", defective=False, step=2,
                          description="tests[].pathの上位のディレクトリが、リポジトリの中でワークスペースの外を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-06": dict(group="check", workspace="pkg", field="implements", path="ext/a.py", link=("pkg/ext", "../shared"), files=["shared/a.py"],
                          outcome="missing", defective=False, step=2,
                          description="implementsの上位のディレクトリが、リポジトリの中でワークスペースの外を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "SINGLE-174-07": dict(group="verify", defective=True, cwd="inner", link=("inner", "real"), kind="blocked", step=4,
                          tests=[["real/test_auth.py", "real/test_session.py"]], files=["real/test_auth.py", "real/test_session.py"],
                          description="cwdがシンボリックリンクなら、リンク先がワークスペースの中でも、cwdが利用できないものとして起動前に遮断する（テストのcwdの配下の判定には進まない）"),
    "SINGLE-174-08": dict(group="verify", defective=True, cwd="tests", link=("tests/link", "../other"), kind="failed", step=4,
                          tests=[["tests/link/test_auth.py", "tests/link/test_session.py"]], files=["other/test_auth.py", "other/test_session.py"],
                          invalid=[("TECH-001", 0), ("TECH-001", 1)],
                          description="テストのパスの途中がシンボリックリンクなら、リンク先がワークスペースの中でも、存在しないパスと同じにし、検証対象をfailedにする"),
    "SINGLE-174-09": dict(group="verify", defective=True, cwd="tests", link=("tests/link", "../other"), kind="failed", step=4,
                          tests=[["tests/test_ok.py", "tests/link/test_auth.py"], ["tests/link/test_auth.py"]],
                          files=["tests/test_ok.py", "other/test_auth.py"], invalid=[("TECH-001", 1), ("TECH-002", 0)],
                          description="シンボリックリンクを経由するテストのパスを複数の文書が宣言するとき、違反したエントリごとに、宣言した文書とtests[i].pathを発生元にして1件ずつ返す"),
    "SINGLE-174-10": dict(group="verify", defective=True, cwd=".", link=("ext", "real"), kind="failed", step=4,
                          tests=[["ext/test_auth.py", "ext/test_session.py"]], files=["real/test_auth.py", "real/test_session.py"],
                          invalid=[("TECH-001", 0), ("TECH-001", 1)],
                          description="cwdが.でも、テストのパスの途中がシンボリックリンクなら、存在しないパスと同じにし、検証対象をfailedにする"),
    "MULTI-061-01": dict(group="multi", owner="web", field="tests", path="ext/test_x.py", link=("apps/web/ext", "../../tests"),
                         files=["tests/test_x.py"], outcome="missing", defective=True, step=5,
                         description="メンバーのtests[].pathの上位のディレクトリがシンボリックリンクなら、ルートの領域へ解決するとしても存在しないパスと同じにする"),
    "MULTI-061-02": dict(group="multi", owner="platform", field="implements", path="apps/web/src/a.py", link=None,
                         files=["apps/web/src/a.py"], outcome="violation", defective=False, step=5,
                         description="ルートワークスペースがimplementsで字句のままメンバーの配下を宣言したら所有境界の違反にする"),
    "MULTI-061-03": dict(group="multi", owner="web", field="implements", path="ext/a.py", link=("apps/web/ext", "real"),
                         files=["apps/web/real/a.py"], outcome="missing", defective=True, step=5,
                         description="メンバーのimplementsの上位のディレクトリがメンバーの中を指すシンボリックリンクでも、辿らず、存在しないパスと同じにする"),
    "MULTI-061-04": dict(group="multi", owner="web", field="implements", path="ext/session.py", link=("apps/web/ext", "../../services/api/src"),
                         files=["services/api/src/session.py"], outcome="missing", defective=True, step=5,
                         description="メンバーのimplementsの上位のディレクトリが別のメンバーを指すシンボリックリンクなら、存在しないパスと同じにする"),
    "MULTI-061-05": dict(group="multi", owner="platform", field="implements", path="lk/a.py", link=("lk", "apps/web/src"),
                         files=["apps/web/src/a.py"], outcome="missing", defective=True, step=5,
                         description="ルートのimplementsの上位のディレクトリがメンバーの配下を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "MULTI-061-06": dict(group="multi", owner="web", field="implements", path="ext/env", link=("apps/web/ext", EXTERNAL_DIRECTORY),
                         files=[], outcome="missing", defective=True, step=5,
                         description="メンバーのimplementsの上位のディレクトリがリポジトリの外を指すシンボリックリンクなら、存在しないパスと同じにする"),
    "MULTI-061-07": dict(group="multi", owner="platform", field="tests", path="lib/test_x.py", link=("lib", "shared"),
                         files=["shared/test_x.py"], outcome="missing", defective=True, step=5,
                         description="ルートのtests[].pathの上位のディレクトリがルートの領域の中を指すシンボリックリンクでも、辿らず、存在しないパスと同じにする"),
}
ROOTS = {"platform": ".", "web": "apps/web", "api": "services/api"}


def yaml_path(text):
    """フロントマターのパスのYAMLの書き方。NFCの文字列はそのまま（ASCIIを含む）、NFCでない文字列は二重引用符の`\\uXXXX`で書く（正規化形を変えない）。"""
    if text == unicodedata.normalize("NFC", text):
        return text
    return '"' + "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text) + '"'


def case_of(identifier):
    """ケースの定義。fixtureのIDか、同じ形のケースの辞書（`strict_path_fixtures`が入力と参照計算を共有する）を受け付ける。"""
    return CASES[identifier] if isinstance(identifier, str) else identifier


# --- 字句のパスの参照計算（Coreにも`pathown`にも`realpath`にも依存しない） --------------------------

def reference_outcome(identifier, repository):
    """準備手順の後の入力から、宣言したパスの扱いを導く（`check`と`multi`）: `missing`、`violation`、`ok`。"""
    case = case_of(identifier)
    if case["group"] == "check":
        workspace = repository / case["workspace"]
        return "ok" if lexical.lookup(workspace, case["path"], "file") == "ok" else "missing"
    prefix = owner_prefix(case)
    if lexical.lookup(repository / prefix, case["path"], "file") != "ok":
        return "missing"
    declared = case["path"] if prefix in ("", ".") else f"{prefix}/{case['path']}"
    return "ok" if lexical.owner(declared, ROOTS) == case["owner"] else "violation"


def owner_prefix(case):
    return "" if case["owner"] == "platform" else dict(MEMBERS)[case["owner"]]


def reference_verify(identifier, repository):
    """準備手順の後の入力から、`verify`の結果を導く（`verify` §4の4.と§5.1）。

    戻り値は`("failed", 不正なエントリ(文書, 添字)の列)`、`("blocked", None)`（`cwd`が利用できない）、`("outside", None)`（`cwd`の配下にないテストがある）、
    `("passed", 引数列)`のどれか。テストのパスの検査は、起動前の検査（`cwd`、`cwd`の包含）より前に行う。
    """
    case = case_of(identifier)
    declared = tech_documents(identifier)
    invalid = [(document, index) for document in sorted(declared)
               for index, (path, _) in enumerate(declared[document]) if lexical.lookup(repository, path, "file") != "ok"]
    if invalid:
        return "failed", invalid
    if lexical.lookup(repository, case["cwd"], "directory") != "ok":
        return "blocked", None
    tests = declared_tests(identifier)
    if any(not lexical.within(test, case["cwd"]) for test in tests):
        return "outside", None
    root = lexical.segments(case["cwd"])
    return "passed", ["/".join(lexical.segments(test)[len(root):]) for test in tests]


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
    case = case_of(identifier)
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
    case = case_of(identifier)
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    for name in TEST_NAMES:
        del inputs[f"tests/{name}"]
    for path in case["files"]:
        inputs[path] = content_of(path)
    inputs[digest_reference.CONFIG_PATH] = digest_reference.CONFIG.replace(
        command_cwd.CWD_LINE, f"      cwd: {case.get('cwdYaml', case['cwd'])}\n").encode()
    return inputs


def tech_documents(identifier):
    """宣言する文書のパス→(ID、`tests`の宣言(パス, 規範文)の並び)。"""
    case = case_of(identifier)
    documents = {"TECH-001": [(path, STATEMENTS[index]) for index, path in enumerate(case["tests"][0])]}
    if len(case["tests"]) > 1:
        documents["TECH-002"] = [(path, STATEMENTS[0]) for path in case["tests"][1]]
    return documents


def tech_text(identifier, document):
    """TECH-001は`SINGLE-042`の文書の`tests`だけを置き換え、TECH-002は`SINGLE-106-02`と同じ形の最小の具体化にする。"""
    tests = tech_documents(identifier)[document]
    block = "tests:\n" + "".join(f"  - path: {yaml_path(path)}\n    covers: [{cover}]\n    command: default\n" for path, cover in tests)
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
    case = case_of(identifier)
    root = multi_reference.root_config(MEMBERS, "platform")
    return root + (VERIFY_BLOCK if case["owner"] == "platform" and case["field"] == "tests" else "")


def multi_inputs(identifier):
    case = case_of(identifier)
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
    return {"check": check_inputs, "verify": verify_inputs, "multi": multi_inputs}[case_of(identifier)["group"]](identifier)


def reviewed_links(identifier):
    link = case_of(identifier)["link"]
    return {link[0]: link[1]} if link else {}


def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def result_name(identifier):
    return "expected/verify.json" if case_of(identifier)["group"] == "verify" else "expected/check.json"


def reviewed_manifest(identifier):
    case = case_of(identifier)
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
    case = case_of(identifier)
    if case["group"] == "verify":
        return case["kind"]
    return "failed" if case["outcome"] in ("missing", "violation") else "passed"


# --- 期待結果 ----------------------------------------------------------------------------------

def path_diagnostic(case):
    key = "implements" if case["field"] == "implements" else "tests[0].path"
    return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARIES[case["field"]],
            "source": {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md", "key": key}}


def check_result(identifier):
    case = case_of(identifier)
    rejected = case["outcome"] == "missing"
    return {"schemaVersion": "1.0", "operation": "check", "status": "failed" if rejected else "passed", "scope": "full",
            "workspace": {"id": "root", "path": "."}, "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": 1, "checkedStatementCount": 1, "durationMs": 0,
            "diagnostics": [path_diagnostic(case)] if rejected else []}


def multi_result(identifier):
    case = case_of(identifier)
    rejected = case["outcome"] in ("missing", "violation")
    owner_id = "REQ-001" if case["owner"] == "platform" else "REQ-101"
    key = "implements" if case["field"] == "implements" else "tests[0].path"
    source = {"kind": "file", "workspaceId": case["owner"], "path": f".spec/requirements/{owner_id}.md", "key": key}
    if case["outcome"] == "violation":
        diagnostic = {"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
                      "summary": f"パス{case['path']}の解決先がワークスペース{case['owner']}の所有領域の外です", "source": source}
    else:
        diagnostic = {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed",
                      "summary": PATH_SUMMARIES[case["field"]], "source": source}
    entries = []
    for identifier_, path in (("platform", "."), ("api", "services/api"), ("web", "apps/web")):
        declares = identifier_ == case["owner"]
        entries.append({"id": identifier_, "path": path, "status": "failed" if declares and rejected else "passed",
                        "checkedDocumentCount": 1 if declares else 0, "checkedStatementCount": 1 if declares else 0, "durationMs": 0,
                        "diagnostics": [diagnostic] if declares and rejected else []})
    return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed" if rejected else "passed",
            "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": entries,
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}


def verify_digest_input(identifier):
    """参照計算A。`SINGLE-042`のレビュー済みの材料に、`cwd`、テストのパス、TECH-002だけを加える（ソートは`tests[].path`の昇順）。"""
    case = case_of(identifier)
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
    return sorted({path for tests in case_of(identifier)["tests"] for path in tests})


def invalid_diagnostic(document, index):
    """テストのパスが不正なエントリの診断（`verify` §4の4.。`check`と同じ文言と発生元）。"""
    return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARIES["tests"],
            "source": {"kind": "file", "workspaceId": "root", "path": f".spec/technical/{document}.md", "key": f"tests[{index}].path"}}


def verify_result(identifier):
    case = case_of(identifier)
    blocked, failed = case["kind"] == "blocked", case["kind"] == "failed"
    entry = {"target": "REQ-001", "status": case["kind"], "contextDigest": verify_digest(identifier), "statements": list(STATEMENTS),
             "bindingRefs": [], "diagnostics": [invalid_diagnostic(document, index) for document, index in case["invalid"]] if failed else []}
    diagnostic = {"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked", "summary": CWD_SUMMARY,
                  "source": {"kind": "file", "workspaceId": "root", "path": command_cwd.CONFIG_PATH, "key": command_cwd.KEY}}
    return {"schemaVersion": "1.0", "operation": "verify", "status": case["kind"], "scope": "selected",
            "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None, "commands": [], "durationMs": 0,
            "diagnostics": [diagnostic] if blocked else []}


def reviewed_result(identifier):
    return {"check": check_result, "verify": verify_result, "multi": multi_result}[case_of(identifier)["group"]](identifier)


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
    case = case_of(identifier)
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
        if not (Path(case["link"][1]) / EXTERNAL_FILE).is_file():
            raise ValueError("リポジトリの外のディレクトリのファイルがファイルとして存在する必要があります")
    if case["group"] in ("check", "multi"):
        outcome = reference_outcome(identifier, repository)
        if outcome != case["outcome"]:
            raise ValueError(f"入力から導く扱いが期待と異なります: {outcome}")
        status = "failed" if case["outcome"] in ("missing", "violation") else "passed"
        if case["outcome"] == "missing" and case["link"] is not None:
            # 拒否の原因は、宣言したパスの途中のシンボリックリンクだけである。リンクを辿った先のファイルは存在する（辿れば通る入力）。
            base = repository / (case["workspace"] if case["group"] == "check" else owner_prefix(case))
            if not (os.path.islink(repository / case["link"][0]) and os.path.isfile(base / case["path"])):
                raise ValueError("リンクを辿れば存在する入力である必要があります")
    else:
        status, detail = reference_verify(identifier, repository)
        status = {"failed": "failed", "blocked": "blocked"}.get(status, status)
        if status != case["kind"]:
            raise ValueError(f"入力から導く結果の種類が期待と異なります: {status}")
        if status == "failed" and detail != case["invalid"]:
            raise ValueError(f"入力から導く不正なエントリが期待と異なります: {detail}")
        if any(not os.path.isfile(repository / test) for test in declared_tests(identifier)):
            # リンクを辿れば実在する入力にする（辿らないことだけが原因になる）。
            raise ValueError("宣言したテストは、リンクを辿れば実在する通常のファイルである必要があります")
        if result["commands"] or any(entry["bindingRefs"] for entry in result["targetResults"]):
            raise ValueError("起動しないケースは`commands`と`bindingRefs`が空である必要があります")
        if status == "failed":
            diagnostics = [d for entry in result["targetResults"] for d in entry["diagnostics"]]
            expected = [invalid_diagnostic(document, index) for document, index in detail]
            if diagnostics != expected or result["diagnostics"]:
                raise ValueError("診断が参照計算と異なります")
        elif len(result["diagnostics"]) != 1:
            raise ValueError("遮断は診断1件である必要があります")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")


def check_digest(identifier, repository, result):
    if case_of(identifier)["group"] != "verify":
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
